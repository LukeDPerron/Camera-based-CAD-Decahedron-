"""Camera discovery and physical-device selection without camera hardware."""

from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2

from cameras import CameraDevice, discover_cameras, resolve_camera
from tracking import open_camera


class DiscoveryTests(unittest.TestCase):
    def test_native_backend_sparse_indices_and_duplicate_names(self):
        for system, backend in (("Darwin", cv2.CAP_AVFOUNDATION), ("Windows", cv2.CAP_DSHOW)):
            with self.subTest(system=system):
                fake = SimpleNamespace(enumerate_cameras=MagicMock(return_value=[
                    SimpleNamespace(index=0, name="USB Camera", path="first"),
                    SimpleNamespace(index=12, name="USB Camera", path="second"),
                ]))
                with patch.dict(sys.modules, {"cv2_enumerate_cameras": fake}), patch(
                    "cameras.platform.system", return_value=system
                ), patch("cameras.cv2.VideoCapture") as capture:
                    devices = discover_cameras()
                fake.enumerate_cameras.assert_called_once_with(backend)
                capture.assert_not_called()
                self.assertEqual([d.index for d in devices], [0, 12])
                self.assertNotEqual(devices[0].label, devices[1].label)

    def test_reconnect_uses_persistent_device_id_not_old_index(self):
        selected = CameraDevice(1, "USB", cv2.CAP_DSHOW, "usb-id")
        changed = CameraDevice(4, "USB", cv2.CAP_DSHOW, "usb-id")
        other = CameraDevice(1, "Other", cv2.CAP_DSHOW, "other-id")
        with patch("cameras.discover_cameras", return_value=[other, changed]):
            self.assertEqual(resolve_camera(selected), changed)
        with patch("cameras.discover_cameras", return_value=[other]):
            with self.assertRaisesRegex(RuntimeError, "no longer connected"):
                resolve_camera(selected)

    def test_selected_camera_does_not_fall_back_to_a_different_backend(self):
        cap = MagicMock()
        cap.isOpened.return_value = False
        with patch("tracking.cv2.VideoCapture", return_value=cap) as capture:
            with self.assertRaises(RuntimeError):
                open_camera(4, cv2.CAP_DSHOW)
        capture.assert_called_once_with(4, cv2.CAP_DSHOW)
        cap.release.assert_called_once()


if __name__ == "__main__":
    unittest.main()
