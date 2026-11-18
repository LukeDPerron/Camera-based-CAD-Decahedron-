"""Camera + MediaPipe worker. This module never touches Tk widgets.

Adapted from ../tmp/collect_gestures.py: same Tasks API, VIDEO mode,
confidence thresholds, and mirrored RGB input. No frames/data are recorded.
"""

from dataclasses import dataclass
from pathlib import Path
from queue import Empty, Full, Queue, SimpleQueue
from threading import Event, Lock, Thread
import platform
from math import hypot
import time
import urllib.request

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

from gestures import SixSevenMotion, classify_pose, palm_roll as estimate_palm_roll
from gestures import palm_pitch as estimate_palm_pitch
from gestures import palm_yaw as estimate_palm_yaw
from gestures import pinky_extended
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
    single_hand: bool = False


@dataclass(frozen=True)
class Frame:
    rgb: np.ndarray
    hand: str
    gesture: str
    cursor: tuple[float, float] | None
    fps: float
    pinching: bool = False
    palm: tuple[float, float] | None = None
    palm_scale: float | None = None
    palm_roll: float | None = None
    pinky_up: bool = False
    cat: tuple[float, float] | None = None
    six_seven: tuple[tuple[float, float], tuple[float, float]] | None = None
    hand_count: int = 0
    index_tip: tuple[float, float] | None = None
    palm_yaw: float | None = None
    palm_pitch: float | None = None


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


def draw_overlay(rgb: np.ndarray, landmarks, options: ViewOptions, pinching: bool,
                 cursor: tuple[float, float] | None):
    height, width = rgb.shape[:2]
    points = [(int(p.x * (width - 1)), int(p.y * (height - 1))) for p in landmarks]
    mint = (95, 230, 190)  # RGB, since this frame is already converted for Pillow.
    if options.landmarks:
        for a, b in CONNECTIONS:
            cv2.line(rgb, points[a], points[b], mint, 2, cv2.LINE_AA)
        for point in points:
            cv2.circle(rgb, point, 4, (235, 249, 245), -1, cv2.LINE_AA)
    if options.cursor and cursor is not None:
        color = (255, 194, 102) if pinching else mint
        aim = (int(cursor[0] * (width - 1)), int(cursor[1] * (height - 1)))
        cv2.circle(rgb, aim, 17 if pinching else 12, color, 2, cv2.LINE_AA)
        cv2.circle(rgb, aim, 3, color, -1, cv2.LINE_AA)


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
                    num_hands=1 if self._options.single_hand else 2,
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
            pinching = False
            primary = None
            previous_roll = previous_yaw = previous_pitch = last_hand_seen = None
            previous_mirror = None
            six_seven_motion = SixSevenMotion()
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
                aspect = rgb.shape[1] / rgb.shape[0]
                sample_time = time.monotonic()
                timestamp = max(timestamp + 1, int((sample_time - start) * 1000))
                result = landmarker.detect_for_video(
                    mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), timestamp
                )
                hand, gesture, cursor = "No hand", "—", None
                index_tip = None
                palm = palm_scale = palm_roll = palm_yaw = palm_pitch = None
                pinky_up = False
                cat = None
                palms = {}
                if result.hand_landmarks:
                    labels = [categories[0].category_name for categories in result.handedness]
                    if options.mirror != previous_mirror:
                        six_seven_motion.reset()
                    display_labels = [
                        {"Left": "Right", "Right": "Left"}.get(label, label) if options.mirror else label
                        for label in labels
                    ]
                    index = labels.index(primary) if primary in labels else 0
                    if (labels[index] != primary or options.mirror != previous_mirror
                            or last_hand_seen is None or sample_time - last_hand_seen > 0.5):
                        stable_pose = pending_pose = "Tracking"
                        pose_frames = 0
                        pinching = False
                        previous_roll = previous_yaw = previous_pitch = None
                    primary = labels[index]
                    last_hand_seen = sample_time
                    previous_mirror = options.mirror
                    landmarks = result.hand_landmarks[index]
                    primary_world = result.hand_world_landmarks[index]
                    pose = classify_pose(primary_world, pinching,
                                         image_landmarks=landmarks, aspect=aspect)
                    for hand_index, world_points in enumerate(result.hand_world_landmarks):
                        hand_points = result.hand_landmarks[hand_index]
                        wrist_point, knuckle = hand_points[0], hand_points[9]
                        palms[display_labels[hand_index]] = (
                            (wrist_point.x + knuckle.x) / 2, (wrist_point.y + knuckle.y) / 2)
                        if hand_index != index:
                            draw_overlay(rgb, hand_points, options, False, None)
                        hand_pose = pose if hand_index == index else classify_pose(world_points)
                        if hand_pose.name == "Cat" and (cat is None or hand_index == index):
                            cat = (knuckle.x, knuckle.y)
                    pinching = pose.pinching
                    pinky_up = pose.pinky_up if pinching else pinky_extended(primary_world)
                    pose_frames = pose_frames + 1 if pending_pose == pose.name else 1
                    pending_pose = pose.name
                    if pose_frames >= 3:
                        stable_pose = pending_pose
                    gesture = stable_pose
                    if gesture == "Middle finger" and pose.name != gesture:
                        gesture = pose.name
                    hand = display_labels[index]
                    index_tip = cursor = (landmarks[8].x, landmarks[8].y)
                    if pinching:
                        cursor = ((cursor[0] + landmarks[4].x) / 2,
                                  (cursor[1] + landmarks[4].y) / 2)
                    wrist, middle = landmarks[0], landmarks[9]
                    palm = palms[hand]
                    palm_dx = (middle.x - wrist.x) * aspect
                    palm_dy = wrist.y - middle.y
                    palm_length = hypot(palm_dx, palm_dy)
                    # Compensate for the palm looking shorter when it tilts.
                    world_wrist, world_middle = primary_world[0], primary_world[9]
                    planar = hypot(world_middle.x - world_wrist.x,
                                   world_middle.y - world_wrist.y)
                    full_span = hypot(planar, world_middle.z - world_wrist.z)
                    palm_scale = (palm_length * full_span / max(planar, 0.55 * full_span)
                                  if palm_length >= 0.002 and full_span > 0 else None)
                    palm_roll = previous_roll = estimate_palm_roll(landmarks, aspect, previous_roll)
                    palm_yaw = previous_yaw = estimate_palm_yaw(primary_world, previous_yaw)
                    palm_pitch = previous_pitch = estimate_palm_pitch(primary_world, previous_pitch)
                    draw_overlay(rgb, landmarks, options, pinching, cursor)
                else:
                    stable_pose = pending_pose = "Tracking"
                    pose_frames = 0
                now = time.monotonic()
                six_seven = six_seven_motion.update(palms, sample_time)
                measured = 1 / max(now - previous, 1e-6)
                fps = measured if not fps else 0.9 * fps + 0.1 * measured
                previous = now
                packet = Frame(rgb, hand, gesture, cursor, fps, cursor is not None and pinching,
                               palm, palm_scale, palm_roll, pinky_up, cat, six_seven,
                               len(result.hand_landmarks), index_tip, palm_yaw, palm_pitch)
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
