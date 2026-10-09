"""Per-program screen time: the store, the tracker's accounting and the formatter."""
import shutil
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import app_time
from app_time import AppTimeStore, AppTimeTracker, format_duration, foreground_program

CHROME = ('chrome.exe', 'Google Chrome')
CODE = ('code.exe', 'Visual Studio Code')


def epoch(*args):
    return datetime(*args).timestamp()


class TempDirCase(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.store = AppTimeStore(self.dir / 'sub' / 'app_time.db')


class StoreTests(TempDirCase):
    def test_add_and_day_totals(self):
        self.store.add('chrome.exe', 'Google Chrome', 60, epoch(2026, 10, 8, 9))
        self.store.add('chrome.exe', 'Google Chrome', 30, epoch(2026, 10, 8, 23, 59))
        self.store.add('code.exe', 'Visual Studio Code', 200, epoch(2026, 10, 8, 10))
        self.assertEqual(self.store.day_totals('2026-10-08'),
                         [('code.exe', 'Visual Studio Code', 200.0), ('chrome.exe', 'Google Chrome', 90.0)])
        self.assertEqual(self.store.day_totals('2026-10-09'), [])

    def test_range_totals_across_two_days(self):
        self.store.add('chrome.exe', 'Google Chrome', 100, epoch(2026, 10, 8, 12))
        self.store.add('chrome.exe', 'Google Chrome', 50, epoch(2026, 10, 9, 0, 0, 1))
        self.store.add('code.exe', 'Visual Studio Code', 120, epoch(2026, 10, 9, 8))
        self.store.add('old.exe', 'Old', 999, epoch(2026, 10, 1, 8))
        self.assertEqual(self.store.range_totals('2026-10-08', '2026-10-09'),
                         [('chrome.exe', 'Google Chrome', 150.0), ('code.exe', 'Visual Studio Code', 120.0)])
        self.assertEqual(self.store.range_totals('2026-10-09', '2026-10-09'),
                         [('code.exe', 'Visual Studio Code', 120.0), ('chrome.exe', 'Google Chrome', 50.0)])

    def test_clear_and_close(self):
        self.store.add('chrome.exe', 'Google Chrome', 10, epoch(2026, 10, 8, 12))
        self.store.clear()
        self.assertEqual(self.store.range_totals('2000-01-01', '2999-12-31'), [])
        self.store.close()
        self.store.add('chrome.exe', 'Google Chrome', 5, epoch(2026, 10, 8, 12))
        self.assertEqual(self.store.day_totals('2026-10-08'), [('chrome.exe', 'Google Chrome', 5.0)])
        (self.dir / 'sub' / 'app_time.db').unlink()    # Nothing holds the file open.


class Fakes:
    def __init__(self, program=CHROME, idle=0):
        self.program = program
        self.idle_s = idle

    def sample(self):
        return self.program

    def idle(self):
        return self.idle_s


class TrackerTests(TempDirCase):
    def make(self, fakes=None, **kwargs):
        self.fakes = fakes or Fakes()
        return AppTimeTracker(self.store, sample=self.fakes.sample, idle=self.fakes.idle, **kwargs)

    def total(self, day='2026-10-08'):
        return {exe: seconds for exe, _, seconds in self.store.day_totals(day)}

    def test_counts_elapsed_time_to_the_sampled_program(self):
        tracker = self.make()
        t = epoch(2026, 10, 8, 12)
        tracker.tick(t)                       # First tick only starts the clock.
        tracker.tick(t + 5)
        self.fakes.program = CODE
        tracker.tick(t + 10)
        tracker.flush()
        self.assertEqual(self.total(), {'chrome.exe': 5.0, 'code.exe': 5.0})
        self.assertEqual(tracker.current, 'code.exe')

    def test_idle_time_is_not_counted(self):
        tracker = self.make()
        t = epoch(2026, 10, 8, 12)
        tracker.tick(t)
        self.fakes.idle_s = 120
        tracker.tick(t + 5)
        self.fakes.idle_s = 3
        tracker.tick(t + 10)
        tracker.flush()
        self.assertEqual(self.total(), {'chrome.exe': 5.0})

    def test_no_program_counts_nothing(self):
        tracker = self.make(Fakes(program=None))
        t = epoch(2026, 10, 8, 12)
        tracker.tick(t)
        tracker.tick(t + 5)
        tracker.flush()
        self.assertEqual(self.total(), {})
        self.assertIsNone(tracker.current)

    def test_long_gap_is_capped(self):
        tracker = self.make(interval=5.0)
        t = epoch(2026, 10, 8, 12)
        tracker.tick(t)
        tracker.tick(t + 3600)                # Slept for an hour.
        tracker.flush()
        self.assertEqual(self.total(), {'chrome.exe': 10.0})

    def test_interval_is_split_at_midnight(self):
        tracker = self.make()
        midnight = epoch(2026, 10, 9)
        tracker.tick(midnight - 3)
        tracker.tick(midnight + 2)
        tracker.flush()
        self.assertEqual(self.total('2026-10-08'), {'chrome.exe': 3.0})
        self.assertEqual(self.total('2026-10-09'), {'chrome.exe': 2.0})

    def test_writes_are_batched_until_flush(self):
        tracker = self.make()
        t = epoch(2026, 10, 8, 12)
        for i in range(12):
            tracker.tick(t + 5 * i)
        self.assertEqual(self.total(), {})    # Under 60 s: still in memory.
        tracker.tick(t + 60)                # Reaches the flush interval.
        self.assertEqual(self.total(), {'chrome.exe': 60.0})
        tracker.tick(t + 65)
        self.assertEqual(self.total(), {'chrome.exe': 60.0})
        tracker.flush()
        self.assertEqual(self.total(), {'chrome.exe': 65.0})

    def test_failures_never_raise_and_keep_the_data(self):
        tracker = self.make()
        t = epoch(2026, 10, 8, 12)
        tracker.tick(t)
        tracker.tick(t + 5)
        real_add = self.store.add
        self.store.add = lambda *a: (_ for _ in ()).throw(OSError('disk'))
        tracker.flush()
        self.store.add = real_add
        self.fakes.sample = None              # A broken sampler must not raise either.
        tracker.sample = lambda: 1 / 0
        tracker.tick(t + 10)
        tracker.flush()
        self.assertEqual(self.total(), {'chrome.exe': 5.0})


class ForegroundTests(unittest.TestCase):
    def test_returns_none_or_a_pair_of_strings(self):
        result = foreground_program()
        if result is not None:
            self.assertEqual(len(result), 2)
            self.assertTrue(all(isinstance(part, str) and part for part in result))
            self.assertEqual(result[0], result[0].lower())

    def test_friendly_name_falls_back_to_the_file_name(self):
        self.assertEqual(app_time.friendly_name(r'C:\nowhere\Missing Tool.exe'), 'Missing Tool')


class FormatTests(unittest.TestCase):
    def test_english(self):
        self.assertEqual(format_duration(3 * 3600 + 12 * 60 + 40, 'en'), '3 h 12 min')
        self.assertEqual(format_duration(45 * 60, 'en'), '45 min')
        self.assertEqual(format_duration(59, 'en'), '<1 min')
        self.assertEqual(format_duration(0, 'en'), '<1 min')
        self.assertEqual(format_duration(2 * 3600, 'en'), '2 h')

    def test_chinese(self):
        self.assertEqual(format_duration(3 * 3600 + 12 * 60, 'zh_CN'), '3 小时 12 分')
        self.assertEqual(format_duration(45 * 60, 'zh_CN'), '45 分钟')
        self.assertEqual(format_duration(10, 'zh_CN'), '不到 1 分钟')
        self.assertEqual(format_duration(2 * 3600, 'zh_CN'), '2 小时')


if __name__ == '__main__':
    unittest.main()
