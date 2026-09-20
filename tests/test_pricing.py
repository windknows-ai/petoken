import json
import os
import sqlite3
import tempfile
import time
import unittest
from contextlib import closing
from pathlib import Path

from app_config import load_preferences
from pricing import (MODEL_PRICES, convert_usd, estimate_usd, format_cost,
                     normalize_currency, normalize_rates)
from usage import CodexStore


class CostFixture:
    """Minimal fake CODEX_HOME with a per-thread model choice."""

    def __init__(self, root):
        self.home = Path(root)
        self.rows = []
        self.projects = {}
        self.assignments = {}

    def add(self, thread, name, total, project_id=None, project_name=None,
            model='gpt-6-astra', cached=0):
        path = self.home / f'{thread}.jsonl'
        usage = dict(input_tokens=total - 10, cached_input_tokens=cached,
                     output_tokens=10, reasoning_output_tokens=0, total_tokens=total)
        events = [
            dict(type='session_meta', payload=dict(id=thread, timestamp='2026-09-19T12:00:00Z')),
            dict(type='turn_context', payload=dict(model=model, effort='high')),
            dict(type='event_msg', timestamp='2026-09-19T12:00:02Z', payload=dict(
                type='token_count', info=dict(total_token_usage=usage, last_token_usage=usage,
                                              model_context_window=1000))),
        ]
        path.write_text(''.join(json.dumps(event) + '\n' for event in events), encoding='utf-8')
        stamp = time.time()
        os.utime(path, (stamp, stamp))
        self.rows.append(dict(id=thread, name=name, title='', cwd='', rollout_path=str(path),
            model=model, reasoning_effort='high', source='desktop', project_id=project_id,
            git_origin_url='', updated_at=int(stamp), archived=0))
        if project_id:
            self.assignments[thread] = {'projectId': project_id}
            self.projects.setdefault(project_id, {'name': project_name} if project_name else {})

    def finish(self):
        with closing(sqlite3.connect(self.home / 'state_1.sqlite')) as db:
            db.execute('''create table threads (
                id text, name text, title text, cwd text, rollout_path text, model text,
                reasoning_effort text, source text, project_id text, git_origin_url text,
                updated_at integer, archived integer)''')
            for row in self.rows:
                db.execute('insert into threads values (?,?,?,?,?,?,?,?,?,?,?,?)', tuple(row.values()))
            db.commit()
        state = {'local-projects': self.projects, 'thread-project-assignments': self.assignments}
        (self.home / '.codex-global-state.json').write_text(json.dumps(state), encoding='utf-8')
        return CodexStore(self.home)


class PricingTests(unittest.TestCase):
    def test_internal_table_has_verified_models_only(self):
        self.assertEqual(set(MODEL_PRICES), {'gpt-6-astra', 'gpt-5.6-sol', 'gpt-5.6-terra', 'gpt-5.6-luna'})

    def test_estimate_usd_known_model_tier_and_unknown(self):
        tokens = dict(input_tokens=1000, cached_input_tokens=800,
                      output_tokens=100, reasoning_output_tokens=80)
        self.assertAlmostEqual(estimate_usd(tokens, 'gpt-6-astra'), .0078)
        self.assertAlmostEqual(estimate_usd(tokens, 'gpt-6-astra', 'priority'), .0156)
        self.assertIsNone(estimate_usd(tokens, 'unknown-model'))
        self.assertIsNone(estimate_usd(dict(input_tokens=None, cached_input_tokens=0,
                                            output_tokens=1), 'gpt-6-astra'))

    def test_normalize_currency_accepts_four_and_falls_back(self):
        for code in ('USD', 'CAD', 'EUR', 'CNY'):
            self.assertEqual(normalize_currency(code), code)
        for bad in (None, '', 'usd', 'EUR ', 'GBP', 42):
            self.assertEqual(normalize_currency(bad), 'CAD')

    def test_convert_usd_uses_single_usd_table(self):
        rates = {'CAD': 1.4, 'EUR': 1.2, 'CNY': 0.2}
        self.assertEqual(convert_usd(10, 'USD', rates), 10)
        self.assertAlmostEqual(convert_usd(10, 'CAD', rates), 14.0)
        self.assertAlmostEqual(convert_usd(10, 'EUR', rates), 12.0)
        self.assertAlmostEqual(convert_usd(10, 'CNY', rates), 2.0)
        self.assertIsNone(convert_usd(10, 'EUR', {}))
        self.assertIsNone(convert_usd(None, 'CAD', rates))

    def test_format_cost_symbols_and_unknown(self):
        self.assertEqual(format_cost(12.3, 'USD'), '$12.30')
        self.assertEqual(format_cost(12.3, 'CAD'), 'CA$12.30')
        self.assertEqual(format_cost(12.3, 'EUR'), '\u20ac12.30')
        self.assertEqual(format_cost(12.3, 'CNY'), '\u00a512.30')
        self.assertEqual(format_cost(None, 'USD'), 'N/A')

    def test_normalize_rates_migrates_legacy_cad_cache(self):
        modern = normalize_rates(dict(date='d', source='s', rates={'CAD': 1.4}))
        self.assertEqual(modern['rates'], {'CAD': 1.4})
        legacy = normalize_rates(dict(rate=1.3, date='d', source='s'))
        self.assertEqual(legacy['rates'], {'CAD': 1.3})
        self.assertEqual(normalize_rates(None)['rates'], {})

    def test_legacy_custom_prices_load_but_do_not_drive_cost(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'settings.json'
            path.write_text(json.dumps({
                'manual_fx': 1.0,
                'prices': {'gpt-6-astra': (1000, 1000, 1000, 1000)},
            }), encoding='utf-8')
            prefs = load_preferences(path)
        self.assertEqual(prefs['manual_fx'], 1.0)
        self.assertEqual(prefs['prices'], {'gpt-6-astra': [1000, 1000, 1000, 1000]})
        with tempfile.TemporaryDirectory() as directory:
            fixture = CostFixture(directory)
            fixture.add('a', 'A', 100, 'p-a', 'Alpha')
            data = fixture.finish().read(scope='global')
        # Internal table: (90*10 + 10*50) / 1e6, not the legacy 1000x override.
        self.assertAlmostEqual(data['usd'], 0.0014)
        self.assertEqual(data['unknown'], [])

    def test_unknown_model_is_honestly_unavailable(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = CostFixture(directory)
            fixture.add('a', 'A', 50, 'p-a', 'Alpha', model='future-model-x')
            data = fixture.finish().read(scope='global')
        self.assertTrue(data['available'])
        self.assertEqual(data['usd'], 0)
        self.assertEqual(data['unknown'], ['future-model-x'])

    def test_partially_priced_scope_keeps_known_cost(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = CostFixture(directory)
            fixture.add('a', 'A', 100, 'p-a', 'Alpha')
            fixture.add('b', 'B', 50, 'p-a', 'Alpha', model='future-model-x')
            data = fixture.finish().read(scope='global')
        self.assertAlmostEqual(data['usd'], 0.0014)
        self.assertEqual(data['unknown'], ['future-model-x'])

    def test_scope_cost_matches_scope_tokens(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = CostFixture(directory)
            fixture.add('a1', 'A1', 100, 'p-a', 'Alpha')
            fixture.add('a2', 'A2', 150, 'p-a', 'Alpha')
            fixture.add('b', 'B', 200, 'p-b', 'Beta')
            store = fixture.finish()
            everything = store.read(scope='global')
            alpha = store.read(pinned='a1', scope='project')
            single = store.read(pinned='a2', scope='conversation')
            beta = store.read(pinned='b', scope='project')
            self.assertEqual(everything['tokens']['total_tokens'], 450)
            self.assertAlmostEqual(alpha['usd'] + beta['usd'], everything['usd'])
            self.assertEqual(single['tokens']['total_tokens'], 150)
            self.assertAlmostEqual(single['usd'], (140 * 10 + 10 * 50) / 1_000_000)

    def test_cached_input_uses_cache_price_split(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = CostFixture(directory)
            fixture.add('a', 'A', 1110, 'p-a', 'Alpha', cached=800)
            data = fixture.finish().read(scope='global')
        # Plain 300*10 + cached 800*1 + output 10*50, all over 1e6.
        self.assertAlmostEqual(data['usd'], (300 * 10 + 800 * 1 + 10 * 50) / 1_000_000)


if __name__ == '__main__':
    unittest.main()
