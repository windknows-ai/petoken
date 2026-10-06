"""2.0 interactions: head pat, poke, long press, drag, and the animated paint path."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QImage, QMouseEvent
from PySide6.QtWidgets import QApplication

import pet_geometry as geometry
from pet import DesktopPet
from widget import Panel


class PetInteractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.pref_dir = Path(self.temp.name)
        self.pref_patch = patch('widget.PREF_DIR', self.pref_dir)
        self.pref_patch.start()
        self.panel = Panel(live=False)
        self.pet = DesktopPet(self.panel)
        self.panel.pet = self.pet
        self.pet.activity_timer.stop()
        self.pet.timer.stop()
        self.pet.show()

    def tearDown(self):
        self.panel.tray.hide()
        self.pet.close()
        self.panel.closing = True
        self.panel.close()
        self.panel.deleteLater()
        self.app.processEvents()
        self.pref_patch.stop()
        self.temp.cleanup()

    def mouse(self, kind, local, buttons=Qt.LeftButton, button=Qt.LeftButton):
        local = QPointF(local)
        event = QMouseEvent(kind, local, QPointF(self.pet.mapToGlobal(local.toPoint())),
                            button, buttons, Qt.NoModifier)
        {QEvent.MouseButtonPress: self.pet.mousePressEvent,
         QEvent.MouseButtonRelease: self.pet.mouseReleaseEvent,
         QEvent.MouseMove: self.pet.mouseMoveEvent}[kind](event)

    def head(self, fx):
        sx, sy, sw, sh = geometry.scaled_sprite_rect(self.pet.pet_scale)
        return QPoint(round(sx + fx * sw), round(sy + .2 * sh))

    def test_rubbing_the_head_is_a_pat(self):
        clock = [100.0]
        with patch('pet.time.monotonic', side_effect=lambda: clock[0]):
            for n in range(8):
                clock[0] += .1
                self.mouse(QEvent.MouseMove, self.head(.35 if n % 2 else .6), Qt.NoButton, Qt.NoButton)
        self.assertEqual(self.pet.current_state, 'headpat_happy')

    def test_poke_opens_panel_and_too_many_pokes_pout(self):
        local = QPoint(136, 260)
        with patch.object(self.pet, 'toggle_panel') as toggle:
            self.mouse(QEvent.MouseButtonPress, local)
            self.mouse(QEvent.MouseButtonRelease, local, Qt.NoButton)
            self.assertEqual(self.pet.current_state, 'poked')
            for _ in range(3):
                self.mouse(QEvent.MouseButtonPress, local)
                self.mouse(QEvent.MouseButtonRelease, local, Qt.NoButton)
            self.assertEqual(self.pet.current_state, 'poked')   # Four clicks: still fine.
            self.mouse(QEvent.MouseButtonPress, local)
            self.mouse(QEvent.MouseButtonRelease, local, Qt.NoButton)
        self.assertEqual(toggle.call_count, 5)
        self.assertEqual(self.pet.current_state, 'pout')

    def test_long_press_acts_cute_without_opening_the_panel(self):
        local = QPoint(136, 200)
        with patch.object(self.pet, 'toggle_panel') as toggle:
            self.mouse(QEvent.MouseButtonPress, local)
            self.assertTrue(self.pet.long_press.isActive())
            self.pet.long_press.stop()
            self.pet._long_pressed()
            self.assertEqual(self.pet.current_state, 'coquettish')
            self.mouse(QEvent.MouseButtonRelease, local, Qt.NoButton)
        toggle.assert_not_called()

    def test_drag_shows_dragged_then_lands(self):
        start = QPoint(136, 120)
        with patch.object(self.panel, 'persist'):
            self.mouse(QEvent.MouseButtonPress, start)
            self.mouse(QEvent.MouseMove, start + QPoint(30, 0))
            self.assertTrue(self.pet.dragging)
            self.assertEqual(self.pet.current_state, 'dragged')
            self.assertTrue(self.pet.animator.dragging)
            self.mouse(QEvent.MouseButtonRelease, start + QPoint(30, 0), Qt.NoButton)
        self.assertFalse(self.pet.dragging)
        self.assertEqual(self.pet.current_state, 'landing')
        # Dragging her around a lot never makes her pout.
        with patch.object(self.panel, 'persist'):
            for _ in range(5):
                self.mouse(QEvent.MouseButtonPress, start)
                self.mouse(QEvent.MouseMove, start + QPoint(40, 0))
                self.mouse(QEvent.MouseButtonRelease, start + QPoint(40, 0), Qt.NoButton)
        self.assertEqual(self.pet.current_state, 'landing')

    def test_mood_stays_off_outside_the_live_app(self):
        self.assertFalse(self.pet.mood_enabled)
        self.pet.mood.pose = 'sleep'
        self.pet.update_activity()
        self.assertEqual(self.pet.current_state, 'idle')

    def test_animated_frames_paint_inside_the_window(self):
        for state in ('idle', 'celebrate', 'sleep', 'headpat_happy', 'dragged'):
            self.pet.current_state = state
            for n in range(12):
                self.pet.tick()
            image = QImage(self.pet.size(), QImage.Format_ARGB32_Premultiplied)
            image.fill(0)
            self.pet.render(image)
            self.assertIsNotNone(self.pet.frame)
            self.assertEqual(self.pet.frame.state, state)
            # Something was drawn, and the motion stays small.
            self.assertGreater(image.pixelColor(136, 220).alpha() + image.pixelColor(136, 160).alpha(), 0, state)
            self.assertLess(abs(self.pet.frame.angle), 8)

    def test_clinginess_setting_reaches_the_mood(self):
        from widget import Settings
        settings = Settings(self.panel)
        settings.clinginess.setCurrentIndex(settings.clinginess.findData('clingy'))
        with patch('widget.write_preferences'):
            settings.save()
        self.assertEqual(self.panel.prefs['clinginess'], 'clingy')
        self.assertEqual(self.pet.mood.clinginess, 'clingy')
        settings.deleteLater()


if __name__ == '__main__':
    unittest.main()
