"""Game mode keeps what she wears in order around her, and the usage card sits above all of it."""
import unittest
from unittest import mock

from PySide6.QtCore import QPoint, QRect
from PySide6.QtWidgets import QApplication

import game_mode
import usage_overlay

APP = QApplication.instance() or QApplication([])


class RestackTests(unittest.TestCase):
    def test_the_ring_her_and_what_she_wears_stay_in_order(self):
        class Decor:
            back, front = 'back', 'front'

        class Pet:
            decor = Decor()
            transform_stage = None
            game_usage = 'usage'
            focus_tag = None

        class Halo:
            pet = Pet()
        raised = []
        with mock.patch.object(game_mode, 'raise_quietly', raised.append):
            game_mode.GameHalo.restack(Halo())
        self.assertEqual([w for w in raised if w is not None and not isinstance(w, (Pet,))],
                         [raised[0], 'back', 'front', 'usage'])
        self.assertIs(raised[2], Halo.pet)                          # Between the two decoration layers.


class Screen:
    def __init__(self, rect):
        self.rect = rect

    def availableGeometry(self):
        return self.rect


class Pet:
    pet_scale = 100

    class panel:
        prefs = dict(always_on_top=False)

    def __init__(self, x, y, anchor, screen):
        self._pos, self.card_anchor, self._screen = QPoint(x, y), anchor, Screen(screen)

    def pos(self):
        return self._pos

    def width(self):
        return 272

    def screen(self):
        return self._screen

    def _px(self, value):
        return value


class CardTests(unittest.TestCase):
    def overlay(self, *args):
        card = usage_overlay.UsageOverlay(Pet(*args))
        self.addCleanup(card.deleteLater)
        card.setFixedSize(240, 200)
        return card

    def test_it_sits_centred_over_her_head_just_above_her_top(self):
        card = self.overlay(500, 500, (150, 40), QRect(0, 0, 1920, 1080))
        card.follow()
        self.assertEqual(card.pos(), QPoint(500 + 150 - 120, 500 + 40 - usage_overlay.GAP_ABOVE_SPRITE - 200))

    def test_with_no_room_above_it_moves_beside_her(self):
        card = self.overlay(500, 20, (150, 40), QRect(0, 0, 1920, 1080))
        card.follow()
        self.assertEqual(card.pos(), QPoint(500 + 272 + 8, 0))

    def test_at_the_right_edge_it_goes_to_her_left(self):
        card = self.overlay(1640, 20, (150, 40), QRect(0, 0, 1920, 1080))
        card.follow()
        self.assertEqual(card.pos(), QPoint(1640 - 240 - 8, 0))


if __name__ == '__main__':
    unittest.main()
