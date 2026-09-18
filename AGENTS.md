# Project Working Rules

## Before starting or resuming
1. Read this file and `PROGRESS.md`.
2. Inspect the repository, `git status`, and all relevant implementation files.
3. Verify documented work exists. Repository files are authoritative; progress notes are a recovery aid.
4. Continue the latest unfinished step without repeating completed work.

## General behavior
- Preserve the architecture, coding style, all useful functionality and user changes.
- Make minimal targeted changes; do not refactor or modify unrelated files.
- Avoid unnecessary abstractions, dependencies and overengineering.
- Before a substantial feature, briefly search GitHub for a compatible maintained implementation. Check its license before adapting code; retain attribution. Stop when a suitable reference is found.
- Never fabricate unavailable telemetry, replace unknown fields with zero, or double-count cached input / reasoning output.
- Keep local usage parsing incremental. Never export transcripts or credentials.

## Progress and interruptions
Maintain concise `PROGRESS.md` throughout multi-step work. Update it at meaningful component, feature, bugfix, decision and verification milestones, before changing major stages, and before an interruption.
Include Status, Current Objective, Completed, Files Modified, Important Decisions, Current State, Known Issues, Tests / Verification, Remaining Work, and an exact Next Step.
Assume usage limits, app restarts, connection loss or a new conversation can interrupt any task. Do not keep important state only in chat. Keep incomplete work clearly documented and the repository runnable where possible.
When asked to continue/resume: reread instructions and progress, inspect actual files and Git status, verify old notes, resume the unfinished step, update progress.

## Verification and completion
Run relevant tests/build and launch the application after meaningful changes. Inspect rendered UI and important interactions. Fix errors introduced by the changes. Do not claim unverified results.
Set Status: COMPLETE only after all requested work is finished and verified. Include summary, changed files, evidence and known limitations. Set IN PROGRESS when new work begins.

## Git and files
- Never reset, revert, clean, overwrite or delete unrelated/uncommitted user work.
- Commit and push only when requested. This task explicitly authorizes uploading the finished app to the existing GitHub repository; preserve its visibility.
- Do not modify dependency/generated folders except necessary build steps.
- Do not modify or expose environment secrets, API tokens, credentials or private keys.
- Never commit `.private/`, local Codex logs, personal screenshots or runtime settings.

## Project commands
Windows Python 3.13+, `.venv/Scripts/python.exe`; dependencies in requirements files.
Tests: `python -m unittest discover -s tests -v`.
Run: `python widget.py`. Live screenshot smoke: `python widget.py --smoke .private/smoke.png`.
Keep source MIT licensed; separate third-party and character-art notices from code licensing.

## Multi-Agent Continuity

This project may be worked on interchangeably by Codex and OpenCode.

Both agents share:
- the same repository
- the same Git working tree
- `AGENTS.md`
- `PROGRESS.md`
- `HANDOFF.md`
- `CHANGELOG.md`
- `ROADMAP.md`
- the external version specifications

Neither agent should assume it is the only agent working on the project.

Before starting/resuming:
- inspect `git status`
- inspect `git diff`
- read `PROGRESS.md`
- read `HANDOFF.md` if present
- read the active external version specifications

Valid existing changes may have been created by the other agent.

Do not overwrite, revert, duplicate, or redo valid work simply because another agent created it.

The repository and files are the source of truth, not Codex/OpenCode chat history.

# External Prompt Library

This project uses an external versioned prompt/specification library located at:

`D:\Desktop\petoken`

Before starting or continuing meaningful work:

1. Read `AGENTS.md`.
2. Read `PROGRESS.md`.
3. Read `CHANGELOG.md` if present.
4. Read `ROADMAP.md` if present.
5. Inspect the current repository state and `git status`.
6. Determine the current/target version.
7. Open the matching version folder under:

   `D:\Desktop\petoken`

8. Read all relevant `.md` files in that folder before making changes.
9. If filenames have numeric prefixes, read them in order.
10. Use those files as the authoritative requirements/specifications for that version.

Example:

`D:\Desktop\petoken\V1.1.0`

or

`D:\Desktop\petoken\V1.2.0`

When the user says things like:

- Continue
- Resume
- Continue the current version
- Read the project state and continue

automatically recover context from:

1. repository documentation
2. current repository state
3. the matching external version folder

Do not require the user to paste the same prompts again.

Do not silently modify the user's original prompt/specification files.

If important implementation findings need to be saved, write them to:

`99_Implementation_Notes.md`

inside the ACTIVE version folder.

Keep roles separate:

- External version folder = what this version is supposed to do
- `PROGRESS.md` = what has actually been completed
- `CHANGELOG.md` = released changes
- `ROADMAP.md` = future ideas, not automatically authorized
- `AGENTS.md` = persistent project-wide rules
