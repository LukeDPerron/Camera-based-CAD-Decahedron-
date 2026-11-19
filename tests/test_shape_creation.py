import unittest

import numpy as np

from src.shape_types import ShapeType
from src.scene import Scene
from src.shape_factory import ShapeFactory


class ShapeCreationTests(unittest.TestCase):
    def test_supported_viewer_meshes_have_xyz_rows(self):
        from src.pyglet_viewer import (
            _cube_vertices,
            _pyramid_vertices,
            _sphere_vertices,
        )

        meshes = (
            _cube_vertices(),
            _sphere_vertices(0.32),
            _pyramid_vertices(),
        )

        for vertices in meshes:
            self.assertEqual(vertices.ndim, 2)
            self.assertEqual(vertices.shape[1], 3)
            self.assertGreater(len(vertices), 0)

    def test_create_shape_at_position(self):
        position = np.array([1.0, 2.0, 3.0])
        shape = ShapeFactory.create(ShapeType.CUBE, position)
        position[0] = 99.0

        np.testing.assert_array_equal(shape.transform.position, [1.0, 2.0, 3.0])

    def test_reject_invalid_shape_without_changing_counters(self):
        count = ShapeFactory._counts[ShapeType.CUBE]

        with self.assertRaises(ValueError):
            ShapeFactory.create("CUBE")

        self.assertEqual(ShapeFactory._counts[ShapeType.CUBE], count)

    def test_reject_invalid_position(self):
        with self.assertRaises(ValueError):
            ShapeFactory.create(ShapeType.SPHERE, [0.0, float("nan"), 1.0])

    def test_scene_stores_created_shape(self):
        scene = Scene()
        shape = ShapeFactory.create(ShapeType.PYRAMID, [1.0, 2.0, 4.0])

        scene.add(shape)

        self.assertEqual(scene.objects, [shape])
        self.assertIs(shape.shape_type, ShapeType.PYRAMID)
        np.testing.assert_array_equal(shape.transform.position, [1.0, 2.0, 4.0])


if __name__ == "__main__":
    unittest.main()
