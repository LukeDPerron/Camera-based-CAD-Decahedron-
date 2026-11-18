"""Translate hand motion into changes to the selected scene object."""

from math import cos, exp, isfinite, sin

import numpy as np

from face_snap import snap_faces
from scene_overlay import pick_shape, rotation_angles, rotation_matrix


LEGACY_AXES = {"Thumb out": 0, "Point up": 1, "Open palm": 2}
RELEASE_GRACE = 0.25
TRACKING_GRACE = 0.50
PINCH_DEPTH_GAIN = 2.5
PALM_DEPTH_GAIN = 4.0
WRIST_TWIST_GAIN = 1.15
DELETE_WINDOW = 1.0


class ShapeInteraction:
    def __init__(self):
        self.mode = "Updated"
        self.selected = []
        self.grabbed = False
        self.waiting_for_pinky_down = False
        self.snap_to_faces = False
        self.seated_faces = set()
        self.reset_motion()

    def reset_motion(self):
        self.pinching = False
        self.wait_for_open = self.grabbed
        self.anchor = None
        self.last_sample = None
        self.last_pinch = None
        self.scale = None
        self.last_open_palm = None
        self.group_rotation = (0.0, 0.0, 0.0)

    def update(self, frame, objects, size, now, over_toolbar=False):
        if frame.cursor is None:
            self.last_open_palm = None
            if self.last_sample is None or now - self.last_sample[1] > TRACKING_GRACE:
                self.reset_motion()
            else:
                self.anchor = None
            return
        if self.last_sample is not None:
            previous_hand, previous_time = self.last_sample
            if frame.hand != previous_hand or now - previous_time > TRACKING_GRACE:
                self.reset_motion()
        self.last_sample = (frame.hand, now)
        updated = self.mode == "Updated"

        if not frame.pinching and self.selected:
            if frame.gesture == "Open palm":
                self.last_open_palm = now
            elif (frame.gesture == "Fist" and self.last_open_palm is not None
                  and now - self.last_open_palm <= DELETE_WINDOW):
                destroyed = tuple(self.selected)
                objects[:] = [obj for obj in objects if obj not in destroyed]
                self.selected.clear()
                self.grabbed = False
                self.waiting_for_pinky_down = False
                self.reset_motion()
                return destroyed

        if not frame.pinching:
            self.wait_for_open = False
        if frame.pinching and not self.pinching and not self.wait_for_open:
            self.last_open_palm = None
            hit = None if over_toolbar else pick_shape(objects, size, frame.cursor)
            if frame.pinky_up:
                if updated:
                    self.waiting_for_pinky_down = True
                if hit in self.selected:
                    self.selected.remove(hit)
                elif hit is not None:
                    self.selected.append(hit)
                if updated and hit is not None:
                    self.grabbed = bool(self.selected)
            elif updated and self.grabbed:
                self.grabbed = False
            elif not updated and self.selected:
                self.selected.clear()
            else:
                if hit not in self.selected:
                    self.selected[:] = [] if hit is None else [hit]
                self.grabbed = updated and bool(self.selected)
            self.anchor = None
        if frame.pinching:
            self.last_pinch = now
        self.pinching = self.last_pinch is not None and now - self.last_pinch < RELEASE_GRACE

        if updated and self.waiting_for_pinky_down:
            self.anchor = None
            if frame.pinky_up:
                return
            self.waiting_for_pinky_down = False

        following = self.grabbed if updated else self.pinching
        axis = LEGACY_AXES.get(frame.gesture)
        if not self.selected or (not following and (updated or axis is None)):
            self.anchor = None
            return
        if not updated and self.pinching and not frame.pinching:
            return

        if following:
            aim = (frame.index_tip or frame.cursor) if updated else frame.cursor
        else:
            aim = frame.palm or frame.cursor
        activity = "grab" if following else axis
        scale = frame.palm_scale
        if self.anchor is None or self.anchor[0] != activity:
            self.scale = scale
            self.group_rotation = (0.0, 0.0, 0.0)
            snapshots = [(obj.transform, obj.transform.position.copy(), obj.transform.rotation.copy())
                         for obj in self.selected]
            pivot = frame.cursor if following and frame.pinching else aim
            self.anchor = (activity, aim, snapshots, scale, frame.palm_roll, pivot,
                           frame.palm_yaw, frame.palm_pitch)
            return

        _, origin, snapshots, initial_scale, initial_roll, pivot, initial_yaw, initial_pitch = self.anchor
        dx, dy = aim[0] - origin[0], aim[1] - origin[1]
        focal = min(size)
        width, height = size
        delta = 0.0
        if following or axis == 2:
            if frame.palm_roll is None:
                delta = self.group_rotation[2]
            elif initial_roll is None:
                initial_roll = frame.palm_roll
            else:
                delta = frame.palm_roll - initial_roll
        yaw_delta = None
        pitch_delta = None
        if following and updated and frame.palm_yaw is not None:
            if initial_yaw is None:
                initial_yaw = frame.palm_yaw
            yaw_delta = WRIST_TWIST_GAIN * (frame.palm_yaw - initial_yaw)
        if following and updated and frame.palm_pitch is not None:
            if initial_pitch is None:
                initial_pitch = frame.palm_pitch
            pitch_delta = frame.palm_pitch - initial_pitch
        self.anchor = (activity, origin, snapshots, initial_scale, initial_roll, pivot,
                       initial_yaw, initial_pitch)
        depth_factor = 1.0
        if following and updated and initial_scale and scale and scale > 0:
            self.scale = 0.75 * self.scale + 0.25 * scale
            depth_factor = (initial_scale / self.scale) ** PINCH_DEPTH_GAIN
        pivot_x = (pivot[0] - 0.5) * width / focal
        pivot_y = (0.5 - pivot[1]) * height / focal
        if not following and axis == 2:
            depth_factor = exp(-PALM_DEPTH_GAIN * dy)
        if len(snapshots) > 1:
            previous_pitch, previous_yaw, previous_roll = self.group_rotation
            angles = (previous_pitch if pitch_delta is None else pitch_delta,
                      previous_yaw if yaw_delta is None else yaw_delta,
                      previous_roll if (following or axis == 2) and frame.palm_roll is None else delta)
            center = np.mean([position for _, position, _ in snapshots], axis=0)
            target_center = center.copy()
            depth = center[2] * depth_factor
            if following and updated:
                target_center[0] += depth * dx * width / focal + (depth - center[2]) * pivot_x
                target_center[1] += (depth - center[2]) * pivot_y - depth * dy * height / focal
            elif not following and axis == 0:
                target_center[0] += dx * depth * width / focal
            elif not following and axis == 1:
                target_center[1] -= dy * depth * height / focal
            target_center[2] = depth
            matrix = rotation_matrix(angles)
            targets = [target_center + (position - center) @ matrix
                       for _, position, _ in snapshots]
            if all(target[2] > 0 and np.isfinite(target).all() for target in targets):
                for (transform, _, rotation), target in zip(snapshots, targets):
                    transform.position[:] = target
                    transform.rotation[:] = rotation_angles(rotation_matrix(rotation) @ matrix)
                self.group_rotation = angles
                self._snap_selection(objects)
            return
        c, s = cos(delta), sin(delta)
        for transform, position, rotation in snapshots:
            x, y, z = position
            target = position.copy()
            if following:
                offset_x, offset_y = x - z * pivot_x, y - z * pivot_y
                depth = z * depth_factor
                target[0] = depth * (pivot_x + (dx * width / focal if updated else 0))
                target[0] += c * offset_x - s * offset_y
                target[1] = depth * (pivot_y - (dy * height / focal if updated else 0))
                target[1] += s * offset_x + c * offset_y
                target[2] = depth
            elif axis == 0:
                target[0] += dx * z * width / focal
            elif axis == 1:
                target[1] -= dy * z * height / focal
            else:
                target[2] *= depth_factor
            if target[2] > 0 and all(isfinite(value) for value in target):
                transform.position[:] = target
                transform.rotation[2] = rotation[2] + delta
                previous_pitch, previous_yaw, _ = self.group_rotation
                pitch = previous_pitch if pitch_delta is None else pitch_delta
                yaw = previous_yaw if yaw_delta is None else yaw_delta
                transform.rotation[0] = rotation[0] + pitch
                transform.rotation[1] = rotation[1] + yaw
                self.group_rotation = (pitch, yaw, delta)
                self._snap_selection(objects)

    def _snap_selection(self, objects):
        if self.snap_to_faces and snap_faces(self.selected, objects, self.seated_faces):
            self.selected.clear()
            self.grabbed = False
            self.waiting_for_pinky_down = False
            self.anchor = None
