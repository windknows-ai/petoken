"""Predictions and suggestions (V1.6 "time-saving assistant", part A).

Petoken already sees every task's context and both apps' quota windows;
this module turns those numbers into advice before something goes wrong:

- Pace: when the 5-hour or weekly window will run out at the current
  pace, and whether that is before it resets. The 5-hour pace is the
  last hour's samples when they span at least RECENT_SPAN_S (so a pause
  shows as "not running out"), otherwise the average since the window
  opened; the weekly pace is always the window average.
- Switch: when one app is out (or about to be) and the other open app
  still has plenty left, suggest working there.
- Context: a task at CONTEXT_FULL_USED % or more of its context window
  should be compacted or restarted soon.
- Stuck: a running task whose tokens and context have not moved for
  STUCK_AFTER_S (and that is not waiting for approval) may be stuck.
- Back: a window that ran out (or a rate-limit error) is announced again
  when it resets, so you know you can continue.

Everything is local arithmetic on numbers Petoken already reads. Hints go
to the usage card; the same conditions raise one notification each.
"""
from __future__ import annotations

import time

from usage import quota_window

CONTEXT_FULL_USED = 90
CONTEXT_REARM_USED = 70        # Below this again (after /compact) a task may warn again.
STUCK_AFTER_S = 20 * 60
RECENT_SPAN_S = 10 * 60
HISTORY_S = 60 * 60
AVERAGE_MIN_ELAPSED_S = 30 * 60
WARN_WITHIN_S = 60 * 60        # Notify when the 5-hour window runs out within this.
SWITCH_MIN_LEFT = 40           # The other app needs this much left to be suggested.
WINDOWS = (300, 10080)


def _number(value):
    return (value if isinstance(value, (int, float)) and not isinstance(value, bool)
            else None)


class QuotaPace:
    """Usage samples per (provider, window) and the pace they imply."""

    def __init__(self):
        self._samples = {}

    def observe(self, provider, limits, now=None):
        now = time.time() if now is None else now
        for minutes in WINDOWS:
            key = (provider, minutes)
            window = quota_window(limits, minutes, now)
            if not window or window.get('remaining') is None or window.get('expired'):
                self._samples.pop(key, None)
                continue
            used, reset = 100 - window['remaining'], window.get('reset')
            samples = self._samples.setdefault(key, [])
            if samples:
                last_used, last_reset = samples[-1][1], samples[-1][2]
                if used < last_used - 0.5 or (reset is not None and last_reset is not None
                                              and abs(reset - last_reset) > 600):
                    samples.clear()  # A new window opened.
            samples.append((now, used, reset))
            while len(samples) > 2 and samples[1][0] <= now - HISTORY_S:
                samples.pop(0)

    def status(self, provider, minutes, now=None):
        """dict(left, reset_in, run_out_in) for one window, or None.

        ``run_out_in`` is None when the pace is unknown or flat.
        """
        now = time.time() if now is None else now
        samples = self._samples.get((provider, minutes))
        if not samples:
            return None
        at, used, reset = samples[-1]
        left = max(0.0, 100 - used)
        reset_in = None if reset is None else max(0.0, reset - now)
        rate = None
        first = samples[0]
        if minutes == 300 and at - first[0] >= RECENT_SPAN_S:
            rate = (used - first[1]) / (at - first[0])
        elif reset is not None:
            elapsed = at - (reset - minutes * 60)
            if elapsed >= AVERAGE_MIN_ELAPSED_S and used >= 1:
                rate = used / elapsed
        run_out_in = None
        if left <= 0:
            run_out_in = 0.0
        elif rate and rate > 0:
            run_out_in = max(0.0, left / rate - (now - at))
        return dict(left=left, reset_in=reset_in, run_out_in=run_out_in)

    def short(self, provider, minutes, now=None):
        """The window's status when it runs out before it resets."""
        status = self.status(provider, minutes, now)
        if not status or status['run_out_in'] is None:
            return None
        if status['reset_in'] is not None and status['run_out_in'] >= status['reset_in']:
            return None
        return status


class Assistant:
    """Turns task and quota observations into hints and one-off events."""

    def __init__(self):
        self.pace = QuotaPace()
        self._progress = {}     # task identity -> (fingerprint, since)
        self._waiting = set()   # tasks waiting for approval since their last progress
        self._stuck_sent = {}   # task identity -> progress stamp already announced
        self._context_warned = set()
        self._exhausted = {}    # provider -> reset time of a window that ran out

    # Observations -------------------------------------------------------
    def observe_tasks(self, tasks, now=None):
        """Track progress; returns stuck and context-full events."""
        now = time.time() if now is None else now
        events, seen = [], set()
        for task in tasks or []:
            identity = (task.get('provider_id'), task.get('task_key'))
            if not all(isinstance(part, str) and part for part in identity):
                continue
            seen.add(identity)
            presentation = task.get('presentation') or {}
            project = (task.get('display') or {}).get('project') or ''
            context = _number(presentation.get('context'))
            fingerprint = (repr(presentation.get('tokens')), context)
            previous = self._progress.get(identity)
            if previous is None or previous[0] != fingerprint:
                self._progress[identity] = (fingerprint, now)
                self._waiting.discard(identity)
            elif (now - previous[1] >= STUCK_AFTER_S and task.get('awaiting_approval') is not True
                  and identity not in self._waiting and self._stuck_sent.get(identity) != previous[1]):
                self._stuck_sent[identity] = previous[1]
                events.append(dict(kind='stuck', provider=identity[0], task_key=identity[1], at=now,
                                   project=project, detail=f'{(now - previous[1]) // 60:.0f}',
                                   dedupe=f'stuck:{identity[0]}:{identity[1]}:{previous[1]:.0f}'))
            if context is not None and context >= CONTEXT_FULL_USED:
                if identity not in self._context_warned:
                    self._context_warned.add(identity)
                    events.append(dict(kind='context_full', provider=identity[0], task_key=identity[1],
                                       at=now, project=project, detail=f'{max(0, 100 - context):.0f}',
                                       dedupe=f'context:{identity[0]}:{identity[1]}:{now:.0f}'))
            elif context is not None and context < CONTEXT_REARM_USED:
                self._context_warned.discard(identity)
        for identity in list(self._progress):
            if identity not in seen:
                self._progress.pop(identity)
                self._waiting.discard(identity)
                self._stuck_sent.pop(identity, None)
        return events

    def note_event(self, event):
        """Approval waits are not stuck tasks."""
        if (event or {}).get('kind') == 'needs_approval':
            self._waiting.add((event.get('provider'), event.get('task_key')))

    def expect_reset(self, provider, limits, now=None):
        """A rate-limit error: announce when the tightest window resets."""
        now = time.time() if now is None else now
        windows = [w for w in (quota_window(limits, m, now) for m in WINDOWS)
                   if w and w.get('reset') is not None and w['reset'] > now]
        if not windows:
            return  # Reset time unknown: nothing to count down to.
        tight = [w for w in windows if w.get('remaining') is not None and w['remaining'] <= 5]
        self._exhausted[provider] = (max(w['reset'] for w in tight) if tight
                                     else min(w['reset'] for w in windows))

    def observe_quota(self, quotas, now=None):
        """``quotas``: {provider: limits}. Returns forecast and back events."""
        now = time.time() if now is None else now
        events = []
        for provider, limits in quotas.items():
            self.pace.observe(provider, limits, now)
            for minutes in WINDOWS:
                window = quota_window(limits, minutes, now)
                if (window and window.get('remaining') is not None and window['remaining'] <= 0
                        and window.get('reset') is not None and window['reset'] > now):
                    self._exhausted[provider] = max(self._exhausted.get(provider, 0), window['reset'])
            short = self.pace.short(provider, 300, now)
            if short and 0 < short['left'] and short['run_out_in'] <= WARN_WITHIN_S:
                reset = self.pace._samples[(provider, 300)][-1][2]
                other = self.better_provider(provider, quotas, now)
                events.append(dict(kind='forecast', provider=provider, task_key='', at=now, project='',
                                   detail=f"{short['run_out_in']:.0f}|{other or ''}",
                                   dedupe=f"forecast:{provider}:{reset if reset is not None else int(now // 18000)}"))
        for provider, reset in list(self._exhausted.items()):
            if now >= reset:
                del self._exhausted[provider]
                events.append(dict(kind='quota_back', provider=provider, task_key='', at=now,
                                   project='', detail='', dedupe=f'back:{provider}:{reset:.0f}'))
        return events

    # Advice -------------------------------------------------------------
    def better_provider(self, provider, quotas, now=None):
        """Another app with at least SWITCH_MIN_LEFT % in every window, or None."""
        now = time.time() if now is None else now
        for other, limits in quotas.items():
            if other == provider:
                continue
            windows = [quota_window(limits, m, now) for m in WINDOWS]
            windows = [w for w in windows if w and not w.get('expired')]
            if windows and all(w.get('remaining') is not None and w['remaining'] >= SWITCH_MIN_LEFT
                               for w in windows):
                return other
        return None

    def hint(self, provider, task_key, context, quotas, now=None):
        """The most useful one-line advice for an app's card section.

        Returns (key, values) for localization, or None.
        """
        now = time.time() if now is None else now
        other = self.better_provider(provider, quotas, now) if provider in quotas else None
        five = self.pace.status(provider, 300, now)
        if five and five['left'] <= 0:
            return ('hint_out_switch', dict(other=other)) if other else ('hint_out', {})
        short = self.pace.short(provider, 300, now)
        if short:
            return (('hint_run_out_switch', dict(time=short['run_out_in'], other=other)) if other
                    else ('hint_run_out', dict(time=short['run_out_in'])))
        context = _number(context)
        if context is not None and context >= CONTEXT_FULL_USED:
            return 'hint_context_full', dict(left=max(0, 100 - context))
        week = self.pace.short(provider, 10080, now)
        if week:
            return 'hint_week_run_out', dict(time=week['run_out_in'])
        identity = (provider, task_key)
        progress = self._progress.get(identity)
        if (progress and identity not in self._waiting
                and now - progress[1] >= STUCK_AFTER_S):
            return 'hint_stuck', dict(minutes=(now - progress[1]) // 60)
        return None
