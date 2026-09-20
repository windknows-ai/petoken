# Astra-6 independent V1.1 review — 2026-09-20

Latest: the correction-slice acceptance addendum at the end records R1-R9 FIXED and slice PASS. The original review below is preserved as history; version-level release acceptance remains PARTIAL.

## Verdict and scope

**PARTIAL. Final acceptance and release gate: NOT PASSED.** The architecture and much of V1.1 work are sound, but the latest companion/persistence implementation has reproducible regressions. Keep the approved visual direction; correct behavior before publication. No V1.2 implementation is authorized.

Reviewed source HEAD: `64f7fcb` on `main`, 16 local commits ahead of the current `origin/main` tracking ref. Initial unstaged change: `AGENTS.md` only. No remote push was performed. Reviewed OpenCode commits after the Codex formatting checkpoint `896ed09`, including the jointly continued localization slice `27ceb81` through final art, polish, and companion redesign. Attribution is not inferred solely from Git author names.

Astra read repository instructions/state/history/diff and active external V1.1 specifications 00–04 and 99. The latest explicitly approved landscape/enlarged companion direction takes precedence over older approximately-half-scale presentation requirements. This review does not request new artwork or a redesign.

Implementation code, test code, assets, versions, and AGENTS.md were not modified during review. Review/state/roadmap documents were updated; ignored diagnostic images and JSON are in `.private/astra-review/`. No commit, push, release, or binary publication.

## Independent validation

| Check | Result / limits |
| --- | --- |
| Full unittest discovery | 196/196 passed in 15.224 seconds in this review |
| py_compile | All 36 root/tests/tools Python files passed |
| Isolated source smoke | Exit 0; real usage available; live quota; no keyboard-hook error; panel 560×500; separate temporary preferences |
| Visual inspection | Fresh Chinese/English panel, analytics, desktop pet, and minimum-size Full-number screenshots inspected; current machine scaling only |
| Qt lifecycle probes | Reproduced R1–R4 and R8 below without changing application code; live stage probe uses production state, not preview_state |
| Analytics heading probe | Reproduced R5 with explicit synthetic tokens |
| Local verifier command | `python tools/verify_local.py` FAILS at `assert checked>=3`; its default Conversation read indexes one eligible session |
| Independent Global reconciliation | Explicit `CodexStore.read(scope='global', include_history=True)` indexed 44 sessions; 30 eligible non-fork/non-partial/non-reset sessions match raw cumulative counters; model/session totals match history total |
| git diff --check | Passed; Git emitted only an existing AGENTS.md LF/CRLF conversion warning |
| Frozen build / clean-machine acceptance | Not rebuilt or independently accepted in this review; earlier OpenCode frozen reports do not substitute for a corrected-HEAD build |
| DPI / hardware boundaries | Not independently tested across all 100/125/150/175/200% settings or physical monitor changes; source smoke is not full end-to-end microphone/media/multi-monitor acceptance |

Private evidence: `probes.json`, `extra-probes.json`, `live-smoke.json`, `live-smoke.png`, `panel-en-full.png`, `pet.png`, `analytics-en.png`, `min-full.png`. These must stay ignored and must not be published. A supplementary synthetic UI probe initially supplied an invalid `usd=None` fixture; it was corrected to the source contract's numeric subtotal before evaluating UI results. This fixture mistake is not claimed as a production regression.

## What passed

- Existing centralized version/settings/localization foundation and compatible CodexWisp settings location remain; APP_VERSION is 1.1.0.
- Daily/Token modes, separate Working Context, three-scope numeric aggregation, nullable fields, cache/reasoning subset accounting and fork deduplication retain regression coverage. Live local reconciliation supports the arithmetic; it does not prove every UI interpretation is correct.
- Four-currency estimated-cost presentation, formatting controls, quota reads/countdowns, analytics tables and existing desktop-pet actions remain available. No evidence of a new parser/accounting regression was found in inspected changes.
- Seven chibi assets and shared registry exist; original V1.0 asset preservation is covered. New composition, palette and large character are directionally consistent with the requested character-led companion.
- Music text honestly depends on optional platform subtitle metadata. No real lyrics recognition/transcription is implemented or claimed as verified; absent metadata is an acceptable fallback under the active spec.

## Required corrections

### R1 — P1: Always on Top changes do not preserve a usable window

`widget.py:403–423`, `widget.py:956–971` (introduced in persistence polish).

Settings.save updates the stored preference but never calls apply_topmost: after saving false, both panel and pet still have WindowStaysOnTopHint. Conversely, the pet menu calls apply_topmost, whose setWindowFlag hides the widget before isVisible is checked. A visible pet becomes hidden; both pet and panel can be invisible after toggling.

Apply flags on Settings save and menu changes through one path. Capture visibility before mutation, preserve the intended visible owner and geometry, and coordinate with show/hide coupling without activating/focusing windows unnecessarily. Test true→false and false→true in both visible-pet and visible-panel configurations, Settings and menu paths, restart persistence, and manually hidden states.

### R2 — P1: Pinned startup shows two characters

`widget.py:624–628`, `widget.py:650–675`, `widget.py:1086–1089` (persistence/redesign interaction).

Panel.__init__ shows a pinned panel before main attaches DesktopPet. showEvent cannot hide a pet that does not exist yet; main then unconditionally shows it. Fresh construction with panel_pinned=true produces panel_visible=true, pet_visible=true, stage_visible=true.

Initialize visibility ownership after both objects exist, including pinned/compact startup. Test the actual main initialization order, not only manually ordered panel.show/pet.hide calls. Exactly one intended character owner should be visible; closing/unpinning must restore the correct desktop state.

### R3 — P2: The new live stage is locked to idle and its animation clock stops

`pet.py:101–130`, `pet_assets.py:56`, `widget.py:251–257`, `widget.py:646–663` (introduced by companion redesign).

The visible panel makes ActivityState return usage; usage aliases to idle. CompanionStage copies this state. Hiding DesktopPet stops its animation timer, but the stage copies the stopped pet.phase. A normal Token-mode probe produced state=usage and phase 0 before/after event-loop advancement while the stage's 50 ms timer kept repainting.

Keep usage-panel priority and one authoritative activity decision, but separate overlay visibility from the underlying companion activity needed by the stage. Give the visible renderer an advancing animation clock while respecting motion-off/hidden states; avoid restoring an unnecessary hidden-pet rendering loop. Exercise Working, microphone, music, typing, idle and motion-off through production signals with no preview_state override. Existing state-mirroring tests force preview_state and miss this defect.

### R4 — P2: An inactive selected project/conversation is labelled Working

`widget.py:815–824` (introduced by companion redesign).

Status is driven by global AppModeState while project/title/tokens use the selected analytics scope. With A working and the panel pinned to completed B, the UI labels B Working. Numeric scope selection itself remains coherent, but the activity claim is false.

Bind a context-specific label to that scope's verified working identity, or explicitly label a separate global Codex status and identify the actual working context. Do not silently force analytics back to the working session; preserve independent scopes. Test pinned inactive B/active A, Global, Project, Conversation, and multiple working sessions.

### R5 — P1: Conversation Total Tokens are labelled Non-reasoning Tokens

`analytics_view.py:112–118`, `analytics_view.py:175–178` (localization regression in 27ceb81; previous checkpoint had the correct Total header).

Session headers use token_headers[:-1], dropping Total, while session values omit Non-reasoning and retain Total. The last column displays the official total beneath Non-reasoning Tokens. Synthetic reproduction: header Non-reasoning Tokens; value 1,580,246,791,357 Tokens.

Keep header/key mappings aligned in both languages. Prefer exposing both available non-reasoning and total values to retain all categories, with clear labels. Assert the meaning and numeric value of every model/session/history column, not just column counts or non-null screenshots.

### R6 — P2: Desktop art distorts the approved square assets

`pet_geometry.py:35–37`, `pet.py:233`, `widget.py:286` (old rectangular geometry exposed by final square-art integration).

1254×1254 source images are stretched into 145×197 on the desktop and 184×184 in the stage. The same character therefore has different proportions across surfaces. This is distinct from the approved intentional size difference.

Fit source aspect ratio into logical bounds while preserving the established feet/ground anchor, consistent activity placement and current intended prominence. Do not redraw PNGs or revert the approved 0.68 scale. Validate every pose plus typing frames at multiple DPRs.

### R7 — P2: Full Token numbers are clipped at supported minimum size

`widget.py:522–523`, `widget.py:805–810`, responsive tests.

At PANEL_MIN with Full formatting, 1,580,246,791,357 is visibly cut after 1,580,246,791, in the viewport. Single-line I/O can also force content wider than its viewport. A label's own width fitting the text is insufficient when its scroll viewport clips it. Current resize matrix uses modest 138,000 totals and mainly asserts grab is non-null.

Preserve Full semantics and readable access to full input/output/total at minimum/default sizes; use measured fitting/wrapping/layout behavior without changing the approved art direction. Test B/T-scale values, zh/en, all scopes, viewport clipping, and fractional DPI; inspect resulting images.

### R8 — P2: Missing-data transitions leave old analytics/insights looking current

`widget.py:780–793`, `analytics_view.py:128–132` (pre-existing behavior, not attributed solely to OpenCode).

After a good snapshot followed by a missing/error snapshot, main title resets but prior Cache hit/New work and an open Analytics window still present the previous context without a stale label. This is misleading when a selected scope becomes unavailable.

Clear or explicitly mark last-known values and their old identity; preserve retrievable history rather than deleting data. Verify scope switch→unavailable, source failure/recovery, already-open Analytics, tooltips and history tables. Do not replace unknown values with zero or fall back to another project.

### R9 — P2: Smoke diagnostics persist newly added media text

`activity.py:18–36`, `widget.py:1115` (new music_text combined with existing diagnostic serialization).

ActivityMonitor.status now includes subtitle and track identity. main --smoke serializes the whole status into JSON. A nonempty synthetic music_text is preserved by this exact serialization path, contradicting the memory-only/no-subtitle-or-media-title-persistence promise. The live smoke had music_text=null; no actual media text leak is claimed from this review run.

Allowlist safe activity diagnostics (state booleans / capability availability / bounded error information). Exclude subtitle, title, artist and track identity from reports/logs; test nonempty synthetic metadata. Keep functional live subtitle rendering.

## Remaining acceptance gaps (do not mark these PASS without evidence)

- Spec 03 §14: Settings always exposes the same flat conversation selector. Global does not hide irrelevant selection, and Project lacks an explicit project selector. Respect the current scope architecture; complete the small scope-specific controls, not a new navigation system.
- Spec 01 §11: multiple-working detection exists but the requested compact active-count/clear multi-project presentation is absent. Either implement the bounded indicator or obtain explicit deferral; a previous self-assessment of 'minor' is not a waiver.
- Spec 02 §12: pet hover uses its rectangular frame, including transparent Daily bubble space; no visible-shape hitbox implementation was found. Verify native Windows behavior and constrain unnecessary transparent interaction. Do not claim native click-through purely from transparent painting.
- Spec 02 §19: no automatic system reduced-motion integration was found. Manual motion pause alone does not verify the system preference requirement. Investigate the technically practical native path or record a concrete, accepted fallback.
- Spec 02 §20: no complete idle CPU/RAM, animated CPU, monitoring overhead and startup baseline is recorded. Earlier parser/render timing is useful but is not that baseline.
- The requested fractional-DPI/physical monitor matrix and clean-machine frozen acceptance are not independently established. Correct code first, then validate that exact revision. Music metadata fallback is acceptable; synthetic art previews are not proof of real lifecycle behavior.

## Verification tooling and documentation corrections

- Update tools/verify_local.py to deliberately select its intended scope. Default read now means Conversation; its unconditional >=3 requirement assumes old all-session loading. Keep cross-session checks meaningful: explicit Global reconciliation plus fixtures/clear insufficient-data reporting. Do not just remove assertions to get a green result.
- HANDOFF/PROGRESS/99's prior 'complete/ready/no required gaps' statements are superseded by this review. Record actual fail/partial states until re-reviewed.
- CHANGELOG and release notes still describe the 50% scale/grouped old panel or 300–480×380–800 bounds. Current implementation uses 0.68 scale and 480×420–600×640 bounds, default 560×500. Correct after the fix; keep V1.1 explicitly unpublished. DESIGN and old narrative sections should not be mistaken for current acceptance evidence.
- Do not change APP_VERSION, commit, push or publish automatically as part of review corrections.

## Recommended sequence / release gate

1. **Next bounded OpenCode correction slice:** R1–R9 and targeted real-lifecycle regression tests; preserve current art/composition and accounting. Repair the reconciliation tool and stale status docs. Stop for Astra review.
2. **V1.1 acceptance closure:** explicitly close scope/multiple-task/hitbox/reduced-motion gaps (or user-approved documented fallback where permitted), measure performance, run fresh all-DPI source and frozen QA after corrections. Avoid speculative V1.2 behavior.
3. **Only after acceptance passes:** release preparation/packaging against an identified revision; clean-machine DLL/startup test, actual release metadata, source/art notices and recoverable settings check. User separately authorizes any commit/publication required for release.
4. **After accepted V1.1:** V1.2 planning only, not implementation. Recommend one bounded Codex-status/usage-limit-awareness feature, chosen from the existing roadmap and reconciled with future specifications; do not bundle voice, calendar, file actions, GitHub integration or personality systems. Start only on explicit user approval.

OpenCode should receive a copyable task referencing this report. It must inspect the current diff, preserve pre-existing AGENTS.md and review documentation, implement only the authorized correction slice, validate it, update progress/handoff/99 and stop. Astra remains read-only for implementation.


## Correction-slice acceptance - Astra-6, 2026-09-20

This addendum preserves the original independent review above. The user temporarily authorized Astra as implementer, paused OpenCode, and then expanded the interrupted slice to finish R1-R9. **Correction-slice verdict: PASS. Overall V1.1 release verdict: PARTIAL**, because separate acceptance gaps listed below remain. This is not publication approval or V1.2 authorization.

### Exact recovered state / scope

Parent HEAD was 64f7fcb. At continuation, the tree already contained intentional Astra changes to pet.py, pet_geometry.py, widget.py and tests/test_companion.py plus geometry/responsive/persistence/UI tests. Existing dirty AGENTS.md, HANDOFF.md, PROGRESS.md, ROADMAP.md and this previously untracked review were preserved. No reset/revert or replay from HEAD occurred. The original 256-square renderer, DPR cache and single-character satellite approach were continued; side preference was changed from the unfinished left-first prototype to the new explicit right-first requirement.

### Size, pixels and ownership

- Old draw box: 145 x 197 logical px, stretching a square source. New: 256 x 256, in a 272 x 330 transparent window (previous window 242 x 268). Width +76.6%, height +29.9%. The idle PNG alpha bounds correspond to approximately 130.9 x 192.0 old visible logical px versus 231.1 x 249.5 new visible px; this is an actual artwork enlargement, not just window padding.
- Original PNGs are unchanged. DesktopPet.render_sprite resizes each original source once per actual DPR using KeepAspectRatio/SmoothTransformation, preserves alpha, tags the result's DPR, and draws it at a device-pixel-aligned point without a second target-rectangle resize. Cached outputs for a square source are 256/320/384/448/512 physical px at DPR 1/1.25/1.5/1.75/2. Cache invalidates on DPR change.
- One stable feet anchor: (136, 320) logical px. Short/tall fallback sources are contained and bottom-aligned, never stretched. Approved typing frames retain shared geometry. The panel no longer owns CompanionStage or a separate animation clock.
- The real desktop pet stays visible, live and in place through panel open/close. Usage is an overlay, not an idle pose override. Working > microphone > music > typing > idle remains the character priority. Motion-off pauses animation, hidden pet stops its paint timer. Clicking to open no longer adds a reaction wobble or writes pet_position; dragging persists the normal position.
- Satellite keeps the palette and typography, removes the empty duplicate-character gutter, defaults to 420 x 500, bounds 360 x 420 to 600 x 640, compact height 250. Existing valid saved panel sizes remain usable.

### Exact positioning rule / evidence

Use the pet rectangle and the available geometry of the screen containing its center. Prefer RIGHT with a 12 logical-pixel gap; otherwise LEFT if it fits; otherwise use the side with more room (right wins ties). Bottom-align, then clamp ONLY the panel. On genuinely undersized work areas this explicit fallback may overlap the pet; it never relocates the pet. No above/below alternative or recentering is substituted.

Panel.showEvent, reopening, resizing/compact changes and movement of a visible pet use the same helper. Pinned startup runs only after both objects exist. Manually hiding the pet remains independent. Manual panel dragging is retained; the next pet move/reopen restores the attachment.

Qt tests cover repeated actual clicks (no saved-position write), show/hide coordinates, drag/reopen plus persisted coordinates, startup pin, hidden-pet behavior, topmost in both directions, negative-origin monitor geometry, both sides and insufficient-space clamp. Five DPI runs each perform five open/close cycles at right/left/edge placements: **75 open/close cycles with zero position drift**. A native two-monitor probe also passes placement/containment/topmost visibility and verifies foreground focus is preserved.

### R1-R9 disposition

| Issue | Status | Implementation evidence | Verification evidence |
| --- | --- | --- | --- |
| R1 | FIXED | Settings.save applies topmost; apply_topmost captures/restores visibility and coordinates before flag changes | Settings/menu paths, both directions, actual visible windows/position and existing persistence tests; native foreground probe |
| R2 | FIXED | restore_companion runs after pet construction; no duplicate stage exists | Actual startup order with panel_pinned, both windows visible with exactly one character, no overlap |
| R3 | FIXED | DesktopPet remains renderer/animation owner; opening UI does not force usage-to-idle | Runtime Working/microphone/music/typing/idle signals, real two tap frames, Qt timer advancement/motion pause; no preview_state in new lifecycle probes |
| R4 | FIXED | Detector retains all verified working thread IDs; CodexStore intersects those with scope membership; UI uses scope_activity, Unknown when invalid | Active A plus pinned inactive B, two simultaneous working sessions, Global/Project/Conversation and unavailable detection |
| R5 | FIXED | Conversation table has all nine correctly matched columns including both Non-reasoning and Total | Exact header-to-value assertions in zh_CN/en; nullable Cache Write remains N/A |
| R6 | FIXED | Source aspect ratio preserved in DPR-sized cache, shared feet anchor | Square and tall-source tests, all-pose pictures, five effective DPRs, unchanged source PNGs |
| R7 | FIXED | TokenTotalLabel fits complete integer text; I/O and insights wrap within scroll viewport | Full 1,580,246,791,357 at minimum width in zh_CN/en; viewport/font/height checks and five-DPI screenshots |
| R8 | FIXED | Missing/error snapshot clears obsolete insights/tooltips/tables/raw view; missing history clears prior ranges/days; failed pet context no longer retained as current | Valid -> unavailable -> recovery and history reset tests; no deletion of underlying records |
| R9 | FIXED | activity_diagnostics allowlists microphone/music booleans only; smoke uses it | Nonempty synthetic subtitle/title/artist/new metadata excluded; both source/frozen JSON contain only those two activity fields |

### Verification and tooling

- Full suite: **210 tests PASS** (final pre-commit run 16.987 seconds). Obsolete stage/old-dimension tests were replaced with the explicitly requested behavior, not dropped to hide defects. Existing accounting/modes/scopes/settings/localization tests remain green.
- py_compile: **37 Python files PASS** (root, tests, tools).
- tools/verify_local.py now starts with explicit Global and reconciles nullable official fields, known subtotals and event counts across model/session groups. It additionally reconciles available Project and Conversation selections. It reports INSUFFICIENT_DATA with exit 2 below three eligible raw sessions instead of falsely passing; corruption and insufficient-history fixtures verify that behavior.
- Live local verifier: **PASS**, 31 eligible raw sessions / 44 indexed; Global 1, Project 3, Conversation 3 checks, model/session sums match. Cold ~1.69 s, cached Global read ~0.013 s on this machine (parser timings, not a complete application performance baseline).
- Isolated source smoke: **exit 0**, real usage and quota available, keyboard hook error null, 420 x 500, safe activity diagnostic fields.
- PyInstaller: **PASS**, using the existing PATH/VC-runtime mitigations; final build log `.private/anchor-slice/build-final.log`.
- Isolated final frozen smoke: same acceptance checks as source; result recorded in `.private/anchor-slice/frozen-final.json`. This validates this host, not a pristine machine.
- Visual QA: tools/verify_companion.py uses real activity state inputs, Qt timers and separate top-level windows; **60 named captures across measured DPR 1, 1.25, 1.5, 1.75, 2**. Includes idle, Working, two tap frames, microphone/music, right/left/edge, pin and min-size Full zh/en. Sprite line art, eyes/hair, silhouette and aspect inspected; transparent pair captures plus native desktop captures confirm ownership/placement. No PNG edits or new dependencies.
- Physical monitor probe: two connected monitors, both native DPR 1.25; attachment stayed on the pet's monitor and did not steal focus. Fractional/200% checks use verified Qt DPR overrides; a hardware mixed-DPI hotplug test is not claimed.
- git diff --check passed. All personal/native screenshots and runtime preferences remain ignored in .private/anchor-slice. No user settings or Codex logs were modified.

### Files and remaining boundaries

Implementation: pet.py, pet_geometry.py, widget.py, usage.py, analytics_view.py, activity.py, localization.py. Verification: tests/test_companion.py, test_working_context.py, test_panel_persist.py, test_pet_geometry.py, test_pet_assets.py, test_redesign.py, test_responsive.py, test_ui.py; tools/verify_local.py and new tools/verify_companion.py. State/presentation docs: this report, PROGRESS.md, HANDOFF.md, DESIGN.md, CHANGELOG.md, docs/RELEASE_NOTES_v1.1.0.md; external V1.1.0/99_Implementation_Notes.md appended without rewriting its existing mixed-encoding bytes.

Remaining **version-level** gaps outside the authorized R1-R9 correction: scope-specific project selector/irrelevant Global selector, compact multiple-active indicator, shaped transparent hitboxes, system reduced-motion integration and complete CPU/RAM/startup baseline. Clean-machine distribution and hardware mixed-DPI/hotplug acceptance also remain. Optional media subtitle fallback stays honestly conditional on the platform. These are not silently marked PASS.

APP_VERSION stays 1.1.0. The authorized single local correction checkpoint uses message `fix: close V1.1 companion acceptance gaps`; its parent is 64f7fcb. Pre-existing AGENTS.md and ROADMAP.md changes are excluded. No push/publication. V1.2.0 not started. After this slice Astra returns to the default review/planning role; no next implementation slice begins automatically.

## Pet-scale addendum - OpenCode, 2026-09-21

Final V1.1 requirement implemented on top of the correction checkpoint without altering its geometry, anchoring, or rendering: persistent `pet_scale_percent` (default 100%, range 50–150%, invalid normalizes to 100%). 100% reproduces the approved 256-square composition exactly (base geometry functions byte-unchanged; asserted by test). Scaling is proportional across window/sprite/anchor/bubble/fonts/amplitudes and reuses the single-DPR-resample pipeline; resize preserves the feet anchor's screen position and re-docks the panel through the existing right-first helper. Settings exposes a Character Size / 角色大小 slider with live preview, cancel-revert, Save persistence and Reset-to-Defaults 100%.

Evidence: 232/232 tests pass (22 new in tests/test_pet_scale.py: defaults, bounds, 100%-unchanged, half/intermediate/max geometry, persistence, invalid normalization, reset, all seven state families incl. both typing frames, aspect stability, anchor stability, clamp, panel adjacency, no-move open, no-drift rescale, live preview, bilingual labels); py_compile and git diff --check pass; isolated source smoke exits 0 with live usage/quota; 50/75/100/150% idle+working pets, Settings zh/en, and panel adjacency inspected at measured DPR 1.25 and 2.5 (`.private/pet-scale-qa/`, ignored). 150% maximum justified: 408×495 still docks beside the panel on standard screens and stays below the 1254 px source at high DPR. No artwork, analytics, or version change. Single local checkpoint `feat: add adjustable pet character size`; AGENTS.md/ROADMAP.md pre-existing changes excluded; nothing pushed; V1.2.0 not started.

## Manual-acceptance addendum - OpenCode, 2026-09-20 (A1-A4)

User manual testing on the frozen app found four issues automated QA missed. Dispositions below; single local checkpoint `fix: close final V1.1 manual acceptance issues`; nothing pushed/tagged/published; V1.2.0 not started.

### A1 — Character Size control not found: PASS (stale frozen binary, not a code defect)

Root cause: the frozen binary under test (`dist/petoken/petoken.exe`, 12:19:26) predates the pet-scale commit `c277366` (13:03:40) by ~44 minutes, so it cannot contain the control. The feature exists in HEAD: the real Settings window was launched and inspected — 角色大小 / Character Size slider (50–150%, live %, default 100%) is the last form row, visible without scrolling in zh_CN and en (dialog 540×537/612). Closed with a fresh frozen build whose smoke Settings screenshot shows the same slider. Lesson: acceptance must run against a build of the reviewed revision.

### A2 — QQ Music shows no subtitle: PASS (honest no-subtitle behavior, documented limitation)

Live inspection of the running `QQMusic.exe` SMTC session: title present, artist present, album_title present, **subtitle empty**, playback status PAUSED (5). A 4-second live `ActivityMonitor` probe reads music=False / music_text=None — the pipeline is correct. Per the approved subtitle-only design, no pill is the required behavior; no scraping, lyric APIs, audio capture, transcription, persistence, or fabrication was added. If QQ Music ever populates `subtitle` while Playing, the existing verified path displays it.

### A3 — Compact layout redesigned: PASS

Compact was a cropped expanded stack (cost/pin and status/settings stretched into detached islands, no token metric). It is now intentional: header/project/title/model rows, one divider, one metrics row (cost hero + auto-fitting token hero sharing the width), one control strip (status + pin + settings). Expanded bars lend status/pin/settings while compact (order-stable, flag-guarded); cost uses auto-fit twins so Full trillions plus large costs share a 360 px row with no overlap and no clipped values. Expanded UI untouched. Verified zh/en, Compact/Full, $17k cost, 360/420/600 widths, pinned ◆, two DPRs.

### A4 — Compact to Expanded restore: PASS

Real `QTest.mouseClick` lifecycle probes on HEAD: click enters compact (420×316, `+`), click `+` restores expanded with the last valid size (520×520 and 500×460 cases), 4+ repeated cycles hold size with controls intact, restart-in-compact restores then expands on click. The reported total failure matches the stale 12:19 binary built mid-refactor (64f7fcb-era `CompanionStage` overlay / WIP tree), not current code. Hardening added: `toggle_compact` resets the pet leave-timestamp so an expand-then-anchor jump gets auto-hide grace instead of vanishing. COMPACT_HEIGHT is now 316 (fixed-height holds at every width after disabling wrap on the compact twins; the old ≤280 assertions were legitimately updated).
