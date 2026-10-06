from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from tests.test_codex_recap import RecapFixture, event
from usage import CodexStore, estimate_usd, task_history


def stamp(seconds):
    return datetime.fromtimestamp(seconds, timezone.utc).isoformat()


def token(total, at, last=None):
    def usage(value):
        output = min(10, value)
        return dict(input_tokens=value-output, output_tokens=output, total_tokens=value,
                    cached_input_tokens=0, cache_write_input_tokens=0, reasoning_output_tokens=0)
    return event('token_count', stamp(at), info=dict(total_token_usage=usage(total),
                 last_token_usage=usage(total if last is None else last), model_context_window=1000))


class HistoryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)
        self.fixture = RecapFixture(self.home)
        with closing(sqlite3.connect(self.fixture.db)) as connection:
            connection.execute('ALTER TABLE threads ADD COLUMN updated_at INTEGER DEFAULT 200')
            connection.commit()
        self.store = CodexStore(self.home)

    def add(self, thread='task', source='desktop', start=100, finish=120, total=100, model='gpt-5.6-sol'):
        events = [dict(type='turn_context', payload=dict(model=model))]
        if start is not None:
            events.append(event('task_started', stamp(start), turn_id='turn-' + thread))
        if total is not None:
            events.append(token(total, (start or 100) + 1))
        if finish is not None:
            events.append(event('task_complete', stamp(finish), turn_id='turn-' + thread))
        return self.fixture.add(thread, source, events, meta=dict(timestamp=stamp((start or 100)-1)))

    def test_top_level_sources_sorted_by_start_inclusive_cutoff(self):
        for i, source in enumerate(('desktop', 'vscode', 'cli', 'exec')):
            self.add(source, source, start=100 + i*10, finish=200)
        self.assertEqual([r['thread_id'] for r in self.store.task_history(110)], ['exec', 'cli', 'vscode'])
        self.assertEqual(len(self.store.task_history(100)), 4)
        self.assertEqual(self.store.task_history(300), [])

    def test_interface_and_existing_estimate(self):
        self.add()
        item = self.store.task_history(0)[0]
        self.assertEqual(set(item), {'thread_id', 'title', 'project', 'started_at', 'finished_at', 'total_tokens', 'usd'})
        self.assertEqual((item['thread_id'], item['title'], item['project']), ('task', 'Synthetic', 'Project'))
        self.assertEqual((item['started_at'], item['finished_at'], item['total_tokens']), (100, 120, 100))
        self.assertEqual(item['usd'], estimate_usd(token(100, 100)['payload']['info']['total_token_usage'], 'gpt-5.6-sol'))

    def test_archived_threads_are_retained_but_subagents_and_unknown_sources_are_not(self):
        self.add('old')
        self.add('subagent', '{"subagent":{"thread_spawn":{"parent_thread_id":"old"}}}')
        self.add('unknown', 'future-provider')
        with closing(sqlite3.connect(self.fixture.db)) as connection:
            connection.execute("UPDATE threads SET archived=1 WHERE id='old'")
            connection.commit()
        self.assertEqual([r['thread_id'] for r in self.store.task_history(0)], ['old'])

    def test_cumulative_duplicate_events_and_duplicate_database_rows_count_once(self):
        path = self.add()
        with path.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(token(100, 101)) + '\n')
            stream.write(json.dumps(token(200, 115, last=100)) + '\n')
        with closing(sqlite3.connect(self.fixture.db)) as connection:
            connection.execute("INSERT INTO threads SELECT * FROM threads WHERE id='task'")
            connection.commit()
        result = self.store.task_history(0)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['total_tokens'], 200)

    def test_conflicting_duplicate_identity_is_not_guessed(self):
        self.add()
        with closing(sqlite3.connect(self.fixture.db)) as connection:
            connection.execute("INSERT INTO threads SELECT id,source,cwd,'missing',title,name,project_id,archived,updated_at FROM threads")
            connection.commit()
        self.assertEqual(self.store.task_history(None), [])

    def test_fork_excludes_copied_parent_usage_even_outside_date_range(self):
        self.add('parent')
        self.fixture.add('child', 'cli', [dict(type='turn_context', payload=dict(model='gpt-5.6-sol')),
            event('task_started', stamp(100)), token(100, 101), event('task_complete', stamp(120)),
            event('task_started', stamp(160)), token(300, 170, last=200), event('task_complete', stamp(180))],
            meta=dict(forked_from_id='parent', timestamp=stamp(150)))
        result = self.store.task_history(150)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['thread_id'], 'child')
        self.assertEqual(result[0]['total_tokens'], 200)
        self.assertEqual((result[0]['started_at'], result[0]['finished_at']), (160, 180))

    def test_unknown_fork_boundary_does_not_count_parent_as_child(self):
        self.fixture.add(events=[dict(type='turn_context', payload=dict(model='gpt-5.6-sol')), token(100, 100)],
                         meta=dict(forked_from_id='parent', timestamp=None))
        item = self.store.task_history(None)[0]
        self.assertIsNone(item['total_tokens'])
        self.assertIsNone(item['usd'])

    def test_missing_and_unpriced_usage_are_none_not_zero(self):
        self.add('missing', total=None)
        self.add('unknown-model', model='unknown-model')
        result = {r['thread_id']: r for r in self.store.task_history(0)}
        self.assertIsNone(result['missing']['total_tokens'])
        self.assertIsNone(result['missing']['usd'])
        self.assertEqual(result['unknown-model']['total_tokens'], 100)
        self.assertIsNone(result['unknown-model']['usd'])

    def test_known_zero_is_preserved(self):
        self.add(total=0)
        item = self.store.task_history(0)[0]
        self.assertEqual((item['total_tokens'], item['usd']), (0, 0))

    def test_missing_cache_write_counters_do_not_fabricate_complete_cost(self):
        path = self.add()
        records = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
        for record in records:
            info = record.get('payload', {}).get('info')
            if info:
                for key in ('total_token_usage', 'last_token_usage'):
                    info[key].pop('cache_write_input_tokens')
        path.write_text(''.join(json.dumps(record) + '\n' for record in records), encoding='utf-8')
        item = self.store.task_history(0)[0]
        self.assertEqual(item['total_tokens'], 100)
        self.assertIsNone(item['usd'])

    def test_initial_carry_and_mixed_model_price_gaps_do_not_become_zero_cost(self):
        path = self.add('carry', total=None)
        with path.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(token(500, 110, last=100)) + '\n')
        path = self.add('mixed')
        with path.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(dict(type='turn_context', payload=dict(model='unknown-model'))) + '\n')
            stream.write(json.dumps(token(200, 115, last=100)) + '\n')
        result = {r['thread_id']: r for r in self.store.task_history(0)}
        self.assertEqual(result['carry']['total_tokens'], 500)
        self.assertIsNone(result['carry']['usd'])
        self.assertEqual(result['mixed']['total_tokens'], 200)
        self.assertIsNone(result['mixed']['usd'])

    def test_counter_reset_uses_existing_usage_accounting(self):
        path = self.add()
        with path.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(token(50, 115)) + '\n')
        self.assertEqual(self.store.task_history(0)[0]['total_tokens'], 150)

    def test_missing_counter_or_corrupt_record_does_not_show_partial_total_as_complete(self):
        path = self.add()
        with path.open('a', encoding='utf-8') as stream:
            stream.write('{"type":"event_msg",BROKEN}\n')
        item = self.store.task_history(None)[0]
        self.assertIsNone(item['total_tokens'])
        self.assertIsNone(item['usd'])
        self.assertIsNone(item['finished_at'])

    def test_partial_tail_and_disappearing_source_do_not_use_old_numbers(self):
        path = self.add()
        self.assertEqual(self.store.task_history(0)[0]['total_tokens'], 100)
        with path.open('a', encoding='utf-8') as stream:
            stream.write('{"type":"event_msg"')
        self.assertIsNone(self.store.task_history(None)[0]['total_tokens'])
        path.unlink()
        item = self.store.task_history(None)[0]
        self.assertIsNone(item['total_tokens'])
        self.assertIsNone(item['finished_at'])

    def test_running_thread_has_no_guessed_finish(self):
        self.add(finish=None)
        self.assertIsNone(self.store.task_history(0)[0]['finished_at'])

    def test_unknown_start_only_appears_in_unfiltered_history_last(self):
        self.add('unknown', start=None)
        self.add('known')
        self.assertEqual([r['thread_id'] for r in self.store.task_history(0)], ['known'])
        result = self.store.task_history(None)
        self.assertEqual([r['thread_id'] for r in result], ['known', 'unknown'])
        self.assertIsNone(result[-1]['started_at'])

    def test_metadata_project_name_and_title_first_line(self):
        self.add()
        with closing(sqlite3.connect(self.fixture.db)) as connection:
            connection.execute("UPDATE threads SET title='First line\nprivate details',project_id='p'")
            connection.commit()
        (self.home/'.codex-global-state.json').write_text(json.dumps(
            {'local-projects': {'p': {'name': 'Sample Project'}}}), encoding='utf-8')
        item = self.store.task_history(0)[0]
        self.assertEqual((item['title'], item['project']), ('First line', 'Sample Project'))

    def test_absent_project_and_title_remain_none(self):
        self.fixture.add(cwd='', title='', events=[event('task_started'), event('task_complete', 120)])
        item = self.store.task_history(0)[0]
        self.assertIsNone(item['project'])
        self.assertIsNone(item['title'])

    def test_missing_and_unknown_schema_fail_closed(self):
        self.fixture.db.unlink()
        self.assertEqual(self.store.task_history(0), [])
        self.assertFalse(self.fixture.db.exists())
        with closing(sqlite3.connect(self.fixture.db)) as connection:
            connection.execute('CREATE TABLE threads (id INTEGER, source TEXT)')
            connection.commit()
        self.assertEqual(self.store.task_history(0), [])

    def test_module_wrapper_respects_isolated_codex_home(self):
        self.add()
        with patch.dict(os.environ, {'CODEX_HOME': str(self.home)}):
            self.assertEqual(task_history(0), self.store.task_history(0))

    def test_invalid_cutoffs_are_rejected(self):
        for since in (True, -1, 'today', float('inf'), float('nan'), {}):
            with self.assertRaises(ValueError):
                self.store.task_history(since)

    def test_readonly_reporting_preserves_live_statistics_and_caches(self):
        self.add()
        before = self.store.read(scope='global')
        files = list(self.home.iterdir())
        hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
        sessions = dict(self.store.sessions)
        with patch.object(self.store.approval, 'read', side_effect=AssertionError('history must not query app-server')):
            self.assertEqual(self.store.task_history(0)[0]['total_tokens'], 100)
        self.assertEqual(self.store.sessions, sessions)
        self.assertEqual(hashes, {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in self.home.iterdir()})
        after = self.store.read(scope='global')
        for key in ('tokens', 'usd', 'context', 'active_tasks'):
            self.assertEqual(before[key], after[key])


if __name__ == '__main__':
    unittest.main()
