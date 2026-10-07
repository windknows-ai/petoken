"""2.0 project start presets and the continuation card."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication

import project_start
from project_start import (ContinuationCard, ContinuationWatcher, continuation, match_project,
                           opening_prompt, read_handoff_md, start_project)
from workbench_store import WorkbenchStore

APP = QApplication.instance() or QApplication([])


class FakePanel(QObject):
    def __init__(self, store=None):
        super().__init__()
        self.prefs = dict(language='en', launch_app='claude')
        self.store = store
        self.pet = None

    def workbench_store(self):
        return self.store


class ProjectStartTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name) / 'site'
        self.folder.mkdir()
        self.store = WorkbenchStore(Path(self.temp.name) / 'workbench.sqlite3')
        self.addCleanup(self.store.close)
        self.project = self.store.create_project('Site', str(self.folder))
        self.panel = FakePanel(self.store)

    def test_start_uses_preset_and_latest_note(self):
        self.store.set_preset(self.project['id'], 'codex', str(self.folder), '', 'gpt-5.5', 'high')
        self.store.add_handoff(self.project['id'], 'fix the logout button')
        built, started = [], []
        error = start_project(self.panel, self.store, self.project, starter=started.append,
                              builder=lambda *args, **kwargs: built.append((args, kwargs)) or ['argv'])
        self.assertIsNone(error)
        (app, folder, prompt), kwargs = built[0]
        self.assertEqual((app, Path(folder), kwargs), ('codex', self.folder, dict(model='gpt-5.5', effort='high')))
        self.assertIn('Look at the current state', prompt)
        self.assertTrue(prompt.endswith('My note from last time: fix the logout button'))
        self.assertEqual(started, [['argv']])
        self.assertIn(self.project['id'], self.panel.prefs['project_seen'])

    def test_start_without_preset_uses_the_project_folder_or_says_why_not(self):
        built = []
        start_project(self.panel, self.store, self.project, starter=lambda argv: None,
                      builder=lambda *args, **kwargs: built.append(args) or [])
        self.assertEqual((built[0][0], Path(built[0][1])), ('claude', self.folder))
        bare = self.store.create_project('No folder')
        self.assertEqual(start_project(self.panel, self.store, bare, starter=lambda argv: None),
                         'preset_need_folder')

    def test_opening_prompt(self):
        self.assertEqual(opening_prompt('do X', None, 'en'), 'do X')
        self.assertIn('note', opening_prompt('', dict(body=' note '), 'en'))

    def test_handoff_md_lines_without_markdown(self):
        (self.folder / 'HANDOFF.md').write_text('# Handoff\n\n<!-- hidden -->\n- **Next:** wire the goals\n'
                                                '---\n1. tests\n> careful\n* more\n', encoding='utf-8')
        self.assertEqual(read_handoff_md(str(self.folder)), ['Handoff', 'Next: wire the goals', 'tests', 'careful'])
        self.assertEqual(read_handoff_md(str(self.folder / 'missing')), [])

    def test_continuation_collects_where_you_left_off(self):
        self.assertIsNone(continuation(self.store, self.project))
        todo = self.store.create_todo('login page', self.project['id'])
        self.store.schedule_todo(todo['id'], 1, 'claude', str(self.folder), 'do it')
        self.store.update_schedule(todo['id'], state='failed')
        self.store.add_handoff(self.project['id'], 'halfway through the form')
        history = [dict(provider='codex', title='Other', project='api', finished_at=5),
                   dict(provider='claude', title='Form validation', project='site', finished_at=100)]
        info = continuation(self.store, self.project, history, now=100 + 7200)
        self.assertEqual(info['note'], 'halfway through the form')
        self.assertEqual(info['unfinished'], ['login page'])
        self.assertEqual(info['last_task']['title'], 'Form validation')
        card = ContinuationCard('en', info, now=100 + 7200)
        self.assertIn('Back to Site', card.title.text())
        self.assertIn('Last Claude Code task: Form validation (2 h ago)', card.lines.text())
        notes = []
        card.note_saved.connect(lambda project, body: notes.append(body))
        card.edit.setText('next: the submit button')
        card._save()
        self.assertEqual(notes, ['next: the submit button'])
        card.deleteLater()

    def test_watcher_shows_once_when_you_come_back(self):
        watcher = ContinuationWatcher(self.panel)
        task = dict(provider_id='claude', task_key='s1', display=dict(project='site'))
        self.assertIsNone(watcher.observe([], now=0))              # Baseline.
        self.assertEqual(watcher.observe([task], now=10)['id'], self.project['id'])
        self.assertIsNone(watcher.observe([task], now=20))          # Same task: nothing new.
        other = dict(task, task_key='s2')
        self.assertIsNone(watcher.observe([task, other], now=30))   # Worked on it just now.
        late = dict(task, task_key='s3')
        self.assertIsNotNone(watcher.observe([late], now=30 + project_start.RETURN_GAP_S))
        self.panel.prefs['continuation_card'] = False
        self.assertIsNone(watcher.observe([dict(task, task_key='s4')], now=10 ** 6))

    def test_a_task_waking_up_again_is_not_new(self):
        watcher = ContinuationWatcher(self.panel)
        task = dict(provider_id='claude', task_key='s1', display=dict(project='other'))
        watcher.observe([], now=0)
        watcher.observe([task], now=10)
        self.assertEqual((watcher.fresh, watcher.new), (1, 1))
        watcher.observe([], now=20)                 # Went quiet...
        watcher.observe([task], now=30)             # ...and busy again: back, but not new.
        self.assertEqual((watcher.fresh, watcher.new), (1, 0))

    def test_match_project_by_name_or_folder(self):
        self.assertEqual(match_project([self.project], 'SITE')['id'], self.project['id'])
        self.assertIsNone(match_project([self.project], 'api'))
        self.assertIsNone(match_project([self.project], ''))


class NoteBoxTests(unittest.TestCase):
    def test_note_stands_out_and_can_be_deleted_or_browsed(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        store = WorkbenchStore(Path(temp.name) / 'workbench.sqlite3')
        self.addCleanup(store.close)
        project = store.create_project('Site')
        store.add_handoff(project['id'], 'older note')
        store.add_handoff(project['id'], 'fix the logout button')
        info = continuation(store, project)
        card = ContinuationCard('en', info)
        self.assertFalse(card.note_box.isHidden())
        self.assertEqual(card.note_text.text(), 'fix the logout button')
        deleted, history = [], []
        card.note_deleted.connect(lambda record, note_id: deleted.append(note_id))
        card.history.connect(history.append)
        card.delete_button.click()
        card.history_button.click()
        self.assertEqual(deleted, [info['note_id']])
        self.assertEqual(history[0]['id'], project['id'])
        card.set_note(None)
        self.assertTrue(card.note_box.isHidden())
        card.deleteLater()
        dialog = project_start.HandoffHistory(None, 'en', store, project)
        self.assertEqual(dialog.listing.count(), 2)
        self.assertTrue(dialog.listing.item(0).text().endswith('fix the logout button'))
        dialog.listing.setCurrentRow(0)
        dialog.delete_selected()
        self.assertEqual([n['body'] for n in store.list_handoffs(project['id'])], ['older note'])
        dialog.deleteLater()


class PresetDialogTests(unittest.TestCase):
    def test_project_folder_is_used_not_a_stale_preset_folder(self):
        panel = FakePanel()
        project = dict(id='p', name='Site', directory='D:/work/new-folder')
        with patch('quick_launch.launch_options', return_value=[]):
            dialog = project_start.ProjectPresetDialog(None, panel, project, dict(
                provider_id='claude', folder='D:/work/old-folder', prompt='', model='', effort=''))
        self.assertTrue(dialog.folder.isHidden())
        self.assertIn('new-folder', dialog.folder_label.text())
        self.assertEqual(dialog.folder.currentText(), 'D:/work/new-folder')
        dialog.deleteLater()

    def test_dialog_has_no_time_and_keeps_the_preset(self):
        panel = FakePanel()
        project = dict(id='p', name='Site', directory='D:/site')
        with patch('quick_launch.launch_options', return_value=[]):
            dialog = project_start.ProjectPresetDialog(None, panel, project, dict(
                provider_id='codex', folder='D:/site', prompt='go', model='', effort=''))
            self.assertTrue(dialog.when.isHidden())
            self.assertTrue(dialog.codex.isChecked())
            values = dialog.values()
        self.assertEqual((values['prompt'], values['provider_id']), ('go', 'codex'))
        dialog.deleteLater()


if __name__ == '__main__':
    unittest.main()
