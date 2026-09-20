import hashlib
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtWidgets import QApplication, QLabel, QPushButton
from PySide6.QtGui import QImage
from PySide6.QtCore import QPoint
from widget import Panel, Settings
from pet import DesktopPet
from analytics import aggregate,normalize_usage
from localization import STRINGS, text


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
        self.assertEqual(values['Official OpenAI · Total Tokens'],'120 Tokens')
        self.assertTrue(values['Cache · Cache Hit Ratio'].endswith('%'))
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

    def test_all_scopes_use_the_same_full_token_format(self):
        self.panel.prefs['token_number_format']='full'
        tokens=normalize_usage(dict(input_tokens=31_000_000,cached_input_tokens=0,
                                    output_tokens=399_745,reasoning_output_tokens=0,
                                    total_tokens=31_399_745))
        analytics=aggregate([dict(session='fixture',model='gpt-6-astra',timestamp='2026-09-16T12:00:00Z',
            event_id='format',tokens=tokens)])
        for scope in ('global','project','conversation'):
            self.panel.render(dict(title='Scope',project='Project',model='gpt-6-astra',effort='high',
                mode='follow',scope=scope,tokens=tokens,available=True,analytics=analytics,
                usd=0,raw_total={},raw_last={}))
            self.assertEqual(self.panel.total.text(),'31,399,745')

    def test_working_context_pet_uses_selected_full_format(self):
        self.panel.prefs['token_number_format']='full'
        pet=self.panel.pet
        pet.update_data(dict(working_context=dict(project='Project',title='Task',
            tokens={'total_tokens':31_399_745,'input_tokens':31_000_000,'output_tokens':399_745})))
        self.assertIn('31,399,745 Tokens',pet.toolTip())

    def localized_fixture(self):
        tokens=normalize_usage(dict(input_tokens=100,cached_input_tokens=80,
                                    output_tokens=20,reasoning_output_tokens=12,
                                    total_tokens=120))
        analytics=aggregate([dict(session='fixture',model='gpt-6-astra',
            timestamp='2026-09-16T12:00:00Z',event_id='localized',tokens=tokens)])
        return dict(title='Never Translate This Task',project='Never Translate This Project',
            model='gpt-6-astra',effort='high',mode='follow',scope='project',tokens=tokens,
            available=True,analytics=analytics,usd=0,raw_total={},raw_last={},count=1,
            codex_activity=dict(active=True,valid=True),
            working_context=dict(project='Never Translate This Project',title='Never Translate This Task',
                model='gpt-6-astra',effort='high',tokens=tokens))

    def test_live_language_switch_updates_panel_and_pet_without_changing_data(self):
        data=self.localized_fixture()
        self.panel.render(data)
        before=(self.panel.total.text(),self.panel.prefs['scope'])
        self.panel.prefs['language']='en'
        self.panel.apply_language()
        self.panel.pet.update_data(data)
        self.assertEqual(self.panel.scope_button.text(),'Project ▾')
        self.assertIn('Estimated Cost',self.panel.cost_label.text())
        self.assertIn('Never Translate This Project',self.panel.pet.toolTip())
        self.assertIn('Click to view usage',self.panel.pet.toolTip())
        self.assertEqual((self.panel.total.text(),self.panel.prefs['scope']),before)

    def test_settings_language_selector_and_labels_follow_selected_language(self):
        self.panel.prefs['language']='en'
        settings=Settings(self.panel)
        self.assertEqual(settings.windowTitle(),'petoken · Settings')
        self.assertEqual([settings.language.itemText(i) for i in range(settings.language.count())],
                         ['简体中文','English'])
        self.assertEqual(settings.scope.itemText(0),'Global (Locally Recorded)')
        settings.language.setCurrentIndex(settings.language.findData('zh_CN'))
        self.app.processEvents()
        self.assertEqual(settings.windowTitle(),'petoken · 设置')
        settings.reject()

    def test_settings_language_change_persists_and_refreshes_current_session(self):
        settings=Settings(self.panel)
        settings.language.setCurrentIndex(settings.language.findData('en'))
        with patch('widget.write_preferences') as write:
            settings.save()
        self.assertEqual(self.panel.prefs['language'],'en')
        self.assertEqual(write.call_args.args[0]['language'],'en')
        self.assertEqual(self.panel.cost_label.text(),'Estimated Cost · CAD')

    def test_analytics_tabs_headers_and_dynamic_values_follow_language(self):
        data=self.localized_fixture()
        self.panel.prefs['language']='en'
        self.panel.apply_language()
        self.panel.render(data)
        self.panel.open_analytics();self.app.processEvents()
        analytics=self.panel.analytics_window
        self.assertEqual([analytics.tabs.tabText(i) for i in range(analytics.tabs.count())],
                         ['Full Usage','By Model','By Conversation','Date && History','Raw Fields / Source'])
        self.assertEqual(analytics.metrics.horizontalHeaderItem(0).text(),'Group / Metric')
        self.assertIn('Never Translate This Project',analytics.subtitle.text())
        self.assertNotRegex(analytics.subtitle.text(),r'[\u4e00-\u9fff]')

    def test_representative_english_ui_contains_no_chinese_labels(self):
        self.panel.prefs['language']='en'
        self.panel.apply_language()
        self.panel.render(self.localized_fixture())
        visible='\n'.join(w.text() for cls in (QLabel,QPushButton) for w in self.panel.findChildren(cls))
        self.assertNotRegex(visible,r'[\u4e00-\u9fff]')
        self.assertIn('Waiting for limit refresh',visible)

    def test_representative_chinese_ui_has_no_english_sentence_labels(self):
        self.panel.prefs['language']='zh_CN'
        self.panel.apply_language()
        self.panel.render(self.localized_fixture())
        visible='\n'.join(w.text() for cls in (QLabel,QPushButton) for w in self.panel.findChildren(cls))
        self.assertIn('预估费用',visible)
        self.assertNotIn('Waiting for data',visible)
        self.assertNotIn('Estimated Cost',visible)

    def test_analytics_token_column_headers_use_centralized_catalog(self):
        self.panel.prefs['language']='en'
        self.panel.apply_language()
        self.panel.render(self.localized_fixture())
        self.panel.open_analytics();self.app.processEvents()
        analytics=self.panel.analytics_window
        expected=[text(f'header_{name}','en') for name in
            ('input_tokens','cached_tokens','uncached_tokens','write_tokens',
             'output_tokens','reasoning_tokens','nonreasoning_tokens','total_tokens')]
        self.assertEqual([analytics.models.horizontalHeaderItem(i).text() for i in range(1,9)],expected)
        self.assertEqual(analytics.ranges.horizontalHeaderItem(1).text(),text('header_total_tokens','en'))
        self.assertEqual(analytics.days.horizontalHeaderItem(4).text(),text('header_write_tokens','en'))
        self.panel.prefs['language']='zh_CN'
        self.panel.apply_language();self.app.processEvents()
        self.assertEqual([analytics.models.horizontalHeaderItem(i).text() for i in range(1,9)],
            [text(f'header_{name}','zh_CN') for name in
            ('input_tokens','cached_tokens','uncached_tokens','write_tokens',
             'output_tokens','reasoning_tokens','nonreasoning_tokens','total_tokens')])

    def test_settings_fx_label_is_centralized_and_stable_across_languages(self):
        self.panel.prefs['language']='en'
        settings=Settings(self.panel)
        self.assertEqual(settings.fx_label.text(),text('fx_rate_label','en'))
        settings.language.setCurrentIndex(settings.language.findData('zh_CN'))
        self.app.processEvents()
        self.assertEqual(settings.fx_label.text(),text('fx_rate_label','zh_CN'))
        settings.reject()

    def test_catalog_has_no_unescaped_qt_mnemonics(self):
        import re
        for language, catalog in STRINGS.items():
            for key, value in catalog.items():
                self.assertIsNone(re.search(r'(?<!&)&(?!&)', value),
                    f'{language}.{key} contains a single & that Qt would swallow as a mnemonic')

    def test_pet_title_and_analytics_menu_follow_language(self):
        self.panel.prefs['language']='en'
        self.panel.apply_language();self.app.processEvents()
        self.assertEqual(self.panel.pet.windowTitle(),text('pet_title','en'))
        self.assertEqual(self.panel.pet.tr_text('analytics_button'),
                         self.panel.tray_actions['analytics_button'].text())
        self.panel.prefs['language']='zh_CN'
        self.panel.apply_language();self.app.processEvents()
        self.assertEqual(self.panel.pet.windowTitle(),text('pet_title','zh_CN'))
        self.assertEqual(self.panel.pet.tr_text('analytics_button'),text('analytics_button','zh_CN'))


if __name__=='__main__':unittest.main()
