"""Game mode (2.1): while you play, she stays out of the way and keeps quiet.

Game mode is on while a fullscreen game is in the foreground (game_detect),
or when the user turns it on from her right-click menu. Turning it off by hand
while a game runs keeps it off until that game ends.

While it is on:

* every task reaction, pop-up, approval card and Where-I-Left-Off card is
  silent (all of it is still recorded under Notifications; approval requests
  go back to Claude Code's terminal);
* on the game's screen she shrinks into the bottom-right corner and lets the
  mouse through, so she never blocks the game. A click reaches the game; a
  long press (half a second) on her, or on the info bar, drags it (LongPressDrag);
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
CORNER_SCALE = 70            # % of her usual size while sharing the game's screen.
CORNER_MARGIN = 12
DISPLAYS = ('rings', 'bar', 'hidden')
RING_STYLES = ('tasks', 'space')            # Follow the tasks, or always deep space.
BAR_ITEMS = ('limits', 'cpu', 'gpu', 'gpu_temp', 'vram', 'ram')
DEFAULT_BAR_ITEMS = ('limits', 'cpu', 'gpu', 'gpu_temp')
STAR = {'codex': QColor(112, 162, 255), 'claude': QColor(240, 182, 70)}
SPACE = (QColor('#7B5CFF'), QColor('#B78CFF'), QColor('#5FB4FF'))


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


class GameMode(QObject):
    """On while a game is played (detected or switched on by hand)."""

    changed = Signal(bool)

    def __init__(self, panel, detector=None, clock=time.monotonic):
        super().__init__(panel)
        self.panel = panel
        self.clock = clock
        if detector is None:
            from game_detect import GameDetector, foreground_info
            detector = GameDetector(scan=self._scan_with(foreground_info))
        self.detector = detector
        self.manual = None          # True / False by hand, None: follow detection.
        self.active = False
        self.monitor = None         # (l, t, r, b) of the game's screen, when known.
        self.timer = QTimer(self)
        self.timer.setInterval(POLL_MS)
        self.timer.timeout.connect(self.poll)
        if getattr(panel, 'live', False):
            self.timer.start()

    def _scan_with(self, scan):
        def remembered():
            info = scan()
            if info and info.get('fullscreen'):
                self.monitor = info.get('monitor')
            return info
        return remembered

    @property
    def auto(self):
        return bool(self.panel.prefs.get('game_auto', True))

    def poll(self, now=None):
        now = self.clock() if now is None else now
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
        if self.manual:
            self.monitor = None     # Switched on by hand: no game screen known.
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
    """Her place and size before game mode, to put her back afterwards."""

    def __init__(self, pet):
        self.pet = pet
        self.saved = None

    def enter(self, monitor):
        pet = self.pet
        screen = (pet.screen() or QApplication.primaryScreen())
        area = screen.availableGeometry()
        if monitor is not None:
            l, t, r, b = monitor
            shares = area.intersects(QRect(l, t, r - l, b - t))
        else:
            shares = False
        corner = bool(pet.panel.prefs.get('game_corner', True)) and shares
        self.saved = (pet.pos(), pet.pet_scale, corner)
        pet.setWindowFlag(Qt.WindowTransparentForInput, True)
        if corner:
            pet.apply_pet_scale(max(50, round(pet.pet_scale * CORNER_SCALE / 100)))
            pet.move_clamped(QPoint(area.right() - pet.width() - CORNER_MARGIN,
                                    area.bottom() - pet.height() - CORNER_MARGIN))
        pet.show()

    def leave(self):
        pet = self.pet
        pet.setWindowFlag(Qt.WindowTransparentForInput, False)
        if self.saved is not None:
            position, scale, corner = self.saved
            if corner:
                pet.apply_pet_scale(scale)
                pet.move_clamped(position)
        self.saved = None
        pet.show()


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

    def follow(self):
        pet = self.pet
        side = round(pet.height() * 1.05)
        if self.size() != QSize(side, side):
            self.setFixedSize(side, side)
        # Centred on her upper body, so the ring frames her from behind.
        x = pet.x() + (pet.width() - side) // 2
        y = pet.y() + round(pet.height() * .58) - side // 2
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
        if self.pet.isVisible():
            self.pet.raise_()                           # She stays in front of the ring.

    def _ellipse(self):
        """The ring, as a circle standing behind her upper body."""
        w, h = self.width(), self.height()
        r = min(w, h) * .4
        return QRectF(w / 2 - r, h * .44 - r, 2 * r, 2 * r)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        ring = self._ellipse()
        centre = ring.center()
        breath = .5 + .5 * math.sin(self.t * 2 * math.pi / 4.0)     # 4 s breathing.
        # A slight tilt, like a halo seen a little from the side.
        p.translate(centre)
        p.rotate(-14)
        p.scale(1, .9)
        p.translate(-centre)
        if self.space:
            self._paint_space(p, ring, centre, breath)
        else:
            self._paint_plain(p, ring, centre, breath)
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

    def _paint_plain(self, p, ring, centre, breath):
        """With tasks: a calm violet band, so the coloured stars stand out."""
        r = ring.width() / 2
        haze = QRadialGradient(centre, r * 1.15)
        for stop, alpha in ((.75, 0), (.87, 45 + 25 * breath), (1, 0)):
            c = QColor(theme.VIOLET)
            c.setAlpha(int(alpha))
            haze.setColorAt(stop, c)
        p.setPen(Qt.NoPen)
        p.setBrush(haze)
        p.drawEllipse(centre, r * 1.15, r * 1.15)
        c = QColor('#B8A8FF')
        c.setAlpha(170)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(c, 1.6))
        p.drawEllipse(ring)

    def _paint_stars(self, p, ring, centre, breath):
        count = len(self.stars)
        for index, provider in enumerate(self.stars):
            a = math.radians(self.angle * 1.4 + index * 360 / max(1, count) - 90)
            pos = QPointF(centre.x() + ring.width() / 2 * math.cos(a), centre.y() + ring.height() / 2 * math.sin(a))
            color = QColor(STAR.get(provider, theme.ICE))
            halo = QRadialGradient(pos, 14)
            soft = QColor(color)
            soft.setAlpha(int(120 + 60 * breath))
            halo.setColorAt(0, soft)
            halo.setColorAt(1, QColor(0, 0, 0, 0))
            p.setPen(Qt.NoPen)
            p.setBrush(halo)
            p.drawEllipse(pos, 14, 14)
            path = QPainterPath()
            r = 7
            path.moveTo(pos.x(), pos.y() - r)
            for dx, dy in ((r, 0), (0, r), (-r, 0), (0, -r)):
                path.quadTo(pos.x(), pos.y(), pos.x() + dx, pos.y() + dy)
            p.setBrush(QColor(255, 255, 255))
            p.drawPath(path)
            p.setBrush(color)
            p.drawEllipse(pos, 2.2, 2.2)


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
            if prefs.get('game_rings_side') == 'left':
                x = pet.x() + pet._px(18) - self.width()
            else:
                x = pet.x() + pet.width() - pet._px(18)
            y = pet.y() + pet.height() - self.height() - pet._px(20)
        else:
            spot = prefs.get('game_bar_pos')
            if isinstance(spot, list) and len(spot) == 2 and all(isinstance(v, int) for v in spot):
                x, y = spot          # Dragged somewhere: it stays there.
                screen = (QApplication.screenAt(QPoint(x, y)) or QApplication.primaryScreen()).availableGeometry()
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


def _left_button_down():
    """The left mouse button right now, wherever the cursor is (Windows)."""
    try:
        import ctypes
        user32 = ctypes.windll.user32
        button = 0x02 if user32.GetSystemMetrics(23) else 0x01     # SM_SWAPBUTTON.
        return bool(user32.GetAsyncKeyState(button) & 0x8000)
    except Exception:
        return False


class LongPressDrag(QObject):
    """Long press to drag while she lets the mouse through.

    In game mode her window (and the bar) ignore the mouse, so a click goes
    to the game. This watches the button instead: held for HOLD_S on her or
    on the bar without moving, the window follows the cursor until release.
    """

    def __init__(self, pet, button=_left_button_down, cursor=None, clock=time.monotonic):
        super().__init__(pet)
        from PySide6.QtGui import QCursor
        self.pet = pet
        self.button = button
        self.cursor = cursor or QCursor.pos
        self.clock = clock
        self.press = None           # (target, start point, time, offset)
        self.dragging = None
        self._was_down = False
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self.tick)

    def start(self):
        self._was_down = True       # Ignore a press already held when game mode began.
        self.press = self.dragging = None
        self.timer.start()

    def stop(self):
        if self.dragging is not None:
            self._release()
        self.timer.stop()

    def _targets(self):
        pet = self.pet
        out = []
        usage = getattr(pet, 'game_usage', None)
        if usage is not None and usage.isVisible() and usage.style_name == 'bar':
            out.append(('bar', usage, usage.frameGeometry()))
        # Her sprite, not the empty space above her head.
        box = pet.frameGeometry().adjusted(pet._px(14), pet._px(64), -pet._px(14), 0)
        out.append(('pet', pet, box))
        return out

    def tick(self):
        down = self.button()
        point = self.cursor()
        now = self.clock()
        if not down:
            if self.dragging is not None:
                self._release()
            self.press = None
            self._was_down = False
            return
        if not self._was_down:                      # A fresh press.
            self._was_down = True
            for name, widget, box in self._targets():
                if box.contains(point):
                    self.press = (name, widget, point, now, point - widget.pos())
                    break
            return
        if self.press is None:
            return
        name, widget, start, at, offset = self.press
        if self.dragging is None:
            if (point - start).manhattanLength() > HOLD_SLOP:
                self.press = None                   # A drag inside the game.
                return
            if now - at >= HOLD_S:
                self.dragging = name
                if name == 'pet':
                    self.pet.dragging = True
                    self.pet.update_activity()
            return
        target = point - offset
        if name == 'pet':
            self.pet.move_clamped(target)
            for extra in (getattr(self.pet, 'game_halo', None), getattr(self.pet, 'game_usage', None)):
                if extra is not None and extra.isVisible():
                    extra.follow()
        else:
            widget.move(target)

    def _release(self):
        name, widget = self.dragging, self.press[1] if self.press else None
        self.dragging = None
        if name == 'pet':
            self.pet.dragging = False
            try:
                self.pet.interact('landing', .9)
            except Exception:
                self.pet.update_activity()
        elif name == 'bar' and widget is not None:
            self.pet.panel.prefs['game_bar_pos'] = [widget.x(), widget.y()]
            try:
                self.pet.panel.persist()
            except Exception:
                pass
