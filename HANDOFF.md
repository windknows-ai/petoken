# Handoff

Concise agent-to-agent recovery snapshot. This is NOT a substitute for `PROGRESS.md`, `CHANGELOG.md`, `AGENTS.md`, or the external version specifications.

## Current Version

`V1.0.0` (released, verified baseline of `petoken`, formerly Codex Wisp)

## Current Target Version

`V1.1.0` (UI and interaction refinement — NOT started)

## Current Stage

Pre-development cleanup completed: repository synchronized to the canonical `windknows-ai/petoken`, documentation/branding migration performed. V1.1.0 implementation has NOT started. Visual references resolved: `04_Visual_Reference_Specification.md` is the authoritative text representation of Reference Images 1, 2, and 3.

## Last Completed Step

- Origin updated to `https://github.com/windknows-ai/petoken.git`; fetched tag `v1.0.0`; fast-forwarded local `main` to `da23495` (includes commits `47f841f` Rename project and `da2349` README format fix).
- AGENTS.md: fixed External Prompt Library path to `D:\Desktop\petoken`; consolidated to a single Multi-Agent Continuity section.
- Created `HANDOFF.md`, `CHANGELOG.md`, `ROADMAP.md`.
- Rebranded current-facing docs/code to `petoken`; rewrote README as a concise front page.
- Preserved `CodexWisp` persisted settings directory and other compatibility-sensitive identifiers.
- Final verification passed: `main` at `da23495` synced to `windknows-ai/petoken`, tag `v1.0.0` present, no `C:\Users\fengz\Desktop` paths remain in docs, `python -m unittest discover -s tests` = 17 tests OK.
- Spec context refreshed: `D:\Desktop\petoken\V1.1.0` finalized to six non-`_UPDATED` files (00, 01, 02, 03, 04, 99); `04_Visual_Reference_Specification.md` resolves the visual-reference requirement. Documentation-only corrections applied; no code changed.

## Current Work / Partial Work

None in progress. All cleanup changes are uncommitted in the working tree (see below).

## Important Decisions

- Canonical project name: `petoken`. Canonical repository: `windknows-ai/petoken`.
- Preserve persisted settings directory `.../LocalAppData/CodexWisp` and module/class/internal identifiers; rename only user-facing branding.
- Preserve historical `Codex Wisp` references in V1.0.0 release documentation and commits.
- Version stays `V1.0.0`; do not increment during this cleanup.

## Uncommitted Changes

`AGENTS.md`, `README.md`, `PROGRESS.md`, `DESIGN.md`, `CHANGELOG.md` (new), `ROADMAP.md` (new), `HANDOFF.md` (new), `docs/implementation-plan.md`, `docs/TOKEN_ACCOUNTING.md`, `docs/RELEASE_NOTES_v1.0.0.md`, `THIRD_PARTY_NOTICES.md`, `widget.py`, `pet.py`, `analytics_view.py`, `build.ps1`, `tools/render_states.py`.

## Known Issues / Blockers

- Visual references resolved (no blocker): `D:\Desktop\petoken\V1.1.0\04_Visual_Reference_Specification.md` provides the authoritative text visual specification for Reference Images 1, 2, and 3. Do not claim the reference images are missing.
- GitHub release is titled "Petoken v1.0.0" and flagged Pre-release (delivery record documented a full release); confirm whether this is intended.
- Repository visibility changed from private (per V1.0.0 PROGRESS) to public; confirm intended.

## Exact Next Step

1. Receive user approval of the lifecycle cleanup before committing or starting V1.1.0.
2. Read `D:\Desktop\petoken\V1.1.0` specifications (00, 01, 02, 03, 04, 99 in order); treat `04_Visual_Reference_Specification.md` as the authoritative text visual specification.
3. Begin `03_V1.1.0_UI_and_Interaction_Refinement.md` implementation order step 1 (inspect architecture) and continue through the ordered steps.
4. Do not mark V1.1.0 complete until its acceptance criteria are verified; update version/CHANGELOG/PROGRESS only then.

## Last Agent

OpenCode