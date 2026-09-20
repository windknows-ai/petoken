import json
import re
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QPoint, Qt, QEvent
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

import pet_geometry as geometry
import theme
from analytics import aggregate, normalize_usage
from pet import DesktopPet
from widget import Panel, Settings


def fixture_tokens():
    return normalize_usage(dict(input_tokens=120000, cached_input_tokens=90000,
        cache_write_input_tokens=0, output_tokens=18000,
        reasoning_output_tokens=7000, total_tokens=138000))


def fixture_data(tokens, **overrides):
    analytics = aggregate([dict(session='visual-fixture', model='gpt-6-astra',
        timestamp='2026-09-16T12:00:00Z', event_id='visual', tokens=tokens)])
    data = dict(title='Visual fixture task', project='petoken', model='gpt-6-astra',
        effort='high', mode='follow', scope='project', tokens=tokens, available=True,
        analytics=analytics, usd=2.19, context=42, context_tokens=84000,
        context_window=200000, raw_total=tokens, raw_last=tokens, notes=[],
        unknown=[], partial=False, count=1, session_names={'visual-fixture': 'Visual fixture'},
        working_context=dict(project='petoken', title='Visual fixture task', model='gpt-6-astra',
            effort='high', context=42, tokens=tokens))
    data.update(overrides)
    return data


class RedesignTests(unittest.TestCase):
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

    def tearDown(self):
        self.panel.pet.close()
        self.panel.tray.hide()
        if self.panel.analytics_window:
            self.panel.analytics_window.close()
        self.panel.closing = True
        self.panel.close()
        self.panel.deleteLater()
        self.app.processEvents()
        self.pref_patch.stop()
        self.temp.cleanup()

    def force_token_mode(self, data):
        if not self.panel.app_mode.is_token:
            self.panel.app_mode.update(True, True)
            self.panel.app_mode.update(True, True, self.panel.app_mode.pending_since + 1.0)
        self.panel.pet.update_data(data)

    def test_daily_mode_has_no_token_card(self):
        self.panel.render(dict(status='status_no_usage', rows=[]))
        self.assertFalse(self.panel.pet.token_bubble_visible())
        pixel = self.panel.pet.grab().toImage().pixelColor(121, 30)
        self.assertEqual(pixel.alpha(), 0)

    def test_token_mode_shows_compact_card(self):
        data = fixture_data(fixture_tokens())
        self.panel.render(data)
        self.force_token_mode(data)
        self.assertTrue(self.panel.pet.token_bubble_visible())
        pixel = self.panel.pet.grab().toImage().pixelColor(121, 30)
        self.assertGreater(pixel.alpha(), 0)

    def test_card_uses_same_working_context_project_and_tokens(self):
        data = fixture_data(fixture_tokens())
        self.panel.render(data)
        self.force_token_mode(data)
        tip = self.panel.pet.toolTip()
        self.assertIn('petoken', tip)
        self.assertIn('138.00K', tip)

    def test_long_project_name_truncates_safely(self):
        tokens = fixture_tokens()
        data = fixture_data(tokens, project='P' * 200,
            working_context=dict(project='P' * 200, title='T', model='m',
                                 effort='high', context=1, tokens=tokens))
        self.panel.render(data)
        self.force_token_mode(data)
        self.app.processEvents()
        self.assertEqual(self.panel.pet.width(), geometry.window_size()[0])
        self.assertFalse(self.panel.pet.grab().toImage().isNull())

    def test_full_and_compact_formats_both_fit(self):
        tokens = fixture_tokens()
        for style in ('full', 'compact'):
            self.panel.prefs['token_number_format'] = style
            data = fixture_data(tokens)
            self.panel.render(data)
            self.force_token_mode(data)
            self.app.processEvents()
            self.assertEqual(self.panel.pet.width(), geometry.window_size()[0])
            self.assertFalse(self.panel.pet.grab().toImage().isNull())

    def test_card_fits_both_languages(self):
        tokens = fixture_tokens()
        for language in ('zh_CN', 'en'):
            self.panel.prefs['language'] = language
            self.panel.apply_language()
            data = fixture_data(tokens)
            self.panel.render(data)
            self.force_token_mode(data)
            self.app.processEvents()
            self.assertEqual(self.panel.pet.width(), geometry.window_size()[0])
            self.assertFalse(self.panel.pet.grab().toImage().isNull())

    def test_quota_bars_keep_values_and_resets(self):
        self.panel.show()
        self.app.processEvents()
        self.panel.render(fixture_data(fixture_tokens()))
        self.panel.receive_limits(dict(sampled=time.time(), limits={
            'primary': {'usedPercent': 30, 'windowDurationMins': 300,
                        'resetsAt': time.time() + 1800}}))
        self.assertIn('70%', self.panel.five.value.text())
        self.assertTrue(self.panel.five.reset.isVisible())

    def test_expanded_core_sections_and_navigation(self):
        for name in ('total', 'io_line', 'status_text', 'scope_button', 'context', 'five', 'week',
                     'cost', 'details_button', 'settings_button', 'status'):
            self.assertIsNotNone(getattr(self.panel, name), name)
        self.panel.show()
        self.panel.open_analytics()
        self.app.processEvents()
        self.assertTrue(self.panel.analytics_window.isVisible())
        settings = Settings(self.panel)
        self.assertTrue(settings.currency.count() >= 4)
        settings.reject()

    def test_panel_drag_moves_and_persists(self):
        self.panel.show()
        start = self.panel.pos()
        press = QMouseEvent(QEvent.MouseButtonPress, QPoint(10, 10),
                            QPoint(start.x() + 10, start.y() + 10),
                            Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        move = QMouseEvent(QEvent.MouseMove, QPoint(-20, -10),
                           QPoint(start.x() - 20, start.y() - 10),
                           Qt.NoButton, Qt.LeftButton, Qt.NoModifier)
        self.panel.begin_drag(press)
        self.panel.drag(move)
        self.assertEqual(self.panel.pos() - start, QPoint(-30, -20))
        self.panel.end_drag(move)
        self.assertEqual(self.panel.prefs['position'], [self.panel.pos().x(), self.panel.pos().y()])

    def test_offscreen_saved_position_recovers_on_screen(self):
        pref_dir = Path(self.temp.name)
        (pref_dir / 'settings.json').write_text(json.dumps({'position': [-5000, -5000]}),
                                                encoding='utf-8')
        second = Panel(live=False)
        try:
            screen = self.app.primaryScreen().availableGeometry()
            self.assertGreaterEqual(second.x(), screen.left())
            self.assertGreaterEqual(second.y(), screen.top())
        finally:
            second.tray.hide()
            second.closing = True
            second.close()
            second.deleteLater()
            self.app.processEvents()

    def test_resize_stays_within_minimums_and_persists(self):
        self.assertEqual((self.panel.minimumWidth(), self.panel.minimumHeight()), (360, 420))
        self.panel.show()
        self.app.processEvents()
        self.panel.resize(520, 560)
        self.assertEqual((self.panel.width(), self.panel.height()), (520, 560))
        self.assertTrue(self.panel.body_scroll.isVisible())
        grip = self.panel.size_grip.mapToGlobal(QPoint(2, 2))
        press = QMouseEvent(QEvent.MouseButtonPress, QPoint(2, 2), grip,
                            Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        self.panel.begin_resize(press)
        target = grip + QPoint(60, 60)
        move = QMouseEvent(QEvent.MouseMove, QPoint(62, 62), target,
                           Qt.NoButton, Qt.LeftButton, Qt.NoModifier)
        before = self.panel.size()
        self.panel.do_resize(move)
        self.assertGreaterEqual(self.panel.width(), before.width())
        self.assertIn('panel_size', self.panel.prefs)
        self.panel.end_resize(move)

    def test_compact_hides_body_and_stays_small(self):
        self.panel.show()
        self.panel.toggle_compact()
        self.assertFalse(self.panel.body_scroll.isVisible())
        self.assertLessEqual(self.panel.height(), 280)
        self.assertFalse(self.panel.size_grip.isVisible())
        self.panel.toggle_compact()
        self.assertTrue(self.panel.body_scroll.isVisible())

    def test_redesign_changes_no_data_semantics(self):
        tokens = fixture_tokens()
        self.panel.prefs['language'] = 'zh_CN'
        self.panel.apply_language()
        self.panel.render(fixture_data(tokens))
        before = (dict(self.panel.snapshot['tokens']), self.panel.snapshot['scope'],
                  self.panel.snapshot['usd'])
        self.panel.prefs['language'] = 'en'
        self.panel.apply_language()
        self.panel.render(fixture_data(tokens))
        scope_before = self.panel.prefs['scope']
        after = (dict(self.panel.snapshot['tokens']), self.panel.snapshot['scope'],
                 self.panel.snapshot['usd'])
        self.assertEqual(before, after)
        self.assertEqual(self.panel.prefs['scope'], scope_before)

    def test_theme_tokens_are_well_formed(self):
        colors = [theme.INK, theme.MUTED, theme.ICE, theme.VIOLET, theme.BG,
                  theme.SURFACE_TOP, theme.SURFACE_BOTTOM, theme.CARD, theme.TABLE_BG,
                  theme.TABLE_ALT, theme.TABLE_HEADER, theme.BADGE_BG, theme.CONTROL_BG,
                  theme.BORDER, theme.BORDER_SOFT, theme.BORDER_CONTROL, theme.TRACK,
                  theme.DIVIDER, theme.GRID, theme.HOVER_BG, theme.HOVER_BORDER,
                  theme.CHECKED_BG, theme.MENU_BG, theme.MENU_SELECTED, theme.TOOLTIP_BG,
                  theme.TOOLTIP_BORDER, theme.TAB_PANE_BORDER, theme.TAB_SELECTED_BG]
        for color in colors:
            self.assertRegex(color, r'^#[0-9A-Fa-f]{6}$', color)
        for radius in (theme.RADIUS_SURFACE, theme.RADIUS_CARD, theme.RADIUS_BADGE,
                       theme.RADIUS_BUTTON, theme.RADIUS_BAR):
            self.assertIsInstance(radius, int)
            self.assertGreater(radius, 0)


if __name__ == '__main__':
    unittest.main()
