"""V1.6 experiment only: private, content-free event hints; no Petoken wiring."""
import argparse
import json
from pathlib import Path
import subprocess
import time


APPROVAL_METHODS = frozenset({
    'item/commandExecution/requestApproval', 'item/fileChange/requestApproval',
    'item/permissions/requestApproval', 'item/tool/requestUserInput',
    'mcpServer/elicitation/request',
})


def _identifier(value):
    return value if isinstance(value, str) and value.strip() else None


def normalize_event(message, source='app-server'):
    """Return an event hint, never dialogue/commands or inferred numeric counters."""
    if not isinstance(message, dict):
        return None
    if source == 'notify':
        if message.get('type') != 'agent-turn-complete':
            return None
        return dict(kind='finished', source=source, thread_id=_identifier(message.get('thread-id')),
                    turn_id=_identifier(message.get('turn-id')))
    method, params = message.get('method'), message.get('params')
    if not isinstance(method, str) or not isinstance(params, dict):
        return None
    event = dict(source=source, thread_id=_identifier(params.get('threadId')), turn_id=_identifier(params.get('turnId')))
    turn = params.get('turn')
    if method in ('turn/started', 'turn/completed') and isinstance(turn, dict):
        status = turn.get('status')
        if not isinstance(status, str):
            return None
        kind = ('started' if method == 'turn/started' and status == 'inProgress'
                else {'completed': 'completed', 'failed': 'failed', 'interrupted': 'interrupted'}.get(
                    status) if method == 'turn/completed' else None)
        if kind:
            return dict(event, kind=kind, turn_id=_identifier(turn.get('id')))
    elif method in APPROVAL_METHODS and isinstance(message.get('id'), (str, int)) and not isinstance(message['id'], bool):
        return dict(event, kind='waiting_for_user', request_id=message['id'])
    elif method == 'serverRequest/resolved' and isinstance(params.get('requestId'), (str, int)) and not isinstance(params['requestId'], bool):
        return dict(event, kind='confirmation_resolved', request_id=params['requestId'])
    elif method == 'account/rateLimits/updated' and isinstance(params.get('rateLimits'), dict):
        return dict(event, kind='quota_changed')
    return None


def forward_notify(raw_payload, original_argv, emit, runner=subprocess.run):
    """Deliver a hint first; always forward the untouched argv payload, without shell."""
    try:
        try:
            hint = normalize_event(json.loads(raw_payload), 'notify')
            if hint is not None:
                emit(hint)
        except Exception:
            pass  # Failure of the experimental sink must not disable the existing callback.
    finally:
        result = runner([*original_argv, raw_payload], check=False, shell=False) if original_argv else None
    return result.returncode if result is not None else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--events', type=Path, required=True)
    parser.add_argument('--forward-json', default='[]', help='Original notify argv as a JSON array.')
    parser.add_argument('payload', help='The original single Codex JSON argument.')
    args = parser.parse_args()
    argv = json.loads(args.forward_json)
    if not isinstance(argv, list) or not all(isinstance(arg, str) for arg in argv):
        parser.error('--forward-json must contain a string array')

    def emit(hint):
        with args.events.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(dict(hint, received_ns=time.perf_counter_ns()))+'\n')

    return forward_notify(args.payload, argv, emit)


if __name__ == '__main__':
    raise SystemExit(main())
