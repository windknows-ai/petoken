"""Legal parking interruption, planning cost and terminal lifecycle gates."""
import time
import threading
import unittest
from unittest.mock import patch
from PySide6.QtTest import QSignalSpy

from tests import test_ui as fixture
from tests import test_motion_closeout as closeout
from tests.test_ui import _codex_entry, _CENTER_PET_RECT, _SCREEN_RECT
from widget import valid_panel_size


class MotionRouteTests(unittest.TestCase):
    setUpClass = classmethod(fixture.TaskPanelManagerTests.setUpClass.__func__)
    setUp = fixture.TaskPanelManagerTests.setUp
    tearDown = fixture.TaskPanelManagerTests.tearDown
    _apply_at = fixture.TaskPanelManagerTests._apply_at
    _tick_at = fixture.TaskPanelManagerTests._tick_at
    positions = closeout.MotionCloseoutTests.positions
    warm = closeout.MotionCloseoutTests.warm
    assert_boundary = closeout.MotionCloseoutTests.assert_boundary
    land = closeout.MotionCloseoutTests.land

    def interrupt(self, shift, tick_only=False, jitter=False):
        tasks = [_codex_entry(str(i)) for i in range(8)]
        self.pet_rect = _CENTER_PET_RECT
        stamp = self.warm(tasks, self.pet_rect)
        self.panel.prefs['pet_motion'] = False
        self._apply_at(tasks, self.pet_rect)
        for _ in range(10):
            stamp += 0.04
            self._tick_at(stamp, self.pet_rect)
        before = self.positions()
        self.pet_rect = (self.pet_rect[0] + shift, *self.pet_rect[1:])
        self.assertTrue(self.manager._nominal_valid(
            before, self.pet_rect, _SCREEN_RECT))
        homes = {key: self.manager._auto_home(key, self.pet_rect, _SCREEN_RECT)
                 for key in before}
        self.assertTrue(self.manager._nominal_valid(homes, self.pet_rect, _SCREEN_RECT))
        begin = time.perf_counter()
        if tick_only:
            stamp += 0.04
            self._tick_at(stamp, self.pet_rect)
        else:
            self._apply_at(tasks, self.pet_rect)
        elapsed = time.perf_counter() - begin
        self.assertLess(elapsed, 1.0, 'legal parking planning blocks the GUI')
        self.assert_boundary(before)
        plan = self.manager._park_blend
        self.assertIsNotNone(plan)
        self.assertFalse(plan.get('blocked'))
        self.assertGreater(plan['dur'], 0.0)
        self._apply_at(tasks, self.pet_rect)
        self.assertIs(self.manager._park_blend, plan)
        self.land(stamp, jitter=jitter, limit=12000 if jitter else 6000)
        self.assertEqual(self.positions(), homes)

    def test_eight_star_pet_move_100_parks_validly(self):
        self.interrupt(100)

    def test_eight_star_pet_move_10_parks_validly(self):
        self.interrupt(10)

    def test_timer_only_pet_move_replans_exact_pixels(self):
        self.interrupt(100, tick_only=True)

    def test_pet_move_route_handles_13_27ms_ticks(self):
        self.interrupt(100, jitter=True)

    def test_every_planned_pixel_preserves_complete_frame(self):
        self.pet_rect = _CENTER_PET_RECT
        tasks = [_codex_entry(str(i)) for i in range(8)]
        self.warm(tasks, self.pet_rect)
        self.panel.prefs['pet_motion'] = False
        self._apply_at(tasks, self.pet_rect)
        plan = self.manager._park_blend
        self.assertFalse(plan.get('blocked'))
        context = self.positions()
        for key in sorted(plan['routes'], key=lambda item: plan['windows'][item][0]):
            path, distances = plan['routes'][key]
            self.assertEqual(path[0], context[key])
            for index, pos in enumerate(path):
                context[key] = pos
                self.assertTrue(self.manager._nominal_valid(
                    context, self.pet_rect, _SCREEN_RECT), (key, index))
                if index:
                    delta = sum(abs(a - b) for a, b in zip(path[index - 1], pos))
                    self.assertLessEqual(delta, 2)
                    self.assertEqual(distances[index] - distances[index - 1], delta)
            self.assertEqual(path[-1], self.manager._auto_home(
                key, self.pet_rect, _SCREEN_RECT))

    def test_shutdown_is_terminal_and_idempotent(self):
        tasks = [_codex_entry('a')]
        self._apply_at(tasks, _CENTER_PET_RECT)
        self.manager.shutdown()
        self.manager.shutdown()
        self.assertEqual(self._apply_at(tasks, _CENTER_PET_RECT, generation=999), [])
        self.manager.start_motion()
        self.manager.set_visible(True)
        self.assertFalse(self.manager.sync_motion())
        self.assertFalse(self.manager.motion_timer.isActive())
        self.assertEqual(self.manager.window_count(), 0)

    def test_closing_rejects_queued_render_and_publication(self):
        self.panel.closing = True
        old = self.panel.snapshot
        emitted = QSignalSpy(self.panel.bridge.data)
        self.panel.publish_snapshot({'result': {'generation': 999}})
        self.assertEqual(emitted.count(), 0)
        self.panel.render({'active_tasks': [_codex_entry('late')], 'generation': 999})
        self.assertIs(self.panel.snapshot, old)
        self.assertEqual(self.manager.window_count(), 0)

    def test_preclose_queued_signal_cannot_resurrect_stars(self):
        old = self.panel.snapshot
        payload = {'active_tasks': [_codex_entry('late')], 'generation': 999}
        worker = threading.Thread(target=self.panel.bridge.data.emit, args=(payload,))
        worker.start()
        worker.join()
        self.panel.closing = True
        self.manager.shutdown()
        self.app.processEvents()
        self.assertIs(self.panel.snapshot, old)
        self.assertEqual(self.manager.window_count(), 0)

    def test_opencode_status_arms_shared_motion_clock(self):
        self.panel.snapshot = {'provider_id': 'opencode'}
        with patch.object(self.manager, 'sync_motion') as sync:
            self.panel.refresh_status()
            sync.assert_called_once_with()

    def test_saved_panel_size_rejects_infinity(self):
        self.assertIsNone(valid_panel_size([float('inf'), 500]))
        self.assertIsNone(valid_panel_size([420, float('-inf')]))
        self.assertEqual(valid_panel_size([420, 500]), [420, 500])
