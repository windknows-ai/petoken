"""Reports > "App time" (2.3): how long each program was in front.

Reads the panel's local ``app_time.AppTimeStore``. Recording is off until the
user turns it on (here or in Settings > Rest); only program names and times
are kept, on this computer.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QHeaderView, QLabel, QProgressBar, QPushButton,
                               QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

import theme
from app_time import format_duration
from localization import text

RANGES = ('today', 'yesterday', 'week', 'days7')
SHOWN = 30                       # Programs listed; the rest are summed as "Other".


def days(kind, now=None):
    """('YYYY-MM-DD', 'YYYY-MM-DD') inclusive for a range."""
    today = datetime.fromtimestamp(time.time() if now is None else now).date()
    if kind == 'yesterday':
        start = end = today - timedelta(days=1)
    elif kind == 'week':
        start, end = today - timedelta(days=today.weekday()), today
    elif kind == 'days7':
        start, end = today - timedelta(days=6), today
    else:
        start = end = today
    return start.isoformat(), end.isoformat()


class AppTimeView(QWidget):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.panel = page.panel
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        top = QHBoxLayout()
        self.range = QComboBox()
        for kind in RANGES:
            self.range.addItem('', kind)
        self.range.currentIndexChanged.connect(lambda _: self.render())
        top.addWidget(self.range)
        self.total = QLabel()
        self.total.setStyleSheet('font-weight:600;')
        top.addWidget(self.total)
        top.addStretch()
        self.turn = QPushButton()
        self.turn.setCursor(Qt.PointingHandCursor)
        self.turn.clicked.connect(self.toggle_recording)
        top.addWidget(self.turn)
        self.clear_button = QPushButton()
        self.clear_button.setCursor(Qt.PointingHandCursor)
        self.clear_button.clicked.connect(self.clear)
        top.addWidget(self.clear_button)
        layout.addLayout(top)
        self.note = QLabel()
        self.note.setObjectName('muted')
        self.note.setWordWrap(True)
        layout.addWidget(self.note)
        self.list = QTreeWidget()
        self.list.setRootIsDecorated(False)
        self.list.setColumnCount(3)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list.setStyleSheet('QTreeWidget { outline: 0px; }')
        header = self.list.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        layout.addWidget(self.list, 1)
        self.empty = QLabel()
        self.empty.setObjectName('muted')
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.setWordWrap(True)
        layout.addWidget(self.empty, 1)
        self.apply_language()

    @property
    def language(self):
        return self.panel.prefs.get('language')

    def tr(self, key, **values):
        return text(key, self.language, **values)

    @property
    def recording(self):
        return bool(self.panel.prefs.get('app_time_enabled'))

    def apply_language(self):
        for index, kind in enumerate(RANGES):
            self.range.setItemText(index, self.tr(f'app_time_range_{kind}'))
        self.clear_button.setText(self.tr('app_time_clear'))
        self.list.setHeaderLabels([self.tr(f'app_time_col_{key}') for key in ('app', 'time', 'share')])
        self.render()

    def toggle_recording(self):
        self.panel.set_app_time(not self.recording)
        self.render()

    def clear(self):
        store = getattr(self.panel, 'app_time_store', None)
        if store is not None:
            try:
                store.clear()
            except Exception:
                pass
        self.render()

    def rows(self):
        store = getattr(self.panel, 'app_time_store', None)
        if store is None:
            return []
        tracker = getattr(self.panel, 'app_time_tracker', None)
        if tracker is not None:
            tracker.flush()                   # Include the last minute.
        try:
            return store.range_totals(*days(self.range.currentData()))
        except Exception:
            return []

    def render(self):
        on = self.recording
        self.turn.setText(self.tr('app_time_stop' if on else 'app_time_start'))
        self.note.setText(self.tr('app_time_note_on' if on else 'app_time_note_off'))
        rows = [row for row in self.rows() if row[2] >= 30]   # Under half a minute is noise.
        language = self.language
        total = sum(seconds for _exe, _name, seconds in rows)
        self.total.setText(self.tr('app_time_total', time=format_duration(total, language)) if rows else '')
        self.clear_button.setEnabled(bool(rows))
        self.list.clear()
        if len(rows) > SHOWN:
            rest = sum(seconds for _exe, _name, seconds in rows[SHOWN:])
            rows = rows[:SHOWN] + [('', self.tr('app_time_other'), rest)]
        top = rows[0][2] if rows else 1
        for exe, name, seconds in rows:
            item = QTreeWidgetItem([name or exe, format_duration(seconds, language), ''])
            item.setToolTip(0, exe)
            self.list.addTopLevelItem(item)
            bar = QProgressBar()
            bar.setRange(0, 1000)
            bar.setValue(int(1000 * seconds / top))
            bar.setTextVisible(False)
            bar.setFixedHeight(8)
            bar.setStyleSheet('QProgressBar { border:none; border-radius:4px; background:%s; }'
                              ' QProgressBar::chunk { border-radius:4px; background:%s; }'
                              % (theme.BORDER, theme.SELECT_BAR))
            holder = QWidget()
            box = QHBoxLayout(holder)
            box.setContentsMargins(6, 0, 6, 0)
            box.addWidget(bar)
            self.list.setItemWidget(item, 2, holder)
        self.list.setVisible(bool(rows))
        self.empty.setVisible(not rows)
        self.empty.setText(self.tr('app_time_empty_on' if on else 'app_time_empty_off'))
