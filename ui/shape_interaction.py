"""Translate hand motion into changes to the selected scene object."""

from math import cos, exp, isfinite, sin

from scene_overlay import pick_shape


LEGACY_AXES = {"Thumb out": 0, "Point up": 1, "Open palm": 2}
RELEASE_GRACE = 0.25
TRACKING_GRACE = 0.50
PINCH_DEPTH_GAIN = 2.5
PALM_DEPTH_GAIN = 4.0
DELETE_WINDOW = 1.0


class ShapeInteraction:
    def __init__(self):
        self.mode = "Updated"
        self.selected = []
        self.reset_motion()

    def reset_motion(self):
        self.pinching = False
        self.anchor = None
        self.last_sample = None
        self.last_pinch = None
        self.scale = None
        self.last_open_palm = None

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

        if not frame.pinching and self.selected:
            if frame.gesture == "Open palm":
                self.last_open_palm = now
            elif (frame.gesture == "Fist" and self.last_open_palm is not None
                  and now - self.last_open_palm <= DELETE_WINDOW):
                destroyed = tuple(self.selected)
                objects[:] = [obj for obj in objects if obj not in destroyed]
                self.selected.clear()
                self.reset_motion()
                return destroyed

        if frame.pinching and not self.pinching:
            self.last_open_palm = None
            hit = None if over_toolbar else pick_shape(objects, size, frame.cursor)
            if frame.pinky_up:
                if hit in self.selected:
                    self.selected.remove(hit)
                elif hit is not None:
                    self.selected.append(hit)
            elif self.mode == "Legacy" and self.selected:
                self.selected.clear()
            elif hit not in self.selected:
                self.selected[:] = [] if hit is None else [hit]
            self.anchor = None
        if frame.pinching:
            self.last_pinch = now
        self.pinching = self.last_pinch is not None and now - self.last_pinch < RELEASE_GRACE

        updated = self.mode == "Updated"
        axis = LEGACY_AXES.get(frame.gesture)
        if not self.selected or (not self.pinching and (updated or axis is None)):
            self.anchor = None
            return
        if self.pinching and not frame.pinching:
            return

        aim = frame.cursor if self.pinching else frame.palm or frame.cursor
        activity = "grab" if self.pinching else axis
        scale = frame.palm_scale
        if self.anchor is None or self.anchor[0] != activity:
            self.scale = scale
            snapshots = [(obj.transform, obj.transform.position.copy(), obj.transform.rotation[2])
                         for obj in self.selected]
            self.anchor = (activity, aim, snapshots, scale, frame.palm_roll)
            return

        _, origin, snapshots, initial_scale, initial_roll = self.anchor
        dx, dy = aim[0] - origin[0], aim[1] - origin[1]
        focal = min(size)
        width, height = size
        delta = 0.0
        if self.pinching or axis == 2:
            transform, _, rotation = snapshots[0]
            if frame.palm_roll is None:
                delta = transform.rotation[2] - rotation
            elif initial_roll is None:
                self.anchor = (activity, origin, snapshots, initial_scale, frame.palm_roll)
            else:
                delta = frame.palm_roll - initial_roll
        depth_factor = 1.0
        if self.pinching and updated and initial_scale and scale and scale > 0:
            self.scale = 0.75 * self.scale + 0.25 * scale
            depth_factor = (initial_scale / self.scale) ** PINCH_DEPTH_GAIN
        pivot_x = (origin[0] - 0.5) * width / focal
        pivot_y = (0.5 - origin[1]) * height / focal
        center_x = center_y = 0.0
        if not self.pinching and axis == 2:
            depth_factor = exp(-PALM_DEPTH_GAIN * dy)
            center_x = sum(position[0] for _, position, _ in snapshots) / len(snapshots)
            center_y = sum(position[1] for _, position, _ in snapshots) / len(snapshots)
        c, s = cos(delta), sin(delta)
        for transform, position, rotation in snapshots:
            x, y, z = position
            target = position.copy()
            if self.pinching:
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
                target[0] = center_x + c * (x - center_x) - s * (y - center_y)
                target[1] = center_y + s * (x - center_x) + c * (y - center_y)
                target[2] *= depth_factor
            if target[2] > 0 and all(isfinite(value) for value in target):
                transform.position[:] = target
                transform.rotation[2] = rotation + delta
