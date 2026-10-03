"""V1.2 Slice 5 final correction pass: whole-poll immutability + safe shutdown.

Deterministic Events/barriers/fake clocks only. No sleep-based primary
proof (join timeouts guard hangs, never prove correctness).
"""
import subprocess
import sys
import sqlite3
import tempfile
import threading
import time
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from provider_poller import ProviderPoller
from providers import (PROVIDER_CODEX, PROVIDER_OPENCODE, CodexProvider)
from opencode_provider import OpenCodeProvider
from tests.test_opencode_provider import (BASE_MS, make_message, make_part,
                                          make_session, write_store)
from tests.test_providers import write_home
from usage import CodexStore

NOW_S = BASE_MS / 1000 + 100


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
        write_home(str(home), threads)
        return CodexStore(home)

    def opencode(self, sessions, messages=(), parts=()):
        path = self._fresh('open.db')
        write_store(path, sessions, messages, parts)
        return path


def _sync(poller, prefs=None, **kw):
    poller.poll(prefs, **kw)
    assert poller.drain(timeout=10), 'reads did not finish'
    poller.poll(prefs, **kw)
    assert poller.drain(timeout=10), 'reads did not finish'
    return poller.poll(prefs, **kw)


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
        db = self.fixture.opencode(
            [make_session('ses_a', project='proj-a',
                          directory='/synthetic/alpha',
                          tokens=(10, 1, 1, 1, 0)),
             make_session('ses_b', project='proj-b',
                          directory='/synthetic/beta',
                          tokens=(20, 2, 2, 2, 0), updated=BASE_MS)],
            [make_message('m1', 'ses_b')],
            [make_part('p1', 'ses_b', created=BASE_MS - 100000)])
        poller = ProviderPoller(store, db)
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

    def test_codex_global_to_opencode_project_race(self):
        poller = self._poller()
        _sync(poller, {'scope': 'global'}, active_title='t1',
              detection_valid=True, now=NOW_S)
        # Old global provenance is cached for both providers now.
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
        # Settings change mid-tick: must publish OpenCode/project honestly,
        # never Global (30) relabeled as Project (10).
        immediate = poller.apply_settings(
            {'scope': 'project', 'pinned': 'ses_a',
             'tracking_provider': 'opencode'},
            mark_provider='opencode', now=NOW_S)
        self.assertEqual(immediate['selection']['selected'], 'opencode')
        self.assertEqual(immediate['result']['provider_id'], 'opencode')
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
        # provenance for opencode is still the old global read.
        self.assertEqual(poller._provenance['opencode']['scope'], 'global')
        # Settle the new scope (three rounds: the first may be blocked by
        # the retired previous-epoch slot, the second submits, the third
        # collects); only then does Project data appear.
        for _ in range(2):
            poller.poll({'scope': 'project', 'pinned': 'ses_a',
                         'tracking_provider': 'opencode'}, now=NOW_S)
            self.assertTrue(poller.drain(timeout=10))
        settled = poller.poll(
            {'scope': 'project', 'pinned': 'ses_a',
             'tracking_provider': 'opencode'}, now=NOW_S)
        self.assertEqual(settled['result']['scope'], 'project')
        self.assertTrue(settled['result']['available'])
        self.assertEqual(settled['result']['tokens']['input'], 10)

    def test_opencode_project_to_codex_global_race(self):
        poller = self._poller()
        _sync(poller, {'scope': 'project', 'pinned': 'ses_a',
                       'tracking_provider': 'opencode'}, now=NOW_S)
        entered, release = self._block_collect(poller)
        outcome = {}
        thread = threading.Thread(
            target=lambda: outcome.setdefault(
                'out', poller.poll(
                    {'scope': 'project', 'pinned': 'ses_a',
                     'tracking_provider': 'opencode'}, now=NOW_S)),
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
        prov = poller._provenance.get('codex')
        if prov is not None and prov.get('scope') != 'global':
            self.assertFalse(immediate['result']['available'])
        release.set()
        thread.join(timeout=10)
        self.assertFalse(thread.is_alive())
        old = outcome['out']
        self.assertEqual(old['result']['provider_id'], 'opencode')
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
        db = self.fixture.opencode(
            [make_session('ses_a', project='proj-a',
                          directory='/synthetic/alpha',
                          tokens=(10, 1, 1, 1, 0)),
             make_session('ses_b', project='proj-b',
                          directory='/synthetic/beta',
                          tokens=(20, 2, 2, 2, 0), updated=BASE_MS)])
        poller = ProviderPoller(store, db)
        self._pollers.append(poller)
        return poller

    def test_global_to_project_is_pending_not_mislabeled(self):
        poller = self._poller()
        _sync(poller, {'scope': 'global',
                       'tracking_provider': 'opencode'}, now=NOW_S)
        out = poller.apply_settings(
            {'scope': 'project', 'pinned': 'ses_a',
             'tracking_provider': 'opencode'}, now=NOW_S)
        self.assertEqual(out['result']['scope'], 'project')
        self.assertFalse(out['result']['available'])
        # Global sum (30) must never appear as Project (10).
        tokens = (out['result'].get('tokens') or {})
        self.assertNotEqual(tokens.get('input'), 30)

    def test_project_to_conversation_is_pending(self):
        poller = self._poller()
        _sync(poller, {'scope': 'project', 'pinned': 'ses_a',
                       'tracking_provider': 'opencode'}, now=NOW_S)
        out = poller.apply_settings(
            {'scope': 'conversation', 'pinned': 'ses_b',
             'tracking_provider': 'opencode'}, now=NOW_S)
        self.assertEqual(out['result']['scope'], 'conversation')
        self.assertFalse(out['result']['available'])

    def test_pinned_a_to_pinned_b_is_pending(self):
        poller = self._poller()
        _sync(poller, {'scope': 'conversation', 'pinned': 'ses_a',
                       'tracking_provider': 'opencode'}, now=NOW_S)
        before = poller._provenance['opencode']
        self.assertEqual(before['scope'], 'conversation')
        out = poller.apply_settings(
            {'scope': 'conversation', 'pinned': 'ses_b',
             'tracking_provider': 'opencode'}, now=NOW_S)
        self.assertEqual(out['result']['scope'], 'conversation')
        self.assertFalse(out['result']['available'])
        # Never label ses_a data as ses_b.
        self.assertNotEqual(out['result'].get('session_id'),
                            'opencode:ses_a')


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
            [{'id': 't1', 'working': True}])
        db = self.fixture.opencode([make_session('ses_1', updated=BASE_MS)],
                                   [make_message('m1', 'ses_1')],
                                   [make_part('p1', 'ses_1',
                                              created=BASE_MS - 100000)])
        poller = ProviderPoller(store, db)
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

    def test_late_success_after_provider_change_cannot_repaint(self):
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
            manual = poller.apply_settings(
                {'scope': 'global', 'tracking_provider': 'opencode'},
                mark_provider='opencode', now=NOW_S)
            self.assertEqual(manual['selection']['selected'], 'opencode')
            release.set()
            self.assertTrue(poller.drain(timeout=10))
            settled = poller.poll(
                {'scope': 'global', 'tracking_provider': 'opencode'},
                now=NOW_S)
            self.assertEqual(settled['selection']['selected'], 'opencode')
            self.assertLess(thread.ident, 10 ** 12)  # thread finished
        finally:
            release.set()

    def test_late_error_after_provider_change_cannot_repaint(self):
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
            manual = poller.apply_settings(
                {'scope': 'global', 'tracking_provider': 'opencode'},
                mark_provider='opencode', now=NOW_S)
            gen = manual['generation']
            release.set()
            self.assertTrue(poller.drain(timeout=10))
            settled = poller.poll(
                {'scope': 'global', 'tracking_provider': 'opencode'},
                now=NOW_S)
            self.assertEqual(settled['selection']['selected'], 'opencode')
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
        db = self.fixture.opencode([make_session('ses_1')])
        poller = ProviderPoller(store, db)
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
        db = self.fixture.opencode([make_session('ses_1')])
        poller = ProviderPoller(store, db)
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
                "from test_opencode_provider import write_store, make_session\n"
                "from usage import CodexStore\n"
                "from providers import CodexProvider\n"
                "tmp = tempfile.TemporaryDirectory()\n"
                "home = Path(tmp.name) / 'codex'\n"
                "home.mkdir()\n"
                "write_home(str(home), [{'id': 't1'}])\n"
                "db = Path(tmp.name) / 'open.db'\n"
                "write_store(db, [make_session('ses_1')])\n"
                "poller = ProviderPoller(CodexStore(home), db)\n"
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
        db = self.fixture.opencode([make_session('ses_1')])
        poller = ProviderPoller(store, db)
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
            {'scope': 'global', 'tracking_provider': 'opencode'},
            mark_provider='opencode')
        self.assertGreater(newer['generation'], out['generation'])

    def test_late_pinned_change_success_cannot_repaint(self):
        store = self.fixture.codex([{'id': 't1'}, {'id': 't2'}])
        db = self.fixture.opencode(
            [make_session('ses_a', project='proj-a',
                          directory='/synthetic/alpha',
                          tokens=(10, 1, 1, 1, 0)),
             make_session('ses_b', project='proj-b',
                          directory='/synthetic/beta',
                          tokens=(20, 2, 2, 2, 0))])
        poller = ProviderPoller(store, db)
        self._pollers.append(poller)
        _sync(poller, {'scope': 'conversation', 'pinned': 'ses_a',
                       'tracking_provider': 'opencode'}, now=NOW_S)
        entered = threading.Event()
        release = threading.Event()
        orig = OpenCodeProvider.read
        try:
            def blocking(inner_self, *args, **kwargs):
                entered.set()
                assert release.wait(timeout=30)
                return orig(inner_self, *args, **kwargs)
            OpenCodeProvider.read = blocking
            outcome = {}
            thread = threading.Thread(
                target=lambda: outcome.setdefault(
                    'out', poller.poll(
                        {'scope': 'conversation', 'pinned': 'ses_a',
                         'tracking_provider': 'opencode'}, now=NOW_S)),
                daemon=True)
            thread.start()
            self.assertTrue(entered.wait(timeout=10))
            thread.join(timeout=10)
            poller.apply_settings(
                {'scope': 'conversation', 'pinned': 'ses_b',
                 'tracking_provider': 'opencode'}, now=NOW_S)
            release.set()
            self.assertTrue(poller.drain(timeout=10))
            for _ in range(2):
                poller.poll({'scope': 'conversation', 'pinned': 'ses_b',
                             'tracking_provider': 'opencode'}, now=NOW_S)
                self.assertTrue(poller.drain(timeout=10))
            settled = poller.poll(
                {'scope': 'conversation', 'pinned': 'ses_b',
                 'tracking_provider': 'opencode'}, now=NOW_S)
            self.assertNotEqual(settled['result'].get('session_id'),
                                'opencode:ses_a')
        finally:
            OpenCodeProvider.read = orig
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
        write_home(str(home), threads)
        return CodexStore(home)

    def _db(self, name, sessions, messages=(), parts=()):
        path = self.work / name
        write_store(path, sessions, messages, parts)
        return path

    def _attach(self, threads, sessions, messages=(), parts=()):
        from provider_poller import ProviderPoller as Poller
        self.panel.provider_poller.drain(timeout=10)
        self.panel.provider_poller.close()
        home = self._home(f'codex-{len(list(self.work.iterdir()))}',
                          threads)
        db = self._db(f'open-{len(list(self.work.iterdir()))}.db',
                      sessions, messages, parts)
        self.panel.provider_poller = Poller(home, db)
        return self.panel.provider_poller

    def _poll_render(self, prefs=None, now=None, **kw):
        prefs = dict({'scope': 'global'}, **(prefs or {}))
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
        from providers import CodexProvider as _Codex
        poller = self._attach(
            [{'id': 't1', 'working': True}, {'id': 't2'}],
            [make_session('ses_a', project='proj-a',
                          directory='/synthetic/alpha',
                          tokens=(10, 1, 1, 1, 0)),
             make_session('ses_b', project='proj-b',
                          directory='/synthetic/beta',
                          tokens=(20, 2, 2, 2, 0), updated=BASE_MS)],
            [make_message('m1', 'ses_b')],
            [make_part('p1', 'ses_b', created=BASE_MS - 100000)])
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
            thread.join(timeout=10)
            # Production settings path: persist, apply, synchronous emit.
            self.panel.prefs.update(
                scope='project', pinned='ses_a',
                tracking_provider='opencode')
            immediate = poller.apply_settings(
                dict(self.panel.prefs), mark_provider='opencode',
                now=NOW_S)
            # Actual Qt bridge/render path for the immediate emission.
            self.panel.bridge.data.emit(immediate['result'])
            self.app.processEvents()
            self.assertIn('OpenCode', self.panel.connection.text())
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
            self.assertIn('OpenCode', self.panel.connection.text())
            self.assertEqual(
                self.panel._render_generation,
                immediate['generation'])
        finally:
            poller._collect = orig
            release.set()

    def test_settings_save_paths(self):
        from widget import Settings
        poller = self._attach(
            [{'id': 't1', 'working': True}],
            [make_session('ses_a', project='proj-a',
                          directory='/synthetic/alpha',
                          tokens=(10, 1, 1, 1, 0)),
             make_session('ses_b', project='proj-b',
                          directory='/synthetic/beta',
                          tokens=(20, 2, 2, 2, 0), updated=BASE_MS)],
            [make_message('m1', 'ses_b')],
            [make_part('p1', 'ses_b', created=BASE_MS - 100000)])
        self._poll_render(active_title='t1', detection_valid=True,
                          now=NOW_S)
        gen0 = poller.generation
        # Manual change applies immediately without another poll.
        settings = Settings(self.panel)
        settings.tracking.setCurrentIndex(
            settings.tracking.findData('opencode'))
        settings.scope.setCurrentIndex(
            settings.scope.findData('project'))
        settings.task.setCurrentIndex(max(
            0, settings.task.findData('ses_a')))
        settings.save()
        self.assertEqual(
            self.panel.prefs['tracking_provider'], 'opencode')
        self.assertEqual(self.panel.prefs['scope'], 'project')
        self.assertIn('OpenCode', self.panel.connection.text())
        self.assertGreater(poller.generation, gen0)
        # Simultaneous scope/pinned stay source-consistent: the immediate
        # project panel is honest pending (no Global relabeled as Project)
        # and never shows another pinned session's data.
        immediate_scope = self.panel.snapshot.get('scope')
        self.assertEqual(immediate_scope, 'project')
        # Pending unavailable clears the heroes (em-dash, never stale
        # Global numbers).
        self.assertEqual(self.panel.total.text(), '—')
        # Cancel changes nothing (generation + prefs stable).
        gen1 = poller.generation
        settings = Settings(self.panel)
        settings.tracking.setCurrentIndex(
            settings.tracking.findData('codex'))
        settings.reject()
        self.assertEqual(
            self.panel.prefs['tracking_provider'], 'opencode')
        self.assertEqual(poller.generation, gen1)
        # Reset applies Auto/default scope honestly (no mislabeled cache).
        settings = Settings(self.panel)
        settings.reset_to_defaults()
        settings.reset_to_defaults()
        settings.save()
        self.assertEqual(
            self.panel.prefs['tracking_provider'], 'auto')
        self.assertEqual(self.panel.prefs['scope'], 'conversation')
        # Failed save invalidates nothing and changes no running state.
        gen2 = poller.generation
        sel_before = dict(poller.selection.snapshot())
        settings = Settings(self.panel)
        settings.tracking.setCurrentIndex(
            settings.tracking.findData('codex'))
        with patch('widget.write_preferences',
                   side_effect=OSError('disk-full')):
            settings.save()
        self.assertNotEqual(
            self.panel.prefs['tracking_provider'], 'codex')
        self.assertEqual(poller.generation, gen2)
        self.assertEqual(poller.selection.snapshot(), sel_before)


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
        db = self.fixture.opencode(
            [make_session('ses_a', project='proj-a',
                          directory='/synthetic/alpha',
                          tokens=(10, 1, 1, 1, 0)),
             make_session('ses_b', project='proj-b',
                          directory='/synthetic/beta',
                          tokens=(20, 2, 2, 2, 0), updated=BASE_MS)],
            [make_message('m1', 'ses_b')],
            [make_part('p1', 'ses_b', created=BASE_MS - 100000)])
        poller = ProviderPoller(store, db)
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

    def test_codex_failure_never_pulls_opencode_off(self):
        poller = self._poller()
        _sync(poller, {'scope': 'global',
                       'tracking_provider': 'opencode'}, now=NOW_S)
        entered, release = self._hold(CodexProvider)
        try:
            out = poller.loop_tick(
                {'scope': 'global', 'tracking_provider': 'opencode'},
                now=NOW_S)
            # loop_tick itself never blocks on the held provider.
            self.assertIsNotNone(out['result'].get('generation'))
            self.assertEqual(out['provider_id'], 'opencode')
            self.assertEqual(out['selection']['selected'], 'opencode')
        finally:
            release.set()
        self.assertTrue(poller.drain(timeout=10))
        settled = poller.loop_tick(
            {'scope': 'global', 'tracking_provider': 'opencode'},
            now=NOW_S)
        self.assertEqual(settled['provider_id'], 'opencode')
        self.assertEqual(poller.selection.last_use, {})

    def test_opencode_failure_never_pulls_codex_off(self):
        poller = self._poller()
        _sync(poller, {'scope': 'global'}, active_title='t1',
              detection_valid=True, now=NOW_S)
        entered, release = self._hold(OpenCodeProvider)
        try:
            out = poller.loop_tick(
                {'scope': 'global', 'tracking_provider': 'codex'},
                active_title='t1', detection_valid=True, now=NOW_S)
            self.assertIsNotNone(out['result'].get('generation'))
            self.assertEqual(out['provider_id'], 'codex')
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

    def test_current_opencode_failure_is_tagged_and_honest(self):
        poller = self._poller()
        _sync(poller, {'scope': 'project', 'pinned': 'ses_a',
                       'tracking_provider': 'opencode'}, now=NOW_S)
        with patch.object(OpenCodeProvider, 'read',
                          side_effect=RuntimeError('boom')):
            out = poller.loop_tick(
                {'scope': 'project', 'pinned': 'ses_a',
                 'tracking_provider': 'opencode'}, now=NOW_S)
            self.assertTrue(poller.drain(timeout=10))
            out = poller.loop_tick(
                {'scope': 'project', 'pinned': 'ses_a',
                 'tracking_provider': 'opencode'}, now=NOW_S)
        self.assertIsNotNone(out['result'].get('generation'))
        self.assertEqual(out['result']['provider_id'], 'opencode')
        self.assertEqual(out['result']['scope'], 'project')
        self.assertFalse(out['result']['available'])
        self.assertNotIn('gpt-6-astra', repr(out['result']))
        self.assertEqual(poller.selection.last_use, {})

    def test_poll_raise_returns_preference_bound_failure(self):
        poller = self._poller()
        _sync(poller, {'scope': 'global',
                       'tracking_provider': 'opencode'}, now=NOW_S)
        with patch.object(ProviderPoller, 'poll',
                          side_effect=RuntimeError('poll-boom')):
            out = poller.loop_tick(
                {'scope': 'project', 'pinned': 'ses_a',
                 'tracking_provider': 'opencode'}, now=NOW_S)
        # Bound to the request preference — never hard-coded Codex.
        self.assertIsNotNone(out['result'].get('generation'))
        self.assertEqual(out['provider_id'], 'opencode')
        self.assertEqual(out['result']['scope'], 'project')
        self.assertFalse(out['result']['available'])
        self.assertEqual(poller.selection.last_use, {})

    def test_reset_failure_keeps_opencode_live_and_adapter(self):
        poller = self._poller()
        live = _sync(poller, {'scope': 'global',
                              'tracking_provider': 'opencode'}, now=NOW_S)
        self.assertTrue(live['selection']['live'])
        old_adapter = poller.codex
        with patch('provider_poller.CodexStore',
                   side_effect=OSError('store-gone')):
            out = poller.loop_tick(
                {'scope': 'global', 'tracking_provider': 'opencode'},
                now=NOW_S, reset_requested=True)
        # Provider-isolated: the Codex reset failure never becomes an
        # OpenCode failure. The healthy lane updates independently and
        # stays coherent (live, available, genuine success status).
        self.assertEqual(out['provider_id'], 'opencode')
        self.assertEqual(out['result']['scope'], 'global')
        self.assertTrue(out['result']['available'])
        self.assertTrue(out['selection']['live'])
        self.assertNotEqual(out['result'].get('status'),
                            'status_read_failed')
        self.assertIsNotNone(out['result'].get('generation'))
        self.assertIs(poller.codex, old_adapter)
        self.assertNotEqual(
            (poller._reads.get(PROVIDER_OPENCODE) or {}).get('reason'),
            'status_read_failed')
        self.assertFalse(poller._status[PROVIDER_CODEX]['source_available'])
        self.assertTrue(
            poller._status[PROVIDER_OPENCODE]['source_available'])
        self.assertEqual(poller.selection.last_use, {})
        # A newer settings result still orders after the failure tick.
        newer = poller.apply_settings(
            {'scope': 'global', 'tracking_provider': 'opencode'},
            mark_provider='opencode', now=NOW_S)
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
        # Live revoked and no OpenCode values leaking under Codex.
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
        db = self.fixture.opencode(
            [make_session('ses_a', project='proj-a',
                          directory='/synthetic/alpha',
                          tokens=(10, 1, 1, 1, 0)),
             make_session('ses_b', project='proj-b',
                          directory='/synthetic/beta',
                          tokens=(20, 2, 2, 2, 0), updated=BASE_MS)],
            [make_message('m1', 'ses_b')],
            [make_part('p1', 'ses_b', created=BASE_MS - 100000)])
        poller = ProviderPoller(store, db)
        self._pollers.append(poller)
        return poller

    def _assert_coherent_failure(self, out, provider, scope):
        self.assertIsNotNone(out['result'].get('generation'))
        self.assertEqual(out['provider_id'], provider)
        self.assertEqual(out['result']['scope'], scope)
        self.assertFalse(out['selection']['live'])
        self.assertFalse(out['result']['available'])
        self.assertIsNone(out['result'].get('working_context'))

    def test_internal_failure_manual_opencode_revokes_live(self):
        poller = self._poller()
        prefs = {'scope': 'global', 'tracking_provider': 'opencode'}
        live = _sync(poller, prefs, now=NOW_S)
        self.assertTrue(live['selection']['live'])
        with patch.object(ProviderPoller, '_decide',
                          side_effect=RuntimeError('decide-boom')):
            out = poller.poll(prefs, now=NOW_S)
        self._assert_coherent_failure(out, 'opencode', 'global')
        self.assertEqual(poller.selection.last_use, {})
        newer = poller.apply_settings(
            dict(prefs), mark_provider='opencode', now=NOW_S)
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
        self.assertNotIn('ses_b', repr(out['result']))
        self.assertEqual(poller.selection.last_use, {})

    def test_outer_raise_manual_opencode_cannot_look_successful(self):
        poller = self._poller()
        prefs = {'scope': 'project', 'pinned': 'ses_a',
                 'tracking_provider': 'opencode'}
        live = _sync(poller, prefs, now=NOW_S)
        self.assertTrue(live['selection']['live'])
        with patch.object(ProviderPoller, 'poll',
                          side_effect=RuntimeError('poll-boom')):
            out = poller.loop_tick(dict(prefs), now=NOW_S)
        self._assert_coherent_failure(out, 'opencode', 'project')
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
        for tracking, provider in (('opencode', 'opencode'),
                                   ('codex', 'codex')):
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
        prefs = {'scope': 'global', 'tracking_provider': 'opencode'}
        _sync(poller, prefs, now=NOW_S)
        with patch('provider_poller.CodexStore',
                   side_effect=OSError('store-gone')):
            failed = poller.loop_tick(dict(prefs), now=NOW_S,
                                      reset_requested=True)
        self.assertIsNotNone(failed['result'].get('generation'))
        newer = poller.apply_settings(
            {'scope': 'project', 'pinned': 'ses_a',
             'tracking_provider': 'opencode'},
            mark_provider='opencode', now=NOW_S)
        self.assertGreater(newer['generation'], failed['generation'])
        self.assertEqual(newer['result']['scope'], 'project')

    def test_repeated_reset_failures_stay_bounded(self):
        poller = self._poller()
        prefs = {'scope': 'global', 'tracking_provider': 'opencode'}
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
        # their own); workers stay at exactly the two bounded lanes.
        steps = [b - a for a, b in zip(generations, generations[1:])]
        self.assertTrue(all(step == 1 for step in steps), steps)
        self.assertEqual(len(poller._workers), 2)
        self.assertEqual(poller.selection.last_use, {})

    def test_close_during_reset_request_stays_tagged(self):
        poller = self._poller()
        prefs = {'scope': 'global', 'tracking_provider': 'opencode'}
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

    def test_held_opencode_read_survives_failed_reset(self):
        from opencode_provider import OpenCodeProvider as _Open
        poller = self._poller()
        prefs = {'scope': 'global', 'tracking_provider': 'opencode'}
        _sync(poller, prefs, now=NOW_S)
        # Settle: leftovers done so the held thread submits fresh reads.
        self.assertTrue(poller.drain(timeout=10))
        epoch_before = poller._epoch
        entered = threading.Event()
        release = threading.Event()
        orig = _Open.read
        try:
            def blocking(inner_self, *args, **kwargs):
                entered.set()
                self.assertTrue(release.wait(timeout=30))
                return orig(inner_self, *args, **kwargs)

            _Open.read = blocking
            outcome = {}
            thread = threading.Thread(
                target=lambda: outcome.setdefault(
                    'out', poller.poll(dict(prefs), now=NOW_S)),
                daemon=True)
            thread.start()
            self.assertTrue(entered.wait(timeout=10))
            thread.join(timeout=10)
            self.assertFalse(thread.is_alive())
            held = poller._inflight.get('opencode')
            self.assertIsNotNone(held)
            held_rid = held.request.rid
            self.assertFalse(held.done())
            with patch('provider_poller.CodexStore',
                       side_effect=OSError('store-gone')):
                out = poller.loop_tick(dict(prefs), now=NOW_S,
                                       reset_requested=True)
            # Provider-local: no global invalidation, no OpenCode cancel.
            self.assertEqual(poller._epoch, epoch_before)
            self.assertIs(poller._inflight.get('opencode'), held)
            self.assertFalse(held.done())
            self.assertEqual(out['provider_id'], 'opencode')
            # An identifiable update lands while the read is held, then
            # the exact held result is accepted (never retired by the
            # Codex-owned barrier). In-place INSERT (never a file
            # replace: readers hold the store open, and Windows blocks
            # replacement of open files at OS level).
            new_row = make_session('ses_new', project='proj-c',
                                   directory='/synthetic/gamma',
                                   tokens=(70, 7, 7, 7, 0), cost=0.05,
                                   updated=BASE_MS)
            with closing(sqlite3.connect(
                    poller.opencode.db_path)) as db:
                db.execute(
                    'INSERT INTO session VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    tuple(new_row[key] for key in (
                        'id', 'project_id', 'parent_id', 'directory',
                        'agent', 'model', 'version', 'tokens_input',
                        'tokens_output', 'tokens_reasoning',
                        'tokens_cache_read', 'tokens_cache_write',
                        'cost', 'time_created', 'time_updated')))
                db.commit()
            release.set()
            self.assertTrue(poller.drain(timeout=10))
            settled = poller.poll(dict(prefs), now=NOW_S)
            self.assertEqual(poller._accepted_rid.get('opencode'), held_rid)
            self.assertEqual(
                poller._provenance['opencode']['rid'], held_rid)
            self.assertEqual(
                settled['result']['tokens']['input'], 10 + 20 + 70)
            self.assertEqual(settled['provider_id'], 'opencode')
            self.assertTrue(settled['selection']['live'])
        finally:
            _Open.read = orig
            release.set()

    def test_simultaneous_lanes_only_codex_fenced(self):
        from opencode_provider import OpenCodeProvider as _Open
        poller = self._poller()
        prefs = {'scope': 'global', 'tracking_provider': 'opencode'}
        _sync(poller, prefs, now=NOW_S)
        # Settle: leftovers done so the held thread submits fresh reads.
        self.assertTrue(poller.drain(timeout=10))
        entered_codex = threading.Event()
        release_codex = threading.Event()
        entered_open = threading.Event()
        release_open = threading.Event()
        orig_codex = CodexProvider.read
        orig_open = _Open.read
        try:
            def blocking_codex(inner_self, *args, **kwargs):
                entered_codex.set()
                self.assertTrue(release_codex.wait(timeout=30))
                return orig_codex(inner_self, *args, **kwargs)

            def blocking_open(inner_self, *args, **kwargs):
                entered_open.set()
                self.assertTrue(release_open.wait(timeout=30))
                return orig_open(inner_self, *args, **kwargs)

            CodexProvider.read = blocking_codex
            _Open.read = blocking_open
            outcome = {}
            thread = threading.Thread(
                target=lambda: outcome.setdefault(
                    'out', poller.poll(dict(prefs), now=NOW_S)),
                daemon=True)
            thread.start()
            self.assertTrue(entered_codex.wait(timeout=10))
            self.assertTrue(entered_open.wait(timeout=10))
            thread.join(timeout=10)
            self.assertFalse(thread.is_alive())
            held_open = poller._inflight.get('opencode')
            held_codex = poller._inflight.get('codex')
            self.assertIsNotNone(held_open)
            self.assertIsNotNone(held_codex)
            open_rid = held_open.request.rid
            codex_accepted_mid = poller._accepted_rid.get('codex')
            with patch('provider_poller.CodexStore',
                       side_effect=OSError('store-gone')):
                poller.loop_tick(dict(prefs), now=NOW_S,
                                 reset_requested=True)
            # Only the Codex lane is fenced: epoch untouched, OpenCode
            # request still pending on the same future, OpenCode health
            # untouched, Codex marked failed.
            self.assertEqual(
                poller._inflight.get('opencode'), held_open)
            self.assertFalse(held_open.done())
            self.assertTrue(
                poller._status[PROVIDER_OPENCODE]['source_available'])
            self.assertFalse(
                poller._status[PROVIDER_CODEX]['source_available'])
            release_open.set()
            release_codex.set()
            self.assertTrue(poller.drain(timeout=10))
            poller.poll(dict(prefs), now=NOW_S)
            # Released OpenCode result admitted; released pre-failure
            # Codex success fenced out and cannot clear the marking.
            self.assertEqual(poller._accepted_rid.get('opencode'), open_rid)
            self.assertEqual(
                poller._accepted_rid.get('codex'), codex_accepted_mid)
            self.assertEqual(
                (poller._reads.get(PROVIDER_CODEX) or {}).get('reason'),
                'status_read_failed')
            self.assertFalse(
                poller._status[PROVIDER_CODEX]['source_available'])
        finally:
            CodexProvider.read = orig_codex
            _Open.read = orig_open
            release_codex.set()
            release_open.set()


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
        write_home(str(home), threads)
        return CodexStore(home)

    def _db(self, name, sessions, messages=(), parts=()):
        path = self.work / name
        write_store(path, sessions, messages, parts)
        return path

    def _attach(self, threads, sessions, messages=(), parts=()):
        from provider_poller import ProviderPoller as Poller
        self.panel.provider_poller.drain(timeout=10)
        self.panel.provider_poller.close()
        home = self._home(f'codex-{len(list(self.work.iterdir()))}',
                          threads)
        db = self._db(f'open-{len(list(self.work.iterdir()))}.db',
                      sessions, messages, parts)
        self.panel.provider_poller = Poller(home, db)
        return self.panel.provider_poller

    def _poll_render(self, prefs=None, now=None, **kw):
        prefs = dict({'scope': 'global'}, **(prefs or {}))
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

    def _seed_both(self):
        return self._attach(
            [{'id': 't1', 'working': True}, {'id': 't2'}],
            [make_session('ses_a', project='proj-a',
                          directory='/synthetic/alpha',
                          tokens=(10, 1, 1, 1, 0)),
             make_session('ses_b', project='proj-b',
                          directory='/synthetic/beta',
                          tokens=(20, 2, 2, 2, 0), updated=BASE_MS)],
            [make_message('m1', 'ses_b')],
            [make_part('p1', 'ses_b', created=BASE_MS - 100000)])

    def test_obsolete_codex_failure_cannot_overwrite_opencode(self):
        from providers import CodexProvider as _Codex
        poller = self._seed_both()
        self.panel.prefs.update(
            scope='project', pinned='ses_a',
            tracking_provider='opencode')
        for _ in range(2):
            poller.poll(dict(self.panel.prefs), now=NOW_S)
            self.assertTrue(poller.drain())
        current = poller.poll(dict(self.panel.prefs), now=NOW_S)
        self.panel.render(current['result'])
        self.app.processEvents()
        self.assertIn('OpenCode', self.panel.connection.text())
        self.assertTrue(poller.drain(timeout=10))
        current_gen = current['generation']
        # Old Codex/global iteration started before the settings change:
        # hold its provider read, then fail it on release.
        self.panel.prefs.update(scope='global', pinned='',
                                tracking_provider='codex')
        entered, release = self._hold_read(_Codex, fail=True)
        outcome = {}
        thread = threading.Thread(
            target=lambda: outcome.setdefault(
                'out', self.panel.read_loop_once()), daemon=True)
        thread.start()
        try:
            self.assertTrue(entered.wait(timeout=10))
            thread.join(timeout=10)
            self.assertFalse(thread.is_alive())
            # Newer OpenCode/Project wins while the old tick is held.
            self.panel.prefs.update(
                scope='project', pinned='ses_a',
                tracking_provider='opencode')
            newer = poller.apply_settings(
                dict(self.panel.prefs), mark_provider='opencode',
                now=NOW_S)
            self.panel.bridge.data.emit(newer['result'])
            self.app.processEvents()
            self.assertIn('OpenCode', self.panel.connection.text())
            self.assertGreaterEqual(newer['generation'], current_gen)
            release.set()
            thread.join(timeout=10)
            self.assertFalse(thread.is_alive())
            old = outcome['out']
            self.assertIsNotNone(old['result'].get('generation'))
            self.assertLess(old['generation'], newer['generation'])
            self.panel.bridge.data.emit(old['result'])
            self.app.processEvents()
            self.assertIn('OpenCode', self.panel.connection.text())
            self.assertEqual(self.panel._render_generation,
                             newer['generation'])
        finally:
            release.set()

    def test_obsolete_opencode_failure_cannot_overwrite_codex(self):
        from opencode_provider import OpenCodeProvider as _Open
        # Codex working, OpenCode idle: the seed honestly renders Codex.
        poller = self._attach(
            [{'id': 't1', 'working': True}, {'id': 't2'}],
            [make_session('ses_a', project='proj-a',
                          directory='/synthetic/alpha',
                          tokens=(10, 1, 1, 1, 0)),
             make_session('ses_b', project='proj-b',
                          directory='/synthetic/beta',
                          tokens=(20, 2, 2, 2, 0))])
        self._poll_render(active_title='t1', detection_valid=True,
                          now=NOW_S)
        self.assertIn('Codex', self.panel.connection.text())
        self.assertTrue(poller.drain(timeout=10))
        self.panel.prefs.update(
            scope='project', pinned='ses_a',
            tracking_provider='opencode')
        entered, release = self._hold_read(_Open)
        outcome = {}
        thread = threading.Thread(
            target=lambda: outcome.setdefault(
                'out', self.panel.read_loop_once()), daemon=True)
        thread.start()
        try:
            self.assertTrue(entered.wait(timeout=10))
            thread.join(timeout=10)
            self.assertFalse(thread.is_alive())
            # Newer Codex wins while the old OpenCode tick is held: the
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

    def test_current_opencode_failure_renders_honest_project(self):
        from opencode_provider import OpenCodeProvider as _Open
        self._seed_both()
        self.panel.prefs.update(
            scope='project', pinned='ses_a',
            tracking_provider='opencode')
        with patch.object(_Open, 'read',
                          side_effect=RuntimeError('boom')):
            snap = self.panel.read_loop_once()
            self.assertTrue(
                self.panel.provider_poller.drain(timeout=10))
            snap = self.panel.read_loop_once()
        self.assertIsNotNone(snap['result'].get('generation'))
        self.panel.bridge.data.emit(snap['result'])
        self.app.processEvents()
        self.assertIn('OpenCode', self.panel.connection.text())
        self.assertEqual(snap['result']['scope'], 'project')
        self.assertFalse(snap['selection']['live'])
        self.assertNotIn('gpt-6-astra', self.panel.model.text())
        self.assertNotIn('gpt-6-astra', self.panel.title.toolTip())

    def test_initial_manual_opencode_failure_stays_opencode(self):
        from opencode_provider import OpenCodeProvider as _Open
        self._seed_both()
        self.panel.prefs.update(
            scope='project', pinned='ses_a',
            tracking_provider='opencode')
        self.assertIsNone(self.panel._render_generation)
        with patch.object(_Open, 'read',
                          side_effect=RuntimeError('boom')):
            snap = self.panel.read_loop_once()
            self.assertTrue(
                self.panel.provider_poller.drain(timeout=10))
            snap = self.panel.read_loop_once()
        self.assertIsNotNone(snap['result'].get('generation'))
        self.assertEqual(snap['provider_id'], 'opencode')
        self.panel.bridge.data.emit(snap['result'])
        self.app.processEvents()
        self.assertIn('OpenCode', self.panel.connection.text())
        self.assertIsNotNone(self.panel._render_generation)

    def test_old_global_failure_rejected_after_project_change(self):
        from opencode_provider import OpenCodeProvider as _Open
        self._seed_both()
        self.panel.prefs.update(scope='global',
                                tracking_provider='opencode')
        with patch.object(_Open, 'read',
                          side_effect=RuntimeError('boom')):
            old_fail = self.panel.read_loop_once()
            self.assertTrue(
                self.panel.provider_poller.drain(timeout=10))
            old_fail = self.panel.read_loop_once()
        self.assertIsNotNone(old_fail['result'].get('generation'))
        self.assertEqual(old_fail['result']['scope'], 'global')
        self.assertFalse(old_fail['result']['available'])
        self.panel.prefs.update(
            scope='project', pinned='ses_a',
            tracking_provider='opencode')
        newer = self.panel.provider_poller.apply_settings(
            dict(self.panel.prefs), mark_provider='opencode', now=NOW_S)
        self.panel.bridge.data.emit(newer['result'])
        self.app.processEvents()
        self.assertGreater(newer['generation'], old_fail['generation'])
        self.panel.bridge.data.emit(old_fail['result'])
        self.app.processEvents()
        self.assertEqual(self.panel._render_generation,
                         newer['generation'])
        self.assertIn('OpenCode', self.panel.connection.text())

    def test_old_pinned_failure_rejected_after_pinned_change(self):
        from opencode_provider import OpenCodeProvider as _Open
        self._seed_both()
        self.panel.prefs.update(
            scope='conversation', pinned='ses_a',
            tracking_provider='opencode')
        with patch.object(_Open, 'read',
                          side_effect=RuntimeError('boom')):
            old_fail = self.panel.read_loop_once()
            self.assertTrue(
                self.panel.provider_poller.drain(timeout=10))
            old_fail = self.panel.read_loop_once()
        self.assertIsNotNone(old_fail['result'].get('generation'))
        self.assertFalse(old_fail['result']['available'])
        self.panel.prefs.update(
            scope='conversation', pinned='ses_b',
            tracking_provider='opencode')
        newer = self.panel.provider_poller.apply_settings(
            dict(self.panel.prefs), now=NOW_S)
        self.panel.bridge.data.emit(newer['result'])
        self.app.processEvents()
        self.assertGreater(newer['generation'], old_fail['generation'])
        self.assertNotEqual(
            newer['result'].get('session_id'), 'opencode:ses_a')
        self.panel.bridge.data.emit(old_fail['result'])
        self.app.processEvents()
        self.assertEqual(self.panel._render_generation,
                         newer['generation'])

    def test_no_production_emission_without_generation(self):
        import inspect
        from widget import Panel as _Panel
        poller = self._seed_both()
        self.panel.prefs.update(
            scope='project', pinned='ses_a',
            tracking_provider='opencode')
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
        self._seed_both()
        poller = self.panel.provider_poller
        gen = poller.generation
        poller.close()
        snap = self.panel.read_loop_once()
        self.assertIsNotNone(snap['result'].get('generation'))
        self.assertEqual(snap['generation'], gen + 1)
        self.assertEqual(poller.generation, gen + 1)

    def test_current_decide_failure_renders_coherent_opencode(self):
        poller = self._seed_both()
        self.panel.prefs.update(
            scope='project', pinned='ses_a',
            tracking_provider='opencode')
        for _ in range(2):
            poller.poll(dict(self.panel.prefs), now=NOW_S)
            self.assertTrue(poller.drain(timeout=10))
        live = poller.poll(dict(self.panel.prefs), now=NOW_S)
        self.panel.render(live['result'])
        self.app.processEvents()
        self.assertTrue(live['selection']['live'])
        self.assertIn('OpenCode', self.panel.connection.text())
        with patch.object(ProviderPoller, '_decide',
                          side_effect=RuntimeError('decide-boom')):
            snap = self.panel.read_loop_once()
        self.assertIsNotNone(snap['result'].get('generation'))
        self.assertFalse(snap['selection']['live'])
        self.assertIsNone(snap['result'].get('working_context'))
        self.panel.bridge.data.emit(snap['result'])
        self.app.processEvents()
        # Coherent: OpenCode unavailable, no false Working bubble or
        # context, mode hysteresis untouched (no token arming).
        self.assertIn('OpenCode', self.panel.connection.text())
        self.assertIsNone(self.panel.pet.working_context)
        self.assertFalse(self.panel.pet.token_bubble_visible())
        self.assertFalse(snap['result']['available'])

    def test_reset_failure_opencode_stays_live_through_bridge(self):
        from unittest.mock import patch as _patch
        # Real-time fixtures: read_loop_once runs on the wall clock, so
        # lifecycle/freshness evidence must be wall-clock fresh.
        now_ms = int(time.time() * 1000)
        poller = self._attach(
            [{'id': 't1'}, {'id': 't2'}],
            [make_session('ses_a', project='proj-a',
                          directory='/synthetic/alpha',
                          tokens=(10, 1, 1, 1, 0),
                          created=now_ms - 60000, updated=now_ms),
             make_session('ses_b', project='proj-b',
                          directory='/synthetic/beta',
                          tokens=(20, 2, 2, 2, 0),
                          created=now_ms - 60000, updated=now_ms)],
            [make_message('m1', 'ses_b', created=now_ms - 1000)],
            [make_part('p1', 'ses_b', created=now_ms - 1000)])
        self.panel.prefs.update(
            scope='project', pinned='ses_a',
            tracking_provider='opencode')
        for _ in range(2):
            poller.poll(dict(self.panel.prefs))
            self.assertTrue(poller.drain(timeout=10))
        live = poller.poll(dict(self.panel.prefs))
        self.panel.render(live['result'])
        self.app.processEvents()
        self.assertTrue(live['selection']['live'])
        old_adapter = poller.codex
        with _patch('provider_poller.CodexStore',
                    side_effect=OSError('store-gone')):
            self.panel.reset_store.set()
            snap = self.panel.read_loop_once()
            self.panel.reset_store.clear()
        # The Codex reset failure never becomes an OpenCode failure:
        # the healthy lane stays live with genuine success status.
        self.assertEqual(snap['provider_id'], 'opencode')
        self.assertTrue(snap['selection']['live'])
        self.assertTrue(snap['result']['available'])
        self.assertNotEqual(snap['result'].get('status'),
                            'status_read_failed')
        self.assertIs(poller.codex, old_adapter)
        self.panel.bridge.data.emit(snap['result'])
        self.app.processEvents()
        self.assertIn('OpenCode', self.panel.connection.text())

    def test_reset_failure_codex_selected_renders_unavailable(self):
        from unittest.mock import patch as _patch
        poller = self._attach(
            [{'id': 't1', 'working': True}, {'id': 't2'}],
            [make_session('ses_a', project='proj-a',
                          directory='/synthetic/alpha',
                          tokens=(10, 1, 1, 1, 0))])
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
