"""The workbench Collection page and the usage-goal dialog (2.0)."""
from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QRectF, Qt
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


class CollectionPage(QWidget):
    """Points, what they came from, and the sticker wall."""

    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)
        self.intro = QLabel()
        self.intro.setObjectName('muted')
        self.intro.setWordWrap(True)
        layout.addWidget(self.intro)
        self.points = QLabel()
        self.points.setObjectName('summary')
        layout.addWidget(self.points, 0, Qt.AlignLeft)
        self.wall = QGridLayout()
        self.wall.setHorizontalSpacing(8)
        layout.addLayout(self.wall)
        self.log_title = QLabel()
        self.log_title.setObjectName('section')
        layout.addWidget(self.log_title)
        self.log = QListWidget()
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
