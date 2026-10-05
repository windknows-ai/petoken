# Petoken

> A Codex and Claude Code desktop companion with local usage and cost intelligence on Windows.

*Codex 与 Claude Code 的本机用量与成本桌宠：跟随你的任务，诚实显示 token 用量、额度与费用。*

![Python](https://img.shields.io/badge/Python-3.13-3776AB) ![Windows](https://img.shields.io/badge/Windows-10%2F11-0078D4) ![License](https://img.shields.io/badge/code-MIT-91E4F2)

**Petoken Community** — the free, open-source edition of Petoken. v1.4.0 follows Codex and Claude Code side by side (blue and gold task Stars), shows remaining context and quotas in a small card above the character, and adds a local workbench for projects, todos and notes.

## What it does

Petoken is a small Windows desktop companion for Codex and Claude Code. It follows verified tasks of both and shows their token usage and available cost estimates — per conversation, per project, or globally. An approved character idles on your desktop; hover or click it to reveal the usage panel.

- **Codex + Claude Code**: Settings → Tracking provider offers Auto (default), Codex or Claude Code. Codex Stars are blue, Claude Code Stars are gold.
- **Task Stars**: a centered dimensional ring, stable-number pages for more than 8 tasks, persistent decoration and animated task-local details.
- **Task-level live usage**: input / output / reasoning / cache splits for the current task.
- **Quotas and resets**: Codex 5-hour / weekly usage with reset countdowns (Pro accounts have only the weekly window); Claude Code Pro/Max windows after turning on **Settings → Sync Claude usage**.
- **Usage card**: while tasks run, a small card above the character shows, for each open app, the context, 5-hour and weekly amounts left and when they reset.
- **Workbench**: local projects, todos and plain-text notes, with optional task-to-project links.
- **Cost**: an API-equivalent estimate (USD / CAD / EUR / CNY) only when model pricing and token evidence support it; otherwise `N/A`.
- **Token Analytics**: model / session / date grouping with local lifetime history.
- **Honest unknowns**: unknown model remains Unknown, unavailable numbers remain `N/A`, actual zero remains zero, and partial coverage stays explicit.
- Daily / Token modes, Full / Compact number formats, Simplified Chinese / English UI, pinning, always-on-top, resizable panel, adjustable character size.

## Latest stable release: v1.4.0

Download [Petoken-v1.4.0-Windows-x64.zip](https://github.com/windknows-ai/petoken/releases/download/v1.4.0/Petoken-v1.4.0-Windows-x64.zip) from the [v1.4.0 release](https://github.com/windknows-ai/petoken/releases/tag/v1.4.0). Verify its SHA-256 against the release checksum file. Changes are listed in [CHANGELOG.md](CHANGELOG.md).

## Supported sources

### Codex + Claude Code

Petoken tracks exactly two providers: Codex and Claude Code. Auto follows
whichever provider has a verified working task; task Stars show both at once —
**Codex Stars are blue, Claude Code Stars are gold** — and are named after
their project. Claude Code usage comes from its local session transcripts and
live session registry (CLI and desktop Code tab alike). Context use is measured
against each model's official context window. Claude Code keeps no quota on
disk: its 5-hour / weekly windows appear only after you turn on
**Settings → Sync Claude usage** (claude.ai Pro/Max), which hands Claude Code's
status-line numbers to Petoken; otherwise they read `N/A`.

### Usage card and usage panel

While tasks run, a click-through card above the character shows one block per
open app (Codex desktop or CLI, Claude desktop or CLI): context, 5-hour and
weekly amounts left with reset countdowns. A window the account does not have
is not drawn. Click the character to open the full usage panel. **Usage panel
(always shown)** in the character's right-click menu keeps it open and on top;
it starts unchecked every time Petoken opens.

### Workbench

A native Home / Projects / Todos / Notes workbench opens from the Hub,
character menu or tray. Personal records stay on this device in
`%LOCALAPPDATA%\CodexWisp\workbench.sqlite3`; notes use explicit Save / Ctrl+S
and protect unsaved drafts on navigation or exit. Codex and Claude Code tasks
can be linked to projects. A skippable Chinese/English first-use tutorial
explains the pet and the workbench.

### Source status

| Source | Status | What you get |
| --- | --- | --- |
| Codex desktop client and CLI | Supported | Verified usage totals, available 5-hour / weekly quotas with resets, supported API-equivalent cost, working/idle context |
| Claude Code (CLI / desktop Code tab) | Supported since v1.4.0 | Deduplicated usage totals, API-equivalent cost from Anthropic list prices, working/idle from Claude Code's session registry; 5-hour / weekly limits after turning on **Settings → Sync Claude usage** (Pro/Max, via Claude Code's status line), otherwise N/A |

If a source is missing or stale, its views show that limitation honestly. No other provider is read.

## Install and use

1. Download `Petoken-v1.4.0-Windows-x64.zip` from [GitHub Releases](https://github.com/windknows-ai/petoken/releases/tag/v1.4.0).
2. Extract the **entire folder** and run `petoken.exe` (`_internal` is part of the program — do not copy the exe alone).
3. Use Codex or Claude Code as usual; Petoken follows their running tasks. Optionally turn on **Settings → Sync Claude usage** for Claude quotas. For an isolated demonstration of both providers, run `preview-v1.5.cmd` (`preview-workbench.cmd` for the workbench); their data is synthetic and they do not save your settings.

Interact: click the character to open the panel; drag to move; right-click for the menu; `Alt + Arrow keys` moves the panel.

## Privacy / local-first

- Petoken reads local Codex task metadata and numeric usage events, window task titles and activity state, and memory-only media metadata for the music display. It also reads Claude Code's local session transcripts — numeric usage and session metadata only; message content is discarded in memory — and its live-session registry. No other provider's data is read.
- **Sync Claude usage** is opt-in: it adds a status-line command to Claude Code's settings (backed up first) that keeps only usage numbers. Turn it off in Settings to remove it.
- Never exports transcripts or credentials, never sends model requests, never records audio or keystrokes, never uploads local usage anywhere.
- Details: [`docs/USAGE_MODEL.md`](docs/USAGE_MODEL.md) and [`SECURITY.md`](SECURITY.md).

## Build and test from source

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe widget.py
```

Run the test suite:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Build the Windows package (`dist\petoken\` plus `dist\petoken-Windows-x64.zip`):

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\build.ps1 -Package
```

## Documentation

- Usage semantics (what is counted, what `N/A` means): [`docs/USAGE_MODEL.md`](docs/USAGE_MODEL.md)
- Current Codex scope and historical provider records: [`docs/PROVIDERS.md`](docs/PROVIDERS.md)
- Token formulas and fields: [`docs/TOKEN_ACCOUNTING.md`](docs/TOKEN_ACCOUNTING.md)
- Product roadmap: [`ROADMAP.md`](ROADMAP.md)
- Interface design contract: [`DESIGN.md`](DESIGN.md)
- Character artwork and attribution: [`docs/ARTWORK.md`](docs/ARTWORK.md)
- Security policy: [`SECURITY.md`](SECURITY.md)
- Contributing: [`CONTRIBUTING.md`](CONTRIBUTING.md)
- Third-party components: [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)
- v1.4.0 release notes: [`docs/RELEASE_NOTES_v1.4.0.md`](docs/RELEASE_NOTES_v1.4.0.md)
- Visual QA checklist (human accepted): [`docs/V1_5_DUAL_PROVIDER_QA.md`](docs/V1_5_DUAL_PROVIDER_QA.md)
- Previous release notes: [`docs/RELEASE_NOTES_v1.3.0.md`](docs/RELEASE_NOTES_v1.3.0.md)
- Historical v1.2.0 release notes: [`docs/RELEASE_NOTES_v1.2.0.md`](docs/RELEASE_NOTES_v1.2.0.md)

## Community and licensing

Petoken Community is open source. The application source code is MIT-licensed (see [LICENSE](LICENSE)); character artwork is excluded from the MIT grant (see [docs/ARTWORK.md](docs/ARTWORK.md)). Bug reports and ideas are welcome via [GitHub Issues](https://github.com/windknows-ai/petoken/issues) — see [CONTRIBUTING.md](CONTRIBUTING.md). Petoken is an independent project with no affiliation with or endorsement by OpenAI or any game publisher.
