"""Daily and weekly reports and task history (V1.6 D).

Sources, all local:
- Usage events: every Claude Code response (time, tokens, API-equivalent
  cost) from its transcripts, and every Codex usage record from Codex's
  rollouts. Tokens and cost are counted on the day they happened, so a
  long task that spans days is split correctly.
- Claude Code activity (claude_recap.activity): each turn from your prompt
  to Claude's last reply (AI working time) and every successful file edit,
  straight from the transcripts, so it covers time Petoken was not running.
- Notifications (notifications.py): finished / failed tasks and approvals,
  plus the files listed in Codex recaps (Codex has no per-turn timing yet).
- History: Claude sessions from the transcripts, Codex threads from
  Codex's ``task_history``.

Reading Codex history can take seconds, so ``load`` runs in a worker; the
summaries are plain arithmetic on what it returns. Cost is the API-
equivalent estimate, never a subscription bill: the sum of responses with a
known price, flagged ``partial`` when some responses have none.
"""
from __future__ import annotations

import time
from collections import defaultdict
from datetime import datetime, timedelta

from notifications import parse_recap


def _number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def period(kind, now):
    """(start, end, previous_start) epoch seconds for 'today' or 'week'."""
    local = datetime.fromtimestamp(now)
    midnight = local.replace(hour=0, minute=0, second=0, microsecond=0)
    if kind == 'week':
        start = midnight - timedelta(days=local.weekday())
        previous = start - timedelta(days=7)
    else:
        start = midnight
        previous = start - timedelta(days=1)
    return start.timestamp(), now, previous.timestamp()


def _iso(value):
    from claude_usage import _iso_epoch
    return _iso_epoch(value)


def claude_sources(store=None):
    """(usage events, history rows) from Claude Code's transcripts."""
    from claude_usage import ClaudeStore, project_identity
    store = store or ClaudeStore()
    store.read(scope='global')
    events, history = [], []
    for session in store._sessions().values():
        project = project_identity(session.get('cwd'))[0] if session.get('cwd') else None
        tokens, usd, priced = 0, 0.0, True
        for record in (session.get('records') or {}).values():
            at = _iso(record.get('timestamp'))
            total = _number((record.get('tokens') or {}).get('total_tokens'))
            cost = _number(record.get('usd'))
            if at is not None:
                events.append(dict(provider='claude', session=session['id'], at=at, tokens=total,
                                   usd=cost, project=project))
            tokens += total or 0
            priced = priced and cost is not None
            usd += cost or 0
        if session.get('records'):
            history.append(dict(provider='claude', id=session['id'], title=session.get('title'),
                                project=project, started_at=session.get('first_at'),
                                finished_at=session.get('last_at'), tokens=tokens,
                                usd=usd if priced else None))
    return events, history


def codex_sources(store=None):
    """(usage events, history rows) from Codex's local data."""
    from usage import CodexStore, unique_records
    store = store or CodexStore()
    store.read(scope='global')
    projects = {}
    rows = store.task_history(None)
    for row in rows:
        projects[row['thread_id']] = row.get('project')
    events = []
    for record in unique_records(getattr(store, '_scope_sessions', []) or []):
        at = _iso(record.get('timestamp'))
        if at is None:
            continue
        events.append(dict(provider='codex', session=record.get('session'), at=at,
                           tokens=_number((record.get('tokens') or {}).get('total_tokens')),
                           usd=_number(record.get('usd')), project=projects.get(record.get('session'))))
    history = [dict(provider='codex', id=row['thread_id'], title=row.get('title'), project=row.get('project'),
                    started_at=row.get('started_at'), finished_at=row.get('finished_at'),
                    tokens=row.get('total_tokens'), usd=row.get('usd')) for row in rows]
    return events, history


def load(now=None):
    """Everything the report needs; a provider that fails is just missing."""
    now = time.time() if now is None else now
    events, history, missing = [], [], []
    activity = dict(turns=[], edits=[])
    try:
        import claude_recap
        from claude_usage import default_home
        since = min(period('week', now)[0], period('today', now)[2])
        activity = claude_recap.activity(default_home(), since)
    except Exception:
        pass
    for name, source in (('claude', claude_sources), ('codex', codex_sources)):
        try:
            more_events, more_history = source()
        except Exception:
            missing.append(name)
            continue
        events += more_events
        history += more_history
    history.sort(key=lambda row: -(row.get('finished_at') or row.get('started_at') or 0))
    return dict(events=events, history=history, missing=missing, activity=activity)


def _usage(events, start, end):
    per = defaultdict(lambda: dict(tokens=0, usd=0.0, priced=True, sessions=set()))
    projects = defaultdict(lambda: dict(tokens=0))
    for event in events:
        if not start <= event['at'] < end:
            continue
        slot = per[event['provider']]
        slot['tokens'] += event.get('tokens') or 0
        slot['sessions'].add(event.get('session'))
        if event.get('usd') is None:
            slot['priced'] = slot['priced'] and not event.get('tokens')
        else:
            slot['usd'] += event['usd']
        if event.get('project'):
            projects[event['project']]['tokens'] += event.get('tokens') or 0
    providers = {name: dict(tokens=slot['tokens'], usd=slot['usd'], partial=not slot['priced'],
                            tasks=len(slot['sessions'] - {None}))
                 for name, slot in per.items()}
    top = sorted(projects.items(), key=lambda item: (-item[1]['tokens'], item[0]))[:3]
    return providers, [dict(name=name, tokens=values['tokens']) for name, values in top]


def summarize(data, notices, kind, now):
    """The report card for 'today' or 'week' (plus the previous period)."""
    start, end, previous_start = period(kind, now)
    providers, projects = _usage(data.get('events') or [], start, end)
    before, _ = _usage(data.get('events') or [], previous_start, previous_start + (end - start))
    counts = defaultdict(int)
    activity = data.get('activity') or {}
    seconds = sum(max(0.0, min(stop, end) - max(begin, start))
                  for begin, stop, _project in activity.get('turns') or [])
    files = {f'{project}/{path}' for at, project, path in activity.get('edits') or [] if start <= at < end}
    for notice in notices or []:
        if not start <= (notice.get('at') or 0) < end:
            continue
        counts[notice.get('kind')] += 1
        recap = parse_recap(notice.get('detail')) if notice.get('kind') == 'finished' else None
        if recap and notice.get('provider') == 'codex':
            files.update(f"{notice.get('project')}/{name}" for name in recap.get('names') or [])
    tokens = sum(p['tokens'] for p in providers.values())
    previous_tokens = sum(p['tokens'] for p in before.values())
    return dict(kind=kind, start=start, end=end, providers=providers, projects=projects,
                tokens=tokens, usd=sum(p['usd'] for p in providers.values()),
                partial=any(p['partial'] for p in providers.values()),
                change=None if not previous_tokens else (tokens - previous_tokens) / previous_tokens,
                finished=counts['finished'], failed=counts['failed'], approvals=counts['needs_approval'],
                files=len(files), seconds=seconds, missing=list(data.get('missing') or []))


def search(history, query='', provider=None, since=None):
    """History rows matching a text query, provider and start time."""
    words = [w for w in (query or '').lower().split() if w]
    out = []
    for row in history or []:
        if provider and row.get('provider') != provider:
            continue
        when = row.get('finished_at') or row.get('started_at')
        if since is not None and (when is None or when < since):
            continue
        haystack = ' '.join(str(row.get(k) or '') for k in ('title', 'project')).lower()
        if all(word in haystack for word in words):
            out.append(row)
    return out
