import json
import sqlite3
import tempfile
import time
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from PySide6.QtWidgets import QApplication

import todo_ai
import workbench_store
from notifications import recap_detail
from workbench_store import WorkbenchError, WorkbenchStore

APP = QApplication.instance() or QApplication([])
NOW = 1_800_000_000.0


class FakePanel:
    currency = 'USD'
    fx = dict(rates={})

    def __init__(self, missed='ask'):
        self.prefs = dict(language='en', schedule_missed=missed)
        self.closing = False
        self.notices = []

    def tray_notice(self, title, body=''):
        self.notices.append(title)


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)   # Runs after the stores close (LIFO).
        self.path = Path(self.temp.name) / 'workbench.sqlite3'

    def test_v2_store_gains_schedules_with_a_backup(self):
        with closing(sqlite3.connect(self.path)) as connection, connection:
            for sql in workbench_store._SCHEMA_V2.values():
                connection.execute(sql)
            connection.execute(f'PRAGMA application_id={workbench_store._APPLICATION_ID}')
            connection.execute('PRAGMA user_version=2')
            connection.execute("INSERT INTO todos VALUES (?, 'keep me', NULL, 0, 'now', 'now')", (str(uuid4()),))
        store = WorkbenchStore(self.path)
        self.addCleanup(store.close)
        self.assertEqual([t['title'] for t in store.list_todos()], ['keep me'])
        self.assertEqual(store.list_schedules(), [])
        backups = sorted(Path(self.temp.name).glob('workbench.v2-backup-*.sqlite3'))
        self.assertEqual(len(backups), 1)
        with closing(sqlite3.connect(backups[0])) as connection:
            self.assertEqual(connection.execute('PRAGMA user_version').fetchone()[0], 2)

    def test_schedule_lifecycle_and_cascade(self):
        store = WorkbenchStore(self.path)
        self.addCleanup(store.close)
        todo = store.create_todo('Write the docs')
        saved = store.schedule_todo(todo['id'], NOW, 'claude', r'C:\work\site', 'Write the docs')
        self.assertEqual((saved['state'], saved['provider_id']), ('waiting', 'claude'))
        store.update_schedule(todo['id'], state='started', started_at=NOW, task_key='claude:s1')
        self.assertEqual([s['todo_id'] for s in store.list_schedules(['started'])], [todo['id']])
        again = store.schedule_todo(todo['id'], NOW + 60, 'codex', r'C:\work\site', 'Again')
        self.assertEqual((again['state'], again['task_key']), ('waiting', None))   # Rescheduling resets it.
        with self.assertRaises(WorkbenchError):
            store.schedule_todo(todo['id'], NOW, 'opencode', 'C:\\', 'x')
        with self.assertRaises(WorkbenchError):
            store.update_schedule(todo['id'], state='exploded')
        store.delete_todo(todo['id'])
        self.assertEqual(store.list_schedules(), [])


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.store = WorkbenchStore(self.folder / 'workbench.sqlite3')
        self.launched = []
        self.todo = self.store.create_todo('Add dark mode')

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def scheduler(self, panel=None, match=None):
        return todo_ai.TodoScheduler(panel or FakePanel(), self.store, self.launched.append,
                                     match or (lambda schedule: None))

    def test_due_todo_starts_and_the_task_is_matched(self):
        self.store.schedule_todo(self.todo['id'], NOW, 'claude', str(self.folder), 'Add dark mode')
        scheduler = self.scheduler(match=lambda schedule: 'claude:new-session')
        with patch('quick_launch.build_command', return_value=['wt.exe', 'go']) as build:
            scheduler.tick(NOW - 60)
            self.assertEqual(self.launched, [])                 # Not yet.
            scheduler.tick(NOW + 5)
            scheduler.tick(NOW + 35)                           # The next check finds its task.
        build.assert_called_once_with('claude', str(self.folder), 'Add dark mode', external_id=self.todo['id'],
                                      model=None, effort=None)
        self.assertEqual(self.launched, [['wt.exe', 'go']])
        deadline = time.time() + 3
        while not self.store.get_schedule(self.todo['id'])['task_key'] and time.time() < deadline:
            APP.processEvents()
            time.sleep(0.01)
        schedule = self.store.get_schedule(self.todo['id'])
        self.assertEqual((schedule['state'], schedule['task_key']), ('started', 'claude:new-session'))

    def test_missed_todo_follows_the_users_choice(self):
        self.store.schedule_todo(self.todo['id'], NOW, 'claude', str(self.folder), 'x')
        ask = FakePanel('ask')
        with patch('quick_launch.build_command', return_value=['go']):
            self.scheduler(ask).tick(NOW + todo_ai.MISSED_AFTER_S + 60)
        self.assertEqual(self.store.get_schedule(self.todo['id'])['state'], 'missed')
        self.assertEqual(len(ask.notices), 1)
        self.assertEqual(self.launched, [])
        self.store.schedule_todo(self.todo['id'], NOW, 'claude', str(self.folder), 'x')
        with patch('quick_launch.build_command', return_value=['go']):
            self.scheduler(FakePanel('run')).tick(NOW + todo_ai.MISSED_AFTER_S + 60)
        self.assertEqual(self.store.get_schedule(self.todo['id'])['state'], 'started')
        self.assertEqual(self.launched, [['go']])

    def test_finished_task_waits_for_review_with_a_note(self):
        self.store.schedule_todo(self.todo['id'], NOW, 'claude', str(self.folder), 'Add dark mode')
        self.store.update_schedule(self.todo['id'], state='started', started_at=NOW, task_key='claude:s1')
        scheduler = self.scheduler()
        scheduler.on_event(dict(kind='finished', provider='claude', task_key='claude:other', detail=''))
        self.assertEqual(self.store.get_schedule(self.todo['id'])['state'], 'started')
        detail = recap_detail(dict(files=['src/theme.css'], duration_s=95, usd=0.2))
        scheduler.on_event(dict(kind='finished', provider='claude', task_key='claude:s1', detail=detail))
        schedule = self.store.get_schedule(self.todo['id'])
        self.assertEqual(schedule['state'], 'review')       # 2.0: done by the AI, not yet by you.
        self.assertFalse(self.store.list_todos()[0]['done'])
        self.assertEqual(scheduler.panel.notices[-1], 'Ready for your review: Add dark mode')
        note = self.store.get_note(schedule['note_id'])
        self.assertEqual(note['title'], 'AI finished: Add dark mode')
        self.assertIn('src/theme.css', note['body'])
        self.assertIn('1m 35s', note['body'])

    def test_model_and_effort_reach_the_command(self):
        self.store.schedule_todo(self.todo['id'], NOW, 'claude', str(self.folder), 'x', 'claude-opus-5', 'high')
        with patch('quick_launch.build_command', return_value=['go']) as build:
            self.scheduler().tick(NOW + 1)
        self.assertEqual(build.call_args.kwargs['model'], 'claude-opus-5')
        self.assertEqual(build.call_args.kwargs['effort'], 'high')

    def test_a_task_that_never_shows_up_stops_waiting(self):
        self.store.schedule_todo(self.todo['id'], NOW, 'codex', str(self.folder), 'x')
        self.store.update_schedule(self.todo['id'], state='started', started_at=NOW)
        panel = FakePanel()
        self.scheduler(panel).tick(NOW + todo_ai.MATCH_TIMEOUT_S - 60)
        self.assertEqual(self.store.get_schedule(self.todo['id'])['state'], 'started')
        self.scheduler(panel).tick(NOW + todo_ai.MATCH_TIMEOUT_S + 60)
        self.assertEqual(self.store.get_schedule(self.todo['id'])['state'], 'failed')
        self.assertEqual(len(panel.notices), 1)

    def test_interrupted_turn_does_not_tick_the_todo(self):
        self.store.schedule_todo(self.todo['id'], NOW, 'claude', str(self.folder), 'x')
        self.store.update_schedule(self.todo['id'], state='started', started_at=NOW, task_key='claude:s1')
        with patch('claude_recap.interrupted', return_value=True):
            self.scheduler().on_event(dict(kind='finished', provider='claude', task_key='claude:s1', detail=''))
        self.assertEqual(self.store.get_schedule(self.todo['id'])['state'], 'started')
        self.assertFalse(self.store.list_todos()[0]['done'])
        with patch('claude_recap.interrupted', return_value=False):
            self.scheduler().on_event(dict(kind='finished', provider='claude', task_key='claude:s1', detail=''))
        self.assertEqual(self.store.get_schedule(self.todo['id'])['state'], 'review')

    def test_codex_outcome_decides_interrupted_or_failed(self):
        for outcome, state in (('interrupted', 'started'), ('failed', 'failed'), ('completed', 'review'),
                               (None, 'review')):
            self.store.schedule_todo(self.todo['id'], NOW, 'codex', str(self.folder), 'x')
            self.store.update_schedule(self.todo['id'], state='started', started_at=NOW, task_key='thread-1')
            with patch('codex_recap.turn_outcome', return_value=outcome):
                self.scheduler().on_event(dict(kind='finished', provider='codex', task_key='thread-1', detail=''))
            self.assertEqual(self.store.get_schedule(self.todo['id'])['state'], state, outcome)

    def test_accept_ticks_and_redo_hands_it_back_with_feedback(self):
        self.store.schedule_todo(self.todo['id'], NOW, 'claude', str(self.folder), 'Add dark mode', 'opus', 'high')
        self.store.update_schedule(self.todo['id'], state='review')
        scheduler = self.scheduler()
        self.assertFalse(scheduler.redo(self.todo['id'], '   '))
        with patch('quick_launch.build_command', return_value=['go']) as build:
            self.assertTrue(scheduler.redo(self.todo['id'], 'use the brand colours'))
            self.store.update_schedule(self.todo['id'], state='review')
            self.assertTrue(scheduler.redo(self.todo['id'], 'and add tests'))
        prompt = build.call_args.args[2]
        self.assertEqual(prompt, 'Add dark mode' + chr(10) * 2 + 'My feedback on the last attempt: and add tests')
        self.assertEqual(build.call_args.kwargs['model'], 'opus')
        self.assertEqual(self.store.get_schedule(self.todo['id'])['state'], 'started')
        self.assertFalse(scheduler.accept(self.todo['id']))       # Only a todo waiting for review.
        self.store.update_schedule(self.todo['id'], state='review')
        self.assertTrue(scheduler.accept(self.todo['id']))
        self.assertTrue(self.store.list_todos()[0]['done'])
        self.assertEqual(self.store.get_schedule(self.todo['id'])['state'], 'finished')

    def test_failed_task_is_marked(self):
        self.store.schedule_todo(self.todo['id'], NOW, 'codex', str(self.folder), 'x')
        self.store.update_schedule(self.todo['id'], state='started', started_at=NOW, task_key='thread-1')
        self.scheduler().on_event(dict(kind='failed', provider='codex', task_key='thread-1'))
        self.assertEqual(self.store.get_schedule(self.todo['id'])['state'], 'failed')
        self.assertFalse(self.store.list_todos()[0]['done'])


class MatchTests(unittest.TestCase):
    def test_first_claude_session_in_the_folder_after_the_start(self):
        with tempfile.TemporaryDirectory() as home:
            sessions = Path(home) / 'sessions'
            sessions.mkdir()
            entries = [dict(sessionId='old', cwd=r'C:\work\site', startedAt=(NOW - 600) * 1000),
                       dict(sessionId='other-folder', cwd=r'C:\work\api', startedAt=(NOW + 3) * 1000),
                       dict(sessionId='bot', cwd=r'C:\work\site', startedAt=(NOW + 2) * 1000, kind='sdk'),
                       dict(sessionId='mine', cwd='C:\\work\\Site\\', startedAt=(NOW + 4) * 1000),
                       dict(sessionId='later', cwd=r'C:\work\site', startedAt=(NOW + 90) * 1000)]
            for index, entry in enumerate(entries):
                (sessions / f'{index}.json').write_text(json.dumps(entry), encoding='utf-8')
            self.assertEqual(todo_ai.claude_session_for(r'C:\work\site', NOW, home), 'claude:mine')
            self.assertIsNone(todo_ai.claude_session_for(r'C:\work\none', NOW, home))

    def test_badges(self):
        self.assertEqual(todo_ai.schedule_badge(None, 'en'), '')
        self.assertIn('Claude Code', todo_ai.schedule_badge(dict(state='started', provider_id='claude'), 'en'))
        self.assertTrue(todo_ai.schedule_badge(dict(state='waiting', provider_id='codex', run_at=NOW),
                                               'zh_CN').startswith('⏰'))


if __name__ == '__main__':
    unittest.main()


class DialogAndButtonTests(unittest.TestCase):
    def test_dialog_offers_model_and_effort(self):
        import claude_models
        todo = dict(id='t', title='Write docs', project_id=None)
        with patch('claude_models.catalog', return_value=[dict(m) for m in claude_models.FALLBACK]):
            dialog = todo_ai.GiveToAiDialog(None, FakePanel(), todo, None, [r'C:\work'])
            dialog.model.setCurrentIndex(dialog.model.findData('claude-sonnet-5-5'))
            dialog.effort.setCurrentIndex(dialog.effort.findData('low'))
            values = dialog.values()
        self.assertEqual((values['model'], values['effort']), ('claude-sonnet-5-5', 'low'))
        dialog.close()

    def test_button_takes_back_an_active_hand_off(self):
        import widget
        panel = widget.Panel(live=False)
        panel.prefs['language'] = 'en'
        panel.open_workbench()
        window = panel.workbench_window
        todo = window.store.create_todo('Ship it')
        window.store.schedule_todo(todo['id'], NOW, 'claude', r'C:\work', 'Ship it')
        window.refresh()
        window.todo_list.setCurrentRow(0)
        self.assertEqual(window.todo_ai_button.text(), 'Take back')
        window.todo_ai_button.click()
        self.assertIsNone(window.store.get_schedule(todo['id']))
        window.todo_list.setCurrentRow(0)
        self.assertEqual(window.todo_ai_button.text(), 'Give to AI…')
        window.shutdown()
        panel.shutdown()

