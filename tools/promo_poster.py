"""Landscape and portrait promo posters (Chinese) from her art and the real windows.

Usage:
    python tools/promo_poster.py OUT_DIR [zh_CN|en]

Writes Petoken-海报-横版.png (1920x1080) and Petoken-海报-竖版.png (1080x1920),
both drawn at 2x. The interface pieces are captured from the sandboxed test
build with sample data, like the tutorial video (tools/tutorial_video.py).
"""
import sys
from contextlib import ExitStack
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFontMetrics, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QApplication

import tools.tutorial_video as tv
from tools.tutorial_video import font

ART = ROOT / 'assets' / 'v2_0'
INK, VIOLET, SOFT = QColor('#231E56'), QColor('#5B4BC4'), QColor('#5C5577')
SCALE = 2
TEXT = {
    'zh_CN': dict(
        features=(('实时用量圆环', '上下文 · 5 小时 · 一周额度'), ('桌面一键审批', 'Claude 和 Codex 不用切回终端'),
                  ('快速派活', 'Alt + Shift + 空格，一句话开工'), ('工作台与报告', '待办、项目、折线图'),
                  ('专注陪伴', '倒计时、休息、结束总结'), ('41 个动作', '会撒娇、会睡觉、会生气')),
        footer='Windows  ·  免费开源（MIT）  ·  github.com/windknows-ai/petoken',
        poster=('住在桌面上的', 'AI 编程小伙伴'),
        poster_sub='她盯着 Claude Code 和 Codex 的用量和额度，活干完了喊你，需要你拍板也喊你，还陪你专注。',
        portrait_sub='盯着 Claude Code 和 Codex 的用量和额度，\n干完喊你、要你拍板也喊你，还陪你专注。',
        cover_pill='Petoken 2.0 使用说明', cover=('桌面上的', 'AI 编程搭子'),
        cover_sub='看 Claude Code / Codex 用量\n一键审批 · 陪你专注', cover_sub_tall='看用量 · 一键审批 · 陪你专注',
        files=('Petoken-海报-横版', 'Petoken-海报-竖版', 'Petoken-封面-16x9-B站', 'Petoken-封面-4x3-抖音横',
               'Petoken-封面-3x4-抖音竖')),
    'en': dict(
        features=(('Live usage rings', 'Context · 5 hours · weekly limits'),
                  ('One-click approvals', 'Claude and Codex, no terminal'),
                  ('Quick launch', 'Alt + Shift + Space, one line'), ('Workbench & reports', 'Todos, projects, charts'),
                  ('Focus buddy', 'Countdown, breaks, summary'), ('41 poses', 'Cuddly, sleepy, grumpy')),
        footer='Windows  ·  Free and open source (MIT)  ·  github.com/windknows-ai/petoken',
        poster=('Your desktop', 'AI coding buddy'),
        poster_sub='She watches your Claude Code and Codex usage and limits, pings you when work is done or '
                   'needs you, and keeps you company while you focus.',
        portrait_sub='Watches Claude Code and Codex usage and limits,\npings you when it matters, keeps you company.',
        cover_pill='Petoken 2.0 Guide', cover=('Your desktop', 'AI coding buddy'),
        cover_sub='Claude Code / Codex usage\nOne-click approvals · Focus', cover_sub_tall='Usage · Approvals · Focus',
        files=('Petoken-poster-landscape-EN', 'Petoken-poster-portrait-EN', 'Petoken-cover-16x9-EN',
               'Petoken-cover-4x3-EN', 'Petoken-cover-3x4-EN')),
}
LANG = 'zh_CN'


def T(key):
    return TEXT[LANG][key]
POSES = ('headpat_happy_1', 'focus_read_1', 'sleep_1', 'cheer_1', 'pout_1', 'focus_tea_1')


def art(name):
    image = QImage(str(ART / f'{name}.png'))
    return image if not image.isNull() else None


def background(p, w, h):
    g = QLinearGradient(0, 0, w * .4, h)
    g.setColorAt(0, QColor('#F3EFFD'))
    g.setColorAt(.55, QColor('#E4DCF7'))
    g.setColorAt(1, QColor('#CFC2F0'))
    p.fillRect(QRectF(0, 0, w, h), g)
    p.setPen(Qt.NoPen)
    for cx, cy, r, color in ((.85, .2, .45, '#FFFFFF'), (.1, .9, .4, '#BFAEF0'), (.6, .85, .3, '#F7D9EC')):
        radial = QRadialGradient(QPointF(w * cx, h * cy), max(w, h) * r)
        c = QColor(color)
        c.setAlpha(150)
        radial.setColorAt(0, c)
        c.setAlpha(0)
        radial.setColorAt(1, c)
        p.setBrush(radial)
        p.drawRect(QRectF(0, 0, w, h))


def sparkle(p, center, r, color='#FFC857'):
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    x, y = center
    star = QPainterPath()
    star.moveTo(x, y - r * 2)
    for dx, dy in ((r * 2, 0), (0, r * 2), (-r * 2, 0), (0, -r * 2)):
        star.quadTo(x, y, x + dx, y + dy)
    p.drawPath(star)


def card(p, shot, center, width, angle=0.0):
    """A captured window as a floating card."""
    image, dpr = shot['image'], shot['dpr']
    ratio = image.height() / image.width()
    rect = QRectF(-width / 2, -width * ratio / 2, width, width * ratio)
    p.save()
    p.translate(*center)
    p.rotate(angle)
    p.setPen(Qt.NoPen)
    for k in range(10):
        p.setBrush(QColor(35, 30, 86, 7))
        p.drawRoundedRect(rect.adjusted(-k * 2, -k * 2 + 12, k * 2, k * 2 + 12), 22, 22)
    path = QPainterPath()
    path.addRoundedRect(rect, 16, 16)
    p.setClipPath(path)
    if shot.get('underlay', True):
        p.fillPath(path, QColor('#F7F5FC'))
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.drawImage(rect, image)
    p.restore()


def hero(p, image, rect):
    glow = QRadialGradient(rect.center(), rect.width() * .55)
    glow.setColorAt(0, QColor(255, 255, 255, 210))
    glow.setColorAt(1, QColor(255, 255, 255, 0))
    p.setPen(Qt.NoPen)
    p.setBrush(glow)
    p.drawEllipse(rect.center(), rect.width() * .55, rect.width() * .55)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.drawImage(rect, image)


def pill(p, rect, text, size=24):
    p.setPen(Qt.NoPen)
    p.setBrush(VIOLET)
    p.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)
    p.setPen(QColor('#FFFFFF'))
    p.setFont(font(size, True))
    p.drawText(rect, Qt.AlignCenter, text)


def headline(p, x, y, lines, size, align=Qt.AlignLeft, width=1000):
    while size > 24 and max(QFontMetrics(font(size, True)).horizontalAdvance(t) for t in lines) > width * .98:
        size -= 2                                         # English runs wider: shrink to fit.
    for i, text in enumerate(lines):
        rect = QRectF(x, y + i * size * 1.22, width, size * 1.3)
        if i == len(lines) - 1:
            g = QLinearGradient(rect.left(), 0, rect.left() + width * .7, 0)
            g.setColorAt(0, QColor('#5B4BC4'))
            g.setColorAt(1, QColor('#C2449B'))
            p.setPen(QPen(g, 1))
        else:
            p.setPen(INK)
        p.setFont(font(size, True))
        p.drawText(rect, align | Qt.AlignVCenter, text)


def features(p, x, y, columns, cell_w, cell_h):
    for i, (title, detail) in enumerate(T('features')):
        cx, cy = x + (i % columns) * (cell_w + 18), y + (i // columns) * (cell_h + 16)
        box = QRectF(cx, cy, cell_w, cell_h)
        p.setPen(QPen(QColor(255, 255, 255, 230), 2))
        p.setBrush(QColor(255, 255, 255, 170))
        p.drawRoundedRect(box, 20, 20)
        p.setPen(Qt.NoPen)
        p.setBrush(VIOLET)
        p.drawEllipse(QPointF(cx + 30, cy + cell_h / 2), 9, 9)
        p.setPen(INK)
        p.setFont(font(27, True))
        p.drawText(QRectF(cx + 52, cy + cell_h / 2 - 40, cell_w - 60, 38), Qt.AlignLeft | Qt.AlignVCenter, title)
        p.setPen(SOFT)
        p.setFont(font(19))
        p.drawText(QRectF(cx + 52, cy + cell_h / 2 + 4, cell_w - 60, 30), Qt.AlignLeft | Qt.AlignVCenter, detail)


def footer(p, rect, align=Qt.AlignLeft):
    p.setPen(SOFT)
    p.setFont(font(22))
    p.drawText(rect, align | Qt.AlignVCenter, T('footer'))


def landscape(stills):
    w, h = 1920, 1080
    image = QImage(w * SCALE, h * SCALE, QImage.Format_ARGB32_Premultiplied)
    p = QPainter(image)
    p.scale(SCALE, SCALE)
    p.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform)
    background(p, w, h)
    pill(p, QRectF(110, 120, 236, 52), 'Petoken 2.0')
    headline(p, 104, 200, T('poster'), 92, width=900)
    p.setPen(SOFT)
    p.setFont(font(30))
    p.drawText(QRectF(110, 440, 820, 136), Qt.AlignLeft | Qt.TextWordWrap,
               T('poster_sub'))
    features(p, 110, 580, 2, 390, 96)
    footer(p, QRectF(110, 960, 900, 60))
    hero(p, art('greet_morning_1'), QRectF(1080, 170, 820, 820))
    card(p, stills['card'], (1680, 230), 360, 4)
    card(p, stills['approval'], (1170, 820), 400, -4)
    card(p, stills['focus_card'], (1700, 860), 330, 3)
    for center, r in (((1040, 170), 9), ((1870, 520), 7), ((1500, 110), 6), ((990, 980), 5)):
        sparkle(p, center, r)
    p.end()
    return image


def portrait(stills):
    w, h = 1080, 1920
    image = QImage(w * SCALE, h * SCALE, QImage.Format_ARGB32_Premultiplied)
    p = QPainter(image)
    p.scale(SCALE, SCALE)
    p.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform)
    background(p, w, h)
    pill(p, QRectF(w / 2 - 118, 90, 236, 52), 'Petoken 2.0')
    headline(p, 0, 168, T('poster'), 96, align=Qt.AlignHCenter, width=w)
    p.setPen(SOFT)
    p.setFont(font(30))
    p.drawText(QRectF(90, 410, w - 180, 100), Qt.AlignHCenter | Qt.TextWordWrap,
               T('portrait_sub'))
    hero(p, art('greet_morning_1'), QRectF(110, 500, 860, 860))
    card(p, stills['card'], (850, 700), 320, 5)
    card(p, stills['approval'], (250, 1220), 380, -5)
    for center, r in (((120, 560), 8), ((980, 980), 7), ((560, 520), 5)):
        sparkle(p, center, r)
    features(p, 60, 1400, 2, 471, 92)
    # A strip of poses: "41 个动作".
    y = 1740
    for i, name in enumerate(POSES):
        pose = art(name)
        if pose is not None:
            p.drawImage(QRectF(w / 2 - 3 * 160 + 10 + i * 160, y - 30, 140, 140), pose)
    footer(p, QRectF(0, 1860, w, 44), Qt.AlignHCenter)
    p.end()
    return image


def cover(stills, w, h):
    """A cover: big headline, her, the usage card. Landscape or portrait by shape."""
    image = QImage(w * SCALE, h * SCALE, QImage.Format_ARGB32_Premultiplied)
    p = QPainter(image)
    p.scale(SCALE, SCALE)
    p.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform)
    background(p, w, h)
    if w > h:
        wide = w / h > 1.5
        size = int(h * (.125 if wide else .105))
        pill(p, QRectF(w * .06, h * .14, size * 2.9, size * .62), T('cover_pill'), int(size * .28))
        headline(p, w * .055, h * .25, T('cover'), size, width=w * (.5 if wide else .44))
        p.setPen(SOFT)
        p.setFont(font(int(size * .36)))
        p.drawText(QRectF(w * .06, h * .25 + size * 2.6, w * .48, size * 1.4), Qt.AlignLeft | Qt.TextWordWrap,
                   T('cover_sub'))
        side = h * (1.0 if wide else .8)
        hero(p, art('greet_morning_1'), QRectF(w - side * (1.0 if wide else .96), h - side * .98, side, side))
        card(p, stills['card'], (w * (.86 if wide else .8), h * .2), w * (.17 if wide else .2), 4)
        sparkle(p, (w * .55, h * .16), h * .012)
        sparkle(p, (w * .95, h * .62), h * .009)
    else:
        size = int(w * .125)
        pill(p, QRectF(w / 2 - size * 1.5, h * .06, size * 3, size * .62), T('cover_pill'), int(size * .26))
        headline(p, w * .04, h * .12, T('cover'), size, align=Qt.AlignHCenter, width=w * .92)
        p.setPen(SOFT)
        p.setFont(font(int(size * .34)))
        p.drawText(QRectF(0, h * .12 + size * 2.5, w, size * .6), Qt.AlignHCenter | Qt.AlignVCenter,
                   T('cover_sub_tall'))
        side = w * .8
        hero(p, art('greet_morning_1'), QRectF((w - side) / 2, h - side * .97, side, side))
        card(p, stills['card'], (w * .8, h * .86), w * .32, 5)
        sparkle(p, (w * .12, h * .5), w * .012)
    p.end()
    return image


def main(argv=None):
    global LANG
    argv = sys.argv[1:] if argv is None else argv
    out = Path(argv[0])
    LANG = argv[1] if len(argv) > 1 else 'zh_CN'
    out.mkdir(parents=True, exist_ok=True)
    QApplication.instance() or QApplication([])
    with ExitStack() as stack:
        pv, base = tv.setup(stack, LANG)
        stills = tv.capture_all(pv, base)
        names = T('files')
        landscape(stills).save(str(out / f'{names[0]}.png'))
        portrait(stills).save(str(out / f'{names[1]}.png'))
        for name, (w, h) in zip(names[2:], ((1920, 1080), (1440, 1080), (1080, 1440))):
            cover(stills, w, h).save(str(out / f'{name}.png'))
        tv.finish(pv, base)
    print('done', out)


if __name__ == '__main__':
    main()
