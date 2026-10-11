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
        self.panel.stardust.gain('star_review', f'gift-{amount}-{self.now[0]}', amount)

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
        self.assertEqual(again['refund'], int(shop.VALUE['fanxing'] * shop.REFUND))
        self.assertEqual(self.shop.spendable(), before + again['refund'])

    def test_not_enough_stardust(self):
        self.assertIsNone(self.shop.wish(1))
        self.assertFalse(self.shop.buy(shop.CATALOG[-1]['id']))

    def test_sign_in_streak_and_daily_goal(self):
        for day in range(shop.STREAK_DAYS):
            result = self.shop.sign_in()
            self.assertIsNone(self.shop.sign_in())                     # Once a day.
            self.now[0] += 86400
        self.assertEqual(result['streak'], shop.STREAK_DAYS)
        self.assertEqual(self.store.stardust(reason='star_signin'), shop.SIGNIN * shop.STREAK_DAYS)
        self.assertEqual(self.store.stardust(reason='star_streak'), shop.STREAK_BONUS)
        for n in range(3):
            self.panel.stardust.on_finished(dict(provider='claude', task_key=f't{n}', at=self.now[0] + n, detail=''))
        self.assertEqual(self.store.stardust(reason='star_daily'), shop.DAILY_BONUS)

    def test_wardrobe_set_bonus_and_collection(self):
        self.give(100000)
        theme = shop._THEMES['frost']
        ids = [f'{shop.BY_ID_KIND[m]}.{m}' for m in theme]
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

    def test_limited_items_only_in_their_window(self):
        kimono = shop.BY_ID['outfit.sakura_kimono']
        self.assertTrue(shop.in_window(kimono, datetime(2026, 4, 1).date()))
        self.assertFalse(shop.in_window(kimono, datetime(2026, 10, 11).date()))
        frost = shop.BY_ID['outfit.frost_coat']
        self.assertTrue(shop.in_window(frost, datetime(2027, 1, 5).date()))      # Wraps the new year.

    def test_page_and_wish_show_build(self):
        from shop_view import ShopPage, WishShow

        class Owner:
            pass
        owner = Owner()
        owner.panel = self.panel
        self.give(3000)
        page = ShopPage(owner)
        page.resize(900, 900)
        page.apply_language()
        self.assertEqual(len([c for c in page.cards if c.parent() is not None]) >= shop.FEATURED, True)
        self.assertIn('3000', page.balance.text())
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
