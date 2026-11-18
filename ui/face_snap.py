"""Align nearby faces using the camera-space solid meshes."""

from dataclasses import dataclass

import numpy as np

from scene_overlay import PREVIEW_ROTATION, rotation_angles, rotation_matrix, world_vertices


@dataclass(frozen=True)
class Face:
    vertices: np.ndarray
    center: np.ndarray
    normal: np.ndarray
    radius: float


def solid_faces(obj):
    mesh = obj.get_mesh()
    if "faces" not in mesh:
        return ()
    vertices = world_vertices(obj, mesh)
    inside = vertices.mean(axis=0)
    faces = []
    for indices in mesh.get("contact_faces", mesh["faces"]):
        points = vertices[list(indices)]
        center = points.mean(axis=0)
        normal = np.cross(points[1] - points[0], points[2] - points[0])
        length = np.linalg.norm(normal)
        if length <= 1e-8:
            continue
        normal /= length
        if normal @ (center - inside) < 0:
            normal *= -1
        faces.append(Face(points, center, normal,
                          float(np.max(np.linalg.norm(points - center, axis=1)))))
    return faces


def _basis(face, normal):
    tangent = face.vertices[1] - face.vertices[0]
    tangent /= np.linalg.norm(tangent)
    across = np.cross(normal, tangent)
    if across @ (face.vertices[:2].mean(axis=0) - face.center) < 0:
        tangent, across = -tangent, -across
    return np.array([tangent, across, normal])


def _fit_faces(source, target):
    source_basis = _basis(source, source.normal)
    target_basis = _basis(target, -target.normal)
    if max(len(source.vertices), len(target.vertices)) == 4:
        a, b, normal = target_basis
        target_basis = max((np.array([u, v, normal]) for u, v in
                            ((a, b), (b, -a), (-a, -b), (-b, a))),
                           key=lambda basis: np.trace(source_basis.T @ basis))

    src = (source.vertices - source.center) @ source_basis[:2].T
    dst = (target.vertices - target.center) @ target_basis[:2].T
    src_size, dst_size = np.ptp(src, axis=0), np.ptp(dst, axis=0)
    fit = np.eye(3)
    if len(src) == len(dst):
        src_edges = src[[1, -1]] - src[0]
        if np.linalg.det(src_edges) * np.linalg.det(dst[[1, -1]] - dst[0]) < 0:
            dst = dst[::-1]
        dst = min((np.roll(dst, i, axis=0) for i in range(len(dst))),
                  key=lambda points: np.sum((src / src_size - points / dst_size) ** 2))
        fit[:2, :2] = np.linalg.solve(src_edges, dst[[1, -1]] - dst[0])
    else:
        fit[:2, :2] = np.diag(dst_size / src_size)
    return source_basis.T @ fit @ source_basis, source_basis.T @ target_basis


def snap_faces(moving, objects, locked=None):
    """Fit the moving face and return the completed contact."""
    faces_by_object = {obj: solid_faces(obj) for obj in objects}
    if locked is not None:
        for pair in tuple(locked):
            a, ai, b, bi = pair
            a_faces, b_faces = faces_by_object.get(a, ()), faces_by_object.get(b, ())
            if ai >= len(a_faces) or bi >= len(b_faces):
                locked.remove(pair)
                continue
            source, target = a_faces[ai], b_faces[bi]
            if np.linalg.norm(source.center - target.center) > 0.85 * min(source.radius, target.radius):
                locked.remove(pair)
    fixed_faces = [(obj, faces) for obj, faces in faces_by_object.items() if obj not in moving]
    blocked_objects = {frozenset((pair[0], pair[2])) for pair in locked or ()}
    best = None
    best_score = float("inf")
    for moving_obj in moving:
        for mi, source in enumerate(faces_by_object[moving_obj]):
            for fixed_obj, faces in fixed_faces:
                if frozenset((moving_obj, fixed_obj)) in blocked_objects:
                    continue
                for fi, target in enumerate(faces):
                    pair = (moving_obj, mi, fixed_obj, fi)
                    alignment = -source.normal @ target.normal
                    if alignment < 0.40:
                        continue
                    reach = min(source.radius, target.radius) * 0.60
                    distance = np.linalg.norm(source.center - target.center)
                    if distance > reach:
                        continue
                    # Allow a little overlap before alignment, especially
                    # when the tip of a tilted pyramid reaches a face first.
                    if ((moving_obj.transform.position - target.center) @ target.normal < -0.5 * reach
                            or (fixed_obj.transform.position - source.center) @ source.normal < -0.5 * reach):
                        continue
                    score = distance / reach + 0.25 * (1 - alignment)
                    if score < best_score:
                        best = pair, source, target
                        best_score = score
    if best is None:
        return None

    pair, source, target = best
    resize, turn = _fit_faces(source, target)
    fitted = pair[0]
    adjustment = (fitted.transform.position - source.center) @ (resize - np.eye(3)) @ turn
    positions = [target.center + adjustment + (obj.transform.position - source.center) @ turn
                 for obj in moving]
    if any(position[2] <= 0 or not np.isfinite(position).all() for position in positions):
        return None
    fitted_basis = PREVIEW_ROTATION.T @ rotation_matrix(fitted.transform.rotation)
    fitted.transform.mesh_deformation[:] = (fitted.transform.mesh_deformation @ fitted_basis
                                            @ resize @ np.linalg.inv(fitted_basis))
    for obj, position in zip(moving, positions):
        obj.transform.position[:] = position
        obj.transform.rotation[:] = rotation_angles(rotation_matrix(obj.transform.rotation) @ turn)
    if locked is not None:
        locked.add(pair)
    return pair
