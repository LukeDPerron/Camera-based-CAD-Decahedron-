from typing import Optional

import numpy as np

from .scene_objects import SceneObject


class Scene:
    def __init__(self):
        self.objects: list[SceneObject] = []
        self.selected: Optional[SceneObject] = None

    def add(self, obj: SceneObject) -> None:
        self.objects.append(obj)
        self.selected = obj

    def select_at(self, point, projected_centers: list[tuple[SceneObject, tuple[float, float]]]) -> None:
        if point is None or not projected_centers:
            return
        px, py = point
        best = None
        best_d = 80.0
        for obj, (ox, oy) in projected_centers:
            d = float(np.hypot(px - ox, py - oy))
            if d < best_d:
                best_d = d
                best = obj
        self.selected = best

    def move_selected(self, axis: str, amount: float) -> None:
        if self.selected is None:
            return
        self.selected.translate(axis, amount)
