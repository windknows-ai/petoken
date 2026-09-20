"""Logical bounds for the anchored desktop companion.

Approved square chibi sources occupy a 256x256 box. Rendering fits each source
without stretching and aligns its feet to the same anchor at every screen DPR.
The panel is an adjacent satellite; it never owns or relocates the character.
"""
from __future__ import annotations

# V1.0 baseline, kept as the documented reference. Do not change.
BASELINE_WINDOW = (242, 378)
BASELINE_SPRITE = (214, 290)
BASELINE_SPRITE_Y = 82

# Motion amplitude scale; artwork has its own square logical bounds.
CHARACTER_SCALE = 1.0

WINDOW_WIDTH = 272
# Compact Token card (V1.1 step 12): project + status on line one, live
# Tokens on line two. Smaller than the V1.0 240x70 bubble.
BUBBLE_RECT = (16, 1, 240, 58)
BUBBLE_TEXT_WIDTH = 216

SPRITE_WIDTH = 256
SPRITE_HEIGHT = 256
SPRITE_X = (WINDOW_WIDTH - SPRITE_WIDTH) // 2
SPRITE_Y = 64
WINDOW_HEIGHT = SPRITE_Y + SPRITE_HEIGHT + 10

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


def panel_position(pet, panel_size, screen, gap=12):
    """Place the satellite on the pet's screen without moving its anchor.

    Prefer right, then left. When neither side fits, choose the roomier side
    and clamp only the panel. An undersized work area may necessarily overlap.
    Rectangles use (x, y, width, height); screen uses inclusive edges.
    """
    x, y, width, height = pet
    pw, ph = panel_size
    left, top, right, bottom = screen
    right_space = right + 1 - (x + width + gap)
    left_space = x - gap - left
    use_right = right_space >= pw or (left_space < pw and right_space >= left_space)
    px = x + width + gap if use_right else x - gap - pw
    return clamp_position(px, y + height - ph, pw, ph, screen)
