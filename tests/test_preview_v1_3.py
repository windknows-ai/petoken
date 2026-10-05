"""Synthetic preview isolation and bounded lifecycle checks."""
from contextlib import ExitStack, redirect_stderr
from io import StringIO
import json
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QComboBox, QLabel
from PySide6.QtGui import QColor, QImage, QPixmap
from pet_assets import PREVIEW_STATES
import halo_geometry
from tools.preview_v1_3 import ANCHORS, MAX_TASKS, Preview, fixture_tasks, main, parse_args


class PreviewFixtureTests(unittest.TestCase):
    def test_fixture_unknown_zero_partial_and_provider_identity(self):
        for count in (0, 1, 8, 24, 64):
            tasks = fixture_tasks(count)
            self.assertEqual(len(tasks), count)
            self.assertEqual(len({(t['provider_id'], t['task_key']) for t in tasks}), count)
            # Mixed (default) alternates Codex and Claude Code; Claude keys are scoped.
            self.assertEqual([t['provider_id'] for t in tasks],
                             ['claude' if i % 2 else 'codex' for i in range(count)])
            self.assertTrue(all(t['task_key'].startswith('claude:') == (t['provider_id'] == 'claude')
                                for t in tasks))
            for source in ('codex', 'claude'):
                self.assertTrue(all(t['provider_id'] == source
                                    for t in fixture_tasks(count, source=source)))
            self.assertEqual(len({t['presentation']['tokens']['total_tokens'] for t in tasks}), count)
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

    def test_cli_accepts_all_registered_poses_and_large_task_numbers(self):
        for pose in PREVIEW_STATES:
            for count in (24, MAX_TASKS):
                with self.subTest(pose=pose, count=count):
                    args = parse_args(['--pose', pose, '--count', str(count),
                                       '--expand', str(count), '--smoke', '1'])
                    self.assertEqual((args.pose, args.count, args.expand), (pose, count, count))

    def test_cli_rejects_outside_fixture_bounds_before_gui_start(self):
        for argv in (['--count', '-1'], ['--count', str(MAX_TASKS + 1)],
                     ['--count', '24', '--expand', '25'], ['--expand', '0'],
                     ['--pose', 'invented']):
            with self.subTest(argv=argv), redirect_stderr(StringIO()), self.assertRaises(SystemExit) as result:
                parse_args(argv)
            self.assertEqual(result.exception.code, 2)


class PreviewTests(unittest.TestCase):
    def test_show_hub_control_matches_real_context_pin_and_visibility(self):
        with tempfile.TemporaryDirectory() as directory, patch('widget.PREF_DIR', Path(directory)):
            preview = Preview(count=3)
            try:
                for visible in (False, True, False):
                    preview.visible.setChecked(visible)
                    self.app.processEvents()
                    self.assertEqual(preview.panel.isVisible(), visible)
                    self.assertEqual(preview.panel.is_pinned(), visible)
                    menu = preview.pet.context_menu()
                    self.assertEqual(menu.actions()[0].isChecked(), visible)
                    menu.deleteLater()
            finally:
                preview.cleanup()
                preview.close()
                preview.deleteLater()
                self.app.processEvents()

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_all_activity_pose_controls_render_distinct_artwork_and_usage_alias(self):
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            stack.enter_context(patch('widget.PREF_DIR', Path(directory)))
            monitor = stack.enter_context(patch('activity.ActivityMonitor.start',
                                                side_effect=AssertionError('Live monitor started')))
            preview = Preview(count=0)
            try:
                self.assertEqual(tuple(preview.pose.itemText(i) for i in range(preview.pose.count())),
                                 PREVIEW_STATES)
                self.assertEqual(preview.count.maximum(), MAX_TASKS)
                self.assertEqual(preview.detail_task.maximum(), MAX_TASKS)
                preview.motion.setChecked(False)
                painted = {}
                for pose in PREVIEW_STATES:
                    preview.pose.setCurrentText(pose)
                    self.assertEqual(preview.pet.current_state, pose)
                    image = preview.pet.grab().toImage().convertToFormat(QImage.Format_RGBA8888)
                    self.assertFalse(image.isNull())
                    painted[pose] = hashlib.sha256(bytes(image.constBits())).hexdigest()
                self.assertEqual(len({painted[pose] for pose in PREVIEW_STATES if pose != 'usage'}), 5)
                self.assertEqual(painted['usage'], painted['idle'])
                labels = '\n'.join(label.text() for label in preview.findChildren(QLabel))
                self.assertIn('usage uses idle artwork', labels)
                self.assertIn('do not verify live detection', labels)
                monitor.assert_not_called()
            finally:
                preview.cleanup()
                preview.close()
                preview.deleteLater()
                self.app.processEvents()

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
                self.assertEqual(preview.panel.prefs['tracking_provider'], 'auto')
                self.assertEqual(set(preview.panel.task_manager.task_identities()),
                                 {('codex', 'synthetic-qa-1'), ('claude', 'claude:synthetic-qa-2'),
                                  ('codex', 'synthetic-qa-3')})
                labels = '\n'.join(label.text() for label in preview.findChildren(QLabel))
                choices = [combo.itemText(index) for combo in preview.findChildren(QComboBox)
                           for index in range(combo.count())]
                self.assertNotIn('OpenCode', labels)
                self.assertNotIn('opencode', choices)
                for source in ('mixed', 'codex', 'claude'):
                    self.assertIn(source, choices)
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
                self.assertFalse(preview.panel.isVisible())
                self.assertTrue(preview.panel.task_manager.window_for(('codex', 'synthetic-qa-1')).isVisible())
                preview.visible.setChecked(True)
                preview.ring.setChecked(False)
                self.assertFalse(preview.panel.prefs['star_ring_enabled'])
                self.assertFalse(preview.panel.task_manager.window_for(('codex', 'synthetic-qa-1')).isVisible())
                preview.language.setCurrentText('en')
                self.assertEqual(preview.panel.language, 'en')
                self.assertFalse(preview.panel.task_manager.window_for(('codex', 'synthetic-qa-1')).isVisible())
                preview.ring.setChecked(True)
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
                self.assertEqual(evidence['provider'], 'mixed')
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

    def test_large_fixture_paging_and_off_page_detail_controls(self):
        with tempfile.TemporaryDirectory() as directory, patch('widget.PREF_DIR', Path(directory)):
            preview = Preview(count=24)
            manager = preview.panel.task_manager
            try:
                for count in (24, MAX_TASKS):
                    with self.subTest(count=count):
                        preview.count.setValue(count)
                        self.assertEqual(manager.total_task_count(), count)
                        self.assertEqual(len(manager.task_identities()), count)
                        self.assertLessEqual(manager.window_count(), 8)
                        self.assertEqual(manager.page_count, (count + 7) // 8)
                        labels = dict(manager._labels)
                        preview.detail_task.setValue(count)
                        key = next(key for key in manager.task_identities() if labels[key] == count)
                        self.assertNotIn(key, manager.window_identities())
                        preview.toggle_detail()
                        self.assertEqual(manager.expanded_identity, key)
                        self.assertTrue(manager.detail_window.isVisible())
                        self.assertEqual(manager.page_index, (count - 1) // 8)
                        self.assertEqual(preview.page.value(), manager.page_index + 1)
                        self.assertEqual(manager._labels, labels)
                        preview.toggle_detail()
                        self.assertIsNone(manager.expanded_identity)
                        preview.page.setValue(1)
                        self.assertEqual(manager.page_index, 0)
                        self.assertLessEqual(manager.window_count(), 8)
                output = Path(directory) / 'large-fixture.png'
                preview.capture(output)
                evidence = json.loads(output.with_suffix('.json').read_text(encoding='utf-8'))
                self.assertEqual(evidence['task_count'], MAX_TASKS)
                self.assertEqual(evidence['requested_task_count'], MAX_TASKS)
                self.assertLessEqual(evidence['star_window_count'], 8)
                self.assertEqual(evidence['page_count'], 8)
            finally:
                preview.cleanup()
                preview.close()
                preview.deleteLater()
                self.app.processEvents()

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
                        requested_x = (screen.left() if 'left' in anchor else
                                       screen.right() - rectangle.width() + 1 if 'right' in anchor else
                                       screen.center().x() - rectangle.width() // 2)
                        requested_y = (screen.top() if 'top' in anchor else
                                       screen.bottom() - rectangle.height() + 1 if 'bottom' in anchor else
                                       screen.center().y() - rectangle.height() // 2)
                        expected = halo_geometry.clamp_composition(
                            (requested_x, requested_y, rectangle.width(), rectangle.height()),
                            (screen.left(), screen.top(), screen.right(), screen.bottom()))
                        self.assertEqual((rectangle.x(), rectangle.y(), rectangle.width(), rectangle.height()),
                                         expected.pet_rect)
                        self.assertIsNotNone(expected.pose)
                        self.assertEqual(expected.pose.cx, rectangle.x() + rectangle.width() / 2)
                        self.assertEqual(expected.pose.cy, rectangle.y() + rectangle.height() * .60)
                        left, top, right, bottom = halo_geometry.projected_bounds(expected.pose)
                        self.assertGreaterEqual(left, screen.left())
                        self.assertGreaterEqual(top, screen.top())
                        self.assertLessEqual(right, screen.right() + 1)
                        self.assertLessEqual(bottom, screen.bottom() + 1)
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
                # This assertion covers the settled card; opening opacity is
                # separately represented by the owned transition snapshot.
                preview.panel.task_manager.detail_transition.animation.setCurrentTime(220)
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

    def test_settings_save_applies_tracking_choice_inside_preview(self):
        from widget import Settings
        with tempfile.TemporaryDirectory() as directory, patch('widget.PREF_DIR', Path(directory)):
            preview = Preview(count=4)
            manager = preview.panel.task_manager
            try:
                settings = Settings(preview.panel)
                settings.tracking.setCurrentIndex(settings.tracking.findData('claude'))
                settings.language.setCurrentIndex(settings.language.findData('en'))
                settings.save()  # Previously raised TypeError (mark_provider).
                self.app.processEvents()
                self.assertEqual(preview.panel.prefs['tracking_provider'], 'claude')
                self.assertEqual(preview.language.currentText(), 'en')
                self.assertEqual({key[0] for key in manager.window_identities()}, {'claude'})
                self.assertEqual(preview.panel.snapshot['provider_id'], 'claude')
                preview.count.setValue(3)  # A refresh keeps the saved choice.
                self.assertEqual(preview.panel.prefs['tracking_provider'], 'claude')
                preview.provider.setCurrentText('codex')  # New source resets it.
                self.assertEqual(preview.panel.prefs['tracking_provider'], 'codex')
                self.assertEqual({key[0] for key in manager.window_identities()}, {'codex'})
            finally:
                preview.cleanup()
                preview.close()
                preview.deleteLater()
                self.app.processEvents()

    def test_capture_cli_rejects_unbounded_or_invalid_requests(self):
        for argv in (['--output', 'unused.png'], ['--smoke', '0'],
                     ['--smoke', 'nan'], ['--smoke', 'inf'], ['--smoke', '1e100'],
                     ['--count', '0', '--expand', '1'], ['--provider', 'opencode'],
                     ['--provider', 'all'], ['--anchor', 'outside']):
            diagnostic = StringIO()
            with self.subTest(argv=argv), redirect_stderr(diagnostic), self.assertRaises(SystemExit) as result:
                main(argv)
            self.assertEqual(result.exception.code, 2)
            self.assertIn('error:', diagnostic.getvalue())


if __name__ == '__main__':
    unittest.main()
