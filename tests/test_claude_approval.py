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

    def test_refresh_updates_an_older_install(self):
        self.assertEqual(ca.refresh(self.home, self.script, self.home / 'q'), 'off')   # Not installed: nothing.
        ca.enable(self.home, self.script, self.home / 'q')
        # An older Petoken: shorter wait in the script, 60 s hook timeout.
        self.script.write_text(ca.script_text(self.home / 'q').replace('$wait = 45', '$wait = 10'), encoding='utf-8-sig')
        data = self.settings()
        data['hooks']['PermissionRequest'][1]['hooks'][0]['timeout'] = 60
        (self.home / 'settings.json').write_text(json.dumps(data), encoding='utf-8')
        backups = len(list(self.home.glob('settings.json.petoken-backup-*')))
        self.assertEqual(ca.refresh(self.home, self.script, self.home / 'q'), 'on')
        self.assertEqual(self.script.read_text(encoding='utf-8-sig'), ca.script_text(self.home / 'q'))
        self.assertEqual(self.settings()['hooks']['PermissionRequest'][1]['hooks'][0]['timeout'], ca.HOOK_TIMEOUT_S)
        self.assertEqual(len(self.settings()['hooks']['PermissionRequest']), 2)
        # Already current: no rewrite, no new backup.
        after = len(list(self.home.glob('settings.json.petoken-backup-*')))
        ca.refresh(self.home, self.script, self.home / 'q')
        self.assertEqual(len(list(self.home.glob('settings.json.petoken-backup-*'))), after)
        self.assertGreaterEqual(after, backups)

    def test_unreadable_settings_are_left_alone(self):
        (self.home / 'settings.json').write_text('{oops', encoding='utf-8')
        self.assertEqual(ca.enable(self.home, self.script), 'unreadable')
        self.assertEqual((self.home / 'settings.json').read_text(encoding='utf-8'), '{oops')

    def test_script_waits_less_than_the_hook_timeout(self):
        text = ca.script_text(r"C:\it's here")
        self.assertIn("'C:\\it''s here'", text)
        self.assertIn(f'$wait = {ca.WAIT_S}', text)
        self.assertIn(f'{{ $wait = {ca.QUESTION_WAIT_S} }}', text)
        self.assertLess(max(ca.WAIT_S, ca.QUESTION_WAIT_S), ca.HOOK_TIMEOUT_S)


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
        self.assertEqual(allow, dict(hookEventName='PermissionRequest', decision=dict(
            behavior='allow', updatedInput=COMMAND_INPUT['tool_input'])))
        self.assertEqual(ca.decision(request, 'deny')['hookSpecificOutput']['decision']['behavior'], 'deny')
        self.assertIsNone(ca.decision(request, 'ask'))
        updates = ca.decision(request, 'always')['hookSpecificOutput']['decision']['updatedPermissions']
        self.assertEqual(updates, [
            dict(type='addDirectories', directories=[r'C:\work\site'], destination='localSettings'),
            dict(type='addRules', rules=[dict(toolName='Bash', ruleContent='npm test')], behavior='allow',
                 destination='localSettings')])
        self.assertEqual(ca.rule_text(dict(toolName='Bash', ruleContent='npm test')), 'Bash(npm test)')
        self.assertEqual(ca.rule_text(dict(toolName='Edit')), 'Edit')


QUESTION_INPUT = dict(
    session_id='s1', cwd=r'C:\work\site', hook_event_name='PermissionRequest', tool_name='AskUserQuestion',
    tool_input=dict(questions=[
        dict(question='Which database?', header='DB', multiSelect=False,
             options=[dict(label='SQLite', description='Local file'), dict(label='Postgres', description='Server')]),
        dict(question='Which extras?', header='Extras', multiSelect=True,
             options=[dict(label='Auth', description=''), dict(label='Search', description='')])]))


class QuestionTests(unittest.TestCase):
    def test_questions_are_parsed_and_answered(self):
        request = ca.parse_request('f' * 32, json.dumps(QUESTION_INPUT), 5.0)
        self.assertEqual(request['wait'], ca.QUESTION_WAIT_S)
        self.assertFalse(request['can_always'])
        self.assertEqual([(q['question'], q['multi'], [o['label'] for o in q['options']])
                          for q in request['questions']],
                         [('Which database?', False, ['SQLite', 'Postgres']),
                          ('Which extras?', True, ['Auth', 'Search'])])
        answers = {'Which database?': 'Postgres', 'Which extras?': ['Auth', 'Search']}
        body = ca.decision(request, 'answer', answers)['hookSpecificOutput']['decision']
        self.assertEqual(body['behavior'], 'allow')
        self.assertEqual(body['updatedInput'], dict(questions=QUESTION_INPUT['tool_input']['questions'],
                                                    answers=answers))
        self.assertIsNone(ca.decision(request, 'answer', {}))
        self.assertIsNone(ca.decision(request, 'ask'))

    def test_question_without_questions_goes_back_to_claude(self):
        data = dict(QUESTION_INPUT, tool_input=dict(questions=[]))
        self.assertIsNone(ca.parse_request('f' * 32, json.dumps(data), 1))


class PlanTests(unittest.TestCase):
    def test_plan_choices(self):
        data = dict(session_id='s', cwd=r'C:\w\site', hook_event_name='PermissionRequest', tool_name='ExitPlanMode',
                    tool_input=dict(plan='# Plan\n1. Add a file', planFilePath=r'C:\plans\p.md'))
        request = ca.parse_request('e' * 32, json.dumps(data), 1.0)
        self.assertEqual((request['plan'], request['plan_file'], request['wait']),
                         ('# Plan\n1. Add a file', r'C:\plans\p.md', ca.QUESTION_WAIT_S))
        decision = lambda *a: ca.decision(request, *a)['hookSpecificOutput']['decision']
        self.assertEqual(decision('accept'), dict(
            behavior='allow', updatedInput=data['tool_input'],
            updatedPermissions=[dict(type='setMode', mode='default', destination='session')]))
        self.assertEqual(decision('accept_edits')['updatedPermissions'],
                         [dict(type='setMode', mode='acceptEdits', destination='session')])
        revise = decision('revise', 'use SQLite instead')
        self.assertEqual(revise['behavior'], 'deny')
        self.assertIn('use SQLite instead', revise['message'])
        self.assertEqual(decision('revise', '')['behavior'], 'deny')
        self.assertIsNone(ca.decision(request, 'ask'))
        self.assertIn('ExitPlanMode', ca.script_text('x'))


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
