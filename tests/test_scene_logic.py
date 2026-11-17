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


class SceneSelectionTests(unittest.TestCase):
    def setUp(self):
        self.scene = Scene()

    def test_spawned_shapes_do_not_overlap_and_newest_is_selected(self):
        shapes = [self.scene.spawn(ShapeType.CUBE) for _ in range(7)]

        positions = {tuple(shape.transform.position) for shape in shapes}
        self.assertEqual(len(positions), 7)
        self.assertIs(self.scene.selected, shapes[-1])

    def test_move_selected_only_moves_the_selected_shape(self):
        first = self.scene.spawn(ShapeType.CUBE)
        second = self.scene.spawn(ShapeType.SPHERE)
        first_before = first.transform.position.copy()
        second_before = second.transform.position.copy()

        self.assertTrue(self.scene.move_selected((1.0, -2.0, 0.5)))

        np.testing.assert_array_equal(first.transform.position, first_before)
        np.testing.assert_allclose(second.transform.position, second_before + [1.0, -2.0, 0.5])

    def test_move_without_selection_is_a_no_op(self):
        self.assertFalse(self.scene.move_selected((1.0, 0.0, 0.0)))

    def test_move_rejects_invalid_delta(self):
        self.scene.spawn(ShapeType.CUBE)
        with self.assertRaises(ValueError):
            self.scene.move_selected((float("nan"), 0.0, 0.0))

    def test_select_next_cycles_through_shapes(self):
        self.assertIsNone(self.scene.select_next())
        first = self.scene.spawn(ShapeType.CUBE)
        second = self.scene.spawn(ShapeType.PYRAMID)

        self.assertIs(self.scene.select_next(), first)
        self.assertIs(self.scene.select_next(), second)


if __name__ == "__main__":
    unittest.main()
