"""AE-style motion videos for Petoken 2.3: voice-over, beat-timed cuts, kinetic type.

Usage:
    python tools/motion_video.py OUT_DIR --ffmpeg PATH --script new|game|night|phone|short
                                 [--language zh_CN|en] [--stills] [--rerecord]

The voice is Microsoft's neural TTS through edge-tts (a lively young voice;
word timings drive the karaoke subtitles). Music and sound effects are
synthesized (tools/motion_music.py). Pictures come from the same sandboxed
test build as tools/tutorial_video.py: real window captures, her real
animation, and live recordings of game mode. Every shot is drawn with Qt:
an animated background, a kinetic headline, a camera that pushes in, cards
tilted in 3D, stickers popping in, and whip / zoom / wipe transitions that
land on the beat.
"""
import argparse
import array
import asyncio
import hashlib
import json
import math
import random
import subprocess
import sys
import wave
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QColor, QFont, QFontMetricsF, QImage, QLinearGradient, QPainter, QPainterPath, QPen,
                           QRadialGradient, QTransform)
from PySide6.QtWidgets import QApplication

import tools.tutorial_video as tv
from tools import motion_music as mm
from tools.motion_scripts import SCRIPTS

FPS = 30
SR = mm.SR
STEP = 2 * mm.BEAT                 # Shots last a whole number of half bars.
VO_DELAY = .35                     # The voice starts after the transition.
TRANSITION = .4
VOICES = {'zh_CN': ('zh-CN-XiaoyiNeural', '+6%', '+8Hz'), 'en': ('en-US-EmmaNeural', '+4%', '+3Hz')}
THEMES = {
    'brand': ('#21164F', '#5B3FC4', '#FF7AC6', '#FFD45E'),
    'space': ('#050A22', '#1B2470', '#5FD4FF', '#FFD45E'),
    'night': ('#0B1030', '#2E2F78', '#B9A8FF', '#FFE08A'),
    'pink': ('#2A1450', '#B23E8F', '#FFB1D8', '#FFE27A'),
    'mint': ('#0C2235', '#1E7F8E', '#7CF2D0', '#FFD45E'),
    'sunset': ('#2B1240', '#C9506F', '#FFC48A', '#FFE27A'),
}
GOLD = QColor('#FFD45E')
LANG = 'zh_CN'
W, H = 1920, 1080
VERTICAL = False


# Easing --------------------------------------------------------------------------

def clamp(x):
    return max(0.0, min(1.0, x))


def ease_out(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def ease_in_out(x):
    x = clamp(x)
    return 4 * x ** 3 if x < .5 else 1 - (-2 * x + 2) ** 3 / 2


def ease_back(x, s=1.9):
    x = clamp(x)
    return 1 + (s + 1) * (x - 1) ** 3 + s * (x - 1) ** 2


def font(size, heavy=True):
    f = QFont('Microsoft YaHei UI' if LANG == 'zh_CN' else ('Segoe UI Black' if heavy else 'Segoe UI'))
    f.setPixelSize(int(size))
    f.setBold(heavy and LANG == 'zh_CN')
    return f


# Voice ---------------------------------------------------------------------------

async def _speak(text, voice, rate, pitch, mp3):
    import edge_tts
    words = []
    talk = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch, boundary='WordBoundary')
    with open(mp3, 'wb') as out:
        async for chunk in talk.stream():
            if chunk['type'] == 'audio':
                out.write(chunk['data'])
            elif chunk['type'] == 'WordBoundary':
                words.append((chunk['offset'] / 1e7, (chunk['offset'] + chunk['duration']) / 1e7, chunk['text']))
    return words


def speak(text, folder, ffmpeg):
    """(wav at SR, seconds, [(start, end, word)]), cached by text and voice."""
    voice, rate, pitch = VOICES[LANG]
    key = hashlib.sha1(f'{voice}{rate}{pitch}{text}'.encode()).hexdigest()[:16]
    folder.mkdir(parents=True, exist_ok=True)
    wav, meta = folder / f'{key}.wav', folder / f'{key}.json'
    if not (wav.exists() and meta.exists()):
        mp3 = folder / f'{key}.mp3'
        for attempt in range(3):
            try:
                words = asyncio.run(_speak(text, voice, rate, pitch, mp3))
                break
            except Exception:
                if attempt == 2:
                    raise
        subprocess.run([ffmpeg, '-y', '-loglevel', 'error', '-i', str(mp3), '-ac', '1', '-ar', str(SR), str(wav)],
                       check=True)
        mp3.unlink()
        meta.write_text(json.dumps(words, ensure_ascii=False), encoding='utf-8')
    with wave.open(str(wav)) as w:
        seconds = w.getnframes() / w.getframerate()
    return wav, seconds, [tuple(x) for x in json.loads(meta.read_text(encoding='utf-8'))]


def char_times(text, words):
    """When each character of ``text`` is spoken (seconds into the voice)."""
    times = [None] * len(text)
    low, cursor = text.lower(), 0
    for start, end, word in words:
        at = low.find(word.lower(), cursor)
        if at < 0 or at - cursor > 12:
            continue
        for k in range(len(word)):
            times[at + k] = start + (end - start) * k / max(1, len(word))
        cursor = at + len(word)
    last = 0.0
    for i, value in enumerate(times):
        if value is None:
            times[i] = last
        else:
            last = value
    return times


# Drawing helpers -----------------------------------------------------------------------

def rounded(rect, radius):
    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    return path


def shadow(p, rect, radius, strength=1.0):
    p.setPen(Qt.NoPen)
    for k in range(8):
        p.setBrush(QColor(5, 0, 25, int(16 * strength)))
        p.drawRoundedRect(rect.adjusted(-k * 3, -k * 3 + 14, k * 3, k * 3 + 14), radius + k * 2, radius + k * 2)


def pill(p, center, text, size, accent, angle=0.0, scale=1.0, alpha=1.0, fill='#FFFFFF'):
    f = font(size)
    m = QFontMetricsF(f)
    w, h = m.horizontalAdvance(text) + size * 1.2, size * 1.75
    p.save()
    p.translate(center)
    p.rotate(angle)
    p.scale(scale, scale)
    p.setOpacity(alpha)
    box = QRectF(-w / 2, -h / 2, w, h)
    shadow(p, box, h / 2, .6)
    p.setBrush(QColor(fill))
    p.setPen(QPen(QColor(accent), 3))
    p.drawRoundedRect(box, h / 2, h / 2)
    p.setPen(QColor(accent) if fill == '#FFFFFF' else QColor('#FFFFFF'))
    p.setFont(f)
    p.drawText(box, Qt.AlignCenter, text)
    p.restore()


def units(text):
    """Pieces that pop in one by one: characters (Chinese) or words."""
    if LANG == 'zh_CN':
        return list(text)
    out = []
    for word in text.split(' '):
        out.append(word + ' ')
    return out


def wrap(pieces, f, width):
    m = QFontMetricsF(f)
    lines, line, x = [], [], 0.0
    for piece in pieces:
        w = m.horizontalAdvance(piece)
        if line and x + w > width and piece.strip():
            lines.append(line)
            line, x = [], 0.0
        line.append((piece, x, w))
        x += w
    if line:
        lines.append(line)
    return lines


def headline(p, text, x, y, size, t, width, accent, align=Qt.AlignLeft, start=.1):
    """A title whose characters or words pop in with an overshoot, over a sweeping colour bar."""
    f = font(size)
    lines = wrap(units(text), f, width)
    floor = size * .66                       # A slightly long title shrinks onto one line first.
    while len(lines) == 2 and size > floor and len(text) <= 12:
        size -= 4
        f = font(size)
        lines = wrap(units(text), f, width)
    if len(lines) > 1 and size <= floor:
        size = int(floor / .66)
        f = font(size)
        lines = wrap(units(text), f, width)
    while len(lines) > 2 and size > 40:
        size -= 6
        f = font(size)
        lines = wrap(units(text), f, width)
    line_h = size * 1.18
    index = 0
    for row, line in enumerate(lines):
        total = line[-1][1] + line[-1][2]
        left = x if align == Qt.AlignLeft else x + (width - total) / 2
        top = y + row * line_h
        if row == 0:                                          # The colour bar behind the first line.
            grow = ease_out((t - start) / .45)
            bar = QRectF(left - size * .2, top + line_h * .55, (total + size * .4) * grow, line_h * .42)
            color = QColor(accent)
            color.setAlpha(150)
            p.setPen(Qt.NoPen)
            p.setBrush(color)
            p.drawRoundedRect(bar, 8, 8)
        for piece, px, pw in line:
            a = (t - start - .05 - index * (.045 if LANG == 'zh_CN' else .08)) / .38
            index += 1
            if a <= 0:
                continue
            s = ease_back(a)
            p.save()
            p.translate(left + px + pw / 2, top + line_h * .62)
            p.scale(s, s)
            p.rotate((1 - ease_out(a)) * -12)
            p.setOpacity(clamp(a * 2))
            p.setFont(f)
            p.setPen(QColor(0, 0, 20, 90))
            p.drawText(QRectF(-pw / 2 + 4, -line_h * .62 + 5, pw + 40, line_h), Qt.AlignLeft | Qt.AlignVCenter, piece)
            p.setPen(QColor('#FFFFFF'))
            p.drawText(QRectF(-pw / 2, -line_h * .62, pw + 40, line_h), Qt.AlignLeft | Qt.AlignVCenter, piece)
            p.restore()
    return len(lines) * line_h


def star_path(c, r):
    path = QPainterPath()
    path.moveTo(c.x(), c.y() - r * 2)
    for dx, dy in ((r * 2, 0), (0, r * 2), (-r * 2, 0), (0, -r * 2)):
        path.quadTo(c.x(), c.y(), c.x() + dx, c.y() + dy)
    return path


def burst(p, center, t, count, radius, color, seed):
    """Little stars flying out from ``center`` for the first ~0.9 s."""
    if t > .95 or t < 0:
        return
    rng = random.Random(seed)
    for k in range(count):
        a = rng.uniform(0, 2 * math.pi)
        d = radius * rng.uniform(.5, 1.1) * ease_out(t / .9)
        c = QPointF(center.x() + math.cos(a) * d, center.y() + math.sin(a) * d)
        size = rng.uniform(4, 9) * (1 - t / .95)
        col = QColor(color)
        col.setAlphaF(clamp(1 - t / .95))
        p.setPen(Qt.NoPen)
        p.setBrush(col)
        p.drawPath(star_path(c, size))


# The video -------------------------------------------------------------------------------

class Motion:
    def __init__(self, shots, theme, stills, lives, clipper, notices, ffmpeg):
        self.shots, self.stills, self.lives, self.clipper = shots, stills, lives, clipper
        self.notices, self.ffmpeg = notices, ffmpeg
        self.top, self.bottom, self.accent, self.gold = (QColor(c) for c in THEMES[theme])
        rng = random.Random(4)
        self.bokeh = [(rng.random(), rng.random(), rng.uniform(30, 120), rng.uniform(.004, .02), rng.random())
                      for _ in range(26)]
        self.stars = [(rng.random(), rng.random(), rng.uniform(1, 2.6), rng.uniform(0, 6.3)) for _ in range(90)]
        self.frames = None
        self.decoder = None
        self.last_layer = None

    # Timing -----------------------------------------------------------------------
    def plan(self, voice_dir):
        at = 0.0
        for n, s in enumerate(self.shots):
            s['wav'], s['voice'], words = speak(s['say'], voice_dir, self.ffmpeg)
            s['times'] = char_times(s['say'], words)
            need = max(s.get('min') or 0, VO_DELAY + s['voice'] + .55)
            s['duration'] = math.ceil(need / STEP) * STEP
            s['start'] = at
            at += s['duration']
        self.total = at
        return at

    # Background ---------------------------------------------------------------------
    def background(self, p, time):
        g = QLinearGradient(0, 0, W * .3, H)
        g.setColorAt(0, self.top)
        g.setColorAt(1, self.bottom)
        p.fillRect(0, 0, W, H, g)
        for k, (x, y, r, speed, phase) in enumerate(self.bokeh):
            cx = (x * W + math.sin(time * .3 + phase * 6) * 40) % W
            cy = (y * H - time * speed * H) % (H + 200) - 100
            col = QColor(self.accent if k % 3 else self.gold)
            rg = QRadialGradient(cx, cy, r)
            col.setAlpha(46)
            rg.setColorAt(0, col)
            col.setAlpha(0)
            rg.setColorAt(1, col)
            p.setPen(Qt.NoPen)
            p.setBrush(rg)
            p.drawEllipse(QPointF(cx, cy), r, r)
        for x, y, r, phase in self.stars:
            a = .25 + .75 * (.5 + .5 * math.sin(time * 2.4 + phase))
            p.setBrush(QColor(255, 255, 255, int(150 * a)))
            p.drawEllipse(QPointF(x * W, y * H), r, r)

    # Layout -----------------------------------------------------------------------------
    def stage(self, kind):
        """(content rect, title x, title y, title width, title size)."""
        if VERTICAL:
            return QRectF(50, 470, W - 100, 900), 60, 150, W - 120, 92
        if kind in ('list', 'outro'):
            return QRectF(140, 300, W - 280, 600), 120, 90, W - 240, 92
        return QRectF(W * .36, 120, W * .6, 780), 110, 300, W * .3, 96

    # Shots ---------------------------------------------------------------------------------
    def content(self, p, n, t):
        s = self.shots[n]
        kind = s['kind']
        rect, tx, ty, tw, ts = self.stage(kind)
        getattr(self, 'draw_' + kind)(p, s, t, rect)
        if kind != 'outro' and s.get('title'):
            align = Qt.AlignHCenter if (VERTICAL or kind == 'list') else Qt.AlignLeft
            headline(p, s['title'], tx, ty, ts, t, tw, self.accent, align)
        if s.get('tag'):
            a = ease_back((t - .5) / .4)
            if a > 0:
                pill(p, QPointF(tx + 140 if not VERTICAL else W / 2, ty - 50), s['tag'], 30, self.accent,
                     -4, a, clamp(a))

    def labels(self, p, s, t, anchors):
        items = s.get('labels') or ()
        for i, text in enumerate(items):
            at = self.label_time(s, i)
            a = ease_back((t - at) / .35)
            if a <= 0:
                continue
            fx, fy = anchors[i % len(anchors)]
            pill(p, QPointF(fx, fy + math.sin(t * 2 + i) * 4), text, 36 if not VERTICAL else 42,
                 self.accent if i % 2 else '#7B4DFF', (-5, 4, -3, 5)[i % 4], a, clamp(a * 1.5))

    @staticmethod
    def label_time(s, i):
        count = max(1, len(s.get('labels') or ()))
        return .9 + i * (s['duration'] * .55) / count

    def draw_pose(self, p, s, t, rect):
        frames = self.frames
        if not frames:
            return
        image = frames[min(len(frames) - 1, int(t * FPS))]
        lw, lh = image.width() / image.devicePixelRatio(), image.height() / image.devicePixelRatio()
        scale = min(rect.width() / lw, rect.height() / lh) * .98
        w, h = lw * scale, lh * scale
        cx, bottom = rect.center().x(), rect.bottom()
        # Glow behind her.
        glow = QRadialGradient(cx, bottom - h * .5, h * .6)
        col = QColor(self.accent)
        col.setAlpha(110)
        glow.setColorAt(0, col)
        col.setAlpha(0)
        glow.setColorAt(1, col)
        p.setPen(Qt.NoPen)
        p.setBrush(glow)
        p.drawEllipse(QPointF(cx, bottom - h * .5), h * .62, h * .62)
        p.setBrush(QColor(0, 0, 20, 70))
        p.drawEllipse(QPointF(cx, bottom - 18), w * .3, 22)
        a = ease_back(t / .55, 1.4)
        p.save()
        p.translate(cx, bottom)
        p.rotate((1 - ease_out(t / .55)) * -8)
        p.scale(.62 + .38 * a, .62 + .38 * a)
        p.translate(0, math.sin(t * 2.2) * 6)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.drawImage(QRectF(-w / 2, -h, w, h), image)
        p.restore()
        burst(p, QPointF(cx, bottom - h * .55), t - .1, 16, h * .55, self.gold, hash(s['say']) & 255)
        anchors = ((rect.left() + rect.width() * .12, rect.top() + rect.height() * .22),
                   (rect.right() - rect.width() * .1, rect.top() + rect.height() * .32),
                   (rect.left() + rect.width() * .1, rect.top() + rect.height() * .66),
                   (rect.right() - rect.width() * .12, rect.top() + rect.height() * .76))
        self.labels(p, s, t, anchors)

    def card_transform(self, center, t, duration, tilt=12):
        """A gentle 3D swing in, then a slow push."""
        ang = tilt * (1 - ease_out(t / .9)) + 2.5 * math.sin(t * .7)
        push = .9 + .1 * ease_in_out(t / max(1.0, duration)) + .06 * (1 - ease_back(t / .6)) * -1
        tr = QTransform()
        tr.translate(center.x(), center.y())
        tr.rotate(ang, Qt.YAxis)
        tr.rotate(2 * math.sin(t * .5), Qt.XAxis)
        tr.scale(push, push)
        return tr

    def draw_live(self, p, s, t, rect):
        image = self.decoder.next() if self.decoder else None
        if image is None:
            return
        w, h = self.decoder.size
        tr = self.card_transform(rect.center(), t, s['duration'])
        p.save()
        p.setTransform(tr, True)
        box = QRectF(-w / 2, -h / 2, w, h)
        shadow(p, box, 26)
        p.setClipPath(rounded(box, 26))
        p.drawImage(box, image)
        p.setClipping(False)
        p.setPen(QPen(QColor(255, 255, 255, 90), 3))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(box, 26, 26)
        p.restore()
        anchors = ((rect.left() + 40, rect.top() + 90), (rect.right() - 40, rect.top() + 160),
                   (rect.right() - 60, rect.bottom() - 120), (rect.left() + 60, rect.bottom() - 90))
        self.labels(p, s, t, anchors)

    def draw_still(self, p, s, t, rect):
        shot = self.stills[s['name']]
        image, dpr = shot['image'], shot['dpr']
        lw, lh = image.width() / dpr, image.height() / dpr
        fit = min(rect.width() / lw, rect.height() / lh) * .96
        view = QRectF(0, 0, lw * fit, lh * fit)
        view.moveCenter(rect.center())
        mark = shot['marks'].get(s.get('mark')) if s.get('mark') else None
        zoom, focus = 1.0, QPointF(lw / 2, lh / 2)
        e = ease_in_out((t - .7) / 1.0)
        if mark is not None and not mark.isEmpty():
            target = min(2.1, (lw * .62) / max(40, mark.width()))
            zoom = 1 + (max(1.0, target) - 1) * e
            mc = QPointF(mark.center())
            focus = QPointF(lw / 2 + (mc.x() - lw / 2) * e, lh / 2 + (mc.y() - lh / 2) * e)
        tr = self.card_transform(view.center(), t, s['duration'], tilt=8)
        p.save()
        p.setTransform(tr, True)
        box = QRectF(-view.width() / 2, -view.height() / 2, view.width(), view.height())
        shadow(p, box, 22)
        p.setClipPath(rounded(box, 22))
        p.fillRect(box, QColor('#F4F1FC'))
        k = fit * zoom
        inner = QTransform()
        inner.scale(k, k)
        inner.translate(-focus.x(), -focus.y())
        p.save()
        p.setTransform(inner, True)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.drawImage(QRectF(0, 0, lw, lh), image)
        if mark is not None and not mark.isEmpty() and t > 1.5:
            pulse = .6 + .4 * math.sin((t - 1.5) * 5)
            ring = ease_back((t - 1.5) / .35)
            m = QRectF(mark).adjusted(-8, -8, 8, 8)
            c = m.center()
            m = QRectF(c.x() - m.width() / 2 * ring, c.y() - m.height() / 2 * ring, m.width() * ring, m.height() * ring)
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor(255, 80, 120, int(255 * pulse)), 5 / k))
            p.drawRoundedRect(m, 12, 12)
        p.restore()
        p.setClipping(False)
        p.restore()
        if s.get('step'):
            a = ease_back((t - .3) / .4)
            if a > 0:
                c = QPointF(view.left() + 20, view.top() + 10)
                p.save()
                p.translate(c)
                p.scale(a, a)
                p.setPen(QPen(QColor('#FFFFFF'), 6))
                p.setBrush(QColor(self.accent))
                p.drawEllipse(QPointF(0, 0), 62, 62)
                p.setFont(font(64))
                p.setPen(QColor('#FFFFFF'))
                p.drawText(QRectF(-62, -66, 124, 124), Qt.AlignCenter, str(s['step']))
                p.restore()

    def draw_phone(self, p, s, t, rect):
        h = min(rect.height(), 860 if not VERTICAL else 900)
        w = h * .5
        rise = ease_back(t / .6, 1.2)
        cx = rect.center().x()
        cy = rect.center().y() + (1 - rise) * 500
        body = QRectF(cx - w / 2, cy - h / 2, w, h)
        p.save()
        p.translate(body.center())
        p.rotate(-6 * (1 - ease_out(t / .8)) + 1.5 * math.sin(t * .8))
        p.translate(-body.center())
        shadow(p, body, 60)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor('#121026'))
        p.drawRoundedRect(body, 60, 60)
        screen = body.adjusted(14, 14, -14, -14)
        g = QLinearGradient(screen.topLeft(), screen.bottomLeft())
        g.setColorAt(0, QColor('#3A3474'))
        g.setColorAt(1, QColor('#8A6CD0'))
        p.setBrush(g)
        p.drawRoundedRect(screen, 48, 48)
        p.setBrush(QColor('#121026'))
        p.drawRoundedRect(QRectF(screen.center().x() - 55, screen.top() + 12, 110, 26), 13, 13)
        p.setPen(QColor('#FFFFFF'))
        p.setFont(font(h * .085))
        p.drawText(QRectF(screen.left(), screen.top() + h * .07, screen.width(), h * .1), Qt.AlignCenter, '23:41')
        y = screen.top() + h * .22
        for i, (title, text) in enumerate(self.notices):
            at = .8 + i * .7
            a = ease_back((t - at) / .4)
            if a <= 0:
                continue
            card = QRectF(screen.left() + 14, y, screen.width() - 28, h * .15)
            p.save()
            p.translate(card.center())
            p.scale(.85 + .15 * a, .85 + .15 * a)
            p.translate(-card.center().x(), -card.center().y() - (1 - a) * 40)
            p.setOpacity(clamp(a * 1.5))
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, 235))
            p.drawRoundedRect(card, 20, 20)
            p.setPen(QColor('#6A5C9A'))
            p.setFont(font(h * .018, False))
            p.drawText(card.adjusted(18, 10, -18, 0), Qt.AlignLeft | Qt.AlignTop, 'ntfy · Petoken')
            p.setPen(QColor('#231E56'))
            p.setFont(font(h * .024))
            p.drawText(card.adjusted(18, h * .035, -18, 0), Qt.AlignLeft | Qt.AlignTop,
                       QFontMetricsF(font(h * .024)).elidedText(title, Qt.ElideRight, card.width() - 36))
            p.setPen(QColor('#5C5577'))
            p.setFont(font(h * .019, False))
            p.drawText(card.adjusted(18, h * .075, -18, -6), Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap,
                       QFontMetricsF(font(h * .019, False)).elidedText(text or ' ', Qt.ElideRight,
                                                                      (card.width() - 36) * 1.8))
            p.restore()
            y += h * .17
        p.restore()

    def draw_toast(self, p, s, t, rect):
        """Desktop notices popping up in the corner while she reacts beside them."""
        left = QRectF(rect.left() - W * .05, rect.top() + 60, rect.width() * .42, rect.height() - 60)
        self.draw_pose(p, dict(s, labels=()), t, left)
        w, h = rect.width() * .56, 150
        x = rect.right() - w
        y = rect.bottom() - 40
        for i, (title, text) in enumerate(self.notices):
            at = .7 + i * .9
            a = ease_out((t - at) / .45)
            if a <= 0:
                continue
            y -= h + 22
            card = QRectF(x + (1 - a) * (w + 120), y, w, h)
            p.save()
            p.setOpacity(clamp(a * 1.4))
            shadow(p, card, 18, .9)
            p.setPen(QPen(QColor(255, 255, 255, 40), 1.5))
            p.setBrush(QColor(38, 36, 58, 245))
            p.drawRoundedRect(card, 18, 18)
            icon = QRectF(card.left() + 22, card.top() + 20, 30, 30)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(self.accent))
            p.drawRoundedRect(icon, 8, 8)
            p.setPen(QColor('#BDB6E4'))
            p.setFont(font(20, False))
            p.drawText(QRectF(icon.right() + 12, icon.top() - 2, w, 34), Qt.AlignLeft | Qt.AlignVCenter, 'Petoken')
            p.setPen(QColor('#FFFFFF'))
            p.setFont(font(27))
            p.drawText(card.adjusted(22, 60, -22, 0), Qt.AlignLeft | Qt.AlignTop,
                       QFontMetricsF(font(27)).elidedText(title, Qt.ElideRight, w - 44))
            p.setPen(QColor('#D6D1F2'))
            p.setFont(font(21, False))
            p.drawText(card.adjusted(22, 100, -22, -8), Qt.AlignLeft | Qt.AlignTop,
                       QFontMetricsF(font(21, False)).elidedText(text or ' ', Qt.ElideRight, w - 44))
            p.restore()

    def draw_list(self, p, s, t, rect):
        items = s['items']
        cols = 1 if VERTICAL else 2
        rows = math.ceil(len(items) / cols)
        gap = 34
        cw = (rect.width() - gap * (cols - 1)) / cols
        ch = min(170, (rect.height() - gap * (rows - 1)) / rows)
        top = rect.top() + (rect.height() - rows * ch - gap * (rows - 1)) / 2
        colors = ('#7B4DFF', '#FF5FA2', '#2EC4B6', '#FFB703')
        for i, text in enumerate(items):
            at = self.item_time(s, i)
            a = ease_back((t - at) / .45)
            if a <= 0:
                continue
            r, c = divmod(i, cols)
            box = QRectF(rect.left() + c * (cw + gap), top + r * (ch + gap), cw, ch)
            p.save()
            p.translate(box.center())
            p.scale(.6 + .4 * a, .6 + .4 * a)
            p.rotate((1 - ease_out((t - at) / .45)) * (8 if c else -8))
            p.translate(-box.center() + QPointF((1 - ease_out((t - at) / .45)) * 260, 0))
            p.setOpacity(clamp(a * 1.6))
            shadow(p, box, 30, .8)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, 240))
            p.drawRoundedRect(box, 30, 30)
            dot = QRectF(box.left() + 28, box.center().y() - ch * .3, ch * .6, ch * .6)
            p.setBrush(QColor(colors[i % 4]))
            p.drawEllipse(dot)
            p.setPen(QColor('#FFFFFF'))
            p.setFont(font(ch * .3))
            p.drawText(dot, Qt.AlignCenter, str(i + 1))
            p.setPen(QColor('#231E56'))
            size = ch * .3
            while size > 20 and QFontMetricsF(font(size)).horizontalAdvance(text) > box.width() - dot.width() - 80:
                size -= 2
            p.setFont(font(size))
            p.drawText(box.adjusted(dot.width() + 56, 0, -20, 0), Qt.AlignLeft | Qt.AlignVCenter, text)
            p.restore()

    @staticmethod
    def item_time(s, i):
        return .7 + i * min(.9, (s['duration'] - 1.6) / max(1, len(s['items'])))

    def draw_outro(self, p, s, t, rect):
        if self.frames:
            pet = QRectF(W * .6, H * .12, W * .36, H * .8) if not VERTICAL else QRectF(140, 760, W - 280, 760)
            self.draw_pose(p, dict(s, labels=()), t, pet)
        size = 150 if not VERTICAL else 130
        if VERTICAL:
            x, y, width, align = 40, 260, W - 80, Qt.AlignHCenter
        else:
            x, y, width, align = 120, H * .3, W * .55, Qt.AlignLeft
        used = headline(p, s['title'], x, y, size, t, width, self.accent, align, start=.15)
        a = ease_out((t - .9) / .5)
        if a > 0 and s.get('sub'):
            p.setOpacity(a)
            p.setPen(QColor('#FFFFFF'))
            p.setFont(font(40 if not VERTICAL else 44, False))
            box = QRectF(x, y + used + 30 + (1 - a) * 20, width, 120)
            p.drawText(box, align | Qt.AlignTop | Qt.TextWordWrap, s['sub'])
            p.setOpacity(1)
        burst(p, QPointF(x + width * (.5 if VERTICAL else .3), y + size * .6), t - .1, 26, size * 2.4, self.gold, 9)

    # Subtitles --------------------------------------------------------------------------
    def pieces(self, s):
        if 'pieces' in s:
            return s['pieces']
        text = s['say']
        size = 46 if not VERTICAL else 54
        limit = W * (.78 if not VERTICAL else .86)
        f = font(size)
        m = QFontMetricsF(f)
        import re
        parts = [x for x in re.split(r'(?<=[，。！？；：、,.!?;:])\s*', text) if x]
        spans, start = [], 0
        for part in parts:
            at = text.find(part, start)
            spans.append((at, at + len(part)))
            start = at + len(part)
        joined = []
        for a, b in spans:
            if joined and m.horizontalAdvance(text[joined[-1][0]:b]) <= limit:
                joined[-1] = (joined[-1][0], b)
            else:
                joined.append((a, b))
        s['pieces'] = joined
        return joined

    def subtitle(self, p, s, t):
        voice_t = t - VO_DELAY
        if voice_t < -.1:
            return
        pieces = self.pieces(s)
        times = s['times']
        current = 0
        for i, (a, b) in enumerate(pieces):
            if voice_t >= times[a] - .15:
                current = i
        a, b = pieces[current]
        text = s['say'][a:b].strip()
        offset = s['say'].find(text, a)
        size = 46 if not VERTICAL else 54
        f = font(size)
        m = QFontMetricsF(f)
        width = m.horizontalAdvance(text)
        appear = ease_back((voice_t - times[a] + .15) / .3)
        cy = H - 92 if not VERTICAL else 1540
        box = QRectF(W / 2 - width / 2 - 34, cy - size * .95, width + 68, size * 1.9)
        p.save()
        p.translate(box.center())
        p.scale(.9 + .1 * appear, .9 + .1 * appear)
        p.translate(-box.center())
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(12, 6, 40, 205))
        p.drawRoundedRect(box, box.height() / 2, box.height() / 2)
        x = box.left() + 34
        p.setFont(f)
        for k, ch in enumerate(text):
            spoken = voice_t >= times[min(len(times) - 1, offset + k)]
            p.setPen(self.gold if spoken else QColor('#FFFFFF'))
            cw = m.horizontalAdvance(ch)
            p.drawText(QRectF(x, box.top(), cw + 4, box.height()), Qt.AlignLeft | Qt.AlignVCenter, ch)
            x += cw
        p.restore()

    # Frame --------------------------------------------------------------------------------
    def layer(self, n, t):
        image = QImage(W, H, QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent)
        p = QPainter(image)
        p.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform)
        self.content(p, n, t)
        p.end()
        return image

    def transition(self, p, n, t, current):
        style = ('whip', 'zoom', 'wipe')[n % 3]
        e = ease_in_out(t / TRANSITION)
        prev = self.last_layer
        if style == 'whip':
            for k in range(4):
                p.setOpacity((1 - e) * (.5 if k else 1) / (k + 1))
                p.drawImage(QPointF(-e * W * .7 - k * 40 * math.sin(math.pi * e), 0), prev)
            for k in range(4):
                p.setOpacity(e * (.5 if k else 1) / (k + 1))
                p.drawImage(QPointF((1 - e) * W * .7 + k * 40 * math.sin(math.pi * e), 0), current)
            p.setOpacity(1)
        elif style == 'zoom':
            for image, scale, alpha in ((prev, 1 + e * .6, 1 - e), (current, .8 + .2 * e, e)):
                p.save()
                p.setOpacity(alpha)
                p.translate(W / 2, H / 2)
                p.scale(scale, scale)
                p.translate(-W / 2, -H / 2)
                p.drawImage(0, 0, image)
                p.restore()
            p.setOpacity(1)
            p.fillRect(0, 0, W, H, QColor(255, 255, 255, int(110 * math.sin(math.pi * e))))
        else:
            p.drawImage(0, 0, prev)
            r = e * math.hypot(W, H) * .6
            circle = QPainterPath()
            circle.addEllipse(QPointF(W / 2, H / 2), r, r)
            p.save()
            p.setClipPath(circle)
            p.drawImage(0, 0, current)
            p.restore()
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor(self.gold), 10 * (1 - e) + 2))
            p.drawEllipse(QPointF(W / 2, H / 2), r, r)

    def frame(self, n, t, out):
        s = self.shots[n]
        p = QPainter(out)
        p.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform)
        self.background(p, s['start'] + t)
        current = self.layer(n, t)
        if n > 0 and t < TRANSITION and self.last_layer is not None:
            self.transition(p, n, t, current)          # last_layer: the previous shot's final frame.
        else:
            p.drawImage(0, 0, current)
            self.last_layer = current
        self.subtitle(p, s, t)
        # Brand chip and progress.
        p.setOpacity(.85)
        pill(p, QPointF(W - 150, 60) if not VERTICAL else QPointF(W / 2, 70), 'Petoken', 24, self.accent,
             fill='#FFFFFF')
        p.setOpacity(1)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(self.gold))
        p.drawRect(QRectF(0, H - 6, W * (s['start'] + t) / self.total, 6))
        p.end()

    def begin(self, n):
        """Load what shot ``n`` needs (her frames, a recording decoder)."""
        s = self.shots[n]
        if self.decoder is not None:
            self.decoder.close()
            self.decoder = None
        self.frames = None
        if s['kind'] in ('pose', 'outro', 'toast') and s.get('clip'):
            self.frames = self.clipper.frames(s['clip'], s['duration'] + .1)
        if s['kind'] == 'live':
            from tools.live_capture import Decoder
            path, (w, h) = self.lives[s['name']]
            rect = self.stage('live')[0]
            # The middle of the recording: she, her ring and the rings, without the empty backdrop.
            keep = s.get('crop', (.72, .86))
            crop = (int(w * keep[0]) // 2 * 2, int(h * keep[1]) // 2 * 2)
            if VERTICAL:
                crop = (min(crop[0], int(crop[1] * rect.width() / rect.height())) // 2 * 2, crop[1])
            w, h = crop
            scale = min(rect.width() / w, rect.height() / h) * .94
            size = (int(w * scale) // 2 * 2, int(h * scale) // 2 * 2)
            self.decoder = Decoder(self.ffmpeg, path, size, FPS, start=s.get('offset', 0.0), crop=crop)

    # Sound --------------------------------------------------------------------------------
    def sounds(self):
        """[(time, effect)] for the whole video."""
        out = []
        for n, s in enumerate(self.shots):
            t0 = s['start']
            if n:
                out.append((t0 - .12, 'whoosh'))
            if s['kind'] == 'live' and s.get('name') == 'transform':
                out.append((t0 - 1.5, 'riser'))
                out.append((t0 + .05, 'impact'))
            if s['kind'] == 'outro':
                out.append((t0 + .1, 'impact'))
                out.append((t0 + .3, 'sparkle'))
            if s.get('title'):
                out.append((t0 + .15, 'pop'))
            if s['kind'] == 'pose':
                out.append((t0 + .2, 'sparkle'))
            for i, _ in enumerate(s.get('labels') or ()):
                out.append((t0 + self.label_time(s, i), 'pop'))
            for i, _ in enumerate(s.get('items') or ()):
                out.append((t0 + self.item_time(s, i), 'pop'))
            if s['kind'] == 'phone':
                for i in range(len(self.notices)):
                    out.append((t0 + .8 + i * .7, 'ding'))
        return out


def read_wav(path):
    with wave.open(str(path)) as w:
        data = array.array('h', w.readframes(w.getnframes()))
    return data


def build_audio(motion, folder, ffmpeg):
    total = int((motion.total + 1) * SR)
    voice = array.array('h', bytes(2 * total))
    for s in motion.shots:
        samples = read_wav(s['wav'])
        at = int((s['start'] + VO_DELAY) * SR)
        end = min(total, at + len(samples))
        voice[at:end] = samples[:end - at]
    voice_path = folder / 'voice.wav'
    with wave.open(str(voice_path), 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(voice.tobytes())
    effects = [0.0] * total
    cache = {}
    for at, kind in motion.sounds():
        sound = cache.setdefault(kind, mm.sfx(kind))
        mm._add(effects, at, sound)
    sfx_path = folder / 'sfx.wav'
    mm.write(sfx_path, effects, .8)
    music_path = folder / 'music.wav'
    mm.write(music_path, mm.render(motion.total + 1), .9)
    return voice_path, sfx_path, music_path


def capture(language, out_dir, ffmpeg, wanted_lives, rerecord):
    stack = ExitStack()
    pv, base = tv.setup(stack, language)
    stills = tv.capture_all(pv, base)
    game = [name for name in wanted_lives if name in tv.LIVES]
    ring = [name for name in wanted_lives if name in tv.RING_LIVES]
    lives = tv.record_lives(pv, base, game, out_dir / 'live', rerecord) if game else {}
    if ring:
        lives.update(tv.record_ring_lives(pv, base, ring, out_dir / 'live', rerecord))
    from notifications import recap_detail
    events = [dict(kind='finished', provider='claude', project='website', title=tv.U('history')[0],
                   detail=recap_detail(dict(files=['src/login.ts', 'src/form.css'], duration_s=372, usd=.42))),
              dict(kind='needs_approval', provider='codex', project='api-server', title=tv.U('history')[2]),
              dict(kind='quota_low', provider='claude', project='', detail='18')]
    with patch.object(pv.panel, 'task_title', side_effect=lambda event: event.get('title')):
        notices = [pv.panel.notification_text(event) for event in events]
    return stack, pv, base, stills, lives, notices


def main(argv=None):
    global LANG, W, H, VERTICAL
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('out_dir', type=Path)
    parser.add_argument('--ffmpeg', required=True)
    parser.add_argument('--script', choices=tuple(SCRIPTS), required=True)
    parser.add_argument('--language', choices=('zh_CN', 'en'), default='zh_CN')
    parser.add_argument('--stills', action='store_true', help='One picture per shot, no video')
    parser.add_argument('--rerecord', action='store_true')
    args = parser.parse_args(argv)
    LANG = args.language
    spec = SCRIPTS[args.script][LANG]
    VERTICAL = bool(spec.get('vertical'))
    W, H = (1080, 1920) if VERTICAL else (1920, 1080)
    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    tv.FFMPEG = args.ffmpeg
    shots = [dict(s) for s in spec['shots']]
    wanted = [s['name'] for s in shots if s['kind'] == 'live']
    stack, pv, base, stills, lives, notices = capture(LANG, out_dir, args.ffmpeg, wanted, args.rerecord)
    LANG = args.language                         # tutorial_video.setup set its own.
    with stack:
        motion = Motion(shots, spec['theme'], stills, lives, tv.PetClip(base.panel), notices, args.ffmpeg)
        total = motion.plan(out_dir / 'voice')
        print(f'length {total:.1f} s', flush=True)
        for s in shots:
            print(f"at {int(s['start'] // 60):02d}:{int(s['start'] % 60):02d} {s['title']}", flush=True)
        image = QImage(W, H, QImage.Format_RGB888)
        if args.stills:
            for n, s in enumerate(shots):
                motion.begin(n)
                t = min(s['duration'] - .1, 2.6)
                for k in range(int(t * FPS)):                 # Recordings and clips play up to t.
                    if motion.decoder:
                        motion.decoder.next()
                motion.frame(n, t, image)
                image.save(str(out_dir / f'shot_{n:02d}.png'))
            tv.finish(pv, base)
            return 0
        silent = out_dir / 'video_only.mp4'
        proc = subprocess.Popen([args.ffmpeg, '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
                                 '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-', '-c:v', 'h264_nvenc', '-preset', 'p7',
                                 '-rc', 'vbr', '-cq', '21', '-b:v', '0', '-g', '120', '-bf', '2',
                                 '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(silent)], stdin=subprocess.PIPE)
        for n, s in enumerate(shots):
            motion.begin(n)
            for k in range(int(round(s['duration'] * FPS))):
                motion.frame(n, k / FPS, image)
                proc.stdin.write(bytes(image.constBits()))
            print(f'shot {n + 1}/{len(shots)}', flush=True)
        if motion.decoder:
            motion.decoder.close()
        proc.stdin.close()
        proc.wait()
        voice, effects, music = build_audio(motion, out_dir, args.ffmpeg)
        final = out_dir / spec['out']
        mix = ('[1:a]volume=0.5[m];[2:a]highpass=f=90,acompressor=threshold=-20dB:ratio=3:attack=5:release=120,'
               'volume=1.8,asplit=2[v1][v2];[m][v1]sidechaincompress=threshold=0.03:ratio=8:attack=15:release=320[md];'
               '[md][v2][3:a]amix=inputs=3:normalize=0:weights=1 1 0.7,pan=stereo|c0=c0|c1=c0,loudnorm=I=-14:TP=-1.5:LRA=11,'
               'aresample=48000[a]')
        subprocess.run([args.ffmpeg, '-y', '-loglevel', 'error', '-i', str(silent), '-i', str(music), '-i', str(voice),
                        '-i', str(effects), '-filter_complex', mix, '-map', '0:v', '-map', '[a]', '-c:v', 'copy',
                        '-c:a', 'aac', '-b:a', '192k', '-shortest', '-movflags', '+faststart', str(final)], check=True)
        for path in (silent, voice, effects, music):
            path.unlink()
        print('done', final, flush=True)
        tv.finish(pv, base)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
