import json
import tempfile
import unittest
from pathlib import Path

import desktop
from app_config import (APP_VERSION, DEFAULT_PREFERENCES, SETTINGS_SCHEMA_VERSION,
                        load_preferences, save_preferences)
from localization import DEFAULT_LANGUAGE, normalize_language, text


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "CodexWisp" / "settings.json"

    def tearDown(self):
        self.temp.cleanup()

    def test_app_version_is_shared_with_codex_sidecar(self):
        self.assertEqual(APP_VERSION, "1.2.0")
        self.assertEqual(desktop.APP_VERSION, APP_VERSION)

    def test_ring_visibility_defaults_and_atomic_persistence(self):
        self.assertTrue(load_preferences(self.path)['star_ring_enabled'])
        save_preferences(self.path, {'star_ring_enabled': False, 'future_setting': {'kept': True}})
        loaded = load_preferences(self.path)
        self.assertFalse(loaded['star_ring_enabled'])
        self.assertEqual(loaded['future_setting'], {'kept': True})
        self.assertFalse(self.path.with_suffix('.tmp').exists())
        for invalid in (None, 0, 1, 'false', [], {}):
            self.assertTrue(load_preferences_from({'star_ring_enabled': invalid})['star_ring_enabled'])

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

    def test_supported_languages_load_and_invalid_language_falls_back(self):
        self.assertEqual(load_preferences_from({"language": "zh_CN"})["language"], "zh_CN")
        self.assertEqual(load_preferences_from({"language": "en"})["language"], "en")
        self.assertEqual(load_preferences_from({"language": "fr"})["language"], DEFAULT_LANGUAGE)
        self.assertEqual(normalize_language(None), DEFAULT_LANGUAGE)

    def test_invalid_token_number_format_falls_back_to_compact(self):
        save_preferences(self.path, {"token_number_format": "future-format"})
        self.assertEqual(load_preferences(self.path)["token_number_format"], "compact")

    def test_currency_persists_and_invalid_falls_back_to_cad(self):
        save_preferences(self.path, {"currency": "EUR"})
        self.assertEqual(load_preferences(self.path)["currency"], "EUR")
        save_preferences(self.path, {"currency": "GBP"})
        self.assertEqual(load_preferences(self.path)["currency"], "CAD")
        self.assertEqual(load_preferences_from({"currency": "CNY"})["currency"], "CNY")
        self.assertEqual(load_preferences_from({})["currency"], "CAD")

    def test_legacy_pricing_keys_load_safely_and_are_preserved(self):
        legacy = {"manual_fx": 1.25, "prices": {"gpt-6-astra": [1, 2, 3, 4]}, "currency": "USD"}
        loaded = load_preferences_from(legacy)
        self.assertEqual(loaded["manual_fx"], 1.25)
        self.assertEqual(loaded["prices"], {"gpt-6-astra": [1, 2, 3, 4]})
        self.assertEqual(loaded["currency"], "USD")


    def test_tracking_provider_defaults_codex_and_persists(self):
        self.assertEqual(DEFAULT_PREFERENCES["tracking_provider"], "codex")
        self.assertEqual(load_preferences(self.path)["tracking_provider"],
                         "codex")
        save_preferences(self.path, {"tracking_provider": "codex"})
        self.assertEqual(load_preferences(self.path)["tracking_provider"],
                         "codex")

    def test_tracking_provider_invalid_and_legacy_fall_back(self):
        save_preferences(self.path, {"tracking_provider": "All Providers"})
        self.assertEqual(load_preferences(self.path)["tracking_provider"],
                         "codex")
        self.assertEqual(
            load_preferences_from({"scope": "global"})["tracking_provider"],
            "codex")
        self.assertEqual(
            load_preferences_from(
                {"tracking_provider": " Codex "})["tracking_provider"],
            "codex")

    def test_retired_choices_normalize_without_rewriting_on_load(self):
        self.path.parent.mkdir(parents=True)
        for retired in ("auto", "opencode", "All Providers", None):
            with self.subTest(retired=retired):
                original = json.dumps({"tracking_provider": retired,
                                       "pinned": "thread-1",
                                       "future_setting": {"kept": True}})
                self.path.write_text(original, encoding="utf-8")
                loaded = load_preferences(self.path)
                self.assertEqual(loaded["tracking_provider"], "codex")
                self.assertEqual(loaded["pinned"], "thread-1")
                self.assertEqual(loaded["future_setting"], {"kept": True})
                self.assertEqual(self.path.read_text(encoding="utf-8"), original)

    def test_saving_retired_choice_persists_codex_only(self):
        for retired in ("auto", "opencode"):
            with self.subTest(retired=retired):
                save_preferences(self.path, {"tracking_provider": retired})
                self.assertEqual(load_preferences(self.path)["tracking_provider"], "codex")
                self.assertEqual(json.loads(self.path.read_text(encoding="utf-8"))[
                    "tracking_provider"], "codex")


def load_preferences_from(data):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "settings.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return load_preferences(path)


if __name__ == "__main__":
    unittest.main()
