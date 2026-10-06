"""Bring a Claude Code task's window to the front (V1.6 B: one-click jump).

Claude Code's live-session registry gives each running session's process
ID. Walking up from that process, the first ancestor that owns a visible
top-level window is where the session lives: the Claude desktop app, a
Windows Terminal window, VS Code, or the classic console of a shell (owned
by its ``conhost.exe`` child). That window is restored and raised.

This finds the app window, not a specific terminal tab or desktop
conversation, so the result is reported as 'app'. No window is ever
started, typed into or closed. Explorer and system processes are never
raised.
"""
from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

STOP_AT = {'explorer.exe', 'services.exe', 'svchost.exe', 'wininit.exe', 'winlogon.exe',
           'system', 'userinit.exe', 'sihost.exe', 'runtimebroker.exe'}
CONSOLE_HOSTS = {'conhost.exe', 'openconsole.exe'}
MAX_DEPTH = 12
SW_RESTORE = 9
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080


def _windows_by_pid():
    """Visible, titled, non-tool top-level windows per process ID."""
    if sys.platform != 'win32':
        return {}
    user32 = ctypes.windll.user32
    found = {}

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def visit(hwnd, _):
        if not user32.IsWindowVisible(hwnd) or user32.GetWindowTextLengthW(hwnd) == 0:
            return True
        if user32.GetWindowLongW(hwnd, GWL_EXSTYLE) & WS_EX_TOOLWINDOW:
            return True
        if user32.GetWindow(hwnd, 4):  # GW_OWNER: owned pop-ups are not main windows.
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        found.setdefault(pid.value, []).append(hwnd)
        return True

    user32.EnumWindows(visit, 0)
    return found


def find_window(pid, windows=None, process_class=None):
    """(hwnd, owner pid) of the window hosting ``pid``, or (None, None)."""
    import psutil
    process_class = process_class or psutil.Process
    windows = _windows_by_pid() if windows is None else windows
    try:
        process = process_class(pid)
    except (psutil.Error, ValueError, TypeError):
        return None, None
    for _ in range(MAX_DEPTH):
        try:
            name = (process.name() or '').lower()
        except psutil.Error:
            return None, None
        if name in STOP_AT:
            return None, None
        if windows.get(process.pid):
            return windows[process.pid][0], process.pid
        try:
            hosts = [child for child in process.children()
                     if (child.name() or '').lower() in CONSOLE_HOSTS]
        except psutil.Error:
            hosts = []
        for host in hosts:
            if windows.get(host.pid):
                return windows[host.pid][0], host.pid
        try:
            process = process.parent()
        except psutil.Error:
            return None, None
        if process is None:
            return None, None
    return None, None


def raise_window(hwnd):
    if sys.platform != 'win32' or not hwnd:
        return False
    user32 = ctypes.windll.user32
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
    user32.SetForegroundWindow(hwnd)
    return user32.GetForegroundWindow() == hwnd


def session_pid(session_id, home=None):
    """Process ID of a running session from Claude Code's registry, or None."""
    import json
    from pathlib import Path
    import claude_usage
    folder = Path(home if home is not None else claude_usage.default_home()) / 'sessions'
    for path in folder.glob('*.json'):
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict) or data.get('sessionId') != session_id:
            continue
        pid = data.get('pid')
        if (isinstance(pid, int) and not isinstance(pid, bool) and pid > 0
                and claude_usage._process_alive(pid, data.get('procStart'))):
            return pid
    return None


def focus(session_id, home=None):
    """'app' when the session's window was raised, otherwise None."""
    pid = session_pid(session_id, home)
    if pid is None:
        return None
    hwnd, _owner = find_window(pid)
    return 'app' if hwnd and raise_window(hwnd) else None
