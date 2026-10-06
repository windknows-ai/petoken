"""Notification center core (V1.6): events, history, quiet hours, reminders.

Sources feed normalized events into ``NotificationCenter.ingest``:
- Claude Code hooks (``claude_events``): finished / failed / needs approval,
  under a second after Claude Code reports them.
- Polling (both providers): a running task that leaves the verified active
  set while it was recently active counts as finished. For Codex this is
  the reliable path today (see docs/V1_6_CODEX_EVENTS.md); for Claude it is
  the fallback when hooks are off.
- Quota: the 5-hour window dropping to QUOTA_LOW_LEFT % left, once per
  window.
- Personal reminders (once / daily / weekly), optionally tied to a todo.

Every event is stored once (unique ``dedupe`` key) for RETENTION_DAYS; the
same task/kind from two sources within DUPLICATE_WINDOW_S is one event.
Quiet hours record history but emit nothing. Nothing from before Petoken
started is ever announced.
"""
from __future__ import annotations

import json
import sqlite3
import time
from contextlib import closing, contextmanager
from datetime import datetime, timedelta
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from usage import quota_window

KINDS = ('finished', 'failed', 'needs_approval', 'quota_low', 'reminder',
         # V1.6 predictions and suggestions (forecast.py).
         'forecast', 'context_full', 'stuck', 'quota_back')
REPEATS = ('once', 'daily', 'weekly')
RETENTION_DAYS = 30
DUPLICATE_WINDOW_S = 120
QUOTA_LOW_LEFT = 20
# A task that vanishes from the active set counts as finished only if it was
# active this recently; older disappearances are source changes, not results.
POLL_RECENT_S = 120

_SCHEMA = '''
CREATE TABLE IF NOT EXISTS events(
    id INTEGER PRIMARY KEY, at REAL NOT NULL, kind TEXT NOT NULL,
    provider TEXT NOT NULL DEFAULT '', task_key TEXT NOT NULL DEFAULT '',
    project TEXT NOT NULL DEFAULT '', detail TEXT NOT NULL DEFAULT '',
    dedupe TEXT NOT NULL UNIQUE);
CREATE INDEX IF NOT EXISTS events_at ON events(at);
CREATE TABLE IF NOT EXISTS reminders(
    id INTEGER PRIMARY KEY, title TEXT NOT NULL,
    repeat TEXT NOT NULL CHECK(repeat IN ('once', 'daily', 'weekly')),
    minute INTEGER NOT NULL CHECK(minute BETWEEN 0 AND 1439),
    weekday INTEGER CHECK(weekday BETWEEN 0 AND 6),
    day TEXT, todo_id INTEGER, next_at REAL);
'''


def next_occurrence(repeat, minute, weekday=None, day=None, after=None):
    """Next firing time (epoch seconds) strictly after ``after``, or None."""
    after = time.time() if after is None else after
    base = datetime.fromtimestamp(after)
    hour, mins = divmod(int(minute), 60)
    if repeat == 'once':
        try:
            when = datetime.strptime(day, '%Y-%m-%d').replace(hour=hour, minute=mins)
        except (TypeError, ValueError):
            return None
        return when.timestamp() if when.timestamp() > after else None
    when = base.replace(hour=hour, minute=mins, second=0, microsecond=0)
    if repeat == 'daily':
        if when.timestamp() <= after:
            when += timedelta(days=1)
        return when.timestamp()
    if repeat == 'weekly' and isinstance(weekday, int) and 0 <= weekday <= 6:
        when += timedelta(days=(weekday - when.weekday()) % 7)
        if when.timestamp() <= after:
            when += timedelta(days=7)
        return when.timestamp()
    return None


def recap_detail(recap):
    """A task recap as the stored ``detail`` of a finished event."""
    files = recap.get('files')
    data = dict(files=None if files is None else len(files),
                names=list(files or [])[:20],
                seconds=None if recap.get('duration_s') is None else round(recap['duration_s']),
                usd=recap.get('usd'))
    return json.dumps(data, ensure_ascii=False)


def parse_recap(detail):
    """The recap dict from a finished event's ``detail``, or None."""
    if not isinstance(detail, str) or not detail.startswith('{'):
        return None
    try:
        data = json.loads(detail)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def recap_text(detail, language, currency='USD', rates=None):
    """'3 files changed · 4m 12s · CA$0.58' (only the parts that are known)."""
    from localization import text
    from pricing import convert_usd, format_cost
    from usage_overlay import format_duration
    data = parse_recap(detail)
    if data is None:
        return ''
    parts = []
    files = data.get('files')
    if isinstance(files, int):
        parts.append(text('recap_files', language, count=files) if files else text('recap_no_files', language))
    seconds = data.get('seconds')
    if isinstance(seconds, (int, float)):
        # Elapsed, not a countdown: exact under an hour (42s, 4m 12s).
        minutes, rest = divmod(int(seconds), 60)
        parts.append(format_duration(seconds) if minutes >= 60 else
                     f'{minutes}m {rest}s' if minutes else f'{rest}s')
    usd = data.get('usd')
    if isinstance(usd, (int, float)):
        value = convert_usd(usd, currency, rates or {}) if currency != 'USD' else usd
        if value is None:
            value, currency = usd, 'USD'
        parts.append('≈ ' + format_cost(value, currency))
    return ' · '.join(parts)


def _minutes(value, fallback):
    try:
        hours, mins = (int(part) for part in str(value).split(':'))
    except ValueError:
        return fallback
    return hours * 60 + mins if 0 <= hours < 24 and 0 <= mins < 60 else fallback


def quiet_now(prefs, now=None):
    """Do Not Disturb: the manual switch, or inside the scheduled hours."""
    if prefs.get('dnd_enabled'):
        return True
    if not prefs.get('dnd_scheduled'):
        return False
    start = _minutes(prefs.get('dnd_start'), 22 * 60)
    end = _minutes(prefs.get('dnd_end'), 8 * 60)
    stamp = datetime.fromtimestamp(time.time() if now is None else now)
    minute = stamp.hour * 60 + stamp.minute
    if start == end:
        return False
    return start <= minute < end if start < end else minute >= start or minute < end


class NotificationStore:
    """SQLite history. A connection per call: writes are rare, and no open
    handle ever pins the file (Windows cannot delete or move it then)."""

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._db() as db:
            db.executescript(_SCHEMA)
        self.prune()

    @contextmanager
    def _db(self):
        with closing(sqlite3.connect(str(self.path))) as db:
            db.row_factory = sqlite3.Row
            with db:
                yield db

    def prune(self, now=None):
        cutoff = (time.time() if now is None else now) - RETENTION_DAYS * 86400
        with self._db() as db:
            db.execute('DELETE FROM events WHERE at < ?', (cutoff,))

    def add_event(self, event):
        """Store once; False when this exact event was already recorded."""
        try:
            with self._db() as db:
                db.execute(
                    'INSERT INTO events(at, kind, provider, task_key, project, detail, dedupe) '
                    'VALUES (?, ?, ?, ?, ?, ?, ?)',
                    (event['at'], event['kind'], event.get('provider') or '',
                     event.get('task_key') or '', event.get('project') or '',
                     event.get('detail') or '', event['dedupe']))
        except sqlite3.IntegrityError:
            return False
        return True

    def list_events(self, kind=None, limit=500):
        query = 'SELECT * FROM events' + (' WHERE kind = ?' if kind else '') + ' ORDER BY at DESC LIMIT ?'
        with self._db() as db:
            return [dict(row) for row in db.execute(query, ((kind, limit) if kind else (limit,)))]

    def add_reminder(self, title, repeat, minute, weekday=None, day=None, todo_id=None, now=None):
        title = (title or '').strip()[:200]
        if not title or repeat not in REPEATS:
            raise ValueError('reminder needs a title and a repeat')
        next_at = next_occurrence(repeat, minute, weekday, day, now)
        if next_at is None:
            raise ValueError('reminder time is in the past')
        with self._db() as db:
            cursor = db.execute(
                'INSERT INTO reminders(title, repeat, minute, weekday, day, todo_id, next_at) '
                'VALUES (?, ?, ?, ?, ?, ?, ?)', (title, repeat, int(minute), weekday, day, todo_id, next_at))
        return cursor.lastrowid

    def list_reminders(self):
        with self._db() as db:
            return [dict(row) for row in db.execute(
                'SELECT * FROM reminders ORDER BY next_at IS NULL, next_at')]

    def delete_reminder(self, reminder_id):
        with self._db() as db:
            db.execute('DELETE FROM reminders WHERE id = ?', (reminder_id,))

    def take_due_reminders(self, now=None):
        """Reminders due now; repeating ones move to their next time."""
        now = time.time() if now is None else now
        with self._db() as db:
            due = [dict(row) for row in db.execute(
                'SELECT * FROM reminders WHERE next_at IS NOT NULL AND next_at <= ?', (now,))]
            for row in due:
                following = (None if row['repeat'] == 'once' else
                             next_occurrence(row['repeat'], row['minute'], row['weekday'], row['day'], now))
                db.execute('UPDATE reminders SET next_at = ? WHERE id = ?', (following, row['id']))
        return due


class NotificationCenter(QObject):
    """Deduplicates, records and (outside quiet hours) announces events."""

    fired = Signal(dict)
    recorded = Signal()
    stored = Signal(dict)       # Every event kept in the history (quiet or not).

    def __init__(self, store, prefs):
        super().__init__()
        self.store = store
        self.prefs = prefs  # Callable returning the live preferences dict.
        self._recent = {}
        self._active = None
        self._preference = None
        # Optional: adds a recap (files, time, cost) to finished events.
        self.enrich = None

    def ingest(self, event, now=None):
        now = time.time() if now is None else now
        if event.get('kind') not in KINDS:
            return False
        same = (event.get('provider'), event.get('task_key'), event['kind'])
        if event['kind'] != 'reminder' and now - self._recent.get(same, -1e18) < DUPLICATE_WINDOW_S:
            return False
        if event['kind'] == 'finished' and self.enrich is not None:
            try:
                event = self.enrich(dict(event)) or event
            except Exception:
                pass  # A recap is a bonus; the notice itself must not fail.
        if not self.store.add_event(event):
            return False
        self._recent[same] = now
        self.recorded.emit()
        self.stored.emit(dict(event))
        # Silent events (a background run finishing) are history only.
        if not event.get('silent') and not quiet_now(self.prefs(), now):
            self.fired.emit(dict(event))
        return True

    def observe_tasks(self, tasks, preference, hooks_providers=(), now=None):
        """Polling fallback: recently active tasks that left the set finished."""
        now = time.time() if now is None else now
        current = {}
        for task in tasks or []:
            key = (task.get('provider_id'), task.get('task_key'))
            if all(isinstance(part, str) and part for part in key):
                current[key] = task
        if self._active is None or preference != self._preference:
            self._active, self._preference = current, preference
            return  # New baseline: a changed view is not a finished task.
        # Explicit approval state (Codex control socket, see
        # docs/V1_6_CODEX_APPROVAL.md): announce the step into waiting only.
        for key, task in current.items():
            before = (self._active.get(key) or {}).get('awaiting_approval')
            if task.get('awaiting_approval') is True and before is not True:
                self.ingest(dict(kind='needs_approval', provider=key[0], task_key=key[1], at=now,
                                 project=((task.get('display') or {}).get('project') or ''),
                                 detail='', dedupe=f'approval:{key[0]}:{key[1]}:{now:.0f}',
                                 source='poll'), now)
        for key, task in self._active.items():
            if key in current or key[0] in hooks_providers:
                continue
            seen = task.get('activity_at')
            if not isinstance(seen, (int, float)) or isinstance(seen, bool) or now - seen > POLL_RECENT_S:
                continue
            self.ingest(dict(kind='finished', provider=key[0], task_key=key[1], at=now,
                             project=((task.get('display') or {}).get('project') or ''),
                             detail='', dedupe=f'poll:{key[0]}:{key[1]}:{seen:.0f}', source='poll'), now)
        self._active = current

    def observe_quota(self, provider, limits, now=None):
        """One low-quota notice per 5-hour window when it drops to the threshold."""
        now = time.time() if now is None else now
        window = quota_window(limits, 300, now)
        if not window or window.get('expired') or window.get('remaining') is None:
            return False
        if window['remaining'] > QUOTA_LOW_LEFT:
            return False
        reset = window.get('reset')
        return self.ingest(dict(kind='quota_low', provider=provider, task_key='', at=now, project='',
                                detail=f"{window['remaining']:.0f}",
                                dedupe=f"quota:{provider}:{reset if reset is not None else int(now // 18000)}"), now)

    def fire_reminders(self, now=None):
        now = time.time() if now is None else now
        for row in self.store.take_due_reminders(now):
            self.ingest(dict(kind='reminder', provider='', task_key='', at=now, project='',
                             detail=row['title'], dedupe=f"reminder:{row['id']}:{row['next_at']:.0f}",
                             todo_id=row['todo_id']), now)
