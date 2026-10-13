# Moon-night form partial checkpoint

Status: 40/96 candidate frames, 28/41 action masters. Incomplete; no final overview.

## Sources and mode
- Built-in imagegen redraws the wardrobe from the exact default reference in FRAME_MANIFEST.json. idle_1 reuses assets/v2_3/night_change_3.png with its sleepy eyes and local registration. User approved Pillow masked composition/alignment.
- Use the updated 96-frame manifest or D:/Documents/ChatGPT/petoken-claude/docs/form_art/FORM_ART_1_NIGHT.md. Worktree spec is the obsolete 119-frame version.
- Costume references: assets/v2_3/night_idle_1.png; later batches also assets/v2_3/night_change_3.png for the closed collar. Latest prompt is saved in the production cache's prompt.txt.

## Prompt and local edits
Preserve source pose, head/face/hair placement and scale, hands, feet, expression, props and action marks. Replace dark costume, gloves, stockings and head crystal with lavender long-sleeved pajamas, fully closed fluffy collar, neck bow, matching pants, white fluffy socks, bare hands and moon clip. Do not copy reference pose/pillow. Canvas 1254x1254 RGBA, real transparency; no lettering/background/ground/watermark.

Generated hair/face is registered against source pixels. Original expression is restored locally, excluding hands to avoid old glove pixels. Lower-body adjustment and source alpha contact band are applied. COMPOSITION.json records available registration/raw provenance; independent masks/records remain in scratch. These checks do not prove exact full pose alignment.

Eleven blinks use original source eye changes, with exact pixels outside local masks. idle uses separate eye regions. Thinking/poked punctuation was replaced with local nontext twinkles; thinking blink regenerated afterward. All masks/pre-edit images and cleanup_symbols.py remain in scratch.

Curious neckline was redrawn; redraw introduced a silver horn. The earlier correct registered head was composed above y798 with a 5px feather. Do not recompose from raw-curious_1.png without replaying mask-curious-head-repair.png using exec-2a4e19df-63af-424f-b148-57178c785bd1.png. Current curious base/blink include the repair.

## Validation and limits
VALIDATION.json covers all 40: dimensions/alpha, 40 distinct hashes, 11 blink outside-mask checks, 121 unchanged old assets. Exact head/limb/foot coordinates, seams, costume accessories and animation continuity still require final acceptance. sleep_1 retains a dark bow/crystal pillow prop; review night-form consistency. Runtime integration untested. The only current overview is partial-40.png in external scratch, not a complete delivery overview.

## Current quota block
Second native generation batch returned HTTP 429 usage_limit_reached for cheer_1, clap_1, peek_1 and grievance_1; none returned an image. Reset 1791926437 = 2026-10-13 17:20:37 America/Toronto. No API/CLI fallback authorized or used. Do not substitute duplicates or original armor frames.
