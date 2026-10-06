"""Transactional local projects, todos, notes and explicit task links.

Schema 2 (V1.5) lets Codex and Claude Code tasks be linked to projects;
schema 3 (V1.7) adds ``todo_schedules``: a todo handed to Claude Code or
Codex, now or at a set time, and what became of it. Schema 4 (2.0) adds a
``review`` schedule state (the AI is done, waiting for you to accept it),
project start presets, "where to continue" notes, focus sessions, weekly
project usage goals, stickers and companionship points. Exact older databases
are migrated once on open, one step at a time: a complete SQLite backup is
written beside the file first, each step runs in one transaction, and any
failure rolls back and leaves the original untouched. Anything
unrecognized is never migrated.
"""
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from uuid import UUID, uuid4


class WorkbenchError(Exception):
    """A validation, storage or unsupported-database failure."""


_APPLICATION_ID = 0x50545742
_SCHEMA_VERSION = 4
SCHEDULE_STATES = ('waiting', 'started', 'review', 'finished', 'failed', 'missed')
# Providers whose tasks may be linked to projects.
LINK_PROVIDERS = ('codex', 'claude')
_SCHEMA = {
    'projects': '''CREATE TABLE projects (
        id TEXT PRIMARY KEY NOT NULL, name TEXT NOT NULL, directory TEXT NOT NULL,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL)''',
    'todos': '''CREATE TABLE todos (
        id TEXT PRIMARY KEY NOT NULL, title TEXT NOT NULL,
        project_id TEXT REFERENCES projects(id) ON DELETE SET NULL,
        done INTEGER NOT NULL CHECK (done IN (0, 1)),
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL)''',
    'notes': '''CREATE TABLE notes (
        id TEXT PRIMARY KEY NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL,
        project_id TEXT REFERENCES projects(id) ON DELETE SET NULL,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL)''',
    'task_links': '''CREATE TABLE task_links (
        provider_id TEXT NOT NULL CHECK (provider_id IN ('codex', 'claude')), task_key TEXT NOT NULL,
        project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        PRIMARY KEY (provider_id, task_key))''',
    'todo_schedules': '''CREATE TABLE todo_schedules (
        todo_id TEXT PRIMARY KEY NOT NULL REFERENCES todos(id) ON DELETE CASCADE,
        run_at REAL NOT NULL,
        provider_id TEXT NOT NULL CHECK (provider_id IN ('codex', 'claude')),
        folder TEXT NOT NULL, prompt TEXT NOT NULL,
        model TEXT NOT NULL DEFAULT '', effort TEXT NOT NULL DEFAULT '',
        state TEXT NOT NULL CHECK (state IN ('waiting', 'started', 'review', 'finished', 'failed', 'missed')),
        started_at REAL, task_key TEXT,
        note_id TEXT REFERENCES notes(id) ON DELETE SET NULL)''',
    'project_presets': '''CREATE TABLE project_presets (
        project_id TEXT PRIMARY KEY NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        provider_id TEXT NOT NULL CHECK (provider_id IN ('codex', 'claude')),
        folder TEXT NOT NULL, prompt TEXT NOT NULL,
        model TEXT NOT NULL DEFAULT '', effort TEXT NOT NULL DEFAULT '',
        updated_at TEXT NOT NULL)''',
    'handoff_notes': '''CREATE TABLE handoff_notes (
        id TEXT PRIMARY KEY NOT NULL,
        project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        body TEXT NOT NULL, created_at TEXT NOT NULL)''',
    'focus_sessions': '''CREATE TABLE focus_sessions (
        id TEXT PRIMARY KEY NOT NULL, started_at REAL NOT NULL, planned_s REAL NOT NULL,
        ended_at REAL, completed INTEGER NOT NULL DEFAULT 0 CHECK (completed IN (0, 1)),
        project_id TEXT REFERENCES projects(id) ON DELETE SET NULL,
        todo_id TEXT REFERENCES todos(id) ON DELETE SET NULL)''',
    'usage_goals': '''CREATE TABLE usage_goals (
        project_id TEXT PRIMARY KEY NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        weekly_tokens INTEGER CHECK (weekly_tokens IS NULL OR weekly_tokens > 0),
        weekly_usd REAL CHECK (weekly_usd IS NULL OR weekly_usd > 0),
        updated_at TEXT NOT NULL)''',
    'achievements': '''CREATE TABLE achievements (
        id TEXT PRIMARY KEY NOT NULL, earned_at REAL NOT NULL)''',
    'points_ledger': '''CREATE TABLE points_ledger (
        reason TEXT NOT NULL, ref TEXT NOT NULL, at REAL NOT NULL,
        points INTEGER NOT NULL CHECK (points > 0),
        PRIMARY KEY (reason, ref))''',
}
_V4_TABLES = ('project_presets', 'handoff_notes', 'focus_sessions', 'usage_goals',
              'achievements', 'points_ledger')
# Schema 3 (V1.7): no review state and none of the 2.0 tables.
_SCHEMA_V3 = {name: sql for name, sql in _SCHEMA.items() if name not in _V4_TABLES}
_SCHEMA_V3['todo_schedules'] = _SCHEMA['todo_schedules'].replace("'started', 'review', ", "'started', ")
# The first schema-3 table in V1.7 test builds, before model and effort.
_SCHEDULES_PREVIEW = '''CREATE TABLE todo_schedules (
        todo_id TEXT PRIMARY KEY NOT NULL REFERENCES todos(id) ON DELETE CASCADE,
        run_at REAL NOT NULL,
        provider_id TEXT NOT NULL CHECK (provider_id IN ('codex', 'claude')),
        folder TEXT NOT NULL, prompt TEXT NOT NULL,
        state TEXT NOT NULL CHECK (state IN ('waiting', 'started', 'finished', 'failed', 'missed')),
        started_at REAL, task_key TEXT,
        note_id TEXT REFERENCES notes(id) ON DELETE SET NULL)'''
# Schema 2 (V1.5/V1.6): no schedules. Kept to recognize and migrate it.
_SCHEMA_V2 = {name: sql for name, sql in _SCHEMA_V3.items() if name != 'todo_schedules'}
# Schema 1 (V1.4): Codex-only task links. Kept to recognize and migrate it.
_SCHEMA_V1 = dict(_SCHEMA_V2, task_links='''CREATE TABLE task_links (
        provider_id TEXT NOT NULL CHECK (provider_id = 'codex'), task_key TEXT NOT NULL,
        project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        PRIMARY KEY (provider_id, task_key))''')


def _text(value, field, limit=None, required=False):
    if (not isinstance(value, str) or required and not value.strip()
            or limit is not None and len(value) > limit):
        raise WorkbenchError(f'Invalid {field}')
    try:
        value.encode('utf-8')
    except UnicodeError:
        raise WorkbenchError(f'Invalid {field}') from None
    return value


def _identifier(value):
    try:
        if not isinstance(value, str) or str(UUID(value)) != value:
            raise ValueError
    except (ValueError, AttributeError):
        raise WorkbenchError('Invalid record ID') from None
    return value


def _boolean(value, field):
    if not isinstance(value, bool):
        raise WorkbenchError(f'Invalid {field}')
    return value


def _now():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')


class WorkbenchStore:
    def __init__(self, path):
        self._connection = None
        try:
            self.path = Path(path).absolute()
            existed = self.path.exists()
            if not existed:
                self.path.parent.mkdir(parents=True, exist_ok=True)
            mode = 'rw' if existed else 'rwc'
            connection = sqlite3.connect(self.path.as_uri() + f'?mode={mode}',
                                         uri=True, timeout=.2)
            self._connection = connection
            connection.row_factory = sqlite3.Row
            connection.execute('PRAGMA foreign_keys=ON')
            if not existed:
                # Check again under the write lock: a competing opener may
                # have initialized this new path after our existence check.
                with connection:
                    connection.execute('BEGIN IMMEDIATE')
                    if (not connection.execute('SELECT 1 FROM sqlite_master').fetchone()
                            and connection.execute('PRAGMA user_version').fetchone()[0] == 0
                            and connection.execute('PRAGMA application_id').fetchone()[0] == 0):
                        for sql in _SCHEMA.values():
                            connection.execute(sql)
                        connection.execute(f'PRAGMA application_id={_APPLICATION_ID}')
                        connection.execute(f'PRAGMA user_version={_SCHEMA_VERSION}')
            self.migration_backup = None
            self._migrate_v1()
            self._migrate_v2()
            self._migrate_v3_preview()
            self._migrate_v3()
            self._validate_schema()
        except (OSError, ValueError, TypeError, sqlite3.Error, WorkbenchError) as error:
            self.close()
            if isinstance(error, WorkbenchError):
                raise
            raise WorkbenchError(f'Cannot open workbench database: {error}') from error

    def _backup(self, label):
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        backup = self.path.with_name(f'{self.path.stem}.{label}-backup-{stamp}{self.path.suffix}')
        index = 1
        while backup.exists():
            index += 1
            backup = self.path.with_name(f'{self.path.stem}.{label}-backup-{stamp}-{index}{self.path.suffix}')
        with closing(sqlite3.connect(backup)) as target:
            self._connection.backup(target)
        if self.migration_backup is None:
            self.migration_backup = backup   # The oldest copy: the user's original file.
        return backup

    def _migrate_v2(self):
        """Add todo schedules to an exact schema-2 store, backup first."""
        connection = self._connection
        if (connection.execute('PRAGMA application_id').fetchone()[0] != _APPLICATION_ID
                or connection.execute('PRAGMA user_version').fetchone()[0] != 2):
            return
        self._validate_schema(_SCHEMA_V2, 2)
        self._backup('v2')
        try:
            with connection:
                connection.execute('BEGIN IMMEDIATE')
                if connection.execute('PRAGMA user_version').fetchone()[0] != 2:
                    return  # Another opener migrated it meanwhile.
                connection.execute(_SCHEMA_V3['todo_schedules'])
                connection.execute('PRAGMA user_version=3')
        except sqlite3.Error as error:
            raise WorkbenchError(f'Cannot migrate workbench database: {error}') from error

    def _migrate_v3_preview(self):
        """Rebuild a test build's schedule table with model and effort columns."""
        connection = self._connection
        if (connection.execute('PRAGMA application_id').fetchone()[0] != _APPLICATION_ID
                or connection.execute('PRAGMA user_version').fetchone()[0] != 3):
            return
        row = connection.execute("SELECT sql FROM sqlite_master WHERE name='todo_schedules'").fetchone()
        if row is None or ' '.join(row[0].split()) != ' '.join(_SCHEDULES_PREVIEW.split()):
            return
        self._validate_schema(dict(_SCHEMA_V3, todo_schedules=_SCHEDULES_PREVIEW), 3)
        self._backup('v3-preview')
        columns = 'todo_id, run_at, provider_id, folder, prompt, state, started_at, task_key, note_id'
        try:
            with connection:
                connection.execute('BEGIN IMMEDIATE')
                count = connection.execute('SELECT COUNT(*) FROM todo_schedules').fetchone()[0]
                connection.execute('ALTER TABLE todo_schedules RENAME TO todo_schedules_preview')
                connection.execute(_SCHEMA_V3['todo_schedules'])
                connection.execute(f'INSERT INTO todo_schedules ({columns}) SELECT {columns} FROM todo_schedules_preview')
                connection.execute('DROP TABLE todo_schedules_preview')
                if connection.execute('SELECT COUNT(*) FROM todo_schedules').fetchone()[0] != count:
                    raise WorkbenchError('Workbench migration changed the schedule count')
        except sqlite3.Error as error:
            raise WorkbenchError(f'Cannot migrate workbench database: {error}') from error

    def _migrate_v3(self):
        """Schema 3 to 4: the review state and the 2.0 tables, backup first."""
        connection = self._connection
        if (connection.execute('PRAGMA application_id').fetchone()[0] != _APPLICATION_ID
                or connection.execute('PRAGMA user_version').fetchone()[0] != 3):
            return
        self._validate_schema(_SCHEMA_V3, 3)
        self._backup('v3')
        columns = ('todo_id, run_at, provider_id, folder, prompt, model, effort, state, '
                   'started_at, task_key, note_id')
        try:
            with connection:
                connection.execute('BEGIN IMMEDIATE')
                if connection.execute('PRAGMA user_version').fetchone()[0] != 3:
                    return  # Another opener migrated it meanwhile.
                count = connection.execute('SELECT COUNT(*) FROM todo_schedules').fetchone()[0]
                connection.execute('ALTER TABLE todo_schedules RENAME TO todo_schedules_v3')
                connection.execute(_SCHEMA['todo_schedules'])
                connection.execute(f'INSERT INTO todo_schedules ({columns}) SELECT {columns} FROM todo_schedules_v3')
                connection.execute('DROP TABLE todo_schedules_v3')
                if connection.execute('SELECT COUNT(*) FROM todo_schedules').fetchone()[0] != count:
                    raise WorkbenchError('Workbench migration changed the schedule count')
                for name in _V4_TABLES:
                    connection.execute(_SCHEMA[name])
                connection.execute('PRAGMA user_version=4')
        except sqlite3.Error as error:
            raise WorkbenchError(f'Cannot migrate workbench database: {error}') from error

    def _migrate_v1(self):
        """Upgrade an exact schema-1 store to schema 2, backup first."""
        connection = self._connection
        if (connection.execute('PRAGMA application_id').fetchone()[0] != _APPLICATION_ID
                or connection.execute('PRAGMA user_version').fetchone()[0] != 1):
            return
        # Read-only proof that this is exactly our schema 1 before any write.
        self._validate_schema(_SCHEMA_V1, 1)
        self._backup('v1')
        try:
            with connection:
                connection.execute('BEGIN IMMEDIATE')
                if connection.execute('PRAGMA user_version').fetchone()[0] != 1:
                    return  # Another opener migrated it meanwhile.
                count = connection.execute('SELECT COUNT(*) FROM task_links').fetchone()[0]
                connection.execute('ALTER TABLE task_links RENAME TO task_links_v1')
                connection.execute(_SCHEMA['task_links'])
                connection.execute('INSERT INTO task_links (provider_id, task_key, project_id) '
                                   'SELECT provider_id, task_key, project_id FROM task_links_v1')
                connection.execute('DROP TABLE task_links_v1')
                if connection.execute('SELECT COUNT(*) FROM task_links').fetchone()[0] != count:
                    raise WorkbenchError('Workbench migration changed the task-link count')
                connection.execute('PRAGMA user_version=2')
        except sqlite3.Error as error:
            raise WorkbenchError(f'Cannot migrate workbench database: {error}') from error

    def _validate_schema(self, schema=None, version=_SCHEMA_VERSION):
        schema = _SCHEMA if schema is None else schema
        connection = self._connection
        if (connection.execute('PRAGMA application_id').fetchone()[0] != _APPLICATION_ID
                or connection.execute('PRAGMA user_version').fetchone()[0] != version):
            raise WorkbenchError('Unrecognized or unsupported workbench database')
        # Exact owned schema also verifies the delete actions and constraints;
        # reject extra triggers/views/indexes that could change write semantics.
        objects = connection.execute('SELECT name, type, sql FROM sqlite_master WHERE sql IS NOT NULL').fetchall()
        actual = {row['name']: ' '.join(row['sql'].split())
                  for row in objects if row['type'] == 'table'}
        expected = {name: ' '.join(sql.split()) for name, sql in schema.items()}
        if len(objects) != len(schema) or actual != expected:
            raise WorkbenchError('Unrecognized workbench schema')
        if ([row[0] for row in connection.execute('PRAGMA quick_check')] != ['ok']
                or connection.execute('PRAGMA foreign_key_check').fetchone() is not None):
            raise WorkbenchError('Invalid workbench database records')

    def _open(self):
        if self._connection is None:
            raise WorkbenchError('Workbench store is closed')
        return self._connection

    def _read(self, sql, parameters=()):
        try:
            rows = [dict(row) for row in self._open().execute(sql, parameters).fetchall()]
            for row in rows:
                if 'done' in row:
                    row['done'] = bool(row['done'])
            return rows
        except sqlite3.Error as error:
            raise WorkbenchError(f'Cannot read workbench: {error}') from error

    def _record(self, table, record_id):
        rows = self._read(f'SELECT * FROM {table} WHERE id=?', (_identifier(record_id),))
        if not rows:
            raise WorkbenchError('Record does not exist')
        return rows[0]

    def _project(self, project_id):
        if project_id is not None:
            self._record('projects', project_id)
        return project_id

    def _create(self, table, fields):
        fields = dict(id=str(uuid4()), **fields, created_at=_now())
        fields['updated_at'] = fields['created_at']
        placeholders = ','.join('?' for _ in fields)
        try:
            with self._open() as connection:
                connection.execute(f'INSERT INTO {table} ({",".join(fields)}) VALUES ({placeholders})',
                                   tuple(fields.values()))
                result = self._record(table, fields['id'])
            return result
        except sqlite3.Error as error:
            raise WorkbenchError(f'Cannot save workbench record: {error}') from error

    def _update(self, table, record_id, fields):
        self._record(table, record_id)
        fields = dict(fields, updated_at=_now())
        try:
            with self._open() as connection:
                cursor = connection.execute(f'UPDATE {table} SET {",".join(f"{key}=?" for key in fields)} WHERE id=?',
                                            (*fields.values(), record_id))
                if cursor.rowcount != 1:
                    raise WorkbenchError('Record does not exist')
                result = self._record(table, record_id)
            return result
        except sqlite3.Error as error:
            raise WorkbenchError(f'Cannot save workbench record: {error}') from error

    def _delete(self, table, record_id):
        _identifier(record_id)
        try:
            with self._open() as connection:
                cursor = connection.execute(f'DELETE FROM {table} WHERE id=?', (record_id,))
                if cursor.rowcount != 1:
                    raise WorkbenchError('Record does not exist')
        except sqlite3.Error as error:
            raise WorkbenchError(f'Cannot delete workbench record: {error}') from error

    def _list(self, table, project_id, include_completed=True):
        clauses, parameters = [], []
        if project_id == '':
            clauses.append('project_id IS NULL')
        elif project_id is not None:
            clauses.append('project_id=?')
            parameters.append(_identifier(project_id))
        if not include_completed:
            clauses.append('done=0')
        where = ' WHERE ' + ' AND '.join(clauses) if clauses else ''
        return self._read(f'SELECT * FROM {table}{where} ORDER BY created_at, id', parameters)

    def list_projects(self):
        return self._read('SELECT * FROM projects ORDER BY created_at, id')

    def create_project(self, name, directory=''):
        return self._create('projects', dict(name=_text(name, 'name', 200, True),
                                             directory=_text(directory, 'directory')))

    def update_project(self, id, name, directory=''):
        return self._update('projects', id, dict(name=_text(name, 'name', 200, True),
                                                 directory=_text(directory, 'directory')))

    def delete_project(self, id):
        self._delete('projects', id)

    def list_todos(self, project_id=None, include_completed=True):
        return self._list('todos', project_id, _boolean(include_completed, 'include_completed'))

    def create_todo(self, title, project_id=None, done=False):
        return self._create('todos', dict(title=_text(title, 'title', 200, True),
                                         project_id=self._project(project_id), done=_boolean(done, 'done')))

    def update_todo(self, id, title, project_id=None, done=False):
        return self._update('todos', id, dict(title=_text(title, 'title', 200, True),
                                             project_id=self._project(project_id), done=_boolean(done, 'done')))

    def delete_todo(self, id):
        self._delete('todos', id)

    # Todos handed to AI -----------------------------------------------------
    def schedule_todo(self, todo_id, run_at, provider_id, folder, prompt, model='', effort=''):
        """Hand a todo to Claude Code or Codex at ``run_at`` (epoch seconds);
        empty ``model`` / ``effort`` keep the app's own default."""
        self._record('todos', todo_id)
        if provider_id not in LINK_PROVIDERS:
            raise WorkbenchError('Only Codex and Claude Code can take a todo')
        if isinstance(run_at, bool) or not isinstance(run_at, (int, float)) or run_at != run_at:
            raise WorkbenchError('Invalid time')
        values = (todo_id, float(run_at), provider_id, _text(folder, 'folder', 2000, True),
                  _text(prompt, 'prompt', 8000, True), _text(model or '', 'model', 120),
                  _text(effort or '', 'effort', 40))
        try:
            with self._open() as connection:
                connection.execute(
                    'INSERT INTO todo_schedules (todo_id, run_at, provider_id, folder, prompt, model, effort, state) '
                    "VALUES (?,?,?,?,?,?,?,'waiting') ON CONFLICT(todo_id) DO UPDATE SET run_at=excluded.run_at, "
                    'provider_id=excluded.provider_id, folder=excluded.folder, prompt=excluded.prompt, '
                    "model=excluded.model, effort=excluded.effort, state='waiting', started_at=NULL, task_key=NULL",
                    values)
        except sqlite3.Error as error:
            raise WorkbenchError(f'Cannot save the schedule: {error}') from error
        return self.get_schedule(todo_id)

    def get_schedule(self, todo_id):
        rows = self._read('SELECT * FROM todo_schedules WHERE todo_id=?', (_identifier(todo_id),))
        return rows[0] if rows else None

    def list_schedules(self, states=None):
        if states is None:
            return self._read('SELECT * FROM todo_schedules ORDER BY run_at, todo_id')
        states = [state for state in states if state in SCHEDULE_STATES]
        marks = ','.join('?' for _ in states) or "''"
        return self._read(f'SELECT * FROM todo_schedules WHERE state IN ({marks}) ORDER BY run_at, todo_id',
                          states)

    def update_schedule(self, todo_id, **fields):
        allowed = {'state', 'started_at', 'task_key', 'note_id', 'run_at'}
        if not fields or set(fields) - allowed:
            raise WorkbenchError('Invalid schedule update')
        if 'state' in fields and fields['state'] not in SCHEDULE_STATES:
            raise WorkbenchError('Invalid schedule state')
        try:
            with self._open() as connection:
                cursor = connection.execute(
                    f'UPDATE todo_schedules SET {",".join(f"{key}=?" for key in fields)} WHERE todo_id=?',
                    (*fields.values(), _identifier(todo_id)))
                if cursor.rowcount != 1:
                    raise WorkbenchError('Schedule does not exist')
        except sqlite3.Error as error:
            raise WorkbenchError(f'Cannot save the schedule: {error}') from error
        return self.get_schedule(todo_id)

    def unschedule(self, todo_id):
        try:
            with self._open() as connection:
                connection.execute('DELETE FROM todo_schedules WHERE todo_id=?', (_identifier(todo_id),))
        except sqlite3.Error as error:
            raise WorkbenchError(f'Cannot remove the schedule: {error}') from error

    def _write(self, sql, parameters=()):
        try:
            with self._open() as connection:
                return connection.execute(sql, parameters).rowcount
        except sqlite3.Error as error:
            raise WorkbenchError(f'Cannot save workbench record: {error}') from error

    # 2.0: project start presets ----------------------------------------------
    def get_preset(self, project_id):
        rows = self._read('SELECT * FROM project_presets WHERE project_id=?', (_identifier(project_id),))
        return rows[0] if rows else None

    def set_preset(self, project_id, provider_id, folder, prompt, model='', effort=''):
        """How this project starts work: which app, folder, model and opening prompt."""
        self._record('projects', project_id)
        if provider_id not in LINK_PROVIDERS:
            raise WorkbenchError('Only Codex and Claude Code can start a project')
        self._write(
            'INSERT INTO project_presets VALUES (?,?,?,?,?,?,?) ON CONFLICT(project_id) DO UPDATE SET '
            'provider_id=excluded.provider_id, folder=excluded.folder, prompt=excluded.prompt, '
            'model=excluded.model, effort=excluded.effort, updated_at=excluded.updated_at',
            (project_id, provider_id, _text(folder, 'folder', 2000, True), _text(prompt, 'prompt', 8000),
             _text(model or '', 'model', 120), _text(effort or '', 'effort', 40), _now()))
        return self.get_preset(project_id)

    def delete_preset(self, project_id):
        self._write('DELETE FROM project_presets WHERE project_id=?', (_identifier(project_id),))

    # 2.0: "where to continue next time" ---------------------------------------
    def add_handoff(self, project_id, body):
        self._record('projects', project_id)
        record = dict(id=str(uuid4()), project_id=project_id, body=_text(body, 'note', 2000, True),
                      created_at=_now())
        self._write('INSERT INTO handoff_notes VALUES (?,?,?,?)', tuple(record.values()))
        return record

    def latest_handoff(self, project_id):
        rows = self._read('SELECT * FROM handoff_notes WHERE project_id=? ORDER BY created_at DESC, id LIMIT 1',
                          (_identifier(project_id),))
        return rows[0] if rows else None

    def list_handoffs(self, project_id):
        return self._read('SELECT * FROM handoff_notes WHERE project_id=? ORDER BY created_at DESC, id',
                          (_identifier(project_id),))

    def delete_handoff(self, id):
        self._delete('handoff_notes', id)

    # 2.0: focus sessions ------------------------------------------------------
    def start_focus(self, started_at, planned_s, project_id=None, todo_id=None):
        if isinstance(planned_s, bool) or not isinstance(planned_s, (int, float)) or not 0 < planned_s <= 6 * 3600:
            raise WorkbenchError('Invalid focus length')
        self._project(project_id)
        if todo_id is not None:
            self._record('todos', todo_id)
        record = dict(id=str(uuid4()), started_at=float(started_at), planned_s=float(planned_s),
                      ended_at=None, completed=0, project_id=project_id, todo_id=todo_id)
        self._write('INSERT INTO focus_sessions VALUES (?,?,?,?,?,?,?)', tuple(record.values()))
        return self._record('focus_sessions', record['id'])

    def end_focus(self, id, ended_at, completed):
        if self._write('UPDATE focus_sessions SET ended_at=?, completed=? WHERE id=? AND ended_at IS NULL',
                       (float(ended_at), int(_boolean(completed, 'completed')), _identifier(id))) != 1:
            raise WorkbenchError('Focus session does not exist or already ended')
        return self._record('focus_sessions', id)

    def list_focus(self, since=None):
        rows = self._read('SELECT * FROM focus_sessions WHERE ended_at IS NOT NULL AND ended_at >= ? '
                          'ORDER BY started_at, id', (float(since or 0),))
        for row in rows:
            row['completed'] = bool(row['completed'])
        return rows

    def todos_done_between(self, start, end):
        """Todos ticked off in a time window (by their last change)."""
        def iso(epoch):
            return datetime.fromtimestamp(epoch, timezone.utc).isoformat(timespec='microseconds')
        return self._read('SELECT * FROM todos WHERE done=1 AND updated_at >= ? AND updated_at < ? '
                          'ORDER BY updated_at, id', (iso(start), iso(end)))

    # 2.0: weekly project usage goals -----------------------------------------
    def get_goal(self, project_id):
        rows = self._read('SELECT * FROM usage_goals WHERE project_id=?', (_identifier(project_id),))
        return rows[0] if rows else None

    def list_goals(self):
        return self._read('SELECT * FROM usage_goals ORDER BY project_id')

    def set_goal(self, project_id, weekly_tokens=None, weekly_usd=None):
        """A weekly limit in tokens and/or money; both None removes it."""
        self._record('projects', project_id)
        for value in (weekly_tokens, weekly_usd):
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))
                                      or not value > 0 or value != value):
                raise WorkbenchError('Invalid goal')
        if weekly_tokens is None and weekly_usd is None:
            self._write('DELETE FROM usage_goals WHERE project_id=?', (project_id,))
            return None
        self._write('INSERT INTO usage_goals VALUES (?,?,?,?) ON CONFLICT(project_id) DO UPDATE SET '
                    'weekly_tokens=excluded.weekly_tokens, weekly_usd=excluded.weekly_usd, '
                    'updated_at=excluded.updated_at',
                    (project_id, None if weekly_tokens is None else int(weekly_tokens),
                     None if weekly_usd is None else float(weekly_usd), _now()))
        return self.get_goal(project_id)

    # 2.0: stickers and companionship points -----------------------------------
    def earn(self, achievement_id, at):
        """Record a sticker once; True only the first time."""
        _text(achievement_id, 'sticker', 64, True)
        return self._write('INSERT OR IGNORE INTO achievements VALUES (?,?)', (achievement_id, float(at))) == 1

    def achievements(self):
        return {row['id']: row['earned_at'] for row in self._read('SELECT * FROM achievements')}

    def add_points(self, reason, ref, points, at):
        """Award points once per (reason, ref); True when newly added."""
        if isinstance(points, bool) or not isinstance(points, int) or points <= 0:
            raise WorkbenchError('Invalid points')
        return self._write('INSERT OR IGNORE INTO points_ledger VALUES (?,?,?,?)',
                           (_text(reason, 'reason', 40, True), _text(ref, 'ref', 200, True),
                            float(at), points)) == 1

    def points(self):
        rows = self._read('SELECT COALESCE(SUM(points), 0) AS total FROM points_ledger')
        return rows[0]['total']

    def points_log(self, limit=50):
        return self._read('SELECT * FROM points_ledger ORDER BY at DESC LIMIT ?', (int(limit),))

    def count_points(self, reason):
        return self._read('SELECT COUNT(*) AS n FROM points_ledger WHERE reason=?', (reason,))[0]['n']

    def list_notes(self, project_id=None):
        return self._list('notes', project_id)

    def get_note(self, id):
        return self._record('notes', id)

    def create_note(self, title, body='', project_id=None):
        return self._create('notes', dict(title=_text(title, 'title', 200, True),
                                         body=_text(body, 'body', 1_000_000), project_id=self._project(project_id)))

    def update_note(self, id, title, body, project_id=None):
        return self._update('notes', id, dict(title=_text(title, 'title', 200, True),
                                             body=_text(body, 'body', 1_000_000), project_id=self._project(project_id)))

    def delete_note(self, id):
        self._delete('notes', id)

    def link_task(self, provider_id, task_key, project_id=None):
        if provider_id not in LINK_PROVIDERS:
            raise WorkbenchError('Only Codex and Claude Code tasks can be linked')
        _text(task_key, 'task key', required=True)
        self._project(project_id)
        try:
            with self._open() as connection:
                if project_id is None:
                    connection.execute('DELETE FROM task_links WHERE provider_id=? AND task_key=?',
                                       (provider_id, task_key))
                else:
                    connection.execute('INSERT INTO task_links VALUES (?,?,?) ON CONFLICT(provider_id,task_key) '
                                       'DO UPDATE SET project_id=excluded.project_id',
                                       (provider_id, task_key, project_id))
        except sqlite3.Error as error:
            raise WorkbenchError(f'Cannot save task link: {error}') from error

    def task_links(self):
        return {(row['provider_id'], row['task_key']): row['project_id']
                for row in self._read('SELECT * FROM task_links ORDER BY provider_id,task_key')}

    def close(self):
        if self._connection is not None:
            self._connection.close()
            self._connection = None
