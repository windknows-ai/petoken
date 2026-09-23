# Roadmap

Future ideas, separated from current implementation work.

> ROADMAP ITEMS ARE NOT CURRENT TASKS.
> Reading an item here does not authorize building it. Implement only what is explicitly requested.

## Completed baseline — V1.1

**V1.1.0 USER-ACCEPTED and released as v1.1.0** (existing release record; publication not rechecked during planning). R1–R9, A1–A4 and P1–P2 are complete. Preserve Daily/Token, coherent Codex context, three scopes, analytics, localization, currency/formatting, chibi/DPR/anchor behavior, 50–150% character scale, Compact restore, pin/topmost and expanded resize. These are not future features.

## Approved V1.2 — Codex + OpenCode, one companion

- Status: IMPLEMENTED AND ACCEPTED; local release candidate prepared as V1.2.0 (not yet published — remote publication needs separate authorization).
- REQUIRED: verified privacy-safe OpenCode metadata and activity; minimal two-provider boundary; Auto/Codex/OpenCode tracking; coherent provider/session context; provider-local analytics and truthful capabilities/cost/freshness; failure isolation and bounded polling.
- OPTIONAL, not in recommended scope: separate-provider analytics comparison; verified structured CLI fallback only if actually needed.
- Mandatory: provider-consistent project/session/token/cost; missing OpenCode fields stay N/A; manual choice overrides Auto; Auto ranks working first, both-working by activity recency, neither-working by activity/use recency. Combined cross-provider Token totals prohibited.
- Seven slices: discovery gate → Codex wrapper → OpenCode adapter → selection/activity → current UI binding → analytics/cost → final acceptance.
- No new character assets, UI redesign, version bump or implementation authorized by reading this plan.
- Authoritative approved detail: `D:\Desktop\petoken\V1.2.0\00_Scope_and_Behavior.md`, `01_Provider_Architecture.md`, `02_Implementation_and_Acceptance.md`. Existing original prompt preserved; latest planning-only user instruction overrides its immediate-execution wording.
- OpenCode implements approved slices; Astra reviews; expensive full acceptance runs once at the end unless a defect justifies repetition.

## Deferred V1.3+ ideas

- Additional provider adapters (Claude Code, Gemini and others); combined cross-provider totals.

- Advanced Codex awareness (thinking / coding / testing / error states).
- Usage-limit intelligence.
- GitHub companion functionality.
- Personality systems.
- File interaction.
- Voice interaction.
- Calendar integration.
- Advanced desktop companion features.

These follow the future-idea list defined in the active versioning specification (`D:\Desktop\petoken\V1.1.0\01_Versioning_and_Development_Rules.md`). V1.1.0 (UI and interaction refinement) was the authorized target and is now released; it is not a roadmap item.
