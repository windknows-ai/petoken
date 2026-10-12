"""Drawing a featured item's discount (2.5): a card draw like a mystery shop.

Six cards fly out face down and are shuffled; you pick one; it rises, turns and bursts to
show today's discount. What it shows is drawn by the shop the moment you pick
(shop.Shop.draw_discount), so the odds are exactly the shop's; the cards are only the
moment of finding out. 7 or better (a 30 % or larger discount) gets the gold burst.
"""
from __future__ import annotations

import math
import random

from PySide6.QtCore import QEvent, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

import shop
from localization import text
from wish_show import (FX_DIR, _POOL, _back, _ease, _out, _rgba, _scaled_card, light, play, play_loop, preload,
                       release)

CARDS = 6
GREAT = .7


def discount_text(value):
    """0.75 -> '7.5', 0.7 -> '7'."""
    tenth = round(value * 10, 1)
    return f'{tenth:g}'


class DiscountDraw(QWidget):
    FPS_MS = 16

    def __init__(self, parent, item, draw, language, sound=False, on_sound=None, on_done=None):
        self.host = parent.window() if parent is not None else None
        if self.host is not None:
            super().__init__(self.host)
            self.setGeometry(self.host.overlay_rect() if hasattr(self.host, "overlay_rect") else self.host.rect())
            self.host.installEventFilter(self)
        else:
            super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
            self.resize(1000, 640)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.item, self.draw, self.language, self.on_done = item, draw, language, on_done
        # The window behind, as a picture: drawn under the veil, so the show covers it solidly. A
        # see-through veil let the light-on-black bursts (drawn adding light, alpha too) punch an
        # opaque dark box into it.
        view = getattr(self.host, 'view', None)
        self._behind = view.grabFramebuffer() if view is not None else None
        self.t = 0.0
        self.rng = random.Random(hash(item['id']) & 0xffff)
        self.slots = list(range(CARDS))                     # Card k sits at slot self.slots[k].
        self.swaps = self._plan_swaps()
        self.hover = None
        self.picked = None
        self.picked_at = None
        self.value = None
        self.pointer = None
        for name in ('emblem_' + item['rarity'], 'reveal_haori', 'reveal_mingyue'):
            preload(name)
        self._frames = {}
        from wish_sound import Sounds
        self.sounds = Sounds(sound)
        self.on_sound = on_sound
        self.sounds.play('shuffle')
        self.frame(*self.card_size())                       # Its frame scaled now, before the first paint.
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.setInterval(self.FPS_MS)
        self.timer.timeout.connect(self._step)
        self.timer.start()
        self._last = None

    # Timeline ---------------------------------------------------------------------------
    ENTER = .5
    SWAP = .32

    def _plan_swaps(self):
        swaps = []
        for k in range(3):
            a, b = self.rng.sample(range(CARDS), 2)
            swaps.append((self.ENTER + k * (self.SWAP + .04), a, b))
        return swaps

    def ready(self):
        """Shuffled and waiting to be picked."""
        return self.t >= self.ENTER + len(self.swaps) * (self.SWAP + .04) and self.picked is None

    def _step(self):
        import time
        now = time.perf_counter()
        dt = min(.05, now - self._last) if self._last is not None else self.FPS_MS / 1000
        self._last = now
        self.advance(dt)
        self.update()

    def advance(self, dt):
        self.t += dt
        if self.pointer is not None and self.ready():
            self.hover = self.card_at(self.pointer)

    # Layout -----------------------------------------------------------------------------
    def card_size(self):
        w, h = self.width(), self.height()
        ch = min(h * .42, w * .12 * 2.4)
        return ch / 2.4, ch

    def slot_point(self, slot):
        w, h = self.width(), self.height()
        cw, ch = self.card_size()
        gap = cw * .22
        x0 = w / 2 - (CARDS - 1) / 2 * (cw + gap)
        arc = abs(slot - (CARDS - 1) / 2) ** 2 * h * .008       # A slight fan.
        return QPointF(x0 + slot * (cw + gap), h * .56 + arc)

    def card_place(self, k):
        """Centre, scale, turn (0 face down .. 1 face up), angle and opacity of card ``k``."""
        t, h = self.t, self.height()
        cw, ch = self.card_size()
        start = QPointF(self.width() / 2, h * .62)
        slot = k
        point = None
        for at, a, b in self.swaps:                         # Swaps exchange the cards at two places.
            if t < at:
                break
            if slot in (a, b):
                target = b if slot == a else a
                f = _ease((t - at) / self.SWAP)
                if f < 1:                                   # On its way: one arcs over, the other under.
                    here, there = self.slot_point(slot), self.slot_point(target)
                    lift = math.sin(math.pi * f) * h * .08 * (1 if slot == a else -1)
                    point = here + (there - here) * f + QPointF(0, -lift)
                    break
                slot = target
        if point is None:
            point = self.slot_point(slot)
        enter = _out((t - k * .05) / .45)
        point = start + (point - start) * enter
        angle = (slot - (CARDS - 1) / 2) * 4 * enter
        scale, turn, alpha = 1.0, 0.0, enter
        if self.ready() and self.hover == k:
            point += QPointF(0, -h * .03)
            scale = 1.06
        point += QPointF(0, math.sin(t * 2 + k) * h * .004)
        if self.picked is not None:
            p = t - self.picked_at
            if k == self.picked:
                f = _out(p / .35)
                centre = QPointF(self.width() / 2, h * .5)
                point = point + (centre - point) * f
                scale = _lerp(scale, 1.4, f)
                angle *= 1 - f
                turn = _ease((p - .4) / .35)
            else:
                alpha *= 1 - _ease(p / .35)
        return point, scale, turn, angle, alpha, slot

    def card_at(self, point):
        cw, ch = self.card_size()
        for k in sorted(range(CARDS), key=lambda k: -self.card_place(k)[0].y()):
            centre = self.card_place(k)[0]
            if abs(point.x() - centre.x()) < cw / 2 and abs(point.y() - centre.y()) < ch / 2:
                return k
        return None

    # Input --------------------------------------------------------------------------------
    def mouseMoveEvent(self, event):
        self.pointer = event.position()

    def mousePressEvent(self, event):
        point = event.position()
        if self.picked is None:
            if self.ready():
                k = self.card_at(point)
                if k is not None:
                    self.pick(k)
            return
        if self.t - self.picked_at > 1.0:
            self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape and (self.picked is None or self.t - self.picked_at > 1.0):
            self.close()

    def pick(self, k):
        self.picked, self.picked_at = k, self.t
        self.value = self.draw()                            # The shop draws it now: its odds, untouched.
        self.sounds.play('pick')
        QTimer.singleShot(580, lambda: self.sounds.play('discount_great' if self.great() else 'discount'))

    def great(self):
        return self.value is not None and self.value <= GREAT

    def eventFilter(self, obj, event):
        if obj is self.host and event.type() == QEvent.Resize:
            self.setGeometry(self.host.overlay_rect() if hasattr(self.host, "overlay_rect") else self.host.rect())
        return False

    def closeEvent(self, event):
        self.sounds.close()
        for name in ('reveal_haori', 'reveal_mingyue'):
            release(name)
        if self.host is not None:
            self.host.removeEventFilter(self)
        if self.on_done is not None:
            self.on_done(self.value)
        super().closeEvent(event)

    # Painting -----------------------------------------------------------------------------
    def frame(self, cw, ch):
        ratio = self.devicePixelRatioF()
        key = (int(cw * ratio), int(ch * ratio))
        if key not in self._frames:
            self._frames[key] = _POOL.submit(_scaled_card, str(FX_DIR / f'card_{self.item["rarity"]}.webp'),
                                             key[0], key[1], ratio)
        job = self._frames[key]
        return job.result() if job.done() else None

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        w, h, t = self.width(), self.height(), self.t
        behind = self._behind
        if behind is not None and not behind.isNull():
            ratio = behind.devicePixelRatio() or 1.0
            g = self.geometry()
            p.drawImage(QRectF(self.rect()), behind, QRectF(g.x() * ratio, g.y() * ratio, w * ratio, h * ratio))
            p.fillRect(self.rect(), QColor(4, 4, 16, int(215 * _ease(t / .3))))
            p.setCompositionMode(QPainter.CompositionMode_DestinationOver)
            p.fillRect(self.rect(), QColor(4, 4, 16))              # Wholly opaque underneath.
            p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        else:
            p.fillRect(self.rect(), QColor(4, 4, 16, int(215 * _ease(t / .3))))
        glow = QLinearGradient(0, h * .3, 0, h)
        glow.setColorAt(0, QColor(80, 60, 160, 0))
        glow.setColorAt(1, QColor(80, 60, 160, int(70 * _ease(t / .4))))
        p.fillRect(self.rect(), glow)
        self._paint_item(p)
        order = sorted(range(CARDS), key=lambda k: (k == self.picked, k == self.hover))
        for k in order:
            self._paint_card(p, k)
        self._paint_words(p)
        p.end()

    def _paint_item(self, p):
        from shop_view import draw_item, item_name, rarity_colour
        w, h = self.width(), self.height()
        fade = _ease(self.t / .4)
        if self.picked is not None:                         # The turned card takes the stage.
            fade *= 1 - _ease((self.t - self.picked_at) / .3)
        if fade <= .01:
            return
        p.setOpacity(fade)
        side = h * .15
        draw_item(p, self.item, QRectF(w / 2 - side / 2, h * .06, side, side), rarity_colour(self.item['rarity'], self.t))
        p.setPen(QColor(240, 236, 255))
        p.setFont(QFont('Microsoft YaHei UI', max(10, int(h * .022)), QFont.Bold))
        p.drawText(QRectF(0, h * .06 + side + 4, w, h * .04), Qt.AlignCenter, item_name(self.item, self.language))
        p.setOpacity(1)

    def _paint_card(self, p, k):
        point, scale, turn, angle, alpha, slot = self.card_place(k)
        if alpha <= .01:
            return
        cw, ch = self.card_size()
        flip = abs(math.cos(math.pi * turn))
        face_up = turn >= .5
        p.save()
        p.translate(point)
        p.rotate(angle)
        p.scale(scale * max(.02, flip), scale)
        p.setOpacity(alpha)
        box = QRectF(-cw / 2, -ch / 2, cw, ch)
        if face_up and self.picked == k:                    # Its burst behind it as it shows.
            p.setCompositionMode(QPainter.CompositionMode_Plus)
            shown = self.t - self.picked_at - .58
            play(p, 'reveal_haori' if self.great() else 'reveal_mingyue', QPointF(0, 0), ch * 1.6, shown)
            p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        frame = self.frame(cw, ch)
        if frame is not None:
            p.drawImage(box, frame, QRectF(frame.rect()))
        else:
            p.setPen(QPen(QColor(200, 190, 255), 2))
            p.setBrush(QColor(20, 16, 50))
            p.drawRoundedRect(box, cw * .1, cw * .1)
        self._alpha = alpha
        if not face_up:
            self._paint_back(p, k, cw, ch)
        else:
            self._paint_face(p, cw, ch)
        p.restore()

    def _paint_back(self, p, k, cw, ch):
        p.setCompositionMode(QPainter.CompositionMode_Plus)
        face = QPainterPath()
        face.addRoundedRect(QRectF(-cw * .45, -ch * .46, cw * .9, ch * .9), cw * .06, cw * .06)
        p.setClipPath(face)
        play_loop(p, 'emblem_' + self.item['rarity'], QPointF(0, -ch * .12), cw * 1.1, self.t + k * .3, .8 * self._alpha)
        if self.ready() and self.hover == k:
            light(p, 'flare', QPointF(0, -ch * .12), cw * 2.2, .5)
        p.setOpacity(self._alpha)
        p.setClipping(False)
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        p.setPen(QColor(255, 255, 255, 235))
        p.setFont(QFont('Georgia', max(14, int(ch * .1)), QFont.Bold))
        p.drawText(QRectF(-cw / 2, -ch * .22, cw, ch * .2), Qt.AlignCenter, '?')
        p.setFont(QFont('Microsoft YaHei UI', max(8, int(ch * .04)), QFont.Bold))
        p.drawText(QRectF(-cw * .4, ch * .205, cw * .8, ch * .12), Qt.AlignCenter, text('shop_draw_card', self.language))

    def _paint_face(self, p, cw, ch):
        value = discount_text(self.value or 1)
        great = self.great()
        gold = QLinearGradient(QPointF(0, -ch * .3), QPointF(0, ch * .05))
        if great:
            gold.setColorAt(0, QColor(255, 246, 200))
            gold.setColorAt(.5, QColor(255, 200, 80))
            gold.setColorAt(1, QColor(210, 130, 30))
        else:
            gold.setColorAt(0, QColor(255, 255, 255))
            gold.setColorAt(1, QColor(190, 200, 235))
        font = QFont('Georgia', max(16, int(min(ch * .14, cw * .36))), QFont.Bold)
        path = QPainterPath()
        path.addText(0, 0, font, value)
        bounds = path.boundingRect()
        unit_w = cw * .16
        path.translate(-bounds.center().x() - unit_w / 2, -ch * .12 - bounds.center().y())
        p.setPen(QPen(QColor(30, 20, 60, 220), max(2.0, ch * .008)))
        p.setBrush(gold)
        p.drawPath(path)
        p.setPen(QColor(255, 236, 190) if great else QColor(230, 232, 255))
        p.setFont(QFont('Microsoft YaHei UI', max(10, int(ch * .06)), QFont.Bold))
        p.drawText(QRectF(bounds.width() / 2 - unit_w / 2 + 2, -ch * .13, cw * .3, ch * .08), Qt.AlignLeft | Qt.AlignVCenter,
                   text('shop_discount_unit', self.language))
        price = self.item.get('price')
        if price:
            p.setPen(QColor('#FFFFFF'))
            p.setFont(QFont('Microsoft YaHei UI', max(7, int(min(ch * .03, cw * .085))), QFont.Bold))
            p.drawText(QRectF(-cw * .44, ch * .205, cw * .88, ch * .12), Qt.AlignCenter | Qt.TextWordWrap,
                       text('shop_discount_price', self.language, old=price, new=int(round(price * self.value))))

    def _paint_words(self, p):
        w, h = self.width(), self.height()
        p.setFont(QFont('Microsoft YaHei UI', max(10, int(h * .02))))
        if self.picked is None:
            if self.ready():
                p.setPen(QColor(232, 228, 255, 220))
                p.drawText(QRectF(0, h * .86, w, h * .05), Qt.AlignCenter, text('shop_draw_pick', self.language))
            return
        shown = self.t - self.picked_at
        if shown > 1.0:
            p.setPen(QColor(232, 228, 255, int(220 * _ease((shown - 1.0) / .3))))
            p.drawText(QRectF(0, h * .86, w, h * .05), Qt.AlignCenter, text('shop_draw_done', self.language))


def _lerp(a, b, f):
    return a + (b - a) * f
