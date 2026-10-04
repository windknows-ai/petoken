# Petoken

> A Codex desktop companion with local usage and cost intelligence on Windows.

*专属于 Codex 的本机用量与成本桌宠：跟随你的任务，诚实显示 token 用量、额度与费用。*

![Python](https://img.shields.io/badge/Python-3.13-3776AB) ![Windows](https://img.shields.io/badge/Windows-10%2F11-0078D4) ![License](https://img.shields.io/badge/code-MIT-91E4F2)

**Petoken Community** — the free, open-source edition of Petoken. v1.3.0 is a Codex-only companion with a dimensional task ring and animated task details. The visual refinements previously developed under the V1.4 working name are included in v1.3.0, following human acceptance.

## What it does

Petoken is a small Windows desktop companion for Codex. It follows verified Codex tasks and shows their token usage and available cost estimates — per conversation, per project, or globally. An approved character idles on your desktop; hover or click it to reveal the usage panel.

- **Codex-only tracking**: the current application reads Codex metadata; no alternate provider or mixed-provider mode is selectable.
- **Task Stars**: a centered dimensional ring, stable-number pages for more than 8 tasks, persistent decoration and animated task-local details.
- **Task-level live usage**: input / output / reasoning / cache splits for the current task.
- **Quotas and resets** (Codex): official 5-hour / weekly usage with reset countdowns.
- **Cost**: an API-equivalent estimate (USD / CAD / EUR / CNY) only when model pricing and token evidence support it; otherwise `N/A`.
- **Token Analytics**: model / session / date grouping with local lifetime history.
- **Honest unknowns**: unknown model remains Unknown, unavailable numbers remain `N/A`, actual zero remains zero, and partial coverage stays explicit.
- Daily / Token modes, Full / Compact number formats, Simplified Chinese / English UI, pinning, always-on-top, resizable panel, adjustable character size.

## Latest stable release: v1.3.0

Download [Petoken-v1.3.0-Windows-x64.zip](https://github.com/windknows-ai/petoken/releases/download/v1.3.0/Petoken-v1.3.0-Windows-x64.zip) from the [v1.3.0 release](https://github.com/windknows-ai/petoken/releases/tag/v1.3.0). Verify its SHA-256 against the release checksum file. Changes are listed in [CHANGELOG.md](CHANGELOG.md).

## Supported source

| Source | Status | What you get |
| --- | --- | --- |
| Codex desktop client | Supported in v1.3.0 | Verified usage totals, available 5-hour / weekly quotas with resets, supported API-equivalent cost, working/idle context |

If the Codex source is missing or stale, its views show that limitation honestly. Historical v1.2.0 provider behavior is recorded in its release notes; alternate-provider tracking is no longer part of the current product.

## Install and use

1. Download `Petoken-v1.3.0-Windows-x64.zip` from [GitHub Releases](https://github.com/windknows-ai/petoken/releases/tag/v1.3.0).
2. Extract the **entire folder** and run `petoken.exe` (`_internal` is part of the program — do not copy the exe alone).
3. For Codex tracking, keep the Codex desktop client running (live Working state needs a verified active task). For an isolated demonstration, run `preview-v1.3.cmd`; its tasks are synthetic and it does not save your settings.

Interact: hover about 0.35 s or click the character to open the panel, move away about 0.7 s to hide it; drag to move; right-click for the menu; `Alt + Arrow keys` moves the panel.

## Privacy / local-first

- Petoken reads local Codex task metadata and numeric usage events, window task titles and activity state, and memory-only media metadata for the music display. It does not read alternate-provider stores.
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
- v1.3.0 release notes: [`docs/RELEASE_NOTES_v1.3.0.md`](docs/RELEASE_NOTES_v1.3.0.md)
- Visual QA checklist (human accepted): [`docs/V1_3_VISUAL_QA.md`](docs/V1_3_VISUAL_QA.md)
- Historical v1.2.0 release notes: [`docs/RELEASE_NOTES_v1.2.0.md`](docs/RELEASE_NOTES_v1.2.0.md)

## Community and licensing

Petoken Community is open source. The application source code is MIT-licensed (see [LICENSE](LICENSE)); character artwork is excluded from the MIT grant (see [docs/ARTWORK.md](docs/ARTWORK.md)). Bug reports and ideas are welcome via [GitHub Issues](https://github.com/windknows-ai/petoken/issues) — see [CONTRIBUTING.md](CONTRIBUTING.md). Petoken is an independent project with no affiliation with or endorsement by OpenAI or any game publisher.
