"""Game mode (2.1): while you play, she stays out of the way and keeps quiet.

Game mode is on while a fullscreen game is in the foreground (game_detect),
or when the user turns it on from her right-click menu. Turning it off by hand
while a game runs keeps it off until that game ends.

While it is on:

* every task reaction, pop-up, approval card and Where-I-Left-Off card is
  silent (all of it is still recorded under Notifications; approval requests
  go back to Claude Code's terminal);
* she stays where she is and smoothly takes her game-mode size (its own
  setting, beside her usual size); her windows
  let the mouse through to the game, except while the cursor is over her or
  the info bar (HoverInput): then right-click, drag and long press work as
  usual. This needs only the cursor position, which Windows gives any
  program, even over games that run as administrator (Genshin Impact);
* the star ring stands behind her (GameHalo): one star per running task in the
  usual colours, or a violet deep-space ring when nothing runs;
* instead of the usage card, a compact display (GameUsage) shows either four
  small rings (5 h and week for each app) or a bar with the readings the user
  picks (limits, CPU, GPU, temperature, VRAM, RAM). It is shown or hidden by
  the user only, never because a task started.

The transformation animation into her second form needs the 2.1 art; until it
arrives the switch is immediate.
"""
from __future__ import annotations

import math
import time

from PySide6.QtCore import QObject, QPoint, QPointF, QRect, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (QColor, QConicalGradient, QFont, QFontMetricsF, QPainter, QPainterPath, QPen,
                           QRadialGradient)
from PySide6.QtWidgets import QApplication, QWidget

import theme
from localization import text

POLL_MS = 2000
HOLD_S = .5                  # A press this long on her (or the bar) drags it.
HOLD_SLOP = 10               # Moving further first means it was a drag in the game.
SIDES = ('right', 'left')
DISPLAYS = ('rings', 'bar', 'hidden')
RING_STYLES = ('tasks', 'space')            # Follow the tasks, or always deep space.
BAR_ITEMS = ('limits', 'cpu', 'gpu', 'gpu_temp', 'vram', 'ram')
DEFAULT_BAR_ITEMS = ('limits', 'cpu', 'gpu', 'gpu_temp')
STAR = {'codex': QColor(112, 162, 255), 'claude': QColor(240, 182, 70)}
SPACE = (QColor('#7B5CFF'), QColor('#B78CFF'), QColor('#5FB4FF'))


def raise_quietly(widget):
    """Bring one of her windows to the front without activating it.

    Qt's raise_() activates the window on Windows; done twice a second over
    a game, it took the focus from the game, so the game lost every drag and
    click and soon no longer counted as the foreground window.
    """
    try:
        if widget is None or not widget.isVisible():
            return
        import sys
        if sys.platform != 'win32':
            widget.raise_()
            return
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        user32.SetWindowPos.argtypes = (wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                        ctypes.c_int, ctypes.c_int, wintypes.UINT)
        # HWND_TOP within its band; no move, no size, NO ACTIVATE, no owner order.
        user32.SetWindowPos(int(widget.winId()), None, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010 | 0x0200)
    except (RuntimeError, OSError, AttributeError):
        pass


def ours_in_front():
    """One of Petoken's own windows (her, her menu, Settings) is the foreground window."""
    try:
        import ctypes
        import os
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return False
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return pid.value == os.getpid()
    except (AttributeError, OSError):
        return False


def set_no_activate(widget, on):
    """Clicking ``widget`` never takes the foreground (WS_EX_NOACTIVATE), so a
    game behind keeps it."""
    try:
        import sys
        if widget is None or sys.platform != 'win32':
            return
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        user32.GetWindowLongW.argtypes = (wintypes.HWND, ctypes.c_int)
        user32.SetWindowLongW.argtypes = (wintypes.HWND, ctypes.c_int, ctypes.c_long)
        hwnd = int(widget.winId())
        style = user32.GetWindowLongW(hwnd, -20)
        wanted = (style | 0x08000000) if on else (style & ~0x08000000)
        if wanted != style:
            user32.SetWindowLongW(hwnd, -20, wanted)
    except (RuntimeError, OSError, AttributeError):
        pass


def names(value):
    """A user's list of program names ("a.exe, b.exe" or a list), lowercase."""
    if isinstance(value, str):
        value = value.replace(';', ',').split(',')
    out = []
    for item in value or ():
        if isinstance(item, str) and item.strip():
            name = item.strip().lower().replace('/', '\\').rsplit('\\', 1)[-1]
            out.append(name if '.' in name else name + '.exe')
    return tuple(dict.fromkeys(out))


class ProgramList(QWidget):
    """A whitelist or blacklist of programs: pick .exe files, remove selected ones."""

    def __init__(self, language, values=(), parent=None):
        super().__init__(parent)
        from PySide6.QtWidgets import QHBoxLayout, QListWidget, QPushButton, QVBoxLayout
        self.language = language
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(4)
        self.listing = QListWidget()
        self.listing.setFixedHeight(64)
        self.listing.setMinimumWidth(220)
        column.addWidget(self.listing)
        row = QHBoxLayout()
        row.setSpacing(6)
        self.add_button = QPushButton()
        self.add_button.clicked.connect(lambda _=False: self.pick())   # Not the 'checked' flag as paths.
        self.remove_button = QPushButton()
        self.remove_button.clicked.connect(self.remove_selected)
        row.addWidget(self.add_button)
        row.addWidget(self.remove_button)
        row.addStretch(1)
        column.addLayout(row)
        self.listing.currentRowChanged.connect(lambda _: self._sync())
        for value in values or ():
            self.add(value)
        self.apply_language(language)

    def apply_language(self, language):
        self.language = language
        self.add_button.setText(text('game_list_add', language))
        self.remove_button.setText(text('game_list_remove', language))
        self.listing.setToolTip(text('game_list_tip', language))
        self._sync()

    def _sync(self):
        self.remove_button.setEnabled(self.listing.currentRow() >= 0)

    def add(self, value):
        """Add a program (a full path or just its file name); duplicates are ignored."""
        from PySide6.QtWidgets import QListWidgetItem
        name = (names([value]) or ('',))[0]
        if not name or name in self.values():
            return False
        item = QListWidgetItem(name)
        item.setData(Qt.UserRole, name)
        item.setToolTip(str(value))
        self.listing.addItem(item)
        self._sync()
        return True

    def pick(self, paths=None):
        """The file dialog (``paths`` stands in for it in tests)."""
        if paths is None:
            from PySide6.QtWidgets import QFileDialog
            paths, _ = QFileDialog.getOpenFileNames(self, text('game_list_pick', self.language), '',
                                                    text('game_list_filter', self.language))
        for path in paths or ():
            self.add(path)

    def remove_selected(self):
        row = self.listing.currentRow()
        if row >= 0:
            self.listing.takeItem(row)
        self._sync()

    def values(self):
        return [self.listing.item(i).data(Qt.UserRole) for i in range(self.listing.count())]


class GameMode(QObject):
    """On while a game is played (detected or switched on by hand)."""

    changed = Signal(bool)

    def __init__(self, panel, detector=None, clock=time.monotonic, ours=ours_in_front):
        super().__init__(panel)
        self.panel = panel
        self.clock = clock
        self.ours = ours
        if detector is None:
            from game_detect import GameDetector, foreground_info
            detector = GameDetector(scan=foreground_info)
        self.detector = detector
        self.manual = None          # True / False by hand, None: follow detection.
        self.active = False
        self.timer = QTimer(self)
        self.timer.setInterval(POLL_MS)
        self.timer.timeout.connect(self.poll)
        if getattr(panel, 'live', False):
            self.timer.start()

    @property
    def auto(self):
        return bool(self.panel.prefs.get('game_auto', True))

    def poll(self, now=None):
        now = self.clock() if now is None else now
        if self.active and self.ours():
            # Her own window or menu is in front (a click or hold on her, her menu,
            # Settings): that is not leaving the game.
            return
        playing = False
        if self.auto:
            prefs = self.panel.prefs
            playing = self.detector.poll(now, names(prefs.get('game_extra')), names(prefs.get('game_excluded')))
        if not playing and self.manual is False:
            self.manual = None      # The game ended: back to following detection.
        self._set(self.manual if self.manual is not None else playing)

    def toggle(self):
        """The right-click switch."""
        self.manual = not self.active
        if self.manual is False and not self.detector.playing:
            self.manual = None
        self._set(not self.active)

    def _set(self, active):
        if active != self.active:
            self.active = active
            self.changed.emit(active)

    def quiet(self, kind=None):
        """True while task reactions and pop-ups should stay silent."""
        return self.active

    @property
    def display(self):
        value = self.panel.prefs.get('game_display', 'rings')
        return value if value in DISPLAYS else 'rings'

    @property
    def ring_style(self):
        value = self.panel.prefs.get('game_ring', 'tasks')
        return value if value in RING_STYLES else 'tasks'

    @property
    def bar_items(self):
        items = self.panel.prefs.get('game_bar_items')
        items = [i for i in items if i in BAR_ITEMS] if isinstance(items, list) else list(DEFAULT_BAR_ITEMS)
        return items or list(DEFAULT_BAR_ITEMS)


class Placement:
    """Her size in game mode: the game-mode size on the way in, her usual size
    on the way out, changed smoothly. She stays where she is."""

    def __init__(self, pet):
        self.pet = pet

    def enter(self):
        self.pet.resize_smoothly(self.pet.mode_scale(gaming=True))

    def leave_place(self):
        self.pet.resize_smoothly(self.pet.mode_scale(gaming=False))

    def leave_input(self):
        """Clicks reach her again (after the transformation)."""
        set_clickthrough(self.pet, False)

    def leave(self):
        self.leave_place()
        self.leave_input()


def _clickless(widget):
    flags = (Qt.Tool | Qt.FramelessWindowHint | Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus
             | Qt.WindowStaysOnTopHint)
    widget.setWindowFlags(flags)
    widget.setAttribute(Qt.WA_TranslucentBackground)
    widget.setAttribute(Qt.WA_ShowWithoutActivating)
    widget.setAttribute(Qt.WA_TransparentForMouseEvents)


class GameHalo(QWidget):
    """The star ring standing behind her (a tilted circle like a halo).

    One star per running task in its app's colour; with no tasks (or when the
    user prefers it) a violet deep-space ring that breathes and turns evenly.
    """

    FPS = 60

    def __init__(self, pet):
        super().__init__(None)
        self.pet = pet
        _clickless(self)
        self.stars = []             # Provider ids, one per running task.
        self.space = True
        self.intro = 1.0            # 0 → 1 while the ring flies in behind her (transform.py).
        self.hide_stars = False     # While they are flying in or out (StarFlight).
        self.flare = 0.0            # Extra brightness for the MVP moment.
        self.angle = 0.0
        self.t = 0.0
        self._last = None
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.setInterval(1000 // self.FPS)
        self.timer.timeout.connect(self._tick)
        import random
        rng = random.Random(7)
        # (start angle, length, radius factor, width, colour position, speed, alpha)
        self.wisps = [(rng.uniform(0, 360), rng.uniform(25, 95), 1 + rng.gauss(0, .045),
                       rng.uniform(.6, 2.6), rng.random(), rng.choice((1, 1, 1.35, .8, -.5)),
                       rng.uniform(.35, 1)) for _ in range(70)]

    def set_stars(self, providers, space):
        providers = list(providers)
        if (providers, space) != (self.stars, self.space):
            self.stars, self.space = providers, space
            self.update()

    ROOM = 1.75                 # Window side / her height: room for the ring flying in.

    def follow(self):
        pet = self.pet
        side = round(pet.height() * self.ROOM)
        if self.size() != QSize(side, side):
            self.setFixedSize(side, side)
        # Centred on her upper body, so the ring frames her from behind.
        x = pet.x() + (pet.width() - side) // 2
        y = pet.y() + round(pet.height() * .58) - side // 2 + round(side * .42 / self.ROOM * .3)
        if self.pos() != QPoint(x, y):
            self.move(x, y)

    def showEvent(self, event):
        self._last = None
        self.timer.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)

    def _tick(self):
        now = time.monotonic()
        dt = 0.0 if self._last is None else min(.1, now - self._last)
        self._last = now
        self.t += dt
        self.angle = (self.angle + dt * 18) % 360       # Even rotation: 20 s a turn.
        self.follow()
        self.update()
        # Her windows keep one order, together (as the usual ring does): the
        # ring at the back, her, the transformation, then her displays; all
        # of them stay above other windows like her usual ring. Never over an open menu.
        if QApplication.activePopupWidget() is None and self.frames_since_raise() >= 30:
            self.restack()

    def restack(self):
        pet = self.pet
        order = [self, pet, getattr(pet, 'transform_stage', None), getattr(pet, 'game_usage', None),
                 getattr(pet, 'focus_tag', None)]
        for window in order:
            raise_quietly(window)

    def frames_since_raise(self):
        self._raise_count = getattr(self, '_raise_count', 0) + 1
        if self._raise_count >= 30:                     # About twice a second is plenty.
            self._raise_count = 0
            return 30
        return self._raise_count

    def _ellipse(self):
        """The ring, as a circle standing behind her upper body."""
        w, h = self.width(), self.height()
        r = min(w, h) * .42 / self.ROOM          # The ring is sized by her, not by the window.
        return QRectF(w / 2 - r, h / 2 - r * .3 - r, 2 * r, 2 * r)

    def _transform(self):
        """Tilt (a halo seen a little from the side) and, while flying in, wider and turning."""
        from PySide6.QtGui import QTransform
        intro = max(0.0, min(1.0, self.intro))
        centre = self._ellipse().center()
        t = QTransform()
        t.translate(centre.x(), centre.y())
        t.rotate(-14 - (1 - intro) * 200)
        grow = 1 + (1 - intro) * .6
        t.scale(grow, grow * .9)
        t.translate(-centre.x(), -centre.y())
        return t

    def _star_angle(self, index, count):
        return math.radians(self.angle * 1.4 + index * 360 / max(1, count) - 90)

    def star_points(self, final=True):
        """(provider, global point) of each task star: where it sits once the
        ring is in place (``final``), or as drawn right now."""
        ring = self._ellipse()
        centre = ring.center()
        if final:
            intro, self.intro = self.intro, 1.0
            transform = self._transform()
            self.intro = intro
        else:
            transform = self._transform()
        out = []
        count = len(self.stars)
        for index, provider in enumerate(self.stars):
            a = self._star_angle(index, count)
            local = QPointF(centre.x() + ring.width() / 2 * math.cos(a), centre.y() + ring.height() / 2 * math.sin(a))
            out.append((provider, QPointF(self.mapToGlobal(transform.map(local).toPoint()))))
        return out

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        ring = self._ellipse()
        centre = ring.center()
        breath = .5 + .5 * math.sin(self.t * 2 * math.pi / 4.0)     # 4 s breathing.
        intro = max(0.0, min(1.0, self.intro))
        breath = min(1.0, breath + self.flare)
        p.setTransform(self._transform())
        if intro > 0:
            p.setOpacity(intro)
            self._paint_space(p, ring, centre, breath)       # The same deep-space ring with or without tasks.
        if not self.hide_stars:
            p.setOpacity(1)                                  # Stars ride the ring even as it flies in.
            self._paint_stars(p, ring, centre, breath)

    @staticmethod
    def _mix(position):
        """Violet → lilac → ice blue → violet along 0..1."""
        stops = (SPACE[0], SPACE[1], SPACE[2], SPACE[0])
        x = (position % 1) * 3
        i = min(2, int(x))
        f = x - i
        a, b = stops[i], stops[i + 1]
        return QColor(round(a.red() + (b.red() - a.red()) * f), round(a.green() + (b.green() - a.green()) * f),
                      round(a.blue() + (b.blue() - a.blue()) * f))

    def _paint_space(self, p, ring, centre, breath):
        """A deep-space ring: a violet haze, swirling wisps, a warm core of light
        behind her, and twinkling specks. It breathes and turns evenly."""
        r = ring.width() / 2
        p.setPen(Qt.NoPen)
        # Warm light in the middle (mostly behind her; it glows around her).
        core = QRadialGradient(centre, r * .55)
        core.setColorAt(0, QColor(255, 236, 190, int(110 + 70 * breath)))
        core.setColorAt(.35, QColor(190, 150, 255, int(60 + 30 * breath)))
        core.setColorAt(1, QColor(0, 0, 0, 0))
        p.setBrush(core)
        p.drawEllipse(centre, r * .55, r * .55)
        # The haze: a thick soft band.
        haze = QRadialGradient(centre, r * 1.25)
        for stop, alpha in ((.62, 0), (.8, 70 + 40 * breath), (.9, 95 + 50 * breath), (1, 0)):
            c = QColor(SPACE[0])
            c.setAlpha(int(alpha))
            haze.setColorAt(stop, c)
        p.setBrush(haze)
        p.drawEllipse(centre, r * 1.25, r * 1.25)
        # Wisps turning at their own speeds.
        p.setBrush(Qt.NoBrush)
        for start, length, factor, width, tone, speed, alpha in self.wisps:
            c = self._mix(tone + self.t * .02)
            c.setAlpha(int(255 * alpha * (.55 + .45 * breath)))
            p.setPen(QPen(c, width, Qt.SolidLine, Qt.RoundCap))
            rr = r * factor
            box = QRectF(centre.x() - rr, centre.y() - rr, 2 * rr, 2 * rr)
            p.drawArc(box, int((start + self.angle * speed) * 16), int(length * 16))
        # A bright thin edge.
        edge = QConicalGradient(centre, self.angle)
        for stop in (0, .25, .5, .75, 1):
            c = self._mix(stop)
            c.setAlpha(230)
            edge.setColorAt(stop, c.lighter(130))
        p.setPen(QPen(edge, 1.6))
        p.drawEllipse(ring)
        # Specks of starlight.
        p.setPen(Qt.NoPen)
        for n in range(36):
            a = math.radians(self.angle * .6 + n * 10 + 9 * math.sin(n * 1.7))
            k = 1 + .14 * math.sin(n * 3.1)
            twinkle = .5 + .5 * math.sin(self.t * 3 + n)
            p.setBrush(QColor(255, 255, 255, int(70 + 170 * twinkle)))
            size = .7 + 1.5 * twinkle
            p.drawEllipse(QPointF(centre.x() + r * k * math.cos(a), centre.y() + r * k * math.sin(a)), size, size)

    def _paint_stars(self, p, ring, centre, breath):
        count = len(self.stars)
        for index, provider in enumerate(self.stars):
            a = self._star_angle(index, count)
            rx, ry = ring.width() / 2, ring.height() / 2
            pos = QPointF(centre.x() + rx * math.cos(a), centre.y() + ry * math.sin(a))
            paint_star(p, pos, QColor(STAR.get(provider, theme.ICE)), breath, self.t + index, 1.8)
            # A short comet tail behind it along the ring.
            p.setPen(Qt.NoPen)
            for k in range(1, 9):
                back = a - math.radians(k * 2.6)
                tail = QColor(STAR.get(provider, theme.ICE))
                tail.setAlpha(int(200 * (1 - k / 9) * (.7 + .3 * breath)))
                p.setBrush(tail)
                size = 3.4 * (1 - k / 10)
                p.drawEllipse(QPointF(centre.x() + rx * math.cos(back), centre.y() + ry * math.sin(back)), size, size)


def paint_star(p, pos, color, breath=1.0, phase=0.0, scale=1.0):
    """One task star: a coloured glow, a four-pointed white sparkle with a slow
    twinkle, and a coloured heart (the game ring and the flights share it)."""
    glow = QRadialGradient(pos, 18 * scale)
    soft = QColor(color)
    soft.setAlpha(int(190 + 60 * breath))
    glow.setColorAt(0, soft)
    soft.setAlpha(90)
    glow.setColorAt(.45, soft)
    glow.setColorAt(1, QColor(0, 0, 0, 0))
    p.setPen(Qt.NoPen)
    p.setBrush(glow)
    p.drawEllipse(pos, 18 * scale, 18 * scale)
    twinkle = .85 + .15 * math.sin(phase * 2.3)
    r = 8.5 * scale * twinkle
    path = QPainterPath()
    path.moveTo(pos.x(), pos.y() - r)
    for dx, dy in ((r, 0), (0, r), (-r, 0), (0, -r)):
        path.quadTo(pos.x(), pos.y(), pos.x() + dx, pos.y() + dy)
    p.setBrush(QColor(255, 255, 255, 240))
    p.drawPath(path)
    p.setBrush(color.lighter(130))
    p.drawEllipse(pos, 2.6 * scale, 2.6 * scale)


class StarFlight(QWidget):
    """Task stars flying between the usual star ring and the ring behind her.

    ``starts`` and ``ends`` are callables giving [(provider, global point)].
    The starts are read once when the flight begins (after ``delay`` seconds),
    the ends every frame, so the target ring may keep turning or be dragged.
    """

    DURATION = 1.3

    def __init__(self, starts, ends, on_start=None, on_frame=None, on_done=None, delay=0.0):
        super().__init__(None)
        _clickless(self)
        self.starts, self.ends = starts, ends
        self.on_start, self.on_frame, self.on_done = on_start, on_frame, on_done
        self.delay = max(0.0, delay)
        self.t = -self.delay
        self._last = None
        self._first = None
        self._box = None
        self.done = False
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.setInterval(1000 // 60)
        self.timer.timeout.connect(self._tick)

    def start(self):
        self.timer.start()
        if self.delay <= 0:
            self._begin()

    def _begin(self):
        self._first = list(self.starts())
        if self.on_start is not None:
            self.on_start()
        self._grow()
        self.show()
        raise_quietly(self)

    def _grow(self):
        points = [pt for _, pt in (self._first or [])] + [pt for _, pt in self.ends()]
        if not points:
            return
        xs, ys = [pt.x() for pt in points], [pt.y() for pt in points]
        need = QRect(int(min(xs)) - 50, int(min(ys)) - 130, int(max(xs) - min(xs)) + 100,
                     int(max(ys) - min(ys)) + 180)
        box = need if self._box is None else self._box.united(need)
        if box != self._box:
            self._box = box
            self.setGeometry(box)

    def _tick(self):
        now = time.monotonic()
        dt = 0.0 if self._last is None else min(.05, now - self._last)
        self._last = now
        before = self.t
        self.t += dt
        if self._first is None:
            if self.t >= 0:
                self._begin()
            return
        f = max(0.0, min(1.0, self.t / self.DURATION))
        if self.on_frame is not None:
            self.on_frame(f)
        self._grow()
        self.update()
        if f >= 1.0:
            self.finish()

    def finish(self):
        """End now (also when a new switch interrupts it); runs on_done once."""
        if self.done:
            return
        self.done = True
        self.timer.stop()
        if self._first is None and self.on_start is not None:
            self.on_start()
        if self.on_frame is not None:
            self.on_frame(1.0)
        self.hide()
        if self.on_done is not None:
            self.on_done()
        self.deleteLater()

    def paintEvent(self, event):
        if not self._first:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        f = max(0.0, min(1.0, self.t / self.DURATION))
        e = f * f * (3 - 2 * f)
        ends = list(self.ends())
        origin = QPointF(self.pos())
        for index, (provider, start) in enumerate(self._first):
            if index >= len(ends):
                break                       # No place for it on the other ring.
            end = ends[index][1]
            color = QColor(STAR.get(provider, theme.ICE))
            bend = 70 * (1 if index % 2 else .7)
            for k in range(6, -1, -1):      # The trail first, then the star.
                g = max(0.0, e - k * .035)
                x = start.x() + (end.x() - start.x()) * g
                y = start.y() + (end.y() - start.y()) * g - bend * math.sin(math.pi * g)
                point = QPointF(x, y) - origin
                if k:
                    c = QColor(color)
                    c.setAlpha(int(140 * (1 - k / 7)))
                    p.setPen(Qt.NoPen)
                    p.setBrush(c)
                    p.drawEllipse(point, 3.2 * (1 - k / 8), 3.2 * (1 - k / 8))
                else:
                    paint_star(p, point, color, 1.0, self.t * 3 + index, 1.0 + .8 * e)


class GameUsage(QWidget):
    """The compact usage display while gaming: four small rings, or a bar."""

    RING_D = 30
    RING_W = 3.5

    def __init__(self, pet, stats_wanted=None):
        super().__init__(None)
        self.pet = pet
        _clickless(self)
        self.style_name = 'rings'
        self.cells = []             # (provider, kind, remaining) for the rings.
        self.items = []             # (label, value text, warn) for the bar.
        self.sampler = None

    def _font(self, size, bold=False):
        font = QFont('Microsoft YaHei UI')
        font.setPixelSize(size)
        if bold:
            font.setWeight(QFont.DemiBold)
        return font

    def set_content(self, style_name, sections, stats, items, language):
        from system_stats import LABELS, format_stat
        self.style_name = style_name
        cells, bar = [], []
        for section in sections:
            rows = {row['kind']: row for row in section.get('rows') or []}
            for kind in ('five', 'week'):
                row = rows.get(kind) or {}
                if not row.get('na'):     # A window the plan lacks takes no space here.
                    cells.append((section['provider'], kind, row.get('remaining')))
        if style_name == 'bar':
            labels = LABELS.get(language, LABELS['en'])
            for item in items:
                if item == 'limits':
                    for section in sections:
                        rows = {row['kind']: row for row in section.get('rows') or []}
                        parts = []
                        for kind, key in (('five', 'game_bar_5h'), ('week', 'game_bar_week')):
                            row = rows.get(kind) or {}
                            if row.get('na'):
                                continue
                            left = row.get('remaining')
                            parts.append(f"{text(key, language)} {'—' if left is None else f'{left:.0f}%'}")
                        if parts:
                            lows = [(rows.get(k) or {}).get('remaining') for k in ('five', 'week')]
                            warn = any(v is not None and v < 20 for v in lows)
                            bar.append((section['name'], '  '.join(parts), warn))
                elif item == 'vram':
                    bar.append((labels['vram'], format_stat('vram', stats or {}, language), False))
                else:
                    value = (stats or {}).get(item)
                    hot = (item == 'gpu_temp' and isinstance(value, (int, float)) and value >= 85)
                    bar.append((labels.get(item, item), format_stat(item, value, language), hot))
        changed = (cells, bar) != (self.cells, self.items)
        self.cells, self.items = cells, bar
        self._resize()
        if changed:
            self.update()

    def _resize(self):
        if self.style_name == 'rings':
            count = max(1, len(self.cells))
            size = QSize(self.RING_D + 36, count * (self.RING_D + 18) + 8)
        else:
            metrics = QFontMetricsF(self._font(12, True))
            width = sum(metrics.horizontalAdvance(f'{label} {value}') + 24 for label, value, _ in self.items)
            size = QSize(int(max(80, width + 14)), 30)
        if self.size() != size:
            self.setFixedSize(size)
        self.follow()

    def follow(self):
        pet = self.pet
        prefs = pet.panel.prefs
        if self.style_name == 'rings':
            # Beside her (left or right, the user's choice), at shoulder height.
            # Just outside her picture (her hair reaches its edges), not over her.
            import pet_geometry
            sx, sy, sw, sh = pet_geometry.scaled_sprite_rect(pet.pet_scale)
            if prefs.get('game_rings_side') == 'left':
                x = pet.x() + sx - self.width() - pet._px(4)
            else:
                x = pet.x() + sx + sw + pet._px(4)
            y = pet.y() + sy + sh - self.height() - pet._px(10)
        else:
            spot = prefs.get('game_bar_pos')
            if isinstance(spot, list) and len(spot) == 2 and all(isinstance(v, int) for v in spot):
                x, y = spot          # Dragged somewhere: it stays there.
                screen = (QApplication.screenAt(QPoint(x, y)) or pet.screen()
                          or QApplication.primaryScreen()).availableGeometry()
                x = max(screen.left(), min(x, screen.right() - self.width() + 1))
                y = max(screen.top(), min(y, screen.bottom() - self.height() + 1))
                if self.pos() != QPoint(x, y):
                    self.move(x, y)
                return
            x = pet.x() + (pet.width() - self.width()) // 2
            y = pet.y() + pet._px(56) - self.height()
        screen = (pet.screen() or QApplication.primaryScreen()).availableGeometry()
        x = max(screen.left(), min(x, screen.right() - self.width() + 1))
        y = max(screen.top(), min(y, screen.bottom() - self.height() + 1))
        if self.pos() != QPoint(x, y):
            self.move(x, y)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.style_name == 'bar':
            self._grab = event.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, event):
        grab = getattr(self, '_grab', None)
        if grab is not None and event.buttons() & Qt.LeftButton:
            target = event.globalPosition().toPoint() - grab
            self.pet.panel.prefs['game_bar_pos'] = [target.x(), target.y()]
            self.follow()                   # Kept on a screen, as later.

    def mouseReleaseEvent(self, event):
        if getattr(self, '_grab', None) is not None:
            self._grab = None
            try:
                self.pet.panel.persist()
            except Exception:
                pass

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        card = QColor(theme.CARD)
        card.setAlpha(225)
        p.setPen(QPen(QColor(theme.BORDER), 1))
        p.setBrush(card)
        p.drawRoundedRect(QRectF(.5, .5, self.width() - 1, self.height() - 1), 10, 10)
        if self.style_name == 'rings':
            self._paint_rings(p)
        else:
            self._paint_bar(p)

    def _paint_rings(self, p):
        from usage_overlay import RING, RING_CRITICAL, RING_LOW, CRITICAL_AT, LOW_AT
        language = self.pet.panel.prefs.get('language')
        d, stroke = self.RING_D, self.RING_W
        x = (self.width() - d) / 2
        y = 6
        for provider, kind, left in self.cells:
            ring = QRectF(x + stroke / 2, y + stroke / 2, d - stroke, d - stroke)
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor(theme.TRACK), stroke, Qt.SolidLine, Qt.RoundCap))
            p.drawEllipse(ring)
            if left is not None and left > 0:
                color = RING_CRITICAL if left < CRITICAL_AT else RING_LOW if left < LOW_AT else RING[kind]
                p.setPen(QPen(color, stroke, Qt.SolidLine, Qt.RoundCap))
                p.drawArc(ring, 90 * 16, int(-360 * 16 * min(100.0, left) / 100))
            p.setFont(self._font(11, True))
            p.setPen(QColor(RING_CRITICAL if left is not None and left < CRITICAL_AT else theme.INK))
            p.drawText(ring, Qt.AlignCenter, '—' if left is None else f'{left:.0f}')
            # Under the ring: the app's dot and which window it is.
            dot = STAR.get(provider, QColor(theme.ICE))
            p.setPen(Qt.NoPen)
            p.setBrush(dot)
            label = text('game_bar_5h' if kind == 'five' else 'game_bar_week', language)
            p.setFont(self._font(10))
            width = QFontMetricsF(p.font()).horizontalAdvance(label)
            lx = (self.width() - width - 8) / 2
            p.drawEllipse(QPointF(lx + 3, y + d + 9), 3, 3)
            p.setPen(QColor(theme.INK))
            p.drawText(QRectF(lx + 9, y + d + 1, width + 4, 16), Qt.AlignLeft | Qt.AlignVCenter, label)
            y += d + 18

    def _paint_bar(self, p):
        from usage_overlay import RING_CRITICAL
        x = 12.0
        for index, (label, value, warn) in enumerate(self.items):
            if index:
                p.setPen(QPen(QColor(theme.DIVIDER), 1))
                p.drawLine(QPointF(x - 12, 8), QPointF(x - 12, self.height() - 8))
            p.setFont(self._font(12))
            p.setPen(QColor(theme.MUTED))
            lw = QFontMetricsF(p.font()).horizontalAdvance(label + ' ')
            p.drawText(QRectF(x, 0, lw + 2, self.height()), Qt.AlignLeft | Qt.AlignVCenter, label + ' ')
            x += lw
            p.setFont(self._font(12, True))
            p.setPen(QColor(RING_CRITICAL if warn else theme.INK))
            vw = QFontMetricsF(p.font()).horizontalAdvance(value)
            p.drawText(QRectF(x, 0, vw + 2, self.height()), Qt.AlignLeft | Qt.AlignVCenter, value)
            x += vw + 24


def set_clickthrough(widget, through):
    """Let the mouse pass through ``widget`` (to the game below) or take it.

    Changed on the native window (WS_EX_TRANSPARENT), not with Qt's window
    flag, which would recreate the window each time.
    """
    try:
        if widget is None:
            return
        widget.setAttribute(Qt.WA_TransparentForMouseEvents, bool(through))
        import sys
        if sys.platform != 'win32':
            return
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        user32.GetWindowLongW.argtypes = (wintypes.HWND, ctypes.c_int)
        user32.SetWindowLongW.argtypes = (wintypes.HWND, ctypes.c_int, ctypes.c_long)
        hwnd = int(widget.winId())
        style = user32.GetWindowLongW(hwnd, -20)                     # GWL_EXSTYLE
        wanted = (style | 0x20 | 0x80000) if through else (style & ~0x20)   # TRANSPARENT (+LAYERED)
        if wanted != style:
            user32.SetWindowLongW(hwnd, -20, wanted)
    except (RuntimeError, OSError, AttributeError):
        pass


class HoverInput(QObject):
    """In game mode her windows let the mouse through to the game, except
    while the cursor is over her or the info bar: then they take it, so her
    right-click menu, dragging her and long presses work as outside games.

    Only the cursor position is watched. Windows lets any program read it,
    unlike the mouse buttons, which it hides from ordinary programs while a
    game that runs as administrator (Genshin Impact) has the focus.
    """

    def __init__(self, pet, cursor=None):
        super().__init__(pet)
        from PySide6.QtGui import QCursor
        self.pet = pet
        self.cursor = cursor or QCursor.pos
        self.taking = {}                    # widget -> True while it takes the mouse.
        self.timer = QTimer(self)
        self.timer.setInterval(30)
        self.timer.timeout.connect(self.tick)

    def start(self):
        self.taking = {}
        for widget in self._targets():
            self._set(widget, False)
        set_no_activate(self.pet, True)     # Clicking her never takes the game's focus.
        self.timer.start()

    def stop(self):
        self.timer.stop()
        set_no_activate(self.pet, False)
        for widget in list(self.taking):
            try:
                set_clickthrough(widget, widget is not self.pet)    # She takes the mouse again; the rest never do.
            except RuntimeError:
                pass
        self.taking = {}

    def _targets(self):
        pet = self.pet
        out = [pet]
        usage = getattr(pet, 'game_usage', None)
        if usage is not None and usage.isVisible() and usage.style_name == 'bar':
            out.append(usage)
        return out

    def _box(self, widget):
        if widget is self.pet:
            pet = self.pet
            # Her picture, not the empty room around it.
            return pet.frameGeometry().adjusted(pet._px(14), pet._px(64), -pet._px(14), 0)
        return widget.frameGeometry()

    def _set(self, widget, take):
        if self.taking.get(widget) != take:
            self.taking[widget] = take
            set_clickthrough(widget, not take)

    def tick(self):
        point = self.cursor()
        busy = QApplication.mouseButtons() != Qt.NoButton or getattr(self.pet, 'dragging', False)
        for widget in self._targets():
            if busy and self.taking.get(widget):
                continue                    # Mid-press or mid-drag: keep it.
            self._set(widget, self._box(widget).contains(point))
        if getattr(self.pet, 'dragging', False):
            for extra in (getattr(self.pet, 'game_halo', None), getattr(self.pet, 'game_usage', None)):
                if extra is not None and extra.isVisible():
                    extra.follow()
