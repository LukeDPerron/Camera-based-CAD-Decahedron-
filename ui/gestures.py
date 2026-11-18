"""Small geometric pose indicators, separate from the AI landmark detector.

These are intentionally basic previews, not the custom classifier that the
reference CSV collection script is collecting training data for.
"""

from dataclasses import dataclass
from math import dist
from typing import Sequence


@dataclass(frozen=True)
class Pose:
    name: str
    pinching: bool = False


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
    return cosine < -0.5 and dist(a, c) >= 0.85 * (dist(a, b) + dist(b, c))


def classify_pose(world_landmarks: Sequence, was_pinching: bool = False) -> Pose:
    """Use palm-relative distances so left/right hands and scale behave alike."""
    if len(world_landmarks) != 21:
        return Pose("Tracking")
    points = world_landmarks
    palm_width = dist(_xyz(points[5]), _xyz(points[17]))
    if palm_width < 1e-8:
        return Pose("Tracking")
    extended = [_straight(points, *finger) for finger in
                ((5, 6, 8), (9, 10, 12), (13, 14, 16), (17, 18, 20))]
    if extended == [False, True, False, False]:
        return Pose("Middle finger")
    pinch_ratio = dist(_xyz(points[4]), _xyz(points[8])) / palm_width
    if pinch_ratio < (0.55 if was_pinching else 0.42):
        return Pose("Pinch", pinching=True)
    if all(extended):
        return Pose("Open palm")
    if extended == [True, False, False, False]:
        base, tip = _xyz(points[5]), _xyz(points[8])
        length = dist(base, tip)
        if base[1] - tip[1] >= 0.70 * length:
            return Pose("Point up")
        if base[2] - tip[2] >= 0.70 * length:
            return Pose("Cursor")
        return Pose("Point")
    if not any(extended):
        thumb_out = dist(_xyz(points[4]), _xyz(points[17])) / palm_width
        return Pose("Thumb out" if thumb_out >= 1.6 else "Fist")
    return Pose("Tracking")
