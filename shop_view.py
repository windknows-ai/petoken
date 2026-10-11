"""2.5 Stardust Shop page (workbench) and the wishing show."""
from __future__ import annotations

import math
import random

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import (QColor, QConicalGradient, QFont, QLinearGradient, QPainter, QPainterPath, QPen,
                           QPixmap, QPolygonF, QRadialGradient)
from PySide6.QtWidgets import (QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QProgressBar,
                               QPushButton, QScrollArea, QVBoxLayout, QWidget)

import shop
import theme
from localization import text

# Rarity colours, low to high: deep blue, flashing white, warm gold, flowing silver, iridescent.
RARITY_COLOURS = dict(fanxing=(52, 82, 196), mingyue=(246, 248, 255), haori=(246, 190, 72),
                      yinhe=(160, 178, 222), xinghai=(196, 150, 255))


def rarity_colour(rarity, t=0.0, at=0.0):
    """The rarity's colour at time ``t``; Galaxy shimmers, Starsea cycles hues, Moon flashes."""
    if rarity == 'xinghai':
        return QColor.fromHsvF(((t * .25 + at) % 1.0), .55, 1.0)
    if rarity == 'yinhe':                                    # Steel blue silver with light running through.
        v = .5 + .5 * math.sin(t * 2.2 + at * 6)
        return QColor.fromRgbF(.56 + .36 * v, .62 + .32 * v, .82 + .18 * v)
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


DECOR_PARTS = ('head', 'back', 'ground', 'buddy', 'star')


def item_name(item, language):
    names = item.get('names')
    if names:                                               # Drawn decorations carry their own names.
        return names['en'] if str(language).startswith('en') else names['zh_CN']
    return text(f'shop_item_{item["name"]}', language)


_ART = {}


def item_art(item, frame=0):
    """The drawn picture of an item (Codex's art), or None while it has none yet."""
    frames = item.get('art')
    if not frames:
        return None
    name = frames[frame % len(frames)]
    if name not in _ART:
        pixmap = QPixmap(str(shop.ASSETS / name))
        _ART[name] = pixmap if not pixmap.isNull() else None
    return _ART[name]


_FITTED = {}


def draw_item(p, item, rect, colour):
    """The item's picture fitted into ``rect``; a drawn symbol when it has no art yet."""
    art = item_art(item)
    if art is None:
        glyph(p, item['slot'], rect, colour)
        return
    ratio = p.device().devicePixelRatioF() if p.device() is not None else 1.0
    key = (item['id'], int(rect.width() * ratio), int(rect.height() * ratio))
    if key not in _FITTED:                                  # Scaled once, not every frame.
        fitted = art.scaled(key[1], key[2], Qt.KeepAspectRatio, Qt.SmoothTransformation)
        fitted.setDevicePixelRatio(ratio)
        _FITTED[key] = fitted
    fitted = _FITTED[key]
    w, h = fitted.width() / ratio, fitted.height() / ratio
    p.drawPixmap(QRectF(rect.center().x() - w / 2, rect.center().y() - h / 2, w, h), fitted, QRectF(fitted.rect()))


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
        draw_item(p, self.item, QRectF(box.center().x() - 40, 12, 80, 80), colour)
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
        self.scroll = scroll
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
        # Decorations have parts: a row of small tabs (all, head, back, ground, buddy, task star).
        self.parts = QHBoxLayout()
        self.parts.setSpacing(6)
        self.part_buttons = {}
        for part in ('all',) + DECOR_PARTS:
            button = QPushButton()
            button.setCheckable(True)
            button.setObjectName('chip')
            button.clicked.connect(lambda _=False, part=part: self._pick_part(part))
            self.part_buttons[part] = button
            self.parts.addWidget(button)
        self.parts.addStretch(1)
        layout.addLayout(self.parts)
        self.part = 'all'
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
        for part, button in self.part_buttons.items():
            button.setText(self.tr('shop_part_all') if part == 'all' else self.tr(f'shop_slot_{part}'))
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
        decor = kind == 'decor'
        for part, button in self.part_buttons.items():
            button.setVisible(decor)
            button.setChecked(part == self.part)
            if decor and part != 'all':
                have = sum(1 for i in items if i['slot'] == part and i['id'] in s.owned())
                total = sum(1 for i in items if i['slot'] == part)
                button.setText(f'{self.tr("shop_slot_" + part)} {have}/{total}')
        if decor and self.part != 'all':
            items = [i for i in items if i['slot'] == self.part]
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

    def _pick_part(self, part):
        self.part = part
        self.refresh()

    # Actions -------------------------------------------------------------------------
    def act(self, item, action):
        self._keep_place()
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

    def _keep_place(self):
        """Rebuilding the cards must not move the page: put it back where it was."""
        bar = self.scroll.verticalScrollBar()
        value = bar.value()
        QTimer.singleShot(0, lambda: bar.setValue(value))
        QTimer.singleShot(30, lambda: bar.setValue(value))
        self.setFocus()

    def _sign_in(self):
        self._keep_place()
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
        self._keep_place()
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


from wish_show import WishShow  # noqa: E402  (the show lives in its own module)
