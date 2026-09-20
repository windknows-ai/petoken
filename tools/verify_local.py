"""Opt-in scope-aware reconciliation; outputs numeric diagnostics only."""
import json
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from usage import CodexStore


def reconcile(summary):
    for group in ('models', 'sessions'):
        assert sum(row['events'] for row in summary[group]) == summary['events'], group
        for key, value in summary['tokens'].items():
            assert sum(row['known'][key] for row in summary[group]) == summary['known'][key], (group, key)
            parts = [row['tokens'][key] for row in summary[group]]
            if value is not None:
                assert all(part is not None for part in parts), (group, key, 'unexpected missing value')
                assert sum(parts) == value, (group, key)
            elif parts:
                assert any(part is None for part in parts), (group, key, 'missing coverage lost')


def verify(store=None):
    store = store or CodexStore()
    start = time.perf_counter()
    data = store.read(scope='global', include_history=True)
    assert data.get('available'), data.get('status')
    cold = time.perf_counter() - start
    checked = 0
    for session in store.sessions.values():
        if session.fork_from or session.partial or any('reset' in n.lower() for n in session.notes):
            continue
        if not session.raw_total:
            continue
        for key, value in session.raw_total.items():
            if key in session.total:
                assert session.total[key] == value, (key, session.total[key], value)
        checked += 1
    reconcile(data['history'])
    scopes = {'global': 1, 'project': 0, 'conversation': 0}
    # Reconcile selected contexts using the same scope contract as the UI.
    for row in data.get('rows', [])[:3]:
        for scope in ('conversation', 'project'):
            scoped = store.read(pinned=row['id'], scope=scope, include_history=True)
            if not scoped.get('available'):
                continue  # No invented identity or data for an unavailable project.
            assert scoped['scope_identity']['scope_type'] == scope
            if scope == 'conversation':
                assert scoped['scope_identity']['thread_id'] == row['id']
            reconcile(scoped['history'])
            scopes[scope] += 1
    start = time.perf_counter()
    store.read(scope='global', include_history=True)
    warm = time.perf_counter() - start
    return dict(status='PASS' if checked >= 3 else 'INSUFFICIENT_DATA',
                sessions_reconciled=checked, minimum_sessions=3,
                models_reconcile=True, sessions_reconcile=True, scopes=scopes,
                indexed_sessions=len(store.sessions), cold_seconds=round(cold, 4),
                warm_seconds=round(warm, 4))


if __name__ == '__main__':
    result = verify()
    print(json.dumps(result))
    raise SystemExit(0 if result['status'] == 'PASS' else 2)
