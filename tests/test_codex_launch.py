import base64
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import codex_launch
from codex_focus import _argv


def payload(command):
    script = base64.b64decode(command[-1]).decode('utf-16le')
    data = re.search(r"FromBase64String\('([A-Za-z0-9+/=]+)'\)", script).group(1)
    return json.loads(base64.b64decode(data).decode('utf-8'))


class LaunchTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)/'项目 $name ; space'
        self.folder.mkdir()
        self.addCleanup(patch.stopall)
        self.executables_patcher = patch('codex_launch._executables', return_value=('C:/tools/codex.exe', 'powershell.exe'))
        self.executables = self.executables_patcher.start()
        self.which = patch('codex_launch.shutil.which', return_value='wt.exe').start()

    def test_windows_terminal_is_new_window(self):
        command = codex_launch.launch_command(self.folder, 'Fix this task')
        self.assertEqual(command[:4], ['wt.exe', '--window', 'new', 'new-tab'])
        self.assertEqual(command[4:9], ['powershell.exe', '-NoLogo', '-NoProfile', '-NoExit', '-EncodedCommand'])
        data = payload(command)
        self.assertEqual(data['executable'], 'C:/tools/codex.exe')
        self.assertEqual(data['folder'], str(self.folder.resolve()))

    def test_without_terminal_uses_powershell(self):
        self.which.return_value = None
        command = codex_launch.launch_command(self.folder, 'Fix')
        self.assertEqual(command[:2], ['powershell.exe', '-NoLogo'])

    def test_generation_never_runs_any_process(self):
        with patch('codex_launch.subprocess.Popen') as start, patch('codex_launch.subprocess.run') as run:
            codex_launch.launch_command(self.folder, 'Fix')
            self.assertTrue(codex_launch.available())
        start.assert_not_called()
        run.assert_not_called()

    @unittest.skipUnless(sys.platform == 'win32', 'Windows native argv parser')
    def test_prompts_are_literal_single_arguments_and_not_cli_flags(self):
        for prompt in ('--dangerously-bypass-approvals-and-sandbox',
                       '"quotes" ; & whoami | x $(touch x) `backticks` %PATH%',
                       "新任务\nnext line 'single' \\tail\\", '$env:HOME'):
            command = codex_launch.launch_command(self.folder, prompt)
            data = payload(command)
            arguments = _argv('codex.exe ' + data['arguments'])
            self.assertEqual(arguments, ['codex.exe', '--cd', str(self.folder.resolve()), '--', prompt])
            self.assertNotIn(prompt, base64.b64decode(command[-1]).decode('utf-16le'))
            self.assertTrue(all(';' not in argument for argument in command))

    def test_missing_cli_or_shell_is_unavailable(self):
        for executables in ((None, 'powershell.exe'), ('codex.exe', None), (None, None)):
            self.executables.return_value = executables
            self.assertFalse(codex_launch.available())
            with self.assertRaises(RuntimeError):
                codex_launch.launch_command(self.folder, 'Fix')

    def test_invalid_prompt_and_folder(self):
        for prompt in ('', ' ', None, 'a\0b'):
            with self.assertRaises(ValueError):
                codex_launch.launch_command(self.folder, prompt)
        file = self.folder/'file.txt'
        file.touch()
        for folder in (self.folder/'missing', file, None, 'nul\0name'):
            with self.assertRaises(ValueError):
                codex_launch.launch_command(folder, 'Fix')

    def test_oversized_command_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'command-line limit'):
            codex_launch.launch_command(self.folder, '字' * 10000)

    def test_detection_only_accepts_native_executable_and_supported_platform(self):
        self.executables_patcher.stop()
        binary = self.folder/'codex.exe'
        binary.touch()
        with patch('codex_launch.sys.platform', 'win32'), patch('codex_launch._proxy_binary', return_value=str(binary)):
            self.which.side_effect = lambda name: 'powershell.exe' if name == 'powershell.exe' else None
            self.assertTrue(codex_launch.available())
            for value in (str(binary.with_suffix('.cmd')), str(binary.with_suffix('.ps1')), None):
                with patch('codex_launch._proxy_binary', return_value=value):
                    self.assertFalse(codex_launch.available())
        with patch('codex_launch.sys.platform', 'linux'):
            self.assertFalse(codex_launch.available())


class NativeArgumentTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == 'win32' and shutil.which('powershell.exe'), 'Windows PowerShell')
    def test_real_powershell_passes_literal_unicode_quotes_and_injection_text_to_python(self):
        # Run only a synthetic argv recorder, never Codex or a terminal window.
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root)
            output, sentinel = directory/'argv.json', directory/'must-not-exist.txt'
            prompt = '"quoted" 日本語 ; $(New-Item ' + str(sentinel) + ') & %PATH%\nline\\'
            arguments = ['--cd', str(directory), '--', prompt]
            code = 'import json,sys;from pathlib import Path;Path(' + repr(str(output)) + ').write_text(json.dumps(sys.argv[1:],ensure_ascii=False),encoding="utf-8")'
            script = codex_launch._encoded_script(dict(executable=sys.executable, folder=str(directory),
                arguments=subprocess.list2cmdline(['-c', code, *arguments])))
            subprocess.run([shutil.which('powershell.exe'), '-NoProfile', '-EncodedCommand', script],
                           capture_output=True, check=True, timeout=10,
                           creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(json.loads(output.read_text(encoding='utf-8')), arguments)
            self.assertFalse(sentinel.exists())


if __name__ == '__main__':
    unittest.main()
