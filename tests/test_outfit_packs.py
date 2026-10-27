"""2.5.1 outfit packs: the package keeps the mirror's pictures, the rest comes once she owns it."""
import json
import os
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

import outfit_packs
import outfits
from tools import pack_outfits

APP = QApplication.instance() or QApplication([])
ITEM = dict(id='outfit.gown_haori', set='outfit', name='gown_haori', series='gown', tier='haori')
POSES = ('idle_1', 'idle_2', 'idle_blink', 'typing_1', 'typing_2', 'wave_1', 'celebrate_1', 'sleep_1')


class PackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        base = Path(self.temp.name)
        self.package = base / 'package'
        self.packs = base / 'packs'
        self.root = base / 'appdata'
        tier = self.package / 'gown' / 'haori'
        tier.mkdir(parents=True)
        for k, name in enumerate(POSES):
            image = QImage(8, 8, QImage.Format_ARGB32)
            image.fill(QColor(k * 20, 0, 0, 255))
            image.save(str(tier / f'{name}.png'))
        self.manifest = pack_outfits.main(self.package, self.packs)
        self.patches = [patch.object(outfit_packs, 'OUTFIT_DIR', self.package),
                        patch.object(outfit_packs, 'PACKS_FILE', self.package / 'packs.json'),
                        patch.object(outfit_packs, 'ROOT', self.root),
                        patch.dict(os.environ, PETOKEN_OUTFIT_PACKS=str(self.packs))]
        for p in self.patches:
            p.start()
        outfit_packs.manifest.cache_clear()
        outfits.forget()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        outfit_packs.manifest.cache_clear()
        outfits.forget()
        self.temp.cleanup()

    def test_build_keeps_only_the_mirror_pictures_and_names_the_zip_by_content(self):
        left = sorted(p.stem for p in (self.package / 'gown' / 'haori').iterdir())
        self.assertEqual(left, ['celebrate_1', 'idle_1', 'idle_blink', 'wave_1'])
        entry = self.manifest['gown_haori']
        self.assertEqual(entry['count'], len(POSES))
        self.assertIn(entry['sha256'][:12], entry['file'])
        self.assertEqual(json.loads((self.package / 'packs.json').read_text()), self.manifest)
        with zipfile.ZipFile(self.packs / entry['file']) as archive:
            self.assertEqual(len(archive.namelist()), len(POSES))

    def test_she_keeps_her_own_look_until_it_is_here_then_wears_all_of_it(self):
        self.assertFalse(outfit_packs.ready(ITEM))
        self.assertIsNone(outfits.frame_path(ITEM, 'typing'))
        self.assertIn('idle_1', outfits.frame_path(ITEM, 'typing', preview=True))   # The mirror shows what there is.
        outfit_packs.fetch(ITEM)
        outfits.forget()
        self.assertTrue(outfit_packs.ready(ITEM))
        path = outfits.frame_path(ITEM, 'typing', 1)
        self.assertTrue(path.endswith('typing_2.png'))
        self.assertTrue(Path(path).is_relative_to(self.root))

    def test_a_wrong_or_odd_pack_is_never_used(self):
        entry = self.manifest['gown_haori']
        zip_path = self.packs / entry['file']
        good = zip_path.read_bytes()
        zip_path.write_bytes(good[:-10] + b'0123456789')
        with self.assertRaises(ValueError):
            outfit_packs.fetch(ITEM)
        self.assertFalse(outfit_packs.ready(ITEM))
        with zipfile.ZipFile(zip_path, 'w') as archive:                 # The right hash, a bad name inside.
            archive.writestr('../evil.png', b'x')
        entry['sha256'] = __import__('hashlib').sha256(zip_path.read_bytes()).hexdigest()
        with self.assertRaises(ValueError):
            outfit_packs.fetch(ITEM)
        self.assertFalse(outfit_packs.ready(ITEM))
        self.assertFalse((self.root.parent / 'evil.png').exists())

    def test_owning_an_outfit_downloads_it_in_the_background(self):
        import shop

        class Panel:
            def __init__(self):
                self.changed = 0

            def shop_worn_changed(self):
                self.changed += 1
        panel = Panel()
        packs = outfit_packs.OutfitPacks(None, enabled=True)
        packs.panel = panel
        with patch.dict(shop.BY_ID, {ITEM['id']: ITEM}):
            packs.want(ITEM['id'])
            self.assertEqual(packs.status(ITEM), 0.0)
            end = time.time() + 10
            while not panel.changed:
                APP.processEvents()
                self.assertLess(time.time(), end)
                time.sleep(.01)
        self.assertEqual(panel.changed, 1)
        self.assertTrue(outfit_packs.ready(ITEM))
        self.assertEqual(packs.state, {})

    def test_from_the_repository_every_outfit_is_whole(self):
        with patch.object(outfit_packs, 'PACKS_FILE', self.package / 'none.json'):
            outfit_packs.manifest.cache_clear()
            self.assertTrue(outfit_packs.ready(ITEM))


class ShopHookTests(unittest.TestCase):
    def test_a_new_item_tells_the_panel(self):
        import shop

        class Panel:
            stardust = None

            def __init__(self):
                self.owned = []

            def shop_owned(self, item_id):
                self.owned.append(item_id)
        with tempfile.TemporaryDirectory() as folder:
            panel = Panel()
            store = shop.Shop(panel, Path(folder) / 'shop.json')
            item = next(i['id'] for i in shop.CATALOG if i['set'] == 'outfit')
            store._own(item, 'wish')
            store._own(item, 'wish')                                    # A duplicate: refunded, not fetched again.
        self.assertEqual(panel.owned, [item])


if __name__ == '__main__':
    unittest.main()
