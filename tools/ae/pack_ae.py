"""Pack the After Effects renders (build/ae_out) into the show's frame sequences:
assets/v2_5/wish/seq/<name>/NN.jpg, light on black (drawn additively, so black adds nothing).

The charge is played backwards: rendered as light flying out, it becomes light pouring in.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'build' / 'ae_out'
TARGET = ROOT / 'assets' / 'v2_5' / 'wish' / 'seq'
SEQUENCES = dict(wishstar=dict(size=192), charge=dict(size=256, reverse=True),
                 **{f'reveal_{r}': dict(size=448) for r in ('fanxing', 'mingyue', 'haori', 'yinhe', 'xinghai')})


def main():
    app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])  # noqa: F841 (image plugins)
    total = 0
    for name, options in SEQUENCES.items():
        frames = sorted((SOURCE / name).glob('*.tif'))
        if not frames:
            print('missing', name)
            continue
        if options.get('reverse'):
            frames = frames[::-1]
        out = TARGET / name
        out.mkdir(parents=True, exist_ok=True)
        for old in out.glob('*.jpg'):
            old.unlink()
        for index, path in enumerate(frames):
            image = QImage(str(path)).convertToFormat(QImage.Format_ARGB32_Premultiplied)
            flat = QImage(image.size(), QImage.Format_RGB32)
            flat.fill(QColor(0, 0, 0))
            p = QPainter(flat)
            p.drawImage(0, 0, image)
            p.end()
            side = options['size']
            flat = flat.scaled(side, side, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            target = out / f'{index:02d}.jpg'
            flat.save(str(target), 'JPG', 90)
            total += target.stat().st_size
        print(f'{name}: {len(frames)} frames')
    print(f'{total / 1024:.0f} KB in {TARGET}')


if __name__ == '__main__':
    main()
