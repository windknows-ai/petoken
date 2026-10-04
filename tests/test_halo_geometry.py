"""Projected halo fit and closed-cycle interaction safety."""
import math
import unittest

import halo_geometry as halo


SCREEN = (0, 0, 1919, 1079)


class HaloGeometryTests(unittest.TestCase):
    def test_all_edges_corners_scales_counts_keep_every_phase_valid(self):
        for scale in (0.5, 1.0, 1.5):
            width, height = 272 * scale, 330 * scale
            xs = (0, (1920 - width) / 2, 1920 - width)
            ys = (0, (1080 - height) / 2, 1080 - height)
            for ix, x in enumerate(xs):
                for iy, y in enumerate(ys):
                    if ix == iy == 1:
                        continue
                    pose = halo.fit_pose((x, y, width, height), SCREEN)
                    bounds = halo.projected_bounds(pose)
                    self.assertGreaterEqual(bounds[0], SCREEN[0] - 1e-9)
                    self.assertGreaterEqual(bounds[1], SCREEN[1] - 1e-9)
                    self.assertLessEqual(bounds[2], SCREEN[2] + 1 + 1e-9)
                    self.assertLessEqual(bounds[3], SCREEN[3] + 1 + 1e-9)
                    for count in (1, 3, 8):
                        offsets = halo.phase_offsets(range(count))
                        seen = set()
                        for degree in range(360):
                            phase = math.radians(degree)
                            centers = {key: tuple(round(v) for v in
                                       halo.project(pose, phase + offset)[:2])
                                       for key, offset in offsets.items()}
                            self.assertTrue(halo.frame_valid(centers, SCREEN),
                                            (scale, ix, iy, count, degree, centers))
                            seen.add(tuple(centers.values()))
                        self.assertGreater(len(seen), 300)

    def test_projection_has_tilt_depth_and_periodic_continuity(self):
        pose = halo.fit_pose((824, 375, 272, 330), SCREEN)
        self.assertNotEqual(pose.tilt, 0)
        self.assertNotEqual(halo.project(pose, 0)[1], pose.cy)
        self.assertGreater(halo.project(pose, math.pi / 2)[2], 0)
        self.assertLess(halo.project(pose, 3 * math.pi / 2)[2], 0)
        for index in range(32):
            angle = index * math.tau / 32
            for first, second in zip(halo.project(pose, angle),
                                     halo.project(pose, angle + math.tau)):
                self.assertAlmostEqual(first, second)

    def test_centered_pose_stays_close_and_fit_moves_only_when_needed(self):
        pet = (824, 375, 272, 330)
        pose = halo.fit_pose(pet, SCREEN)
        self.assertEqual(pose.cx, pet[0] + pet[2] / 2)
        self.assertGreater(pose.cy, pet[1] + pet[3] * 0.30)
        self.assertLess(pose.cy, pet[1] + pet[3] * 0.75)
        self.assertLess(2 * pose.rx, pet[2] * 1.4)
        self.assertLess(2 * pose.ry, pet[3])
        side = halo.fit_pose((0, 375, 272, 330), SCREEN)
        self.assertEqual(side.cy, pose.cy)
        self.assertGreater(side.cx, 136)
        self.assertAlmostEqual(halo.projected_bounds(side)[0], 0)

    def test_small_workarea_shrinks_art_axes_preserving_hit_floor(self):
        normal = halo.fit_pose((0, 0, 408, 495), SCREEN)
        screen = (-200, -100, 99, 199)
        pose = halo.fit_pose((-200, -100, 408, 495), screen)
        self.assertLess(pose.rx, normal.rx)
        self.assertGreaterEqual(min(pose.rx, pose.ry), halo.MIN_AXIS)
        for degree in range(720):
            centers = {slot: tuple(round(v) for v in halo.project(
                       pose, math.radians(degree / 2) + offset)[:2])
                       for slot, offset in halo.phase_offsets(range(8)).items()}
            self.assertTrue(halo.frame_valid(centers, screen), degree)

    def test_physically_impossible_workarea_is_explicit(self):
        with self.assertRaisesRegex(ValueError, 'distinct halo hit targets'):
            halo.fit_pose((0, 0, 272, 330), (0, 0, 179, 179))
        for pet, screen in (((0, 0, 0, 330), SCREEN),
                            ((0, 0, math.inf, 330), SCREEN),
                            ((0, 0, 272, 330), (100, 0, 0, 500))):
            with self.assertRaises(ValueError):
                halo.fit_pose(pet, screen)

    def test_slot_offsets_are_identity_stable_and_empty_safe(self):
        self.assertEqual(halo.phase_offsets([8, 2, 5]), halo.phase_offsets([5, 8, 2]))
        self.assertEqual(list(halo.phase_offsets([8, 2, 5])), [2, 5, 8])
        self.assertEqual(halo.phase_offsets([]), {})
        self.assertEqual(halo.phase_offsets([42]), {42: 0})
        self.assertEqual(halo.phase_offsets([5, 5]), {5: 0})

    def test_pose_is_immutable_and_footprint_matches_number_contract(self):
        pose = halo.fit_pose((824, 375, 272, 330), SCREEN)
        with self.assertRaises(AttributeError):
            pose.cx = 0
        disc, number = halo.interactive_footprint(100, 100)
        self.assertEqual(disc, (100, 100, 22))
        self.assertEqual(number, (91, 127, 18, 14))
        self.assertFalse(halo.frame_valid({0: (100, 100), 1: (100, 100)}, SCREEN))
        self.assertFalse(halo.frame_valid({0: (10, 100)}, SCREEN))

    def test_worst_quantized_spacing_clears_disc_and_furthest_label_corner(self):
        required = (halo.HIT_RADIUS + halo.PAIR_MARGIN
                    + math.hypot(halo.LABEL_WIDTH / 2, halo.LABEL_TOP + halo.LABEL_HEIGHT))
        for scale in (0.5, 1.0, 1.5):
            pose = halo.fit_pose((0, 0, 272 * scale, 330 * scale), SCREEN)
            minimum = math.inf
            for step in range(720):
                phase = step * math.tau / 720
                centers = [tuple(round(v) for v in halo.project(pose, phase + offset)[:2])
                           for offset in halo.phase_offsets(range(8)).values()]
                minimum = min(minimum, *(math.dist(first, second)
                              for i, first in enumerate(centers)
                              for second in centers[i + 1:]))
            self.assertGreater(minimum, required, scale)
