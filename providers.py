"""Minimal provider result contract with a Codex-only wrapper (V1.2 slice 2).

Wraps existing CodexStore reads and quota payloads with provider identity,
capabilities, and freshness metadata. Every Codex field passes through
untouched: the same Codex input produces equivalent values. The active
product registry contains Codex alone; historical adapters are never
imported or registered here. There are no combined totals.
"""
from __future__ import annotations

import time

PROVIDER_CODEX = 'codex'
# Historical adapter identity only; absent from the active product registry.
PROVIDER_OPENCODE = 'opencode'
PROVIDER_NAMES = {PROVIDER_CODEX: 'Codex'}

# Known Codex capabilities (fixed, factual per V1.1 behavior). Anything not
# listed here is unsupported until a later slice proves it.
CODEX_CAPABILITIES = frozenset({
    'scopes',            # global / project / conversation, provider-local
    'working_context',   # bound working session, independent of scope
    'quotas',            # account limits with reset timers
    'cost_estimate',     # estimated (not recorded) cost subtotal
    'history',           # on-demand history detail
    'fork_accounting',   # fork-deduplicated aggregation
    'nullable_fields',   # explicit unknown instead of zero-filled
})
def _codex_capabilities():
    return CODEX_CAPABILITIES


# Current product boundary. Historical adapter source remains isolated and
# is not imported, selectable or polled by the application.
PROVIDER_REGISTRY = {
    PROVIDER_CODEX: dict(display_name='Codex',
                         capabilities=_codex_capabilities),
}


def base_result(provider_id, *, available=False, status='', reason='',
                identity=None, tokens=None, working_context=None,
                scope_result=None, quotas=None, cost=None,
                capabilities=frozenset(), partial=False, notes=(),
                payload=None, last_success_at=None, source_event_at=None):
    """One provider-tagged result envelope.

    Successful polling time (``last_success_at``) is freshness metadata and
    is distinct from last usage activity time. Unknown values stay unknown:
    callers must not substitute zeros or another provider's values.
    """
    return dict(provider_id=provider_id,
                provider_name=PROVIDER_NAMES.get(provider_id, provider_id),
                available=available, status=status, reason=reason,
                identity=identity, tokens=tokens,
                working_context=working_context, scope_result=scope_result,
                quotas=quotas, cost=cost, capabilities=capabilities,
                partial=partial, notes=tuple(notes or ()),
                payload=payload, last_success_at=last_success_at,
                source_event_at=source_event_at)


def is_supported(provider_id, capability):
    """Whether a capability is proven for a provider (unknowns are unsupported).

    Dispatches through the registry's per-provider capability getter,
    so an unregistered provider (or a failing lookup) safely reports
    False instead of crashing or inventing capabilities.
    """
    entry = PROVIDER_REGISTRY.get(provider_id)
    if entry is None:
        return False
    try:
        return capability in entry['capabilities']()
    except Exception:
        return False


def active_task(provider_id, task_key, *, working=True,
                activity_valid=True, activity_at=None, display=None,
                presentation=None):
    """One verified working-task entry for Multi-Task enumeration.

    Plain data, no behavior: task_key is the stable provider-scoped
    internal key (never UI display text by itself); display carries
    privacy-safe identity metadata; presentation carries
    provider-local task data (or None fields, never borrowed values).
    Unknown stays unknown: activity_at may be None.
    """
    return dict(provider_id=provider_id, task_key=task_key,
                working=bool(working),
                activity_valid=bool(activity_valid),
                activity_at=activity_at, display=dict(display or {}),
                presentation=presentation)


def active_task_set(provider_id, tasks=(), *, revision=None,
                    observed_at=None, valid=False, source_available=False,
                    reason=''):
    """One provider's coherent verified working-task set.

    Replaced atomically per provider: a newer accepted revision
    supersedes the whole set, and a late older revision must never
    restore retired tasks. valid/source_available describe whether
    this set may prove current work; freshness is evaluated by the
    consumer from observed_at.
    """
    return dict(provider_id=provider_id, tasks=tuple(tasks or ()),
                provider_revision=revision, observed_at=observed_at,
                valid=bool(valid),
                source_available=bool(source_available), reason=reason)


class CodexProvider:
    """Thin tagging wrapper around an existing CodexStore. No reshaping."""

    provider_id = PROVIDER_CODEX

    def __init__(self, store=None):
        if store is None:
            from usage import CodexStore
            store = CodexStore()
        self.store = store

    @property
    def capabilities(self):
        return CODEX_CAPABILITIES

    def read(self, active_title='', pinned='', scope='conversation',
             include_history=False, activity_detection_valid=False):
        """Delegate to CodexStore.read with identical arguments and tag the result."""
        data = self.store.read(active_title=active_title, pinned=pinned,
                               scope=scope, include_history=include_history,
                               activity_detection_valid=activity_detection_valid)
        ok = not data.get('status')
        return base_result(
            PROVIDER_CODEX,
            available=bool(data.get('available', False)),
            status='' if ok else 'unavailable',
            reason=data.get('status') or '',
            identity=data.get('scope_identity'),
            tokens=data.get('tokens'),
            working_context=data.get('working_context'),
            scope_result=data.get('scope_result'),
            quotas=data.get('limits'),
            cost=data.get('usd'),
            capabilities=CODEX_CAPABILITIES,
            partial=bool(data.get('partial', False)),
            notes=data.get('notes'),
            payload=data,
            last_success_at=time.time() if ok else None,
            source_event_at=data.get('sample'))


def wrap_quota(payload):
    """Tag a RateLimits quota payload with its provider. No reshaping."""
    data = dict(payload)
    data['provider_id'] = PROVIDER_CODEX
    return data
