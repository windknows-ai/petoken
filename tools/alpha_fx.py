"""Light-on-black effect pictures (drawn additively in the shows) -> pictures with real
transparency for Qt Quick: alpha = brightness, colour = colour / alpha. assets/v2_5/wish/alpha/."""
import sys
from pathlib import Path

from PySide6.QtGui import QColor, QGuiApplication, QImage

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'assets' / 'v2_5' / 'wish'
NAMES = ('sparkle_lavender', 'sparkle_champagne', 'sparkle_ice', 'sparkle_pearl', 'sparkle_haori', 'sparkle_xinghai',
         'hero_xinghai', 'hero_yinhe', 'hero_haori', 'flare')


def to_alpha(image, vignette=False):
    """``vignette``: fade to nothing towards the edges, so a turning picture never shows its square."""
    image = image.convertToFormat(QImage.Format_RGB32)
    out = QImage(image.size(), QImage.Format_ARGB32)
    w, h = image.width(), image.height()
    for y in range(image.height()):
        for x in range(image.width()):
            c = image.pixelColor(x, y)
            a = max(c.red(), c.green(), c.blue())
            if vignette:
                r = (((x + .5) / w - .5) ** 2 + ((y + .5) / h - .5) ** 2) ** .5 * 2   # 0 centre, 1 edge middle.
                fade = 1.0 if r < .62 else max(0.0, 1 - (r - .62) / .36)
                a = int(a * fade * fade * (3 - 2 * fade))
            if a < 2:
                out.setPixelColor(x, y, QColor(0, 0, 0, 0))
                continue
            k = 255 / a
            out.setPixelColor(x, y, QColor(min(255, int(c.red() * k)), min(255, int(c.green() * k)),
                                           min(255, int(c.blue() * k)), a))
    return out


def main():
    app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])  # noqa: F841
    target = SOURCE / 'alpha'
    target.mkdir(exist_ok=True)
    for name in NAMES:
        image = QImage(str(SOURCE / f'{name}.webp'))
        if image.width() > 256:
            image = image.scaledToWidth(256)
        to_alpha(image, vignette=name.startswith(('hero_', 'flare'))).save(str(target / f'{name}.png'))
        print(name)


if __name__ == '__main__':
    main()
