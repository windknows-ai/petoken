"""Application metadata and backward-compatible preference storage."""
from __future__ import annotations

import json
from pathlib import Path

from localization import DEFAULT_LANGUAGE, normalize_language
from pricing import DEFAULT_CURRENCY, normalize_currency
from provider_selection import (DEFAULT_TRACKING_PROVIDER,
                                normalize_tracking_provider)
from token_format import DEFAULT_TOKEN_NUMBER_FORMAT, normalize_token_format
from pet_geometry import PET_SCALE_DEFAULT, normalize_pet_scale

APP_VERSION = "1.6.0"
# 2: V1.5 Codex + Claude Code. Earlier builds offered no provider choice and
# saved the forced "codex" value, so that value migrates once to Auto.
SETTINGS_SCHEMA_VERSION = 2
DEFAULT_PREFERENCES = {
    "settings_schema_version": SETTINGS_SCHEMA_VERSION,
    "language": DEFAULT_LANGUAGE,
    "scope": "conversation",
    "tracking_provider": DEFAULT_TRACKING_PROVIDER,
    "token_number_format": DEFAULT_TOKEN_NUMBER_FORMAT,
    "currency": DEFAULT_CURRENCY,
    "always_on_top": True,
    "panel_pinned": False,
    "pet_scale_percent": PET_SCALE_DEFAULT,
    "pet_motion": True,
    "star_ring_enabled": True,
    "workbench_tutorial_seen": False,
    "dnd_enabled": False,
    "dnd_scheduled": False,
    "dnd_start": "22:00",
    "dnd_end": "08:00",
    "assistant_hints": True,
    "quick_launch_hotkey": "Ctrl+Alt+Space",
    "launch_folders": [],
    "mute_claude_toasts": True,
}


def valid_position(value):
    """Accept finite saved coordinates; malformed files must not block startup."""
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in value):
        return None
    try:
        coordinates = [int(v) for v in value]
    except (ValueError, OverflowError):
        return None
    return coordinates if all(-(2**31) <= v < 2**31 for v in coordinates) else None


def normalize_preferences(data):
    """Merge safe defaults while retaining every existing preference."""
    raw = data if isinstance(data, dict) else {}
    preferences = dict(raw)
    for key, value in DEFAULT_PREFERENCES.items():
        preferences.setdefault(key, value)
    scope = preferences.get("scope")
    preferences["scope"] = (scope if isinstance(scope, str)
                            and scope in ("global", "project", "conversation")
                            else "conversation")
    # One-time migration: the V1.1 `topmost` pin-double-duty becomes the
    # explicit always-on-top preference. An explicit new value always wins;
    # the legacy key itself stays untouched in the file.
    if "always_on_top" not in raw and "topmost" in raw:
        preferences["always_on_top"] = bool(raw["topmost"])
    if not isinstance(preferences.get("always_on_top"), bool):
        preferences["always_on_top"] = True
    if not isinstance(preferences.get("panel_pinned"), bool):
        preferences["panel_pinned"] = False
    if not isinstance(preferences.get("pet_motion"), bool):
        preferences["pet_motion"] = True
    if not isinstance(preferences.get("star_ring_enabled"), bool):
        preferences["star_ring_enabled"] = True
    if not isinstance(preferences.get("workbench_tutorial_seen"), bool):
        preferences["workbench_tutorial_seen"] = False
    if not isinstance(preferences.get("assistant_hints"), bool):
        preferences["assistant_hints"] = True
    if preferences.get("quick_launch_hotkey") not in ("Ctrl+Alt+Space", "Alt+Shift+Space",
                                                      "Ctrl+Alt+K", "off"):
        preferences["quick_launch_hotkey"] = "Ctrl+Alt+Space"
    if not isinstance(preferences.get("mute_claude_toasts"), bool):
        preferences["mute_claude_toasts"] = True
    folders = preferences.get("launch_folders")
    preferences["launch_folders"] = ([f for f in folders if isinstance(f, str) and f][:8]
                                     if isinstance(folders, list) else [])
    if preferences.get("launch_app") not in ("claude", "codex"):
        preferences.pop("launch_app", None)
    for key in ("dnd_enabled", "dnd_scheduled"):
        if not isinstance(preferences.get(key), bool):
            preferences[key] = False
    for key, fallback in (("dnd_start", "22:00"), ("dnd_end", "08:00")):
        value = preferences.get(key)
        if not (isinstance(value, str) and len(value) == 5 and value[2] == ":"
                and value[:2].isdigit() and value[3:].isdigit()
                and int(value[:2]) < 24 and int(value[3:]) < 60):
            preferences[key] = fallback
    for key in ("position", "pet_position"):
        if key in preferences:
            preferences[key] = valid_position(preferences[key])
    preferences["pet_scale_percent"] = normalize_pet_scale(
        preferences.get("pet_scale_percent"))
    schema = raw.get("settings_schema_version")
    if isinstance(schema, bool) or not isinstance(schema, int) or schema < 1:
        schema = 1 if raw else SETTINGS_SCHEMA_VERSION
    if (schema < 2 and normalize_tracking_provider(
            preferences.get("tracking_provider")) == "codex"):
        preferences["tracking_provider"] = "auto"
    preferences["settings_schema_version"] = max(schema, SETTINGS_SCHEMA_VERSION)
    preferences["token_number_format"] = normalize_token_format(
        preferences.get("token_number_format"))
    # Normalize retired provider choices (OpenCode) in memory; loading
    # never rewrites disk.
    preferences["tracking_provider"] = normalize_tracking_provider(
        preferences.get("tracking_provider"))
    preferences["language"] = normalize_language(preferences.get("language"))
    preferences["currency"] = normalize_currency(preferences.get("currency"))
    return preferences


def load_preferences(path: Path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    return normalize_preferences(data)


def save_preferences(path: Path, data):
    preferences = normalize_preferences(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(preferences, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)
