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
