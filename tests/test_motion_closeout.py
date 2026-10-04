"""Historical exterior-route boundaries with current Codex-only fixtures."""
import unittest

from tests import test_ui as ui_fixture

from tests.test_ui import (
    _codex_entry, _secondary_codex_entry,
    _CENTER_PET_RECT, _SCREEN_RECT,
)


class MotionCloseoutTests(unittest.TestCase):
    setUpClass = classmethod(ui_fixture.TaskPanelManagerTests.setUpClass.__func__)
    setUp = ui_fixture.TaskPanelManagerTests.setUp
    tearDown = ui_fixture.TaskPanelManagerTests.tearDown
    _apply_at = ui_fixture.TaskPanelManagerTests._apply_at
    _tick_at = ui_fixture.TaskPanelManagerTests._tick_at

    def positions(self):
        return {key: (orb.x(), orb.y())
                for key, orb in self.manager._windows.items()
                if key not in self.manager._ring_staged}

    def warm(self, tasks, pet):
        self._apply_at(tasks, pet)
        stamp = 1000.0
        self._tick_at(stamp, pet)
        for _ in range(75):
            stamp += 0.04
            self._tick_at(stamp, pet)
        return stamp

    def assert_boundary(self, before):
        after = self.positions()
        for key in before.keys() & after.keys():
            self.assertEqual(before[key], after[key], key)
        self.assertTrue(self.manager._nominal_valid(
            after, self.pet_rect, _SCREEN_RECT))

    def land(self, stamp, limit=6000, jitter=False):
        for frame in range(limit):
            before = self.positions()
            stamp += (0.013 if frame % 2 else 0.027) if jitter else 0.04
            self._tick_at(stamp, self.pet_rect)
            after = self.positions()
            for key in before.keys() & after.keys():
                distance = sum(abs(a - b) for a, b in zip(
                    before[key], after[key]))
                self.assertLessEqual(distance, 16, (frame, key))
            self.assertTrue(self.manager._nominal_valid(
                after, self.pet_rect, _SCREEN_RECT), frame)
            if self.manager._park_blend is None:
                self.assertFalse(self.manager._ring_staged)
                return stamp
        self.fail('parking did not finish within 240 seconds of active time')

    def arc_case(self, initial, changed, preference='auto'):
        self.pet_rect = (100, 100, 272, 330)
        stamp = self.warm(initial, self.pet_rect)
        self.assertEqual(self.manager._orbit_mode[0], 'arc')
        before = self.positions()
        self._apply_at(changed, self.pet_rect, preference=preference)
        self.assert_boundary(before)
        self.land(stamp)

    def test_arc_add_preserves_frame_zero(self):
        self.arc_case([_codex_entry(str(i)) for i in range(3)],
                      [_codex_entry(str(i)) for i in range(4)])

    def test_arc_remove_preserves_frame_zero(self):
        self.arc_case([_codex_entry(str(i)) for i in range(4)],
                      [_codex_entry(str(i)) for i in range(3)])

    def test_same_arc_tuple_membership_preserves_frame_zero(self):
        self.arc_case([_codex_entry(str(i)) for i in range(4)],
                      [_codex_entry(str(i)) for i in range(5)])

    def test_arc_composition_retire_preserves_frame_zero(self):
        tasks = ([_codex_entry(str(i)) for i in range(3)]
                 + [_secondary_codex_entry('z-secondary:x')])
        self.arc_case(tasks, tasks[:-1], 'codex')

    def test_eight_star_parking_finds_complete_schedule(self):
        self.pet_rect = _CENTER_PET_RECT
        tasks = [_codex_entry(str(i)) for i in range(8)]
        stamp = self.warm(tasks, self.pet_rect)
        before = self.positions()
        self.panel.prefs['pet_motion'] = False
        self._apply_at(tasks, self.pet_rect)
        self.assert_boundary(before)
        self.land(stamp)
        for key, pos in self.positions().items():
            self.assertEqual(pos, self.manager._auto_home(
                key, self.pet_rect, _SCREEN_RECT))

    def test_newcomer_replans_and_waits_for_parking_landing(self):
        self.pet_rect = _CENTER_PET_RECT
        tasks = [_codex_entry(str(i)) for i in range(6)]
        stamp = self.warm(tasks, self.pet_rect)
        self.panel.prefs['pet_motion'] = False
        self._apply_at(tasks, self.pet_rect)
        for _ in range(10):
            stamp += 0.04
            self._tick_at(stamp, self.pet_rect)
        old = self.manager._park_blend
        before = self.positions()
        tasks.append(_codex_entry('6'))
        self._apply_at(tasks, self.pet_rect)
        self.assertIsNot(self.manager._park_blend, old)
        self.assertIn(('codex', '6'), self.manager._ring_staged)
        self.assert_boundary(before)
        current = self.manager._park_blend
        self._apply_at(tasks, self.pet_rect)
        self.assertIs(self.manager._park_blend, current)
        self.land(stamp, limit=12000, jitter=True)
        self.assertEqual(len(self.positions()), 7)

    def test_retire_during_parking_replans_from_current_pixels(self):
        self.pet_rect = _CENTER_PET_RECT
        tasks = [_codex_entry(str(i)) for i in range(8)]
        stamp = self.warm(tasks, self.pet_rect)
        self.panel.prefs['pet_motion'] = False
        self._apply_at(tasks, self.pet_rect)
        for _ in range(10):
            stamp += 0.04
            self._tick_at(stamp, self.pet_rect)
        old = self.manager._park_blend
        before = self.positions()
        self._apply_at(tasks[:-1], self.pet_rect)
        self.assertIsNot(self.manager._park_blend, old)
        self.assert_boundary(before)
        self.land(stamp)

    def test_composition_retire_during_parking_replans_visible_obstacles(self):
        self.pet_rect = _CENTER_PET_RECT
        tasks = ([_codex_entry(str(i)) for i in range(5)]
                 + [_secondary_codex_entry('z-secondary:x')])
        stamp = self.warm(tasks, self.pet_rect)
        self.panel.prefs['pet_motion'] = False
        self._apply_at(tasks, self.pet_rect)
        for _ in range(10):
            stamp += 0.04
            self._tick_at(stamp, self.pet_rect)
        old = self.manager._park_blend
        before = self.positions()
        self._apply_at(tasks[:-1], self.pet_rect, preference='codex')
        self.assertIsNot(self.manager._park_blend, old)
        self.assert_boundary(before)
        self.land(stamp)

    def test_hide_show_and_motion_resume_keep_parking_frame_zero(self):
        self.pet_rect = (100, 100, 272, 330)
        tasks = [_codex_entry(str(i)) for i in range(4)]
        stamp = self.warm(tasks, self.pet_rect)
        self.panel.prefs['pet_motion'] = False
        self._apply_at(tasks, self.pet_rect)
        for _ in range(10):
            stamp += 0.04
            self._tick_at(stamp, self.pet_rect)
        before = self.positions()
        plan = self.manager._park_blend
        self.manager.set_visible(False)
        self.manager.set_visible(True)
        self.assert_boundary(before)
        self.assertIs(self.manager._park_blend, plan)
        self.panel.prefs['pet_motion'] = True
        self._apply_at(tasks, self.pet_rect)
        self.assert_boundary(before)
        self.land(stamp)
        before = self.positions()
        stamp += 0.04
        self._tick_at(stamp, self.pet_rect)
        for key, position in self.positions().items():
            self.assertLessEqual(sum(abs(a - b) for a, b in zip(
                before[key], position)), 16)


if __name__ == '__main__':
    unittest.main()
