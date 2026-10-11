"""The wishing show (2.5): shooting stars cross the night sky and she catches one
(a single wish) or a whole shower of them (ten wishes). Each star burns in its
rarity's colour, turns into a light in her hands, then into the card of what
she found. A click skips to the cards; another closes.

Rarity colours: Starsea iridescent, Galaxy flowing silver, Sun warm gold,
Moon flashing white, Stars deep blue (shop_view.rarity_colour).
"""
from __future__ import annotations

import math
import random

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QFont, QLinearGradient, QPainter, QPainterPath, QPen,
                           QPolygonF, QRadialGradient)
from PySide6.QtWidgets import QWidget

import shop
from localization import text


def _ease(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def _back(x, s=1.7):
    x = max(0.0, min(1.0, x)) - 1
    return x * x * ((s + 1) * x + s) + 1


def _lerp(a, b, f):
    return a + (b - a) * f


def _rgba(colour, alpha):
    return QColor(colour.red(), colour.green(), colour.blue(), max(0, min(255, int(alpha))))


def _crystal(p, c, r, colour, alpha=1.0, core=True):
    """A four-point crystal star, like the task stars."""
    p.setPen(Qt.NoPen)
    glow = QRadialGradient(c, r * 2.8)
    glow.setColorAt(0, _rgba(colour, 170 * alpha))
    glow.setColorAt(1, _rgba(colour, 0))
    p.setBrush(glow)
    p.drawEllipse(c, r * 2.8, r * 2.8)
    p.setBrush(_rgba(QColor(255, 255, 255), 250 * alpha) if core else _rgba(colour, 230 * alpha))
    p.drawPolygon(QPolygonF([c + QPointF(0, -r * 1.7), c + QPointF(r * .38, -r * .38), c + QPointF(r * 1.7, 0),
                             c + QPointF(r * .38, r * .38), c + QPointF(0, r * 1.7), c + QPointF(-r * .38, r * .38),
                             c + QPointF(-r * 1.7, 0), c + QPointF(-r * .38, -r * .38)]))


class WishShow(QWidget):
    FPS_MS = 25

    def __init__(self, parent, results, language, starsea=False):
        super().__init__(parent, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.results, self.language, self.starsea = results, language, starsea
        self.ten = len(results) > 1
        self.t = 0.0
        if parent is not None:
            self.setGeometry(parent.geometry())
        else:
            self.resize(1000, 640)
        self.rng = random.Random(len(results) * 31 + sum(map(ord, results[0]['item']['id'])))
        rng = self.rng
        self.stars = [(rng.random(), rng.random(), rng.choice((.6, 1.0, 1.6)), rng.random() * 6.3, rng.choice((0, 1, 2)))
                      for _ in range(280)]
        self.band = [(rng.gauss(0, .07), rng.random(), rng.random() * 6.3) for _ in range(420)]
        self.nebula = [((.22, .3), (120, 80, 220), .55), ((.74, .22), (60, 110, 230), .5),
                       ((.55, .7), (210, 90, 180), .45), ((.12, .78), (60, 180, 200), .38)]
        self.ambient = []                                   # Thin shooting stars that just pass by.
        at = .3
        while at < 12:
            self.ambient.append((at, rng.uniform(.25, 1.1), rng.uniform(-.1, .5), rng.uniform(.5, .9)))
            at += rng.uniform(.35, .9)
        best = max(range(len(results)), key=lambda i: shop.RARITIES.index(results[i]['item']['rarity']))
        others = sorted((i for i in range(len(results)) if i != best),
                        key=lambda i: shop.RARITIES.index(results[i]['item']['rarity']))
        self.order = others + [best]                        # The best one comes last.
        self.best = best
        if self.ten:
            self.catch = {i: 1.5 + k * .24 + (.35 if i == best else 0) for k, i in enumerate(self.order)}
            self.flip0 = max(self.catch.values()) + 1.1
            self.length = self.flip0 + 10 * .12 + 1.4
        else:
            self.catch = {0: 2.3}
            self.flip0 = 3.4
            self.length = 5.0
        self.bursts = {}
        self.sprite = self._sprite()
        self.timer = QTimer(self)
        self.timer.setInterval(self.FPS_MS)
        self.timer.timeout.connect(self._step)
        self.timer.start()

    # Setup ------------------------------------------------------------------------------
    def _sprite(self):
        import pet_assets
        for pose in (('star_celebrate',) if self.starsea else ()) + ('celebrate', 'idle'):
            pixmap = pet_assets.frame_for(pose, 0) if pet_assets.frame_count(pose) else pet_assets.sprite_for(pose)
            if pixmap is not None and not pixmap.isNull():
                return pixmap
        return None

    def colour(self, index, t=None):
        from shop_view import rarity_colour
        return rarity_colour(self.results[index]['item']['rarity'], self.t if t is None else t, index / 10)

    def rank(self, index):
        return shop.RARITIES.index(self.results[index]['item']['rarity'])

    def _step(self):
        self.t += self.FPS_MS / 1000
        self.update()

    def mousePressEvent(self, event):
        if self.t < self.length - .6:
            self.t = self.length - .6                       # Straight to the cards.
        else:
            self.close()

    def keyPressEvent(self, event):
        self.mousePressEvent(event)

    # Layout -----------------------------------------------------------------------------
    def her_place(self):
        """Her position (centre) and size at the current time."""
        w, h, t = self.width(), self.height(), self.t
        size = h * (.42 if not self.ten else .34)
        enter = _ease((t - .2) / 1.0)
        if not self.ten:
            start, rest = QPointF(-.1 * w, h * 1.0), QPointF(w * .3, h * .62)
        else:
            start, rest = QPointF(w * .5, h * 1.25), QPointF(w * .5, h * .66)
        pos = start + (rest - start) * enter
        if self.ten:                                        # Aside for the cards.
            aside = _ease((t - (self.flip0 - .7)) / .7)
            pos = pos + (QPointF(w * .87, h * .78) - pos) * aside
            size *= 1 - .4 * aside
        bob = math.sin(t * 2.1) * h * .008
        reach = 0.0
        for at in self.catch.values():                      # She reaches up as a star arrives.
            reach = max(reach, math.exp(-((t - at) / .22) ** 2))
        return QPointF(pos.x(), pos.y() + bob - reach * h * .03), size

    def hand(self):
        pos, size = self.her_place()
        return QPointF(pos.x() + size * .34, pos.y() - size * .24)       # Her raised hand, beside her face.

    def slot(self, k):
        """Where card ``k`` sits."""
        w, h = self.width(), self.height()
        if not self.ten:
            return QPointF(w * .64, h * .46), (w * .26, h * .52)
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
        self._sky(p)
        for at, x0, y0, length in self.ambient:
            self._ambient_meteor(p, at, x0, y0, length)
        if self.results[self.best]['item']['rarity'] == 'xinghai':
            self._starsea_tint(p)
        self._her(p)
        for index in self.order:
            self._destined(p, index)
        self._cards(p)
        for at, centre, colour, strength in list(self.bursts.values()):
            self._burst(p, at, centre, colour, strength)
        if self.t > self.length - .9:
            p.setPen(QColor(220, 220, 255, int(200 * _ease((self.t - self.length + .9) / .4))))
            p.setFont(QFont('Microsoft YaHei UI', 10))
            p.drawText(QRectF(0, self.height() - 44, self.width(), 26), Qt.AlignCenter,
                       text('shop_wish_close', self.language))

    def _sky(self, p):
        w, h, t = self.width(), self.height(), self.t
        fade = _ease(t / .45)
        g = QLinearGradient(0, 0, 0, h)
        g.setColorAt(0, QColor(5, 6, 26))
        g.setColorAt(.6, QColor(16, 12, 46))
        g.setColorAt(1, QColor(30, 18, 64))
        p.setOpacity(fade)
        p.fillRect(self.rect(), g)
        p.setPen(Qt.NoPen)
        for (cx, cy), rgb, size in self.nebula:              # Soft drifting nebulae.
            c = QPointF(w * (cx + .02 * math.sin(t * .3 + cx * 9)), h * (cy + .02 * math.cos(t * .25 + cy * 7)))
            r = max(w, h) * size * .6
            neb = QRadialGradient(c, r)
            neb.setColorAt(0, QColor(*rgb, 46))
            neb.setColorAt(.5, QColor(*rgb, 18))
            neb.setColorAt(1, QColor(*rgb, 0))
            p.setBrush(neb)
            p.drawEllipse(c, r, r)
        p.save()                                            # A faint Milky Way.
        p.translate(w * .5, h * .4)
        p.rotate(-24)
        band = QLinearGradient(0, -h * .16, 0, h * .16)
        band.setColorAt(0, QColor(200, 190, 255, 0))
        band.setColorAt(.5, QColor(210, 200, 255, 34))
        band.setColorAt(1, QColor(200, 190, 255, 0))
        p.fillRect(QRectF(-w, -h * .16, w * 2, h * .32), band)
        for dy, dx, phase in self.band:
            a = 60 + 70 * math.sin(t * 1.4 + phase)
            p.setBrush(QColor(235, 230, 255, int(max(0, a))))
            p.drawEllipse(QPointF((dx * 2 - 1) * w, dy * h * 1.6), .9, .9)
        p.restore()
        for x, y, size, phase, layer in self.stars:          # Three layers, the near ones drift.
            drift = (t * (.004, .009, .016)[layer]) % 1.0
            a = .45 + .55 * max(0.0, math.sin(t * (1.2 + layer * .6) + phase))
            p.setBrush(QColor(225, 230, 255, int(210 * a)))
            point = QPointF(((x - drift) % 1.0) * w, y * h * .92)
            p.drawEllipse(point, size * .7, size * .7)
            if size > 1.4 and a > .9:
                _crystal(p, point, 1.6, QColor(200, 210, 255), (a - .9) * 8)
        p.setOpacity(1)

    def _ambient_meteor(self, p, at, x0, y0, length):
        t = self.t - at
        life = .85
        if not 0 <= t <= life:
            return
        w, h = self.width(), self.height()
        f = t / life
        heading = QPointF(-.82, .57)
        head = QPointF(w * x0, h * y0) + heading * (w * .7 * f)
        tail = head - heading * (w * .16 * length)
        fade = math.sin(math.pi * f)
        g = QLinearGradient(tail, head)
        g.setColorAt(0, QColor(190, 210, 255, 0))
        g.setColorAt(1, QColor(240, 245, 255, int(200 * fade)))
        pen = QPen(QBrush(g), 1.6)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.drawLine(tail, head)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, int(220 * fade)))
        p.drawEllipse(head, 1.6, 1.6)

    def _starsea_tint(self, p):
        """A Starsea find washes the sky in shifting colours as it arrives."""
        at = self.catch[self.best]
        a = math.exp(-((self.t - at + .2) / .9) ** 2) * .5
        if a < .01:
            return
        g = QLinearGradient(0, 0, self.width(), self.height())
        for k in range(5):
            g.setColorAt(k / 4, QColor.fromHsvF((k / 4 * .8 + self.t * .2) % 1, .55, 1, a * .35))
        p.fillRect(self.rect(), g)

    def _her(self, p):
        if self.sprite is None:
            return
        pos, size = self.her_place()
        glow = QRadialGradient(pos, size * .7)
        glow.setColorAt(0, QColor(170, 150, 255, 90))
        glow.setColorAt(1, QColor(170, 150, 255, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(glow)
        p.drawEllipse(pos, size * .7, size * .7)
        scale = size / self.sprite.height()
        sw, sh = self.sprite.width() * scale, size
        p.setOpacity(_ease((self.t - .2) / .4))
        p.drawPixmap(QRectF(pos.x() - sw / 2, pos.y() - sh / 2, sw, sh), self.sprite, QRectF(self.sprite.rect()))
        p.setOpacity(1)

    def _destined(self, p, index):
        """The star that becomes this find: a meteor down to her hand, then a light
        that flies to its card."""
        w, h, t = self.width(), self.height(), self.t
        at = self.catch[index]
        travel = .9 if not self.ten else .7
        colour = self.colour(index)
        rank = self.rank(index)
        hand = self.hand()
        if t < at - travel:
            return
        if t < at:                                          # Falling towards her.
            f = _ease((t - (at - travel)) / travel)
            rng = random.Random(index * 13 + 5)
            start = QPointF(w * rng.uniform(.75, 1.08), h * rng.uniform(-.1, .12))
            head = start + (hand - start) * f
            direction = hand - start
            length = math.hypot(direction.x(), direction.y()) or 1
            unit = QPointF(direction.x() / length, direction.y() / length)
            tail = head - unit * (w * (.18 + .05 * rank))
            g = QLinearGradient(tail, head)
            g.setColorAt(0, _rgba(colour, 0))
            g.setColorAt(.7, _rgba(colour, 140))
            g.setColorAt(1, QColor(255, 255, 255, 240))
            for width, alpha in ((14 + rank * 3, .25), (5 + rank, .6), (2.2, 1.0)):
                pen = QPen(QBrush(g), width)
                pen.setCapStyle(Qt.RoundCap)
                p.setOpacity(alpha)
                p.setPen(pen)
                p.drawLine(tail, head)
            p.setOpacity(1)
            for k in range(6):                              # Sparks shed behind it.
                q = head - unit * (w * .03 * (k + 1)) + QPointF(rng.uniform(-6, 6), rng.uniform(-6, 6))
                p.setPen(Qt.NoPen)
                p.setBrush(_rgba(colour, 200 * (1 - k / 6)))
                p.drawEllipse(q, 1.6, 1.6)
            _crystal(p, head, 5 + rank * 1.3, colour)
            return
        if index not in self.bursts:                        # Caught: a flash at her hand.
            self.bursts[index] = (at, QPointF(hand), colour, (1 + rank) / 5)
        flip = self.flip0 + (self.order.index(index) * .12 if self.ten else 0)
        if t < flip:                                        # A light in her hands, then to its card.
            # Ten: each light goes to its card at once and waits there; one: at the end.
            fly = _ease((t - (at + .15)) / .5) if self.ten else _ease((t - (flip - .55)) / .55)
            centre, (cw, ch) = self.slot(self.order.index(index) if self.ten else 0)
            target = centre if self.ten else centre
            orb = hand + (target - hand) * fly
            pulse = 1 + .15 * math.sin(t * 9 + index)
            radius = (10 + rank * 3) * pulse * (1 + fly * (.6 if not self.ten else .2))
            if rank == 4:
                rays = QConicalGradient(orb, t * 120)
                for k in range(7):
                    rays.setColorAt(k / 6, QColor.fromHsvF((k / 6 + t * .3) % 1, .65, 1, .5))
                p.setPen(Qt.NoPen)
                p.setBrush(rays)
                p.drawEllipse(orb, radius * 3.2, radius * 3.2)
            _crystal(p, orb, radius, colour)

    def _burst(self, p, at, centre, colour, strength):
        t = self.t - at
        if not 0 <= t <= 1.4:
            return
        a = 1 - t / 1.4
        ring = self.height() * (.08 + .5 * strength) * _ease(t / .6)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(_rgba(colour, 200 * a * a), 3 + 4 * strength))
        p.drawEllipse(centre, ring, ring * .92)
        flash = QRadialGradient(centre, self.height() * (.15 + .3 * strength))
        flash.setColorAt(0, _rgba(QColor(255, 255, 255), 170 * max(0.0, 1 - t / .3)))
        flash.setColorAt(.4, _rgba(colour, 140 * max(0.0, 1 - t / .5)))
        flash.setColorAt(1, _rgba(colour, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(flash)
        p.drawEllipse(centre, self.height() * (.15 + .3 * strength), self.height() * (.15 + .3 * strength))
        rng = random.Random(int(at * 1000))
        for k in range(int(18 + 50 * strength)):            # Sparks flying out.
            angle = rng.uniform(0, math.tau)
            speed = rng.uniform(.3, 1.0) * self.height() * (.25 + .35 * strength)
            d = speed * (1 - (1 - min(1.0, t / 1.2)) ** 2)
            q = centre + QPointF(math.cos(angle) * d, math.sin(angle) * d + 30 * t * t)
            p.setBrush(_rgba(colour if k % 3 else QColor(255, 255, 255), 230 * a))
            p.drawEllipse(q, 1.2 + 1.6 * strength * a, 1.2 + 1.6 * strength * a)

    def _cards(self, p):
        for k, index in enumerate(self.order if self.ten else [0]):
            flip = self.flip0 + (k * .12 if self.ten else 0)
            f = (self.t - flip) / .45
            if f <= 0:
                continue
            centre, (cw, ch) = self.slot(k)
            self._card(p, index, centre, cw, ch, f)

    def _card(self, p, index, centre, cw, ch, f):
        from shop_view import glyph
        result = self.results[index]
        item = result['item']
        colour = self.colour(index)
        rank = self.rank(index)
        flipped = max(.02, abs(math.cos(math.pi * (1 - _back(min(1.0, f))) / 2)) if f < 1 else 1.0)
        p.save()
        p.translate(centre)
        p.scale(flipped, 1.0)
        box = QRectF(-cw / 2, -ch / 2, cw, ch)
        for k in range(4):                                  # Its light around the frame.
            p.setPen(QPen(_rgba(colour, (60 - k * 14) * (1 + rank * .3)), 6 + k * 5))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(box, 16, 16)
        inside = QLinearGradient(box.topLeft(), box.bottomRight())
        inside.setColorAt(0, QColor(28, 22, 70))
        inside.setColorAt(1, QColor(colour.red() // 4 + 18, colour.green() // 4 + 14, colour.blue() // 4 + 46))
        if rank == 4:
            frame = QConicalGradient(QPointF(0, 0), self.t * 80)
            for k in range(7):
                frame.setColorAt(k / 6, QColor.fromHsvF((k / 6 + self.t * .2) % 1, .55, 1))
            pen = QPen(QBrush(frame), 3.5)
        elif rank == 3:
            frame = QLinearGradient(box.topLeft() + QPointF(math.sin(self.t * 2) * cw, 0), box.bottomRight())
            frame.setColorAt(0, QColor(150, 160, 190))
            frame.setColorAt(.5, QColor(250, 252, 255))
            frame.setColorAt(1, QColor(150, 160, 190))
            pen = QPen(QBrush(frame), 3.2)
        else:
            pen = QPen(colour, 3)
        p.setPen(pen)
        p.setBrush(inside)
        p.drawRoundedRect(box, 16, 16)
        s = min(cw, ch)
        glyph(p, item['slot'], QRectF(-s * .26, -ch * .38, s * .52, s * .52), colour)
        p.setPen(QColor('#FFFFFF'))
        p.setFont(QFont('Microsoft YaHei UI', max(9, int(ch * .075)), QFont.Bold))
        from shop_view import item_name
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
