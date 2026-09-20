import unittest

import pet_geometry as geometry


class PetGeometryTests(unittest.TestCase):
    def test_v1_baseline_reference_is_unchanged(self):
        self.assertEqual(geometry.BASELINE_WINDOW, (242, 378))
        self.assertEqual(geometry.BASELINE_SPRITE, (214, 290))
        self.assertEqual(geometry.BASELINE_SPRITE_Y, 82)

    def test_logical_character_is_half_baseline_size(self):
        self.assertEqual(geometry.CHARACTER_SCALE, 0.5)
        self.assertEqual((geometry.SPRITE_WIDTH, geometry.SPRITE_HEIGHT), (107, 145))
        self.assertLess(geometry.WINDOW_HEIGHT, geometry.BASELINE_WINDOW[1])
        self.assertEqual(geometry.window_size(), (242, 232))

    def test_single_shared_sprite_box_for_all_states(self):
        first = geometry.sprite_rect()
        for offset in (0, 1, -2, 3):
            x, y, w, h = geometry.sprite_rect(offset)
            self.assertEqual((x, w, h), (first[0], 107, 145))
            self.assertEqual(y, first[1] + offset)

    def test_feet_anchor_is_sprite_bottom_center(self):
        x, y, w, h = geometry.sprite_rect()
        ax, ay = geometry.anchor()
        self.assertEqual((ax, ay), (geometry.WINDOW_WIDTH // 2, y + h))
        self.assertEqual(geometry.anchor(), (121, 225))

    def test_bubble_stays_inside_window_above_sprite(self):
        bx, by, bw, bh = geometry.bubble_rect()
        ww, wh = geometry.window_size()
        self.assertGreaterEqual(bx, 0)
        self.assertGreaterEqual(by, 0)
        self.assertLessEqual(bx + bw, ww)
        self.assertLessEqual(by + bh, geometry.sprite_rect()[1])
        self.assertEqual((bw, bh), (240, 70))

    def test_reaction_pivot_is_inside_sprite_box(self):
        x, y, w, h = geometry.sprite_rect()
        px, py = geometry.REACTION_PIVOT
        self.assertTrue(x <= px <= x + w)
        self.assertTrue(y <= py <= y + h)

    def test_clamp_keeps_window_on_screen(self):
        screen = (0, 0, 1919, 1079)
        self.assertEqual(geometry.clamp_position(100, 100, 242, 232, screen), (100, 100))
        self.assertEqual(geometry.clamp_position(-5000, -5000, 242, 232, screen), (0, 0))
        self.assertEqual(geometry.clamp_position(5000, 5000, 242, 232, screen), (1919 - 242 + 1, 1079 - 232 + 1))

    def test_device_pixels_scale_linearly(self):
        self.assertEqual(geometry.device_pixels(107, 1.0), 107)
        self.assertEqual(geometry.device_pixels(107, 1.25), 134)
        self.assertEqual(geometry.device_pixels(107, 2.0), 214)

    def test_old_saved_position_stays_recoverable(self):
        # V1.0 default placement expressed as top-left; the smaller V1.1
        # window at the same point must remain fully visible.
        screen = (0, 0, 1919, 1079)
        old_default = (1919 - 280, 1079 - 400)
        ww, wh = geometry.window_size()
        x, y = geometry.clamp_position(*old_default, ww, wh, screen)
        self.assertEqual((x, y), old_default)
        self.assertLessEqual(x + ww, 1920)
        self.assertLessEqual(y + wh, 1080)


if __name__ == '__main__':
    unittest.main()
