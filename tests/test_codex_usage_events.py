from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from tests.test_codex_recap import RecapFixture, event
from tests.test_codex_history import stamp, token
from usage import CodexStore, SessionUsage, unique_records, usage_events


class UsageEventsTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)
        self.fixture = RecapFixture(self.home)
        self.store = CodexStore(self.home)

    def add(self, key='task', source='desktop', events=None, model='gpt-5.6-sol', meta=None, cwd='D:/Project'):
        return self.fixture.add(key, source, [dict(type='turn_context', payload=dict(model=model)),
            *(events if events is not None else [token(100, 101)])],
            meta=dict(timestamp=stamp(90), **(meta or {})), cwd=cwd)

    def append(self, path, record):
        with path.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(record) + '\n')

    def test_public_contract_and_existing_price_are_identical(self):
        path = self.add()
        session = SessionUsage(path)
        session.refresh()
        result = self.store.usage_events(0)
        self.assertEqual(len(result), 1)
        self.assertEqual(set(result[0]), {'at', 'thread_id', 'project', 'model', 'total_tokens', 'usd'})
        self.assertEqual(result[0], dict(at=101., thread_id='task', project='Project',
            model='gpt-5.6-sol', total_tokens=100, usd=session.records[0]['usd']))

    def test_cutoff_inclusive_sorted_and_all_top_level_sources(self):
        for index, source in enumerate(('exec', 'cli', 'vscode', 'desktop')):
            self.add(source, source, [token(100, 104-index)])
        self.assertEqual([r['thread_id'] for r in self.store.usage_events(102)], ['vscode', 'cli', 'exec'])
        self.assertEqual(self.store.usage_events(105), [])

    def test_duplicates_and_counter_reset_reuse_existing_deltas(self):
        samples = [token(100, 101), token(100, 101), token(200, 102, last=100), token(40, 103)]
        path = self.add(events=samples)
        with closing(sqlite3.connect(self.fixture.db)) as connection:
            connection.execute('INSERT INTO threads SELECT * FROM threads')
            connection.commit()
        session = SessionUsage(path)
        session.refresh()
        records = unique_records([session])
        output = self.store.usage_events(None)
        self.assertEqual([r['total_tokens'] for r in output], [100, 100, 40])
        self.assertEqual([r['usd'] for r in output], [r['usd'] for r in records])

    def test_fork_inheritance_is_not_counted_again(self):
        self.add('parent', events=[token(100, 101)])
        self.fixture.add('child', events=[dict(type='turn_context', payload=dict(model='gpt-5.6-sol')),
            token(100, 101), token(180, 160, last=80)],
            meta=dict(timestamp=stamp(150), forked_from_id='parent'))
        result = self.store.usage_events(None)
        self.assertEqual([(r['thread_id'], r['total_tokens']) for r in result], [('parent', 100), ('child', 80)])

    def test_ancestor_event_ids_are_excluded_even_after_fork_boundary(self):
        self.add('parent', events=[token(100, 101)])
        self.fixture.add('child', events=[dict(type='turn_context', payload=dict(model='gpt-5.6-sol')),
            token(100, 101), token(180, 160, last=80)],
            meta=dict(timestamp=stamp(90), forked_from_id='parent'))
        self.assertEqual(sum(r['total_tokens'] for r in self.store.usage_events(None)), 180)

    def test_multiple_files_for_same_thread_use_most_complete_session(self):
        original = self.add()
        copy = self.home/'copy.jsonl'
        copy.write_bytes(original.read_bytes())
        self.append(copy, token(200, 102, last=100))
        with closing(sqlite3.connect(self.fixture.db)) as connection:
            connection.execute('INSERT INTO threads SELECT id,source,cwd,?,title,name,project_id,archived FROM threads',
                               (str(copy),))
            connection.commit()
        self.assertEqual([r['total_tokens'] for r in self.store.usage_events(0)], [100, 100])

    def test_conflicting_project_metadata_is_not_guessed(self):
        self.add()
        with closing(sqlite3.connect(self.fixture.db)) as connection:
            connection.execute("INSERT INTO threads SELECT id,source,'D:/Different',rollout_path,title,name,project_id,archived FROM threads")
            connection.execute("INSERT INTO threads SELECT * FROM threads WHERE cwd='D:/Project'")
            connection.commit()
        result = self.store.usage_events(0)
        self.assertEqual(len(result), 1)
        self.assertIsNone(result[0]['project'])

    def test_archived_and_independent_subagent_usage_are_included(self):
        self.add('parent')
        self.add('child', '{"subagent":{"thread_spawn":{"parent_thread_id":"parent"}}}', [token(50, 102)])
        with closing(sqlite3.connect(self.fixture.db)) as connection:
            connection.execute("UPDATE threads SET archived=1 WHERE id='parent'")
            connection.commit()
        self.assertEqual(sum(r['total_tokens'] for r in self.store.usage_events(0)), 150)

    def test_unknown_carry_is_none_and_excluded_from_dated_queries(self):
        self.add(events=[token(100, 101, last=40)])
        result = self.store.usage_events(None)
        self.assertEqual([r['total_tokens'] for r in result], [40, 60])
        self.assertIsNone(result[-1]['at'])
        self.assertIsNone(result[-1]['model'])
        self.assertIsNone(result[-1]['usd'])
        self.assertEqual(len(self.store.usage_events(0)), 1)

    def test_unknown_model_and_total_stay_none(self):
        sample = token(100, 101)
        for kind in ('total_token_usage', 'last_token_usage'):
            del sample['payload']['info'][kind]['total_tokens']
            del sample['payload']['info'][kind]['input_tokens']
        self.add(events=[sample], model='unknown-model')
        result = self.store.usage_events(0)
        self.assertEqual(len(result), 1)
        self.assertIsNone(result[0]['total_tokens'])
        self.assertIsNone(result[0]['usd'])

    def test_missing_total_with_known_breakdown_keeps_existing_derivation(self):
        sample = token(100, 101)
        for key in ('total_token_usage', 'last_token_usage'):
            del sample['payload']['info'][key]['total_tokens']
        self.add(events=[sample])
        self.assertEqual(self.store.usage_events(0)[0]['total_tokens'], 100)

    def test_unknown_cache_write_count_is_not_treated_as_zero_cost(self):
        sample = token(100, 101)
        for key in ('total_token_usage', 'last_token_usage'):
            del sample['payload']['info'][key]['cache_write_input_tokens']
        self.add(events=[sample])
        result = self.store.usage_events(0)[0]
        self.assertEqual(result['total_tokens'], 100)
        self.assertIsNone(result['usd'])

    def test_tier_and_cache_prices_are_the_existing_record_prices(self):
        sample = token(100, 101)
        for key in ('total_token_usage', 'last_token_usage'):
            sample['payload']['info'][key]['cached_input_tokens'] = 50
        path = self.fixture.add(events=[dict(type='turn_context', payload=dict(
            model='gpt-5.6-sol', service_tier='priority')), sample], meta=dict(timestamp=stamp(90)))
        session = SessionUsage(path)
        session.refresh()
        self.assertEqual(self.store.usage_events(0)[0]['usd'], session.records[0]['usd'])

    def test_unrecognized_counter_record_is_not_zero(self):
        self.add(events=[event('token_count', stamp(101), info={'future_counters': {}})])
        result = self.store.usage_events(0)
        self.assertEqual(len(result), 1)
        self.assertIsNone(result[0]['total_tokens'])
        self.assertIsNone(result[0]['usd'])

    def test_unknown_project_stays_none(self):
        self.add(cwd='')
        self.assertIsNone(self.store.usage_events(0)[0]['project'])

    def test_project_assignment_is_refreshed_without_changing_usage(self):
        self.add()
        before = self.store.usage_events(0)[0]
        (self.home/'.codex-global-state.json').write_text(json.dumps({
            'thread-project-assignments': {'task': {'projectId': 'p'}},
            'local-projects': {'p': {'name': 'Assigned'}}}), encoding='utf-8')
        after = self.store.usage_events(0)[0]
        self.assertEqual(after['project'], 'Assigned')
        self.assertEqual(after['total_tokens'], before['total_tokens'])
        self.assertEqual(after['usd'], before['usd'])

    def test_missing_files_do_not_return_cached_usage(self):
        path = self.add()
        self.assertEqual(len(self.store.usage_events(0)), 1)
        path.unlink()
        self.assertEqual(self.store.usage_events(0), [])
        self.fixture.db.unlink()
        self.assertEqual(self.store.usage_events(0), [])
        self.assertFalse(self.fixture.db.exists())

    def test_invalid_identity_and_unknown_fork_boundary_are_excluded(self):
        self.add(meta={'id': 'other'})
        self.fixture.add('child', events=[token(100, 101)], meta={'forked_from_id': 'parent', 'timestamp': None})
        self.assertEqual(self.store.usage_events(None), [])

    def test_unknown_sqlite_schema_has_no_invented_events(self):
        with closing(sqlite3.connect(self.fixture.db)) as connection:
            connection.execute('DROP TABLE threads')
            connection.execute('CREATE TABLE threads (id INTEGER, rollout_path TEXT)')
            connection.commit()
        self.assertEqual(self.store.usage_events(None), [])

    def test_truncated_file_without_metadata_does_not_reuse_cached_identity(self):
        path = self.add()
        self.assertEqual(len(self.store.usage_events(0)), 1)
        path.write_text(json.dumps(token(50, 102)) + '\n', encoding='utf-8')
        self.assertEqual(self.store.usage_events(0), [])

    def test_incremental_append_and_same_size_rewrite(self):
        path = self.add()
        self.store.usage_events(0)
        self.append(path, token(200, 102, last=100))
        self.assertEqual([r['total_tokens'] for r in self.store.usage_events(0)], [100, 100])
        data = path.read_text(encoding='utf-8').replace('200', '300')
        path.write_text(data, encoding='utf-8')
        self.assertEqual([r['total_tokens'] for r in self.store.usage_events(0)], [100, 200])

    def test_partial_tail_returns_only_completed_records_then_recovers(self):
        path = self.add()
        record = json.dumps(token(200, 102, last=100))
        with path.open('a', encoding='utf-8') as stream:
            stream.write(record[:20])
        self.assertEqual(len(self.store.usage_events(0)), 1)
        with path.open('a', encoding='utf-8') as stream:
            stream.write(record[20:] + '\n')
        self.assertEqual(len(self.store.usage_events(0)), 2)

    def test_readonly_and_no_approval_or_scope_polling(self):
        self.add()
        before = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.home.iterdir()}
        with patch.object(self.store.approval, 'read', side_effect=AssertionError('Must not poll')):
            with patch.object(self.store, 'read', side_effect=AssertionError('Must not poll')):
                self.store.usage_events(0)
        self.assertEqual({p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.home.iterdir()}, before)
        self.assertEqual(self.store.sessions, {})
        self.assertEqual(self.store._scope_sessions, ())

    def test_module_wrapper_uses_codex_home(self):
        self.add()
        with patch.dict('os.environ', {'CODEX_HOME': str(self.home)}):
            self.assertEqual(usage_events(0), self.store.usage_events(0))

    def test_invalid_cutoffs_raise_value_error(self):
        for value in (True, -1, float('nan'), float('inf'), '101', 10**400):
            with self.assertRaises(ValueError):
                self.store.usage_events(value)


if __name__ == '__main__':
    unittest.main()
