"""Read-only Claude Code usage reader (V1.5). No transcript text or credentials are retained.

Verified against Claude Code 2.1.286 on Windows:

- ``<home>/projects/<project>/**/*.jsonl`` session transcripts. Only
  assistant lines carry ``message.usage``. One API response may be written
  as several lines repeating the same usage, so records dedupe by
  ``message.id``. A line is parsed in memory only to reach its numeric usage
  and metadata (model, session, cwd, branch, effort, time); message content
  is dropped at once and never stored, displayed or exported. Locally
  generated ``<synthetic>`` messages carry no API usage and are skipped.
- ``<home>/sessions/<pid>.json`` live-session registry written by running
  Claude Code processes (sessionId, cwd, status, process start time). A
  session is Working only while its entry says ``busy`` AND that exact
  process (pid plus creation time) is still alive, so a stale file left by
  a crashed process never claims current work.

Token mapping into the shared schema (``analytics.TOKEN_KEYS``): Anthropic
``input_tokens`` exclude cache traffic, so ``input = input + cache_read +
cache_write``, ``cached_input = cache_read``, ``cache_write_input =
cache_creation``, ``output = output`` (thinking included),
``reasoning_output = thinking`` when recorded, ``total = input + output``.
Anything missing stays ``None``. Context use is the latest main-chain
request's input against the model's official context window (a request
larger than that window makes it unknown). Claude subscription quotas and
reset times are not stored locally and stay unavailable.

Synchronous by design: callers run it on the poller's background worker.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from analytics import aggregate, count, summarize
from pricing import claude_price_model, estimate_claude_usd
from providers import (CLAUDE_CAPABILITIES, PROVIDER_CLAUDE, active_task,
                       base_result)

PROVIDER_ID = PROVIDER_CLAUDE
SESSION_PREFIX = f'{PROVIDER_ID}:'
PROJECT_PREFIX = f'{PROVIDER_ID}-project:'
# New transcript files are discovered at most this often; known files are
# refreshed every read (one stat each, new complete lines only).
DISCOVERY_TTL_S = 5.0
REGISTRY_BUSY = 'busy'
# Official context windows (tokens), verified 2026-10-05 against Anthropic's
# models overview. Locally observed Opus 5.5 requests reach 831K tokens,
# confirming Claude Code uses the full window. Unlisted models stay unknown.
CONTEXT_WINDOWS = {
    'claude-fable-5-1': 1_000_000, 'claude-mythos-5-1': 1_000_000,
    'claude-fable-5': 1_000_000, 'claude-mythos-5': 1_000_000,
    'claude-opus-5-5': 1_000_000, 'claude-opus-5': 1_000_000,
    'claude-opus-4-8': 1_000_000, 'claude-opus-4-7': 1_000_000,
    'claude-opus-4-6': 1_000_000, 'claude-sonnet-5-5': 1_000_000,
    'claude-sonnet-5': 1_000_000, 'claude-sonnet-4-6': 1_000_000,
    'claude-haiku-4-5': 200_000,
}


def context_window(model):
    return CONTEXT_WINDOWS.get(claude_price_model(model))


def context_percent(tokens, model):
    """Share of the model's window used by the latest request, or None."""
    window = context_window(model)
    tokens = count(tokens)
    if tokens is None or not window or tokens > window:
        return None
    return 100 * tokens / window


def default_home():
    """Claude Code's config directory. ``PETOKEN_CLAUDE_HOME`` overrides it
    for isolated QA/tests without touching Claude Code's own variable."""
    configured = (os.environ.get('PETOKEN_CLAUDE_HOME')
                  or os.environ.get('CLAUDE_CONFIG_DIR'))
    return Path(configured) if configured else Path.home() / '.claude'


def scoped_session_id(raw_id):
    return f'{SESSION_PREFIX}{raw_id}'


def strip_scope(value):
    """Raw session ID of a Claude-scoped pin, or '' for anything else."""
    value = (value or '').strip() if isinstance(value, str) else ''
    return value[len(SESSION_PREFIX):] if value.startswith(SESSION_PREFIX) else ''


def project_identity(cwd):
    """(name, source, project_id) for a session working directory."""
    if not isinstance(cwd, str) or not cwd.strip():
        return None, 'unavailable', None
    cleaned = cwd.strip().removeprefix('\\\\?\\').rstrip('\\/')
    name = re.split(r'[\\/]', cleaned)[-1] if cleaned else ''
    key = os.path.normcase(os.path.normpath(cleaned)) if cleaned else ''
    if not name or not key:
        return None, 'unavailable', None
    return name, 'cwd_basename', f'{PROJECT_PREFIX}{key}'


def map_usage(usage):
    """One Anthropic ``usage`` object in the shared token schema."""
    usage = usage if isinstance(usage, dict) else {}
    plain = count(usage.get('input_tokens'))
    read = count(usage.get('cache_read_input_tokens'))
    write = count(usage.get('cache_creation_input_tokens'))
    out = count(usage.get('output_tokens'))
    details = usage.get('output_tokens_details')
    reasoning = count(details.get('thinking_tokens')) if isinstance(details, dict) else None
    total_input = plain + read + write if None not in (plain, read, write) else None
    return dict(input_tokens=total_input, cached_input_tokens=read,
                cache_write_input_tokens=write, output_tokens=out,
                reasoning_output_tokens=reasoning,
                total_tokens=(total_input + out if total_input is not None
                              and out is not None else None))


def _iso_epoch(value):
    try:
        stamp = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except (ValueError, TypeError):
        return None
    return stamp.timestamp() if stamp.tzinfo is not None else None


def _text(value):
    return value.strip() if isinstance(value, str) and value.strip() else None


class ClaudeTranscript:
    """Incremental reader for one transcript file (complete lines only)."""

    def __init__(self, path):
        self.path = Path(path)
        self.offset = 0
        self.records = {}
        self.meta = {}
        self.titles = {}
        self.partial = False
        self.source_available = False
        self.notes = set()

    def refresh(self):
        try:
            size = self.path.stat().st_size
            if size < self.offset:
                self.__init__(self.path)  # Rewritten file: start over.
            self.source_available = True
            if size == self.offset:
                return
            with self.path.open('rb') as handle:
                handle.seek(self.offset)
                while line := handle.readline():
                    if not line.endswith(b'\n'):
                        break  # Writer may be halfway through a JSON object.
                    self.offset = handle.tell()
                    if b'"custom-title"' in line[:64]:
                        self._title(line)
                    elif b'"usage"' in line and b'"assistant"' in line:
                        self._assistant(line)
        except OSError:
            self.partial = True
            self.source_available = False
            self.notes.add('note_usage_source_unavailable')

    def _invalid(self):
        self.partial = True
        self.notes.add('note_usage_record_invalid')

    def _title(self, line):
        try:
            entry = json.loads(line)
        except ValueError:
            return
        if isinstance(entry, dict) and entry.get('type') == 'custom-title':
            session = _text(entry.get('sessionId'))
            title = _text(entry.get('customTitle'))
            if session and title:
                self.titles[session] = title

    def _assistant(self, line):
        try:
            entry = json.loads(line)
        except ValueError:
            self._invalid()
            return
        if not isinstance(entry, dict) or entry.get('type') != 'assistant':
            return
        message = entry.get('message')
        usage = message.get('usage') if isinstance(message, dict) else None
        if not isinstance(usage, dict):
            return
        model = _text(message.get('model'))
        if model == '<synthetic>':
            return
        event = _text(message.get('id')) or _text(entry.get('requestId'))
        if not event:
            self._invalid()
            return
        session = _text(entry.get('sessionId')) or self.path.stem
        stamp = _text(entry.get('timestamp'))
        sidechain = bool(entry.get('isSidechain'))
        meta = self.meta.setdefault(session, dict(
            cwd=None, branch=None, version=None, model=None, effort=None,
            first_at=None, last_at=None, last_input=None))
        at = _iso_epoch(stamp)
        if at is not None:
            if meta['first_at'] is None or at < meta['first_at']:
                meta['first_at'] = at
            if meta['last_at'] is None or at >= meta['last_at']:
                meta['last_at'] = at
                meta['sample'] = stamp
        # A session belongs to the project it was started in: later
        # directory changes inside the session never move it.
        if meta['cwd'] is None:
            meta['cwd'] = _text(entry.get('cwd'))
        for key, field in (('branch', 'gitBranch'), ('version', 'version'),
                           ('effort', 'effort')):
            value = _text(entry.get(field))
            if value:
                meta[key] = value
        if event in self.records:
            return  # Same response repeated per content block.
        tokens = map_usage(usage)
        if model and not sidechain:
            meta['model'] = model
        if not sidechain and tokens['input_tokens'] is not None:
            meta['last_input'] = tokens['input_tokens']
        self.records[event] = dict(
            session=session, model=model, timestamp=stamp, event_id=event,
            tokens=tokens, usd=estimate_claude_usd(usage, model),
            sidechain=sidechain)


def _process_alive(pid, proc_start=None):
    """Whether that exact process still runs (pid reuse is rejected)."""
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        return False
    if sys.platform != 'win32':
        try:
            os.kill(pid, 0)
        except PermissionError:
            return True
        except OSError:
            return False
        return True
    try:
        import ctypes
        from ctypes import wintypes
        kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        handle = kernel32.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        try:
            code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value != 259:
                return False
            try:
                expected = int(proc_start)
            except (TypeError, ValueError):
                return True
            times = [wintypes.FILETIME() for _ in range(4)]
            if not kernel32.GetProcessTimes(handle, *(ctypes.byref(t) for t in times)):
                return True
            created = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
            return created == expected
        finally:
            kernel32.CloseHandle(handle)
    except (OSError, AttributeError):
        return False


def read_registry(home, alive=_process_alive):
    """Live sessions by raw ID, or ``None`` when the registry is unavailable."""
    folder = Path(home) / 'sessions'
    if not folder.is_dir():
        return None
    entries = {}
    for path in folder.glob('*.json'):
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        session = _text(data.get('sessionId'))
        if not session or not alive(data.get('pid'), data.get('procStart')):
            continue
        updated = data.get('statusUpdatedAt', data.get('updatedAt'))
        activity_at = (updated / 1000 if isinstance(updated, (int, float))
                       and not isinstance(updated, bool) and updated > 0 else None)
        status = _text(data.get('status'))
        entry = dict(session_id=session, status=status,
                     busy=status == REGISTRY_BUSY, activity_at=activity_at,
                     cwd=_text(data.get('cwd')), name=_text(data.get('name')))
        previous = entries.get(session)
        if previous is None or (activity_at or 0) >= (previous['activity_at'] or 0):
            entries[session] = entry
    return entries


class ClaudeStore:
    def __init__(self, home=None):
        self.home = Path(home) if home is not None else default_home()
        self.transcripts = {}
        self._discovered_at = None
        self._index = dict(signature=None, sessions={})
        self.analytics_cache = {}

    def _discover(self, now):
        projects = self.home / 'projects'
        if not projects.is_dir():
            return False
        if self._discovered_at is None or now - self._discovered_at >= DISCOVERY_TTL_S:
            try:
                found = {str(path) for path in projects.rglob('*.jsonl')}
            except OSError:
                found = set(self.transcripts)
            for key in found - set(self.transcripts):
                self.transcripts[key] = ClaudeTranscript(key)
            for key in set(self.transcripts) - found:
                self.transcripts.pop(key, None)
            self._discovered_at = now
        for transcript in self.transcripts.values():
            transcript.refresh()
        return True

    def _sessions(self):
        """Per-session records and metadata merged across transcript files
        (subagent transcripts carry their parent's session ID)."""
        signature = tuple(sorted((key, t.offset, len(t.titles))
                                 for key, t in self.transcripts.items()))
        if self._index['signature'] == signature:
            return self._index['sessions']
        sessions = {}

        def slot(session):
            return sessions.setdefault(session, dict(
                id=session, records={}, title=None, cwd=None, branch=None,
                model=None, effort=None, first_at=None, last_at=None,
                sample=None, last_input=None, partial=False, notes=set(),
                source_available=True))
        for transcript in self.transcripts.values():
            for record in transcript.records.values():
                slot(record['session'])['records'].setdefault(record['event_id'], record)
            for session, meta in transcript.meta.items():
                item = slot(session)
                item['partial'] |= transcript.partial
                item['notes'] |= transcript.notes
                item['source_available'] &= transcript.source_available
                earlier = meta['first_at'] is not None and (
                    item['first_at'] is None or meta['first_at'] < item['first_at'])
                if earlier:
                    item['first_at'] = meta['first_at']
                if meta['cwd'] is not None and (earlier or item['cwd'] is None):
                    item['cwd'] = meta['cwd']
                newer = meta['last_at'] is not None and (
                    item['last_at'] is None or meta['last_at'] >= item['last_at'])
                for key in ('branch', 'model', 'effort', 'last_input'):
                    if meta.get(key) is not None and (newer or item[key] is None):
                        item[key] = meta[key]
                if newer:
                    item['last_at'], item['sample'] = meta['last_at'], meta.get('sample')
            for session, title in transcript.titles.items():
                slot(session)['title'] = title
        self._index = dict(signature=signature, sessions=sessions)
        return sessions

    @staticmethod
    def _title(session, registry_entry=None):
        name = (registry_entry or {}).get('name')
        return name or (session or {}).get('title') or None

    @staticmethod
    def _summary(session):
        return summarize(list((session or {}).get('records', {}).values()))

    def _task(self, entry, session):
        project, _source, _project_id = project_identity(
            (session or {}).get('cwd') or entry.get('cwd'))
        summary = self._summary(session)
        records = (session or {}).get('records') or {}
        return active_task(
            PROVIDER_ID, scoped_session_id(entry['session_id']), working=True,
            activity_valid=True, activity_at=entry.get('activity_at'),
            display=dict(project=project),
            presentation=dict(
                tokens=summary['tokens'], model=(session or {}).get('model'),
                effort=(session or {}).get('effort'),
                context=context_percent((session or {}).get('last_input'),
                                        (session or {}).get('model')),
                available=bool(records),
                source_available=bool((session or {}).get('source_available', True)),
                partial=bool((session or {}).get('partial')),
                notes=tuple(sorted((session or {}).get('notes') or ()))))

    def read(self, active_title='', pinned='', scope='conversation',
             include_history=False, activity_detection_valid=False):
        scope = {'task': 'conversation'}.get(scope, scope)
        if scope not in ('global', 'project', 'conversation'):
            scope = 'conversation'
        now = time.time()
        if not self._discover(now):
            return dict(status='status_claude_no_local_data', rows=[], scope=scope,
                        claude_activity=dict(active=False, valid=False,
                                             reason='no_local_data'),
                        working_context=None, active_tasks=[])
        sessions = self._sessions()
        registry = read_registry(self.home)
        working = sorted((entry for entry in (registry or {}).values() if entry['busy']),
                         key=lambda e: (-(e['activity_at'] or 0), e['session_id']))
        primary = working[0] if working else None
        claude_activity = dict(
            active=bool(working), valid=registry is not None,
            reason=('registry_unavailable' if registry is None
                    else 'registry_busy' if working else 'no_running_session'),
            thread=scoped_session_id(primary['session_id']) if primary else None,
            working_threads=[scoped_session_id(e['session_id']) for e in working],
            activity_at=primary['activity_at'] if primary else None)
        active_tasks = [self._task(entry, sessions.get(entry['session_id']))
                        for entry in working]
        working_context = None
        if primary is not None:
            session = sessions.get(primary['session_id'])
            project, project_source, project_id = project_identity(
                (session or {}).get('cwd') or primary.get('cwd'))
            working_context = dict(
                thread=scoped_session_id(primary['session_id']),
                title=self._title(session, primary), project=project,
                project_source=project_source, project_id=project_id,
                status='working', tokens=self._summary(session)['tokens'],
                available=bool((session or {}).get('records')),
                model=(session or {}).get('model'), effort=(session or {}).get('effort'),
                context=context_percent((session or {}).get('last_input'),
                                        (session or {}).get('model')),
                sample=(session or {}).get('sample'), selection=None,
                activity_reason='registry_busy')

        raw_pin = strip_scope(pinned)
        if raw_pin:
            chosen, mode = sessions.get(raw_pin), 'fixed'
        elif primary is not None and primary['session_id'] in sessions:
            chosen, mode = sessions[primary['session_id']], 'working'
        else:
            ranked = sorted(sessions.values(), key=lambda s: (s['last_at'] or 0, s['id']))
            chosen, mode = (ranked[-1] if ranked else None), 'recent'
        common = dict(rows=[], scope=scope, claude_activity=claude_activity,
                      working_context=working_context, active_tasks=active_tasks)
        if scope != 'global' and chosen is None:
            identity = dict(scope_type=scope, unavailable=True)
            if scope == 'conversation':
                identity['thread_id'] = pinned or None
            return dict(common, status=('status_pinned_unavailable' if raw_pin
                                        else 'status_no_desktop_task'),
                        scope_identity=identity)

        chosen_entry = (registry or {}).get(chosen['id']) if chosen else None
        chosen_title = self._title(chosen, chosen_entry)
        chosen_project, chosen_source, chosen_project_id = project_identity(
            chosen['cwd'] if chosen else None)
        if scope == 'global':
            relevant = list(sessions.values())
            scope_identity = dict(scope_type='global', locally_recorded=True)
        elif scope == 'project':
            scope_identity = dict(scope_type='project', project_id=chosen_project_id,
                                  project_name=chosen_project, project_source=chosen_source)
            if chosen_project_id is None:
                scope_identity['unavailable'] = True
                return dict(common, status='status_project_unavailable',
                            scope_identity=scope_identity)
            relevant = [s for s in sessions.values()
                        if project_identity(s['cwd'])[2] == chosen_project_id]
        else:
            relevant = [chosen]
            scope_identity = dict(
                scope_type='conversation', thread_id=scoped_session_id(chosen['id']),
                conversation_title=chosen_title, project_id=chosen_project_id,
                project_name=chosen_project, project_source=chosen_source)

        records = [record for session in relevant for record in session['records'].values()]
        signature = (self._index['signature'], tuple(sorted(s['id'] for s in relevant)))
        if self.analytics_cache.get('signature') != signature:
            self.analytics_cache = dict(signature=signature, summary=aggregate(records))
        analysis = self.analytics_cache['summary']
        tokens = analysis['tokens']
        unknown = sorted({r.get('model') or 'unknown_breakdown' for r in records
                          if r.get('usd') is None and r['tokens'].get('total_tokens')})
        partial = any(s['partial'] or not s['source_available'] for s in relevant)
        notes = sorted(set().union(*(s['notes'] for s in relevant)) if relevant else ())
        available = bool(records)
        working_ids = set(claude_activity['working_threads'])
        scope_working = working_ids.intersection(scoped_session_id(s['id']) for s in relevant)
        if scope == 'global':
            display_project, display_title = 'display_all_usage', 'display_local_history'
        elif scope == 'project':
            display_project = display_title = chosen_project or 'project_unavailable'
        else:
            display_project = chosen_project or 'project_unavailable'
            display_title = chosen_title or 'display_untitled'
        return dict(
            common, status='' if records else 'status_no_usage', mode=mode,
            thread=scoped_session_id(chosen['id']) if chosen else None,
            title=display_title, project=display_project,
            scope_identity=scope_identity,
            scope_result=dict(identity=scope_identity, tokens=tokens, analytics=analysis,
                              available=available, count=len(relevant), partial=partial),
            tokens=tokens, available=available,
            model=chosen['model'] if chosen else None,
            effort=chosen['effort'] if chosen else None,
            tier=None,
            context=(context_percent(chosen['last_input'], chosen['model'])
                     if chosen else None),
            context_tokens=chosen['last_input'] if chosen else None,
            context_window=context_window(chosen['model']) if chosen else None,
            usd=sum(r.get('usd') or 0 for r in records), unknown=unknown,
            partial=partial, excluded_forks=0, count=len(relevant),
            sample=chosen['sample'] if chosen else None, limits=None,
            analytics=analysis,
            history=dict(analysis, partial=partial) if include_history else None,
            session_names={scoped_session_id(s['id']): self._title(s, (registry or {}).get(s['id']))
                           for s in relevant},
            current_session=self._summary(chosen), raw_total={}, raw_last={},
            notes=notes,
            scope_activity=dict(active=bool(scope_working),
                                valid=bool(claude_activity['valid']),
                                working_count=len(scope_working)))


class ClaudeProvider:
    """Tags ClaudeStore reads with the shared provider envelope."""

    provider_id = PROVIDER_ID

    def __init__(self, store=None):
        self.store = store if store is not None else ClaudeStore()

    @property
    def capabilities(self):
        return CLAUDE_CAPABILITIES

    def read(self, active_title='', pinned='', scope='conversation',
             include_history=False, activity_detection_valid=False):
        data = self.store.read(active_title=active_title, pinned=pinned,
                               scope=scope, include_history=include_history,
                               activity_detection_valid=activity_detection_valid)
        ok = not data.get('status')
        return base_result(
            PROVIDER_ID,
            available=bool(data.get('available', False)),
            status='' if ok else 'unavailable',
            reason=data.get('status') or '',
            identity=data.get('scope_identity'),
            tokens=data.get('tokens'),
            working_context=data.get('working_context'),
            scope_result=data.get('scope_result'),
            quotas=None,
            cost=data.get('usd'),
            capabilities=CLAUDE_CAPABILITIES,
            partial=bool(data.get('partial', False)),
            notes=data.get('notes'),
            payload=data,
            last_success_at=time.time() if ok else None,
            source_event_at=data.get('sample'))
