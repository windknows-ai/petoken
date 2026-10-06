# Petoken v1.6.0

**Time-saving assistant — human QA of the new cards and reports on 2026-10-06.**

## Highlights

- **Predictions and tips.** Petoken watches your pace and tells you before a
  limit runs out, whether that happens before it resets, and which other open
  app still has room. It also flags context almost full, a task with no
  progress for 20 minutes, and a used-up limit or rate limit that has come
  back. One line in the usage card and one notification each; turn them off in
  Settings → Assistant.
- **Answer Claude on the character** (opt-in, Settings → Claude → Approve
  Claude on the pet). Permission requests, Claude's multiple-choice questions
  and its plans appear as cards beside the character: Allow / Always allow /
  Deny; pick or type answers; Accept / Accept and allow edits / Revise with a
  note. Always-allow rules are saved to the project's local Claude settings and
  can be revoked under Allowed rules. Without an answer in time (45 s, or 5
  minutes for questions and plans), or with Petoken closed, Claude Code asks you
  itself. A card closes by itself when you answer in Claude instead.
- **Recaps and one-click jump.** Finished-task notices show files changed, turn
  time and cost; clicking a notice, ↗ in Star details or a report row brings
  the task's window to the front.
- **Quick launch.** Ctrl+Alt+Space (selectable; a taken shortcut falls back to
  the next free one), the character menu or the tray: write what to do, pick a
  folder and Claude Code or Codex, and it starts in a new terminal.
- **Reports.** Workbench → Reports: today / this week tasks, AI working time,
  files changed, tokens, cost and the change from last period, plus a
  searchable history of Claude sessions and Codex threads.
- **Tidier settings and menus**, one notice instead of two (the Claude desktop
  app's own pop-ups are muted while Petoken runs and restored on exit), quiet
  background Claude runs, and new official Codex model prices.

## Install

Download `Petoken-Setup-v1.6.0.exe` and run it. It installs per user (no
administrator rights), adds Start menu / optional desktop shortcuts and an
uninstaller (Windows Settings → Apps), and upgrades an earlier Petoken in place:
settings, workbench records and history carry over. The installer is not
code-signed yet, so Windows SmartScreen may ask you to choose **More info → Run
anyway**. Verify it against `SHA256SUMS.txt` from the
[GitHub release](https://github.com/windknows-ai/petoken/releases/tag/v1.6.0).

The portable ZIP is no longer published; the installer is the only download.

## Requirements and limits

- No administrator rights or system changes. The Claude Code hooks are per-user
  PowerShell scripts run with `-ExecutionPolicy Bypass` for that run only; on
  managed PCs where Group Policy enforces a script policy they may be blocked,
  and Claude Code then asks as usual.
- Quick launch needs the Claude Code or Codex command-line tool installed.
- Codex does not yet let other programs answer its questions or approvals;
  window jumping for Codex works where Codex can match the window.
- Costs are API-equivalent estimates, not subscription bills;
  `codex-auto-review` has no published price and stays N/A.

## Privacy

Approval requests pass through files under
`%LOCALAPPDATA%\CodexWisp\claude-approvals` that are deleted once answered; a
step log keeps only times, short IDs and tool names. Recaps, reports and
predictions use tool names, file paths, timestamps and usage numbers from local
transcripts, never message text or file contents. Nothing is uploaded. See
[SECURITY.md](../SECURITY.md).

## Verification

The full native regression suite (1150+ tests) passes; the approval flow was
verified end to end with Claude Code 2.1.286 (allow, always allow, deny,
questions and plans in the desktop app). Application code is MIT; character
artwork is excluded from that grant. Petoken is not affiliated with OpenAI,
Anthropic or a game publisher.
