"""2.1 game mode: switching, quiet tasks, her place, the ring and the compact display."""
import unittest
from types import SimpleNamespace

from PySide6.QtWidgets import QApplication

import game_mode
from game_mode import GameMode, names

APP = QApplication.instance() or QApplication([])


class FakeDetector:
    def __init__(self):
        self.playing = False
        self.calls = []

    def poll(self, now, extra=(), excluded=()):
        self.calls.append((extra, excluded))
        return self.playing


class FakePanel(SimpleNamespace):
    pass


class GameModeTests(unittest.TestCase):
    def setUp(self):
        from PySide6.QtCore import QObject
        self.panel = QObject()
        self.panel.prefs = dict(game_extra='EldenRing, D:/games/my.exe', game_excluded='vlc')
        self.detector = FakeDetector()
        self.mode = GameMode(self.panel, detector=self.detector, clock=lambda: 0)
        self.seen = []
        self.mode.changed.connect(self.seen.append)

    def test_follows_detection_and_passes_the_user_lists(self):
        self.mode.poll()
        self.assertFalse(self.mode.active)
        self.detector.playing = True
        self.mode.poll()
        self.assertTrue(self.mode.active)
        self.assertTrue(self.mode.quiet('finished'))
        self.assertEqual(self.detector.calls[-1], (('eldenring.exe', 'my.exe'), ('vlc.exe',)))
        self.detector.playing = False
        self.mode.poll()
        self.assertEqual(self.seen, [True, False])

    def test_switching_off_during_a_game_lasts_until_it_ends(self):
        self.detector.playing = True
        self.mode.poll()
        self.mode.toggle()                       # Off by hand.
        self.mode.poll()
        self.assertFalse(self.mode.active)       # Still off while the game runs.
        self.detector.playing = False
        self.mode.poll()                         # The game ended...
        self.detector.playing = True
        self.mode.poll()                         # ...and the next one turns it on again.
        self.assertTrue(self.mode.active)

    def test_switching_on_by_hand_without_a_game(self):
        self.mode.toggle()
        self.mode.poll()
        self.assertTrue(self.mode.active)
        self.mode.toggle()
        self.mode.poll()
        self.assertFalse(self.mode.active)

    def test_no_detection_when_turned_off(self):
        self.panel.prefs['game_auto'] = False
        self.detector.playing = True
        self.mode.poll()
        self.assertFalse(self.mode.active)
        self.assertEqual(self.detector.calls, [])

    def test_settings_with_safe_fallbacks(self):
        self.assertEqual((self.mode.display, self.mode.ring_style), ('rings', 'tasks'))
        self.panel.prefs.update(game_display='bogus', game_ring='space', game_bar_items=['gpu', 'nope'])
        self.assertEqual((self.mode.display, self.mode.ring_style, self.mode.bar_items), ('rings', 'space', ['gpu']))
        self.assertEqual(names('a.exe; b'), ('a.exe', 'b.exe'))
        self.assertEqual(names(['A.EXE', 'a.exe']), ('a.exe',))


class PanelGameModeTests(unittest.TestCase):
    """The real panel and pet (non-live): quiet notices, ring, display, place."""

    @classmethod
    def setUpClass(cls):
        from widget import Panel
        from pet import DesktopPet
        cls.panel = Panel(live=False)
        cls.panel.pet = DesktopPet(cls.panel)

    @classmethod
    def tearDownClass(cls):
        cls.panel.pet.close()
        cls.panel.closing = True
        cls.panel.close()

    def test_game_mode_end_to_end(self):
        panel, pet = self.panel, self.panel.pet
        pet.show()
        reactions = []
        original = pet.react
        pet.react = lambda kind, event=None: reactions.append(kind)
        try:
            panel.game_mode.toggle()
            self.assertTrue(panel.game_mode.active)
            self.assertTrue(panel.tray_actions['game_mode_menu'].isChecked())
            self.assertFalse(pet.usage_overlay_wanted())            # The compact display instead.
            pet.sync_game()
            self.assertTrue(pet.game_halo.isVisible())
            self.assertTrue(pet.game_halo.space)                     # No tasks: deep-space ring.
            self.assertTrue(pet.game_usage.isVisible())
            panel.announce(dict(kind='finished', provider='claude'))
            self.assertEqual(reactions, [])                          # Quiet while gaming.
            # A task starting during the game must not bring the usual ring back.
            from tests import test_ui as ui
            panel.task_manager.apply_snapshot([ui._codex_entry('new-in-game')], preference='auto',
                                              language='en', pet_rect=ui._CENTER_PET_RECT,
                                              screen_rect=ui._SCREEN_RECT)
            self.assertFalse(panel.task_manager._visible)
            self.assertFalse(any(orb.isVisible() for orb in panel.task_manager._windows.values()))
            panel.prefs['game_display'] = 'hidden'
            pet.sync_game()
            self.assertFalse(pet.game_usage.isVisible())
            panel.game_mode.toggle()
            self.assertFalse(panel.game_mode.active)
            self.assertFalse(pet.game_halo.isVisible())
            panel.announce(dict(kind='finished', provider='claude'))
            self.assertEqual(reactions, ['finished'])
        finally:
            pet.react = original
            panel.prefs['game_display'] = 'rings'
            pet.hide()

    def test_long_press_drags_her_and_the_bar_while_clicks_pass(self):
        from PySide6.QtCore import QPoint
        pet = self.panel.pet
        pet.show()
        state = dict(down=False, at=QPoint(0, 0), now=0.0)
        drag = game_mode.LongPressDrag(pet, button=lambda: state['down'], cursor=lambda: state['at'],
                                       clock=lambda: state['now'])
        drag._was_down = False
        box = pet.frameGeometry()
        inside = QPoint(box.center().x(), box.bottom() - 20)
        start = pet.pos()

        def step(down, at, dt):
            state.update(down=down, at=at, now=state['now'] + dt)
            drag.tick()
        # A click: nothing moves.
        step(True, inside, 0)
        step(False, inside, .1)
        self.assertEqual(pet.pos(), start)
        # A press that moves at once is a drag inside the game: ignored.
        step(True, inside, 0)
        step(True, inside + QPoint(40, 0), .1)
        step(True, inside + QPoint(80, 0), .6)
        self.assertEqual(pet.pos(), start)
        step(False, inside, .1)
        # Hold half a second, then move: she follows.
        step(True, inside, 0)
        step(True, inside, .6)
        self.assertTrue(pet.dragging)
        step(True, inside + QPoint(-60, -30), .02)
        self.assertEqual(pet.pos(), start + QPoint(-60, -30))
        step(False, inside, .02)
        self.assertFalse(pet.dragging)
        pet.move(start)
        # The bar, once dragged, stays where it was put.
        usage = game_mode.GameUsage(pet)
        usage.set_content('bar', [], dict(cpu=5.0), ['cpu'], 'en')
        usage.show()
        drag.pet.game_usage = usage
        grab = usage.frameGeometry().center()
        step(True, grab, 0)
        step(True, grab, .6)
        step(True, grab + QPoint(100, 50), .02)
        step(False, grab, .02)
        self.assertEqual(self.panel.prefs['game_bar_pos'], [usage.x(), usage.y()])
        pet.move(pet.pos() + QPoint(30, 0))
        usage.follow()
        self.assertEqual([usage.x(), usage.y()], self.panel.prefs['game_bar_pos'])   # Didn't follow her.
        self.panel.prefs['game_bar_pos'] = None
        drag.pet.game_usage = None
        usage.deleteLater()
        pet.hide()

    def test_a_right_click_on_her_opens_her_menu_in_game_mode(self):
        from PySide6.QtCore import QPoint
        pet = self.panel.pet
        pet.show()
        state = dict(right=False, at=QPoint(0, 0))
        drag = game_mode.LongPressDrag(pet, button=lambda: False, cursor=lambda: state['at'],
                                       right=lambda: state['right'])
        box = pet.frameGeometry()
        on_her = QPoint(box.center().x(), box.bottom() - 20)
        for right in (True, False):
            state.update(right=right, at=on_her)
            drag.tick()
        self.assertTrue(drag.menu.isVisible())
        drag.menu.close()
        drag.menu = None
        away = QPoint(box.left() - 200, box.top())       # Elsewhere: the game's own right click.
        for right in (True, False):
            state.update(right=right, at=away)
            drag.tick()
        self.assertIsNone(drag.menu)
        pet.hide()

    def test_rings_go_left_or_right(self):
        pet = self.panel.pet
        usage = game_mode.GameUsage(pet)
        usage.set_content('rings', [dict(provider='claude', name='Claude Code',
                                         rows=[dict(kind='five', remaining=50), dict(kind='week', remaining=50)])],
                          None, [], 'en')
        right = usage.x()
        self.panel.prefs['game_rings_side'] = 'left'
        usage.follow()
        self.assertLess(usage.x(), right)
        self.assertLessEqual(usage.x() + usage.width(), pet.x() + pet.width() // 2)
        self.panel.prefs['game_rings_side'] = 'right'
        usage.deleteLater()

    def test_compact_display_content(self):
        import time
        import usage_overlay as uo
        pet = self.panel.pet
        now = time.time()
        limits = dict(primary=dict(windowDurationMins=300, usedPercent=64, resetsAt=now + 900),
                      secondary=dict(windowDurationMins=10080, usedPercent=90, resetsAt=now + 86400))
        sections = [uo.provider_section('claude', limits, None, '', 'en', now)]
        usage = game_mode.GameUsage(pet)
        usage.set_content('rings', sections, None, [], 'en')
        self.assertEqual(usage.cells, [('claude', 'five', 36), ('claude', 'week', 10)])
        usage.set_content('bar', sections, dict(cpu=12.0, gpu=None, gpu_temp=88.0),
                          ['limits', 'cpu', 'gpu', 'gpu_temp'], 'en')
        self.assertEqual(usage.items[0], ('Claude Code', '5h 36%  Week 10%', True))
        self.assertEqual(usage.items[1:], [('CPU', '12%', False), ('GPU', 'N/A', False),
                                           ('GPU temp', '88°C', True)])
        image = usage.grab().toImage()
        self.assertGreater(image.width(), 100)
        usage.deleteLater()


if __name__ == '__main__':
    unittest.main()
