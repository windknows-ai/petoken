"""Desktop adapters: accessibility title, official quota RPC, public FX data."""
from __future__ import annotations

import ctypes
import json
import os
import queue
import shutil
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

from app_config import APP_VERSION


def codex_executable():
    base = Path(os.environ.get('LOCALAPPDATA', ''))/'OpenAI/Codex/bin'
    candidates = list(base.glob('*/codex.exe'))
    if candidates:
        return str(max(candidates, key=lambda p: p.stat().st_mtime))
    npm = Path(os.environ.get('APPDATA', ''))/'npm/node_modules/@openai/codex'
    candidates = list(npm.glob('**/bin/codex.exe'))
    return str(candidates[0]) if candidates else shutil.which('codex.exe')


def is_codex_window(pid):
    kernel = ctypes.windll.kernel32
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.QueryFullProcessImageNameW.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_uint32)]
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        return False
    try:
        buffer = ctypes.create_unicode_buffer(32768)
        size = ctypes.c_uint32(len(buffer))
        if not kernel.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return False
        path = buffer.value.lower()
        return 'openai.codex' in path or '\\codex\\' in path or Path(path).name == 'codex.exe'
    finally:
        kernel.CloseHandle(handle)


class ActiveTask:
    def __init__(self):
        self.title = ''
        self.seen = 0
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True, name='codex-accessibility')

    def start(self):
        self.thread.start()

    def run(self):
        if os.name != 'nt':
            return
        import uiautomation as auto
        with auto.UIAutomationInitializerInThread():
            auto.SetGlobalSearchTimeout(.25)
            while not self.stop.is_set():
                try:
                    windows = [w for w in auto.GetRootControl().GetChildren()
                               if w.Name in ('ChatGPT', 'Codex') and is_codex_window(w.ProcessId)]
                    foreground = ctypes.windll.user32.GetForegroundWindow()
                    windows.sort(key=lambda w: w.NativeWindowHandle != foreground)
                    title = ''
                    for w in windows:
                        doc = w.DocumentControl(searchDepth=10)
                        if doc.Exists(0, 0):
                            # Value contains the launch URL, not the active SPA route.
                            title = doc.GetLegacyIAccessiblePattern().Name or doc.Name
                            if title:
                                break
                    self.title = title
                    self.seen = time.time()
                except Exception:
                    self.title = ''
                self.stop.wait(1)


class RateLimits:
    def __init__(self, callback, home=None):
        self.callback = callback
        self.home = home
        self.stop = threading.Event()
        self.process = None
        self.counter = 0
        self.thread = threading.Thread(target=self.run, daemon=True, name='codex-quotas')

    def start(self):
        self.thread.start()

    def request(self, method, params):
        self.counter += 1
        request_id = self.counter
        self.process.stdin.write(json.dumps(dict(id=request_id, method=method, params=params))+'\n')
        self.process.stdin.flush()
        deadline = time.monotonic()+10
        while not self.stop.is_set():
            if time.monotonic() >= deadline:
                raise TimeoutError('quota RPC timed out')
            try:
                response = self.responses.get(timeout=.25)
            except queue.Empty:
                if self.process.poll() is not None:
                    raise OSError('Codex sidecar exited')
                continue
            if response.get('id') == request_id:
                if 'error' in response:
                    raise OSError('quota RPC unavailable')
                return response['result']
        raise OSError('stopped')

    @staticmethod
    def read_responses(process, responses):
        try:
            for line in process.stdout:
                try:
                    data = json.loads(line)
                    if 'id' in data:
                        responses.put(data)
                except ValueError:
                    pass
        except (OSError, ValueError):
            pass

    def cleanup(self):
        p = self.process
        if p is not None:
            try:
                p.terminate()
                p.wait(timeout=2)
            except subprocess.TimeoutExpired:
                p.kill()
            except OSError:
                pass
            for stream in (p.stdin, p.stdout):
                try:
                    stream.close()
                except (OSError, ValueError):
                    pass
            self.process = None

    def run(self):
        while not self.stop.is_set():
            try:
                binary = codex_executable()
                if not binary:
                    raise FileNotFoundError('Codex executable missing')
                env = os.environ.copy()
                if self.home:
                    env['CODEX_HOME'] = str(self.home)
                self.process = subprocess.Popen([binary, 'app-server'], stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding='utf-8',
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0, env=env)
                self.responses = queue.Queue()
                threading.Thread(target=self.read_responses, args=(self.process,self.responses), daemon=True).start()
                self.request('initialize', {'clientInfo': {'name': 'codex_wisp', 'version': APP_VERSION}})
                self.process.stdin.write('{"method":"initialized"}\n')
                self.process.stdin.flush()
                while not self.stop.is_set():
                    start = time.monotonic()
                    result = self.request('account/rateLimits/read', {})
                    buckets = result.get('rateLimitsByLimitId') or {}
                    limits = buckets.get('codex') or result.get('rateLimits')
                    self.callback(dict(limits=limits, sampled=time.time(), error=''))
                    self.stop.wait(max(0, 1-(time.monotonic()-start)))
            except Exception:
                if not self.stop.is_set():
                    self.callback(dict(error='额度暂不可用；保留上次读数，15 秒后重试。'))
            finally:
                self.cleanup()
            self.stop.wait(15)

    def close(self):
        self.stop.set()
        p = self.process
        if p:
            try:
                p.terminate()
            except OSError:
                pass
        self.thread.join(timeout=3)


FX_URL = 'https://www.bankofcanada.ca/valet/observations/FXUSDCAD/json?recent=1'


def fetch_fx():
    request = urllib.request.Request(FX_URL, headers={'User-Agent': 'Codex-Wisp/1.0'})
    with urllib.request.urlopen(request, timeout=10) as response:
        data = json.load(response)
    observation = data['observations'][-1]
    rate = float(observation['FXUSDCAD']['v'])
    if not 0 < rate < 10:
        raise ValueError('Invalid USD/CAD rate')
    return dict(rate=rate, date=observation['d'], source='Bank of Canada')
