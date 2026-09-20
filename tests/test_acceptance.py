import json
import os
import sqlite3
import tempfile
import time
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from activity import ActivityState
from app_config import load_preferences
from pet import DesktopPet
from usage import CodexStore
from widget import Panel


class StoreFixture:
    """Minimal fake CODEX_HOME with per-thread models, projects, and mtimes."""

    def __init__(self, root):
        self.home = Path(root)
        self.rows = []
        self.projects = {}
        self.assignments = {}

    def add(self, thread, name, total, project_id=None, project_name=None,
            model='gpt-6-astra', working=False, mtime=None):
        path = self.home / f'{thread}.jsonl'
        usage = dict(input_tokens=total - 10, cached_input_tokens=0,
                     output_tokens=10, reasoning_output_tokens=0, total_tokens=total)
        events = [
            dict(type='session_meta', payload=dict(id=thread, timestamp='2026-09-19T12:00:00Z')),
            dict(type='turn_context', payload=dict(model=model, effort='high')),
        ]
        if working:
            events.append(dict(type='event_msg', timestamp='2026-09-19T12:00:01Z',
                               payload=dict(type='task_started')))
        events.append(dict(type='event_msg', timestamp='2026-09-19T12:00:02Z', payload=dict(
            type='token_count', info=dict(total_token_usage=usage, last_token_usage=usage,
                                          model_context_window=1000))))
        path.write_text(''.join(json.dumps(event) + '\n' for event in events), encoding='utf-8')
        stamp = time.time() if mtime is None else mtime
        os.utime(path, (stamp, stamp))
        self.rows.append(dict(id=thread, name=name, title='', cwd='', rollout_path=str(path),
            model=model, reasoning_effort='high', source='desktop', project_id=project_id,
            git_origin_url='', updated_at=int(stamp), archived=0))
        if project_id:
            self.assignments[thread] = {'projectId': project_id}
            self.projects.setdefault(project_id, {'name': project_name} if project_name else {})

    def finish(self):
        with closing(sqlite3.connect(self.home / 'state_1.sqlite')) as db:
            db.execute('''create table threads (
                id text, name text, title text, cwd text, rollout_path text, model text,
                reasoning_effort text, source text, project_id text, git_origin_url text,
                updated_at integer, archived integer)''')
            for row in self.rows:
                db.execute('insert into threads values (?,?,?,?,?,?,?,?,?,?,?,?)', tuple(row.values()))
            db.commit()
        state = {'local-projects': self.projects, 'thread-project-assignments': self.assignments}
        (self.home / '.codex-global-state.json').write_text(json.dumps(state), encoding='utf-8')
        return CodexStore(self.home)


class EdgeCaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.pref_patch = patch('widget.PREF_DIR', Path(self.temp.name))
        self.pref_patch.start()
        self.panels = []

    def tearDown(self):
        for panel in self.panels:
            panel.tray.hide()
            if panel.analytics_window:
                panel.analytics_window.close()
            if hasattr(panel, 'pet'):
                panel.pet.close()
            panel.closing = True
            panel.close()
            panel.deleteLater()
        self.app.processEvents()
        self.pref_patch.stop()
        self.temp.cleanup()

    def make_panel(self, prefs=None):
        if prefs is not None:
            Path(self.temp.name, 'settings.json').write_text(json.dumps(prefs), encoding='utf-8')
        panel = Panel(live=False)
        self.panels.append(panel)
        return panel

    def test_garbage_settings_file_falls_back_to_defaults(self):
        path = Path(self.temp.name) / 'settings.json'
        path.write_text('{not valid json\x00', encoding='utf-8')
        prefs = load_preferences(path)
        self.assertEqual(prefs['language'], 'zh_CN')
        self.assertEqual(prefs['currency'], 'CAD')
        self.assertEqual(prefs['scope'], 'conversation')

    def test_uia_unavailable_stays_conservative(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = StoreFixture(directory)
            fixture.add('a', 'A', 100, 'p-a', 'Alpha')
            data = fixture.finish().read(active_title='', activity_detection_valid=False)
        self.assertFalse(data['codex_activity']['active'])

    def test_crash_without_task_complete_goes_stale(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = StoreFixture(directory)
            fixture.add('a', 'A', 100, 'p-a', 'Alpha', working=True,
                        mtime=time.time() - 3600)
            store = fixture.finish()
            data = store.read(active_title='A', activity_detection_valid=True)
        self.assertFalse(data['codex_activity']['active'])

    def test_deleted_conversation_reports_unavailable(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = StoreFixture(directory)
            fixture.add('a', 'A', 100, 'p-a', 'Alpha')
            data = fixture.finish().read(pinned='gone', scope='conversation')
        self.assertEqual(data['status'], 'status_pinned_unavailable')
        self.assertNotIn('tokens', data)

    def test_missing_project_metadata_is_unavailable(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = StoreFixture(directory)
            fixture.add('a', 'A', 100)
            data = fixture.finish().read(pinned='a', scope='project')
        self.assertEqual(data['status'], 'status_project_unavailable')

    def test_extremely_large_token_values_render(self):
        from analytics import aggregate, normalize_usage
        panel = self.make_panel()
        panel.pet = DesktopPet(panel)
        panel.pet.activity_timer.stop()
        tokens = normalize_usage(dict(input_tokens=4_000_000_000_000, cached_input_tokens=0,
            output_tokens=1_000_000_000_000, reasoning_output_tokens=0,
            total_tokens=5_000_000_000_000))
        analytics = aggregate([dict(session='big', model='gpt-6-astra',
            timestamp='2026-09-16T12:00:00Z', event_id='big', tokens=tokens)])
        for style in ('full', 'compact'):
            panel.prefs['token_number_format'] = style
            panel.render(dict(title='Big', project='Big', model='gpt-6-astra', effort='high',
                mode='follow', scope='global', tokens=tokens, available=True, analytics=analytics,
                usd=100.0, raw_total={}, raw_last={}, count=1, session_names={'big': 'Big'}))
            self.app.processEvents()
            self.assertFalse(panel.grab().toImage().isNull(), style)
        self.assertIn('T', panel.total.text())

    def test_long_conversation_title_renders_safely(self):
        from analytics import aggregate, normalize_usage
        from pet import DesktopPet
        panel = Panel(live=False)
        try:
            panel.pet = DesktopPet(panel)
            panel.pet.activity_timer.stop()
            tokens = normalize_usage(dict(input_tokens=100, cached_input_tokens=0,
                output_tokens=10, reasoning_output_tokens=0, total_tokens=110))
            analytics = aggregate([dict(session='s', model='gpt-6-astra',
                timestamp='2026-09-16T12:00:00Z', event_id='s', tokens=tokens)])
            panel.render(dict(title='T' * 300, project='P', model='gpt-6-astra', effort='high',
                mode='follow', scope='conversation', tokens=tokens, available=True,
                analytics=analytics, usd=0.01, raw_total={}, raw_last={}, count=1,
                session_names={'s': 'S' * 300}))
            self.app.processEvents()
            self.assertFalse(panel.grab().toImage().isNull())
        finally:
            panel.pet.close()
            panel.tray.hide()
            panel.closing = True
            panel.close()
            panel.deleteLater()
            self.app.processEvents()

    def test_token_music_and_working_typing_priorities(self):
        state = ActivityState()
        state.key(100)
        state.sample(microphone=False, music=True, now=100)
        state.sample(microphone=False, music=True, now=100.6)
        self.assertEqual(state.state(100.6, codex_working=True), 'working')
        self.assertEqual(state.state(100.6), 'music')
        self.assertEqual(ActivityState().state(200), 'idle')


class CombinationTests(unittest.TestCase):
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
        self.panel.fx_data = dict(date='2026-09-18', source='Bank of Canada',
                                  rates={'CAD': 1.4, 'EUR': 1.2, 'CNY': 0.2})

    def tearDown(self):
        self.panel.pet.close()
        self.panel.tray.hide()
        if self.panel.analytics_window:
            self.panel.analytics_window.close()
        self.panel.closing = True
        self.panel.close()
        self.panel.deleteLater()
        self.app.processEvents()
        self.pref_patch.stop()
        self.temp.cleanup()

    def render_combo(self, language, scope, style, currency):
        from analytics import aggregate, normalize_usage
        tokens = normalize_usage(dict(input_tokens=120000, cached_input_tokens=90000,
            cache_write_input_tokens=0, output_tokens=18000,
            reasoning_output_tokens=7000, total_tokens=138000))
        analytics = aggregate([dict(session='s', model='gpt-6-astra',
            timestamp='2026-09-16T12:00:00Z', event_id='s', tokens=tokens)])
        self.panel.prefs.update(language=language, scope=scope,
                                token_number_format=style, currency=currency)
        self.panel.apply_language()
        data = dict(title='Combo task', project='Combo project', model='gpt-6-astra',
            effort='high', mode='follow', scope=scope, tokens=tokens, available=True,
            analytics=analytics, usd=2.19, context=42, context_tokens=84000,
            context_window=200000, raw_total=tokens, raw_last=tokens, notes=[],
            unknown=[], partial=False, count=1, session_names={'s': 'S'})
        self.panel.render(data)
        self.app.processEvents()
        return data

    def test_feature_combinations_render_cleanly(self):
        combos = [('zh_CN', 'global', 'compact', 'CAD', 'CA$'),
                  ('en', 'project', 'full', 'USD', '$'),
                  ('en', 'conversation', 'compact', 'EUR', '\u20ac')]
        seen = set()
        for language, scope, style, currency, symbol in combos:
            data = self.render_combo(language, scope, style, currency)
            self.assertFalse(self.panel.grab().toImage().isNull(), (language, scope))
            self.assertIn(symbol, self.panel.cost.text(), (language, currency))
            self.assertIn(currency, self.panel.cost_label.text())
            seen.add(self.panel.total.text())
        self.assertEqual(len(seen), 2)

    def test_resized_language_and_scope_switches(self):
        self.panel.show()
        self.panel.resize(400, 600)
        self.render_combo('zh_CN', 'project', 'compact', 'CAD')
        self.render_combo('en', 'global', 'full', 'USD')
        self.assertEqual((self.panel.width(), self.panel.height()), (400, 600))
        self.assertFalse(self.panel.grab().toImage().isNull())
        self.assertIn('Global', self.panel.scope_button.text())

    def test_currency_switch_keeps_tokens_but_moves_cost(self):
        usd = self.render_combo('en', 'project', 'compact', 'USD')['usd']
        total_usd, cost_usd = self.panel.total.text(), self.panel.cost.text()
        self.render_combo('en', 'project', 'compact', 'CNY')
        self.assertEqual(self.panel.total.text(), total_usd)
        self.assertNotEqual(self.panel.cost.text(), cost_usd)
        self.assertIn('CNY', self.panel.cost_label.text())
        self.assertEqual(self.panel.snapshot['usd'], usd)


if __name__ == '__main__':
    unittest.main()
