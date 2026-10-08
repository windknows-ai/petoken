"""Every pose has a trigger, and the workbench Guide explains them and the clinginess levels."""
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

import pet_assets as assets
import pose_guide
from localization import ZH_CN, EN
from notifications import recap_detail

APP = QApplication.instance() or QApplication([])


class PoseGuideTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.pref_patch = patch('widget.PREF_DIR', Path(self.temp.name))
        self.pref_patch.start()
        from widget import Panel
        from pet import DesktopPet
        self.panel = Panel(live=False)
        self.pet = DesktopPet(self.panel)
        self.panel.pet = self.pet
        self.pet.activity_timer.stop()
        self.pet.timer.stop()

    def tearDown(self):
        self.panel.focus_mode.abandon()
        self.panel.tray.hide()
        self.pet.close()
        self.panel.closing = True
        self.panel.close()
        self.panel.deleteLater()
        APP.processEvents()
        self.pref_patch.stop()
        self.temp.cleanup()

    def test_guide_lists_every_pose_with_text_and_a_show_button(self):
        listed = [s for _group, states in pose_guide.GROUPS for s in states]
        game = {entry.state for entry in assets.GAME_REGISTRY} | set(pose_guide.SPECIAL)
        self.assertEqual(set(listed), set(assets.registered_states()) | set(assets.companion_states()) | game)
        for state in listed:
            for table in (ZH_CN, EN):
                self.assertIn(f'pose_name_{state}', table)
                self.assertIn(f'pose_when_{state}', table)
        guide = pose_guide.GuidePage(self.panel)
        guide.apply_language()
        self.assertEqual(len(guide.show_buttons), len(listed))
        guide.show_buttons['sleep'].click()
        self.assertEqual(self.pet.current_state, 'sleep')
        guide.show_buttons['transform'].click()                  # Enters game mode to watch it.
        self.assertTrue(self.panel.game_mode.active)
        self.panel.game_mode.toggle()
        guide.deleteLater()

    def test_levels_explained_and_switchable(self):
        for level in pose_guide.LEVELS:
            self.assertIn(f'guide_level_{level}', ZH_CN)
            self.assertIn(f'guide_level_{level}', EN)
        guide = pose_guide.GuidePage(self.panel)
        guide.apply_language()
        self.assertFalse(guide.level_buttons['moderate'].isEnabled())     # In use.
        guide.level_buttons['clingy'].click()
        self.assertEqual(self.panel.prefs['clinginess'], 'clingy')
        self.assertEqual(self.pet.mood.clinginess, 'clingy')
        self.assertFalse(guide.level_buttons['clingy'].isEnabled())
        self.assertTrue(guide.level_buttons['moderate'].isEnabled())
        guide.deleteLater()

    def test_guide_is_a_workbench_tab(self):
        from workbench import WorkbenchWindow
        from workbench_store import WorkbenchStore
        self.panel.prefs['language'] = 'en'
        store = WorkbenchStore(Path(self.temp.name) / 'w.sqlite3')
        window = WorkbenchWindow(self.panel, store)
        self.assertIs(window.tabs.widget(window.guide_tab), window.guide_page)
        self.assertEqual(window.tabs.tabText(window.guide_tab), 'Guide')
        window.shutdown()
        window.deleteLater()

    def test_new_triggers(self):
        quick = dict(kind='finished', detail=recap_detail(dict(files=[], duration_s=30, usd=None)))
        slow = dict(kind='finished', detail=recap_detail(dict(files=[], duration_s=600, usd=None)))
        self.pet.react('finished', quick)
        self.assertEqual(self.pet.current_state, 'surprised')
        self.pet.react('finished', slow)
        first = self.pet.current_state
        self.pet.react('finished', slow)
        self.assertEqual({first, self.pet.current_state}, {'celebrate', 'thumbs_up'})
        self.pet.reaction_state = None
        self.panel._approval_requested(dict(tool='AskUserQuestion'))
        self.assertEqual(self.pet.current_state, 'thinking')
        self.pet.reaction_state = None
        self.panel.start_focus(25)
        self.assertEqual(self.pet.current_state, 'cheer')
        self.panel.focus_mode.abandon()
        self.pet.interaction_state = None
        self.pet.panel.activity.state.stable['music'] = True
        self.pet.panel.activity.state.sampled = time.monotonic()
        with patch('pet.time.time', return_value=120 * 3):
            self.pet.update_activity()
        self.assertEqual(self.pet.current_state, 'guitar')


if __name__ == '__main__':
    unittest.main()
