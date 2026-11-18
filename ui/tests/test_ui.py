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
        def photo_pixel(x, y):
            return self.app.tk.call(str(self.app.photo), "get", x, y)

        center = (self.app.photo.width() // 2, self.app.photo.height() // 2)
        self.assertEqual(photo_pixel(*center), (0, 0, 0))
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
        self.assertEqual([obj.shape_type.name for obj in self.app.scene.objects], ["CUBE"])
        self.assertGreater(max(photo_pixel(*center)), 0)
        self.assertIn("Cube selected", self.app.shape_message)
        self.assertTrue(self.app.canvas.find_withtag("shape_toolbar"))
        for _, (x1, y1, x2, y2) in buttons[1:]:
            self.app.canvas.event_generate("<Button-1>", x=int((x1 + x2) / 2),
                                           y=int((y1 + y2) / 2))
        self.assertEqual([obj.shape_type.name for obj in self.app.scene.objects],
                         ["CUBE", "SPHERE", "PYRAMID"])
        self.assertEqual(len({tuple(obj.transform.position) for obj in self.app.scene.objects}), 3)
        fitted_height = self.app.photo.height()
        for x_offset in (-1.1, 1.1):
            self.assertGreater(max(photo_pixel(int(center[0] + fitted_height * x_offset / 4),
                                               center[1])), 0)
        self.assertEqual(self.app.last_image.getpixel((320, 180)), (0, 0, 0))
        self.app._empty_canvas("Camera stopped")
        self.assertIsNone(self.app.dwell.target)
        self.assertFalse(self.app.canvas.find_withtag("shape_toolbar"))

    def test_pinch_selects_and_modes_move_the_object(self):
        import numpy as np
        from tracking import Frame

        self.app._select_shape("Cube")
        obj = self.app.scene.objects[0]
        rgb = np.zeros((360, 640, 3), dtype=np.uint8)
        now = 0

        def send(cursor, pose="Tracking", pinching=False, scale=.1):
            nonlocal now
            now += .05
            with patch("app.time.monotonic", return_value=now):
                self.app._display_frame(Frame(rgb, "Right", pose, cursor, 30,
                                              pinching, cursor, scale))

        self.assertEqual(self.app.mode_switch.get(), "Updated")
        send((.5, .5), pinching=True)
        self.assertEqual(self.app.interaction.selected, [obj])
        send((.6, .4), scale=.15)
        x, y, z = obj.transform.position
        self.assertGreater(x, 0)
        self.assertGreater(y, 0)
        self.assertLess(z, 4)
        now += .25
        send((.8, .3))
        self.assertGreater(obj.transform.position[0], x)
        dropped_position = obj.transform.position.copy()
        send((.8, .3), pinching=True)
        self.assertFalse(self.app.interaction.grabbed)
        send((.6, .6))
        np.testing.assert_allclose(obj.transform.position, dropped_position)

        self.app.mode_switch.set("Legacy")
        self.app._set_gesture_mode("Legacy")
        obj.transform.position[:] = (0, 0, 4)
        send((.5, .5), pinching=True)
        self.assertFalse(self.app.interaction.selected)
        now += .25
        send((.5, .5))
        send((.5, .5), pinching=True)
        self.assertEqual(self.app.interaction.selected, [obj])
        now += .25
        send((.5, .5), "Thumb out")
        send((.6, .4), "Thumb out")
        x = obj.transform.position[0]
        self.assertGreater(x, 0)
        np.testing.assert_allclose(obj.transform.position[1:], (0, 4))
        send((.6, .5), "Point up")
        send((.7, .4), "Point up")
        y = obj.transform.position[1]
        self.assertGreater(y, 0)
        send((.6, .5), "Palm")
        send((.7, .4), "Palm")
        expected = (x, y, 4 * np.exp(.4))
        np.testing.assert_allclose(obj.transform.position, expected)
        send(None, "—")
        send((.9, .9), "Palm")
        np.testing.assert_allclose(obj.transform.position, expected)
        send((.9, .9), pinching=True)
        self.assertFalse(self.app.interaction.selected)

    def test_updated_grab_survives_dropouts_and_passes_old_depth_limits(self):
        import numpy as np
        from tracking import Frame

        self.app._select_shape("Cube")
        obj = self.app.scene.objects[0]
        rgb = np.zeros((360, 640, 3), dtype=np.uint8)
        now = 0

        def send(cursor, pinching, scale=.1):
            nonlocal now
            now += .1
            with patch("app.time.monotonic", return_value=now):
                self.app._display_frame(Frame(rgb, "Right", "Tracking", cursor, 30,
                                              pinching, cursor, scale))

        send((.5, .5), True)
        send((.6, .5), False)
        send((.65, .5), True)
        self.assertEqual(self.app.interaction.selected, [obj])
        self.assertGreater(obj.transform.position[0], 0)
        send(None, False)
        send(None, False)
        send(None, False)
        now += .5
        send((.65, .5), True)
        self.assertTrue(self.app.interaction.grabbed)
        for _ in range(12):
            send((.65, .5), False, scale=.01)
        self.assertGreater(obj.transform.position[2], 12)
        for _ in range(12):
            send((.65, .5), False, scale=.5)
        self.assertLess(obj.transform.position[2], 1.4)
        self.assertGreater(obj.transform.position[2], 0)

    def test_updated_roll_rotates_around_an_off_center_grab_after_releasing_pinch(self):
        from math import pi
        import numpy as np
        from tracking import Frame

        self.app._select_shape("Cube")
        obj = self.app.scene.objects[0]
        rgb = np.zeros((360, 640, 3), dtype=np.uint8)
        tip = (.52, .5)
        index_tip = (.53, .5)
        for now, roll, pinching in ((0, 0, True), (.1, pi / 2, False)):
            with patch("app.time.monotonic", return_value=now):
                self.app._display_frame(Frame(rgb, "Right", "Tracking",
                                              tip if pinching else index_tip, 30,
                                              pinching, tip, .1, roll, index_tip=index_tip))
        self.assertEqual(self.app.interaction.selected, [obj])
        pivot = 4 * (.52 - .5) * 640 / 360
        np.testing.assert_allclose(obj.transform.position, (pivot, -pivot, 4))
        self.assertAlmostEqual(obj.transform.rotation[2], pi / 2)

    def test_updated_wrist_twist_renders_rotation_with_a_stationary_cursor(self):
        from math import pi
        import numpy as np
        from tracking import Frame

        self.app._select_shape("Cube")
        obj = self.app.scene.objects[0]
        rgb = np.zeros((360, 640, 3), dtype=np.uint8)
        tip = (.5, .5)

        def show(now, yaw, pitch=0, pinching=False):
            with patch("app.time.monotonic", return_value=now):
                self.app._display_frame(Frame(rgb, "Right", "Point up", tip, 30,
                                              pinching, tip, .1, 0, palm_yaw=yaw,
                                              palm_pitch=pitch))
            return self.app.tk.call(str(self.app.photo), "data", "-format", "png")

        before = show(0, 0, pinching=True)
        turned = show(.1, pi / 3)
        self.assertNotEqual(before, turned)
        self.assertAlmostEqual(obj.transform.rotation[1], 1.15 * pi / 3)
        forward = show(.2, pi / 3, -pi / 4)
        self.assertNotEqual(forward, turned)
        self.assertAlmostEqual(obj.transform.rotation[0], -pi / 4)
        backward = show(.3, pi / 3, pi / 4)
        self.assertNotEqual(forward, backward)
        self.assertAlmostEqual(obj.transform.rotation[0], pi / 4)
        np.testing.assert_allclose(obj.transform.position, (0, 0, 4))

    def test_updated_group_yaw_and_pitch_orbit_a_shared_center(self):
        from math import pi
        import numpy as np
        from scene_overlay import rotation_matrix
        from tracking import Frame

        self.app._select_shape("Cube")
        self.app._select_shape("Sphere")
        cube, sphere = self.app.scene.objects
        sphere.transform.rotation[1] = .3
        initial_sphere = rotation_matrix(sphere.transform.rotation)
        rgb = np.zeros((360, 640, 3), dtype=np.uint8)

        def show(now, tip, pinch=False, pinky=False, yaw=0, pitch=0):
            with patch("app.time.monotonic", return_value=now):
                self.app._display_frame(Frame(rgb, "Right", "Tracking", tip, 30,
                                              pinch, tip, .1, 0, pinky,
                                              palm_yaw=yaw, palm_pitch=pitch))

        show(0, (.5, .5), pinch=True)
        show(.3, (.5, .5))
        tip = (.345, .5)
        show(.4, tip, pinch=True, pinky=True)
        self.assertEqual(self.app.interaction.selected, [cube, sphere])
        yaw = (pi / 2) / 1.15
        moved_tip = (.4, .4)
        show(.5, moved_tip, pinch=True, pinky=True, yaw=yaw)
        show(.6, moved_tip, pinky=True, yaw=yaw)
        np.testing.assert_allclose(cube.transform.position, (0, 0, 4))
        np.testing.assert_allclose(sphere.transform.position, (-1.1, 0, 4))
        np.testing.assert_allclose(rotation_matrix(sphere.transform.rotation), initial_sphere)
        show(.7, moved_tip)
        np.testing.assert_allclose(cube.transform.position, (0, 0, 4))
        show(.8, moved_tip, yaw=yaw)
        np.testing.assert_allclose(cube.transform.position, (-.55, 0, 3.45))
        np.testing.assert_allclose(sphere.transform.position, (-.55, 0, 4.55))
        show(.9, moved_tip, yaw=yaw, pitch=pi / 2)
        np.testing.assert_allclose(cube.transform.position, (-.55, .55, 4))
        np.testing.assert_allclose(sphere.transform.position, (-.55, -.55, 4))
        np.testing.assert_allclose(rotation_matrix(sphere.transform.rotation),
                                   initial_sphere @ rotation_matrix((pi / 2, pi / 2, 0)),
                                   atol=1e-8)

    def test_pinky_pinch_group_moves_rotates_and_deletes_together(self):
        from math import pi
        import numpy as np
        from gestures import classify_pose
        from test_gestures import hand_points
        from tracking import Frame

        for shape in ("Cube", "Sphere", "Pyramid"):
            self.app._select_shape(shape)
        cube, sphere, pyramid = self.app.scene.objects
        self.app._set_gesture_mode("Legacy")
        rgb = np.zeros((360, 640, 3), dtype=np.uint8)

        def send(now, tip, pose="Tracking", *, pinch=False, pinky=False, roll=0):
            with patch("app.time.monotonic", return_value=now):
                self.app._display_frame(Frame(rgb, "Right", pose, tip, 30, pinch,
                                              tip, .1, roll, pinky))

        send(0, (.5, .5), pinch=True)
        send(.3, (.35, .5))
        send(.4, (.35, .5), pinch=True, pinky=True)
        self.assertEqual(self.app.interaction.selected, [cube, sphere])
        send(.7, (.5, .5), "Thumb out")
        send(.8, (.6, .5), "Thumb out")
        self.assertGreater(cube.transform.position[0], 0)
        self.assertGreater(sphere.transform.position[0], -1.1)
        palm = classify_pose(hand_points()).name
        send(.9, (.6, .5), palm)
        send(1.0, (.6, .5), palm, roll=pi / 2)
        np.testing.assert_allclose([cube.transform.rotation[2], sphere.transform.rotation[2]],
                                   [pi / 2, pi / 2])
        self.assertGreater(cube.transform.position[1], sphere.transform.position[1])
        fist_points = hand_points((False,) * 4)
        fist_points[4] = fist_points[8]
        send(1.1, (.6, .5), classify_pose(fist_points).name)
        self.assertEqual(self.app.scene.objects, [pyramid])
        self.assertFalse(self.app.interaction.selected)
        self.assertEqual(len(self.app.effects.explosions), 2)

    def test_gesture_images_stay_visible_and_explosion_fades(self):
        import numpy as np
        from tracking import Frame

        rgb = np.zeros((360, 640, 3), dtype=np.uint8)
        both = Frame(rgb, "Right", "Cat", (.5, .5), 30, cat=(.5, .5),
                     six_seven=((.3, .5), (.7, .5)), hand_count=2)
        no_effect = Frame(rgb, "Right", "Tracking", (.5, .5), 30)

        def show(now, frame):
            with patch("app.time.monotonic", return_value=now):
                self.app._display_frame(frame)
            return self.app.tk.call(str(self.app.photo), "data", "-format", "png")

        clear = show(0, no_effect)
        first = show(1, both)
        self.assertEqual(show(2, both), first)
        self.assertFalse(self.app.effects.explosions)
        self.assertNotEqual(first, clear)
        self.assertEqual(show(2.1, no_effect), clear)
        self.assertFalse(self.app.effects.explosions)
        self.app.effects.explode((.5, .5), 2.2)
        full = show(2.2, no_effect)
        self.assertNotEqual(full, clear)
        faded = show(3.0, no_effect)
        self.assertNotEqual(full, faded)
        self.assertNotEqual(clear, faded)
        self.assertEqual(show(3.9, no_effect), clear)
        self.assertFalse(self.app.effects.explosions)

    def test_middle_finger_has_to_be_held_to_quit(self):
        import numpy as np
        from tracking import Frame

        rgb = np.zeros((360, 640, 3), dtype=np.uint8)
        gesture = Frame(rgb, "Right", "Middle finger", (.5, .5), 30)
        other = Frame(rgb, "Right", "Tracking", (.5, .5), 30)
        with patch.object(self.app, "close") as close:
            for now, frame in ((0, gesture), (.3, gesture), (.4, other), (.6, gesture),
                               (.8, gesture), (1.0, gesture), (1.2, gesture), (1.4, gesture)):
                with patch("app.time.monotonic", return_value=now):
                    self.app._display_frame(frame)
            close.assert_not_called()
            with patch("app.time.monotonic", return_value=1.5):
                self.app._display_frame(gesture)
            close.assert_called_once()

    def test_face_snap_drops_selection_and_requires_a_fresh_pinch(self):
        import numpy as np
        from face_snap import solid_faces
        from scene_overlay import shape_center
        from tracking import Frame

        self.app._select_shape("Cube")
        self.app._select_shape("Cube")
        fixed, moving = self.app.scene.objects
        face = max(solid_faces(fixed), key=lambda candidate: candidate.normal[0])
        source = min(solid_faces(moving), key=lambda candidate: candidate.normal @ face.normal)
        moving.transform.position += face.center - source.center + .08 * face.normal
        self.app.snap_to_faces.set(True)
        self.app._update_face_snap()
        rgb = np.zeros((360, 640, 3), dtype=np.uint8)

        def show(now, tip, pinching):
            with patch("app.time.monotonic", return_value=now):
                self.app._display_frame(Frame(rgb, "Right", "Tracking", tip, 30,
                                              pinching, tip, .1))

        tip = shape_center(moving, (640, 360))
        show(0, tip, True)
        self.assertEqual(self.app.interaction.selected, [moving])
        show(.1, tip, True)
        self.assertFalse(self.app.interaction.selected)
        self.assertFalse(self.app.interaction.grabbed)
        tip = shape_center(moving, (640, 360))
        show(.2, tip, True)
        self.assertFalse(self.app.interaction.selected)
        show(.5, tip, False)
        show(.6, tip, True)
        show(.7, tip, True)
        self.assertEqual(self.app.interaction.selected, [moving])
        self.assertTrue(self.app.interaction.grabbed)

    def test_face_and_one_hand_options_update_the_live_ui(self):
        self.app.snap_to_faces.set(True)
        self.app._update_face_snap()
        self.assertTrue(self.app.interaction.snap_to_faces)
        self.app.snap_to_faces.set(False)
        self.app._update_face_snap()
        self.assertFalse(self.app.interaction.snap_to_faces)

        worker = MagicMock()
        worker.is_alive.return_value = True
        worker.stop_event = Event()
        self.app.worker = worker
        self.app.single_hand.set(True)
        self.app._update_hand_limit()
        self.assertTrue(self.app.restart_camera)
        self.assertTrue(self.app._view_options().single_hand)
        worker.stop.assert_called_once()

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
