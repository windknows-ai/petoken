"""Adjustable pet character size: persistence, geometry, anchoring, all states."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication

import pet_assets as assets
import pet_geometry as geometry
from app_config import DEFAULT_PREFERENCES, load_preferences, save_preferences
from pet import DesktopPet
from widget import Panel, Settings

STATES = ('idle', 'typing', 'codex_working', 'microphone', 'music', 'guitar')
SCALES = (50, 75, 100, 150)


class PetScaleTests(unittest.TestCase):
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

    # -- preference semantics ----------------------------------------------

    def test_no_saved_value_gives_100(self):
        self.assertEqual(DEFAULT_PREFERENCES['pet_scale_percent'], 100)
        self.assertEqual(load_preferences(self.pref_dir / 'missing.json')['pet_scale_percent'], 100)
        self.assertEqual(geometry.normalize_pet_scale(None), 100)
        self.assertEqual(self.make_panel().prefs['pet_scale_percent'], 100)

    def test_minimum_value_is_50(self):
        self.assertEqual(geometry.PET_SCALE_MIN, 50)
        for raw in (0, 1, 49, -100):
            self.assertEqual(geometry.normalize_pet_scale(raw), 50, repr(raw))

    def test_approved_geometry_at_100_is_unchanged(self):
        self.assertEqual(geometry.scaled_window_size(100), (272, 330))
        self.assertEqual(geometry.scaled_window_size(100), geometry.window_size())
        self.assertEqual(geometry.scaled_sprite_rect(100), (8, 64, 256, 256))
        self.assertEqual(geometry.scaled_sprite_rect(100), geometry.sprite_rect())
        self.assertEqual(geometry.scaled_anchor(100), (136, 320))
        self.assertEqual(geometry.scaled_anchor(100), geometry.anchor())

    def test_50_percent_is_half_dimensions(self):
        self.assertEqual(geometry.scaled_window_size(50), (136, 165))
        self.assertEqual(geometry.scaled_sprite_rect(50), (4, 32, 128, 128))
        self.assertEqual(geometry.scaled_anchor(50), (68, 160))

    def test_intermediate_75_percent_scales_correctly(self):
        self.assertEqual(geometry.scaled_window_size(75), (204, 248))
        self.assertEqual(geometry.scaled_sprite_rect(75), (6, 48, 192, 192))
        self.assertEqual(geometry.scaled_anchor(75), (102, 240))

    def test_maximum_stays_within_safe_geometry(self):
        self.assertEqual(geometry.PET_SCALE_MAX, 150)
        window = geometry.scaled_window_size(150)
        self.assertEqual(window, (408, 495))
        self.assertLessEqual(window[0], 600)
        self.assertLessEqual(window[1], 700)
        side = geometry.scaled_sprite_rect(150)[2]
        self.assertEqual(side, 384)
        # Even at 150% on a 200% display the physical sprite (768 px) stays
        # below the 1254 px source, so no upscaling blur is introduced.
        self.assertLess(geometry.device_pixels(side, 2.0), 1254)

    def test_persistence_roundtrip(self):
        path = self.pref_dir / 'scale.json'
        save_preferences(path, {'pet_scale_percent': 75})
        self.assertEqual(load_preferences(path)['pet_scale_percent'], 75)
        save_preferences(path, {'pet_scale_percent': 100})
        self.assertEqual(load_preferences(path)['pet_scale_percent'], 100)
        panel = self.make_panel({'pet_scale_percent': 75})
        panel.persist()
        self.assertEqual(self.make_panel().prefs['pet_scale_percent'], 75)

    def test_invalid_values_normalize_safely(self):
        self.assertEqual(geometry.normalize_pet_scale('huge'), 100)
        self.assertEqual(geometry.normalize_pet_scale([100]), 100)
        self.assertEqual(geometry.normalize_pet_scale({'x': 1}), 100)
        self.assertEqual(geometry.normalize_pet_scale(True), 100)
        self.assertEqual(geometry.normalize_pet_scale(float('nan')), 100)
        self.assertEqual(geometry.normalize_pet_scale(9999), 150)
        self.assertEqual(geometry.normalize_pet_scale('75'), 75)
        self.assertEqual(geometry.normalize_pet_scale(72.6), 73)

    def test_reset_to_defaults_restores_100(self):
        panel = self.make_panel({'pet_scale_percent': 75})
        pet = self.attach_pet(panel)
        self.assertEqual(pet.pet_scale, 75)
        settings = Settings(panel)
        try:
            self.assertEqual(settings.pet_scale.value(), 75)
            settings.pet_scale.setValue(150)
            self.assertEqual(pet.pet_scale, 150)
            settings.reset_button.click()
            settings.reset_button.click()
            self.assertEqual(settings.pet_scale.value(), 100)
            self.assertEqual(pet.pet_scale, 100)
            settings.save()
            self.assertEqual(panel.prefs['pet_scale_percent'], 100)
            self.assertEqual(
                load_preferences(self.pref_dir / 'settings.json')['pet_scale_percent'], 100)
        finally:
            settings.deleteLater()

    # -- every state scales together -----------------------------------------

    def test_all_states_scale_proportionally(self):
        panel = self.make_panel()
        pet = self.attach_pet(panel)
        sizes = {}
        for scale in SCALES:
            pet.apply_pet_scale(scale)
            self.assertEqual((pet.width(), pet.height()),
                             geometry.scaled_window_size(scale))
            for state in STATES:
                pixmap = assets.sprite_for(state)
                self.assertFalse(pixmap.isNull(), (state, scale))
                rendered = pet.render_sprite(pixmap)
                size = rendered.deviceIndependentSize()
                sizes[(state, scale)] = (round(size.width()), round(size.height()))
                self.assertFalse(pet.grab().toImage().isNull(), (state, scale))
        for state in STATES:
            w50, h50 = sizes[(state, 50)]
            for scale in (75, 100, 150):
                w, h = sizes[(state, scale)]
                self.assertEqual((w, h), (w50 * scale // 50, h50 * scale // 50),
                                 (state, scale))

    def test_typing_frames_scale_with_idle(self):
        panel = self.make_panel()
        pet = self.attach_pet(panel)
        for scale in SCALES:
            pet.apply_pet_scale(scale)
            idle = pet.render_sprite(assets.sprite_for('idle'))
            for phase in (0, 1):
                frame = assets.frame_for('typing', phase)
                self.assertIsNotNone(frame, (scale, phase))
                rendered = pet.render_sprite(frame)
                self.assertEqual(
                    (round(rendered.deviceIndependentSize().width()),
                     round(rendered.deviceIndependentSize().height())),
                    (round(idle.deviceIndependentSize().width()),
                     round(idle.deviceIndependentSize().height())),
                    (scale, phase))

    def test_idle_aspect_ratio_unchanged_across_scales(self):
        panel = self.make_panel()
        pet = self.attach_pet(panel)
        ratios = set()
        for scale in SCALES:
            pet.apply_pet_scale(scale)
            size = pet.render_sprite(assets.sprite_for('idle')).deviceIndependentSize()
            ratios.add(round(size.width() / size.height(), 6))
        self.assertEqual(len(ratios), 1)

    def test_feet_anchor_stays_stable(self):
        for scale in list(SCALES) + [60, 125]:
            x, y, w, h = geometry.scaled_sprite_rect(scale)
            ww, _ = geometry.scaled_window_size(scale)
            self.assertEqual(geometry.scaled_anchor(scale), (ww // 2, y + h), scale)

    def test_working_state_scales(self):
        self._state_paints_at_all_scales('working')

    def test_microphone_state_scales(self):
        self._state_paints_at_all_scales('microphone')

    def test_music_state_scales(self):
        self._state_paints_at_all_scales('music')

    def test_guitar_state_scales(self):
        self._state_paints_at_all_scales('guitar')

    def _state_paints_at_all_scales(self, state):
        panel = self.make_panel()
        pet = self.attach_pet(panel)
        for scale in SCALES:
            pet.apply_pet_scale(scale)
            pet.preview_state = state
            pet.update_activity()
            self.app.processEvents()
            self.assertFalse(pet.grab().toImage().isNull(), (state, scale))
        pet.preview_state = None

    # -- anchoring, clamping, panel follow -------------------------------------

    def test_clamp_keeps_scaled_pet_on_screen(self):
        panel = self.make_panel()
        pet = self.attach_pet(panel)
        screen = self.app.primaryScreen().availableGeometry()
        for scale in SCALES:
            pet.apply_pet_scale(scale)
            pet.move_clamped(QPoint(-5000, -5000))
            pos = pet.pos()
            self.assertGreaterEqual(pos.x(), screen.left(), scale)
            self.assertGreaterEqual(pos.y(), screen.top(), scale)
            pet.move_clamped(QPoint(screen.right() + 5000, screen.bottom() + 5000))
            pos = pet.pos()
            self.assertLessEqual(pos.x() + pet.width(), screen.right() + 1, scale)
            self.assertLessEqual(pos.y() + pet.height(), screen.bottom() + 1, scale)

    def test_panel_opens_next_to_scaled_pet_without_moving_it(self):
        for scale in SCALES:
            panel = self.make_panel()
            pet = self.attach_pet(panel)
            pet.apply_pet_scale(scale)
            pet.show()
            self.app.processEvents()
            before = pet.pos()
            pet.show_panel()
            self.app.processEvents()
            self.assertTrue(panel.isVisible(), scale)
            self.assertEqual(pet.pos(), before, scale)
            self.assertFalse(panel.geometry().intersects(pet.geometry()), scale)
            panel.hide()

    def test_rescale_with_panel_open_has_no_drift_or_duplicate(self):
        panel = self.make_panel()
        pet = self.attach_pet(panel)
        pet.show()
        self.app.processEvents()
        # Roomy position so clamping cannot interfere with drift measurement.
        screen = self.app.primaryScreen().availableGeometry()
        pet.move_clamped(QPoint(screen.left() + 400, screen.top() + 300))
        pet.show_panel()
        self.app.processEvents()
        original = pet.pos()
        pet.apply_pet_scale(150)
        self.app.processEvents()
        # Feet stay planted: the anchor's screen position is preserved.
        anchor = QPoint(*geometry.scaled_anchor(150))
        self.assertEqual(pet.pos() + anchor, original + QPoint(*geometry.scaled_anchor(100)))
        self.assertFalse(panel.geometry().intersects(pet.geometry()))
        pet.apply_pet_scale(100)
        self.app.processEvents()
        self.assertEqual(pet.pos(), original)
        self.assertTrue(pet.isVisible())
        self.assertTrue(panel.isVisible())
        self.assertFalse(hasattr(panel, 'stage'))
        panel.hide()

    def test_settings_slider_previews_live_and_cancel_reverts(self):
        panel = self.make_panel()
        pet = self.attach_pet(panel)
        settings = Settings(panel)
        try:
            settings.pet_scale.setValue(75)
            self.assertEqual(settings.pet_scale_value.text(), '75%')
            self.assertEqual(pet.pet_scale, 75)
            settings.reject()
            self.assertEqual(pet.pet_scale, 100)
        finally:
            settings.deleteLater()

    def test_settings_labels_follow_language(self):
        panel = self.make_panel({'language': 'en'})
        settings = Settings(panel)
        try:
            self.assertEqual(settings.pet_scale_label.text(), 'Character Size')
            panel.prefs['language'] = 'zh_CN'
            panel.apply_language()
            en_settings = Settings(panel)
            try:
                self.assertEqual(en_settings.pet_scale_label.text(), '角色大小')
            finally:
                en_settings.deleteLater()
        finally:
            settings.deleteLater()


if __name__ == '__main__':
    unittest.main()
