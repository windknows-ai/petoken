"""2.5 Stardust Shop: balances, buying, discounts, wishes, sign-in, wardrobe, collections."""
import random
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import QApplication

import shop
from shop import Shop
from stardust import Stardust
from workbench_store import WorkbenchStore

APP = QApplication.instance() or QApplication([])
NOW = datetime(2026, 10, 11, 12, 0).timestamp()


class FakePanel:
    def __init__(self, store):
        self.store = store
        self.prefs = dict(language='zh_CN')

    def workbench_store(self):
        return self.store

    def stardust_unlocked(self, name):
        pass


class ShopTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.dir = Path(temp.name)
        self.store = WorkbenchStore(self.dir / 'workbench.sqlite3')
        self.addCleanup(self.store.close)
        self.panel = FakePanel(self.store)
        self.now = [NOW]
        self.panel.stardust = Stardust(self.panel, clock=lambda: self.now[0])
        self.shop = Shop(self.panel, self.dir / 'shop.json', clock=lambda: self.now[0], rng=random.Random(3))
        self.panel.shop = self.shop

    def give(self, amount):
        self.panel.stardust.gain('star_gift', f'gift-{amount}-{self.now[0]}', amount)

    def test_spending_never_lowers_earned_stardust(self):
        self.give(500)
        item = next(i for i in shop.CATALOG if i['rarity'] == 'fanxing' and not i.get('window'))
        self.assertTrue(self.shop.buy(item['id']))
        self.assertEqual(self.shop.earned(), 500)
        self.assertEqual(self.shop.spendable(), 500 - item['price'])
        self.assertFalse(self.shop.buy(item['id']))                 # Already owned.
        reloaded = Shop(self.panel, self.dir / 'shop.json', clock=lambda: self.now[0])
        self.assertIn(item['id'], reloaded.owned())

    def test_featured_four_are_fixed_for_the_day_with_drawn_discounts(self):
        self.give(5000)
        first = [i['id'] for i, _ in self.shop.featured()]
        self.assertEqual(len(first), shop.FEATURED)
        self.assertEqual(first, [i['id'] for i, _ in self.shop.featured()])
        pick = first[0]
        discount = self.shop.draw_discount(pick)
        self.assertIn(discount, shop.DISCOUNTS)
        self.assertEqual(self.shop.draw_discount(pick), discount)      # Only once.
        self.assertEqual(self.shop.price(pick), round(shop.BY_ID[pick]['price'] * discount))
        self.now[0] += 86400
        self.assertEqual(self.shop.price(pick), shop.BY_ID[pick]['price'])   # Tomorrow it is gone.

    def test_wishes_pity_ten_floor_and_duplicate_refunds(self):
        self.give(100000)
        rarities = [self.shop.wish(1)[0]['item']['rarity'] for _ in range(shop.PITY)]
        self.assertIn('xinghai', rarities)                              # Pity at the latest.
        ten = self.shop.wish(10)
        self.assertEqual(len(ten), 10)
        self.assertTrue(any(shop.RARITIES.index(r['item']['rarity']) >= 1 for r in ten))

        class Low:                                                      # Always a Stars-rarity roll.
            def random(self):
                return .99

            def choice(self, pool):
                return pool[0]
        self.shop.rng = Low()
        first = self.shop._roll()
        before = self.shop.spendable()
        again = self.shop._roll()
        self.assertEqual(again['item']['id'], first['item']['id'])
        self.assertEqual(again['refund'], shop.REFUND)
        self.assertEqual(self.shop.spendable(), before + again['refund'])

    def test_not_enough_stardust(self):
        self.assertIsNone(self.shop.wish(1))
        self.assertFalse(self.shop.buy(shop.CATALOG[-1]['id']))

    def test_sign_in_streak_and_daily_goal(self):
        for day in range(len(shop.SIGNIN)):
            result = self.shop.sign_in()
            self.assertIsNone(self.shop.sign_in())                     # Once a day.
            self.now[0] += 86400
        self.assertEqual(result['streak'], len(shop.SIGNIN))
        self.assertEqual(self.store.stardust(reason='star_signin'), 500 * 4 + 650 * 3)
        self.now[0] += 86400
        self.assertEqual(self.shop.signin_reward(), 500)                # Day 8: the week starts over.
        self.now[0] += 86400 * 2
        self.assertEqual(self.shop.signin_reward(), 500)                # A missed day: day 1 again.
        for n in range(3):
            self.panel.stardust.on_finished(dict(provider='claude', task_key=f't{n}', at=self.now[0] + n, detail=''))
        self.assertEqual(self.store.stardust(reason='star_daily'), shop.DAILY_BONUS)

    def test_wardrobe_set_bonus_and_collection(self):
        self.give(100000)
        ids = [next(i['id'] for i in shop.CATALOG if i['set'] == kind and i.get('theme') == 'frost')
               for kind in shop.SETS]
        self.shop.state['owned'] = list(ids)
        for item_id in ids:
            self.assertTrue(self.shop.equip(item_id))
        self.assertIn('frost', self.shop.set_bonuses())
        self.shop.save_outfit('冬天')
        self.shop.unequip('weapon')
        self.assertNotIn('frost', self.shop.set_bonuses())
        self.assertTrue(self.shop.wear_outfit('冬天'))
        self.assertIn('frost', self.shop.set_bonuses())
        rest = [i['id'] for i in shop.CATALOG if i['set'] == 'weapon' and i['id'] not in self.shop.owned()]
        for item_id in rest[:-1]:
            self.shop._own(item_id, 'test')
        self.assertEqual(self.store.stardust(reason='star_collection'), 0)
        self.shop._own(rest[-1], 'test')
        self.assertEqual(self.store.stardust(reason='star_collection'), shop.COLLECTION_BONUS)

    def test_discount_card_draw_uses_the_shops_draw(self):
        from discount_draw import DiscountDraw, discount_text
        self.give(5000)
        pick = [i for i, _ in self.shop.featured()][0]
        done = []
        draw = DiscountDraw(None, pick, lambda: self.shop.draw_discount(pick['id']), 'zh_CN', on_done=done.append)
        draw.timer.stop()
        self.assertIsNone(draw.card_at(draw.slot_point(0)))   # Not ready while shuffling.
        while not draw.ready():
            draw.advance(1 / 30)
        k = draw.card_at(draw.card_place(3)[0])
        self.assertIsNotNone(k)
        draw.mousePressEvent(type('E', (), {'position': lambda self: draw.card_place(k)[0]})())
        self.assertEqual(draw.value, self.shop.state['featured']['items'][pick['id']])   # Drawn by the shop.
        for _ in range(60):
            self.assertFalse(draw.grab().isNull())
            draw.advance(1 / 30)
        draw.close()
        self.assertEqual(done, [draw.value])
        self.assertEqual(discount_text(.75), '7.5')
        self.assertEqual(discount_text(.7), '7')

    def test_wardrobe_tries_on_buys_and_wears(self):
        from wardrobe import Wardrobe
        self.give(3000)
        self.panel.apply_ring_skin = lambda: None
        self.panel.persist = lambda: None
        w = Wardrobe(self.panel)
        w.resize(1220, 800)
        w.set_kind('head')
        crown = shop.BY_ID['decor.head_prism_crown']
        w.choose(crown)
        self.assertIs(w.preview_items()['head'], crown)          # Tried on before it is owned.
        self.assertNotIn(crown['id'], self.shop.owned())
        w._act()                                                  # Buy and wear.
        self.assertIn(crown['id'], self.shop.owned())
        self.assertEqual(self.shop.equipped()['head'], crown['id'])
        w._act()                                                  # Take it off again.
        self.assertNotIn('head', self.shop.equipped())
        coat = next(i for i in shop.CATALOG if i['slot'] == 'outfit' and i['id'] not in self.shop.owned())
        w.bridge.tryOn(coat['id'])                                  # An outfit tried on stays on while
        w.choose(shop.BY_ID['decor.head_cloud_beret'])              # a hat is tried with it.
        tried = w.preview_items()
        self.assertIs(tried['outfit'], coat)
        self.assertEqual(tried['head']['id'], 'decor.head_cloud_beret')
        self.assertTrue(w.bridge.trying)
        w.bridge.clearFitting()
        self.assertNotIn('outfit', w.preview_items())
        self.assertFalse(w.bridge.trying)
        w.choose(crown)                                             # Fitting a piece by hand.
        self.assertTrue(w.bridge.canAdjust)
        self.addCleanup(shop.OWN_FIT.clear)
        w.bridge.nudge(0, .02)
        w.bridge.growPiece(1.1)
        self.assertAlmostEqual(shop.OWN_FIT[crown['id']]['dy'], .02)
        self.assertIn('110%', w.bridge.fitText)
        w.bridge.resetFit()
        self.assertNotIn(crown['id'], shop.OWN_FIT)
        w.bridge.setZoom(1.3)
        self.assertAlmostEqual(w.bridge.zoom, 1.3)
        self.assertIn('0.6%', w.bridge.oddsText)                    # The odds, shown openly.
        self.assertIn(str(shop.REFUND), w.bridge.oddsText)
        self.assertEqual(w.errors, [])                              # The Qt Quick page loads cleanly.
        bridge = w.bridge
        for kind in ('weapon', 'back', 'star', 'outfit'):
            w.set_kind(kind)
            shown = [shop.BY_ID[i['id']]['slot'] for i in bridge.pageItems]
            self.assertTrue(shown and all(slot == kind for slot in shown))
        w.set_kind('head')                                          # 18 pieces: two pages of shelves.
        self.assertEqual(bridge.pageCount, 2)
        bridge.turn(1)
        self.assertEqual(len(bridge.pageItems), 2)
        from wardrobe import portrait
        for pose in ('cheer', 'idle'):
            w.set_pose(pose)
            image = portrait(self.panel, w.preview_items(), pose, 300, 420)
            self.assertGreater(image.pixelColor(150, 300).alpha(), 0)  # She is in the mirror.
        for page in range(3):
            bridge.setPage(page)
            self.assertFalse(w.grab().isNull())
        self.assertEqual(len(bridge.featured), shop.FEATURED)
        self.assertEqual(len(bridge.skins), 4)
        before = bridge.signText
        w._sign_in()
        self.assertNotEqual(bridge.signText, before)                # Signed in: shown at once.
        self.assertTrue(bridge.signedIn)
        w.close()

    def test_limited_items_only_in_their_window(self):
        lantern = shop.BY_ID['weapon.moon_lantern']
        self.assertTrue(shop.in_window(lantern, datetime(2026, 2, 1).date()))
        self.assertFalse(shop.in_window(lantern, datetime(2026, 10, 11).date()))
        self.assertTrue(shop.in_window(dict(window=((12, 1), (2, 28))), datetime(2027, 1, 5).date()))  # New year.

    def test_page_and_wish_show_build(self):
        from shop_view import ShopPage, WishShow

        class Owner:
            pass
        owner = Owner()
        owner.panel = self.panel
        self.give(8000)
        page = ShopPage(owner)
        page.resize(900, 900)
        page.apply_language()
        self.assertEqual(len([c for c in page.cards if c.parent() is not None]) >= shop.FEATURED, True)
        self.assertIn('8000', page.balance.text())
        for results in (self.shop.wish(10), self.shop.wish(1)):
            show = WishShow(None, results, 'zh_CN')
            show.timer.stop()
            steps = 0
            while show.queue and steps < 2000:                    # A player chasing the nearest star.
                if show.stars:
                    star = min(show.stars, key=lambda s: (s['pos'].x() - show.her.x()) ** 2
                               + (s['pos'].y() - show.her.y()) ** 2)
                    show.pointer = star['pos']
                show.advance(1 / 30)
                steps += 1
                if steps % 20 == 0:
                    self.assertFalse(show.grab().isNull())
            self.assertFalse(show.queue)                            # Every star found (helped if slow).
            self.assertEqual(sorted(show.catch), list(range(len(results))))
            while show.t < show.length:                           # Bursts, cards.
                show.advance(.2)
                self.assertFalse(show.grab().isNull())
            show.close()
        import wish_sound
        heard = []

        class Ears(wish_sound.Sounds):                              # Records what would be played.
            def __init__(self, enabled=True, volume=0):
                super().__init__(False)
                self.enabled = True
                self._thread = None

            def play(self, name):
                heard.append(name)
                return True
        original = wish_sound.Sounds
        wish_sound.Sounds = Ears
        try:
            listened = WishShow(None, [dict(item=shop.BY_ID['decor.back_starsea_seraph'], refund=0)], 'zh_CN')
            listened.timer.stop()
            listened.skip()
            while listened.t < listened.length:
                listened.advance(1 / 30)
            listened.close()
        finally:
            wish_sound.Sounds = original
        for name in ('open', 'rise_xinghai', 'burst_xinghai', 'flip', 'flip_fine'):
            self.assertIn(name, heard)
        self.assertEqual(len(heard), len(set(heard)))                 # Nothing piles up twice.
        idle = WishShow(None, self.shop.wish(1), 'zh_CN')            # Nobody steers: it still ends.
        idle.timer.stop()
        for _ in range(900):
            idle.advance(1 / 30)
        self.assertFalse(idle.queue)
        skipped = WishShow(None, self.shop.wish(10), 'zh_CN')        # Skip: everything at once.
        skipped.timer.stop()
        skipped.skip()
        self.assertFalse(skipped.queue)
        self.assertLess(skipped.flip0, 10)
        idle.close()
        skipped.close()
        page.deleteLater()


if __name__ == '__main__':
    unittest.main()
