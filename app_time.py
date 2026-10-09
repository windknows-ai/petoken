"""Per-program screen time for Petoken's Reports (2.3).

Reports can show "how long you spent in each program today / this week".
Everything stays on this computer, in a local SQLite file. Only the program's
file name (chrome.exe) and its friendly name (Google Chrome) are stored: never
window titles, never content. Recording is opt-in; the app decides when to
create an AppTimeTracker and call tick().

Three small pieces, all Qt-free:

  - foreground_program(): which program is in front right now (ctypes, Windows
    only; None for the desktop, the lock screen, ourselves, or any failure).
  - AppTimeStore: SQLite totals per (day, program). A connection per call, so
    the file is never held open (Windows cannot delete or move it then).
  - AppTimeTracker: turns "sample every few seconds" into seconds per program.
    Idle time (you are away) and sleep/hibernate gaps are never counted, and
    an interval that crosses local midnight is split between the two days.
"""
from __future__ import annotations

import os
import sqlite3
import sys
import time
from contextlib import closing
from datetime import datetime, time as dtime
from pathlib import Path

# Windows shell windows that are not applications.
SHELL_CLASSES = frozenset({'progman', 'workerw', 'shell_traywnd', 'shell_secondarytraywnd'})
IGNORED_EXES = frozenset({'lockapp.exe'})
FLUSH_EVERY = 60.0     # Seconds between writes to the database.

_friendly_cache = {}   # exe path -> friendly name


def _file_description(path):
    """FileDescription from the exe's version resource, or ''."""
    import ctypes
    from ctypes import wintypes

    version = ctypes.WinDLL('version', use_last_error=True)
    version.GetFileVersionInfoSizeW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
    version.GetFileVersionInfoSizeW.restype = wintypes.DWORD
    version.GetFileVersionInfoW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
    version.GetFileVersionInfoW.restype = wintypes.BOOL
    version.VerQueryValueW.argtypes = [
        ctypes.c_void_p, wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(wintypes.UINT)]
    version.VerQueryValueW.restype = wintypes.BOOL

    size = version.GetFileVersionInfoSizeW(path, None)
    if not size:
        return ''
    data = ctypes.create_string_buffer(size)
    if not version.GetFileVersionInfoW(path, 0, size, data):
        return ''

    def query(sub_block):
        pointer = ctypes.c_void_p()
        length = wintypes.UINT(0)
        if not version.VerQueryValueW(data, sub_block, ctypes.byref(pointer), ctypes.byref(length)):
            return None, 0
        return pointer.value, length.value

    languages = []
    pointer, length = query('\\VarFileInfo\\Translation')
    if pointer:
        words = (wintypes.WORD * (length // 2)).from_address(pointer)
        languages = [(words[i], words[i + 1]) for i in range(0, len(words) - 1, 2)]
    languages += [(0x0409, 0x04B0), (0x0409, 0x04E4), (0x0000, 0x04B0)]
    for lang, codepage in languages:
        pointer, length = query('\\StringFileInfo\\%04x%04x\\FileDescription' % (lang, codepage))
        if pointer and length:
            text = ctypes.wstring_at(pointer).strip()
            if text:
                return text
    return ''


def friendly_name(path):
    """A human name for the program at `path`, cached per path."""
    if path in _friendly_cache:
        return _friendly_cache[path]
    name = ''
    try:
        name = _file_description(path)
    except Exception:
        name = ''
    if not name:
        base = os.path.basename(path)
        name = base[:-4] if base.lower().endswith('.exe') else base
    _friendly_cache[path] = name
    return name


def foreground_program():
    """(exe_name_lowercase, friendly_name) of the foreground program, or None.

    None when there is no foreground window, it is the desktop/taskbar/lock
    screen or this very process, on non-Windows systems, and on any failure.
    """
    if sys.platform != 'win32':
        return None
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.WinDLL('user32', use_last_error=True)
        kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        user32.GetForegroundWindow.restype = wintypes.HWND
        user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.QueryFullProcessImageNameW.argtypes = [
            wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None
        buffer = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, buffer, len(buffer))
        if buffer.value.lower() in SHELL_CLASSES:
            return None
        pid = wintypes.DWORD(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value or pid.value == os.getpid():
            return None

        path = ''
        handle = kernel32.OpenProcess(0x1000, False, pid.value)   # QUERY_LIMITED_INFORMATION
        if handle:
            try:
                text = ctypes.create_unicode_buffer(1024)
                length = wintypes.DWORD(len(text))
                if kernel32.QueryFullProcessImageNameW(handle, 0, text, ctypes.byref(length)):
                    path = text.value
            finally:
                kernel32.CloseHandle(handle)
        if not path:
            return None
        exe = os.path.basename(path).lower()
        if not exe or exe in IGNORED_EXES:
            return None
        return exe, friendly_name(path)
    except Exception:
        return None


def _day(at):
    return datetime.fromtimestamp(at).date().isoformat()


class AppTimeStore:
    """SQLite totals per (local day, program). A connection per call."""

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(str(self.path))) as db, db:
            db.execute(
                'CREATE TABLE IF NOT EXISTS app_time('
                'day TEXT, exe TEXT, name TEXT, seconds REAL, PRIMARY KEY(day, exe))')

    def add(self, exe, name, seconds, at):
        """Add seconds to the local day of `at` (epoch seconds)."""
        with closing(sqlite3.connect(str(self.path))) as db, db:
            db.execute(
                'INSERT INTO app_time(day, exe, name, seconds) VALUES (?, ?, ?, ?) '
                'ON CONFLICT(day, exe) DO UPDATE SET seconds = seconds + excluded.seconds, '
                'name = excluded.name',
                (_day(at), exe, name, float(seconds)))

    def day_totals(self, day):
        """[(exe, name, seconds)] for one 'YYYY-MM-DD' day, most time first."""
        return self.range_totals(day, day)

    def range_totals(self, start_day, end_day):
        """Same shape, summed over start_day..end_day inclusive."""
        with closing(sqlite3.connect(str(self.path))) as db:
            rows = db.execute(
                'SELECT exe, MAX(name), SUM(seconds) AS total FROM app_time '
                'WHERE day >= ? AND day <= ? GROUP BY exe ORDER BY total DESC, exe',
                (start_day, end_day)).fetchall()
        return [(exe, name, float(total)) for exe, name, total in rows]

    def clear(self):
        with closing(sqlite3.connect(str(self.path))) as db, db:
            db.execute('DELETE FROM app_time')

    def close(self):
        """Nothing is held open between calls; kept for a tidy shutdown path."""


class AppTimeTracker:
    """Turns periodic samples into seconds per program.

    The app calls tick() every `interval` seconds. Each tick credits the
    program in front NOW with the time since the previous tick (at most
    2*interval, so a sleep/hibernate gap never counts), unless the user has
    been idle for idle_after seconds. Seconds are batched in memory and written
    at most every FLUSH_EVERY seconds and on flush().
    """

    def __init__(self, store, sample=foreground_program, idle=None, clock=time.time,
                 interval=5.0, idle_after=120):
        self.store = store
        self.sample = sample
        self.idle = idle
        self.clock = clock
        self.interval = interval
        self.idle_after = idle_after
        self.current = None        # exe of the last sample.
        self._last = None          # Time of the previous tick.
        self._last_flush = None
        self._pending = {}         # (day, exe) -> [name, seconds, at]

    def _credit(self, exe, name, seconds, at):
        if seconds <= 0:
            return
        entry = self._pending.setdefault((_day(at), exe), [name, 0.0, at])
        entry[0] = name
        entry[1] += seconds

    def tick(self, now=None):
        try:
            self._tick(self.clock() if now is None else now)
        except Exception:
            pass

    def _tick(self, now):
        previous, self._last = self._last, now
        if self._last_flush is None:
            self._last_flush = now
        program = self.sample()
        self.current = program[0] if program else None
        elapsed = 0.0 if previous is None else min(now - previous, 2 * self.interval)
        away = self.idle is not None and self.idle() >= self.idle_after
        if program and elapsed > 0 and not away:
            exe, name = program
            start = now - elapsed
            midnight = datetime.combine(datetime.fromtimestamp(now).date(), dtime.min).timestamp()
            if start < midnight <= now:
                self._credit(exe, name, midnight - start, start)
                self._credit(exe, name, now - midnight, now)
            else:
                self._credit(exe, name, elapsed, now)
        if now - self._last_flush >= FLUSH_EVERY:
            self.flush(now)

    def flush(self, now=None):
        """Write the batched seconds; they stay queued if the write fails."""
        self._last_flush = self.clock() if now is None else now
        for key in list(self._pending):
            name, seconds, at = self._pending[key]
            try:
                self.store.add(key[1], name, seconds, at)
            except Exception:
                return
            del self._pending[key]


def format_duration(seconds, language='en'):
    """'3 h 12 min' / '45 min' / '<1 min' (zh: '3 小时 12 分' / '45 分钟' / '不到 1 分钟')."""
    minutes = int(max(0, seconds) // 60)
    hours, minutes = divmod(minutes, 60)
    zh = str(language or '').lower().startswith('zh')
    if not hours and not minutes:
        return '不到 1 分钟' if zh else '<1 min'
    if zh:
        if not hours:
            return '%d 分钟' % minutes
        return '%d 小时 %d 分' % (hours, minutes) if minutes else '%d 小时' % hours
    if not hours:
        return '%d min' % minutes
    return '%d h %d min' % (hours, minutes) if minutes else '%d h' % hours
