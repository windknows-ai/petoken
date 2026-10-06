"""Render the Petoken promo video from real UI captures (see promo_capture.py).

Usage:
    python tools/promo_capture.py ASSETS
    python tools/promo_video.py ASSETS OUT.mp4 [--language en] [--ffmpeg PATH]

1920x1080, 30 fps, about 52 s, with a procedurally synthesized soundtrack
(no third-party music). Frames are drawn with Pillow and piped to ffmpeg.
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
DURATION = 52.0
INK = (35, 30, 86)
VIOLET = (72, 63, 134)
MUTED = (72, 67, 101)
BLUE = (112, 162, 255)
GOLD = (240, 182, 70)
GREEN = (62, 125, 97)
BERRY = (138, 46, 74)
AMBER = (201, 138, 30)
FONT_DIR = Path('C:/Windows/Fonts')

TEXT = {
    'en': dict(
        tagline='A desktop companion for Codex & Claude Code',
        ring_title='Every AI task becomes a star',
        ring_body='Blue for Codex, gold for Claude Code.\nClick a star to see its tokens, model and context.',
        overlay_title='Limits at a glance',
        overlay_body='Context, 5-hour and weekly limits left,\nwith reset countdowns, right above her head.',
        notify_title='She lets you know when it matters',
        notify_foot='Instant with Claude Code  ·  Do Not Disturb when you need to focus',
        toasts=[('Claude Code task finished', 'website'),
                ('Claude Code task hit an error', 'docs · rate_limit'),
                ('Codex is waiting for your approval', 'api-server')],
        hub_title='Tokens, cost and quotas, honestly',
        hub_points=['Per conversation, per project or overall', 'API-equivalent cost estimates',
                    'Unknown stays unknown, never guessed'],
        wb_title='A little workbench'+chr(10)+'for your day',
        wb_points=['Projects, todos and notes', 'Notification history', 'Personal reminders'],
        local_title='Local-first',
        local_points=['Nothing is uploaded', 'No conversation content is stored', 'Free and open source'],
        outro_sub='Free for Windows 10 / 11',
        url='github.com/windknows-ai/petoken',
        codex='Codex', claude='Claude Code', app='Petoken',
    ),
}


def font(name, size):
    return ImageFont.truetype(str(FONT_DIR / name), size)


# --- easing -------------------------------------------------------------
def clamp(x, lo=0.0, hi=1.0):
    return lo if x < lo else hi if x > hi else x


def ease_out(t):
    t = clamp(t)
    return 1 - (1 - t) ** 3


def ease_back(t):
    t = clamp(t)
    c = 1.4
    return 1 + (c + 1) * (t - 1) ** 3 + c * (t - 1) ** 2


def window(t, start, end, fade_in=0.55, fade_out=0.45):
    """Opacity of a scene element alive between start and end."""
    if t < start or t > end:
        return 0.0
    return min(ease_out((t - start) / fade_in), clamp((end - t) / fade_out))


# --- drawing helpers ----------------------------------------------------
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


def paste(frame, img, x, y, alpha=1.0):
    if alpha <= 0.003:
        return
    frame.alpha_composite(with_alpha(img, alpha), (int(round(x)), int(round(y))))


def fit(img, height=None, width=None):
    if height:
        return img.resize((round(img.width * height / img.height), height), Image.LANCZOS)
    return img.resize((width, round(img.height * width / img.width)), Image.LANCZOS)


def shadowed(img, radius=26, offset=14, strength=90):
    """Soft drop shadow so captured windows sit on the background."""
    pad = radius * 2
    base = Image.new('RGBA', (img.width + pad * 2, img.height + pad * 2), (0, 0, 0, 0))
    shadow = Image.new('RGBA', base.size, (0, 0, 0, 0))
    alpha = img.getchannel('A').point(lambda v: strength if v > 8 else 0)
    shadow.paste((35, 30, 86, 255), (pad, pad + offset), alpha)
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius))
    base.alpha_composite(shadow)
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
    w, h = txt.width + 64, max(54, txt.height + 22)
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, w - 1, h - 1), h // 2, fill=(246, 244, 252, 235), outline=(129, 119, 159, 255), width=2)
    d.ellipse((20, h // 2 - 9, 38, h // 2 + 9), fill=color)
    img.alpha_composite(txt, (48, (h - txt.height) // 2))
    return img


def toast(title, body, color, f_title, f_body, f_app, app):
    w, h = 640, 158
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, w - 1, h - 1), 22, fill=(250, 249, 253, 248), outline=(160, 152, 188, 255), width=2)
    d.ellipse((30, 34, 50, 54), fill=color)
    img.alpha_composite(text_image(app, f_app, MUTED), (62, 26))
    img.alpha_composite(text_image(title, f_title, INK), (28, 66))
    img.alpha_composite(text_image(body, f_body, MUTED), (30, 108))
    return shadowed(img, radius=18, offset=10, strength=70)


def bullet_list(points, fnt, color=VIOLET):
    rows = [text_image(p, fnt, INK) for p in points]
    gap = 26
    h = sum(r.height for r in rows) + gap * (len(rows) - 1)
    img = Image.new('RGBA', (max(r.width for r in rows) + 52, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    y = 0
    for r in rows:
        cy = y + r.height // 2 + 2
        d.ellipse((4, cy - 8, 20, cy + 8), fill=color)
        img.alpha_composite(r, (44, y))
        y += r.height + gap
    return img


def sparkle(draw, x, y, r, alpha, color=(255, 255, 255)):
    c = color + (int(alpha),)
    draw.polygon([(x, y - r), (x + r * .28, y - r * .28), (x + r, y), (x + r * .28, y + r * .28),
                  (x, y + r), (x - r * .28, y + r * .28), (x - r, y), (x - r * .28, y - r * .28)], fill=c)


# --- scene assets -------------------------------------------------------
class Assets:
    def __init__(self, folder, language):
        t = TEXT[language]
        self.t = t
        sprite = lambda name: fit(Image.open(ROOT / 'assets/v1_1' / f'{name}.png').convert('RGBA'), height=640)
        self.idle, self.celebrate, self.sad, self.wave = (sprite(n) for n in ('idle', 'celebrate', 'sad', 'wave'))
        self.wave_small = fit(self.wave, height=520)
        cap = lambda name: Image.open(Path(folder) / f'{name}.png').convert('RGBA')
        self.ring = fit(cap('ring'), height=760)
        self.detail = shadowed(fit(cap('detail'), height=430))
        self.overlay = fit(cap('overlay'), height=820)
        self.hub = shadowed(fit(cap('hub'), height=860))
        self.wb_home = shadowed(rounded(fit(cap('workbench_home'), width=1100)))
        self.wb_notify = shadowed(rounded(fit(cap('workbench_notifications'), width=1100)))
        f_hero = font('segoeuib.ttf', 150)
        f_h1 = font('seguisb.ttf', 68)
        f_body = font('segoeui.ttf', 38)
        f_pill = font('seguisb.ttf', 30)
        self.title = text_image(t['app'], f_hero, INK)
        self.tagline = text_image(t['tagline'], font('segoeuil.ttf', 46), VIOLET)
        self.ring_title = text_image(t['ring_title'], f_h1)
        self.ring_body = text_image(t['ring_body'], f_body, MUTED)
        self.pill_codex = pill(t['codex'], BLUE, f_pill)
        self.pill_claude = pill(t['claude'], GOLD, f_pill)
        self.overlay_title = text_image(t['overlay_title'], f_h1)
        self.overlay_body = text_image(t['overlay_body'], f_body, MUTED)
        self.notify_title = text_image(t['notify_title'], f_h1)
        self.notify_foot = text_image(t['notify_foot'], font('segoeui.ttf', 32), MUTED)
        colors = (GREEN, BERRY, AMBER)
        self.toasts = [toast(a, b, c, font('seguisb.ttf', 34), font('segoeui.ttf', 28), font('segoeui.ttf', 24), t['app'])
                       for (a, b), c in zip(t['toasts'], colors)]
        self.hub_title = text_image(t['hub_title'], f_h1)
        self.hub_points = bullet_list(t['hub_points'], f_body)
        self.wb_title = text_image(t['wb_title'], f_h1)
        self.wb_points = bullet_list(t['wb_points'], f_body)
        self.local_title = text_image(t['local_title'], font('segoeuib.ttf', 110))
        self.local_points = bullet_list(t['local_points'], font('segoeui.ttf', 44))
        self.outro_title = text_image(t['app'] + ' v1.5', font('segoeuib.ttf', 120))
        self.outro_sub = text_image(t['outro_sub'], font('segoeuil.ttf', 46), VIOLET)
        self.url = text_image(t['url'], font('seguisb.ttf', 44), INK)
        self.background = self._background()
        rng = random.Random(7)
        self.stars = [(rng.uniform(0, W), rng.uniform(0, H), rng.uniform(4, 11), rng.uniform(0, 6.28),
                       rng.uniform(6, 18), rng.choice([(255, 255, 255), (255, 246, 214), (226, 236, 255)]))
                      for _ in range(46)]

    def _background(self):
        bg = Image.new('RGBA', (W, H))
        top, bottom = (233, 230, 245), (196, 190, 222)
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


# --- frame --------------------------------------------------------------
def render(a, t):
    frame = a.background.copy()
    layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for x, y, r, phase, drift, color in a.stars:
        yy = (y - drift * t) % H
        tw = 0.5 + 0.5 * math.sin(t * 1.6 + phase)
        sparkle(d, x + 6 * math.sin(t * .4 + phase), yy, r, 60 + 150 * tw, color)
    frame.alpha_composite(layer)
    float_y = 10 * math.sin(t * 1.4)

    # 1. Intro 0-5
    al = window(t, 0.0, 5.0, 1.2)
    if al:
        rise = 60 * (1 - ease_out(t / 1.4))
        paste(frame, a.idle, 150, 230 + rise + float_y, al)
        k = window(t, 1.0, 5.0, 0.8)
        paste(frame, a.title, 820, 330 + 30 * (1 - ease_out((t - 1.0) / 0.8)), k)
        k2 = window(t, 1.7, 5.0, 0.8)
        paste(frame, a.tagline, 830, 520 + 20 * (1 - ease_out((t - 1.7) / 0.8)), k2)

    # 2. Ring 5-12
    al = window(t, 5.0, 12.0)
    if al:
        s = ease_out((t - 5.0) / 0.9)
        paste(frame, a.ring, 120 - 40 * (1 - s), 170 + float_y, al)
        paste(frame, a.ring_title, 1010, 230 + 24 * (1 - s), al)
        paste(frame, a.ring_body, 1012, 340 + 24 * (1 - s), window(t, 5.5, 12.0))
        paste(frame, a.pill_codex, 1012, 500, window(t, 6.1, 12.0))
        paste(frame, a.pill_claude, 1012 + a.pill_codex.width + 22, 500, window(t, 6.4, 12.0))
        k = window(t, 8.3, 12.0, 0.6)
        paste(frame, a.detail, 1210 + 80 * (1 - ease_out((t - 8.3) / 0.6)), 590, k)

    # 3. Overlay 12-19
    al = window(t, 12.0, 19.0)
    if al:
        s = ease_out((t - 12.0) / 0.9)
        paste(frame, a.overlay, 170, 140 + 50 * (1 - s) + float_y * .6, al)
        paste(frame, a.overlay_title, 1000, 360 + 24 * (1 - s), al)
        paste(frame, a.overlay_body, 1002, 470 + 24 * (1 - s), window(t, 12.5, 19.0))

    # 4. Notifications 19-30
    al = window(t, 19.0, 30.0)
    if al:
        paste(frame, a.notify_title, 110, 90, al)
        paste(frame, a.notify_foot, 112, 950, window(t, 20.0, 30.0))
        beats = [(19.6, 23.2, a.celebrate, 0), (23.2, 26.8, a.sad, 1), (26.8, 30.0, a.wave, 2)]
        for start, end, sprite, index in beats:
            k = window(t, start, end, 0.35, 0.3)
            if not k:
                continue
            hop = -46 * math.sin(math.pi * clamp((t - start) / 0.5)) if index != 1 else 14 * clamp((t - start) / 0.6)
            paste(frame, sprite, 230, 250 + hop + (float_y if index != 1 else 0), k)
            slide = ease_back((t - start - 0.25) / 0.6)
            paste(frame, a.toasts[index], 2000 - (2000 - 1080) * slide, 380, window(t, start + 0.25, end, 0.3, 0.3))

    # 5. Hub 30-36
    al = window(t, 30.0, 36.0)
    if al:
        s = ease_out((t - 30.0) / 0.9)
        paste(frame, a.hub_title, 120, 280 + 24 * (1 - s), al)
        paste(frame, a.hub_points, 124, 420, window(t, 30.6, 36.0))
        paste(frame, a.hub, 1190 + 70 * (1 - s), 60, al)

    # 6. Workbench 36-43
    al = window(t, 36.0, 43.0)
    if al:
        s = ease_out((t - 36.0) / 0.9)
        paste(frame, a.wb_title, 100, 260 + 24 * (1 - s), al)
        paste(frame, a.wb_points, 104, 480, window(t, 36.6, 43.0))
        swap = clamp((t - 39.6) / 0.6)
        paste(frame, a.wb_home, 700 + 70 * (1 - s), 150, al * (1 - swap))
        paste(frame, a.wb_notify, 700 + 70 * (1 - s), 150, al * swap)

    # 7. Local-first 43-46.5
    al = window(t, 43.0, 46.5)
    if al:
        paste(frame, a.local_title, (W - a.local_title.width) / 2, 300, al)
        paste(frame, a.local_points, (W - a.local_points.width) / 2, 480, window(t, 43.4, 46.5))

    # 8. Outro 46.5-52
    al = window(t, 46.5, 52.1, 0.7, 0.9)
    if al:
        paste(frame, a.wave_small, (W - a.wave_small.width) / 2, 80 + float_y, al)
        paste(frame, a.outro_title, (W - a.outro_title.width) / 2, 610, window(t, 47.0, 52.1, 0.7, 0.9))
        paste(frame, a.outro_sub, (W - a.outro_sub.width) / 2, 780, window(t, 47.5, 52.1, 0.7, 0.9))
        paste(frame, a.url, (W - a.url.width) / 2, 870, window(t, 47.9, 52.1, 0.7, 0.9))
    return frame.convert('RGB')


# --- music --------------------------------------------------------------
def soundtrack(path, seconds=DURATION, rate=44100):
    """Soft synth pad, bell arpeggios and three notification chimes."""
    n = int(seconds * rate)
    buf = array('f', [0.0]) * n
    midi = lambda m: 440.0 * 2 ** ((m - 69) / 12)
    chords = [(48, 55, 59, 62, 64), (45, 52, 55, 59, 60), (41, 48, 52, 55, 57), (43, 50, 55, 57, 62)]
    beat = 60 / 84
    bar = beat * 8
    two_pi = 2 * math.pi

    def add_tone(freq, start, length, amp, attack, release, detune=0.0, decay=None):
        i0, i1 = int(start * rate), min(n, int((start + length + release) * rate))
        w1, w2 = two_pi * freq / rate, two_pi * freq * (1 + detune) / rate
        att, rel_start = attack * rate, (length) * rate
        for i in range(max(0, i0), i1):
            k = i - i0
            env = k / att if k < att else 1.0
            if k > rel_start:
                env *= max(0.0, 1 - (k - rel_start) / (release * rate))
            if decay:
                env *= math.exp(-k / (decay * rate))
            buf[i] += amp * env * (math.sin(w1 * k) + (0.6 * math.sin(w2 * k) if detune else 0.0))

    index = 0
    start = 0.0
    while start < seconds:
        chord = chords[index % len(chords)]
        for m in chord:
            add_tone(midi(m), start, bar, 0.022, 1.4, 1.8, detune=0.003)
        if start >= 2.0:
            arp = [chord[1] + 12, chord[2] + 12, chord[3] + 12, chord[4] + 12]
            for step in range(16):
                note_t = start + step * beat / 2
                if note_t < seconds - 3:
                    add_tone(midi(arp[(step * 3) % 4]), note_t, 0.05, 0.03, 0.005, 0.05, decay=0.55)
        index += 1
        start += bar
    for at in (19.85, 23.45, 27.05):  # Notification chimes.
        for m, delay in ((84, 0.0), (88, 0.09), (91, 0.18)):
            add_tone(midi(m), at + delay, 0.05, 0.05, 0.004, 0.05, decay=0.7)
    peak = max(abs(v) for v in buf) or 1.0
    fade_in, fade_out = 1.5 * rate, 3.0 * rate
    with wave.open(str(path), 'wb') as out:
        out.setnchannels(2)
        out.setsampwidth(2)
        out.setframerate(rate)
        frames = bytearray()
        for i, v in enumerate(buf):
            g = min(1.0, i / fade_in, (n - i) / fade_out)
            s = int(max(-1.0, min(1.0, v / peak * 0.8 * g)) * 32767)
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
            render(assets, sec).save(args.output.with_name(f'{args.output.stem}_{sec:05.1f}s.png'))
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
                             '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p',
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
