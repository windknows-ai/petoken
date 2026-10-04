"""Synthetic preview isolation and bounded lifecycle checks."""
from contextlib import ExitStack, redirect_stderr
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QComboBox, QLabel
from PySide6.QtGui import QColor, QImage, QPixmap
from tools.preview_v1_3 import ANCHORS, Preview, fixture_tasks, main


class PreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_fixture_unknown_zero_partial_and_provider_identity(self):
        for count in (0, 1, 8):
            tasks = fixture_tasks(count)
            self.assertEqual(len(tasks), count)
            self.assertEqual(len({(t['provider_id'], t['task_key']) for t in tasks}), count)
            self.assertTrue(all(task['provider_id'] == 'codex' for task in tasks))
        for case in ('zero', 'unknown', 'partial'):
            for task in fixture_tasks(2, case=case):
                projection = task['presentation']
                self.assertIn('Synthetic QA', task['display']['project'])
                if case == 'zero':
                    self.assertEqual(set(projection['tokens'].values()), {0})
                    self.assertEqual(projection['cost_amount'], 0)
                elif case == 'unknown':
                    self.assertEqual(set(projection['tokens'].values()), {None})
                    self.assertIsNone(projection['model'])
                else:
                    self.assertTrue(projection['partial'])
                    self.assertIn(None, projection['tokens'].values())
        shared = fixture_tasks(3, case='same_project')
        self.assertEqual(len({t['display']['project'] for t in shared}), 1)
        self.assertEqual(len({t['task_key'] for t in shared}), 3)
        self.assertEqual(len({t['presentation']['tokens']['total_tokens'] for t in shared}), 3)
        self.assertTrue(all(t['presentation']['cost_amount'] is None for t in shared))
        long_labels = fixture_tasks(1, case='long_labels')[0]
        self.assertGreater(len(long_labels['display']['project']), 100)
        self.assertGreater(len(long_labels['presentation']['model']), 100)

    def test_preview_isolated_controls_and_cleanup(self):
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            stack.enter_context(patch('widget.PREF_DIR', Path(directory)))
            reads = [stack.enter_context(patch(name, side_effect=AssertionError('Live source accessed')))
                     for name in ('usage.CodexStore.read',
                                  'desktop.ActiveTask.start', 'desktop.RateLimits.start',
                                  'activity.ActivityMonitor.start', 'provider_poller.ProviderPoller.loop_tick')]
            preview = Preview(count=3, language='zh_CN', case='partial')
            try:
                self.assertFalse(preview.panel.live)
                self.assertEqual(preview.panel.task_manager.window_count(), 3)
                self.assertFalse(preview.pet.activity_timer.isActive())
                self.assertEqual(preview.panel.snapshot['provider_id'], 'codex')
                self.assertEqual(preview.panel.prefs['tracking_provider'], 'codex')
                labels = '\n'.join(label.text() for label in preview.findChildren(QLabel))
                choices = [combo.itemText(index) for combo in preview.findChildren(QComboBox)
                           for index in range(combo.count())]
                self.assertNotIn('OpenCode', labels)
                self.assertNotIn('opencode', choices)
                self.assertNotIn('mixed', choices)
                preview.source.setChecked(False)
                self.assertEqual(preview.panel.task_manager.window_count(), 0)
                preview.source.setChecked(True)
                self.assertEqual(preview.panel.task_manager.window_count(), 3)
                preview.topmost.setChecked(False)
                self.assertFalse(preview.panel.prefs['always_on_top'])
                preview.count.setValue(1)
                self.assertEqual(preview.panel.task_manager.window_count(), 1)
                preview.pose.setCurrentText('working')
                self.assertEqual(preview.pet.current_state, 'working')
                preview.motion.setChecked(False)
                self.assertFalse(preview.panel.prefs['pet_motion'])
                preview.visible.setChecked(False)
                self.assertFalse(preview.panel.task_manager.window_for(('codex', 'synthetic-qa-1')).isVisible())
                preview.visible.setChecked(True)
                preview.language.setCurrentText('en')
                self.assertEqual(preview.panel.language, 'en')
                preview.count.setValue(0)
                self.assertEqual(preview.panel.task_manager.window_count(), 0)
                self.assertIn('SYNTHETIC QA', preview.panel.connection.text())
                for read in reads:
                    read.assert_not_called()
            finally:
                preview.cleanup()
                preview.close()
                preview.deleteLater()
                self.app.processEvents()
            self.assertFalse(preview.panel.clock.isActive())
            self.assertFalse(preview.pet.timer.isActive())
            self.assertFalse(preview.panel.task_manager.motion_timer.isActive())
            self.assertEqual(preview.panel.task_manager.window_count(), 0)

    def test_detail_controls_use_real_manager_and_close_on_source_loss(self):
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            stack.enter_context(patch('widget.PREF_DIR', Path(directory)))
            reads = [stack.enter_context(patch(name, side_effect=AssertionError('Live source accessed')))
                     for name in ('usage.CodexStore.read',
                                  'desktop.ActiveTask.start', 'desktop.RateLimits.start',
                                  'activity.ActivityMonitor.start', 'provider_poller.ProviderPoller.loop_tick')]
            preview = Preview(count=3, case='partial')
            manager = preview.panel.task_manager
            try:
                key = next(identity for identity in manager.window_identities()
                           if manager._labels[identity] == 1)
                star = manager.window_for(key)
                before = (star.x(), star.y())
                preview.toggle_detail()
                self.assertEqual(manager.expanded_identity, key)
                self.assertTrue(manager.detail_window.isVisible())
                self.assertIs(manager.window_for(key), star)
                self.assertEqual((star.x(), star.y()), before)
                preview.case.setCurrentText('unknown')
                self.assertEqual(manager.expanded_identity, key)
                self.assertIn('Unknown', manager.detail_window.panel_text())
                output = Path(directory) / 'synthetic-detail.png'
                with patch.object(manager, 'capture_windows', wraps=manager.capture_windows) as layers, \
                        patch.object(QApplication, 'topLevelWidgets',
                                     side_effect=AssertionError('Arbitrary desktop/window scan')):
                    preview.capture(output)
                layers.assert_called_once_with()
                self.assertTrue(output.is_file())
                evidence = json.loads(output.with_suffix('.json').read_text(encoding='utf-8'))
                self.assertEqual(evidence['kind'], 'SYNTHETIC_QA')
                self.assertEqual(evidence['provider'], 'codex')
                self.assertEqual(evidence['anchor'], 'center')
                self.assertFalse(evidence['live_provider_polling'])
                self.assertEqual(evidence['expanded_task_number'], 1)
                self.assertTrue(evidence['detail_visible'])
                preview.source.setChecked(False)
                self.assertIsNone(manager.expanded_identity)
                self.assertEqual(manager.window_count(), 0)
                preview.source.setChecked(True)
                self.assertIsNone(manager.expanded_identity)
                self.assertEqual(manager.window_count(), 3)
                for read in reads:
                    read.assert_not_called()
            finally:
                preview.cleanup()
                preview.close()
                preview.deleteLater()
                self.app.processEvents()
            self.assertIsNone(manager.detail_window)

    def test_anchor_controls_use_actual_clamped_pet_position(self):
        with tempfile.TemporaryDirectory() as directory, patch('widget.PREF_DIR', Path(directory)):
            preview = Preview(count=0)
            try:
                screen = preview.pet.screen().availableGeometry()
                for anchor in ANCHORS:
                    with self.subTest(anchor=anchor):
                        preview.anchor.setCurrentText(anchor)
                        rectangle = preview.pet.geometry()
                        self.assertTrue(screen.contains(rectangle))
                        if 'left' in anchor:
                            self.assertEqual(rectangle.left(), screen.left())
                        if 'right' in anchor:
                            self.assertEqual(rectangle.right(), screen.right())
                        if 'top' in anchor:
                            self.assertEqual(rectangle.top(), screen.top())
                        if 'bottom' in anchor:
                            self.assertEqual(rectangle.bottom(), screen.bottom())
            finally:
                preview.cleanup()
                preview.close()
                preview.deleteLater()
                self.app.processEvents()

    def test_capture_retains_detail_pixels_when_hub_overlaps(self):
        with tempfile.TemporaryDirectory() as directory, patch('widget.PREF_DIR', Path(directory)):
            preview = Preview(count=3, case='partial')
            try:
                preview.toggle_detail()
                detail = preview.panel.task_manager.detail_window
                self.assertTrue(detail.isVisible())
                preview.panel.move(detail.pos())
                self.app.processEvents()
                marker = QPixmap(detail.size())
                marker.fill(QColor('#ff00f0'))
                output = Path(directory) / 'overlapping-detail.png'
                windows = [*preview.panel.task_manager.capture_windows(), preview.panel]
                bounds = windows[0].geometry()
                for window in windows[1:]:
                    bounds = bounds.united(window.geometry())
                overlap = detail.geometry().intersected(preview.panel.geometry())
                self.assertFalse(overlap.isEmpty())
                point = overlap.center() - bounds.topLeft()
                with patch.object(detail, 'grab', return_value=marker):
                    preview.capture(output)
                image = QImage(str(output))
                dpr = preview.devicePixelRatioF()
                self.assertEqual(image.pixelColor(round(point.x() * dpr),
                                                  round(point.y() * dpr)),
                                 QColor('#ff00f0'))
            finally:
                preview.cleanup()
                preview.close()
                preview.deleteLater()
                self.app.processEvents()

    def test_capture_cli_rejects_unbounded_or_invalid_requests(self):
        for argv in (['--output', 'unused.png'], ['--smoke', '0'],
                     ['--smoke', 'nan'], ['--smoke', 'inf'], ['--smoke', '1e100'],
                     ['--count', '0', '--expand', '1'], ['--provider', 'opencode'],
                     ['--provider', 'mixed'], ['--anchor', 'outside']):
            diagnostic = StringIO()
            with self.subTest(argv=argv), redirect_stderr(diagnostic), self.assertRaises(SystemExit) as result:
                main(argv)
            self.assertEqual(result.exception.code, 2)
            self.assertIn('error:', diagnostic.getvalue())


if __name__ == '__main__':
    unittest.main()
