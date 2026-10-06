import json
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import codex_recap
from codex_recap import epoch, recap, thread_rows


def event(kind, at=100, **fields):
    return dict(type='event_msg', timestamp=at, payload=dict(type=kind, **fields))


class RecapFixture:
    def __init__(self, home):
        self.home = Path(home)
        self.db = self.home/'state_5.sqlite'
        with closing(sqlite3.connect(self.db)) as connection:
            connection.execute('CREATE TABLE threads (id TEXT, source TEXT, cwd TEXT, '
                               'rollout_path TEXT, title TEXT, name TEXT, project_id TEXT, archived INTEGER)')
            connection.commit()

    def add(self, thread='task', source='desktop', events=(), cwd='D:/Project', meta=None, title='Synthetic'):
        path = self.home/(thread + '.jsonl')
        metadata = dict(id=thread, timestamp=90, cwd=cwd)
        metadata.update(meta or {})
        records = [dict(type='session_meta', payload=metadata), *events]
        path.write_text(''.join(json.dumps(row) + '\n' for row in records), encoding='utf-8')
        with closing(sqlite3.connect(self.db)) as connection:
            connection.execute('INSERT INTO threads (id,source,cwd,rollout_path,title,name,project_id,archived) VALUES (?,?,?,?,?,?,?,?)',
                               (thread, source, cwd, str(path), title, None, None, 0))
            connection.commit()
        return path

    def ledger(self, rows):
        with closing(sqlite3.connect(self.home/'thread_history_1.sqlite')) as connection:
            connection.execute('CREATE TABLE thread_turns (thread_id TEXT, turn_id TEXT, '
                               'status TEXT, started_at INTEGER, completed_at INTEGER, rollout_ordinal INTEGER)')
            connection.executemany('INSERT INTO thread_turns VALUES (?,?,?,?,?,?)', rows)
            connection.commit()


class RecapTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)
        self.fixture = RecapFixture(self.home)

    def test_desktop_vscode_cli_and_exec_times(self):
        for source in ('desktop', 'vscode', 'cli', 'exec'):
            self.fixture.add(source, source, [event('task_started', started_at=101, turn_id='a'),
                event('task_complete', 120, completed_at=119, turn_id='a')])
            self.assertEqual(recap(self.home, source), dict(files=None, started_at=101.,
                                                          finished_at=119., duration_s=18.))

    def test_successful_structured_edits_are_relative_sorted_and_deduplicated(self):
        changes = {'D:/Project/z.py': {'type': 'add', 'content': 'DO NOT EXPORT'},
                   'src/old.py': {'type': 'update', 'move_path': 'src/new.py', 'unified_diff': 'PRIVATE'},
                   'gone.py': {'type': 'delete', 'content': 'PRIVATE'}}
        self.fixture.add(events=[event('task_started', turn_id='a'),
            event('patch_apply_end', 105, success=True, changes=changes),
            event('patch_apply_end', 106, success=True, changes=changes),
            event('task_complete', 120, turn_id='a')])
        result = recap(self.home, 'task')
        self.assertEqual(result['files'], ['gone.py', 'src/new.py', 'src/old.py', 'z.py'])
        self.assertEqual(result['duration_s'], 20)
        self.assertNotIn('PRIVATE', json.dumps(result))

    def test_paginated_completed_file_change(self):
        self.fixture.add(events=[event('item_completed', item=dict(type='FileChange',
            status='completed', changes={'a.py': {'type': 'update'}}))])
        self.assertEqual(recap(self.home, 'task')['files'], ['a.py'])

    def test_file_change_windows_extended_drive_paths(self):
        for index, (root, cwd, path) in enumerate([
            (r'\\?\D:\Project', r'D:\Project', r'D:\Project\a.py'),
            (r'D:\Project', r'\\?\D:\Project', r'\\?\D:\Project\a.py'),
            (r'\\?\D:\Project', r'\\?\D:\Project\src', 'a.py'),
        ]):
            with self.subTest(root=root, cwd=cwd, path=path):
                thread = 'drive-' + str(index)
                self.fixture.add(thread, cwd=root, events=[
                    dict(type='turn_context', payload=dict(cwd=cwd)),
                    event('item_completed', item=dict(type='FileChange', status='completed',
                        changes={path: {'type': 'update'}, r'E:\outside.py': {'type': 'add'},
                                 r'D:\Project-other\outside.py': {'type': 'add'}}))])
                expected = ['src/a.py'] if index == 2 else ['a.py']
                self.assertEqual(recap(self.home, thread)['files'], expected)

    def test_file_change_windows_extended_unc_paths(self):
        for index, (root, cwd, path) in enumerate([
            (r'\\?\UNC\server\share\Project', r'\\server\share\Project',
             r'\\server\share\Project\a.py'),
            (r'\\server\share\Project', r'\\?\UNC\server\share\Project',
             r'\\?\UNC\server\share\Project\a.py'),
            (r'\\?\unc\server\share\Project', r'\\?\UNC\server\share\Project\src', 'a.py'),
        ]):
            with self.subTest(root=root, cwd=cwd, path=path):
                thread = 'unc-' + str(index)
                self.fixture.add(thread, cwd=root, events=[
                    dict(type='turn_context', payload=dict(cwd=cwd)),
                    event('item_completed', item=dict(type='FileChange', status='completed',
                        changes={path: {'type': 'update'},
                                 r'\\?\UNC\server\other\Project\outside.py': {'type': 'add'},
                                 r'\\other\share\Project\outside.py': {'type': 'add'},
                                 r'..\..\outside.py': {'type': 'add'}}))])
                expected = ['src/a.py'] if index == 2 else ['a.py']
                self.assertEqual(recap(self.home, thread)['files'], expected)

    def test_failed_declined_and_proposed_changes_are_not_modifications(self):
        changes = {'a.py': {'type': 'add'}}
        self.fixture.add(events=[event('patch_apply_begin', changes=changes),
            event('patch_apply_end', success=False, changes=changes),
            event('patch_apply_end', success=True, status='declined', changes=changes),
            event('item_completed', item=dict(type='FileChange', status='failed', changes=changes))])
        self.assertIsNone(recap(self.home, 'task')['files'])

    def test_tool_success_summary_requires_matching_apply_patch_call(self):
        self.fixture.add(events=[dict(type='response_item', payload=dict(type='custom_tool_call',
            name='apply_patch', call_id='p', input='PRIVATE PATCH')),
            dict(type='response_item', payload=dict(type='custom_tool_call_output', call_id='p',
            output='Success. Updated the following files:\nM a.py\nA b.py\n'))])
        self.assertEqual(recap(self.home, 'task')['files'], ['a.py', 'b.py'])

    def test_assistant_text_shell_command_and_unpaired_output_are_not_evidence(self):
        self.fixture.add(events=[dict(type='response_item', payload=dict(type='function_call',
            name='exec_command', call_id='p', arguments='touch a.py')),
            dict(type='response_item', payload=dict(type='function_call_output', call_id='p',
            output='Success. Updated the following files:\nA a.py\n'))])
        self.assertIsNone(recap(self.home, 'task')['files'])

    def test_changed_cwd_and_paths_outside_project(self):
        self.fixture.add(events=[dict(type='turn_context', payload=dict(cwd='D:/Project/src')),
            event('patch_apply_end', success=True, changes={
                'a.py': {'type': 'add'}, '../../outside.py': {'type': 'add'},
                'E:/other.py': {'type': 'add'}, 'D:/Project-other/a.py': {'type': 'add'}})])
        self.assertEqual(recap(self.home, 'task')['files'], ['src/a.py'])

    def test_posix_paths_deleted_files_need_not_exist(self):
        self.fixture.add(cwd='/project', events=[event('patch_apply_end', success=True,
            changes={'/project/removed.py': {'type': 'delete'}})])
        self.assertEqual(recap(self.home, 'task')['files'], ['removed.py'])

    def test_explicit_empty_patch_list_is_empty_not_unknown(self):
        self.fixture.add(events=[event('patch_apply_end', success=True, changes={})])
        self.assertEqual(recap(self.home, 'task')['files'], [])

    def test_missing_project_is_unknown(self):
        self.fixture.add(cwd='', events=[event('patch_apply_end', success=True,
                                             changes={'a.py': {'type': 'add'}})])
        self.assertIsNone(recap(self.home, 'task')['files'])

    def test_multiple_turns_use_first_start_and_last_finish(self):
        self.fixture.add(events=[event('task_started', turn_id='a'), event('task_complete', 120, turn_id='a'),
            event('turn_started', 200, turn_id='b'), event('turn_complete', 240, turn_id='b', duration_ms=40000)])
        result = recap(self.home, 'task')
        self.assertEqual((result['started_at'], result['finished_at'], result['duration_s']), (100, 240, 140))

    def test_running_last_turn_does_not_use_previous_finish(self):
        self.fixture.add(events=[event('task_started', turn_id='a'), event('task_complete', 120, turn_id='a'),
            event('task_started', 200, turn_id='b'), event('task_complete', 220, turn_id='other')])
        result = recap(self.home, 'task')
        self.assertEqual(result['started_at'], 100)
        self.assertIsNone(result['finished_at'])
        self.assertIsNone(result['duration_s'])

    def test_aborted_thread_has_explicit_terminal_time(self):
        self.fixture.add(events=[event('task_started', turn_id='a'), event('turn_aborted', 110, turn_id='a')])
        self.assertEqual(recap(self.home, 'task')['finished_at'], 110)

    def test_missing_start_is_not_session_creation_or_duration_guess(self):
        self.fixture.add(events=[event('task_complete', 120, duration_ms=20000)])
        result = recap(self.home, 'task')
        self.assertIsNone(result['started_at'])
        self.assertEqual(result['finished_at'], 120)
        self.assertIsNone(result['duration_s'])

    def test_completion_can_carry_explicit_start(self):
        self.fixture.add(events=[event('task_complete', 120, started_at=100, completed_at=118)])
        self.assertEqual(recap(self.home, 'task')['duration_s'], 18)

    def test_invalid_or_reversed_times_remain_unknown(self):
        self.fixture.add(events=[event('task_started', at=None, started_at=True), event('task_complete', 120)])
        self.assertIsNone(recap(self.home, 'task')['started_at'])
        self.fixture.add('reverse', events=[event('task_started', 200), event('task_complete', 100)])
        self.assertIsNone(recap(self.home, 'reverse')['finished_at'])
        self.assertIsNone(epoch('2026-10-06T00:00:00'))
        self.assertIsNone(epoch(float('nan')))
        self.assertEqual(epoch('2026-10-06T00:00:00Z'), 1791244800.)

    def test_fork_does_not_include_inherited_times_or_edits(self):
        self.fixture.add(meta=dict(forked_from_id='parent', timestamp=150), events=[
            event('task_started', 100), event('patch_apply_end', 110, success=True,
                changes={'inherited.py': {'type': 'add'}}), event('task_complete', 120),
            event('task_started', 160), event('patch_apply_end', 170, success=True,
                changes={'own.py': {'type': 'add'}}), event('task_complete', 180)])
        self.assertEqual(recap(self.home, 'task'),
                         dict(files=['own.py'], started_at=160, finished_at=180, duration_s=20))

    def test_unknown_fork_boundary_and_wrong_thread_fail_closed(self):
        for name, meta in [('fork', dict(forked_from_id='parent', timestamp=None)),
                           ('wrong', dict(id='different'))]:
            self.fixture.add(name, meta=meta, events=[event('task_started'), event('task_complete', 120)])
            self.assertEqual(recap(self.home, name),
                             dict(files=None, started_at=None, finished_at=None, duration_s=None))

    def test_corruption_and_partial_tail_do_not_reuse_terminal_state(self):
        for suffix in ('{bad}\n', '{"type":"event_msg"'):
            path = self.fixture.add('bad' + str(len(suffix)), events=[event('task_started'), event('task_complete', 120)])
            with path.open('a', encoding='utf-8') as stream:
                stream.write(suffix)
            result = recap(self.home, path.stem)
            self.assertIsNone(result['finished_at'])

    def test_missing_thread_file_and_database_are_unknown_without_creation(self):
        path = self.fixture.add()
        path.unlink()
        self.assertIsNone(recap(self.home, 'task')['files'])
        self.assertIsNone(recap(self.home, 'absent')['started_at'])
        self.assertIsNone(recap(self.home, "' OR 1=1 --")['started_at'])
        self.fixture.db.unlink()
        self.assertEqual(thread_rows(self.home), [])
        self.assertIsNone(recap(self.home, 'task')['finished_at'])
        self.assertFalse(self.fixture.db.exists())

    def test_ledger_fallback_is_thread_scoped_and_terminal_only(self):
        self.fixture.add()
        self.fixture.ledger([('task', 'a', 'completed', 100, 120, 1),
                             ('task', 'b', 'failed', 150, 190, 2),
                             ('other', 'c', 'completed', 1, 500, 3)])
        self.assertEqual(recap(self.home, 'task'),
                         dict(files=None, started_at=100, finished_at=190, duration_s=90))
        with closing(sqlite3.connect(self.home/'thread_history_1.sqlite')) as connection:
            connection.execute("UPDATE thread_turns SET status='inProgress' WHERE turn_id='b'")
            connection.commit()
        self.assertIsNone(recap(self.home, 'task')['finished_at'])

    def test_ledger_missing_completed_field_does_not_guess(self):
        self.fixture.add()
        self.fixture.ledger([('task', 'a', 'completed', 100, 120, 1)])
        with closing(sqlite3.connect(self.home/'thread_history_1.sqlite')) as connection:
            connection.execute('ALTER TABLE thread_turns DROP COLUMN completed_at')
            connection.commit()
        result = recap(self.home, 'task')
        self.assertEqual(result['started_at'], 100)
        self.assertIsNone(result['finished_at'])

    def test_missing_rollout_can_use_explicit_ledger_times(self):
        self.fixture.add().unlink()
        self.fixture.ledger([('task', 'a', 'completed', 100, 120, 1)])
        self.assertEqual(recap(self.home, 'task'),
                         dict(files=None, started_at=100, finished_at=120, duration_s=20))

    def test_missing_first_start_cannot_be_replaced_by_a_later_turn(self):
        self.fixture.add(events=[event('task_started', at=None), event('task_complete', 120),
                                event('task_started', 150), event('task_complete', 170)])
        result = recap(self.home, 'task')
        self.assertIsNone(result['started_at'])
        self.assertEqual(result['finished_at'], 170)
        self.assertIsNone(result['duration_s'])

    def test_unknown_schema_does_not_query_other_table(self):
        with closing(sqlite3.connect(self.fixture.db)) as connection:
            connection.execute('DROP TABLE threads')
            connection.execute('CREATE TABLE threads (id INTEGER, source TEXT)')
            connection.commit()
        self.assertEqual(thread_rows(self.home), [])


class ActivityTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)
        self.fixture = RecapFixture(self.home)

    def test_each_completed_turn_and_cutoff_use_end_not_start(self):
        self.fixture.add(events=[event('turn_started', 100, turn_id='a'),
            event('task_complete', 120, turn_id='a'),
            event('task_started', 200, turn_id='b'), event('turn_complete', 240, turn_id='b'),
            event('turn_started', 300, turn_id='c')])
        self.assertEqual(codex_recap.activity(self.home, 120),
                         dict(turns=[(100., 120., 'Project'), (200., 240., 'Project')], edits=[]))
        self.assertEqual(codex_recap.activity(self.home, 121)['turns'], [(200., 240., 'Project')])

    def test_all_top_level_sources_and_terminal_tags(self):
        for index, source in enumerate(('desktop', 'vscode', 'cli', 'exec')):
            self.fixture.add(source, source, events=[event('turn_started', 100 + index),
                event(('task_complete', 'turn_complete', 'turn_aborted', 'task_complete')[index], 120 + index)])
        self.assertEqual(codex_recap.activity(self.home, 0)['turns'],
                         [(100. + i, 120. + i, 'Project') for i in range(4)])

    def test_turn_identity_missing_starts_and_duplicate_completions(self):
        self.fixture.add(events=[event('task_complete', 95, started_at=90),
            event('turn_started', 100, turn_id='a'), event('turn_complete', 105, turn_id='other'),
            event('turn_complete', 120, turn_id='a'), event('task_complete', 130, turn_id='a'),
            event('turn_started', 140, turn_id='b'), event('turn_complete', None, turn_id='b'),
            event('turn_complete', 150, turn_id='b')])
        self.assertEqual(codex_recap.activity(self.home, 0)['turns'], [(100., 120., 'Project')])

    def test_unknown_invalid_reversed_and_explicit_times(self):
        self.fixture.add(events=[event('turn_started', None), event('task_complete', 110),
            event('turn_started', 150), event('turn_complete', 140),
            event('turn_started', '2026-10-06T00:00:00'), event('task_complete', 200),
            event('turn_started', None, started_at=210), event('task_complete', None, completed_at=230),
            event('patch_apply_end', None, success=True, changes={'unknown.py': {'type': 'add'}}),
            event('patch_apply_end', True, success=True, changes={'invalid.py': {'type': 'add'}})])
        self.assertEqual(codex_recap.activity(self.home, 0),
                         dict(turns=[(210., 230., 'Project')], edits=[]))

    def test_successful_edits_have_per_event_times_and_inclusive_cutoff(self):
        self.fixture.add(events=[event('patch_apply_end', 109, success=True, changes={'old.py': {'type': 'add'}}),
            event('patch_apply_end', 110, success=True, changes={
                'z.py': {'type': 'delete'}, 'a.py': {'type': 'update', 'move_path': 'b.py'}}),
            event('item_completed', 120, item=dict(type='FileChange', status='completed',
                changes={'a.py': {'type': 'update', 'unified_diff': 'PRIVATE'}})),
            event('patch_apply_end', 130, success=False, changes={'failed.py': {'type': 'add'}}),
            event('patch_apply_end', 140, success=True, status='declined', changes={'declined.py': {'type': 'add'}}),
            event('item_completed', 150, item=dict(type='FileChange', status='inProgress',
                changes={'proposed.py': {'type': 'add'}}))])
        result = codex_recap.activity(self.home, 110)
        self.assertEqual(result, dict(turns=[], edits=[(110., 'Project', 'a.py'),
            (110., 'Project', 'b.py'), (110., 'Project', 'z.py'), (120., 'Project', 'a.py')]))
        self.assertNotIn('PRIVATE', json.dumps(result))

    def test_iso_timestamps_and_posix_paths(self):
        self.fixture.add(cwd='/project', events=[
            event('turn_started', '2026-10-06T00:00:00Z'),
            event('patch_apply_end', '2026-10-06T00:00:01+00:00', success=True,
                  changes={'/project/a.py': {'type': 'delete'}}),
            event('turn_complete', '2026-10-06T00:00:02Z')])
        self.assertEqual(codex_recap.activity(self.home, '2026-10-06T00:00:01Z'),
                         dict(turns=[(1791244800., 1791244802., 'project')],
                              edits=[(1791244801., 'project', 'a.py')]))

    def test_unconfirmed_tool_output_is_not_a_structured_edit(self):
        self.fixture.add(events=[dict(type='response_item', timestamp=100,
            payload=dict(type='custom_tool_call', name='apply_patch', call_id='p')),
            dict(type='response_item', timestamp=110,
            payload=dict(type='custom_tool_call_output', call_id='p',
                         output='Success. Updated the following files:\nM a.py\n'))])
        self.assertEqual(codex_recap.activity(self.home, 0), dict(turns=[], edits=[]))

    def test_huge_and_nonfinite_event_times_are_unknown(self):
        for index, value in enumerate((10**400, float('inf'), float('nan'), True)):
            self.fixture.add(str(index), events=[event('turn_started', value),
                event('turn_complete', 120), event('patch_apply_end', value, success=True,
                                              changes={'unknown.py': {'type': 'add'}})])
        self.assertIsNone(epoch(10**400))
        self.assertEqual(codex_recap.activity(self.home, 0), dict(turns=[], edits=[]))

    def test_edit_paths_are_deduplicated_within_event_not_across_events(self):
        changes = {'a.py': {'type': 'update', 'move_path': 'a.py'},
                   'D:/Project/a.py': {'type': 'update'}}
        self.fixture.add(events=[event('patch_apply_end', 110, success=True, changes=changes),
                                 event('patch_apply_end', 120, success=True, changes=changes)])
        self.assertEqual(codex_recap.activity(self.home, 0)['edits'],
                         [(110., 'Project', 'a.py'), (120., 'Project', 'a.py')])

    def test_extended_drive_unc_and_changed_cwd_paths(self):
        for index, (root, cwd, absolute) in enumerate([
            (r'\\?\D:\Project', r'D:\Project\src', r'D:\Project\b.py'),
            (r'\\?\UNC\server\share\Project', r'\\server\share\Project\src',
             r'\\server\share\Project\b.py'),
        ]):
            self.fixture.add(str(index), cwd=root, events=[
                dict(type='turn_context', payload=dict(cwd=cwd)),
                event('patch_apply_end', 100 + index, success=True, changes={
                    'a.py': {'type': 'add'}, absolute: {'type': 'update'},
                    r'..\..\outside.py': {'type': 'add'}, r'E:\outside.py': {'type': 'add'}})])
        self.assertEqual(codex_recap.activity(self.home, 0)['edits'],
                         [(100., 'Project', 'b.py'), (100., 'Project', 'src/a.py'),
                          (101., 'Project', 'b.py'), (101., 'Project', 'src/a.py')])

    def test_old_rollout_is_not_opened_and_mtime_boundary_is_inclusive(self):
        old = self.fixture.add('old', events=[event('turn_started', 100), event('task_complete', 200)])
        recent = self.fixture.add('recent', events=[event('turn_started', 100), event('task_complete', 120)])
        os.utime(old, (99, 99))
        os.utime(recent, (100, 100))
        with patch('codex_recap._rollout_events', wraps=codex_recap._rollout_events) as read:
            self.assertEqual(codex_recap.activity(self.home, 100)['turns'], [(100., 120., 'Project')])
        self.assertEqual([call.args[0]['id'] for call in read.call_args_list], ['recent'])

    def test_fork_copied_history_is_excluded(self):
        self.fixture.add(meta=dict(forked_from_id='parent', timestamp=150), events=[
            event('turn_started', 100), event('patch_apply_end', 110, success=True,
                changes={'copied.py': {'type': 'add'}}), event('task_complete', 120),
            event('turn_started', 160), event('patch_apply_end', 170, success=True,
                changes={'own.py': {'type': 'add'}}), event('task_complete', 180)])
        self.assertEqual(codex_recap.activity(self.home, 0),
                         dict(turns=[(160., 180., 'Project')], edits=[(170., 'Project', 'own.py')]))

    def test_duplicates_archived_and_distinct_subagent_turns(self):
        self.fixture.add(events=[event('turn_started', 100), event('task_complete', 120)])
        self.fixture.add('child', source='{"subagent":{"thread_spawn":{"parent_thread_id":"task"}}}',
                         events=[event('turn_started', 100), event('task_complete', 120)])
        self.fixture.add('conflict', events=[event('turn_started', 200), event('task_complete', 220)])
        with closing(sqlite3.connect(self.fixture.db)) as connection:
            connection.execute("UPDATE threads SET archived=1 WHERE id='task'")
            connection.execute("INSERT INTO threads SELECT * FROM threads WHERE id='task'")
            connection.execute("INSERT INTO threads SELECT id,source,cwd,'other.jsonl',title,name,project_id,archived FROM threads WHERE id='conflict'")
            connection.commit()
        self.assertEqual(codex_recap.activity(self.home, 0)['turns'],
                         [(100., 120., 'Project'), (100., 120., 'Project')])

    def test_project_name_uses_existing_assignment_metadata(self):
        self.fixture.add(events=[event('turn_started', 100), event('task_complete', 120)])
        (self.home/'.codex-global-state.json').write_text(json.dumps({
            'thread-project-assignments': {'task': {'projectId': 'p'}},
            'local-projects': {'p': {'name': 'Named Project'}}}), encoding='utf-8')
        self.assertEqual(codex_recap.activity(self.home, 0)['turns'], [(100., 120., 'Named Project')])

    def test_absent_project_stays_none_and_wrong_thread_events_are_skipped(self):
        self.fixture.add(cwd='', events=[event('turn_started', 100),
            event('patch_apply_end', 110, success=True, changes={'a.py': {'type': 'add'}}),
            event('turn_complete', 115, thread_id='other'), event('task_complete', 120)])
        self.assertEqual(codex_recap.activity(self.home, 0), dict(turns=[(100., 120., None)], edits=[]))

    def test_corrupt_incomplete_and_mismatched_rollouts_fail_closed(self):
        for name, meta, suffix in [('corrupt', {}, '{bad}\n'), ('partial', {}, '{"type":'),
                                   ('wrong', {'id': 'other'}, ''),
                                   ('fork', {'forked_from_id': 'parent', 'timestamp': None}, '')]:
            path = self.fixture.add(name, meta=meta, events=[event('turn_started', 100), event('task_complete', 120)])
            with path.open('a', encoding='utf-8') as stream:
                stream.write(suffix)
        self.assertEqual(codex_recap.activity(self.home, 0), dict(turns=[], edits=[]))

    def test_invalid_since_missing_sources_and_readonly_files(self):
        path = self.fixture.add(events=[event('turn_started', 100), event('task_complete', 120)])
        before = {file.name: (file.read_bytes(), file.stat().st_mtime_ns) for file in self.home.iterdir()}
        for since in (None, True, -1, float('nan'), float('inf'), 10**400, 'unknown'):
            self.assertEqual(codex_recap.activity(self.home, since), dict(turns=[], edits=[]))
        self.assertEqual(codex_recap.activity(self.home, 0)['turns'], [(100., 120., 'Project')])
        self.assertEqual({file.name: (file.read_bytes(), file.stat().st_mtime_ns) for file in self.home.iterdir()}, before)
        path.unlink()
        self.assertEqual(codex_recap.activity(self.home, 0), dict(turns=[], edits=[]))
        self.fixture.db.unlink()
        self.assertEqual(codex_recap.activity(self.home, 0), dict(turns=[], edits=[]))
        self.assertFalse(self.fixture.db.exists())


if __name__ == '__main__':
    unittest.main()
