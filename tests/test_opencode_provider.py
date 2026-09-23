"""Slice 3: OpenCode read-only incremental adapter. Synthetic stores only."""
import json
import os
import sqlite3
import tempfile
import time
import unittest
from contextlib import closing
from datetime import datetime
from pathlib import Path

import providers
from opencode_provider import (DB_TIMEOUT_S, OPENCODE_CAPABILITIES,
                               OpenCodeProvider, opencode_active_display,
                               parse_message_tokens, parse_model,
                               scoped_project_id, scoped_session_id)
from providers import CodexProvider, is_supported
from usage import CodexStore

SESSION_DDL = '''CREATE TABLE session (
    id TEXT, project_id TEXT, parent_id TEXT, directory TEXT, agent TEXT,
    model TEXT, version TEXT, tokens_input INTEGER, tokens_output INTEGER,
    tokens_reasoning INTEGER, tokens_cache_read INTEGER,
    tokens_cache_write INTEGER, cost REAL, time_created INTEGER,
    time_updated INTEGER)'''
MESSAGE_DDL = '''CREATE TABLE message (
    id TEXT, session_id TEXT, time_created INTEGER, time_updated INTEGER,
    data TEXT)'''
PART_DDL = '''CREATE TABLE part (
    id TEXT, message_id TEXT, session_id TEXT, time_created INTEGER,
    time_updated INTEGER, data TEXT)'''

BASE_MS = 1789900000000


def make_session(sid, project='proj-a', parent=None, directory='/synthetic/alpha',
                 model=None, version=None, tokens=(100, 20, 5, 400, 0), cost=0.05,
                 created=BASE_MS, updated=BASE_MS + 1000):
    if model is None:
        model = json.dumps({'id': 'test-model', 'providerID': 'testco',
                            'variant': 'default'})
    return dict(id=sid, project_id=project, parent_id=parent,
                directory=directory, agent='build', model=model,
                version=version,
                tokens_input=tokens[0], tokens_output=tokens[1],
                tokens_reasoning=tokens[2], tokens_cache_read=tokens[3],
                tokens_cache_write=tokens[4], cost=cost,
                time_created=created, time_updated=updated)


def make_message(mid, session_id, created=BASE_MS, role='assistant',
                 cost=7, tokens=None):
    if tokens is None:
        tokens = {'input': 10, 'output': 4, 'reasoning': 1,
                  'cache': {'read': 40, 'write': 0}}
    data = dict(role=role, mode='build', agent='build', variant='default',
                path='/synthetic/alpha', cost=cost,
                tokens=json.dumps(tokens), modelID='test-model',
                providerID='testco', time={'created': created})
    return dict(id=mid, session_id=session_id, time_created=created,
                time_updated=created, data=json.dumps(data))


def make_part(pid, session_id, created=BASE_MS, kind='step-start',
              reason=None, message_id='msg_1'):
    data = dict(type=kind)
    if reason is not None:
        data['reason'] = reason
    return dict(id=pid, message_id=message_id, session_id=session_id,
                time_created=created, time_updated=created,
                data=json.dumps(data))


def write_store(path, sessions, messages=(), parts=(),
                with_message_table=True, with_part_table=True):
    path = Path(path)
    if path.exists():
        path.unlink()
    with closing(sqlite3.connect(path)) as db:
        db.execute(SESSION_DDL)
        for row in sessions:
            db.execute('INSERT INTO session VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                       tuple(row[key] for key in (
                           'id', 'project_id', 'parent_id', 'directory',
                           'agent', 'model', 'version', 'tokens_input',
                           'tokens_output', 'tokens_reasoning',
                           'tokens_cache_read', 'tokens_cache_write',
                           'cost', 'time_created', 'time_updated')))
        if with_message_table:
            db.execute(MESSAGE_DDL)
            for row in messages:
                db.execute('INSERT INTO message VALUES (?,?,?,?,?)',
                           (row['id'], row['session_id'], row['time_created'],
                            row['time_updated'], row['data']))
        if with_part_table:
            db.execute(PART_DDL)
            for row in parts:
                db.execute('INSERT INTO part VALUES (?,?,?,?,?,?)',
                           (row['id'], row['message_id'], row['session_id'],
                            row['time_created'], row['time_updated'],
                            row['data']))
        db.commit()
    return path


class StoreFailureTests(unittest.TestCase):
    def test_missing_store_unavailable(self):
        with tempfile.TemporaryDirectory() as directory:
            result = OpenCodeProvider(
                Path(directory) / 'absent.db').read(pinned='ses_x')
        self.assertFalse(result['available'])
        self.assertEqual(result['status'], 'unavailable')
        self.assertEqual(result['reason'], 'missing_store')
        self.assertIsNone(result['payload'])
        self.assertIsNone(result['last_success_at'])
        self.assertEqual(result['provider_id'], 'opencode')

    def test_locked_store_isolated(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write_store(Path(directory) / 'open.db',
                               [make_session('ses_1')])
            holder = sqlite3.connect(path, timeout=5)
            holder.execute('BEGIN EXCLUSIVE')
            try:
                result = OpenCodeProvider(path).read(pinned='ses_1')
            finally:
                holder.rollback()
                holder.close()
        self.assertFalse(result['available'])
        self.assertEqual(result['reason'], 'store_locked')

    def test_unsupported_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            empty = Path(directory) / 'empty.db'
            with closing(sqlite3.connect(empty)) as db:
                db.execute('CREATE TABLE unrelated (id TEXT)')
                db.commit()
            self.assertEqual(OpenCodeProvider(empty).read()['reason'],
                             'unsupported_schema')
            narrow = Path(directory) / 'narrow.db'
            with closing(sqlite3.connect(narrow)) as db:
                db.execute('CREATE TABLE session (id TEXT, cost REAL)')
                db.commit()
            self.assertEqual(OpenCodeProvider(narrow).read()['reason'],
                             'unsupported_schema')


class ScopeAccountingTests(unittest.TestCase):
    def test_conversation_scope_sums_raw_categories_only(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write_store(Path(directory) / 'open.db', [
                make_session('ses_1', tokens=(100, 20, 5, 400, 0), cost=0.05),
                make_session('ses_2', tokens=(7, 7, 7, 7, 7), cost=0.01)])
            result = OpenCodeProvider(path).read(pinned='ses_1')
        self.assertTrue(result['available'])
        self.assertEqual(result['status'], '')
        self.assertEqual(result['tokens'],
                         dict(input=100, output=20, reasoning=5,
                              cache_read=400, cache_write=0, total=None))
        # No verified total formula: categories are never added together.
        self.assertIsNone(result['tokens']['total'])
        self.assertEqual(result['cost']['amount'], 0.05)
        self.assertIsNone(result['cost']['currency'])
        self.assertEqual(result['cost']['coverage'], 'recorded')
        self.assertFalse(result['partial'])
        self.assertIsNone(result['working_context'])
        self.assertIsNone(result['quotas'])
        self.assertIsNotNone(result['last_success_at'])
        identity = result['identity']
        self.assertEqual(identity['session_id'], 'opencode:ses_1')
        self.assertEqual(identity['project_id'], 'opencode:proj-a')

    def test_scoped_pinned_prefix_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write_store(Path(directory) / 'open.db',
                               [make_session('ses_1')])
            result = OpenCodeProvider(path).read(pinned='opencode:ses_1')
        self.assertTrue(result['available'])
        self.assertEqual(result['identity']['session_id'], 'opencode:ses_1')

    def test_unknown_session_unavailable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write_store(Path(directory) / 'open.db',
                               [make_session('ses_1')])
            result = OpenCodeProvider(path).read(pinned='ses_ghost')
        self.assertFalse(result['available'])
        self.assertEqual(result['reason'], 'session_not_found')

    def test_project_scope_groups_by_id_not_basename(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write_store(Path(directory) / 'open.db', [
                make_session('ses_1', project='proj-a',
                             directory='/synthetic/shared', tokens=(10, 1, 1, 1, 0)),
                make_session('ses_2', project='proj-b',
                             directory='/synthetic/shared', tokens=(20, 2, 2, 2, 0)),
                make_session('ses_3', project='proj-a',
                             directory='/synthetic/other', tokens=(30, 3, 3, 3, 0))])
            result = OpenCodeProvider(path).read(pinned='ses_1', scope='project')
        # Same basename (shared) but different project_id is excluded; the
        # same project_id under another directory is included.
        self.assertEqual(result['tokens']['input'], 40)
        self.assertEqual(result['scope_result']['count'], 2)
        self.assertEqual(result['identity']['project_id'], 'opencode:proj-a')

    def test_global_scope_sums_all_projects(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write_store(Path(directory) / 'open.db', [
                make_session('ses_1', project='proj-a', tokens=(10, 0, 0, 0, 0)),
                make_session('ses_2', project='proj-b', tokens=(20, 0, 0, 0, 0))])
            result = OpenCodeProvider(path).read(scope='global')
        self.assertEqual(result['tokens']['input'], 30)
        self.assertEqual(result['scope_result']['count'], 2)

    def test_nullable_vs_real_zero(self):
        null_row = make_session('ses_null', tokens=(50, 5, 1, 9, None), cost=None)
        zero_row = make_session('ses_zero', tokens=(50, 5, 1, 9, 0), cost=0.0)
        with tempfile.TemporaryDirectory() as directory:
            path = write_store(Path(directory) / 'open.db', [null_row, zero_row])
            result = OpenCodeProvider(path).read(scope='global')
        # NULL cache_write stays unknown with partial coverage; the scope
        # still reports the known subtotal, never a zero-filled complete sum.
        self.assertEqual(result['tokens']['cache_write'], 0)
        self.assertEqual(result['payload']['coverage']['cache_write'], 'partial')
        self.assertTrue(result['partial'])
        self.assertIn('cache_write_incomplete', result['notes'])
        # A recorded 0.0 cost is a real zero and counts as recorded.
        self.assertEqual(result['cost']['amount'], 0.0)
        self.assertEqual(result['cost']['recorded_sessions'], 1)
        self.assertEqual(result['cost']['coverage'], 'partial')
        self.assertEqual(result['tokens']['input'], 100)
        self.assertEqual(result['payload']['coverage']['input'], 'complete')

    def test_message_costs_never_summed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write_store(
                Path(directory) / 'open.db', [make_session('ses_1', cost=0.25)],
                [make_message('msg_1', 'ses_1', cost=999)])
            result = OpenCodeProvider(path).read(pinned='ses_1')
        self.assertEqual(result['cost']['amount'], 0.25)

    def test_arbitrary_and_malformed_models(self):
        weird = json.dumps({'id': 'id/with spaces:odd', 'providerID': 'p',
                            'variant': 'x\nhigh'})
        rows = [make_session('ses_weird', model=weird),
                make_session('ses_broken', model='{not json'),
                make_session('ses_empty', model='')]
        with tempfile.TemporaryDirectory() as directory:
            path = write_store(Path(directory) / 'open.db', rows)
            result = OpenCodeProvider(path).read(
                scope='global', include_history=True)
        by_id = {s['session_id']: s
                 for s in result['payload']['history']['sessions']}
        self.assertEqual(by_id['opencode:ses_weird']['model'],
                         dict(id='id/with spaces:odd', provider='p',
                              variant='x\nhigh'))
        self.assertIsNone(by_id['opencode:ses_broken']['model'])
        self.assertIsNone(by_id['opencode:ses_empty']['model'])
        # Malformed models never drop the session's accounted tokens.
        self.assertEqual(result['tokens']['input'], 300)

    def test_project_display_never_invents_identity(self):
        rows = [make_session('ses_1', project='proj-a',
                             directory='/synthetic/alpha'),
                make_session('ses_2', project='proj-b', directory='')]
        with tempfile.TemporaryDirectory() as directory:
            path = write_store(Path(directory) / 'open.db', rows)
            provider = OpenCodeProvider(path)
            named = provider.read(pinned='ses_1', scope='project')
            blank = provider.read(pinned='ses_2', scope='project')
        self.assertEqual(named['identity']['project_id'], 'opencode:proj-a')
        self.assertEqual(named['identity']['project_name'], 'alpha')
        self.assertEqual(blank['identity']['project_id'], 'opencode:proj-b')
        self.assertIsNone(blank['identity']['project_name'])


class RevisionForkTests(unittest.TestCase):
    def test_fork_chain_counted_once_each_and_idempotent(self):
        rows = [make_session('ses_parent', tokens=(100, 10, 1, 50, 0),
                             updated=BASE_MS + 1000),
                make_session('ses_child', parent='ses_parent',
                             tokens=(40, 4, 1, 8, 0), updated=BASE_MS + 2000),
                make_session('ses_grandchild', parent='ses_child',
                             tokens=(5, 5, 5, 5, 5), updated=BASE_MS + 3000)]
        with tempfile.TemporaryDirectory() as directory:
            path = write_store(Path(directory) / 'open.db', rows)
            provider = OpenCodeProvider(path)
            first = provider.read(scope='global')
            second = provider.read(scope='global')
            # Own-session rollups add once each; fork links need no exclusion.
            self.assertEqual(first['tokens']['input'], 145)
            self.assertEqual(first['scope_result']['count'], 3)
            self.assertEqual(first['tokens'], second['tokens'])
            self.assertEqual(first['payload']['sessions'],
                             second['payload']['sessions'])
            history = first['payload']
            self.assertIsNone(history['history'])  # history off by default
            detailed = provider.read(scope='global', include_history=True)
            links = {s['session_id']: s['parent_id'] for s in
                     detailed['payload']['history']['sessions']}
            self.assertEqual(links['opencode:ses_child'], 'opencode:ses_parent')
            self.assertEqual(links['opencode:ses_grandchild'],
                             'opencode:ses_child')
            self.assertIsNone(links['opencode:ses_parent'])

    def test_revisions_replace_without_double_counting(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write_store(Path(directory) / 'open.db',
                               [make_session('ses_1', tokens=(100, 0, 0, 0, 0),
                                             cost=0.10, updated=BASE_MS + 1000)])
            provider = OpenCodeProvider(path)
            before = provider.read(pinned='ses_1')
            self.assertEqual(before['tokens']['input'], 100)
            with closing(sqlite3.connect(path)) as db:
                db.execute('UPDATE session SET tokens_input=160, cost=0.16,'
                           ' time_updated=? WHERE id=?',
                           (BASE_MS + 2000, 'ses_1'))
                db.commit()
            refreshed = provider.refresh()
            after = provider.read(pinned='ses_1')
        self.assertGreaterEqual(refreshed['revised'], 1)
        self.assertEqual(after['tokens']['input'], 160)
        self.assertEqual(after['cost']['amount'], 0.16)
        self.assertEqual(after['scope_result']['count'], 1)

    def test_store_replacement_resyncs(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'open.db'
            write_store(path, [make_session('ses_1', tokens=(100, 0, 0, 0, 0)),
                               make_session('ses_2', tokens=(200, 0, 0, 0, 0))])
            provider = OpenCodeProvider(path)
            self.assertEqual(provider.read(scope='global')['tokens']['input'],
                             300)
            write_store(path, [make_session('ses_9', tokens=(7, 0, 0, 0, 0))])
            replaced = provider.read(scope='global')
        self.assertEqual(replaced['tokens']['input'], 7)
        self.assertEqual(replaced['scope_result']['count'], 1)


class TimestampHistoryTests(unittest.TestCase):
    def test_activity_timestamp_and_daily_calendar(self):
        midnight = datetime.combine(datetime.now().date(),
                                    datetime.min.time())
        midnight_ms = int(midnight.timestamp() * 1000)
        yesterday = _local_day_for(midnight_ms - 1000)
        today = _local_day_for(midnight_ms + 3600000)
        sessions = [make_session('ses_1', updated=BASE_MS + 5000)]
        messages = [make_message('msg_a', 'ses_1', created=midnight_ms - 1000,
                                 role='user',
                                 tokens={'input': 11, 'output': 0,
                                         'reasoning': 0,
                                         'cache': {'read': 0, 'write': 0}}),
                    make_message('msg_b', 'ses_1',
                                 created=midnight_ms + 3600000,
                                 role='assistant',
                                 tokens={'input': 22, 'output': 3,
                                         'reasoning': 0,
                                         'cache': {'read': 5, 'write': 0}})]
        with tempfile.TemporaryDirectory() as directory:
            path = write_store(Path(directory) / 'open.db', sessions,
                               messages)
            result = OpenCodeProvider(path).read(pinned='ses_1',
                                                 include_history=True)
        self.assertEqual(result['payload']['last_activity_at'], BASE_MS + 5000)
        self.assertEqual(result['source_event_at'], (BASE_MS + 5000) / 1000)
        daily = result['payload']['history']['daily']
        self.assertEqual(set(daily), {yesterday, today})
        self.assertEqual(daily[yesterday]['input'], 11)
        self.assertEqual(daily[yesterday]['user_messages'], 1)
        self.assertEqual(daily[today]['input'], 22)
        self.assertEqual(daily[today]['cache_read'], 5)
        self.assertFalse(result['partial'])

    def test_session_totals_only_daily_unavailable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write_store(Path(directory) / 'open.db',
                               [make_session('ses_1')],
                               with_message_table=False)
            result = OpenCodeProvider(path).read(pinned='ses_1',
                                                 include_history=True)
        history = result['payload']['history']
        self.assertEqual(len(history['sessions']), 1)
        self.assertIsNone(history['daily'])
        self.assertIn('daily_unavailable', result['notes'])
        self.assertTrue(result['partial'])

    def test_malformed_message_rows_skipped(self):
        good = make_message('msg_ok', 'ses_1')
        broken = dict(id='msg_bad', session_id='ses_1',
                      time_created=BASE_MS, time_updated=BASE_MS,
                      data=json.dumps(dict(role='assistant', cost=1,
                                           tokens='{{{bad',
                                           time={'created': BASE_MS})))
        timeless = dict(id='msg_old', session_id='ses_1',
                        time_created=None, time_updated=BASE_MS,
                        data=json.dumps(dict(
                            role='assistant', cost=1,
                            tokens=json.dumps({'input': 1, 'output': 0,
                                               'reasoning': 0,
                                               'cache': {'read': 0,
                                                         'write': 0}}),
                            time={'created': BASE_MS})))
        with tempfile.TemporaryDirectory() as directory:
            path = write_store(Path(directory) / 'open.db',
                               [make_session('ses_1')], [good, broken, timeless])
            result = OpenCodeProvider(path).read(pinned='ses_1',
                                                 include_history=True)
        history = result['payload']['history']
        self.assertEqual(history['skipped_message_rows'], 2)
        self.assertIn('message_rows_skipped', result['notes'])
        total_inputs = sum(day['input'] for day in history['daily'].values())
        self.assertEqual(total_inputs, 10)


def _local_day_for(milliseconds):
    return datetime.fromtimestamp(milliseconds / 1000).date().isoformat()


class ProviderIsolationTests(unittest.TestCase):
    def test_same_raw_ids_stay_provider_scoped(self):
        import tests.test_providers as codex_fixture
        with tempfile.TemporaryDirectory() as directory:
            home = codex_fixture.write_home(directory, [{'id': 'ses_shared'}])
            codex = CodexProvider(CodexStore(home)).read(
                pinned='ses_shared', scope='conversation')
            path = write_store(Path(directory) / 'open.db',
                               [make_session('ses_shared', tokens=(3, 3, 3, 3, 3))])
            opencode = OpenCodeProvider(path).read(pinned='ses_shared')
        self.assertEqual(codex['provider_id'], 'codex')
        self.assertEqual(opencode['provider_id'], 'opencode')
        self.assertNotEqual(codex['identity'], opencode['identity'])
        self.assertEqual(opencode['identity']['session_id'],
                         'opencode:ses_shared')
        # No shared assumed token schema: Codex-derived fields never leak in.
        for leaked in ('input_tokens', 'cached_input_tokens',
                       'uncached_input_tokens', 'non_reasoning_output_tokens',
                       'total_tokens'):
            self.assertNotIn(leaked, opencode['tokens'])
        self.assertNotIn('total_tokens', opencode['payload']['coverage'])
        self.assertEqual(scoped_session_id('ses_shared'), 'opencode:ses_shared')
        self.assertEqual(scoped_project_id('proj-a'), 'opencode:proj-a')

    def test_capability_lookup_matches_adapter(self):
        provider = OpenCodeProvider(Path('absent.db'))
        self.assertEqual(provider.capabilities, OPENCODE_CAPABILITIES)
        for capability in OPENCODE_CAPABILITIES:
            self.assertTrue(is_supported('opencode', capability), capability)
        for denied in ('quotas', 'working_context', 'cost_estimate',
                       'cost_currency', 'completion', 'telepathy'):
            self.assertFalse(is_supported('opencode', denied), denied)
        self.assertTrue(is_supported('codex', 'scopes'))
        self.assertFalse(is_supported('future', 'scopes'))
        self.assertLessEqual(DB_TIMEOUT_S, 0.25)

    def test_no_activity_or_quotas_claimed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write_store(Path(directory) / 'open.db',
                               [make_session('ses_1')])
            result = OpenCodeProvider(path).read(
                pinned='ses_1', active_title='Task Window')
        self.assertIsNone(result['working_context'])
        self.assertIsNone(result['quotas'])
        self.assertNotIn('working_context', OPENCODE_CAPABILITIES)
        self.assertNotIn('quotas', OPENCODE_CAPABILITIES)

    def test_model_and_token_parsers_reject_gracefully(self):
        self.assertIsNone(parse_model('{bad'))
        self.assertIsNone(parse_model(None))
        self.assertIsNone(parse_model('42'))
        self.assertIsNone(parse_message_tokens('{{{'))
        self.assertIsNone(parse_message_tokens(None))
        self.assertIsNone(parse_message_tokens(json.dumps({'input': 'many'})))
        # Booleans, negatives and non-finite numbers invalidate the row;
        # missing keys stay unknown without killing the row.
        self.assertIsNone(parse_message_tokens(json.dumps({'input': True})))
        self.assertIsNone(parse_message_tokens(json.dumps({'input': -1})))
        self.assertIsNone(parse_message_tokens(json.dumps(
            {'input': float('inf')})))
        self.assertIsNone(parse_message_tokens(json.dumps(
            {'input': float('nan')})))
        sparse = parse_message_tokens(json.dumps({'input': 5}))
        self.assertEqual(sparse['input'], 5)
        self.assertIsNone(sparse['output'])
        parsed = parse_message_tokens(json.dumps(
            {'input': 1, 'output': 2, 'reasoning': 3,
             'cache': {'read': 4, 'write': 5}}))
        self.assertEqual(parsed, dict(input=1, output=2, reasoning=3,
                                      cache_read=4, cache_write=5))
        self.assertEqual(parse_model(json.dumps(
            {'id': 'm', 'providerID': 'p', 'variant': 'v'})),
            dict(id='m', provider='p', variant='v'))


class UnknownZeroCoverageTests(unittest.TestCase):
    def test_all_missing_tokens_stay_unknown(self):
        row = make_session('ses_none', tokens=(None, None, None, None, None),
                           cost=None)
        with tempfile.TemporaryDirectory() as directory:
            path = write_store(Path(directory) / 'open.db', [row])
            result = OpenCodeProvider(path).read(pinned='ses_none')
        # A known row with unknown values is available but never zero.
        self.assertTrue(result['available'])
        for category in ('input', 'output', 'reasoning', 'cache_read',
                         'cache_write'):
            self.assertIsNone(result['tokens'][category])
            self.assertEqual(result['payload']['coverage'][category],
                             'unknown')
        self.assertIsNone(result['cost']['amount'])
        self.assertEqual(result['cost']['coverage'], 'unknown')
        self.assertTrue(result['partial'])
        self.assertIn('input_unknown', result['notes'])

    def test_real_zero_stays_complete_zero(self):
        row = make_session('ses_zero', tokens=(0, 0, 0, 0, 0), cost=0.0)
        with tempfile.TemporaryDirectory() as directory:
            path = write_store(Path(directory) / 'open.db', [row])
            result = OpenCodeProvider(path).read(pinned='ses_zero')
        self.assertEqual(result['tokens'],
                         dict(input=0, output=0, reasoning=0, cache_read=0,
                              cache_write=0, total=None))
        for category in ('input', 'output', 'reasoning', 'cache_read',
                         'cache_write'):
            self.assertEqual(result['payload']['coverage'][category],
                             'complete')
        self.assertEqual(result['cost']['amount'], 0.0)
        self.assertFalse(result['partial'])

    def test_daily_coverage_unknown_partial_complete(self):
        gap = 72 * 3600 * 1000  # immune to single DST transitions
        sessions = [make_session('ses_1')]
        messages = [
            make_message('msg_null', 'ses_1', created=BASE_MS,
                         tokens={'input': None, 'output': None,
                                 'reasoning': None,
                                 'cache': {'read': None, 'write': None}}),
            make_message('msg_full', 'ses_1', created=BASE_MS + gap,
                         tokens={'input': 8, 'output': 2, 'reasoning': 1,
                                 'cache': {'read': 3, 'write': 0}}),
            make_message('msg_half', 'ses_1', created=BASE_MS + gap,
                         tokens={'input': 4, 'output': None, 'reasoning': 0,
                                 'cache': {'read': 1, 'write': None}}),
            make_message('msg_pure', 'ses_1', created=BASE_MS + 2 * gap,
                         tokens={'input': 5, 'output': 5, 'reasoning': 5,
                                 'cache': {'read': 5, 'write': 5}}),
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = write_store(Path(directory) / 'open.db', sessions,
                               messages)
            result = OpenCodeProvider(path).read(pinned='ses_1',
                                                 include_history=True)
        history = result['payload']['history']
        keys = sorted(history['daily'])
        self.assertEqual(len(keys), 3)
        null_day, mixed_day, full_day = (history['daily'][k] for k in keys)
        null_cov, mixed_cov, full_cov = (
            history['daily_coverage'][k] for k in keys)
        self.assertIsNone(null_day['input'])
        self.assertEqual(null_cov['input'], 'unknown')
        self.assertEqual(mixed_day['input'], 12)
        self.assertEqual(mixed_cov['input'], 'complete')
        self.assertEqual(mixed_day['output'], 2)
        self.assertEqual(mixed_cov['output'], 'partial')
        self.assertEqual(full_day['cache_write'], 5)
        self.assertEqual(full_cov['cache_write'], 'complete')
        self.assertTrue(result['partial'])


class ReplacementRevisionTests(unittest.TestCase):
    def test_same_id_replacement_with_older_timestamps(self):
        # Astra repro: same session ID, older watermark, same-or-larger
        # store must serve the NEW values, never the cached ones.
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'open.db'
            write_store(path, [make_session('ses_1', tokens=(100, 0, 0, 0, 0),
                                            cost=0.5, updated=BASE_MS + 9000)])
            provider = OpenCodeProvider(path)
            self.assertEqual(provider.read(pinned='ses_1')['tokens']['input'],
                             100)
            write_store(path, [make_session('ses_1', tokens=(7, 1, 1, 1, 1),
                                            cost=0.07,
                                            created=BASE_MS,
                                            updated=BASE_MS + 1000)])
            replaced = provider.read(pinned='ses_1')
        self.assertEqual(replaced['tokens']['input'], 7)
        self.assertEqual(replaced['cost']['amount'], 0.07)
        self.assertEqual(replaced['scope_result']['count'], 1)

    def test_larger_replacement_with_stale_timestamps(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'open.db'
            write_store(path, [make_session('ses_1', tokens=(100, 0, 0, 0, 0),
                                            updated=BASE_MS + 9000)])
            provider = OpenCodeProvider(path)
            provider.read(scope='global')
            write_store(path, [
                make_session('ses_a', tokens=(1, 0, 0, 0, 0),
                             updated=BASE_MS + 1000),
                make_session('ses_b', tokens=(2, 0, 0, 0, 0),
                             updated=BASE_MS + 1000),
                make_session('ses_c', tokens=(3, 0, 0, 0, 0),
                             updated=BASE_MS + 1000)])
            grown = provider.read(scope='global')
        self.assertEqual(grown['tokens']['input'], 6)
        self.assertEqual(grown['scope_result']['count'], 3)

    def test_timestamp_rollback_picked_up(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write_store(Path(directory) / 'open.db',
                               [make_session('ses_1', tokens=(100, 0, 0, 0, 0),
                                             updated=BASE_MS + 9000)])
            provider = OpenCodeProvider(path)
            provider.read(pinned='ses_1')
            with closing(sqlite3.connect(path)) as db:
                db.execute('UPDATE session SET tokens_input=33,'
                           ' time_updated=? WHERE id=?',
                           (BASE_MS + 1000, 'ses_1'))
                db.commit()
            rolled = provider.read(pinned='ses_1')
        self.assertEqual(rolled['tokens']['input'], 33)
        self.assertEqual(rolled['scope_result']['count'], 1)

    def test_deleted_session_pruned(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write_store(Path(directory) / 'open.db', [
                make_session('ses_1', tokens=(10, 0, 0, 0, 0)),
                make_session('ses_2', tokens=(20, 0, 0, 0, 0))])
            provider = OpenCodeProvider(path)
            self.assertEqual(provider.read(scope='global')['tokens']['input'],
                             30)
            with closing(sqlite3.connect(path)) as db:
                db.execute("DELETE FROM session WHERE id='ses_2'")
                db.commit()
            pruned = provider.read(scope='global')
            gone = provider.read(pinned='ses_2')
        self.assertEqual(pruned['tokens']['input'], 10)
        self.assertEqual(pruned['scope_result']['count'], 1)
        self.assertEqual(gone['reason'], 'session_not_found')


class CorruptFieldTests(unittest.TestCase):
    def test_text_in_token_column_rejected(self):
        row = make_session('ses_text', tokens=(100, 20, 5, 400, 0))
        row['tokens_input'] = 'many'  # SQLite keeps unconvertible TEXT as-is
        with tempfile.TemporaryDirectory() as directory:
            path = write_store(Path(directory) / 'open.db', [row])
            result = OpenCodeProvider(path).read(pinned='ses_text')
        self.assertIsNone(result['tokens']['input'])
        self.assertEqual(result['payload']['coverage']['input'], 'unknown')
        self.assertIn('input_unknown', result['notes'])
        self.assertEqual(result['tokens']['output'], 20)
        self.assertIn('invalid_values_rejected', result['notes'])
        self.assertTrue(result['partial'])

    def test_bad_cost_and_timestamps_guarded(self):
        rows = [make_session('ses_bad', tokens=(10, 1, 1, 1, 1), cost='free',
                             created=10 ** 18, updated='yesterday'),
                make_session('ses_good', tokens=(5, 1, 1, 1, 1), cost=0.02,
                             updated=BASE_MS + 2000)]
        with tempfile.TemporaryDirectory() as directory:
            path = write_store(Path(directory) / 'open.db', rows)
            result = OpenCodeProvider(path).read(scope='global')
        # Corrupt cost is unknown (never zero); corrupt timestamps never
        # break the cursor or activity ranking.
        self.assertEqual(result['cost']['amount'], 0.02)
        self.assertEqual(result['cost']['coverage'], 'partial')
        self.assertEqual(result['payload']['last_activity_at'], BASE_MS + 2000)
        self.assertEqual(result['tokens']['input'], 15)
        self.assertIn('invalid_values_rejected', result['notes'])

    def test_out_of_range_message_timestamp_skipped(self):
        messages = [make_message('msg_bad', 'ses_1', created=10 ** 18),
                    make_message('msg_ok', 'ses_1', created=BASE_MS)]
        with tempfile.TemporaryDirectory() as directory:
            path = write_store(Path(directory) / 'open.db',
                               [make_session('ses_1')], messages)
            result = OpenCodeProvider(path).read(pinned='ses_1',
                                                 include_history=True)
        history = result['payload']['history']
        self.assertEqual(history['skipped_message_rows'], 1)
        total = sum(day['input'] for day in history['daily'].values())
        self.assertEqual(total, 10)

    def test_invalid_json_numbers_skipped(self):
        def raw_data(tokens_literal):
            return json.dumps(dict(role='assistant', cost=1,
                                   tokens=tokens_literal,
                                   time={'created': BASE_MS}))

        messages = [make_message('msg_ok', 'ses_1')]
        messages.append(dict(id='msg_inf', session_id='ses_1',
                             time_created=BASE_MS, time_updated=BASE_MS,
                             data=raw_data(json.dumps(float('inf')))))
        messages.append(dict(id='msg_neg', session_id='ses_1',
                             time_created=BASE_MS, time_updated=BASE_MS,
                             data=raw_data(json.dumps({'input': -2}))))
        messages.append(dict(id='msg_bool', session_id='ses_1',
                             time_created=BASE_MS, time_updated=BASE_MS,
                             data=raw_data(json.dumps({'input': True}))))
        with tempfile.TemporaryDirectory() as directory:
            path = write_store(Path(directory) / 'open.db',
                               [make_session('ses_1')], messages)
            result = OpenCodeProvider(path).read(pinned='ses_1',
                                                 include_history=True)
        history = result['payload']['history']
        self.assertEqual(history['skipped_message_rows'], 3)
        total = sum(day['input'] for day in history['daily'].values())
        self.assertEqual(total, 10)


class HistoryCacheTests(unittest.TestCase):
    def test_unchanged_history_reads_use_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write_store(Path(directory) / 'open.db',
                               [make_session('ses_1')],
                               [make_message('msg_1', 'ses_1')])
            provider = OpenCodeProvider(path)
            first = provider.read(pinned='ses_1', include_history=True)
            second = provider.read(pinned='ses_1', include_history=True)
        self.assertEqual(provider.history_scans, 1)
        self.assertFalse(first['payload']['history']['cached'])
        self.assertTrue(second['payload']['history']['cached'])
        self.assertIsNotNone(first['payload']['history']['as_of'])
        self.assertEqual(first['payload']['history']['daily'],
                         second['payload']['history']['daily'])

    def test_message_revision_marks_pending_until_floor(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write_store(Path(directory) / 'open.db',
                               [make_session('ses_1')],
                               [make_message('msg_1', 'ses_1')])
            provider = OpenCodeProvider(path)
            first = provider.read(pinned='ses_1', include_history=True)
            with closing(sqlite3.connect(path)) as db:
                db.execute('UPDATE message SET data=?, time_updated=?'
                           ' WHERE id=?',
                           (make_message('msg_1', 'ses_1',
                                         tokens={'input': 50, 'output': 0,
                                                 'reasoning': 0,
                                                 'cache': {'read': 0,
                                                           'write': 0}})['data'],
                            BASE_MS + 777, 'msg_1'))
                db.commit()
            # Change recorded but floor fresh: stale cache serves, as_of kept.
            pending = provider.read(pinned='ses_1', include_history=True)
            self.assertEqual(provider.history_scans, 1)
            pending_history = pending['payload']['history']
            self.assertTrue(pending_history['cached'])
            self.assertTrue(pending_history['refresh_pending'])
            self.assertIn('history_refresh_pending', pending['notes'])
            self.assertEqual(pending_history['as_of'],
                             first['payload']['history']['as_of'])
            stale_total = sum(day['input']
                              for day in pending_history['daily'].values())
            self.assertEqual(stale_total, 10)
            # Floor elapsed: exactly one rescan with recomputed totals.
            key = ('conversation', 'ses_1')
            provider._history_cache[key]['scanned_at'] -= 31
            revised = provider.read(pinned='ses_1', include_history=True)
            self.assertEqual(provider.history_scans, 2)
            fresh_history = revised['payload']['history']
            self.assertFalse(fresh_history['refresh_pending'])
            total = sum(day['input']
                        for day in fresh_history['daily'].values())
            # Recomputed from scratch: the new value, never old + new.
            self.assertEqual(total, 50)

    def test_message_deletion_marks_pending_until_floor(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write_store(Path(directory) / 'open.db',
                               [make_session('ses_1')],
                               [make_message('msg_1', 'ses_1'),
                                make_message('msg_2', 'ses_1')])
            provider = OpenCodeProvider(path)
            provider.read(pinned='ses_1', include_history=True)
            with closing(sqlite3.connect(path)) as db:
                db.execute("DELETE FROM message WHERE id='msg_2'")
                db.commit()
            pending = provider.read(pinned='ses_1', include_history=True)
            self.assertEqual(provider.history_scans, 1)
            self.assertTrue(pending['payload']['history']['refresh_pending'])
            key = ('conversation', 'ses_1')
            provider._history_cache[key]['scanned_at'] -= 31
            pruned = provider.read(pinned='ses_1', include_history=True)
        self.assertEqual(provider.history_scans, 2)
        total = sum(day['input']
                    for day in pruned['payload']['history']['daily'].values())
        self.assertEqual(total, 10)

    def test_floor_expiry_without_change_does_not_rescan(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write_store(Path(directory) / 'open.db',
                               [make_session('ses_1')],
                               [make_message('msg_1', 'ses_1')])
            provider = OpenCodeProvider(path)
            provider.read(pinned='ses_1', include_history=True)
            key = ('conversation', 'ses_1')
            provider._history_cache[key]['scanned_at'] -= 31
            quiet = provider.read(pinned='ses_1', include_history=True)
        # The floor is an upper bound, not a mandate: unchanged data is
        # never rescanned wastefully.
        self.assertEqual(provider.history_scans, 1)
        self.assertTrue(quiet['payload']['history']['cached'])
        self.assertFalse(quiet['payload']['history']['refresh_pending'])

    def test_continuous_writes_scan_once_until_floor(self):
        # Reviewer repro: successive revisions must not produce a scan
        # each; changes coalesce into one pending rescan after the floor.
        with tempfile.TemporaryDirectory() as directory:
            path = write_store(Path(directory) / 'open.db',
                               [make_session('ses_1')],
                               [make_message('msg_1', 'ses_1')])
            provider = OpenCodeProvider(path)
            first = provider.read(pinned='ses_1', include_history=True)
            first_as_of = first['payload']['history']['as_of']
            for step, value in enumerate((20, 30, 40)):
                with closing(sqlite3.connect(path)) as db:
                    db.execute('UPDATE message SET data=?, time_updated=?'
                               ' WHERE id=?',
                               (make_message('msg_1', 'ses_1',
                                             tokens={'input': value,
                                                     'output': 0,
                                                     'reasoning': 0,
                                                     'cache': {'read': 0,
                                                               'write': 0}}
                                             )['data'],
                                BASE_MS + 100 + step, 'msg_1'))
                    db.commit()
                burst = provider.read(pinned='ses_1', include_history=True)
                burst_history = burst['payload']['history']
                self.assertTrue(burst_history['cached'], step)
                self.assertTrue(burst_history['refresh_pending'], step)
                self.assertEqual(burst_history['as_of'], first_as_of, step)
            self.assertEqual(provider.history_scans, 1)
            key = ('conversation', 'ses_1')
            provider._history_cache[key]['scanned_at'] -= 31
            settled = provider.read(pinned='ses_1', include_history=True)
            self.assertEqual(provider.history_scans, 2)
            total = sum(day['input'] for day in
                        settled['payload']['history']['daily'].values())
            self.assertEqual(total, 40)
            self.assertFalse(
                settled['payload']['history']['refresh_pending'])

    def test_session_revision_marks_history_pending(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write_store(Path(directory) / 'open.db',
                               [make_session('ses_1', tokens=(100, 0, 0, 0, 0),
                                             cost=0.10,
                                             updated=BASE_MS + 1000)],
                               [make_message('msg_1', 'ses_1')])
            provider = OpenCodeProvider(path)
            provider.read(pinned='ses_1', include_history=True)
            with closing(sqlite3.connect(path)) as db:
                db.execute('UPDATE session SET tokens_input=160, cost=0.16,'
                           ' time_updated=? WHERE id=?',
                           (BASE_MS + 2000, 'ses_1'))
                db.commit()
            # Session rollups are exact immediately (fresh snapshot), but
            # history invalidation stays pending behind the floor.
            pending = provider.read(pinned='ses_1', include_history=True)
            self.assertEqual(pending['tokens']['input'], 160)
            self.assertEqual(provider.history_scans, 1)
            self.assertTrue(pending['payload']['history']['refresh_pending'])
            key = ('conversation', 'ses_1')
            provider._history_cache[key]['scanned_at'] -= 31
            settled = provider.read(pinned='ses_1', include_history=True)
            self.assertEqual(provider.history_scans, 2)
            self.assertFalse(
                settled['payload']['history']['refresh_pending'])


def enable_wal(path):
    with closing(sqlite3.connect(path)) as db:
        db.execute('PRAGMA journal_mode=WAL').fetchone()
        db.commit()
    return path


class WalWriterTests(unittest.TestCase):
    """Retained-writer probes: committed WAL frames (no checkpoint) must
    be visible, uncommitted writes must stay invisible."""

    def test_wal_update_visible_with_retained_writer(self):
        with tempfile.TemporaryDirectory() as directory:
            path = enable_wal(write_store(
                Path(directory) / 'open.db',
                [make_session('ses_1', tokens=(100, 0, 0, 0, 0),
                              updated=BASE_MS + 1000)]))
            provider = OpenCodeProvider(path)
            self.assertEqual(provider.read(pinned='ses_1')['tokens']['input'],
                             100)
            writer = sqlite3.connect(path, timeout=5)
            writer.execute('PRAGMA wal_autocheckpoint=0')
            try:
                writer.execute('UPDATE session SET tokens_input=7,'
                               ' time_updated=? WHERE id=?',
                               (BASE_MS + 2000, 'ses_1'))
                writer.commit()
                first = provider.read(pinned='ses_1')
                second = provider.read(pinned='ses_1')
            finally:
                writer.close()
            self.assertEqual(first['tokens']['input'], 7)
            self.assertEqual(second['tokens']['input'], 7)

    def test_wal_delete_visible_with_retained_writer(self):
        with tempfile.TemporaryDirectory() as directory:
            path = enable_wal(write_store(
                Path(directory) / 'open.db',
                [make_session('ses_1', tokens=(10, 0, 0, 0, 0)),
                 make_session('ses_2', tokens=(20, 0, 0, 0, 0))]))
            provider = OpenCodeProvider(path)
            writer = sqlite3.connect(path, timeout=5)
            writer.execute('PRAGMA wal_autocheckpoint=0')
            try:
                writer.execute("DELETE FROM session WHERE id='ses_2'")
                writer.commit()
                pruned = provider.read(scope='global')
            finally:
                writer.close()
            self.assertEqual(pruned['tokens']['input'], 10)
            self.assertEqual(pruned['scope_result']['count'], 1)

    def test_wal_uncommitted_invisible_then_rollback(self):
        with tempfile.TemporaryDirectory() as directory:
            path = enable_wal(write_store(
                Path(directory) / 'open.db',
                [make_session('ses_1', tokens=(100, 0, 0, 0, 0),
                              updated=BASE_MS + 1000)]))
            provider = OpenCodeProvider(path)
            writer = sqlite3.connect(path, timeout=5)
            writer.execute('PRAGMA wal_autocheckpoint=0')
            try:
                writer.execute('UPDATE session SET tokens_input=7'
                               ' WHERE id=?', ('ses_1',))
                uncommitted = provider.read(pinned='ses_1')
                writer.rollback()
                rolled_back = provider.read(pinned='ses_1')
                writer.execute('UPDATE session SET tokens_input=9'
                               ' WHERE id=?', ('ses_1',))
                writer.commit()
                committed = provider.read(pinned='ses_1')
            finally:
                writer.close()
            # Isolation: uncommitted and rolled-back writes never surface.
            self.assertEqual(uncommitted['tokens']['input'], 100)
            self.assertEqual(rolled_back['tokens']['input'], 100)
            self.assertEqual(committed['tokens']['input'], 9)


NOW_S = BASE_MS / 1000 + 100


class ActivitySnapshotTests(unittest.TestCase):
    def test_open_step_working(self):
        sessions = [make_session('ses_1', updated=BASE_MS)]
        parts = [make_part('p_start', 'ses_1', created=BASE_MS - 100000)]
        with tempfile.TemporaryDirectory() as directory:
            path = write_store(Path(directory) / 'open.db', sessions, (),
                               parts)
            snap = OpenCodeProvider(path).activity_snapshot(now=NOW_S)
        self.assertTrue(snap['valid'])
        self.assertTrue(snap['working'])
        self.assertEqual(snap['primary_session_id'], 'opencode:ses_1')
        self.assertEqual(snap['checked'], 1)
        self.assertEqual(snap['last_lifecycle_at'], BASE_MS - 100000)
        self.assertFalse(snap['evidence_unknown'])
        self.assertIn('expiry_s', snap['policy'])
        (entry,) = snap['sessions']
        self.assertTrue(entry['working'])
        self.assertEqual(entry['evidence'], 'open_step')
        self.assertAlmostEqual(entry['open_age_s'], 200.0)

    def test_expiry_boundary(self):
        sessions = [make_session('ses_fresh', updated=BASE_MS),
                    make_session('ses_old', updated=BASE_MS)]
        parts = [make_part('p1', 'ses_fresh', created=BASE_MS - 799000),
                 make_part('p2', 'ses_old', created=BASE_MS - 801000)]
        with tempfile.TemporaryDirectory() as directory:
            path = write_store(Path(directory) / 'open.db', sessions, (),
                               parts)
            snap = OpenCodeProvider(path).activity_snapshot(now=NOW_S)
        by_id = {e['session_id']: e for e in snap['sessions']}
        # Ages 899 s vs 901 s against the 900 s expiry.
        self.assertTrue(by_id['opencode:ses_fresh']['working'])
        self.assertFalse(by_id['opencode:ses_old']['working'])
        self.assertTrue(snap['working'])
        self.assertEqual(snap['primary_session_id'], 'opencode:ses_fresh')

    def test_step_gap_grace_then_idle(self):
        sessions = [make_session('ses_1', updated=BASE_MS)]
        parts = [make_part('p_start', 'ses_1', created=BASE_MS + 69000),
                 make_part('p_fin', 'ses_1', created=BASE_MS + 70000,
                           kind='step-finish', reason='tool-calls')]
        with tempfile.TemporaryDirectory() as directory:
            path = write_store(Path(directory) / 'open.db', sessions, (),
                               parts)
            provider = OpenCodeProvider(path)
            bridged = provider.activity_snapshot(now=NOW_S)
            later = provider.activity_snapshot(now=NOW_S + 31)
            provider.close()
        # Finish 30 s ago: bridged; 61 s ago: idle.
        self.assertTrue(bridged['working'])
        (entry,) = bridged['sessions']
        self.assertEqual(entry['evidence'], 'step_gap')
        self.assertEqual(entry['finish_reason'], 'tool-calls')
        self.assertFalse(later['working'])

    def test_stop_finish_bridged_not_completed(self):
        sessions = [make_session('ses_1', updated=BASE_MS)]
        parts = [make_part('p_start', 'ses_1', created=BASE_MS + 69000),
                 make_part('p_fin', 'ses_1', created=BASE_MS + 70000,
                           kind='step-finish', reason='stop')]
        with tempfile.TemporaryDirectory() as directory:
            path = write_store(Path(directory) / 'open.db', sessions, (),
                               parts)
            snap = OpenCodeProvider(path).activity_snapshot(now=NOW_S)
        # 'stop' does not prove session completion (live sessions start
        # new steps after stop finishes); the gap still bridges.
        self.assertTrue(snap['working'])

    def test_long_silent_tool_stays_working(self):
        sessions = [make_session('ses_1', updated=BASE_MS - 700000)]
        parts = [make_part('p_start', 'ses_1', created=BASE_MS - 700000)]
        with tempfile.TemporaryDirectory() as directory:
            path = write_store(Path(directory) / 'open.db', sessions, (),
                               parts)
            snap = OpenCodeProvider(path).activity_snapshot(now=NOW_S)
        # Open 800 s with zero writes since: fresh writes are evidence,
        # never a requirement.
        self.assertTrue(snap['working'])
        (entry,) = snap['sessions']
        self.assertAlmostEqual(entry['newest_part_age_s'], 800.0)

    def test_stale_abandonment_idle(self):
        ancient = BASE_MS - 3 * 86400000
        sessions = [make_session('ses_gone', updated=ancient),
                    make_session('ses_recent', updated=BASE_MS)]
        parts = [make_part('p_old', 'ses_gone', created=ancient),
                 make_part('p_new', 'ses_recent', created=ancient,
                           message_id='msg_2')]
        with tempfile.TemporaryDirectory() as directory:
            path = write_store(Path(directory) / 'open.db', sessions, (),
                               parts)
            snap = OpenCodeProvider(path).activity_snapshot(now=NOW_S)
        # Ancient row never probed; recent row with ancient open is expired.
        self.assertEqual(snap['checked'], 1)
        self.assertFalse(snap['working'])
        self.assertIsNone(snap['primary_session_id'])
        (entry,) = snap['sessions']
        self.assertEqual(entry['session_id'], 'opencode:ses_recent')
        self.assertGreater(entry['open_age_s'], 900)

    def test_missing_store_unknown_not_idle(self):
        with tempfile.TemporaryDirectory() as directory:
            snap = OpenCodeProvider(
                Path(directory) / 'absent.db').activity_snapshot(now=NOW_S)
        self.assertFalse(snap['valid'])
        self.assertFalse(snap['working'])
        self.assertEqual(snap['reason'], 'missing_store')
        self.assertIsNone(snap['last_lifecycle_at'])

    def test_locked_store_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write_store(Path(directory) / 'open.db',
                               [make_session('ses_1')])
            holder = sqlite3.connect(path, timeout=5)
            holder.execute('BEGIN EXCLUSIVE')
            try:
                snap = OpenCodeProvider(path).activity_snapshot(now=NOW_S)
            finally:
                holder.rollback()
                holder.close()
        self.assertFalse(snap['valid'])
        self.assertEqual(snap['reason'], 'store_locked')

    def test_missing_part_table_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write_store(Path(directory) / 'open.db',
                               [make_session('ses_1')], (),
                               with_part_table=False)
            snap = OpenCodeProvider(path).activity_snapshot(now=NOW_S)
        self.assertFalse(snap['valid'])
        self.assertEqual(snap['reason'], 'activity_unavailable')

    def test_last_lifecycle_at_is_max_and_primary_is_newest(self):
        sessions = [make_session('ses_a', updated=BASE_MS),
                    make_session('ses_b', updated=BASE_MS + 500)]
        parts = [make_part('p_a', 'ses_a', created=BASE_MS - 50000),
                 make_part('p_b', 'ses_b', created=BASE_MS - 10000)]
        with tempfile.TemporaryDirectory() as directory:
            path = write_store(Path(directory) / 'open.db', sessions, (),
                               parts)
            snap = OpenCodeProvider(path).activity_snapshot(now=NOW_S)
        # Attributable lifecycle instants only: row-update clocks never
        # feed recency, so the max comes from the observed starts.
        self.assertEqual(snap['last_lifecycle_at'], BASE_MS - 10000)
        self.assertEqual(snap['primary_session_id'], 'opencode:ses_b')
        self.assertEqual(snap['checked'], 2)

    def test_overlapping_messages_open_wins(self):
        # Reviewer scenario: message A open at age 200s while a later
        # message B already finished at age 100s. Session-wide MAX
        # comparison says idle; message-scoped pairing says working.
        sessions = [make_session('ses_1', updated=BASE_MS)]
        parts = [make_part('p_a', 'ses_1', created=BASE_MS,
                           message_id='msg_a'),
                 make_part('p_b1', 'ses_1', created=BASE_MS + 50000,
                           message_id='msg_b'),
                 make_part('p_b2', 'ses_1', created=BASE_MS + 90000,
                           kind='step-finish', reason='tool-calls',
                           message_id='msg_b')]
        with tempfile.TemporaryDirectory() as directory:
            path = write_store(Path(directory) / 'open.db', sessions, (),
                               parts)
            snap = OpenCodeProvider(path).activity_snapshot(now=NOW_S)
        self.assertTrue(snap['working'])
        (entry,) = snap['sessions']
        self.assertTrue(entry['working'])
        self.assertEqual(entry['evidence'], 'open_step')
        self.assertAlmostEqual(entry['open_age_s'], 100.0)
        self.assertFalse(entry['unknown'])

    def test_equal_timestamps_close(self):
        sessions = [make_session('ses_1', updated=BASE_MS)]
        parts = [make_part('p_start', 'ses_1', created=BASE_MS),
                 make_part('p_fin', 'ses_1', created=BASE_MS,
                           kind='step-finish', reason='stop')]
        with tempfile.TemporaryDirectory() as directory:
            path = write_store(Path(directory) / 'open.db', sessions, (),
                               parts)
            snap = OpenCodeProvider(path).activity_snapshot(now=NOW_S)
        # Start == finish closes the step (deterministic tie rule); the
        # finish itself is 100 s old, past grace.
        self.assertFalse(snap['working'])
        (entry,) = snap['sessions']
        self.assertEqual(entry['evidence'], 'idle')
        self.assertFalse(entry['unknown'])

    def test_text_timestamp_stays_unknown(self):
        sessions = [make_session('ses_1', updated=BASE_MS)]
        row = make_part('p_bad', 'ses_1', created=BASE_MS)
        row['time_created'] = 'soon'
        with tempfile.TemporaryDirectory() as directory:
            path = write_store(Path(directory) / 'open.db', sessions, (),
                               [row])
            snap = OpenCodeProvider(path).activity_snapshot(now=NOW_S)
        self.assertFalse(snap['working'])
        self.assertTrue(snap['evidence_unknown'])
        (entry,) = snap['sessions']
        self.assertTrue(entry['unknown'])
        self.assertFalse(entry['working'])

    def test_future_start_stays_unknown(self):
        future_ms = int(NOW_S * 1000) + 86400000
        sessions = [make_session('ses_1', updated=BASE_MS)]
        parts = [make_part('p_future', 'ses_1', created=future_ms)]
        with tempfile.TemporaryDirectory() as directory:
            path = write_store(Path(directory) / 'open.db', sessions, (),
                               parts)
            snap = OpenCodeProvider(path).activity_snapshot(now=NOW_S)
        # A negative age must never satisfy '< expiry': future evidence
        # is unknown, not working.
        self.assertFalse(snap['working'])
        self.assertTrue(snap['evidence_unknown'])
        (entry,) = snap['sessions']
        self.assertTrue(entry['unknown'])
        self.assertIsNone(entry['open_age_s'])

    def test_uncommitted_finish_stays_invisible(self):
        sessions = [make_session('ses_1', updated=BASE_MS)]
        parts = [make_part('p_start', 'ses_1', created=BASE_MS - 100000)]
        with tempfile.TemporaryDirectory() as directory:
            path = write_store(Path(directory) / 'open.db', sessions, (),
                               parts)
            provider = OpenCodeProvider(path)
            writer = sqlite3.connect(path, timeout=5)
            try:
                writer.execute(
                    'INSERT INTO part VALUES (?,?,?,?,?,?)',
                    ('p_fin', 'msg_1', 'ses_1', BASE_MS - 50000,
                     BASE_MS - 50000,
                     json.dumps({'type': 'step-finish',
                                 'reason': 'stop'})))
                during = provider.activity_snapshot(now=NOW_S)
                writer.rollback()
                after = provider.activity_snapshot(now=NOW_S)
            finally:
                writer.close()
            provider.close()
        self.assertTrue(during['working'])
        self.assertTrue(after['working'])

    def test_racing_commits_stay_structured(self):
        sessions = [make_session('ses_1', updated=BASE_MS)]
        parts = [make_part('p_start', 'ses_1', created=BASE_MS - 100000)]
        with tempfile.TemporaryDirectory() as directory:
            path = write_store(Path(directory) / 'open.db', sessions, (),
                               parts)
            provider = OpenCodeProvider(path)
            writer = sqlite3.connect(path, timeout=5)
            try:
                for i in range(30):
                    writer.execute(
                        'INSERT INTO part VALUES (?,?,?,?,?,?)',
                        (f't{i}', f'msg_tool_{i}', 'ses_1',
                         BASE_MS - 90000 + i, BASE_MS - 90000 + i,
                         json.dumps({'type': 'tool', 'tool': 'read',
                                     'callID': f'c{i}', 'state': 'done'})))
                    writer.commit()
                    snap = provider.activity_snapshot(now=NOW_S)
                    self.assertTrue(snap['valid'], i)
                    self.assertTrue(snap['working'], i)
                    for entry in snap['sessions']:
                        self.assertIsInstance(entry['working'], bool)
                        self.assertIsInstance(entry['unknown'], bool)
                        for key in ('open_age_s', 'finish_age_s',
                                    'newest_part_age_s'):
                            value = entry[key]
                            self.assertTrue(
                                value is None or value >= 0, (i, key))
            finally:
                writer.close()
            provider.close()

    def test_start_finish_start_leaves_latest_open(self):
        base = BASE_MS
        sessions = [make_session('ses_1', updated=base)]
        parts = [make_part('s1', 'ses_1', created=base - 300000),
                 make_part('f1', 'ses_1', created=base - 200000,
                           kind='step-finish', reason='tool-calls'),
                 make_part('s2', 'ses_1', created=base - 100000)]
        with tempfile.TemporaryDirectory() as directory:
            path = write_store(Path(directory) / 'open.db', sessions, (),
                               parts)
            snap = OpenCodeProvider(path).activity_snapshot(now=NOW_S)
        # MIN/MAX aggregation would compare first start to the finish
        # and report idle; the state machine keeps the latest open.
        self.assertTrue(snap['working'])
        (entry,) = snap['sessions']
        self.assertEqual(entry['evidence'], 'open_step')
        self.assertAlmostEqual(entry['open_age_s'], 200.0)
        self.assertFalse(entry['unknown'])

    def test_start_finish_start_finish_closes(self):
        base = BASE_MS
        sessions = [make_session('ses_1', updated=base)]
        parts = [make_part('s1', 'ses_1', created=base - 300000),
                 make_part('f1', 'ses_1', created=base - 200000,
                           kind='step-finish', reason='tool-calls'),
                 make_part('s2', 'ses_1', created=base - 190000),
                 make_part('f2', 'ses_1', created=base - 180000,
                           kind='step-finish', reason='stop')]
        with tempfile.TemporaryDirectory() as directory:
            path = write_store(Path(directory) / 'open.db', sessions, (),
                               parts)
            snap = OpenCodeProvider(path).activity_snapshot(now=NOW_S)
        self.assertFalse(snap['working'])
        (entry,) = snap['sessions']
        # Latest finish is 280 s old: past grace, correctly idle.
        self.assertEqual(entry['evidence'], 'idle')
        self.assertEqual(entry['finish_reason'], 'stop')
        self.assertAlmostEqual(entry['finish_age_s'], 280.0)

    def test_multiple_completed_steps_close_with_latest_reason(self):
        base = BASE_MS
        sessions = [make_session('ses_1', updated=base)]
        parts = [make_part('s1', 'ses_1', created=base - 50000,
                           message_id='msg_a'),
                 make_part('f1', 'ses_1', created=base - 40000,
                           kind='step-finish', reason='tool-calls',
                           message_id='msg_a'),
                 make_part('s2', 'ses_1', created=base - 30000,
                           message_id='msg_b'),
                 make_part('f2', 'ses_1', created=base - 20000,
                           kind='step-finish', reason='stop',
                           message_id='msg_b')]
        with tempfile.TemporaryDirectory() as directory:
            path = write_store(Path(directory) / 'open.db', sessions, (),
                               parts)
            snap = OpenCodeProvider(path).activity_snapshot(now=NOW_S)
        self.assertFalse(snap['working'])
        (entry,) = snap['sessions']
        self.assertEqual(entry['finish_reason'], 'stop')
        self.assertAlmostEqual(entry['finish_age_s'], 120.0)

    def test_malformed_start_with_valid_finish_stays_unknown(self):
        base = BASE_MS
        sessions = [make_session('ses_1', updated=base)]
        bad = make_part('s_bad', 'ses_1', created=base - 100000)
        bad['time_created'] = 'garbage'
        parts = [bad,
                 make_part('f_ok', 'ses_1', created=base - 50000,
                           kind='step-finish', reason='stop')]
        with tempfile.TemporaryDirectory() as directory:
            path = write_store(Path(directory) / 'open.db', sessions, (),
                               parts)
            snap = OpenCodeProvider(path).activity_snapshot(now=NOW_S)
        # Ambiguous pairing proves neither work nor idleness.
        self.assertFalse(snap['working'])
        self.assertTrue(snap['evidence_unknown'])
        (entry,) = snap['sessions']
        self.assertTrue(entry['unknown'])

    def test_future_finish_with_valid_start_stays_qualified(self):
        base = BASE_MS
        future_ms = int(NOW_S * 1000) + 3600000
        sessions = [make_session('ses_1', updated=base)]
        parts = [make_part('s_ok', 'ses_1', created=base - 100000),
                 make_part('f_future', 'ses_1', created=future_ms,
                           kind='step-finish', reason='stop')]
        with tempfile.TemporaryDirectory() as directory:
            path = write_store(Path(directory) / 'open.db', sessions, (),
                               parts)
            snap = OpenCodeProvider(path).activity_snapshot(now=NOW_S)
        # The future finish proves nothing and disqualifies nothing: the
        # valid fresh open still reports working, qualified by unknown.
        # (The reviewed bug was future times CREATING verdicts through
        # negative ages passing '< expiry' — impossible here.)
        self.assertTrue(snap['working'])
        self.assertTrue(snap['evidence_unknown'])
        (entry,) = snap['sessions']
        self.assertTrue(entry['working'])
        self.assertTrue(entry['unknown'])

    def test_stale_row_with_fresh_open_step_works(self):
        # Reviewer recall case: session.time_updated older than the
        # prefilter window, but a valid step-start only ~100 s old.
        # Must be working (or conservatively unknown) — never
        # confirmed idle because of the prefilter.
        stale_ms = BASE_MS - 7200000
        sessions = [make_session('ses_1', updated=stale_ms)]
        parts = [make_part('p_fresh', 'ses_1', created=BASE_MS)]
        with tempfile.TemporaryDirectory() as directory:
            path = write_store(Path(directory) / 'open.db', sessions, (),
                               parts)
            snap = OpenCodeProvider(path).activity_snapshot(now=NOW_S)
        self.assertTrue(snap['working'])
        self.assertEqual(snap['checked'], 1)
        (entry,) = snap['sessions']
        self.assertEqual(entry['session_id'], 'opencode:ses_1')
        self.assertFalse(entry['unknown'])

    def test_policy_record_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write_store(Path(directory) / 'open.db',
                               [make_session('ses_1')])
            snap = OpenCodeProvider(path).activity_snapshot(now=NOW_S)
        policy = snap['policy']
        self.assertEqual(
            (policy['expiry_s'], policy['grace_s'],
             policy['prefilter_margin_s']), (900, 60, 300))
        for key in ('basis', 'confidence', 'false_positives',
                    'false_negatives', 'recall_basis'):
            self.assertTrue(policy[key], key)


class ActivityProbeIncrementTests(unittest.TestCase):
    """The steady-state probe skips the full part scan while the log is
    unchanged, reusing the coherent projection with a fresh clock. Any
    new part write or session revision forces a rescan."""

    def _provider(self, directory, sessions, parts):
        path = write_store(Path(directory) / 'open.db', sessions, (),
                           parts)
        return OpenCodeProvider(path), path

    def test_unchanged_store_reuses_projection(self):
        sessions = [make_session('ses_1', updated=BASE_MS)]
        parts = [make_part('p_start', 'ses_1', created=BASE_MS - 100000)]
        with tempfile.TemporaryDirectory() as directory:
            provider, _ = self._provider(directory, sessions, parts)
            first = provider.activity_snapshot(now=NOW_S)
            second = provider.activity_snapshot(now=NOW_S)
            third = provider.activity_snapshot(now=NOW_S + 30)
            provider.close()
        self.assertTrue(first['working'])
        self.assertEqual(provider.activity_scans, 1)
        self.assertEqual(second, first)
        # A fresh clock still re-evaluates ages through the reused rows.
        self.assertTrue(third['working'])
        self.assertEqual(third['last_lifecycle_at'],
                         first['last_lifecycle_at'])

    def test_grace_expiry_visible_without_rescan(self):
        sessions = [make_session('ses_1', updated=BASE_MS)]
        parts = [make_part('p_start', 'ses_1', created=BASE_MS + 69000),
                 make_part('p_fin', 'ses_1', created=BASE_MS + 70000,
                           kind='step-finish', reason='tool-calls')]
        with tempfile.TemporaryDirectory() as directory:
            provider, _ = self._provider(directory, sessions, parts)
            bridged = provider.activity_snapshot(now=NOW_S)
            idle = provider.activity_snapshot(now=NOW_S + 61)
            provider.close()
        self.assertTrue(bridged['working'])
        self.assertFalse(idle['working'])
        self.assertEqual(provider.activity_scans, 1)

    def test_new_part_forces_rescan(self):
        sessions = [make_session('ses_1', updated=BASE_MS)]
        parts = [make_part('p1', 'ses_1', created=BASE_MS - 2000000,
                           kind='step-finish', reason='stop')]
        with tempfile.TemporaryDirectory() as directory:
            provider, path = self._provider(directory, sessions, parts)
            idle = provider.activity_snapshot(now=NOW_S)
            self.assertFalse(idle['working'])
            with closing(sqlite3.connect(path, timeout=5)) as db:
                db.execute(
                    'INSERT INTO part VALUES (?,?,?,?,?,?)',
                    ('p2', 'msg_1', 'ses_1', BASE_MS - 1000, BASE_MS - 1000,
                     json.dumps({'type': 'step-start'})))
                db.commit()
            working = provider.activity_snapshot(now=NOW_S)
            provider.close()
        self.assertTrue(working['working'])
        self.assertEqual(working['primary_session_id'], 'opencode:ses_1')
        self.assertEqual(provider.activity_scans, 2)

    def test_session_revision_forces_rescan(self):
        sessions = [make_session('ses_1', updated=BASE_MS)]
        with tempfile.TemporaryDirectory() as directory:
            provider, path = self._provider(directory, sessions, ())
            provider.activity_snapshot(now=NOW_S)
            with closing(sqlite3.connect(path, timeout=5)) as db:
                db.execute('UPDATE session SET time_updated=? WHERE id=?',
                           (BASE_MS + 5000, 'ses_1'))
                db.commit()
            provider.activity_snapshot(now=NOW_S)
            provider.close()
        self.assertEqual(provider.activity_scans, 2)

    def test_missing_part_table_stays_unknown(self):
        sessions = [make_session('ses_1', updated=BASE_MS)]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'open.db'
            with closing(sqlite3.connect(path)) as db:
                db.execute(SESSION_DDL)
                db.execute(
                    'INSERT INTO session VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    tuple(sessions[0][key] for key in (
                        'id', 'project_id', 'parent_id', 'directory',
                        'agent', 'model', 'version', 'tokens_input',
                        'tokens_output', 'tokens_reasoning',
                        'tokens_cache_read', 'tokens_cache_write',
                        'cost', 'time_created', 'time_updated')))
                db.commit()
            snap = OpenCodeProvider(path).activity_snapshot(now=NOW_S)
        self.assertFalse(snap['valid'])
        self.assertFalse(snap['working'])

    def test_wider_window_after_narrower_rescans(self):
        # A cached projection from a narrower (newer-clock) window must
        # not serve a wider (older-clock) window: the older window could
        # match rows the projection never fetched.
        sessions = [make_session('ses_1', updated=BASE_MS)]
        parts = [make_part('p_start', 'ses_1', created=BASE_MS - 100000)]
        with tempfile.TemporaryDirectory() as directory:
            provider, _ = self._provider(directory, sessions, parts)
            narrow = provider.activity_snapshot(now=NOW_S + 600)
            wide = provider.activity_snapshot(now=NOW_S)
            provider.close()
        self.assertTrue(narrow['working'])
        self.assertTrue(wide['working'])
        self.assertEqual(provider.activity_scans, 2)


FINISH_DATA = json.dumps({'type': 'step-finish', 'reason': 'stop'})
OPEN_CREATED = BASE_MS - 100000
OLD_CREATED = BASE_MS - 1000000


class ActivityBytesKeyTests(unittest.TestCase):
    """Commit-generation invalidation: every committed write class the
    retired fingerprints missed must rescan at once, including
    same-size updates with restored mtimes that collide any stat-only
    key. A reused provider must always agree with a fresh provider."""

    def _working_store(self, directory, wal=False):
        path = write_store(
            Path(directory) / 'open.db',
            [make_session('ses_1', updated=BASE_MS)], (),
            [make_part('p_open', 'ses_1', created=OPEN_CREATED)])
        if wal:
            enable_wal(path)
        return path

    def _agree_with_fresh(self, provider, path, now=NOW_S):
        reused = provider.activity_snapshot(now=now)
        fresh = OpenCodeProvider(path)
        try:
            fresh_snap = fresh.activity_snapshot(now=now)
        finally:
            fresh.close()
        self.assertEqual(reused['working'], fresh_snap['working'])
        self.assertEqual(reused['primary_session_id'],
                         fresh_snap['primary_session_id'])
        self.assertEqual(
            [entry['working'] for entry in reused['sessions']],
            [entry['working'] for entry in fresh_snap['sessions']])
        return reused, fresh_snap

    def test_same_rowid_update_rescans_immediately(self):
        for wal in (False, True):
            with tempfile.TemporaryDirectory() as directory:
                path = self._working_store(directory, wal=wal)
                provider = OpenCodeProvider(path)
                live = provider.activity_snapshot(now=NOW_S)
                self.assertTrue(live['working'], wal)
                scans = provider.activity_scans
                with closing(sqlite3.connect(path)) as db:
                    db.execute(
                        'UPDATE part SET time_created=?, time_updated=?,'
                        ' data=? WHERE id=?',
                        (OLD_CREATED, OLD_CREATED, FINISH_DATA, 'p_open'))
                    db.commit()
                idle, _ = self._agree_with_fresh(provider, path)
                self.assertFalse(idle['working'], wal)
                self.assertIsNone(idle['primary_session_id'])
                self.assertGreater(provider.activity_scans, scans, wal)
                # Release the commit-detector handle before the temp
                # dir is cleaned (Windows cannot delete open files).
                provider.close()

    def test_same_size_update_with_restored_mtime_rescans(self):
        # Exact final-gate repro: prime with a fresh step-start, commit
        # an in-place same-size UPDATE to an expired step-finish, then
        # restore the pre-commit mtime. File id and size are unchanged
        # and no WAL exists, so any stat-only key collides — the commit
        # generation must still force an immediate rescan that agrees
        # with a fresh provider.
        start_data = json.dumps({'type': 'step-start'}) + ' '
        finish_data = json.dumps({'type': 'step-finish'})
        self.assertEqual(len(start_data), len(finish_data))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'open.db'
            part = make_part('p_open', 'ses_1', created=OPEN_CREATED)
            part['data'] = start_data
            part['time_updated'] = OPEN_CREATED
            write_store(path, [make_session('ses_1', updated=BASE_MS)],
                        (), [part])
            provider = OpenCodeProvider(path)
            try:
                live = provider.activity_snapshot(now=NOW_S)
                self.assertTrue(live['working'])
                scans = provider.activity_scans
                before = path.stat()
                with closing(sqlite3.connect(path)) as db:
                    db.execute(
                        'UPDATE part SET time_created=?, time_updated=?,'
                        ' data=? WHERE id=?',
                        (OLD_CREATED, OLD_CREATED, finish_data, 'p_open'))
                    db.commit()
                os.utime(path, ns=(before.st_atime_ns,
                                   before.st_mtime_ns))
                after = path.stat()
                self.assertEqual(after.st_size, before.st_size)
                self.assertEqual(after.st_mtime_ns, before.st_mtime_ns)
                idle, _ = self._agree_with_fresh(provider, path)
                self.assertFalse(idle['working'])
                self.assertIsNone(idle['primary_session_id'])
                self.assertGreater(provider.activity_scans, scans)
            finally:
                provider.close()

    def test_primary_session_tracks_committed_change(self):
        # Two working sessions: the newest instant wins. Committing a
        # finish on the primary must move primary to the other session
        # on the reused provider, agreeing with a fresh provider.
        with tempfile.TemporaryDirectory() as directory:
            path = write_store(
                Path(directory) / 'open.db',
                [make_session('ses_a', updated=BASE_MS),
                 make_session('ses_b', updated=BASE_MS)], (),
                [make_part('p_a', 'ses_a', created=BASE_MS - 200000),
                 make_part('p_b', 'ses_b', created=BASE_MS - 50000)])
            provider = OpenCodeProvider(path)
            try:
                live = provider.activity_snapshot(now=NOW_S)
                self.assertTrue(live['working'])
                self.assertEqual(live['primary_session_id'],
                                 'opencode:ses_b')
                with closing(sqlite3.connect(path)) as db:
                    db.execute(
                        'UPDATE part SET time_created=?, time_updated=?,'
                        ' data=? WHERE id=?',
                        (OLD_CREATED, OLD_CREATED, FINISH_DATA, 'p_b'))
                    db.commit()
                moved, _ = self._agree_with_fresh(provider, path)
                self.assertTrue(moved['working'])
                self.assertEqual(moved['primary_session_id'],
                                 'opencode:ses_a')
            finally:
                provider.close()

    def test_retry_exhaustion_reports_unstable_unknown(self):
        # Real commits straddle every projection attempt: working,
        # idle, working candidates with a final idle store. After the
        # bounded redo is exhausted the candidate must be discarded —
        # never evaluated, cached, or publishable as working or idle.
        start_data = json.dumps({'type': 'step-start'})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'open.db'
            part = make_part('p_open', 'ses_1', created=OPEN_CREATED)
            part['time_updated'] = OPEN_CREATED
            write_store(path, [make_session('ses_1', updated=BASE_MS)],
                        (), [part])
            provider = OpenCodeProvider(path)
            try:
                live = provider.activity_snapshot(now=NOW_S)
                self.assertTrue(live['working'])
                orig_current = provider._dv_current
                calls = []

                def flipping(file_id):
                    calls.append(1)
                    if len(calls) in (2, 4, 6):
                        with closing(sqlite3.connect(path)) as db:
                            if len(calls) in (2, 6):
                                db.execute(
                                    'UPDATE part SET time_created=?,'
                                    ' time_updated=?, data=? WHERE id=?',
                                    (OLD_CREATED, OLD_CREATED,
                                     FINISH_DATA, 'p_open'))
                            else:
                                db.execute(
                                    'UPDATE part SET time_created=?,'
                                    ' time_updated=?, data=? WHERE id=?',
                                    (OPEN_CREATED, OPEN_CREATED,
                                     start_data, 'p_open'))
                            db.commit()
                    return orig_current(file_id)

                provider._dv_current = flipping
                try:
                    # Fresh probe state forces the rescan path with
                    # exactly six generation reads (before/after x3).
                    provider._activity_probe = None
                    outcome = provider.activity_snapshot(now=NOW_S)
                finally:
                    del provider._dv_current
                self.assertEqual(len(calls), 6)
                self.assertFalse(outcome['valid'])
                self.assertFalse(outcome['working'])
                self.assertIsNone(outcome['primary_session_id'])
                self.assertEqual(outcome['reason'], 'activity_unstable')
                self.assertEqual(outcome['sessions'], [])
                self.assertIsNone(provider._activity_probe)
                self.assertEqual(provider.activity_scans, 4)
                # Final store is idle; a fresh read agrees it is idle
                # (the discarded last candidate looked working).
                fresh = OpenCodeProvider(path)
                try:
                    settled = fresh.activity_snapshot(now=NOW_S)
                finally:
                    fresh.close()
                self.assertTrue(settled['valid'])
                self.assertFalse(settled['working'])
            finally:
                provider.close()

    def test_commit_then_stable_retry_agrees_with_fresh(self):
        # One commit lands around the first projection; the bounded
        # redo then observes a stable store and must agree with a fresh
        # provider instead of reusing anything stale.
        with tempfile.TemporaryDirectory() as directory:
            path = self._working_store(directory)
            provider = OpenCodeProvider(path)
            try:
                live = provider.activity_snapshot(now=NOW_S)
                self.assertTrue(live['working'])
                scans = provider.activity_scans
                orig_current = provider._dv_current
                calls = []

                def once_flipping(file_id):
                    calls.append(1)
                    if len(calls) == 2:
                        with closing(sqlite3.connect(path)) as db:
                            db.execute(
                                'UPDATE part SET time_created=?,'
                                ' time_updated=?, data=? WHERE id=?',
                                (OLD_CREATED, OLD_CREATED,
                                 FINISH_DATA, 'p_open'))
                            db.commit()
                    return orig_current(file_id)

                provider._dv_current = once_flipping
                try:
                    # Fresh probe state forces the rescan path: one
                    # straddled attempt, then a stable retry.
                    provider._activity_probe = None
                    outcome = provider.activity_snapshot(now=NOW_S)
                finally:
                    del provider._dv_current
                self.assertEqual(len(calls), 4)
                self.assertFalse(outcome['working'])
                self.assertIsNone(outcome['primary_session_id'])
                self.assertEqual(provider.activity_scans, scans + 2)
                reused, fresh = self._agree_with_fresh(provider, path)
                self.assertFalse(reused['working'])
                self.assertFalse(fresh['working'])
                self.assertEqual(provider.activity_scans, scans + 2)
            finally:
                provider.close()

    def test_shutdown_refuses_detector_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self._working_store(directory)
            provider = OpenCodeProvider(path)
            try:
                live = provider.activity_snapshot(now=NOW_S)
                self.assertTrue(live['working'])
                self.assertIsNotNone(provider._dv_conn)
                provider.shutdown()
                self.assertIsNone(provider._dv_conn)
                # Snapshots keep evaluating from fresh reads but never
                # cache and never reopen the detector.
                snap = provider.activity_snapshot(now=NOW_S)
                self.assertTrue(snap['valid'])
                self.assertTrue(snap['working'])
                self.assertIsNone(provider._activity_probe)
                self.assertIsNone(provider._dv_conn)
                provider.close()
                again = provider.activity_snapshot(now=NOW_S)
                self.assertTrue(again['working'])
                self.assertIsNone(provider._dv_conn)
                provider.shutdown()
            finally:
                provider.close()

    def test_delete_lifecycle_row_with_same_max_rescans(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write_store(
                Path(directory) / 'open.db',
                [make_session('ses_1', updated=BASE_MS)], (),
                [make_part('p_old', 'ses_1', created=OLD_CREATED,
                           kind='step-finish', reason='stop'),
                 make_part('p_open', 'ses_1', created=OPEN_CREATED),
                 make_part('p_tail', 'ses_1', created=BASE_MS - 50000,
                           kind='text')])
            provider = OpenCodeProvider(path)
            self.assertTrue(
                provider.activity_snapshot(now=NOW_S)['working'])
            scans = provider.activity_scans
            with closing(sqlite3.connect(path)) as db:
                db.execute("DELETE FROM part WHERE id='p_open'")
                db.commit()
            idle, _ = self._agree_with_fresh(provider, path)
            self.assertFalse(idle['working'])
            self.assertGreater(provider.activity_scans, scans)
            provider.close()

    def test_retained_wal_writer_commits_and_rollback(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self._working_store(directory, wal=True)
            provider = OpenCodeProvider(path)
            self.assertTrue(
                provider.activity_snapshot(now=NOW_S)['working'])
            writer = sqlite3.connect(path, timeout=5)
            writer.execute('PRAGMA wal_autocheckpoint=0')
            try:
                # Uncommitted writes stay invisible: still working and a
                # fresh provider agrees.
                writer.execute(
                    'UPDATE part SET time_created=?, data=? WHERE id=?',
                    (OLD_CREATED, FINISH_DATA, 'p_open'))
                hidden, _ = self._agree_with_fresh(provider, path)
                self.assertTrue(hidden['working'])
                writer.rollback()
                rolled, _ = self._agree_with_fresh(provider, path)
                self.assertTrue(rolled['working'])
                # The retained-writer commit lands only in -wal (main
                # size+mtime untouched) and must still rescan at once.
                scans = provider.activity_scans
                writer.execute(
                    'UPDATE part SET time_created=?, data=? WHERE id=?',
                    (OLD_CREATED, FINISH_DATA, 'p_open'))
                writer.commit()
                idle, _ = self._agree_with_fresh(provider, path)
                self.assertFalse(idle['working'])
                self.assertGreater(provider.activity_scans, scans)
                # A new open step from the same writer revives Working.
                writer.execute(
                    "INSERT INTO part VALUES (?,?,?,?,?,?)",
                    ('p_next', 'msg_1', 'ses_1', OPEN_CREATED,
                     OPEN_CREATED,
                     json.dumps({'type': 'step-start'})))
                writer.commit()
                revived, _ = self._agree_with_fresh(provider, path)
                self.assertTrue(revived['working'])
                self.assertEqual(revived['primary_session_id'],
                                 'opencode:ses_1')
            finally:
                writer.close()
            provider.close()

    def test_replacement_with_same_shape_rescans(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self._working_store(directory)
            provider = OpenCodeProvider(path)
            self.assertTrue(
                provider.activity_snapshot(now=NOW_S)['working'])
            scans = provider.activity_scans
            # Same session ids/revisions, same part count and rowids,
            # but flipped lifecycle meaning in a brand-new file. The
            # detector handle is released first: on Windows an open
            # handle blocks replacement at OS level, so a successful
            # replace implies the reader comes back fresh — the cached
            # projection must still be distrusted via file identity.
            provider.close()
            write_store(
                path, [make_session('ses_1', updated=BASE_MS)], (),
                [make_part('p_open', 'ses_1', created=OLD_CREATED,
                           kind='step-finish', reason='stop')])
            idle, _ = self._agree_with_fresh(provider, path)
            self.assertFalse(idle['working'])
            self.assertGreater(provider.activity_scans, scans)
            provider.close()

    def test_unchanged_store_reuses_with_fresh_clock(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self._working_store(directory)
            provider = OpenCodeProvider(path)
            self.assertTrue(
                provider.activity_snapshot(now=NOW_S)['working'])
            self.assertEqual(provider.activity_scans, 1)
            # No bytes changed: policy re-evaluates with the fresh clock
            # (the open step ages out) without rescanning.
            aged = provider.activity_snapshot(now=NOW_S + 800)
            self.assertFalse(aged['working'])
            self.assertEqual(provider.activity_scans, 1)
            provider.close()

    def test_backstop_bounds_theoretical_residuals(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self._working_store(directory)
            provider = OpenCodeProvider(path)
            self.assertTrue(
                provider.activity_snapshot(now=NOW_S)['working'])
            self.assertEqual(provider.activity_scans, 1)
            provider._activity_probe['scanned_at'] -= 61
            forced = provider.activity_snapshot(now=NOW_S)
            self.assertTrue(forced['working'])
            self.assertEqual(provider.activity_scans, 2)
            provider.close()

    def test_retained_wal_delete_rescans_immediately(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write_store(
                Path(directory) / 'open.db',
                [make_session('ses_1', updated=BASE_MS)], (),
                [make_part('p_old', 'ses_1', created=OLD_CREATED,
                           kind='step-finish', reason='stop'),
                 make_part('p_open', 'ses_1', created=OPEN_CREATED),
                 make_part('p_tail', 'ses_1', created=BASE_MS - 50000,
                           kind='text')])
            enable_wal(path)
            provider = OpenCodeProvider(path)
            self.assertTrue(
                provider.activity_snapshot(now=NOW_S)['working'])
            writer = sqlite3.connect(path, timeout=5)
            writer.execute('PRAGMA wal_autocheckpoint=0')
            try:
                scans = provider.activity_scans
                writer.execute("DELETE FROM part WHERE id='p_open'")
                writer.commit()
                idle, _ = self._agree_with_fresh(provider, path)
                self.assertFalse(idle['working'])
                self.assertGreater(provider.activity_scans, scans)
                # Uncommitted delete stays invisible to both providers.
                writer.execute("DELETE FROM part WHERE id='p_tail'")
                hidden, _ = self._agree_with_fresh(provider, path)
                self.assertFalse(hidden['working'])
                writer.rollback()
                rolled, _ = self._agree_with_fresh(provider, path)
                self.assertFalse(rolled['working'])
            finally:
                writer.close()
            provider.close()

    def test_session_revision_forces_activity_rescan(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self._working_store(directory)
            provider = OpenCodeProvider(path)
            self.assertTrue(
                provider.activity_snapshot(now=NOW_S)['working'])
            scans = provider.activity_scans
            with closing(sqlite3.connect(path)) as db:
                db.execute('UPDATE session SET tokens_input=?,'
                           ' time_updated=? WHERE id=?',
                           (999, BASE_MS + 2000, 'ses_1'))
                db.commit()
            reused, fresh = self._agree_with_fresh(provider, path)
            self.assertEqual(reused['working'], fresh['working'])
            self.assertGreater(provider.activity_scans, scans)
            provider.close()


class RecordedTotalTests(unittest.TestCase):
    """OpenCode recorded Total: the five stored-category sum for
    verified session versions with complete coverage — the same sum
    OpenCode's own stats computes over its session rollups. Anything
    missing, partial, malformed, or unverified stays N/A."""

    FIVE = (1000, 200, 30, 4000, 70)
    FIVE_SUM = 5300

    def _read(self, directory, sessions, **kwargs):
        path = write_store(Path(directory) / 'open.db', sessions)
        return OpenCodeProvider(path).read(**kwargs)

    def test_distinct_values_sum_for_verified_version(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self._read(
                directory,
                [make_session('ses_1', version='1.18.31',
                              tokens=self.FIVE, cost=0.05)],
                pinned='ses_1')
        self.assertTrue(result['available'])
        self.assertEqual(result['tokens']['total'], self.FIVE_SUM)
        self.assertEqual(result['scope_result']['coverage']['total'],
                         'complete')
        self.assertIn('total_recorded_sum', result['notes'])
        self.assertFalse(result['partial'])
        # Raw categories preserved alongside the total.
        self.assertEqual(
            (result['tokens']['input'], result['tokens']['output'],
             result['tokens']['reasoning'], result['tokens']['cache_read'],
             result['tokens']['cache_write']), self.FIVE)

    def test_second_verified_tag_sums(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self._read(
                directory,
                [make_session('ses_1', version='1.18.32',
                              tokens=self.FIVE, cost=0.05)],
                pinned='ses_1')
        self.assertEqual(result['tokens']['total'], self.FIVE_SUM)

    def test_complete_zero_stays_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self._read(
                directory,
                [make_session('ses_1', version='1.18.31',
                              tokens=(0, 0, 0, 0, 0), cost=0.0)],
                pinned='ses_1')
        self.assertEqual(result['tokens']['total'], 0)
        self.assertEqual(result['scope_result']['coverage']['total'],
                         'complete')

    def test_missing_field_gives_na(self):
        with tempfile.TemporaryDirectory() as directory:
            row = make_session('ses_1', version='1.18.31',
                               tokens=(100, 20, 5, 400, 0))
            row['tokens_cache_write'] = None
            path = write_store(Path(directory) / 'open.db', [row])
            result = OpenCodeProvider(path).read(pinned='ses_1')
        self.assertIsNone(result['tokens']['total'])
        self.assertEqual(result['scope_result']['coverage']['total'],
                         'unknown')
        self.assertIn('total_unavailable_unverified_or_incomplete',
                      result['notes'])

    def test_partial_scope_gives_na_not_subtotal(self):
        with tempfile.TemporaryDirectory() as directory:
            full = make_session('ses_a', project='proj-x',
                                version='1.18.31', tokens=self.FIVE,
                                updated=BASE_MS)
            thin = make_session('ses_b', project='proj-x',
                                version='1.18.31', tokens=self.FIVE,
                                updated=BASE_MS)
            thin['tokens_input'] = None
            result = self._read(directory, [full, thin], scope='global')
        self.assertEqual(result['tokens']['input'], self.FIVE[0])
        self.assertEqual(result['scope_result']['coverage']['input'],
                         'partial')
        self.assertIsNone(result['tokens']['total'])
        self.assertTrue(result['partial'])

    def test_malformed_field_gives_na(self):
        with tempfile.TemporaryDirectory() as directory:
            row = make_session('ses_1', version='1.18.31',
                               tokens=self.FIVE)
            row['tokens_output'] = -4
            path = write_store(Path(directory) / 'open.db', [row])
            result = OpenCodeProvider(path).read(pinned='ses_1')
        # Negative output is rejected to unknown, so the Total is N/A.
        self.assertIsNone(result['tokens']['output'])
        self.assertIsNone(result['tokens']['total'])

    def test_unverified_versions_give_na(self):
        for version in (None, '', '1.17.0', '1.19.0', 11831):
            with tempfile.TemporaryDirectory() as directory:
                result = self._read(
                    directory,
                    [make_session('ses_1', version=version,
                                  tokens=self.FIVE, cost=0.05)],
                    pinned='ses_1')
            self.assertIsNone(result['tokens']['total'], version)
            self.assertEqual(
                result['scope_result']['coverage']['total'], 'unknown')

    def test_mixed_versions_give_na(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self._read(
                directory,
                [make_session('ses_a', project='proj-x',
                              version='1.18.31', tokens=self.FIVE,
                              updated=BASE_MS),
                 make_session('ses_b', project='proj-x',
                              version='9.9.9', tokens=self.FIVE,
                              updated=BASE_MS)],
                scope='global')
        self.assertEqual(result['tokens']['input'], self.FIVE[0] * 2)
        self.assertIsNone(result['tokens']['total'])

    def test_message_upstream_total_never_used(self):
        # An upstream per-message tokens.total must not leak into the
        # session-rollup Total, which sums only stored columns.
        upstream_total = 999999
        message_tokens = {'input': 10, 'output': 4, 'reasoning': 1,
                          'cache': {'read': 40, 'write': 0},
                          'total': upstream_total}
        with tempfile.TemporaryDirectory() as directory:
            path = write_store(
                Path(directory) / 'open.db',
                [make_session('ses_1', version='1.18.31',
                              tokens=self.FIVE, cost=0.05)],
                [make_message('m1', 'ses_1', tokens=message_tokens)])
            result = OpenCodeProvider(path).read(pinned='ses_1',
                                                 include_history=True)
        self.assertEqual(result['tokens']['total'], self.FIVE_SUM)
        self.assertNotEqual(result['tokens']['total'], upstream_total)

    def test_active_display_and_working_context_carry_total(self):
        from opencode_provider import opencode_working_context
        row = make_session('ses_work', project='proj-w',
                           directory='/synthetic/work',
                           version='1.18.31', tokens=self.FIVE,
                           cost=0.05, updated=BASE_MS)
        shown = opencode_active_display(row, 'conversation',
                                        'session_not_found')
        self.assertEqual(shown['tokens']['total'], self.FIVE_SUM)
        self.assertEqual(shown['token_coverage']['total'], 'complete')
        context = opencode_working_context(row)
        self.assertEqual(context['tokens']['total'], self.FIVE_SUM)
        # Unverified rows stay N/A in both shapes.
        row['version'] = None
        self.assertIsNone(
            opencode_active_display(
                row, 'conversation',
                'session_not_found')['tokens']['total'])
        self.assertIsNone(
            opencode_working_context(row)['tokens']['total'])


class DisplayMappingTests(unittest.TestCase):
    def test_active_display_binds_one_row_coherently(self):
        row = make_session('ses_work', project='proj-w',
                           directory='/synthetic/work',
                           tokens=(100, 20, 5, 400, 7), cost=0.05,
                           updated=BASE_MS)
        shown = opencode_active_display(row, 'conversation',
                                        'session_not_found')
        self.assertTrue(shown['available'])
        self.assertEqual(shown['presentation'], 'active_session')
        self.assertEqual(shown['scope'], 'conversation')
        identity = shown['scope_identity']
        self.assertEqual(identity['scope_type'], 'active_session')
        self.assertEqual(identity['requested_scope'], 'conversation')
        self.assertEqual(identity['session_id'], 'opencode:ses_work')
        self.assertEqual(shown['session_id'], 'opencode:ses_work')
        self.assertEqual(shown['model'], 'test-model')
        self.assertEqual(shown['project'], 'work')
        self.assertEqual(shown['tokens']['input'], 100)
        self.assertEqual(shown['tokens']['output'], 20)
        self.assertEqual(shown['tokens']['reasoning'], 5)
        self.assertEqual(shown['tokens']['cache_read'], 400)
        self.assertEqual(shown['tokens']['cache_write'], 7)
        self.assertIsNone(shown['tokens']['total'])
        self.assertEqual(shown['cost']['amount'], 0.05)
        self.assertIsNone(shown['cost']['currency'])
        self.assertEqual(shown['scope_status'], 'waiting_available_task')
        self.assertEqual(shown['breakdown_sessions'], [])
        self.assertIsNone(shown['history'])

    def test_active_display_rejects_missing_row(self):
        self.assertIsNone(opencode_active_display(None, 'conversation',
                                                 'session_not_found'))
        self.assertIsNone(opencode_active_display({}, 'conversation', ''))
        self.assertIsNone(opencode_active_display(
            dict(make_session('x'), id=None), 'conversation', ''))
    def _read(self, directory, **kwargs):
        path = write_store(
            Path(directory) / 'open.db',
            [make_session('ses_1', project='proj-a',
                          directory='/synthetic/alpha',
                          tokens=(100, 20, 5, 400, 0), cost=0.05),
             make_session('ses_2', project='proj-b',
                          directory='/synthetic/beta',
                          tokens=(7, 7, 7, 7, 7), cost=0.0)])
        return OpenCodeProvider(path).read(**kwargs)

    def test_conversation_display(self):
        from opencode_provider import opencode_display
        with tempfile.TemporaryDirectory() as directory:
            result = opencode_display(
                self._read(directory, pinned='ses_1'))
        self.assertEqual(result['provider_id'], 'opencode')
        self.assertEqual(result['status'], '')
        self.assertTrue(result['available'])
        self.assertEqual(result['scope'], 'conversation')
        self.assertEqual(result['project'], 'alpha')
        self.assertEqual(result['session_id'], 'opencode:ses_1')
        self.assertEqual(result['title'], 'ses_1')
        self.assertEqual(result['model'], 'test-model')
        self.assertEqual(result['effort'], 'default')
        self.assertEqual(result['model_detail']['provider'], 'testco')
        # Raw categories only; total never summed.
        self.assertEqual(
            result['tokens'],
            dict(input=100, output=20, reasoning=5, cache_read=400,
                 cache_write=0, total=None))
        self.assertEqual(result['cost']['amount'], 0.05)
        self.assertIsNone(result['cost']['currency'])

    def test_global_display_uses_all_usage_labels(self):
        from opencode_provider import opencode_display
        with tempfile.TemporaryDirectory() as directory:
            result = opencode_display(
                self._read(directory, scope='global'))
        self.assertEqual(result['project'], 'display_all_usage')
        self.assertEqual(result['title'], 'display_local_history')
        self.assertIsNone(result['model'])
        self.assertEqual(result['tokens']['input'], 107)

    def test_project_display_names_project(self):
        from opencode_provider import opencode_display
        with tempfile.TemporaryDirectory() as directory:
            result = opencode_display(
                self._read(directory, pinned='ses_1', scope='project'))
        self.assertEqual(result['project'], 'alpha')
        self.assertEqual(result['title'], 'alpha')
        self.assertIsNone(result['model'])

    def test_status_mapping(self):
        from opencode_provider import opencode_display
        with tempfile.TemporaryDirectory() as directory:
            missing = opencode_display(
                self._read(directory, pinned='ghost'))
            self.assertEqual(missing['status'], 'waiting_available_task')
            self.assertFalse(missing['available'])
            self.assertIsNone(missing['project'])
            absent = opencode_display(
                OpenCodeProvider(
                    Path(directory) / 'absent.db').read())
            self.assertEqual(absent['status'], 'no_reliable_record')

    def test_working_context_binding(self):
        from opencode_provider import (opencode_session_row,
                                       opencode_working_context)
        with tempfile.TemporaryDirectory() as directory:
            path = write_store(Path(directory) / 'open.db',
                               [make_session('ses_1')])
            read = OpenCodeProvider(path).read(pinned='ses_1')
            row = opencode_session_row(read, 'ses_1')
            context = opencode_working_context(row)
            self.assertEqual(context['thread'], 'ses_1')
            self.assertEqual(context['project'], 'alpha')
            self.assertEqual(context['model'], 'test-model')
            self.assertEqual(context['tokens']['input'], 100)
            self.assertIsNone(context['tokens']['total'])
            self.assertIsNone(context['context'])
            self.assertIsNone(opencode_working_context(None))
            self.assertIsNone(opencode_session_row(read, 'ghost'))


if __name__ == '__main__':
    unittest.main()
