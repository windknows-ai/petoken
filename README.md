# Petoken

> Local usage & cost intelligence for AI coding agents on Windows.

*AI 结对编程的本机用量与成本桌宠：跟随你当前打开的任务，诚实显示 token 用量、额度与费用。*

![Python](https://img.shields.io/badge/Python-3.13-3776AB) ![Windows](https://img.shields.io/badge/Windows-10%2F11-0078D4) ![License](https://img.shields.io/badge/code-MIT-91E4F2)

**Petoken Community** — the free, open-source edition of Petoken. This public repository contains the complete application source for the released version below.

## What it does

Petoken is a small Windows desktop companion. It follows your active AI coding task and shows, on demand, that task's token usage and cost — per conversation, per project, or globally. An approved character idles on your desktop; hover or click it to reveal the usage panel.

- **Dual-provider tracking**: Codex and OpenCode, via Auto (working-first), Codex-only, or OpenCode-only tracking, switchable in Settings.
- **Task-level live usage**: input / output / reasoning / cache splits for the current task.
- **Quotas and resets** (Codex): official 5-hour / weekly usage with reset countdowns.
- **Cost**: Codex shows an API-equivalent estimate (USD / CAD / EUR / CNY); OpenCode shows its own recorded amount (currency unknown, never converted).
- **Token Analytics**: model / session / date grouping with local lifetime history.
- **Honest unknowns**: anything unverified renders as `N/A` — never zero-filled, never invented, never summed across providers.
- Daily / Token modes, Full / Compact number formats, Simplified Chinese / English UI, pinning, always-on-top, resizable panel, adjustable character size.

## Latest stable release: v1.2.0

Download the Windows x64 package from [GitHub Releases](https://github.com/windknows-ai/petoken/releases) (`Petoken-v1.2.0-Windows-x64.zip`). Changes are listed in [CHANGELOG.md](CHANGELOG.md).

## Supported providers

| Source | Status | What you get |
| --- | --- | --- |
| Codex desktop client | Available now | Official totals, 5-hour / weekly quotas with resets, API-equivalent cost, working/idle context |
| OpenCode 1.18.31 / 1.18.32 | Available now | Five raw usage categories plus a recorded Total on verified complete data, recorded cost (currency unknown); no quotas or context — those UI areas stay hidden rather than fabricated |

If a source is missing, its views honestly show unavailable without affecting the other provider.

## Install and use

1. Download `Petoken-v1.2.0-Windows-x64.zip` from [GitHub Releases](https://github.com/windknows-ai/petoken/releases).
2. Extract the **entire folder** and run `petoken.exe` (`_internal` is part of the program — do not copy the exe alone).
3. Keep the selected source running: the Codex desktop client for Codex tracking, or OpenCode for OpenCode tracking (live Working state needs an active task).

Interact: hover about 0.35 s or click the character to open the panel, move away about 0.7 s to hide it; drag to move; right-click for the menu; `Alt + Arrow keys` moves the panel.

## Privacy / local-first

- Reads local numeric usage metadata only: Codex task metadata and usage events, OpenCode session metadata through an allowlisted column set (no titles, message bodies, tool parameters, credentials, or share links), window task titles and activity state, and memory-only media metadata for the music display.
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
- Provider architecture and verified capabilities: [`docs/PROVIDERS.md`](docs/PROVIDERS.md)
- Token formulas and fields: [`docs/TOKEN_ACCOUNTING.md`](docs/TOKEN_ACCOUNTING.md)
- Product roadmap: [`ROADMAP.md`](ROADMAP.md)
- Interface design contract: [`DESIGN.md`](DESIGN.md)
- Character artwork and attribution: [`docs/ARTWORK.md`](docs/ARTWORK.md)
- Security policy: [`SECURITY.md`](SECURITY.md)
- Contributing: [`CONTRIBUTING.md`](CONTRIBUTING.md)
- Third-party components: [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)
- v1.2.0 release notes: [`docs/RELEASE_NOTES_v1.2.0.md`](docs/RELEASE_NOTES_v1.2.0.md)
- Unreleased V1.3 visual QA checklist (acceptance pending): [`docs/V1_3_VISUAL_QA.md`](docs/V1_3_VISUAL_QA.md)

## Community and licensing

Petoken Community is open source. The application source code is MIT-licensed (see [LICENSE](LICENSE)); character artwork is excluded from the MIT grant (see [docs/ARTWORK.md](docs/ARTWORK.md)). Bug reports and ideas are welcome via [GitHub Issues](https://github.com/windknows-ai/petoken/issues) — see [CONTRIBUTING.md](CONTRIBUTING.md). Petoken is an independent project with no affiliation with or endorsement by OpenAI, OpenCode, or any game publisher.
