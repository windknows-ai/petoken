"""Synthetic malformed metadata recovery and task-local truth boundaries."""
import json
from datetime import datetime
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from opencode_provider import OpenCodeProvider, _display_basename, _sanitize_session
from usage import (CodexActivityDetector, CodexStore, SessionUsage,
                   _context_percent, _display_basename as codex_basename,
                   project_identity, quota_window)
from token_format import format_ratio, format_token_value
from pricing import estimate_usd


class SourceTruthRecoveryTests(unittest.TestCase):
    def test_native_early_date_keeps_valid_lifecycle_sibling(self):
        with tempfile.TemporaryDirectory() as directory:
            rows = []
            for thread, stamp in (('bad', '0001-01-01T00:00:00'),
                                  ('good', datetime.now().astimezone().isoformat())):
                path = Path(directory) / (thread + '.jsonl')
                path.write_text(json.dumps(dict(type='event_msg', timestamp=stamp,
                    payload=dict(type='task_started', turn_id=thread))) + '\n', encoding='utf-8')
                rows.append(dict(id=thread, name=thread, rollout_path=str(path)))
            detector = CodexActivityDetector(directory)
            self.assertIn('good', [item['thread'] for item in
                                  detector.enumerate_working_tasks(rows)])
            self.assertEqual(detector.detect(rows, 'good', True)['thread'], 'good')
            with patch('usage.datetime') as dates:
                dates.fromisoformat.return_value.timestamp.side_effect = OSError('native date')
                self.assertIsNone(detector._event_time('0001-01-01T00:00:00'))

    def test_oversized_tokens_preserve_known_total_and_bounded_context(self):
        huge = 10 ** 1000
        self.assertEqual(_context_percent(huge, 100), 100)
        self.assertEqual(_context_percent(huge, huge * 2), 50)
        self.assertEqual(_context_percent(0, huge), 0)
        for value in (None, True, -1, float('inf'), {}):
            self.assertIsNone(_context_percent(value, 100))
            self.assertIsNone(_context_percent(1, value))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'synthetic.jsonl'
            path.write_text(json.dumps(dict(type='event_msg', payload=dict(
                type='token_count', info=dict(model_context_window=100,
                    total_token_usage=dict(total_tokens=huge),
                    last_token_usage=dict(total_tokens=huge))))) + '\n', encoding='utf-8')
            projection = CodexStore(directory)._task_context(
                dict(id='huge', rollout_path=str(path)), {}, {})['presentation']
            self.assertEqual(projection['tokens']['total_tokens'], huge)
            self.assertEqual(projection['context'], 100)
        self.assertEqual(format_token_value(huge), f'{huge:,}')
        for value in (float('nan'), float('inf'), huge):
            self.assertEqual(format_ratio(value), 'N/A')

    def test_unrepresentable_estimated_cost_keeps_exact_usage(self):
        tokens = dict(input_tokens=10 ** 1000, cached_input_tokens=0,
                      output_tokens=0, total_tokens=10 ** 1000)
        self.assertIsNone(estimate_usd(tokens, 'gpt-5.6-sol'))
        session = SessionUsage('synthetic.jsonl')
        session.consume(dict(type='turn_context', payload=dict(model='gpt-5.6-sol')))
        session.consume(dict(type='event_msg', payload=dict(type='token_count',
            info=dict(total_token_usage=tokens, last_token_usage=tokens))))
        self.assertEqual(session.total['total_tokens'], 10 ** 1000)
        self.assertIsNone(session.records[0]['usd'])
        zero = dict(input_tokens=0, cached_input_tokens=0, output_tokens=0)
        self.assertEqual(estimate_usd(zero, 'gpt-5.6-sol'), 0)

    def test_nonstandard_uri_spellings_hide_private_metadata(self):
        for prefix in ('https:', 'https:/', 'https:\\', 'https:\\\\',
                       'ssh:/', 'ssh:\\'):
            value = prefix + 'synthetic-user:synthetic-secret@example.invalid/Project?token=synthetic-private#private'
            for helper in (codex_basename, _display_basename):
                with self.subTest(prefix=prefix, helper=helper.__module__):
                    self.assertEqual(helper(value), 'Project')
            self.assertEqual(project_identity(dict(id='t', cwd=value), {})[0], 'Project')
        for helper in (codex_basename, _display_basename):
            self.assertIsNone(helper('https:synthetic-user:synthetic-secret@example.invalid'))

    def test_quota_shape_and_percent_validation(self):
        for limits in (None, [], 'bad', True, {'primary': []}):
            with self.subTest(limits=limits):
                self.assertIsNone(quota_window(limits, 300, now=100))
        for used in (None, True, False, '0', [], {}, float('nan'),
                     float('inf'), -1, 101, 10 ** 1000):
            with self.subTest(used=used):
                result = quota_window({'primary': dict(windowDurationMins=300,
                    usedPercent=used, resetsAt=200)}, 300, now=100)
                self.assertIsNone(result['remaining'])
                self.assertEqual(result['reset'], 200)
                self.assertFalse(result['expired'])
        for used, remaining in ((0, 100), (100, 0), (12.5, 87.5)):
            result = quota_window({'secondary': dict(window_minutes=300,
                used_percent=used, resets_at=200)}, 300, now=201)
            self.assertEqual(result, dict(remaining=remaining, reset=200, expired=True))

    def test_invalid_reset_keeps_observed_percent_without_datetime_crash(self):
        for reset in (None, 'bad', True, False, [], {}, float('nan'),
                      float('inf'), -float('inf'), 10 ** 1000, 1e30):
            with self.subTest(reset=reset):
                result = quota_window({'primary': dict(windowDurationMins=300,
                    usedPercent=100, resetsAt=reset)}, 300, now=100)
                self.assertEqual(result, dict(remaining=0, reset=None, expired=False))
        result = quota_window({'primary': dict(windowDurationMins=300,
            usedPercent=0, resetsAt=200)}, 300, now=100)
        self.assertEqual(datetime.fromtimestamp(result['reset']), datetime.fromtimestamp(200))

    def test_uri_directory_labels_exclude_credentials_query_and_fragment(self):
        values = [
            'https://synthetic-user:synthetic-secret@example.invalid/private/Project?token=synthetic-private#private',
            'ssh://synthetic-user:synthetic-secret@example.invalid/private/Project?token=synthetic-private#private',
            '//synthetic-user:synthetic-secret@example.invalid/private/Project?token=synthetic-private#private',
        ]
        for value in values:
            with self.subTest(value=value):
                self.assertEqual(_display_basename(value), 'Project')
                label, source, identity = project_identity(dict(id='t', cwd=value), {})
                self.assertEqual((label, source), ('Project', 'cwd_basename'))
                self.assertTrue(identity.startswith('cwd:'))
                self.assertEqual(project_identity(dict(id='t', project_id='p'),
                    {'local-projects': {'p': {'name': value}}})[0], 'Project')
                self.assertEqual(project_identity(dict(id='t', git_origin_url=value), {})[0], 'Project')
        for value in ('https://synthetic-user:synthetic-secret@example.invalid',
                      'https://[broken/private/Project?token=synthetic-private'):
            self.assertIsNone(_display_basename(value))
            self.assertIsNone(project_identity(dict(id='t', cwd=value), {})[0])

    def test_native_path_names_and_identity_remain_distinct(self):
        for value, expected in ((r'D:\Private\Project Name', 'Project Name'),
                                (r'\\?\D:\Private\Project', 'Project'),
                                (r'\\synthetic-server\private\Project#1', 'Project#1'),
                                ('/private/Project#1', 'Project#1'),
                                ('/private/Project?1', 'Project?1'),
                                ('Project', 'Project')):
            with self.subTest(value=value):
                self.assertEqual(_display_basename(value), expected)
                self.assertEqual(project_identity(dict(id='t', cwd=value), {})[0], expected)
        first = project_identity(dict(id='a', cwd='/one/Project'), {})
        second = project_identity(dict(id='b', cwd='/two/Project'), {})
        self.assertEqual(first[0], second[0])
        self.assertNotEqual(first[2], second[2])
        for value in ([], {}, True, 1, None):
            self.assertIsNone(_display_basename(value))

    def test_malformed_project_assignments_fall_back_without_losing_siblings(self):
        states = [
            {'thread-project-assignments': []},
            {'thread-project-assignments': {'bad': 'bad'}},
            {'thread-project-assignments': {'bad': {'projectId': []}}},
            {'local-projects': []},
            {'local-projects': {'p': 'bad'}},
        ]
        for state in states:
            with self.subTest(state=state):
                self.assertEqual(project_identity(dict(id='bad', project_id='p',
                    cwd='/private/Fallback'), state)[0], 'Fallback')
        state = {'thread-project-assignments': {'bad': 'bad', 'good': {'projectId': 'p'}},
                 'local-projects': {'p': {'name': 'Good'}}}
        self.assertEqual(project_identity(dict(id='bad', cwd='/private/Fallback'), state)[0], 'Fallback')
        self.assertEqual(project_identity(dict(id='good'), state), ('Good', 'project_metadata', 'p'))

    def test_malformed_lifecycle_does_not_fabricate_working_or_abort_siblings(self):
        with tempfile.TemporaryDirectory() as directory:
            rows = []
            stamp = datetime.now().astimezone().isoformat()
            invalid = [dict(type='event_msg', timestamp=stamp, payload='task_started'),
                       dict(type='event_msg', timestamp=stamp, payload=['task_started']),
                       dict(type='event_msg', timestamp=stamp, payload={'type': ['task_started']}),
                       ['task_started']]
            for thread, events in (('bad', invalid), ('good', invalid + [
                    dict(type='event_msg', timestamp=stamp,
                         payload=dict(type='task_started', turn_id='turn-good'))])):
                path = Path(directory) / (thread + '.jsonl')
                path.write_text(''.join(json.dumps(event) + '\n' for event in events), encoding='utf-8')
                rows.append(dict(id=thread, rollout_path=str(path)))
            detector = CodexActivityDetector(directory)
            found = detector.enumerate_working_tasks(rows, now=time.time())
            self.assertEqual([item['thread'] for item in found], ['good'])
            self.assertEqual(detector.detect(rows, '', True)['thread'], 'good')

    def test_malformed_usage_payload_retains_known_metadata_and_marks_partial(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'synthetic.jsonl'
            events = [dict(type='turn_context', payload=dict(model='custom', effort='high')),
                      dict(type='event_msg', payload='token_count'),
                      dict(type='event_msg', payload=['token_count']),
                      dict(type='event_msg', payload=dict(type='token_count', info=dict(
                          total_token_usage=dict(total_tokens=7),
                          last_token_usage=dict(total_tokens=7))))]
            path.write_text(''.join(json.dumps(event) + '\n' for event in events), encoding='utf-8')
            session = SessionUsage(path)
            session.refresh()
            self.assertEqual(session.display_metadata({}), dict(model='custom', effort='high'))
            self.assertEqual(session.total['total_tokens'], 7)
            self.assertTrue(session.partial)
            self.assertIn('note_usage_record_invalid', session.notes)

    def test_opencode_effort_comes_from_each_task_model(self):
        rows = {}
        for thread, model, effort in (('a', 'custom-a', 'high'), ('b', 'custom-b', None)):
            row, _ = _sanitize_session(dict(id=thread, directory='/private/Project',
                model=json.dumps(dict(id=model, variant=effort)), version='1.18.31',
                tokens_input=0, tokens_output=0, tokens_reasoning=0,
                tokens_cache_read=0, tokens_cache_write=0, cost=0))
            rows[thread] = row
        with tempfile.TemporaryDirectory() as directory:
            provider = OpenCodeProvider(Path(directory) / 'synthetic.db')
            try:
                provider._sessions = rows
                with patch.object(provider, 'activity_snapshot', return_value=dict(valid=True,
                        sessions=[dict(session_id='opencode:' + thread,
                                       working=True, instant=1000) for thread in rows])):
                    tasks = provider.active_tasks()['tasks']
            finally:
                provider.close()
        self.assertEqual([(task['presentation']['model'], task['presentation']['effort'])
                          for task in tasks], [('custom-a', 'high'), ('custom-b', None)])
        self.assertTrue(all(task['presentation']['tokens']['total'] == 0 for task in tasks))


if __name__ == '__main__':
    unittest.main()
