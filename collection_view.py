"""The workbench Collection page and the usage-goal dialog (2.0)."""
from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
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
        p.setPen(QColor('#ECE8FF') if getattr(self, 'dark', False) else QColor(theme.INK))
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
            return
        meteor = self.choice == 'meteor'
        tail = .6 if meteor else .35
        heads = ((.9, 2.4) if front else (4.0, 5.3))
        for head in heads:
            for k in range(20):
                t0, t1 = head - tail * k / 20, head - tail * (k + 1) / 20
                fade = 1 - k / 20
                color = QColor(255, 244, 222, int(220 * fade)) if meteor else QColor(220, 210, 255, int(200 * fade))
                pen = QPen(color, 2.6 * fade + .4)
                pen.setCapStyle(Qt.RoundCap)
                p.setPen(pen)
                p.drawLine(QPointF(*point(t0)), QPointF(*point(t1)))
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255))
            x, y = point(head)
            p.drawEllipse(QPointF(x, y), 3.2, 3.2)

    def _shooting_stars(self, p):
        from PySide6.QtGui import QLinearGradient
        for (hx, hy), length, rgb in (((18, 40), 38, (255, 226, 170)), ((122, 30), 30, (190, 220, 255))):
            tx, ty = hx + length * .86, hy - length * .5
            gradient = QLinearGradient(tx, ty, hx, hy)
            gradient.setColorAt(0, QColor(*rgb, 0))
            gradient.setColorAt(1, QColor(255, 255, 255, 240))
            p.setPen(QPen(gradient, 2.2))
            p.drawLine(QPointF(tx, ty), QPointF(hx, hy))
            p.setPen(QPen(QColor(255, 255, 255, 210), 1))
            p.drawLine(QPointF(hx - 5, hy), QPointF(hx + 5, hy))
            p.drawLine(QPointF(hx, hy - 5), QPointF(hx, hy + 5))

    def _curtains(self, p):
        import math
        from PySide6.QtGui import QLinearGradient
        import halo_scene
        for i in range(40):
            angle = math.pi + math.pi * (i + .5) / 40
            x = self.W / 2 + 60 * math.cos(angle)
            y = 72 + 15 * math.sin(angle)
            height = 30 + 34 * (.5 + .5 * math.sin(angle * 3.1)) * (.6 + .4 * math.cos(angle * 1.7))
            tint = halo_scene.aurora_tint(angle, 0)
            gradient = QLinearGradient(x, y, x, y - height)
            gradient.setColorAt(0, QColor(*tint, 170))
            gradient.setColorAt(1, QColor(*tint, 0))
            pen = QPen(gradient, 3.4)
            pen.setCapStyle(Qt.FlatCap)
            p.setPen(pen)
            p.drawLine(QPointF(x, y), QPointF(x, y - height))

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.setPen(QPen(QColor(theme.VIOLET if self.current else theme.BORDER_SOFT), 2.5 if self.current else 1))
        p.setBrush(QColor(36, 30, 78) if self.unlocked else QColor(70, 66, 96))
        p.drawRoundedRect(QRectF(2, 2, self.W - 4, 104), 10, 10)
        # The scene is drawn whole first (ring behind her, her, ring in front),
        # then faded if locked, so she always hides the back of the ring.
        from PySide6.QtGui import QImage
        scene = QImage(self.W * 2, self.H * 2, QImage.Format_ARGB32_Premultiplied)
        scene.setDevicePixelRatio(2)
        scene.fill(Qt.transparent)
        q = QPainter(scene)
        q.setRenderHint(QPainter.Antialiasing)
        q.setRenderHint(QPainter.SmoothPixmapTransform)
        if self.choice == 'meteor':
            self._shooting_stars(q)
        elif self.choice == 'aurora':
            self._curtains(q)
        self._ring(q, False)
        sprite = self.sprite()
        if sprite is not None:
            q.drawPixmap(int((self.W - sprite.width()) / 2), 100 - sprite.height(), sprite)
        self._ring(q, True)
        q.end()
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(2, 2, self.W - 4, 104), 10, 10)
        p.save()
        p.setClipPath(clip)
        p.setOpacity(1.0 if self.unlocked else .45)
        p.drawImage(QRectF(0, 0, self.W, self.H), scene)
        p.restore()
        p.setOpacity(1)
        p.setPen(QColor(theme.INK))
        p.setFont(QFont('Microsoft YaHei UI', 9, QFont.DemiBold))
        p.drawText(QRectF(0, 110, self.W, 18), Qt.AlignCenter, self.name)
        p.setPen(QColor('#F3C96B' if self.current else '#A9A2D6') if getattr(self, 'dark', False)
                 else QColor(theme.VIOLET if self.current else theme.MUTED))
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
        # Stardust (ring skins, the Starsea form) lives in the Stardust Wardrobe (wardrobe.py).
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
