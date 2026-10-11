"""The Stardust Wardrobe (2.5): everything stardust in its own window, apart from the workbench.

On the left a mirror: she stands on a starlit stage wearing what you pick, and you can turn
her through a few poses (the poses with a free hand show a weapon held; otherwise it floats at
her side). Choosing a piece tries it on at once, owned or not. On the right three pages:
- Wardrobe: the pieces by kind (outfits, weapons, head, back, ground, buddy, task star), wear,
  take off, buy; saved outfits.
- Shop: today's four featured pieces (with the discount card draw) and wishes.
- Milestones: earned stardust and what it unlocks (ring skins, the Starsea form), the
  collection book, the sign-in streak.
"""
from __future__ import annotations

import math
import time

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import (QColor, QFont, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient,
                           QTransform)
from PySide6.QtWidgets import (QButtonGroup, QComboBox, QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
                               QSizeGrip, QStackedWidget, QVBoxLayout, QWidget)

import decor
import pet_assets
import pet_geometry as geometry
import shop
from localization import text

INK = '#ECE8FF'
MUTED = '#A9A2D6'
GOLD = '#F3C96B'
KINDS = ('outfit', 'weapon', 'head', 'back', 'ground', 'buddy', 'star')
METAL = dict(fanxing=((70, 98, 170), (190, 210, 255)), mingyue=((150, 155, 180), (250, 250, 255)),
             haori=((150, 98, 30), (255, 226, 140)), yinhe=((110, 120, 190), (235, 240, 255)),
             xinghai=((150, 110, 230), (255, 200, 250)))
POSE_CHOICES = (('idle', 'wardrobe_pose_idle'), ('greet_morning', 'wardrobe_pose_greet'),
                ('cheer', 'wardrobe_pose_cheer'), ('thumbs_up', 'wardrobe_pose_thumbs'),
                ('ready_go', 'wardrobe_pose_ready'))

STYLE = f'''
QWidget#wardrobe {{ background: transparent; }}
QWidget {{ color: {INK}; font-family: "Microsoft YaHei UI"; font-size: 13px; }}
QLabel {{ background: transparent; }}
QLabel#muted {{ color: {MUTED}; }}
QLabel#title {{ font-size: 18px; font-weight: 700; color: #FFFFFF; }}
QLabel#section {{ font-size: 15px; font-weight: 700; color: #FFFFFF; padding: 4px 0px; }}
QLabel#chip {{ background: rgba(255,255,255,18); border: 1px solid rgba(200,180,255,60); border-radius: 13px;
              padding: 4px 12px; }}
QPushButton {{ background: rgba(255,255,255,16); border: 1px solid rgba(200,180,255,70); border-radius: 15px;
               padding: 6px 14px; color: {INK}; }}
QPushButton:hover {{ background: rgba(190,160,255,48); border-color: rgba(220,200,255,150); }}
QPushButton:disabled {{ color: rgba(236,232,255,90); border-color: rgba(200,180,255,30); }}
QPushButton#primary {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #9C7BFF, stop:1 #5C8DFF);
                       border: 1px solid rgba(255,255,255,90); font-weight: 700; }}
QPushButton#gold {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #FFD98A, stop:1 #E09A3A);
                    border: 1px solid rgba(255,255,255,120); color: #2A1A05; font-weight: 700; }}
QPushButton#tab {{ background: transparent; border: none; border-bottom: 2px solid transparent; border-radius: 0px;
                   padding: 8px 16px; font-size: 15px; color: {MUTED}; }}
QPushButton#tab:checked {{ color: #FFFFFF; border-bottom: 2px solid {GOLD}; font-weight: 700; }}
QPushButton#kind {{ text-align: left; border-radius: 12px; padding: 9px 14px; }}
QPushButton#kind:checked {{ background: rgba(190,160,255,60); border-color: rgba(230,215,255,180); font-weight: 700; }}
QPushButton#pose {{ padding: 4px 12px; border-radius: 12px; font-size: 12px; }}
QPushButton#pose:checked {{ background: rgba(243,201,107,60); border-color: {GOLD}; }}
QPushButton#window {{ border: none; background: transparent; font-size: 16px; padding: 2px 10px; }}
QPushButton#window:hover {{ background: rgba(255,255,255,30); }}
QComboBox {{ background: rgba(255,255,255,16); border: 1px solid rgba(200,180,255,70); border-radius: 12px;
             padding: 5px 10px; }}
QComboBox QAbstractItemView {{ background: #1C1640; color: {INK}; selection-background-color: #4A3A90; }}
QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 8px; }}
QScrollBar::handle:vertical {{ background: rgba(200,180,255,80); border-radius: 4px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0px; }}
'''


def tr(key, language, **values):
    return text(key, language, **values)


def _metal(rarity, a, b):
    g = QLinearGradient(a, b)
    low, high = METAL[rarity]
    if rarity == 'xinghai':
        for k in range(7):
            g.setColorAt(k / 6, QColor.fromHsvF((k / 6 + .55) % 1, .4, 1))
    else:
        for k, c in enumerate((low, high, low, high, low)):
            g.setColorAt(k / 4, QColor(*c))
    return g


# A piece of the wardrobe: its frame in its rarity's metal, its picture, its state ---------------
class Tile(QWidget):
    W, H = 118, 150

    def __init__(self, wardrobe, item):
        super().__init__()
        self.wardrobe, self.item = wardrobe, item
        self.setFixedSize(self.W, self.H)
        self.setCursor(Qt.PointingHandCursor)
        self.hover = False

    def enterEvent(self, event):
        self.hover = True
        self.update()

    def leaveEvent(self, event):
        self.hover = False
        self.update()

    def mousePressEvent(self, event):
        self.wardrobe.choose(self.item)

    def paintEvent(self, event):
        from shop_view import draw_item, item_name, rarity_colour
        w = self.wardrobe
        store = w.shop
        item = self.item
        owned = item['id'] in store.owned()
        worn = store.equipped().get(item['slot']) == item['id']
        chosen = w.chosen is not None and w.chosen['id'] == item['id']
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        box = QRectF(3, 3, self.W - 6, self.H - 6)
        path = QPainterPath()
        path.addRoundedRect(box, 12, 12)
        colour = rarity_colour(item['rarity'], w.t, hash(item['id']) % 100 / 100)
        face = QLinearGradient(box.topLeft(), box.bottomLeft())
        face.setColorAt(0, QColor(22, 18, 52))
        face.setColorAt(1, QColor(colour.red() // 3 + 12, colour.green() // 3 + 10, colour.blue() // 3 + 30))
        p.fillPath(path, face)
        glow = QRadialGradient(QPointF(box.center().x(), box.top() + 52), 60)
        glow.setColorAt(0, QColor(colour.red(), colour.green(), colour.blue(), 70))
        glow.setColorAt(1, QColor(colour.red(), colour.green(), colour.blue(), 0))
        p.fillPath(path, glow)
        if not owned:
            p.setOpacity(.5)
        draw_item(p, item, QRectF(box.center().x() - 42, 12, 84, 84), colour)
        p.setOpacity(1)
        p.setPen(QPen(_metal(item['rarity'], box.topLeft(), box.bottomRight()), 3 if (chosen or self.hover) else 2))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)
        if chosen:
            p.setPen(QPen(QColor(255, 236, 170, 200), 1.4))
            p.drawRoundedRect(box.adjusted(4, 4, -4, -4), 9, 9)
        p.setPen(QColor('#FFFFFF') if owned else QColor(MUTED))
        p.setFont(QFont('Microsoft YaHei UI', 9, QFont.DemiBold))
        name = p.fontMetrics().elidedText(item_name(item, w.language), Qt.ElideRight, int(box.width() - 10))
        p.drawText(QRectF(box.left(), 100, box.width(), 18), Qt.AlignCenter, name)
        rank = shop.RARITIES.index(item['rarity']) + 1
        for k in range(rank):                              # Rank stars.
            cx = box.center().x() + (k - (rank - 1) / 2) * 11
            self._star(p, cx, 125, 4.2, colour)
        if worn:
            badge = QRectF(box.right() - 44, box.top() + 6, 40, 18)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(110, 210, 160, 220))
            p.drawRoundedRect(badge, 9, 9)
            p.setPen(QColor('#0E2A1C'))
            p.setFont(QFont('Microsoft YaHei UI', 8, QFont.Bold))
            p.drawText(badge, Qt.AlignCenter, tr('wardrobe_worn', w.language))
        elif not owned:
            price = store.price(item['id'])
            label = tr('wardrobe_wish_only', w.language) if price is None else f'✦ {price}'
            badge = QRectF(box.left() + 6, box.top() + 6, 52, 18)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(10, 8, 30, 190))
            p.drawRoundedRect(badge, 9, 9)
            p.setPen(QColor(GOLD))
            p.setFont(QFont('Microsoft YaHei UI', 8, QFont.Bold))
            p.drawText(badge, Qt.AlignCenter, label)
        p.end()

    @staticmethod
    def _star(p, cx, cy, r, colour):
        path = QPainterPath()
        for k in range(10):
            a = math.pi * k / 5 - math.pi / 2
            rad = r if k % 2 == 0 else r * .45
            pt = QPointF(cx + math.cos(a) * rad, cy + math.sin(a) * rad)
            path.moveTo(pt) if k == 0 else path.lineTo(pt)
        path.closeSubpath()
        p.setPen(Qt.NoPen)
        p.setBrush(colour.lighter(115))
        p.drawPath(path)


# The mirror: her on a starlit stage, wearing what is worn and what is being tried ------------------
class _MirrorPet:
    pet_scale = 100

    def pos(self):
        return QPoint(0, 0)

    def devicePixelRatioF(self):
        return 1.0


class _Layer:
    def __init__(self, front):
        self.front = front

    def pos(self):
        return QPoint(0, 0)


class Mirror(QWidget):
    def __init__(self, wardrobe):
        super().__init__()
        self.wardrobe = wardrobe
        self.pose = 'idle'
        self.decor = decor.Decor(_MirrorPet())
        self.setMinimumSize(380, 460)
        self._sky = None
        self._sprites = {}

    def sprite(self, pose):
        if pose not in self._sprites:
            starsea = getattr(self.wardrobe.panel, 'starsea', None)
            state = pose
            if starsea is not None and starsea.active and f'star_{pose}' in pet_assets.STAR_REGISTRY:
                state = f'star_{pose}'
            pm = pet_assets.frame_for(state, 0) if pet_assets.frame_count(state) else pet_assets.sprite_for(state)
            if pm is None or pm.isNull():
                pm = pet_assets.sprite_for('idle')
            sx, sy, sw, sh = geometry.scaled_sprite_rect(100)
            self._sprites[pose] = (state, pm.scaled(sw * 2, sh * 2, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        return self._sprites[pose]

    def paintEvent(self, event):
        w, h = self.width(), self.height()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        box = QRectF(0, 0, w, h)
        clip = QPainterPath()
        clip.addRoundedRect(box, 18, 18)
        p.setClipPath(clip)
        self._paint_stage(p, w, h)
        state, sprite = self.sprite(self.pose)
        sx, sy, sw, sh = geometry.scaled_sprite_rect(100)
        k = min(w / 300, (h - 40) / 330)                   # Her 100 % box, scaled up into the mirror.
        p.save()
        p.translate(w / 2 - (sx + sw / 2) * k, h * .86 - (sy + sh) * k + math.sin(self.wardrobe.t * 1.6) * 3)
        p.scale(k, k)
        size_w, size_h = sprite.width() / 2, sprite.height() / 2
        rect = QRectF(sx + (sw - size_w) / 2, sy + sh - size_h, size_w, size_h)
        self.decor.items = self.wardrobe.preview_items()
        self.decor.pose = (state, sprite, QTransform(), rect)
        self.decor.source = decor.frame_file(state, 0)
        self.decor.paint(p, _Layer(False))
        p.setTransform(QTransform().translate(w / 2 - (sx + sw / 2) * k,
                                              h * .86 - (sy + sh) * k + math.sin(self.wardrobe.t * 1.6) * 3).scale(k, k))
        p.drawPixmap(rect, sprite, QRectF(sprite.rect()))
        self.decor.paint(p, _Layer(True))
        p.restore()
        p.setClipping(False)
        p.setPen(QPen(QColor(210, 190, 255, 90), 1.4))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(box.adjusted(.7, .7, -.7, -.7), 18, 18)
        chosen = self.wardrobe.chosen
        if chosen is not None and chosen['id'] not in self.wardrobe.shop.owned():
            pill = QRectF(14, 14, 88, 24)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(243, 201, 107, 210))
            p.drawRoundedRect(pill, 12, 12)
            p.setPen(QColor('#2A1A05'))
            p.setFont(QFont('Microsoft YaHei UI', 9, QFont.Bold))
            p.drawText(pill, Qt.AlignCenter, tr('wardrobe_trying', self.wardrobe.language))
        p.end()

    def _paint_stage(self, p, w, h):
        if self._sky is None or self._sky[0] != (w, h):
            from wish_show import FX_DIR
            image = QImage(str(FX_DIR / 'sky_far.jpg'))
            if not image.isNull():
                scale = max(w / image.width(), h / image.height()) * 1.05
                image = image.scaled(int(image.width() * scale), int(image.height() * scale), Qt.IgnoreAspectRatio,
                                     Qt.SmoothTransformation)
            self._sky = ((w, h), image)
        image = self._sky[1]
        p.fillRect(QRectF(0, 0, w, h), QColor(8, 7, 24))
        if not image.isNull():
            drift = math.sin(self.wardrobe.t * .05) * 10
            p.drawImage(QPointF((w - image.width()) / 2 + drift, (h - image.height()) / 2), image)
        shade = QLinearGradient(0, 0, 0, h)
        shade.setColorAt(0, QColor(6, 5, 20, 40))
        shade.setColorAt(1, QColor(6, 5, 20, 150))
        p.fillRect(QRectF(0, 0, w, h), shade)
        stage = QRadialGradient(QPointF(w / 2, h * .87), w * .42)    # A pool of light where she stands.
        stage.setColorAt(0, QColor(190, 170, 255, 120))
        stage.setColorAt(.5, QColor(140, 120, 255, 40))
        stage.setColorAt(1, QColor(140, 120, 255, 0))
        p.save()
        p.translate(w / 2, h * .87)
        p.scale(1, .22)
        p.translate(-w / 2, -h * .87)
        p.setPen(Qt.NoPen)
        p.setBrush(stage)
        p.drawEllipse(QPointF(w / 2, h * .87), w * .42, w * .42)
        p.restore()
        from wish_show import light
        p.setCompositionMode(QPainter.CompositionMode_Plus)
        t = self.wardrobe.t
        for k in range(16):                                  # Motes rising from the stage.
            phase = (t * .12 + k * .137) % 1
            x = w * (.2 + .6 * ((k * .618) % 1)) + math.sin(t + k) * 6
            y = h * (.88 - .6 * phase)
            light(p, ('sparkle_lavender', 'sparkle_ice', 'sparkle_champagne')[k % 3], QPointF(x, y), 14,
                  math.sin(math.pi * phase) * .8)
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)


# The window -----------------------------------------------------------------------------------
class Wardrobe(QWidget):
    def __init__(self, panel):
        super().__init__(None, Qt.Window | Qt.FramelessWindowHint)
        self.panel = panel
        self.setObjectName('wardrobe')
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet(STYLE)
        self.setWindowTitle('Petoken')
        self.resize(1220, 800)
        self.setMinimumSize(980, 640)
        self.t = 0.0
        self.kind = 'head'
        self.chosen = None
        self._drag = None
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(12)
        outer.addLayout(self._header())
        body = QHBoxLayout()
        body.setSpacing(14)
        left = QVBoxLayout()
        self.mirror = Mirror(self)
        left.addWidget(self.mirror, 1)
        poses = QHBoxLayout()
        self.pose_group = QButtonGroup(self)
        self.pose_buttons = {}
        for pose, key in POSE_CHOICES:
            b = QPushButton()
            b.setObjectName('pose')
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, pose=pose: self.set_pose(pose))
            self.pose_group.addButton(b)
            self.pose_buttons[pose] = (b, key)
            poses.addWidget(b)
        self.pose_buttons['idle'][0].setChecked(True)
        left.addLayout(poses)
        presets = QHBoxLayout()
        self.save_outfit = QPushButton()
        self.save_outfit.clicked.connect(self._save_outfit)
        self.outfits = QComboBox()
        self.wear_outfit = QPushButton()
        self.wear_outfit.clicked.connect(self._wear_outfit)
        self.take_all = QPushButton()
        self.take_all.clicked.connect(self._take_all)
        for widget in (self.save_outfit, self.outfits, self.wear_outfit, self.take_all):
            presets.addWidget(widget)
        left.addLayout(presets)
        self.bonus = QLabel()
        self.bonus.setObjectName('muted')
        self.bonus.setWordWrap(True)
        left.addWidget(self.bonus)
        body.addLayout(left, 5)
        right = QVBoxLayout()
        tabs = QHBoxLayout()
        self.tab_group = QButtonGroup(self)
        self.tab_buttons = []
        for k, key in enumerate(('wardrobe_tab_closet', 'wardrobe_tab_shop', 'wardrobe_tab_milestones')):
            b = QPushButton()
            b.setObjectName('tab')
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, k=k: self.pages.setCurrentIndex(k))
            self.tab_group.addButton(b)
            self.tab_buttons.append((b, key))
            tabs.addWidget(b)
        tabs.addStretch(1)
        right.addLayout(tabs)
        self.pages = QStackedWidget()
        self.pages.addWidget(self._closet_page())
        self.pages.addWidget(self._shop_page())
        self.pages.addWidget(self._milestone_page())
        right.addWidget(self.pages, 1)
        self.pages.currentChanged.connect(lambda k: self.tab_buttons[k][0].setChecked(True))
        body.addLayout(right, 7)
        outer.addLayout(body, 1)
        grip = QSizeGrip(self)
        grip_row = QHBoxLayout()
        grip_row.addStretch(1)
        grip_row.addWidget(grip, 0, Qt.AlignRight | Qt.AlignBottom)
        outer.addLayout(grip_row)
        self.tab_buttons[0][0].setChecked(True)
        self.clock = QTimer(self)
        self.clock.setInterval(33)
        self.clock.timeout.connect(self._tick)
        self.apply_language()
        self.refresh()

    # Shell ---------------------------------------------------------------------------------
    @property
    def language(self):
        return self.panel.prefs.get('language', 'zh_CN')

    @property
    def shop(self):
        return self.panel.shop

    def _header(self):
        row = QHBoxLayout()
        row.setContentsMargins(14, 4, 4, 0)
        self.title = QLabel()
        self.title.setObjectName('title')
        row.addWidget(self.title)
        row.addSpacing(18)
        self.balance = QLabel()
        self.balance.setObjectName('chip')
        self.earned = QLabel()
        self.earned.setObjectName('chip')
        row.addWidget(self.balance)
        row.addWidget(self.earned)
        row.addStretch(1)
        self.signin = QPushButton()
        self.signin.setObjectName('gold')
        self.signin.clicked.connect(self._sign_in)
        row.addWidget(self.signin)
        row.addSpacing(10)
        for symbol, slot in (('—', self.showMinimized), ('✕', self.close)):
            b = QPushButton(symbol)
            b.setObjectName('window')
            b.clicked.connect(slot)
            row.addWidget(b)
        return row

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        box = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        g = QLinearGradient(box.topLeft(), box.bottomRight())
        g.setColorAt(0, QColor(14, 11, 36))
        g.setColorAt(.6, QColor(22, 15, 52))
        g.setColorAt(1, QColor(34, 20, 66))
        p.setPen(QPen(QColor(200, 180, 255, 80), 1.2))
        p.setBrush(g)
        p.drawRoundedRect(box, 16, 16)
        glow = QRadialGradient(QPointF(box.width() * .75, 0), box.width() * .6)
        glow.setColorAt(0, QColor(150, 120, 255, 40))
        glow.setColorAt(1, QColor(150, 120, 255, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(glow)
        p.drawRoundedRect(box, 16, 16)
        p.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and event.position().y() < 56:
            self._drag = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, event):
        self._drag = None

    def showEvent(self, event):
        super().showEvent(event)
        self.clock.start()
        self.refresh()

    def hideEvent(self, event):
        super().hideEvent(event)
        self.clock.stop()

    def _tick(self):
        self.t += .033
        self.mirror.update()

    def apply_language(self):
        lang = self.language
        self.title.setText(tr('wardrobe_title', lang))
        for b, key in self.tab_buttons:
            b.setText(tr(key, lang))
        for pose, (b, key) in self.pose_buttons.items():
            b.setText(tr(key, lang))
        self.save_outfit.setText(tr('wardrobe_save_outfit', lang))
        self.wear_outfit.setText(tr('wardrobe_wear_outfit', lang))
        self.take_all.setText(tr('wardrobe_take_all', lang))
        self.featured_title.setText(tr('shop_featured', lang))
        self.wish_title.setText(tr('shop_wish', lang))
        self.wish_one.setText(tr('shop_wish_one', lang, cost=shop.WISH_COST))
        self.wish_ten.setText(tr('shop_wish_ten', lang, cost=shop.TEN_COST))
        self.milestone_title.setText(tr('stardust_section', lang))
        self.book_title.setText(tr('shop_book', lang))

    # Closet ---------------------------------------------------------------------------------
    def _closet_page(self):
        page = QWidget()
        row = QHBoxLayout(page)
        row.setContentsMargins(0, 6, 0, 0)
        rail = QVBoxLayout()
        self.kind_group = QButtonGroup(self)
        self.kind_buttons = {}
        for kind in KINDS:
            b = QPushButton()
            b.setObjectName('kind')
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, kind=kind: self.set_kind(kind))
            self.kind_group.addButton(b)
            self.kind_buttons[kind] = b
            rail.addWidget(b)
        rail.addStretch(1)
        row.addLayout(rail)
        column = QVBoxLayout()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        holder = QWidget()
        self.grid = QGridLayout(holder)
        self.grid.setSpacing(10)
        self.grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        scroll.setWidget(holder)
        self.grid_scroll = scroll
        column.addWidget(scroll, 1)
        detail = QHBoxLayout()
        self.detail = QLabel()
        self.detail.setWordWrap(True)
        detail.addWidget(self.detail, 1)
        self.action = QPushButton()
        self.action.setObjectName('primary')
        self.action.clicked.connect(self._act)
        self.second = QPushButton()
        self.second.clicked.connect(self._act_second)
        detail.addWidget(self.second)
        detail.addWidget(self.action)
        column.addLayout(detail)
        row.addLayout(column, 1)
        self.kind_buttons[self.kind].setChecked(True)
        self.tiles = []
        return page

    def set_kind(self, kind):
        self.kind = kind
        self.kind_buttons[kind].setChecked(True)
        self._fill_grid()

    def set_pose(self, pose):
        self.pose_buttons[pose][0].setChecked(True)
        self.mirror.pose = pose
        self.mirror.update()

    def preview_items(self):
        """What the mirror shows: what she wears, with the chosen piece tried on."""
        items = decor.worn_items(self.panel)
        if self.chosen is not None and self.chosen.get('art'):
            items[self.chosen['slot']] = self.chosen
        return items

    def choose(self, item):
        self.chosen = item
        if item['slot'] == 'weapon' and decor.hands().get(decor.frame_file(self.mirror.pose, 0)) is None:
            pass                                             # It floats at her side in this pose.
        self._update_detail()
        for tile in self.tiles:
            tile.update()
        self.mirror.update()

    def _fill_grid(self):
        while self.grid.count():
            widget = self.grid.takeAt(0).widget()
            if widget is not None:
                widget.deleteLater()
        items = [i for i in shop.CATALOG if i['slot'] == self.kind and shop.in_window(i, self.shop.today())]
        columns = max(2, (self.grid_scroll.viewport().width() - 10) // (Tile.W + 10))
        self.tiles = []
        for n, item in enumerate(items):
            tile = Tile(self, item)
            self.tiles.append(tile)
            self.grid.addWidget(tile, n // columns, n % columns)
        rows = (len(items) + columns - 1) // columns          # Room for every row: they never overlap.
        self.grid.parentWidget().setMinimumHeight(rows * (Tile.H + 10) + 10)
        self._update_detail()

    def _update_detail(self):
        from shop_view import item_name
        lang = self.language
        item = self.chosen
        self.second.hide()
        if item is None or item['slot'] != self.kind:
            self.detail.setText(tr('wardrobe_pick_hint', lang))
            self.action.hide()
            return
        store = self.shop
        owned = item['id'] in store.owned()
        worn = store.equipped().get(item['slot']) == item['id']
        rarity = tr(f'shop_rarity_{item["rarity"]}', lang)
        note = '' if item.get('art') else tr('wardrobe_no_art', lang)
        self.detail.setText(f'<b style="font-size:15px">{item_name(item, lang)}</b>'
                            f'&nbsp;&nbsp;<span style="color:{GOLD}">{rarity}</span><br>'
                            f'<span style="color:{MUTED}">{tr("shop_slot_" + item["slot"], lang)}{note}</span>')
        self.action.show()
        if worn:
            self.action.setText(tr('wardrobe_take_off', lang))
        elif owned:
            self.action.setText(tr('wardrobe_wear', lang))
        else:
            price = store.price(item['id'])
            if price is None:
                self.action.setText(tr('wardrobe_wish_only', lang))
                self.action.setEnabled(False)
                return
            self.action.setText(tr('wardrobe_buy', lang, price=price))
            self.action.setEnabled(store.spendable() >= price)
            return
        self.action.setEnabled(True)

    def _act(self):
        item, store = self.chosen, self.shop
        if item is None:
            return
        if store.equipped().get(item['slot']) == item['id']:
            store.unequip(item['slot'])
        elif item['id'] in store.owned():
            store.equip(item['id'])
        elif store.buy(item['id']):
            store.equip(item['id'])                          # Bought: put it on.
        self.refresh()

    def _act_second(self):
        pass

    # Shop -------------------------------------------------------------------------------------
    def _shop_page(self):
        page = QWidget()
        column = QVBoxLayout(page)
        column.setContentsMargins(4, 8, 4, 4)
        self.featured_title = QLabel()
        self.featured_title.setObjectName('section')
        column.addWidget(self.featured_title)
        self.featured_row = QHBoxLayout()
        self.featured_row.setSpacing(12)
        column.addLayout(self.featured_row)
        column.addSpacing(14)
        self.wish_title = QLabel()
        self.wish_title.setObjectName('section')
        column.addWidget(self.wish_title)
        banner = QHBoxLayout()
        self.wish_one = QPushButton()
        self.wish_one.setObjectName('primary')
        self.wish_one.clicked.connect(lambda: self._wish(1))
        self.wish_ten = QPushButton()
        self.wish_ten.setObjectName('gold')
        self.wish_ten.clicked.connect(lambda: self._wish(10))
        banner.addWidget(self.wish_one)
        banner.addWidget(self.wish_ten)
        banner.addStretch(1)
        column.addLayout(banner)
        self.pity = QLabel()
        self.pity.setObjectName('muted')
        self.pity.setWordWrap(True)
        column.addWidget(self.pity)
        column.addStretch(1)
        return page

    def _fill_featured(self):
        while self.featured_row.count():
            entry = self.featured_row.takeAt(0)
            if entry.widget() is not None:
                entry.widget().deleteLater()
        lang = self.language
        for item, discount in self.shop.featured():
            cell = QVBoxLayout()
            holder = QWidget()
            holder.setLayout(cell)
            tile = Tile(self, item)
            cell.addWidget(tile, 0, Qt.AlignHCenter)
            owned = item['id'] in self.shop.owned()
            if owned:
                b = QPushButton(tr('wardrobe_owned', lang))
                b.setEnabled(False)
            elif discount is None:
                b = QPushButton(tr('shop_draw_discount', lang))
                b.setObjectName('gold')
                b.clicked.connect(lambda _=False, item=item: self.draw_discount(item))
            else:
                price = self.shop.price(item['id'])
                b = QPushButton(tr('wardrobe_buy_discount', lang, price=price, off=_discount(discount)))
                b.setObjectName('primary')
                b.setEnabled(self.shop.spendable() >= price)
                b.clicked.connect(lambda _=False, item=item: self._buy(item))
            cell.addWidget(b)
            self.featured_row.addWidget(holder)
        self.featured_row.addStretch(1)

    def _buy(self, item):
        if self.shop.buy(item['id']):
            self.shop.equip(item['id'])
        self.refresh()

    def _sound_pref(self):
        panel = self.panel

        def remember(enabled):
            panel.prefs['wish_sound'] = enabled
            persist = getattr(panel, 'persist', None)
            if persist is not None:
                persist()
        return panel.prefs.get('wish_sound', True), remember

    def draw_discount(self, item):
        from discount_draw import DiscountDraw
        sound, remember = self._sound_pref()
        draw = DiscountDraw(self, item, lambda: self.shop.draw_discount(item['id']), self.language, sound=sound,
                            on_sound=remember, on_done=lambda value: self.refresh())
        draw.show()
        draw.raise_()
        draw.setFocus()
        self._overlay = draw

    def _wish(self, count):
        results = self.shop.wish(count)
        if not results:
            return
        from wish_show import WishShow
        sound, remember = self._sound_pref()
        starsea = getattr(self.panel, 'starsea', None)
        show = WishShow(self, results, self.language, bool(starsea is not None and starsea.active), sound=sound,
                        on_sound=remember)
        show.show()
        show.raise_()
        show.setFocus()
        self._overlay = show
        self.refresh()

    # Milestones --------------------------------------------------------------------------------
    def _milestone_page(self):
        from PySide6.QtWidgets import QProgressBar
        from collection_view import SkinCard
        page = QWidget()
        column = QVBoxLayout(page)
        column.setContentsMargins(4, 8, 4, 4)
        self.milestone_title = QLabel()
        self.milestone_title.setObjectName('section')
        column.addWidget(self.milestone_title)
        row = QHBoxLayout()
        self.stardust = QLabel()
        self.stardust.setObjectName('chip')
        row.addWidget(self.stardust)
        self.stardust_bar = QProgressBar()
        self.stardust_bar.setTextVisible(False)
        self.stardust_bar.setFixedHeight(10)
        self.stardust_bar.setStyleSheet('QProgressBar { background: rgba(255,255,255,20); border: none; border-radius: 5px; }'
                                        'QProgressBar::chunk { border-radius: 5px; background: qlineargradient('
                                        'x1:0,y1:0,x2:1,y2:0, stop:0 #8C6CFF, stop:1 #F3C96B); }')
        row.addWidget(self.stardust_bar, 1)
        self.stardust_next = QLabel()
        self.stardust_next.setObjectName('muted')
        row.addWidget(self.stardust_next)
        column.addLayout(row)
        self.stardust_earn = QLabel()
        self.stardust_earn.setObjectName('muted')
        self.stardust_earn.setWordWrap(True)
        column.addWidget(self.stardust_earn)
        cards = QHBoxLayout()
        self.skin_cards = {choice: SkinCard(choice, self._skin_chosen)
                           for choice in ('default', 'meteor', 'aurora', 'starsea')}
        for card in self.skin_cards.values():
            card.dark = True                                 # Light words on the wardrobe's night.
            cards.addWidget(card)
        cards.addStretch(1)
        column.addLayout(cards)
        column.addSpacing(10)
        self.book_title = QLabel()
        self.book_title.setObjectName('section')
        column.addWidget(self.book_title)
        self.book = QVBoxLayout()
        column.addLayout(self.book)
        column.addStretch(1)
        return page

    def _skin_chosen(self, choice):
        panel = self.panel
        if choice == 'starsea':
            starsea = getattr(panel, 'starsea', None)
            if starsea is not None:
                starsea.toggle()
            self.mirror._sprites.clear()
        else:
            panel.prefs['ring_skin'] = choice
            try:
                panel.persist()
            except Exception:
                pass
            panel.apply_ring_skin()
        self._fill_milestones()

    def _fill_milestones(self):
        from PySide6.QtWidgets import QProgressBar
        from stardust import UNLOCKS, next_unlock, unlocked
        lang = self.language
        panel = self.panel
        dust = getattr(panel, 'stardust', None)
        total = dust.total() if dust is not None else 0
        have = unlocked(total)
        coming = next_unlock(total)
        self.stardust.setText(text('stardust_total', lang, points=total))
        goal = coming and dict(UNLOCKS)[coming[0]] or UNLOCKS[-1][1]
        self.stardust_bar.setRange(0, goal)
        self.stardust_bar.setValue(min(total, goal))
        self.stardust_next.setText(text('stardust_next', lang, left=coming[1],
                                        name=text(f'stardust_name_{coming[0]}', lang)) if coming
                                   else text('stardust_all', lang))
        self.stardust_earn.setText(text('stardust_earn', lang))
        need = dict(UNLOCKS)
        skin = panel.prefs.get('ring_skin', 'default')
        starsea = getattr(panel, 'starsea', None)
        for choice, card in self.skin_cards.items():
            key = 'starsea' if choice == 'starsea' else f'skin_{choice}'
            ok = choice == 'default' or key in have
            if choice == 'starsea':
                ok = ok and starsea is not None and starsea.art_ready()
                current = bool(starsea is not None and starsea.active)
            else:
                current = skin == choice
            caption = (text('stardust_card_on', lang) if current else text('stardust_card_wear', lang) if ok
                       else text('stardust_card_locked', lang, need=need.get(key, 0)))
            card.set_state(text(f'stardust_card_{choice}', lang), caption, ok, current,
                           text(f'stardust_card_{choice}_tip', lang))
        while self.book.count():
            entry = self.book.takeAt(0)
            if entry.widget() is not None:
                entry.widget().deleteLater()
        for kind, (got, all_) in self.shop.collection().items():
            line = QWidget()
            row = QHBoxLayout(line)
            row.setContentsMargins(0, 0, 0, 0)
            label = QLabel(tr('shop_book_line', lang, set=tr(f'shop_set_{kind}', lang), have=got, total=all_,
                              bonus=shop.COLLECTION_BONUS))
            bar = QProgressBar()
            bar.setRange(0, all_)
            bar.setValue(got)
            bar.setTextVisible(False)
            bar.setFixedHeight(8)
            bar.setStyleSheet(self.stardust_bar.styleSheet())
            row.addWidget(label)
            row.addWidget(bar, 1)
            self.book.addWidget(line)

    # Outfits, sign-in ---------------------------------------------------------------------------
    def _save_outfit(self):
        name = tr('shop_preset_default', self.language, n=len(self.shop.state.get('wardrobe', [])) + 1)
        self.shop.save_outfit(name)
        self.refresh()

    def _wear_outfit(self):
        if self.outfits.currentText():
            self.shop.wear_outfit(self.outfits.currentText())
            self.refresh()

    def _take_all(self):
        for slot in list(self.shop.equipped()):
            self.shop.unequip(slot)
        self.refresh()

    def _sign_in(self):
        self.shop.sign_in()
        self.refresh()

    # Everything at once ----------------------------------------------------------------------------
    def refresh(self):
        lang = self.language
        s = self.shop
        self.balance.setText(tr('wardrobe_balance', lang, points=s.spendable()))
        self.earned.setText(tr('wardrobe_earned', lang, points=s.earned()))
        signed = s.state.get('signin_day') == s.today().isoformat()
        self.signin.setText(tr('shop_signed', lang, streak=s.state.get('streak', 0)) if signed
                            else tr('shop_signin', lang, points=shop.SIGNIN))
        self.signin.setEnabled(not signed)
        owned = s.owned()
        for kind, b in self.kind_buttons.items():
            total = [i for i in shop.CATALOG if i['slot'] == kind]
            have = sum(1 for i in total if i['id'] in owned)
            b.setText(f'{tr("shop_slot_" + kind, lang)}   {have}/{len(total)}')
        self._fill_grid()
        self._fill_featured()
        self.wish_one.setEnabled(s.spendable() >= shop.WISH_COST)
        self.wish_ten.setEnabled(s.spendable() >= shop.TEN_COST)
        self.pity.setText(tr('shop_pity', lang, left=s.pity_left()))
        self.outfits.clear()
        for preset in s.state.get('wardrobe', []):
            self.outfits.addItem(preset['name'])
        self.wear_outfit.setEnabled(self.outfits.count() > 0)
        bonuses = [tr(f'shop_theme_{t}', lang) for t in s.set_bonuses()]
        self.bonus.setText(tr('shop_set_bonus', lang, sets='、'.join(bonuses)) if bonuses else '')
        self._fill_milestones()
        self.mirror.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.tiles:
            QTimer.singleShot(0, self._fill_grid)


def _discount(value):
    from discount_draw import discount_text
    return discount_text(value)
