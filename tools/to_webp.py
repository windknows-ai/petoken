"""Re-encode a folder's PNGs as WebP (alpha kept) for the package: python tools/to_webp.py <folder>.
The app reads either (outfits.py looks for .webp first)."""
import sys
from pathlib import Path

from PySide6.QtGui import QGuiApplication, QImage


def main(folder):
    app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])  # noqa: F841 (image plugins)
    count = 0
    for png in sorted(Path(folder).rglob('*.png')):
        image = QImage(str(png))
        if image.isNull() or not image.save(str(png.with_suffix('.webp')), 'WEBP', 90):
            continue
        png.unlink()
        count += 1
    print(f'WebP {count} images in {folder}')


if __name__ == '__main__':
    main(sys.argv[1])
