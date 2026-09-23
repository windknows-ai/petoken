# Handoff

## Latest — V1.2.0 docs correction CORRECTED, awaiting focused Astra re-review (2026-09-22)

- README provider-use step fixed; stale PROGRESS passages marked historical (records preserved). Rebuilt + refreshed `dist/Petoken-v1.2.0-Windows-x64.zip`; frozen launch/exit clean. No code/behavior changes. No commit/push/tag/release.
- Current candidate artifacts (verified on disk 2026-09-22): exe 4,019,845 bytes, SHA-256 `3E5D04C405D6EBA84E8BD43100D1E2B1441F827BC79436C289E161FBBE34243F`; `dist/Petoken-v1.2.0-Windows-x64.zip` 64,647,578 bytes, SHA-256 `D6AA69071D1123A65AC4D93BDB3035A9DEF6AC0D583B1D54ED0D3BDC9C6F7270`. The older candidate hashes below (`7990DFC2…A5CA` / `A8BDAA57…3981`) are SUPERSEDED — deliver only the current ZIP above.
- Exact Next Action: focused Astra re-review of docs + new package. Remote publication needs separate explicit user authorization.

## Latest — V1.2.0 manual-QA correction CORRECTED, awaiting Astra re-review (2026-09-22)

- Quota/context chrome hidden in every OpenCode view (+ Codex restore incl. unavailable); neutral Active-session titles/tooltips with raw-ID retention; source-backed recorded Total (1.18.31/1.18.32 + complete; N/A otherwise; upstream totals never used); live SQL-exact reconciliation.
- Validation: FULL 571 green (62.6 s native, no offscreen); compile + diff-check clean; UI inspected (neutral title, live recorded Total, no quota area). Fresh `build.ps1 -Package` (exit 0): exe `7990DFC2…A5CA` (4,019,845 B), `dist/Petoken-v1.2.0-Windows-x64.zip` `A8BDAA57…3981` (64,647,684 B); frozen available (live Active session) + absent (`no_provider` Daily) smokes clean; package privacy-checked. Prior candidate hash retired. No commit/push/tag/release.
- Exact Next Action: Astra re-reviews and decides release. Remote publication needs separate explicit user authorization.

## Latest — V1.2.0 local release candidate PREPARED, awaiting Astra review (2026-09-22)

- `APP_VERSION` 1.2.0; CHANGELOG V1.2.0 entry; README/ROADMAP updated; no behavior changes. FULL 556 green (60.2 s); compile + diff-check clean. Fresh `build.ps1 -Package` (exit 0): exe SHA-256 `9537605B…81D63B8D`, zip SHA-256 `D740A418…F536377AB`; frozen available (live Active session) + absent (`no_provider` Daily) smokes clean; package privacy-checked. No commit/push/tag/release.
- Exact Next Action: Astra reviews the release candidate. Remote publication needs separate explicit user authorization.

## Latest — V1.2 final-gate micro-blockers CORRECTED, awaiting Astra re-review (2026-09-22)

- (1) Exhaustion now reports `activity_unstable` unknown with rows discarded (never working/idle), stable recovery preserved. (2) Terminal `shutdown()` blocks detector reopen after poller close; reusable `close()` kept; close stays prompt. 5 new focused regressions; all prior regressions retained.
- Validation: FULL 556 green (63.3 s native, no offscreen); compile + diff-check clean; no build/visual QA in this pass (frozen binary predates these micro-fixes). APP_VERSION 1.1.0. No commit/push/tag/release.
- Exact Next Action: Astra re-reviews the two micro-blockers and decides release. No further implementation without approval.

## Latest — V1.2 remaining cache blocker CORRECTED, awaiting Astra re-review (2026-09-22)

- Stat-only key retired: reuse now requires persistent-reader `data_version` equality (probe-validated against every committed class incl. the exact same-size UPDATE + restored-mtime repro), file-identity reopen on replacement, straddle-safe projection, 60 s backstop as supplement only. Active-session presentation preserved and re-verified; test sync hardened (drain-before-close, detector release on swaps/poller close).
- Validation: FULL 551 green (61.6 s native, no offscreen); 50 modules compile; diff-check clean; live-store ~124 ms first / ~8 ms steady; source + live Manual/Auto + fresh `build.ps1 -Package` (exit 0) + frozen available/absent smokes, no QtCore error; privacy clean. APP_VERSION 1.1.0. No commit/push/tag/release.
- Exact Next Action: Astra performs final acceptance re-review and decides release. No further implementation without approval.

## Latest — V1.2 final-acceptance blockers CORRECTED, awaiting Astra re-review (2026-09-22)

- Both BLOCKED items fixed: (1) live OpenCode session now presents as explicitly marked `active_session` (single-row coherent, Total/currency N/A, scope/analytics independent, dishonest-waiting removed; stale/unknown/missing stay honest; Codex untouched); (2) activity probe uses storage-byte invalidation (file id + main/wal size+mtime, revision, window, 60 s backstop; ~8 ms steady on the live 1.4 GB store, reused agrees with fresh).
- Validation: FULL 548 green (60 s native, no offscreen; one loaded-run UI timeout flake, green in isolation + rerun); 50 modules compile; diff-check clean; fresh frozen rebuild + available/absent smokes exit 0, no QtCore error; live Manual + Auto verified coherent; privacy clean (temp prefs homes, `.private` ignored). APP_VERSION 1.1.0. No commit/push/tag/release.
- Exact Next Action: Astra performs final acceptance re-review and decides release. No further implementation without approval.

## Latest — V1.2 Slice 7 FINAL ACCEPTANCE READY FOR REVIEW (2026-09-22)

- FULL 519 green; 50 modules compile; diff-check clean; fresh DLL-safe build + source/frozen/absent smokes exit 0; live Codex + OpenCode working verified with SQL-exact reconciliation; UI matrix pairwise-covered (fractional-DPR/physical-drag unavailable, recorded); perf +0.62pp idle / −0.34pp active with flat memory (PASS); privacy clean; settings byte-identical. APP_VERSION 1.1.0. No commit/push/tag/release.
- Exact Next Action: GPT-5.6 performs final acceptance review and decides release. No further implementation without approval.

## Latest OpenCode slice — V1.2 Slice 6 corrections COMPLETE (2026-09-22)

- Both BLOCKED items fixed, no Slice 7: authoritative history column order (headers and rows from one category definition; Cache Write kept; Total N/A), per-cell daily/range/lifetime coverage with skipped-row caps, recorded-cost columns with independent coverage, sanitized daily coverage in raw view. Follow-up: skipped-only days count as range evidence (ranges partial, day N/A/unknown, Today untouched); screenshot gates check loadable images with matching dimensions, not byte sizes. 10 new tests + 4 inspected screenshots; slice6 31 + coupled 178 + FULL 513 green; compile/diff clean. No commit/push/version bump/build.
- Exact Next Action: GPT-5.6 re-reviews the Slice 6 corrections and authorizes Slice 7 or reports corrections. Slice 7 NOT authorized.

## Latest OpenCode slice — V1.2 Slice 6 provider-local analytics COMPLETE (2026-09-22)

- OpenCode raw-category analytics in the existing window (history + sanitized breakdown forwarded; Codex path byte-identical plus heading label; atomic switches; late results never reach the window; 30 s floor intact). 21 new tests + inspected populated/partial screenshots; focused 110 + FULL 503 green; compile/diff clean. No commit/push/version bump/build.
- Exact Next Action: GPT-5.6 reviews Slice 6 and authorizes Slice 7 or reports corrections. Slice 7 NOT authorized.

## Latest OpenCode slice — V1.2 Slice 5 provider-local reset fence COMPLETE (2026-09-22)

- Remaining BLOCKED item fixed, no Slice 6: failed Codex reset advances only a Codex-local request fence (global epoch untouched, OpenCode never cancelled/retired, old adapter kept, Codex-only failed marking, same-iteration OpenCode independence). 2 new held/simultaneous-lane regressions + updated reset bound; test_slice5_final 46 + focused 92 + Qt UI 51 + FULL 482 green; compile/diff clean. No commit/push/version bump/build.
- Exact Next Action: GPT-5.6 re-reviews the provider-local reset fence and authorizes Slice 6 or reports corrections. Slice 6 NOT authorized.

## Latest OpenCode slice — V1.2 Slice 5 current-failure semantics COMPLETE (2026-09-22)

- Both BLOCKED items fixed, no Slice 6: coherent current failures via selection authority (`_coherent_failure`: manual lane-bound, Auto whole-tick, always tagged/live-False/working-None/unavailable/no-stamp) + failure-atomic provider-isolated Codex reset (old adapter kept, Codex-only marking, same-iteration OpenCode independence). 13 new + 2 updated tests; FULL 480 green; compile/diff clean. No commit/push/version bump/build.
- Exact Next Action: GPT-5.6 re-reviews the current-failure semantics correction and authorizes Slice 6 or reports corrections. Slice 6 NOT authorized.

## Latest OpenCode slice — V1.2 Slice 5 fallback correction COMPLETE (2026-09-22)

- Single BLOCKED item fixed, no Slice 6: `ProviderPoller.loop_tick()` centralizes fallback ownership (pre-reset tick on reset failure, own-tick poll-body fallbacks, preference-bound last-resort, never stamping use) + `Panel.read_loop_once()` helper; loop outer handler emits nothing; render legacy path retained but unreachable from production. 16 new tests (poller isolation/honesty/binding/reset/closed + Qt bridge obsolete-both-directions/current/initial/scope/pinned/no-None/static-guard/closing) + FULL 467 green; compile/diff clean. No commit/push/version bump/build.
- Exact Next Action: GPT-5.6 re-reviews the fallback correction and authorizes Slice 6 or reports corrections. Slice 6 NOT authorized.

## Latest OpenCode slice — V1.2 Slice 5 final correction COMPLETE (2026-09-21)

- Both BLOCKED items fixed, no Slice 6: immutable whole-tick capture/publication with provenance-compatible cached publish (honest pending, live working preserved when valid; reset/poll-fallback epoch-safe) + daemon-worker shutdown (pool replaced, close idempotent/no-join/no-mutation, child-held-forever exits promptly). 15 new tests (races both directions + Qt bridge rejection, compat, late, reset, settings paths, fallback, close, subprocess) + FULL 451 green; compile/diff clean. No commit/push/version bump/build.
- Exact Next Action: Astra-6 re-reviews final corrected Slice 5 and authorizes Slice 6 or reports corrections. Slice 6 NOT authorized.

## Latest OpenCode slice — V1.2 Slice 5 corrections COMPLETE (2026-09-20)

- All four BLOCKED items fixed, no Slice 6 work: bounded parallel providers (2-thread pool, strict single-flight, non-blocking collect, freshness expiry); immutable request contexts with retired-context discard, epoch invalidation + cancel, synchronous Settings.save/change_scope publish from cache; pet retires context on explicit absence with self-described provider only; every render exit ends with provider-aware cost/quota refresh. 12 new tests + updated helpers; FULL suite 436 green; phase flake documented (isolated-pass, retained traceback, animation untouched); compile/diff clean. No commit/push/version bump/build.
- Exact Next Action: Astra-6 re-reviews corrected Slice 5 and authorizes Slice 6 or reports corrections. Slice 6 NOT authorized.

## Latest OpenCode slice — V1.2 Slice 5 UI wiring COMPLETE (2026-09-20)

- Poller + display + panel/pet/Settings wiring done per plan (atomic snapshots, N/A boundaries, no leakage, analytics pending marker, tracking combo, generation guards). 30 new tests (poller/display/settings/Qt incl. 6-shot zh/en matrix, inspected); FULL suite 424 green (one timing flake, isolated-pass); compile/diff clean. No commit/push/version bump/build.
- Exact Next Action: Astra-6 reviews Slice 5 (wiring, UI tests, screenshots in `.private/ui-slice5/`, `docs/PROVIDERS.md` §18) and authorizes Slice 6 or reports corrections. Slice 6+ NOT authorized.

## Latest OpenCode slice — V1.2 Slice 4 dual-layer correction COMPLETE (2026-09-20)

- Remaining blocker fixed: OpenCode shaper checks outer reason AND inner payload.status (safe-read, non-dict safe); either-layer failure forces source/working/validity down, cached data kept; benign markers never invalidate. Parameterized regressions (3 errors × outer/inner/mixed) through the real chain + controls; focused suites 152 green; compile/diff clean. No commit/push/version bump/build.
- Exact Next Action: Astra-6 re-reviews the dual-layer correction and authorizes Slice 5 or reports corrections. Slice 5 NOT authorized.

## Latest OpenCode slice — V1.2 Slice 4 validity-boundary addendum COMPLETE (2026-09-20)

- Single BLOCKED item fixed: dual-layer source-failure detection in both shapers (outer reason + payload status); outer-only failure invalidates live beside cached data; pinned scope stays benign (verified). 2 new regressions, focused suites 131 green; compile/diff clean. No commit/push/version bump/build.
- Exact Next Action: Astra-6 re-reviews the validity-boundary fix and authorizes Slice 5 or reports corrections. Slice 5 NOT authorized.

## Latest OpenCode slice — V1.2 Slice 4 final corrections COMPLETE (2026-09-20)

- All three BLOCKED items fixed, no Slice 5 work: fail-closed validity/source boundary (None/missing/failure paths, False defaults, explicit fixtures, e2e); same-message state-machine lifecycle (FIFO, deterministic ties, unknown-safe, coherent snapshot); part-driven recall (stale-row/fresh-open regressed) + attributable recency with idle-edit proofs. 16 new/updated focused tests, FULL suite 387 green; live re-verified; compile/diff clean. No commit/push/version bump/build.
- Exact Next Action: Astra-6 performs final Slice 4 review (`provider_selection.py`, `tests/test_provider_selection.py`, `OpenCodeProvider.activity_snapshot`, `docs/PROVIDERS.md` §13–15) and authorizes Slice 5 or reports corrections. Slice 5 NOT authorized.

## Latest Astra Slice 4 correction re-review — BLOCKED (validity only)

- 59 targeted activity/selection tests pass. Manual override, late reevaluation, message-scoped timestamp handling and explicit heuristic policy corrections pass the bounded review.
- Remaining prior blocker: codex_provider_status(None) / missing codex_activity yield source_available/activity_valid True; explicit source error plus cached success payload can still yield Live. Missing validity also defaults True in the generic selector. Missing evidence must be unknown; source failures must override cached working claims while scope failures remain separate.
- Exact next action: OpenCode follows `D:\Desktop\petoken\V1.2.0\09_Slice_4_Validity_ReReview.md`, adds the focused shaper/selector regressions and stops for re-review. Slice 5 held. Astra changed review docs only; no full tests/builds/implementation/commit/push.

## Latest OpenCode slice — V1.2 Slice 4 corrections COMPLETE (2026-09-20)

- All five BLOCKED items fixed, no Slice 5 work: manual bypass; validity separation (source/scoped/validity + unknown output); late-batch freshness reevaluation + preference + tag matching; message-scoped coherent lifecycle with timestamp validation; explicit policy + attributable recency with metadata-edit proofs. 20 new/updated focused tests, FULL suite 371 green; live re-verified; compile/diff clean. No commit/push/version bump/build.
- Exact Next Action: Astra-6 re-reviews corrected Slice 4 (`provider_selection.py`, `tests/test_provider_selection.py`, `OpenCodeProvider.activity_snapshot`, `docs/PROVIDERS.md` §13–14) and authorizes Slice 5 or reports corrections. Slice 5+ NOT authorized.

## Latest Astra review — Slice 4 BLOCKED for Slice 5

- 39 targeted activity/selection tests pass, but synthetic probes reproduce delayed manual override, rejected late batch retaining expired Live, lost unknown-activity validity, valid working context excluded by missing analytics scope, incorrect cross-message start/finish pairing, future timestamp false work and malformed timestamp TypeError.
- Correct these and separate heuristic policy/verified activity recency; 900s/60s and the prefilter are sample-based policy, not proven provider semantics. Settings/mode diffs stayed scoped and 0.4s/2s hysteresis unchanged. No UI/accounting/pricing expansion observed.
- Exact next action: OpenCode follows `D:\Desktop\petoken\V1.2.0\08_Slice_4_Review_Gate.md`, corrects Slice 4 and stops for re-review. Slice 5 not authorized. Astra modified review documents only; no build/visual QA/implementation/commit/push.

## Latest OpenCode slice — V1.2 Slice 4 activity + selection COMPLETE (2026-09-20)

- Activity snapshot + pure selection logic done (untracked `opencode_provider.py` method, new `provider_selection.py`); expiry 900 s / grace 60 s justified from live step data; preference persisted via existing tolerant settings (no UI); AppModeState timing preserved. 11 activity + 28 selection tests (fake clock), FULL suite 351 green; live snapshot verified; compile/diff clean. No commit/push/version bump/build.
- Exact Next Action: Astra-6 reviews Slice 4 (`provider_selection.py`, `tests/test_provider_selection.py`, `OpenCodeProvider.activity_snapshot`, `docs/PROVIDERS.md` §13, settings hook, `app_mode.py` rename) and authorizes Slice 5 or reports corrections. Slice 5+ NOT authorized. OpenCode must not implement further slices without explicit approval.

## Latest Astra verdict — Slice 3 second corrections PASS

- Both previously blocking issues closed in this bounded review: retained-WAL update/delete/rollback reads are fresh; rapid history changes coalesce behind a 30-second floor with stable cached/as_of and explicit refresh_pending. Nine targeted tests plus independent retained-WAL/fake-clock boundary probe passed; unchanged post-floor data did not rescan.
- Exact next action: OpenCode follows `D:\Desktop\petoken\V1.2.0\07_OpenCode_Slice_4_Handoff.md` for activity/lifecycle + provider selection only, then stops for review. This supersedes earlier BLOCKED/held Slice 4 instructions below. No full suite/build, implementation edit, commit or push by Astra.

## Latest OpenCode slice — V1.2 Slice 3 second corrections COMPLETE (2026-09-20)

- Both re-review BLOCKED items fixed in `opencode_provider.py` (untracked), no Slice 4 work: detector removed (always-project + diff; WAL premise reproduced locally — version stays 2, stat identical, SELECT sees new values); genuine 30 s floor (pending coalescing, frozen as_of, one post-floor rescan; revisions mark pending; no-waste expiry). 42 adapter + 12 provider tests, 99 coupled green; live SQL reconciliation still exact; compile/diff clean. No commit/push/version bump/build.
- Exact Next Action: Astra-6 re-reviews the corrected Slice 3 (`opencode_provider.py`, `tests/test_opencode_provider.py`, `docs/PROVIDERS.md` §10–12) and either passes the Slice 3 gate or reports corrections. Slice 4 (`06_Slice_3_Review_and_Slice_4_Gate.md`) remains NOT authorized. OpenCode must not implement slices 4–7 without explicit approval.

## Latest Astra re-review — Slice 3 corrections: BLOCKED

- 49 focused adapter/provider tests passed independently; original all-unknown/zero and malformed-number/date regressions are covered. No full suite/build or implementation edit.
- Remaining revision blocker reproduced with a persistent WAL writer: after input 100 -> 7, main-file identity and newly opened connection data_version both stay unchanged (2); refresh returns cached 100. data_version values from separate connections cannot serve as a persistent change detector. Correct WAL-aware invalidation and test WAL update/deletion/rollback with the writer kept open.
- Remaining history-bound blocker: three full history scans in two simulated seconds after successive message updates. Fingerprint changes bypass the claimed 30-second minimum interval; refresh also clears the history cache on ordinary changes. Mark dirty/coalesce updates, retain as_of/coverage and serve cached data until a genuine per-selection rescan budget allows refresh. Test continuous writes and session revisions as well as unchanged data.
- Exact next action: OpenCode fixes these two Slice 3 blockers and returns for re-review. Slice 4 remains unauthorized. No commit/push by Astra.

## Latest Astra review — V1.2 Slice 3: BLOCKED for Slice 4

- Independently ran 34 adapter/provider tests: PASS. Synthetic adversarial probes reproduced all-unknown tokens becoming 0 (session and daily), same-size replacement retaining stale input 100 instead of 7, malformed token TypeError and out-of-range timestamp OSError. Two unchanged history reads also perform two full selected-message scans.
- Exact next action: OpenCode corrects Slice 3 and adds focused regressions, then returns for Astra review. Requirements and a held, NOT authorized Slice 4 handoff: `D:\Desktop\petoken\V1.2.0\06_Slice_3_Review_and_Slice_4_Gate.md`. Slice 4 remains activity/lifecycle + selection only after this gate passes.
- Read-only connections, project-id grouping, raw-category separation and recorded amount/currency=None are sound directions. Nullable/incremental claims need the corrections above. No implementation edits, full tests/builds, commit or push by Astra. This verdict supersedes earlier progression instructions.

## Latest OpenCode slice — V1.2 Slice 3 corrections COMPLETE (2026-09-20)

- All four BLOCKED items fixed in `opencode_provider.py` (untracked), no Slice 4 work: unknown-never-zero sums + daily coverage; identity/data_version coherent snapshots (same-size/larger replacement, rollback, deletion); corrupt-cell validation without zero-fill; fingerprinted 30 s-bounded history cache with explicit freshness. 37 adapter + 12 provider tests, 94 coupled green; live SQL reconciliation still exact; compile/diff clean. No commit/push/version bump/build.
- Exact Next Action: Astra-6 re-reviews the corrected Slice 3 (`opencode_provider.py`, `tests/test_opencode_provider.py`, `docs/PROVIDERS.md` §10–11) and either passes the Slice 3 gate or reports corrections. Slice 4 (`06_Slice_3_Review_and_Slice_4_Gate.md`) remains NOT authorized. OpenCode must not implement slices 4–7 without explicit approval.

## Latest Astra review — V1.2 Slice 2

- PASS WITH CONDITIONS for Slice 3. Actual wrapper preserves full Codex payload/raw/nullable fields; the base envelope assumes no token formula. Capabilities are separated for the current Codex-only stage; no accidental OpenCode accounting was introduced.
- Independently ran only tests/test_providers.py: 10/10 PASS. A synthetic probe confirmed the working-context parity test is vacuous (both None; activity invalid/uia_unavailable). OpenCode must add deterministic non-null context/argument parity and unavailable-scope versus working-context coverage before adapter work.
- Exact next action: follow `D:\Desktop\petoken\V1.2.0\05_OpenCode_Slice_3_Handoff.md`. Verify OpenCode accounting/project/fork/revision mappings before aggregation; unknown currency stays unknown; update capability lookup consistently; no UI/selector/activity activation or combined totals.
- Review only: no implementation changes or full tests/builds; no commit/push. This block supersedes earlier Slice-2-awaiting-review instructions.

## Latest Astra review — V1.2 Slice 1

- Verdict: PASS WITH CONDITIONS for Slice 2 only (Codex wrapper). SQLite metadata is sufficient to proceed; this is not approval of OpenCode token semantics, project grouping or automatic activity.
- Corrections: cache_read 501.7M > input 18.3M contradicts the claimed subset; step-finish/tool-calls is not proven session completion. Project identity mapping, fork/revision handling and bounded activity expiry require further evidence. Unknown cost currency stays None/N/A, with no symbol/conversion assumption.
- Exact next action: OpenCode follows `D:\Desktop\petoken\V1.2.0\04_OpenCode_Slice_2_Handoff.md`: correct discovery confidence labels, implement the minimal Codex wrapper and focused parity tests, then STOP for Astra review. No OpenCode adapter/UI/selector in Slice 2.
- Astra reviewed documents and relevant Git diff only; no implementation, tests/builds, database probing, commit or push. This review supersedes earlier PROVEN/no-blocker claims and Slice-1-awaiting-review instructions below.

## V1.1.0 delivered — current state (OpenCode delivery, 2026-09-20)

- Current Released Version: **V1.1.0** (pushed, tagged `v1.1.0` on `3cf7eb5`, full GitHub Release "Petoken v1.1.0", ZIP published; release SHAs/URL in PROGRESS.md delivery record).
- Current Target Version: **V1.2.0 — PLANNING ONLY**. Implementation Status: **NOT STARTED**.
- Current Implementer: OpenCode. Review / Planning Agent: Codex / Astra-6.
- Exact Next Action: Astra-6 reviews the Slice 3 adapter (see top block) and authorizes Slice 4 or reports corrections. OpenCode must not implement slices 4–7 without explicit approval. No commit/push per handoff.

## Current planning handoff — 2026-09-20 (supersedes older status below)

- Baseline: completed V1.1 per the user's current instruction; implementation checkpoint `fcd9288`; current HEAD `3cf7eb5` after concurrent documentation/workflow commits. ROADMAP records user acceptance/release. Older unpublished/PARTIAL statements below are historical, not the current planning gate; remote publication was not rechecked.
- Current implementer: OpenCode. Planner/reviewer: Codex / Astra-6. V1.2 plan approved; OpenCode is assigned Slice 1 discovery/documentation only. Astra does not implement.
- V1.2 plan APPROVED: focused Codex + OpenCode support, seven slices, no new art or unrelated integrations. Specifications: `D:\Desktop\petoken\V1.2.0\00_Scope_and_Behavior.md`, `01_Provider_Architecture.md`, `02_Implementation_and_Acceptance.md`; findings in `99_Implementation_Notes.md`. Original prompt preserved.
- Exact next action: OpenCode follows `D:\Desktop\petoken\V1.2.0\03_OpenCode_Slice_1_Handoff.md`, verifies metadata/activity/recency, documents evidence and stops for Astra review. Shared-file handoff prepared; no OpenCode session was launched or messaged. No adapter implementation, commit, version change or publication.
- This session changed planning/state documents only. Existing AGENTS/CHANGELOG/DESIGN/release-note changes preserved; ROADMAP planning updated in place. No tests/builds/visual QA run, as requested. Existing historical reports below remain for recovery, not renewed task authorization.

## Latest authorized correction - COMPLETE

- Astra temporarily implemented this slice; OpenCode stayed paused. Correction acceptance PASS: enlarged aspect-preserving 256-square pet, one real character as spatial anchor, right-first adjacent satellite, R1-R9 and scope-aware verifier fixed. Default role returns to Astra review/planning after this slice.
- Evidence: 210 tests; 37 compiled Python files; source/frozen smoke with real usage/quota; PyInstaller; five effective DPRs; 75 zero-drift cycles; two native monitor/focus checks. Details and remaining version-level gaps: docs/REVIEW_V1.1.0_ASTRA.md addendum.
- One authorized correction checkpoint: `fix: close V1.1 companion acceptance gaps`, parent `64f7fcb`. AGENTS.md and ROADMAP.md pre-existing changes excluded. No push/publication or V1.2.

## Historical baseline review (2026-09-20)

- COMPLETED: independent review of HEAD `64f7fcb`; verdict PARTIAL / not release-ready. Implementation code was not modified. Initial working-tree change was `AGENTS.md` only and is preserved.
- Fresh checks: 196 tests pass; 36 Python files compile; isolated source smoke exits 0 with live usage/quota and no keyboard hook error. Qt probes reproduce window visibility, pinned startup, stage animation/state, and scoped-status defects; final findings are recorded in `docs/REVIEW_V1.1.0_ASTRA.md`.
- `tools/verify_local.py` failed at `assert checked>=3` after the earlier numeric reconciliation assertions passed. Confirmed default Conversation scope indexes one eligible session. An independent explicit Global check reconciled 30 eligible / 44 indexed sessions and both model/session sums; the original command still FAILS and needs a scope-aware fix.

Concise current execution/review snapshot. This is NOT a substitute for `PROGRESS.md`, `CHANGELOG.md`, `AGENTS.md`, or the external version specifications.

## Current Implementer

`OpenCode`

OpenCode is the primary implementation agent. It implements only explicitly approved slices, validates them, updates project-state documentation, and stops for review.

## Review / Planning Agent

`Codex / Astra-6`

Astra-6 is the primary reviewer, technical lead, acceptance reviewer, and roadmap planner. Its default role is read/review/plan rather than implementation.

## Current Released Version

`V1.0.0` (published verified baseline of `petoken`, formerly Codex Wisp)

## Current Target Version

`V1.1.0` (parent `64f7fcb` plus the correction checkpoint containing this entry; correction slice PASS, version acceptance PARTIAL; not pushed or published)

## Current Approved Slice

`Final V1.1 polish P1–P2 (OpenCode)`

P1 free edge/corner resize of the Expanded panel (420–650×400–800, persisted, pet never moves, compact stays fixed); P2 Settings About-the-Data section in the exact approved zh/en copy. No Expanded/Compact redesign, no artwork/analytics/version change, no V1.2.0.

## Implementation Status

`COMPLETED — AWAITING USER ACCEPTANCE`

The P1–P2 slice is implemented, verified (258 tests, edge-drag probes, resize QA at two DPRs, isolated source smoke), and committed locally as one scoped checkpoint. No push, tag, GitHub Release or binary publication. V1.2.0 not started.

## Last Review Verdict

`PASS for the authorized correction slice; PARTIAL for full V1.1 release readiness`

See the latest addendum in `docs/REVIEW_V1.1.0_ASTRA.md`; preserve the original review as history.

## Required Corrections

`R1-R9 and verification-tool corrections FIXED. Remaining separate version gaps: scope selection, multi-active indication, hitboxes, system reduced motion, full performance baseline and distribution acceptance.`

The report gives precise reproduction evidence and regression-test requirements. Subsequent acceptance closure must address remaining scope/multi-task/accessibility/performance evidence gaps.

## Next Planned Slice

`Not started: remaining V1.1 acceptance closure, subject to the next explicit task.`

Astra-6 remains the default reviewer/planner. ROADMAP.md is planning context only, not implementation authorization.

## Exact Next Action

- OpenCode: STOP after the A1–A4 checkpoint; no further implementation without explicit authorization.
- User: manual acceptance of A1–A4 against the fresh `dist/petoken/petoken.exe` build (relaunch it — the stale process was stopped for the rebuild).
- User: explicitly authorizes any push, tag, GitHub Release, binary publication, or V1.2.0 start.

## Last Completed Step

- Origin updated to `https://github.com/windknows-ai/petoken.git`; fetched tag `v1.0.0`; fast-forwarded local `main` to `da23495` (includes commits `47f841f` Rename project and `da2349` README format fix).
- AGENTS.md: fixed External Prompt Library path to `D:\Desktop\petoken`; consolidated to a single Multi-Agent Continuity section.
- Created `HANDOFF.md`, `CHANGELOG.md`, `ROADMAP.md`.
- Rebranded current-facing docs/code to `petoken`; rewrote README as a concise front page.
- Preserved `CodexWisp` persisted settings directory and other compatibility-sensitive identifiers.
- Final verification passed: `main` at `da23495` synced to `windknows-ai/petoken`, tag `v1.0.0` present, no `C:\Users\fengz\Desktop` paths remain in docs, `python -m unittest discover -s tests` = 17 tests OK.
- Spec context refreshed: `D:\Desktop\petoken\V1.1.0` finalized to six non-`_UPDATED` files (00, 01, 02, 03, 04, 99); `04_Visual_Reference_Specification.md` resolves the visual-reference requirement. Documentation-only corrections applied; no code changed.
- Cleanup committed locally as `9b7300b`; it has not been pushed.
- OpenCode performed V1.1.0 Implementation Order Step 1 architecture inspection only. No V1.1.0 implementation code existed before Codex began development.
- Codex added one `APP_VERSION` source, settings schema version 1 with compatible default merging and atomic persistence, persistent language preference, and a centralized `zh_CN` / `en` string catalog.
- Verification passed: 22 tests, `py_compile`, isolated live smoke, and `git diff --check`. The existing visual baseline was preserved.
- Codex added centralized `AppModeState`, explicit Codex lifecycle detection across unarchived desktop sessions, working-state priority, and Daily-mode bubble hiding. UIA task presence plus a running lifecycle event is required; a visible idle Codex window is insufficient.
- Daily / Token verification passed: 30 tests, `py_compile`, live Token smoke, logical/visual Daily bubble checks, and detector cold/warm timing. No visual redesign was performed.
- Checkpoint commit `859b654fca36fc792b2846bb1acb27ffcdd50ba7` was created locally with a clean post-commit working tree; no push and no version change.
- Token Mode now prefers a foreground UIA-matched working thread, otherwise the most recently active working thread. The chosen session supplies one structured `working_context` containing project identity and that session's fork-deduplicated Token data.
- Project identity priority is explicit project metadata, Git origin repository name, cwd basename, then unavailable. No full paths or inferred window-title project names are exposed.
- Working-context recovery verification passed: 39 tests, `py_compile`, isolated live smoke, and visual bubble inspection. With two working sessions detected, the live bubble selected the foreground thread and showed that thread's matching title, `Web Project`, and 31.40M session Tokens.
- Working Context checkpoint `f061ccf11362425fff9da379f45a4d36469b5f4c` was committed locally without pushing or changing the application version; its post-commit working tree was clean.
- Codex implemented structured Global / Project / Conversation identities and coherent scope results. Global reads all eligible local rollout rows, Project groups only a shared stable project identity, and Conversation selects exactly one thread. All use the existing nullable/fork-deduplicated accounting.
- The minimal Settings and quick-menu selector now exposes all three scopes. Legacy `task` settings remain Conversation-compatible. Analytics scope changes do not alter the active Working Context or pet bubble.
- Scope verification passed: 52 tests, `py_compile`, isolated Global smoke, and panel/pet/analytics screenshot inspection. The smoke aggregated 1,698 unique events / 186,031,972 locally recorded Tokens while the pet independently displayed the active `Web Project` context.
- Three-scope checkpoint `f6da971855bfbf53f9b1e919c14029800819e649` was committed locally with a clean post-commit tree; it was not pushed and did not change the application version.
- Codex added one `token_format.py` source for Full and Compact Token presentation. Compact uses two decimals with K/M/B/T boundary promotion; invalid/missing inputs stay unavailable. The persistent preference defaults and invalid values to Compact.
- Main panel, all three scopes, Working Context bubble/tooltips, and Analytics metric/model/conversation/history tables now use that formatter. Analytics token values and headers show `Tokens`, ratios show `%`, and event coverage shows `Records`.
- Formatting verification passed: 63 tests, `py_compile`, and separate Full/Compact Global smokes. Both panel, pet and analytics screenshots were inspected; Compact showed `191.41M Tokens`, Full showed `191,626,989 Tokens`.
- Formatting checkpoint `896ed094900d76bcc7c9e0ff0cb60200a363b2ec` was committed locally without pushing or changing the application version; its post-commit working tree was clean.
- Codex began the zh_CN / en visible-language pass on top of `896ed09` (catalog expansion, settings/panel/Settings/Analytics/pet localization, status/note keys, 7 tests) and stopped at its usage limit before final verification/reporting; PROGRESS/99 notes were not yet updated.
- OpenCode recovered the exact tree, confirmed `896ed09` clean and all localization work uncommitted, ran the targeted tests green before editing, and finished surgically: centralized pet Analytics menu text, Analytics token column headers (`header_*_tokens`), Settings FX label (`fx_rate_label`), and Qt-mnemonic escaping (`Date && History`). Added 4 tests; updated 1 Codex tab-text expectation for the escaping.
- Localization verification passed: 74 tests, `py_compile`, `git diff --check`, isolated zh_CN and en smokes (both exit 0, live quota, no keyboard error), and panel/pet/Settings/Analytics screenshots inspected in both languages with no clipping.
- Localization checkpoint `27ceb81` committed locally (12 files: catalog/UI/tests/PROGRESS/HANDOFF work; message "feat: add bilingual UI localization"). `AGENTS.md` diff is +755/-0 append-only (Codex `## Codex Instructions (auto-synced)` bootstrap section after line 126, verified via `git diff --numstat`/`git diff`); unrelated to localization, tool-generated, so excluded from the commit and left unmodified in the working tree (not reverted).
- Step 8 cost/currency implemented and verified by OpenCode, uncommitted: new `pricing.py` (moved `MODEL_PRICES`/`estimate_usd` from `usage.py` with identical math, plus USD-canonical currency layer); `usage.py` keeps `PRICES`/`estimate_usd` aliases and dropped the custom-price override plumbing; `desktop.fetch_fx` returns `{date, source, rates:{CAD,EUR,CNY}}` from verified BoC series (USD legs derived); `app_config` persists `currency` (default CAD, invalid falls back); Settings exposes only a Currency combo (manual FX + per-model price controls removed; legacy keys preserved untouched); cost display converts once (`≈ CA$…` etc.) with honest USD fallback when a rate is missing.
- Cost verification passed: 90 tests, `py_compile`, `git diff --check`, and four isolated smokes (zh+CAD, en+USD/EUR/CNY) with live BoC rates, no scope/cost mismatch, and no manual pricing controls in Settings.
- Cost/currency checkpoint `918f8cf` committed locally (11 files: pricing/currency/UI/tests/PROGRESS/HANDOFF work; message "feat: simplify estimated cost and add currency selection"). `AGENTS.md` excluded again, untouched.
- Step 9 implemented by OpenCode, uncommitted: new `pet_geometry.py` (V1.0 baseline constants, `CHARACTER_SCALE = 0.5`, one 107×145 sprite box at (67,80), feet anchor (121,225), unchanged 240×70 bubble, pure clamp/DPR helpers); `pet.py` paints from full-resolution sources into the logical box with smooth filtering, scaled motion amplitudes, and geometry-driven clamp/placement; `tools/render_states.py` renders all six states plus a forced Token Mode shot.
- Character verification passed: 102 tests, `py_compile`, `git diff --check`, 100%/200% state renders inspected (sharp, anchored, bubble attached, Daily bubble hidden), live zh_CN smoke exits 0. Idle asset hash unchanged; no artwork touched.
- Geometry checkpoint `f3cf834` committed locally (7 files: geometry/render/tests/PROGRESS/HANDOFF work; message "feat: add compact DPI-aware pet geometry"). `AGENTS.md` excluded again, untouched.
- Step 10 implemented by OpenCode, uncommitted: new `pet_assets.py` (frozen `AssetEntry` registry for idle/typing/codex_working/microphone/music/guitar, `ALIASES` for working→codex_working and usage→idle, `PREVIEW_STATES`, `entry_for`/`sprite_for` with primary→fallback→idle chain, `validate_path`/`load_path`, `load_sprites` keyed by activity name, `frames` stub for future animation); `pet.py` builds sprites from the registry (no filenames left in pet code, null-safe paint); `tools/render_states.py` enumerates `STATES = PREVIEW_STATES`; `assets/v1_1/README.md` documents the drop-in convention.
- Asset verification passed: 113 tests, `py_compile`, `git diff --check`, 100%/200% renders for all six states plus Token Mode (all resolve via V1.0 fallbacks), live zh_CN smoke exits 0, idle SHA unchanged.
- Registry checkpoint `a687cbc` committed locally (7 files: registry/render/README/tests/PROGRESS/HANDOFF work; message "feat: add V1.1 pet asset registry"). `AGENTS.md` excluded again, untouched.
- Step 11 implemented by OpenCode, uncommitted: `ActivityState` gains timestamp-only `tap_phase` (`TAP_MIN_INTERVAL = 0.12`, `TYPING_WINDOW = 1.5`); typing entry carries `frames = (typing_1, typing_2)` with `frame_for` + cache; pet renders frames when present else a subtle feet-anchored fallback tilt (±1.2°, ±2px); render tool emits neutral/tap0/tap1 shots via synthetic timestamp pulses.
- Typing verification passed: 122 tests, `py_compile`, `git diff --check`, 100%/200% tap renders inspected, live F24 typing smoke exits 0 with visible taps and `keyboard_hook_error: null`.
- Typing checkpoint `13f8892` committed locally (9 files: interaction/frames/tests/tool/docs work; message "feat: add reactive typing interaction"). `AGENTS.md` excluded again, untouched.
- Step 12 implemented by OpenCode, uncommitted: new `theme.py` (one palette/radii/font source); compact Token card 240×58 (project·status + ctx right on line one, live Tokens on line two; was 240×70 three-row); window 242×216; grouped token/quota cards; smaller hierarchy type (brand 14, number 28, cost 22); corner-drag `⋰` resizing (300–480 × 380–800, compact fixed 250, debounced `panel_size` persist); Analytics palette-only swap with identical values.
- Redesign verification passed: 136 tests, `py_compile`, `git diff --check`, full matrix inspected, no data-semantics change. One scratch render script bypassed isolation and persisted real user settings once (valid app-managed state; harnesses must stay isolated).
- Redesign checkpoint `74cddea` committed locally (11 files: theme/card/panel/tests/docs work; message "feat: redesign compact token interface"). `AGENTS.md` excluded again, untouched.
- Step 13 implemented by OpenCode, uncommitted: `body.addStretch(1)` pins content top in tall windows; `PANEL_MIN/MAX/DEFAULT` + `valid_panel_size()` centralize bounds and make malformed `panel_size` uncrashable (clamp or default); grip/init/compact paths share the helper; 7 responsive tests (bounds, restore/restart, invalid recovery, compact preservation, grip clamp, 48-combo min-width stress).
- Responsive verification passed: 143 tests, `py_compile`, `git diff --check`, matrix above, restart persistence by test, no semantics change.
- Responsive checkpoint `5af3a98` committed locally (4 files: layout/persistence/tests/docs work; message "fix: harden responsive panel layout"). `AGENTS.md` excluded again, untouched.
- Step 14 implemented by OpenCode, uncommitted: `summarize_music_text` + `ActivityMonitor.read_music_text` (SMTC `subtitle` field only, recomputed each 0.5 s poll, failure → None); pet `music_subtitle()` gate (Music-visible only, verbatim, memory-only) + one-line pill (elided ≤208 px, bubble styling, no box when absent); render tool `pet-music-text.png` with synthetic labeled content.
- Music verification passed: 155 tests, `py_compile`, `git diff --check`, 100%/200% pill inspected, no-media smoke exits 0. Real `subtitle` field confirmed in the installed projection; no app populates it here (0 sessions), so live text is architecture-verified, not end-to-end observed.
- Music checkpoint `2d3394f` committed locally (7 files: capability/tests/tool/docs work; message "feat: add music subtitle capability"). `AGENTS.md` excluded again, untouched.
- Acceptance performed by OpenCode, uncommitted: full §26 matrix (see 99 notes), Reset to Defaults added (spec 01 §25 gap), 11 edge/combination tests, perf probe, privacy grep, DESIGN/README consistency touch-ups, PyInstaller build + frozen smoke, final screenshot set. Verdict NOT READY (artwork BLOCKED); APP_VERSION stays `1.0.0`.
- V1.1 polish slice implemented and verified by OpenCode, committed locally as one checkpoint: panel bounds widened to 360×400–560×760 (default 420×600) with airier margins/spacing; theme lifted to a softer companion palette with rounder radii (surface 26, card 20, badge 12, button 10); surface gradient changed to a smooth vertical two-stop (less banding); pet painter gains TextAntialiasing and a theme-derived bubble fill; the ◇/◆ cost-row button now pins the panel open (`panel_pinned`, suppresses cursor-leave auto-hide, restores visible at startup, manual close still works); Always on Top is a persisted user setting (Settings checkbox + pet context-menu toggle, default on, one-time legacy `topmost` migration) applied to pet and panel via `apply_topmost`; new `always_on_top`/`panel_pin`/`panel_unpin` strings in zh_CN/en (`pin_toggle` retired). 14 new tests in `tests/test_panel_persist.py`; legitimate expectation updates in responsive/redesign/UI tests. 184 tests pass; isolated live smoke exits 0 at the new default size; 100%/200% screenshot matrix (`.private/polish-slice/`) inspected.
- V1.1 companion-redesign slice implemented and verified by OpenCode, committed locally as one checkpoint: three mock candidates prototyped (`.private/companion-redesign-concepts/`, A character-left / B overlap / C bottom-anchor); B chosen. `CHARACTER_SCALE` 0.5→0.68 (pet 242×268); new `CompanionStage` paints the live pet state in the panel over a transparent 230 px gutter bleeding ~16 px past the surface edge (a radial glow backdrop was tried and removed after screenshots showed banding rings); landscape bounds 480×420–600×640, default 560×500; token/quota sections card-free with `io_line` + Working/Idle status line; `showEvent`/`hideEvent` coupling keeps exactly one character visible (was-visible tracking, timer start/stop); panel opens centered on the pet for flicker-free hover; compact hides stage+scroll. 12 new tests in `tests/test_companion.py`; legitimate updates across geometry/asset/UI/redesign/responsive/acceptance/persist tests. 196 tests pass; isolated live smoke exits 0 at 560×500; 100%/200% matrix (`.private/companion-qa/`) inspected. Known tradeoff: quota strips sit below the scroll fold at default size.
- Final V1.1 pet-scale requirement implemented and verified by OpenCode, committed locally as one scoped checkpoint: `pet_scale_percent` (100% default = Astra-approved 256-square size, 50–150% range, invalid → 100%); proportional scaling of window/sprite/anchor/bubble/fonts/amplitudes from unchanged base constants; single-DPR-resample rendering preserved; anchor-preserving resize with panel re-dock; Settings slider + live % + cancel-revert + Reset 100%. 22 new tests in `tests/test_pet_scale.py`. 232 tests pass; isolated smoke exits 0; 50/75/100/150% QA inspected at two DPRs. Astra's geometry/anchoring/rendering work preserved untouched.
- Final V1.1 manual-acceptance corrections A1–A4 implemented and verified by OpenCode, committed locally as one scoped checkpoint: A1 stale-binary diagnosis with real-Settings + fresh-frozen proof; A2 live QQ Music SMTC verdict (subtitle empty → honest no-pill PASS, pipeline probe music=False/None); A3 compact-only redesign (COMPACT_HEIGHT 316, auto-fit twins, order-stable lending, expanded untouched); A4 real-click restore (last-size, cycles, restart) + toggle auto-hide grace. 13 new tests in `tests/test_compact_acceptance.py`; ≤280 assertions legitimately updated. 245 tests pass; source + frozen smokes exit 0; fresh PyInstaller build verified.

## Current Work / Partial Work

No implementation slice is currently authorized. The V1.1 companion-redesign slice is complete locally and awaits Astra-6 review/planning and/or explicit user publication authorization.

OpenCode must not start V1.2.0 or any new feature slice until Astra-6/user approval.

## Important Decisions

- Canonical project name: `petoken`. Canonical repository: `windknows-ai/petoken`.
- Preserve persisted settings directory `.../LocalAppData/CodexWisp` and module/class/internal identifiers; rename only user-facing branding.
- Preserve historical `Codex Wisp` references in V1.0.0 release documentation and commits.
- GitHub's currently published release remains V1.0.0 until the user authorizes publication. Local V1.1.0 implementation is complete and `APP_VERSION` is `1.1.0`.

## Current Git State

- Branch: `main`, HEAD is the local companion-redesign checkpoint on top of the polish slice; nothing was pushed.
- The redesign checkpoint includes: live chibi stage + landscape panel + show/hide coupling, enlarged pet, state-dot compact card, 12 new tests, legitimate geometry/bound/widget expectation updates, and PROGRESS/HANDOFF updates. `AGENTS.md` remains worktree-modified (excluded from every checkpoint).
- Verification: 196 tests pass, `py_compile` pass, `git diff --check` pass, isolated live smoke exit 0, 100%/200% screenshot matrix inspected.
- External `D:\Desktop\petoken\V1.1.0\99_Implementation_Notes.md` has a redesign-slice entry outside this Git repository.

## Known Issues / Blockers

- Visual references resolved (no blocker): `D:\Desktop\petoken\V1.1.0\04_Visual_Reference_Specification.md` provides the authoritative text visual specification for Reference Images 1, 2, and 3. Do not claim the reference images are missing.
- GitHub release is titled "Petoken v1.0.0" and flagged Pre-release (delivery record documented a full release); confirm whether this is intended.
- Repository visibility changed from private (per V1.0.0 PROGRESS) to public; confirm intended.
- Working-state recovery is bounded: an unclean session with no `task_complete` can remain active for at most five minutes while a task window exists; a genuinely running tool that writes no rollout events for more than five minutes can temporarily fall back to Daily until the next event.
- The prior project/Token mismatch is resolved for the pet bubble. The expanded dashboard now has the completed three-scope system, independent from active Working Context.
- Some local sessions have neither project metadata nor Git origin nor cwd; their project is shown as unavailable instead of being invented.

## Exact Next Step

1. Codex / Astra-6 reviews the completed V1.1.0 repository state when available and determines the next approved action.
2. If the user wants V1.1.0 published, publication still requires explicit user authorization for push + GitHub Release + binaries.
3. OpenCode must not start V1.2.0 or another slice on its own.
4. Any future implementation task must be an explicitly approved slice.

## Last Implementation Agent

OpenCode.

## Review / Planning Agent

Codex / Astra-6.
