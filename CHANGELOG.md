# Changelog

Concise summaries of released versions. Version-specific detail lives in the release documentation; do not turn this file into full technical documentation.

## V1.6.0 — 2026-10-06

Time-saving assistant; human QA of the new cards and reports on 2026-10-06.

### Added
- **Predictions and tips**: when the 5-hour / weekly limit runs out at your pace and whether before it resets, a switch suggestion to the open app with room, context almost full, no progress for 20 minutes, a used-up limit coming back. One line in the usage card plus one notification each.
- **Answer Claude on the character** (opt-in): permission requests (Allow / Always allow / Deny / Answer in Claude, with revocable always-allow rules), Claude's multiple-choice questions and its plans (Accept / Accept and allow edits / Revise with a note). Claude Code asks itself when there is no answer in time or Petoken is closed.
- **Recaps** on finished-task notices (files changed, turn time, cost) and **one-click jump** to a task's window from notices, Star details and reports.
- **Quick launch**: a global shortcut (selectable), the character menu or the tray start Claude Code or Codex on a prompt in a new terminal.
- **Reports** in the workbench: today / this week with tasks, AI working time, files changed, tokens, cost and the change from the previous period; searchable task history for both apps.
- Prices for gpt-6.1-sol, gpt-6-sol, gpt-6-luna and gpt-5.5 (official, checked 2026-10-06).

### Changed
- Settings is split into General / Tasks / Claude / Assistant / About tabs; the character and tray menus keep everyday actions on top and the rest under More.
- While Petoken runs the Claude desktop app's own pop-ups are muted (restored on exit), and background Claude runs (`claude -p`, scripts, agents) finish quietly in the history.
- Installed Claude Code hooks are brought up to date when Petoken starts.
- Releases ship the one-click installer only.

### Fixed
- Approval cards that outlived their request (answered in Claude, session closed) disappear instead of reappearing on the next start.
- Dark focus frame on report and allowed-rules rows.

See [release notes](docs/RELEASE_NOTES_v1.6.0.md).

## V1.5.0 — 2026-10-05

Notifications and reminders (roadmap phase "1.6 reminders and notifications"); human visual QA accepted on 2026-10-05.

### Added
- Notifications when a task finishes, fails or waits for your approval, and when the 5-hour limit drops to 20 % left: the character cheers, looks sad or waves (new artwork) and a Windows notification appears.
- Opt-in **Claude instant notifications**: Claude Code hooks deliver finished / failed / waiting events in under a second (CLI and desktop Code tab).
- Codex: finished tasks by regular checks; waiting-for-approval for Codex CLI tasks from Codex's own control socket. The Codex desktop app does not expose these states.
- Workbench **Notifications** tab: 30-day history with type colours and filter; once / daily / weekly personal reminders that can link a todo.
- **Do Not Disturb**, manual or scheduled (default 22:00–08:00).

### Changed
- Todos, notes and reminders are added through a dialog (Add → write → confirm), like projects; workbench lists separate rows with dividers.
- Only a pending approval opens its task from a notification; the rest is history.
- Settings opens on its own without opening the usage panel.

### Fixed
- Dark focus frame on clicked workbench rows; the notification list jumping to the top after a double-click.

See [release notes](docs/RELEASE_NOTES_v1.5.0.md).

## V1.4.0 — 2026-10-05

Codex + Claude Code companion with a usage card and a local workbench. Combines the work developed under the V1.4 (workbench) and V1.5 (dual provider) working names; human visual QA accepted on 2026-10-05.

### Added
- Claude Code as a second provider (CLI and desktop Code tab): deduplicated usage, API-equivalent cost from Anthropic list prices, official context windows, working/idle from Claude Code's session registry. Tracking choice Auto / Codex / Claude Code.
- Gold Claude Code Stars beside blue Codex Stars; the ring, beads and trails take the colour of the nearest Stars.
- Usage card above the character while tasks run: context, 5-hour and weekly amounts left with reset countdowns for each open app; readable at every character size.
- Opt-in **Sync Claude usage** setting for Claude Pro/Max 5-hour / weekly windows via Claude Code's status line (backs up Claude Code's settings first; never replaces a custom status line).
- Native workbench: Home / Projects / Todos / Notes, task-to-project links for both providers, first-use tutorial.
- Codex compatibility notice when a Codex version's data is only partly understood.

### Changed
- Task Stars, details, the Hub task menu and the workbench name tasks after their project.
- The usage panel opens on click and always starts closed; **Usage panel (always shown)** in the character menu keeps it open and on top for the session.
- Codex Pro accounts show only the weekly window (5-hour reads N/A).
- Settings upgrade once from the Codex-only provider choice to Auto; the workbench database upgrades once to schema 2 with a full backup.

### Fixed
- Settings changes not saving, the Hub close button, oversized tooltips, Hub overlapping an open Star detail, and Codex CLI sessions not being detected.

See [release notes](docs/RELEASE_NOTES_v1.4.0.md).

## V1.3.0 — 2026-10-04

Codex-only desktop companion. Includes the user-accepted visual/interaction refinements developed under the V1.4 working name; published as v1.3.0 by user request.

### Added
- Compact tilted star ring with front/back depth, luminous crystal Stars, pearl/violet/champagne arcs and longer tapered trails.
- Stable task numbers and pages of up to 8 Stars, with all tasks reachable through the Hub and off-page detail selection.
- Smooth 220 ms task-detail open/close animation with continuous reversal and immediate reduced-motion behavior.
- Explicit star-ring setting, independent of Hub visibility; isolated preview exposes original idle, typing, working, microphone and music artwork.

### Changed
- Codex is the sole supported runtime provider. Alternate-provider selection/polling is removed; the historical OpenCode adapter is excluded from the Windows executable.
- Hub overview and task-local details preserve source/scope identity and explicit Unknown, N/A, zero and partial coverage.

### Fixed
- Pet/ring drift and screen-edge stalls, stale ring geometry after resize, front-plane occlusion after native pet raises, and disappearing decoration on Hub interaction.
- Off-page task lifecycle, stale/retired detail snapshots, workarea changes while motion is disabled and pager overlap/transparent backing.
- Provider publication/shutdown races, task projection responsiveness, malformed timestamps, large token formatting and privacy-safe labels.

See [release notes](docs/RELEASE_NOTES_v1.3.0.md) for installation, verification and supported limits.

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
