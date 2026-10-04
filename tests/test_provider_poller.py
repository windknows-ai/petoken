"""Codex product orchestration and retained lifecycle/concurrency regressions."""
import os
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from provider_poller import ProviderPoller
from provider_selection import normalize_tracking_provider
from providers import CodexProvider
from tests.test_providers import write_home
from usage import CodexStore

NOW_S = datetime(2026, 9, 19, 12, 1, 40, tzinfo=timezone.utc).timestamp()
TOKEN_EPOCH = datetime(2026, 9, 19, 12, 0, 2, tzinfo=timezone.utc).timestamp()

class PollerFixture:
    def __init__(self, root):
        self.root = Path(root)
        self.counter = 0

    def _fresh(self, name):
        self.counter += 1
        return self.root / f'{name}-{self.counter}'

    def codex(self, threads):
        home = self._fresh('codex')
        home.mkdir(parents=True, exist_ok=True)
        write_home(str(home), threads)
        return CodexStore(home)


class PollerSelectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.fixture = PollerFixture(self.temp.name)
        self._pollers = []

    def tearDown(self):
        for poller in self._pollers:
            poller.drain(timeout=10)
            poller.close()
        self.temp.cleanup()

    def _poller(self, threads):
        store = self.fixture.codex(threads)
        poller = ProviderPoller(store)
        self._pollers.append(poller)
        return poller

    def _sync_poll(self, poller, prefs=None, **kw):
        """Deterministic async poll: three submit/collect rounds.

        Three rounds guarantee one full fresh round-trip even when a
        previous-epoch job is still draining: round one retires it,
        round two collects the resubmit, round three decides on it.
        Returns the last tick.
        """
        out = poller.poll(prefs, **kw)
        self.assertTrue(poller.drain(), 'provider reads did not finish')
        out = poller.poll(prefs, **kw)
        self.assertTrue(poller.drain(), 'provider reads did not finish')
        return poller.poll(prefs, **kw)

    def _resync(self, poller, prefs=None, **kw):
        """Change prefs the production way, then settle two ticks."""
        poller.apply_settings(dict(prefs or {}))
        return self._sync_poll(poller, prefs, **kw)

    def test_codex_working_selected_live(self):
        poller = self._poller([{'id': 't1', 'working': True}])
        out = self._sync_poll(poller, {'scope': 'global'}, active_title='t1',
                          detection_valid=True)
        self.assertEqual(out['provider_id'], 'codex')
        self.assertTrue(out['selection']['live'])
        self.assertEqual(out['result']['provider_id'], 'codex')
        self.assertEqual(out['result']['working_context']['thread'], 't1')
        self.assertEqual(out['codex']['provider_id'], 'codex')

    def test_generation_increments_and_bump(self):
        poller = self._poller([{'id': 't1'}])
        # Generation counting is synchronous and needs no completions.
        first = poller.poll({'scope': 'global'})
        second = poller.poll({'scope': 'global'})
        self.assertEqual((first['generation'], second['generation']), (1, 2))
        poller.bump_generation()
        third = poller.poll({'scope': 'global'})
        self.assertEqual(third['generation'], 4)
        self.assertEqual(third['result']['generation'], 4)


class BlockedProviderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.fixture = PollerFixture(self.temp.name)
        self._pollers = []
        self._originals = []

    def tearDown(self):
        for target, method, orig in self._originals:
            setattr(target, method, orig)
        for poller in self._pollers:
            poller.drain(timeout=10)
            poller.close()
        self.temp.cleanup()

    def _poller(self, threads):
        store = self.fixture.codex(threads)
        poller = ProviderPoller(store)
        self._pollers.append(poller)
        return poller

    def _hold(self, target, method, fail_on_release=False):
        entered = threading.Event()
        release = threading.Event()
        calls = []
        orig = getattr(target, method)
        self._originals.append((target, method, orig))

        def blocking(*args, **kwargs):
            calls.append(1)
            entered.set()
            self.assertTrue(release.wait(timeout=30))
            if fail_on_release:
                raise RuntimeError('released-boom')
            return orig(*args, **kwargs)

        setattr(target, method, blocking)
        return entered, release, calls

    def _poll_thread(self, poller, prefs, **kw):
        outcome = {}
        thread = threading.Thread(
            target=lambda: outcome.setdefault(
                'out', poller.poll(prefs, **kw)),
            daemon=True)
        thread.start()
        return thread, outcome

    def test_stale_live_expires_while_blocked(self):
        from providers import CodexProvider
        poller = self._poller([{'id': 't1', 'working': True}])
        live = self._sync(poller, {'scope': 'global'}, active_title='t1',
                          detection_valid=True, now=NOW_S)
        self.assertTrue(live['selection']['live'])
        entered, release, calls = self._hold(CodexProvider, 'read')
        try:
            thread, _ = self._poll_thread(
                poller, {'scope': 'global'}, active_title='t1',
                detection_valid=True, now=NOW_S)
            self.assertTrue(entered.wait(timeout=10))
            thread.join(timeout=10)
            self.assertFalse(thread.is_alive())
            # Six seconds later with no fresh Codex data: Live expires
            # without waiting for the blocked operation.
            out = poller.poll({'scope': 'global'}, active_title='t1',
                              detection_valid=True, now=NOW_S + 6)
            self.assertFalse(out['selection']['live'])
            self.assertTrue(out['selection']['stale'])
        finally:
            release.set()

    def test_scope_change_mid_read_retires(self):
        from providers import CodexProvider
        poller = self._poller([{'id': 't1', 'working': True}, {'id': 't2'}])
        self._sync(poller, {'scope': 'conversation', 'pinned': 't2'},
                   active_title='t1', detection_valid=True)
        entered, release, _ = self._hold(CodexProvider, 'read')
        try:
            thread, _ = self._poll_thread(
                poller, {'scope': 'conversation', 'pinned': 't2'},
                active_title='t1', detection_valid=True)
            self.assertTrue(entered.wait(timeout=10))
            thread.join(timeout=10)
            # Change scope mid-read through the settings path.
            poller.apply_settings({'scope': 'project', 'pinned': ''})
            release.set()
            self.assertTrue(poller.drain())
            # The released old-scope result retires silently; settle the
            # new-scope read before asserting.
            poller.poll({'scope': 'project', 'pinned': ''},
                        active_title='t1', detection_valid=True)
            self.assertTrue(poller.drain())
            out = poller.poll({'scope': 'project', 'pinned': ''},
                              active_title='t1', detection_valid=True)
            # The released old-scope result cannot repaint.
            self.assertEqual(out['result'].get('scope'), 'project')
            self.assertNotEqual(out['result'].get('thread'), 't2')
        finally:
            release.set()

    def test_released_error_cannot_repaint(self):
        from providers import CodexProvider
        poller = self._poller([{'id': 't1', 'working': True}])
        first = self._sync(poller, {'scope': 'global'}, active_title='t1',
                           detection_valid=True)
        entered, release, _ = self._hold(CodexProvider, 'read',
                                         fail_on_release=True)
        try:
            thread, _ = self._poll_thread(
                poller, {'scope': 'global'}, active_title='t1',
                detection_valid=True)
            self.assertTrue(entered.wait(timeout=10))
            thread.join(timeout=10)
            release.set()
            self.assertTrue(poller.drain())
            out = poller.poll({'scope': 'global'}, active_title='t1',
                              detection_valid=True)
            # Explicit failure excludes immediately; the failed provider
            # is never selected, and nothing old repaints.
            self.assertFalse(out['selection']['live'])
            self.assertIsNone(out['selection']['selected'])
            self.assertFalse(
                poller._status['codex']['source_available'])
            self.assertIsNone(out['result'].get('working_context'))
        finally:
            release.set()

    def _sync(self, poller, prefs=None, **kw):
        poller.poll(prefs, **kw)
        self.assertTrue(poller.drain(), 'provider reads did not finish')
        return poller.poll(prefs, **kw)


class CodexEnumerationTests(unittest.TestCase):
    """Slice B: focus-independent verified-lifecycle Codex enumeration.

    The enumeration takes rows only — no title/foreground/UIA input
    exists — while the legacy detector keeps its foreground behavior
    untouched beside it."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name) / 'codex'
        self.home.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.temp.cleanup()

    def _rows(self):
        import sqlite3
        from contextlib import closing
        with closing(sqlite3.connect(self.home / 'state_1.sqlite')) as db:
            db.row_factory = sqlite3.Row
            return [dict(r) for r in db.execute('select * from threads')]

    def _append_event(self, thread, kind):
        import json
        line = json.dumps(dict(
            type='event_msg',
            timestamp=datetime.now(timezone.utc).isoformat(),
            payload=dict(type=kind))) + '\n'
        with open(self.home / f'{thread}.jsonl', 'a',
                   encoding='utf-8') as fh:
            fh.write(line)

    def test_working_task_enumerated_without_foreground(self):
        write_home(str(self.home), [{'id': 't1', 'working': True}])
        store = CodexStore(self.home)
        found = store.activity.enumerate_working_tasks(self._rows())
        self.assertEqual([item['thread'] for item in found], ['t1'])
        self.assertIsNotNone(found[0]['activity_at'])

    def test_foreground_elsewhere_leaves_membership_unchanged(self):
        write_home(str(self.home), [{'id': 't1', 'working': True},
                                    {'id': 't2', 'working': True}])
        store = CodexStore(self.home)
        rows = self._rows()
        # Legacy primary selection follows the foreground title when
        # it matches (isolated detectors so debounce cannot leak
        # across the two probes), but the enumerated set cannot move
        # with it.
        legacy_match = CodexStore(self.home).activity.detect(
            rows, 't1', True)['thread']
        legacy_other = CodexStore(self.home).activity.detect(
            rows, 'no-such-window', True)['thread']
        first = store.activity.enumerate_working_tasks(rows)
        second = store.activity.enumerate_working_tasks(rows)
        self.assertEqual(legacy_match, 't1')
        self.assertEqual(legacy_other, 't2')
        self.assertEqual([item['thread'] for item in first],
                         [item['thread'] for item in second])
        self.assertEqual([item['thread'] for item in first],
                         ['t1', 't2'])

    def test_recent_token_without_lifecycle_is_excluded(self):
        write_home(str(self.home), [{'id': 't1'}])
        self._append_event('t1', 'token_count')
        store = CodexStore(self.home)
        rows = self._rows()
        self.assertEqual(store.activity.enumerate_working_tasks(rows),
                         [])
        # TOKEN CHANGE != WORKING: a completed/idle task with very
        # recent accounting updates and no provider-trusted open turn
        # stays Not Working on BOTH APIs (the legacy recent-token
        # promotion is retired).
        legacy = store.activity.detect(rows, 't1', True)
        self.assertFalse(legacy['active'])
        self.assertEqual(legacy['reason'], 'no_running_session')

    def test_two_working_tasks_both_included(self):
        write_home(str(self.home), [{'id': 't1', 'working': True},
                                    {'id': 't2', 'working': True}])
        store = CodexStore(self.home)
        found = store.activity.enumerate_working_tasks(self._rows())
        self.assertEqual(sorted(item['thread'] for item in found),
                         ['t1', 't2'])

    def test_completion_removes_only_that_task(self):
        write_home(str(self.home), [{'id': 't1', 'working': True},
                                    {'id': 't2', 'working': True}])
        store = CodexStore(self.home)
        before = store.activity.enumerate_working_tasks(self._rows())
        self.assertEqual(sorted(item['thread'] for item in before),
                         ['t1', 't2'])
        self._append_event('t1', 'task_complete')
        after = store.activity.enumerate_working_tasks(self._rows())
        self.assertEqual([item['thread'] for item in after], ['t2'])

    def test_stale_and_missing_files_excluded(self):
        import os
        import time
        write_home(str(self.home), [{'id': 't1', 'working': True}])
        path = self.home / 't1.jsonl'
        old = time.time() - 400
        os.utime(path, (old, old))
        store = CodexStore(self.home)
        rows = [dict(id='t1', rollout_path=str(path)),
                dict(id='ghost', rollout_path=str(path) + '.missing')]
        self.assertEqual(store.activity.enumerate_working_tasks(rows),
                         [])

    def test_sensitive_thread_title_never_in_task_surface(self):
        import json
        import sqlite3
        from contextlib import closing
        write_home(str(self.home), [{'id': 't1', 'working': True}])
        secret = 'PRIVATE USER PROMPT TITLE'
        with closing(sqlite3.connect(self.home / 'state_1.sqlite')) as db:
            db.execute('UPDATE threads SET name=?, title=? WHERE id=?',
                       (secret, secret, 't1'))
            db.commit()
        store = CodexStore(self.home)
        rows = self._rows()
        found = store.activity.enumerate_working_tasks(rows)
        self.assertEqual([item['thread'] for item in found], ['t1'])
        read = store.read(active_title='nope', scope='global',
                          activity_detection_valid=True)
        tasks = read.get('active_tasks') or []
        self.assertEqual(len(tasks), 1)
        blob = json.dumps(tasks)
        self.assertNotIn(secret, blob)
        self.assertNotIn('t1.jsonl', blob)
        # Safe task-local metrics still work on the same task.
        task = tasks[0]
        self.assertTrue(task['working'])
        self.assertIn('tokens', task['presentation'])
        self.assertNotIn('title', task['display'])
        self.assertNotIn('name', task['display'])
        self.assertIsNone(task['display'].get('project'))
        # Legacy working_context path is unchanged by this fix: it
        # keeps its approved title behavior (documented, not new).
        self.assertEqual(read['working_context']['title'], secret)


class CodexWorkingPredicateTests(unittest.TestCase):
    """One shared task-level Working predicate for detect() + enumerate.

    Synthetic homes only. Every test asserts BOTH APIs agree: the
    enumerated set and the legacy detect() provider signal come from
    the same qualified candidates. TOKEN CHANGE != WORKING and
    foreground/focus never gate membership anywhere here.
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name) / 'codex'
        self.home.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.temp.cleanup()

    def _rows(self):
        import sqlite3
        from contextlib import closing
        with closing(sqlite3.connect(self.home / 'state_1.sqlite')) as db:
            db.row_factory = sqlite3.Row
            return [dict(r) for r in db.execute('select * from threads')]

    def _append_turn(self, thread, kind, turn_id=None, home=None):
        import json
        payload = dict(type=kind)
        if turn_id is not None:
            payload['turn_id'] = turn_id
        line = json.dumps(dict(
            type='event_msg', timestamp='2026-09-19T12:00:01Z',
            payload=payload)) + '\n'
        with open((home or self.home) / f'{thread}.jsonl', 'a',
                  encoding='utf-8') as handle:
            handle.write(line)

    def _write_ledger(self, turns):
        import sqlite3
        from contextlib import closing
        path = self.home / 'thread_history_1.sqlite'
        with closing(sqlite3.connect(path)) as db:
            db.execute('CREATE TABLE IF NOT EXISTS thread_turns '
                       '(thread_id TEXT, turn_id TEXT, status TEXT, '
                       'started_at REAL, completed_at REAL)')
            for turn in turns:
                db.execute('INSERT INTO thread_turns VALUES (?,?,?,?,?)',
                           (turn['thread_id'], turn.get('turn_id'),
                            turn['status'], turn.get('started_at'),
                            turn.get('completed_at')))
            db.commit()

    def _both(self, store, rows, expect):
        """Assert enumerate() and detect() agree; detect across titles."""
        found = store.activity.enumerate_working_tasks(rows)
        self.assertEqual(sorted(item['thread'] for item in found),
                         sorted(expect))
        for title in ('t1', 'no-such-window', ''):
            with self.subTest(title=title):
                signal = store.activity.detect(rows, title, True)
                if not expect:
                    self.assertFalse(signal['active'])
                    self.assertEqual(signal['reason'],
                                     'no_running_session')
                else:
                    self.assertTrue(signal['active'])
                    self.assertIn(signal['thread'], expect)

    def test_long_turn_start_outside_tail_recovers_via_ledger(self):
        import time
        now = time.time()
        write_home(str(self.home), [{'id': 't1'}])
        path = self.home / 't1.jsonl'
        start = ('{"type":"event_msg","timestamp":"2026-09-19T12:00:01Z",'
                 '"payload":{"type":"task_started","turn_id":"L1"}}\n')
        filler = ('{"type":"response_item","payload":{"type":"text",'
                  '"text":"' + 'x' * 200 + '"}}\n')
        with open(path, 'w', encoding='utf-8') as handle:
            handle.write(start)
            for _ in range(11000):
                handle.write(filler)
        self.assertGreater(path.stat().st_size, 2 * 1024 * 1024)
        self._write_ledger([dict(thread_id='t1', turn_id='L1',
                                 status='inProgress', started_at=now)])
        # Fresh store: empty detector cursors, as after a restart.
        store = CodexStore(self.home)
        self._both(store, self._rows(), ['t1'])
        found = store.activity.enumerate_working_tasks(self._rows())
        self.assertIsNotNone(found[0]['activity_at'])

    def test_stale_zombie_inprogress_is_not_working(self):
        import os
        import time
        now = time.time()
        write_home(str(self.home), [{'id': 't1'}])
        self._write_ledger([dict(thread_id='t1', turn_id='L1',
                                 status='inProgress', started_at=now)])
        path = self.home / 't1.jsonl'
        old = now - 400
        os.utime(path, (old, old))
        store = CodexStore(self.home)
        self._both(store, self._rows(), [])

    def test_turn_aborted_closes_immediately(self):
        write_home(str(self.home), [{'id': 't1'}])
        self._append_turn('t1', 'task_started', 'T1')
        self._append_turn('t1', 'turn_aborted', 'T1')
        store = CodexStore(self.home)
        self._both(store, self._rows(), [])

    def test_complete_with_recent_tokens_stays_not_working(self):
        write_home(str(self.home), [{'id': 't1'}])
        self._append_turn('t1', 'task_started', 'T1')
        self._append_turn('t1', 'task_complete', 'T1')
        self._append_turn('t1', 'token_count')
        store = CodexStore(self.home)
        self._both(store, self._rows(), [])

    def test_ledger_terminals_are_not_working(self):
        import time
        now = time.time()
        for status in ('completed', 'failed', 'interrupted'):
            with self.subTest(status=status):
                home = Path(self.temp.name) / f'codex-{status}'
                home.mkdir(parents=True, exist_ok=True)
                write_home(str(home), [{'id': 't1'}])
                with open(home / 't1.jsonl', 'a',
                          encoding='utf-8') as handle:
                    handle.write('{"type":"event_msg",'
                                 '"timestamp":"2026-09-19T12:00:01Z",'
                                 '"payload":{"type":"token_count"}}\n')
                path = home / 'thread_history_1.sqlite'
                import sqlite3
                from contextlib import closing
                with closing(sqlite3.connect(path)) as db:
                    db.execute('CREATE TABLE thread_turns '
                               '(thread_id TEXT, turn_id TEXT, status TEXT, '
                               'started_at REAL, completed_at REAL)')
                    db.execute('INSERT INTO thread_turns VALUES '
                               "(?,?,?,?,?)",
                               ('t1', 'L1', status, now, None))
                    db.commit()
                store = CodexStore(home)
                with closing(sqlite3.connect(
                        home / 'state_1.sqlite')) as db:
                    db.row_factory = sqlite3.Row
                    rows = [dict(r)
                            for r in db.execute('select * from threads')]
                found = store.activity.enumerate_working_tasks(rows)
                self.assertEqual(found, [])
                signal = store.activity.detect(rows, 't1', True)
                self.assertFalse(signal['active'])

    def test_old_terminal_does_not_close_new_start(self):
        import time
        now = time.time()
        write_home(str(self.home), [{'id': 't1'}])
        self._append_turn('t1', 'task_started', 'TA')
        self._append_turn('t1', 'task_complete', 'TA')
        self._append_turn('t1', 'task_started', 'TB')
        self._write_ledger([dict(thread_id='t1', turn_id='TB',
                                 status='inProgress', started_at=now)])
        store = CodexStore(self.home)
        self._both(store, self._rows(), ['t1'])

    def test_old_abort_does_not_close_new_start(self):
        import time
        now = time.time()
        write_home(str(self.home), [{'id': 't1'}])
        self._append_turn('t1', 'task_started', 'TA')
        self._append_turn('t1', 'turn_aborted', 'TA')
        self._append_turn('t1', 'task_started', 'TB')
        self._write_ledger([dict(thread_id='t1', turn_id='TB',
                                 status='inProgress', started_at=now)])
        store = CodexStore(self.home)
        self._both(store, self._rows(), ['t1'])

    def test_ledger_recovery_after_terminal(self):
        import time
        now = time.time()
        write_home(str(self.home), [{'id': 't1'}])
        self._append_turn('t1', 'task_started', 'TA')
        self._append_turn('t1', 'task_complete', 'TA')
        # Ledger names a strictly newer turn; the bounded tail never
        # saw its start, but fresh same-thread evidence corroborates.
        self._write_ledger([dict(thread_id='t1', turn_id='TB',
                                 status='inProgress', started_at=now)])
        store = CodexStore(self.home)
        self._both(store, self._rows(), ['t1'])

    def test_ledger_same_turn_race_terminal_wins(self):
        import time
        now = time.time()
        write_home(str(self.home), [{'id': 't1'}])
        self._append_turn('t1', 'task_started', 'T1')
        self._append_turn('t1', 'task_complete', 'T1')
        self._write_ledger([dict(thread_id='t1', turn_id='T1',
                                 status='inProgress', started_at=now)])
        store = CodexStore(self.home)
        self._both(store, self._rows(), [])

    def test_stale_ledger_terminal_ignored_for_open_turn(self):
        import time
        from usage import CodexActivityDetector
        now = time.time()
        write_home(str(self.home), [{'id': 't1', 'working': True}])
        old_start = (CodexActivityDetector._event_time(
            '2026-09-19T12:00:01Z') or now) - 100
        self._write_ledger([dict(thread_id='t1', turn_id='OLD',
                                 status='completed',
                                 started_at=old_start)])
        store = CodexStore(self.home)
        self._both(store, self._rows(), ['t1'])

    def test_running_and_idle_threads(self):
        write_home(str(self.home), [{'id': 'ta', 'working': True},
                                    {'id': 'tb', 'working': True}])
        self._append_turn('tb', 'task_complete')
        self._append_turn('tb', 'token_count')
        store = CodexStore(self.home)
        self._both(store, self._rows(), ['ta'])

    def test_two_concurrent_turns(self):
        write_home(str(self.home), [{'id': 'ta', 'working': True},
                                    {'id': 'tb', 'working': True}])
        store = CodexStore(self.home)
        found = store.activity.enumerate_working_tasks(self._rows())
        self.assertEqual(sorted(item['thread'] for item in found),
                         ['ta', 'tb'])
        for title in ('ta', 'no-such-window', ''):
            signal = store.activity.detect(self._rows(), title, True)
            self.assertTrue(signal['active'])
            self.assertIn(signal['thread'], ('ta', 'tb'))
            self.assertEqual(signal['working_count'], 2)

    def test_unreadable_rollout_fails_closed(self):
        import time
        now = time.time()
        write_home(str(self.home), [{'id': 't1'}])
        self._write_ledger([dict(thread_id='t1', turn_id='L1',
                                 status='inProgress', started_at=now)])
        store = CodexStore(self.home)
        rows = [dict(id='t1',
                     rollout_path=str(self.home / 'missing.jsonl'))]
        self._both(store, rows, [])

    def test_rollout_open_without_ledger_still_qualifies(self):
        write_home(str(self.home), [{'id': 't1', 'working': True}])
        store = CodexStore(self.home)
        self.assertFalse((self.home / 'thread_history_1.sqlite').exists())
        self._both(store, self._rows(), ['t1'])

    def test_production_store_resolves_ledger_from_home(self):
        import time
        now = time.time()
        write_home(str(self.home), [{'id': 't1'}])
        self._append_turn('t1', 'task_started', 'TA')
        self._append_turn('t1', 'task_complete', 'TA')
        self._write_ledger([dict(thread_id='t1', turn_id='TB',
                                 status='inProgress', started_at=now)])
        with patch.dict(os.environ, {'CODEX_HOME': str(self.home)}):
            store = CodexStore()
            self.assertEqual(store.activity.ledger.path,
                             self.home / 'thread_history_1.sqlite')
            found = store.activity.enumerate_working_tasks(self._rows())
            self.assertEqual([item['thread'] for item in found], ['t1'])

    def test_uia_invalid_cannot_veto_verified_working(self):
        write_home(str(self.home), [{'id': 't1', 'working': True}])
        store = CodexStore(self.home)
        rows = self._rows()
        self.assertEqual(
            [item['thread']
             for item in store.activity.enumerate_working_tasks(rows)],
            ['t1'])
        for valid in (True, False):
            for title in ('t1', 'unrelated-window', ''):
                with self.subTest(valid=valid, title=title):
                    signal = store.activity.detect(rows, title, valid)
                    self.assertTrue(signal['active'])
                    self.assertEqual(signal['thread'], 't1')

    def test_same_turn_ledger_terminal_vetoes_rollout_start(self):
        import time
        now = time.time()
        for status in ('completed', 'failed', 'interrupted'):
            with self.subTest(status=status):
                home = Path(self.temp.name) / f'codex-{status}'
                home.mkdir(parents=True, exist_ok=True)
                write_home(str(home), [{'id': 't1'}])
                self._append_turn('t1', 'task_started', 'T1', home=home)
                import json as json_module
                starts = [
                    json_module.loads(raw)
                    for raw in (home / 't1.jsonl').read_text(
                        encoding='utf-8').splitlines()
                    if raw.strip()]
                self.assertTrue(any(
                    line.get('type') == 'event_msg'
                    and (line.get('payload') or {}).get('type') == 'task_started'
                    and (line.get('payload') or {}).get('turn_id') == 'T1'
                    for line in starts),
                    'fixture must contain task_started turn T1')
                import sqlite3
                from contextlib import closing
                with closing(sqlite3.connect(
                        home / 'thread_history_1.sqlite')) as db:
                    db.execute('CREATE TABLE thread_turns '
                               '(thread_id TEXT, turn_id TEXT, status TEXT, '
                               'started_at REAL, completed_at REAL)')
                    db.execute('INSERT INTO thread_turns VALUES '
                               '(?,?,?,?,?)',
                               ('t1', 'T1', status, now, None))
                    db.commit()
                store = CodexStore(home)
                with closing(sqlite3.connect(
                        home / 'state_1.sqlite')) as db:
                    db.row_factory = sqlite3.Row
                    rows = [dict(r)
                            for r in db.execute('select * from threads')]
                self.assertEqual(
                    store.activity.enumerate_working_tasks(rows), [])
                signal = store.activity.detect(rows, 't1', True)
                self.assertFalse(signal['active'])

    def test_stale_inprogress_never_reopens_aborted_turn(self):
        import time
        from usage import CodexActivityDetector
        end = CodexActivityDetector._event_time('2026-09-19T12:00:01Z')
        write_home(str(self.home), [{'id': 't1'}])
        self._append_turn('t1', 'task_started', 'TB')
        self._append_turn('t1', 'turn_aborted', 'TB')
        # Ledger turn A is older, inside the skew window: still stale.
        self._write_ledger([dict(thread_id='t1', turn_id='LA',
                                 status='inProgress',
                                 started_at=end - 3)])
        store = CodexStore(self.home)
        self._both(store, self._rows(), [])
        # A strictly newer ledger turn still recovers.
        self._write_ledger([dict(thread_id='t1', turn_id='LC',
                                 status='inProgress',
                                 started_at=end + 10)])
        store = CodexStore(self.home)
        self._both(store, self._rows(), ['t1'])

    def test_close_turn_ids_within_skew_stay_distinct(self):
        import time
        from usage import CodexActivityDetector
        base = CodexActivityDetector._event_time('2026-09-19T12:00:01Z')
        write_home(str(self.home), [{'id': 't1'}])
        self._append_turn('t1', 'task_started', 'TA')
        self._append_turn('t1', 'task_complete', 'TA')
        self._append_turn('t1', 'task_started', 'TB')
        # Ledger terminal for TA starts 2s after TB's open: ids
        # differ, so TA cannot close TB despite proximity.
        self._write_ledger([dict(thread_id='t1', turn_id='TA',
                                 status='completed',
                                 started_at=base + 2)])
        store = CodexStore(self.home)
        self._both(store, self._rows(), ['t1'])
        self._append_turn('t1', 'turn_aborted', 'TB')
        self._both(store, self._rows(), [])

    def test_recovery_reaches_provider_projection(self):
        import time
        now = time.time()
        write_home(str(self.home), [{'id': 't1'}])
        self._append_turn('t1', 'task_started', 'TA')
        self._append_turn('t1', 'task_complete', 'TA')
        self._write_ledger([dict(thread_id='t1', turn_id='TB',
                                 status='inProgress', started_at=now)])
        store = CodexStore(self.home)
        read = store.read(active_title='nope', scope='global',
                          activity_detection_valid=True)
        tasks = read.get('active_tasks') or []
        self.assertEqual([t['task_key'] for t in tasks], ['t1'])
        self.assertTrue(tasks[0]['working'])


class ActiveTaskPollerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self._pollers = []
        self._counter = 0

    def tearDown(self):
        for poller in self._pollers:
            poller.drain(timeout=10)
            poller.close()
        self.temp.cleanup()

    def _codex_home(self, name, threads):
        home = Path(self.temp.name) / name
        home.mkdir(exist_ok=True)
        write_home(str(home), threads)
        return home

    def _poller(self, home):
        poller = ProviderPoller(CodexStore(home))
        self._pollers.append(poller)
        return poller

    def _sync_poll(self, poller, prefs=None, **kw):
        out = poller.poll(prefs, **kw)
        self.assertTrue(poller.drain(), 'provider reads did not finish')
        out = poller.poll(prefs, **kw)
        self.assertTrue(poller.drain(), 'provider reads did not finish')
        return poller.poll(prefs, **kw)

    def _wall_ms(self):
        import time
        return int(time.time() * 1000)

    def _keys(self, out):
        return [t['task_key'] for t in out.get('active_tasks') or []]

    def test_codex_completion_removes_only_that_task(self):
        home = self._codex_home('codex-a',
                                [{'id': 't1', 'working': True},
                                 {'id': 't2', 'working': True}])
        poller = self._poller(home)
        out = self._sync_poll(poller, {'scope': 'global'})
        self.assertEqual(sorted(self._keys(out)), ['t1', 't2'])
        import json
        from datetime import datetime, timezone
        line = json.dumps(dict(
            type='event_msg',
            timestamp=datetime.now(timezone.utc).isoformat(),
            payload=dict(type='task_complete'))) + '\n'
        with open(home / 't1.jsonl', 'a', encoding='utf-8') as fh:
            fh.write(line)
        out = self._sync_poll(poller, {'scope': 'global'})
        self.assertEqual(self._keys(out), ['t2'])

    def test_failure_result_carries_no_stale_membership(self):
        # Reported shape: selection not live + provider unavailable,
        # yet active_tasks previously held ['t1']. The failure result
        # must derive membership from the failure state: empty.
        now_ms = self._wall_ms()
        home = self._codex_home('codex-h',
                                [{'id': 't1', 'working': True}])
        poller = self._poller(home)
        live = self._sync_poll(
            poller, {'scope': 'global', 'tracking_provider': 'codex'})
        self.assertEqual(self._keys(live), ['t1'])
        import shutil
        self.assertTrue(poller.drain(timeout=10))
        shutil.rmtree(home)
        out = self._sync_poll(
            poller, {'scope': 'global', 'tracking_provider': 'codex'})
        self.assertFalse(out['selection']['live'])
        self.assertFalse(out['result']['available'])
        self.assertEqual(out.get('active_tasks'), [])
        failed = poller._active_sets['codex']
        self.assertFalse(failed['valid'])
        self.assertEqual(failed['tasks'], ())

    def test_late_success_after_failure_stays_retired(self):
        # Newer failure retires A; an older success arriving late must
        # not resurrect it. Monotonic per-lane acceptance decides.
        from types import SimpleNamespace
        now_ms = self._wall_ms()
        home = self._codex_home('codex-j',
                                [{'id': 't1', 'working': True}])
        poller = self._poller(home)
        out = self._sync_poll(poller, {'scope': 'global'})
        self.assertEqual(self._keys(out), ['t1'])
        stored = poller._active_sets['codex']
        current_rev = stored['provider_revision']
        poller._store_active_set_locked(
            'codex', SimpleNamespace(rid=current_rev + 1,
                                     now=now_ms / 1000), None)
        retired = poller._active_sets['codex']
        self.assertFalse(retired['valid'])
        self.assertEqual(retired['tasks'], ())
        from providers import active_task
        ghost = dict(active_task('codex', 't1'), working=True,
                     activity_valid=True)
        poller._store_active_set_locked(
            'codex', SimpleNamespace(rid=current_rev,
                                     now=now_ms / 1000 - 1),
            {'payload': {'active_tasks': [ghost]}})
        still = poller._active_sets['codex']
        self.assertFalse(still['valid'])
        self.assertEqual(still['tasks'], ())
        self.assertEqual(still['provider_revision'], current_rev + 1)

    def test_late_failure_cannot_erase_newer_success(self):
        # Newer success holds A; an older failure arriving late must
        # not erase it.
        from types import SimpleNamespace
        now_ms = self._wall_ms()
        home = self._codex_home('codex-k',
                                [{'id': 't1', 'working': True}])
        poller = self._poller(home)
        out = self._sync_poll(poller, {'scope': 'global'})
        self.assertEqual(self._keys(out), ['t1'])
        stored = poller._active_sets['codex']
        current_rev = stored['provider_revision']
        poller._store_active_set_locked(
            'codex', SimpleNamespace(rid=current_rev - 1,
                                     now=now_ms / 1000 - 1), None)
        kept = poller._active_sets['codex']
        self.assertTrue(kept['valid'])
        self.assertEqual([t['task_key'] for t in kept['tasks']], ['t1'])
        self.assertEqual(kept['provider_revision'], current_rev)


class ActiveTaskFilterTests(unittest.TestCase):
    """Slice B: headless Auto/manual membership over accepted sets —
    pure function, immediate, no debounce, no focus input."""

    def _sets(self):
        from providers import active_task, active_task_set
        codex = active_task_set(
            'codex', [active_task('codex', 'A'),
                      active_task('codex', 'B')],
            revision=5, observed_at=1000.0, valid=True,
            source_available=True)
        opencode = active_task_set(
            'opencode', [active_task('opencode', 'C'),
                         active_task('opencode', 'D'),
                         active_task('opencode', 'E')],
            revision=7, observed_at=1000.0, valid=True,
            source_available=True)
        statuses = {
            'codex': dict(provider_id='codex', source_available=True),
            'opencode': dict(provider_id='opencode',
                             source_available=True)}
        return {'codex': codex, 'opencode': opencode}, statuses

    def _keys(self, tasks):
        return [t['task_key'] for t in tasks]

    def test_legacy_auto_ignores_foreign_sets(self):
        from provider_poller import filter_active_tasks
        sets, statuses = self._sets()
        merged = filter_active_tasks(
            sets, statuses, {'codex': 1000.0, 'opencode': 1000.0},
            'auto', now=1001.0)
        self.assertEqual(self._keys(merged), ['A', 'B'])

    def test_legacy_choices_expose_only_codex(self):
        from provider_poller import filter_active_tasks
        sets, statuses = self._sets()
        success = {'codex': 1000.0, 'opencode': 1000.0}
        self.assertEqual(
            self._keys(filter_active_tasks(
                sets, statuses, success, 'codex', now=1001.0)),
            ['A', 'B'])
        self.assertEqual(
            self._keys(filter_active_tasks(
                sets, statuses, success, 'opencode', now=1001.0)),
            ['A', 'B'])

    def test_preference_switch_is_immediate(self):
        from provider_poller import filter_active_tasks
        sets, statuses = self._sets()
        success = {'codex': 1000.0, 'opencode': 1000.0}
        first = filter_active_tasks(sets, statuses, success, 'codex',
                                    now=1001.0)
        second = filter_active_tasks(sets, statuses, success, 'auto',
                                     now=1001.0)
        third = filter_active_tasks(sets, statuses, success, 'opencode',
                                    now=1001.0)
        self.assertEqual(self._keys(first), ['A', 'B'])
        self.assertEqual(self._keys(second), ['A', 'B'])
        self.assertEqual(self._keys(third), ['A', 'B'])

    def test_unknown_preference_falls_back_to_codex(self):
        from provider_poller import filter_active_tasks
        sets, statuses = self._sets()
        merged = filter_active_tasks(
            sets, statuses, {'codex': 1000.0, 'opencode': 1000.0},
            'claude', now=1001.0)
        self.assertEqual(self._keys(merged), ['A', 'B'])

    def test_stale_and_invalid_sets_dropped(self):
        from provider_poller import filter_active_tasks
        sets, statuses = self._sets()
        merged = filter_active_tasks(
            sets, statuses, {'codex': 1000.0, 'opencode': 990.0},
            'auto', now=1001.0)
        self.assertEqual(self._keys(merged), ['A', 'B'])
        sets['codex'] = dict(sets['codex'], valid=False)
        merged = filter_active_tasks(
            sets, statuses, {'codex': 1000.0, 'opencode': 1000.0},
            'auto', now=1001.0)
        self.assertEqual(self._keys(merged), [])

    def test_repeated_calls_are_deterministic(self):
        from provider_poller import filter_active_tasks
        sets, statuses = self._sets()
        success = {'codex': 1000.0, 'opencode': 1000.0}
        first = filter_active_tasks(sets, statuses, success, 'auto',
                                    now=1001.0)
        second = filter_active_tasks(sets, statuses, success, 'auto',
                                     now=1001.0)
        self.assertEqual(self._keys(first), self._keys(second))


class CodexProductBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.poller = ProviderPoller(PollerFixture(self.temp.name).codex([
            {'id': 't1', 'working': True}, {'id': 't2'}]))
        self.prefs = {'scope': 'global', 'tracking_provider': 'codex'}
        self.releases = []

    def tearDown(self):
        for release in self.releases:
            release.set()
        self.poller.close()
        for worker in self.poller._workers.values():
            worker.join(timeout=10)
            self.assertFalse(worker.is_alive())
        self.temp.cleanup()

    def settle(self, prefs=None):
        for _ in range(3):
            out = self.poller.poll(prefs or self.prefs, active_title='t1',
                                   detection_valid=True, now=NOW_S)
            self.assertTrue(self.poller.drain())
        return out

    def block_read(self):
        entered, release = threading.Event(), threading.Event()
        self.releases.append(release)
        original = self.poller.codex.read
        def read(**kwargs):
            entered.set()
            self.assertTrue(release.wait(timeout=10))
            return original(**kwargs)
        self.poller.codex.read = read
        self.poller.poll(self.prefs, active_title='t1', detection_valid=True, now=NOW_S)
        self.assertTrue(entered.wait(timeout=10))
        return release

    def test_normal_runtime_never_imports_or_instantiates_opencode(self):
        import subprocess
        import sys
        code = '''
import builtins, sys, tempfile
from pathlib import Path
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name == 'opencode_provider' or name.startswith('opencode_provider.'):
        raise AssertionError('historical adapter imported by active runtime')
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
from provider_poller import ProviderPoller, PROVIDER_KEYS, POOL_THREADS
from providers import PROVIDER_REGISTRY
from provider_selection import TRACKING_CHOICES
from usage import CodexStore
with tempfile.TemporaryDirectory() as root:
    p = ProviderPoller(CodexStore(Path(root)))
    assert not hasattr(p, 'opencode')
    for preference in ('auto', 'opencode', 'codex', None, ['opencode']):
        for _ in range(3):
            out = p.loop_tick({'tracking_provider': preference}, now=1000)
            assert p.drain()
        assert out['preference'] == out['provider_id'] == 'codex'
        assert 'opencode' not in out and 'opencode_activity' not in out
        assert set(p._workers) == {'codex'}
    p.close()
    assert p.poll()['active_tasks'] == []
assert PROVIDER_KEYS == TRACKING_CHOICES == tuple(PROVIDER_REGISTRY) == ('codex',)
assert POOL_THREADS == 1 and 'opencode_provider' not in sys.modules
'''
        result = subprocess.run([sys.executable, '-c', code], cwd=Path(__file__).parent.parent,
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_old_preferences_preserve_codex_payload_identity_and_membership(self):
        before = self.settle()
        for preference in ('auto', 'opencode', 'bogus', None, [], {}):
            with self.subTest(preference=preference):
                out = self.poller.apply_settings(
                    dict(self.prefs, tracking_provider=preference), now=NOW_S)
                self.assertEqual(out['preference'], 'codex')
                self.assertEqual(out['result']['tokens'], before['result']['tokens'])
                self.assertEqual([t['task_key'] for t in out['active_tasks']], ['t1'])
                self.assertEqual(self.poller.selection.last_use, {})

    def test_config_migration_does_not_rewrite_original_file(self):
        import json
        from app_config import load_preferences
        path = Path(self.temp.name) / 'preferences.json'
        for preference in ('auto', 'opencode', ['opencode'], {'provider': 'opencode'}):
            raw = json.dumps({'tracking_provider': preference, 'user_note': 'keep'})
            path.write_text(raw, encoding='utf-8')
            before = path.read_bytes()
            loaded = load_preferences(path)
            self.assertEqual(loaded['tracking_provider'], 'codex')
            self.assertEqual(loaded['user_note'], 'keep')
            self.assertEqual(path.read_bytes(), before)
        path.write_text('{broken', encoding='utf-8')
        self.assertEqual(load_preferences(path)['tracking_provider'], 'codex')
        self.assertEqual(path.read_text(encoding='utf-8'), '{broken')

    def test_default_selector_and_submit_reject_foreign_provider(self):
        from provider_selection import ProviderSelection
        from provider_poller import _Tick
        foreign = dict(provider_id='opencode', source_available=True,
                       available=True, working=True, activity_valid=True,
                       activity_at=NOW_S, last_success_at=NOW_S)
        selector = ProviderSelection()
        for preference in ('auto', 'opencode', None):
            snap = selector.update({'opencode': foreign}, preference=preference,
                                   generation=1, now=NOW_S)
            self.assertIsNone(snap['selected'])
            self.assertFalse(snap['live'])
            self.assertEqual(snap['preference'], 'codex')
        tick = _Tick(0, 0, 'codex', 'global', '', False, '', False, NOW_S)
        self.assertFalse(self.poller._submit('opencode', tick))
        self.assertEqual(self.poller._workers, {})
        self.assertEqual(self.poller._rid, 0)

    def test_blocked_read_uses_one_daemon_slot(self):
        release = self.block_read()
        future = self.poller._inflight['codex']
        for _ in range(10):
            self.poller.poll(self.prefs, now=NOW_S)
            self.assertIs(self.poller._inflight['codex'], future)
        self.assertEqual(tuple(self.poller._workers), ('codex',))
        self.assertTrue(self.poller._workers['codex'].daemon)
        release.set()
        self.assertTrue(self.poller.drain())

    def test_close_during_read_is_terminal_and_idempotent(self):
        self.settle()
        release = self.block_read()
        worker = self.poller._workers['codex']
        before = dict(self.poller._accepted_rid)
        self.poller.close()
        generation = self.poller.generation
        self.poller.close()
        self.assertEqual(self.poller.generation, generation)
        self.assertTrue(worker.is_alive())
        release.set()
        worker.join(timeout=10)
        self.assertFalse(worker.is_alive())
        self.poller._collect()
        self.assertEqual(self.poller._accepted_rid, before)
        out = self.poller.poll(self.prefs, now=NOW_S)
        self.assertEqual(out['active_tasks'], [])
        self.assertFalse(out['selection']['live'])
        self.assertIsNone(out['result']['working_context'])

    def test_failed_reset_fences_old_success_and_retains_adapter(self):
        self.settle()
        old = self.poller.codex
        release = self.block_read()
        before = dict(self.poller._accepted_rid)
        with patch('provider_poller.CodexStore', side_effect=RuntimeError('reset failed')):
            out = self.poller.loop_tick(self.prefs, reset_requested=True, now=NOW_S)
        self.assertIs(self.poller.codex, old)
        self.assertFalse(out['selection']['live'])
        self.assertEqual(out['active_tasks'], [])
        release.set()
        self.assertTrue(self.poller.drain())
        self.poller._collect()
        self.assertEqual(self.poller._accepted_rid, before)
        self.assertFalse(self.poller._status['codex']['source_available'])
        self.assertFalse(self.poller._active_sets['codex']['valid'])

    def test_successful_reset_retires_old_adapter_completion(self):
        self.settle()
        release = self.block_read()
        old = self.poller.codex
        before = dict(self.poller._accepted_rid)
        replacement = PollerFixture(Path(self.temp.name) / 'replacement').codex([
            {'id': 'new', 'working': True}])
        with patch('provider_poller.CodexStore', return_value=replacement):
            self.poller.reset_codex()
        self.assertIsNot(self.poller.codex, old)
        release.set()
        self.assertTrue(self.poller.drain())
        self.poller._collect()
        self.assertEqual(self.poller._accepted_rid, before)
        out = self.settle()
        self.assertEqual([t['task_key'] for t in out['active_tasks']], ['new'])

    def test_scope_change_keeps_verified_membership_and_live_context(self):
        self.settle()
        out = self.poller.apply_settings({'scope': 'conversation', 'pinned': 't2'}, now=NOW_S)
        self.assertFalse(out['result']['available'])
        self.assertEqual(out['result']['scope'], 'conversation')
        self.assertEqual(out['result']['working_context']['thread'], 't1')
        out = self.settle({'scope': 'conversation', 'pinned': 't2'})
        self.assertEqual(out['result']['thread'], 't2')
        self.assertEqual(out['result']['working_context']['thread'], 't1')
        self.assertEqual([t['task_key'] for t in out['active_tasks']], ['t1'])

    def test_cache_requires_exact_codex_identity_without_prefix_stripping(self):
        from provider_poller import _compatible
        prov = {'scope': 'conversation', 'pinned': 'opencode:t2'}
        self.assertFalse(_compatible(prov, 'conversation', 't2'))
        self.assertTrue(_compatible(prov, 'conversation', 'opencode:t2'))
        self.assertFalse(_compatible(prov, 'project', 'opencode:t2'))
        self.assertTrue(_compatible({'scope': 'global'}, 'global', 'any'))
        self.settle()
        self.poller._provenance['codex'] = prov
        out = self.poller.apply_settings({'scope': 'conversation', 'pinned': 't2'}, now=NOW_S)
        self.assertFalse(out['result']['available'])
        self.assertNotIn('tokens', out['result'])

    def test_task_sets_reject_foreign_lane_and_foreign_inner_identity(self):
        from types import SimpleNamespace
        from providers import active_task
        self.settle()
        revision = self.poller._active_sets['codex']['provider_revision']
        request = SimpleNamespace(rid=revision + 1, now=NOW_S)
        payload = {'payload': {'active_tasks': [active_task('codex', 't1'),
                                               active_task('opencode', 'foreign')]}}
        self.poller._store_active_set_locked('opencode', request, payload)
        self.assertNotIn('opencode', self.poller._active_sets)
        self.poller._store_active_set_locked('codex', request, payload)
        tasks = self.poller._merged_active_tasks('auto', NOW_S)
        self.assertEqual([t['task_key'] for t in tasks], ['t1'])
