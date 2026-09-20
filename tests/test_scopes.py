import json
import os
import sqlite3
import tempfile
import time
import unittest
from contextlib import closing
from pathlib import Path

from usage import CodexStore


MISSING = object()


class ScopeFixture:
    def __init__(self, root):
        self.home = Path(root)
        self.rows = []
        self.projects = {}
        self.assignments = {}

    def add(self, thread, name, total, project_id=None, project_name=None,
            *, working=False, cached=0, cache_write=MISSING, duplicate=False,
            mtime=None, cwd='', origin='', file_tag=''):
        path = self.home / f'{thread}{file_tag}.jsonl'
        usage = dict(input_tokens=total-10, cached_input_tokens=cached,
                     output_tokens=10, reasoning_output_tokens=0, total_tokens=total)
        if cache_write is not MISSING:
            usage['cache_write_input_tokens'] = cache_write
        events = [
            dict(type='session_meta', payload=dict(id=thread, timestamp='2026-09-19T12:00:00Z')),
            dict(type='turn_context', payload=dict(model='gpt-6-astra', effort='high')),
        ]
        if working:
            events.append(dict(type='event_msg', timestamp='2026-09-19T12:00:01Z',
                               payload=dict(type='task_started')))
        token = dict(type='event_msg', timestamp='2026-09-19T12:00:02Z', payload=dict(
            type='token_count', info=dict(total_token_usage=usage, last_token_usage=usage,
                                          model_context_window=1000)))
        events.append(token)
        if duplicate:
            events.append(token)
        path.write_text(''.join(json.dumps(event)+'\n' for event in events), encoding='utf-8')
        stamp = time.time() if mtime is None else mtime
        os.utime(path, (stamp, stamp))
        self.rows.append(dict(id=thread, name=name, title='', cwd=cwd, rollout_path=str(path),
            model='gpt-6-astra', reasoning_effort='high', source='desktop', project_id=project_id,
            git_origin_url=origin, updated_at=int(stamp), archived=0))
        if project_id:
            self.assignments[thread] = {'projectId': project_id}
            self.projects.setdefault(project_id, {'name': project_name} if project_name else {})

    def add_fork(self, thread, parent, project_id, project_name, inherited_total, total):
        path = self.home / f'{thread}.jsonl'
        inherited = dict(input_tokens=inherited_total-10, cached_input_tokens=0,
                         output_tokens=10, reasoning_output_tokens=0, total_tokens=inherited_total)
        current = dict(input_tokens=total-10, cached_input_tokens=0,
                       output_tokens=10, reasoning_output_tokens=0, total_tokens=total)
        added = dict(input_tokens=total-inherited_total, cached_input_tokens=0,
                     output_tokens=0, reasoning_output_tokens=0, total_tokens=total-inherited_total)
        events = [
            dict(type='session_meta', payload=dict(id=thread, forked_from_id=parent,
                                                   timestamp='2026-09-19T12:00:10Z')),
            dict(type='turn_context', payload=dict(model='gpt-6-astra', effort='high')),
            dict(type='event_msg', timestamp='2026-09-19T12:00:02Z', payload=dict(
                type='token_count', info=dict(total_token_usage=inherited, last_token_usage=inherited))),
            dict(type='event_msg', timestamp='2026-09-19T12:00:11Z', payload=dict(
                type='token_count', info=dict(total_token_usage=current, last_token_usage=added))),
        ]
        path.write_text(''.join(json.dumps(event)+'\n' for event in events), encoding='utf-8')
        stamp = time.time()
        self.rows.append(dict(id=thread, name='Fork', title='', cwd='', rollout_path=str(path),
            model='gpt-6-astra', reasoning_effort='high', source='desktop', project_id=project_id,
            git_origin_url='', updated_at=int(stamp), archived=0))
        self.assignments[thread] = {'projectId': project_id}
        self.projects.setdefault(project_id, {'name': project_name})

    def finish(self):
        with closing(sqlite3.connect(self.home/'state_1.sqlite')) as db:
            db.execute('''create table threads (
                id text, name text, title text, cwd text, rollout_path text, model text,
                reasoning_effort text, source text, project_id text, git_origin_url text,
                updated_at integer, archived integer)''')
            for row in self.rows:
                db.execute('insert into threads values (?,?,?,?,?,?,?,?,?,?,?,?)', tuple(row.values()))
            db.commit()
        state = {'local-projects': self.projects, 'thread-project-assignments': self.assignments}
        (self.home/'.codex-global-state.json').write_text(json.dumps(state), encoding='utf-8')
        return CodexStore(self.home)


class ScopeTests(unittest.TestCase):
    def test_global_aggregates_multiple_projects(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = ScopeFixture(directory)
            fixture.add('a', 'A', 100, 'p-a', 'Alpha')
            fixture.add('b', 'B', 200, 'p-b', 'Beta')
            data = fixture.finish().read(scope='global')
        self.assertEqual(data['scope_identity'], {'scope_type': 'global', 'locally_recorded': True})
        self.assertEqual((data['tokens']['total_tokens'], data['count']), (300, 2))

    def test_project_contains_only_its_multiple_conversations(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = ScopeFixture(directory)
            fixture.add('a1', 'A1', 100, 'p-a', 'Alpha')
            fixture.add('a2', 'A2', 150, 'p-a', 'Alpha')
            fixture.add('b', 'B', 200, 'p-b', 'Beta')
            data = fixture.finish().read(pinned='a1', scope='project')
        self.assertEqual(data['scope_identity']['project_id'], 'p-a')
        self.assertEqual(data['scope_identity']['project_name'], 'Alpha')
        self.assertEqual((data['tokens']['total_tokens'], data['count']), (250, 2))

    def test_conversation_contains_exact_selected_thread(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = ScopeFixture(directory)
            fixture.add('a1', 'A1', 100, 'p-a', 'Alpha')
            fixture.add('a2', 'A2', 150, 'p-a', 'Alpha')
            data = fixture.finish().read(pinned='a2', scope='conversation')
        self.assertEqual(data['scope_identity']['thread_id'], 'a2')
        self.assertEqual(data['scope_identity']['conversation_title'], 'A2')
        self.assertEqual((data['tokens']['total_tokens'], data['count']), (150, 1))

    def test_duplicate_underlying_events_are_counted_once(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = ScopeFixture(directory)
            fixture.add('a', 'A', 100, 'p-a', 'Alpha', duplicate=True)
            data = fixture.finish().read(scope='global')
        self.assertEqual(data['tokens']['total_tokens'], 100)
        self.assertEqual(data['analytics']['events'], 1)

    def test_duplicate_session_files_use_the_most_complete_copy_once(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = ScopeFixture(directory); now = time.time()
            fixture.add('a', 'A', 100, 'p-a', 'Alpha', file_tag='-old', mtime=now-1)
            fixture.add('a', 'A', 150, 'p-a', 'Alpha', file_tag='-new', mtime=now)
            data = fixture.finish().read(scope='global')
        self.assertEqual(data['tokens']['total_tokens'], 150)
        self.assertEqual((data['count'], data['analytics']['events']), (1, 1))

    def test_fork_inheritance_is_excluded_at_global_and_conversation_scopes(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = ScopeFixture(directory)
            fixture.add('parent', 'Parent', 100, 'p-a', 'Alpha')
            fixture.add_fork('child', 'parent', 'p-a', 'Alpha', 100, 150)
            store = fixture.finish()
            global_data = store.read(scope='global')
            child_data = store.read(pinned='child', scope='conversation')
        self.assertEqual(global_data['tokens']['total_tokens'], 150)
        self.assertEqual(child_data['tokens']['total_tokens'], 50)

    def test_nullable_fields_remain_unknown_across_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = ScopeFixture(directory)
            fixture.add('a', 'A', 100, 'p-a', 'Alpha', cache_write=5)
            fixture.add('b', 'B', 200, 'p-b', 'Beta')
            data = fixture.finish().read(scope='global')
        self.assertIsNone(data['tokens']['cache_write_input_tokens'])
        self.assertEqual(data['analytics']['known']['cache_write_input_tokens'], 5)
        self.assertEqual(data['analytics']['coverage']['cache_write_input_tokens'], 1)

    def test_switching_scope_changes_identity_and_values_together(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = ScopeFixture(directory)
            fixture.add('a', 'A', 100, 'p-a', 'Alpha')
            fixture.add('b', 'B', 200, 'p-b', 'Beta')
            store = fixture.finish()
            project = store.read(pinned='a', scope='project')
            conversation = store.read(pinned='b', scope='conversation')
        self.assertEqual((project['scope_identity']['project_name'], project['tokens']['total_tokens']),
                         ('Alpha', 100))
        self.assertEqual((conversation['scope_identity']['conversation_title'],
                          conversation['tokens']['total_tokens']), ('B', 200))

    def test_missing_conversation_does_not_fall_back_to_unrelated_data(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = ScopeFixture(directory)
            fixture.add('a', 'A', 100, 'p-a', 'Alpha')
            data = fixture.finish().read(pinned='deleted', scope='conversation')
        self.assertEqual(data['scope_identity'], {
            'scope_type': 'conversation', 'thread_id': 'deleted', 'unavailable': True})
        self.assertNotIn('tokens', data)
        self.assertTrue(data['status'])

    def test_analytics_scope_does_not_change_active_working_context(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = ScopeFixture(directory); now = time.time()
            fixture.add('a', 'Working A', 100, 'p-a', 'Alpha', working=True, mtime=now)
            fixture.add('b', 'Inspect B', 200, 'p-b', 'Beta', working=True, mtime=now-1)
            store = fixture.finish()
            global_data = store.read('Working A', scope='global', activity_detection_valid=True)
            project_data = store.read('Working A', pinned='b', scope='project',
                                      activity_detection_valid=True)
        self.assertEqual(global_data['working_context']['thread'], 'a')
        self.assertEqual(project_data['working_context']['thread'], 'a')
        self.assertEqual(project_data['scope_identity']['project_name'], 'Beta')
        self.assertEqual(project_data['tokens']['total_tokens'], 200)

    def test_same_display_names_do_not_merge_distinct_project_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = ScopeFixture(directory)
            fixture.add('a', 'Task', 100, 'p-a', 'Shared')
            fixture.add('b', 'Task', 200, 'p-b', 'Shared')
            store = fixture.finish()
            first = store.read(pinned='a', scope='project')
            second = store.read(pinned='b', scope='project')
        self.assertEqual((first['scope_identity']['project_id'], first['tokens']['total_tokens']),
                         ('p-a', 100))
        self.assertEqual((second['scope_identity']['project_id'], second['tokens']['total_tokens']),
                         ('p-b', 200))


if __name__ == '__main__':
    unittest.main()
