import json
import os
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import codex_focus
from tests.test_codex_recap import RecapFixture


class FocusTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)
        self.fixture = RecapFixture(self.home)
        self.fixture.add()
        self.addCleanup(patch.stopall)
        patch('codex_focus.sys.platform', 'win32').start()
        self.processes = patch('codex_focus._processes', return_value=[]).start()
        self.windows = patch('codex_focus._windows', return_value=[]).start()
        self.foreground = patch('codex_focus._foreground', return_value=True).start()
        self.console = patch('codex_focus._console_window', return_value=0).start()
        patch('codex_focus._argv', side_effect=lambda line: json.loads(line or '[]')).start()

    def cli(self, arguments=None, source='cli'):
        self.fixture.add('cli-task', source)
        self.processes.return_value = [dict(pid=10, parent_pid=20, name='codex.exe',
            path='C:/tools/codex.exe', command_line=json.dumps(
                ['codex.exe', *(arguments if arguments is not None else ['resume', 'cli-task'])]))]

    def test_desktop_focus_is_app_level_not_thread_exact(self):
        self.processes.return_value = [dict(pid=10, name='ChatGPT.exe',
            path='C:/Program Files/WindowsApps/OpenAI.Codex_1/app/ChatGPT.exe')]
        self.windows.return_value = [dict(hwnd=123, pid=10)]
        self.assertEqual(codex_focus.focus(self.home, 'task'), 'app')
        self.foreground.assert_called_once_with(dict(hwnd=123, pid=10))
        self.console.assert_not_called()

    def test_wrong_chatgpt_app_and_headless_daemon_are_not_focused(self):
        self.processes.return_value = [dict(pid=10, name='ChatGPT.exe', path='C:/Other/ChatGPT.exe'),
            dict(pid=20, name='codex.exe', path='C:/tools/app-server-daemon/codex.exe')]
        self.windows.return_value = [dict(hwnd=123, pid=10), dict(hwnd=456, pid=20)]
        self.assertIsNone(codex_focus.focus(self.home, 'task'))
        self.foreground.assert_not_called()

    def test_no_window_does_not_launch_an_app(self):
        with patch('codex_focus.subprocess.Popen') as launch:
            self.assertIsNone(codex_focus.focus(self.home, 'task'))
        launch.assert_not_called()

    def test_explicit_cli_resume_and_visible_console_is_exact(self):
        self.cli()
        self.console.return_value = 123
        self.windows.return_value = [dict(hwnd=123, pid=99)]
        self.assertEqual(codex_focus.focus(self.home, 'cli-task'), 'exact')
        self.console.assert_called_once_with(10)

    def test_exec_resume_is_also_correlated(self):
        self.cli(['exec', 'resume', 'cli-task'], source='exec')
        self.console.return_value = 123
        self.windows.return_value = [dict(hwnd=123, pid=99)]
        self.assertEqual(codex_focus.focus(self.home, 'cli-task'), 'exact')

    def test_hidden_pseudoconsole_only_focuses_verified_terminal_app(self):
        self.cli()
        self.processes.return_value += [dict(pid=20, parent_pid=30, name='pwsh.exe'),
                                       dict(pid=30, parent_pid=0, name='WindowsTerminal.exe')]
        self.console.return_value = 999  # Hidden, so not returned by EnumWindows.
        self.windows.return_value = [dict(hwnd=123, pid=30)]
        self.assertEqual(codex_focus.focus(self.home, 'cli-task'), 'app')

    def test_failed_console_query_can_use_terminal_ancestor(self):
        self.cli()
        self.processes.return_value += [dict(pid=20, parent_pid=0, name='WindowsTerminal.exe')]
        self.console.side_effect = OSError('access denied')
        self.windows.return_value = [dict(hwnd=123, pid=20)]
        self.assertEqual(codex_focus.focus(self.home, 'cli-task'), 'app')

    def test_uuid_in_prompt_is_not_process_correlation(self):
        self.cli(['Discuss cli-task'])
        self.assertIsNone(codex_focus.focus(self.home, 'cli-task'))
        self.console.assert_not_called()

    def test_different_resume_id_is_not_correlated(self):
        self.cli(['resume', 'other-task', 'cli-task'])
        self.assertIsNone(codex_focus.focus(self.home, 'cli-task'))

    def test_new_cli_and_wrong_program_have_no_proven_window(self):
        self.cli()
        self.processes.return_value[0]['name'] = 'powershell.exe'
        self.assertIsNone(codex_focus.focus(self.home, 'cli-task'))

    def test_multiple_processes_or_terminal_windows_fail_closed(self):
        self.cli()
        other = dict(self.processes.return_value[0], pid=11)
        self.processes.return_value.append(other)
        self.assertIsNone(codex_focus.focus(self.home, 'cli-task'))
        self.processes.return_value.pop()
        self.processes.return_value.append(dict(pid=20, parent_pid=0, name='WindowsTerminal.exe'))
        self.windows.return_value = [dict(hwnd=123, pid=20), dict(hwnd=124, pid=20)]
        self.assertIsNone(codex_focus.focus(self.home, 'cli-task'))

    def test_parent_cycle_terminates(self):
        self.cli()
        self.processes.return_value.append(dict(pid=20, parent_pid=10, name='pwsh.exe'))
        self.assertIsNone(codex_focus.focus(self.home, 'cli-task'))

    def test_foreground_rejection_is_not_success(self):
        self.cli()
        self.console.return_value = 123
        self.windows.return_value = [dict(hwnd=123, pid=99)]
        self.foreground.return_value = False
        self.assertIsNone(codex_focus.focus(self.home, 'cli-task'))

    def test_invalid_thread_unsupported_source_and_platform(self):
        self.assertIsNone(codex_focus.focus(self.home, 'absent'))
        self.fixture.add('vscode-task', 'vscode')
        self.assertIsNone(codex_focus.focus(self.home, 'vscode-task'))
        with patch('codex_focus.sys.platform', 'linux'):
            self.assertIsNone(codex_focus.focus(self.home, 'task'))

    def test_snapshot_timeout_unknown_shape_and_access_error(self):
        for error in (subprocess.TimeoutExpired('synthetic', 4), ValueError(), PermissionError()):
            self.processes.side_effect = error
            self.assertIsNone(codex_focus.focus(self.home, 'task'))


class NativeHelperTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == 'win32' and (shutil.which('powershell.exe') or shutil.which('pwsh.exe')),
                         'Windows PowerShell helper')
    def test_console_helper_executes_only_against_this_synthetic_test_process(self):
        handle = codex_focus._console_window(os.getpid())
        self.assertIsInstance(handle, int)
        self.assertGreaterEqual(handle, 0)

    @unittest.skipUnless(sys.platform == 'win32', 'Windows argument parser')
    def test_command_line_parser_preserves_literal_arguments(self):
        arguments = ['C:/with space/codex.exe', 'resume', 'thread-id', '"quote" 日本語 ; $x']
        self.assertEqual(codex_focus._argv(subprocess.list2cmdline(arguments)), arguments)

    def test_process_reader_uses_static_script_and_rejects_unknown_schema(self):
        with patch('codex_focus._powershell', return_value='[]') as run:
            self.assertEqual(codex_focus._processes(), [])
            self.assertIn("$_.Name -ieq 'codex.exe'", run.call_args.args[0])
        with patch('codex_focus._powershell', return_value='{}'):
            with self.assertRaises(ValueError):
                codex_focus._processes()

    def test_console_helper_only_accepts_numeric_pid(self):
        with patch('codex_focus._powershell', return_value='123\n') as run:
            self.assertEqual(codex_focus._console_window(42), 123)
            self.assertIn('AttachConsole(42)', run.call_args.args[0])
            for invalid in (True, '42; bad', 0, -1, 2**32):
                self.assertEqual(codex_focus._console_window(invalid), 0)
            self.assertEqual(run.call_count, 1)

    def test_foreground_checks_pid_and_restores_minimized_window(self):
        user = Mock()
        user.GetWindowThreadProcessId.side_effect = lambda handle, pointer: setattr(pointer._obj, 'value', 10)
        user.GetForegroundWindow.return_value = 123
        user.IsWindowVisible.return_value = True
        user.IsIconic.return_value = True
        with patch('codex_focus.ctypes.WinDLL', return_value=user, create=True):
            self.assertTrue(codex_focus._foreground(dict(hwnd=123, pid=10)))
            user.ShowWindow.assert_called_once_with(123, 9)
            self.assertFalse(codex_focus._foreground(dict(hwnd=123, pid=11)))
            self.assertEqual(user.SetForegroundWindow.call_count, 1)


if __name__ == '__main__':
    unittest.main()
