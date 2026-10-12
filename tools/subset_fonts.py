"""Subset the bundled fonts to what Petoken shows: ASCII, punctuation, the 3,500 common Chinese
characters (GB 2312 level 1) plus every character in localization.py. Writes assets/fonts/."""
import re
import sys
from pathlib import Path

from fontTools import subset

ROOT = Path(__file__).resolve().parents[1]


def characters():
    chars = set(chr(c) for c in range(0x20, 0x7F))
    chars |= set('，。、；：？！“”‘’（）《》【】—…·～￥％＋－×÷→←↑↓★☆✦✧♪♥◆●○■□')
    for hi in range(0xB0, 0xD8):                         # GB 2312 level 1 (common characters).
        for lo in range(0xA1, 0xFF):
            try:
                chars.add(bytes([hi, lo]).decode('gb2312'))
            except UnicodeDecodeError:
                pass
    chars |= set((ROOT / 'localization.py').read_text(encoding='utf-8'))
    return ''.join(sorted(c for c in chars if c.isprintable()))


def main(source_dir):
    out = ROOT / 'assets' / 'fonts'
    out.mkdir(parents=True, exist_ok=True)
    text = characters()
    for name in ('NotoSansSC', 'NotoSerifSC'):
        options = subset.Options()
        options.layout_features = ['*']
        options.flavor = None
        font = subset.load_font(str(Path(source_dir) / f'{name}.ttf'), options)
        sub = subset.Subsetter(options)
        sub.populate(text=text)
        sub.subset(font)
        target = out / f'{name}.ttf'
        subset.save_font(font, str(target), options)
        print(name, f'{target.stat().st_size / 1e6:.1f} MB', len(text), 'characters')


if __name__ == '__main__':
    main(sys.argv[1])
