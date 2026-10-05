# Petoken v1.4.0

**Codex + Claude Code Windows desktop companion — human visual QA accepted on 2026-10-05.**
This release combines the work developed under the V1.4 (workbench) and V1.5
(dual provider) working names.

## Highlights

- **Claude Code support** beside Codex (CLI and the desktop app's Code tab):
  deduplicated token usage, API-equivalent cost from Anthropic list prices,
  official context windows and working/idle state from Claude Code's own
  session registry. Settings → Tracking provider: Auto (default), Codex or
  Claude Code.
- **Blue and gold Stars**: Codex tasks are blue, Claude Code tasks gold; the
  ring, beads and trails blend toward the nearest Stars. Stars, details, the
  Hub task menu and the workbench are named after each task's project.
- **Usage card** above the character while tasks run: for each open app,
  context, 5-hour and weekly amounts left with reset countdowns. Codex Pro
  accounts have no 5-hour window, so that row is not drawn (the Hub shows N/A).
  The card stays readable at small character sizes and never blocks clicks.
- **Sync Claude usage** (opt-in, Settings): Claude Code keeps no quota on disk
  and shares its 5-hour / weekly windows only with a status-line command.
  Turning this on backs up Claude Code's `settings.json` and adds Petoken's
  status line; it never replaces a custom status line and is removed when
  turned off. Only numbers are kept. Needs a claude.ai Pro/Max account. The
  status line is a Claude Code terminal feature; the desktop app's Code tab
  did not run it during QA, so desktop-only users may keep N/A.
- **Workbench**: Home / Projects / Todos / Notes with explicit saving, draft
  protection, task-to-project links for both providers and a first-use guide.
- **Usage panel** opens on click and always starts closed; **Usage panel
  (always shown)** in the character menu keeps it open and on top.

## Install

Download `Petoken-v1.4.0-Windows-x64.zip` and `SHA256SUMS.txt` from the
[GitHub release](https://github.com/windknows-ai/petoken/releases/tag/v1.4.0).
Verify the ZIP's SHA-256, then extract the entire folder to a new location and
run `petoken.exe`; keep `_internal` alongside it.

Existing settings upgrade once from the Codex-only provider choice to Auto.
The workbench database upgrades once to schema 2 and keeps a full backup of
the previous file beside it. A new installation starts in English (Simplified
Chinese is in Settings → Language); an existing language choice is kept. The
download contains only the program, its licences and user documents.

## Privacy

Claude Code transcripts are parsed in memory only for numeric usage and session
metadata; message content is discarded. App detection for the usage card uses
process image names and paths only. No credentials are read, no model requests
are sent and nothing is uploaded. See [SECURITY.md](../SECURITY.md) and
[usage semantics](USAGE_MODEL.md).

## Verification and limits

1091 native regression tests pass, including frozen-package preview checks.
The maintainer accepted visual and functional QA on 2026-10-05. API-equivalent
cost remains an estimate, not a bill. Claude quotas depend on the opt-in sync
and on Claude Code running its status line. Application code is MIT; character
artwork is excluded from that grant. Petoken is not affiliated with OpenAI,
Anthropic or a game publisher.
