"""Hardware-independent checks for landmark-based pose classification."""

from pathlib import Path
import sys
from types import SimpleNamespace as Point
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gestures import classify_pose


def hand_points(extended=(True, True, True, True)):
    points = [Point(x=0.0, y=0.0, z=0.0) for _ in range(21)]
    points[4] = Point(x=-1.3, y=0.5, z=0)
    for x, (base, joint, tip), straight in zip(
        (-0.5, -0.15, 0.2, 0.5),
        ((5, 6, 8), (9, 10, 12), (13, 14, 16), (17, 18, 20)), extended,
    ):
        points[base] = Point(x=x, y=1.0, z=0)
        points[joint] = Point(x=x, y=1.5, z=0)
        points[tip] = Point(x=x, y=2.5 if straight else 1.0, z=0)
    return points


class PoseTests(unittest.TestCase):
    def test_open_palm(self):
        points = hand_points()
        for joint, tip in ((6, 8), (10, 12), (14, 16), (18, 20)):
            points[tip] = Point(x=points[joint].x + 0.4, y=1.9, z=0)
        for mirror in (1, -1):
            front = [Point(x=mirror * p.x, y=-p.y, z=p.z) for p in points]
            self.assertEqual(classify_pose(front).name, "Palm")

    def test_index_direction_distinguishes_up_from_toward_camera(self):
        points = hand_points((True, False, False, False))
        up = [Point(x=p.x, y=-p.y, z=p.z) for p in points]
        self.assertEqual(classify_pose(up).name, "Point up")
        for direction, expected in ((-1, "Cursor"), (1, "Point")):
            for index, depth in ((6, 0.5), (8, 1.5)):
                points[index] = Point(x=points[5].x, y=points[5].y, z=direction * depth)
            self.assertEqual(classify_pose(points).name, expected)

    def test_index_only_point(self):
        self.assertEqual(classify_pose(hand_points((True, False, False, False))).name, "Point")

    def test_fist(self):
        points = hand_points((False,) * 4)
        points[4] = Point(x=-0.2, y=0.5, z=0)
        self.assertEqual(classify_pose(points).name, "Fist")

    def test_pinch_is_scale_and_mirror_invariant(self):
        points = hand_points()
        points[4] = Point(x=points[8].x + 0.1, y=points[8].y, z=0)
        for scale in (-0.1, 1.0, 10.0):
            transformed = [Point(x=p.x * scale, y=p.y * scale, z=p.z * scale) for p in points]
            pose = classify_pose(transformed)
            self.assertEqual(pose.name, "Pinch")
            self.assertTrue(pose.pinching)

    def test_unknown_and_degenerate_inputs(self):
        self.assertEqual(classify_pose([]).name, "Tracking")
        self.assertEqual(classify_pose([Point(x=0, y=0, z=0)] * 21).name, "Tracking")
