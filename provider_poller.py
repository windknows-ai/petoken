"""Background poll orchestration: providers -> selection -> snapshot (V1.2 slice 5).

Qt-free worker logic. One dedicated daemon worker per provider (Codex
and Claude Code; never overlapping reads against one adapter, no
GUI-thread I/O) replaces the previous pool: a permanently blocked provider read
cannot keep the process alive, because daemon workers are never joined
and close() never blocks. Every poll captures one immutable tick
(generation, settings epoch, preference/scope/pinned, history mode and
activity inputs) before any work; every per-provider submit clones that
tick into its own immutable request (fresh monotonic id plus the tick
generation). Completions are accepted only for the current epoch with a
newer id, and every publication carries its own tick generation — never
the live counter — so a settings change during the tick retires the old
tick entirely: its submits carry the old epoch, its result carries the
old generation, and the GUI guard rejects it.

Cached reads carry provenance (provider, scope, pinned identity,
history mode, accepted epoch/id). Settings publication reuses cached
scoped data only when its provenance matches the requested scope/pinned
(global ignores pinned); otherwise it publishes an honest
pending/unavailable panel for the requested scope and never labels
Global data as Project/Conversation or one pinned session as another.
Independently verified working context may still ride along when the
selection is live and its own provenance is valid.

Shared selector/request state is owned by the poller and mutated only
under its lock; adapter I/O never runs under the lock, and adapters are
captured at submit time so a reset can never hand an old request a new
adapter. Selection is level-triggered over the latest accepted status
per provider.
"""
from __future__ import annotations

import threading
import time
from concurrent.futures import CancelledError

from claude_usage import ClaudeProvider
from provider_selection import (FRESHNESS_S, PREFERENCE_AUTO,
                                ProviderSelection, claude_provider_status,
                                codex_provider_status,
                                normalize_tracking_provider)
from providers import (CLAUDE_CAPABILITIES, CODEX_CAPABILITIES,
                       PROVIDER_CLAUDE, PROVIDER_CODEX, CodexProvider,
                       active_task_set, base_result)
from usage import CodexStore

PROVIDER_KEYS = (PROVIDER_CODEX, PROVIDER_CLAUDE)
POOL_THREADS = 2  # One dedicated daemon slot per active provider adapter.

_VALID_SCOPES = ('global', 'project', 'conversation')


def _normalize_scope(value):
    scope = value if isinstance(value, str) else 'conversation'
    scope = {'task': 'conversation'}.get(scope, scope)
    return scope if scope in _VALID_SCOPES else 'conversation'


def hub_preference(preference, pinned):
    """Provider the Hub inspects for one tick.

    Under Auto an explicitly pinned task routes the Hub to that task's own
    provider (Claude pins are ``claude:``-scoped, any other pin is a Codex
    thread), so inspecting a task never shows another provider's data. A
    manual provider preference always wins. Star membership never uses
    this: it follows the user's preference alone.
    """
    preference = normalize_tracking_provider(preference)
    if preference != PREFERENCE_AUTO or not pinned:
        return preference
    return (PROVIDER_CLAUDE if str(pinned).startswith(f'{PROVIDER_CLAUDE}:')
            else PROVIDER_CODEX)


def filter_active_tasks(active_sets, statuses, success_at, preference,
                        now=None):
    """Verified fresh membership over accepted provider sets, without I/O.

    Auto unions every active provider lane; a manual preference exposes
    only its own lane. Retired/unknown preferences normalize to Auto, and
    foreign provider sets cannot enter the active product, even when
    supplied by an old caller.
    """
    now = time.time() if now is None else now
    preference = normalize_tracking_provider(preference)
    lanes = (PROVIDER_KEYS if preference == PREFERENCE_AUTO
             else tuple(pid for pid in PROVIDER_KEYS if pid == preference))
    merged = []
    for pid in lanes:
        entry = (active_sets or {}).get(pid) or {}
        status = (statuses or {}).get(pid) or {}
        if not entry.get('valid', False):
            continue
        if not status.get('source_available', False):
            continue
        last = (success_at or {}).get(pid)
        if not (isinstance(last, (int, float))
                and now - last <= FRESHNESS_S):
            continue
        merged.extend(task for task in entry.get('tasks') or []
                      if isinstance(task, dict)
                      and task.get('provider_id') == pid)
    return merged


class _Tick:
    """Immutable whole-poll context, captured atomically before any work."""

    __slots__ = ('generation', 'epoch', 'preference', 'scope', 'pinned',
                 'want_history', 'active_title', 'detection_valid', 'now')

    def __init__(self, generation, epoch, preference, scope, pinned,
                 want_history, active_title, detection_valid, now):
        self.generation = generation
        self.epoch = epoch
        self.preference = preference
        self.scope = scope
        self.pinned = pinned
        self.want_history = want_history
        self.active_title = active_title
        self.detection_valid = detection_valid
        self.now = now


class _Request:
    """Immutable per-submit request context. Never relabeled."""

    __slots__ = ('rid', 'epoch', 'generation', 'preference', 'scope',
                 'pinned', 'want_history', 'active_title',
                 'detection_valid', 'now', 'codex_fence')

    def __init__(self, rid, epoch, generation, preference, scope, pinned,
                 want_history, active_title, detection_valid, now,
                 codex_fence=0):
        self.rid = rid
        self.epoch = epoch
        self.generation = generation
        self.preference = preference
        self.scope = scope
        self.pinned = pinned
        self.want_history = want_history
        self.active_title = active_title
        self.detection_valid = detection_valid
        self.now = now
        self.codex_fence = codex_fence


class _SlotFuture:
    """Minimal future for one bounded per-provider slot (tests use done(),
    result(timeout) and cancel(), plus the .request attribute)."""

    def __init__(self, request):
        self.request = request
        self._cond = threading.Condition()
        self._done = False
        self._cancelled = False
        self._started = False
        self._outcome = None
        self._exc = None

    def done(self):
        with self._cond:
            return self._done or self._cancelled

    def result(self, timeout=None):
        with self._cond:
            if not self._done and not self._cancelled:
                self._cond.wait(timeout)
                if not self._done and not self._cancelled:
                    raise TimeoutError('provider read timed out')
            if self._cancelled:
                raise CancelledError()
            if self._exc is not None:
                raise self._exc
            return self._outcome

    def cancel(self):
        with self._cond:
            if self._done or self._cancelled:
                return False
            if self._started:
                return False
            self._cancelled = True
            self._done = True
            self._cond.notify_all()
            return True

    def _try_start(self):
        with self._cond:
            if self._cancelled or self._done or self._started:
                return False
            self._started = True
            return True

    def _set_result(self, outcome):
        with self._cond:
            if self._cancelled or self._done:
                return False
            self._outcome = outcome
            self._done = True
            self._cond.notify_all()
            return True

    def _set_exception(self, exc):
        with self._cond:
            if self._cancelled or self._done:
                return False
            self._exc = exc
            self._done = True
            self._cond.notify_all()
            return True


def _unknown_status(provider_id):
    """Explicitly unknown provider state (never polled or never read)."""
    return dict(provider_id=provider_id, available=False,
                source_available=False, activity_valid=False, working=False,
                activity_at=None, last_success_at=None, error='')


def _codex_failed():
    return base_result(
        PROVIDER_CODEX, available=False, status='unavailable',
        reason='status_read_failed', capabilities=CODEX_CAPABILITIES,
        notes=('status_read_failed',),
        payload=dict(status='status_read_failed', rows=[],
                     codex_activity=dict(active=False, valid=False,
                                         reason='status_read_failed')))


def _claude_failed():
    return base_result(
        PROVIDER_CLAUDE, available=False, status='unavailable',
        reason='status_read_failed', capabilities=CLAUDE_CAPABILITIES,
        notes=('status_read_failed',),
        payload=dict(status='status_read_failed', rows=[],
                     claude_activity=dict(active=False, valid=False,
                                          reason='status_read_failed')))


def _failed_read(key):
    return _claude_failed() if key == PROVIDER_CLAUDE else _codex_failed()


def _compatible(prov, req_scope, req_pinned):
    """Cached scoped data may serve the request only when it was read for
    the same scope (global ignores pinned) and the same pinned session."""
    if not isinstance(prov, dict):
        return False
    if prov.get('scope') != req_scope:
        return False
    if req_scope == 'global':
        return True
    return (prov.get('pinned') or '') == (req_pinned or '')


class ProviderPoller:
    """Owns the provider adapters, selection, request epochs and daemon slots."""

    def __init__(self, codex_store=None, claude_store=None):
        self.codex = CodexProvider(codex_store)
        self.claude = ClaudeProvider(claude_store)
        self.selection = ProviderSelection()
        self.generation = 0
        self._lock = threading.RLock()
        self._job_cond = threading.Condition(self._lock)
        self._closed = False
        self._rid = 0
        self._epoch = 0
        # Provider-local invalidation for failed Codex resets: bumped only
        # when a reset construction fails, so pre-failure Codex completions
        # retire without relabeling any already captured tick.
        self._codex_fence = 0
        self._inflight = {}
        self._jobs = {}
        self._workers = {}
        self._accepted_rid = {}
        self._status = {key: _unknown_status(key) for key in PROVIDER_KEYS}
        self._reads = {}
        self._provenance = {}
        self._success_at = {}
        # Latest accepted per-provider active-task sets: {provider_id:
        # active-task-set dict}. Replaced atomically per lane with the
        # accepting request's monotonic id as revision, so an older
        # result can never overwrite a newer accepted set.
        self._active_sets = {}

    # -- lifecycle ----------------------------------------------------

    def close(self):
        """Release workers. Idempotent; never blocks on hung reads and
        never joins daemon workers, so a permanently blocked provider
        cannot keep the process alive."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
            # Retire envelopes committed just before shutdown, including
            # snapshots already waiting in the GUI event queue.
            self._epoch += 1
            self.generation += 1
            for future in list(self._inflight.values()):
                try:
                    future.cancel()
                except Exception:
                    pass
            self._inflight = {}
            self._jobs = {}
            try:
                self._job_cond.notify_all()
            except Exception:
                pass
    def _install_codex_locked(self, new_adapter):
        """Swap in a prebuilt Codex adapter. Caller holds the lock and has
        checked for close. Bumps the epoch (retiring in-flight work bound
        to the old adapter) and cancels outstanding reads."""
        self._epoch += 1
        self.generation += 1
        for future in list(self._inflight.values()):
            try:
                future.cancel()
            except Exception:
                pass
        self.codex = new_adapter

    def reset_codex(self):
        """Recreate the Codex store, retiring outstanding Codex work.

        Failure-atomic: the replacement is constructed before any shared
        mutation, so a construction failure keeps the old adapter, epoch,
        in-flight work and caches untouched. On success the epoch bump
        guarantees an old request (bound to the old adapter captured at
        submit) can never become current under the new adapter, and a
        retired old result can never repaint.
        """
        new_adapter = CodexProvider(CodexStore())
        with self._lock:
            if self._closed:
                return
            self._install_codex_locked(new_adapter)

    def _fail_codex_reset(self):
        """Keep the old adapter and fence pre-failure completions after
        reset construction fails. Cached live membership retires; only a
        newer successful Codex read can restore it. No use-time is stamped.
        """
        with self._lock:
            if self._closed:
                return
            self._codex_fence += 1
            pending = self._inflight.get(PROVIDER_CODEX)
            if pending is not None:
                try:
                    pending.cancel()
                except Exception:
                    pass
            self._reads[PROVIDER_CODEX] = _codex_failed()
            self._status[PROVIDER_CODEX] = self._shape(PROVIDER_CODEX)
            # Retire only this lane's live membership, keeping its
            # revision so only a newer accepted Codex outcome can
            # replace it.
            previous = self._active_sets.get(PROVIDER_CODEX)
            self._active_sets[PROVIDER_CODEX] = active_task_set(
                PROVIDER_CODEX, (),
                revision=(previous or {}).get('provider_revision', -1),
                observed_at=time.time(), valid=False,
                source_available=False, reason='codex_reset_failed')

    def bump_generation(self):
        """Invalidate in-flight results after settings/scope changes."""
        with self._lock:
            if self._closed:
                return
            self._epoch += 1
            self.generation += 1
            for future in list(self._inflight.values()):
                try:
                    future.cancel()
                except Exception:
                    pass

    def mark_used(self, provider_id, now=None):
        with self._lock:
            if self._closed:
                return
            self.selection.mark_used(provider_id, now=now)

    # -- workers ------------------------------------------------------

    def _ensure_worker(self, key):
        if key in self._workers:
            return
        thread = threading.Thread(target=self._worker_loop, args=(key,),
                                  daemon=True, name=f'provider-{key}')
        self._workers[key] = thread
        thread.start()

    def _worker_loop(self, key):
        while True:
            with self._lock:
                while key not in self._jobs and not self._closed:
                    self._job_cond.wait()
                if self._closed:
                    return
                request, reader, future = self._jobs.pop(key)
            if not future._try_start():
                continue
            try:
                outcome = reader(request)
            except Exception as exc:  # noqa: BLE001 - isolated per provider
                try:
                    future._set_exception(exc)
                except Exception:
                    pass
                with self._lock:
                    try:
                        self._job_cond.notify_all()
                    except Exception:
                        pass
                continue
            try:
                future._set_result(outcome)
            except Exception:
                pass
            with self._lock:
                try:
                    self._job_cond.notify_all()
                except Exception:
                    pass

    def _submit(self, key, tick):
        """Submit at most one outstanding read per provider.

        Each submit clones the tick into its own immutable request
        carrying a fresh monotonic id plus the tick generation; the
        adapter is captured now so a later reset can never hand this
        request a new adapter.
        """
        with self._lock:
            if self._closed or key not in PROVIDER_KEYS:
                return False
            pending = self._inflight.get(key)
            if pending is not None and not pending.done():
                return False
            self._ensure_worker(key)
            self._rid += 1
            request = _Request(
                self._rid, tick.epoch, tick.generation, tick.preference,
                tick.scope, tick.pinned, tick.want_history,
                tick.active_title, tick.detection_valid, tick.now,
                self._codex_fence)
            adapter = self.claude if key == PROVIDER_CLAUDE else self.codex

            def reader(req, ad=adapter):
                return ad.read(
                    active_title=req.active_title, pinned=req.pinned,
                    scope=req.scope, include_history=req.want_history,
                    activity_detection_valid=req.detection_valid)
            future = _SlotFuture(request)
            future.request = request
            self._jobs[key] = (request, reader, future)
            self._inflight[key] = future
            try:
                self._job_cond.notify_all()
            except Exception:
                pass
            return True

    def _read_codex(self, request):  # pragma: no cover - compat shim
        return self.codex.read(
            active_title=request.active_title, pinned=request.pinned,
            scope=request.scope, include_history=request.want_history,
            activity_detection_valid=request.detection_valid)

    def _collect(self):
        """Accept current-epoch newer-rid completions; discard the rest.

        Codex completions additionally require the current Codex fence,
        so work submitted before a failed reset can never overwrite the
        reset-failure marking. Never blocks: pending futures stay in
        flight for a later tick,
        so a hung provider cannot delay the other. Each claimed future
        is popped atomically, so a newer submit can never be deleted.
        Explicit error outcomes invalidate immediately (failed status,
        no success-time advance); slow absence decays through the
        existing freshness gate instead. Never mutates after close.
        """
        with self._lock:
            if self._closed:
                return
        claimed = []
        with self._lock:
            if self._closed:
                return
            for key in PROVIDER_KEYS:
                future = self._inflight.get(key)
                if future is None or not future.done():
                    continue
                del self._inflight[key]
                claimed.append((key, future.request, future))
        for key, request, future in claimed:
            try:
                outcome = future.result(timeout=0)
                failed = False
            except CancelledError:
                continue  # Best-effort cancel won: slot already freed.
            except Exception:
                outcome, failed = None, True
            with self._lock:
                if self._closed:
                    continue
                if (request.epoch != self._epoch
                        or request.rid <= self._accepted_rid.get(key, -1)
                        or (key == PROVIDER_CODEX and request.codex_fence
                            != self._codex_fence)):
                    continue  # Retired: never repaint, never refresh.
                self._accepted_rid[key] = request.rid
                self._provenance[key] = dict(
                    scope=request.scope, pinned=request.pinned,
                    want_history=request.want_history, epoch=request.epoch,
                    rid=request.rid, generation=request.generation)
                if failed:
                    self._reads[key] = _failed_read(key)
                    self._status[key] = self._shape(key)
                    self._store_active_set_locked(key, request, None)
                    continue
                self._reads[key] = outcome
                self._success_at[key] = request.now
                self._status[key] = self._shape(key)
                self._store_active_set_locked(key, request, outcome)

    def _store_active_set_locked(self, key, request, outcome):
        """Record one lane's coherent active-task set. Caller holds the
        lock; pure dict work, no I/O.

        The stamped revision is the accepting request's monotonic id,
        so replacement is monotonic per lane: an older outcome can
        never overwrite a newer accepted set (late results cannot
        resurrect retired tasks). Stored validity additionally
        requires the lane's shaped source-availability, so a set built
        from a down source never claims to prove current work even
        when it happens to be empty. ``outcome=None`` is an explicit
        lane failure: the lane's live membership retires truthfully
        to an empty invalid set while other lanes stay intact.
        """
        if key not in PROVIDER_KEYS:
            return
        previous = self._active_sets.get(key)
        if (previous is not None and request.rid <= previous.get(
                'provider_revision', -1)):
            return
        if outcome is None:
            entry = active_task_set(
                key, (), revision=request.rid, observed_at=request.now,
                valid=False, source_available=False,
                reason='lane_failed')
        else:
            tasks = ((outcome.get('payload') or {}).get('active_tasks')
                     if isinstance(outcome, dict) else None) or []
            tasks = [task for task in tasks if isinstance(task, dict)
                     and task.get('provider_id') == key]
            entry = active_task_set(
                key, tasks, revision=request.rid,
                observed_at=request.now, valid=True,
                source_available=True)
        lane_ok = self._status.get(key, {}).get('source_available', False)
        entry['valid'] = bool(entry.get('valid', False) and lane_ok)
        self._active_sets[key] = entry

    def _merged_active_tasks(self, preference, now, statuses=None):
        """Snapshot lane sets/success coherently, then filter to the
        visible verified working tasks. Publication callers retain their
        outer lock during the pure filter; no I/O happens here.

        Statuses default to the last accepted lane statuses, but a
        failure path passes its temporary failure statuses instead:
        the merged membership is then filtered against the failure
        state being returned, never against stale previous success.
        """
        with self._lock:
            sets = {key: dict(entry)
                    for key, entry in self._active_sets.items()}
            if statuses is None:
                statuses = {key: dict(status)
                            for key, status in self._status.items()}
            success = dict(self._success_at)
        return filter_active_tasks(sets, statuses, success, preference,
                                   now)

    def _shape(self, key):
        """Shape the latest accepted read into a selection status."""
        shape = (claude_provider_status if key == PROVIDER_CLAUDE
                 else codex_provider_status)
        return shape(self._reads.get(key), self._success_at.get(key))

    def _snapshot_statuses(self):
        with self._lock:
            return {key: dict(status) for key, status in self._status.items()}

    def drain(self, timeout=10):
        """Wait until no reads are in flight. Test/support utility only;
        production ticks never block. Returns False on timeout."""
        deadline = time.monotonic() + timeout
        while True:
            with self._lock:
                if self._closed:
                    return True
                pending = [future for future in self._inflight.values()
                           if not future.done()]
            if not pending:
                return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.01)

    # -- publication --------------------------------------------------

    def _decide(self, tick):
        """Commit selection and its complete envelope for a current tick."""
        with self._lock:
            if self._closed:
                return self._closed_result(tick)
            if (tick.epoch != self._epoch
                    or tick.generation != self.generation):
                return self._obsolete_result(tick)
            hub = hub_preference(tick.preference, tick.pinned)
            snapshot = self.selection.update(
                self._snapshot_statuses(), preference=hub,
                now=tick.now, generation=tick.generation)
            result = self._publish_locked(
                snapshot, hub, tick.scope, tick.pinned,
                tick.generation)
            return dict(generation=tick.generation,
                        preference=tick.preference, selection=snapshot,
                        provider_id=result['provider_id'], result=result,
                        codex=self._reads.get(PROVIDER_CODEX),
                        claude=self._reads.get(PROVIDER_CLAUDE),
                        active_tasks=self._merged_active_tasks(
                            tick.preference, tick.now))

    def _pending_result(self, selected, scope, live, generation):
        """Honest pending/unavailable panel for the requested scope.

        Working context rides along only when the selection is live;
        scoped tokens/cost are never filled from incompatible cache.
        """
        working = None
        if live and selected in PROVIDER_KEYS:
            read = self._reads.get(selected)
            context = (read.get('working_context')
                       if isinstance(read, dict) else None)
            if isinstance(context, dict):
                working = dict(context, provider_id=selected)
        return dict(provider_id=selected, status='no_reliable_record',
                    available=False, scope=scope, working_context=working)

    def _publish_locked(self, snapshot, preference, scope, pinned,
                        generation):
        """Publish for one tick. Caller holds the lock; the result always
        carries the tick generation, never the live counter."""
        selected = snapshot['selected']
        live = bool(snapshot['live'])
        if selected in PROVIDER_KEYS and not _compatible(
                self._provenance.get(selected), scope, pinned):
            result = self._pending_result(selected, scope, live,
                                          generation)
            result['selection'] = snapshot
            result['generation'] = generation
            return result
        if selected in PROVIDER_KEYS:
            read = self._reads.get(selected) or {}
            result = dict(read.get('payload') or {})
            result['provider_id'] = selected
            result['scope'] = scope
            if live:
                context = read.get('working_context')
                result['working_context'] = (
                    dict(context, provider_id=selected)
                    if isinstance(context, dict) else None)
            else:
                # The bubble follows selection, never a stale detector.
                result['working_context'] = None
        else:
            provider_id = (preference if preference != 'auto'
                           else PROVIDER_CODEX)
            result = dict(provider_id=provider_id,
                          status='no_reliable_record', available=False,
                          scope=scope, working_context=None)
        result['selection'] = snapshot
        result['generation'] = generation
        return result

    def _publish(self, snapshot, preference, scope='conversation'):
        # Back-compat shim for older callers/tests: pinned unknown means
        # only global data is safely reusable.
        with self._lock:
            return self._publish_locked(snapshot, preference, scope, '',
                                        self.generation)

    def _submit_all(self, tick_or_pref, scope=None, pinned=None,
                    want_history=False, active_title='',
                    detection_valid=False, now=None):
        # New path takes a tick; the legacy positional path (kept for any
        # external caller) rebuilds one from the current epoch without
        # relabeling in flight work.
        if isinstance(tick_or_pref, _Tick):
            tick = tick_or_pref
            for key in PROVIDER_KEYS:
                self._submit(key, tick)
            return
        with self._lock:
            if self._closed:
                return
            epoch = self._epoch
            generation = self.generation
        template = _Tick(generation, epoch, normalize_tracking_provider(tick_or_pref),
                         _normalize_scope(scope), pinned or '',
                         want_history, active_title, detection_valid, now)
        for key in PROVIDER_KEYS:
            self._submit(key, template)

    def _obsolete_result(self, tick):
        """Tick retired by a newer epoch/generation: no selection mutation,
        tick-tagged generation so the GUI guard must reject it."""
        with self._lock:
            if self._closed:
                return self._closed_result(tick)
            snapshot = self.selection.snapshot()
            codex_read = self._reads.get(PROVIDER_CODEX)
            claude_read = self._reads.get(PROVIDER_CLAUDE)
        result = dict(provider_id=tick.preference
                      if tick.preference != 'auto' else PROVIDER_CODEX,
                      status='obsolete_tick', available=False,
                      scope=tick.scope, working_context=None,
                      selection=snapshot, generation=tick.generation)
        return dict(generation=tick.generation, preference=tick.preference,
                    selection=snapshot, provider_id=result['provider_id'],
                    result=result, codex=codex_read, claude=claude_read,
                    active_tasks=[])

    def _closed_result(self, tick=None, prefs=None):
        with self._lock:
            snapshot = dict(self.selection.snapshot(), live=False)
            generation = tick.generation if tick is not None else self.generation
            preference = (tick.preference if tick is not None
                          else normalize_tracking_provider(
                              (prefs or {}).get('tracking_provider')))
            scope = (tick.scope if tick is not None
                     else _normalize_scope((prefs or {}).get('scope')))
            codex_read = self._reads.get(PROVIDER_CODEX)
            claude_read = self._reads.get(PROVIDER_CLAUDE)
        result = dict(provider_id=preference
                      if preference != 'auto' else PROVIDER_CODEX,
                      status='no_reliable_record', available=False,
                      scope=scope, working_context=None,
                      selection=snapshot, generation=generation)
        # A closed/shutdown poller proves no current work: its live
        # active-task membership is empty, never previously accepted
        # tasks. Historical analytics state elsewhere is untouched.
        return dict(generation=generation, preference=preference,
                    selection=snapshot, provider_id=result['provider_id'],
                    result=result, codex=codex_read, claude=claude_read,
                    active_tasks=[])

    @staticmethod
    def _failed_status(target):
        """Explicit conservative failure for one provider: source
        unavailable/invalid, no working claim, no freshness anchor."""
        return dict(
            provider_id=target, available=False, source_available=False,
            activity_valid=False, working=False, activity_at=None,
            last_success_at=None, error='status_read_failed')

    def _coherent_failure(self, tick):
        """Current-tick failure with internally coherent selection.

        The failure is fed through ProviderSelection as an explicit
        conservative Codex status, so the snapshot cannot claim Live beside
        failed/unavailable data and the published working context is
        always None. Compatible cached history stays stored internally but
        is never presented as freshly validated. A tick retired by a
        concurrent change returns its older generation untouched for the
        GUI guard; nothing here stamps use-time. Caller holds no lock."""
        with self._lock:
            if self._closed:
                return self._closed_result(tick)
            if (tick.epoch != self._epoch
                    or tick.generation != self.generation):
                return self._obsolete_result(tick)
            preference = tick.preference
            hub = hub_preference(preference, tick.pinned)
            targets = ((hub,) if hub != 'auto'
                       else PROVIDER_KEYS)
            inputs = self._snapshot_statuses()
            for target in targets:
                inputs[target] = self._failed_status(target)
            snapshot = self.selection.update(
                inputs, preference=hub, now=tick.now,
                generation=tick.generation)
            result = self._publish_locked(snapshot, hub, tick.scope,
                                           tick.pinned, tick.generation)
            # Filter against the temporary failure statuses being
            # returned — not the last successful lane statuses — so a
            # failed lane contributes no live membership while healthy
            # lanes keep theirs. The set means VERIFIED CURRENTLY
            # WORKING tasks: entries are never kept with working=False.
            return dict(
                generation=tick.generation, preference=preference,
                selection=snapshot, provider_id=result['provider_id'],
                result=result, codex=self._reads.get(PROVIDER_CODEX),
                claude=self._reads.get(PROVIDER_CLAUDE),
                active_tasks=self._merged_active_tasks(
                    preference, tick.now, statuses=inputs))

    def poll(self, prefs=None, active_title='', detection_valid=False,
             want_history=False, now=None):
        """One non-blocking tick: capture context, collect, submit, publish.

        Collection runs BEFORE submission so a just-completed read is
        always accepted before its slot is reused; otherwise the
        completed future would be orphaned and no provider would ever
        update. Always returns promptly, even with a provider hung
        mid-read: pending providers simply contribute their latest
        accepted state (or explicit unknown), and freshness expires
        their Live claims. A tick retired by a concurrent settings
        change never submits old values under the new epoch and never
        publishes under the new generation.
        """
        now = time.time() if now is None else now
        with self._lock:
            if self._closed:
                prefs = prefs or {}
                return self._closed_result(prefs=prefs)
            self.generation += 1
            tick_generation = self.generation
            tick_epoch = self._epoch
        prefs = prefs or {}
        preference = normalize_tracking_provider(
            prefs.get('tracking_provider'))
        scope = _normalize_scope(prefs.get('scope'))
        pinned = prefs.get('pinned') or ''
        tick = _Tick(tick_generation, tick_epoch, preference, scope,
                     pinned, want_history, active_title, detection_valid,
                     now)
        try:
            self._collect()
            with self._lock:
                if self._closed:
                    return self._closed_result(tick)
                cur_epoch, cur_gen = self._epoch, self.generation
            if tick.epoch != cur_epoch or tick.generation != cur_gen:
                return self._obsolete_result(tick)
            self._submit_all(tick)
            with self._lock:
                if self._closed:
                    return self._closed_result(tick)
                cur_epoch, cur_gen = self._epoch, self.generation
            if tick.epoch != cur_epoch or tick.generation != cur_gen:
                return self._obsolete_result(tick)
            return self._decide(tick)
        except Exception:
            return self._coherent_failure(tick)

    def apply_settings(self, prefs, mark_provider=None, now=None):
        """Settings/scope change path: invalidate, optionally stamp use,
        and immediately re-evaluate from compatible cached state.

        Performs no I/O, so Settings can publish synchronously instead
        of waiting for the next slow poll. Auto and polling never mark
        use time; only an explicit new manual choice does. Cached scoped
        data is reused only when its provenance matches the requested
        scope/pinned; otherwise an honest pending panel is published.
        """
        now = time.time() if now is None else now
        prefs = prefs or {}
        with self._lock:
            if self._closed:
                return self._closed_result(prefs=prefs)
            self._epoch += 1
            self.generation += 1
            tick_generation = self.generation
            for future in list(self._inflight.values()):
                try:
                    future.cancel()
                except Exception:
                    pass
            if mark_provider is not None:
                self.selection.mark_used(mark_provider, now=now)
            preference = normalize_tracking_provider(
                prefs.get('tracking_provider'))
            scope = _normalize_scope(prefs.get('scope'))
            pinned = prefs.get('pinned') or ''
            hub = hub_preference(preference, pinned)
            snapshot = self.selection.update(
                self._snapshot_statuses(), preference=hub, now=now,
                generation=tick_generation)
            result = self._publish_locked(snapshot, hub, scope,
                                           pinned, tick_generation)
            return dict(generation=tick_generation, preference=preference,
                        selection=snapshot, provider_id=result['provider_id'],
                        result=result,
                        active_tasks=self._merged_active_tasks(
                            preference, now))

    def _current_failure(self, preference, scope, pinned, now=None):
        """Last-resort tagged failure for the current prefs context.

        Builds a tick for this context and delegates to
        _coherent_failure, so the result carries an immutable
        generation, revokes Live through the selection authority, and
        follows the request preference — it can never look like a
        successful cached refresh. Used only when no tick was captured
        (e.g. an unexpected error around poll); poll-body failures
        already return their own tick-tagged coherent results. Never
        stamps use-time. Caller holds no lock."""
        now = time.time() if now is None else now
        with self._lock:
            if self._closed:
                return self._closed_result(prefs={
                    'tracking_provider': preference, 'scope': scope,
                    'pinned': pinned})
            self.generation += 1
            tick = _Tick(self.generation, self._epoch, preference, scope,
                         pinned, False, '', False, now)
        return self._coherent_failure(tick)

    def loop_tick(self, prefs=None, active_title='',
                  detection_valid=False, want_history=False, now=None,
                  reset_requested=False):
        """One production read-loop iteration. Always returns a
        context-tagged snapshot; expected failures never raise.

        Generation/context ownership stays centralized here so the Qt
        bridge never receives an untagged fallback: Codex reset
        construction is failure-atomic (the old adapter is kept and only
        the Codex source is marked failed), the same iteration then
        continues with a fresh Codex poll; poll-body failures return coherent results
        for their own tick generation. Successful resets fall through
        to a fresh poll with a new tick. Never stamps use-time.
        """
        now = time.time() if now is None else now
        prefs = dict(prefs or {})
        try:
            preference = normalize_tracking_provider(
                prefs.get('tracking_provider'))
        except Exception:
            preference = PREFERENCE_AUTO
        try:
            scope = _normalize_scope(prefs.get('scope'))
        except Exception:
            scope = 'conversation'
        try:
            pinned = prefs.get('pinned') or ''
        except Exception:
            pinned = ''
        new_adapter = None
        if reset_requested:
            try:
                new_adapter = CodexProvider(CodexStore())
            except Exception:
                # Failure-atomic and provider-isolated: construction
                # failed before any shared mutation, so mark only the
                # Codex source failed (keeping the old adapter) and fall
                # through to a fresh read on the retained adapter.
                self._fail_codex_reset()
        if new_adapter is not None:
            with self._lock:
                if self._closed:
                    return self._closed_result(prefs=prefs)
                self._install_codex_locked(new_adapter)
        try:
            return self.poll(prefs, active_title=active_title,
                             detection_valid=detection_valid,
                             want_history=want_history, now=now)
        except Exception:
            return self._current_failure(preference, scope, pinned,
                                         now=now)
