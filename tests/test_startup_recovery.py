"""Malformed local preferences cannot prevent the companion from starting."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from app_config import load_preferences, normalize_preferences, valid_position
from pet import DesktopPet
from widget import Panel


class StartupRecoveryTests(unittest.TestCase):
    def test_saved_scope_defaults_safely_and_preserves_file_bytes(self):
        values = ([], {}, None, True, 1, ['project'], 'invalid', 'task',
                  'global', 'project', 'conversation')
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'settings.json'
            for scope in values:
                with self.subTest(scope=scope):
                    raw = {'scope': scope, 'future_setting': {'kept': True}}
                    original = json.dumps(raw).encode('utf-8')
                    path.write_bytes(original)
                    loaded = load_preferences(path)
                    expected = (scope if isinstance(scope, str)
                                and scope in ('global', 'project', 'conversation')
                                else 'conversation')
                    self.assertEqual(loaded['scope'], expected)
                    self.assertEqual(loaded['future_setting'], raw['future_setting'])
                    self.assertEqual(path.read_bytes(), original)
                    self.assertEqual(raw['scope'], scope)

    def test_container_scopes_start_without_rewriting_settings(self):
        app = QApplication.instance() or QApplication([])
        for scope in ([], {}):
            with self.subTest(scope=scope), tempfile.TemporaryDirectory() as folder:
                with patch('widget.PREF_DIR', Path(folder)):
                    path = Path(folder) / 'settings.json'
                    original = json.dumps({'scope': scope}).encode('utf-8')
                    path.write_bytes(original)
                    panel = Panel(live=False)
                    try:
                        self.assertEqual(panel.prefs['scope'], 'conversation')
                        self.assertGreater(panel.width(), 0)
                        self.assertEqual(path.read_bytes(), original)
                    finally:
                        panel.shutdown()
                        panel.tray.hide()
                        panel.close()
                        panel.deleteLater()
                        app.processEvents()

    def test_saved_coordinates_and_motion_are_validated(self):
        for value in ([100, 'bad'], [None, 100], [float('inf'), 100],
                      [True, 100], [10**100, 100], '100,100', [100]):
            self.assertIsNone(valid_position(value), value)
        self.assertEqual(valid_position([-1200, 190]), [-1200, 190])
        self.assertFalse(normalize_preferences({'pet_motion': False})['pet_motion'])
        self.assertTrue(normalize_preferences({'pet_motion': 'false'})['pet_motion'])

    def test_malformed_coordinates_start_without_rewriting_settings(self):
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as folder, patch('widget.PREF_DIR', Path(folder)):
            path = Path(folder) / 'settings.json'
            original = json.dumps({'position': [100, 'bad'], 'pet_position': [None, 100]})
            path.write_text(original, encoding='utf-8')
            panel = Panel(live=False)
            try:
                panel.pet = DesktopPet(panel)
                panel.pet.activity_timer.stop()
                self.assertGreater(panel.width(), 0)
                self.assertGreater(panel.pet.width(), 0)
                self.assertEqual(path.read_text(encoding='utf-8'), original)
            finally:
                panel.task_manager.shutdown()
                panel.provider_poller.close()
                panel.pet.close()
                panel.clock.stop()
                panel.tray.hide()
                panel.closing = True
                panel.close()
                panel.deleteLater()
                app.processEvents()
