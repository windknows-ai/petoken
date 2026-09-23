"""Slice 5: provider poller orchestration. Qt-free, synthetic stores."""
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
from tests.test_opencode_provider import (BASE_MS, make_message, make_part,
                                          make_session, write_store)
from tests.test_providers import write_home
from usage import CodexStore

NOW_S = BASE_MS / 1000 + 100
TOKEN_EPOCH = datetime(2026, 9, 19, 12, 0, 2,
                       tzinfo=timezone.utc).timestamp()


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

    def opencode(self, sessions, messages=(), parts=()):
        path = self._fresh('open.db')
        write_store(path, sessions, messages, parts)
        return path


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

    def _poller(self, threads, sessions, messages=(), parts=()):
        store = self.fixture.codex(threads)
        db = self.fixture.opencode(sessions, messages, parts)
        poller = ProviderPoller(store, db)
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
        poller = self._poller([{'id': 't1', 'working': True}],
                              [make_session('ses_1')])
        out = self._sync_poll(poller, {'scope': 'global'}, active_title='t1',
                          detection_valid=True)
        self.assertEqual(out['provider_id'], 'codex')
        self.assertTrue(out['selection']['live'])
        self.assertEqual(out['result']['provider_id'], 'codex')
        self.assertEqual(out['result']['working_context']['thread'], 't1')
        self.assertEqual(out['codex']['provider_id'], 'codex')

    def test_opencode_working_selected_live(self):
        poller = self._poller(
            [{'id': 't1'}],
            [make_session('ses_live', updated=BASE_MS)],
            [make_message('m1', 'ses_live')],
            [make_part('p1', 'ses_live', created=BASE_MS - 100000)])
        out = self._sync_poll(poller, {'scope': 'global'}, detection_valid=False,
                          now=NOW_S)
        self.assertEqual(out['provider_id'], 'opencode')
        self.assertTrue(out['selection']['live'])
        result = out['result']
        # Raw categories travel; total stays unknown, never summed.
        self.assertEqual(result['tokens']['input'], 100)
        self.assertIsNone(result['tokens']['total'])
        self.assertEqual(result['working_context']['thread'], 'ses_live')
        self.assertEqual(result['working_context']['project'], 'alpha')

    def test_both_working_newest_wins_coherently(self):
        open_start = BASE_MS - 100000  # far newer than the Codex sample
        poller = self._poller(
            [{'id': 't1', 'working': True}],
            [make_session('ses_new', updated=BASE_MS)],
            [make_message('m1', 'ses_new')],
            [make_part('p1', 'ses_new', created=open_start)])
        out = self._sync_poll(poller, {'scope': 'global'}, active_title='t1',
                          detection_valid=True, now=NOW_S)
        self.assertEqual(out['provider_id'], 'opencode')
        # Winner coherence: selected tokens are the winner's own.
        self.assertEqual(out['result']['tokens']['input'], 100)
        self.assertNotEqual(out['result']['tokens']['input'],
                            out['codex']['tokens']['input_tokens'])
        # And back: an older OpenCode open loses to Codex work.
        old_start = int((TOKEN_EPOCH - 500) * 1000)
        poller_old = self._poller(
            [{'id': 't1', 'working': True}],
            [make_session('ses_old', updated=old_start)],
            [make_message('m1', 'ses_old')],
            [make_part('p1', 'ses_old', created=old_start)])
        out_old = self._sync_poll(poller_old,
            {'scope': 'global'}, active_title='t1', detection_valid=True,
            now=TOKEN_EPOCH + 300)
        self.assertEqual(out_old['provider_id'], 'codex')
        self.assertEqual(out_old['result']['working_context']['thread'],
                         't1')

    def test_manual_wins_without_marking_use(self):
        poller = self._poller(
            [{'id': 't1', 'working': True}],
            [make_session('ses_1', updated=BASE_MS)],
            [make_message('m1', 'ses_1')],
            [make_part('p1', 'ses_1', created=BASE_MS - 100000)])
        out = self._sync_poll(poller, {'scope': 'global',
                           'tracking_provider': 'opencode'},
                          active_title='t1', detection_valid=True, now=NOW_S)
        self.assertEqual(out['provider_id'], 'opencode')
        self.assertEqual(out['selection']['reason'], 'manual')
        # Polling never fabricates use time, even for manual preference.
        self.assertEqual(poller.selection.last_use, {})
        self.assertEqual(normalize_tracking_provider('bogus'), 'auto')

    def test_codex_failure_does_not_block_opencode(self):
        poller = self._poller(
            [{'id': 't1'}],
            [make_session('ses_1', updated=BASE_MS)],
            [make_message('m1', 'ses_1')],
            [make_part('p1', 'ses_1', created=BASE_MS - 100000)])
        with patch.object(CodexProvider, 'read',
                          side_effect=RuntimeError('boom')):
            out = self._sync_poll(poller, {'scope': 'global'}, now=NOW_S)
        self.assertEqual(out['provider_id'], 'opencode')
        self.assertTrue(out['selection']['live'])
        self.assertEqual(out['codex']['reason'], 'status_read_failed')

    def test_opencode_failure_does_not_block_codex(self):
        poller = self._poller([{'id': 't1', 'working': True}],
                              [make_session('ses_1')])
        with patch.object(poller.opencode, 'read',
                          side_effect=RuntimeError('boom')):
            out = self._sync_poll(poller, {'scope': 'global'}, active_title='t1',
                              detection_valid=True)
        self.assertEqual(out['provider_id'], 'codex')
        self.assertTrue(out['selection']['live'])
        self.assertFalse(out['opencode']['available'])

    def test_generation_increments_and_bump(self):
        poller = self._poller([{'id': 't1'}], [make_session('ses_1')])
        # Generation counting is synchronous and needs no completions.
        first = poller.poll({'scope': 'global'})
        second = poller.poll({'scope': 'global'})
        self.assertEqual((first['generation'], second['generation']), (1, 2))
        poller.bump_generation()
        third = poller.poll({'scope': 'global'})
        self.assertEqual(third['generation'], 4)
        self.assertEqual(third['result']['generation'], 4)

    def test_scope_selection_stays_separate_from_working(self):
        poller = self._poller(
            [{'id': 't1', 'working': True}, {'id': 't2'}],
            [make_session('ses_a', project='proj-a',
                          directory='/synthetic/alpha',
                          tokens=(10, 1, 1, 1, 0)),
             make_session('ses_b', project='proj-b',
                          directory='/synthetic/beta',
                          tokens=(20, 2, 2, 2, 0),
                          updated=BASE_MS),
             ],
            [make_message('m1', 'ses_b')],
            [make_part('p1', 'ses_b', created=BASE_MS - 100000)])
        # Codex: pinned analytics session t2, working session t1.
        codex = self._sync_poll(poller, {'scope': 'conversation', 'pinned': 't2'},
                            active_title='t1', detection_valid=True)
        self.assertEqual(codex['result'].get('thread'), 't2')
        self.assertEqual(codex['result']['working_context']['thread'], 't1')
        # OpenCode: pinned ses_a, working ses_b (newer lifecycle wins).
        # Prefs change goes through apply_settings like production, so
        # the old pinned-t2 completions retire instead of repainting.
        opencode = self._resync(poller, {'scope': 'conversation', 'pinned': 'ses_a',
                                 'tracking_provider': 'opencode'},
                                now=NOW_S)
        self.assertEqual(opencode['result']['session_id'],
                         'opencode:ses_a')
        self.assertEqual(opencode['result']['tokens']['input'], 10)
        context = opencode['result']['working_context']
        self.assertEqual(context['thread'], 'ses_b')
        self.assertEqual(context['project'], 'beta')
        self.assertEqual(context['tokens']['input'], 20)

    def test_no_combined_totals_anywhere(self):
        poller = self._poller(
            [{'id': 't1', 'working': True}],
            [make_session('ses_1', updated=BASE_MS)],
            [make_message('m1', 'ses_1')],
            [make_part('p1', 'ses_1', created=BASE_MS - 100000)])
        out = self._sync_poll(poller, {'scope': 'global'}, active_title='t1',
                          detection_valid=True, now=NOW_S)
        blob = repr(out['result']) + repr(out['selection'])
        self.assertNotIn('combined', blob)
        if out['provider_id'] == 'opencode':
            self.assertIsNone(out['result']['tokens']['total'])


class BlockedProviderTests(unittest.TestCase):
    """Latency isolation with Event-held reads. No sleeps: Events order
    every step; join timeouts only guard against hangs (failure, not
    timing)."""

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

    def tearDown(self):
        for target, method, orig in self._originals:
            setattr(target, method, orig)
        for poller in self._pollers:
            poller.drain(timeout=10)
            poller.close()
        self.temp.cleanup()

    def _poller(self, threads, sessions, messages=(), parts=()):
        store = self.fixture.codex(threads)
        db = self.fixture.opencode(sessions, messages, parts)
        poller = ProviderPoller(store, db)
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

    def _live_opencode_poller(self):
        return self._poller(
            [{'id': 't1'}],
            [make_session('ses_1', updated=BASE_MS)],
            [make_message('m1', 'ses_1')],
            [make_part('p1', 'ses_1', created=BASE_MS - 100000)])

    def test_held_codex_opencode_updates_independently(self):
        from providers import CodexProvider
        poller = self._live_opencode_poller()
        entered, release, calls = self._hold(CodexProvider, 'read')
        try:
            thread, outcome = self._poll_thread(
                poller, {'scope': 'global'}, now=NOW_S)
            self.assertTrue(entered.wait(timeout=10))
            # The tick returns promptly with OpenCode data while Codex
            # is still blocked: pre-fix sequential reads hang here.
            thread.join(timeout=10)
            self.assertFalse(thread.is_alive())
            # Wait only for the unblocked provider, then decide.
            poller._inflight['opencode'].result(timeout=10)
            out = poller.poll({'scope': 'global'}, now=NOW_S)
            self.assertEqual(out['provider_id'], 'opencode')
            self.assertTrue(out['selection']['live'])
            self.assertEqual(out['result']['tokens']['input'], 100)
            self.assertFalse(poller._status['codex']['source_available'])
            # Single-flight: many more ticks submit nothing new for the
            # blocked provider, and total in-flight stays bounded.
            for _ in range(5):
                poller.poll({'scope': 'global'}, now=NOW_S)
            self.assertEqual(len(calls), 1)
            in_flight = [f for f in poller._inflight.values()
                         if not f.done()]
            self.assertLessEqual(len(in_flight), 2)
        finally:
            release.set()

    def test_held_opencode_codex_updates_independently(self):
        from opencode_provider import OpenCodeProvider
        poller = self._poller([{'id': 't1', 'working': True}],
                              [make_session('ses_1')])
        entered, release, calls = self._hold(OpenCodeProvider, 'read')
        try:
            thread, outcome = self._poll_thread(
                poller, {'scope': 'global'}, active_title='t1',
                detection_valid=True)
            self.assertTrue(entered.wait(timeout=10))
            thread.join(timeout=10)
            self.assertFalse(thread.is_alive())
            poller._inflight['codex'].result(timeout=10)
            out = poller.poll({'scope': 'global'}, active_title='t1',
                              detection_valid=True)
            self.assertEqual(out['provider_id'], 'codex')
            self.assertTrue(out['selection']['live'])
            poller.poll({'scope': 'global'}, active_title='t1',
                        detection_valid=True)
            self.assertEqual(len(calls), 1)
        finally:
            release.set()

    def test_stale_live_expires_while_blocked(self):
        from providers import CodexProvider
        poller = self._poller([{'id': 't1', 'working': True}],
                              [make_session('ses_1')])
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

    def test_manual_mid_read_both_directions(self):
        from providers import CodexProvider
        poller = self._poller([{'id': 't1', 'working': True}],
                              [make_session('ses_1', updated=BASE_MS)])
        live = self._sync(poller, {'scope': 'global'}, active_title='t1',
                          detection_valid=True, now=NOW_S)
        self.assertTrue(live['selection']['live'])
        self.assertEqual(live['selection']['selected'], 'codex')
        entered, release, _ = self._hold(CodexProvider, 'read')
        try:
            thread, _ = self._poll_thread(
                poller, {'scope': 'global'}, active_title='t1',
                detection_valid=True, now=NOW_S)
            self.assertTrue(entered.wait(timeout=10))
            thread.join(timeout=10)
            self.assertFalse(thread.is_alive())
            # Manual OpenCode applies immediately from cache: no release.
            manual = poller.apply_settings(
                {'scope': 'global', 'tracking_provider': 'opencode'},
                mark_provider='opencode', now=NOW_S)
            self.assertEqual(manual['selection']['selected'], 'opencode')
            self.assertIn('opencode', poller.selection.last_use)
            # Release the old read: retired epoch discards it, and the
            # manual winner stands through the settle.
            release.set()
            self.assertTrue(poller.drain())
            settled = poller.poll({'scope': 'global',
                                   'tracking_provider': 'opencode'},
                                  now=NOW_S)
            self.assertEqual(settled['selection']['selected'], 'opencode')
            # And back while OpenCode is the blocked one.
            from opencode_provider import OpenCodeProvider
            entered2, release2, _ = self._hold(OpenCodeProvider, 'read')
            try:
                thread2, _ = self._poll_thread(
                    poller, {'scope': 'global',
                             'tracking_provider': 'opencode'}, now=NOW_S)
                self.assertTrue(entered2.wait(timeout=10))
                thread2.join(timeout=10)
                self.assertFalse(thread2.is_alive())
                back = poller.apply_settings(
                    {'scope': 'global', 'tracking_provider': 'codex'},
                    mark_provider='codex', now=NOW_S)
                self.assertEqual(back['selection']['selected'], 'codex')
            finally:
                release2.set()
        finally:
            release.set()

    def test_scope_change_mid_read_retires(self):
        from providers import CodexProvider
        poller = self._poller(
            [{'id': 't1', 'working': True}, {'id': 't2'}],
            [make_session('ses_1')])
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
        poller = self._poller([{'id': 't1', 'working': True}],
                              [make_session('ses_1')])
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
            self.assertEqual(out['selection']['selected'], 'opencode')
            self.assertFalse(
                poller._status['codex']['source_available'])
            self.assertIsNone(out['result'].get('working_context'))
        finally:
            release.set()

    def _sync(self, poller, prefs=None, **kw):
        poller.poll(prefs, **kw)
        self.assertTrue(poller.drain(), 'provider reads did not finish')
        return poller.poll(prefs, **kw)


class ActiveSessionPollerTests(unittest.TestCase):
    """Blocker 1: a verified live OpenCode session must reach the panel
    even when the requested scope names no session. All values shown
    must come from that one session row."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.fixture = PollerFixture(self.temp.name)
        self._pollers = []

    def tearDown(self):
        for poller in self._pollers:
            poller.drain(timeout=10)
            poller.close()
        self.temp.cleanup()

    def _stores(self, threads, sessions, messages=(), parts=()):
        store = self.fixture.codex(threads)
        db = self.fixture.opencode(sessions, messages, parts)
        poller = ProviderPoller(store, db)
        self._pollers.append(poller)
        return poller, db

    def _live(self, version=None, tokens=(100, 20, 5, 400, 7)):
        sessions = [make_session('ses_work', project='proj-w',
                                 directory='/synthetic/work',
                                 version=version, tokens=tokens, cost=0.05,
                                 updated=BASE_MS)]
        messages = [make_message('m1', 'ses_work')]
        parts = [make_part('p1', 'ses_work', created=BASE_MS - 100000)]
        return self._stores([{'id': 't1'}], sessions, messages, parts)

    def _sync_poll(self, poller, prefs=None, **kw):
        out = poller.poll(prefs, **kw)
        self.assertTrue(poller.drain(), 'provider reads did not finish')
        out = poller.poll(prefs, **kw)
        self.assertTrue(poller.drain(), 'provider reads did not finish')
        return poller.poll(prefs, **kw)

    def _assert_active(self, result, live=True):
        self.assertTrue(result['available'])
        self.assertEqual(result.get('presentation'), 'active_session')
        self.assertEqual(result['scope'], 'conversation')
        identity = result['scope_identity']
        self.assertEqual(identity['scope_type'], 'active_session')
        self.assertEqual(identity['requested_scope'], 'conversation')
        self.assertEqual(identity['session_id'], 'opencode:ses_work')
        self.assertEqual(result['session_id'], 'opencode:ses_work')
        self.assertEqual(result['model'], 'test-model')
        self.assertEqual(result['project'], 'work')
        tokens = result['tokens']
        self.assertEqual(
            (tokens['input'], tokens['output'], tokens['reasoning'],
             tokens['cache_read'], tokens['cache_write']),
            (100, 20, 5, 400, 7))
        self.assertIsNone(tokens['total'])
        self.assertEqual(result['cost']['amount'], 0.05)
        self.assertIsNone(result['cost']['currency'])
        working = result['working_context']
        self.assertIsNotNone(working)
        self.assertEqual(working['thread'], 'ses_work')
        self.assertEqual(working['tokens']['input'], 100)
        self.assertEqual(result['scope_status'], 'waiting_available_task')
        self.assertEqual(result['breakdown_sessions'], [])
        self.assertIsNone(result['history'])
        return result

    def test_manual_opencode_conversation_no_pin_shows_active(self):
        poller, _ = self._live()
        out = self._sync_poll(
            poller, {'scope': 'conversation',
                     'tracking_provider': 'opencode'}, now=NOW_S)
        self.assertEqual(out['selection']['selected'], 'opencode')
        self.assertTrue(out['selection']['live'])
        self._assert_active(out['result'])

    def test_auto_conversation_no_pin_shows_active(self):
        poller, _ = self._live()
        out = self._sync_poll(poller, {'scope': 'conversation'},
                              now=NOW_S)
        self.assertEqual(out['selection']['selected'], 'opencode')
        self.assertTrue(out['selection']['live'])
        self._assert_active(out['result'])

    def test_codex_pin_does_not_hide_live_opencode(self):
        poller, _ = self._live()
        out = self._sync_poll(
            poller, {'scope': 'conversation', 'pinned': 't1',
                     'tracking_provider': 'opencode'}, now=NOW_S)
        self.assertTrue(out['selection']['live'])
        shown = self._assert_active(out['result'])
        self.assertNotIn('t1', (shown['session_id'], shown['model']))

    def test_matching_opencode_pin_keeps_scoped_view(self):
        poller, _ = self._live()
        out = self._sync_poll(
            poller, {'scope': 'conversation', 'pinned': 'ses_work',
                     'tracking_provider': 'opencode'}, now=NOW_S)
        result = out['result']
        self.assertTrue(result['available'])
        self.assertIsNone(result.get('presentation'))
        self.assertEqual(result['scope_identity']['scope_type'],
                         'conversation')
        self.assertEqual(result['session_id'], 'opencode:ses_work')
        self.assertEqual(result['tokens']['input'], 100)

    def test_idle_conversation_no_pin_stays_waiting(self):
        poller, _ = self._stores(
            [{'id': 't1'}],
            [make_session('ses_idle', updated=BASE_MS)])
        out = self._sync_poll(
            poller, {'scope': 'conversation',
                     'tracking_provider': 'opencode'}, now=NOW_S)
        result = out['result']
        self.assertFalse(result['available'])
        self.assertEqual(result['status'], 'waiting_available_task')
        self.assertIsNone(result.get('presentation'))
        self.assertIsNone(result.get('working_context'))

    def test_deleted_session_row_stays_honest(self):
        import sqlite3
        from contextlib import closing
        poller, db = self._live()
        first = self._sync_poll(
            poller, {'scope': 'conversation',
                     'tracking_provider': 'opencode'}, now=NOW_S)
        self.assertTrue(first['result']['available'])
        with closing(sqlite3.connect(db)) as connection:
            connection.execute("DELETE FROM session WHERE id='ses_work'")
            connection.commit()
        out = self._sync_poll(
            poller, {'scope': 'conversation',
                     'tracking_provider': 'opencode'}, now=NOW_S)
        result = out['result']
        self.assertFalse(result['available'])
        self.assertIsNone(result.get('presentation'))
        self.assertIsNone(result.get('working_context'))

    def test_stale_activity_clears_live_after_committed_finish(self):
        import sqlite3
        from contextlib import closing
        poller, db = self._live()
        live = self._sync_poll(poller, {'scope': 'global'}, now=NOW_S)
        self.assertTrue(live['selection']['live'])
        self.assertEqual(
            live['result']['working_context']['thread'], 'ses_work')
        with closing(sqlite3.connect(db)) as connection:
            connection.execute(
                'UPDATE part SET time_created=?, time_updated=?, data=?'
                " WHERE id='p1'",
                (BASE_MS - 1000000, BASE_MS - 1000000,
                 '{"type": "step-finish", "reason": "stop"}'))
            connection.commit()
        out = self._sync_poll(poller, {'scope': 'global'}, now=NOW_S)
        # The same-rowid UPDATE invalidates the cached projection at
        # once: selection cannot retain stale Live.
        self.assertFalse(out['selection']['live'])
        self.assertIsNone(out['result'].get('working_context'))

    def test_delete_clears_live_without_stale_badge(self):
        import sqlite3
        from contextlib import closing
        poller, db = self._live()
        live = self._sync_poll(
            poller, {'scope': 'conversation',
                     'tracking_provider': 'opencode'}, now=NOW_S)
        self.assertTrue(live['selection']['live'])
        self.assertEqual(live['result'].get('presentation'),
                         'active_session')
        with closing(sqlite3.connect(db)) as connection:
            connection.execute("DELETE FROM part WHERE id='p1'")
            connection.commit()
        out = self._sync_poll(
            poller, {'scope': 'conversation',
                     'tracking_provider': 'opencode'}, now=NOW_S)
        self.assertFalse(out['selection']['live'])
        self.assertIsNone(out['result'].get('presentation'))
        self.assertIsNone(out['result'].get('working_context'))
        self.assertFalse(out['result']['available'])

    def test_replacement_clears_live_without_stale_badge(self):
        from tests.test_opencode_provider import write_store as _write
        poller, db = self._live()
        live = self._sync_poll(
            poller, {'scope': 'conversation',
                     'tracking_provider': 'opencode'}, now=NOW_S)
        self.assertTrue(live['selection']['live'])
        # Drain the settling reads, then release the detector handle:
        # on Windows an open handle blocks replacement at OS level, so
        # a successful replace implies the reader comes back fresh.
        self.assertTrue(poller.drain(timeout=10))
        poller.opencode.close()
        _write(db, [make_session('ses_work', updated=BASE_MS)], (),
               [make_part('p1', 'ses_work', created=BASE_MS - 1000000,
                          kind='step-finish', reason='stop')])
        out = self._sync_poll(
            poller, {'scope': 'conversation',
                     'tracking_provider': 'opencode'}, now=NOW_S)
        self.assertFalse(out['selection']['live'])
        self.assertIsNone(out['result'].get('presentation'))
        self.assertIsNone(out['result'].get('working_context'))

    def test_same_size_update_with_restored_mtime_clears_live(self):
        import json as _json
        import sqlite3
        from contextlib import closing
        poller, db = self._live()
        live = self._sync_poll(
            poller, {'scope': 'conversation',
                     'tracking_provider': 'opencode'}, now=NOW_S)
        self.assertTrue(live['selection']['live'])
        self.assertEqual(live['result'].get('presentation'),
                         'active_session')
        # Same-size committed UPDATE (default start JSON is 22 chars;
        # the compact finish JSON matches) + restored mtime: no stat
        # signal changes, yet Live must drop at once.
        finish_data = _json.dumps({'type': 'step-finish'},
                                  separators=(',', ':'))
        with closing(sqlite3.connect(db)) as probe:
            start_data = probe.execute(
                "SELECT data FROM part WHERE id='p1'").fetchone()[0]
        self.assertEqual(len(finish_data), len(start_data))
        before = os.stat(db)
        with closing(sqlite3.connect(db)) as connection:
            connection.execute(
                'UPDATE part SET time_created=?, time_updated=?, data=?'
                " WHERE id='p1'",
                (BASE_MS - 1000000, BASE_MS - 1000000, finish_data))
            connection.commit()
        os.utime(db, ns=(before.st_atime_ns, before.st_mtime_ns))
        after = os.stat(db)
        self.assertEqual(after.st_size, before.st_size)
        self.assertEqual(after.st_mtime_ns, before.st_mtime_ns)
        out = self._sync_poll(
            poller, {'scope': 'conversation',
                     'tracking_provider': 'opencode'}, now=NOW_S)
        self.assertFalse(out['selection']['live'])
        self.assertIsNone(out['result'].get('presentation'))
        self.assertIsNone(out['result'].get('working_context'))
        self.assertFalse(out['result']['available'])

    def test_retry_exhaustion_never_publishes_live(self):
        import json as _json
        import sqlite3
        from contextlib import closing
        from opencode_provider import OpenCodeProvider
        poller, db = self._live()
        live = self._sync_poll(
            poller, {'scope': 'conversation',
                     'tracking_provider': 'opencode'}, now=NOW_S)
        self.assertTrue(live['selection']['live'])
        start_data = _json.dumps({'type': 'step-start'})
        finish_data = _json.dumps({'type': 'step-finish',
                                   'reason': 'stop'})
        adapter = poller.opencode
        orig_current = adapter._dv_current
        calls = []

        def flipping(file_id):
            calls.append(1)
            if len(calls) in (2, 4, 6):
                with closing(sqlite3.connect(db)) as connection:
                    if len(calls) in (2, 6):
                        connection.execute(
                            'UPDATE part SET time_created=?,'
                            ' time_updated=?, data=? WHERE id=?',
                            (BASE_MS - 1000000, BASE_MS - 1000000,
                             finish_data, 'p1'))
                    else:
                        connection.execute(
                            'UPDATE part SET time_created=?,'
                            ' time_updated=?, data=? WHERE id=?',
                            (BASE_MS - 100000, BASE_MS - 100000,
                             start_data, 'p1'))
                    connection.commit()
            return orig_current(file_id)

        try:
            # Fresh probe state forces the rescan path with exactly six
            # generation reads; every attempt straddles a real commit
            # and the final store is idle while the last candidate
            # looks working. The flipper goes in only after the settle
            # drain so no trailing worker can consume its call budget.
            prefs = {'scope': 'conversation',
                     'tracking_provider': 'opencode'}
            self.assertTrue(poller.drain(timeout=10))
            adapter._activity_probe = None
            adapter._dv_current = flipping
            poller.poll(prefs, now=NOW_S)
            self.assertTrue(poller.drain(timeout=10),
                            'exhaustion read did not finish')
            # Exactly one snapshot ran: six generation reads, nothing
            # cached from the exhausted projection.
            self.assertEqual(len(calls), 6)
            self.assertIsNone(adapter._activity_probe)
            out = poller.poll(prefs, now=NOW_S)
        finally:
            del adapter._dv_current
        self.assertFalse(out['selection']['live'])
        self.assertIsNone(out['result'].get('working_context'))
        self.assertIsNone(out['result'].get('presentation'))
        self.assertFalse(out['result']['available'])
        # Recovery: a later stable poll serves the current idle store
        # and agrees with a fresh provider.
        settled = self._sync_poll(
            poller, {'scope': 'conversation',
                     'tracking_provider': 'opencode'}, now=NOW_S)
        self.assertFalse(settled['selection']['live'])
        self.assertIsNone(settled['result'].get('working_context'))
        check = OpenCodeProvider(db)
        try:
            fresh = check.activity_snapshot(now=NOW_S)
        finally:
            check.close()
        self.assertFalse(fresh['working'])

    def test_close_blocks_detector_reopen_after_shutdown(self):
        import sqlite3
        import threading
        import time
        from contextlib import closing
        poller, db = self._live()
        live = self._sync_poll(
            poller, {'scope': 'conversation',
                     'tracking_provider': 'opencode'}, now=NOW_S)
        self.assertTrue(live['selection']['live'])
        # Settle the trailing submit so the raced poll finds a free
        # slot; then a real commit forces it into the rescan path.
        self.assertTrue(poller.drain(timeout=10))
        with closing(sqlite3.connect(db)) as connection:
            connection.execute(
                "INSERT INTO part VALUES (?,?,?,?,?,?)",
                ('p_extra', 'msg_1', 'ses_work', BASE_MS - 90000,
                 BASE_MS - 90000, '{"type": "step-start"}'))
            connection.commit()
        entered, release, finished = (threading.Event(), threading.Event(),
                                      threading.Event())
        adapter = poller.opencode
        orig_current = adapter._dv_current
        calls = []

        def pausing(file_id):
            # Pause the in-flight read between its generation checks:
            # the second generation read runs only after release.
            calls.append(1)
            if len(calls) == 2:
                entered.set()
                try:
                    self.assertTrue(release.wait(timeout=30))
                    return orig_current(file_id)
                finally:
                    finished.set()
            return orig_current(file_id)

        adapter._dv_current = pausing
        try:
            outcome = {}
            thread = threading.Thread(
                target=lambda: outcome.setdefault(
                    'out', poller.poll(
                        {'scope': 'conversation',
                         'tracking_provider': 'opencode'}, now=NOW_S)),
                daemon=True)
            thread.start()
            self.assertTrue(entered.wait(timeout=10))
            thread.join(timeout=10)
            self.assertFalse(thread.is_alive())
            # Close must return promptly without joining the paused
            # worker, and must terminally shut the detector down.
            started = time.monotonic()
            poller.close()
            elapsed = time.monotonic() - started
            self.assertLess(elapsed, 10)
            self.assertIsNone(adapter._dv_conn)
            poller.close()
            self.assertIsNone(adapter._dv_conn)
            release.set()
            # No drain-before-close substitute: the poller is already
            # shut; the late worker outcome must stay unpublished and
            # must not reopen the detector. Wait for the worker itself
            # (finished fires on its way out) before asserting.
            self.assertTrue(finished.wait(timeout=10))
            self.assertTrue(poller.drain(timeout=10))
        finally:
            release.set()
            del adapter._dv_current
        self.assertGreaterEqual(len(calls), 2)
        self.assertIsNone(adapter._dv_conn)
        closed = poller.poll(
            {'scope': 'conversation',
             'tracking_provider': 'opencode'}, now=NOW_S)
        # No late publication: the closed poller serves only its honest
        # unavailable result with no working context. (The retained
        # selector memory still shows the last pre-shutdown snapshot;
        # only published results matter.)
        self.assertFalse(closed['result']['available'])
        self.assertIsNone(closed['result'].get('working_context'))
        self.assertIsNone(closed['result'].get('presentation'))

    def test_recorded_total_survives_provider_switches(self):
        poller, _ = self._live(version='1.18.31',
                               tokens=(1000, 200, 30, 4000, 70))
        manual = self._sync_poll(
            poller, {'scope': 'conversation',
                     'tracking_provider': 'opencode'}, now=NOW_S)
        self.assertEqual(manual['result']['tokens']['total'], 5300)
        self.assertEqual(
            manual['result']['working_context']['tokens']['total'], 5300)
        codex = self._sync_poll(poller, {'tracking_provider': 'codex'},
                                active_title='t1', detection_valid=True,
                                now=NOW_S)
        self.assertEqual(codex['provider_id'], 'codex')
        self.assertNotIn('test-model', codex['result'].get('model') or '')
        back = self._sync_poll(
            poller, {'scope': 'conversation',
                     'tracking_provider': 'opencode'}, now=NOW_S)
        self.assertEqual(back['result']['tokens']['total'], 5300)
        self.assertEqual(back['result']['session_id'],
                         'opencode:ses_work')


if __name__ == '__main__':
    unittest.main()
