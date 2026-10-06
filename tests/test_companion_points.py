"""2.0 companionship points, stickers, usage goals and the Collection page."""
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import QApplication

import companion
from companion import Companion, goal_ratio, project_usage, week_start
from workbench_store import WorkbenchStore

APP = QApplication.instance() or QApplication([])
# Wednesday 2026-10-07 15:00 local time.
NOW = datetime(2026, 10, 7, 15, 0).timestamp()


class FakePet:
    def __init__(self):
        self.poses = []

    def interact(self, pose, seconds):
        self.poses.append(pose)


class FakePanel:
    def __init__(self):
        self.prefs = dict(language='en')
        self.notices = []
        self.pet = FakePet()

    def tray_notice(self, title, body=''):
        self.notices.append(title)


class CompanionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = WorkbenchStore(Path(self.temp.name) / 'workbench.sqlite3')
        self.addCleanup(self.store.close)
        self.panel = FakePanel()
        self.now = [NOW]
        self.companion = Companion(self.panel, self.store, clock=lambda: self.now[0])

    def test_points_once_per_reason_and_ref(self):
        self.companion.award('todo_done', 't1')
        self.companion.award('todo_done', 't1')
        self.companion.award('focus_done', 'f1')
        self.companion.award('tokens_used', 'x')            # Not a reason: nothing.
        self.assertEqual(self.store.points(), companion.POINTS['todo_done'] + companion.POINTS['focus_done'])

    def test_first_project_sticker_and_celebration(self):
        project = self.store.create_project('site')
        self.assertEqual(self.companion.todo_done(dict(id='t0', project_id=None)), [])
        self.assertEqual(self.companion.todo_done(dict(id='t1', project_id=project['id'])), ['first_project'])
        self.assertEqual(self.companion.todo_done(dict(id='t2', project_id=project['id'])), [])
        self.assertEqual(self.panel.notices, ['New sticker: First Project'])
        self.assertEqual(self.panel.pet.poses, ['clap'])

    def test_focus_streak_and_count_stickers(self):
        for day in range(10):
            start = NOW - day * 86400
            session = self.store.start_focus(start, 1500)
            self.store.end_focus(session['id'], start + 1500, True)
        fresh = self.companion.award('focus_done', 'last')
        self.assertEqual(set(fresh), {'focus_10', 'streak_7'})
        self.assertIn('streak_7', self.store.achievements())

    def test_goal_worried_over_then_proud_next_week(self):
        project = self.store.create_project('Site', 'D:/work/site')
        self.store.set_goal(project['id'], weekly_tokens=1000)
        start = week_start(NOW)
        events = [dict(at=start + 3600, project='site', tokens=850, usd=None)]
        self.assertEqual([a[0] for a in self.companion.check_goals(events, NOW)], ['worried'])
        self.assertEqual(self.companion.check_goals(events, NOW + 60), [])          # Only once.
        events.append(dict(at=start + 7200, project='site', tokens=300, usd=.5))
        self.assertEqual([a[0] for a in self.companion.check_goals(events, NOW + 120)], ['over'])
        self.assertEqual(self.panel.pet.poses, ['worried', 'grievance'])
        # The next week begins: last week went over, so no pride.
        self.assertEqual(self.companion.check_goals(events, NOW + 7 * 86400), [])
        # A quiet week after that: proud, points and the goal sticker.
        alerts = self.companion.check_goals(events, NOW + 14 * 86400)
        self.assertEqual([a[0] for a in alerts], ['proud'])
        self.assertEqual(self.store.count_points('goal_week'), 1)
        self.assertIn('goal_week', self.store.achievements())

    def test_usage_and_ratio(self):
        project = dict(name='Site', directory='D:/work/site-folder')
        events = [dict(at=10, project='site-folder', tokens=100, usd=1.0),
                  dict(at=11, project='SITE', tokens=50, usd=None),
                  dict(at=12, project='other', tokens=999, usd=9.0),
                  dict(at=99, project='site', tokens=1, usd=0)]
        self.assertEqual(project_usage(events, project, 0, 50), (150, 1.0, False))
        self.assertEqual(goal_ratio(dict(weekly_tokens=300, weekly_usd=1.0), 150, 1.0), 1.0)
        self.assertIsNone(goal_ratio(dict(), 1, 1))
        self.assertEqual(datetime.fromtimestamp(week_start(NOW)), datetime(2026, 10, 5))


class CollectionPageTests(unittest.TestCase):
    def test_wall_and_log(self):
        from collection_view import CollectionPage, GoalDialog

        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        store = WorkbenchStore(Path(temp.name) / 'workbench.sqlite3')
        self.addCleanup(store.close)
        store.add_points('todo_done', 't1', 2, NOW)
        store.earn('first_weekly', NOW)

        class Owner:
            pass
        owner = Owner()
        owner.store, owner.panel = store, FakePanel()
        page = CollectionPage(owner)
        page.apply_language()
        self.assertEqual(page.points.text(), 'Companionship points: 2')
        self.assertEqual(page.wall.count(), len(companion.STICKERS))
        self.assertIn('Todo done', page.log.item(0).text())
        page.deleteLater()
        dialog = GoalDialog(None, 'en', dict(name='Site'), dict(weekly_tokens=2_500_000, weekly_usd=None))
        self.assertEqual(dialog.values(), dict(weekly_tokens=2_500_000, weekly_usd=None))
        dialog.tokens.setValue(0)
        dialog.usd.setValue(4.5)
        self.assertEqual(dialog.values(), dict(weekly_tokens=None, weekly_usd=4.5))
        dialog.deleteLater()


if __name__ == '__main__':
    unittest.main()
