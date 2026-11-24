"""Top-center color picker overlay: a droplet toggle button and a palette
page, selected the same way the shape toolbar selects a shape -- hover the
fingertip over a control and hold for a moment (DwellSelector), not a pinch.

Picking a color only changes what the *next* created shape will use. It
never touches shapes that already exist; see colors/shape_color.py for the
actual color assignment, which app.py applies right after a shape is spawned.

The color-wheel second page still needs work and is disabled for now -- its
code is commented out below rather than removed, not deleted outright.
"""

from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from typing import Optional, Tuple

from PIL import ImageTk

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from colors.color_wheel import hex_to_hsv
# Color-wheel page is disabled for now (needs more work); its imports and
# usages below are commented out rather than removed.
# from colors.color_wheel import compose, draw_markers, fit_layout, pick_color
from colors.shape_color import hex_to_rgb
from dwell import DwellSelector

PALETTE = (
    ("White", "#FFFFFF"),
    ("Grey", "#B4B4B4"),
    ("Black", "#000000"),
    ("Red", "#FF0000"),
    ("Blue", "#0000FF"),
    ("Purple", "#800080"),
    ("Brown", "#8B4513"),
    ("Yellow", "#FFFF00"),
    ("Green", "#00FF00"),
    ("Pink", "#FFC0CB"),
    ("Light blue", "#ADD8E6"),
    ("Light purple", "#E6E6FA"),
)
DEFAULT_HEX = "#B4B4B4"

DROPLET_SIZE = 40
SWATCH_SIZE = 28
SWATCH_GAP = 8
SWATCH_COLUMNS = 6
ARROW_SIZE = 26
WHEEL_RADIUS = 78
PANEL_BG = "#18212B"
PANEL_BORDER = "#344353"
TEXT = "#EDF4F7"
MUTED = "#95A5B5"
ACCENT = "#5FE6BE"


def panel_frame_rect(image_size, canvas_size):
    """Same letterboxing math as app._shape_layout, kept standalone here."""
    iw, ih = image_size
    width, height = canvas_size
    scale = min(max(1, width) / iw, max(1, height) / ih)
    fw, fh = int(iw * scale), int(ih * scale)
    return (width - fw) / 2, (height - fh) / 2, fw, fh


class ColorPanel:
    def __init__(self):
        self.open = False
        self.page = "palette"
        self.selected_hex = DEFAULT_HEX
        self.hue, self.saturation, self.value = hex_to_hsv(DEFAULT_HEX)
        self.dwell = DwellSelector(duration=1.0, max_gap=0.35)
        self._wheel_photo = None
        self._wheel_image_hue = None

    @property
    def selected_rgb(self) -> Tuple[int, int, int]:
        return hex_to_rgb(self.selected_hex)

    def _droplet_rect(self, rect):
        left, top, fw, _ = rect
        cx = left + fw / 2
        half = DROPLET_SIZE / 2
        y1 = top + 10
        return (cx - half, y1, cx + half, y1 + DROPLET_SIZE)

    def _palette_layout(self, rect):
        left, top, fw, _ = rect
        _, _, _, droplet_bottom = self._droplet_rect(rect)
        columns = SWATCH_COLUMNS
        rows = -(-len(PALETTE) // columns)
        grid_w = columns * SWATCH_SIZE + (columns - 1) * SWATCH_GAP
        x0 = left + fw / 2 - grid_w / 2
        y0 = droplet_bottom + 36
        swatches = []
        for index, (name, hex_code) in enumerate(PALETTE):
            row, column = divmod(index, columns)
            x = x0 + column * (SWATCH_SIZE + SWATCH_GAP)
            y = y0 + row * (SWATCH_SIZE + SWATCH_GAP)
            swatches.append((name, hex_code, (x, y, x + SWATCH_SIZE, y + SWATCH_SIZE)))
        grid_h = rows * SWATCH_SIZE + (rows - 1) * SWATCH_GAP
        bounds = (x0 - 12, droplet_bottom + 8, x0 + grid_w + 12, y0 + grid_h + ARROW_SIZE + 18)
        arrow = (bounds[2] - ARROW_SIZE - 10, bounds[3] - ARROW_SIZE - 8,
                 bounds[2] - 10, bounds[3] - 8)
        return swatches, arrow, bounds

    # Color-wheel page: disabled for now, needs more work. Kept commented
    # out (not deleted) so it can be picked back up later.
    # def _wheel_layout(self, rect):
    #     left, top, fw, _ = rect
    #     _, _, _, droplet_bottom = self._droplet_rect(rect)
    #     cx = left + fw / 2
    #     cy = droplet_bottom + 36 + WHEEL_RADIUS
    #     bounds = (cx - WHEEL_RADIUS - 14, droplet_bottom + 8,
    #               cx + WHEEL_RADIUS + 14, cy + WHEEL_RADIUS + ARROW_SIZE + 18)
    #     arrow = (bounds[0] + 10, bounds[3] - ARROW_SIZE - 8,
    #              bounds[0] + 10 + ARROW_SIZE, bounds[3] - 8)
    #     return (cx, cy), arrow, bounds

    @staticmethod
    def _inside(point, rect):
        if point is None:
            return False
        x, y = point
        x1, y1, x2, y2 = rect
        return x1 <= x <= x2 and y1 <= y <= y2

    def hover_target(self, point, rect) -> Optional[str]:
        """What the fingertip is currently over, for highlighting while aiming."""
        if self._inside(point, self._droplet_rect(rect)):
            return "droplet"
        if not self.open:
            return None
        if self.page == "palette":
            swatches, arrow, _ = self._palette_layout(rect)
            # Forward arrow (-> color wheel) disabled along with that page;
            # not reachable while it's commented out.
            # if self._inside(point, arrow):
            #     return "arrow"
            for name, hex_code, swatch_rect in swatches:
                if self._inside(point, swatch_rect):
                    return hex_code
        # else:  # color-wheel page -- disabled, see _wheel_layout/_draw_wheel
        #     center, arrow, _ = self._wheel_layout(rect)
        #     if self._inside(point, arrow):
        #         return "arrow"
        #     if pick_color(fit_layout(center, WHEEL_RADIUS), point, self.hue) is not None:
        #         return "wheel"
        return None

    def over_panel(self, point, rect) -> bool:
        """Whether a point lands anywhere on the (open) panel's hit area."""
        if self._inside(point, self._droplet_rect(rect)):
            return True
        if not self.open:
            return False
        # Wheel page is disabled; palette is the only page while it's off.
        _, _, bounds = self._palette_layout(rect)
        return self._inside(point, bounds)

    def _apply(self, target: str, point: Tuple[float, float], rect) -> None:
        """Commit the control under `target` once dwell has fired on it."""
        if target == "droplet":
            self.open = not self.open
        elif self.page == "palette":
            # "arrow" (-> color wheel) is disabled along with that page;
            # hover_target() never returns it while commented out, so this
            # branch would only matter once the wheel is re-enabled.
            # if target == "arrow":
            #     self.page = "wheel"
            # else:
            for name, hex_code, _ in self._palette_layout(rect)[0]:
                if hex_code == target:
                    self.selected_hex = hex_code
                    self.hue, self.saturation, self.value = hex_to_hsv(hex_code)
                    break
        # else:  # color-wheel page -- disabled, see _wheel_layout/_draw_wheel
        #     if target == "arrow":
        #         self.page = "palette"
        #     else:
        #         center, _, _ = self._wheel_layout(rect)
        #         result = pick_color(fit_layout(center, WHEEL_RADIUS), point, self.hue)
        #         if result is not None:
        #             self.selected_hex, self.hue, self.saturation, self.value = result

    def update(self, point: Optional[Tuple[float, float]], now: float, rect) -> None:
        """Call once per frame with the fingertip position; selects after a
        short hover, same as the shape toolbar's DwellSelector."""
        target = self.hover_target(point, rect)
        fired = self.dwell.update(target, now)
        if fired is not None:
            self._apply(fired, point, rect)

    def pick_now(self, point: Optional[Tuple[float, float]], rect) -> None:
        """Mouse-click fallback: select immediately, same as _click_shape."""
        target = self.hover_target(point, rect)
        if target is not None:
            self._apply(target, point, rect)
        self.dwell.reset()

    def draw(self, canvas: tk.Canvas, rect, hover=None, tag="color_panel"):
        canvas.delete(tag)
        x1, y1, x2, y2 = self._droplet_rect(rect)
        outline = ACCENT if hover == "droplet" else PANEL_BORDER
        canvas.create_oval(x1, y1, x2, y2, fill=PANEL_BG, outline=outline, width=2, tags=tag)
        self._draw_dwell_arc(canvas, "droplet", (x1, y1, x2, y2), tag)
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        swatch_color = self.selected_hex
        canvas.create_oval(cx - 8, cy - 9, cx + 8, cy + 7, fill=swatch_color, outline="", tags=tag)
        canvas.create_polygon(cx, cy - 13, cx + 7, cy - 1, cx - 7, cy - 1,
                              fill=swatch_color, outline="", tags=tag)
        if not self.open:
            return
        # Wheel page is disabled for now; always draw the palette.
        self._draw_palette(canvas, rect, hover, tag)
        # if self.page == "palette":
        #     self._draw_palette(canvas, rect, hover, tag)
        # else:
        #     self._draw_wheel(canvas, rect, hover, tag)

    def _draw_palette(self, canvas, rect, hover, tag):
        swatches, arrow, bounds = self._palette_layout(rect)
        bx1, by1, bx2, by2 = bounds
        canvas.create_rectangle(bx1, by1, bx2, by2, fill=PANEL_BG, outline=PANEL_BORDER, tags=tag)
        canvas.create_text((bx1 + bx2) / 2, by1 + 12, text="PRESETS", fill=MUTED,
                           font=("Helvetica", 10, "bold"), tags=tag)
        for name, hex_code, (sx1, sy1, sx2, sy2) in swatches:
            is_selected = hex_code == self.selected_hex
            is_hover = hover == hex_code
            width = 3 if is_selected else 2
            outline = ACCENT if (is_selected or is_hover) else PANEL_BORDER
            canvas.create_rectangle(sx1, sy1, sx2, sy2, fill=hex_code, outline=outline,
                                    width=width, tags=tag)
            self._draw_dwell_arc(canvas, hex_code, (sx1, sy1, sx2, sy2), tag)
        # Forward arrow (-> color wheel) disabled along with that page.
        # self._draw_arrow(canvas, arrow, hover == "arrow", forward=True, tag=tag)
        # self._draw_dwell_arc(canvas, "arrow", arrow, tag)

    # Color-wheel page: disabled for now, needs more work. Kept commented
    # out (not deleted) so it can be picked back up later.
    # def _draw_wheel(self, canvas, rect, hover, tag):
    #     center, arrow, bounds = self._wheel_layout(rect)
    #     bx1, by1, bx2, by2 = bounds
    #     canvas.create_rectangle(bx1, by1, bx2, by2, fill=PANEL_BG, outline=PANEL_BORDER, tags=tag)
    #     size = int(WHEEL_RADIUS * 2)
    #     if self._wheel_photo is None or self._wheel_image_hue != round(self.hue, 1):
    #         layout = fit_layout((size / 2, size / 2), WHEEL_RADIUS)
    #         image = compose(layout, self.hue, size)
    #         image = draw_markers(image, layout, self.hue, self.saturation, self.value, size)
    #         self._wheel_photo = ImageTk.PhotoImage(image, master=canvas)
    #         self._wheel_image_hue = round(self.hue, 1)
    #     canvas.create_image(center[0], center[1], image=self._wheel_photo, tags=tag)
    #     if self.dwell.target == "wheel" and self.dwell.progress > 0:
    #         r = WHEEL_RADIUS + 6
    #         canvas.create_arc(center[0] - r, center[1] - r, center[0] + r, center[1] + r,
    #                           start=90, extent=-359.9 * self.dwell.progress, style="arc",
    #                           outline=ACCENT, width=2, tags=tag)
    #     cx, cy = center
    #     text_x = cx + WHEEL_RADIUS + 20
    #     r, g, b = self.selected_rgb
    #     for index, line in enumerate((f"hex  {self.selected_hex}", f"R  {r}", f"G  {g}", f"B  {b}")):
    #         canvas.create_text(text_x, by1 + 18 + index * 16, text=line, fill=TEXT, anchor="w",
    #                            font=("Helvetica", 10), tags=tag)
    #     self._draw_arrow(canvas, arrow, hover == "arrow", forward=False, tag=tag)
    #     self._draw_dwell_arc(canvas, "arrow", arrow, tag)

    def _draw_dwell_arc(self, canvas, target, bounds, tag):
        """Radial progress ring while hovering a control, same look as the
        shape toolbar's dwell indicator."""
        if self.dwell.target != target or self.dwell.progress <= 0:
            return
        x1, y1, x2, y2 = bounds
        canvas.create_arc(x1 + 1, y1 + 1, x2 - 1, y2 - 1, start=90,
                          extent=-359.9 * self.dwell.progress, style="arc",
                          outline=ACCENT, width=2, tags=tag)

    @staticmethod
    def _draw_arrow(canvas, rect, is_hover, forward, tag):
        ax1, ay1, ax2, ay2 = rect
        amy = (ay1 + ay2) / 2
        color = ACCENT if is_hover else TEXT
        canvas.create_oval(ax1, ay1, ax2, ay2, fill=PANEL_BG, outline=color, width=2, tags=tag)
        pad = (ax2 - ax1) * 0.28
        if forward:
            canvas.create_line(ax1 + pad, amy, ax2 - pad, amy, fill=color, width=2, tags=tag)
            canvas.create_line(ax2 - pad - 6, amy - 6, ax2 - pad, amy, ax2 - pad - 6, amy + 6,
                               fill=color, width=2, tags=tag)
        else:
            canvas.create_line(ax1 + pad, amy, ax2 - pad, amy, fill=color, width=2, tags=tag)
            canvas.create_line(ax1 + pad + 6, amy - 6, ax1 + pad, amy, ax1 + pad + 6, amy + 6,
                               fill=color, width=2, tags=tag)
