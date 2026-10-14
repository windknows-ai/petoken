# Moon-night form partial checkpoint

Status: 76/96 candidate frames, all 41 action masters. Incomplete; no final overview.

## Sources and mode
- Built-in imagegen redraws the wardrobe from the exact default reference in FRAME_MANIFEST.json. idle_1 reuses assets/v2_3/night_change_3.png with its sleepy eyes and local registration. User approved Pillow masked composition/alignment.
- Use the updated 96-frame manifest or D:/Documents/ChatGPT/petoken-claude/docs/form_art/FORM_ART_1_NIGHT.md. Worktree spec is the obsolete 119-frame version.
- Costume references: assets/v2_3/night_idle_1.png; later batches also assets/v2_3/night_change_3.png for the closed collar. Latest prompt is saved in the production cache's prompt.txt.

## Prompt and local edits
Preserve source pose, head/face/hair placement and scale, hands, feet, expression, props and action marks. Replace dark costume, gloves, stockings and head crystal with lavender long-sleeved pajamas, fully closed fluffy collar, neck bow, matching pants, white fluffy socks, bare hands and moon clip. Do not copy reference pose/pillow. Canvas 1254x1254 RGBA, real transparency; no lettering/background/ground/watermark.

Generated hair/face is registered against source pixels. Original expression is restored locally, excluding hands to avoid old glove pixels. Lower-body adjustment and source alpha contact band are applied. COMPOSITION.json records available registration/raw provenance; independent masks/records remain in scratch. These checks do not prove exact full pose alignment.

Twenty blinks retain exact pixels outside local masks. Nineteen use original source eye changes; worried uses a native closed-eye redraw because source-face compositing caused visible seams. idle uses separate eye regions. Thinking/poked punctuation was replaced with local nontext twinkles; thinking blink regenerated afterward. All masks/pre-edit images and cleanup_symbols.py remain in scratch.

Curious neckline was redrawn; redraw introduced a silver horn. The earlier correct registered head was composed above y798 with a 5px feather. Do not recompose from raw-curious_1.png without replaying mask-curious-head-repair.png using exec-2a4e19df-63af-424f-b148-57178c785bd1.png. Current curious base/blink include the repair.

## Validation and limits
VALIDATION.json covers all 76: dimensions/alpha, 76 distinct hashes, 20 blink and 14 localized-variant outside-mask checks, 121 unchanged old assets. Exact head/limb/foot coordinates, seams, costume accessories and animation continuity still require final acceptance. sleep_1 retains a dark bow/crystal pillow prop; review night-form consistency. Runtime integration untested. The only current overview is partial-76.png in external scratch, not a complete delivery overview.

## Current quota block
Third quota block returned HTTP 429 usage_limit_reached for yawn_3, wake_stretch_2, curious_2, thinking_2. No images returned. Reset 1792029747 = 2026-10-14 22:02:27 America/Toronto. User selected native-quota waiting; no CLI/API authorization. 20 frames remain. No final overview or full pose acceptance yet.

## Latest continuation methods
13 additional action masters were drawn, with 9 added blinks. Three inspected noncostume deltas (grievance_2, worried_2, focus_read_4) and 11 moving wardrobe variants bring 40 to 76. The moving frames use a native redraw, registration, then a local mask derived from visible source-frame differences; pixels outside it remain exactly the action base. Component bounding rectangles avoid changing distant hair or marks. COMPOSITION.json and external record/mask/raw files preserve available provenance.

Worried uses a registered native face with source sweat-mark composition; rectangular source-face copying was disabled after seam failures. Its blink was natively redrawn against night base, then only local eye regions retained. Hold-card face ROI is manually corrected because paper was misclassified as skin. Cheer/yawn/stretch neckline and hand exclusions prevent legacy glove/armor restoration. See PROGRESS.md for exact replay steps and final review concerns.
