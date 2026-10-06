"""V1.6 notifications: center, history, quiet hours, reminders, Claude hooks."""
import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('PETOKEN_CLAUDE_HOME', os.path.join(
    tempfile.gettempdir(), 'petoken-tests-no-claude-home'))

from PySide6.QtWidgets import QApplication

import claude_events
from notifications import (NotificationCenter, NotificationStore, next_occurrence,
                           quiet_now)


def at(hour, minute=0, day=6):
    return datetime(2026, 10, day, hour, minute).timestamp()  # 2026-10-06 is a Tuesday.


class TimeRuleTests(unittest.TestCase):
    def test_next_occurrence(self):
        now = at(10)
        self.assertEqual(next_occurrence('daily', 9 * 60, after=now), at(9, day=7))
        self.assertEqual(next_occurrence('daily', 11 * 60, after=now), at(11))
        self.assertEqual(next_occurrence('weekly', 9 * 60, weekday=1, after=now), at(9, day=13))
        self.assertEqual(next_occurrence('weekly', 9 * 60, weekday=3, after=now), at(9, day=8))
        self.assertEqual(next_occurrence('once', 12 * 60, day='2026-10-06', after=now), at(12))
        self.assertIsNone(next_occurrence('once', 9 * 60, day='2026-10-06', after=now))

    def test_quiet_hours(self):
        scheduled = dict(dnd_scheduled=True, dnd_start='22:00', dnd_end='08:00')
        self.assertTrue(quiet_now(scheduled, at(23)))
        self.assertTrue(quiet_now(scheduled, at(7, 59)))
        self.assertFalse(quiet_now(scheduled, at(8)))
        self.assertFalse(quiet_now(dict(scheduled, dnd_scheduled=False), at(23)))
        self.assertTrue(quiet_now(dict(dnd_enabled=True), at(12)))
        self.assertTrue(quiet_now(dict(dnd_scheduled=True, dnd_start='13:00', dnd_end='14:00'), at(13, 30)))


class CenterTests(unittest.TestCase):
    def setUp(self):
        self.app = QApplication.instance() or QApplication([])
        self.temp = tempfile.TemporaryDirectory()
        self.prefs = {}
        self.store = NotificationStore(Path(self.temp.name) / 'n.sqlite3')
        self.center = NotificationCenter(self.store, lambda: self.prefs)
        self.fired = []
        self.center.fired.connect(self.fired.append)

    def tearDown(self):
        self.temp.cleanup()  # Fails on Windows if a connection were left open.

    def event(self, kind='finished', key='claude:s1', dedupe='a', at_=None):
        return dict(kind=kind, provider='claude', task_key=key, at=at_ or time.time(),
                    project='alpha', detail='', dedupe=dedupe)

    def test_same_event_once_and_quiet_hours_still_record(self):
        self.assertTrue(self.center.ingest(self.event()))
        self.assertFalse(self.center.ingest(self.event()))
        self.assertFalse(self.center.ingest(self.event(dedupe='b')))  # same task/kind, other source
        self.prefs['dnd_enabled'] = True
        self.assertTrue(self.center.ingest(self.event(kind='failed', dedupe='c')))
        self.assertEqual([e['kind'] for e in self.fired], ['finished'])
        self.assertEqual(len(self.store.list_events()), 2)
        self.assertEqual(len(self.store.list_events('failed')), 1)

    def test_history_is_kept_thirty_days(self):
        old = time.time() - 31 * 86400
        self.store.add_event(self.event(dedupe='old', at_=old))
        self.store.add_event(self.event(dedupe='new'))
        self.store.prune()
        self.assertEqual([e['dedupe'] for e in self.store.list_events()], ['new'])

    def test_polling_finishes_only_recent_tasks_and_ignores_view_changes(self):
        now = time.time()
        task = lambda key, seen: dict(provider_id='codex', task_key=key, activity_at=seen,
                                      display=dict(project='p'))
        self.center.observe_tasks([task('t1', now), task('t2', now - 600)], 'auto', now=now)
        self.center.observe_tasks([], 'codex', now=now)  # View changed: new baseline.
        self.assertEqual(self.store.list_events(), [])
        self.center.observe_tasks([task('t1', now), task('t2', now - 600)], 'codex', now=now)
        self.center.observe_tasks([], 'codex', now=now + 5)
        events = self.store.list_events()
        self.assertEqual([(e['task_key'], e['kind']) for e in events], [('t1', 'finished')])
        # Providers with instant hooks are not double-reported by polling.
        claude = dict(provider_id='claude', task_key='claude:s9', activity_at=now)
        self.center.observe_tasks([claude], 'codex', hooks_providers=('claude',), now=now)
        self.center.observe_tasks([], 'codex', hooks_providers=('claude',), now=now)
        self.assertEqual(len(self.store.list_events()), 1)

    def test_codex_approval_state_announces_each_wait_once(self):
        now = time.time()
        task = lambda waiting: dict(provider_id='codex', task_key='t1', activity_at=now,
                                    awaiting_approval=waiting, display=dict(project='p'))
        self.center.observe_tasks([task(True)], 'auto', now=now)  # Baseline: no replay.
        self.center.observe_tasks([task(True)], 'auto', now=now + 2)
        self.assertEqual(self.store.list_events('needs_approval'), [])
        self.center.observe_tasks([task(False)], 'auto', now=now + 4)
        self.center.observe_tasks([task(True)], 'auto', now=now + 200)
        self.center.observe_tasks([task(True)], 'auto', now=now + 202)
        self.center.observe_tasks([task(None)], 'auto', now=now + 204)
        events = self.store.list_events('needs_approval')
        self.assertEqual([(e['provider'], e['task_key']) for e in events], [('codex', 't1')])

    def test_low_quota_once_per_window(self):
        now = time.time()
        limits = lambda used, reset: dict(primary=dict(windowDurationMins=300, usedPercent=used, resetsAt=reset))
        self.assertFalse(self.center.observe_quota('codex', limits(50, now + 999), now))
        self.assertTrue(self.center.observe_quota('codex', limits(85, now + 999), now))
        self.assertFalse(self.center.observe_quota('codex', limits(90, now + 999), now + 200))
        self.assertTrue(self.center.observe_quota('codex', limits(90, now + 9999), now + 200))
        self.assertFalse(self.center.observe_quota('codex', None, now))

    def test_reminders_fire_and_repeat(self):
        now = time.time()
        stamp = datetime.fromtimestamp(now + 120)
        minute = stamp.hour * 60 + stamp.minute
        once = self.store.add_reminder('look', 'once', minute, day=stamp.strftime('%Y-%m-%d'), now=now)
        daily = self.store.add_reminder('water', 'daily', minute, now=now)
        with self.assertRaises(ValueError):
            self.store.add_reminder('', 'daily', minute, now=now)
        self.center.fire_reminders(now + 200)
        self.assertEqual(sorted(e['detail'] for e in self.store.list_events('reminder')), ['look', 'water'])
        rows = {r['id']: r for r in self.store.list_reminders()}
        self.assertIsNone(rows[once]['next_at'])
        self.assertGreater(rows[daily]['next_at'], now + 80000)


class ClaudeHooksTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        self.script = self.home / 'CodexWisp' / claude_events.SCRIPT_NAME

    def tearDown(self):
        self.temp.cleanup()

    def settings(self):
        return json.loads((self.home / 'settings.json').read_text(encoding='utf-8'))

    def test_enable_and_disable_keep_existing_hooks(self):
        mine = dict(hooks=[dict(type='command', command='my-lint.sh')])
        (self.home / 'settings.json').write_text(json.dumps(dict(
            model='haiku', hooks=dict(Stop=[mine], PreToolUse=[mine]))), encoding='utf-8')
        self.assertEqual(claude_events.enable(self.home, self.script), 'on')
        data = self.settings()
        self.assertEqual(data['model'], 'haiku')
        self.assertEqual(data['hooks']['Stop'][0], mine)
        self.assertEqual(len(data['hooks']['Stop']), 2)
        ours = data['hooks']['Stop'][1]['hooks'][0]
        self.assertTrue(ours['async'])
        self.assertIn(claude_events.SCRIPT_NAME, ours['args'][-1])
        self.assertTrue(list(self.home.glob('settings.json.petoken-backup-*')))
        self.assertEqual(claude_events.enable(self.home, self.script), 'on')  # No duplicates.
        self.assertEqual(len(self.settings()['hooks']['Stop']), 2)
        self.assertEqual(claude_events.disable(self.home), 'off')
        self.assertEqual(self.settings()['hooks'], dict(Stop=[mine], PreToolUse=[mine]))

    def test_unreadable_settings_untouched(self):
        (self.home / 'settings.json').write_text('{oops', encoding='utf-8')
        self.assertEqual(claude_events.enable(self.home, self.script), 'unreadable')
        self.assertEqual((self.home / 'settings.json').read_text(encoding='utf-8'), '{oops')

    def test_reader_never_replays_history_and_maps_events(self):
        path = self.home / 'events.jsonl'
        line = lambda **kw: json.dumps(dict(dict(at=time.time(), session='s1', prompt='p1', project='alpha'), **kw)) + '\n'
        path.write_text(line(event='Stop'), encoding='utf-8-sig')
        reader = claude_events.ClaudeEventReader(path)
        self.assertEqual(reader.poll(), [])  # Old lines are history.
        with path.open('a', encoding='utf-8') as handle:
            handle.write(line(event='Stop', prompt='p2'))
            handle.write(line(event='StopFailure', kind='rate_limit', prompt='p3'))
            handle.write(line(event='Notification', kind='permission_prompt'))
            handle.write(line(event='Notification', kind='idle_prompt'))
            handle.write('{"event": "Stop", "at": 1, "session": "s1"')  # Incomplete line.
        events = reader.poll()
        self.assertEqual([(e['kind'], e['detail']) for e in events],
                         [('finished', ''), ('failed', 'rate_limit'), ('needs_approval', 'permission_prompt')])
        self.assertEqual(events[0]['task_key'], 'claude:s1')
        self.assertEqual(events[0]['project'], 'alpha')
        self.assertEqual(reader.poll(), [])

    @unittest.skipUnless(os.name == 'nt' and shutil.which('powershell'), 'Windows PowerShell')
    def test_hook_script_keeps_metadata_only(self):
        self.script.parent.mkdir(parents=True)
        self.script.write_text(claude_events._SCRIPT, encoding='utf-8-sig')
        payload = dict(hook_event_name='Stop', session_id='abc-1', prompt_id='p-9',
                       cwd='C:/secret/client/alpha', last_assistant_message='SECRET REPLY',
                       transcript_path='C:/secret/t.jsonl')
        result = subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                                 str(self.script)], input=json.dumps(payload).encode('utf-8'),
                                capture_output=True, timeout=60, env=dict(os.environ, LOCALAPPDATA=str(self.home)))
        self.assertEqual(result.returncode, 0)
        written = (self.home / 'CodexWisp' / claude_events.EVENTS_NAME).read_text(encoding='utf-8-sig')
        self.assertNotIn('SECRET', written)
        self.assertNotIn('secret', written)
        record = json.loads(written.strip())
        self.assertEqual((record['event'], record['session'], record['prompt'], record['project']),
                         ('Stop', 'abc-1', 'p-9', 'alpha'))


class PanelNotificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from widget import Panel
        from pet import DesktopPet
        self.temp = tempfile.TemporaryDirectory()
        self.pref_patch = patch('widget.PREF_DIR', Path(self.temp.name))
        self.pref_patch.start()
        self.panel = Panel(live=False)
        self.panel.pet = DesktopPet(self.panel)
        self.panel.pet.activity_timer.stop()

    def tearDown(self):
        if self.panel.workbench_window:
            self.panel.workbench_window.shutdown()
        self.panel.pet.close()
        self.panel.tray.hide()
        self.panel.closing = True
        self.panel.close()
        self.pref_patch.stop()
        self.temp.cleanup()

    def test_event_reacts_records_and_lists_in_workbench(self):
        event = dict(kind='failed', provider='claude', task_key='claude:s1', at=time.time(),
                     project='alpha', detail='rate_limit', dedupe='x')
        self.assertTrue(self.panel.notifications.ingest(event))
        self.assertEqual(self.panel.pet.reaction_state, 'sad')
        self.assertIn('sad', self.panel.pet.sprites)
        title, body = self.panel.notification_text(event)
        self.assertEqual((title, body), ('Claude Code task hit an error', 'alpha · rate_limit'))
        self.panel.open_notice(event)  # Task is gone: opens the notification list.
        window = self.panel.workbench_window
        self.assertEqual(window.tabs.currentIndex(), window.notifications_tab)
        self.assertEqual(window.notify_list.count(), 1)
        self.assertIn('alpha', window.notify_list.item(0).text())

    def test_workbench_buttons_new_note_and_reminder_delete(self):
        from PySide6.QtWidgets import QDialog, QLineEdit, QPlainTextEdit
        self.panel.open_workbench()
        window = self.panel.workbench_window

        def confirm(dialog):
            dialog.findChildren(QLineEdit)[0].setText('Clicked note')
            dialog.findChildren(QPlainTextEdit)[0].setPlainText('body')
            return QDialog.Accepted
        with patch.object(QDialog, 'exec', confirm):
            window.new_note_button.click()  # Through the real button signal.
        self.assertEqual([n['title'] for n in window.store.list_notes()], ['Clicked note'])
        self.assertFalse(window.status.isVisible())
        self.assertFalse(window.reminder_delete_button.isVisible())
        self.assertTrue(window.add_reminder('water', 'daily', datetime.now() + timedelta(hours=1)))
        self.assertTrue(window.reminder_delete_button.isHidden())
        window.reminder_list.setCurrentRow(0)
        self.assertFalse(window.reminder_delete_button.isHidden())

    def test_settings_save_quiet_hours(self):
        from widget import Settings
        settings = Settings(self.panel)
        settings.dnd_scheduled.setChecked(True)
        settings.dnd_start.setTime(settings.dnd_start.time().fromString('21:30', 'HH:mm'))
        with patch('widget.write_preferences'):
            settings.save()
        self.assertTrue(self.panel.prefs['dnd_scheduled'])
        self.assertEqual(self.panel.prefs['dnd_start'], '21:30')
        self.assertFalse(settings.claude_notify.isChecked())


if __name__ == '__main__':
    unittest.main()
