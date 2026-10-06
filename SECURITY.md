# Security

## Design principles

- The Codex and Claude Code integrations read **local task and numeric usage metadata**. They never export transcripts, credentials, prompts, responses, or tool contents, and never upload local usage anywhere.
- Claude Code transcript lines are parsed in memory only to reach numeric usage and session metadata (model, session, start directory, branch, effort, time, title); message content is discarded immediately and never stored, displayed, logged or exported. Liveness comes from Claude Code's own session registry and a read-only process check.
- Optional **Sync Claude usage** (off by default) adds a status-line command to Claude Code's `settings.json` after backing the file up. The command keeps only numbers (usage percentages, reset times, context size and use, model ID) under `%LOCALAPPDATA%\CodexWisp\claude-status`; it never stores conversation content, paths or credentials, and turning it off removes only Petoken's entry. A custom status line is never replaced.
- Optional **Claude instant notifications** (off by default) add asynchronous hooks to Claude Code's `settings.json` after backing it up; existing hooks are kept and turning it off removes only Petoken's. The hook script appends event metadata only (event type, error or notification type, session and prompt IDs, project folder name) to `%LOCALAPPDATA%\CodexWisp\claude-events.jsonl`, never conversation content. Codex approval state is read only from Codex's existing local control sockets. Notification history and reminders stay in `%LOCALAPPDATA%\CodexWisp\notifications.sqlite3` for 30 days.
- Optional **Approve Claude on the pet** (off by default) adds one blocking `PermissionRequest` hook to Claude Code's `settings.json` after backing it up; other hooks are kept and turning it off removes only Petoken's. The hook writes Claude Code's request to `%LOCALAPPDATA%\CodexWisp\claude-approvals` and waits for Petoken's answer; request and answer files are deleted once answered or expired, and a step log keeps only times, short IDs and tool names. If Petoken is not running the hook steps aside at once. "Always allow" rules are written by Claude Code to the project's `.claude/settings.local.json`; Petoken lists the ones it requested and can revoke them.
- Task recaps, reports and predictions read tool names, edited file paths, timestamps and usage numbers from local Claude Code transcripts and Codex rollouts; message text, commands and file contents are not stored.
- Quick launch starts the Claude Code or Codex CLI in a new terminal only when you press Start; the prompt is passed as encoded data, never through a shell, and no permission flags are added.
- While Petoken runs it can mute the Claude desktop app's own Windows notifications (on by default, Settings → Claude). Only that app's entry under the current user's notification settings is changed; the previous value is recorded first and restored on exit.
- **Update check** (on by default, Settings > General): once a day a read-only HTTPS request reads the latest release of windknows-ai/petoken from GitHub; nothing about the computer is sent. An update downloads the installer and `SHA256SUMS.txt` into `%LOCALAPPDATA%\CodexWisp\updates` and is refused unless the hash matches; the installer then runs silently with `/RELAUNCH=1`.
- Optional **Codex instant notifications and approvals** (off by default) add hooks to Codex's `hooks.json` (backed up first; other hooks are kept; Codex asks the user to trust them). Events keep only times, event types, IDs and the project folder name in `%LOCALAPPDATA%\CodexWisp\codex-events.jsonl`; approval requests use the same exchange folder as Claude's and are allow once / deny only.
- Todos handed to AI keep their prompt, folder, model and effort in the local workbench database; launches use the same encoded-data path as quick launch.
- Uncaught errors are written to `%LOCALAPPDATA%\CodexWisp\errors.log` (trimmed). **Export diagnostics** shows its full content before saving; it contains versions, feature states, that log, the approval step log and notification counts, with folder lists reduced to a count.
- The usage overlay checks which apps are open from process image names and paths only (Codex desktop / CLI, Claude desktop / CLI); it never reads window contents.
- Petoken reads exactly Codex and Claude Code. The former OpenCode adapter and its tests were removed in v1.4.0; their history is in git.
- Media titles/artists/subtitle metadata are memory-only for the music display and are never stored.
- The unreleased V1.4 workbench stores only user-entered project names/folder paths,
  todos, plain-text notes and explicit Codex / Claude Code task-to-project links in a separate
  local SQLite database. It does not scan project folders, parse new chat content,
  upload or encrypt these records. Its disposable QA preview never uses this
  personal database. Back up the complete database while Petoken is closed.

## Reporting a vulnerability

If you find a privacy or security issue (e.g. the app reading more than documented, or a release package containing unexpected files), please open a GitHub issue with the `security` label, or contact the maintainer privately via the email listed on the GitHub profile. Do **not** post suspected credentials or personal data in public issues.

## Release integrity

Each GitHub Release lists the installer's SHA-256 hash in `SHA256SUMS.txt`. After downloading, you may verify it before running the installer.
