"""Mute the Claude desktop app's own Windows notifications while Petoken runs.

With Claude instant notifications on, a finished Claude task would pop up
twice: once from the Claude desktop app and once from Petoken. While the
setting is on, Petoken turns off the Claude app's toasts in the same
per-user place as Windows Settings > System > Notifications > Claude
(``HKCU\\...\\Notifications\\Settings\\<app id>\\Enabled``) and puts the
previous value back when Petoken exits or the setting is turned off.

The previous value is written to a small state file first, so if Petoken
ever stops without restoring, the next start still knows the user's own
choice. No administrator rights are needed; nothing outside the current
user's notification settings is touched. Only the Claude desktop app's
own entry (``Claude_<publisher>!Claude``) is changed.
"""
from __future__ import annotations

import json
import re
import sys

import claude_statusline as bridge

SETTINGS_KEY = r'Software\Microsoft\Windows\CurrentVersion\Notifications\Settings'
STATE_NAME = 'claude-toasts-muted.json'
_CLAUDE_APP = re.compile(r'^Claude_[a-z0-9]{13}!Claude$')


class WindowsRegistry:
    """The few registry calls this module needs (current user only)."""

    def __init__(self):
        import winreg
        self.winreg = winreg

    def subkeys(self, path):
        winreg = self.winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
                count = winreg.QueryInfoKey(key)[0]
                return [winreg.EnumKey(key, index) for index in range(count)]
        except OSError:
            return []

    def get(self, path, name):
        winreg = self.winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
                return winreg.QueryValueEx(key, name)[0]
        except OSError:
            return None

    def set(self, path, name, value):
        winreg = self.winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, path) as key:
            winreg.SetValueEx(key, name, 0, winreg.REG_DWORD, int(value))

    def delete(self, path, name):
        winreg = self.winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, name)
        except OSError:
            pass


def _registry(registry):
    if registry is not None:
        return registry
    return WindowsRegistry() if sys.platform == 'win32' else None


def state_path():
    return bridge.data_dir() / STATE_NAME


def claude_apps(registry=None):
    """Notification app IDs of the Claude desktop app on this account."""
    registry = _registry(registry)
    if registry is None:
        return []
    return [name for name in registry.subkeys(SETTINGS_KEY) if _CLAUDE_APP.match(name)]


def _load_state(path):
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def mute(registry=None, path=None):
    """Turn the Claude app's toasts off; returns the app IDs muted."""
    registry = _registry(registry)
    path = path if path is not None else state_path()
    apps = claude_apps(registry)
    if registry is None or not apps:
        return []
    state = _load_state(path) or {}
    for app in apps:
        if app not in state:   # Keep the first value we saw: the user's own choice.
            state[app] = registry.get(f'{SETTINGS_KEY}\\{app}', 'Enabled')
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state), encoding='utf-8')
    except OSError:
        return []   # Without a record of the old value, change nothing.
    muted = []
    for app in apps:
        try:
            registry.set(f'{SETTINGS_KEY}\\{app}', 'Enabled', 0)
            muted.append(app)
        except OSError:
            pass
    return muted


def restore(registry=None, path=None):
    """Put back what the Claude app's toasts were before Petoken muted them."""
    registry = _registry(registry)
    path = path if path is not None else state_path()
    state = _load_state(path)
    if registry is None or state is None:
        return False
    for app, value in state.items():
        if not _CLAUDE_APP.match(app):
            continue
        key = f'{SETTINGS_KEY}\\{app}'
        try:
            if value is None:
                registry.delete(key, 'Enabled')   # It was never set: Windows default (on).
            else:
                registry.set(key, 'Enabled', value)
        except OSError:
            return False
    try:
        path.unlink()
    except OSError:
        pass
    return True
