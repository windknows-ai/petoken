"""Read runtime approval state from an existing local Codex control socket.

No daemon startup, thread resume, subscriptions, or approval decisions. The
native Codex proxy preserves the server's private Unix-socket access checks.
Queries keep short-lived proxies because the store has no connection teardown
hook; snapshots and failed attempts are throttled within each reader instead.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import queue
import shutil
import struct
import subprocess
import threading
import time


def approval_state(status):
    """Tri-state result from an explicit, loaded runtime status only."""
    if not isinstance(status, dict):
        return None
    kind = status.get('type')
    if kind == 'idle':
        return False
    if kind != 'active':
        return None  # notLoaded is not proof about another server's task.
    flags = status.get('activeFlags')
    if not isinstance(flags, list) or not all(isinstance(f, str) for f in flags):
        return None
    if 'waitingOnApproval' in flags:
        return True
    if any(f != 'waitingOnUserInput' for f in flags):
        return None
    return False


def _proxy_binary():
    executable = shutil.which('codex.exe' if os.name == 'nt' else 'codex')
    if executable:
        return executable
    if os.name == 'nt' and os.environ.get('APPDATA'):
        binary = (Path(os.environ['APPDATA']) / 'npm/node_modules/@openai/codex/node_modules/'
                  '@openai/codex-win32-x64/vendor/x86_64-pc-windows-msvc/bin/codex.exe')
        if binary.is_file():
            return str(binary)
    return None


class _ControlConnection:
    MAX_MESSAGE = 1024 * 1024
    MAX_HEADERS = 8192

    def __init__(self, process, deadline):
        self.process, self.deadline = process, deadline
        self.buffer = bytearray()
        self.blocks = queue.Queue(maxsize=32)
        self.stopped = threading.Event()
        self.reader = threading.Thread(target=self._pump, daemon=True)
        self.reader.start()

    def _pump(self):
        try:
            while not self.stopped.is_set():
                block = self.process.stdout.read1(16384)
                while not self.stopped.is_set():
                    try:
                        self.blocks.put(block, timeout=.05)
                        break
                    except queue.Full:
                        continue
                if not block:
                    break
        except (OSError, ValueError):
            if not self.stopped.is_set():
                try:
                    self.blocks.put_nowait(b'')
                except queue.Full:
                    pass

    def _exact(self, size):
        while len(self.buffer) < size:
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('Codex status query timed out')
            block = self.blocks.get(timeout=remaining)
            if not block:
                raise OSError('Codex control connection closed')
            self.buffer.extend(block)
        data = bytes(self.buffer[:size])
        del self.buffer[:size]
        return data

    def _write(self, data):
        self.process.stdin.write(data)
        self.process.stdin.flush()

    def handshake(self):
        key = base64.b64encode(os.urandom(16)).decode('ascii')
        self._write(('GET / HTTP/1.1\r\nHost: localhost\r\nUpgrade: websocket\r\n'
                     'Connection: Upgrade\r\nSec-WebSocket-Version: 13\r\n'
                     f'Sec-WebSocket-Key: {key}\r\n\r\n').encode('ascii'))
        header = bytearray()
        while not header.endswith(b'\r\n\r\n'):
            if len(header) >= self.MAX_HEADERS:
                raise ValueError('Oversized WebSocket upgrade')
            header.extend(self._exact(1))
        lines = header.decode('ascii').split('\r\n')
        fields = {k.lower(): v.strip() for line in lines[1:] if ':' in line
                  for k, v in [line.split(':', 1)]}
        expected = base64.b64encode(hashlib.sha1(
            (key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode('ascii')).digest()).decode('ascii')
        if (lines[0].split()[1] != '101' or fields.get('sec-websocket-accept') != expected
                or fields.get('upgrade', '').lower() != 'websocket'
                or 'upgrade' not in [v.strip() for v in fields.get('connection', '').lower().split(',')]
                or fields.get('sec-websocket-extensions')):
            raise ValueError('Invalid WebSocket upgrade')

    def _frame(self, payload, opcode=1):
        size, mask = len(payload), os.urandom(4)
        length = (bytes([0x80 | size]) if size < 126 else b'\xfe' + struct.pack('!H', size)
                  if size < 65536 else b'\xff' + struct.pack('!Q', size))
        self._write(bytes([0x80 | opcode]) + length + mask
                    + bytes(value ^ mask[i % 4] for i, value in enumerate(payload)))

    def send(self, message):
        self._frame(json.dumps(message).encode('utf-8'))

    def receive(self):
        payload = bytearray()
        fragmented = False
        while True:
            if time.monotonic() >= self.deadline:
                raise TimeoutError('Codex status query timed out')
            first, second = self._exact(2)
            opcode, final, size = first & 15, bool(first & 128), second & 127
            if first & 112 or second & 128:
                raise ValueError('Unsupported WebSocket frame')
            if size == 126:
                size = struct.unpack('!H', self._exact(2))[0]
            elif size == 127:
                size = struct.unpack('!Q', self._exact(8))[0]
            if size > self.MAX_MESSAGE or len(payload) + size > self.MAX_MESSAGE:
                raise ValueError('Oversized status response')
            block = self._exact(size)
            if opcode == 8:
                raise OSError('Codex control connection closed')
            if opcode in (9, 10):
                if not final or size > 125:
                    raise ValueError('Invalid WebSocket control frame')
                if opcode == 9:
                    self._frame(block, 10)
                continue
            if opcode == 1 and not fragmented:
                fragmented = True
            elif opcode != 0 or not fragmented:
                raise ValueError('Invalid WebSocket message')
            payload.extend(block)
            if final:
                return json.loads(payload.decode('utf-8'))

    def request(self, number, method, params):
        self.send(dict(id=number, method=method, params=params))
        while True:
            if time.monotonic() >= self.deadline:
                raise TimeoutError('Codex status query timed out')
            message = self.receive()
            if isinstance(message, dict) and message.get('id') == number and 'method' not in message:
                if 'error' in message:
                    return None
                return message.get('result')
            # Never answer server requests or retain notification contents.

    def close(self):
        self.stopped.set()
        try:
            self.process.terminate()
            try:
                self.process.wait(timeout=.2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=.2)
        except (OSError, subprocess.TimeoutExpired):
            pass
        self.reader.join(timeout=.2)
        for stream in (self.process.stdin, self.process.stdout):
            try:
                stream.close()
            except (OSError, ValueError):
                pass


class CodexApprovalReader:
    QUERY_INTERVAL = 5.

    def __init__(self, home, *, binary=None, timeout=.75):
        self.home = Path(home).absolute()
        self.binary, self.timeout = binary, timeout
        self._lock = threading.Lock()
        self._next_query = 0.
        self._states = {}
        self._socket_identity = None

    def read(self, thread_ids):
        """Return a copied snapshot, querying at most once per five seconds.

        Task/endpoint changes discard the snapshot without bypassing the
        throttle. An unobservable disconnect is detected on the next query.
        """
        states = {tid: None for tid in thread_ids if isinstance(tid, str) and tid}
        path = self.home / 'app-server-control/app-server-control.sock'
        with self._lock:
            if not states:
                self._states = {}
                self._socket_identity = None
                return states
            try:
                stat = path.stat()
            except OSError:
                self._states = dict(states)
                self._socket_identity = None
                return states
            identity = (stat.st_dev, stat.st_ino, stat.st_ctime_ns)
            if identity != self._socket_identity or states.keys() != self._states.keys():
                self._states = dict(states)
            self._socket_identity = identity
            now = time.monotonic()
            if now >= self._next_query:
                # Failed attempts are throttled too; clear old positives first.
                self._next_query = now + self.QUERY_INTERVAL
                self._states = dict(states)
                self._states = self._query(states, path)
            return dict(self._states)

    def _query(self, states, path):
        connection = None
        try:
            binary = self.binary or _proxy_binary()
            if not binary:
                return states
            process = subprocess.Popen([str(binary), 'app-server', 'proxy', '--sock', str(path)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                env=dict(os.environ, CODEX_HOME=str(self.home)),
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            connection = _ControlConnection(process, time.monotonic() + self.timeout)
            connection.handshake()
            if not isinstance(connection.request(1, 'initialize',
                    dict(clientInfo=dict(name='petoken_approval_reader', version='1.6'))), dict):
                return states
            connection.send(dict(method='initialized', params={}))
            loaded = connection.request(2, 'thread/loaded/list', {})
            ids = loaded.get('data') if isinstance(loaded, dict) else None
            if not isinstance(ids, list) or not all(isinstance(tid, str) for tid in ids):
                return states
            for number, tid in enumerate((tid for tid in ids if tid in states and len(tid) <= 128), 3):
                result = connection.request(number, 'thread/read', dict(threadId=tid, includeTurns=False))
                thread = result.get('thread') if isinstance(result, dict) else None
                if isinstance(thread, dict) and thread.get('id') == tid:
                    states[tid] = approval_state(thread.get('status'))
        except (OSError, ValueError, TypeError, KeyError, IndexError, queue.Empty, TimeoutError):
            return dict.fromkeys(states)  # Never keep a prior True after disconnect/error.
        finally:
            if connection is not None:
                connection.close()
        return states
