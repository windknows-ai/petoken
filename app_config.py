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

APP_VERSION = "1.2.0"
SETTINGS_SCHEMA_VERSION = 1
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
}


def normalize_preferences(data):
    """Merge safe defaults while retaining every existing preference."""
    raw = data if isinstance(data, dict) else {}
    preferences = dict(raw)
    for key, value in DEFAULT_PREFERENCES.items():
        preferences.setdefault(key, value)
    # One-time migration: the V1.1 `topmost` pin-double-duty becomes the
    # explicit always-on-top preference. An explicit new value always wins;
    # the legacy key itself stays untouched in the file.
    if "always_on_top" not in raw and "topmost" in raw:
        preferences["always_on_top"] = bool(raw["topmost"])
    if not isinstance(preferences.get("always_on_top"), bool):
        preferences["always_on_top"] = True
    if not isinstance(preferences.get("panel_pinned"), bool):
        preferences["panel_pinned"] = False
    preferences["pet_scale_percent"] = normalize_pet_scale(
        preferences.get("pet_scale_percent"))
    schema = preferences.get("settings_schema_version")
    if isinstance(schema, bool) or not isinstance(schema, int) or schema < 1:
        preferences["settings_schema_version"] = SETTINGS_SCHEMA_VERSION
    preferences["token_number_format"] = normalize_token_format(
        preferences.get("token_number_format"))
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
