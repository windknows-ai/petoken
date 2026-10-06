import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
from pathlib import Path
import queue
import struct
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from codex_approval import CodexApprovalReader, _ControlConnection, approval_state
from tests.test_scopes import ScopeFixture


def frame(data, opcode=1, final=True):
    data = data.encode() if isinstance(data, str) else data
    size = len(data)
    length = (bytes([size]) if size < 126 else b'\x7e' + struct.pack('!H', size)
              if size < 65536 else b'\x7f' + struct.pack('!Q', size))
    return bytes([(128 if final else 0) | opcode]) + length + data


class ApprovalStateTests(unittest.TestCase):
    def test_waiting_is_explicit(self):
        for flags in (['waitingOnApproval'], ['waitingOnApproval', 'waitingOnUserInput']):
            self.assertIs(approval_state(dict(type='active', activeFlags=flags)), True)

    def test_loaded_nonwaiting_is_explicit(self):
        self.assertIs(approval_state(dict(type='idle')), False)
        for flags in ([], ['waitingOnUserInput']):
            self.assertIs(approval_state(dict(type='active', activeFlags=flags)), False)

    def test_unknown_is_not_false(self):
        for status in (None, [], {}, {'type': 'notLoaded'}, {'type': 'systemError'},
                       {'type': 'newStatus'}, {'type': 'active'},
                       {'type': 'active', 'activeFlags': 'waitingOnApproval'},
                       {'type': 'active', 'activeFlags': [True]},
                       {'type': 'active', 'activeFlags': ['futureFlag']}):
            with self.subTest(status=status):
                self.assertIsNone(approval_state(status))


class ControlConnectionTests(unittest.TestCase):
    def connection(self, data):
        process = Mock(stdin=io.BytesIO(), stdout=io.BytesIO(data))
        connection = _ControlConnection(process, time.monotonic()+1)
        self.addCleanup(connection.close)
        return connection

    def test_upgrade_checks_nonce(self):
        nonce = b'n'*16
        key = base64.b64encode(nonce).decode()
        accept = base64.b64encode(hashlib.sha1(
            (key+'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest()).decode()
        headers = f'HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: {accept}\r\n\r\n'
        connection = self.connection(headers.encode())
        with patch('codex_approval.os.urandom', return_value=nonce):
            connection.handshake()
        self.assertTrue(connection.process.stdin.getvalue().startswith(b'GET / HTTP/1.1'))

    def test_wrong_upgrade_is_rejected(self):
        for data in (b'HTTP/1.1 403 Forbidden\r\n\r\n', b'HTTP/1.1 101 Switching Protocols\r\n\r\n'):
            with self.subTest(data=data):
                with self.assertRaises(ValueError):
                    self.connection(data).handshake()

    def test_client_frames_are_masked(self):
        connection = self.connection(b'')
        for size in (10, 126, 66000):
            payload = b'x'*size
            connection._frame(payload)
            raw = connection.process.stdin.getvalue()
            connection.process.stdin.seek(0)
            connection.process.stdin.truncate(0)
            offset = 2 if size < 126 else 4 if size < 65536 else 10
            mask, encoded = raw[offset:offset+4], raw[offset+4:]
            self.assertTrue(raw[1] & 128)
            self.assertEqual(bytes(v ^ mask[i % 4] for i, v in enumerate(encoded)), payload)

    def test_fragmented_message_and_ping(self):
        data = frame('{"id":', final=False)+frame(b'ping', opcode=9)+frame('7,"result":{}}', opcode=0)
        connection = self.connection(data)
        self.assertEqual(connection.receive(), {'id': 7, 'result': {}})
        self.assertEqual(connection.process.stdin.getvalue()[0], 0x8a)

    def test_extended_response_and_ignored_server_request(self):
        data = frame(json.dumps(dict(id=99, method='item/commandExecution/requestApproval', params={})))
        data += frame(json.dumps(dict(id=3, result={'padding': 'x'*70000})))
        connection = self.connection(data)
        self.assertEqual(len(connection.request(3, 'thread/read', {})['padding']), 70000)
        raw = connection.process.stdin.getvalue()
        size, mask = raw[1] & 127, raw[2:6]
        self.assertEqual(len(raw), size+6)
        sent = json.loads(bytes(v ^ mask[i % 4] for i, v in enumerate(raw[6:])))
        self.assertEqual(sent['method'], 'thread/read')

    def test_closed_malformed_and_oversized_messages(self):
        for data in (b'', frame(b'', opcode=8), b'\x81\x7f'+struct.pack('!Q', 2**30),
                     frame('{}', opcode=0), b'\xc1\x02{}', frame('not json')):
            with self.subTest(data=data):
                with self.assertRaises((OSError, ValueError)):
                    self.connection(data).receive()

    def test_query_has_a_deadline(self):
        connection = self.connection(b'')
        connection.deadline = time.monotonic()-1
        with self.assertRaises(TimeoutError):
            connection.receive()

    def test_transport_eof_is_visible_without_a_status_query(self):
        connection = self.connection(b'')
        self.assertTrue(connection.disconnected.wait(timeout=1))
        self.assertFalse(connection.healthy())


class ApprovalReaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        path = self.home/'app-server-control/app-server-control.sock'
        path.parent.mkdir()
        path.touch()
        self.reader = CodexApprovalReader(self.home, binary='synthetic-codex.exe')
        self.addCleanup(self.reader.close)
        self.connection = Mock()
        self.connection.healthy.return_value = True
        self.popen = patch('codex_approval.subprocess.Popen', return_value=Mock()).start()
        self.addCleanup(patch.stopall)
        patch('codex_approval._ControlConnection', return_value=self.connection).start()
        self.clock = patch('codex_approval.time.monotonic', return_value=100.).start()

    def responses(self, statuses, reader=None):
        reader = reader or self.reader
        initialized = [] if reader._connection is not None else [{}]
        self.connection.request.side_effect = initialized + [{'data': list(statuses)}]+[
            {'thread': {'id': tid, 'status': status}} for tid, status in statuses.items()]

    def test_batch_is_thread_scoped_and_only_reads(self):
        self.responses({'yes': {'type': 'active', 'activeFlags': ['waitingOnApproval']},
                        'no': {'type': 'active', 'activeFlags': []},
                        'other': {'type': 'idle'}})
        self.assertEqual(self.reader.read(['yes', 'no', 'absent']),
                         {'yes': True, 'no': False, 'absent': None})
        calls = self.connection.request.call_args_list
        self.assertEqual([call.args[1] for call in calls],
                         ['initialize', 'thread/loaded/list', 'thread/read', 'thread/read'])
        self.assertTrue(all(call.args[2]['includeTurns'] is False for call in calls[2:]))
        self.assertEqual(self.popen.call_args.args[0][1:4], ['app-server', 'proxy', '--sock'])
        self.assertEqual(self.popen.call_args.kwargs['env']['CODEX_HOME'], str(self.home))
        self.connection.close.assert_not_called()

    def test_disconnect_clears_even_partially_received_true(self):
        self.connection.request.side_effect = [{}, {'data': ['yes', 'other']},
            {'thread': {'id': 'yes', 'status': {'type': 'active', 'activeFlags': ['waitingOnApproval']}}},
            queue.Empty()]
        self.assertEqual(self.reader.read(['yes', 'other']), {'yes': None, 'other': None})

    def test_no_stale_positive_on_next_poll(self):
        self.responses({'yes': {'type': 'active', 'activeFlags': ['waitingOnApproval']}})
        self.assertIs(self.reader.read(['yes'])['yes'], True)
        self.connection.request.side_effect = OSError('disconnected')
        self.clock.return_value += 5
        self.assertIsNone(self.reader.read(['yes'])['yes'])
        self.assertIsNone(self.reader.read(['yes'])['yes'])
        self.assertEqual(self.popen.call_count, 1)

    def test_same_tasks_are_cached_until_five_seconds(self):
        self.responses({'yes': {'type': 'active', 'activeFlags': ['waitingOnApproval']},
                        'no': {'type': 'idle'}})
        first = self.reader.read(['yes', 'no'])
        first['yes'] = False
        self.clock.return_value += 4.999
        self.assertEqual(self.reader.read(iter(['no', 'yes', 'yes'])),
                         {'no': False, 'yes': True})
        self.popen.assert_called_once()
        self.responses({'yes': {'type': 'idle'}, 'no': {'type': 'idle'}})
        self.clock.return_value = 105.
        self.assertEqual(self.reader.read(['yes', 'no']), {'yes': False, 'no': False})
        self.assertEqual(self.popen.call_count, 1)
        self.connection.close.assert_not_called()

    def test_sustained_polling_does_not_spawn_per_poll(self):
        for poll in range(1000):
            self.clock.return_value = 100. + poll / 100.
            self.responses({'yes': {'type': 'idle'}})
            self.assertEqual(self.reader.read(['yes']), {'yes': False})
        self.assertEqual(self.popen.call_count, 1)

    def test_concurrent_polls_share_one_query(self):
        self.responses({'yes': {'type': 'active', 'activeFlags': ['waitingOnApproval']}})
        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(lambda _: self.reader.read(['yes']), range(16)))
        self.assertEqual(results, [{'yes': True}] * 16)
        self.popen.assert_called_once()

    def test_task_changes_cannot_bypass_throttle_or_resurrect_true(self):
        self.responses({'yes': {'type': 'active', 'activeFlags': ['waitingOnApproval']}})
        self.assertEqual(self.reader.read(['yes']), {'yes': True})
        self.clock.return_value += 1
        self.assertEqual(self.reader.read(['yes', 'new']), {'yes': None, 'new': None})
        self.assertEqual(self.reader.read(['yes']), {'yes': None})
        self.popen.assert_called_once()
        self.clock.return_value = 105.
        self.responses({'yes': {'type': 'idle'}, 'new': {'type': 'idle'}})
        self.assertEqual(self.reader.read(['yes', 'new']), {'yes': False, 'new': False})
        self.assertEqual(self.popen.call_count, 1)

    def test_empty_tasks_clear_cache_without_resetting_throttle(self):
        self.responses({'yes': {'type': 'active', 'activeFlags': ['waitingOnApproval']}})
        self.assertEqual(self.reader.read(['yes']), {'yes': True})
        self.assertEqual(self.reader.read([]), {})
        self.assertEqual(self.reader.read(['yes']), {'yes': None})
        self.popen.assert_called_once()

    def test_socket_disappearance_immediately_clears_cached_true(self):
        self.responses({'yes': {'type': 'active', 'activeFlags': ['waitingOnApproval']}})
        self.assertEqual(self.reader.read(['yes']), {'yes': True})
        path = self.home/'app-server-control/app-server-control.sock'
        path.unlink()
        self.assertEqual(self.reader.read(['yes']), {'yes': None})
        path.touch()
        self.assertEqual(self.reader.read(['yes']), {'yes': None})
        self.popen.assert_called_once()

    def test_socket_replacement_immediately_clears_cached_true(self):
        self.responses({'yes': {'type': 'active', 'activeFlags': ['waitingOnApproval']}})
        self.assertEqual(self.reader.read(['yes']), {'yes': True})
        original = (self.home/'app-server-control/app-server-control.sock').stat()
        replacement = SimpleNamespace(st_dev=original.st_dev, st_ino=original.st_ino + 1,
                                      st_ctime_ns=original.st_ctime_ns)
        with patch('codex_approval.Path.stat', return_value=replacement):
            self.assertEqual(self.reader.read(['yes']), {'yes': None})
        self.assertEqual(self.reader.read(['yes']), {'yes': None})
        self.popen.assert_called_once()

    def test_socket_error_immediately_clears_cached_true(self):
        self.responses({'yes': {'type': 'active', 'activeFlags': ['waitingOnApproval']}})
        self.assertEqual(self.reader.read(['yes']), {'yes': True})
        with patch('codex_approval.Path.stat', side_effect=PermissionError('unreadable')):
            self.assertEqual(self.reader.read(['yes']), {'yes': None})
        self.assertEqual(self.reader.read(['yes']), {'yes': None})
        self.popen.assert_called_once()

    def test_failed_launch_is_throttled_and_retried(self):
        self.popen.side_effect = OSError('not executable')
        for _ in range(10):
            self.assertEqual(self.reader.read(['yes']), {'yes': None})
        self.popen.assert_called_once()
        self.clock.return_value += 5
        self.popen.side_effect = None
        self.responses({'yes': {'type': 'idle'}})
        self.assertEqual(self.reader.read(['yes']), {'yes': False})
        self.assertEqual(self.popen.call_count, 2)

    def test_unloaded_thread_does_not_keep_cached_true(self):
        self.responses({'yes': {'type': 'active', 'activeFlags': ['waitingOnApproval']}})
        self.assertEqual(self.reader.read(['yes']), {'yes': True})
        self.clock.return_value += 5
        self.responses({})
        self.assertEqual(self.reader.read(['yes']), {'yes': None})
        self.assertEqual(self.reader.read(['yes']), {'yes': None})
        self.assertEqual(self.popen.call_count, 1)

    def test_rpc_errors_and_timeouts_replace_positive_cache_with_unknown(self):
        for error in (None, {'thread': {'id': 'wrong'}}, TimeoutError('timed out'), queue.Empty()):
            with self.subTest(error=error):
                reader = CodexApprovalReader(self.home, binary='synthetic-codex.exe')
                self.addCleanup(reader.close)
                self.responses({'yes': {'type': 'active', 'activeFlags': ['waitingOnApproval']}}, reader)
                self.assertEqual(reader.read(['yes']), {'yes': True})
                self.clock.return_value += 5
                self.connection.request.side_effect = [{'data': ['yes']}, error]
                self.assertEqual(reader.read(['yes']), {'yes': None})
                launches = self.popen.call_count
                self.assertEqual(reader.read(['yes']), {'yes': None})
                self.assertEqual(self.popen.call_count, launches)

    def test_wrong_thread_or_schema_is_unknown(self):
        for response in (None, {}, {'thread': {'id': 'wrong', 'status': {'type': 'idle'}}},
                         {'thread': {'id': 'yes', 'status': {'type': 'notLoaded'}}}):
            self.clock.return_value += 5
            self.connection.request.side_effect = [{}, {'data': ['yes']}, response]
            self.assertIsNone(self.reader.read(['yes'])['yes'])
        self.assertEqual(self.popen.call_count, 4)

    def test_missing_socket_empty_tasks_and_missing_binary_do_not_launch(self):
        self.assertEqual(self.reader.read([]), {})
        with patch('codex_approval._proxy_binary', return_value=None):
            self.assertEqual(CodexApprovalReader(self.home).read(['yes']), {'yes': None})
        (self.home/'app-server-control/app-server-control.sock').unlink()
        self.assertEqual(self.reader.read(['yes']), {'yes': None})
        self.popen.assert_not_called()

    def test_process_failure_is_unknown(self):
        self.popen.side_effect = OSError('not executable')
        self.assertEqual(self.reader.read(['yes']), {'yes': None})

    def test_invalid_loaded_list_cannot_borrow_another_threads_status(self):
        for loaded in (None, {}, {'data': {}}, {'data': [True]}, {'data': [{'id': 'yes'}]}):
            self.clock.return_value += 5
            self.connection.request.side_effect = [{}, loaded]
            self.assertEqual(self.reader.read(['yes']), {'yes': None})
        self.assertEqual(self.popen.call_count, 5)

    def test_unreadable_socket_is_unknown(self):
        with patch('codex_approval.Path.stat', side_effect=PermissionError('unreadable')):
            self.assertEqual(self.reader.read(['yes']), {'yes': None})
        self.popen.assert_not_called()

    def test_reuse_across_a_minute_has_unique_ids_and_fresh_deadlines(self):
        ids = []
        for second in range(0, 61, 5):
            self.clock.return_value = 100. + second
            self.responses({'yes': {'type': 'active', 'activeFlags': ['waitingOnApproval']}})
            self.assertEqual(self.reader.read(['yes']), {'yes': True})
            if second:
                self.assertEqual(self.connection.deadline, 100. + second + .75)
        ids = [call.args[0] for call in self.connection.request.call_args_list]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual([c.args[1] for c in self.connection.request.call_args_list].count('initialize'), 1)
        self.popen.assert_called_once()
        self.connection.handshake.assert_called_once()

    def test_dead_proxy_immediately_clears_true_and_retries_only_after_interval(self):
        self.responses({'yes': {'type': 'active', 'activeFlags': ['waitingOnApproval']}})
        self.assertEqual(self.reader.read(['yes']), {'yes': True})
        self.connection.healthy.return_value = False
        self.clock.return_value += 1
        self.assertEqual(self.reader.read(['yes']), {'yes': None})
        self.connection.close.assert_called_once()
        self.popen.assert_called_once()
        self.clock.return_value = 105.
        self.connection.healthy.return_value = True
        self.responses({'yes': {'type': 'idle'}})
        self.assertEqual(self.reader.read(['yes']), {'yes': False})
        self.assertEqual(self.popen.call_count, 2)

    def test_empty_or_close_disposes_once_without_killing_server(self):
        self.responses({'yes': {'type': 'idle'}})
        self.reader.read(['yes'])
        self.reader.read([])
        self.reader.close()
        self.reader.close()
        self.connection.close.assert_called_once()
        self.assertIsNone(self.reader._connection)
        self.clock.return_value = 105.
        self.responses({'yes': {'type': 'idle'}})
        self.assertEqual(self.reader.read(['yes']), {'yes': False})
        self.assertEqual(self.popen.call_count, 2)

    def test_rpc_error_after_partial_positive_closes_and_clears_batch(self):
        self.responses({'yes': {'type': 'idle'}, 'other': {'type': 'idle'}})
        self.reader.read(['yes','other'])
        self.clock.return_value = 105.
        self.connection.request.side_effect = [{'data':['yes','other']},
            {'thread': {'id':'yes','status':{'type':'active','activeFlags':['waitingOnApproval']}}}, None]
        self.assertEqual(self.reader.read(['yes','other']), {'yes':None,'other':None})
        self.connection.close.assert_called_once()
        self.assertIsNone(self.reader._connection)


class UsageApprovalIntegrationTests(unittest.TestCase):
    def test_usage_polls_reuse_the_readers_throttled_snapshot(self):
        with tempfile.TemporaryDirectory() as root:
            fixture = ScopeFixture(root)
            fixture.add('synthetic', 'Synthetic', 100, working=True)
            store = fixture.finish()
            self.addCleanup(store.approval.close)
            path = Path(root)/'app-server-control/app-server-control.sock'
            path.parent.mkdir()
            path.touch()
            store.approval.binary = 'synthetic-codex.exe'
            connection = Mock()
            connection.request.side_effect = [{}, {'data': ['synthetic']},
                {'thread': {'id': 'synthetic', 'status':
                            {'type': 'active', 'activeFlags': ['waitingOnApproval']}}}]
            with patch('codex_approval.time.monotonic', return_value=100.) as clock, \
                    patch('codex_approval.subprocess.Popen', return_value=Mock()) as popen, \
                    patch('codex_approval._ControlConnection', return_value=connection):
                first = store.read(scope='global')
                for _ in range(4):
                    clock.return_value += 1
                    current = store.read(scope='global')
                    self.assertEqual(current['tokens'], first['tokens'])
                    self.assertEqual(current['active_tasks'], first['active_tasks'])
                    self.assertIs(current['active_tasks'][0]['awaiting_approval'], True)
                self.assertEqual(popen.call_count, 1)
                clock.return_value = 105.
                connection.request.side_effect = OSError('disconnected')
                current = store.read(scope='global')
                self.assertIsNone(current['active_tasks'][0]['awaiting_approval'])
                self.assertEqual(current['tokens'], first['tokens'])
                self.assertEqual(popen.call_count, 1)

    def test_new_field_is_additive_for_desktop_vscode_cli_and_exec(self):
        with tempfile.TemporaryDirectory() as root:
            fixture = ScopeFixture(root)
            for source in ('desktop', 'vscode', 'cli', 'exec'):
                fixture.add(source, source, 100, working=True)
                fixture.rows[-1]['source'] = source
            store = fixture.finish()
            before = store.read(scope='global')
            with patch.object(store.approval, 'read', return_value={
                    'desktop': True, 'vscode': False, 'cli': None, 'exec': False}) as reader:
                after = store.read(scope='global')
            self.assertEqual(before['tokens'], after['tokens'])
            self.assertEqual({t['task_key']: t['awaiting_approval'] for t in after['active_tasks']},
                             {'desktop': True, 'vscode': False, 'cli': None, 'exec': False})
            for old, new in zip(before['active_tasks'], after['active_tasks']):
                self.assertEqual({k: v for k, v in old.items() if k != 'awaiting_approval'},
                                 {k: v for k, v in new.items() if k != 'awaiting_approval'})
            reader.assert_called_once()

    def test_quiet_or_escalation_tool_call_never_proves_approval(self):
        with tempfile.TemporaryDirectory() as root:
            fixture = ScopeFixture(root)
            fixture.add('synthetic', 'Synthetic', 100, working=True)
            path = Path(fixture.rows[-1]['rollout_path'])
            with path.open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(dict(type='response_item', payload=dict(type='function_call',
                    name='exec_command', arguments=json.dumps(dict(sandbox_permissions='require_escalated')))))+'\n')
            task = fixture.finish().read()['active_tasks'][0]
            self.assertIsNone(task['awaiting_approval'])


if __name__ == '__main__':
    unittest.main()
