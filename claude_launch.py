"""Start Claude Code on a prompt in a new terminal (V1.6 C: quick launch).

Builds the argv for ``subprocess.Popen(argv, shell=False)``: Windows
Terminal when installed, otherwise a PowerShell window, running the native
``claude.exe`` interactively in the project folder with the prompt as its
first message (``claude -- <prompt>``). The prompt and folder travel as
UTF-8 JSON inside an encoded script and reach Claude Code through
ProcessStartInfo, so quotes, semicolons and other characters in the prompt
are never interpreted by a shell. No permission flags are added: Claude
Code asks exactly as it normally would. Same approach as codex_launch.
"""
from __future__ import annotations

import base64
import json
import shutil
import subprocess
import sys
from pathlib import Path

MAX_COMMAND = 32767


def executable():
    """The native Claude Code CLI, or None (wrapper scripts are not used)."""
    if sys.platform != 'win32':
        return None
    found = shutil.which('claude.exe')
    if not found:
        candidate = Path.home() / '.local' / 'bin' / 'claude.exe'
        found = str(candidate) if candidate.is_file() else None
    return found if found and Path(found).suffix.lower() == '.exe' else None


def _shell():
    return shutil.which('powershell.exe') or shutil.which('pwsh.exe')


def available():
    return bool(executable() and _shell())


def _encoded_script(payload):
    data = base64.b64encode(json.dumps(payload, ensure_ascii=False).encode('utf-8')).decode('ascii')
    script = """$ErrorActionPreference = 'Stop'
$payload = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('DATA')) | ConvertFrom-Json
Set-Location -LiteralPath $payload.folder
$start = New-Object System.Diagnostics.ProcessStartInfo
$start.FileName = $payload.executable
$start.Arguments = $payload.arguments
$start.WorkingDirectory = $payload.folder
$start.UseShellExecute = $false
$taskProcess = [System.Diagnostics.Process]::Start($start)
$taskProcess.WaitForExit()
""".replace('DATA', data)
    return base64.b64encode(script.encode('utf-16le')).decode('ascii')


def launch_command(folder, prompt, cli=None, shell=None, terminal=None):
    """argv for Popen(shell=False); raises ValueError / RuntimeError."""
    if not isinstance(prompt, str) or not prompt.strip() or '\0' in prompt:
        raise ValueError('A nonempty prompt without NUL is required')
    try:
        project = Path(folder).resolve(strict=True)
    except (TypeError, ValueError, OSError) as error:
        raise ValueError('An existing project folder is required') from error
    if not project.is_dir():
        raise ValueError('An existing project folder is required')
    cli = cli or executable()
    shell = shell or _shell()
    if not cli or not shell:
        raise RuntimeError('Claude Code CLI and Windows PowerShell are required')
    arguments = subprocess.list2cmdline(['--', prompt])
    encoded = _encoded_script(dict(executable=cli, folder=str(project), arguments=arguments))
    command = [shell, '-NoLogo', '-NoProfile', '-NoExit', '-EncodedCommand', encoded]
    terminal = terminal if terminal is not None else shutil.which('wt.exe')
    if terminal:
        command = [terminal, '--window', 'new', 'new-tab', '--startingDirectory', str(project), *command]
    if len(subprocess.list2cmdline(command)) + 1 > MAX_COMMAND:
        raise ValueError('The prompt is too long for a Windows command line')
    return command


def launch(argv):
    """Start ``argv`` in its own console window."""
    flags = getattr(subprocess, 'CREATE_NEW_CONSOLE', 0)
    # No std redirection: the PowerShell fallback must write to its own console.
    return subprocess.Popen(argv, shell=False, creationflags=flags, close_fds=True)
