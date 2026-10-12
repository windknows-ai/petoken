"""What every Qt Quick window of Petoken shares (2.5).

The look lives in ui/Petoken (Theme, WindowShell, GemButton...). This module is the Python side
around it: the bundled fonts, sharp native text, links to icons and lights, the window operations
a frameless window needs (`HostBridge`), and `QuickWindow`, the rounded, shadowed, translucent
top-level window one QML page is shown in.
"""
from __future__ import annotations

import functools
from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Qt, Slot
from PySide6.QtGui import QFontDatabase, QRegion
from PySide6.QtQuick import QQuickImageProvider, QQuickWindow
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import QWidget

import pet_assets
from localization import text

ROOT = Path(__file__).resolve().parent
QML_DIR = ROOT / 'ui'
MARGIN = 14                         # The window's shadow margin (WindowShell.margin).
RADIUS = 30                         # Its corner radius (Theme.windowRadius).
_FONTS = []


def load_fonts():
    """The bundled fonts (assets/fonts, SIL OFL): Noto Sans SC for words, Noto Serif SC for titles."""
    if not _FONTS:
        for path in sorted((pet_assets.ASSETS_DIR / 'fonts').glob('*.ttf')):
            _FONTS.append(QFontDatabase.addApplicationFont(str(path)))
        # Words drawn by the system's font renderer (hinted, ClearType-sharp), not scaled glyph
        # textures, which look soft at the small sizes of Chinese labels.
        QQuickWindow.setTextRenderType(QQuickWindow.TextRenderType.NativeTextRendering)
    return _FONTS


def file_url(path):
    return QUrl.fromLocalFile(str(path)).toString()


# Names a newer brief gave pieces Codex had already drawn under another name.
_ART_ALIAS = {}


@functools.lru_cache(maxsize=512)
def ui_art(name):
    """A picture Codex drew for the interface (assets/ui/<name>.png or assets/ui/<part>/<name>.png),
    or '' while it has none."""
    if not name:
        return ''
    folder = pet_assets.ASSETS_DIR / 'ui'
    for candidate in (name, _ART_ALIAS.get(name)):
        if not candidate:
            continue
        if (folder / f'{candidate}.png').is_file():
            return file_url(folder / f'{candidate}.png')
        for path in sorted(folder.glob(f'*/{candidate}.png')):
            return file_url(path)
    return ''


class Icons(QQuickImageProvider):
    """image://icon/<name>/<filled 0|1>/<colour without #>: a Phosphor icon drawn in that colour at the
    size asked (no shader per icon: dozens of tinted icons cost nothing to draw)."""

    def __init__(self):
        super().__init__(QQuickImageProvider.Image)
        self._cache = {}

    def requestImage(self, ident, size, requested):
        from PySide6.QtCore import QRectF
        from PySide6.QtGui import QColor, QImage, QPainter
        from PySide6.QtSvg import QSvgRenderer
        name, _, rest = ident.partition('/')
        filled, _, colour = rest.partition('/')
        side = max(8, requested.width() if requested.width() > 0 else 40)
        key = (name, filled, colour, side)
        if key not in self._cache:
            folder = pet_assets.ASSETS_DIR / 'icons' / ('fill' if filled == '1' else 'regular')
            path = folder / (f'{name}-fill.svg' if filled == '1' else f'{name}.svg')
            image = QImage(side, side, QImage.Format_ARGB32_Premultiplied)
            image.fill(0)
            p = QPainter(image)
            p.setRenderHint(QPainter.Antialiasing)
            QSvgRenderer(str(path)).render(p, QRectF(0, 0, side, side))
            p.setCompositionMode(QPainter.CompositionMode_SourceIn)
            p.fillRect(image.rect(), QColor('#' + colour[:8]) if colour else QColor('white'))
            p.end()
            if len(self._cache) > 600:
                self._cache.clear()
            self._cache[key] = image
        return self._cache[key]


class _Icons(QQuickImageProvider):
    """The shared icon store, registered in an engine (a provider belongs to the engine it is in)."""

    def __init__(self):
        super().__init__(QQuickImageProvider.Image)

    def requestImage(self, ident, size, requested):
        return icons().requestImage(ident, size, requested)


_ICONS = None


def icons():
    global _ICONS
    if _ICONS is None:
        _ICONS = Icons()
    return _ICONS


class HostBridge(QObject):
    """The window operations and lookups every page's `bridge` offers (WindowShell uses them)."""

    def __init__(self, window, panel):
        super().__init__(window)
        self.window, self.panel = window, panel

    @property
    def language(self):
        return self.panel.prefs.get('language', 'zh_CN')

    def _t(self, key, **values):
        return text(key, self.language, **values)

    @Slot(str, result=str)
    def tr(self, key):
        base, _, part = key.partition('@')                  # 'shop_featured@title' / '@note': a heading
        if part:                                            # and its bracketed aside, shown apart.
            import re
            found = re.match(r'^(.*?)\s*[（(](.*)[）)]\s*$', self._t(base))
            if found is None:
                return self._t(base) if part == 'title' else ''
            return found.group(1) if part == 'title' else found.group(2)
        return self._t(key)

    @Slot(str, bool, result=str)
    def iconUrl(self, name, filled):
        if not name:
            return ''
        folder = pet_assets.ASSETS_DIR / 'icons' / ('fill' if filled else 'regular')
        return file_url(folder / (f'{name}-fill.svg' if filled else f'{name}.svg'))

    @Slot(str, result=str)
    def artUrl(self, name):
        return ui_art(name)

    @Slot(str, result=str)
    def wardrobeUrl(self, name):
        return file_url(pet_assets.ASSETS_DIR / 'v2_5' / 'wardrobe' / f'{name}.png')

    @Slot(str, result=str)
    def fxUrl(self, name):
        """A light: the sky as JPEG, glows with real transparency (tools/alpha_fx.py)."""
        from wish_show import FX_DIR
        if name.startswith('sky'):
            return file_url(FX_DIR / f'{name}.jpg')
        alpha = FX_DIR / 'alpha' / f'{name}.png'
        return file_url(alpha if alpha.is_file() else FX_DIR / f'{name}.webp')

    @Slot()
    def close(self):
        self.window.close()

    @Slot()
    def minimize(self):
        self.window.showMinimized()

    @Slot()
    def toggleMaximized(self):
        if self.window.isMaximized():
            self.window.showNormal()
        else:
            self.window.showMaximized()

    @Slot()
    def startMove(self):
        handle = self.window.windowHandle()
        if handle is not None:
            handle.startSystemMove()

    @Slot()
    def startResize(self):
        handle = self.window.windowHandle()
        if handle is not None:
            handle.startSystemResize(Qt.BottomEdge | Qt.RightEdge)


class QuickWindow(QWidget):
    """A frameless, translucent window showing one QML page (its root is a WindowShell)."""

    def __init__(self, parent=None, flags=Qt.Window):
        super().__init__(parent, flags | Qt.FramelessWindowHint)
        load_fonts()
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.view = QQuickWidget(self)
        self.view.setClearColor(Qt.transparent)
        self.view.setResizeMode(QQuickWidget.SizeRootObjectToView)
        self.view.engine().addImportPath(str(QML_DIR))
        self.view.engine().addImageProvider('icon', _Icons())
        self.errors = []

    def load(self, qml, **context):
        """Show ``qml`` (a file in ui/Petoken), with ``context`` as its context properties."""
        for name, value in context.items():
            self.view.rootContext().setContextProperty(name, value)
        self.view.setSource(QUrl.fromLocalFile(str(QML_DIR / 'Petoken' / qml)))
        self.errors = [e.toString() for e in self.view.errors()]
        return self.errors

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.view.setGeometry(self.rect())

    # The rounded body overlays (the wish show, the discount draw) play inside.
    def overlay_rect(self):
        return self.rect().adjusted(MARGIN + 1, MARGIN + 1, -MARGIN - 1, -MARGIN - 1)

    @staticmethod
    def overlay_mask(size, radius=RADIUS - 1):
        w, h = size.width(), size.height()
        region = QRegion(radius, 0, w - 2 * radius, h).united(QRegion(0, radius, w, h - 2 * radius))
        for x, y in ((0, 0), (w - 2 * radius, 0), (0, h - 2 * radius), (w - 2 * radius, h - 2 * radius)):
            region = region.united(QRegion(x, y, 2 * radius, 2 * radius, QRegion.Ellipse))
        return region
