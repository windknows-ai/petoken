"""Game detection for Petoken's game mode (2.1).

Game mode keeps the pet quiet while the user plays: it turns on only when
the FOREGROUND window is fullscreen (exclusive, or borderless and covering
its whole monitor) AND the program is a game. Fullscreen alone is not
enough, because a fullscreen video, browser, IDE or the desktop must never
switch it on. "Is a game" is a conservative guess from the exe path:

  - inside a launcher's game library (Steam, Epic, Riot, GOG, ...),
  - a well-known game exe name, or
  - on the user's own list of exe names.

Known non-games (browsers, players, editors, the launchers themselves) are
never games, and the user's exclusion list beats everything. GameDetector
adds hysteresis so a short alt-tab does not drop out of game mode and a
flicker of fullscreen does not start it.

The Windows calls use ctypes only; everywhere else, and on any failure,
foreground_info() and d3d_fullscreen() just report "nothing".
"""
from __future__ import annotations

import os
import sys

# Windows shell windows that cover the whole screen but are not applications.
SHELL_CLASSES = frozenset({'progman', 'workerw', 'shell_traywnd', 'shell_secondarytraywnd'})
FULLSCREEN_TOLERANCE = 1           # Pixels.
QUNS_RUNNING_D3D_FULL_SCREEN = 3

# Folders that only games live in (compared lowercase, with backslashes).
LIBRARY_MARKERS = (
    '\\steamapps\\common\\', '\\epic games\\', '\\riot games\\', '\\gog galaxy\\games\\',
    '\\ubisoft game launcher\\games\\', '\\ea games\\', '\\origin games\\', '\\xboxgames\\',
    '\\world of warcraft\\', '\\overwatch\\', '\\diablo iv\\', '\\hearthstone\\',
    '\\genshin impact', '\\star rail', '\\zenlesszonezero', '\\hoyoplay\\games\\',
)

KNOWN_GAMES = frozenset({
    'yuanshen.exe', 'genshinimpact.exe', 'starrail.exe', 'zenlesszonezero.exe', 'bh3.exe',
    'league of legends.exe', 'valorant-win64-shipping.exe', 'cs2.exe', 'csgo.exe', 'dota2.exe',
    'r5apex.exe', 'fortniteclient-win64-shipping.exe', 'minecraft.windows.exe', 'eldenring.exe',
    'gta5.exe', 'rdr2.exe', 'cyberpunk2077.exe', 'overwatch.exe', 'wow.exe', 'hearthstone.exe',
    'tslgame.exe', 'narakabladepoint.exe', 'rocketleague.exe', 'destiny2.exe', 'witcher3.exe',
    'bg3.exe', 'bg3_dx11.exe', 'hollow_knight.exe', 'stardew valley.exe', 'terraria.exe',
    'rainbowsix.exe', 'rainbowsix_vulkan.exe', 'sekiro.exe', 'darksoulsiii.exe', 'monsterhunterworld.exe',
    'helldivers2.exe', 'palworld-win64-shipping.exe', 'deadlock.exe', 'apex_legends.exe',
    'diablo iv.exe', 'sc2_x64.exe', 'fifa23.exe', 'eurotrucks2.exe', 'factorio.exe',
})

# Never games, even fullscreen. javaw.exe runs Minecraft but also every Java
# tool, so it is not a game by itself.
NOT_GAMES = frozenset({
    'chrome.exe', 'msedge.exe', 'firefox.exe', 'brave.exe', 'opera.exe', 'vivaldi.exe', 'iexplore.exe',
    'vlc.exe', 'mpv.exe', 'potplayermini64.exe', 'potplayermini.exe', 'wmplayer.exe', 'mpc-hc64.exe',
    'mpc-hc.exe', 'spotify.exe', 'netflix.exe', 'applicationframehost.exe', 'video.ui.exe',
    'winword.exe', 'excel.exe', 'powerpnt.exe', 'outlook.exe', 'onenote.exe', 'acrobat.exe',
    'code.exe', 'devenv.exe', 'pycharm64.exe', 'idea64.exe', 'webstorm64.exe', 'clion64.exe',
    'studio64.exe', 'notepad.exe', 'notepad++.exe', 'windowsterminal.exe', 'cmd.exe',
    'powershell.exe', 'pwsh.exe', 'python.exe', 'pythonw.exe', 'javaw.exe', 'java.exe',
    'explorer.exe', 'searchhost.exe', 'startmenuexperiencehost.exe', 'obs64.exe', 'obs32.exe',
    'discord.exe', 'slack.exe', 'teams.exe', 'zoom.exe', 'wechat.exe', 'qq.exe',
    'steam.exe', 'steamwebhelper.exe', 'epicgameslauncher.exe', 'epicwebhelper.exe',
    'riotclientservices.exe', 'riotclientux.exe', 'galaxyclient.exe', 'battle.net.exe',
    'origin.exe', 'eadesktop.exe', 'upc.exe', 'hoyoplay.exe',
    'claude.exe', 'codex.exe', 'petoken.exe',
})


def _norm(path):
    return str(path or '').replace('/', '\\').lower()


def _file_name(path):
    return _norm(path).rsplit('\\', 1)[-1]


def is_game(exe_path, extra=(), excluded=()):
    """True when the program at exe_path looks like a game."""
    name = _file_name(exe_path)
    if not name:
        return False
    if name in {_file_name(item) for item in excluded or ()}:
        return False
    if name in {_file_name(item) for item in extra or ()}:
        return True
    if name in NOT_GAMES:
        return False
    path = _norm(exe_path)
    if any(marker in path for marker in LIBRARY_MARKERS):
        return True
    return name in KNOWN_GAMES


def _covers(rect, monitor):
    tol = FULLSCREEN_TOLERANCE
    return (rect[0] <= monitor[0] + tol and rect[1] <= monitor[1] + tol
            and rect[2] >= monitor[2] - tol and rect[3] >= monitor[3] - tol)


def foreground_info():
    """The foreground window as a dict, or None (not Windows, or any failure).

    {pid, exe (full path), name (lowercase file name), window_class,
    rect, monitor (both (left, top, right, bottom)), fullscreen}
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
        user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
        user32.MonitorFromWindow.restype = wintypes.HANDLE
        user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.QueryFullProcessImageNameW.argtypes = [
            wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

        class MonitorInfo(ctypes.Structure):
            _fields_ = [('cbSize', wintypes.DWORD), ('rcMonitor', wintypes.RECT),
                        ('rcWork', wintypes.RECT), ('dwFlags', wintypes.DWORD)]

        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None
        pid = wintypes.DWORD(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value or pid.value == os.getpid():
            return None
        buffer = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, buffer, len(buffer))
        window_class = buffer.value

        exe = ''
        handle = kernel32.OpenProcess(0x1000, False, pid.value)   # QUERY_LIMITED_INFORMATION
        if handle:
            try:
                path = ctypes.create_unicode_buffer(1024)
                size = wintypes.DWORD(len(path))
                if kernel32.QueryFullProcessImageNameW(handle, 0, path, ctypes.byref(size)):
                    exe = path.value
            finally:
                kernel32.CloseHandle(handle)

        window = wintypes.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(window)):
            return None
        rect = (window.left, window.top, window.right, window.bottom)
        monitor = rect
        monitor_handle = user32.MonitorFromWindow(hwnd, 2)        # MONITOR_DEFAULTTONEAREST
        if monitor_handle:
            info = MonitorInfo()
            info.cbSize = ctypes.sizeof(MonitorInfo)
            if user32.GetMonitorInfoW(monitor_handle, ctypes.byref(info)):
                box = info.rcMonitor
                monitor = (box.left, box.top, box.right, box.bottom)
        fullscreen = rect[2] > rect[0] and rect[3] > rect[1] and _covers(rect, monitor)
        if window_class.lower() in SHELL_CLASSES:
            fullscreen = False
        return dict(pid=int(pid.value), exe=exe, name=_file_name(exe), window_class=window_class,
                    rect=rect, monitor=monitor, fullscreen=bool(fullscreen))
    except Exception:
        return None


def d3d_fullscreen():
    """True while Windows says a Direct3D exclusive-fullscreen app is running."""
    if sys.platform != 'win32':
        return False
    try:
        import ctypes

        state = ctypes.c_int(0)
        result = ctypes.windll.shell32.SHQueryUserNotificationState(ctypes.byref(state))
        return result == 0 and state.value == QUNS_RUNNING_D3D_FULL_SCREEN
    except Exception:
        return False


class GameDetector:
    """Hysteresis around "a game is in the foreground, fullscreen".

    Game mode starts after enter_s seconds of game frames in a row and ends
    after exit_s seconds without one, so a quick alt-tab keeps it on.
    """

    def __init__(self, scan=foreground_info, d3d=d3d_fullscreen, enter_s=4.0, exit_s=15.0):
        self.scan = scan
        self.d3d = d3d
        self.enter_s = enter_s
        self.exit_s = exit_s
        self.playing = False
        self.game = None           # Lowercase exe name of the current or last game.
        self._since = None         # When the current run of game frames began.
        self._last = None          # When the last game frame was seen.

    def _frame(self, extra, excluded):
        try:
            info = self.scan()
            if not info:
                return None
            if not (info.get('fullscreen') or self.d3d()):
                return None
            exe = info.get('exe') or ''
            if not is_game(exe, extra, excluded):
                return None
            return _file_name(exe)
        except Exception:
            return None

    def poll(self, now, extra=(), excluded=()):
        """Feed one sample taken at time `now` (seconds); returns .playing."""
        name = self._frame(extra, excluded)
        if name:
            if self._since is None:
                self._since = now
            self._last = now
            self.game = name
            if not self.playing and now - self._since >= self.enter_s:
                self.playing = True
        else:
            self._since = None
            if self.playing and now - (self._last if self._last is not None else now) >= self.exit_s:
                self.playing = False
        return self.playing
