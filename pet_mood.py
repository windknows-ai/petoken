"""What the pet does when nothing more important is going on.

Mood is the lowest layer. DesktopPet resolves the visible pose in this
order: being dragged > a notification reaction > an interaction (head pat,
poke, long press) > the task state (typing, AI working, music) > mood.

Mood comes from the clock, whether you are at the computer and how long
since anything happened: a morning greeting, a yawn late at night, boredom,
falling asleep when you are away, and waking up and welcoming you back.
How often she does things by herself follows the clinginess setting.
Nothing spontaneous happens during Do Not Disturb or full-screen apps,
except falling asleep and waking up.
"""
from __future__ import annotations

import ctypes
import os
import random
from dataclasses import dataclass

CLINGINESS = ('quiet', 'moderate', 'clingy')
DEFAULT_CLINGINESS = 'moderate'
AWAY_WELCOME_S = 30 * 60
ACTIVE_S = 90                 # Input within this long counts as "at the computer".


@dataclass(frozen=True)
class Tuning:
    bored_after: float | None     # Seconds with no task and no interaction.
    bored_every: float
    sleep_after: float            # Seconds without any input.
    night_sleep_after: float
    yawn_every: float | None      # Late at night, while you are still up.
    greet: bool
    seek_attention: bool          # Clingy: also peeks and acts cute for attention.


TUNING = {
    'quiet': Tuning(None, 0, 20 * 60, 8 * 60, None, False, False),
    'moderate': Tuning(15 * 60, 15 * 60, 20 * 60, 6 * 60, 30 * 60, True, False),
    'clingy': Tuning(6 * 60, 8 * 60, 30 * 60, 10 * 60, 20 * 60, True, True),
}


def normalize_clinginess(value):
    return value if value in CLINGINESS else DEFAULT_CLINGINESS


def is_night(hour):
    return hour >= 23 or hour < 5


def input_idle_seconds():
    """Seconds since the last keyboard or mouse input anywhere, or 0."""
    if os.name != 'nt':
        return 0.0

    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [('cbSize', ctypes.c_uint), ('dwTime', ctypes.c_uint)]

    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(info)
    try:
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            return 0.0
        ticks = ctypes.windll.kernel32.GetTickCount() & 0xFFFFFFFF
    except (AttributeError, OSError):
        return 0.0
    return ((ticks - info.dwTime) & 0xFFFFFFFF) / 1000.0


def fullscreen_now():
    """A full-screen game, video or presentation is in front."""
    if os.name != 'nt':
        return False
    state = ctypes.c_int(0)
    try:
        if ctypes.windll.shell32.SHQueryUserNotificationState(ctypes.byref(state)) != 0:
            return False
    except (AttributeError, OSError):
        return False
    # QUNS_BUSY, QUNS_RUNNING_D3D_FULL_SCREEN, QUNS_PRESENTATION_MODE.
    return state.value in (2, 3, 4)


class Mood:
    """Feed it once a second with :meth:`update`; read :attr:`pose`."""

    def __init__(self, clinginess=DEFAULT_CLINGINESS, rng=None, greeted_day=None):
        self.clinginess = normalize_clinginess(clinginess)
        self.rng = rng or random.Random()
        self.greeted_day = greeted_day        # The last day the morning greeting played.
        self.pose = None
        self.until = 0.0
        self.queue = []
        self.sleeping = False
        self.calm_since = None                # No task and no interaction since then.
        self.next_bored = None
        self.next_yawn = None
        self.was_quiet = False
        self.longest_idle = 0.0

    @property
    def tuning(self):
        return TUNING[self.clinginess]

    def set_clinginess(self, value):
        self.clinginess = normalize_clinginess(value)
        self.next_bored = self.next_yawn = None

    def interacted(self, now):
        """You touched her: boredom starts over, and she wakes up."""
        self.calm_since = now
        self.next_bored = None
        if self.sleeping:
            self._wake(now, 0.0)

    def _play(self, pose, seconds, now):
        self.pose, self.until = pose, now + seconds

    def _wake(self, now, away):
        self.sleeping = False
        self.queue = [('wake_stretch', 2.4)]
        if away >= AWAY_WELCOME_S and self.tuning.greet:
            self.queue.append(('hug', 3.5))
        self.pose = None
        self.until = 0.0

    def update(self, now, wall, idle, busy=False, quiet=False, fullscreen=False):
        """Advance the mood.

        ``now`` is monotonic seconds, ``wall`` a local datetime, ``idle`` the
        seconds since the last input anywhere, ``busy`` whether a task state
        is showing, ``quiet`` Do Not Disturb. Returns :attr:`pose`.
        """
        tuning = self.tuning
        night = is_night(wall.hour)
        self.longest_idle = max(self.longest_idle, idle)
        if self.calm_since is None or busy:
            self.calm_since = now

        # Sleep and waking happen at every clinginess level.
        limit = tuning.night_sleep_after if (night or quiet) else tuning.sleep_after
        if not self.sleeping and idle >= limit and not busy:
            self.sleeping = True
            self.queue.clear()
        if self.sleeping:
            if idle < 5 or busy:
                self._wake(now, self.longest_idle)
            else:
                self.pose, self.until = 'sleep', now + 2
                self.was_quiet = quiet
                return self.pose
        if idle < 5:
            self.longest_idle = idle

        spontaneous = not quiet and not fullscreen and not busy
        if quiet and not self.was_quiet and night and tuning.greet and not fullscreen:
            self.queue.append(('greet_night', 3.5))
        self.was_quiet = quiet

        if self.pose and now >= self.until:
            self.pose = None
        if self.pose is None and self.queue:
            pose, seconds = self.queue.pop(0)
            self._play(pose, seconds, now)
            return self.pose
        if self.pose is not None or not spontaneous or idle > ACTIVE_S:
            return self.pose

        today = wall.date().isoformat()
        if tuning.greet and 5 <= wall.hour < 12 and self.greeted_day != today:
            self.greeted_day = today
            self._play('greet_morning', 3.5, now)
            return self.pose
        if tuning.yawn_every and night:
            if self.next_yawn is None:
                self.next_yawn = now + tuning.yawn_every * self.rng.uniform(.5, 1.0)
            elif now >= self.next_yawn:
                self.next_yawn = now + tuning.yawn_every * self.rng.uniform(.8, 1.2)
                self._play('yawn', 3.0, now)
                return self.pose
        if tuning.bored_after is not None and now - self.calm_since >= tuning.bored_after:
            if self.next_bored is None or now >= self.next_bored:
                self.next_bored = now + tuning.bored_every * self.rng.uniform(.8, 1.2)
                choices = ['bored']
                if tuning.seek_attention:
                    choices += ['peek', 'coquettish']
                self._play(self.rng.choice(choices), 6.0, now)
        return self.pose
