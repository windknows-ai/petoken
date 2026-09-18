# Codex Wisp v1.0.0

This is petoken V1.0.0, released under the former project name Codex Wisp.

First complete Windows release of the Codex usage desktop pet.

## Highlights

- Approved idle character remains the default identity, with temporary typing, microphone and guitar/music poses.
- Stable priority: open usage panel → microphone → music → typing → idle.
- Automatically follows the active Codex desktop task through Windows accessibility; optional task pinning and task/project scope.
- Per-second local usage refresh and official account 5-hour/weekly quota reads with reset countdowns.
- Full nullable token accounting: official total, input, cache read/write, uncached input, output, reasoning, non-reasoning output, derived ratios and comparison view.
- Model, session, daily, today, 7-day, 30-day and local-recorded-lifetime breakdowns.
- CAD API-equivalent cost estimate using model/tier pricing and a dated Bank of Canada exchange rate.
- Local-only numeric telemetry parsing; no transcript export, model calls, keystroke content or audio recording.

## Interaction and behavior

- Hover the pet for roughly 0.35 seconds or click it to show the usage panel; leaving both pet and panel for roughly 0.7 seconds hides it again.
- Drag the pet or the panel to move them; `Alt + 方向键` / `Alt+Arrow` moves the panel.
- Right-click the pet or the tray icon for Settings, full Token Analytics, pause animation, hide, or exit.
- State priority is fixed: open usage panel → microphone in use → music playing → typing → idle. Entry/exit delays prevent pose flicker; only the last key time is recorded — no key content is read or stored.
- Scope can be the current task or the entire project (local records), with optional task pinning.

## Token Analytics

The compact panel keeps Total, Input, Output, Cache hit, New work, Context, 5-hour, Weekly and the CAD estimate. The expanded window additionally shows:

- Raw fields: `input_tokens`, `cached_input_tokens`, `cache_write_input_tokens`, `output_tokens`, `reasoning_output_tokens`, `total_tokens`.
- Derived: uncached input, non-reasoning output, cache-hit ratio, new work, output ratio, reasoning share.
- Comparison-only metric: Claude-style Raw Processed, clearly labelled as a comparison and never replacing the official OpenAI total.
- Grouping: by model, session and local day, plus today, the last 7/30 calendar days and the local recorded lifetime.
- Raw snapshot: the latest `total_token_usage` / `last_token_usage`, including unexplained extra fields.

Cached input is already inside input and reasoning is already inside output, so neither is added to the official total again. Missing or incompletely covered fields display `N/A` and known subtotals rather than fake zeros; see [Token accounting](TOKEN_ACCOUNTING.md) for the full formulas.

## Verification

- 17 unit/UI tests cover nullable accounting, cache/reasoning subsets, resets, forks, duplicates, history, state priority/debounce, hover behavior, quota selection/countdowns and approved assets.
- Independent local JSONL reconciliation confirms session and model totals.
- Source and frozen builds were launched against the installed Codex client; the frozen build followed the active task and returned live quota data.
- Normal and 200% DPI views, all four poses, the compact panel and expanded analytics were visually inspected.

## Known limits

- Local recorded lifetime cannot include deleted or cloud-only records.
- Players must integrate with Windows System Media Transport Controls to trigger the music state.
- Current-task detection depends on the Codex window's Windows Accessibility title; if it is ambiguous, the app falls back to the recent task and the task can be pinned in Settings.
- Context is the latest recorded context ratio; it may differ slightly from the CLI's display after reserving output space.
- The release executable is not code-signed; Windows may show its normal unknown-publisher/SmartScreen prompt on another machine.

## License

The source code is MIT licensed ([LICENSE](../LICENSE)); the character artwork is excluded from that grant. See [Artwork and attribution](ARTWORK.md).

The released V1.0.0 binary was named `CodexWisp.exe`; later releases build as `petoken.exe`.
