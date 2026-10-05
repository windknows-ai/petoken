@AGENTS.md

# Claude in this repository

AGENTS.md is the shared rulebook for every agent here. The overrides below apply to Claude only.

## Role and file ownership (decided by the maintainer, 2026-10-05)

Codex and Claude work in parallel by provider and never review each other's code; the maintainer does the final visual and functional acceptance.

- **Codex owns**: `usage.py`, `tests/test_usage.py`, Codex test fixtures, every `codex_*` module and its tests, and the Codex continuity files `AGENTS.md`, `HANDOFF.md`, `PETOKEN_CODEX_EXECUTION_STATE.md`.
- **Claude owns**: every `claude_*` module and its tests, plus all shared code (`providers.py`, `provider_selection.py`, `provider_poller.py`, `widget.py`, `pet.py`, `workbench*.py`, `localization.py`, `pricing.py`, `app_config.py`, `desktop.py`, `analytics*.py`, `tools/`, docs, build files).
- Claude never edits Codex-owned files. A needed change there goes to the maintainer as a one-line request for Codex.
- Claude does not run the AGENTS.md "auto-synced" instruction sync and does not write `HANDOFF.md`; Claude's continuity lives in `CLAUDE_PROGRESS.md`.

## Branches and merging

- Claude works in its own worktree on `claude/<version>` branches; Codex uses `codex/<version>-…` branches.
- Claude merges a finished Codex branch after two automatic checks only: the branch touched nothing outside Codex's files, and the full test suite passes. A failure goes back to Codex through the maintainer; Claude does not fix Codex files.
- Merging to `main`, tagging, pushing and publishing need the maintainer's explicit authorization.

## Working notes

- Python: `D:\Documents\ChatGPT\codex-widget\.venv\Scripts\python.exe`; tests: `python -m unittest discover -s tests`.
- Tests that poll providers set `PETOKEN_CLAUDE_HOME` to a never-created directory so real `~/.claude` data never leaks into results; keep new poller tests hermetic the same way.
- Isolated visual QA: `python tools/preview_v1_3.py --provider mixed` (synthetic Codex blue and Claude gold stars, no provider reads, temporary settings).
