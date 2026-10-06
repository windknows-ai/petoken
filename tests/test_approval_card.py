import json
import tempfile
import unittest
from pathlib import Path

from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import QApplication

import claude_approval as ca
from approval_card import ApprovalController, elide_lines, request_title

APP = QApplication.instance() or QApplication([])


class FakePanel:
    def __init__(self):
        self.prefs = dict(language='en')
        self.pet = None


class CardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.broker = ca.ApprovalBroker(Path(self.temp.name) / 'q')
        self.controller = ApprovalController(FakePanel(), self.broker)

    def tearDown(self):
        self.controller.stop()
        self.temp.cleanup()

    def put(self, request_id, **extra):
        self.broker.folder.mkdir(parents=True, exist_ok=True)
        data = {**dict(session_id='s', cwd=r'C:\work\site', tool_name='Bash',
                       tool_input=dict(command='npm test')), **extra}
        (self.broker.folder / f'{request_id}.request.json').write_text(json.dumps(data), encoding='utf-8')

    def test_queue_shows_oldest_and_answers(self):
        seen = []
        self.controller.requested.connect(seen.append)
        self.put('a' * 32)
        self.put('b' * 32, tool_input=dict(command='line one\nline two'))
        self.controller.tick()
        card = self.controller.card
        self.assertTrue(card.isVisible())
        self.assertEqual(len(seen), 2)
        self.assertEqual(card.title.text(), 'Claude Code wants to run a command')
        self.assertIn('1 more', card.countdown.text())
        card.allow.click()
        self.assertTrue((self.broker.folder / f"{'a' * 32}.decision.json").exists())
        # The multi-line command can only be allowed once.
        self.assertFalse(self.controller.card.always.isEnabled())
        self.controller.card.ask.click()
        self.assertEqual((self.broker.folder / f"{'b' * 32}.decision.json").read_text(encoding='utf-8'), '')
        self.assertIsNone(self.controller.card)

    def test_request_that_timed_out_disappears(self):
        self.put('c' * 32)
        self.controller.tick()
        (self.broker.folder / f"{'c' * 32}.request.json").unlink()
        self.controller.tick()
        self.assertIsNone(self.controller.card)

    def test_titles_and_eliding(self):
        self.assertEqual(request_title(dict(tool='Write'), 'zh_CN'), 'Claude Code 想修改文件')
        self.assertEqual(request_title(dict(tool='mcp__x__y'), 'en'), 'Claude Code wants to use mcp__x__y')
        metrics = QFontMetrics(QFont('Consolas', 9))
        lines = elide_lines('x' * 2000, metrics, 200).split('\n')
        self.assertEqual(len(lines), 4)
        self.assertTrue(lines[-1].endswith('…'))


if __name__ == '__main__':
    unittest.main()
