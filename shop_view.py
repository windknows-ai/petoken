"""2.5 Stardust Shop page (workbench) and the wishing show."""
from __future__ import annotations

import math
import random

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import (QColor, QConicalGradient, QFont, QLinearGradient, QPainter, QPainterPath, QPen,
                           QPolygonF, QRadialGradient)
from PySide6.QtWidgets import (QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QProgressBar,
                               QPushButton, QScrollArea, QVBoxLayout, QWidget)

import shop
import theme
from localization import text

# Rarity colours, low to high: deep blue, flashing white, warm gold, flowing silver, iridescent.
RARITY_COLOURS = dict(fanxing=(52, 82, 196), mingyue=(242, 246, 255), haori=(246, 190, 72),
                      yinhe=(200, 210, 232), xinghai=(196, 150, 255))


def rarity_colour(rarity, t=0.0, at=0.0):
    """The rarity's colour at time ``t``; Galaxy shimmers, Starsea cycles hues, Moon flashes."""
    if rarity == 'xinghai':
        return QColor.fromHsvF(((t * .25 + at) % 1.0), .55, 1.0)
    if rarity == 'yinhe':
        v = .78 + .22 * math.sin(t * 3 + at * 6)
        return QColor.fromRgbF(.72 * v + .2, .76 * v + .2, .86 * v + .14)
    if rarity == 'mingyue':
        flash = .85 + .15 * max(0.0, math.sin(t * 5 + at * 4))
        return QColor.fromRgbF(flash, flash, 1.0)
    return QColor(*RARITY_COLOURS[rarity])


def glyph(p, slot, rect, colour):
    """A simple drawn symbol per slot, until the real parts are drawn."""
    c = rect.center()
    s = min(rect.width(), rect.height()) / 2
    p.setPen(QPen(QColor(255, 255, 255, 230), max(1.5, s * .08)))
    p.setBrush(colour)
    path = QPainterPath()
    if slot == 'outfit':                                    # A dress.
        path.moveTo(c.x() - s * .3, c.y() - s * .7)
        path.lineTo(c.x() + s * .3, c.y() - s * .7)
        path.lineTo(c.x() + s * .2, c.y() - s * .2)
        path.lineTo(c.x() + s * .65, c.y() + s * .7)
        path.lineTo(c.x() - s * .65, c.y() + s * .7)
        path.lineTo(c.x() - s * .2, c.y() - s * .2)
        path.closeSubpath()
    elif slot == 'weapon':                                  # A staff with a star.
        p.drawLine(QPointF(c.x() - s * .55, c.y() + s * .7), QPointF(c.x() + s * .35, c.y() - s * .3))
        return _star(p, QPointF(c.x() + s * .42, c.y() - s * .42), s * .38, colour)
    elif slot == 'head':                                    # A crown.
        path.moveTo(c.x() - s * .65, c.y() + s * .35)
        for i, (dx, dy) in enumerate(((-.65, -.45), (-.32, .0), (0, -.6), (.32, 0), (.65, -.45), (.65, .35))):
            path.lineTo(c.x() + s * dx, c.y() + s * dy)
        path.closeSubpath()
    elif slot == 'back':                                    # Wings.
        for side in (-1, 1):
            wing = QPainterPath()
            wing.moveTo(c)
            wing.cubicTo(c + QPointF(side * s * .9, -s * .9), c + QPointF(side * s * 1.0, s * .2), c + QPointF(side * s * .2, s * .5))
            wing.closeSubpath()
            p.drawPath(wing)
        return
    elif slot == 'ground':                                  # A magic circle.
        p.setBrush(Qt.NoBrush)
        pen = QPen(colour, max(2.0, s * .12))
        p.setPen(pen)
        p.drawEllipse(c, s * .8, s * .32)
        p.drawEllipse(c, s * .5, s * .2)
        return
    elif slot == 'buddy':                                   # A little spirit.
        p.drawEllipse(c, s * .5, s * .45)
        p.setBrush(QColor(40, 30, 80))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(c.x() - s * .17, c.y() - s * .05), s * .07, s * .09)
        p.drawEllipse(QPointF(c.x() + s * .17, c.y() - s * .05), s * .07, s * .09)
        return
    else:                                                   # A task-star style.
        return _star(p, c, s * .75, colour)
    p.drawPath(path)


def _star(p, c, r, colour):
    p.setBrush(colour)
    p.drawPolygon(QPolygonF([c + QPointF(0, -r), c + QPointF(r * .28, -r * .28), c + QPointF(r, 0),
                             c + QPointF(r * .28, r * .28), c + QPointF(0, r), c + QPointF(-r * .28, r * .28),
                             c + QPointF(-r, 0), c + QPointF(-r * .28, -r * .28)]))


def item_name(item, language):
    return text(f'shop_item_{item["name"]}', language)


class ItemCard(QWidget):
    W, H = 150, 186

    def __init__(self, page, item):
        super().__init__()
        self.page, self.item = page, item
        self.setFixedSize(self.W, self.H)
        self.t = 0.0
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 112, 8, 8)
        layout.setSpacing(4)
        self.button = QPushButton()
        self.button.clicked.connect(self._clicked)
        layout.addStretch(1)
        layout.addWidget(self.button)
        self.extra = None

    def _clicked(self):
        self.page.act(self.item, self.button.property('action'))

    def set_action(self, label, action, enabled=True, tip=''):
        self.button.setText(label)
        self.button.setProperty('action', action)
        self.button.setEnabled(enabled)
        self.button.setToolTip(tip)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rarity = self.item['rarity']
        colour = rarity_colour(rarity, self.t, hash(self.item['id']) % 100 / 100)
        box = QRectF(2, 2, self.W - 4, 104)
        g = QLinearGradient(box.topLeft(), box.bottomRight())
        g.setColorAt(0, QColor(30, 26, 70))
        g.setColorAt(1, QColor(colour.red() // 3 + 20, colour.green() // 3 + 16, colour.blue() // 3 + 40))
        p.setPen(QPen(colour, 2.4))
        p.setBrush(g)
        p.drawRoundedRect(box, 10, 10)
        glyph(p, self.item['slot'], QRectF(box.center().x() - 34, 18, 68, 68), colour)
        p.setPen(QColor(theme.INK))
        p.setFont(QFont('Microsoft YaHei UI', 9, QFont.DemiBold))
        p.drawText(QRectF(0, 108, self.W, 18), Qt.AlignCenter, item_name(self.item, self.page.language))
        p.setPen(QColor(theme.MUTED))
        p.setFont(QFont('Microsoft YaHei UI', 8))
        p.drawText(QRectF(0, 126, self.W, 16), Qt.AlignCenter, self.caption)

    caption = ''


class ShopPage(QWidget):
    """Balances, sign-in, today's four, wishing, the catalogue, the wardrobe, the collection book."""

    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        inner.setObjectName('shopInner')
        scroll.viewport().setObjectName('shopViewport')
        scroll.setStyleSheet('QScrollArea, QWidget#shopViewport, QWidget#shopInner { background: transparent; }')
        scroll.setWidget(inner)
        outer.addWidget(scroll)
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)
        self.note = QLabel()
        self.note.setObjectName('muted')
        self.note.setWordWrap(True)
        layout.addWidget(self.note)
        top = QHBoxLayout()
        self.balance = QLabel()
        self.balance.setObjectName('summary')
        top.addWidget(self.balance)
        self.earned = QLabel()
        self.earned.setObjectName('muted')
        top.addWidget(self.earned, 1)
        self.signin = QPushButton()
        self.signin.clicked.connect(self._sign_in)
        top.addWidget(self.signin)
        layout.addLayout(top)
        # Today's four.
        self.featured_title = QLabel()
        self.featured_title.setObjectName('section')
        layout.addWidget(self.featured_title)
        self.featured_row = QHBoxLayout()
        self.featured_row.setSpacing(10)
        layout.addLayout(self.featured_row)
        # Wishing.
        self.wish_title = QLabel()
        self.wish_title.setObjectName('section')
        layout.addWidget(self.wish_title)
        wish = QHBoxLayout()
        self.wish_one = QPushButton()
        self.wish_one.clicked.connect(lambda: self._wish(1))
        self.wish_ten = QPushButton()
        self.wish_ten.clicked.connect(lambda: self._wish(10))
        self.pity = QLabel()
        self.pity.setObjectName('muted')
        wish.addWidget(self.wish_one)
        wish.addWidget(self.wish_ten)
        wish.addWidget(self.pity, 1)
        layout.addLayout(wish)
        # Catalogue.
        cat = QHBoxLayout()
        self.catalog_title = QLabel()
        self.catalog_title.setObjectName('section')
        cat.addWidget(self.catalog_title)
        self.set_pick = QComboBox()
        self.set_pick.currentIndexChanged.connect(lambda _: self.refresh())
        cat.addWidget(self.set_pick)
        cat.addStretch(1)
        layout.addLayout(cat)
        self.grid = QGridLayout()
        self.grid.setSpacing(10)
        layout.addLayout(self.grid)
        # Wardrobe.
        self.wardrobe_title = QLabel()
        self.wardrobe_title.setObjectName('section')
        layout.addWidget(self.wardrobe_title)
        self.worn = QLabel()
        self.worn.setWordWrap(True)
        layout.addWidget(self.worn)
        row = QHBoxLayout()
        self.preset_name = QLineEdit()
        self.preset_save = QPushButton()
        self.preset_save.clicked.connect(self._save_outfit)
        self.preset_pick = QComboBox()
        self.preset_wear = QPushButton()
        self.preset_wear.clicked.connect(self._wear_outfit)
        for widget in (self.preset_name, self.preset_save, self.preset_pick, self.preset_wear):
            row.addWidget(widget)
        layout.addLayout(row)
        # Collection book.
        self.book_title = QLabel()
        self.book_title.setObjectName('section')
        layout.addWidget(self.book_title)
        self.book = QVBoxLayout()
        layout.addLayout(self.book)
        layout.addStretch(1)
        self.cards = []
        self.clock = QTimer(self)
        self.clock.setInterval(60)
        self.clock.timeout.connect(self._tick)

    @property
    def language(self):
        return self.owner.panel.prefs.get('language')

    @property
    def shop(self):
        return getattr(self.owner.panel, 'shop', None)

    def tr(self, key, **values):
        return text(key, self.language, **values)

    def apply_language(self):
        self.note.setText(self.tr('shop_note'))
        self.featured_title.setText(self.tr('shop_featured'))
        self.wish_title.setText(self.tr('shop_wish'))
        self.catalog_title.setText(self.tr('shop_catalog'))
        self.wardrobe_title.setText(self.tr('shop_wardrobe'))
        self.book_title.setText(self.tr('shop_book'))
        self.preset_name.setPlaceholderText(self.tr('shop_preset_name'))
        self.preset_save.setText(self.tr('shop_preset_save'))
        self.preset_wear.setText(self.tr('shop_preset_wear'))
        self.wish_one.setText(self.tr('shop_wish_one', cost=shop.WISH_COST))
        self.wish_ten.setText(self.tr('shop_wish_ten', cost=shop.TEN_COST))
        index = max(0, self.set_pick.currentIndex())
        self.set_pick.blockSignals(True)
        self.set_pick.clear()
        for kind in shop.SETS:
            self.set_pick.addItem(self.tr(f'shop_set_{kind}'), kind)
        self.set_pick.setCurrentIndex(index)
        self.set_pick.blockSignals(False)
        self.refresh()

    def showEvent(self, event):
        super().showEvent(event)
        self.clock.start()

    def hideEvent(self, event):
        super().hideEvent(event)
        self.clock.stop()

    def _tick(self):
        for card in self.cards:
            if card.item['rarity'] in ('xinghai', 'yinhe', 'mingyue'):
                card.t += .06
                card.update()

    def _clear(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()

    def _card(self, item, featured=False, discount=None):
        s = self.shop
        card = ItemCard(self, item)
        owned = item['id'] in s.owned()
        price = s.price(item['id'])
        rarity = self.tr(f'shop_rarity_{item["rarity"]}')
        if featured and not owned:
            card.caption = (self.tr('shop_price_off', price=price, base=item['price'], off=f'{discount * 10:g}')
                            if discount else f'{rarity} · {self.tr("shop_price", price=item["price"])}')
            if discount is None:
                card.set_action(self.tr('shop_draw_discount'), 'discount')
            else:
                card.set_action(self.tr('shop_buy'), 'buy', s.spendable() >= price)
        elif owned:
            worn = s.equipped().get(item['slot']) == item['id']
            card.caption = f'{rarity} · ' + self.tr('shop_owned')
            card.set_action(self.tr('shop_take_off') if worn else self.tr('shop_wear'), 'off' if worn else 'wear')
        elif item['price'] is None:
            card.caption = f'{rarity} · ' + self.tr('shop_wish_only')
            card.set_action(self.tr('shop_wish_only_short'), 'none', False)
        else:
            card.caption = f'{rarity} · {self.tr("shop_price", price=price)}'
            card.set_action(self.tr('shop_buy'), 'buy', s.spendable() >= price)
        if item.get('window'):
            card.setToolTip(self.tr('shop_limited'))
        self.cards.append(card)
        return card

    def refresh(self):
        s = self.shop
        if s is None:
            return
        self.cards = []
        self.balance.setText(self.tr('shop_balance', points=s.spendable()))
        self.earned.setText(self.tr('shop_earned', points=s.earned()))
        signed = s.state.get('signin_day') == s.today().isoformat()
        self.signin.setText(self.tr('shop_signed', streak=s.state.get('streak', 0)) if signed
                            else self.tr('shop_signin', points=shop.SIGNIN))
        self.signin.setEnabled(not signed)
        self._clear(self.featured_row)
        for item, discount in s.featured():
            self.featured_row.addWidget(self._card(item, True, discount))
        self.featured_row.addStretch(1)
        self.wish_one.setEnabled(s.spendable() >= shop.WISH_COST)
        self.wish_ten.setEnabled(s.spendable() >= shop.TEN_COST)
        self.pity.setText(self.tr('shop_pity', left=s.pity_left()))
        self._clear(self.grid)
        kind = self.set_pick.currentData() or shop.SETS[0]
        items = [i for i in shop.CATALOG if i['set'] == kind and shop.in_window(i, s.today())]
        columns = max(2, (self.width() - 40) // (ItemCard.W + 10))
        for index, item in enumerate(items):
            self.grid.addWidget(self._card(item), index // columns, index % columns)
        worn = s.equipped()
        names = [f'{self.tr("shop_slot_" + slot)}：{item_name(shop.BY_ID[worn[slot]], self.language)}'
                 for slot in shop.SLOTS if slot in worn]
        bonuses = [self.tr(f'shop_theme_{t}') for t in s.set_bonuses()]
        self.worn.setText((' · '.join(names) or self.tr('shop_wearing_nothing'))
                          + ('\n' + self.tr('shop_set_bonus', sets='、'.join(bonuses)) if bonuses else ''))
        self.preset_pick.clear()
        for preset in s.state.get('wardrobe', []):
            self.preset_pick.addItem(preset['name'])
        self.preset_wear.setEnabled(self.preset_pick.count() > 0)
        self._clear(self.book)
        for kind, (have, total) in s.collection().items():
            row = QHBoxLayout()
            label = QLabel(self.tr('shop_book_line', set=self.tr(f'shop_set_{kind}'), have=have, total=total,
                                   bonus=shop.COLLECTION_BONUS))
            bar = QProgressBar()
            bar.setRange(0, total)
            bar.setValue(have)
            bar.setTextVisible(False)
            bar.setFixedHeight(8)
            holder = QWidget()
            holder_layout = QHBoxLayout(holder)
            holder_layout.setContentsMargins(0, 0, 0, 0)
            holder_layout.addWidget(label)
            holder_layout.addWidget(bar, 1)
            self.book.addWidget(holder)

    # Actions -------------------------------------------------------------------------
    def act(self, item, action):
        s = self.shop
        if action == 'discount':
            s.draw_discount(item['id'])
        elif action == 'buy':
            s.buy(item['id'])
        elif action == 'wear':
            s.equip(item['id'])
        elif action == 'off':
            s.unequip(item['slot'])
        self.refresh()

    def _sign_in(self):
        result = self.shop.sign_in()
        if result and hasattr(self.owner.panel, 'tray_notice'):
            self.owner.panel.tray_notice(self.tr('shop_signin_done', points=result['gained'], streak=result['streak']))
        self.refresh()

    def _save_outfit(self):
        name = self.preset_name.text().strip() or self.tr('shop_preset_default', n=len(self.shop.state.get('wardrobe', [])) + 1)
        self.shop.save_outfit(name)
        self.preset_name.clear()
        self.refresh()

    def _wear_outfit(self):
        self.shop.wear_outfit(self.preset_pick.currentText())
        self.refresh()

    def _wish(self, count):
        results = self.shop.wish(count)
        if not results:
            return
        self.show_wish(results)
        self.refresh()

    def show_wish(self, results):
        starsea = getattr(self.owner.panel, 'starsea', None)
        show = WishShow(self.owner, results, self.language, bool(starsea is not None and starsea.active))
        show.show()
        show.raise_()
        self._show = show


class WishShow(QWidget):
    """She flies up into the stars and picks one (or sweeps past ten); each
    star lights in its rarity's colour, then what she found is shown."""

    def __init__(self, parent, results, language, starsea=False):
        super().__init__(parent, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.starsea = starsea
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.results, self.language = results, language
        self.ten = len(results) > 1
        self.t = 0.0
        self.length = 6.2 if self.ten else 4.4
        if parent is not None:
            self.setGeometry(parent.geometry())
        else:
            self.resize(900, 600)
        rng = random.Random(7)
        self.sky = [(rng.random(), rng.random() * .75, rng.random() * 1.6 + .4, rng.random() * 6.3) for _ in range(140)]
        best = max(results, key=lambda r: shop.RARITIES.index(r['item']['rarity']))
        self.order = sorted(range(len(results)), key=lambda i: (results[i] is best, shop.RARITIES.index(results[i]['item']['rarity'])))
        self.sprite = self._sprite()
        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self._step)
        self.timer.start()

    def _sprite(self):
        import pet_assets
        for pose in (('star_celebrate',) if self.starsea else ()) + ('celebrate', 'idle'):
            if pet_assets.frame_count(pose):
                pixmap = pet_assets.frame_for(pose, 0)
            else:
                pixmap = pet_assets.sprite_for(pose)
            if pixmap is not None and not pixmap.isNull():
                return pixmap.scaledToHeight(220, Qt.SmoothTransformation)
        return None

    def _step(self):
        self.t += .016
        if self.t > self.length + 30:
            self.close()
        self.update()

    def mousePressEvent(self, event):
        if self.t < self.length - .4:
            self.t = self.length - .4                    # Skip to what she found.
        else:
            self.close()

    def keyPressEvent(self, event):
        self.mousePressEvent(event)

    def _star_points(self):
        w, h = self.width(), self.height()
        if not self.ten:
            return [QPointF(w * .5, h * .2)]
        return [QPointF(w * (.12 + .76 * k / 9), h * (.3 - .12 * math.sin(math.pi * k / 9))) for k in range(10)]

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h, t = self.width(), self.height(), self.t
        fade = min(1.0, t / .6)
        sky = QLinearGradient(0, 0, 0, h)
        sky.setColorAt(0, QColor(8, 8, 32, int(245 * fade)))
        sky.setColorAt(1, QColor(30, 22, 74, int(245 * fade)))
        p.fillRect(self.rect(), sky)
        for x, y, size, phase in self.sky:
            a = int(fade * 160 * (.5 + .5 * math.sin(t * 2 + phase)))
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(220, 225, 255, a))
            p.drawEllipse(QPointF(x * w, y * h), size * .6, size * .6)
        points = self._star_points()
        fly_start, fly_end = .6, 2.0 if not self.ten else 1.6
        sweep_end = fly_end if not self.ten else 4.4
        # Where she is: up from below, then (ten) across the arc of stars.
        reveal = max(0.0, min(1.0, (t - (self.length - .4)) / .4))
        pos = scale = None
        if self.sprite is not None:
            if t < fly_end:
                f = max(0.0, (t - fly_start) / (fly_end - fly_start))
                f = f * f * (3 - 2 * f)
                start = QPointF(w * .5, h * 1.05)
                goal = points[0] if not self.ten else QPointF(w * .08, h * .45)
                pos = start + (goal - start) * f
                scale = 1 - (.3 if not self.ten else .55) * f
            else:
                f = min(1.0, (t - fly_end) / max(.01, sweep_end - fly_end))
                pos = points[0] if not self.ten else QPointF(w * (.08 + .84 * f), h * (.42 - .14 * math.sin(math.pi * f)))
                scale = .7 if not self.ten else .45
            if not self.ten:                                  # She hovers just below the star she picked.
                pos = pos + QPointF(0, 90 * min(1.0, max(0.0, t - fly_end) / .5))
        hand = pos + QPointF(0, 14 * scale) if pos is not None else None
        # The stars she picks light up in their rarity's colour.
        stars = []
        for index in self.order:
            point = points[index] if self.ten else points[0]
            if self.ten:
                lit_at = fly_end + (sweep_end - fly_end) * (index + .5) / 10
                if index == self.order[-1]:
                    lit_at = sweep_end + .1                   # The best one flares last.
            else:
                lit_at = fly_end
            a = max(0.0, min(1.0, (t - lit_at) / .35))
            held = 0.0
            if a > 0 and not self.ten and hand is not None:  # The star comes down into her hands.
                held = max(0.0, min(1.0, (t - lit_at - .35) / .6))
                held = held * held * (3 - 2 * held)
                point = point + (hand - point) * held
            stars.append((index, point, a * (1 - .55 * reveal), held))
        for index, point, a, held in stars:                   # Their light, behind her.
            if a <= 0:
                continue
            rarity = self.results[index]['item']['rarity']
            colour = rarity_colour(rarity, t, index / 10)
            big = 1 + shop.RARITIES.index(rarity) * .35 + (1.2 if not self.ten else 0)
            radius = 60 * big * a * (1 - .45 * held)
            glow = QRadialGradient(point, radius)
            glow.setColorAt(0, QColor(colour.red(), colour.green(), colour.blue(), int(230 * (1 - .4 * held))))
            glow.setColorAt(1, QColor(colour.red(), colour.green(), colour.blue(), 0))
            p.setPen(Qt.NoPen)
            p.setBrush(glow)
            p.drawEllipse(point, radius, radius)
            if rarity == 'xinghai':                         # Iridescent rays.
                rays = QConicalGradient(point, t * 90)
                for k in range(7):
                    rays.setColorAt(k / 6, QColor.fromHsvF((k / 6 + t * .2) % 1, .6, 1, .5))
                p.setBrush(rays)
                p.drawEllipse(point, 90 * a, 90 * a)
        if pos is not None:                                   # Her, with a trail of light.
            for k in range(8):
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(200, 190, 255, int(40 * (1 - k / 8))))
                p.drawEllipse(pos + QPointF(0, 30 * k * scale), 30 * scale * (1 - k / 10), 30 * scale * (1 - k / 10))
            sw, sh = self.sprite.width() * scale, self.sprite.height() * scale
            p.drawPixmap(QRectF(pos.x() - sw / 2, pos.y() - sh / 2, sw, sh), self.sprite, QRectF(self.sprite.rect()))
        for index, point, a, held in stars:                   # The stars themselves, in front.
            if a <= 0:
                _star(p, point, 5, QColor(220, 225, 255, 140))
                continue
            rarity = self.results[index]['item']['rarity']
            big = 1 + shop.RARITIES.index(rarity) * .35 + (1.2 if not self.ten else 0)
            p.setPen(QPen(QColor(255, 255, 255, 200), 1.2))
            _star(p, point, 10 * big * (.6 + .4 * a) * (1 - .3 * held), rarity_colour(rarity, t, index / 10))
        # What she found.
        if t >= self.length - .4:
            a = min(1.0, (t - (self.length - .4)) / .4)
            self._paint_results(p, a)

    def _paint_results(self, p, a):
        w, h = self.width(), self.height()
        n = len(self.results)
        cols = 5 if self.ten else 1
        cw, ch = (150, 120) if self.ten else (260, 200)
        rows = math.ceil(n / cols)
        x0 = (w - cols * (cw + 14)) / 2
        y0 = h * .45 if self.ten else h * .56
        p.setOpacity(a)
        for k, result in enumerate(self.results):
            item = result['item']
            box = QRectF(x0 + (k % cols) * (cw + 14), y0 + (k // cols) * (ch + 14), cw, ch)
            colour = rarity_colour(item['rarity'], self.t, k / 10)
            p.setPen(QPen(colour, 3))
            p.setBrush(QColor(24, 20, 60, 235))
            p.drawRoundedRect(box, 12, 12)
            glyph(p, item['slot'], QRectF(box.center().x() - ch * .22, box.top() + 10, ch * .44, ch * .44), colour)
            p.setPen(QColor('#FFFFFF'))
            p.setFont(QFont('Microsoft YaHei UI', 10 if self.ten else 13, QFont.Bold))
            p.drawText(QRectF(box.left(), box.top() + ch * .56, cw, 22), Qt.AlignCenter, item_name(item, self.language))
            p.setPen(colour)
            p.setFont(QFont('Microsoft YaHei UI', 8 if self.ten else 10))
            line = text(f'shop_rarity_{item["rarity"]}', self.language)
            if result['refund']:
                line += ' · ' + text('shop_refund', self.language, points=result['refund'])
            p.drawText(QRectF(box.left(), box.top() + ch * .56 + 22, cw, 18), Qt.AlignCenter, line)
        p.setPen(QColor(220, 220, 255))
        p.setFont(QFont('Microsoft YaHei UI', 9))
        p.drawText(QRectF(0, h - 40, w, 24), Qt.AlignCenter, text('shop_wish_close', self.language))
        p.setOpacity(1)
