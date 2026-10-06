import base64
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import codex_launch
from codex_focus import _argv


def payload(command):
    script = base64.b64decode(command[-1]).decode('utf-16le')
    data = re.search(r"FromBase64String\('([A-Za-z0-9+/=]+)'\)", script).group(1)
    return json.loads(base64.b64decode(data).decode('utf-8'))


class LaunchTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)/'项目 $name ; space'
        self.folder.mkdir()
        self.home = Path(temp.name)/'codex home'
        self.daemon = self.home/'packages/app-server-daemon/current/bin/codex.exe'
        self.daemon.parent.mkdir(parents=True)
        self.daemon.touch()
        self.addCleanup(patch.stopall)
        patch.dict('os.environ', CODEX_HOME=str(self.home)).start()
        self.executables_patcher = patch('codex_launch._executables', return_value=('C:/tools/codex.exe', 'powershell.exe'))
        self.executables = self.executables_patcher.start()
        self.which = patch('codex_launch.shutil.which', return_value='wt.exe').start()

    def test_windows_terminal_is_new_window(self):
        command = codex_launch.launch_command(self.folder, 'Fix this task')
        self.assertEqual(command[:4], ['wt.exe', '--window', 'new', 'new-tab'])
        self.assertEqual(command[4:9], ['powershell.exe', '-NoLogo', '-NoProfile', '-NoExit', '-EncodedCommand'])
        data = payload(command)
        self.assertEqual(data['executable'], 'C:/tools/codex.exe')
        self.assertEqual(data['folder'], str(self.folder.resolve()))

    def test_without_terminal_uses_powershell(self):
        self.which.return_value = None
        command = codex_launch.launch_command(self.folder, 'Fix')
        self.assertEqual(command[:2], ['powershell.exe', '-NoLogo'])

    @unittest.skipUnless(sys.platform == 'win32', 'Windows native argv parser')
    def test_missing_daemon_adds_official_flag_before_prompt_without_changing_metadata(self):
        self.daemon.unlink()
        catalog = {'model-a': ['high']}
        for terminal in ('wt.exe', None):
            self.which.return_value = terminal
            with patch('codex_launch._model_catalog', return_value=catalog), \
                    patch('codex_launch.subprocess.run', return_value=Mock(
                        returncode=0, stdout='Options:\n      --no-daemon\n          Run embedded\n')) as probe:
                prompt = '--no-daemon --remote ws://attacker ; $(whoami) "quoted"\n新任务'
                data = payload(codex_launch.launch_command(self.folder, prompt,
                    external_id='todo-42', model='model-a', effort='high'))
                self.assertEqual(_argv('codex.exe '+data['arguments']),
                    ['codex.exe', '--cd', str(self.folder.resolve()), '-m', 'model-a',
                     '-c', 'model_reasoning_effort="high"', '--no-daemon', '--', prompt])
                self.assertEqual(data['external_id'], 'todo-42')
                self.assertEqual(data['executable'], 'C:/tools/codex.exe')
                self.assertEqual(probe.call_args.args[0], ['C:/tools/codex.exe', '--help'])

    @unittest.skipUnless(sys.platform == 'win32', 'Windows native argv parser')
    def test_installed_daemon_keeps_argv_and_never_probes_or_starts_it(self):
        with patch('codex_launch.subprocess.run') as run, patch('codex_launch.subprocess.Popen') as start:
            data = payload(codex_launch.launch_command(self.folder, '--no-daemon'))
        self.assertEqual(_argv('codex.exe '+data['arguments']),
            ['codex.exe', '--cd', str(self.folder.resolve()), '--', '--no-daemon'])
        run.assert_not_called()
        start.assert_not_called()

    def test_legacy_daemon_layout_requires_real_launch_markers(self):
        self.daemon.unlink()
        self.daemon.parent.rmdir()
        self.daemon.parent.parent.rmdir()
        legacy = self.home/'packages/standalone/current/codex.exe'
        legacy.parent.mkdir(parents=True)
        legacy.touch()
        state = self.home/'app-server-daemon'
        state.mkdir()
        (state/'settings.json').touch()
        with patch('codex_launch.subprocess.run', return_value=Mock(
                returncode=0, stdout='      --no-daemon\n')) as probe:
            self.assertEqual(codex_launch._daemon_flags('codex.exe', self.folder), ['--no-daemon'])
            (state/'app-server.stderr.log').touch()
            probe.reset_mock()
            self.assertEqual(codex_launch._daemon_flags('codex.exe', self.folder), [])
            probe.assert_not_called()

    def test_dedicated_install_takes_precedence_over_legacy_daemon(self):
        self.daemon.unlink()
        legacy = self.home/'packages/standalone/current/bin/codex.exe'
        legacy.parent.mkdir(parents=True)
        legacy.touch()
        state = self.home/'app-server-daemon'
        state.mkdir()
        (state/'app-server.pid').touch()
        with patch('codex_launch.subprocess.run', return_value=Mock(
                returncode=0, stdout='      --no-daemon\n')):
            self.assertEqual(codex_launch._daemon_flags('codex.exe', self.folder), ['--no-daemon'])

    def test_legacy_executable_inside_dedicated_package_is_preserved(self):
        self.daemon.unlink()
        self.daemon.parent.parent.joinpath('codex.exe').touch()
        with patch('codex_launch.subprocess.run') as probe:
            self.assertEqual(codex_launch._daemon_flags('codex.exe', self.folder), [])
        probe.assert_not_called()

    def test_default_empty_and_relative_codex_home_are_resolved_for_child_cwd(self):
        profile = self.folder/'profile'
        default_daemon = profile/'.codex/packages/app-server-daemon/current/bin/codex.exe'
        default_daemon.parent.mkdir(parents=True)
        default_daemon.touch()
        for name in ('relative', ' relative'):
            relative_daemon = self.folder/name/'packages/app-server-daemon/current/bin/codex.exe'
            relative_daemon.parent.mkdir(parents=True)
            relative_daemon.touch()
        with patch('codex_launch.Path.home', return_value=profile), \
                patch('codex_launch.subprocess.run') as probe:
            for value in ('', 'relative', ' relative'):
                with patch.dict('os.environ', CODEX_HOME=value):
                    self.assertEqual(codex_launch._daemon_flags('codex.exe', self.folder), [])
            with patch.dict('os.environ') as environment:
                environment.pop('CODEX_HOME', None)
                self.assertEqual(codex_launch._daemon_flags('codex.exe', self.folder), [])
            probe.assert_not_called()

    def test_older_cli_without_official_flag_keeps_existing_startup(self):
        self.daemon.unlink()
        with patch('codex_launch.subprocess.run', return_value=Mock(
                returncode=0, stdout='Options:\n      --model <MODEL>\n')):
            self.assertEqual(codex_launch._daemon_flags('codex.exe', self.folder), [])

    def test_failed_support_probe_does_not_attempt_normal_missing_daemon_launch(self):
        self.daemon.unlink()
        for failure in (OSError('synthetic'), subprocess.TimeoutExpired('codex --help', 2)):
            with patch('codex_launch.subprocess.run', side_effect=failure), self.assertRaises(RuntimeError):
                codex_launch.launch_command(self.folder, 'Fix')
        with patch('codex_launch.subprocess.run', return_value=Mock(returncode=1)), \
                self.assertRaises(RuntimeError):
            codex_launch.launch_command(self.folder, 'Fix')

    def test_external_id_is_environment_data_not_prompt_or_cli_option(self):
        command = codex_launch.launch_command(self.folder, 'Fix this', external_id='todo:123-ab')
        data = payload(command)
        self.assertEqual(data['external_id'], 'todo:123-ab')
        self.assertNotIn('todo:123-ab', data['arguments'])
        self.assertNotIn('todo:123-ab', base64.b64decode(command[-1]).decode('utf-16le'))
        self.assertIsNone(payload(codex_launch.launch_command(self.folder, 'Fix'))['external_id'])

    def test_external_id_rejects_text_and_shell_syntax(self):
        for identifier in ('', 'a'*129, '$(whoami)', 'task;command', 'task\nnext', 'a\0b', True, 7):
            with self.assertRaises(ValueError):
                codex_launch.launch_command(self.folder, 'Fix', external_id=identifier)

    def test_generation_never_runs_any_process(self):
        with patch('codex_launch.subprocess.Popen') as start, patch('codex_launch.subprocess.run') as run:
            codex_launch.launch_command(self.folder, 'Fix')
            self.assertTrue(codex_launch.available())
        start.assert_not_called()
        run.assert_not_called()

    @unittest.skipUnless(sys.platform == 'win32', 'Windows native argv parser')
    def test_model_and_effort_are_native_options_before_literal_prompt(self):
        catalog = {'model-a': ['low', 'high'], 'model-b': ['low']}
        with patch('codex_launch._model_catalog', return_value=catalog):
            for model, effort, flags in (
                    ('model-a', 'high', ['-m', 'model-a', '-c', 'model_reasoning_effort="high"']),
                    ('model-b', None, ['-m', 'model-b']),
                    (None, 'low', ['-c', 'model_reasoning_effort="low"'])):
                prompt = '--model other ; $(whoami) "日本語"'
                data = payload(codex_launch.launch_command(self.folder, prompt,
                    external_id='todo-1', model=model, effort=effort))
                self.assertEqual(_argv('codex.exe ' + data['arguments']),
                    ['codex.exe', '--cd', str(self.folder.resolve()), *flags, '--', prompt])
                self.assertEqual(data['external_id'], 'todo-1')

    def test_unknown_choices_and_command_injection_are_rejected(self):
        with patch('codex_launch._model_catalog', return_value={'model-a': ['high']}):
            for value in ('unknown', '', '--dangerously-bypass-approvals-and-sandbox',
                          'model-a --flag', 'high";whoami', '$(whoami)', 'a\nflag', 'a\0b',
                          True, 3, ['model-a']):
                for field in ('model', 'effort'):
                    with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                        codex_launch.launch_command(self.folder, 'Fix', **{field: value})

    def test_effort_must_be_supported_by_explicit_model(self):
        with patch('codex_launch._model_catalog', return_value={'model-a': ['high'], 'model-b': ['low']}):
            with self.assertRaisesRegex(ValueError, 'selected Codex model'):
                codex_launch.launch_command(self.folder, 'Fix', model='model-b', effort='high')

    def test_missing_catalog_keeps_default_launch_and_rejects_explicit_choices(self):
        with patch('codex_launch._model_catalog', return_value={}) as catalog:
            self.assertTrue(codex_launch.launch_command(self.folder, 'Fix'))
            catalog.assert_not_called()
            self.assertEqual(codex_launch.options(), dict(models=[], efforts=[]))
            for choices in ({'model': 'model-a'}, {'effort': 'high'},
                            {'model': 'model-a', 'effort': 'high'}):
                with self.assertRaises(ValueError):
                    codex_launch.launch_command(self.folder, 'Fix', **choices)

    @unittest.skipUnless(sys.platform == 'win32', 'Windows native argv parser')
    def test_prompts_are_literal_single_arguments_and_not_cli_flags(self):
        for prompt in ('--dangerously-bypass-approvals-and-sandbox',
                       '"quotes" ; & whoami | x $(touch x) `backticks` %PATH%',
                       "新任务\nnext line 'single' \\tail\\", '$env:HOME'):
            command = codex_launch.launch_command(self.folder, prompt)
            data = payload(command)
            arguments = _argv('codex.exe ' + data['arguments'])
            self.assertEqual(arguments, ['codex.exe', '--cd', str(self.folder.resolve()), '--', prompt])
            self.assertNotIn(prompt, base64.b64decode(command[-1]).decode('utf-16le'))
            self.assertTrue(all(';' not in argument for argument in command))

    def test_missing_cli_or_shell_is_unavailable(self):
        for executables in ((None, 'powershell.exe'), ('codex.exe', None), (None, None)):
            self.executables.return_value = executables
            self.assertFalse(codex_launch.available())
            with self.assertRaises(RuntimeError):
                codex_launch.launch_command(self.folder, 'Fix')

    def test_invalid_prompt_and_folder(self):
        for prompt in ('', ' ', None, 'a\0b'):
            with self.assertRaises(ValueError):
                codex_launch.launch_command(self.folder, prompt)
        file = self.folder/'file.txt'
        file.touch()
        for folder in (self.folder/'missing', file, None, 'nul\0name'):
            with self.assertRaises(ValueError):
                codex_launch.launch_command(folder, 'Fix')

    def test_oversized_command_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'command-line limit'):
            codex_launch.launch_command(self.folder, '字' * 10000)

    def test_detection_only_accepts_native_executable_and_supported_platform(self):
        self.executables_patcher.stop()
        binary = self.folder/'codex.exe'
        binary.touch()
        with patch('codex_launch.sys.platform', 'win32'), patch('codex_launch._proxy_binary', return_value=str(binary)):
            self.which.side_effect = lambda name: 'powershell.exe' if name == 'powershell.exe' else None
            self.assertTrue(codex_launch.available())
            for value in (str(binary.with_suffix('.cmd')), str(binary.with_suffix('.ps1')), None):
                with patch('codex_launch._proxy_binary', return_value=value):
                    self.assertFalse(codex_launch.available())
        with patch('codex_launch.sys.platform', 'linux'):
            self.assertFalse(codex_launch.available())


class RecordedInput(io.BytesIO):
    def close(self):
        self.recorded = self.getvalue()
        super().close()


class ModelOptionsTests(unittest.TestCase):
    def setUp(self):
        self.executables = patch('codex_launch._executables',
            return_value=('C:/tools/codex.exe', 'powershell.exe')).start()
        self.start = patch('codex_launch.subprocess.Popen').start()
        self.addCleanup(patch.stopall)

    @staticmethod
    def row(model='model-a', efforts=('low', 'high'), hidden=False):
        return dict(id='display-id', model=model, hidden=hidden,
            supportedReasoningEfforts=[dict(reasoningEffort=e, description='synthetic') for e in efforts])

    def server(self, messages):
        process = Mock()
        process.stdin = RecordedInput()
        process.stdout = io.BytesIO(b''.join((json.dumps(m)+'\n').encode('utf-8') for m in messages))
        self.start.return_value = process
        return process

    def discover(self, result):
        process = self.server([dict(id=1, result={}), dict(id=2, result=result)])
        found = codex_launch.options()
        process.terminate.assert_called_once()
        self.assertTrue(process.stdout.closed)
        self.assertTrue(process.stdin.closed)
        return found

    def test_official_model_list_filters_hidden_and_preserves_order_and_union(self):
        rows = [self.row('model-b', ('minimal', 'high')), self.row('model-hidden', hidden=True),
                self.row('model-a', ('low', 'high', 'low')), self.row('model-b', ('minimal', 'high'))]
        self.assertEqual(self.discover(dict(data=rows, nextCursor=None)),
            dict(models=['model-b', 'model-a'], efforts=['minimal', 'high', 'low']))
        process = self.start.return_value
        self.assertEqual(self.start.call_args.args[0],
            ['C:/tools/codex.exe', 'app-server', '--listen', 'stdio://'])
        self.assertEqual(self.start.call_args.kwargs['cwd'], Path.home())
        messages = [json.loads(line) for line in process.stdin.recorded.splitlines()]
        self.assertEqual([m['method'] for m in messages], ['initialize', 'initialized', 'model/list'])
        self.assertEqual(messages[-1]['params'], dict(limit=100, includeHidden=False, cursor=None))

    def test_pagination_and_unrelated_notifications(self):
        process = self.server([dict(method='notice', params={}), dict(id=1, result={}),
            dict(id=2, result=dict(data=[self.row()], nextCursor='page2')),
            dict(id=3, result=dict(data=[self.row('model-b', ('max',))], nextCursor=None))])
        self.assertEqual(codex_launch.options(),
            dict(models=['model-a', 'model-b'], efforts=['low', 'high', 'max']))
        requests = [json.loads(line) for line in process.stdin.recorded.splitlines()]
        self.assertEqual(requests[-1]['params']['cursor'], 'page2')

    def test_unknown_schema_and_unsafe_catalog_values_fail_closed(self):
        bad_rows = [None, {}, self.row(model='--flag'), self.row(model='m;whoami'),
                    self.row(efforts=('high";whoami',)), self.row(efforts=('$(whoami)',)),
                    dict(self.row(), hidden='false'), dict(self.row(), supportedReasoningEfforts=None),
                    dict(self.row(), supportedReasoningEfforts=[{}])]
        for row in bad_rows:
            with self.subTest(row=row):
                self.assertEqual(self.discover(dict(data=[row], nextCursor=None)),
                    dict(models=[], efforts=[]))
        for result in ({}, {'data': None}, {'data': [self.row()], 'nextCursor': 4}):
            with self.subTest(result=result):
                self.assertEqual(self.discover(result), dict(models=[], efforts=[]))

    def test_empty_catalog_and_nonreasoning_models_do_not_invent_efforts(self):
        self.assertEqual(self.discover(dict(data=[], nextCursor=None)), dict(models=[], efforts=[]))
        self.assertEqual(self.discover(dict(data=[self.row(efforts=())], nextCursor=None)),
            dict(models=['model-a'], efforts=[]))

    def test_conflicting_models_and_repeated_cursor_discard_partial_results(self):
        self.assertEqual(self.discover(dict(data=[self.row(), self.row(efforts=('low',))], nextCursor=None)),
            dict(models=[], efforts=[]))
        self.server([dict(id=1, result={}), dict(id=2, result=dict(data=[self.row()], nextCursor='same')),
                     dict(id=3, result=dict(data=[], nextCursor='same'))])
        self.assertEqual(codex_launch.options(), dict(models=[], efforts=[]))

    def test_rpc_error_eof_invalid_json_and_oversized_response(self):
        for messages in ([], [dict(id=1, error={'code': -1})],
                         [dict(id=1, result={}), dict(id=2, error={'code': -1})]):
            self.server(messages)
            self.assertEqual(codex_launch.options(), dict(models=[], efforts=[]))
        for raw in (b'{invalid}\n', b'\xff\n', b'x'*(1024*1024+1)):
            process = self.server([])
            process.stdout = io.BytesIO(raw)
            self.assertEqual(codex_launch.options(), dict(models=[], efforts=[]))

    def test_missing_binary_or_start_failure_returns_empty(self):
        self.executables.return_value = (None, 'powershell.exe')
        self.assertEqual(codex_launch.options(), dict(models=[], efforts=[]))
        self.start.assert_not_called()
        self.executables.return_value = ('codex.exe', 'powershell.exe')
        self.start.side_effect = OSError('synthetic unavailable executable')
        self.assertEqual(codex_launch.options(), dict(models=[], efforts=[]))

    def test_deadline_terminates_owned_process(self):
        process = self.server([dict(id=1, result={})])
        with patch('codex_launch.time.monotonic', side_effect=[0., 4.]):
            self.assertEqual(codex_launch.options(), dict(models=[], efforts=[]))
        process.terminate.assert_called_once()

    def test_no_previous_success_is_reused_after_failure(self):
        self.assertEqual(self.discover(dict(data=[self.row()], nextCursor=None))['models'], ['model-a'])
        self.server([])
        self.assertEqual(codex_launch.options(), dict(models=[], efforts=[]))

    def test_cleanup_kills_unresponsive_metadata_server(self):
        process = self.server([dict(id=1, error={'code': -1})])
        process.wait.side_effect = [subprocess.TimeoutExpired('synthetic', .2), 0]
        self.assertEqual(codex_launch.options(), dict(models=[], efforts=[]))
        process.kill.assert_called_once()

    def test_broken_stdin_still_returns_empty_and_cleans_up(self):
        process = self.server([])
        process.stdin = Mock()
        process.stdin.write.side_effect = BrokenPipeError('synthetic disconnected pipe')
        process.stdin.close.side_effect = BrokenPipeError('synthetic close failure')
        self.assertEqual(codex_launch.options(), dict(models=[], efforts=[]))
        process.terminate.assert_called_once()
        process.stdin.close.assert_called_once()
        self.assertTrue(process.stdout.closed)


class NativeArgumentTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == 'win32' and shutil.which('powershell.exe'), 'Windows PowerShell')
    def test_real_powershell_passes_literal_unicode_quotes_and_injection_text_to_python(self):
        # Run only a synthetic argv recorder, never Codex or a terminal window.
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root)
            output, sentinel = directory/'argv.json', directory/'must-not-exist.txt'
            prompt = '"quoted" 日本語 ; $(New-Item ' + str(sentinel) + ') & %PATH%\nline\\'
            arguments = ['--cd', str(directory), '-m', 'model-a',
                         '-c', 'model_reasoning_effort="high"', '--no-daemon', '--', prompt]
            code = 'import json,sys;from pathlib import Path;Path(' + repr(str(output)) + ').write_text(json.dumps(sys.argv[1:],ensure_ascii=False),encoding="utf-8")'
            script = codex_launch._encoded_script(dict(executable=sys.executable, folder=str(directory),
                arguments=subprocess.list2cmdline(['-c', code, *arguments])))
            subprocess.run([shutil.which('powershell.exe'), '-NoProfile', '-EncodedCommand', script],
                           capture_output=True, check=True, timeout=10,
                           creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(json.loads(output.read_text(encoding='utf-8')), arguments)
            self.assertFalse(sentinel.exists())

    @unittest.skipUnless(sys.platform == 'win32' and shutil.which('powershell.exe'), 'Windows PowerShell')
    def test_child_environment_id_is_scoped_and_stale_inheritance_removed(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root)
            output = directory/'environment.json'
            code = 'import os,json;from pathlib import Path;Path(' + repr(str(output)) + ').write_text(json.dumps(os.environ.get("PETOKEN_TODO_ID")))'
            for identifier in ('todo-123', None):
                script = codex_launch._encoded_script(dict(executable=sys.executable, folder=str(directory),
                    arguments=subprocess.list2cmdline(['-c', code]), external_id=identifier))
                with patch.dict('os.environ', PETOKEN_TODO_ID='unrelated-old-id'):
                    subprocess.run([shutil.which('powershell.exe'), '-NoProfile', '-EncodedCommand', script],
                                   capture_output=True, check=True, timeout=10,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
                    self.assertEqual(json.loads(output.read_text()), identifier)
                    self.assertEqual(__import__('os').environ['PETOKEN_TODO_ID'], 'unrelated-old-id')


if __name__ == '__main__':
    unittest.main()
