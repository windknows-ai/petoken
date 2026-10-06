import time
import unittest
from datetime import datetime

from PySide6.QtWidgets import QApplication

import reports
from notifications import recap_detail

APP = QApplication.instance() or QApplication([])
# Wednesday 2026-10-07 15:00 local time.
NOW = datetime(2026, 10, 7, 15, 0).timestamp()
HOUR = 3600


def event(provider, session, hours_ago, tokens, usd, project='site'):
    return dict(provider=provider, session=session, at=NOW - hours_ago * HOUR, tokens=tokens, usd=usd,
                project=project)


DATA = dict(events=[
    event('claude', 'a', 1, 1000, 0.5),
    event('claude', 'a', 2, 500, 0.25),
    event('codex', 't1', 3, 2000, None, 'api'),        # Price unknown.
    event('codex', 't1', 4, 100, 0.1, 'api'),
    event('claude', 'b', 26, 700, 0.2, 'docs'),        # Yesterday 13:00, before the same time today.
    event('claude', 'c', 24 * 4, 900, 0.3, 'docs'),    # Last week.
], history=[
    dict(provider='claude', id='a', title='Add dark mode', project='site', started_at=NOW - 2 * HOUR,
         finished_at=NOW - HOUR, tokens=1500, usd=0.75),
    dict(provider='codex', id='t1', title='Fix login', project='api', started_at=NOW - 4 * HOUR,
         finished_at=None, tokens=2100, usd=None),
    dict(provider='claude', id='old', title='Old work', project='docs', started_at=NOW - 40 * 86400,
         finished_at=NOW - 40 * 86400, tokens=1, usd=0),
], missing=[], activity=dict(
    # A turn from 14:00-14:10 today, one from 23:50 yesterday to 00:20 today.
    # Codex turns carry a fourth field, the outcome.
    turns=[(NOW - HOUR, NOW - HOUR + 600, 'site'),
           (NOW - 15 * HOUR - 600, NOW - 15 * HOUR + 1200, 'site', 'completed')],
    edits=[(NOW - HOUR, 'site', 'a.css'), (NOW - HOUR + 60, 'site', 'a.css'), (NOW - HOUR, 'site', 'b.css'),
           (NOW - 30 * HOUR, 'site', 'old.css')]))


class ReportTests(unittest.TestCase):
    def test_periods(self):
        start, end, previous = reports.period('today', NOW)
        self.assertEqual(datetime.fromtimestamp(start), datetime(2026, 10, 7))
        self.assertEqual(datetime.fromtimestamp(previous), datetime(2026, 10, 6))
        start, _, previous = reports.period('week', NOW)
        self.assertEqual(datetime.fromtimestamp(start), datetime(2026, 10, 5))   # Monday.
        self.assertEqual(datetime.fromtimestamp(previous), datetime(2026, 9, 28))

    def test_today(self):
        notices = [dict(kind='finished', at=NOW - HOUR, project='site', provider='claude',
                        detail=recap_detail(dict(files=['ignored.css'], duration_s=600, usd=0.75))),
                   dict(kind='finished', at=NOW - 2 * HOUR, project='api', provider='codex',
                        detail=recap_detail(dict(files=['login.py'], duration_s=None, usd=None))),
                   dict(kind='failed', at=NOW - HOUR, project='api', detail='rate_limit'),
                   dict(kind='finished', at=NOW - 30 * HOUR, project='x', detail='')]
        summary = reports.summarize(DATA, notices, 'today', NOW)
        self.assertEqual(summary['tokens'], 3600)
        self.assertAlmostEqual(summary['usd'], 0.85)
        self.assertTrue(summary['partial'])
        self.assertEqual(summary['providers']['claude'], dict(tokens=1500, usd=0.75, partial=False, tasks=1))
        # 10 min today + the 20 min after midnight; a.css and b.css (recaps are not counted twice).
        self.assertEqual((summary['finished'], summary['failed'], summary['files'], summary['seconds']),
                         (2, 1, 2, 1800))
        self.assertEqual([p['name'] for p in summary['projects']], ['api', 'site'])
        # By 15:00 yesterday 700 tokens were used.
        self.assertAlmostEqual(summary['change'], (3600 - 700) / 700)

    def test_week_and_empty(self):
        self.assertEqual(reports.summarize(DATA, [], 'week', NOW)['tokens'], 4300)
        empty = reports.summarize(dict(events=[], history=[], missing=['codex']), [], 'today', NOW)
        self.assertEqual((empty['tokens'], empty['usd'], empty['change'], empty['missing']), (0, 0, None, ['codex']))

    def test_search(self):
        history = DATA['history']
        self.assertEqual([r['id'] for r in reports.search(history, 'DARK')], ['a'])
        self.assertEqual([r['id'] for r in reports.search(history, 'api')], ['t1'])
        self.assertEqual([r['id'] for r in reports.search(history, provider='claude', since=NOW - 7 * 86400)], ['a'])
        self.assertEqual(len(reports.search(history)), 3)


class FakeCodexStore:
    def __init__(self):
        self.since = 'unset'

    def read(self, scope):
        self.scope = scope

    def task_history(self, scope):
        return [dict(thread_id='t1', title='Fix login', project='api', started_at=1.0,
                     finished_at=None, total_tokens=30, usd=None)]

    def usage_events(self, since):
        self.since = since
        return [dict(at=NOW - HOUR, thread_id='t1', project=None, model='gpt-5.5', total_tokens=20, usd=.1),
                dict(at=None, thread_id='t1', project='api', model=None, total_tokens=10, usd=None)]


class CodexSourceTests(unittest.TestCase):
    def test_codex_usage_comes_from_the_public_events(self):
        store = FakeCodexStore()
        events, history = reports.codex_sources(store, since=NOW - 7 * 86400)
        self.assertEqual(store.since, NOW - 7 * 86400)
        # The undated carry is left out; the project falls back to the task's.
        self.assertEqual(events, [dict(provider='codex', session='t1', at=NOW - HOUR, tokens=20,
                                       usd=.1, project='api')])
        self.assertEqual(history[0]['title'], 'Fix login')


class FakeStore:
    def list_events(self, kind=None, limit=500):
        return []


class FakePanel:
    live = False
    currency = 'USD'
    fx = dict(rates={})

    def __init__(self):
        self.prefs = dict(language='en')
        self.notifications = type('C', (), dict(store=FakeStore()))()


class ReportPageTests(unittest.TestCase):
    def test_page_loads_in_background_and_filters(self):
        from report_view import ReportPage
        page = ReportPage(FakePanel(), loader=lambda: DATA)
        page.refresh()
        deadline = time.time() + 5
        while page.data is None and time.time() < deadline:
            APP.processEvents()
            time.sleep(0.01)
        self.assertIs(page.data, DATA)   # Passed by reference, not copied.
        self.assertTrue(page.tiles['tasks'][0].text().isdigit())
        page.range.setCurrentIndex(2)   # All time.
        self.assertEqual(page.history.topLevelItemCount(), 3)
        page.query.setText('login')
        self.assertEqual(page.history.topLevelItemCount(), 1)
        self.assertEqual(page.history.topLevelItem(0).text(5), 'N/A')
        self.assertEqual(page._cost_text(0, True), 'N/A')
        self.assertEqual(page._cost_text(1.5, True), '≈ $1.50+')
        page.close()


if __name__ == '__main__':
    unittest.main()


class ReportCacheTests(unittest.TestCase):
    def test_one_load_at_a_time_and_staleness(self):
        import threading as th
        gate, calls, seen = th.Event(), [], []

        def loader():
            calls.append(1)
            gate.wait(5)
            return dict(events=[], history=[], missing=[])
        cache = reports.ReportCache(loader, max_age=60)
        self.assertTrue(cache.stale())
        self.assertTrue(cache.refresh(seen.append))
        self.assertFalse(cache.refresh(seen.append))       # Joins the running load.
        gate.set()
        deadline = time.time() + 5
        while len(seen) < 2 and time.time() < deadline:
            time.sleep(0.01)
        self.assertEqual((len(calls), len(seen)), (1, 2))
        self.assertFalse(cache.stale())
        self.assertTrue(cache.stale(time.time() + 61))

    def test_page_shows_cached_numbers_at_once(self):
        from report_view import ReportPage
        panel = FakePanel()
        panel.report_cache = reports.ReportCache(lambda: DATA)
        panel.report_cache.data, panel.report_cache.at = DATA, time.time()
        page = ReportPage(panel)
        page.refresh()
        self.assertIs(page.data, DATA)                       # No waiting for a load.
        self.assertFalse(page.loading)                       # Fresh: no background reload.
        page.close()

