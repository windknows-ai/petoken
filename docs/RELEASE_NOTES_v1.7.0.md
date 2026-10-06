# Petoken v1.7.0

**Updates, onboarding, todos handed to AI, Codex on the character — human QA on 2026-10-06.**

## Highlights

- **Stays up to date.** Once a day Petoken reads GitHub's latest-release
  record (read only; nothing about your computer is sent). A new version shows
  what changed: Update now, Later, or Skip this version. The installer is used
  only if its SHA-256 matches the release's `SHA256SUMS.txt`; Petoken then
  installs it silently and reopens, keeping settings and data. "Update
  automatically" lets it do this by itself while no task is running.
- **Welcome guide** for new users: language, the Claude Code and Codex
  integrations (each explaining what it changes) and the assistant options.
  Upgrading users never see it; reopen it from Settings > General.
- **Give a todo to AI.** Hand a todo to Claude Code or Codex with a folder,
  model and effort, now or at a set time. The resulting task is matched to the
  todo; its first real finish ticks the todo and writes a recap note with the
  files changed, time and cost. A turn you interrupted does not count. Take back
  cancels it; a task that never starts is flagged after 15 minutes; missed times
  remind you or run right away (your choice).
- **Codex on the character** (opt-in, Settings > Claude and Codex): instant
  finished and waiting notices, and Codex permission requests as cards (allow
  once / deny). Trust the hooks once in Codex with `/hooks`; Codex's approval
  policy must ask (not `never`) for approvals to appear.
- **Quick launch** offers the model and effort from each app's own live list,
  so new models show up and retired ones disappear by themselves, and a "Just
  chat" mode without a project folder.
- **Faster reports** (background cache), **Export diagnostics** for bug reports
  (you see everything before it is saved), and a smaller installer: Pillow is
  no longer shipped (this also clears the 18 Dependabot alerts).

## Install

Download `Petoken-Setup-v1.7.0.exe` and run it: per user, no administrator
rights, upgrades in place (settings, workbench and history carry over; the
workbench database is migrated once with a backup beside it). SmartScreen may
ask for **More info → Run anyway** because the installer is not code-signed
yet. Verify it against `SHA256SUMS.txt` from the
[GitHub release](https://github.com/windknows-ai/petoken/releases/tag/v1.7.0).
From v1.7.0 on, Petoken can update itself.

## Limits

- Codex questions (request_user_input) and plans cannot be answered by other
  programs yet; Codex has no failure hook, so failures still come from regular
  checks. Codex approvals were verified in the CLI; the Codex desktop app and
  VS Code rely on the same hooks.
- Interrupt detection for todos covers Claude Code; an interrupted Codex turn
  may still count as finished.
- Hooks are per-user PowerShell scripts; on managed PCs where Group Policy
  enforces a script policy they may be blocked and the apps then ask as usual.

## Privacy

The update check and update download are the only network requests. Codex
hook events keep only times, event types, IDs and the project folder name.
Diagnostics exports contain versions, feature states, the error log, the
approval step log and notification counts, never conversation or file
contents. See [SECURITY.md](https://github.com/windknows-ai/petoken/blob/v1.7.0/SECURITY.md).

## Verification

The full native regression suite (1230+ tests) passes. Application code is
MIT; character artwork is excluded from that grant. Petoken is not affiliated
with OpenAI, Anthropic or a game publisher.
