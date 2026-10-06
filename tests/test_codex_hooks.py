import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

import codex_hooks as hooks


class InstallationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.path = self.home / 'hooks.json'
        self.script = self.home / "'script %name.ps1"
        self.target = self.home / 'data'

    def enable(self):
        return hooks.enable(self.home, script=self.script, target=self.target)

    def test_install_disable_preserve_other_hooks_and_config(self):
        original = dict(description='user', hooks=dict(Stop=[dict(matcher='.*', hooks=[dict(
            type='command', command='user-script')])]), other={'unchanged': True})
        self.path.write_text(json.dumps(original), encoding='utf-8')
        toml = self.home / 'config.toml'
        toml.write_text('notify = ["existing"]\n', encoding='utf-8')
        self.assertEqual(self.enable(), 'on')
        data = json.loads(self.path.read_text())
        self.assertEqual(data['hooks']['Stop'][0], original['hooks']['Stop'][0])
        self.assertEqual(toml.read_text(), 'notify = ["existing"]\n')
        self.assertEqual(len(list(self.home.glob('hooks.json.petoken-backup-*'))), 1)
        self.assertEqual(self.enable(), 'on')
        self.assertEqual(len(list(self.home.glob('hooks.json.petoken-backup-*'))), 1)
        self.assertEqual(hooks.disable(self.home), 'off')
        self.assertEqual(json.loads(self.path.read_text()), original)
        self.assertEqual(len(list(self.home.glob('hooks.json.petoken-backup-*'))), 2)

    def test_mixed_group_retains_user_handler_and_metadata(self):
        self.enable()
        data = json.loads(self.path.read_text())
        group = data['hooks']['Stop'][0]
        group['matcher'] = 'user matcher'
        group['hooks'].append(dict(type='command', command='user'))
        self.path.write_text(json.dumps(data))
        self.assertEqual(hooks.disable(self.home), 'off')
        self.assertEqual(json.loads(self.path.read_text())['hooks']['Stop'],
                         [dict(matcher='user matcher', hooks=[dict(type='command', command='user')])])

    def test_malformed_config_is_not_overwritten(self):
        for raw in ('invalid', '[]', '{"hooks":null}', '{"hooks":{"Stop":{}}}',
                    '{"hooks":{"Stop":[{"hooks":[false]}]}}'):
            with self.subTest(raw=raw):
                self.path.write_text(raw)
                self.assertEqual(self.enable(), 'unreadable')
                self.assertEqual(hooks.disable(self.home), 'unreadable')
                self.assertEqual(self.path.read_text(), raw)

    def test_state_partial_and_only_configured_not_trusted(self):
        self.assertEqual(hooks.state(self.home), 'off')
        self.enable()
        data = json.loads(self.path.read_text())
        del data['hooks']['Stop']
        self.path.write_text(json.dumps(data))
        self.assertEqual(hooks.state(self.home), 'partial')
        self.assertFalse((self.home / 'hook-trust.json').exists())

    def test_unowned_similar_name_is_not_removed(self):
        data = dict(hooks=dict(Stop=[dict(hooks=[dict(type='command', command='codex-hooks.ps1',
            statusMessage=hooks.MARKER)])]))
        self.path.write_text(json.dumps(data))
        self.assertEqual(hooks.disable(self.home), 'off')
        self.assertEqual(json.loads(self.path.read_text()), data)

    def test_concurrent_edit_detected(self):
        self.path.write_text('{}')
        with self.assertRaises(OSError):
            hooks._write(self.path, {'hooks': {}}, b'older')
        self.assertEqual(self.path.read_text(), '{}')

    def test_unowned_script_is_preserved_and_updates_change_definition_hash(self):
        self.script.write_text('user script')
        self.assertEqual(self.enable(), 'unreadable')
        self.assertEqual(self.script.read_text(), 'user script')
        self.assertFalse(self.path.exists())
        self.script.unlink()
        self.enable()
        command = json.loads(self.path.read_text())['hooks']['Stop'][0]['hooks'][0]['command']
        with patch('codex_hooks._SCRIPT', hooks._SCRIPT+'\n# update\n'):
            self.enable()
        updated = json.loads(self.path.read_text())['hooks']['Stop'][0]['hooks'][0]['command']
        self.assertNotEqual(command, updated)


class EventTests(unittest.TestCase):
    def record(self, event='Stop', **extra):
        return dict(at=100., event=event, session='synthetic-thread', turn='turn1',
                    project='project', **extra)

    def test_normalized_contract_and_explicit_failure(self):
        for event, kind in (('Stop', 'finished'), ('PermissionRequest', 'needs_approval'),
                            ('UserPromptSubmit', 'started')):
            result = hooks.normalize(self.record(event))
            self.assertEqual(result['kind'], kind)
            self.assertEqual(result['provider'], 'codex')
            self.assertEqual(result['task_key'], 'synthetic-thread')
            self.assertEqual(set(result), {'kind','provider','task_key','at','project','detail','dedupe','source'})
        result = hooks.normalize(self.record('turn/completed', kind='failed'))
        self.assertEqual(result['kind'], 'failed')
        self.assertEqual(result['source'], 'app-server')

    def test_unknowns_and_interrupt_not_task_failure(self):
        for record in (None, [], {}, self.record('Interrupt'), self.record('SessionEnd'),
                       self.record('PostToolUse'), self.record('StopFailure'),
                       self.record('turn/completed', kind='interrupted')):
            self.assertIsNone(hooks.normalize(record))
        for at in (True, None, -1, math.nan, math.inf, '100', 10**400):
            self.assertIsNone(hooks.normalize(dict(self.record(), at=at)))

    def test_no_dialogue_or_paths_in_normalized_event(self):
        record = dict(self.record(), project=r'C:\secret\project', prompt='secret text',
                      last_assistant_message='secret', tool_input={'command':'secret'})
        result = hooks.normalize(record)
        self.assertEqual(result['project'], 'project')
        self.assertNotIn('secret', json.dumps(result))

    def test_tail_skips_history_and_waits_for_complete_line(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'events'
            path.write_text(json.dumps(self.record()) + '\n')
            reader = hooks.CodexEventReader(path)
            self.assertEqual(reader.poll(), [])
            with path.open('a') as stream:
                stream.write(json.dumps(self.record('UserPromptSubmit')))
            self.assertEqual(reader.poll(), [])
            with path.open('a') as stream:
                stream.write('\ninvalid\n')
            self.assertEqual([e['kind'] for e in reader.poll()], ['started'])
            path.write_text('{}\n')
            self.assertEqual(reader.poll(), [])

    def test_tail_handles_initial_missing_file_and_replacement(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'events'
            reader = hooks.CodexEventReader(path)
            self.assertEqual(reader.poll(), [])
            path.write_text(json.dumps(self.record()) + '\n')
            self.assertEqual(len(reader.poll()), 1)
            new = path.with_suffix('.new')
            new.write_text(json.dumps(self.record('UserPromptSubmit')) + '\n')
            new.replace(path)
            self.assertEqual([e['kind'] for e in reader.poll()], ['started'])

    def test_explicit_launch_binding_is_separate_and_does_not_start_work(self):
        record = self.record('SessionStart', kind='startup', external_id='todo-123')
        self.assertIsNone(hooks.normalize(record))
        self.assertEqual(hooks.launch_binding(record), dict(thread_id='synthetic-thread',
            external_id='todo-123', at=100., project='project'))
        for bad in (dict(record, kind='resume'), dict(record, external_id=None), dict(record, at=None)):
            self.assertIsNone(hooks.launch_binding(bad))
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)/'events'
            reader = hooks.CodexEventReader(path)
            reader.poll()
            path.write_text(json.dumps(record)+'\n'+json.dumps(self.record())+'\n')
            self.assertEqual([e['kind'] for e in reader.poll()], ['finished'])
            self.assertEqual(reader.launch_bindings, [hooks.launch_binding(record)])
            reader.poll()
            self.assertEqual(reader.launch_bindings, [])


@unittest.skipUnless(os.name == 'nt' and shutil.which('powershell.exe'), 'Windows PowerShell')
class ScriptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.folder = self.root / 'claude-approvals'
        self.folder.mkdir()
        self.script = self.root / 'script.ps1'
        self.script.write_text(hooks._SCRIPT, encoding='utf-8-sig')
        self.request = dict(hook_event_name='PermissionRequest', session_id='synthetic',
            turn_id='turn1', cwd=r'D:\project', tool_name='Bash',
            tool_input=dict(command='echo synthetic', description='synthetic approval'),
            prompt='secret prompt', last_assistant_message='secret reply')

    def start(self, data=None):
        process = subprocess.Popen([shutil.which('powershell.exe'), '-NoProfile', '-File',
            str(self.script), '-DataDir', str(self.root)], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
        self.addCleanup(lambda: process.kill() if process.poll() is None else None)
        process.stdin.write(json.dumps(data or self.request).encode('utf-8'))
        process.stdin.close()
        process.stdin = None
        return process

    def wait_request(self, process):
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            paths = list(self.folder.glob('*.request.json'))
            if paths:
                return paths[0]
            if process.poll() is not None:
                self.fail('Hook exited before publishing synthetic request')
            time.sleep(.03)
        self.fail('Hook failed to publish synthetic request')

    def finish(self, process):
        stdout, stderr = process.communicate(timeout=8)
        self.assertEqual(process.returncode, 0)
        self.assertEqual(stderr, b'')
        return stdout

    def test_allow_deny_strip_claude_only_fields(self):
        for behavior in ('allow', 'deny'):
            (self.folder / 'alive').touch()
            process = self.start()
            path = self.wait_request(process)
            data = json.loads(path.read_text())
            self.assertEqual(data['provider'], 'codex')
            self.assertEqual(data['tool_input'], self.request['tool_input'])
            self.assertEqual(int(path.with_name(path.name.replace('.request.json','.pid')).read_text()), process.pid)
            decision = dict(behavior=behavior, message='synthetic', updatedInput={'bad':True},
                            updatedPermissions=[{'bad':True}], interrupt=True)
            path.with_name(path.name.replace('.request.json','.decision.json')).write_text(json.dumps(
                {'hookSpecificOutput': {'decision': decision}}))
            output = json.loads(self.finish(process))
            self.assertEqual(output, {'hookSpecificOutput': {'hookEventName':'PermissionRequest',
                'decision': {'behavior':behavior,'message':'synthetic'}}})
            self.assertEqual(list(self.folder.glob('*.json')), [])
            events = (self.root / hooks.EVENTS_NAME).read_text()
            for secret in ('secret prompt','secret reply','echo synthetic',r'D:\project'):
                self.assertNotIn(secret, events)

    def test_receiver_missing_or_stale_returns_immediately(self):
        for age in (None, 11):
            if age is not None:
                (self.folder / 'alive').touch()
                os.utime(self.folder / 'alive', (time.time()-age,)*2)
            self.assertEqual(self.finish(self.start()), b'')
            self.assertEqual(list(self.folder.glob('*.json')), [])

    def test_empty_invalid_decision_hand_back_without_answer(self):
        for raw in ('', '{bad', '{}', '{"hookSpecificOutput":{"decision":{"behavior":"future"}}}'):
            (self.folder / 'alive').touch()
            process = self.start()
            path = self.wait_request(process)
            path.with_name(path.name.replace('.request.json','.decision.json')).write_text(raw)
            self.assertEqual(self.finish(process), b'')

    def test_receiver_disappears_while_waiting(self):
        (self.folder / 'alive').touch()
        process = self.start()
        self.wait_request(process)
        (self.folder / 'alive').unlink()
        self.assertEqual(self.finish(process), b'')
        self.assertEqual(list(self.folder.glob('*.json')), [])

    def test_timeout_returns_to_codex(self):
        self.assertIn('$watch.Elapsed.TotalSeconds -lt 45', hooks._SCRIPT)
        self.script.write_text(hooks._SCRIPT.replace('$watch.Elapsed.TotalSeconds -lt 45',
            '$watch.Elapsed.TotalSeconds -lt 0.3'), encoding='utf-8-sig')
        (self.folder / 'alive').touch()
        self.assertEqual(self.finish(self.start()), b'')
        self.assertEqual(list(self.folder.glob('*.json')), [])

    def test_lifecycle_is_metadata_only(self):
        data = dict(self.request, hook_event_name='Stop')
        self.assertEqual(self.finish(self.start(data)), b'')
        record = json.loads((self.root / hooks.EVENTS_NAME).read_text())
        self.assertEqual(record['event'], 'Stop')
        self.assertEqual(record['project'], 'project')
        self.assertNotIn('secret', json.dumps(record))

    def test_installed_encoded_handler_runs_with_quoted_paths(self):
        home = self.root / 'home'
        script = self.root / "script ' %NAME%.ps1"
        self.assertEqual(hooks.enable(home, script=script, target=self.root), 'on')
        handler = json.loads((home/'hooks.json').read_text())['hooks']['Stop'][0]['hooks'][0]
        result = subprocess.run(handler['command'].split(), input=json.dumps(dict(self.request,
            hook_event_name='Stop')).encode(), capture_output=True, timeout=8,
            creationflags=subprocess.CREATE_NO_WINDOW)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b'', b''))
        self.assertEqual(json.loads((self.root/hooks.EVENTS_NAME).read_text())['session'], 'synthetic')

    def test_unsupported_permission_input_is_handed_back(self):
        (self.folder/'alive').touch()
        self.assertEqual(self.finish(self.start(dict(self.request,
            tool_name='request_permissions', tool_input={'permissions': {'network': True}}))), b'')
        self.assertEqual(list(self.folder.glob('*.json')), [])

    def test_concurrent_hooks_keep_lines_separate(self):
        processes = [self.start(dict(self.request, hook_event_name='Stop',
            session_id=f'session-{i}')) for i in range(6)]
        for process in processes:
            self.assertEqual(self.finish(process), b'')
        records = [json.loads(l) for l in (self.root/hooks.EVENTS_NAME).read_text().splitlines()]
        self.assertEqual({r['session'] for r in records}, {f'session-{i}' for i in range(6)})

    def test_only_new_session_captures_explicit_environment_id(self):
        for source in ('startup', 'resume', 'compact'):
            with patch.dict(os.environ, PETOKEN_TODO_ID='todo-123'):
                self.assertEqual(self.finish(self.start(dict(self.request,
                    hook_event_name='SessionStart', source=source))), b'')
        records = [json.loads(l) for l in (self.root/hooks.EVENTS_NAME).read_text().splitlines()]
        self.assertEqual(records[0]['external_id'], 'todo-123')
        self.assertNotIn('external_id', records[1])
        self.assertNotIn('external_id', records[2])


if __name__ == '__main__':
    unittest.main()
