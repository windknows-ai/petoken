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
        try:
            return float(value) if math.isfinite(value) and value >= 0 else None
        except OverflowError:
            return None
    if isinstance(value, str):
        try:
            stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
            return stamp.timestamp() if stamp.tzinfo is not None else None
        except (ValueError, OverflowError, OSError):
            pass
    return None


def _without_extended_prefix(path):
    if path[:8].upper() == '\\\\?\\UNC\\':
        return '\\\\' + path[8:]
    return path[4:] if path.startswith('\\\\?\\') else path


def _relative(path, root, cwd):
    if not all(isinstance(value, str) and value and '\0' not in value
               for value in (path, root, cwd)):
        return None
    path, root, cwd = map(_without_extended_prefix, (path, root, cwd))
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


def _rollout_events(row):
    """Validated, thread-local events with the same cwd/fork rules for all readers."""
    root = cwd = row.get('cwd')
    metadata = False
    fork_at = None
    with Path(row['rollout_path']).open('rb') as stream:
        for line in stream:
            if not line.endswith(b'\n'):
                raise ValueError('incomplete rollout record')
            event = json.loads(line)
            if not isinstance(event, dict) or not isinstance(event.get('payload'), dict):
                raise ValueError('invalid rollout record')
            payload = event['payload']
            kind = event.get('type')
            stamp = epoch(event.get('timestamp'))
            if kind == 'session_meta' and not metadata:
                if payload.get('id') != row['id']:
                    raise ValueError('mismatched rollout identity')
                metadata = True
                root = root or payload.get('cwd')
                cwd = payload.get('cwd') or root
                if payload.get('forked_from_id'):
                    fork_at = epoch(payload.get('timestamp'))
                    if fork_at is None:
                        raise ValueError('unknown fork boundary')
                continue
            if not metadata:
                raise ValueError('missing rollout identity')
            if fork_at is not None and (stamp is None or stamp < fork_at):
                continue
            if payload.get('thread_id', row['id']) != row['id']:
                continue
            if kind == 'turn_context':
                cwd = payload.get('cwd') or cwd
            yield event, payload, root, cwd, stamp


def _changed_paths(payload, root, cwd):
    tag = payload.get('type')
    changes = None
    if tag == 'patch_apply_end' and payload.get('success') is True and payload.get('status') in (None, 'completed'):
        changes = payload.get('changes')
    elif tag == 'item_completed':
        item = payload.get('item')
        if isinstance(item, dict) and item.get('type') == 'FileChange' and item.get('status') == 'completed':
            changes = item.get('changes')
    if not isinstance(changes, dict):
        return None
    paths = set()
    for name, change in changes.items():
        if not isinstance(change, dict) or change.get('type') not in ('add', 'delete', 'update'):
            raise ValueError('invalid file change')
        for changed in (name, change.get('move_path')):
            relative = _relative(changed, root, cwd)
            if relative:
                paths.add(relative)
    return paths


def _rollout_summary(row):
    """Scan one log without retaining messages, patch bodies or command contents."""
    unknown = dict(files=None, started_at=None, finished_at=None, duration_s=None)
    if not row.get('rollout_path'):
        return unknown, False
    root = row.get('cwd')
    files, calls = set(), set()
    observed_edits = False
    start = finish = None
    active_turn = None
    lifecycle = False
    start_seen = False
    try:
        for event, payload, root, cwd, stamp in _rollout_events(row):
            kind = event.get('type')
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
            changed = _changed_paths(payload, root, cwd)
            if changed is not None:
                observed_edits = True
                files.update(changed)
    except OSError:
        return unknown, False
    except (ValueError, TypeError):
        return unknown, True
    if start is not None and finish is not None and finish < start:
        finish = None
    duration = finish - start if start is not None and finish is not None else None
    return dict(files=sorted(files) if observed_edits and root else None,
                started_at=start, finished_at=finish, duration_s=duration), lifecycle


def _turn_error(payload):
    """Protocol ErrorEvent affects replayed turn status, excluding control errors."""
    if not isinstance(payload, dict) or not isinstance(payload.get('message'), str):
        return None
    if payload.get('willRetry') is True:
        return False
    info = payload.get('codex_error_info')
    if info is None:
        return True
    name = info if isinstance(info, str) else next(iter(info), None) if isinstance(info, dict) and len(info) == 1 else None
    if not isinstance(name, str):
        return None
    name = name.replace('_', '').lower()
    if name in ('threadrollbackfailed', 'activeturnnotsteerable'):
        return False
    return True if name in (
        'contextwindowexceeded', 'sessionbudgetexceeded', 'usagelimitexceeded', 'ratelimitexceeded',
        'flexunavailable', 'serveroverloaded', 'cyberpolicy', 'biopolicy', 'misalignmentpolicyviolation',
        'toomanydenials', 'httpconnectionfailed', 'responsestreamconnectionfailed', 'internalservererror',
        'unauthorized', 'badrequest', 'invalidprompt', 'sandboxerror', 'responsestreamdisconnected',
        'responsetoomanyfailedattempts', 'other') else None


def _terminal_outcome(payload, error=False):
    """Only terminal lifecycle events, never an individual tool/error event."""
    if payload.get('type') not in ('task_complete', 'turn_complete', 'turn_aborted'):
        return None
    if 'status' in payload:
        status = payload['status']
        return status if status in ('completed', 'failed', 'interrupted') else None
    if payload.get('type') == 'turn_aborted':
        return 'interrupted'
    if payload.get('error') is not None:
        error = _turn_error(payload['error'])
    return 'failed' if error is True else 'completed' if error is False else None


def turn_outcome(home, thread_id):
    """Latest explicit local turn outcome; a subsequent start resets it to None.

    Does not connect to app-server or infer completion from time/inactivity.
    Missing, corrupt, incomplete or mismatched rollouts return None.
    """
    row = thread_info(home, thread_id)
    if not row or not row.get('rollout_path'):
        return None
    outcome = active_turn = None
    started = False
    in_turn = False
    error = False
    try:
        for event, payload, _root, _cwd, _stamp in _rollout_events(row):
            if event.get('type') != 'event_msg':
                continue
            tag = payload.get('type')
            if tag in ('task_started', 'turn_started'):
                active_turn = payload.get('turn_id')
                started = True
                in_turn = True
                outcome = None
                error = False
            elif tag == 'error' and in_turn and payload.get('turn_id', active_turn) == active_turn:
                current = _turn_error(payload)
                if current is not False and error is not True:
                    error = current
            elif tag in ('task_complete', 'turn_complete', 'turn_aborted'):
                if started and (not in_turn or payload.get('turn_id') != active_turn):
                    continue
                outcome = _terminal_outcome(payload, error)
                in_turn = False
    except (OSError, ValueError, TypeError):
        return None
    return outcome


def _rollout_activity(row, since, project):
    turns, edits = [], []
    started = active_turn = None
    in_turn = False
    error = False
    for event, payload, root, cwd, stamp in _rollout_events(row):
        if event.get('type') != 'event_msg':
            continue
        tag = payload.get('type')
        if tag in ('task_started', 'turn_started'):
            value = epoch(payload.get('started_at'))
            started = stamp if value is None else value
            active_turn = payload.get('turn_id')
            in_turn = True
            error = False
        elif tag == 'error' and in_turn and payload.get('turn_id', active_turn) == active_turn:
            current = _turn_error(payload)
            if current is not False and error is not True:
                error = current
        elif tag in ('task_complete', 'turn_complete', 'turn_aborted'):
            if in_turn and payload.get('turn_id') == active_turn:
                value = epoch(payload.get('completed_at'))
                ended = stamp if value is None else value
                if started is not None and ended is not None and ended >= max(since, started):
                    turns.append((started, ended, project, _terminal_outcome(payload, error)))
                in_turn = False
        if stamp is not None and stamp >= since:
            changed = _changed_paths(payload, root, cwd)
            if changed:
                edits.extend((stamp, project, relative) for relative in sorted(changed))
    return turns, edits


def activity(home, since):
    """Explicit per-turn and edit activity, sorted by UTC epoch seconds.

    Turns are (start, end, project, outcome), with an unknown outcome as None.

    Only rollouts with filesystem mtime >= since are read. task_started is
    accepted as the local Codex alias of turn_started. Running/unknown turns
    are omitted; projects use the existing project-name resolution (or None).
    Archived and independent subagent turns remain history, while inherited
    fork events and duplicate/conflicting index entries are not counted again.
    Unknown cutoffs and unreadable/corrupt logs return no inferred activity.
    """
    result = dict(turns=[], edits=[])
    since = epoch(since)
    if since is None:
        return result
    # usage imports recap helpers, so resolve its pure project helper lazily.
    from usage import project_identity
    try:
        state = json.loads((Path(home)/'.codex-global-state.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        state = {}
    rows = {}
    for row in thread_rows(home):
        key = row['id']
        if key not in rows:
            rows[key] = row
        elif rows[key] != row:
            rows[key] = None
    for row in rows.values():
        if not row or not row.get('rollout_path'):
            continue
        try:
            if Path(row['rollout_path']).stat().st_mtime < since:
                continue
            turns, edits = _rollout_activity(row, since, project_identity(row, state)[0])
        except (OSError, ValueError, TypeError):
            continue
        result['turns'].extend(turns)
        result['edits'].extend(edits)
    result['turns'].sort(key=lambda item: (item[0], item[1], item[2] or ''))
    result['edits'].sort(key=lambda item: (item[0], item[1] or '', item[2]))
    return result


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
