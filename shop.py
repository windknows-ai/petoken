"""2.5 Stardust Shop (test build: prices and odds are placeholders).

Two balances (docs/V2_5_SHOP_PLAN.md):
- earned stardust (stardust.Stardust.total(), never goes down) decides the
  milestone rewards (Meteor, Aurora, Starsea);
- spendable stardust = earned - spent + refunds, what the shop takes.

Items come in three sets (outfits, weapons, decorations), each with its own
rarity spread Starsea:Galaxy:Sun:Moon:Stars = 1:3:9:18:27 (scaled), and the
Starsea rarity only comes from wishing. Every day four items are featured,
each with a discount the person draws once (60 % .. 95 %).

The shop's own state (what was bought, spent, the wish counter, what is worn,
saved outfits, today's featured items) lives in a small JSON file beside the
settings, written atomically; earnings (sign-in, daily goal, collections)
are stardust entries like any other.
"""
from __future__ import annotations

import json
import os
import random
import time
from datetime import date, datetime, timedelta
from pathlib import Path

RARITIES = ('fanxing', 'mingyue', 'haori', 'yinhe', 'xinghai')      # Low .. high.
SETS = ('outfit', 'weapon', 'decor')
SLOTS = ('outfit', 'weapon', 'head', 'back', 'ground', 'buddy', 'star')
# Placeholders until the person sets the real numbers.
PRICES = dict(fanxing=80, mingyue=200, haori=500, yinhe=1200)
WISH_COST = 100
TEN_COST = 1000
ODDS = (('xinghai', .02), ('yinhe', .06), ('haori', .14), ('mingyue', .30), ('fanxing', .48))
PITY = 60                     # A Starsea item at the latest on this wish.
REFUND = .5                   # A duplicate gives back this share of its value.
VALUE = dict(PRICES, xinghai=3000)
DISCOUNTS = (.6, .65, .7, .75, .8, .85, .9, .95)
FEATURED = 4
SIGNIN, STREAK_DAYS, STREAK_BONUS = 10, 7, 50
DAILY_TASKS, DAILY_BONUS = 3, 20
COLLECTION_BONUS = 100
WEEK_GOAL_BONUS = 30
# Per set, out of 20: Starsea 1, Galaxy 1, Sun 3, Moon 6, Stars 9.
SPREAD = dict(xinghai=1, yinhe=1, haori=3, mingyue=6, fanxing=9)

_NAMES = {
    'outfit': ('starsea_gown', 'galaxy_robe', 'sun_dress', 'moon_dress', 'aurora_coat', 'sakura_kimono',
               'frost_coat', 'cloud_cape', 'mint_hoodie', 'night_sailor', 'lavender_dress', 'cocoa_sweater',
               'ocean_dress', 'peach_dress', 'ink_hanfu', 'candy_dress', 'forest_cloak', 'ruby_dress',
               'pearl_dress', 'twilight_dress'),
    'weapon': ('starsea_staff', 'galaxy_blade', 'sun_spear', 'moon_bow', 'comet_wand', 'frost_sword',
               'sakura_fan', 'star_lance', 'crystal_orb', 'lantern', 'umbrella', 'quill', 'mallet',
               'ribbon_wand', 'katana', 'harp', 'shield', 'kite', 'whip', 'feather_dart'),
    'decor': ('starsea_wings', 'galaxy_halo', 'sun_crown', 'moon_circle', 'cat_ears', 'bunny_ears',
              'flower_crown', 'witch_hat', 'cloud_seat', 'star_buddy', 'jelly_lamp', 'kitten',
              'heart_star', 'moon_star', 'snow_star', 'paw_star', 'magic_circle', 'flower_bed', 'bow',
              'beret'),
}
_DECOR_SLOT = dict(starsea_wings='back', galaxy_halo='head', sun_crown='head', moon_circle='ground',
                   cat_ears='head', bunny_ears='head', flower_crown='head', witch_hat='head',
                   cloud_seat='ground', star_buddy='buddy', jelly_lamp='buddy', kitten='buddy',
                   heart_star='star', moon_star='star', snow_star='star', paw_star='star',
                   magic_circle='ground', flower_bed='ground', bow='head', beret='head')
# Matching themes make a set (one outfit, one weapon, one decoration).
_THEMES = dict(sakura=('sakura_kimono', 'sakura_fan', 'flower_crown'),
               frost=('frost_coat', 'frost_sword', 'snow_star'),
               moon=('moon_dress', 'moon_bow', 'moon_circle'),
               starsea=('starsea_gown', 'starsea_staff', 'starsea_wings'))
# Only on sale at certain times of year: (month, day) from .. to.
_LIMITED = dict(sakura_kimono=((3, 15), (4, 30)), lantern=((1, 20), (2, 20)), frost_coat=((12, 1), (2, 28)))


def _catalog():
    items = []
    for kind in SETS:
        names = list(_NAMES[kind])
        for rarity in reversed(RARITIES):                     # The first names are the rarest.
            for _ in range(SPREAD[rarity]):
                name = names.pop(0)
                theme = next((t for t, members in _THEMES.items() if name in members), None)
                items.append(dict(id=f'{kind}.{name}', set=kind, name=name, rarity=rarity,
                                  slot=kind if kind != 'decor' else _DECOR_SLOT[name],
                                  price=PRICES.get(rarity), theme=theme, window=_LIMITED.get(name)))
    return items


CATALOG = _catalog()
BY_ID = {item['id']: item for item in CATALOG}


def in_window(item, day):
    window = item.get('window')
    if not window:
        return True
    (m1, d1), (m2, d2) = window
    key = (day.month, day.day)
    return (m1, d1) <= key <= (m2, d2) if (m1, d1) <= (m2, d2) else key >= (m1, d1) or key <= (m2, d2)


class Shop:
    def __init__(self, panel, path, clock=time.time, rng=None):
        self.panel = panel
        self.path = Path(path)
        self.clock = clock
        self.rng = rng or random.Random()
        self.state = self._load()

    # Storage -------------------------------------------------------------------
    def _load(self):
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
            if isinstance(data, dict):
                return data
        except (OSError, ValueError):
            pass
        return {}

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix('.tmp')
        temp.write_text(json.dumps(self.state, ensure_ascii=False, indent=1), encoding='utf-8')
        os.replace(temp, self.path)

    def today(self):
        return datetime.fromtimestamp(self.clock()).date()

    # Balances -----------------------------------------------------------------------
    @property
    def dust(self):
        return getattr(self.panel, 'stardust', None)

    def earned(self):
        return self.dust.total() if self.dust is not None else 0

    def spendable(self):
        return self.earned() - self.state.get('spent', 0) + self.state.get('refunds', 0)

    def _spend(self, amount):
        if amount > self.spendable():
            return False
        self.state['spent'] = self.state.get('spent', 0) + int(amount)
        return True

    # Owning and wearing ----------------------------------------------------------------
    def owned(self):
        return set(self.state.get('owned', []))

    def _own(self, item_id, source):
        owned = self.state.setdefault('owned', [])
        if item_id in owned:
            refund = int(VALUE[BY_ID[item_id]['rarity']] * REFUND)
            self.state['refunds'] = self.state.get('refunds', 0) + refund
            return refund
        owned.append(item_id)
        self.state.setdefault('log', []).append(dict(item=item_id, at=self.clock(), source=source))
        self._check_collection(BY_ID[item_id]['set'])
        return 0

    def equipped(self):
        return dict(self.state.get('equipped', {}))

    def equip(self, item_id):
        item = BY_ID[item_id]
        if item_id not in self.owned():
            return False
        self.state.setdefault('equipped', {})[item['slot']] = item_id
        self._save()
        return True

    def unequip(self, slot):
        self.state.setdefault('equipped', {}).pop(slot, None)
        self._save()

    def save_outfit(self, name):
        presets = [p for p in self.state.get('wardrobe', []) if p['name'] != name]
        presets.append(dict(name=name, items=self.equipped()))
        self.state['wardrobe'] = presets[-5:]
        self._save()

    def wear_outfit(self, name):
        preset = next((p for p in self.state.get('wardrobe', []) if p['name'] == name), None)
        if preset is None:
            return False
        self.state['equipped'] = {slot: i for slot, i in preset['items'].items() if i in self.owned()}
        self._save()
        return True

    def set_bonuses(self):
        """Themes whose outfit, weapon and decoration are all worn right now."""
        worn = set(self.equipped().values())
        return [theme for theme, members in _THEMES.items() if all(f'{BY_ID_KIND[m]}.{m}' in worn for m in members)]

    # Buying ------------------------------------------------------------------------------
    def on_sale(self):
        day = self.today()
        return [i for i in CATALOG if i['price'] is not None and in_window(i, day)]

    def featured(self):
        """Today's four, the same all day: [(item, discount or None)]."""
        key = self.today().isoformat()
        today = self.state.get('featured', {})
        if today.get('day') != key:
            pool = [i['id'] for i in self.on_sale() if i['id'] not in self.owned()] or [i['id'] for i in self.on_sale()]
            pick = random.Random(f'{key}:{self.state.setdefault("seed", random.randrange(1 << 30))}').sample(
                pool, min(FEATURED, len(pool)))
            today = dict(day=key, items={i: None for i in pick})
            self.state['featured'] = today
            self._save()
        return [(BY_ID[i], d) for i, d in today['items'].items()]

    def draw_discount(self, item_id):
        """The person draws this item's discount for today (once)."""
        items = self.state.get('featured', {}).get('items', {})
        if item_id not in items or items[item_id] is not None:
            return items.get(item_id)
        items[item_id] = self.rng.choice(DISCOUNTS)
        self._save()
        return items[item_id]

    def price(self, item_id):
        item = BY_ID[item_id]
        if item['price'] is None:
            return None
        discount = self.state.get('featured', {}).get('items', {}).get(item_id) \
            if self.state.get('featured', {}).get('day') == self.today().isoformat() else None
        return int(round(item['price'] * (discount or 1)))

    def buy(self, item_id):
        item = BY_ID[item_id]
        price = self.price(item_id)
        if price is None or item_id in self.owned() or not in_window(item, self.today()):
            return False
        if not self._spend(price):
            return False
        self._own(item_id, 'buy')
        self._save()
        return True

    # Wishing ------------------------------------------------------------------------------
    def pity_left(self):
        return PITY - self.state.get('pity', 0)

    def _roll(self, floor=None):
        self.state['pity'] = self.state.get('pity', 0) + 1
        if self.state['pity'] >= PITY:
            rarity = 'xinghai'
        else:
            x, rarity = self.rng.random(), 'fanxing'
            for name, chance in ODDS:
                if x < chance:
                    rarity = name
                    break
                x -= chance
        if floor and RARITIES.index(rarity) < RARITIES.index(floor):
            rarity = floor
        if rarity == 'xinghai':
            self.state['pity'] = 0
        pool = [i for i in CATALOG if i['rarity'] == rarity]
        item = self.rng.choice(pool)
        refund = self._own(item['id'], 'wish')
        return dict(item=item, refund=refund)

    def wish(self, count=1):
        """One or ten wishes; a ten-wish brings at least one Moon item. None if too poor."""
        cost = TEN_COST if count == 10 else WISH_COST * count
        if not self._spend(cost):
            return None
        results = [self._roll() for _ in range(count)]
        if count == 10 and all(RARITIES.index(r['item']['rarity']) < 1 for r in results):
            results[-1] = self._roll(floor='mingyue')
        self._save()
        return results

    # Earning ------------------------------------------------------------------------------
    def sign_in(self):
        """Today's sign-in: SIGNIN stardust, plus a bonus every STREAK_DAYS days in a row."""
        day = self.today()
        last = self.state.get('signin_day')
        if last == day.isoformat():
            return None
        streak = self.state.get('streak', 0) + 1 if last == (day - timedelta(days=1)).isoformat() else 1
        self.state.update(signin_day=day.isoformat(), streak=streak)
        self._save()
        gained = SIGNIN
        if self.dust is not None:
            self.dust.gain('star_signin', day.isoformat(), SIGNIN)
            if streak % STREAK_DAYS == 0:
                self.dust.gain('star_streak', day.isoformat(), STREAK_BONUS)
                gained += STREAK_BONUS
        return dict(streak=streak, gained=gained)

    def _check_collection(self, kind):
        members = {i['id'] for i in CATALOG if i['set'] == kind}
        done = self.state.setdefault('collections', [])
        if kind not in done and members <= self.owned():
            done.append(kind)
            if self.dust is not None:
                self.dust.gain('star_collection', kind, COLLECTION_BONUS)

    def collection(self):
        """{set: (owned, total)} for the collection book."""
        owned = self.owned()
        return {kind: (sum(1 for i in CATALOG if i['set'] == kind and i['id'] in owned),
                       sum(1 for i in CATALOG if i['set'] == kind)) for kind in SETS}


BY_ID_KIND = {item['name']: item['set'] for item in CATALOG}
