"""Late-night mode and the sit-too-long reminder (2.3).

Late-night mode: from the evening hour the user chose (23:00 by default)
until morning (07:00), and optionally whenever Do Not Disturb is on, she
wears her moon pajamas and her idle and mood poses become the sleepy night
versions (hugging her moon pillow, yawning, asleep on it). Task poses stay as
they are: she still works when an AI does. Game mode wins over it. Switching
it by hand (her menu, under Show) lasts until the night window next changes.
Until the night art exists she simply keeps her usual poses.

Sit-too-long reminder: after the user has been using the computer for a
stretch (an hour by default) without a real pause (five minutes with no
input), she stretches and a notice suggests getting up. Not while focusing
(focus has its own breaks) or gaming, and only the pose during Do Not
Disturb.
"""
from __future__ import annotations

import time
from datetime import datetime

from PySide6.QtCore import QObject, QTimer, Signal

# Night versions of her poses: shown instead of these while it is night.
NIGHT_POSES = {'idle': 'night_idle', 'sleep': 'night_sleep', 'yawn': 'night_yawn', 'greet_night': 'night_goodnight',
               'wake_stretch': 'night_wake', 'bored': 'night_read', 'peek': 'night_milk'}
# The pajama change: (pose, seconds), played when the night begins and,
# after she wakes, backwards when it ends.
CHANGE_ON = (('night_change_0', .9), ('night_change_1', 1.0), ('night_change_2', 1.0), ('night_change_3', 1.0),
             ('night_settle_1', 1.1), ('night_settle_2', 1.0))
CHANGE_OFF = (('night_wake', 2.4), ('night_settle_2', .8), ('night_settle_1', 1.0), ('night_change_3', 1.0),
              ('night_change_2', 1.0), ('night_change_1', 1.0), ('night_change_0', 1.0))
PAUSE_S = 5 * 60                 # This long without input resets the sitting time.
SIT_CHOICES = (30, 45, 60, 90)
CHECK_MS = 30 * 1000


def _minutes(value, fallback):
    try:
        hours, minutes = str(value).split(':')
        return int(hours) * 60 + int(minutes)
    except (ValueError, AttributeError):
        return fallback


def in_window(prefs, now=None):
    """Inside the chosen night hours."""
    start = _minutes(prefs.get('night_start'), 23 * 60)
    end = _minutes(prefs.get('night_end'), 7 * 60)
    stamp = datetime.fromtimestamp(time.time() if now is None else now)
    minute = stamp.hour * 60 + stamp.minute
    if start == end:
        return False
    return start <= minute < end if start < end else minute >= start or minute < end


class NightMode(QObject):
    changed = Signal(bool)

    def __init__(self, panel, clock=time.time):
        super().__init__(panel)
        self.panel = panel
        self.clock = clock
        self.active = False
        self.manual = None           # True / False by hand until the window changes.
        self._scheduled = None
        self.timer = QTimer(self)
        self.timer.setInterval(CHECK_MS)
        self.timer.timeout.connect(self.poll)
        if getattr(panel, 'live', False):
            self.timer.start()
            QTimer.singleShot(0, self.poll)

    def scheduled(self, now=None):
        """Night by the clock (or Do Not Disturb, when chosen)."""
        prefs = self.panel.prefs
        if not prefs.get('night_enabled', True):
            return False
        if in_window(prefs, now):
            return True
        if prefs.get('night_with_dnd', True):
            from notifications import quiet_now
            return quiet_now(prefs, now)
        return False

    def poll(self, now=None):
        now = self.clock() if now is None else now
        scheduled = self.scheduled(now)
        if scheduled != self._scheduled:
            self._scheduled = scheduled
            self.manual = None           # The night began or ended: back to the schedule.
        self._set(self.manual if self.manual is not None else scheduled)

    def toggle(self):
        self.manual = not self.active
        self._set(self.manual)

    def _set(self, active):
        if active != self.active:
            self.active = active
            self.changed.emit(active)

    def change_steps(self, active):
        """The change to play now, or () until its pictures exist."""
        import pet_assets
        steps = CHANGE_ON if active else CHANGE_OFF
        return steps if all(pet_assets.has_own_art(pose) for pose, _s in steps) else ()

    def pose(self, pose):
        """The night version of ``pose`` while it is night and its art exists."""
        if not self.active:
            return pose
        import pet_assets
        night = NIGHT_POSES.get(pose)
        return night if night and pet_assets.has_own_art(night) else pose


class SitReminder(QObject):
    """Counts unbroken time at the computer; reminds once per stretch."""

    remind = Signal()

    def __init__(self, panel, idle=None, clock=time.monotonic):
        super().__init__(panel)
        self.panel = panel
        if idle is None:
            from pet_mood import input_idle_seconds
            idle = input_idle_seconds
        self.idle = idle
        self.clock = clock
        self.since = None            # When the current stretch at the computer began.
        self.reminded_at = None
        self.timer = QTimer(self)
        self.timer.setInterval(CHECK_MS)
        self.timer.timeout.connect(self.poll)
        if getattr(panel, 'live', False):
            self.timer.start()

    @property
    def minutes(self):
        """Minutes of sitting before a reminder; 0 = off."""
        value = self.panel.prefs.get('sit_minutes', 60)
        return value if value in SIT_CHOICES or value == 0 else 60

    def poll(self, now=None):
        now = self.clock() if now is None else now
        if self.idle() >= PAUSE_S:
            self.since, self.reminded_at = None, None    # A real pause: a new stretch next time.
            return False
        if self.since is None:
            self.since = now - min(self.idle(), PAUSE_S)
        if not self.minutes:
            return False
        busy = any(getattr(getattr(self.panel, name, None), attr, False)
                   for name, attr in (('game_mode', 'active'), ('focus_mode', 'active')))
        focus = getattr(getattr(self.panel, 'focus_mode', None), 'phase', 'idle') != 'idle'
        if busy or focus:
            return False
        due = self.since + self.minutes * 60
        if self.reminded_at is not None:
            due = self.reminded_at + self.minutes * 60   # Still sitting: again after another stretch.
        if now >= due:
            self.reminded_at = now
            self.remind.emit()
            return True
        return False

    def sitting_minutes(self, now=None):
        now = self.clock() if now is None else now
        return 0 if self.since is None else int((now - self.since) // 60)
