"""Gentle companion surfaces retain readable text and complete native controls."""
import unittest
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QComboBox
import theme
from widget import STYLE


def contrast(first, second):
    def luminance(value):
        c = QColor(value)
        channels = [v / 255 for v in (c.red(), c.green(), c.blue())]
        linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in channels]
        return sum(a * b for a, b in zip(linear, [.2126, .7152, .0722]))
    light, dark = sorted([luminance(first), luminance(second)], reverse=True)
    return (light + .05) / (dark + .05)


class CompanionThemeTests(unittest.TestCase):
    def test_native_analytics_selected_rows_keep_readable_companion_colors(self):
        from PySide6.QtGui import QPalette
        from PySide6.QtWidgets import QWidget
        from analytics_view import table, populate
        parent = QWidget()
        parent.setStyleSheet(STYLE)
        view = table(['Value'])
        view.setParent(parent)
        populate(view, [['Known subtotal']])
        view.selectRow(0)
        view.show()
        parent.show()
        self.app.processEvents()
        try:
            for group in [QPalette.Active, QPalette.Inactive]:
                foreground = view.palette().color(group, QPalette.HighlightedText).name()
                background = view.palette().color(group, QPalette.Highlight).name()
                self.assertEqual(foreground, theme.INK.lower())
                self.assertEqual(background, theme.TAB_SELECTED_BG.lower())
                self.assertGreaterEqual(contrast(foreground, background), 4.5)
        finally:
            parent.close()
            parent.deleteLater()

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_pearl_surfaces_and_readable_primary_secondary_accents(self):
        self.assertGreater(QColor(theme.BG).lightness(), 230)
        for background in [theme.BG, theme.CARD, theme.TABLE_BG, theme.TAB_SELECTED_BG]:
            for foreground in [theme.INK, theme.MUTED, theme.ICE, theme.VIOLET]:
                with self.subTest(background=background, foreground=foreground):
                    self.assertGreaterEqual(contrast(foreground, background), 4.5)

    def test_native_combo_dropdown_has_no_black_frame(self):
        combo = QComboBox()
        combo.setStyleSheet(STYLE)
        combo.addItems(['未分类', 'Project'])
        combo.resize(180, 40)
        combo.show()
        self.app.processEvents()
        try:
            image = combo.grab().toImage()
            scale = image.devicePixelRatio()
            black = sum(image.pixelColor(round(x * scale), round(y * scale)).lightness() < 35
                        for x in range(combo.width() - 25, combo.width() - 2)
                        for y in range(2, combo.height() - 2))
            self.assertEqual(black, 0)
            combo.setCurrentIndex(1)
            self.assertEqual(combo.currentText(), 'Project')
        finally:
            combo.close()
            combo.deleteLater()
