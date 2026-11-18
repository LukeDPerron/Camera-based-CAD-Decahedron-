import os
import time
import urllib.request
from collections import Counter, deque

import numpy as np

from .gesture_event import LABEL_TO_GESTURE, GestureEvent, GestureType

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MODEL_PATH = os.path.join(ROOT, "hand_landmarker.task")
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/latest/hand_landmarker.task"
)
CLASSIFIER_PATH = os.path.join(ROOT, "models", "gesture_clf.pkl")


def ensure_model():
    if not os.path.exists(MODEL_PATH):
        print("Downloading hand model (about 8 MB, one time only)...")
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)


class GestureRecognizer:
    """Reads a camera frame and emits a GestureEvent.

    Uses the same MediaPipe HandLandmarker as data_collection/collect_gestures.py.
    If models/gesture_clf.pkl exists (trained on those CSVs), that classifier is used.
    Otherwise a landmark heuristic covers the five collected labels.
    """

    def __init__(self):
        ensure_model()
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision

        options = vision.HandLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=MODEL_PATH),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=1,
            min_hand_detection_confidence=0.6,
            min_hand_presence_confidence=0.6,
            min_tracking_confidence=0.5,
        )
        self._mp = mp
        self.landmarker = vision.HandLandmarker.create_from_options(options)
        self.start = time.monotonic()
        self.history = deque(maxlen=8)
        self.classifier = self._try_load_classifier()
        self.last_cursor = None
        self.last_hand_size = None
        self.last_landmarks = None

    def _try_load_classifier(self):
        if not os.path.exists(CLASSIFIER_PATH):
            return None
        try:
            import pickle

            with open(CLASSIFIER_PATH, "rb") as f:
                return pickle.load(f)
        except Exception as exc:
            print(f"Could not load {CLASSIFIER_PATH}: {exc}")
            return None

    def close(self) -> None:
        self.landmarker.close()

    def predict(self, frame, forced_label: str | None = None) -> GestureEvent:
        h, w = frame.shape[:2]
        rgb = frame[:, :, ::-1].copy()
        mp_image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
        timestamp_ms = int((time.monotonic() - self.start) * 1000)
        result = self.landmarker.detect_for_video(mp_image, timestamp_ms)

        self.last_landmarks = None
        cursor = None
        label = "none"
        confidence = 0.0

        if result.hand_landmarks:
            self.last_landmarks = result.hand_landmarks[0]
            tip = self.last_landmarks[8]
            cursor = (tip.x * w, tip.y * h)
            if forced_label:
                label, confidence = forced_label, 1.0
            elif self.classifier is not None and result.hand_world_landmarks:
                label, confidence = self._classify_model(result.hand_world_landmarks[0])
            else:
                label, confidence = self._classify_heuristic(self.last_landmarks)
        elif forced_label:
            label, confidence = forced_label, 1.0

        if not forced_label:
            self.history.append(label)
            label = Counter(self.history).most_common(1)[0][0]
        gesture = LABEL_TO_GESTURE.get(label, GestureType.NONE)
        return GestureEvent(
            type=gesture,
            confidence=confidence,
            cursor_pos=cursor,
            label=label,
        )

    def _classify_model(self, world) -> tuple[str, float]:
        feat = []
        for p in world:
            feat += [p.x, p.y, p.z]
        X = [feat]
        label = str(self.classifier.predict(X)[0])
        confidence = 0.8
        if hasattr(self.classifier, "predict_proba"):
            confidence = float(np.max(self.classifier.predict_proba(X)))
        return label, confidence

    def _classify_heuristic(self, lms) -> tuple[str, float]:
        def xy(i):
            return np.array([lms[i].x, lms[i].y], dtype=float)

        wrist = xy(0)

        def extended(tip, pip) -> bool:
            return np.linalg.norm(xy(tip) - wrist) > np.linalg.norm(xy(pip) - wrist) * 1.15

        thumb = extended(4, 3)
        index = extended(8, 6)
        middle = extended(12, 10)
        ring = extended(16, 14)
        pinky = extended(20, 18)
        others_curled = (not middle) and (not ring) and (not pinky)
        index_vec = xy(8) - xy(5)
        index_len = float(np.linalg.norm(index_vec))
        pointing_at_camera = index and index_len < 0.11 and lms[8].z < lms[5].z

        scores = {
            "none": 0.15,
        }
        label = max(scores, key=scores.get)
        return label, scores[label]
