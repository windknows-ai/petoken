"""Read-only Codex usage reader. No transcript or credentials are retained."""
from __future__ import annotations

import json
import os
import sqlite3
import time
import hashlib
from contextlib import closing
from datetime import datetime
from pathlib import Path
from analytics import TOKEN_KEYS, normalize_usage, derive, aggregate, summarize
from pricing import MODEL_PRICES as PRICES, estimate_usd
from providers import PROVIDER_CODEX, active_task


def quota_window(limits, minutes, now=None):
    now = time.time() if now is None else now
    for key in ('primary', 'secondary'):
        w = (limits or {}).get(key)
        if not isinstance(w, dict):
            continue
        if w.get('windowDurationMins', w.get('window_minutes')) != minutes:
            continue
        used = w.get('usedPercent', w.get('used_percent'))
        if not isinstance(used, (int, float)):
            return None
        reset = w.get('resetsAt', w.get('resets_at'))
        return dict(remaining=max(0, min(100, 100-used)), reset=reset,
                    expired=bool(reset and reset <= now))
    return None


def select_thread(rows, title, pinned):
    if pinned:
        return next(((r, 'fixed') for r in rows if r['id'] == pinned), (None, 'missing'))
    matches = [r for r in rows if title and title in (r.get('name'), r.get('title'))]
    if len(matches) == 1:
        return matches[0], 'follow'
    return (rows[0], 'recent') if rows else (None, 'empty')


def project_identity(row, state):
    assignments = state.get('thread-project-assignments', {}) if isinstance(state, dict) else {}
    projects = state.get('local-projects', {}) if isinstance(state, dict) else {}
    project_id = (assignments.get(row.get('id')) or {}).get('projectId') or row.get('project_id')
    project = projects.get(project_id, {}) if isinstance(projects, dict) else {}
    name = project.get('name') if isinstance(project, dict) else None
    if isinstance(name, str) and name.strip():
        return name.strip(), 'project_metadata', project_id
    origin = row.get('git_origin_url')
    if isinstance(origin, str) and origin.strip():
        normalized_origin = origin.strip().rstrip('/\\')
        repository = normalized_origin.rsplit('/',1)[-1].rsplit(':',1)[-1]
        repository = repository.removesuffix('.git').strip()
        if repository:
            return repository, 'git_origin', project_id or 'git:'+normalized_origin.lower()
    cwd = row.get('cwd')
    if isinstance(cwd, str) and cwd.strip():
        normalized_cwd = clean_path(cwd.strip())
        directory = Path(cwd.strip().removeprefix('\\\\?\\').rstrip('/\\')).name.strip()
        if directory:
            return directory, 'cwd_basename', project_id or 'cwd:'+normalized_cwd
    return None, 'unavailable', project_id


def conversation_title(row):
    name = row.get('name')
    if isinstance(name, str) and name.strip():
        return name.strip()
    title = row.get('title')
    return title.split('\n',1)[0].strip() if isinstance(title, str) and title.strip() else None


def clean_path(value):
    return os.path.normcase(os.path.normpath(str(value).removeprefix('\\\\?\\')))


def unique_records(sessions):
    """Remove duplicated files and inherited ancestor events, keep new child work."""
    by_id={s.session_id:s for s in sessions}
    seen=set()
    result=[]
    for session in sessions:
        ancestor_ids=set()
        parent=session.fork_from
        while parent and parent not in ancestor_ids:
            ancestor_ids.add(parent)
            parent=by_id[parent].fork_from if parent in by_id else None
        inherited_ids={r['event_id'] for sid in ancestor_ids if sid in by_id for r in by_id[sid].records}
        for r in session.records:
            key=(session.session_id,r['event_id'])
            if key in seen or r.get('inherited') or r['event_id'] in inherited_ids:
                continue
            seen.add(key);result.append(r)
    return result


def distinct_sessions(rows, cache):
    """Use one most-complete local file for each stable session ID."""
    selected = {}
    for row in rows:
        session = cache[row['rollout_path']]
        current = selected.get(session.session_id)
        if current is None or (len(session.records), session.offset) > (len(current.records), current.offset):
            selected[session.session_id] = session
    return list(selected.values())


class SessionUsage:
    def __init__(self, path):
        self.path = Path(path)
        self.offset = 0
        self.total = {}
        self.previous = {}
        self.last = {}
        self.model = None
        self.effort = None
        self.tier = None
        self.window = None
        self.usd = 0.0
        self.unpriced = set()
        self.limits = None
        self.sample = None
        self.available = False
        self.partial = False
        self.parent = None
        self.inherited = False
        self.session_id = str(self.path)
        self.records = []
        self.seen = set()
        self.raw_total = {}
        self.raw_last = {}
        self.notes = set()
        self.meta_seen = False
        self.fork_from = None
        self.created = None
        self.known = {k:0 for k in TOKEN_KEYS}
        self.coverage = {k:0 for k in TOKEN_KEYS}

    def consume(self, e):
        p = e.get('payload') or {}
        if e.get('type') == 'session_meta':
            if self.meta_seen:
                return  # Copied ancestor metadata must not change child identity.
            self.meta_seen = True
            self.session_id = p.get('id') or self.session_id
            self.fork_from = p.get('forked_from_id')
            self.created = p.get('timestamp')
            source = p.get('source')
            if isinstance(source, dict):
                self.parent = ((source.get('subagent') or {}).get('thread_spawn') or {}).get('parent_thread_id')
            # A fork copies its parent's history; do not count it again in project totals.
            self.inherited = bool(p.get('forked_from_id'))
        if e.get('type') == 'turn_context':
            self.model = p.get('model', self.model)
            self.effort = p.get('effort', p.get('reasoning_effort', self.effort))
            self.tier = p.get('service_tier')
        if e.get('type') != 'event_msg' or p.get('type') != 'token_count':
            return
        if p.get('rate_limits'):
            self.limits = p['rate_limits']
        info = p.get('info')
        if not isinstance(info, dict):
            return
        raw_total = info.get('total_token_usage')
        raw_last = info.get('last_token_usage')
        if not isinstance(raw_total,dict) and not isinstance(raw_last,dict):
            return
        self.raw_total = raw_total if isinstance(raw_total,dict) else {}
        self.raw_last = raw_last if isinstance(raw_last,dict) else {}
        current = normalize_usage(raw_total)
        last = normalize_usage(raw_last)
        self.last = last
        self.window = info.get('model_context_window')
        self.sample = e.get('timestamp')
        self.available = True
        identity = hashlib.sha256(json.dumps([e.get('timestamp'),raw_total,raw_last],sort_keys=True).encode()).hexdigest()
        if identity in self.seen or (raw_total is not None and current == self.previous):
            return
        self.seen.add(identity)
        reset = (current['total_tokens'] is not None and self.previous.get('total_tokens') is not None
                 and current['total_tokens'] < self.previous['total_tokens'])
        if not isinstance(raw_total,dict) or reset:
            if not isinstance(raw_last,dict):
                self.partial = True
                self.notes.add('note_reset_missing_last')
                self.previous = current
                return
            delta = last
            if reset:
                self.notes.add('note_reset_used_last')
                if current['total_tokens'] != last['total_tokens']:
                    self.partial = True
                    self.notes.add('note_reset_carry')
        else:
            delta = {k: (max(0,v-(self.previous.get(k) or 0)) if v is not None
                and (not self.previous or self.previous.get(k) is not None) else last.get(k)) for k,v in current.items()}
        # If the first cumulative record contains older requests, retain the
        # carry but do not pretend it belongs to the current model or day.
        if (not self.previous and current.get('total_tokens') is not None and last.get('total_tokens') is not None
                and current['total_tokens'] > last['total_tokens']):
            carry = {k:max(0,current[k]-last[k]) if current[k] is not None and last[k] is not None else None for k in TOKEN_KEYS}
            self.add_record(carry, None, None, identity+'-carry')
            delta = last
            self.notes.add('note_initial_carry')
        self.add_record(delta, self.model, e.get('timestamp'), identity)
        self.previous = current

    def add_record(self, delta, model, timestamp, identity):
        inherited=bool(self.fork_from and timestamp and self.created and timestamp<self.created)
        record = dict(session=self.session_id,model=model,timestamp=timestamp,event_id=identity,tokens=delta,inherited=inherited)
        self.records.append(record)
        for key,value in delta.items():
            if value is not None:
                self.known[key]+=value
                self.coverage[key]+=1
        self.total = {k:self.known[k] if self.coverage[k]==len(self.records) else None for k in TOKEN_KEYS}
        cost = estimate_usd(delta, model, self.tier, self.last.get('input_tokens'))
        record['usd']=cost
        if cost is None:
            if delta.get('total_tokens'):
                self.unpriced.add(model or 'unknown_breakdown')
        else:
            self.usd += cost
        if delta.get('cache_write_input_tokens') is None:
            self.notes.add('note_cache_write_unavailable')

    def refresh(self):
        try:
            size = self.path.stat().st_size
            if size < self.offset:
                self.__init__(self.path)
            if size == self.offset:
                return
            with self.path.open('rb') as f:
                f.seek(self.offset)
                while line := f.readline():
                    if not line.endswith(b'\n'):
                        break  # Writer may be halfway through a JSON object.
                    self.offset = f.tell()
                    # Ignore conversation content without decoding/parsing it.
                    if not any(t in line[:180] for t in (b'"session_meta"', b'"turn_context"', b'"event_msg"')):
                        continue
                    try:
                        self.consume(json.loads(line))
                    except (ValueError, TypeError, AttributeError):
                        self.partial = True
        except OSError:
            self.partial = True


class CodexActivityDetector:
    """Track explicit Codex turn lifecycle events without rescanning full logs."""
    STALE_SECONDS = 300
    LEGACY_TOKEN_SECONDS = 15
    TAIL_BYTES = 2 * 1024 * 1024
    SWITCH_SECONDS = .4

    def __init__(self):
        self.files = {}
        self.selected_thread = None
        self.pending_thread = None
        self.pending_since = None

    @staticmethod
    def _event_time(value):
        try:
            return datetime.fromisoformat(value.replace('Z','+00:00')).timestamp()
        except (ValueError, TypeError, AttributeError):
            return None

    def _refresh(self, path):
        path = Path(path)
        stat = path.stat()
        entry = self.files.get(path)
        if entry is None or stat.st_size < entry['offset']:
            start = max(0, stat.st_size-self.TAIL_BYTES)
            entry = dict(offset=start, working=None, lifecycle_at=None, token_at=None,
                         mtime=stat.st_mtime)
            self.files[path] = entry
            fresh = True
        else:
            fresh = False
            if stat.st_size == entry['offset']:
                entry['mtime'] = stat.st_mtime
                return entry
        with path.open('rb') as stream:
            stream.seek(entry['offset'])
            if fresh and entry['offset']:
                stream.readline()  # The bounded tail may begin inside a JSON line.
                entry['offset'] = stream.tell()
            while line := stream.readline():
                if not line.endswith(b'\n'):
                    break
                entry['offset'] = stream.tell()
                if not any(marker in line for marker in
                           (b'"task_started"', b'"task_complete"', b'"token_count"')):
                    continue
                try:
                    event = json.loads(line)
                except (ValueError, TypeError):
                    continue
                payload = event.get('payload') or {}
                if event.get('type') != 'event_msg':
                    continue
                kind = payload.get('type')
                if kind == 'task_started':
                    entry['working'] = True
                    entry['lifecycle_at'] = event.get('timestamp')
                elif kind == 'task_complete':
                    entry['working'] = False
                    entry['lifecycle_at'] = event.get('timestamp')
                elif kind == 'token_count':
                    entry['token_at'] = self._event_time(event.get('timestamp'))
        entry['mtime'] = stat.st_mtime
        return entry

    def _select(self, candidates, rows, active_title, now):
        by_id = {row.get('id'):row for row in rows}
        foreground = [candidate for candidate in candidates
                      if active_title in (by_id[candidate['thread']].get('name'),
                                          by_id[candidate['thread']].get('title'))]
        if foreground:
            candidate = max(foreground, key=lambda item:(item['activity_at'],item['thread']))
            selection = 'foreground'
        else:
            candidate = max(candidates, key=lambda item:(item['activity_at'],item['thread']))
            selection = 'most_recent'
        active = {item['thread']:item for item in candidates}
        if self.selected_thread not in active:
            self.selected_thread = candidate['thread']
            self.pending_thread = None
            self.pending_since = None
        elif candidate['thread'] != self.selected_thread:
            if candidate['thread'] != self.pending_thread:
                self.pending_thread = candidate['thread']
                self.pending_since = now
            elif now-self.pending_since >= self.SWITCH_SECONDS:
                self.selected_thread = candidate['thread']
                self.pending_thread = None
                self.pending_since = None
        else:
            self.pending_thread = None
            self.pending_since = None
        selected = dict(active[self.selected_thread])
        selected['selection'] = selection if selected['thread'] == candidate['thread'] else 'debounced_previous'
        selected['working_count'] = len(candidates)
        selected['working_threads'] = sorted(active)
        return selected

    def detect(self, rows, active_title, detection_valid, now=None):
        now = time.time() if now is None else now
        if not detection_valid:
            self.selected_thread = None
            return dict(active=False, valid=False, reason='uia_unavailable')
        if not active_title:
            self.selected_thread = None
            return dict(active=False, valid=True, reason='no_task_window')
        candidates = []
        for row in rows:
            path = row.get('rollout_path')
            if not path:
                continue
            try:
                if now-Path(path).stat().st_mtime > self.STALE_SECONDS:
                    continue
                entry = self._refresh(path)
            except OSError:
                continue
            if entry['working'] is True:
                candidates.append(dict(active=True, valid=True, reason='task_started',
                    thread=row.get('id'), sample=entry['lifecycle_at'], activity_at=entry['mtime']))
            elif (entry['working'] is None and entry['token_at'] is not None
                    and now-entry['token_at'] <= self.LEGACY_TOKEN_SECONDS):
                candidates.append(dict(active=True, valid=True, reason='recent_token_legacy',
                    thread=row.get('id'), activity_at=entry['token_at']))
        if candidates:
            return self._select(candidates, rows, active_title, now)
        self.selected_thread = None
        self.pending_thread = None
        self.pending_since = None
        return dict(active=False, valid=True, reason='no_running_session')

    def enumerate_working_tasks(self, rows, now=None):
        """Focus-independent verified-lifecycle working-thread enumeration.

        Inspects every row with a readable, recently-written rollout
        and returns verified working threads in stable order, WITHOUT
        any title/foreground/UIA input — foreground selection can
        never change membership. Only explicit lifecycle evidence
        counts: a thread joins iff its parsed history ends in
        task_started with no later authoritative task_complete. The
        legacy recent-token fallback (UNKNOWN lifecycle) is
        deliberately excluded here; it stays available to detect()
        for backward-compatible primary-context behavior.

        Shares _refresh parsing with detect(): both callers converge
        on the same entry state regardless of call order, so legacy
        detect() outcomes are unchanged by calling this first, after,
        or not at all. Returns [{thread, activity_at}] with
        activity_at as the lifecycle-instant epoch (or None when the
        stored timestamp is unusable).
        """
        now = time.time() if now is None else now
        found = []
        for row in rows or []:
            path = row.get('rollout_path')
            if not path:
                continue
            try:
                if now - Path(path).stat().st_mtime > self.STALE_SECONDS:
                    continue
                entry = self._refresh(path)
            except OSError:
                continue
            if entry.get('working') is not True:
                continue
            found.append(dict(thread=row.get('id'),
                              activity_at=self._event_time(
                                  entry.get('lifecycle_at'))))
        found.sort(key=lambda item: (item['activity_at'] is None,
                                     item['activity_at'],
                                     item['thread']))
        return found


class CodexStore:
    def __init__(self, home=None):
        self.home = Path(home or os.environ.get('CODEX_HOME') or Path.home()/'.codex')
        self.sessions = {}
        self.state_stamp = None
        self.state = {}
        self.analytics_cache = {}
        self.history_cache = {}
        self.activity = CodexActivityDetector()

    def _task_context(self, row, item, state):
        """Per-task presentation for one verified working thread.

        Additive Multi-Task plumbing: mirrors the working_context
        field semantics (same helpers, same fallbacks) for a single
        enumerated thread, without touching the legacy
        working-context path. Refreshes only this thread's session;
        bounded by the verified-working count. The display carries
        project metadata only: raw thread names/titles (which may
        contain user-derived content) are deliberately omitted here
        — Slice C owns visible neutral labels, and the legacy
        working_context path is unchanged.
        """
        key = row.get('rollout_path')
        session = self.sessions.get(key)
        if session is None:
            session = SessionUsage(key)
            self.sessions[key] = session
        session.refresh()
        summary = summarize(unique_records([session]))
        project, project_source, project_id = project_identity(row, state)
        last_tokens = session.last.get('total_tokens')
        return active_task(
            PROVIDER_CODEX, row.get('id'), working=True,
            activity_valid=True, activity_at=item.get('activity_at'),
            display=dict(project=project),
            presentation=dict(
                tokens=summary['tokens'],
                model=session.model or row.get('model'),
                effort=session.effort or row.get('reasoning_effort'),
                context=(min(100, max(0, 100 * last_tokens / session.window))
                         if last_tokens is not None and session.window
                         else None),
                available=session.available))

    def read(self, active_title='', pinned='', scope='conversation', include_history=False,
             activity_detection_valid=False):
        scope = {'task':'conversation'}.get(scope, scope)
        if scope not in ('global','project','conversation'):
            scope = 'conversation'
        state_path = self.home/'.codex-global-state.json'
        try:
            stamp = state_path.stat().st_mtime_ns
            if stamp != self.state_stamp:
                self.state = json.loads(state_path.read_text(encoding='utf-8'))
                self.state_stamp = stamp
        except (OSError, ValueError):
            pass
        databases = list(self.home.glob('state_*.sqlite'))
        if not databases:
            return dict(status='status_no_local_data', rows=[],
                        codex_activity=dict(active=False,valid=False,reason='no_database'))
        db = max(databases, key=lambda p: int(p.stem.split('_')[-1]))
        try:
            with closing(sqlite3.connect(db.as_uri()+'?mode=ro', uri=True, timeout=.2)) as c:
                c.row_factory = sqlite3.Row
                columns = {r[1] for r in c.execute('pragma table_info(threads)')}
                fields = [x for x in ('id','name','title','cwd','rollout_path','model','reasoning_effort','source','project_id','git_origin_url','updated_at','archived') if x in columns]
                rows = [dict(r) for r in c.execute(f"select {','.join(fields)} from threads order by updated_at desc")]
        except sqlite3.Error:
            return dict(status='status_database_unavailable', rows=[],
                        codex_activity=dict(active=False,valid=False,reason='database_unavailable'))
        desktop = [r for r in rows if r.get('source') in ('vscode','desktop') and not r.get('archived')]
        eligible = [r for r in rows if r.get('rollout_path')]
        codex_activity = self.activity.detect(desktop, active_title, activity_detection_valid)
        chosen, mode = select_thread(desktop, active_title, pinned)
        state = self.state
        working_row = next((row for row in desktop if row.get('id') == codex_activity.get('thread')), None)
        if scope == 'project' and not pinned and working_row:
            chosen, mode = working_row, 'working'
        working_context = None
        if working_row:
            key = working_row.get('rollout_path')
            if key not in self.sessions:
                self.sessions[key] = SessionUsage(key)
            working_session = self.sessions[key]
            working_session.refresh()
            working_summary = summarize(unique_records([working_session]))
            working_project, project_source, working_project_id = project_identity(working_row, state)
            last_tokens = working_session.last.get('total_tokens')
            working_context = dict(
                thread=working_row.get('id'),
                title=conversation_title(working_row),
                project=working_project, project_source=project_source, project_id=working_project_id,
                status='working', tokens=working_summary['tokens'], available=working_session.available,
                model=working_session.model or working_row.get('model'),
                effort=working_session.effort or working_row.get('reasoning_effort'),
                context=(min(100,max(0,100*last_tokens/working_session.window))
                         if last_tokens is not None and working_session.window else None),
                sample=working_session.sample, selection=codex_activity.get('selection'),
                activity_reason=codex_activity.get('reason'))
        by_id = {row.get('id'): row for row in desktop}
        active_tasks = []
        for item in self.activity.enumerate_working_tasks(desktop):
            row = by_id.get(item['thread'])
            if row is None:
                continue
            active_tasks.append(self._task_context(row, item, state))
        if scope != 'global' and not chosen:
            identity = dict(scope_type=scope, unavailable=True)
            if scope == 'conversation':
                identity['thread_id'] = pinned or None
            return dict(status='status_pinned_unavailable' if pinned else 'status_no_desktop_task',
                        rows=desktop, scope=scope, scope_identity=identity,
                        codex_activity=codex_activity, working_context=working_context,
                        active_tasks=active_tasks)

        chosen_project, chosen_project_source, chosen_project_id = (
            project_identity(chosen, state) if chosen else (None, 'unavailable', None))
        if scope == 'global':
            relevant = eligible
            scope_identity = dict(scope_type='global', locally_recorded=True)
        elif scope == 'project':
            scope_identity = dict(scope_type='project', project_id=chosen_project_id,
                project_name=chosen_project, project_source=chosen_project_source)
            if chosen_project_id is None:
                scope_identity['unavailable'] = True
                return dict(status='status_project_unavailable', rows=desktop, scope=scope,
                            scope_identity=scope_identity, codex_activity=codex_activity,
                            working_context=working_context, active_tasks=active_tasks)
            relevant = [r for r in eligible if project_identity(r, state)[2] == chosen_project_id]
        else:
            relevant = [chosen]
            scope_identity = dict(scope_type='conversation', thread_id=chosen.get('id'),
                conversation_title=conversation_title(chosen), project_id=chosen_project_id,
                project_name=chosen_project, project_source=chosen_project_source)

        working_ids = set(codex_activity.get('working_threads', []))
        scope_working = working_ids.intersection(row.get('id') for row in relevant)
        scope_activity = dict(active=bool(scope_working), valid=bool(codex_activity.get('valid')),
                              working_count=len(scope_working))
        refresh_rows = relevant + ([working_row] if working_row and working_row not in relevant else [])
        for row in refresh_rows:
            key = row.get('rollout_path')
            if not key:
                continue
            if key not in self.sessions:
                self.sessions[key] = SessionUsage(key)
            self.sessions[key].refresh()
        sessions = distinct_sessions(relevant, self.sessions)
        current = self.sessions.get(chosen.get('rollout_path')) if chosen else None
        if current is None and sessions:
            current = sessions[0]
        records = unique_records(sessions)
        excluded_forks = sum(len(s.records) for s in sessions)-len(records)
        signature = tuple(sorted((s.session_id,s.offset) for s in sessions))
        if self.analytics_cache.get('signature') != signature:
            self.analytics_cache = dict(signature=signature,summary=aggregate(records))
        analysis = self.analytics_cache['summary']
        tokens = analysis['tokens']
        unknown = sorted({r.get('model') or 'unknown_breakdown' for r in records if r.get('usd') is None and r['tokens'].get('total_tokens')})
        last_tokens = current.last.get('total_tokens') if current else None
        context = (min(100, max(0, 100*last_tokens/current.window))
                   if current and last_tokens is not None and current.window else None)
        partial = any(s.partial or not s.available for s in sessions)
        history = dict(analysis, partial=partial) if include_history else None
        names = {self.sessions[r['rollout_path']].session_id:conversation_title(r)
                 for r in relevant}
        available = any(s.available for s in sessions)
        scope_result = dict(identity=scope_identity, tokens=tokens, analytics=analysis,
                            available=available, count=len(sessions), partial=partial)
        if scope == 'global':
            display_project, display_title = 'display_all_usage', 'display_local_history'
        elif scope == 'project':
            display_project = display_title = chosen_project or 'project_unavailable'
        else:
            display_project = chosen_project or 'project_unavailable'
            display_title = conversation_title(chosen) or 'display_untitled'
        current_summary = summarize(unique_records([current])) if current else summarize([])
        return dict(rows=desktop, status='' if relevant else 'status_no_usage', mode=mode,
                    thread=chosen.get('id') if chosen else None, title=display_title,
                    project=display_project, scope=scope, scope_identity=scope_identity,
                    scope_result=scope_result, tokens=tokens, available=available,
                    model=(current.model or chosen.get('model')) if current and chosen else None,
                    effort=(current.effort or chosen.get('reasoning_effort')) if current and chosen else None,
                    tier=current.tier if current else None, context=context,
                    context_tokens=last_tokens, context_window=current.window if current else None,
                    usd=sum(r.get('usd') or 0 for r in records), unknown=unknown,
                    partial=partial, excluded_forks=excluded_forks, count=len(sessions),
                    sample=current.sample if current else None,
                    limits=current.limits if current else None, analytics=analysis, history=history,
                    session_names=names, current_session=current_summary,
                    raw_total=current.raw_total if current else {}, raw_last=current.raw_last if current else {},
                    notes=sorted(set().union(*(s.notes for s in sessions))), codex_activity=codex_activity,
                    working_context=working_context, scope_activity=scope_activity,
                    active_tasks=active_tasks)


def sample_age(timestamp):
    try:
        return max(0, time.time()-datetime.fromisoformat(timestamp.replace('Z','+00:00')).timestamp())
    except (ValueError, TypeError, AttributeError):
        return None
