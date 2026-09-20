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

Animation readiness: an entry may later carry ``frames`` (a tuple of paths
for a frame sequence). The loader resolves only the still ``path`` today; no
frame timers exist yet.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

ASSETS_DIR = Path(__file__).parent / "assets"
V1_1_DIR = ASSETS_DIR / "v1_1"

IDLE_FALLBACK = "assets/skirk-pet.png"


@dataclass(frozen=True)
class AssetEntry:
    state: str
    path: str
    fallback: str = IDLE_FALLBACK
    frames: tuple = field(default_factory=tuple)

    @property
    def animated(self):
        return bool(self.frames)


REGISTRY = (
    AssetEntry("idle", "assets/v1_1/idle.png", "assets/skirk-pet.png"),
    AssetEntry("typing", "assets/v1_1/typing.png", "assets/skirk-typing.png",
               frames=("assets/v1_1/typing_1.png", "assets/v1_1/typing_2.png")),
    AssetEntry("codex_working", "assets/v1_1/working.png", "assets/skirk-pet.png"),
    AssetEntry("microphone", "assets/v1_1/microphone.png", "assets/skirk-microphone.png"),
    AssetEntry("music", "assets/v1_1/music.png", "assets/skirk-music.png"),
    AssetEntry("guitar", "assets/v1_1/guitar.png", "assets/skirk-pet.png"),
)

# Activity-layer names that are not character poses.
ALIASES = {"working": "codex_working", "usage": "idle"}

# Preview states understood by DesktopPet (activity names).
PREVIEW_STATES = ("idle", "typing", "microphone", "music", "working", "usage")


def entry_for(state):
    """Return the registry entry for ``state``; unknown states map to idle."""
    key = ALIASES.get(state, state)
    for entry in REGISTRY:
        if entry.state == key:
            return entry
    return REGISTRY[0]


def registered_states():
    return tuple(entry.state for entry in REGISTRY)


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


_FRAME_CACHE = {}


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
    from PySide6.QtGui import QPixmap
    path = valid[phase % len(valid)]
    pixmap = _FRAME_CACHE.get(path)
    if pixmap is None or pixmap.isNull():
        pixmap = QPixmap(str(ASSETS_DIR.parent / path))
        _FRAME_CACHE[path] = pixmap
    return pixmap if not pixmap.isNull() else None


def load_sprites():
    """Build the DesktopPet sprite table.

    Keys are registry states plus activity aliases (``working``,
    ``usage``), so the renderer and QA can address every pose by name
    while activity logic keeps its own vocabulary.
    """
    table = {entry.state: sprite_for(entry.state) for entry in REGISTRY}
    table['working'] = table['codex_working']
    table['usage'] = table['idle']
    return table
