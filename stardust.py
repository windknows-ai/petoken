"""Stardust (2.4): what the AIs got done for you, saved up for unlocks.

Like companionship points it rewards work that helped you, never tokens
spent: a finished AI task (+5, +2 when it took under a minute), AI work you
accepted after review (+12), a focus round (+8), and the AI's working time
(+1 per 6 minutes of a finished task, at most +60 a day). A heavy day of work
earns about 300, and work never earns more than WORK_DAILY_CAP a day (sign-in,
streaks and collection bonuses come on top). Each award counts
once (by reason and a reference), stored with the points under a ``star_``
reason so the two totals never mix.

Unlocks: the Meteor star-ring skin at 150, Aurora at 400, and her third form,
"Starsea Awakening", at 1000 (its pictures arrive later; until then the
unlock is recorded and announced).
"""
from __future__ import annotations

import time
from datetime import datetime

GAINS = dict(star_task=5, star_task_short=2, star_review=12, star_focus=8)
TIME_STEP_S = 6 * 60
TIME_DAILY_CAP = 60
WORK = ('star_task', 'star_task_short', 'star_review', 'star_focus', 'star_time', 'star_daily')
WORK_DAILY_CAP = 300                  # What a heavy day of work earns at most (one wish is 250).
UNLOCKS = (('skin_meteor', 150), ('skin_aurora', 400), ('starsea', 1000))
SKINS = ('default', 'meteor', 'aurora')


def unlocked(total):
    return [name for name, need in UNLOCKS if total >= need]


def next_unlock(total):
    """(name, stardust still needed) or None when everything is unlocked."""
    for name, need in UNLOCKS:
        if total < need:
            return name, need - total
    return None


class Stardust:
    def __init__(self, panel, clock=time.time):
        self.panel = panel
        self.clock = clock

    @property
    def store(self):
        opener = getattr(self.panel, 'workbench_store', None)
        return opener() if callable(opener) else None

    def total(self):
        store = self.store
        try:
            return store.stardust() if store is not None else 0
        except Exception:
            return 0

    def _add(self, reason, ref, amount):
        store = self.store
        if store is None or amount <= 0:
            return False
        try:
            return store.add_points(reason, str(ref)[:200], int(amount), self.clock())
        except Exception:
            return False

    def gain(self, reason, ref, amount=None):
        """Add stardust once per (reason, ref); returns what it newly unlocked."""
        before = self.total()
        amount = GAINS.get(reason, 0) if amount is None else amount
        if reason in WORK:
            amount = min(amount, max(0, WORK_DAILY_CAP - self.work_today()))
        if not self._add(reason, ref, amount):
            return []
        fresh = [name for name in unlocked(self.total()) if name not in unlocked(before)]
        for name in fresh:
            self._celebrate(name)
        return fresh

    def on_finished(self, event):
        """A finished AI task: stardust for it and for its working time."""
        ref = f"{event.get('provider', '')}:{event.get('task_key', '')}:{round(event.get('at') or 0)}"
        seconds = None
        try:
            from notifications import parse_recap
            recap = parse_recap(event.get('detail') or '')
            seconds = recap.get('seconds') if recap else None
        except Exception:
            seconds = None
        short = seconds is not None and seconds < 60
        fresh = self.gain('star_task_short' if short else 'star_task', ref)
        fresh += self._daily_goal()
        if seconds:
            steps = int(seconds // TIME_STEP_S)
            room = TIME_DAILY_CAP - self.time_today()
            amount = min(steps, max(0, room))
            if amount > 0:
                fresh += self.gain('star_time', ref, amount)
        return fresh

    DAILY_TASKS, DAILY_BONUS = 3, 20

    def _daily_goal(self):
        """The day's small goal (2.5): three finished AI tasks earn a bonus once."""
        store = self.store
        if store is None:
            return []
        day = datetime.fromtimestamp(self.clock()).replace(hour=0, minute=0, second=0, microsecond=0)
        try:
            rows = store.points_log(400)
        except Exception:
            return []
        done = sum(1 for r in rows if str(r['reason']).startswith('star_task') and r['at'] >= day.timestamp())
        if done >= self.DAILY_TASKS:
            return self.gain('star_daily', day.date().isoformat(), self.DAILY_BONUS)
        return []

    def work_today(self):
        """Stardust earned by work since midnight (the part WORK_DAILY_CAP limits)."""
        store = self.store
        if store is None:
            return 0
        day = datetime.fromtimestamp(self.clock()).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        try:
            return sum(store.stardust(reason=reason, since=day) for reason in WORK)
        except Exception:
            return 0

    def time_today(self):
        store = self.store
        if store is None:
            return 0
        day = datetime.fromtimestamp(self.clock()).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        try:
            return store.stardust(reason='star_time', since=day)
        except Exception:
            return 0

    def _celebrate(self, name):
        hook = getattr(self.panel, 'stardust_unlocked', None)
        if callable(hook):
            try:
                hook(name)
            except Exception:
                pass
