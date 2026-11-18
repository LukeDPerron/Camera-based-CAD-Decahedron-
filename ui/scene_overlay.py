"""Project camera-relative scene geometry onto a fitted video frame."""

from math import atan2, cos, hypot, sin

import numpy as np
import cv2
from PIL import ImageDraw


# Turn the default meshes slightly so their depth is visible head-on.
PREVIEW_ROTATION = np.array([
    [0.866, 0.0, 0.5],
    [0.171, 0.940, -0.296],
    [-0.470, 0.342, 0.814],
])
OUTLINE = (124, 243, 210)
SELECTED = (255, 194, 102)


def _project(points, size):
    width, height = size
    return (points[:, :2] / points[:, 2:] * (min(size), -min(size))
            + (width / 2, height / 2))


def shape_center(obj, size):
    center = _project(obj.transform.position[None, :], size)[0]
    return center[0] / size[0], center[1] / size[1]


def _tilt(points, rotation):
    pitch, yaw, _ = rotation
    if yaw:
        c, s = cos(yaw), sin(yaw)
        points = points @ np.array([[c, 0, -s], [0, 1, 0], [s, 0, c]])
    if pitch:
        c, s = cos(pitch), sin(pitch)
        points = points @ np.array([[1, 0, 0], [0, c, s], [0, -s, c]])
    return points


def rotation_matrix(rotation):
    """Return the camera-space rotation for row vectors, including roll."""
    roll = rotation[2]
    c, s = cos(roll), sin(roll)
    return _tilt(np.eye(3), rotation) @ np.array([[c, s, 0], [-s, c, 0], [0, 0, 1]])


def rotation_angles(matrix):
    """Convert a camera-space matrix back to the scene's pitch, yaw, and roll."""
    planar = hypot(matrix[0, 2], matrix[2, 2])
    pitch = atan2(matrix[1, 2], planar)
    if planar < 1e-8:
        return pitch, atan2(matrix[2, 0], matrix[0, 0]), 0.0
    return (pitch, atan2(-matrix[0, 2], matrix[2, 2]),
            atan2(-matrix[1, 0], matrix[1, 1]))


def world_vertices(obj, mesh):
    """Use the same solid orientation for display and face contact."""
    return (mesh["local_points"] @ PREVIEW_ROTATION.T
            @ rotation_matrix(obj.transform.rotation) + obj.transform.position)


def _geometry(obj, size):
    position = obj.transform.position
    if position[2] <= 0:
        return None
    mesh = obj.get_mesh()
    if mesh["kind"] == "sphere":
        center = _project(position[None, :], size)[0]
        radius = min(size) * mesh["radius"] / position[2]
        return mesh, None, (center, radius)
    points = world_vertices(obj, mesh)
    if np.min(points[:, 2]) < 0.15 * position[2]:
        # Compress depth for extreme close-ups so the outline stays visible.
        points[:, 2] = position[2] + (points[:, 2] - position[2]) * (
            0.85 * position[2] / (position[2] - np.min(points[:, 2])))
    return mesh, points, _project(points, size)


def _back_to_front(objects):
    return sorted(objects, key=lambda obj: obj.transform.position[2], reverse=True)


def pick_shape(objects, size, cursor):
    """Return the visible object under the normalized fingertip."""
    aim = (cursor[0] * size[0], cursor[1] * size[1])
    for obj in reversed(_back_to_front(objects)):
        geometry = _geometry(obj, size)
        if geometry is None:
            continue
        mesh, _, projected = geometry
        if mesh["kind"] == "sphere":
            center, radius = projected
            if np.linalg.norm(center - aim) <= radius:
                return obj
        elif cv2.pointPolygonTest(cv2.convexHull(projected.astype(np.float32)), aim, False) >= 0:
            return obj
    return None


def draw_scene(image, objects, selected=()):
    if not objects:
        return
    draw = ImageDraw.Draw(image)
    for obj in _back_to_front(objects):
        is_selected = obj in selected
        outline = SELECTED if is_selected else OUTLINE
        geometry = _geometry(obj, image.size)
        if geometry is None:
            continue
        mesh, points, projected = geometry
        if mesh["kind"] == "sphere":
            (x, y), radius = projected
            for step in range(12):
                amount = step / 12
                r = radius * (1 - amount)
                cx, cy = x - radius * amount * 0.35, y - radius * amount * 0.35
                color = tuple(min(255, int(c * (0.48 + amount))) for c in obj.color)
                draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color)
            draw.ellipse((x - radius, y - radius, x + radius, y + radius),
                         outline=outline, width=3 if is_selected else 2)
            roll = obj.transform.rotation[2]
            mx, my, mz = _tilt(np.array([0.6, 0.0, -0.8]), obj.transform.rotation)
            if mz < 0:
                mark_x = x + radius * (mx * cos(roll) - my * sin(roll))
                mark_y = y - radius * (mx * sin(roll) + my * cos(roll))
                mark = 0.07 * radius
                draw.ellipse((mark_x - mark, mark_y - mark, mark_x + mark, mark_y + mark),
                             fill=outline)
            continue

        pixels = [tuple(point) for point in projected]
        if "faces" in mesh:
            faces = sorted(mesh.get("contact_faces", mesh["faces"]),
                           key=lambda face: points[list(face), 2].mean(),
                           reverse=True)
            for face in faces:
                a, b, c = points[list(face[:3])]
                normal = np.cross(b - a, c - a)
                shade = 0.45 + 0.55 * abs(normal @ (0.36, 0.48, 0.8)) / max(
                    1e-8, np.linalg.norm(normal))
                color = tuple(int(channel * shade) for channel in obj.color)
                draw.polygon([pixels[i] for i in face], fill=color, outline=outline,
                             width=3 if is_selected else 1)
        else:
            for a, b in mesh["edges"]:
                draw.line((pixels[a], pixels[b]), fill=outline, width=2)
