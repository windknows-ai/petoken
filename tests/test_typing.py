import tempfile
import unittest
from pathlib import Path

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from activity import TAP_MIN_INTERVAL, TYPING_WINDOW, ActivityState
from pet_assets import (AssetEntry, entry_for, existing_frames, frame_for,
                        resolve_path, sprite_for)


class TypingInteractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_keyboard_layer_keeps_no_key_content(self):
        state = ActivityState()
        state.key(100.0)
        self.assertEqual(state.tap_phase, 1)
        state.key(100.05)
        self.assertEqual(state.tap_phase, 1)
        state.key(100.3)
        self.assertEqual(state.tap_phase, 0)
        for value in state.__dict__.values():
            self.assertNotIsInstance(value, str)
        self.assertEqual(state.last_key, 100.3)

    def test_first_pulse_activates_typing_immediately(self):
        state = ActivityState()
        self.assertEqual(state.state(50), 'idle')
        state.key(50)
        self.assertEqual(state.state(50), 'typing')

    def test_repeated_pulses_alternate_tap_phase(self):
        state = ActivityState()
        state.key(10)
        first = state.tap_phase
        state.key(10.2)
        self.assertNotEqual(state.tap_phase, first)
        state.key(10.4)
        self.assertEqual(state.tap_phase, first)

    def test_rapid_pulses_coalesce_into_current_phase(self):
        state = ActivityState()
        flips = 0
        previous = state.tap_phase
        for i in range(50):
            state.key(20 + i * 0.002)
            if state.tap_phase != previous:
                flips += 1
                previous = state.tap_phase
        self.assertLessEqual(flips, 2)

    def test_inactivity_decays_back_to_idle(self):
        state = ActivityState()
        state.key(30)
        self.assertEqual(state.state(30 + TYPING_WINDOW - 0.1), 'typing')
        self.assertEqual(state.state(30 + TYPING_WINDOW + 0.1), 'idle')
        self.assertEqual(TYPING_WINDOW, 1.5)

    def test_working_microphone_music_override_typing(self):
        state = ActivityState()
        state.key(40)
        self.assertEqual(state.state(40, codex_working=True), 'working')
        state.sample(microphone=True, music=False, now=40)
        state.sample(microphone=True, music=False, now=40.6)
        self.assertEqual(state.state(40.6), 'microphone')
        state.sample(microphone=False, music=True, now=41)
        state.sample(microphone=False, music=True, now=42.6)
        self.assertEqual(state.state(42.6), 'music')

    def test_typing_frames_resolve_through_registry(self):
        entry = entry_for('typing')
        self.assertEqual(entry.frames[:2], ('assets/v1_1/typing_1.png', 'assets/v1_1/typing_2.png'))
        # 2.0 frames 3 and 4 join the loop once their art exists.
        self.assertEqual(entry.frames[2:], ('assets/v2_0/typing_3.png', 'assets/v2_0/typing_4.png'))
        self.assertEqual(len(existing_frames(entry)), 2)
        self.assertIsNotNone(frame_for('typing', 0))
        self.assertIsNotNone(frame_for('typing', 1))
        self.assertNotEqual(frame_for('typing', 0).cacheKey(),
                            frame_for('typing', 1).cacheKey())
        # No static typing.png supplied: the still pose is the first frame.
        self.assertEqual(resolve_path(entry), 'assets/v1_1/typing_1.png')
        self.assertIsNotNone(sprite_for('typing'))

    def test_present_frames_are_selected_by_phase(self):
        with tempfile.TemporaryDirectory() as directory:
            left = Path(directory) / 'tap_left.png'
            right = Path(directory) / 'tap_right.png'
            QImage(32, 32, QImage.Format_ARGB32).save(str(left))
            QImage(48, 48, QImage.Format_ARGB32).save(str(right))
            entry = AssetEntry('typing', 'assets/v1_1/typing.png',
                               'assets/skirk-typing.png', frames=(str(left), str(right)))
            self.assertEqual([Path(p).name for p in existing_frames(entry)],
                             ['tap_left.png', 'tap_right.png'])
            self.assertEqual(frame_for(entry, 0).width(), 32)
            self.assertEqual(frame_for(entry, 1).width(), 48)
            self.assertEqual(frame_for(entry, 2).width(), 32)


if __name__ == '__main__':
    unittest.main()
