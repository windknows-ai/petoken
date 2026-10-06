import json
import tempfile
import unittest
from pathlib import Path

import claude_toasts as ct

APP = 'Claude_pzs8sxrjxfjjc!Claude'


class FakeRegistry:
    def __init__(self, keys, values=None):
        self.keys = list(keys)
        self.values = dict(values or {})

    def subkeys(self, path):
        return list(self.keys)

    def get(self, path, name):
        return self.values.get((path, name))

    def set(self, path, name, value):
        self.values[(path, name)] = value

    def delete(self, path, name):
        self.values.pop((path, name), None)


def key(app=APP):
    return (f'{ct.SETTINGS_KEY}\{app}', 'Enabled')


class ToastTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.state = Path(self.temp.name) / 'state.json'

    def tearDown(self):
        self.temp.cleanup()

    def test_mute_and_restore_never_set_value(self):
        registry = FakeRegistry([APP, 'Microsoft.Teams', 'Claude_fake!Other'])
        self.assertEqual(ct.mute(registry, self.state), [APP])
        self.assertEqual(registry.values, {key(): 0})
        self.assertTrue(ct.restore(registry, self.state))
        self.assertEqual(registry.values, {})          # Back to the Windows default.
        self.assertFalse(self.state.exists())

    def test_users_own_off_setting_is_kept(self):
        registry = FakeRegistry([APP], {key(): 0})
        ct.mute(registry, self.state)
        ct.restore(registry, self.state)
        self.assertEqual(registry.values, {key(): 0})

    def test_crash_then_restart_remembers_the_original(self):
        registry = FakeRegistry([APP], {key(): 1})
        ct.mute(registry, self.state)                  # Petoken stops without restoring...
        ct.mute(registry, self.state)                  # ...and starts again.
        self.assertEqual(json.loads(self.state.read_text(encoding='utf-8')), {APP: 1})
        ct.restore(registry, self.state)
        self.assertEqual(registry.values, {key(): 1})

    def test_no_claude_app(self):
        registry = FakeRegistry(['Microsoft.Teams'])
        self.assertEqual(ct.mute(registry, self.state), [])
        self.assertFalse(self.state.exists())
        self.assertFalse(ct.restore(registry, self.state))


if __name__ == '__main__':
    unittest.main()
