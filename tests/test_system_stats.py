"""Hardware readings for the game-mode bar."""
import threading
import time
import unittest

import system_stats
from system_stats import GB, StatsSampler, SystemStats, format_stat


def gpu_fake():
    return dict(gpu=37.0, gpu_temp=45.0, vram_used_gb=3.1, vram_total_gb=8.0, gpu_name='Fake GPU')


class StatsTests(unittest.TestCase):
    def test_cpu_percent_from_filetime_samples(self):
        times = iter([(100, 1000, 500), (150, 1600, 900), (150, 1600, 900)])
        stats = SystemStats(cpu_times=lambda: next(times), memory=lambda: None, gpu=lambda: None)
        self.assertIsNone(stats.sample()['cpu'])                 # No delta yet.
        # idle +50, kernel +600, user +400: busy = 1 - 50 / 1000.
        self.assertEqual(stats.sample()['cpu'], 95.0)
        self.assertIsNone(stats.sample()['cpu'])                 # Clock did not move.

    def test_cpu_source_failures_are_none(self):
        def broken():
            raise OSError('nope')
        stats = SystemStats(cpu_times=broken, memory=broken, gpu=broken)
        sample = stats.sample()
        self.assertEqual(set(sample), set(system_stats.KEYS))
        self.assertTrue(all(value is None for value in sample.values()))

    def test_ram_from_struct_values(self):
        self.assertEqual(system_stats.memory_reading(63, 16 * GB, 6 * GB), (63.0, 10.0, 16.0))
        sample = SystemStats(cpu_times=lambda: None, memory=lambda: (63.0, 10.0, 16.0), gpu=lambda: None).sample()
        self.assertEqual((sample['ram'], sample['ram_used_gb'], sample['ram_total_gb']), (63.0, 10.0, 16.0))

    def test_gpu_missing_gives_none_fields(self):
        missing = system_stats.NvmlGpu(loader=lambda: (_ for _ in ()).throw(OSError('no nvml')))
        stats = SystemStats(cpu_times=lambda: None, memory=lambda: None, gpu=missing.read)
        sample = stats.sample()
        for key in ('gpu', 'gpu_temp', 'vram_used_gb', 'vram_total_gb', 'gpu_name', 'fps'):
            self.assertIsNone(sample[key])
        missing.close()

    def test_gpu_init_is_not_retried_within_a_minute(self):
        calls, now = [], [0.0]

        def loader():
            calls.append(1)
            raise OSError('no nvml')
        gpu = system_stats.NvmlGpu(loader=loader, clock=lambda: now[0])
        self.assertIsNone(gpu.read())
        self.assertIsNone(gpu.read())
        self.assertEqual(len(calls), 1)
        now[0] = system_stats.GPU_RETRY_S + 1
        gpu.read()
        self.assertEqual(len(calls), 2)

    def test_gpu_fake_values(self):
        sample = SystemStats(cpu_times=lambda: None, memory=lambda: None, gpu=gpu_fake).sample()
        self.assertEqual((sample['gpu'], sample['gpu_temp']), (37.0, 45.0))
        self.assertEqual((sample['vram_used_gb'], sample['vram_total_gb']), (3.1, 8.0))
        self.assertEqual(sample['gpu_name'], 'Fake GPU')
        self.assertIsNone(sample['fps'])

    def test_sampler_only_samples_while_wanted(self):
        calls, hit = [], threading.Event()

        def memory():
            calls.append(1)
            hit.set()
            return 50.0, 8.0, 16.0
        stats = SystemStats(cpu_times=lambda: None, memory=memory, gpu=lambda: None)
        wanted = [False]
        sampler = StatsSampler(lambda: wanted[0], interval=0.01, stats=stats)
        sampler.start()
        time.sleep(0.08)
        self.assertEqual(calls, [])
        self.assertIsNone(sampler.latest['ram'])
        wanted[0] = True
        self.assertTrue(hit.wait(1))
        deadline = time.time() + 1
        while sampler.latest['ram'] is None and time.time() < deadline:
            time.sleep(0.005)
        self.assertEqual(sampler.latest['ram'], 50.0)
        wanted[0] = False
        time.sleep(0.05)
        count = len(calls)
        time.sleep(0.08)
        self.assertEqual(len(calls), count)
        sampler.stop()
        sampler.join(1)
        self.assertFalse(sampler.is_alive())

    def test_format_stat(self):
        sample = dict(vram_used_gb=3.14, vram_total_gb=8.0)
        for language in ('en', 'zh_CN'):
            self.assertEqual(format_stat('cpu', 62.6, language), '63%')
            self.assertEqual(format_stat('ram', 41.0, language), '41%')
            self.assertEqual(format_stat('gpu', 0.0, language), '0%')
            self.assertEqual(format_stat('gpu_temp', 45.0, language), '45°C')
            self.assertEqual(format_stat('vram', sample, language), '3.1/8.0 GB')
            self.assertEqual(format_stat('cpu', None, language), 'N/A')
            self.assertEqual(format_stat('vram', dict(vram_used_gb=None, vram_total_gb=8.0), language), 'N/A')
            self.assertEqual(format_stat('fps', None, language), 'N/A')
        self.assertEqual(format_stat('cpu', 5), '5%')
        self.assertEqual(format_stat('vram', None), 'N/A')
        for language in ('en', 'zh_CN'):
            self.assertEqual(set(system_stats.LABELS[language]),
                             {'cpu', 'ram', 'gpu', 'gpu_temp', 'vram', 'fps'})
        self.assertEqual(system_stats.LABELS['zh_CN']['ram'], '内存')

    def test_real_sample_smoke(self):
        stats = SystemStats()
        try:
            stats.sample()
            time.sleep(0.05)
            sample = stats.sample()
        finally:
            stats.close()
        self.assertIsInstance(sample, dict)
        self.assertEqual(set(sample), set(system_stats.KEYS))
        self.assertIsNone(sample['fps'])


if __name__ == '__main__':
    unittest.main()
