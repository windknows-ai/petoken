import json
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
import zipfile
from contextlib import closing
from pathlib import Path

import diagnostics


class DiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.saved = sys.excepthook, threading.excepthook

    def tearDown(self):
        sys.excepthook, threading.excepthook = self.saved
        self.temp.cleanup()

    def test_uncaught_errors_are_logged_from_main_and_threads(self):
        diagnostics.install_error_log(self.folder)
        try:
            raise ValueError('boom')
        except ValueError:
            sys.excepthook(*sys.exc_info())
        worker = threading.Thread(target=lambda: 1 / 0, name='worker-1')
        worker.start()
        worker.join()
        log = diagnostics.error_log_path(self.folder).read_text(encoding='utf-8')
        self.assertIn('ValueError: boom', log)
        self.assertIn('(thread worker-1)', log)
        self.assertIn('ZeroDivisionError', log)

    def test_log_is_trimmed(self):
        path = diagnostics.error_log_path(self.folder)
        path.write_text('x\n' * diagnostics.MAX_LOG_BYTES, encoding='utf-8')
        diagnostics.record_error(self.folder, KeyError, KeyError('k'), None)
        self.assertLess(path.stat().st_size, diagnostics.MAX_LOG_BYTES)
        self.assertTrue(path.read_text(encoding='utf-8').rstrip().endswith("KeyError: 'k'"))

    def test_collect_keeps_private_things_out(self):
        (self.folder / 'claude-approvals').mkdir()
        (self.folder / 'claude-approvals' / 'events.log').write_text(
            '2026-10-06 01:00:00 abcd1234 Bash received\n', encoding='utf-8')
        with closing(sqlite3.connect(self.folder / 'notifications.sqlite3')) as db:
            db.execute('CREATE TABLE events(at REAL, kind TEXT)')
            db.executemany('INSERT INTO events VALUES (?, ?)',
                           [(time.time(), 'finished'), (time.time(), 'finished'), (1.0, 'failed')])
            db.commit()
        prefs = dict(language='zh_CN', launch_folders=[r'C:\Users\me\secret-project', r'D:\work'])
        sections = diagnostics.collect(self.folder, prefs, '1.7.0', {'Approve Claude on the pet': 'on'})
        self.assertEqual(set(sections), {'about.txt', 'features.txt', 'preferences.json', 'errors.log',
                                         'approval-steps.log', 'notifications-7-days.txt'})
        self.assertIn('Petoken 1.7.0', sections['about.txt'])
        self.assertNotIn('secret-project', sections['preferences.json'])
        self.assertEqual(json.loads(sections['preferences.json'])['launch_folders'], '<2 folders, not included>')
        self.assertEqual(sections['notifications-7-days.txt'], 'finished: 2')
        self.assertIn('Bash received', sections['approval-steps.log'])
        self.assertEqual(sections['errors.log'], '(no errors recorded)')
        target = diagnostics.write_zip(self.folder / 'out.zip', sections)
        with zipfile.ZipFile(target) as archive:
            self.assertEqual(sorted(archive.namelist()), sorted(sections))


if __name__ == '__main__':
    unittest.main()
