"""2.0 focus companion mode: phases, records, summary, quiet notices, pet and reports."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication

import focus_mode
import reports
from focus_mode import FocusCard, FocusMode, clock_text
from workbench_store import WorkbenchStore

APP = QApplication.instance() or QApplication([])


class FakePanel(QObject):
    def __init__(self):
        super().__init__()
        self.prefs = dict(language='en')
        self.notices = []
        self.notifications = None
        self.report_cache = None

    def tray_notice(self, title, body=''):
        self.notices.append(title)


class FocusModeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = WorkbenchStore(Path(self.temp.name) / 'workbench.sqlite3')
        self.addCleanup(self.store.close)
        self.now = [1_000_000.0]
        self.panel = FakePanel()
        self.mode = FocusMode(self.panel, self.store, clock=lambda: self.now[0])
        self.ended, self.ready = [], []
        self.mode.ended.connect(self.ended.append)
        self.mode.summary_ready.connect(self.ready.append)

    def test_full_round_records_summary_and_breaks(self):
        todo = self.store.create_todo('ship it')
        self.mode.start(25)
        self.assertTrue(self.mode.active)
        self.assertEqual(clock_text(self.mode.remaining()), '25:00')
        self.now[0] += 600
        self.mode.tick()
        self.assertEqual(self.mode.phase, 'focus')
        self.store.update_todo(todo['id'], 'ship it', done=True)
        # The store stamps real time; put the window around it.
        import time
        self.mode.started = time.time() - 5
        self.now[0] = self.mode.ends = time.time() + 1
        self.mode.tick()
        self.assertEqual(self.mode.phase, 'break')
        [summary] = self.ended
        self.assertTrue(summary['completed'])
        self.assertEqual(summary['todos'], ['ship it'])
        self.assertFalse(self.ready[0]['loading'])
        [session] = self.store.list_focus()
        self.assertTrue(session['completed'])
        self.assertEqual(self.panel.notices[-1], 'Focus done: take a 5-minute break')
        self.now[0] = self.mode.ends + 1
        self.mode.tick()
        self.assertEqual(self.mode.phase, 'idle')
        self.assertEqual(self.panel.notices[-1], 'Break is over')

    def test_stopping_early_has_no_break(self):
        self.mode.start(45)
        self.now[0] += 300
        self.mode.stop()
        self.assertEqual(self.mode.phase, 'idle')
        self.assertFalse(self.ended[0]['completed'])
        self.assertEqual(self.ended[0]['end'] - self.ended[0]['start'], 300)
        self.assertFalse(self.store.list_focus()[0]['completed'])

    def test_breaks_follow_your_settings(self):
        lengths = []
        for round_ in range(4):
            self.mode.start(25)
            self.now[0] = self.mode.ends
            self.mode.tick()
            lengths.append(self.mode.ends - self.now[0])
            self.mode.skip_break()
        self.assertEqual(lengths, [300, 300, 300, focus_mode.LONG_BREAK_MIN * 60])   # Defaults.
        self.panel.prefs.update(focus_break=10, focus_long_break=30, focus_long_every=2)
        self.mode.rounds = 0
        lengths = []
        for round_ in range(2):
            self.mode.start(25)
            self.now[0] = self.mode.ends
            self.mode.tick()
            lengths.append(self.mode.ends - self.now[0])
            self.mode.skip_break()
        self.assertEqual(lengths, [600, 1800])
        self.panel.prefs.update(focus_break=0, focus_long_every=0)
        self.mode.start(25)
        self.now[0] = self.mode.ends
        self.mode.tick()
        self.assertEqual(self.mode.phase, 'idle')        # No break at all.
        self.assertEqual(self.ended[-1]['break_min'], 0)

    def test_focus_on_a_todo_and_tick_it_off_from_the_card(self):
        todo = self.store.create_todo('write tests')
        self.mode.start(25, todo)
        self.assertEqual(self.mode.todo_title, 'write tests')
        self.assertEqual(self.mode.session['todo_id'], todo['id'])
        self.now[0] = self.mode.ends
        self.mode.tick()
        summary = self.ended[-1]
        self.assertEqual((summary['todo_id'], summary['todo_done']), (todo['id'], False))
        card = FocusCard('en', dict(summary, loading=False))
        self.assertIn('Focused on: write tests', card.lines.text())
        self.assertFalse(card.todo_button.isHidden())
        done = []
        card.todo_done.connect(done.append)
        card.todo_button.click()
        self.assertEqual(done, [todo['id']])
        self.assertTrue(card.todo_button.isHidden())
        card.deleteLater()

    def test_only_urgent_notices_get_through(self):
        self.assertFalse(self.mode.quiet('finished'))
        self.mode.start(25)
        self.assertTrue(self.mode.quiet('finished'))
        self.assertTrue(self.mode.quiet('reminder'))
        for kind in ('needs_approval', 'failed', 'quota_low', 'context_full'):
            self.assertFalse(self.mode.quiet(kind), kind)

    def test_abandon_on_exit_records_unfinished(self):
        self.mode.start(25)
        self.now[0] += 60
        self.mode.abandon()
        self.assertEqual(self.mode.phase, 'idle')
        self.assertEqual(self.ended, [])
        self.assertFalse(self.store.list_focus()[0]['completed'])

    def test_card_lists_what_got_done(self):
        card = FocusCard('en', dict(start=0, end=1500, planned=1500, completed=True, todos=['a', 'b'],
                                    ai_finished=2, files=None, tokens=None, loading=True, break_min=5))
        self.assertEqual(card.title.text(), 'Focus done · 25 min')
        self.assertIn('2 todos done: a, b', card.lines.text())
        self.assertIn('Counting', card.note.text())
        card.update_summary(dict(start=0, end=1500, planned=1500, completed=True, todos=[], ai_finished=0,
                                 files=3, tokens=1200, loading=False, break_min=5))
        self.assertIn('3 files changed', card.lines.text())
        self.assertIn('Take a 5-minute break', card.note.text())
        card.deleteLater()

    def test_reports_count_focus_time(self):
        from tests.test_reports import DATA, NOW
        data = dict(DATA, focus=[(NOW - 3600, NOW - 2100, True), (NOW - 40 * 86400, NOW - 40 * 86400 + 60, False)])
        summary = reports.summarize(data, [], 'today', NOW)
        self.assertEqual((summary['focus_count'], summary['focus_seconds']), (1, 1500))


class FocusPetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.pref_patch = patch('widget.PREF_DIR', Path(self.temp.name))
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

    def test_she_reads_and_counts_down_while_you_focus(self):
        menu = self.pet.context_menu()
        titles = [a.text() for a in menu.actions()]
        self.assertIn(self.pet.tr_text('focus_menu'), titles)
        menu.deleteLater()
        self.panel.start_focus(25)
        self.assertEqual(self.pet.current_state, 'focus_read')
        self.assertTrue(self.pet.focus_subtitle().startswith('Focus · 2'))
        with patch.object(self.pet, 'token_bubble_visible', return_value=True):
            self.assertIsNotNone(self.pet.focus_subtitle())     # Shown even while AI works.
        with patch.object(self.pet, 'react') as react:
            self.panel.announce(dict(kind='finished', provider='claude'))
            react.assert_not_called()
            self.panel.announce(dict(kind='failed', provider='claude'))
            react.assert_called_once_with('failed')
        menu = self.pet.context_menu()
        self.assertTrue(any(a.text().startswith('End focus') for a in menu.actions()))
        menu.deleteLater()
        self.panel.focus_mode.stop()
        self.assertIsNotNone(self.panel._focus_card)
        self.assertIsNone(self.pet.focus_subtitle())
        self.panel._focus_card.close()


if __name__ == '__main__':
    unittest.main()
