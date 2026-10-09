"""2.2 phone notifications through ntfy (against a local test server, never ntfy.sh)."""
import http.server
import threading
import time
import unittest
from types import SimpleNamespace

from PySide6.QtWidgets import QApplication

import phone_push
from phone_push import PhonePush, new_topic

APP = QApplication.instance() or QApplication([])


class Server:
    """A tiny ntfy stand-in on localhost that records what it receives."""

    def __init__(self, status=200):
        self.got = []
        self.event = threading.Event()
        outer = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers.get('Content-Length') or 0))
                outer.got.append((self.path, dict(self.headers), body.decode('utf-8')))
                self.send_response(status)
                self.end_headers()
                outer.event.set()

            def log_message(self, *args):
                pass
        self.httpd = http.server.HTTPServer(('127.0.0.1', 0), Handler)
        self.url = f'http://127.0.0.1:{self.httpd.server_address[1]}'
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def wait(self):
        self.event.wait(5)
        self.event.clear()

    def close(self):
        self.httpd.shutdown()


class PhonePushTests(unittest.TestCase):
    def setUp(self):
        self.server = Server()
        self.addCleanup(self.server.close)
        self.idle = [0.0]
        self.panel = SimpleNamespace(prefs=dict(push_enabled=True, push_topic='petoken-test', push_server=self.server.url,
                                                language='en'),
                                     focus_mode=SimpleNamespace(active=False), game_mode=SimpleNamespace(active=False))
        self.push = PhonePush(self.panel, idle=lambda: self.idle[0])
        self.addCleanup(self.push.close)

    def test_topics_are_long_and_random(self):
        a, b = new_topic(), new_topic()
        self.assertNotEqual(a, b)
        self.assertTrue(a.startswith('petoken-') and len(a) == 30)
        self.assertFalse(set(a[8:]) & set('lo01'))

    def test_sends_only_when_away_focusing_or_gaming(self):
        event = dict(kind='finished', provider='claude')
        self.assertFalse(self.push.notify(event, 'Claude Code finished', 'website'))   # At the computer.
        self.panel.game_mode.active = True
        self.assertTrue(self.push.notify(event, 'Claude Code finished', 'website'))    # Gaming.
        self.server.wait()
        path, headers, body = self.server.got[-1]
        self.assertEqual(path, '/petoken-test')
        self.assertEqual((headers['Title'], body), ('Claude Code finished', 'website'))
        self.assertEqual(headers['Tags'], 'white_check_mark')
        self.panel.game_mode.active = False
        self.idle[0] = phone_push.AWAY_AFTER_S + 1                                       # Away.
        self.assertTrue(self.push.notify(dict(kind='needs_approval'), 'Waiting', 'api'))
        self.server.wait()
        self.assertEqual(self.server.got[-1][1]['Priority'], 'high')

    def test_choices_privacy_dnd_and_rate_limit(self):
        self.panel.prefs['push_when'] = 'always'
        self.assertFalse(self.push.notify(dict(kind='reminder'), 'Reminder', ''))       # Not chosen by default.
        self.panel.prefs['push_project'] = False
        self.assertTrue(self.push.notify(dict(kind='failed'), 'Codex failed', 'secret-project · rate_limit'))
        self.server.wait()
        self.assertNotIn('secret-project', self.server.got[-1][2])                     # No project names.
        self.panel.prefs.update(dnd_enabled=True)
        self.assertFalse(self.push.notify(dict(kind='failed'), 'Codex failed', ''))     # Do Not Disturb.
        self.panel.prefs.update(dnd_enabled=False)
        sent = sum(self.push.notify(dict(kind='finished'), 'done', '') for _ in range(20))
        self.assertLessEqual(sent + 1, phone_push.PER_MINUTE)                          # A burst is capped.
        self.panel.prefs['push_enabled'] = False
        self.assertFalse(self.push.notify(dict(kind='failed'), 'x', ''))

    def test_test_button_reports_success_and_errors(self):
        results = []
        self.push.test(results.append)
        self.server.wait()
        for _ in range(50):
            if results:
                break
            time.sleep(.02)
        self.assertEqual(results, [None])
        self.assertEqual(self.server.got[-1][1]['Title'], 'Petoken test')
        self.panel.prefs['push_server'] = 'http://127.0.0.1:9'                         # Nothing listens there.
        results.clear()
        self.push.test(results.append)
        for _ in range(250):
            if results:
                break
            time.sleep(.02)
        self.assertTrue(results and results[0])


class PhoneSettingsTests(unittest.TestCase):
    def test_settings_page_round_trip(self):
        from unittest.mock import patch
        from widget import Panel, Settings
        panel = Panel(live=False)
        self.addCleanup(lambda: (setattr(panel, 'closing', True), panel.phone_push.close(), panel.close()))
        settings = Settings(panel)
        settings.show()
        self.assertTrue(settings.push_topic.startswith('petoken-'))                     # A topic is ready.
        self.assertIn(settings.push_topic, settings.push_url.text())
        self.assertFalse(settings._card_of(settings.push_test_label).isVisibleTo(settings))   # Hidden until on.
        settings.push_enabled.setChecked(True)
        settings.push_kind_boxes['reminder'].setChecked(True)
        old = settings.push_topic
        settings.push_renew.click()
        self.assertNotEqual(settings.push_topic, old)
        with patch('widget.write_preferences'):
            settings.save()
        self.assertTrue(panel.prefs['push_enabled'])
        self.assertEqual(panel.prefs['push_topic'], settings.push_topic)
        self.assertIn('reminder', panel.prefs['push_kinds'])
        settings.close()


if __name__ == '__main__':
    unittest.main()
