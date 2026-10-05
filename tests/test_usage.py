import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from usage import CodexStore, SessionUsage, estimate_usd, select_thread, quota_window


def event(total, last=None):
    return {"type": "event_msg", "timestamp": "2026-09-16T12:00:00Z", "payload": {
        "type": "token_count", "info": {"total_token_usage": total,
        "last_token_usage": last or total, "model_context_window": 258400}}}


class UsageTests(unittest.TestCase):
    def test_cached_and_reasoning_not_double_counted(self):
        tokens = dict(input_tokens=1000, cached_input_tokens=800,
                      output_tokens=100, reasoning_output_tokens=80)
        self.assertAlmostEqual(estimate_usd(tokens, "gpt-6-astra"), .0078)
        self.assertAlmostEqual(estimate_usd(tokens, "gpt-6-astra", "priority"), .0156)
        self.assertIsNone(estimate_usd(tokens, "unknown-model"))

    def test_long_context_and_cache_writes(self):
        tokens = dict(input_tokens=300000, cached_input_tokens=100000,
                      cache_write_input_tokens=50000, output_tokens=1000)
        self.assertAlmostEqual(estimate_usd(tokens, "gpt-6-astra"), 4.525)

    def test_incremental_dedup_partial_lines_and_model_switch(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "rollout.jsonl"
            a = dict(input_tokens=1000, cached_input_tokens=800, output_tokens=100, total_tokens=1100)
            b = dict(input_tokens=2000, cached_input_tokens=1600, output_tokens=200, total_tokens=2200)
            ctx = {"type": "turn_context", "payload": {"model": "gpt-6-astra", "effort": "high"}}
            p.write_text(json.dumps(ctx)+"\n"+json.dumps(event(a))+"\n"+json.dumps(event(a))+"\n", encoding="utf-8")
            s = SessionUsage(p)
            s.refresh()
            self.assertEqual(s.total['total_tokens'], 1100)
            self.assertAlmostEqual(s.usd, .0078)
            with p.open('ab') as f:
                f.write((json.dumps({"type": "turn_context", "payload": {"model": "gpt-5.6-sol"}})+'\n').encode())
                line = json.dumps(event(b, a)).encode()
                f.write(line[:40])
            s.refresh()
            self.assertEqual(s.total['total_tokens'], 1100)
            with p.open('ab') as f: f.write(line[40:]+b'\n')
            s.refresh()
            self.assertEqual(s.total['total_tokens'], 2200)
            self.assertAlmostEqual(s.usd, .01092)
            s.refresh()
            self.assertAlmostEqual(s.usd, .01092)

    def test_active_title_beats_latest_writer_and_stale_route(self):
        rows = [dict(id='new', name='Widget', title='', cwd='B'),
                dict(id='old', name='3D website', title='', cwd='A')]
        row, mode = select_thread(rows, '3D website', '')
        self.assertEqual(row['id'], 'old')
        self.assertEqual(mode, 'follow')
        self.assertEqual(select_thread(rows, '', 'old')[0]['id'], 'old')
        self.assertEqual(select_thread(rows, '', '')[1], 'recent')
        self.assertEqual(select_thread(rows, '', 'deleted'), (None, 'missing'))

    def test_limits_use_duration_not_primary_slot(self):
        limits = {'primary': {'usedPercent': 40, 'windowDurationMins': 10080, 'resetsAt': 200},
                  'secondary': {'usedPercent': 70, 'windowDurationMins': 300, 'resetsAt': 200}}
        self.assertEqual(quota_window(limits, 300, now=100)['remaining'], 30)
        self.assertTrue(quota_window(limits, 300, now=201)['expired'])
        self.assertIsNone(quota_window(limits, 123, now=100))


class CodexCompatibilityTests(unittest.TestCase):
    fixture_dir = Path(__file__).parent / 'fixtures' / 'codex'

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.fixture = json.loads((self.fixture_dir / 'current-structure.json').read_text(encoding='utf-8'))
        self.rollout = self.home / 'fixture.jsonl'
        self.rollout.write_bytes((self.fixture_dir / 'current-0.156.1.jsonl').read_bytes())
        self.version = patch('usage.installed_version', return_value='0.156.1')
        self.version_mock = self.version.start()
        self.addCleanup(self.version.stop)
        self.database()
        self.ledger()

    def database(self, missing=(), extra=False, wrong=None, row_override=None):
        path = self.home / 'state_5.sqlite'
        path.unlink(missing_ok=True)
        columns = self.fixture['databases']['state_5.sqlite']['columns']
        columns = [dict(c) for c in columns if c['name'] not in missing]
        if extra:
            columns.append(dict(name='future_counter', type='INTEGER'))
        if wrong:
            next(c for c in columns if c['name'] == wrong)['type'] = 'BLOB'
        values = {c['name']: (0 if c['type'] == 'INTEGER' else '') for c in columns}
        values.update({k: v for k, v in dict(id='codex-fixture', rollout_path=str(self.rollout),
            updated_at=1791158400, source='desktop', archived=0, cli_version='0.156.1',
            title='Synthetic', name='Synthetic', cwd='fixture-project').items() if k in values})
        values.update(row_override or {})
        with closing(sqlite3.connect(path)) as db:
            db.execute('CREATE TABLE threads (' + ','.join('"'+c['name']+'" '+c['type'] for c in columns) + ')')
            db.execute('INSERT INTO threads VALUES (' + ','.join('?' for _ in values) + ')', tuple(values.values()))
            db.commit()

    def ledger(self):
        columns = self.fixture['databases']['thread_history_1.sqlite']['columns']
        with closing(sqlite3.connect(self.home / 'thread_history_1.sqlite')) as db:
            db.execute('CREATE TABLE thread_turns (' + ','.join('"'+c['name']+'" '+c['type'] for c in columns) + ')')
            db.commit()

    def assert_unavailable(self, data):
        self.assertFalse(data.get('available', False))
        self.assertTrue(data.get('tokens') is None or all(v is None for v in data['tokens'].values()))
        self.assertIsNone(data.get('usd'))

    def test_current_machine_fixture_keeps_all_baseline_numbers(self):
        store = CodexStore(self.home)
        self.assertEqual(store.compatibility['status'], 'supported')
        data = store.read()
        baseline = self.fixture['baseline_numeric_result']
        self.assertEqual(data['tokens'], baseline['tokens'])
        self.assertEqual(data['raw_last'], baseline['last_tokens'])
        self.assertEqual(data['context_window'], baseline['context_window'])
        self.assertEqual(data['compatibility']['status'], 'supported')
        self.assertEqual(data['compatibility']['codex_version'], '0.156.1')
        self.assertEqual(data['compatibility']['writer_versions'], ['0.156.1'])
        self.assertTrue(data['compatibility']['components']['usage']['fingerprints'])

    def test_extra_column_is_safe_and_changes_fingerprint(self):
        first = CodexStore(self.home).read()
        self.database(extra=True)
        second = CodexStore(self.home).read()
        self.assertEqual(second['tokens'], first['tokens'])
        self.assertEqual(second['compatibility']['status'], 'supported')
        self.assertNotEqual(first['compatibility']['components']['threads']['fingerprint']['sha256'],
                            second['compatibility']['components']['threads']['fingerprint']['sha256'])

    def test_missing_required_fields_fail_closed(self):
        for field in ('id', 'rollout_path', 'updated_at'):
            with self.subTest(field=field):
                self.database(missing=(field,))
                data = CodexStore(self.home).read()
                self.assert_unavailable(data)
                self.assertEqual(data['compatibility']['status'], 'unsupported')
                self.assertIn('missing_field:threads:'+field, data['compatibility']['reasons'])

    def test_missing_optional_field_preserves_known_numbers(self):
        self.database(missing=('model',))
        data = CodexStore(self.home).read()
        self.assertEqual(data['tokens'], self.fixture['baseline_numeric_result']['tokens'])
        self.assertEqual(data['compatibility']['status'], 'partial')
        self.assertIsNone(data['model'])

    def test_missing_source_or_archived_does_not_invent_desktop_membership(self):
        for field in ('source', 'archived'):
            self.database(missing=(field,))
            store = CodexStore(self.home)
            self.assert_unavailable(store.read())
            self.assertEqual(store.read(scope='global')['tokens'], self.fixture['baseline_numeric_result']['tokens'])

    def test_wrong_declared_type_fails_closed(self):
        self.database(wrong='rollout_path')
        self.assert_unavailable(CodexStore(self.home).read())

    def test_wrong_row_type_does_not_crash_or_create_zero(self):
        self.database(row_override={'updated_at': 'not-a-number'})
        self.assert_unavailable(CodexStore(self.home).read())

    def test_missing_table_and_corrupt_database_fail_closed(self):
        path = self.home / 'state_5.sqlite'
        with closing(sqlite3.connect(path)) as db:
            db.execute('DROP TABLE threads')
            db.commit()
        self.assert_unavailable(CodexStore(self.home).read())
        path.write_bytes(b'not sqlite')
        self.assert_unavailable(CodexStore(self.home).read())

    def test_missing_database_and_home_fail_closed(self):
        (self.home / 'state_5.sqlite').unlink()
        self.assert_unavailable(CodexStore(self.home).read())
        self.assert_unavailable(CodexStore(self.home / 'absent').read())
        self.assertFalse((self.home / 'absent').exists())

    def test_missing_usage_file_does_not_expose_cached_numbers(self):
        store = CodexStore(self.home)
        self.assertTrue(store.read()['available'])
        self.rollout.unlink()
        data = store.read()
        self.assert_unavailable(data)
        self.assertEqual(data['compatibility']['components']['usage']['status'], 'unsupported')

    def test_schema_is_rechecked_on_same_store_and_can_recover(self):
        store = CodexStore(self.home)
        before = store.read()
        self.database(missing=('rollout_path',))
        self.assert_unavailable(store.read())
        self.database()
        self.assertEqual(store.read()['tokens'], before['tokens'])

    def test_unrecognized_usage_shape_is_unavailable_after_known_record(self):
        store = CodexStore(self.home)
        self.assertTrue(store.read()['available'])
        with self.rollout.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(dict(type='event_msg', timestamp='2026-10-05T00:00:03Z',
                payload=dict(type='token_count', info=dict(future_usage=dict(total=99)))))+'\n')
        self.assert_unavailable(store.read())

    def test_missing_and_invalid_counters_remain_nullable(self):
        for value in (None, True, '123', -1):
            tokens = dict(input_tokens=value, output_tokens=5, total_tokens=value)
            self.rollout.write_text(json.dumps(event(tokens))+'\n', encoding='utf-8')
            data = CodexStore(self.home).read()
            self.assertIsNone(data['tokens']['input_tokens'])
            self.assertIsNone(data['tokens']['total_tokens'])
            self.assertEqual(data['tokens']['output_tokens'], 5)
            self.assertEqual(data['compatibility']['status'], 'partial')

    def test_missing_ledger_preserves_usage_but_marks_partial(self):
        (self.home / 'thread_history_1.sqlite').unlink()
        data = CodexStore(self.home).read()
        self.assertEqual(data['tokens'], self.fixture['baseline_numeric_result']['tokens'])
        self.assertEqual(data['compatibility']['status'], 'partial')

    def test_update_check_is_not_misreported_as_installed_version(self):
        (self.home / 'version.json').write_text('{"latest_version":"999.0.0"}', encoding='utf-8')
        self.version_mock.return_value = None
        data = CodexStore(self.home).read()
        self.assertIsNone(data['compatibility']['codex_version'])
        self.assertEqual(data['compatibility']['writer_versions'], ['0.156.1'])

    def test_unknown_filename_does_not_crash_database_selection(self):
        (self.home / 'state_future.sqlite').write_bytes(b'unknown')
        self.assertEqual(CodexStore(self.home).read()['tokens'], self.fixture['baseline_numeric_result']['tokens'])

    def test_unknown_quota_structure_does_not_reuse_stale_limits(self):
        self.rollout.write_text(json.dumps(dict(type='event_msg', payload=dict(type='token_count',
            rate_limits=['changed'], info=event(dict(input_tokens=10, output_tokens=5, total_tokens=15))['payload']['info'])))+'\n', encoding='utf-8')
        data = CodexStore(self.home).read()
        self.assertIsNone(data['limits'])
        self.assertEqual(data['tokens']['total_tokens'], 15)
        self.assertEqual(data['compatibility']['status'], 'partial')

    def test_global_missing_source_keeps_only_explicit_partial_known_history(self):
        with closing(sqlite3.connect(self.home / 'state_5.sqlite')) as db:
            db.execute('INSERT INTO threads SELECT * FROM threads')
            db.execute('UPDATE threads SET id=?, rollout_path=? WHERE rowid=2',
                       ('absent', str(self.home / 'absent.jsonl')))
            db.commit()
        data = CodexStore(self.home).read(scope='global', include_history=True)
        self.assertTrue(data['partial'])
        self.assertTrue(all(v is None for v in data['tokens'].values()))
        self.assertEqual(data['analytics']['known']['total_tokens'], 65212)
        self.assertIsNone(data['scope_result']['analytics']['tokens']['total_tokens'])
        self.assertIsNone(data['history']['tokens']['total_tokens'])

    def test_missing_usage_file_recovers_without_poisoning_cached_analytics(self):
        store = CodexStore(self.home)
        expected = store.read()['tokens']
        self.rollout.unlink()
        self.assert_unavailable(store.read())
        self.rollout.write_bytes((self.fixture_dir / 'current-0.156.1.jsonl').read_bytes())
        self.assertEqual(store.read()['tokens'], expected)
        self.assertEqual(store.read()['compatibility']['status'], 'supported')

    def test_same_length_rewritten_log_is_reparsed(self):
        first = json.dumps(event(dict(input_tokens=10, output_tokens=5, total_tokens=15)))+'\n'
        second = json.dumps(event(dict(input_tokens=20, output_tokens=5, total_tokens=25)))+'\n'
        self.assertEqual(len(first), len(second))
        self.rollout.write_text(first, encoding='utf-8')
        store = CodexStore(self.home)
        self.assertEqual(store.read()['tokens']['total_tokens'], 15)
        self.rollout.write_text(second, encoding='utf-8')
        self.assertEqual(store.read()['tokens']['total_tokens'], 25)

    def test_version_change_with_known_schema_preserves_numbers(self):
        before = CodexStore(self.home).read()['tokens']
        self.version_mock.return_value = '0.157.0'
        store = CodexStore(self.home)
        self.assertEqual(store.read()['tokens'], before)
        self.assertEqual(store.read()['compatibility']['status'], 'supported')
        self.assertEqual(store.compatibility['codex_version'], '0.157.0')

    def test_ledger_missing_column_is_unavailable_without_losing_usage(self):
        from usage import CodexTurnLedger
        with closing(sqlite3.connect(self.home / 'thread_history_1.sqlite')) as db:
            db.execute('ALTER TABLE thread_turns DROP COLUMN status')
            db.commit()
        self.assertIsNone(CodexTurnLedger(self.home).latest_turn('codex-fixture'))
        data = CodexStore(self.home).read()
        self.assertEqual(data['compatibility']['components']['turn_ledger']['status'], 'unsupported')
        self.assertEqual(data['tokens'], self.fixture['baseline_numeric_result']['tokens'])

    def test_partial_current_scope_is_not_contaminated_by_other_working_source(self):
        from usage import CodexActivityDetector
        with closing(sqlite3.connect(self.home / 'state_5.sqlite')) as db:
            db.execute('INSERT INTO threads SELECT * FROM threads')
            db.execute('UPDATE threads SET id=?, rollout_path=? WHERE rowid=2',
                       ('other', str(self.home / 'absent.jsonl')))
            db.commit()
        task = dict(thread='other', activity_at=1)
        with patch.object(CodexActivityDetector, 'enumerate_working_tasks', return_value=[task]):
            data = CodexStore(self.home).read(pinned='codex-fixture')
        self.assertEqual(data['tokens'], self.fixture['baseline_numeric_result']['tokens'])
        self.assertEqual(data['compatibility']['status'], 'partial')

    def test_empty_rollout_path_is_unavailable(self):
        self.database(row_override={'rollout_path': ''})
        self.assert_unavailable(CodexStore(self.home).read())

    def test_sqlite_view_does_not_masquerade_as_known_table(self):
        with closing(sqlite3.connect(self.home / 'state_5.sqlite')) as db:
            db.execute('ALTER TABLE threads RENAME TO changed')
            db.execute('CREATE VIEW threads AS SELECT * FROM changed')
            db.commit()
        data = CodexStore(self.home).read()
        self.assert_unavailable(data)
        self.assertEqual(data['compatibility']['status'], 'unsupported')

    def test_version_probe_reads_installed_metadata_without_executing_cli(self):
        from codex_compat import installed_version
        package = self.home / 'node_modules' / '@openai' / 'codex' / 'package.json'
        package.parent.mkdir(parents=True)
        with patch('codex_compat.shutil.which', return_value=str(self.home / 'codex.cmd')):
            package.write_text('{"version":"0.156.1","latest_version":"999.0.0"}', encoding='utf-8')
            self.assertEqual(installed_version(), '0.156.1')
            package.write_text('{"latest_version":"999.0.0"}', encoding='utf-8')
            self.assertIsNone(installed_version())
            package.write_text('broken', encoding='utf-8')
            self.assertIsNone(installed_version())

    def test_all_sqlite_probes_are_readonly(self):
        from codex_compat import probe_database, THREAD_REQUIRED, THREAD_OPTIONAL
        connection = sqlite3.connect
        with patch('codex_compat.sqlite3.connect', wraps=connection) as connect:
            report = probe_database(self.home / 'state_5.sqlite', 'threads', THREAD_REQUIRED, THREAD_OPTIONAL)
        self.assertEqual(report['status'], 'supported')
        self.assertIn('?mode=ro', connect.call_args.args[0])
        self.assertTrue(connect.call_args.kwargs['uri'])


if __name__ == '__main__': unittest.main()
