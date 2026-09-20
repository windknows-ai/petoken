import json
import tempfile
import unittest
from pathlib import Path

import desktop
from app_config import (APP_VERSION, DEFAULT_PREFERENCES, SETTINGS_SCHEMA_VERSION,
                        load_preferences, save_preferences)
from localization import DEFAULT_LANGUAGE, text


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "CodexWisp" / "settings.json"

    def tearDown(self):
        self.temp.cleanup()

    def test_app_version_is_shared_with_codex_sidecar(self):
        self.assertEqual(APP_VERSION, "1.0.0")
        self.assertEqual(desktop.APP_VERSION, APP_VERSION)

    def test_missing_file_uses_new_field_defaults(self):
        self.assertEqual(load_preferences(self.path), DEFAULT_PREFERENCES)
        self.assertEqual(DEFAULT_PREFERENCES["scope"], "conversation")

    def test_legacy_settings_migrate_without_losing_unknown_fields(self):
        legacy = {"scope": "project", "topmost": False, "future_setting": {"kept": True}}
        self.path.parent.mkdir(parents=True)
        self.path.write_text(json.dumps(legacy), encoding="utf-8")

        loaded = load_preferences(self.path)

        self.assertEqual(loaded["settings_schema_version"], SETTINGS_SCHEMA_VERSION)
        self.assertEqual(loaded["language"], DEFAULT_LANGUAGE)
        self.assertEqual(loaded["scope"], "project")
        self.assertFalse(loaded["topmost"])
        self.assertEqual(loaded["future_setting"], {"kept": True})

    def test_older_schema_is_upgraded_and_future_schema_is_preserved(self):
        self.assertEqual(load_preferences_from({"settings_schema_version": 0})["settings_schema_version"], 1)
        self.assertEqual(load_preferences_from({"settings_schema_version": 3})["settings_schema_version"], 3)

    def test_language_preference_persists_through_atomic_save(self):
        save_preferences(self.path, {"language": "en", "pinned": "thread-1",
                                     "token_number_format": "full"})

        self.assertEqual(load_preferences(self.path)["language"], "en")
        self.assertEqual(load_preferences(self.path)["pinned"], "thread-1")
        self.assertEqual(load_preferences(self.path)["token_number_format"], "full")
        self.assertFalse(self.path.with_suffix(".tmp").exists())
        self.assertEqual(text("settings_title", "en"), "petoken · Settings")

    def test_invalid_token_number_format_falls_back_to_compact(self):
        save_preferences(self.path, {"token_number_format": "future-format"})
        self.assertEqual(load_preferences(self.path)["token_number_format"], "compact")


def load_preferences_from(data):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "settings.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return load_preferences(path)


if __name__ == "__main__":
    unittest.main()
