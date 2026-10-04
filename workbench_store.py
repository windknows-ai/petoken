"""Transactional local projects, todos, notes and explicit Codex task links."""
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from uuid import UUID, uuid4


class WorkbenchError(Exception):
    """A validation, storage or unsupported-database failure."""


_APPLICATION_ID = 0x50545742
_SCHEMA_VERSION = 1
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
        provider_id TEXT NOT NULL CHECK (provider_id = 'codex'), task_key TEXT NOT NULL,
        project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        PRIMARY KEY (provider_id, task_key))''',
}


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
            self._validate_schema()
        except (OSError, ValueError, TypeError, sqlite3.Error, WorkbenchError) as error:
            self.close()
            if isinstance(error, WorkbenchError):
                raise
            raise WorkbenchError(f'Cannot open workbench database: {error}') from error

    def _validate_schema(self):
        connection = self._connection
        if (connection.execute('PRAGMA application_id').fetchone()[0] != _APPLICATION_ID
                or connection.execute('PRAGMA user_version').fetchone()[0] != _SCHEMA_VERSION):
            raise WorkbenchError('Unrecognized or unsupported workbench database')
        # Exact owned schema also verifies the delete actions and constraints;
        # reject extra triggers/views/indexes that could change write semantics.
        objects = connection.execute('SELECT name, type, sql FROM sqlite_master WHERE sql IS NOT NULL').fetchall()
        actual = {row['name']: ' '.join(row['sql'].split())
                  for row in objects if row['type'] == 'table'}
        expected = {name: ' '.join(sql.split()) for name, sql in _SCHEMA.items()}
        if len(objects) != len(_SCHEMA) or actual != expected:
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
        if provider_id != 'codex':
            raise WorkbenchError('Only Codex tasks can be linked')
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
