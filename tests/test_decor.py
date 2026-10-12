"""2.5 decorations: the drawn catalogue, where pieces sit on her, the task-star style."""
import unittest
from collections import Counter

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QApplication

import decor
import shop

APP = QApplication.instance() or QApplication([])


class FakeShop:
    def __init__(self, worn):
        self.worn = worn

    def equipped(self):
        return dict(self.worn)

    def owned(self):
        return set(self.worn.values()) - {'decor.star_paw'}         # One worn piece no longer owned.


class FakePanel:
    def __init__(self, worn):
        self.shop = FakeShop(worn)


class DecorTests(unittest.TestCase):
    def test_catalogue_has_codex_sixty_with_their_spread_and_art(self):
        pieces = [i for i in shop.CATALOG if i['set'] == 'decor']
        self.assertEqual(len(pieces), 60)
        self.assertEqual(Counter(i['rarity'] for i in pieces),
                         Counter(xinghai=1, yinhe=3, haori=9, mingyue=19, fanxing=28))
        self.assertEqual(Counter(i['slot'] for i in pieces), Counter(head=18, back=10, ground=10, buddy=10, star=12))
        for item in pieces:
            for frame in item['art']:
                self.assertTrue((shop.ASSETS / frame).is_file(), frame)
        self.assertEqual(len(shop.BY_ID['decor.buddy_moon_kitten']['art']), 2)
        from shop_view import item_name
        self.assertEqual(item_name(shop.BY_ID['decor.head_star_bow'], 'en'), 'Starlight Bow')

    def test_outfits_cover_every_pose_with_the_nearest_drawn_one(self):
        import outfits
        drawn = [i for i in shop.CATALOG if i['set'] == 'outfit']
        self.assertEqual(Counter(i['series'] for i in drawn), Counter(starsea_gown=5, frost_coat=3))
        coat = shop.BY_ID['outfit.frost_coat_haori']
        self.assertTrue(outfits.frame_path(coat, 'cheer').endswith('frost_coat/haori/celebrate_1.png'))
        self.assertTrue(outfits.frame_path(coat, 'greet_morning', 1).endswith('wave_2.png'))
        self.assertTrue(outfits.frame_path(coat, 'idle', 0, blink=True).endswith('idle_blink.png'))
        self.assertTrue(outfits.frame_path(coat, 'some_new_pose').endswith('idle_1.png'))
        for own in ('star_idle', 'night_idle', 'game_cheer', 'form2_idle'):
            self.assertIsNone(outfits.frame_path(coat, own))       # Her other forms keep their art.
        self.assertIsNotNone(outfits.pixmap(coat, 'typing', 2))

    def test_weapon_keeps_one_hand_through_a_pose(self):
        import time

        class Pet:
            pet_scale = 100

            def pos(self):
                from PySide6.QtCore import QPoint
                return QPoint(0, 0)

            def devicePixelRatioF(self):
                return 1.0
        d = decor.Decor(Pet())
        xs = []
        for k in range(8):                                          # dragged_4 holds with the other hand.
            d.source = f'assets/v2_0/dragged_{k % 4 + 1}.png'
            d._step_weapon()
            xs.append(d._wpose[0])
            time.sleep(.02)
        self.assertLess(max(xs) - min(xs), .05)

    def test_head_top_skips_thin_tips_and_finds_the_head(self):
        image = QImage(200, 200, QImage.Format_ARGB32)
        image.fill(QColor(0, 0, 0, 0))
        p = QPainter(image)
        p.fillRect(150, 10, 3, 30, QColor('white'))              # A thin feather sticking up.
        p.setBrush(QColor('white'))
        p.drawEllipse(QPointF(100, 110), 60, 60)                # Her head, top at y = 50.
        p.end()
        fx, fy = decor.head_top(QPixmap.fromImage(image))
        self.assertAlmostEqual(fx, .5, delta=.06)
        self.assertAlmostEqual(fy, .25, delta=.05)

    def test_worn_pieces_rest_their_band_on_her_hair(self):
        image = QImage(200, 200, QImage.Format_ARGB32)
        image.fill(QColor(0, 0, 0, 0))
        p = QPainter(image)
        p.setBrush(QColor('white'))
        p.drawEllipse(QPointF(100, 110), 60, 60)                # Her head, top at y = 50.
        p.end()
        art = QImage(120, 80, QImage.Format_ARGB32)              # A crown: points above a rim 100 wide.
        art.fill(QColor(0, 0, 0, 0))
        p = QPainter(art)
        p.fillRect(10, 60, 100, 12, QColor('gold'))
        p.fillRect(55, 0, 10, 60, QColor('gold'))
        p.fillRect(57, 72, 6, 8, QColor('gold'))                 # A pendant under the rim does not count.
        p.end()
        cx, bottom, width = decor.art_band(QPixmap.fromImage(art))
        self.assertAlmostEqual(cx, 60, delta=2)
        self.assertAlmostEqual(bottom, 72, delta=2)
        self.assertAlmostEqual(width, 100, delta=3)
        rect = QRectF(0, 0, 200, 200)
        point, anchor, scale = decor.worn_on_head(QPixmap.fromImage(image), rect, QPixmap.fromImage(art),
                                                  'head_prism_crown', 1.0)
        self.assertAlmostEqual(point.x(), 100, delta=4)
        self.assertGreater(point.y(), 55)                       # Sunk into her hair, not perched on top,
        self.assertLess(point.y(), 110)                         # and still on her head.
        self.assertGreater(image.pixelColor(int(point.x()), int(point.y())).alpha(), 0)

    def test_worn_items_only_owned_drawn_pieces_and_star_style(self):
        worn = {'head': 'decor.head_star_bow', 'outfit': 'outfit.moon_dress', 'star': 'decor.star_paw'}
        items = decor.worn_items(FakePanel(worn))
        self.assertEqual(set(items), {'head'})                   # Outfits have no drawn art yet; paw not owned.
        decor.STAR = shop.BY_ID['decor.star_heart']
        try:
            image = QImage(80, 80, QImage.Format_ARGB32_Premultiplied)
            image.fill(0)
            p = QPainter(image)
            self.assertTrue(decor.paint_star(p, QPointF(40, 40), 50))
            p.end()
            self.assertGreater(image.pixelColor(40, 40).alpha(), 0)
        finally:
            decor.STAR = None
        self.assertFalse(decor.paint_star(None, QPointF(0, 0), 10))

    def test_lying_poses_hide_head_and_back(self):
        class Pet:
            pet_scale = 100

            def pos(self):
                from PySide6.QtCore import QPoint
                return QPoint(0, 0)

            def devicePixelRatioF(self):
                return 1.0

        class Layer:
            front = True

            def pos(self):
                from PySide6.QtCore import QPoint
                return QPoint(0, 0)
        d = decor.Decor(Pet())
        d.items = {'head': shop.BY_ID['decor.head_star_bow']}
        sprite = QPixmap(100, 100)
        sprite.fill(QColor('white'))
        from PySide6.QtGui import QTransform
        for state, drawn in (('idle', True), ('sleep', False)):
            image = QImage(400, 400, QImage.Format_ARGB32_Premultiplied)
            image.fill(0)
            p = QPainter(image)
            d.pose = (state, sprite, QTransform(), QRectF(150, 150, 100, 100))
            d.paint(p, Layer())
            p.end()
            lit = any(image.pixelColor(x, y).alpha() for x in range(0, 400, 4) for y in range(0, 170, 4))
            self.assertEqual(lit, drawn, state)


if __name__ == '__main__':
    unittest.main()


class OwnFitAndFullSetTests(unittest.TestCase):
    def test_own_fit_moves_grows_and_turns_a_piece(self):
        import tempfile
        from pathlib import Path
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        store = shop.Shop(FakePanel({}), Path(temp.name) / 'shop.json')
        self.addCleanup(shop.OWN_FIT.clear)
        crown = shop.BY_ID['decor.head_prism_crown']
        store.adjust_fit(crown['id'], dx=.02, dy=-.01, scale=1.1, angle=5)
        store.adjust_fit(crown['id'], dx=.02)
        shift, grown, turned = decor.own_fit(crown, QRectF(0, 0, 200, 100))
        self.assertAlmostEqual(shift.x(), 8, delta=.01)
        self.assertAlmostEqual(shift.y(), -1, delta=.01)
        self.assertAlmostEqual(grown, 1.1)
        self.assertEqual(turned, 5)
        again = shop.Shop(FakePanel({}), Path(temp.name) / 'shop.json')     # Kept with the shop.
        self.assertIn(crown['id'], again.state['fit'])
        again.reset_fit(crown['id'])
        self.assertEqual(decor.own_fit(crown, QRectF(0, 0, 200, 100))[1], 1.0)

    def test_forms_use_their_full_set_once_drawn(self):
        import pet_assets
        import starsea
        self.addCleanup(pet_assets._FULL_CACHE.clear)
        pet_assets._FULL_CACHE['night:typing'] = True
        pet_assets._FULL_CACHE['star:hug'] = True
        self.assertEqual(pet_assets.full_set('night', 'typing'), 'night:typing')
        self.assertIsNone(pet_assets.full_set('night', 'hug') if not pet_assets._file(
            pet_assets._FORM_ENTRIES['night:hug'].path).is_file() else None)
        from night_mode import NightMode
        night = NightMode.__new__(NightMode)
        night.active = True
        self.assertEqual(night.pose('typing'), 'night:typing')
        sea = starsea.StarseaForm.__new__(starsea.StarseaForm)
        sea.__dict__['active'] = True
        self.assertEqual(sea.pose('hug'), 'star:hug')
        self.assertEqual(sea.pose('night:typing'), 'night:typing')   # Another form's picture stays.
