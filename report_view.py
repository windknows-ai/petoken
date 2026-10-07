"""Workbench "Reports" page (V1.6 D): today / this week, and task history.

The numbers come from the panel's shared ``reports.ReportCache``: warmed in
the background after Petoken starts, so the page shows the last result at
once and refreshes it in a worker when it is older than RELOAD_S (Codex
history can take seconds). Double-clicking a history row jumps to that
task's window when it is still open.
"""
from __future__ import annotations

import time

from datetime import datetime

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (QComboBox, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                               QPushButton, QScrollArea, QStackedWidget, QTreeWidget, QTreeWidgetItem,
                               QVBoxLayout, QWidget)

import reports
import theme
from localization import text
from pricing import convert_usd, format_cost
from providers import PROVIDER_NAMES
from token_format import format_tokens

RELOAD_S = 300
RANGES = (('week', 7), ('month', 30), ('all', None))
# Data board periods: today, yesterday, this week, then whole past weeks.
PERIODS = ('today', 'yesterday', 'week') + tuple(f'week-{n}' for n in range(1, 8))


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
        shared = getattr(panel, 'report_cache', None)
        self.cache = (reports.ReportCache(loader, RELOAD_S) if loader is not None or shared is None
                      else shared)
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
        # Two sub-pages: the data board (numbers for one period) and the
        # analysis (how it changed over days or weeks).
        switch = QHBoxLayout()
        self.board_button, self.analysis_button = QPushButton(), QPushButton()
        for index, button in enumerate((self.board_button, self.analysis_button)):
            button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(lambda _=False, i=index: self.show_sub(i))
            switch.addWidget(button)
        switch.addStretch()
        layout.addLayout(switch)
        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)
        board = QWidget()
        self.stack.addWidget(board)
        layout = QVBoxLayout(board)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        top = QHBoxLayout()
        self.period_box = QComboBox()
        for kind in PERIODS:
            self.period_box.addItem('', kind)
        self.period_box.currentIndexChanged.connect(lambda _: self.set_kind(self.period_box.currentData()))
        top.addWidget(self.period_box)
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
        # No dark focus frame around the clicked cell (as in the other lists).
        self.setStyleSheet('QPushButton:checked { background:%s; border-color:%s; font-weight:600; }'
                           ' QTreeWidget { outline: 0px; }'
                           % (theme.TAB_SELECTED_BG, theme.SELECT_BAR))
        layout.addWidget(self.history, 1)
        self.analysis = AnalysisView(self)
        self.stack.addWidget(self.analysis)
        self.show_sub(0)
        self.apply_language()

    @property
    def language(self):
        return self.panel.prefs.get('language')

    def tr(self, key, **values):
        return text(key, self.language, **values)

    def apply_language(self):
        self.intro.setText(self.tr('report_intro'))
        self.board_button.setText(self.tr('report_board'))
        self.analysis_button.setText(self.tr('report_analysis'))
        for index, kind in enumerate(PERIODS):
            self.period_box.setItemText(index, self.period_text(kind))
        self.analysis.apply_language()
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
        """Show what the cache has now; reload in the background when stale."""
        if self.cache.data is not None and self.data is not self.cache.data:
            self.data, self.loaded_at = self.cache.data, self.cache.at
            self.render()
        if self.loading or not (force or self.cache.stale()):
            return
        self.loading = True
        self.status.setText(self.tr('report_updating' if self.data is not None else 'report_loading'))
        self.reload_button.setEnabled(False)
        self.cache.refresh(self._signals.loaded.emit)

    def _loaded(self, data):
        self.loading = False
        self.data, self.loaded_at = data, self.cache.at
        self.reload_button.setEnabled(True)
        self.render()

    def period_text(self, kind):
        if kind in ('today', 'yesterday', 'week'):
            return self.tr({'today': 'report_today', 'yesterday': 'report_yesterday', 'week': 'report_week'}[kind])
        start, end, _ = reports.period(kind, time.time())
        first, last = datetime.fromtimestamp(start), datetime.fromtimestamp(end - 1)
        span = f'{first.month}/{first.day}–{last.month}/{last.day}'
        return self.tr('report_last_week' if kind == 'week-1' else 'report_weeks_ago',
                       n=int(kind.split('-')[1]), span=span)

    def show_sub(self, index):
        self.stack.setCurrentIndex(index)
        self.board_button.setChecked(index == 0)
        self.analysis_button.setChecked(index == 1)
        if index == 1:
            self.analysis.render()

    def set_kind(self, kind):
        if kind is None:
            return
        if self.period_box.currentData() != kind:
            self.period_box.setCurrentIndex(max(0, self.period_box.findData(kind)))
        if kind.startswith('week'):
            companion = getattr(self.panel, 'companion', None)
            if companion is not None:
                companion.earn('first_weekly')
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
        if self.data is None:
            return
        if self.stack.currentIndex() == 1:
            self.analysis.render()
        center = getattr(self.panel, 'notifications', None)
        notices = center.store.list_events(limit=5000) if center is not None else []
        summary = reports.summarize(self.data, notices, self.kind, time.time())
        values = dict(
            tasks=str(sum(p['tasks'] for p in summary['providers'].values())),
            time=duration_text(summary['seconds']) if summary['seconds'] else '—',
            files=str(summary['files']),
            tokens=self._tokens(summary['tokens']),
            cost=self._cost_text(summary['usd'], summary['partial']),
            change='—' if summary['change'] is None else
            ('0%' if abs(summary['change']) < .005 else f"{summary['change']:+.0%}"))
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
        if summary.get('focus_count'):
            lines.append(self.tr('report_focus', count=summary['focus_count'],
                                 time=duration_text(summary['focus_seconds'])))
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


class AnalysisView(QWidget):
    """Reports > Analysis: tokens, cost, AI time and tasks as line charts."""

    def __init__(self, page):
        super().__init__()
        from report_charts import RANGES as CHART_RANGES, LineChart
        self.page = page
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        top = QHBoxLayout()
        self.range = QComboBox()
        from report_charts import DEFAULT_RANGE
        for key in CHART_RANGES:
            self.range.addItem('', key)
        self.range.setCurrentIndex(self.range.findData(DEFAULT_RANGE))
        self.range.currentIndexChanged.connect(lambda _: self.render())
        top.addWidget(self.range)
        top.addStretch()
        self.note = QLabel()
        self.note.setObjectName('muted')
        top.addWidget(self.note)
        layout.addLayout(top)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        body = QWidget()
        body.setObjectName('charts')
        body.setStyleSheet('QWidget#charts { background:transparent; }')
        column = QVBoxLayout(body)
        column.setContentsMargins(0, 0, 6, 0)
        column.setSpacing(12)
        self.charts = {}
        for key in ('tokens', 'usd', 'hours', 'tasks'):
            chart = LineChart()
            self.charts[key] = chart
            column.addWidget(chart)
        column.addStretch()
        scroll.setWidget(body)
        scroll.setStyleSheet('QScrollArea { background:transparent; border:0; }')
        scroll.viewport().setAutoFillBackground(False)
        layout.addWidget(scroll, 1)

    def tr(self, key, **values):
        return self.page.tr(key, **values)

    def apply_language(self):
        from report_charts import RANGES as CHART_RANGES
        for index, key in enumerate(CHART_RANGES):
            self.range.setItemText(index, self.tr(f'report_chart_range_{key}'))
        self.render()

    def render(self):
        from report_charts import COLORS, series
        page = self.page
        if page.data is None:
            self.note.setText(self.tr('report_loading'))
            return
        self.note.setText(self.tr('report_chart_note'))
        kind = self.range.currentData()
        data = series(page.data, kind, time.time())
        names = {p: PROVIDER_NAMES[p] for p in ('claude', 'codex')}

        def per_app(values):
            return [(names[p], COLORS[p], values[p]) for p in ('claude', 'codex')]

        def tokens(value, axis=False):
            return format_tokens(round(value), 'compact').replace(' Tokens', '') if axis else page._tokens(round(value))

        # Costs are drawn in your currency, so the axis gets round numbers.
        currency = getattr(page.panel, 'currency', 'USD')
        rates = (getattr(page.panel, 'fx', None) or {}).get('rates') or {}
        rate = (convert_usd(1.0, currency, rates) if currency != 'USD' else 1.0) or 1.0
        shown = currency if rate != 1.0 or currency == 'USD' else 'USD'

        def cost(value, axis=False):
            text_ = format_cost(value, shown)
            return text_ if axis else '≈ ' + text_

        def hours(value, axis=False):
            return f'{value:.0f}h' if axis else duration_text(value * 3600)

        def count(value, axis=False):
            return f'{value:.0f}'

        total_tokens = sum(sum(v) for v in data['tokens'].values())
        total_usd = sum(sum(v) for v in data['usd'].values())
        total_hours = sum(data['hours'])
        total_tasks = sum(sum(v) for v in data['tasks'].values())
        self.charts['tokens'].set_data(self.tr('report_chart_tokens'), page._tokens(total_tokens),
                                       data['labels'], per_app(data['tokens']), tokens)
        local = {p: [v * rate for v in data['usd'][p]] for p in data['usd']}
        self.charts['usd'].set_data(self.tr('report_chart_cost'), page._cost(total_usd),
                                    data['labels'], per_app(local), cost)
        self.charts['hours'].set_data(self.tr('report_chart_hours'), duration_text(total_hours * 3600),
                                      data['labels'], [(self.tr('report_chart_all_apps'), COLORS['total'],
                                                        data['hours'])], hours)
        self.charts['tasks'].set_data(self.tr('report_chart_tasks'), str(total_tasks),
                                      data['labels'], per_app(data['tasks']), count)
