# Project Progress

Status: IN PROGRESS — V1.0.0 delivered and verified. The V1.1.0 architecture, foundation, Daily / Token mode, coherent Working Context, and Global / Project / Conversation scope slices are complete and verified; work is stopped before Token number formatting and units.

## Current Objective
Continue V1.1.0 from implementation-order step 6. Analytics now has one deduplicated Global / Project / Conversation scope system while the compact Token bubble remains bound to the independent active Working Context.

## Completed
- Isolated repository cloned; personal website untouched. GitHub upload permission verified; current repo visibility private.
- Live Qt panel with original ice-spirit icon, task-following via Windows accessibility document title, manual pinning, task/project scope, total/input/output, context, 5h/weekly quotas, CAD estimate, tray, compact mode, drag/keyboard movement.
- Hidden official Codex app-server quota RPC works every second. No model calls or widget credential reads.
- Incremental JSONL usage reading and read-only SQLite metadata work. Five initial unit tests pass; live window screenshot verified.
- Persistent AGENTS.md and this recovery file added following the user attachment.
- Nullable raw/derived analytics, model/session/calendar-day history, raw field detail and reset countdowns implemented. Eleven unit tests pass. Live expanded smoke succeeds with quota data and correct active task.
- Approved transparent Skirk-style character integrated in `pet.py`, original asset `assets/skirk-pet.png` MUST NOT be changed. User approved existing idle UI and only requested temporary activity variations.
- Three transparent activity sprite edits generated from the approved original; the original idle asset is byte-for-byte unchanged.
- `activity.py` detects only keyboard timing, microphone capture-session activity, and Windows media playback state. Stable debounce and the approved panel > microphone > music > typing > idle priority are implemented.
- Hover/click usage reveal and automatic leave-to-pet behavior are implemented without activating the widget window or stealing keyboard focus.
- Fork aggregation now removes inherited ancestor snapshots while retaining each child session's unique work. Local raw-record reconciliation succeeds.
- Final README, token-accounting reference, artwork notice, MIT code license, third-party notices and reproducible PyInstaller build script added.
- Visual QA found and fixed a white Qt scroll viewport that made the main panel hard to read.
- Frozen startup failure diagnosed to Codex runtime PATH contaminating PyInstaller dependency discovery with a versioned ICU 78 DLL. The build now filters that path and standardizes the compatible PySide VC runtime.
- Source committed and pushed to the existing private `Wind-Fzx/codex-widget` repository. GitHub Release `v1.0.0` published with the verified Windows x64 zip.
- `D:\Desktop\Codex Wisp.lnk` created for the corrected frozen executable; the final app is running and responding.
- Lifecycle continuation: repository transferred to `windknows-ai/petoken`. Local `origin` updated to `https://github.com/windknows-ai/petoken.git`; tag `v1.0.0` fetched; remote commits `47f841f` (Rename project) and `da2349` (README format) merged via fast-forward to `da23495`. Existing uncommitted AGENTS.md work preserved.
- AGENTS.md: External Prompt Library path corrected to `D:\Desktop\petoken`; Multi-Agent Continuity section added.
- Created `HANDOFF.md`, `CHANGELOG.md`, `ROADMAP.md` per the active versioning rules.
- Branding migrated to `petoken` in current-facing docs and UI (README, DESIGN, docs headings, window/tray titles, build output names); persisted `CodexWisp` settings directory and V1.0.0 historical names intentionally preserved.
- README shortened to a concise front page; detailed V1.0.0 behavior preserved in `docs/RELEASE_NOTES_v1.0.0.md`.
- Cleanup committed locally as `9b7300b` ("docs: prepare petoken for V1.1.0 multi-agent development"); not pushed. Spec folder finalized to six non-`_UPDATED` files; stale image-blocker references removed from PROGRESS/HANDOFF/ROADMAP.
- V1.1.0 Implementation Order Step 1 (architecture inspection) completed; report delivered in chat, awaiting implementation approval. No V1.1.0 implementation code written.
- V1.1.0 foundation slice implemented: `APP_VERSION = "1.0.0"` is shared by Qt and the Codex app-server client; the actual release version remains unchanged.
- Settings schema version 1 adds safe defaults for `settings_schema_version` and `language`, upgrades missing/older schema metadata, preserves future schema numbers and all unknown user keys, keeps the `LocalAppData/CodexWisp` directory, and retains atomic temp-file replacement.
- Added the centralized `zh_CN` / `en` string catalog without performing the full visible-language conversion or intentional visual changes.
- Added centralized `AppModeState` with `daily` and `token` modes. Entry requires 0.4 seconds of stable activity; exit requires 2 seconds of stable inactivity/failure to avoid flicker.
- Codex working detection now combines a fresh successful UIA scan containing a real task window with explicit `task_started` / `task_complete` lifecycle events from any unarchived desktop/vscode rollout. Old formats without lifecycle markers may use a 15-second recent-token fallback. Initial reads inspect at most the last 2 MB and subsequent reads are incremental/cached.
- Activity priority is now usage panel > Codex working > microphone > music > typing > idle. Codex working and typing remain distinct states; the existing idle asset is used as the temporary working visual until the later animation slice.
- The existing token bubble is painted only in Token Mode. Daily Mode keeps the approved character and hides the bubble without changing its Token-mode geometry.
- Local checkpoint `859b654fca36fc792b2846bb1acb27ffcdd50ba7` records the approved foundation and Daily / Token slices; the working tree was clean immediately after the commit and it was not pushed.
- Token Mode now selects one coherent working context: prefer the fresh UIA title when it matches a working thread; otherwise select the working thread with the newest rollout activity. A switch between two still-working threads must remain stable for 0.4 seconds; if the selected thread completes, another verified working thread takes over immediately.
- Project names come from structured metadata in this order: explicit local project name, Git origin repository name, cwd basename, then unavailable. Full paths and arbitrary window text are never used as project names.
- The bubble's title, project, model, context percentage and session-total Token values now come from the same selected `SessionUsage`. Fork-inherited events remain excluded and nullable fields remain nullable. This Working Context stays independent from the expanded panel's newer three-scope analytics selection.
- Token bubble text now shows project plus session Tokens and an explicit Working status while preserving the existing bubble geometry and styling.
- Approved Working Context checkpoint `f061ccf11362425fff9da379f45a4d36469b5f4c` was committed locally without pushing or changing `APP_VERSION`.
- Token analytics now normalizes legacy `task` scope to Conversation and exposes exactly Global, Project, and Conversation. The selected scope and all of its identity/statistics travel in one read result; changing analytics scope never changes the active Working Context.
- Global aggregates normalized records from every locally indexed row with a rollout path. It uses one most-complete file per stable session ID, then `unique_records()` to remove duplicate and inherited fork events before aggregating. It is explicitly labeled as locally recorded, not cloud/account lifetime.
- Project resolves the selected/default working conversation through the shared project resolver, then aggregates only rows with the same stable explicit project ID, Git-origin identity, or normalized cwd identity. Equal display names do not merge distinct projects.
- Conversation uses one exact selected thread ID and never falls back to Project or Global. Missing selections and unavailable project identities return an explicit unavailable state without unrelated Tokens.
- Scope history, model and session breakdowns now use the same selected scope. Nullable accounting, cache/reasoning subset rules, calendar-day ranges, and fork exclusion remain unchanged.

## Files Modified
Historical V1.0.0 scope: AGENTS.md, PROGRESS.md, DESIGN.md, docs/implementation-plan.md, usage.py, analytics.py, analytics_view.py, desktop.py, widget.py, pet.py, activity.py, assets/, tests/, tools/, requirements*.txt, .gitignore.
Lifecycle continuation: AGENTS.md, PROGRESS.md, README.md, DESIGN.md, CHANGELOG.md (new), ROADMAP.md (new), HANDOFF.md (new), docs/implementation-plan.md, docs/TOKEN_ACCOUNTING.md, docs/RELEASE_NOTES_v1.0.0.md, THIRD_PARTY_NOTICES.md, widget.py, pet.py, analytics_view.py, build.ps1.
V1.1.0 foundation slice: app_config.py (new), localization.py (new), desktop.py, widget.py, tests/test_settings.py (new), PROGRESS.md, HANDOFF.md, and external `V1.1.0/99_Implementation_Notes.md`.
V1.1.0 Daily / Token slice: app_mode.py (new), activity.py, usage.py, widget.py, pet.py, tests/test_app_mode.py (new), tests/test_activity.py, tests/test_ui.py, PROGRESS.md, HANDOFF.md, and external `V1.1.0/99_Implementation_Notes.md`.
V1.1.0 working-context slice: usage.py, widget.py, pet.py, tests/test_app_mode.py, tests/test_ui.py, tests/test_working_context.py (new), PROGRESS.md, HANDOFF.md, and external `V1.1.0/99_Implementation_Notes.md`.
V1.1.0 scope slice: app_config.py, usage.py, widget.py, analytics_view.py, tests/test_scopes.py (new), tests/test_settings.py, tests/test_ui.py, PROGRESS.md, HANDOFF.md, and external `V1.1.0/99_Implementation_Notes.md`.

## Important Decisions
- Source: local Codex `state_*.sqlite` + JSONL sessions; UIA document LegacyIAccessible Name follows actual active task. Initial URL is stale and must never select the task.
- App-server only initializes and reads account/rateLimits/read; exact 300 and 10080 minute windows selected. Public Bank of Canada USD/CAD daily series.
- Token source total includes cached input and reasoning output. Enhancement must replace missing-as-zero behavior with explicit unknown coverage without removing fields.
- Default pet toggles the existing panel; analytics in a separate modeless details window. Preserve all quota functionality and add visible reset countdowns.
- Upload is already authorized; do not change repo visibility. All screenshots with live personal data stay ignored in `.private/`.
- Activity priority: transient usage panel > microphone > music > typing > idle. Detect only activity booleans/timestamps, never typed text or audio content. Hide usage after leaving pet/panel, respecting open settings/details.
- Reference: https://github.com/ccusage/ccusage (MIT; active). Studied cumulative/last-request parsing and cache subset normalization; no code copied, kept Python architecture. https://store.steampowered.com/app/3419430/Bongo_Cat/ inspires temporary key-reactive posing only, not replacement character art.
- Continuation decisions: canonical name `petoken`, canonical repository `windknows-ai/petoken`. Rename user-facing branding only; preserve the persisted `CodexWisp` settings directory, module/class/internal identifiers, and historical `Codex Wisp` names in V1.0.0 release documentation. Version stays V1.0.0; no increment for documentation/branding work.
- Daily / Token mode is centralized in `AppModeState`; UI components consume that state and do not independently infer Codex activity.
- A visible Codex window alone never activates Token Mode. Explicit session lifecycle plus fresh UIA task presence is the primary rule; missing/stale/unreadable sources are conservative and cannot activate it.
- Working-session selection and project/Token binding happen in `CodexStore`; the pet consumes a single `working_context` object and does not combine independently selected values.
- The Token Mode pet bubble follows the selected global working session; analytics scope is an independent user selection and cannot change active-work detection.
- Scope identity is structured rather than label-based: Global carries `scope_type` and a local-recorded flag; Project carries stable ID/name/source; Conversation carries thread ID/title and its parent project identity. Formatted labels are presentation only.
- Existing settings remain compatible: missing scope defaults to Conversation, legacy `task` is interpreted as Conversation, and malformed values safely fall back to Conversation. The persisted `pinned` value remains the stable conversation selector.

## Current State
V1.0.0 is finished and verified. OpenCode performed the pre-implementation Step 1 architecture inspection only; Codex verified it and has performed all V1.1.0 implementation work. Checkpoint `859b654` records the foundation and Daily / Token slices; checkpoint `f061ccf` records Working Context. The completed scope slice remains intentionally uncommitted. `99_Implementation_Notes.md` is maintained outside this Git repository.

## Known Issues
- Media playback detection depends on Windows System Media Transport Controls, so players that do not integrate with Windows media controls cannot be detected reliably.
- Microphone detection reports active Windows capture sessions; the app never opens or records the microphone.
- The release executable is not code-signed; Windows may show its normal unknown-publisher/SmartScreen prompt on another machine.
- V1.1.0 visual references resolved: `04_Visual_Reference_Specification.md` in `D:\Desktop\petoken\V1.1.0` is the authoritative text representation of Reference Images 1, 2, and 3; image-reading capability is not a blocker.
- The GitHub release is now titled `Petoken v1.0.0` and flagged Pre-release (the V1.0.0 delivery record documented a full release), and repository visibility is now public (was private). Confirm both are intended.

## Tests / Verification
- 17 unit/UI tests pass: price/cache math, nullable accounting, dedup/partial lines/resets/forks/model changes, calendar aggregation, state priority/debounce, transparent assets, hover reveal, N/A cache writes, countdown preservation, task matching and quota duration/expiry.
- Approved idle asset SHA-256 remains `7ce0d2fbd0eb89d2f6786c9bb1d5bada1aff7d89ea2f5dd079cce8a26483e1a0`; every activity sprite has a real transparent alpha channel.
- Independent local raw-record reconciliation: 28 sessions reconciled; model and session sums match; warm cached read about 0.005 seconds.
- Official quota RPC, UIA title and public FX verified live.
- `.private/first.png` shows live panel; title followed a switch to the 3D website task correctly.
- Normal and 200% DPI synthetic views inspected: all four poses, compact panel and analytics are legible without clipping.
- Clean frozen `CodexWisp.exe --smoke` exits 0, follows `构建沉浸式3D个人网站`, reads usage and gets live account quota. The release tree contains no foreign ICU copied from the Codex tool runtime.
- Final frozen smoke follows `开发实时用量悬浮 Widget`, reports live quota, `keyboard_hook_error: null`, and valid microphone/music booleans. A synthetic F24 key event triggered the real low-level hook and selected `typing` without capturing text.
- Final archive: 53,316,751 bytes; SHA-256 `339598CC41F9D15A7B778A0C2CF6B73513CB0BF6C4918B7704216B7FCCE4E26E`.
- Source/private-data scan found no credential signatures or personal absolute paths; `.private/`, build output, dist output, virtualenv and generated spec are ignored.
- Commit `ab843dd2082ab5848ded03a210cd2ca7e04ac838` pushed to `origin/main`; GitHub Release `v1.0.0` is published, non-draft and non-prerelease. Uploaded asset size/digest match the local archive.
- Desktop shortcut target verified; final `CodexWisp.exe` process is running and responsive.
- V1.1.0 foundation verification: 22 tests pass (17 existing + 5 targeted); all project/test Python files pass `py_compile`; isolated source smoke exits successfully with current task, usage, live quota and activity signals; smoke image preserves the existing 360×730 UI; `git diff --check` passes.
- An initial smoke run exposed a removed `json` import used by the smoke-report callback. The import was restored and the complete test/compile/smoke sequence passed on rerun.
- Daily / Token verification: 30 tests pass (22 prior + 8 targeted); all project/test Python files pass `py_compile`; isolated live smoke reports `app_mode: token`, `reason: task_started`, correct live usage/quota, and no keyboard-hook error. Token and Daily pet screenshots were inspected: the Token bubble is unchanged and the Daily bubble is absent.
- Live detector timing on current local data: about 4.07 ms for the bounded cold scan and 0.06 ms for a warm incremental check.
- Working-context recovery verification: the uncommitted implementation was complete rather than partial. All 39 tests pass (30 prior + 9 targeted), all Python files pass `py_compile`, and an isolated live smoke detected two working sessions, selected the foreground thread, and reported its matching title, `Web Project`, 31,399,745 session Tokens, explicit project metadata source, live quota, and no keyboard-hook error. The bubble screenshot was inspected and kept the existing 242×378 pet / 240×70 bubble geometry.
- Initial fixture runs exposed that Python's SQLite context manager does not close Windows file handles and that display names must not reuse case-normalizing path logic. Production read-only connections now close explicitly, and cwd fallback extracts its basename without altering case; all tests passed after both fixes.
- Scope verification: 52 tests pass (39 checkpoint tests + 13 scope/settings/UI tests); all project/test Python files pass `py_compile`. Isolated Global smoke exits 0, reports `scope_type=global` with the local-recorded limitation, aggregates 1,698 unique events / 186,031,972 Tokens, keeps live quota/activity signals, and independently shows the active `Web Project` Working Context in the pet bubble. Panel, pet and expanded analytics screenshots were inspected.

## Remaining Work
- Implement compact/full Token number formatting and consistent metric units.
- Continue later V1.1.0 steps only when authorized. Do not start V1.2.0.

## Next Step
Implement V1.1.0 order step 6 only: add the persisted Full / Compact Token number format and consistent units in Token Analysis. Do not begin the full localization pass, currency work, assets, Bongo-Cat, subtitles, or V1.2.0.
