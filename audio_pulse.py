"""How loud the computer is playing right now, for the Aurora ring (2.4).

Only the default speakers' peak meter is read (a number from 0 to 1, the
same one the Windows volume mixer shows); no sound is recorded or stored.
It runs only while the Aurora skin is worn and stops otherwise.
"""
from __future__ import annotations

import math
import threading
import time

LEVEL = 0.0          # Smoothed loudness, 0 .. 1.
BEAT = 0.0           # A short pulse on each sudden rise (a beat), 0 .. 1, fading.
FAKE = False         # The test build plays a made-up rhythm instead.
_thread = None
_stop = threading.Event()


def _meter():
    import comtypes
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioMeterInformation
    comtypes.CoInitialize()
    device = AudioUtilities.GetSpeakers()
    device = getattr(device, '_dev', device)
    return device.Activate(IAudioMeterInformation._iid_, CLSCTX_ALL, None).QueryInterface(IAudioMeterInformation)


def _run():
    global LEVEL, BEAT
    meter, retry, slow = None, 0.0, 0.0
    while not _stop.is_set():
        now = time.monotonic()
        peak = 0.0
        if FAKE:
            phase = (now * 2.0) % 1.0                         # 120 beats a minute.
            peak = .35 + .45 * math.exp(-phase * 6) + .1 * math.sin(now * 7)
        else:
            try:
                if meter is None and now >= retry:
                    meter = _meter()
                peak = meter.GetPeakValue() if meter is not None else 0.0
            except Exception:
                meter, retry = None, now + 5
        peak = max(0.0, min(1.0, peak))
        LEVEL = peak if peak > LEVEL else LEVEL * .86 + peak * .14     # Quick to rise, slow to fall.
        slow = slow * .96 + peak * .04
        BEAT = 1.0 if peak > slow * 1.5 + .08 and peak > .25 else BEAT * .85
        _stop.wait(1 / 30)
    LEVEL = BEAT = 0.0


def running():
    return _thread is not None and _thread.is_alive()


def start():
    global _thread
    if running():
        return
    _stop.clear()
    _thread = threading.Thread(target=_run, daemon=True, name='aurora-audio')
    _thread.start()


def stop():
    global _thread
    _stop.set()
    _thread = None
