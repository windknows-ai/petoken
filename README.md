# Petoken

**English** | [简体中文](README.zh-CN.md)

> A Codex and Claude Code desktop companion with local usage and cost intelligence on Windows.
>
> Codex 与 Claude Code 的桌面 AI 编程小伙伴：跟着你的任务，诚实地显示 token 用量、额度和费用。

![Python](https://img.shields.io/badge/Python-3.13-3776AB) ![Windows](https://img.shields.io/badge/Windows-10%2F11-0078D4) ![License](https://img.shields.io/badge/code-MIT-91E4F2)

**Petoken Community** — the free, open-source edition of Petoken. v1.7.0 keeps itself up to date, welcomes new users, takes todos to Claude Code or Codex now or at a set time, and brings Codex notices and approvals onto the character. Since v1.6 it is a time-saving assistant: it predicts when your limits run out, lets you approve Claude Code's requests, answer its questions and accept its plans right on the character, jumps to a task's window in one click, starts new tasks from anywhere and reports what AI did for you today and this week — beside the Codex and Claude Code usage tracking, notifications and local workbench of earlier versions.

## What it does

Petoken is a small Windows desktop companion for Codex and Claude Code. It follows verified tasks of both and shows their token usage and available cost estimates — per conversation, per project, or globally. An approved character idles on your desktop; hover or click it to reveal the usage panel.

- **Codex + Claude Code**: Settings → Tracking provider offers Auto (default), Codex or Claude Code. Codex Stars are blue, Claude Code Stars are gold.
- **Task Stars**: a centered dimensional ring, stable-number pages for more than 8 tasks, persistent decoration and animated task-local details.
- **Task-level live usage**: input / output / reasoning / cache splits for the current task.
- **Quotas and resets**: Codex 5-hour / weekly usage with reset countdowns (Pro accounts have only the weekly window); Claude Code Pro/Max windows after turning on **Settings → Sync Claude usage**.
- **Usage card**: while tasks run, a small card above the character shows, for each open app, the context, 5-hour and weekly amounts left and when they reset.
- **Notifications**: the character cheers, looks sad or waves and a pop-up appears when a task finishes, fails or waits for your approval, or when the 5-hour limit runs low; 30-day history, Do Not Disturb and personal reminders.
- **Predictions and tips** (new in 1.6): when a limit will run out at your current pace, which open app still has room, context almost full, a task with no progress, a used-up limit coming back.
- **Answer Claude on the character** (new in 1.6, opt-in): permission requests (Allow / Always allow / Deny), Claude's multiple-choice questions and its plans (Accept / Accept and allow edits / Revise).
- **Recaps and one-click jump** (new in 1.6): finished-task notices say which files changed, how long it took and what it cost; one click brings the task's window to the front.
- **Quick launch** (new in 1.6): a shortcut opens a small box — what to do, which folder, Claude Code or Codex — and the task starts in a new terminal.
- **Reports** (new in 1.6): today / this week — tasks, AI working time, files changed, tokens and cost — plus a searchable task history.
- **Workbench**: local projects, todos, plain-text notes and reminders, with optional task-to-project links.
- **Cost**: an API-equivalent estimate (USD / CAD / EUR / CNY) only when model pricing and token evidence support it; otherwise `N/A`.
- **Token Analytics**: model / session / date grouping with local lifetime history.
- **Honest unknowns**: unknown model remains Unknown, unavailable numbers remain `N/A`, actual zero remains zero, and partial coverage stays explicit.
- Daily / Token modes, Full / Compact number formats, Simplified Chinese / English UI, pinning, always-on-top, resizable panel, adjustable character size.

## Latest stable release: v2.2.1

Download the **one-click installer** [Petoken-Setup-v2.2.1.exe](https://github.com/windknows-ai/petoken/releases/download/v2.2.1/Petoken-Setup-v2.2.1.exe) from the [v2.2.1 release](https://github.com/windknows-ai/petoken/releases/tag/v2.2.1) and verify its SHA-256 against the release checksum file. Changes are listed in [CHANGELOG.md](CHANGELOG.md).

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

### Notifications

When a task finishes, fails or waits for your approval, or the 5-hour limit
drops to 20 % left, the character reacts and a Windows notification appears;
clicking a waiting-for-approval notice opens that task. Everything is kept for
30 days under **Notifications** in the workbench, beside once / daily / weekly
personal reminders. **Do Not Disturb** (manual or scheduled) silences pop-ups
and reactions while still keeping the history.

| | Claude Code | Codex CLI | Codex desktop app |
| --- | --- | --- | --- |
| Finished | under 1 s* | a few seconds | a few seconds |
| Failed | under 1 s* | — | — |
| Waiting for approval | under 1 s* | a few seconds | — |

\* With **Settings → Claude → Claude instant notifications** on (adds hooks to
Claude Code's settings, backed up first). Without it, finished tasks are noticed
by regular checks. The Codex desktop app does not expose approval or failure
state to other programs, so those stay silent. Background Claude runs that you
did not open yourself (`claude -p`, scripts, agents) are kept in the history
without a pop-up. While Petoken runs, the Claude desktop app's own pop-ups are
muted so you get one notice, not two (Settings → Claude; your setting comes
back when Petoken exits).

### Time-saving assistant (v1.6)

- **Predictions and tips.** From your pace over the last hour (or since the
  window opened) Petoken predicts when the 5-hour and weekly limits run out and
  whether that is before they reset, and suggests the other open app when it
  still has room. It also flags context almost full (time to `/compact`), a
  task with no progress for 20 minutes, and a used-up limit or rate limit that
  has come back. Hints appear as one line in the usage card; each also raises
  one notification. Settings → Assistant → Predictions and tips.
- **Answer Claude on the character** (opt-in: Settings → Claude → Approve
  Claude on the pet). When Claude Code asks for permission, a card beside the
  character offers Allow, Always allow (saved to the project's local settings,
  listed and revocable under Allowed rules), Deny or Answer in Claude. Claude's
  multiple-choice questions and plans get their own cards: pick options or type
  an answer; accept a plan, accept and allow edits, or ask for changes with a
  note. Without an answer (45 s for permissions, 5 minutes for questions and
  plans), or when Petoken is closed, Claude Code asks you itself as usual.
  Works in the CLI and the desktop app's Code tab. Codex does not offer a way
  for other programs to answer yet.
- **Recaps and one-click jump.** Finished-task notices say how many files the
  task changed, how long the turn took and its API-equivalent cost (Codex:
  files). Clicking a notice, or ↗ in a Star's details, raises the window the
  task runs in (Claude desktop, terminal, VS Code; Codex where Codex can match
  it).
- **Quick launch.** Alt+Shift+Space (choose another shortcut or turn it off in
  Settings → Assistant), the character menu or the tray open a small box: what
  to do, a project folder (recent ones offered) and Claude Code or Codex. Start
  opens a new terminal running that CLI on your prompt; the task then shows up
  as a Star. The prompt is passed as data, never through a shell, and no
  permission flags are added.
- **Reports.** Workbench → Reports (also in the character menu) shows today or
  this week: tasks worked on, AI working time (each turn from prompt to last
  reply), files changed, tokens, API-equivalent cost and the change against the
  previous period, followed by a searchable history of Claude sessions and Codex
  threads. Double-click a row to jump to its window.

### New in v2.2: game mode and phone notifications

- **Game mode.** Start a fullscreen game (or switch it on from the menu) and
  she transforms into her second form: she rises, the star ring flies behind
  her, armour forms piece by piece, a sword appears and a spotlight shows her
  off (13 s, or 6 s at double speed). While you play, task notices stay
  quiet (still kept under Notifications), the mouse goes to the game except
  when it is over her, and a compact display shows your limits as small
  rings or a bar with CPU, GPU, temperature and VRAM. Her size in game mode
  has its own setting. Whitelist or blacklist games in Settings > Game mode.
- **Notifications on your phone.** Settings > Phone sends finished, failed,
  waiting-for-you and low-limit notices to the free ntfy app (iOS and
  Android, no account) while you are away from the computer, focusing or
  gaming. Notices name the task as Claude shows it.
- **Also:** the usage card shows only the account limits (5 hours and the
  week) as two larger gauges; focus breaks start when you press OK; the menus
  and settings are reorganised (switches under Show, only the options that
  apply).

### New in v2.0: she comes alive

- **A living character.** Real-time animation: she breathes, blinks, sways,
  hops and squashes; pose changes blend; 32 new full-body poses with their
  own frames (asleep on her stomach, bored with her chin in her hands,
  yawning, peeking, pouting, reading at a desk…). Workbench > Guide lists
  all 41 poses, when each appears, and plays any of them for you.
- **Touch and mood.** Rub her head, poke her, hold the mouse on her to see
  her act cute, drag her around. She greets you in the morning, yawns late
  at night, gets bored, falls asleep when you are away and welcomes you back.
  How much she does on her own follows Clinginess (Quiet / Moderate /
  Clingy), explained in the Guide. A left click no longer opens the panel:
  it is in the right-click menu.
- **Focus with her.** Right-click > Focus: she reads beside you, only urgent
  notices pop up, a countdown with an End button sits under her; afterwards
  a card shows what got done and a break follows (lengths are yours).
- **Projects pick up where you left off.** Start Work opens Claude Code or
  Codex with each project's own settings and your last note; Where I Left Off
  shows your note, the last AI task and unfinished work, and pops up when you
  come back to a project after a while.
- **AI work waits for your review.** A todo the AI finishes is not ticked off
  until you look: Accept, or Redo with what to change.
- **Usage goals, points and stickers.** Weekly token or dollar goals per
  project (she worries at 80%); companionship points and stickers from todos,
  focus and breaks, never from tokens.
- **Reports with charts.** A data board for any day or any of the last weeks,
  and line charts of tokens, cost, AI time and tasks over 7 days, 30 days or
  12 weeks.
- **A new usage card.** Ring gauges for context, 5 hours and the week, amber
  and red as they run low; Codex Pro shows the 5-hour ring as N/A. Optional:
  refresh Claude's limits in the background (Settings > Claude and Codex).
- **Clearer everywhere.** Settings and every workbench page explain
  themselves; a seven-step tutorial; the mouse wheel no longer changes
  drop-downs by accident.

### New in v1.7

- **Updates.** Once a day Petoken reads the latest release from GitHub (a
  read-only request; nothing about your computer is sent). A new version shows
  what changed with Update now / Later / Skip this version; the download is
  used only if its SHA-256 matches the release checksum file, then Petoken
  installs it silently and reopens. Tick "Update automatically" and it updates
  by itself while no task is running. Settings > General.
- **Welcome guide.** A first start walks new users through language, the
  Claude Code and Codex integrations (each with what it changes) and the
  assistant options. People upgrading never see it; reopen it from Settings.
- **Give a todo to AI.** Workbench > Todos > Give to AI…: Claude Code or
  Codex, a folder, a model and effort, now or at a set time. The task is tied
  to the todo; its first real finish ticks it and writes a recap note (an
  interrupted turn does not count). Take back cancels it. Missed times follow
  Settings > Assistant: remind me, or run right away.
- **Codex on the character** (opt-in, Settings > Claude and Codex): Codex
  hooks bring finished and waiting notices at once and Codex permission
  requests as cards (allow once / deny). Codex asks you to trust the hooks
  once with `/hooks`; its approval policy must ask (not `never`). Codex
  questions and plans cannot be answered by other programs yet.
- **Quick launch, upgraded.** Pick the model and effort from each app's own
  live list (Claude Code's model catalog, Codex's model list: new models
  appear and retired ones go by themselves), or tick "Just chat" to talk
  without a project folder.
- **Faster reports, diagnostics, smaller package.** Reports open at once from
  a background cache; Settings > About the data > Export diagnostics saves a
  zip for bug reports after showing everything in it; Pillow is no longer
  shipped.

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
| Claude Code (CLI / desktop Code tab) | Supported | Deduplicated usage totals, API-equivalent cost from Anthropic list prices, working/idle from Claude Code's session registry; 5-hour / weekly limits after turning on **Settings → Sync Claude usage** (Pro/Max, via Claude Code's status line), otherwise N/A |

If a source is missing or stale, its views show that limitation honestly. No other provider is read.

## Install and use

1. Download **Petoken-Setup-v1.7.1.exe** from [GitHub Releases](https://github.com/windknows-ai/petoken/releases/tag/v1.7.1) (v1.7.0 and later update themselves) and run it: click through, no administrator rights needed. It adds a Start menu (and optional desktop) shortcut and an uninstaller under Windows Settings → Apps. Upgrading keeps your settings and workbench.
   - Windows may show "Windows protected your PC" because the installer is not code-signed yet: choose **More info → Run anyway**.
2. Use Codex or Claude Code as usual; Petoken follows their running tasks. In **Settings → Claude** you can turn on Sync Claude usage (quotas), Claude instant notifications and Approve Claude on the pet. The interface starts in English; switch to Simplified Chinese in Settings → General → Language.

Interact: click the character to open the panel; drag to move; right-click for the menu (quick launch, workbench, reports, settings; display options under More); `Alt + Arrow keys` moves the panel.

No administrator rights or system changes are needed. Petoken's Claude Code hooks are per-user PowerShell scripts started with `-ExecutionPolicy Bypass` for that run only, so they work with Windows' default script policy; on managed PCs where Group Policy enforces a script policy they may be blocked, and Claude Code then simply asks as usual.

## Privacy / local-first

- Petoken reads local Codex task metadata and numeric usage events, window task titles and activity state, and memory-only media metadata for the music display. It also reads Claude Code's local session transcripts — numeric usage and session metadata only; message content is discarded in memory — and its live-session registry. No other provider's data is read.
- **Sync Claude usage** is opt-in: it adds a status-line command to Claude Code's settings (backed up first) that keeps only usage numbers. Turn it off in Settings to remove it.
- **Approve Claude on the pet** is opt-in: a hook hands each request to Petoken through files under `%LOCALAPPDATA%\CodexWisp\claude-approvals` that are deleted once answered; a small step log keeps times and tool names only. Recaps, reports and predictions read tool names, file paths, timestamps and usage numbers from local transcripts, never message text or file contents.
- Muting the Claude desktop app's pop-ups changes only that app's entry in your own Windows notification settings and restores it when Petoken exits.
- Never exports transcripts or credentials, never sends model requests, never records audio or keystrokes, never uploads local usage anywhere. The only network requests are the daily update check (GitHub's latest-release record, read only) and, when you choose to update, the installer and checksum download; turn the check off in Settings > General.
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

Build the one-click installer (`dist\Petoken-Setup-v<version>.exe`, needs [Inno Setup 6](https://jrsoftware.org/isinfo.php)):

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\build.ps1 -Installer
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
- v1.7.1 release notes: [`docs/RELEASE_NOTES_v1.7.1.md`](docs/RELEASE_NOTES_v1.7.1.md) (fix); v1.7.0: [`docs/RELEASE_NOTES_v1.7.0.md`](docs/RELEASE_NOTES_v1.7.0.md)
- Previous release notes: [`docs/RELEASE_NOTES_v1.6.0.md`](docs/RELEASE_NOTES_v1.6.0.md), [`docs/RELEASE_NOTES_v1.5.0.md`](docs/RELEASE_NOTES_v1.5.0.md), [`docs/RELEASE_NOTES_v1.4.0.md`](docs/RELEASE_NOTES_v1.4.0.md), [`docs/RELEASE_NOTES_v1.3.0.md`](docs/RELEASE_NOTES_v1.3.0.md)
- Historical v1.2.0 release notes: [`docs/RELEASE_NOTES_v1.2.0.md`](docs/RELEASE_NOTES_v1.2.0.md)

## Community and licensing

Petoken Community is open source. The application source code is MIT-licensed (see [LICENSE](LICENSE)); character artwork is excluded from the MIT grant (see [docs/ARTWORK.md](docs/ARTWORK.md)). Bug reports and ideas are welcome via [GitHub Issues](https://github.com/windknows-ai/petoken/issues) — see [CONTRIBUTING.md](CONTRIBUTING.md). Petoken is an independent project with no affiliation with or endorsement by OpenAI, Anthropic or any game publisher.
