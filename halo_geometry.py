"""Compact projected halo geometry and its visible interactive footprints."""
from __future__ import annotations

import math
from typing import NamedTuple

from pet_geometry import STAR_PAIR_MARGIN as PAIR_MARGIN, clamp_position, footprint_in_workarea, footprints_collide


HIT_RADIUS = 22
LABEL_WIDTH, LABEL_HEIGHT, LABEL_TOP = 18, 14, 27
MAX_SAFE_STARS = 8
MARGIN_X, MARGIN_Y = HIT_RADIUS, LABEL_TOP + LABEL_HEIGHT + 1
DEFAULT_TILT = math.radians(12)

# Every pair on an eight-slot ellipse is at least 2*r*sin(pi/8) apart.
# Clear the label's furthest corner plus another disc, pair margin and
# worst relative pixel rounding. This is a hit-geometry floor, not art tuning.
MIN_AXIS = math.ceil((math.hypot(LABEL_WIDTH / 2, LABEL_TOP + LABEL_HEIGHT)
                      + HIT_RADIUS + PAIR_MARGIN + math.sqrt(2))
                     / (2 * math.sin(math.pi / MAX_SAFE_STARS)))


class HaloPose(NamedTuple):
    cx: float
    cy: float
    rx: float
    ry: float
    tilt: float  # Radians, like the phase passed to project().


class HaloPlacement(NamedTuple):
    pet_rect: tuple
    pose: HaloPose | None


def projected_bounds(pose):
    """Conservative closed-cycle hit/number bounds, including pixel padding."""
    c, s = math.cos(pose.tilt), math.sin(pose.tilt)
    ex = math.hypot(pose.rx * c, pose.ry * s) + MARGIN_X
    ey = math.hypot(pose.rx * s, pose.ry * c) + MARGIN_Y
    return pose.cx - ex, pose.cy - ey, pose.cx + ex, pose.cy + ey


def _axis_fit(limit, dx, dy, c, s):
    """Largest fraction between the safe circle and desired ellipse."""
    a = (dx * c) ** 2 + (dy * s) ** 2
    b = 2 * MIN_AXIS * (dx * c * c + dy * s * s)
    if a == 0:
        return 1.0
    # Stable positive quadratic root; no repeated search or visual tolerance.
    remaining = max(0.0, limit * limit - MIN_AXIS * MIN_AXIS)
    return 2 * remaining / (b + math.sqrt(b * b + 4 * a * remaining))


def fit_pose(pet_rect, screen_rect):
    """Fit a close halo into an inclusive workarea without shrinking its hits.

    Supports up to eight equally spaced stable slots. Tiny workareas that
    cannot hold those fixed interactive footprints are explicitly rejected;
    an overlapping or clipped fallback is never presented as a valid pose.
    """
    px, py, width, height = pet_rect
    left, top, right, bottom = screen_rect
    if (not all(math.isfinite(v) for v in (*pet_rect, *screen_rect))
            or width <= 0 or height <= 0 or right < left or bottom < top):
        raise ValueError('invalid pet rectangle or workarea')
    x_limit = (right + 1 - left) / 2 - MARGIN_X
    y_limit = (bottom + 1 - top) / 2 - MARGIN_Y
    if min(x_limit, y_limit) < MIN_AXIS:
        raise ValueError('workarea cannot hold eight distinct halo hit targets')
    rx, ry = max(MIN_AXIS, width * 0.58), max(MIN_AXIS, height * 0.25)
    c, s = math.cos(DEFAULT_TILT), math.sin(DEFAULT_TILT)
    dx, dy = rx - MIN_AXIS, ry - MIN_AXIS
    fraction = min(1.0, _axis_fit(x_limit, dx, dy, c, s),
                   _axis_fit(y_limit, dy, dx, c, s))
    rx, ry = MIN_AXIS + dx * fraction, MIN_AXIS + dy * fraction
    ex = math.hypot(rx * c, ry * s) + MARGIN_X
    ey = math.hypot(rx * s, ry * c) + MARGIN_Y
    cx = min(max(px + width / 2, left + ex), right + 1 - ex)
    cy = min(max(py + height * 0.60, top + ey), bottom + 1 - ey)
    return HaloPose(cx, cy, rx, ry, DEFAULT_TILT)


def clamp_composition(pet_rect, screen_rect):
    """Clamp the pet and its centered closed-cycle halo as one composition.

    Pet origins are integer QWidget coordinates; dimensions are preserved.
    A None pose means the workarea cannot contain the body and eight safe
    fixed-size hits together. The returned pet is still normally clamped;
    callers may hide or clip decoration, but cannot claim safe halo hits.
    """
    px, py, width, height = pet_rect
    left, top, right, bottom = screen_rect
    if (not all(math.isfinite(v) for v in (*pet_rect, *screen_rect))
            or width <= 0 or height <= 0 or right < left or bottom < top):
        raise ValueError('invalid pet rectangle or workarea')
    x, y = clamp_position(round(px), round(py), width, height, screen_rect)
    fallback = HaloPlacement((x, y, width, height), None)
    if width > right + 1 - left or height > bottom + 1 - top:
        return fallback

    # The nearest body-contained integer origin to the workarea midpoint
    # gives the largest symmetric halo, including an odd-width pixel grid.
    best_x, best_y = clamp_position(
        round((left + right + 1) / 2 - width / 2),
        round((top + bottom + 1) / 2 - height * .60),
        width, height, screen_rect)
    cx, cy = best_x + width / 2, best_y + height * .60
    x_limit = min(cx - left, right + 1 - cx) - MARGIN_X
    y_limit = min(cy - top, bottom + 1 - cy) - MARGIN_Y
    if min(x_limit, y_limit) < MIN_AXIS:
        return fallback

    rx, ry = max(MIN_AXIS, width * .58), max(MIN_AXIS, height * .25)
    c, s = math.cos(DEFAULT_TILT), math.sin(DEFAULT_TILT)
    dx, dy = rx - MIN_AXIS, ry - MIN_AXIS
    fraction = min(1.0, _axis_fit(x_limit, dx, dy, c, s),
                   _axis_fit(y_limit, dy, dx, c, s))
    rx, ry = MIN_AXIS + dx * fraction, MIN_AXIS + dy * fraction
    ex = math.hypot(rx * c, ry * s) + MARGIN_X
    ey = math.hypot(rx * s, ry * c) + MARGIN_Y
    # Epsilon corrects analytic-root roundoff before integer ceil/floor.
    xmin = math.ceil(max(left, left + ex - width / 2) - 1e-9)
    xmax = math.floor(min(right + 1 - width, right + 1 - ex - width / 2) + 1e-9)
    ymin = math.ceil(max(top, top + ey - height * .60) - 1e-9)
    ymax = math.floor(min(bottom + 1 - height, bottom + 1 - ey - height * .60) + 1e-9)
    x, y = min(max(round(px), xmin), xmax), min(max(round(py), ymin), ymax)
    return HaloPlacement((x, y, width, height),
                         HaloPose(x + width / 2, y + height * .60,
                                  rx, ry, DEFAULT_TILT))


def project(pose, angle_rad):
    """Return (screen x, screen y, depth), back<0 and front>0."""
    x, y = pose.rx * math.cos(angle_rad), pose.ry * math.sin(angle_rad)
    c, s = math.cos(pose.tilt), math.sin(pose.tilt)
    return pose.cx + x * c - y * s, pose.cy + x * s + y * c, math.sin(angle_rad)


def phase_offsets(stable_slots):
    """Equal radians by stable slot rank, independent of input/poll order."""
    slots = sorted(set(stable_slots))
    return {slot: math.tau * rank / len(slots) for rank, slot in enumerate(slots)}


def interactive_footprint(x, y):
    """Disc and number rectangle; transparent widget bounds are irrelevant."""
    return ((x, y, HIT_RADIUS),
            (x - LABEL_WIDTH / 2, y + LABEL_TOP, LABEL_WIDTH, LABEL_HEIGHT))


def frame_valid(centers, screen_rect):
    """Usable onscreen hits and distinct tasks; body occlusion is paint policy."""
    footprints = [interactive_footprint(*center) for center in centers.values()]
    return (all(footprint_in_workarea(item, screen_rect) for item in footprints)
            and not any(footprints_collide(first, second)
                        for i, first in enumerate(footprints)
                        for second in footprints[i + 1:]))
