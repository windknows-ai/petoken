"""Selection and membership commit together before settings or shutdown."""
import os as _os
import tempfile as _tempfile
# Hermetic Claude lane: a never-created home keeps real ~/.claude data out.
_os.environ.setdefault('PETOKEN_CLAUDE_HOME', _os.path.join(
    _tempfile.gettempdir(), 'petoken-tests-no-claude-home'))
import tempfile
import threading
import unittest
from unittest.mock import patch

from provider_poller import ProviderPoller, _normalize_scope
from tests.test_provider_poller import NOW_S, PollerFixture


class PublicationRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        fixture = PollerFixture(self.temp.name)
        self.poller = ProviderPoller(
            fixture.codex([{'id': 't1', 'working': True}]))
        self.prefs = {'scope': 'global', 'tracking_provider': 'codex'}
        self.events = []
        self.threads = []
        self.errors = []
        for _ in range(3):
            self.settled = self.poller.poll(
                self.prefs, active_title='t1', detection_valid=True, now=NOW_S)
            self.assertTrue(self.poller.drain())
        self.assertTrue(self.settled['selection']['live'])
        self.assertEqual([t['task_key'] for t in self.settled['active_tasks']], ['t1'])

    def tearDown(self):
        for event in self.events:
            event.set()
        for thread in self.threads:
            thread.join(timeout=10)
        self.poller.close()
        for worker in self.poller._workers.values():
            worker.join(timeout=10)
            self.assertFalse(worker.is_alive())
        self.temp.cleanup()

    def _pause(self):
        entered, release = threading.Event(), threading.Event()
        self.events.append(release)
        return entered, release

    def _start(self, action):
        result = {}

        def run():
            try:
                result['out'] = action()
            except Exception as exc:
                self.errors.append(exc)

        thread = threading.Thread(target=run, daemon=True)
        self.threads.append(thread)
        thread.start()
        return thread, result

    def _join(self, thread):
        thread.join(timeout=10)
        self.assertFalse(thread.is_alive())
        self.assertEqual(self.errors, [])

    def _obsolete_decision(self, change):
        entered, release = self._pause()
        original = self.poller._decide

        def pause(tick):
            entered.set()
            self.assertTrue(release.wait(timeout=10))
            return original(tick)

        with patch.object(self.poller, '_decide', side_effect=pause):
            thread, result = self._start(lambda: self.poller.poll(self.prefs, now=NOW_S))
            self.assertTrue(entered.wait(timeout=10))
            # Use the original decision for any newer poll in this thread.
            with patch.object(self.poller, '_decide', side_effect=original):
                change()
            before = self.poller.selection.snapshot()
            release.set()
            self._join(thread)
        self.assertEqual(self.poller.selection.snapshot(), before)
        self.assertLess(result['out']['generation'], self.poller.generation)
        self.assertFalse(result['out']['result']['available'])
        self.assertEqual(result['out']['active_tasks'], [])
        return result['out']

    def test_settings_epoch_rejects_decision_before_selection_mutation(self):
        out = self._obsolete_decision(lambda: self.poller.apply_settings(
            dict(self.prefs, tracking_provider='opencode'), now=NOW_S))
        self.assertEqual(out['result']['status'], 'obsolete_tick')
        self.assertEqual(self.poller.selection.snapshot()['selected'], 'codex')

    def test_newer_poll_generation_rejects_decision_without_epoch_change(self):
        epoch = self.poller._epoch
        self._obsolete_decision(lambda: self.poller.poll(
            dict(self.prefs, tracking_provider='opencode'), now=NOW_S))
        self.assertEqual(self.poller._epoch, epoch)
        self.assertEqual(self.poller.selection.snapshot()['selected'], 'codex')

    def test_close_rejects_decision_and_retains_selector_memory(self):
        out = self._obsolete_decision(self.poller.close)
        self.assertFalse(out['selection']['live'])
        self.assertIsNone(out['result']['working_context'])
        self.assertTrue(self.poller.selection.snapshot()['live'])

    def _race_final_merge(self, change):
        entered, release = self._pause()
        attempted = threading.Event()
        original = self.poller._merged_active_tasks

        def pause(*args, **kwargs):
            if threading.current_thread() is poll_thread:
                entered.set()
                self.assertTrue(release.wait(timeout=10))
            return original(*args, **kwargs)

        # The poll thread is assigned before the worker reaches the merge.
        ready = threading.Event()
        with patch.object(self.poller, '_merged_active_tasks', side_effect=pause):
            poll_thread, result = self._start(lambda: (
                ready.wait(timeout=10), self.poller.poll(
                    self.prefs, active_title='t1', detection_valid=True, now=NOW_S))[1])
            ready.set()
            self.assertTrue(entered.wait(timeout=10))
            acquired = self.poller._lock.acquire(blocking=False)
            if acquired:
                self.poller._lock.release()
            self.assertFalse(acquired, 'final envelope escaped its commit lock')

            def mutate():
                attempted.set()
                return change()

            change_thread, _ = self._start(mutate)
            self.assertTrue(attempted.wait(timeout=10))
            release.set()
            self._join(poll_thread)
            self._join(change_thread)
        out = result['out']
        self.assertLess(out['generation'], self.poller.generation)
        self.assertEqual(out['preference'], 'codex')
        self.assertEqual(out['selection']['selected'], 'codex')
        self.assertTrue(out['selection']['live'])
        self.assertEqual(out['result']['working_context']['thread'], 't1')
        self.assertEqual([t['task_key'] for t in out['active_tasks']], ['t1'])

    def test_close_serializes_with_final_merge_and_retires_committed_payload(self):
        self._race_final_merge(self.poller.close)
        out = self.poller.poll(self.prefs, now=NOW_S)
        self.assertEqual(out['generation'], self.poller.generation)
        self.assertFalse(out['selection']['live'])
        self.assertFalse(out['result']['available'])
        self.assertEqual(out['active_tasks'], [])
        self.assertIsNone(out['result']['working_context'])

    def test_settings_serializes_with_final_merge(self):
        self._race_final_merge(lambda: self.poller.apply_settings(
            dict(self.prefs, tracking_provider='opencode'), now=NOW_S))
        self.assertEqual(self.poller.selection.snapshot()['selected'], 'codex')

    def test_direct_scope_inputs_reject_containers_and_preserve_supported_values(self):
        for value in ([], {}, None, True, 1, 'invalid', 'task'):
            with self.subTest(value=value):
                self.assertEqual(_normalize_scope(value), 'conversation')
                out = self.poller.apply_settings(dict(self.prefs, scope=value), now=NOW_S)
                self.assertEqual(out['result']['scope'], 'conversation')
        for scope in ('global', 'project', 'conversation'):
            self.assertEqual(_normalize_scope(scope), scope)
