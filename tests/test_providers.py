"""Slice 2: Codex-only provider wrapper parity. Synthetic homes only."""
import json
import os
import sqlite3
import tempfile
import time
import unittest
from contextlib import closing
from pathlib import Path

import providers
from opencode_provider import OPENCODE_CAPABILITIES
from providers import (CODEX_CAPABILITIES, PROVIDER_CODEX, PROVIDER_OPENCODE,
                       CodexProvider, base_result, is_supported, wrap_quota)
from usage import CodexStore


def write_home(root, threads):
    home = Path(root)
    rows = []
    for spec in threads:
        thread = spec['id']
        usage = dict(input_tokens=90, cached_input_tokens=80, output_tokens=20,
                     reasoning_output_tokens=5, total_tokens=110)
        events = [
            dict(type='session_meta', payload=dict(id=thread, timestamp='2026-09-19T12:00:00Z')),
            dict(type='turn_context', payload=dict(model='gpt-6-astra', effort='high')),
        ]
        if spec.get('working'):
            events.append(dict(type='event_msg', timestamp='2026-09-19T12:00:01Z',
                               payload=dict(type='task_started')))
        events.append(dict(type='event_msg', timestamp='2026-09-19T12:00:02Z', payload=dict(
            type='token_count', info=dict(total_token_usage=usage, last_token_usage=usage,
                                          model_context_window=1000))))
        path = home / f'{thread}.jsonl'
        path.write_text(''.join(json.dumps(e) + '\n' for e in events), encoding='utf-8')
        stamp = time.time()
        os.utime(path, (stamp, stamp))
        rows.append(dict(id=thread, name=spec.get('name', thread), title='',
                         cwd='', rollout_path=str(path), model='gpt-6-astra',
                         reasoning_effort='high', source='desktop',
                         project_id='proj-1', git_origin_url='',
                         updated_at=int(stamp), archived=0))
    with closing(sqlite3.connect(home / 'state_1.sqlite')) as db:
        db.execute('''create table threads (
            id text, name text, title text, cwd text, rollout_path text, model text,
            reasoning_effort text, source text, project_id text, git_origin_url text,
            updated_at integer, archived integer)''')
        for row in rows:
            db.execute('insert into threads values (?,?,?,?,?,?,?,?,?,?,?,?)',
                       tuple(row.values()))
        db.commit()
    (home / '.codex-global-state.json').write_text(json.dumps({}), encoding='utf-8')
    return home


class ProviderContractTests(unittest.TestCase):
    def test_identities_and_capability_sets(self):
        self.assertEqual(PROVIDER_CODEX, 'codex')
        self.assertEqual(PROVIDER_OPENCODE, 'opencode')
        self.assertIn('working_context', CODEX_CAPABILITIES)
        self.assertIn('quotas', CODEX_CAPABILITIES)
        # Slice 3: OpenCode capabilities are proven by the adapter and
        # looked up there; the lookup must not deny implemented abilities.
        self.assertIn('scopes', OPENCODE_CAPABILITIES)
        self.assertIn('activity', OPENCODE_CAPABILITIES)
        self.assertNotIn('quotas', OPENCODE_CAPABILITIES)
        self.assertNotIn('working_context', OPENCODE_CAPABILITIES)
        self.assertTrue(is_supported('codex', 'scopes'))
        self.assertFalse(is_supported('codex', 'telepathy'))
        self.assertTrue(is_supported('opencode', 'scopes'))
        self.assertFalse(is_supported('opencode', 'telepathy'))
        self.assertFalse(is_supported('future', 'scopes'))

    def test_no_shared_token_schema_or_combined_totals(self):
        self.assertFalse(hasattr(providers, 'normalize_tokens'))
        self.assertFalse(hasattr(providers, 'combined_totals'))
        self.assertFalse(hasattr(providers, 'merge_providers'))

    def test_base_result_defaults_to_unknown(self):
        result = base_result('codex')
        self.assertFalse(result['available'])
        self.assertIsNone(result['tokens'])
        self.assertIsNone(result['working_context'])
        self.assertIsNone(result['last_success_at'])
        self.assertEqual(result['provider_name'], 'Codex')


class CodexParityTests(unittest.TestCase):
    def read_both(self, home, **kwargs):
        store = CodexStore(home)
        direct = store.read(**kwargs)
        wrapped = CodexProvider(CodexStore(home)).read(**kwargs)
        return direct, wrapped

    def test_full_data_parity_across_scopes(self):
        with tempfile.TemporaryDirectory() as directory:
            home = write_home(directory, [{'id': 't1', 'working': True}, {'id': 't2'}])
            for scope in ('global', 'project', 'conversation'):
                for history in (False, True):
                    direct, wrapped = self.read_both(
                        home, pinned='t2', scope=scope, include_history=history)
                    self.assertEqual(wrapped['payload'], direct)
                    self.assertEqual(wrapped['provider_id'], 'codex')
                    self.assertEqual(wrapped['provider_name'], 'Codex')
                    self.assertEqual(wrapped['capabilities'], CODEX_CAPABILITIES)
                    self.assertEqual(wrapped['available'], direct.get('available', False))
                    self.assertEqual(wrapped['tokens'], direct.get('tokens'))
                    self.assertEqual(wrapped['working_context'], direct.get('working_context'))
                    self.assertEqual(wrapped['scope_result'], direct.get('scope_result'))
                    if not direct.get('status'):
                        self.assertEqual(wrapped['status'], '')
                        self.assertIsNotNone(wrapped['last_success_at'])
                    self.assertEqual(wrapped['notes'], tuple(direct.get('notes') or ()))

    def test_scope_change_keeps_working_context(self):
        # Deterministic valid activity: t1 is working and its name matches
        # the inspected title, so both reads must carry a non-null context
        # for t1 while the scope result follows pinned t2.
        with tempfile.TemporaryDirectory() as directory:
            home = write_home(directory, [{'id': 't1', 'working': True}, {'id': 't2'}])
            provider = CodexProvider(CodexStore(home))
            seen = []
            for scope in ('global', 'project', 'conversation'):
                for history in (False, True):
                    direct, wrapped = self.read_both(
                        home, active_title='t1', pinned='t2', scope=scope,
                        include_history=history, activity_detection_valid=True)
                    self.assertEqual(wrapped['payload'], direct)
                    context = wrapped['working_context']
                    self.assertIsNotNone(context, (scope, history))
                    self.assertEqual(context['thread'], 't1')
                    self.assertEqual(context, direct['working_context'])
                    seen.append(wrapped['scope_result'])
            self.assertNotEqual(seen[1], seen[2])

    def test_missing_scope_selection_preserves_working_context(self):
        # An unavailable scope selection must not erase live working activity.
        with tempfile.TemporaryDirectory() as directory:
            home = write_home(directory, [{'id': 't1', 'working': True}, {'id': 't2'}])
            direct, wrapped = self.read_both(
                home, active_title='t1', pinned='ghost', scope='conversation',
                activity_detection_valid=True)
            self.assertEqual(wrapped['payload'], direct)
            self.assertEqual(direct['status'], 'status_pinned_unavailable')
            self.assertEqual(wrapped['status'], 'unavailable')
            self.assertEqual(wrapped['reason'], 'status_pinned_unavailable')
            self.assertIsNotNone(wrapped['working_context'])
            self.assertEqual(wrapped['working_context']['thread'], 't1')

    def test_history_flag_passes_through(self):
        with tempfile.TemporaryDirectory() as directory:
            home = write_home(directory, [{'id': 't1'}])
            provider = CodexProvider(CodexStore(home))
            self.assertIsNone(provider.read(pinned='t1')['payload']['history'])
            self.assertIsNotNone(
                provider.read(pinned='t1', include_history=True)['payload']['history'])

    def test_missing_data_stays_unavailable(self):
        with tempfile.TemporaryDirectory() as directory:
            wrapped = CodexProvider(CodexStore(Path(directory))).read()
            self.assertEqual(wrapped['payload']['status'], 'status_no_local_data')
            self.assertFalse(wrapped['available'])
            self.assertEqual(wrapped['status'], 'unavailable')
            self.assertEqual(wrapped['reason'], 'status_no_local_data')
            self.assertIsNone(wrapped['last_success_at'])
            self.assertIsNone(wrapped['tokens'])

    def test_corrupt_database_stays_unavailable(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, 'state_9.sqlite').write_bytes(b'not a database')
            wrapped = CodexProvider(CodexStore(Path(directory))).read()
            self.assertEqual(wrapped['payload']['status'], 'status_database_unavailable')
            self.assertFalse(wrapped['available'])
            self.assertIsNone(wrapped['last_success_at'])

    def test_nullable_fields_are_preserved_not_zeroed(self):
        with tempfile.TemporaryDirectory() as directory:
            home = write_home(directory, [{'id': 't1'}])
            wrapped = CodexProvider(CodexStore(home)).read(pinned='t1')
            self.assertEqual(wrapped['payload']['tokens']['total_tokens'], 110)
            # Cache-write was never recorded: explicit unknown, never zero-filled.
            self.assertIsNone(wrapped['payload']['tokens']['cache_write_input_tokens'])

    def test_cost_provenance_preserved_beside_numeric_alias(self):
        # The envelope cost is a numeric alias only; provenance and coverage
        # (usd/unknown/partial) must stay in the payload — it is not a
        # complete fully-priced estimate on its own.
        with tempfile.TemporaryDirectory() as directory:
            home = write_home(directory, [{'id': 't1'}])
            direct, wrapped = self.read_both(home, pinned='t1', scope='conversation')
            self.assertEqual(wrapped['cost'], direct['usd'])
            for key in ('usd', 'unknown', 'partial'):
                self.assertIn(key, wrapped['payload'])
            self.assertEqual(wrapped['payload']['usd'], direct['usd'])
            self.assertEqual(wrapped['payload']['unknown'], direct['unknown'])
            self.assertEqual(wrapped['payload']['partial'], direct['partial'])

    def test_quota_payloads_pass_through_tagged(self):
        live = dict(limits={'primary': {'usedPercent': 30}}, sampled=1234.5, error='')
        wrapped = wrap_quota(live)
        self.assertEqual(wrapped['limits'], live['limits'])
        self.assertEqual(wrapped['sampled'], 1234.5)
        self.assertEqual(wrapped['provider_id'], 'codex')
        failed = wrap_quota(dict(error='quota_error'))
        self.assertEqual(failed['error'], 'quota_error')
        self.assertEqual(failed['provider_id'], 'codex')
        self.assertNotIn('limits', failed)


if __name__ == '__main__':
    unittest.main()
