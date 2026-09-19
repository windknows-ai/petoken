# Handoff

Concise agent-to-agent recovery snapshot. This is NOT a substitute for `PROGRESS.md`, `CHANGELOG.md`, `AGENTS.md`, or the external version specifications.

## Current Version

`V1.0.0` (released, verified baseline of `petoken`, formerly Codex Wisp)

## Current Target Version

`V1.1.0` (UI and interaction refinement — Daily / Token mode slice complete)

## Current Stage

Pre-development cleanup is committed locally at `9b7300b`. OpenCode completed V1.1.0 Step 1 architecture inspection. Codex completed and verified the approved foundation and centralized Daily / Token mode slices; this checkpoint commit records both slices without pushing them. Visual references are resolved by `04_Visual_Reference_Specification.md`.

## Last Completed Step

- Origin updated to `https://github.com/windknows-ai/petoken.git`; fetched tag `v1.0.0`; fast-forwarded local `main` to `da23495` (includes commits `47f841f` Rename project and `da2349` README format fix).
- AGENTS.md: fixed External Prompt Library path to `D:\Desktop\petoken`; consolidated to a single Multi-Agent Continuity section.
- Created `HANDOFF.md`, `CHANGELOG.md`, `ROADMAP.md`.
- Rebranded current-facing docs/code to `petoken`; rewrote README as a concise front page.
- Preserved `CodexWisp` persisted settings directory and other compatibility-sensitive identifiers.
- Final verification passed: `main` at `da23495` synced to `windknows-ai/petoken`, tag `v1.0.0` present, no `C:\Users\fengz\Desktop` paths remain in docs, `python -m unittest discover -s tests` = 17 tests OK.
- Spec context refreshed: `D:\Desktop\petoken\V1.1.0` finalized to six non-`_UPDATED` files (00, 01, 02, 03, 04, 99); `04_Visual_Reference_Specification.md` resolves the visual-reference requirement. Documentation-only corrections applied; no code changed.
- Cleanup committed locally as `9b7300b`; it has not been pushed.
- OpenCode completed V1.1.0 Implementation Order Step 1 (architecture inspection). No V1.1.0 implementation code existed when Codex took over.
- Codex added one `APP_VERSION` source, settings schema version 1 with compatible default merging and atomic persistence, persistent language preference, and a centralized `zh_CN` / `en` string catalog.
- Verification passed: 22 tests, `py_compile`, isolated live smoke, and `git diff --check`. The existing visual baseline was preserved.
- Codex added centralized `AppModeState`, explicit Codex lifecycle detection across unarchived desktop sessions, working-state priority, and Daily-mode bubble hiding. UIA task presence plus a running lifecycle event is required; a visible idle Codex window is insufficient.
- Daily / Token verification passed: 30 tests, `py_compile`, live Token smoke, logical/visual Daily bubble checks, and detector cold/warm timing. No visual redesign was performed.

## Current Work / Partial Work

No implementation is currently in progress. Stop point is immediately before active-project identity integration.

## Important Decisions

- Canonical project name: `petoken`. Canonical repository: `windknows-ai/petoken`.
- Preserve persisted settings directory `.../LocalAppData/CodexWisp` and module/class/internal identifiers; rename only user-facing branding.
- Preserve historical `Codex Wisp` references in V1.0.0 release documentation and commits.
- Version stays `V1.0.0`; do not increment during this cleanup.

## Current Git State

- Branch: `main`; this checkpoint commit follows cleanup checkpoint `9b7300b` and is not pushed.
- The checkpoint contains the approved V1.1.0 version/settings/localization foundation and Daily / Token mode work, their tests, and repository state documentation.
- The working tree is clean at this checkpoint before active-project identity work begins.
- External `D:\Desktop\petoken\V1.1.0\99_Implementation_Notes.md` is updated outside this Git repository.

## Known Issues / Blockers

- Visual references resolved (no blocker): `D:\Desktop\petoken\V1.1.0\04_Visual_Reference_Specification.md` provides the authoritative text visual specification for Reference Images 1, 2, and 3. Do not claim the reference images are missing.
- GitHub release is titled "Petoken v1.0.0" and flagged Pre-release (delivery record documented a full release); confirm whether this is intended.
- Repository visibility changed from private (per V1.0.0 PROGRESS) to public; confirm intended.
- Working-state recovery is bounded: an unclean session with no `task_complete` can remain active for at most five minutes while a task window exists; a genuinely running tool that writes no rollout events for more than five minutes can temporarily fall back to Daily until the next event.
- Global mode may be activated by one session while the existing UIA-followed panel displays another project. Correctly associating the detected working session with its project and live usage is the next V1.1.0 step.

## Exact Next Step

1. Implement V1.1.0 order step 4: expose the detected working session's project identity to Token Mode and pair the visible project name with the matching live token usage.
2. Do not combine that slice with new scopes, currency changes, character assets, Bongo-Cat animation, music subtitles, or V1.2.0.
3. Do not mark V1.1.0 complete until all V1.1.0 acceptance criteria are verified.

## Last Agent

Codex (primary). OpenCode remains the fallback continuation agent if Codex usage is exhausted.
