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
import os
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


def _v21(name, count):
    return tuple(f"assets/v2_1/{name}_{n}.png" for n in range(1, count + 1))


def _v23(name, count):
    return tuple(f"assets/v2_3/{name}_{n}.png" for n in range(1, count + 1))


def _v24(name, count):
    return tuple(f"assets/v2_4/{name}_{n}.png" for n in range(1, count + 1))


def _file(path):
    """A registry path on disk. New art may live outside the repository until
    its branch is merged (PETOKEN_V2_1_ART / PETOKEN_V2_3_ART, as in transform.py)."""
    p = Path(path)
    if p.is_absolute():
        return p
    for folder, env in (("v2_1", "PETOKEN_V2_1_ART"), ("v2_3", "PETOKEN_V2_3_ART"), ("v2_4", "PETOKEN_V2_4_ART")):
        if path.startswith(f"assets/{folder}/") and not (ASSETS_DIR / folder).is_dir():
            other = os.environ.get(env)
            if other:
                return Path(other) / path[len(f"assets/{folder}/"):]
    file = ASSETS_DIR.parent / path
    if path.startswith('assets/v2_5/forms/') and path.endswith('.png') and not file.is_file():
        webp = file.with_suffix('.webp')                  # The package carries the full sets as WebP.
        if webp.is_file():
            return webp
    return file


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
# exists, has an eyes-closed image). See docs/V2_0_ART_PROMPTS.md.
_COMPANION = (
    ("coquettish", 4, "wave", True), ("headpat_happy", 4, "celebrate", True),
    ("sleep", 3, "idle", False), ("bored", 3, "idle", True), ("yawn", 3, "idle", False),
    ("wake_stretch", 2, "celebrate", False), ("curious", 2, "working", True),
    ("thinking", 2, "working", True), ("shy", 2, "idle", False), ("pout", 2, "sad", True),
    ("poked", 1, "idle", False), ("dragged", 4, "wave", False), ("landing", 1, "idle", True),
    ("hug", 2, "wave", True), ("heart", 1, "celebrate", False), ("greet_morning", 2, "wave", True),
    ("greet_night", 2, "wave", False), ("surprised", 1, "celebrate", False),
    ("thumbs_up", 1, "celebrate", True), ("cheer", 2, "celebrate", True), ("clap", 3, "celebrate", True),
    ("peek", 2, "idle", False), ("grievance", 2, "sad", False),
    ("focus_read", 4, "working", True), ("focus_tea", 2, "idle", False),
    ("focus_done", 1, "celebrate", True), ("stretch_break", 2, "celebrate", True),
    ("hold_card", 1, "wave", True), ("packing", 1, "idle", True), ("ready_go", 1, "wave", True),
    ("worried", 2, "sad", True), ("proud", 1, "celebrate", True),
)
# Every pose may arrive as <name>.png or <name>_1.png (and further frames).
COMPANION_REGISTRY = tuple(
    AssetEntry(name, f"assets/v2_0/{name}.png", f"assets/v1_1/{fallback}.png",
               frames=_v2(name, frames),
               blink=f"assets/v2_0/{name}_blink.png" if blink else "")
    for name, frames, fallback, blink in _COMPANION)

# 2.1 game mode: her second form (docs/V2_1_ART_PROMPTS.md). Until the art
# exists each falls back to her idle pose.
_GAME = (("form2_idle", 4, True), ("game_watch", 3, True), ("game_tense", 2, True), ("game_cheer", 2, False),
         ("game_victory", 2, False), ("game_defeat", 2, True), ("game_drink", 2, False), ("game_bored", 2, True))
GAME_REGISTRY = tuple(
    AssetEntry(name, f"assets/v2_1/{name}.png", "assets/v1_1/idle.png", frames=_v21(name, frames),
               blink=f"assets/v2_1/{name}_blink.png" if blink else "")
    for name, frames, blink in _GAME)

# 2.3 late-night mode: her moon pajamas (docs/V2_3_ART_PROMPTS.md). Until the
# art exists night_mode keeps her usual poses.
_NIGHT = (("night_idle", 4, True), ("night_yawn", 2, False), ("night_sleep", 3, False), ("night_milk", 2, False),
          ("night_read", 2, True), ("night_goodnight", 2, False), ("night_wake", 2, False))
NIGHT_REGISTRY = tuple(
    AssetEntry(name, f"assets/v2_3/{name}.png", "assets/v1_1/idle.png", frames=_v23(name, frames),
               blink=f"assets/v2_3/{name}_blink.png" if blink else "")
    for name, frames, blink in _NIGHT)
# The pajama change, one picture per step (night_mode.CHANGE_ON / CHANGE_OFF).
NIGHT_CHANGE_REGISTRY = tuple(
    AssetEntry(name, f"assets/v2_3/{name}.png", "assets/v1_1/idle.png")
    for name in ("night_change_0", "night_change_1", "night_change_2", "night_change_3",
                 "night_settle_1", "night_settle_2"))

# 2.4 her third form, Starsea (starsea.py, docs/V2_4_STARSEA_PLAN.md), and
# the awakening into it, one picture per step.
_STAR = (("star_idle", 4, True), ("star_typing", 3, False), ("star_celebrate", 2, False), ("star_sad", 1, True),
         ("star_wave", 2, False), ("star_thinking", 2, False), ("star_sleep", 2, False), ("star_headpat", 2, False),
         ("star_poked", 1, False), ("star_dragged", 1, False))
STAR_REGISTRY = tuple(
    AssetEntry(name, f"assets/v2_4/{name}.png", "assets/v1_1/idle.png", frames=_v24(name, frames),
               blink=f"assets/v2_4/{name}_blink.png" if blink else "")
    for name, frames, blink in _STAR) + tuple(
    AssetEntry(f"awaken_{n}", f"assets/v2_4/awaken_{n}.png", "assets/v1_1/idle.png") for n in range(5))

# 2.5 every action in every form: the night pajamas, the game form and Starsea each get a full set of
# her default actions (assets/v2_5/forms/<form>/<pose>_<n>.png, <pose>_blink.png), drawn in that
# form's look. A form uses its full-set picture of an action once it exists (full_set), else what it
# did before. The states are named '<form>:<pose>'.
FULL_POSES = tuple(entry.state for entry in REGISTRY + COMPANION_REGISTRY)
FORM_DIRS = dict(night='night', game='game', star='starsea')
FORM_PREFIXES = tuple(f'{form}:' for form in FORM_DIRS)
FORM_REGISTRY = tuple(
    AssetEntry(f'{form}:{pose}', f'assets/v2_5/forms/{folder}/{pose}.png', 'assets/v1_1/idle.png',
               frames=tuple(f'assets/v2_5/forms/{folder}/{pose}_{n}.png' for n in range(1, 7)),
               blink=f'assets/v2_5/forms/{folder}/{pose}_blink.png')
    for form, folder in FORM_DIRS.items() for pose in FULL_POSES)


def full_set(form, pose):
    """'<form>:<pose>' when that form has its own picture of the action, else None."""
    if pose not in FULL_POSES:
        return None
    state = f'{form}:{pose}'
    if state not in _FULL_CACHE:
        entry = _FORM_ENTRIES[state]
        _FULL_CACHE[state] = _file(entry.path).is_file() or bool(existing_frames(entry))
    return state if _FULL_CACHE[state] else None


_FULL_CACHE = {}
_FORM_ENTRIES = {entry.state: entry for entry in FORM_REGISTRY}


# Activity-layer names that are not character poses.
ALIASES = {"working": "codex_working", "usage": "idle"}

# Preview states understood by DesktopPet (activity names).
PREVIEW_STATES = ("idle", "typing", "microphone", "music", "working", "usage",
                  "celebrate", "sad", "wave")


def entry_for(state):
    """Return the registry entry for ``state``; unknown states map to idle."""
    key = ALIASES.get(state, state)
    for entry in REGISTRY + COMPANION_REGISTRY + GAME_REGISTRY + NIGHT_REGISTRY + NIGHT_CHANGE_REGISTRY + STAR_REGISTRY + FORM_REGISTRY:
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
    file = _file(path)
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
    file = _file(path)
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
        if readable(candidate):
            return candidate
    return None


_READABLE = {}


def readable(path):
    """Whether ``path`` is a picture Qt can read, from its header only (decoding every pose's full
    picture just to check it made start-up take seconds)."""
    if path not in _READABLE:
        from PySide6.QtGui import QImageReader
        file = _file(path)
        reader = QImageReader(str(file))
        _READABLE[path] = file.is_file() and reader.canRead() and not reader.size().isEmpty()
    return _READABLE[path]


class LazySprites(dict):
    """{state: picture} whose pictures are read the first time they are shown (through the
    size-capped cache), not all at start-up. Values may be a QPixmap or a registry path."""

    def __getitem__(self, key):
        value = dict.__getitem__(self, key)
        return pose_source(value) if isinstance(value, str) else value

    def get(self, key, default=None):
        if key not in self:
            return default
        value = self[key]
        return default if value is None else value

    def values(self):
        return [self[key] for key in self]

    def items(self):
        return [(key, self[key]) for key in self]

    def copy(self):
        return LazySprites(dict.items(self))


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
_OWN_CACHE = {}


def pose_source(path):
    """A cached, size-capped pixmap for ``path``, or None when unloadable."""
    pixmap = _FRAME_CACHE.get(path)
    if pixmap is not None:
        _FRAME_CACHE.move_to_end(path)
        return pixmap
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage, QPixmap
    file = _file(path)
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
                                     bool(entry.blink and _file(entry.blink).is_file()))
    return _COUNT_CACHE[entry.state]


def frame_count(state):
    """How many frames of ``state`` exist on disk (checked once per process)."""
    return _art(state)[0]


def has_own_art(state):
    """The pose has its own picture (not a fallback): it draws its own symbols."""
    entry = entry_for(state)
    if entry.state not in _OWN_CACHE:
        _OWN_CACHE[entry.state] = (_file(entry.path).is_file() or frame_count(state) > 0)
    return _OWN_CACHE[entry.state]


def has_blink(state):
    return _art(state)[1]


def blink_for(state):
    """The eyes-closed image for ``state``, or None."""
    return pose_source(entry_for(state).blink) if has_blink(state) else None


def existing_frames(entry):
    """Return the entry's frame paths that actually exist on disk, in order."""
    return [path for path in entry.frames if _file(path).is_file()]


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
        table = LazySprites()
        for entry in REGISTRY + COMPANION_REGISTRY + GAME_REGISTRY + NIGHT_REGISTRY + NIGHT_CHANGE_REGISTRY                 + STAR_REGISTRY + FORM_REGISTRY:
            path = resolve_path(entry)
            if path is not None:
                dict.__setitem__(table, entry.state, path)       # Read when first shown.
        for alias, state in (('working', 'codex_working'), ('usage', 'idle')):
            if state in table:
                dict.__setitem__(table, alias, dict.__getitem__(table, state))
        _SPRITE_TABLE = table
    return _SPRITE_TABLE.copy()
