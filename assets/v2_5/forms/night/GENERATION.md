# Moon-night form generation record

All 41 actions / 96 candidate sprite PNGs and FORMS_NIGHT_PREVIEW.png are present. Generation is complete; exact anatomical-anchor acceptance remains unverified. See PROGRESS.md and VALIDATION.json for the distinction.

Built-in imagegen edited the exact default-pose references listed in FRAME_MANIFEST.json. Costume references were assets/v2_3/night_idle_1.png and night_change_3.png. idle_1 reuses the existing knees-up night_change_3 artwork with sleepy eyes. User authorized Pillow local composition and pixel alignment. No paid API/backend switch was used.

Prompt intent: retain pose, head/face/hair placement, scale, hands, feet, expression, props and action marks; replace armor, gloves and stockings with lavender long-sleeved pajamas, closed fluffy white collar, bow, matching pants, fluffy white socks, bare hands and crescent clip. Transparent 1254x1254 canvas; no lettering/background/watermark.

Native redraws were registered and locally composed. Facial restoration excludes hands/neck to avoid bringing back gloves/armor. Final small-motion frames use either the original-variant-first method or a Night-base-first edit localized to source-motion masks. The latter repaired greeting ghosting and kept unchanged hair/props stable. Curious and worried have specific repair pipelines described in PROGRESS.md; preserve them when replaying.

Twenty blink outputs retain exact pixels outside local masks; worried uses a native eye-only redraw and the other blinks use source-eye changes/local patches. Thirty-four other variants also pass outside-mask equality. Available raw paths, transforms and composition records are in COMPOSITION.json; exact working masks/raws remain in external scratch.

The original lower-alpha-band enforcement introduced pale fragments where original costumes protruded beyond pajamas. Final FOOTER_CLEANUP.json and ALPHA_CLEANUP.json record their removal and low-alpha fringe cleanup. Original alpha-band equality is therefore not a final acceptance test. The full preview and validation hashes were refreshed after cleanup.

Validation confirms completeness, dimensions, RGBA, transparency, unique hashes, fixed regions and unchanged original images. All source/Night pairs were visually reviewed. Exploratory head contour checks in HEAD_CHECK.json have nonzero optima and are not anatomical-anchor measurements. Exact head/limb/foot equality and runtime accessory attachment alignment have not been certified; do not describe this package as having passed that strict requirement.

No external code or libraries were added to the repository. Existing game-form registration records were inspected only as a diagnostic reference; their validation results were not reused for Night. No code, original assets or files outside assets/v2_5/forms/night/ changed. Local branch only; no push/merge/publication.
