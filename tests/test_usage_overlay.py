"""V1.5 usage overlay, Claude status-line bridge, app presence and star names."""
import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

# Hermetic Claude lane: no real ~/.claude or bridge snapshots in tests.
os.environ.setdefault('PETOKEN_CLAUDE_HOME', os.path.join(
    tempfile.gettempdir(), 'petoken-tests-no-claude-home'))

from PySide6.QtWidgets import QApplication

import claude_statusline as bridge
from claude_usage import ClaudeStore
from desktop import classify_process
from tests.test_claude_usage import ClaudeHome, assistant
import usage_overlay as overlay

NOW = 1_791_000_000.0


def snapshot(session='s1', written=NOW - 60, five=(40.0, NOW + 3600),
             week=(25.0, NOW + 86400), context=12.0, size=200_000):
    data = dict(session_id=session, written_at=written, model='claude-opus-5-5',
                context_window_size=size, context_used_percentage=context)
    data['five_hour'] = (None if five is None
                         else dict(used_percentage=five[0], resets_at=five[1]))
    data['seven_day'] = (None if week is None
                         else dict(used_percentage=week[0], resets_at=week[1]))
    return data


class BridgeSettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name) / 'claude'
        self.home.mkdir()
        self.script = Path(self.temp.name) / 'CodexWisp' / bridge.SCRIPT_NAME

    def tearDown(self):
        self.temp.cleanup()

    def settings(self):
        return json.loads((self.home / 'settings.json').read_text(encoding='utf-8'))

    def test_enable_keeps_other_settings_and_backs_up_first(self):
        (self.home / 'settings.json').write_text(
            json.dumps(dict(model='haiku', theme='dark')), encoding='utf-8')
        self.assertEqual(bridge.enable(self.home, self.script), 'on')
        data = self.settings()
        self.assertEqual((data['model'], data['theme']), ('haiku', 'dark'))
        self.assertIn(bridge.SCRIPT_NAME, data['statusLine']['command'])
        self.assertTrue(self.script.read_text(encoding='utf-8-sig').startswith(
            f'# {bridge.MARKER}'))
        backups = list(self.home.glob('settings.json.petoken-backup-*'))
        self.assertEqual(len(backups), 1)
        self.assertNotIn('statusLine', json.loads(backups[0].read_text(encoding='utf-8')))

    def test_disable_removes_only_our_status_line(self):
        bridge.enable(self.home, self.script)
        self.assertEqual(bridge.disable(self.home), 'off')
        self.assertNotIn('statusLine', self.settings())

    def test_a_custom_status_line_is_never_replaced_or_removed(self):
        custom = dict(statusLine=dict(type='command', command='my-line.sh'))
        (self.home / 'settings.json').write_text(json.dumps(custom), encoding='utf-8')
        self.assertEqual(bridge.enable(self.home, self.script), 'foreign')
        self.assertEqual(bridge.disable(self.home), 'foreign')
        self.assertEqual(self.settings(), custom)
        self.assertFalse(list(self.home.glob('*.petoken-backup-*')))

    def test_unreadable_settings_are_left_alone(self):
        (self.home / 'settings.json').write_text('{ not json', encoding='utf-8')
        self.assertEqual(bridge.enable(self.home, self.script), 'unreadable')
        self.assertEqual((self.home / 'settings.json').read_text(encoding='utf-8'), '{ not json')

    def test_missing_settings_file_is_created(self):
        self.assertEqual(bridge.state(self.home), 'off')
        self.assertEqual(bridge.enable(self.home, self.script), 'on')

    def test_isolated_claude_home_isolates_snapshots(self):
        with patch.dict(os.environ, {'PETOKEN_CLAUDE_HOME': str(self.home)}):
            os.environ.pop('PETOKEN_CLAUDE_STATUS_DIR', None)
            self.assertEqual(bridge.status_dir(), self.home / 'petoken-status')


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, data):
        (self.folder / f'{name}.json').write_text(
            data if isinstance(data, str) else json.dumps(data), encoding='utf-8')

    def test_newest_snapshot_gives_each_window_in_codex_shape(self):
        self.write('old', snapshot('old', written=NOW - 600, five=(10.0, NOW + 100)))
        self.write('new', snapshot('new', written=NOW - 30, five=(55.0, NOW + 200), week=None))
        snaps = bridge.read_snapshots(self.folder, NOW)
        self.assertEqual([s['session_id'] for s in snaps], ['new', 'old'])
        limits, sampled = bridge.account_limits(snaps)
        self.assertEqual(limits['primary'], dict(windowDurationMins=300, usedPercent=55.0,
                                                 resetsAt=NOW + 200))
        # The weekly window comes from the newest snapshot that has one.
        self.assertEqual(limits['secondary']['usedPercent'], 25.0)
        self.assertEqual(sampled, NOW - 30)

    def test_invalid_expired_and_old_data_is_dropped(self):
        self.write('expired', snapshot('expired', five=(50.0, NOW - 1), week=(150.0, NOW + 9)))
        self.write('ancient', snapshot('ancient', written=NOW - bridge.SNAPSHOT_MAX_AGE_S - 1))
        self.write('broken', '{nope')
        self.write('flag', dict(written_at=True))
        snaps = bridge.read_snapshots(self.folder, NOW)
        self.assertEqual([s['session_id'] for s in snaps], ['expired'])
        self.assertEqual(bridge.account_limits(snaps), (None, None))

    def test_missing_folder_means_no_data(self):
        self.assertEqual(bridge.read_snapshots(self.folder / 'none', NOW), [])


@unittest.skipUnless(os.name == 'nt' and shutil.which('powershell'), 'Windows PowerShell')
class BridgeScriptTests(unittest.TestCase):
    def test_script_keeps_numbers_only_and_prints_a_line(self):
        with tempfile.TemporaryDirectory() as root:
            script = Path(root) / bridge.SCRIPT_NAME
            script.write_text(bridge._SCRIPT, encoding='utf-8-sig')
            payload = dict(session_id='abc-1', cwd='C:/secret/client',
                           transcript_path='C:/secret/t.jsonl',
                           model=dict(id='claude-opus-5-5', display_name='Opus'),
                           rate_limits=dict(five_hour=dict(used_percentage=20, resets_at=NOW)),
                           context_window=dict(context_window_size=200000, used_percentage=8))
            result = subprocess.run(bridge.bridge_command(script), shell=True, timeout=60,
                                    input=json.dumps(payload).encode('utf-8'),
                                    capture_output=True, env=dict(os.environ, LOCALAPPDATA=root))
            self.assertEqual(result.returncode, 0)
            self.assertIn('ctx 8%', result.stdout.decode('utf-8'))
            written = (Path(root) / 'CodexWisp' / 'claude-status' / 'abc-1.json').read_text(
                encoding='utf-8-sig')
            self.assertNotIn('secret', written)
            self.assertEqual(set(json.loads(written)), {
                'session_id', 'written_at', 'model', 'five_hour', 'seven_day',
                'context_window_size', 'context_used_percentage'})


class StoreBridgeTests(unittest.TestCase):
    def test_store_reports_bridge_limits_and_official_context(self):
        with tempfile.TemporaryDirectory() as root:
            home = ClaudeHome(Path(root) / 'claude')
            home.transcript('alpha', 's1', [
                assistant('s1', 'a1', 'C:/work/alpha', '2026-10-05T01:00:00Z')])
            status = Path(root) / 'status'
            status.mkdir()
            now = time.time()
            (status / 's1.json').write_text(json.dumps(snapshot(
                's1', written=now - 5, five=(30.0, now + 900), context=64.0)), encoding='utf-8')
            data = ClaudeStore(home.root, status_folder=status).read(pinned='claude:s1')
            self.assertEqual(data['limits']['primary']['usedPercent'], 30.0)
            self.assertEqual(data['context'], 64.0)
            self.assertEqual(data['context_window'], 200_000)
            plain = ClaudeStore(home.root, status_folder=Path(root) / 'none').read(
                pinned='claude:s1')
            self.assertIsNone(plain['limits'])


class ProcessTests(unittest.TestCase):
    def test_classify_process(self):
        self.assertEqual(classify_process('Claude.exe', ''), 'claude')
        self.assertEqual(classify_process('codex.exe', r'c:\users\u\appdata\roaming\npm\codex.exe'), 'codex')
        self.assertEqual(classify_process(
            'ChatGPT.exe', r'c:\program files\windowsapps\openai.codex_1\app\chatgpt.exe'), 'codex')
        self.assertIsNone(classify_process('ChatGPT.exe', r'c:\program files\chatgpt\chatgpt.exe'))
        self.assertIsNone(classify_process(
            'codex.exe', r'c:\users\u\.codex\packages\app-server-daemon\releases\codex.exe'))
        self.assertIsNone(classify_process('notepad.exe', ''))


class PresenceTests(unittest.TestCase):
    def test_nothing_shows_before_the_first_scan_and_failure_is_unknown(self):
        presence = overlay.UsagePresence(scan=lambda: {'codex'})
        self.assertEqual(presence.apps, frozenset())
        presence.poll()
        self.assertEqual(presence.apps, frozenset({'codex'}))
        failing = overlay.UsagePresence(scan=lambda: None)
        failing.poll()
        self.assertIsNone(failing.apps)


class OverlayRowTests(unittest.TestCase):
    def test_codex_pro_has_no_five_hour_row(self):
        pro = dict(secondary=dict(windowDurationMins=10080, usedPercent=40, resetsAt=NOW + 7200))
        section = overlay.provider_section('codex', pro, 30, 'proj', 'en', NOW)
        self.assertEqual([r['kind'] for r in section['rows']], ['context', 'week'])
        self.assertEqual(section['rows'][0]['remaining'], 70)
        self.assertEqual(section['rows'][1]['remaining'], 60)
        self.assertEqual(section['rows'][1]['reset'], 7200)
        self.assertIsNone(section['note'])

    def test_plus_shows_both_windows(self):
        plus = dict(primary=dict(windowDurationMins=300, usedPercent=10, resetsAt=NOW + 60),
                    secondary=dict(windowDurationMins=10080, usedPercent=40, resetsAt=NOW + 7200))
        section = overlay.provider_section('codex', plus, None, '', 'en', NOW)
        self.assertEqual([r['kind'] for r in section['rows']], ['context', 'five', 'week'])
        self.assertIsNone(section['rows'][0]['remaining'])

    def test_unknown_limits_show_a_note(self):
        section = overlay.provider_section('claude', None, 5, 'p', 'en', NOW, note='Turn it on')
        self.assertEqual([r['kind'] for r in section['rows']], ['context'])
        self.assertEqual(section['note'], 'Turn it on')

    def test_durations_and_context_colours(self):
        self.assertEqual(overlay.format_duration(40 * 60), '40m')
        self.assertEqual(overlay.format_duration(2 * 3600 + 13 * 60), '2h 13m')
        self.assertEqual(overlay.format_duration(3 * 86400 + 4 * 3600), '3d 4h')
        self.assertEqual(overlay.format_duration(4 * 3600 + 5 * 60), '4h 5m')

    def test_card_stays_legible_on_a_small_character(self):
        self.assertEqual(overlay.overlay_scale(50), overlay.MIN_SCALE / 100)
        self.assertEqual(overlay.overlay_scale(120), 1.2)
        for base, floor, _family in overlay.FONTS.values():
            self.assertGreaterEqual(max(floor, round(base * overlay.overlay_scale(50))), 10)
        self.assertEqual(overlay.context_color(0).name(), '#ffffff')
        self.assertEqual(overlay.context_color(100).name(), '#231e56')
        self.assertLess(overlay.context_color(70).lightness(), overlay.context_color(20).lightness())


class _Presence:
    def __init__(self, apps, claude_limits=None, claude_sync='off'):
        self.apps, self.claude_limits, self.claude_sync = apps, claude_limits, claude_sync

    def stop(self):
        pass


class PanelOverlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from widget import Panel
        from pet import DesktopPet
        self.temp = tempfile.TemporaryDirectory()
        self.pref_patch = patch('widget.PREF_DIR', Path(self.temp.name))
        self.pref_patch.start()
        self.panel = Panel(live=False)
        self.panel.prefs['language'] = 'en'
        self.panel.pet = DesktopPet(self.panel)
        self.panel.pet.activity_timer.stop()
        now = time.time()
        self.panel.quota = dict(sampled=now, limits=dict(
            secondary=dict(windowDurationMins=10080, usedPercent=20, resetsAt=now + 9000)))
        self.panel.task_manager._universe = {
            ('codex', 't1'): dict(provider_id='codex', activity_at=now,
                                  display=dict(project='alpha'), presentation=dict(context=40)),
            ('claude', 'claude:s1'): dict(provider_id='claude', activity_at=now,
                                          display=dict(project='beta'), presentation=dict(context=10))}

    def tearDown(self):
        self.panel.task_manager._universe = {}
        self.panel.pet.close()
        self.panel.tray.hide()
        self.panel.closing = True
        self.panel.close()
        self.pref_patch.stop()
        self.temp.cleanup()

    def providers(self, presence):
        return [s['provider'] for s in overlay.build_sections(self.panel, presence)]

    def test_sections_follow_the_open_apps(self):
        self.assertEqual(self.providers(_Presence(frozenset({'codex'}))), ['codex'])
        self.assertEqual(self.providers(_Presence(frozenset({'claude'}))), ['claude'])
        self.assertEqual(self.providers(_Presence(frozenset({'claude', 'codex'}))),
                         ['codex', 'claude'])
        self.assertEqual(self.providers(_Presence(frozenset())), [])
        # Unknown process list: fall back to the apps with running tasks.
        self.assertEqual(self.providers(_Presence(None)), ['codex', 'claude'])

    def test_sections_carry_project_context_and_claude_hint(self):
        codex, claude = overlay.build_sections(
            self.panel, _Presence(frozenset({'codex', 'claude'})))
        self.assertEqual((codex['project'], codex['rows'][0]['remaining']), ('alpha', 60))
        self.assertEqual([r['kind'] for r in codex['rows']], ['context', 'week'])
        self.assertEqual(claude['note'], 'Turn on Sync Claude usage in Settings')

    def test_overlay_shows_only_in_token_mode_and_paints(self):
        pet = self.panel.pet
        pet.presence = _Presence(frozenset({'codex'}))
        pet.show()
        pet.sync_usage_overlay()
        self.assertFalse(pet.usage_overlay_visible())
        mode = self.panel.app_mode
        mode.update(True, True, now=1)
        mode.update(True, True, now=2)
        pet.sync_usage_overlay()
        self.assertTrue(pet.usage_overlay.isVisible())
        self.assertTrue(pet.usage_overlay.testAttribute(
            __import__('PySide6.QtCore', fromlist=['Qt']).Qt.WA_TransparentForMouseEvents))
        image = pet.usage_overlay.grab().toImage()
        self.assertGreater(image.pixelColor(image.width() // 2, image.height() // 2).alpha(), 0)
        self.assertLessEqual(pet.usage_overlay.geometry().bottom(), pet.geometry().bottom())
        pet.hide()
        self.assertFalse(pet.usage_overlay_visible())


class StarNameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from widget import Panel
        from pet import DesktopPet
        self.temp = tempfile.TemporaryDirectory()
        self.pref_patch = patch('widget.PREF_DIR', Path(self.temp.name))
        self.pref_patch.start()
        self.panel = Panel(live=False)
        self.panel.pet = DesktopPet(self.panel)
        self.panel.pet.activity_timer.stop()
        self.manager = self.panel.task_manager

    def tearDown(self):
        self.manager._universe = {}
        self.manager._labels = {}
        self.panel.pet.close()
        self.panel.tray.hide()
        self.panel.closing = True
        self.panel.close()
        self.pref_patch.stop()
        self.temp.cleanup()

    def test_stars_are_named_after_their_project(self):
        tasks = {('codex', 'a'): 'test 1', ('claude', 'b'): 'test 1',
                 ('codex', 'c'): 'other', ('codex', 'd'): None}
        self.manager._universe = {key: dict(provider_id=key[0], display=dict(project=project))
                                  for key, project in tasks.items()}
        self.manager._labels = {('codex', 'a'): 2, ('claude', 'b'): 1,
                                ('codex', 'c'): 3, ('codex', 'd'): 4}
        label = lambda key: self.manager.label_text(key, 'en')
        self.assertEqual(label(('claude', 'b')), 'test 1 · 1')
        self.assertEqual(label(('codex', 'a')), 'test 1 · 2')
        self.assertEqual(label(('codex', 'c')), 'other')
        self.assertEqual(label(('codex', 'd')), 'Active task 4')


if __name__ == '__main__':
    unittest.main()
