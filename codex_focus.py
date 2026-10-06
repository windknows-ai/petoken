"""Best-effort Windows focus, without opening/resuming threads or changing settings."""
from __future__ import annotations

import base64
import ctypes
from ctypes import wintypes
import json
import ntpath
import shutil
import subprocess
import sys

from codex_recap import thread_info


def _powershell(script):
    executable = shutil.which('powershell.exe') or shutil.which('pwsh.exe')
    if not executable:
        raise OSError('PowerShell unavailable')
    encoded = base64.b64encode(script.encode('utf-16le')).decode('ascii')
    result = subprocess.run([executable, '-NoProfile', '-NonInteractive', '-EncodedCommand', encoded],
                            capture_output=True, timeout=4, check=True,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    return result.stdout.decode('utf-8-sig')


def _processes():
    # Read only Codex and possible terminal ancestors. Never export other command lines.
    script = """$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$filter = "Name='codex.exe' OR Name='ChatGPT.exe' OR Name='WindowsTerminal.exe' OR Name='OpenConsole.exe' OR Name='conhost.exe' OR Name='powershell.exe' OR Name='pwsh.exe' OR Name='cmd.exe' OR Name='node.exe'"
@(Get-CimInstance Win32_Process -Filter $filter | ForEach-Object {
    [pscustomobject]@{pid=$_.ProcessId; parent_pid=$_.ParentProcessId; name=$_.Name;
        path=$_.ExecutablePath; command_line=$(if ($_.Name -ieq 'codex.exe') {$_.CommandLine} else {''})}
}) | ConvertTo-Json -Compress
"""
    result = json.loads(_powershell(script))
    if not isinstance(result, list) or not all(isinstance(p, dict) for p in result):
        raise ValueError('Unknown process snapshot')
    return result


def _argv(command_line):
    if not isinstance(command_line, str) or not command_line:
        return []
    shell = ctypes.WinDLL('shell32', use_last_error=True)
    shell.CommandLineToArgvW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_int)]
    shell.CommandLineToArgvW.restype = ctypes.POINTER(wintypes.LPWSTR)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    count = ctypes.c_int()
    pointer = shell.CommandLineToArgvW(command_line, ctypes.byref(count))
    if not pointer:
        return []
    try:
        return [pointer[i] for i in range(count.value)]
    finally:
        kernel.LocalFree(pointer)


def _resumes(process, thread_id):
    if (str(process.get('name', '')).lower() != 'codex.exe'
            or not isinstance(process.get('pid'), int) or process['pid'] <= 0):
        return False
    argv = _argv(process.get('command_line'))
    arguments = argv[1:]
    if arguments[:2] == ['exec', 'resume']:
        arguments = arguments[1:]
    # Only a positional resume ID is evidence; UUIDs in prompts/titles are not.
    return len(arguments) >= 2 and arguments[0] == 'resume' and arguments[1] == thread_id


def _windows():
    user = ctypes.WinDLL('user32', use_last_error=True)
    user.IsWindowVisible.argtypes = [wintypes.HWND]
    user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, ctypes.c_ssize_t)
    user.EnumWindows.argtypes = [callback_type, ctypes.c_ssize_t]
    windows = []

    @callback_type
    def collect(handle, _):
        if user.IsWindowVisible(handle):
            process_id = wintypes.DWORD()
            user.GetWindowThreadProcessId(handle, ctypes.byref(process_id))
            windows.append(dict(hwnd=handle, pid=process_id.value))
        return True

    if not user.EnumWindows(collect, 0):
        raise OSError('Cannot enumerate windows')
    return windows


def _console_window(process_id):
    # Attach in an isolated helper, never detach Petoken's own console.
    if not isinstance(process_id, int) or isinstance(process_id, bool) or not 0 < process_id < 2**32:
        return 0
    script = """$ErrorActionPreference = 'Stop'
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class PetokenConsole {
    [DllImport("kernel32.dll")] public static extern bool AttachConsole(uint processId);
    [DllImport("kernel32.dll")] public static extern bool FreeConsole();
    [DllImport("kernel32.dll")] public static extern IntPtr GetConsoleWindow();
}
'@
[PetokenConsole]::FreeConsole() | Out-Null
$handle = 0
try {
    if ([PetokenConsole]::AttachConsole(PROCESS_ID)) {
        $handle = [PetokenConsole]::GetConsoleWindow().ToInt64()
    }
} finally { [PetokenConsole]::FreeConsole() | Out-Null }
[Console]::WriteLine($handle)
""".replace('PROCESS_ID', str(process_id))
    return int(_powershell(script).strip())


def _foreground(window):
    user = ctypes.WinDLL('user32', use_last_error=True)
    user.IsWindowVisible.argtypes = [wintypes.HWND]
    user.IsIconic.argtypes = [wintypes.HWND]
    user.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user.SetForegroundWindow.argtypes = [wintypes.HWND]
    user.GetForegroundWindow.restype = wintypes.HWND
    user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    process_id = wintypes.DWORD()
    user.GetWindowThreadProcessId(window['hwnd'], ctypes.byref(process_id))
    if process_id.value != window['pid'] or not user.IsWindowVisible(window['hwnd']):
        return False
    if user.IsIconic(window['hwnd']):
        user.ShowWindow(window['hwnd'], 9)  # SW_RESTORE.
    user.SetForegroundWindow(window['hwnd'])
    return user.GetForegroundWindow() == window['hwnd']


def _desktop_process(process):
    path = str(process.get('path') or '').replace('/', '\\').lower()
    name = str(process.get('name') or '').lower()
    return name in ('chatgpt.exe', 'codex.exe') and (
        'openai.codex' in path or '\\openai\\codex\\app\\' in path)


def focus(home, thread_id):
    """'exact' for a proven console; 'app' for app-level focus; otherwise None."""
    if sys.platform != 'win32':
        return None
    row = thread_info(home, thread_id)
    if row is None:
        return None
    try:
        processes, windows = _processes(), _windows()
        if row.get('source') == 'desktop':
            ids = {p['pid'] for p in processes if _desktop_process(p)}
            candidates = [w for w in windows if w['pid'] in ids]
            return 'app' if candidates and _foreground(candidates[0]) else None
        if row.get('source') not in ('cli', 'exec'):
            return None
        matches = [p for p in processes if _resumes(p, thread_id)]
        if len(matches) != 1:
            return None
        try:
            handle = _console_window(matches[0]['pid'])
        except (OSError, ValueError, subprocess.SubprocessError):
            handle = 0
        exact = [w for w in windows if w['hwnd'] == handle]
        if exact:
            return 'exact' if _foreground(exact[0]) else None
        # A pseudoconsole's HWND is hidden. A verified terminal ancestor can
        # identify its app window, but not the active tab/pane inside that window.
        by_pid = {p['pid']: p for p in processes}
        process, seen = matches[0], set()
        while process.get('parent_pid') in by_pid and process['pid'] not in seen:
            seen.add(process['pid'])
            process = by_pid[process['parent_pid']]
            if ntpath.basename(str(process.get('name') or '')).lower() == 'windowsterminal.exe':
                candidates = [w for w in windows if w['pid'] == process['pid']]
                return 'app' if len(candidates) == 1 and _foreground(candidates[0]) else None
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError):
        pass
    return None
