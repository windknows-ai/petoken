"""V1.2 Slice 6: provider-local analytics and cost provenance.

Traverses the real provider result -> poller/render -> analytics window
path. Codex behavior is parity-checked; OpenCode shows verified raw
categories only, with honest N/A, coverage, recorded cost and history.
"""
import json
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from provider_poller import ProviderPoller
from providers import CodexProvider
from opencode_provider import OpenCodeProvider
from tests.test_opencode_provider import (BASE_MS, make_message, make_part,
                                          make_session, write_store)
from tests.test_providers import write_home
from usage import CodexStore

NOW_S = BASE_MS / 1000 + 100


def _sync(poller, prefs=None, **kw):
    poller.poll(prefs, **kw)
    assert poller.drain(timeout=10), 'reads did not finish'
    poller.poll(prefs, **kw)
    assert poller.drain(timeout=10), 'reads did not finish'
    return poller.poll(prefs, **kw)


class AnalyticsFixture:
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from widget import Panel
        from pet import DesktopPet
        self.temp = tempfile.TemporaryDirectory()
        self.pref_patch = patch('widget.PREF_DIR', Path(self.temp.name))
        self.pref_patch.start()
        self.panel = Panel(live=False)
        self.panel.pet = DesktopPet(self.panel)
        self.panel.pet.activity_timer.stop()
        self.panel.prefs['language'] = 'en'
        self.panel.apply_language()
        self.work = Path(self.temp.name) / 'stores'
        self.work.mkdir()

    def tearDown(self):
        try:
            self.panel.provider_poller.drain(timeout=10)
        except Exception:
            pass
        self.panel.provider_poller.close()
        self.panel.pet.close()
        self.panel.tray.hide()
        if self.panel.analytics_window:
            self.panel.analytics_window.close()
        self.panel.closing = True
        self.panel.close()
        self.panel.deleteLater()
        self.app.processEvents()
        self.pref_patch.stop()
        self.temp.cleanup()

    def _home(self, name, threads):
        home = self.work / name
        home.mkdir(exist_ok=True)
        write_home(str(home), threads)
        return CodexStore(home)

    def _db(self, name, sessions, messages=(), parts=()):
        path = self.work / name
        write_store(path, sessions, messages, parts)
        return path

    def _attach(self, threads, sessions, messages=(), parts=()):
        self.panel.provider_poller.drain(timeout=10)
        self.panel.provider_poller.close()
        tag = len(list(self.work.iterdir()))
        home = self._home(f'codex-{tag}', threads)
        db = self._db(f'open-{tag}.db', sessions, messages, parts)
        self.panel.provider_poller = ProviderPoller(home, db)
        return self.panel.provider_poller

    def _poll_render(self, prefs=None, now=None, history=False, **kw):
        prefs = dict({'scope': 'global'}, **(prefs or {}))
        poller = self.panel.provider_poller
        poller.poll(prefs, now=now, want_history=history, **kw)
        self.assertTrue(poller.drain(), 'reads did not finish')
        poller.poll(prefs, now=now, want_history=history, **kw)
        self.assertTrue(poller.drain(), 'reads did not finish')
        out = poller.poll(prefs, now=now, want_history=history, **kw)
        self.panel.render(out['result'])
        self.app.processEvents()
        return out

    def _open_window(self):
        self.panel.open_analytics()
        self.app.processEvents()
        return self.panel.analytics_window

    def _cell(self, table, row, column):
        item = table.item(row, column)
        self.assertIsNotNone(item, f'empty cell {(row, column)}')
        return item.text()

    def _assert_shot(self, window, path):
        """Screenshot existence without compression-size assumptions: the
        save must succeed and the file must load as a non-null image
        whose dimensions match the captured pixmap."""
        from PySide6.QtGui import QImage
        pixmap = window.grab()
        self.assertTrue(pixmap.save(path, 'PNG'), path)
        image = QImage(path)
        self.assertFalse(image.isNull(), path)
        self.assertGreater(image.width(), 0, path)
        self.assertGreater(image.height(), 0, path)
        self.assertEqual((image.width(), image.height()),
                         (pixmap.width(), pixmap.height()), path)

    def _column(self, table, column):
        return [self._cell(table, row, column)
                for row in range(table.rowCount())]


class CodexAnalyticsParityTests(AnalyticsFixture, unittest.TestCase):
    def test_codex_metrics_formulas_unchanged(self):
        self._attach([{'id': 't1', 'working': True}],
                     [make_session('ses_1')])
        self._poll_render(active_title='t1', detection_valid=True,
                          history=True)
        window = self._open_window()
        first_column = self._column(window.metrics, 0)
        values = self._column(window.metrics, 1)
        body = dict(zip(first_column, values))
        self.assertEqual(body['Official OpenAI Usage · Total Tokens'], '110 Tokens')
        self.assertEqual(body['Official OpenAI Usage · Input Tokens'], '90 Tokens')
        self.assertEqual(body['Official OpenAI Usage · Uncached Input'], '10 Tokens')
        self.assertIn('Codex', window.heading.text())

    def test_codex_model_session_history_views_intact(self):
        self._attach([{'id': 't1', 'working': True}],
                     [make_session('ses_1')])
        self._poll_render(active_title='t1', detection_valid=True,
                          history=True)
        window = self._open_window()
        self.assertIn('gpt-6-astra', self._column(window.models, 0))
        self.assertTrue(window.sessions.rowCount() >= 1)
        self.assertIn('N/A', window.note.text())


class OpenCodeRawAnalyticsTests(AnalyticsFixture, unittest.TestCase):
    def _live_opencode(self, sessions, messages, parts, prefs):
        poller = self._attach([{'id': 't1'}], sessions, messages, parts)
        out = self._poll_render(prefs, now=NOW_S, history=True)
        self.assertEqual(out['provider_id'], 'opencode')
        return poller, self._open_window()

    def test_five_raw_categories_no_derived_values(self):
        _, window = self._live_opencode(
            [make_session('ses_1', tokens=(100, 20, 5, 400, 0))],
            [make_message('m1', 'ses_1')],
            [make_part('p1', 'ses_1', created=BASE_MS - 100000)],
            {'scope': 'conversation', 'pinned': 'ses_1',
             'tracking_provider': 'opencode'})
        labels = self._column(window.metrics, 0)
        values = dict(zip(labels, self._column(window.metrics, 1)))
        get = lambda label: values[f'OpenCode raw · {label}']
        self.assertEqual(get('Input Tokens'), '100 Tokens')
        self.assertEqual(get('Output Tokens'), '20 Tokens')
        self.assertEqual(get('Reasoning Tokens'), '5 Tokens')
        self.assertEqual(get('Cached Tokens'), '400 Tokens')
        self.assertEqual(get('Write Tokens'), '0 Tokens')
        self.assertEqual(get('Total Tokens'), 'N/A')
        blob = json.dumps([labels, list(values.values())])
        self.assertNotIn('gpt-6-astra', blob)
        self.assertNotIn('$', blob)

    def test_unknown_partial_zero_coverage(self):
        poller = self._attach(
            [{'id': 't1'}],
            [make_session('ses_a', tokens=(10, 1, 1, 1, 0)),
             make_session('ses_b', tokens=(None, 2, 2, 2, 0))])
        out = self._poll_render({'tracking_provider': 'opencode'},
                                now=NOW_S, history=True)
        window = self._open_window()
        labels = self._column(window.metrics, 0)
        rows = dict(zip(labels, zip(self._column(window.metrics, 1),
                                    self._column(window.metrics, 2))))
        value, coverage = rows['OpenCode raw · Input Tokens']
        self.assertEqual(value, '10 Tokens')
        self.assertIn('partial', coverage)
        for row in range(window.sessions.rowCount()):
            cells = [window.sessions.item(row, column).text()
                     for column in range(window.sessions.columnCount())]
            if cells[0] == 'opencode:ses_b':
                self.assertEqual(cells[1], 'N/A')
        self.assertIn('OpenCode', window.heading.text())

    def test_recorded_zero_cost_displays_zero(self):
        self._attach(
            [{'id': 't1'}],
            [make_session('ses_zero', tokens=(0, 0, 0, 0, 0), cost=0.0,
                          updated=BASE_MS)],
            [make_message('m1', 'ses_zero')],
            [make_part('p1', 'ses_zero', created=BASE_MS - 100000)])
        out = self._poll_render({'scope': 'conversation',
                                 'pinned': 'ses_zero',
                                 'tracking_provider': 'opencode'},
                                now=NOW_S, history=True)
        window = self._open_window()
        labels = self._column(window.metrics, 0)
        values = dict(zip(labels, self._column(window.metrics, 1)))
        self.assertEqual(values['OpenCode raw · Input Tokens'], '0 Tokens')
        cost = values['OpenCode raw · Recorded Cost']
        self.assertIn('0', cost)
        self.assertNotIn('$', self.panel.analytics_window.raw.toPlainText())
        self.assertNotIn('USD', self.panel.analytics_window.raw.toPlainText())

    def test_unknown_cost_and_category_stay_na(self):
        self._attach(
            [{'id': 't1'}],
            [make_session('ses_myst', tokens=(None, None, None, None, None),
                          cost=None, updated=BASE_MS)])
        self._poll_render({'scope': 'conversation', 'pinned': 'ses_myst',
                           'tracking_provider': 'opencode'},
                          now=NOW_S, history=True)
        window = self._open_window()
        values = self._column(window.metrics, 1)
        self.assertTrue(all(value == 'N/A' for value in values[:5]))
        self.assertEqual(values[5], 'N/A')
        self.assertEqual(values[6], 'N/A')


class ProviderScopeIsolationTests(AnalyticsFixture, unittest.TestCase):
    def test_same_raw_id_never_collides(self):
        self._attach(
            [{'id': 'shared', 'working': True, 'name': 'shared'}],
            [make_session('shared', project='proj-x',
                          directory='/synthetic/xray',
                          tokens=(7, 7, 7, 7, 7), updated=BASE_MS)],
            [make_message('m1', 'shared')],
            [make_part('p1', 'shared', created=BASE_MS - 100000)])
        codex = self._poll_render({'tracking_provider': 'codex'},
                                  active_title='shared',
                                  detection_valid=True, now=NOW_S)
        window = self._open_window()
        self.assertIn('gpt-6-astra', self._column(window.models, 0))
        self.panel.prefs['tracking_provider'] = 'opencode'
        self.panel.provider_poller.mark_used('opencode')
        self.panel.provider_poller.bump_generation()
        self._poll_render({'scope': 'conversation', 'pinned': 'shared',
                           'tracking_provider': 'opencode'}, now=NOW_S,
                          history=True)
        window = self._open_window()
        sessions = self._column(window.sessions, 0)
        self.assertIn('opencode:shared', sessions)
        self.assertNotIn('gpt-6-astra', self._column(window.models, 0))
        self.assertNotIn('gpt-6-astra', window.raw.toPlainText())

    def test_switch_replaces_analytics_atomically(self):
        self._attach(
            [{'id': 't1', 'working': True}],
            [make_session('ses_1', updated=BASE_MS)],
            [make_message('m1', 'ses_1')],
            [make_part('p1', 'ses_1', created=BASE_MS - 100000)])
        self._poll_render(active_title='t1', detection_valid=True,
                          history=True)
        window = self._open_window()
        self.assertIn('gpt-6-astra', self._column(window.models, 0))
        self.panel.prefs['tracking_provider'] = 'opencode'
        self.panel.provider_poller.mark_used('opencode')
        self.panel.provider_poller.bump_generation()
        self._poll_render({'scope': 'conversation', 'pinned': 'ses_1',
                           'tracking_provider': 'opencode'}, now=NOW_S,
                          history=True)
        window = self._open_window()
        self.assertIn('OpenCode', window.heading.text())
        self.assertNotIn('gpt-6-astra', self._column(window.models, 0))
        self.assertNotIn('gpt-6-astra', window.raw.toPlainText())

    def test_late_analytics_cannot_restore(self):
        self._attach(
            [{'id': 't1', 'working': True}],
            [make_session('ses_1', updated=BASE_MS)],
            [make_message('m1', 'ses_1')],
            [make_part('p1', 'ses_1', created=BASE_MS - 100000)])
        codex = self._poll_render(active_title='t1', detection_valid=True,
                                  history=True)
        window = self._open_window()
        self.panel.prefs['tracking_provider'] = 'opencode'
        self.panel.provider_poller.mark_used('opencode')
        self.panel.provider_poller.bump_generation()
        newer = self._poll_render(
            {'scope': 'conversation', 'pinned': 'ses_1',
             'tracking_provider': 'opencode'}, now=NOW_S, history=True)
        window = self._open_window()
        self.assertIn('OpenCode', window.heading.text())
        stale = dict(codex['result'])
        stale['generation'] = newer['generation'] - 1
        self.panel.render(stale)
        self.app.processEvents()
        self.assertIn('OpenCode', window.heading.text())
        self.assertNotIn('gpt-6-astra', self._column(window.models, 0))

    def test_unavailable_clears_tables(self):
        from opencode_provider import OpenCodeProvider as OcProvider
        self._attach(
            [{'id': 't1', 'working': True}],
            [make_session('ses_1', updated=BASE_MS)],
            [make_message('m1', 'ses_1')],
            [make_part('p1', 'ses_1', created=BASE_MS - 100000)])
        self._poll_render({'scope': 'conversation', 'pinned': 'ses_1',
                           'tracking_provider': 'opencode'}, now=NOW_S,
                          history=True)
        window = self._open_window()
        self.assertGreater(window.sessions.rowCount(), 0)
        self.panel.provider_poller.opencode.close()
        self.panel.provider_poller.opencode = OcProvider(
            self.work / 'absent.db')
        self._poll_render({'tracking_provider': 'opencode'}, now=NOW_S)
        self.assertEqual(window.sessions.rowCount(), 0)
        self.assertEqual(window.models.rowCount(), 0)
        self.assertIn('OpenCode', window.heading.text())


class BreakdownHistoryCostTests(AnalyticsFixture, unittest.TestCase):
    def test_model_session_sums_keep_coverage(self):
        import json as _json
        first = _json.dumps({'id': 'weird-model-xyz', 'providerID': 'alt',
                             'variant': 'beta'})
        second = _json.dumps({'id': 'weird-model-xyz', 'providerID': 'alt',
                              'variant': 'beta'})
        self._attach(
            [{'id': 't1'}],
            [make_session('ses_a', project='proj-a',
                          directory='/synthetic/alpha', model=first,
                          tokens=(10, 1, 1, 1, 0)),
             make_session('ses_b', project='proj-b',
                          directory='/synthetic/beta', model=second,
                          tokens=(20, 2, 2, 2, 0))])
        self._poll_render({'tracking_provider': 'opencode'}, now=NOW_S,
                          history=True)
        window = self._open_window()
        models = {self._cell(window.models, row, 0): row
                  for row in range(window.models.rowCount())}
        row = models['weird-model-xyz']
        self.assertEqual(self._cell(window.models, row, 1), '30 Tokens')
        self.assertEqual(self._cell(window.models, row, 6), 'N/A')
        sessions = {self._cell(window.sessions, row, 0): row
                    for row in range(window.sessions.rowCount())}
        self.assertEqual(len(sessions), 2)
        self.assertIn('opencode:ses_a', sessions)

    def test_fork_rows_are_not_subtracted(self):
        self._attach(
            [{'id': 't1'}],
            [make_session('parent', project='proj-a',
                          directory='/synthetic/alpha',
                          tokens=(50, 5, 5, 5, 0)),
             make_session('child', project='proj-a', parent='parent',
                          directory='/synthetic/alpha',
                          tokens=(60, 6, 6, 6, 0))])
        self._poll_render({'tracking_provider': 'opencode'}, now=NOW_S,
                          history=True)
        window = self._open_window()
        rows = {self._cell(window.sessions, row, 0): row
                for row in range(window.sessions.rowCount())}
        self.assertEqual(self._cell(window.sessions, rows['opencode:child'], 1),
                         '60 Tokens')
        self.assertEqual(len(rows), 2)

    def test_daily_ranges_and_floor(self):
        now_ms = int(time.time() * 1000)
        old_ms = now_ms - 10 * 86400000
        old_day = datetime.fromtimestamp(old_ms / 1000).date().isoformat()
        deltas = {'input': 11, 'output': 3, 'reasoning': 1,
                  'cache': {'read': 5, 'write': 0}}
        fresh = {'input': 100, 'output': 20, 'reasoning': 2,
                 'cache': {'read': 40, 'write': 1}}
        poller = self._attach(
            [{'id': 't1'}],
            [make_session('ses_old', updated=old_ms),
             make_session('ses_new', updated=now_ms)],
            [make_message('m-old', 'ses_old', created=old_ms, tokens=deltas),
             make_message('m-new', 'ses_new', created=now_ms, tokens=fresh)])
        self._poll_render({'tracking_provider': 'opencode'}, now=NOW_S,
                          history=True)
        window = self._open_window()
        days = {self._cell(window.days, row, 0): row
                for row in range(window.days.rowCount())}
        self.assertIn(old_day, days)
        self.assertEqual(self._cell(window.days, days[old_day], 1), '11 Tokens')
        ranges = {self._cell(window.ranges, row, 0): row
                  for row in range(window.ranges.rowCount())}
        self.assertGreaterEqual(len(ranges), 3)
        raw_history = json.loads(window.raw.toPlainText())['history']
        self.assertIsNotNone(raw_history['as_of'])
        note_before = window.history_note.text()
        self._poll_render({'tracking_provider': 'opencode'}, now=NOW_S,
                          history=True)
        self.assertEqual(window.history_note.text(), note_before)
        scans = poller.opencode.history_scans
        self._poll_render({'tracking_provider': 'opencode'}, now=NOW_S,
                          history=True)
        self.assertEqual(poller.opencode.history_scans, scans)

    def test_skipped_rows_stay_partial(self):
        now_ms = int(time.time() * 1000)
        poller = self._attach(
            [{'id': 't1'}],
            [make_session('ses_1', updated=now_ms)],
            [dict(id='bad', session_id='ses_1', time_created=now_ms,
                  time_updated=now_ms, data='{"role": "user"}'),
             make_message('m1', 'ses_1', created=now_ms,
                          tokens={'input': 9, 'output': 1, 'reasoning': 0,
                                  'cache': {'read': 2, 'write': 0}})])
        self._poll_render({'tracking_provider': 'opencode'}, now=NOW_S,
                          history=True)
        window = self._open_window()
        raw_history = json.loads(window.raw.toPlainText())['history']
        self.assertEqual(raw_history['skipped_message_rows'], 1)
        self.assertIn('1', window.history_note.text())

    def test_message_cost_never_reaggregated(self):
        self._attach(
            [{'id': 't1'}],
            [make_session('ses_1', cost=0.25, updated=BASE_MS)],
            [make_message('m1', 'ses_1', cost=99)],
            [make_part('p1', 'ses_1', created=BASE_MS - 100000)])
        self._poll_render({'scope': 'conversation', 'pinned': 'ses_1',
                           'tracking_provider': 'opencode'}, now=NOW_S,
                          history=True)
        window = self._open_window()
        labels = self._column(window.metrics, 0)
        values = dict(zip(labels, self._column(window.metrics, 1)))
        cost = values['OpenCode raw · Recorded Cost']
        self.assertIn('0.25', cost.replace(',', ''))
        self.assertNotIn('99', cost)

    def test_cost_has_no_currency_symbol(self):
        self._attach(
            [{'id': 't1'}],
            [make_session('ses_1', cost=1.5, updated=BASE_MS)])
        self._poll_render({'tracking_provider': 'opencode'}, now=NOW_S,
                          history=True)
        window = self._open_window()
        blob = window.raw.toPlainText()
        for symbol in ('$', 'USD', 'CAD', 'EUR', 'CNY', 'currency'):
            if symbol == 'currency':
                continue
            self.assertNotIn(symbol, blob)


class AnalyticsUiLocalizationTests(AnalyticsFixture, unittest.TestCase):
    def test_heading_scope_bilingual(self):
        self._attach(
            [{'id': 't1', 'working': True}],
            [make_session('ses_1', updated=BASE_MS)],
            [make_message('m1', 'ses_1')],
            [make_part('p1', 'ses_1', created=BASE_MS - 100000)])
        self._poll_render({'scope': 'conversation', 'pinned': 'ses_1',
                           'tracking_provider': 'opencode'}, now=NOW_S,
                          history=True)
        for language, scope_word in (('zh_CN', '会话'), ('en', 'Conversation')):
            self.panel.prefs['language'] = language
            self.panel.apply_language()
            window = self._open_window()
            self.assertIn('OpenCode', window.heading.text())
            self.assertIn(scope_word, window.heading.text())
            self.assertIn('OpenCode', window.raw.toPlainText())

    def test_full_compact_formatting(self):
        self._attach(
            [{'id': 't1'}],
            [make_session('ses_big', tokens=(1500, 20, 5, 400, 0))],
            [make_message('m-big', 'ses_big', created=BASE_MS,
                          tokens={'input': 1500, 'output': 2, 'reasoning': 0,
                                  'cache': {'read': 4, 'write': 0}})])
        out = self._poll_render({'scope': 'conversation',
                                 'pinned': 'ses_big',
                                 'tracking_provider': 'opencode'},
                                now=NOW_S, history=True)
        self.panel.prefs['token_number_format'] = 'full'
        window = self._open_window()
        labels = self._column(window.metrics, 0)
        values = dict(zip(labels, self._column(window.metrics, 1)))
        self.assertEqual(values['OpenCode raw · Input Tokens'], '1,500 Tokens')
        day_key = datetime.fromtimestamp(BASE_MS / 1000).date().isoformat()
        days = {self._cell(window.days, row, 0): row
                for row in range(window.days.rowCount())}
        self.assertEqual(self._cell(window.days, days[day_key], 1),
                         '1,500 Tokens')
        self.panel.prefs['token_number_format'] = 'compact'
        window = self._open_window()
        labels = self._column(window.metrics, 0)
        values = dict(zip(labels, self._column(window.metrics, 1)))
        self.assertEqual(values['OpenCode raw · Input Tokens'], '1.50K Tokens')
        days = {self._cell(window.days, row, 0): row
                for row in range(window.days.rowCount())}
        self.assertEqual(self._cell(window.days, days[day_key], 1),
                         '1.50K Tokens')

    def test_long_labels_render_safely(self):
        import json as _json
        long_id = 'm-' + 'x' * 200
        model = _json.dumps({'id': long_id, 'providerID': 'alt',
                             'variant': 'v'})
        self._attach(
            [{'id': 't1'}],
            [make_session('ses_1', model=model)])
        self._poll_render({'tracking_provider': 'opencode'}, now=NOW_S,
                          history=True)
        window = self._open_window()
        self.assertIn(long_id, self._column(window.models, 0))
        self.app.processEvents()

    def test_raw_tab_allowlist_only(self):
        self._attach(
            [{'id': 't1', 'working': True}],
            [make_session('ses_1', project='proj-a',
                          directory='/synthetic/alpha',
                          tokens=(100, 20, 5, 400, 0), cost=0.05,
                          updated=BASE_MS)],
            [make_message('m1', 'ses_1')],
            [make_part('p1', 'ses_1', created=BASE_MS - 100000)])
        self._poll_render({'scope': 'conversation', 'pinned': 'ses_1',
                           'tracking_provider': 'opencode'}, now=NOW_S,
                          history=True)
        window = self._open_window()
        blob = window.raw.toPlainText()
        payload = json.loads(blob)
        self.assertEqual(payload['provider'], 'opencode')
        self.assertEqual(payload['scope'], 'conversation')
        for forbidden in ('directory', '/synthetic/alpha', 'tool_calls',
                          'sk-', 'share', 'credential', 'token_count'):
            self.assertNotIn(forbidden, blob)

    def test_synthetic_ui_checks(self):
        import os
        shots = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), '.private', 'ui-slice6')
        os.makedirs(shots, exist_ok=True)
        self._attach(
            [{'id': 't1', 'working': True}],
            [make_session('ses_1', project='proj-a',
                          directory='/synthetic/alpha',
                          tokens=(100, 20, 5, 400, 0), cost=0.05,
                          updated=BASE_MS)],
            [make_message('m1', 'ses_1')],
            [make_part('p1', 'ses_1', created=BASE_MS - 100000)])
        self._poll_render({'scope': 'conversation', 'pinned': 'ses_1',
                           'tracking_provider': 'opencode'}, now=NOW_S,
                          history=True)
        window = self._open_window()
        path = os.path.join(shots, 'opencode-populated.png')
        self._assert_shot(window, path)
        self._attach(
            [{'id': 't9'}],
            [make_session('ses_part', tokens=(None, 4, None, 9, None),
                          cost=None)])
        self._poll_render({'scope': 'conversation', 'pinned': 'ses_part',
                           'tracking_provider': 'opencode'}, now=NOW_S,
                          history=True)
        window = self._open_window()
        path = os.path.join(shots, 'opencode-partial.png')
        self._assert_shot(window, path)


class HistoryCostCorrectionTests(AnalyticsFixture, unittest.TestCase):
    """Slice 6 corrections: authoritative history column order, daily /
    range / lifetime coverage, and model/session recorded cost."""

    def _headers(self, table):
        return [table.horizontalHeaderItem(column).text()
                for column in range(table.columnCount())]

    def _row(self, table, name):
        rows = {self._cell(table, row, 0): row
                for row in range(table.rowCount())}
        return [self._cell(table, rows[name], column)
                for column in range(table.columnCount())]

    def _tip(self, table, name, column):
        rows = {self._cell(table, row, 0): row
                for row in range(table.rowCount())}
        return table.item(rows[name], column).toolTip()

    def test_history_header_value_mapping(self):
        deltas = {'input': 1, 'output': 2, 'reasoning': 3,
                  'cache': {'read': 4, 'write': 5}}
        # A fixed day safely outside Today/Last-7/Last-30 in any timezone.
        old_ms = BASE_MS - 40 * 86400000
        old_day = datetime.fromtimestamp(old_ms / 1000).date().isoformat()
        self._attach(
            [{'id': 't1'}],
            [make_session('ses_1', tokens=(10, 20, 30, 40, 50))],
            [make_message('m1', 'ses_1', created=old_ms, tokens=deltas)])
        self._poll_render({'tracking_provider': 'opencode'}, now=NOW_S,
                          history=True)
        window = self._open_window()
        expected = ['Input Tokens', 'Output Tokens', 'Reasoning Tokens',
                    'Cached Tokens', 'Write Tokens', 'Total Tokens',
                    'Type / Coverage']
        self.assertEqual(self._headers(window.days)[1:], expected)
        self.assertEqual(self._headers(window.ranges)[1:], expected)
        self.assertEqual(
            self._row(window.days, old_day),
            [old_day, '1 Tokens', '2 Tokens', '3 Tokens', '4 Tokens',
             '5 Tokens', 'N/A', 'complete'])
        lifetime = self._row(window.ranges, 'Local recorded lifetime')
        self.assertEqual(
            lifetime,
            ['Local recorded lifetime', '10 Tokens', '20 Tokens',
             '30 Tokens', '40 Tokens', '50 Tokens', 'N/A', 'complete'])
        names = [self._cell(window.ranges, row, 0)
                 for row in range(window.ranges.rowCount())]
        for name in names[1:]:
            self.assertEqual(self._row(window.ranges, name)[1:7],
                             ['N/A', 'N/A', 'N/A', 'N/A', 'N/A', 'N/A'])

    def test_partial_daily_marks_day_and_ranges(self):
        now_ms = int(time.time() * 1000)
        full = {'input': 5, 'output': 3, 'reasoning': 1,
                'cache': {'read': 2, 'write': 0}}
        partial = {'input': None, 'output': 7, 'reasoning': 0,
                   'cache': {'read': 1, 'write': 0}}
        self._attach(
            [{'id': 't1'}],
            [make_session('ses_1', updated=now_ms)],
            [make_message('m1', 'ses_1', created=now_ms, tokens=full),
             make_message('m2', 'ses_1', created=now_ms, tokens=partial)])
        self._poll_render({'tracking_provider': 'opencode'}, now=NOW_S,
                          history=True)
        window = self._open_window()
        day_key = datetime.fromtimestamp(now_ms / 1000).date().isoformat()
        row = self._row(window.days, day_key)
        self.assertEqual(row[1], '5 Tokens · partial')
        self.assertIn('partial', self._tip(window.days, day_key, 1))
        self.assertEqual(row[2], '10 Tokens')
        names = [self._cell(window.ranges, row, 0)
                 for row in range(window.ranges.rowCount())]
        for name in names[1:]:
            cells = self._row(window.ranges, name)
            self.assertEqual(cells[1], '5 Tokens · partial')
            self.assertIn('partial', cells[7])

    def test_unknown_zero_mixed_ranges(self):
        day_a = int(time.time() * 1000)
        day_b = day_a - 2 * 86400000
        self._attach(
            [{'id': 't1'}],
            [make_session('ses_1', updated=day_a)],
            [make_message('m-a', 'ses_1', created=day_a,
                          tokens={'input': 8, 'output': 0, 'reasoning': 0,
                                  'cache': {'read': 0, 'write': 0}}),
             make_message('m-b', 'ses_1', created=day_b,
                          tokens={'input': None, 'output': 4,
                                  'reasoning': 0,
                                  'cache': {'read': 1, 'write': 0}})])
        self._poll_render({'tracking_provider': 'opencode'}, now=NOW_S,
                          history=True)
        window = self._open_window()
        key_b = datetime.fromtimestamp(day_b / 1000).date().isoformat()
        row_b = self._row(window.days, key_b)
        self.assertEqual(row_b[1], 'N/A')
        key_a = datetime.fromtimestamp(day_a / 1000).date().isoformat()
        row_a = self._row(window.days, key_a)
        self.assertEqual(row_a[2], '0 Tokens')
        names = [self._cell(window.ranges, row, 0)
                 for row in range(window.ranges.rowCount())]
        last30 = self._row(window.ranges, names[-1])
        self.assertEqual(last30[1], '8 Tokens · partial')
        self.assertIn('partial', last30[7])

    def test_skipped_rows_cap_range_coverage(self):
        now_ms = int(time.time() * 1000)
        self._attach(
            [{'id': 't1'}],
            [make_session('ses_1', updated=now_ms)],
            [dict(id='bad', session_id='ses_1', time_created=now_ms,
                  time_updated=now_ms, data='{"role": "user"}'),
             make_message('m1', 'ses_1', created=now_ms,
                          tokens={'input': 9, 'output': 1, 'reasoning': 0,
                                  'cache': {'read': 2, 'write': 0}})])
        self._poll_render({'tracking_provider': 'opencode'}, now=NOW_S,
                          history=True)
        window = self._open_window()
        names = [self._cell(window.ranges, row, 0)
                 for row in range(window.ranges.rowCount())]
        for name in names[1:]:
            cells = self._row(window.ranges, name)
            self.assertNotEqual(cells[7], 'complete')

    def test_session_recorded_cost_column(self):
        self._attach(
            [{'id': 't1'}],
            [make_session('ses_paid', cost=2.5),
             make_session('ses_free', cost=0.0),
             make_session('ses_myst', cost=None)])
        self._poll_render({'tracking_provider': 'opencode'}, now=NOW_S,
                          history=True)
        window = self._open_window()
        rows = {self._cell(window.sessions, row, 0): row
                for row in range(window.sessions.rowCount())}
        self.assertEqual(
            self._cell(window.sessions, rows['opencode:ses_paid'], 8),
            '2.5000')
        self.assertEqual(
            self._cell(window.sessions, rows['opencode:ses_free'], 8), '0')
        missing = self._cell(window.sessions, rows['opencode:ses_myst'], 8)
        self.assertEqual(missing, 'N/A')
        tip = window.sessions.item(rows['opencode:ses_myst'], 8).toolTip()
        self.assertIn('unknown', tip)

    def test_model_recorded_cost_aggregation(self):
        import json as _json
        same = _json.dumps({'id': 'cost-model-z', 'providerID': 'alt',
                            'variant': 'v'})
        other = _json.dumps({'id': 'solo-model', 'providerID': 'alt',
                             'variant': 'v'})
        self._attach(
            [{'id': 't1'}],
            [make_session('ses_1', model=same, cost=1.0),
             make_session('ses_2', model=same, cost=2.0),
             make_session('ses_3', model=same, cost=None),
             make_session('ses_4', model=other, cost=None)])
        self._poll_render({'tracking_provider': 'opencode'}, now=NOW_S,
                          history=True)
        window = self._open_window()
        rows = {self._cell(window.models, row, 0): row
                for row in range(window.models.rowCount())}
        self.assertIn('cost-model-z', rows)
        self.assertIn('solo-model', rows)
        self.assertEqual(
            self._cell(window.models, rows['cost-model-z'], 8), '3.0000')
        tip = window.models.item(rows['cost-model-z'], 8).toolTip()
        self.assertIn('partial', tip)
        solo = self._cell(window.models, rows['solo-model'], 8)
        self.assertEqual(solo, 'N/A')
        solo_tip = window.models.item(rows['solo-model'], 8).toolTip()
        self.assertIn('unknown', solo_tip)

    def test_model_cost_all_known_is_complete(self):
        import json as _json
        model = _json.dumps({'id': 'paid-model', 'providerID': 'alt',
                             'variant': 'v'})
        self._attach(
            [{'id': 't1'}],
            [make_session('ses_1', model=model, cost=1.0),
             make_session('ses_2', model=model, cost=2.0)])
        self._poll_render({'tracking_provider': 'opencode'}, now=NOW_S,
                          history=True)
        window = self._open_window()
        rows = {self._cell(window.models, row, 0): row
                for row in range(window.models.rowCount())}
        self.assertEqual(
            self._cell(window.models, rows['paid-model'], 8), '3.0000')
        tip = window.models.item(rows['paid-model'], 8).toolTip()
        self.assertEqual(tip, '')

    def test_cost_boundaries_have_no_currency(self):
        self._attach(
            [{'id': 't1', 'working': True}],
            [make_session('ses_1', cost=1.5, updated=BASE_MS)],
            [make_message('m1', 'ses_1')],
            [make_part('p1', 'ses_1', created=BASE_MS - 100000)])
        self._poll_render({'scope': 'conversation', 'pinned': 'ses_1',
                           'tracking_provider': 'opencode'}, now=NOW_S,
                          history=True)
        window = self._open_window()
        blob_parts = [window.raw.toPlainText()]
        for table in (window.metrics, window.models, window.sessions,
                      window.ranges, window.days):
            for row in range(table.rowCount()):
                for column in range(table.columnCount()):
                    blob_parts.append(table.item(row, column).text())
                    blob_parts.append(table.item(row, column).toolTip())
        blob = '\n'.join(blob_parts)
        for symbol in ('$', 'USD', 'CAD', 'EUR', 'CNY'):
            self.assertNotIn(symbol, blob)
        self.assertEqual(window.days.columnCount(), 8)
        self.assertEqual(window.ranges.columnCount(), 8)

    def test_skipped_only_day_keeps_ranges_partial(self):
        now_ms = int(time.time() * 1000)
        old_ms = now_ms - 2 * 86400000
        old_day = datetime.fromtimestamp(old_ms / 1000).date().isoformat()
        today_key = datetime.fromtimestamp(now_ms / 1000).date().isoformat()
        self._attach(
            [{'id': 't1'}],
            [make_session('ses_1', updated=now_ms)],
            [dict(id='skipped', session_id='ses_1', time_created=old_ms,
                  time_updated=old_ms, data='{"role": "user"}'),
             make_message('m1', 'ses_1', created=now_ms,
                          tokens={'input': 6, 'output': 1, 'reasoning': 0,
                                  'cache': {'read': 2, 'write': 0}})])
        self._poll_render({'tracking_provider': 'opencode'}, now=NOW_S,
                          history=True)
        window = self._open_window()
        today = self._row(window.days, today_key)
        self.assertEqual(today[1], '6 Tokens')
        skipped = self._row(window.days, old_day)
        self.assertEqual(skipped[1:7],
                         ['N/A', 'N/A', 'N/A', 'N/A', 'N/A', 'N/A'])
        self.assertEqual(skipped[7], 'unknown')
        names = [self._cell(window.ranges, row, 0)
                 for row in range(window.ranges.rowCount())]
        self.assertEqual(self._row(window.ranges, names[0])[1], '100 Tokens')
        for name in names[1:]:
            cells = self._row(window.ranges, name)
            if '30' in name or '7' in name:
                self.assertEqual(cells[1], '6 Tokens · partial')
                self.assertIn('partial', cells[7])
            else:
                self.assertEqual(cells[1], '6 Tokens')
            self.assertEqual(cells[6], 'N/A')

    def test_correction_screenshots(self):
        import os
        shots = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), '.private', 'ui-slice6')
        os.makedirs(shots, exist_ok=True)
        deltas = {'input': 1, 'output': 2, 'reasoning': 3,
                  'cache': {'read': 4, 'write': 5}}
        self._attach(
            [{'id': 't1'}],
            [make_session('ses_1', tokens=(10, 20, 30, 40, 50))],
            [make_message('m1', 'ses_1', created=BASE_MS, tokens=deltas)])
        self._poll_render({'tracking_provider': 'opencode'}, now=NOW_S,
                          history=True)
        window = self._open_window()
        window.tabs.setCurrentIndex(3)
        self.app.processEvents()
        path = os.path.join(shots, 'opencode-history.png')
        self._assert_shot(window, path)
        now_ms = int(time.time() * 1000)
        self._attach(
            [{'id': 't2'}],
            [make_session('ses_p', tokens=(None, 4, None, 9, None),
                          updated=now_ms)],
            [make_message('m1', 'ses_p', created=now_ms,
                          tokens={'input': None, 'output': 4,
                                  'reasoning': None,
                                  'cache': {'read': 9, 'write': None}})])
        self._poll_render({'tracking_provider': 'opencode'}, now=NOW_S,
                          history=True)
        window = self._open_window()
        window.tabs.setCurrentIndex(3)
        self.app.processEvents()
        path = os.path.join(shots, 'opencode-history-partial.png')
        self._assert_shot(window, path)
        import json as _json
        model = _json.dumps({'id': 'shot-model', 'providerID': 'alt',
                             'variant': 'v'})
        self._attach(
            [{'id': 't3'}],
            [make_session('ses_c1', model=model, cost=1.25),
             make_session('ses_c2', model=model, cost=None)])
        self._poll_render({'tracking_provider': 'opencode'}, now=NOW_S,
                          history=True)
        window = self._open_window()
        window.tabs.setCurrentIndex(1)
        self.app.processEvents()
        path = os.path.join(shots, 'opencode-model-cost.png')
        self._assert_shot(window, path)


class RecordedTotalAnalyticsTests(AnalyticsFixture, unittest.TestCase):
    """OpenCode recorded Total across metrics, model/session tables and
    history Lifetime; day/range rows stay N/A (message deltas, never
    stored rollups)."""

    FIVE = (1000, 200, 30, 4000, 70)
    FIVE_SUM = 5300

    def _verified_store(self):
        other_model = json.dumps({'id': 'other-model',
                                  'providerID': 'testco',
                                  'variant': 'default'})
        return (
            [{'id': 't1'}],
            [make_session('ses_a', version='1.18.31', tokens=self.FIVE,
                          cost=0.05, updated=BASE_MS),
             make_session('ses_b', version='1.18.32', tokens=self.FIVE,
                          cost=0.05, updated=BASE_MS),
             make_session('ses_c', model=other_model, project='proj-c',
                          version='9.9.9',
                          tokens=(7, 7, 7, 7, 7), cost=0.01,
                          updated=BASE_MS)],
            [make_message('ma', 'ses_a'), make_message('mb', 'ses_b'),
             make_message('mc', 'ses_c')],
            [make_part('pa', 'ses_a', created=BASE_MS - 100000),
             make_part('pb', 'ses_b', created=BASE_MS - 100000),
             make_part('pc', 'ses_c', created=BASE_MS - 100000)])

    def test_verified_project_scope_totals(self):
        threads, sessions, messages, parts = self._verified_store()
        self._attach(threads, sessions, messages, parts)
        out = self._poll_render(
            {'scope': 'project', 'pinned': 'ses_a',
             'tracking_provider': 'opencode'}, now=NOW_S, history=True)
        self.assertEqual(out['result']['tokens']['total'],
                         self.FIVE_SUM * 2)
        window = self._open_window()
        labels = self._column(window.metrics, 0)
        values = dict(zip(labels, self._column(window.metrics, 1)))
        self.assertEqual(values['OpenCode raw · Total Tokens'],
                         '10.60K Tokens')
        models = {self._cell(window.models, row, 0): row
                  for row in range(window.models.rowCount())}
        self.assertEqual(self._cell(window.models, models['test-model'], 6),
                         '10.60K Tokens')
        rows = {self._cell(window.sessions, row, 0): row
                for row in range(window.sessions.rowCount())}
        self.assertEqual(
            self._cell(window.sessions, rows['opencode:ses_a'], 6),
            '5.30K Tokens')
        self.assertEqual(
            self._cell(window.sessions, rows['opencode:ses_b'], 6),
            '5.30K Tokens')
        lifetime = self._row(window.ranges, 'Local recorded lifetime')
        self.assertEqual(lifetime[6], '10.60K Tokens')
        # Day/range rows aggregate message deltas: Total stays N/A.
        for row in range(window.days.rowCount()):
            self.assertEqual(self._cell(window.days, row, 6), 'N/A')
        names = [self._cell(window.ranges, row, 0)
                 for row in range(window.ranges.rowCount())]
        rows = {self._cell(window.ranges, row, 0): row
                for row in range(window.ranges.rowCount())}
        for name in names[1:]:
            self.assertEqual(self._cell(window.ranges, rows[name], 6),
                             'N/A')

    def test_mixed_scope_total_unavailable(self):
        threads, sessions, messages, parts = self._verified_store()
        self._attach(threads, sessions, messages, parts)
        out = self._poll_render({'tracking_provider': 'opencode'},
                                now=NOW_S, history=True)
        self.assertIsNone(out['result']['tokens']['total'])
        window = self._open_window()
        labels = self._column(window.metrics, 0)
        values = dict(zip(labels, self._column(window.metrics, 1)))
        self.assertEqual(values['OpenCode raw · Total Tokens'], 'N/A')
        models = {self._cell(window.models, row, 0): row
                  for row in range(window.models.rowCount())}
        self.assertEqual(self._cell(window.models, models['test-model'], 6),
                         '10.60K Tokens')
        self.assertEqual(self._cell(window.models, models['other-model'], 6),
                         'N/A')
        lifetime = self._row(window.ranges, 'Local recorded lifetime')
        self.assertEqual(lifetime[6], 'N/A')

    def _row(self, table, name):
        rows = {self._cell(table, row, 0): row
                for row in range(table.rowCount())}
        return [self._cell(table, rows[name], column)
                for column in range(table.columnCount())]


if __name__ == '__main__':
    unittest.main()
