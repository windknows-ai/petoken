"""Approve Claude Code permission requests on the pet (V1.6 B, opt-in).

When the user turns on Settings -> "Approve Claude requests on the pet",
Petoken installs a small PowerShell script as a *blocking*
``PermissionRequest`` hook in Claude Code's ``settings.json`` (backed up
first; other hooks untouched). Claude Code runs it whenever it is about
to ask for permission, in the CLI and in the desktop app's Code tab.

The script and Petoken talk through files in
``%LOCALAPPDATA%\\CodexWisp\\claude-approvals``:

1. Petoken touches ``alive`` every couple of seconds while it runs. If the
   file is missing or stale the script exits at once, so with Petoken
   closed Claude Code asks exactly as before.
2. The script writes the request (Claude Code's hook input) to
   ``<id>.request.json`` and waits up to WAIT_S seconds for
   ``<id>.decision.json``.
3. The pet shows the request: Allow once, Always allow, Deny, or "Answer
   in Claude". The decision file holds the hook output (or nothing, which
   hands the question back to Claude Code's own prompt). On timeout the
   script also hands it back. Request files are deleted once answered.

Always allow returns ``updatedPermissions``: Claude Code's own suggestions
(rules and extra directories, saved to the project's local settings
instead of the session) plus one precise rule for this call, e.g.
``Bash(npm test)``. Every rule Petoken asked for is listed in a small
ledger so Settings can show and revoke it.

Verified on Claude Code 2.1.286 (CLI): the hook blocks the prompt, and
``{"behavior": "allow"}`` runs the command.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import time
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import claude_statusline as bridge

SCRIPT_NAME = 'claude-approval.ps1'
FOLDER_NAME = 'claude-approvals'
LEDGER_NAME = 'claude-approval-rules.json'
MARKER = 'petoken-claude-approval'
WAIT_S = 45                # The pet's turn; then Claude Code asks itself.
QUESTION_WAIT_S = 300      # Claude's questions (AskUserQuestion) need time to think.
HOOK_TIMEOUT_S = 330       # Claude Code's limit for the hook, above both waits.
QUESTION_TOOL = 'AskUserQuestion'
PLAN_TOOL = 'ExitPlanMode'         # "Claude has a plan": accept, accept and allow edits, or revise.
ALIVE_STALE_S = 10
SHELL_TOOLS = ('Bash', 'PowerShell')
EDIT_TOOLS = ('Edit', 'Write', 'MultiEdit', 'NotebookEdit')
MAX_RULE_COMMAND = 300
_ID = re.compile(r'^[0-9a-f]{32}$')

_SCRIPT = r'''# petoken-claude-approval: written by Petoken. Asks the desktop pet first.
$ErrorActionPreference = 'SilentlyContinue'
$folder = '__FOLDER__'
$alive = Join-Path $folder 'alive'
function Alive {
    $item = Get-Item -LiteralPath $alive
    return ($null -ne $item) -and (([DateTime]::UtcNow - $item.LastWriteTimeUtc).TotalSeconds -le __STALE__)
}
if (-not (Alive)) { exit 0 }
$utf8 = New-Object System.Text.UTF8Encoding($false)
$reader = New-Object System.IO.StreamReader([Console]::OpenStandardInput(), $utf8)
$raw = $reader.ReadToEnd()
$id = [guid]::NewGuid().ToString('N')
$request = Join-Path $folder "$id.request.json"
$decision = Join-Path $folder "$id.decision.json"
[IO.File]::WriteAllText("$request.tmp", $raw, $utf8)
Move-Item -LiteralPath "$request.tmp" -Destination $request -Force
$wait = __WAIT__
if ($raw -match '"tool_name"\s*:\s*"(AskUserQuestion|ExitPlanMode)"') { $wait = __QUESTION_WAIT__ }
$deadline = [DateTime]::UtcNow.AddSeconds($wait)
while ([DateTime]::UtcNow -lt $deadline) {
    if (Test-Path -LiteralPath $decision) {
        $answer = [IO.File]::ReadAllText($decision, $utf8)
        Remove-Item -LiteralPath $decision, $request -Force
        if ($answer.Trim()) { [Console]::Out.Write($answer) }
        exit 0
    }
    if (-not (Alive)) { break }
    Start-Sleep -Milliseconds 150
}
Remove-Item -LiteralPath $request -Force
exit 0
'''


def folder():
    """Request/decision folder; ``PETOKEN_CLAUDE_HOME`` (tests/QA) isolates it."""
    isolated = os.environ.get('PETOKEN_CLAUDE_HOME')
    return (Path(isolated) if isolated else bridge.data_dir()) / FOLDER_NAME


def script_path():
    return bridge.data_dir() / SCRIPT_NAME


def ledger_path():
    isolated = os.environ.get('PETOKEN_CLAUDE_HOME')
    return (Path(isolated) if isolated else bridge.data_dir()) / LEDGER_NAME


def script_text(target=None):
    target = str(Path(target) if target is not None else folder())
    return (_SCRIPT.replace('__FOLDER__', target.replace("'", "''"))
            .replace('__WAIT__', str(WAIT_S)).replace('__QUESTION_WAIT__', str(QUESTION_WAIT_S))
            .replace('__STALE__', str(ALIVE_STALE_S)))


# Installation -------------------------------------------------------------
def _handler(script):
    return dict(type='command', command='powershell', timeout=HOOK_TIMEOUT_S,
                args=['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script)])


def _ours(group):
    return isinstance(group, dict) and any(
        isinstance(h, dict) and any(SCRIPT_NAME in str(a) for a in (h.get('args') or []))
        for h in group.get('hooks') or [])


def state(home=None):
    """'on' | 'off' | 'unreadable'."""
    try:
        hooks = bridge._read_settings(bridge.settings_path(home)).get('hooks') or {}
    except (OSError, ValueError):
        return 'unreadable'
    if not isinstance(hooks, dict):
        return 'unreadable'
    groups = hooks.get('PermissionRequest') or []
    return 'on' if isinstance(groups, list) and any(_ours(g) for g in groups) else 'off'


def _without_ours(hooks):
    groups = hooks.get('PermissionRequest')
    if isinstance(groups, list):
        kept = [g for g in groups if not _ours(g)]
        if kept:
            hooks['PermissionRequest'] = kept
        else:
            hooks.pop('PermissionRequest')
    return hooks


def enable(home=None, script=None, target=None):
    """Install the script and our blocking hook beside any existing ones."""
    if state(home) == 'unreadable':
        return 'unreadable'
    script = Path(script) if script is not None else script_path()
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(script_text(target), encoding='utf-8-sig')
    path = bridge.settings_path(home)
    data = bridge._read_settings(path)
    if path.exists():
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        shutil.copy2(path, path.with_name(f'{path.name}.petoken-backup-{stamp}'))
    hooks = _without_ours(dict(data.get('hooks') or {}))
    hooks.setdefault('PermissionRequest', []).append(dict(hooks=[_handler(script)]))
    data['hooks'] = hooks
    bridge._write_settings(path, data)
    return state(home)


def disable(home=None):
    """Remove only Petoken's approval hook."""
    current = state(home)
    if current != 'on':
        return current
    path = bridge.settings_path(home)
    data = bridge._read_settings(path)
    hooks = _without_ours(dict(data.get('hooks') or {}))
    if hooks:
        data['hooks'] = hooks
    else:
        data.pop('hooks', None)
    bridge._write_settings(path, data)
    return state(home)


# Requests -----------------------------------------------------------------
def _text(value, limit=2000):
    return value[:limit] if isinstance(value, str) else ''


def summary(tool, tool_input):
    """What the request is about, in one string (command, file, URL…)."""
    tool_input = tool_input if isinstance(tool_input, dict) else {}
    for key in ('command', 'file_path', 'notebook_path', 'url', 'query', 'pattern', 'path'):
        if _text(tool_input.get(key)):
            return _text(tool_input[key])
    values = [f'{k}: {v}' for k, v in tool_input.items() if isinstance(v, (str, int, float))]
    return _text('\n'.join(values)) or tool


def precise_rule(tool, tool_input):
    """(toolName, ruleContent or None) for "always allow", or None if too broad."""
    tool_input = tool_input if isinstance(tool_input, dict) else {}
    if tool in SHELL_TOOLS:
        command = tool_input.get('command')
        if (not isinstance(command, str) or not command.strip() or '\n' in command
                or len(command) > MAX_RULE_COMMAND):
            return None
        return tool, command.strip()
    if tool == 'WebFetch':
        host = urlparse(_text(tool_input.get('url'))).hostname
        return (tool, f'domain:{host}') if host else None
    if not isinstance(tool, str) or not re.match(r'^[A-Za-z0-9_.:-]{1,128}$', tool):
        return None
    return tool, None   # Edit, Write, WebSearch, MCP tools: the tool in this project.


def parse_request(request_id, raw, at):
    """Claude Code's hook input to the fields the pet shows, or None."""
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(data, dict) or data.get('hook_event_name', 'PermissionRequest') != 'PermissionRequest':
        return None
    tool = _text(data.get('tool_name'), 128)
    if not tool:
        return None
    tool_input = data.get('tool_input') if isinstance(data.get('tool_input'), dict) else {}
    cwd = _text(data.get('cwd'), 1000)
    if tool == PLAN_TOOL:
        plan = _text(tool_input.get('plan'), 20000)
        return dict(id=request_id, at=at, session=_text(data.get('session_id'), 128), cwd=cwd,
                    project=Path(cwd).name if cwd else '', tool=tool, summary=plan, description='',
                    suggestions=[], rule=None, can_always=False, plan=plan,
                    plan_file=_text(tool_input.get('planFilePath'), 1000), wait=QUESTION_WAIT_S)
    if tool == QUESTION_TOOL:
        questions = parse_questions(tool_input.get('questions'))
        if not questions:
            return None
        return dict(id=request_id, at=at, session=_text(data.get('session_id'), 128), cwd=cwd,
                    project=Path(cwd).name if cwd else '', tool=tool, summary=questions[0]['question'],
                    description='', suggestions=[], rule=None, can_always=False,
                    questions=questions, original=tool_input.get('questions'), wait=QUESTION_WAIT_S)
    suggestions = [s for s in data.get('permission_suggestions') or []
                   if isinstance(s, dict) and s.get('type') in ('addRules', 'addDirectories')]
    rule = precise_rule(tool, tool_input)
    return dict(id=request_id, at=at, session=_text(data.get('session_id'), 128), cwd=cwd,
                project=Path(cwd).name if cwd else '', tool=tool, wait=WAIT_S,
                summary=summary(tool, tool_input),
                description=_text(tool_input.get('description'), 300),
                suggestions=suggestions, rule=rule, can_always=rule is not None)


def parse_questions(value):
    """Claude's AskUserQuestion questions: question, header, options, multiSelect."""
    out = []
    for item in value if isinstance(value, list) else []:
        if not isinstance(item, dict) or not _text(item.get('question')):
            continue
        options = [dict(label=_text(o.get('label'), 200), description=_text(o.get('description'), 400))
                   for o in item.get('options') or [] if isinstance(o, dict) and _text(o.get('label'))]
        out.append(dict(question=_text(item['question'], 1000), header=_text(item.get('header'), 40),
                        options=options[:6], multi=bool(item.get('multiSelect'))))
    return out[:4]


def decision(request, choice, answers=None):
    """The hook output for ``choice``: 'allow' | 'always' | 'deny' | 'ask' |
    'answer' (``answers``: question text -> label, labels or typed text)."""
    if choice == 'ask':
        return None
    if choice in ('accept', 'accept_edits') and request.get('tool') == PLAN_TOOL:
        # Approving a plan also leaves plan mode, exactly like Claude's own
        # buttons: back to asking as usual, or "accept and allow edits".
        # Without the mode change Claude stays in plan mode and cannot act.
        mode = 'acceptEdits' if choice == 'accept_edits' else 'default'
        body = dict(behavior='allow',
                    updatedPermissions=[dict(type='setMode', mode=mode, destination='session')])
        return dict(hookSpecificOutput=dict(hookEventName='PermissionRequest', decision=body))
    if choice == 'revise' and request.get('tool') == PLAN_TOOL:
        feedback = (answers or '').strip() if isinstance(answers, str) else ''
        body = dict(behavior='deny', message=(f'The user wants changes to the plan: {feedback}' if feedback
                                              else 'The user rejected the plan. Ask what to change.'))
        return dict(hookSpecificOutput=dict(hookEventName='PermissionRequest', decision=body))
    if choice == 'answer':
        if not answers or request.get('tool') != QUESTION_TOOL:
            return None
        body = dict(behavior='allow', updatedInput=dict(questions=request.get('original') or [],
                                                        answers=dict(answers)))
        return dict(hookSpecificOutput=dict(hookEventName='PermissionRequest', decision=body))
    if choice == 'deny':
        body = dict(behavior='deny', message='Denied from Petoken.')
    else:
        body = dict(behavior='allow')
        if choice == 'always' and request.get('can_always'):
            body['updatedPermissions'] = always_permissions(request)
    return dict(hookSpecificOutput=dict(hookEventName='PermissionRequest', decision=body))


def always_permissions(request):
    """Claude Code's suggestions, kept for the project, plus a precise rule."""
    updates = []
    for suggestion in request.get('suggestions') or []:
        updates.append(dict(suggestion, destination='localSettings'))
    tool, content = request['rule']
    rule = dict(toolName=tool, **({'ruleContent': content} if content else {}))
    if not any(u.get('type') == 'addRules' and rule in (u.get('rules') or []) for u in updates):
        updates.append(dict(type='addRules', rules=[rule], behavior='allow',
                            destination='localSettings'))
    return updates


def rule_text(rule):
    """``{'toolName': 'Bash', 'ruleContent': 'npm test'}`` -> ``Bash(npm test)``."""
    if not isinstance(rule, dict) or not rule.get('toolName'):
        return ''
    content = rule.get('ruleContent')
    return f"{rule['toolName']}({content})" if content else rule['toolName']


class ApprovalBroker:
    """Petoken's side of the file exchange."""

    def __init__(self, target=None):
        self.folder = Path(target) if target is not None else folder()
        self.pending = {}
        self.answered = set()   # Answered; the script has not removed the request yet.

    def heartbeat(self):
        try:
            self.folder.mkdir(parents=True, exist_ok=True)
            (self.folder / 'alive').write_text(f'{time.time():.0f}', encoding='ascii')
        except OSError:
            pass

    def poll(self):
        """(new requests, ids that went away: answered elsewhere or timed out)."""
        try:
            names = {p.name[:-len('.request.json')]: p for p in self.folder.glob('*.request.json')}
        except OSError:
            names = {}
        new = []
        for request_id, path in sorted(names.items(), key=lambda item: item[1].stat().st_mtime
                                       if item[1].exists() else 0):
            if request_id in self.pending or request_id in self.answered or not _ID.match(request_id):
                continue
            try:
                raw, at = path.read_text(encoding='utf-8-sig'), path.stat().st_mtime
            except OSError:
                continue
            request = parse_request(request_id, raw, at)
            if request is None:
                self._write(request_id, None)  # Not ours to judge: Claude Code asks.
                self.answered.add(request_id)
                continue
            self.pending[request_id] = request
            new.append(request)
        gone = [request_id for request_id in self.pending if request_id not in names]
        for request_id in gone:
            self.pending.pop(request_id)
        self.answered &= set(names)
        return new, gone

    def answer(self, request_id, choice, answers=None):
        request = self.pending.pop(request_id, None)
        if request is None:
            return False
        output = decision(request, choice, answers)
        self.answered.add(request_id)
        if not self._write(request_id, output):
            return False
        if choice == 'always' and output and request.get('can_always'):
            record_rules(request)
        return True

    def _write(self, request_id, output):
        target = self.folder / f'{request_id}.decision.json'
        temp = target.with_name(target.name + '.tmp')
        try:
            temp.write_text('' if output is None else json.dumps(output), encoding='utf-8')
            temp.replace(target)
        except OSError:
            return False
        return True

    def shutdown(self):
        """Hand every open question back to Claude Code and stop waiting scripts."""
        for request_id in list(self.pending):
            self.answer(request_id, 'ask')
        try:
            (self.folder / 'alive').unlink()
        except OSError:
            pass


# "Always allow" ledger ----------------------------------------------------
def list_rules(path=None):
    path = Path(path) if path is not None else ledger_path()
    try:
        rules = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return []
    return [r for r in rules if isinstance(r, dict) and isinstance(r.get('cwd'), str)] \
        if isinstance(rules, list) else []


def _save_rules(rules, path=None):
    path = Path(path) if path is not None else ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(rules, ensure_ascii=False, indent=1), encoding='utf-8')
    temp.replace(path)


def record_rules(request, path=None, now=None):
    rules = list_rules(path)
    for update in always_permissions(request):
        entry = dict(at=time.time() if now is None else now, cwd=request['cwd'],
                     project=request['project'], tool=request['tool'])
        if update.get('type') == 'addRules':
            entry.update(rules=[rule_text(r) for r in update.get('rules') or [] if rule_text(r)])
        else:
            entry.update(directories=[d for d in update.get('directories') or [] if isinstance(d, str)])
        if (entry.get('rules') or entry.get('directories')) and not any(
                (r.get('cwd'), r.get('rules'), r.get('directories'))
                == (entry['cwd'], entry.get('rules'), entry.get('directories')) for r in rules):
            rules.append(entry)
    try:
        _save_rules(rules, path)
    except OSError:
        pass


def revoke(entry, path=None):
    """Remove one ledger entry's rules from the project's local settings."""
    settings = Path(entry['cwd']) / '.claude' / 'settings.local.json'
    try:
        data = bridge._read_settings(settings)
    except (OSError, ValueError):
        return False
    permissions = data.get('permissions') if isinstance(data.get('permissions'), dict) else None
    if permissions is not None:
        for key, values in (('allow', entry.get('rules')), ('additionalDirectories', entry.get('directories'))):
            current = permissions.get(key)
            if values and isinstance(current, list):
                permissions[key] = [v for v in current if v not in values]
                if not permissions[key]:
                    permissions.pop(key)
        if settings.exists():
            bridge._write_settings(settings, data)
    rules = [r for r in list_rules(path) if r != entry]
    try:
        _save_rules(rules, path)
    except OSError:
        return False
    return True


def new_request_id():
    return uuid.uuid4().hex
