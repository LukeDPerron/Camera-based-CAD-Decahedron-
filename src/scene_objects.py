from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np

from .gesture_event import ShapeType


@dataclass
class Transform:
    position: np.ndarray = field(default_factory=lambda: np.array([0.0, 0.0, 4.0], dtype=float))
    rotation: np.ndarray = field(default_factory=lambda: np.zeros(3, dtype=float))
    scale: np.ndarray = field(default_factory=lambda: np.ones(3, dtype=float))


@dataclass
class RigidBody:
    velocity: np.ndarray = field(default_factory=lambda: np.zeros(3, dtype=float))
    angular_velocity: np.ndarray = field(default_factory=lambda: np.zeros(3, dtype=float))
    mass: float = 1.0
    restitution: float = 0.35
    friction: float = 0.8
    gravity_enabled: bool = True

    @property
    def inverse_mass(self) -> float:
        return 0.0 if self.mass <= 0.0 else 1.0 / self.mass


class SceneObject(ABC):
    def __init__(self, name: str, shape_type: ShapeType, transform: Transform | None = None):
        self.name = name
        self.shape_type = shape_type
        self.transform = transform or Transform()
        self.color = (180, 180, 180)
        self.rigid_body = RigidBody()

    def translate(self, axis: str, amount: float) -> None:
        index = {"x": 0, "y": 1, "z": 2}[axis]
        self.transform.position[index] += amount

    def apply_scale(self, amount: float) -> None:
        factor = max(0.1, float(amount))
        self.transform.scale *= factor

    @abstractmethod
    def get_mesh(self) -> dict:
        ...


class Cube(SceneObject):
    def __init__(self, name: str, transform: Transform | None = None):
        super().__init__(name, ShapeType.CUBE, transform)

    def get_mesh(self) -> dict:
        s = 0.35 * self.transform.scale
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
        radius = 0.32 * float(np.mean(self.transform.scale))
        return {"kind": "sphere", "radius": radius}


class Cylinder(SceneObject):
    def __init__(self, name: str, transform: Transform | None = None):
        super().__init__(name, ShapeType.CYLINDER, transform)

    def get_mesh(self) -> dict:
        r = 0.22 * float(np.mean(self.transform.scale[:2]))
        h = 0.5 * float(self.transform.scale[1])
        rings = []
        for y in (-h, h):
            ring = []
            for i in range(12):
                a = 2 * np.pi * i / 12
                ring.append([r * np.cos(a), y, r * np.sin(a)])
            rings.append(np.array(ring, dtype=float))
        points = np.vstack(rings)
        edges = []
        for ring_i in range(2):
            for i in range(12):
                a = ring_i * 12 + i
                b = ring_i * 12 + (i + 1) % 12
                edges.append((a, b))
        for i in range(12):
            edges.append((i, i + 12))
        return {"kind": "wire", "local_points": points, "edges": edges}


class Pyramid(SceneObject):
    def __init__(self, name: str, transform: Transform | None = None):
        super().__init__(name, ShapeType.PYRAMID, transform)

    def get_mesh(self) -> dict:
        s = self.transform.scale
        x = 0.35 * s[0]
        y = 0.35 * s[1]
        z = 0.35 * s[2]
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
