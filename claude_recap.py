"""What one Claude Code reply did (V1.6 B: task recap).

When a Claude task finishes, the notification says which files it changed,
how long the turn took and what it cost. Everything comes from the
session's local transcript, read from the end:

- The turn starts at the last real user prompt (not a tool result or a
  meta entry) and ends at the last assistant entry after it.
- Files: ``file_path`` of Edit / Write / MultiEdit / NotebookEdit calls
  whose tool result was not an error, from the main transcript and any
  subagent transcripts in that time span. Paths are shown relative to the
  project folder. Shell commands that write files are not counted, so the
  list is "files Claude edited", not every change on disk.
- Cost: the API-equivalent price of every response in the span
  (``pricing.estimate_claude_usd``), each response counted once.

Only tool names, file paths, timestamps and usage numbers are kept; message
text, file contents and commands are never stored.
"""
from __future__ import annotations

import json
from pathlib import Path, PureWindowsPath

from claude_usage import _iso_epoch
from pricing import estimate_claude_usd

EDIT_TOOLS = ('Edit', 'Write', 'MultiEdit', 'NotebookEdit')
TAIL_BYTES = 4 * 1024 * 1024
# A turn with nothing written for this long was waiting (a background task,
# a usage limit, a question), not working: that stretch is left out.
IDLE_GAP_S = 15 * 60


def transcript_files(home, session):
    """The session's main transcript and its subagent transcripts."""
    projects = Path(home) / 'projects'
    if not session or any(c in session for c in '/\\*?[]'):
        return None, []
    main = next(iter(sorted(projects.glob(f'*/{session}.jsonl'))), None)
    if main is None:
        return None, []
    return main, sorted(main.with_suffix('').glob('**/*.jsonl'))


def active_seconds(times, start, end):
    """Seconds from start to end, leaving out every stretch of more than
    IDLE_GAP_S with nothing written (``times``: when anything was written,
    by the main transcript or a subagent)."""
    points = sorted({start, end, *(t for t in times if t is not None and start < t < end)})
    return sum(b - a for a, b in zip(points, points[1:]) if b - a <= IDLE_GAP_S)


def _entries(path, tail=TAIL_BYTES):
    """Complete JSON lines from the last ``tail`` bytes of ``path``."""
    try:
        with Path(path).open('rb') as handle:
            handle.seek(0, 2)
            size = handle.tell()
            handle.seek(max(0, size - tail))
            chunk = handle.read()
    except OSError:
        return []
    lines = chunk.split(b'\n')
    if size > tail:
        lines = lines[1:]          # Started mid-line.
    if lines and not chunk.endswith(b'\n'):
        lines = lines[:-1]         # Writer is halfway through the last line.
    out = []
    for line in lines:
        if b'"user"' not in line and b'"assistant"' not in line:
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if isinstance(entry, dict):
            out.append(entry)
    return out


def _content(entry):
    message = entry.get('message')
    content = message.get('content') if isinstance(message, dict) else None
    return content


def _is_prompt(entry):
    if entry.get('type') != 'user' or entry.get('isMeta') or entry.get('isSidechain'):
        return False
    content = _content(entry)
    if isinstance(content, list):
        if any(isinstance(b, dict) and b.get('type') == 'tool_result' for b in content):
            return False
        content = ' '.join(b.get('text') or '' for b in content
                           if isinstance(b, dict) and b.get('type') == 'text')
    if not isinstance(content, str):
        return False
    text = content.strip()
    # Command wrappers and "[Request interrupted by user]" are not prompts.
    return bool(text) and not text.startswith(('<', '[Request interrupted'))


def _relative(path, cwd):
    if not isinstance(path, str) or not path:
        return None
    if cwd:
        try:
            return PureWindowsPath(path).relative_to(PureWindowsPath(cwd)).as_posix()
        except ValueError:
            pass
    return PureWindowsPath(path).as_posix()


def _scan(entries, start, end, cwd, edits, results, costs):
    for entry in entries:
        at = _iso_epoch(entry.get('timestamp'))
        if at is None or at < start or (end is not None and at > end):
            continue
        content = _content(entry)
        if entry.get('type') == 'assistant':
            message = entry.get('message') or {}
            event = message.get('id') or entry.get('requestId')
            usage = message.get('usage')
            if event and isinstance(usage, dict) and event not in costs:
                costs[event] = estimate_claude_usd(usage, message.get('model'))
            for block in content if isinstance(content, list) else []:
                if (isinstance(block, dict) and block.get('type') == 'tool_use'
                        and block.get('name') in EDIT_TOOLS):
                    tool_input = block.get('input') or {}
                    path = tool_input.get('file_path') or tool_input.get('notebook_path')
                    edits[block.get('id')] = (path, cwd)
        elif entry.get('type') == 'user' and isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get('type') == 'tool_result':
                    results[block.get('tool_use_id')] = not block.get('is_error')


def recap(home, session, finished_at=None):
    """dict(files, started_at, finished_at, duration_s, usd) or None.

    ``files`` is a sorted list of relative paths; ``usd`` is None when any
    response's price is unknown.
    """
    main, subagents = transcript_files(home, session)
    if main is None:
        return None
    entries = _entries(main)
    prompts = [e for e in entries if _is_prompt(e)]
    if not prompts:
        return None
    start = _iso_epoch(prompts[-1].get('timestamp'))
    if start is None:
        return None
    replies = [_iso_epoch(e.get('timestamp')) for e in entries if e.get('type') == 'assistant']
    replies = [at for at in replies if at is not None and at >= start]
    if not replies:
        return None
    end = max(replies)
    # Paths relative to where the prompt was typed, even after a cd.
    cwd = prompts[-1].get('cwd')
    edits, results, costs = {}, {}, {}
    _scan(entries, start, end, cwd, edits, results, costs)
    for path in subagents:
        _scan(_entries(path), start, end, cwd, edits, results, costs)
    files = sorted({_relative(path, cwd) for key, (path, cwd) in edits.items()
                    if results.get(key) and _relative(path, cwd)})
    known = [cost for cost in costs.values() if cost is not None]
    usd = sum(known) if costs and len(known) == len(costs) else None
    finished = finished_at if finished_at is not None else end
    # Waiting (a background task, a used-up limit) is not working time; a
    # subagent writing in its own transcript is.
    times = [_iso_epoch(e.get('timestamp')) for e in entries]
    for path in subagents:
        times += [_iso_epoch(e.get('timestamp')) for e in _entries(path)]
    return dict(files=files, started_at=start, finished_at=finished,
                duration_s=active_seconds(times, start, max(start, finished)), usd=usd)


def _all_entries(path):
    """Every complete user/assistant line of a transcript."""
    return _entries(path, tail=1 << 40)


def activity(home, since):
    """Turns and successful file edits since ``since`` (epoch seconds), for
    reports: ``turns`` are (start, end, project) from each real prompt to
    the last reply before the next prompt, split where nothing was written
    for IDLE_GAP_S; ``edits`` are (time, project, relative path). Files
    untouched since ``since`` are skipped. A resumed session repeats the
    earlier transcript in a new file: each stretch is listed once."""
    projects = Path(home) / 'projects'
    turns, edits = [], []
    seen = set()

    def close(start, last, cwd):
        if start is not None and last is not None and last >= since and (start, last) not in seen:
            seen.add((start, last))
            turns.append((start, last, _project(cwd)))
    try:
        mains = [p for p in projects.glob('*/*.jsonl') if p.stat().st_mtime >= since]
    except OSError:
        return dict(turns=turns, edits=edits)
    for main in mains:
        entries = _all_entries(main)
        subagents = [_all_entries(p) for p in main.with_suffix('').glob('**/*.jsonl')]
        stamped = sorted(((_iso_epoch(e.get('timestamp')), e) for e in entries),
                         key=lambda item: item[0] or 0)
        # A subagent at work keeps the turn going while the main transcript is quiet.
        ticks = sorted((_iso_epoch(e.get('timestamp')), None) for found in subagents for e in found
                       if _iso_epoch(e.get('timestamp')) is not None)
        timeline = sorted(stamped + ticks, key=lambda item: item[0] or 0)
        start = cwd = None
        last = previous = None
        for at, entry in timeline:
            if at is None:
                continue
            if entry is not None and _is_prompt(entry):
                close(start, last, cwd)
                start, cwd, last, previous = at, entry.get('cwd'), None, at
                continue
            if start is None:
                continue
            if at - previous > IDLE_GAP_S:          # It waited: the work so far is one stretch.
                close(start, last, cwd)
                start, last = at, None
            previous = at
            if entry is not None and entry.get('type') == 'assistant':
                last = at
        close(start, last, cwd)
        # Successful edits, main transcript and its subagents.
        folders = {}
        for at, entry in stamped:
            if at is not None and _is_prompt(entry):
                folders[at] = entry.get('cwd')
        prompt_times = sorted(folders)
        for path_entries in [entries] + subagents:
            calls, results = {}, {}
            for entry in path_entries:
                at = _iso_epoch(entry.get('timestamp'))
                content = _content(entry)
                if at is None or not isinstance(content, list):
                    continue
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if (entry.get('type') == 'assistant' and block.get('type') == 'tool_use'
                            and block.get('name') in EDIT_TOOLS and at >= since):
                        tool_input = block.get('input') or {}
                        calls[block.get('id')] = (at, tool_input.get('file_path') or tool_input.get('notebook_path'))
                    elif entry.get('type') == 'user' and block.get('type') == 'tool_result':
                        results[block.get('tool_use_id')] = not block.get('is_error')
            for key, (at, path) in calls.items():
                if not results.get(key):
                    continue
                earlier = [t for t in prompt_times if t <= at]
                cwd = folders[earlier[-1]] if earlier else None
                relative = _relative(path, cwd)
                if relative:
                    edits.append((at, _project(cwd), relative))
    return dict(turns=turns, edits=edits)


def _project(cwd):
    return PureWindowsPath(cwd).name if isinstance(cwd, str) and cwd else ''


INTERRUPTED = '[Request interrupted'


def interrupted(home, session):
    """True when the session's last turn ended because the user interrupted
    it ("[Request interrupted by user…]" after the last real prompt), so a
    "finished" event for it does not mean the work is done."""
    main, _subagents = transcript_files(home, session)
    if main is None:
        return False
    entries = _entries(main)
    last_prompt = max((index for index, entry in enumerate(entries) if _is_prompt(entry)), default=None)
    if last_prompt is None:
        return False
    for entry in entries[last_prompt + 1:]:
        if entry.get('type') != 'user':
            continue
        content = _content(entry)
        texts = [content] if isinstance(content, str) else [
            b.get('text') or '' for b in content or [] if isinstance(b, dict) and b.get('type') == 'text']
        if any(isinstance(t, str) and t.strip().startswith(INTERRUPTED) for t in texts):
            return True
    return False
