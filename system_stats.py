"""Hardware readings for the game-mode bar (2.1).

Game mode can show a small bar above the pet with the numbers a gamer
watches: CPU %, RAM %, GPU %, GPU temperature and VRAM. Everything here uses
only ctypes and the standard library, so Petoken ships no extra packages:

    CPU   kernel32.GetSystemTimes, two samples apart (the first has no delta)
    RAM   kernel32.GlobalMemoryStatusEx
    GPU   NVIDIA only, through nvml.dll (it ships with the driver)

CPU temperature is left out on purpose (Windows needs admin rights for it)
and FPS is always None. Any reading that is unavailable is None and nothing
here raises: a PC without an NVIDIA card just shows N/A for the GPU fields.
The sources are injectable so the tests need no hardware.
"""
from __future__ import annotations

import ctypes
import sys
import threading
import time

GB = 1024 ** 3
GPU_RETRY_S = 60            # Do not retry a failed NVML init more than once a minute.
NVML_PATHS = ('nvml.dll', r'C:\Windows\System32\nvml.dll',
              r'C:\Program Files\NVIDIA Corporation\NVSMI\nvml.dll')
KEYS = ('cpu', 'ram', 'ram_used_gb', 'ram_total_gb', 'gpu', 'gpu_temp',
        'vram_used_gb', 'vram_total_gb', 'gpu_name', 'fps')

LABELS = {
    'en': dict(cpu='CPU', ram='RAM', gpu='GPU', gpu_temp='GPU temp', vram='VRAM', fps='FPS'),
    'zh_CN': dict(cpu='CPU', ram='内存', gpu='GPU', gpu_temp='GPU 温度', vram='显存', fps='FPS'),
}


# ---- CPU ---------------------------------------------------------------

class _FileTime(ctypes.Structure):
    _fields_ = [('low', ctypes.c_uint32), ('high', ctypes.c_uint32)]

    def value(self):
        return (self.high << 32) | self.low


def read_cpu_times():
    """(idle, kernel, user) in 100 ns ticks, or None. Kernel includes idle."""
    try:
        idle, kernel, user = _FileTime(), _FileTime(), _FileTime()
        if not ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
            return None
        return idle.value(), kernel.value(), user.value()
    except Exception:
        return None


def cpu_percent(before, after):
    """Busy percent between two (idle, kernel, user) samples, or None."""
    try:
        d_idle, d_kernel, d_user = (after[i] - before[i] for i in range(3))
        total = d_kernel + d_user
        if total <= 0:
            return None
        return round(min(max((1 - d_idle / total) * 100, 0.0), 100.0), 1)
    except Exception:
        return None


# ---- RAM ---------------------------------------------------------------

class _MemoryStatus(ctypes.Structure):
    _fields_ = [('dwLength', ctypes.c_uint32), ('dwMemoryLoad', ctypes.c_uint32),
                ('ullTotalPhys', ctypes.c_uint64), ('ullAvailPhys', ctypes.c_uint64),
                ('ullTotalPageFile', ctypes.c_uint64), ('ullAvailPageFile', ctypes.c_uint64),
                ('ullTotalVirtual', ctypes.c_uint64), ('ullAvailVirtual', ctypes.c_uint64),
                ('ullAvailExtendedVirtual', ctypes.c_uint64)]


def read_memory():
    """(percent, used_gb, total_gb) of physical memory, or None."""
    try:
        status = _MemoryStatus()
        status.dwLength = ctypes.sizeof(_MemoryStatus)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return None
        return memory_reading(status.dwMemoryLoad, status.ullTotalPhys, status.ullAvailPhys)
    except Exception:
        return None


def memory_reading(load, total, available):
    return float(load), round((total - available) / GB, 2), round(total / GB, 2)


# ---- NVIDIA GPU (NVML) -------------------------------------------------

class _Utilization(ctypes.Structure):
    _fields_ = [('gpu', ctypes.c_uint), ('memory', ctypes.c_uint)]


class _MemoryInfo(ctypes.Structure):
    _fields_ = [('total', ctypes.c_ulonglong), ('free', ctypes.c_ulonglong), ('used', ctypes.c_ulonglong)]


class NvmlGpu:
    """GPU 0 through nvml.dll. read() returns a dict, or None when unavailable."""

    def __init__(self, loader=None, clock=time.monotonic):
        self._loader = loader or self._load
        self._clock = clock
        self._lib = None
        self._handle = None
        self._name = None
        self._failed_at = None

    @staticmethod
    def _load():
        if sys.platform != 'win32':
            raise OSError('NVML is only read on Windows')
        for path in NVML_PATHS:
            try:
                return ctypes.WinDLL(path)
            except OSError:
                continue
        raise OSError('nvml.dll not found')

    def _start(self):
        if self._lib is not None:
            return True
        if self._failed_at is not None and self._clock() - self._failed_at < GPU_RETRY_S:
            return False
        lib = None
        try:
            lib = self._loader()
            if lib.nvmlInit_v2() != 0:
                raise OSError('nvmlInit failed')
            handle = ctypes.c_void_p()
            if lib.nvmlDeviceGetHandleByIndex_v2(0, ctypes.byref(handle)) != 0:
                lib.nvmlShutdown()
                raise OSError('no GPU 0')
            self._lib, self._handle, self._failed_at = lib, handle, None
            self._name = self._read_name()
            return True
        except Exception:
            self._failed_at = self._clock()
            return False

    def _read_name(self):
        try:
            buffer = ctypes.create_string_buffer(96)
            if self._lib.nvmlDeviceGetName(self._handle, buffer, 96) == 0:
                return buffer.value.decode('utf-8', 'replace') or None
        except Exception:
            pass
        return None

    def read(self):
        if not self._start():
            return None
        out = dict(gpu=None, gpu_temp=None, vram_used_gb=None, vram_total_gb=None, gpu_name=self._name)
        try:
            usage = _Utilization()
            if self._lib.nvmlDeviceGetUtilizationRates(self._handle, ctypes.byref(usage)) == 0:
                out['gpu'] = float(usage.gpu)
            temp = ctypes.c_uint()
            if self._lib.nvmlDeviceGetTemperature(self._handle, 0, ctypes.byref(temp)) == 0:
                out['gpu_temp'] = float(temp.value)
            info = _MemoryInfo()
            if self._lib.nvmlDeviceGetMemoryInfo(self._handle, ctypes.byref(info)) == 0:
                out['vram_used_gb'] = round(info.used / GB, 2)
                out['vram_total_gb'] = round(info.total / GB, 2)
        except Exception:
            self.close()
            self._failed_at = self._clock()
            return None
        return out

    def close(self):
        lib, self._lib, self._handle = self._lib, None, None
        if lib is not None:
            try:
                lib.nvmlShutdown()
            except Exception:
                pass


# ---- sampling ----------------------------------------------------------

class SystemStats:
    """One reading of everything. sources: cpu_times() -> (idle, kernel, user)
    or None, memory() -> (percent, used_gb, total_gb) or None, gpu() -> dict
    with the gpu fields or None."""

    def __init__(self, cpu_times=None, memory=None, gpu=None):
        self._nvml = None
        if gpu is None:
            self._nvml = NvmlGpu()
            gpu = self._nvml.read
        self._cpu_times = cpu_times or read_cpu_times
        self._memory = memory or read_memory
        self._gpu = gpu
        self._previous = None

    def sample(self):
        out = dict.fromkeys(KEYS)
        try:
            now = self._cpu_times()
            if now is not None and self._previous is not None:
                out['cpu'] = cpu_percent(self._previous, now)
            if now is not None:
                self._previous = now
        except Exception:
            pass
        try:
            reading = self._memory()
            if reading:
                out['ram'], out['ram_used_gb'], out['ram_total_gb'] = reading
        except Exception:
            pass
        try:
            reading = self._gpu()
            if reading:
                for key in ('gpu', 'gpu_temp', 'vram_used_gb', 'vram_total_gb', 'gpu_name'):
                    out[key] = reading.get(key)
        except Exception:
            pass
        return out

    def close(self):
        if self._nvml is not None:
            self._nvml.close()


class StatsSampler(threading.Thread):
    """Samples every `interval` seconds, but only while wanted() is True, so a
    hidden bar costs nothing. `.latest` is replaced whole, never mutated."""

    def __init__(self, wanted, interval=2.0, stats=None):
        super().__init__(name='petoken-system-stats', daemon=True)
        self.wanted = wanted
        self.interval = interval
        self.latest = dict.fromkeys(KEYS)
        self._stats = stats or SystemStats()
        self._stop_event = threading.Event()

    def run(self):
        try:
            while not self._stop_event.is_set():
                try:
                    if self.wanted():
                        self.latest = self._stats.sample()
                except Exception:
                    pass
                self._stop_event.wait(self.interval)
        finally:
            self._stats.close()

    def stop(self):
        self._stop_event.set()


# ---- display -----------------------------------------------------------

def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def format_stat(key, value, language='en'):
    """Short text for the bar. For 'vram' pass the whole sample dict.

    The text is the same in every language; only LABELS differ.
    """
    try:
        if key == 'vram':
            used, total = value.get('vram_used_gb'), value.get('vram_total_gb')
            if _number(used) and _number(total):
                return f'{used:.1f}/{total:.1f} GB'
            return 'N/A'
        if not _number(value):
            return 'N/A'
        if key == 'gpu_temp':
            return f'{value:.0f}\u00b0C'
        if key in ('cpu', 'ram', 'gpu'):
            return f'{value:.0f}%'
        if key == 'fps':
            return f'{value:.0f}'
    except Exception:
        pass
    return 'N/A'
