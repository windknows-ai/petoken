"""Background refresh of Claude subscription limits (2.0, opt-in).

Claude Code only tells its status line the 5-hour and weekly limits when a
conversation has a new message, so the usage card goes stale while no
Claude Code session is busy. When the user turns this on (Settings >
Claude and Codex), Petoken asks the Claude Code CLI one tiny question in
the background every few minutes and keeps the limits from its reply:

    claude -p ok --model haiku --system-prompt ... --tools "" \\
        --no-session-persistence --setting-sources "" --strict-mcp-config \\
        --output-format stream-json --verbose

That is about 700 input and 150 output Haiku tokens per refresh, counted
against the account like any other use. No window opens, no session is
saved, and the user's settings (hooks, status line, MCP servers) are not
loaded, so Petoken's own notifications do not fire. A refresh is skipped
while a real Claude Code session has written fresh numbers anyway. The
result is written as one more status-line snapshot, so everything that
reads Claude's limits picks it up unchanged.
"""
from __future__ import annotations

import json
import re
import subprocess
import threading
import time
from pathlib import Path

INTERVALS = (0, 1, 5, 15)          # Minutes; 0 is off.
# The refresh runs in its own folder. Claude Code registers the run as a
# session for its few seconds; Petoken ignores sessions in this folder, so
# the star ring and notifications never react to a refresh.
PROBE_DIRNAME = 'claude-probe'


def is_probe_cwd(cwd):
    """True for a session started by the background refresh."""
    if not isinstance(cwd, str) or not cwd:
        return False
    parts = [part for part in re.split(r'[\\/]+', cwd.strip().lower()) if part]
    return len(parts) >= 2 and parts[-1] == PROBE_DIRNAME and parts[-2] == 'codexwisp'
SNAPSHOT_NAME = 'petoken-probe.json'
TIMEOUT_S = 60
PROMPT = 'ok'
SYSTEM = 'Reply with the single word ok.'


def command(cli):
    return [cli, '-p', PROMPT, '--model', 'haiku', '--system-prompt', SYSTEM, '--tools', '',
            '--no-session-persistence', '--setting-sources', '', '--strict-mcp-config',
            '--output-format', 'stream-json', '--verbose']


def parse(lines):
    """The account windows from Claude Code's stream-json output, or None.

    Returns {'five_hour': (used %, resets_at), 'seven_day': (...)} with
    whichever windows the rate_limit_event carries.
    """
    for line in lines:
        line = line.strip()
        if '"rate_limit_event"' not in line:
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        info = (event or {}).get('rate_limit_info') or {}
        windows = info.get('unifiedWindows') or {}
        out = {}
        for key in ('five_hour', 'seven_day'):
            window = windows.get(key) or {}
            used, reset = window.get('utilization'), window.get('resetsAt')
            if (isinstance(used, (int, float)) and not isinstance(used, bool) and 0 <= used <= 1
                    and isinstance(reset, (int, float)) and not isinstance(reset, bool)):
                out[key] = (round(used * 100, 1), float(reset))
        if out:
            return out
    return None


def write_snapshot(windows, folder, now=None):
    """Save the windows like a status-line snapshot (see claude_statusline)."""
    now = time.time() if now is None else now
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    data = dict(session_id='petoken-probe', written_at=int(now), model='',
                five_hour=None, seven_day=None, context_window_size=None, context_used_percentage=None)
    for key, (used, reset) in windows.items():
        data[key] = dict(used_percentage=used, resets_at=reset)
    target = folder / SNAPSHOT_NAME
    temp = target.with_suffix('.tmp')
    temp.write_text(json.dumps(data), encoding='utf-8')
    temp.replace(target)
    return target


def probe(cli, cwd, runner=None):
    """Ask once; the windows, or None when the CLI gave none."""
    run = runner or subprocess.run
    try:
        result = run(command(cli), cwd=str(cwd), stdin=subprocess.DEVNULL, capture_output=True,
                     timeout=TIMEOUT_S, encoding='utf-8', errors='replace',
                     creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    except (OSError, subprocess.TimeoutExpired):
        return None
    return parse((result.stdout or '').splitlines())


def fresh(folder, minutes, now=None):
    """A snapshot newer than the interval already exists (a real session wrote it)."""
    now = time.time() if now is None else now
    try:
        paths = list(Path(folder).glob('*.json'))
    except OSError:
        return False
    for path in paths:
        if path.name == SNAPSHOT_NAME:
            continue
        try:
            if now - path.stat().st_mtime < minutes * 60:
                return True
        except OSError:
            continue
    return False


class ClaudeProbe:
    """Runs ``probe`` every N minutes in a worker; never on the UI thread."""

    def __init__(self, panel, folder=None, cli=None, runner=None):
        import claude_launch
        import claude_statusline
        self.panel = panel
        self.folder = Path(folder) if folder is not None else claude_statusline.status_dir()
        self.cli = cli if cli is not None else claude_launch.executable()
        self.runner = runner
        self.last = 0.0
        self.busy = False

    @property
    def minutes(self):
        value = self.panel.prefs.get('claude_probe_minutes', 0)
        return value if value in INTERVALS else 0

    def tick(self, now=None):
        """Called every few seconds; starts a refresh when one is due."""
        now = time.time() if now is None else now
        minutes = self.minutes
        if not minutes or not self.cli or self.busy or now - self.last < minutes * 60:
            return False
        self.last = now
        if fresh(self.folder, minutes, now):
            return False
        self.busy = True

        def work():
            try:
                cwd = self.folder.parent / PROBE_DIRNAME
                cwd.mkdir(parents=True, exist_ok=True)
                windows = probe(self.cli, cwd, self.runner)
                if windows:
                    write_snapshot(windows, self.folder)
            except OSError:
                pass
            finally:
                self.busy = False
        threading.Thread(target=work, daemon=True, name='claude-probe').start()
        return True
