"""Small geometric pose indicators, separate from the AI landmark detector.

These are intentionally basic previews, not the custom classifier that the
reference CSV collection script is collecting training data for.
"""

from dataclasses import dataclass
<<<<<<< HEAD
from math import dist
=======
from math import atan2, cos, dist, hypot, pi, sin
>>>>>>> milesBranch
from typing import Sequence


@dataclass(frozen=True)
class Pose:
    name: str
    pinching: bool = False
    pinky_up: bool = False


def _xyz(point):
    return (point.x, point.y, point.z)


def _straight(points, base: int, joint: int, tip: int) -> bool:
    a, b, c = (_xyz(points[i]) for i in (base, joint, tip))
    v = tuple(x - y for x, y in zip(a, b))
    w = tuple(x - y for x, y in zip(c, b))
    magnitude = dist(a, b) * dist(c, b)
    if magnitude < 1e-10:
        return False
    cosine = sum(x * y for x, y in zip(v, w)) / magnitude
<<<<<<< HEAD
    # Allow a relaxed bend and measure reach from the finger's own knuckle.
    # A wrist-distance test can reject extended fingers on a front-on palm.
=======
>>>>>>> milesBranch
    return cosine < -0.5 and dist(a, c) >= 0.85 * (dist(a, b) + dist(b, c))


def pinky_extended(points: Sequence) -> bool:
    return len(points) == 21 and _straight(points, 17, 18, 20)


def palm_roll(image_landmarks: Sequence, aspect: float, previous: float | None) -> float | None:
    """Estimate in-plane rotation from the wrist and four knuckles."""
    wrist = image_landmarks[0]
    knuckles = [image_landmarks[i] for i in (5, 9, 13, 17)]
    dx = (sum(p.x for p in knuckles) / 4 - wrist.x) * aspect
    dy = wrist.y - sum(p.y for p in knuckles) / 4
    index, pinky = knuckles[0], knuckles[-1]
    across_x = (pinky.x - index.x) * aspect
    across_y = index.y - pinky.y
    width = hypot(across_x, across_y)
    if hypot(dx, dy) >= max(0.002, 0.45 * width):
        angle = atan2(dy, dx)
    elif previous is not None and width >= 0.002:
        angle = atan2(across_y, across_x) + pi / 2
        if cos(angle - previous) < 0:
            angle += pi
    else:
        return previous
    if previous is None:
        return angle
    delta = angle - previous
    return previous + 0.55 * atan2(sin(delta), cos(delta))


def palm_yaw(world_landmarks: Sequence, previous: float | None) -> float | None:
    """Track an upright wrist twist from the depth of the outer knuckles."""
    index, pinky = world_landmarks[5], world_landmarks[17]
    x, y, z = (pinky.x - index.x, pinky.y - index.y, pinky.z - index.z)
    across = hypot(x, z)
    if across < max(1e-8, 0.30 * hypot(x, y, z)):
        return previous
    return _smooth_tilt(atan2(-z, x), previous)


def palm_pitch(world_landmarks: Sequence, previous: float | None) -> float | None:
    """Track forward and backward tilt using the wrist-to-knuckles axis."""
    wrist = world_landmarks[0]
    knuckles = [world_landmarks[i] for i in (5, 9, 13, 17)]
    x = sum(p.x for p in knuckles) / 4 - wrist.x
    y = wrist.y - sum(p.y for p in knuckles) / 4
    z = sum(p.z for p in knuckles) / 4 - wrist.z
    if hypot(y, z) < max(1e-8, 0.30 * hypot(x, y, z)):
        return previous
    return _smooth_tilt(atan2(z, y), previous)


def _smooth_tilt(angle: float, previous: float | None) -> float:
    if previous is None:
        return angle
    delta = angle - previous
    return previous + 0.65 * atan2(sin(delta), cos(delta))


def classify_pose(world_landmarks: Sequence, was_pinching: bool = False, *,
                  image_landmarks: Sequence | None = None, aspect: float = 1.0) -> Pose:
    """Use palm-relative distances so left/right hands and scale behave alike."""
    if len(world_landmarks) != 21:
        return Pose("Tracking")
    points = world_landmarks
    palm_width = dist(_xyz(points[5]), _xyz(points[17]))
    if palm_width < 1e-8:
        return Pose("Tracking")
    extended = [_straight(points, *finger) for finger in
                ((5, 6, 8), (9, 10, 12), (13, 14, 16))]
    extended.append(pinky_extended(points))
    pinch_ratio = dist(_xyz(points[4]), _xyz(points[8])) / palm_width
    if was_pinching and image_landmarks is not None and pinch_ratio < 1.05:
        wrist, thumb, index, tip, middle, pinky = (image_landmarks[i] for i in (0, 4, 5, 8, 9, 17))
        span = max(hypot((index.x - pinky.x) * aspect, index.y - pinky.y),
                   hypot((wrist.x - middle.x) * aspect, wrist.y - middle.y))
        separation = hypot((thumb.x - tip.x) * aspect, thumb.y - tip.y)
        # During a turn, depth estimates can split fingertips that are still
        # together in the image. Use overlap only to sustain an existing grab.
        if span > 0 and separation < 0.20 * span:
            return Pose("Pinch", pinching=True, pinky_up=extended[3])
    if extended == [True, False, False, True]:
        tips = [_xyz(points[i]) for i in (4, 12, 16)]
        if max(dist(tips[0], tips[1]), dist(tips[0], tips[2]),
               dist(tips[1], tips[2])) < 0.38 * palm_width:
            return Pose("Cat")
    if extended == [False, True, False, False]:
        return Pose("Middle finger")
    folded = not any(extended)
    thumb_out = dist(_xyz(points[4]), _xyz(points[17])) / palm_width
    index_reach = dist(_xyz(points[5]), _xyz(points[8])) / palm_width
    if folded and thumb_out < 1.6 and index_reach < 0.40:
        return Pose("Fist")
    if pinch_ratio < (0.55 if was_pinching else 0.42):
        return Pose("Pinch", pinching=True, pinky_up=extended[3])
    if all(extended):
        return Pose("Palm")
    if extended == [True, False, False, False]:
<<<<<<< HEAD
        base = _xyz(points[5])
        tip = _xyz(points[8])
        length = dist(base, tip)
        # MediaPipe's camera-aligned axes have positive Y down and positive Z
        # away from the camera. Horizontal mirroring leaves both tests intact.
        if base[2] - tip[2] >= 0.70 * length:
            return Pose("Cursor")
        if base[1] - tip[1] >= 0.70 * length:
            return Pose("Point up")
=======
        base, tip = _xyz(points[5]), _xyz(points[8])
        length = dist(base, tip)
        if base[1] - tip[1] >= 0.70 * length:
            return Pose("Point up")
        if base[2] - tip[2] >= 0.70 * length:
            return Pose("Cursor")
>>>>>>> milesBranch
        return Pose("Point")
    if folded:
        return Pose("Thumb out" if thumb_out >= 1.6 else "Fist")
    return Pose("Tracking")


class SixSevenMotion:
    """Recognize alternating up and down strokes from two tracked palms."""

    STROKE_HEIGHT = 0.045
    MAX_SAMPLE_GAP = 0.25
    MAX_STROKE_GAP = 0.65

    def __init__(self):
        self.reset()

    def reset(self):
        self.anchor = None
        self.last_sample = None
        self.last_stroke = None
        self.direction = 0
        self.reversals = 0

    def update(self, palms, now):
        if set(palms) != {"Left", "Right"}:
            self.reset()
            return None
        if self.last_sample is not None and now - self.last_sample > self.MAX_SAMPLE_GAP:
            self.reset()
        self.last_sample = now
        left, right = palms["Left"], palms["Right"]
        if (self.anchor is None or
                (self.last_stroke is not None and now - self.last_stroke > self.MAX_STROKE_GAP)):
            self.anchor = (left[1], right[1])
            self.last_stroke = None
            self.direction = self.reversals = 0
            return None

        dl, dr = left[1] - self.anchor[0], right[1] - self.anchor[1]
        if min(abs(dl), abs(dr)) >= self.STROKE_HEIGHT:
            if dl * dr < 0:
                direction = 1 if dl > 0 else -1
                if self.direction and self.direction != direction:
                    self.reversals += 1
                self.direction = direction
                self.last_stroke = now
            self.anchor = (left[1], right[1])

        if self.reversals >= 2:
            return (left, right) if left[0] <= right[0] else (right, left)
        return None
