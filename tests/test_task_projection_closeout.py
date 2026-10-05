"""Task-local truth checks using synthetic metadata only."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from usage import CodexStore, SessionUsage, project_identity


class TaskProjectionCloseoutTests(unittest.TestCase):
    def test_absent_metadata_falls_back_but_explicit_unknown_does_not(self):
        session = SessionUsage('synthetic.jsonl')
        row = {'model': 'real/arbitrary-model', 'reasoning_effort': 'high'}
        self.assertEqual(session.display_metadata(row),
                         {'model': 'real/arbitrary-model', 'effort': 'high'})
        session.consume({'type': 'turn_context', 'payload':
                         {'model': None, 'reasoning_effort': None}})
        self.assertEqual(session.display_metadata(row),
                         {'model': None, 'effort': None})
        session.consume({'type': 'turn_context', 'payload': {}})
        self.assertEqual(session.display_metadata(row),
                         {'model': None, 'effort': None})
        session.consume({'type': 'turn_context', 'payload':
                         {'model': 'custom:model-2026', 'effort': 'xhigh'}})
        self.assertEqual(session.display_metadata(row),
                         {'model': 'custom:model-2026', 'effort': 'xhigh'})

    def test_malformed_codex_metadata_is_unknown(self):
        for value in ({'id': 'model'}, [], True, 42, '', '  '):
            with self.subTest(value=value):
                session = SessionUsage('synthetic.jsonl')
                session.consume({'type': 'turn_context', 'payload':
                                 {'model': value, 'effort': value}})
                self.assertEqual(session.display_metadata(
                    {'model': 'old', 'reasoning_effort': 'old'}),
                    {'model': None, 'effort': None})

    def test_retained_task_usage_marks_unreadable_and_partial(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'synthetic.jsonl'
            tokens = dict(input_tokens=90, output_tokens=10,
                          total_tokens=100, cached_input_tokens=0,
                          cache_write_input_tokens=0, reasoning_output_tokens=0)
            events = [dict(type='turn_context', payload=dict(model=None)),
                      dict(type='event_msg', timestamp='2026-10-01T12:00:00Z',
                           payload=dict(type='token_count', info=dict(
                               total_token_usage=tokens, last_token_usage=tokens)))]
            path.write_text('\n'.join(map(json.dumps, events)) + '\n', encoding='utf-8')
            store = CodexStore(directory)
            row = dict(id='t', rollout_path=str(path), model='old-model')
            first = store._task_context(row, {'activity_at': 1}, {})['presentation']
            self.assertEqual(first['tokens']['total_tokens'], 100)
            self.assertIsNone(first['model'])
            self.assertTrue(first['source_available'])
            self.assertFalse(first['partial'])
            path.unlink()
            retained = store._task_context(row, {'activity_at': 2}, {})['presentation']
            self.assertEqual(retained['tokens']['total_tokens'], 100)
            self.assertTrue(retained['available'])
            self.assertFalse(retained['source_available'])
            self.assertTrue(retained['partial'])
            self.assertIn('note_usage_source_unavailable', retained['notes'])

    def test_malformed_record_marks_partial_projection(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'synthetic.jsonl'
            path.write_text('{"type":"event_msg",BROKEN}\n', encoding='utf-8')
            result = CodexStore(directory)._task_context(
                dict(id='t', rollout_path=str(path)), {}, {})['presentation']
            self.assertTrue(result['source_available'])
            self.assertFalse(result['available'])
            self.assertTrue(result['partial'])
            self.assertIn('note_usage_record_invalid', result['notes'])

    def test_project_origin_label_excludes_url_secrets(self):
        origins = ['https://synthetic-user:synthetic-secret@example.invalid/org/repo.git?token=synthetic-private#secret',
                   'ssh://synthetic-user@example.invalid/org/repo.git?token=synthetic-private',
                   'git@example.invalid:org/repo.git#synthetic-private']
        for origin in origins:
            with self.subTest(origin=origin):
                self.assertEqual(project_identity(
                    dict(id='t', git_origin_url=origin), {})[0], 'repo')

    def test_configured_project_path_is_basename(self):
        for name in (r'D:\Sensitive\Project', '/synthetic/private/Project', 'Project',
                     'https://synthetic-user:synthetic-secret@example.invalid/Project?token=synthetic-private#private'):
            with self.subTest(name=name):
                state = {'local-projects': {'p': {'name': name}}}
                self.assertEqual(project_identity(
                    dict(id='t', project_id='p'), state)[0], 'Project')

    def test_malformed_context_window_cannot_break_task_projection(self):
        for value in (True, '100', -10, {}, float('nan')):
            with self.subTest(value=value):
                session = SessionUsage('synthetic.jsonl')
                session.consume(dict(type='event_msg', payload=dict(
                    type='token_count', info=dict(model_context_window=value,
                        total_token_usage={'total_tokens': 100},
                        last_token_usage={'total_tokens': 100}))))
                store = CodexStore('synthetic-home')
                store.sessions['synthetic.jsonl'] = session
                with patch.object(session, 'refresh'):
                    projection = store._task_context(dict(id='t',
                        rollout_path='synthetic.jsonl'), {}, {})['presentation']
                self.assertIsNone(projection['context'])


if __name__ == '__main__':
    unittest.main()
