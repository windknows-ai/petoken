# Current V1.5 sources: Codex and Claude Code

V1.5 tracks exactly two providers: Codex and Claude Code. No other provider
will be added. Settings offer Auto (default), Codex or Claude Code. Auto
follows the provider whose task is verifiably working, and stars show both
providers' working tasks: Codex stars are blue, Claude Code stars are gold.
A manual choice shows only that provider in the Hub and the stars. Legacy
OpenCode preferences migrate to Auto, and so does the forced `codex` value
that Codex-only builds (settings schema 1) saved without a user choice.

## Claude Code (V1.5) verification record

Verified on Windows against Claude Code 2.1.286 (CLI and the desktop app's
Code tab share one data directory). Adapter: `claude_usage.py`.

- **Data directory**: `%USERPROFILE%\.claude`, or `CLAUDE_CONFIG_DIR`.
  `PETOKEN_CLAUDE_HOME` overrides it for tests and isolated QA only.
- **Transcripts**: `projects/<encoded launch dir>/<sessionId>.jsonl`, one
  JSON object per line; subagent transcripts carry their parent's
  `sessionId`. Only `type: "assistant"` lines carry `message.usage`.
- **Duplicated usage**: one API response is written as several lines (one
  per content block) that repeat identical usage. Records dedupe by
  `message.id` (fallback `requestId`); counting lines would multiply tokens.
- **Usage fields**: `input_tokens`, `cache_read_input_tokens`,
  `cache_creation_input_tokens` with a `cache_creation` split
  (`ephemeral_5m_input_tokens` / `ephemeral_1h_input_tokens`),
  `output_tokens`, `output_tokens_details.thinking_tokens`, `speed`,
  `inference_geo`. `message.model` names the model; `<synthetic>` marks
  locally generated messages without API usage and is skipped.
- **Metadata used**: `sessionId`, `timestamp`, `cwd`, `gitBranch`, `effort`,
  `version`, `isSidechain`, and `custom-title` lines (session title). A
  session belongs to the directory it started in.
- **Live sessions**: each running process writes `sessions/<pid>.json`
  with `sessionId`, `cwd`, `status` (`busy` while a turn runs),
  `statusUpdatedAt` (ms), optional `name` and `procStart`. `procStart`
  equals the process creation FILETIME reported by `GetProcessTimes`, so
  a session is Working only when its entry is `busy` AND that exact
  process (pid plus creation time) is alive. A missing registry makes
  activity unknown, never idle.
- **Not available locally**: subscription 5-hour/weekly limits, reset
  times, the context window and billed amounts. These stay `N/A`.
- **Privacy**: transcript lines are parsed in memory only to reach numeric
  usage and the metadata above; message content, prompts, tool input and
  output are never stored, displayed, logged or exported.

Read only numeric usage/task metadata. Unknown model remains Unknown, unavailable usage/quota/cost remains N/A, real zero remains zero, and partial coverage remains explicit. Model pricing must support any API-equivalent cost estimate. Working/Idle evidence does not establish finer task phases.

The former OpenCode adapter and its low-level tests remain internal historical compatibility material while active runtime/UI/configuration paths are removed. They do not constitute a supported current provider, an active polling lane, or authorization to read its store. The records below are retained to preserve verified history and shared-infrastructure reasoning; they describe earlier slices and the released v1.2.0 product, not current V1.3 behavior.

## Historical OpenCode discovery and implementation record

> Astra review: **PASS WITH CONDITIONS for Slice 2 (Codex wrapper only)**.
> Observations below are preserved, but these conclusions are NOT accepted:
> cache_read 501.7M versus input 18.3M cannot establish a cache subset of input;
> OpenCode token subset/total semantics need verification. A step-finish with
> tool-calls does not establish session completion. Project identity joins,
> session-level activity and exact abandoned-work expiry remain unproven.
> Cost currency stays unknown; no currency symbol or conversion is justified.
> See V1.2 `04_OpenCode_Slice_2_Handoff.md` for the bounded next slice and gates.

Discovery/documentation only (V1.2 Slice 1). No adapter, UI, or selector was
implemented from this. Verified facts below; proposals are marked as such.
All queries were read-only, metadata-only, short-timeout projections against
the installed tool. No auth material, prompts, responses, source code, tool
arguments, conversation exports, or content-bearing rows were read.

## 1. Tested version and source

- Installed product: `opencode-ai` npm package, version **1.18.31**
  (`opencode --version`; `package.json` agrees; MIT license). Binary-only
  `bin/opencode.exe`; no bundled JS source to inspect.
- Structured source: SQLite at `%USERPROFILE%\.local\share\opencode\opencode.db`
  (from `opencode db path`), WAL mode, ~527 MB on this machine.
- Official CLI surface used: `opencode stats [--days N] [--models] [--project]`,
  `opencode db [SELECT …] --format json`, `opencode session list` (exists, not
  run — lists titles). `opencode export` was NOT used (content-bearing).
- Live population at discovery: 54 sessions, 2867 messages, 12784 parts,
  46983 events, 2 projects. Counts drifted slightly between queries: the
  store is actively written during normal use.
- Side effect observed: `opencode db` saves oversized outputs into the
  tool's own `tool-output/` directory. Keep queries small (aggregates,
  key listings, tight LIMITs); never dump full rows.

## 2. Safe field map

Timestamps are **milliseconds since epoch** (verified: `MAX(session.time_updated)`
matched wall-clock seconds before querying). IDs are opaque `ses_…` strings.

### `session` — canonical per-session rollup (preferred source for totals)

| Column | Type | Slice-1 finding |
| --- | --- | --- |
| id | TEXT | Stable session key (`ses_` prefix). Use truncated only in logs. |
| project_id | TEXT | Joins `project.id`. Both local projects are unnamed (`name` NULL). |
| parent_id | TEXT | Set on 30/54 sessions: fork/branch lineage. Dedup/fork logic must handle chains; do not reuse Codex fork rules unverified. |
| title/slug/directory/path | TEXT | Title is user content: display-only like Codex titles, never analytics input. `directory` maps cwd identity (never log full paths). |
| model | TEXT | JSON `{"id","providerID","variant"}`. 4 distinct observed (`opencode`, `meta`, `openai` providers; `xhigh`/`default` variants). Arbitrary IDs must pass through verbatim. |
| agent | TEXT | Observed `build`, `general`. |
| tokens_input/output/reasoning/cache_read/cache_write | INTEGER | Rollup columns. Raw evidence: session totals input 18.3M, output 1.2M, reasoning 632K, cache_read 501.7M, cache_write 0 (CLI agrees). One session showed SUM(message input deltas) == rollup exactly (8,075,044); the general formula is UNVERIFIED. **Correction (Slice 2 review): cache_read 501.7M cannot be a subset of input 18.3M, so the Codex cached-⊆-input invariant does NOT transfer.** Cache/input/output/reasoning relationships are UNVERIFIED: preserve the raw columns, never add them, never assume subset semantics. |
| cost | REAL | Canonical recorded amount. Total $0.7135 matches `opencode stats` `$0.71` exactly. |
| time_created/updated/compacting/archived | INTEGER | ms. `archived`/`compacting` are 0/NULL on all 54 rows here: no completion signal has ever fired locally; do not rely on it. |
| metadata | TEXT | Empty on sampled rows. No hidden fields. |
| share_url/revert/permission/summary_* | — | Existence noted; values not read (potential links/diffs). |

### `message` — per-message deltas and activity ticks

Columns: id, session_id, time_created, time_updated, data (JSON).
`data` envelope keys (exact): parentID, role, mode, agent, variant, path,
cost (INTEGER), tokens (double-encoded JSON string), modelID, providerID,
time (`{created[, updated]}`).
`tokens` inner keys (exact): input, output, reasoning, cache (`{read, write}`).
Roles observed: `assistant` 2720 / `user` 167. The 167 user-role messages are
the most defensible "explicit user use" signal for recency.

### `part` — tool lifecycle and content parts (metadata envelope only)

Columns: id, message_id, session_id, time_created, time_updated, data (JSON).
Envelope keys (exact): type, tool, callID, state, metadata.
`type` vocabulary with counts: tool 3757, step-start 2715, step-finish 2709,
reasoning 2737, text 530, patch 417, file 16, compaction 7.
`tool` names match `opencode stats` TOOL USAGE exactly (read/bash/edit/…).
`step-start` data keys: type, snapshot. `step-finish` keys: type, reason,
snapshot, tokens, cost. Finish `reason` values observed: `tool-calls` 2552,
`stop` 146, `unknown` 10. **No error/abandoned reason exists**: error-specific
completion detection is UNAVAILABLE. **Correction (Slice 2 review): a
step-finish — especially `tool-calls`, which only advances the loop — is NOT
proven session completion.** Session-completion semantics are UNRESOLVED;
consume step-finish only as step-boundary evidence.

`state` (tool parts) holds full tool-call records including arguments and
outputs: the adapter must project `type`/`tool`/timing only and must never
read `state.input/output`, `text`/`reasoning` parts, `file`/`patch` contents,
`session_input.prompt` (table empty here: 0 rows — legacy/unused, still
off-limits), or `export` output.

### `event` / `event_sequence` — event-sourced changelog, not a lifecycle state

`event(aggregate_id, seq, type, data)` with index on (aggregate, seq).
Only 4 types exist: `session.created.1` (54), `session.updated.1` (3066),
`message.updated.1`, `message.part.updated.1`. No started/completed/error
types: events order revisions (dedup by aggregate+seq, replace-not-append)
but cannot alone declare a session working.

### Project mapping

`project(id, worktree, vcs, name NULL, …)`, `project_directory(project_id,
directory, …)`, `session.directory`, `workspace(…time_used…)` — workspace is
EMPTY here. **Correction (Slice 2 review): stable session.project_id →
project mapping is UNRESOLVED** (worktree multiplicity, missing names, and
directory fallback all unverified). A directory basename is display text, not
unique identity; display falls back to basename or unavailable, never invented.

## 3. Cost, currency, and subset semantics

- Canonical cost: `session.cost` (REAL). Verified total $0.7135 == CLI `$0.71`.
- Per-message `cost` (INTEGER) does **not** sum to session cost (verified: 0
  vs 0.307 on the latest session). Never sum message costs; use session
  rollups for totals and message deltas only for recency/activity.
- **No currency column exists anywhere** (searched all table definitions).
  The CLI presents `$`; treat the recorded amount as currency-unstated per
  01 §Accounting (unknown currency yields unavailable for conversion; a
  recorded 0.0 remains a valid zero, e.g. free-tier models show `$0.0000`).
- Token subset rules are UNVERIFIED for OpenCode (correction, Slice 2
  review): do not mirror Codex (uncached inputs, non-reasoning outputs,
  cache-write inference). Raw columns are preserved as-is; missing components
  propagate unknown; never infer cache-write from uncached input.

## 4. Capability / unsupported matrix

| Capability | Status | Evidence |
| --- | --- | --- |
| Session identity/model (project mapping unresolved) | SUPPORTED* | `session` columns + `model` JSON; 4 models observed; project join UNRESOLVED (see §2) |
| Token totals + input/output/reasoning/cache splits | SUPPORTED (raw only) | Rollups present, CLI-reconciled; inter-field formulas UNVERIFIED |
| Recorded cost amount | SUPPORTED | REAL column, CLI-reconciled; currency unstated |
| Cost currency | UNSUPPORTED | No column; CLI `$` is presentation only; converted/labelled cost stays N/A (Slice 2 condition) |
| Live working/busy signal | PROVISIONAL (expiry unresolved) | Unmatched step-start + fresh part writes observed live; exact expiry TBD slice 4; one observation does not prove the full rule |
| Session completion | UNRESOLVED | step-finish observed but NOT proven session completion (esp. `tool-calls`); no error-specific reason exists |
| Expiry/abandonment timestamps | UNSUPPORTED | `time_archived` never set locally |
| Quotas/limits | UNSUPPORTED | No source table/columns found |
| Daily calendar history | SUPPORTED* | Derivable from message/part `time_created` (ms); session-totals-only fallback is N/A for ranges |
| Cache-write nonzero values | UNVERIFIED | Column real, all zeros locally |
| Fork/branch chains | SUPPORTED* | `parent_id` present; merge semantics unverified — slice 3 must test |
| Incremental indexed reads | SUPPORTED | `message_session_time_created_id_idx`, `part_session_idx`, `session_project_idx`, `session_parent_idx` |
| `session_input`/workspace `time_used` | UNSUPPORTED | Empty tables here |

## 5. Activity and recency evidence (live, provisional)

Candidate working rule (Slice 4 must still prove it across tool-call steps,
long silent tools, abandonment, and process/session association): a session
is working iff it has a step-start with no later step-finish **and** fresh
part writes, subject to a bounded expiry. Observed 2026-09-20 ~18:05 local
(one observation — explicitly not proof of the full rule):

- 4 unmatched step-starts across 3 sessions; one opened ~20 s before the
  probe with 4 newer parts, while multiple `OpenCode.exe` processes were
  running. Independent live activity, structurally matching the rule.
- Two stale unmatched opens (~1 day and ~2.7 days old, `big-pickle` model):
  proof that open steps MUST expire — a 1-day-old open step is not work.
  The exact expiry threshold is UNRESOLVED (Slice 2 condition); slice 4 must
  justify it with session-level evidence, not assume parity.
- Comparable ms timestamps for ranking: `session.time_updated`,
  `message/part.time_created`, user-role message times (explicit use).
  Polling/reads write no session rows, so reads never fake activity.
- Neither-working fallback: most recent activity above, else explicit
  provider choice (petoken-side pref, slice 4). Unknown timestamps stay
  unknown; ties keep the current selection.

## 6. Privacy boundary

Allowlist: table/column names; enum vocabularies (roles, reasons, tool
names, part types); integer counts/sums; ms timestamps; truncated IDs;
`model`/`agent`/`variant`/`providerID` strings; project mapping mechanism.
Denylist: `auth.json`, `credential`/`account*` tables, prompts, responses,
`text`/`reasoning`/`file`/`patch` part contents, tool `state` arguments and
outputs, `session_input.prompt`, full directory paths, share URLs,
`opencode export` output, whole content-bearing JSON rows. Keep every query
a projection or aggregate; keep CLI outputs small to avoid the tool-output
side effect noted in §1.

## 7. Incremental strategy (proposal for slice 3)

SQLite read-only with ≤250 ms busy timeout and explicit close; per-provider
single in-flight query; active checks ≥1 s apart; history on demand ≤1/30 s.
Cursors: per-session `MAX(time_created)` on message/part via
`message_session_time_created_id_idx` / `part_session_idx`; event replay by
`(aggregate_id, seq)`; scope via `session_project_idx`; fork walk via
`session_parent_idx`. Session rollups are the totals level; message deltas
are the recency/activity level — never mix the two into one sum. Stale after
5 s without a successful active refresh (per 01); usage timestamps are not
freshness timestamps.

## 8. Synthetic fixture definitions (shapes only, for slice-3 tests)

- `session` row: `{id: "ses_<rand>", project_id, parent_id|null, model:
  {"id","providerID","variant"}, tokens_{input,output,reasoning,cache_read,
  cache_write}, cost: REAL, time_created/updated: ms}`.
- `message` row: `{id, session_id, time_created, data: {role: user|assistant,
  mode, agent, variant, path, cost: INT, tokens: STRINGIFY({input, output,
  reasoning, cache: {read, write}}), modelID, providerID, time: {created}}}`.
- Lifecycle: `part{type: step-start}` … `part{type: tool, tool, callID}` …
  `part{type: step-finish, reason: stop|tool-calls|unknown}`; an open step has
  no later step-finish; stale opens (≥1 day) must expire.
- Fork: child row with `parent_id` = parent `id`; dedup by provider + id;
  revisions replace by `(aggregate_id, seq)`.
- No real content, paths, credentials, or full rows in fixtures.

## 9. Blockers and open questions for Astra review
1. No BLOCKER for a history adapter (slice 3 can proceed on this source).
2. Automatic OpenCode Token Mode is FEASIBLE via the step-start/finish rule
   with expiry — final thresholds and the 1 s stability/0.4 s/2 s interplay
   belong to slice 4. Error-specific completion is unavailable by design.
3. Cost currency is unstated: slice 3/6 must decide display treatment
   (suggest: show recorded amount, never convert, label provenance).
4. `session_input`/`workspace` are empty here: code must treat them as
   optional, not assumed.
5. Live-busy proof rests on one same-day observation plus structural
   pairing; slice-7 live acceptance (Codex work, OpenCode work, both
   simultaneous, long tool) remains required per 02.

## 10. Slice 3 adapter record (implementation, OpenCode)

`opencode_provider.py` (new, uncommitted) implements the read-only
incremental adapter from the verified mappings above; `providers.py`
delegates OpenCode capability lookup to it (`is_supported` is consistent
with the adapter, no hard-coded deny, no plugin framework).

Resolved before aggregating (live metadata-only reconciliation,
opencode-ai 1.18.31, 54 sessions / 2976 messages at probe time):

- Token relationships: message deltas sum to session rollups within
  live-write drift (input 18.84M both levels), while cache_read (551M)
  dwarfs input — Codex subset/total formulas do NOT transfer. Adapter
  sums same-category raw columns only; `total` stays unknown with a
  `total_unavailable_no_verified_formula` note.
- Fork inheritance: three live fork children show rollup == own message
  deltas exactly, so rollups are own-session totals and scope sums need
  no exclusion. Dedup is provider + session id; `parent_id` chains are
  preserved scoped in history rows.
- Project joins: 0 orphan and 0 NULL `project_id` rows; both project
  names NULL. Scopes group by `project_id` (identity
  `opencode:<id>`); display falls back to directory basename or
  unavailable — never grouped or invented from basenames.
- Revisions: all 54 rows have `time_updated > time_created`, so the
  incremental cursor is `time_updated`-based with replace-by-id;
  shrink/replacement of the store file forces a full resync.
- Timestamps are ms; `last_activity_at` is max selected `time_updated`;
  daily buckets use local calendar days over message `time_created`.
- Cost: `SUM(session.cost)` matched the adapter to the unit with
  `recorded` coverage; message costs (sum 0) are never aggregated.
  Amount preserved, currency None, recorded 0.0 kept as a real zero.
- New tables since slice 1 (`account`, `credential`, `permission`,
  `todo`, `session_share`, …) are never touched; `account`/`credential`
  are empty locally. `summary_*`, titles, paths, share URLs, icon URLs,
  part `state`/text and message bodies are not projected.

Live adapter check: global read over 54 sessions matched direct SQL
exactly on all five categories and cost (19,005,697 / 1,290,064 /
710,092 / 557,219,221 / 0 input/out/reason/cread/cwrite; cost 0.9208
recorded); one conversation read matched its session row exactly.

Declared OpenCode capabilities: `scopes`, `history`, `cost_recorded`,
`nullable_fields`, `incremental_cache`. Explicitly NOT declared:
activity/working context/completion/expiry (slice 4 gates; step-finish,
esp. `tool-calls`, is still not session completion), quotas, cost
currency/estimates, daily ranges from session totals, combined
cross-provider totals (no such code path exists).

Tests: `tests/test_opencode_provider.py` (synthetic stores only) —
missing/locked/unsupported stores, all-missing/mixed/real-zero token
coverage, daily unknown/partial/complete coverage, nullable-vs-zero,
arbitrary/malformed models, project/global/conversation scopes, fork
chains, same-size/larger replacement, timestamp rollback, deletion,
repeated-read idempotence, text/bool/negative/non-finite/out-of-range
field rejection, calendar boundaries, message-cost exclusion, bounded
history-cache behavior (unchanged/revised/deleted/30 s-stale), provider
isolation. Plus Slice 2 conditions:
deterministic non-null working-context parity across scopes/history
with a missing-scope selection, and Codex cost provenance
(usd/unknown/partial beside the numeric alias).

## 11. Slice 3 correction record (re-review fixes, OpenCode)

Astra's four correction items are implemented in `opencode_provider.py`
(still uncommitted), no fork subtraction or activity claims added:

1. Unknown is never zero: all-None categories sum to None with
   `unknown` coverage; real zeros stay complete zeros; known subtotals
   stay explicitly partial. Daily buckets carry per-day per-category
   `daily_coverage` (unknown/partial/complete) beside the flat values.
2. Replacement/revision correctness: every refresh re-projects the
   session table with a single SELECT snapshot and diffs by stable id —
   deliberately no skip-if-unchanged detector, after adversarial probes
   showed file-size, mtime and cross-connection data_version comparisons
   all miss committed writes (a retained WAL writer with checkpoints
   disabled leaves main-file stat and fresh-connection data_version
   unchanged while new values are readable). Same-size/larger
   replacement, timestamp rollback and deletion are picked up by the
   value diff; file identity (ino/dev) only guards history-cache
   validity across replacement, never session freshness.
3. Malformed metadata is validated: token cells require finite
   non-boolean numbers ≥ 0, cost any finite non-boolean number,
   timestamps finite non-boolean ≥ 0; message delta rows with
   boolean/negative/non-finite/wrong-typed numbers are skipped whole.
   Out-of-range timestamps are guarded at date conversion. Corrupt
   cells become unknown (never zero), good rows keep honest coverage,
   and an `invalid_values_rejected` note is emitted.
4. History is cached and bounded: per-selection cache keyed by scope +
   pinned with a message (count, max-time_updated) fingerprint.
   Fingerprint changes and session-revision invalidation only mark the
   entry pending and coalesce — the previous scan keeps serving with
   its as_of plus a `history_refresh_pending` note — and a rescan
   happens only after the 30-second floor elapses. Floor expiry alone
   never rescans unchanged data. Totals recompute from scratch (never
   accumulate). History carries `as_of`/`cached`/`refresh_pending`;
   envelope partial reflects daily coverage and skipped rows.

Re-validation: 37 adapter + 12 provider tests green with the coupled
suites (94 total); live adapter output still matches direct SQL exactly
on all 54 sessions and one conversation row; `py_compile` +
`git diff --check` clean; no build/DPI/full suite per the lightweight
rule. `nullable_fields` and `incremental_cache` are now substantiated
by the above regressions.

## 12. Second correction record — WAL + history floor (OpenCode)

Re-review BLOCKED items, fixed in `opencode_provider.py` (uncommitted):

1. WAL-aware freshness with no detector: premise reproduced locally —
   after a retained-writer WAL commit (checkpoints disabled),
   fresh-connection `data_version` stays 2 and main-file stat is
   identical while a fresh SELECT already sees the new value. Session
   refresh therefore always projects and diffs; file identity (ino/dev)
   only clears history on true replacement. Regressions: WAL update /
   delete visible with the writer held open, uncommitted writes
   invisible with correct post-rollback values.
2. Genuine 30-second history floor: successive changes coalesce into
   one pending flag; the stale scan keeps serving with frozen as_of
   until the floor elapses (3 rapid writes → 1 scan, then exactly 1
   rescan with latest totals). Session revisions mark pending instead
   of clearing; floor expiry without change never rescans.

Re-validation: 42 adapter + 12 provider tests green with the coupled
suites (99 total); live adapter output still matches direct SQL exactly
on all 54 sessions; `py_compile` + `git diff --check` clean; no
build/DPI/full suite. No commit/push/version bump. Slice 4 NOT started.

## 13. Slice 4 activity evidence and expiry justification (OpenCode)

Live step-structure probe (metadata timing only, 2938 messages):

- Steps pair within `message_id`: 2933 messages carry both step-start
  and step-finish, 5 start-only, 0 finish-only. Open-step detection is
  therefore per-session latest-start vs latest-finish.
- Completed-step durations: median 3.3 s, p99 109 s, max 597 s (2/2933
  steps exceed 5 min). Durations already include any silent running
  time (finish minus start regardless of writes).
- Inter-step gaps (finish to next start, same session): median 6 s,
  p90 50 s, p99 225 s; 7.7% exceed 60 s. The 60 s grace bridges normal
  model latency; longer gaps briefly drop the badge and self-heal on
  the next start.
- `tool-calls` finishes are followed by a new start in 42 sessions;
  even `stop` finishes are followed by one in 13. Neither reason proves
  session completion, so completion as a distinct state stays
  unavailable — idle means no open step and no finish inside grace.
- Three sessions held open steps at probe time: one live (newest part
  1.2 s old, working) and two abandoned (2.3/2.8 days old, correctly
  idle). Stale opens exceed any candidate expiry by orders of magnitude.
- `session.time_updated` sits within ~1 s of every open step-start
  (step-start bumps the row), so probing sessions touched inside
  expiry + 300 s margin provably recalls every working session.
  (Row clocks also move on non-part writes — e.g. one row 2.7 days
  newer than its parts — so they are recall-grade, and ranking-grade
  for recency, never audit-grade.)

Rule implemented in `OpenCodeProvider.activity_snapshot` (one coherent
statement projecting ordered per-message type/reason/timing metadata
only): an ordered state machine pairs starts/finishes inside each
message_id — one start per message is NOT assumed
(start→finish→start leaves the latest step open; several completed
steps in one message close it; equal timestamps close
deterministically; finishes never close other messages' opens).
Recall does not depend on unproven session metadata: the statement
covers recently-touched sessions' parts, window-fresh parts
store-wide, and timeless step parts anywhere, so a stale session row
can never hide a fresh valid open step (regressed explicitly), and
idle is sound for sessions holding none of those. Timestamps must be
finite, non-boolean, non-negative and not in the future; unusable
evidence stays unknown per message/session — verdicts derive from
valid evidence only, doubt is flagged, and nothing can crash or
fabricate. Working iff any open message is younger than 900 s
(`OPENCODE_WORKING_EXPIRY_S` = 1.5x the longest completed step ever
observed) or the latest finish is under 60 s
(`OPENCODE_STEP_GRACE_S`, covering >92% of observed gaps). Fresh part writes are reported as evidence but never
required, so long silent tools stay active. Unreadable stores yield
valid=False (unknown, never idle). Expiry/grace are candidate
policies, not proven semantics: their basis, confidence and known
false positives/negatives travel in the snapshot `policy` record.
Session-update order is recall-grade context only (300 s margin
constant retained for the window); exhaustive recall comes from the
part-driven predicates above, not from trusting row metadata.

Live check after implementation: the genuinely working session
(1.8 s-old open step) reports working via open_step; a session whose
tool-calls finish landed 68.6 s earlier correctly reports idle
(past grace, no new step yet).

Selection (`provider_selection.py`, pure logic, no I/O): manual
Auto/Codex/OpenCode wins at once and clears pending Auto state
(invalid/legacy to Auto, persisted through the existing tolerant
settings, no UI in this slice); Auto ranks sole working, then newest
attributable activity among working, then max(activity, manual use)
while staying Daily/historical; ties and unknowns retain current,
then stable provider ID order; 1 s switch stability except immediate
switch off unavailable providers; live badge follows current input
immediately; sources stale after 5 s without successful poll lose live
claims but keep history flagged stale; poll generations reject late
payloads while reevaluating freshness against current time with the
current preference, and mismatched provider tags are dropped.
Availability is three separate flags — source (store readable),
scoped-data (current selection resolved) and activity validity — so a
missing pinned scope never excludes a working provider, and unverified
working stays unknown (never confirmed idle) in the output.
Shapers are fail-closed: absent results, missing detector blocks and
explicit source failures (status_no_local_data,
status_database_unavailable) yield unavailable/invalid even beside
cached working data (cached history stays displayable, never proves
work). Recency uses attributable instants only: OpenCode lifecycle
starts/finishes, Codex working-session token events; row-update
clocks, poll times and file mtimes are never used — an idle
session/thread metadata edit cannot move either provider's instant
(pinned by before/after tests both directions). Foreground/session
titles never enter selection. Feeding the
selection's live claim into the unchanged `AppModeState` preserves the
0.4 s / 2.0 s hysteresis (input parameter generalized from
`codex_active` to `active`; all call sites positional).

## 14. Slice 4 correction record (re-review fixes, OpenCode)

Astra's five BLOCKED items, fixed without Slice 5 work:

1. Manual bypass: manual choices switch at once and clear pending Auto
   state in both directions (previously debounced behind pending_switch).
2. Validity separation: source / scoped-data / activity-validity are
   independent flags. A missing pinned scope keeps a working provider
   eligible and live; unreadable activity yields unknown (output
   `activity_unknown`, never confirmed idle); errors exclude the
   provider while freshness independently gates live claims.
3. Late batches contribute no payload but still reevaluate freshness
   against current time with the current preference (a 6 s-delayed
   batch returns live=False/stale=True, and a manual change landing
   mid-poll applies at once); mismatched provider tags are dropped.
4. Message-scoped pairing from one coherent statement (the live
   two-orphan session behaves identically under both rules today, but
   synthetic overlap now reports working); equal timestamps close;
   future/TEXT timestamps stay unknown without crashing; uncommitted
   writes stay invisible; racing commits keep every snapshot
   structured.
5. Policy explicitness: the `policy` record (basis/confidence/false
   positives-negatives) travels with every snapshot; recency uses
   attributable lifecycle/token instants only — an idle session-row or
   thread-row edit cannot move either provider's instant (pinned by
   before/after tests both directions).

Re-validation: 20 new + updated focused tests; FULL suite green (371
tests); live snapshot re-verified (open_step working, 87.5 s-old
finish idle, policy attached); `py_compile` + `git diff --check`
clean; no build/QA matrix. No commit/push/version bump.

## 15. Slice 4 final correction record (validity/lifecycle/recall)

1. Fail-closed validity: `codex_provider_status(None)`, missing
   detector blocks and explicit source failures
   (status_no_local_data/status_database_unavailable) yield
   unavailable/invalid even beside cached working data (cached history
   stays displayable, never proves work); `_activity_valid` and
   `_source_available` default missing flags to False; hand-built test
   statuses declare verified validity through a documented
   verified-fixture helper, with raw-dict tests pinning the
   fail-closed defaults and real envelopes covering the production
   path end-to-end (absent result, missing detector block, omitted
   validity, source failure + cached context, failure + history,
   missing scope + working, verified idle, verified working).
2. Same-message lifecycle: ordered per-message state machine (FIFO
   unmatched starts; equal timestamps close deterministically;
   stray finishes feed recency, never close other messages) from one
   coherent statement; TEXT/future/NULL timestamps stay unknown
   without crashing; uncommitted writes stay invisible; racing
   commits stay structured.
3. Recall without prefilter trust: part-driven predicates
   (recent sessions, window-fresh parts, timeless steps) replace the
   row-clock prefilter as the recall mechanism — stale
   session.time_updated + fresh valid open step reports working
   (regressed explicitly). Recency stays attributable-only both
   directions (verified by before/after idle-edit tests).

Re-validation: 16 new/updated focused tests; FULL suite green (387
tests); live snapshot re-verified (two concurrent open_step sessions,
policy attached); `py_compile` + `git diff --check` clean; no
build/QA matrix. No commit/push/version bump. Slice 5 NOT started.

## 16. Slice 4 validity-boundary addendum (outer reason)

Source failure is detected at BOTH envelope layers (outer reason and
payload status) in both shapers: an outer
`status_database_unavailable` (Codex) or `missing_store`/
`store_locked`/`unsupported_schema` (OpenCode) invalidates source and
working claims even when the payload still carries old successful or
cached data (regressed: only the outer reason changed, cached
working_context kept). `status_pinned_unavailable` stays benign at
either layer. Re-validation: 2 new shaper regressions; focused
provider/selection suites green; compile/diff clean.

## 17. Slice 4 dual-layer correction (payload status)

The OpenCode shaper previously checked payload existence plus the
outer reason only — a `payload.status` failure marker beside an empty
outer reason stayed source-available and could go Live. Both shapers
now check outer reason AND inner payload status against their failure
sets (missing/non-dict payloads stay unavailable without raising);
either layer reporting a source failure forces source_available False,
working False and validity down, while cached `available`/tokens/cost/
history are kept, never cleared. Benign scoped-data markers
(`session_not_found`, Codex `status_pinned_unavailable`) at either
layer alone never invalidate. Re-validation: parameterized outer-only /
inner-only / mixed-benign regressions over all three OpenCode errors
through the real shaper → selector chain, plus healthy/benign-live
controls and unchanged Codex dual-layer/pinned behavior.

## 18. Slice 5 UI wiring (OpenCode, 2026-09-20)

`provider_poller.py` (new, Qt-free) polls both providers independently
per tick (isolated failures, one generation per poll), folds statuses
through the shared `ProviderSelection`, and publishes one atomic
result: the winner's render dict (Codex raw shape unchanged;
OpenCode via `opencode_display()`), normalized `working_context`
present only when selection is live, plus selection/generation
metadata. The single background loop, Qt signals and 1 s cadence are
reused; no DB/CLI/detection work runs on GUI threads.

Display contract (`opencode_display`, presentation aliases only):
raw input/output/reasoning/cache_read/cache_write travel under own
names, total stays None (rendered N/A, never summed), cost keeps
amount with currency None (value N/A, recorded amount in tooltip),
model IDs verbatim, global reuses all-usage labels, unavailable
reasons map to existing generic catalog keys. Capability downgrades
in UI: no total (N/A), no currency conversion/symbol, no quotas or
reset countdowns (Codex quota widgets blank, never linger), no
context %, stale/unknown status words, OpenCode analytics shows the
Slice 6 raw-category view (Codex analytics never render under OpenCode
nor vice versa). Recorded 0.0 renders as 0, missing as N/A.

Panel/pet behavior: provider identity in the connection line and
tooltips (existing strings/layout untouched for Codex); bubble
follows the selection-bound working session while analytics keeps the
independent pinned scope; Daily hides the live bubble; long names
elide with full tooltips; pet anchor/geometry/pin/topmost/compact
preserved. Settings gains Auto/Codex/OpenCode (persisted
tracking_provider, bilingual, save/cancel/reset semantics kept);
manual save stamps use time and bumps generations, Auto never marks.
Scope changes bump generations; render drops older generations;
late Codex quota under OpenCode renders N/A. `AppModeState` is fed
from selection live/reliable (unknown/stale never force Token Mode);
legacy raw snapshots keep the exact previous feed.

## 19. Slice 5 corrections: isolation, invalidation, pet retire, atomic clearing

Worker ownership (final correction): two dedicated daemon workers, one
per provider, started lazily and never joined. Correction to the prior
note: the previous ThreadPoolExecutor pool was NOT daemon-safe — its
workers are joined at interpreter shutdown even after
shutdown(wait=False), so a permanently blocked read kept the process
alive. close() is idempotent, clears in-flight/jobs without waiting,
wakes idle workers to exit, and never mutates after close; blocked
workers stay daemon-held and the process exits promptly (verified by a
child-process shutdown regression with one provider held forever).
At most one outstanding read per provider (strict single-flight, no
overlap, no unbounded creation); adapter I/O never under the selector
lock and never on the GUI thread; adapters are captured at submit so a
reset can never hand an old request a new adapter. Shared
selector/request state mutates only under the poller RLock.

Whole-tick immutability (correction to the prior per-submit-only
claim): every poll captures one immutable tick (generation, settings
epoch, preference/scope/pinned, history mode, activity inputs) before
any work. Per-provider submits clone that tick (fresh id plus the tick
generation). Completion is accepted only for the current epoch with a
newer id; every publication carries its own tick generation — never the
live counter — so a settings change mid-tick retires the old tick: its
submits carry the old epoch and its result carries the old generation,
which the render guard must reject. Submit contexts come from the tick
captured before the race, never re-read inside _submit_all.
reset_codex() bumps epoch+generation and captures, so old requests stay
on the old adapter and retired results never become current.

Cache provenance (correction to the prior reuse claim): each accepted
read retains provider/scope/pinned/history-mode/epoch/id. Settings
publication reuses cached scoped data only when scope matches (global
ignores pinned) and stripped pinned identity matches; otherwise it
publishes an honest pending/unavailable panel for the requested scope —
never Global-as-Project/Conversation and never one pinned session as
another. Live working context may still ride along only when the
selection is live and its own provenance is valid. Manual stays
immediate (compatible cache or honest pending, never the previous
provider); only changed-to-manual stamps use; Auto/polling/scope
re-saves never stamp. Poll-level exceptions return tick-tagged
fallbacks that also retire via the generation guard.

Pet retires `working_context` on explicit absence (direct assignment,
no retention branch); the tooltip provider comes from the context
itself only (Codex contexts are stamped at publish, so a retained
context can never inherit the new payload's provider); missing rows
clear instead of borrowing scope data. Hysteresis keeps 0.4 s/2.0 s
pose timing with unknown/empty content, never a false Working label.

Every render exit (available and unavailable, both providers) ends
with the provider-aware cost/quota refresh, so quota/reset/context/
cost clear atomically in the same transaction — never on the next
timer tick. Codex-unavailable keeps its quota behavior; OpenCode
stays N/A throughout.

### Fallback correction: no untagged loop emission

Defect: `Panel.read_loop()` had an outer exception branch emitting an
untagged Codex payload (`generation=None`), which bypassed the render
guard and could overwrite a newer OpenCode/Project UI. The accepted
tick/provenance/worker architecture is preserved exactly; only the
fallback boundary moved.

Authoritative rule: no provider-loop error result may reach the Qt
bridge without an immutable generation/settings context.
`ProviderPoller.loop_tick()` owns one production iteration —
Codex reset construction is failure-atomic (the old adapter is kept and
only the Codex request fence advances), then a fresh `poll()` whose body
failures return their own tick generation. A last-resort
`_current_failure()` (fresh generation, selection re-evaluated,
compatible-or-pending publish, preference-bound provider, never a
use-time stamp) covers only the unreachable remainder. `Panel`
grew a testable `read_loop_once()` helper; the loop's outer handler
now emits nothing, so torn-down prefs/bridge during shutdown can never
overwrite newer UI. `render()` keeps legacy generation-less support
for fixtures/old callers, which production emissions can no longer
reach. Obsolete failures keep their older generation (rejected);
current failures render honest provider-specific unavailable states
for the requested scope with Live revoked; first-run failures render
honest tagged pending (manual preference followed, never fabricated);
reset failures stay tied to the captured adapter/fence with the old
adapter retained.

### Current-failure semantics: coherent Live revocation, reset isolation

Corrections to prior fallback claims: a tick-tagged generation alone
did not make poll fallbacks coherent (a failed result could ride with
`live=True`), `_current_failure()` could republish compatible cache as
a live success, and a Codex reset failure was misattributed to a
healthy OpenCode lane. Final rules, all inside `ProviderPoller` (the
sole fallback owner; `widget.py` only gathers inputs and emits tagged
results):

- Provider-specific read failure: failed envelopes flow through the
  normal collect/shape/select path; the failing lane is excluded while
  the healthy lane updates independently.
- Codex-specific reset failure: construction is failure-atomic (the
  old adapter is kept unless replacement completes); only the Codex
  request fence advances while the global epoch is left alone, only a
  queued Codex read may be cancelled, and only the Codex source is
  marked failed — pre-failure Codex completions with the old fence are
  fenced out so a stale Codex success cannot erase the marking, while a
  running OpenCode request stays admissible and its accepted
  result/provenance advances; the same iteration continues with a fresh
  poll so OpenCode updates independently. OpenCode selected and healthy
  stays provider/data/status coherent; Codex selected shows an honest
  tagged Codex unavailable with Live revoked and no OpenCode values.
- Shared orchestration failure (exception after tick capture,
  decide/publication failure, unexpected poll raise): fed through
  `ProviderSelection` as explicit conservative statuses — a manual
  preference fails only its own lane (result stays preference-bound
  unavailable); under Auto the whole tick fails rather than letting one
  lane claim a fresh validation it never performed. Every current
  failure is tagged, `live=False`, `working_context=None`, honest
  unavailable, never stamps use-time; cached history stays stored but
  is never presented as freshly validated.
- Obsolete failure: keeps its older generation untouched (rejected by
  the render guard); current tagged failure: coherent as above.

## 20. Slice 6 provider-local analytics (OpenCode, 2026-09-22)

`opencode_display()` additionally forwards the verified history
aggregates and a sanitized per-session breakdown (scoped session /
project / parent IDs, verbatim model IDs, raw per-category tokens,
recorded cost amount; no directories, paths, message content,
credentials or share links). `AnalyticsWindow.update_data()` branches
on `provider_id`: the Codex path is byte-identical (now with an
explicit `Codex` heading label); the OpenCode path renders one scoped
snapshot — heading `TOKEN ANALYTICS · OpenCode · {scope}`, subtitle
with session/project/count/freshness, metrics rows for the five raw
categories with independent complete/partial/unknown coverage, Total
always N/A, recorded cost without symbol or conversion (recorded 0
shows `0`, missing shows N/A), model/session tables grouped and summed
per raw category (no total column values, fork rows kept as
own-session values), daily buckets with per-day coverage, Today/Last-7/
Last-30 sums from reliable local-calendar buckets only, cached `as_of`
/ `refresh_pending` / skipped-row markers, and an allowlisted raw
metadata tab. Unsupported derived rows (uncached input, non-reasoning
output, hit/new-work/processed ratios) are omitted rather than
fabricated; the note line states the raw-only rule. The 30-second
history refresh floor is untouched (display never scans). `analytics_payload()`
passes both providers' tagged snapshots through, so switches replace
the view atomically and late generations never reach the window.

### Slice 6 correction: history column order, coverage, recorded cost

Authoritative history column order, derived from one category
definition for headers and values alike: Range/Date, Input, Output,
Reasoning, Cache Read, Cache Write, Total (N/A), Coverage — applied to
Lifetime, Today, Last-7, Last-30 and per-day rows, so Cache Write is
never dropped and no value can sit under the wrong header. Every
history cell carries its own coverage: complete renders normally with
a coverage tooltip, partial shows the known subtotal with a visible
partial marker plus tooltip, unknown stays N/A, real zero stays zero
(Full/Compact formatting throughout). Lifetime coverage comes from
scope `token_coverage`; day coverage from `daily_coverage`;
Today/7/30 aggregate independently per category (complete only when
all contributing day evidence is complete, partial on any partial or
known/unknown mix, unknown when nothing reliable exists) with
unattributable skipped rows capping ranges at partial; the summary
Coverage column never replaces the per-cell coverage. Model/session
tables gain a Recorded Cost column (known amounts summed, complete /
partial / unknown cost coverage independent from token coverage,
recorded 0 as `0`, missing as N/A, no symbol/conversion/FX, no daily
  cost allocation); the raw tab additionally exposes sanitized
  `daily_coverage` for audit.

  Skipped-only-day follow-up: range evidence includes days with
  messages > 0 OR skipped > 0, so a skipped-only day inside Last 7/30
  forces those ranges partial (known subtotal, no zero-fill) while its
  own row stays N/A/unknown and untouched windows stay complete;
  unattributable skips remain a backstop cap. Screenshot existence
  checks assert loadable non-null images with matching widget
  dimensions instead of byte-size thresholds.

## 21. Slice 7 acceptance record (2026-09-22, this host)

- Verified sources: Codex local home with 1 state DB (23 desktop
  rows); OpenCode `opencode.db` (~1.2 GB, 54 sessions / 4318 messages /
  19576 parts at acceptance time; live counts drift). Capability matrix
  unchanged from §§4/11/20; heuristic activity policy stays 900 s open
  expiry + 60 s finish grace (documented candidate policy, not proven
  semantics); cost currency stays unknown with no symbol/conversion;
  history keeps the 30 s rescan floor while the per-second activity
  probe reuses its coherent projection unless part writes or session
  revisions occur (fingerprint-gated; same state machine, fresh clock).
- Frozen/source verification: fresh `build.ps1` DLL-safe build
  (`dist/petoken/petoken.exe`, no foreign ICU, VC runtime standardized);
  source smoke, frozen smoke, frozen OpenCode-absent smoke (honest
  `no_provider` empty state) and frozen close/relaunch all exit 0 with
  no QtCore DLL error; real `CodexWisp` settings verified byte-identical
  after scripted live runs (backup/restore).
- Live evidence (metadata only): idle Daily state; live Codex working
  session (Auto → Codex, Token Mode live, quota live); live OpenCode
  working session (manual + Auto → OpenCode live; scope tokens and cost
  match direct SQL exactly; currency None; Total None); absent-store
  failure revokes Live to honest `missing_store` unavailable;
  en/Full/expanded/150%/pinned analytics over live OpenCode data.

## 22. Final-acceptance blocker corrections (2026-09-22, this host)

Two BLOCKED items found at the final gate are corrected here; the
§21 "ready" claim is superseded until Astra re-reviews.

### 22.1 Live OpenCode context reaches the main panel

Root cause: with saved `Auto / Conversation / no pin` preferences, the
scoped read misses (`session_not_found`) while the poller holds
verified live evidence bound to the activity-selected session row; the
panel took the unavailable branch and rendered waiting over live
context. Correction: when the OpenCode lane is selected and live and
the working row is still cached, the poller publishes an explicitly
marked `active_session` presentation built from that one row only
(project/session/model, five raw categories, recorded cost; Total
None, currency None, no cross-provider sums). The identity carries
`scope_type: active_session` plus the requested scope and the
scope-miss status, so live values are never relabeled as scoped
aggregates. The panel labels the connection `OpenCode · Active
session` while the scope button keeps the requested (independent)
scope; analytics keeps its independent genuinely-empty scope view
(scope status, empty tables, allowlisted raw with `presentation`,
`scope_status`, `requested_scope`). Unknown/stale/unavailable activity
or a missing/unbound row keeps the honest unavailable panel; Codex
behavior is untouched (no Codex values linger after switching; late
generations are still rejected).

### 22.2 Commit-generation activity invalidation

Root cause: the storage-byte key (file id + main/wal size + mtime)
is metadata, not a commit signal — a same-size UPDATE with a restored
mtime reproduces a full key collision: the cached probe reports
Working while a fresh provider reports idle until the 60 s backstop.
Correction: reuse requires the commit generation —
`PRAGMA data_version` read on ONE persistent read-only connection —
to equal the generation the rows were projected at, plus unchanged
session rows, a no-wider recall window, and the 60 s backstop as a
supplement only. Validated by probe: a connection that has previously
read data_version observes every committed change on re-read
(same-size/same-rowid UPDATEs, same-max DELETEs, retained-writer WAL
commits without checkpoint, session-table writes), while a fresh
connection's data_version misses them all; uncommitted writes stay
invisible and rollback leaves the version untouched. File identity
separately reopens the detector and forces a rescan on replacement
(on Windows an open handle blocks replacement at OS level, so a
successful replace implies a fresh detector). The projection is
straddle-safe: the generation is read before and after the single
statement and a surrounding commit forces a bounded redo, so cached
rows always belong to the cached generation; detector failure never
reuses (one coherent evaluation, no caching). **Retry exhaustion:
if all three before/after checks still differ, the last candidate is
discarded entirely and the snapshot reports `activity_unstable`
unknown (`valid=False`, `working=False`, no primary, nothing cached,
nothing evaluated) — it can never read as working or idle, and the
next stable poll recovers normally.** Shutdown is terminal:
`OpenCodeProvider.shutdown()` marks shutdown under the detector lock
and closes the handle; the detector is never opened or reopened
afterward (in-flight workers observe None and evaluate at most once
without caching), while reusable `close()` never sets the flag.
`ProviderPoller.close()` is wired to the terminal path and stays
prompt (no worker is joined; late outcomes are discarded as retired).
Steady-state cost on the live ~1.5 GB store: first projection ~124 ms,
steady reuse ~8 ms, generation check ~0.009 ms; a reused provider
agrees with a fresh provider on the live store. Test-sync hardening
found along the way: `read_loop_once`/`poll` submit without draining
and `ProviderPoller.close()` clears the in-flight table, so a close
with unsettled workers orphaned file users past temp cleanup (the
WinError-32 family, previously seen once as a flake on a Codex file);
affected tests now drain before mid-test closes, and adapter swaps
close the old detector first (`ProviderPoller.close()` also releases
the detector handle).

## 23. OpenCode recorded Total and presentation correction (2026-09-22)

### 23.1 Source-backed recorded Total

Upstream ground truth (opencode-ai tags v1.18.31/v1.18.32):
`packages/opencode/src/session/session.ts` (`getUsage`) stores
normalized per-session rollups — stored `input` already excludes
cache read/write, stored `output` already excludes reasoning, and
each session row carries the creating app's `version`
(`InstallationVersion`); `packages/opencode/src/cli/cmd/stats.ts`
(`aggregateSessionStats`) sums exactly the five stored categories
per session (`input + output + reasoning + cache.read +
cache.write`). There is no separate session-rollup total column, and
message-level upstream `tokens.total` is never a session rollup.

Adapter rule (`_recorded_total`, `_token_sums`): for scopes whose
every session row carries a version in
`OPENCODE_RECORDED_TOTAL_VERSIONS` (`1.18.31`, `1.18.32`) and every
category is completely known, Total is the five-category sum (real
zeros stay zero); any missing, malformed, partial, or unverified
row keeps Total N/A with `unknown` coverage — never a subtotal,
never zero-filled, never borrowed. The per-row rule is identical, so
analytics model/session sums over fully-recorded groups equal the
scope sum by construction. Scope `partial` is computed from the five
categories (plus cost) only; the informational Total never marks a
scope partial. Lifetime aggregates scope rollups (recorded Total
applies); day/range rows aggregate upstream message deltas, so their
Total stays N/A by semantics. The main panel, pet bubble/tooltip,
metrics, model/session tables, and Lifetime share the same recorded
value; Codex formulas are untouched and no cross-provider total
exists. Verified live on this host: all 61 sessions are
verified-complete and the adapter global Total equals the direct SQL
sum of the five stored columns exactly.

### 23.2 Unsupported UI hidden, neutral session labels

OpenCode has no verified quota, context, reset, or refresh source,
so `Panel.apply_provider_chrome()` hides the Context meter, the
5-hour/week meters, their divider, and the quota-refresh status in
every OpenCode view (available, unavailable, stale, Full, Compact);
the metrics body ends at Token Analytics while recorded cost and
neutral controls stay. Codex restores the full quota/context UI at
once, including unavailable states; late quota callbacks repaint
hidden text only. The adapter deliberately excludes session titles
(user text), so no verified human-readable title exists: the
prominent main-panel title and the pet tooltip show the localized
Active-session label instead of a raw session ID wherever a single
session would be named. Exact raw IDs stay in selection identity,
working-context binding, scoped analytics tables, and the raw/debug
tab.
