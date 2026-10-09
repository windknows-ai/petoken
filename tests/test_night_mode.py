import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication

import night_mode
from night_mode import NightMode, SitReminder, in_window

APP = QApplication.instance() or QApplication([])


def at(hour, minute=0):
    return datetime(2026, 10, 9, hour, minute).timestamp()


class FakePanel(QObject):
    def __init__(self, **prefs):
        super().__init__()
        self.prefs = dict(prefs)
        self.live = False


class Busy:
    def __init__(self, active=False, phase='idle'):
        self.active, self.phase = active, phase


class NightWindowTest(unittest.TestCase):
    def test_overnight_window(self):
        prefs = {'night_start': '23:00', 'night_end': '07:00'}
        self.assertTrue(in_window(prefs, at(23, 30)))
        self.assertTrue(in_window(prefs, at(3)))
        self.assertFalse(in_window(prefs, at(7)))
        self.assertFalse(in_window(prefs, at(22, 59)))

    def test_same_day_window_and_bad_values(self):
        self.assertTrue(in_window({'night_start': '13:00', 'night_end': '14:00'}, at(13, 30)))
        self.assertFalse(in_window({'night_start': '13:00', 'night_end': '14:00'}, at(14, 30)))
        self.assertFalse(in_window({'night_start': '10:00', 'night_end': '10:00'}, at(10)))
        self.assertTrue(in_window({'night_start': 'x', 'night_end': None}, at(0)))   # Defaults 23–7.


class NightModeTest(unittest.TestCase):
    def test_follows_the_clock_and_dnd(self):
        panel = FakePanel(night_with_dnd=True, dnd_enabled=False)
        night = NightMode(panel)
        seen = []
        night.changed.connect(seen.append)
        night.poll(at(12))
        self.assertFalse(night.active)
        night.poll(at(23, 5))
        self.assertTrue(night.active)
        night.poll(at(7, 1))
        self.assertFalse(night.active)
        panel.prefs['dnd_enabled'] = True                 # Do Not Disturb: pajamas at noon too.
        night.poll(at(12))
        self.assertTrue(night.active)
        panel.prefs['night_with_dnd'] = False
        night.poll(at(12))
        self.assertFalse(night.active)
        self.assertEqual(seen, [True, False, True, False])

    def test_off_means_never(self):
        night = NightMode(FakePanel(night_enabled=False))
        night.poll(at(2))
        self.assertFalse(night.active)

    def test_manual_switch_lasts_until_the_window_changes(self):
        night = NightMode(FakePanel())
        night.poll(at(12))
        night.toggle()
        self.assertTrue(night.active)
        night.poll(at(15))
        self.assertTrue(night.active)                    # Still by hand.
        night.poll(at(23, 30))                           # Night begins: schedule again (on).
        night.toggle()
        self.assertFalse(night.active)
        night.poll(at(2))
        self.assertFalse(night.active)
        night.poll(at(8))                                # Morning: schedule again (off).
        self.assertFalse(night.active)
        self.assertIsNone(night.manual)

    def test_pose_only_when_the_night_art_exists(self):
        night = NightMode(FakePanel())
        night.poll(at(1))
        with mock.patch('pet_assets.has_own_art', return_value=False):
            self.assertEqual(night.pose('idle'), 'idle')
        with mock.patch('pet_assets.has_own_art', return_value=True):
            self.assertEqual(night.pose('idle'), 'night_idle')
            self.assertEqual(night.pose('sleep'), 'night_sleep')
            self.assertEqual(night.pose('typing'), 'typing')   # Task poses stay.
        night.poll(at(12))
        with mock.patch('pet_assets.has_own_art', return_value=True):
            self.assertEqual(night.pose('idle'), 'idle')

    def test_night_poses_are_registered(self):
        import pet_assets
        names = {entry.state for entry in pet_assets.NIGHT_REGISTRY}
        self.assertEqual(names, set(night_mode.NIGHT_POSES.values()))


class SitReminderTest(unittest.TestCase):
    def make(self, **prefs):
        self.idle = 0.0
        panel = FakePanel(**prefs)
        panel.game_mode, panel.focus_mode = Busy(), Busy()
        reminder = SitReminder(panel, idle=lambda: self.idle, clock=lambda: 0.0)
        fired = []
        reminder.remind.connect(lambda: fired.append(True))
        return panel, reminder, fired

    def test_reminds_after_the_stretch_and_again_later(self):
        _panel, reminder, fired = self.make(sit_minutes=30)
        self.assertFalse(reminder.poll(0))
        self.assertFalse(reminder.poll(29 * 60))
        self.assertTrue(reminder.poll(30 * 60))
        self.assertEqual(reminder.sitting_minutes(30 * 60), 30)
        self.assertFalse(reminder.poll(31 * 60))         # Once per stretch…
        self.assertTrue(reminder.poll(60 * 60))          # …then again after another one.
        self.assertEqual(len(fired), 2)

    def test_a_real_pause_starts_over(self):
        _panel, reminder, fired = self.make(sit_minutes=30)
        reminder.poll(0)
        self.idle = 6 * 60
        reminder.poll(20 * 60)
        self.idle = 0
        reminder.poll(21 * 60)
        self.assertFalse(reminder.poll(45 * 60))          # Only 24 minutes since the pause.
        self.assertTrue(reminder.poll(51 * 60))
        self.assertEqual(len(fired), 1)

    def test_quiet_while_gaming_focusing_or_off(self):
        panel, reminder, fired = self.make(sit_minutes=30)
        reminder.poll(0)
        panel.game_mode.active = True
        self.assertFalse(reminder.poll(40 * 60))
        panel.game_mode.active = False
        panel.focus_mode.phase = 'focus'
        self.assertFalse(reminder.poll(40 * 60))
        panel.focus_mode.phase = 'idle'
        panel.prefs['sit_minutes'] = 0
        self.assertFalse(reminder.poll(40 * 60))
        panel.prefs['sit_minutes'] = 30
        self.assertTrue(reminder.poll(40 * 60))
        self.assertEqual(len(fired), 1)


class PreferencesTest(unittest.TestCase):
    def test_rest_preferences_are_cleaned(self):
        from app_config import load_preferences
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'settings.json'
            path.write_text('{"night_start": "late", "sit_minutes": 7, "app_time_enabled": "yes"}',
                            encoding='utf-8')
            prefs = load_preferences(path)
        self.assertEqual(prefs['night_start'], '23:00')
        self.assertEqual(prefs['sit_minutes'], 60)
        self.assertIs(prefs['app_time_enabled'], False)
        self.assertIs(prefs['night_enabled'], True)


if __name__ == '__main__':
    unittest.main()


class PanelCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.pref_patch = mock.patch('widget.PREF_DIR', Path(self.temp.name))
        self.pref_patch.start()
        from widget import Panel
        from pet import DesktopPet
        self.panel = Panel(live=False)
        self.pet = DesktopPet(self.panel)
        self.panel.pet = self.pet
        self.pet.activity_timer.stop()
        self.pet.timer.stop()

    def tearDown(self):
        self.panel.focus_mode.abandon()
        self.panel.tray.hide()
        self.pet.close()
        self.panel.closing = True
        self.panel.close()
        self.panel.deleteLater()
        APP.processEvents()
        self.pref_patch.stop()
        self.temp.cleanup()

class PanelRestTest(PanelCase):
    def test_settings_rest_page_saves(self):
        from widget import Settings
        settings = Settings(self.panel)
        self.assertEqual(settings.sit.currentData(), 60)
        settings.night_enabled.setChecked(False)
        self.assertFalse(settings.night_start.isEnabled())
        settings.sit.setCurrentIndex(settings.sit.findData(0))
        settings.app_time.setChecked(True)
        with mock.patch('widget.write_preferences'):
            settings.save()
        self.assertFalse(self.panel.prefs['night_enabled'])
        self.assertEqual(self.panel.prefs['sit_minutes'], 0)
        self.assertTrue(self.panel.prefs['app_time_enabled'])
        self.assertIsNone(self.panel.app_time_tracker)       # Never records from a test panel.
        settings.deleteLater()

    def test_night_pose_and_menu_switch(self):
        self.pet.mood_enabled = False
        night = self.panel.night_mode
        with mock.patch('pet_assets.has_own_art', return_value=True):
            night.toggle()
            self.assertTrue(night.active)
            self.pet.update_activity()
            self.assertEqual(self.pet.current_state, 'night_idle')
            night.toggle()
            self.assertEqual(self.pet.current_state, 'idle')

    def test_sit_reminder_makes_her_stretch(self):
        self.pet.show()
        self.panel._sit_too_long()
        self.assertEqual(self.pet.interaction_state, 'stretch_break')

    def test_app_time_report_lists_programs(self):
        import time as clock
        from report_view import ReportPage
        store = self.panel.app_time_store
        store.add('code.exe', 'Visual Studio Code', 3 * 3600, clock.time())
        store.add('chrome.exe', 'Google Chrome', 20 * 60, clock.time())
        store.add('blip.exe', 'Blip', 5, clock.time())
        page = ReportPage(self.panel, loader=lambda: None)
        page.show_sub(2)
        view = page.app_time
        self.assertEqual(view.list.topLevelItemCount(), 2)   # Under 30 s left out.
        self.assertEqual(view.list.topLevelItem(0).text(0), 'Visual Studio Code')
        self.assertIn('3', view.total.text())
        view.clear()
        self.assertEqual(view.list.topLevelItemCount(), 0)
        self.assertTrue(view.empty.isVisibleTo(view))
        page.deleteLater()


class ChangeTest(PanelCase):
    def test_the_change_plays_step_by_step_and_ends_in_pajamas(self):
        import night_mode as nm
        self.pet.mood_enabled = False
        self.pet.show()
        steps = self.panel.night_mode.change_steps(True)
        self.assertEqual(steps, nm.CHANGE_ON)                 # The art is in the repository.
        quick = tuple((pose, 0.01) for pose, _s in steps)
        with mock.patch.object(self.panel.night_mode, 'change_steps', return_value=quick):
            self.panel.night_mode.toggle()
            self.assertEqual(self.pet.current_state, 'night_change_0')
            import time as clock
            deadline = clock.monotonic() + 3
            while self.pet.change_state is not None and clock.monotonic() < deadline:
                APP.processEvents()
            self.assertIsNone(self.pet.change_state)
            self.assertEqual(self.pet.current_state, 'night_idle')
            self.panel.game_mode.active = True               # Never during a game.
            self.panel.night_mode.toggle()
            self.assertIsNone(self.pet.change_state)
            self.panel.game_mode.active = False

    def test_a_newer_change_replaces_the_old_one(self):
        self.pet.show()
        self.pet.play_change((('night_change_0', 5), ('night_change_1', 5)))
        self.pet.play_change((('night_settle_2', 5),))
        self.assertEqual(self.pet.change_state, 'night_settle_2')

    def test_gentle_fade_between_change_steps(self):
        import pet_motion
        animator = pet_motion.Animator()
        animator.set_state('idle', 0)
        animator.set_state('night_change_0', 1)
        self.assertEqual(animator.fade_s, pet_motion.GENTLE_FADE_S)
        animator.set_state('typing', 2)
        self.assertEqual(animator.fade_s, pet_motion.GENTLE_FADE_S)   # Leaving the change is gentle too.
        animator.set_state('idle', 3)
        self.assertEqual(animator.fade_s, pet_motion.CROSSFADE_S)
