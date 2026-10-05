"""Human-reported V1.4 scene and overflow regressions on native Qt."""
from pathlib import Path
import tempfile
import sys
import unittest
from unittest.mock import patch

from PySide6.QtCore import QPoint, QRect, QRectF, Qt
from PySide6.QtWidgets import QApplication

import halo_geometry
import theme
from pet import DesktopPet
from tools.preview_v1_3 import fixture_tasks
from widget import Panel


class SceneV14Tests(unittest.TestCase):
    def test_pager_buttons_fit_when_resting_focused_and_pressed(self):
        from PySide6.QtTest import QTest
        self.apply(24)
        self.manager.set_page(1)
        pager = self.manager.page_controls
        for button in [self.manager.page_previous, self.manager.page_next]:
            for state in ['resting', 'focused', 'pressed']:
                with self.subTest(state=state):
                    if state == 'focused':
                        button.setFocus()
                    elif state == 'pressed':
                        QTest.mousePress(button, Qt.LeftButton)
                    self.app.processEvents()
                    self.assertTrue(pager.rect().contains(button.geometry()),
                                    (pager.rect(), button.geometry()))
                    if state == 'pressed':
                        QTest.mouseRelease(button, Qt.LeftButton)
        self.assertEqual(pager.size().width(), 168)
        self.assertEqual(pager.size().height(), 32)

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.pref_patch = patch('widget.PREF_DIR', Path(self.temp.name))
        self.pref_patch.start()
        self.panel = Panel(live=False)
        self.panel.pet = self.pet = DesktopPet(self.panel)
        self.pet.activity_timer.stop()
        self.pet.timer.stop()
        self.pet.show()
        self.manager = self.panel.task_manager

    def tearDown(self):
        self.manager.shutdown()
        self.panel.clock.stop()
        self.panel.closing = True
        self.panel.close()
        self.pet.close()
        self.panel.tray.hide()
        self.app.processEvents()
        self.pref_patch.stop()
        self.temp.cleanup()

    def apply(self, count, generation=1):
        self.manager.apply_snapshot(fixture_tasks(count), generation=generation)
        self.app.processEvents()

    def assert_centered(self):
        pose = self.manager._halo_pose
        self.assertAlmostEqual(pose.cx, self.pet.x() + self.pet.width() / 2, delta=1)
        self.assertAlmostEqual(pose.cy, self.pet.y() + self.pet.height() * .60, delta=1)

    def test_all_edges_move_whole_centered_composition(self):
        self.apply(8)
        r = self.pet.screen().availableGeometry()
        for x in (r.left(), r.right() - self.pet.width() + 1):
            for y in (r.top(), r.bottom() - self.pet.height() + 1):
                self.pet.move_clamped(QPoint(x, y))
                self.assert_centered()
                centers = {k: (w.x() + 56, w.y() + 48) for k, w in self.manager._windows.items()}
                self.assertTrue(halo_geometry.frame_valid(centers, (r.left(), r.top(), r.right(), r.bottom())))

    def test_hide_usage_hub_preserves_ring_and_stars(self):
        self.apply(3)
        self.panel.show()
        self.panel.hide_to_tray()
        self.assertTrue(self.manager._visible)
        self.assertTrue(self.manager.trail_overlay.isVisible())
        self.assertTrue(all(w.isVisible() for w in self.manager._windows.values()))

    @unittest.skipUnless(sys.platform == 'win32', 'Windows native occlusion')
    def test_pet_raise_repairs_front_ring_even_without_depth_crossing(self):
        from tests.test_halo_scene import HaloSceneTests
        self.apply(3)
        self.pet.raise_()
        self.app.processEvents()
        self.manager._halo_commit(0, record=False)
        windows = self.manager.capture_windows()
        ranks = HaloSceneTests.native_ranks(self, windows)
        order = [ranks[int(w.winId())] for w in windows]
        self.assertEqual(order, sorted(order, reverse=True))

    def test_resize_updates_without_task_publication(self):
        self.apply(3)
        for scale in (50, 150, 100):
            self.pet.apply_pet_scale(scale)
            self.assert_centered()
            self.assertEqual(self.manager._last_pet_rect, (self.pet.x(), self.pet.y(), self.pet.width(), self.pet.height()))
            self.assertTrue(self.manager.trail_overlay.isVisible())

    def test_empty_source_keeps_decorative_ring_without_inventing_stars(self):
        self.apply(0)
        self.assertEqual(self.manager.window_count(), 0)
        self.assertTrue(self.manager.trail_overlay.isVisible())
        self.assertFalse(self.manager.trail_overlay.stars)

    def test_all_24_tasks_accessible_in_safe_pages_with_stable_labels(self):
        self.apply(24)
        self.assertLessEqual(self.manager.window_count(), 8)
        self.assertEqual(self.manager.total_task_count(), 24)
        self.assertEqual(self.manager.page_count, 3)
        labels = dict(self.manager._labels)
        visited = set()
        for page in range(3):
            self.manager.set_page(page)
            self.assertEqual(self.manager.window_count(), 8)
            visited.update(self.manager.window_identities())
            self.assertEqual(self.manager._labels, labels)
        self.assertEqual(visited, set(self.manager.task_identities()))
        key = self.manager.task_identities()[0]
        self.manager.activate_task(key)
        self.assertEqual(self.manager.expanded_identity, key)
        self.assertEqual(self.manager.page_index, 0)

    def test_explicit_ring_disable_survives_refresh_and_hub_operations(self):
        self.panel.prefs['star_ring_enabled'] = False
        self.apply(3)
        self.panel.show()
        self.panel.hide_to_tray()
        self.apply(4, generation=2)
        self.assertFalse(self.manager._visible)
        self.assertFalse(self.manager.trail_overlay.isVisible())
        self.assertTrue(all(not w.isVisible() for w in self.manager._windows.values()))

    def test_same_task_open_reverses_current_close_frame(self):
        self.apply(3)
        key = self.manager.window_identities()[0]
        self.manager.orb_activated(key)
        animation = self.manager.detail_transition.animation
        animation.setCurrentTime(220)
        self.manager.collapse_detail()
        animation.setCurrentTime(80)
        before = self.manager.detail_transition.overlay.progress
        self.manager.orb_activated(key)
        self.assertAlmostEqual(self.manager.detail_transition.overlay.progress, before)

    def test_pager_does_not_cover_ring_hits_or_number_badges(self):
        self.apply(24)
        screen = self.pet.screen().availableGeometry()
        for scale in (50, 75, 100, 150):
            self.pet.apply_pet_scale(scale)
            for point in (screen.center(), screen.topLeft(), screen.bottomRight()):
                self.pet.move_clamped(point)
                left, top, right, bottom = halo_geometry.projected_bounds(self.manager._halo_pose)
                bounds = QRectF(left, top, right - left, bottom - top)
                pager = QRectF(self.manager.page_controls.geometry())
                self.assertFalse(pager.intersects(bounds), (scale, pager, bounds))
                self.assertTrue(QRectF(screen).contains(pager))

    def test_pager_has_opaque_readable_surface_and_transparent_rounded_corners(self):
        self.apply(24)
        pager = self.manager.page_controls
        image = pager.grab().toImage()
        dpr = image.devicePixelRatio()
        background = image.pixelColor(round(84 * dpr), round(6 * dpr))
        self.assertGreater(background.alpha(), 240)
        self.assertEqual(background.name(), theme.SURFACE_TOP.lower())
        from tests.test_companion_theme import contrast
        self.assertGreaterEqual(contrast(theme.INK, background.name()), 4.5)
        self.assertEqual(image.pixelColor(0, 0).alpha(), 0)

    def test_workarea_change_reclamps_cached_composition_while_motion_off(self):
        self.apply(8)
        screen = self.pet.screen()
        r = screen.availableGeometry()
        self.pet.move_clamped(QPoint(r.right() - self.pet.width(), r.center().y()))
        self.panel.prefs['pet_motion'] = False
        reduced = QRect(r.left(), r.top(), r.width() - 48, r.height())
        with patch.object(screen, 'availableGeometry', return_value=reduced):
            pet_rect, screen_rect = self.manager._anchor()
            self.assert_centered()
            self.assertEqual(pet_rect, (self.pet.x(), self.pet.y(), self.pet.width(), self.pet.height()))
            self.assertTrue(halo_geometry.frame_valid(
                {k: (w.x() + 56, w.y() + 48) for k, w in self.manager._windows.items()}, screen_rect))

    def test_retire_or_disable_during_close_cancels_snapshot(self):
        self.apply(3)
        key = self.manager.window_identities()[0]
        for index, operation in enumerate(('retire', 'disable', 'move')):
            self.manager.set_visible(True)
            self.apply(3, generation=10 + index * 2)
            self.manager.orb_activated(key)
            self.manager.detail_transition.animation.setCurrentTime(220)
            self.manager.collapse_detail()
            self.assertTrue(self.manager.detail_transition.running)
            if operation == 'retire':
                self.apply(0, generation=11 + index * 2)
            elif operation == 'disable':
                self.manager.set_visible(False)
            else:
                self.pet.move_clamped(self.pet.pos() + QPoint(-10, -10))
            self.assertFalse(self.manager.detail_transition.running)
            self.assertFalse(self.manager.detail_transition.overlay.isVisible())


if __name__ == '__main__':
    unittest.main()
