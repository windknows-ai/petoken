"""The 2.0 adjustable test build: every control works on synthetic data only."""
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QPushButton

APP = QApplication.instance() or QApplication([])


class PreviewV20Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.patches = [patch('widget.PREF_DIR', Path(self.temp.name)),
                        patch('quick_launch.build_command', lambda *a, **k: ['preview']),
                        patch('claude_launch.launch', lambda argv: None)]
        for item in self.patches:
            item.start()
        from tools.preview_v2_0 import Preview
        self.preview = Preview('zh_CN')
        self.preview.pet.activity_timer.stop()
        self.preview.pet.timer.stop()

    def tearDown(self):
        preview = self.preview
        preview.panel.focus_mode.abandon()
        for card in (preview.panel._focus_card, preview.panel._continuation_card):
            if card is not None:
                card.close()
        if preview.panel.workbench_window is not None:
            preview.panel.workbench_window.hide()
            preview.panel.workbench_window.deleteLater()
        preview.panel.tray.hide()
        preview.pet.close()
        preview.store.close()
        preview.panel.closing = True
        preview.panel.close()
        preview.panel.deleteLater()
        preview.deleteLater()
        APP.processEvents()
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def test_focus_runs_faster_and_finishes(self):
        preview = self.preview
        preview.clock.set_speed(60)
        preview.panel.start_focus(25)
        preview.pet.interaction_state = None              # After the cheer, she reads.
        preview.pet.update_activity()
        self.assertEqual(preview.pet.current_state, 'focus_read')
        preview.focus_now()
        self.assertEqual(preview.panel.focus_mode.phase, 'break')
        self.assertIsNotNone(preview.panel._focus_card)

    def test_goals_with_any_numbers(self):
        preview = self.preview
        preview.goal_amount.setValue(2)
        preview.goal_unit.setCurrentIndex(1)            # 2 billion.
        preview.used_amount.setValue(1.7)
        preview.used_unit.setCurrentIndex(1)
        with patch.object(preview.pet, 'interact') as interact:
            preview.apply_goal()
            interact.assert_called_with('worried', 4)
        self.assertEqual(preview.store.get_goal(preview.projects[0]['id'])['weekly_tokens'], 2_000_000_000)
        with patch.object(preview.pet, 'interact') as interact:
            preview.next_week()
            interact.assert_called_with('proud', 4)

    def test_notes_card_and_review(self):
        preview = self.preview
        preview.add_note()
        preview.show_card()
        card = preview.panel._continuation_card
        self.assertIsNotNone(card)
        self.assertEqual(card.note_text.text(), '提交按钮还没接上，下次先做它')
        self.assertIn('给登录页加上表单校验', card.lines.text())
        card.start_button.click()                       # Simulated: no terminal.
        preview.make_review()
        reviews = [s for s in preview.store.list_schedules() if s['state'] == 'review']
        self.assertEqual(len(reviews), 1)
        preview.earn()
        self.assertIn(preview.sticker.currentData(), preview.store.achievements())

    def test_every_simple_button_runs(self):
        preview = self.preview
        skip = {'退出 / Exit', '开始专注（选待办、休息）…', '打开报告'}
        for widget in preview.findChildren(QPushButton):
            if widget.text() in skip:
                continue
            widget.click()
        preview.drag_end()
        for index in range(preview.pose.count()):
            preview.pose.setCurrentIndex(index)
            preview.pet.tick()
        self.assertTrue(preview.pet.frame is not None)


class CombinedPreviewTests(unittest.TestCase):
    """Both windows share one pet: 1.x tasks and the star ring with 2.0 features."""

    def test_both_windows_drive_the_same_pet(self):
        temp = tempfile.TemporaryDirectory()
        patches = [patch('widget.PREF_DIR', Path(temp.name)),
                   patch('quick_launch.build_command', lambda *a, **k: ['preview']),
                   patch('claude_launch.launch', lambda argv: None)]
        for item in patches:
            item.start()
        from tools.preview_v1_3 import Preview as BasePreview
        from tools.preview_v2_0 import Preview
        base = BasePreview(3, 'zh_CN')
        preview = Preview('zh_CN', base)
        try:
            self.assertIs(preview.pet, base.pet)
            self.assertIsNone(preview.pet.preview_state)       # 1.x "idle" lets her act.
            self.assertEqual(base.panel.task_manager.total_task_count(), 3)   # Star ring tasks.
            preview.pet.interact('headpat_happy', 2)
            self.assertEqual(preview.pet.current_state, 'headpat_happy')
            base.pose.setCurrentText('music')
            self.assertEqual(preview.pet.current_state, 'music')
            base.pose.setCurrentText('idle')
            preview.pet.interaction_state = None          # The pat is over.
            preview.panel.start_focus(25)
            preview.pet.interaction_state = None          # After the cheer, she reads.
            preview.pet.update_activity()
            self.assertEqual(preview.pet.current_state, 'focus_read')
            preview.make_review()
        finally:
            preview.panel.focus_mode.abandon()
            for card in (preview.panel._focus_card, preview.panel._continuation_card):
                if card is not None:
                    card.close()
            preview.store.close()
            base.cleanup()
            base.deleteLater()
            preview.deleteLater()
            APP.processEvents()
            for item in reversed(patches):
                item.stop()
            temp.cleanup()


if __name__ == '__main__':
    unittest.main()
