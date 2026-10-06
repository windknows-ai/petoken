"""Workbench "Reports" page (V1.6 D): today / this week, and task history.

The numbers come from ``reports`` in a worker thread (Codex history can
take seconds); the page shows "Counting…" meanwhile and keeps the result
for RELOAD_S before reading again. Double-clicking a history row jumps to
that task's window when it is still open.
"""
from __future__ import annotations

import threading
import time

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (QComboBox, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                               QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

import reports
import theme
from localization import text
from pricing import convert_usd, format_cost
from providers import PROVIDER_NAMES
from token_format import format_tokens

RELOAD_S = 300
RANGES = (('week', 7), ('month', 30), ('all', None))


class _Loader(QObject):
    loaded = Signal(object)


def duration_text(seconds):
    minutes = int(seconds or 0) // 60
    hours, minutes = divmod(minutes, 60)
    return f'{hours}h {minutes}m' if hours else f'{minutes}m'


class ReportPage(QWidget):
    def __init__(self, panel, loader=None):
        super().__init__()
        self.panel = panel
        self.load_data = loader or reports.load
        self.data = None
        self.loaded_at = 0.0
        self.loading = False
        self.kind = 'today'
        self._signals = _Loader()
        self._signals.loaded.connect(self._loaded)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)
        self.intro = QLabel()
        self.intro.setObjectName('muted')
        self.intro.setWordWrap(True)
        layout.addWidget(self.intro)
        top = QHBoxLayout()
        self.today_button = QPushButton()
        self.week_button = QPushButton()
        for button, kind in ((self.today_button, 'today'), (self.week_button, 'week')):
            button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(lambda _=False, k=kind: self.set_kind(k))
            top.addWidget(button)
        top.addStretch()
        self.status = QLabel()
        self.status.setObjectName('muted')
        top.addWidget(self.status)
        self.reload_button = QPushButton()
        self.reload_button.setCursor(Qt.PointingHandCursor)
        self.reload_button.clicked.connect(lambda: self.refresh(force=True))
        top.addWidget(self.reload_button)
        layout.addLayout(top)
        card = QFrame()
        card.setObjectName('card')
        card.setStyleSheet('QFrame#card { border:1px solid palette(mid); border-radius:12px; }')
        grid = QGridLayout(card)
        grid.setContentsMargins(14, 12, 14, 12)
        grid.setHorizontalSpacing(18)
        self.tiles = {}
        for index, key in enumerate(('tasks', 'time', 'files', 'tokens', 'cost', 'change')):
            value, caption = QLabel('—'), QLabel()
            value.setStyleSheet('font-size:20px; font-weight:600;')
            caption.setObjectName('muted')
            grid.addWidget(value, 0 if index < 3 else 2, index % 3)
            grid.addWidget(caption, 1 if index < 3 else 3, index % 3)
            self.tiles[key] = (value, caption)
        self.breakdown = QLabel()
        self.breakdown.setObjectName('muted')
        self.breakdown.setWordWrap(True)
        grid.addWidget(self.breakdown, 4, 0, 1, 3)
        layout.addWidget(card)
        head = QHBoxLayout()
        self.history_title = QLabel()
        self.history_title.setObjectName('section')
        head.addWidget(self.history_title)
        head.addStretch()
        self.query = QLineEdit()
        self.query.setClearButtonEnabled(True)
        self.query.textChanged.connect(lambda _: self.render_history())
        head.addWidget(self.query, 1)
        self.provider = QComboBox()
        for key in (None, 'claude', 'codex'):
            self.provider.addItem('', key)
        self.provider.currentIndexChanged.connect(lambda _: self.render_history())
        head.addWidget(self.provider)
        self.range = QComboBox()
        for key, days in RANGES:
            self.range.addItem('', days)
        self.range.setCurrentIndex(1)
        self.range.currentIndexChanged.connect(lambda _: self.render_history())
        head.addWidget(self.range)
        layout.addLayout(head)
        self.history = QTreeWidget()
        self.history.setRootIsDecorated(False)
        self.history.setColumnCount(6)
        self.history.itemDoubleClicked.connect(self._open_row)
        self.history.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        header = self.history.header()
        header.setStretchLastSection(False)
        for column in range(6):
            header.setSectionResizeMode(column, QHeaderView.Stretch if column in (2, 3)
                                        else QHeaderView.ResizeToContents)
        self.setStyleSheet('QPushButton:checked { background:%s; border-color:%s; font-weight:600; }'
                           % (theme.TAB_SELECTED_BG, theme.SELECT_BAR))
        layout.addWidget(self.history, 1)
        self.apply_language()

    @property
    def language(self):
        return self.panel.prefs.get('language')

    def tr(self, key, **values):
        return text(key, self.language, **values)

    def apply_language(self):
        self.intro.setText(self.tr('report_intro'))
        self.today_button.setText(self.tr('report_today'))
        self.week_button.setText(self.tr('report_week'))
        self.reload_button.setText(self.tr('report_reload'))
        self.history_title.setText(self.tr('report_history'))
        self.query.setPlaceholderText(self.tr('report_search'))
        self.provider.setItemText(0, self.tr('wb_notify_all'))
        for index, key in enumerate(('claude', 'codex'), 1):
            self.provider.setItemText(index, PROVIDER_NAMES[key])
        for index, (key, _days) in enumerate(RANGES):
            self.range.setItemText(index, self.tr(f'report_range_{key}'))
        self.history.setHeaderLabels([self.tr(f'report_col_{key}') for key in
                                      ('when', 'app', 'title', 'project', 'tokens', 'cost')])
        for key, (_value, caption) in self.tiles.items():
            caption.setText(self.tr(f'report_tile_{key}'))
        for key in ('time', 'files'):
            for widget in self.tiles[key]:
                widget.setToolTip(self.tr(f'report_tile_{key}_tip'))
        self.render()

    # Loading -------------------------------------------------------------
    def refresh(self, force=False):
        if self.loading or (not force and self.data is not None and time.time() - self.loaded_at < RELOAD_S):
            return
        self.loading = True
        self.status.setText(self.tr('report_loading'))
        self.reload_button.setEnabled(False)

        def work():
            try:
                data = self.load_data()
            except Exception:
                data = dict(events=[], history=[], missing=['claude', 'codex'])
            self._signals.loaded.emit(data)
        threading.Thread(target=work, daemon=True).start()

    def _loaded(self, data):
        self.loading = False
        self.data, self.loaded_at = data, time.time()
        self.reload_button.setEnabled(True)
        self.render()

    def set_kind(self, kind):
        self.kind = kind
        self.render()

    # Rendering -----------------------------------------------------------
    def _cost(self, usd):
        currency, rates = getattr(self.panel, 'currency', 'USD'), (getattr(self.panel, 'fx', None) or {}).get('rates')
        value = convert_usd(usd, currency, rates or {}) if currency != 'USD' else usd
        if value is None:
            value, currency = usd, 'USD'
        return '≈ ' + format_cost(value, currency)

    def _cost_text(self, usd, partial):
        """Known cost, '+' when some responses have no price; N/A when none do."""
        if partial and not usd:
            return 'N/A'
        return self._cost(usd) + ('+' if partial else '')

    def _tokens(self, value):
        return format_tokens(value, self.panel.prefs.get('token_number_format')) if value is not None else '—'

    def render(self):
        self.today_button.setChecked(self.kind == 'today')
        self.week_button.setChecked(self.kind == 'week')
        if self.data is None:
            return
        center = getattr(self.panel, 'notifications', None)
        notices = center.store.list_events(limit=5000) if center is not None else []
        summary = reports.summarize(self.data, notices, self.kind, time.time())
        values = dict(
            tasks=str(sum(p['tasks'] for p in summary['providers'].values())),
            time=duration_text(summary['seconds']) if summary['seconds'] else '—',
            files=str(summary['files']),
            tokens=self._tokens(summary['tokens']),
            cost=self._cost_text(summary['usd'], summary['partial']),
            change='—' if summary['change'] is None else f"{summary['change']:+.0%}")
        for key, value in values.items():
            self.tiles[key][0].setText(value)
        self.tiles['cost'][0].setToolTip(self.tr('report_cost_partial') if summary['partial'] else
                                         self.tr('report_cost_note'))
        lines = []
        for provider in ('claude', 'codex'):
            info = summary['providers'].get(provider)
            if info:
                lines.append(self.tr('report_provider_line', app=PROVIDER_NAMES[provider],
                                     tasks=info['tasks'], tokens=self._tokens(info['tokens']),
                                     cost=self._cost_text(info['usd'], info['partial'])))
        if summary['finished'] or summary['failed']:
            lines.append(self.tr('report_outcomes', finished=summary['finished'], failed=summary['failed']))
        if summary['projects']:
            lines.append(self.tr('report_projects', projects=', '.join(p['name'] for p in summary['projects'])))
        if summary['missing']:
            lines.append(self.tr('report_missing', apps=', '.join(PROVIDER_NAMES.get(m, m)
                                                                 for m in summary['missing'])))
        if not summary['providers'] and not summary['finished']:
            lines.append(self.tr('report_empty'))
        self.breakdown.setText('\n'.join(lines))
        self.status.setText(self.tr('report_updated', time=time.strftime('%H:%M', time.localtime(self.loaded_at))))
        self.render_history()

    def render_history(self):
        self.history.clear()
        if self.data is None:
            return
        days = self.range.currentData()
        since = None if days is None else time.time() - days * 86400
        rows = reports.search(self.data.get('history'), self.query.text(), self.provider.currentData(), since)
        for row in rows[:500]:
            when = row.get('finished_at') or row.get('started_at')
            item = QTreeWidgetItem([
                time.strftime('%m-%d %H:%M', time.localtime(when)) if when else '—',
                PROVIDER_NAMES.get(row['provider'], row['provider']),
                row.get('title') or self.tr('task_unnamed'), row.get('project') or '—',
                self._tokens(row.get('tokens')),
                self._cost(row['usd']) if row.get('usd') is not None else 'N/A'])
            item.setData(0, Qt.UserRole, row)
            item.setToolTip(2, row.get('title') or '')
            self.history.addTopLevelItem(item)

    def _open_row(self, item):
        row = item.data(0, Qt.UserRole) or {}
        key = f"claude:{row['id']}" if row.get('provider') == 'claude' else row.get('id')
        if key and getattr(self.panel, 'live', False):
            self.panel.focus_task((row['provider'], key))
