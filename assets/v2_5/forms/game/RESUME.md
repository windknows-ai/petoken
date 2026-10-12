# Game-form art checkpoint

Task is **incomplete**: 71 of the corrected 96 requested sprite PNGs exist.
Branch: `codex/forms-game`; isolated checkout: `D:/Documents/ChatGPT/petoken-forms-game`.
Only this asset folder was changed. No code, existing art, root handoff files,
Claude checkout, merge, push or publication was changed/performed.

## Current progress

- Updated user specification: 41 actions / 96 PNGs. Original planned-but-missing
  default frames were explicitly removed by the user. The authoritative updated
  table is `D:/Documents/ChatGPT/petoken-claude/docs/form_art/FORM_ART_2_GAME.md`.
  The isolated checkout's old copy of that document is stale; do not edit it.
- 71 wardrobe edits generated with the built-in image_gen tool, using each
  exact default pose and `assets/v2_1/form2_idle_1.png` as the armor reference.
- All 71 sprites checked as 1254x1254 RGBA with actual transparent pixels.
- Lower-body registration below y=1000 matches each original alpha>8 bottom
  anchor; the entire upper region remains unchanged during registration.
- 32 subsequent frames reuse the original source motion masks, preserving
  every RGBA pixel outside the permitted moving regions. This prevents armor
  and hair details from changing across an animation.
- `FORMS_GAME_PREVIEW.png` is a **progress** contact sheet with 25 PENDING slots,
  not the final complete overview. No placeholder sprite files were created.
- Per-file sources, missing filenames and next step: `GENERATION_STATE.json`.
  Final pixel/dimension/hash checks: `VALIDATION.json`. Generated raw paths and
  full drawing prompts: `GENERATION_PROMPTS.json`.

## Blocker and next steps

Built-in image_gen returned HTTP 429 `usage_limit_reached`, a 1440-minute Plus
quota window. Reported reset: **2026-10-12 16:45:33 America/Toronto**
(20:45:33 UTC, Unix 1791837933). Do not repeatedly retry before the reset.
No paid API fallback or key access has been authorized.

1. Generate missing primary frames: `focus_done_1`, `stretch_break_1`,
   `stretch_break_2`, `worried_2`, `proud_1`, using the exact table references.
2. Generate all 20 `_blink` files as eye-only edits of the finished matching
   game-form `_1` PNG, with the corresponding default blink as eye reference.
   Sixteen attempted blink calls failed with the quota error; no blink PNG
   exists yet. Four blink calls were not attempted after the limit was known.
3. Finish registration, original motion-mask composition and visual inspection.
   Pixel-perfect individual head/hand/foot landmark agreement has not been
   numerically certified; do not claim complete pose acceptance yet.
4. Validate the exact 96 filenames, RGBA/dimensions/transparency, outside-eye
   equality for every blink, frame continuity, immutable source hashes and
   allowed-directory-only Git changes. Replace the progress contact sheet with
   the completed overview, update these records, and make the final local commit.
5. Do not push, merge, tag or publish.

## Local finishing tools

Authoring helpers are outside the repository at:
`C:/Users/fengz/.codex/visualizations/2026/10/12/01a12eca-e5b7-7be1-87bd-8038dabcf65e/`:
`game_pixels.ps1`, `game_compose.ps1`, and `game_sheet.ps1`.
They use the installed System.Drawing runtime; no Python or new dependency was
used. Compilation needs the installed .NET 10 Drawing.Common, Primitives,
Private.Windows.GdiPlus and Private.Windows.Core assemblies. Initial compiler
reference failures were repaired; no sprite was changed by the failed checks.

`COMPOSITION_PLAN.json` records the reusable parts/polygons and parents from
the existing default-form validation files. Do not repeatedly composite already
finished sprites: restore the applicable generated raw PNG first if a rework is
needed, register its lower region, then apply the relevant motion-mask entry.
