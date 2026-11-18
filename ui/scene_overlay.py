"""Project camera-relative scene geometry onto a fitted video frame."""

from math import cos, sin

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


def _geometry(obj, size):
    position = obj.transform.position
    if position[2] <= 0:
        return None
    mesh = obj.get_mesh()
    if mesh["kind"] == "sphere":
        center = _project(position[None, :], size)[0]
        radius = min(size) * mesh["radius"] / position[2]
        return mesh, None, (center, radius)
    points = mesh["local_points"] @ PREVIEW_ROTATION.T
    # Preserve a perspective view of the faces at close range without letting
    # the mesh cross behind the projection plane as its on-screen size grows.
    points[:, 2] *= min(1.0, position[2] / 4.0)
    points += position
    if np.any(points[:, 2] <= 0):
        return None
    projected = _project(points, size)
    roll = obj.transform.rotation[2]
    if roll:
        center = _project(position[None, :], size)[0]
        c, s = cos(roll), sin(roll)
        projected = (projected - center) @ np.array([[c, -s], [s, c]]) + center
    return mesh, points, projected


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


def draw_scene(image, objects, selected=None):
    if not objects:
        return
    draw = ImageDraw.Draw(image)
    for obj in _back_to_front(objects):
        outline = SELECTED if obj is selected else OUTLINE
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
                         outline=outline, width=3 if obj is selected else 2)
            roll = obj.transform.rotation[2]
            mark_x, mark_y = x + 0.6 * radius * cos(roll), y - 0.6 * radius * sin(roll)
            mark = 0.07 * radius
            draw.ellipse((mark_x - mark, mark_y - mark, mark_x + mark, mark_y + mark),
                         fill=outline)
            continue

        pixels = [tuple(point) for point in projected]
        if "faces" in mesh:
            faces = sorted(mesh["faces"], key=lambda face: points[list(face), 2].mean(),
                           reverse=True)
            for face in faces:
                a, b, c = points[list(face[:3])]
                normal = np.cross(b - a, c - a)
                shade = 0.45 + 0.55 * abs(normal @ (0.36, 0.48, 0.8)) / max(
                    1e-8, np.linalg.norm(normal))
                color = tuple(int(channel * shade) for channel in obj.color)
                draw.polygon([pixels[i] for i in face], fill=color, outline=outline,
                             width=3 if obj is selected else 1)
        else:
            for a, b in mesh["edges"]:
                draw.line((pixels[a], pixels[b]), fill=outline, width=2)
