"""Hardware-independent checks for bounded frames, and resource cleanup."""

from pathlib import Path
from queue import Empty
import sys
from types import SimpleNamespace as Point
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

<<<<<<< HEAD
from test_gestures import hand_points
from tracking import CameraWorker, ViewOptions, open_camera


=======
from gestures import SixSevenMotion, classify_pose, palm_pitch, palm_roll, palm_yaw
from tracking import CameraWorker, ViewOptions, open_camera


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
    def test_palm_pitch_distinguishes_forward_and_backward_tilts(self):
        from math import pi

        for direction in (-1, 1):
            points = [Point(x=p.x, y=-p.y, z=direction * p.y) for p in hand_points()]
            self.assertAlmostEqual(palm_pitch(points, None), direction * pi / 4)

    def test_palm_yaw_detects_a_twist_with_an_upright_index(self):
        from math import pi

        hand = [Point(x=p.x, y=-p.y, z=p.z)
                for p in hand_points((True, False, False, False))]
        self.assertEqual(classify_pose(hand).name, "Point up")
        edge_on = [Point(x=p.z, y=p.y, z=-p.x) for p in hand]
        self.assertEqual(classify_pose(edge_on).name, "Point up")
        self.assertAlmostEqual(palm_yaw(hand, None), 0)
        self.assertAlmostEqual(palm_yaw(edge_on, None), pi / 2)
        self.assertGreater(palm_yaw(edge_on, 0), pi / 4)

    def test_projected_fingertip_overlap_sustains_only_an_existing_pinch(self):
        points = hand_points()
        points[4] = Point(x=points[8].x, y=points[8].y, z=.8)
        self.assertFalse(classify_pose(points, image_landmarks=points).pinching)
        self.assertTrue(classify_pose(points, True, image_landmarks=points).pinching)
        separated = points.copy()
        separated[4] = Point(x=0, y=points[8].y, z=.8)
        self.assertFalse(classify_pose(points, True, image_landmarks=separated).pinching)

    def test_palm_roll_uses_knuckles_when_the_wrist_axis_is_foreshortened(self):
        from math import pi

        points = hand_points()
        points[0] = Point(x=0, y=1.01)
        self.assertAlmostEqual(palm_roll(points, 1, pi / 2), pi / 2)
        self.assertAlmostEqual(palm_roll(points, 1, -pi / 2), -pi / 2)
        self.assertIsNone(palm_roll(points, 1, None))

    def test_cat_requires_all_three_fingertips_to_touch(self):
        points = hand_points((True, False, False, True))
        for index in (4, 12, 16):
            points[index] = Point(x=0, y=1.1, z=0)
        self.assertEqual(classify_pose(points).name, "Cat")
        points[16] = Point(x=.5, y=1.1, z=0)
        self.assertNotEqual(classify_pose(points).name, "Cat")

    def test_six_seven_requires_two_hands_and_repeated_opposite_motion(self):
        motion = SixSevenMotion()
        high_low = {"Left": (.3, .4), "Right": (.7, .6)}
        low_high = {"Left": (.3, .6), "Right": (.7, .4)}
        both_high = {"Left": (.3, .3), "Right": (.7, .3)}
        both_low = {"Left": (.3, .7), "Right": (.7, .7)}
        for now, palms in ((0, both_high), (.1, both_low), (.2, both_high),
                           (.3, {}), (.4, high_low), (.5, low_high), (.6, high_low)):
            self.assertIsNone(motion.update(palms, now))
        self.assertEqual(motion.update(low_high, .7), ((.3, .6), (.7, .4)))
        for now in (.85, 1.0, 1.15, 1.3):
            self.assertIsNotNone(motion.update(low_high, now))
        self.assertIsNone(motion.update(low_high, 1.4))
        self.assertIsNone(motion.update({"Left": (.3, .4)}, 1.5))

    def test_pinky_up_pinch_and_tucked_fist(self):
        points = hand_points((True, False, False, True))
        points[4] = points[8]
        self.assertTrue(classify_pose(points).pinky_up)
        points = hand_points((False,) * 4)
        points[4] = points[8]
        self.assertEqual(classify_pose(points).name, "Fist")

    def test_middle_finger_alone(self):
        points = hand_points((False, True, False, False))
        points[4] = points[8]
        self.assertEqual(classify_pose(points).name, "Middle finger")

    def test_legacy_direction_poses(self):
        points = hand_points((True, False, False, False))
        self.assertEqual(classify_pose([Point(x=p.x, y=-p.y, z=p.z)
                                        for p in points]).name, "Point up")
        self.assertEqual(classify_pose(hand_points((False,) * 4)).name, "Thumb out")

    def test_open_palm(self):
        self.assertEqual(classify_pose(hand_points()).name, "Open palm")

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


>>>>>>> milesBranch
class CameraTests(unittest.TestCase):
    def test_native_backends_fall_back_and_release_failed_capture(self):
        import cv2
        for system, backend in (("Darwin", cv2.CAP_AVFOUNDATION), ("Windows", cv2.CAP_DSHOW)):
            with self.subTest(system=system):
                failed, working = MagicMock(), MagicMock()
                failed.isOpened.return_value = False
                working.isOpened.return_value = True
                with patch("tracking.platform.system", return_value=system), patch(
                    "tracking.cv2.VideoCapture", side_effect=[failed, working]
                ) as create:
                    self.assertIs(open_camera(2), working)
                self.assertEqual(create.call_args_list[0].args, (2, backend))
                self.assertEqual(create.call_args_list[1].args, (2, cv2.CAP_ANY))
                failed.release.assert_called_once()

    def test_missing_camera_gives_actionable_error(self):
        cap = MagicMock()
        cap.isOpened.return_value = False
        with patch("tracking.cv2.VideoCapture", return_value=cap):
            with self.assertRaisesRegex(RuntimeError, "Allow camera access"):
                open_camera(999)
        self.assertGreaterEqual(cap.release.call_count, 1)


class WorkerTests(unittest.TestCase):
    def _events(self, worker):
        events = []
        while True:
            try:
                events.append(worker.events.get_nowait())
            except Empty:
                return events

    def _setup(self):
        worker = CameraWorker(0, ViewOptions())
        cap, detector = MagicMock(), MagicMock()
        detector.detect_for_video.return_value = Point(hand_landmarks=[])
        return worker, cap, detector

    def test_latest_frame_only_strict_timestamps_and_stop_cleanup(self):
        worker, cap, detector = self._setup()
        calls = 0

        def read():
            nonlocal calls
            calls += 1
            if calls == 5:
                worker.stop()
            return True, np.full((48, 64, 3), calls, dtype=np.uint8)

        cap.read.side_effect = read
        with patch("tracking.ensure_model", return_value=Path("unused.task")), patch(
            "tracking.vision.HandLandmarker.create_from_options", return_value=detector
        ), patch("tracking.open_camera", return_value=cap):
            worker.start()
            worker.join(timeout=5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(worker.frames.qsize(), 1)
        self.assertTrue(np.all(worker.frames.get_nowait().rgb == 5))
        timestamps = [c.args[1] for c in detector.detect_for_video.call_args_list]
        self.assertTrue(all(a < b for a, b in zip(timestamps, timestamps[1:])))
        cap.release.assert_called_once()
        detector.close.assert_called_once()
        self.assertFalse(any(kind == "error" for kind, _ in self._events(worker)))

    def test_physical_handedness_with_and_without_mirror(self):
        for mirror in (False, True):
            for physical_hand in ("Left", "Right"):
                with self.subTest(mirror=mirror, hand=physical_hand):
                    worker, cap, detector = self._setup()
                    worker.set_options(ViewOptions(mirror=mirror))
                    predicted = (
                        {"Left": "Right", "Right": "Left"}[physical_hand]
                        if mirror else physical_hand
                    )
                    detector.detect_for_video.return_value = Point(
                        hand_landmarks=[hand_points()],
                        hand_world_landmarks=[hand_points()],
                        handedness=[[Point(category_name=predicted)]],
                    )
                    bgr = np.zeros((48, 64, 3), dtype=np.uint8)
                    bgr[:, 0] = 255

                    def read():
                        worker.stop()
                        return True, bgr.copy()

                    cap.read.side_effect = read
                    with patch("tracking.ensure_model", return_value=Path("unused.task")), patch(
                        "tracking.vision.HandLandmarker.create_from_options", return_value=detector
                    ), patch("tracking.open_camera", return_value=cap), patch("tracking.draw_overlay"):
                        worker.run()
                    self.assertFalse(any(kind == "error" for kind, _ in self._events(worker)))
                    self.assertEqual(worker.frames.get_nowait().hand, physical_hand)
                    image = detector.detect_for_video.call_args.args[0].numpy_view()
                    np.testing.assert_array_equal(image, bgr[:, ::-1] if mirror else bgr)

    def test_worker_tracks_both_palms_across_detector_order_changes(self):
        worker, cap, detector = self._setup()
        worker.set_options(ViewOptions(mirror=False))
        results = []
        for step in range(4):
            entries = []
            for index, label in enumerate(("Left", "Right")):
                x = (.3, .7)[index]
                y = (.4, .6)[(step + index) % 2]
                points = hand_points()
                points[0] = Point(x=x, y=y - .1, z=0)
                points[9] = Point(x=x, y=y + .1, z=0)
                entries.append((points, hand_points(), [Point(category_name=label)]))
            if step % 2:
                entries.reverse()
            image_points, world_points, labels = zip(*entries)
            results.append(Point(hand_landmarks=image_points, hand_world_landmarks=world_points,
                                 handedness=labels))
        detector.detect_for_video.side_effect = results
        frames_read = 0

        def read():
            nonlocal frames_read
            frames_read += 1
            if frames_read == len(results):
                worker.stop()
            return True, np.zeros((48, 64, 3), dtype=np.uint8)

        cap.read.side_effect = read
        with patch("tracking.ensure_model", return_value=Path("unused.task")), patch(
            "tracking.vision.HandLandmarker.create_from_options", return_value=detector
        ), patch("tracking.open_camera", return_value=cap), patch("tracking.draw_overlay") as overlay:
            worker.run()
        self.assertFalse(any(kind == "error" for kind, _ in self._events(worker)))
        frame = worker.frames.get_nowait()
        self.assertEqual(frame.hand, "Left")
        self.assertEqual(frame.hand_count, 2)
        np.testing.assert_allclose(frame.six_seven, ((.3, .6), (.7, .4)))
        self.assertEqual(overlay.call_count, 8)

    def test_inference_error_releases_camera_and_model(self):
        worker, cap, detector = self._setup()
        cap.read.return_value = (True, np.zeros((48, 64, 3), dtype=np.uint8))
        detector.detect_for_video.side_effect = RuntimeError("inference failed")
        with patch("tracking.ensure_model", return_value=Path("unused.task")), patch(
            "tracking.vision.HandLandmarker.create_from_options", return_value=detector
        ), patch("tracking.open_camera", return_value=cap):
            worker.start()
            worker.join(timeout=5)
        self.assertFalse(worker.is_alive())
        cap.release.assert_called_once()
        detector.close.assert_called_once()
        self.assertIn(("error", "inference failed"), self._events(worker))

    def test_single_hand_option_limits_the_detector(self):
        worker, _, detector = self._setup()
        worker.set_options(ViewOptions(single_hand=True))
        with patch("tracking.ensure_model", return_value=Path("unused.task")), patch(
            "tracking.vision.HandLandmarker.create_from_options", return_value=detector
        ) as create, patch("tracking.open_camera", side_effect=RuntimeError("camera unavailable")):
            worker.run()
        self.assertEqual(create.call_args.args[0].num_hands, 1)

    def test_camera_open_failure_closes_model(self):
        worker, _, detector = self._setup()
        with patch("tracking.ensure_model", return_value=Path("unused.task")), patch(
            "tracking.vision.HandLandmarker.create_from_options", return_value=detector
        ), patch("tracking.open_camera", side_effect=RuntimeError("camera unavailable")):
            worker.start()
            worker.join(timeout=5)
        self.assertFalse(worker.is_alive())
        detector.close.assert_called_once()
        self.assertIn(("error", "camera unavailable"), self._events(worker))


if __name__ == "__main__":
    unittest.main()
