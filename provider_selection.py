"""Deterministic provider selection: preference + activity ranking (V1.2 slice 4).

Production exposes Codex alone. Explicit provider-ID injection retains
historical pure ranking tests without activating adapters. No I/O or threads.
A status snapshot is a plain dict per provider::

    {provider_id, available, source_available, activity_valid, working,
     activity_at, last_success_at, error}

- ``available``: the scoped read produced data for the current
  analytics selection (missing pinned scope reads False here while the
  provider itself may be working — scope availability is never
  provider availability).
- ``source_available``: the store/lifecycle source reads (history
  stays valid when stale). Absent means unavailable: fail-closed,
  never inferred from scoped data.
- ``activity_valid``: the working claim was verified this poll.
  Absent means unknown/False: unverified working is unknown, never
  idle, and an unverified instant never feeds recency.
- ``working``: a verified live claim from the provider's own rule.
- ``activity_at``: last ATTRIBUTABLE work/lifecycle/usage instant in
  epoch seconds (OpenCode lifecycle instants, Codex lifecycle event
  times). Row-update clocks, poll times and file mtimes are never
  used: unknown stays unknown and falls back to use-time/retention.
- ``last_success_at``: last successful poll in epoch seconds
  (freshness clock, kept separate from activity recency).

Ranking (00 §Exact visible behavior): a manual choice wins at once and
clears pending Auto state; Auto prefers the sole working provider,
then the most recently active of several working providers, then the
most recently active/used provider while staying Daily (historical, no
live bubble). Unknown timestamps never fabricate recency: ties and
all-unknown fields retain the current eligible selection, then stable
provider ID order. Foreground/session titles never enter this module,
so foreground cannot override provider ranking by construction.

Stability: a newly preferred Auto provider must win for STABILITY_S
before the selection switches, except when the current selection
becomes unavailable (immediate — an unavailable provider cannot
serve). The live badge always follows the current input immediately,
so debounce never presents an invalid/completed context as live.

Freshness: a source without a successful poll inside FRESHNESS_S is
stale: its working claim is ignored (live removed immediately on real
failure) while its history stays selectable and is flagged stale.
Freshness and errors invalidate live claims independently of
historical-data availability.

Generations: polls carry a caller-assigned generation bound to that
poll's provider context; entries whose inner provider tag mismatches
their key are dropped. Batches older than the applied generation are
late results: their payload is ignored, but freshness is reevaluated
against current time with the current user preference, so a delayed
batch can neither freeze a stale live badge nor block a manual switch.
"""
from __future__ import annotations

import time
from datetime import datetime

from providers import PROVIDER_CODEX, PROVIDER_OPENCODE, PROVIDER_REGISTRY

PREFERENCE_AUTO = 'auto'
PREFERENCE_CODEX = PROVIDER_CODEX
PREFERENCE_OPENCODE = PROVIDER_OPENCODE
# Persisted Auto/OpenCode preferences migrate to the sole active provider.
TRACKING_CHOICES = tuple(PROVIDER_REGISTRY)
DEFAULT_TRACKING_PROVIDER = PREFERENCE_CODEX
KNOWN_PROVIDERS = tuple(PROVIDER_REGISTRY)

# A newly preferred provider must hold for 1 s before switching (00).
STABILITY_S = 1.0
# A source is stale after 5 s without a successful refresh (01).
FRESHNESS_S = 5.0

# Codex store statuses that mean the source itself is down (as opposed
# to a missing analytics selection on a readable store). Checked at
# BOTH envelope layers: a failed outer reason must invalidate even
# when the payload still carries old successful/cached data.
# status_read_failed is the poller-level read exception (same class).
CODEX_SOURCE_FAILURES = frozenset(
    {'status_no_local_data', 'status_database_unavailable',
     'status_read_failed'})

# Inert historical status shaping, used only by explicitly isolated adapter
# tests/callers. Production registry and poller never invoke this path.
OPENCODE_SOURCE_FAILURES = frozenset(
    {'missing_store', 'store_locked', 'unsupported_schema'})


def normalize_tracking_provider(value):
    """Normalize current and legacy preferences to the active Codex product."""
    if isinstance(value, str) and value.strip().lower() in TRACKING_CHOICES:
        return value.strip().lower()
    return DEFAULT_TRACKING_PROVIDER


def _epoch(value):
    return value if isinstance(value, (int, float)) and value >= 0 else None


def _iso_epoch(value):
    try:
        return datetime.fromisoformat(
            str(value).replace('Z', '+00:00')).timestamp()
    except (ValueError, TypeError, OverflowError, OSError):
        return None


def codex_provider_status(read_result, last_success_at=None):
    """Shape a Codex envelope into a selection status snapshot.

    Fail-closed: an absent result, a missing detector block, or an
    explicit source failure at EITHER layer (outer reason or payload
    status: status_no_local_data, status_database_unavailable) yields
    unavailable/invalid even beside cached working data — cached
    history may stay displayable, but it never proves current work.
    A benign scoped-data failure (status_pinned_unavailable) at either
    layer keeps the source available: with independently verified
    working activity the provider stays eligible and live. Recency uses the
    working session's latest token-event time, or unknown when idle (a
    working session with no token event yet also reports unknown).
    """
    if not isinstance(read_result, dict):
        return dict(provider_id=PROVIDER_CODEX, available=False,
                    source_available=False, activity_valid=False,
                    working=False, activity_at=None,
                    last_success_at=_epoch(last_success_at), error='')
    payload = read_result.get('payload')
    if not isinstance(payload, dict):
        return dict(provider_id=PROVIDER_CODEX, available=False,
                    source_available=False, activity_valid=False,
                    working=False, activity_at=None,
                    last_success_at=_epoch(last_success_at),
                    error=read_result.get('reason') or '')
    status_code = payload.get('status') or ''
    activity = payload.get('codex_activity')
    activity = activity if isinstance(activity, dict) else None
    context = read_result.get('working_context')
    reason = read_result.get('reason') or ''
    # Dual layer: the outer reason and the inner payload status are
    # checked independently (status_code aliases payload.status).
    source_available = (status_code not in CODEX_SOURCE_FAILURES
                        and reason not in CODEX_SOURCE_FAILURES)
    activity_valid = bool(source_available and activity is not None
                          and activity.get('valid', False))
    working = bool(source_available and activity_valid
                   and context is not None)
    sample = _iso_epoch(context.get('sample')) if isinstance(
        context, dict) else None
    return dict(provider_id=PROVIDER_CODEX,
                available=bool(read_result.get('available', False)),
                source_available=source_available,
                activity_valid=activity_valid,
                working=working,
                activity_at=sample if working else None,
                last_success_at=_epoch(last_success_at),
                error=reason)


def opencode_provider_status(read_result, activity, last_success_at=None):
    """Shape an OpenCode envelope + activity snapshot into a status.

    A readable store with a missing pinned scope stays source-available;
    idle recency uses attributable lifecycle instants only. Evidence
    that is present but unusable downgrades validity instead of
    claiming confirmed idle. Store failures are detected at BOTH
    layers — outer read_result.reason AND inner payload.status — so a
    cached payload carrying a failure marker still invalidates, while
    benign scoped-data markers at either layer stay benign. A failed
    source also forces validity down: cached activity never proves
    current work.
    """
    read_result = read_result or {}
    snapshot = activity if isinstance(activity, dict) else {}
    payload = read_result.get('payload')
    payload = payload if isinstance(payload, dict) else None
    reason = read_result.get('reason') or ''
    payload_status = payload.get('status') or '' if payload else ''
    snap_valid = bool(snapshot.get('valid', False))
    unknown_evidence = bool(snapshot.get('evidence_unknown', False))
    source_available = (payload is not None
                        and reason not in OPENCODE_SOURCE_FAILURES
                        and payload_status not in OPENCODE_SOURCE_FAILURES)
    base_valid = snap_valid and not (
        unknown_evidence and not snapshot.get('working', False))
    activity_valid = bool(source_available and base_valid)
    working = bool(activity_valid and snapshot.get('working', False))
    last_lifecycle = snapshot.get('last_lifecycle_at')
    activity_at = (last_lifecycle / 1000 if isinstance(
        last_lifecycle, (int, float)) and last_lifecycle >= 0 else None)
    return dict(provider_id=PROVIDER_OPENCODE,
                available=bool(read_result.get('available', False)),
                source_available=source_available,
                activity_valid=activity_valid,
                working=working,
                activity_at=activity_at,
                last_success_at=_epoch(last_success_at),
                error=reason or snapshot.get('reason') or '')


def _stable_order(provider_ids):
    return sorted(provider_ids)


def _source_available(status):
    # Fail-closed: absent means unavailable, never inferred.
    return bool(status.get('source_available', False))


def _activity_valid(status):
    # Fail-closed: absent means unknown, never verified.
    return bool(status.get('activity_valid', False))


class ProviderSelection:
    """One deterministic selection with debounced switching.

    The selector operates over an allowed provider-ID set: None means
    the real runtime registry (production path, unchanged), while
    tests may inject a synthetic third ID to prove deterministic
    N-provider behavior without registering anything globally.
    """

    def __init__(self, provider_ids=None):
        self._generic = provider_ids is not None
        self._allowed = (tuple(provider_ids) if provider_ids is not None
                         else KNOWN_PROVIDERS)
        self.current = None
        self.pending = None
        self.pending_since = None
        self.last_use = {}
        self.applied_generation = None
        self._last_inputs = {}
        self._snapshot = dict(selected=None, live=False, historical=False,
                              stale=False, activity_unknown=False,
                              source_available=False, data_available=False,
                              reason='no_provider', detail='', tie_broken=False,
                              pending_switch=None,
                              preference=(PREFERENCE_AUTO if self._generic
                                          else DEFAULT_TRACKING_PROVIDER),
                              applied_generation=None)

    def mark_used(self, provider_id, now=None):
        """Record an explicit provider choice (manual use time). Call this
        when the user explicitly picks a provider; update() deliberately
        never calls it, because merely (auto-)selecting a provider must
        not refresh its use time."""
        now = time.time() if now is None else now
        if provider_id in self._allowed:
            self.last_use[provider_id] = now

    def snapshot(self):
        return dict(self._snapshot)

    def _fresh(self, status, now):
        success_at = _epoch(status.get('last_success_at'))
        return success_at is not None and now - success_at <= FRESHNESS_S

    def _rank_auto(self, inputs, fresh):
        """Return (winner, reason, detail, tie_broken) among sources.

        Only fresh verified working claims compete as working: stale or
        unverified sources cannot force selection, though their history
        stays eligible for idle recency and is flagged stale/unknown.
        """
        eligible = {pid: status for pid, status in inputs.items()
                    if _source_available(status)}
        if not eligible:
            return None, 'no_provider', 'no_available_provider', False
        workers = sorted(pid for pid, status in eligible.items()
                         if status.get('working', False)
                         and _activity_valid(status) and fresh.get(pid))
        if len(workers) == 1:
            return workers[0], 'working', 'sole_working_provider', False
        if workers:
            return self._newest(
                {pid: eligible[pid] for pid in workers},
                'both_working_recency')
        scores = {}
        for pid, status in eligible.items():
            # Unverified provenance taints the instant too: unknown
            # activity never becomes fabricated recency.
            activity = (_epoch(status.get('activity_at'))
                        if _activity_valid(status) else None)
            use = _epoch(self.last_use.get(pid))
            known = [v for v in (activity, use) if v is not None]
            scores[pid] = max(known) if known else None
        present = [s for s in scores.values() if s is not None]
        leaders = [pid for pid, score in scores.items()
                   if score is not None and present and score == max(present)]
        if self.current in leaders:
            return self.current, 'idle_recency', 'recency_tie_retained', True
        if leaders:
            winner = _stable_order(leaders)[0]
            tied = len(leaders) > 1
            return winner, 'idle_recency', (
                'recency_tie_stable_order' if tied else 'max_recency'), tied
        if self.current in eligible:
            return self.current, 'retained_current', 'all_unknown_retained', True
        winner = _stable_order(eligible)[0]
        return winner, 'stable_order', 'all_unknown_stable_order', True

    def _newest(self, contenders, reason):
        """Newest attributable activity wins; unknowns sort last; ties
        retain then stable order. Returns (winner, reason, detail, tie)."""
        stamps = {pid: _epoch(status.get('activity_at'))
                  for pid, status in contenders.items()}
        known = {pid: stamp for pid, stamp in stamps.items()
                 if stamp is not None}
        if not known:
            if self.current in contenders:
                return self.current, reason, 'activity_unknown_retained', True
            return (_stable_order(contenders)[0], reason,
                    'activity_unknown_stable_order', True)
        newest = max(known.values())
        leaders = sorted(pid for pid, stamp in known.items()
                         if stamp == newest)
        if self.current in leaders:
            return self.current, reason, 'activity_tie_retained', True
        if len(leaders) > 1:
            return leaders[0], reason, 'activity_tie_stable_order', True
        return leaders[0], reason, 'newest_activity', False

    def _matched(self, inputs):
        """Drop entries whose inner provider tag mismatches their key,
        that are not dicts, or that fall outside this selector's
        allowed provider-ID set (the runtime registry by default, so a
        synthetic test ID never leaks into production selection)."""
        matched = {}
        for pid, status in (inputs or {}).items():
            if pid not in self._allowed or not isinstance(status, dict):
                continue
            if status.get('provider_id', pid) != pid:
                continue
            matched[pid] = status
        return matched

    def _decide(self, inputs, preference, now):
        """Rank, debounce and publish one snapshot from accepted inputs."""
        available = {pid for pid, status in inputs.items()
                     if _source_available(status)}
        winner = reason = detail = None
        tie = False
        if preference != PREFERENCE_AUTO:
            if preference in available:
                # Manual choices bypass Auto debounce at once and clear
                # any pending automatic switch.
                self.current, self.pending, self.pending_since = (
                    preference, None, None)
                winner, reason, detail = (
                    preference, 'manual', 'manual_choice')
            else:
                self.current, self.pending, self.pending_since = (
                    None, None, None)
                winner, reason, detail = (
                    None, 'manual_unavailable', 'manual_provider_unavailable')
        else:
            fresh = {pid: self._fresh(status, now)
                     for pid, status in inputs.items()}
            winner, reason, detail, tie = self._rank_auto(inputs, fresh)
            if winner != self.current:
                if (winner is None or self.current is None
                        or self.current not in available):
                    # Nothing servable to protect: switch at once.
                    self.current, self.pending, self.pending_since = (
                        winner, None, None)
                elif winner != self.pending:
                    self.pending, self.pending_since = winner, now
                elif now - self.pending_since >= STABILITY_S:
                    self.current, self.pending, self.pending_since = (
                        winner, None, None)
            else:
                self.pending, self.pending_since = None, None
        selected = self.current
        status = inputs.get(selected) if selected else None
        live = bool(status and _source_available(status)
                    and _activity_valid(status)
                    and status.get('working', False)
                    and self._fresh(status, now))
        stale = bool(status and _source_available(status)
                     and not self._fresh(status, now))
        self._snapshot = dict(
            selected=selected, live=live,
            historical=selected is not None and not live,
            stale=stale,
            activity_unknown=bool(status and not _activity_valid(status)),
            source_available=bool(status and _source_available(status)),
            data_available=bool(status and status.get('available', False)),
            reason=reason, detail=detail, tie_broken=tie,
            pending_switch=self.pending, preference=preference,
            applied_generation=self.applied_generation)
        return self.snapshot()

    def update(self, inputs, preference=PREFERENCE_AUTO, now=None,
               generation=None):
        """Fold one tagged poll batch into the selection.

        Late batches (generation below the applied one) contribute no
        payload, but freshness is still reevaluated against current time
        with the current user preference, so neither a frozen live badge
        nor a stale Auto winner can survive them.
        """
        now = time.time() if now is None else now
        if self._generic:
            # Explicit injected IDs exercise isolated historical ranking logic;
            # production always normalizes against the active registry.
            preference = (preference if isinstance(preference, str)
                          and preference in (PREFERENCE_AUTO,) + self._allowed
                          else PREFERENCE_AUTO)
        else:
            preference = normalize_tracking_provider(preference)
        if generation is not None:
            if (self.applied_generation is not None
                    and generation < self.applied_generation):
                return self._decide(dict(self._last_inputs), preference, now)
            self.applied_generation = generation
        self._last_inputs = {pid: dict(status) for pid, status
                             in self._matched(inputs).items()}
        return self._decide(dict(self._last_inputs), preference, now)
