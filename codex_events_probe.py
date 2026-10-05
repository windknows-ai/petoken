"""Opt-in, offline protocol experiment with a real Codex binary and fake local API.

Never uses real CODEX_HOME, credentials, conversations or an inference service.
Artifacts stay in a caller-selected experiment folder. Not imported by Petoken.
"""
import argparse
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from codex_events import normalize_event


class Backend(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_POST(self):
        request = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.server.calls.append(dict(at_ns=time.perf_counter_ns(), keys=sorted(request), tool_schemas=request.get('tools', [])))
        if self.server.scenario == 'failure':
            self.send_response(400)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.server.terminal_ns = time.perf_counter_ns()
            self.wfile.write(b'{"error":{"message":"Synthetic probe failure","type":"invalid_request_error","code":"probe"}}')
            return
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('x-codex-primary-used-percent', str(self.server.percent))
        self.send_header('x-codex-primary-window-minutes', '300')
        self.send_header('x-codex-primary-reset-after-seconds', '3600')
        self.server.quota_ns = time.perf_counter_ns()
        self.end_headers()
        response = dict(id='resp_probe', model='gpt-6.1-sol', status='in_progress', output=[])
        self.event('response.created', response=response)
        if self.server.scenario == 'approval':
            item = dict(type='function_call', id='fc_probe', call_id='call_probe', name='exec_command',
                        arguments=json.dumps(dict(cmd='Write-Output Petoken-Probe',
                            sandbox_permissions='require_escalated', justification='Synthetic confirmation probe')))
        else:
            item = dict(type='message', id='msg_probe', role='assistant', phase='final_answer',
                        content=[dict(type='output_text', text='Petoken probe OK', annotations=[])])
        self.event('response.output_item.added', output_index=0, item=item)
        self.event('response.output_item.done', output_index=0, item=item)
        response.update(status='completed', output=[item], usage=dict(input_tokens=100, output_tokens=10, total_tokens=110,
            input_tokens_details=dict(cached_tokens=0), output_tokens_details=dict(reasoning_tokens=0)))
        self.server.terminal_ns = time.perf_counter_ns()
        self.event('response.completed', response=response)

    def event(self, kind, **fields):
        self.wfile.write(('data: '+json.dumps(dict(type=kind, **fields))+'\n\n').encode())
        self.wfile.flush()


class Client:
    def __init__(self, binary, home, cwd):
        env = dict(os.environ, CODEX_HOME=str(home))
        for key in ('OPENAI_API_KEY', 'CODEX_API_KEY', 'OPENAI_BASE_URL', 'CODEX_REMOTE_TOKEN'):
            env.pop(key, None)
        self.proc = subprocess.Popen([str(binary), 'app-server', '--listen', 'stdio://'],
            env=env, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding='utf-8', creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.messages = queue.Queue()
        self.seen = []
        self.errors = []
        threading.Thread(target=self.read, daemon=True).start()
        threading.Thread(target=lambda: self.errors.extend(self.proc.stderr.read().splitlines()), daemon=True).start()

    def read(self):
        for line in self.proc.stdout:
            try:
                message = json.loads(line)
            except ValueError:
                continue
            stamped = (time.perf_counter_ns(), message)
            self.seen.append(stamped)
            self.messages.put(stamped)

    def send(self, message):
        self.proc.stdin.write(json.dumps(message)+'\n')
        self.proc.stdin.flush()

    def wait(self, predicate, timeout=30):
        deadline = time.monotonic()+timeout
        while time.monotonic() < deadline:
            stamped = self.messages.get(timeout=max(.01, deadline-time.monotonic()))
            if predicate(stamped[1]):
                return stamped
        raise TimeoutError('Protocol response not received')

    def request(self, number, method, params):
        self.send(dict(id=number, method=method, params=params))
        _, response = self.wait(lambda m: m.get('id') == number and 'method' not in m)
        if 'error' in response:
            raise RuntimeError(json.dumps(response['error']))
        return response['result']

    def close(self):
        self.proc.terminate()
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()


def run(binary, root, label, scenarios):
    root.mkdir(parents=True)  # Refuse to reuse/overwrite any existing experiment directory.
    home, cwd = root/'home', root/'cwd'
    home.mkdir(exist_ok=True)
    cwd.mkdir(exist_ok=True)
    if (home/'auth.json').exists():
        raise ValueError('Experiment home must not contain credentials')
    backend = ThreadingHTTPServer(('127.0.0.1', 0), Backend)
    backend.scenario, backend.percent, backend.calls, backend.terminal_ns, backend.quota_ns = 'success', 10, [], None, None
    threading.Thread(target=backend.serve_forever, daemon=True).start()
    sink = root/'notify.jsonl'
    forward = root/'original.jsonl'
    original = root/'original_callback.py'
    original.write_text('import json,sys,time\nfrom pathlib import Path\nwith Path(sys.argv[1]).open("a",encoding="utf-8") as f: f.write(json.dumps({"argv":sys.argv[2:],"received_ns":time.perf_counter_ns()})+"\\n")\n', encoding='utf-8')
    notify = [sys.executable, str(Path(__file__).with_name('codex_events.py')), '--events', str(sink),
              '--forward-json', json.dumps([sys.executable, str(original), str(forward), 'unchanged prefix']),]
    config = 'model = "gpt-6.1-sol"\nmodel_provider = "probe"\napproval_policy = "on-request"\nsandbox_mode = "read-only"\n'
    config += 'notify = '+json.dumps(notify)+'\n[analytics]\nenabled = false\n[model_providers.probe]\nname = "Offline probe"\n'
    config += f'base_url = "http://127.0.0.1:{backend.server_port}/v1"\nwire_api = "responses"\nrequires_openai_auth = false\nsupports_websockets = false\nrequest_max_retries = 0\nstream_max_retries = 0\n'
    (home/'config.toml').write_text(config, encoding='utf-8')
    client = None
    evidence = dict(label=label, binary_version=subprocess.check_output([str(binary), '--version'], text=True).strip(),
                    offline=True, samples=[])
    try:
        client = Client(binary, home, cwd)
        evidence['initialize'] = client.request(1, 'initialize', dict(clientInfo=dict(name='petoken_probe', title='Petoken offline probe', version='1.6'), capabilities=dict(experimentalApi=True)))
        client.send(dict(method='initialized', params={}))
        thread = client.request(2, 'thread/start', dict(model='gpt-6.1-sol', cwd=str(cwd), approvalPolicy='on-request',
                                sandbox='read-only', approvalsReviewer='user'))['thread']['id']
        for index, scenario in enumerate(scenarios):
            backend.scenario = scenario
            backend.percent = 10+index
            backend.terminal_ns = None
            backend.quota_ns = None
            start = time.perf_counter_ns()
            initial = len(client.seen)
            client.request(10+index, 'turn/start', dict(threadId=thread, input=[dict(type='text', text='Synthetic offline event probe.')]))
            if scenario == 'approval':
                at, message = client.wait(lambda m: m.get('method') in ('item/commandExecution/requestApproval', 'item/tool/requestUserInput'))
                evidence['samples'].append(dict(scenario=scenario, kind='waiting_for_user', trigger_ms=(at-start)/1e6,
                    backend_delivery_ms=(at-backend.terminal_ns)/1e6 if backend.terminal_ns else None))
                # This is our own fake command. Cancel without granting any permission.
                client.send(dict(id=message['id'], result=dict(decision='cancel')))
            at, complete = client.wait(lambda m: m.get('method') == 'turn/completed')
            evidence['samples'].append(dict(scenario=scenario, kind='terminal', status=complete['params']['turn']['status'],
                turn_id=complete['params']['turn']['id'], trigger_ns=start, backend_terminal_ns=backend.terminal_ns,
                trigger_ms=(at-start)/1e6, backend_delivery_ms=(at-backend.terminal_ns)/1e6 if backend.terminal_ns else None))
            deadline = time.monotonic()+1
            while time.monotonic() < deadline:
                if sink.exists() and any(json.loads(line).get('turn_id') == complete['params']['turn']['id']
                                         for line in sink.read_text(encoding='utf-8').splitlines()):
                    break
                time.sleep(.02)
            sample_events = []
            for at, message in client.seen[initial:]:
                hint = normalize_event(message)
                if hint:
                    event = dict(kind=hint['kind'], trigger_ms=(at-start)/1e6)
                    if hint['kind'] == 'quota_changed' and backend.quota_ns:
                        event['backend_delivery_ms'] = (at-backend.quota_ns)/1e6
                    sample_events.append(event)
            evidence['samples'][-1]['events'] = sample_events
        evidence['notify'] = [json.loads(line) for line in sink.read_text(encoding='utf-8').splitlines()] if sink.exists() else []
        for hint in evidence['notify']:
            sample = next((s for s in evidence['samples'] if s.get('turn_id') == hint['turn_id']), None)
            if sample:
                hint['trigger_ms'] = (hint['received_ns']-sample['trigger_ns'])/1e6
                if sample['backend_terminal_ns']:
                    hint['backend_delivery_ms'] = (hint['received_ns']-sample['backend_terminal_ns'])/1e6
        if forward.exists():
            forwarded = [json.loads(line) for line in forward.read_text(encoding='utf-8').splitlines()]
            evidence['forward_count'] = len(forwarded)
            evidence['forward_prefix_preserved'] = all(e['argv'][0] == 'unchanged prefix' for e in forwarded)
        evidence['backend_calls'] = backend.calls
    finally:
        evidence['backend_calls'] = backend.calls
        if client:
            evidence['methods'] = sorted({m.get('method') for _, m in client.seen if m.get('method')})
            evidence['terminal_statuses'] = [m['params']['turn']['status'] for _, m in client.seen
                                            if m.get('method') == 'turn/completed']
            evidence['protocol_errors'] = [m['params'] for _, m in client.seen if m.get('method') == 'error']
            evidence['diagnostics'] = client.errors[-12:]
            client.close()
        backend.shutdown()
        (root/'evidence.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    return evidence


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--label', required=True)
    parser.add_argument('--scenarios', default='success,success,success,failure,approval')
    args = parser.parse_args()
    result = run(args.binary, args.out, args.label, args.scenarios.split(','))
    print(json.dumps({k: result[k] for k in ('label', 'binary_version', 'samples', 'methods', 'notify')}, indent=2))
