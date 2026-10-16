# Night form art handoff

## Current progress
- 2026-10-16: all 41 actions / 96 candidate sprite PNGs are saved, plus FORMS_NIGHT_PREVIEW.png (2160x3648). No frames remain to generate. Strict anatomical-anchor acceptance remains open; this is not a pixel-exact registration certificate.
- Branch codex/forms-night; isolated worktree D:/Documents/ChatGPT/petoken-forms-night; base ad44b23. Only assets/v2_5/forms/night/ changed. No push/merge/tag/publication.
- Authoritative updated brief: D:/Documents/ChatGPT/petoken-claude/docs/form_art/FORM_ART_1_NIGHT.md (96 frames). The isolated worktree's source brief still says 119; do not use that stale count.
- This continuation adds the final 20 frames, repairs greet_night_2 ghosting with a Night-base-first edit, and excludes the opposite diagonal collar in stretch_break_2. Native quota was available again; no paid API used.
- All 96 source/Night pairs were reviewed in paired-review-1..6.png outside the repository. Enlarged worried and stretch_break_2 images were inspected. Sleep retains the source pillow's dark bow/crystal prop; it is separate from the clothing.
- Final cleanup removed artificial pale contact-band fragments and alpha1..3 color speckles. Preview was rebuilt after cleanup. Earlier source lower-band equality was not sufficient evidence of correct foot placement and is not an acceptance condition.

## Verification and open issues
- VALIDATION.json: 96 distinct 1254x1254 RGBA sprites, alpha min0/max255; 20 blink and 34 localized-variant outside-mask equality checks passed; all 121 original PNG hashes unchanged; no missing frames or validator errors.
- ALPHA_CHECK.json: all four 16x16 corners are completely transparent on every sprite. FOOTER_CLEANUP.json and ALPHA_CLEANUP.json document removal of invented fallback pixels/fringes.
- HEAD_CHECK.json contains exploratory color/alpha contour searches, including nonzero best translations. Differences in redrawn hair, shading and eye pixels make those scores ambiguous. They were not used to shift otherwise fixed animation groups. Exact head/hand/foot coordinates and accessory attachment alignment have NOT been certified. Do not report the user requirement of completely identical anchors as verified.
- No remaining obvious collar/armor composition seams were found in the contact-sheet review. This is limited visual evidence, not a full anatomical landmark check.
- Runtime integration and overlays have not been tested. No application code changed.
- First alpha-component report export failed on numpy.int64 JSON serialization; corrected by converting/using Python int. The first broad component cleanup would remove intentional ground puffs; it was replaced from backups with a fallback-color filter before final cleanup. Final checks ran after the correction.

## Decisions and replay details
- Built-in imagegen draws pajamas from exact default-pose references plus existing night_idle_1/night_change_3 costume references. User explicitly authorized Pillow local masks and alignment; no backend switch was authorized or used.
- production.py registers generated hair/face, adjusts lower body, restores source facial expressions with exclusions for hands/collar, and originally copied source lower alpha bands. Final output must additionally replay clean_footer.py plus the exact fallback-fill/alpha1..3 cleanup in ALPHA_CLEANUP.json. Do not reinstate the old source alpha band after cleanup.
- save_variant.py uses premultiplied visible source deltas, component rectangles and feathered masks to preserve fixed areas. save_night_edit.py first edits the completed Night base, registers to that base, and retains only source-motion regions. Night-first method is used for greet_night_2, cheer_2, clap_2/3, peek_2, focus_read_2/3, focus_tea_2.
- curious_1 has a corrected closed neckline and an earlier horn-free registered head above y798, feather5: exec-2a4e19df-63af-424f-b148-57178c785bd1.png / mask-curious-head-repair.png. Do not blindly recompose raw-curious_1.png.
- idle_1 reuses night_change_3 plus sleepy eyes. Thinking/poked punctuation became local twinkles via cleanup_symbols.py. Regenerate relevant blinks after changing any base.
- Worried source-face rectangle caused seams/old glove fragments and is disabled. Its native face and local sweat mark are retained. final_worried_blink.py uses native closed-eye regions; do not run the abandoned flat-fill worried_blink.py. Refresh before-worried-prop-fix.png before replay if the base changes.
- Hold-card face box is manually (490,515,840,680), because the automatic detector selected the cream card. Worried face override is (530,495,920,665). Diagonal neck exclusion differs for stretch_break_2; preserve it.
- yawn hand/neck and thinking_2 hand exclusions prevent copying legacy gloves or armor. greet_night_2 must use its Night-first raw, not the rejected source-first raw that moved hair.

## Next steps
1. Exact registration remains the substantive unresolved requirement: measure source/Night anatomical landmarks (head attachment origin, hands, each foot), resolve contour alerts with per-pose masks/warps, and check accessory overlays. Do not treat footer alpha equality or exploratory contour minima as a substitute.
2. After any pixel changes, regenerate masks/blinks as necessary, replay fragment cleanup, rerun verify_checkpoint.py, refresh ALPHA_CHECK.json and the complete overview, then make another local commit. Do not push.

## Resume tools and cache
- Python: C:/Users/fengz/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe (Pillow/numpy available).
- Scratch: C:/Users/fengz/.codex/generated_images/01a12eca-f0d4-7e80-b080-5757175f4f88/night-production.
- frames.json, spec.md, prompt.txt, original-sha256.json; production.py, save_native.py, save_variant.py, save_night_edit.py, local_variants.py, final_worried_blink.py, cleanup_symbols.py, clean_footer.py, verify_checkpoint.py, review_all.py, head_alpha_check.py.
- Raw redraws: raw-*.png / raw-edit-*.png; exact per-frame masks and record-*.json. Per-frame records override old composition.json. COMPOSITION.json contains consolidated available provenance.
- before-footer-cleanup/ contains all 96 pre-cleanup PNGs. Do not rerun clean_footer.py after further pixel changes without refreshing backups; the script replays from those backups. Final exact-fill and alpha1..3 cleanup is documented by ALPHA_CLEANUP.json, not yet integrated into production.py.
- Native image originals also persist in the parent generated_images folder. Do not rely on transient V8 stores across turns.
