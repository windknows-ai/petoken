# Petoken 2.0: Codex engineering

Branch: `codex/v2.0-engineering`, based on `9d96ee9`.
Scope: Codex modules, their tests, `usage.py`, and this document only.
Existing untracked `assets/v2_0/` artwork is preserved and excluded from this work.

## Progress

- Completed: explicit latest-turn outcomes and per-turn activity outcomes, including terminal errors, interruptions, new starts, identity/fork validation and fail-closed handling.
- IN PROGRESS: finish public usage-event validation and performance/integration documentation, then commit that independent unit.
- Decision: activity turns become `(start, end, project, outcome)`; shared consumers need a Claude-owned migration.
- Decision: ordinary tool errors are not terminal failures; completed turns with explicit terminal errors are failed.
- Next: synthetic regression, real-rollout read-only timing, local commits and integration report. No merge or push.
- First targeted run: 94/95 passed. One new fixture incorrectly expected an unknown total despite a complete input/output breakdown; the existing normalizer correctly derives that total. Corrected the fixture to omit input as well; no existing numeric rule changed.

## 1. Explicit turn outcomes

```python
from codex_recap import turn_outcome, activity

outcome = turn_outcome(home, thread_id)
turns = activity(home, since_epoch)['turns']
# Each item: (start_epoch, end_epoch, project_name_or_None, outcome)
```

`outcome` is `completed`, `interrupted`, `failed`, or `None`. It describes the
latest recorded turn, not the entire conversation or the quality of its work.
A subsequent `task_started` / `turn_started` resets the outcome. An active
turn, absent evidence, unknown status/error shape, identity mismatch, unknown
fork boundary, unreadable/corrupt/incomplete rollout yields `None`.

Evidence is thread-local `event_msg` lifecycle records:

- `task_complete` / `turn_complete`: explicit terminal `status` if present;
  otherwise terminal `error`, or ordinary completion without error.
- `turn_aborted`: interrupted, including replacement/budget-limited aborts;
  no inference that the original requested work was finished.
- Legacy `error` followed by the matching completion: use the protocol's
  `ErrorEvent::affects_turn_status` classification. Control errors
  `ThreadRollbackFailed` and `ActiveTurnNotSteerable` do not fail the turn;
  unknown error classifications yield `None`. Errors alone do not establish
  a finished turn. Tool exit codes, rejected patches and stream retries are
  not terminal outcomes.

The existing validated rollout reader enforces session identity, thread
ownership and fork timestamps. Both historical v1 names (`task_*`) and v2
aliases (`turn_*`) are supported. Synthetic coverage includes desktop, VS Code,
CLI and exec. No app-server connection, process, resume, configuration write
or timing heuristic is used; raw JSON-RPC streams are not read from disk.

`activity()` keeps its previous time, path and mtime filtering. Unknown start
or end times and open turns are omitted. A turn with known start/end and
unknown terminal classification remains present with outcome `None`.
Edits remain `(at, project, relative_path)` with no format change. Existing
`recap()` fields and timing semantics are unchanged.

Verification: `python -m unittest tests.test_codex_recap -q`: **58 passed**.

### Shared integration required before merge (Claude)

`reports.py:summarize` currently unpacks three fields per activity turn and
would raise `ValueError` on a new Codex four-tuple. Read `turn[:3]` for the
duration calculation so mixed Claude three-tuples and Codex four-tuples both
work; consume `turn[3]` when present for outcomes. This branch does not modify
shared code. A completed outcome is transport evidence, not proof that a
todo's acceptance criteria were satisfied; interrupted/failed/unknown must
not be marked completed automatically.

### Official references (checked 2026-10-06)

- [OpenAI protocol source](https://github.com/openai/codex/blob/main/codex-rs/protocol/src/protocol.rs): `TurnStarted`, `TurnComplete`, persisted aliases, terminal `error`, `ErrorEvent::affects_turn_status`, and `TurnAborted`.
- [Official app-server documentation](https://learn.chatgpt.com/docs/app-server): terminal `turn/completed` statuses are completed/interrupted/failed. This provides the classification reference, not a new live transport.

Only the documented behavior was reused; no external code/dependency was copied.
