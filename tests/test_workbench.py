"""Native workbench persistence, draft and task-source boundaries."""
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QDialogButtonBox, QLineEdit, QMessageBox, QWidget

from workbench import WorkbenchWindow
from workbench_store import WorkbenchError, WorkbenchStore


class WorkbenchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = WorkbenchStore(Path(self.temp.name) / 'workbench.sqlite3')
        self.panel = QWidget()
        self.panel.prefs = {'language': 'zh_CN'}
        self.activations = []
        keys = [('codex', str(n)) for n in range(1, 25)]
        self.panel.task_manager = SimpleNamespace(
            task_identities=lambda: keys, _universe={key: {} for key in keys},
            _ring_staged=set(), label_text=lambda key, lang: 'Task ' + key[1],
            activate_task=lambda key, keyboard=False: self.activations.append((key, keyboard)))
        self.window = WorkbenchWindow(self.panel, self.store)

    def tearDown(self):
        with patch('workbench.QMessageBox.question', return_value=QMessageBox.Discard):
            self.window.shutdown()
        self.panel.close()
        self.app.processEvents()
        self.temp.cleanup()

    def test_empty_store_real_actions_and_all_task_rows(self):
        self.assertEqual(self.window.project_list.count(), 2)
        self.assertEqual(self.window.task_list.count(), 24)
        self.assertEqual(self.window.todo_list.count(), 0)
        self.assertEqual(self.window.notes_list.count(), 0)
        self.window.todo_input.setText('整理本周项目')
        self.assertTrue(self.window.add_todo())
        self.assertEqual(self.store.list_todos()[0]['title'], '整理本周项目')
        self.assertEqual(self.window.todo_input.text(), '')

    def test_todo_checkbox_reopens_and_failed_write_reverts(self):
        self.store.create_todo('Verify build')
        self.window.refresh()
        self.window.todo_list.item(0).setCheckState(Qt.Checked)
        self.assertTrue(self.store.list_todos()[0]['done'])
        self.window.todo_list.item(0).setCheckState(Qt.Unchecked)
        self.assertFalse(self.store.list_todos()[0]['done'])
        with patch.object(self.store, 'update_todo', side_effect=WorkbenchError('locked')):
            self.window.todo_list.item(0).setCheckState(Qt.Checked)
        self.assertFalse(self.store.list_todos()[0]['done'])
        self.assertEqual(self.window.todo_list.item(0).checkState(), Qt.Unchecked)

    def test_project_scope_and_explicit_off_page_task_link(self):
        project = self.store.create_project('A')
        self.store.create_todo('Inbox')
        self.store.create_todo('Project', project['id'])
        self.window.refresh()
        self.assertTrue(self.window.assign_task(('codex', '24'), project['id']))
        self.window.select_project(project['id'])
        self.assertEqual(self.window.todo_list.count(), 1)
        self.assertEqual(self.window.task_list.count(), 1)
        self.window.task_list.setCurrentRow(0)
        self.window.open_selected_task()
        self.assertEqual(self.activations, [(('codex', '24'), True)])

    def test_note_save_persists_exact_unicode_and_newlines(self):
        self.assertTrue(self.window.new_note())
        self.window.note_title.setText('交接')
        self.window.note_body.setPlainText('第一行\nsecond line 🌙\n')
        self.assertTrue(self.window.note_dirty)
        self.assertTrue(self.window.save_note())
        self.assertFalse(self.window.note_dirty)
        self.assertEqual(self.store.list_notes()[0]['body'], '第一行\nsecond line 🌙\n')

    def test_failed_note_save_and_navigation_cancel_preserve_draft(self):
        project = self.store.create_project('Other')
        self.window.new_note()
        self.window.note_body.setPlainText('unsaved draft')
        with patch.object(self.store, 'update_note', side_effect=WorkbenchError('locked')):
            self.assertFalse(self.window.save_note())
        self.assertTrue(self.window.note_dirty)
        with patch('workbench.QMessageBox.question', return_value=QMessageBox.Cancel):
            self.assertFalse(self.window.select_project(project['id']))
            self.assertFalse(self.window.close())
        self.assertIsNone(self.window.project_scope)
        self.assertEqual(self.window.note_body.toPlainText(), 'unsaved draft')

    def test_language_change_and_refresh_do_not_replace_dirty_note(self):
        self.window.new_note()
        self.window.note_title.setText('Edited')
        self.window.note_body.setPlainText('draft')
        self.panel.prefs['language'] = 'en'
        self.window.apply_language()
        self.window.refresh()
        self.window.update_tasks()
        self.assertEqual(self.window.note_title.text(), 'Edited')
        self.assertEqual(self.window.note_body.toPlainText(), 'draft')
        self.assertTrue(self.window.note_dirty)
        self.assertEqual(self.window.tabs.tabText(0), 'Home')

    def test_switching_note_cancel_keeps_selection_and_save_switches(self):
        first = self.store.create_note('A')
        second = self.store.create_note('B')
        self.window.refresh(note_id=first['id'])
        self.window.note_body.setPlainText('draft')
        with patch('workbench.QMessageBox.question', return_value=QMessageBox.Cancel):
            self.window.select_note(second['id'])
        self.assertEqual(self.window.note_id, first['id'])
        with patch('workbench.QMessageBox.question', return_value=QMessageBox.Save):
            self.window.select_note(second['id'])
        self.assertEqual(self.store.get_note(first['id'])['body'], 'draft')
        self.assertEqual(self.window.note_id, second['id'])

    def test_stale_task_activation_is_ignored(self):
        self.window.task_list.setCurrentRow(23)
        self.panel.task_manager._universe.clear()
        self.window.open_selected_task()
        self.assertEqual(self.activations, [])
        self.window.update_tasks()
        self.assertEqual(self.window.task_list.count(), 0)

    def test_close_discard_resets_draft_before_window_reopens(self):
        self.window.new_note()
        self.window.note_body.setPlainText('discard me')
        with patch('workbench.QMessageBox.question', return_value=QMessageBox.Discard):
            self.assertTrue(self.window.close())
        self.assertFalse(self.window.note_dirty)
        self.assertEqual(self.window.note_body.toPlainText(), '')

    def test_project_deletion_leaves_note_and_todo_in_inbox(self):
        p = self.store.create_project('Project')
        self.store.create_todo('Keep todo', p['id'])
        note = self.store.create_note('Keep note', 'body', p['id'])
        self.store.delete_project(p['id'])
        self.window.refresh()
        self.window.select_project('')
        self.assertEqual(self.window.todo_list.count(), 1)
        self.assertEqual(self.window.notes_list.count(), 1)
        self.assertEqual(self.store.get_note(note['id'])['body'], 'body')

    def test_failed_project_form_keeps_entered_text_and_dialog_open(self):
        observed = {}
        def enter():
            dialog = QApplication.activeModalWidget()
            inputs = dialog.findChildren(QLineEdit)
            inputs[0].setText('Keep project')
            inputs[1].setText('D:/Keep folder')
            dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.Ok).click()
            observed['visible'] = dialog.isVisible()
            observed['fields'] = [edit.text() for edit in inputs]
            QTimer.singleShot(0, dialog.reject)
        with patch.object(self.store, 'create_project', side_effect=WorkbenchError('locked')):
            QTimer.singleShot(0, enter)
            self.window.edit_project()
        self.assertTrue(observed['visible'])
        self.assertEqual(observed['fields'], ['Keep project', 'D:/Keep folder'])

    def test_clean_selected_note_stays_clean_after_project_delete(self):
        project = self.store.create_project('A')
        note = self.store.create_note('Keep', 'body', project['id'])
        self.window.refresh(note_id=note['id'])
        self.window.projects_table.setCurrentItem(self.window.projects_table.topLevelItem(0))
        with patch('workbench.QMessageBox.question', return_value=QMessageBox.Yes):
            self.window.delete_project()
        self.assertEqual(self.window.note_id, note['id'])
        self.assertEqual(self.window.note_body.toPlainText(), 'body')
        self.assertIsNone(self.window.note_project.currentData())
        self.assertFalse(self.window.note_dirty)


if __name__ == '__main__':
    unittest.main()
