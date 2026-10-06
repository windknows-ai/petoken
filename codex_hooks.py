"""Opt-in Codex hooks; metadata events and one-shot permission decisions only.

Installation is not trust approval. Users must review the installed hooks in
Codex's /hooks browser. Nothing here changes config.toml, notify or trust.
"""
from __future__ import annotations

import base64
import json
import math
import ntpath
import os
from pathlib import Path
import re
import shutil
import uuid

MARKER = 'petoken-codex-hooks'
SCRIPT_NAME = 'codex-hooks.ps1'
EVENTS_NAME = 'codex-events.jsonl'
HOOK_EVENTS = ('SessionStart', 'UserPromptSubmit', 'Stop', 'PermissionRequest', 'Interrupt')
WAIT_S = 45
ALIVE_STALE_S = 10
_ID = re.compile(r'^[A-Za-z0-9._:-]{1,128}$')

_SCRIPT = r'''# petoken-codex-hooks: metadata only; no model context on stdout.
param([string]$DataDir)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$utf8 = New-Object System.Text.UTF8Encoding($false)
function Clean($v) { if ($v -is [string] -and $v -cmatch '^[A-Za-z0-9._:-]{1,128}$') { return $v }; return '' }
function Alive($folder) {
    try {
        $age = ([DateTime]::UtcNow - (Get-Item -LiteralPath (Join-Path $folder 'alive')).LastWriteTimeUtc).TotalSeconds
        return ($age -ge 0 -and $age -le 10)
    } catch { return $false }
}
$request = $owner = $decision = $temp = $null
try {
    $reader = New-Object IO.StreamReader([Console]::OpenStandardInput(), $utf8)
    $data = $reader.ReadToEnd() | ConvertFrom-Json
    $session = Clean $data.session_id
    $event = Clean $data.hook_event_name
    if (-not $session -or $event -notin @('SessionStart','UserPromptSubmit','Stop','PermissionRequest','Interrupt')) { exit 0 }
    $folder = Join-Path $DataDir 'claude-approvals'
    # A dead receiver must not leave a request or make an approval decision.
    if ($event -eq 'PermissionRequest' -and -not (Alive $folder)) { exit 0 }
    [IO.Directory]::CreateDirectory($DataDir) | Out-Null
    $project = if ($data.cwd -is [string]) { [IO.Path]::GetFileName($data.cwd.TrimEnd('\','/')) } else { '' }
    $line = [ordered]@{
        at = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() / 1000.0
        event = $event; kind = ''; session = $session
        turn = (Clean $data.turn_id); project = $project
    }
    # Cross-process serialization keeps concurrent hooks from interleaving JSON.
    $hash = [Security.Cryptography.SHA256]::Create().ComputeHash($utf8.GetBytes($DataDir.ToLowerInvariant()))
    $mutex = New-Object Threading.Mutex($false, ('Local\PetokenCodexEvents' + [BitConverter]::ToString($hash).Replace('-','')))
    $locked = $false
    try {
        try { $locked = $mutex.WaitOne(2000) } catch [Threading.AbandonedMutexException] { $locked = $true }
        if ($locked) {
            [IO.File]::AppendAllText((Join-Path $DataDir 'codex-events.jsonl'), ($line | ConvertTo-Json -Compress) + "`n", $utf8)
        }
    } finally { if ($locked) { $mutex.ReleaseMutex() }; $mutex.Dispose() }
    if ($event -ne 'PermissionRequest' -or -not (Alive $folder)) { exit 0 }
    $inputData = $data.tool_input
    # Don't substitute a different tool or invent an executable command.
    if (-not (Clean $data.tool_name) -or $null -eq $inputData) { exit 0 }
    $toolInput = [ordered]@{}
    foreach ($key in @('command','file_path','description')) {
        if ($inputData.$key -is [string]) { $toolInput[$key] = $inputData.$key }
    }
    if (-not $toolInput.Contains('command') -and -not $toolInput.Contains('file_path')) { exit 0 }
    if (-not $toolInput.Contains('description')) { $toolInput['description'] = '' }
    $id = [guid]::NewGuid().ToString('N')
    $request = Join-Path $folder "$id.request.json"
    $temp = "$request.tmp"
    $owner = Join-Path $folder "$id.pid"
    $decision = Join-Path $folder "$id.decision.json"
    $body = [ordered]@{ hook_event_name='PermissionRequest'; provider='codex'; session_id=$session
        cwd=$data.cwd; tool_name=$data.tool_name; tool_input=$toolInput }
    [IO.File]::WriteAllText($temp, ($body | ConvertTo-Json -Depth 10 -Compress), $utf8)
    [IO.File]::WriteAllText($owner, [string]$PID, $utf8)
    [IO.File]::Move($temp, $request)
    $watch = [Diagnostics.Stopwatch]::StartNew()
    while ($watch.Elapsed.TotalSeconds -lt 45) {
        if (-not (Alive $folder)) { break }
        if ([IO.File]::Exists($decision)) {
            $raw = [IO.File]::ReadAllText($decision, $utf8)
            if ($raw.Trim()) {
                $answer = ($raw | ConvertFrom-Json).hookSpecificOutput.decision
                if ($answer.behavior -cin @('allow','deny')) {
                    $choice = [ordered]@{ behavior=$answer.behavior }
                    if ($answer.message -is [string]) { $choice['message'] = $answer.message }
                    # Strip Claude-only updatedInput/updatedPermissions/interrupt.
                    $out = @{ hookSpecificOutput=@{ hookEventName='PermissionRequest'; decision=$choice } }
                    [Console]::Out.Write(($out | ConvertTo-Json -Depth 10 -Compress))
                }
            }
            break
        }
        Start-Sleep -Milliseconds 150
    }
} catch {
    # Broken files/receiver => Codex's own prompt, never an implicit allow.
} finally {
    foreach ($path in @($request,$owner,$decision,$temp)) {
        if ($path) { try { [IO.File]::Delete($path) } catch {} }
    }
}
exit 0
'''


def data_dir():
    """PETOKEN_CODEX_HOME isolates event/approval storage for tests and QA."""
    isolated = os.environ.get('PETOKEN_CODEX_HOME')
    return Path(isolated) if isolated else Path(os.environ['LOCALAPPDATA']) / 'CodexWisp'


def events_path():
    return data_dir() / EVENTS_NAME


def _config(home):
    return Path(home if home is not None else os.environ.get('CODEX_HOME', Path.home() / '.codex')) / 'hooks.json'


def _read(path):
    data = json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else {}
    hooks = data.get('hooks', {}) if isinstance(data, dict) else None
    if (not isinstance(hooks, dict) or any(not isinstance(groups, list) or any(
            not isinstance(g, dict) or not isinstance(g.get('hooks'), list)
            or any(not isinstance(h, dict) for h in g['hooks']) for g in groups)
            for groups in hooks.values())):
        raise ValueError('Unknown Codex hooks configuration')
    return data


def _ours(handler):
    command = handler.get('command')
    if handler.get('statusMessage') != MARKER or not isinstance(command, str):
        return False
    try:
        script = base64.b64decode(command.split(' -EncodedCommand ', 1)[1], validate=True).decode('utf-16le')
    except (ValueError, IndexError, UnicodeError):
        return False
    return script.startswith(f'# {MARKER}\n& ')


def state(home=None):
    """on/off/partial/unreadable: installed definitions, NOT Codex trust status."""
    try:
        hooks = _read(_config(home)).get('hooks', {})
        present = [any(_ours(h) for g in hooks.get(e, []) for h in g['hooks']) for e in HOOK_EVENTS]
        return 'on' if all(present) else 'partial' if any(present) else 'off'
    except (OSError, ValueError):
        return 'unreadable'


def _without_ours(data):
    hooks = data.get('hooks', {})
    for event in list(hooks):
        kept = []
        for group in hooks[event]:
            handlers = [h for h in group['hooks'] if not _ours(h)]
            if handlers == group['hooks']:
                kept.append(group)
            elif handlers:
                kept.append(dict(group, hooks=handlers))
        if kept:
            hooks[event] = kept
        else:
            del hooks[event]
    if not hooks:
        data.pop('hooks', None)
    return data


def _write(path, data, original):
    path.parent.mkdir(parents=True, exist_ok=True)
    if (path.read_bytes() if path.exists() else None) != original:
        raise OSError('Codex hooks changed during installation')
    if original is not None:
        shutil.copy2(path, path.with_name(f'{path.name}.petoken-backup-{uuid.uuid4().hex}'))
    temp = path.with_name(f'{path.name}.{uuid.uuid4().hex}.tmp')
    try:
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def enable(home=None, *, script=None, target=None):
    """Back up and merge Windows command hooks without changing other sources."""
    path = _config(home)
    try:
        original = path.read_bytes() if path.exists() else None
        data = _without_ours(_read(path))
        script = Path(script) if script is not None else data_dir() / SCRIPT_NAME
        target = Path(target) if target is not None else data_dir()
        script, target = script.absolute(), target.absolute()
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text(_SCRIPT, encoding='utf-8-sig')
        literal = lambda p: "'" + str(p).replace("'", "''") + "'"
        invoke = f'# {MARKER}\n& {literal(script)} -DataDir {literal(target)}'
        encoded = base64.b64encode(invoke.encode('utf-16le')).decode('ascii')
        command = f'powershell.exe -NoProfile -ExecutionPolicy Bypass -EncodedCommand {encoded}'
        hooks = data.setdefault('hooks', {})
        for event in HOOK_EVENTS:
            handler = dict(type='command', command=command, statusMessage=MARKER,
                           timeout=50 if event == 'PermissionRequest' else 3)
            # exec can exit before a background Stop logger finishes.
            if event == 'UserPromptSubmit':
                handler['async'] = True
            hooks.setdefault(event, []).append(dict(hooks=[handler]))
        if data != _read(path):
            _write(path, data, original)
        return state(home)
    except (OSError, ValueError):
        return 'unreadable'


def disable(home=None):
    """Back up, remove only owned handlers, retain user handlers in mixed groups."""
    path = _config(home)
    try:
        original = path.read_bytes() if path.exists() else None
        data = _read(path)
        cleaned = _without_ours(json.loads(json.dumps(data)))
        if cleaned != data:
            _write(path, cleaned, original)
        return state(home)
    except (OSError, ValueError):
        return 'unreadable'


def _clean(value):
    return value if isinstance(value, str) and _ID.fullmatch(value) else ''


def normalize(record):
    """Same notification shape as claude_events; task_key is the raw thread ID.

    No StopFailure hook exists. The optional turn/completed record is only for
    an already-connected app-server emitter with an explicit terminal status.
    """
    if not isinstance(record, dict):
        return None
    at, session = record.get('at'), _clean(record.get('session'))
    if isinstance(at, bool) or not isinstance(at, (int, float)) or not session:
        return None
    try:
        at = float(at)
    except OverflowError:
        return None
    if not math.isfinite(at) or at < 0:
        return None
    event, detail = record.get('event'), _clean(record.get('kind'))
    kind = {'Stop': 'finished', 'PermissionRequest': 'needs_approval', 'UserPromptSubmit': 'started'}.get(event)
    if event == 'turn/completed':
        kind = {'completed': 'finished', 'failed': 'failed'}.get(detail)
    if not kind:
        return None
    turn = _clean(record.get('turn')) or f'{at:.3f}'
    key = f'{turn}:{int(at // 15)}' if kind == 'needs_approval' else turn
    project = record.get('project')
    return dict(kind=kind, provider='codex', task_key=session, at=float(at),
                project=ntpath.basename(project.strip().rstrip('\\/'))[:200] if isinstance(project, str) else '',
                detail=detail, dedupe=f'codex:{session}:{key}:{kind}',
                source='app-server' if event == 'turn/completed' else 'hook')


class CodexEventReader:
    """Tail complete new metadata lines; never replay history at startup."""
    def __init__(self, path=None):
        self.path = Path(path) if path is not None else events_path()
        self.offset = None
        self.identity = None

    def poll(self):
        try:
            stat = self.path.stat()
            identity = stat.st_dev, stat.st_ino
            if self.offset is None:
                self.offset, self.identity = stat.st_size, identity
                return []
            if self.identity != identity or stat.st_size < self.offset:
                self.offset = 0
            self.identity = identity
            with self.path.open('rb') as stream:
                stream.seek(self.offset)
                chunk = stream.read(1024 * 1024)
        except OSError:
            if self.offset is None:
                self.offset = 0
            return []
        complete = chunk.rfind(b'\n') + 1
        self.offset += complete
        events = []
        for raw in chunk[:complete].splitlines():
            try:
                event = normalize(json.loads(raw.decode('utf-8-sig')))
            except (ValueError, UnicodeError):
                continue
            if event is not None:
                events.append(event)
        return events
