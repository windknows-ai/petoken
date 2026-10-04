"""Native integration regressions for the default projected halo scene."""
import math
import sys
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from PySide6.QtCore import QEventLoop, QPoint, QTimer, Qt
from PySide6.QtWidgets import QApplication, QPlainTextEdit

import halo_geometry
from pet import DesktopPet
from widget import Panel, TaskPanelManager
from tests.test_ui import _codex_entry


SCREEN = (0, 0, 1919, 1079)
CENTER = (824, 375, 272, 330)
EDGES = {
    'left': (0, 375, 272, 330), 'right': (1648, 375, 272, 330),
    'top': (824, 0, 272, 330), 'bottom': (824, 750, 272, 330),
    'top_left': (0, 0, 272, 330), 'top_right': (1648, 0, 272, 330),
    'bottom_left': (0, 750, 272, 330),
    'bottom_right': (1648, 750, 272, 330),
}


class HaloSceneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.pref_patch = patch('widget.PREF_DIR', Path(self.temp.name))
        self.pref_patch.start()
        self.panel = Panel(live=False)
        self.panel.pet = DesktopPet(self.panel)
        self.panel.pet.activity_timer.stop()
        self.panel.pet.timer.stop()
        self.manager = self.panel.task_manager
        self.assertFalse(self.manager.legacy_exterior_motion)
        self.pet_rect = CENTER
        self.stamp = 1000.0
        self.generation = 0
        self.panel.prefs['pet_motion'] = True
        self.anchor_patch = patch.object(self.manager, '_anchor',
                                        side_effect=lambda: (self.pet_rect, SCREEN))
        self.anchor_patch.start()
        self.planner_patch = patch('widget._plan_parking_routes',
                                   side_effect=AssertionError('halo used exterior planner'))
        self.planner_patch.start()

    def tearDown(self):
        self.manager.shutdown()
        self.panel.pet.close()
        self.panel.tray.hide()
        if self.panel.analytics_window:
            self.panel.analytics_window.close()
        self.panel.closing = True
        self.panel.close()
        self.panel.deleteLater()
        self.app.processEvents()
        self.planner_patch.stop()
        self.anchor_patch.stop()
        self.pref_patch.stop()
        self.temp.cleanup()

    def tasks(self, numbers, total=110):
        return [_codex_entry('halo-%s' % n, total=total, model='gpt-6-sol')
                for n in numbers]

    def apply(self, numbers, total=110):
        self.generation += 1
        return self.manager.apply_snapshot(
            self.tasks(numbers, total), generation=self.generation,
            pet_rect=self.pet_rect, screen_rect=SCREEN)

    def positions(self):
        return {key: (orb.x(), orb.y())
                for key, orb in self.manager._windows.items()
                if key not in self.manager._ring_staged and orb.isVisible()}

    def assert_frame(self):
        positions = self.positions()
        self.assertEqual(set(positions),
                         set(self.manager._windows) - self.manager._ring_staged)
        centers = {key: (x + 56, y + 48) for key, (x, y) in positions.items()}
        self.assertTrue(halo_geometry.frame_valid(centers, SCREEN), centers)
        for key in positions:
            orb = self.manager._windows[key]
            self.assertTrue(orb.is_star_hit(QPoint(56, 48)))
            self.assertTrue(orb.is_star_hit(orb.number_label.geometry().center()))
            self.assertFalse(orb.is_star_hit(QPoint(0, 0)))
        for key in self.manager._ring_staged:
            self.assertFalse(self.manager._windows[key].isVisible())
        self.assertIsNone(self.manager._park_plan_job)
        self.assertIsNone(self.manager._park_plan_request)

    def step(self, dt=.04):
        before = self.positions()
        self.stamp += dt
        self.manager.tick_visual(self.stamp, pet_rect=self.pet_rect,
                                 screen_rect=SCREEN)
        after = self.positions()
        for key in before.keys() & after.keys():
            distance = sum(abs(a - b) for a, b in zip(before[key], after[key]))
            self.assertLessEqual(distance, 16, (key, before[key], after[key]))
        if self.manager._visible and self.manager._windows:
            self.assert_frame()
        return after

    def settle(self, limit=1200):
        for _ in range(limit):
            self.step()
            if not self.manager._halo_pending():
                return
        self.fail('halo pose/slot settlement did not finish within 48 active seconds')

    def test_center_shared_phase_depth_and_compact_layers(self):
        self.apply(range(8))
        self.step()
        start = self.manager._ring_t
        for _ in range(100):
            self.step()
        self.assertAlmostEqual(self.manager._ring_t - start, 4.0)
        self.assertEqual(self.manager._orbit_mode, ('halo',))
        self.assertFalse(self.manager.motion_timer.isActive())
        for key, offset in self.manager._halo_offsets.items():
            x, y, depth = halo_geometry.project(
                self.manager._halo_pose, self.manager._ring_t * math.tau / 24 + offset)
            orb = self.manager._windows[key]
            self.assertLessEqual(abs(orb.x() + 56 - x), .5)
            self.assertLessEqual(abs(orb.y() + 48 - y), .5)
            self.assertAlmostEqual(orb.depth, depth)
        layers = (self.manager.back_overlay, self.manager.trail_overlay)
        for layer in layers:
            self.assertTrue(layer.windowFlags() & Qt.WindowTransparentForInput)
            self.assertLess(layer.width() * layer.height(), 1920 * 1080 * .1)
            self.assertLessEqual(max(map(len, layer._trails.values())), layer.MAX_SAMPLES)
            self.assertFalse(layer.findChildren(QTimer))

    def test_anchor_changed_and_timer_only_geometry_follow_without_snap(self):
        self.apply(range(8))
        self.step()
        for target, notify in ((EDGES['top_left'], True),
                               (EDGES['bottom_right'], False), (CENTER, True)):
            before = self.positions()
            phase = self.manager._ring_t
            self.pet_rect = target
            if notify:
                self.manager.anchor_changed()
                self.assertEqual(self.positions(), before)
                self.assertEqual(self.manager._halo_target,
                                 halo_geometry.fit_pose(target, SCREEN))
            self.step()
            self.assertGreater(self.manager._ring_t, phase)
            self.settle()
            self.assertEqual(self.manager._halo_pose,
                             halo_geometry.fit_pose(target, SCREEN))
            for layer in (self.manager.back_overlay, self.manager.trail_overlay):
                self.assertLess(layer.width() * layer.height(), 1920 * 1080 * .5)

    def test_native_pet_move_event_updates_ordinary_anchor(self):
        self.apply(range(3))
        before = self.positions()
        self.anchor_patch.stop()
        self.panel.pet.show()
        self.panel.pet.move(300, 200)
        self.app.processEvents()
        actual_pet, actual_screen = self.manager._anchor()
        self.assertEqual(self.manager._halo_target,
                         halo_geometry.fit_pose(actual_pet, actual_screen))
        self.assertEqual(self.positions(), before)
        phase = self.manager._ring_t
        self.manager.tick_visual(self.stamp)
        self.manager.tick_visual(self.stamp + .04)
        self.assertGreater(self.manager._ring_t, phase)
        after = self.positions()
        for key in before:
            self.assertLessEqual(sum(abs(a - b) for a, b in
                                     zip(before[key], after[key])), 16)

    def test_intentional_drag_transports_attached_halo_without_phase_jump(self):
        self.apply(range(8))
        self.step()
        self.anchor_patch.stop()
        self.panel.pet.show()
        windows = dict(self.manager._windows)
        for point in (QPoint(50, 50), QPoint(600, 400), QPoint(800, 450),
                      QPoint(5000, 5000), QPoint(50, 5000), QPoint(5000, 50)):
            phase = self.manager._ring_t
            offsets = dict(self.manager._halo_offsets)
            self.panel.pet.move_clamped(point)
            self.app.processEvents()
            pet, screen = self.manager._anchor()
            self.assertEqual(self.manager._halo_pose, halo_geometry.fit_pose(pet, screen))
            self.assertEqual(self.manager._ring_t, phase)
            self.assertEqual(self.manager._halo_offsets, offsets)
            self.assertEqual(self.manager._windows, windows)
            self.assertFalse(self.manager.back_overlay._trails)
            self.assertFalse(self.manager.trail_overlay._trails)
            positions = self.positions()
            self.assertTrue(self.manager._nominal_valid(positions, pet, screen))
            # The scene is transported by the deliberate pointer command. Each
            # subsequent autonomous frame retains its separate 16px budget.
            self.stamp += .04
            self.manager.tick_visual(self.stamp, pet_rect=pet, screen_rect=screen)
            self.assertEqual(self.positions(), positions)
            self.stamp += .04
            self.manager.tick_visual(self.stamp, pet_rect=pet, screen_rect=screen)
            for key, pos in self.positions().items():
                self.assertLessEqual(sum(abs(a-b) for a,b in zip(pos, positions[key])), 16)

    def test_metadata_generations_and_membership_preserve_survivor_boundary(self):
        self.apply(range(8))
        for _ in range(40):
            self.step()
        windows = dict(self.manager._windows)
        slots = dict(self.manager._slots)
        labels = dict(self.manager._labels)
        before, phase = self.positions(), self.manager._ring_t
        for total in (120, 130, 140):
            self.apply(range(8), total)
            self.assertEqual(self.positions(), before)
            self.assertEqual(self.manager._ring_t, phase)
        self.manager.apply_snapshot([], generation=self.generation - 1,
                                    pet_rect=self.pet_rect, screen_rect=SCREEN)
        self.assertEqual(self.positions(), before)
        self.apply((1, 3, 6))
        for key in self.manager._windows:
            self.assertIs(self.manager._windows[key], windows[key])
            self.assertEqual(self.manager._slots[key], slots[key])
            self.assertEqual(self.manager._labels[key], labels[key])
            self.assertEqual(self.positions()[key], before[key])
        self.settle()
        before = self.positions()
        self.apply(range(8))
        self.assertTrue(self.manager._ring_staged)
        for key in before:
            self.assertEqual(self.positions()[key], before[key])
        self.assert_frame()
        self.settle()
        self.assertEqual(len(self.positions()), 8)
        self.assertFalse(self.manager._ring_staged)
        for _ in range(100):
            self.step()

    def test_hover_press_and_detail_hold_the_entire_group(self):
        self.apply(range(8))
        for _ in range(10):
            self.step()
        keys = list(self.manager._windows)
        for hold, release in ((self.manager.add_hover_hold, self.manager.release_hover_hold),
                              (self.manager.add_press_hold, self.manager.release_press_hold)):
            hold(keys[0])
            before, phase = self.positions(), self.manager._ring_t
            for _ in range(10):
                self.step()
            self.assertEqual(self.positions(), before)
            self.assertEqual(self.manager._ring_t, phase)
            release(keys[0])
            self.step()
            self.assertGreater(self.manager._ring_t, phase)
        self.manager.orb_activated(keys[0])
        self.manager._clear_interaction_holds()
        before, phase = self.positions(), self.manager._ring_t
        self.assertTrue(self.manager.detail_window.isVisible())
        for layer in (self.manager.back_overlay, self.manager.trail_overlay):
            self.assertFalse(layer._trails)
        for _ in range(10):
            self.step()
        self.assertEqual(self.positions(), before)
        self.assertEqual(self.manager._ring_t, phase)
        self.apply(range(8), total=999)
        self.assertEqual(self.positions(), before)
        self.manager.collapse_detail()
        self.assertEqual(self.positions(), before)
        self.step(dt=10)
        self.assertEqual(self.positions(), before)
        self.step()
        self.assertGreater(self.manager._ring_t, phase)

    def test_hide_retire_shutdown_are_terminal_for_late_ticks(self):
        self.apply(range(8))
        for _ in range(10):
            self.step()
        keys = list(self.manager._windows)
        self.manager.add_hover_hold(keys[0])
        self.manager.add_press_hold(keys[1])
        all_positions = {k: (w.x(), w.y()) for k, w in self.manager._windows.items()}
        phase = self.manager._ring_t
        self.manager.set_visible(False)
        self.assertFalse(self.manager._hover_holds | self.manager._press_holds)
        self.assertFalse(self.manager.back_overlay.isVisible())
        self.assertFalse(self.manager.trail_overlay.isVisible())
        for _ in range(3):
            self.step(dt=10)
        self.assertEqual(self.manager._ring_t, phase)
        self.assertEqual({k: (w.x(), w.y()) for k, w in self.manager._windows.items()},
                         all_positions)
        self.manager.set_visible(True)
        self.assertEqual(self.positions(), all_positions)
        self.step(dt=10)
        self.assertEqual(self.positions(), all_positions)
        self.step()
        self.assertGreater(self.manager._ring_t, phase)
        retired = self.manager._windows[keys[0]]
        self.manager.add_hover_hold(keys[0])
        self.manager.add_press_hold(keys[0])
        before = self.positions()
        self.apply(range(1, 8))
        self.assertFalse(retired.isVisible())
        self.assertNotIn(keys[0], self.manager._hover_holds | self.manager._press_holds)
        for key in self.positions():
            self.assertEqual(self.positions()[key], before[key])
        for layer in (self.manager.back_overlay, self.manager.trail_overlay):
            self.assertNotIn(keys[0], layer._trails)
        self.apply(())
        self.assertTrue(self.manager.back_overlay.isVisible())
        self.assertTrue(self.manager.trail_overlay.isVisible())
        self.assertFalse(self.manager.back_overlay.stars)
        self.assertFalse(self.manager.trail_overlay.stars)
        self.manager.shutdown()
        self.manager.tick_visual(self.stamp + 100, pet_rect=CENTER, screen_rect=SCREEN)
        self.apply(range(8))
        self.assertEqual(self.manager.window_count(), 0)
        self.assertFalse(self.manager.motion_timer.isActive())
        self.assertFalse(self.manager.back_overlay._trails)
        self.assertFalse(self.manager.trail_overlay._trails)

    def test_one_production_timer_off_settles_fades_idles_and_resumes(self):
        self.apply(range(8))
        self.panel.live = True
        loop = QEventLoop()
        observed = []

        def timeout():
            observed.append(self.manager._ring_t)
            if len(observed) == 4:
                loop.quit()

        self.manager.motion_timer.timeout.connect(timeout)
        deadline = QTimer()
        deadline.setSingleShot(True)
        deadline.timeout.connect(loop.quit)
        self.manager.sync_motion()
        deadline.start(2000)
        loop.exec()
        deadline.stop()
        self.manager.motion_timer.timeout.disconnect(timeout)
        self.assertEqual(len(observed), 4, 'shared native clock did not deliver ticks')
        self.assertGreater(observed[-1], observed[0])
        self.assert_frame()
        self.manager.stop_motion()
        self.stamp = time.monotonic()
        self.step()
        self.pet_rect = EDGES['bottom_right']
        before = self.positions()
        self.panel.prefs['pet_motion'] = False
        self.manager.anchor_changed()
        self.assertEqual(self.positions(), before)
        self.assertTrue(self.manager.motion_timer.isActive())
        phase = self.manager._ring_t
        self.settle()
        for _ in range(100):
            if not self.manager.motion_timer.isActive():
                break
            self.step()
        self.assertFalse(self.manager.motion_timer.isActive())
        self.assertEqual(self.manager._ring_t, phase)
        self.assertFalse(self.manager.back_overlay.has_trails())
        self.assertFalse(self.manager.trail_overlay.has_trails())
        before = self.positions()
        self.panel.prefs['pet_motion'] = True
        self.manager.sync_motion()
        self.assertTrue(self.manager.motion_timer.isActive())
        self.step(dt=20)
        self.assertEqual(self.positions(), before)
        self.step()
        self.assertGreater(self.manager._ring_t, phase)
        self.manager.shutdown()
        self.assertFalse(self.manager.motion_timer.isActive())


    def native_ranks(self, windows):
        import ctypes
        from ctypes import wintypes
        api = ctypes.WinDLL('user32')
        api.GetTopWindow.argtypes = (wintypes.HWND,)
        api.GetTopWindow.restype = wintypes.HWND
        api.GetWindow.argtypes = (wintypes.HWND, wintypes.UINT)
        api.GetWindow.restype = wintypes.HWND
        wanted = {int(w.winId()) for w in windows}
        result, handle = {}, api.GetTopWindow(None)
        for rank in range(4096):
            if not handle:
                break
            if handle in wanted:
                result[handle] = rank
            handle = api.GetWindow(handle, 2)
        self.assertEqual(set(result), wanted)
        return result

    def assert_native_depth_order(self):
        windows = self.manager.capture_windows()
        ranks = self.native_ranks(windows)
        actual = [ranks[int(w.winId())] for w in windows]
        self.assertEqual(actual, sorted(actual, reverse=True))

    @unittest.skipUnless(sys.platform == 'win32', 'Windows native window ordering')
    def test_idle_off_topmost_toggles_restore_native_depth_order(self):
        self.panel.pet.show()
        self.apply(range(8))
        self.panel.prefs['pet_motion'] = False
        self.manager.stop_motion()
        self.manager._clear_trails()
        for enabled in (False, True, False, True):
            self.panel.set_always_on_top(enabled)
            self.app.processEvents()
            self.assertFalse(self.manager.motion_timer.isActive())
            self.assert_native_depth_order()

    @unittest.skipUnless(sys.platform == 'win32', 'Windows native window ordering')
    def test_normal_depth_crossings_preserve_overlapping_editor_order(self):
        self.panel.pet.show()
        self.apply(range(8))
        self.panel.set_always_on_top(False)
        editor = QPlainTextEdit()
        try:
            editor.resize(500, 420)
            editor.move(self.panel.pet.pos())
            editor.show()
            editor.raise_()
            self.app.processEvents()
            self.step()
            initial = self.manager._halo_stack
            crossings = 0
            for _ in range(310):
                self.step()
                self.app.processEvents()
                if self.manager._halo_stack != initial:
                    crossings += 1
                    initial = self.manager._halo_stack
                    windows = self.manager.capture_windows()
                    ranks = self.native_ranks(windows + [editor])
                    self.assertLess(ranks[int(editor.winId())],
                                    min(ranks[int(w.winId())] for w in windows))
                    self.assert_native_depth_order()
            self.assertGreaterEqual(crossings, 3)
        finally:
            editor.close()

    def test_pet_rejects_foreign_payload_and_foreign_working_context(self):
        valid = {'provider_id': 'codex', 'total': 17, 'project': 'accepted',
                 'title': 'Codex task', 'model': 'gpt-6-sol'}
        self.panel.pet.update_data(valid)
        snapshot = self.panel.pet.snapshot
        tooltip = self.panel.pet.toolTip()
        self.panel.pet.update_data({'provider_id': 'opencode', 'total': 999})
        self.assertIs(self.panel.pet.snapshot, snapshot)
        self.assertEqual(self.panel.pet.toolTip(), tooltip)
        self.panel.pet.update_data(dict(valid, working_context={
            'provider_id': 'opencode', 'title': 'foreign task', 'total': 999}))
        self.assertIsNone(self.panel.pet.working_context)
        self.assertNotIn('foreign task', self.panel.pet.toolTip())

    def test_suspended_decoration_uses_current_visible_centers_only(self):
        self.apply(range(8))
        for numbers in (range(8), range(1, 8), range(3), ()):
            self.apply(numbers)
            self.step()
            expected = {key: (x + 56, y + 48, self.manager._halo_depths[key])
                        for key, (x, y) in self.positions().items()}
            for layer in (self.manager.back_overlay, self.manager.trail_overlay):
                self.assertEqual(layer.stars, expected)
                self.assertLessEqual(len(layer.stars), 8)


def _edge_full_cycle(count, name, pet_rect):
    def test(self):
        self.pet_rect = pet_rect
        self.apply(range(count))
        self.assertIsNone(self.manager._park_blend)
        self.assertIsNone(self.manager._ring_blend)
        self.assertEqual(len(self.positions()), count)
        self.step()
        phase = self.manager._ring_t
        initial = self.positions()
        for frame in range(601):
            if frame == 300:
                # An exhausted historical route must not become the halo clock.
                self.manager._park_blend = {'t': 1.0, 'dur': 1.0, 'paths': {}}
                self.manager._ring_blend = {'t': 1.0, 'dur': 1.0, 'paths': {}}
            before_phase = self.manager._ring_t
            self.step()
            self.assertGreater(self.manager._ring_t, before_phase)
            if frame < 300:
                self.assertIsNone(self.manager._park_blend)
                self.assertIsNone(self.manager._ring_blend)
        self.assertGreaterEqual(self.manager._ring_t - phase, 24)
        for key, position in initial.items():
            self.assertLessEqual(sum(abs(a - b) for a, b in
                                     zip(position, self.positions()[key])), 4)
    test.__name__ = 'test_full_cycle_%s_%s' % (count, name)
    return test


for _count in (1, 3, 8):
    for _name, _rect in EDGES.items():
        _test = _edge_full_cycle(_count, _name, _rect)
        setattr(HaloSceneTests, _test.__name__, _test)


if __name__ == '__main__':
    unittest.main()
