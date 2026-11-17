"""Camera + MediaPipe worker. This module never touches Tk widgets.

Adapted from ../tmp/collect_gestures.py: same Tasks API, VIDEO mode,
confidence thresholds, and mirrored RGB input. No frames/data are recorded.
"""

from dataclasses import dataclass
from pathlib import Path
from queue import Empty, Full, Queue, SimpleQueue
from threading import Event, Lock, Thread
import platform
import time
import urllib.request

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

from gestures import classify_pose
from cameras import CameraDevice, resolve_camera


HERE = Path(__file__).resolve().parent
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/1/hand_landmarker.task"
)
CONNECTIONS = (
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (0, 17), (17, 18), (18, 19), (19, 20),
)


@dataclass(frozen=True)
class ViewOptions:
    mirror: bool = True
    landmarks: bool = True
    cursor: bool = True


@dataclass(frozen=True)
class Frame:
    rgb: np.ndarray
    hand: str
    gesture: str
    cursor: tuple[float, float] | None
    fps: float


def ensure_model() -> Path:
    """Reuse the reference asset; download atomically only when it is absent."""
    destination = HERE / "models" / "hand_landmarker.task"
    reference = HERE.parent / "tmp" / "hand_landmarker.task"
    for candidate in (destination, reference):
        if candidate.is_file():
            return candidate
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(".part")
    try:
        with urllib.request.urlopen(MODEL_URL, timeout=20) as source:
            with partial.open("wb") as target:
                while chunk := source.read(128 * 1024):
                    target.write(chunk)
        partial.replace(destination)
    except Exception as exc:
        partial.unlink(missing_ok=True)
        raise RuntimeError(
            "Could not download the hand model. Check your connection and retry, "
            "or copy hand_landmarker.task into ui/models/."
        ) from exc
    return destination


def open_camera(index: int, backend: int | None = None):
    system = platform.system()
    native = {"Darwin": cv2.CAP_AVFOUNDATION, "Windows": cv2.CAP_DSHOW}.get(
        system, cv2.CAP_ANY
    )
    # An enumerated device's index only has meaning for its specific backend.
    # Falling back to a different backend could open a different physical camera.
    backends = (backend,) if backend is not None else dict.fromkeys((native, cv2.CAP_ANY))
    for api in backends:
        cap = cv2.VideoCapture(index, api)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            cap.set(cv2.CAP_PROP_FPS, 30)
            return cap
        cap.release()
    raise RuntimeError(
        f"Could not open camera {index}. Allow camera access in system settings, "
        "close other apps using it, or refresh and select another camera."
    )


def draw_overlay(rgb: np.ndarray, landmarks, options: ViewOptions, pinching: bool):
    height, width = rgb.shape[:2]
    points = [(int(p.x * (width - 1)), int(p.y * (height - 1))) for p in landmarks]
    mint = (95, 230, 190)  # RGB, since this frame is already converted for Pillow.
    if options.landmarks:
        for a, b in CONNECTIONS:
            cv2.line(rgb, points[a], points[b], mint, 2, cv2.LINE_AA)
        for point in points:
            cv2.circle(rgb, point, 4, (235, 249, 245), -1, cv2.LINE_AA)
    if options.cursor:
        color = (255, 194, 102) if pinching else mint
        cv2.circle(rgb, points[8], 17 if pinching else 12, color, 2, cv2.LINE_AA)
        cv2.circle(rgb, points[8], 3, color, -1, cv2.LINE_AA)


class CameraWorker(Thread):
    def __init__(self, index: int | CameraDevice, options: ViewOptions):
        super().__init__(name="camera-tracker", daemon=True)
        self.index = index
        self.frames: Queue[Frame] = Queue(maxsize=1)
        self.events: SimpleQueue[tuple[str, str]] = SimpleQueue()
        self.stop_event = Event()
        self._options = options
        self._lock = Lock()

    def set_options(self, options: ViewOptions):
        with self._lock:
            self._options = options

    def stop(self):
        self.stop_event.set()

    def run(self):
        cap = None
        landmarker = None
        try:
            self.events.put(("loading", "Preparing hand tracker…"))
            model = ensure_model()
            if self.stop_event.is_set():
                return
            landmarker = vision.HandLandmarker.create_from_options(
                vision.HandLandmarkerOptions(
                    base_options=mp_python.BaseOptions(
                        model_asset_path=str(model),
                        delegate=mp_python.BaseOptions.Delegate.CPU,
                    ),
                    running_mode=vision.RunningMode.VIDEO,
                    num_hands=1,
                    min_hand_detection_confidence=0.6,
                    min_hand_presence_confidence=0.6,
                    min_tracking_confidence=0.5,
                )
            )
            if self.stop_event.is_set():
                return
            self.events.put(("loading", "Opening camera…"))
            if isinstance(self.index, CameraDevice):
                device = resolve_camera(self.index)
                cap = open_camera(device.index, device.backend)
            else:
                cap = open_camera(self.index)
            start = previous = time.monotonic()
            timestamp = -1
            failures = 0
            fps = 0.0
            stable_pose = pending_pose = "Tracking"
            pose_frames = 0
            while not self.stop_event.is_set():
                ok, bgr = cap.read()
                if not ok or bgr is None:
                    failures += 1
                    if failures >= 10:
                        raise RuntimeError(
                            "The camera stopped sending frames. Reconnect it, "
                            "check camera permissions, and press Start camera."
                        )
                    self.stop_event.wait(0.05)
                    continue
                failures = 0
                with self._lock:
                    options = self._options
                if options.mirror:
                    bgr = cv2.flip(bgr, 1)
                rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                timestamp = max(timestamp + 1, int((time.monotonic() - start) * 1000))
                result = landmarker.detect_for_video(
                    mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), timestamp
                )
                hand, gesture, cursor = "No hand", "—", None
                if result.hand_landmarks:
                    landmarks = result.hand_landmarks[0]
                    pose = classify_pose(result.hand_world_landmarks[0])
                    pose_frames = pose_frames + 1 if pending_pose == pose.name else 1
                    pending_pose = pose.name
                    if pose_frames >= 3:
                        stable_pose = pending_pose
                    gesture = stable_pose
                    hand = result.handedness[0][0].category_name
                    # The Tasks model predicts handedness on unmirrored input.
                    # Mirroring the input reverses its Left/Right prediction.
                    if options.mirror:
                        hand = "Left" if hand == "Right" else "Right"
                    cursor = (landmarks[8].x, landmarks[8].y)
                    draw_overlay(rgb, landmarks, options, pose.pinching)
                else:
                    stable_pose = pending_pose = "Tracking"
                    pose_frames = 0
                now = time.monotonic()
                measured = 1 / max(now - previous, 1e-6)
                fps = measured if not fps else 0.9 * fps + 0.1 * measured
                previous = now
                packet = Frame(rgb, hand, gesture, cursor, fps)
                # Keep only the newest frame so inference never queues behind Tk.
                try:
                    self.frames.get_nowait()
                except Empty:
                    pass
                try:
                    self.frames.put_nowait(packet)
                except Full:
                    pass
        except Exception as exc:
            self.events.put(("error", str(exc)))
        finally:
            if cap is not None:
                cap.release()
            if landmarker is not None:
                landmarker.close()
            self.events.put(("stopped", "Camera stopped"))
