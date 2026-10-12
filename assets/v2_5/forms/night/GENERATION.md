# Moon-night form partial art checkpoint

Status: 6 of 96 frames saved as candidates; entire request incomplete.

## Mode and sources
- Built-in imagegen used for typing_1, typing_2, microphone_1 and guitar_1.
- idle_1 reuses the existing assets/v2_3/night_change_3.png wardrobe master with registered original foot contact alpha and its original sleepy eyes; idle_blink closes only local eye regions using assets/v2_0/idle_blink.png.
- User explicitly authorized Pillow local masked composition and pixel alignment on 2026-10-12.
- FRAME_MANIFEST.json records the approved updated 41-action / 96-frame source mapping. The worktree's original docs/form_art spec still contains the older 119-frame list; use this manifest or the refreshed Claude checkout's spec.

## Prompt set
For the four new imagegen edits, image 1 was the corresponding original frame from FRAME_MANIFEST.json, image 2 was assets/v2_3/night_idle_1.png as costume-only reference. Prompt constraints: keep the original head/face/hair size and placement, original eye expression, arms/hands/legs/foot contact positions, existing props and action marks; replace dark armor, gloves, stockings and crystal ornament with pale-lavender long-sleeved pajamas, neck bow, matching pajama pants, fluffy white socks, bare hands and moon clip. Do not copy the costume reference's cross-legged pose or pillow. Keep the exact original typing direction in each typing frame, microphone pose/closed singing eyes in microphone_1, and original acoustic guitar/strumming pose/closed eyes in guitar_1. Exactly 1254x1254 RGBA, real transparency, no text, background, ground or watermark.

## Composition and validation
Generated hair/face is registered against the unchanged original upper-head pixels; a local original facial patch retains the source expression. Lower-body vertical registration and an exact original alpha contact band retain foot anchors. idle_blink retains every pixel outside the eye mask. See VALIDATION.json for actual checks and their limits. Preview/scratch scripts/masks/raws are retained outside the repo in the production cache recorded in PROGRESS.md.

## Blocking condition
Built-in imagegen returned HTTP 429 usage_limit_reached for idle_1, codex_working_1, music_1, celebrate_1, sad_1 and wave_1. No images were returned by those six attempted jobs. Service reset timestamp: 1791837933 (2026-10-12 16:45:33 America/Toronto). Do not silently substitute blank frames, duplicate actions or paid API calls.
