import numpy as np

from .scene import Scene
from .scene_objects import Cube, Pyramid, SceneObject, Sphere


class PhysicsWorld:
    def __init__(self, gravity=(0.0, -9.81, 0.0), ground_y=-2.0):
        self.gravity = np.asarray(gravity, dtype=float)
        self.ground_y = float(ground_y)

    def step(self, scene: Scene, dt: float) -> None:
        dt = min(max(float(dt), 0.0), 0.05)
        if dt == 0.0:
            return

        for obj in scene.objects:
            body = obj.rigid_body
            if body.gravity_enabled:
                body.velocity += self.gravity * dt
            obj.transform.position += body.velocity * dt

            obj.transform.rotation += body.angular_velocity * dt
            self._resolve_ground_collision(obj)

        for i, first in enumerate(scene.objects):
            for second in scene.objects[i + 1 :]:
                self._resolve_object_collision(first, second)

    def _resolve_ground_collision(self, obj: SceneObject) -> None:
        radius = self.support_radius(obj)
        lowest = float(obj.transform.position[1] - radius)
        if lowest >= self.ground_y:
            return

        penetration = self.ground_y - lowest
        obj.transform.position[1] += penetration
        body = obj.rigid_body
        if body.velocity[1] < 0.0:
            body.velocity[1] = -body.velocity[1] * body.restitution
            if abs(body.velocity[1]) < 0.15:
                body.velocity[1] = 0.0
            body.velocity[0] *= body.friction
            body.velocity[2] *= body.friction

    def _resolve_object_collision(self, first: SceneObject, second: SceneObject) -> None:
        delta = second.transform.position - first.transform.position
        distance = float(np.linalg.norm(delta))
        if distance < 1e-6:
            delta = np.array([1.0, 0.0, 0.0], dtype=float)
            distance = 1.0

        combined_radius = self.support_radius(first) + self.support_radius(second)
        if distance >= combined_radius:
            return

        normal = delta / distance
        penetration = combined_radius - distance
        inverse_a = first.rigid_body.inverse_mass
        inverse_b = second.rigid_body.inverse_mass
        inverse_sum = inverse_a + inverse_b
        if inverse_sum == 0.0:
            return

        correction = normal * (penetration / inverse_sum)
        first.transform.position -= correction * inverse_a
        second.transform.position += correction * inverse_b

        relative_velocity = second.rigid_body.velocity - first.rigid_body.velocity
        separating_speed = float(np.dot(relative_velocity, normal))
        if separating_speed >= 0.0:
            return

        restitution = min(first.rigid_body.restitution, second.rigid_body.restitution)
        impulse_magnitude = -(1.0 + restitution) * separating_speed / inverse_sum
        impulse = normal * impulse_magnitude
        first.rigid_body.velocity -= impulse * inverse_a
        second.rigid_body.velocity += impulse * inverse_b

    @staticmethod
    def support_radius(obj: SceneObject) -> float:
        scale = obj.transform.scale
        if isinstance(obj, Sphere):
            return 0.32 * float(np.max(scale))
        if isinstance(obj, (Cube, Pyramid)):
            return 0.35 * float(np.max(scale))
        return 0.32 * float(np.max(scale))
