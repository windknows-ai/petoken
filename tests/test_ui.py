import hashlib
import tempfile
import threading
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from PySide6.QtWidgets import QApplication, QCheckBox, QDoubleSpinBox, QLabel, QPushButton, QWidget
from PySide6.QtGui import QImage, QMouseEvent
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from widget import (Panel, Settings, TaskPanelManager, TaskPanelWindow,
                    filter_tasks_for_preference, format_recorded_cost,
                    format_task_metrics, order_tasks, task_identity)
from pet import DesktopPet
from analytics import aggregate,normalize_usage
from localization import STRINGS, normalize_language, text
import pet_geometry as pet_geometry
from pet import DesktopPet
from analytics import aggregate,normalize_usage
from localization import STRINGS, normalize_language, text
import pet_geometry as pet_geometry
from provider_poller import ProviderPoller
from tests.test_providers import write_home
from usage import CodexStore

NOW_S = datetime(2026, 9, 19, 12, 1, 40, tzinfo=timezone.utc).timestamp()


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
        from widget import COMPACT_HEIGHT
        self.assertEqual(self.panel.height(),COMPACT_HEIGHT)
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
            self.assertEqual(pet.current_state,'idle')
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

    def test_settings_currency_selector_replaces_manual_pricing(self):
        self.panel.prefs['language']='en'
        settings=Settings(self.panel)
        self.assertEqual([settings.currency.itemText(i) for i in range(settings.currency.count())],
                         ['USD','CAD','EUR','CNY'])
        self.assertEqual(settings.currency_label.text(),'Currency')
        self.assertEqual(settings.findChildren(QDoubleSpinBox),[])
        boxes=settings.findChildren(QCheckBox)
        self.assertEqual(len(boxes),1)
        self.assertIs(boxes[0],settings.topmost)
        self.assertEqual(settings.topmost_label.text(),'Always on Top')
        settings.currency.setCurrentIndex(settings.currency.findData('EUR'))
        with patch('widget.write_preferences') as write:
            settings.save()
        self.assertEqual(self.panel.prefs['currency'],'EUR')
        self.assertEqual(write.call_args.args[0]['currency'],'EUR')
        self.assertIn('EUR',self.panel.cost_label.text())
        settings.deleteLater()

    def test_currency_change_does_not_alter_token_counts(self):
        data=self.localized_fixture()
        self.panel.fx_data=dict(date='2026-09-18',source='Bank of Canada',
                                rates={'CAD':1.4,'EUR':1.2,'CNY':0.2})
        shown={}
        for code in ('USD','CAD','EUR','CNY'):
            self.panel.prefs['currency']=code
            self.panel.render(data)
            shown[code]=(self.panel.total.text(),self.panel.io_line.text(),
                         self.panel.cost.text(),self.panel.cost_label.text())
        totals={v[:2] for v in shown.values()}
        self.assertEqual(len(totals),1)
        self.assertTrue(shown['USD'][2].startswith('≈ $'))
        self.assertTrue(shown['CAD'][2].startswith('≈ CA$'))
        self.assertTrue(shown['EUR'][2].startswith('≈ \u20ac'))
        self.assertTrue(shown['CNY'][2].startswith('≈ \u00a5'))
        self.assertTrue(all(v[3].endswith(code) for code,v in
                            zip(('USD','CAD','EUR','CNY'),shown.values())))

    def test_missing_rate_falls_back_to_usd_honestly(self):
        data=self.localized_fixture()
        self.panel.fx_data=dict(date='2026-09-15',source='Bank of Canada · bundled',
                                rates={'CAD':1.3917})
        self.panel.prefs['currency']='EUR'
        self.panel.render(data)
        self.assertTrue(self.panel.cost.text().startswith('≈ $'))
        self.assertIn('USD',self.panel.cost_label.text())
        self.assertIn(text('fx_unavailable_usd',self.panel.language),self.panel.cost.toolTip())

    def test_language_change_does_not_alter_cost_numerics(self):
        data=self.localized_fixture()
        self.panel.fx_data=dict(date='2026-09-18',source='Bank of Canada',
                                rates={'CAD':1.4,'EUR':1.2,'CNY':0.2})
        self.panel.prefs['currency']='EUR'
        self.panel.prefs['language']='zh_CN'
        self.panel.apply_language()
        self.panel.render(data)
        before=(self.panel.cost.text(),data['usd'])
        self.panel.prefs['language']='en'
        self.panel.apply_language()
        self.panel.render(data)
        self.assertEqual((self.panel.cost.text(),data['usd']),before)
        self.assertIn('EUR',self.panel.cost_label.text())

    def test_catalog_has_no_unescaped_qt_mnemonics(self):
        import re
        # Settings About titles render on plain buddy-less QLabels, which
        # display a single & literally (verified in screenshots); every other
        # catalog string must stay mnemonic-safe for menus/buttons/tabs.
        label_only = {'about_3_title', 'about_4_title'}
        for language, catalog in STRINGS.items():
            for key, value in catalog.items():
                if key in label_only:
                    continue
                self.assertIsNone(re.search(r'(?<!&)&(?!&)', value),
                    f'{language}.{key} contains a single & that Qt would swallow as a mnemonic')

    def test_pet_uses_companion_scale_window_and_full_res_sources(self):
        import pet_geometry as geometry
        self.assertEqual((self.panel.pet.width(),self.panel.pet.height()),geometry.window_size())
        self.assertEqual(geometry.window_size(),(272,330))
        for state in ('idle','typing','microphone','music'):
            source=self.panel.pet.sprites[state]
            self.assertFalse(source.isNull(),state)
            self.assertGreater(source.width(),500,state)

    def test_pet_paints_every_state_without_changing_geometry(self):
        import pet_geometry as geometry
        before=(self.panel.pet.width(),self.panel.pet.height())
        for state in ('idle','typing','microphone','music','working','usage'):
            self.panel.pet.preview_state=state
            self.panel.pet.update_activity()
            self.app.processEvents()
            image=self.panel.pet.grab().toImage()
            self.assertFalse(image.isNull(),state)
        self.assertEqual((self.panel.pet.width(),self.panel.pet.height()),before)
        self.assertEqual(geometry.sprite_rect(),(8,64,256,256))
        self.panel.pet.preview_state=None

    def test_pet_drag_clamp_and_saved_position_recovery(self):
        from PySide6.QtCore import QPoint
        screen=self.app.primaryScreen().availableGeometry()
        self.panel.pet.move_clamped(QPoint(-5000,-5000))
        pos=self.panel.pet.pos()
        self.assertGreaterEqual(pos.x(),screen.left())
        self.assertGreaterEqual(pos.y(),screen.top())
        self.panel.pet.move_clamped(QPoint(screen.right()+5000,screen.bottom()+5000))
        pos=self.panel.pet.pos()
        self.assertLessEqual(pos.x()+self.panel.pet.width(),screen.right()+1)
        self.assertLessEqual(pos.y()+self.panel.pet.height(),screen.bottom()+1)
        # An old V1.0-era saved top-left keeps the smaller window on screen.
        self.panel.pet.move_clamped(QPoint(screen.right()-280,screen.bottom()-400))
        pos=self.panel.pet.pos()
        self.assertLessEqual(pos.x()+self.panel.pet.width(),screen.right()+1)
        self.assertLessEqual(pos.y()+self.panel.pet.height(),screen.bottom()+1)

    def test_typing_tap_phases_render_without_geometry_change(self):
        import pet_geometry as geometry
        from types import SimpleNamespace
        from activity import ActivityState
        window_before=(self.panel.pet.width(),self.panel.pet.height())
        self.panel.activity=SimpleNamespace(state=ActivityState())
        self.panel.pet.preview_state='typing'
        base=1000.0
        for pulse,phase in ((None,0),(0.0,1),(0.2,0)):
            if pulse is not None:
                self.panel.activity.state.key(base+pulse)
            self.panel.pet.update_activity()
            self.app.processEvents()
            self.assertEqual(self.panel.pet.current_state,'typing')
            self.assertEqual(self.panel.pet.typing_phase(),phase)
            self.assertFalse(self.panel.pet.grab().toImage().isNull())
        self.assertEqual((self.panel.pet.width(),self.panel.pet.height()),window_before)
        self.assertEqual(geometry.anchor(),(136,320))
        self.panel.pet.preview_state=None

    def test_music_subtitle_pill_only_with_text_and_music_visible(self):
        self.panel.pet.preview_state='music'
        self.panel.pet.update_activity()
        self.assertIsNone(self.panel.pet.music_subtitle())
        self.assertEqual(self.panel.pet.grab().toImage().pixelColor(121,29).alpha(),0)
        self.panel.activity.status['music_text']={'text':'Test subtitle line','source':'qa',
            'identity':('qa','T','A')}
        self.assertEqual(self.panel.pet.music_subtitle(),'Test subtitle line')
        self.assertGreater(self.panel.pet.grab().toImage().pixelColor(121,29).alpha(),0)
        self.panel.pet.preview_state=None

    def test_token_mode_hides_music_subtitle(self):
        self.panel.activity.status['music_text']={'text':'Test subtitle line','source':'qa',
            'identity':('qa','T','A')}
        self.panel.pet.preview_state='music'
        self.panel.pet.update_activity()
        self.assertIsNotNone(self.panel.pet.music_subtitle())
        self.panel.app_mode.update(True,True)
        self.panel.app_mode.update(True,True,self.panel.app_mode.pending_since+1.0)
        self.assertTrue(self.panel.pet.token_bubble_visible())
        self.assertIsNone(self.panel.pet.music_subtitle())
        self.panel.pet.preview_state=None

    def test_music_subtitle_long_text_elides_and_stays_untranslated(self):
        line='长字幕行测试 '+'very long subtitle line '*20
        self.panel.activity.status['music_text']={'text':line,'source':'qa',
            'identity':('qa','T','A')}
        self.panel.pet.preview_state='music'
        self.panel.pet.update_activity()
        self.assertEqual(self.panel.pet.music_subtitle(),line.strip())
        before=(self.panel.pet.width(),self.panel.pet.height())
        self.assertFalse(self.panel.pet.grab().toImage().isNull())
        self.assertEqual((self.panel.pet.width(),self.panel.pet.height()),before)
        self.panel.pet.preview_state=None

    def test_reset_to_defaults_needs_confirm_and_restores_form(self):
        self.panel.prefs['language']='en'
        settings=Settings(self.panel)
        settings.scope.setCurrentIndex(settings.scope.findData('global'))
        settings.token_format.setCurrentIndex(settings.token_format.findData('full'))
        settings.currency.setCurrentIndex(settings.currency.findData('EUR'))
        settings.topmost.setChecked(False)
        self.assertEqual(settings.reset_button.text(),'Reset to Defaults')
        settings.reset_button.click()
        self.assertEqual(settings.reset_button.text(),'Click again to confirm reset')
        self.assertEqual(settings.scope.currentData(),'global')
        settings.reset_button.click()
        self.assertEqual(settings.scope.currentData(),'conversation')
        self.assertEqual(settings.language.currentData(),'zh_CN')
        self.assertEqual(settings.token_format.currentData(),'compact')
        self.assertEqual(settings.currency.currentData(),'CAD')
        self.assertTrue(settings.topmost.isChecked())
        self.assertEqual(settings.windowTitle(),'petoken · 设置')
        with patch('widget.write_preferences') as write:
            settings.save()
        saved=write.call_args.args[0]
        self.assertEqual((saved['scope'],saved['language'],saved['token_number_format'],
                          saved['currency'],saved['always_on_top']),('conversation','zh_CN','compact','CAD',True))
        settings.deleteLater()

    def test_final_art_states_share_geometry_and_taps_differ(self):
        import pet_assets as assets
        import pet_geometry as geometry
        from types import SimpleNamespace
        from activity import ActivityState
        self.panel.activity=SimpleNamespace(state=ActivityState(),close=lambda:None,
            status={'microphone':None,'music':None,'music_text':None})
        grabs=set()
        for state in ('idle','typing','codex_working','working','microphone','music','guitar','usage'):
            self.panel.pet.preview_state=state
            self.panel.pet.update_activity()
            self.app.processEvents()
            image=self.panel.pet.grab().toImage()
            self.assertFalse(image.isNull(),state)
            grabs.add(image.cacheKey() if hasattr(image,'cacheKey') else image.sizeInBytes())
            self.assertEqual((self.panel.pet.width(),self.panel.pet.height()),
                             geometry.window_size(),state)
        self.assertEqual(geometry.anchor(),(136,320))
        self.assertGreater(len(grabs),1)
        self.panel.pet.preview_state=None
        self.assertEqual(assets.resolve_path(assets.entry_for('idle')),'assets/v1_1/idle.png')

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


NOW_S = datetime(2026, 9, 19, 12, 1, 40, tzinfo=timezone.utc).timestamp()


class ProviderUiTests(unittest.TestCase):
    """Current Codex-only Hub/source/scope tests; no historical adapter startup."""
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])



    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.pref_patch = patch('widget.PREF_DIR', Path(self.temp.name))
        self.pref_patch.start()
        self.panel = Panel(live=False)
        self.panel.pet = DesktopPet(self.panel)
        self.panel.pet.activity_timer.stop()
        self.work = Path(self.temp.name) / 'stores'
        self.work.mkdir()



    def tearDown(self):
        self.panel.provider_poller.drain(timeout=10)
        self.panel.provider_poller.close()
        self.panel.pet.close(); self.panel.tray.hide()
        if self.panel.analytics_window: self.panel.analytics_window.close()
        self.panel.closing = True; self.panel.close()
        self.panel.deleteLater(); self.app.processEvents()
        self.pref_patch.stop(); self.temp.cleanup()



    def _home(self, name, threads):
        home = self.work / name
        home.mkdir(exist_ok=True)
        write_home(str(home), threads)
        return CodexStore(home)



    def _poll_render(self, prefs=None, now=None, **kw):
        # Three rounds guarantee one full fresh round-trip even when a
        # previous-epoch job is still draining (see poller tests).
        prefs = dict({'scope': 'global'}, **(prefs or {}))
        poller = self.panel.provider_poller
        poller.poll(prefs, now=now, **kw)
        self.assertTrue(poller.drain(), 'provider reads did not finish')
        poller.poll(prefs, now=now, **kw)
        self.assertTrue(poller.drain(), 'provider reads did not finish')
        out = poller.poll(prefs, now=now, **kw)
        self.panel.render(out['result'])
        self.app.processEvents()
        return out



    def _apply_render(self, prefs_update, mark=None, now=None):
        """Production settings path: persist, apply, synchronous emit."""
        self.panel.prefs.update(prefs_update)
        out = self.panel.provider_poller.apply_settings(
            dict(self.panel.prefs), mark_provider=mark, now=now)
        self.panel.render(out['result'])
        self.app.processEvents()
        return out



    def test_working_session_separate_from_pinned_scope(self):
        self._attach([{'id': 't1', 'working': True}, {'id': 't2'}])
        # Codex: analytics inspects t2, bubble follows working t1.
        self._poll_render({'scope': 'conversation', 'pinned': 't2'},
                          active_title='t1', detection_valid=True)
        self.assertIn('t1', self.panel.pet.toolTip())

    def test_missing_scope_with_valid_working_codex(self):
        self._attach([{'id': 't1', 'working': True}, {'id': 't2'}])
        out = self._poll_render({'scope': 'conversation', 'pinned': 'ghost'},
                                active_title='t1', detection_valid=True)
        self.assertTrue(out['selection']['live'])
        self.assertIn('t1', self.panel.pet.toolTip())
        self.assertIn('Codex', self.panel.connection.text())



    def test_source_failure_clears_live_keeps_history_honest(self):
        poller = self._attach([{'id': 't1', 'working': True}])
        live = self._poll_render(active_title='t1', detection_valid=True,
                                 now=NOW_S)
        self.assertTrue(live['selection']['live'])
        from unittest.mock import patch
        from providers import CodexProvider
        with patch.object(CodexProvider, 'read',
                          side_effect=RuntimeError('boom')):
            failed = self._poll_render(now=NOW_S)
        # Failed Codex source revokes Live and cannot reuse cached totals.
        self.assertFalse(failed['selection']['live'])
        self.assertIsNone(failed['result'].get('working_context'))
        self.assertNotIn('gpt-6-astra', self.panel.model.text())
        self.assertIn('Codex', self.panel.connection.text())
        # Unavailable Hub state uses an em dash beside explicit source failure.
        self.assertEqual(self.panel.total.text(), '—')
        self.assertFalse(failed['selection']['source_available'])
        self.assertFalse(failed['result']['available'])
        self.assertEqual(failed['codex']['reason'], 'status_read_failed')
        self.assertIn(text('no_reliable_record', self.panel.language), self.panel.connection.text())



    def test_late_generation_quota_and_scope_ignored(self):
        self._attach([{'id': 't1', 'working': True}])
        first = self._poll_render(active_title='t1', detection_valid=True,
                                  now=NOW_S)
        first_total = self.panel.total.text()
        stale = dict(first['result'])
        stale['generation'] = first['generation'] - 1
        stale['scope'] = 'project'
        self.panel.render(stale)
        self.app.processEvents()
        self.assertEqual(self.panel.total.text(), first_total)
        self.panel.receive_limits(dict(provider_id='codex', sampled=time.time(),
                                       limits={'primary': {'usedPercent': 30,
                                                           'windowDurationMins': 300,
                                                           'resetsAt': time.time() + 1800}}))
        self.app.processEvents()
        self.assertIn('70%', self.panel.five.value.text())


    def test_codex_unavailable_preserves_quota(self):
        self._attach([{'id': 't1', 'working': True}])
        self._poll_render(active_title='t1', detection_valid=True)
        self.panel.show(); self.app.processEvents()
        self.panel.receive_limits(dict(
            sampled=time.time(),
            limits={'primary': {'usedPercent': 30, 'windowDurationMins': 300,
                                'resetsAt': time.time() + 18000}}))
        self.app.processEvents()
        self.assertIn('70%', self.panel.five.value.text())
        gone = self.work / 'codex-gone'
        gone.mkdir(exist_ok=True)
        write_home(str(gone), [{'id': 't9'}])
        import shutil
        shutil.rmtree(gone)
        from providers import CodexProvider
        from usage import CodexStore
        self.panel.provider_poller.codex = CodexProvider(CodexStore(gone))
        out = self._poll_render({'tracking_provider': 'codex'})
        self.assertFalse(out['selection']['live'])
        self.assertIn('70%', self.panel.five.value.text())
        self.assertTrue(self.panel.five.reset.isVisible())



    def test_change_scope_mid_read_via_control(self):
        import threading
        from providers import CodexProvider
        poller = self._attach([{'id': 't1', 'working': True}, {'id': 't2'}])
        self._poll_render({'scope': 'conversation', 'pinned': 't2'},
                          active_title='t1', detection_valid=True)
        # Settle the render's trailing submit first: _poll_render leaves
        # its last poll in flight, and a held poll started on an
        # occupied slot would never enter the blocking read (worker
        # entry would time out under load).
        self.assertTrue(poller.drain(timeout=10))
        entered, release = self._hold(CodexProvider)
        try:
            thread, _ = self._poll_thread(
                {'scope': 'conversation', 'pinned': 't2'},
                active_title='t1', detection_valid=True)
            self.assertTrue(entered.wait(timeout=10))
            thread.join(timeout=10)
            self.assertFalse(thread.is_alive())
            # Real quick control mid-read: invalidates (epoch + generation
            # advance at once), then repaints from cache without waiting
            # for the blocked read.
            before = poller.generation
            self.panel.change_scope('project')
            self.assertEqual(self.panel.prefs['scope'], 'project')
            self.assertGreater(poller.generation, before)
            release.set()
            self.assertTrue(poller.drain())
            out = self._poll_render({'scope': 'project'},
                                    active_title='t1', detection_valid=True)
            self.assertEqual(out['result'].get('scope'), 'project')
            from localization import scope_text
            self.assertIn(
                scope_text('project', self.panel.language),
                self.panel.scope_button.text())
        finally:
            release.set()



    def _hold(self, target):
        import threading
        entered, release = threading.Event(), threading.Event()
        orig = target.read
        def blocking(inner_self, *args, **kwargs):
            entered.set()
            self.assertTrue(release.wait(timeout=30))
            return orig(inner_self, *args, **kwargs)
        target.read = blocking
        self.addCleanup(setattr, target, 'read', orig)
        return entered, release



    def _poll_thread(self, prefs, **kw):
        outcome = {}
        thread = threading.Thread(
            target=lambda: outcome.setdefault(
                'out', self.panel.provider_poller.poll(prefs, **kw)),
            daemon=True)
        thread.start()
        return thread, outcome



    def test_bubble_binds_activity_session_not_scope_title(self):
        self._attach([{'id': 't1', 'working': True}, {'id': 't2'}])
        # Codex side first: scope title t2, bubble follows working t1.
        self._poll_render({'scope': 'conversation', 'pinned': 't2'},
                          active_title='t1', detection_valid=True)
        self.assertIn('t2', self.panel.title.text())
        self.assertIn('t1', self.panel.pet.toolTip())

    def _attach(self, threads):
        self.panel.provider_poller.drain(timeout=10)
        self.panel.provider_poller.close()
        home = self._home(f'codex-{len(list(self.work.iterdir()))}', threads)
        self.panel.provider_poller = ProviderPoller(home)
        return self.panel.provider_poller

    def test_settings_exposes_no_visible_provider_selector(self):
        settings = Settings(self.panel)
        settings.show()
        self.app.processEvents()
        tracking = getattr(settings, 'tracking', None)
        self.assertTrue(tracking is None or not tracking.isVisible())
        self.assertEqual(self.panel.prefs['tracking_provider'], 'codex')
        settings.close()

    def test_legacy_preference_does_not_switch_provider_or_context(self):
        self._attach([{'id': 't1', 'working': True}])
        before = self._poll_render(active_title='t1', detection_valid=True, now=NOW_S)
        for legacy in ('auto', 'opencode', 'unknown'):
            after = self._apply_render({'scope': 'global', 'tracking_provider': legacy}, now=NOW_S)
            self.assertEqual(after['preference'], 'codex')
            self.assertEqual(after['result']['provider_id'], 'codex')
            self.assertEqual(after['result']['tokens'], before['result']['tokens'])
            self.assertNotIn('OpenCode', self.panel.connection.text())

    def test_long_codex_project_and_model_keep_layout_usable(self):
        self._attach([{'id': 't1'}])
        data = dict(self._poll_render(now=NOW_S)['result'])
        data.update(provider_id='codex', model='MODEL ' + 'x' * 400,
                    project='PROJECT ' + 'y' * 400)
        self.panel.render(data)
        self.panel.show()
        self.app.processEvents()
        self.assertLessEqual(self.panel.width(), 480)
        self.assertGreater(self.panel.model.width(), 0)
        self.assertGreater(self.panel.project.width(), 0)



def _codex_entry(key, project='PROJ', total=110, input_=100, output=10,
                 model='gpt-6-astra', activity_at=100.0):
    return {'provider_id': 'codex', 'task_key': key, 'working': True,
            'activity_valid': True, 'activity_at': activity_at,
            'display': {'project': project},
            'presentation': {
                'tokens': {'total_tokens': total, 'input_tokens': input_,
                           'output_tokens': output,
                           'cached_input_tokens': None,
                           'cache_write_input_tokens': None,
                           'reasoning_output_tokens': None},
                'model': model, 'effort': 'high', 'context': 50,
                'available': True}}


def _secondary_codex_entry(key, project='alpha', tokens=None,
                           total=1012, model='gpt-6-sol', activity_at=None):
    if tokens is None:
        input_ = total * 3 // 4 if total is not None else None
        output = total - input_ if total is not None else None
        tokens = (input_, output, 0 if total is not None else None,
                  input_ // 2 if input_ is not None else None, 0 if total is not None else None)
    names = ('input_tokens', 'output_tokens', 'reasoning_output_tokens',
             'cached_input_tokens', 'cache_write_input_tokens')
    return {'provider_id': 'codex', 'task_key': key, 'working': True,
            'activity_valid': True, 'activity_at': activity_at,
            'display': {'project': project},
            'presentation': {'tokens': dict(zip(names, tokens), total_tokens=total),
                             'model': model, 'effort': 'medium',
                             'context': None, 'available': True}}


_PET_RECT = (100, 100, 272, 330)
_SCREEN_RECT = (0, 0, 1919, 1079)
# Ordinary centered layout (Astra fixture): full ring must fit here.
_CENTER_PET_RECT = (824, 375, 272, 330)
_CENTER_HUB = (960.0, 540.0)
# Genuinely constrained edge fixtures: no full ring may be selected.
_EDGE_PET_RECT = (40, 40, 272, 330)
_LOWERRIGHT_PET_RECT = (1500, 600, 272, 330)


def _assert_finite_task_parking(test, manager, pet_rect, screen_rect):
    stamp = 1000.0
    for frame in range(6000):
        before = {k: (w.x(), w.y()) for k, w in manager._windows.items()
                  if k not in manager._ring_staged}
        manager.tick_visual(stamp, pet_rect=pet_rect, screen_rect=screen_rect)
        stamp += 0.04
        after = {k: (w.x(), w.y()) for k, w in manager._windows.items()
                 if k not in manager._ring_staged}
        for key in before.keys() & after.keys():
            test.assertLessEqual(sum(abs(a - b) for a, b in
                                     zip(before[key], after[key])), 16)
        test.assertTrue(manager._nominal_valid(after, pet_rect, screen_rect))
        if manager._park_blend is None and manager._ring_blend is None:
            test.assertFalse(manager._ring_staged)
            for key, position in after.items():
                test.assertEqual(position, manager._auto_home(
                    key, pet_rect, screen_rect))
            return
    test.fail('retirement parking exceeded 240 seconds of active time')


class TaskPanelManagerTests(unittest.TestCase):
    """Historical exterior-route regressions with current Codex task fixtures.

    Compact-halo integration is covered by current Expanded/MultiTask tests.
    """
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.pref_patch = patch('widget.PREF_DIR', Path(self.temp.name))
        self.pref_patch.start()
        self.panel = Panel(live=False)
        self.panel.pet = DesktopPet(self.panel)
        self.panel.pet.activity_timer.stop()
        self.panel.task_manager.shutdown()
        self.manager = TaskPanelManager(self.panel, legacy_exterior_motion=True)
        self.panel.task_manager = self.manager

    def tearDown(self):
        self.manager.shutdown()
        self.panel.pet.close(); self.panel.tray.hide()
        if self.panel.analytics_window: self.panel.analytics_window.close()
        self.panel.closing = True; self.panel.close()
        self.panel.deleteLater(); self.app.processEvents()
        self.pref_patch.stop(); self.temp.cleanup()

    def _apply(self, tasks, preference='auto', generation=None,
               language='en'):
        return self.manager.apply_snapshot(
            tasks, preference=preference, generation=generation,
            language=language, pet_rect=_PET_RECT,
            screen_rect=_SCREEN_RECT)

    def _apply_at(self, tasks, pet_rect, preference='auto',
                  generation=None, language='en'):
        return self.manager.apply_snapshot(
            tasks, preference=preference, generation=generation,
            language=language, pet_rect=pet_rect,
            screen_rect=_SCREEN_RECT)

    def _tick_at(self, stamp, pet_rect):
        self.manager.tick_visual(stamp, pet_rect=pet_rect,
                                 screen_rect=_SCREEN_RECT)

    def _hub_angle(self, key, hub=_CENTER_HUB):
        import math
        x, y = self._orb_pos(key)
        return math.degrees(math.atan2(
            x + 56.0 - hub[0], -(y + 48.0 - hub[1]))) % 360.0

    def _orb_pos(self, key):
        orb = self.manager.window_for(key)
        return (orb.x(), orb.y())

    def _auto_home(self, key):
        visible = sorted(self.manager.slot_for(k)
                         for k in self.manager.window_identities())
        return pet_geometry.star_ring_anchor(
            visible, self.manager.slot_for(key),
            _PET_RECT, _SCREEN_RECT)

    def test_empty_set_shows_no_orbs(self):
        self.assertEqual(self._apply([]), [])
        self.assertEqual(self.manager.window_count(), 0)

    def test_single_task_gets_exactly_one_orb(self):
        task = _codex_entry('t1')
        keys = self._apply([task])
        self.assertEqual(keys, [('codex', 't1')])
        orb = self.manager.window_for(('codex', 't1'))
        self.assertIsNotNone(orb)
        self.assertTrue(orb.isVisible())
        self.assertEqual(orb.number_label.text(), '1')
        self.assertEqual(self._orb_pos(('codex', 't1')),
                         self._auto_home(('codex', 't1')))

    def test_two_tasks_get_two_orbs_and_reuse(self):
        first = _codex_entry('t1')
        second = _secondary_codex_entry('z-secondary:s1')
        keys = self._apply([first, second])
        self.assertEqual(len(keys), 2)
        orb = self.manager.window_for(('codex', 'z-secondary:s1'))
        keys = self._apply([first, second])
        self.assertEqual(len(keys), 2)
        self.assertIs(self.manager.window_for(('codex', 'z-secondary:s1')),
                      orb)

    def test_five_tasks_get_five_orbs(self):
        tasks = ([_codex_entry(f't{i}') for i in range(2)]
                 + [_secondary_codex_entry(f'z-secondary:s{i}') for i in range(3)])
        keys = self._apply(tasks)
        self.assertEqual(len(keys), 5)
        self.assertEqual(self.manager.window_count(), 5)
        positions = [self._orb_pos(k) for k in keys]
        self.assertEqual(len(set(positions)), 5)

    def test_eight_tasks_have_no_silent_cap(self):
        tasks = [_secondary_codex_entry(f'z-secondary:ses_{i}', activity_at=float(i))
                 for i in range(8)]
        keys = self._apply(tasks)
        self.assertEqual(len(keys), 8)
        self.assertEqual(self.manager.window_count(), 8)
        positions = [self._orb_pos(k) for k in keys]
        self.assertEqual(len(set(positions)), 8)

    def test_label_stable_across_sibling_retirement(self):
        alpha = _codex_entry('a', activity_at=10.0)
        beta = _codex_entry('b', activity_at=20.0)
        self._apply([alpha, beta])
        beta_key = ('codex', 'b')
        self.assertEqual(
            self.manager.window_for(beta_key).number_label.text(), '1')
        self._apply([beta])
        orb = self.manager.window_for(beta_key)
        self.assertIsNotNone(orb)
        self.assertEqual(orb.number_label.text(), '1')
        gamma = _codex_entry('c', activity_at=30.0)
        self._apply([beta, gamma])
        self.assertEqual(
            self.manager.window_for(('codex', 'c')).number_label.text(),
            '2')
        self.assertEqual(
            self.manager.window_for(beta_key).number_label.text(), '1')

    def test_slot_stable_across_activity_changes(self):
        tasks = [_codex_entry(k, activity_at=float(i))
                 for i, k in enumerate(('a', 'b', 'c'))]
        self._apply(tasks)
        before = {k: self.manager.slot_for((('codex', k))) for k in 'abc'}
        shuffled = [_codex_entry(k, activity_at=float(99 - i))
                    for i, k in enumerate(('a', 'b', 'c'))]
        self._apply(shuffled)
        after = {k: self.manager.slot_for((('codex', k))) for k in 'abc'}
        self.assertEqual(before, after)
        positions_before = {k: self._orb_pos(('codex', k)) for k in 'abc'}
        self.app.processEvents()
        positions_after = {k: self._orb_pos(('codex', k)) for k in 'abc'}
        self.assertEqual(positions_before, positions_after)
        for k in 'abc':
            self.assertEqual(positions_before[k],
                             self._auto_home(('codex', k)))

    def test_retired_slot_reused_deterministically(self):
        tasks = [_codex_entry(k, activity_at=float(i))
                 for i, k in enumerate(('a', 'b', 'c'))]
        self._apply(tasks)
        slots_before = {k: self.manager.slot_for(('codex', k)) for k in 'abc'}
        remaining = [_codex_entry(k, activity_at=float(i))
                     for i, k in enumerate(('a', 'c'))]
        self._apply(remaining)
        self.assertEqual(self.manager.slot_for(('codex', 'a')),
                         slots_before['a'])
        self.assertEqual(self.manager.slot_for(('codex', 'c')),
                         slots_before['c'])
        newcomer = _codex_entry('d', activity_at=999.0)
        self._apply(remaining + [newcomer])
        self.assertEqual(self.manager.slot_for(('codex', 'd')),
                         slots_before['b'])
        self.assertNotEqual(self.manager.slot_for(('codex', 'd')),
                            self.manager.slot_for(('codex', 'a')))

    def test_legacy_preferences_preserve_all_codex_tasks(self):
        tasks = [_codex_entry('a'), _codex_entry('b')] + [
            _secondary_codex_entry(f'z-secondary:{key}') for key in 'cde']
        self._apply(tasks)
        before = {key: self.manager.window_for(key) for key in self.manager.window_identities()}
        for preference in ('codex', 'auto', 'opencode', 'unknown'):
            self.assertEqual(set(self._apply(tasks, preference=preference)), set(before))
            for key, orb in before.items():
                self.assertIs(self.manager.window_for(key), orb)


    def test_all_codex_task_variants_always_surfaced(self):
        codex = _codex_entry('a')
        first = _secondary_codex_entry('z-secondary:b')
        second = _secondary_codex_entry('z-secondary:c')
        keys = self._apply([codex, first, second])
        self.assertEqual(len(keys), 3)
        self.assertIn(('codex', 'a'), keys)
        self.assertIn(('codex', 'z-secondary:b'), keys)
        self.assertIn(('codex', 'z-secondary:c'), keys)

    def test_late_generation_never_resurrects(self):
        alpha = _codex_entry('a')
        beta = _codex_entry('b')
        gamma = _codex_entry('c')
        self._apply([alpha, beta], generation=5)
        self.assertEqual(self._apply([alpha, beta, gamma], generation=4),
                         [('codex', 'a'), ('codex', 'b')])
        self.assertIsNone(self.manager.window_for(('codex', 'c')))
        self._apply([beta], generation=6)
        self.assertIsNone(self.manager.window_for(('codex', 'a')))
        self.assertIsNotNone(self.manager.window_for(('codex', 'b')))

    def test_scene_hide_retains_universe_assignments(self):
        tasks = [_codex_entry('a'), _secondary_codex_entry('z-secondary:b')]
        self._apply(tasks, generation=1)
        before = {key: (self.manager.label_number_for(key), self.manager.slot_for(key))
                  for key in self.manager.window_identities()}
        self.manager.set_visible(False)
        self.assertTrue(all(not self.manager.window_for(key).isVisible() for key in before))
        self._apply(tasks, generation=2)
        self.manager.set_visible(True)
        self.assertEqual(before, {key: (self.manager.label_number_for(key),
                                       self.manager.slot_for(key)) for key in before})


    def test_hidden_scene_keeps_lifetime_state(self):
        tasks = [_codex_entry('a'), _secondary_codex_entry('z-secondary:c')]
        self._apply(tasks, generation=1)
        key = ('codex', 'z-secondary:c')
        orb = self.manager.window_for(key)
        number, slot = self.manager.label_number_for(key), self.manager.slot_for(key)
        self.manager.set_visible(False)
        self._apply(tasks, generation=2)
        self.manager.set_visible(True)
        self.assertIs(self.manager.window_for(key), orb)
        self.assertEqual((self.manager.label_number_for(key), self.manager.slot_for(key)),
                         (number, slot))


    def test_composition_retires_only_removed_codex_task(self):
        tasks = [_codex_entry('a'), _codex_entry('b'), _secondary_codex_entry('z-secondary:c')]
        self._apply(tasks, generation=1)
        key = ('codex', 'z-secondary:c')
        survivor = self.manager.window_for(key)
        number, slot = self.manager.label_number_for(key), self.manager.slot_for(key)
        self._apply([tasks[0], tasks[2]], generation=2)
        self.assertIsNone(self.manager.label_number_for(('codex', 'b')))
        self.assertIs(self.manager.window_for(key), survivor)
        self.assertEqual((self.manager.label_number_for(key), self.manager.slot_for(key)),
                         (number, slot))


    def test_completion_retires_only_finished_orb(self):
        self.panel.prefs['pet_motion'] = False
        alpha = _codex_entry('a', activity_at=10.0)
        beta = _codex_entry('b', activity_at=20.0)
        gamma = _codex_entry('c', activity_at=30.0)
        self._apply([alpha, beta, gamma])
        survivors = {k: self.manager.window_for(k) for k in
                     (('codex', 'a'), ('codex', 'c'))}
        numbers = {k: w.number_label.text() for k, w in survivors.items()}
        slots = {k: self.manager.slot_for(k) for k in survivors}
        positions = {k: self._orb_pos(k) for k in survivors}
        self._apply([alpha, gamma])
        self.assertIsNone(self.manager.window_for(('codex', 'b')))
        # Retirement retains the displayed frame before finite parking.
        for key, orb in survivors.items():
            self.assertIs(self.manager.window_for(key), orb)
            self.assertEqual(orb.number_label.text(), numbers[key])
            self.assertEqual(self.manager.slot_for(key), slots[key])
            self.assertEqual(self._orb_pos(key), positions[key])
        _assert_finite_task_parking(self, self.manager, _PET_RECT, _SCREEN_RECT)
    def test_privacy_sensitive_values_never_visible(self):
        codex = _codex_entry('t1', project='safe-proj')
        codex['title'] = 'PRIVATE REVIEW NOTES'
        codex['prompt'] = 'prompt secret'
        codex['response'] = 'response secret'
        oc = _secondary_codex_entry('z-secondary:ses_SECRET_9', project='path')
        oc['session_title'] = 'My Secret Project'
        oc['directory'] = 'C:\\private\\client\\matter'
        keys = self._apply([codex, oc])
        self.assertEqual(len(keys), 2)
        visible = '\n'.join(
            self.manager.window_for(k).panel_text() for k in keys)
        for secret in ('ses_SECRET_9', 'C:\\private\\client\\matter',
                       'PRIVATE REVIEW NOTES', 'My Secret Project',
                       'prompt secret', 'response secret'):
            self.assertNotIn(secret, visible)
        self.assertIn(text('task_panel_label', 'en', n=1), visible)
        self.assertIn('Working', visible)
        self.assertIn('Codex', visible)
        self.assertNotIn('OpenCode', visible)

    def test_optional_context_fields_are_absent(self):
        task = _secondary_codex_entry('z-secondary:s1')
        self._apply([task])
        visible = self.manager.window_for(
            ('codex', 'z-secondary:s1')).panel_text()
        for word in ('Context Limit', 'Messages', 'Created', 'Tool Calls'):
            self.assertNotIn(word, visible)

    def test_default_is_not_a_fake_task(self):
        self.assertEqual(self.manager.window_identities(), [])
        self._apply([_codex_entry('t1')])
        self.assertEqual(self.manager.window_identities(), [('codex', 't1')])
        self.assertNotIn((None, None), self.manager.window_identities())
        self._apply([])
        self.assertEqual(self.manager.window_identities(), [])
        self.assertNotIn((None, None), self.manager.window_identities())

    def test_retire_one_keeps_app_and_siblings_alive(self):
        self.panel.prefs['pet_motion'] = False
        alpha = _codex_entry('a')
        beta = _codex_entry('b')
        self._apply([alpha, beta])
        survivor = self.manager.window_for(('codex', 'b'))
        survivor_number = survivor.number_label.text()
        survivor_slot = self.manager.slot_for(('codex', 'b'))
        survivor_position = self._orb_pos(('codex', 'b'))
        self._apply([beta])
        self.assertIsNone(self.manager.window_for(('codex', 'a')))
        self.assertTrue(survivor.isVisible())
        # Identity and frame zero survive the retirement transition.
        self.assertIs(self.manager.window_for(('codex', 'b')), survivor)
        self.assertEqual(survivor.number_label.text(), survivor_number)
        self.assertEqual(self.manager.slot_for(('codex', 'b')),
                         survivor_slot)
        self.assertEqual(self._orb_pos(('codex', 'b')), survivor_position)
        _assert_finite_task_parking(self, self.manager, _PET_RECT, _SCREEN_RECT)
        self.assertFalse(QApplication.instance().closingDown())

    def test_shutdown_closes_all_orbs(self):
        tasks = [_codex_entry('a'), _secondary_codex_entry('z-secondary:b')]
        self._apply(tasks)
        self.assertEqual(self.manager.window_count(), 2)
        self.manager.shutdown()
        self.assertEqual(self.manager.window_count(), 0)

    def test_hide_and_show_follow_main_panel(self):
        self._apply([_codex_entry('a'), _codex_entry('b')])
        orb = self.manager.window_for(('codex', 'b'))
        self.manager.set_visible(False)
        self.assertFalse(orb.isVisible())
        self.manager.set_visible(True)
        self.assertTrue(orb.isVisible())

    def test_repeated_cycles_do_not_leak_references(self):
        alpha = _codex_entry('a')
        beta = _codex_entry('b')
        for _ in range(3):
            self._apply([alpha, beta])
            self.assertEqual(self.manager.window_count(), 2)
            self._apply([])
            self.assertEqual(self.manager.window_count(), 0)
        self.assertEqual(self.manager.window_identities(), [])

    def test_task_panel_window_preserved_for_codex_detail(self):
        window = TaskPanelWindow(provider_id='codex')
        try:
            window.set_task(_secondary_codex_entry('secondary', total=120,
                tokens=(100, 20, 5, 80, 0), model='mock-model'), 'Active task 1', 'en')
            rows = {key: value[1].text() for key, value in window._rows.items()}
            self.assertIn('120', rows['total'])
            self.assertIn('100', rows['input'])
            self.assertIn('20', rows['output'])
            self.assertEqual(rows['model'], 'mock-model')
            for unsupported in ('cost', 'cache_read', 'cache_write', 'reasoning'):
                self.assertNotIn(unsupported, rows)
        finally:
            window.close()
            window.deleteLater()

    def test_click_below_threshold_activates_without_drag(self):
        task = _codex_entry('t1')
        self._apply([task])
        key = ('codex', 't1')
        orb = self.manager.window_for(key)
        before = self._orb_pos(key)
        center = orb.rect().center()
        root = orb.mapToGlobal(center)
        press = QMouseEvent(QEvent.MouseButtonPress, QPointF(center),
                            QPointF(root), Qt.LeftButton,
                            Qt.LeftButton, Qt.NoModifier)
        orb.mousePressEvent(press)
        jitter = QPointF(root.x() + 2, root.y() + 1)
        move = QMouseEvent(QEvent.MouseMove, QPointF(center) + QPointF(2, 1),
                           jitter, Qt.LeftButton, Qt.LeftButton,
                           Qt.NoModifier)
        orb.mouseMoveEvent(move)
        release = QMouseEvent(QEvent.MouseButtonRelease,
                              QPointF(center) + QPointF(2, 1), jitter,
                              Qt.LeftButton, Qt.NoButton, Qt.NoModifier)
        orb.mouseReleaseEvent(release)
        self.assertEqual(self.manager.last_activated, key)
        self.assertEqual(self._orb_pos(key), before)

    def test_drag_above_threshold_moves_nothing(self):
        # Collapsed stars are not draggable: press + move + release
        # beyond the threshold suppresses the click AND repositions
        # nothing. No override store exists anymore.
        task = _codex_entry('t1')
        self._apply([task])
        key = ('codex', 't1')
        orb = self.manager.window_for(key)
        before = self._orb_pos(key)
        self.assertFalse(hasattr(self.manager, 'set_user_position'))
        self.assertFalse(hasattr(self.manager, 'user_position_for'))
        self.assertFalse(hasattr(self.manager, 'reset_layout'))
        center = orb.rect().center()
        root = orb.mapToGlobal(center)
        press = QMouseEvent(QEvent.MouseButtonPress, QPointF(center),
                            QPointF(root), Qt.LeftButton,
                            Qt.LeftButton, Qt.NoModifier)
        orb.mousePressEvent(press)
        target = QPoint(root.x() + 200, root.y() + 120)
        move = QMouseEvent(QEvent.MouseMove,
                           QPointF(center) + QPointF(200, 120),
                           QPointF(target), Qt.LeftButton, Qt.LeftButton,
                           Qt.NoModifier)
        orb.mouseMoveEvent(move)
        release = QMouseEvent(QEvent.MouseButtonRelease,
                              QPointF(center) + QPointF(200, 120),
                              QPointF(target), Qt.LeftButton, Qt.NoButton,
                              Qt.NoModifier)
        orb.mouseReleaseEvent(release)
        self.assertIsNone(self.manager.last_activated)
        self.assertEqual(self._orb_pos(key), before)
        left, top, right, bottom = _SCREEN_RECT
        width, height = pet_geometry.TASK_STAR_SIZE
        self.assertGreaterEqual(before[0], left)
        self.assertGreaterEqual(before[1], top)
        self.assertLessEqual(before[0] + width, right + 1)
        self.assertLessEqual(before[1] + height, bottom + 1)

    def test_refresh_without_ticks_never_moves_orbs(self):
        alpha = _codex_entry('a', activity_at=10.0)
        beta = _codex_entry('b', activity_at=20.0)
        self._apply([alpha, beta], generation=1)
        key = ('codex', 'b')
        home = self._orb_pos(key)
        self._apply([alpha, beta], generation=2)
        self.assertEqual(self._orb_pos(key), home)
        # Metric-only and activity-only updates must not move it.
        moved = _codex_entry('a', total=999, input_=800, output=199,
                             activity_at=10.0)
        self._apply([moved, beta], generation=3)
        self.assertEqual(self._orb_pos(key), home)
        changed = _codex_entry('a', activity_at=555.0)
        self._apply([changed, beta], generation=4)
        self.assertEqual(self._orb_pos(key), home)
        # Filter hide/restore and generation jumps keep it too.
        self._apply([changed, beta], preference='codex', generation=5)
        self.assertEqual(self._orb_pos(key), home)
        self._apply([changed, beta], generation=100)
        self.assertEqual(self._orb_pos(key), home)
        # Membership changes re-anchor deterministically to the new
        # composition; nothing moves without ticks otherwise.

    def test_auto_orbs_follow_pet_on_reapply(self):
        alpha = _codex_entry('a')
        beta = _codex_entry('b')
        self._apply([alpha, beta])
        key_a, key_b = ('codex', 'a'), ('codex', 'b')
        moved_pet = (_PET_RECT[0] + 300, _PET_RECT[1],
                     _PET_RECT[2], _PET_RECT[3])
        self.manager.apply_snapshot(
            [alpha, beta], language='en', pet_rect=moved_pet,
            screen_rect=_SCREEN_RECT)
        visible = sorted(self.manager.slot_for(k)
                         for k in self.manager.window_identities())
        for key in (key_a, key_b):
            expected = pet_geometry.star_ring_anchor(
                visible, self.manager.slot_for(key),
                moved_pet, _SCREEN_RECT)
            self.assertEqual(self._orb_pos(key), expected)

    def test_no_drag_state_on_manager(self):
        self._apply([_codex_entry('a')])
        for name in ('set_user_position', 'user_position_for',
                     'reset_layout'):
            self.assertFalse(hasattr(self.manager, name), name)

    def test_star_surface_is_custom_painted_not_button(self):
        from widget import TaskOrbWindow
        task = _codex_entry('t1')
        self._apply([task])
        orb = self.manager.window_for(('codex', 't1'))
        self.assertIsInstance(orb, TaskOrbWindow)
        self.assertEqual((orb.width(), orb.height()),
                         pet_geometry.TASK_STAR_SIZE)
        # Custom star paint path exists and owns rendering.
        self.assertNotEqual(type(orb).paintEvent, QWidget.paintEvent)
        # No button chrome, no surface box, no provider text widget.
        self.assertFalse(hasattr(orb, 'provider_label'))
        self.assertFalse(hasattr(orb, 'status_dot'))
        self.assertEqual(orb.styleSheet(), '')
        # Static D2A paint parameters exist for D2B breathing.
        for name in ('halo_alpha', 'halo_radius', 'core_intensity',
                     'facet_intensity', 'star_scale'):
            self.assertEqual(getattr(orb, name), 1.0)

    def test_star_hit_body_clicks_corner_ignored(self):
        from PySide6.QtCore import QPoint
        task = _codex_entry('t1')
        self._apply([task])
        key = ('codex', 't1')
        orb = self.manager.window_for(key)
        cx, cy = pet_geometry.TASK_STAR_CENTER
        self.assertTrue(orb.is_star_hit(QPoint(cx, cy)))
        self.assertTrue(orb.is_star_hit(
            QPoint(orb.number_label.geometry().center())))
        # Clearly transparent pixels must not count as star clicks
        # (outside both the hit disc and the label strip).
        for corner in (QPoint(2, 2), QPoint(109, 2), QPoint(2, 80),
                       QPoint(109, 80)):
            self.assertFalse(orb.is_star_hit(corner), corner)
        # A press in the transparent corner never arms click or drag.
        center = orb.rect().center()
        root = orb.mapToGlobal(center)
        press = QMouseEvent(QEvent.MouseButtonPress, QPointF(2, 2),
                            QPointF(root.x() - 54, root.y() - 54),
                            Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        orb.mousePressEvent(press)
        self.assertIsNone(orb._press_global)
        release = QMouseEvent(QEvent.MouseButtonRelease, QPointF(2, 2),
                              QPointF(root.x() - 54, root.y() - 54),
                              Qt.LeftButton, Qt.NoButton, Qt.NoModifier)
        orb.mouseReleaseEvent(release)
        self.assertIsNone(self.manager.last_activated)

    def test_star_click_opens_detail_preserving_star(self):
        # V1.3 detail is task-local; the existing Star retains its size and identity.
        alpha = _codex_entry('a')
        beta = _codex_entry('b')
        self._apply([alpha, beta])
        key = ('codex', 'a')
        orb = self.manager.window_for(key)
        center = orb.rect().center()
        root = orb.mapToGlobal(center)
        press = QMouseEvent(QEvent.MouseButtonPress, QPointF(center),
                            QPointF(root), Qt.LeftButton,
                            Qt.LeftButton, Qt.NoModifier)
        orb.mousePressEvent(press)
        release = QMouseEvent(QEvent.MouseButtonRelease, QPointF(center),
                              QPointF(root), Qt.LeftButton, Qt.NoButton,
                              Qt.NoModifier)
        orb.mouseReleaseEvent(release)
        self.assertEqual(self.manager.last_activated, key)
        self.assertEqual(self.manager.window_count(), 2)
        self.assertEqual(self.manager.expanded_identity, key)
        self.assertTrue(self.manager.detail_window.isVisible())
        self.assertEqual((orb.width(), orb.height()),
                         pet_geometry.TASK_STAR_SIZE)

    def test_shared_timer_exists_but_stays_idle(self):
        # D2B clock exists as one shared QTimer yet never arms itself
        # under test: motion tests drive tick_visual() manually.
        from PySide6.QtCore import QTimer
        task = _codex_entry('t1')
        self._apply([task])
        timer = self.manager.motion_timer
        self.assertIsInstance(timer, QTimer)
        self.assertEqual(timer.interval(),
                         pet_geometry.MOTION_TICK_MS)
        self.assertFalse(timer.isActive())
        self.assertFalse(hasattr(self.manager, 'orbit_timer'))
        self.assertFalse(hasattr(self.manager, 'breath_timer'))
        orb = self.manager.window_for(('codex', 't1'))
        timers = [c for c in orb.children()
                  if c.__class__.__name__ == 'QTimer']
        self.assertEqual(timers, [])

    def _tick(self, stamp):
        self.manager.tick_visual(stamp, pet_rect=_PET_RECT,
                                 screen_rect=_SCREEN_RECT)

    def _orb_positions(self):
        return {k: (self.manager.window_for(k).x(),
                    self.manager.window_for(k).y())
                for k in self.manager.window_identities()}

    def test_tick_advances_orbit_deterministically(self):
        self._apply([_codex_entry('a'), _codex_entry('b'),
                     _secondary_codex_entry('z-secondary:c')])
        homes = self._orb_positions()
        self.assertEqual(self.manager._orbit_mode[0], 'arc')
        self.assertGreater(self.manager._orbit_mode[1], 0.0)
        self._tick(1000.0)
        self.assertEqual(self._orb_positions(), homes)
        # Visual clocks advance at most one nominal 40 ms frame per
        # tick (delayed callbacks never catch up hidden time), so
        # drive real 40 ms frames: 2 s of motion must visibly move.
        stamp = 1000.0
        for _ in range(50):
            stamp += 0.04
            self._tick(stamp)
        moved = self._orb_positions()
        self.assertTrue(any(moved[k] != homes[k] for k in homes),
                        'orbit must visibly advance within 2 s')
        for key in homes:
            self.assertAlmostEqual(
                self.manager._orbit_t.get(key), 2.0, places=6)

    def test_orbit_matches_across_instances(self):
        self._apply([_codex_entry('a'), _codex_entry('b')])
        for stamp in (1000.0, 1001.0, 1002.0, 1003.0):
            self._tick(stamp)
        first = self._orb_positions()
        panel2 = Panel(live=False)
        panel2.pet = DesktopPet(panel2)
        panel2.pet.activity_timer.stop()
        try:
            panel2.task_manager.shutdown()
            manager2 = TaskPanelManager(panel2, legacy_exterior_motion=True)
            panel2.task_manager = manager2
            manager2.apply_snapshot(
                [_codex_entry('a'), _codex_entry('b')], language='en',
                pet_rect=_PET_RECT, screen_rect=_SCREEN_RECT)
            for stamp in (1000.0, 1001.0, 1002.0, 1003.0):
                manager2.tick_visual(stamp, pet_rect=_PET_RECT,
                                     screen_rect=_SCREEN_RECT)
            second = {k: (manager2.window_for(k).x(),
                          manager2.window_for(k).y())
                      for k in manager2.window_identities()}
            self.assertEqual(first, second)
        finally:
            manager2.shutdown()
            panel2.pet.close()
            panel2.tray.hide()
            panel2.closing = True
            panel2.close()
            panel2.deleteLater()
            self.app.processEvents()

    def test_orbit_speed_bounded(self):
        # Calm-speed bound derived from the selected mode itself: peak
        # one-sided-arc rate is amplitude*pi/period, times lane radius,
        # times sqrt(2) for the diagonal Manhattan worst case, plus
        # integer-quantization slack. A runaway clock fails this.
        import math
        self._apply([_codex_entry('a'), _codex_entry('b'),
                     _secondary_codex_entry('z-secondary:c')])
        self._tick(1000.0)
        mode = self.manager._orbit_mode
        self.assertEqual(mode[0], 'arc')
        peak_rate = math.radians(mode[1]) * math.pi / mode[2]
        caps = {key: math.sqrt(2.0) * params['radius'] * peak_rate + 4.0
                for key, params in self.manager._orbit.items()}
        previous = self._orb_positions()
        for step in range(1, 11):
            self._tick(1000.0 + step)
            current = self._orb_positions()
            for key in previous:
                dx = current[key][0] - previous[key][0]
                dy = current[key][1] - previous[key][1]
                self.assertLessEqual(
                    abs(dx) + abs(dy), caps[key],
                    (key, step, previous[key], current[key]))
            previous = current

    def test_orbit_mode_selection_arc12_corner3(self):
        # Three-star corner composition cannot fit a rigid 360-degree
        # sweep (pet exclusion bites first); selection must pick the
        # widest valid one-sided arc. Pinned exactly: retuning the
        # selector must update this deliberately.
        self._apply([_codex_entry('a'), _codex_entry('b'),
                     _secondary_codex_entry('z-secondary:c')])
        self.assertEqual(self.manager._orbit_mode, ('arc', 12.0, 14.0))

    def test_orbit_mode_selection_arc25_smaller(self):
        self._apply([_codex_entry('a'), _codex_entry('b')])
        self.assertEqual(self.manager._orbit_mode, ('arc', 25.0, 20.5))
        self._apply([_codex_entry('a')])
        self.assertEqual(self.manager._orbit_mode, ('arc', 25.0, 20.5))

    def test_arc_motion_is_hub_centered(self):
        # Hub-centered arcs: hub distance stays constant while the
        # angle genuinely travels. A home+axis*sin() bobber fails the
        # radius half whenever its axis has a radial component; the
        # mean-offset test below kills even the degenerate
        # perpendicular-axis case.
        import math
        self._apply([_codex_entry('a'), _codex_entry('b'),
                     _secondary_codex_entry('z-secondary:c')])
        mode = self.manager._orbit_mode
        self.assertEqual(mode[0], 'arc')
        amplitude, period = mode[1], mode[2]
        pcx = _PET_RECT[0] + _PET_RECT[2] / 2.0
        pcy = _PET_RECT[1] + _PET_RECT[3] / 2.0
        keys = list(self.manager.window_identities())
        radii = {key: [] for key in keys}
        angles = {key: [] for key in keys}
        stamp = 1000.0
        self._tick(stamp)
        # One nominal frame per tick (no hidden-time catch-up), so a
        # full arc cycle needs period/0.04 real frames.
        frames = int(math.ceil(period / 0.04))
        for _ in range(frames):
            stamp += 0.04
            self._tick(stamp)
            for key in keys:
                x, y = self._orb_pos(key)
                cx, cy = x + 56.0, y + 48.0
                radii[key].append(math.hypot(cx - pcx, cy - pcy))
                angles[key].append(math.degrees(
                    math.atan2(cx - pcx, -(cy - pcy))))
        for key in keys:
            self.assertLessEqual(
                max(radii[key]) - min(radii[key]), 5.0, key)
            unwrapped = [angles[key][0]]
            for angle in angles[key][1:]:
                step = angle - unwrapped[-1]
                step += 360.0 * (step < -180.0) - 360.0 * (step > 180.0)
                unwrapped.append(unwrapped[-1] + step)
            self.assertGreaterEqual(
                max(unwrapped) - min(unwrapped), 0.6 * amplitude, key)

    def test_arc_mean_offset_from_home(self):
        # One-sided arcs carry a DC bias: the time-mean position sits
        # off home. Any symmetric home+axis*sin() motion has mean ==
        # home exactly over full periods, so it fails here
        # deterministically regardless of axis choice.
        import math
        self._apply([_codex_entry('a'), _codex_entry('b'),
                     _secondary_codex_entry('z-secondary:c')])
        homes = self._orb_positions()
        period = int(self.manager._orbit_mode[2])
        stamp = 1000.0
        self._tick(stamp)
        total = {key: [0.0, 0.0]
                 for key in self.manager.window_identities()}
        # Full arc cycle at one nominal frame per tick: the mean over
        # complete revolutions exposes the one-sided DC bias.
        frames = int(math.ceil(period / 0.04))
        for _ in range(frames):
            stamp += 0.04
            self._tick(stamp)
            for key in total:
                x, y = self._orb_pos(key)
                total[key][0] += x
                total[key][1] += y
        for key in total:
            mx = total[key][0] / frames - homes[key][0]
            my = total[key][1] / frames - homes[key][1]
            offset = math.hypot(mx, my)
            self.assertGreaterEqual(offset, 3.0, key)
            self.assertLessEqual(offset, 60.0, key)

    def test_arc_motion_spans_two_dimensions(self):
        # The orbital system as a whole must move in X and Y over a
        # full arc cycle (union over stars), not along one line.
        self._apply([_codex_entry('a'), _codex_entry('b'),
                     _secondary_codex_entry('z-secondary:c')])
        period = int(self.manager._orbit_mode[2])
        stamp = 1000.0
        self._tick(stamp)
        xs, ys = [], []
        for _ in range(period):
            stamp += 1.0
            self._tick(stamp)
            for key in self.manager.window_identities():
                x, y = self._orb_pos(key)
                xs.append(x + 56.0)
                ys.append(y + 48.0)
        self.assertGreater(max(xs) - min(xs), 20.0)
        self.assertGreater(max(ys) - min(ys), 20.0)

    def test_orbit_preserves_spacing_through_cycle(self):
        # Every tick position through a full cycle must satisfy the
        # same final footprint rules as static placement: pet
        # exclusion plus pairwise non-overlap.
        self._apply([_codex_entry('a'), _codex_entry('b'),
                     _secondary_codex_entry('z-secondary:c')])
        period = int(self.manager._orbit_mode[2])
        stamp = 1000.0
        self._tick(stamp)
        for _ in range(period):
            stamp += 1.0
            self._tick(stamp)
            self.assertTrue(pet_geometry._windows_valid(
                self._orb_positions(), _PET_RECT, _SCREEN_RECT))

    def test_ring_mode_selected_centered_1_3_5(self):
        # Astra regression: an ordinary centered layout must select a
        # real full ring — never an arc — for 1, 3, and 5 stars.
        # Pinned exactly: retuning the search must update this.
        expected = ('ring', 476.0, 476.0, 45.0, 1.0, 0.0)
        self._apply_at([_codex_entry('a')], _CENTER_PET_RECT)
        self.assertEqual(self.manager._orbit_mode, expected)
        self.assertEqual(self.manager._ring_offsets,
                         {('codex', 'a'): 0.0})
        self._apply_at([_codex_entry('a'), _codex_entry('b'),
                        _secondary_codex_entry('z-secondary:c')],
                       _CENTER_PET_RECT)
        self.assertEqual(self.manager._orbit_mode, expected)
        self.assertEqual(self.manager._ring_offsets,
                         {('codex', 'a'): 0.0, ('codex', 'b'): 120.0,
                          ('codex', 'z-secondary:c'): 240.0})
        self._apply_at([_codex_entry('a'), _codex_entry('b'),
                        _secondary_codex_entry('z-secondary:c'),
                        _secondary_codex_entry('z-secondary:s0'),
                        _secondary_codex_entry('z-secondary:s1')],
                       _CENTER_PET_RECT)
        self.assertEqual(self.manager._orbit_mode, expected)
        self.assertEqual(self.manager._ring_offsets,
                         {('codex', 'a'): 0.0, ('codex', 'b'): 72.0,
                          ('codex', 'z-secondary:c'): 144.0,
                          ('codex', 'z-secondary:s0'): 216.0,
                          ('codex', 'z-secondary:s1'): 288.0})

    def test_ring_full_360_coverage(self):
        # One revolution: continuous phase, all four quadrants,
        # start/end coincide, mid-cycle on multiple sides of the hub.
        # A 12-40 deg arc fails every assertion here.
        self._apply_at([_codex_entry('a'), _codex_entry('b'),
                        _secondary_codex_entry('z-secondary:c')],
                       _CENTER_PET_RECT)
        mode = self.manager._orbit_mode
        self.assertEqual(mode[0], 'ring')
        period = mode[3]
        keys = list(self.manager.window_identities())
        stamp = 1000.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        # Warm-up: newly shown orbs start at static homes; the first
        # live tick joins the ring. Measure from the ring itself, then
        # drive one full revolution at real 40 ms frames (one nominal
        # frame per tick: delayed callbacks never fast-forward).
        stamp += 0.04
        self._tick_at(stamp, _CENTER_PET_RECT)
        start = self._orb_positions()
        travel = {key: [self._hub_angle(key)] for key in keys}
        quadrants = set()
        frames = int(round(period / 0.04))
        coarse = {key: [self._hub_angle(key)] for key in keys}
        for step in range(1, frames + 1):
            stamp += 0.04
            self._tick_at(stamp, _CENTER_PET_RECT)
            for key in keys:
                angle = self._hub_angle(key)
                prev = travel[key][-1]
                delta = angle - prev
                delta += 360.0 * (delta < -180.0) - 360.0 * (delta > 180.0)
                # Common clockwise direction: no material backwards
                # step (0.5 deg tolerance covers integer quantization
                # at 40 ms sampling, ~0.3 deg per frame).
                self.assertGreaterEqual(delta, -0.5, (key, step))
                travel[key].append(prev + delta)
                x, y = self._orb_pos(key)
                quadrants.add((x + 56.0 >= _CENTER_HUB[0],
                               y + 48.0 >= _CENTER_HUB[1]))
            if step % 25 == 0:
                for key in keys:
                    angle = self._hub_angle(key)
                    cprev = coarse[key][-1]
                    cdelta = angle - cprev
                    cdelta += (360.0 * (cdelta < -180.0)
                               - 360.0 * (cdelta > 180.0))
                    self.assertGreater(cdelta, 0.0, (key, step))
                    coarse[key].append(cprev + cdelta)
        for key in keys:
            total = travel[key][-1] - travel[key][0]
            self.assertGreaterEqual(total, 355.0, key)
            self.assertLessEqual(total, 365.0, key)
        self.assertEqual(len(quadrants), 4)
        end = self._orb_positions()
        for key in keys:
            self.assertLessEqual(abs(end[key][0] - start[key][0])
                                 + abs(end[key][1] - start[key][1]), 2,
                                 key)

    def test_ring_shared_direction_and_spacing(self):
        # One orbital system: same rotational sense, rigid relative
        # spacing (120 deg / 72 deg), no per-star reversal or swap.
        for tasks, spacing in (
                ([_codex_entry('a'), _codex_entry('b'),
                  _secondary_codex_entry('z-secondary:c')], 120.0),
                ([_codex_entry('a'), _codex_entry('b'),
                  _secondary_codex_entry('z-secondary:c'),
                  _secondary_codex_entry('z-secondary:s0'),
                  _secondary_codex_entry('z-secondary:s1')], 72.0)):
            self._apply_at(tasks, _CENTER_PET_RECT)
            mode = self.manager._orbit_mode
            self.assertEqual(mode[0], 'ring')
            period = mode[3]
            keys = list(self.manager.window_identities())
            stamp = 3000.0
            self._tick_at(stamp, _CENTER_PET_RECT)
            stamp += period / 36.0
            self._tick_at(stamp, _CENTER_PET_RECT)
            # A membership change starts a recomposition glide;
            # spacing rigidity applies to the steady ring after it.
            for _ in range(400):
                if self.manager._ring_blend is None:
                    break
                stamp += period / 36.0
                self._tick_at(stamp, _CENTER_PET_RECT)
            self.assertIsNone(self.manager._ring_blend)
            series = {key: [self._hub_angle(key)] for key in keys}
            for _ in range(36):
                stamp += period / 36.0
                self._tick_at(stamp, _CENTER_PET_RECT)
                for key in keys:
                    series[key].append(self._hub_angle(key))
            first, second = keys[0], keys[1]
            gaps = [(series[second][i] - series[first][i]) % 360.0
                    for i in range(len(series[first]))]
            for gap in gaps:
                self.assertGreaterEqual(gap, spacing - 3.0)
                self.assertLessEqual(gap, spacing + 3.0)
            self.assertLessEqual(max(gaps) - min(gaps), 1.5)

    def test_ring_full_cycle_safety_across_layouts(self):
        # Dense full-cycle footprint validity: centered ring plus two
        # edge-constrained arc fallbacks (pinned — edges must not
        # claim a ring they cannot hold).
        cases = [
            (_CENTER_PET_RECT,
             [_codex_entry('a'), _codex_entry('b'),
              _secondary_codex_entry('z-secondary:c')],
             'ring'),
            (_EDGE_PET_RECT,
             [_codex_entry('a'), _codex_entry('b'),
              _secondary_codex_entry('z-secondary:c')],
             'arc'),
            (_LOWERRIGHT_PET_RECT,
             [_codex_entry('a'), _codex_entry('b'),
              _secondary_codex_entry('z-secondary:c')],
             'arc'),
        ]
        for pet_rect, tasks, kind in cases:
            self._apply_at(tasks, pet_rect)
            mode = self.manager._orbit_mode
            self.assertEqual(mode[0], kind, pet_rect)
            period = mode[2] if kind == 'arc' else mode[3]
            stamp = 5000.0
            self._tick_at(stamp, pet_rect)
            for _ in range(int(period)):
                stamp += 1.0
                self._tick_at(stamp, pet_rect)
                self.assertTrue(pet_geometry._windows_valid(
                    self._orb_positions(), pet_rect, _SCREEN_RECT),
                    (pet_rect, stamp))

    def test_ring_arc_fallback_constrained_corner(self):
        # Corner fixture: full-ring candidates rejected, arc fallback
        # selected, every frame valid through the arc period.
        self._apply([_codex_entry('a'), _codex_entry('b'),
                     _secondary_codex_entry('z-secondary:c')])
        mode = self.manager._orbit_mode
        self.assertEqual(mode, ('arc', 12.0, 14.0))
        self.assertEqual(self.manager._ring_offsets, {})
        stamp = 6000.0
        self._tick(stamp)
        for _ in range(int(mode[2])):
            stamp += 1.0
            self._tick(stamp)
            self.assertTrue(pet_geometry._windows_valid(
                self._orb_positions(), _PET_RECT, _SCREEN_RECT))

    def test_ring_speed_bounded(self):
        # Ring calm-speed bound from the selected mode itself:
        # circumference rate times diagonal Manhattan worst case plus
        # quantization slack. A runaway clock fails this.
        import math
        self._apply_at([_codex_entry('a'), _codex_entry('b'),
                        _secondary_codex_entry('z-secondary:c')],
                       _CENTER_PET_RECT)
        mode = self.manager._orbit_mode
        self.assertEqual(mode[0], 'ring')
        rate = 2.0 * math.pi * (mode[1] + mode[2]) / 2.0 / mode[3]
        cap = math.sqrt(2.0) * rate + 4.0
        stamp = 7000.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        stamp += 1.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        previous = self._orb_positions()
        for _ in range(10):
            stamp += 1.0
            self._tick_at(stamp, _CENTER_PET_RECT)
            current = self._orb_positions()
            for key in previous:
                dx = current[key][0] - previous[key][0]
                dy = current[key][1] - previous[key][1]
                self.assertLessEqual(abs(dx) + abs(dy), cap,
                                     (key, previous[key], current[key]))
            previous = current

    def test_ring_breathing_independent(self):
        # Orbit paused by hover, breathing advances, center unchanged.
        self._apply_at([_codex_entry('a'), _codex_entry('b')],
                       _CENTER_PET_RECT)
        self.assertEqual(self.manager._orbit_mode[0], 'ring')
        key = ('codex', 'a')
        stamp = 8000.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        self.manager.set_hovered(key)
        frozen = self._orb_pos(key)
        alphas = set()
        for _ in range(8):
            stamp += 0.25
            self._tick_at(stamp, _CENTER_PET_RECT)
            self.assertEqual(self._orb_pos(key), frozen)
            alphas.add(round(self.manager.window_for(key).halo_alpha, 3))
        self.assertGreater(len(alphas), 1)
        self.manager.set_hovered(None)

    def test_ring_trail_from_stationary_hub(self):
        # Stationary hub, full ring: motion accumulates trail history
        # and raises a visible overlay without any pet dragging.
        self._apply_at([_codex_entry('a'), _codex_entry('b'),
                        _secondary_codex_entry('z-secondary:c')],
                       _CENTER_PET_RECT)
        self.assertEqual(self.manager._orbit_mode[0], 'ring')
        key = ('codex', 'a')
        stamp = 9000.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        before = self._orb_pos(key)
        for _ in range(8):
            stamp += 0.2
            self._tick_at(stamp, _CENTER_PET_RECT)
        self.assertNotEqual(self._orb_pos(key), before)
        self.assertGreater(self.manager.trail_for(key), 0)
        self.assertTrue(self.manager.trail_overlay.has_trails())
        self.assertTrue(self.manager.trail_overlay.isVisible())

    def test_ring_hover_freeze_resume(self):
        # Whole-group pause: hovering one star freezes every ring
        # peer (never a collision, never a catch-up); leave resumes
        # from the same shared phase with a normal-frame step.
        self._apply_at([_codex_entry('a'), _codex_entry('b'),
                        _secondary_codex_entry('z-secondary:c')],
                       _CENTER_PET_RECT)
        self.assertEqual(self.manager._orbit_mode[0], 'ring')
        key = ('codex', 'a')
        stamp = 10000.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        stamp += 1.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        self.manager.set_hovered(key)
        frozen = self._orb_positions()
        for _ in range(5):
            stamp += 0.5
            self._tick_at(stamp, _CENTER_PET_RECT)
        self.assertEqual(self._orb_positions(), frozen)
        self.manager.set_hovered(None)
        stamp += 0.04
        self._tick_at(stamp, _CENTER_PET_RECT)
        resumed = self._orb_positions()
        for k in frozen:
            self.assertLessEqual(abs(resumed[k][0] - frozen[k][0])
                                 + abs(resumed[k][1] - frozen[k][1]), 8,
                                 k)

    # Blocker regressions: 40 ms production frame, ring rate
    # 2*pi*476/45 px/s -> ~2.7 px/frame; bound 8 admits diagonal +
    # quantization slack while any teleport fails by two orders.
    _RING_FRAME = 0.04
    _RING_FRAME_CAP = 8

    def _expected_ring_window(self, offset_deg, ring_t=0.0):
        import math
        mode = self.manager._orbit_mode
        theta = (mode[5] + mode[4]
                 * math.degrees(2.0 * math.pi / mode[3] * ring_t)
                 + offset_deg)
        center = pet_geometry.orbit_center_at(
            _CENTER_HUB[0], _CENTER_HUB[1], mode[1], mode[2], theta)
        return pet_geometry.star_center_to_window_position(
            center[0], center[1])

    def test_ring_first_frame_already_on_ring(self):
        # Blocker A: first visible frame must already be the selected
        # orbit position — no static-home flash, no 500 px first tick.
        for tasks, offsets in (
                ([_codex_entry('a')], {('codex', 'a'): 0.0}),
                ([_codex_entry('a'), _codex_entry('b'),
                  _secondary_codex_entry('z-secondary:c'),
                  _secondary_codex_entry('z-secondary:s0'),
                  _secondary_codex_entry('z-secondary:s1')],
                 {('codex', 'a'): 0.0, ('codex', 'b'): 72.0,
                  ('codex', 'z-secondary:c'): 144.0,
                  ('codex', 'z-secondary:s0'): 216.0,
                  ('codex', 'z-secondary:s1'): 288.0})):
            self._apply_at(tasks, _CENTER_PET_RECT)
            self.assertEqual(self.manager._orbit_mode[0], 'ring')
            first = self._orb_positions()
            ring_t = self.manager._ring_t
            for key, offset in offsets.items():
                orb = self.manager.window_for(key)
                self.assertTrue(orb.isVisible(), key)
                want = self._expected_ring_window(offset, ring_t)
                got = first[key]
                self.assertLessEqual(abs(got[0] - want[0])
                                     + abs(got[1] - want[1]), 2, key)
            stamp = 20000.0
            self._tick_at(stamp, _CENTER_PET_RECT)
            stamp += self._RING_FRAME
            self._tick_at(stamp, _CENTER_PET_RECT)
            second = self._orb_positions()
            for key in first:
                self.assertLessEqual(
                    abs(second[key][0] - first[key][0])
                    + abs(second[key][1] - first[key][1]),
                    self._RING_FRAME_CAP, key)
            self._apply([])

    def test_ring_unchanged_refresh_no_yank(self):
        # Blocker A guard for placement: an ordinary unchanged
        # refresh must not snap orbital stars back to D2A homes.
        tasks = [_codex_entry('a'), _codex_entry('b'),
                 _secondary_codex_entry('z-secondary:c')]
        self._apply_at(tasks, _CENTER_PET_RECT)
        stamp = 21000.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        stamp += 2.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        placed = self._orb_positions()
        self._apply_at(tasks, _CENTER_PET_RECT)
        self.assertEqual(self._orb_positions(), placed)
        stamp += self._RING_FRAME
        self._tick_at(stamp, _CENTER_PET_RECT)
        moved = self._orb_positions()
        for key in placed:
            self.assertLessEqual(
                abs(moved[key][0] - placed[key][0])
                + abs(moved[key][1] - placed[key][1]),
                self._RING_FRAME_CAP, key)

    def test_ring_hover_pauses_whole_group(self):
        # Blocker B: hovering A freezes every peer too, so no peer
        # can ever approach the hovered star and trip the guard.
        tasks = [_codex_entry('a'), _codex_entry('b'),
                 _secondary_codex_entry('z-secondary:c'),
                 _secondary_codex_entry('z-secondary:s0'),
                 _secondary_codex_entry('z-secondary:s1')]
        self._apply_at(tasks, _CENTER_PET_RECT)
        stamp = 22000.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        stamp += 2.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        key = ('codex', 'a')
        self.manager.set_hovered(key)
        frozen = self._orb_positions()
        alphas = set()
        for _ in range(25):
            stamp += 0.2
            self._tick_at(stamp, _CENTER_PET_RECT)
            self.assertEqual(self._orb_positions(), frozen)
            alphas.add(round(
                self.manager.window_for(key).halo_alpha, 3))
        self.assertGreater(len(alphas), 1)
        self.assertTrue(pet_geometry._windows_valid(
            frozen, _CENTER_PET_RECT, _SCREEN_RECT))
        self.manager.set_hovered(None)

    def test_ring_hover_resume_continuity(self):
        # Blocker B resume: after a long pause, one frame moves a
        # normal-frame distance with spacing intact — no 229 px jump.
        tasks = [_codex_entry('a'), _codex_entry('b'),
                 _secondary_codex_entry('z-secondary:c'),
                 _secondary_codex_entry('z-secondary:s0'),
                 _secondary_codex_entry('z-secondary:s1')]
        self._apply_at(tasks, _CENTER_PET_RECT)
        keys = list(self.manager.window_identities())
        stamp = 23000.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        stamp += 1.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        self.manager.set_hovered(keys[0])
        for _ in range(15):
            stamp += 0.2
            self._tick_at(stamp, _CENTER_PET_RECT)
        frozen = self._orb_positions()
        self.manager.set_hovered(None)
        stamp += self._RING_FRAME
        self._tick_at(stamp, _CENTER_PET_RECT)
        resumed = self._orb_positions()
        for key in keys:
            self.assertLessEqual(
                abs(resumed[key][0] - frozen[key][0])
                + abs(resumed[key][1] - frozen[key][1]),
                self._RING_FRAME_CAP, key)
        gaps = []
        for first, second in zip(keys, keys[1:] + keys[:1]):
            gap = (self._hub_angle(second) - self._hub_angle(first))
            gaps.append(gap % 360.0)
        for gap in gaps:
            self.assertGreaterEqual(gap, 72.0 - 3.0)
            self.assertLessEqual(gap, 72.0 + 3.0)

    def test_ring_safety_hold_freezes_phase(self):
        # General guard rule: rejected frame holds positions AND the
        # shared phase; the next valid frame is adjacent, not ahead.
        tasks = [_codex_entry('a'), _codex_entry('b'),
                 _secondary_codex_entry('z-secondary:c')]
        self._apply_at(tasks, _CENTER_PET_RECT)
        stamp = 24000.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        stamp += 1.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        phase = self.manager._ring_t
        # Corner hub cannot hold r476: every proposed frame invalid.
        stamp += 1.0
        self._tick_at(stamp, _EDGE_PET_RECT)
        held = self._orb_positions()
        stamp += 1.0
        self._tick_at(stamp, _EDGE_PET_RECT)
        stamp += 1.0
        self._tick_at(stamp, _EDGE_PET_RECT)
        self.assertEqual(self._orb_positions(), held)
        self.assertEqual(self.manager._ring_t, phase)
        stamp += 1.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        resumed = self._orb_positions()
        for key in held:
            self.assertLessEqual(
                abs(resumed[key][0] - held[key][0])
                + abs(resumed[key][1] - held[key][1]),
                98, key)

    def test_ring_retire_recomposition_continuity(self):
        # Blocker A recomposition: retiring B re-angles survivors to
        # new spacing over an adaptive glide — a 79 px snap frame
        # fails the 16 px cap; every frame stays valid.
        tasks = [_codex_entry('a'), _codex_entry('b'),
                 _secondary_codex_entry('z-secondary:c')]
        self._apply_at(tasks, _CENTER_PET_RECT)
        stamp = 25000.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        stamp += 3.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        before = self._orb_positions()
        survivors = [('codex', 'a'), ('codex', 'z-secondary:c')]
        windows = {k: self.manager.window_for(k) for k in survivors}
        self._apply_at([_codex_entry('a'),
                        _secondary_codex_entry('z-secondary:c')],
                       _CENTER_PET_RECT)
        for key in survivors:
            self.assertIs(self.manager.window_for(key), windows[key])
        # Blend starts exactly where survivors are: apply moves none.
        self.assertEqual({k: self._orb_pos(k) for k in survivors},
                         {k: before[k] for k in survivors})
        self.assertEqual(self.manager._ring_offsets,
                         {survivors[0]: 0.0, survivors[1]: 180.0})
        blend = self.manager._ring_blend
        self.assertIsNotNone(blend)
        self.assertGreaterEqual(blend['dur'], 0.4)
        self.assertLessEqual(blend['dur'], 10.0)
        peak = 0
        previous = {k: self._orb_pos(k) for k in survivors}
        for _ in range(400):
            stamp += 0.04
            self._tick_at(stamp, _CENTER_PET_RECT)
            current = {k: self._orb_pos(k) for k in survivors}
            for key in survivors:
                peak = max(peak, abs(current[key][0] - previous[key][0])
                           + abs(current[key][1] - previous[key][1]))
            self.assertTrue(pet_geometry._windows_valid(
                self._orb_positions(), _CENTER_PET_RECT,
                _SCREEN_RECT))
            previous = current
            if self.manager._ring_blend is None:
                break
        self.assertIsNone(self.manager._ring_blend)
        self.assertLessEqual(peak, 16)
        self.assertEqual(
            self.manager.trail_for(('codex', 'b')), 0)
        stamp += 1.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        after = {k: self._orb_pos(k) for k in survivors}
        self.assertTrue(any(after[k] != previous[k] for k in survivors))

    def test_ring_new_task_joins_without_home_flash(self):
        # Blocker A join: a new star's first visible frame is its
        # recomposed orbit slot, never the static home.
        import math
        self._apply_at([_codex_entry('a'), _codex_entry('b')],
                       _CENTER_PET_RECT)
        stamp = 26000.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        stamp += 1.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        before = self._orb_positions()
        self._apply_at([_codex_entry('a'), _codex_entry('b'),
                        _secondary_codex_entry('z-secondary:c')],
                       _CENTER_PET_RECT)
        key = ('codex', 'z-secondary:c')
        orb = self.manager.window_for(key)
        self.assertIsNotNone(orb)
        self.assertTrue(orb.isVisible())
        want = self._expected_ring_window(240.0, self.manager._ring_t)
        got = self._orb_pos(key)
        self.assertLessEqual(abs(got[0] - want[0])
                             + abs(got[1] - want[1]), 3, key)
        home = self.manager._auto_home(
            key, _CENTER_PET_RECT, _SCREEN_RECT)
        self.assertGreater(math.hypot(got[0] - home[0],
                                      got[1] - home[1]), 100, key)
        for old in before:
            self.assertEqual(self._orb_pos(old), before[old])
        # Survivors glide within the same per-frame cap; final
        # spacing is exact thirds; the transition completes.
        peak = 0
        previous = dict(before)
        for _ in range(400):
            stamp += 0.04
            self._tick_at(stamp, _CENTER_PET_RECT)
            current = self._orb_positions()
            for old in before:
                peak = max(peak, abs(current[old][0] - previous[old][0])
                           + abs(current[old][1] - previous[old][1]))
            self.assertTrue(pet_geometry._windows_valid(
                current, _CENTER_PET_RECT, _SCREEN_RECT))
            previous = current
            if self.manager._ring_blend is None:
                break
        self.assertIsNone(self.manager._ring_blend)
        self.assertLessEqual(peak, 16)
        self.assertEqual(self.manager._ring_offsets,
                         {('codex', 'a'): 0.0, ('codex', 'b'): 120.0,
                          key: 240.0})

    def test_ring_recomposition_stress_five_to_three(self):
        # Demanding case: 5 -> 3 recomposes fifths into thirds with
        # no newcomers blocking slots. Identities preserved, all
        # frames valid and capped, transition completes exactly.
        pair = [_codex_entry('a'), _codex_entry('b')]
        five = pair + [_secondary_codex_entry('z-secondary:c'),
                       _secondary_codex_entry('z-secondary:s0'),
                       _secondary_codex_entry('z-secondary:s1')]
        trio = pair + [_secondary_codex_entry('z-secondary:c')]
        self._apply_at(five, _CENTER_PET_RECT)
        stamp = 27000.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        stamp += 2.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        windows = {k: self.manager.window_for(k)
                   for k in self.manager.window_identities()}
        survivors = [('codex', 'a'), ('codex', 'b'),
                     ('codex', 'z-secondary:c')]
        self._apply_at(trio, _CENTER_PET_RECT)
        for key in survivors:
            self.assertIs(self.manager.window_for(key), windows[key])
        self.assertEqual(self.manager._ring_offsets,
                         {survivors[0]: 0.0, survivors[1]: 120.0,
                          survivors[2]: 240.0})
        peak = 0
        previous = self._orb_positions()
        for _ in range(400):
            stamp += 0.04
            self._tick_at(stamp, _CENTER_PET_RECT)
            current = self._orb_positions()
            for key in survivors:
                peak = max(peak, abs(current[key][0] - previous[key][0])
                           + abs(current[key][1] - previous[key][1]))
            self.assertTrue(pet_geometry._windows_valid(
                current, _CENTER_PET_RECT, _SCREEN_RECT))
            previous = current
            if self.manager._ring_blend is None:
                break
        self.assertIsNone(self.manager._ring_blend)
        self.assertLessEqual(peak, 16)

    def test_ring_bulk_add_recovers_without_freeze(self):
        # Bulk multi-add (2 -> 5 in one apply): the chosen rotation
        # routes survivors around static newcomer slots, so the glide
        # completes through only transient squeezes — never a freeze,
        # never a snap. The forced-abort path is covered separately.
        pair = [_codex_entry('a'), _codex_entry('b')]
        five = pair + [_secondary_codex_entry('z-secondary:c'),
                       _secondary_codex_entry('z-secondary:s0'),
                       _secondary_codex_entry('z-secondary:s1')]
        self._apply_at(pair, _CENTER_PET_RECT)
        stamp = 27500.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        stamp += 2.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        windows = {k: self.manager.window_for(k)
                   for k in self.manager.window_identities()}
        self._apply_at(five, _CENTER_PET_RECT)
        for key, orb in windows.items():
            self.assertIs(self.manager.window_for(key), orb)
        # A real stall abort must occur on this blocked path.
        self.assertIsNotNone(self.manager._ring_blend)
        peak = 0
        previous = self._orb_positions()
        for _ in range(300):
            stamp += 0.04
            self._tick_at(stamp, _CENTER_PET_RECT)
            current = self._orb_positions()
            for key in current:
                peak = max(peak, abs(current[key][0] - previous[key][0])
                           + abs(current[key][1] - previous[key][1]))
            self.assertTrue(pet_geometry._windows_valid(
                self._orb_positions(), _CENTER_PET_RECT,
                _SCREEN_RECT))
            previous = current
            if self.manager._ring_blend is None:
                break
        self.assertIsNone(self.manager._ring_blend)
        # Glide, abort, and recovery frames share one cap: abandoning
        # the blocked blend preserves visible geometry, so no single
        # frame — including the first post-abort frame — may snap.
        # Keep measuring past the clear: the recovery jump would land
        # here under the old bare-clear abort.
        for _ in range(25):
            stamp += 0.04
            self._tick_at(stamp, _CENTER_PET_RECT)
            current = self._orb_positions()
            for key in current:
                peak = max(peak, abs(current[key][0] - previous[key][0])
                           + abs(current[key][1] - previous[key][1]))
            self.assertTrue(pet_geometry._windows_valid(
                current, _CENTER_PET_RECT, _SCREEN_RECT))
            previous = current
        self.assertLessEqual(peak, 16)
        moving = self._orb_positions()
        stamp += 1.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        self.assertNotEqual(self._orb_positions(), moving)

    def test_ring_frame0_all_invalid_rejected_and_staged(self):
        # Deterministic all-invalid fixture: two placed survivors
        # standing 15 deg apart (post-rebase-like tight pattern, all
        # offsets zeroed) plus one newcomer. Every candidate rotation
        # — both anchors and the midpoint — parks the newcomer within
        # ~8 deg of a survivor (<=66 px at any realizable radius,
        # under the 78 px prefilter). The planner must reject every
        # candidate — no direct blend — and stage the newcomer hidden
        # instead of starting a doomed overlap blend.
        from widget import TaskOrbWindow
        self._apply_at([_codex_entry('a'), _codex_entry('b')],
                       _CENTER_PET_RECT)
        key_a = ('codex', 'a')
        key_b = ('codex', 'b')
        key_c = ('codex', 'z-secondary:z')
        mode = self.manager._orbit_mode
        self.assertEqual(mode[0], 'ring')
        hub = (_CENTER_PET_RECT[0] + _CENTER_PET_RECT[2] / 2.0,
               _CENTER_PET_RECT[1] + _CENTER_PET_RECT[3] / 2.0)
        for key, angle in ((key_a, 30.0), (key_b, 45.0)):
            center = pet_geometry.orbit_center_at(
                hub[0], hub[1], mode[1], mode[2], angle)
            pos = pet_geometry.star_center_to_window_position(
                center[0], center[1])
            orb = self.manager.window_for(key)
            orb.move(*pos)
            self.manager._placed[key] = pos
        orb_c = TaskOrbWindow(key_c, provider_id='codex',
                              manager=self.manager)
        self.manager._windows[key_c] = orb_c
        self.manager._ring_offsets = {key_a: 0.0, key_b: 0.0,
                                      key_c: 0.0}
        self.manager._maybe_start_blend(('static',), {},
                                        _CENTER_PET_RECT, _SCREEN_RECT)
        # The blocker is staged hidden: excluded from the blend plan
        # and from subsequent nominal geometry (getattr keeps the
        # fail-first read clean on pre-staging implementations).
        self.assertIn(key_c, getattr(self.manager, '_ring_staged',
                                     set()))
        nominal, _ = self.manager._nominal_positions(
            _CENTER_PET_RECT, _SCREEN_RECT)
        self.assertNotIn(key_c, nominal)
        self.assertIn(key_a, nominal)
        self.assertIn(key_b, nominal)
        # Survivors still glide alone toward final slots.
        self.assertIsNotNone(self.manager._ring_blend)
        self.assertEqual(set(self.manager._ring_blend['start']),
                         {key_a, key_b})
        self.assertNotIn(key_c, self.manager._placed)
        self.assertFalse(orb_c.isVisible())
        # Planner purity: selection offsets untouched by the search.
        self.assertEqual(self.manager._ring_offsets,
                         {key_a: 0.0, key_b: 0.0, key_c: 0.0})

    def test_ring_stall_abort_recovers_via_staging(self):
        # 2 -> 8 bulk on the real state machine: the direct blend
        # starts, stalls mid-glide on parked newcomers, and the abort
        # stages the 6 blockers hidden instead of dead-holding.
        # Survivors glide alone to final slots, staged stars reveal at
        # validated final slots, circulation resumes. No snap, no
        # freeze, no identity loss.
        pair = [_codex_entry('a'), _codex_entry('b')]
        eight = pair + [_secondary_codex_entry('z-secondary:c'),
                        _secondary_codex_entry('z-secondary:s0'),
                        _secondary_codex_entry('z-secondary:s1'),
                        _secondary_codex_entry('z-secondary:s2'),
                        _secondary_codex_entry('z-secondary:s3'),
                        _secondary_codex_entry('z-secondary:s4')]
        keys = [('codex', 'a'), ('codex', 'b'),
                ('codex', 'z-secondary:c'),
                ('codex', 'z-secondary:s0'),
                ('codex', 'z-secondary:s1'),
                ('codex', 'z-secondary:s2'),
                ('codex', 'z-secondary:s3'),
                ('codex', 'z-secondary:s4')]
        pair_keys = [('codex', 'a'), ('codex', 'b')]
        newcomers = [k for k in keys if k not in pair_keys]
        eighths = {key: 45.0 * rank for rank, key in enumerate(keys)}
        self._apply_at(pair, _CENTER_PET_RECT)
        stamp = 34000.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        stamp += 2.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        windows = {k: self.manager.window_for(k)
                   for k in self.manager.window_identities()}
        self._apply_at(eight, _CENTER_PET_RECT)
        for key, orb in windows.items():
            self.assertIs(self.manager.window_for(key), orb)
        # Direct blend first (valid frame-0 exists); staging comes
        # from the abort, not the apply.
        self.assertIsNotNone(self.manager._ring_blend)
        self.assertEqual(set(self.manager._ring_staged), set())
        self.assertEqual(self.manager._ring_offsets, eighths)
        # Drive the real state machine to full recovery, recording a
        # full trace. Holds may be intermittent (valid squeeze frames
        # reset the stall counter), so onset and clock-freeze are
        # established post-hoc from the trace — never predicted.
        trace = []
        previous = {k: v for k, v in self._orb_positions().items()}
        prev_staged = set()
        peak = 0
        staged_ever = set()
        revealed_first = {}
        recovered_at = None
        for n in range(400):
            stamp += 0.04
            self._tick_at(stamp, _CENTER_PET_RECT)
            current = self._orb_positions()
            staged = set(self.manager._ring_staged)
            staged_ever |= staged
            visible = {k: v for k, v in current.items()
                       if k not in staged}
            prev_visible = {k: v for k, v in previous.items()
                            if k not in prev_staged}
            self.assertTrue(pet_geometry._windows_valid(
                visible, _CENTER_PET_RECT, _SCREEN_RECT))
            for key in visible:
                if key in prev_visible:
                    peak = max(
                        peak, abs(current[key][0] - prev_visible[key][0])
                        + abs(current[key][1] - prev_visible[key][1]))
            # First-visible-frame check for newly revealed staged
            # stars: final valid ring slot, never a home flash. The
            # hidden-to-shown step itself is not motion, so it stays
            # out of the displacement peak.
            for key in prev_staged - staged:
                orb = self.manager.window_for(key)
                self.assertTrue(orb.isVisible(), key)
                want = self._expected_ring_window(
                    eighths[key], self.manager._ring_t)
                got = current[key]
                self.assertLessEqual(abs(got[0] - want[0])
                                     + abs(got[1] - want[1]), 3, key)
                revealed_first[key] = got
            blend = self.manager._ring_blend
            trace.append((dict(visible), self.manager._ring_t,
                          blend['t'] if blend is not None else None))
            previous = current
            prev_staged = set(staged)
            if blend is None and not staged:
                recovered_at = n + 1
                break
        # The abort path fired (blockers were staged), then the full
        # set converged: well under 10 s of simulated time.
        self.assertEqual(set(staged_ever), set(newcomers))
        self.assertIsNone(self.manager._ring_blend)
        self.assertEqual(set(self.manager._ring_staged), set())
        self.assertIsNotNone(recovered_at)
        self.assertLess(recovered_at, 250)
        self.assertLessEqual(peak, 16)
        # Selection offsets untouched throughout (no invalid commit).
        self.assertEqual(self.manager._ring_offsets, eighths)
        # Every staged star revealed exactly once, at its final slot.
        self.assertEqual(set(revealed_first), set(newcomers))
        for key, orb in windows.items():
            self.assertIs(self.manager.window_for(key), orb)
        for key in keys:
            self.assertTrue(self.manager.window_for(key).isVisible(),
                            key)
        self.assertTrue(pet_geometry._windows_valid(
            self._orb_positions(), _CENTER_PET_RECT, _SCREEN_RECT))
        # Circulation resumes automatically: positions and shared
        # phase advance under ordinary ring motion.
        moving = self._orb_positions()
        phase = self.manager._ring_t
        for _ in range(25):
            stamp += 0.04
            self._tick_at(stamp, _CENTER_PET_RECT)
        self.assertNotEqual(self._orb_positions(), moving)
        self.assertGreater(self.manager._ring_t, phase)
        # Post-hoc hold proof: three straight ticks with frozen
        # positions, frozen ring phase, and frozen blend clock while
        # blending — the pre-abort stall really held time still.
        held = False
        for first, second, third in zip(trace, trace[1:], trace[2:]):
            (p0, r0, b0), (p1, r1, b1), (p2, r2, b2) = (
                first, second, third)
            if (b0 is not None and b1 is not None and b2 is not None
                    and p0 == p1 == p2 and r0 == r1 == r2
                    and b0 == b1 == b2):
                held = True
                break
        self.assertTrue(held)

    def test_ring_same_snapshot_preserves_recovery(self):
        # Reapplying the identical task set mid-recovery must not
        # restart the plan from frame zero: positions, staged set,
        # and the active blend continue untouched, with no snap.
        pair = [_codex_entry('a'), _codex_entry('b')]
        eight = pair + [_secondary_codex_entry('z-secondary:c'),
                        _secondary_codex_entry('z-secondary:s0'),
                        _secondary_codex_entry('z-secondary:s1'),
                        _secondary_codex_entry('z-secondary:s2'),
                        _secondary_codex_entry('z-secondary:s3'),
                        _secondary_codex_entry('z-secondary:s4')]
        self._apply_at(pair, _CENTER_PET_RECT)
        stamp = 35000.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        stamp += 2.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        self._apply_at(eight, _CENTER_PET_RECT)
        for _ in range(400):
            stamp += 0.04
            self._tick_at(stamp, _CENTER_PET_RECT)
            if self.manager._ring_staged:
                break
        self.assertTrue(self.manager._ring_staged)
        before_pos = self._orb_positions()
        before_staged = set(self.manager._ring_staged)
        before_blend = self.manager._ring_blend
        self.assertIsNotNone(before_blend)
        before_t = before_blend['t']
        self._apply_at(eight, _CENTER_PET_RECT)
        self.assertEqual(self._orb_positions(), before_pos)
        self.assertEqual(set(self.manager._ring_staged), before_staged)
        self.assertIs(self.manager._ring_blend, before_blend)
        self.assertEqual(self.manager._ring_blend['t'], before_t)
        # Recovery still completes afterwards.
        for _ in range(2000):
            stamp += 0.04
            self._tick_at(stamp, _CENTER_PET_RECT)
            if (self.manager._ring_blend is None
                    and not self.manager._ring_staged):
                break
        self.assertIsNone(self.manager._ring_blend)
        self.assertEqual(set(self.manager._ring_staged), set())

    def test_ring_retire_staged_task_recovers_rest(self):
        # Retiring a still-hidden staged task mid-recovery cleans its
        # bookkeeping and the remaining set still converges: bounded
        # frames, valid geometry, uniform final spacing, identities
        # of the rest preserved.
        import math
        pair = [_codex_entry('a'), _codex_entry('b')]
        eight = pair + [_secondary_codex_entry('z-secondary:c'),
                        _secondary_codex_entry('z-secondary:s0'),
                        _secondary_codex_entry('z-secondary:s1'),
                        _secondary_codex_entry('z-secondary:s2'),
                        _secondary_codex_entry('z-secondary:s3'),
                        _secondary_codex_entry('z-secondary:s4')]
        seven = [t for t in eight
                 if not (t.get('provider_id') == 'codex'
                         and t.get('task_key') == 'z-secondary:s4')]
        dropped = ('codex', 'z-secondary:s4')
        self._apply_at(pair, _CENTER_PET_RECT)
        stamp = 36000.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        stamp += 2.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        survivors = {k: self.manager.window_for(k)
                     for k in self.manager.window_identities()}
        self._apply_at(eight, _CENTER_PET_RECT)
        for _ in range(400):
            stamp += 0.04
            self._tick_at(stamp, _CENTER_PET_RECT)
            if self.manager._ring_staged:
                break
        self.assertIn(dropped, self.manager._ring_staged)
        before = self._orb_positions()
        self._apply_at(seven, _CENTER_PET_RECT)
        self.assertIsNone(self.manager.window_for(dropped))
        self.assertNotIn(dropped, self.manager._ring_staged)
        self.assertIsNone(self.manager.slot_for(dropped))
        for key in before:
            if key != dropped:
                self.assertEqual(self._orb_pos(key), before[key])
        for key, orb in survivors.items():
            self.assertIs(self.manager.window_for(key), orb)
        peak = 0
        previous = self._orb_positions()
        prev_staged = set(self.manager._ring_staged)
        for _ in range(2000):
            stamp += 0.04
            self._tick_at(stamp, _CENTER_PET_RECT)
            current = self._orb_positions()
            staged = set(self.manager._ring_staged)
            visible = {k: v for k, v in current.items()
                       if k not in staged}
            self.assertTrue(pet_geometry._windows_valid(
                visible, _CENTER_PET_RECT, _SCREEN_RECT))
            prev_visible = {k: v for k, v in previous.items()
                            if k not in prev_staged}
            for key in visible:
                if key in prev_visible:
                    peak = max(
                        peak, abs(current[key][0] - prev_visible[key][0])
                        + abs(current[key][1] - prev_visible[key][1]))
            # Newly revealed staged stars appear directly at valid
            # ring slots (hidden-to-shown is an appearance, not
            # motion): full set valid, never a home flash.
            for key in prev_staged - staged:
                orb = self.manager.window_for(key)
                self.assertTrue(orb.isVisible(), key)
                home = self.manager._auto_home(
                    key, _CENTER_PET_RECT, _SCREEN_RECT)
                got = current[key]
                self.assertGreater(math.hypot(got[0] - home[0],
                                              got[1] - home[1]), 100,
                                   key)
            previous = current
            prev_staged = set(staged)
            if (self.manager._ring_blend is None
                    and not self.manager._ring_staged):
                break
        self.assertIsNone(self.manager._ring_blend)
        self.assertEqual(set(self.manager._ring_staged), set())
        self.assertLessEqual(peak, 16)
        remaining = [('codex', 'a'), ('codex', 'b'),
                     ('codex', 'z-secondary:c'),
                     ('codex', 'z-secondary:s0'),
                     ('codex', 'z-secondary:s1'),
                     ('codex', 'z-secondary:s2'),
                     ('codex', 'z-secondary:s3')]
        for ident in remaining:
            self.assertTrue(
                self.manager.window_for(ident).isVisible(), ident)
        self.assertTrue(pet_geometry._windows_valid(
            self._orb_positions(), _CENTER_PET_RECT, _SCREEN_RECT))
        values = sorted(self.manager._ring_offsets.values())
        self.assertEqual(len(values), 7)
        for first, second in zip(values, values[1:]):
            self.assertAlmostEqual(second - first, 360.0 / 7.0)

    def _drive_ring_frames(self, stamp, pet_rect, count):
        """Advance count 40 ms ticks; assert the visible set stays
        valid every frame; return (stamp, peak visible displacement).
        Hidden-to-shown appearances are not motion and stay out."""
        peak = 0
        previous = {k: v for k, v in self._orb_positions().items()
                    if k not in self.manager._ring_staged}
        prev_staged = set(self.manager._ring_staged)
        for _ in range(count):
            stamp += 0.04
            self._tick_at(stamp, pet_rect)
            current = self._orb_positions()
            staged = set(self.manager._ring_staged)
            visible = {k: v for k, v in current.items()
                       if k not in staged}
            self.assertTrue(pet_geometry._windows_valid(
                visible, pet_rect, _SCREEN_RECT))
            prev_visible = {k: v for k, v in previous.items()
                            if k not in prev_staged}
            for key in visible:
                if key in prev_visible:
                    peak = max(
                        peak, abs(current[key][0] - prev_visible[key][0])
                        + abs(current[key][1] - prev_visible[key][1]))
            previous = current
            prev_staged = set(staged)
        return stamp, peak

    def _run_eight_to_staged(self, stamp):
        """Drive canonical 2->8 bulk until newcomers stage; return
        (stamp, eight_tasks). Asserts staging really engaged."""
        pair = [_codex_entry('a'), _codex_entry('b')]
        eight = pair + [_secondary_codex_entry('z-secondary:c'),
                        _secondary_codex_entry('z-secondary:s0'),
                        _secondary_codex_entry('z-secondary:s1'),
                        _secondary_codex_entry('z-secondary:s2'),
                        _secondary_codex_entry('z-secondary:s3'),
                        _secondary_codex_entry('z-secondary:s4')]
        self._apply_at(pair, _CENTER_PET_RECT)
        self._tick_at(stamp, _CENTER_PET_RECT)
        stamp += 2.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        self._apply_at(eight, _CENTER_PET_RECT)
        for _ in range(400):
            stamp += 0.04
            self._tick_at(stamp, _CENTER_PET_RECT)
            if self.manager._ring_staged:
                return stamp, eight
        self.fail('staged recovery never engaged')

    def test_ring_staged_survive_hide_show(self):
        # Blocker 1: set_visible(True) must not expose staged
        # newcomers; recovery continues and reveals atomically.
        stamp = 37000.0
        stamp, eight = self._run_eight_to_staged(stamp)
        staged = set(self.manager._ring_staged)
        self.assertEqual(len(staged), 6)
        for key in staged:
            self.assertFalse(
                self.manager.window_for(key).isVisible(), key)
        stamp += 0.2
        self._tick_at(stamp, _CENTER_PET_RECT)
        for cycle in range(2):
            self.manager.set_visible(False)
            for key in self.manager.window_identities():
                self.assertFalse(
                    self.manager.window_for(key).isVisible(), key)
            self.manager.set_visible(True)
            self.assertEqual(set(self.manager._ring_staged), staged)
            for key in staged:
                self.assertFalse(
                    self.manager.window_for(key).isVisible(), key)
            for key in self.manager.window_identities():
                if key not in staged:
                    self.assertTrue(
                        self.manager.window_for(key).isVisible(), key)
            visible = {k: v for k, v in self._orb_positions().items()
                       if k not in staged}
            self.assertTrue(pet_geometry._windows_valid(
                visible, _CENTER_PET_RECT, _SCREEN_RECT))
            self.assertEqual(self.manager._hover_holds, set())
            self.assertEqual(self.manager._press_holds, set())
            self.assertIsNone(self.manager._hovered)
        # Recovery completes after the toggles: full ring circulates.
        for _ in range(2000):
            stamp += 0.04
            self._tick_at(stamp, _CENTER_PET_RECT)
            if (self.manager._ring_blend is None
                    and not self.manager._ring_staged):
                break
        self.assertIsNone(self.manager._ring_blend)
        self.assertEqual(set(self.manager._ring_staged), set())
        for key in self.manager.window_identities():
            self.assertTrue(
                self.manager.window_for(key).isVisible(), key)
        moving = self._orb_positions()
        phase = self.manager._ring_t
        stamp, peak = self._drive_ring_frames(stamp, _CENTER_PET_RECT,
                                              25)
        self.assertLessEqual(peak, 16)
        self.assertNotEqual(self._orb_positions(), moving)
        self.assertGreater(self.manager._ring_t, phase)

    def test_ring_motion_toggle_continuity_during_recovery(self):
        # Blocker 2: OFF->ON during staged 2->8 recovery must glide
        # from exact visible pixels — never jump ~1024 px to the ring
        # — and ON->OFF must glide home instead of snapping.
        windows = {}
        stamp = 38000.0
        stamp, eight = self._run_eight_to_staged(stamp)
        for k in self.manager.window_identities():
            windows[k] = self.manager.window_for(k)
        self.panel.prefs['pet_motion'] = False
        try:
            staged_before = set(self.manager._ring_staged)
            visible_before = {
                k: v for k, v in self._orb_positions().items()
                if k not in staged_before}
            self._apply_at(eight, _CENTER_PET_RECT)
            # Frame zero for every previously visible star: the apply
            # itself moves nothing visible. Staged newcomers stay
            # staged (hidden, inert): revealing them now at static
            # homes while survivors still sit mid-ring would bypass
            # complete-frame validation, so the OFF transition keeps
            # them hidden until the parking glide lands a valid full
            # home set.
            after = self._orb_positions()
            for key, pos in visible_before.items():
                self.assertEqual(after[key], pos, key)
            self.assertEqual(set(self.manager._ring_staged),
                             staged_before)
            for key in staged_before:
                orb = self.manager.window_for(key)
                self.assertFalse(orb.isVisible(), key)
            self.assertIsNone(self.manager._ring_blend)
            visible_now = {k: v for k, v in after.items()
                           if k not in staged_before}
            self.assertTrue(pet_geometry._windows_valid(
                visible_now, _CENTER_PET_RECT, _SCREEN_RECT))
            # Parking glides home boundedly: per-40ms-frame budget,
            # valid every frame (hidden staged orbs are not motion and
            # stay out of the frame), landing exactly on static homes.
            # The staged remainder is revealed only through the
            # validated complete-frame path at landing.
            previous = dict(visible_now)
            for _ in range(4000):
                stamp += 0.04
                self._tick_at(stamp, _CENTER_PET_RECT)
                staged = set(self.manager._ring_staged)
                current = {k: v for k, v in
                           self._orb_positions().items()
                           if k not in staged}
                self.assertTrue(pet_geometry._windows_valid(
                    current, _CENTER_PET_RECT, _SCREEN_RECT))
                for key in current:
                    if key in previous:
                        self.assertLessEqual(
                            abs(current[key][0] - previous[key][0])
                            + abs(current[key][1] - previous[key][1]),
                            16, key)
                for key in staged:
                    self.assertFalse(
                        self.manager.window_for(key).isVisible(), key)
                previous = current
                if self.manager._park_blend is None:
                    break
            self.assertIsNone(self.manager._park_blend)
            landed = {k: v for k, v in
                      self._orb_positions().items()
                      if k not in self.manager._ring_staged}
            for key in landed:
                self.assertEqual(
                    landed[key],
                    self.manager._auto_home(
                        key, _CENTER_PET_RECT, _SCREEN_RECT), key)
            self.assertFalse(
                self.manager.trail_overlay.isVisible())
            self.panel.prefs['pet_motion'] = True
            before = self._orb_positions()
            self._apply_at(eight, _CENTER_PET_RECT)
            # Frame zero again: re-enable moves nothing by itself —
            # survivors glide while crowded blockers wait staged.
            self.assertEqual(self._orb_positions(), before)
            for key, orb in windows.items():
                self.assertIs(self.manager.window_for(key), orb)
            # The full set converges boundedly: per-40ms-frame budget,
            # valid every frame, staged stars revealed atomically at
            # validated slots (appearance, not motion).
            previous = dict(before)
            prev_staged = set(self.manager._ring_staged)
            recovered_at = None
            for n in range(1200):
                stamp += 0.04
                self._tick_at(stamp, _CENTER_PET_RECT)
                current = self._orb_positions()
                staged = set(self.manager._ring_staged)
                visible = {k: v for k, v in current.items()
                           if k not in staged}
                self.assertTrue(pet_geometry._windows_valid(
                    visible, _CENTER_PET_RECT, _SCREEN_RECT))
                prev_visible = {k: v for k, v in previous.items()
                                if k not in prev_staged}
                for key in visible:
                    if key in prev_visible:
                        self.assertLessEqual(
                            abs(current[key][0] - prev_visible[key][0])
                            + abs(current[key][1] - prev_visible[key][1]),
                            16, (n, key))
                for key in prev_staged - staged:
                    self.assertTrue(
                        self.manager.window_for(key).isVisible(), key)
                previous = current
                prev_staged = set(staged)
                if (self.manager._ring_blend is None
                        and not self.manager._ring_staged):
                    recovered_at = n
                    break
            self.assertIsNotNone(recovered_at)
            for key, orb in windows.items():
                self.assertIs(self.manager.window_for(key), orb)
                self.assertTrue(
                    self.manager.window_for(key).isVisible(), key)
            moving = self._orb_positions()
            phase = self.manager._ring_t
            stamp, peak = self._drive_ring_frames(
                stamp, _CENTER_PET_RECT, 25)
            self.assertLessEqual(peak, 16)
            self.assertNotEqual(self._orb_positions(), moving)
            self.assertGreater(self.manager._ring_t, phase)
        finally:
            self.panel.prefs['pet_motion'] = True

    def test_delayed_ring_tick_does_not_fast_forward(self):
        # Reviewer P1: a delayed timer callback (5 s gap) must advance
        # at most one nominal 40 ms frame — never apply hidden elapsed
        # time as one large visible step — and must not create a giant
        # first trail segment.
        import math
        tasks = [_codex_entry('a'), _codex_entry('b'),
                 _secondary_codex_entry('z-secondary:c')]
        self._apply_at(tasks, _CENTER_PET_RECT)
        self.assertEqual(self.manager._orbit_mode[0], 'ring')
        stamp = 1000.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        for _ in range(25):
            stamp += 0.04
            self._tick_at(stamp, _CENTER_PET_RECT)
        before = self._orb_positions()
        ring_before = self.manager._ring_t
        # Single delayed callback after a 5 s stall.
        stamp += 5.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        after = self._orb_positions()
        for key in before:
            step = (abs(after[key][0] - before[key][0])
                    + abs(after[key][1] - before[key][1]))
            self.assertLessEqual(step, 16, key)
        self.assertLessEqual(
            self.manager._ring_t - ring_before, 0.04 + 1e-9)
        self.assertTrue(pet_geometry._windows_valid(
            after, _CENTER_PET_RECT, _SCREEN_RECT))
        trails = self.manager.trail_overlay._trails
        for key, samples in trails.items():
            points = [(x, y) for x, y, _ in samples]
            for first, second in zip(points, points[1:]):
                self.assertLessEqual(
                    math.hypot(second[0] - first[0],
                               second[1] - first[1]), 16.0, key)

    def test_delayed_parking_tick_stays_bounded(self):
        # Reviewer P1: a 250 ms gap during an ON->OFF parking glide
        # advances a single nominal frame, not six frames at once.
        tasks = [_codex_entry('a'), _codex_entry('b'),
                 _secondary_codex_entry('z-secondary:c')]
        self._apply_at(tasks, _CENTER_PET_RECT)
        stamp = 2000.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        for _ in range(25):
            stamp += 0.04
            self._tick_at(stamp, _CENTER_PET_RECT)
        self.panel.prefs['pet_motion'] = False
        try:
            self._apply_at(tasks, _CENTER_PET_RECT)
            self.assertIsNotNone(self.manager._park_blend)
            self._tick_at(stamp, _CENTER_PET_RECT)
            stamp += 0.04
            self._tick_at(stamp, _CENTER_PET_RECT)
            before = {k: v for k, v in
                      self._orb_positions().items()
                      if k not in self.manager._ring_staged}
            stamp += 0.25
            self._tick_at(stamp, _CENTER_PET_RECT)
            after = {k: v for k, v in
                     self._orb_positions().items()
                     if k not in self.manager._ring_staged}
            for key in before:
                step = (abs(after[key][0] - before[key][0])
                        + abs(after[key][1] - before[key][1]))
                self.assertLessEqual(step, 16, key)
            self.assertTrue(pet_geometry._windows_valid(
                after, _CENTER_PET_RECT, _SCREEN_RECT))
        finally:
            self.panel.prefs['pet_motion'] = True

    def test_blend_duration_preserves_frame_budget(self):
        # Reviewer P1: uncapped durations keep the eased peak frame
        # step at the nominal target for ANY travel — including long
        # large-work-area hauls a 10 s cap would have sprinted.
        peak = pet_geometry.RING_BLEND_EASE_PEAK
        frame = pet_geometry.RING_BLEND_FRAME_S
        target = pet_geometry.RING_BLEND_TARGET_PX_PER_FRAME
        previous = 0.0
        for travel in (0.0, 1.0, 50.0, 500.0, 1500.0, 3000.0,
                       6000.0):
            duration = pet_geometry.ring_blend_duration_s(travel)
            self.assertGreaterEqual(
                duration, pet_geometry.RING_BLEND_MIN_S)
            self.assertGreaterEqual(duration, previous)
            previous = duration
            if travel > 0.0:
                self.assertLessEqual(
                    travel * peak * frame / duration, target)

    def test_large_work_area_toggle_keeps_frame_budget(self):
        # Reviewer P1: on a large work area the long ON->OFF parking
        # legs that duration caps used to sprint must instead glide
        # longer with every 40 ms frame inside the 16 px budget.
        screen = (0, 0, 3839, 2159)
        pet_rect = (1784, 915, 272, 330)
        tasks = [_codex_entry('a'), _codex_entry('b'),
                 _secondary_codex_entry('z-secondary:c'),
                 _secondary_codex_entry('z-secondary:s0'),
                 _secondary_codex_entry('z-secondary:s1')]
        self.manager.apply_snapshot(
            tasks, pet_rect=pet_rect, screen_rect=screen)
        stamp = 3000.0
        self.manager.tick_visual(stamp, pet_rect=pet_rect,
                                 screen_rect=screen)
        for _ in range(25):
            stamp += 0.04
            self.manager.tick_visual(stamp, pet_rect=pet_rect,
                                     screen_rect=screen)
        self.panel.prefs['pet_motion'] = False
        try:
            before = {k: (self.manager.window_for(k).x(),
                          self.manager.window_for(k).y())
                      for k in self.manager.window_identities()}
            self.manager.apply_snapshot(
                tasks, pet_rect=pet_rect, screen_rect=screen)
            after = {k: (self.manager.window_for(k).x(),
                         self.manager.window_for(k).y())
                     for k in self.manager.window_identities()}
            for key, pos in before.items():
                if key not in self.manager._ring_staged:
                    self.assertEqual(after[key], pos, key)
            previous = {k: v for k, v in after.items()
                        if k not in self.manager._ring_staged}
            for _ in range(4000):
                stamp += 0.04
                self.manager.tick_visual(stamp, pet_rect=pet_rect,
                                         screen_rect=screen)
                staged = set(self.manager._ring_staged)
                current = {
                    k: (self.manager.window_for(k).x(),
                        self.manager.window_for(k).y())
                    for k in self.manager.window_identities()
                    if k not in staged}
                self.assertTrue(pet_geometry._windows_valid(
                    current, pet_rect, screen))
                for key in current:
                    if key in previous:
                        self.assertLessEqual(
                            abs(current[key][0] - previous[key][0])
                            + abs(current[key][1] - previous[key][1]),
                            16, key)
                previous = current
                if self.manager._park_blend is None:
                    break
            self.assertIsNone(self.manager._park_blend)
        finally:
            self.panel.prefs['pet_motion'] = True

    def test_ring_motion_toggle_full_ring(self):
        # OFF->ON across 1/3/5-star full rings: bounded, valid,
        # circulating, identities stable.
        cases = ([_codex_entry('a')],
                 [_codex_entry('a'), _codex_entry('b'),
                  _secondary_codex_entry('z-secondary:c')],
                 [_codex_entry('a'), _codex_entry('b'),
                  _secondary_codex_entry('z-secondary:c'),
                  _secondary_codex_entry('z-secondary:s0'),
                  _secondary_codex_entry('z-secondary:s1')])
        stamp = 39000.0
        self.panel.prefs['pet_motion'] = False
        try:
            for tasks in cases:
                self._apply_at(tasks, _CENTER_PET_RECT)
                windows = {k: self.manager.window_for(k)
                           for k in self.manager.window_identities()}
                self.assertIsNone(self.manager._ring_blend)
                parked = self._orb_positions()
                self.assertTrue(pet_geometry._windows_valid(
                    parked, _CENTER_PET_RECT, _SCREEN_RECT))
                self.panel.prefs['pet_motion'] = True
                try:
                    self._apply_at(tasks, _CENTER_PET_RECT)
                    stamp, peak = self._drive_ring_frames(
                        stamp, _CENTER_PET_RECT, 120)
                    self.assertLessEqual(peak, 16)
                    for key, orb in windows.items():
                        self.assertIs(
                            self.manager.window_for(key), orb)
                    moving = self._orb_positions()
                    stamp, peak = self._drive_ring_frames(
                        stamp, _CENTER_PET_RECT, 25)
                    self.assertLessEqual(peak, 16)
                    self.assertNotEqual(self._orb_positions(), moving)
                finally:
                    self.panel.prefs['pet_motion'] = False
                self._apply_at([], _CENTER_PET_RECT)
        finally:
            self.panel.prefs['pet_motion'] = True

    def test_ring_hide_while_hover_paused(self):
        # Hover-pause plus manager hide: holds clear on hide, show
        # fabricates none, motion resumes afterwards.
        tasks = [_codex_entry('a'), _codex_entry('b'),
                 _secondary_codex_entry('z-secondary:c')]
        self._apply_at(tasks, _CENTER_PET_RECT)
        stamp = 40000.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        stamp += 1.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        key = ('codex', 'a')
        self.manager.set_hovered(key)
        frozen = self._orb_positions()
        stamp += 0.5
        self._tick_at(stamp, _CENTER_PET_RECT)
        self.assertEqual(self._orb_positions(), frozen)
        self.manager.set_visible(False)
        self.assertEqual(self.manager._hover_holds, set())
        self.assertEqual(self.manager._press_holds, set())
        self.assertIsNone(self.manager._hovered)
        self.manager.set_visible(True)
        self.assertEqual(self.manager._hover_holds, set())
        self.assertEqual(self.manager._press_holds, set())
        self.assertIsNone(self.manager._hovered)
        moving = self._orb_positions()
        stamp, peak = self._drive_ring_frames(
            stamp, _CENTER_PET_RECT, 25)
        self.assertLessEqual(peak, 16)
        self.assertNotEqual(self._orb_positions(), moving)

    def test_ring_repeated_motion_toggles(self):
        # ON->OFF->ON->OFF->ON: no phase error, no stale staged or
        # blend state, no trail streak, labels/slots stable.
        tasks = [_codex_entry('a'), _codex_entry('b'),
                 _secondary_codex_entry('z-secondary:c')]
        self._apply_at(tasks, _CENTER_PET_RECT)
        stamp = 41000.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        stamp += 1.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        labels = {k: self.manager.window_for(k).number_label.text()
                  for k in self.manager.window_identities()}
        slots = {k: self.manager.slot_for(k)
                 for k in self.manager.window_identities()}
        windows = {k: self.manager.window_for(k)
                   for k in self.manager.window_identities()}
        self.panel.prefs['pet_motion'] = False
        try:
            for _ in range(3):
                self._apply_at(tasks, _CENTER_PET_RECT)
                self.assertIsNone(self.manager._ring_blend)
                self.assertEqual(set(self.manager._ring_staged),
                                 set())
                parked = self._orb_positions()
                self.assertTrue(pet_geometry._windows_valid(
                    parked, _CENTER_PET_RECT, _SCREEN_RECT))
                self.panel.prefs['pet_motion'] = True
                try:
                    self._apply_at(tasks, _CENTER_PET_RECT)
                    stamp, peak = self._drive_ring_frames(
                        stamp, _CENTER_PET_RECT, 60)
                    self.assertLessEqual(peak, 16)
                finally:
                    self.panel.prefs['pet_motion'] = False
            self.panel.prefs['pet_motion'] = True
            self._apply_at(tasks, _CENTER_PET_RECT)
            stamp, peak = self._drive_ring_frames(
                stamp, _CENTER_PET_RECT, 60)
            self.assertLessEqual(peak, 16)
            self.assertIsNone(self.manager._ring_blend)
            self.assertEqual(set(self.manager._ring_staged), set())
            for key, orb in windows.items():
                self.assertIs(self.manager.window_for(key), orb)
            for k, number in labels.items():
                self.assertEqual(
                    self.manager.window_for(k).number_label.text(),
                    number)
            for k, slot in slots.items():
                self.assertEqual(self.manager.slot_for(k), slot)
            moving = self._orb_positions()
            phase = self.manager._ring_t
            stamp, peak = self._drive_ring_frames(
                stamp, _CENTER_PET_RECT, 25)
            self.assertLessEqual(peak, 16)
            self.assertNotEqual(self._orb_positions(), moving)
            self.assertGreater(self.manager._ring_t, phase)
        finally:
            self.panel.prefs['pet_motion'] = True

    def test_ring_motion_toggle_at_edge(self):
        # OFF->ON under an edge (arc-mode) layout: arc clocks restart
        # at homes instead of resuming mid-swing with a jump.
        tasks = [_codex_entry('a'), _codex_entry('b')]
        self._apply_at(tasks, _PET_RECT)
        self.assertEqual(self.manager._orbit_mode[0], 'arc')
        stamp = 42000.0
        self._tick_at(stamp, _PET_RECT)
        stamp += 3.0
        self._tick_at(stamp, _PET_RECT)
        self.panel.prefs['pet_motion'] = False
        try:
            self._apply_at(tasks, _PET_RECT)
            parked = self._orb_positions()
            self.assertTrue(pet_geometry._windows_valid(
                parked, _PET_RECT, _SCREEN_RECT))
            self.panel.prefs['pet_motion'] = True
            self._apply_at(tasks, _PET_RECT)
            stamp, peak = self._drive_ring_frames(
                stamp, _PET_RECT, 100)
            self.assertLessEqual(peak, 16)
            moving = self._orb_positions()
            stamp, peak = self._drive_ring_frames(
                stamp, _PET_RECT, 25)
            self.assertLessEqual(peak, 16)
            self.assertNotEqual(self._orb_positions(), moving)
        finally:
            self.panel.prefs['pet_motion'] = True

    def test_ring_park_resume_without_apply(self):
        # Audit: timer-only OFF->ON resume with no apply in between.
        # Disabling motion starts a parking glide from exact pixels
        # via ticks alone; re-enabling plans a ring blend from the
        # parked homes via ticks alone. No boundary ever teleports.
        tasks = [_codex_entry('a'), _codex_entry('b'),
                 _secondary_codex_entry('z-secondary:c')]
        self._apply_at(tasks, _CENTER_PET_RECT)
        stamp = 43000.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        stamp += 2.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        windows = {k: self.manager.window_for(k)
                   for k in self.manager.window_identities()}
        self.panel.prefs['pet_motion'] = False
        try:
            cruising = self._orb_positions()
            stamp += 0.04
            self._tick_at(stamp, _CENTER_PET_RECT)
            # Initiation tick moves nothing: frame zero preserved.
            self.assertEqual(self._orb_positions(), cruising)
            self.assertIsNotNone(self.manager._park_blend)
            self.assertIsNone(self.manager._ring_blend)
            self.assertEqual(set(self.manager._ring_staged), set())
            # Parking completes boundedly at static homes.
            previous = dict(cruising)
            for _ in range(2000):
                stamp += 0.04
                self._tick_at(stamp, _CENTER_PET_RECT)
                current = self._orb_positions()
                self.assertTrue(pet_geometry._windows_valid(
                    current, _CENTER_PET_RECT, _SCREEN_RECT))
                for key in current:
                    self.assertLessEqual(
                        abs(current[key][0] - previous[key][0])
                        + abs(current[key][1] - previous[key][1]), 16,
                        key)
                previous = current
                if self.manager._park_blend is None:
                    break
            self.assertIsNone(self.manager._park_blend)
            for key in self.manager.window_identities():
                self.assertEqual(
                    current[key],
                    self.manager._auto_home(
                        key, _CENTER_PET_RECT, _SCREEN_RECT), key)
            for key in current:
                orb = self.manager.window_for(key)
                self.assertEqual(
                    (orb.halo_alpha, orb.halo_radius,
                     orb.core_intensity, orb.facet_intensity),
                    (1.0, 1.0, 1.0, 1.0))
            self.assertFalse(
                self.manager.trail_overlay.isVisible())
            self.panel.prefs['pet_motion'] = True
            stamp += 0.04
            self._tick_at(stamp, _CENTER_PET_RECT)
            self.assertIsNotNone(self.manager._ring_blend)
            stamp, peak = self._drive_ring_frames(
                stamp, _CENTER_PET_RECT, 120)
            self.assertLessEqual(peak, 16)
            for key, orb in windows.items():
                self.assertIs(self.manager.window_for(key), orb)
        finally:
            self.panel.prefs['pet_motion'] = True

    def test_off_state_refresh_keeps_parking_glide(self):
        # Reviewer P1: repeated OFF-state syncs (1 Hz status timer) and
        # unchanged OFF snapshots must not restart an active parking
        # glide. Each restart resets t=0/_last_tick and stalls landing;
        # idempotent refreshes let the glide complete within budget.
        tasks = [_codex_entry('a'), _codex_entry('b'),
                 _secondary_codex_entry('z-secondary:c')]
        self._apply_at(tasks, _CENTER_PET_RECT)
        stamp = 50000.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        for _ in range(25):
            stamp += 0.04
            self._tick_at(stamp, _CENTER_PET_RECT)
        self.panel.prefs['pet_motion'] = False
        try:
            self._apply_at(tasks, _CENTER_PET_RECT)
            self.assertIsNotNone(self.manager._park_blend)
            # Advance so t > 0, then a same-state apply must keep the
            # identical glide object (no restart, no t reset). The
            # initiation tick carries dt=0 (frame zero); the next tick
            # advances the easing clock.
            stamp += 0.04
            self._tick_at(stamp, _CENTER_PET_RECT)
            stamp += 0.04
            self._tick_at(stamp, _CENTER_PET_RECT)
            blend = self.manager._park_blend
            self.assertIsNotNone(blend)
            t_before = blend['t']
            self.assertGreater(t_before, 0.0)
            self._apply_at(tasks, _CENTER_PET_RECT)
            self.assertIs(self.manager._park_blend, blend)
            self.assertEqual(blend['t'], t_before)
            # Direct re-entry (the primitive both sync_motion and
            # apply_snapshot share) must also be a no-op mid-glide.
            self.manager._begin_park_glide(
                _CENTER_PET_RECT, _SCREEN_RECT)
            self.assertIs(self.manager._park_blend, blend)
            self.assertEqual(blend['t'], t_before)
            # Live-style sync_motion during parking must not restart
            # either (patched live gate; real timer stopped after).
            from unittest.mock import patch as _patch
            try:
                with _patch.object(self.manager, '_live_armed',
                                   return_value=True):
                    self.manager.sync_motion()
                self.assertIs(self.manager._park_blend, blend)
                self.assertEqual(blend['t'], t_before)
            finally:
                try:
                    self.manager.motion_timer.stop()
                except Exception:
                    pass
            # Drive to completion with a periodic same-state refresh
            # (live 1 Hz status tick + poll snapshot): bounded steps,
            # valid geometry, lands home, glide clears.
            previous = self._orb_positions()
            for i in range(4000):
                stamp += 0.04
                self._tick_at(stamp, _CENTER_PET_RECT)
                if i % 25 == 0:
                    self._apply_at(tasks, _CENTER_PET_RECT)
                    self.manager._begin_park_glide(
                        _CENTER_PET_RECT, _SCREEN_RECT)
                current = self._orb_positions()
                self.assertTrue(pet_geometry._windows_valid(
                    current, _CENTER_PET_RECT, _SCREEN_RECT))
                for key in current:
                    if key in previous:
                        self.assertLessEqual(
                            abs(current[key][0] - previous[key][0])
                            + abs(current[key][1] - previous[key][1]),
                            16, key)
                previous = current
                if self.manager._park_blend is None:
                    break
            self.assertIsNone(self.manager._park_blend)
            for key in self.manager.window_identities():
                self.assertEqual(
                    current[key],
                    self.manager._auto_home(
                        key, _CENTER_PET_RECT, _SCREEN_RECT), key)
        finally:
            self.panel.prefs['pet_motion'] = True

    def test_ring_toggle_immediate_boundary_off_to_on(self):
        # Immediate-boundary OFF->ON for 1/3/5 stars: the baseline is
        # captured BEFORE the state-changing call (capturing it after
        # would hide an apply-time teleport). The apply itself must
        # move nothing (0 px); subsequent 40 ms frames stay bounded
        # and valid until the ring circulates again.
        cases = ([_codex_entry('a')],
                 [_codex_entry('a'), _codex_entry('b'),
                  _secondary_codex_entry('z-secondary:c')],
                 [_codex_entry('a'), _codex_entry('b'),
                  _secondary_codex_entry('z-secondary:c'),
                  _secondary_codex_entry('z-secondary:s0'),
                  _secondary_codex_entry('z-secondary:s1')])
        stamp = 44000.0
        self.panel.prefs['pet_motion'] = False
        try:
            for tasks in cases:
                self._apply_at(tasks, _CENTER_PET_RECT)
                self._tick_at(stamp, _CENTER_PET_RECT)
                windows = {k: self.manager.window_for(k)
                           for k in self.manager.window_identities()}
                parked = self._orb_positions()
                self.assertTrue(pet_geometry._windows_valid(
                    parked, _CENTER_PET_RECT, _SCREEN_RECT))
                self.panel.prefs['pet_motion'] = True
                try:
                    before = self._orb_positions()
                    self._apply_at(tasks, _CENTER_PET_RECT)
                    after = self._orb_positions()
                    # Preferred immediate displacement: 0 px.
                    for key in before:
                        self.assertEqual(after[key], before[key], key)
                    previous = dict(after)
                    for _ in range(400):
                        stamp += 0.04
                        self._tick_at(stamp, _CENTER_PET_RECT)
                        current = self._orb_positions()
                        self.assertTrue(
                            pet_geometry._windows_valid(
                                current, _CENTER_PET_RECT,
                                _SCREEN_RECT))
                        for key in current:
                            self.assertLessEqual(
                                abs(current[key][0] - previous[key][0])
                                + abs(current[key][1] - previous[key][1]),
                                16, key)
                        previous = current
                        if self.manager._ring_blend is None:
                            break
                    self.assertIsNone(self.manager._ring_blend)
                    for key, orb in windows.items():
                        self.assertIs(
                            self.manager.window_for(key), orb)
                    moving = self._orb_positions()
                    phase = self.manager._ring_t
                    stamp, peak = self._drive_ring_frames(
                        stamp, _CENTER_PET_RECT, 25)
                    self.assertLessEqual(peak, 16)
                    self.assertNotEqual(self._orb_positions(), moving)
                    self.assertGreater(self.manager._ring_t, phase)
                finally:
                    self.panel.prefs['pet_motion'] = False
                self._apply_at([], _CENTER_PET_RECT)
        finally:
            self.panel.prefs['pet_motion'] = True

    def test_ring_toggle_immediate_boundary_on_to_off(self):
        # Immediate-boundary ON->OFF for 1/3/5 stars: no instant park
        # at static homes. The apply freezes frame zero; ticks glide
        # home boundedly; the parked state is stable and clickable
        # (identities/labels/slots intact, no trail artifact).
        cases = ([_codex_entry('a')],
                 [_codex_entry('a'), _codex_entry('b'),
                  _secondary_codex_entry('z-secondary:c')],
                 [_codex_entry('a'), _codex_entry('b'),
                  _secondary_codex_entry('z-secondary:c'),
                  _secondary_codex_entry('z-secondary:s0'),
                  _secondary_codex_entry('z-secondary:s1')])
        stamp = 45000.0
        for tasks in cases:
            self._apply_at(tasks, _CENTER_PET_RECT)
            stamp += 0.04
            self._tick_at(stamp, _CENTER_PET_RECT)
            stamp += 2.0
            self._tick_at(stamp, _CENTER_PET_RECT)
            windows = {k: self.manager.window_for(k)
                       for k in self.manager.window_identities()}
            labels = {k: self.manager.label_number_for(k)
                      for k in self.manager.window_identities()}
            slots = {k: self.manager.slot_for(k)
                     for k in self.manager.window_identities()}
            self.panel.prefs['pet_motion'] = False
            try:
                before = self._orb_positions()
                self._apply_at(tasks, _CENTER_PET_RECT)
                after = self._orb_positions()
                for key in before:
                    self.assertEqual(after[key], before[key], key)
                previous = dict(after)
                for _ in range(2000):
                    stamp += 0.04
                    self._tick_at(stamp, _CENTER_PET_RECT)
                    current = self._orb_positions()
                    self.assertTrue(pet_geometry._windows_valid(
                        current, _CENTER_PET_RECT, _SCREEN_RECT))
                    for key in current:
                        self.assertLessEqual(
                            abs(current[key][0] - previous[key][0])
                            + abs(current[key][1] - previous[key][1]),
                            16, key)
                    previous = current
                    if self.manager._park_blend is None:
                        break
                self.assertIsNone(self.manager._park_blend)
                for key in self.manager.window_identities():
                    self.assertEqual(
                        current[key],
                        self.manager._auto_home(
                            key, _CENTER_PET_RECT, _SCREEN_RECT), key)
                for key, orb in windows.items():
                    self.assertIs(self.manager.window_for(key), orb)
                    # Clickable parked state: activation still routes.
                    self.manager.orb_activated(key)
                    self.assertEqual(
                        self.manager.last_activated, key)
                for key, number in labels.items():
                    self.assertEqual(
                        self.manager.label_number_for(key), number)
                for key, slot in slots.items():
                    self.assertEqual(self.manager.slot_for(key), slot)
                self.assertFalse(
                    self.manager.trail_overlay.isVisible())
                # Parked ticks stay frozen with a fresh clock.
                stamp += 5.0
                self._tick_at(stamp, _CENTER_PET_RECT)
                self.assertEqual(self._orb_positions(), current)
            finally:
                self.panel.prefs['pet_motion'] = True
            self._apply_at([], _CENTER_PET_RECT)

    def test_ring_toggle_mid_blend_to_off(self):
        # Active blend -> OFF: toggling off mid-glide abandons the
        # ring blend from exact current pixels and parks home
        # boundedly; toggling back on resumes circulation.
        tasks = [_codex_entry('a'), _codex_entry('b'),
                 _secondary_codex_entry('z-secondary:c')]
        self.panel.prefs['pet_motion'] = False
        try:
            self._apply_at(tasks, _CENTER_PET_RECT)
            stamp = 46000.0
            self._tick_at(stamp, _CENTER_PET_RECT)
            self.panel.prefs['pet_motion'] = True
            self._apply_at(tasks, _CENTER_PET_RECT)
            self.assertIsNotNone(self.manager._ring_blend)
            stamp += 0.04
            self._tick_at(stamp, _CENTER_PET_RECT)
            stamp += 0.04
            self._tick_at(stamp, _CENTER_PET_RECT)
            mid = self._orb_positions()
            self.panel.prefs['pet_motion'] = False
            self._apply_at(tasks, _CENTER_PET_RECT)
            self.assertIsNone(self.manager._ring_blend)
            self.assertEqual(self._orb_positions(), mid)
            previous = dict(mid)
            for _ in range(2000):
                stamp += 0.04
                self._tick_at(stamp, _CENTER_PET_RECT)
                current = self._orb_positions()
                self.assertTrue(pet_geometry._windows_valid(
                    current, _CENTER_PET_RECT, _SCREEN_RECT))
                for key in current:
                    self.assertLessEqual(
                        abs(current[key][0] - previous[key][0])
                        + abs(current[key][1] - previous[key][1]), 16,
                        key)
                previous = current
                if self.manager._park_blend is None:
                    break
            self.assertIsNone(self.manager._park_blend)
            self.panel.prefs['pet_motion'] = True
            self._apply_at(tasks, _CENTER_PET_RECT)
            stamp, peak = self._drive_ring_frames(
                stamp, _CENTER_PET_RECT, 150)
            self.assertLessEqual(peak, 16)
            moving = self._orb_positions()
            stamp, peak = self._drive_ring_frames(
                stamp, _CENTER_PET_RECT, 25)
            self.assertLessEqual(peak, 16)
            self.assertNotEqual(self._orb_positions(), moving)
        finally:
            self.panel.prefs['pet_motion'] = True

    def test_ring_toggle_crowded_midblend_to_off(self):
        # Crowded ON->OFF mid-recovery: toggling off one tick after a
        # bulk 2->8 add must freeze the exact visible frame (no
        # instant park at static homes, however crowded), then glide
        # home boundedly across successive rounds without hiding
        # survivors or leaking staged stars.
        tasks = [_codex_entry('a'), _codex_entry('b'),
                 _secondary_codex_entry('z-secondary:c')]
        bulk = (tasks + [_secondary_codex_entry('z-secondary:s0'),
                         _secondary_codex_entry('z-secondary:s1'),
                         _codex_entry('d'), _codex_entry('e'),
                         _secondary_codex_entry('z-secondary:s2')])
        self._apply_at(tasks, _CENTER_PET_RECT)
        stamp = 46500.0
        for _ in range(30):
            stamp += 0.04
            self._tick_at(stamp, _CENTER_PET_RECT)
        self._apply_at(bulk, _CENTER_PET_RECT)
        stamp += 0.04
        self._tick_at(stamp, _CENTER_PET_RECT)
        visible_before = {
            k: v for k, v in self._orb_positions().items()
            if k not in self.manager._ring_staged}
        self.panel.prefs['pet_motion'] = False
        try:
            self._apply_at(bulk, _CENTER_PET_RECT)
            after = self._orb_positions()
            for key, pos in visible_before.items():
                self.assertEqual(after[key], pos, key)
            previous = dict(after)
            for _ in range(4000):
                stamp += 0.04
                self._tick_at(stamp, _CENTER_PET_RECT)
                current = self._orb_positions()
                visible = {
                    k: v for k, v in current.items()
                    if k not in self.manager._ring_staged}
                self.assertTrue(pet_geometry._windows_valid(
                    visible, _CENTER_PET_RECT, _SCREEN_RECT))
                for key in current:
                    if key in previous:
                        self.assertLessEqual(
                            abs(current[key][0] - previous[key][0])
                            + abs(current[key][1] - previous[key][1]),
                            16, key)
                previous = current
                if self.manager._park_blend is None:
                    break
            self.assertIsNone(self.manager._park_blend)
            for key in self.manager.window_identities():
                self.assertEqual(
                    current[key],
                    self.manager._auto_home(
                        key, _CENTER_PET_RECT, _SCREEN_RECT), key)
        finally:
            self.panel.prefs['pet_motion'] = True
        self._apply_at([], _CENTER_PET_RECT)

    def test_ring_toggle_off_to_on_with_pet_move(self):
        # Toggle ON landing on a moved hub: the apply moves nothing
        # (frame zero is exact current pixels even though the hub
        # changed), then the transition settles boundedly onto valid
        # geometry with identities intact.
        tasks = [_codex_entry('a'), _codex_entry('b'),
                 _secondary_codex_entry('z-secondary:c')]
        moved = (840, 380, 272, 330)
        self.panel.prefs['pet_motion'] = False
        try:
            self._apply_at(tasks, _CENTER_PET_RECT)
            stamp = 46600.0
            self._tick_at(stamp, _CENTER_PET_RECT)
            windows = {k: self.manager.window_for(k)
                       for k in self.manager.window_identities()}
            before = self._orb_positions()
            self.panel.prefs['pet_motion'] = True
            self._apply_at(tasks, moved)
            after = self._orb_positions()
            for key in before:
                self.assertEqual(after[key], before[key], key)
            previous = dict(after)
            for _ in range(1200):
                stamp += 0.04
                self._tick_at(stamp, moved)
                current = self._orb_positions()
                for key in current:
                    self.assertLessEqual(
                        abs(current[key][0] - previous[key][0])
                        + abs(current[key][1] - previous[key][1]),
                        16, key)
                previous = current
                if (self.manager._ring_blend is None
                        and self.manager._park_blend is None):
                    break
            self.assertIsNone(self.manager._ring_blend)
            self.assertIsNone(self.manager._park_blend)
            visible = {
                k: v for k, v in current.items()
                if k not in self.manager._ring_staged}
            self.assertTrue(pet_geometry._windows_valid(
                visible, moved, _SCREEN_RECT))
            for key, orb in windows.items():
                self.assertIs(self.manager.window_for(key), orb)
        finally:
            self.panel.prefs['pet_motion'] = True
        self._apply_at([], _CENTER_PET_RECT)

    def test_ring_toggle_hover_around_toggle(self):
        # Hover/press around toggles: a hover pause survives the OFF
        # transition bookkeeping (holds are visibility-local), parking
        # still completes, and release plus re-enable resumes.
        tasks = [_codex_entry('a'), _codex_entry('b'),
                 _secondary_codex_entry('z-secondary:c')]
        self._apply_at(tasks, _CENTER_PET_RECT)
        stamp = 47000.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        stamp += 1.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        key = ('codex', 'a')
        other = ('codex', 'b')
        self.manager.add_hover_hold(key)
        self.manager.add_press_hold(other)
        frozen = self._orb_positions()
        stamp += 0.5
        self._tick_at(stamp, _CENTER_PET_RECT)
        self.assertEqual(self._orb_positions(), frozen)
        self.panel.prefs['pet_motion'] = False
        try:
            before = self._orb_positions()
            self._apply_at(tasks, _CENTER_PET_RECT)
            self.assertEqual(self._orb_positions(), before)
            previous = dict(before)
            for _ in range(2000):
                stamp += 0.04
                self._tick_at(stamp, _CENTER_PET_RECT)
                current = self._orb_positions()
                self.assertTrue(pet_geometry._windows_valid(
                    current, _CENTER_PET_RECT, _SCREEN_RECT))
                for ident in current:
                    self.assertLessEqual(
                        abs(current[ident][0] - previous[ident][0])
                        + abs(current[ident][1] - previous[ident][1]),
                        16, ident)
                previous = current
                if self.manager._park_blend is None:
                    break
            self.assertIsNone(self.manager._park_blend)
        finally:
            self.panel.prefs['pet_motion'] = True
        self.manager.release_hover_hold(key)
        self.manager.release_press_hold(other)
        self.assertEqual(self.manager._press_holds, set())
        self._apply_at(tasks, _CENTER_PET_RECT)
        stamp, peak = self._drive_ring_frames(
            stamp, _CENTER_PET_RECT, 120)
        self.assertLessEqual(peak, 16)
        moving = self._orb_positions()
        stamp, peak = self._drive_ring_frames(
            stamp, _CENTER_PET_RECT, 25)
        self.assertLessEqual(peak, 16)
        self.assertNotEqual(self._orb_positions(), moving)

    def test_ring_toggle_stale_holds_resume_without_release(self):
        # Motion transitions clear stale hover/press holds: an old
        # interaction with no release event must never freeze the
        # resumed ring. Unlike the hover-around test above, nothing
        # releases the holds before re-enabling.
        tasks = [_codex_entry('a'), _codex_entry('b'),
                  _secondary_codex_entry('z-secondary:c')]
        self._apply_at(tasks, _CENTER_PET_RECT)
        stamp = 47100.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        stamp += 2.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        key = ('codex', 'a')
        other = ('codex', 'b')
        self.manager.add_hover_hold(key)
        self.manager.add_press_hold(other)
        self.assertTrue(self.manager._ring_paused())
        self.panel.prefs['pet_motion'] = False
        try:
            before = self._orb_positions()
            self._apply_at(tasks, _CENTER_PET_RECT)
            # Apply-driven OFF transition drops the stale holds.
            self.assertEqual(self.manager._hover_holds, set())
            self.assertEqual(self.manager._press_holds, set())
            self.assertIsNone(self.manager._hovered)
            self.assertFalse(self.manager._ring_paused())
            self.assertEqual(self._orb_positions(), before)
            for _ in range(2000):
                stamp += 0.04
                self._tick_at(stamp, _CENTER_PET_RECT)
                if self.manager._park_blend is None:
                    break
            self.assertIsNone(self.manager._park_blend)
        finally:
            self.panel.prefs['pet_motion'] = True
        # Re-enable WITHOUT releasing anything: the ring must
        # circulate again instead of staying hover-frozen.
        self._apply_at(tasks, _CENTER_PET_RECT)
        self.assertEqual(self.manager._hover_holds, set())
        self.assertEqual(self.manager._press_holds, set())
        self.assertIsNone(self.manager._hovered)
        self.assertFalse(self.manager._ring_paused())
        moving = self._orb_positions()
        stamp, peak = self._drive_ring_frames(
            stamp, _CENTER_PET_RECT, 120)
        self.assertLessEqual(peak, 16)
        stamp, peak = self._drive_ring_frames(
            stamp, _CENTER_PET_RECT, 25)
        self.assertLessEqual(peak, 16)
        self.assertNotEqual(self._orb_positions(), moving)
        self._apply_at([], _CENTER_PET_RECT)

    def test_ring_toggle_stale_holds_timer_only_resume(self):
        # Timer-driven OFF->ON (prefs flipped with no intervening
        # apply): stale holds die on the transition and ticks plan
        # continuity from exact pixels instead of freezing.
        tasks = [_codex_entry('a'), _codex_entry('b'),
                  _secondary_codex_entry('z-secondary:c')]
        self._apply_at(tasks, _CENTER_PET_RECT)
        stamp = 47150.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        stamp += 2.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        key = ('codex', 'a')
        self.manager.add_hover_hold(key)
        self.manager.add_press_hold(('codex', 'b'))
        self.assertTrue(self.manager._ring_paused())
        self.panel.prefs['pet_motion'] = False
        try:
            before = self._orb_positions()
            stamp += 0.04
            self._tick_at(stamp, _CENTER_PET_RECT)
            # Timer-only OFF starts the park and drops stale holds.
            self.assertEqual(self.manager._hover_holds, set())
            self.assertEqual(self.manager._press_holds, set())
            self.assertIsNone(self.manager._hovered)
            after = self._orb_positions()
            for key in before:
                self.assertLessEqual(
                    abs(after[key][0] - before[key][0])
                    + abs(after[key][1] - before[key][1]),
                    16, key)
            for _ in range(2000):
                stamp += 0.04
                self._tick_at(stamp, _CENTER_PET_RECT)
                if self.manager._park_blend is None:
                    break
            self.assertIsNone(self.manager._park_blend)
        finally:
            self.panel.prefs['pet_motion'] = True
        # Timer-only ON: no apply, just ticks — must resume motion.
        stamp += 0.04
        self._tick_at(stamp, _CENTER_PET_RECT)
        self.assertFalse(self.manager._ring_paused())
        moving = self._orb_positions()
        stamp, peak = self._drive_ring_frames(
            stamp, _CENTER_PET_RECT, 120)
        self.assertLessEqual(peak, 16)
        stamp, peak = self._drive_ring_frames(
            stamp, _CENTER_PET_RECT, 25)
        self.assertLessEqual(peak, 16)
        self.assertNotEqual(self._orb_positions(), moving)
        self._apply_at([], _CENTER_PET_RECT)

    def test_ring_to_arc_staged_reveal_retry(self):
        # Ring-to-arc with a blocked home reveal: survivors stay at
        # their exact pixels (frame zero), staged newcomers stay
        # hidden AND inert (out of arc motion and validation), arc
        # ticks retry the reveal, and the set completes on valid
        # geometry with bounded per-frame movement.
        stamp = 47200.0
        stamp, eight = self._run_eight_to_staged(stamp)
        staged = set(self.manager._ring_staged)
        self.assertEqual(len(staged), 6)
        dest = (600, 60, 272, 330)
        survivors_before = {
            k: v for k, v in self._orb_positions().items()
            if k not in staged}
        self.assertEqual(len(survivors_before), 2)
        self._apply_at(eight, dest)
        self.assertEqual(self.manager._orbit_mode[0], 'arc')
        current = self._orb_positions()
        for key, pos in survivors_before.items():
            self.assertEqual(current[key], pos, key)
        self.assertEqual(set(self.manager._ring_staged), staged)
        for key in staged:
            self.assertFalse(
                self.manager.window_for(key).isVisible(), key)
        nominal, _centers = self.manager._nominal_positions(
            dest, _SCREEN_RECT)
        for key in staged:
            self.assertNotIn(key, nominal, key)
        for _ in range(75):
            stamp, peak = self._drive_ring_frames(stamp, dest, 40)
            self.assertLessEqual(peak, 16)
            if (not self.manager._ring_staged
                    and self.manager._park_blend is None
                    and self.manager._ring_blend is None):
                break
        self.assertEqual(set(self.manager._ring_staged), set())
        self.assertIsNone(self.manager._park_blend)
        for key in self.manager.window_identities():
            self.assertTrue(
                self.manager.window_for(key).isVisible(), key)
        moving = self._orb_positions()
        stamp, peak = self._drive_ring_frames(stamp, dest, 200)
        self.assertLessEqual(peak, 16)
        self.assertNotEqual(self._orb_positions(), moving)
        self._apply_at([], _CENTER_PET_RECT)

    def test_ring_toggle_hide_show_around_toggle(self):
        # Hide/show around a toggle: hiding preserves pixels, the OFF
        # apply moves nothing while hidden, showing resumes the park
        # glide, and re-enable circulates.
        tasks = [_codex_entry('a'), _codex_entry('b'),
                 _secondary_codex_entry('z-secondary:c')]
        self._apply_at(tasks, _CENTER_PET_RECT)
        stamp = 48000.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        stamp += 1.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        self.manager.set_visible(False)
        for key in self.manager.window_identities():
            self.assertFalse(
                self.manager.window_for(key).isVisible(), key)
        self.panel.prefs['pet_motion'] = False
        try:
            before = self._orb_positions()
            self._apply_at(tasks, _CENTER_PET_RECT)
            self.assertEqual(self._orb_positions(), before)
            self.manager.set_visible(True)
            for key in self.manager.window_identities():
                self.assertTrue(
                    self.manager.window_for(key).isVisible(), key)
            previous = dict(before)
            for _ in range(2000):
                stamp += 0.04
                self._tick_at(stamp, _CENTER_PET_RECT)
                current = self._orb_positions()
                self.assertTrue(pet_geometry._windows_valid(
                    current, _CENTER_PET_RECT, _SCREEN_RECT))
                for ident in current:
                    self.assertLessEqual(
                        abs(current[ident][0] - previous[ident][0])
                        + abs(current[ident][1] - previous[ident][1]),
                        16, ident)
                previous = current
                if self.manager._park_blend is None:
                    break
            self.assertIsNone(self.manager._park_blend)
            for key in self.manager.window_identities():
                self.assertEqual(
                    current[key],
                    self.manager._auto_home(
                        key, _CENTER_PET_RECT, _SCREEN_RECT), key)
        finally:
            self.panel.prefs['pet_motion'] = True
        self._apply_at(tasks, _CENTER_PET_RECT)
        stamp, peak = self._drive_ring_frames(
            stamp, _CENTER_PET_RECT, 120)
        self.assertLessEqual(peak, 16)

    def test_ring_unchanged_snapshot_starts_no_blend(self):
        # Poll refreshes must not run recomposition machinery: same
        # snapshot -> no blend state, no movement, same mode.
        tasks = [_codex_entry('a'), _codex_entry('b'),
                 _secondary_codex_entry('z-secondary:c')]
        self._apply_at(tasks, _CENTER_PET_RECT)
        stamp = 28000.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        stamp += 1.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        mode = self.manager._orbit_mode
        placed = self._orb_positions()
        self._apply_at(tasks, _CENTER_PET_RECT)
        self._apply_at(tasks, _CENTER_PET_RECT)
        self.assertIsNone(self.manager._ring_blend)
        self.assertEqual(self.manager._orbit_mode, mode)
        self.assertEqual(self._orb_positions(), placed)

    def test_ring_hide_hovered_task_resumes(self):
        # Blocker B: hovering x pauses the ring; retiring x
        # must drop its hold so B/C resume; readding x adds no hold.
        tasks = [_codex_entry('b'), _codex_entry('c'),
                 _secondary_codex_entry('z-secondary:x')]
        self._apply_at(tasks, _CENTER_PET_RECT)
        labels = {k: self.manager.window_for(k).number_label.text()
                  for k in self.manager.window_identities()}
        stamp = 29000.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        stamp += 1.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        key = ('codex', 'z-secondary:x')
        self.manager.set_hovered(key)
        frozen = self._orb_positions()
        stamp += 0.5
        self._tick_at(stamp, _CENTER_PET_RECT)
        self.assertEqual(self._orb_positions(), frozen)
        self._apply_at(tasks[:2], _CENTER_PET_RECT, preference='codex')
        self.assertNotIn(key, self.manager._hover_holds)
        self.assertNotIn(key, self.manager.window_identities())
        self.assertEqual(self.manager.trail_for(key), 0)
        stamp += 1.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        self.assertNotEqual(self._orb_positions(), frozen)
        self._apply_at(tasks, _CENTER_PET_RECT, preference='auto')
        self.assertNotIn(key, self.manager._hover_holds)
        for k, number in labels.items():
            if k == key:
                continue
            self.assertEqual(
                self.manager.window_for(k).number_label.text(), number)
        moving = self._orb_positions()
        stamp += 1.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        self.assertNotEqual(self._orb_positions(), moving)

    def test_ring_hide_pressed_task_resumes(self):
        # Blocker B press variant: press x through the real event
        # path, hide it before any release, ring must still resume.
        from PySide6.QtCore import QEvent, QPointF, Qt
        from PySide6.QtGui import QMouseEvent
        tasks = [_codex_entry('b'), _codex_entry('c'),
                 _secondary_codex_entry('z-secondary:x')]
        self._apply_at(tasks, _CENTER_PET_RECT)
        stamp = 30000.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        stamp += 1.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        key = ('codex', 'z-secondary:x')
        orb = self.manager.window_for(key)
        center = orb.rect().center()
        root = orb.mapToGlobal(center)
        press = QMouseEvent(QEvent.MouseButtonPress, QPointF(center),
                            QPointF(root), Qt.LeftButton,
                            Qt.LeftButton, Qt.NoModifier)
        orb.mousePressEvent(press)
        self.assertIn(key, self.manager._press_holds)
        frozen = self._orb_positions()
        stamp += 0.5
        self._tick_at(stamp, _CENTER_PET_RECT)
        self.assertEqual(self._orb_positions(), frozen)
        self._apply_at(tasks[:2], _CENTER_PET_RECT, preference='codex')
        self.assertNotIn(key, self.manager._press_holds)
        stamp += 1.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        self.assertNotEqual(self._orb_positions(), frozen)
        self._apply_at(tasks, _CENTER_PET_RECT, preference='auto')
        self.assertNotIn(key, self.manager._press_holds)
        moving = self._orb_positions()
        stamp += 1.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        self.assertNotEqual(self._orb_positions(), moving)

    def test_ring_multiple_hold_cleanup_semantics(self):
        # A hovered + B pressed: hiding A keeps B's hold (paused);
        # hiding B too resumes. Set cleanup must be exact.
        a = _secondary_codex_entry('z-secondary:x')
        b = _codex_entry('b')
        c = _codex_entry('c')
        key_a = ('codex', 'z-secondary:x')
        key_b = ('codex', 'b')
        self._apply_at([b, c, a], _CENTER_PET_RECT)
        stamp = 31000.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        stamp += 1.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        self.manager.add_hover_hold(key_a)
        self.manager.add_press_hold(key_b)
        self._apply_at([b, c], _CENTER_PET_RECT, preference='codex')
        self.assertNotIn(key_a, self.manager._hover_holds)
        self.assertIn(key_b, self.manager._press_holds)
        frozen = self._orb_positions()
        stamp += 1.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        self.assertEqual(self._orb_positions(), frozen)
        self._apply_at([c], _CENTER_PET_RECT, preference='codex')
        self.assertNotIn(key_b, self.manager._press_holds)
        self.assertEqual(self.manager._hover_holds, set())
        moving = self._orb_positions()
        stamp += 1.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        self.assertNotEqual(self._orb_positions(), moving)

    def test_ring_hide_restore_clears_stale_holds_and_retains_identity(self):
        tasks = [_codex_entry('b'), _secondary_codex_entry('z-secondary:x')]
        self._apply_at(tasks, _CENTER_PET_RECT)
        before = {key: (self.manager.window_for(key), self.manager.slot_for(key),
                        self.manager.label_number_for(key)) for key in self.manager.window_identities()}
        key = ('codex', 'z-secondary:x')
        self.manager.set_hovered(key)
        self.manager.set_visible(False)
        self.assertFalse(self.manager._hover_holds)
        self.assertFalse(self.manager._press_holds)
        self.assertEqual(self.manager.trail_for(key), 0)
        self.manager.set_visible(True)
        for identity, (orb, slot, number) in before.items():
            self.assertIs(self.manager.window_for(identity), orb)
            self.assertEqual((self.manager.slot_for(identity), self.manager.label_number_for(identity)),
                             (slot, number))


    def test_ring_retire_hovered_task_cleans_hold(self):
        # Retirement with an active hover: dead key leaves no hold,
        # survivors resume immediately.
        tasks = [_codex_entry('a'), _codex_entry('b'),
                 _secondary_codex_entry('z-secondary:c')]
        self._apply_at(tasks, _CENTER_PET_RECT)
        stamp = 33000.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        stamp += 1.0
        self._tick_at(stamp, _CENTER_PET_RECT)
        key = ('codex', 'a')
        self.manager.set_hovered(key)
        stamp += 0.5
        self._tick_at(stamp, _CENTER_PET_RECT)
        self._apply_at([_codex_entry('b'),
                        _secondary_codex_entry('z-secondary:c')],
                       _CENTER_PET_RECT)
        self.assertNotIn(key, self.manager._hover_holds)
        self.assertIsNone(self.manager._hovered)
        moving = self._orb_positions()
        # One nominal frame per tick: drive 1 s of real frames so the
        # resumed ring visibly advances.
        for _ in range(25):
            stamp += 0.04
            self._tick_at(stamp, _CENTER_PET_RECT)
        self.assertNotEqual(self._orb_positions(), moving)

    def test_ring_reduced_motion_centered(self):
        # pet_motion=False with a ring-capable layout: static homes,
        # parked paint, no trail — the ring never starts.
        self.panel.prefs['pet_motion'] = False
        try:
            self._apply_at([_codex_entry('a'), _codex_entry('b'),
                            _secondary_codex_entry('z-secondary:c')],
                           _CENTER_PET_RECT)
            homes = self._orb_positions()
            self.assertFalse(self.manager.motion_timer.isActive())
            stamp = 11000.0
            self._tick_at(stamp, _CENTER_PET_RECT)
            stamp += 5.0
            self._tick_at(stamp, _CENTER_PET_RECT)
            self.assertEqual(self._orb_positions(), homes)
            for key in homes:
                orb = self.manager.window_for(key)
                self.assertEqual(
                    (orb.halo_alpha, orb.halo_radius,
                     orb.core_intensity, orb.facet_intensity),
                    (1.0, 1.0, 1.0, 1.0))
            self.assertFalse(
                self.manager.trail_overlay.isVisible())
            self.assertFalse(self.manager.sync_motion())
        finally:
            self.panel.prefs['pet_motion'] = True

    def test_ring_identity_stable_on_retire(self):
        # B retires: A/C keep windows, labels, and slots while the
        # spacing recomposes from thirds to halves.
        tasks = [_codex_entry('a'), _codex_entry('b'),
                 _secondary_codex_entry('z-secondary:c')]
        self._apply_at(tasks, _CENTER_PET_RECT)
        self.assertEqual(self.manager._orbit_mode[0], 'ring')
        survivors = [('codex', 'a'), ('codex', 'z-secondary:c')]
        windows = {k: self.manager.window_for(k) for k in survivors}
        labels = {k: self.manager.window_for(k).number_label.text()
                  for k in survivors}
        slots = {k: self.manager.slot_for(k) for k in survivors}
        self._apply_at([_codex_entry('a'),
                        _secondary_codex_entry('z-secondary:c')],
                       _CENTER_PET_RECT)
        self.assertEqual(self.manager._orbit_mode[0], 'ring')
        for key in survivors:
            self.assertIs(self.manager.window_for(key), windows[key])
            self.assertEqual(
                self.manager.window_for(key).number_label.text(),
                labels[key])
            self.assertEqual(self.manager.slot_for(key), slots[key])
        self.assertEqual(self.manager._ring_offsets,
                         {survivors[0]: 0.0, survivors[1]: 180.0})

    def test_hover_freezes_orbit_and_resumes(self):
        self._apply([_codex_entry('a'), _codex_entry('b')])
        key = ('codex', 'a')
        self._tick(1000.0)
        self._tick(1001.0)
        self.manager.set_hovered(key)
        frozen = self._orb_pos(key)
        self._tick(1001.1)
        self._tick(1001.2)
        self.assertEqual(self._orb_pos(key), frozen)
        self.manager.set_hovered(None)
        self._tick(1001.3)
        resumed = self._orb_pos(key)
        self.assertLessEqual(abs(resumed[0] - frozen[0])
                             + abs(resumed[1] - frozen[1]), 5)

    def test_hover_wiring_via_enter_leave_events(self):
        from PySide6.QtGui import QEnterEvent
        self._apply([_codex_entry('a')])
        key = ('codex', 'a')
        orb = self.manager.window_for(key)
        center = orb.rect().center()
        orb.enterEvent(QEnterEvent(QPointF(center), QPointF(center),
                                   QPointF(center)))
        self.assertEqual(self.manager._hovered, key)
        orb.leaveEvent(QEvent(QEvent.Leave))
        self.assertIsNone(self.manager._hovered)

    def test_breathing_bounds_and_phase_offsets(self):
        self._apply([_codex_entry('a'), _codex_entry('b'),
                     _secondary_codex_entry('z-secondary:c')])
        seen = {}
        stamp = 2000.0
        for _ in range(41):
            self._tick(stamp)
            stamp += 0.25
            for key in self.manager.window_identities():
                orb = self.manager.window_for(key)
                self.assertGreaterEqual(orb.halo_alpha, 0.65)
                self.assertLessEqual(orb.halo_alpha, 1.0)
                self.assertGreaterEqual(orb.halo_radius, 0.92)
                self.assertLessEqual(orb.halo_radius, 1.08)
                self.assertGreaterEqual(orb.core_intensity, 0.85)
                self.assertLessEqual(orb.core_intensity, 1.0)
                self.assertGreaterEqual(orb.facet_intensity, 0.85)
                self.assertLessEqual(orb.facet_intensity, 1.0)
                seen.setdefault(key, set()).add(
                    round(orb.halo_alpha, 3))
        values = list(seen.values())
        self.assertTrue(any(len(v) > 1 for v in values),
                        'breathing must modulate paint state')
        self.assertGreater(len(set(
            tuple(sorted(v)) for v in values)), 1,
            'slots must breathe out of phase')

    def test_trail_bounded_expiry_and_clearing(self):
        self._apply([_codex_entry('a'), _codex_entry('b')])
        key = ('codex', 'a')
        stamp = 3000.0
        for _ in range(30):
            self._tick(stamp)
            stamp += 0.2
            self.assertLessEqual(self.manager.trail_for(key), 10)
        self.assertGreaterEqual(self.manager.trail_for(key), 1)
        self.manager.set_hovered(key)
        self._tick(stamp + 5.0)
        self.assertEqual(self.manager.trail_for(key), 0)
        self.manager.set_hovered(None)
        self._apply([_codex_entry('b')])
        self.assertEqual(self.manager.trail_for(key), 0)

    def test_trail_overlay_input_transparent_and_childless(self):
        self._apply([_codex_entry('a'), _codex_entry('b')])
        self.assertEqual(self.manager._orbit_mode[0], 'arc')
        overlay = self.manager.trail_overlay
        self.assertTrue(overlay.testAttribute(
            Qt.WA_TransparentForMouseEvents))
        self.assertTrue(overlay.testAttribute(
            Qt.WA_ShowWithoutActivating))
        self.assertEqual(
            [c for c in overlay.children()
             if isinstance(c, QWidget)], [])
        stamp = 4000.0
        # One nominal frame per tick: drive 2 s of real frames so the
        # arc builds a visible ribbon.
        for _ in range(50):
            self._tick(stamp)
            stamp += 0.04
        self.assertTrue(overlay.has_trails())
        self.assertTrue(overlay.isVisible())
        self.manager.shutdown()
        self.assertFalse(overlay.isVisible())
        self.assertEqual(self.manager.trail_for(('codex', 'a')), 0)

    def test_pet_follow_tracks_orbit_center(self):
        import pet_geometry as geometry
        self._apply([_codex_entry('a'), _codex_entry('b')])
        self._tick(5000.0)
        self._tick(5001.0)
        before = self._orb_positions()
        moved_pet = (_PET_RECT[0] + 300, _PET_RECT[1],
                     _PET_RECT[2], _PET_RECT[3])
        # Short tick: orbital drift stays sub-pixel-plus-quantization
        # so the rigid +300 shift dominates the assertion.
        self.manager.tick_visual(5001.1, pet_rect=moved_pet,
                                 screen_rect=_SCREEN_RECT)
        after = self._orb_positions()
        for key in before:
            # Rigid pet follow plus at most one tick of swing drift.
            self.assertLessEqual(abs(after[key][0] - before[key][0] - 300)
                                 + abs(after[key][1] - before[key][1]), 5)
            foot = geometry.star_window_footprint(*after[key])
            self.assertFalse(
                geometry.footprint_hits_pet(foot, moved_pet), key)

    def test_reduced_motion_parks_and_freezes(self):
        self.panel.prefs['pet_motion'] = False
        try:
            self._apply([_codex_entry('a'), _codex_entry('b')])
            homes = self._orb_positions()
            self.assertFalse(self.manager.motion_timer.isActive())
            self._tick(6000.0)
            self._tick(6005.0)
            self.assertEqual(self._orb_positions(), homes)
            for key in homes:
                orb = self.manager.window_for(key)
                self.assertEqual(
                    (orb.halo_alpha, orb.halo_radius,
                     orb.core_intensity, orb.facet_intensity),
                    (1.0, 1.0, 1.0, 1.0))
            self.assertFalse(
                self.manager.trail_overlay.isVisible())
            self.assertFalse(self.manager.sync_motion())
        finally:
            self.panel.prefs['pet_motion'] = True

    def test_motion_lifecycle_retire_and_shutdown(self):
        self._apply([_codex_entry('a'), _codex_entry('b'),
                     _secondary_codex_entry('z-secondary:c')])
        self._tick(7000.0)
        self._tick(7001.0)
        self.manager.start_motion()
        self.assertTrue(self.manager.motion_timer.isActive())
        self.manager.stop_motion()
        self.assertFalse(self.manager.motion_timer.isActive())
        self._apply([_codex_entry('a'), _codex_entry('c')])
        self.assertNotIn(('codex', 'b'), self.manager._orbit)
        self.assertNotIn(('codex', 'b'), self.manager._orbit_t)
        self.assertEqual(self.manager.trail_for(('codex', 'b')), 0)
        survivor = self.manager.window_for(('codex', 'a'))
        self.assertIsNotNone(survivor)
        self._apply([])
        self.assertEqual(self.manager.window_count(), 0)
        self.assertFalse(self.manager.motion_timer.isActive())
        self.manager.shutdown()
        self.assertFalse(self.manager.trail_overlay.isVisible())

    def test_retirement_drops_trails_before_readding(self):
        self._apply([_codex_entry('a'),
                     _secondary_codex_entry('z-secondary:b')])
        self._tick(8000.0)
        self._tick(8001.0)
        key = ('codex', 'z-secondary:b')
        self.assertIsNotNone(self.manager.window_for(key))
        self._apply([_codex_entry('a')], preference='codex')
        self.assertIsNone(self.manager.window_for(key))
        self.assertEqual(self.manager.trail_for(key), 0)
        self._apply([_codex_entry('a'), _secondary_codex_entry('z-secondary:b')])
        orb = self.manager.window_for(key)
        self.assertIsNotNone(orb)
        self.assertTrue(orb.number_label.text().isdigit())

    def _probe_overlay(self):
        """Swap in a paint-counting overlay; caller owns no cleanup."""
        from trail_overlay import TrailOverlay

        class ProbeOverlay(TrailOverlay):
            def __init__(self):
                super().__init__()
                self.paints = 0

            def paintEvent(self, event):
                self.paints += 1
                super().paintEvent(event)

        self.manager.trail_overlay.deleteLater()
        probe = ProbeOverlay()
        self.manager.trail_overlay = probe
        return probe

    def test_trail_overlay_repaints_on_motion_updates(self):
        # Astra probe: first show paints once; subsequent motion
        # updates must schedule more paints, or ribbons freeze.
        self._apply([_codex_entry('a'), _codex_entry('b'),
                     _secondary_codex_entry('z-secondary:c')])
        probe = self._probe_overlay()
        stamp = 10000.0
        # One nominal frame per tick: 2 s of real frames per block.
        for _ in range(50):
            self._tick(stamp)
            stamp += 0.04
        self.assertTrue(probe.has_trails())
        self.app.processEvents()
        first_paints = probe.paints
        self.assertGreaterEqual(first_paints, 1)
        for _ in range(50):
            self._tick(stamp)
            stamp += 0.04
        self.app.processEvents()
        self.assertGreater(probe.paints, first_paints)

    def test_trail_overlay_repaints_fade_then_stops(self):
        # A frozen star records nothing, yet its aging ribbon must
        # keep repainting while samples expire, then stop forever.
        # History is seeded directly (deterministic span) so expiry
        # timing never depends on orbital phase luck; fade and
        # silence still run end to end through manager ticks.
        self._apply([_codex_entry('a')])
        probe = self._probe_overlay()
        key = ('codex', 'a')
        for index in range(6):
            probe.record_sample(key, 400.0 + index * 2.0, 300.0,
                                11000.0 + index * 0.2)
        self.assertTrue(probe.has_trails())
        self.manager.set_hovered(key)
        # Arming tick only sets the clock (dt=0 path); expiry math
        # below counts from the ticks that follow.
        self._tick(11000.6)
        # First fade tick drops 2 of 6 samples: visible shrinks but
        # survives, so the update must paint while still shown.
        self._tick(11001.5)
        self.app.processEvents()
        self.assertTrue(probe.isVisible())
        frozen_paints = probe.paints
        self.assertGreaterEqual(frozen_paints, 1)
        # Second fade tick drops 1 more sample: still visible, must
        # repaint again as the ribbon shortens.
        self._tick(11001.7)
        self.app.processEvents()
        self.assertGreater(probe.paints, frozen_paints)
        self.assertTrue(probe.has_trails())
        # All samples expire: overlay hides, then the loop goes quiet.
        for stamp in (11002.5, 11003.5, 11004.5, 11005.5):
            self._tick(stamp)
        self.app.processEvents()
        self.assertFalse(probe.has_trails())
        self.assertFalse(probe.isVisible())
        quiet = probe.paints
        for stamp in (11006.5, 11007.5, 11008.5, 11009.5):
            self._tick(stamp)
        self.app.processEvents()
        self.assertEqual(probe.paints, quiet)
        self.manager.set_hovered(None)

    def test_retire_repaints_overlay_without_stale_ribbon(self):
        # Visible surviving trails need an erase paint; a cleared and
        # hidden parking overlay has no ribbon left to repaint.
        self._apply([_codex_entry('a'), _codex_entry('b')])
        probe = self._probe_overlay()
        stamp = 12000.0
        # One nominal frame per tick: ~2.5 s of real frames builds the
        # survivor ribbon whose erase paint the retire must schedule.
        for _ in range(60):
            self._tick(stamp)
            stamp += 0.04
        self.assertTrue(probe.has_trails())
        self.app.processEvents()
        paints_before = probe.paints
        self._apply([_codex_entry('a')])
        self.app.processEvents()
        self.assertEqual(self.manager.trail_for(('codex', 'b')), 0)
        self.assertNotIn(('codex', 'b'), probe._trails)
        if probe.isVisible():
            self.assertGreater(probe.paints, paints_before)
        else:
            self.assertFalse(probe.has_trails())
        for _ in range(20):
            self._tick(stamp)
            stamp += 0.04
        self.app.processEvents()
        self.assertNotIn(('codex', 'b'), probe._trails)
        self.assertEqual(self.manager.trail_for(('codex', 'b')), 0)


class MultiTaskIntegrationTests(unittest.TestCase):
    """Current Codex-only synthetic stores through the actual poll/publication path."""
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])


    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.pref_patch = patch('widget.PREF_DIR', Path(self.temp.name))
        self.pref_patch.start()
        self.panel = Panel(live=False)
        self.panel.pet = DesktopPet(self.panel)
        self.panel.pet.activity_timer.stop()
        self.work = Path(self.temp.name) / 'stores'
        self.work.mkdir()
        self.manager = self.panel.task_manager


    def tearDown(self):
        self.manager.shutdown()
        self.panel.provider_poller.drain(timeout=10)
        self.panel.provider_poller.close()
        self.panel.pet.close(); self.panel.tray.hide()
        if self.panel.analytics_window: self.panel.analytics_window.close()
        self.panel.closing = True; self.panel.close()
        self.panel.deleteLater(); self.app.processEvents()
        self.pref_patch.stop(); self.temp.cleanup()


    def _publish_render(self, prefs=None, now=None, **kw):
        # Fake clock advances across rounds so the legacy 1-second
        # primary-selection stability can mature exactly like production
        # ticks; the task sets themselves carry no debounce. Every later
        # apply_settings in the same test reuses the final instant so
        # accepted sets stay fresh (FRESHNESS_S=5.0).
        base = NOW_S if now is None else now
        prefs = dict({'scope': 'conversation'}, **(prefs or {}))
        poller = self.panel.provider_poller
        for step, instant in enumerate((base, base + 1.5, base + 3.0)):
            out = poller.poll(prefs, now=instant, **kw)
            if step < 2:
                self.assertTrue(poller.drain(), 'provider reads did not finish')
        self._last_now = base + 3.0
        self.panel.publish_snapshot(out)
        self.app.processEvents()
        return out


    def _apply_publish(self, prefs_update, mark=None, now=None):
        self.panel.prefs.update(prefs_update)
        if now is None:
            now = getattr(self, '_last_now', NOW_S + 3.0)
        out = self.panel.provider_poller.apply_settings(
            dict(self.panel.prefs), mark_provider=mark, now=now)
        self.panel.publish_snapshot(out)
        self.app.processEvents()
        return out


    def _orb_labels(self):
        return {k: self.manager.window_for(k).number_label.text()
                for k in self.manager.window_identities()}


    def _assert_exact_coverage(self, out):
        """Every visible task has exactly one orb; main is never counted."""
        tasks = out.get('active_tasks') or []
        keys = [task_identity(t) for t in tasks]
        self.assertEqual(sorted(self.manager.window_identities()),
                         sorted(keys))
        self.assertEqual(self.manager.window_count(), len(keys))
        return keys


    def test_a_zero_tasks_exactly_one_default_panel(self):
        self._idle_stores()
        out = self._publish_render({'tracking_provider': 'auto'}, now=NOW_S)
        self.assertEqual(out.get('active_tasks'), [])
        self.assertEqual(self.manager.window_count(), 0)
        # The main panel itself is the default: present, not Working,
        # and never a fake task.
        self.assertNotEqual(self.panel.status_text.text(),
                            text('working', self.panel.language))


    def test_b_single_codex_task_gets_one_orb(self):
        self._attach_multi([{'id': 't1', 'working': True,
                             'name': 'PRIVATE REVIEW NOTES'}])
        out = self._publish_render({'tracking_provider': 'auto'}, now=NOW_S,
                                   active_title='t1', detection_valid=True)
        tasks = out.get('active_tasks') or []
        self.assertEqual(len(tasks), 1)
        keys = self._assert_exact_coverage(out)
        self.assertEqual(keys, [('codex', 't1')])
        orb = self.manager.window_for(('codex', 't1'))
        self.assertEqual(orb.number_label.text(), '1')
        self.assertIn('Codex', orb.toolTip())
        self.assertNotIn('PRIVATE REVIEW NOTES', orb.panel_text())
        # Main stays a legacy hub: provider context, no task identity.
        self.assertIn('Codex', self.panel.connection.text())


    def test_c_two_codex_tasks_get_two_orbs(self):
        self._attach_multi([{'id': 't1', 'working': True},
                            {'id': 't2', 'working': True}])
        out = self._publish_render({'tracking_provider': 'auto'}, now=NOW_S,
                                   active_title='t1', detection_valid=True)
        self.assertEqual(len(out.get('active_tasks') or []), 2)
        self._assert_exact_coverage(out)
        self.assertEqual(self.manager.window_count(), 2)
        numbers = sorted(self._orb_labels().values())
        self.assertEqual(len(set(numbers)), 2)


    def test_hub_neutral_with_one_sensitive_codex_task(self):
        # D1 blocker regression: one verified Codex task with a
        # sensitive raw title. The orb is neutral AND the main hub
        # must not expose the raw title or claim a task identity.
        self._attach_multi([{'id': 't1', 'working': True,
                             'name': 'PRIVATE REVIEW NOTES'}])
        out = self._publish_render({'tracking_provider': 'auto'}, now=NOW_S,
                                   active_title='t1', detection_valid=True)
        tasks = out.get('active_tasks') or []
        self.assertEqual(len(tasks), 1)
        keys = self._assert_exact_coverage(out)
        self.assertEqual(keys, [('codex', 't1')])
        self.assertEqual(self.manager.window_count(), 1)
        orb = self.manager.window_for(('codex', 't1'))
        self.assertNotIn('PRIVATE REVIEW NOTES', orb.panel_text())
        main_text = '\n'.join((
            self.panel.title.text(), self.panel.title.toolTip(),
            self.panel.project.text(),
            self.panel.project.toolTip() or '',
            self.panel.connection.text()))
        self.assertNotIn('PRIVATE REVIEW NOTES', main_text)
        self.assertNotIn('t1', self.panel.title.text())
        for language in ('zh_CN', 'en'):
            self.assertNotIn(text('task_panel_label', language, n=1),
                             self.panel.title.text())
        # Main still exists as a companion hub with provider framing.
        self.assertIn('Codex', self.panel.title.text())
        self.assertIn('Codex', self.panel.connection.text())


    def test_zero_orbs_preserves_legacy_title(self):
        # Compatibility: with zero active orbs the legacy main title
        # behavior is fully preserved (pinned scope title passes
        # through unchanged).
        self._attach_multi([{'id': 't1'}, {'id': 't2'}])
        out = self._publish_render({'scope': 'conversation', 'pinned': 't2',
                                    'tracking_provider': 'auto'}, now=NOW_S)
        self.assertEqual(out.get('active_tasks'), [])
        self.assertEqual(self.manager.window_count(), 0)
        self.assertIn('t2', self.panel.title.text())


    def test_global_codex_hub_stays_legacy_orb_surfaced(self):
        # One working thread under global scope: the hub keeps its
        # legacy aggregate view while the task gets exactly one orb.
        # Nothing is consumed into main and nothing is suppressed.
        self._attach_multi([{'id': 't1', 'working': True}, {'id': 't2'}])
        out = self._publish_render({'scope': 'global',
                                    'tracking_provider': 'auto'}, now=NOW_S,
                                   active_title='t1', detection_valid=True)
        tasks = out.get('active_tasks') or []
        self.assertEqual([task_identity(t) for t in tasks], [('codex', 't1')])
        keys = self._assert_exact_coverage(out)
        self.assertEqual(keys, [('codex', 't1')])
        orb = self.manager.window_for(('codex', 't1'))
        self.assertEqual(orb.number_label.text(), '1')
        self.assertIn('Codex', self.panel.connection.text())


    def test_scope_switch_preserves_task_envelope(self):
        # Real clock throughout: change_scope() stamps real time, so the
        # accepted sets must be real-fresh for the envelope assertion to
        # be about preservation rather than expiration.
        self._attach_multi([{'id': 't1', 'working': True},
                            {'id': 't2', 'working': True}])
        out = self._publish_render({'tracking_provider': 'auto'},
                                   now=time.time(),
                                   active_title='t1', detection_valid=True)
        self.assertEqual(len(out.get('active_tasks') or []), 2)
        self._assert_exact_coverage(out)
        labels_before = {
            k: self.manager.label_number_for(k)
            for k in (('codex', 't1'), ('codex', 't2'))}
        homes_before = {
            k: (self.manager.window_for(k).x(),
                self.manager.window_for(k).y())
            for k in (('codex', 't1'), ('codex', 't2'))}
        # Real scope-switch path: the full envelope (tasks + preference)
        # must survive; both orbs persist with stable identity/position.
        self.panel.change_scope('global')
        self.app.processEvents()
        snapshot = self.panel.snapshot
        self.assertEqual(len(snapshot.get('active_tasks') or []), 2)
        self.assertEqual(snapshot.get('preference'), 'codex')
        self._assert_exact_coverage(snapshot)
        self.assertEqual(
            {k: self.manager.label_number_for(k)
             for k in (('codex', 't1'), ('codex', 't2'))},
            labels_before)
        self.assertEqual(
            {k: (self.manager.window_for(k).x(),
                 self.manager.window_for(k).y())
             for k in (('codex', 't1'), ('codex', 't2'))},
            homes_before)
        self.panel.change_scope('conversation')
        self.app.processEvents()
        snapshot = self.panel.snapshot
        self.assertEqual(len(snapshot.get('active_tasks') or []), 2)
        self._assert_exact_coverage(snapshot)
        self.assertEqual(
            {k: self.manager.label_number_for(k)
             for k in (('codex', 't1'), ('codex', 't2'))},
            labels_before)


    def _attach_multi(self, threads):
        import json
        from contextlib import closing
        import sqlite3
        self.panel.provider_poller.drain(timeout=10)
        self.panel.provider_poller.close()
        home = self.work / f'codex-{len(list(self.work.iterdir()))}'
        home.mkdir()
        write_home(str(home), threads)
        for spec in threads:
            path = home / f"{spec['id']}.jsonl"
            events = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
            for event in events:
                if event['type'] == 'turn_context':
                    event['payload']['model'] = spec.get('model', 'gpt-6-sol')
                info = event.get('payload', {}).get('info')
                if info:
                    for usage in ('total_token_usage', 'last_token_usage'):
                        info[usage].update(spec.get('tokens', {}))
            path.write_text(''.join(json.dumps(event) + '\n' for event in events), encoding='utf-8')
            with closing(sqlite3.connect(home / 'state_1.sqlite')) as db:
                db.execute('UPDATE threads SET model=? WHERE id=?',
                           (spec.get('model', 'gpt-6-sol'), spec['id']))
                db.commit()
        self.panel.provider_poller = ProviderPoller(CodexStore(home))
        return home

    def _idle_stores(self):
        return self._attach_multi([{'id': 't1'}])

    def _complete(self, home, key):
        import json
        with (home / f'{key}.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(dict(type='event_msg',
                timestamp=datetime.now(timezone.utc).isoformat(),
                payload=dict(type='task_complete'))) + '\n')

    def test_current_codex_counts_and_distinct_task_local_metrics(self):
        for count in (1, 3, 5, 8):
            with self.subTest(count=count):
                self._attach_multi([dict(id=f't{i}', working=True, model=f'model-{i}',
                                         tokens={'input_tokens': 100 + i,
                                                 'output_tokens': 20 + i,
                                                 'total_tokens': 120 + 2 * i})
                                    for i in range(count)])
                out = self._publish_render(now=NOW_S)
                keys = self._assert_exact_coverage(out)
                self.assertEqual(len(keys), count)
                self.assertEqual({task['provider_id'] for task in out['active_tasks']}, {'codex'})
                by_key = {task['task_key']: task for task in out['active_tasks']}
                for i in range(count):
                    presentation = by_key[f't{i}']['presentation']
                    self.assertEqual(presentation['model'], f'model-{i}')
                    self.assertEqual(presentation['tokens']['total_tokens'], 120 + 2 * i)
                numbers = [self.manager.window_for(key).number_label.text() for key in keys]
                self.assertEqual(len(set(numbers)), count)

    def test_lifecycle_completion_add_and_return_to_default(self):
        home = self._attach_multi([{'id': 't1', 'working': True},
                                   {'id': 't2', 'working': True},
                                   {'id': 't3'}])
        out = self._publish_render(now=NOW_S)
        self.assertEqual(len(self._assert_exact_coverage(out)), 2)
        key = ('codex', 't2')
        survivor = self.manager.window_for(key)
        number, slot = self.manager.label_number_for(key), self.manager.slot_for(key)
        self._complete(home, 't1')
        out = self._publish_render(now=NOW_S)
        self.assertEqual(self._assert_exact_coverage(out), [key])
        self.assertIs(self.manager.window_for(key), survivor)
        self.assertEqual((self.manager.label_number_for(key), self.manager.slot_for(key)),
                         (number, slot))
        import json
        with (home / 't3.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(dict(type='event_msg',
                timestamp=datetime.now(timezone.utc).isoformat(),
                payload=dict(type='task_started'))) + '\n')
        out = self._publish_render(now=NOW_S)
        self.assertEqual(set(self._assert_exact_coverage(out)), {key, ('codex', 't3')})
        self.assertIs(self.manager.window_for(key), survivor)
        self._complete(home, 't2')
        self._complete(home, 't3')
        out = self._publish_render(now=NOW_S)
        self.assertEqual(self._assert_exact_coverage(out), [])
        self.assertNotEqual(self.panel.status_text.text(), text('working', self.panel.language))

    def test_legacy_choices_preserve_all_codex_objects_labels_and_slots(self):
        self._attach_multi([{'id': f't{i}', 'working': True} for i in range(5)])
        self._publish_render(now=NOW_S)
        before = {key: (self.manager.window_for(key), self.manager.label_number_for(key),
                        self.manager.slot_for(key)) for key in self.manager.window_identities()}
        for preference in ('auto', 'opencode', 'codex', 'unknown'):
            out = self._apply_publish({'tracking_provider': preference})
            self.assertEqual(out['preference'], 'codex')
            self.assertEqual(set(self._assert_exact_coverage(out)), set(before))
            for key, (orb, number, slot) in before.items():
                self.assertIs(self.manager.window_for(key), orb)
                self.assertEqual((self.manager.label_number_for(key), self.manager.slot_for(key)),
                                 (number, slot))

    def test_source_failure_retires_all_codex_orbs_and_live_context(self):
        self._attach_multi([{'id': f't{i}', 'working': True} for i in range(3)])
        self.assertEqual(len(self._assert_exact_coverage(self._publish_render(now=NOW_S))), 3)
        from providers import CodexProvider
        self.assertTrue(self.panel.provider_poller.drain())
        with patch.object(CodexProvider, 'read', side_effect=RuntimeError('read failed')):
            out = self._publish_render(now=NOW_S)
        self.assertEqual(self._assert_exact_coverage(out), [])
        self.assertFalse(out['selection']['live'])
        self.assertIsNone(out['result'].get('working_context'))

    def test_codex_provenance_and_task_privacy_both_languages(self):
        self._attach_multi([{'id': f'private-thread-{i}', 'working': True,
                             'name': 'PRIVATE REVIEW NOTES'} for i in range(3)])
        for language in ('zh_CN', 'en'):
            self.panel.prefs['language']=language
            self.panel.apply_language()
            out = self._publish_render(now=NOW_S)
            keys = self._assert_exact_coverage(out)
            visible = '\n'.join(self.manager.window_for(key).panel_text() for key in keys)
            self.assertNotIn('PRIVATE REVIEW NOTES', visible)
            self.assertNotIn('private-thread-', visible)
            self.assertIn('Codex', self.panel.connection.text())
            self.assertNotIn('OpenCode', self.panel.connection.text())
            self.assertNotIn('PRIVATE REVIEW NOTES', self.panel.title.text())
            self.assertNotIn('private-thread-', self.panel.title.text())

    def test_shutdown_and_late_generation_never_resurrect_scene(self):
        self._attach_multi([{'id': 't1', 'working': True}])
        out = self._publish_render(now=NOW_S)
        self.assertEqual(len(self._assert_exact_coverage(out)), 1)
        stale = dict(out, generation=out['generation'] - 1, active_tasks=[],
                     result=dict(out['result'], generation=out['generation'] - 1))
        self.panel.publish_snapshot(stale)
        self.assertEqual(self.manager.window_count(), 1)
        self.panel.shutdown()
        self.panel.publish_snapshot(out)
        self.app.processEvents()
        self.assertEqual(self.manager.window_count(), 0)



class TaskPanelLogicTests(unittest.TestCase):
    """Pure Slice C mapping rules: no widgets, no stores, no threads."""

    def test_task_identity_is_provider_scoped(self):
        codex = {'provider_id': 'codex', 'task_key': '123'}
        opencode = {'provider_id': 'opencode', 'task_key': '123'}
        self.assertEqual(task_identity(codex), ('codex', '123'))
        self.assertNotEqual(task_identity(codex), task_identity(opencode))

    def test_current_codex_order_is_activity_then_stable_key(self):
        tasks = [dict(provider_id='codex', task_key=key, activity_at=instant)
                 for key, instant in (('b', 300.0), ('a', 100.0), ('t', 1.0), ('c', None))]
        ordered = [task_identity(task) for task in order_tasks(tasks)]
        self.assertEqual(ordered, [('codex', 'b'), ('codex', 'a'), ('codex', 't'), ('codex', 'c')])


    def test_order_tie_breaks_on_stable_key(self):
        first = {'provider_id': 'codex', 'task_key': 't2', 'activity_at': 50.0}
        second = {'provider_id': 'codex', 'task_key': 't1', 'activity_at': 50.0}
        ordered = [task_identity(t) for t in order_tasks([first, second])]
        self.assertEqual(ordered, [('codex', 't1'), ('codex', 't2')])

    def test_current_filter_rejects_foreign_tasks_for_legacy_preferences(self):
        codex = {'provider_id': 'codex', 'task_key': 't1'}
        foreign = {'provider_id': 'opencode', 'task_key': 'foreign'}
        for preference in ('codex', 'auto', 'opencode', 'bogus', None):
            self.assertEqual(filter_tasks_for_preference([codex, foreign], preference), [codex])


    def test_filter_never_mutates_input(self):
        tasks = [{'provider_id': 'codex', 'task_key': 't1'}]
        filter_tasks_for_preference(tasks, 'opencode')
        self.assertEqual(len(tasks), 1)

    def test_star_ray_points_bounds(self):
        points = pet_geometry.star_ray_points()
        self.assertEqual(len(points), 8)
        xs = [x for x, _ in points]
        ys = [y for _, y in points]
        self.assertEqual(max(abs(x) for x in xs),
                         pet_geometry.TASK_STAR_RAY_H)
        self.assertEqual(max(abs(y) for y in ys),
                         pet_geometry.TASK_STAR_RAY_V)
        self.assertGreater(pet_geometry.TASK_STAR_RAY_V,
                           pet_geometry.TASK_STAR_RAY_H)
        self.assertLessEqual(2 * pet_geometry.TASK_STAR_RAY_V + 8, 72)
        self.assertLessEqual(2 * pet_geometry.TASK_STAR_RAY_H + 8, 72)

    def test_star_ring_composition_counts(self):
        screen = (0, 0, 1919, 1079)
        pet = (824, 375, 272, 330)
        for count in (1, 2, 3, 4, 5, 8):
            visible = list(range(1, count + 1))
            self._assert_final_star_constraints(visible, pet, screen)

    def test_star_ring_single_prefers_upper_side(self):
        pet = (824, 600, 272, 330)
        screen = (0, 0, 1919, 1079)
        x, y = pet_geometry.star_ring_anchor([3], 3, pet, screen)
        center_x = x + pet_geometry.TASK_STAR_CENTER[0]
        center_y = y + pet_geometry.TASK_STAR_CENTER[1]
        pet_cx = pet[0] + pet[2] / 2
        pet_top = pet[1]
        self.assertLess(center_y, pet_top)
        self.assertLess(abs(center_x - pet_cx), 200)

    def _assert_final_star_constraints(self, visible, pet, screen):
        """Validate FINAL integer UI output against every contract.

        Uses the real runtime path (star_ring_anchor windows +
        star_window_footprint), not float centers: window bounds,
        full-footprint pet exclusion, full-footprint pairwise
        non-overlap (circle-circle, both circle-label directions,
        label-label), and determinism.
        """
        windows = {s: pet_geometry.star_ring_anchor(visible, s, pet, screen)
                   for s in visible}
        left, top, right, bottom = screen
        for slot, (wx, wy) in windows.items():
            self.assertGreaterEqual(wx, left, (visible, pet, slot))
            self.assertGreaterEqual(wy, top, (visible, pet, slot))
            self.assertLessEqual(wx + 112, right + 1, (visible, pet, slot))
            self.assertLessEqual(wy + 112, bottom + 1, (visible, pet, slot))
        feet = {s: pet_geometry.star_window_footprint(*pos)
                for s, pos in windows.items()}
        for slot, footprint in feet.items():
            self.assertFalse(
                pet_geometry.footprint_hits_pet(footprint, pet),
                (visible, pet, slot))
        ordered = sorted(feet)
        for i in range(len(ordered)):
            for j in range(i + 1, len(ordered)):
                self.assertFalse(
                    pet_geometry.footprints_collide(
                        feet[ordered[i]], feet[ordered[j]]),
                    (visible, pet, ordered[i], ordered[j]))
        again = {s: pet_geometry.star_ring_anchor(visible, s, pet, screen)
                 for s in visible}
        self.assertEqual(again, windows)
        return windows

    def test_star_ring_eight_center_pet_repro(self):
        # Exact Astra reproduction: 8 stars around a centered pet.
        # Formerly slots 3 and 7 landed 58.8 px apart (< 76 hit
        # diameters); final footprints must clear completely.
        screen = (0, 0, 1919, 1079)
        pet = (824, 375, 272, 330)
        visible = [1, 2, 3, 4, 5, 6, 7, 8]
        windows = self._assert_final_star_constraints(visible, pet, screen)
        feet = {s: pet_geometry.star_window_footprint(*pos)
                for s, pos in windows.items()}
        (ax, ay, _), _ = feet[3]
        (bx, by, _), _ = feet[7]
        import math
        self.assertGreaterEqual(math.hypot(ax - bx, ay - by), 76)
        self.assertFalse(
            pet_geometry.footprints_collide(feet[3], feet[7]))

    def test_star_ring_four_right_pet_repro(self):
        # Exact Astra reproduction: 4 stars with a right-side pet.
        # Formerly a star clamped to center (1808, 719) with rays in
        # the pet region; final footprints must clear the hub while
        # staying in bounds.
        screen = (0, 0, 1919, 1079)
        pet = (1610, 650, 272, 330)
        visible = [1, 2, 3, 4]
        windows = self._assert_final_star_constraints(visible, pet, screen)
        for slot, (wx, wy) in windows.items():
            self.assertGreaterEqual(wx, 0)
            self.assertLessEqual(wx + 112, 1920)
            footprint = pet_geometry.star_window_footprint(wx, wy)
            self.assertFalse(
                pet_geometry.footprint_hits_pet(footprint, pet), slot)

    def test_star_ring_eight_right_pet_label_repro(self):
        # Right-side pet 8-star layout: with the number-label strip
        # included, no circle/label/label primitive may overlap.
        screen = (0, 0, 1919, 1079)
        pet = (1610, 100, 272, 330)
        visible = [1, 2, 3, 4, 5, 6, 7, 8]
        self._assert_final_star_constraints(visible, pet, screen)

    def test_star_ring_quantization_rule(self):
        # One authoritative rule shared by solver and UI: round
        # half to even, center-anchored. The widget receives exactly
        # these coordinates via QWidget.move.
        self.assertEqual(
            pet_geometry.star_center_to_window_position(100.0, 100.0),
            (44, 52))
        self.assertEqual(
            pet_geometry.star_center_to_window_position(100.5, 100.5),
            (44, 52))
        self.assertEqual(
            pet_geometry.star_center_to_window_position(101.5, 99.5),
            (46, 52))

    def test_star_footprint_matches_widget_mask(self):
        # Canonical footprint equals the real TaskOrbWindow mask and
        # hit-test geometry: disc r38 at star center plus the exact
        # label strip rect.
        disc, label = pet_geometry.star_window_footprint(10, 20)
        self.assertEqual(disc, (66, 68, 38))
        self.assertEqual(label, (10, 106, 112, 24))
        lx, ly, lw, lh = pet_geometry.STAR_LABEL_RECT
        self.assertEqual(label, (10 + lx, 20 + ly, lw, lh))

    def test_star_footprint_collision_boundaries(self):
        # Boundary pinning with non-interacting dummy labels: 77 px
        # disc centers collide, 78 px do not; a disc center 43 px
        # from the pet fails, 44 px passes.
        far_a = (-500, -500, 1, 1)
        far_b = (500, 500, 1, 1)
        disc_a = ((0, 0, 38), far_a)
        disc_b = ((77, 0, 38), far_b)
        disc_c = ((78, 0, 38), far_b)
        self.assertTrue(
            pet_geometry.footprints_collide(disc_a, disc_b))
        self.assertFalse(
            pet_geometry.footprints_collide(disc_a, disc_c))
        pet = (1000, 500, 272, 330)
        inside = ((1000 + 272 + 43, 600, 38), far_a)
        edge = ((1000 + 272 + 44, 600, 38), far_a)
        self.assertTrue(
            pet_geometry.footprint_hits_pet(inside, pet))
        self.assertFalse(
            pet_geometry.footprint_hits_pet(edge, pet))

    def test_star_ring_rounding_rejects_naive_candidate(self):
        # Center distance alone is NOT sufficient: 100 px centers
        # pass any disc rule, yet the 112 px label strips overlap:
        # the full footprint validator rejects while a naive check
        # accepts. At 120 px the same strips clear.
        self.assertTrue(pet_geometry.footprints_collide(
            ((500, 500, 38), (444, 538, 112, 24)),
            ((600, 500, 38), (544, 538, 112, 24))))
        self.assertFalse(pet_geometry.footprints_collide(
            ((500, 500, 38), (444, 538, 112, 24)),
            ((620, 500, 38), (564, 538, 112, 24))))

    def test_star_ring_edge_aware_placements(self):
        screen = (0, 0, 1919, 1079)
        cases = (
            (824, 375, 272, 330),
            (1610, 650, 272, 330),
            (38, 375, 272, 330),
            (1610, 100, 272, 330),
            (824, 20, 272, 330),
            (824, 700, 272, 330),
        )
        for pet in cases:
            for count in (1, 2, 3, 4, 5, 8):
                visible = list(range(1, count + 1))
                self._assert_final_star_constraints(visible, pet, screen)

    def test_star_ring_never_covers_pet(self):
        # No star center may hide inside the companion window: the
        # ring surrounds the hub, never sits on top of it. Uses the
        # same STAR_PET_CLEAR exclusion as the placement contract.
        screen = (0, 0, 1919, 1079)
        pets = ((824, 375, 272, 330), (1610, 650, 272, 330),
                (38, 375, 272, 330), (824, 20, 272, 330),
                (824, 700, 272, 330))
        clear = pet_geometry.STAR_PET_CLEAR
        for pet in pets:
            for count in (1, 2, 3, 4, 5, 8):
                visible = list(range(1, count + 1))
                centers = pet_geometry.star_ring_centers(visible, pet, screen)
                self.assertEqual(len(centers), count)
                for slot, (cx, cy) in centers.items():
                    inside = (pet[0] - clear <= cx <= pet[0] + pet[2] + clear
                              and pet[1] - clear <= cy <= pet[1] + pet[3] + clear)
                    self.assertFalse(inside, (pet, count, slot))

    def test_star_ring_visible_set_not_lifetime_order(self):
        # Filtered-hidden slots leave no holes: composition uses the
        # visible set, while lifetime slots stay untouched.
        pet = (824, 375, 272, 330)
        screen = (0, 0, 1919, 1079)
        full = [pet_geometry.star_ring_anchor([1, 2, 3, 4, 5], s, pet, screen)
                for s in (1, 2, 3, 4, 5)]
        partial = [pet_geometry.star_ring_anchor([1, 3, 5], s, pet, screen)
                   for s in (1, 3, 5)]
        self.assertEqual(len(set(partial)), 3)
        self.assertNotEqual(
            partial[0],
            pet_geometry.star_ring_anchor([1, 2, 3, 4, 5], 1, pet, screen))
        self.assertEqual(len(set(full)), 5)

    def test_star_ring_deterministic_for_same_slot(self):
        pet = (100, 100, 272, 330)
        screen = (0, 0, 1919, 1079)
        first = pet_geometry.star_ring_anchor([1, 2, 3], 2, pet, screen)
        second = pet_geometry.star_ring_anchor([1, 2, 3], 2, pet, screen)
        self.assertEqual(first, second)
        self.assertEqual(pet_geometry.star_phase_seed(2),
                         pet_geometry.star_phase_seed(2))
        self.assertNotEqual(pet_geometry.star_phase_seed(1),
                            pet_geometry.star_phase_seed(2))

    def test_geometry_stack_has_no_overlap_and_clamps(self):
        size = pet_geometry.TASK_WINDOW_CODEX
        pet = (100, 100, 272, 330)
        screen = (0, 0, 1919, 1079)
        first = pet_geometry.task_window_position(0, size, pet, screen)
        second = pet_geometry.task_window_position(1, size, pet, screen)
        self.assertEqual(first[0], second[0])
        self.assertGreater(second[1], first[1])
        self.assertGreaterEqual(first[0], 100 + 272 + 12)
        for slot in range(12):
            x, y = pet_geometry.task_window_position(slot, size, pet, screen)
            self.assertGreaterEqual(x, 0)
            self.assertGreaterEqual(y, 0)
            self.assertLessEqual(x + size[0], 1920)
            self.assertLessEqual(y + size[1], 1080)

    def test_geometry_overflow_uses_second_column(self):
        # Historical exterior repro: pet near center, 8 Codex windows on a
        # 1920x1080 work area. The right side alone cannot hold them, so
        # the algorithm must spill left -- never clamp-stack.
        size = pet_geometry.TASK_WINDOW_OPENCODE
        pet = (1000, 100, 272, 330)
        screen = (0, 0, 1919, 1079)
        positions = [pet_geometry.task_window_position(s, size, pet, screen)
                     for s in range(8)]
        self.assertEqual(len(set(positions)), 8)
        for x, y in positions:
            self.assertGreaterEqual(x, 0)
            self.assertGreaterEqual(y, 0)
            self.assertLessEqual(x + size[0], 1920)
            self.assertLessEqual(y + size[1], 1080)
        seen_x = {x for x, _ in positions}
        self.assertGreater(len(seen_x), 1)

    def test_geometry_edges_and_small_height(self):
        codex = pet_geometry.TASK_WINDOW_CODEX
        screen = (0, 0, 1919, 1079)
        left = [pet_geometry.task_window_position(s, codex, (38, 100, 272, 330), screen)
                for s in range(4)]
        self.assertTrue(all(x >= 38 + 272 + 12 for x, _ in left))
        self.assertEqual(len(set(left)), 4)
        right = [pet_geometry.task_window_position(s, codex, (1610, 100, 272, 330), screen)
                 for s in range(4)]
        self.assertTrue(all(x + codex[0] <= 1610 for x, _ in right))
        self.assertEqual(len(set(right)), 4)
        center = [pet_geometry.task_window_position(s, codex, (824, 100, 272, 330), screen)
                  for s in range(4)]
        self.assertEqual(len(set(center)), 4)
        short = [pet_geometry.task_window_position(s, codex, (100, 100, 272, 330),
                                                   (0, 0, 1919, 399))
                 for s in range(4)]
        self.assertEqual(len(set(short)), 4)
        for x, y in short:
            self.assertGreaterEqual(x, 0)
            self.assertLessEqual(x + codex[0], 1920)

    def test_format_recorded_cost_precision(self):
        # Historical pure formatter; no recorded-cost claim enters Codex UI.
        self.assertEqual(format_recorded_cost(None), 'N/A')
        self.assertEqual(format_recorded_cost(True), 'N/A')
        self.assertEqual(format_recorded_cost('x'), 'N/A')
        self.assertEqual(format_recorded_cost(0), '0.00')
        self.assertEqual(format_recorded_cost(0.0), '0.00')
        self.assertEqual(format_recorded_cost(0.001), '0.001')
        self.assertEqual(format_recorded_cost(0.01), '0.01')
        self.assertEqual(format_recorded_cost(1.23), '1.23')
        self.assertEqual(format_recorded_cost(5.46), '5.46')
        for value in (None, 0, 0.001, 0.01, 1.23, 5.46, 1234.5):
            rendered = format_recorded_cost(value)
            self.assertNotIn('$', rendered)
            self.assertNotIn('USD', rendered)
        self.assertNotEqual(format_recorded_cost(0.001), '0.00')

    def test_current_codex_metrics_preserve_known_unknown_and_zero(self):
        for value, rendered in ((0, '0'), (None, 'N/A'), (532, '532')):
            metrics = format_task_metrics('codex', {'tokens': {
                'total_tokens': value, 'input_tokens': value, 'output_tokens': value,
                'cached_input_tokens': value, 'cache_write_input_tokens': value,
                'reasoning_output_tokens': value}, 'model': None}, 'en')
            for row in ('total', 'input', 'output'):
                self.assertIn(rendered, metrics[row][0])
            self.assertEqual(metrics['model'][0], 'Unknown')
            for unsupported in ('cost', 'reasoning', 'cache_read', 'cache_write'):
                self.assertNotIn(unsupported, metrics)
        known = format_task_metrics('codex', {'tokens': {'total_tokens': 110},
                                             'model': 'gpt-6-sol'}, 'en')
        self.assertIn('110', known['total'][0])
        self.assertEqual(known['model'][0], 'gpt-6-sol')


    def test_geometry_deterministic_for_same_slot(self):
        size = pet_geometry.TASK_WINDOW_CODEX
        pet = (100, 100, 272, 330)
        screen = (0, 0, 1919, 1079)
        self.assertEqual(pet_geometry.task_window_position(2, size, pet, screen),
                         pet_geometry.task_window_position(2, size, pet, screen))

    def test_current_task_localization_keys_both_languages(self):
        for language in ('zh_CN', 'en'):
            label = text('task_panel_label', language, n=3)
            self.assertIn('3', label)
            for key in ('task_panel_total', 'task_panel_input', 'task_panel_output',
                        'task_panel_reasoning', 'task_panel_cache_read', 'task_panel_cache_write',
                        'task_panel_model', 'task_panel_cost', 'unknown'):
                self.assertNotEqual(text(key, language), key)
        self.assertNotEqual(text('task_panel_label', 'zh_CN', n=1),
                            text('task_panel_label', 'en', n=1))



if __name__=='__main__':unittest.main()
