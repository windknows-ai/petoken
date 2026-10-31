"""The Stardust Wardrobe (2.5): everything stardust, in its own window.

The window is drawn by Qt Quick (ui/Petoken/Wardrobe.qml): rounded night glass with a soft
shadow, Codex's star cabinet with the pieces standing on its shelves in glass domes, the standing
mirror where she tries things on, doors that swing open in perspective, spring-loaded buttons and
GPU particles. This module is its data and its actions (`WardrobeBridge`), the pictures it asks
for (`Pictures`: her in the mirror, the ring-skin previews) and the window around it. The wish
show and the discount card draw still play over it as widgets.

Sounds only where they mean something: buying (and the shows themselves).
"""
from __future__ import annotations

import functools

import math
from pathlib import Path

from PySide6.QtCore import Property, QPoint, QRectF, Qt, Signal, Slot
from PySide6.QtGui import QImage, QPainter, QTransform
from PySide6.QtQuick import QQuickImageProvider

import decor
import pet_assets
import pet_geometry as geometry
import shop
from localization import text

WARDROBE_DIR = pet_assets.ASSETS_DIR / 'v2_5' / 'wardrobe'
KINDS = ('outfit', 'weapon', 'head', 'back', 'ground', 'buddy', 'star')
PER_PAGE = 16                       # Four shelves of four.
POSES = (('idle', 'wardrobe_pose_idle'), ('greet_morning', 'wardrobe_pose_greet'), ('cheer', 'wardrobe_pose_cheer'),
         ('thumbs_up', 'wardrobe_pose_thumbs'), ('ready_go', 'wardrobe_pose_ready'))
from quick_ui import MARGIN, HostBridge, QuickWindow, file_url, load_fonts   # noqa: E402,F401  (shared)


def art_path(item):
    frames = item.get('art')
    if not frames:
        return None
    folder = shop.ASSETS.parent / item['art_dir'] if item.get('art_dir') else shop.ASSETS
    return folder / frames[0]


# Pictures the window asks for ---------------------------------------------------------------
class _MirrorPet:
    pet_scale = 100
    ratio = 1.0

    def pos(self):
        return QPoint(0, 0)

    def devicePixelRatioF(self):
        return self.ratio


class _Layer:
    def __init__(self, front):
        self.front = front

    def pos(self):
        return QPoint(0, 0)


@functools.lru_cache(maxsize=16)
def _picture(path):
    """Her full-size picture, read once (the mirror and the skin cards ask for it again and again
    while the window lays out)."""
    return QImage(str(pet_assets._file(path)))


def portrait(panel, items, pose, width, height):
    """Her in ``pose`` wearing ``items``, on transparency, ``width`` x ``height`` pixels: her feet
    at the bottom centre, room above and beside her for wings, crowns and a buddy."""
    import outfits
    width, height = max(64, int(width)), max(64, int(height))
    outfit = items.get('outfit')
    starsea = getattr(panel, 'starsea', None)
    state = pose
    if starsea is not None and getattr(starsea, 'active', False):
        state = starsea.pose(pose)                          # Her Starsea look in the mirror too.
    path = (outfits.frame_path(outfit, state, preview=True) if outfit is not None else None) or decor.frame_file(state, 0) \
        or decor.frame_file('idle', 0)
    sx, sy, sw, sh = geometry.scaled_sprite_rect(100)
    k = min(height / (sh * 1.16), width / (sw * 1.45))       # Her box, with room for what she wears.
    source = _picture(path)
    sprite = source.scaled(int(sh * k), int(sh * k), Qt.KeepAspectRatio, Qt.SmoothTransformation)
    image = QImage(width, height, QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    p = QPainter(image)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    place = QTransform().translate(width / 2 - (sx + sw / 2) * k, height * .97 - (sy + sh) * k).scale(k, k)
    p.setTransform(place)
    size_w, size_h = sprite.width() / k, sprite.height() / k
    rect = QRectF(sx + (sw - size_w) / 2, sy + sh - size_h, size_w, size_h)
    pet = _MirrorPet()
    pet.ratio = k
    dressing = decor.Decor(pet)
    dressing.items = {slot: item for slot, item in items.items() if slot != 'outfit'}
    dressing.pose = (state, sprite, QTransform(), rect)
    dressing.source = path
    dressing.paint(p, _Layer(False))
    p.setTransform(place)
    p.drawImage(rect, sprite, QRectF(sprite.rect()))
    dressing.paint(p, _Layer(True))
    p.end()
    return image


class _Ring:
    """What collection_view.SkinCard's ring painters read: its width and which skin."""
    W = 148

    def __init__(self, choice):
        self.choice = choice


_SKINS = {}


def skin_scene(choice, width, height):
    """A ring skin's preview (her with that star ring around her) drawn at ``width`` x ``height``
    pixels on transparency: the ring painted at that size, her from her full-size picture."""
    from collection_view import SkinCard
    key = (choice, int(width), int(height))
    if key in _SKINS:
        return _SKINS[key]
    width, height = max(32, int(width)), max(24, int(height))
    image = QImage(width, height, QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    p = QPainter(image)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    k = min(width / 148, height / 108)                      # The card's scene is 148 x 108.
    p.translate((width - 148 * k) / 2, (height - 108 * k) / 2)
    p.scale(k, k)
    ring = _Ring(choice)
    if choice == 'meteor':
        SkinCard._shooting_stars(ring, p)
    elif choice == 'aurora':
        SkinCard._curtains(ring, p)
    SkinCard._ring(ring, p, False)
    pose = 'star_idle' if choice == 'starsea' and pet_assets.has_own_art('star_idle') else 'idle'
    path = decor.frame_file(pose, 0) or decor.frame_file('idle', 0)
    her = _picture(path) if path else QImage()
    if not her.isNull():
        side = 92 * k                                       # Scaled once, straight from the big picture.
        her = her.scaled(int(side * her.width() / max(1, her.height())), int(side), Qt.KeepAspectRatio,
                         Qt.SmoothTransformation)
        size_w, size_h = her.width() / k, her.height() / k
        p.drawImage(QRectF((148 - size_w) / 2, 100 - size_h, size_w, size_h), her, QRectF(her.rect()))
    SkinCard._ring(ring, p, True)
    p.end()
    if len(_SKINS) > 16:
        _SKINS.clear()
    _SKINS[key] = image
    return image


class Pictures(QQuickImageProvider):
    """image://petoken/mirror/<n> (her in the mirror) and image://petoken/skin/<key>/<n>."""

    def __init__(self, bridge):
        super().__init__(QQuickImageProvider.Image)
        self.bridge = bridge

    def requestImage(self, ident, size, requested):
        kind, _, rest = ident.partition('/')
        w = requested.width() if requested.width() > 0 else 600
        h = requested.height() if requested.height() > 0 else 800
        if kind == 'mirror':
            return portrait(self.bridge.panel, self.bridge.preview_items(), self.bridge._pose, w, h)
        if kind == 'skin':
            return skin_scene(rest.split('/')[0], w, h)
        return QImage(1, 1, QImage.Format_ARGB32_Premultiplied)


# The data and actions -----------------------------------------------------------------------
class WardrobeBridge(HostBridge):
    changed = Signal()
    opened = Signal()
    sparkle = Signal(bool)
    coveredChanged = Signal()

    def __init__(self, window, panel):
        super().__init__(window, panel)
        self._covered = False
        self._kind = 'head'
        self._page = 0
        self._shelf = 0
        self._pose = 'idle'
        self._chosen = None
        self._fitting = {}               # slot -> the piece tried on there (kept while others are tried).
        self._serial = 0
        from wish_sound import Sounds
        self.sounds = Sounds(bool(panel.prefs.get('wish_sound', True)))

    # Helpers
    @property
    def shop(self):
        return self.panel.shop

    def touch(self, portrait_too=False):
        if portrait_too:
            self._serial += 1
        self.changed.emit()

    def preview_items(self):
        """What the mirror shows: what she wears, with the chosen piece tried on."""
        items = decor.worn_items(self.panel)
        worn = self.shop.equipped().get('outfit')
        if worn in shop.BY_ID and shop.BY_ID[worn].get('art') and worn in self.shop.owned():
            items['outfit'] = shop.BY_ID[worn]
        for slot, item in self._fitting.items():
            if item.get('art'):
                items[slot] = item
        return items

    def _item(self, item):
        from shop_view import item_name
        store = self.shop
        owned = item['id'] in store.owned()
        worn = store.equipped().get(item['slot']) == item['id']
        price = store.price(item['id'])
        badge = (self._t('wardrobe_worn') if worn else '' if owned else
                 self._t('wardrobe_wish_only') if price is None else f'✦ {price}')
        path = art_path(item)
        return dict(id=item['id'], name=item_name(item, self.language), rarity=item['rarity'], owned=owned, worn=worn,
                    badge=badge, art=file_url(path) if path else '')

    # Read by the page
    @Slot(str, result=str)
    def tr(self, key):
        if key == 'wardrobe_title_plain':
            return self._t('wardrobe_title').replace('✦', '').strip()
        return super().tr(key)

    @Property(bool, notify=coveredChanged)
    def covered(self):
        """A wish show or a discount draw fills the window: the wardrobe beneath stops drawing (its
        sparkles and her bobbing would be redrawn and copied every frame for nothing)."""
        return self._covered

    def set_covered(self, covered):
        if covered != self._covered:
            self._covered = covered
            self.coveredChanged.emit()

    @Property(str, notify=changed)
    def balanceText(self):
        return f'{self.shop.spendable():,}'

    @Property(str, notify=changed)
    def earnedText(self):
        return self._t('wardrobe_earned', points=f'{self.shop.earned():,}')

    @Property(bool, notify=changed)
    def signedIn(self):
        return self.shop.state.get('signin_day') == self.shop.today().isoformat()

    @Property(str, notify=changed)
    def signText(self):
        if self.shop.state.get('signin_day') == self.shop.today().isoformat():
            return self._t('shop_signed', streak=self.shop.state.get('streak', 0))
        return self._t('shop_signin', points=self.shop.signin_reward())

    @Property(int, notify=changed)
    def page(self):
        return self._page

    @Property(str, notify=changed)
    def kind(self):
        return self._kind

    @Property('QVariant', notify=changed)
    def kinds(self):
        owned = self.shop.owned()
        out = []
        for kind in KINDS:
            items = [i for i in shop.CATALOG if i['slot'] == kind]
            out.append(dict(key=kind, label=self._t(f'shop_slot_{kind}'), have=sum(1 for i in items if i['id'] in owned),
                            total=len(items)))
        return out

    def kind_items(self):
        return [i for i in shop.CATALOG if i['slot'] == self._kind and shop.in_window(i, self.shop.today())]

    @Property(int, notify=changed)
    def pageCount(self):
        return max(1, math.ceil(len(self.kind_items()) / PER_PAGE))

    @Property(int, notify=changed)
    def shelfPage(self):
        return self._shelf

    @Property('QVariant', notify=changed)
    def pageItems(self):
        items = self.kind_items()[self._shelf * PER_PAGE:(self._shelf + 1) * PER_PAGE]
        return [self._item(i) for i in items]

    @Property(str, notify=changed)
    def chosenId(self):
        return self._chosen['id'] if self._chosen is not None else ''

    @Property('QVariant', notify=changed)
    def chosen(self):
        item = self._chosen
        if item is None:
            return {}
        from shop_view import item_name
        store = self.shop
        owned = item['id'] in store.owned()
        worn = store.equipped().get(item['slot']) == item['id']
        price = store.price(item['id'])
        detail = self._t(f'shop_slot_{item["slot"]}') + ('' if item.get('art') else self._t('wardrobe_no_art'))
        packs = getattr(self.panel, 'outfit_packs', None)
        status = packs.status(item) if packs is not None and owned else None
        if status == 'failed':
            detail += self._t('wardrobe_pack_failed')
        elif status is not None:
            detail += self._t('wardrobe_pack_loading', percent=int(status * 100))
        if worn:
            action = dict(actionText=self._t('wardrobe_take_off'), actionKind='ghost', actionIcon='arrow-u-up-left',
                          actionEnabled=True)
        elif owned:
            action = dict(actionText=self._t('wardrobe_wear'), actionKind='violet', actionIcon='sparkle',
                          actionEnabled=True)
        elif price is None:
            action = dict(actionText=self._t('wardrobe_wish_only'), actionKind='ghost', actionIcon='shooting-star',
                          actionEnabled=False)
        else:
            action = dict(actionText=self._t('wardrobe_buy', price=price), actionKind='gold', actionIcon='shopping-bag',
                          actionEnabled=store.spendable() >= price)
        return dict(name=item_name(item, self.language), rarity=item['rarity'],
                    rarityLabel=self._t(f'shop_rarity_{item["rarity"]}'), detail=detail, **action)

    @Property(bool, notify=changed)
    def trying(self):
        owned = self.shop.owned()
        return any(item['id'] not in owned for item in self._fitting.values())

    @Property(str, notify=changed)
    def portrait(self):
        return f'image://petoken/mirror/{self._serial}'

    @Property(str, notify=changed)
    def pose(self):
        return self._pose

    @Property('QVariant', notify=changed)
    def poses(self):
        return [dict(key=key, label=self._t(label)) for key, label in POSES]

    @Property('QVariant', notify=changed)
    def outfits(self):
        return [p['name'] for p in self.shop.state.get('wardrobe', [])]

    @Property(str, notify=changed)
    def bonusText(self):
        bonuses = [self._t(f'shop_theme_{t}') for t in self.shop.set_bonuses()]
        return self._t('shop_set_bonus', sets='、'.join(bonuses)) if bonuses else ''

    @Property('QVariant', notify=changed)
    def featured(self):
        from discount_draw import discount_text
        out = []
        for item, discount in self.shop.featured():
            entry = self._item(item)
            price = self.shop.price(item['id'])
            off_text = ''
            if entry['owned']:
                mode, label, ok, price_text = 'owned', self._t('wardrobe_owned'), False, ''
            elif discount is None:
                mode, label, ok = 'draw', self._t('shop_draw_discount'), True
                price_text = f'✦ {item["price"]}' if item.get('price') else ''
            else:                                           # The price says it all; the button just buys.
                mode, ok = 'buy', self.shop.spendable() >= price
                label = self._t('wardrobe_buy_now')
                off_text = self._t('wardrobe_off', off=discount_text(discount))
                price_text = f'<s style="color:#8C84BC">{item["price"]}</s>&nbsp;&nbsp;✦ {price}'
            entry.update(mode=mode, buttonText=label, enabled=ok, priceText=price_text, offText=off_text, badge='')
            out.append(entry)
        return out

    @Property(str, notify=changed)
    def wishOneText(self):
        return self._t('shop_wish_one', cost=shop.WISH_COST)

    @Property(str, notify=changed)
    def wishTenText(self):
        return self._t('shop_wish_ten', cost=shop.TEN_COST)

    @Property(bool, notify=changed)
    def canWishOne(self):
        return self.shop.spendable() >= shop.WISH_COST

    @Property(bool, notify=changed)
    def canWishTen(self):
        return self.shop.spendable() >= shop.TEN_COST

    @Property(str, notify=changed)
    def pityText(self):
        return self._t('shop_pity', left=self.shop.pity_left())

    @Property('QVariant', notify=changed)
    def milestone(self):
        from stardust import UNLOCKS, next_unlock
        dust = getattr(self.panel, 'stardust', None)
        total = dust.total() if dust is not None else 0
        coming = next_unlock(total)
        goal = coming and dict(UNLOCKS)[coming[0]] or UNLOCKS[-1][1]
        return dict(totalText=self._t('stardust_total', points=total), fraction=min(1.0, total / max(1, goal)),
                    nextText=(self._t('stardust_next', left=coming[1], name=self._t(f'stardust_name_{coming[0]}'))
                              if coming else self._t('stardust_all')),
                    earnText=self._t('stardust_earn'), **self._earn_parts())

    def _earn_parts(self):
        """'How to earn it: a · b · c' as a heading and its ways, each shown on its own."""
        import re
        whole = self._t('stardust_earn').rstrip('。.')
        found = re.match(r'^(.*?)[：:]\s*(.*)$', whole)
        head, rest = (found.group(1), found.group(2)) if found else ('', whole)
        return dict(earnTitle=head.strip(), earnWays=[w.strip() for w in rest.split('·') if w.strip()])

    def skin_states(self):
        from stardust import UNLOCKS, unlocked
        dust = getattr(self.panel, 'stardust', None)
        have = unlocked(dust.total() if dust is not None else 0)
        need = dict(UNLOCKS)
        skin = self.panel.prefs.get('ring_skin', 'default')
        starsea = getattr(self.panel, 'starsea', None)
        out = []
        for choice in ('default', 'meteor', 'aurora', 'starsea'):
            key = 'starsea' if choice == 'starsea' else f'skin_{choice}'
            ok = choice == 'default' or key in have
            if choice == 'starsea':
                ok = ok and starsea is not None and starsea.art_ready()
                current = bool(starsea is not None and starsea.active)
            else:
                current = skin == choice
            ok = ok or current                              # What she wears is never shown locked.
            caption = (self._t('stardust_card_on') if current else self._t('stardust_card_wear') if ok
                       else self._t('stardust_card_locked', need=need.get(key, 0)))
            out.append(dict(key=choice, name=self._t(f'stardust_card_{choice}'), caption=caption, unlocked=ok,
                            current=current, image=f'image://petoken/skin/{choice}'))
        return out

    @Property('QVariant', notify=changed)
    def skins(self):
        return self.skin_states()

    @Property('QVariant', notify=changed)
    def book(self):
        out = []
        for kind, (got, total) in self.shop.collection().items():
            out.append(dict(label=self._t('shop_book_line', set=self._t(f'shop_set_{kind}'), have=got, total=total,
                                          bonus=shop.COLLECTION_BONUS), fraction=got / max(1, total)))
        return out

    # Actions
    @Slot(int)
    def setPage(self, index):
        self._page = index
        self.touch()

    @Slot(str)
    def setKind(self, kind):
        self._kind, self._shelf = kind, 0
        self.touch()

    @Slot(int)
    def turn(self, step):
        self._shelf = max(0, min(self.pageCount - 1, self._shelf + step))
        self.touch()

    @Slot(str)
    def setPose(self, pose):
        self._pose = pose
        self.touch(True)

    @Slot(str)
    def choose(self, item_id):
        self._chosen = shop.BY_ID.get(item_id)
        if self._chosen is not None:                        # Tried on with whatever else is being tried.
            self._fitting[self._chosen['slot']] = self._chosen
        self.sparkle.emit(False)
        self.touch(True)

    @Slot(str)
    def tryOn(self, item_id):
        item = shop.BY_ID.get(item_id)
        if item is not None:
            self._kind = item['slot']
            items = self.kind_items()
            self._shelf = items.index(item) // PER_PAGE if item in items else 0
            self.choose(item_id)

    @Slot()
    def act(self):
        item, store = self._chosen, self.shop
        if item is None:
            return
        if store.equipped().get(item['slot']) == item['id']:
            store.unequip(item['slot'])
            self._fitting.pop(item['slot'], None)
        elif item['id'] in store.owned():
            store.equip(item['id'])
            self.sparkle.emit(True)
        elif store.buy(item['id']):
            store.equip(item['id'])
            self.sparkle.emit(True)
            self.sounds.play('discount')
        self.touch(True)

    # Fitting a piece by hand, and her size in the mirror ----------------------------------
    def _fit_item(self):
        item = self._chosen
        return item if item is not None and item.get('art') and item['slot'] not in ('outfit', 'star') else None

    @Property(bool, notify=changed)
    def canAdjust(self):
        return self._fit_item() is not None

    @Property(str, notify=changed)
    def fitText(self):
        item = self._fit_item()
        if item is None:
            return self._t('wardrobe_fit_none')
        own = shop.OWN_FIT.get(item['id']) or {}
        return self._t('wardrobe_fit_now', scale=round(own.get('scale', 1.0) * 100), angle=round(own.get('angle', 0)))

    @Slot(float, float)
    def nudge(self, dx, dy):
        item = self._fit_item()
        if item is not None:
            self.shop.adjust_fit(item['id'], dx=dx, dy=dy)
            self.touch(True)

    @Slot(float)
    def growPiece(self, factor):
        item = self._fit_item()
        if item is not None:
            self.shop.adjust_fit(item['id'], scale=factor)
            self.touch(True)

    @Slot(float)
    def turnPiece(self, degrees):
        item = self._fit_item()
        if item is not None:
            self.shop.adjust_fit(item['id'], angle=degrees)
            self.touch(True)

    @Slot()
    def resetFit(self):
        item = self._fit_item()
        if item is not None:
            self.shop.reset_fit(item['id'])
            self.touch(True)

    @Property(str, notify=changed)
    def oddsText(self):
        """The odds, read from the shop's own numbers (what is shown is what is drawn)."""
        rates = ' · '.join(f"{self._t(f'shop_rarity_{name}')} {chance * 100:g}%" for name, chance in shop.ODDS)
        rules = self._t('wardrobe_odds_text', refund=shop.REFUND).split('\n', 1)[1]
        return rates + '\n' + rules

    @Property(float, notify=changed)
    def zoom(self):
        """Her size in the mirror (only her: the mirror and the closet stay as they are)."""
        return float(self.shop.state.get('mirror_zoom', 1.0))

    @Slot(float)
    def setZoom(self, value):
        self.shop.state['mirror_zoom'] = round(max(.6, min(1.6, value)), 3)
        self.shop._save()
        self.touch()

    @Slot()
    def clearFitting(self):
        """Back to what she really wears."""
        self._fitting = {}
        self._chosen = None
        self.touch(True)

    @Slot()
    def signIn(self):
        self.shop.sign_in()
        self.touch()

    @Slot(str)
    def buyFeatured(self, item_id):
        if self.shop.buy(item_id):
            self.shop.equip(item_id)
            self.sounds.play('discount')
            self._chosen = shop.BY_ID.get(item_id)
            self.sparkle.emit(True)
        self.touch(True)

    @Slot(str)
    def drawDiscount(self, item_id):
        self.window.draw_discount(shop.BY_ID[item_id])

    @Slot(int)
    def wish(self, count):
        self.window.wish(count)

    @Slot(str)
    def chooseSkin(self, choice):
        panel = self.panel
        if choice == 'starsea':
            starsea = getattr(panel, 'starsea', None)
            if starsea is not None:
                starsea.toggle()
        else:
            panel.prefs['ring_skin'] = choice
            try:
                panel.persist()
            except Exception:
                pass
            panel.apply_ring_skin()
        self.touch(True)

    @Slot()
    def saveOutfit(self):
        name = self._t('shop_preset_default', n=len(self.shop.state.get('wardrobe', [])) + 1)
        self.shop.save_outfit(name)
        self.touch()

    @Slot()
    def wearOutfit(self):
        presets = self.shop.state.get('wardrobe', [])
        if presets:
            self.shop.wear_outfit(presets[-1]['name'])
            self._chosen = None
            self._fitting = {}
            self.touch(True)

    @Slot()
    def takeAll(self):
        for slot in list(self.shop.equipped()):
            self.shop.unequip(slot)
        self._chosen = None
        self._fitting = {}
        self.touch(True)



# The window ------------------------------------------------------------------------------------
class Wardrobe(QuickWindow):
    def __init__(self, panel):
        super().__init__()
        self.panel = panel
        self.setWindowTitle(text('wardrobe_open', panel.prefs.get('language', 'zh_CN')))
        self.resize(1260 + 2 * MARGIN, 840 + 2 * MARGIN)
        self.setMinimumSize(1060, 720)
        self.bridge = WardrobeBridge(self, panel)
        self.view.engine().addImageProvider('petoken', Pictures(self.bridge))
        self.load('Wardrobe.qml', bridge=self.bridge)
        self._overlay = None

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._overlay is not None:
            try:
                self._overlay.setGeometry(self.overlay_rect())
                self._overlay.setMask(self.overlay_mask(self._overlay.size()))
            except RuntimeError:
                self._overlay = None

    def showEvent(self, event):
        super().showEvent(event)
        self.bridge.touch(True)
        self.bridge.opened.emit()

    def closeEvent(self, event):
        overlay, self._overlay = self._overlay, None
        if overlay is not None:                              # A show still playing ends with the window:
            try:                                             # hidden, it kept its clock, its sound thread
                overlay.close()                              # and hundreds of MB of frames.
                overlay.deleteLater()
            except RuntimeError:
                pass
            self.bridge.set_covered(False)
        self.bridge.sounds.close()
        from wish_sound import Sounds
        self.bridge.sounds = Sounds(bool(self.panel.prefs.get('wish_sound', True)))
        super().closeEvent(event)

    def refresh(self):
        self.bridge.touch(True)

    def _sound_pref(self):
        panel = self.panel

        def remember(enabled):
            panel.prefs['wish_sound'] = enabled
            persist = getattr(panel, 'persist', None)
            if persist is not None:
                persist()
        return panel.prefs.get('wish_sound', True), remember

    def _show_overlay(self, overlay):
        overlay.setGeometry(self.overlay_rect())
        overlay.setMask(self.overlay_mask(overlay.size()))
        overlay.show()
        overlay.raise_()
        overlay.setFocus()
        overlay.installEventFilter(self)                     # Gone as soon as it closes.
        self._overlay = overlay
        self.bridge.set_covered(True)

    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        if obj is self._overlay and event.type() in (QEvent.Hide, QEvent.Close):
            self._overlay = None
            self.bridge.set_covered(False)
            self.bridge.touch(True)
        return False

    def draw_discount(self, item):
        from discount_draw import DiscountDraw
        sound, remember = self._sound_pref()
        draw = DiscountDraw(self, item, lambda: self.shop.draw_discount(item['id']), self.bridge.language,
                            sound=sound, on_sound=remember, on_done=lambda value: self.bridge.touch(True))
        self._show_overlay(draw)

    def wish(self, count):
        results = self.shop.wish(count)
        if not results:
            return
        from wish_show import WishShow
        sound, remember = self._sound_pref()
        starsea = getattr(self.panel, 'starsea', None)
        show = WishShow(self, results, self.bridge.language, bool(starsea is not None and starsea.active),
                        sound=sound, on_sound=remember)
        self._show_overlay(show)                             # The wardrobe catches up when it closes.

    @property
    def shop(self):
        return self.panel.shop

    # For tests and the preview
    def set_kind(self, kind):
        self.bridge.setKind(kind)

    def choose(self, item):
        self.bridge.choose(item['id'])

    def set_pose(self, pose):
        self.bridge.setPose(pose)

    def preview_items(self):
        return self.bridge.preview_items()

    def _act(self):
        self.bridge.act()

    def _sign_in(self):
        self.bridge.signIn()
