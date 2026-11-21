"""Change the color of scene objects (src.scene_objects.SceneObject).

Every SceneObject already carries a mutable ``color`` attribute (an RGB
triplet) that scene_overlay.py reads when shading and drawing it, so applying
a new color is just a matter of validating the input and assigning it.
"""

from __future__ import annotations

from typing import Iterable, Tuple, Union

RGB = Tuple[int, int, int]
Color = Union[str, RGB]


def hex_to_rgb(hex_code: str) -> RGB:
    """Convert a '#RRGGBB' (or 'RRGGBB') string to an (r, g, b) triplet."""
    code = hex_code.strip().lstrip("#")
    if len(code) != 6 or any(c not in "0123456789abcdefABCDEF" for c in code):
        raise ValueError(f"Expected a 6-digit hex color, got {hex_code!r}")
    return tuple(int(code[i:i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb: RGB) -> str:
    """Convert an (r, g, b) triplet to a '#RRGGBB' string."""
    r, g, b = (max(0, min(255, round(channel))) for channel in rgb)
    return f"#{r:02X}{g:02X}{b:02X}"


def _resolve_rgb(color: Color) -> RGB:
    if isinstance(color, str):
        return hex_to_rgb(color)
    r, g, b = color
    return max(0, min(255, round(r))), max(0, min(255, round(g))), max(0, min(255, round(b)))


def set_shape_color(obj, color: Color) -> RGB:
    """Set a single scene object's color. Accepts a hex string or an RGB triplet."""
    rgb = _resolve_rgb(color)
    obj.color = rgb
    return rgb


def set_shapes_color(objects: Iterable, color: Color) -> RGB:
    """Set the color of every object in an iterable (e.g. ShapeInteraction.selected)."""
    rgb = _resolve_rgb(color)
    for obj in objects:
        obj.color = rgb
    return rgb
