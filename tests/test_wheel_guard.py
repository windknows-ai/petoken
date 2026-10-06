"""The mouse wheel never changes a drop-down, number box or slider by accident."""
import unittest

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import (QApplication, QComboBox, QScrollArea, QSlider, QSpinBox, QVBoxLayout,
                               QWidget)

import widget

APP = QApplication.instance() or QApplication([])


def wheel(target, delta=-120):
    event = QWheelEvent(QPointF(5, 5), QPointF(target.mapToGlobal(QPoint(5, 5))), QPoint(0, 0),
                        QPoint(0, delta), Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False)
    QApplication.sendEvent(target, event)


class WheelGuardTests(unittest.TestCase):
    def test_wheel_scrolls_the_page_not_the_value(self):
        widget.install_wheel_guard()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        page = QWidget()
        layout = QVBoxLayout(page)
        combo, spin, slider = QComboBox(), QSpinBox(), QSlider(Qt.Horizontal)
        combo.addItems(['a', 'b', 'c'])
        spin.setRange(0, 10)
        spin.setValue(5)
        slider.setRange(0, 10)
        slider.setValue(5)
        for item in (combo, spin, slider):
            layout.addWidget(item)
        layout.addSpacing(2000)
        scroll.setWidget(page)
        scroll.resize(200, 200)
        scroll.show()
        APP.processEvents()
        for item in (combo, spin, slider):
            wheel(item)
        self.assertEqual((combo.currentIndex(), spin.value(), slider.value()), (0, 5, 5))
        self.assertGreater(scroll.verticalScrollBar().value(), 0)      # The page moved.
        scroll.deleteLater()


if __name__ == '__main__':
    unittest.main()
