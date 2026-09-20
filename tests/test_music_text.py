import asyncio
import unittest

from PySide6.QtWidgets import QApplication

from activity import ActivityMonitor, ActivityState, summarize_music_text


class FakeProperties:
    def __init__(self, title='', artist='', subtitle=''):
        self.title = title
        self.artist = artist
        self.subtitle = subtitle


class FakeSession:
    def __init__(self, app_id='player.example', props=None, fail=False):
        self.source_app_user_model_id = app_id
        self._props = props or FakeProperties()
        self._fail = fail

    async def try_get_media_properties_async(self):
        if self._fail:
            raise OSError('metadata unavailable')
        return self._props


class MusicTextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_music_activity_works_with_no_text_source(self):
        state = summarize_music_text('player.example', 'Track', 'Artist', '', True)
        self.assertIsNone(state)
        activity = ActivityState()
        activity.sample(microphone=False, music=True, now=10)
        activity.sample(microphone=False, music=True, now=10.6)
        self.assertEqual(activity.state(10.6), 'music')

    def test_verified_text_becomes_available(self):
        state = summarize_music_text('player.example', 'Track', 'Artist', 'A subtitle line', True)
        self.assertEqual(state['text'], 'A subtitle line')
        self.assertEqual(state['source'], 'player.example')
        self.assertTrue(state['identity'])

    def test_unavailable_text_produces_no_fake_content(self):
        for subtitle in ('', '   ', None, 42):
            self.assertIsNone(summarize_music_text('app', 'T', 'A', subtitle, True),
                              repr(subtitle))

    def test_stopped_playback_produces_no_text(self):
        self.assertIsNone(summarize_music_text('app', 'T', 'A', 'Words', False))

    def test_track_change_produces_new_identity(self):
        first = summarize_music_text('app', 'Track One', 'A', 'Words one', True)
        second = summarize_music_text('app', 'Track Two', 'A', 'Words two', True)
        self.assertNotEqual(first['identity'], second['identity'])
        self.assertNotEqual(first['text'], second['text'])

    def test_metadata_failure_yields_none(self):
        text = asyncio.run(ActivityMonitor.read_music_text(FakeSession(fail=True), True))
        self.assertIsNone(text)

    def test_reader_returns_text_and_survives_garbage(self):
        session = FakeSession(props=FakeProperties('T', 'A', '  Padded line  '))
        text = asyncio.run(ActivityMonitor.read_music_text(session, True))
        self.assertEqual(text['text'], 'Padded line')
        empty = asyncio.run(ActivityMonitor.read_music_text(FakeSession(), True))
        self.assertIsNone(empty)

    def test_text_is_memory_only_and_untranslated(self):
        line = 'Original Zeile · 原始字幕行'
        state = summarize_music_text('app', 'T', 'A', line, True)
        self.assertEqual(state['text'], line)
        self.assertEqual(set(state), {'text', 'source', 'identity'})

    def test_priority_order_is_unchanged(self):
        activity = ActivityState()
        activity.key(50)
        self.assertEqual(activity.state(50, codex_working=True), 'working')
        activity.sample(microphone=True, music=True, now=50)
        activity.sample(microphone=True, music=True, now=50.6)
        self.assertEqual(activity.state(50.6), 'microphone')
        activity.sample(microphone=False, music=True, now=51)
        activity.sample(microphone=False, music=True, now=52.6)
        self.assertEqual(activity.state(52.6), 'music')
        self.assertEqual(activity.state(52.6), 'music')


if __name__ == '__main__':
    unittest.main()
