"""Package step: store 2.0 pose images at the size the pet ever draws them.

pet_assets.pose_source scales every frame and blink image down to
SOURCE_MAX_SIDE when it loads, so larger copies in the installer only cost
download size. The repository keeps Codex's 1254 px originals.
"""
import sys
from pathlib import Path


def main(folder):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QGuiApplication, QImage
    from pet_assets import SOURCE_MAX_SIDE
    app = QGuiApplication.instance() or QGuiApplication(['shrink'])
    count = 0
    for path in sorted(Path(folder).glob('*.png')):
        image = QImage(str(path))
        if image.isNull() or max(image.width(), image.height()) <= SOURCE_MAX_SIDE:
            continue
        small = image.scaled(SOURCE_MAX_SIDE, SOURCE_MAX_SIDE, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        if not small.save(str(path), 'PNG'):
            raise SystemExit(f'Cannot save {path}')
        count += 1
    print(f'Shrank {count} images in {folder}')
    del app


if __name__ == '__main__':
    main(sys.argv[1])
