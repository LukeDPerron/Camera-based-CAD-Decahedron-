"""Composite the gesture sprites and fading explosions onto the camera."""

from pathlib import Path
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont, ImageOps


ASSETS = Path(__file__).resolve().parents[1] / "static"
EXPLOSION_DURATION = 1.6


class GestureEffects:
    def __init__(self):
        self.reset()

    def reset(self):
        self.cat = self.six_seven = None
        self.explosions = []

    def update(self, frame):
        self.cat = frame.cat
        self.six_seven = frame.six_seven

    def explode(self, point, now):
        self.explosions.append((point, now))

    @staticmethod
    @lru_cache(maxsize=24)
    def _sprite(name, box):
        try:
            with Image.open(ASSETS / f"{name}.png") as image:
                return ImageOps.contain(image.convert("RGBA"), (box, box))
        except OSError:
            return None

    @staticmethod
    @lru_cache(maxsize=12)
    def _number_font(size):
        return ImageFont.load_default(size=size)

    def _paste(self, frame, name, point, fraction, opacity=1.0):
        sprite = self._sprite(name, max(1, round(min(frame.size) * fraction)))
        if sprite is None:
            return
        x = round(point[0] * frame.width - sprite.width / 2)
        y = round(point[1] * frame.height - sprite.height / 2)
        mask = sprite.getchannel("A")
        if opacity < 1:
            mask = mask.point([round(i * opacity) for i in range(256)])
        frame.paste(sprite, (x, y), mask)

    def draw(self, frame, now):
        if self.cat is not None:
            self._paste(frame, "cat", self.cat, 0.32)
        if self.six_seven is not None:
            size = max(12, round(min(frame.size) * 0.20))
            draw = ImageDraw.Draw(frame)
            for digit, (x, y), color in zip("67", self.six_seven, ("#7CF3D2", "#FFD189")):
                draw.text((x * frame.width, max(size / 2, y * frame.height - size)),
                          digit, font=self._number_font(size), anchor="mm", fill=color,
                          stroke_width=max(2, size // 16), stroke_fill="#14232D")
        self.explosions[:] = [(point, start) for point, start in self.explosions
                             if now - start < EXPLOSION_DURATION]
        for point, start in self.explosions:
            opacity = 1 - max(0, now - start) / EXPLOSION_DURATION
            self._paste(frame, "explosion", point, 0.38, opacity)
