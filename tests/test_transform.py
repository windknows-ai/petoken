"""2.1 transformation: pieces from stage differences, the timeline, playing it."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication

import transform

APP = QApplication.instance() or QApplication([])


def _stage_images(folder):
    """A base figure, then one coloured block added per stage (cumulative)."""
    side = 120
    image = QImage(side, side, QImage.Format_ARGB32)
    image.fill(Qt.transparent)
    p = QPainter(image)
    p.fillRect(QRect(40, 20, 40, 90), QColor('#8080C0'))
    p.end()
    for name in ('xform_rise_1', 'xform_base'):
        image.save(str(folder / f'{name}.png'))
    for index, (name, _) in enumerate(transform.STAGES):
        p = QPainter(image)
        p.fillRect(QRect(5 + index * 12, 10 + index * 10, 10, 10), QColor(255, 200 - index * 15, 60))
        p.end()
        image.save(str(folder / f'{name}.png'))


class TransformTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        _stage_images(self.folder)
        patcher = patch.dict(os.environ, PETOKEN_V2_1_ART=str(self.folder))
        patcher.start()
        self.addCleanup(patcher.stop)
        root = patch.object(transform, 'ROOT', self.folder / 'nowhere')
        root.start()
        self.addCleanup(root.stop)

    def test_each_piece_is_exactly_what_its_stage_adds(self):
        self.assertTrue(transform.available())
        pieces = transform.Pieces.build(120)
        self.assertEqual(len(pieces.stages), len(transform.STAGES))
        for index, (piece, outline, box, direction, _) in enumerate(pieces.stages):
            self.assertEqual(box, QRect(5 + index * 12, 10 + index * 10, 10, 10))
            self.assertEqual(direction, transform.STAGES[index][1])
            self.assertEqual(piece.pixelColor(5, 5).alpha(), 255)          # The block itself...
            self.assertEqual(outline.pixelColor(5, 5).alpha(), 0)          # ...its middle is not outline...
            self.assertEqual(outline.pixelColor(0, 5).alpha(), 255)        # ...its edge is.
        self.assertIsNotNone(pieces.flash)

    def test_timeline_lengths_and_parts(self):
        pieces = transform.Pieces.build(120)
        enter = transform.Timeline(pieces)
        self.assertEqual([name for name, _ in enter.parts], ['rise', 'ring', 'arm', 'mvp', 'settle'])
        self.assertTrue(5 <= enter.length <= 15)                            # The agreed range.
        self.assertEqual(enter.at(0)[0], 'rise')
        self.assertEqual(enter.at(enter.length + 1), ('settle', 1.0))
        leave = transform.Timeline(pieces, leaving=True)
        self.assertEqual([name for name, _ in leave.parts], ['unarm', 'fall'])
        self.assertLess(leave.length, enter.length / 2)

    def test_stage_plays_to_the_end_and_renders_every_part(self):
        from widget import Panel
        from pet import DesktopPet
        panel = Panel(live=False)
        pet = DesktopPet(panel)
        self.addCleanup(pet.close)
        pieces = transform.Pieces.build(pet._transform_side())
        stage = transform.TransformStage(pet, pieces, speed=50)
        image = QImage(stage.size(), QImage.Format_ARGB32_Premultiplied)
        for t in (0.2, 2.0, 4.0, 8.0, 10.5, 12.5):
            stage.t = t
            image.fill(Qt.transparent)
            stage.render(image)                     # No part of the timeline fails to draw.
        done = []
        stage.finished.connect(lambda: done.append(1))
        stage.start()
        stage._tick()
        self.assertEqual(done, [])
        stage.t = stage.timeline.length            # Time is up: the next frame finishes.
        stage._tick()
        self.assertEqual(done, [1])
        stage.close()

    def test_no_art_means_no_animation(self):
        with patch.dict(os.environ, PETOKEN_V2_1_ART=str(self.folder / 'missing')):
            self.assertFalse(transform.available())
            self.assertIsNone(transform.Pieces.build(120))


if __name__ == '__main__':
    unittest.main()
