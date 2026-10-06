"""Companionship points, stickers and weekly project usage goals (2.0).

Points come from things that help you, never from spending tokens: todos
done, AI work you accepted, focus sessions, breaks taken, and weeks a
project stayed under its usage goal. Each award counts once (by reason and
a reference such as the todo id). Milestones earn stickers, shown on the
Collection page of the workbench.

Goals: a project may have a weekly limit in tokens and/or API-equivalent
dollars. Usage is summed from the report data (this week, Monday 00:00
local time). She gets worried at 80%, you get one notice at 100%, and when
a week ends under the goal she is proud of it.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta
from pathlib import Path

from localization import text

POINTS = dict(todo_done=2, todo_accepted=5, focus_done=10, break_taken=3, goal_week=10)
STICKERS = (
    # id, how it is earned (checked by ``_check``).
    'first_project', 'first_weekly', 'focus_10', 'streak_7', 'goal_week', 'todos_100',
)
WORRY_AT = .8


def week_start(now):
    day = datetime.fromtimestamp(now).replace(hour=0, minute=0, second=0, microsecond=0)
    return (day - timedelta(days=day.weekday())).timestamp()


def project_names(project):
    names = {project['name'].lower()}
    if project.get('directory'):
        names.add(Path(project['directory']).name.lower())
    return names


def project_usage(events, project, start, end):
    """(tokens, usd, priced) a project used between ``start`` and ``end``."""
    names = project_names(project)
    tokens, usd, priced = 0, 0.0, True
    for event in events or []:
        if not start <= event.get('at', 0) < end or (event.get('project') or '').lower() not in names:
            continue
        tokens += event.get('tokens') or 0
        if event.get('usd') is None:
            priced = priced and not event.get('tokens')
        else:
            usd += event['usd']
    return tokens, usd, priced


def goal_ratio(goal, tokens, usd):
    """The share of the goal used: the larger of the token and money shares."""
    shares = []
    if goal.get('weekly_tokens'):
        shares.append(tokens / goal['weekly_tokens'])
    if goal.get('weekly_usd'):
        shares.append(usd / goal['weekly_usd'])
    return max(shares) if shares else None


class Companion:
    """Awards points and stickers, and watches usage goals."""

    def __init__(self, panel, store=None, clock=time.time):
        self.panel = panel
        self._store = store
        self.clock = clock

    @property
    def store(self):
        if self._store is not None:
            return self._store
        opener = getattr(self.panel, 'workbench_store', None)
        return opener() if callable(opener) else None

    @property
    def language(self):
        return self.panel.prefs.get('language')

    # Points and stickers -----------------------------------------------
    def award(self, reason, ref):
        """Add the points for ``reason`` once per ``ref``; returns new stickers."""
        store = self.store
        if store is None or reason not in POINTS:
            return []
        try:
            if not store.add_points(reason, str(ref), POINTS[reason], self.clock()):
                return []
        except Exception:
            return []
        return self._check()

    def earn(self, sticker):
        store = self.store
        if store is None:
            return False
        try:
            fresh = store.earn(sticker, self.clock())
        except Exception:
            return False
        if fresh:
            self._celebrate(sticker)
        return fresh

    def _check(self):
        store = self.store
        try:
            have = store.achievements()
            todos = store.count_points('todo_done')
            focus = store.list_focus()
        except Exception:
            return []
        wanted = []
        if todos >= 100:
            wanted.append('todos_100')
        done = [f for f in focus if f['completed']]
        if len(done) >= 10:
            wanted.append('focus_10')
        days = {datetime.fromtimestamp(f['started_at']).date() for f in done}
        if days:
            latest = max(days)
            if all(latest - timedelta(days=n) in days for n in range(7)):
                wanted.append('streak_7')
        try:
            if store.count_points('goal_week'):
                wanted.append('goal_week')
        except Exception:
            pass
        fresh = [s for s in wanted if s not in have and self.earn(s)]
        return fresh

    def todo_done(self, todo):
        """A todo ticked off (by you, or by accepting the AI's work)."""
        fresh = self.award('todo_done', todo['id'])
        if todo.get('project_id'):
            if self.earn('first_project'):
                fresh.append('first_project')
        return fresh

    def _celebrate(self, sticker):
        pet = getattr(self.panel, 'pet', None)
        if pet is not None:
            pet.interact('clap', 3)
        notice = getattr(self.panel, 'tray_notice', None)
        if notice is not None:
            notice(text('sticker_earned', self.language, name=text(f'sticker_{sticker}', self.language)),
                   text(f'sticker_{sticker}_how', self.language))

    # Usage goals --------------------------------------------------------
    def check_goals(self, events, now=None):
        """Worry at 80%, one notice at 100%, pride after a week under goal."""
        store = self.store
        if store is None:
            return []
        now = self.clock() if now is None else now
        try:
            goals = store.list_goals()
            projects = {p['id']: p for p in store.list_projects()}
        except Exception:
            return []
        start = week_start(now)
        previous = week_start(start - 1)
        alerts = dict(self.panel.prefs.get('goal_alerts') or {})
        out = []
        for goal in goals:
            project = projects.get(goal['project_id'])
            if project is None:
                continue
            state = dict(alerts.get(goal['project_id']) or {})
            if state.get('week') != start:
                # A new week: was the last one under the goal?
                if state.get('week') == previous:
                    tokens, usd, _ = project_usage(events, project, previous, start)
                    ratio = goal_ratio(goal, tokens, usd)
                    if ratio is not None and ratio < 1:
                        out.append(('proud', project))
                        self.award('goal_week', f"{goal['project_id']}:{previous:.0f}")
                state = dict(week=start, level=0)
            tokens, usd, _ = project_usage(events, project, start, now + 1)
            ratio = goal_ratio(goal, tokens, usd)
            level = 100 if ratio is not None and ratio >= 1 else 80 if ratio is not None and ratio >= WORRY_AT else 0
            if level > state.get('level', 0):
                out.append(('over' if level == 100 else 'worried', project, ratio))
            state['level'] = max(level, state.get('level', 0))
            alerts[goal['project_id']] = state
        self.panel.prefs['goal_alerts'] = alerts
        self._announce(out)
        return out

    def _announce(self, alerts):
        pet = getattr(self.panel, 'pet', None)
        notice = getattr(self.panel, 'tray_notice', None)
        for alert in alerts:
            kind, project = alert[0], alert[1]
            if pet is not None:
                pet.interact({'proud': 'proud', 'worried': 'worried', 'over': 'grievance'}[kind], 4)
            if notice is not None:
                if kind == 'proud':
                    notice(text('goal_proud', self.language, project=project['name']), '')
                else:
                    notice(text(f'goal_{kind}', self.language, project=project['name'],
                                percent=round(alert[2] * 100)), text('goal_body', self.language))
