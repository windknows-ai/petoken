import json
import os
import tempfile
import unittest
from pathlib import Path

from activity import ActivityState
from app_mode import AppModeState, DAILY_MODE, TOKEN_MODE
from usage import CodexActivityDetector


def lifecycle(kind, timestamp="2026-09-19T12:00:00Z"):
    return json.dumps({"type": "event_msg", "timestamp": timestamp,
                       "payload": {"type": kind}}) + "\n"


class AppModeTests(unittest.TestCase):
    def test_daily_to_token_and_token_to_daily_are_debounced(self):
        state = AppModeState()
        self.assertEqual(state.update(True, True, now=1), DAILY_MODE)
        self.assertEqual(state.update(True, True, now=1.5), TOKEN_MODE)
        self.assertEqual(state.update(False, True, now=2), TOKEN_MODE)
        self.assertEqual(state.update(False, True, now=4.1), DAILY_MODE)

    def test_explicit_running_session_is_active_without_typing(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rollout.jsonl"
            path.write_text(lifecycle("task_started"), encoding="utf-8")
            now = path.stat().st_mtime
            signal = CodexActivityDetector().detect(
                [{"id": "thread-1", "rollout_path": str(path)}], True, True, now)
        self.assertTrue(signal["active"])
        self.assertEqual(ActivityState().state(now=1, codex_working=signal["active"]), "working")

    def test_open_but_completed_codex_is_inactive(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rollout.jsonl"
            path.write_text(lifecycle("task_started") + lifecycle("task_complete"), encoding="utf-8")
            now = path.stat().st_mtime
            signal = CodexActivityDetector().detect(
                [{"id": "thread-1", "rollout_path": str(path)}], True, True, now)
        self.assertFalse(signal["active"])
        self.assertEqual(signal["reason"], "no_running_session")

    def test_task_complete_transitions_detector_to_inactive(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rollout.jsonl"
            path.write_text(lifecycle("task_started"), encoding="utf-8")
            detector = CodexActivityDetector()
            self.assertTrue(detector.detect(
                [{"id": "thread-1", "rollout_path": str(path)}], True, True,
                path.stat().st_mtime)["active"])
            with path.open("a", encoding="utf-8") as stream:
                stream.write(lifecycle("task_complete"))
            self.assertFalse(detector.detect(
                [{"id": "thread-1", "rollout_path": str(path)}], True, True,
                path.stat().st_mtime)["active"])

    def test_any_running_desktop_session_makes_global_signal_active(self):
        with tempfile.TemporaryDirectory() as directory:
            idle = Path(directory) / "idle.jsonl"
            running = Path(directory) / "running.jsonl"
            idle.write_text(lifecycle("task_started") + lifecycle("task_complete"), encoding="utf-8")
            running.write_text(lifecycle("task_started"), encoding="utf-8")
            now = max(idle.stat().st_mtime, running.stat().st_mtime)
            signal = CodexActivityDetector().detect([
                {"id": "idle", "rollout_path": str(idle)},
                {"id": "running", "rollout_path": str(running)},
            ], True, True, now)
        self.assertTrue(signal["active"])
        self.assertEqual(signal["thread"], "running")

    def test_stale_or_failed_detection_cannot_force_token_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rollout.jsonl"
            path.write_text(lifecycle("task_started"), encoding="utf-8")
            os.utime(path, (100, 100))
            signal = CodexActivityDetector().detect(
                [{"id": "thread-1", "rollout_path": str(path)}], True, True, now=500)
        self.assertFalse(signal["active"])
        state = AppModeState()
        state.update(True, reliable=False, now=1)
        self.assertEqual(state.update(True, reliable=False, now=2), DAILY_MODE)


if __name__ == "__main__":
    unittest.main()
