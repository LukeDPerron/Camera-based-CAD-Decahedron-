"""Checks for camera-space face snapping."""

from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from face_snap import snap_faces, solid_faces
from src.scene_objects import Cube, Pyramid, Sphere


class FaceSnapTests(unittest.TestCase):
    def test_snap_matches_face_dimensions_for_different_sizes(self):
        for moving_type, fixed_type in ((Cube, Cube), (Pyramid, Cube), (Pyramid, Pyramid)):
            with self.subTest(moving=moving_type, fixed=fixed_type):
                moving, fixed = moving_type("Moving"), fixed_type("Fixed")
                moving.transform.scale[:] = (.55, .70, .85)
                source = solid_faces(moving)[0]
                fi, target = min(enumerate(solid_faces(fixed)),
                                 key=lambda item: item[1].normal @ source.normal)
                moving.transform.position += target.center - source.center + .08 * target.normal
                self.assertEqual(snap_faces([moving], [moving, fixed]), (moving, 0, fixed, fi))
                fitted = solid_faces(moving)[0]
                tangent = target.vertices[1] - target.vertices[0]
                tangent /= np.linalg.norm(tangent)
                basis = np.array([tangent, np.cross(target.normal, tangent)])
                np.testing.assert_allclose(np.ptp(fitted.vertices @ basis.T, axis=0),
                                           np.ptp(target.vertices @ basis.T, axis=0), atol=1e-8)
                if len(fitted.vertices) == len(target.vertices):
                    for point in fitted.vertices:
                        self.assertLess(np.min(np.linalg.norm(target.vertices - point, axis=1)), 1e-8)

    def test_every_pyramid_face_snaps_in_both_directions(self):
        for moving_type, fixed_type in ((Pyramid, Cube), (Cube, Pyramid), (Pyramid, Pyramid)):
            for pyramid_index in range(5):
                with self.subTest(moving=moving_type, fixed=fixed_type, face=pyramid_index):
                    moving, fixed = moving_type("Moving"), fixed_type("Fixed")
                    moving_faces, fixed_faces = solid_faces(moving), solid_faces(fixed)
                    self.assertEqual(len(moving_faces if moving_type is Pyramid else fixed_faces), 5)
                    if moving_type is Pyramid:
                        mi = pyramid_index
                        fi = min(range(len(fixed_faces)),
                                 key=lambda i: fixed_faces[i].normal @ moving_faces[mi].normal)
                    else:
                        fi = pyramid_index
                        mi = min(range(len(moving_faces)),
                                 key=lambda i: moving_faces[i].normal @ fixed_faces[fi].normal)
                    source, target = moving_faces[mi], fixed_faces[fi]
                    moving.transform.position += target.center - source.center + .08 * target.normal
                    locked = set()
                    pair = (moving, mi, fixed, fi)
                    self.assertEqual(snap_faces([moving], [moving, fixed], locked), pair)
                    aligned = solid_faces(moving)[mi]
                    np.testing.assert_allclose(aligned.center, target.center, atol=1e-8)
                    np.testing.assert_allclose(aligned.normal, -target.normal, atol=1e-8)
                    self.assertIsNone(snap_faces([moving], [moving, fixed], locked))
                    self.assertIn(pair, locked)
                    moving.transform.position += target.normal
                    self.assertIsNone(snap_faces([moving], [moving, fixed], locked))
                    self.assertNotIn(pair, locked)

    def test_snap_moves_the_group_without_changing_spacing(self):
        cube, pyramid, sphere = Cube("Fixed"), Pyramid("Moving"), Sphere("Group member")
        source = solid_faces(pyramid)[0]
        fixed_faces = solid_faces(cube)
        target = min(fixed_faces, key=lambda face: face.normal @ source.normal)
        pyramid.transform.position += target.center - source.center + .08 * target.normal
        sphere.transform.position[:] = pyramid.transform.position + np.array([0, 1, 0])
        self.assertIsNotNone(snap_faces([pyramid, sphere], [pyramid, sphere, cube]))
        self.assertAlmostEqual(np.linalg.norm(sphere.transform.position - pyramid.transform.position), 1)
        self.assertIsNone(snap_faces([sphere], [sphere, pyramid, cube]))
