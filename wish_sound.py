"""Sounds of the wishing show (2.5): assets/v2_5/wish/sound/*.mp3 (tools/render_wish_sounds.py).

Played through Windows' own media control interface (winmm, no extra library). Its devices
belong to the thread that opened them, and opening eleven takes a third of a second, so one
sound thread owns them all: it opens every sound when the show starts (the show never waits)
and plays what it is told; several can ring at once. Elsewhere, or if Windows refuses, silent.
"""
from __future__ import annotations

import queue
import sys
import threading

import pet_assets

SOUND_DIR = pet_assets.ASSETS_DIR / 'v2_5' / 'wish' / 'sound'


class Sounds:
    def __init__(self, enabled=True, volume=700):
        self.enabled = enabled
        self.volume = volume
        self._jobs = queue.Queue()
        self._thread = None
        if sys.platform == 'win32' and SOUND_DIR.is_dir():
            self._thread = threading.Thread(target=self._run, name='wish-sound', daemon=True)
            self._thread.start()

    def _run(self):
        try:
            import ctypes
            winmm = ctypes.WinDLL('winmm')
            winmm.mciSendStringW.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_void_p)
        except (OSError, AttributeError):
            return

        def send(command):
            return winmm.mciSendStringW(command, None, 0, None)
        opened = {}
        for path in sorted(SOUND_DIR.glob('*.mp3')):
            alias = f'petoken_wish_{path.stem}'
            send(f'close {alias}')                          # Left over from an earlier show.
            if send(f'open "{path}" type mpegvideo alias {alias}') == 0:
                send(f'setaudio {alias} volume to {self.volume}')
                opened[path.stem] = alias
        while True:
            action, name = self._jobs.get()
            if action == 'close':
                for alias in opened.values():
                    send(f'close {alias}')
                return
            if action == 'stop':
                for alias in opened.values():
                    send(f'stop {alias}')
            elif action == 'play' and name in opened:
                send(f'play {opened[name]} from 0')

    def play(self, name):
        if self.enabled and self._thread is not None:
            self._jobs.put(('play', name))
            return True
        return False

    def set_enabled(self, enabled):
        self.enabled = enabled
        if not enabled and self._thread is not None:
            self._jobs.put(('stop', None))

    def close(self):
        if self._thread is not None:
            self._jobs.put(('close', None))
            self._thread = None
