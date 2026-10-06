"""Generate a new Windows terminal command; never start Codex in this module."""
from __future__ import annotations

import base64
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

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


def launch_command(folder, prompt, *, external_id=None):
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
    arguments = subprocess.list2cmdline(['--cd', str(project), '--', prompt])
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
