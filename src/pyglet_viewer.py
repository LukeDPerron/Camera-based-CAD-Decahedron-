import math
import threading

import numpy as np
import pyglet
from pyglet.gl import GL_TRIANGLES
from pyglet.graphics import Batch, ShaderGroup
from pyglet.graphics.shader import Shader, ShaderProgram
from pyglet.math import Mat4, Vec3
from pyglet.window import key, mouse

from .gesture_event import ShapeType
from .physics import PhysicsWorld
from .scene import Scene
from .shape_factory import ShapeFactory
from .scene_objects import Cube, Cylinder, Pyramid, Sphere


VERTEX_SHADER = """
#version 330
in vec3 position;
in vec3 color;
uniform mat4 projection;
uniform mat4 view;
out vec3 vertex_color;
void main() {
    gl_Position = projection * view * vec4(position, 1.0);
    vertex_color = color;
}
"""

FRAGMENT_SHADER = """
#version 330
in vec3 vertex_color;
out vec4 final_color;
void main() {
    final_color = vec4(vertex_color, 1.0);
}
"""


def _sphere_vertices(radius, slices=16, stacks=10):
    vertices = []
    for i in range(stacks):
        phi0 = math.pi * i / stacks
        phi1 = math.pi * (i + 1) / stacks
        for j in range(slices):
            theta0 = 2.0 * math.pi * j / slices
            theta1 = 2.0 * math.pi * (j + 1) % slices

            def point(phi, theta):
                return (
                    radius * math.sin(phi) * math.cos(theta),
                    radius * math.cos(phi),
                    radius * math.sin(phi) * math.sin(theta),
                )

            a = point(phi0, theta0)
            b = point(phi1, theta0)
            c = point(phi1, theta1)
            d = point(phi0, theta1)
            vertices.extend(a + b + c)
            vertices.extend(a + c + d)
    return np.asarray(vertices, dtype=np.float32)


def _cube_vertices(scale):
    x, y, z = 0.35 * np.asarray(scale, dtype=float)
    corners = [
        (-x, -y, -z), (x, -y, -z), (x, y, -z), (-x, y, -z),
        (-x, -y, z), (x, -y, z), (x, y, z), (-x, y, z),
    ]
    faces = [
        (0, 1, 2), (0, 2, 3),
        (4, 6, 5), (4, 7, 6),
        (0, 4, 5), (0, 5, 1),
        (3, 2, 6), (3, 6, 7),
        (0, 3, 7), (0, 7, 4),
        (1, 5, 6), (1, 6, 2),
    ]
    vertices = []
    for face in faces:
        for index in face:
            vertices.extend(corners[index])
    return np.asarray(vertices, dtype=np.float32)


def _pyramid_vertices(scale):
    x, y, z = 0.35 * np.asarray(scale, dtype=float)
    points = np.asarray([
        [-x, -y, -z], [x, -y, -z], [x, -y, z], [-x, -y, z],
        [0.0, y, 0.0],
    ])
    faces = [(0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4), (0, 3, 2), (0, 2, 1)]
    vertices = np.asarray([points[index] for face in faces for index in face], dtype=np.float32)
    return vertices


def _cylinder_vertices(scale, slices=16):
    scale = np.asarray(scale, dtype=float)
    radius = 0.22 * float(np.mean(scale[:2]))
    height = 0.5 * scale[1]
    vertices = []
    for lower in (False, True):
        y = -height if not lower else height
        for i in range(slices):
            a = 2.0 * math.pi * i / slices
            b = 2.0 * math.pi * (i + 1) / slices
            if lower:
                vertices.extend((0.0, y, 0.0))
                vertices.extend((radius * math.cos(a), y, radius * math.sin(a)))
                vertices.extend((radius * math.cos(b), y, radius * math.sin(b)))
            else:
                vertices.extend((0.0, y, 0.0))
                vertices.extend((radius * math.cos(b), y, radius * math.sin(b)))
                vertices.extend((radius * math.cos(a), y, radius * math.sin(a)))
    for i in range(slices):
        a = 2.0 * math.pi * i / slices
        b = 2.0 * math.pi * (i + 1) / slices
        bottom_a = (radius * math.cos(a), -height, radius * math.sin(a))
        bottom_b = (radius * math.cos(b), -height, radius * math.sin(b))
        top_a = (radius * math.cos(a), height, radius * math.sin(a))
        top_b = (radius * math.cos(b), height, radius * math.sin(b))
        vertices.extend(bottom_a + top_a + bottom_b)
        vertices.extend(bottom_b + top_a + top_b)
    return np.asarray(vertices, dtype=np.float32)


class PygletSceneWindow(pyglet.window.Window):
    def __init__(self, scene: Scene, physics: PhysicsWorld | None = None):
        super().__init__(width=1280, height=720, caption="Decahedron 3D Scene", resizable=True)
        self.scene = scene
        self.physics = physics or PhysicsWorld()
        self.camera_yaw = 45.0
        self.camera_pitch = 25.0
        self.camera_distance = 8.0
        self.camera_target = np.array([0.0, 0.0, 0.0], dtype=float)
        self.paused = False
        self.lock = threading.RLock()
        vertex_shader = Shader(VERTEX_SHADER, "vertex")
        fragment_shader = Shader(FRAGMENT_SHADER, "fragment")
        self.program = ShaderProgram(vertex_shader, fragment_shader)
        self.shader_group = ShaderGroup(self.program)

        pyglet.gl.glEnable(pyglet.gl.GL_DEPTH_TEST)
        pyglet.clock.schedule_interval(self._step, 1.0 / 60.0)

    def _step(self, dt):
        if not self.paused:
            with self.lock:
                self.physics.step(self.scene, dt)

    def _camera(self):
        yaw = math.radians(self.camera_yaw)
        pitch = math.radians(self.camera_pitch)
        offset = np.array([
            math.cos(pitch) * math.sin(yaw),
            math.sin(pitch),
            math.cos(pitch) * math.cos(yaw),
        ]) * self.camera_distance
        position = self.camera_target + offset
        view = Mat4.look_at(
            Vec3(*position),
            Vec3(*self.camera_target),
            Vec3(0.0, 1.0, 0.0),
        )
        projection = Mat4.perspective_projection(
            aspect=self.width / max(1.0, self.height),
            z_near=0.1,
            z_far=100.0,
            fov=60.0,
        )
        return projection, view

    def _vertices_for(self, obj):
        if isinstance(obj, Cube):
            local = _cube_vertices(obj.transform.scale)
        elif isinstance(obj, Sphere):
            radius = 0.32 * float(np.max(obj.transform.scale))
            local = _sphere_vertices(radius)
        elif isinstance(obj, Pyramid):
            local = _pyramid_vertices(obj.transform.scale)
        elif isinstance(obj, Cylinder):
            local = _cylinder_vertices(obj.transform.scale)
        else:
            return np.empty((0, 3), dtype=np.float32)
        return local + obj.transform.position.astype(np.float32)

    def on_draw(self):
        self.clear()
        projection, view = self._camera()
        batch = Batch()
        with self.lock:
            objects = list(self.scene.objects)
            selected = self.scene.selected

        for obj in objects:
            vertices = self._vertices_for(obj)
            if len(vertices) == 0:
                continue
            if obj is selected:
                color = (1.0, 0.82, 0.2)
            else:
                color = tuple(channel / 255.0 for channel in obj.color)
            vertex_count = len(vertices)
            colors = np.tile(np.asarray(color, dtype=np.float32), (vertex_count, 1)).reshape(-1)
            batch.add(
                vertex_count,
                GL_TRIANGLES,
                self.shader_group,
                ("position3f", tuple(float(value) for value in vertices.reshape(-1))),
                ("color3f", tuple(float(value) for value in colors)),
            )

        pyglet.gl.glEnable(pyglet.gl.GL_DEPTH_TEST)
        self.program["projection"] = projection
        self.program["view"] = view
        batch.draw()

    def on_key_press(self, symbol, modifiers):
        if symbol == key._1:
            self.scene.add(ShapeFactory.create(ShapeType.CUBE))
        elif symbol == key._2:
            self.scene.add(ShapeFactory.create(ShapeType.SPHERE))
        elif symbol == key._3:
            self.scene.add(ShapeFactory.create(ShapeType.PYRAMID))
        elif symbol == key.G:
            for obj in self.scene.objects:
                obj.rigid_body.gravity_enabled = not obj.rigid_body.gravity_enabled
        elif symbol == key.P:
            self.paused = not self.paused
        elif symbol == key.DELETE:
            if self.scene.selected:
                self.scene.objects.remove(self.scene.selected)
                self.scene.selected = self.scene.objects[-1] if self.scene.objects else None

    def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        if buttons & mouse.LEFT:
            self.camera_yaw -= dx * 0.35
            self.camera_pitch = max(-80.0, min(80.0, self.camera_pitch + dy * 0.35))

    def on_mouse_scroll(self, x, y, scroll_x, scroll_y):
        self.camera_distance = max(2.0, min(30.0, self.camera_distance - scroll_y))


def run(scene: Scene | None = None, physics: PhysicsWorld | None = None) -> None:
    PygletSceneWindow(scene or Scene(), physics)
    pyglet.app.run()


if __name__ == "__main__":
    run()
