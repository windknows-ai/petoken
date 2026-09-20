"""Final V1.1 manual-acceptance issues: Settings discoverability (A1),
compact layout (A3), compact-to-expanded restore (A4). Real clicks, real
lifecycle — never slot-only invocation."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from analytics import aggregate, normalize_usage
from widget import COMPACT_HEIGHT, Panel, Settings


def fixture_tokens(total=44570000):
    return normalize_usage(dict(input_tokens=44300000, cached_input_tokens=40000000,
        cache_write_input_tokens=0, output_tokens=268450,
        reasoning_output_tokens=90000, total_tokens=total))


def fixture(tokens, **over):
    analysis = aggregate([dict(session='s', model='gpt-6-astra', event_id='s',
        timestamp='2026-09-20T12:00:00Z', tokens=tokens)])
    data = dict(title='Widget Task', project='Web Project', model='gpt-6-astra',
        effort='high', mode='working', scope='project', tokens=tokens,
        available=True, analytics=analysis, usd=51.59, context=54,
        context_tokens=1, context_window=2, raw_total=tokens, raw_last=tokens,
        notes=[], unknown=[], partial=False, count=1, session_names={'s': 'S'},
        scope_activity=dict(valid=True, active=True))
    data.update(over)
    return data


class CompactAcceptanceTests(unittest.TestCase):
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

    def click(self, button):
        QTest.mouseClick(button, Qt.LeftButton)

    # -- A1: discoverable character-size control ------------------------------

    def test_settings_shows_character_size_with_live_percent(self):
        for language, label in (('zh_CN', '角色大小'), ('en', 'Character Size')):
            panel = self.make_panel({'language': language})
            settings = Settings(panel)
            try:
                settings.show()
                self.app.processEvents()
                self.assertTrue(settings.pet_scale.isVisibleTo(settings))
                self.assertEqual(settings.pet_scale_label.text(), label)
                self.assertEqual(settings.pet_scale.minimum(), 50)
                self.assertEqual(settings.pet_scale.maximum(), 150)
                self.assertEqual(settings.pet_scale.value(), 100)
                self.assertEqual(settings.pet_scale_value.text(), '100%')
            finally:
                settings.deleteLater()

    def test_settings_slider_roundtrip_persists_and_restores(self):
        panel = self.make_panel()
        settings = Settings(panel)
        try:
            settings.pet_scale.setValue(75)
            self.assertEqual(settings.pet_scale_value.text(), '75%')
            settings.save()
        finally:
            settings.deleteLater()
        self.assertEqual(panel.prefs['pet_scale_percent'], 75)
        fresh = self.make_panel()
        self.assertEqual(fresh.prefs['pet_scale_percent'], 75)
        check = Settings(fresh)
        try:
            self.assertEqual(check.pet_scale.value(), 75)
        finally:
            check.deleteLater()

    # -- A4: real-click compact/expanded lifecycle ------------------------------

    def test_real_click_enters_and_exits_compact(self):
        panel = self.make_panel()
        panel.show()
        self.app.processEvents()
        self.click(panel.collapse_button)
        self.app.processEvents()
        self.assertTrue(panel.compact)
        self.assertEqual(panel.collapse_button.text(), '+')
        self.assertEqual(panel.height(), COMPACT_HEIGHT)
        self.click(panel.collapse_button)
        self.app.processEvents()
        self.assertFalse(panel.compact)
        self.assertEqual(panel.collapse_button.text(), '−')
        self.assertTrue(panel.body_scroll.isVisible())

    def test_repeated_real_click_cycles_hold_size(self):
        panel = self.make_panel({'panel_size': [520, 520]})
        panel.show()
        self.app.processEvents()
        for _ in range(4):
            self.click(panel.collapse_button)
            self.app.processEvents()
            self.assertTrue(panel.compact)
            self.assertEqual(panel.height(), COMPACT_HEIGHT)
            self.click(panel.collapse_button)
            self.app.processEvents()
            self.assertFalse(panel.compact)
            self.assertEqual((panel.width(), panel.height()), (520, 520))
        self.assertTrue(panel.collapse_button.isVisible())
        self.assertTrue(panel.pin.isVisible())
        self.assertTrue(panel.settings_button.isVisible())

    def test_expand_restores_last_valid_size_not_default(self):
        panel = self.make_panel({'panel_size': [500, 460]})
        panel.show()
        self.app.processEvents()
        self.assertEqual((panel.width(), panel.height()), (500, 460))
        self.click(panel.collapse_button)
        self.app.processEvents()
        self.click(panel.collapse_button)
        self.app.processEvents()
        self.assertEqual((panel.width(), panel.height()), (500, 460))

    def test_restart_in_compact_then_real_click_expands(self):
        first = self.make_panel()
        first.show()
        self.app.processEvents()
        first.toggle_compact()
        first.persist()
        second = self.make_panel()
        second.show()
        self.app.processEvents()
        self.assertTrue(second.compact)
        self.assertEqual(second.height(), COMPACT_HEIGHT)
        self.click(second.collapse_button)
        self.app.processEvents()
        self.assertFalse(second.compact)
        self.assertTrue(second.body_scroll.isVisible())

    def test_compact_toggle_grants_autohide_grace(self):
        from pet import DesktopPet
        panel = self.make_panel()
        pet = DesktopPet(panel)
        panel.pet = pet
        pet.activity_timer.stop()
        pet.show()
        panel.show()
        self.app.processEvents()
        pet.show_panel()
        self.app.processEvents()
        pet.left_since = 1.0  # stale leave timestamp
        panel.toggle_compact()
        self.assertIsNone(pet.left_since)
        panel.hide()

    # -- A3: intentional compact composition -------------------------------------

    def test_compact_shows_heroes_and_single_control_strip(self):
        panel = self.make_panel({'language': 'en'})
        panel.render(fixture(fixture_tokens()))
        panel.show()
        self.app.processEvents()
        panel.toggle_compact()
        self.app.processEvents()
        self.assertTrue(panel.compact_box.isVisible())
        self.assertFalse(panel.cost_bar.isVisible())
        self.assertFalse(panel.bottom_bar.isVisible())
        self.assertTrue(panel.pin.isVisible())
        self.assertTrue(panel.settings_button.isVisible())
        self.assertIn('44.57M', panel.compact_total.text())
        self.assertEqual(panel.compact_total.text(), panel.total.text())
        self.assertEqual(panel.compact_cost.text(), panel.cost.text())
        self.assertIn('CA$', panel.compact_cost.text())
        self.assertFalse(panel.compact_total.text().startswith(','))
        panel.toggle_compact()
        self.app.processEvents()
        self.assertFalse(panel.compact_box.isVisible())
        self.assertTrue(panel.cost_bar.isVisible())
        self.assertTrue(panel.bottom_bar.isVisible())
        self.assertIn('44.57M', panel.total.text())

    def test_compact_full_and_long_cost_fit_without_overlap(self):
        panel = self.make_panel({'language': 'en', 'token_number_format': 'full'})
        big = fixture_tokens(total=1580246791357)
        panel.render(fixture(big, usd=12345.67))
        panel.show()
        self.app.processEvents()
        panel.toggle_compact()
        for width in (420, 520, 650):
            panel.resize(width, panel.height())
            self.app.processEvents()
            self.assertEqual(panel.height(), COMPACT_HEIGHT, width)
            self.assertFalse(panel.compact_cost.geometry().intersects(
                panel.compact_total.geometry()), width)
            self.assertIn('1,580,246,791,357', panel.compact_total.text())
            self.assertIn('CA$', panel.compact_cost.text())
            self.assertFalse(panel.grab().toImage().isNull(), width)

    def test_compact_renders_both_languages(self):
        for language, cost_word in (('zh_CN', '预估费用'), ('en', 'Estimated Cost')):
            panel = self.make_panel({'language': language})
            panel.render(fixture(fixture_tokens()))
            panel.show()
            self.app.processEvents()
            panel.toggle_compact()
            self.app.processEvents()
            self.assertIn(cost_word, panel.compact_cost_label.text(), language)
            self.assertFalse(panel.grab().toImage().isNull(), language)
            panel.hide()

    def test_compact_unavailable_state_stays_honest(self):
        panel = self.make_panel()
        panel.render(dict(status='status_no_usage', rows=[]))
        panel.show()
        self.app.processEvents()
        panel.toggle_compact()
        self.app.processEvents()
        self.assertEqual(panel.compact_total.text(), '—')
        self.assertEqual(panel.compact_cost.text(), '—')

    def test_pin_and_topmost_survive_compact_cycle(self):
        panel = self.make_panel({'panel_pinned': True, 'always_on_top': True})
        panel.render(fixture(fixture_tokens()))
        panel.show()
        self.app.processEvents()
        panel.toggle_compact()
        self.app.processEvents()
        self.assertTrue(panel.is_pinned())
        self.assertTrue(panel.pin.isChecked())
        self.assertEqual(panel.pin.text(), '◆')
        panel.toggle_compact()
        self.app.processEvents()
        self.assertTrue(panel.pin.isChecked())
        self.assertTrue(bool(panel.windowFlags() & Qt.WindowStaysOnTopHint))
        panel.set_always_on_top(False)
        panel.toggle_compact()
        panel.toggle_compact()
        self.app.processEvents()
        self.assertFalse(bool(panel.windowFlags() & Qt.WindowStaysOnTopHint))

    # -- A2: empty-subtitle honesty at the pet gate --------------------------------

    def test_empty_subtitle_session_shows_no_pill(self):
        from types import SimpleNamespace
        from activity import ActivityState
        panel = self.make_panel()
        from pet import DesktopPet
        panel.pet = DesktopPet(panel)
        panel.pet.activity_timer.stop()
        panel.activity = SimpleNamespace(state=ActivityState(), close=lambda: None,
            status={'microphone': False, 'music': True, 'music_text': None})
        panel.pet.preview_state = 'music'
        panel.pet.update_activity()
        self.assertEqual(panel.pet.current_state, 'music')
        self.assertIsNone(panel.pet.music_subtitle())


if __name__ == '__main__':
    unittest.main()
