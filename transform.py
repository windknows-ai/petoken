"""Her transformation into her second form when game mode starts (2.1).

Continuous, no fades or cuts: she rises from her idle pose (frame by frame),
the star ring gathers behind her, then each piece of armour forms on her
body: a line of light first traces the piece's outline, and the piece fills
in behind it. Then the sword, a short MVP moment (a showcase spotlight comes
on from above, her MVP poses, a slight push-in) and the effects settle. Leaving game mode
plays the armour coming off, quickly, in reverse.

The art is a series of stage images on one canvas (docs/V2_1_ART_PROMPTS.md):
consecutive stages differ only where the new piece is. ``Pieces`` finds each
piece as that difference, once, in a worker thread, at her display size.
Missing art means no animation (game mode simply switches).
"""
from __future__ import annotations

import math
import os
import random
import threading
import time
from pathlib import Path

from PySide6.QtCore import QObject, QPoint, QPointF, QRect, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (QColor, QImage, QLinearGradient, QPainter, QPen, QPixmap, QRadialGradient,
                           QTransform)
from PySide6.QtWidgets import QApplication, QWidget

import pet_geometry as geometry

ROOT = Path(__file__).resolve().parent
RISE = ('xform_rise_0a', 'xform_rise_0b', 'xform_rise_1', 'xform_rise_2', 'xform_rise_3', 'xform_base')
# Each new piece, and the direction its light travels.
STAGES = (('xform_armor_1', 'up'), ('xform_armor_2', 'up'), ('xform_armor_3', 'out'), ('xform_armor_4', 'up'),
          ('xform_armor_5', 'out'), ('xform_armor_6', 'down'), ('xform_armor_7', 'across'),
          ('xform_weapon_1', 'up'), ('xform_weapon_2', 'up'))
MVP = ('mvp_1', 'mvp_2', 'mvp_3')
FORM2 = 'xform_weapon_2'          # Her second form until form2_idle exists.
# Seconds at 1× speed.
RISE_S = 1.8
RING_S = 1.2
PIECE_S = .74
MVP_S = 2.0
SETTLE_S = 1.2
LEAVE_PIECE_S = .2
LEAVE_RISE_S = .9
FPS = 120
GLOW = QColor(186, 228, 255)      # The light that draws the armour.
DIFF_MIN = 40                     # Summed RGBA difference that counts as "changed".


def art_dir():
    """assets/v2_1, or PETOKEN_V2_1_ART (the art branch while it is not merged)."""
    folder = ROOT / 'assets' / 'v2_1'
    if (folder / 'xform_base.png').exists():
        return folder
    other = os.environ.get('PETOKEN_V2_1_ART')
    return Path(other) if other and (Path(other) / 'xform_base.png').exists() else None


def available():
    folder = art_dir()
    return folder is not None and all((folder / f'{name}.png').exists() for name, _ in STAGES)


def _scaled(path, side):
    image = QImage(str(path))
    if image.isNull():
        return None
    return image.scaled(side, side, Qt.IgnoreAspectRatio, Qt.SmoothTransformation).convertToFormat(
        QImage.Format_ARGB32_Premultiplied)


def _diff_piece(before, after):
    """(piece image, outline image, bbox) of what ``after`` adds to ``before``."""
    w, h = after.width(), after.height()
    a, b = bytes(before.constBits()), bytes(after.constBits())
    stride = w * 4
    mask = bytearray(w * h)
    xs, ys = [], []
    for y in range(h):
        row = y * stride
        if a[row:row + stride] == b[row:row + stride]:
            continue
        for x in range(w):
            k = row + x * 4
            if a[k:k + 4] != b[k:k + 4]:
                d = (abs(a[k] - b[k]) + abs(a[k + 1] - b[k + 1]) + abs(a[k + 2] - b[k + 2])
                     + abs(a[k + 3] - b[k + 3]))
                if d >= DIFF_MIN:
                    mask[y * w + x] = 1
                    xs.append(x)
                    ys.append(y)
    if not xs:
        return None
    x0, y0, x1, y1 = min(xs), min(ys), max(xs) + 1, max(ys) + 1
    box = QRect(x0, y0, x1 - x0, y1 - y0)
    piece = after.copy(box)
    outline = QImage(box.size(), QImage.Format_ARGB32_Premultiplied)
    outline.fill(Qt.transparent)
    bits = bytearray(bytes(piece.constBits()))
    pw = box.width()
    glow = (GLOW.blue(), GLOW.green(), GLOW.red(), 255)       # BGRA, premultiplied (alpha 255).
    out = bytearray(bytes(outline.constBits()))
    for y in range(y0, y1):
        for x in range(x0, x1):
            k = ((y - y0) * pw + (x - x0)) * 4
            if not mask[y * w + x]:
                bits[k:k + 4] = b'\0\0\0\0'                     # Only the new piece.
                continue
            edge = (x == 0 or y == 0 or x == w - 1 or y == h - 1 or not mask[y * w + x - 1]
                    or not mask[y * w + x + 1] or not mask[(y - 1) * w + x] or not mask[(y + 1) * w + x])
            if edge:
                out[k:k + 4] = bytes(glow)
    piece = QImage(bytes(bits), pw, box.height(), pw * 4, QImage.Format_ARGB32_Premultiplied).copy()
    outline = QImage(bytes(out), pw, box.height(), pw * 4, QImage.Format_ARGB32_Premultiplied).copy()
    return piece, outline, box


def _silhouette(image):
    """Her shape in solid light, for the MVP flash."""
    out = QImage(image.size(), QImage.Format_ARGB32_Premultiplied)
    out.fill(Qt.transparent)
    p = QPainter(out)
    p.drawImage(0, 0, image)
    p.setCompositionMode(QPainter.CompositionMode_SourceIn)
    p.fillRect(out.rect(), QColor(255, 255, 255))
    p.end()
    return out


class Pieces:
    """Everything the animation draws, at one display size (built once, in a worker)."""

    def __init__(self, side):
        self.side = side
        self.rise = []          # Images, idle side first.
        self.base = None
        self.stages = []        # (piece, outline, bbox, direction, full stage image)
        self.mvp = []
        self.form2 = None
        self.flash = None

    @classmethod
    def build(cls, side):
        folder = art_dir()
        if folder is None:
            return None
        self = cls(side)
        for name in RISE:
            image = _scaled(folder / f'{name}.png', side) if (folder / f'{name}.png').exists() else None
            if image is not None:
                self.rise.append(image)
        self.base = self.rise[-1] if self.rise else None
        previous = self.base
        if previous is None:
            return None
        for name, direction in STAGES:
            image = _scaled(folder / f'{name}.png', side)
            if image is None:
                return None
            found = _diff_piece(previous, image)
            if found is not None:
                piece, outline, box = found
                self.stages.append((piece, outline, box, direction, image))
            previous = image
        self.form2 = previous
        # She ends on the first frame of her second-form idle, where the pet takes over.
        if (folder / 'form2_idle_1.png').exists():
            self.form2 = _scaled(folder / 'form2_idle_1.png', side)
        for name in MVP:
            if (folder / f'{name}.png').exists():
                self.mvp.append(_scaled(folder / f'{name}.png', side))
        self.flash = _silhouette(self.mvp[-1] if self.mvp else self.form2)
        return self


class PieceCache(QObject):
    """Builds Pieces in a worker the first time they are needed for a size."""

    ready = Signal()

    def __init__(self):
        super().__init__()
        self.pieces = None
        self._building = None
        self._lock = threading.Lock()

    def get(self, side):
        pieces = self.pieces
        if pieces is not None and pieces.side == side:
            return pieces
        with self._lock:
            if self._building == side:
                return None
            self._building = side

        def work():
            try:
                built = Pieces.build(side)
            except Exception:
                built = None
            self.pieces = built
            with self._lock:
                self._building = None
            self.ready.emit()
        threading.Thread(target=work, daemon=True, name='petoken-transform-art').start()
        return None


CACHE = PieceCache()


def _ease(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


class Timeline:
    """Which part of the animation plays at ``t`` seconds (1× speed)."""

    def __init__(self, pieces, leaving=False):
        self.pieces = pieces
        self.leaving = leaving
        self.parts = []
        rise = len(pieces.rise)
        if leaving:
            self.parts.append(('unarm', len(pieces.stages) * LEAVE_PIECE_S))
            self.parts.append(('fall', LEAVE_RISE_S))
        else:
            self.parts.append(('rise', RISE_S if rise > 1 else .4))
            self.parts.append(('ring', RING_S))
            self.parts.append(('arm', len(pieces.stages) * PIECE_S))
            self.parts.append(('mvp', MVP_S))
            self.parts.append(('settle', SETTLE_S))
        self.length = sum(d for _, d in self.parts)

    def at(self, t):
        for name, duration in self.parts:
            if t < duration:
                return name, t / duration if duration else 1.0
            t -= duration
        return self.parts[-1][0], 1.0


class Particle:
    __slots__ = ('x', 'y', 'vx', 'vy', 'life', 'age', 'size', 'color')

    def __init__(self, x, y, vx, vy, life, size, color):
        self.x, self.y, self.vx, self.vy, self.life, self.size, self.color = x, y, vx, vy, life, size, color
        self.age = 0.0


class TransformStage(QWidget):
    """Click-through window over her that plays the transformation."""

    finished = Signal()

    def __init__(self, pet, pieces, leaving=False, speed=1.0, idle=None):
        super().__init__(None)
        self.pet = pet
        self.pieces = pieces
        self.timeline = Timeline(pieces, leaving)
        self.speed = speed
        self.idle = idle                    # Her idle pose (QImage), where the rise starts.
        self.t = 0.0
        self._last = None
        self.particles = []
        self.rng = random.Random(3)
        self._spark = self._spark_pixmap()
        flags = (Qt.Tool | Qt.FramelessWindowHint | Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus
                 | Qt.WindowStaysOnTopHint)
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.setInterval(max(1, 1000 // FPS))
        self.timer.timeout.connect(self._tick)
        self.frames = 0
        self.place()

    # Geometry ---------------------------------------------------------------
    def sprite_rect(self):
        """Her sprite box on screen (global), exactly where the pet draws it."""
        sx, sy, sw, sh = geometry.scaled_sprite_rect(self.pet.pet_scale)
        return QRectF(self.pet.x() + sx, self.pet.y() + sy, sw, sh)

    def place(self):
        box = self.sprite_rect()
        w, h = box.width() * 2.2, box.height() * 2.0
        x = box.center().x() - w / 2
        y = box.bottom() + box.height() * .3 - h
        self.setGeometry(QRect(round(x), round(y), round(w), round(h)))
        self._box = QRectF(box.x() - self.x(), box.y() - self.y(), box.width(), box.height())

    @staticmethod
    def _spark_pixmap():
        pix = QPixmap(32, 32)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        g = QRadialGradient(16, 16, 16)
        g.setColorAt(0, QColor(255, 255, 255, 255))
        g.setColorAt(.3, QColor(GLOW.red(), GLOW.green(), GLOW.blue(), 200))
        g.setColorAt(1, QColor(0, 0, 0, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawEllipse(0, 0, 32, 32)
        p.end()
        return pix

    # Running ----------------------------------------------------------------
    def start(self):
        self._last = None
        self.show()
        self.raise_()
        self.timer.start()

    def _tick(self):
        now = time.perf_counter()
        dt = 0.0 if self._last is None else min(.05, now - self._last)
        self._last = now
        self.t += dt * self.speed
        self.frames += 1
        for particle in self.particles:
            particle.age += dt
            particle.x += particle.vx * dt
            particle.y += particle.vy * dt
            particle.vy -= 18 * dt          # Light drifts upward.
        self.particles = [q for q in self.particles if q.age < q.life]
        halo = getattr(self.pet, 'game_halo', None)
        if halo is not None:
            name, f = self.timeline.at(self.t)
            halo.intro = self._ring_intro(name, f)
            halo.flare = self._ring_flare(name, f)
        if self.t >= self.timeline.length:
            self.timer.stop()
            self.finished.emit()
            return
        if self.frames % 30 == 0:
            self.raise_()
        self.update()

    def _ring_intro(self, name, f):
        if self.timeline.leaving:
            return 1.0 - (_ease(f) if name == 'fall' else 0.0)
        return {'rise': 0.0, 'ring': _ease(f)}.get(name, 1.0)

    @staticmethod
    def _ring_flare(name, f):
        # A gentle lift while she is on show, nothing blinding.
        if name == 'mvp':
            return .25 * math.sin(min(1.0, f) * math.pi)
        return 0.0

    def _burst(self, x, y, count, speed=90, life=.9):
        for _ in range(count):
            a = self.rng.uniform(0, 2 * math.pi)
            v = self.rng.uniform(.3, 1) * speed
            self.particles.append(Particle(x, y, math.cos(a) * v, math.sin(a) * v, self.rng.uniform(.4, life),
                                           self.rng.uniform(2, 6), None))

    # Drawing ----------------------------------------------------------------
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        name, f = self.timeline.at(self.t)
        box = QRectF(self._box)
        lift = self._lift(name, f) * box.height()
        zoom = self._zoom(name, f)
        centre = QPointF(box.center().x(), box.center().y() - lift)
        p.translate(centre)
        p.scale(zoom, zoom)
        p.translate(-centre)
        target = box.translated(0, -lift)
        if name in ('mvp', 'settle'):
            self._paint_spotlight(p, target, name, f)
        self._paint_body(p, target, name, f)
        p.resetTransform()
        self._paint_particles(p)

    def _lift(self, name, f):
        """She floats a little while transforming, and lands at the end."""
        top = .05
        if self.timeline.leaving:
            return top * (1 - _ease(f)) if name == 'fall' else top
        if name == 'rise':
            return top * _ease(f)
        if name == 'settle':
            return top * (1 - _ease(f))
        return top

    def _zoom(self, name, f):
        if self.timeline.leaving:
            return 1.0
        if name == 'arm':
            return 1.0 + .04 * f
        if name == 'mvp':
            return 1.04 + .04 * _ease(min(1.0, f * 2))
        if name == 'settle':
            return 1.08 - .08 * _ease(f)
        return 1.0

    def _rise_frame(self, f):
        frames = ([self.idle] if self.idle is not None else []) + list(self.pieces.rise)
        if len(frames) == 1:
            return frames[0], None, 0.0
        x = f * (len(frames) - 1)
        i = min(len(frames) - 2, int(x))
        local = x - i
        # Each pose holds, then a short in-between into the next (limited animation).
        blend = max(0.0, (local - .78) / .22)
        return frames[i], frames[i + 1], blend

    def _paint_body(self, p, target, name, f):
        pieces = self.pieces
        scale = target.width() / pieces.side
        if name in ('rise', 'fall'):
            a, b, blend = self._rise_frame(f if name == 'rise' else 1 - f)
            p.drawImage(target, a)
            if b is not None and blend > 0:
                p.setOpacity(blend)
                p.drawImage(target, b)
                p.setOpacity(1)
            return
        if name == 'ring':
            p.drawImage(target, pieces.base)
            return
        if name in ('mvp', 'settle'):
            image = pieces.form2
            if name == 'mvp' and pieces.mvp:
                image = pieces.mvp[min(len(pieces.mvp) - 1, int(f * len(pieces.mvp)))]
            p.drawImage(target, image)
            return
        # Arming (or unarming): the finished stages, then the piece being drawn.
        count = len(pieces.stages)
        if name == 'unarm':
            x = (1 - f) * count
        else:
            x = f * count
        done = min(count, int(x))
        local = x - done
        below = pieces.stages[done - 1][4] if done > 0 else pieces.base
        p.drawImage(target, below)
        if done < count:
            piece, outline, bbox, direction, _ = pieces.stages[done]
            rect = QRectF(target.x() + bbox.x() * scale, target.y() + bbox.y() * scale,
                          bbox.width() * scale, bbox.height() * scale)
            if name == 'unarm':
                self._paint_piece(p, piece, outline, rect, direction, local, leaving=True)
            else:
                self._paint_piece(p, piece, outline, rect, direction, local)
                if self.frames % 3 == 0:
                    front = self._front_point(rect, direction, local)
                    self._burst(front.x() + self._origin().x(), front.y() + self._origin().y(), 2, 50, .7)

    def _origin(self):
        return QPointF(0, 0)

    @staticmethod
    def _front_point(rect, direction, t):
        if direction == 'up':
            return QPointF(rect.center().x(), rect.bottom() - rect.height() * t)
        if direction == 'down':
            return QPointF(rect.center().x(), rect.top() + rect.height() * t)
        if direction == 'across':
            return QPointF(rect.left() + rect.width() * t, rect.center().y())
        return QPointF(rect.center().x() + rect.width() / 2 * t * (1 if int(t * 10) % 2 else -1), rect.center().y())

    @staticmethod
    def _gradient(rect, direction, front, soft):
        """Opaque where the light has passed, clear ahead of it."""
        if direction in ('up', 'down', 'across'):
            if direction == 'up':
                start, end = QPointF(rect.center().x(), rect.bottom()), QPointF(rect.center().x(), rect.top())
            elif direction == 'down':
                start, end = QPointF(rect.center().x(), rect.top()), QPointF(rect.center().x(), rect.bottom())
            else:
                start, end = QPointF(rect.left(), rect.center().y()), QPointF(rect.right(), rect.center().y())
            g = QLinearGradient(start, end)
        else:
            radius = max(rect.width(), rect.height()) / 2
            g = QRadialGradient(rect.center(), radius)
        front = max(0.0, min(1.0, front))
        g.setColorAt(0, QColor(0, 0, 0, 255))
        g.setColorAt(max(0.0, front - soft), QColor(0, 0, 0, 255))
        g.setColorAt(min(1.0, front + 1e-3), QColor(0, 0, 0, 0))
        g.setColorAt(1, QColor(0, 0, 0, 0))
        return g

    def _paint_piece(self, p, piece, outline, rect, direction, t, leaving=False):
        """The outline of light runs ahead; the piece fills in behind it, glowing, then cools."""
        side = QSize(max(1, round(rect.width())), max(1, round(rect.height())))
        layer = QImage(side, QImage.Format_ARGB32_Premultiplied)
        layer.fill(Qt.transparent)
        q = QPainter(layer)
        q.setRenderHint(QPainter.SmoothPixmapTransform)
        local = QRectF(0, 0, side.width(), side.height())
        if leaving:
            fill_front, line_front, heat = t, t, 1 - t
        else:
            line_front = _ease(min(1.0, t * 1.45))
            fill_front = _ease(max(0.0, (t - .18) / .82))
            heat = 1 - _ease(max(0.0, (t - .55) / .45))
        # The piece, as far as the fill has come.
        q.drawImage(local, piece)
        if heat > 0:                       # Freshly formed armour glows, then takes its colour.
            q.setCompositionMode(QPainter.CompositionMode_SourceAtop)
            hot = QColor(GLOW)
            hot.setAlpha(int(200 * heat))
            q.fillRect(local, hot)
        q.setCompositionMode(QPainter.CompositionMode_DestinationIn)
        q.fillRect(local, self._gradient(local, direction, fill_front, .12))
        q.setCompositionMode(QPainter.CompositionMode_SourceOver)
        # The outline, as far as the line of light has come, brightest at its front.
        line = QImage(side, QImage.Format_ARGB32_Premultiplied)
        line.fill(Qt.transparent)
        r = QPainter(line)
        r.setRenderHint(QPainter.SmoothPixmapTransform)
        r.drawImage(local, outline)
        r.setCompositionMode(QPainter.CompositionMode_DestinationIn)
        r.fillRect(local, self._gradient(local, direction, line_front, .35))
        r.end()
        q.setOpacity(.9 if not leaving else heat)
        q.drawImage(0, 0, line)
        q.end()
        p.drawImage(rect, layer)
        # A soft glow over the line, so it reads at a small size.
        p.setOpacity(.55 * (heat if leaving else (1 - fill_front * .6)))
        p.drawImage(rect.adjusted(-2, -2, 2, 2), line)
        p.setOpacity(1)

    def _paint_spotlight(self, p, target, name, f):
        """A showcase spotlight: soft-edged, brighter in the middle, coming on from
        the top down onto her; a soft pool at her feet; it dims as the moment ends."""
        if name == 'mvp':
            reach = _ease(min(1.0, f / .3))                     # The light travels down.
            strength = 1.0
        else:
            reach, strength = 1.0, 1 - _ease(f)
        if strength <= 0:
            return
        top_y = min(target.top() - target.height() * .55, 0.0)
        floor = target.bottom() - target.height() * .02
        bottom = top_y + (floor - top_y) * reach
        cx = target.center().x()
        narrow, wide = target.width() * .14, target.width() * .6
        spread = narrow + (wide - narrow) * reach
        # Drawn small, then scaled up smoothly: the edges come out soft.
        k = 6
        area = QRectF(cx - wide * 1.4, top_y, wide * 2.8, floor - top_y + target.height() * .1)
        small = QImage(max(1, int(area.width() / k)), max(1, int(area.height() / k)),
                       QImage.Format_ARGB32_Premultiplied)
        small.fill(Qt.transparent)
        q = QPainter(small)
        q.setRenderHint(QPainter.Antialiasing)
        q.scale(1 / k, 1 / k)
        q.translate(-area.x(), -area.y())
        q.setPen(Qt.NoPen)
        # Layers from the wide, faint outside to the bright core.
        for share, alpha in ((1.0, 30), (.75, 32), (.5, 38), (.28, 44)):
            beam = QLinearGradient(QPointF(cx, top_y), QPointF(cx, floor))
            beam.setColorAt(0, QColor(235, 244, 255, 0))
            beam.setColorAt(.2, QColor(236, 244, 255, int(alpha * strength)))
            beam.setColorAt(.75, QColor(214, 230, 255, int(alpha * .85 * strength)))
            beam.setColorAt(1, QColor(200, 220, 255, int(alpha * .7 * strength)))
            q.setBrush(beam)
            half_top, half_bottom = narrow * share, spread * share
            q.drawPolygon([QPointF(cx - half_top, top_y), QPointF(cx + half_top, top_y),
                           QPointF(cx + half_bottom, bottom), QPointF(cx - half_bottom, bottom)])
        # Faint streaks inside the beam, drifting slowly.
        for n in range(5):
            drift = math.sin(self.t * .7 + n * 1.9) * .25
            offset = (n - 2) / 2.5 + drift * .3
            streak = QLinearGradient(QPointF(cx, top_y), QPointF(cx, bottom))
            streak.setColorAt(0, QColor(255, 255, 255, 0))
            streak.setColorAt(.3, QColor(255, 255, 255, int(22 * strength)))
            streak.setColorAt(1, QColor(255, 255, 255, 0))
            q.setBrush(streak)
            x0, x1 = cx + narrow * offset * .6, cx + spread * offset * .8
            w0, w1 = narrow * .08, spread * .07
            q.drawPolygon([QPointF(x0 - w0, top_y), QPointF(x0 + w0, top_y),
                           QPointF(x1 + w1, bottom), QPointF(x1 - w1, bottom)])
        if reach >= .99:
            pool = QRadialGradient(QPointF(cx, floor), wide)
            pool.setColorAt(0, QColor(228, 240, 255, int(95 * strength)))
            pool.setColorAt(.5, QColor(210, 228, 255, int(40 * strength)))
            pool.setColorAt(1, QColor(0, 0, 0, 0))
            q.setBrush(pool)
            q.save()
            q.translate(cx, floor)
            q.scale(1, .22)
            q.drawEllipse(QPointF(0, 0), wide * 1.1, wide * 1.1)
            q.restore()
        q.end()
        p.save()
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.drawImage(area, small)
        p.restore()
        # Dust drifting in the beam.
        if name == 'mvp' and self.frames % 5 == 0:
            x = cx + self.rng.uniform(-.7, .7) * spread * .7
            y = top_y + self.rng.uniform(.2, .9) * (bottom - top_y)
            self.particles.append(Particle(x, y, self.rng.uniform(-5, 5), self.rng.uniform(3, 10),
                                           self.rng.uniform(.9, 1.7), self.rng.uniform(1.0, 2.0), None))

    def _paint_particles(self, p):
        for particle in self.particles:
            alpha = 1 - particle.age / particle.life
            p.setOpacity(max(0.0, alpha))
            s = particle.size * (1 + .5 * alpha)
            p.drawPixmap(QRectF(particle.x - s, particle.y - s, 2 * s, 2 * s), self._spark, QRectF(0, 0, 32, 32))
        p.setOpacity(1)
