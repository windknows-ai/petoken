"""Expanded analytics. Every primary value is exact or explicitly unavailable."""
import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QDialog, QHeaderView,
    QLabel, QPlainTextEdit, QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from localization import scope_text, text
import theme
from token_format import format_ratio, format_tokens


def help_text(metric, language):
    return text(f'help_{metric}', language)


def table(headers):
    widget = QTableWidget(0, len(headers))
    widget.setHorizontalHeaderLabels(headers)
    widget.setEditTriggers(QAbstractItemView.NoEditTriggers)
    widget.setSelectionBehavior(QAbstractItemView.SelectRows)
    widget.setAlternatingRowColors(True)
    widget.verticalHeader().hide()
    widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
    widget.horizontalHeader().setStretchLastSection(True)
    widget.setStyleSheet(f'QTableWidget {{background:{theme.TABLE_BG};alternate-background-color:{theme.TABLE_ALT};gridline-color:{theme.GRID};border:0;}} QHeaderView::section {{background:{theme.TABLE_HEADER};color:{theme.INK};padding:8px;border:0;}} QTableWidget::item {{padding:6px;}}')
    return widget


def set_headers(widget, headers):
    for column, header in enumerate(headers):
        item = widget.horizontalHeaderItem(column)
        if item is None:
            item = QTableWidgetItem()
            widget.setHorizontalHeaderItem(column, item)
        item.setText(header)


def populate(widget, rows):
    selected = widget.currentRow()
    scroll = widget.verticalScrollBar().value()
    widget.setRowCount(len(rows))
    for row, values in enumerate(rows):
        for column, value in enumerate(values):
            shown, tip = value if isinstance(value, tuple) else (str(value), '')
            item = widget.item(row, column)
            if item is None:
                item = QTableWidgetItem()
                widget.setItem(row, column, item)
            item.setText(shown)
            item.setToolTip(tip)
    if 0 <= selected < len(rows):
        widget.selectRow(selected)
    widget.verticalScrollBar().setValue(scroll)


class AnalyticsWindow(QDialog):
    def __init__(self, panel):
        super().__init__(panel)
        self.setWindowFlag(Qt.Window, True)
        screen = QApplication.primaryScreen().availableGeometry()
        self.resize(min(1020, screen.width()-40), min(750, screen.height()-40))
        layout = QVBoxLayout(self)
        self.heading = QLabel('TOKEN ANALYTICS')
        self.heading.setStyleSheet(f'font-size:21px;font-weight:600;color:{theme.ICE};')
        layout.addWidget(self.heading)
        self.subtitle = QLabel()
        self.subtitle.setWordWrap(True)
        layout.addWidget(self.subtitle)
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f'QTabWidget::pane {{border:1px solid {theme.TAB_PANE_BORDER};}} QTabBar::tab {{background:{theme.TABLE_ALT};padding:11px 14px;}} QTabBar::tab:selected {{background:{theme.TAB_SELECTED_BG};color:{theme.ICE};}}')
        layout.addWidget(self.tabs)
        self.metrics = table(['', '', ''])
        self.tabs.addTab(self.metrics, '')
        self.models = table(['']*9)
        self.tabs.addTab(self.models, '')
        self.sessions = table(['']*9)
        self.tabs.addTab(self.sessions, '')
        history = QWidget()
        history_layout = QVBoxLayout(history)
        self.history_note = QLabel()
        self.history_note.setWordWrap(True)
        history_layout.addWidget(self.history_note)
        self.ranges = table(['']*6)
        self.ranges.setMaximumHeight(240)
        history_layout.addWidget(self.ranges)
        self.days = table(['']*7)
        history_layout.addWidget(self.days)
        self.tabs.addTab(history, '')
        self.raw = QPlainTextEdit()
        self.raw.setReadOnly(True)
        self.raw.setStyleSheet(f'background:{theme.TABLE_BG};color:#DDE6FC;font-family:Consolas;font-size:12px;')
        self.tabs.addTab(self.raw, '')
        self.note = QLabel()
        self.note.setWordWrap(True)
        layout.addWidget(self.note)
        self.snapshot = {}
        self.apply_language()

    @property
    def language(self):
        return self.parentWidget().prefs.get('language')

    def tr_text(self, key, **values):
        return text(key, self.language, **values)

    def apply_language(self):
        t = self.tr_text
        self.setWindowTitle(t('analytics_title'))
        for index, key in enumerate(('tab_full', 'tab_models', 'tab_conversations', 'tab_history', 'tab_raw')):
            self.tabs.setTabText(index, t(key))
        token_headers = [t('header_input_tokens'), t('header_cached_tokens'), t('header_uncached_tokens'),
                         t('header_write_tokens'), t('header_output_tokens'), t('header_reasoning_tokens'),
                         t('header_nonreasoning_tokens'), t('header_total_tokens')]
        set_headers(self.metrics, [t('header_group_metric'), t('header_exact'), t('header_type_coverage')])
        set_headers(self.models, [t('header_model')] + token_headers)
        set_headers(self.sessions, [t('header_conversation')] + token_headers)
        set_headers(self.ranges, [t('header_range'), t('header_total_tokens'), t('header_input_tokens'),
                                  t('header_cached_tokens'), t('header_output_tokens'), t('header_reasoning_tokens')])
        set_headers(self.days, [t('header_date_local'), t('header_total_tokens'), t('header_input_tokens'),
                                t('header_cached_tokens'), t('header_write_tokens'), t('header_output_tokens'),
                                t('header_reasoning_tokens')])
        self.history_note.setText(t('history_initial'))
        self.note.setText(t('analytics_na_note'))
        if self.snapshot:
            self.update_data(self.snapshot)

    def update_data(self, data):
        self.snapshot = data
        analysis = data.get('analytics')
        if data.get('status') or not analysis or not data.get('available'):
            self.heading.setText(self.tr_text('analytics_heading', scope=scope_text(
                data.get('scope', self.parentWidget().prefs.get('scope')), self.language)))
            self.subtitle.setText(self.tr_text(data.get('status') or 'no_reliable_record'))
            for widget in (self.metrics, self.models, self.sessions, self.ranges, self.days):
                widget.setRowCount(0)
            self.raw.clear()
            self.history_note.setText(self.tr_text('no_reliable_record'))
            self.note.setText(self.tr_text('analytics_na_note'))
            return
        t = self.tr_text
        token_style = self.parentWidget().prefs.get('token_number_format')
        scope_name = scope_text(data.get('scope'), self.language, recorded=data.get('scope') == 'global')
        title = t(data.get('title')) if data.get('title') in ('display_local_history', 'display_untitled') else data.get('title', '')
        project = t(data.get('project')) if data.get('project') in ('display_all_usage', 'project_unavailable') else data.get('project', '')
        self.heading.setText(t('analytics_heading', scope=scope_name))
        self.subtitle.setText(t('analytics_subtitle', title=title, project=project, events=analysis['events']))
        fields = [
            ('group_official', 'total_tokens', 'metric_total'), ('group_official', 'input_tokens', 'metric_input'),
            ('group_official', 'cached_input_tokens', 'metric_cached'), ('group_official', 'uncached_input_tokens', 'metric_uncached'),
            ('group_official', 'output_tokens', 'metric_output'), ('group_official', 'reasoning_output_tokens', 'metric_reasoning'),
            ('group_official', 'non_reasoning_output_tokens', 'metric_nonreasoning'), ('group_cache', 'cache_write_input_tokens', 'metric_cache_write'),
            ('group_cache', 'cache_hit_ratio', 'metric_cache_hit'), ('group_derived', 'new_work', 'metric_new_work'),
            ('group_derived', 'output_ratio', 'metric_output_ratio'), ('group_derived', 'reasoning_ratio', 'metric_reasoning_ratio'),
            ('group_comparison', 'comparison_uncached', 'metric_comparison_uncached'),
            ('group_comparison', 'cached_input_tokens', 'metric_cache_read_component'),
            ('group_comparison', 'cache_write_input_tokens', 'metric_cache_write_component'),
            ('group_comparison', 'output_tokens', 'metric_output_component'),
            ('group_comparison', 'claude_raw', 'metric_claude_raw'),
            ('group_comparison', 'known_processed', 'metric_known_processed')]
        rows = []
        for group_key, key, caption_key in fields:
            raw = key in analysis['tokens']
            value = (analysis['tokens'] if raw else analysis['derived']).get(key)
            coverage = f"{t('raw')} · {analysis['coverage'][key]}/{analysis['events']} {t('records')}" if raw else t('derived')
            if raw and value is None and analysis['coverage'][key]:
                coverage += ' · ' + t('known_subtotal', value=format_tokens(analysis['known'][key], token_style))
            if key == 'total_tokens':
                coverage = t('total_source_coverage')
            shown = format_ratio(value) if key.endswith('ratio') else format_tokens(value, token_style)
            rows.append((f"{t(group_key)} · {t(caption_key)}", (shown, help_text(key, self.language)), coverage))
        populate(self.metrics, rows)

        def values(row, keys):
            return [format_tokens(row['tokens'].get(key, row['derived'].get(key)), token_style) for key in keys]

        models = []
        for row in analysis['models']:
            name = t('unknown_model') if row['name'] == 'unknown_model' else row['name']
            models.append([name] + values(row, ['input_tokens', 'cached_input_tokens', 'uncached_input_tokens',
                'cache_write_input_tokens', 'output_tokens', 'reasoning_output_tokens', 'non_reasoning_output_tokens', 'total_tokens']))
        populate(self.models, models)
        names = data.get('session_names', {})
        populate(self.sessions, [[(names.get(row['name']) or row['name'], row['name'])] + values(row,
            ['input_tokens', 'cached_input_tokens', 'uncached_input_tokens', 'cache_write_input_tokens',
             'output_tokens', 'reasoning_output_tokens', 'non_reasoning_output_tokens', 'total_tokens']) for row in analysis['sessions']])
        history_data = data.get('history')
        if history_data:
            ranges = [(t('range_current'), data['current_session']), (t('range_lifetime'), history_data),
                (t('range_today'), history_data['ranges']['today']), (t('range_last7'), history_data['ranges']['last7']),
                (t('range_last30'), history_data['ranges']['last30']), (t('range_undated'), history_data['undated'])]
            populate(self.ranges, [[name] + values(row, ['total_tokens', 'input_tokens', 'cached_input_tokens',
                'output_tokens', 'reasoning_output_tokens']) for name, row in ranges])
            populate(self.days, [[row['name']] + values(row, ['total_tokens', 'input_tokens', 'cached_input_tokens',
                'cache_write_input_tokens', 'output_tokens', 'reasoning_output_tokens']) for row in history_data['daily']])
            self.history_note.setText(t('history_loaded') + (t('history_partial') if history_data.get('partial') else ''))
        else:
            self.ranges.setRowCount(0)
            self.days.setRowCount(0)
            self.history_note.setText(t('history_loading'))
        localized_notes = [t(note) for note in data.get('notes', [])]
        raw = json.dumps(dict(source='Codex JSONL event_msg/token_count/info (current session latest record)',
            total_token_usage=data.get('raw_total'), last_token_usage=data.get('raw_last'),
            model_context_window=data.get('context_window'), timestamp=data.get('sample'),
            model_metadata=data.get('model'), reasoning_effort=data.get('effort'), service_tier=data.get('tier'),
            field_notes=t('raw_field_notes'), notes=localized_notes), ensure_ascii=False, indent=2)
        if self.raw.toPlainText() != raw:
            position = self.raw.verticalScrollBar().value()
            self.raw.setPlainText(raw)
            self.raw.verticalScrollBar().setValue(position)
        self.note.setText('N/A · ' + (' | '.join(localized_notes) or t('analytics_default_note')))
