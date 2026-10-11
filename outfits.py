"""Shop outfits (2.5): Codex drew each outfit tier as 22 frames of her core poses
(assets/v2_5/outfits/<series>/<rarity>/<pose>_<n>.png, plus blinks). Worn, every pose shows the
outfit's picture of that pose, or of the nearest core pose (a cheer uses its celebrate frames, a
morning greeting its wave). Her Starsea form, night pajamas and game form keep their own art.
"""
from __future__ import annotations

import functools

import pet_assets

OUTFIT_DIR = pet_assets.ASSETS_DIR / 'v2_5' / 'outfits'
SERIES = dict(starsea_gown=('星海长裙', 'Starsea Gown'), frost_coat=('霜雪外套', 'Frost Coat'))
THEME = dict(starsea_gown='starsea', frost_coat='frost')
TIER = dict(xinghai=('星海', 'Starsea'), yinhe=('银河', 'Galaxy'), haori=('皓日', 'Sun'), mingyue=('明月', 'Moon'),
            fanxing=('繁星', 'Stars'))
CORE = ('idle', 'typing', 'celebrate', 'sad', 'wave', 'thinking', 'sleep', 'headpat', 'poked', 'dragged')
NEAREST = dict(
    codex_working='typing', microphone='idle', music='idle', guitar='idle',
    cheer='celebrate', clap='celebrate', thumbs_up='celebrate', proud='celebrate', heart='celebrate', hug='headpat',
    mvp='celebrate', ready_go='wave', greet_morning='wave', greet_night='wave', peek='thinking', curious='thinking',
    focus_read='thinking', focus_tea='idle', focus_done='celebrate', stretch_break='idle', hold_card='idle',
    packing='idle', grievance='sad', worried='sad', pout='sad', shy='headpat', coquettish='headpat',
    headpat_happy='headpat', surprised='poked', landing='dragged', bored='idle', yawn='sleep', wake_stretch='idle')
# States that are a different look of hers already: an outfit never covers them.
OWN_LOOK = ('star_', 'night_', 'game_', 'form2', 'xform', 'awaken')


def catalog(prices):
    """The drawn outfits as shop items (one per series and tier)."""
    items = []
    if not OUTFIT_DIR.is_dir():
        return items
    for series in sorted(p.name for p in OUTFIT_DIR.iterdir() if p.is_dir()):
        for tier in ('xinghai', 'yinhe', 'haori', 'mingyue', 'fanxing'):
            folder = OUTFIT_DIR / series / tier
            if not (folder / 'idle_1.png').is_file():
                continue
            zh, en = SERIES.get(series, (series, series))
            items.append(dict(id=f'outfit.{series}_{tier}', set='outfit', name=f'{series}_{tier}', rarity=tier,
                              slot='outfit', price=prices.get(tier), theme=THEME.get(series), window=None,
                              names=dict(zh_CN=f'{zh}·{TIER[tier][0]}', en_US=f'{en} · {TIER[tier][1]}',
                                         en=f'{en} · {TIER[tier][1]}'),
                              art=['idle_1.png'], art_dir=f'outfits/{series}/{tier}', series=series, tier=tier))
    return items


def core_pose(state):
    if state is None or state.startswith(OWN_LOOK):
        return None
    if state in CORE:
        return state
    return NEAREST.get(state, 'idle')


@functools.lru_cache(maxsize=256)
def _frames(series, tier, pose):
    folder = OUTFIT_DIR / series / tier
    found = sorted(folder.glob(f'{pose}_[0-9].png'))
    return tuple(str(p.relative_to(pet_assets.ASSETS_DIR.parent)).replace('\\', '/') for p in found)


def frame_path(item, state, index=0, blink=False):
    """The outfit picture for ``state`` (frame ``index``, or its blink), or None to keep her own."""
    pose = core_pose(state)
    if item is None or pose is None:
        return None
    if blink:
        path = OUTFIT_DIR / item['series'] / item['tier'] / f'{pose}_blink.png'
        if path.is_file():
            return str(path.relative_to(pet_assets.ASSETS_DIR.parent)).replace('\\', '/')
    frames = _frames(item['series'], item['tier'], pose) or _frames(item['series'], item['tier'], 'idle')
    return frames[index % len(frames)] if frames else None


def pixmap(item, state, index=0, blink=False):
    path = frame_path(item, state, index, blink)
    return pet_assets.pose_source(path) if path else None
