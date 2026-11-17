"""Dwell behavior checks without camera, GUI, or third-party dependencies."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dwell import DwellSelector


class DwellTests(unittest.TestCase):
    def test_one_second_and_no_repeat_until_leaving(self):
        selector = DwellSelector()
        for now in (0, .2, .4, .6, .8):
            self.assertIsNone(selector.update("Cube", now))
        self.assertEqual(selector.update("Cube", 1.0), "Cube")
        for now in (1.2, 1.4, 1.6):
            self.assertIsNone(selector.update("Cube", now))
        selector.update(None, 1.7)
        for now in (2, 2.2, 2.4, 2.6, 2.8):
            self.assertIsNone(selector.update("Cube", now))
        self.assertEqual(selector.update("Cube", 3), "Cube")

    def test_switching_targets_restarts_timer(self):
        selector = DwellSelector()
        for now in (0, .2, .4, .6, .8):
            selector.update("Cube", now)
        self.assertIsNone(selector.update("Sphere", 1.0))
        self.assertEqual(selector.progress, 0)
        for now in (1.2, 1.4, 1.6, 1.8):
            self.assertIsNone(selector.update("Sphere", now))
        self.assertEqual(selector.update("Sphere", 2), "Sphere")

    def test_lost_hand_and_stalled_frames_reset_progress(self):
        for missing_hand in (True, False):
            with self.subTest(missing_hand=missing_hand):
                selector = DwellSelector()
                for now in (0, .2, .4, .6):
                    selector.update("Pyramid", now)
                if missing_hand:
                    selector.update(None, .7)
                self.assertIsNone(selector.update("Pyramid", 2))
                self.assertEqual(selector.progress, 0)

    def test_explicit_reset_clears_activation(self):
        selector = DwellSelector()
        selector.update("Cube", 0)
        selector.update("Cube", .2)
        selector.reset()
        self.assertIsNone(selector.target)
        self.assertEqual(selector.progress, 0)
        self.assertIsNone(selector.update("Cube", .3))


if __name__ == "__main__":
    unittest.main()
