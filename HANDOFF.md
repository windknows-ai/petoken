# Handoff

Concise agent-to-agent recovery snapshot. This is NOT a substitute for `PROGRESS.md`, `CHANGELOG.md`, `AGENTS.md`, or the external version specifications.

## Current Version

`V1.0.0` (released, verified baseline of `petoken`, formerly Codex Wisp)

## Current Target Version

`V1.1.0` (UI and interaction refinement — through responsive polish complete; redesign committed, responsive uncommitted; not pushed)

## Current Stage

OpenCode is the active continuation agent (Codex at usage limit). Redesign was committed as `74cddea`; the Step 13 responsive polish (top-pinned tall layouts, crash-safe size restore, restart/compact persistence, min-width stress) is complete and verified but intentionally uncommitted. No data-semantics or visual-language change. Nothing was pushed. Visual references are resolved by `04_Visual_Reference_Specification.md`.

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

## Current Work / Partial Work

None in progress. Step 13 responsive polish is complete and verified but uncommitted (see Git state). Do not start V1.2.0.

## Important Decisions

- Canonical project name: `petoken`. Canonical repository: `windknows-ai/petoken`.
- Preserve persisted settings directory `.../LocalAppData/CodexWisp` and module/class/internal identifiers; rename only user-facing branding.
- Preserve historical `Codex Wisp` references in V1.0.0 release documentation and commits.
- Version stays `V1.0.0`; do not increment during this cleanup.

## Current Git State

- Branch: `main`, HEAD `74cddea` ("feat: redesign compact token interface"), eleven commits ahead of `origin/main`; nothing was pushed.
- The Step 13 responsive slice is intentionally uncommitted and unpushed. Modified tracked files: `widget.py`, `PROGRESS.md`, `HANDOFF.md`. New untracked files: `tests/test_responsive.py`. `AGENTS.md` remains worktree-modified (excluded from every checkpoint).
- Verification: 143 tests pass, `py_compile` passes, `git diff --check` passes, min/max/typical sizes × zh/en × Full/Compact × 3 scopes × 4 currencies inspected plus Token card at 100/125/150/175/200%, live isolated smokes exit 0.
- External `D:\Desktop\petoken\V1.1.0\99_Implementation_Notes.md` is updated outside this Git repository.

## Known Issues / Blockers

- Visual references resolved (no blocker): `D:\Desktop\petoken\V1.1.0\04_Visual_Reference_Specification.md` provides the authoritative text visual specification for Reference Images 1, 2, and 3. Do not claim the reference images are missing.
- GitHub release is titled "Petoken v1.0.0" and flagged Pre-release (delivery record documented a full release); confirm whether this is intended.
- Repository visibility changed from private (per V1.0.0 PROGRESS) to public; confirm intended.
- Working-state recovery is bounded: an unclean session with no `task_complete` can remain active for at most five minutes while a task window exists; a genuinely running tool that writes no rollout events for more than five minutes can temporarily fall back to Daily until the next event.
- The prior project/Token mismatch is resolved for the pet bubble. The expanded dashboard now has the completed three-scope system, independent from active Working Context.
- Some local sessions have neither project metadata nor Git origin nor cwd; their project is shown as unavailable instead of being invented.

## Exact Next Step

1. Implement V1.1.0 order step 14 only when authorized: Music Mode subtitle capability (or clean feature-ready module).
2. Do not combine that slice with Working-animation or V1.2.0.
3. Do not mark V1.1.0 complete until all V1.1.0 acceptance criteria are verified.

## Last Agent

OpenCode (active continuation agent; Codex at usage limit).
