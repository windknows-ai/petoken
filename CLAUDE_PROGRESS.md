# Claude progress

## Current state — V1.5 dual provider (branch `claude/v1.5-dual-provider`, from `e529ddb`)

Codex compatibility layer (`cd637e1`) merged as `116fb9a`; compatibility notice and V1.5 preview added in `3809953`. Full suite after merge: 1042 tests, all pass. **Waiting for the maintainer's visual QA.**

- Package: `D:\Documents\ChatGPT\petoken-takeover-backups\2026-10-05-v1.5-dual-provider\package-dev\petoken\` — launcher `preview-v1.5.cmd`, checklist `V1_5_DUAL_PROVIDER_QA.md`. EXE SHA256 `a9bdc92fb69ab5d7a5593b1c78fc295c3ca6323d29473827ac4a29f96a060e7a`; ZIP `820cdcf577083a5ca21314ea8be42160b72239a38ae5179d6ae8d4d1bba6f43d` (rebuilt from `cb52d3b`). Frozen capture `frozen-ring.png` shows blue Codex and gold Claude stars with a matching ring gradient.
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
- [ ] Next maintainer QA round. Release/main merge only on explicit authorization.

## Open questions for the maintainer

- Combined (Codex + Claude) total view: currently none, by design.
- Product name/description: README still leads with the released v1.3.0 "Codex companion" wording; decide wording at release.
- Claude task → project links need a workbench database migration (planned before 2.x).
