"""Notifications on the phone, through ntfy (2.2).

ntfy (https://ntfy.sh, free and open source, iOS and Android apps) delivers a
message posted to a "topic" to every phone subscribed to it. Petoken makes a
long random topic name for this computer, so in practice only someone who
knows it (the user, after scanning the QR code in Settings) receives the
messages. The server can be the public ntfy.sh or the user's own.

What is sent: the same notices as on the desktop (an AI finished, failed,
waits for approval, a limit runs low...), title and one line, optionally with
the project name. When: while the user is away from the computer (no input
for a few minutes), or always while focusing or gaming (desktop pop-ups are
silent then). Never during Do Not Disturb. Nothing is read back from the
server; approving from the phone is planned for later.
"""
from __future__ import annotations

import queue
import secrets
import threading
import time
import urllib.error
import urllib.request

DEFAULT_SERVER = 'https://ntfy.sh'
KINDS = ('finished', 'failed', 'needs_approval', 'quota_low', 'reminder')
DEFAULT_KINDS = ('finished', 'failed', 'needs_approval', 'quota_low')
WHEN = ('away', 'always')
AWAY_AFTER_S = 5 * 60
PER_MINUTE = 6                      # At most this many messages a minute (a burst of finishes).
TIMEOUT_S = 10
PRIORITY = {'needs_approval': 'high', 'failed': 'high', 'quota_low': 'default', 'finished': 'default',
            'reminder': 'high'}
TAGS = {'finished': 'white_check_mark', 'failed': 'x', 'needs_approval': 'raising_hand',
        'quota_low': 'warning', 'reminder': 'alarm_clock'}


def new_topic():
    """A long random topic: 22 lowercase letters and digits after 'petoken-'."""
    alphabet = 'abcdefghijkmnpqrstuvwxyz23456789'          # No look-alikes (l, o, 0, 1).
    return 'petoken-' + ''.join(secrets.choice(alphabet) for _ in range(22))


def topic_url(prefs):
    server = (prefs.get('push_server') or DEFAULT_SERVER).strip().rstrip('/')
    return f"{server}/{prefs.get('push_topic') or ''}"


def subscribe_url(prefs):
    """What the phone opens to subscribe (the ntfy app understands the topic URL)."""
    return topic_url(prefs)


def build_message(event, title, body, prefs):
    """The request headers and body for one notice."""
    kind = event.get('kind') or ''
    if not prefs.get('push_project', True):
        body = ''                    # Only what happened, no project or task name.
    headers = {'Title': title.encode('utf-8'), 'Priority': PRIORITY.get(kind, 'default'),
               'Tags': TAGS.get(kind, 'bell')}
    return headers, (body or title).encode('utf-8')


class PhonePush:
    """Sends notices to ntfy in a worker thread; never blocks the UI."""

    def __init__(self, panel, opener=None, idle=None, clock=time.monotonic):
        self.panel = panel
        self.opener = opener or urllib.request.urlopen
        if idle is None:
            from pet_mood import input_idle_seconds
            idle = input_idle_seconds
        self.idle = idle
        self.clock = clock
        self.sent = []               # Times of recent sends (rate limit).
        self.last_error = None
        self.queue = queue.Queue()
        self.worker = threading.Thread(target=self._run, daemon=True, name='petoken-push')
        self.worker.start()

    @property
    def prefs(self):
        return self.panel.prefs

    @property
    def enabled(self):
        return bool(self.prefs.get('push_enabled')) and bool(self.prefs.get('push_topic'))

    def wanted(self, event):
        """Should this notice go to the phone now?"""
        if not self.enabled:
            return False
        kind = event.get('kind')
        kinds = self.prefs.get('push_kinds')
        if kind not in (kinds if isinstance(kinds, list) else DEFAULT_KINDS):
            return False
        try:
            from widget import quiet_now
            if quiet_now(self.prefs):
                return False         # Do Not Disturb covers the phone too.
        except Exception:
            pass
        if self.prefs.get('push_when', 'away') == 'always':
            return True
        busy = any(getattr(getattr(self.panel, name, None), 'active', False) for name in ('focus_mode', 'game_mode'))
        return busy or self.idle() >= AWAY_AFTER_S

    def notify(self, event, title, body):
        """Called for every desktop notice; sends it when wanted."""
        if not self.wanted(event):
            return False
        now = self.clock()
        self.sent = [t for t in self.sent if now - t < 60]
        if len(self.sent) >= PER_MINUTE:
            return False
        self.sent.append(now)
        headers, data = build_message(event, title, body, self.prefs)
        self.queue.put((topic_url(self.prefs), headers, data, None))
        return True

    def test(self, done=None):
        """Send a test message now (Settings' button); ``done(error or None)`` afterwards."""
        from localization import text
        language = self.prefs.get('language')
        headers = {'Title': text('push_test_title', language).encode('utf-8'), 'Tags': 'tada'}
        self.queue.put((topic_url(self.prefs), headers, text('push_test_body', language).encode('utf-8'), done))

    def _run(self):
        while True:
            item = self.queue.get()
            if item is None:
                return
            url, headers, data, done = item
            error = None
            try:
                request = urllib.request.Request(url, data=data, headers=headers, method='POST')
                with self.opener(request, timeout=TIMEOUT_S) as response:
                    if getattr(response, 'status', 200) >= 400:
                        error = f'HTTP {response.status}'
            except urllib.error.HTTPError as exc:
                error = f'HTTP {exc.code}'
            except (urllib.error.URLError, OSError, ValueError) as exc:
                error = str(getattr(exc, 'reason', exc))
            self.last_error = error
            if done is not None:
                try:
                    done(error)
                except Exception:
                    pass

    def close(self):
        self.queue.put(None)
