"""2.5 Stardust Shop (prices, wish price and odds set by the person).

Two balances (docs/V2_5_SHOP_PLAN.md):
- earned stardust (stardust.Stardust.total(), never goes down) decides the
  milestone rewards (Meteor, Aurora, Starsea);
- spendable stardust = earned - spent + refunds, what the shop takes.

Items come in three sets (outfits, weapons, decorations), each with its own
rarity spread Starsea:Galaxy:Sun:Moon:Stars = 1:3:9:18:27 (scaled), and the
Starsea rarity only comes from wishing. Every day four items are featured,
each with a discount the person draws once (60 % .. 95 %). A wish costs 300
(ten for 3000); a heavy day of work earns about 600; a duplicate gives back 100.

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

ASSETS = Path(__file__).resolve().parent / 'assets' / 'v2_5' / 'shop'
WEAPONS = Path(__file__).resolve().parent / 'assets' / 'v2_5' / 'weapons'
GRIP = (627, 900)             # Where every weapon picture is held (Codex drew them on her 1254 px canvas).

RARITIES = ('fanxing', 'mingyue', 'haori', 'yinhe', 'xinghai')      # Low .. high.
SETS = ('outfit', 'weapon', 'decor')
SLOTS = ('outfit', 'weapon', 'head', 'back', 'ground', 'buddy', 'star')
# The person's numbers (2026-10-12).
PRICES = dict(fanxing=200, mingyue=800, haori=1800, yinhe=4500)
WISH_COST = 300
TEN_COST = 3000
# Starsea 0.6%, Galaxy 1.5%, Sun 4%, Moon 15%, the rest (78.9%) Stars.
ODDS = (('xinghai', .006), ('yinhe', .015), ('haori', .04), ('mingyue', .15), ('fanxing', .789))
PITY = 60                     # A Starsea item at the latest on this wish.
REFUND = 100                  # A duplicate from a wish gives back this much stardust, whatever its rarity.
DISCOUNTS = (.6, .65, .7, .75, .8, .85, .9, .95)
FEATURED = 4
SIGNIN = (500, 650, 500, 650, 500, 650, 500)    # Days 1..7 in a row, then round again (the person's numbers).
DAILY_TASKS, DAILY_BONUS = 3, 20
COLLECTION_BONUS = 100
WEEK_GOAL_BONUS = 30
# Per set, out of 20: Starsea 1, Galaxy 1, Sun 3, Moon 6, Stars 9.
SPREAD = dict(xinghai=1, yinhe=1, haori=3, mingyue=6, fanxing=9)

# Matching themes make a set (one outfit, one weapon, one decoration).
_THEMES = dict(sakura=('sakura_kimono', 'sakura_fan', 'head_pearl_flower'),
               frost=('frost_coat', 'frost_sword', 'star_snowflake'),
               moon=('moon_dress', 'crescent_bow', 'ground_moon_ripple'),
               starsea=('starsea_gown', 'starsea_scepter', 'back_starsea_seraph'))
# Only on sale at certain times of year: (month, day) from .. to.
_LIMITED = dict(sakura_kimono=((3, 15), (4, 30)), moon_lantern=((1, 20), (2, 20)), frost_coat=((12, 1), (2, 28)))


def _decorations():
    """Codex's 60 drawn decorations (assets/v2_5/shop/manifest.json): five kinds
    (head, back, ground, buddy, task star), with their own rarity spread."""
    try:
        manifest = json.loads((ASSETS / 'manifest.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return []
    items = []
    for entry in manifest:
        name, rarity = entry['id'], entry['rarity']
        theme = next((t for t, members in _THEMES.items() if name in members), None)
        items.append(dict(id=f'decor.{name}', set='decor', name=name, rarity=rarity, slot=entry['category'],
                          price=PRICES.get(rarity), theme=theme, window=_LIMITED.get(name),
                          names=dict(zh_CN=entry['name_zh'], en=entry['name_en']), art=list(entry['frames']),
                          anchor=(entry['anchor']['x'], entry['anchor']['y'])))
    order = {r: k for k, r in enumerate(reversed(RARITIES))}       # Rarest first, like the other sets.
    return sorted(items, key=lambda i: order[i['rarity']])


def _weapons():
    """Codex's 20 drawn weapons (assets/v2_5/weapons/manifest.json), held at GRIP."""
    try:
        manifest = json.loads((WEAPONS / 'manifest.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return []
    items = []
    for entry in manifest:
        name, rarity = entry['id'], entry['rarity']
        theme = next((t for t, members in _THEMES.items() if name in members), None)
        items.append(dict(id=f'weapon.{name}', set='weapon', name=name, rarity=rarity, slot='weapon',
                          price=PRICES.get(rarity), theme=theme, window=_LIMITED.get(name),
                          names=dict(zh_CN=entry['name_zh'], en=entry['name_en']), art=[entry['file']],
                          art_dir='weapons', anchor=GRIP))
    order = {r: k for k, r in enumerate(reversed(RARITIES))}
    return sorted(items, key=lambda i: order[i['rarity']])


def _catalog():
    """Outfits (outfits.py), weapons and decorations: all drawn by Codex."""
    import outfits
    return outfits.catalog(PRICES) + _weapons() + _decorations()


CATALOG = _catalog()
BY_ID = {item['id']: item for item in CATALOG}


def in_window(item, day):
    window = item.get('window')
    if not window:
        return True
    (m1, d1), (m2, d2) = window
    key = (day.month, day.day)
    return (m1, d1) <= key <= (m2, d2) if (m1, d1) <= (m2, d2) else key >= (m1, d1) or key <= (m2, d2)


# The person's own fit of each piece: {item id: dict(dx, dy, scale, angle)} (decor.own_fit).
OWN_FIT = {}
FIT_LIMITS = dict(dx=(-.35, .35), dy=(-.35, .35), scale=(.4, 2.5), angle=(-180, 180))


class Shop:
    def __init__(self, panel, path, clock=time.time, rng=None):
        self.panel = panel
        self.path = Path(path)
        self.clock = clock
        self.rng = rng or random.Random()
        self.state = self._load()
        OWN_FIT.clear()
        OWN_FIT.update(self.state.get('fit') or {})

    # Storage -------------------------------------------------------------------
    def _load(self):
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
            if isinstance(data, dict):
                return data
        except (OSError, ValueError):
            pass
        return {}

    def adjust_fit(self, item_id, dx=0.0, dy=0.0, scale=1.0, angle=0.0):
        """Move, grow or turn a piece on her (the person's own fit, kept per piece)."""
        own = dict(OWN_FIT.get(item_id) or {})
        for key, by in (('dx', dx), ('dy', dy), ('angle', angle)):
            low, high = FIT_LIMITS[key]
            own[key] = round(max(low, min(high, own.get(key, 0) + by)), 4)
        low, high = FIT_LIMITS['scale']
        own['scale'] = round(max(low, min(high, own.get('scale', 1.0) * scale)), 4)
        OWN_FIT[item_id] = own
        self.state['fit'] = dict(OWN_FIT)
        self._save()
        self._worn_changed()
        return own

    def reset_fit(self, item_id):
        OWN_FIT.pop(item_id, None)
        self.state['fit'] = dict(OWN_FIT)
        self._save()
        self._worn_changed()

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
        # Never below zero: stardust earned can shrink (its record reset) after it was spent.
        return max(0, self.earned() - self.state.get('spent', 0) + self.state.get('refunds', 0))

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
            refund = REFUND
            self.state['refunds'] = self.state.get('refunds', 0) + refund
            return refund
        owned.append(item_id)
        self.state.setdefault('log', []).append(dict(item=item_id, at=self.clock(), source=source))
        self._check_collection(BY_ID[item_id]['set'])
        hook = getattr(self.panel, 'shop_owned', None)               # An outfit's pictures come now.
        if hook is not None:
            hook(item_id)
        return 0

    def equipped(self):
        return dict(self.state.get('equipped', {}))

    def equip(self, item_id):
        item = BY_ID[item_id]
        if item_id not in self.owned():
            return False
        self.state.setdefault('equipped', {})[item['slot']] = item_id
        self._save()
        self._worn_changed()
        return True

    def _worn_changed(self):
        hook = getattr(self.panel, 'shop_worn_changed', None)       # She puts it on at once.
        if hook is not None:
            hook()

    def unequip(self, slot):
        self.state.setdefault('equipped', {}).pop(slot, None)
        self._save()
        self._worn_changed()

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
        self._worn_changed()
        return True

    def set_bonuses(self):
        """Themes whose outfit, weapon and decoration are all worn right now."""
        worn = [BY_ID[i] for i in self.equipped().values() if i in BY_ID]
        return [theme for theme in _THEMES
                if all(any(w['set'] == kind and w.get('theme') == theme for w in worn) for kind in SETS)]

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
    def _next_streak(self):
        """How many days in a row today's sign-in makes (a missed day starts the week's round again)."""
        day = self.today()
        last = self.state.get('signin_day')
        return self.state.get('streak', 0) + 1 if last == (day - timedelta(days=1)).isoformat() else 1

    def signin_reward(self):
        """What signing in today gives."""
        return SIGNIN[(self._next_streak() - 1) % len(SIGNIN)]

    def sign_in(self):
        """Today's sign-in: the stardust of this day of the week-long round."""
        day = self.today()
        if self.state.get('signin_day') == day.isoformat():
            return None
        streak, gained = self._next_streak(), self.signin_reward()
        self.state.update(signin_day=day.isoformat(), streak=streak)
        self._save()
        if self.dust is not None:
            self.dust.gain('star_signin', day.isoformat(), gained)
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
