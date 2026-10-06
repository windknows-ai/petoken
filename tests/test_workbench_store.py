"""Local workbench persistence; every database lives in a temporary directory."""
import hashlib
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
from uuid import uuid4

from workbench_store import WorkbenchError, WorkbenchStore


class WorkbenchStoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'workbench.sqlite3'
        self.store = WorkbenchStore(self.path)
        self.addCleanup(self.store.close)

    def test_empty_and_unicode_crud_durable_reopen(self):
        self.assertEqual(self.store.list_projects(), [])
        self.assertEqual(self.store.list_todos(), [])
        self.assertEqual(self.store.list_notes(), [])
        self.assertEqual(self.store.task_links(), {})
        project = self.store.create_project(' 项目 🦋 ', 'D:/资料/项目')
        self.assertEqual(project['name'], ' 项目 🦋 ')
        self.assertEqual(project['directory'], 'D:/资料/项目')
        self.assertEqual(set(project), {'id', 'name', 'directory', 'created_at', 'updated_at'})
        updated = self.store.update_project(project['id'], project['name'], project['directory'])
        self.assertEqual(updated['created_at'], project['created_at'])
        self.assertGreaterEqual(updated['updated_at'], project['updated_at'])
        todo = self.store.create_todo("任务 '; DROP TABLE notes; --", project['id'])
        note = self.store.create_note('笔记 📝', '第一行\nsecond line\x00end', project['id'])
        self.assertEqual(set(todo), {'id', 'title', 'project_id', 'done', 'created_at', 'updated_at'})
        self.assertEqual(set(note), {'id', 'title', 'body', 'project_id', 'created_at', 'updated_at'})
        todo = self.store.update_todo(todo['id'], '已完成', project['id'], True)
        note = self.store.update_note(note['id'], '新版', '正文 🦋\nplain text', project['id'])
        project = self.store.update_project(project['id'], '新项目', '')
        self.store.link_task('codex', 'task:/私密-key', project['id'])
        self.store.close()
        self.store = WorkbenchStore(self.path)
        self.addCleanup(self.store.close)
        self.assertEqual(self.store.list_projects(), [project])
        self.assertEqual(self.store.list_todos(), [todo])
        self.assertEqual(self.store.list_notes(), [note])
        self.assertEqual(self.store.get_note(note['id']), note)
        self.assertIs(self.store.list_todos()[0]['done'], True)
        self.assertEqual(self.store.task_links(), {('codex', 'task:/私密-key'): project['id']})
        self.assertEqual(todo['created_at'][:10], todo['updated_at'][:10])
        self.assertGreaterEqual(todo['updated_at'], todo['created_at'])
        self.store.delete_todo(todo['id'])
        self.store.delete_note(note['id'])
        self.store.delete_project(project['id'])
        self.assertEqual(self.store.list_todos(), [])
        self.assertEqual(self.store.list_notes(), [])
        self.assertEqual(self.store.task_links(), {})

    def test_all_unassigned_project_and_completion_filters(self):
        a, b = self.store.create_project('A'), self.store.create_project('B')
        todos = [self.store.create_todo('Inbox'), self.store.create_todo('A todo', a['id']),
                 self.store.create_todo('A done', a['id'], True), self.store.create_todo('B todo', b['id'])]
        notes = [self.store.create_note('Inbox'), self.store.create_note('A note', project_id=a['id']),
                 self.store.create_note('B note', project_id=b['id'])]
        self.assertEqual(self.store.list_todos(), todos)
        self.assertEqual(self.store.list_todos(''), todos[:1])
        self.assertEqual(self.store.list_todos(a['id']), todos[1:3])
        self.assertEqual(self.store.list_todos(a['id'], include_completed=False), todos[1:2])
        self.assertEqual(self.store.list_todos(include_completed=False), [todos[0], todos[1], todos[3]])
        self.assertEqual(self.store.list_notes(), notes)
        self.assertEqual(self.store.list_notes(''), notes[:1])
        self.assertEqual(self.store.list_notes(b['id']), notes[2:])
        moved = self.store.update_todo(todos[1]['id'], 'Moved', b['id'])
        self.assertEqual(self.store.list_todos(b['id']), [moved, todos[3]])
        self.assertFalse(self.store.update_todo(todos[2]['id'], 'Reopen')['done'])
        self.assertIsNone(self.store.update_note(notes[1]['id'], 'Unassigned', '')['project_id'])

    def test_project_delete_retains_children_and_cascades_links(self):
        project = self.store.create_project('Delete')
        todo = self.store.create_todo('Keep', project['id'], True)
        note = self.store.create_note('Keep', 'body', project['id'])
        self.store.link_task('codex', 'stable', project['id'])
        self.store.delete_project(project['id'])
        self.assertEqual(self.store.list_todos('')[0], {**todo, 'project_id': None})
        self.assertEqual(self.store.get_note(note['id']), {**note, 'project_id': None})
        self.assertEqual(self.store.task_links(), {})
        with closing(sqlite3.connect(self.path)) as connection, connection:
            self.assertEqual(connection.execute('PRAGMA foreign_key_check').fetchall(), [])

    def test_links_replace_remove_and_reject_foreign_provider_or_project(self):
        a, b = self.store.create_project('A'), self.store.create_project('B')
        self.store.link_task('codex', 'key', a['id'])
        self.store.link_task('codex', 'key', b['id'])
        self.assertEqual(self.store.task_links(), {('codex', 'key'): b['id']})
        for provider, key, project in [('opencode', 'key', a['id']), ('codex', '', a['id']),
                                      ('codex', None, a['id']), ('codex', 'other', str(uuid4()))]:
            with self.subTest(provider=provider, key=key), self.assertRaises(WorkbenchError):
                self.store.link_task(provider, key, project)
        self.assertEqual(self.store.task_links(), {('codex', 'key'): b['id']})
        self.store.link_task('codex', 'key', None)
        self.store.link_task('codex', 'missing', None)
        self.assertEqual(self.store.task_links(), {})

    def test_validation_no_truncation_or_partial_mutation(self):
        project = self.store.create_project('Valid')
        note = self.store.create_note('Note', 'original')
        for text in ('', ' \t\n', 'x' * 201, None, 4, 'bad\ud800'):
            for method in (self.store.create_project, self.store.create_todo, self.store.create_note):
                with self.subTest(method=method.__name__, text=repr(text)[:25]), self.assertRaises(WorkbenchError):
                    method(text)
        for action in (lambda: self.store.update_project(project['id'], 'Name', None),
                       lambda: self.store.create_note('Title', 'x' * 1_000_001),
                       lambda: self.store.update_note(note['id'], 'Title', None),
                       lambda: self.store.update_note(note['id'], 'Title', 'x' * 1_000_001),
                       lambda: self.store.create_todo('Title', done=1),
                       lambda: self.store.list_todos(include_completed=1),
                       lambda: self.store.create_todo('Title', project_id=''),
                       lambda: self.store.create_note('Title', project_id=str(uuid4()))):
            with self.assertRaises(WorkbenchError):
                action()
        self.assertEqual(self.store.list_projects(), [project])
        self.assertEqual(self.store.get_note(note['id']), note)
        self.assertEqual(self.store.list_todos(), [])
        self.assertEqual(len(self.store.create_note('x' * 200, 'x' * 1_000_000)['body']), 1_000_000)

    def test_invalid_missing_ids_fail(self):
        for record_id in (None, 0, True, '', 'not-a-uuid', str(uuid4())):
            for method in (self.store.delete_project, self.store.delete_todo,
                           self.store.delete_note, self.store.get_note):
                with self.subTest(method=method.__name__, record_id=record_id), self.assertRaises(WorkbenchError):
                    method(record_id)
        for method in (self.store.list_todos, self.store.list_notes):
            with self.assertRaises(WorkbenchError):
                method(project_id='invalid')
        for action in (lambda: self.store.update_project(str(uuid4()), 'A'),
                       lambda: self.store.update_todo(str(uuid4()), 'A'),
                       lambda: self.store.update_note(str(uuid4()), 'A', 'body')):
            with self.assertRaises(WorkbenchError):
                action()

    def test_transaction_rollback_retains_project_children_links(self):
        project = self.store.create_project('Project')
        todo = self.store.create_todo('Todo', project['id'])
        note = self.store.create_note('Note', project_id=project['id'])
        self.store.link_task('codex', 'key', project['id'])
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("CREATE TRIGGER reject_delete AFTER DELETE ON projects BEGIN SELECT RAISE(ABORT, 'injected failure'); END")
        with self.assertRaises(WorkbenchError):
            self.store.delete_project(project['id'])
        self.assertEqual(self.store.list_projects(), [project])
        self.assertEqual(self.store.list_todos(), [todo])
        self.assertEqual(self.store.list_notes(), [note])
        self.assertEqual(self.store.task_links(), {('codex', 'key'): project['id']})
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute('DROP TRIGGER reject_delete')
        self.store.delete_project(project['id'])

    def test_locked_write_fails_without_losing_saved_records_then_recovers(self):
        project = self.store.create_project('Saved')
        connection = sqlite3.connect(self.path)
        self.addCleanup(connection.close)
        connection.execute('BEGIN IMMEDIATE')
        with self.assertRaises(WorkbenchError):
            self.store.create_note('Blocked')
        connection.rollback()
        self.assertEqual(self.store.list_projects(), [project])
        self.assertEqual(self.store.list_notes(), [])
        self.assertEqual(self.store.create_note('Recovered')['title'], 'Recovered')

    def test_blocked_commit_rolls_back_and_never_returns_unsaved_record(self):
        saved = self.store.create_note('Saved', 'body')
        reader = sqlite3.connect(self.path)
        self.addCleanup(reader.close)
        reader.execute('BEGIN')
        reader.execute('SELECT * FROM notes').fetchall()
        with self.assertRaises(WorkbenchError):
            self.store.create_note('Unsaved draft', 'keep editor content')
        self.assertEqual(self.store.list_notes(), [saved])
        reader.rollback()
        reopened = WorkbenchStore(self.path)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.list_notes(), [saved])
        self.assertEqual(self.store.create_note('Retry saved')['title'], 'Retry saved')

    def test_close_idempotent_and_operations_fail_after_close(self):
        self.store.close()
        self.store.close()
        for action in (self.store.list_projects, self.store.list_todos, self.store.list_notes,
                       self.store.task_links, lambda: self.store.create_project('Closed'),
                       lambda: self.store.link_task('codex', 'key', None)):
            with self.assertRaises(WorkbenchError):
                action()

    def test_corrupt_future_unrecognized_schema_files_remain_identical(self):
        self.store.close()
        for kind in ('corrupt', 'empty', 'foreign', 'future', 'changed', 'changed_constraint', 'broken_foreign_keys'):
            path = Path(self.directory.name) / f'{kind}.sqlite3'
            if kind == 'corrupt':
                path.write_bytes(b'not sqlite\x00personal content')
            elif kind == 'empty':
                path.touch()
            elif kind == 'foreign':
                with closing(sqlite3.connect(path)) as connection, connection:
                    connection.execute('CREATE TABLE personal(content TEXT)')
                    connection.execute("INSERT INTO personal VALUES ('keep me')")
            else:
                path.write_bytes(self.path.read_bytes())
                with closing(sqlite3.connect(path)) as connection, connection:
                    if kind == 'future':
                        connection.execute('PRAGMA user_version=999')
                    elif kind == 'changed':
                        connection.execute('ALTER TABLE notes ADD COLUMN unsupported TEXT')
                    elif kind == 'changed_constraint':
                        sql = connection.execute("SELECT sql FROM sqlite_master WHERE name='task_links'").fetchone()[0]
                        connection.execute('DROP TABLE task_links')
                        connection.execute(sql.replace("'codex'", "'CODEX'"))
                    else:
                        connection.execute("INSERT INTO todos VALUES (?, 'orphan', ?, 0, 'now', 'now')",
                                           (str(uuid4()), str(uuid4())))
            original = hashlib.sha256(path.read_bytes()).hexdigest()
            with self.subTest(kind=kind), self.assertRaises(WorkbenchError):
                WorkbenchStore(path)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), original)

    def test_new_nested_path_creates_empty_store(self):
        nested = Path(self.directory.name) / 'nested' / 'data.sqlite3'
        store = WorkbenchStore(nested)
        self.addCleanup(store.close)
        self.assertEqual(store.list_projects(), [])
        self.assertTrue(nested.is_file())



class SchemaMigrationTests(unittest.TestCase):
    """Schema 1 (V1.4, Codex-only links) -> schema 2 (V1.5, Codex + Claude Code)."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.folder = Path(self.directory.name)
        self.path = self.folder / 'workbench.sqlite3'

    def make_v1(self, path, task_links_sql=None, link_provider='codex'):
        import workbench_store
        schema = dict(workbench_store._SCHEMA_V1)
        if task_links_sql is not None:
            schema['task_links'] = task_links_sql
        project = str(uuid4())
        with closing(sqlite3.connect(path)) as connection, connection:
            for sql in schema.values():
                connection.execute(sql)
            connection.execute(f'PRAGMA application_id={workbench_store._APPLICATION_ID}')
            connection.execute('PRAGMA user_version=1')
            connection.execute("INSERT INTO projects VALUES (?, '项目', 'D:/p', 'now', 'now')", (project,))
            connection.execute("INSERT INTO todos VALUES (?, 'todo', ?, 0, 'now', 'now')", (str(uuid4()), project))
            connection.execute("INSERT INTO notes VALUES (?, 'n', '私密内容', ?, 'now', 'now')", (str(uuid4()), project))
            connection.execute("INSERT INTO task_links VALUES (?, 'thread-1', ?)", (link_provider, project))
        return project

    def backups(self):
        return sorted(self.folder.glob('workbench.v1-backup-*.sqlite3'))

    def test_exact_v1_migrates_once_with_backup_and_keeps_every_record(self):
        project = self.make_v1(self.path)
        store = WorkbenchStore(self.path)
        self.addCleanup(store.close)
        self.assertEqual(store.task_links(), {('codex', 'thread-1'): project})
        self.assertEqual(len(store.list_todos()), 1)
        self.assertEqual(store.list_notes()[0]['body'], '私密内容')
        store.link_task('claude', 'claude:session-1', project)
        self.assertEqual(store.task_links()[('claude', 'claude:session-1')], project)
        with self.assertRaises(WorkbenchError):
            store.link_task('opencode', 'x', project)
        [backup] = self.backups()
        self.assertEqual(store.migration_backup, backup)
        with closing(sqlite3.connect(backup)) as connection:
            self.assertEqual(connection.execute('PRAGMA user_version').fetchone()[0], 1)
            self.assertEqual(connection.execute('SELECT task_key FROM task_links').fetchall(), [('thread-1',)])
        store.close()
        again = WorkbenchStore(self.path)
        self.addCleanup(again.close)
        self.assertIsNone(again.migration_backup)
        self.assertEqual(len(self.backups()), 1)
        self.assertEqual(len(again.task_links()), 2)

    def test_unrecognized_v1_is_never_backed_up_or_changed(self):
        changed = """CREATE TABLE task_links (
        provider_id TEXT NOT NULL CHECK (provider_id = 'CODEX'), task_key TEXT NOT NULL,
        project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        PRIMARY KEY (provider_id, task_key))"""
        self.make_v1(self.path, task_links_sql=changed, link_provider='CODEX')
        original = hashlib.sha256(self.path.read_bytes()).hexdigest()
        with self.assertRaises(WorkbenchError):
            WorkbenchStore(self.path)
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(), original)
        self.assertEqual(self.backups(), [])

    def test_failed_migration_rolls_back_and_keeps_the_backup(self):
        from unittest.mock import patch
        import workbench_store
        project = self.make_v1(self.path)
        broken = dict(workbench_store._SCHEMA, task_links='CREATE TABLE task_links (broken')
        with patch.object(workbench_store, '_SCHEMA', broken), self.assertRaises(WorkbenchError):
            WorkbenchStore(self.path)
        self.assertEqual(len(self.backups()), 1)
        with closing(sqlite3.connect(self.path)) as connection:
            self.assertEqual(connection.execute('PRAGMA user_version').fetchone()[0], 1)
            self.assertEqual(connection.execute('SELECT project_id FROM task_links').fetchall(), [(project,)])
            names = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertNotIn('task_links_v1', names)
        # The untouched v1 store still migrates on the next normal open.
        store = WorkbenchStore(self.path)
        self.addCleanup(store.close)
        self.assertEqual(store.task_links(), {('codex', 'thread-1'): project})



class SchemaFourTests(unittest.TestCase):
    """2.0: review state, presets, handoffs, focus, goals, stickers, points."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.folder = Path(self.directory.name)
        self.path = self.folder / 'workbench.sqlite3'

    def make_v3(self):
        import workbench_store
        project, todo = str(uuid4()), str(uuid4())
        with closing(sqlite3.connect(self.path)) as connection, connection:
            for sql in workbench_store._SCHEMA_V3.values():
                connection.execute(sql)
            connection.execute(f'PRAGMA application_id={workbench_store._APPLICATION_ID}')
            connection.execute('PRAGMA user_version=3')
            connection.execute("INSERT INTO projects VALUES (?, 'site', 'D:/p', 'now', 'now')", (project,))
            connection.execute("INSERT INTO todos VALUES (?, 'todo', ?, 0, 'now', 'now')", (todo, project))
            connection.execute("INSERT INTO todo_schedules VALUES (?, 1.0, 'claude', 'D:/p', 'go', 'opus', 'high', "
                               "'started', 2.0, 'claude:s1', NULL)", (todo,))
        return project, todo

    def test_exact_v3_migrates_with_backup_and_keeps_schedules(self):
        project, todo = self.make_v3()
        store = WorkbenchStore(self.path)
        self.addCleanup(store.close)
        schedule = store.get_schedule(todo)
        self.assertEqual((schedule['state'], schedule['model'], schedule['task_key']), ('started', 'opus', 'claude:s1'))
        self.assertEqual(store.update_schedule(todo, state='review')['state'], 'review')
        [backup] = sorted(self.folder.glob('workbench.v3-backup-*.sqlite3'))
        with closing(sqlite3.connect(backup)) as connection:
            self.assertEqual(connection.execute('PRAGMA user_version').fetchone()[0], 3)
        self.assertIsNone(store.get_preset(project))

    def test_presets_handoffs_goals(self):
        store = WorkbenchStore(self.path)
        self.addCleanup(store.close)
        project = store.create_project('site', 'D:/site')['id']
        store.set_preset(project, 'codex', 'D:/site', 'continue the login work', 'gpt-5.5', 'high')
        self.assertEqual(store.get_preset(project)['model'], 'gpt-5.5')
        store.set_preset(project, 'claude', 'D:/site', '')
        self.assertEqual((store.get_preset(project)['provider_id'], store.get_preset(project)['model']), ('claude', ''))
        with self.assertRaises(WorkbenchError):
            store.set_preset(project, 'opencode', 'D:/site', '')
        store.add_handoff(project, 'first')
        store.add_handoff(project, 'fix the logout button next')
        self.assertEqual(store.latest_handoff(project)['body'], 'fix the logout button next')
        self.assertEqual(store.set_goal(project, weekly_tokens=2_000_000)['weekly_tokens'], 2_000_000)
        self.assertEqual(store.set_goal(project, weekly_usd=5.0)['weekly_tokens'], None)
        for bad in (0, -1, True, float('nan')):
            with self.assertRaises(WorkbenchError):
                store.set_goal(project, weekly_tokens=bad)
        self.assertIsNone(store.set_goal(project))
        self.assertEqual(store.list_goals(), [])
        store.delete_project(project)        # Presets and handoffs go with it.
        with self.assertRaises(WorkbenchError):
            store.get_preset(project) or store.latest_handoff(project) or store._record('projects', project)

    def test_focus_sessions_and_done_todos(self):
        import time
        store = WorkbenchStore(self.path)
        self.addCleanup(store.close)
        todo = store.create_todo('write tests')
        now = time.time()
        session = store.start_focus(now, 25 * 60, todo_id=todo['id'])
        with self.assertRaises(WorkbenchError):
            store.start_focus(now, 0)
        store.update_todo(todo['id'], 'write tests', done=True)
        self.assertEqual(store.list_focus(), [])           # Still running.
        ended = store.end_focus(session['id'], now + 1500, True)
        self.assertEqual(ended['completed'], 1)
        with self.assertRaises(WorkbenchError):
            store.end_focus(session['id'], now + 1600, False)
        self.assertEqual([s['id'] for s in store.list_focus(now - 10)], [session['id']])
        self.assertEqual([t['id'] for t in store.todos_done_between(now - 5, time.time() + 5)], [todo['id']])
        self.assertEqual(store.todos_done_between(now - 100, now - 50), [])

    def test_stickers_and_points_count_once(self):
        store = WorkbenchStore(self.path)
        self.addCleanup(store.close)
        self.assertTrue(store.earn('first_project', 10))
        self.assertFalse(store.earn('first_project', 20))
        self.assertEqual(store.achievements(), {'first_project': 10})
        self.assertTrue(store.add_points('todo_done', 'todo-1', 5, 1))
        self.assertFalse(store.add_points('todo_done', 'todo-1', 5, 2))
        self.assertTrue(store.add_points('focus_done', 'f-1', 10, 3))
        self.assertEqual((store.points(), store.count_points('todo_done')), (15, 1))
        with self.assertRaises(WorkbenchError):
            store.add_points('x', 'y', 0, 1)


if __name__ == '__main__':
    unittest.main()
