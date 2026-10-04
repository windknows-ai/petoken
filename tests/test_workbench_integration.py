"""Workbench entry points preserve the accepted companion lifecycle."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QMessageBox

from widget import Panel
from pet import DesktopPet
from tools.preview_v1_3 import fixture_tasks


class WorkbenchIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.patch = patch('widget.PREF_DIR', Path(self.temp.name))
        self.patch.start()
        self.panel = Panel(live=False)
        self.panel.pet = DesktopPet(self.panel)
        self.panel.pet.activity_timer.stop()

    def tearDown(self):
        with patch('workbench.QMessageBox.question', return_value=QMessageBox.Discard):
            self.panel.shutdown()
        self.panel.close()
        self.panel.deleteLater()
        self.app.processEvents()
        self.patch.stop()
        self.temp.cleanup()

    def test_nonlive_uses_temporary_database_and_reuses_window(self):
        self.panel.open_workbench()
        first = self.panel.workbench_window
        first.todo_input.setText('Temporary QA')
        first.add_todo()
        self.assertFalse((Path(self.temp.name) / 'workbench.sqlite3').exists())
        self.assertEqual(first.store.list_todos()[0]['title'], 'Temporary QA')
        first.close()
        self.panel.open_workbench()
        self.assertIs(self.panel.workbench_window, first)
        self.assertTrue(first.isVisible())
        self.assertIn('workbench_open', self.panel.tray_actions)
        self.assertTrue(self.panel.workbench_button.text())

    def test_live_store_path_and_reopen_are_owned_by_user_preferences(self):
        # No live threads: only choose the production path after construction.
        self.panel.live = True
        self.panel.open_workbench()
        self.panel.live = False
        self.assertEqual(self.panel.workbench_window.store.path,
                         Path(self.temp.name) / 'workbench.sqlite3')
        self.assertTrue(self.panel.workbench_window.store.path.exists())
        self.assertIsNone(self.panel._workbench_temp)

    def test_shutdown_cancel_preserves_companion_and_draft(self):
        self.panel.open_workbench()
        self.panel.workbench_window.new_note()
        self.panel.workbench_window.note_body.setPlainText('Keep draft')
        with patch('workbench.QMessageBox.question', return_value=QMessageBox.Cancel):
            self.assertFalse(self.panel.shutdown())
        self.assertFalse(self.panel.closing)
        self.assertFalse(self.panel.stop.is_set())
        self.assertFalse(self.panel.task_manager._shutdown)
        self.assertEqual(self.panel.workbench_window.note_body.toPlainText(), 'Keep draft')

    def test_language_update_keeps_note_and_entry_point(self):
        self.panel.open_workbench()
        self.panel.workbench_window.new_note()
        self.panel.workbench_window.note_body.setPlainText('Keep draft')
        self.panel.prefs['language'] = 'en'
        self.panel.apply_language()
        self.assertEqual(self.panel.workbench_window.tabs.tabText(0), 'Home')
        self.assertEqual(self.panel.workbench_button.text(), 'Open workbench')
        self.assertEqual(self.panel.workbench_window.note_body.toPlainText(), 'Keep draft')

    def test_workbench_and_hub_visibility_do_not_retire_ring_tasks(self):
        manager = self.panel.task_manager
        manager.apply_snapshot(fixture_tasks(24))
        self.panel.pet.show()
        manager.set_visible(True)
        identities = tuple(manager.task_identities())
        self.panel.open_workbench()
        self.app.processEvents()
        window = self.panel.workbench_window
        self.assertEqual(window.task_list.count(), 24)
        window.close()
        self.panel.hide()
        self.assertEqual(tuple(manager.task_identities()), identities)
        self.assertEqual(manager.total_task_count(), 24)
        manager.apply_snapshot(fixture_tasks(3))
        self.panel.open_workbench()
        self.assertEqual(window.task_list.count(), 3)
        self.assertEqual(manager.total_task_count(), 3)


if __name__ == '__main__':
    unittest.main()
