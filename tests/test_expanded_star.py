"""Actual Expanded Star boundaries, task truth and native Qt lifecycle."""
from threading import Event
import unittest
from unittest.mock import patch

from PySide6.QtCore import Qt, QEvent, QPoint, QTimer
from PySide6.QtGui import QKeyEvent
from PySide6.QtTest import QTest

import pet_geometry
from localization import scope_text, text
from tests import test_ui as ui


class ExpandedStarTests(unittest.TestCase):
    setUpClass = classmethod(ui.TaskPanelManagerTests.setUpClass.__func__)
    setUp = ui.TaskPanelManagerTests.setUp
    tearDown = ui.TaskPanelManagerTests.tearDown

    def apply(self, tasks, generation=None, preference='auto', pet=ui._CENTER_PET_RECT,
              screen=ui._SCREEN_RECT, language='en'):
        self.manager.apply_snapshot(tasks, generation=generation, preference=preference,
                                    language=language, pet_rect=pet, screen_rect=screen)

    def tick(self, stamp, pet=ui._CENTER_PET_RECT, screen=ui._SCREEN_RECT):
        self.manager.tick_visual(stamp, pet_rect=pet, screen_rect=screen)

    def positions(self):
        return {key: (orb.x(), orb.y()) for key, orb in self.manager._windows.items()
                if key not in self.manager._ring_staged}

    def warm(self, tasks=None, pet=ui._CENTER_PET_RECT):
        tasks = tasks or [ui._codex_entry(str(i)) for i in range(3)]
        self.apply(tasks, pet=pet)
        stamp = 100.0
        self.tick(stamp, pet)
        for _ in range(75):
            stamp += .04
            self.tick(stamp, pet)
        return tasks, stamp

    def assert_frame(self, before, pet=ui._CENTER_PET_RECT, screen=ui._SCREEN_RECT):
        after = self.positions()
        for key in before.keys() & after.keys():
            self.assertEqual(before[key], after[key], key)
        self.assertTrue(self.manager._nominal_valid(after, pet, screen))

    def assert_first_resume(self, before, stamp, pet=ui._CENTER_PET_RECT):
        self.tick(stamp + 500, pet)
        self.assert_frame(before, pet)
        self.tick(stamp + 500.04, pet)
        after = self.positions()
        for key in before.keys() & after.keys():
            self.assertLessEqual(sum(abs(a-b) for a,b in zip(before[key],after[key])),16)
        self.assertTrue(self.manager._nominal_valid(after, pet, ui._SCREEN_RECT))

    def test_open_refresh_collapse_and_first_resume_exact_pixels(self):
        tasks, stamp = self.warm()
        before, phase = self.positions(), self.manager._ring_t
        key=('codex','0')
        orb=self.manager.window_for(key)
        slot, number = self.manager.slot_for(key), self.manager.label_number_for(key)
        self.manager.orb_activated(key)
        card=self.manager.detail_window
        self.assertTrue(card.isVisible())
        self.assert_frame(before)
        tasks[0]['presentation']['tokens']['total_tokens']=999
        self.apply(tasks, generation=2)
        self.assert_frame(before)
        self.assertEqual(card._rows['total'][1].full_text,'999 Tokens')
        self.tick(stamp + 400)
        self.assert_frame(before)
        self.assertEqual(self.manager._ring_t,phase)
        self.manager.collapse_detail()
        self.assert_frame(before)
        self.assertIs(self.manager.window_for(key),orb)
        self.assertEqual((self.manager.slot_for(key),self.manager.label_number_for(key)),(slot,number))
        self.assert_first_resume(before,stamp)

    def test_one_card_same_star_toggle_other_provider_task_local(self):
        a=ui._codex_entry('private-id-A',total=111,project='Alpha')
        b=ui._opencode_entry('private-id-B',total=222,model='Other model')
        self.apply([a,b])
        with patch.object(self.panel.provider_poller,'poll',side_effect=AssertionError('Read')), \
             patch.object(self.panel,'persist',side_effect=AssertionError('Persist')):
            self.manager.orb_activated(('codex','private-id-A'))
            self.assertEqual(self.manager.detail_window._rows['total'][1].full_text,'111 Tokens')
            self.manager.orb_activated(('opencode','private-id-B'))
            card=self.manager.detail_window
            self.assertEqual(card.provider_id,'opencode')
            self.assertEqual(card._rows['total'][1].full_text,'222')
            self.assertNotIn('private-id',card.panel_text())
            self.assertNotIn('111',card.panel_text())
            self.manager.orb_activated(('opencode','private-id-B'))
            self.assertIsNone(self.manager.expanded_identity)
            self.assertFalse(card.isVisible())

    def test_toggles_survive_pause_and_resume_from_exact_pixels(self):
        tasks,stamp=self.warm()
        before=self.positions()
        self.manager.orb_activated(('codex','0'))
        for motion in (False,True,False):
            self.panel.prefs['pet_motion']=motion
            self.manager.sync_motion()
            self.apply(tasks)
            self.tick(stamp+50)
            self.assert_frame(before)
            self.assertEqual(self.manager.expanded_identity,('codex','0'))
        self.manager.collapse_detail()
        self.assert_frame(before)
        self.assert_first_resume(before,stamp)

    def test_arc_and_active_parking_freeze_and_resume(self):
        pet=ui._PET_RECT
        tasks,stamp=self.warm(pet=pet)
        self.panel.prefs['pet_motion']=False
        self.apply(tasks,pet=pet)
        self.tick(stamp+.04,pet)
        self.tick(stamp+.08,pet)
        before=self.positions()
        self.manager.orb_activated(('codex','0'))
        self.assertIsNotNone(self.manager._park_blend)
        elapsed=self.manager._park_blend['t']
        self.tick(stamp+100,pet)
        self.assert_frame(before,pet)
        self.assertEqual((self.manager._park_blend or {}).get('t'),elapsed)
        self.manager.collapse_detail()
        self.assert_frame(before,pet)
        self.assert_first_resume(before,stamp,pet)

    def test_newcomer_and_other_retire_defer_geometry(self):
        tasks,stamp=self.warm()
        before=self.positions()
        self.manager.orb_activated(('codex','0'))
        changed=[tasks[0],tasks[1],ui._opencode_entry('new')]
        self.apply(changed,generation=2)
        self.assert_frame(before)
        self.assertEqual(self.manager.expanded_identity,('codex','0'))
        self.assertIn(('opencode','new'),self.manager._ring_staged)
        self.assertFalse(self.manager.window_for(('opencode','new')).isVisible())
        before=self.positions()
        self.manager.collapse_detail()
        self.assert_frame(before)
        self.assert_first_resume(before,stamp)

    def test_filter_retire_and_stale_close_before_star(self):
        for reason in ('filter','retire','stale'):
            with self.subTest(reason=reason):
                tasks=[ui._codex_entry('a'),ui._opencode_entry('b')]
                self.apply(tasks)
                key=('codex','a')
                self.manager.orb_activated(key)
                card=self.manager.detail_window
                orb=self.manager.window_for(key)
                original_close=orb.close
                def close():
                    self.assertIsNone(self.manager.expanded_identity)
                    self.assertFalse(card.isVisible())
                    return original_close()
                with patch.object(orb,'close',side_effect=close):
                    if reason=='filter':
                        self.apply([tasks[1]],preference='opencode')
                    else:
                        self.apply([] if reason=='stale' else [tasks[1]])
                self.assertIsNone(self.manager.expanded_identity)
                self.assertIsNone(self.manager.window_for(key))

    def test_old_generation_cannot_change_open_detail(self):
        tasks,_=self.warm()
        self.apply(tasks,generation=10)
        self.manager.orb_activated(('codex','0'))
        before=self.positions()
        card=self.manager.detail_window
        self.apply([],generation=9)
        self.assert_frame(before)
        self.assertIs(self.manager.detail_window,card)
        self.assertEqual(self.manager.expanded_identity,('codex','0'))

    def test_hide_restore_and_shutdown_are_terminal(self):
        tasks,stamp=self.warm()
        self.manager.orb_activated(('codex','0'))
        before=self.positions()
        card=self.manager.detail_window
        self.manager.set_visible(False)
        self.assertIsNone(self.manager.expanded_identity)
        self.assertFalse(card.isVisible())
        self.manager.set_visible(True)
        self.assertIsNone(self.manager.expanded_identity)
        self.assert_frame(before)
        self.assert_first_resume(before,stamp)
        self.manager.orb_activated(('codex','0'))
        with patch.object(self.manager.window_for(('codex','0')),'close',wraps=self.manager.window_for(('codex','0')).close) as close:
            self.manager.shutdown()
            close.assert_called_once()
        self.assertIsNone(self.manager.detail_window)
        self.manager.shutdown()
        self.apply(tasks,generation=100)
        self.manager.orb_activated(('codex','0'))
        self.assertEqual(self.manager.window_count(),0)

    def test_pending_worker_cannot_commit_while_expanded(self):
        tasks,stamp=self.warm(pet=ui._PET_RECT)
        gate,started=Event(),Event()
        def plan(inputs):
            started.set()
            gate.wait(3)
            return None
        self.manager._live_armed=lambda:True
        try:
            with patch('widget._plan_parking_routes',side_effect=plan):
                self.panel.prefs['pet_motion']=False
                self.apply(tasks,pet=ui._PET_RECT)
                self.assertTrue(started.wait(1))
                self.manager.motion_timer.stop()
                before=self.positions()
                self.manager.orb_activated(('codex','0'))
                gate.set()
                self.assertTrue(self.manager._park_plan_job[2].wait(1))
                self.tick(stamp+500,ui._PET_RECT)
                self.assert_frame(before,ui._PET_RECT)
                self.assertIsNone(self.manager._park_plan_request)
                self.assertFalse(self.manager._poll_park_plan(ui._PET_RECT,ui._SCREEN_RECT))
                self.manager.collapse_detail()
                self.assert_frame(before,ui._PET_RECT)
                self.assert_first_resume(before,stamp,ui._PET_RECT)
        finally:
            gate.set()
            self.manager.motion_timer.stop()
            self.manager._live_armed=lambda:False

    def test_geometry_change_explicitly_collapses_and_replans(self):
        tasks,stamp=self.warm()
        self.manager.orb_activated(('codex','0'))
        before=self.positions()
        moved=(834,375,272,330)
        self.tick(stamp+.04,moved)
        self.assertIsNone(self.manager.expanded_identity)
        self.assert_frame(before,moved)

    def test_card_language_topmost_format_keep_anchor_and_visibility(self):
        task=ui._codex_entry('a',total=1234567,model=None)
        self.apply([task])
        self.manager.orb_activated(('codex','a'))
        before=self.positions()
        card=self.manager.detail_window
        self.panel.prefs.update(language='zh_CN',token_number_format='full')
        self.manager.retranslate('zh_CN')
        self.assertEqual(card._rows['model'][1].full_text,text('unknown','zh_CN'))
        self.assertEqual(card.collapse_button.toolTip(),text('task_collapse','zh_CN'))
        position=(card.x(),card.y())
        for topmost in (False,True):
            self.manager.apply_topmost(topmost)
            self.assertEqual(bool(card.windowFlags()&Qt.WindowStaysOnTopHint),topmost)
            self.assertTrue(card.isVisible())
            self.assertEqual((card.x(),card.y()),position)
            self.assert_frame(before)

    def test_actual_keyboard_star_hub_entry_and_escape(self):
        task=ui._codex_entry('a')
        self.panel.prefs['language']='en'
        self.panel.render(dict(provider_id='codex',available=False,scope='global',
                               generation=1,preference='auto',active_tasks=[task]))
        self.panel.show()
        self.app.processEvents()
        self.assertEqual(self.panel.tasks_button.text(),'Active tasks · 1 ▾')
        self.assertIn('Codex',self.panel.task_provenance.full_text)
        self.panel.refresh_task_menu()
        action=self.panel.task_menu.actions()[0]
        action.trigger()
        self.assertEqual(self.manager.expanded_identity,('codex','a'))
        self.assertTrue(self.manager.detail_window.collapse_button.hasFocus())
        QTest.keyClick(self.manager.detail_window.collapse_button,Qt.Key_Escape)
        self.app.processEvents()
        self.assertIsNone(self.manager.expanded_identity)
        orb=self.manager.window_for(('codex','a'))
        self.assertEqual(orb.focusPolicy(),Qt.StrongFocus)
        self.assertIn('Active task',orb.accessibleName())
        event=QKeyEvent(QEvent.KeyPress,Qt.Key_Return,Qt.NoModifier)
        orb.keyPressEvent(event)
        self.assertEqual(self.manager.expanded_identity,('codex','a'))

    def test_unknown_zero_partial_source_notes_and_opencode_variant(self):
        task=ui._opencode_entry('secret',total=0,tokens=(0,0,0,0,0),cost=0,model=None)
        task['presentation'].update(effort='recorded-variant',partial=True,source_available=False,
                                    notes=['note_initial_carry','private_untranslated_note'])
        self.apply([task])
        self.manager.orb_activated(('opencode','secret'))
        card=self.manager.detail_window
        self.assertEqual(card._rows['total'][1].full_text,'0')
        self.assertEqual(card._rows['cost'][1].full_text,'0.00')
        self.assertEqual(card._rows['model'][1].full_text,'Unknown')
        self.assertEqual(card._rows['effort'][0].text(),'Model variant')
        self.assertNotIn('context',card._rows)
        self.assertIn('Partial'.lower(),card.panel_text().lower())
        self.assertIn('source unavailable',card.warning.text())
        self.assertNotIn('private_untranslated_note',card.panel_text())
        self.assertNotIn('note_initial_carry',card.panel_text())
        task['presentation']['version']=None
        self.apply([task])
        self.assertEqual(card.provider_label.toolTip(),'')

    def test_long_plain_text_and_short_screen_clamp(self):
        task=ui._codex_entry('secret',project='<b>project</b>'*30,model='<i>model</i>'*30)
        screen=(0,0,1199,279)
        pet=(400,40,272,160)
        self.apply([task],pet=pet,screen=screen)
        before=self.positions()
        self.manager.orb_activated(('codex','secret'))
        self.app.processEvents()
        card=self.manager.detail_window
        self.assertLessEqual(card.height(),280)
        self.assertGreaterEqual(card.x(),0)
        self.assertGreaterEqual(card.y(),0)
        self.assertLessEqual(card.x()+card.width(),1200)
        self.assertLessEqual(card.y()+card.height(),280)
        self.assertEqual(card.project_label.textFormat(),Qt.PlainText)
        self.assertEqual(card._rows['model'][1].textFormat(),Qt.PlainText)
        self.assertIn('<i>model</i>',card._rows['model'][1].toolTip())
        self.assertTrue(card.collapse_button.isVisible())
        self.assert_native_value_render(card,'model')
        self.assert_frame(before,pet,screen)

    def test_hide_after_deferred_add_replans_before_resume(self):
        tasks,stamp=self.warm()
        self.manager.orb_activated(('codex','0'))
        self.apply(tasks+[ui._codex_entry('new')])
        before=self.positions()
        self.manager.set_visible(False)
        self.assert_frame(before)
        self.manager.set_visible(True)
        self.assert_frame(before)
        self.assert_first_resume(before,stamp)

    def test_active_blend_pause_keeps_elapsed_and_first_resume(self):
        tasks,stamp=self.warm()
        self.apply(tasks+[ui._codex_entry('new')])
        self.assertTrue(self.manager._ring_blend or self.manager._park_blend)
        before=self.positions()
        blend=self.manager._ring_blend or self.manager._park_blend
        elapsed=blend['t']
        self.manager.orb_activated(('codex','0'))
        self.tick(stamp+100)
        self.assert_frame(before)
        self.assertEqual(blend['t'],elapsed)
        self.manager.collapse_detail()
        self.assert_frame(before)
        self.assert_first_resume(before,stamp)

    def test_hub_mixed_count_and_opencode_motion_are_provider_independent(self):
        self.manager._live_armed=lambda:True
        self.panel.prefs['language']='en'
        try:
            self.panel.render(dict(provider_id='opencode',available=False,scope='project',
                                   generation=1,preference='auto',
                                   active_tasks=[ui._codex_entry('a'),ui._opencode_entry('b')]))
            self.assertTrue(self.manager.motion_timer.isActive())
            self.assertEqual(self.panel.tasks_button.text(),'Active tasks · 2 ▾')
            self.assertIn('OpenCode',self.panel.task_provenance.full_text)
            self.assertIn('Project',self.panel.task_provenance.full_text)
            self.panel.refresh_task_menu()
            self.assertEqual(len(self.panel.task_menu.actions()),2)
        finally:
            self.manager.motion_timer.stop()
            self.manager._live_armed=lambda:False

    def test_motion_off_pet_move_immediately_invalidates_detail(self):
        self.panel.pet.move(500,300)
        self.panel.pet.show()
        self.panel.prefs['pet_motion']=False
        pet,screen=self.manager._anchor()
        tasks=[ui._codex_entry('a'),ui._codex_entry('b')]
        self.apply(tasks,pet=pet,screen=screen)
        self.manager.orb_activated(('codex','a'))
        self.assertEqual(self.manager.expanded_identity,('codex','a'))
        before=self.positions()
        self.panel.pet.move(self.panel.pet.x()+10,self.panel.pet.y())
        self.assertIsNone(self.manager.expanded_identity)
        new_pet,new_screen=self.manager._anchor()
        self.assert_frame(before,new_pet,new_screen)

    def test_topmost_snapshot_while_open_preserves_visible_pixels(self):
        tasks,_=self.warm()
        self.manager.orb_activated(('codex','0'))
        before=self.positions()
        for topmost in (False,True):
            self.panel.prefs['always_on_top']=topmost
            self.apply(tasks)
            self.assert_frame(before)
            self.assertTrue(all(orb.isVisible() for orb in self.manager._windows.values()))
            self.assertTrue(self.manager.detail_window.isVisible())

    @staticmethod
    def luminance(color):
        values=[color.redF(),color.greenF(),color.blueF()]
        linear=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in values]
        return sum(v*w for v,w in zip(linear,(.2126,.7152,.0722)))

    def assert_native_value_render(self, card, key):
        value=card._rows[key][1]
        card.scroll.ensureWidgetVisible(value)
        self.app.processEvents()
        self.assertGreater(value.width(),20,key)
        self.assertTrue(value.text(),key)
        image=card.grab().toImage()
        dpr=image.devicePixelRatio()
        body=card.scroll.widget()
        viewport=card.scroll.viewport()
        blank=viewport.mapTo(card,QPoint(viewport.width()-3,2))
        background=image.pixelColor(round(blank.x()*dpr),round(blank.y()*dpr))
        foreground=value.palette().windowText().color()
        light,dark=sorted((self.luminance(background),self.luminance(foreground)),reverse=True)
        contrast=(light+.05)/(dark+.05)
        self.assertGreaterEqual(contrast,4.5,(key,background.name(),foreground.name(),body.autoFillBackground()))
        origin=value.mapTo(card,QPoint(0,0))
        region=image.copy(round(origin.x()*dpr),round(origin.y()*dpr),
                          round(value.width()*dpr),round(value.height()*dpr))
        glyph_pixels=0
        for y in range(region.height()):
            for x in range(region.width()):
                color=region.pixelColor(x,y)
                light,dark=sorted((self.luminance(color),self.luminance(background)),reverse=True)
                if (light+.05)/(dark+.05)>=4.5:
                    glyph_pixels+=1
        self.assertGreater(glyph_pixels,4,(key,value.text(),background.name()))
        return contrast

    def test_native_card_render_contrast_both_languages_providers_cases(self):
        from pathlib import Path
        captures=Path(r'D:\Documents\ChatGPT\petoken-takeover-backups\2026-10-03-resume')
        for language in ('en','zh_CN'):
            for provider in ('codex','opencode'):
                for case in ('known','zero','unknown','partial'):
                    with self.subTest(language=language,provider=provider,case=case):
                        if provider=='codex':
                            task=ui._codex_entry('render-proof',total=0 if case=='zero' else 12345)
                        else:
                            task=ui._opencode_entry('render-proof',total=0 if case=='zero' else 12345,
                                                    cost=0 if case=='zero' else .125)
                        task['presentation']['effort']='high' if provider=='codex' else 'recorded-variant'
                        if case=='zero':
                            task['presentation']['tokens']={k:0 for k in task['presentation']['tokens']}
                        if case=='unknown':
                            task['presentation']['model']=None
                            task['presentation']['tokens']={k:None for k in task['presentation']['tokens']}
                            task['presentation']['effort']=None
                            task['presentation'].update(context=None,cost_amount=None,available=False)
                        if case=='partial':
                            task['presentation'].update(partial=True,source_available=False)
                        self.apply([task],language=language)
                        self.manager.orb_activated((provider,'render-proof'))
                        card=self.manager.detail_window
                        self.app.processEvents()
                        name=f'8-card-{language}-{provider}-{case}.png'
                        self.assertTrue(card.grab().save(str(captures/name)))
                        for key in ('total','model','effort'):
                            self.assert_native_value_render(card,key)
                        if provider=='opencode':
                            self.assert_native_value_render(card,'cost')
                        self.manager.collapse_detail()

    def test_rapid_native_hub_menu_escape_collapses_without_hiding_scene(self):
        task=ui._codex_entry('native-menu-proof')
        self.panel.prefs['language']='en'
        self.panel.render(dict(provider_id='codex',available=False,scope='global',
                               generation=1,preference='auto',active_tasks=[task]))
        self.panel.show()
        self.panel.activateWindow()
        self.panel.tasks_button.setFocus()
        self.assertTrue(QTest.qWaitForWindowActive(self.panel,1000))
        self.app.processEvents()
        key=('codex','native-menu-proof')
        orb=self.manager.window_for(key)
        before=self.positions()
        chosen=[]
        def choose():
            menu=self.panel.task_menu
            menu_visible=menu.isVisible()
            QTest.keyClick(menu,Qt.Key_Down)
            QTest.keyClick(menu,Qt.Key_Return)
            card=self.manager.detail_window
            chosen.append((menu_visible,self.manager.expanded_identity,
                           card.collapse_button.hasFocus()))
            # Deliver the next real key before another Qt/OS activation turn.
            QTest.keyClick(card.collapse_button,Qt.Key_Escape)
        QTimer.singleShot(0,choose)
        self.panel.tasks_button.setFocus()
        QTest.keyClick(self.panel.tasks_button,Qt.Key_Space)
        self.app.processEvents()
        self.assertEqual(chosen,[(True,key,True)])
        self.assertIsNone(self.manager.expanded_identity)
        self.assertTrue(self.panel.isVisible())
        self.assertTrue(self.manager._visible)
        self.assertTrue(orb.isVisible())
        self.assertIs(self.manager.window_for(key),orb)
        self.assertEqual(self.positions(),before)
        self.panel.activateWindow()
        self.panel.tasks_button.setFocus()
        self.assertTrue(QTest.qWaitForWindowActive(self.panel,1000))
        QTest.keyClick(self.panel.tasks_button,Qt.Key_Escape)
        self.app.processEvents()
        self.assertFalse(self.manager._visible)
        self.assertFalse(orb.isVisible())
        self.assertTrue(not self.panel.isVisible() or self.panel.isMinimized())

    def test_unknown_quota_missing_reset_clears_and_zero_is_valid(self):
        self.panel.show()
        now=__import__('time').time()
        self.panel.quota_provider='codex'
        self.panel.snapshot=dict(provider_id='codex')
        def quota(reset):
            return dict(sampled=now,limits=dict(primary=dict(usedPercent=30,windowDurationMins=300,resetsAt=reset)))
        self.panel.receive_limits(quota(now+300))
        self.assertTrue(self.panel.five.reset.isVisible())
        self.panel.receive_limits(quota(None))
        self.assertFalse(self.panel.five.reset.isVisible())
        self.assertEqual(self.panel.five.reset.text(),'')
        self.panel.receive_limits(quota(0))
        self.assertTrue(self.panel.five.reset.isVisible())
        self.panel.receive_limits(dict(sampled=now,limits={}))
        self.assertEqual(self.panel.five.value.text(),'N/A')
        self.assertEqual(self.panel.five.reset.text(),'')
        self.assertFalse(self.panel.five.reset.isVisible())
        self.assertEqual(scope_text([], 'en'),scope_text('conversation','en'))
        self.assertEqual(scope_text({}, 'zh_CN'),scope_text('conversation','zh_CN'))


if __name__=='__main__':
    unittest.main()
