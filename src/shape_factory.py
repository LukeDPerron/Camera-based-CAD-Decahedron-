import numpy as np

from .scene_objects import Cube, Pyramid, SceneObject, Sphere, Transform
from .shape_types import ShapeType


class ShapeFactory:
    _counts = {
        ShapeType.CUBE: 0,
        ShapeType.SPHERE: 0,
        ShapeType.PYRAMID: 0,
    }

    @classmethod
    def create(cls, shape_type: ShapeType, position=None) -> SceneObject:
        if not isinstance(shape_type, ShapeType):
            raise ValueError(f"Unknown shape: {shape_type}")

        transform = Transform()
        if position is not None:
            coordinates = np.asarray(position, dtype=float)
            if coordinates.shape != (3,) or not np.isfinite(coordinates).all():
                raise ValueError("Shape position must contain three finite coordinates")
            transform.position = coordinates.copy()

        cls._counts[shape_type] += 1
        n = cls._counts[shape_type]
        if shape_type is ShapeType.CUBE:
            return Cube(f"Cube #{n}", transform)
        if shape_type is ShapeType.SPHERE:
            return Sphere(f"Sphere #{n}", transform)
        if shape_type is ShapeType.PYRAMID:
            return Pyramid(f"Pyramid #{n}", transform)
        raise AssertionError(f"Unhandled shape: {shape_type}")
