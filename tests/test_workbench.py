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

    def test_completed_filter_has_visible_checkmark_and_keyboard_toggle(self):
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QStyle, QStyleOptionButton
        from widget import STYLE
        self.panel.setStyleSheet(STYLE)
        self.panel.prefs['workbench_tutorial_seen'] = True
        self.store.create_todo('Pending')
        done = self.store.create_todo('Completed')
        self.store.update_todo(done['id'], done['title'], done=True)
        self.window.refresh()
        self.window.tabs.setCurrentIndex(1)
        self.window.show()
        self.app.processEvents()
        checkbox = self.window.show_completed
        option = QStyleOptionButton()
        checkbox.initStyleOption(option)
        indicator = checkbox.style().subElementRect(QStyle.SE_CheckBoxIndicator, option, checkbox)
        image = checkbox.grab().toImage()
        scale = image.devicePixelRatio()
        interior = indicator.adjusted(3, 3, -3, -3)
        dark = sum(image.pixelColor(round(x * scale), round(y * scale)).lightness() < 90
                   for x in range(interior.left(), interior.right() + 1)
                   for y in range(interior.top(), interior.bottom() + 1))
        self.assertGreater(dark, 5, 'Checked indicator must contain a contrasting tick')
        self.assertEqual(self.window.todo_list.count(), 2)
        checkbox.setFocus()
        QTest.keyClick(checkbox, Qt.Key_Space)
        self.assertFalse(checkbox.isChecked())
        self.assertEqual(self.window.todo_list.count(), 1)
        QTest.keyClick(checkbox, Qt.Key_Space)
        self.assertTrue(checkbox.isChecked())
        self.assertEqual(self.window.todo_list.count(), 2)

    def test_todo_actions_require_selection_and_follow_delete_and_filter(self):
        self.assertTrue(self.window.todo_edit_button.isHidden())
        self.assertTrue(self.window.todo_delete_button.isHidden())
        self.store.create_todo('One')
        self.window.refresh()
        self.assertTrue(self.window.todo_edit_button.isHidden())
        self.window.todo_list.setCurrentRow(0)
        self.assertFalse(self.window.todo_edit_button.isHidden())
        self.assertFalse(self.window.todo_delete_button.isHidden())
        self.window.todo_list.clearSelection()
        self.assertTrue(self.window.todo_edit_button.isHidden())
        with patch.object(self.window, '_record_dialog') as edit, \
                patch.object(self.window, '_confirm') as confirm:
            self.window.edit_todo()
            self.window.delete_todo()
        edit.assert_not_called()
        confirm.assert_not_called()
        self.window.todo_list.setCurrentRow(0)
        self.window.todo_list.item(0).setCheckState(Qt.Checked)
        self.window.todo_list.setCurrentRow(0)
        self.window.show_completed.setChecked(False)
        self.assertEqual(self.window.todo_list.count(), 0)
        self.assertTrue(self.window.todo_edit_button.isHidden())
        self.window.show_completed.setChecked(True)
        self.window.todo_list.setCurrentRow(0)
        with patch.object(self.window, '_confirm', return_value=True):
            self.window.delete_todo()
        self.assertEqual(self.window.todo_list.count(), 0)
        self.assertTrue(self.window.todo_delete_button.isHidden())

    def test_project_actions_require_selection_and_folder(self):
        self.assertTrue(self.window.project_edit_button.isHidden())
        self.assertTrue(self.window.project_delete_button.isHidden())
        self.store.create_project('No folder')
        self.store.create_project('With folder', self.temp.name)
        self.window.refresh()
        self.window.projects_table.setCurrentItem(self.window.projects_table.topLevelItem(0))
        self.assertFalse(self.window.project_edit_button.isHidden())
        self.assertTrue(self.window.project_folder_button.isHidden())
        self.window.projects_table.setCurrentItem(self.window.projects_table.topLevelItem(1))
        self.assertFalse(self.window.project_folder_button.isHidden())
        self.window.projects_table.clearSelection()
        self.assertTrue(self.window.project_edit_button.isHidden())
        self.assertTrue(self.window.project_delete_button.isHidden())
        self.assertTrue(self.window.project_folder_button.isHidden())
        with patch.object(self.window, '_confirm') as confirm:
            self.window.delete_project()
        confirm.assert_not_called()

    def test_note_actions_hide_for_empty_and_unselected_records(self):
        self.assertTrue(self.window.save_button.isHidden())
        self.assertTrue(self.window.note_delete_button.isHidden())
        self.window.new_note()
        self.assertFalse(self.window.save_button.isHidden())
        self.assertFalse(self.window.note_delete_button.isHidden())
        self.window.notes_list.clearSelection()
        self.assertTrue(self.window.note_delete_button.isHidden())
        with patch.object(self.window, '_confirm') as confirm:
            self.window.delete_note()
        confirm.assert_not_called()
        self.window.notes_list.setCurrentRow(0)
        with patch.object(self.window, '_confirm', return_value=True):
            self.window.delete_note()
        self.assertTrue(self.window.note_delete_button.isHidden())
        self.assertTrue(self.window.save_button.isHidden())

    def test_task_actions_require_valid_selected_task(self):
        self.assertTrue(self.window.task_detail_button.isHidden())
        self.assertTrue(self.window.task_link_button.isHidden())
        self.window.task_list.setCurrentRow(0)
        self.assertFalse(self.window.task_detail_button.isHidden())
        self.window.task_list.clearSelection()
        with patch('workbench.QDialog') as dialog:
            self.window.open_selected_task()
            self.window.link_selected_task()
        self.assertEqual(self.activations, [])
        dialog.assert_not_called()
        self.assertTrue(self.window.task_detail_button.isHidden())
        self.window.task_list.setCurrentRow(0)
        key = self.window.task_list.currentItem().data(Qt.UserRole)
        self.panel.task_manager._ring_staged.add(key)
        self.window.update_tasks()
        self.assertTrue(self.window.task_detail_button.isHidden())
        self.assertTrue(self.window.task_link_button.isHidden())
        self.panel.task_manager._universe.clear()
        self.window.update_tasks()
        self.assertEqual(self.window.task_list.count(), 0)
        self.assertTrue(self.window.task_detail_button.isHidden())

    def test_native_note_click_cancel_restores_selection_and_actions(self):
        from PySide6.QtTest import QTest
        first = self.store.create_note('First')
        second = self.store.create_note('Second')
        self.window.refresh(note_id=first['id'])
        self.panel.prefs['workbench_tutorial_seen'] = True
        self.window.tabs.setCurrentIndex(2)
        self.window.show()
        self.app.processEvents()
        self.window.note_body.setPlainText('Keep this draft')
        target = next(self.window.notes_list.item(i) for i in range(self.window.notes_list.count())
                      if self.window.notes_list.item(i).data(Qt.UserRole) == second['id'])
        with patch('workbench.QMessageBox.question', return_value=QMessageBox.Cancel):
            QTest.mouseClick(self.window.notes_list.viewport(), Qt.LeftButton,
                            pos=self.window.notes_list.visualItemRect(target).center())
        self.assertEqual(self.window.note_id, first['id'])
        self.assertEqual(self.window.note_body.toPlainText(), 'Keep this draft')
        item = self.window.notes_list.currentItem()
        self.assertEqual(item.data(Qt.UserRole), first['id'])
        self.assertTrue(item.isSelected())
        self.assertFalse(self.window.note_delete_button.isHidden())
        self.assertTrue(self.window.note_delete_button.isEnabled())

    def test_task_link_modal_revalidates_retired_and_staged_identity(self):
        for staged in [False, True]:
            with self.subTest(staged=staged):
                manager = self.panel.task_manager
                key = ('codex', '1')
                manager._universe[key] = {}
                manager._ring_staged.clear()
                self.window.update_tasks()
                self.window.task_list.setCurrentRow(0)
                def invalidate_and_accept():
                    if staged:
                        manager._ring_staged.add(key)
                    else:
                        manager._universe.pop(key)
                    self.window.update_tasks()
                    dialog = self.app.activeModalWidget()
                    dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.Ok).click()
                QTimer.singleShot(0, invalidate_and_accept)
                self.window.link_selected_task()
                self.assertNotIn(key, self.store.task_links())

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
