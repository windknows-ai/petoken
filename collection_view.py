"""The workbench Collection page and the usage-goal dialog (2.0)."""
from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (QComboBox, QDialog, QDoubleSpinBox, QFormLayout, QGridLayout, QHBoxLayout, QLabel,
                               QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget)

import theme
from companion import STICKERS
from localization import text
from pet_assets import ASSETS_DIR

GLYPHS = dict(first_project='⚑', first_weekly='☰', focus_10='◔', streak_7='7',
              goal_week='✓', todos_100='100')
COLORS = dict(first_project='#8F7CFF', first_weekly='#6FA8FF', focus_10='#5CC8B8', streak_7='#FF8FB1',
              goal_week='#7BCB6B', todos_100='#FFB84D')


class StickerBadge(QWidget):
    """A sticker: its art when it exists, otherwise a drawn badge; grey until earned."""

    def __init__(self, sticker, earned_at, language):
        super().__init__()
        self.sticker, self.earned_at = sticker, earned_at
        self.setFixedSize(108, 136)
        self.art = None
        path = ASSETS_DIR / 'v2_0' / f'sticker_{sticker}.png'
        if path.is_file():
            from PySide6.QtGui import QPixmap
            pixmap = QPixmap(str(path))
            self.art = None if pixmap.isNull() else pixmap
        self.name = text(f'sticker_{sticker}', language)
        how = text(f'sticker_{sticker}_how', language)
        when = (datetime.fromtimestamp(earned_at).strftime('%Y-%m-%d') if earned_at else '')
        self.setToolTip(how + (f'\n{text("sticker_earned_on", language, date=when)}' if when else ''))
        self.caption = when or text('sticker_locked', language)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        box = QRectF(16, 4, 76, 76)
        if not self.earned_at:
            p.setOpacity(.35)
        if self.art is not None:
            p.drawPixmap(box.toRect(), self.art)
        else:
            color = QColor(COLORS.get(self.sticker, theme.VIOLET) if self.earned_at else '#B9B3C4')
            p.setPen(QPen(QColor('#FFFFFF'), 4))
            p.setBrush(color)
            p.drawEllipse(box)
            p.setPen(QColor('#FFFFFF'))
            font = QFont('Segoe UI', 22 if len(GLYPHS.get(self.sticker, '')) < 3 else 17, QFont.Bold)
            p.setFont(font)
            p.drawText(box, Qt.AlignCenter, GLYPHS.get(self.sticker, '★'))
        p.setOpacity(1)
        p.setPen(QColor(theme.INK))
        p.setFont(QFont('Microsoft YaHei UI', 9, QFont.DemiBold))
        p.drawText(QRectF(0, 84, self.width(), 20), Qt.AlignCenter, self.name)
        p.setPen(QColor(theme.MUTED))
        p.setFont(QFont('Microsoft YaHei UI', 8))
        p.drawText(QRectF(0, 104, self.width(), 18), Qt.AlignCenter, self.caption)


class SkinCard(QWidget):
    """A preview of a star-ring skin (or her Starsea form): her with the ring
    around her, greyed with its price until unlocked; a click puts it on."""

    W, H = 148, 150

    def __init__(self, choice, on_click):
        super().__init__()
        self.choice, self.on_click = choice, on_click
        self.setFixedSize(self.W, self.H)
        self.unlocked = self.current = False
        self.name = self.caption = ''
        self._sprite = None
        self.setCursor(Qt.PointingHandCursor)

    def set_state(self, name, caption, unlocked, current, tip=''):
        self.name, self.caption, self.unlocked, self.current = name, caption, unlocked, current
        self.setCursor(Qt.PointingHandCursor if unlocked and not current else Qt.ArrowCursor)
        self.setToolTip(tip)
        self.update()

    def sprite(self):
        if self._sprite is None:
            import pet_assets
            pose = 'star_idle' if self.choice == 'starsea' and pet_assets.has_own_art('star_idle') else 'idle'
            pixmap = pet_assets.frame_for(pose, 0) if pet_assets.frame_count(pose) else pet_assets.sprite_for(pose)
            self._sprite = pixmap.scaledToHeight(92, Qt.SmoothTransformation) if pixmap else False
        return self._sprite or None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.unlocked and not self.current:
            self.on_click(self.choice)

    def _ring(self, p, front):
        import math
        import halo_scene
        cx, cy, rx, ry, tilt = self.W / 2, 72, 60, 15, math.radians(-7)

        def point(t):
            x, y = rx * math.cos(t), ry * math.sin(t)
            return (cx + x * math.cos(tilt) - y * math.sin(tilt), cy + x * math.sin(tilt) + y * math.cos(tilt))
        steps = 48
        span = [(math.pi * i / steps) if front else (math.pi + math.pi * i / steps) for i in range(steps + 1)]
        aurora = self.choice == 'aurora'
        for width, alpha, core in ((7, 45, False), (3, 120, False), (1.3, 230, True)):
            for a, b in zip(span, span[1:]):
                rgb = halo_scene.aurora_tint((a + b) / 2, 0) if aurora else (150, 132, 255)
                if core:
                    rgb = tuple(round(c + (255 - c) * .6) for c in rgb)
                pen = QPen(QColor(*rgb, alpha), width)
                pen.setCapStyle(Qt.FlatCap)
                p.setPen(pen)
                (x1, y1), (x2, y2) = point(a), point(b)
                p.drawLine(QPointF(x1, y1), QPointF(x2, y2))
        if aurora:
            return            # The aurora ring shows with no tasks: no stars.
        meteor = self.choice == 'meteor'
        tail = 2.6 if meteor else .35
        heads = ((.5, 1.7, 2.9) if front else (3.9, 5.4)) if meteor else ((.9, 2.4) if front else (4.0, 5.3))
        for head in heads:
            for k in range(20):
                t0, t1 = head - tail * k / 20, head - tail * (k + 1) / 20
                fade = 1 - k / 20
                color = QColor(255, 236, 190, int(235 * fade)) if meteor else QColor(220, 210, 255, int(200 * fade))
                pen = QPen(color, (3.4 if meteor else 2.6) * fade + .4)
                pen.setCapStyle(Qt.RoundCap)
                p.setPen(pen)
                p.drawLine(QPointF(*point(t0)), QPointF(*point(t1)))
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255))
            x, y = point(head)
            p.drawEllipse(QPointF(x, y), 3.2, 3.2)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.setPen(QPen(QColor(theme.VIOLET if self.current else theme.BORDER_SOFT), 2.5 if self.current else 1))
        p.setBrush(QColor(36, 30, 78) if self.unlocked else QColor(70, 66, 96))
        p.drawRoundedRect(QRectF(2, 2, self.W - 4, 104), 10, 10)
        if not self.unlocked:
            p.setOpacity(.45)
        self._ring(p, False)
        sprite = self.sprite()
        if sprite is not None:
            p.drawPixmap(int((self.W - sprite.width()) / 2), 100 - sprite.height(), sprite)
        self._ring(p, True)
        p.setOpacity(1)
        p.setPen(QColor(theme.INK))
        p.setFont(QFont('Microsoft YaHei UI', 9, QFont.DemiBold))
        p.drawText(QRectF(0, 110, self.W, 18), Qt.AlignCenter, self.name)
        p.setPen(QColor(theme.VIOLET if self.current else theme.MUTED))
        p.setFont(QFont('Microsoft YaHei UI', 8))
        p.drawText(QRectF(0, 128, self.W, 18), Qt.AlignCenter, self.caption)


class CollectionPage(QWidget):
    """Points, what they came from, and the sticker wall."""

    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        # Everything scrolls together, so nothing overlaps in a short window.
        from PySide6.QtWidgets import QFrame, QScrollArea
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        inner.setObjectName('collectionInner')
        scroll.viewport().setObjectName('collectionViewport')
        scroll.setStyleSheet('QScrollArea, QWidget#collectionViewport, QWidget#collectionInner '
                             '{ background: transparent; }')
        scroll.setWidget(inner)
        outer.addWidget(scroll)
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)
        self.intro = QLabel()
        self.intro.setObjectName('muted')
        self.intro.setWordWrap(True)
        layout.addWidget(self.intro)
        self.points = QLabel()
        self.points.setObjectName('summary')
        layout.addWidget(self.points, 0, Qt.AlignLeft)
        # 2.4 stardust: how much, how to earn it, and what it unlocks (a preview each).
        from PySide6.QtWidgets import QProgressBar
        self.stardust_title = QLabel()
        self.stardust_title.setObjectName('section')
        layout.addWidget(self.stardust_title)
        star_row = QHBoxLayout()
        self.stardust = QLabel()
        self.stardust.setObjectName('summary')
        star_row.addWidget(self.stardust)
        self.stardust_bar = QProgressBar()
        self.stardust_bar.setTextVisible(False)
        self.stardust_bar.setFixedHeight(10)
        star_row.addWidget(self.stardust_bar, 1)
        self.stardust_next = QLabel()
        self.stardust_next.setObjectName('muted')
        star_row.addWidget(self.stardust_next)
        layout.addLayout(star_row)
        self.stardust_earn = QLabel()
        self.stardust_earn.setObjectName('muted')
        self.stardust_earn.setWordWrap(True)
        layout.addWidget(self.stardust_earn)
        cards = QHBoxLayout()
        cards.setSpacing(10)
        self.skin_cards = {choice: SkinCard(choice, self._card_chosen)
                           for choice in ('default', 'meteor', 'aurora', 'starsea')}
        for card in self.skin_cards.values():
            cards.addWidget(card)
        cards.addStretch(1)
        layout.addLayout(cards)
        self.wall = QGridLayout()
        self.wall.setHorizontalSpacing(8)
        layout.addLayout(self.wall)
        self.log_title = QLabel()
        self.log_title.setObjectName('section')
        layout.addWidget(self.log_title)
        self.log = QListWidget()
        self.log.setMinimumHeight(180)
        layout.addWidget(self.log, 1)

    @property
    def language(self):
        return self.owner.panel.prefs.get('language')

    def apply_language(self):
        self.intro.setText(text('collection_intro', self.language))
        self.log_title.setText(text('collection_log', self.language))
        self.refresh()

    def _flow(self):
        """As many badges per row as fit."""
        columns = max(2, min(len(STICKERS), (self.width() - 36) // 114))
        if columns == self._columns:
            return
        self._columns = columns
        for badge in getattr(self, 'badges', []):
            self.wall.removeWidget(badge)
        for index, badge in enumerate(getattr(self, 'badges', [])):
            self.wall.addWidget(badge, index // columns, index % columns)

    def showEvent(self, event):
        super().showEvent(event)
        self._columns = None
        self._flow()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if getattr(self, 'badges', None):
            self._flow()

    def refresh(self):
        store = self.owner.store
        try:
            total, earned, log = store.points(), store.achievements(), store.points_log(30)
        except Exception:
            total, earned, log = 0, {}, []
        language = self.language
        self.points.setText(text('collection_points', language, points=total))
        self._refresh_stardust(language)
        while self.wall.count():
            item = self.wall.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().setParent(None)
                item.widget().deleteLater()
        self.badges = [StickerBadge(sticker, earned.get(sticker), language) for sticker in STICKERS]
        self._columns = None
        self._flow()
        self.log.clear()
        for row in log:
            when = datetime.fromtimestamp(row['at']).strftime('%m-%d %H:%M')
            self.log.addItem(QListWidgetItem(text('collection_log_line', language, when=when,
                                                  reason=text(f'points_{row["reason"]}', language),
                                                  points=row['points'])))
        if not log:
            self.log.addItem(QListWidgetItem(text('collection_empty', language)))


    def _refresh_stardust(self, language):
        from stardust import SKINS, UNLOCKS, next_unlock, unlocked
        panel = self.owner.panel
        dust = getattr(panel, 'stardust', None)
        total = dust.total() if dust is not None else 0
        have = unlocked(total)
        coming = next_unlock(total)
        self.stardust_title.setText(text('stardust_section', language))
        self.stardust.setText(text('stardust_total', language, points=total))
        goal = coming and dict(UNLOCKS)[coming[0]] or UNLOCKS[-1][1]
        self.stardust_bar.setRange(0, goal)
        self.stardust_bar.setValue(min(total, goal))
        self.stardust_next.setText(text('stardust_next', language, left=coming[1],
                                        name=text(f'stardust_name_{coming[0]}', language))
                                   if coming else text('stardust_all', language))
        self.stardust_earn.setText(text('stardust_earn', language))
        need = dict(UNLOCKS)
        skin = panel.prefs.get('ring_skin', 'default')
        starsea = getattr(panel, 'starsea', None)
        for choice, card in self.skin_cards.items():
            key = 'starsea' if choice == 'starsea' else f'skin_{choice}'
            unlocked = choice == 'default' or key in have
            if choice == 'starsea':
                unlocked = unlocked and starsea is not None and starsea.art_ready()
                current = bool(starsea is not None and starsea.active)
            else:
                current = skin == choice
            caption = (text('stardust_card_on', language) if current else
                       text('stardust_card_wear', language) if unlocked else
                       text('stardust_card_locked', language, need=need.get(key, 0)))
            card.set_state(text(f'stardust_card_{choice}', language), caption, unlocked, current,
                           text(f'stardust_card_{choice}_tip', language))

    def _card_chosen(self, choice):
        panel = self.owner.panel
        if choice == 'starsea':
            starsea = getattr(panel, 'starsea', None)
            if starsea is not None:
                starsea.toggle()
        else:
            panel.prefs['ring_skin'] = choice
            try:
                panel.persist()
            except Exception:
                pass
            panel.apply_ring_skin()
        self._refresh_stardust(self.language)


class GoalDialog(QDialog):
    """A project's weekly limit, in tokens and/or API-equivalent dollars."""

    def __init__(self, parent, language, project, goal=None):
        super().__init__(parent)
        self.setWindowTitle(text('goal_title', language, project=project['name']))
        self.setMinimumWidth(380)
        layout = QVBoxLayout(self)
        intro = QLabel(text('goal_intro', language))
        intro.setWordWrap(True)
        intro.setObjectName('muted')
        layout.addWidget(intro)
        form = QFormLayout()
        # A number and a unit (million or billion tokens).
        self.tokens = QDoubleSpinBox()
        self.tokens.setRange(0, 999_999)
        self.tokens.setDecimals(2)
        self.tokens.setSpecialValueText(text('goal_none', language))
        self.unit = QComboBox()
        self.unit.addItem(text('goal_unit_million', language), 1_000_000)
        self.unit.addItem(text('goal_unit_billion', language), 1_000_000_000)
        amount = (goal or {}).get('weekly_tokens') or 0
        if amount >= 1_000_000_000 and amount % 10_000_000 == 0:
            self.unit.setCurrentIndex(1)
        self.tokens.setValue(amount / self.unit.currentData())
        token_row = QWidget()
        line = QHBoxLayout(token_row)
        line.setContentsMargins(0, 0, 0, 0)
        line.addWidget(self.tokens, 1)
        line.addWidget(self.unit)
        self.usd = QDoubleSpinBox()
        self.usd.setRange(0, 100_000)
        self.usd.setDecimals(2)
        self.usd.setSpecialValueText(text('goal_none', language))
        self.usd.setPrefix('$ ')
        self.usd.setValue((goal or {}).get('weekly_usd') or 0)
        form.addRow(text('goal_tokens', language), token_row)
        form.addRow(text('goal_usd', language), self.usd)
        layout.addLayout(form)
        row = QHBoxLayout()
        row.addStretch(1)
        cancel = QPushButton(text('launch_cancel', language))
        cancel.clicked.connect(self.reject)
        ok = QPushButton(text('preset_save', language))
        ok.setDefault(True)
        ok.clicked.connect(self.accept)
        row.addWidget(cancel)
        row.addWidget(ok)
        layout.addLayout(row)

    def values(self):
        return dict(weekly_tokens=round(self.tokens.value() * self.unit.currentData()) or None,
                    weekly_usd=round(self.usd.value(), 2) or None)
