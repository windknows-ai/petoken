# Petoken v1.3.0

**Codex-only Windows desktop companion — human visual QA accepted on 2026-10-04.**
The accepted refinements previously called V1.4 during development are included
in this v1.3.0 release at the user's request.

## Highlights

- Close-fitting tilted star ring with front/back depth, brighter crystal Stars,
  pearl/violet/champagne glow, dotted arcs and longer tapered trails.
- Pet and ring move/resize as one centered composition. Front layers retain
  correct native ordering; screen boundaries do not stall the shared orbit.
- Ring stays enabled across Hub interactions and empty/unavailable task sources.
  Only the explicit ring setting disables it; no tasks means decoration without
  invented task Stars.
- Smooth Star-origin detail unfold/fade, reversible close and reduced-motion
  support. Retired tasks, movement and shutdown cancel obsolete snapshots.
- More than 8 tasks use stable-number pages with direct off-page detail access.
  Task-local metrics never merge identities or fabricate unknown values.
- Original idle, typing, working, microphone and music artwork is preserved.
- Codex-only runtime/settings/analytics. No OpenCode adapter is imported or
  bundled in the frozen executable; old adapter source/tests are historical.
- Improved provider recovery, publication/shutdown safety and privacy-safe
  projections retain honest Unknown/N/A/zero/partial distinctions.

## Install

Download `Petoken-v1.3.0-Windows-x64.zip` and `SHA256SUMS.txt` from the
[GitHub release](https://github.com/windknows-ai/petoken/releases/tag/v1.3.0).
Verify the ZIP's SHA-256, then extract the entire folder to a new location.
Run `petoken.exe`; keep `_internal` alongside it. The executable SHA-256 is
also listed in `SHA256SUMS.txt`.

Normal operation follows the user's local Codex client. `preview-v1.3.cmd`
opens an isolated synthetic demonstration with temporary settings and no live
provider polling. The former `--preview-v1-4` entry remains a compatibility
alias; it is not a separate version. Existing preferences remain compatible.

## Verification and limits

The accepted implementation has effective coverage of 914 native regression
cases: 913 passed in the full run; one obsolete Settings assertion was updated
and all 31 current UI tests passed a targeted recheck, without runtime changes.
Independent native/code/package review and frozen executable scenarios passed;
the user then accepted visual QA. Release version/label changes receive their
own targeted checks and rebuilt package validation.

At most 8 distinct interactive Stars occupy one page; 24/64 task sets were
tested and production identity is not capped at 64. Very small workareas may
lack room for the body and fixed-size targets; decoration remains centered
without a containment guarantee. Arbitrary DPI/monitor configurations have not
all been tested. Synthetic microphone/music/typing poses verify rendering,
not live physical detection. API-equivalent cost remains an estimate, not a bill.

See [visual walkthrough](V1_3_VISUAL_QA.md), [usage semantics](USAGE_MODEL.md)
and [artwork terms](ARTWORK.md). Application code is MIT; character artwork is
excluded from that grant. The project is not affiliated with OpenAI or a game
publisher.
