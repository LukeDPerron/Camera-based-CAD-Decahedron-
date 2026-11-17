"""Optional real Tk checks: set CAMERA_UI_TEST_GUI=1 with a display available."""

import os
from pathlib import Path
from queue import Queue, SimpleQueue
import sys
from threading import Event
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@unittest.skipUnless(os.environ.get("CAMERA_UI_TEST_GUI") == "1", "Optional display test")
class UiTests(unittest.TestCase):
    def setUp(self):
        import customtkinter as ctk
        from app import CameraCanvasApp
        ctk.set_appearance_mode("dark")
        self.real_start_camera = CameraCanvasApp.start_camera
        self.no_camera = patch.object(CameraCanvasApp, "start_camera")
        self.no_camera.start()
        self.app = CameraCanvasApp()
        self.app.after_cancel(self.app.startup_scan_job)
        self.app.update()
        from cameras import CameraDevice
        self.devices = [CameraDevice(0, "Built-in", 1200, "builtin"),
                        CameraDevice(7, "USB webcam", 1200, "usb")]
        self._scan_result(self.devices)

    def _scan_result(self, devices, error="", previous=None):
        self.app._scan_selected = previous
        self.app._scan_auto_start = False
        self.app.camera_results.put((devices, error))
        self.app._poll_camera_scan()

    def tearDown(self):
        # Tests create several roots in one process; discard delayed Tk/CTk
        # callbacks before destroying each root to avoid stale Tcl commands.
        for job in self.app.tk.call("after", "info"):
            self.app.after_cancel(job)
        self.app.worker = None
        self.app.close()
        self.no_camera.stop()

    def test_frame_fits_canvas_after_resize(self):
        import numpy as np
        from tracking import Frame
        self.app._display_frame(Frame(np.zeros((360, 640, 3), dtype=np.uint8), "Right", "Point", (.2, .4), 30))
        for geometry in ("1180x780", "900x660"):
            self.app.geometry(geometry)
            self.app.update()
            photo = self.app.photo
            canvas = self.app.canvas
            self.assertLessEqual(photo.width(), canvas.winfo_width())
            self.assertLessEqual(photo.height(), canvas.winfo_height())
            self.assertAlmostEqual(photo.width() / photo.height(), 640 / 360, delta=.01)
            self.assertEqual(canvas.itemcget(self.app.message_item, "state"), "hidden")
        self.assertEqual(self.app.hand_value.cget("text"), "Right")
        self.assertEqual(self.app.position_value.cget("text"), "0.20 / 0.40")

    def test_fingertip_selects_shape_after_dwell_and_resets_on_stop(self):
        import numpy as np
        from tracking import Frame
        self.app._display_frame(Frame(np.zeros((360, 640, 3), dtype=np.uint8),
                                      "Right", "Point", None, 30))
        buttons, _ = self.app._shape_layout()
        _, (x1, y1, x2, y2) = buttons[0]
        width, height = self.app.canvas.winfo_width(), self.app.canvas.winfo_height()
        scale = min(width / 640, height / 360)
        fw, fh = int(640 * scale), int(360 * scale)
        tip = (((x1+x2)/2 - (width-fw)/2) / fw,
               ((y1+y2)/2 - (height-fh)/2) / fh)
        frame = Frame(np.zeros((360, 640, 3), dtype=np.uint8), "Right", "Point", tip, 30)
        for now in (0, .2, .4, .6, .8, 1, 1.2):
            with patch("app.time.monotonic", return_value=now):
                self.app._display_frame(frame)
        self.assertEqual(self.app.shape_count, 1)
        self.assertIn("Cube selected", self.app.shape_message)
        self.assertTrue(self.app.canvas.find_withtag("shape_toolbar"))
        self.app._empty_canvas("Camera stopped")
        self.assertIsNone(self.app.dwell.target)
        self.assertFalse(self.app.canvas.find_withtag("shape_toolbar"))

    def test_stopped_worker_preserves_error_and_enables_retry(self):
        worker = MagicMock()
        worker.events = SimpleQueue()
        worker.events.put(("error", "Allow camera access in system settings."))
        worker.events.put(("stopped", "Camera stopped"))
        worker.stop_event = Event()
        worker.is_alive.return_value = False
        self.app.worker = worker
        self.app._poll()
        self.assertTrue(self.app.error)
        self.assertIsNone(self.app.worker)
        self.assertIn("Allow camera access", self.app.canvas.itemcget(self.app.message_item, "text"))
        self.assertEqual(self.app.camera_button.cget("state"), "normal")
        self.assertEqual(self.app.camera_dropdown.cget("state"), "normal")

    def test_stop_clears_frame_and_restores_start_controls(self):
        worker = MagicMock()
        worker.events = SimpleQueue()
        worker.frames = Queue()
        worker.stop_event = Event()
        worker.stop.side_effect = worker.stop_event.set
        worker.is_alive.return_value = True
        self.app.worker = worker
        self.app._toggle_camera()
        self.assertTrue(worker.stop_event.is_set())
        self.assertEqual(self.app.camera_button.cget("state"), "disabled")
        worker.is_alive.return_value = False
        self.app._poll()
        self.assertEqual(self.app.camera_button.cget("text"), "Start camera")
        self.assertIsNone(self.app.last_image)

    def test_dropdown_contains_named_devices_and_preserves_selection_after_renumber(self):
        from cameras import CameraDevice
        self.assertEqual(self.app.camera_dropdown.cget("values"), [d.label for d in self.devices])
        changed = CameraDevice(2, "USB webcam", 1200, "usb")
        self._scan_result([changed, self.devices[0]], previous=self.devices[1])
        self.assertEqual(self.app.camera_name.get(), changed.label)
        self.assertEqual(self.app.camera_choices[changed.label].index, 2)

    def test_empty_scan_disables_start_but_allows_refresh(self):
        self._scan_result([])
        self.assertEqual(self.app.camera_dropdown.cget("state"), "disabled")
        self.assertEqual(self.app.camera_button.cget("state"), "disabled")
        self.assertEqual(self.app.refresh_button.cget("state"), "normal")
        self.assertIn("No cameras found", self.app.canvas.itemcget(self.app.message_item, "text"))
        self._scan_result(self.devices)
        self.assertEqual(self.app.camera_button.cget("state"), "normal")

    def test_discovery_failure_displays_help_and_allows_retry(self):
        self._scan_result([], "Install the updated dependencies")
        self.assertIn("Install", self.app.canvas.itemcget(self.app.message_item, "text"))
        self.assertEqual(self.app.refresh_button.cget("state"), "normal")

    def test_switch_waits_for_old_worker_before_opening_selected_device(self):
        old_worker = MagicMock()
        old_worker.events = SimpleQueue()
        old_worker.stop_event = Event()
        old_worker.stop.side_effect = old_worker.stop_event.set
        old_worker.is_alive.return_value = True
        self.app.worker = old_worker
        self.app.camera_name.set(self.devices[1].label)
        self.app._select_camera(self.devices[1].label)
        self.assertTrue(old_worker.stop_event.is_set())
        self.assertEqual(self.app.camera_dropdown.cget("state"), "disabled")
        with patch("app.CameraWorker") as factory:
            self.app._poll()
            factory.assert_not_called()
            old_worker.is_alive.return_value = False
            # Exercise the real start method when the old worker has exited.
            self.app.start_camera.side_effect = lambda: self.real_start_camera(self.app)
            self.app._poll()
            self.assertEqual(factory.call_args.args[0], self.devices[1])
            factory.return_value.start.assert_called_once()
            self.assertEqual(self.app.camera_dropdown.cget("state"), "normal")


if __name__ == "__main__":
    unittest.main()
