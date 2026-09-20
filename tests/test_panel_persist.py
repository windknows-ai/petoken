"""V1.1 polish slice: panel proportions, pin persistence, always-on-top."""
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QApplication

from app_config import load_preferences
from pet import DesktopPet
from widget import PANEL_DEFAULT, PANEL_MAX, PANEL_MIN, Panel, Settings, valid_panel_size


class PanelPersistTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.pref_dir = Path(self.temp.name)
        self.pref_patch = patch('widget.PREF_DIR', self.pref_dir)
        self.pref_patch.start()
        self.panels = []

    def tearDown(self):
        for panel in self.panels:
            panel.tray.hide()
            if panel.analytics_window:
                panel.analytics_window.close()
            if hasattr(panel, 'pet'):
                panel.pet.close()
            panel.closing = True
            panel.close()
            panel.deleteLater()
        self.app.processEvents()
        self.pref_patch.stop()
        self.temp.cleanup()

    def make_panel(self, prefs=None):
        if prefs is not None:
            (self.pref_dir / 'settings.json').write_text(json.dumps(prefs), encoding='utf-8')
        panel = Panel(live=False)
        self.panels.append(panel)
        return panel

    def attach_pet(self, panel):
        panel.pet = DesktopPet(panel)
        panel.pet.activity_timer.stop()
        return panel.pet

    # -- defaults and migration -------------------------------------------

    def test_new_window_preferences_default_sane(self):
        prefs = load_preferences(self.pref_dir / 'settings.json')
        self.assertTrue(prefs['always_on_top'])
        self.assertFalse(prefs['panel_pinned'])

    def test_legacy_topmost_migrates_once_to_always_on_top(self):
        (self.pref_dir / 'a.json').write_text(json.dumps({'topmost': False}), encoding='utf-8')
        self.assertFalse(load_preferences(self.pref_dir / 'a.json')['always_on_top'])
        (self.pref_dir / 'b.json').write_text(json.dumps({'topmost': True}), encoding='utf-8')
        self.assertTrue(load_preferences(self.pref_dir / 'b.json')['always_on_top'])
        (self.pref_dir / 'c.json').write_text(
            json.dumps({'topmost': False, 'always_on_top': True}), encoding='utf-8')
        self.assertTrue(load_preferences(self.pref_dir / 'c.json')['always_on_top'])

    def test_non_boolean_window_preferences_fall_back_to_defaults(self):
        (self.pref_dir / 's.json').write_text(
            json.dumps({'always_on_top': 'yes', 'panel_pinned': 'no'}), encoding='utf-8')
        prefs = load_preferences(self.pref_dir / 's.json')
        self.assertTrue(prefs['always_on_top'])
        self.assertFalse(prefs['panel_pinned'])

    def test_legacy_topmost_key_is_preserved_untouched(self):
        (self.pref_dir / 's.json').write_text(
            json.dumps({'scope': 'project', 'topmost': False}), encoding='utf-8')
        loaded = load_preferences(self.pref_dir / 's.json')
        self.assertFalse(loaded['topmost'])
        self.assertFalse(loaded['always_on_top'])

    # -- always-on-top ------------------------------------------------------

    def test_topmost_flags_follow_preference_for_panel_and_pet(self):
        panel = self.make_panel({'always_on_top': False})
        pet = self.attach_pet(panel)
        self.assertFalse(bool(panel.windowFlags() & Qt.WindowStaysOnTopHint))
        self.assertFalse(bool(pet.windowFlags() & Qt.WindowStaysOnTopHint))
        panel.set_always_on_top(True)
        self.assertTrue(bool(panel.windowFlags() & Qt.WindowStaysOnTopHint))
        self.assertTrue(bool(pet.windowFlags() & Qt.WindowStaysOnTopHint))
        saved = json.loads((self.pref_dir / 'settings.json').read_text(encoding='utf-8'))
        self.assertTrue(saved['always_on_top'])

    def test_topmost_defaults_keep_windows_on_top(self):
        panel = self.make_panel()
        pet = self.attach_pet(panel)
        self.assertTrue(bool(panel.windowFlags() & Qt.WindowStaysOnTopHint))
        self.assertTrue(bool(pet.windowFlags() & Qt.WindowStaysOnTopHint))

    def test_pet_menu_handler_updates_preference_and_flags(self):
        panel = self.make_panel()
        pet = self.attach_pet(panel)
        pet.toggle_topmost(False)
        self.assertFalse(panel.prefs['always_on_top'])
        self.assertFalse(bool(pet.windowFlags() & Qt.WindowStaysOnTopHint))
        saved = json.loads((self.pref_dir / 'settings.json').read_text(encoding='utf-8'))
        self.assertFalse(saved['always_on_top'])

    def test_settings_checkbox_saves_always_on_top(self):
        panel = self.make_panel()
        settings = Settings(panel)
        try:
            self.assertTrue(settings.topmost.isChecked())
            settings.topmost.setChecked(False)
            with patch('widget.write_preferences') as write:
                settings.save()
            saved = write.call_args.args[0]
            self.assertFalse(saved['always_on_top'])
            self.assertFalse(panel.prefs['always_on_top'])
        finally:
            settings.deleteLater()

    # -- pinned / persistent panel -------------------------------------------

    def test_pin_button_reflects_state_in_both_languages(self):
        panel = self.make_panel({'language': 'en'})
        self.assertFalse(panel.is_pinned())
        self.assertFalse(panel.pin.isChecked())
        self.assertEqual(panel.pin.text(), '◇')
        self.assertEqual(panel.pin.toolTip(), 'Pin panel open')
        panel.toggle_pin()
        self.assertTrue(panel.is_pinned())
        self.assertEqual(panel.pin.text(), '◆')
        self.assertEqual(panel.pin.toolTip(), 'Unpin panel')
        panel.prefs['language'] = 'zh_CN'
        panel.apply_language()
        self.assertEqual(panel.pin.toolTip(), '取消固定面板')
        panel.toggle_pin()
        self.assertEqual(panel.pin.toolTip(), '固定面板（保持展开）')

    def test_pin_state_persists_across_restart(self):
        first = self.make_panel()
        first.toggle_pin()
        self.assertTrue(first.prefs['panel_pinned'])
        first.persist()
        second = self.make_panel()
        self.assertTrue(second.is_pinned())
        self.assertTrue(second.pin.isChecked())

    def test_pinned_panel_restores_visible_unpinned_stays_hidden(self):
        pinned = self.make_panel({'panel_pinned': True})
        self.attach_pet(pinned)
        pinned.restore_companion()
        self.assertTrue(pinned.isVisible())
        self.assertTrue(pinned.pet.isVisible())
        plain = self.make_panel({})
        self.assertFalse(plain.isVisible())

    def test_pinned_panel_ignores_cursor_leave_auto_hide(self):
        for pinned_pref, expect_visible in ((False, False), (True, True)):
            panel = self.make_panel({'panel_pinned': pinned_pref})
            pet = self.attach_pet(panel)
            panel.show()
            self.app.processEvents()
            pet.left_since = time.monotonic() - 1.0
            with patch('pet.QCursor.pos', return_value=QPoint(-9999, -9999)):
                pet.update_activity()
            self.app.processEvents()
            self.assertEqual(panel.isVisible(), expect_visible, pinned_pref)
            panel.hide()

    # -- proportions ----------------------------------------------------------

    def test_landscape_proportions_stay_sane_and_clamped(self):
        self.assertEqual(PANEL_MIN, (360, 420))
        self.assertEqual(PANEL_MAX, (600, 640))
        self.assertEqual(PANEL_DEFAULT, (420, 500))
        self.assertGreater(PANEL_DEFAULT[0] + 272, PANEL_DEFAULT[1])
        self.assertEqual(valid_panel_size([500, 500]), [500, 500])
        self.assertEqual(valid_panel_size([10, 9999]), [PANEL_MIN[0], PANEL_MAX[1]])

    def test_default_and_minimum_sizes_show_without_clipping(self):
        from analytics import aggregate, normalize_usage
        tokens = normalize_usage(dict(input_tokens=120000, cached_input_tokens=90000,
            cache_write_input_tokens=0, output_tokens=18000,
            reasoning_output_tokens=7000, total_tokens=138000))
        analytics = aggregate([dict(session='s', model='gpt-6-astra',
            timestamp='2026-09-16T12:00:00Z', event_id='s', tokens=tokens)])
        for size in (PANEL_DEFAULT, PANEL_MIN, PANEL_MAX):
            panel = self.make_panel()
            panel.show()
            panel.resize(*size)
            panel.render(dict(title='Polish fixture', project='petoken',
                model='gpt-6-astra', effort='high', mode='follow', scope='project',
                tokens=tokens, available=True, analytics=analytics, usd=2.19,
                context=42, context_tokens=84000, context_window=200000,
                raw_total=tokens, raw_last=tokens, notes=[], unknown=[],
                partial=False, count=1, session_names={'s': 'S'}))
            self.app.processEvents()
            self.assertEqual((panel.width(), panel.height()), size)
            self.assertFalse(panel.grab().toImage().isNull(), size)
            panel.hide()


if __name__ == '__main__':
    unittest.main()
