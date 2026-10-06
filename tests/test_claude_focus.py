import json
import tempfile
import unittest
from pathlib import Path

import claude_focus


class FakeProcess:
    tree = {}

    def __init__(self, pid):
        if pid not in self.tree:
            import psutil
            raise psutil.NoSuchProcess(pid)
        self.pid = pid

    def name(self):
        return self.tree[self.pid][0]

    def parent(self):
        parent = self.tree[self.pid][1]
        return FakeProcess(parent) if parent is not None else None

    def children(self):
        return [FakeProcess(pid) for pid, (_, parent) in self.tree.items() if parent == self.pid]


class FindWindowTests(unittest.TestCase):
    def find(self, tree, windows, start):
        FakeProcess.tree = tree
        return claude_focus.find_window(start, windows, FakeProcess)

    def test_desktop_app_ancestor(self):
        tree = {1: ('explorer.exe', None), 10: ('Claude.exe', 1), 20: ('Claude.exe', 10), 30: ('claude.exe', 20)}
        self.assertEqual(self.find(tree, {10: [111]}, 30), (111, 10))

    def test_terminal_and_classic_console(self):
        tree = {1: ('explorer.exe', None), 5: ('WindowsTerminal.exe', 1), 6: ('pwsh.exe', 5),
                7: ('claude.exe', 6), 8: ('OpenConsole.exe', 5)}
        self.assertEqual(self.find(tree, {5: [55]}, 7), (55, 5))
        tree = {1: ('explorer.exe', None), 6: ('cmd.exe', 1), 7: ('claude.exe', 6), 9: ('conhost.exe', 6)}
        self.assertEqual(self.find(tree, {9: [99]}, 7), (99, 9))

    def test_never_raises_explorer_or_guesses(self):
        tree = {1: ('explorer.exe', None), 7: ('claude.exe', 1)}
        self.assertEqual(self.find(tree, {1: [11]}, 7), (None, None))
        self.assertEqual(self.find(tree, {}, 404), (None, None))


class SessionPidTests(unittest.TestCase):
    def test_pid_comes_from_a_live_registry_entry(self):
        with tempfile.TemporaryDirectory() as home:
            folder = Path(home) / 'sessions'
            folder.mkdir()
            (folder / '1.json').write_text(json.dumps(dict(sessionId='abc', pid=4242, status='busy')),
                                           encoding='utf-8')
            from unittest.mock import patch
            with patch('claude_usage._process_alive', return_value=True):
                self.assertEqual(claude_focus.session_pid('abc', home), 4242)
                self.assertIsNone(claude_focus.session_pid('nope', home))
            with patch('claude_usage._process_alive', return_value=False):
                self.assertIsNone(claude_focus.session_pid('abc', home))


if __name__ == '__main__':
    unittest.main()
