# Future V1.1 character assets (drop-in directory)

This directory is intentionally empty. It reserves the drop-in location for
future explicitly approved V1.1 chibi artwork. No final artwork exists yet;
do NOT generate, redraw, or invent assets here.

## Convention

Approved files, when supplied, use these exact names:

- `idle.png`
- `typing.png` (static fallback pose)
- `typing_1.png` / `typing_2.png` (optional tap-left / tap-right frames;
  used automatically when both exist, otherwise the static pose plus a
  subtle fallback tilt is rendered)
- `working.png` (Codex Working; distinct from typing)
- `microphone.png`
- `music.png`
- `guitar.png`

Requirements per file:

- transparent PNG with a real alpha channel, no opaque background
- any source resolution (higher is better; rendering scales it into the
  shared logical sprite box, so dimensions never affect layout)
- same feet/ground baseline placement as the V1.0 assets where possible

## Behavior

The registry in `pet_assets.py` prefers these files and falls back to the
verified V1.0 assets in `assets/` while a state file is missing. Missing
files are normal and never an error.

The V1.0 baseline files in `assets/` must NOT be moved, renamed, or
overwritten; `assets/skirk-pet.png` is SHA-pinned by the test suite.
