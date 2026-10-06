# Petoken 2.0: Codex engineering

Branch: `codex/v2.0-engineering`, based on `9d96ee9`.
Scope: Codex modules, their tests, `usage.py`, and this document only.
Existing untracked `assets/v2_0/` artwork is preserved and excluded from this work.

## Progress

- Completed: explicit latest-turn outcomes and per-turn activity outcomes, including terminal errors, interruptions, new starts, identity/fork validation and fail-closed handling.
- Completed: public usage-event interface, incremental report cache, synthetic regression and read-only timing on the actual large rollout.
- Decision: activity turns become `(start, end, project, outcome)`; shared consumers need a Claude-owned migration.
- Decision: ordinary tool errors are not terminal failures; completed turns with explicit terminal errors are failed.
- Next: Claude migrates the shared report/goal consumers, then the maintainer integrates and accepts the version. No merge or push in this branch.
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

## 2. Public usage-event interface

```python
from usage import CodexStore, usage_events

events = usage_events(since_epoch)  # CODEX_HOME, otherwise ~/.codex
store = CodexStore(home)           # Retain in the report worker for warm reads.
events = store.usage_events(since_epoch)
```

Each event has exactly these fields:

| Field | Meaning |
|---|---|
| `at` | Explicit UTC epoch seconds, or `None` for undated records |
| `thread_id` | Verified session/thread identity |
| `project` | Existing project identity resolution, or `None` |
| `model` | Recorded model ID for the delta, or `None` |
| `total_tokens` | Existing incremental token delta, or `None` |
| `usd` | Existing API-equivalent USD estimate for the delta, or `None` |

The cutoff is inclusive: `at >= since_epoch`. `None` requests all history,
including initial cumulative carry whose date/model are unknown. Numeric
cutoffs omit undated records instead of assigning them to a guessed date.
Results are sorted by time ascending, then thread ID, with undated records
last. Invalid, negative or non-finite cutoffs raise `ValueError`.

This is an event-delta API, not a list of cumulative snapshots or subscriptions
charges. It reuses `SessionUsage`, `distinct_sessions`, `unique_records` and
their existing counter reset, duplicate file/event and fork inheritance rules.
It includes archived threads and independent subagent work, matching global
usage accounting; copied ancestor usage is not counted again. It does not
roll child costs into a parent task. Parents are read even when outside the
requested date range so inherited event IDs can be excluded.

USD uses the existing per-record pricing result (including recorded service
tier and request-size rules), with the same unknown-cache-write guard as
`task_history`: missing required counters/model/price remains `None`, never
zero. No price table or existing live numeric behavior is changed. Existing
normalization can derive a missing total from a complete input/output
breakdown; this established rule is preserved, not replaced by `None`.

There is a separate incremental cache for report reads. The public interface
does not call `read()`, poll approval, start processes or mutate live scope,
analytics or history caches. Missing/unreadable files are excluded immediately,
never served from a stale cache. Completed records before a partially written
tail remain available, and the tail is read only after its newline arrives.
Existing malformed-record handling keeps valid neighboring usage records;
unrecognized counter records expose unknown values rather than invented zeros.

### Shared integration (Claude)

- Replace `reports.py:codex_sources` access to `_scope_sessions` and
  `unique_records` with `store.usage_events(since_epoch)`. Report adapters can
  add `provider='codex'`, map `thread_id` to their session key and
  `total_tokens` to their token field. `at` is now epoch seconds, not an ISO
  string. Keep `task_history` only for thread titles/lifecycle metadata.
- Project usage goals should sum these deltas within the requested range.
  If a relevant amount is `None`, retain an incomplete/unknown result instead
  of treating it as zero. Undated carry cannot be assigned to a daily goal.
- Use a retained Store on a worker, serialize access to that Store, and do
  not put cold history reads on the UI thread. The module function creates a
  fresh Store each call; it intentionally does not hold global process state.

## 3. Verification and measured performance

All tests use temporary synthetic SQLite/JSONL data. Final affected regression:

```text
python -m unittest tests.test_usage tests.test_analytics
  tests.test_codex_recap tests.test_codex_usage_events tests.test_codex_history
  tests.test_codex_approval tests.test_codex_events tests.test_codex_hooks
  tests.test_codex_launch tests.test_codex_focus tests.test_reports -q
```

**291 passed**. This includes 58 recap/activity/outcome tests and 25 public
usage-event tests. Existing report tests use synthetic three-field activity;
they do not validate the new shared four-tuple integration, which remains
Claude's required change described above. The entire UI/native suite was not
run because no shared/UI implementation was changed.

Read-only real-data benchmark on 2026-10-06, `.venv/Scripts/python.exe`, Windows:
the largest rollout was **285,231,397 bytes** (~285 MB / 272 MiB), already
larger than the requested ~228 MB. File metadata/aggregates only were reported;
no dialogue, command text, patches or credentials were exported.

| Operation | Wall time |
|---|---:|
| Latest `turn_outcome`, including local index lookup | 0.769 s |
| Single-rollout `activity(home, 0)` | 0.747 s |
| Single-rollout `store.usage_events(None)`, first Store read | 0.420 s |
| Same Store, repeated single-rollout read | 0.011 s |
| All 123 readable local rollout index entries (~1.052 GB), first read | 1.977 s |
| Same Store, repeated all-history read | 0.041 s |

Single-rollout timings isolate its row with a temporary `thread_rows` mock;
all-history timings use the actual SQLite index. These are single wall-clock
samples with the Windows filesystem cache present, not cold-disk guarantees.
The active file grew by 907 bytes during the benchmark. Warm report reads
reuse parsed records and consume only appended data. Sorting/deduplication
still runs each time and the memory cache grows with retained usage records.

The large real rollout yielded 51 closed turns: **37 completed, 3 interrupted,
11 failed**; its latest open turn correctly returned `None`. Synthetic tests
establish the failure/interrupt classification; this real check confirms the
record formats are present, without launching or interrupting a real task.

## 4. Limits / handoff

- Local metadata and persisted rollout only; missing, pruned, cloud-only or
  not-yet-flushed evidence cannot establish a terminal outcome or full usage.
- A completed turn does not prove the work's correctness. A later user turn
  clears the prior outcome; no idle timer or inferred success is used.
- The lifecycle reader fully streams the qualifying rollout each call. Call
  on demand/in a worker; it is not a replacement live notification transport.
- Usage-event results have no stable external event ID in the requested
  schema. Fetch a range and replace that report slice; appending every response
  to a persistent database without deduplication would recount events.
- Store cache access is synchronous and not designed for concurrent callers.
- Final changed files: `codex_recap.py`, `tests/test_codex_recap.py`, `usage.py`,
  `tests/test_codex_usage_events.py`, and this document. Existing artwork and
  shared files remain outside these commits.
- Outcome commit: `320855a`. The independent usage-event commit follows this
  document update. Deliver the local branch; do not merge or push it.
