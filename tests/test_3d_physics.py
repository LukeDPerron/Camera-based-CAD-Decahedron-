import unittest

import numpy as np

from src.gesture_event import ShapeType
from src.physics import PhysicsWorld
from src.scene import Scene
from src.shape_factory import ShapeFactory


class PhysicsWorldTests(unittest.TestCase):
    def test_gravity_moves_object_down(self):
        scene = Scene()
        obj = ShapeFactory.create(ShapeType.CUBE)
        obj.transform.position[:] = [0.0, 5.0, 0.0]
        obj.rigid_body.velocity[:] = [0.0, 0.0, 0.0]
        scene.add(obj)

        PhysicsWorld(ground_y=-2.0).step(scene, 0.1)

        self.assertLess(obj.transform.position[1], 5.0)

    def test_ground_collision_stops_and_bounces(self):
        scene = Scene()
        obj = ShapeFactory.create(ShapeType.SPHERE)
        obj.transform.position[:] = [0.0, -1.0, 0.0]
        obj.rigid_body.velocity[:] = [0.0, -2.0, 0.0]
        scene.add(obj)

        PhysicsWorld(ground_y=-1.0).step(scene, 0.1)

        self.assertGreaterEqual(obj.transform.position[1], -1.0)
        self.assertGreaterEqual(obj.rigid_body.velocity[1], 0.0)

    def test_object_collision_separates_overlapping_objects(self):
        scene = Scene()
        first = ShapeFactory.create(ShapeType.SPHERE, [0.0, 0.0, 0.0])
        second = ShapeFactory.create(ShapeType.SPHERE, [0.1, 0.0, 0.0])
        scene.add(first)
        scene.add(second)

        PhysicsWorld(gravity=(0.0, 0.0, 0.0)).step(scene, 0.01)

        distance = float(np.linalg.norm(second.transform.position - first.transform.position))
        self.assertGreater(distance, 0.1)

    def test_pyramid_is_created_and_meshed(self):
        obj = ShapeFactory.create(ShapeType.PYRAMID)

        mesh = obj.get_mesh()

        self.assertEqual(mesh["kind"], "triangles")
        self.assertEqual(len(mesh["local_points"]), 5)
        self.assertEqual(len(mesh["faces"]), 6)


if __name__ == "__main__":
    unittest.main()
