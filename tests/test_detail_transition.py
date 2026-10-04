"""Detail snapshot geometry and native lifecycle; no live product services."""
import unittest

from PySide6.QtCore import QEvent, QPoint, QPointF, QRectF, Qt
from PySide6.QtWidgets import QApplication, QLineEdit, QPushButton, QWidget

from detail_transition import (DURATION_MS, START_SCALE_X, START_SCALE_Y,
                               DetailTransition, transformed_rect)


class DetailTransformTests(unittest.TestCase):
    def test_endpoints_scale_about_star_without_zero_size(self):
        card, star = QRectF(500, 300, 360, 420), QPointF(460, 360)
        start = transformed_rect(card, star, 0)
        self.assertAlmostEqual(start.width(), card.width() * START_SCALE_X)
        self.assertAlmostEqual(start.height(), card.height() * START_SCALE_Y)
        self.assertAlmostEqual(start.x() - star.x(), (card.x() - star.x()) * START_SCALE_X)
        self.assertAlmostEqual(start.y() - star.y(), (card.y() - star.y()) * START_SCALE_Y)
        self.assertEqual(transformed_rect(card, star, 1), card)

    def test_union_contains_every_frame_with_outside_origin(self):
        card = QRectF(-900, 500, 360, 420)
        for star in (QPointF(-1000, 440), QPointF(-350, 1100)):
            bounds = transformed_rect(card, star, 0).united(card)
            for frame in range(23):
                self.assertTrue(bounds.adjusted(-.001, -.001, .001, .001).contains(
                    transformed_rect(card, star, frame / 22)))

    def test_out_of_range_progress_clamps_to_finite_endpoints(self):
        card, star = QRectF(20, 30, 100, 80), QPointF(5, 10)
        self.assertEqual(transformed_rect(card, star, -2), transformed_rect(card, star, 0))
        self.assertEqual(transformed_rect(card, star, 4), card)


class DetailTransitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.card = QWidget(None, Qt.Tool | Qt.FramelessWindowHint)
        self.card.setFixedSize(360, 420)
        self.card.move(500, 300)
        self.card.setStyleSheet('background: #1c2140; color: #f0f3ff;')
        self.button = QPushButton('Collapse', self.card)
        self.button.setGeometry(20, 20, 100, 32)
        self.transition = DetailTransition()
        self.star = QPoint(460, 360)

    def tearDown(self):
        self.transition.shutdown()
        try:
            self.card.close()
            self.card.deleteLater()
        except RuntimeError:
            pass
        self.app.processEvents()

    def finish(self):
        self.transition.animation.setCurrentTime(DURATION_MS)
        self.assertFalse(self.transition.running)

    def test_open_has_immediate_visibility_fixed_layout_and_finite_completion(self):
        finished = []
        geometry = self.card.geometry()
        self.transition.open(self.card, self.star, on_finished=lambda: finished.append('open'))
        self.assertTrue(self.card.isVisible())
        self.assertTrue(self.transition.running)
        self.assertEqual(self.card.windowOpacity(), 0)
        self.assertTrue(self.transition.overlay.isVisible())
        previous = 0
        for stamp in (0, 80, 160):
            self.transition.animation.setCurrentTime(stamp)
            self.assertGreaterEqual(self.transition.overlay.progress, previous)
            previous = self.transition.overlay.progress
            self.assertEqual(self.card.geometry(), geometry)
        self.finish()
        self.assertEqual(self.card.geometry(), geometry)
        self.assertEqual(self.card.windowOpacity(), 1)
        self.assertTrue(self.card.isVisible())
        self.assertFalse(self.transition.overlay.isVisible())
        self.assertTrue(self.transition.overlay.pixmap.isNull())
        self.assertEqual(finished, ['open'])

    def test_close_hides_real_card_immediately_and_finishes_once(self):
        self.card.show()
        completed = []
        self.transition.close(self.card, self.star, on_finished=lambda: completed.append('close'))
        self.assertFalse(self.card.isVisible())
        self.assertTrue(self.transition.running)
        self.assertEqual(self.transition.overlay.progress, 1)
        self.transition.animation.setCurrentTime(80)
        self.assertLess(self.transition.overlay.progress, 1)
        self.finish()
        self.assertFalse(self.card.isVisible())
        self.assertEqual(completed, ['close'])

    def test_reduced_motion_is_immediate_without_overlay_or_animation(self):
        completed = []
        self.transition.open(self.card, self.star, animated=False,
                             on_finished=lambda: completed.append('open'))
        self.assertTrue(self.card.isVisible())
        self.assertFalse(self.transition.running)
        self.assertIsNone(self.transition.overlay)
        self.transition.close(self.card, self.star, animated=False,
                              on_finished=lambda: completed.append('close'))
        self.assertFalse(self.card.isVisible())
        self.assertEqual(completed, ['open', 'close'])

    def test_cancel_restores_original_opacity_without_changing_visibility(self):
        self.card.setWindowOpacity(.7)
        original = self.card.windowOpacity()
        self.transition.open(self.card, self.star)
        self.transition.cancel()
        self.assertTrue(self.card.isVisible())
        self.assertEqual(self.card.windowOpacity(), original)
        self.assertFalse(self.transition.running)
        self.assertTrue(self.transition.overlay.pixmap.isNull())
        self.transition.close(self.card, self.star)
        self.transition.cancel()
        self.assertFalse(self.card.isVisible())
        self.assertEqual(self.card.windowOpacity(), original)

    def test_reverse_close_from_open_retains_current_transform_and_alpha(self):
        self.transition.open(self.card, self.star)
        self.transition.animation.setCurrentTime(80)
        progress = self.transition.overlay.progress
        self.transition.close(self.card, self.star)
        self.assertAlmostEqual(self.transition.overlay.progress, progress)
        self.assertFalse(self.card.isVisible())
        self.finish()

    def test_reverse_open_from_close_retains_current_transform_and_alpha(self):
        self.card.show()
        self.transition.close(self.card, self.star)
        self.transition.animation.setCurrentTime(80)
        progress = self.transition.overlay.progress
        self.transition.open(self.card, self.star)
        self.assertAlmostEqual(self.transition.overlay.progress, progress)
        self.assertTrue(self.card.isVisible())
        self.finish()

    def test_obsolete_frame_and_completion_cannot_mutate_new_transition(self):
        completed = []
        self.transition.open(self.card, self.star, on_finished=lambda: completed.append('old'))
        old_generation = self.transition._generation
        self.transition.cancel()
        self.transition.open(self.card, self.star, on_finished=lambda: completed.append('new'))
        self.transition.animation.setCurrentTime(80)
        progress = self.transition.overlay.progress
        self.transition._frame(old_generation, 1)
        self.transition._finish(old_generation)
        self.assertEqual(self.transition.overlay.progress, progress)
        self.assertEqual(self.card.windowOpacity(), 0)
        self.assertTrue(self.transition.running)
        self.finish()
        self.assertEqual(completed, ['new'])

    def test_caller_hidden_card_never_reshows_at_completion(self):
        self.transition.open(self.card, self.star)
        self.card.hide()
        self.finish()
        self.assertFalse(self.card.isVisible())
        self.assertEqual(self.card.windowOpacity(), 1)

    def test_deleted_card_cancels_overlay_and_callback(self):
        completed = []
        self.transition.open(self.card, self.star, on_finished=lambda: completed.append('stale'))
        self.card.deleteLater()
        self.app.sendPostedEvents(self.card, QEvent.DeferredDelete)
        self.assertFalse(self.transition.running)
        self.assertFalse(self.transition.overlay.isVisible())
        self.assertTrue(self.transition.overlay.pixmap.isNull())
        self.assertEqual(completed, [])

    def test_shutdown_is_terminal_and_drops_snapshot(self):
        completed = []
        self.transition.open(self.card, self.star, on_finished=lambda: completed.append('stale'))
        self.transition.shutdown()
        self.assertFalse(self.transition.running)
        self.assertIsNone(self.transition.overlay)
        self.assertEqual(self.card.windowOpacity(), 1)
        self.card.hide()
        self.transition.open(self.card, self.star)
        self.assertFalse(self.card.isVisible())
        self.assertEqual(completed, [])

    def test_overlay_is_input_transparent_nonactivating_and_mirrors_topmost(self):
        self.transition.open(self.card, self.star)
        layer = self.transition.overlay
        self.assertTrue(layer.windowFlags() & Qt.WindowTransparentForInput)
        self.assertTrue(layer.testAttribute(Qt.WA_TransparentForMouseEvents))
        self.assertTrue(layer.testAttribute(Qt.WA_ShowWithoutActivating))
        self.assertEqual(layer.focusPolicy(), Qt.NoFocus)
        self.assertFalse(layer.windowFlags() & Qt.WindowStaysOnTopHint)
        self.transition.cancel()
        self.card.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.transition.open(self.card, self.star)
        self.assertTrue(layer.windowFlags() & Qt.WindowStaysOnTopHint)

    def test_rapid_operations_reuse_one_layer_and_one_animation(self):
        self.transition.open(self.card, self.star)
        layer, animation = self.transition.overlay, self.transition.animation
        for _ in range(50):
            self.transition.close(self.card, self.star)
            self.transition.open(self.card, self.star)
            self.assertIs(self.transition.overlay, layer)
            self.assertIs(self.transition.animation, animation)
            self.assertEqual(len(self.transition._connections), 3)
        self.finish()
        self.assertEqual(self.transition._connections, [])

    def test_mouse_open_keeps_editor_focus_and_root_can_focus_keyboard_card(self):
        editor = QLineEdit()
        try:
            editor.show()
            editor.activateWindow()
            editor.setFocus()
            self.app.processEvents()
            self.assertIs(self.app.focusWidget(), editor)
            self.transition.open(self.card, self.star)
            self.app.processEvents()
            self.assertIs(self.app.focusWidget(), editor)
            self.card.activateWindow()
            self.button.setFocus(Qt.ShortcutFocusReason)
            self.app.processEvents()
            self.assertIs(self.app.focusWidget(), self.button)
            self.finish()
        finally:
            editor.close()
            editor.deleteLater()


if __name__ == '__main__':
    unittest.main()
