# Claude progress

## Current state — V1.5 dual provider (branch `claude/v1.5-dual-provider`, from `e529ddb`)

Codex compatibility layer (`cd637e1`) merged as `116fb9a`; compatibility notice and V1.5 preview added in `3809953`. Full suite after merge: 1042 tests, all pass. **Maintainer visual QA accepted 2026-10-05; release not yet authorized.**

- Package: `D:\Documents\ChatGPT\petoken-takeover-backups\2026-10-05-v1.5-dual-provider\package-dev\petoken\` — launcher `preview-v1.5.cmd`, checklist `V1_5_DUAL_PROVIDER_QA.md`. EXE SHA256 `4f5fd593954820191833f9fe0142eb3ab42d1605d5532881f37f446ed7bac553`; ZIP `13c939a8240ae642d2478530bf763a687e542741673a1e55815657487aa8d5de` (rebuilt from `5d2fa96`). Frozen captures: `frozen-ring.png` (ring gradient), `frozen-avoid.png` (Hub clear of an open star detail).
- **Final optimization (`00d56f7`), awaiting maintainer QA.** Package: `D:\Documents\ChatGPT\petoken-takeover-backups\2026-10-05-v1.5-dual-provider\package-final\petoken\` (built separately because the `package-dev` build was running). EXE SHA256 `cc85afe1605a6b350784e5e6085c6f7f3aa81eff98b77d0e5ec95055edd20ba0`; ZIP `bf1c88196fd461b31c3a227955ecee4559dea6df79888ffb9a6f13c5ece4af94`. Full suite 1088 tests: all pass except one Windows temp-file lock flake in `test_ui.MultiTaskIntegrationTests` (passes 3/3 alone).
  - Stars/detail/Hub menu/workbench named by project (`Project · n` for duplicates; numbered fallback when unknown).
  - `usage_overlay.py`: click-through card above the pet in Token Mode, one block per open app (`desktop.running_apps`, background `UsagePresence`, 3 s), rows context / 5h / week with remaining + reset; missing window = no row (Codex Pro). Overlay is created lazily (eager creation in every test pet crashed the long suite).
  - `claude_statusline.py`: opt-in Settings toggle "同步 Claude 用量"; installs `%LOCALAPPDATA%\CodexWisp\claude-statusline.ps1`, sets `statusLine` (backup, never replaces a foreign one). Snapshots in `...\CodexWisp\claude-status\`; `PETOKEN_CLAUDE_HOME` isolates them in tests. Enabled on the maintainer's machine 2026-10-05 (backup `~/.claude/settings.json.petoken-backup-20261005-135504`). The desktop Code tab wrote **no** snapshot during this session — needs a terminal `claude` session (or a new desktop session) to confirm.
- Codex compatibility notice: Hub connection label appends 部分兼容 / Partly compatible (or 格式无法识别) when `payload['compatibility']['status']` is partial/unsupported; tooltip lists version and reasons. On this machine Codex 0.156.1 reports partial (`partial_usage_history`, `unknown_quota_structure`).

- `claude_usage.py`: Claude Code adapter. Reads `~/.claude/projects/**/*.jsonl` incrementally (complete lines only), dedupes repeated usage by `message.id`, skips `<synthetic>`, maps Anthropic usage into the shared token schema, prices via `pricing.estimate_claude_usd`. Liveness from `~/.claude/sessions/<pid>.json` (`busy` + same pid and creation time alive). Session project = its start directory. Content never retained.
- Registry: Codex + Claude Code only. Tracking choices Auto (default) / Codex / Claude Code. Settings schema 2 migrates the forced `codex` of Codex-only builds to Auto once.
- Poller: one daemon lane per provider; Claude failures never touch the Codex lane or its reset fence. Auto unions both providers' stars; a pinned task routes the Hub to its own provider (`claude:`-scoped keys).
- UI: Codex stars blue, Claude stars gold; provider chooser visible in Settings; Hub/pet/connection labels name the selected provider; Claude quota/context rows read N/A with "No limits from this source".
- Workbench lists both providers' tasks; project links stay Codex-only until the workbench DB gets a versioned migration (its `task_links` table has `CHECK (provider_id = 'codex')`).
- Preview tool: `--provider mixed|codex|claude` (default mixed).
- Tests (before merge): full suite 1013 run, all pass after updating Codex-only boundary assertions to the V1.5 contract and the stale 500×500 Hub test to the fixed 440×720 Hub. New `tests/test_claude_usage.py` (21 tests) plus a workbench link test.
- Verified against real data: Auto selects the working Claude session, Codex source stays readable.

## Next

- [x] Merged `codex/v1.5-codex-compat` (only Codex files touched; full suite passes) and surfaced its compatibility status in the Hub.
- [x] Built the isolated package for visual QA.
- [x] QA round 1 fixes (`cb52d3b`): preview Settings save (synthetic poller rejected `mark_provider`), pinned-Hub X now closes + unpins with a pointing cursor, ring and trails tinted by nearby star colours (blue/gold, meeting through lavender).
- [x] QA round 2 (`01a58e5`): Hub steps aside from an open star detail and returns on close (unless dragged); task-follow and workbench text name both providers.
- [x] Maintainer visual QA accepted on 2026-10-05 (package from `01a58e5`).
- [x] Round 3 after acceptance: workbench schema-2 migration (Claude links, backup + rollback), Claude context from official windows, Token Analytics for Claude, ornament/guide/trail tint (`f6c885b`); workbench three-tier buttons, provider dots, provider-neutral wording (`b14ab8f`, `d169610`).
- [x] Codex CLI/exec task detection (`12919b8`) merged as `f8e37ca`; full suite 1065 pass.
- [x] Tooltip fix (`5d2fa96`): unscoped per-widget style sheets leaked into Qt tooltips (total help at 30px); scoped by object name. Claude total help text; Hub model label no longer collapses to an ellipsis. Full suite 1068 pass.
- [ ] Maintainer re-check of round 3 + live Codex CLI detection.
- [ ] Release decision pending: merge to main, version bump (APP_VERSION still 1.3.0), release notes, publication — each needs explicit authorization.

## Open questions for the maintainer

- Combined (Codex + Claude) total view: currently none, by design.
- Product name/description: README still leads with the released v1.3.0 "Codex companion" wording; decide wording at release.
- Claude task → project links need a workbench database migration (planned before 2.x).
