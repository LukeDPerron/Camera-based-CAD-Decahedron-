import math
import threading
import json
import os
import tempfile

import numpy as np
import pyglet
from pyglet.gl import GL_BLEND, GL_DEPTH_TEST, GL_LINES, GL_TRIANGLES, glBlendFunc, GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA
from pyglet.graphics import Batch, ShaderGroup
from pyglet.graphics.shader import Shader, ShaderProgram
from pyglet.math import Mat4, Vec3
from pyglet.window import key, mouse

from .scene import Scene
from .shape_factory import ShapeFactory
from .scene_objects import Cube, Pyramid, Sphere
from .shape_types import ShapeType


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
    return np.asarray(vertices, dtype=np.float32).reshape(-1, 3)


def _cube_vertices():
    x = y = z = 0.35
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
    return np.asarray(vertices, dtype=np.float32).reshape(-1, 3)


def _grid_vertices(size=10.0, spacing=1.0, y=-2.0):
    vertices = []
    limit = int(size / spacing)
    for i in range(-limit, limit + 1):
        offset = i * spacing
        vertices.extend((-size, y, offset))
        vertices.extend((size, y, offset))
        vertices.extend((-size, y, offset))
        vertices.extend((offset, y, -size))
        vertices.extend((offset, y, size))
    return np.asarray(vertices, dtype=np.float32).reshape(-1, 3)


def _pyramid_vertices():
    x = y = z = 0.35
    points = np.asarray([
        [-x, -y, -z], [x, -y, -z], [x, -y, z], [-x, -y, z],
        [0.0, y, 0.0],
    ])
    faces = [(0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4), (0, 3, 2), (0, 2, 1)]
    vertices = np.asarray([points[index] for face in faces for index in face], dtype=np.float32)
    return vertices.reshape(-1, 3)


class PygletSceneWindow(pyglet.window.Window):
    def __init__(self, scene: Scene):
        super().__init__(width=1280, height=720, caption="Decahedron 3D Scene", resizable=True)
        self.scene = scene
        self.camera_yaw = 45.0
        self.camera_pitch = 25.0
        self.camera_distance = 8.0
        self.camera_target = np.array([0.0, 0.0, 0.0], dtype=float)
        self.lock = threading.RLock()
        vertex_shader = Shader(VERTEX_SHADER, "vertex")
        fragment_shader = Shader(FRAGMENT_SHADER, "fragment")
        self.program = ShaderProgram(vertex_shader, fragment_shader)
        self.shader_group = ShaderGroup(self.program)

        pyglet.gl.glEnable(pyglet.gl.GL_DEPTH_TEST)
        self.help_label = pyglet.text.Label(
            "Press 1 = Cube  |  2 = Sphere  |  3 = Pyramid",
            font_name="Arial",
            font_size=16,
            x=20,
            y=20,
            color=(255, 255, 255, 255),
            anchor_x="left",
            anchor_y="bottom",
            batch=None,
        )
        self._shape_command_path = os.path.join(
            tempfile.gettempdir(), "decahedron_shape_commands.json"
        )
        self._shape_command_mtime = None
        pyglet.clock.schedule_interval(self._poll_shape_commands, 0.05)

    def _poll_shape_commands(self, dt):
        try:
            mtime = os.path.getmtime(self._shape_command_path)
        except FileNotFoundError:
            return
        if mtime == self._shape_command_mtime:
            return
        self._shape_command_mtime = mtime

        try:
            with open(self._shape_command_path, "r", encoding="utf-8") as command_file:
                command = json.load(command_file)
        except (OSError, json.JSONDecodeError):
            return

        shape = command.get("shape")
        shape_type = {
            "Cube": ShapeType.CUBE,
            "Sphere": ShapeType.SPHERE,
            "Pyramid": ShapeType.PYRAMID,
        }.get(shape)
        if shape_type is not None:
            with self.lock:
                self.scene.add(ShapeFactory.create(shape_type))
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
            local = _cube_vertices()
        elif isinstance(obj, Sphere):
            local = _sphere_vertices(0.32)
        elif isinstance(obj, Pyramid):
            local = _pyramid_vertices()
        else:
            return np.empty((0, 3), dtype=np.float32)
        return local + obj.transform.position.astype(np.float32)

    def on_draw(self):
        self.clear()
        projection, view = self._camera()
        batch = Batch()
        grid = _grid_vertices()
        grid_colors = np.tile(
            np.asarray((0.35, 0.45, 0.55), dtype=np.float32),
            (len(grid), 1),
        ).reshape(-1)
        self.program.vertex_list(
            len(grid),
            GL_LINES,
            batch=batch,
            group=self.shader_group,
            position=("f", tuple(float(value) for value in grid.reshape(-1))),
            color=("f", tuple(float(value) for value in grid_colors)),
        )
        with self.lock:
            objects = list(self.scene.objects)

        for obj in objects:
            vertices = self._vertices_for(obj)
            if len(vertices) == 0:
                continue
            color = tuple(channel / 255.0 for channel in obj.color)
            vertex_count = len(vertices)
            colors = np.tile(np.asarray(color, dtype=np.float32), (vertex_count, 1)).reshape(-1)
            self.program.vertex_list(
                vertex_count,
                GL_TRIANGLES,
                batch=batch,
                group=self.shader_group,
                position=("f", tuple(float(value) for value in vertices.reshape(-1))),
                color=("f", tuple(float(value) for value in colors)),
            )

        pyglet.gl.glEnable(pyglet.gl.GL_DEPTH_TEST)
        self.program["projection"] = projection
        self.program["view"] = view
        batch.draw()

        pyglet.gl.glDisable(GL_DEPTH_TEST)
        pyglet.gl.glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        self.help_label.draw()
        pyglet.gl.glDisable(GL_BLEND)
        pyglet.gl.glEnable(GL_DEPTH_TEST)

    def on_key_press(self, symbol, modifiers):
        if symbol == key._1:
            self.scene.add(ShapeFactory.create(ShapeType.CUBE))
        elif symbol == key._2:
            self.scene.add(ShapeFactory.create(ShapeType.SPHERE))
        elif symbol == key._3:
            self.scene.add(ShapeFactory.create(ShapeType.PYRAMID))

    def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        if buttons & mouse.LEFT:
            self.camera_yaw -= dx * 0.35
            self.camera_pitch = max(-80.0, min(80.0, self.camera_pitch + dy * 0.35))

    def on_mouse_scroll(self, x, y, scroll_x, scroll_y):
        self.camera_distance = max(2.0, min(30.0, self.camera_distance - scroll_y))


def run(scene: Scene | None = None) -> None:
    PygletSceneWindow(scene or Scene())
    pyglet.app.run()


if __name__ == "__main__":
    run()
