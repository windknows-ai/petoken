"""First-use guidance is discoverable from normal application startup."""
from contextlib import ExitStack
import unittest
from unittest.mock import patch

import widget


class WorkbenchStartupTests(unittest.TestCase):
    def startup(self, preferences, arguments=()):
        with ExitStack() as stack:
            stack.enter_context(patch('widget.sys.argv', ['petoken', *arguments]))
            app = stack.enter_context(patch('widget.QApplication')).return_value
            app.exec.return_value = 0
            panel = stack.enter_context(patch('widget.Panel')).return_value
            panel.prefs = preferences
            lock = stack.enter_context(patch('widget.QLockFile')).return_value
            lock.tryLock.return_value = True
            stack.enter_context(patch('widget.PREF_DIR'))
            stack.enter_context(patch('pet.DesktopPet'))
            timer = stack.enter_context(patch('widget.QTimer.singleShot'))
            self.assertEqual(widget.main(), 0)
            panel.restore_companion.assert_called_once()
            lock.unlock.assert_called_once()
            return panel, timer

    def test_unseen_normal_launch_schedules_optional_guide(self):
        for preferences in [{}, {'workbench_tutorial_seen': False}]:
            with self.subTest(preferences=preferences):
                panel, timer = self.startup(preferences)
                timer.assert_called_once_with(0, panel, panel.open_workbench_tutorial)
                panel.open_workbench_tutorial.assert_not_called()

    def test_seen_normal_launch_preserves_quiet_startup(self):
        _, timer = self.startup({'workbench_tutorial_seen': True})
        timer.assert_not_called()

    def test_ordinary_smoke_does_not_schedule_first_use_guide(self):
        _, timer = self.startup({'workbench_tutorial_seen': False},
                                ['--smoke', 'capture.png'])
        self.assertEqual(timer.call_count, 1)
        self.assertEqual(timer.call_args.args[0], 6000)


if __name__ == '__main__':
    unittest.main()
