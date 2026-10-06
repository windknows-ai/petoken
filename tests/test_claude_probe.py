"""Opt-in background refresh of Claude's limits."""
import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

import claude_probe
import claude_statusline

EVENT = json.dumps(dict(type='rate_limit_event', rate_limit_info=dict(
    status='allowed', unifiedWindows=dict(five_hour=dict(utilization=.42, resetsAt=2_000_000_000),
                                          seven_day=dict(utilization=.88, resetsAt=2_000_500_000)))))


class Panel:
    def __init__(self, minutes):
        self.prefs = dict(claude_probe_minutes=minutes)


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name) / 'claude-status'

    def test_parse_and_snapshot_reach_the_usage_card(self):
        windows = claude_probe.parse(['{"type":"system"}', EVENT, '{"type":"result"}'])
        self.assertEqual(windows, dict(five_hour=(42.0, 2_000_000_000.0), seven_day=(88.0, 2_000_500_000.0)))
        self.assertIsNone(claude_probe.parse(['{"type":"result"}']))
        claude_probe.write_snapshot(windows, self.folder, now=time.time())
        limits, _ = claude_statusline.account_limits(claude_statusline.read_snapshots(self.folder))
        self.assertEqual(limits['primary']['usedPercent'], 42.0)
        self.assertEqual(limits['secondary']['usedPercent'], 88.0)

    def test_command_is_quiet_and_cheap(self):
        argv = claude_probe.command('claude.exe')
        for flag in ('--no-session-persistence', '--strict-mcp-config', '--setting-sources', '--tools'):
            self.assertIn(flag, argv)
        self.assertEqual(argv[argv.index('--model') + 1], 'haiku')

    def test_tick_follows_the_interval_and_skips_fresh_sessions(self):
        calls = []

        def runner(argv, **kwargs):
            calls.append(argv)
            return SimpleNamespace(stdout=EVENT + '\n')

        off = claude_probe.ClaudeProbe(Panel(0), self.folder, cli='claude.exe', runner=runner)
        self.assertFalse(off.tick(now=1000))
        probe = claude_probe.ClaudeProbe(Panel(5), self.folder, cli='claude.exe', runner=runner)
        self.assertTrue(probe.tick(now=time.time()))
        for _ in range(50):
            if not probe.busy:
                break
            time.sleep(.05)
        self.assertEqual(len(calls), 1)
        self.assertTrue((self.folder / claude_probe.SNAPSHOT_NAME).exists())
        self.assertFalse(probe.tick(now=time.time() + 60))          # Within 5 minutes.
        # A real session wrote numbers just now: no need to ask.
        (self.folder / 'session.json').write_text('{}', encoding='utf-8')
        probe.last = time.time() - 400                               # The interval has passed...
        self.assertFalse(probe.tick(now=time.time()))                # ...but the numbers are fresh.
        self.assertEqual(len(calls), 1)


if __name__ == '__main__':
    unittest.main()
