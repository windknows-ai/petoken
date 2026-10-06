"""Error log and "Export diagnostics" (V1.7).

Petoken runs without a console, so an unexpected error used to vanish.
``install_error_log`` appends uncaught exceptions (Qt slots, threads and the
main loop) to ``%LOCALAPPDATA%\\CodexWisp\\errors.log``, trimmed to the last
MAX_LOG_BYTES.

``collect`` gathers what helps with a bug report into named text sections;
the Settings dialog shows every section before ``write_zip`` saves them.
Included: versions, which features are on, the error log, the approval step
log (times, short IDs, tool names) and notification counts. Never included:
conversation or file contents, prompts, commands, folder paths or
credentials (preferences are copied with folder lists reduced to a count).
"""
from __future__ import annotations

import json
import platform
import sqlite3
import sys
import threading
import time
import traceback
import zipfile
from contextlib import closing
from pathlib import Path

MAX_LOG_BYTES = 256 * 1024
TAIL_LINES = 300
_PRIVATE_PREFS = ('launch_folders',)


def error_log_path(folder):
    return Path(folder) / 'errors.log'


def _trim(path):
    try:
        if path.stat().st_size > MAX_LOG_BYTES:
            data = path.read_bytes()[-MAX_LOG_BYTES // 2:]
            path.write_bytes(data[data.find(b'\n') + 1:])
    except OSError:
        pass


def record_error(folder, kind, value, tb, where='main'):
    path = error_log_path(folder)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        text = ''.join(traceback.format_exception(kind, value, tb))
        with path.open('a', encoding='utf-8') as handle:
            handle.write(f'--- {time.strftime("%Y-%m-%d %H:%M:%S")} ({where})\n{text}')
        _trim(path)
    except OSError:
        pass


def install_error_log(folder):
    """Log uncaught exceptions from the main thread, Qt slots and threads."""
    previous = sys.excepthook

    def hook(kind, value, tb):
        record_error(folder, kind, value, tb)
        if previous is not None and previous is not sys.__excepthook__:
            previous(kind, value, tb)

    def thread_hook(args):
        if args.exc_type is not SystemExit:
            record_error(folder, args.exc_type, args.exc_value, args.exc_traceback,
                         where=f'thread {getattr(args.thread, "name", "?")}')

    sys.excepthook = hook
    threading.excepthook = thread_hook


def _tail(path, lines=TAIL_LINES):
    try:
        return '\n'.join(Path(path).read_text(encoding='utf-8', errors='replace').splitlines()[-lines:])
    except OSError:
        return ''


def _preferences(prefs):
    safe = {}
    for key, value in (prefs or {}).items():
        if key in _PRIVATE_PREFS:
            safe[key] = f'<{len(value) if isinstance(value, list) else 0} folders, not included>'
        else:
            safe[key] = value
    return json.dumps(safe, ensure_ascii=False, indent=1, default=str)


def _notification_counts(path, days=7):
    try:
        with closing(sqlite3.connect(f'file:{path}?mode=ro', uri=True)) as db:
            rows = db.execute('SELECT kind, COUNT(*) FROM events WHERE at > ? GROUP BY kind ORDER BY kind',
                              (time.time() - days * 86400,)).fetchall()
    except sqlite3.Error:
        return 'unavailable'
    return '\n'.join(f'{kind}: {count}' for kind, count in rows) or 'none'


def collect(folder, prefs, version, features):
    """{file name: text} for the diagnostics zip. ``features``: {name: state}."""
    folder = Path(folder)
    try:
        from PySide6 import __version__ as pyside
    except Exception:
        pyside = '?'
    about = '\n'.join([
        f'Petoken {version}',
        f'Windows {platform.version()} ({platform.machine()})',
        f'Python {platform.python_version()}, PySide6 {pyside}',
        f'Frozen build: {bool(getattr(sys, "frozen", False))}',
        f'Exported {time.strftime("%Y-%m-%d %H:%M:%S %z")}',
    ])
    return {
        'about.txt': about,
        'features.txt': '\n'.join(f'{name}: {state}' for name, state in features.items()),
        'preferences.json': _preferences(prefs),
        'errors.log': _tail(error_log_path(folder)) or '(no errors recorded)',
        'approval-steps.log': _tail(folder / 'claude-approvals' / 'events.log') or '(empty)',
        'notifications-7-days.txt': _notification_counts(folder / 'notifications.sqlite3'),
    }


def write_zip(path, sections):
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, body in sections.items():
            archive.writestr(name, body)
    return Path(path)
