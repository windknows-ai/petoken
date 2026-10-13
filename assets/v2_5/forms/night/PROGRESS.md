# Night form art handoff

## Current progress
- CHECKPOINT: 40/96 candidate frames saved, 28/41 action masters. Branch codex/forms-night; worktree D:\Documents\ChatGPT\petoken-forms-night; base ad44b23. Initial checkpoint d8e1a27 contains six. This continuation adds 34 candidates and refreshes validation/provenance.
- Exact approved 96-frame mapping and current file presence are in FRAME_MANIFEST.json. All original references exist. Source docs in this worktree are the obsolete 119-frame version; use the updated Claude checkout's FORM_ART_1_NIGHT.md or the persisted manifest.
- Only assets/v2_5/forms/night/ may change; do not edit code, old pictures or root instructions/handoffs. No merge/push. User explicitly authorized Pillow local composition/alignment.
- BLOCKED by the second built-in imagegen quota limit (HTTP 429 usage_limit_reached). Reset 1791926437 = 2026-10-13 17:20:37 America/Toronto. cheer_1/clap_1/peek_1/grievance_1 returned no image. No API/CLI fallback authorized.

## Decisions and fixes
- Built-in imagegen wardrobe edits; exact source facial/contact-band constraints via authorized Pillow. Moving variants still need generation/continuity composition; current blinks use local source eye masks and outside-mask equality.
- Source facial-mask rectangles had restored black glove pixels on working/yawn/thinking/bored/shy; production.py now excludes those hand regions. Review every new pose for remaining wardrobe artifacts.
- Curious_1 neckline initially incorrect: redrawn closed pajama collar. Redraw introduced a silver horn; repaired with earlier correct registered head above y798 (5px feather), retaining the corrected lower shirt. Do NOT blindly recompose curious_1 from raw-curious_1.png: replay this head repair, retained source raw exec-2a4e19df-63af-424f-b148-57178c785bd1.png and mask-curious-head-repair.png. Its blink has been regenerated after repair.
- sleep_3 source delta moves a raised foot, not just a prop: it requires a pajama/sock variant, not direct original-color copy.
- Full pose/rig/animation acceptance remains pending. VALIDATION.json refreshed for all 40: format/alpha, 40 distinct hashes, 11 blinks outside local masks exact, 121 old PNG hashes unchanged. Source lower alpha bands match; this does not prove anatomical anchors.

## Exact next steps
1. Generate remaining 13 action masters (starting cheer_1, clap_1, peek_1, grievance_1), using the latest fully closed-collar prompt and visible night_change_3 costume plus night_idle_1 references.
2. Add eye-only blinks as masters become available. Later nonblink variants need localized wardrobe edits; only grievance_2/worried_2 and purely facial focus_read_4 may copy original-only deltas when inspected.
3. Review all master/variant poses, head/foot/hand alignment, costume consistency, no lettering or armor/gloves, no isolated alpha fragments. Ensure curious head repair has no scalp seam. Replace source question/exclamation glyphs with nontext crescent/twinkle pictograms while retaining mark positions.
4. Verify all 96, original asset hashes and blink outside-mask pixels; create full FORMS_NIGHT_PREVIEW.png; update metadata/handoff, local commit only, report hash. Entire request is not complete.

## Resume tools
- Python: C:\Users\fengz\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe.
- Scratch: C:\Users\fengz\.codex\generated_images\01a12eca-f0d4-7e80-b080-5757175f4f88\night-production. production.py, frames.json/spec.md, original-sha256.json (121 old PNGs), raw-*.png, initial-*.png, masks, composition.json, per-frame record-*.json and preview PNGs. Per-frame records override the older aggregate; consolidate at final QA.
- Generation prompt: prompt.txt; remaining master queue: master-jobs-remaining.json. Native generated originals remain in parent generated_images folder.

## Latest continuation checkpoint
- Saved 34 more candidates, total 40. No complete FORMS_NIGHT_PREVIEW.png; 56 frames remain. Missing master queue: master-jobs-remaining.json in scratch.
- Source peek/grievance/worried/proud inspected for safe costume reuse; independent poses and visible gloves require redraws. No duplicate substitutions.
- Thinking/poked punctuation replaced with twinkles; masks/pre-edit images retained. cleanup_symbols.py replays the edits and thinking blink. First mask touched the bubble rim; corrected and visually checked.
- Diagnostic record-thinking_1.json read failed: that record is only in composition.json. COMPOSITION.json consolidates available records. No asset lost.
- Metadata script initially failed on Windows GBK default decoding; rerun with explicit UTF-8 reads/writes succeeded.
- sleep_1 retains the source pillow dark bow/crystal prop; review night-form consistency during final acceptance.
- Exact next step after quota reset: cheer_1/clap_1/peek_1/grievance_1, then the other nine remaining masters; derive blinks and finish moving variants. Preserve curious head repair and replay symbol cleanup if bases are recomposed.
