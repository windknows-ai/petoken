"""2.4 stardust: gains, the daily time cap, unlocks, ring skins and the Collection page."""
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

from PySide6.QtWidgets import QApplication

import halo_scene
import stardust
from stardust import Stardust, next_unlock, unlocked
from workbench_store import WorkbenchStore

APP = QApplication.instance() or QApplication([])
NOW = datetime(2026, 10, 10, 15, 0).timestamp()


class FakePanel:
    def __init__(self, store):
        self.store = store
        self.prefs = dict(language='en')
        self.unlocks = []

    def workbench_store(self):
        return self.store

    def stardust_unlocked(self, name):
        self.unlocks.append(name)


def finished(key, seconds=None, at=NOW):
    detail = json.dumps(dict(seconds=seconds)) if seconds is not None else ''
    return dict(kind='finished', provider='claude', task_key=key, at=at, detail=detail)


class StardustTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.store_path = Path(temp.name) / 'workbench.sqlite3'
        self.store = WorkbenchStore(self.store_path)
        self.addCleanup(self.store.close)
        self.panel = FakePanel(self.store)
        self.dust = Stardust(self.panel, clock=lambda: NOW)

    def test_gains_count_once_and_stay_apart_from_points(self):
        self.store.add_points('todo_done', 't1', 2, NOW)
        self.dust.on_finished(finished('a', 30 * 60))          # +10 task, +10 time.
        self.dust.on_finished(finished('a', 30 * 60))          # Same event: nothing.
        self.dust.on_finished(finished('b', 20))               # Under a minute: +4.
        self.dust.gain('star_review', 'todo-7')
        self.assertEqual(self.dust.total(), 10 + 10 + 4 + 24)
        self.assertEqual(self.store.points(), 2)

    def test_time_is_capped_per_day(self):
        self.dust.on_finished(finished('long', 8 * 3600))       # 160 steps, capped at 120.
        self.dust.on_finished(finished('more', 3600))
        self.assertEqual(self.dust.time_today(), stardust.TIME_DAILY_CAP)

    def test_work_earns_at_most_the_daily_cap(self):
        for n in range(40):                                   # A very heavy day.
            self.dust.on_finished(finished(f'w{n}', 40 * 60))
            self.dust.gain('star_review', f'r{n}')
        self.assertEqual(self.dust.work_today(), stardust.WORK_DAILY_CAP)
        self.dust.gain('star_signin', 'today', 10)              # Sign-in comes on top.
        self.assertEqual(self.dust.total(), stardust.WORK_DAILY_CAP + 10)
        self.dust.on_running()                                  # So does running time.
        self.assertEqual(self.dust.total(), stardust.WORK_DAILY_CAP + 20)

    def test_every_five_minutes_running_gives_ten_once(self):
        now = [NOW]
        dust = Stardust(self.panel, clock=lambda: now[0])
        dust.on_running()
        dust.on_running()                                       # The same five minutes: nothing more.
        now[0] += stardust.RUNNING_STEP_S
        dust.on_running()
        self.assertEqual(dust.total(), 20)
        self.assertEqual(stardust.RUNNING_STEP_S, 300)

    def test_unlocks_fire_once_in_order(self):
        self.assertEqual(next_unlock(0), ('skin_meteor', 150))
        self.dust.gain('star_gift', 'x', 149)
        self.assertEqual(self.panel.unlocks, [])
        self.assertEqual(self.dust.gain('star_gift', 'y', 300), ['skin_meteor', 'skin_aurora'])
        self.dust.gain('star_gift', 'z', 1)
        self.assertEqual(self.panel.unlocks, ['skin_meteor', 'skin_aurora'])
        self.assertEqual(unlocked(1000), ['skin_meteor', 'skin_aurora', 'starsea'])
        self.assertIsNone(next_unlock(1000))

    def test_wardrobe_milestones_show_progress_and_unlocked_skins(self):
        import random
        from shop import Shop
        from wardrobe import Wardrobe
        self.dust.gain('star_gift', 'x', 200)
        self.panel.stardust = self.dust
        self.panel.apply_ring_skin = mock.Mock()
        self.panel.persist = mock.Mock()
        self.panel.shop = Shop(self.panel, self.store_path.parent / 'shop.json', rng=random.Random(1))
        page = Wardrobe(self.panel)
        bridge = page.bridge
        self.assertEqual(bridge.milestone['totalText'], 'Stardust 200')
        self.assertAlmostEqual(bridge.milestone['fraction'], 200 / 400)
        self.assertIn('200 more', bridge.milestone['nextText'])
        self.assertIn('+24', bridge.milestone['earnText'])
        cards = {c['key']: c for c in bridge.skins}
        self.assertEqual([k for k, c in cards.items() if c['unlocked']], ['default', 'meteor'])
        self.assertEqual(cards['aurora']['caption'], 'Unlocks at 400')
        self.assertTrue(cards['default']['current'])
        bridge.chooseSkin('meteor')
        self.assertEqual(self.panel.prefs['ring_skin'], 'meteor')
        self.panel.apply_ring_skin.assert_called()
        self.assertTrue({c['key']: c for c in bridge.skins}['meteor']['current'])
        import wardrobe
        picture = wardrobe.skin_scene('meteor', 444, 324)
        self.assertEqual((picture.width(), picture.height()), (444, 324))
        self.assertGreater(picture.pixelColor(222, 200).alpha(), 0)
        page.deleteLater()


class PanelStardustTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.pref_patch = mock.patch('widget.PREF_DIR', Path(self.temp.name))
        self.pref_patch.start()
        from widget import Panel
        self.panel = Panel(live=False)
        self.store = WorkbenchStore(Path(self.temp.name) / 'workbench.sqlite3')
        self.panel.workbench_store = lambda: self.store      # Tests have no live database.

    def tearDown(self):
        halo_scene.SKIN = 'default'
        self.store.close()
        self.panel.focus_mode.abandon()
        self.panel.tray.hide()
        self.panel.closing = True
        self.panel.close()
        self.panel.deleteLater()
        APP.processEvents()
        self.pref_patch.stop()
        self.temp.cleanup()

    def test_unlock_puts_the_skin_on_and_finished_events_add_stardust(self):
        self.panel.prefs['ring_skin'] = 'aurora'
        self.panel.apply_ring_skin()
        self.assertEqual(halo_scene.SKIN, 'default')          # Not unlocked yet.
        self.panel.announce(finished('k1', 15 * 60))
        self.assertEqual(self.panel.stardust.total(), 10 + 5)
        self.panel.stardust.gain('star_gift', 'big', 150)
        self.assertEqual((self.panel.prefs['ring_skin'], halo_scene.SKIN), ('meteor', 'meteor'))

    def test_starsea_form_after_unlock_and_only_when_chosen(self):
        from pet import DesktopPet
        import starsea
        pet = DesktopPet(self.panel)
        self.panel.pet = pet
        pet.activity_timer.stop()
        self.addCleanup(pet.close)
        self.assertFalse(self.panel.starsea.available())          # Not unlocked yet.
        self.panel.stardust.gain('star_gift', 'big', 1000)
        self.assertTrue(self.panel.starsea.available())
        self.assertFalse(self.panel.starsea.active)               # Never put on by itself.
        self.assertTrue(self.panel.starsea.toggle())
        self.assertEqual(self.panel.prefs['pet_form'], 'starsea')
        pet.update_activity()
        self.assertEqual(pet.current_state, 'star_idle')
        self.assertEqual(self.panel.starsea.pose('typing'), 'star_typing')
        self.assertEqual(self.panel.starsea.pose('night_read'), 'night_read')   # Pajamas win.
        self.assertEqual(self.panel.starsea.pose('form2_idle'), 'form2_idle')   # So does game mode.
        self.assertEqual(starsea.awaken_steps(False)[0][0], 'awaken_4')
        self.assertFalse(self.panel.starsea.toggle())
        pet.update_activity()
        self.assertEqual(pet.current_state, 'idle')

    def test_accepted_review_also_gives_stardust(self):
        self.panel.companion.award('todo_accepted', 'todo-1')
        self.assertEqual(self.panel.stardust.total(), stardust.GAINS['star_review'])


if __name__ == '__main__':
    unittest.main()
