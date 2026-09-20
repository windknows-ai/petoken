"""Anchored companion: real state, window lifecycle and source-density rendering."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QApplication

import pet_assets as assets
from pet import DesktopPet
from widget import PANEL_DEFAULT, PANEL_MAX, PANEL_MIN, Panel, Settings


class CompanionTests(unittest.TestCase):
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

    def test_open_close_reopen_keeps_one_pet_at_same_position(self):
        panel = self.make_panel()
        pet = self.attach_pet(panel)
        pet.show()
        original = pet.pos()
        for _ in range(2):
            pet.show_panel()
            self.app.processEvents()
            self.assertTrue(pet.isVisible())
            self.assertEqual(pet.pos(), original)
            self.assertFalse(panel.geometry().intersects(pet.geometry()))
            self.assertFalse(hasattr(panel, 'stage'))
            self.assertTrue(pet.timer.isActive())
            panel.hide()
            self.app.processEvents()
            self.assertEqual(pet.pos(), original)
            self.assertTrue(pet.isVisible())

    def test_hidden_pet_is_not_revealed_by_panel(self):
        panel = self.make_panel()
        pet = self.attach_pet(panel)
        panel.show()
        panel.hide()
        self.assertFalse(pet.isVisible())

    def test_user_can_toggle_pet_without_closing_panel(self):
        panel = self.make_panel()
        pet = self.attach_pet(panel)
        pet.show_panel()
        panel.toggle_pet()
        self.assertTrue(pet.isVisible())
        self.assertTrue(panel.isVisible())
        panel.toggle_pet()
        self.assertFalse(pet.isVisible())
        self.assertTrue(panel.isVisible())

    def test_drag_moves_satellite_and_reopen_uses_latest_anchor(self):
        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QMouseEvent
        panel = self.make_panel()
        pet = self.attach_pet(panel)
        pet.show()
        pet.show_panel()
        before = pet.pos()
        previous_panel = panel.pos()
        local = QPoint(100, 160)
        start = pet.mapToGlobal(local)
        pet.mousePressEvent(QMouseEvent(QEvent.MouseButtonPress, local, start,
                            Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
        pet.mouseMoveEvent(QMouseEvent(QEvent.MouseMove, local, start+QPoint(-50, -40),
                           Qt.NoButton, Qt.LeftButton, Qt.NoModifier))
        pet.mouseReleaseEvent(QMouseEvent(QEvent.MouseButtonRelease, local, start+QPoint(-50, -40),
                              Qt.LeftButton, Qt.NoButton, Qt.NoModifier))
        self.app.processEvents()
        self.assertNotEqual(pet.pos(), before)
        self.assertNotEqual(panel.pos(), previous_panel)
        self.assertFalse(panel.geometry().intersects(pet.geometry()))
        moved = pet.pos()
        docked = panel.pos()
        panel.hide()
        pet.show_panel()
        self.assertEqual(pet.pos(), moved)
        self.assertEqual(panel.pos(), docked)
        saved = json.loads((self.pref_dir/'settings.json').read_text(encoding='utf-8'))
        self.assertEqual(saved['pet_position'], [pet.x(), pet.y()])

    def test_click_open_close_never_writes_saved_pet_position(self):
        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QMouseEvent
        panel = self.make_panel()
        pet = self.attach_pet(panel)
        pet.show()
        original = dict(panel.prefs)
        local = QPoint(100, 160)
        point = pet.mapToGlobal(local)
        with patch.object(panel, 'persist') as persist:
            for _ in range(4):
                pet.mousePressEvent(QMouseEvent(QEvent.MouseButtonPress, local, point,
                    Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
                pet.mouseReleaseEvent(QMouseEvent(QEvent.MouseButtonRelease, local, point,
                    Qt.LeftButton, Qt.NoButton, Qt.NoModifier))
            persist.assert_not_called()
        self.assertEqual(panel.prefs, original)

    def test_resize_and_compact_keep_anchor_on_its_screen(self):
        panel = self.make_panel()
        pet = self.attach_pet(panel)
        pet.show()
        pet.show_panel()
        anchor = pet.pos()
        screen = pet.screen().availableGeometry()
        for size in (PANEL_MIN, PANEL_MAX):
            panel.resize(*size)
            self.app.processEvents()
            self.assertTrue(screen.contains(panel.geometry()))
            self.assertFalse(panel.geometry().intersects(pet.geometry()))
            self.assertEqual(pet.pos(), anchor)
        panel.toggle_compact()
        self.app.processEvents()
        self.assertEqual(pet.pos(), anchor)
        self.assertTrue(pet.isVisible())
        self.assertFalse(panel.geometry().intersects(pet.geometry()))

    def test_real_activity_stays_live_with_panel_open(self):
        import time
        from PySide6.QtTest import QTest
        panel = self.make_panel()
        pet = self.attach_pet(panel)
        pet.show()
        pet.show_panel()
        state = panel.activity.state
        now = time.monotonic()
        state.sample(True, True, now-1)
        state.sample(True, True, now)
        state.key(now)
        pet.update_activity()
        self.assertEqual(pet.current_state, 'microphone')
        state.stable['microphone'] = False
        pet.update_activity()
        self.assertEqual(pet.current_state, 'music')
        state.stable['music'] = False
        pet.update_activity()
        self.assertEqual(pet.current_state, 'typing')
        panel.app_mode.update(True, True, now=1)
        panel.app_mode.update(True, True, now=2)
        state.last_key = 0
        pet.update_activity()
        self.assertEqual(pet.current_state, 'working')
        phase = pet.phase
        QTest.qWait(180)
        self.assertGreater(pet.phase, phase)
        panel.app_mode.update(False, True, now=3)
        panel.app_mode.update(False, True, now=6)
        pet.update_activity()
        self.assertEqual(pet.current_state, 'idle')
        pet.toggle_motion(False)
        phase = pet.phase
        QTest.qWait(110)
        self.assertEqual(pet.phase, phase)

    def test_pinned_real_startup_order_docks_without_replacing_character(self):
        panel = self.make_panel({'panel_pinned': True})
        self.assertFalse(panel.isVisible())
        pet = self.attach_pet(panel)
        anchor = pet.pos()
        panel.restore_companion()
        self.app.processEvents()
        self.assertTrue(panel.isVisible())
        self.assertTrue(pet.isVisible())
        self.assertEqual(pet.pos(), anchor)
        self.assertFalse(panel.geometry().intersects(pet.geometry()))

    def test_topmost_both_directions_preserve_visible_windows_and_positions(self):
        panel = self.make_panel()
        pet = self.attach_pet(panel)
        pet.show()
        for expanded in (False, True):
            if expanded:
                pet.show_panel()
            positions = (pet.pos(), panel.pos())
            for enabled in (False, True):
                panel.set_always_on_top(enabled)
                self.app.processEvents()
                self.assertTrue(pet.isVisible())
                self.assertEqual(panel.isVisible(), expanded)
                self.assertEqual((pet.pos(), panel.pos()), positions)
                for window in (pet, panel):
                    self.assertEqual(bool(window.windowFlags() & Qt.WindowStaysOnTopHint), enabled)

    def test_settings_applies_topmost_without_moving_anchor(self):
        panel = self.make_panel()
        pet = self.attach_pet(panel)
        pet.show()
        pet.show_panel()
        anchor = pet.pos()
        settings = Settings(panel)
        settings.topmost.setChecked(False)
        settings.save()
        self.app.processEvents()
        for window in (panel, pet):
            self.assertFalse(bool(window.windowFlags() & Qt.WindowStaysOnTopHint))
            self.assertTrue(window.isVisible())
        self.assertEqual(pet.pos(), anchor)
        settings.deleteLater()

    def test_render_density_cache_and_aspect_ratio(self):
        from PySide6.QtGui import QPixmap
        panel = self.make_panel()
        pet = self.attach_pet(panel)
        original = pet.sprites['idle']
        for dpr in (1.0, 1.25, 2.0):
            with patch.object(pet, 'devicePixelRatioF', return_value=dpr):
                result = pet.render_sprite(original)
                self.assertEqual((result.width(), result.height()), (round(256*dpr),)*2)
                self.assertEqual(result.devicePixelRatioF(), dpr)
                self.assertEqual(pet.render_sprite(original).cacheKey(), result.cacheKey())
                self.assertEqual(result.toImage().pixelColor(0, 0).alpha(), 0)
                self.assertEqual(len(pet._render_cache), 1)
                tall = QPixmap(100, 200)
                tall.fill(Qt.white)
                fitted = pet.render_sprite(tall)
                self.assertEqual(fitted.width()*2, fitted.height())

    def test_panel_position_uses_work_area_with_negative_monitor_coordinates(self):
        import pet_geometry as geometry
        from PySide6.QtCore import QRect
        screen = (-1920, -100, -1, 979)
        for pet_rect in ((-300, 600, 272, 330), (-1910, 600, 272, 330),
                         (-1100, -100, 272, 330)):
            point = geometry.panel_position(pet_rect, (420, 500), screen)
            panel_rect = QRect(*point, 420, 500)
            self.assertTrue(QRect(-1920, -100, 1920, 1080).contains(panel_rect))
            self.assertFalse(panel_rect.intersects(QRect(*pet_rect)))

    def test_panel_position_clamps_roomier_side_when_neither_fits(self):
        import pet_geometry as geometry
        from PySide6.QtCore import QRect
        pet = (250, 650, 272, 330)
        point = geometry.panel_position(pet, (420, 500), (0, 0, 799, 999))
        rect = QRect(*point, 420, 500)
        self.assertTrue(QRect(0, 0, 800, 1000).contains(rect))
        self.assertEqual(point, (380, 480))
        self.assertEqual(pet, (250, 650, 272, 330))

    def test_right_preferred_and_left_fallback_are_deterministic(self):
        import pet_geometry as geometry
        screen = (0, 0, 1919, 1079)
        self.assertEqual(geometry.panel_position((700, 600, 272, 330), (420, 500), screen), (984, 430))
        self.assertEqual(geometry.panel_position((1500, 600, 272, 330), (420, 500), screen), (1068, 430))
        self.assertEqual(geometry.panel_position((0, 0, 272, 330), (420, 500), screen), (284, 0))

    def test_live_typing_frames_alternate_without_repositioning(self):
        import time
        panel = self.make_panel()
        pet = self.attach_pet(panel)
        pet.show()
        pet.show_panel()
        original = pet.pos()
        now = time.monotonic()
        images = []
        for stamp in (now, now + .2):
            panel.activity.state.key(stamp)
            pet.update_activity()
            self.assertEqual(pet.current_state, 'typing')
            images.append(pet.render_sprite(assets.frame_for('typing', pet.typing_phase())).toImage())
            self.assertEqual(pet.pos(), original)
        self.assertNotEqual(images[0], images[1])

    def fixture_data(self, huge=False):
        from analytics import aggregate, normalize_usage
        tokens = normalize_usage(dict(input_tokens=1_234_567_890_123 if huge else 100,
            cached_input_tokens=80, output_tokens=345_678_901_234 if huge else 20,
            reasoning_output_tokens=12))
        analysis = aggregate([dict(session='fixture', model='fixture-model',
            timestamp='2026-09-20T12:00:00Z', event_id='fixture', tokens=tokens)])
        return dict(title='Fixture', project='Fixture project', scope='conversation',
            mode='fixed', tokens=tokens, analytics=analysis, history=analysis,
            current_session=analysis, available=True, usd=0, raw_total=tokens,
            scope_activity=dict(valid=True, active=False))

    def test_analytics_session_columns_match_values_in_both_languages(self):
        from localization import text
        panel = self.make_panel({'token_number_format': 'full'})
        panel.render(self.fixture_data())
        panel.open_analytics()
        for language in ('en', 'zh_CN'):
            panel.prefs['language'] = language
            panel.apply_language()
            table = panel.analytics_window.sessions
            headers = ['header_input_tokens', 'header_cached_tokens', 'header_uncached_tokens',
                       'header_write_tokens', 'header_output_tokens', 'header_reasoning_tokens',
                       'header_nonreasoning_tokens', 'header_total_tokens']
            values = ['100 Tokens', '80 Tokens', '20 Tokens', 'N/A', '20 Tokens',
                      '12 Tokens', '8 Tokens', '120 Tokens']
            for column, (header, value) in enumerate(zip(headers, values), 1):
                self.assertEqual(table.horizontalHeaderItem(column).text(), text(header, language))
                self.assertEqual(table.item(0, column).text(), value)

    def test_full_trillion_values_fit_actual_minimum_viewport(self):
        panel = self.make_panel({'token_number_format': 'full'})
        for language in ('zh_CN', 'en'):
            panel.prefs['language'] = language
            panel.apply_language()
            panel.render(self.fixture_data(huge=True))
            panel.show()
            panel.resize(*PANEL_MIN)
            self.app.processEvents()
            self.assertEqual(panel.total.text(), '1,580,246,791,357')
            self.assertLessEqual(panel.total.fontMetrics().horizontalAdvance(panel.total.text()), panel.total.width())
            self.assertLessEqual(panel.body.width(), panel.body_scroll.viewport().width())
            self.assertTrue(panel.io_line.wordWrap())
            self.assertLessEqual(panel.io_line.heightForWidth(panel.io_line.width()), panel.io_line.height())

    def test_unavailable_clears_old_metrics_tables_and_tooltips_then_recovers(self):
        panel = self.make_panel()
        data = self.fixture_data()
        panel.render(data)
        panel.open_analytics()
        analytics = panel.analytics_window
        self.assertGreater(analytics.days.rowCount(), 0)
        panel.render(dict(status='status_pinned_unavailable', scope='project'))
        self.assertIn('N/A', panel.insights.text())
        self.assertNotIn('Fixture', analytics.subtitle.text())
        for table in (analytics.metrics, analytics.models, analytics.sessions, analytics.ranges, analytics.days):
            self.assertEqual(table.rowCount(), 0)
        self.assertEqual(analytics.raw.toPlainText(), '')
        self.assertNotIn('120', panel.total.toolTip())
        panel.render(data)
        self.assertEqual(analytics.sessions.rowCount(), 1)
        panel.render(dict(data, history=None))
        self.assertEqual(analytics.days.rowCount(), 0)
        self.assertEqual(analytics.ranges.rowCount(), 0)

    def test_selected_context_status_does_not_borrow_global_activity(self):
        panel = self.make_panel({'language': 'en'})
        data = self.fixture_data()
        panel.app_mode.update(True, True, now=1)
        panel.app_mode.update(True, True, now=2)
        panel.render(dict(data, codex_activity=dict(active=True, valid=True),
            working_context=dict(project='Unrelated working project', tokens={'total_tokens':999})))
        self.assertEqual(panel.status_text.text(), 'Idle')
        self.assertEqual(panel.project.text(), 'FIXTURE PROJECT')
        panel.render(dict(data, scope_activity=dict(active=True, valid=True)))
        self.assertEqual(panel.status_text.text(), 'Working')
        panel.render(dict(data, scope_activity=dict(active=False, valid=False)))
        self.assertEqual(panel.status_text.text(), 'Unknown')

    def test_diagnostics_allowlist_never_contains_media_content(self):
        from activity import activity_diagnostics
        status = dict(microphone=True, music=False, music_text=dict(
            text='private subtitle', identity=('private app', 'private title', 'private artist')),
            arbitrary_new_field='private future metadata')
        self.assertEqual(activity_diagnostics(status), dict(microphone=True, music=False))
        self.assertNotIn('private', json.dumps(activity_diagnostics(status)))
        self.assertEqual(activity_diagnostics({'microphone':'private text'}), dict(microphone=None, music=None))

    # -- data integration ------------------------------------------------------

    def test_io_line_carries_both_values_and_status_follows_mode(self):
        from analytics import aggregate, normalize_usage
        panel = self.make_panel({'language': 'en'})
        tokens = normalize_usage(dict(input_tokens=120000, cached_input_tokens=90000,
            cache_write_input_tokens=0, output_tokens=18000,
            reasoning_output_tokens=7000, total_tokens=138000))
        analytics = aggregate([dict(session='s', model='gpt-6-astra',
            timestamp='2026-09-16T12:00:00Z', event_id='s', tokens=tokens)])
        panel.render(dict(title='T', project='P', model='gpt-6-astra', effort='high',
            mode='follow', scope='project', tokens=tokens, available=True,
            scope_activity=dict(active=False, valid=True),
            analytics=analytics, usd=1.0, context=10, context_tokens=1,
            context_window=10, raw_total=tokens, raw_last=tokens, notes=[],
            unknown=[], partial=False, count=1, session_names={'s': 'S'}))
        self.assertIn('120.00K', panel.io_line.text())
        self.assertIn('18.00K', panel.io_line.text())
        self.assertEqual(panel.status_text.text(), 'Idle')
        panel.app_mode.update(True, True)
        panel.app_mode.update(True, True, panel.app_mode.pending_since + 1.0)
        panel.render(dict(title='T', project='P', model='gpt-6-astra', effort='high',
            mode='working', scope='project', tokens=tokens, available=True,
            scope_activity=dict(active=True, valid=True),
            analytics=analytics, usd=1.0, context=10, context_tokens=1,
            context_window=10, raw_total=tokens, raw_last=tokens, notes=[],
            unknown=[], partial=False, count=1, session_names={'s': 'S'}))
        self.assertEqual(panel.status_text.text(), 'Working')

    def test_compact_keeps_identity_and_hides_scroll(self):
        panel = self.make_panel()
        panel.show()
        panel.toggle_compact()
        self.app.processEvents()
        self.assertFalse(panel.body_scroll.isVisible())
        self.assertLessEqual(panel.height(), 280)
        self.assertTrue(panel.title.isVisible())
        panel.toggle_compact()
        self.app.processEvents()
        self.assertTrue(panel.body_scroll.isVisible())

    def test_minimum_size_keeps_identity_controls(self):
        panel = self.make_panel()
        panel.show()
        panel.resize(*PANEL_MIN)
        self.app.processEvents()
        self.assertEqual((panel.width(), panel.height()), PANEL_MIN)
        self.assertFalse(panel.grab().toImage().isNull())
        self.assertTrue(panel.details_button.isVisible())
        self.assertTrue(panel.settings_button.isVisible())
        self.assertTrue(panel.pin.isVisible())


if __name__ == '__main__':
    unittest.main()
