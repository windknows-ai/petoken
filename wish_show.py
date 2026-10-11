"""The wishing show (2.5).

A meteor shower drifts across the night sky, every streak radiating from one
point like a real shower. She flies in, looks around among the falling stars,
spots hers and catches it (a single wish), or sweeps through the shower
catching ten that then circle her (ten wishes). Each find bursts in its
rarity's light, then becomes the card of what she found. A click skips to the
cards; another closes.

The lights are pre-rendered with real bloom and lens streaks
(tools/render_wish_fx.py) and drawn additively, so they mix like light. Each
rarity has its own shape, not just its own colour:
Stars a sapphire four-point star, Moon a full moon in a pale halo ring that
flashes, Sun a gold sun with a ragged corona and rays, Galaxy a tilted silver
spiral that turns, Starsea a prism star in turning rainbow rings.
"""
from __future__ import annotations

import math
import random

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QConicalGradient, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QWidget

import pet_assets
import shop
from localization import text

FX_DIR = pet_assets.ASSETS_DIR / 'v2_5' / 'wish'
SHOWER = ('ice', 'champagne', 'lavender', 'pearl')                 # The task-star palette.
POSES = dict(fly=('dragged', 'star_dragged'), look=('curious', 'star_thinking'), spot=('surprised', 'star_poked'),
             reach=('wave', 'star_wave'), cheer=('cheer', 'star_celebrate'))
_FX = {}


def fx(name):
    """A pre-rendered light (on black, drawn additively); a null pixmap when missing."""
    if name not in _FX:
        path = FX_DIR / (name + ('.jpg' if name == 'sky' else '.webp'))
        _FX[name] = QPixmap(str(path)) if path.is_file() else QPixmap()
    return _FX[name]


def _ease(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def _out(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def _back(x, s=1.7):
    x = max(0.0, min(1.0, x)) - 1
    return x * x * ((s + 1) * x + s) + 1


def _lerp(a, b, f):
    return a + (b - a) * f


def _rgba(colour, alpha):
    return QColor(colour.red(), colour.green(), colour.blue(), max(0, min(255, int(alpha))))


def light(p, name, centre, width, alpha=1.0, angle=0.0, squash=1.0, tilt=0.0):
    """Draw light ``name`` centred at ``centre``, ``width`` wide. ``squash`` flattens it
    after turning (a tilted disc that turns, like the galaxy), ``tilt`` turns the
    flattened result."""
    pm = fx(name)
    if pm.isNull() or alpha <= .01 or width < 1:
        return
    p.save()
    p.translate(centre)
    if tilt:
        p.rotate(tilt)
    if squash != 1.0:
        p.scale(1.0, squash)
    if angle:
        p.rotate(angle)
    p.setOpacity(min(1.0, alpha))
    height = width * pm.height() / pm.width()
    p.drawPixmap(QRectF(-width / 2, -height / 2, width, height), pm, QRectF(pm.rect()))
    p.restore()


def streak(p, name, head, angle, length, alpha=1.0, grow=1.0):
    """A meteor sprite with its head at ``head`` flying at ``angle`` degrees; its tail is
    ``length`` long and grows out of the head for ``grow`` < 1."""
    pm = fx(name)
    if pm.isNull() or alpha <= .01:
        return
    hero = pm.width() >= 1280
    hx = pm.width() - (72 if hero else 56)
    scale = length / (hx * .55)                                     # The visible tail is about half the sprite.
    start = hx * (1 - max(.02, min(1.0, grow)))
    p.save()
    p.translate(head)
    p.rotate(angle)
    p.scale(scale, scale)
    p.setOpacity(min(1.0, alpha))
    p.drawPixmap(QRectF(start - hx, -pm.height() / 2, pm.width() - start, pm.height()), pm,
                 QRectF(start, 0, pm.width() - start, pm.height()))
    p.restore()


class WishShow(QWidget):
    FPS_MS = 25

    def __init__(self, parent, results, language, starsea=False):
        super().__init__(parent, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self.results, self.language, self.starsea = results, language, starsea
        self.ten = len(results) > 1
        self.t = 0.0
        if parent is not None:
            self.setGeometry(parent.geometry())
        else:
            self.resize(1000, 640)
        self.rng = random.Random(len(results) * 31 + sum(map(ord, results[0]['item']['id'])))
        best = max(range(len(results)), key=lambda i: shop.RARITIES.index(results[i]['item']['rarity']))
        others = sorted((i for i in range(len(results)) if i != best),
                        key=lambda i: shop.RARITIES.index(results[i]['item']['rarity']))
        self.order = others + [best]                        # The best one comes last.
        self.best = best
        if self.ten:
            self.catch = {i: 2.9 + k * .26 + (.45 if i == best else 0) for k, i in enumerate(self.order)}
            self.flip0 = max(self.catch.values()) + 1.2
            self.length = self.flip0 + 10 * .12 + 1.4
        else:
            self.catch = {0: 3.75}
            self.flip0 = 5.0
            self.length = 6.4
        self.travel = .75 if self.ten else 1.05
        self.spot = min(self.catch.values()) - self.travel - .1     # She sees the first one coming.
        self.shower = self._shower()
        self.twinkles = [(self.rng.random(), self.rng.random() * .92, self.rng.uniform(.010, .028),
                          self.rng.random() * 6.3, self.rng.uniform(.7, 1.8), self.rng.choice(SHOWER))
                         for _ in range(70)]
        self.sparks = {}                                    # Per catch: the sparks it throws out.
        self._poses = {}
        self._sky = None
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.setInterval(self.FPS_MS)
        self.timer.timeout.connect(self._step)
        self.timer.start()

    # Setup ------------------------------------------------------------------------------
    def _shower(self):
        """Meteors: (start time, life, x, y, depth, colour key). The rate swells, peaks
        while she searches and fades out after the catch."""
        rng = self.rng
        peak_end = (max(self.catch.values()) if self.ten else self.catch[0]) + .2
        end = peak_end + 1.4
        out, t = [], .15
        while t < end:
            ramp = _ease((t - .1) / 1.0) * (1 - _ease((t - peak_end) / 1.2))
            rate = 2.5 + (16 if self.ten else 12) * ramp
            t += rng.expovariate(rate)
            depth = rng.random() ** 1.4
            out.append((t, rng.uniform(1.0, 1.7), rng.uniform(-.15, 1.05), rng.uniform(-.25, .75), depth,
                        rng.choice(SHOWER)))
        return out

    def pose(self, name, size):
        """Her picture for a moment of the show, scaled once to ``size`` pixels tall."""
        state = POSES[name][1 if self.starsea else 0]
        key = (state, int(size))
        if key not in self._poses:
            source = None
            for candidate in (state, POSES[name][0], 'idle'):
                source = (pet_assets.frame_for(candidate, 0) if pet_assets.frame_count(candidate)
                          else pet_assets.sprite_for(candidate))
                if source is not None and not source.isNull():
                    break
            if source is None or source.isNull():
                self._poses[key] = None
            else:
                ratio = self.devicePixelRatioF()
                scaled = source.scaledToHeight(int(size * ratio), Qt.SmoothTransformation)
                scaled.setDevicePixelRatio(ratio)
                self._poses[key] = scaled
        return self._poses[key]

    def colour(self, index, t=None):
        from shop_view import rarity_colour
        return rarity_colour(self.rarity(index), self.t if t is None else t, index / 10)

    def rarity(self, index):
        return self.results[index]['item']['rarity']

    def rank(self, index):
        return shop.RARITIES.index(self.rarity(index))

    def _step(self):
        self.t += self.FPS_MS / 1000
        if self.t > self.length + 30:
            self.timer.stop()
        self.update()

    def mousePressEvent(self, event):
        if self.t < self.length - .6:
            self.t = self.length - .6                       # Straight to the cards.
        else:
            self.close()

    def keyPressEvent(self, event):
        self.mousePressEvent(event)

    # Her --------------------------------------------------------------------------------
    def her_size(self):
        h = self.height()
        size = h * (.40 if not self.ten else .34)
        if self.ten:
            size *= 1 - .4 * _ease((self.t - (self.flip0 - .8)) / .8)
        return size

    def her_place(self):
        """Her centre, size, lean (degrees) and whether she faces left."""
        w, h, t = self.width(), self.height(), self.t
        size = self.her_size()
        rest = QPointF(w * .30, h * .60) if not self.ten else QPointF(w * .50, h * .62)
        start = QPointF(-.18 * w, h * 1.05)
        bend = QPointF(w * .05, h * .30) if not self.ten else QPointF(w * .12, h * .25)
        f = _out((t - .7) / 1.4)                              # Flying in on a curve.
        a, b = (1 - f) ** 2, 2 * (1 - f) * f
        pos = start * a + bend * b + rest * (f * f)
        lean = -16 * (1 - f)
        facing_left = False
        if f >= 1:
            pos = QPointF(rest)
            look = t - 2.1
            if 0 < look < self.spot - 2.1:                   # Searching: she drifts and looks back once.
                pos += QPointF(math.sin(look * 1.7) * w * .02, -math.sin(look * 1.1) * h * .015)
                facing_left = .35 < look < .85
        if self.ten:
            first, last = min(self.catch.values()), max(self.catch.values())
            sweep = _ease((t - first + .4) / (last - first + .4))
            pos += QPointF(math.sin(sweep * math.pi * 2) * w * .1, -math.sin(sweep * math.pi) * h * .05)
            aside = _ease((t - (self.flip0 - .8)) / .8)
            pos = pos + (QPointF(w * .88, h * .80) - pos) * aside
        else:
            towards = math.exp(-((t - self.catch[0]) / .45) ** 2)   # A little dash up to meet it.
            pos += QPointF(w * .03, -h * .04) * towards
        pos += QPointF(0, math.sin(t * 2.1) * h * .008)
        return pos, size, lean, facing_left

    def pose_name(self):
        t = self.t
        if t < 2.1:
            return 'fly'
        if t < self.spot:
            return 'look'
        if self.ten:
            if t > self.flip0 - .8:
                return 'cheer'
            near = min(abs(t - at) for at in self.catch.values())
            return 'reach' if near < .3 or t < min(self.catch.values()) else 'cheer'
        at = self.catch[0]
        if t < at - .55:
            return 'spot'
        return 'reach' if t < at + .15 else 'cheer'

    def hand(self):
        pos, size, lean, facing_left = self.her_place()
        dx = size * .40 * (-1 if facing_left else 1)
        return QPointF(pos.x() + dx, pos.y() - size * .30)      # Just past her raised hand, clear of her face.

    def slot(self, k):
        """Where card ``k`` sits."""
        w, h = self.width(), self.height()
        if not self.ten:
            return QPointF(w * .66, h * .47), (w * .26, h * .54)
        cw, ch = min(w * .14, 170), min(h * .3, 210)
        gap = cw * .1
        row, col = divmod(k, 5)
        x0 = w * .44 - 2 * (cw + gap)
        return QPointF(x0 + col * (cw + gap), h * .3 + row * (ch + gap)), (cw, ch)

    # Painting ---------------------------------------------------------------------------
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        self._paint_sky(p)
        p.setCompositionMode(QPainter.CompositionMode_Plus)
        self._paint_twinkles(p)
        self._paint_shower(p)
        if self.ten:
            self._paint_orbit(p, behind=True)
        for index in self.order:                            # Catches light her from behind.
            self._paint_burst(p, index)
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        self._paint_her(p)
        p.setCompositionMode(QPainter.CompositionMode_Plus)
        if self.ten:
            self._paint_orbit(p, behind=False)
        for index in self.order:
            self._paint_destined(p, index)
        if not self.ten:
            self._paint_found(p)
        self._paint_card_lights(p)
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        self._paint_cards(p)
        p.setOpacity(1)
        if self.t > self.length - .9:
            p.setPen(QColor(220, 220, 255, int(200 * _ease((self.t - self.length + .9) / .4))))
            p.setFont(QFont('Microsoft YaHei UI', 10))
            p.drawText(QRectF(0, self.height() - 44, self.width(), 26), Qt.AlignCenter,
                       text('shop_wish_close', self.language))
        p.end()

    def _paint_sky(self, p):
        w, h, t = self.width(), self.height(), self.t
        p.fillRect(self.rect(), QColor(4, 5, 20))
        sky = fx('sky')
        if sky.isNull():
            return
        cover = 1.10                                        # Room to drift.
        if self._sky is None or self._sky[0] != (w, h):
            ratio = self.devicePixelRatioF()
            scale = max(w / sky.width(), h / sky.height()) * cover
            scaled = sky.scaled(int(sky.width() * scale * ratio), int(sky.height() * scale * ratio),
                                Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            scaled.setDevicePixelRatio(ratio)
            self._sky = ((w, h), scaled)
        scaled = self._sky[1]
        sw, sh = scaled.width() / scaled.devicePixelRatio(), scaled.height() / scaled.devicePixelRatio()
        drift = t / 12.0                                    # A slow pan, like the sky turning.
        x = -(sw - w) * (.15 + .7 * (drift % 1.0 if drift < 1 else 1.0))
        y = -(sh - h) * (.6 - .3 * min(1.0, drift))
        p.setOpacity(_ease(t / .5))
        p.drawPixmap(QPointF(x, y), scaled)
        p.setOpacity(1)

    def _paint_twinkles(self, p):
        w, h, t = self.width(), self.height(), self.t
        fade = _ease(t / .6)
        for x, y, size, phase, speed, key in self.twinkles:
            a = max(0.0, math.sin(t * speed + phase)) ** 3
            if a > .02:
                light(p, f'sparkle_{key}', QPointF(x * w, y * h), size * h * (.7 + .5 * a), a * .9 * fade,
                      angle=15 * math.sin(t * .5 + phase))

    def _paint_shower(self, p):
        w, h, t = self.width(), self.height(), self.t
        radiant = QPointF(w * 1.22, -h * .38)
        focus = 1.0
        if not self.ten:                                    # The sky hushes while hers comes.
            focus = 1 - .45 * math.exp(-((t - self.catch[0] + .3) / .7) ** 2)
        for at, life, x, y, depth, key in self.shower:
            age = t - at
            if not 0 <= age <= life:
                continue
            f = age / life
            centre = QPointF(x * w, y * h)
            d = centre - radiant
            n = math.hypot(d.x(), d.y()) or 1
            ux, uy = d.x() / n, d.y() / n
            speed = h * (.45 + .75 * depth)
            head = centre + QPointF(ux, uy) * (speed * (age - life * .4))
            angle = math.degrees(math.atan2(uy, ux))
            env = _ease(f / .12) * (1 - _ease((f - .5) / .5))
            alpha = env * (.3 + .7 * depth) * focus
            thin = depth < .5
            length = h * (.14 + .36 * depth)
            streak(p, f'meteor_{key}{"_thin" if thin else ""}', head, angle, length, alpha, grow=f / .3)
            if depth > .72:                                 # The near ones flare at the head.
                flicker = .75 + .25 * math.sin(t * 31 + at * 17)
                light(p, f'sparkle_{key}', head, h * .05 * depth * flicker, alpha * .8, angle=angle * .2)

    def _destined_path(self, index, f):
        """Point on its curved path down to her hand, and its heading in degrees."""
        w, h = self.width(), self.height()
        rng = random.Random(index * 13 + 5)
        start = QPointF(w * rng.uniform(.80, 1.06), -h * rng.uniform(.02, .12))
        end = self.hand()
        mid = (start + end) * .5
        bend = QPointF(-(end.y() - start.y()), end.x() - start.x()) * (rng.uniform(.18, .3) * (1 if index % 2 else -1))
        control = mid + bend
        a, b, c = (1 - f) ** 2, 2 * (1 - f) * f, f * f
        point = start * a + control * b + end * c
        tangent = (control - start) * (2 * (1 - f)) + (end - control) * (2 * f)
        return point, math.degrees(math.atan2(tangent.y(), tangent.x()))

    def _paint_destined(self, p, index):
        """Its star coming down: a curving comet in its rarity's colour."""
        t, h = self.t, self.height()
        at = self.catch[index]
        if not at - self.travel <= t < at:
            return
        rarity, rank = self.rarity(index), self.rank(index)
        f = _ease((t - (at - self.travel)) / self.travel)
        head, angle = self._destined_path(index, f)
        for k in range(1, 22):                              # Its curved trail of light.
            g = f - k * .018
            if g <= 0:
                break
            point, _ = self._destined_path(index, g)
            light(p, f'sparkle_{rarity}', point, h * (.05 - k * .0016) * (1 + rank * .12), (1 - k / 22) * .55)
        streak(p, f'meteor_{rarity}', head, angle, h * (.22 + .04 * rank), 1.0, grow=f / .25)
        size = h * (.07 + .025 * rank)
        light(p, f'hero_{rarity}', head, size * 2.2, .9, angle=t * 60)
        light(p, f'sparkle_{rarity}', head, size, 1.0)

    def _paint_burst(self, p, index):
        """The catch: a flash, a shock ring, god rays, a lens streak and sparks."""
        t = self.t - self.catch[index]
        if not 0 <= t <= 1.6:
            return
        h, w = self.height(), self.width()
        rarity, rank = self.rarity(index), self.rank(index)
        strength = (1 + rank) / 5 * (1.0 if not self.ten or index == self.best else .45)
        centre = self.hand()
        light(p, f'hero_{rarity}', centre, h * (.14 + .24 * strength) * _out(t / .2), (1 - _ease(t / .6)) * .85)
        light(p, f'shock_{rarity}', centre, h * (.15 + 1.1 * strength) * _out(t / .9), (1 - _ease(t / 1.0)) * (.3 + .6 * strength))
        light(p, f'rays_{rarity}', centre, h * (.5 + .8 * strength), (1 - _ease(t / 1.2)) * (.35 + .5 * strength),
              angle=t * 25 + index * 40)
        light(p, 'flare_gold' if rarity == 'haori' else 'flare', centre, w * (.4 + .5 * strength),
              (1 - _ease(t / .8)) * (.5 + .5 * strength))
        if index not in self.sparks:
            rng = random.Random(index * 7 + 1)
            self.sparks[index] = [(rng.uniform(0, math.tau), rng.uniform(.25, 1.0), rng.uniform(.6, 1.4),
                                   rng.random()) for _ in range(int(24 + 40 * strength))]
        for angle, speed, size, kind in self.sparks[index]:
            d = h * (.18 + .38 * strength) * speed * _out(t / 1.3)
            q = centre + QPointF(math.cos(angle) * d, math.sin(angle) * d + h * .05 * t * t)
            key = rarity if kind < .7 else SHOWER[int(kind * 10) % 4]
            light(p, f'sparkle_{key}', q, h * .045 * size * (1 - t / 1.6), (1 - _ease(t / 1.6)))

    def _star_look(self, p, rarity, centre, width, alpha, t):
        """A find's light, alive: each rarity moves in its own way."""
        if rarity == 'fanxing':                             # A twinkle that turns a little.
            light(p, 'hero_fanxing', centre, width, alpha, angle=8 * math.sin(t * 1.3))
            light(p, 'hero_fanxing', centre, width * .7, alpha * .35 * (.5 + .5 * math.sin(t * 4)), angle=45)
        elif rarity == 'mingyue':                           # The moon flashes white.
            flash = .78 + .22 * max(0.0, math.sin(t * 3.2)) ** 6
            light(p, 'hero_mingyue', centre, width * (1.15 + .03 * flash), alpha * flash)
            light(p, 'sparkle_mingyue', centre, width * .5, alpha * (.3 + .7 * max(0.0, math.sin(t * 3.2)) ** 12))
        elif rarity == 'haori':                             # The sun's rays turn.
            light(p, 'rays_haori', centre, width * 1.3, alpha * .45, angle=-t * 12)
            light(p, 'hero_haori', centre, width, alpha, angle=t * 8)
        elif rarity == 'yinhe':                             # A tilted silver galaxy, turning.
            light(p, 'hero_yinhe', centre, width * 1.55, alpha, angle=t * 35, squash=.6, tilt=-18)
            light(p, 'sparkle_yinhe', centre, width * .35, alpha * .8)
        else:                                               # Prism star in turning rainbow rings.
            light(p, 'rays_xinghai', centre, width * 1.4, alpha * .35, angle=t * 10)
            light(p, 'hero_xinghai_ring', centre, width * 1.15, alpha * .9, angle=t * 50, squash=.62, tilt=-14)
            light(p, 'hero_xinghai_ring', centre, width * .8, alpha * .5, angle=-t * 70, squash=.9)
            light(p, 'hero_xinghai', centre, width, alpha * .7, angle=t * 6)

    def _paint_found(self, p):
        """One wish: the caught star rises from her hands, grows, then becomes the card."""
        t, h = self.t, self.height()
        at = self.catch[0]
        if not at <= t < self.flip0 + .3:
            return
        rarity, rank = self.rarity(0), self.rank(0)
        rise = _out((t - at) / .9)
        hand = self.hand()
        above = hand + QPointF(self.width() * .13, -h * .17) * rise
        width = h * (.06 + (.36 + .04 * rank) * rise)
        fly = _ease((t - (self.flip0 - .55)) / .55)
        centre, (cw, ch) = self.slot(0)
        point = above + (centre - above) * fly
        width = _lerp(width, cw * 2.2, fly)
        self._star_look(p, rarity, point, width, _ease((t - at - .1) / .35) * (1 - .5 * _ease((t - self.flip0) / .3)), t)

    def _orbit_point(self, k, t):
        pos, size, lean, left = self.her_place()
        angle = k * math.tau / 10 + t * .9
        return QPointF(pos.x() + math.cos(angle) * size * .72, pos.y() - size * .08 + math.sin(angle) * size * .2), \
            math.sin(angle)

    def _paint_orbit(self, p, behind):
        """Ten wishes: each caught star circles her until the cards come."""
        t, h = self.t, self.height()
        for k, index in enumerate(self.order):
            at = self.catch[index]
            if t < at:
                continue
            point, depth = self._orbit_point(k, t)
            settle = _out((t - at) / .4)
            point = self.hand() + (point - self.hand()) * settle
            fly = _ease((t - (self.flip0 - .6)) / .6)
            if fly > 0:                                     # To its card.
                centre, (cw, ch) = self.slot(k)
                point = point + (centre - point) * fly
                depth = 1.0
            if (depth < 0) != behind:
                continue
            rarity, rank = self.rarity(index), self.rank(index)
            width = h * (.09 + .02 * rank) * (1 + fly * 1.2)
            dim = .55 if depth < 0 else 1.0
            fade = 1 - _ease((t - self.flip0 - k * .12) / .3)
            if fade > 0:
                self._star_look(p, rarity, point, width, dim * fade, t + k)

    def _paint_her(self, p):
        pos, size, lean, facing_left = self.her_place()
        if pos.x() < -size:
            return
        name = self.pose_name()
        sprite = self.pose(name, size if not self.ten else self.height() * .34)
        if sprite is None:
            return
        p.setCompositionMode(QPainter.CompositionMode_Plus)    # Her own soft light, and a stardust wake.
        light(p, 'sparkle_lavender', pos, size * 1.3, .35)
        for k in range(14):
            back = (self.t - k * .05)
            if back < .7:
                break
            was = self._wake_point(back)
            light(p, f'sparkle_{SHOWER[k % 4]}', was, size * (.16 - k * .009), .5 * (1 - k / 14))
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        sw = sprite.width() / sprite.devicePixelRatio() * size / (sprite.height() / sprite.devicePixelRatio())
        p.save()
        p.translate(pos)
        p.rotate(lean)
        if facing_left:
            p.scale(-1, 1)
        p.setOpacity(_ease((self.t - .7) / .3))
        p.drawPixmap(QRectF(-sw / 2, -size / 2, sw, size), sprite, QRectF(sprite.rect()))
        p.restore()

    def _wake_point(self, t):
        """Where she was at time ``t`` (her stardust wake), offset to around her waist."""
        now = self.t
        self.t = t
        pos, size, lean, left = self.her_place()
        self.t = now
        return pos + QPointF(0, size * .18)

    def _paint_card_lights(self, p):
        """Behind each turned card, its star keeps shining."""
        for k, index in enumerate(self.order if self.ten else [0]):
            flip = self.flip0 + (k * .12 if self.ten else 0)
            f = _ease((self.t - flip) / .5)
            if f <= 0:
                continue
            centre, (cw, ch) = self.slot(k)
            rank = self.rank(index)
            self._star_look(p, self.rarity(index), centre, max(cw, ch) * (1.5 + .15 * rank), f * (.35 + .12 * rank),
                            self.t + k)

    def _paint_cards(self, p):
        for k, index in enumerate(self.order if self.ten else [0]):
            flip = self.flip0 + (k * .12 if self.ten else 0)
            f = (self.t - flip) / .45
            if f <= 0:
                continue
            centre, (cw, ch) = self.slot(k)
            self._card(p, index, centre, cw, ch, f)

    def _card(self, p, index, centre, cw, ch, f):
        from shop_view import draw_item, item_name
        result = self.results[index]
        item = result['item']
        colour = self.colour(index)
        rank = self.rank(index)
        flipped = max(.02, abs(math.cos(math.pi * (1 - _back(min(1.0, f))) / 2)) if f < 1 else 1.0)
        p.save()
        p.translate(centre)
        p.scale(flipped, 1.0)
        box = QRectF(-cw / 2, -ch / 2, cw, ch)
        inside = QLinearGradient(box.topLeft(), box.bottomRight())
        inside.setColorAt(0, QColor(22, 18, 58, 235))
        inside.setColorAt(1, QColor(colour.red() // 4 + 14, colour.green() // 4 + 12, colour.blue() // 4 + 40, 235))
        if rank == 4:                                       # Starsea: an iridescent frame that turns.
            frame = QConicalGradient(QPointF(0, 0), self.t * 80)
            for k in range(7):
                frame.setColorAt(k / 6, QColor.fromHsvF((k / 6 + self.t * .2) % 1, .55, 1))
            pen = QPen(frame, 3.5)
        elif rank == 3:                                     # Galaxy: silver flowing along the frame.
            shift = (self.t * .6) % 2 - .5
            frame = QLinearGradient(box.topLeft(), box.bottomRight())
            for stop, value in ((0, .45), (max(0, min(1, shift - .18)), .55), (max(0, min(1, shift)), 1.0),
                                (max(0, min(1, shift + .18)), .55), (1, .45)):
                frame.setColorAt(stop, QColor.fromRgbF(.62 + .38 * value, .68 + .32 * value, .82 + .18 * value))
            pen = QPen(frame, 3.2)
        elif rank == 1:                                     # Moon: white that flashes.
            flash = .8 + .2 * max(0.0, math.sin(self.t * 3.2)) ** 6
            pen = QPen(QColor.fromRgbF(flash, flash, 1.0), 2.4 + 1.6 * flash)
        else:
            pen = QPen(colour, 3)
        p.setPen(pen)
        p.setBrush(inside)
        p.drawRoundedRect(box, 16, 16)
        s = min(cw, ch)
        draw_item(p, item, QRectF(-s * .34, -ch * .44, s * .68, s * .58), colour)
        p.setPen(QColor('#FFFFFF'))
        p.setFont(QFont('Microsoft YaHei UI', max(9, int(ch * .075)), QFont.Bold))
        p.drawText(QRectF(-cw / 2, ch * .08, cw, ch * .14), Qt.AlignCenter, item_name(item, self.language))
        label = text(f'shop_rarity_{item["rarity"]}', self.language)
        pill = QRectF(-cw * .3, ch * .24, cw * .6, ch * .11)
        p.setPen(Qt.NoPen)
        p.setBrush(_rgba(colour, 90))
        p.drawRoundedRect(pill, pill.height() / 2, pill.height() / 2)
        p.setPen(QColor('#FFFFFF'))
        p.setFont(QFont('Microsoft YaHei UI', max(8, int(ch * .055)), QFont.DemiBold))
        p.drawText(pill, Qt.AlignCenter, label)
        if result['refund']:
            p.setPen(QColor(220, 215, 255))
            p.setFont(QFont('Microsoft YaHei UI', max(7, int(ch * .045))))
            p.drawText(QRectF(-cw / 2, ch * .37, cw, ch * .1), Qt.AlignCenter,
                       text('shop_refund', self.language, points=result['refund']))
        shine = (f - 1) / .7                                # A gleam sweeps across once.
        if 0 < shine < 1:
            x = -cw + 2 * cw * shine
            g = QLinearGradient(QPointF(x - cw * .2, -ch / 2), QPointF(x + cw * .2, ch / 2))
            g.setColorAt(0, QColor(255, 255, 255, 0))
            g.setColorAt(.5, QColor(255, 255, 255, 90))
            g.setColorAt(1, QColor(255, 255, 255, 0))
            path = QPainterPath()
            path.addRoundedRect(box, 16, 16)
            p.setClipPath(path)
            p.fillRect(box, g)
        p.restore()
