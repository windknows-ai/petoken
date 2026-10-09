"""2.1 game mode: switching, quiet tasks, her place, the ring and the compact display."""
import unittest
from types import SimpleNamespace

from PySide6.QtWidgets import QApplication

import game_mode
from game_mode import GameMode, names

APP = QApplication.instance() or QApplication([])


def all_actions(menu):
    """A menu's actions, its submenus' included."""
    for action in menu.actions():
        yield action
        if action.menu() is not None:
            yield from all_actions(action.menu())


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
        from unittest.mock import patch
        from widget import Panel
        from pet import DesktopPet
        # These tests are about the switching, not the animation (tests/test_transform.py):
        # whether the art happens to be prepared by earlier tests must not matter.
        cls.no_animation = patch('transform.available', return_value=False)
        cls.no_animation.start()
        cls.panel = Panel(live=False)
        cls.panel.pet = DesktopPet(cls.panel)

    def tearDown(self):
        if self.panel.game_mode.active:          # A failed test must not leave it on for the next.
            self.panel.game_mode.toggle()

    @classmethod
    def tearDownClass(cls):
        cls.no_animation.stop()
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

    def test_right_clicks_never_stack_menus(self):
        from PySide6.QtCore import QPoint
        pet = self.panel.pet
        pet.show()
        state = dict(right=False)
        box = pet.frameGeometry()
        on_her = QPoint(box.center().x(), box.bottom() - 20)
        drag = game_mode.LongPressDrag(pet, button=lambda: False, cursor=lambda: on_her,
                                       right=lambda: state['right'])

        def right_click():
            for down in (True, False):
                state['right'] = down
                drag.tick()
        right_click()
        first = drag.menu
        self.assertTrue(first.isVisible())
        self.assertTrue(first.windowFlags() & __import__('PySide6.QtCore', fromlist=['Qt']).Qt.WindowStaysOnTopHint)
        right_click()                              # Again: closes it, opens nothing new.
        self.assertIsNone(drag.menu)
        right_click()                              # And again: one fresh menu.
        self.assertIsNotNone(drag.menu)
        drag.menu.close()
        pet.hide()

    def test_stars_fly_between_the_rings(self):
        from PySide6.QtCore import QPointF
        done, frames = [], []
        flight = game_mode.StarFlight(lambda: [('claude', QPointF(100, 100)), ('codex', QPointF(200, 120))],
                                      lambda: [('claude', QPointF(300, 300)), ('codex', QPointF(320, 340))],
                                      on_frame=frames.append, on_done=lambda: done.append(1))
        flight.start()
        flight._tick()
        flight.t = flight.DURATION
        flight._tick()
        self.assertEqual(done, [1])
        self.assertEqual(frames[-1], 1.0)
        matched = type(self.panel)._match_stars([('codex', 1), ('claude', 2)], providers=['claude', 'codex'])
        self.assertEqual(matched, [('claude', 2), ('codex', 1)])

    def test_rings_go_left_or_right(self):
        pet = self.panel.pet
        area = (pet.screen() or APP.primaryScreen()).availableGeometry()
        pet.move(area.center() - pet.rect().center())          # Room on both sides.
        self.panel.prefs['game_rings_side'] = 'right'
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

    def test_menu_puts_everyday_actions_first_and_switches_under_show(self):
        pet = self.panel.pet
        menu = pet.context_menu()
        top = [a.text() for a in menu.actions() if not a.isSeparator()]
        self.assertEqual(top[0], pet.tr_text('launch_menu'))
        view = next(a.menu() for a in menu.actions() if a.text() == pet.tr_text('menu_view'))
        inside = [a.text() for a in view.actions()]
        for key in ('usage_panel', 'usage_card_menu', 'game_mode_menu', 'always_on_top', 'idle_motion'):
            self.assertIn(pet.tr_text(key), inside)
            self.assertNotIn(pet.tr_text(key), top)
        menu.deleteLater()
        self.panel.game_mode.toggle()                              # In a game: the way out comes first.
        menu = pet.context_menu()
        self.assertEqual(menu.actions()[0].text(), pet.tr_text('game_mode_leave'))
        menu.actions()[0].trigger()
        self.assertFalse(self.panel.game_mode.active)
        menu.deleteLater()

    def test_whitelist_and_blacklist_take_picked_programs(self):
        from widget import Settings
        self.panel.prefs['game_extra'] = 'old.exe, other'                 # A 2.1 test-build value.
        settings = Settings(self.panel)
        self.assertEqual(settings.game_extra.values(), ['old.exe', 'other.exe'])
        settings.game_extra.pick([r'D:/Games/Elden Ring/eldenring.exe', r'D:/Games/old.exe'])   # Duplicate ignored.
        self.assertEqual(settings.game_extra.values(), ['old.exe', 'other.exe', 'eldenring.exe'])
        settings.game_extra.listing.setCurrentRow(0)
        settings.game_extra.remove_selected()
        settings.game_excluded.pick([r'C:\Program Files\VLC\vlc.exe'])
        with __import__('unittest.mock', fromlist=['patch']).patch('widget.write_preferences'):
            settings.save()
        self.assertEqual(self.panel.prefs['game_extra'], ['other.exe', 'eldenring.exe'])
        self.assertEqual(self.panel.prefs['game_excluded'], ['vlc.exe'])
        self.assertEqual(game_mode.names(self.panel.prefs['game_extra']), ('other.exe', 'eldenring.exe'))
        settings.close()

    def test_settings_show_only_what_matters_for_the_choice(self):
        from widget import Settings
        settings = Settings(self.panel)
        settings.show()
        rings, bar = settings._card_of(settings.game_rings_side_label), settings._card_of(settings.game_bar_label)
        settings.game_display.setCurrentIndex(settings.game_display.findData('rings'))
        self.assertTrue(rings.isVisibleTo(settings) or not settings.tabs.currentIndex() == 4)
        self.assertFalse(bar.isVisibleTo(settings))
        settings.game_display.setCurrentIndex(settings.game_display.findData('bar'))
        self.assertFalse(rings.isVisibleTo(settings))
        settings.game_auto.setChecked(False)
        self.assertFalse(settings._card_of(settings.game_extra_label).isVisibleTo(settings))
        settings.dnd_scheduled.setChecked(False)
        self.assertFalse(settings.dnd_start.isEnabled())
        settings.close()

    def test_the_menu_item_switches_game_mode(self):
        pet = self.panel.pet
        for expected in (True, False):
            menu = pet.context_menu()
            action = next(a for a in all_actions(menu) if a.text() == pet.tr_text('game_mode_menu'))
            self.assertEqual(action.isChecked(), not expected)
            action.trigger()
            self.assertEqual(self.panel.game_mode.active, expected)
            menu.deleteLater()

    def test_game_moods_come_and_go(self):
        from unittest.mock import patch
        pet = self.panel.pet
        for name in ('_game_mood', '_game_next'):
            if hasattr(pet, name):
                delattr(pet, name)
        with patch('pet_assets.has_own_art', return_value=True), patch('random.uniform', return_value=60), \
                patch('random.choices', return_value=[('game_drink', 2, 6)]):
            self.assertIn(pet._game_pose(0), ('form2_idle', 'idle'))      # She starts on guard...
            self.assertIn(pet._game_pose(59), ('form2_idle', 'idle'))
            self.assertEqual(pet._game_pose(61), 'game_drink')             # ...then a mood...
            self.assertEqual(pet._game_pose(66), 'game_drink')
            self.assertIn(pet._game_pose(68), ('form2_idle', 'idle'))     # ...and back on guard.

    def test_v2_1_art_can_live_outside_the_repository(self):
        import os
        from unittest.mock import patch
        import pet_assets
        with patch.object(pet_assets, 'ASSETS_DIR', pet_assets.ASSETS_DIR.parent / 'no-assets-here'), \
                patch.dict(os.environ, PETOKEN_V2_1_ART='D:/art'):
            self.assertEqual(pet_assets._file('assets/v2_1/form2_idle_1.png').as_posix(), 'D:/art/form2_idle_1.png')
            self.assertTrue(pet_assets._file('assets/v2_0/idle_1.png').as_posix().endswith('assets/v2_0/idle_1.png'))

    def test_windows_that_lost_always_on_top_get_it_back(self):
        pet = self.panel.pet
        pet.show()
        lost = int(pet.winId())
        repaired = []
        count = self.panel.keep_on_top(
            get_style=lambda hwnd: 0 if hwnd == lost else 0x8,      # Only her window lost it.
            set_position=repaired.append)
        self.assertEqual((count, repaired), (1, [lost]))
        self.assertEqual(self.panel.keep_on_top(get_style=lambda hwnd: 0x8, set_position=repaired.append), 0)
        pet.hide()

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
