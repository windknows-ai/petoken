# Changelog

Concise summaries of released versions. Version-specific detail lives in the release documentation; do not turn this file into full technical documentation.

## V1.2.0 — 2026-09-22 (local release candidate; not yet published)

Dual-provider companion: the pet follows Codex and OpenCode tasks side by side, verified against `D:\Desktop\petoken\V1.2.0`, implementation accepted for release preparation.

### Added
- Second usage provider (OpenCode, read-only local SQLite): automatic/manual tracking across Auto / Codex / OpenCode with working-first Auto ranking; Conversation scope may present the verified live session as an explicitly marked Active session when the requested scope names no session.
- OpenCode Token Analytics: five raw categories (Input / Output / Reasoning / Cache Read / Cache Write) with independent coverage, source-backed recorded Total for verified session versions (see Boundaries), recorded cost with unknown currency, per-session breakdown and daily history with coverage markers.
- Commit-aware OpenCode activity invalidation (persistent read-only `data_version` generation, file-identity replacement guard, straddle-safe projection, `activity_unstable` unknown on retry exhaustion, terminal detector shutdown on poller close).
- OpenCode mode hides the unsupported Context, 5-hour/weekly, reset, and quota-refresh UI in every view (available, unavailable, stale, Full, Compact); it returns immediately on Codex. Prominent OpenCode titles/tooltips use the localized Active-session label instead of raw session IDs (exact IDs stay in selection, attribution, and analytics).

### Changed
- Settings gains provider tracking selection (default Auto); existing preferences, panel layout, character set and Codex behavior are preserved.

### Fixed
- No waiting/unavailable panel over verified live OpenCode context; no stale Working from same-size updates, same-max deletes, retained-writer WAL commits, replacements, or straddled projections; no detector reopen after shutdown; no late results repainting newer UI.

### Boundaries (unchanged guarantees)
- No combined cross-provider totals; OpenCode Total is a recorded usage total (five stored categories summed, verified 1.18.31/1.18.32 sessions with complete data only — never billed, never context) and stays N/A whenever inputs or version semantics are unverified; unknown stays unknown (never zero-filled); recorded cost has no currency inference or conversion; no quotas, context windows or reset timers for OpenCode.
- Local-only metadata reads (allowlisted columns, no prompts/responses/tool contents/credentials/paths/titles); nothing is uploaded.

## V1.0.0 — 2026-09-17

First formal foundation release of `petoken` (previously Codex Wisp).

### Added
- Transparent Windows desktop pet with the approved idle character plus temporary typing, microphone and music/guitar poses.
- Automatic follow of the active Codex task via Windows accessibility, with optional task pinning and task/project scope.
- Per-second local token usage refresh and official account 5-hour / weekly quota reads with reset countdowns.
- Nullable token accounting: total, input/cache-read/cache-write, uncached input, output, reasoning, derived ratios and a Claude-style comparison view.
- Model, session, daily, 7-day, 30-day and local-recorded-lifetime breakdowns in Token Analytics.
- CAD API-equivalent cost estimate using model/tier pricing and a dated Bank of Canada exchange rate.
- Local-only numeric telemetry parsing; no transcript export, model calls, keystroke content or audio recording.

### Changed
- (First release: no prior versions.)

### Fixed
- (First release: no prior regressions.)

## V1.1.0 — 2026-09-20

UI / interaction refinement, verified against `D:\Desktop\petoken\V1.1.0`, user-accepted and published to GitHub as v1.1.0.

### Added
- Daily / Token modes with debounced transitions and a bound Working Context (project, model, context, session Tokens).
- Global / Project / Conversation scopes; Full / Compact Token formatting with units.
- Simplified Chinese / English UI with live switching; USD / CAD / EUR / CNY Estimated Cost from an internal table.
- Compact two-line Token card; adjacent, resizable companion panel with size persistence; Reset to Defaults.
- V1.1 chibi character set (idle, typing frames, Working, microphone, music, guitar) with shared anchor and DPI-aware rendering; reactive tap typing.
- Music subtitle capability from platform SMTC metadata when provided.
- Adjustable pet character size (50–150%, default 100%) with live Settings preview and anchor-preserving resize.
- Always on Top and panel pinning; pet-relative floating panel that re-docks without moving the pet.
- Intentional Compact layout (cost + token heroes, single control strip) with Compact ↔ Expanded size restoration.
- Free four-edge/four-corner Expanded resizing (420–650 × 400–800) with persisted size.
- Settings About-the-Data section (four numbered items, zh_CN/en).

### Changed
- Larger aspect-preserving 256 x 256 logical-pixel chibi rendering, stable desktop anchor, DPR-aware sprite cache; centralized theme and no manual pricing controls.

### Fixed
- Responsive tall-window spacing, malformed panel-size crash, render-tool Token pose ordering.
- R1–R9 acceptance corrections: topmost/pinned lifecycle, scoped Working status, Conversation token headers, Full-number fitting, stale analytics clearing, and media-free smoke diagnostics.
- Manual-acceptance corrections: Compact layout and Compact ↔ Expanded restore (plus auto-hide grace on toggle).
- The same desktop character remains visible when the panel opens beside it; only dragging saves its position.
