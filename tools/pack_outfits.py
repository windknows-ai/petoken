"""Build step (2.5.1): zip each outfit tier of the package into its own download, keep only the
mirror's pictures in the package, and write packs.json for outfit_packs.py.

    python tools/pack_outfits.py <package outfits folder> <folder for the zips>
"""
from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from outfit_packs import PREVIEW  # noqa: E402

TIERS = ('xinghai', 'yinhe', 'haori', 'mingyue', 'fanxing')


def kept(name):
    """A picture the mirror shows: the first frame (or blink) of one of its poses."""
    stem = name.rsplit('.', 1)[0]
    return any(stem in (f'{pose}_1', f'{pose}_blink') for pose in PREVIEW)


def main(outfits, out):
    outfits, out = Path(outfits), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for series in sorted(p for p in outfits.iterdir() if p.is_dir()):
        for tier in TIERS:
            folder = series / tier
            pictures = sorted(p for p in folder.glob('*') if p.suffix in ('.webp', '.png')) if folder.is_dir() else []
            if not pictures:
                continue
            temp = out / f'outfit-{series.name}-{tier}.part'
            with zipfile.ZipFile(temp, 'w', zipfile.ZIP_STORED) as archive:     # WebP is compressed already.
                for picture in pictures:                    # Fixed dates: the same pictures, the same zip.
                    entry = zipfile.ZipInfo(picture.name, date_time=(2026, 1, 1, 0, 0, 0))
                    archive.writestr(entry, picture.read_bytes())
            data = temp.read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            name = f'outfit-{series.name}-{tier}-{digest[:12]}.zip'     # Named by content: old versions keep theirs.
            temp.replace(out / name)
            manifest[f'{series.name}_{tier}'] = dict(file=name, sha256=digest, size=len(data), count=len(pictures))
            for picture in pictures:
                if not kept(picture.name):
                    picture.unlink()
    (outfits / 'packs.json').write_text(json.dumps(manifest, indent=1), encoding='utf-8')
    return manifest


if __name__ == '__main__':
    print(f'Packed {len(main(sys.argv[1], sys.argv[2]))} outfits into {sys.argv[2]}')
