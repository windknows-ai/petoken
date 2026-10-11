"""Packs the rendered wishing-show lights (tools/render_wish_fx.py) for shipping:
the sky as JPEG, every sprite as WebP, into assets/v2_5/wish/."""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QGuiApplication, QImage

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'build' / 'wish_fx_png'
TARGET = ROOT / 'assets' / 'v2_5' / 'wish'


def main():
    app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])  # noqa: F841 (Qt image plugins)
    TARGET.mkdir(parents=True, exist_ok=True)
    total = 0
    for png in sorted(SOURCE.glob('*.png')):
        image = QImage(str(png))
        if png.stem == 'sky' or png.stem.startswith('sky_'):          # Full-frame layers: JPEG.
            out = TARGET / f'{png.stem}.jpg'
            image.save(str(out), 'JPG', 92)
        else:
            out = TARGET / f'{png.stem}.webp'
            image.save(str(out), 'WEBP', 92)
        total += out.stat().st_size
    print(f'{total / 1024:.0f} KB in {TARGET}')


if __name__ == '__main__':
    main()
