import hashlib
import json
import tempfile
import time
import unittest
from pathlib import Path

from PySide6.QtWidgets import QApplication

import updater
from app_config import normalize_preferences

APP = QApplication.instance() or QApplication([])
INSTALLER = b'MZ fake installer'


def release(version='9.9.9', installer=True, sums=True, **extra):
    assets = []
    if installer:
        assets.append(dict(name=f'Petoken-Setup-v{version}.exe', browser_download_url='inst'))
    if sums:
        assets.append(dict(name='SHA256SUMS.txt', browser_download_url='sums'))
    return dict(tag_name=f'v{version}', body='## New\n- things', html_url='https://x', assets=assets, **extra)


class FeedTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def feed(self, data):
        path = self.root / 'feed.json'
        path.write_text(json.dumps(data), encoding='utf-8')
        return str(path)

    def test_versions(self):
        self.assertTrue(updater.newer('1.7.0', '1.6.0'))
        self.assertTrue(updater.newer('v1.10.0', '1.9.3'))
        self.assertFalse(updater.newer('1.6.0', '1.6.0'))
        self.assertFalse(updater.newer('banana', '1.6.0'))

    def test_latest_needs_installer_and_checksums(self):
        found = updater.latest(self.feed(release()))
        self.assertEqual((found['version'], found['installer'], found['sums']), ('9.9.9', 'inst', 'sums'))
        self.assertIsNone(updater.latest(self.feed(release(sums=False))))
        self.assertIsNone(updater.latest(self.feed(release(installer=False))))
        self.assertIsNone(updater.latest(self.feed(release(prerelease=True))))
        self.assertIsNone(updater.latest(str(self.root / 'missing.json')))

    def test_due_offer_and_skip(self):
        prefs = normalize_preferences({})
        self.assertTrue(updater.due(prefs, now=time.time()))
        prefs['update_checked_at'] = time.time()
        self.assertFalse(updater.due(prefs))
        prefs['update_check'] = False
        self.assertFalse(updater.due(prefs, now=time.time() + 10 ** 6))
        found = dict(version='9.9.9')
        self.assertIs(updater.offer(found, '1.7.0', {}), found)
        self.assertIsNone(updater.offer(found, '1.7.0', {'update_skip': '9.9.9'}))
        self.assertIsNone(updater.offer(dict(version='1.0.0'), '1.7.0', {}))

    def test_download_verifies_the_checksum(self):
        good = hashlib.sha256(INSTALLER).hexdigest()
        files = {'sums': f'{good}  Petoken-Setup-v9.9.9.exe\n'.encode(), 'inst': INSTALLER}
        for name, body in files.items():
            (self.root / name).write_bytes(body)
        found = dict(version='9.9.9', sums=str(self.root / 'sums'), installer=str(self.root / 'inst'))
        target = updater.download(found, self.root / 'updates')
        self.assertEqual(target.read_bytes(), INSTALLER)
        (self.root / 'inst').write_bytes(b'tampered')
        with self.assertRaises(ValueError):
            updater.download(found, self.root / 'updates2')
        self.assertFalse((self.root / 'updates2' / 'Petoken-Setup-v9.9.9.exe').exists())
        self.assertIn('/RELAUNCH=1', updater.install_command(target))
        self.assertIn('/SILENT', updater.install_command(target))


class FakeManager:
    def __init__(self, count=0):
        self.count = count

    def total_task_count(self):
        return self.count


class FakePanel:
    def __init__(self, prefs=None, running=0):
        self.prefs = normalize_preferences(prefs or {})
        self.task_manager = FakeManager(running)
        self.approvals = None
        self.closing = False
        self.notices, self.saved, self.shut = [], 0, 0

    def persist(self):
        self.saved += 1

    def tray_notice(self, title, body=''):
        self.notices.append(title)

    def shutdown(self):
        self.shut += 1


def pump(condition, seconds=3):
    deadline = time.time() + seconds
    while not condition() and time.time() < deadline:
        APP.processEvents()
        time.sleep(0.01)


class ControllerTests(unittest.TestCase):
    def controller(self, panel, found, installs):
        from update_ui import UpdateController
        return UpdateController(panel, check=lambda: found, download=lambda r: Path('setup.exe'),
                                start=installs.append)

    def test_manual_check_reports_up_to_date(self):
        panel, installs = FakePanel(), []
        control = self.controller(panel, dict(version='0.0.1', notes=''), installs)
        control.check_now(manual=True)
        pump(lambda: panel.notices)
        self.assertEqual(len(panel.notices), 1)
        self.assertIsNone(control.dialog)

    def test_new_version_opens_the_dialog(self):
        panel, installs = FakePanel(), []
        control = self.controller(panel, dict(version='99.0.0', notes='- new'), installs)
        control.check_now(manual=False)
        pump(lambda: control.dialog is not None)
        self.assertTrue(control.dialog.isVisible())
        control.dialog.skip.click()
        self.assertEqual(panel.prefs['update_skip'], '99.0.0')
        self.assertEqual(installs, [])

    def test_automatic_update_waits_until_idle(self):
        panel, installs = FakePanel(dict(update_auto=True), running=1), []
        control = self.controller(panel, dict(version='99.0.0', notes=''), installs)
        control.check_now(manual=False)
        pump(lambda: control.pending is not None)
        self.assertEqual(installs, [])          # A task is running: not now.
        panel.task_manager.count = 0
        control.tick()
        pump(lambda: installs)
        self.assertEqual(installs, [Path('setup.exe')])
        pump(lambda: panel.shut, seconds=2)
        self.assertEqual(panel.shut, 1)          # Petoken closes so the installer can replace it.


class OnboardingPrefTests(unittest.TestCase):
    def test_only_a_first_start_gets_the_guide(self):
        self.assertFalse(normalize_preferences({})['onboarding_done'])
        self.assertTrue(normalize_preferences({'language': 'en'})['onboarding_done'])   # Upgrading user.
        self.assertFalse(normalize_preferences({'language': 'en', 'onboarding_done': False})['onboarding_done'])

    def test_wizard_choices(self):
        from onboarding import OnboardingWizard
        panel = FakePanel()
        applied = []
        panel.finish_onboarding = applied.append
        wizard = OnboardingWizard(panel, claude=True)
        self.assertEqual(wizard.stack.count(), 4)
        wizard.language_box.setCurrentIndex(wizard.language_box.findData('zh_CN'))
        self.assertEqual(wizard.next.text(), '下一步')
        wizard.claude_boxes['claude_approval'][0].setChecked(False)
        for _ in range(3):
            wizard.forward()
        self.assertEqual(wizard.next.text(), '完成')
        wizard.forward()
        choices = applied[-1]
        self.assertEqual(choices['language'], 'zh_CN')
        self.assertEqual(choices['claude'], dict(claude_sync=True, claude_notify=True, claude_approval=False,
                                                 mute_claude_toasts=True))
        self.assertEqual(OnboardingWizard(panel, claude=False).stack.count(), 3)


if __name__ == '__main__':
    unittest.main()
