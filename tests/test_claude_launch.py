import base64
import ctypes
import json
import re
import sys
import tempfile
import unittest
from ctypes import wintypes

import claude_launch


def split_windows(command_line):
    """Windows' own argument parsing (what claude.exe will see)."""
    count = ctypes.c_int()
    shell32 = ctypes.windll.shell32
    shell32.CommandLineToArgvW.restype = ctypes.POINTER(wintypes.LPWSTR)
    argv = shell32.CommandLineToArgvW('x.exe ' + command_line, ctypes.byref(count))
    try:
        return [argv[i] for i in range(1, count.value)]
    finally:
        ctypes.windll.kernel32.LocalFree(argv)


def payload(argv):
    script = base64.b64decode(argv[argv.index('-EncodedCommand') + 1]).decode('utf-16le')
    data = re.search(r"FromBase64String\('([^']+)'\)", script).group(1)
    return json.loads(base64.b64decode(data).decode('utf-8'))


@unittest.skipUnless(sys.platform == 'win32', 'Windows only')
class LaunchCommandTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp.cleanup()

    def test_prompt_reaches_claude_unchanged(self):
        prompt = '修复 "login"; rm -rf / & echo $HOME `whoami` \\path\\ -p --dangerously-skip-permissions\nline 2'
        argv = claude_launch.launch_command(self.temp.name, prompt, cli=r'C:\bin\claude.exe',
                                            shell=r'C:\ps\powershell.exe', terminal=r'C:\wt.exe')
        self.assertEqual(argv[:4], [r'C:\wt.exe', '--window', 'new', 'new-tab'])
        self.assertNotIn(prompt, ' '.join(argv))       # Never visible to a shell.
        data = payload(argv)
        self.assertEqual(data['executable'], r'C:\bin\claude.exe')
        self.assertEqual(split_windows(data['arguments']), ['--', prompt])

    def test_powershell_fallback_and_validation(self):
        argv = claude_launch.launch_command(self.temp.name, 'hi', cli='c.exe', shell='ps.exe', terminal='')
        self.assertEqual(argv[0], 'ps.exe')
        self.assertIn('-NoExit', argv)
        with self.assertRaises(ValueError):
            claude_launch.launch_command(self.temp.name, '  ', cli='c.exe', shell='ps.exe', terminal='')
        with self.assertRaises(ValueError):
            claude_launch.launch_command(self.temp.name + '-missing', 'hi', cli='c.exe', shell='ps.exe')
        with self.assertRaises(ValueError):
            claude_launch.launch_command(self.temp.name, 'x' * 40000, cli='c.exe', shell='ps.exe', terminal='')


if __name__ == '__main__':
    unittest.main()
