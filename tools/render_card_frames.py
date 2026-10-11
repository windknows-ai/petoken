"""Renders the wishing show's result card frames, one per rarity (2.5, round 6).

    python tools/render_card_frames.py

A frame is everything on a card except the find's picture and words: a beveled metal border
in the rarity's metal, star filigree in the corners, a gem crest at the top, a nebula-textured
face tinted by the rarity with a glass sheen, rank stars and a metal-edged name plate.
Writes assets/v2_5/wish/card_<rarity>.webp (with transparency), 480 x 1152 (aspect 1 : 2.4).
"""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QGuiApplication, QImage, QLinearGradient, QPainter,
                           QPainterPath, QPen, QPolygonF, QRadialGradient)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'assets' / 'v2_5' / 'wish'
W, H = 480, 1152
METAL = dict(
    fanxing=[(.22, .3, .55), (.72, .82, 1), (.28, .38, .72), (.86, .92, 1), (.22, .3, .55)],
    mingyue=[(.5, .53, .64), (.98, .98, 1), (.62, .65, .78), (1, 1, 1), (.5, .53, .64)],
    haori=[(.5, .3, .06), (1, .88, .52), (.72, .47, .1), (1, .96, .72), (.5, .3, .06)],
    yinhe=[(.36, .4, .66), (.9, .94, 1), (.48, .56, .9), (.98, .99, 1), (.36, .4, .66)],
    xinghai=None,
)
TINT = dict(fanxing=(.25, .42, 1), mingyue=(.82, .88, 1), haori=(1, .66, .2), yinhe=(.62, .72, 1), xinghai=(.8, .55, 1))
GEM = dict(fanxing=(.3, .5, 1), mingyue=(.9, .95, 1), haori=(1, .7, .2), yinhe=(.7, .8, 1), xinghai=(.9, .5, 1))
RANK = dict(fanxing=1, mingyue=2, haori=3, yinhe=4, xinghai=5)


def colour(rgb, alpha=1.0):
    return QColor.fromRgbF(rgb[0], rgb[1], rgb[2], alpha)


def metal(rarity, a, b):
    """A metal gradient between two points (iridescent for Starsea)."""
    g = QLinearGradient(a, b)
    if METAL[rarity] is None:
        for k in range(9):
            g.setColorAt(k / 8, QColor.fromHsvF((k / 8 * .9 + .55) % 1, .35 if k % 2 else .15, 1))
    else:
        stops = METAL[rarity]
        for k, rgb in enumerate(stops):
            g.setColorAt(k / (len(stops) - 1), colour(rgb))
    return g


def star(cx, cy, r, inner=.28, points=4, turn=0.0):
    poly = QPolygonF()
    for k in range(points * 2):
        a = turn + math.pi * k / points - math.pi / 2
        rad = r if k % 2 == 0 else r * inner
        poly.append(QPointF(cx + math.cos(a) * rad, cy + math.sin(a) * rad))
    return poly


def face(p, rarity, box, radius, sky):
    path = QPainterPath()
    path.addRoundedRect(box, radius, radius)
    p.save()
    p.setClipPath(path)
    p.fillRect(box, QColor(8, 7, 22))
    if not sky.isNull():                                   # A piece of the night sky as its texture.
        rng = random.Random(len(rarity))
        sx = rng.randint(0, max(0, sky.width() - int(box.width() * 1.4)))
        piece = sky.copy(sx, 200, int(box.width() * 1.4), int(box.height() * 1.4))
        p.setOpacity(.9)
        p.drawImage(box, piece)
        p.setOpacity(1)
    tint = TINT[rarity]
    wash = QLinearGradient(box.topLeft(), box.bottomLeft())
    wash.setColorAt(0, colour(tint, .10))
    wash.setColorAt(.55, colour(tint, .18))
    wash.setColorAt(1, colour(tint, .55))
    p.fillRect(box, wash)
    glow = QRadialGradient(QPointF(box.center().x(), box.top() + box.height() * .36), box.width() * .7)
    glow.setColorAt(0, colour(tint, .34))
    glow.setColorAt(1, colour(tint, 0))
    p.fillRect(box, glow)
    rng = random.Random(7 + len(rarity))
    p.setPen(Qt.NoPen)
    for _ in range(140):                                   # Fine stars on the face.
        x, y = rng.uniform(box.left(), box.right()), rng.uniform(box.top(), box.bottom())
        r = rng.choice((.7, .9, 1.2, 1.6))
        p.setBrush(QColor(255, 255, 255, rng.randint(60, 200)))
        p.drawEllipse(QPointF(x, y), r, r)
        if r > 1.5:
            p.drawPolygon(star(x, y, r * 3.2, .2))
    vignette = QRadialGradient(box.center(), box.height() * .62)
    vignette.setColorAt(.55, QColor(0, 0, 0, 0))
    vignette.setColorAt(1, QColor(0, 0, 0, 170))
    p.fillRect(box, vignette)
    sheen = QLinearGradient(QPointF(box.left(), box.top()), QPointF(box.right(), box.top() + box.width() * 1.1))
    sheen.setColorAt(0, QColor(255, 255, 255, 0))
    sheen.setColorAt(.42, QColor(255, 255, 255, 0))
    sheen.setColorAt(.5, QColor(255, 255, 255, 34))
    sheen.setColorAt(.58, QColor(255, 255, 255, 0))
    sheen.setColorAt(1, QColor(255, 255, 255, 0))
    p.fillRect(box, sheen)
    p.restore()


def border(p, rarity, box, radius):
    """Three rings: a dark outline, the metal band with its bevel, a fine bright line inside."""
    a, b = box.topLeft(), box.bottomRight()
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(QColor(4, 4, 12, 230), 15))
    p.drawRoundedRect(box, radius, radius)
    p.setPen(QPen(QBrush(metal(rarity, a, b)), 11))
    p.drawRoundedRect(box, radius, radius)
    p.setPen(QPen(QColor(255, 255, 255, 120), 2))           # Bevel highlight on the outer edge.
    p.drawRoundedRect(box.adjusted(-4.5, -4.5, 4.5, 4.5), radius + 4, radius + 4)
    p.setPen(QPen(QColor(0, 0, 0, 120), 2))                 # Bevel shadow on the inner edge.
    p.drawRoundedRect(box.adjusted(4.5, 4.5, -4.5, -4.5), radius - 4, radius - 4)
    inner = box.adjusted(16, 16, -16, -16)
    p.setPen(QPen(QBrush(metal(rarity, inner.bottomRight(), inner.topLeft())), 2.2))
    p.drawRoundedRect(inner, radius * .6, radius * .6)


def corners(p, rarity, box):
    m = metal(rarity, box.topLeft(), box.bottomRight())
    for sx, sy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
        cx = box.left() + 34 if sx > 0 else box.right() - 34
        cy = box.top() + 34 if sy > 0 else box.bottom() - 34
        path = QPainterPath()                                # Filigree: two arcs meeting in a star.
        path.moveTo(cx, cy + sy * 70)
        path.cubicTo(cx, cy + sy * 30, cx + sx * 10, cy + sy * 10, cx + sx * 40, cy)
        path.moveTo(cx + sx * 70, cy)
        path.cubicTo(cx + sx * 30, cy, cx + sx * 10, cy + sy * 10, cx, cy + sy * 40)
        p.setPen(QPen(QBrush(m), 3.2, Qt.SolidLine, Qt.RoundCap))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(m))
        p.drawPolygon(star(cx, cy, 15, .26))
        p.setBrush(QColor(255, 255, 255, 230))
        p.drawEllipse(QPointF(cx, cy), 3, 3)
        for k in (1, 2):                                    # Small gems along the arcs.
            p.setBrush(colour(GEM[rarity], .95))
            p.drawEllipse(QPointF(cx + sx * 26 * k + sx * 8, cy - sy * 1), 3.2, 3.2)
            p.drawEllipse(QPointF(cx - sx * 1, cy + sy * 26 * k + sy * 8), 3.2, 3.2)


def crest(p, rarity, box):
    cx, cy = box.center().x(), box.top()
    m = metal(rarity, QPointF(cx - 40, cy - 40), QPointF(cx + 40, cy + 40))
    p.setPen(QPen(QColor(4, 4, 12, 230), 5))
    p.setBrush(QBrush(m))
    wings = QPainterPath()                                  # Little wings either side of the gem.
    for sx in (-1, 1):
        wings.moveTo(cx, cy)
        wings.cubicTo(cx + sx * 40, cy - 22, cx + sx * 74, cy - 6, cx + sx * 92, cy + 4)
        wings.cubicTo(cx + sx * 66, cy + 10, cx + sx * 40, cy + 14, cx, cy + 10)
    p.drawPath(wings)
    p.drawEllipse(QPointF(cx, cy), 34, 34)
    gem = QRadialGradient(QPointF(cx - 8, cy - 10), 32)
    gem.setColorAt(0, QColor(255, 255, 255))
    gem.setColorAt(.35, colour(GEM[rarity]))
    gem.setColorAt(1, colour(tuple(c * .35 for c in GEM[rarity])))
    if rarity == 'xinghai':
        gem = QConicalGradient(QPointF(cx, cy), 30)
        for k in range(7):
            gem.setColorAt(k / 6, QColor.fromHsvF(k / 6, .55, 1))
    p.setPen(QPen(QColor(255, 255, 255, 150), 1.5))
    p.setBrush(QBrush(gem))
    p.drawEllipse(QPointF(cx, cy), 24, 24)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(255, 255, 255, 235))
    p.drawPolygon(star(cx, cy, 15, .25))


def plate(p, rarity, box):
    """The name plate low on the card and the rank stars above it."""
    top, bottom = box.top() + box.height() * .7, box.top() + box.height() * .92
    rect = QRectF(box.left() + 30, top, box.width() - 60, bottom - top)
    path = QPainterPath()
    path.addRoundedRect(rect, 18, 18)
    fill = QLinearGradient(rect.topLeft(), rect.bottomLeft())
    fill.setColorAt(0, QColor(10, 8, 26, 205))
    fill.setColorAt(1, QColor(4, 3, 14, 230))
    p.setPen(Qt.NoPen)
    p.setBrush(fill)
    p.drawPath(path)
    m = metal(rarity, rect.topLeft(), rect.topRight())
    p.setPen(QPen(QBrush(m), 2.4))
    p.setBrush(Qt.NoBrush)
    p.drawPath(path)
    p.setPen(QPen(QBrush(m), 1.4))
    p.drawLine(QPointF(rect.left() + 40, rect.top() + rect.height() * .62),
               QPointF(rect.right() - 40, rect.top() + rect.height() * .62))
    for sx in (-1, 1):                                      # Diamonds at the plate's ends.
        x = rect.center().x() + sx * (rect.width() / 2)
        p.setPen(QPen(QColor(4, 4, 12, 220), 2))
        p.setBrush(QBrush(m))
        p.drawPolygon(star(x, rect.center().y(), 13, .55))
    count = RANK[rarity]
    gap = 34
    x0 = box.center().x() - gap * (count - 1) / 2
    for k in range(count):
        cx, cy = x0 + k * gap, top - 30
        p.setPen(QPen(QColor(4, 4, 12, 200), 2))
        p.setBrush(QBrush(metal(rarity, QPointF(cx - 12, cy - 12), QPointF(cx + 12, cy + 12))))
        p.drawPolygon(star(cx, cy, 14, .45, points=5))


def render(rarity, sky):
    image = QImage(W, H, QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    p = QPainter(image)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    box = QRectF(22, 48, W - 44, H - 70)
    radius = 30
    face(p, rarity, box, radius, sky)
    border(p, rarity, box, radius)
    corners(p, rarity, box)
    plate(p, rarity, box)
    crest(p, rarity, box)
    p.end()
    OUT.mkdir(parents=True, exist_ok=True)
    image.save(str(OUT / f'card_{rarity}.webp'), 'WEBP', 92)
    return image


def main():
    app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])  # noqa: F841
    sky = QImage(str(OUT / 'sky_far.jpg'))
    for rarity in METAL:
        render(rarity, sky)
        print('card', rarity)


if __name__ == '__main__':
    main()
