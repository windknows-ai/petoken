import json
import tempfile
import time
import unittest
from pathlib import Path

import claude_approval as ca

COMMAND_INPUT = dict(
    session_id='s1', cwd=r'C:\work\site', hook_event_name='PermissionRequest', tool_name='Bash',
    tool_input=dict(command='npm test', description='Run the tests'),
    permission_suggestions=[dict(type='addDirectories', directories=[r'C:\work\site'], destination='session'),
                            dict(type='setMode', mode='acceptEdits', destination='session')])


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        self.script = self.home / ca.SCRIPT_NAME
        foreign = dict(hooks=dict(PermissionRequest=[dict(hooks=[dict(type='command', command='other')])],
                                  Stop=[dict(hooks=[dict(type='command', command='x')])]),
                       model='opus')
        (self.home / 'settings.json').write_text(json.dumps(foreign), encoding='utf-8')

    def tearDown(self):
        self.temp.cleanup()

    def settings(self):
        return json.loads((self.home / 'settings.json').read_text(encoding='utf-8'))

    def test_enable_and_disable_keep_foreign_hooks(self):
        self.assertEqual(ca.state(self.home), 'off')
        self.assertEqual(ca.enable(self.home, self.script, self.home / 'q'), 'on')
        groups = self.settings()['hooks']['PermissionRequest']
        self.assertEqual(len(groups), 2)
        ours = groups[1]['hooks'][0]
        self.assertEqual(ours['timeout'], ca.HOOK_TIMEOUT_S)
        self.assertNotIn('async', ours)  # Blocking: Claude Code waits for the pet.
        self.assertIn(str(self.home / 'q'), self.script.read_text(encoding='utf-8-sig'))
        self.assertTrue(list(self.home.glob('settings.json.petoken-backup-*')))
        # Enabling twice does not add a second hook.
        ca.enable(self.home, self.script, self.home / 'q')
        self.assertEqual(len(self.settings()['hooks']['PermissionRequest']), 2)
        self.assertEqual(ca.disable(self.home), 'off')
        data = self.settings()
        self.assertEqual(data['hooks']['PermissionRequest'], [dict(hooks=[dict(type='command', command='other')])])
        self.assertEqual(data['model'], 'opus')

    def test_unreadable_settings_are_left_alone(self):
        (self.home / 'settings.json').write_text('{oops', encoding='utf-8')
        self.assertEqual(ca.enable(self.home, self.script), 'unreadable')
        self.assertEqual((self.home / 'settings.json').read_text(encoding='utf-8'), '{oops')

    def test_script_waits_less_than_the_hook_timeout(self):
        text = ca.script_text(r"C:\it's here")
        self.assertIn("'C:\\it''s here'", text)
        self.assertIn(f'AddSeconds({ca.WAIT_S})', text)
        self.assertLess(ca.WAIT_S, ca.HOOK_TIMEOUT_S)


class RequestTests(unittest.TestCase):
    def test_parse_keeps_what_the_card_needs(self):
        request = ca.parse_request('a' * 32, json.dumps(COMMAND_INPUT), 5.0)
        self.assertEqual((request['tool'], request['summary'], request['project'], request['description']),
                         ('Bash', 'npm test', 'site', 'Run the tests'))
        self.assertEqual([s['type'] for s in request['suggestions']], ['addDirectories'])
        self.assertTrue(request['can_always'])
        self.assertIsNone(ca.parse_request('a' * 32, '{oops', 1))
        self.assertIsNone(ca.parse_request('a' * 32, json.dumps(dict(hook_event_name='Stop', tool_name='x')), 1))

    def test_precise_rules(self):
        self.assertEqual(ca.precise_rule('Bash', dict(command=' npm test ')), ('Bash', 'npm test'))
        self.assertIsNone(ca.precise_rule('Bash', dict(command='a\nb')))
        self.assertIsNone(ca.precise_rule('PowerShell', dict(command='x' * 400)))
        self.assertEqual(ca.precise_rule('WebFetch', dict(url='https://docs.example.com/a')),
                         ('WebFetch', 'domain:docs.example.com'))
        self.assertEqual(ca.precise_rule('Edit', dict(file_path='a.py')), ('Edit', None))
        self.assertEqual(ca.summary('Edit', dict(file_path='a.py', old_string='x')), 'a.py')

    def test_decisions(self):
        request = ca.parse_request('a' * 32, json.dumps(COMMAND_INPUT), 5.0)
        allow = ca.decision(request, 'allow')['hookSpecificOutput']
        self.assertEqual(allow, dict(hookEventName='PermissionRequest', decision=dict(behavior='allow')))
        self.assertEqual(ca.decision(request, 'deny')['hookSpecificOutput']['decision']['behavior'], 'deny')
        self.assertIsNone(ca.decision(request, 'ask'))
        updates = ca.decision(request, 'always')['hookSpecificOutput']['decision']['updatedPermissions']
        self.assertEqual(updates, [
            dict(type='addDirectories', directories=[r'C:\work\site'], destination='localSettings'),
            dict(type='addRules', rules=[dict(toolName='Bash', ruleContent='npm test')], behavior='allow',
                 destination='localSettings')])
        self.assertEqual(ca.rule_text(dict(toolName='Bash', ruleContent='npm test')), 'Bash(npm test)')
        self.assertEqual(ca.rule_text(dict(toolName='Edit')), 'Edit')


class BrokerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.broker = ca.ApprovalBroker(self.root / 'q')
        self.ledger = self.root / 'rules.json'

    def tearDown(self):
        self.temp.cleanup()

    def put(self, request_id, data):
        self.broker.folder.mkdir(parents=True, exist_ok=True)
        (self.broker.folder / f'{request_id}.request.json').write_text(
            data if isinstance(data, str) else json.dumps(data), encoding='utf-8')

    def test_heartbeat_poll_answer_and_gone(self):
        self.broker.heartbeat()
        self.assertTrue((self.broker.folder / 'alive').exists())
        first, second = 'a' * 32, 'b' * 32
        self.put(first, COMMAND_INPUT)
        self.put(second, COMMAND_INPUT)
        new, gone = self.broker.poll()
        self.assertEqual(sorted(r['id'] for r in new), [first, second])
        self.assertEqual(self.broker.poll(), ([], []))
        self.assertTrue(self.broker.answer(first, 'allow'))
        # Until the script removes the answered request it is not asked again.
        self.assertEqual(self.broker.poll(), ([], []))
        answer = json.loads((self.broker.folder / f'{first}.decision.json').read_text(encoding='utf-8'))
        self.assertEqual(answer['hookSpecificOutput']['decision']['behavior'], 'allow')
        # The script timed out on the second one and removed its request.
        (self.broker.folder / f'{second}.request.json').unlink()
        (self.broker.folder / f'{first}.request.json').unlink()
        self.assertEqual(self.broker.poll(), ([], [second]))
        self.assertFalse(self.broker.answer(second, 'allow'))

    def test_unreadable_request_goes_back_to_claude(self):
        self.put('c' * 32, '{oops')
        self.assertEqual(self.broker.poll(), ([], []))
        self.assertEqual((self.broker.folder / f"{'c' * 32}.decision.json").read_text(encoding='utf-8'), '')

    def test_shutdown_hands_back_and_stops_waiting(self):
        self.broker.heartbeat()
        self.put('d' * 32, COMMAND_INPUT)
        self.broker.poll()
        self.broker.shutdown()
        self.assertEqual((self.broker.folder / f"{'d' * 32}.decision.json").read_text(encoding='utf-8'), '')
        self.assertFalse((self.broker.folder / 'alive').exists())

    def test_always_rules_are_recorded_and_revocable(self):
        project = self.root / 'site'
        (project / '.claude').mkdir(parents=True)
        local = project / '.claude' / 'settings.local.json'
        local.write_text(json.dumps(dict(permissions=dict(
            allow=['Bash(npm test)', 'Bash(ls)'], additionalDirectories=[str(project)]))), encoding='utf-8')
        request = ca.parse_request('e' * 32, json.dumps(dict(COMMAND_INPUT, cwd=str(project),
            permission_suggestions=[dict(type='addDirectories', directories=[str(project)])])), time.time())
        ca.record_rules(request, self.ledger, now=1.0)
        ca.record_rules(request, self.ledger, now=2.0)   # No duplicates.
        rules = ca.list_rules(self.ledger)
        self.assertEqual([(r.get('rules'), r.get('directories')) for r in rules],
                         [(None, [str(project)]), (['Bash(npm test)'], None)])
        self.assertTrue(ca.revoke(rules[1], self.ledger))
        data = json.loads(local.read_text(encoding='utf-8'))
        self.assertEqual(data['permissions']['allow'], ['Bash(ls)'])
        self.assertEqual(len(ca.list_rules(self.ledger)), 1)
        ca.revoke(ca.list_rules(self.ledger)[0], self.ledger)
        self.assertNotIn('additionalDirectories', json.loads(local.read_text(encoding='utf-8'))['permissions'])


if __name__ == '__main__':
    unittest.main()
