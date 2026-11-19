import json
import struct

import numpy as np

from .scene import Scene
from .scene_objects import Pyramid, Sphere


class GLTFExporter:
    def export(self, scene: Scene, path: str) -> None:
        positions = []
        indices = []
        nodes = []
        meshes = []

        for i, obj in enumerate(scene.objects):
            verts, tris = _mesh_for(obj)
            verts = verts + obj.transform.position.reshape(1, 3)
            start_v = len(positions)
            start_i = len(indices)
            positions.extend(verts.tolist())
            indices.extend((np.array(tris) + start_v).reshape(-1).tolist())
            count_i = len(tris) * 3
            meshes.append({"primitives": [{"attributes": {"POSITION": 0}, "indices": 1}]})
            # Each object gets its own mesh accessor pair via one shared buffer; use per-mesh views.
            nodes.append({"mesh": i, "name": obj.name})
            # Store ranges to rebuild accessors per mesh below
            meshes[-1]["_range"] = (start_v, len(verts), start_i, count_i)

        if not positions:
            positions = [[0, 0, 0]]
            indices = [0, 0, 0]
            nodes = [{"mesh": 0, "name": "empty"}]
            meshes = [{"primitives": [{"attributes": {"POSITION": 0}, "indices": 1}], "_range": (0, 1, 0, 3)}]

        pos = np.array(positions, dtype=np.float32)
        idx = np.array(indices, dtype=np.uint16)
        bin_blob = pos.tobytes() + idx.tobytes()
        index_offset = pos.nbytes

        accessors = []
        buffer_views = []
        final_meshes = []
        for mesh in meshes:
            sv, nv, si, ni = mesh["_range"]
            pos_off = sv * 12
            idx_off = index_offset + si * 2
            mins = pos[sv : sv + nv].min(axis=0).tolist()
            maxs = pos[sv : sv + nv].max(axis=0).tolist()
            bv_p = len(buffer_views)
            buffer_views.append({"buffer": 0, "byteOffset": pos_off, "byteLength": nv * 12, "target": 34962})
            acc_p = len(accessors)
            accessors.append(
                {"bufferView": bv_p, "componentType": 5126, "count": nv, "type": "VEC3", "min": mins, "max": maxs}
            )
            bv_i = len(buffer_views)
            buffer_views.append({"buffer": 0, "byteOffset": idx_off, "byteLength": ni * 2, "target": 34963})
            acc_i = len(accessors)
            accessors.append({"bufferView": bv_i, "componentType": 5123, "count": ni, "type": "SCALAR"})
            final_meshes.append({"primitives": [{"attributes": {"POSITION": acc_p}, "indices": acc_i}]})

        gltf = {
            "asset": {"version": "2.0", "generator": "Decahedron"},
            "scene": 0,
            "scenes": [{"nodes": list(range(len(nodes)))}],
            "nodes": nodes,
            "meshes": final_meshes,
            "buffers": [{"byteLength": len(bin_blob)}],
            "bufferViews": buffer_views,
            "accessors": accessors,
        }
        json_blob = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
        json_blob += b" " * ((4 - len(json_blob) % 4) % 4)
        bin_padded = bin_blob + b"\x00" * ((4 - len(bin_blob) % 4) % 4)

        with open(path, "wb") as f:
            f.write(struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(json_blob) + 8 + len(bin_padded)))
            f.write(struct.pack("<I4s", len(json_blob), b"JSON"))
            f.write(json_blob)
            f.write(struct.pack("<I4s", len(bin_padded), b"BIN\x00"))
            f.write(bin_padded)


def _mesh_for(obj):
    if isinstance(obj, Sphere):
        return _uv_sphere(0.32)
    if isinstance(obj, Pyramid):
        x = y = z = 0.35
        v = np.array(
            [
                [-x, -y, -z], [x, -y, -z], [x, -y, z], [-x, -y, z],
                [0.0, y, 0.0],
            ],
            dtype=float,
        )
        t = [(0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4), (0, 3, 2), (0, 2, 1)]
        return v, t
    return _box(np.full(3, 0.35))


def _box(s):
    x, y, z = s
    v = np.array(
        [
            [-x, -y, -z],
            [x, -y, -z],
            [x, y, -z],
            [-x, y, -z],
            [-x, -y, z],
            [x, -y, z],
            [x, y, z],
            [-x, y, z],
        ],
        dtype=float,
    )
    t = [
        (0, 1, 2), (0, 2, 3),
        (4, 6, 5), (4, 7, 6),
        (0, 4, 5), (0, 5, 1),
        (2, 6, 7), (2, 7, 3),
        (0, 3, 7), (0, 7, 4),
        (1, 5, 6), (1, 6, 2),
    ]
    return v, t


def _uv_sphere(radius, slices=12, stacks=8):
    verts = []
    for i in range(stacks + 1):
        phi = np.pi * i / stacks
        for j in range(slices):
            th = 2 * np.pi * j / slices
            verts.append(
                [
                    radius * np.sin(phi) * np.cos(th),
                    radius * np.cos(phi),
                    radius * np.sin(phi) * np.sin(th),
                ]
            )
    tris = []
    for i in range(stacks):
        for j in range(slices):
            a = i * slices + j
            b = i * slices + (j + 1) % slices
            c = (i + 1) * slices + j
            d = (i + 1) * slices + (j + 1) % slices
            if i != 0:
                tris.append((a, c, b))
            if i != stacks - 1:
                tris.append((b, c, d))
    return np.array(verts, dtype=float), tris
