"""Fixed overview and explicit native pet controls; isolated preference files."""
import os as _os
import tempfile as _tempfile
# Hermetic Claude lane: a never-created home keeps real ~/.claude data out.
_os.environ.setdefault('PETOKEN_CLAUDE_HOME', _os.path.join(
    _tempfile.gettempdir(), 'petoken-tests-no-claude-home'))
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QScrollArea

from analytics import aggregate, normalize_usage
from pet import DesktopPet
from provider_poller import ProviderPoller
from tests.test_providers import write_home
from tools.preview_v1_3 import fixture_tasks
from usage import CodexStore
from widget import COMPACT_HEIGHT, HUB_SIZE, Panel


class HubInteractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.pref_patch = patch('widget.PREF_DIR', Path(self.temp.name))
        self.pref_patch.start()
        self.panel = Panel(live=False)
        self.pet = self.panel.pet = DesktopPet(self.panel)
        self.pet.activity_timer.stop()
        self.pet.timer.stop()
        self.pet.show()
        self.app.processEvents()

    def tearDown(self):
        self.panel.provider_poller.close()
        self.panel.task_manager.shutdown()
        self.panel.clock.stop()
        self.pet.close()
        self.panel.tray.hide()
        self.panel.closing = True
        self.panel.close()
        self.panel.deleteLater()
        self.app.processEvents()
        self.pref_patch.stop()
        self.temp.cleanup()

    def poll(self):
        poller = self.panel.provider_poller
        for _ in range(3):
            out = poller.poll(dict(self.panel.prefs), active_title='a', detection_valid=True)
            self.assertTrue(poller.drain())
        self.panel.publish_snapshot(out)
        self.app.processEvents()
        return out

    def seed(self):
        home = Path(self.temp.name) / 'codex'
        home.mkdir()
        write_home(home, [dict(id='a', working=True), dict(id='b', working=True)])
        self.panel.provider_poller.close()
        self.panel.provider_poller = ProviderPoller(CodexStore(home))
        self.panel.prefs.update(scope='global', pinned='', language='en')
        self.panel.apply_language()
        self.poll()

    def test_fixed_size_ignores_old_saved_and_programmatic_resize(self):
        self.panel.prefs['panel_size'] = [600, 800]
        self.panel.apply_compact()
        self.panel.resize(900, 200)
        self.assertEqual(self.panel.size().toTuple(), HUB_SIZE)
        self.assertEqual(self.panel.minimumSize(), self.panel.maximumSize())
        for _ in range(3):
            self.panel.toggle_compact()
            self.assertEqual(self.panel.size().toTuple(), (HUB_SIZE[0], COMPACT_HEIGHT))
            self.panel.toggle_compact()
            self.assertEqual(self.panel.size().toTuple(), HUB_SIZE)
        self.assertFalse(self.panel.findChildren(QScrollArea))

    def test_no_hover_open_or_cursor_leave_hide(self):
        QTest.mouseMove(self.pet, QPoint(120, 160))
        QTest.qWait(450)
        self.pet.update_activity()
        self.assertFalse(self.panel.isVisible())
        QTest.mouseClick(self.pet, Qt.LeftButton, pos=QPoint(120, 160))
        self.assertTrue(self.panel.isVisible())
        QTest.mouseMove(self.pet, QPoint(-100, -100))
        QTest.qWait(800)
        self.pet.update_activity()
        self.assertTrue(self.panel.isVisible())
        QTest.mouseClick(self.pet, Qt.LeftButton, pos=QPoint(120, 160))
        self.assertFalse(self.panel.isVisible())

    def test_context_check_keeps_open_topmost_until_unchecked(self):
        self.panel.set_always_on_top(False)
        menu = self.pet.context_menu()
        action = menu.actions()[0]
        self.assertTrue(action.isCheckable())
        self.assertFalse(action.isChecked())
        action.trigger()
        self.assertTrue(self.panel.is_pinned())
        self.assertTrue(self.panel.isVisible())
        self.assertTrue(self.panel.windowFlags() & Qt.WindowStaysOnTopHint)
        self.assertFalse(self.pet.windowFlags() & Qt.WindowStaysOnTopHint)
        self.pet.toggle_panel()
        self.panel.hide_to_tray()
        self.panel.close()
        QTest.keyClick(self.panel, Qt.Key_Escape)
        self.assertTrue(self.panel.isVisible())
        # X stays clickable on a pinned Hub (it closes and unpins).
        self.assertTrue(self.panel.hide_button.isEnabled())
        self.assertEqual(self.panel.hide_button.cursor().shape(), Qt.PointingHandCursor)
        self.panel.set_always_on_top(False)
        self.assertTrue(self.panel.windowFlags() & Qt.WindowStaysOnTopHint)
        action.trigger()
        self.assertFalse(self.panel.is_pinned())
        self.assertFalse(self.panel.isVisible())
        self.assertFalse(self.panel.windowFlags() & Qt.WindowStaysOnTopHint)
        menu.deleteLater()

    def test_pin_restores_on_restart(self):
        self.panel.set_panel_pinned(True)
        other = Panel(live=False)
        other.pet = DesktopPet(other)
        other.pet.activity_timer.stop()
        try:
            other.restore_companion()
            self.assertTrue(other.isVisible())
            self.assertTrue(other.pet.context_menu().actions()[0].isChecked())
        finally:
            other.shutdown()

    def test_selected_task_routes_hub_without_opening_star_detail(self):
        self.seed()
        before = self.panel.snapshot['generation']
        self.panel.refresh_task_menu()
        self.panel.task_menu.actions()[-1].trigger()
        selected = self.panel.prefs['pinned']
        self.assertIn(selected, ('a', 'b'))
        self.assertEqual(self.panel.prefs['scope'], 'conversation')
        self.assertGreater(self.panel.snapshot['generation'], before)
        self.assertFalse(self.panel.snapshot['available'])  # no wrong-scope cached totals
        self.poll()
        self.assertEqual(self.panel.title.full_text, selected)
        self.assertEqual(self.panel.total.text(), '110')
        self.assertIsNone(self.panel.task_manager.expanded_identity)
        self.assertEqual(self.panel.task_manager.total_task_count(), 2)
        for scope in ('project', 'global', 'conversation'):
            self.panel.change_scope(scope)
            self.poll()
            self.assertEqual(self.panel.snapshot['scope'], scope)
            self.assertEqual(self.panel.prefs['pinned'], selected)
            self.assertEqual(self.panel.total.text(), '110' if scope == 'conversation' else '220')
        self.panel.refresh_task_menu()
        self.panel.task_menu.actions()[0].trigger()
        self.assertFalse(self.panel.prefs['pinned'])
        self.poll()
        self.assertEqual(self.panel.task_manager.total_task_count(), 2)

    def test_retired_menu_task_cannot_switch_current_hub(self):
        self.seed()
        self.panel.refresh_task_menu()
        old = self.panel.task_menu.actions()[-1]
        self.panel.task_manager.apply_snapshot([])
        before = dict(self.panel.prefs)
        old.trigger()
        self.assertEqual(self.panel.prefs, before)

    def test_compact_numbers_and_settings_have_complete_height(self):
        self.test_full_populated_layout_fits_without_scroll()
        self.panel.toggle_compact()
        self.app.processEvents()
        for w in (self.panel.compact_box, self.panel.compact_cost, self.panel.compact_total,
                  self.panel.settings_button):
            self.assertTrue(w.isVisible())
            self.assertGreaterEqual(w.height(), w.minimumSizeHint().height())
            self.assertTrue(self.panel.rect().contains(w.mapTo(self.panel, w.rect().bottomRight())))

    def test_older_task_result_cannot_restore_previous_selection(self):
        self.seed()
        stale = dict(self.panel.snapshot)
        self.panel.select_hub_task(('codex', 'b'))
        current = dict(self.panel.snapshot)
        self.panel.render(stale)
        self.assertEqual(self.panel.snapshot, current)
        self.poll()
        self.assertEqual(self.panel.title.full_text, 'b')

    def test_full_populated_layout_fits_without_scroll(self):
        tokens = normalize_usage(dict(input_tokens=143580000, output_tokens=722920,
                                      cached_input_tokens=138000000, total_tokens=144302920))
        for language in ('zh_CN', 'en'):
            self.panel.prefs.update(language=language, token_number_format='full')
            self.panel.apply_language()
            self.panel.render(dict(provider_id='codex', available=True, scope='conversation',
                title='A long task title ' * 20, project='Codex', model='gpt-6.1-sol', effort='high',
                tokens=tokens, usd=12.34, context=19, context_tokens=38000, context_window=200000,
                analytics=aggregate([]), scope_activity=dict(valid=True, active=False)))
            self.panel.receive_limits(dict(sampled=time.time(), provider_id='codex', limits={
                'primary': dict(usedPercent=50, windowDurationMins=300, resetsAt=time.time() + 4000),
                'secondary': dict(usedPercent=8, windowDurationMins=10080, resetsAt=time.time() + 700000)}))
            self.panel.show()
            self.app.processEvents()
            for widget in (self.panel.total, self.panel.io_line, self.panel.insights,
                           self.panel.context, self.panel.five, self.panel.week,
                           self.panel.cost, self.panel.settings_button):
                self.assertTrue(widget.isVisible())
                self.assertTrue(self.panel.rect().contains(widget.mapTo(self.panel, QPoint(0, 0))))
                self.assertTrue(self.panel.rect().contains(widget.mapTo(self.panel, widget.rect().bottomRight())))
                self.assertGreaterEqual(widget.height(), widget.minimumSizeHint().height())
