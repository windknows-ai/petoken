import hashlib
import tempfile
import threading
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from PySide6.QtWidgets import QApplication, QCheckBox, QDoubleSpinBox, QLabel, QPushButton
from PySide6.QtGui import QImage
from PySide6.QtCore import QPoint
from widget import Panel, Settings
from pet import DesktopPet
from analytics import aggregate,normalize_usage
from localization import STRINGS, text
from provider_poller import ProviderPoller
from tests.test_opencode_provider import (BASE_MS, make_message, make_part,
                                          make_session, write_store)
from tests.test_providers import write_home
from usage import CodexStore


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


NOW_S = BASE_MS / 1000 + 100


class ProviderUiTests(unittest.TestCase):
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

    def _db(self, name, sessions, messages=(), parts=()):
        path = self.work / name
        write_store(path, sessions, messages, parts)
        return path

    def _attach(self, threads, sessions, messages=(), parts=()):
        self.panel.provider_poller.drain(timeout=10)
        self.panel.provider_poller.close()
        home = self._home(f'codex-{len(list(self.work.iterdir()))}', threads)
        db = self._db(f'open-{len(list(self.work.iterdir()))}.db', sessions,
                      messages, parts)
        self.panel.provider_poller = ProviderPoller(home, db)
        return self.panel.provider_poller

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

    def _apply_render(self, prefs_update, mark=None):
        """Production settings path: persist, apply, synchronous emit."""
        self.panel.prefs.update(prefs_update)
        out = self.panel.provider_poller.apply_settings(
            dict(self.panel.prefs), mark_provider=mark)
        self.panel.render(out['result'])
        self.app.processEvents()
        return out

    def test_settings_tracking_defaults_options_and_labels(self):
        settings = Settings(self.panel)
        self.assertEqual([settings.tracking.itemData(i)
                          for i in range(settings.tracking.count())],
                         ['auto', 'codex', 'opencode'])
        self.assertEqual(settings.tracking.currentData(), 'auto')
        self.assertEqual(settings.tracking_label.text(),
                         text('tracking_provider', 'zh_CN'))
        settings.language.setCurrentIndex(
            settings.language.findData('en'))
        settings.apply_language()
        self.assertEqual(
            [settings.tracking.itemText(i)
             for i in range(settings.tracking.count())],
            [text('tracking_auto', 'en'), text('tracking_codex', 'en'),
             text('tracking_opencode', 'en')])
        settings.reject()

    def test_settings_tracking_save_cancel_reset(self):
        import json
        import widget as widget_module
        poller = self._attach([{'id': 't1'}], [make_session('ses_1')])
        settings = Settings(self.panel)
        settings.tracking.setCurrentIndex(settings.tracking.findData('opencode'))
        before_generation = poller.generation
        settings.save()
        self.assertEqual(self.panel.prefs['tracking_provider'], 'opencode')
        prefs_file = widget_module.PREF_DIR / 'settings.json'
        loaded = json.loads(prefs_file.read_text(encoding='utf-8'))
        self.assertEqual(loaded.get('tracking_provider'), 'opencode')
        self.assertIn('opencode', poller.selection.last_use)
        self.assertGreater(poller.generation, before_generation)
        # Cancel discards: change the form, reject, prefs keep opencode.
        settings = Settings(self.panel)
        settings.tracking.setCurrentIndex(settings.tracking.findData('codex'))
        settings.reject()
        self.assertEqual(self.panel.prefs['tracking_provider'], 'opencode')
        # Reset returns to Auto (two-click confirm), then persists.
        settings = Settings(self.panel)
        settings.reset_to_defaults(); settings.reset_to_defaults()
        self.assertEqual(settings.tracking.currentData(), 'auto')
        settings.save()
        self.assertEqual(self.panel.prefs['tracking_provider'], 'auto')

    def test_codex_opencode_codex_switch_stays_coherent(self):
        self._attach(
            [{'id': 't1', 'working': True}],
            [make_session('ses_1', updated=BASE_MS)],
            [make_message('m1', 'ses_1')],
            [make_part('p1', 'ses_1', created=BASE_MS - 100000)])
        codex = self._poll_render(active_title='t1', detection_valid=True)
        self.assertIn('Codex', self.panel.connection.text())
        codex_total = self.panel.total.text()
        self.assertNotEqual(codex_total, 'N/A')
        self.panel.prefs['tracking_provider'] = 'opencode'
        self.panel.provider_poller.mark_used('opencode')
        self.panel.provider_poller.bump_generation()
        opencode = self._poll_render({'scope': 'conversation',
                                      'pinned': 'ses_1',
                                      'tracking_provider': 'opencode'},
                                     now=NOW_S)
        self.assertIn('OpenCode', self.panel.connection.text())
        self.assertEqual(self.panel.total.text(), 'N/A')
        self.assertEqual(self.panel.model.text(), 'test-model')
        self.assertNotIn('gpt-6-astra', self.panel.model.text())
        self.assertNotIn('gpt-6-astra', self.panel.title.toolTip())
        self.panel.prefs['tracking_provider'] = 'codex'
        self.panel.provider_poller.mark_used('codex')
        self.panel.provider_poller.bump_generation()
        back = self._poll_render({'tracking_provider': 'codex'},
                                 active_title='t1', detection_valid=True)
        self.assertIn('Codex', self.panel.connection.text())
        self.assertEqual(self.panel.total.text(), codex_total)
        self.assertNotIn('test-model', self.panel.model.text())

    def test_both_working_both_idle_and_manual_unavailable(self):
        self._attach(
            [{'id': 't1', 'working': True}],
            [make_session('ses_1', updated=BASE_MS)],
            [make_message('m1', 'ses_1')],
            [make_part('p1', 'ses_1', created=BASE_MS - 100000)])
        both = self._poll_render(active_title='t1', detection_valid=True,
                                 now=NOW_S)
        self.assertTrue(both['selection']['live'])
        self.assertEqual(self.panel.status_text.text(),
                         text('working', self.panel.language))
        # Both idle: Daily, historical, no live bubble arming.
        idle = self._poll_render(
            {'scope': 'global'}, detection_valid=False, now=NOW_S + 10000)
        self.assertFalse(idle['selection']['live'])
        self.assertEqual(self.panel.app_mode.pending, None)
        self.assertEqual(self.panel.app_mode.mode, 'daily')
        self.assertEqual(self.panel.status_text.text(),
                         text('idle', self.panel.language))
        # Manual to a down provider: unavailable, never the other side.
        # Same poller keeps generations monotonic so the render lands.
        self.panel.prefs['tracking_provider'] = 'opencode'
        from opencode_provider import OpenCodeProvider as OcProvider
        self.panel.provider_poller.opencode.close()
        self.panel.provider_poller.opencode = OcProvider(
            self.work / 'absent.db')
        snap = self._poll_render({'tracking_provider': 'opencode'},
                                 now=NOW_S + 10000)
        self.assertIsNone(snap['selection']['selected'])
        self.assertFalse(snap['selection']['live'])
        self.assertIn('OpenCode', self.panel.connection.text())

    def test_working_session_separate_from_pinned_scope(self):
        self._attach(
            [{'id': 't1', 'working': True}, {'id': 't2'}],
            [make_session('ses_a', project='proj-a',
                          directory='/synthetic/alpha',
                          tokens=(10, 1, 1, 1, 0)),
             make_session('ses_b', project='proj-b',
                          directory='/synthetic/beta',
                          tokens=(20, 2, 2, 2, 0), updated=BASE_MS)],
            [make_message('m1', 'ses_b')],
            [make_part('p1', 'ses_b', created=BASE_MS - 100000)])
        # Codex: analytics inspects t2, bubble follows working t1.
        self._poll_render({'scope': 'conversation', 'pinned': 't2'},
                          active_title='t1', detection_valid=True)
        self.assertIn('t1', self.panel.pet.toolTip())
        # OpenCode: analytics inspects ses_a, bubble follows ses_b.
        self.panel.prefs['tracking_provider'] = 'opencode'
        self.panel.provider_poller.mark_used('opencode')
        self.panel.provider_poller.bump_generation()
        self._poll_render({'scope': 'conversation', 'pinned': 'ses_a',
                           'tracking_provider': 'opencode'}, now=NOW_S)
        self.assertIn('OpenCode', self.panel.pet.toolTip())
        self.assertIn('beta', self.panel.pet.toolTip())
        self.assertNotIn('alpha', self.panel.pet.toolTip())
        self.assertIn(text('active_session', self.panel.language),
                      self.panel.pet.toolTip())
        self.assertNotIn('ses_b', self.panel.pet.toolTip())
        self.assertEqual(self.panel.title.text(),
                         text('active_session', self.panel.language))
        self.assertNotIn('ses_a', self.panel.title.toolTip())

    def test_missing_scope_with_valid_working_codex(self):
        self._attach([{'id': 't1', 'working': True}, {'id': 't2'}], [])
        out = self._poll_render({'scope': 'conversation', 'pinned': 'ghost'},
                                active_title='t1', detection_valid=True)
        self.assertTrue(out['selection']['live'])
        self.assertIn('t1', self.panel.pet.toolTip())
        self.assertIn('Codex', self.panel.connection.text())

    def test_valid_history_with_unknown_activity_opencode(self):
        path = self.work / 'noparts.db'
        write_store(path, [make_session('ses_1', tokens=(100, 20, 5, 400, 0))],
                    with_part_table=False)
        home = self._home('codex-idle', [{'id': 't1'}])
        self.panel.provider_poller.drain(timeout=10)
        self.panel.provider_poller.close()
        self.panel.provider_poller = ProviderPoller(home, path)
        out = self._poll_render({'tracking_provider': 'opencode'})
        self.assertFalse(out['selection']['live'])
        self.assertEqual(self.panel.status_text.text(),
                         text('unknown', self.panel.language))
        # History still renders: scope sum visible without a live claim.
        self.assertIn('100', self.panel.io_line.text())

    def test_source_failure_clears_live_keeps_history_honest(self):
        poller = self._attach([{'id': 't1', 'working': True}],
                              [make_session('ses_1', updated=BASE_MS)])
        live = self._poll_render(active_title='t1', detection_valid=True,
                                 now=NOW_S)
        self.assertTrue(live['selection']['live'])
        from unittest.mock import patch
        from providers import CodexProvider
        with patch.object(CodexProvider, 'read',
                          side_effect=RuntimeError('boom')):
            failed = self._poll_render(now=NOW_S)
        # Live is removed at once; the surviving provider's own scope
        # data renders (N/A total, no Codex numbers lingering).
        self.assertFalse(failed['selection']['live'])
        self.assertIsNone(failed['result'].get('working_context'))
        self.assertNotIn('gpt-6-astra', self.panel.model.text())
        self.assertIn('OpenCode', self.panel.connection.text())
        self.assertEqual(self.panel.total.text(), 'N/A')

    def test_late_generation_quota_and_scope_ignored(self):
        self._attach(
            [{'id': 't1', 'working': True}],
            [make_session('ses_1', updated=BASE_MS)],
            [make_message('m1', 'ses_1')],
            [make_part('p1', 'ses_1', created=BASE_MS - 100000)])
        first = self._poll_render(active_title='t1', detection_valid=True,
                                  now=NOW_S)
        first_total = self.panel.total.text()
        stale = dict(first['result'])
        stale['generation'] = first['generation'] - 1
        stale['scope'] = 'project'
        self.panel.render(stale)
        self.app.processEvents()
        self.assertEqual(self.panel.total.text(), first_total)
        # Late Codex quota under OpenCode selection renders N/A.
        self.panel.prefs['tracking_provider'] = 'opencode'
        self.panel.provider_poller.mark_used('opencode')
        self.panel.provider_poller.bump_generation()
        self._poll_render({'tracking_provider': 'opencode'}, now=NOW_S)
        self.panel.receive_limits(dict(provider_id='codex', sampled=time.time(),
                                       limits={'primary': {'usedPercent': 30,
                                                           'windowDurationMins': 300,
                                                           'resetsAt': time.time() + 1800}}))
        self.app.processEvents()
        self.assertEqual(self.panel.five.value.text(), '—')
        self.assertFalse(self.panel.five.reset.isVisible())

    def test_opencode_na_boundaries_and_real_zero(self):
        self._attach(
            [{'id': 't1'}],
            [make_session('ses_zero', tokens=(0, 0, 0, 0, 0), cost=0.0,
                          updated=BASE_MS)],
            [make_message('m1', 'ses_zero')],
            [make_part('p1', 'ses_zero', created=BASE_MS - 100000)])
        out = self._poll_render({'scope': 'conversation',
                                 'pinned': 'ses_zero',
                                 'tracking_provider': 'opencode'}, now=NOW_S)
        self.assertTrue(out['selection']['live'])
        self.assertEqual(self.panel.total.text(), 'N/A')
        self.assertEqual(self.panel.cost.text(), '—')
        self.assertIn('0.0000', self.panel.cost.toolTip())
        self.assertEqual(self.panel.context.value.text(), '—')
        # Real zeros render as 0, missing values as N/A.
        self.assertIn(' 0 ', f" {self.panel.io_line.text()} ")
        self.assertEqual(self.panel.five.value.text(), '—')
        self.assertFalse(self.panel.five.reset.isVisible())
        self.assertNotIn('$', self.panel.cost.text())
        self.assertNotIn('CA$', self.panel.cost.toolTip())

    def test_long_names_keep_layout_usable(self):
        long_name = 'x' * 200
        self._attach(
            [{'id': 't1', 'working': True}],
            [make_session('ses_1', project='p', directory='/synthetic/' + long_name,
                          updated=BASE_MS)],
            [make_message('m1', 'ses_1')],
            [make_part('p1', 'ses_1', created=BASE_MS - 100000)])
        width_before = self.panel.width()
        self._poll_render({'scope': 'conversation', 'pinned': 'ses_1',
                           'tracking_provider': 'opencode'}, now=NOW_S)
        self.app.processEvents()
        self.assertEqual(self.panel.width(), width_before)
        self.assertLessEqual(len(self.panel.project.text()), 200)
        self.assertIn(long_name.upper(), self.panel.project.toolTip())
        self.panel.show(); self.app.processEvents()

    def test_provider_switch_preserves_pet_and_chrome(self):
        poller = self._attach(
            [{'id': 't1', 'working': True}],
            [make_session('ses_1', updated=BASE_MS)],
            [make_message('m1', 'ses_1')],
            [make_part('p1', 'ses_1', created=BASE_MS - 100000)])
        self._poll_render(active_title='t1', detection_valid=True, now=NOW_S)
        pet_pos = self.panel.pet.pos()
        pet_size = self.panel.pet.size()
        pin_before = self.panel.is_pinned()
        self.panel.prefs['tracking_provider'] = 'opencode'
        poller.mark_used('opencode')
        poller.bump_generation()
        self._poll_render({'tracking_provider': 'opencode'}, now=NOW_S)
        self.panel.prefs['tracking_provider'] = 'auto'
        poller.bump_generation()
        self._poll_render(now=NOW_S)
        self.assertEqual(self.panel.pet.pos(), pet_pos)
        self.assertEqual(self.panel.pet.size(), pet_size)
        self.assertEqual(self.panel.is_pinned(), pin_before)
        self.panel.show(); self.app.processEvents()
        self.panel.toggle_compact(); self.app.processEvents()
        from widget import COMPACT_HEIGHT
        self.assertEqual(self.panel.height(), COMPACT_HEIGHT)
        self.panel.toggle_compact(); self.app.processEvents()
        self.assertTrue(self.panel.body_scroll.isVisible())

    def test_synthetic_bilingual_panel_matrix_screenshots(self):
        import os
        from opencode_provider import OpenCodeProvider
        shots = os.path.join(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))), '.private',
            'ui-slice5')
        os.makedirs(shots, exist_ok=True)

        def build():
            return self._attach(
                [{'id': 't1', 'working': True}],
                [make_session('ses_1', updated=BASE_MS)],
                [make_message('m1', 'ses_1')],
                [make_part('p1', 'ses_1', created=BASE_MS - 100000)])

        self.panel.resize(560, 500)
        for language in ('zh_CN', 'en'):
            poller = build()
            self.panel.prefs['language'] = language
            self.panel.prefs['tracking_provider'] = 'auto'
            self.panel.apply_language()
            codex = self._poll_render(active_title='t1',
                                      detection_valid=True)
            self._shot(shots, f'{language}-codex-live', language,
                       codex['result'])
            self.panel.prefs['tracking_provider'] = 'opencode'
            poller.mark_used('opencode')
            poller.bump_generation()
            opencode = self._poll_render(
                {'scope': 'conversation', 'pinned': 'ses_1',
                 'tracking_provider': 'opencode'}, now=NOW_S)
            self._shot(shots, f'{language}-opencode-live', language,
                       opencode['result'])
            self.panel.provider_poller.opencode.close()
            self.panel.provider_poller.opencode = OpenCodeProvider(
                os.path.join(self.temp.name, 'absent.db'))
            missing = self._poll_render({'tracking_provider': 'opencode'},
                                        now=NOW_S)
            self._shot(shots, f'{language}-opencode-unavailable', language,
                       missing['result'])

    def _shot(self, shots, name, language, result):
        import os
        self.panel.prefs['language'] = language
        self.panel.apply_language()
        self.panel.render(result)
        self.app.processEvents()
        path = os.path.join(shots, f'{name}.png')
        self.assertTrue(self.panel.grab().save(path, 'PNG'), name)
        self.assertGreater(os.path.getsize(path), 10000, name)

    def test_settings_save_applies_immediately_without_poll(self):
        self._attach([{'id': 't1', 'working': True}],
                     [make_session('ses_1', updated=BASE_MS)],
                     [make_message('m1', 'ses_1')],
                     [make_part('p1', 'ses_1', created=BASE_MS - 100000)])
        self._poll_render(active_title='t1', detection_valid=True)
        self.assertIn('Codex', self.panel.connection.text())
        settings = Settings(self.panel)
        settings.tracking.setCurrentIndex(
            settings.tracking.findData('opencode'))
        settings.save()
        # No manual poll or render invoked: save published synchronously.
        self.assertIn('OpenCode', self.panel.connection.text())
        self.assertIn('opencode',
                      self.panel.provider_poller.selection.last_use)
        settings = Settings(self.panel)
        settings.tracking.setCurrentIndex(
            settings.tracking.findData('codex'))
        settings.save()
        self.assertIn('Codex', self.panel.connection.text())

    def test_token_mode_switch_retires_pet_context(self):
        self._attach(
            [{'id': 't1', 'working': True}],
            [make_session('ses_1', updated=BASE_MS)],
            [make_message('m1', 'ses_1')],
            [make_part('p1', 'ses_1', created=BASE_MS - 100000)])
        self._poll_render(active_title='t1', detection_valid=True)
        tick = time.monotonic()
        self.panel.app_mode.update(True, True, now=tick)
        self.panel.app_mode.update(True, True, now=tick + 0.5)
        self.assertTrue(self.panel.pet.token_bubble_visible())
        self.assertEqual(self.panel.pet.working_context['thread'], 't1')
        # Switch to available-but-idle OpenCode while Token Mode is
        # still inside its deactivation delay.
        self._apply_render({'tracking_provider': 'opencode'},
                           mark='opencode')
        self.assertTrue(self.panel.pet.token_bubble_visible())
        self.assertIsNone(self.panel.pet.working_context)
        self.assertNotIn('t1', self.panel.pet.toolTip())
        # Scope data stays provider-labeled; t1 is gone, not relabeled.
        self.assertIn('OpenCode', self.panel.pet.toolTip())

    def test_missing_working_row_clears_bubble(self):
        import sqlite3
        from contextlib import closing
        path = self._db('orphan.db',
                        [make_session('ses_x', project='proj-x',
                                      directory='/synthetic/xray',
                                      updated=BASE_MS)],
                        [make_message('m1', 'ses_x')],
                        [make_part('p1', 'ses_x', created=BASE_MS - 100000)])
        home = self._home('codex-missing-row', [{'id': 't1'}])
        from provider_poller import ProviderPoller as Poller
        self.panel.provider_poller.drain(timeout=10)
        self.panel.provider_poller.close()
        self.panel.provider_poller = Poller(home, path)
        with closing(sqlite3.connect(path, timeout=5)) as db:
            db.execute("DELETE FROM session WHERE id='ses_x'")
            db.commit()
        out = self._poll_render({'tracking_provider': 'opencode'},
                                now=NOW_S)
        self.assertIsNone(out['result'].get('working_context'))
        self.assertIn('N/A', self.panel.pet.toolTip())

    def test_quota_clears_atomically_on_unavailable_switch(self):
        self._attach(
            [{'id': 't1', 'working': True}],
            [make_session('ses_1', updated=BASE_MS)],
            [make_message('m1', 'ses_1')],
            [make_part('p1', 'ses_1', created=BASE_MS - 100000)])
        self._poll_render(active_title='t1', detection_valid=True)
        self.panel.receive_limits(dict(
            sampled=time.time(),
            limits={'primary': {'usedPercent': 30, 'windowDurationMins': 300,
                                'resetsAt': time.time() + 18000}}))
        self.app.processEvents()
        self.panel.show(); self.app.processEvents()
        self.assertIn('70%', self.panel.five.value.text())
        self.assertTrue(self.panel.five.reset.isVisible())
        from opencode_provider import OpenCodeProvider as OcProvider
        self.panel.provider_poller.opencode.close()
        self.panel.provider_poller.opencode = OcProvider(
            self.work / 'absent.db')
        self._apply_render({'tracking_provider': 'opencode'},
                           mark='opencode')
        # Same-transaction clearing: no timer tick or quota callback
        # runs between render and these assertions.
        self.assertEqual(self.panel.five.value.text(), '—')
        self.assertFalse(self.panel.five.reset.isVisible())
        self.assertEqual(self.panel.cost.text(), '—')
        self.assertEqual(self.panel.context.value.text(), '—')
        self.assertIn('OpenCode', self.panel.connection.text())

    def test_codex_unavailable_preserves_quota(self):
        self._attach([{'id': 't1', 'working': True}],
                     [make_session('ses_1')])
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
        poller = self._attach(
            [{'id': 't1', 'working': True}, {'id': 't2'}],
            [make_session('ses_1')])
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
        self._attach(
            [{'id': 't1', 'working': True}, {'id': 't2'}],
            [make_session('ses_a', project='proj-a',
                          directory='/synthetic/alpha',
                          tokens=(10, 1, 1, 1, 0)),
             make_session('ses_b', project='proj-b',
                          directory='/synthetic/beta',
                          tokens=(20, 2, 2, 2, 0), updated=BASE_MS)],
            [make_message('m1', 'ses_b')],
            [make_part('p1', 'ses_b', created=BASE_MS - 100000)])
        # Codex side first: scope title t2, bubble follows working t1.
        self._poll_render({'scope': 'conversation', 'pinned': 't2'},
                          active_title='t1', detection_valid=True)
        self.assertIn('t2', self.panel.title.text())
        self.assertIn('t1', self.panel.pet.toolTip())
        # OpenCode side: differing projects/tokens prove the binding.
        self.panel.prefs['tracking_provider'] = 'opencode'
        self.panel.provider_poller.mark_used('opencode')
        self.panel.provider_poller.bump_generation()
        out = self._poll_render({'scope': 'conversation', 'pinned': 'ses_a',
                                 'tracking_provider': 'opencode'}, now=NOW_S)
        context = out['result']['working_context']
        self.assertEqual((context['thread'], context['project'],
                          context['tokens']['input']), ('ses_b', 'beta', 20))
        self.assertIn('beta', self.panel.pet.toolTip())
        self.assertNotIn('alpha', self.panel.pet.toolTip())

    def _live_work(self, sessions=None, messages=None, parts=None):
        if sessions is None:
            sessions = [make_session(
                'ses_work', project='proj-w',
                directory='/synthetic/work', tokens=(100, 20, 5, 400, 7),
                cost=0.05, updated=BASE_MS)]
        if messages is None:
            messages = [make_message('m1', 'ses_work')]
        if parts is None:
            parts = [make_part('p1', 'ses_work',
                               created=BASE_MS - 100000)]
        return self._attach([{'id': 't1'}], sessions, messages, parts)

    def _assert_active_panel(self):
        self.assertIn(text('active_session', self.panel.language),
                      self.panel.connection.text())
        # Prominent surfaces never show raw session IDs; the exact ID
        # stays in selection, attribution, and analytics instead.
        self.assertEqual(self.panel.title.text(),
                         text('active_session', self.panel.language))
        self.assertIn(text('active_session', self.panel.language),
                      self.panel.title.toolTip())
        self.assertNotIn('ses_work', self.panel.title.toolTip())
        self.assertEqual(self.panel.model.text(), 'test-model')
        self.assertIn('100', self.panel.io_line.text())
        self.assertEqual(self.panel.total.text(), 'N/A')
        self.assertEqual(self.panel.status_text.text(),
                         text('working', self.panel.language))

    def test_live_opencode_without_pin_shows_active_session(self):
        self._live_work()
        out = self._poll_render({'scope': 'conversation',
                                 'tracking_provider': 'opencode'},
                                now=NOW_S)
        self.assertTrue(out['selection']['live'])
        self.assertEqual(out['result'].get('presentation'),
                         'active_session')
        self._assert_active_panel()
        # Auto with the same saved Conversation/no-pin preferences.
        self.panel.prefs['tracking_provider'] = 'auto'
        self.panel.provider_poller.mark_used('opencode')
        self.panel.provider_poller.bump_generation()
        auto = self._poll_render({'scope': 'conversation'}, now=NOW_S)
        self.assertEqual(auto['selection']['selected'], 'opencode')
        self.assertTrue(auto['selection']['live'])
        self.assertEqual(auto['result'].get('presentation'),
                         'active_session')
        self._assert_active_panel()

    def test_codex_pin_does_not_hide_live_opencode(self):
        self._live_work()
        out = self._poll_render({'scope': 'conversation', 'pinned': 't1',
                                 'tracking_provider': 'opencode'},
                                now=NOW_S)
        self.assertTrue(out['selection']['live'])
        self._assert_active_panel()
        self.assertEqual(out['result']['session_id'],
                         'opencode:ses_work')
        self.assertEqual(out['result']['tokens']['input'], 100)

    def test_matching_pin_keeps_scoped_view(self):
        self._live_work()
        out = self._poll_render({'scope': 'conversation',
                                 'pinned': 'ses_work',
                                 'tracking_provider': 'opencode'},
                                now=NOW_S)
        result = out['result']
        self.assertTrue(result['available'])
        self.assertIsNone(result.get('presentation'))
        self.assertEqual(result['scope_identity']['scope_type'],
                         'conversation')
        self.assertNotIn(text('active_session', self.panel.language),
                         self.panel.connection.text())
        self.assertEqual(self.panel.title.text(),
                         text('active_session', self.panel.language))
        # The pinned session's exact ID stays in selection/attribution,
        # never in the prominent title.
        self.assertNotIn('ses_work', self.panel.title.toolTip())
        self.assertEqual(out['result']['session_id'],
                         'opencode:ses_work')

    def test_other_pin_shows_scope_with_live_bubble(self):
        self._live_work(
            [make_session('ses_work', project='proj-w',
                          directory='/synthetic/work',
                          tokens=(100, 20, 5, 400, 7), cost=0.05,
                          updated=BASE_MS),
             make_session('ses_idle', project='proj-i',
                          directory='/synthetic/idle',
                          tokens=(10, 1, 1, 1, 0), cost=0.01)],
            [make_message('m1', 'ses_work')],
            [make_part('p1', 'ses_work', created=BASE_MS - 100000)])
        out = self._poll_render({'scope': 'conversation',
                                 'pinned': 'ses_idle',
                                 'tracking_provider': 'opencode'},
                                now=NOW_S)
        result = out['result']
        self.assertTrue(result['available'])
        self.assertIsNone(result.get('presentation'))
        # Panel shows the pinned scope's own values, never the live row;
        # the prominent title stays neutral while the exact pinned ID
        # remains in selection and analytics.
        self.assertEqual(self.panel.title.text(),
                         text('active_session', self.panel.language))
        self.assertNotIn('ses_idle', self.panel.title.toolTip())
        self.assertNotIn('ses_work', self.panel.title.toolTip())
        self.assertEqual(result['session_id'], 'opencode:ses_idle')
        self.assertIn('10', self.panel.io_line.text())
        # The bubble follows the live working session instead.
        self.assertEqual(result['working_context']['thread'], 'ses_work')
        self.assertIn('work', self.panel.pet.toolTip())
        self.assertIn(text('active_session', self.panel.language),
                      self.panel.pet.toolTip())
        self.assertNotIn('ses_work', self.panel.pet.toolTip())

    def test_opencode_hides_quota_context_everywhere(self):
        self._live_work()
        self.panel.show()
        self.app.processEvents()
        quotas = dict(
            sampled=time.time(),
            limits={'primary': {'usedPercent': 30,
                                'windowDurationMins': 300,
                                'resetsAt': time.time() + 18000}})
        self.panel.receive_limits(quotas)
        self.app.processEvents()
        out = self._poll_render({'scope': 'conversation',
                                 'tracking_provider': 'opencode'},
                                now=NOW_S)
        self.assertTrue(out['result']['available'])
        for language in ('zh_CN', 'en'):
            self.panel.prefs['language'] = language
            self.panel.apply_language()
            self.panel.render(out['result'])
            self.app.processEvents()
            self.assertFalse(self.panel.context.isVisible())
            self.assertFalse(self.panel.five.isVisible())
            self.assertFalse(self.panel.week.isVisible())
            self.assertFalse(self.panel.quota_divider.isVisible())
            self.assertFalse(self.panel.status.isVisible())
            # Metrics body ends at Token Analytics; recorded cost stays.
            self.assertTrue(self.panel.cost.isVisible())
            self.assertTrue(self.panel.details_button.isVisible())
        # Late quota updates while in OpenCode repaint hidden text only.
        self.panel.receive_limits(quotas)
        self.app.processEvents()
        self.assertFalse(self.panel.five.isVisible())
        self.assertFalse(self.panel.status.isVisible())
        # Stale OpenCode (source older than the freshness gate) keeps
        # the area hidden instead of a waiting refresh status.
        from opencode_provider import OpenCodeProvider
        self.assertTrue(
            self.panel.provider_poller.drain(timeout=10))
        entered, release = self._hold(OpenCodeProvider)
        try:
            thread, _ = self._poll_thread(
                {'scope': 'conversation',
                 'tracking_provider': 'opencode'}, now=NOW_S)
            self.assertTrue(entered.wait(timeout=10))
            thread.join(timeout=10)
            self.assertFalse(thread.is_alive())
            poller = self.panel.provider_poller
            stale = poller.poll(
                {'scope': 'conversation',
                 'tracking_provider': 'opencode'}, now=NOW_S + 10)
            self.panel.render(stale['result'])
            self.app.processEvents()
            self.assertFalse(stale['selection']['live'])
            self.assertTrue(stale['selection']['stale'])
            self.assertFalse(self.panel.context.isVisible())
            self.assertFalse(self.panel.five.isVisible())
            self.assertFalse(self.panel.week.isVisible())
            self.assertFalse(self.panel.status.isVisible())
        finally:
            release.set()
            self.assertTrue(
                self.panel.provider_poller.drain(timeout=10))
        # Compact layout: twins carry cost/total, quota stays hidden.
        self.panel.toggle_compact()
        self.app.processEvents()
        self.assertTrue(self.panel.compact_box.isVisible())
        self.assertFalse(self.panel.five.isVisible())
        self.assertFalse(self.panel.status.isVisible())
        self.panel.toggle_compact()
        self.app.processEvents()
        self.assertFalse(self.panel.context.isVisible())
        self.assertFalse(self.panel.five.isVisible())
        # Unavailable OpenCode keeps the area hidden, never N/A meters.
        from opencode_provider import OpenCodeProvider as OcProvider
        self.panel.provider_poller.opencode.close()
        self.panel.provider_poller.opencode = OcProvider(
            self.work / 'absent.db')
        gone = self._poll_render({'tracking_provider': 'opencode'},
                                 now=NOW_S)
        self.assertFalse(gone['result']['available'])
        self.assertFalse(self.panel.context.isVisible())
        self.assertFalse(self.panel.five.isVisible())
        self.assertFalse(self.panel.week.isVisible())
        self.assertFalse(self.panel.status.isVisible())
        # Switching back to Codex restores quota/context immediately.
        # A re-attached poller is a fresh producer: like an app
        # relaunch it restarts the render-generation guard, while its
        # own generations stay monotonic afterward.
        self._attach([{'id': 't1', 'working': True}],
                     [make_session('ses_1')])
        self.panel.provider_poller.mark_used('codex')
        self.panel._render_generation = None
        self.panel.receive_limits(quotas)
        self.app.processEvents()
        codex = self._poll_render({'tracking_provider': 'codex'},
                                  active_title='t1', detection_valid=True)
        self.assertTrue(codex['selection']['live'])
        self.assertTrue(self.panel.context.isVisible())
        self.assertTrue(self.panel.five.isVisible())
        self.assertTrue(self.panel.week.isVisible())
        self.assertTrue(self.panel.quota_divider.isVisible())
        self.assertTrue(self.panel.status.isVisible())
        self.assertIn('70%', self.panel.five.value.text())

    def test_verified_live_total_shows_recorded_sum(self):
        self._live_work(
            [make_session('ses_big', project='proj-w',
                          directory='/synthetic/work',
                          version='1.18.31',
                          tokens=(1000, 200, 30, 4000, 70), cost=0.05,
                          updated=BASE_MS)],
            [make_message('m1', 'ses_big')],
            [make_part('p1', 'ses_big', created=BASE_MS - 100000)])
        out = self._poll_render({'scope': 'conversation',
                                 'tracking_provider': 'opencode'},
                                now=NOW_S)
        result = out['result']
        self.assertTrue(result['available'])
        self.assertEqual(result['presentation'], 'active_session')
        self.assertEqual(result['tokens']['total'], 5300)
        self.assertEqual(self.panel.total.text(), '5.30K')
        self.assertIn('1.00K', self.panel.total.toolTip())
        self.assertIn(text('total_unavailable_note', self.panel.language),
                      self.panel.total.toolTip())
        # Splits stay raw and separate beside the recorded total.
        self.assertIn('1.00K', self.panel.io_line.text())
        # Pet tooltip carries the recorded total under a neutral title.
        self.assertIn('5.30K', self.panel.pet.toolTip())
        self.assertIn(text('active_session', self.panel.language),
                      self.panel.pet.toolTip())
        self.assertNotIn('ses_big', self.panel.pet.toolTip())
        # Recorded cost preserved; quota/context hidden.
        self.assertEqual(result['cost']['amount'], 0.05)
        self.assertFalse(self.panel.context.isVisible())
        self.assertFalse(self.panel.five.isVisible())
        self.assertFalse(self.panel.status.isVisible())

    def test_idle_unknown_and_missing_stay_honest(self):
        self._attach([{'id': 't1'}],
                     [make_session('ses_idle', updated=BASE_MS)])
        idle = self._poll_render({'scope': 'conversation',
                                  'tracking_provider': 'opencode'},
                                 now=NOW_S)
        # Idle with no live lane: honest unavailable, never a fabricated
        # scope view (transient store contention under load may surface
        # the preference-bound pending shape instead of the scope miss).
        self.assertFalse(idle['result']['available'])
        self.assertIn(self.panel.connection.text(),
                      [f"OpenCode · {text('waiting_available_task', self.panel.language)}",
                       f"OpenCode · {text('no_reliable_record', self.panel.language)}"])
        self.assertEqual(self.panel.total.text(), '—')
        self.assertFalse(self.panel.status_dot.isVisible())
        self.assertIsNone(idle['result'].get('working_context'))
        # Unknown activity with a matching scope stays unknown, never
        # working: scoped values render without a live claim.
        path = self.work / 'noparts.db'
        write_store(path, [make_session('ses_1', tokens=(100, 20, 5, 400, 0))],
                    with_part_table=False)
        home = self._home('codex-idle', [{'id': 't1'}])
        self.panel.provider_poller.drain(timeout=10)
        self.panel.provider_poller.close()
        self.panel.provider_poller = ProviderPoller(home, path)
        unknown = self._poll_render({'scope': 'conversation',
                                     'pinned': 'ses_1',
                                     'tracking_provider': 'opencode'},
                                    now=NOW_S)
        self.assertFalse(unknown['selection']['live'])
        self.assertEqual(self.panel.status_text.text(),
                         text('unknown', self.panel.language))
        # A deleted session row clears the live panel, never a stale one.
        self._live_work()
        live = self._poll_render({'scope': 'conversation',
                                  'tracking_provider': 'opencode'},
                                 now=NOW_S)
        self.assertTrue(live['result']['available'])
        import sqlite3
        from contextlib import closing
        db = self.panel.provider_poller.opencode.db_path
        with closing(sqlite3.connect(db)) as connection:
            connection.execute("DELETE FROM session WHERE id='ses_work'")
            connection.commit()
        gone = self._poll_render({'scope': 'conversation',
                                  'tracking_provider': 'opencode'},
                                 now=NOW_S)
        self.assertFalse(gone['result']['available'])
        self.assertIsNone(gone['result'].get('presentation'))
        self.assertIsNone(gone['result'].get('working_context'))
        self.assertIn(text('waiting_available_task',
                           self.panel.language),
                      self.panel.connection.text())

    def test_read_failure_stays_honest(self):
        self._live_work()
        from opencode_provider import OpenCodeProvider
        with patch.object(OpenCodeProvider, 'read',
                          side_effect=RuntimeError('boom')):
            failed = self._poll_render(
                {'scope': 'conversation',
                 'tracking_provider': 'opencode'}, now=NOW_S)
        self.assertFalse(failed['result']['available'])
        self.assertIsNone(failed['result'].get('working_context'))
        self.assertIn(text('no_reliable_record',
                           self.panel.language),
                      self.panel.connection.text())

    def test_stale_scope_miss_never_shows_active(self):
        from opencode_provider import OpenCodeProvider
        self._live_work()
        live = self._poll_render({'scope': 'conversation',
                                  'tracking_provider': 'opencode'},
                                 now=NOW_S)
        self.assertEqual(live['result'].get('presentation'),
                         'active_session')
        # Same trailing-submit settle as above: the held poll must find
        # a free slot so worker entry is deterministic, not load-raced.
        self.assertTrue(
            self.panel.provider_poller.drain(timeout=10))
        entered, release = self._hold(OpenCodeProvider)
        try:
            thread, _ = self._poll_thread(
                {'scope': 'conversation',
                 'tracking_provider': 'opencode'}, now=NOW_S)
            self.assertTrue(entered.wait(timeout=10))
            thread.join(timeout=10)
            self.assertFalse(thread.is_alive())
            # No drain while the worker is held: poll is non-blocking
            # and the advanced clock expires Live into honest stale.
            poller = self.panel.provider_poller
            out = poller.poll({'scope': 'conversation',
                               'tracking_provider': 'opencode'},
                              now=NOW_S + 10)
            self.panel.render(out['result'])
            self.app.processEvents()
            self.assertFalse(out['selection']['live'])
            self.assertTrue(out['selection']['stale'])
            self.assertIsNone(out['result'].get('presentation'))
            self.assertIn(self.panel.connection.text(),
                          [f"OpenCode · {text('waiting_available_task', self.panel.language)}",
                           f"OpenCode · {text('no_reliable_record', self.panel.language)}"])
        finally:
            release.set()
            self.assertTrue(
                self.panel.provider_poller.drain(timeout=10))

    def test_late_active_result_rejected(self):
        self._live_work()
        old = self._poll_render({'scope': 'conversation',
                                 'tracking_provider': 'opencode'},
                                now=NOW_S)
        self.assertEqual(old['result'].get('presentation'),
                         'active_session')
        self.panel.provider_poller.bump_generation()
        new = self._poll_render({'scope': 'global',
                                 'tracking_provider': 'opencode'},
                                now=NOW_S)
        self.assertGreater(new['generation'], old['generation'])
        self.panel.render(old['result'])
        self.app.processEvents()
        # The late active payload cannot repaint the newer panel.
        self.assertNotIn(text('active_session', self.panel.language),
                         self.panel.connection.text())

    def test_switch_to_codex_clears_active(self):
        self._attach(
            [{'id': 't1', 'working': True}],
            [make_session('ses_work', project='proj-w',
                          directory='/synthetic/work',
                          tokens=(100, 20, 5, 400, 7), cost=0.05,
                          updated=BASE_MS)],
            [make_message('m1', 'ses_work')],
            [make_part('p1', 'ses_work', created=BASE_MS - 100000)])
        codex = self._poll_render({'tracking_provider': 'codex'},
                                  active_title='t1', detection_valid=True)
        codex_total = self.panel.total.text()
        self.assertNotEqual(codex_total, 'N/A')
        self.panel.prefs['tracking_provider'] = 'opencode'
        self.panel.provider_poller.mark_used('opencode')
        self.panel.provider_poller.bump_generation()
        active = self._poll_render({'scope': 'conversation',
                                    'tracking_provider': 'opencode'},
                                   now=NOW_S)
        self.assertEqual(active['result'].get('presentation'),
                         'active_session')
        self.panel.prefs['tracking_provider'] = 'codex'
        self.panel.provider_poller.mark_used('codex')
        self.panel.provider_poller.bump_generation()
        back = self._poll_render({'tracking_provider': 'codex'},
                                 active_title='t1', detection_valid=True)
        self.assertIn('Codex', self.panel.connection.text())
        self.assertEqual(self.panel.total.text(), codex_total)
        self.assertNotIn('test-model', self.panel.model.text())
        self.assertNotIn('ses_work', self.panel.title.toolTip())

    def test_analytics_keeps_scope_view_for_active_session(self):
        self._live_work()
        self.panel.show()
        self.panel.open_analytics()
        self.app.processEvents()
        out = self._poll_render({'scope': 'conversation',
                                 'tracking_provider': 'opencode'},
                                now=NOW_S)
        result = out['result']
        self.assertEqual(result.get('presentation'), 'active_session')
        # Scope-mismatch proof at the data level: the live values are
        # tagged active_session, never relabeled as scoped aggregates.
        self.assertEqual(result['scope_identity']['scope_type'],
                         'active_session')
        self.assertEqual(result['scope_identity']['requested_scope'],
                         'conversation')
        window = self.panel.analytics_window
        self.assertEqual(window.subtitle.text(),
                         text('waiting_available_task',
                              self.panel.language))
        self.assertEqual(window.metrics.rowCount(), 0)
        self.assertIn('active_session', window.raw.toPlainText())
        self.assertEqual(window.history_note.text(),
                         text('waiting_available_task',
                              self.panel.language))


if __name__=='__main__':unittest.main()
