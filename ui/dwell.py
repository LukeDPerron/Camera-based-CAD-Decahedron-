"""Timed fingertip selection, independent of camera and Tk dependencies."""


class DwellSelector:
    def __init__(self, duration=1.0, max_gap=0.35):
        self.duration = duration
        self.max_gap = max_gap
        self.reset()

    def reset(self):
        self.target = None
        self.started = None
        self.last_seen = None
        self.fired = False
        self.progress = 0.0

    def update(self, target, now):
        """Return a selection once per hover; require leaving before reselecting."""
        if target is None:
            self.reset()
            return None
        if (target != self.target or self.last_seen is None
                or now - self.last_seen > self.max_gap):
            self.reset()
            self.target = target
            self.started = now
        self.last_seen = now
        self.progress = min(1.0, max(0.0, (now - self.started) / self.duration))
        if self.progress >= 1.0 and not self.fired:
            self.fired = True
            return target
        return None
