"""Logical character geometry for the desktop pet.

Separates three concerns that V1.0 tangled together:

- source asset pixels (``assets/skirk-*.png``, ~1080 px, never modified here),
- logical pet size (device-independent pixels the UI is laid out in),
- physical rendering (logical size times the screen devicePixelRatio).

V1.0 baseline: 242x378 window, 214x290 sprite box at y=82.
Companion redesign (V1.1 character-led slice): ``CHARACTER_SCALE`` (0.68) of
the baseline apparent size, so the desktop pet holds its own next to the
wider companion panel. One shared sprite box and one feet/ground anchor for
every state, bubble geometry unchanged. Future approved chibi assets only
need to fill the same logical sprite box; no per-state offsets exist to
re-tune.
"""
from __future__ import annotations

# V1.0 baseline, kept as the documented reference. Do not change.
BASELINE_WINDOW = (242, 378)
BASELINE_SPRITE = (214, 290)
BASELINE_SPRITE_Y = 82

# Companion presentation scale vs the V1.0 baseline apparent size.
CHARACTER_SCALE = 0.68

WINDOW_WIDTH = BASELINE_WINDOW[0]
# Compact Token card (V1.1 step 12): project + status on line one, live
# Tokens on line two. Smaller than the V1.0 240x70 bubble.
BUBBLE_RECT = (1, 1, 240, 58)
BUBBLE_TEXT_WIDTH = 216

SPRITE_WIDTH = int(BASELINE_SPRITE[0] * CHARACTER_SCALE)
SPRITE_HEIGHT = int(BASELINE_SPRITE[1] * CHARACTER_SCALE)
SPRITE_X = (WINDOW_WIDTH - SPRITE_WIDTH) // 2
SPRITE_Y = 64
WINDOW_HEIGHT = SPRITE_Y + SPRITE_HEIGHT + 7

# Feet/ground anchor: bottom-center of the shared sprite box. Every state
# draws into the same box, so switching states cannot shift the feet.
ANCHOR = (WINDOW_WIDTH // 2, SPRITE_Y + SPRITE_HEIGHT)
REACTION_PIVOT = (WINDOW_WIDTH // 2, SPRITE_Y + SPRITE_HEIGHT // 2)

# Idle motion amplitudes, scaled with the character (V1.0: 3 and 1.5).
BOB_AMPLITUDE = 3 * CHARACTER_SCALE
TYPING_AMPLITUDE = 1.5 * CHARACTER_SCALE

# Default screen margins preserved from the V1.0 placement.
MARGIN_RIGHT = 38
MARGIN_BOTTOM = 22


def window_size():
    return (WINDOW_WIDTH, WINDOW_HEIGHT)


def sprite_rect(offset_y=0):
    return (SPRITE_X, SPRITE_Y + offset_y, SPRITE_WIDTH, SPRITE_HEIGHT)


def bubble_rect():
    return BUBBLE_RECT


def anchor():
    return ANCHOR


def device_pixels(logical, dpr):
    return max(1, round(logical * dpr))


def clamp_position(x, y, width, height, screen):
    """Clamp a top-left window position inside a screen rect.

    ``screen`` is ``(left, top, right, bottom)`` in the same coordinate
    space; returns the clamped ``(x, y)``. Pure function so DPI and
    multi-monitor clamping stay unit-testable.
    """
    left, top, right, bottom = screen
    return (max(left, min(x, right - width + 1)),
            max(top, min(y, bottom - height + 1)))
