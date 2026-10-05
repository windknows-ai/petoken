"""First-use guide is optional, durable and uses real existing actions."""
import unittest
from unittest.mock import Mock, patch

from PySide6.QtWidgets import QMessageBox
from tests import test_workbench as fixtures


class TutorialTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.WorkbenchTests.setUpClass.__func__)
    setUp = fixtures.WorkbenchTests.setUp
    tearDown = fixtures.WorkbenchTests.tearDown
    def test_first_show_opens_guide_without_creating_records(self):
        self.window.show()
        self.app.processEvents()
        self.assertTrue(self.window.tutorial.isVisible())
        self.assertEqual(self.store.list_projects(), [])
        self.assertEqual(self.store.list_todos(), [])
        self.assertEqual(self.store.list_notes(), [])
        self.assertNotEqual(self.panel.prefs.get('workbench_tutorial_seen'), True)

    def test_skip_is_saved_and_reopen_is_optional(self):
        self.panel.persist = Mock(return_value=True)
        self.window.open_tutorial()
        self.window.tutorial.finish()
        self.assertTrue(self.panel.prefs['workbench_tutorial_seen'])
        self.panel.persist.assert_called_once()
        self.assertFalse(self.window.tutorial.isVisible())
        self.window.open_tutorial()
        self.assertEqual(self.window.tutorial.step, 0)
        self.assertTrue(self.window.tutorial.isVisible())

    def test_failed_preference_save_keeps_guide_and_reverts_flag(self):
        self.panel.persist = Mock(return_value=False)
        self.window.open_tutorial()
        self.assertFalse(self.window.tutorial.finish())
        self.assertNotEqual(self.panel.prefs.get('workbench_tutorial_seen'), True)
        self.assertTrue(self.window.tutorial.isVisible())
        self.assertTrue(self.window.tutorial.error.isVisible())

    def test_action_routes_to_todos_and_can_resume_same_step(self):
        self.window.open_tutorial()
        self.window.tutorial.set_step(2)
        with patch.object(self.window, '_record_dialog', return_value=True) as dialog:
            self.window.tutorial.perform_action()
        dialog.assert_called_once()  # The step opens the Add todo dialog.
        self.assertEqual(self.window.tabs.currentIndex(), 1)
        self.assertFalse(self.window.tutorial.isVisible())
        self.window.open_tutorial()
        self.assertEqual(self.window.tutorial.step, 2)
        self.assertEqual(self.store.list_todos(), [])

    def test_note_action_cancel_preserves_draft_and_guide(self):
        self.window.new_note(self.window.tr('wb_untitled'))
        self.window.note_body.setPlainText('Keep draft')
        self.window.open_tutorial()
        self.window.tutorial.set_step(3)
        with patch('workbench.QMessageBox.question', return_value=QMessageBox.Cancel):
            self.window.tutorial.perform_action()
        self.assertTrue(self.window.tutorial.isVisible())
        self.assertEqual(self.window.note_body.toPlainText(), 'Keep draft')
        self.assertEqual(len(self.store.list_notes()), 1)

    def test_language_and_close_preserve_draft(self):
        self.window.new_note(self.window.tr('wb_untitled'))
        self.window.note_body.setPlainText('Keep draft')
        self.window.open_tutorial()
        self.panel.prefs['language'] = 'en'
        self.window.apply_language()
        self.assertEqual(self.window.tutorial.title.text(), 'A small place to start')
        with patch('workbench.QMessageBox.question', return_value=QMessageBox.Cancel):
            self.assertFalse(self.window.close())
        self.assertTrue(self.window.tutorial.isVisible())
        with patch('workbench.QMessageBox.question', return_value=QMessageBox.Discard):
            self.assertTrue(self.window.close())
        self.assertFalse(self.window.tutorial.isVisible())

    def test_seen_guide_does_not_auto_open_on_new_window(self):
        self.panel.prefs['workbench_tutorial_seen'] = True
        self.window.show()
        self.app.processEvents()
        self.assertFalse(self.window.tutorial.isVisible())

    def test_pending_first_show_is_cancelled_by_shutdown(self):
        self.window.show()
        self.window.shutdown()
        self.app.processEvents()
        self.assertFalse(self.window.tutorial.isVisible())

    def test_next_back_and_completion_do_not_create_samples(self):
        self.panel.persist = Mock(return_value=True)
        self.window.open_tutorial()
        self.window.tutorial.advance()
        self.assertEqual(self.window.tutorial.step, 1)
        self.window.tutorial.back.click()
        self.assertEqual(self.window.tutorial.step, 0)
        for _ in range(5):
            self.window.tutorial.advance()
        self.assertTrue(self.panel.prefs['workbench_tutorial_seen'])
        self.assertFalse(self.window.tutorial.isVisible())
        self.assertEqual(self.store.list_projects(), [])


if __name__ == '__main__':
    unittest.main()
