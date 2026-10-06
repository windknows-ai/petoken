import ctypes
import tempfile
import unittest
from ctypes import wintypes
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

import quick_launch

APP = QApplication.instance() or QApplication([])


class FakePanel:
    def __init__(self, folders=()):
        self.prefs = dict(language='en', launch_folders=list(folders))
        self.saved = 0

    def persist(self):
        self.saved += 1


class FolderTests(unittest.TestCase):
    def test_known_folders_dedupe_strip_prefix_and_skip_missing(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            prefs = dict(launch_folders=[a, a.upper(), a + '-gone'])
            rows = [dict(cwd='\\\\?\\' + b), dict(cwd=None), dict(cwd=a)]
            with patch('claude_usage.read_registry', return_value={}):
                self.assertEqual(quick_launch.known_folders(prefs, claude_home=a, codex_rows=rows), [a, b])

    def test_remember_folder_moves_to_front(self):
        prefs = dict(launch_folders=['C:\\a', 'C:\\b'])
        quick_launch.remember_folder(prefs, 'c:\\B')
        self.assertEqual(prefs['launch_folders'], ['c:\\B', 'C:\\a'])


class DialogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.panel = FakePanel([self.temp.name])
        with patch('claude_launch.available', return_value=True), \
                patch('quick_launch.codex_available', return_value=False), \
                patch('quick_launch.known_folders', return_value=[self.temp.name]):
            self.dialog = quick_launch.QuickLaunchDialog(self.panel)

    def tearDown(self):
        self.dialog.close()
        self.temp.cleanup()

    def test_validation_then_launch(self):
        started = []
        self.assertIsNone(self.dialog.launch(started.append))
        self.assertEqual(self.dialog.error.text(), 'Write what it should do first.')
        self.dialog.prompt.setPlainText('add "dark mode"')
        self.dialog.folder.setEditText(self.temp.name + '-missing')
        self.assertIsNone(self.dialog.launch(started.append))
        self.assertEqual(started, [])
        self.dialog.folder.setEditText(self.temp.name)
        with patch('quick_launch.build_command', return_value=['wt.exe', 'x']) as build:
            self.assertTrue(self.dialog.launch(started.append))
        build.assert_called_once_with('claude', str(Path(self.temp.name)), 'add "dark mode"', model=None, effort=None)
        self.assertEqual(started, [['wt.exe', 'x']])
        self.assertEqual(self.panel.prefs['launch_app'], 'claude')
        self.assertEqual(self.panel.saved, 1)

    def test_model_effort_and_chat_mode(self):
        models = [self.dialog.model.itemData(i) for i in range(self.dialog.model.count())]
        efforts = [self.dialog.effort.itemData(i) for i in range(self.dialog.effort.count())]
        self.assertEqual(models, ['', 'fable', 'opus', 'sonnet', 'haiku'])
        self.assertEqual(efforts, ['', 'low', 'medium', 'high', 'xhigh', 'max'])
        self.dialog.model.setCurrentIndex(self.dialog.model.findData('opus'))
        self.dialog.effort.setCurrentIndex(self.dialog.effort.findData('high'))
        self.dialog.prompt.setPlainText('What is a monad?')
        self.dialog.chat.setChecked(True)
        self.assertFalse(self.dialog.folder.isEnabled())
        with patch('quick_launch.chat_folder', return_value=self.temp.name),                 patch('quick_launch.build_command', return_value=['x']) as build:
            self.assertTrue(self.dialog.launch(lambda argv: None))
        build.assert_called_once_with('claude', self.temp.name, 'What is a monad?', model='opus', effort='high')
        self.assertEqual(self.panel.prefs['launch_options']['claude'], dict(model='opus', effort='high'))
        self.assertEqual(self.panel.prefs['launch_folders'], [self.temp.name])   # Chats are not remembered.

    def test_missing_codex_cannot_be_chosen(self):
        self.assertFalse(self.dialog.codex.isEnabled())
        self.assertTrue(self.dialog.claude.isChecked())


class HotkeyTests(unittest.TestCase):
    def test_wm_hotkey_message_is_recognised(self):
        hotkey = quick_launch.GlobalHotkey()
        hotkey.registered = 'Ctrl+Alt+K'   # Pretend: never grab a real system-wide key in tests.
        seen = []
        hotkey.pressed.connect(lambda: seen.append(1))
        message = wintypes.MSG()
        message.message, message.wParam = quick_launch.WM_HOTKEY, quick_launch.HOTKEY_ID
        self.assertEqual(hotkey.filter.nativeEventFilter(b'windows_generic_MSG', ctypes.addressof(message)), (True, 0))
        message.wParam = 1
        self.assertEqual(hotkey.filter.nativeEventFilter(b'windows_generic_MSG', ctypes.addressof(message)), (False, 0))
        self.assertEqual(seen, [1])
        hotkey.registered = None

    def test_taken_choice_falls_back_to_the_next_free_one(self):
        hotkey = quick_launch.GlobalHotkey()
        free = {quick_launch.HOTKEYS['Ctrl+Alt+K']}
        tried = []

        def register(mods, key):
            tried.append((mods, key))
            return (mods, key) in free
        self.assertEqual(hotkey.register('Alt+Shift+Space', register), 'Ctrl+Alt+K')
        self.assertEqual(tried, [quick_launch.HOTKEYS['Alt+Shift+Space'], quick_launch.HOTKEYS['Ctrl+Alt+K']])
        free.clear()
        hotkey.unregister(lambda: None)
        self.assertIsNone(hotkey.register('Ctrl+Alt+Space', register))


if __name__ == '__main__':
    unittest.main()
