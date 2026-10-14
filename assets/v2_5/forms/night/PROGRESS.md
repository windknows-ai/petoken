# Night form art handoff

## Current progress
- CHECKPOINT: 76/96 candidate PNGs; all 41 action masters, 20 blinks, 14 other localized variants and typing_2. Entire request is incomplete. Previous commit b302a54 had 40; this continuation adds 36 and corrects yawn_1.
- Branch codex/forms-night; isolated worktree D:/Documents/ChatGPT/petoken-forms-night, base ad44b23. Only assets/v2_5/forms/night/ may change. No code/old-art/root-handoff edits, no merge or push. User authorized Pillow local masked composition and alignment.
- Updated 41-action/96-frame references are in FRAME_MANIFEST.json. Worktree source spec is obsolete (119); correct updated spec is in D:/Documents/ChatGPT/petoken-claude/docs/form_art/FORM_ART_1_NIGHT.md.
- BLOCKED: native imagegen again returned HTTP 429 usage_limit_reached for yawn_3, wake_stretch_2, curious_2, thinking_2. None returned images. Reset 1792029747 = 2026-10-14 22:02:27 America/Toronto. User explicitly chose waiting for native quota, not paid API. No CLI/API authorization.
- No complete FORMS_NIGHT_PREVIEW.png yet. Scratch partial-76.png shows current candidates.

## Verification and open review
- VALIDATION.json freshly checks all 76: RGBA 1254x1254, alpha 0..255, 76 distinct hashes, 20 blink outside-mask checks, 14 localized-variant outside-mask checks, 121 unchanged old PNG hashes. All 76 source lower alpha bands match.
- Lower alpha bands are limited contact checks; they do not prove exact head/hand/foot coordinates. Final per-pose anchors, seams, clothing consistency and animation continuity still need review. Runtime attachment integration untested.
- Current sleep pillow retains a dark bow/crystal prop. Review night-form consistency.
- Worried face restoration produced head/hair seams and old glove fragments. Its original rectangular source-face restoration is now disabled in production.py; retain registered native face, and specifically recheck head/hand anchors at final acceptance. Manual flat-fill eyelids were rejected; current worried_blink uses a native eye-only redraw with local masks over night base.

## Decisions and reproducible fixes
- Native edits use exact original pose plus canonical night_change_3 costume and night_idle_1. Variants use corresponding original variant plus completed night action base and canonical costume. No duplicate or armor-frame substitutions.
- production.py registers unchanged upper hair/face, adjusts lower-body height, restores local source face except hand/collar exclusion masks, and enforces source lower alpha band. Added exclusions for cheer, focus_read/tea, ready_go, packing, yawn; stretch_break uses a diagonal neckline exclusion. Hold-card auto face detector selected cream paper: inspected facial ROI override (490,515,840,680) fixes it.
- Existing curious_1 has a corrected closed collar and repaired horn-free head. Do not blindly recompose raw-curious_1.png; replay earlier registered head exec-2a4e19df-63af-424f-b148-57178c785bd1.png above y798 with mask-curious-head-repair.png (5px feather), then regenerate blink.
- Thinking/poked punctuation cleaned with local twinkles; replay cleanup_symbols.py if those bases change.
- grievance_2, worried_2 and focus_read_4 use inspected noncostume source deltas. local_variants.py restores source sweat mark and these three variants; it now replays final_worried_blink.py when native blink raw exists. Refresh before-worried-prop-fix.png after any new worried base composition. Do NOT use the abandoned worried_blink.py flat-fill experiment.
- save_variant.py composes native wardrobe variant, then retains base outside coarse source-delta component rectangles (expanded and feathered). Separate components keep unchanged hair/props stable. registered-*.png records full intermediate; variant-mask-*.png and record-*.json record exact local changes. Current coquette 2..4 used the earlier single bounding rectangle; either approach is retained in its record.
- yawn_1/2 old upper-arm/neck remnants corrected with expanded hand/neck exclusions, then yawn_2 localized again against corrected base.

## Exact next steps
1. After quota reset, resume yawn_3 / wake_stretch_2 / curious_2 / thinking_2, then remaining 16 listed below. Use one native edit per asset; preserve base areas via save_variant.py where source motion is local. Curious_2 tilts the whole head and needs full-pose review.
2. Review all 96 at full size and in animation: original anatomical anchors, hand/foot positions, head scale, seams, closed collar, no glove/armor remnants, no readable glyphs or detached alpha fragments. Revisit worried anchors, source-blink eye locality and pillow accessory consistency.
3. Run verify_checkpoint.py, create full FORMS_NIGHT_PREVIEW.png only when all 96 exist and reviewed. Refresh metadata/this handoff and commit locally. Do not push; report final hash and exact verification limits.

Remaining 20: yawn_3, wake_stretch_2, curious_2, thinking_2, shy_2, pout_2, dragged_2, dragged_3, dragged_4, hug_2, greet_morning_2, greet_night_2, cheer_2, clap_2, clap_3, peek_2, focus_read_2, focus_read_3, focus_tea_2, stretch_break_2.

## Resume tools and cache
- Python: C:/Users/fengz/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe (Pillow/numpy present).
- Scratch: C:/Users/fengz/.codex/generated_images/01a12eca-f0d4-7e80-b080-5757175f4f88/night-production.
- Important files: production.py, save_native.py, save_variant.py, local_variants.py, final_worried_blink.py, cleanup_symbols.py, verify_checkpoint.py; frames.json/spec.md/prompt.txt, original-sha256.json (121 originals), raw-*.png, registered-*.png, masks and per-frame record-*.json. Per-frame records override old composition.json; consolidated available provenance is committed in COMPOSITION.json. variant-jobs-remaining.json tracks remaining frames.
- Never rely on V8 result stores after a turn boundary. Native originals persist in the parent generated_images folder; selected copies are raw-*.png in scratch. The four prior-turn raws for sleep_3/bored_2/bored_3/yawn_2 were recovered from disk after stores expired; no generation repeated.
- Validation process exceeded the first 10s command wait; waited on session 43283 before reading the contact sheet. An initial premature view failed because the file was still being produced; final validation exited 0.
