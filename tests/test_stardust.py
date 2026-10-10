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
        self.store = WorkbenchStore(Path(temp.name) / 'workbench.sqlite3')
        self.addCleanup(self.store.close)
        self.panel = FakePanel(self.store)
        self.dust = Stardust(self.panel, clock=lambda: NOW)

    def test_gains_count_once_and_stay_apart_from_points(self):
        self.store.add_points('todo_done', 't1', 2, NOW)
        self.dust.on_finished(finished('a', 30 * 60))          # +3 task, +3 time.
        self.dust.on_finished(finished('a', 30 * 60))          # Same event: nothing.
        self.dust.on_finished(finished('b', 20))               # Under a minute: +1.
        self.dust.gain('star_review', 'todo-7')
        self.assertEqual(self.dust.total(), 3 + 3 + 1 + 8)
        self.assertEqual(self.store.points(), 2)

    def test_time_is_capped_per_day(self):
        self.dust.on_finished(finished('long', 8 * 3600))       # 48 steps, capped at 40.
        self.dust.on_finished(finished('more', 3600))
        self.assertEqual(self.dust.time_today(), stardust.TIME_DAILY_CAP)

    def test_unlocks_fire_once_in_order(self):
        self.assertEqual(next_unlock(0), ('skin_meteor', 150))
        self.dust.gain('star_review', 'x', 149)
        self.assertEqual(self.panel.unlocks, [])
        self.assertEqual(self.dust.gain('star_review', 'y', 300), ['skin_meteor', 'skin_aurora'])
        self.dust.gain('star_review', 'z', 1)
        self.assertEqual(self.panel.unlocks, ['skin_meteor', 'skin_aurora'])
        self.assertEqual(unlocked(1000), ['skin_meteor', 'skin_aurora', 'starsea'])
        self.assertIsNone(next_unlock(1000))

    def test_collection_page_shows_progress_and_unlocked_skins(self):
        from collection_view import CollectionPage
        self.dust.gain('star_review', 'x', 200)
        self.panel.stardust = self.dust
        self.panel.apply_ring_skin = mock.Mock()
        self.panel.persist = mock.Mock()

        class Owner:
            pass
        owner = Owner()
        owner.store, owner.panel = self.store, self.panel
        page = CollectionPage(owner)
        page.apply_language()
        self.assertEqual(page.stardust.text(), 'Stardust 200')
        self.assertEqual((page.stardust_bar.value(), page.stardust_bar.maximum()), (200, 400))
        self.assertIn('200 more', page.stardust_next.text())
        self.assertEqual([page.skin.itemData(i) for i in range(page.skin.count())], ['default', 'meteor'])
        page.skin.setCurrentIndex(1)
        self.assertEqual(self.panel.prefs['ring_skin'], 'meteor')
        self.panel.apply_ring_skin.assert_called()
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
        self.assertEqual(self.panel.stardust.total(), 3 + 1)
        self.panel.stardust.gain('star_review', 'big', 150)
        self.assertEqual((self.panel.prefs['ring_skin'], halo_scene.SKIN), ('meteor', 'meteor'))

    def test_starsea_form_after_unlock_and_only_when_chosen(self):
        from pet import DesktopPet
        import starsea
        pet = DesktopPet(self.panel)
        self.panel.pet = pet
        pet.activity_timer.stop()
        self.addCleanup(pet.close)
        self.assertFalse(self.panel.starsea.available())          # Not unlocked yet.
        self.panel.stardust.gain('star_review', 'big', 1000)
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
