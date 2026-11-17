"""Hardware-independent checks for bounded frames, and resource cleanup."""

from pathlib import Path
from queue import Empty
import sys
from types import SimpleNamespace as Point
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from test_gestures import hand_points
from tracking import CameraWorker, ViewOptions, open_camera


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
