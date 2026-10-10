"""Calendar reminders (2.4): meetings from your calendar's .ics subscription link.

Google Calendar, Outlook.com, iCloud and Feishu can all give a private
"iCal / .ics" address; a local .ics file works too. Petoken reads it every
15 minutes (in a worker, never blocking her) and:

  - shortly before a meeting (10 minutes by default) she holds up a card and a
    notice names it (also on the phone, when phone notices are on);
  - during the meeting Do Not Disturb is on by itself (optional);
  - when it ends, one notice sums up what the AIs did meanwhile.

The parser is small and self-contained: VEVENT with DTSTART/DTEND/DURATION
(UTC, floating, TZID or all-day), RRULE (DAILY/WEEKLY/MONTHLY/YEARLY with
INTERVAL, COUNT, UNTIL, BYDAY, BYMONTHDAY), EXDATE and RECURRENCE-ID
overrides. Time zones come from the file's own VTIMEZONE blocks (standard and
daylight rules), so no time-zone database is needed; an unknown TZID is read
as local time. Links and events stay on this computer.
"""
from __future__ import annotations

import re
import threading
import time
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

FETCH_EVERY_S = 15 * 60
LEAD_CHOICES = (5, 10, 15, 30)
WINDOW_DAYS = 3
WEEKDAYS = ('MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU')
_ACTIVE = {'meeting': None}          # The meeting going on now (for quiet_now).


def in_meeting():
    """The meeting happening now when "quiet during meetings" is on, else None."""
    return _ACTIVE['meeting']


# Parsing ---------------------------------------------------------------------------

def unfold(text):
    """Content lines with folded continuations joined."""
    lines = []
    for raw in text.replace('\r\n', '\n').replace('\r', '\n').split('\n'):
        if raw[:1] in (' ', '\t') and lines:
            lines[-1] += raw[1:]
        elif raw.strip():
            lines.append(raw)
    return lines


def parse_line(line):
    """(NAME, {PARAM: value}, value)."""
    head, _, value = line.partition(':')
    parts = head.split(';')
    params = {}
    for part in parts[1:]:
        key, _, val = part.partition('=')
        params[key.upper()] = val.strip('"')
    return parts[0].upper(), params, value


def unescape(value):
    return (value.replace('\\n', '\n').replace('\\N', '\n').replace('\\,', ',').replace('\\;', ';')
            .replace('\\\\', '\\'))


def components(lines):
    """Nested components as dicts: {'name', 'props': [(name, params, value)], 'children'}."""
    root = dict(name='ROOT', props=[], children=[])
    stack = [root]
    for line in lines:
        name, params, value = parse_line(line)
        if name == 'BEGIN':
            node = dict(name=value.upper(), props=[], children=[])
            stack[-1]['children'].append(node)
            stack.append(node)
        elif name == 'END':
            if len(stack) > 1:
                stack.pop()
        else:
            stack[-1]['props'].append((name, params, value))
    return root


def prop(node, name):
    for key, params, value in node['props']:
        if key == name:
            return params, value
    return None, None


def props(node, name):
    return [(params, value) for key, params, value in node['props'] if key == name]


def nth_weekday(year, month, spec):
    """The day of ``month`` named by an RRULE BYDAY like '2SU' or '-1SU'."""
    match = re.fullmatch(r'([+-]?\d*)([A-Z]{2})', spec)
    n = int(match.group(1) or 1)
    weekday = WEEKDAYS.index(match.group(2))
    if n > 0:
        first = date(year, month, 1)
        day = first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))
    else:
        nxt = date(year + (month == 12), month % 12 + 1, 1)
        last = nxt - timedelta(days=1)
        day = last - timedelta(days=(last.weekday() - weekday) % 7 + 7 * (-n - 1))
    return day


def _offset(text):
    sign = -1 if text.startswith('-') else 1
    text = text.lstrip('+-')
    hours, minutes = int(text[:2]), int(text[2:4])
    return sign * timedelta(hours=hours, minutes=minutes)


class Zone:
    """A VTIMEZONE: standard and daylight offsets with their yearly rules."""

    def __init__(self, node):
        self.rules = []                 # (offset, month, byday, start time, fixed date)
        for child in node['children']:
            if child['name'] not in ('STANDARD', 'DAYLIGHT'):
                continue
            _, to = prop(child, 'TZOFFSETTO')
            _, start = prop(child, 'DTSTART')
            _, rule = prop(child, 'RRULE')
            if not to or not start:
                continue
            start_dt = datetime.strptime(start[:15], '%Y%m%dT%H%M%S')
            parts = dict(p.split('=', 1) for p in rule.split(';') if '=' in p) if rule else {}
            self.rules.append((_offset(to), int(parts.get('BYMONTH', start_dt.month)),
                               parts.get('BYDAY'), start_dt.time(), None if rule else start_dt))

    def utcoffset(self, local):
        """The offset for a local wall-clock time (the transition rule in force)."""
        if not self.rules:
            return None
        best, best_at = None, None
        for year in (local.year - 1, local.year):
            for offset, month, byday, at, fixed in self.rules:
                if fixed is not None:
                    when = fixed
                else:
                    day = nth_weekday(year, month, byday) if byday else date(year, month, 1)
                    when = datetime.combine(day, at)
                if when <= local and (best_at is None or when > best_at):
                    best, best_at = offset, when
        return best if best is not None else self.rules[0][0]


def to_epoch(value, params, zones):
    """(epoch seconds, all-day) for a DATE or DATE-TIME value."""
    value = value.strip()
    if params.get('VALUE') == 'DATE' or len(value) == 8:
        day = datetime.strptime(value[:8], '%Y%m%d')
        return day.timestamp(), True
    local = datetime.strptime(value[:15], '%Y%m%dT%H%M%S')
    if value.endswith('Z'):
        return local.replace(tzinfo=timezone.utc).timestamp(), False
    zone = zones.get(params.get('TZID', ''))
    offset = zone.utcoffset(local) if zone else None
    if offset is None:
        return local.timestamp(), False           # Floating or unknown zone: local time.
    return (local - offset).replace(tzinfo=timezone.utc).timestamp(), False


def duration(text):
    match = re.fullmatch(r'([+-])?P(?:(\d+)W)?(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?', text.strip())
    if not match:
        return 0
    sign = -1 if match.group(1) == '-' else 1
    w, d, h, m, s = (int(g or 0) for g in match.groups()[1:])
    return sign * (((w * 7 + d) * 24 + h) * 3600 + m * 60 + s)


def occurrences(start, rule, until_window, all_day=False):
    """Start times (epoch) of a recurring event, up to ``until_window``.

    Steps are taken on the local calendar, so a 9:00 meeting stays at 9:00
    across daylight-saving changes."""
    parts = dict(p.split('=', 1) for p in rule.split(';') if '=' in p)
    freq = parts.get('FREQ', 'DAILY')
    interval = max(1, int(parts.get('INTERVAL', 1)))
    count = int(parts['COUNT']) if 'COUNT' in parts else None
    until = None
    if 'UNTIL' in parts:
        until, _ = to_epoch(parts['UNTIL'], {}, {})
    days = [d[-2:] for d in parts.get('BYDAY', '').split(',') if d]
    monthdays = [int(d) for d in parts.get('BYMONTHDAY', '').split(',') if d]
    first = datetime.fromtimestamp(start)
    out, n, step = [], 0, 0
    while step < 5000:
        if freq == 'DAILY':
            batch = [first + timedelta(days=step * interval)]
        elif freq == 'WEEKLY':
            week = first - timedelta(days=first.weekday()) + timedelta(weeks=step * interval)
            wanted = days or [WEEKDAYS[first.weekday()]]
            batch = [week + timedelta(days=WEEKDAYS.index(d)) for d in sorted(wanted, key=WEEKDAYS.index)]
        elif freq == 'MONTHLY':
            month_index = first.month - 1 + step * interval
            year, month = first.year + month_index // 12, month_index % 12 + 1
            if days and parts.get('BYDAY', '')[:1] in '+-0123456789':
                batch = [datetime.combine(nth_weekday(year, month, d), first.time())
                         for d in parts['BYDAY'].split(',')]
            else:
                batch = []
                for md in monthdays or [first.day]:
                    try:
                        batch.append(first.replace(year=year, month=month, day=md))
                    except ValueError:
                        pass
        else:                                   # YEARLY
            try:
                batch = [first.replace(year=first.year + step * interval)]
            except ValueError:
                batch = []
        step += 1
        for when in batch:
            at = when.timestamp()
            if at < start:
                continue
            if until is not None and at > until + (86400 if all_day else 0):
                return out
            n += 1
            if count is not None and n > count:
                return out
            if at > until_window:
                return out
            out.append(at)
    return out


def events(text, now=None, days=WINDOW_DAYS):
    """[{uid, title, start, end, all_day, location}] from ``now`` - 1 day to ``now`` + ``days``."""
    now = time.time() if now is None else now
    root = components(unfold(text))
    calendars = [c for c in root['children'] if c['name'] == 'VCALENDAR'] or [root]
    out = []
    for cal in calendars:
        zones = {}
        for node in cal['children']:
            if node['name'] == 'VTIMEZONE':
                _, tzid = prop(node, 'TZID')
                if tzid:
                    zones[tzid] = Zone(node)
        lo, hi = now - 86400, now + days * 86400
        overrides = {}
        for node in cal['children']:
            if node['name'] != 'VEVENT':
                continue
            params, value = prop(node, 'RECURRENCE-ID')
            if value:
                _, uid = prop(node, 'UID')
                overrides.setdefault(uid, set()).add(to_epoch(value, params, zones)[0])
        for node in cal['children']:
            if node['name'] != 'VEVENT':
                continue
            _, status = prop(node, 'STATUS')
            if (status or '').upper() == 'CANCELLED':
                continue
            params, value = prop(node, 'DTSTART')
            if not value:
                continue
            try:
                start, all_day = to_epoch(value, params, zones)
                eparams, evalue = prop(node, 'DTEND')
                if evalue:
                    end = to_epoch(evalue, eparams, zones)[0]
                else:
                    _, dur = prop(node, 'DURATION')
                    end = start + (duration(dur) if dur else (86400 if all_day else 0))
            except (ValueError, AttributeError):
                continue
            _, uid = prop(node, 'UID')
            _, summary = prop(node, 'SUMMARY')
            _, location = prop(node, 'LOCATION')
            _, rid = prop(node, 'RECURRENCE-ID')
            _, rule = prop(node, 'RRULE')
            length = end - start
            starts = [start]
            if rule and not rid:
                excluded = set(overrides.get(uid, ()))
                for xparams, xvalue in props(node, 'EXDATE'):
                    for item in xvalue.split(','):
                        try:
                            excluded.add(to_epoch(item, xparams, zones)[0])
                        except ValueError:
                            pass
                starts = [s for s in occurrences(start, rule, hi, all_day) if s not in excluded]
            for s in starts:
                if s + max(length, 1) < lo or s > hi:
                    continue
                out.append(dict(uid=uid or '', title=unescape(summary or '').strip() or '(no title)',
                                start=s, end=s + length, all_day=all_day,
                                location=unescape(location or '').strip()))
    out.sort(key=lambda e: e['start'])
    return out


# Fetching ------------------------------------------------------------------------------

def read_source(source, timeout=20):
    """The text of one link (http/https/webcal) or local .ics file."""
    source = source.strip()
    if source.lower().startswith('webcal://'):
        source = 'https://' + source[9:]
    if re.match(r'https?://', source, re.I):
        request = urllib.request.Request(source, headers={'User-Agent': 'Petoken calendar'})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read(5_000_000).decode('utf-8', errors='replace')
    return Path(source).read_text(encoding='utf-8', errors='replace')


def sources(prefs):
    value = prefs.get('calendar_sources') or []
    if isinstance(value, str):
        value = value.splitlines()
    return [s.strip() for s in value if isinstance(s, str) and s.strip()]


# Watching ---------------------------------------------------------------------------------

class CalendarWatcher:
    """Fetches the calendars now and then; reminds before meetings and keeps
    quiet during them. ``tick`` is called every 30 seconds by the panel."""

    def __init__(self, panel, clock=time.time, reader=read_source):
        self.panel = panel
        self.clock = clock
        self.reader = reader
        self.items = []
        self.fetched_at = 0.0
        self.error = ''
        self.reminded = set()           # (uid, start)
        self.current = None             # The meeting under way.
        self._busy = False
        self._lock = threading.Lock()

    @property
    def prefs(self):
        return self.panel.prefs

    @property
    def enabled(self):
        return bool(self.prefs.get('calendar_enabled')) and bool(sources(self.prefs))

    @property
    def lead(self):
        value = self.prefs.get('calendar_lead_minutes', 10)
        return (value if value in LEAD_CHOICES else 10) * 60

    def refresh(self, done=None, wait=False):
        """Read every source in a worker; ``done(ok)`` runs afterwards (in the worker)."""
        if self._busy:
            return
        self._busy = True
        links = sources(self.prefs)

        def work():
            found, errors = [], []
            for link in links:
                try:
                    found += events(self.reader(link), self.clock())
                except Exception as exc:          # One bad link never hides the others.
                    errors.append(f'{type(exc).__name__}')
            with self._lock:
                self.items = sorted(found, key=lambda e: e['start'])
                self.fetched_at = self.clock()
                self.error = ', '.join(errors)
            self._busy = False
            if done is not None:
                done(not errors)
        if wait:
            work()
        else:
            threading.Thread(target=work, daemon=True, name='petoken-calendar').start()

    def upcoming(self, now=None):
        now = self.clock() if now is None else now
        with self._lock:
            return [e for e in self.items if not e['all_day'] and e['end'] > now]

    def tick(self, now=None):
        """[(kind, event)] to act on now: 'soon', 'start', 'end'."""
        now = self.clock() if now is None else now
        if not self.enabled:
            self._set_current(None)
            return []
        if now - self.fetched_at >= FETCH_EVERY_S:
            self.refresh()
        actions = []
        meeting = None
        for event in self.upcoming(now):
            key = (event['uid'], event['start'])
            if 0 < event['start'] - now <= self.lead and key not in self.reminded:
                self.reminded.add(key)
                actions.append(('soon', event))
            if event['start'] <= now < event['end'] and meeting is None:
                meeting = event
        previous = self.current
        if meeting is not None and (previous is None or previous['start'] != meeting['start']):
            actions.append(('start', meeting))
        if previous is not None and (meeting is None or meeting['start'] != previous['start']):
            actions.append(('end', previous))
        self._set_current(meeting)
        return actions

    def _set_current(self, meeting):
        self.current = meeting
        _ACTIVE['meeting'] = meeting if (meeting is not None and self.prefs.get('calendar_dnd', True)) else None
