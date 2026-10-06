"""Render the Petoken promo video from real UI captures (see promo_capture.py).

Usage:
    python tools/promo_capture.py ASSETS
    python tools/promo_video.py ASSETS OUT.mp4 [--language en] [--ffmpeg PATH]
    python tools/promo_video.py ASSETS OUT.mp4 --preview 3.2 9.5   # stills only

1920x1080, 30 fps, 51 s. Motion-graphics style: spring overshoot, squash and
stretch, staggered word pops, iris transitions and particle bursts, all on a
100 BPM grid shared with a procedurally synthesized soundtrack (no
third-party music). Frames are drawn with Pillow and piped to ffmpeg
(imageio-ffmpeg or --ffmpeg).
"""
import argparse
import math
import random
import struct
import subprocess
import sys
import wave
from array import array
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
W, H, FPS = 1920, 1080, 30
BEAT = 0.6                      # 100 BPM
DURATION = 51.0
CUTS = (4.8, 11.4, 17.4, 28.8, 34.8, 41.4, 45.0)   # iris transitions
INK = (35, 30, 86)
VIOLET = (72, 63, 134)
LAVENDER = (173, 160, 230)
MUTED = (72, 67, 101)
BLUE = (112, 162, 255)
GOLD = (240, 182, 70)
GREEN = (62, 125, 97)
BERRY = (138, 46, 74)
AMBER = (201, 138, 30)
FONT_DIR = Path('C:/Windows/Fonts')
NL = chr(10)

TEXT = {
    'en': dict(
        tagline='A desktop companion for Codex & Claude Code',
        ring_title='Every AI task becomes a star',
        ring_body='Blue for Codex, gold for Claude Code.' + NL + 'Click a star for its tokens, model and context.',
        overlay_title='Limits at a glance',
        overlay_body='Context, 5-hour and weekly limits left,' + NL + 'with reset countdowns, right above her head.',
        notify_title='She lets you know when it matters',
        notify_foot='Instant with Claude Code  ·  Do Not Disturb when you need to focus',
        toasts=[('Claude Code task finished', 'website'),
                ('Claude Code task hit an error', 'docs · rate_limit'),
                ('Codex is waiting for your approval', 'api-server')],
        hub_title='Tokens, cost and quotas',
        hub_unit='tokens tracked',
        hub_points=['Per conversation, project or overall', 'API-equivalent cost estimates',
                    'Unknown stays unknown, never guessed'],
        wb_title='A little workbench' + NL + 'for your day',
        wb_points=['Projects, todos and notes', 'Notification history', 'Personal reminders'],
        local_title='Local-first',
        local_points=['Nothing is uploaded', 'No conversation content stored', 'Free and open source'],
        outro_sub='Free for Windows 10 / 11',
        url='github.com/windknows-ai/petoken',
        codex='Codex', claude='Claude Code', app='Petoken',
    ),
}


def font(name, size):
    return ImageFont.truetype(str(FONT_DIR / name), size)


# --- motion curves --------------------------------------------------------
def clamp(x, lo=0.0, hi=1.0):
    return lo if x < lo else hi if x > hi else x


def ease_out(t):
    t = clamp(t)
    return 1 - (1 - t) ** 3


def ease_in(t):
    t = clamp(t)
    return t * t * t


def spring(t, freq=2.1, damping=0.38):
    """Damped spring from 0 to 1 with overshoot (AE 'elastic' feel)."""
    if t <= 0:
        return 0.0
    w = 2 * math.pi * freq
    wd = w * math.sqrt(1 - damping * damping)
    decay = math.exp(-damping * w * t)
    return 1 - decay * (math.cos(wd * t) + damping * w / wd * math.sin(wd * t))


def pop(t, start, freq=2.1, damping=0.38):
    return spring(t - start, freq, damping)


# --- drawing primitives -----------------------------------------------------
def text_image(value, fnt, fill=INK, spacing=10):
    probe = ImageDraw.Draw(Image.new('RGBA', (1, 1)))
    box = probe.multiline_textbbox((0, 0), value, font=fnt, spacing=spacing)
    img = Image.new('RGBA', (box[2] - box[0] + 8, box[3] - box[1] + 8), (0, 0, 0, 0))
    ImageDraw.Draw(img).multiline_text((4 - box[0], 4 - box[1]), value, font=fnt, fill=fill, spacing=spacing)
    return img


def with_alpha(img, alpha):
    if alpha >= 0.999:
        return img
    out = img.copy()
    out.putalpha(img.getchannel('A').point(lambda v: int(v * alpha)))
    return out


def draw(frame, img, cx, cy, scale=1.0, sx=1.0, sy=1.0, rot=0.0, alpha=1.0, anchor='center'):
    """Composite img transformed around its centre (or bottom-centre)."""
    alpha = clamp(alpha)
    if alpha <= 0.004 or scale <= 0.01:
        return
    w = max(1, int(round(img.width * scale * sx)))
    h = max(1, int(round(img.height * scale * sy)))
    out = img if (w, h) == img.size else img.resize((w, h), Image.BICUBIC)
    if abs(rot) > 0.05:
        out = out.rotate(rot, Image.BICUBIC, expand=True)
    x = cx - out.width / 2
    y = cy - out.height / 2 if anchor == 'center' else cy - out.height
    frame.alpha_composite(with_alpha(out, alpha), (int(round(x)), int(round(y))))


def fit(img, height=None, width=None):
    if height:
        return img.resize((round(img.width * height / img.height), height), Image.LANCZOS)
    return img.resize((width, round(img.height * width / img.width)), Image.LANCZOS)


def shadowed(img, radius=26, offset=14, strength=90):
    pad = radius * 2
    base = Image.new('RGBA', (img.width + pad * 2, img.height + pad * 2), (0, 0, 0, 0))
    shadow = Image.new('RGBA', base.size, (0, 0, 0, 0))
    alpha = img.getchannel('A').point(lambda v: strength if v > 8 else 0)
    shadow.paste((35, 30, 86, 255), (pad, pad + offset), alpha)
    base.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(radius)))
    base.alpha_composite(img, (pad, pad))
    return base


def rounded(img, radius=22):
    mask = Image.new('L', img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, img.width - 1, img.height - 1), radius, fill=255)
    out = img.convert('RGBA')
    out.putalpha(mask)
    return out


def pill(label, color, fnt):
    txt = text_image(label, fnt, INK)
    w, h = txt.width + 64, max(58, txt.height + 22)
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, w - 1, h - 1), h // 2, fill=(248, 246, 253, 240), outline=(129, 119, 159, 255), width=2)
    d.ellipse((20, h // 2 - 10, 40, h // 2 + 10), fill=color)
    img.alpha_composite(txt, (50, (h - txt.height) // 2))
    return shadowed(img, 10, 6, 60)


def toast(title, body, color, app):
    w, h = 660, 162
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, w - 1, h - 1), 24, fill=(251, 250, 254, 250), outline=(160, 152, 188, 255), width=2)
    d.rounded_rectangle((0, 0, 12, h - 1), 6, fill=color)
    d.ellipse((34, 32, 56, 54), fill=color)
    img.alpha_composite(text_image(app, font('segoeui.ttf', 24), MUTED), (68, 24))
    img.alpha_composite(text_image(title, font('seguisb.ttf', 34), INK), (32, 66))
    img.alpha_composite(text_image(body, font('segoeui.ttf', 28), MUTED), (34, 110))
    return shadowed(img, 18, 10, 70)


def check_badge(size=64, color=VIOLET):
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((0, 0, size - 1, size - 1), fill=color)
    d.line([(size * .28, size * .53), (size * .44, size * .68), (size * .73, size * .36)],
           fill=(255, 255, 255, 255), width=max(4, size // 11), joint='curve')
    return img


def sparkle(d, x, y, r, alpha, color=(255, 255, 255)):
    c = color + (int(clamp(alpha / 255) * 255),)
    d.polygon([(x, y - r), (x + r * .28, y - r * .28), (x + r, y), (x + r * .28, y + r * .28),
               (x, y + r), (x - r * .28, y + r * .28), (x - r, y), (x - r * .28, y - r * .28)], fill=c)


def burst(d, cx, cy, t, start, color=GOLD, count=10, r0=70, r1=190, length=46, width=7):
    """Radial line burst (shape-layer style) that flies out and fades."""
    p = (t - start) / 0.5
    if not 0 < p < 1:
        return
    inner = r0 + (r1 - r0) * ease_out(p)
    run = length * (1 - p)
    for i in range(count):
        a = 2 * math.pi * i / count + 0.3
        x0, y0 = cx + math.cos(a) * inner, cy + math.sin(a) * inner
        x1, y1 = cx + math.cos(a) * (inner + run), cy + math.sin(a) * (inner + run)
        d.line([(x0, y0), (x1, y1)], fill=color + (int(255 * (1 - p)),), width=max(1, int(width * (1 - p) + 1)))
    if p < .6:
        sparkle(d, cx + r1 * .8, cy - r1 * .6, 14 * (1 - p), 255 * (1 - p / .6), (255, 255, 255))


class Words:
    """A line (or lines) of text whose words pop in one after another."""

    def __init__(self, value, fnt, fill=INK, gap=0.06, line_gap=12):
        self.items = []
        space = fnt.getlength(' ')
        y = 0
        width = 0
        ascent, descent = fnt.getmetrics()
        line_h = ascent + descent
        for line in value.split(NL):
            x = 0
            for word in line.split(' '):
                advance = fnt.getlength(word)
                img = Image.new('RGBA', (int(advance) + 12, line_h + 8), (0, 0, 0, 0))
                ImageDraw.Draw(img).text((6, 4 + ascent), word, font=fnt, fill=fill, anchor='ls')
                self.items.append((img, x - 6, y))
                x += advance + space
            width = max(width, x - space)
            y += line_h + line_gap
        self.width, self.height, self.gap = width, y, gap

    def draw(self, frame, t, start, x0, y0, alpha=1.0):
        for index, (img, x, y) in enumerate(self.items):
            s = pop(t, start + index * self.gap, 2.4, 0.42)
            if s <= 0:
                continue
            draw(frame, img, x0 + x + img.width / 2, y0 + y + img.height / 2 + 46 * (1 - s),
                 scale=0.55 + 0.45 * s, alpha=alpha * clamp((t - start - index * self.gap) / 0.18))


# --- assets ---------------------------------------------------------------
class Assets:
    def __init__(self, folder, language):
        t = self.t = TEXT[language]
        sprite = lambda name, h=600: fit(Image.open(ROOT / 'assets/v1_1' / f'{name}.png').convert('RGBA'), height=h)
        self.idle, self.celebrate, self.sad, self.wave = (sprite(n) for n in ('idle', 'celebrate', 'sad', 'wave'))
        self.wave_small = sprite('wave', 470)
        cap = lambda name: Image.open(Path(folder) / f'{name}.png').convert('RGBA')
        self.ring = fit(cap('ring'), height=740)
        self.detail = shadowed(fit(cap('detail'), height=440))
        self.overlay_card = shadowed(fit(cap('overlay_card'), height=270), 16, 8, 70)
        self.ring_small = fit(cap('ring'), height=640)
        self.hub = shadowed(fit(cap('hub'), height=860))
        self.wb_home = shadowed(rounded(fit(cap('workbench_home'), width=1080)))
        self.wb_notify = shadowed(rounded(fit(cap('workbench_notifications'), width=1080)))
        h1 = font('seguisb.ttf', 70)
        body = font('segoeui.ttf', 38)
        self.letters = Words(' '.join(t['app']), font('segoeuib.ttf', 160))
        self.letters.items = [(img, x - index * font('segoeuib.ttf', 160).getlength(' '), y)
                              for index, (img, x, y) in enumerate(self.letters.items)]
        self.tagline = Words(t['tagline'], font('segoeuil.ttf', 46), VIOLET, gap=0.05)
        self.ring_title = Words(t['ring_title'], h1)
        self.ring_body = text_image(t['ring_body'], body, MUTED)
        self.pills = [pill(t['codex'], BLUE, font('seguisb.ttf', 30)), pill(t['claude'], GOLD, font('seguisb.ttf', 30))]
        self.overlay_title = Words(t['overlay_title'], h1)
        self.overlay_body = text_image(t['overlay_body'], body, MUTED)
        self.notify_title = Words(t['notify_title'], h1)
        self.notify_foot = text_image(t['notify_foot'], font('segoeui.ttf', 32), MUTED)
        self.toasts = [toast(a, b, c, t['app']) for (a, b), c in zip(t['toasts'], (GREEN, BERRY, AMBER))]
        self.hub_title = Words(t['hub_title'], h1)
        self.hub_unit = text_image(t['hub_unit'], font('segoeuil.ttf', 40), VIOLET)
        self.counter_font = font('segoeuib.ttf', 150)
        self.hub_points = [text_image(p, body) for p in t['hub_points']]
        self.wb_title = Words(t['wb_title'], h1)
        self.wb_points = [text_image(p, body) for p in t['wb_points']]
        self.local_title = Words(t['local_title'], font('segoeuib.ttf', 120), gap=0.0)
        self.local_points = [text_image(p, font('segoeui.ttf', 46)) for p in t['local_points']]
        self.check = check_badge(66)
        self.dot = check_badge(26, VIOLET)
        self.outro_title = Words(t['app'] + ' v1.5', font('segoeuib.ttf', 120), gap=0.08)
        self.outro_sub = text_image(t['outro_sub'], font('segoeuil.ttf', 46), VIOLET)
        self.url_font = font('seguisb.ttf', 46)
        self.background = self._background()
        rng = random.Random(7)
        self.stars = [(rng.uniform(0, W), rng.uniform(0, H), rng.uniform(4, 11), rng.uniform(0, 6.28),
                       rng.uniform(8, 22), rng.choice([(255, 255, 255), (255, 246, 214), (226, 236, 255)]))
                      for _ in range(52)]

    def _background(self):
        bg = Image.new('RGBA', (W, H))
        top, bottom = (234, 231, 246), (196, 190, 222)
        d = ImageDraw.Draw(bg)
        for y in range(H):
            k = y / (H - 1)
            d.line([(0, y), (W, y)], fill=tuple(round(a + (b - a) * k) for a, b in zip(top, bottom)) + (255,))
        glow = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        g = ImageDraw.Draw(glow)
        g.ellipse((-260, -240, 820, 620), fill=(255, 255, 255, 120))
        g.ellipse((1240, 520, 2240, 1380), fill=(173, 160, 230, 110))
        bg.alpha_composite(glow.filter(ImageFilter.GaussianBlur(140)))
        return bg


# --- scenes ---------------------------------------------------------------
def character(frame, img, cx, ground, t, start, mode='idle'):
    """The pet with motion: drop-in landing, breathing, jumps, droop, wave wobble."""
    k = t - start
    sx = sy = 1.0
    rot = 0.0
    y = ground
    if mode == 'drop':
        s = spring(k, 1.7, 0.30)
        y = ground - 620 * (1 - s)
        over = max(0.0, s - 1)          # Past the floor: squash.
        sy, sx = 1 - 1.6 * over, 1 + 1.6 * over
        if k < 0.25:                    # Falling: stretch.
            sy, sx = 1.08, 0.94
    elif mode == 'jump':
        p = clamp(k / 0.7)
        y = ground - 120 * math.sin(math.pi * p)
        if p < 0.12 or p > 0.9:
            sy, sx = 0.9, 1.08
        elif p < 0.5:
            sy, sx = 1.07, 0.95
        if k > 0.7:
            s = spring(k - 0.7, 3, 0.35)
            sy, sx = 1 - 0.08 * (1 - s), 1 + 0.08 * (1 - s)
    elif mode == 'droop':
        s = spring(k, 1.6, 0.5)
        y = ground + 18 * s
        sy, sx = 1 - 0.05 * s, 1 + 0.03 * s
        rot = 2.0 * math.sin(k * 2.2) * math.exp(-k * 0.8)
    elif mode == 'wave':
        rot = 4.5 * math.sin(k * 7.5) * math.exp(-k * 0.6)
    if mode != 'drop':
        breath = 0.012 * math.sin(t * 2.6)
        sy *= 1 + breath
        sx *= 1 - breath * 0.5
        y += 8 * math.sin(t * 1.5)
    draw(frame, img, cx, y, sx=sx, sy=sy, rot=rot, anchor='bottom')


def bullets(frame, items, t, start, x, y, step=70, icon=None):
    for index, img in enumerate(items):
        at = start + index * BEAT / 2
        s = pop(t, at, 2.4, 0.4)
        if s <= 0:
            continue
        cy = y + index * step
        draw(frame, icon, x + icon.width / 2, cy, scale=s)
        draw(frame, img, x + icon.width + 26 + img.width / 2 + 60 * (1 - s), cy, alpha=clamp((t - at) / 0.2))


def iris(frame, t):
    """Two-colour circle wipe closing over each cut, then opening from the centre."""
    diag = math.hypot(W, H)
    for cut in CUTS:
        if cut - 0.4 <= t < cut:
            p = (t - (cut - 0.4)) / 0.4
            ox, oy = W * 0.85, H * 0.2
            layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
            d = ImageDraw.Draw(layer)
            r1 = diag * ease_in(clamp(p * 1.25))
            r2 = diag * ease_in(clamp(p * 1.25 - 0.22))
            d.ellipse((ox - r1, oy - r1, ox + r1, oy + r1), fill=LAVENDER + (255,))
            if r2 > 0:
                d.ellipse((ox - r2, oy - r2, ox + r2, oy + r2), fill=VIOLET + (255,))
            frame.alpha_composite(layer)
        elif cut <= t < cut + 0.42:
            p = (t - cut) / 0.42
            r = diag * 0.6 * ease_out(p)
            mask = Image.new('L', (W, H), 255)
            ImageDraw.Draw(mask).ellipse((W / 2 - r, H / 2 - r, W / 2 + r, H / 2 + r), fill=0)
            cover = Image.new('RGBA', (W, H), VIOLET + (255,))
            cover.putalpha(mask)
            frame.alpha_composite(cover)


def render(a, t):
    frame = a.background.copy()
    fx = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(fx)
    for x, y, r, phase, drift, color in a.stars:
        yy = (y - drift * t) % H
        tw = 0.5 + 0.5 * math.sin(t * 1.9 + phase)
        sparkle(d, x + 8 * math.sin(t * .5 + phase), yy, r, 50 + 160 * tw, color)
    frame.alpha_composite(fx)
    fx = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(fx)

    # 1. Intro: the pet drops in and lands, title letters bounce in.
    if t < CUTS[0]:
        character(frame, a.idle, 470, 900, t, 0.3, 'drop' if t < 2.0 else 'idle')
        burst(d, 470, 860, t, 0.75, LAVENDER, 12, 140, 300, 60, 8)
        for index, (img, x, y) in enumerate(a.letters.items):
            s = pop(t, 1.2 + index * 0.07, 2.6, 0.32)
            if s > 0:   # Each letter drops in, stretched, and lands on the baseline.
                draw(frame, img, 860 + x + img.width / 2, 250 + img.height, sx=1 + 0.25 * (1 - s), sy=max(0.05, s),
                     alpha=clamp((t - 1.2 - index * 0.07) / 0.12), anchor='bottom')
        a.tagline.draw(frame, t, 2.4, 870, 520)

    # 2. Task stars.
    elif t < CUTS[1]:
        s0 = CUTS[0] + 0.15
        s = pop(t, s0, 1.8, 0.4)
        draw(frame, a.ring, 520, 560 + 8 * math.sin(t * 1.5), scale=0.6 + 0.4 * s, rot=-6 * (1 - s),
             alpha=clamp((t - s0) / 0.2))
        a.ring_title.draw(frame, t, s0 + 0.3, 1000, 230)
        draw(frame, a.ring_body, 1000 + a.ring_body.width / 2, 400, alpha=clamp((t - s0 - 0.9) / 0.4),
             scale=0.96 + 0.04 * ease_out((t - s0 - 0.9) / 0.4))
        x = 1000
        for index, img in enumerate(a.pills):
            at = s0 + 1.2 + index * BEAT / 2
            draw(frame, img, x + img.width / 2, 540, scale=pop(t, at, 2.6, 0.32))
            x += img.width + 10
        ds = pop(t, s0 + 2.4, 2.0, 0.36)
        draw(frame, a.detail, 1500, 800 - 80 * (1 - ds), scale=0.4 + 0.6 * ds, rot=8 * (1 - ds),
             alpha=clamp((t - s0 - 2.4) / 0.15))
        burst(d, 1500, 760, t, s0 + 2.55, GOLD)

    # 3. Usage card: pops out of her head.
    elif t < CUTS[2]:
        s0 = CUTS[1] + 0.15
        character(frame, a.ring_small, 520, 1030, t, s0, 'idle')
        cs = pop(t, s0 + 0.6, 2.0, 0.34)
        draw(frame, a.overlay_card, 520, 330 + 120 * (1 - cs), sx=0.3 + 0.7 * cs, sy=0.1 + 0.9 * cs,
             alpha=clamp((t - s0 - 0.6) / 0.12))
        burst(d, 520, 330, t, s0 + 0.75, BLUE, 12, 150, 290)
        a.overlay_title.draw(frame, t, s0 + 0.3, 1000, 360)
        draw(frame, a.overlay_body, 1000 + a.overlay_body.width / 2, 520, alpha=clamp((t - s0 - 1.0) / 0.4))

    # 4. Notifications: three reactions, each with a toast.
    elif t < CUTS[3]:
        s0 = CUTS[2] + 0.15
        a.notify_title.draw(frame, t, s0, 110, 80)
        draw(frame, a.notify_foot, W - 110 - a.notify_foot.width / 2, 1000, alpha=clamp((t - s0 - 1.0) / 0.4))
        beats = [(CUTS[2] + 0.6, a.celebrate, 'jump', GREEN), (CUTS[2] + 4.2, a.sad, 'droop', BERRY),
                 (CUTS[2] + 7.8, a.wave, 'wave', AMBER)]
        for index, (start, sprite, mode, color) in enumerate(beats):
            end = beats[index + 1][0] - 0.3 if index < 2 else CUTS[3]
            if not start - 0.3 <= t < end:
                continue
            if t < start:   # New pose springs up from a gentle squash.
                k = spring(t - start + 0.3, 3.0, 0.35)
                draw(frame, sprite, 520, 980, sx=1 + 0.18 * (1 - k), sy=0.62 + 0.38 * k,
                     alpha=clamp((t - start + 0.3) / 0.08), anchor='bottom')
            else:
                character(frame, sprite, 520, 980, t, start, mode)
            ts = pop(t, start + 0.15, 1.9, 0.33)
            draw(frame, a.toasts[index], 2400 - (2400 - 1340) * ts, 470, rot=-5 * (1 - ts),
                 alpha=clamp((t - start - 0.15) / 0.1))
            burst(d, 520, 520, t, start + 0.1, color, 12, 220, 360)

    # 5. Hub: counter ticks up, points pop, the panel springs in.
    elif t < CUTS[4]:
        s0 = CUTS[3] + 0.15
        a.hub_title.draw(frame, t, s0, 110, 160)
        p = ease_out((t - s0 - 0.5) / 1.6)
        if t > s0 + 0.5:
            value = text_image(f'{1.38 * p:.2f}M', a.counter_font, VIOLET)
            ks = pop(t, s0 + 0.5, 2.4, 0.35)
            draw(frame, value, 110 + value.width / 2, 380, scale=0.7 + 0.3 * ks)
            draw(frame, a.hub_unit, 120 + a.hub_unit.width / 2, 490, alpha=clamp((t - s0 - 0.9) / 0.3))
        bullets(frame, a.hub_points, t, s0 + 1.8, 120, 620, 78, a.dot)
        hs = pop(t, s0 + 0.3, 1.7, 0.38)
        draw(frame, a.hub, 1500, 560 + 160 * (1 - hs), scale=0.7 + 0.3 * hs, rot=5 * (1 - hs),
             alpha=clamp((t - s0 - 0.3) / 0.15))

    # 6. Workbench: home springs up, then flips to Notifications.
    elif t < CUTS[5]:
        s0 = CUTS[4] + 0.15
        a.wb_title.draw(frame, t, s0, 100, 250)
        bullets(frame, a.wb_points, t, s0 + 1.2, 104, 520, 74, a.dot)
        ws = pop(t, s0 + 0.3, 1.7, 0.4)
        flip_at = s0 + 3.3
        if t < flip_at:
            draw(frame, a.wb_home, 1300, 560 + 200 * (1 - ws), scale=0.75 + 0.25 * ws,
                 alpha=clamp((t - s0 - 0.3) / 0.15))
        f = clamp((t - flip_at) / 0.18)
        if t >= flip_at and f < 1:
            draw(frame, a.wb_home, 1300, 560, sx=max(0.02, 1 - f))
        if t >= flip_at + 0.18:
            fs = pop(t, flip_at + 0.18, 2.4, 0.4)
            draw(frame, a.wb_notify, 1300, 560, sx=max(0.02, fs))
            burst(d, 1300, 560, t, flip_at + 0.25, LAVENDER, 14, 420, 620, 70, 9)

    # 7. Local-first: badges bounce in one by one.
    elif t < CUTS[6]:
        s0 = CUTS[5] + 0.15
        a.local_title.draw(frame, t, s0, (W - a.local_title.width) / 2, 230)
        for index, img in enumerate(a.local_points):
            at = s0 + 0.6 + index * BEAT
            s = pop(t, at, 2.4, 0.32)
            if s <= 0:
                continue
            y = 460 + index * 110
            x0 = (W - 700) / 2
            draw(frame, a.check, x0 + 33, y, scale=s, rot=-30 * (1 - s))
            draw(frame, img, x0 + 100 + img.width / 2 + 50 * (1 - s), y, alpha=clamp((t - at) / 0.2))
            burst(d, x0 + 33, y, t, at + 0.05, GOLD, 8, 40, 90, 24, 5)

    # 8. Outro: wave, title pop, URL typed out.
    else:
        s0 = CUTS[6] + 0.15
        cs = pop(t, s0, 1.8, 0.32)
        if t < s0 + 1.0:
            draw(frame, a.wave_small, W / 2, 560 + 300 * (1 - cs), sx=1 + 0.12 * (1 - cs), sy=max(0.05, cs),
                 anchor='bottom')
        else:
            character(frame, a.wave_small, W / 2, 560, t, s0 + 1.0, 'wave')
        a.outro_title.draw(frame, t, s0 + 0.6, (W - a.outro_title.width) / 2, 600)
        draw(frame, a.outro_sub, W / 2, 800, alpha=clamp((t - s0 - 1.4) / 0.4))
        typed = a.t['url'][:int(max(0, t - s0 - 2.0) / 0.045)]
        if typed:
            done = len(typed) == len(a.t['url'])
            caret = '|' if not done or int(t * 2.5) % 2 == 0 else ' '
            url = text_image(typed + caret, a.url_font, INK)
            full = a.url_font.getlength(a.t['url'])
            draw(frame, url, (W - full) / 2 + url.width / 2, 900)
        fade = clamp((t - (DURATION - 0.8)) / 0.8)
        if fade:
            frame.alpha_composite(Image.new('RGBA', (W, H), (234, 231, 246, int(255 * fade))))

    frame.alpha_composite(fx)
    iris(frame, t)
    return frame.convert('RGB')


# --- soundtrack -----------------------------------------------------------
def soundtrack(path, seconds=DURATION, rate=44100):
    """100 BPM: pad, bell arps, soft kick/hats, whooshes on cuts, pops on hits."""
    n = int(seconds * rate)
    buf = array('f', [0.0]) * n
    rng = random.Random(3)
    midi = lambda m: 440.0 * 2 ** ((m - 69) / 12)
    two_pi = 2 * math.pi

    def tone(freq, start, length, amp, attack=0.005, release=0.05, decay=None, detune=0.0, sweep=0.0):
        i0 = int(start * rate)
        i1 = min(n, int((start + length + release) * rate))
        att, rel_at = attack * rate, length * rate
        phase = phase2 = 0.0
        for i in range(max(0, i0), i1):
            k = i - i0
            f = freq * (1 + sweep * math.exp(-k / (0.04 * rate))) if sweep else freq
            phase += two_pi * f / rate
            phase2 += two_pi * f * (1 + detune) / rate
            env = k / att if k < att else 1.0
            if k > rel_at:
                env *= max(0.0, 1 - (k - rel_at) / (release * rate))
            if decay:
                env *= math.exp(-k / (decay * rate))
            buf[i] += amp * env * (math.sin(phase) + (0.6 * math.sin(phase2) if detune else 0.0))

    def noise(start, length, amp, rise=False):
        i0 = int(start * rate)
        last = 0.0
        for k in range(int(length * rate)):
            i = i0 + k
            if not 0 <= i < n:
                continue
            p = k / (length * rate)
            env = (p ** 2) if rise else math.exp(-p * 6)
            last = 0.7 * last + 0.3 * (rng.random() * 2 - 1)     # Softened noise.
            buf[i] += amp * env * last

    chords = [(48, 55, 59, 62, 64), (45, 52, 55, 59, 60), (41, 48, 52, 55, 57), (43, 50, 55, 57, 62)]
    bar = BEAT * 8
    start, index = 0.0, 0
    while start < seconds:
        chord = chords[index % 4]
        for m in chord:
            tone(midi(m), start, bar, 0.018, 1.0, 1.6, detune=0.003)
        if start >= CUTS[0] - 0.01:
            arp = [chord[1] + 12, chord[3] + 12, chord[2] + 12, chord[4] + 12]
            for step in range(16):
                at = start + step * BEAT / 2
                if at < seconds - 3:
                    tone(midi(arp[step % 4]), at, 0.04, 0.026, decay=0.45)
        index += 1
        start += bar
    beat_t = CUTS[0]
    while beat_t < CUTS[6] + BEAT * 6:
        tone(110, beat_t, 0.16, 0.22, attack=0.002, release=0.05, decay=0.09, sweep=1.4)   # Soft kick.
        noise(beat_t + BEAT / 2, 0.05, 0.05)                                                # Hat.
        beat_t += BEAT
    for cut in CUTS:
        noise(cut - 0.45, 0.45, 0.16, rise=True)                                            # Whoosh.
    hits = [0.75, 1.2, CUTS[0] + 2.55, CUTS[1] + 0.75, CUTS[2] + 0.7, CUTS[2] + 4.3, CUTS[2] + 7.9,
            CUTS[4] + 3.55, CUTS[5] + 0.8, CUTS[5] + 1.4, CUTS[5] + 2.0, CUTS[6] + 0.25]
    for at in hits:
        tone(900, at, 0.06, 0.07, decay=0.05, sweep=-0.45)                                  # Pop.
        for m, delay in ((84, 0.0), (88, 0.07), (91, 0.14)):
            tone(midi(m), at + delay, 0.04, 0.025, decay=0.5)
    peak = max(abs(v) for v in buf) or 1.0
    fade_in, fade_out = 0.8 * rate, 2.5 * rate
    with wave.open(str(path), 'wb') as out:
        out.setnchannels(2)
        out.setsampwidth(2)
        out.setframerate(rate)
        frames = bytearray()
        for i, v in enumerate(buf):
            g = min(1.0, i / fade_in, (n - i) / fade_out)
            s = int(max(-1.0, min(1.0, v / peak * 0.85 * g)) * 32767)
            frames += struct.pack('<hh', s, s)
        out.writeframes(bytes(frames))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('assets', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--language', default='en', choices=sorted(TEXT))
    parser.add_argument('--ffmpeg', default=None)
    parser.add_argument('--preview', type=float, nargs='*', help='Save stills at these seconds and exit')
    args = parser.parse_args()
    assets = Assets(args.assets, args.language)
    if args.preview:
        for sec in args.preview:
            render(assets, sec).save(args.output.with_name(f'{args.output.stem}_{sec:05.2f}s.png'))
        return
    ffmpeg = args.ffmpeg
    if ffmpeg is None:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    music = args.output.with_suffix('.wav')
    soundtrack(music)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen([ffmpeg, '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
                             '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-', '-i', str(music),
                             '-c:v', 'libx264', '-preset', 'medium', '-crf', '17', '-pix_fmt', 'yuv420p',
                             '-c:a', 'aac', '-b:a', '192k', '-shortest', '-movflags', '+faststart',
                             str(args.output)], stdin=subprocess.PIPE)
    total = int(DURATION * FPS)
    for index in range(total):
        proc.stdin.write(render(assets, index / FPS).tobytes())
        if index % 150 == 0:
            print(f'frame {index}/{total}', flush=True)
    proc.stdin.close()
    proc.wait()
    music.unlink(missing_ok=True)
    print('wrote', args.output, 'exit', proc.returncode)
    sys.exit(proc.returncode)


if __name__ == '__main__':
    main()
