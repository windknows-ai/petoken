import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from widget import PANEL_DEFAULT, PANEL_MAX, PANEL_MIN, Panel, valid_panel_size


class ResponsiveTests(unittest.TestCase):
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

    def test_valid_panel_size_clamps_and_rejects_garbage(self):
        self.assertEqual(valid_panel_size([500, 500]), [500, 500])
        self.assertEqual(valid_panel_size([10, 9999]), [PANEL_MIN[0], PANEL_MAX[1]])
        for bad in (None, 'big', [300], ['wide', 'tall'], {}, [None, None], 42):
            self.assertIsNone(valid_panel_size(bad), repr(bad))

    def test_supported_bounds_are_sane(self):
        self.assertEqual(PANEL_MIN, (420, 400))
        self.assertEqual(PANEL_MAX, (650, 800))
        self.assertEqual(PANEL_DEFAULT, (420, 500))
        self.assertGreater(PANEL_DEFAULT[0] + 272, PANEL_DEFAULT[1])

    def test_saved_size_restores_and_survives_restart(self):
        first = self.make_panel({'panel_size': [520, 560]})
        self.assertEqual((first.width(), first.height()), (520, 560))
        first.persist()
        second = self.make_panel()
        self.assertEqual((second.width(), second.height()), (520, 560))

    def test_missing_or_invalid_saved_size_recovers_safely(self):
        self.assertEqual((self.make_panel().width(), self.make_panel().height())[0], 420)
        self.assertEqual((self.make_panel({'panel_size': [1, 99999]}).width(),
                          self.make_panel({'panel_size': [1, 99999]}).height()), (420, 800))
        self.assertEqual((self.make_panel({'panel_size': ['wide', 'tall']}).width(),
                          self.make_panel({'panel_size': ['wide', 'tall']}).height()), (420, 500))

    def test_compact_mode_preserves_saved_expanded_size(self):
        from widget import COMPACT_HEIGHT
        panel = self.make_panel({'panel_size': [520, 560]})
        panel.show()
        panel.toggle_compact()
        self.assertEqual(panel.prefs['panel_size'], [520, 560])
        self.assertEqual(panel.height(), COMPACT_HEIGHT)
        panel.toggle_compact()
        self.assertEqual((panel.width(), panel.height()), (520, 560))
        self.assertEqual(panel.prefs['panel_size'], [520, 560])

    def test_minimum_width_renders_all_scopes_languages_formats_currencies(self):
        from analytics import aggregate, normalize_usage
        from pet import DesktopPet
        panel = self.make_panel()
        panel.pet = DesktopPet(panel)
        panel.pet.activity_timer.stop()
        panel.show()
        panel.resize(*PANEL_MIN)
        panel.fx_data = dict(date='2026-09-18', source='Bank of Canada',
                             rates={'CAD': 1.4, 'EUR': 1.2, 'CNY': 0.2})
        tokens = normalize_usage(dict(input_tokens=120000, cached_input_tokens=90000,
            cache_write_input_tokens=0, output_tokens=18000,
            reasoning_output_tokens=7000, total_tokens=138000))
        analytics = aggregate([dict(session='s', model='gpt-6-astra',
            timestamp='2026-09-16T12:00:00Z', event_id='s', tokens=tokens)])
        for scope in ('global', 'project', 'conversation'):
            for language in ('zh_CN', 'en'):
                for style in ('full', 'compact'):
                    for currency in ('USD', 'CAD', 'EUR', 'CNY'):
                        panel.prefs.update(language=language, token_number_format=style,
                                           currency=currency)
                        panel.apply_language()
                        panel.render(dict(title='Stress task title', project='Stress project',
                            model='gpt-6-astra', effort='high', mode='follow', scope=scope,
                            tokens=tokens, available=True, analytics=analytics, usd=2.19,
                            context=42, context_tokens=84000, context_window=200000,
                            raw_total=tokens, raw_last=tokens, notes=[], unknown=[],
                            partial=False, count=1, session_names={'s': 'S'}))
                        self.app.processEvents()
                        self.assertEqual(panel.width(), PANEL_MIN[0])
                        self.assertFalse(panel.grab().toImage().isNull(),
                                         (scope, language, style, currency))
        self.assertTrue(panel.details_button.isVisible())
        self.assertTrue(panel.settings_button.isVisible())

    def test_grip_resize_updates_size_within_bounds(self):
        from PySide6.QtCore import QPoint, QEvent
        from PySide6.QtGui import QMouseEvent
        from PySide6.QtCore import Qt
        panel = self.make_panel()
        panel.show()
        panel.resize(340, 640)
        grip = panel.size_grip.mapToGlobal(QPoint(2, 2))
        panel.begin_resize(QMouseEvent(QEvent.MouseButtonPress, QPoint(2, 2), grip,
                                       Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
        panel.do_resize(QMouseEvent(QEvent.MouseMove, QPoint(402, 402), grip + QPoint(400, 400),
                                    Qt.NoButton, Qt.LeftButton, Qt.NoModifier))
        self.assertEqual((panel.width(), panel.height()), PANEL_MAX)
        self.assertEqual(panel.prefs['panel_size'], list(PANEL_MAX))
        panel.end_resize(QMouseEvent(QEvent.MouseButtonRelease, QPoint(0, 0), grip,
                                     Qt.LeftButton, Qt.NoButton, Qt.NoModifier))


if __name__ == '__main__':
    unittest.main()
