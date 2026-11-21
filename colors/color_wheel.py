"""Hue-ring + saturation/value-square color picker (not wired into the UI yet).

Layout mirrors the reference swatch: an outer ring sweeps hue around a full
circle, and a square inscribed inside the ring picks saturation (x axis) and
value (y axis) for whichever hue was last selected on the ring. A pinch
landing on either shape resolves to a hex color; ``ColorWheelPicker`` wraps
that into an edge-triggered update() a gesture loop can call every frame,
the same pattern shape_interaction.ShapeInteraction uses for pinch starts.

To use this from a button later: call ``compose()`` once (and again only when
the selected hue changes) to get the gradient image, call ``draw_markers()`` on
top of it each frame for the two indicator rings, and feed the fingertip
position into a ``ColorWheelPicker`` to get hex updates back.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw

from .shape_color import hex_to_rgb, rgb_to_hex

Point = Tuple[float, float]


@dataclass(frozen=True)
class ColorWheelLayout:
    center: Point
    outer_radius: float
    ring_width: float

    @property
    def inner_radius(self) -> float:
        return self.outer_radius - self.ring_width

    @property
    def square_size(self) -> float:
        # Largest square that fits inside the ring's inner circle.
        return self.inner_radius * math.sqrt(2)

    @property
    def square_bounds(self) -> Tuple[float, float, float, float]:
        cx, cy = self.center
        half = self.square_size / 2
        return (cx - half, cy - half, cx + half, cy + half)


def fit_layout(center: Point, outer_radius: float, ring_fraction: float = 0.22) -> ColorWheelLayout:
    """Build a layout from a center point and overall (outer) radius."""
    return ColorWheelLayout(center, outer_radius, outer_radius * ring_fraction)


def hit_region(layout: ColorWheelLayout, point: Point) -> Optional[str]:
    """Return 'ring', 'square', or None for where a point lands on the wheel."""
    cx, cy = layout.center
    x, y = point
    distance = math.hypot(x - cx, y - cy)
    if layout.inner_radius <= distance <= layout.outer_radius:
        return "ring"
    x1, y1, x2, y2 = layout.square_bounds
    if x1 <= x <= x2 and y1 <= y <= y2:
        return "square"
    return None


def hue_at(layout: ColorWheelLayout, point: Point) -> float:
    """Hue in degrees [0, 360) for a point on (or off) the ring."""
    cx, cy = layout.center
    x, y = point
    return math.degrees(math.atan2(-(y - cy), x - cx)) % 360.0


def saturation_value_at(layout: ColorWheelLayout, point: Point) -> Tuple[float, float]:
    """Saturation/value in [0, 1] for a point on (or off) the square."""
    x1, y1, x2, y2 = layout.square_bounds
    size = x2 - x1
    saturation = (point[0] - x1) / size
    value = 1.0 - (point[1] - y1) / size
    return _clamp01(saturation), _clamp01(value)


def point_for_saturation_value(layout: ColorWheelLayout, saturation: float, value: float) -> Point:
    """Inverse of saturation_value_at, for placing the square's marker."""
    x1, y1, x2, y2 = layout.square_bounds
    size = x2 - x1
    return (x1 + _clamp01(saturation) * size, y1 + (1.0 - _clamp01(value)) * size)


def point_for_hue(layout: ColorWheelLayout, hue: float) -> Point:
    """Inverse of hue_at, for placing the ring's marker at its mid-radius."""
    cx, cy = layout.center
    radius = (layout.inner_radius + layout.outer_radius) / 2
    angle = math.radians(hue)
    return (cx + radius * math.cos(angle), cy - radius * math.sin(angle))


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def hsv_to_hex(hue_degrees: float, saturation: float, value: float) -> str:
    r, g, b = _hsv_to_rgb_scalar(hue_degrees / 360.0, saturation, value)
    return rgb_to_hex((r * 255.0, g * 255.0, b * 255.0))


def hex_to_hsv(hex_code: str) -> Tuple[float, float, float]:
    r, g, b = (channel / 255.0 for channel in hex_to_rgb(hex_code))
    h, s, v = _rgb_to_hsv_scalar(r, g, b)
    return h * 360.0, s, v


def pick_color(layout: ColorWheelLayout, point: Point,
                current_hue: float = 0.0) -> Optional[Tuple[str, float, float, float]]:
    """Resolve a pointer position to a color, if it lands on the wheel.

    Returns (hex_code, hue, saturation, value), or None if the point misses
    both the ring and the square. ``current_hue`` is used when the point
    lands on the square, so picking saturation/value keeps the last hue.
    """
    region = hit_region(layout, point)
    if region == "ring":
        hue = hue_at(layout, point)
        return hsv_to_hex(hue, 1.0, 1.0), hue, 1.0, 1.0
    if region == "square":
        saturation, value = saturation_value_at(layout, point)
        return hsv_to_hex(current_hue, saturation, value), current_hue, saturation, value
    return None


class ColorWheelPicker:
    """Edge-triggers a color pick when a pinch starts over the wheel.

    Mirrors the ``frame.pinching and not self.pinching`` edge used in
    shape_interaction.ShapeInteraction, so a gesture loop can call update()
    once per frame and only react when a new pick is returned.
    """

    def __init__(self, layout: ColorWheelLayout, initial_hex: str = "#B4B4B4"):
        self.layout = layout
        self.hex_code = initial_hex
        self.hue, self.saturation, self.value = hex_to_hsv(initial_hex)
        self._was_pinching = False

    def update(self, point: Optional[Point], pinching: bool) -> Optional[str]:
        """Call once per frame; returns the newly picked hex code, or None."""
        picked = None
        if point is not None and pinching and not self._was_pinching:
            result = pick_color(self.layout, point, self.hue)
            if result is not None:
                self.hex_code, self.hue, self.saturation, self.value = result
                picked = self.hex_code
        self._was_pinching = pinching
        return picked


def _hsv_to_rgb_scalar(h: float, s: float, v: float) -> Tuple[float, float, float]:
    rgb = _hsv_to_rgb_array(np.array([h]), np.array([s]), np.array([v]))
    return float(rgb[0, 0]), float(rgb[0, 1]), float(rgb[0, 2])


def _rgb_to_hsv_scalar(r: float, g: float, b: float) -> Tuple[float, float, float]:
    maxc, minc = max(r, g, b), min(r, g, b)
    v = maxc
    delta = maxc - minc
    s = 0.0 if maxc == 0 else delta / maxc
    if delta == 0:
        h = 0.0
    elif maxc == r:
        h = ((g - b) / delta) % 6.0
    elif maxc == g:
        h = (b - r) / delta + 2.0
    else:
        h = (r - g) / delta + 4.0
    return h / 6.0, s, v


def _hsv_to_rgb_array(h: np.ndarray, s: np.ndarray, v: np.ndarray) -> np.ndarray:
    """Vectorized HSV -> RGB in [0, 1], for rendering the gradient quickly."""
    i = np.floor(h * 6.0)
    f = h * 6.0 - i
    p = v * (1.0 - s)
    q = v * (1.0 - f * s)
    t = v * (1.0 - (1.0 - f) * s)
    i = i.astype(int) % 6

    r = np.select([i == 0, i == 1, i == 2, i == 3, i == 4, i == 5], [v, q, p, p, t, v])
    g = np.select([i == 0, i == 1, i == 2, i == 3, i == 4, i == 5], [t, v, v, q, p, p])
    b = np.select([i == 0, i == 1, i == 2, i == 3, i == 4, i == 5], [p, p, t, v, v, q])
    return np.stack([r, g, b], axis=-1)


def render_ring(layout: ColorWheelLayout, size: int = 320) -> Image.Image:
    """Render just the hue ring as an RGBA image; independent of selected hue."""
    scale = size / (2 * layout.outer_radius)
    local = ColorWheelLayout((size / 2, size / 2), layout.outer_radius * scale,
                              layout.ring_width * scale)
    y, x = np.mgrid[0:size, 0:size].astype(float)
    cx, cy = local.center
    dx, dy = x - cx, y - cy
    distance = np.hypot(dx, dy)
    hue = (np.degrees(np.arctan2(-dy, dx)) % 360.0) / 360.0

    rgb = _hsv_to_rgb_array(hue, np.ones_like(hue), np.ones_like(hue))
    alpha = ((distance >= local.inner_radius) & (distance <= local.outer_radius)).astype(float)
    rgba = np.concatenate([rgb, alpha[..., None]], axis=-1)
    return Image.fromarray((rgba * 255).astype(np.uint8), mode="RGBA")


def render_square(layout: ColorWheelLayout, hue: float, size: int = 320) -> Image.Image:
    """Render the saturation/value square tinted to ``hue``, as an RGBA image."""
    scale = size / (2 * layout.outer_radius)
    local = ColorWheelLayout((size / 2, size / 2), layout.outer_radius * scale,
                              layout.ring_width * scale)
    x1, y1, x2, y2 = local.square_bounds
    side = max(1, round(x2 - x1))
    yy, xx = np.mgrid[0:side, 0:side].astype(float)
    saturation = xx / (side - 1) if side > 1 else xx
    value = 1.0 - yy / (side - 1) if side > 1 else 1.0 - yy
    hue_plane = np.full_like(saturation, (hue % 360.0) / 360.0)

    rgb = _hsv_to_rgb_array(hue_plane, saturation, value)
    rgba = np.concatenate([rgb, np.ones_like(saturation)[..., None]], axis=-1)
    tile = Image.fromarray((rgba * 255).astype(np.uint8), mode="RGBA")
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.paste(tile, (round(x1), round(y1)))
    return canvas


def compose(layout: ColorWheelLayout, hue: float = 0.0, size: int = 320) -> Image.Image:
    """Combine the ring and the hue-tinted square into one RGBA image."""
    wheel = render_ring(layout, size)
    square = render_square(layout, hue, size)
    wheel.alpha_composite(square)
    return wheel


def draw_markers(image: Image.Image, layout: ColorWheelLayout, hue: float, saturation: float,
                  value: float, size: int = 320, radius: int = 7) -> Image.Image:
    """Draw the ring-hue and square-saturation/value indicator circles, like the reference."""
    scale = size / (2 * layout.outer_radius)
    local = ColorWheelLayout((size / 2, size / 2), layout.outer_radius * scale,
                              layout.ring_width * scale)
    draw = ImageDraw.Draw(image)
    for point in (point_for_hue(local, hue), point_for_saturation_value(local, saturation, value)):
        x, y = point
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), outline="white", width=2)
    return image
