"""Bounded workbench preview CLI, independent of live application startup."""
from contextlib import redirect_stderr
from io import StringIO
import unittest

from tools.preview_workbench import parse_args


class WorkbenchPreviewArgumentsTests(unittest.TestCase):
    def test_defaults_and_largest_task_fixture(self):
        args = parse_args(['--count', '64', '--tab', 'notes', '--language', 'en'])
        self.assertEqual((args.count, args.tab, args.language), (64, 'notes', 'en'))
        self.assertEqual((args.width, args.height), (980, 700))

    def test_empty_and_minimum_supported_size(self):
        args = parse_args(['--empty', '--count', '0', '--width', '680', '--height', '460'])
        self.assertTrue(args.empty)
        self.assertEqual(args.count, 0)

    def test_invalid_timers_sizes_and_tasks_fail_before_startup(self):
        for values in [('smoke', 'nan'), ('smoke', 'inf'), ('smoke', '-1'),
                       ('smoke', '0'), ('width', '679'), ('height', '459'), ('count', '65')]:
            with self.subTest(values=values), redirect_stderr(StringIO()):
                with self.assertRaises(SystemExit):
                    parse_args(['--' + values[0], values[1]])

    def test_output_requires_bounded_capture_time(self):
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit):
            parse_args(['--output', 'unused.png'])


if __name__ == '__main__':
    unittest.main()
