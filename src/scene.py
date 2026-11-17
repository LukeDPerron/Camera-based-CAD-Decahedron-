import numpy as np

from .gesture_event import ShapeType
from .scene_objects import SceneObject
from .shape_factory import ShapeFactory

# New shapes are laid out left to right in front of the viewer camera so they
# do not spawn on top of each other.
SPAWN_SLOTS = 5
SPAWN_SPACING = 1.2
SPAWN_DEPTH = 4.0


class Scene:
    def __init__(self):
        self.objects: list[SceneObject] = []
        self.selected: SceneObject | None = None

    def add(self, obj: SceneObject) -> None:
        self.objects.append(obj)
        self.selected = obj

    def spawn(self, shape_type: ShapeType) -> SceneObject:
        """Create a shape in the next free slot and select it."""
        index = len(self.objects)
        column = index % SPAWN_SLOTS - SPAWN_SLOTS // 2
        row = index // SPAWN_SLOTS
        position = (column * SPAWN_SPACING, row * SPAWN_SPACING, SPAWN_DEPTH)
        obj = ShapeFactory.create(shape_type, position=position)
        self.add(obj)
        return obj

    def select_next(self) -> SceneObject | None:
        """Cycle the selection through the shapes in creation order."""
        if not self.objects:
            self.selected = None
            return None
        if self.selected in self.objects:
            index = (self.objects.index(self.selected) + 1) % len(self.objects)
        else:
            index = 0
        self.selected = self.objects[index]
        return self.selected

    def move_selected(self, delta) -> bool:
        """Translate the selected shape; returns False when nothing is selected."""
        offset = np.asarray(delta, dtype=float)
        if offset.shape != (3,) or not np.isfinite(offset).all():
            raise ValueError("Move delta must contain three finite coordinates")
        if self.selected is None:
            return False
        # Rebind rather than mutate in place: the viewer thread reads positions.
        self.selected.transform.position = self.selected.transform.position + offset
        return True
