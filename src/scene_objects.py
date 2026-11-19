from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np

from .shape_types import ShapeType


@dataclass
class Transform:
    position: np.ndarray = field(default_factory=lambda: np.array([0.0, 0.0, 4.0], dtype=float))


class SceneObject(ABC):
    def __init__(self, name: str, shape_type: ShapeType, transform: Transform | None = None):
        self.name = name
        self.shape_type = shape_type
        self.transform = transform or Transform()
        self.color = (180, 180, 180)

    @abstractmethod
    def get_mesh(self) -> dict:
        ...


class Cube(SceneObject):
    def __init__(self, name: str, transform: Transform | None = None):
        super().__init__(name, ShapeType.CUBE, transform)

    def get_mesh(self) -> dict:
        s = np.full(3, 0.35)
        corners = np.array(
            [[x, y, z] for x in (-s[0], s[0]) for y in (-s[1], s[1]) for z in (-s[2], s[2])],
            dtype=float,
        )
        edges = [
            (0, 1), (1, 3), (3, 2), (2, 0),
            (4, 5), (5, 7), (7, 6), (6, 4),
            (0, 4), (1, 5), (2, 6), (3, 7),
        ]
        return {"kind": "wire", "local_points": corners, "edges": edges}


class Sphere(SceneObject):
    def __init__(self, name: str, transform: Transform | None = None):
        super().__init__(name, ShapeType.SPHERE, transform)

    def get_mesh(self) -> dict:
        return {"kind": "sphere", "radius": 0.32}


class Pyramid(SceneObject):
    def __init__(self, name: str, transform: Transform | None = None):
        super().__init__(name, ShapeType.PYRAMID, transform)

    def get_mesh(self) -> dict:
        x = y = z = 0.35
        points = np.array(
            [
                [-x, -y, -z],
                [x, -y, -z],
                [x, -y, z],
                [-x, -y, z],
                [0.0, y, 0.0],
            ],
            dtype=float,
        )
        faces = [(0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4), (0, 3, 2), (0, 2, 1)]
        return {"kind": "triangles", "local_points": points, "faces": faces}
