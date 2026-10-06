import json
import tempfile
import unittest
from pathlib import Path

from PySide6.QtWidgets import QApplication

import claude_events
from notifications import NotificationCenter, NotificationStore

APP = QApplication.instance() or QApplication([])


class SilentEventTests(unittest.TestCase):
    def test_background_runs_are_history_only(self):
        with tempfile.TemporaryDirectory() as folder:
            store = NotificationStore(Path(folder) / 'n.sqlite3')
            center = NotificationCenter(store, lambda: {})
            fired = []
            center.fired.connect(fired.append)
            base = dict(kind='finished', provider='claude', project='p', detail='', at=1.0)
            self.assertTrue(center.ingest(dict(base, task_key='claude:bg', dedupe='a', silent=True), now=10))
            self.assertTrue(center.ingest(dict(base, task_key='claude:me', dedupe='b'), now=10))
            self.assertEqual([e['task_key'] for e in fired], ['claude:me'])
            self.assertEqual(len(store.list_events()), 2)

    def test_interactive_sessions_come_from_the_registry(self):
        with tempfile.TemporaryDirectory() as home:
            sessions = Path(home) / 'sessions'
            sessions.mkdir()
            for name, data in (('1.json', dict(sessionId='cli', kind='interactive')),
                               ('2.json', dict(sessionId='old')),
                               ('3.json', dict(sessionId='bot', kind='sdk')),
                               ('4.json', '{oops')):
                (sessions / name).write_text(data if isinstance(data, str) else json.dumps(data),
                                             encoding='utf-8')
            self.assertEqual(claude_events.interactive_sessions(home), {'cli', 'old'})
            self.assertEqual(claude_events.interactive_sessions(Path(home) / 'missing'), set())


if __name__ == '__main__':
    unittest.main()
