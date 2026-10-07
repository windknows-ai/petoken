"""Opt-in Claude Code status-line bridge for subscription usage (V1.5).

Claude Code publishes the account's 5-hour and 7-day usage only to a
configured status-line command (claude.ai Pro/Max subscribers). When the
user turns the bridge on in Settings, Petoken installs a small PowerShell
script and points Claude Code's ``statusLine`` setting at it. On every
update the script keeps a few numbers — usage percentages, reset times
and the context window of that session — in
``%LOCALAPPDATA%\\CodexWisp\\claude-status\\<session>.json`` and prints a
one-line status. No conversation content, path or credential is written.

Safety rules: the user's ``settings.json`` is backed up first and only the
``statusLine`` key is changed; an existing custom status line is never
overwritten; turning the bridge off removes the key only while it still
points at Petoken's script. Windows only (PowerShell ships with Windows),
so no Python or Petoken path is needed when Claude Code runs it.
"""
from __future__ import annotations

import json
import os
import shutil
import time
from datetime import datetime
from pathlib import Path

SCRIPT_NAME = 'claude-statusline.ps1'
STATUS_DIRNAME = 'claude-status'
MARKER = 'petoken-claude-statusline'
# A snapshot older than this no longer describes the live window reliably.
SNAPSHOT_MAX_AGE_S = 6 * 3600

_SCRIPT = r'''# petoken-claude-statusline: written by Petoken. Keeps only usage numbers.
$ErrorActionPreference = 'SilentlyContinue'
# Read stdin as UTF-8 without touching the console's code pages, which
# Claude Code's own terminal shares with this script.
$reader = New-Object System.IO.StreamReader([Console]::OpenStandardInput(), [Text.Encoding]::UTF8)
$raw = $reader.ReadToEnd()
$data = $raw | ConvertFrom-Json
if ($null -eq $data) { exit 0 }
$folder = Join-Path $env:LOCALAPPDATA 'CodexWisp\claude-status'
New-Item -ItemType Directory -Force -Path $folder | Out-Null
$session = [string]$data.session_id
if ($session -notmatch '^[A-Za-z0-9._-]{1,128}$') { $session = 'unknown' }
function Window($w) {
    if ($null -eq $w) { return $null }
    return [ordered]@{ used_percentage = $w.used_percentage; resets_at = $w.resets_at }
}
$limits = $data.rate_limits
$ctx = $data.context_window
$snapshot = [ordered]@{
    session_id = $session
    written_at = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    model = [string]$data.model.id
    five_hour = Window $limits.five_hour
    seven_day = Window $limits.seven_day
    context_window_size = $ctx.context_window_size
    context_used_percentage = $ctx.used_percentage
}
$target = Join-Path $folder ($session + '.json')
$temp = $target + '.tmp'
($snapshot | ConvertTo-Json -Depth 4 -Compress) | Set-Content -Path $temp -Encoding UTF8
Move-Item -Force -Path $temp -Destination $target
$parts = @()
if ($data.model.display_name) { $parts += [string]$data.model.display_name }
if ($null -ne $ctx.used_percentage) { $parts += ('ctx ' + [math]::Round([double]$ctx.used_percentage) + '%') }
if ($limits.five_hour) { $parts += ('5h ' + [math]::Round([double]$limits.five_hour.used_percentage) + '%') }
if ($limits.seven_day) { $parts += ('7d ' + [math]::Round([double]$limits.seven_day.used_percentage) + '%') }
Write-Output ($parts -join ' | ')
'''


def data_dir():
    return Path(os.environ.get('LOCALAPPDATA', str(Path.home() / '.local/share'))) / 'CodexWisp'


def status_dir():
    """Where snapshots land. ``PETOKEN_CLAUDE_STATUS_DIR`` overrides it; an
    isolated ``PETOKEN_CLAUDE_HOME`` (QA/tests) also isolates snapshots."""
    configured = os.environ.get('PETOKEN_CLAUDE_STATUS_DIR')
    if configured:
        return Path(configured)
    isolated = os.environ.get('PETOKEN_CLAUDE_HOME')
    if isolated:
        return Path(isolated) / 'petoken-status'
    return data_dir() / STATUS_DIRNAME


def script_path():
    return data_dir() / SCRIPT_NAME


def settings_path(home=None):
    if home is None:
        from claude_usage import default_home
        home = default_home()
    return Path(home) / 'settings.json'


def bridge_command(script=None):
    script = Path(script) if script is not None else script_path()
    return f'powershell -NoProfile -ExecutionPolicy Bypass -File "{script}"'


def _is_ours(status_line):
    return (isinstance(status_line, dict) and isinstance(status_line.get('command'), str)
            and SCRIPT_NAME in status_line['command'])


def _read_settings(path):
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError('settings.json is not a JSON object')
    return data


def _write_settings(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.petoken-tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)


def state(home=None):
    """'on' | 'off' | 'foreign' (another status line) | 'unreadable'."""
    try:
        status_line = _read_settings(settings_path(home)).get('statusLine')
    except (OSError, ValueError):
        return 'unreadable'
    if status_line is None:
        return 'off'
    return 'on' if _is_ours(status_line) else 'foreign'


def enable(home=None, script=None):
    """Install the script and point Claude Code at it. Returns the new state.

    Never replaces a custom status line or an unreadable settings file.
    """
    current = state(home)
    if current in ('foreign', 'unreadable'):
        return current
    script = Path(script) if script is not None else script_path()
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(_SCRIPT, encoding='utf-8-sig')  # BOM: PowerShell 5.1 reads UTF-8.
    path = settings_path(home)
    data = _read_settings(path)
    if path.exists():
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        shutil.copy2(path, path.with_name(f'{path.name}.petoken-backup-{stamp}'))
    data['statusLine'] = dict(type='command', command=bridge_command(script), padding=0)
    _write_settings(path, data)
    return state(home)


def disable(home=None):
    """Remove Petoken's status line only while it is still Petoken's."""
    if state(home) != 'on':
        return state(home)
    path = settings_path(home)
    data = _read_settings(path)
    data.pop('statusLine', None)
    _write_settings(path, data)
    return state(home)


def _window(raw, now):
    if not isinstance(raw, dict):
        return None
    used, reset = raw.get('used_percentage'), raw.get('resets_at')
    if isinstance(used, bool) or not isinstance(used, (int, float)) or not 0 <= used <= 200:
        return None
    # Past the limit Claude Code reports more than 100% (e.g. 101%): that is
    # "nothing left", not bad data to skip for an older, emptier snapshot.
    used = min(used, 100)
    if isinstance(reset, bool) or not isinstance(reset, (int, float)) or reset <= now:
        return None  # Claude Code drops a window once it resets; so do we.
    return dict(used=float(used), resets_at=float(reset))


def read_snapshots(folder=None, now=None):
    """Valid per-session snapshots, newest first."""
    folder = Path(folder) if folder is not None else status_dir()
    now = time.time() if now is None else now
    snapshots = []
    try:
        paths = list(folder.glob('*.json'))
    except OSError:
        return []
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding='utf-8-sig'))
        except (OSError, ValueError):
            continue
        written = data.get('written_at') if isinstance(data, dict) else None
        if isinstance(written, bool) or not isinstance(written, (int, float)):
            continue
        if now - written > SNAPSHOT_MAX_AGE_S:
            continue
        snapshots.append(dict(
            session_id=str(data.get('session_id') or ''), written_at=float(written),
            model=data.get('model') if isinstance(data.get('model'), str) else None,
            five_hour=_window(data.get('five_hour'), now),
            seven_day=_window(data.get('seven_day'), now),
            context_window_size=(data.get('context_window_size')
                                 if isinstance(data.get('context_window_size'), int) else None),
            context_used=(float(data['context_used_percentage'])
                          if isinstance(data.get('context_used_percentage'), (int, float))
                          and not isinstance(data.get('context_used_percentage'), bool) else None)))
    snapshots.sort(key=lambda s: -s['written_at'])
    return snapshots


def account_limits(snapshots):
    """Account-wide 5h/7d windows from the newest snapshot that has each,
    shaped like the Codex limits payload so shared quota code reads both."""
    limits, sampled = {}, None
    for key, minutes, slot in (('five_hour', 300, 'primary'), ('seven_day', 10080, 'secondary')):
        source = next((s for s in snapshots if s[key] is not None), None)
        if source is None:
            continue
        window = source[key]
        limits[slot] = dict(windowDurationMins=minutes, usedPercent=window['used'],
                            resetsAt=window['resets_at'])
        sampled = max(sampled or 0, source['written_at'])
    return (limits or None), sampled
