# Petoken v1.5.0

**Notifications and reminders — human visual QA accepted on 2026-10-05.**
This release delivers the roadmap phase called "1.6 reminders and notifications".

## Highlights

- **Know when a task needs you.** When a Codex or Claude Code task finishes,
  fails or waits for your approval, or the 5-hour limit drops to 20 % left,
  the character cheers, looks sad or waves (new artwork) and a Windows
  notification appears. Clicking a waiting-for-approval notice opens that task.
- **Claude instant notifications** (opt-in, Settings): Claude Code hooks report
  finished, failed and waiting turns in under a second, in the CLI and the
  desktop app's Code tab. Claude Code's `settings.json` is backed up first,
  your own hooks are kept, and turning it off removes only Petoken's hooks.
  The Claude desktop app also shows its own completion notices; turn those off
  in the Claude app if you want only Petoken's.
- **Codex**: finished tasks are noticed by regular checks within a few seconds.
  Waiting-for-approval works for Codex CLI tasks through Codex's own control
  socket. The Codex desktop app does not expose approval or failure state to
  other programs, so those stay silent rather than guessed.
- **Notifications tab** in the workbench: 30-day history with a colour per type
  and a filter; once / daily / weekly personal reminders that can link a todo.
- **Do Not Disturb**, manual or scheduled (default 22:00–08:00): no pop-ups or
  reactions, history still recorded.
- Workbench polish: todos, notes and reminders are added through a dialog, rows
  are separated by dividers, and the focus frame on clicked rows is gone.

## Install

Download `Petoken-v1.5.0-Windows-x64.zip` and `SHA256SUMS.txt` from the
[GitHub release](https://github.com/windknows-ai/petoken/releases/tag/v1.5.0).
Verify the ZIP's SHA-256, extract the entire folder and run `petoken.exe`;
keep `_internal` alongside it. Settings, workbench records and history from
v1.4.0 carry over.

## Privacy

Hooks record event metadata only (event type, error or notification type,
session and prompt IDs, project folder name), never conversation content.
History and reminders stay on this device. See [SECURITY.md](../SECURITY.md).

## Verification

The full native regression suite passes and the release package was smoke
tested. Application code is MIT; character artwork is excluded from that grant.
Petoken is not affiliated with OpenAI, Anthropic or a game publisher.
