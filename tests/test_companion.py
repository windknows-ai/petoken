"""Companion-redesign slice: character-led composition, stage, coupling."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QApplication

import pet_assets as assets
from pet import DesktopPet
from widget import PANEL_DEFAULT, PANEL_MAX, PANEL_MIN, Panel, Settings


class CompanionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.pref_dir = Path(self.temp.name)
        self.pref_patch = patch('widget.PREF_DIR', self.pref_dir)
        self.pref_patch.start()
        self.panels = []

    def tearDown(self):
        for panel in self.panels:
            panel.tray.hide()
            if panel.analytics_window:
                panel.analytics_window.close()
            if hasattr(panel, 'pet'):
                panel.pet.close()
            panel.closing = True
            panel.close()
            panel.deleteLater()
        self.app.processEvents()
        self.pref_patch.stop()
        self.temp.cleanup()

    def make_panel(self, prefs=None):
        if prefs is not None:
            (self.pref_dir / 'settings.json').write_text(json.dumps(prefs), encoding='utf-8')
        panel = Panel(live=False)
        self.panels.append(panel)
        return panel

    def attach_pet(self, panel):
        panel.pet = DesktopPet(panel)
        panel.pet.activity_timer.stop()
        return panel.pet

    # -- composition ------------------------------------------------------

    def test_stage_bleeds_over_the_surface_edge(self):
        panel = self.make_panel()
        panel.show()
        self.app.processEvents()
        stage = panel.stage
        self.assertEqual((stage.x(), stage.width()), (8, 230))
        self.assertGreater(stage.x() + stage.width(), 150)
        self.assertTrue(bool(stage.testAttribute(Qt.WA_TransparentForMouseEvents)))

    def test_character_occupies_a_leading_share_of_the_window(self):
        panel = self.make_panel()
        panel.show()
        share = panel.stage.width() / panel.width()
        self.assertGreaterEqual(share, 0.30)
        self.assertLessEqual(share, 0.45)

    def test_default_panel_is_landscape(self):
        self.assertGreater(PANEL_DEFAULT[0], PANEL_DEFAULT[1])
        self.assertEqual(PANEL_DEFAULT, (560, 500))

    # -- single-character coupling ------------------------------------------

    def test_panel_show_hides_pet_and_hide_restores_it(self):
        panel = self.make_panel()
        pet = self.attach_pet(panel)
        pet.show()
        self.assertTrue(pet.isVisible())
        panel.show()
        self.app.processEvents()
        self.assertFalse(pet.isVisible())
        panel.hide()
        self.app.processEvents()
        self.assertTrue(pet.isVisible())

    def test_user_hidden_pet_stays_hidden_after_panel_closes(self):
        panel = self.make_panel()
        pet = self.attach_pet(panel)
        pet.hide()
        panel.show()
        self.app.processEvents()
        panel.hide()
        self.app.processEvents()
        self.assertFalse(pet.isVisible())

    def test_toggle_pet_reveals_pet_by_closing_panel(self):
        panel = self.make_panel()
        pet = self.attach_pet(panel)
        pet.show()
        panel.show()
        self.app.processEvents()
        self.assertFalse(pet.isVisible())
        panel.toggle_pet()
        self.app.processEvents()
        self.assertTrue(pet.isVisible())
        self.assertFalse(panel.isVisible())

    def test_show_panel_centers_on_pet_for_stable_hover(self):
        panel = self.make_panel()
        pet = self.attach_pet(panel)
        pet.move(900, 500)
        panel.resize(*PANEL_DEFAULT)
        pet.show_panel()
        center = pet.geometry().center()
        self.assertTrue(panel.geometry().contains(center))

    # -- stage liveness -------------------------------------------------------

    def test_stage_mirrors_every_pet_state(self):
        from analytics import aggregate, normalize_usage
        panel = self.make_panel()
        pet = self.attach_pet(panel)
        panel.show()
        tokens = normalize_usage(dict(input_tokens=120000, cached_input_tokens=90000,
            cache_write_input_tokens=0, output_tokens=18000,
            reasoning_output_tokens=7000, total_tokens=138000))
        analysis = aggregate([dict(session='s', model='gpt-6-astra',
            timestamp='2026-09-16T12:00:00Z', event_id='s', tokens=tokens)])
        panel.render(dict(title='T', project='P', model='m', effort='high',
            mode='follow', scope='project', tokens=tokens, available=True,
            analytics=analysis, usd=1.0, context=10, context_tokens=1,
            context_window=10, raw_total=tokens, raw_last=tokens, notes=[],
            unknown=[], partial=False, count=1, session_names={'s': 'S'}))
        seen = set()
        for state in ('idle', 'typing', 'microphone', 'music', 'working', 'usage', 'guitar'):
            pet.preview_state = state
            pet.update_activity()
            panel.tick_stage()
            self.app.processEvents()
            self.assertEqual(panel.stage.current_state, state)
            image = panel.stage.grab().toImage()
            self.assertFalse(image.isNull(), state)
            seen.add(image.cacheKey())
        self.assertGreater(len(seen), 1)
        pet.preview_state = None

    def test_stage_resolves_typing_frames(self):
        from types import SimpleNamespace
        from activity import ActivityState
        panel = self.make_panel()
        pet = self.attach_pet(panel)
        panel.activity = SimpleNamespace(state=ActivityState(), close=lambda: None,
            status={'microphone': None, 'music': None, 'music_text': None})
        panel.show()
        pet.preview_state = 'typing'
        pet.update_activity()
        panel.tick_stage()
        self.app.processEvents()
        self.assertEqual(panel.stage.current_state, 'typing')
        self.assertIsNotNone(assets.frame_for('typing', pet.typing_phase()))
        self.assertFalse(panel.stage.grab().toImage().isNull())
        pet.preview_state = None

    # -- data integration ------------------------------------------------------

    def test_io_line_carries_both_values_and_status_follows_mode(self):
        from analytics import aggregate, normalize_usage
        panel = self.make_panel({'language': 'en'})
        tokens = normalize_usage(dict(input_tokens=120000, cached_input_tokens=90000,
            cache_write_input_tokens=0, output_tokens=18000,
            reasoning_output_tokens=7000, total_tokens=138000))
        analytics = aggregate([dict(session='s', model='gpt-6-astra',
            timestamp='2026-09-16T12:00:00Z', event_id='s', tokens=tokens)])
        panel.render(dict(title='T', project='P', model='gpt-6-astra', effort='high',
            mode='follow', scope='project', tokens=tokens, available=True,
            analytics=analytics, usd=1.0, context=10, context_tokens=1,
            context_window=10, raw_total=tokens, raw_last=tokens, notes=[],
            unknown=[], partial=False, count=1, session_names={'s': 'S'}))
        self.assertIn('120.00K', panel.io_line.text())
        self.assertIn('18.00K', panel.io_line.text())
        self.assertEqual(panel.status_text.text(), 'Idle')
        panel.app_mode.update(True, True)
        panel.app_mode.update(True, True, panel.app_mode.pending_since + 1.0)
        panel.render(dict(title='T', project='P', model='gpt-6-astra', effort='high',
            mode='working', scope='project', tokens=tokens, available=True,
            analytics=analytics, usd=1.0, context=10, context_tokens=1,
            context_window=10, raw_total=tokens, raw_last=tokens, notes=[],
            unknown=[], partial=False, count=1, session_names={'s': 'S'}))
        self.assertEqual(panel.status_text.text(), 'Working')

    def test_compact_keeps_identity_and_hides_stage_and_scroll(self):
        panel = self.make_panel()
        panel.show()
        panel.toggle_compact()
        self.app.processEvents()
        self.assertFalse(panel.body_scroll.isVisible())
        self.assertFalse(panel.stage.isVisible())
        self.assertLessEqual(panel.height(), 280)
        self.assertTrue(panel.title.isVisible())
        panel.toggle_compact()
        self.app.processEvents()
        self.assertTrue(panel.body_scroll.isVisible())
        self.assertTrue(panel.stage.isVisible())

    def test_minimum_size_keeps_identity_controls_and_stage(self):
        panel = self.make_panel()
        panel.show()
        panel.resize(*PANEL_MIN)
        self.app.processEvents()
        self.assertEqual((panel.width(), panel.height()), PANEL_MIN)
        self.assertFalse(panel.grab().toImage().isNull())
        self.assertTrue(panel.details_button.isVisible())
        self.assertTrue(panel.settings_button.isVisible())
        self.assertTrue(panel.pin.isVisible())


if __name__ == '__main__':
    unittest.main()
