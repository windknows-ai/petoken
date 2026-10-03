"""Production parking planning keeps the native Qt event loop responsive."""
import threading
import time
import unittest
from unittest.mock import patch

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtTest import QSignalSpy

import widget
from tests import test_ui as fixture
from tests import test_motion_closeout as closeout
from tests.test_ui import _codex_entry, _CENTER_PET_RECT, _SCREEN_RECT


class PlanningResponsivenessTests(unittest.TestCase):
    setUpClass = classmethod(fixture.TaskPanelManagerTests.setUpClass.__func__)
    setUp = fixture.TaskPanelManagerTests.setUp
    tearDown = fixture.TaskPanelManagerTests.tearDown
    _apply_at = fixture.TaskPanelManagerTests._apply_at
    _tick_at = fixture.TaskPanelManagerTests._tick_at
    positions = closeout.MotionCloseoutTests.positions
    warm = closeout.MotionCloseoutTests.warm
    land = closeout.MotionCloseoutTests.land

    def prepare(self):
        self.tasks = [_codex_entry(str(i)) for i in range(8)]
        self.pet_rect = _CENTER_PET_RECT
        self.stamp = self.warm(self.tasks, self.pet_rect)
        self.panel.prefs['pet_motion'] = False
        self._apply_at(self.tasks, self.pet_rect)
        for _ in range(10):
            self.stamp += 0.04
            self._tick_at(self.stamp, self.pet_rect)
        self.panel.live = True
        self.anchor_patch = patch.object(
            self.manager, '_anchor', side_effect=lambda: (self.pet_rect, _SCREEN_RECT))
        self.anchor_patch.start()
        self.addCleanup(self.anchor_patch.stop)

    def held_planner(self):
        entered, release = threading.Event(), threading.Event()
        calls = []
        original = widget._plan_parking_routes
        gui_thread = threading.get_ident()

        def plan(inputs):
            calls.append((threading.get_ident(), inputs))
            entered.set()
            if not release.wait(5):
                raise RuntimeError('test failed to release planner')
            return original(inputs)

        self.addCleanup(release.set)
        patcher = patch('widget._plan_parking_routes', side_effect=plan)
        patcher.start()
        self.addCleanup(patcher.stop)
        return entered, release, calls, original, gui_thread

    def pump_until(self, predicate, timeout=5000):
        loop, check, deadline = QEventLoop(), QTimer(), QTimer()
        check.setInterval(5)
        check.timeout.connect(lambda: loop.quit() if predicate() else None)
        deadline.setSingleShot(True)
        deadline.timeout.connect(loop.quit)
        check.start()
        deadline.start(timeout)
        loop.exec()
        check.stop()
        deadline.stop()
        self.assertTrue(predicate(), 'native Qt loop did not reach the event condition')

    def shifted_plan(self, shift):
        self.prepare()
        before = self.positions()
        self.pet_rect = (self.pet_rect[0] + shift[0],
                         self.pet_rect[1] + shift[1], *self.pet_rect[2:])
        self.assertTrue(self.manager._nominal_valid(before, self.pet_rect, _SCREEN_RECT))
        entered, release, calls, original, gui_thread = self.held_planner()
        start = time.perf_counter()
        self._apply_at(self.tasks, self.pet_rect, generation=10)
        self.assertLess(time.perf_counter() - start, 0.25)
        self.assertTrue(entered.wait(1))
        self.assertNotEqual(calls[0][0], gui_thread)
        pending, request = self.manager._park_blend, self.manager._park_plan_request
        self.assertTrue(pending['pending'])
        self.assertEqual(self.positions(), before)
        phase = (self.manager._ring_t, self.manager._motion_t)
        controlled = []

        def control():
            # Accepted metadata-only polls preserve the geometry job and clock.
            for generation in range(11, 16):
                self._apply_at(self.tasks, self.pet_rect, generation=generation)
            self.manager.retranslate('en')
            controlled.append(True)

        motion = QSignalSpy(self.manager.motion_timer.timeout)
        QTimer.singleShot(0, control)
        self.assertTrue(motion.wait(250), 'shared native clock stalled during planning')
        self.assertTrue(controlled)
        self.assertIs(self.manager._park_blend, pending)
        self.assertIs(self.manager._park_plan_request, request)
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.positions(), before)
        self.assertEqual((self.manager._ring_t, self.manager._motion_t), phase)
        # Run actual CPU planning while native heartbeat/control callbacks execute.
        heartbeat, gaps = QTimer(), []
        last = [time.perf_counter()]

        def beat():
            current = time.perf_counter()
            gaps.append(current - last[0])
            last[0] = current

        heartbeat.timeout.connect(beat)
        heartbeat.start(5)
        release.set()
        job = self.manager._park_plan_job
        self.pump_until(lambda: job[2].is_set())
        heartbeat.stop()
        self.assertTrue(gaps)
        self.assertLess(max(gaps), 0.25)
        self.manager.stop_motion()
        # Consume through the actual shared visual-clock callback; this commit
        # owns frame zero, even after an arbitrarily delayed clock sample.
        self.manager._on_motion_timeout()
        committed = self.manager._park_blend
        self.assertFalse(committed.get('pending'))
        self.assertFalse(committed.get('blocked'))
        self.assertEqual(self.positions(), before)
        expected = original((*calls[0][1][:-1], False))
        self.assertEqual(committed['routes'], expected['routes'])
        self.assertEqual(committed['windows'], expected['windows'])
        self.land(time.monotonic())
        self.assertEqual(self.positions(), {
            key: self.manager._auto_home(key, self.pet_rect, _SCREEN_RECT)
            for key in before})
        self.assertFalse(self.manager.motion_timer.isActive())
        self.manager.sync_motion()
        self.assertIsNone(self.manager._park_blend)
        self.assertFalse(self.manager.motion_timer.isActive())

    def test_native_left100_plans_without_blocking_controls(self):
        self.shifted_plan((-100, 0))

    def test_native_down100_plans_without_blocking_controls(self):
        self.shifted_plan((0, 100))

    def immediate_plan(self, shift, tick_only=False):
        self.prepare()
        before = self.positions()
        self.pet_rect = (self.pet_rect[0] + shift[0],
                         self.pet_rect[1] + shift[1], *self.pet_rect[2:])
        heartbeat, control_timer = QTimer(), QTimer()
        gaps, controls, started = [], [], []
        last = [time.perf_counter()]

        def beat():
            current = time.perf_counter()
            gaps.append(current - last[0])
            last[0] = current

        def control():
            if not started or not (self.manager._park_blend or {}).get('pending'):
                return
            request = self.manager._park_plan_request
            start = time.perf_counter()
            self._apply_at(self.tasks, self.pet_rect, generation=len(controls) + 20)
            self.manager.retranslate('en')
            controls.append(time.perf_counter() - start)
            self.assertIs(self.manager._park_plan_request, request)

        def begin():
            start = time.perf_counter()
            if tick_only:
                self._tick_at(self.stamp + 0.04, self.pet_rect)
            else:
                self._apply_at(self.tasks, self.pet_rect, generation=10)
            started.append(time.perf_counter() - start)
            self.assertEqual(self.positions(), before)

        heartbeat.timeout.connect(beat)
        control_timer.timeout.connect(control)
        heartbeat.start(5)
        control_timer.start(17)
        QTimer.singleShot(0, begin)
        try:
            self.pump_until(lambda: bool(started)
                            and not (self.manager._park_blend or {}).get('pending'))
        finally:
            heartbeat.stop()
            control_timer.stop()
            self.manager.stop_motion()
        self.assertLess(started[0], 0.25)
        self.assertGreater(len(gaps), 5)
        self.assertGreater(len(controls), 2)
        self.assertLess(max(gaps), 0.25)
        self.assertLess(max(controls), 0.25)
        self.assertEqual(self.positions(), before)
        self.assertFalse(self.manager._park_blend.get('blocked'))
        self.land(time.monotonic())

    def test_immediate_left100_worker_allows_native_paint_and_control_callbacks(self):
        self.immediate_plan((-100, 0))

    def test_immediate_down100_worker_allows_native_paint_and_control_callbacks(self):
        self.immediate_plan((0, 100))

    def test_timer_only_left100_queues_worker_and_keeps_native_controls_responsive(self):
        self.immediate_plan((-100, 0), tick_only=True)

    def stale_case(self, change):
        self.prepare()
        entered, release, calls, _, _ = self.held_planner()
        self.pet_rect = (self.pet_rect[0] - 100, *self.pet_rect[1:])
        self._apply_at(self.tasks, self.pet_rect, generation=10)
        self.assertTrue(entered.wait(1))
        old_job = self.manager._park_plan_job
        old_request = self.manager._park_plan_request
        self.manager.stop_motion()
        change()
        latest = self.manager._park_plan_request
        self.assertGreater(latest[0], old_request[0])
        self.assertIs(self.manager._park_plan_job, old_job)
        self.assertEqual(len(calls), 1)
        before = self.positions()
        release.set()
        self.assertTrue(old_job[2].wait(5))
        self._tick_at(self.stamp + 10, self.pet_rect)
        self.assertEqual(self.positions(), before)
        self.assertTrue(self.manager._park_blend['pending'])
        self.assertIs(self.manager._park_plan_request, latest)
        new_job = self.manager._park_plan_job
        self.assertEqual(new_job[:2], latest[:2])
        self.assertTrue(new_job[2].wait(5))
        self._tick_at(self.stamp + 20, self.pet_rect)
        self.assertEqual(self.positions(), before)
        self.assertEqual(self.manager._park_blend['pet_rect'], tuple(self.pet_rect))
        self.assertIsNone(self.manager._park_plan_request)
        self.assertEqual(len(calls), 2)

    def test_membership_latest_job_coalesces_and_old_generation_cannot_restore(self):
        def change():
            self.tasks = self.tasks[:-1] + [_codex_entry('replacement')]
            self._apply_at(self.tasks, self.pet_rect, generation=12)
            latest = self.manager._park_plan_request
            self._apply_at([_codex_entry('obsolete')], self.pet_rect, generation=11)
            self.assertIs(self.manager._park_plan_request, latest)
            self.assertIn(('codex', 'replacement'), self.manager._ring_staged)
            self.assertNotIn(('codex', '7'), self.manager._windows)
        self.stale_case(change)

    def test_geometry_changes_coalesce_only_latest_immutable_request(self):
        def change():
            for y in (385, 395, 405):
                self.pet_rect = (self.pet_rect[0], y, *self.pet_rect[2:])
                self._apply_at(self.tasks, self.pet_rect)
        self.stale_case(change)

    def test_external_position_change_replans_from_actual_pixels(self):
        def change():
            orb = next(iter(self.manager._windows.values()))
            orb.move(orb.x() + 1, orb.y())
            self._tick_at(self.stamp + 0.04, self.pet_rect)
        self.stale_case(change)

    def test_hide_invalidates_worker_and_show_restores_exact_pixels(self):
        self.prepare()
        entered, release, calls, _, _ = self.held_planner()
        self.pet_rect = (self.pet_rect[0] - 100, *self.pet_rect[1:])
        self._apply_at(self.tasks, self.pet_rect)
        self.assertTrue(entered.wait(1))
        job, before = self.manager._park_plan_job, self.positions()
        self.manager.set_visible(False)
        self.assertIsNone(self.manager._park_plan_request)
        self.assertIsNone(self.manager._park_blend)
        self.assertFalse(self.manager.motion_timer.isActive())
        release.set()
        self.assertTrue(job[2].wait(5))
        self.assertEqual(self.positions(), before)
        self.manager.set_visible(True)
        self.manager.stop_motion()
        self._tick_at(self.stamp + 10, self.pet_rect)
        self.assertEqual(self.positions(), before)
        self.assertTrue(self.manager._park_blend['pending'])
        latest_job = self.manager._park_plan_job
        self.assertTrue(latest_job[2].wait(5))
        self._tick_at(self.stamp + 20, self.pet_rect)
        self.assertEqual(self.positions(), before)
        self.assertEqual(len(calls), 2)

    def test_shutdown_never_joins_or_commits_late_pure_worker(self):
        self.prepare()
        entered, release, _, _, _ = self.held_planner()
        self.pet_rect = (self.pet_rect[0] - 100, *self.pet_rect[1:])
        self._apply_at(self.tasks, self.pet_rect)
        self.assertTrue(entered.wait(1))
        job = self.manager._park_plan_job
        start = time.perf_counter()
        self.manager.shutdown()
        self.assertLess(time.perf_counter() - start, 0.25)
        self.assertFalse(job[2].is_set())
        release.set()
        self.assertTrue(job[2].wait(5))
        self.manager._on_motion_timeout()
        self._apply_at(self.tasks, self.pet_rect, generation=999)
        self.manager.set_visible(True)
        self.assertEqual(self.manager.window_count(), 0)
        self.assertIsNone(self.manager._park_blend)
        self.assertIsNone(self.manager._park_plan_request)
        self.assertFalse(self.manager.motion_timer.isActive())

    def test_motion_toggle_supersedes_pending_job_without_late_park_commit(self):
        self.prepare()
        entered, release, _, _, _ = self.held_planner()
        self.pet_rect = (self.pet_rect[0] - 100, *self.pet_rect[1:])
        self._apply_at(self.tasks, self.pet_rect)
        self.assertTrue(entered.wait(1))
        old_job = self.manager._park_plan_job
        self.manager.stop_motion()
        self.panel.prefs['pet_motion'] = True
        before = self.positions()
        self._apply_at(self.tasks, self.pet_rect)
        self.assertEqual(self.positions(), before)
        self.assertIsNone(self.manager._park_plan_request)
        self.assertIsNone(self.manager._park_blend)
        ring = self.manager._ring_blend
        release.set()
        self.assertTrue(old_job[2].wait(5))
        self._tick_at(self.stamp + 10, self.pet_rect)
        self.assertIsNone(self.manager._park_blend)
        self.assertIs(self.manager._ring_blend, ring)

    def test_worker_failure_holds_exact_frame_and_idles_native_timer(self):
        self.prepare()
        before = self.positions()
        self.pet_rect = (self.pet_rect[0] - 100, *self.pet_rect[1:])
        with patch('widget._plan_parking_routes', side_effect=RuntimeError('probe')):
            self._apply_at(self.tasks, self.pet_rect)
            job = self.manager._park_plan_job
            self.assertTrue(job[2].wait(1))
            self.manager._on_motion_timeout()
        self.assertEqual(self.positions(), before)
        self.assertEqual(self.manager._park_blend['blocked'], 'parking_planner_error')
        self.assertIsNone(self.manager._park_plan_request)
        self.assertFalse(self.manager.motion_timer.isActive())

    def test_external_home_positions_cancel_pending_work_and_idle(self):
        self.prepare()
        entered, release, _, _, _ = self.held_planner()
        self.pet_rect = (self.pet_rect[0] - 100, *self.pet_rect[1:])
        self._apply_at(self.tasks, self.pet_rect)
        self.assertTrue(entered.wait(1))
        job = self.manager._park_plan_job
        for key, orb in self.manager._windows.items():
            pos = self.manager._auto_home(key, self.pet_rect, _SCREEN_RECT)
            orb.move(*pos)
            self.manager._placed[key] = pos
        before = self.positions()
        self._tick_at(self.stamp + 10, self.pet_rect)
        self.assertEqual(self.positions(), before)
        self.assertIsNone(self.manager._park_blend)
        self.assertIsNone(self.manager._park_plan_request)
        self.assertFalse(self.manager.motion_timer.isActive())
        release.set()
        self.assertTrue(job[2].wait(5))
        self.manager._on_motion_timeout()
        self.assertEqual(self.positions(), before)
        self.assertIsNone(self.manager._park_blend)
