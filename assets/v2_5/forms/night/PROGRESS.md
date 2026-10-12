# Night form art handoff

## Current progress
- PARTIAL: 6 of the approved 96 frames saved as candidates: idle_1, idle_blink, typing_1, typing_2, microphone_1, guitar_1. Five of 41 actions have candidate coverage. No complete overview; no merge or push.
- Branch codex/forms-night; isolated worktree D:\Documents\ChatGPT\petoken-forms-night; base ad44b23. Keep Claude checkout and all shared code/old pictures unchanged.
- Source request updated by user: use D:\Documents\ChatGPT\petoken-claude\docs\form_art\FORM_ART_1_NIGHT.md (96 frames). All 96 references exist. FRAME_MANIFEST.json is the exact approved mapping persisted here.
- User explicitly authorized Pillow local masked composition and pixel alignment; missing-28 issue is resolved, not pending.
- 6 canvas/RGBA/true-alpha checks and foot-band alpha comparisons pass. idle blink changes only the eye mask; 121 existing source PNG hashes unchanged. Full pose/seam/native animation acceptance remains unverified; see VALIDATION.json.

## Decisions
- Built-in imagegen for wardrobe drawing, Pillow only for permitted registration/local composition. Reused existing night_change_3 for idle; no invented poses or duplicate fallback frames.
- First automatic color-mask/skin-box registration trials were rejected because of seams and wrong scale. Current hair/face registration plus narrow facial/contact masks produced the reviewed six candidates; review each future pose rather than assuming those static checks prove full body geometry.
- Only add files under assets/v2_5/forms/night/. Latest explicit scope overrides historical V1.5 ownership and instruction-sync writes outside this folder.

## Blocker
- Six further imagegen jobs returned HTTP 429 usage_limit_reached; no new images returned. Reported reset 2026-10-12 16:45:33 America/Toronto (1791837933). Do not retry repeatedly before reset.
- CLI/API fallback requires explicit user selection and OPENAI_API_KEY; no paid API used or authorized.

## Exact next steps
1. After quota becomes available, generate codex_working_1, music_1, celebrate_1, sad_1, wave_1; idle_1 is already reused, not a required retry.
2. Finish remaining masters from FRAME_MANIFEST.json, then moving variants. Copy original facial-only/prop-only deltas where appropriate; derive all blinks with exact eye-only masks. Never restore original armor from motion deltas.
3. Review all source-relative head/foot/hand locations and local composition seams, fix any issues. Static contact-strip equality is only one placement check.
4. Validate all 96 distinct 1254x1254 RGBA sprites, no text, true background alpha, eye-only blink changes and original-asset hashes; produce FORMS_NIGHT_PREVIEW.png covering the complete set.
5. Update this handoff, local commit of the completed art only, report commit ID; do not push/merge.

## Resume tools
- Python: C:\Users\fengz\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe (WindowsApps python silently exits 1).
- Durable scratch: C:\Users\fengz\.codex\generated_images\01a12eca-f0d4-7e80-b080-5757175f4f88\night-production (production.py, frames.json, spec.md, original-sha256.json, masks, composition.json and partial-6.png).
- Initial raw imagegen candidates copied into that cache for recovery. Original generated files remain under the same thread's generated_images directory.
