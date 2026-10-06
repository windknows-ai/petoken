"""Read explicit local Codex thread metadata, lifecycle and confirmed edit paths."""
from __future__ import annotations

from contextlib import closing
from datetime import datetime
import json
import math
import ntpath
from pathlib import Path
import posixpath
import sqlite3

from codex_compat import inspect_table, state_database


TOP_LEVEL_SOURCES = frozenset({'desktop', 'vscode', 'cli', 'exec'})


def thread_rows(home):
    """Metadata only, including archived threads; missing structures yield []."""
    database = state_database(Path(home))
    if database is None:
        return []
    optional = {key: 'TEXT' for key in ('rollout_path', 'source', 'cwd', 'title',
                                      'name', 'project_id', 'git_origin_url')}
    try:
        with closing(sqlite3.connect(database.resolve().as_uri() + '?mode=ro',
                                     uri=True, timeout=.2)) as connection:
            connection.row_factory = sqlite3.Row
            schema = inspect_table(connection, 'threads', {'id': 'TEXT'}, optional)
            if schema['status'] == 'unsupported':
                return []
            fields = ','.join('"' + field + '"' for field in schema['valid_fields'])
            rows = [dict(row) for row in connection.execute('SELECT ' + fields + ' FROM threads')]
        for row in rows:
            for key, value in tuple(row.items()):
                if not isinstance(value, str):
                    row[key] = None
        return [row for row in rows if row.get('id')]
    except (OSError, ValueError, sqlite3.Error):
        return []


def thread_info(home, thread_id):
    if not isinstance(thread_id, str) or not thread_id:
        return None
    rows = [row for row in thread_rows(home) if row['id'] == thread_id]
    return rows[0] if len(rows) == 1 else None


def epoch(value):
    """Explicit epoch seconds or a timezone-bearing ISO timestamp; no unit guesses."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value) if math.isfinite(value) and value >= 0 else None
    if isinstance(value, str):
        try:
            stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
            return stamp.timestamp() if stamp.tzinfo is not None else None
        except (ValueError, OverflowError, OSError):
            pass
    return None


def _relative(path, root, cwd):
    if not all(isinstance(value, str) and value and '\0' not in value
               for value in (path, root, cwd)):
        return None
    paths = ntpath if ntpath.splitdrive(root)[0] else posixpath
    if not paths.isabs(root) or not paths.isabs(cwd):
        return None
    target = paths.normpath(path if paths.isabs(path) else paths.join(cwd, path))
    try:
        if paths.normcase(paths.commonpath([root, target])) != paths.normcase(paths.normpath(root)):
            return None
        relative = paths.relpath(target, root)
    except ValueError:
        return None
    return relative.replace('\\', '/') if relative != '.' else None


def _ledger_times(home, thread_id):
    path = Path(home)/'thread_history_1.sqlite'
    required = {'thread_id': 'TEXT', 'turn_id': 'TEXT', 'status': 'TEXT',
                'started_at': ('INTEGER', 'REAL')}
    optional = {'completed_at': ('INTEGER', 'REAL'), 'rollout_ordinal': 'INTEGER'}
    try:
        with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro',
                                     uri=True, timeout=.2)) as connection:
            connection.row_factory = sqlite3.Row
            schema = inspect_table(connection, 'thread_turns', required, optional)
            if schema['status'] == 'unsupported':
                return None, None
            fields = ','.join('"' + field + '"' for field in schema['valid_fields'])
            order = 'rollout_ordinal' if 'rollout_ordinal' in schema['valid_fields'] else 'started_at'
            rows = [dict(row) for row in connection.execute(
                'SELECT ' + fields + ' FROM thread_turns WHERE thread_id=? ORDER BY ' + order + ',rowid',
                (thread_id,))]
        if not rows:
            return None, None
        starts = [epoch(row['started_at']) for row in rows]
        start = min(starts) if all(value is not None for value in starts) else None
        last = rows[-1]
        finish = (epoch(last.get('completed_at'))
                  if last['status'] in ('completed', 'failed', 'interrupted') else None)
        return start, finish
    except (OSError, ValueError, sqlite3.Error):
        return None, None


def _rollout_summary(row):
    """Scan one log without retaining messages, patch bodies or command contents."""
    unknown = dict(files=None, started_at=None, finished_at=None, duration_s=None)
    path = row.get('rollout_path')
    if not path:
        return unknown, False
    root = cwd = row.get('cwd')
    files, calls = set(), set()
    observed_edits = False
    start = finish = None
    active_turn = None
    lifecycle = False
    start_seen = False
    metadata = False
    fork_at = None
    try:
        with Path(path).open('rb') as stream:
            for line in stream:
                if not line.endswith(b'\n'):
                    return unknown, True  # The terminal record may still be being written.
                event = json.loads(line)
                if not isinstance(event, dict) or not isinstance(event.get('payload'), dict):
                    return unknown, True
                payload = event['payload']
                kind = event.get('type')
                stamp = epoch(event.get('timestamp'))
                if kind == 'session_meta' and not metadata:
                    if payload.get('id') != row['id']:
                        return unknown, True
                    metadata = True
                    root = root or payload.get('cwd')
                    cwd = payload.get('cwd') or root
                    if payload.get('forked_from_id'):
                        fork_at = epoch(payload.get('timestamp'))
                        if fork_at is None:
                            return unknown, True
                    continue
                if not metadata:
                    return unknown, True
                if fork_at is not None and (stamp is None or stamp < fork_at):
                    continue
                if payload.get('thread_id', row['id']) != row['id']:
                    continue
                if kind == 'turn_context':
                    cwd = payload.get('cwd') or cwd
                if kind == 'response_item':
                    call_id = payload.get('call_id')
                    if (payload.get('type') in ('function_call', 'custom_tool_call')
                            and payload.get('name') in ('apply_patch', 'functions.apply_patch')
                            and isinstance(call_id, str)):
                        calls.add(call_id)
                    elif (payload.get('type') in ('function_call_output', 'custom_tool_call_output')
                          and isinstance(call_id, str) and call_id in calls):
                        calls.discard(call_id)
                        output = payload.get('output')
                        if isinstance(output, str) and output.startswith('Success. Updated the following files:\n'):
                            for entry in output.splitlines()[1:]:
                                if len(entry) < 3 or entry[:2] not in ('A ', 'M ', 'D '):
                                    return unknown, True
                                relative = _relative(entry[2:], root, cwd)
                                if relative:
                                    files.add(relative)
                            observed_edits = True
                if kind != 'event_msg':
                    continue
                tag = payload.get('type')
                if tag in ('task_started', 'turn_started'):
                    lifecycle = True
                    value = epoch(payload.get('started_at'))
                    value = stamp if value is None else value
                    if not start_seen:
                        start = value
                        start_seen = True
                    active_turn = payload.get('turn_id')
                    finish = None
                elif tag in ('task_complete', 'turn_complete', 'turn_aborted'):
                    if active_turn is not None and payload.get('turn_id') != active_turn:
                        continue
                    lifecycle = True
                    if not start_seen:
                        start = epoch(payload.get('started_at'))
                        start_seen = True
                    value = epoch(payload.get('completed_at'))
                    finish = stamp if value is None else value
                changes = None
                if tag == 'patch_apply_end' and payload.get('success') is True and payload.get('status') in (None, 'completed'):
                    changes = payload.get('changes')
                elif tag == 'item_completed':
                    item = payload.get('item')
                    if isinstance(item, dict) and item.get('type') == 'FileChange' and item.get('status') == 'completed':
                        changes = item.get('changes')
                if isinstance(changes, dict):
                    observed_edits = True
                    for name, change in changes.items():
                        if not isinstance(change, dict) or change.get('type') not in ('add', 'delete', 'update'):
                            return unknown, True
                        for changed in (name, change.get('move_path')):
                            relative = _relative(changed, root, cwd)
                            if relative:
                                files.add(relative)
        if not metadata:
            return unknown, False
    except OSError:
        return unknown, False
    except (ValueError, TypeError):
        return unknown, True
    if start is not None and finish is not None and finish < start:
        finish = None
    duration = finish - start if start is not None and finish is not None else None
    return dict(files=sorted(files) if observed_edits and root else None,
                started_at=start, finished_at=finish, duration_s=duration), lifecycle


def recap_row(home, row):
    result, lifecycle = _rollout_summary(row)
    if not lifecycle:
        start, finish = _ledger_times(home, row['id'])
        if start is not None and finish is not None and finish < start:
            finish = None
        result.update(started_at=start, finished_at=finish,
                      duration_s=finish - start if start is not None and finish is not None else None)
    return result


def recap(home, thread_id):
    """Confirmed paths and thread elapsed time, in UTC epoch seconds (or None)."""
    row = thread_info(home, thread_id)
    return recap_row(home, row) if row else dict(files=None, started_at=None,
                                                finished_at=None, duration_s=None)
