"""Expanded analytics. Every primary value is exact or explicitly unavailable."""
import json
from datetime import date, datetime, timedelta

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QDialog, QHeaderView,
    QLabel, QPlainTextEdit, QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from localization import scope_text, text
import theme
from token_format import format_ratio, format_tokens

# OpenCode raw categories in display order: (token key, header key).
OPENCODE_COLUMNS = (
    ('input', 'header_input_tokens'),
    ('output', 'header_output_tokens'),
    ('reasoning', 'header_reasoning_tokens'),
    ('cache_read', 'header_cached_tokens'),
    ('cache_write', 'header_write_tokens'),
)
_OPENCODE_COVERAGE_KEYS = (
    'coverage_complete', 'coverage_partial', 'coverage_unknown',
    'coverage_unavailable')


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
        if (data.get('provider_id') or 'codex') != 'codex':
            return
        self.snapshot = data
        analysis = data.get('analytics')
        if data.get('status') or not analysis or not data.get('available'):
            self.heading.setText(self.tr_text('analytics_heading_provider', provider='Codex', scope=scope_text(
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
        # The OpenCode view uses fewer columns; restore the Codex layout
        # explicitly so provider switches never leak column counts.
        token_headers = [t('header_input_tokens'), t('header_cached_tokens'), t('header_uncached_tokens'),
                         t('header_write_tokens'), t('header_output_tokens'), t('header_reasoning_tokens'),
                         t('header_nonreasoning_tokens'), t('header_total_tokens')]
        self.models.setColumnCount(9)
        set_headers(self.models, [t('header_model')] + token_headers)
        self.sessions.setColumnCount(9)
        set_headers(self.sessions, [t('header_conversation')] + token_headers)
        self.ranges.setColumnCount(6)
        set_headers(self.ranges, [t('header_range'), t('header_total_tokens'), t('header_input_tokens'),
                                  t('header_cached_tokens'), t('header_output_tokens'), t('header_reasoning_tokens')])
        self.days.setColumnCount(7)
        set_headers(self.days, [t('header_date_local'), t('header_total_tokens'), t('header_input_tokens'),
                                t('header_cached_tokens'), t('header_write_tokens'), t('header_output_tokens'),
                                t('header_reasoning_tokens')])
        scope_name = scope_text(data.get('scope'), self.language, recorded=data.get('scope') == 'global')
        title = t(data.get('title')) if data.get('title') in ('display_local_history', 'display_untitled') else data.get('title', '')
        project = t(data.get('project')) if data.get('project') in ('display_all_usage', 'project_unavailable') else data.get('project', '')
        self.heading.setText(t('analytics_heading_provider', provider='Codex', scope=scope_name))
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

    # -- OpenCode provider-local analytics (Slice 6) --------------------

    def _opencode_coverage(self, coverage):
        key = f'coverage_{coverage}'
        return self.tr_text(key if key in _OPENCODE_COVERAGE_KEYS else 'coverage_unknown')

    def _opencode_cell(self, value, token_style):
        return format_tokens(value, token_style)

    def _opencode_merge(self, pairs):
        """Merge (value, coverage-word) pairs without inventing data:
        unknown when nothing is known, complete only when everything is
        known and complete, otherwise partial."""
        known = [value for value, _ in pairs if value is not None]
        if not known:
            return None, self.tr_text('coverage_unknown')
        if len(known) == len(pairs) and all(
                word == self.tr_text('coverage_complete') for _, word in pairs):
            return sum(known), self.tr_text('coverage_complete')
        return sum(known), self.tr_text('coverage_partial')

    def _opencode_cost_text(self, cost):
        amount = (cost or {}).get('amount')
        if amount is None or isinstance(amount, bool):
            return 'N/A'
        if amount == 0:
            return '0'
        return f'{amount:,.4f}'

    def _opencode_cost_value(self, amount):
        if amount is None or isinstance(amount, bool):
            return 'N/A'
        if amount == 0:
            return '0'
        return f'{amount:,.4f}'

    def _opencode_cost_merge(self, amounts):
        """Aggregate recorded session costs: sum known amounts only, with
        coverage complete when every session reported one, partial when
        known and unknown mix, unknown when none did. Token coverage is
        tracked independently and never consulted here."""
        known = [amount for amount in amounts
                 if amount is not None and not isinstance(amount, bool)]
        if not known:
            return None, self.tr_text('coverage_unknown')
        if len(known) == len(amounts):
            return sum(known), self.tr_text('coverage_complete')
        return sum(known), self.tr_text('coverage_partial')

    def _opencode_word_summary(self, words):
        """Summarize per-category coverage words without hiding them:
        the summary never replaces the per-cell coverage behind it."""
        complete_word = self.tr_text('coverage_complete')
        unknown_word = self.tr_text('coverage_unknown')
        if all(word == unknown_word for word in words):
            return unknown_word
        if all(word == complete_word for word in words):
            return complete_word
        return self.tr_text('coverage_partial')

    def _opencode_history_cell(self, value, word, token_style):
        """One history value with independently inspectable coverage:
        complete values render normally with a coverage tooltip, partial
        values carry a visible partial marker plus tooltip, unknown
        values stay N/A, real zeros stay zero."""
        complete_word = self.tr_text('coverage_complete')
        if value is None:
            return 'N/A', word
        text = format_tokens(value, token_style)
        if word == complete_word:
            return (text, word)
        return f'{text} · {word}', word

    def update_opencode(self, data):
        """Historical isolated-test renderer; never reached by update_data.

        Render one OpenCode scoped snapshot: raw categories, the
        recorded Total for verified versions (N/A otherwise), no
        derived ratios, recorded cost with unknown currency.
        Every value comes from this provider-tagged snapshot; switching
        provider/scope replaces the whole view atomically."""
        t = self.tr_text
        token_style = self.parentWidget().prefs.get('token_number_format')
        scope_name = scope_text(data.get('scope'), self.language,
                                recorded=data.get('scope') == 'global')
        heading = t('analytics_heading_provider', provider='OpenCode',
                    scope=scope_name)
        self.heading.setText(heading)
        columns = [t(header) for _, header in OPENCODE_COLUMNS]
        history_columns = columns + [t('header_total_tokens'), t('header_type_coverage')]
        self.models.setColumnCount(9)
        set_headers(self.models, [t('header_model')] + history_columns + [t('metric_recorded_cost')])
        self.sessions.setColumnCount(9)
        set_headers(self.sessions, [t('header_conversation')] + history_columns + [t('metric_recorded_cost')])
        self.ranges.setColumnCount(8)
        set_headers(self.ranges, [t('header_range')] + history_columns)
        self.days.setColumnCount(8)
        set_headers(self.days, [t('header_date_local')] + history_columns)
        selection = data.get('selection') or {}
        if data.get('presentation') == 'active_session':
            # The live session is panel-visible, but the requested scope
            # genuinely holds no data: keep the independent scope view
            # honest instead of relabeling live values as scope data.
            scope_status = data.get('scope_status') or 'no_reliable_record'
            self.subtitle.setText(t(scope_status))
            for widget in (self.metrics, self.models, self.sessions, self.ranges, self.days):
                widget.setRowCount(0)
            self.raw.setPlainText(json.dumps(
                self._opencode_raw(data), ensure_ascii=False, indent=2))
            self.history_note.setText(t(scope_status))
            self.note.setText(t('analytics_opencode_note'))
            return
        if data.get('status') or not data.get('available'):
            self.subtitle.setText(t(data.get('status') or 'no_reliable_record'))
            for widget in (self.metrics, self.models, self.sessions, self.ranges, self.days):
                widget.setRowCount(0)
            self.raw.setPlainText(json.dumps(
                self._opencode_raw(data), ensure_ascii=False, indent=2))
            self.history_note.setText(t(data.get('status') or 'no_reliable_record'))
            self.note.setText(t('analytics_opencode_note'))
            return
        title = t(data.get('title')) if data.get('title') in ('display_local_history', 'display_untitled') else data.get('title', '')
        project = t(data.get('project')) if data.get('project') in ('display_all_usage', 'project_unavailable') else data.get('project', '')
        breakdown = data.get('breakdown_sessions') or []
        if selection.get('live'):
            freshness = t('working')
        elif selection.get('stale'):
            freshness = t('status_stale')
        elif selection.get('activity_unknown'):
            freshness = t('unknown')
        else:
            freshness = t('idle')
        self.subtitle.setText(t('analytics_subtitle_opencode', title=title, project=project,
                                count=len(breakdown), freshness=freshness))
        tokens = data.get('tokens') or {}
        coverage = data.get('token_coverage') or {}
        rows = []
        for key, header_key in OPENCODE_COLUMNS:
            word = self._opencode_coverage(coverage.get(key))
            rows.append((f"{t('group_opencode_raw')} · {t(header_key)}",
                         (self._opencode_cell(tokens.get(key), token_style),
                          '' if word == t('coverage_complete') else t('help_partial_coverage')),
                         word))
        rows.append((f"{t('group_opencode_raw')} · {t('metric_total')}",
                     (self._opencode_cell(tokens.get('total'), token_style),
                      t('help_opencode_total')),
                     self._opencode_coverage(coverage.get('total'))))
        cost = data.get('cost') or {}
        cost_tip = (f"{cost.get('recorded_sessions', 0)}/{cost.get('total_sessions', 0)} "
                    f"{t('records')}\n{t('help_recorded_cost')}\n{t('help_unknown_currency')}")
        rows.append((f"{t('group_opencode_raw')} · {t('metric_recorded_cost')}",
                     (self._opencode_cost_text(cost), cost_tip),
                     self._opencode_coverage(
                         {'recorded': 'complete', 'partial': 'partial'}.get(cost.get('coverage'), 'unknown'))))
        populate(self.metrics, rows)
        by_model = {}
        for row in breakdown:
            by_model.setdefault(row.get('model'), []).append(row)
        complete_word = t('coverage_complete')
        unknown_word = t('coverage_unknown')
        models = []
        for model_id in sorted(by_model, key=lambda name: (name is None, name)):
            name = t('unknown_model') if model_id is None else model_id
            cells = []
            for key, _ in OPENCODE_COLUMNS:
                value, word = self._opencode_merge(
                    [(row['tokens'].get(key),
                      complete_word if row['tokens'].get(key) is not None else unknown_word)
                     for row in by_model[model_id]])
                cells.append((self._opencode_cell(value, token_style),
                              '' if word == complete_word else word))
            _, summary = self._opencode_merge(
                [(row['tokens'].get(key),
                  complete_word if row['tokens'].get(key) is not None else unknown_word)
                 for row in by_model[model_id] for key, _ in OPENCODE_COLUMNS])
            cost_value, cost_word = self._opencode_cost_merge(
                [row.get('cost_amount') for row in by_model[model_id]])
            # Recorded model total: the adapter's per-session recorded
            # totals summed only when every session in the group has
            # one; otherwise N/A (never a partial sum, never borrowed).
            row_totals = [row.get('total') for row in by_model[model_id]]
            if all(value is not None for value in row_totals):
                total_text = self._opencode_cell(sum(row_totals),
                                                 token_style)
            else:
                total_text = 'N/A'
            models.append([(name, name if model_id is None else model_id)] + cells + [
                (total_text, t('help_opencode_total')), summary,
                (self._opencode_cost_value(cost_value),
                 '' if cost_word == complete_word else cost_word)])
        populate(self.models, models)
        sessions = []
        for row in sorted(breakdown, key=lambda entry: entry.get('session_id') or ''):
            cells = []
            for key, _ in OPENCODE_COLUMNS:
                value = row['tokens'].get(key)
                cells.append((self._opencode_cell(value, token_style),
                              '' if value is not None else unknown_word))
            _, summary = self._opencode_merge(
                [(row['tokens'].get(key),
                  complete_word if row['tokens'].get(key) is not None else unknown_word)
                 for key, _ in OPENCODE_COLUMNS])
            cost_value, cost_word = self._opencode_cost_merge([row.get('cost_amount')])
            total_value = row.get('total')
            sessions.append([(row['session_id'], row['session_id'])] + cells + [
                (self._opencode_cell(total_value, token_style),
                 t('help_opencode_total')), summary,
                (self._opencode_cost_value(cost_value),
                 '' if cost_word == complete_word else cost_word)])
        populate(self.sessions, sessions)
        self._opencode_history(data, token_style)
        self.raw.setPlainText(json.dumps(
            self._opencode_raw(data), ensure_ascii=False, indent=2))
        self.note.setText(t('analytics_opencode_note'))

    def _opencode_history(self, data, token_style):
        t = self.tr_text
        history = data.get('history') or {}
        daily = history.get('daily')
        coverage_map = history.get('daily_coverage') or {}
        if not daily:
            self.ranges.setRowCount(0)
            self.days.setRowCount(0)
            self.history_note.setText(t('history_loading') if data.get('available') else t('history_unavailable'))
            return
        tokens = data.get('tokens') or {}
        coverage = data.get('token_coverage') or {}
        lifetime = []
        lifetime_words = []
        for key, _ in OPENCODE_COLUMNS:
            word = self._opencode_coverage(coverage.get(key))
            lifetime_words.append(word)
            lifetime.append(self._opencode_history_cell(tokens.get(key), word, token_style))
        # Lifetime aggregates the scope's own session rollups, so its
        # Total is the recorded sum when available; day/range rows stay
        # N/A because they aggregate upstream message deltas, never
        # stored rollups.
        lifetime.append(self._opencode_history_cell(
            tokens.get('total'),
            self._opencode_coverage(coverage.get('total')), token_style))
        lifetime.append(self._opencode_word_summary(lifetime_words))
        ranges = [[t('range_lifetime')] + lifetime]
        skipped_total = history.get('skipped_message_rows') or 0
        attributed = sum((daily.get(day) or {}).get('skipped', 0) for day in daily)
        unattributed_skips = max(0, skipped_total - attributed)
        today = date.today()
        windows = [(t('range_today'), {today.isoformat()}),
                   (t('range_last7'), {(today - timedelta(days=offset)).isoformat() for offset in range(7)}),
                   (t('range_last30'), {(today - timedelta(days=offset)).isoformat() for offset in range(30)})]
        for name, days in windows:
            # A day with only skipped records still counts as evidence:
            # otherwise a skipped-only day inside the window would let
            # the range claim complete. Values always sum known numbers
            # only; skipped-only days contribute N/A/unknown.
            contributing = [day for day in days
                            if day in daily and ((daily[day].get('messages', 0) or 0) > 0
                                                 or (daily[day].get('skipped', 0) or 0) > 0)]
            cells = []
            words = []
            for key, _ in OPENCODE_COLUMNS:
                day_coverages = [(coverage_map.get(day) or {}).get(key)
                                 for day in contributing]
                known = [daily[day][key] for day in contributing
                         if daily[day].get(key) is not None]
                value = sum(known) if known else None
                if value is None:
                    word = t('coverage_unknown')
                elif all(word == t('coverage_complete') for word in day_coverages):
                    word = t('coverage_complete')
                else:
                    word = t('coverage_partial')
                if (unattributed_skips and contributing
                        and word == t('coverage_complete')):
                    # Skipped rows that cannot be attributed to a day must
                    # never let a range claim complete.
                    word = t('coverage_partial')
                words.append(word)
                cells.append(self._opencode_history_cell(value, word, token_style))
            cells += ['N/A', self._opencode_word_summary(words)]
            ranges.append([name] + cells)
        populate(self.ranges, ranges)
        days = []
        for day_key in sorted(daily):
            values = daily[day_key]
            day_coverages = coverage_map.get(day_key) or {}
            row = [day_key]
            words = []
            for key, _ in OPENCODE_COLUMNS:
                word = self._opencode_coverage(day_coverages.get(key))
                words.append(word)
                row.append(self._opencode_history_cell(values.get(key), word, token_style))
            row += ['N/A', self._opencode_word_summary(words)]
            days.append(row)
        populate(self.days, days)
        parts = [t('history_loaded')]
        if history.get('as_of'):
            try:
                stamped = datetime.fromtimestamp(history['as_of']).strftime('%Y-%m-%d %H:%M')
            except (OverflowError, OSError, ValueError, TypeError):
                stamped = 'N/A'
            parts.append(t('history_cached_as_of', time=stamped))
        elif history.get('cached'):
            parts.append(t('history_cached_as_of', time='N/A'))
        if history.get('refresh_pending'):
            parts.append(t('history_refresh_pending'))
        if history.get('skipped_message_rows'):
            parts.append(t('history_skipped_rows', count=history['skipped_message_rows']))
        self.history_note.setText(' '.join(parts))

    def _opencode_raw(self, data):
        """Allowlisted metadata only: identities, raw categories plus
        coverage, recorded cost without currency, freshness and history
        markers, generation and notes. Never paths, content, credentials
        or share links."""
        identity = data.get('scope_identity') or {}
        scope_identity = {key: identity.get(key) for key in
                          ('scope_type', 'requested_scope', 'session_id',
                           'project_id', 'project_name')
                          if identity.get(key) is not None}
        detail = data.get('model_detail') or {}
        history = data.get('history') or {}
        selection = data.get('selection') or {}
        cost = data.get('cost') or {}
        return dict(
            source=self.tr_text('raw_source_opencode'),
            provider=data.get('provider_id'), scope=data.get('scope'),
            scope_identity=scope_identity,
            presentation=data.get('presentation'),
            scope_status=data.get('scope_status'),
            title=data.get('title'), project=data.get('project'),
            session_id=data.get('session_id'),
            model=data.get('model'),
            model_detail={key: detail.get(key) for key in
                          ('provider', 'variant', 'agent')},
            tokens=data.get('tokens'), token_coverage=data.get('token_coverage'),
            cost=dict(amount=cost.get('amount'), coverage=cost.get('coverage'),
                      recorded_sessions=cost.get('recorded_sessions'),
                      total_sessions=cost.get('total_sessions')),
            freshness=dict(live=bool(selection.get('live')),
                           stale=bool(selection.get('stale'))),
            history=dict(as_of=history.get('as_of'), cached=bool(history.get('cached')),
                         refresh_pending=bool(history.get('refresh_pending')),
                         skipped_message_rows=history.get('skipped_message_rows', 0),
                         daily_coverage=history.get('daily_coverage')),
            generation=data.get('generation'),
            notes=list(data.get('notes') or ()))
