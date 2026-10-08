"""Codex-only Slice 5 regression: whole-poll immutability + safe shutdown.

Deterministic Events/barriers/fake clocks only. No sleep-based primary
proof (join timeouts guard hangs, never prove correctness).
"""
import os as _os
import tempfile as _tempfile
# Hermetic Claude lane: a never-created home keeps real ~/.claude data out.
_os.environ.setdefault('PETOKEN_CLAUDE_HOME', _os.path.join(
    _tempfile.gettempdir(), 'petoken-tests-no-claude-home'))
import subprocess
import sys
import json
import sqlite3
import tempfile
import threading
import time
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from provider_poller import ProviderPoller
from providers import (PROVIDER_CODEX, CodexProvider)
from tests.test_providers import write_home
from usage import CodexStore

NOW_S = time.time()


def write_codex_home(home, threads):
    """Distinct synthetic task totals/projects expose cache relabeling."""
    write_home(str(home), threads)
    with closing(sqlite3.connect(Path(home) / 'state_1.sqlite')) as db:
        for index, spec in enumerate(threads):
            thread = spec['id']
            db.execute('UPDATE threads SET project_id=?, cwd=? WHERE id=?',
                       (f'proj-{index}', f'D:/synthetic/project-{index}', thread))
            path = Path(home) / f'{thread}.jsonl'
            rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
            for row in rows:
                info = (row.get('payload') or {}).get('info')
                if info:
                    for key in ('total_token_usage', 'last_token_usage'):
                        info[key] = {key: value * (index * 2 + 1)
                                     for key, value in info[key].items()}
            path.write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8')
        db.commit()


class FinalFixture:
    def __init__(self, root):
        self.root = Path(root)
        self.counter = 0

    def _fresh(self, name):
        self.counter += 1
        return self.root / f'{name}-{self.counter}'

    def codex(self, threads):
        home = self._fresh('codex')
        home.mkdir(parents=True, exist_ok=True)
        write_codex_home(home, threads)
        return CodexStore(home)



def _sync(poller, prefs=None, **kw):
    kw.setdefault('active_title', 't1')
    kw.setdefault('detection_valid', True)
    poller.poll(prefs, **kw)
    assert poller.drain(timeout=10), 'reads did not finish'
    poller.poll(prefs, **kw)
    assert poller.drain(timeout=10), 'reads did not finish'
    result = poller.poll(prefs, **kw)
    assert poller.drain(timeout=10), 'last read did not finish'
    poller._collect()
    return result


class WholePollRaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.fixture = FinalFixture(self.temp.name)
        self._pollers = []
        self._patches = []

    def tearDown(self):
        for target, name, orig in self._patches:
            setattr(target, name, orig)
        for poller in self._pollers:
            try:
                poller.drain(timeout=10)
            except Exception:
                pass
            poller.close()
        self.temp.cleanup()

    def _poller(self):
        store = self.fixture.codex(
            [{'id': 't1', 'working': True}, {'id': 't2'}])
        poller = ProviderPoller(store)
        self._pollers.append(poller)
        return poller

    def _block_collect(self, poller):
        entered = threading.Event()
        release = threading.Event()
        orig = poller._collect
        self._patches.append((poller, '_collect', orig))

        def blocking():
            entered.set()
            self.assertTrue(release.wait(timeout=30))
            return orig()

        poller._collect = blocking
        return entered, release

    def test_codex_global_to_project_whole_tick_race(self):
        poller = self._poller()
        _sync(poller, {'scope': 'global'}, active_title='t1',
              detection_valid=True, now=NOW_S)
        # Global provenance is cached for the sole Codex source.
        entered, release = self._block_collect(poller)
        outcome = {}
        thread = threading.Thread(
            target=lambda: outcome.setdefault(
                'out', poller.poll(
                    {'scope': 'global', 'tracking_provider': 'codex'},
                    active_title='t1', detection_valid=True, now=NOW_S)),
            daemon=True)
        thread.start()
        self.assertTrue(entered.wait(timeout=10))
        # Settings change mid-tick: must publish Codex/project honestly,
        # never Global (440) relabeled as Project (110).
        immediate = poller.apply_settings(
            {'scope': 'project', 'pinned': 't1',
             'tracking_provider': 'codex'},
            mark_provider='codex', now=NOW_S)
        self.assertEqual(immediate['selection']['selected'], 'codex')
        self.assertEqual(immediate['result']['provider_id'], 'codex')
        self.assertEqual(immediate['result']['scope'], 'project')
        # No project cache yet: honest pending, never Global-as-Project.
        self.assertFalse(immediate['result']['available'])
        release.set()
        thread.join(timeout=10)
        self.assertFalse(thread.is_alive())
        old = outcome['out']
        self.assertEqual(old['result']['provider_id'], 'codex')
        self.assertEqual(old['result']['scope'], 'global')
        self.assertLess(old['generation'], immediate['generation'])
        # Obsolete tick never submitted old values under the new epoch:
        # provenance for Codex is still the old global read.
        self.assertEqual(poller._provenance['codex']['scope'], 'global')
        # Settle the new scope (three rounds: the first may be blocked by
        # the retired previous-epoch slot, the second submits, the third
        # collects); only then does Project data appear.
        for _ in range(2):
            poller.poll({'scope': 'project', 'pinned': 't1',
                         'tracking_provider': 'codex'}, now=NOW_S)
            self.assertTrue(poller.drain(timeout=10))
        settled = poller.poll(
            {'scope': 'project', 'pinned': 't1',
             'tracking_provider': 'codex'}, now=NOW_S)
        self.assertEqual(settled['result']['scope'], 'project')
        self.assertTrue(settled['result']['available'])
        self.assertEqual(settled['result']['tokens']['total_tokens'], 110)
        self.assertEqual(settled['result']['thread'], 't1')

    def test_codex_project_to_global_whole_tick_race(self):
        poller = self._poller()
        _sync(poller, {'scope': 'project', 'pinned': 't1',
                       'tracking_provider': 'codex'}, now=NOW_S)
        entered, release = self._block_collect(poller)
        outcome = {}
        thread = threading.Thread(
            target=lambda: outcome.setdefault(
                'out', poller.poll(
                    {'scope': 'project', 'pinned': 't1',
                     'tracking_provider': 'codex'}, now=NOW_S)),
            daemon=True)
        thread.start()
        self.assertTrue(entered.wait(timeout=10))
        immediate = poller.apply_settings(
            {'scope': 'global', 'tracking_provider': 'codex'},
            mark_provider='codex', now=NOW_S)
        self.assertEqual(immediate['selection']['selected'], 'codex')
        self.assertEqual(immediate['result']['provider_id'], 'codex')
        self.assertEqual(immediate['result']['scope'], 'global')
        # Codex global was never cached under project-only seeding for
        # this tick shape: pending rather than Project-as-Global.
        # (If a global read was already cached from earlier seeding it
        # would be compatible; here the last provenance is project, so
        # the immediate must not reuse it as global.)
        self.assertEqual(poller._provenance['codex']['scope'], 'project')
        self.assertFalse(immediate['result']['available'])
        release.set()
        thread.join(timeout=10)
        self.assertFalse(thread.is_alive())
        old = outcome['out']
        self.assertEqual(old['result']['provider_id'], 'codex')
        self.assertLess(old['generation'], immediate['generation'])


class ScopeCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.fixture = FinalFixture(self.temp.name)
        self._pollers = []

    def tearDown(self):
        for poller in self._pollers:
            try:
                poller.drain(timeout=10)
            except Exception:
                pass
            poller.close()
        self.temp.cleanup()

    def _poller(self):
        store = self.fixture.codex([{'id': 't1'}, {'id': 't2'}])
        poller = ProviderPoller(store)
        self._pollers.append(poller)
        return poller

    def test_global_to_project_is_pending_not_mislabeled(self):
        poller = self._poller()
        _sync(poller, {'scope': 'global',
                       'tracking_provider': 'codex'}, now=NOW_S)
        out = poller.apply_settings(
            {'scope': 'project', 'pinned': 't1',
             'tracking_provider': 'codex'}, now=NOW_S)
        self.assertEqual(out['result']['scope'], 'project')
        self.assertFalse(out['result']['available'])
        # Global sum (440) must never appear as Project (110).
        self.assertIsNone(out['result'].get('tokens'))
        settled = _sync(poller, {'scope': 'project', 'pinned': 't1'}, now=NOW_S)
        self.assertEqual(settled['result']['tokens']['total_tokens'], 110)

    def test_project_to_conversation_is_pending(self):
        poller = self._poller()
        _sync(poller, {'scope': 'project', 'pinned': 't1',
                       'tracking_provider': 'codex'}, now=NOW_S)
        out = poller.apply_settings(
            {'scope': 'conversation', 'pinned': 't2',
             'tracking_provider': 'codex'}, now=NOW_S)
        self.assertEqual(out['result']['scope'], 'conversation')
        self.assertFalse(out['result']['available'])
        settled = _sync(poller, {'scope': 'conversation', 'pinned': 't2'}, now=NOW_S)
        self.assertEqual(settled['result']['thread'], 't2')
        self.assertEqual(settled['result']['tokens']['total_tokens'], 330)

    def test_pinned_a_to_pinned_b_is_pending(self):
        poller = self._poller()
        _sync(poller, {'scope': 'conversation', 'pinned': 't1',
                       'tracking_provider': 'codex'}, now=NOW_S)
        before = poller._provenance['codex']
        self.assertEqual(before['scope'], 'conversation')
        out = poller.apply_settings(
            {'scope': 'conversation', 'pinned': 't2',
             'tracking_provider': 'codex'}, now=NOW_S)
        self.assertEqual(out['result']['scope'], 'conversation')
        self.assertFalse(out['result']['available'])
        # Never label t1 data as t2.
        self.assertNotEqual(out['result'].get('thread'),
                            't1')
        settled = _sync(poller, {'scope': 'conversation', 'pinned': 't2'}, now=NOW_S)
        self.assertEqual(settled['result']['thread'], 't2')
        self.assertEqual(settled['result']['tokens']['total_tokens'], 330)


class LateOutcomeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.fixture = FinalFixture(self.temp.name)
        self._pollers = []
        self._originals = []

    def tearDown(self):
        for target, name, orig in self._originals:
            setattr(target, name, orig)
        for poller in self._pollers:
            try:
                poller.drain(timeout=10)
            except Exception:
                pass
            poller.close()
        self.temp.cleanup()

    def _poller(self):
        store = self.fixture.codex(
            [{'id': 't1', 'working': True}, {'id': 't2'}])
        poller = ProviderPoller(store)
        self._pollers.append(poller)
        return poller

    def _hold(self, target, fail=False):
        entered = threading.Event()
        release = threading.Event()
        orig = target.read
        self._originals.append((target, 'read', orig))

        def blocking(inner_self, *args, **kwargs):
            entered.set()
            self.assertTrue(release.wait(timeout=30))
            if fail:
                raise RuntimeError('released-boom')
            return orig(inner_self, *args, **kwargs)

        target.read = blocking
        return entered, release

    def _poll_thread(self, poller, prefs, **kw):
        outcome = {}
        thread = threading.Thread(
            target=lambda: outcome.setdefault(
                'out', poller.poll(prefs, **kw)), daemon=True)
        thread.start()
        return thread, outcome

    def test_late_success_after_settings_epoch_cannot_repaint(self):
        poller = self._poller()
        _sync(poller, {'scope': 'global'}, active_title='t1',
              detection_valid=True, now=NOW_S)
        entered, release = self._hold(CodexProvider)
        try:
            thread, _ = self._poll_thread(
                poller, {'scope': 'global'}, active_title='t1',
                detection_valid=True, now=NOW_S)
            self.assertTrue(entered.wait(timeout=10))
            thread.join(timeout=10)
            request = poller._inflight['codex'].request
            frozen = (request.epoch, request.generation, request.scope,
                      request.pinned, request.active_title, request.detection_valid,
                      request.want_history, request.now)
            accepted = poller._accepted_rid['codex']
            manual = poller.apply_settings(
                {'scope': 'conversation', 'pinned': 't1',
                 'tracking_provider': 'codex'}, now=NOW_S)
            self.assertEqual(manual['selection']['selected'], 'codex')
            self.assertEqual((request.epoch, request.generation, request.scope,
                              request.pinned, request.active_title,
                              request.detection_valid, request.want_history,
                              request.now), frozen)
            self.assertLess(request.epoch, poller._epoch)
            release.set()
            self.assertTrue(poller.drain(timeout=10))
            poller._collect()
            self.assertEqual(poller._accepted_rid['codex'], accepted)
            settled = poller.poll(
                {'scope': 'conversation', 'pinned': 't1',
                 'tracking_provider': 'codex'},
                now=NOW_S)
            self.assertEqual(settled['selection']['selected'], 'codex')
            self.assertEqual(settled['result']['scope'], 'conversation')
            self.assertFalse(thread.is_alive())
        finally:
            release.set()

    def test_late_error_after_settings_epoch_cannot_repaint(self):
        poller = self._poller()
        _sync(poller, {'scope': 'global'}, active_title='t1',
              detection_valid=True, now=NOW_S)
        entered, release = self._hold(CodexProvider, fail=True)
        try:
            thread, _ = self._poll_thread(
                poller, {'scope': 'global'}, active_title='t1',
                detection_valid=True, now=NOW_S)
            self.assertTrue(entered.wait(timeout=10))
            thread.join(timeout=10)
            accepted = poller._accepted_rid['codex']
            manual = poller.apply_settings(
                {'scope': 'project', 'pinned': 't1',
                 'tracking_provider': 'codex'}, now=NOW_S)
            gen = manual['generation']
            release.set()
            self.assertTrue(poller.drain(timeout=10))
            poller._collect()
            self.assertEqual(poller._accepted_rid['codex'], accepted)
            settled = poller.poll(
                {'scope': 'project', 'pinned': 't1',
                 'tracking_provider': 'codex'},
                now=NOW_S)
            self.assertEqual(settled['selection']['selected'], 'codex')
            self.assertGreaterEqual(settled['generation'], gen)
        finally:
            release.set()

    def test_late_success_after_scope_change_cannot_repaint(self):
        poller = self._poller()
        _sync(poller, {'scope': 'conversation', 'pinned': 't2'},
              active_title='t1', detection_valid=True)
        entered, release = self._hold(CodexProvider)
        try:
            thread, _ = self._poll_thread(
                poller, {'scope': 'conversation', 'pinned': 't2'},
                active_title='t1', detection_valid=True)
            self.assertTrue(entered.wait(timeout=10))
            thread.join(timeout=10)
            poller.apply_settings({'scope': 'project', 'pinned': ''},
                                  now=NOW_S)
            release.set()
            self.assertTrue(poller.drain(timeout=10))
            out = poller.poll({'scope': 'project', 'pinned': ''},
                              active_title='t1', detection_valid=True)
            self.assertEqual(out['result'].get('scope'), 'project')
            self.assertNotEqual(out['result'].get('thread'), 't2')
        finally:
            release.set()


class ResetRaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.fixture = FinalFixture(self.temp.name)
        # Never the user's real Claude Code history: it can be hundreds of MB,
        # and reading it made these timed polls miss their deadline.
        home = Path(self.temp.name) / 'home'
        home.mkdir()
        environ = patch.dict(_os.environ, USERPROFILE=str(home), HOME=str(home))
        environ.start()
        self.addCleanup(environ.stop)
        self._pollers = []
        self._originals = []

    def tearDown(self):
        for target, name, orig in self._originals:
            setattr(target, name, orig)
        for poller in self._pollers:
            try:
                poller.drain(timeout=10)
            except Exception:
                pass
            poller.close()
        self.temp.cleanup()

    def test_reset_codex_during_inflight_uses_old_adapter_and_retires(self):
        store = self.fixture.codex([{'id': 't1', 'working': True}])
        poller = ProviderPoller(store)
        self._pollers.append(poller)
        _sync(poller, {'scope': 'global'}, active_title='t1',
              detection_valid=True)
        old_adapter = poller.codex
        entered = threading.Event()
        release = threading.Event()
        calls_old = []
        calls_new = []
        orig_class = CodexProvider.read
        self._originals.append((CodexProvider, 'read', orig_class))

        def blocking_old(inner_self, *args, **kwargs):
            if inner_self is old_adapter:
                calls_old.append(1)
                entered.set()
                self.assertTrue(release.wait(timeout=30))
            return orig_class(inner_self, *args, **kwargs)

        CodexProvider.read = blocking_old
        outcome = {}
        thread = threading.Thread(
            target=lambda: outcome.setdefault(
                'out', poller.poll({'scope': 'global'}, active_title='t1',
                                   detection_valid=True)), daemon=True)
        thread.start()
        self.assertTrue(entered.wait(timeout=10))
        thread.join(timeout=10)
        epoch_before = poller._epoch
        poller.reset_codex()
        new_adapter = poller.codex
        self.assertIsNot(old_adapter, new_adapter)
        self.assertGreater(poller._epoch, epoch_before)

        def counting_new(inner_self, *args, **kwargs):
            if inner_self is new_adapter:
                calls_new.append(1)
            return orig_class(inner_self, *args, **kwargs)

        CodexProvider.read = counting_new
        release.set()
        self.assertTrue(poller.drain(timeout=10))
        # Old request ran on the old adapter and retired via the epoch
        # bump: exactly one old call, no new-adapter use for that tick.
        self.assertEqual(len(calls_old), 1)
        self.assertEqual(len(calls_new), 0)
        CodexProvider.read = orig_class
        self._originals.pop()
        out = poller.poll({'scope': 'global'}, active_title='t1',
                          detection_valid=True)
        self.assertTrue(poller.drain(timeout=10))
        out = poller.poll({'scope': 'global'}, active_title='t1',
                          detection_valid=True)
        self.assertEqual(out['result']['provider_id'], 'codex')


class CloseSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.fixture = FinalFixture(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_close_twice_safe_and_no_post_close_mutation(self):
        store = self.fixture.codex([{'id': 't1', 'working': True}])
        poller = ProviderPoller(store)
        try:
            _sync(poller, {'scope': 'global'}, active_title='t1',
                  detection_valid=True)
            gen = poller.generation
            status_before = {k: dict(v) for k, v in poller._status.items()}
            # Settle workers before closing (see
            # test_no_production_emission_without_generation): a close
            # with reads in flight would orphan file users past cleanup.
            self.assertTrue(poller.drain(timeout=10))
            poller.close()
            poller.close()  # idempotent
            after = poller.poll({'scope': 'global'})
            self.assertEqual(after['generation'], gen + 1)
            self.assertEqual(poller.generation, gen + 1)
            self.assertEqual(poller._status, status_before)
            self.assertTrue(poller.drain(timeout=5))
        finally:
            poller.close()


class ShutdownSubprocessTests(unittest.TestCase):
    def test_child_exits_with_provider_held_forever(self):
        with tempfile.TemporaryDirectory() as directory:
            child = Path(directory) / 'child_close.py'
            child.write_text(
                "import sys, tempfile, threading\n"
                "from pathlib import Path\n"
                f"sys.path.insert(0, {str(Path(__file__).resolve().parents[1])!r})\n"
                f"sys.path.insert(0, {str(Path(__file__).resolve().parent)!r})\n"
                "from provider_poller import ProviderPoller\n"
                "from test_providers import write_home\n"
                "from usage import CodexStore\n"
                "from providers import CodexProvider\n"
                "tmp = tempfile.TemporaryDirectory()\n"
                "home = Path(tmp.name) / 'codex'\n"
                "home.mkdir()\n"
                "write_home(str(home), [{'id': 't1'}])\n"
                "poller = ProviderPoller(CodexStore(home))\n"
                "entered = threading.Event()\n"
                "orig = CodexProvider.read\n"
                "def held(self, *a, **k):\n"
                "    entered.set()\n"
                "    threading.Event().wait()  # forever, never released\n"
                "    return orig(self, *a, **k)\n"
                "CodexProvider.read = held\n"
                "poller.poll({'scope': 'global'})\n"
                "assert entered.wait(timeout=10), 'worker never entered read'\n"
                "poller.close()\n"
                "sys.exit(0)\n",
                encoding='utf-8')
            proc = subprocess.Popen(
                [sys.executable, str(child)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                _, _ = proc.communicate(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
                _, _ = proc.communicate(timeout=10)
                self.fail('child did not exit with provider held forever')
            self.assertEqual(proc.returncode, 0)


class PollExceptionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.fixture = FinalFixture(self.temp.name)
        self._pollers = []

    def tearDown(self):
        for poller in self._pollers:
            try:
                poller.drain(timeout=10)
            except Exception:
                pass
            poller.close()
        self.temp.cleanup()

    def test_poll_exception_returns_tick_fallback_without_raise(self):
        store = self.fixture.codex([{'id': 't1', 'working': True}])
        poller = ProviderPoller(store)
        self._pollers.append(poller)
        _sync(poller, {'scope': 'global'}, active_title='t1',
              detection_valid=True)
        with patch.object(ProviderPoller, '_decide',
                          side_effect=RuntimeError('decide-boom')):
            out = poller.poll({'scope': 'global'}, active_title='t1',
                              detection_valid=True)
        # Never raises; the failure is fed through selection authority,
        # so Live is revoked coherently instead of surviving beside the
        # failure. Under Auto a shared orchestration failure fails the
        # whole tick (no lane claims a fresh validation it never
        # performed): honest unavailable with Live revoked.
        self.assertFalse(out['selection']['live'])
        self.assertIsNone(out['result'].get('working_context'))
        self.assertEqual(out['provider_id'], 'codex')
        self.assertFalse(out['result']['available'])
        self.assertIsNotNone(out['generation'])
        # A newer settings publish still wins; the fallback is older.
        newer = poller.apply_settings(
            {'scope': 'global', 'tracking_provider': 'codex'},
            mark_provider='codex')
        self.assertGreater(newer['generation'], out['generation'])

    def test_late_pinned_change_success_cannot_repaint(self):
        store = self.fixture.codex([{'id': 't1'}, {'id': 't2'}])
        poller = ProviderPoller(store)
        self._pollers.append(poller)
        _sync(poller, {'scope': 'conversation', 'pinned': 't1',
                       'tracking_provider': 'codex'}, now=NOW_S)
        entered = threading.Event()
        release = threading.Event()
        orig = CodexProvider.read
        try:
            def blocking(inner_self, *args, **kwargs):
                entered.set()
                assert release.wait(timeout=30)
                return orig(inner_self, *args, **kwargs)
            CodexProvider.read = blocking
            outcome = {}
            thread = threading.Thread(
                target=lambda: outcome.setdefault(
                    'out', poller.poll(
                        {'scope': 'conversation', 'pinned': 't1',
                         'tracking_provider': 'codex'}, now=NOW_S)),
                daemon=True)
            thread.start()
            self.assertTrue(entered.wait(timeout=10))
            thread.join(timeout=10)
            poller.apply_settings(
                {'scope': 'conversation', 'pinned': 't2',
                 'tracking_provider': 'codex'}, now=NOW_S)
            release.set()
            self.assertTrue(poller.drain(timeout=10))
            for _ in range(2):
                poller.poll({'scope': 'conversation', 'pinned': 't2',
                             'tracking_provider': 'codex'}, now=NOW_S)
                self.assertTrue(poller.drain(timeout=10))
            settled = poller.poll(
                {'scope': 'conversation', 'pinned': 't2',
                 'tracking_provider': 'codex'}, now=NOW_S)
            self.assertNotEqual(settled['result'].get('thread'),
                                't1')
            self.assertEqual(settled['result']['thread'], 't2')
            self.assertEqual(settled['result']['tokens']['total_tokens'], 330)
        finally:
            CodexProvider.read = orig
            release.set()


class QtBridgeRaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from unittest.mock import patch as _patch
        from widget import Panel
        from pet import DesktopPet
        self.temp = tempfile.TemporaryDirectory()
        self.pref_patch = _patch('widget.PREF_DIR', Path(self.temp.name))
        self.pref_patch.start()
        self.panel = Panel(live=False)
        self.panel.pet = DesktopPet(self.panel)
        self.panel.pet.activity_timer.stop()
        self.panel.active.title = 't1'
        self.panel.active.seen = time.time()
        self.work = Path(self.temp.name) / 'stores'
        self.work.mkdir()

    def tearDown(self):
        try:
            self.panel.provider_poller.drain(timeout=10)
        except Exception:
            pass
        self.panel.provider_poller.close()
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

    def _home(self, name, threads):
        home = self.work / name
        home.mkdir(exist_ok=True)
        write_codex_home(home, threads)
        return CodexStore(home)


    def _attach(self, threads):
        from provider_poller import ProviderPoller as Poller
        self.panel.provider_poller.drain(timeout=10)
        self.panel.provider_poller.close()
        home = self._home(f'codex-{len(list(self.work.iterdir()))}',
                          threads)
        self.panel.provider_poller = Poller(home)
        return self.panel.provider_poller

    def _poll_render(self, prefs=None, now=None, **kw):
        prefs = dict({'scope': 'global'}, **(prefs or {}))
        kw.setdefault('active_title', 't1')
        kw.setdefault('detection_valid', True)
        poller = self.panel.provider_poller
        poller.poll(prefs, now=now, **kw)
        self.assertTrue(poller.drain(), 'reads did not finish')
        poller.poll(prefs, now=now, **kw)
        self.assertTrue(poller.drain(), 'reads did not finish')
        out = poller.poll(prefs, now=now, **kw)
        self.panel.render(out['result'])
        self.app.processEvents()
        return out

    def test_whole_poll_race_rejected_through_qt_bridge(self):
        poller = self._attach([{'id': 't1', 'working': True}, {'id': 't2'}])
        self._poll_render(active_title='t1', detection_valid=True,
                          now=NOW_S)
        entered = threading.Event()
        release = threading.Event()
        orig = poller._collect
        try:
            def blocking():
                entered.set()
                self.assertTrue(release.wait(timeout=30))
                return orig()
            poller._collect = blocking
            outcome = {}
            thread = threading.Thread(
                target=lambda: outcome.setdefault(
                    'out', poller.poll(
                        {'scope': 'global',
                         'tracking_provider': 'codex'},
                        active_title='t1', detection_valid=True,
                        now=NOW_S)), daemon=True)
            thread.start()
            self.assertTrue(entered.wait(timeout=10))
            # Production settings path: persist, apply, synchronous emit.
            self.panel.prefs.update(
                scope='project', pinned='t1',
                tracking_provider='codex')
            immediate = poller.apply_settings(
                dict(self.panel.prefs), mark_provider='codex',
                now=NOW_S)
            # Actual Qt bridge/render path for the immediate emission.
            self.panel.bridge.data.emit(immediate['result'])
            self.app.processEvents()
            self.assertIn('Codex', self.panel.connection.text())
            self.assertEqual(immediate['result']['scope'], 'project')
            self.assertFalse(immediate['result']['available'])
            release.set()
            thread.join(timeout=10)
            self.assertFalse(thread.is_alive())
            old = outcome['out']
            self.assertLess(old['generation'],
                            immediate['generation'])
            # Late obsolete emission through the same bridge path.
            self.panel.bridge.data.emit(old['result'])
            self.app.processEvents()
            self.assertIn('Codex', self.panel.connection.text())
            self.assertEqual(
                self.panel._render_generation,
                immediate['generation'])
        finally:
            poller._collect = orig
            release.set()

    def test_settings_save_paths(self):
        from widget import Settings
        poller = self._attach([{'id': 't1', 'working': True}, {'id': 't2'}])
        self._poll_render(active_title='t1', detection_valid=True, now=NOW_S)
        gen0 = poller.generation
        settings = Settings(self.panel)
        self.assertEqual([settings.tracking.itemData(i) for i in range(settings.tracking.count())],
                         ['auto', 'codex', 'claude'])
        self.assertFalse(settings.tracking.isHidden())
        settings.tracking.setCurrentIndex(settings.tracking.findData('codex'))
        settings.scope.setCurrentIndex(settings.scope.findData('project'))
        settings.task.setCurrentIndex(max(0, settings.task.findData('t1')))
        settings.save()
        self.assertEqual(self.panel.prefs['tracking_provider'], 'codex')
        self.assertEqual(self.panel.prefs['scope'], 'project')
        self.assertIn('Codex', self.panel.connection.text())
        self.assertGreater(poller.generation, gen0)
        self.assertEqual(self.panel.snapshot.get('scope'), 'project')
        self.assertEqual(self.panel.total.text(), '—')
        gen1, prefs1 = poller.generation, dict(self.panel.prefs)
        settings = Settings(self.panel)
        settings.scope.setCurrentIndex(settings.scope.findData('global'))
        settings.reject()
        self.assertEqual(self.panel.prefs, prefs1)
        self.assertEqual(poller.generation, gen1)
        settings = Settings(self.panel)
        settings.reset_to_defaults()
        settings.reset_to_defaults()
        settings.save()
        self.assertEqual(self.panel.prefs['tracking_provider'], 'auto')
        self.assertEqual(self.panel.prefs['scope'], 'conversation')
        gen2, prefs2 = poller.generation, dict(self.panel.prefs)
        selection = dict(poller.selection.snapshot())
        settings = Settings(self.panel)
        settings.scope.setCurrentIndex(settings.scope.findData('global'))
        with patch('widget.write_preferences', side_effect=OSError('disk-full')):
            settings.save()
        self.assertEqual(self.panel.prefs, prefs2)
        self.assertEqual(poller.generation, gen2)
        self.assertEqual(poller.selection.snapshot(), selection)
        self.assertTrue(settings.error.text())


class LoopTickFallbackTests(unittest.TestCase):
    """Production fallback boundary at the poller level: every failure
    path returns an immutable generation/settings context, never a
    hard-coded untagged Codex payload."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.fixture = FinalFixture(self.temp.name)
        self._pollers = []
        self._originals = []

    def tearDown(self):
        for target, name, orig in self._originals:
            setattr(target, name, orig)
        for poller in self._pollers:
            try:
                poller.drain(timeout=10)
            except Exception:
                pass
            poller.close()
        self.temp.cleanup()

    def _poller(self, codex_working=True):
        threads = ([{'id': 't1', 'working': True}, {'id': 't2'}]
                   if codex_working else [{'id': 't1'}, {'id': 't2'}])
        store = self.fixture.codex(threads)
        poller = ProviderPoller(store)
        self._pollers.append(poller)
        return poller

    def _hold(self, target, fail=False):
        entered = threading.Event()
        release = threading.Event()
        orig = target.read
        self._originals.append((target, 'read', orig))

        def blocking(inner_self, *args, **kwargs):
            entered.set()
            self.assertTrue(release.wait(timeout=30))
            if fail:
                raise RuntimeError('released-boom')
            return orig(inner_self, *args, **kwargs)

        target.read = blocking
        return entered, release

    def test_held_codex_read_returns_prompt_tagged_snapshot(self):
        poller = self._poller()
        _sync(poller, {'scope': 'global',
                       'tracking_provider': 'opencode'}, now=NOW_S)
        entered, release = self._hold(CodexProvider)
        try:
            out = poller.loop_tick(
                {'scope': 'global', 'tracking_provider': 'opencode'},
                now=NOW_S)
            self.assertTrue(entered.wait(timeout=10))
            # loop_tick itself never blocks on the held provider.
            self.assertIsNotNone(out['result'].get('generation'))
            self.assertEqual(out['provider_id'], 'codex')
            self.assertEqual(out['selection']['selected'], 'codex')
        finally:
            release.set()
        self.assertTrue(poller.drain(timeout=10))
        settled = poller.loop_tick(
            {'scope': 'global', 'tracking_provider': 'codex'},
            now=NOW_S)
        self.assertEqual(settled['provider_id'], 'codex')
        self.assertEqual(poller.selection.last_use, {})

    def test_held_codex_read_preserves_verified_cache_until_stale(self):
        from provider_selection import FRESHNESS_S
        poller = self._poller()
        _sync(poller, {'scope': 'global'}, active_title='t1',
              detection_valid=True, now=NOW_S)
        entered, release = self._hold(CodexProvider)
        try:
            out = poller.loop_tick(
                {'scope': 'global', 'tracking_provider': 'codex'},
                active_title='t1', detection_valid=True, now=NOW_S)
            self.assertIsNotNone(out['result'].get('generation'))
            self.assertEqual(out['provider_id'], 'codex')
            self.assertTrue(entered.wait(timeout=10))
            self.assertTrue(out['selection']['live'])
            self.assertTrue(out['result']['available'])
            stale = poller.loop_tick({'scope': 'global'}, active_title='t1',
                                    detection_valid=True, now=NOW_S + FRESHNESS_S + 1)
            self.assertFalse(stale['selection']['live'])
            self.assertIsNone(stale['result'].get('working_context'))
            self.assertEqual(stale['active_tasks'], [])
        finally:
            release.set()
        self.assertTrue(poller.drain(timeout=10))

    def test_current_codex_failure_is_tagged_and_revokes_live(self):
        poller = self._poller()
        live = _sync(poller, {'scope': 'global'}, active_title='t1',
                     detection_valid=True, now=NOW_S)
        self.assertTrue(live['selection']['live'])
        with patch.object(CodexProvider, 'read',
                          side_effect=RuntimeError('boom')):
            out = poller.loop_tick(
                {'scope': 'global', 'tracking_provider': 'codex'},
                active_title='t1', detection_valid=True, now=NOW_S)
            self.assertTrue(poller.drain(timeout=10))
            out = poller.loop_tick(
                {'scope': 'global', 'tracking_provider': 'codex'},
                active_title='t1', detection_valid=True, now=NOW_S)
        self.assertIsNotNone(out['result'].get('generation'))
        self.assertEqual(out['result']['provider_id'], 'codex')
        self.assertEqual(out['result']['scope'], 'global')
        self.assertFalse(out['selection']['live'])
        self.assertIsNone(out['result'].get('working_context'))
        self.assertEqual(poller.selection.last_use, {})

    def test_current_codex_project_failure_is_tagged_and_honest(self):
        poller = self._poller()
        _sync(poller, {'scope': 'project', 'pinned': 't1',
                       'tracking_provider': 'codex'}, now=NOW_S)
        with patch.object(CodexProvider, 'read',
                          side_effect=RuntimeError('boom')):
            out = poller.loop_tick(
                {'scope': 'project', 'pinned': 't1',
                 'tracking_provider': 'codex'}, now=NOW_S)
            self.assertTrue(poller.drain(timeout=10))
            out = poller.loop_tick(
                {'scope': 'project', 'pinned': 't1',
                 'tracking_provider': 'codex'}, now=NOW_S)
        self.assertIsNotNone(out['result'].get('generation'))
        self.assertEqual(out['result']['provider_id'], 'codex')
        self.assertEqual(out['result']['scope'], 'project')
        self.assertFalse(out['result']['available'])
        self.assertNotIn('gpt-6-astra', repr(out['result']))
        self.assertEqual(poller.selection.last_use, {})

    def test_poll_raise_returns_preference_bound_failure(self):
        poller = self._poller()
        _sync(poller, {'scope': 'global',
                       'tracking_provider': 'codex'}, now=NOW_S)
        with patch.object(ProviderPoller, 'poll',
                          side_effect=RuntimeError('poll-boom')):
            out = poller.loop_tick(
                {'scope': 'project', 'pinned': 't1',
                 'tracking_provider': 'codex'}, now=NOW_S)
        # Bound to the requested scope/pin despite an outer poll failure.
        self.assertIsNotNone(out['result'].get('generation'))
        self.assertEqual(out['provider_id'], 'codex')
        self.assertEqual(out['result']['scope'], 'project')
        self.assertFalse(out['result']['available'])
        self.assertEqual(poller.selection.last_use, {})

    def test_failed_reset_retains_adapter_and_revokes_retired_choice(self):
        poller = self._poller()
        prefs = {'scope': 'global', 'tracking_provider': 'opencode'}
        live = _sync(poller, prefs, active_title='t1', detection_valid=True, now=NOW_S)
        self.assertTrue(live['selection']['live'])
        old_adapter, epoch, fence = poller.codex, poller._epoch, poller._codex_fence
        with patch('provider_poller.CodexStore', side_effect=OSError('store-gone')):
            out = poller.loop_tick(prefs, active_title='t1', detection_valid=True,
                                   now=NOW_S, reset_requested=True)
        self.assertEqual(out['provider_id'], 'codex')
        self.assertFalse(out['selection']['live'])
        self.assertFalse(out['result']['available'])
        self.assertEqual(out['active_tasks'], [])
        self.assertIs(poller.codex, old_adapter)
        self.assertEqual(poller._epoch, epoch)
        self.assertEqual(poller._codex_fence, fence + 1)
        self.assertEqual(poller.selection.last_use, {})
        newer = poller.apply_settings({'scope': 'project', 'pinned': 't2'}, now=NOW_S)
        self.assertGreater(newer['generation'], out['generation'])

    def test_reset_failure_codex_selected_is_honest_unavailable(self):
        poller = self._poller()
        live = _sync(poller, {'scope': 'global',
                              'tracking_provider': 'codex'},
                     active_title='t1', detection_valid=True, now=NOW_S)
        self.assertEqual(live['selection']['selected'], 'codex')
        self.assertTrue(live['selection']['live'])
        old_adapter = poller.codex
        with patch('provider_poller.CodexStore',
                   side_effect=OSError('store-gone')):
            out = poller.loop_tick(
                {'scope': 'global', 'tracking_provider': 'codex'},
                active_title='t1', detection_valid=True, now=NOW_S,
                reset_requested=True)
        # Codex-selected reset failure: tagged Codex unavailable with
        # Live revoked; failed source cannot expose cached task metrics.
        self.assertEqual(out['provider_id'], 'codex')
        self.assertFalse(out['result']['available'])
        self.assertFalse(out['selection']['live'])
        self.assertIsNone(out['result'].get('working_context'))
        self.assertNotIn('test-model', repr(out['result']))
        self.assertIsNotNone(out['result'].get('generation'))
        self.assertIs(poller.codex, old_adapter)
        self.assertEqual(poller.selection.last_use, {})

    def test_loop_tick_closed_returns_tagged_without_mutation(self):
        poller = self._poller()
        _sync(poller, {'scope': 'global'}, now=NOW_S)
        gen = poller.generation
        snapshot_before = poller.selection.snapshot()
        self.assertTrue(poller.drain(timeout=10))
        poller.close()
        out = poller.loop_tick({'scope': 'global'}, now=NOW_S)
        self.assertIsNotNone(out['result'].get('generation'))
        self.assertEqual(out['generation'], gen + 1)
        self.assertEqual(poller.generation, gen + 1)
        self.assertEqual(poller.selection.snapshot(), snapshot_before)

    def test_loop_tick_success_never_stamps_use(self):
        poller = self._poller()
        out = poller.loop_tick({'scope': 'global'}, now=NOW_S)
        self.assertIsNotNone(out['result'].get('generation'))
        self.assertEqual(poller.selection.last_use, {})


class CurrentFailureSemanticsTests(unittest.TestCase):
    """Current-tick failures must be internally coherent: tagged with
    the tick generation/context, Live revoked, no working context, no
    fresh-success appearance, no use-time stamp."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.fixture = FinalFixture(self.temp.name)
        self._pollers = []

    def tearDown(self):
        for poller in self._pollers:
            try:
                poller.drain(timeout=10)
            except Exception:
                pass
            poller.close()
        self.temp.cleanup()

    def _poller(self):
        store = self.fixture.codex(
            [{'id': 't1', 'working': True}, {'id': 't2'}])
        poller = ProviderPoller(store)
        self._pollers.append(poller)
        return poller

    def _assert_coherent_failure(self, out, provider, scope):
        self.assertIsNotNone(out['result'].get('generation'))
        self.assertEqual(out['provider_id'], provider)
        self.assertEqual(out['result']['scope'], scope)
        self.assertFalse(out['selection']['live'])
        self.assertFalse(out['result']['available'])
        self.assertIsNone(out['result'].get('working_context'))

    def test_internal_failure_project_context_revokes_live(self):
        poller = self._poller()
        prefs = {'scope': 'global', 'tracking_provider': 'codex'}
        live = _sync(poller, prefs, now=NOW_S)
        self.assertTrue(live['selection']['live'])
        with patch.object(ProviderPoller, '_decide',
                          side_effect=RuntimeError('decide-boom')):
            out = poller.poll(prefs, now=NOW_S)
        self._assert_coherent_failure(out, 'codex', 'global')
        self.assertEqual(poller.selection.last_use, {})
        newer = poller.apply_settings(
            dict(prefs), mark_provider='codex', now=NOW_S)
        self.assertGreater(newer['generation'], out['generation'])

    def test_internal_failure_manual_codex_revokes_live(self):
        poller = self._poller()
        prefs = {'scope': 'global', 'tracking_provider': 'codex'}
        live = _sync(poller, prefs, active_title='t1',
                     detection_valid=True, now=NOW_S)
        self.assertTrue(live['selection']['live'])
        with patch.object(ProviderPoller, '_decide',
                          side_effect=RuntimeError('decide-boom')):
            out = poller.poll(prefs, active_title='t1',
                              detection_valid=True, now=NOW_S)
        self._assert_coherent_failure(out, 'codex', 'global')
        self.assertNotIn('t2', repr(out['result']))
        self.assertEqual(poller.selection.last_use, {})

    def test_outer_raise_project_context_cannot_look_successful(self):
        poller = self._poller()
        prefs = {'scope': 'project', 'pinned': 't1',
                 'tracking_provider': 'codex'}
        live = _sync(poller, prefs, now=NOW_S)
        self.assertTrue(live['selection']['live'])
        with patch.object(ProviderPoller, 'poll',
                          side_effect=RuntimeError('poll-boom')):
            out = poller.loop_tick(dict(prefs), now=NOW_S)
        self._assert_coherent_failure(out, 'codex', 'project')
        self.assertEqual(poller.selection.last_use, {})

    def test_outer_raise_manual_codex_cannot_look_successful(self):
        poller = self._poller()
        prefs = {'scope': 'global', 'tracking_provider': 'codex'}
        live = _sync(poller, prefs, active_title='t1',
                     detection_valid=True, now=NOW_S)
        self.assertTrue(live['selection']['live'])
        with patch.object(ProviderPoller, 'poll',
                          side_effect=RuntimeError('poll-boom')):
            out = poller.loop_tick(dict(prefs), active_title='t1',
                                   detection_valid=True, now=NOW_S)
        self._assert_coherent_failure(out, 'codex', 'global')
        self.assertEqual(poller.selection.last_use, {})

    def test_first_run_manual_failures_stay_preference_bound(self):
        for tracking, provider in (('opencode', 'codex'),
                                   ('auto', 'codex'), ('codex', 'codex')):
            poller = self._poller()
            prefs = {'scope': 'global', 'tracking_provider': tracking}
            with patch.object(ProviderPoller, '_decide',
                              side_effect=RuntimeError('decide-boom')):
                out = poller.poll(prefs, active_title='t1',
                                  detection_valid=True, now=NOW_S)
            self._assert_coherent_failure(out, provider, 'global')
            self.assertEqual(poller.selection.last_use, {})

    def test_auto_unverified_failure_is_honest_unavailable(self):
        poller = self._poller()
        with patch.object(ProviderPoller, '_decide',
                          side_effect=RuntimeError('decide-boom')):
            out = poller.poll({'scope': 'global'}, now=NOW_S)
        self._assert_coherent_failure(out, 'codex', 'global')
        self.assertEqual(poller.selection.last_use, {})

    def test_reset_failure_orders_before_settings_change(self):
        poller = self._poller()
        prefs = {'scope': 'global', 'tracking_provider': 'codex'}
        _sync(poller, prefs, now=NOW_S)
        with patch('provider_poller.CodexStore',
                   side_effect=OSError('store-gone')):
            failed = poller.loop_tick(dict(prefs), now=NOW_S,
                                      reset_requested=True)
        self.assertIsNotNone(failed['result'].get('generation'))
        newer = poller.apply_settings(
            {'scope': 'project', 'pinned': 't1',
             'tracking_provider': 'codex'},
            mark_provider='codex', now=NOW_S)
        self.assertGreater(newer['generation'], failed['generation'])
        self.assertEqual(newer['result']['scope'], 'project')

    def test_repeated_reset_failures_stay_bounded(self):
        poller = self._poller()
        prefs = {'scope': 'global', 'tracking_provider': 'codex'}
        _sync(poller, prefs, now=NOW_S)
        with patch('provider_poller.CodexStore',
                   side_effect=OSError('store-gone')):
            generations = []
            for _ in range(5):
                out = poller.loop_tick(dict(prefs), now=NOW_S,
                                       reset_requested=True)
                self.assertIsNotNone(out['result'].get('generation'))
                generations.append(out['generation'])
                self.assertTrue(poller.drain(timeout=10))
        # One poll tick per iteration (failed resets add no generation of
        # their own); workers stay at exactly one bounded lane per provider.
        steps = [b - a for a, b in zip(generations, generations[1:])]
        self.assertTrue(all(step == 1 for step in steps), steps)
        self.assertEqual(set(poller._workers), {'codex', 'claude'})
        self.assertEqual(poller.selection.last_use, {})

    def test_close_during_reset_request_stays_tagged(self):
        poller = self._poller()
        prefs = {'scope': 'global', 'tracking_provider': 'codex'}
        _sync(poller, prefs, now=NOW_S)
        gen = poller.generation
        snapshot_before = poller.selection.snapshot()
        self.assertTrue(poller.drain(timeout=10))
        poller.close()
        out = poller.loop_tick(dict(prefs), now=NOW_S,
                               reset_requested=True)
        self.assertIsNotNone(out['result'].get('generation'))
        self.assertEqual(out['generation'], gen + 1)
        self.assertEqual(poller.generation, gen + 1)
        self.assertEqual(poller.selection.snapshot(), snapshot_before)

    def test_held_codex_success_is_fenced_by_failed_reset(self):
        poller = self._poller()
        prefs = {'scope': 'global', 'tracking_provider': 'codex'}
        _sync(poller, prefs, now=NOW_S)
        self.assertTrue(poller.drain(timeout=10))
        accepted = poller._accepted_rid['codex']
        epoch, fence, old_adapter = poller._epoch, poller._codex_fence, poller.codex
        entered, release = threading.Event(), threading.Event()
        original = CodexProvider.read
        def held(adapter, *args, **kwargs):
            entered.set()
            self.assertTrue(release.wait(timeout=30))
            return original(adapter, *args, **kwargs)
        try:
            CodexProvider.read = held
            poller.poll(prefs, active_title='t1', detection_valid=True, now=NOW_S)
            self.assertTrue(entered.wait(timeout=10))
            future = poller._inflight['codex']
            self.assertEqual(future.request.codex_fence, fence)
            with patch('provider_poller.CodexStore', side_effect=OSError('store-gone')):
                failed = poller.loop_tick(prefs, now=NOW_S, reset_requested=True)
            self.assertEqual(poller._epoch, epoch)
            self.assertIs(poller.codex, old_adapter)
            self.assertIs(poller._inflight['codex'], future)
            self.assertFalse(future.done())
            self.assertEqual(poller._codex_fence, fence + 1)
            self.assertFalse(failed['selection']['live'])
            self.assertEqual(failed['active_tasks'], [])
            release.set()
            self.assertTrue(poller.drain(timeout=10))
            poller._collect()
            self.assertEqual(poller._accepted_rid['codex'], accepted)
            self.assertEqual(poller._reads['codex']['reason'], 'status_read_failed')
            self.assertFalse(poller._status['codex']['source_available'])
            CodexProvider.read = original
            recovered = _sync(poller, prefs, now=NOW_S)
            self.assertGreater(poller._accepted_rid['codex'], future.request.rid)
            self.assertTrue(recovered['result']['available'])
            self.assertTrue(recovered['selection']['live'])
        finally:
            release.set()
            CodexProvider.read = original

    def test_repeated_reset_while_held_has_one_bounded_codex_lane(self):
        poller = self._poller()
        prefs = {'scope': 'global', 'tracking_provider': 'opencode'}
        _sync(poller, prefs, now=NOW_S)
        self.assertTrue(poller.drain(timeout=10))
        entered, release = threading.Event(), threading.Event()
        original = CodexProvider.read
        accepted = poller._accepted_rid['codex']
        def held(adapter, *args, **kwargs):
            entered.set()
            self.assertTrue(release.wait(timeout=30))
            return original(adapter, *args, **kwargs)
        try:
            CodexProvider.read = held
            poller.poll(prefs, now=NOW_S)
            self.assertTrue(entered.wait(timeout=10))
            future = poller._inflight['codex']
            old_fence = poller._codex_fence
            with patch('provider_poller.CodexStore', side_effect=OSError('store-gone')):
                for offset in range(1, 6):
                    out = poller.loop_tick(prefs, now=NOW_S, reset_requested=True)
                    self.assertEqual(poller._codex_fence, old_fence + offset)
                    self.assertIs(poller._inflight['codex'], future)
                    self.assertEqual(set(poller._workers), {'codex', 'claude'})
                    self.assertFalse(out['selection']['live'])
                    self.assertEqual(out['active_tasks'], [])
            release.set()
            self.assertTrue(poller.drain(timeout=10))
            poller._collect()
            self.assertEqual(poller._accepted_rid['codex'], accepted)
            self.assertEqual(poller._reads['codex']['reason'], 'status_read_failed')
        finally:
            release.set()
            CodexProvider.read = original


class QtFallbackBridgeTests(unittest.TestCase):
    """Production producer (Panel.read_loop_once) through the actual Qt
    bridge: no emission without an immutable generation, obsolete
    failures rejected, current failures honest."""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from unittest.mock import patch as _patch
        from widget import Panel
        from pet import DesktopPet
        self.temp = tempfile.TemporaryDirectory()
        self.pref_patch = _patch('widget.PREF_DIR', Path(self.temp.name))
        self.pref_patch.start()
        self.panel = Panel(live=False)
        self.panel.pet = DesktopPet(self.panel)
        self.panel.pet.activity_timer.stop()
        self.panel.active.title = 't1'
        self.panel.active.seen = time.time()
        self.work = Path(self.temp.name) / 'stores'
        self.work.mkdir()

    def tearDown(self):
        try:
            self.panel.provider_poller.drain(timeout=10)
        except Exception:
            pass
        self.panel.provider_poller.close()
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

    def _home(self, name, threads):
        home = self.work / name
        home.mkdir(exist_ok=True)
        write_codex_home(home, threads)
        return CodexStore(home)


    def _attach(self, threads):
        from provider_poller import ProviderPoller as Poller
        self.panel.provider_poller.drain(timeout=10)
        self.panel.provider_poller.close()
        home = self._home(f'codex-{len(list(self.work.iterdir()))}',
                          threads)
        self.panel.provider_poller = Poller(home)
        return self.panel.provider_poller

    def _poll_render(self, prefs=None, now=None, **kw):
        prefs = dict({'scope': 'global'}, **(prefs or {}))
        kw.setdefault('active_title', 't1')
        kw.setdefault('detection_valid', True)
        poller = self.panel.provider_poller
        poller.poll(prefs, now=now, **kw)
        self.assertTrue(poller.drain(), 'reads did not finish')
        poller.poll(prefs, now=now, **kw)
        self.assertTrue(poller.drain(), 'reads did not finish')
        out = poller.poll(prefs, now=now, **kw)
        self.panel.render(out['result'])
        self.app.processEvents()
        return out

    def _hold_read(self, target, fail=False):
        entered, release = threading.Event(), threading.Event()
        orig = target.read

        def blocking(inner_self, *args, **kwargs):
            entered.set()
            self.assertTrue(release.wait(timeout=30))
            if fail:
                raise RuntimeError('released-boom')
            return orig(inner_self, *args, **kwargs)

        target.read = blocking
        self.addCleanup(setattr, target, 'read', orig)
        return entered, release

    def _seed_codex(self):
        return self._attach([{'id': 't1', 'working': True}, {'id': 't2'}])

    def test_obsolete_global_failure_cannot_overwrite_project(self):
        poller = self._seed_codex()
        self.panel.prefs.update(
            scope='project', pinned='t1',
            tracking_provider='codex')
        for _ in range(2):
            poller.poll(dict(self.panel.prefs), now=NOW_S)
            self.assertTrue(poller.drain())
        current = poller.poll(dict(self.panel.prefs), now=NOW_S)
        self.panel.render(current['result'])
        self.app.processEvents()
        self.assertIn('Codex', self.panel.connection.text())
        self.assertTrue(poller.drain(timeout=10))
        current_gen = current['generation']
        # Old Codex/global iteration started before the settings change:
        # hold its provider read, then fail it on release.
        self.panel.prefs.update(scope='global', pinned='',
                                tracking_provider='codex')
        entered, release = self._hold_read(CodexProvider, fail=True)
        outcome = {}
        thread = threading.Thread(
            target=lambda: outcome.setdefault(
                'out', self.panel.read_loop_once()), daemon=True)
        thread.start()
        try:
            self.assertTrue(entered.wait(timeout=10))
            thread.join(timeout=10)
            self.assertFalse(thread.is_alive())
            # Newer Codex/Project wins while the old tick is held.
            self.panel.prefs.update(
                scope='project', pinned='t1',
                tracking_provider='codex')
            newer = poller.apply_settings(
                dict(self.panel.prefs), mark_provider='codex',
                now=NOW_S)
            self.panel.bridge.data.emit(newer['result'])
            self.app.processEvents()
            self.assertIn('Codex', self.panel.connection.text())
            self.assertGreaterEqual(newer['generation'], current_gen)
            release.set()
            thread.join(timeout=10)
            self.assertFalse(thread.is_alive())
            old = outcome['out']
            self.assertIsNotNone(old['result'].get('generation'))
            self.assertLess(old['generation'], newer['generation'])
            self.panel.bridge.data.emit(old['result'])
            self.app.processEvents()
            self.assertIn('Codex', self.panel.connection.text())
            self.assertEqual(self.panel._render_generation,
                             newer['generation'])
        finally:
            release.set()

    def test_obsolete_project_failure_cannot_overwrite_conversation(self):
        # A held project tick cannot overwrite a newer conversation tick.
        poller = self._attach([{'id': 't1', 'working': True}, {'id': 't2'}])
        self._poll_render(active_title='t1', detection_valid=True,
                          now=NOW_S)
        self.assertIn('Codex', self.panel.connection.text())
        self.assertTrue(poller.drain(timeout=10))
        self.panel.prefs.update(
            scope='project', pinned='t1',
            tracking_provider='codex')
        entered, release = self._hold_read(CodexProvider, fail=True)
        outcome = {}
        thread = threading.Thread(
            target=lambda: outcome.setdefault(
                'out', self.panel.read_loop_once()), daemon=True)
        thread.start()
        try:
            self.assertTrue(entered.wait(timeout=10))
            thread.join(timeout=10)
            self.assertFalse(thread.is_alive())
            # Newer Codex wins while the old Codex tick is held: the
            # settings path publishes synchronously, no drain needed.
            self.panel.prefs.update(
                scope='conversation', pinned='',
                tracking_provider='codex')
            newer = poller.apply_settings(
                dict(self.panel.prefs), mark_provider='codex', now=NOW_S)
            self.panel.bridge.data.emit(newer['result'])
            self.app.processEvents()
            self.assertIn('Codex', self.panel.connection.text())
            release.set()
            thread.join(timeout=10)
            self.assertFalse(thread.is_alive())
            old = outcome['out']
            self.assertIsNotNone(old['result'].get('generation'))
            self.assertLess(old['generation'], newer['generation'])
            self.panel.bridge.data.emit(old['result'])
            self.app.processEvents()
            self.assertIn('Codex', self.panel.connection.text())
            self.assertEqual(self.panel._render_generation,
                             newer['generation'])
        finally:
            release.set()

    def test_current_codex_failure_renders_honest_project(self):
        self._seed_codex()
        self.panel.prefs.update(
            scope='project', pinned='t1',
            tracking_provider='codex')
        with patch.object(CodexProvider, 'read',
                          side_effect=RuntimeError('boom')):
            snap = self.panel.read_loop_once()
            self.assertTrue(
                self.panel.provider_poller.drain(timeout=10))
            snap = self.panel.read_loop_once()
        self.assertIsNotNone(snap['result'].get('generation'))
        self.panel.bridge.data.emit(snap['result'])
        self.app.processEvents()
        self.assertIn('Codex', self.panel.connection.text())
        self.assertEqual(snap['result']['scope'], 'project')
        self.assertFalse(snap['selection']['live'])
        self.assertNotIn('gpt-6-astra', self.panel.model.text())
        self.assertNotIn('gpt-6-astra', self.panel.title.toolTip())

    def test_initial_codex_project_failure_stays_tagged(self):
        self._seed_codex()
        self.panel.prefs.update(
            scope='project', pinned='t1',
            tracking_provider='codex')
        self.assertIsNone(self.panel._render_generation)
        with patch.object(CodexProvider, 'read',
                          side_effect=RuntimeError('boom')):
            snap = self.panel.read_loop_once()
            self.assertTrue(
                self.panel.provider_poller.drain(timeout=10))
            snap = self.panel.read_loop_once()
        self.assertIsNotNone(snap['result'].get('generation'))
        self.assertEqual(snap['provider_id'], 'codex')
        self.panel.bridge.data.emit(snap['result'])
        self.app.processEvents()
        self.assertIn('Codex', self.panel.connection.text())
        self.assertIsNotNone(self.panel._render_generation)

    def test_old_global_failure_rejected_after_project_change(self):
        self._seed_codex()
        self.panel.prefs.update(scope='global',
                                tracking_provider='codex')
        with patch.object(CodexProvider, 'read',
                          side_effect=RuntimeError('boom')):
            old_fail = self.panel.read_loop_once()
            self.assertTrue(
                self.panel.provider_poller.drain(timeout=10))
            old_fail = self.panel.read_loop_once()
        self.assertIsNotNone(old_fail['result'].get('generation'))
        self.assertEqual(old_fail['result']['scope'], 'global')
        self.assertFalse(old_fail['result']['available'])
        self.panel.prefs.update(
            scope='project', pinned='t1',
            tracking_provider='codex')
        newer = self.panel.provider_poller.apply_settings(
            dict(self.panel.prefs), mark_provider='codex', now=NOW_S)
        self.panel.bridge.data.emit(newer['result'])
        self.app.processEvents()
        self.assertGreater(newer['generation'], old_fail['generation'])
        self.panel.bridge.data.emit(old_fail['result'])
        self.app.processEvents()
        self.assertEqual(self.panel._render_generation,
                         newer['generation'])
        self.assertIn('Codex', self.panel.connection.text())

    def test_old_pinned_failure_rejected_after_pinned_change(self):
        self._seed_codex()
        self.panel.prefs.update(
            scope='conversation', pinned='t1',
            tracking_provider='codex')
        with patch.object(CodexProvider, 'read',
                          side_effect=RuntimeError('boom')):
            old_fail = self.panel.read_loop_once()
            self.assertTrue(
                self.panel.provider_poller.drain(timeout=10))
            old_fail = self.panel.read_loop_once()
        self.assertIsNotNone(old_fail['result'].get('generation'))
        self.assertFalse(old_fail['result']['available'])
        self.panel.prefs.update(
            scope='conversation', pinned='t2',
            tracking_provider='codex')
        newer = self.panel.provider_poller.apply_settings(
            dict(self.panel.prefs), now=NOW_S)
        self.panel.bridge.data.emit(newer['result'])
        self.app.processEvents()
        self.assertGreater(newer['generation'], old_fail['generation'])
        self.assertNotEqual(
            newer['result'].get('thread'), 't1')
        self.panel.bridge.data.emit(old_fail['result'])
        self.app.processEvents()
        self.assertEqual(self.panel._render_generation,
                         newer['generation'])

    def test_no_production_emission_without_generation(self):
        import inspect
        from widget import Panel as _Panel
        poller = self._seed_codex()
        self.panel.prefs.update(
            scope='project', pinned='t1',
            tracking_provider='codex')
        snapshots = [self.panel.read_loop_once()]
        with patch.object(ProviderPoller, 'poll',
                          side_effect=RuntimeError('poll-boom')):
            snapshots.append(self.panel.read_loop_once())
        with patch('provider_poller.CodexStore',
                   side_effect=OSError('store-gone')):
            self.panel.reset_store.set()
            snapshots.append(self.panel.read_loop_once())
            self.panel.reset_store.clear()
        # Settle workers BEFORE closing: close() cancels pending reads
        # and a later drain() on a closed poller is a no-op, so an
        # unsettled close would leave file users racing temp cleanup
        # (deterministic WinError 32 on Windows).
        self.assertTrue(
            self.panel.provider_poller.drain(timeout=10))
        self.panel.provider_poller.close()
        snapshots.append(self.panel.read_loop_once())
        for snap in snapshots:
            self.assertIsNotNone(snap['result'].get('generation'))
        tail = inspect.getsource(_Panel.read_loop).split('except')[-1]
        self.assertNotIn('.emit(', tail)

    def test_closing_during_failure_stays_tagged(self):
        self._seed_codex()
        poller = self.panel.provider_poller
        gen = poller.generation
        poller.close()
        snap = self.panel.read_loop_once()
        self.assertIsNotNone(snap['result'].get('generation'))
        self.assertEqual(snap['generation'], gen + 1)
        self.assertEqual(poller.generation, gen + 1)

    def test_current_decide_failure_renders_coherent_codex(self):
        poller = self._seed_codex()
        self.panel.prefs.update(
            scope='project', pinned='t1',
            tracking_provider='codex')
        for _ in range(2):
            poller.poll(dict(self.panel.prefs), active_title='t1',
                        detection_valid=True, now=NOW_S)
            self.assertTrue(poller.drain(timeout=10))
        live = poller.poll(dict(self.panel.prefs), active_title='t1',
                           detection_valid=True, now=NOW_S)
        self.panel.render(live['result'])
        self.app.processEvents()
        self.assertTrue(live['selection']['live'])
        self.assertIn('Codex', self.panel.connection.text())
        with patch.object(ProviderPoller, '_decide',
                          side_effect=RuntimeError('decide-boom')):
            snap = self.panel.read_loop_once()
        self.assertIsNotNone(snap['result'].get('generation'))
        self.assertFalse(snap['selection']['live'])
        self.assertIsNone(snap['result'].get('working_context'))
        self.panel.bridge.data.emit(snap['result'])
        self.app.processEvents()
        # Coherent: Codex unavailable, no false Working bubble or
        # context, mode hysteresis untouched (no token arming).
        self.assertIn('Codex', self.panel.connection.text())
        self.assertIsNone(self.panel.pet.working_context)
        self.assertFalse(self.panel.pet.token_bubble_visible())
        self.assertFalse(snap['result']['available'])

    def test_retired_choice_reset_failure_revokes_live_through_bridge(self):
        poller = self._seed_codex()
        self.panel.prefs.update(scope='project', pinned='t1', tracking_provider='opencode')
        live = self._poll_render(dict(self.panel.prefs), active_title='t1',
                                 detection_valid=True, now=NOW_S)
        self.assertTrue(live['selection']['live'])
        old_adapter = poller.codex
        with patch('provider_poller.CodexStore', side_effect=OSError('store-gone')):
            self.panel.reset_store.set()
            snap = self.panel.read_loop_once()
        self.assertEqual(snap['provider_id'], 'codex')
        self.assertFalse(snap['selection']['live'])
        self.assertFalse(snap['result']['available'])
        self.assertEqual(snap['active_tasks'], [])
        self.assertIs(poller.codex, old_adapter)
        self.panel.bridge.data.emit(snap['result'])
        self.app.processEvents()
        self.assertIn('Codex', self.panel.connection.text())
        self.assertIsNone(self.panel.pet.working_context)
        self.assertFalse(self.panel.pet.token_bubble_visible())

    def test_reset_failure_codex_selected_renders_unavailable(self):
        from unittest.mock import patch as _patch
        poller = self._attach([{'id': 't1', 'working': True}, {'id': 't2'}])
        self._poll_render(active_title='t1', detection_valid=True,
                          now=NOW_S)
        self.panel.prefs.update(tracking_provider='codex')
        live = self._poll_render({'tracking_provider': 'codex'},
                                 active_title='t1', detection_valid=True,
                                 now=NOW_S)
        self.assertTrue(live['selection']['live'])
        old_adapter = poller.codex
        with _patch('provider_poller.CodexStore',
                    side_effect=OSError('store-gone')):
            self.panel.reset_store.set()
            snap = self.panel.read_loop_once()
            self.panel.reset_store.clear()
        self.assertEqual(snap['provider_id'], 'codex')
        self.assertFalse(snap['selection']['live'])
        self.assertFalse(snap['result']['available'])
        self.assertIsNone(snap['result'].get('working_context'))
        self.assertIs(poller.codex, old_adapter)
        self.panel.bridge.data.emit(snap['result'])
        self.app.processEvents()
        self.assertIn('Codex', self.panel.connection.text())
        self.assertIsNone(self.panel.pet.working_context)


if __name__ == '__main__':
    unittest.main()
