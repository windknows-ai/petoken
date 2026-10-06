"""Render the Petoken promo video: the companion introduces herself.

Usage:
    python tools/promo_capture.py ASSETS
    python tools/promo_video.py ASSETS OUT.mp4 [--language en] [--ffmpeg PATH]
    python tools/promo_video.py ASSETS OUT.mp4 --preview 3.2 9.5   # stills only

1920x1080, 30 fps, about 71 s at 120 BPM. Every frame is drawn in code
(Pillow) from the real artwork and real UI captures: springs, squash and
stretch, speech bubbles, a code-drawn 3D star ring, a typing terminal,
live data visualisation, glitch and pixel transitions. The soundtrack and
every sound effect are synthesized here (no third-party audio). Frames are
piped to ffmpeg (imageio-ffmpeg or --ffmpeg).
"""
import argparse
import math
import re
import random
import struct
import subprocess
import sys
import wave
from array import array
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
W, H, FPS = 1920, 1080, 30
BEAT = 0.5                       # 120 BPM
DURATION = 71.0
NL = chr(10)
INK = (35, 30, 86)
VIOLET = (72, 63, 134)
LAVENDER = (173, 160, 230)
MUTED = (72, 67, 101)
BLUE = (112, 162, 255)
GOLD = (240, 182, 70)
GREEN = (62, 125, 97)
BERRY = (138, 46, 74)
AMBER = (201, 138, 30)
WHITE = (255, 255, 255)
FONT_DIR = Path('C:/Windows/Fonts')
SYMBOLS = 'msgothic.ttc'         # Has the music notes, arrows, refresh and check glyphs.
CJK = 'msyh.ttc'

# Scene boundaries (seconds) and the transition that opens each scene.
SCENES = [('boot', 0.0), ('hello', 2.5), ('react', 7.0), ('term', 14.0), ('ring', 22.0),
          ('limits', 29.0), ('stats', 37.0), ('notify', 45.0), ('workbench', 53.0),
          ('custom', 58.5), ('local', 62.5), ('outro', 65.0)]
TRANSITIONS = {2.5: 'flash', 7.0: 'iris', 14.0: 'stripes', 22.0: 'iris', 29.0: 'glitch', 37.0: 'pixel',
               45.0: 'stripes', 53.0: 'iris', 58.5: 'stripes', 62.5: 'iris', 65.0: 'flash'}

TEXT = {
    'en': dict(
        boot='> petoken.exe',
        hi='Hi!', hello='I\'m Petoken!', buddy='Your desktop buddy for',
        codex='Codex', claude='Claude Code', amp='&',
        react_title='I work when you work',
        typing='You type, I type.', music='Music on? I vibe along.', song='Lo-fi Beats · Midnight Study',
        mic='On a call? Mic\'s on!',
        term1='Give a task to Codex or Claude...', term2='...and it becomes one of my stars!',
        cmd_claude='claude "add dark mode to the website"', out_claude=['Reading 12 files...', 'Updated styles.css'],
        cmd_codex='codex "fix the login bug in api-server"', out_codex=['Running tests...', '42 passed'],
        ring1='Blue for Codex, gold for Claude Code.', ring2='Click a star for its details.',
        pages='8+ tasks? I page them.',
        limits1='I watch your limits...', limits_note='Only for the apps you have open',
        bar_ctx='Context', bar_5h='5-hour', bar_week='Weekly', left='left', left_fmt='{v}% left',
        sync='Claude Pro/Max limits: one switch in Settings',
        stats1='...and count every token, honestly.', tokens='tokens', scopes=['Conversation', 'Project', 'Global'],
        breakdown='By model · conversation · date',
        notify=[('Done? I cheer!', 'Claude Code task finished', 'website'),
                ('Error? I\'ll tell you.', 'Claude Code task hit an error', 'docs · rate_limit'),
                ('Need your OK? I wave!', 'Codex is waiting for your approval', 'api-server')],
        dnd='Do Not Disturb · 22:00-08:00', low='5-hour limit low? I\'ll warn you.',
        wb='I keep your todos,' + NL + 'notes and reminders too.',
        wb_tags=['Projects', 'Todos', 'Notes', 'Reminders', 'Getting started guide'],
        custom='Make me yours!', size='Size', ontop='Always on top',
        local='Everything stays on your PC.',
        local_points=['Nothing uploaded', 'No chat content saved', 'Free & open source'],
        outro='Get me free on GitHub!', product='Petoken v1.5', url='github.com/windknows-ai/petoken',
        platform='Windows 10 / 11', app='Petoken',
    ),
    'zh_CN': dict(
        boot='> petoken.exe',
        hi='嗨！', hello='我是 Petoken！', buddy='你的桌面 AI 小伙伴，支持',
        codex='Codex', claude='Claude Code', amp='&',
        react_title='你忙的时候，我也在',
        typing='你打字，我也打字。', music='放音乐？我跟着摇摆～', song='Lo-fi Beats · 深夜学习',
        mic='在开会？麦克风已就位！',
        term1='把任务交给 Codex 或 Claude……', term2='……它就会变成我的一颗星星！',
        cmd_claude='claude "给网站加上深色模式"', out_claude=['正在读取 12 个文件……', '已更新 styles.css'],
        cmd_codex='codex "修复 api-server 的登录 bug"', out_codex=['正在运行测试……', '42 项通过'],
        ring1='蓝色是 Codex，金色是 Claude Code。', ring2='点一下星星，就能看详情。',
        pages='任务超过 8 个？我会分页。',
        limits1='我帮你盯着额度……', limits_note='只显示你正开着的 App',
        bar_ctx='上下文', bar_5h='5 小时', bar_week='1 周', left='剩余', left_fmt='剩 {v}%',
        sync='Claude Pro/Max 额度：设置里一键同步',
        stats1='……每个 token 都算得清清楚楚。', tokens='tokens', scopes=['对话', '项目', '全部'],
        breakdown='按模型 · 对话 · 日期统计',
        notify=[('完成了？我欢呼！', 'Claude Code 任务完成', 'website'),
                ('出错了？我告诉你。', 'Claude Code 任务出错了', 'docs · rate_limit'),
                ('要你确认？我招手！', 'Codex 在等你确认', 'api-server')],
        dnd='免打扰 · 22:00-08:00', low='5 小时额度快用完？我提醒你。',
        wb='待办、便签和提醒，' + NL + '我也帮你记着。',
        wb_tags=['项目', '待办', '便签', '提醒', '新手教程'],
        custom='把我变成你喜欢的样子！', size='大小', ontop='始终置顶',
        local='所有数据都只留在你的电脑上。',
        local_points=['不上传任何数据', '不保存对话内容', '免费开源'],
        outro='去 GitHub 免费领养我吧！', product='Petoken v1.5', url='github.com/windknows-ai/petoken',
        platform='Windows 10 / 11', app='Petoken',
    ),
}


# --- basics -----------------------------------------------------------------
FONT_MAP = {}   # Filled per language: Latin face -> a face that has the script.
ZH_FONTS = {'segoeuib.ttf': 'msyhbd.ttc', 'seguisb.ttf': 'msyhbd.ttc', 'segoeui.ttf': 'msyh.ttc',
            'segoeuil.ttf': 'msyhl.ttc', 'consola.ttf': 'msyh.ttc', 'consolab.ttf': 'msyhbd.ttc'}


def font(name, size):
    return ImageFont.truetype(str(FONT_DIR / FONT_MAP.get(name, name)), size)


def clamp(x, lo=0.0, hi=1.0):
    return lo if x < lo else hi if x > hi else x


def ease_out(t):
    t = clamp(t)
    return 1 - (1 - t) ** 3


def ease_in(t):
    t = clamp(t)
    return t * t * t


def ease_io(t):
    t = clamp(t)
    return 4 * t ** 3 if t < .5 else 1 - (-2 * t + 2) ** 3 / 2


def spring(t, freq=2.1, damping=0.38):
    if t <= 0:
        return 0.0
    w = 2 * math.pi * freq
    wd = w * math.sqrt(1 - damping * damping)
    return 1 - math.exp(-damping * w * t) * (math.cos(wd * t) + damping * w / wd * math.sin(wd * t))


def pop(t, start, freq=2.3, damping=0.36):
    return spring(t - start, freq, damping)


def text_image(value, fnt, fill=INK, spacing=10):
    probe = ImageDraw.Draw(Image.new('RGBA', (1, 1)))
    box = probe.multiline_textbbox((0, 0), value, font=fnt, spacing=spacing)
    img = Image.new('RGBA', (max(1, box[2] - box[0] + 8), max(1, box[3] - box[1] + 8)), (0, 0, 0, 0))
    ImageDraw.Draw(img).multiline_text((4 - box[0], 4 - box[1]), value, font=fnt, fill=fill, spacing=spacing)
    return img


def with_alpha(img, alpha):
    if alpha >= 0.999:
        return img
    out = img.copy()
    out.putalpha(img.getchannel('A').point(lambda v: int(v * alpha)))
    return out


def draw(frame, img, cx, cy, scale=1.0, sx=1.0, sy=1.0, rot=0.0, alpha=1.0, anchor='center'):
    alpha = clamp(alpha)
    if alpha <= 0.004 or scale <= 0.01 or img is None:
        return
    w = max(1, int(round(img.width * scale * sx)))
    h = max(1, int(round(img.height * scale * sy)))
    out = img if (w, h) == img.size else img.resize((w, h), Image.BICUBIC)
    if abs(rot) > 0.05:
        out = out.rotate(rot, Image.BICUBIC, expand=True)
    x = cx - out.width / 2
    y = {'center': cy - out.height / 2, 'bottom': cy - out.height, 'top': cy}[anchor]
    frame.alpha_composite(with_alpha(out, alpha), (int(round(x)), int(round(y))))


def fit(img, height=None, width=None):
    if height:
        return img.resize((round(img.width * height / img.height), height), Image.LANCZOS)
    return img.resize((width, round(img.height * width / img.width)), Image.LANCZOS)


def shadowed(img, radius=24, offset=12, strength=85):
    pad = radius * 2
    base = Image.new('RGBA', (img.width + pad * 2, img.height + pad * 2), (0, 0, 0, 0))
    shadow = Image.new('RGBA', base.size, (0, 0, 0, 0))
    shadow.paste(INK + (255,), (pad, pad + offset), img.getchannel('A').point(lambda v: strength if v > 8 else 0))
    base.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(radius)))
    base.alpha_composite(img, (pad, pad))
    return base


def rounded(img, radius=22):
    mask = Image.new('L', img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, img.width - 1, img.height - 1), radius, fill=255)
    out = img.convert('RGBA')
    out.putalpha(mask)
    return out


def pill(label, fnt, dot=None, fill=(249, 247, 253, 242), fg=INK, pad=26):
    txt = text_image(label, fnt, fg)
    left = pad + (30 if dot else 0)
    w, h = txt.width + left + pad, max(56, txt.height + 22)
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, w - 1, h - 1), h // 2, fill=fill, outline=(129, 119, 159, 255), width=2)
    if dot:
        d.ellipse((pad - 2, h // 2 - 10, pad + 18, h // 2 + 10), fill=dot)
    img.alpha_composite(txt, (left, (h - txt.height) // 2))
    return shadowed(img, 10, 6, 55)


def icon_pill(icon, label, fnt, icon_font):
    """Pill with a symbol glyph (drawn in a font that has it) before the label."""
    glyph = text_image(icon, icon_font, VIOLET)
    txt = text_image(label, fnt, INK)
    w, h = glyph.width + txt.width + 70, max(56, txt.height + 22)
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, w - 1, h - 1), h // 2, fill=(249, 247, 253, 242), outline=(129, 119, 159, 255), width=2)
    img.alpha_composite(glyph, (26, (h - glyph.height) // 2))
    img.alpha_composite(txt, (26 + glyph.width + 14, (h - txt.height) // 2))
    return shadowed(img, 10, 6, 55)


def sparkle(d, x, y, r, alpha, color=WHITE):
    c = tuple(color[:3]) + (int(clamp(alpha / 255) * 255),)
    d.polygon([(x, y - r), (x + r * .28, y - r * .28), (x + r, y), (x + r * .28, y + r * .28),
               (x, y + r), (x - r * .28, y + r * .28), (x - r, y), (x - r * .28, y - r * .28)], fill=c)


def burst(d, cx, cy, t, start, color=GOLD, count=10, r0=70, r1=190, length=46, width=7):
    p = (t - start) / 0.5
    if not 0 < p < 1:
        return
    inner = r0 + (r1 - r0) * ease_out(p)
    run = length * (1 - p)
    for i in range(count):
        a = 2 * math.pi * i / count + 0.3
        d.line([(cx + math.cos(a) * inner, cy + math.sin(a) * inner),
                (cx + math.cos(a) * (inner + run), cy + math.sin(a) * (inner + run))],
               fill=color + (int(255 * (1 - p)),), width=max(1, int(width * (1 - p) + 1)))


def star_sprite(color, size=120):
    """Glowing four-point star like the app's task stars."""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    glow = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((size * .22, size * .22, size * .78, size * .78), fill=color + (150,))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(size * .12)))
    d = ImageDraw.Draw(img)
    c = size / 2
    sparkle(d, c, c, size * .42, 255, tuple(min(255, v + 40) for v in color))
    sparkle(d, c, c, size * .22, 255, WHITE)
    return img


class Words:
    """Text whose words pop in on one baseline, one after another."""

    def __init__(self, value, fnt, fill=INK, gap=0.06, line_gap=10):
        self.items, self.gap = [], gap
        ascent, descent = fnt.getmetrics()
        line_h = ascent + descent
        space = fnt.getlength(' ')
        y = width = 0
        for line in value.split(NL):
            x = 0
            for word in re.findall(r"[A-Za-z0-9.,'!?&%/:+-]+| +|[^ ]", line):
                adv = fnt.getlength(word)
                if word.isspace():
                    x += adv
                    continue
                img = Image.new('RGBA', (int(adv) + 12, line_h + 8), (0, 0, 0, 0))
                ImageDraw.Draw(img).text((6, 4 + ascent), word, font=fnt, fill=fill, anchor='ls')
                self.items.append((img, x - 6, y))
                x += adv
            width = max(width, x)
            y += line_h + line_gap
        if len(self.items) > 10:        # Long CJK lines: keep the whole pop under a second.
            self.gap = min(gap, 0.75 / len(self.items))
        self.width, self.height = width, y

    def draw(self, frame, t, start, x0, y0, alpha=1.0):
        for i, (img, x, y) in enumerate(self.items):
            s = pop(t, start + i * self.gap, 2.6, 0.4)
            if s > 0:
                draw(frame, img, x0 + x + img.width / 2, y0 + y + img.height / 2 + 44 * (1 - s),
                     scale=0.5 + 0.5 * s, alpha=alpha * clamp((t - start - i * self.gap) / 0.15))


class Bubble:
    """Speech bubble that pops from its tail and types its text."""

    def __init__(self, value, fnt, tail='left'):
        self.value, self.font, self.tail = value, fnt, tail
        full = text_image(value, fnt, INK)
        self.w, self.h = full.width + 64, full.height + 44
        img = Image.new('RGBA', (self.w + 40, self.h + 40), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        line = (150, 140, 190, 255)
        d.rounded_rectangle((20, 0, 20 + self.w, self.h), 30, fill=(255, 255, 255, 250), outline=line, width=3)
        tx = 60 if tail == 'left' else self.w - 20
        dx = -34 if tail == 'left' else 34
        back = 26 if tail == 'left' else -26
        d.polygon([(tx, self.h - 3), (tx + dx, self.h + 34), (tx + back, self.h - 3)], fill=(255, 255, 255, 250))
        d.line([(tx, self.h), (tx + dx, self.h + 34)], fill=line, width=3)
        d.line([(tx + dx, self.h + 34), (tx + back, self.h)], fill=line, width=3)
        self.base = shadowed(img, 14, 8, 60)
        self.pad = 28
        self.tip_x = tx + dx

    def draw(self, frame, t, start, x, y, end=None):
        """x, y: where the tail points."""
        if t < start or (end is not None and t > end + 0.25):
            return
        s = pop(t, start, 2.8, 0.34)
        out = 1.0 if end is None or t < end else 1 - ease_in((t - end) / 0.25)
        img = self.base.copy()
        chars = int(len(self.value) * clamp((t - start - 0.08) / max(0.25, len(self.value) * 0.028)))
        if chars:
            img.alpha_composite(text_image(self.value[:chars], self.font, INK), (self.pad + 20 + 28, self.pad + 18))
        scale = s * out
        w, h = int(img.width * scale), int(img.height * scale)
        if w < 2 or h < 2:
            return
        img = img.resize((w, h), Image.BICUBIC)
        ax = (self.tip_x + self.pad) * scale
        ay = (self.h + 34 + self.pad) * scale
        frame.alpha_composite(img, (int(x - ax), int(y - ay)))


# --- the cast -------------------------------------------------------------------
class Assets:
    def __init__(self, folder, language):
        t = self.t = TEXT[language]
        art = lambda name, h=600: fit(Image.open(ROOT / 'assets/v1_1' / f'{name}.png').convert('RGBA'), height=h)
        self.pose = {n: art(n) for n in ('idle', 'typing_1', 'typing_2', 'working', 'microphone', 'music',
                                         'guitar', 'celebrate', 'sad', 'wave')}
        self.small_music = art('music', 470)
        cap = lambda name: Image.open(Path(folder) / f'{name}.png').convert('RGBA')
        self.detail = shadowed(fit(cap('detail'), height=420))
        self.overlay = fit(cap('overlay'), height=700)
        analytics = cap('analytics')
        analytics = analytics.crop((0, 100, analytics.width, 850))
        self.analytics = shadowed(rounded(fit(analytics, width=1150), 18))
        self.wb = shadowed(rounded(fit(cap('workbench_home'), width=880)))
        self.wb_notify = shadowed(rounded(fit(cap('workbench_notifications'), width=880)))
        self.f_h1 = font('seguisb.ttf', 64)
        self.f_body = font('segoeui.ttf', 36)
        self.f_bubble = font('seguisb.ttf', 40)
        self.f_pill = font('seguisb.ttf', 30)
        self.f_mono = font('consola.ttf', 34)
        self.f_mono_b = font('consolab.ttf', 34)
        self.f_sym = font(SYMBOLS, 30)
        self.f_check = font(SYMBOLS, 34)
        self.star_blue, self.star_gold = star_sprite(BLUE), star_sprite(GOLD)
        self.background = self._background((236, 233, 248), (196, 190, 222))
        self.night = self._background((44, 38, 92), (24, 20, 52), glow=False)
        rng = random.Random(7)
        self.stars = [(rng.uniform(0, W), rng.uniform(0, H), rng.uniform(4, 11), rng.uniform(0, 6.28),
                       rng.uniform(8, 22), rng.choice([WHITE, (255, 246, 214), (226, 236, 255)])) for _ in range(52)]
        B = lambda s, side='left': Bubble(s, self.f_bubble, side)
        self.hi = Words(t['hi'], font('segoeuib.ttf', 230), VIOLET)
        self.b_hello = B(t['hello'])
        self.buddy = Words(t['buddy'], font('segoeuil.ttf', 54), VIOLET, 0.05)
        self.pill_codex = pill(t['codex'], self.f_pill, BLUE)
        self.pill_claude = pill(t['claude'], self.f_pill, GOLD)
        self.amp = text_image(t['amp'], font('segoeuil.ttf', 54), VIOLET)
        self.react_title = Words(t['react_title'], self.f_h1)
        self.b_typing, self.b_music, self.b_mic = B(t['typing']), B(t['music']), B(t['mic'])
        self.song = icon_pill('\u266a', t['song'], self.f_pill, font(SYMBOLS, 34))
        self.glyphs = [text_image(g, self.f_mono_b, VIOLET) for g in ('{ }', '</>', ';', '=>', '()', '#')]
        self.notes = [text_image(g, font(SYMBOLS, 64), VIOLET) for g in ('\u266a', '\u266b')]
        self.b_term1, self.b_term2 = B(t['term1']), B(t['term2'])
        self.b_ring1, self.b_ring2 = B(t['ring1']), B(t['ring2'])
        self.pages = pill(t['pages'], self.f_pill)
        self.b_limits = B(t['limits1'])
        self.limits_note = pill(t['limits_note'], self.f_pill, LAVENDER)
        self.sync = pill(t['sync'], self.f_pill, GOLD)
        self.b_stats = B(t['stats1'])
        self.breakdown = pill(t['breakdown'], self.f_pill, VIOLET)
        self.scope_chips = [(pill(s, self.f_pill), pill(s, self.f_pill, None, (72, 63, 134, 255), WHITE))
                            for s in t['scopes']]
        self.money = [text_image('\u2248 ' + m, font('segoeuib.ttf', 70), VIOLET)
                      for m in ('$12.84', 'CA$17.87', '\u20ac11.06', '\u00a593.42')]
        self.b_notify = [B(a) for a, _b, _c in t['notify']]
        self.toasts = [self._toast(b, c, col) for (_a, b, c), col in zip(t['notify'], (GREEN, BERRY, AMBER))]
        self.dnd = pill(t['dnd'], self.f_pill, VIOLET)
        self.low = pill(t['low'], self.f_pill, AMBER)
        self.b_wb = B(t['wb'], 'right')
        self.wb_tags = [pill(n, self.f_pill, c) for n, c in zip(t['wb_tags'], (VIOLET, GREEN, BLUE, AMBER, GOLD))]
        self.b_custom = B(t['custom'])
        self.langs = [pill('English', font(CJK, 34), BLUE), pill('\u4e2d\u6587', font(CJK, 34), BLUE)]
        self.b_outro = B(t['outro'])
        self.local = Words(t['local'], font('segoeuib.ttf', 88), INK, 0.08)
        self.local_points = [pill(p, font('seguisb.ttf', 36), c) for p, c in zip(t['local_points'], (GREEN, VIOLET, GOLD))]
        self.product = Words(t['product'], font('segoeuib.ttf', 120), INK, 0.09)
        self.platform = text_image(t['platform'], font('segoeuil.ttf', 44), VIOLET)
        self.url_font = font('seguisb.ttf', 46)
        self.tokens = text_image(t['tokens'], font('segoeuil.ttf', 44), VIOLET)
        digit_font = font('segoeuib.ttf', 120)
        self.digits = [text_image(str(i), digit_font, VIOLET) for i in range(10)]
        self.comma = text_image(',', digit_font, VIOLET)
        rng = random.Random(11)
        level, self.chart = 0.0, []
        for i in range(60):
            level += rng.uniform(0.2, 1.0) * (1.6 if 18 < i < 30 or 42 < i < 50 else 0.6)
            self.chart.append(level)

    def _toast(self, title, body, color):
        w, h = 640, 150
        img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((0, 0, w - 1, h - 1), 24, fill=(251, 250, 254, 250), outline=(160, 152, 188, 255), width=2)
        d.rounded_rectangle((0, 0, 12, h - 1), 6, fill=color)
        d.ellipse((34, 28, 56, 50), fill=color)
        img.alpha_composite(text_image(self.t['app'], font('segoeui.ttf', 24), MUTED), (68, 20))
        img.alpha_composite(text_image(title, font('seguisb.ttf', 33), INK), (32, 60))
        img.alpha_composite(text_image(body, font('segoeui.ttf', 27), MUTED), (34, 102))
        return shadowed(img, 18, 10, 70)

    def _background(self, top, bottom, glow=True):
        bg = Image.new('RGBA', (W, H))
        d = ImageDraw.Draw(bg)
        for y in range(H):
            k = y / (H - 1)
            d.line([(0, y), (W, y)], fill=tuple(round(a + (b - a) * k) for a, b in zip(top, bottom)) + (255,))
        if glow:
            layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
            g = ImageDraw.Draw(layer)
            g.ellipse((-260, -240, 820, 620), fill=(255, 255, 255, 120))
            g.ellipse((1240, 520, 2240, 1380), fill=(173, 160, 230, 110))
            bg.alpha_composite(layer.filter(ImageFilter.GaussianBlur(140)))
        return bg


def act(frame, img, cx, ground, t, start, mode='idle', size=1.0):
    """The companion performs: drop-in, jump, droop, wave, talk, groove, breathe."""
    k = t - start
    sx = sy = 1.0
    rot = 0.0
    y = ground
    if mode == 'drop':
        s = spring(k, 1.8, 0.32)
        y = ground - 640 * (1 - s)
        over = max(0.0, s - 1)
        sy, sx = 1 - 1.5 * over, 1 + 1.5 * over
        if k < 0.22:
            sy, sx = 1.08, 0.94
    elif mode == 'jump':
        p = clamp(k / 0.6)
        y = ground - 130 * math.sin(math.pi * p)
        sy, sx = (0.9, 1.08) if p < 0.1 or p > 0.92 else (1.07, 0.95) if p < 0.5 else (1.0, 1.0)
    elif mode == 'droop':
        s = spring(k, 1.6, 0.5)
        y = ground + 16 * s
        sy, sx = 1 - 0.05 * s, 1 + 0.03 * s
        rot = 2 * math.sin(k * 2.2) * math.exp(-k * .8)
    elif mode == 'wave':
        rot = 4.5 * math.sin(k * 7.5) * math.exp(-k * .5)
    elif mode == 'talk':
        b = abs(math.sin(k * 9)) * math.exp(-k * 0.9)
        sy, sx = 1 + 0.035 * b, 1 - 0.02 * b
    elif mode == 'groove':
        b = abs(math.sin(math.pi * k / BEAT))
        sy, sx = 1 - 0.04 * b, 1 + 0.03 * b
        rot = 3 * math.sin(math.pi * k / BEAT / 2)
    if mode != 'drop':
        breath = 0.012 * math.sin(t * 2.6)
        sy *= 1 + breath
        sx *= 1 - breath * .5
        y += 7 * math.sin(t * 1.5)
    draw(frame, img, cx, y, scale=size, sx=sx, sy=sy, rot=rot, anchor='bottom')


# --- code-drawn ring --------------------------------------------------------------
def ring(frame, t, cx, cy, rx, ry, stars, behind, front_hook=None, tilt=-8):
    """3D tilted ring with orbiting stars: back half, the body, then the front half."""
    tr = math.radians(tilt)

    def point(angle, scale=1.0):
        x, y = math.cos(angle) * rx * scale, math.sin(angle) * ry * scale
        return cx + x * math.cos(tr) - y * math.sin(tr), cy + x * math.sin(tr) + y * math.cos(tr)

    def half(front):
        layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        steps = 120
        for i in range(steps):
            a0, a1 = 2 * math.pi * i / steps, 2 * math.pi * (i + 1) / steps
            depth = math.sin((a0 + a1) / 2)
            if (depth > 0) != front:
                continue
            alpha = int(120 + 120 * max(0.0, depth)) if front else int(70 + 50 * (1 + depth))
            mix = 0.5 + 0.5 * math.cos(a0 - t * 0.6)
            col = tuple(int(LAVENDER[j] * (1 - mix) + (255, 236, 200)[j] * mix) for j in range(3))
            d.line([point(a0), point(a1)], fill=col + (alpha,), width=9 if front else 5)
            if i % 6 == 0:
                px, py = point(a0, 1.08)
                d.ellipse((px - 3, py - 3, px + 3, py + 3), fill=WHITE + (alpha // 2,))
        frame.alpha_composite(layer.filter(ImageFilter.GaussianBlur(7)))
        frame.alpha_composite(layer)
        for angle, sprite in stars:
            depth = math.sin(angle)
            if (depth > 0) != front:
                continue
            x, y = point(angle)
            pulse = 1 + 0.08 * math.sin(t * 6 + angle)
            draw(frame, sprite, x, y, scale=(0.8 + 0.55 * (depth + 1) / 2) * pulse,
                 alpha=0.55 + 0.45 * (depth + 1) / 2)
    half(False)
    behind()
    half(True)
    if front_hook:
        front_hook(point)


# --- transitions --------------------------------------------------------------------
def glitch(img, strength, seed):
    rng = random.Random(seed)
    r, g, b = img.split()
    dx = int(28 * strength)
    img = Image.merge('RGB', (ImageChops.offset(r, dx, 0), g, ImageChops.offset(b, -dx, 0)))
    for _ in range(int(9 * strength) + 1):
        y = rng.randrange(0, H - 80)
        h = rng.randrange(8, 70)
        band = img.crop((0, y, W, y + h))
        img.paste(band, (rng.randint(-120, 120) if strength > 0.2 else 0, y))
    lines = Image.new('L', (W, H), 0)
    ld = ImageDraw.Draw(lines)
    for y in range(0, H, 4):
        ld.line([(0, y), (W, y)], fill=int(60 * strength))
    return Image.composite(Image.new('RGB', (W, H), (10, 8, 30)), img, lines)


def pixelate(img, k):
    k = max(1, int(k))
    if k == 1:
        return img
    return img.resize((max(1, W // k), max(1, H // k)), Image.NEAREST).resize((W, H), Image.NEAREST)


def transition(frame, t):
    diag = math.hypot(W, H)
    for cut, kind in TRANSITIONS.items():
        if kind == 'iris':
            if cut - 0.35 <= t < cut:
                p = (t - cut + 0.35) / 0.35
                layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
                d = ImageDraw.Draw(layer)
                ox, oy = W * .85, H * .2
                for col, lag in ((LAVENDER, 0.0), (VIOLET, 0.22)):
                    r = diag * ease_in(clamp(p * 1.3 - lag))
                    if r > 0:
                        d.ellipse((ox - r, oy - r, ox + r, oy + r), fill=col + (255,))
                frame.alpha_composite(layer)
            elif cut <= t < cut + 0.35:
                r = diag * .6 * ease_out((t - cut) / 0.35)
                mask = Image.new('L', (W, H), 255)
                ImageDraw.Draw(mask).ellipse((W / 2 - r, H / 2 - r, W / 2 + r, H / 2 + r), fill=0)
                cover = Image.new('RGBA', (W, H), VIOLET + (255,))
                cover.putalpha(mask)
                frame.alpha_composite(cover)
        elif kind == 'stripes' and cut - 0.35 <= t < cut + 0.35:
            layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
            d = ImageDraw.Draw(layer)
            for i, col in enumerate((LAVENDER, VIOLET, GOLD, INK)):
                if t < cut:     # Bands sweep in from the left...
                    p = ease_in(clamp((t - cut + 0.35) / 0.27 - i * 0.08))
                    x0, x1 = -400.0, -400 + (W + 800) * p
                else:           # ...and leave to the right.
                    p = ease_out(clamp((t - cut) / 0.27 - i * 0.08))
                    x0, x1 = -400 + (W + 800) * p, W + 400.0
                if x1 > x0:
                    d.polygon([(x0 + 260, 0), (x1 + 260, 0), (x1, H), (x0, H)], fill=col + (255,))
            frame.alpha_composite(layer)
        elif kind == 'flash' and cut - 0.1 <= t < cut + 0.5:
            p = (t - cut + 0.1) / 0.6
            layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
            r = diag * ease_out(p * 1.6)
            ImageDraw.Draw(layer).ellipse((W / 2 - r, H / 2 - r, W / 2 + r, H / 2 + r),
                                          fill=(255, 255, 255, int(255 * (1 - ease_in(p)))))
            frame.alpha_composite(layer)


def scene_at(t):
    name, start = SCENES[0]
    for n, s in SCENES:
        if t >= s:
            name, start = n, s
    return name, start


# --- one frame ------------------------------------------------------------------
def render(a, t):
    name, s0 = scene_at(t)
    T = a.t
    k = t - s0
    frame = (a.night if name == 'boot' else a.background).copy()
    if name != 'boot':
        bg = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        bd = ImageDraw.Draw(bg)
        for x, y, r, phase, drift, color in a.stars:
            sparkle(bd, x + 8 * math.sin(t * .5 + phase), (y - drift * t) % H, r,
                    50 + 160 * (0.5 + 0.5 * math.sin(t * 1.9 + phase)), color)
        frame.alpha_composite(bg)
    fx = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(fx)

    if name == 'boot':
        typed = T['boot'][:int(max(0, k - 0.2) / 0.06)]
        caret = '_' if int(t * 4) % 2 == 0 else ' '
        draw(frame, text_image(typed + caret, font('consolab.ttf', 72), (200, 190, 255)), W / 2, H / 2)
        if k > 1.4:
            for i in range(14):
                ang = i / 14 * 2 * math.pi
                rr = 40 + 900 * ease_out((k - 1.4) / 1.0)
                sparkle(d, W / 2 + math.cos(ang) * rr, H / 2 + math.sin(ang) * rr * .6, 12,
                        255 * (1 - clamp((k - 1.4) / 1.1)), GOLD)

    elif name == 'hello':
        act(frame, a.pose['wave'], 560, 960, t, s0 + 0.05, 'drop' if k < 1.6 else 'wave')
        burst(d, 560, 920, t, s0 + 0.5, LAVENDER, 12, 160, 320, 60, 8)
        a.hi.draw(frame, t, s0 + 0.7, 930, 150)
        a.b_hello.draw(frame, t, s0 + 1.3, 980, 540)
        a.buddy.draw(frame, t, s0 + 2.4, 960, 620)
        xs = [975, 975 + a.pill_codex.width + 4, 975 + a.pill_codex.width + a.amp.width + 14]
        for i, img in enumerate((a.pill_codex, a.amp, a.pill_claude)):
            draw(frame, img, xs[i] + img.width / 2, 790, scale=pop(t, s0 + 3.2 + i * BEAT / 2, 2.8, .32))
        burst(d, xs[0] + a.pill_codex.width / 2, 790, t, s0 + 3.3, BLUE, 10, 60, 150, 26, 5)
        burst(d, xs[2] + a.pill_claude.width / 2, 790, t, s0 + 3.8, GOLD, 10, 60, 170, 26, 5)

    elif name == 'react':
        a.react_title.draw(frame, t, s0 + 0.1, 110, 80)
        beats = [(0.0, 'typing'), (2.33, 'music'), (4.66, 'mic')]
        for i, (at, kind) in enumerate(beats):
            start, end = s0 + at, s0 + (beats[i + 1][0] if i < 2 else 7.0)
            if not start <= t < end:
                continue
            kk = t - start
            if kind == 'typing':
                pose = a.pose['typing_1' if int(kk / (BEAT / 2)) % 2 == 0 else 'typing_2']
                act(frame, pose, 700, 990, t, start, 'idle')
                for j in range(6):
                    if kk > j * 0.3:
                        p = ((kk - j * 0.3) % 1.2) / 1.2
                        draw(frame, a.glyphs[j % len(a.glyphs)], 700 + (j - 2.5) * 80 + 30 * math.sin(p * 6),
                             760 - 300 * ease_out(p), scale=0.6 + 0.4 * p, alpha=1 - p)
                a.b_typing.draw(frame, t, start + 0.2, 960, 520)
            elif kind == 'music':
                act(frame, a.pose['music'], 700, 990, t, start, 'groove')
                for j in range(5):
                    if kk > j * 0.35:
                        p = ((kk - j * 0.35) % 1.4) / 1.4
                        draw(frame, a.notes[j % 2], 500 + j * 90, 640 - 360 * p + 20 * math.sin(p * 8),
                             rot=20 * math.sin(p * 5), alpha=1 - p)
                draw(frame, a.song, 1300, 820, scale=pop(t, start + 0.3, 2.6, .34))
                a.b_music.draw(frame, t, start + 0.15, 960, 520)
            else:
                act(frame, a.pose['microphone'], 700, 990, t, start, 'talk')
                for j in range(3):
                    p = ((kk - j * 0.25) % 0.75) / 0.75
                    r = 60 + 160 * p
                    d.arc((860 - r, 640 - r, 860 + r, 640 + r), -45, 45, fill=VIOLET + (int(200 * (1 - p)),), width=6)
                a.b_mic.draw(frame, t, start + 0.15, 960, 520)

    elif name == 'term':
        pose = a.pose['typing_1' if int(k / (BEAT / 2)) % 2 == 0 else 'typing_2']
        act(frame, pose, 430, 1010, t, s0, 'idle', 0.9)
        ts = pop(t, s0 + 0.2, 1.9, .4)
        tw, th = 1000, 520
        term = Image.new('RGBA', (tw, th), (0, 0, 0, 0))
        td = ImageDraw.Draw(term)
        td.rounded_rectangle((0, 0, tw - 1, th - 1), 22, fill=(30, 26, 62, 245), outline=(120, 110, 180, 255), width=2)
        td.rounded_rectangle((0, 0, tw - 1, 54), 22, fill=(52, 46, 98, 255))
        td.rectangle((0, 30, tw - 1, 54), fill=(52, 46, 98, 255))
        for i, col in enumerate(((255, 110, 110), (255, 200, 90), (110, 210, 140))):
            td.ellipse((24 + i * 30, 18, 42 + i * 30, 36), fill=col)
        lines = [(0.6, '$ ' + T['cmd_claude'], GOLD, 'cmd'), (2.6, '  ' + T['out_claude'][0], (190, 185, 230), 'out'),
                 (3.0, '  \u2713 ' + T['out_claude'][1], (130, 220, 160), 'out'),
                 (3.8, '$ ' + T['cmd_codex'], BLUE, 'cmd'), (5.8, '  ' + T['out_codex'][0], (190, 185, 230), 'out'),
                 (6.2, '  \u2713 ' + T['out_codex'][1], (130, 220, 160), 'out')]
        flights = []
        for i, (at, line, col, kind) in enumerate(lines):
            if kind == 'cmd':
                flights.append((at + len(line) * 0.035, a.f_mono_b.getlength(line), 84 + i * 66 + 18, col))
            if k < at:
                continue
            n = len(line) if kind == 'out' else int((k - at) / 0.035)
            shown = line[:n]
            fnt = a.f_mono_b if kind == 'cmd' else a.f_mono
            if '✓' in shown:
                head, tail = shown.split('✓', 1)
                td.text((34, 84 + i * 66), head, font=fnt, fill=col)
                x_ = 34 + fnt.getlength(head)
                td.text((x_, 84 + i * 66), '✓', font=a.f_check, fill=col)
                td.text((x_ + a.f_check.getlength('✓'), 84 + i * 66), tail, font=fnt, fill=col)
            else:
                td.text((34, 84 + i * 66), shown, font=fnt, fill=col)
            if kind == 'cmd' and n < len(line) and int(t * 6) % 2 == 0:
                cx_ = 34 + fnt.getlength(shown) + 4
                td.rectangle((cx_, 88 + i * 66, cx_ + 18, 120 + i * 66), fill=(220, 215, 255))
        tx, ty = 1360, 600
        draw(frame, shadowed(term, 20, 10, 80), tx, ty + 160 * (1 - ts), scale=0.7 + 0.3 * ts, rot=-4 * (1 - ts),
             alpha=clamp((k - 0.2) / 0.15))
        for done_at, ex, ey, col in flights:     # Each finished command flies off as a star.
            p = (k - done_at - 0.15) / 1.1
            if 0 < p < 1.05:
                x0, y0 = tx - tw / 2 + 34 + ex, ty - th / 2 + ey
                x1, y1 = 470, 430
                cxp, cyp = (x0 + x1) / 2, min(y0, y1) - 380

                def bez(q):
                    return ((1 - q) ** 2 * x0 + 2 * (1 - q) * q * cxp + q * q * x1,
                            (1 - q) ** 2 * y0 + 2 * (1 - q) * q * cyp + q * q * y1)
                q = ease_io(clamp(p))
                for j in range(10):
                    px, py = bez(clamp(q - j * 0.025))
                    sparkle(d, px, py, 14 - j, 220 - j * 20, col)
                bx, by = bez(q)
                draw(frame, a.star_gold if col == GOLD else a.star_blue, bx, by, scale=0.9 + 0.3 * math.sin(p * 9))
            burst(d, 470, 430, t, s0 + done_at + 1.25, col, 12, 50, 170, 30, 6)
        a.b_term1.draw(frame, t, s0 + 0.4, 500, 330, s0 + 3.6)
        a.b_term2.draw(frame, t, s0 + 4.6, 500, 330)

    elif name == 'ring':
        cx, cy = 640, 650
        stars = [(t * 0.9 + i * math.pi / 2, a.star_blue if i % 2 == 0 else a.star_gold) for i in range(4)]

        def body():
            act(frame, a.pose['idle'], cx, 950, t, s0, 'idle')

        def hook(point):
            if k > 3.4:
                ds = pop(t, s0 + 3.4, 2.0, .36)
                draw(frame, a.detail, 1480, 660 + 80 * (1 - ds), scale=0.4 + 0.6 * ds, rot=8 * (1 - ds),
                     alpha=clamp((k - 3.4) / .12))
        rs = ease_out(k / 0.8)
        ring(frame, t, cx, cy, 480 * (0.6 + 0.4 * rs), 140 * (0.6 + 0.4 * rs), stars, body, hook)
        a.b_ring1.draw(frame, t, s0 + 0.5, 980, 330, s0 + 3.2)
        a.b_ring2.draw(frame, t, s0 + 3.5, 980, 330)
        draw(frame, a.pages, 640, 1010, scale=pop(t, s0 + 5.0, 2.6, .34))

    elif name == 'limits':
        os_ = pop(t, s0 + 0.15, 2.0, .38)
        draw(frame, a.overlay, 470, 610 + 120 * (1 - os_), scale=0.7 + 0.3 * os_, alpha=clamp((k - .15) / .15))
        burst(d, 470, 330, t, s0 + 0.5, BLUE, 12, 140, 280)
        a.b_limits.draw(frame, t, s0 + 0.7, 760, 200)
        bars = [(T['bar_ctx'], 62, None, 'ctx'), (T['bar_5h'], 36, 41 * 60 + 12, '5h'),
                (T['bar_week'], 63, 3 * 86400 + 4 * 3600, 'week')]
        panel = Image.new('RGBA', (820, 420), (0, 0, 0, 0))
        pd = ImageDraw.Draw(panel)
        pd.rounded_rectangle((0, 0, 819, 419), 30, fill=(250, 248, 254, 235), outline=(150, 140, 190, 255), width=2)
        for i, (label, value, reset, kind) in enumerate(bars):
            at = 1.4 + i * BEAT
            grow = spring(k - at, 1.6, .45) if k > at else 0
            y = 50 + i * 120
            pd.text((40, y), label, font=a.f_body, fill=MUTED)
            pd.rounded_rectangle((40, y + 56, 780, y + 80), 12, fill=(196, 190, 222))
            width = 740 * value / 100 * grow
            if width > 24:
                if kind == 'ctx':
                    for xx in range(int(width)):
                        c = xx / 740
                        pd.line([(40 + xx, y + 58), (40 + xx, y + 78)],
                                fill=tuple(int(255 + (INK[j] - 255) * c) for j in range(3)))
                    pd.rounded_rectangle((40, y + 56, 40 + width, y + 80), 12, outline=(129, 119, 159), width=2)
                else:
                    pd.rounded_rectangle((40, y + 56, 40 + width, y + 80), 12,
                                         fill=(220, 232, 255) if kind == '5h' else VIOLET, outline=(129, 119, 159), width=2)
            pd.text((780, y + 2), T['left_fmt'].format(v=int(value * clamp(grow))), font=a.f_pill, fill=INK, anchor='ra')
            if reset and k > at:
                left = reset - int(k - at)
                dd, rem = divmod(left, 86400)
                hh, rem = divmod(rem, 3600)
                mm, ss = divmod(rem, 60)
                stamp = f'\u21bb {dd}d {hh}h' if dd else f'\u21bb {mm}m {ss:02d}s'
                pd.text((560, y + 6), stamp, font=font(SYMBOLS, 28), fill=MUTED, anchor='ra')
        ps = pop(t, s0 + 1.0, 2.0, .4)
        draw(frame, shadowed(panel, 18, 10, 70), 1410, 560 + 100 * (1 - ps), scale=0.8 + 0.2 * ps,
             alpha=clamp((k - 1.0) / .15))
        draw(frame, a.limits_note, 1410, 880, scale=pop(t, s0 + 3.2, 2.6, .34))
        draw(frame, a.sync, 1410, 970, scale=pop(t, s0 + 4.6, 2.6, .34))
        burst(d, 1410, 970, t, s0 + 4.7, GOLD, 10, 60, 200, 30, 6)

    elif name == 'stats':
        act(frame, a.pose['working'], 400, 1010, t, s0, 'talk' if k < 2 else 'idle', 0.92)
        a.b_stats.draw(frame, t, s0 + 0.3, 520, 330, s0 + 4.3)
        if k < 4.6:
            value = 1382450 * ease_out((k - 0.8) / 2.2) if k > 0.8 else 0
            text = f'{int(value):,}'
            x = 860
            places = len(text.replace(',', ''))
            seen = 0
            for ch in text:     # Odometer: every digit rolls to the next.
                if ch == ',':
                    frame.alpha_composite(a.comma, (int(x), 100 + a.digits[0].height - a.comma.height + 18))
                    x += a.comma.width - 20
                    continue
                place = places - 1 - seen
                seen += 1
                # Odometer: a wheel only turns while the wheel below it rolls over.
                low = int(value // 10 ** place) % 10
                below = (value % 10 ** place) / 10 ** place if place else value % 1
                frac = below if place == 0 else clamp((below - 0.9) / 0.1)
                if place < places - 3:
                    frac = 0.0
                col = Image.new('RGBA', a.digits[0].size, (0, 0, 0, 0))
                col.alpha_composite(a.digits[low], (0, int(-frac * col.height)))
                col.alpha_composite(a.digits[(low + 1) % 10], (0, int((1 - frac) * col.height)))
                frame.alpha_composite(col, (int(x), 100))
                x += a.digits[0].width - 12
            draw(frame, a.tokens, x + 90, 190, alpha=clamp((k - 1) / .3))
            if k > 2:
                step = int((k - 2.0) / 0.55)
                draw(frame, a.money[step % 4], 1560, 330, scale=pop(t, s0 + 2.0 + step * 0.55, 3, .3))
            chart = Image.new('RGBA', (880, 360), (0, 0, 0, 0))
            cd = ImageDraw.Draw(chart)
            cd.rounded_rectangle((0, 0, 879, 359), 26, fill=(250, 248, 254, 225), outline=(150, 140, 190, 255), width=2)
            prog = clamp((k - 0.9) / 2.4)
            pts = [(40 + i * 800 / 59, 320 - v / a.chart[-1] * 260) for i, v in enumerate(a.chart)]
            n = max(2, int(len(pts) * prog))
            if prog > 0:
                cd.polygon(pts[:n] + [(pts[n - 1][0], 320), (40, 320)], fill=LAVENDER + (110,))
                cd.line(pts[:n], fill=VIOLET, width=6, joint='curve')
                hx, hy = pts[n - 1]
                cd.ellipse((hx - 12, hy - 12, hx + 12, hy + 12), fill=GOLD, outline=WHITE, width=3)
            cs = pop(t, s0 + 0.7, 2.0, .4)
            draw(frame, shadowed(chart, 18, 10, 70), 1320, 610 + 80 * (1 - cs), scale=0.85 + 0.15 * cs,
                 alpha=clamp((k - .7) / .15))
            for i, (plain, lit) in enumerate(a.scope_chips):
                on = k > 2.6 and int((k - 2.6) / 0.5) % 3 == i
                draw(frame, lit if on else plain, 1030 + i * 260, 900, scale=pop(t, s0 + 2.2 + i * 0.15, 2.6, .34))
        else:
            ks = pop(t, s0 + 4.6, 1.9, .38)
            draw(frame, a.analytics, 1250, 540 + 160 * (1 - ks), scale=0.7 + 0.3 * ks, rot=4 * (1 - ks),
                 alpha=clamp((k - 4.6) / .15))
            draw(frame, a.breakdown, 1240, 990, scale=pop(t, s0 + 5.4, 2.6, .34))

    elif name == 'notify':
        beats = [(0.2, 'celebrate', 'jump', GREEN), (2.6, 'sad', 'droop', BERRY), (5.0, 'wave', 'wave', AMBER)]
        for i, (at, pose, mode, col) in enumerate(beats):
            start = s0 + at
            end = s0 + (beats[i + 1][0] if i < 2 else 8.0)
            if start - 0.25 <= t < end:
                if t < start:
                    q = spring(t - start + 0.25, 3, .35)
                    draw(frame, a.pose[pose], 520, 990, sx=1 + 0.18 * (1 - q), sy=0.62 + 0.38 * q, anchor='bottom')
                else:
                    act(frame, a.pose[pose], 520, 990, t, start, mode)
                a.b_notify[i].draw(frame, t, start + 0.1, 600, 360, end - 0.3)
                burst(d, 520, 600, t, start + 0.05, col, 12, 220, 360)
        arrived = [s0 + at + 0.2 for at, *_ in beats]
        for i, start in enumerate(arrived):     # Toasts slam in, older ones slide down.
            if t < start:
                continue
            q = pop(t, start, 2.0, .34)
            later = [s for s in arrived[i + 1:] if s <= t]
            shift = sum(spring(t - s, 2.4, .5) for s in later)
            draw(frame, a.toasts[i], 2300 - (2300 - 1520) * q, 250 + shift * 170, rot=-6 * (1 - q),
                 scale=1 - 0.05 * len(later))
        draw(frame, a.low, 1500, 880, scale=pop(t, s0 + 6.6, 2.6, .34))
        draw(frame, a.dnd, 1500, 970, scale=pop(t, s0 + 7.0, 2.6, .34))

    elif name == 'workbench':
        ws = pop(t, s0 + 0.2, 1.8, .4)
        flip = s0 + 3.0
        if t < flip:
            draw(frame, a.wb, 640, 560 + 180 * (1 - ws), scale=0.7 + 0.3 * ws, rot=-3 * (1 - ws),
                 alpha=clamp((k - .2) / .15))
        elif t < flip + 0.16:
            draw(frame, a.wb, 640, 560, sx=max(0.02, 1 - (t - flip) / 0.16))
        else:
            draw(frame, a.wb_notify, 640, 560, sx=max(0.02, pop(t, flip + 0.16, 2.6, .4)))
        act(frame, a.pose['wave'], 1580, 1010, t, s0, 'wave', 0.82)
        a.b_wb.draw(frame, t, s0 + 0.5, 1700, 470)
        spots = [(230, 120), (1080, 120), (230, 1000), (1100, 1000), (660, 1030)]
        for i, (img, (x, y)) in enumerate(zip(a.wb_tags, spots)):
            draw(frame, img, x, y + 6 * math.sin(t * 3 + i), scale=pop(t, s0 + 0.9 + i * BEAT * 0.6, 2.8, .32))

    elif name == 'custom':
        wobble = 0.5 + 0.5 * math.sin((k - 0.6) * 2.4) if k > 0.6 else 0.5 * pop(t, s0, 2, .4)
        size = 0.75 + 0.45 * wobble
        act(frame, a.pose['celebrate'], 520, 1010, t, s0, 'idle', size)
        a.b_custom.draw(frame, t, s0 + 0.3, 620, 280)
        sl = Image.new('RGBA', (720, 90), (0, 0, 0, 0))
        sd = ImageDraw.Draw(sl)
        sd.text((0, 26), T['size'], font=a.f_pill, fill=INK)
        sd.rounded_rectangle((120, 40, 600, 52), 6, fill=(196, 190, 222))
        knob = 120 + 480 * wobble
        sd.rounded_rectangle((120, 40, knob, 52), 6, fill=VIOLET)
        sd.ellipse((knob - 18, 28, knob + 18, 64), fill=WHITE, outline=VIOLET, width=4)
        sd.text((715, 26), f'{int(50 + 100 * wobble)}%', font=a.f_pill, fill=INK, anchor='ra')
        draw(frame, sl, 1400, 300, scale=pop(t, s0 + 0.5, 2.6, .34))
        lang = int(max(0, k - 1) / 0.75) % 2
        draw(frame, a.langs[lang], 1220, 460, scale=pop(t, s0 + 1.0, 2.6, .34) * (1 + 0.06 * (lang == 1)))
        on = k > 1.8
        sw = Image.new('RGBA', (110, 60), (0, 0, 0, 0))
        swd = ImageDraw.Draw(sw)
        swd.rounded_rectangle((0, 0, 109, 59), 30, fill=VIOLET if on else (196, 190, 222))
        kx = 30 + 50 * ease_out((k - 1.8) / 0.25) if on else 30
        swd.ellipse((kx - 22, 8, kx + 22, 52), fill=WHITE)
        row = Image.new('RGBA', (520, 70), (0, 0, 0, 0))
        row.alpha_composite(text_image(T['ontop'], a.f_pill), (0, 14))
        row.alpha_composite(sw, (400, 5))
        draw(frame, row, 1420, 590, scale=pop(t, s0 + 1.4, 2.6, .34))
        keys = Image.new('RGBA', (560, 80), (0, 0, 0, 0))
        kd = ImageDraw.Draw(keys)
        lit = int(k / BEAT) % 4
        for i, cap in enumerate(('Alt', '+', '\u2190', '\u2191', '\u2193', '\u2192')):
            x = i * 90
            press = 6 if cap != '+' and lit == i - 2 else 0
            if cap != '+':
                kd.rounded_rectangle((x, press, x + 76, 70), 12, fill=(250, 248, 254), outline=(129, 119, 159), width=3)
            kd.text((x + 38, 35 + press), cap, font=a.f_sym, fill=INK, anchor='mm')
        draw(frame, keys, 1380, 730, scale=pop(t, s0 + 2.0, 2.6, .34))

    elif name == 'local':
        act(frame, a.small_music, 330, 1010, t, s0, 'groove')
        a.local.draw(frame, t, s0 + 0.1, 640, 250)
        for i, img in enumerate(a.local_points):
            at = s0 + 0.8 + i * BEAT
            s = pop(t, at, 2.8, .3)
            draw(frame, img, 700 + img.width / 2, 520 + i * 120, scale=s, rot=-12 * (1 - min(1.0, s)))
            burst(d, 700, 520 + i * 120, t, at + 0.05, GOLD, 8, 30, 100, 22, 5)

    else:   # outro
        act(frame, a.pose['guitar'], 960, 620, t, s0 + 0.05, 'drop' if k < 1.3 else 'groove', 0.8)
        for j in range(6):
            if k > 0.8 + j * 0.3:
                p = ((k - j * 0.3) % 1.8) / 1.8
                draw(frame, a.notes[j % 2], 760 + j * 80, 420 - 300 * p, rot=25 * math.sin(p * 6), alpha=1 - p, scale=0.8)
        a.b_outro.draw(frame, t, s0 + 0.9, 1220, 230)
        a.product.draw(frame, t, s0 + 1.4, (W - a.product.width) / 2, 640)
        draw(frame, a.platform, W / 2, 820, alpha=clamp((k - 2.2) / .4))
        typed = T['url'][:int(max(0, k - 2.6) / 0.04)]
        if typed:
            caret = '|' if len(typed) < len(T['url']) or int(t * 2.5) % 2 == 0 else ' '
            url = text_image(typed + caret, a.url_font, INK)
            draw(frame, url, (W - a.url_font.getlength(T['url'])) / 2 + url.width / 2, 910)
        fade = clamp((t - (DURATION - 0.7)) / 0.7)
        if fade:
            frame.alpha_composite(Image.new('RGBA', (W, H), (236, 233, 248, int(255 * fade))))

    frame.alpha_composite(fx)
    transition(frame, t)
    rgb = frame.convert('RGB')
    for cut, kind in TRANSITIONS.items():
        if kind == 'glitch' and cut - 0.3 <= t < cut + 0.35:
            rgb = glitch(rgb, clamp(1 - abs(t - cut) / 0.35), int(t * 30))
        elif kind == 'pixel' and cut - 0.35 <= t < cut + 0.35:
            rgb = pixelate(rgb, 1 + 44 * ease_in(clamp(1 - abs(t - cut) / 0.35)))
    return rgb


# --- soundtrack -------------------------------------------------------------------
def soundtrack(path, seconds=DURATION, rate=44100):
    """120 BPM pop: kick, clap, hats, bass, pad, arps, typing clicks, glitch
    stutters, 8-bit blips, whooshes, chimes and a plucked-guitar outro."""
    n = int(seconds * rate)
    buf = array('f', [0.0]) * n
    rng = random.Random(3)
    midi = lambda m: 440.0 * 2 ** ((m - 69) / 12)
    tau = 2 * math.pi

    def tone(freq, start, length, amp, attack=0.004, release=0.04, decay=None, sweep=0.0, shape='sine', detune=0.0):
        i0, i1 = int(start * rate), min(n, int((start + length + release) * rate))
        att, rel_at = attack * rate, length * rate
        ph = ph2 = 0.0
        for i in range(max(0, i0), i1):
            k = i - i0
            f = freq * (1 + sweep * math.exp(-k / (0.035 * rate))) if sweep else freq
            ph += tau * f / rate
            ph2 += tau * f * (1 + detune) / rate
            env = k / att if k < att else 1.0
            if k > rel_at:
                env *= max(0.0, 1 - (k - rel_at) / (release * rate))
            if decay:
                env *= math.exp(-k / (decay * rate))
            if shape == 'square':
                v = 1.0 if math.sin(ph) > 0 else -1.0
            elif shape == 'tri':
                v = 2 / math.pi * math.asin(math.sin(ph))
            else:
                v = math.sin(ph) + (0.6 * math.sin(ph2) if detune else 0.0)
            buf[i] += amp * env * v

    def noise(start, length, amp, rise=False, smooth=0.7, decay=6.0):
        i0, last = int(start * rate), 0.0
        total = max(1, int(length * rate))
        for k in range(total):
            i = i0 + k
            if 0 <= i < n:
                p = k / total
                env = p * p if rise else math.exp(-p * decay)
                last = smooth * last + (1 - smooth) * (rng.random() * 2 - 1)
                buf[i] += amp * env * last

    def pluck(freq, start, amp, length=1.6):
        """Karplus-Strong plucked string."""
        period = max(2, int(rate / freq))
        line = [rng.random() * 2 - 1 for _ in range(period)]
        i0 = int(start * rate)
        for k in range(int(length * rate)):
            i = i0 + k
            if not 0 <= i < n:
                break
            v = line[k % period]
            line[k % period] = 0.996 * 0.5 * (v + line[(k + 1) % period])
            buf[i] += amp * v

    chords = [(48, 55, 59, 62, 64), (45, 52, 55, 59, 60), (41, 48, 52, 55, 57), (43, 50, 55, 57, 62)]
    bar = BEAT * 4
    start, index = 0.0, 0
    while start < seconds:
        chord = chords[(index // 2) % 4]
        if start >= 2.4:
            for m in chord:
                tone(midi(m), start, bar, 0.012, 0.6, 0.8, detune=0.003)
            root = chord[0] - 12
            for step in range(8):
                at = start + step * BEAT / 2
                if at < 64.9:
                    tone(midi(root + (12 if step % 4 == 3 else 0)), at, 0.18, 0.09, 0.005, 0.05, shape='tri')
            if 22.0 <= start < 29.0 or 45.0 <= start < 53.0 or 7.0 <= start < 14.0:
                arp = [chord[1] + 12, chord[3] + 12, chord[2] + 24, chord[4] + 12]
                for step in range(16):
                    tone(midi(arp[step % 4]), start + step * BEAT / 4, 0.03, 0.022, decay=0.25)
        index += 1
        start += bar
    beat = 2.5
    while beat < 64.9:
        if not 28.7 <= beat < 29.4:
            tone(105, beat, 0.15, 0.24, 0.002, 0.04, decay=0.09, sweep=1.5)          # Kick.
            noise(beat + BEAT / 2, 0.04, 0.045, smooth=0.2)                              # Hat.
            if beat >= 7.0 and round((beat - 2.5) / BEAT) % 2 == 1:
                noise(beat, 0.16, 0.12, smooth=0.45, decay=9)                            # Clap.
        beat += BEAT
    clicks = [14.6 + i * 0.035 for i in range(40)] + [17.8 + i * 0.035 for i in range(40)] + \
             [7.0 + i * 0.125 for i in range(18)]
    for at in clicks:                                                                    # Typing.
        noise(at, 0.012, 0.05, smooth=0.1, decay=10)
    for cut, kind in TRANSITIONS.items():
        if kind in ('iris', 'stripes'):
            noise(cut - 0.4, 0.42, 0.14, rise=True)
        elif kind == 'flash':
            noise(cut - 0.1, 0.6, 0.12, decay=4)
            tone(midi(84), cut, 0.6, 0.05, decay=0.5)
        elif kind == 'glitch':
            for j in range(8):
                noise(cut - 0.3 + j * 0.075, 0.03, 0.2, smooth=0.05, decay=2)
                tone(200 + 300 * (j % 3), cut - 0.3 + j * 0.075, 0.02, 0.05, shape='square')
        elif kind == 'pixel':
            for j, m in enumerate((84, 88, 91, 96, 91, 88)):
                tone(midi(m), cut - 0.3 + j * 0.08, 0.06, 0.035, shape='square')
    for at in (3.0, 3.2, 5.7, 6.2, 15.9, 19.1, 22.5, 25.9, 29.5, 30.4, 33.6, 37.8, 45.25, 47.65, 50.05,
               53.4, 59.0, 63.3, 65.7):
        tone(880, at, 0.05, 0.06, decay=0.05, sweep=-0.45)                               # Pops.
        for m, dl in ((84, 0.0), (88, 0.06), (91, 0.12)):
            tone(midi(m), at + dl, 0.04, 0.02, decay=0.45)
    for at, ch in ((65.2, chords[0]), (66.2, chords[1]), (67.2, chords[2]), (68.2, chords[3]), (69.2, chords[0])):
        for j, m in enumerate(ch):                                                       # Guitar.
            pluck(midi(m + 12), at + j * 0.025, 0.09)
    peak = max(abs(v) for v in buf) or 1.0
    fade_in, fade_out = 0.3 * rate, 2.2 * rate
    with wave.open(str(path), 'wb') as out:
        out.setnchannels(2)
        out.setsampwidth(2)
        out.setframerate(rate)
        data = bytearray()
        for i, v in enumerate(buf):
            g = min(1.0, i / fade_in, (n - i) / fade_out)
            s = int(max(-1.0, min(1.0, v / peak * 0.85 * g)) * 32767)
            data += struct.pack('<hh', s, s)
        out.writeframes(bytes(data))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('assets', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--language', default='en', choices=sorted(TEXT))
    parser.add_argument('--ffmpeg', default=None)
    parser.add_argument('--preview', type=float, nargs='*', help='Save stills at these seconds and exit')
    args = parser.parse_args()
    if args.language == 'zh_CN':
        FONT_MAP.update(ZH_FONTS)
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
        if index % 300 == 0:
            print(f'frame {index}/{total}', flush=True)
    proc.stdin.close()
    proc.wait()
    music.unlink(missing_ok=True)
    print('wrote', args.output, 'exit', proc.returncode)
    sys.exit(proc.returncode)


if __name__ == '__main__':
    main()
