"""Real-time character animation for the desktop pet (pure maths, no Qt).

DesktopPet steps one Animator per timer tick and paints the Frame it
returns. Everything runs on real elapsed time, so the motion looks the same
at 30 or 60 frames per second and recovers cleanly after a stall.

Layers, combined into one Frame:
- breathing: a slow stretch around the feet that keeps the volume (a little
  narrower as it gets taller), with each pose's own rate and depth;
- springs: squash, tilt and lift are damped springs. Interactions kick them
  (poke, landing, hop) or move their target (sway while dragged), and they
  settle by themselves instead of following fixed keyframes;
- pose changes cross-fade with a small stretch;
- frame sequences play at each pose's own rate, looping or once, and blend
  into the next frame at the end of each frame;
- blinks every few seconds when the pose has an eyes-closed image;
- small floating symbols (hearts, Zzz, sparkles, a sweat drop, a question
  mark, notes) drawn by code, so a pose reads well even before its art.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

FPS_LIVELY = 60
FPS_CALM = 30
CROSSFADE_S = .14
FRAME_BLEND = .3          # Share of each frame spent blending into the next.
BLINK_S = .12
BLINK_GAP = (2.5, 6.0)
DOUBLE_BLINK = .2
MAX_DT = 1 / 20           # A stall never turns into one huge physics step.
SUBSTEP = 1 / 240
SWAY_LIMIT = 6.0          # Degrees while dragged; keeps the art inside the window.
DRAG_GAIN = .006          # Degrees per logical pixel per second of drag speed.
SQUASH_LIMIT = (-.10, .14)


class Spring:
    """A damped spring pulled toward ``target``; ``kick`` adds velocity."""

    def __init__(self, stiffness, damping, value=0.0):
        self.stiffness = stiffness
        self.damping = damping
        self.value = value
        self.velocity = 0.0
        self.target = 0.0

    def kick(self, velocity):
        self.velocity += velocity

    def step(self, dt):
        while dt > 1e-9:
            h = min(dt, SUBSTEP)
            accel = self.stiffness * (self.target - self.value) - self.damping * self.velocity
            self.velocity += accel * h
            self.value += self.velocity * h
            dt -= h

    @property
    def settled(self):
        return abs(self.value - self.target) < 2e-3 and abs(self.velocity) < 2e-2


@dataclass(frozen=True)
class Profile:
    breath_period: float = 3.6    # Seconds per breath.
    breath_depth: float = .012    # Share of the height at the deepest breath.
    sway: float = 0.0             # Side-to-side lean in degrees.
    sway_period: float = 6.0
    hop: float = 0.0              # Upward kick when the pose starts (logical px/s).
    bounce: float = 0.0           # Continuous small hops (logical px).
    bounce_period: float = .5
    fps: float = 5.0              # Frame-sequence rate.
    loop: bool = True
    particles: str = ''           # hearts, zzz, sparkles, sweat, question, notes
    # Until a pose has its own picture it borrows a V1.1 one; these make the
    # borrowed picture read differently (a steady lean, sinking lower).
    lean: float = 0.0             # Degrees, clockwise.
    sink: float = 0.0             # Logical px down.


PROFILES = {
    'idle': Profile(fps=1.2),
    'typing': Profile(breath_period=3.0),
    'codex_working': Profile(breath_period=3.2, sway=.6, fps=1.5),
    'working': Profile(breath_period=3.2, sway=.6, fps=1.5),
    'microphone': Profile(breath_period=2.8, sway=.8, sway_period=2.4),
    'music': Profile(breath_period=2.0, sway=2.2, sway_period=1.1, fps=4, particles='notes'),
    'guitar': Profile(breath_period=2.0, sway=1.6, sway_period=1.1, particles='notes'),
    'celebrate': Profile(breath_period=1.6, hop=200, bounce=3, bounce_period=.45, fps=6, particles='sparkles'),
    'sad': Profile(breath_period=4.8, breath_depth=.008),
    'wave': Profile(sway=1.4, sway_period=1.2, fps=5),
    # 2.0 companionship poses.
    'coquettish': Profile(sway=2.4, sway_period=1.4, fps=5, particles='hearts'),
    'headpat_happy': Profile(hop=120, fps=6, particles='hearts'),
    'shy': Profile(sway=1.0, sway_period=2.2, breath_period=2.6, fps=1.5, lean=-3, sink=3),
    'pout': Profile(breath_period=1.2, breath_depth=.02, fps=3.0, bounce=1.5, bounce_period=.35),
    'poked': Profile(loop=False),
    'dragged': Profile(breath_period=1.2, breath_depth=.008, fps=8, particles='sweat'),
    'landing': Profile(loop=False),
    'curious': Profile(sway=1.6, sway_period=3.0, fps=1.5, particles='question', lean=-5),
    'thinking': Profile(sway=.8, sway_period=4.0, fps=1.2, particles='question', lean=4),
    'bored': Profile(breath_period=5.0, breath_depth=.016, fps=1.2, sway=1.5, sway_period=7.0, lean=-4, sink=4),
    'yawn': Profile(breath_period=2.4, breath_depth=.045, fps=2.0, loop=False, lean=3),
    'sleep': Profile(breath_period=5.5, breath_depth=.026, fps=1.0, particles='zzz', lean=5, sink=8),
    'wake_stretch': Profile(hop=110, fps=2.0, loop=False, breath_depth=.03, breath_period=2.0),
    'hug': Profile(hop=150, fps=2.0, particles='hearts'),
    'heart': Profile(hop=170, particles='hearts'),
    'greet_morning': Profile(hop=110, sway=1.2, sway_period=1.2, fps=3.0, particles='sparkles'),
    'greet_night': Profile(breath_period=4.6, breath_depth=.018, fps=3.0, particles='zzz', lean=3),
    'surprised': Profile(hop=240),
    'thumbs_up': Profile(hop=130, particles='sparkles'),
    'cheer': Profile(bounce=2.5, bounce_period=.6, fps=2.5),
    'clap': Profile(fps=7, bounce=2, bounce_period=.42, particles='sparkles'),
    'peek': Profile(sway=1.0, sway_period=3.0, fps=1.0, lean=5, sink=10),
    'grievance': Profile(breath_period=4.4, fps=1.0, particles='sweat', lean=-3, sink=4),
    'focus_read': Profile(breath_period=4.2, fps=.4),
    'focus_tea': Profile(breath_period=4.6, breath_depth=.016, fps=1.5),
    'focus_done': Profile(hop=170, particles='sparkles'),
    'stretch_break': Profile(sway=2.0, sway_period=3.0, fps=1.2),
    'hold_card': Profile(),
    'packing': Profile(),
    'ready_go': Profile(hop=150),
    'worried': Profile(breath_period=1.6, fps=2.0, particles='sweat', sway=1.2, sway_period=.9),
    'proud': Profile(hop=140, particles='sparkles'),
}


def profile_for(state):
    return PROFILES.get(state, PROFILES['idle'])


@dataclass
class Particle:
    kind: str
    x: float          # Sprite-box fractions; y may go above the box (negative).
    y: float
    alpha: float
    size: float       # Share of the sprite side.
    angle: float = 0.0


@dataclass
class Frame:
    state: str
    index: int = 0
    next_index: int | None = None
    next_alpha: float = 0.0
    previous: str | None = None
    previous_index: int = 0
    fade: float = 1.0                 # New-pose opacity share during a cross-fade.
    scale_x: float = 1.0              # Around the feet.
    scale_y: float = 1.0
    angle: float = 0.0                # Degrees, clockwise, around ``pivot``.
    pivot: tuple = (.5, 1.0)          # Sprite-box fractions.
    lift: float = 0.0                 # Logical px upward at 100% size.
    blink: bool = False
    particles: list = field(default_factory=list)
    lively: bool = False              # Something is moving fast: tick at 60 fps.


def _cycle_random(kind, cycle, slot):
    # A stable pseudo-random value per particle life, without stored state.
    return random.Random(hash((kind, cycle, slot)) & 0xFFFFFFFF).random()


def particles(kind, t):
    """Floating symbols for ``kind`` at pose time ``t`` (seconds)."""
    out = []
    if kind in ('hearts', 'sparkles', 'notes'):
        count, life = 3, 2.4
        for slot in range(count):
            age = t + slot * life / count
            cycle, local = divmod(age, life)
            p = local / life
            jitter = _cycle_random(kind, cycle, slot)
            x = .5 + (jitter - .5) * .7 + math.sin(p * math.pi * 2 + slot) * .03
            y = .18 - p * .3
            alpha = min(1.0, p * 5) * min(1.0, (1 - p) * 2.5)
            size = (.075 if kind == 'hearts' else .065) * (.8 + .4 * jitter) * (.7 + .3 * min(1.0, p * 4))
            out.append(Particle(kind[:-1] if kind != 'notes' else 'note', x, y, alpha, size,
                                angle=math.sin(p * 6 + slot) * 12))
    elif kind == 'zzz':
        life = 3.0
        for slot in range(3):
            cycle, local = divmod(t + slot * life / 3, life)
            p = local / life
            out.append(Particle('z', .8 + p * .14, .02 - p * .22,
                                min(1.0, p * 4) * min(1.0, (1 - p) * 2), .05 + p * .05, angle=-12))
    elif kind == 'sweat':
        p = (t % 2.2) / 2.2
        out.append(Particle('sweat', .3, .12 + p * .05, min(1.0, p * 6) * min(1.0, (1 - p) * 3), .06))
    elif kind == 'question':
        out.append(Particle('question', .76, .02 + math.sin(t * 2.4) * .015,
                            min(1.0, t * 3), .1, angle=math.sin(t * 1.7) * 8))
    return out


class Animator:
    """Turns pose changes and interactions into a smooth stream of frames.

    ``frame_count(state)`` and ``has_blink(state)`` describe the artwork that
    actually exists, so missing art only removes frames or blinks, never the
    motion itself.
    """

    def __init__(self, frame_count=lambda state: 0, has_blink=lambda state: False, rng=None,
                 own_art=lambda state: True):
        self.frame_count = frame_count
        self.has_blink = has_blink
        self.own_art = own_art
        self.rng = rng or random.Random()
        self.squash = Spring(260, 13)       # Positive: shorter and wider.
        self.tilt = Spring(110, 8.5)        # Degrees.
        self.lift = Spring(170, 12)         # Logical px upward.
        self.state = 'idle'
        self.started = None
        self.previous = None
        self.previous_index = 0
        self.changed = None
        self.now = None
        self.breath = 0.0
        self.sway_phase = 0.0
        self.dragging = False
        self.grab = (.5, .3)
        self.grab_pivot = False
        self.drag_velocity = 0.0
        self.next_blink = None
        self.blink_until = float('-inf')
        self._index = 0

    # Events ---------------------------------------------------------------
    def set_state(self, state, now):
        if state == self.state:
            return
        if self.started is not None:
            self.previous, self.previous_index = self.state, self._index
            self.changed = now
            self.squash.kick(-1.1)          # A small stretch as the pose changes.
        self.state, self.started = state, now
        hop = profile_for(state).hop
        if hop:
            self.lift.kick(hop)

    def cut(self, state, now):
        """Show ``state`` at once: no cross-fade and no squash (the transformation
        has already shown the change)."""
        self.previous = self.changed = None
        self.state, self.started = state, now
        self._index = 0

    def poke(self, side=0.0):
        """A click on the body: squash, and lean away from the click side."""
        self.squash.kick(2.2)
        self.tilt.kick(-side * 45)

    def hop(self, strength=160):
        self.lift.kick(strength)
        self.squash.kick(-.8)

    def start_drag(self, grab=(.5, .3)):
        self.dragging = True
        self.grab = (min(.85, max(.15, grab[0])), min(.7, max(.05, grab[1])))
        self.grab_pivot = True
        self.drag_velocity = 0.0
        self.lift.target = 6.0
        self.squash.kick(-1.4)              # Stretched when picked up.

    def drag(self, velocity_x):
        """Horizontal drag speed in logical px/s; the body lags behind it."""
        self.drag_velocity = .6 * self.drag_velocity + .4 * velocity_x

    def end_drag(self):
        self.dragging = False
        self.drag_velocity = 0.0
        self.tilt.target = 0.0
        self.lift.target = 0.0
        self.lift.kick(-60)
        self.squash.kick(3.0)               # Landing.

    # Frames ---------------------------------------------------------------
    def _frame_index(self, t, count, profile):
        if count <= 1:
            return 0, None, 0.0
        position = t * profile.fps
        whole = int(position)
        if not profile.loop and whole >= count - 1:
            return count - 1, None, 0.0
        index = whole % count
        part = position - whole
        if part > 1 - FRAME_BLEND:
            nxt = (index + 1) % count
            return index, nxt, (part - (1 - FRAME_BLEND)) / FRAME_BLEND
        return index, None, 0.0

    def _blink(self, now, eligible):
        if self.next_blink is None:
            self.next_blink = now + self.rng.uniform(*BLINK_GAP)
        if now < self.blink_until:
            return True
        if now >= self.next_blink:
            if not eligible:
                self.next_blink = now + .3
                return False
            self.blink_until = now + BLINK_S
            if self.rng.random() < DOUBLE_BLINK:
                self.next_blink = self.blink_until + .12
            else:
                self.next_blink = now + self.rng.uniform(*BLINK_GAP)
            return True
        return False

    def step(self, now):
        if self.started is None:
            self.started = now
        dt = 0.0 if self.now is None else min(MAX_DT, max(0.0, now - self.now))
        self.now = now
        profile = profile_for(self.state)
        t = now - self.started

        if self.dragging:
            self.drag_velocity *= math.exp(-dt * 6)
            self.tilt.target = max(-SWAY_LIMIT, min(SWAY_LIMIT, self.drag_velocity * DRAG_GAIN))
        for spring in (self.squash, self.tilt, self.lift):
            spring.step(dt)
        if self.grab_pivot and not self.dragging and abs(self.tilt.value) < .3:
            self.grab_pivot = False

        self.breath += dt * 2 * math.pi / profile.breath_period
        self.sway_phase += dt * 2 * math.pi / max(.2, profile.sway_period)
        breath = (1 - math.cos(self.breath)) / 2
        squash = max(SQUASH_LIMIT[0], min(SQUASH_LIMIT[1], self.squash.value))
        scale_y = (1 + profile.breath_depth * breath) * (1 - squash)
        scale_x = (1 - profile.breath_depth * .5 * breath) * (1 + squash * .6)
        angle = self.tilt.value
        if not self.dragging:
            angle += profile.sway * math.sin(self.sway_phase)
        lift = max(-4.0, self.lift.value)
        if (profile.lean or profile.sink) and not self.own_art(self.state):
            angle += profile.lean
            lift -= profile.sink
        if profile.bounce and not self.dragging:
            lift += profile.bounce * abs(math.sin(math.pi * t / profile.bounce_period))

        count = self.frame_count(self.state)
        index, nxt, alpha = self._frame_index(t, count, profile)
        self._index = index
        fade = 1.0
        previous = None
        if self.changed is not None and self.previous is not None:
            fade = min(1.0, (now - self.changed) / CROSSFADE_S)
            if fade >= 1.0:
                self.previous = self.changed = None
            else:
                previous = self.previous
        eligible = (index == 0 and nxt is None and previous is None and not self.dragging
                    and self.has_blink(self.state))
        blink = self._blink(now, eligible) and eligible

        lively = bool(previous or self.dragging or nxt is not None or profile.bounce
                      or profile.particles or profile.sway
                      or not (self.squash.settled and self.tilt.settled and self.lift.settled))
        return Frame(
            state=self.state, index=index, next_index=nxt, next_alpha=alpha,
            previous=previous, previous_index=self.previous_index, fade=fade,
            scale_x=scale_x, scale_y=scale_y, angle=angle,
            pivot=self.grab if self.grab_pivot else (.5, 1.0), lift=lift, blink=blink,
            particles=particles(profile.particles, t) if profile.particles else [],
            lively=lively)
