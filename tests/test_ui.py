import hashlib
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage
from PySide6.QtCore import QPoint
from widget import Panel, Settings
from pet import DesktopPet
from analytics import aggregate,normalize_usage


class UiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.pref_patch=patch('widget.PREF_DIR',Path(self.temp.name));self.pref_patch.start()
        self.panel=Panel(live=False)
        self.panel.pet=DesktopPet(self.panel)
        self.panel.pet.activity_timer.stop()

    def tearDown(self):
        self.panel.pet.close();self.panel.tray.hide()
        if self.panel.analytics_window:self.panel.analytics_window.close()
        self.panel.closing=True;self.panel.close()
        self.panel.deleteLater();self.app.processEvents()
        self.pref_patch.stop();self.temp.cleanup()

    def test_idle_asset_unchanged_and_sprites_have_transparency(self):
        base=Path(__file__).parents[1]/'assets'
        self.assertEqual(hashlib.sha256((base/'skirk-pet.png').read_bytes()).hexdigest(),
            '7ce0d2fbd0eb89d2f6786c9bb1d5bada1aff7d89ea2f5dd079cce8a26483e1a0')
        for name in ('pet','typing','microphone','music'):
            image=QImage(str(base/f'skirk-{name}.png'))
            self.assertFalse(image.isNull())
            self.assertTrue(image.hasAlphaChannel(),name)
            self.assertEqual(image.pixelColor(0,0).alpha(),0,name)

    def test_unknown_cache_write_expanded_and_countdown_preserved(self):
        tokens=normalize_usage(dict(input_tokens=100,cached_input_tokens=80,output_tokens=20,reasoning_output_tokens=12))
        a=aggregate([dict(session='fixture',model='gpt-6-astra',timestamp='2026-09-16T12:00:00Z',event_id='a',tokens=tokens)])
        self.panel.render(dict(title='测试任务',project='测试项目',model='gpt-6-astra',effort='high',
            mode='follow',scope='task',tokens=tokens,available=True,analytics=a,usd=0,raw_total={},raw_last={}))
        self.panel.receive_limits(dict(sampled=time.time(),limits={'primary':{'usedPercent':30,'windowDurationMins':300,'resetsAt':time.time()+1800}}))
        self.panel.show();self.panel.open_analytics();self.app.processEvents()
        self.assertIn('70%',self.panel.five.value.text())
        self.assertIn('后重置',self.panel.five.reset.text())
        metrics=self.panel.analytics_window.metrics
        values={metrics.item(i,0).text():metrics.item(i,1).text() for i in range(metrics.rowCount())}
        self.assertEqual(values['Cache · Cache Write'],'N/A')
        self.assertEqual(values['Official OpenAI · Total Tokens'],'120')
        self.panel.toggle_compact();self.app.processEvents()
        self.assertFalse(self.panel.body_scroll.isVisible())
        self.assertLessEqual(self.panel.height(),280)
        self.panel.toggle_compact();self.app.processEvents()
        self.assertTrue(self.panel.body_scroll.isVisible())
        settings=Settings(self.panel);settings.show();self.app.processEvents();settings.reject()

    def test_hover_shows_and_leave_hides_then_activity_returns(self):
        pet=self.panel.pet;pet.show();self.app.processEvents()
        with patch('pet.QCursor') as cursor:
            cursor.pos.return_value=pet.pos()+QPoint(120,160)
            pet.hover_since=time.monotonic()-1
            pet.update_activity()
            self.assertTrue(self.panel.isVisible())
            self.assertEqual(pet.current_state,'usage')
            cursor.pos.return_value=QPoint(-9999,-9999)
            pet.left_since=time.monotonic()-1
            self.panel.activity.state.key()
            pet.update_activity()
            self.assertFalse(self.panel.isVisible())
            self.assertEqual(pet.current_state,'typing')

    def test_token_bubble_follows_central_app_mode(self):
        pet=self.panel.pet
        self.assertFalse(pet.token_bubble_visible())
        self.panel.app_mode.update(True,True,now=1)
        self.panel.app_mode.update(True,True,now=1.5)
        self.assertTrue(pet.token_bubble_visible())
        self.panel.app_mode.update(False,True,now=2)
        self.assertTrue(pet.token_bubble_visible())
        self.panel.app_mode.update(False,True,now=4.1)
        self.assertFalse(pet.token_bubble_visible())

    def test_token_bubble_uses_one_coherent_working_context(self):
        pet=self.panel.pet
        self.panel.app_mode.update(True,True,now=1)
        self.panel.app_mode.update(True,True,now=1.5)
        pet.update_data(dict(project='Panel Project',title='Panel Task',tokens={'total_tokens':999},
            working_context=dict(project='Working Project',title='Working Task',model='gpt-6-astra',
                effort='high',tokens={'total_tokens':220,'input_tokens':200,'output_tokens':20})))
        self.assertEqual(pet.working_context['project'],'Working Project')
        self.assertEqual(pet.working_context['tokens']['total_tokens'],220)
        self.assertIn('Working Project',pet.toolTip())
        self.assertNotIn('Panel Project',pet.toolTip())

    def test_scope_selector_exposes_global_project_and_conversation(self):
        settings=Settings(self.panel)
        self.assertEqual([settings.scope.itemData(i) for i in range(settings.scope.count())],
                         ['global','project','conversation'])
        settings.reject()

    def test_unknown_scope_preference_falls_back_to_conversation(self):
        self.panel.prefs['scope']='unknown-future-value'
        settings=Settings(self.panel)
        self.assertEqual(settings.scope.currentData(),'conversation')
        settings.reject()


if __name__=='__main__':unittest.main()
