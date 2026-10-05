import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path

from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QApplication

import pet_assets as assets
import pet_geometry as geometry

ROOT = Path(__file__).parents[1]
IDLE_SHA = '7ce0d2fbd0eb89d2f6786c9bb1d5bada1aff7d89ea2f5dd079cce8a26483e1a0'


class PetAssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_v1_idle_asset_hash_unchanged(self):
        self.assertEqual(hashlib.sha256((ROOT / 'assets/skirk-pet.png').read_bytes()).hexdigest(), IDLE_SHA)

    def test_registry_resolves_every_current_state(self):
        self.assertEqual(set(assets.registered_states()),
                         {'idle', 'typing', 'codex_working', 'microphone', 'music', 'guitar',
                          'celebrate', 'sad', 'wave'})
        for state in assets.PREVIEW_STATES:
            pixmap = assets.sprite_for(state)
            self.assertIsNotNone(pixmap, state)
            self.assertFalse(pixmap.isNull(), state)

    def test_codex_working_and_typing_are_distinct_states(self):
        working = assets.entry_for('working')
        typing = assets.entry_for('typing')
        self.assertEqual(working.state, 'codex_working')
        self.assertEqual(typing.state, 'typing')
        self.assertNotEqual(working.path, typing.path)
        self.assertNotEqual(working.fallback, typing.fallback)

    def test_final_v1_1_primaries_resolve_for_every_state(self):
        for entry in assets.REGISTRY:
            self.assertTrue((ROOT / entry.path).is_file()
                            or assets.existing_frames(entry), entry.state)
            pixmap = assets.sprite_for(entry.state)
            self.assertIsNotNone(pixmap, entry.state)
            self.assertFalse(pixmap.isNull(), entry.state)
            self.assertEqual((pixmap.width(), pixmap.height()), (1254, 1254))
        self.assertEqual(len(assets.existing_frames(assets.entry_for('typing'))), 2)

    def test_typing_frames_come_from_final_art(self):
        self.assertIsNotNone(assets.frame_for('typing', 0))
        self.assertIsNotNone(assets.frame_for('typing', 1))
        self.assertNotEqual(
            assets.frame_for('typing', 0).cacheKey(),
            assets.frame_for('typing', 1).cacheKey())

    def test_missing_primary_falls_back_without_error(self):
        entry = assets.AssetEntry('typing', 'assets/v1_1/absent.png',
                                  'assets/skirk-typing.png')
        self.assertEqual(assets.resolve_path(entry), 'assets/skirk-typing.png')
        self.assertEqual(assets.resolve_path(assets.entry_for('idle')),
                         'assets/v1_1/idle.png')
        self.assertFalse(assets.validate_path(entry.path)[0])
        self.assertIsNotNone(assets.sprite_for('typing'))

    def test_unknown_state_resolves_to_idle(self):
        idle = assets.sprite_for('idle')
        self.assertIsNotNone(assets.sprite_for('dance-party'))
        self.assertEqual(assets.entry_for('dance-party').state, 'idle')
        self.assertEqual(assets.sprite_for('dance-party').size(), idle.size())

    def test_broken_asset_does_not_crash(self):
        with tempfile.TemporaryDirectory() as directory:
            broken = Path(directory) / 'broken.png'
            broken.write_bytes(b'this is not an image')
            ok, reason = assets.validate_path(str(broken))
            self.assertFalse(ok)
            self.assertTrue(reason)
            self.assertIsNone(assets.load_path(str(broken)))
            missing = Path(directory) / 'absent.png'
            self.assertFalse(assets.validate_path(str(missing))[0])
            self.assertIsNone(assets.load_path(str(missing)))

    def test_source_resolution_never_changes_logical_geometry(self):
        with tempfile.TemporaryDirectory() as directory:
            small = Path(directory) / 'small.png'
            large = Path(directory) / 'large.png'
            QImage(64, 64, QImage.Format_ARGB32).save(str(small))
            QImage(1024, 1024, QImage.Format_ARGB32).save(str(large))
            self.assertNotEqual(assets.load_path(str(small)).width(),
                                assets.load_path(str(large)).width())
        self.assertEqual(geometry.sprite_rect(), (8, 64, 256, 256))
        self.assertEqual(geometry.anchor(), (136, 320))

    def test_entries_carry_no_layout_geometry(self):
        for entry in assets.REGISTRY:
            for field in ('rect', 'size', 'scale', 'anchor', 'x', 'y', 'width', 'height'):
                self.assertFalse(hasattr(entry, field), f'{entry.state}.{field}')
        self.assertFalse(assets.entry_for('idle').animated)

    def test_resolved_art_keeps_transparency(self):
        image = QImage(str(ROOT / 'assets/skirk-pet.png'))
        self.assertFalse(image.isNull())
        self.assertTrue(image.hasAlphaChannel())
        self.assertEqual(image.pixelColor(0, 0).alpha(), 0)
        for state in ('typing', 'microphone', 'music'):
            pixmap = assets.sprite_for(state)
            self.assertFalse(pixmap.isNull(), state)

    def test_render_tool_enumerates_registered_preview_states(self):
        spec = importlib.util.spec_from_file_location(
            'render_states', str(ROOT / 'tools/render_states.py'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(tuple(module.STATES), assets.PREVIEW_STATES)
        self.assertIn('working', module.STATES)
        self.assertIn('usage', module.STATES)

    def test_logical_geometry_is_dpr_independent(self):
        self.assertEqual(geometry.window_size(), (272, 330))
        self.assertEqual(geometry.device_pixels(145, 1.0) * 2, geometry.device_pixels(145, 2.0))
        pixmap = QPixmap(str(ROOT / 'assets/skirk-pet.png'))
        self.assertGreater(pixmap.width(), geometry.SPRITE_WIDTH * 4)


if __name__ == '__main__':
    unittest.main()
