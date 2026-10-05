"""Synthetic protocol/argv tests: no installed Codex, account, configuration or data."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock

from codex_events import APPROVAL_METHODS, forward_notify, normalize_event


class CodexEventTests(unittest.TestCase):
    def turn(self, method, status):
        return dict(method=method, params=dict(threadId='synthetic-thread',
            turn=dict(id='synthetic-turn', status=status, error=dict(message='Private content'))))

    def test_started(self):
        hint = normalize_event(self.turn('turn/started', 'inProgress'))
        self.assertEqual((hint['kind'], hint['thread_id'], hint['turn_id']),
                         ('started', 'synthetic-thread', 'synthetic-turn'))

    def test_completed_failed_and_interrupted_are_distinct(self):
        for status in ('completed', 'failed', 'interrupted'):
            with self.subTest(status=status):
                hint = normalize_event(self.turn('turn/completed', status))
                self.assertEqual(hint['kind'], status)
                self.assertNotIn('error', hint)
                self.assertNotIn('Private content', json.dumps(hint))

    def test_retryable_error_and_unknown_terminal_are_not_failures(self):
        self.assertIsNone(normalize_event(dict(method='error', params=dict(willRetry=True))))
        self.assertIsNone(normalize_event(self.turn('turn/completed', 'future-status')))
        self.assertIsNone(normalize_event(self.turn('turn/started', 'completed')))

    def test_all_approval_and_user_input_requests_keep_request_id_without_content(self):
        for method in APPROVAL_METHODS:
            with self.subTest(method=method):
                message = dict(id=7, method=method, params=dict(threadId='thread', turnId='turn',
                    reason='Private reason', command='Private command', questions=['Private question']))
                hint = normalize_event(message)
                self.assertEqual(hint, dict(kind='waiting_for_user', source='app-server',
                                           thread_id='thread', turn_id='turn', request_id=7))
                message.pop('id')
                self.assertIsNone(normalize_event(message))
                message['id'] = True
                self.assertIsNone(normalize_event(message))

    def test_resolution(self):
        hint = normalize_event(dict(method='serverRequest/resolved', params=dict(threadId='thread', requestId=7)))
        self.assertEqual(hint['kind'], 'confirmation_resolved')
        self.assertEqual(hint['request_id'], 7)
        for malformed in (None, True, [], {'private': 'content'}):
            self.assertIsNone(normalize_event(dict(method='serverRequest/resolved',
                                                   params=dict(requestId=malformed))))

    def test_quota_is_a_hint_not_fabricated_numbers(self):
        for quotas in ({}, {'primary': None}, {'primary': {'usedPercent': 25}}):
            with self.subTest(quotas=quotas):
                hint = normalize_event(dict(method='account/rateLimits/updated', params=dict(rateLimits=quotas)))
                self.assertEqual(hint['kind'], 'quota_changed')
                self.assertNotIn('usedPercent', hint)
        self.assertIsNone(normalize_event(dict(method='account/rateLimits/updated', params={})))

    def test_notify_is_finished_not_an_inferred_success(self):
        payload = dict(type='agent-turn-complete', **{'thread-id': 'thread', 'turn-id': 'turn',
            'cwd': 'private-path', 'input-messages': ['Private prompt'], 'last-assistant-message': 'Private reply'})
        self.assertEqual(normalize_event(payload, 'notify'),
                         dict(kind='finished', source='notify', thread_id='thread', turn_id='turn'))
        for kind in ('approval-requested', 'task-started', 'agent-turn-failed'):
            self.assertIsNone(normalize_event(dict(type=kind), 'notify'))

    def test_malformed_and_unrelated_messages(self):
        for value in (None, [], 'text', {}, {'method': []}, {'method': {}, 'params': {}},
                      {'method': 'turn/started', 'params': []}, {'id': 1, 'result': {}},
                      {'method': 'turn/started', 'params': {'turn': []}}):
            with self.subTest(value=value):
                self.assertIsNone(normalize_event(value))

    def test_malformed_identifiers_never_leak_nested_content(self):
        message = self.turn('turn/started', 'inProgress')
        message['params']['threadId'] = {'private': 'content'}
        message['params']['turn']['id'] = ['private']
        hint = normalize_event(message)
        self.assertIsNone(hint['thread_id'])
        self.assertIsNone(hint['turn_id'])
        self.assertNotIn('private', json.dumps(hint))
        for status in (None, [], {'private': 'content'}):
            self.assertIsNone(normalize_event(self.turn('turn/completed', status)))

    def test_hint_is_emitted_before_original_and_raw_argument_is_unchanged(self):
        order = []
        raw = '{ "type": "agent-turn-complete", "input-messages": ["中文 \\\" quotes"] }'
        def runner(argv, **kwargs):
            order.append('original')
            self.assertEqual(argv, ['original.exe', 'prefix with spaces', raw])
            self.assertEqual(kwargs, dict(check=False, shell=False))
            return subprocess.CompletedProcess(argv, 7)
        code = forward_notify(raw, ['original.exe', 'prefix with spaces'],
                              lambda _: order.append('petoken'), runner)
        self.assertEqual(code, 7)
        self.assertEqual(order, ['petoken', 'original'])

    def test_sink_failure_still_forwards_and_preserves_exit_status(self):
        runner = Mock(return_value=subprocess.CompletedProcess([], 3))
        emit = Mock(side_effect=KeyError('Synthetic sink failure'))
        self.assertEqual(forward_notify('{"type":"agent-turn-complete"}', ['original.exe'], emit, runner), 3)
        runner.assert_called_once_with(['original.exe', '{"type":"agent-turn-complete"}'], check=False, shell=False)

    def test_malformed_or_unsupported_payload_is_still_forwarded(self):
        for raw in ('{not-json', '{"type":"future-event"}'):
            runner, emit = Mock(return_value=subprocess.CompletedProcess([], 0)), Mock()
            self.assertEqual(forward_notify(raw, ['original.exe'], emit, runner), 0)
            emit.assert_not_called()
            runner.assert_called_once_with(['original.exe', raw], check=False, shell=False)

    def test_real_subprocess_argv_preserves_unicode_quotes_and_prefix(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            capture, script = path/'argv.json', path/'original.py'
            script.write_text('import json,sys\nfrom pathlib import Path\nPath(sys.argv[1]).write_text(json.dumps(sys.argv[2:]),encoding="utf-8")\nsys.exit(7)\n', encoding='utf-8')
            raw = json.dumps({'type': 'agent-turn-complete', 'input-messages': ['中文 "quote" $() ;']}, ensure_ascii=False)
            hints = []
            code = forward_notify(raw, [sys.executable, str(script), str(capture), 'prefix with spaces'], hints.append)
            self.assertEqual(code, 7)
            self.assertEqual(json.loads(capture.read_text(encoding='utf-8')), ['prefix with spaces', raw])
            self.assertEqual(len(hints), 1)


if __name__ == '__main__':
    unittest.main()
