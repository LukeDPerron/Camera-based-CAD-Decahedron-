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

    def test_create_command_adds_and_selects_shape(self):
        event = GestureEvent(
            type=GestureType.CREATE_SHAPE,
            confidence=1.0,
            shape_type=ShapeType.CYLINDER,
        )

        self.handler.handle(event, np.array([1.0, 2.0, 4.0]), [])

        self.assertEqual(len(self.scene.objects), 1)
        self.assertIs(self.scene.selected, self.scene.objects[0])
        self.assertIs(self.scene.selected.shape_type, ShapeType.CYLINDER)
        np.testing.assert_array_equal(self.scene.selected.transform.position, [1.0, 2.0, 4.0])

    def test_cursor_gesture_selects_nearest_object(self):
        first = ShapeFactory.create(ShapeType.CUBE, [0.0, 0.0, 4.0])
        second = ShapeFactory.create(ShapeType.SPHERE, [1.0, 0.0, 4.0])
        self.scene.add(first)
        self.scene.add(second)
        event = GestureEvent(
            type=GestureType.CURSOR_SELECT,
            confidence=1.0,
            cursor_pos=(106.0, 100.0),
        )

        self.handler.handle(event, None, [(first, (100.0, 100.0)), (second, (110.0, 100.0))])

        self.assertIs(self.scene.selected, second)

    def test_axis_gestures_translate_only_the_selected_axis(self):
        shape = ShapeFactory.create(ShapeType.CUBE, [0.0, 0.0, 4.0])
        self.scene.add(shape)

        for gesture, delta in (
            (GestureType.X_AXIS, (0.5, 0.0, 0.0)),
            (GestureType.Y_AXIS, (0.0, -0.25, 0.0)),
            (GestureType.Z_AXIS, (0.0, 0.0, 1.0)),
        ):
            self.handler.handle(GestureEvent(gesture, 1.0, delta=delta), None, [])

        np.testing.assert_allclose(shape.transform.position, [0.5, -0.25, 5.0])

    def test_axis_gesture_without_selection_is_a_noop(self):
        self.handler.handle(
            GestureEvent(GestureType.X_AXIS, 1.0, delta=(0.5, 0.0, 0.0)),
            None,
            [],
        )

        self.assertEqual(self.scene.objects, [])


if __name__ == "__main__":
    unittest.main()
