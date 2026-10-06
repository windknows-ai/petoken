"""Every pose has a trigger, and the guide in Settings lists them all."""
import tempfile
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
        self.assertEqual(set(listed), set(assets.registered_states()) | set(assets.companion_states()))
        for state in listed:
            for table in (ZH_CN, EN):
                self.assertIn(f'pose_name_{state}', table)
                self.assertIn(f'pose_when_{state}', table)
        guide = pose_guide.PoseGuide(None, self.panel)
        self.assertEqual(len(guide.show_buttons), len(listed))
        guide.show_buttons['sleep'].click()
        self.assertEqual(self.pet.current_state, 'sleep')
        guide.deleteLater()

    def test_settings_has_a_card_for_the_guide(self):
        from widget import Settings
        settings = Settings(self.panel)
        self.assertIn(str(pose_guide.pose_count()), settings.poses_button.text())
        settings.deleteLater()

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
        self.pet.panel.activity.state.sampled = __import__('time').monotonic()
        with patch('pet.time.time', return_value=120 * 3):
            self.pet.update_activity()
        self.assertEqual(self.pet.current_state, 'guitar')


if __name__ == '__main__':
    unittest.main()
