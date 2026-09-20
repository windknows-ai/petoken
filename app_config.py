"""Application metadata and backward-compatible preference storage."""
from __future__ import annotations

import json
from pathlib import Path

from localization import DEFAULT_LANGUAGE

APP_VERSION = "1.0.0"
SETTINGS_SCHEMA_VERSION = 1
DEFAULT_PREFERENCES = {
    "settings_schema_version": SETTINGS_SCHEMA_VERSION,
    "language": DEFAULT_LANGUAGE,
    "scope": "conversation",
}


def normalize_preferences(data):
    """Merge safe defaults while retaining every existing preference."""
    preferences = dict(data) if isinstance(data, dict) else {}
    for key, value in DEFAULT_PREFERENCES.items():
        preferences.setdefault(key, value)
    schema = preferences.get("settings_schema_version")
    if isinstance(schema, bool) or not isinstance(schema, int) or schema < 1:
        preferences["settings_schema_version"] = SETTINGS_SCHEMA_VERSION
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
