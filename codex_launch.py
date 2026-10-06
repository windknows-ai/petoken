"""Generate terminal argv; never start a task in this module.

options() queries the native CLI's official app-server model/list, not a guessed
or hard-coded cache. Codex handles catalog config, cache identity, account and
picker visibility. Failure returns empty lists; no stale result is reused.
Each discovery owns a short-lived process with a three-second query deadline.
Efforts are the visible models' ordered union; explicit model/effort pairs must
also be supported by that model. Project-specific provider overrides may differ
from this user-level catalog. No configuration or conversation is changed here.

Protocol: https://learn.chatgpt.com/docs/app-server#list-models-modellist
CLI flags: https://learn.chatgpt.com/docs/developer-commands
"""
from __future__ import annotations

import base64
import json
from pathlib import Path
import queue
import re
import shutil
import subprocess
import sys
import threading
import time

from codex_approval import _proxy_binary


def _executables():
    if sys.platform != 'win32':
        return None, None
    cli = _proxy_binary()
    # A native executable avoids .cmd/.ps1 wrapper shell interpretation.
    if not cli or Path(cli).suffix.lower() != '.exe' or not Path(cli).is_file():
        cli = None
    shell = shutil.which('powershell.exe') or shutil.which('pwsh.exe')
    return cli, shell


def available():
    """Native CLI and PowerShell are present; login/network health is not probed."""
    cli, shell = _executables()
    return bool(cli and shell)


def _model_catalog():
    """Ordered {model: efforts}, using only model discovery on an owned server."""
    cli, _ = _executables()
    if not cli:
        return {}
    process, reader = None, None
    stopped = threading.Event()
    lines = queue.Queue(maxsize=32)
    deadline = time.monotonic() + 3.
    try:
        process = subprocess.Popen([cli, 'app-server', '--listen', 'stdio://'],
            cwd=Path.home(), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))

        def pump():
            try:
                while not stopped.is_set():
                    raw = process.stdout.readline(1024 * 1024 + 1)
                    if len(raw) > 1024 * 1024:
                        raw = b''
                    while not stopped.is_set():
                        try:
                            lines.put(raw, timeout=.05)
                            break
                        except queue.Full:
                            continue
                    if not raw:
                        break
            except (OSError, ValueError):
                try:
                    lines.put_nowait(b'')
                except queue.Full:
                    pass

        reader = threading.Thread(target=pump, daemon=True)
        reader.start()

        def send(message):
            process.stdin.write((json.dumps(message)+'\n').encode('utf-8'))
            process.stdin.flush()

        def request(number, method, params):
            send(dict(id=number, method=method, params=params))
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError('Model discovery timed out')
                raw = lines.get(timeout=remaining)
                if not raw:
                    raise OSError('Model discovery connection closed')
                message = json.loads(raw.decode('utf-8'))
                if isinstance(message, dict) and message.get('id') == number and 'method' not in message:
                    if 'error' in message or not isinstance(message.get('result'), dict):
                        raise ValueError('Model discovery unavailable')
                    return message['result']
                # Discovery does not answer server requests or start/resume threads.

        request(1, 'initialize', dict(clientInfo=dict(name='petoken_launch_options', version='1.7')))
        send(dict(method='initialized', params={}))
        catalog, cursors, cursor, number = {}, set(), None, 2
        while True:
            result = request(number, 'model/list', dict(limit=100, includeHidden=False, cursor=cursor))
            rows = result.get('data')
            if not isinstance(rows, list):
                raise ValueError('Unknown model list')
            for row in rows:
                if not isinstance(row, dict) or not isinstance(row.get('hidden'), bool):
                    raise ValueError('Unknown model visibility')
                if row['hidden']:
                    continue
                model, levels = row.get('model'), row.get('supportedReasoningEfforts')
                if (not isinstance(model, str) or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}', model) is None
                        or not isinstance(levels, list)):
                    raise ValueError('Unknown model capabilities')
                efforts = []
                for level in levels:
                    effort = level.get('reasoningEffort') if isinstance(level, dict) else None
                    if not isinstance(effort, str) or re.fullmatch(r'[a-z][a-z0-9_]{0,31}', effort) is None:
                        raise ValueError('Unknown effort')
                    if effort not in efforts:
                        efforts.append(effort)
                if model in catalog and catalog[model] != efforts:
                    raise ValueError('Conflicting model capabilities')
                catalog[model] = efforts
            cursor = result.get('nextCursor')
            if cursor is None:
                return catalog
            if not isinstance(cursor, str) or not cursor or cursor in cursors or len(cursors) >= 100:
                raise ValueError('Unknown model pagination')
            cursors.add(cursor)
            number += 1
    except (OSError, ValueError, TypeError, queue.Empty, TimeoutError):
        return {}
    finally:
        stopped.set()
        if process is not None:
            try:
                process.terminate()
                try:
                    process.wait(timeout=.2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=.2)
            except (OSError, subprocess.TimeoutExpired):
                pass
            if reader is not None:
                reader.join(timeout=.2)
            for stream in (process.stdin, process.stdout):
                if stream is not None:
                    try:
                        stream.close()
                    except OSError:
                        pass


def _choice_lists(catalog):
    return dict(models=list(catalog), efforts=list(dict.fromkeys(
        effort for levels in catalog.values() for effort in levels)))


def options():
    """Visible model IDs and union of their efforts; unavailable => two empty lists.

    Models are ordered by Codex's picker; per-model effort order is preserved.
    Only discovery is performed, never inference, approval or a config write.
    """
    return _choice_lists(_model_catalog())


def _encoded_script(payload):
    data = base64.b64encode(json.dumps(payload, ensure_ascii=False).encode('utf-8')).decode('ascii')
    # User text is JSON data, never PowerShell source. ProcessStartInfo.Arguments
    # avoids PowerShell 5.1's lossy native-argument reconstruction for quotes.
    script = """$ErrorActionPreference = 'Stop'
$payload = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('DATA')) | ConvertFrom-Json
Set-Location -LiteralPath $payload.folder
$start = New-Object System.Diagnostics.ProcessStartInfo
$start.FileName = $payload.executable
$start.Arguments = $payload.arguments
$start.WorkingDirectory = $payload.folder
$start.UseShellExecute = $false
$start.CreateNoWindow = $false
$start.EnvironmentVariables.Remove('PETOKEN_TODO_ID')
if ($payload.external_id) { $start.EnvironmentVariables['PETOKEN_TODO_ID'] = $payload.external_id }
$taskProcess = [System.Diagnostics.Process]::Start($start)
$taskProcess.WaitForExit()
""".replace('DATA', data)
    return base64.b64encode(script.encode('utf-16le')).decode('ascii')


def launch_command(folder, prompt, *, external_id=None, model=None, effort=None):
    """Return argv for subprocess.Popen(argv, shell=False), or raise on invalid input.

    PowerShell's standalone window requires CREATE_NEW_CONSOLE when the caller
    starts this argv from a process that already has a console.
    """
    if not isinstance(prompt, str) or not prompt.strip() or '\0' in prompt:
        raise ValueError('A nonempty prompt without NUL is required')
    if external_id is not None and (not isinstance(external_id, str)
            or re.fullmatch(r'[A-Za-z0-9._:-]{1,128}', external_id) is None):
        raise ValueError('External ID must be a metadata identifier of 1 to 128 characters')
    if isinstance(folder, str) and not folder.strip():
        raise ValueError('An existing project directory is required')
    try:
        project = Path(folder).resolve(strict=True)
    except (TypeError, ValueError, OSError) as error:
        raise ValueError('An existing project directory is required') from error
    if not project.is_dir():
        raise ValueError('An existing project directory is required')
    cli, shell = _executables()
    if not cli or not shell:
        raise RuntimeError('Native Codex CLI and Windows PowerShell are required')
    argv = ['--cd', str(project)]
    if model is not None or effort is not None:
        catalog = _model_catalog()
        choices = _choice_lists(catalog)
        if model is not None and (not isinstance(model, str) or model not in choices['models']):
            raise ValueError('Model is not available in the Codex picker')
        if effort is not None and (not isinstance(effort, str) or effort not in choices['efforts']):
            raise ValueError('Reasoning effort is not available in the Codex picker')
        if model is not None and effort is not None and effort not in catalog[model]:
            raise ValueError('Reasoning effort is not supported by the selected Codex model')
        if model is not None:
            argv.extend(['-m', model])
        if effort is not None:
            argv.extend(['-c', f'model_reasoning_effort={json.dumps(effort)}'])
    arguments = subprocess.list2cmdline([*argv, '--', prompt])
    encoded = _encoded_script(dict(executable=cli, folder=str(project), arguments=arguments,
                                  external_id=external_id))
    command = [shell, '-NoLogo', '-NoProfile', '-NoExit', '-EncodedCommand', encoded]
    terminal = shutil.which('wt.exe')
    if terminal:
        # No raw user text reaches wt's semicolon-based command grammar.
        command = [terminal, '--window', 'new', 'new-tab', *command]
    if len(subprocess.list2cmdline(command).encode('utf-16le')) // 2 + 1 > 32767:
        raise ValueError('Encoded command exceeds the Windows command-line limit')
    return command
