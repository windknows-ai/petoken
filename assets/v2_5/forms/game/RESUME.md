# Game-form art delivery

**Complete: 41 actions, 96 sprite PNGs, and FORMS_GAME_PREVIEW.png.**
Branch: `codex/forms-game`; checkout: `D:/Documents/ChatGPT/petoken-forms-game`.
All changes relative to base `ad44b23` are additions inside this asset folder.
No application code or existing artwork changed. No merge, push or publication.

## Current progress

- The user corrected the original 119-frame plan to the 96 actual default
  frames. The authoritative updated table is
  `D:/Documents/ChatGPT/petoken-claude/docs/form_art/FORM_ART_2_GAME.md`;
  its SHA256 and all exact per-frame source paths are in GENERATION_STATE.json.
  The isolated checkout's older task document is stale and intentionally untouched.
- Every requested sprite was drawn with built-in image_gen, editing its exact
  default pose with `assets/v2_1/form2_idle_1.png` as the game armor reference.
  GENERATION_PROMPTS.json contains all 96 prompts and generated raw file paths.
- All 96 filenames, 1254x1254 RGBA dimensions, real alpha, transparent corners
  and immutable original hashes passed validation. All final hair-contour
  registration offsets and alpha>8 bottom-baseline deltas are zero.
- All 54 follow-up frames, including all 20 blinks, passed exact RGBA equality
  outside their original permitted motion/eye masks. Blinks keep the complete
  game-form first-frame body, armor, props and mouth fixed.
- All source/output action sheets, all 20 closed-eye frames, composition seams
  and the complete contact sheet were visually inspected. The overview has all
  96 actual sprites and contains no PENDING placeholders.
- Evidence: VALIDATION.json, FINAL_HEAD_CHECK.json, HEAD_REGISTRATION.json,
  BASELINE_REGISTRATION.json, FRAME_CONTINUITY.json and COMPOSITION_PLAN.json.

## Decisions

- Preserve each default pose instead of substituting the standing game idle.
  Original occupied-hand props remain in place; armor is fitted to the existing
  anatomy. Source-pose scale is unchanged during integer head registration.
- Match hair-contour edges above y=850 to position the head. Register only the
  lower region below y=1000 to its original bottom anchor; upper anatomy is not
  scaled. These checks measure placement, not clothing-pixel identity.
- Reuse the project's existing animation masks to prevent wardrobe/hair jitter.
  The second stretch frame needed one mask adjustment: old stocking-only foot
  protect polygons erased its registered armored-boot toe. Its full-body mask
  now uses the already registered child feet and extends below the baseline to
  avoid feather attenuation. Final head/bottom and fixed-region checks pass.
- Initial 71-frame checkpoint: `5eea302`. The drawing quota interruption was
  resolved after the user chose to wait for built-in generation; the remaining
  25 frames were subsequently generated. No API fallback or key access used.

## Next steps and open issues

- This report belongs to the final local commit; use `git log -1` for its hash.
- User owns final aesthetic acceptance and Claude owns integration if requested.
  No known file, transparency, anchor-registration or animation-mask failure remains.
- Stop after the final local commit/report. Do not merge, push, tag or publish.

## Project conventions and rework

- Exact corrected 41-action / 96-filename list; do not add nonexistent planned
  default frames. The overview is additional to the 96 transparent sprite PNGs.
- Authoring helpers live outside the repository at
  `C:/Users/fengz/.codex/visualizations/2026/10/12/01a12eca-e5b7-7be1-87bd-8038dabcf65e/`:
  game_pixels.ps1, game_compose.ps1, game_validate.ps1, game_sheet.ps1.
  They use the installed System.Drawing runtime; no Python/new dependency used.
- For rework, restore the relevant raw output from GENERATION_PROMPTS.json,
  apply its recorded registration, then compose the applicable motion-mask entry.
  Do not repeatedly composite a finished PNG. Preserve this art-only write scope.
