"""Translate hand motion into changes to the selected scene object."""

from math import cos, exp, isfinite, sin

from scene_overlay import pick_shape


LEGACY_AXES = {"Thumb out": 0, "Point up": 1, "Open palm": 2}
RELEASE_GRACE = 0.25
TRACKING_GRACE = 0.50
PINCH_DEPTH_GAIN = 2.5
PALM_DEPTH_GAIN = 4.0


class ShapeInteraction:
    def __init__(self):
        self.mode = "Updated"
        self.selected = None
        self.reset_motion()

    def reset_motion(self):
        self.pinching = False
        self.anchor = None
        self.last_sample = None
        self.last_pinch = None
        self.scale = None

    def update(self, frame, objects, size, now, over_toolbar=False):
        if frame.cursor is None:
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

        if frame.pinching and not self.pinching:
            if self.mode == "Legacy" and self.selected is not None:
                self.selected = None
            else:
                self.selected = None if over_toolbar else pick_shape(objects, size, frame.cursor)
        if frame.pinching:
            self.last_pinch = now
        self.pinching = self.last_pinch is not None and now - self.last_pinch < RELEASE_GRACE

        updated = self.mode == "Updated"
        axis = LEGACY_AXES.get(frame.gesture)
        if self.selected is None or (not self.pinching and (updated or axis is None)):
            self.anchor = None
            return
        if self.pinching and not frame.pinching:
            return

        aim = frame.cursor if self.pinching else frame.palm or frame.cursor
        activity = "grab" if self.pinching else axis
        scale = frame.palm_scale
        transform = self.selected.transform
        if self.anchor is None or self.anchor[0] != activity:
            self.scale = scale
            self.anchor = (activity, aim, transform.position.copy(), scale,
                           frame.palm_roll, transform.rotation[2])
            return

        _, origin, position, initial_scale, initial_roll, rotation = self.anchor
        dx, dy = aim[0] - origin[0], aim[1] - origin[1]
        target = position.copy()
        if self.pinching:
            if frame.palm_roll is None:
                delta = transform.rotation[2] - rotation
            elif initial_roll is None:
                delta = 0.0
                self.anchor = (activity, origin, position, initial_scale, frame.palm_roll, rotation)
            else:
                delta = frame.palm_roll - initial_roll
            depth = position[2]
            if updated and initial_scale and scale and scale > 0:
                self.scale = 0.75 * self.scale + 0.25 * scale
                depth *= (initial_scale / self.scale) ** PINCH_DEPTH_GAIN
            focal = min(size)
            pivot_x = (origin[0] - 0.5) * size[0] / focal
            pivot_y = (0.5 - origin[1]) * size[1] / focal
            offset_x = position[0] / position[2] - pivot_x
            offset_y = position[1] / position[2] - pivot_y
            if updated:
                pivot_x += dx * size[0] / focal
                pivot_y -= dy * size[1] / focal
            target[0] = depth * pivot_x + position[2] * (cos(delta) * offset_x - sin(delta) * offset_y)
            target[1] = depth * pivot_y + position[2] * (sin(delta) * offset_x + cos(delta) * offset_y)
            target[2] = depth
            transform.rotation[2] = rotation + delta
        elif axis == 0:
            target[0] += dx * position[2] * size[0] / min(size)
        elif axis == 1:
            target[1] -= dy * position[2] * size[1] / min(size)
        else:
            target[2] = position[2] * exp(-PALM_DEPTH_GAIN * dy)
        if target[2] > 0 and all(isfinite(value) for value in target):
            transform.position[:] = target
