"""Logical bounds for the anchored desktop companion.

Approved square chibi sources occupy a 256x256 box. Rendering fits each source
without stretching and aligns its feet to the same anchor at every screen DPR.
The panel is an adjacent satellite; it never owns or relocates the character.
"""
from __future__ import annotations

from functools import lru_cache as _lru_cache
import heapq
import math

# V1.0 baseline, kept as the documented reference. Do not change.
BASELINE_WINDOW = (242, 378)
BASELINE_SPRITE = (214, 290)
BASELINE_SPRITE_Y = 82

# Motion amplitude scale; artwork has its own square logical bounds.
CHARACTER_SCALE = 1.0

# User-adjustable character size. 100% is the approved V1.1 size defined by
# the constants below; the window, sprite box, anchor, bubble and amplitudes
# all scale proportionally so the composition never distorts.
PET_SCALE_DEFAULT = 100
PET_SCALE_MIN = 50
PET_SCALE_MAX = 150

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


def normalize_pet_scale(value):
    """Normalize a saved character-size percentage into the supported range.

    Missing or corrupted values fall back to 100% (the approved size), so an
    upgrade never silently resizes an existing user's pet. Never raises.
    """
    try:
        if isinstance(value, bool):
            return PET_SCALE_DEFAULT
        scale = int(round(float(value)))
    except (TypeError, ValueError, ArithmeticError):
        return PET_SCALE_DEFAULT
    return max(PET_SCALE_MIN, min(scale, PET_SCALE_MAX))


def _scaled(logical, percent):
    return max(1, round(logical * percent / 100))


def scaled_window_size(percent=PET_SCALE_DEFAULT):
    percent = normalize_pet_scale(percent)
    return (_scaled(WINDOW_WIDTH, percent), _scaled(WINDOW_HEIGHT, percent))


def scaled_sprite_rect(percent=PET_SCALE_DEFAULT, offset_y=0):
    percent = normalize_pet_scale(percent)
    width, height = scaled_window_size(percent)
    side = _scaled(SPRITE_WIDTH, percent)
    x = (width - side) // 2
    y = _scaled(SPRITE_Y, percent) + offset_y
    return (x, y, side, side)


def scaled_anchor(percent=PET_SCALE_DEFAULT):
    percent = normalize_pet_scale(percent)
    width, _ = scaled_window_size(percent)
    x, y, w, h = scaled_sprite_rect(percent)
    return (width // 2, y + h)


def scaled_bubble_rect(percent=PET_SCALE_DEFAULT):
    percent = normalize_pet_scale(percent)
    bx, by, bw, bh = BUBBLE_RECT
    return (_scaled(bx, percent), _scaled(by, percent),
            _scaled(bw, percent), _scaled(bh, percent))


def scaled_bubble_text_width(percent=PET_SCALE_DEFAULT):
    return _scaled(BUBBLE_TEXT_WIDTH, normalize_pet_scale(percent))


def scaled_reaction_pivot(percent=PET_SCALE_DEFAULT):
    percent = normalize_pet_scale(percent)
    width, _ = scaled_window_size(percent)
    x, y, w, h = scaled_sprite_rect(percent)
    return (width // 2, y + h // 2)


def scaled_amplitudes(percent=PET_SCALE_DEFAULT):
    percent = normalize_pet_scale(percent)
    return (BOB_AMPLITUDE * percent / 100, TYPING_AMPLITUDE * percent / 100)


def clamp_position(x, y, width, height, screen):
    """Clamp a top-left window position inside a screen rect.

    ``screen`` is ``(left, top, right, bottom)`` in the same coordinate
    space; returns the clamped ``(x, y)``. Pure function so DPI and
    multi-monitor clamping stay unit-testable.
    """
    left, top, right, bottom = screen
    return (max(left, min(x, right - width + 1)),
            max(top, min(y, bottom - height + 1)))


# Multi-task panel windows (V1.3 Slice C): one compact window per verified
# working task beyond the primary surface. Fixed logical sizes keep the
# slot -> position mapping deterministic and unit-testable; OpenCode
# windows are taller because they carry the full recorded-category set.
TASK_WINDOW_GAP = 12
TASK_WINDOW_CODEX = (252, 208)
TASK_WINDOW_OPENCODE = (252, 336)


def task_window_size(provider_id):
    """Fixed logical window size for one task panel by provider."""
    return TASK_WINDOW_OPENCODE if provider_id == 'opencode' else TASK_WINDOW_CODEX


# Multi-task star ring (V1.3 Slice D2A): one crystalline task star per
# verified working task, arranged in a static ring around the pet.
# D2B will animate these same anchors (slow orbit + breathing); D2A
# holds the static snapshot so shape/size/color/arrangement can be
# approved first. No timers here — pure geometry only.
TASK_STAR_SIZE = (112, 112)
TASK_STAR_CENTER = (56, 48)
TASK_STAR_HIT_R = 38
TASK_STAR_CORE_R = 7
TASK_STAR_RAY_V = 30
TASK_STAR_RAY_H = 22
TASK_STAR_WAIST = 5
TASK_ORB_DRAG_THRESHOLD_PX = 6

# Final-placement clearance contracts (D2A geometry blocker).
# Hit disc radius is TASK_STAR_HIT_R: two centers need >= 76 px, plus
# a small margin. Never shrink the hit target to pass layout.
STAR_MIN_CENTER_DIST = 78
# Pet exclusion margin: hit radius plus a small margin, so the final
# visible rays (30 px) and hit disc both clear the companion window.
STAR_PET_CLEAR = 44
# Canonical interactive footprint of one task surface, widget-local.
# MUST match TaskOrbWindow exactly: the OS mask is the ellipse
# inscribed in the hit square united with this label strip, and the
# press handler uses the same label geometry. Single source of
# truth so validation and UI can never disagree.
STAR_LABEL_RECT = (0, 86, 112, 24)
# Pairwise margins: touching boundaries count as invalid, and absorb
# mask rasterization (<=1 px). Pet margin is larger (humans notice a
# star glued to the hub more than two stars nearly touching).
STAR_PAIR_MARGIN = 2
STAR_PET_MARGIN = 6

# D2B celestial motion: a true star ring around the pet hub wherever
# one fits, safe arcs only as constrained-layout fallback. A ring is a
# rigid circle (preferred) or ellipse (fallback) with a common
# direction, equal slot-rank spacing, and continuous 0-360-720 phase —
# never an out-and-back reversal. Ring candidates are validated phase
# by phase against the same final footprint rules as static
# placement. (Early small anchor radii could not rotate — measured
# 0/24 — but realistic ring radii validate fully in normal centered
# layouts, e.g. r 305..475 px on 1919x1079.) Arc periods scale with
# amplitude for a constant calm peak speed; ring periods scale with
# radius for a constant calm tangential speed.
MOTION_TICK_MS = 40
ORBIT_ARC_CANDIDATES_DEG = (90.0, 60.0, 40.0, 25.0, 12.0)
ORBIT_SWEEP_SAMPLES = 24
# Full-ring search: common clockwise direction (+1: top -> right),
# fixed base phase, 120 selection samples (every 3 degrees).
RING_DIRECTION = +1.0
RING_BASE_DEG = 0.0
RING_SWEEP_SAMPLES = 120
RING_RADIUS_STEP_PX = 10.0
RING_ELLIPSE_STEP_PX = 30.0
RING_ELLIPSE_COMBO_CAP = 80
RING_PERIOD_MIN_S = 28.0
RING_PERIOD_MAX_S = 45.0
RING_TARGET_SPEED_PX_S = 55.0
# Recomposition glide: adaptive duration from actual survivor travel
# so no 40 ms frame looks like a snap. Smoothstep peaks at 1.5x mean
# speed; duration targets 7 px/frame nominal at the tangential peak
# (worst diagonal-plus-quantization Manhattan stays under the hard
# 16 px test bound), floored so tiny moves stay snappy. There is
# intentionally no upper cap: long hauls glide longer instead of
# sprinting past the per-frame budget on large work areas.
RING_BLEND_MIN_S = 0.4
# Legacy upper bound, retained for compatibility only. The duration
# helper no longer applies it (uncapped durations preserve the
# 16 px per 40 ms budget on long paths).
RING_BLEND_MAX_S = 10.0
RING_BLEND_TARGET_PX_PER_FRAME = 7.0
RING_BLEND_FRAME_S = 0.04
RING_BLEND_EASE_PEAK = 1.5
# Anti-deadlock: a glide that cannot advance past a blocked path
# (untested bulk corner) is abandoned after this much hold so the
# ring resumes on its validated path instead of freezing forever.
RING_BLEND_STALL_LIMIT_S = 1.0
# Trail bounds: short, fading, strictly bounded history. Samples
# expire after ~1.2 s; visibility needs a real span, so stillness
# paints nothing.
TRAIL_MAX_SAMPLES = 10
TRAIL_MAX_AGE_S = 1.2
TRAIL_VISIBILITY_SPAN_PX = 0.5


def star_center_to_window_position(cx, cy):
    """Authoritative float-center to integer QWidget top-left.

    The ONLY quantization rule: round-half-even to integers, exactly
    what the task surface receives via QWidget.move. The solver and
    the UI share this helper, so a validated candidate IS the
    on-screen geometry — no second rounding transform exists.
    """
    return (int(round(cx - TASK_STAR_CENTER[0])),
            int(round(cy - TASK_STAR_CENTER[1])))


def star_window_footprint(wx, wy):
    """Final integer interactive primitives for a placed surface.

    Returns (disc, label) with disc = (center_x, center_y, radius)
    and label = (x, y, w, h); both integer, both in screen
    coordinates, both exactly matching the widget mask/hit-test.
    """
    cx, cy = wx + TASK_STAR_CENTER[0], wy + TASK_STAR_CENTER[1]
    lx, ly, lw, lh = STAR_LABEL_RECT
    return ((cx, cy, TASK_STAR_HIT_R), (wx + lx, wy + ly, lw, lh))


PARKING_WORK_BATCH_PIXELS = 256
PARKING_WORK_YIELD_S = 0.001


def parking_route(start, home, static_windows, pet, screen, yield_work=None):
    """Bounded integer route among stationary full footprints.

    Validate every pixel between lattice nodes. Runtime consumes these same
    pixels, so it cannot encounter an unsampled edge collision.
    """
    obstacles = [(pos, star_window_footprint(*pos))
                 for pos in static_windows.values()]
    left, top, right, bottom = screen
    width, height = TASK_STAR_SIZE
    checked = {}

    def valid(pos):
        if pos not in checked:
            x, y = pos
            footprint = star_window_footprint(x, y)
            checked[pos] = (
                left <= x <= right + 1 - width
                and top <= y <= bottom + 1 - height
                and not footprint_hits_pet(footprint, pet)
                and not any(
                    abs(x - pos[0]) < width + STAR_PAIR_MARGIN
                    and abs(y - pos[1]) < height + STAR_PAIR_MARGIN
                    and footprints_collide(footprint, obstacle)
                    for pos, obstacle in obstacles))
            if yield_work is not None and len(checked) % PARKING_WORK_BATCH_PIXELS == 0:
                yield_work()
        return checked[pos]

    def line(first, last):
        dx, dy = last[0] - first[0], last[1] - first[1]
        steps = max(abs(dx), abs(dy))
        pixels = []
        for step in range(1, steps + 1):
            pos = (round(first[0] + dx * step / steps),
                   round(first[1] + dy * step / steps))
            if not valid(pos):
                return None
            pixels.append(pos)
        return pixels

    def connect(first, last):
        direct = line(first, last)
        if direct is not None:
            return direct
        for corner in ((last[0], first[1]), (first[0], last[1])):
            first_leg = line(first, corner)
            if first_leg is not None:
                last_leg = line(corner, last)
                if last_leg is not None:
                    return first_leg + last_leg
        return None

    if not valid(start) or not valid(home):
        return None
    direct = connect(start, home)
    if direct is not None:
        return [start] + direct

    def remaining(pos):
        return abs(pos[0] - home[0]) + abs(pos[1] - home[1])

    frontier = [(remaining(start), 0, start)]
    costs = {start: 0}
    parents, edges = {}, {}
    visited = 0
    # ponytail: bounded eight-pixel A* for desktop parking; finer corridors
    # require a finer lattice, never an unchecked connector or visible snap.
    while frontier and visited < 6000:
        _, negative_cost, pos = heapq.heappop(frontier)
        cost = -negative_cost
        if cost != costs[pos]:
            continue
        visited += 1
        if remaining(pos) <= 32:
            final = connect(pos, home)
            if final is not None:
                chain = []
                cursor = pos
                while cursor != start:
                    chain.append(edges[cursor])
                    cursor = parents[cursor]
                return ([start]
                        + [pixel for edge in reversed(chain) for pixel in edge]
                        + final)
        for dx, dy in ((-8, 0), (8, 0), (0, -8), (0, 8),
                       (-8, -8), (-8, 8), (8, -8), (8, 8)):
            neighbor = (pos[0] + dx, pos[1] + dy)
            next_cost = cost + abs(dx) + abs(dy)
            if next_cost >= costs.get(neighbor, math.inf) or not valid(neighbor):
                continue
            edge = line(pos, neighbor)
            if edge is None:
                continue
            costs[neighbor] = next_cost
            parents[neighbor], edges[neighbor] = pos, edge
            heapq.heappush(frontier, (next_cost + remaining(neighbor),
                                     -next_cost, neighbor))
    return None


def _point_rect_dist_sq(px, py, rect):
    """Squared distance from a point to a rect (0 when inside)."""
    rx, ry, rw, rh = rect
    dx = max(rx - px, 0, px - (rx + rw))
    dy = max(ry - py, 0, py - (ry + rh))
    return dx * dx + dy * dy


def _rects_overlap(a, b, margin):
    """Whether two integer rects overlap within a margin."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return (ax < bx + bw + margin and bx < ax + aw + margin
            and ay < by + bh + margin and by < ay + ah + margin)


def footprints_collide(first, second):
    """Full pairwise interactive collision: circle-circle, both
    circle-label directions, and label-label. Conservative: exact
    boundary touches count as collisions."""
    (ax, ay, ar), alabel = first
    (bx, by, br), blabel = second
    margin = STAR_PAIR_MARGIN
    if (ax - bx) ** 2 + (ay - by) ** 2 < (ar + br + margin) ** 2:
        return True
    if _point_rect_dist_sq(ax, ay, blabel) < (ar + margin) ** 2:
        return True
    if _point_rect_dist_sq(bx, by, alabel) < (br + margin) ** 2:
        return True
    return _rects_overlap(alabel, blabel, margin)


def footprint_hits_pet(footprint, pet):
    """Whether a final footprint intrudes into the pet exclusion."""
    (cx, cy, radius), label = footprint
    x, y, width, height = pet
    margin = STAR_PET_MARGIN
    if _point_rect_dist_sq(cx, cy, (x, y, width, height)) < (radius + margin) ** 2:
        return True
    return _rects_overlap(
        label, (x, y, width, height), margin)


def footprint_in_workarea(footprint, screen):
    """Whether the final interactive footprint stays usable onscreen."""
    (cx, cy, radius), label = footprint
    left, top, right, bottom = screen
    if not (left <= cx - radius and cx + radius <= right + 1
            and top <= cy - radius and cy + radius <= bottom + 1):
        return False
    lx, ly, lw, lh = label
    return (left <= lx and lx + lw <= right + 1
            and top <= ly and ly + lh <= bottom + 1)


def star_centers_valid(centers, pet, screen):
    """Center-level validity for orbit-envelope sampling.

    Same contracts as the footprint validator (bounds as true center
    ranges, pet exclusion, pairwise hit clearance) but computed
    directly on centers for cheap phase sampling. The solver's final
    acceptance still uses full integer footprints; this is the fast
    path for choosing a safe swing amplitude.
    """
    left, top, right, bottom = screen
    lo_x = left + TASK_STAR_CENTER[0]
    hi_x = right - (TASK_STAR_SIZE[0] - TASK_STAR_CENTER[0]) + 1
    lo_y = top + TASK_STAR_CENTER[1]
    hi_y = bottom - (TASK_STAR_SIZE[1] - TASK_STAR_CENTER[1]) + 1
    if hi_x < lo_x or hi_y < lo_y:
        return False
    points = [centers[item] for item in sorted(centers)]
    for cx, cy in points:
        if not (lo_x <= cx <= hi_x and lo_y <= cy <= hi_y):
            return False
    x, y, width, height = pet
    for cx, cy in points:
        if (x - STAR_PET_CLEAR <= cx <= x + width + STAR_PET_CLEAR
                and y - STAR_PET_CLEAR <= cy <= y + height + STAR_PET_CLEAR):
            return False
    for i in range(len(points)):
        for j in range(i + 1, len(points)):
            dx = points[i][0] - points[j][0]
            dy = points[i][1] - points[j][1]
            if dx * dx + dy * dy < STAR_MIN_CENTER_DIST ** 2:
                return False
    return True


def orbit_center_at(pet_center_x, pet_center_y, radius_x, radius_y,
                    angle_deg):
    """One parametric orbit position (pure, degrees, 0 = up).

    The D2B motion primitive: every visible star travels a
    pet-centered circle (radius_x == radius_y) or arc, so the whole
    ring reads as one coherent orbital system around the hub.
    """
    import math
    theta = math.radians(angle_deg)
    return (pet_center_x + radius_x * math.sin(theta),
            pet_center_y - radius_y * math.cos(theta))


def arc_angle_at(base_deg, amplitude_deg, direction, cycle_frac):
    """One-sided tangent arc position along an orbit (pure).

    Starts exactly at the home angle, ventures out to
    base + direction * amplitude at half cycle, and retraces back —
    smooth (zero velocity) at both ends, so composition changes and
    hover resumes never teleport. Shared by envelope selection and
    the per-tick runtime so both agree exactly.
    """
    import math
    return (base_deg + direction * amplitude_deg
            * (1.0 - math.cos(2.0 * math.pi * cycle_frac)) / 2.0)


def arc_period_s(amplitude_deg):
    """Arc out-and-back period scaled for a calm constant peak speed."""
    return 8.0 + 0.5 * amplitude_deg


def ring_period_s(radius_eff_px):
    """Ring revolution period for a calm constant tangential speed.

    Target RING_TARGET_SPEED_PX_S clamped into [MIN, MAX] seconds:
    small rings stay unhurried, huge rings stay unmistakable.
    """
    import math
    period = 2.0 * math.pi * radius_eff_px / RING_TARGET_SPEED_PX_S
    return min(RING_PERIOD_MAX_S, max(RING_PERIOD_MIN_S, period))


def ring_abs_angle_deg(cx, cy, hub_x, hub_y):
    """Absolute ring angle of a center around a hub (inverse of
    orbit_center_at: 0 = up, clockwise positive). Pure."""
    import math
    return math.degrees(math.atan2(cx - hub_x, -(cy - hub_y))) % 360.0


def ring_blend_ease(u):
    """Smoothstep easing for recomposition glides (pure, 0..1)."""
    u = min(1.0, max(0.0, u))
    return u * u * (3.0 - 2.0 * u)


def ring_shortest_delta_deg(from_deg, to_deg):
    """Shortest-path signed angular delta in (-180, 180] (pure)."""
    return (to_deg - from_deg + 540.0) % 360.0 - 180.0


def ring_blend_duration_s(travel_px):
    """Adaptive recomposition duration for a bounded frame speed.

    Peak eased velocity is EASE_PEAK x mean, so duration targets
    TARGET px per FRAME_S tick at the peak, floored into
    [MIN, +inf) seconds. There is intentionally no upper clamp:
    capping the duration would raise the eased peak frame step
    above the D2B 16 px per 40 ms budget on long paths (large
    work areas), so long hauls glide longer instead of sprinting.
    Deterministic, pure.
    """
    duration = (max(0.0, travel_px) * RING_BLEND_EASE_PEAK
                * RING_BLEND_FRAME_S / RING_BLEND_TARGET_PX_PER_FRAME)
    return max(RING_BLEND_MIN_S, duration)


def ring_search_bounds(pet_rect, screen_rect):
    """Geometry-derived ring search bounds (pure).

    Returns (hub, circle_lo, circle_hi, rx_lo, rx_hi, ry_lo, ry_hi):
    hub is the pet center; *_lo clears the pet rect on-axis with star
    disc + pet margins plus 1 px strictness; *_hi keeps the 112x112
    window (center +/- (56, 48) top-left anchored) inside the work
    area. Empty ranges (hi < lo) mean no ring fits that axis: the
    caller falls back to arcs. Nothing here is validated — the sweep
    below stays authoritative.
    """
    import math
    px, py, pw, ph = pet_rect
    left, top, right, bottom = screen_rect
    hub = (px + pw / 2.0, py + ph / 2.0)
    clear = TASK_STAR_HIT_R + STAR_PET_MARGIN + 1.0
    circle_lo = max(pw, ph) / 2.0 + clear
    rx_lo = pw / 2.0 + clear
    ry_lo = ph / 2.0 + clear
    rx_hi = min(hub[0] - TASK_STAR_CENTER[0] - left,
                (right + 1) - TASK_STAR_CENTER[0] - hub[0])
    ry_hi = min(hub[1] - TASK_STAR_CENTER[1] - top,
                (bottom + 1) - (TASK_STAR_SIZE[1] - TASK_STAR_CENTER[1])
                - hub[1])
    circle_hi = min(rx_hi, ry_hi)
    return (hub, circle_lo, circle_hi, rx_lo, rx_hi, ry_lo, ry_hi)


def star_ray_points(scale=1.0):
    """Eight-point crystalline cross-star silhouette (pure data).

    Four principal rays with concave waists between them; vertical
    rays longer than horizontal. Points are (dx, dy) offsets from the
    star center, clockwise from the top tip. Unit-testable so star
    bounds can be asserted without a QApplication.
    """
    v = TASK_STAR_RAY_V * scale
    h = TASK_STAR_RAY_H * scale
    w = TASK_STAR_WAIST * scale
    return [(0, -v), (w, -w), (h, 0), (w, w),
            (0, v), (-w, w), (-h, 0), (-w, -w)]


def star_phase_seed(slot):
    """Deterministic D2B motion seed for a lifetime slot.

    Stable for the slot's lifetime: orbit phase offset and breathing
    phase derive from this, never from activity recency. D2B must
    advance phase with accumulated active time (pause-safe), never
    with absolute wall clock, so hover/drag resume cannot teleport.
    """
    return ((int(slot) * 2654435761) % 1000) / 1000.0


def _ring_rotation(pet, screen):
    """Bias the ring composition toward usable work-area space.

    Determined BEFORE any position is computed: a pet in the upper
    half opens the arc downward, in the lower half upward; a pet on
    the right opens leftward, on the left rightward. Deterministic;
    full rings simply spin by the same offset.
    """
    x, y, width, height = pet
    left, top, right, bottom = screen
    pcx, pcy = x + width / 2, y + height / 2
    scx, scy = (left + right) / 2, (top + bottom) / 2
    dx, dy = pcx - scx, pcy - scy
    if abs(dy) > abs(dx):
        return 180 if dy < 0 else 0
    return -90 if dx > 0 else (90 if dx < 0 else 0)


def _open_direction(pet, screen):
    """Angle (degrees, 0 = up, clockwise) toward usable space.

    Points from the pet center at the work-area center: the open
    side where an arc composition naturally belongs. Exact (not
    snapped) and deterministic. A centered pet yields straight up.
    """
    import math
    x, y, width, height = pet
    left, top, right, bottom = screen
    dx = (left + right) / 2 - (x + width / 2)
    dy = (y + height / 2) - (top + bottom) / 2
    if dx == 0 and dy == 0:
        return 0.0
    return math.degrees(math.atan2(dx, dy)) % 360.0


def _gap_centers(surrounding, count, circular):
    """Centers of angular gaps between consecutive sorted angles.

    Outer-lane stars sit in the middle of inner-lane gaps — never on
    top of an inner star. Takes the first ``count`` lowest gap
    centers (deterministic). Circular rings wrap the last gap around
    360°; arcs use linear gaps only.
    """
    pts = sorted(surrounding)
    gaps = []
    for index in range(len(pts) - 1):
        gaps.append((pts[index] + pts[index + 1]) / 2)
    if circular and pts:
        gaps.append(((pts[-1] + pts[0] + 360) % 360))
    return gaps[:count]


def _compose_candidate(ordered, pet, base_rot, open_angle, mode,
                       radius_boost, shift_steps, screen):
    """One deterministic composition candidate: {slot: center}.

    ``mode`` is ('ring', extra_rot) or ('arc', spread). Ring mode
    keeps the approved purposeful arrangements (single, pair,
    triangle, cardinal ring, pentagon, two lanes); arc mode spreads
    points across the open side for tight corners. ``shift_steps``
    translates the ring center toward the work-area center in 48 px
    steps. No clamping here: validity is judged on these raw
    centers, so a later step can never silently undo a guarantee.
    """
    import math
    count = len(ordered)
    x, y, width, height = pet
    left, top, right, bottom = screen
    pcx, pcy = x + width / 2, y + height / 2
    sdx = (left + right) / 2 - pcx
    sdy = (top + bottom) / 2 - pcy
    shift_len = (sdx * sdx + sdy * sdy) ** 0.5 or 1.0
    ccx = pcx + sdx / shift_len * shift_steps
    ccy = pcy + sdy / shift_len * shift_steps
    kind = mode[0]
    centers = {}
    for item in ordered:
        rank = ordered.index(item)
        lane = 0
        if kind == 'ring':
            extra_rot = mode[1]
            rot = base_rot + extra_rot
            if count <= 1:
                angle = 0
            elif count == 2:
                angle = (-35, 35)[rank]
            elif count == 3:
                angle = (-60, 0, 60)[rank]
            elif count == 4:
                angle = (0, 90, 180, 270)[rank]
            elif count == 5:
                angle = (0, 72, 144, 216, 288)[rank]
            else:
                inner = ordered[:5]
                inner_angles = [(0, 72, 144, 216, 288)[k] for k in range(5)]
                if item in inner:
                    angle = inner_angles[inner.index(item)]
                else:
                    lane = 1
                    outer = ordered[5:]
                    angle = _gap_centers(inner_angles, len(outer), True)[
                        outer.index(item)]
            theta = math.radians(angle + rot)
        else:
            spread = mode[1]
            if count <= 1:
                angle = open_angle
            else:
                inner = ordered[:5]
                if item in inner:
                    sub = inner.index(item) / (len(inner) - 1) - 0.5
                else:
                    lane = 1
                    outer = ordered[5:]
                    inner_span = [spread * (k / (len(inner) - 1) - 0.5)
                                  for k in range(len(inner))]
                    sub = _gap_centers(inner_span, len(outer), False)[
                        outer.index(item)] / spread
                angle = open_angle + spread * sub
            theta = math.radians(angle)
        radius_x = width / 2 + 84 + radius_boost + lane * 66
        radius_y = height / 2 + 84 + radius_boost + lane * 66
        centers[item] = (ccx + radius_x * math.sin(theta),
                         ccy - radius_y * math.cos(theta))
    return centers


def _finalize_candidate(centers, screen):
    """Float centers to FINAL integer windows, or None.

    Applies the single authoritative quantization rule, then
    requires the rearranged window to already sit inside the work
    area: if any clamp would move it, the whole candidate is
    rejected (returned None) instead of being silently reshaped.
    This is what makes later clamp calls provably no-ops.
    """
    width, height = TASK_STAR_SIZE
    left, top, right, bottom = screen
    windows = {}
    for item, (cx, cy) in centers.items():
        wx, wy = star_center_to_window_position(cx, cy)
        if not (left <= wx and wx + width <= right + 1
                and top <= wy and wy + height <= bottom + 1):
            return None
        windows[item] = (wx, wy)
    return windows


def _windows_valid(windows, pet, screen):
    """Final-constraint check on quantized integer windows.

    Judges the EXACT geometry QWidget.move will receive: full
    interactive footprints (disc + label strip) against pet
    exclusion and each other. STAR_MIN_CENTER_DIST remains only as
    a cheap prefilter inside the pairwise check below — the
    footprint validator is authoritative.
    """
    footprints = {item: star_window_footprint(*pos)
                  for item, pos in windows.items()}
    for footprint in footprints.values():
        if footprint_hits_pet(footprint, pet):
            return False
    items = list(footprints)
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            first, second = footprints[items[i]], footprints[items[j]]
            (ax, ay, _), _ = first
            (bx, by, _), _ = second
            if ((ax - bx) ** 2 + (ay - by) ** 2
                    < STAR_MIN_CENTER_DIST ** 2):
                return False
            if footprints_collide(first, second):
                return False
    return True


def _candidate_space():
    """Bounded deterministic candidate list, closest-first.

    Ring rotations preserve the approved look; radius boosts widen
    tight lanes; arc modes bias to open space (narrower spreads hug
    the open side in tight corners); shifts translate the whole
    composition toward the work-area center. Fixed order, fixed
    size, no randomness: 108 ring + 48 arc candidates.
    """
    space = []
    for shift in (0, 48, 96):
        for boost in (0, 40, 80):
            for extra in range(0, 360, 30):
                space.append(('ring', extra, boost, shift))
    for shift in (0, 48, 96, 144, 192, 240):
        for spread in (270, 210, 150, 110):
            for boost in (0, 40):
                space.append(('arc', spread, boost, shift))
    return space


@_lru_cache(maxsize=64)
def _cached_solve(ordered_key, pet_key, screen_key):
    """Cached core of the candidate search (hashable inputs only).

    Returns final integer centers aligned with ``ordered_key``.
    Each candidate flows through the exact UI pipeline —
    quantize to integer windows, then full-footprint validation —
    so an accepted candidate IS the on-screen geometry.
    """
    items = list(ordered_key)
    base_rot = _ring_rotation(pet_key, screen_key)
    open_angle = _open_direction(pet_key, screen_key)
    for mode in _candidate_space():
        if mode[0] == 'ring':
            _, extra, boost, shift = mode
            centers = _compose_candidate(
                items, pet_key, base_rot, open_angle,
                ('ring', extra), boost, shift, screen_key)
        else:
            _, spread, boost, shift = mode
            centers = _compose_candidate(
                items, pet_key, base_rot, open_angle,
                ('arc', spread), boost, shift, screen_key)
        windows = _finalize_candidate(centers, screen_key)
        if windows is not None and _windows_valid(windows, pet_key,
                                                  screen_key):
            return tuple(
                (windows[item][0] + TASK_STAR_CENTER[0],
                 windows[item][1] + TASK_STAR_CENTER[1])
                for item in items)
    centers = _compose_candidate(items, pet_key, base_rot, open_angle,
                                 ('ring', 0), 0, 0, screen_key)
    fallback = _finalize_candidate(centers, screen_key)
    if fallback is not None:
        return tuple(
            (fallback[item][0] + TASK_STAR_CENTER[0],
             fallback[item][1] + TASK_STAR_CENTER[1])
            for item in items)
    width, height = TASK_STAR_SIZE
    clamped = {
        item: clamp_position(*star_center_to_window_position(*centers[item]),
                             width, height, screen_key)
        for item in items}
    return tuple(
        (clamped[item][0] + TASK_STAR_CENTER[0],
         clamped[item][1] + TASK_STAR_CENTER[1])
        for item in items)


def star_ring_anchor(visible_slots, slot, pet, screen,
                     size=TASK_STAR_SIZE):
    """Static star-ring home for one task, given the visible slot set.

    ``visible_slots`` is the CURRENT visible stable slot set (not
    lifetime order alone): 1 star takes a purposeful single position,
    3 take a triangle, 4+ a ring, 6-8 a second lane — never holes left
    by filtered-hidden slots. Lifetime slots are never renumbered or
    mutated here; rank within the visible set only selects a
    composition angle. No activity input, no reordering. Rectangles
    use (x, y, width, height); screen uses inclusive edges. Returns
    the exact integer widget top-left the surface will receive (the
    star center sits at TASK_STAR_CENTER inside it: the D2C morph
    origin and D2B orbit anchor). The trailing clamp is provably a
    no-op for solver-accepted layouts — dead safety for the
    physically-impossible fallback only.
    """
    centers = star_ring_centers(visible_slots, pet, screen)
    center_x, center_y = centers[slot]
    pw, ph = size
    home = star_center_to_window_position(center_x, center_y)
    return clamp_position(home[0], home[1], pw, ph, screen)


def star_ring_centers(visible_slots, pet, screen):
    """Final integer star centers for the whole visible set.

    A bounded deterministic candidate search evaluates compositions
    against ALL final constraints together (quantized window bounds,
    full-footprint pet exclusion, full-footprint pairwise
    non-overlap) and returns the first fully valid arrangement, as
    the exact integer centers QWidget.move will use. No later
    transform re-decides anything. Returns {slot: (center_x,
    center_y)} with integer values. Deterministic; same inputs
    always give same outputs. Results are cached: identical layouts
    never pay the search twice.
    """
    ordered = tuple(sorted(visible_slots))
    if not ordered:
        return {}
    aligned = _cached_solve(tuple(ordered), tuple(pet), tuple(screen))
    return dict(zip(ordered, aligned))


def task_window_position(slot, size, pet, screen, gap=TASK_WINDOW_GAP):
    """Place one task window for a lifetime-stable visual slot.

    Windows stack vertically beside the pet; when the current side runs
    out of rows, deterministic columns continue first on the right side
    of the pet and then on the left, so every slot maps to a distinct
    position whenever the work area physically allows it. Column
    direction is chosen from measured capacity — never by generating
    positions off-screen and relying on clamping, which used to collapse
    several windows onto the same edge coordinate. Clamping remains only
    as a final safety guard for genuinely undersized work areas (where
    overlap is unavoidable but nothing is ever hidden: there is no panel
    cap). Rectangles use (x, y, width, height); screen uses inclusive
    edges.
    """
    x, y, width, _ = pet
    pw, ph = size
    left, top, right, bottom = screen
    rows = max(1, (bottom + 1 - top) // (ph + gap))
    right_cols = max(0, (right + 1 - (x + width + gap) + gap) // (pw + gap))
    left_cols = max(0, (x - gap - left + gap) // (pw + gap))

    def column_x(index):
        if index < right_cols:
            return x + width + gap + index * (pw + gap)
        spill = index - right_cols
        if spill < left_cols:
            return x - gap - pw - spill * (pw + gap)
        # Physically out of room: keep extending deterministically on
        # the roomier side instead of stacking everything at the clamp
        # edge. These positions may still clamp (true overflow), but
        # only when no work-area space exists at all.
        extra = spill - left_cols
        if right + 1 - (x + width) >= x - left:
            return x + width + gap + (right_cols + extra) * (pw + gap)
        return x - gap - pw - (left_cols + extra) * (pw + gap)

    column, row = divmod(slot, rows)
    return clamp_position(column_x(column), top + row * (ph + gap),
                          pw, ph, screen)


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
