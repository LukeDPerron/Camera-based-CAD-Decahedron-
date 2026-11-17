import unittest

import numpy as np

from src.command_handler import CommandHandler
from src.gesture_event import GestureEvent, GestureType, ShapeType
from src.scene import Scene
from src.shape_factory import ShapeFactory


class ShapeCreationTests(unittest.TestCase):
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


class GestureCommandTests(unittest.TestCase):
    def setUp(self):
        self.scene = Scene()
        self.handler = CommandHandler(self.scene)

    def test_create_command_adds_shape(self):
        event = GestureEvent(
            type=GestureType.CREATE_SHAPE,
            confidence=1.0,
            shape_type=ShapeType.CYLINDER,
        )

        self.handler.handle(event, np.array([1.0, 2.0, 4.0]), [])

        self.assertEqual(len(self.scene.objects), 1)
        self.assertIs(self.scene.objects[0].shape_type, ShapeType.CYLINDER)
        np.testing.assert_array_equal(self.scene.objects[0].transform.position, [1.0, 2.0, 4.0])


if __name__ == "__main__":
    unittest.main()
