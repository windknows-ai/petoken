"""Quick launch (V1.6 C): hand a new task to Claude Code or Codex.

A global hotkey (Ctrl+Alt+Space, opt-out in Settings), the pet's menu or
the tray open a small window: what to do, which project folder, which
app. Start opens a new terminal in that folder running the app's CLI on
the prompt (``claude_launch`` / Codex's ``codex_launch``); the task then
shows up as a star like any other. Nothing runs without the user pressing
Start, and no permission flags are added.

Recent folders: the ones used here before, then folders of live Claude
sessions and recent Codex threads that still exist.
"""
from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from pathlib import Path

from PySide6.QtCore import QAbstractNativeEventFilter, QObject, Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QButtonGroup, QComboBox, QDialog, QFileDialog, QHBoxLayout, QLabel,
                               QPlainTextEdit, QPushButton, QRadioButton, QVBoxLayout)

import claude_launch
from localization import text
from providers import PROVIDER_NAMES

HOTKEY_ID = 0x5045   # 'PE'
MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x4000
WM_HOTKEY = 0x0312
# Choices in Settings, in fallback order: when the chosen one is taken by
# another program, the next free one is used instead.
HOTKEYS = {
    'Ctrl+Alt+Space': (MOD_CONTROL | MOD_ALT, 0x20),
    'Alt+Shift+Space': (MOD_ALT | MOD_SHIFT, 0x20),
    'Ctrl+Alt+K': (MOD_CONTROL | MOD_ALT, 0x4B),
}
DEFAULT_HOTKEY = 'Ctrl+Alt+Space'
MAX_RECENT = 8


def _clean_folder(value):
    if not isinstance(value, str) or not value.strip():
        return None
    value = value.strip()
    if value.startswith('\\\\?\\UNC\\'):
        value = '\\\\' + value[8:]
    elif value.startswith('\\\\?\\'):
        value = value[4:]
    try:
        path = Path(value)
        return str(path) if path.is_dir() else None
    except OSError:
        return None


def known_folders(prefs, claude_home=None, codex_rows=None):
    """Recent project folders, most useful first, existing ones only."""
    found = list(prefs.get('launch_folders') or [])
    try:
        from claude_usage import default_home, read_registry
        registry = read_registry(claude_home if claude_home is not None else default_home()) or {}
        found += [entry.get('cwd') for entry in registry.values()]
    except Exception:
        pass
    try:
        if codex_rows is None:
            import codex_recap
            from usage import CodexStore
            codex_rows = codex_recap.thread_rows(CodexStore().home)[:30]
        found += [row.get('cwd') for row in codex_rows]
    except Exception:
        pass
    out, seen = [], set()
    for value in found:
        folder = _clean_folder(value)
        if folder and folder.lower() not in seen:
            seen.add(folder.lower())
            out.append(folder)
    return out[:MAX_RECENT + 4]


def remember_folder(prefs, folder):
    folders = [f for f in prefs.get('launch_folders') or [] if isinstance(f, str) and f.lower() != folder.lower()]
    prefs['launch_folders'] = [folder] + folders[:MAX_RECENT - 1]


def codex_available():
    try:
        import codex_launch
        return codex_launch.available()
    except Exception:
        return False


def build_command(app, folder, prompt):
    if app == 'claude':
        return claude_launch.launch_command(folder, prompt)
    import codex_launch
    return codex_launch.launch_command(folder, prompt)


class QuickLaunchDialog(QDialog):
    def __init__(self, panel, parent=None):
        super().__init__(parent)
        self.panel = panel
        language = self.language = panel.prefs.get('language')
        self.setWindowTitle(text('launch_title', language))
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(text('launch_prompt', language)))
        self.prompt = QPlainTextEdit()
        self.prompt.setPlaceholderText(text('launch_prompt_hint', language))
        self.prompt.setFixedHeight(96)
        layout.addWidget(self.prompt)
        layout.addWidget(QLabel(text('launch_folder', language)))
        row = QHBoxLayout()
        self.folder = QComboBox()
        self.folder.setEditable(True)
        self.folder.setInsertPolicy(QComboBox.NoInsert)
        for folder in known_folders(panel.prefs):
            self.folder.addItem(folder)
        browse = QPushButton(text('launch_browse', language))
        browse.clicked.connect(self.browse)
        row.addWidget(self.folder, 1)
        row.addWidget(browse)
        layout.addLayout(row)
        apps = QHBoxLayout()
        self.apps = QButtonGroup(self)
        self.claude = QRadioButton(PROVIDER_NAMES['claude'])
        self.codex = QRadioButton(PROVIDER_NAMES['codex'])
        self.claude.setEnabled(claude_launch.available())
        self.codex.setEnabled(codex_available())
        for button in (self.claude, self.codex):
            self.apps.addButton(button)
            apps.addWidget(button)
            if not button.isEnabled():
                button.setToolTip(text('launch_app_missing', language))
        apps.addStretch(1)
        layout.addLayout(apps)
        last = panel.prefs.get('launch_app')
        chosen = self.codex if last == 'codex' and self.codex.isEnabled() else self.claude
        if not chosen.isEnabled():
            chosen = self.codex if self.codex.isEnabled() else None
        if chosen is not None:
            chosen.setChecked(True)
        self.error = QLabel('')
        self.error.setWordWrap(True)
        self.error.setStyleSheet('color:#8A2E4A;')
        self.error.hide()
        layout.addWidget(self.error)
        buttons = QHBoxLayout()
        note = QLabel(text('launch_note', language))
        note.setObjectName('muted')
        note.setWordWrap(True)
        buttons.addWidget(note, 1)
        cancel = QPushButton(text('launch_cancel', language))
        cancel.clicked.connect(self.reject)
        self.start = QPushButton(text('launch_start', language))
        self.start.setDefault(True)
        self.start.clicked.connect(self.launch)
        buttons.addWidget(cancel)
        buttons.addWidget(self.start)
        layout.addLayout(buttons)
        QShortcut(QKeySequence('Ctrl+Return'), self, activated=self.launch)
        self.prompt.setFocus()

    def browse(self):
        folder = QFileDialog.getExistingDirectory(self, text('launch_folder', self.language),
                                                  self.folder.currentText())
        if folder:
            self.folder.setEditText(str(Path(folder)))

    def app(self):
        return 'codex' if self.codex.isChecked() else 'claude' if self.claude.isChecked() else None

    def fail(self, key):
        self.error.setText(text(key, self.language))
        self.error.show()

    def launch(self, starter=None):
        prompt = self.prompt.toPlainText().strip()
        folder = _clean_folder(self.folder.currentText())
        app = self.app()
        if not prompt:
            return self.fail('launch_need_prompt')
        if not folder:
            return self.fail('launch_need_folder')
        if app is None:
            return self.fail('launch_app_missing')
        try:
            argv = build_command(app, folder, prompt)
            (starter or claude_launch.launch)(argv)
        except ValueError:
            return self.fail('launch_too_long' if len(prompt) > 8000 else 'launch_need_folder')
        except (RuntimeError, OSError):
            return self.fail('launch_failed')
        remember_folder(self.panel.prefs, folder)
        self.panel.prefs['launch_app'] = app
        try:
            self.panel.persist()
        except Exception:
            pass
        self.accept()
        return True


class _HotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self, owner):
        super().__init__()
        self.owner = owner

    def nativeEventFilter(self, event_type, message):
        try:
            return self.owner.handle(event_type, message)
        except Exception:
            return False, 0


class GlobalHotkey(QObject):
    """Ctrl+Alt+Space anywhere in Windows (RegisterHotKey); install
    ``self.filter`` on the application to receive it."""

    pressed = Signal()

    def __init__(self):
        super().__init__()
        self.registered = None    # Name of the active combination, or None.
        self.filter = _HotkeyFilter(self)

    def register(self, wanted=DEFAULT_HOTKEY, register=None):
        """Use ``wanted``, or the next free choice; returns the active name."""
        if sys.platform != 'win32':
            return None
        register = register or (lambda mods, key: ctypes.windll.user32.RegisterHotKey(
            None, HOTKEY_ID, mods | MOD_NOREPEAT, key))
        names = list(HOTKEYS)
        start = names.index(wanted) if wanted in HOTKEYS else 0
        order = names[start:] + names[:start]
        if self.registered == order[0]:
            return self.registered
        self.unregister()
        for name in order:
            if register(*HOTKEYS[name]):
                self.registered = name
                break
        return self.registered

    def unregister(self, unregister=None):
        if self.registered:
            (unregister or (lambda: ctypes.windll.user32.UnregisterHotKey(None, HOTKEY_ID)))()
            self.registered = None

    def handle(self, event_type, message):
        if self.registered and event_type in (b'windows_generic_MSG', 'windows_generic_MSG'):
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                self.pressed.emit()
                return True, 0
        return False, 0
