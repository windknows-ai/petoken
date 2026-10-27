"""Outfit packs (2.5.1): the installer carries only what the wardrobe mirror shows of each outfit
(its first idle, greeting and cheer pictures); the rest of an outfit, every action of hers in it,
is downloaded once she owns it (bought or wished for) and kept in ``%LOCALAPPDATA%\\CodexWisp\\outfits``.

The build zips each outfit tier (tools/pack_outfits.py) and writes ``packs.json`` beside the
outfits: file name, size, SHA-256 and picture count of each pack. The packs sit on their own
GitHub pre-release (``outfits-v1``), so update checks never see it. A download whose hash does not
match is thrown away; a pack is unpacked into a temporary folder and only renamed into place when
complete. Run from the repository (no ``packs.json``) every outfit is already whole.

Packs are named by their content, so every later release adds only the packs that changed and
older versions keep finding theirs.

``PETOKEN_OUTFIT_PACKS`` (a folder or an https address ending in /) replaces the download place for QA.
"""
from __future__ import annotations

import functools
import hashlib
import json
import os
import re
import shutil
import threading
import urllib.request
import zipfile
from pathlib import Path

from PySide6.QtCore import QObject, Signal

import pet_assets

OUTFIT_DIR = pet_assets.ASSETS_DIR / 'v2_5' / 'outfits'
PACKS_FILE = OUTFIT_DIR / 'packs.json'
BASE_URL = 'https://github.com/windknows-ai/petoken/releases/download/outfits-v1/'
ROOT = Path(os.environ.get('LOCALAPPDATA', str(Path.home() / '.local/share'))) / 'CodexWisp' / 'outfits'
DONE = '.complete'
TIMEOUT_S = 30
_MEMBER = re.compile(r'^[A-Za-z0-9_.-]+\.(webp|png|json)$')
# The pictures the mirror shows (wardrobe.POSES and the core poses they fall back to): kept in the package.
PREVIEW = ('idle', 'greet_morning', 'cheer', 'thumbs_up', 'ready_go', 'wave', 'celebrate')


@functools.lru_cache(maxsize=1)
def manifest():
    """{outfit name: dict(file, sha256, size, count)}; empty when every outfit came whole."""
    try:
        data = json.loads(PACKS_FILE.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def pack_folder(series, tier):
    return ROOT / series / tier


def ready(item):
    """Whether all of this outfit's pictures are here (in the package, or downloaded)."""
    if item is None or item.get('set') != 'outfit':
        return True
    if item['name'] not in manifest():
        return True
    return (pack_folder(item['series'], item['tier']) / DONE).is_file()


def folder(series, tier):
    """Where this outfit's pictures are read from: the downloaded pack once whole, else the package."""
    pack = pack_folder(series, tier)
    return pack if (pack / DONE).is_file() else OUTFIT_DIR / series / tier


def _source(name):
    base = os.environ.get('PETOKEN_OUTFIT_PACKS') or BASE_URL
    return base + name if base.startswith('https://') else str(Path(base) / name)


def _read(name, size, progress=None, opener=None):
    """The pack's bytes, reporting progress (0..1) as they come."""
    source = _source(name)
    if not source.startswith('https://'):
        data = Path(source).read_bytes()
        if progress:
            progress(1.0)
        return data
    request = urllib.request.Request(source, headers={'User-Agent': 'Petoken-outfits'})
    chunks, got = [], 0
    with (opener or urllib.request.urlopen)(request, timeout=TIMEOUT_S) as response:
        while True:
            chunk = response.read(256 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
            got += len(chunk)
            if got > size * 1.05 + 1024:
                raise ValueError('Download larger than expected')
            if progress and size:
                progress(min(1.0, got / size))
    return b''.join(chunks)


def fetch(item, progress=None, opener=None):
    """Download, check and unpack one outfit; raise OSError / ValueError when it cannot."""
    entry = manifest().get(item['name'])
    if entry is None or ready(item):
        return
    data = _read(entry['file'], int(entry.get('size') or 0), progress, opener)
    if hashlib.sha256(data).hexdigest() != entry['sha256']:
        raise ValueError('Checksum mismatch: the download was not used')
    target = pack_folder(item['series'], item['tier'])
    temp = target.with_name(target.name + '.part')
    shutil.rmtree(temp, ignore_errors=True)
    temp.mkdir(parents=True)
    import io
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = archive.namelist()
        if not names or any(not _MEMBER.match(n) for n in names):
            raise ValueError('Unexpected file in the outfit pack')
        for name in names:
            (temp / name).write_bytes(archive.read(name))
    if len(names) < int(entry.get('count') or 0):
        raise ValueError('The outfit pack is incomplete')
    (temp / DONE).write_text(entry['sha256'], encoding='utf-8')
    shutil.rmtree(target, ignore_errors=True)
    temp.replace(target)


class OutfitPacks(QObject):
    """Downloads owned outfits one at a time on a worker thread; tells the panel when one is whole."""
    progressed = Signal(str, float)
    finished = Signal(str, bool)

    def __init__(self, panel, enabled=False):
        super().__init__(panel)
        self.panel = panel
        self.enabled = enabled
        self.state = {}                  # outfit id -> fraction downloaded, or 'failed'
        self._queue = []
        self._lock = threading.Lock()
        self._worker = None
        self.progressed.connect(self._progressed)
        self.finished.connect(self._finished)

    def status(self, item):
        """None when whole, else a fraction downloaded so far or 'failed'."""
        if ready(item):
            return None
        return self.state.get(item['id'], 0.0)

    def want(self, item_id):
        """She owns this now: fetch it if it is an outfit not here yet."""
        import shop
        item = shop.BY_ID.get(item_id)
        if not self.enabled or item is None or ready(item):
            return
        with self._lock:
            if item_id in self._queue:
                return
            self._queue.append(item_id)
            self.state[item_id] = 0.0
            if self._worker is None or not self._worker.is_alive():
                self._worker = threading.Thread(target=self._work, name='petoken-outfits', daemon=True)
                self._worker.start()

    def ensure(self):
        """Every owned outfit that is not here yet (after an update, or a failed download)."""
        store = getattr(self.panel, 'shop', None)
        if store is None:
            return
        for item_id in sorted(store.owned()):
            if item_id.startswith('outfit.'):
                self.want(item_id)

    def _work(self):
        import shiboken6
        import shop
        while True:
            with self._lock:
                if not self._queue:
                    self._worker = None
                    return
                item_id = self._queue[0]
            ok = True
            try:
                fetch(shop.BY_ID[item_id], lambda share: shiboken6.isValid(self)
                      and self.progressed.emit(item_id, share))
            except (OSError, ValueError, zipfile.BadZipFile):
                ok = False
            with self._lock:
                self._queue.remove(item_id)
            if not shiboken6.isValid(self):
                return
            self.finished.emit(item_id, ok)

    def _progressed(self, item_id, share):
        last = self.state.get(item_id)
        self.state[item_id] = share
        if not isinstance(last, float) or int(share * 20) != int(last * 20):
            self._wardrobe_refresh()

    def _finished(self, item_id, ok):
        if ok:
            self.state.pop(item_id, None)
            import outfits
            outfits.forget()
            hook = getattr(self.panel, 'shop_worn_changed', None)
            if hook is not None:
                hook()                                  # She wears all of it now.
        else:
            self.state[item_id] = 'failed'
            self._wardrobe_refresh()

    def _wardrobe_refresh(self):
        window = getattr(self.panel, 'wardrobe_window', None)
        if window is not None and window.isVisible():
            window.refresh()
