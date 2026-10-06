"""Opt-in Claude Code hooks bridge for instant task notifications (V1.6).

Claude Code runs hooks in the CLI and in the desktop app's Code tab alike.
When the user turns on Settings -> "Claude instant notifications", Petoken
installs a small PowerShell script and adds one asynchronous command hook
per event to Claude Code's ``settings.json`` (backed up first; nothing else
is touched). Each run appends one line to
``%LOCALAPPDATA%\\CodexWisp\\claude-events.jsonl``: time, event, its type
(notification or error type), session and prompt IDs and the project folder
name. No conversation content, prompt, path or credential is written.

A file rather than a local HTTP hook: Claude Code reports an unreachable
HTTP receiver as a hook error, so users would see errors whenever Petoken
is closed. The script always succeeds and Petoken reads the file whenever
it runs. Verified on Claude Code 2.1.286: Stop arrives under a second after
the reply in both the CLI and the desktop app.
"""
from __future__ import annotations

import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path

import claude_statusline as bridge

SCRIPT_NAME = 'claude-events.ps1'
EVENTS_NAME = 'claude-events.jsonl'
MARKER = 'petoken-claude-events'
HOOK_EVENTS = ('UserPromptSubmit', 'Stop', 'StopFailure', 'Notification', 'PermissionRequest')
# Petoken reads only new lines; an old file this large is simply reset.
MAX_FILE_BYTES = 2 * 1024 * 1024
_ID = re.compile(r'^[A-Za-z0-9._:-]{1,128}$')

_SCRIPT = r'''# petoken-claude-events: written by Petoken. Keeps event metadata only.
$ErrorActionPreference = 'SilentlyContinue'
$reader = New-Object System.IO.StreamReader([Console]::OpenStandardInput(), [Text.Encoding]::UTF8)
$data = $reader.ReadToEnd() | ConvertFrom-Json
if ($null -eq $data) { exit 0 }
function Clean($value) { $s = [string]$value; if ($s -match '^[A-Za-z0-9._:-]{1,128}$') { return $s } return '' }
$kind = @($data.notification_type, $data.error_type) | Where-Object { $_ } | Select-Object -First 1
$project = ''
if ($data.cwd) { $project = Split-Path -Leaf ([string]$data.cwd) }
$line = [ordered]@{
    at = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() / 1000.0
    event = Clean $data.hook_event_name
    kind = Clean $kind
    session = Clean $data.session_id
    prompt = Clean $data.prompt_id
    project = $project
}
$folder = Join-Path $env:LOCALAPPDATA 'CodexWisp'
New-Item -ItemType Directory -Force -Path $folder | Out-Null
Add-Content -Path (Join-Path $folder 'claude-events.jsonl') -Value ($line | ConvertTo-Json -Compress) -Encoding UTF8
exit 0
'''


def script_path():
    return bridge.data_dir() / SCRIPT_NAME


def events_path():
    """Where the script appends; ``PETOKEN_CLAUDE_HOME`` (tests/QA) isolates it."""
    isolated = os.environ.get('PETOKEN_CLAUDE_HOME')
    return Path(isolated) / EVENTS_NAME if isolated else bridge.data_dir() / EVENTS_NAME


def _handler(script):
    return dict(type='command', command='powershell', async_=True, timeout=10,
                args=['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script)])


def _ours(group):
    return isinstance(group, dict) and any(
        isinstance(h, dict) and any(SCRIPT_NAME in str(a) for a in (h.get('args') or []))
        for h in group.get('hooks') or [])


def state(home=None):
    """'on' | 'off' | 'partial' | 'unreadable'."""
    try:
        hooks = bridge._read_settings(bridge.settings_path(home)).get('hooks') or {}
    except (OSError, ValueError):
        return 'unreadable'
    if not isinstance(hooks, dict):
        return 'unreadable'
    present = [any(_ours(g) for g in hooks.get(event) or []) for event in HOOK_EVENTS]
    return 'on' if all(present) else 'partial' if any(present) else 'off'


def _without_ours(hooks):
    cleaned = {}
    for event, groups in hooks.items():
        kept = [g for g in groups if not _ours(g)] if isinstance(groups, list) else groups
        if kept != []:
            cleaned[event] = kept
    return cleaned


def enable(home=None, script=None):
    """Install the script and our hooks beside any existing ones."""
    if state(home) == 'unreadable':
        return 'unreadable'
    script = Path(script) if script is not None else script_path()
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(_SCRIPT, encoding='utf-8-sig')
    path = bridge.settings_path(home)
    data = bridge._read_settings(path)
    if path.exists():
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        shutil.copy2(path, path.with_name(f'{path.name}.petoken-backup-{stamp}'))
    hooks = _without_ours(data.get('hooks') or {})
    handler = _handler(script)
    handler['async'] = handler.pop('async_')
    for event in HOOK_EVENTS:
        hooks.setdefault(event, []).append(dict(hooks=[dict(handler)]))
    data['hooks'] = hooks
    bridge._write_settings(path, data)
    return state(home)


def disable(home=None):
    """Remove only Petoken's hooks; other hooks stay exactly as they were."""
    current = state(home)
    if current in ('off', 'unreadable'):
        return current
    path = bridge.settings_path(home)
    data = bridge._read_settings(path)
    hooks = _without_ours(data.get('hooks') or {})
    if hooks:
        data['hooks'] = hooks
    else:
        data.pop('hooks', None)
    bridge._write_settings(path, data)
    return state(home)


def interactive_sessions(home=None):
    """IDs of sessions a person opened (CLI or desktop), from Claude Code's
    live-session registry. Headless runs (``claude -p``, SDK, scripts and
    agents driving Claude) are not registered there."""
    from claude_usage import default_home
    folder = Path(home if home is not None else default_home()) / 'sessions'
    found = set()
    try:
        paths = list(folder.glob('*.json'))
    except OSError:
        return found
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and data.get('kind', 'interactive') == 'interactive':
            session = _clean(data.get('sessionId'))
            if session:
                found.add(session)
    return found


def _clean(value):
    return value if isinstance(value, str) and _ID.match(value) else ''


def normalize(record):
    """One file line to a notification event, or None."""
    if not isinstance(record, dict):
        return None
    at = record.get('at')
    session = _clean(record.get('session'))
    if isinstance(at, bool) or not isinstance(at, (int, float)) or not session:
        return None
    event, kind = record.get('event'), _clean(record.get('kind'))
    prompt = _clean(record.get('prompt')) or f'{at:.0f}'
    if event == 'Stop':
        name, key = 'finished', prompt
    elif event == 'StopFailure':
        name, key = 'failed', prompt
    elif event == 'PermissionRequest' or (event == 'Notification' and kind == 'permission_prompt'):
        name, key = 'needs_approval', f'{prompt}:{int(at // 15)}'
    elif event == 'UserPromptSubmit':
        name, key = 'started', prompt
    else:
        return None
    project = record.get('project')
    return dict(kind=name, provider='claude', task_key=f'claude:{session}', at=float(at),
                project=project.strip()[:200] if isinstance(project, str) else '',
                detail=kind, dedupe=f'claude:{session}:{key}:{name}', source='hook')


class ClaudeEventReader:
    """Reads lines appended since Petoken started; history is never replayed."""

    def __init__(self, path=None):
        self.path = Path(path) if path is not None else events_path()
        self.offset = None

    def poll(self):
        try:
            size = self.path.stat().st_size
        except OSError:
            self.offset = self.offset if self.offset is not None else 0
            return []
        if self.offset is None:
            if size > MAX_FILE_BYTES:
                try:
                    self.path.write_bytes(b'')
                    size = 0
                except OSError:
                    pass
            self.offset = size
            return []
        if size < self.offset:
            self.offset = 0  # Reset or replaced by someone else.
        if size == self.offset:
            return []
        try:
            with self.path.open('rb') as handle:
                handle.seek(self.offset)
                chunk = handle.read(size - self.offset)
        except OSError:
            return []
        complete = chunk.rfind(b'\n') + 1
        self.offset += complete
        events = []
        for raw in chunk[:complete].splitlines():
            try:
                event = normalize(json.loads(raw.decode('utf-8-sig').lstrip('﻿')))
            except ValueError:
                continue
            if event is not None:
                events.append(event)
        return events
