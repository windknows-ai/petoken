"""Centralized character-asset registry for the desktop pet.

One authoritative table maps every logical pet state to its artwork. Future
approved V1.1 chibi assets are dropped into ``assets/v1_1/<state>.png`` and
picked up automatically; until then each state resolves to its verified V1.0
fallback. DesktopPet never names PNG files directly.

State model: the activity layer reports ``idle``/``typing``/``microphone``/
``music``/``working``/``usage``. ``working`` (Codex Working) and ``typing``
are distinct registry identities (``codex_working`` vs ``typing``) even while
both temporarily reuse approved fallback art. ``usage`` (panel open) is not a
pose and aliases to ``idle``.

Geometry independence: entries carry no coordinates. Every resolved pixmap
renders through ``pet_geometry`` into the same logical sprite box, so source
PNG dimensions never affect layout, scale, anchor, or bubble placement.

Animation (2.0): an entry may carry ``frames`` (a frame sequence) and a
``blink`` image (the same pose with eyes closed). Both are optional: only
files that exist are used, so art can arrive pose by pose. 2.0 art lives in
``assets/v2_0/``; companionship poses without their own art yet fall back
to the closest V1.1 pose, and pet_motion keeps them moving either way.
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path

ASSETS_DIR = Path(__file__).parent / "assets"
V1_1_DIR = ASSETS_DIR / "v1_1"
V2_0_DIR = ASSETS_DIR / "v2_0"

IDLE_FALLBACK = "assets/skirk-pet.png"


@dataclass(frozen=True)
class AssetEntry:
    state: str
    path: str
    fallback: str = IDLE_FALLBACK
    frames: tuple = field(default_factory=tuple)
    blink: str = ""

    @property
    def animated(self):
        return bool(existing_frames(self))


def _v2(name, count):
    return tuple(f"assets/v2_0/{name}_{n}.png" for n in range(1, count + 1))


REGISTRY = (
    AssetEntry("idle", "assets/v1_1/idle.png", "assets/skirk-pet.png",
               frames=_v2("idle", 4), blink="assets/v2_0/idle_blink.png"),
    AssetEntry("typing", "assets/v1_1/typing.png", "assets/skirk-typing.png",
               frames=("assets/v1_1/typing_1.png", "assets/v1_1/typing_2.png",
                       "assets/v2_0/typing_3.png", "assets/v2_0/typing_4.png"),
               blink="assets/v2_0/typing_blink.png"),
    AssetEntry("codex_working", "assets/v1_1/working.png", "assets/skirk-pet.png",
               frames=_v2("working", 3), blink="assets/v2_0/working_blink.png"),
    AssetEntry("microphone", "assets/v1_1/microphone.png", "assets/skirk-microphone.png",
               blink="assets/v2_0/microphone_blink.png"),
    AssetEntry("music", "assets/v1_1/music.png", "assets/skirk-music.png",
               frames=_v2("music", 4), blink="assets/v2_0/music_blink.png"),
    AssetEntry("guitar", "assets/v1_1/guitar.png", "assets/skirk-pet.png",
               blink="assets/v2_0/guitar_blink.png"),
    # V1.6 notification reactions.
    AssetEntry("celebrate", "assets/v1_1/celebrate.png", "assets/skirk-pet.png",
               frames=_v2("celebrate", 3), blink="assets/v2_0/celebrate_blink.png"),
    AssetEntry("sad", "assets/v1_1/sad.png", "assets/skirk-pet.png",
               blink="assets/v2_0/sad_blink.png"),
    AssetEntry("wave", "assets/v1_1/wave.png", "assets/skirk-pet.png",
               frames=_v2("wave", 3), blink="assets/v2_0/wave_blink.png"),
)

# 2.0 companionship poses: (name, frames, the V1.1 pose shown until the art
# exists, has an eyes-closed image). See docs/V2_0_ART_LIST.md.
_COMPANION = (
    ("coquettish", 4, "wave", True), ("headpat_happy", 4, "celebrate", True),
    ("shy", 1, "idle", True), ("pout", 1, "sad", True), ("poked", 1, "idle", True),
    ("dragged", 4, "wave", True), ("landing", 1, "idle", True),
    ("curious", 1, "working", True), ("thinking", 1, "working", True),
    ("bored", 1, "idle", True), ("yawn", 1, "idle", False), ("sleep", 3, "idle", False),
    ("wake_stretch", 1, "celebrate", False), ("hug", 1, "wave", True),
    ("heart", 1, "celebrate", True), ("greet_morning", 1, "wave", True),
    ("greet_night", 1, "wave", True), ("surprised", 1, "celebrate", True),
    ("thumbs_up", 1, "celebrate", True), ("cheer", 1, "celebrate", True),
    ("clap", 3, "celebrate", True), ("peek", 1, "idle", True), ("grievance", 1, "sad", True),
    ("focus_read", 4, "working", True), ("focus_tea", 1, "idle", False),
    ("focus_done", 1, "celebrate", True), ("stretch_break", 1, "celebrate", True),
    ("hold_card", 1, "wave", True), ("packing", 1, "idle", True),
    ("ready_go", 1, "wave", True), ("worried", 1, "sad", True), ("proud", 1, "celebrate", True),
)
COMPANION_REGISTRY = tuple(
    AssetEntry(name, f"assets/v2_0/{name}.png", f"assets/v1_1/{fallback}.png",
               frames=_v2(name, frames) if frames > 1 else (),
               blink=f"assets/v2_0/{name}_blink.png" if blink else "")
    for name, frames, fallback, blink in _COMPANION)

# Activity-layer names that are not character poses.
ALIASES = {"working": "codex_working", "usage": "idle"}

# Preview states understood by DesktopPet (activity names).
PREVIEW_STATES = ("idle", "typing", "microphone", "music", "working", "usage",
                  "celebrate", "sad", "wave")


def entry_for(state):
    """Return the registry entry for ``state``; unknown states map to idle."""
    key = ALIASES.get(state, state)
    for entry in REGISTRY + COMPANION_REGISTRY:
        if entry.state == key:
            return entry
    return REGISTRY[0]


def registered_states():
    return tuple(entry.state for entry in REGISTRY)


def companion_states():
    return tuple(entry.state for entry in COMPANION_REGISTRY)


def validate_path(path):
    """Lightweight check: exists, loads, non-zero, alpha-capable PNG data."""
    from PySide6.QtGui import QImage
    file = ASSETS_DIR.parent / path if not Path(path).is_absolute() else Path(path)
    if not file.is_file():
        return False, "missing file"
    image = QImage(str(file))
    if image.isNull() or image.width() <= 0 or image.height() <= 0:
        return False, "unreadable image"
    if not image.hasAlphaChannel() and image.pixelColor(0, 0).alpha() != 0:
        return False, "no transparency"
    return True, ""


def load_path(path):
    """Load ``path`` to a QPixmap, or None when missing/broken."""
    from PySide6.QtGui import QPixmap
    file = ASSETS_DIR.parent / path if not Path(path).is_absolute() else Path(path)
    pixmap = QPixmap(str(file))
    return pixmap if not pixmap.isNull() else None


def resolve_path(entry):
    """Return the first loadable path: primary, existing frames, fallback, idle.

    A state with frames but no still file uses its first frame as the static
    pose (e.g. motion-paused typing). Pure path selection, directly
    unit-testable without touching artwork. Returns None only when even the
    pinned idle fallback cannot load.
    """
    for candidate in [entry.path] + existing_frames(entry) + [entry.fallback, IDLE_FALLBACK]:
        if load_path(candidate) is not None:
            return candidate
    return None


def sprite_for(state):
    """Resolve ``state`` to a pixmap via :func:`resolve_path`.

    Never raises and never fabricates a path. Returns None only when even
    the pinned idle fallback cannot load (i.e. repository assets deleted).
    """
    path = resolve_path(entry_for(state))
    return load_path(path) if path is not None else None


# Frames and blink images are decoded on first use, scaled down to what the
# largest pet on a 2x screen needs, and kept in a small LRU: 2.0 has about a
# hundred images and full-size sources would cost several MB each.
SOURCE_MAX_SIDE = 768
SOURCE_CACHE_SIZE = 48
_FRAME_CACHE = OrderedDict()
_COUNT_CACHE = {}


def pose_source(path):
    """A cached, size-capped pixmap for ``path``, or None when unloadable."""
    pixmap = _FRAME_CACHE.get(path)
    if pixmap is not None:
        _FRAME_CACHE.move_to_end(path)
        return pixmap
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage, QPixmap
    file = ASSETS_DIR.parent / path if not Path(path).is_absolute() else Path(path)
    image = QImage(str(file))
    if image.isNull():
        return None
    if max(image.width(), image.height()) > SOURCE_MAX_SIDE:
        image = image.scaled(SOURCE_MAX_SIDE, SOURCE_MAX_SIDE, Qt.KeepAspectRatio,
                             Qt.SmoothTransformation)
    pixmap = QPixmap.fromImage(image)
    _FRAME_CACHE[path] = pixmap
    while len(_FRAME_CACHE) > SOURCE_CACHE_SIZE:
        _FRAME_CACHE.popitem(last=False)
    return pixmap


def _art(state):
    entry = entry_for(state)
    if entry.state not in _COUNT_CACHE:
        _COUNT_CACHE[entry.state] = (len(existing_frames(entry)),
                                     bool(entry.blink and (ASSETS_DIR.parent / entry.blink).is_file()))
    return _COUNT_CACHE[entry.state]


def frame_count(state):
    """How many frames of ``state`` exist on disk (checked once per process)."""
    return _art(state)[0]


def has_blink(state):
    return _art(state)[1]


def blink_for(state):
    """The eyes-closed image for ``state``, or None."""
    return pose_source(entry_for(state).blink) if has_blink(state) else None


def existing_frames(entry):
    """Return the entry's frame paths that actually exist on disk, in order."""
    return [path for path in entry.frames
            if (ASSETS_DIR.parent / path).is_file()]


def frame_for(state_or_entry, phase):
    """Resolve one animation frame for a tap ``phase``.

    Accepts a state name or an ``AssetEntry`` (entries are directly testable
    with temporary files). Returns None when no frame files exist, in which
    case callers keep the static fallback visual. Loaded frames are cached so
    per-repaint resolution stays cheap.
    """
    entry = state_or_entry if isinstance(state_or_entry, AssetEntry) else entry_for(state_or_entry)
    valid = existing_frames(entry)
    if not valid:
        return None
    return pose_source(valid[phase % len(valid)])


_SPRITE_TABLE = None


def load_sprites():
    """Build the DesktopPet sprite table.

    Keys are registry states plus activity aliases (``working``,
    ``usage``), so the renderer and QA can address every pose by name
    while activity logic keeps its own vocabulary.

    Decoded once per process: each source is about 6 MB in memory, and
    QPixmap copies share the same data, so extra pets (tests, previews)
    cost nothing more.
    """
    global _SPRITE_TABLE
    if _SPRITE_TABLE is None:
        table = {entry.state: sprite_for(entry.state) for entry in REGISTRY}
        # Companion poses share the V1.1 pixmap they fall back to, so they
        # cost no extra memory until their own art exists.
        paths = {resolve_path(entry): table[entry.state] for entry in REGISTRY}
        for entry in COMPANION_REGISTRY:
            path = resolve_path(entry)
            table[entry.state] = paths.get(path) or (pose_source(path) if path else None)
        table['working'] = table['codex_working']
        table['usage'] = table['idle']
        _SPRITE_TABLE = table
    return dict(_SPRITE_TABLE)
