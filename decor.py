"""Wearing the shop's decorations (2.5).

Codex drew 60 pieces in five kinds (assets/v2_5/shop/manifest.json). Each has
an anchor: the point that touches her (a hat's lower middle) or its centre.

- head: on top of her head. The head top is found in each pose's picture
  (the highest opaque pixels near the middle), so it follows every pose;
  hidden while she lies down.
- back: behind her, around her upper body (wings, capes, wheels).
- ground: under her feet (cushions, circles, pools).
- buddy: a little friend floating beside her, two frames.
- star: replaces the crystal of every task star on the ring (widget.TaskOrbWindow).

The pieces live in two click-through layers that follow her: one just behind
her window and one just in front, so big wings are never cut off by her own
window. They use the same motion as her picture (lift, tilt, squash), so a
hop carries the hat along.
"""
from __future__ import annotations

import functools
import math
import sys
import time

from PySide6.QtCore import QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QWidget

import pet_geometry as geometry
import shop

LYING = frozenset({'sleep', 'star_sleep', 'dragged', 'star_dragged', 'landing', 'peek'})
SCALE = .42 / 336             # A Stars-rarity hat (336 px wide) is .42 of her sprite box; all pieces share it.
BEHIND = ('ground', 'back', 'weapon')
FRONT = ('buddy', 'head', 'weapon')
# How each piece sits on her, beyond the kind's rule: scale, nudge (fractions of her sprite box),
# turn (degrees) and, for clips and flowers, 'side' (pinned at the side of her head, not on top).
# Checked one by one on her idle, wave, typing and thinking poses.
FIT = {
    'head_cloud_beret': dict(scale=1.2, dy=.075), 'head_moon_sleepcap': dict(scale=1.22, dy=.085),
    'head_celestial_beret': dict(scale=1.18, dy=.075, angle=-6), 'head_moon_rabbit_hat': dict(scale=1.15, dy=.08),
    'head_prism_crown': dict(dy=.04), 'head_lunar_tiara': dict(dy=.045), 'head_crystal_circlet': dict(dy=.04),
    'head_pearl_tiara': dict(dy=.045), 'head_orbit_halo': dict(dy=-.015), 'head_lavender_wreath': dict(scale=1.05, dy=.05),
    'head_frost_cat_ears': dict(dy=.055), 'head_lilac_rabbit_ears': dict(dy=.05), 'head_aurora_antlers': dict(dy=.045),
    'head_star_bow': dict(dx=-.1, dy=.05, angle=-14, scale=.9), 'head_butterfly_ribbon': dict(dx=-.1, dy=.05, angle=-12, scale=.9),
    'head_crescent_clip': dict(side=True, scale=.62, angle=-30), 'head_pearl_flower': dict(side=True, scale=.6, angle=-20),
    'head_crystal_sprout': dict(side=True, scale=.62, angle=-28),
    'back_cloud_wings': dict(scale=1.5, dy=-.05), 'back_butterfly_wings': dict(scale=1.42, dy=-.04),
    'back_moon_ribbon': dict(scale=1.55, dy=-.02), 'back_crystal_wings': dict(scale=1.18, dy=-.04),
    'ground_lavender_garden': dict(scale=1.18), 'ground_star_disc': dict(scale=1.22), 'ground_moon_ripple': dict(scale=1.1),
}
# Bulky weapons drawn smaller so they never hide her face.
WEAPON_SCALE = dict(sakura_fan=.6, crystal_orb=.6, star_shield=.55, star_harp=.62, small_umbrella=.68,
                    small_hammer=.66, star_kite=.72, starlight_whip=.82, moon_lantern=.9)
HANDS_FILE = shop.WEAPONS / 'hands.json'
_HANDS = None


def hands():
    """{frame file: hand} measured by Codex for every pose frame (None where no hand can hold)."""
    global _HANDS
    if _HANDS is None:
        try:
            import json
            _HANDS = {e['file']: (None if e.get('none') else e) for e in json.loads(HANDS_FILE.read_text(encoding='utf-8'))}
        except (OSError, ValueError, KeyError):
            _HANDS = {}
    return _HANDS


_DOMINANT = {}


def dominant_hand(prefix):
    """The hand most frames of a pose hold with ('dragged' holds left in three frames of four):
    a stray frame using the other hand must not throw the weapon across her."""
    if prefix not in _DOMINANT:
        counts = {}
        for path, hand in hands().items():
            if hand and path.rsplit('/', 1)[-1].rsplit('_', 1)[0] == prefix:
                counts[hand['hand']] = counts.get(hand['hand'], 0) + 1
        _DOMINANT[prefix] = max(counts, key=counts.get) if counts else None
    return _DOMINANT[prefix]


@functools.lru_cache(maxsize=512)
def frame_file(state, index=0, blink=False):
    """The picture file she shows for ``state`` (its ``index`` frame, or its blink)."""
    import pet_assets
    try:
        entry = pet_assets.entry_for(state)
        if blink and entry.blink:
            return entry.blink
        frames = pet_assets.existing_frames(entry)
        return frames[index % len(frames)] if frames else entry.path
    except (AttributeError, KeyError, ZeroDivisionError):
        return None
STAR = None                   # The worn task-star style (an item), read by the task stars.
_HEADS = {}


def head_box(pixmap):
    """(centre x, top y, width) of her head as fractions of ``pixmap``: the top is the first row wide
    enough to be her head (not the feather); the centre and width are the medians of the hair's left
    and right edges over the head's top band, so the thin feather on one side never pulls them."""
    key = pixmap.cacheKey()
    if key not in _HEADS:
        image = pixmap.toImage().convertToFormat(QImage.Format_ARGB32).scaledToWidth(128, Qt.FastTransformation)
        w, h = image.width(), image.height()
        found = (.5, .12, .5)
        top = None
        lefts, rights = [], []
        for y in range(h):
            xs = [x for x in range(int(w * .15), int(w * .85)) if (image.pixel(x, y) >> 24) > 140]
            if top is None:
                if len(xs) >= w * .12:
                    top = y
                else:
                    continue
            if y > top + h * .1:
                break
            runs, start = [], None                          # The widest unbroken run is her head;
            for x in xs + [None]:                           # the feather is a thin run of its own.
                if start is None:
                    start = prev = x
                elif x is None or x != prev + 1:
                    runs.append((start, prev))
                    start = prev = x
                else:
                    prev = x
            if runs:
                left, right = max(runs, key=lambda r: r[1] - r[0])
                lefts.append(left)
                rights.append(right)
        if top is not None and lefts:
            lefts.sort()
            rights.sort()
            left, right = lefts[len(lefts) // 2], rights[len(rights) // 2]
            found = ((left + right) / 2 / w, top / h, (right - left) / w)
        if len(_HEADS) > 256:
            _HEADS.clear()
        _HEADS[key] = found
    return _HEADS[key]


def head_top(pixmap):
    """(x, y) fractions of ``pixmap`` where the top of her head is."""
    x, y, _ = head_box(pixmap)
    return x, y


def worn_items(panel):
    """{slot: item} of the decorations she wears now."""
    store = getattr(panel, 'shop', None)
    if store is None:
        return {}
    items = {}
    for slot, item_id in store.equipped().items():
        item = shop.BY_ID.get(item_id)
        if item is not None and item.get('art') and item_id in store.owned():
            items[slot] = item
    return items


class DecorLayer(QWidget):
    def __init__(self, decor, front):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                         | Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.decor, self.front = decor, front

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        self.decor.paint(p, self)
        p.end()


class Decor:
    def __init__(self, pet):
        self.pet = pet
        self.items = {}
        self.back = self.front = None
        self.pose = None              # (state, pixmap, transform, drawn rect) of her last paint.

    # Which pieces, and the two layers ---------------------------------------------------
    def layers(self):
        return [w for w in (self.back, self.front) if w is not None and w.isVisible()]

    def refresh(self):
        """Re-read what she wears and show or hide the layers."""
        global STAR
        self.items = worn_items(self.pet.panel)
        STAR = self.items.get('star')
        wanted = {'back': any(s in self.items for s in BEHIND), 'front': any(s in self.items for s in FRONT)}
        shown = self.pet.isVisible() and not getattr(self.pet, 'veiled', False)
        for name, front in (('back', False), ('front', True)):
            layer = getattr(self, name)
            if wanted[name] and shown:
                if layer is None:
                    layer = DecorLayer(self, front)
                    setattr(self, name, layer)
                self._place(layer)
                if not layer.isVisible():
                    layer.show()
                layer.update()
            elif layer is not None:
                layer.hide()
        self.restack()
        manager = getattr(self.pet.panel, 'task_manager', None)
        for orb in getattr(manager, '_windows', {}).values() if manager is not None else ():
            orb.update()                                    # The task stars take the new style.

    def area(self):
        """The layers' rectangle: her window with room for wings, the ground and a buddy."""
        g = self.pet.geometry()
        w, h = g.width(), g.height()
        return QRect(g.x() - int(w * .55), g.y() - int(h * .25), int(w * 2.1), int(h * 1.5))

    def _place(self, layer):
        area = self.area()
        if layer.geometry() != area:
            if layer.size() == area.size():
                layer.move(area.topLeft())                  # Moving only: never a resize mid-drag.
            else:
                layer.setGeometry(area)

    def sync(self):
        """She moved: the layers follow at once."""
        for layer in self.layers():
            self._place(layer)
        self.restack()

    def restack(self):
        """Behind layer directly under her window, front layer directly over it."""
        if sys.platform != 'win32' or not self.layers():
            return
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.WinDLL('user32', use_last_error=True)
            user32.SetWindowPos.argtypes = (wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                            ctypes.c_int, ctypes.c_int, wintypes.UINT)
            user32.GetWindow.argtypes = (wintypes.HWND, wintypes.UINT)
            user32.GetWindow.restype = wintypes.HWND
            flags = 0x0001 | 0x0002 | 0x0010 | 0x0200       # No size, no move, no activate, no owner order.
            pet = int(self.pet.winId())
            if self.back is not None and self.back.isVisible():
                handle = int(self.back.winId())
                if (user32.GetWindow(pet, 2) or 0) != handle:          # GW_HWNDNEXT: directly below.
                    user32.SetWindowPos(handle, pet, 0, 0, 0, 0, flags)
            if self.front is not None and self.front.isVisible():
                handle = int(self.front.winId())
                above = user32.GetWindow(pet, 3) or 0                  # GW_HWNDPREV: directly above.
                if above != handle:
                    user32.SetWindowPos(handle, above or -1, 0, 0, 0, 0, flags)
        except (OSError, AttributeError):
            pass

    # Her picture --------------------------------------------------------------------------
    def pet_painted(self, state, pixmap, transform, rect, source=None):
        """Called from her paint with what she drew (``source``: its file), and how it was placed."""
        if not self.layers():
            return
        self.source = source
        moving = self._step_weapon() if 'weapon' in self.items else False
        pose = (state, pixmap.cacheKey(), transform, QRectF(rect))
        if (self.pose is None or pose[1:] != self.pose[1:] or pose[0] != self.pose[0] or 'buddy' in self.items
                or moving):
            self.pose = (state, pixmap, transform, QRectF(rect))
            for layer in self.layers():
                layer.update()

    def _weapon_target(self, now):
        """Where the weapon wants to be: (x, y as fractions of her picture, angle, scale, in front)."""
        source = getattr(self, 'source', None) or ''
        hand = hands().get(source)
        prefix = source.rsplit('/', 1)[-1].rsplit('_', 1)[0]
        if hand is not None and hand['hand'] != dominant_hand(prefix):
            hand = None                                     # A stray frame: keep the hand it had.
            held = getattr(self, '_held', None)
            if held is not None and held[0] == prefix:
                hand = held[1]
        if hand is not None:
            self._held = (prefix, hand)
            angle = hand.get('angle', 0)
            return hand['x'] / 1254, hand['y'] / 1254, angle - 360 if angle > 180 else angle, 1.0, \
                bool(hand.get('front', True))
        self._held = None
        return .9, .62 + math.sin(now * 1.8) * .025, 22 + math.sin(now * 1.2) * 4, .62, False

    def _step_weapon(self):
        """Ease the weapon towards where it wants to be (no jumps between frames). True while moving."""
        now = time.monotonic()
        last = getattr(self, '_wtime', None)
        if last is not None and now - last < .004:
            return getattr(self, '_wmoving', False)
        self._wtime = now
        target = self._weapon_target(now)
        state = getattr(self, '_wpose', None)
        if state is None or last is None or now - last > .5:
            self._wpose = list(target)
            self._wmoving = False
            return False
        blend = 1 - math.exp(-(now - last) / .07)
        turn = (target[2] - state[2] + 180) % 360 - 180
        new = [state[0] + (target[0] - state[0]) * blend, state[1] + (target[1] - state[1]) * blend,
               state[2] + turn * blend, state[3] + (target[3] - state[3]) * blend, target[4]]
        self._wmoving = abs(new[0] - state[0]) + abs(new[1] - state[1]) > .0005 or abs(turn) > .3
        self._wpose = new
        return self._wmoving

    def paint(self, p, layer):
        if self.pose is None:
            return
        from shop_view import item_art
        state, pixmap, transform, rect = self.pose
        offset = self.pet.pos() - layer.pos()
        p.translate(offset.x(), offset.y())
        p.setTransform(transform, True)
        side = geometry.scaled_sprite_rect(self.pet.pet_scale)[2]
        scale = side * SCALE
        now = time.monotonic()
        lying = state in LYING
        for slot in (FRONT if layer.front else BEHIND):
            item = self.items.get(slot)
            if item is None or (lying and slot in ('head', 'back')):
                continue
            art = item_art(item, int(now * 2.2) if slot == 'buddy' else 0)
            if art is None:
                continue
            ax, ay = item['anchor']
            fit = FIT.get(item['name'], {})
            size = scale * fit.get('scale', 1.0)
            nudge = QPointF(fit.get('dx', 0) * rect.width(), fit.get('dy', 0) * rect.height())
            turn = fit.get('angle', 0)
            if slot == 'weapon':                            # In her hand (Codex measured it per frame), eased.
                self._step_weapon()
                fx, fy, turn_to, grow, front = self._wpose
                if front != layer.front:
                    continue                                # Held in front, or floating behind her.
                point = QPointF(rect.x() + fx * rect.width(), rect.y() + fy * rect.height())
                self._draw(p, art, point, (ax, ay), rect.width() / 1254 * grow * WEAPON_SCALE.get(item['name'], 1.0),
                           turn_to)
                continue
            if slot == 'head':
                fx, fy, fw = head_box(pixmap)
                size *= max(.85, min(1.2, fw / .5))         # As wide as her head is in this pose.
                if fit.get('side'):                         # Pinned at the side of her head, away from her feather.
                    point = QPointF(rect.x() + (fx - fw * .38) * rect.width(), rect.y() + (fy + .13) * rect.height())
                else:
                    point = QPointF(rect.x() + fx * rect.width(), rect.y() + (fy + .07) * rect.height())
            elif slot == 'back':
                point = QPointF(rect.center().x(), rect.y() + rect.height() * .5)
            elif slot == 'ground':
                point = QPointF(rect.center().x(), rect.bottom() + rect.height() * .01)
                size *= .78
            else:                                           # A buddy bobs at her left, clear of her raised hand.
                point = QPointF(rect.left() - side * .06, rect.y() + rect.height() * .4 + math.sin(now * 2.3) * side * .03)
                size *= .8
            self._draw(p, art, point + nudge, (ax, ay), size, turn)

    _SCALED = {}

    def _draw(self, p, art, point, anchor, scale, angle=0.0):
        """``art`` with its anchor at ``point`` (turned ``angle`` about it); scaled once per size."""
        ratio = self.pet.devicePixelRatioF()
        key = (art.cacheKey(), round(scale * ratio, 4))
        if key not in self._SCALED:
            if len(self._SCALED) > 64:
                self._SCALED.clear()
            scaled = art.scaled(max(1, round(art.width() * scale * ratio)), max(1, round(art.height() * scale * ratio)),
                                Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            self._SCALED[key] = scaled
        scaled = self._SCALED[key]
        p.save()
        p.translate(point)
        if angle:
            p.rotate(angle)
        p.drawPixmap(QRectF(-anchor[0] * scale, -anchor[1] * scale, art.width() * scale, art.height() * scale),
                     scaled, QRectF(scaled.rect()))
        p.restore()

    def close(self):
        for layer in (self.back, self.front):
            if layer is not None:
                layer.close()
        self.back = self.front = None


def paint_star(painter, centre, size):
    """A task star in the worn style; False when she wears none."""
    if STAR is None:
        return False
    from shop_view import item_art
    art = item_art(STAR)
    if art is None:
        return False
    scale = size / max(art.width(), art.height())
    w, h = art.width() * scale, art.height() * scale
    painter.drawPixmap(QRectF(centre.x() - w / 2, centre.y() - h / 2, w, h), art, QRectF(art.rect()))
    return True

