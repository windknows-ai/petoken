import json
import tempfile
import unittest
from pathlib import Path

import claude_recap
from notifications import parse_recap, recap_detail, recap_text

SESSION = '11111111-2222-3333-4444-555555555555'
CWD = r'C:\work\site'


def stamp(seconds):
    return f'2026-10-06T10:{seconds // 60:02d}:{seconds % 60:02d}.000Z'


def user(at, content, **extra):
    return dict(type='user', timestamp=stamp(at), cwd=CWD, sessionId=SESSION,
                message=dict(role='user', content=content), **extra)


def assistant(at, message_id, blocks=(), output=100, cwd=CWD, **extra):
    return dict(type='assistant', timestamp=stamp(at), cwd=cwd, sessionId=SESSION, requestId='r' + message_id,
                message=dict(id=message_id, model='claude-sonnet-4-5', content=list(blocks),
                             usage=dict(input_tokens=1000, output_tokens=output)), **extra)


def edit(tool_id, path, name='Edit'):
    return dict(type='tool_use', id=tool_id, name=name, input=dict(file_path=path, old_string='secret'))


def result(tool_id, error=False):
    return dict(type='tool_result', tool_use_id=tool_id, content='ok', is_error=error)


class RecapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        self.folder = self.home / 'projects' / 'C--work-site'
        self.folder.mkdir(parents=True)

    def tearDown(self):
        self.temp.cleanup()

    def write(self, entries, path=None):
        path = path or self.folder / f'{SESSION}.jsonl'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(''.join(json.dumps(e) + '\n' for e in entries), encoding='utf-8')

    def test_last_turn_files_time_and_cost(self):
        self.write([
            user(0, 'old prompt'),
            assistant(5, 'm0', [edit('t0', CWD + r'\old.py')]),
            user(6, [result('t0')]),
            user(60, [dict(type='text', text='add dark mode')]),
            assistant(70, 'm1', [edit('t1', CWD + r'\src\styles.css'), edit('t2', CWD + r'\bad.py')]),
            assistant(70, 'm1', [edit('t1', CWD + r'\src\styles.css')]),   # Same response, another block.
            user(71, [result('t1'), result('t2', error=True)]),
            assistant(80, 'm2', [edit('t3', r'D:\elsewhere\notes.md', 'Write')], cwd=r'D:\elsewhere'),
            user(81, [result('t3')]),
            user(82, '[Request interrupted by user]'),
            assistant(312, 'm3'),
        ])
        recap = claude_recap.recap(self.home, SESSION)
        self.assertEqual(recap['files'], ['D:/elsewhere/notes.md', 'src/styles.css'])
        self.assertEqual(recap['duration_s'], 252)
        self.assertAlmostEqual(recap['usd'], 3 * (1000 * 3 + 100 * 15) / 1_000_000)

    def test_subagent_edits_and_unknown_price(self):
        self.write([user(0, 'go'), assistant(30, 'm1')])
        self.write([assistant(10, 'sub1', [edit('s1', CWD + r'\a.py')], isSidechain=True),
                    user(11, [result('s1')], isSidechain=True)],
                   self.folder / SESSION / 'subagents' / 'agent-1.jsonl')
        recap = claude_recap.recap(self.home, SESSION)
        self.assertEqual(recap['files'], ['a.py'])
        self.write([user(0, 'go'), dict(assistant(30, 'm1'), message=dict(
            id='m1', model='mystery-model', content=[], usage=dict(input_tokens=1, output_tokens=1)))])
        self.assertIsNone(claude_recap.recap(self.home, SESSION)['usd'])

    def test_missing_or_unfinished(self):
        self.assertIsNone(claude_recap.recap(self.home, SESSION))
        self.assertIsNone(claude_recap.recap(self.home, '../x'))
        self.write([user(0, 'still thinking')])
        self.assertIsNone(claude_recap.recap(self.home, SESSION))

    def test_detail_round_trip_and_text(self):
        detail = recap_detail(dict(files=['a.py', 'b.py', 'c.py'], duration_s=251.6, usd=0.42))
        self.assertEqual(parse_recap(detail)['names'], ['a.py', 'b.py', 'c.py'])
        self.assertEqual(recap_text(detail, 'en'), '3 files changed · 4m 12s · ≈ $0.42')
        self.assertEqual(recap_text(recap_detail(dict(files=[], duration_s=None, usd=None)), 'zh_CN'), '没有改文件')
        self.assertEqual(recap_text('rate_limit', 'en'), '')
        self.assertIsNone(parse_recap(''))


if __name__ == '__main__':
    unittest.main()
