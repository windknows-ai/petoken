# Handoff

Concise agent-to-agent recovery snapshot. This is NOT a substitute for `PROGRESS.md`, `CHANGELOG.md`, `AGENTS.md`, or the external version specifications.

## Current Version

`V1.0.0` (released, verified baseline of `petoken`, formerly Codex Wisp)

## Current Target Version

`V1.1.0` (UI and interaction refinement — three-scope Token architecture complete)

## Current Stage

OpenCode performed the pre-implementation Step 1 architecture inspection only. Codex verified it and has performed all V1.1.0 implementation work. Local checkpoints `859b654` and `f061ccf` record the approved foundations/modes and Working Context respectively; neither was pushed. The completed three-scope slice remains uncommitted. Visual references are resolved by `04_Visual_Reference_Specification.md`.

## Last Completed Step

- Origin updated to `https://github.com/windknows-ai/petoken.git`; fetched tag `v1.0.0`; fast-forwarded local `main` to `da23495` (includes commits `47f841f` Rename project and `da2349` README format fix).
- AGENTS.md: fixed External Prompt Library path to `D:\Desktop\petoken`; consolidated to a single Multi-Agent Continuity section.
- Created `HANDOFF.md`, `CHANGELOG.md`, `ROADMAP.md`.
- Rebranded current-facing docs/code to `petoken`; rewrote README as a concise front page.
- Preserved `CodexWisp` persisted settings directory and other compatibility-sensitive identifiers.
- Final verification passed: `main` at `da23495` synced to `windknows-ai/petoken`, tag `v1.0.0` present, no `C:\Users\fengz\Desktop` paths remain in docs, `python -m unittest discover -s tests` = 17 tests OK.
- Spec context refreshed: `D:\Desktop\petoken\V1.1.0` finalized to six non-`_UPDATED` files (00, 01, 02, 03, 04, 99); `04_Visual_Reference_Specification.md` resolves the visual-reference requirement. Documentation-only corrections applied; no code changed.
- Cleanup committed locally as `9b7300b`; it has not been pushed.
- OpenCode performed V1.1.0 Implementation Order Step 1 architecture inspection only. No V1.1.0 implementation code existed before Codex began development.
- Codex added one `APP_VERSION` source, settings schema version 1 with compatible default merging and atomic persistence, persistent language preference, and a centralized `zh_CN` / `en` string catalog.
- Verification passed: 22 tests, `py_compile`, isolated live smoke, and `git diff --check`. The existing visual baseline was preserved.
- Codex added centralized `AppModeState`, explicit Codex lifecycle detection across unarchived desktop sessions, working-state priority, and Daily-mode bubble hiding. UIA task presence plus a running lifecycle event is required; a visible idle Codex window is insufficient.
- Daily / Token verification passed: 30 tests, `py_compile`, live Token smoke, logical/visual Daily bubble checks, and detector cold/warm timing. No visual redesign was performed.
- Checkpoint commit `859b654fca36fc792b2846bb1acb27ffcdd50ba7` was created locally with a clean post-commit working tree; no push and no version change.
- Token Mode now prefers a foreground UIA-matched working thread, otherwise the most recently active working thread. The chosen session supplies one structured `working_context` containing project identity and that session's fork-deduplicated Token data.
- Project identity priority is explicit project metadata, Git origin repository name, cwd basename, then unavailable. No full paths or inferred window-title project names are exposed.
- Working-context recovery verification passed: 39 tests, `py_compile`, isolated live smoke, and visual bubble inspection. With two working sessions detected, the live bubble selected the foreground thread and showed that thread's matching title, `Web Project`, and 31.40M session Tokens.
- Working Context checkpoint `f061ccf11362425fff9da379f45a4d36469b5f4c` was committed locally without pushing or changing the application version; its post-commit working tree was clean.
- Codex implemented structured Global / Project / Conversation identities and coherent scope results. Global reads all eligible local rollout rows, Project groups only a shared stable project identity, and Conversation selects exactly one thread. All use the existing nullable/fork-deduplicated accounting.
- The minimal Settings and quick-menu selector now exposes all three scopes. Legacy `task` settings remain Conversation-compatible. Analytics scope changes do not alter the active Working Context or pet bubble.
- Scope verification passed: 52 tests, `py_compile`, isolated Global smoke, and panel/pet/analytics screenshot inspection. The smoke aggregated 1,698 unique events / 186,031,972 locally recorded Tokens while the pet independently displayed the active `Web Project` context.

## Current Work / Partial Work

No implementation is currently in progress. Stop point is immediately before compact/full Token number formatting and units.

## Important Decisions

- Canonical project name: `petoken`. Canonical repository: `windknows-ai/petoken`.
- Preserve persisted settings directory `.../LocalAppData/CodexWisp` and module/class/internal identifiers; rename only user-facing branding.
- Preserve historical `Codex Wisp` references in V1.0.0 release documentation and commits.
- Version stays `V1.0.0`; do not increment during this cleanup.

## Current Git State

- Branch: `main`, checkpoint HEAD `f061ccf`, three commits ahead of `origin/main`; no local checkpoint was pushed.
- The post-checkpoint scope slice is intentionally uncommitted. Modified tracked files: `PROGRESS.md`, `HANDOFF.md`, `app_config.py`, `usage.py`, `widget.py`, `analytics_view.py`, `tests/test_settings.py`, and `tests/test_ui.py`. New untracked file: `tests/test_scopes.py`.
- External `D:\Desktop\petoken\V1.1.0\99_Implementation_Notes.md` is updated outside this Git repository.

## Known Issues / Blockers

- Visual references resolved (no blocker): `D:\Desktop\petoken\V1.1.0\04_Visual_Reference_Specification.md` provides the authoritative text visual specification for Reference Images 1, 2, and 3. Do not claim the reference images are missing.
- GitHub release is titled "Petoken v1.0.0" and flagged Pre-release (delivery record documented a full release); confirm whether this is intended.
- Repository visibility changed from private (per V1.0.0 PROGRESS) to public; confirm intended.
- Working-state recovery is bounded: an unclean session with no `task_complete` can remain active for at most five minutes while a task window exists; a genuinely running tool that writes no rollout events for more than five minutes can temporarily fall back to Daily until the next event.
- The prior project/Token mismatch is resolved for the pet bubble. The expanded dashboard now has the completed three-scope system, independent from active Working Context.
- Some local sessions have neither project metadata nor Git origin nor cwd; their project is shown as unavailable instead of being invented.

## Exact Next Step

1. Implement V1.1.0 order step 6: persisted Full / Compact Token number formatting and consistent metric units.
2. Do not combine that slice with the full localization pass, currency changes, character assets, Bongo-Cat animation, music subtitles, or V1.2.0.
3. Do not mark V1.1.0 complete until all V1.1.0 acceptance criteria are verified.

## Last Agent

Codex (primary). OpenCode remains the fallback continuation agent if Codex usage is exhausted.
