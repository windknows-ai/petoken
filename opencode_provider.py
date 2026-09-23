"""Read-only incremental OpenCode metadata adapter (V1.2 slice 3).

Verified against installed opencode-ai 1.18.31 SQLite source (evidence in
docs/PROVIDERS.md and the V1.2 99 notes):
- Session rollups are own-session totals: fork-child rollups equal the
  child's own message deltas on live samples, so scope sums add
  same-category raw columns. No cross-category formulas, no Codex
  subset/total semantics (cache_read dwarfs input). No fork subtraction
  of any kind is performed.
- Every live session.project_id joins project.id; project names are NULL,
  so display falls back to the session directory basename or unavailable.
  Scopes group by project_id, never by basename.
- No currency column exists: recorded cost amounts are preserved with
  currency None; a recorded 0.0 is a real zero. No conversion, no symbol,
  no Codex pricing inference.
- Message costs do not sum to session cost: totals use session rollups;
  message deltas serve recency/daily history only.
- Unknown stays unknown: all-None categories sum to None (never 0), real
  zeros stay zero, and known subtotals carry explicit partial coverage.

Cache correctness: every refresh re-projects the allowlisted session
table with a single SELECT (one coherent snapshot — rows and IDs can
never straddle a live write) and diffs by stable id. There is
deliberately NO stat-based change detector for session data:
file-size, mtime and fresh-connection data_version reads all missed
real committed writes under adversarial probes (a retained WAL writer
leaves main-file stat identity unchanged; a fresh connection's
data_version misses same-size commits, while one persistent reader
observing data_version across calls — used for the activity probe —
sees every one). A fresh read transaction sees every committed write
by construction — including un-checkpointed WAL frames — so this path
cannot serve stale rows. The per-poll cost is one small rollup-table
projection, never a history scan. Invalid numeric/timestamp cells are
rejected to unknown without zero-fill; corrupt message rows are skipped
with counts. Message history is cached per selection with a
(count, max-time_updated) fingerprint: changes only mark the entry
pending and coalesce, the stale cache keeps serving with its as_of,
and a rescan happens only after the 30-second floor elapses — neither
fingerprint changes nor session-revision invalidation can force an
early scan. Coverage and scan freshness stay explicit.

Synchronous by design: callers must invoke it from background workers,
never the GUI/animation thread (wired in slice 5).

Privacy: only allowlisted metadata columns/paths are projected. Session
titles/paths/share links/summary diffs, message bodies and token-adjacent
content, part state/text/file/patch contents, tool arguments/outputs,
auth/credential tables and exports are never read.
"""
from __future__ import annotations

import json
import math
import os
import sqlite3
import threading
import time
from contextlib import closing
from datetime import datetime
from pathlib import Path

from providers import PROVIDER_OPENCODE, base_result

PROVIDER_ID = PROVIDER_OPENCODE

# Busy timeout per 01 (~250 ms read-only transactions, explicit close).
DB_TIMEOUT_S = 0.25
# Historical rescans: on demand/change, at most once per 30 seconds per 01.
HISTORY_TTL_S = 30
# Working lifecycle (slice 4, justified from live evidence in
# docs/PROVIDERS.md): an open step (step-start with no later step-finish
# in the same session) counts as working while younger than the expiry;
# a just-finished step bridges inter-step model latency for the grace
# window. Neither finish reason ('tool-calls' nor 'stop') proves session
# completion — both are followed by new starts live — so completion as a
# distinct state stays unavailable; idle simply means no open step and
# no finish inside the grace window.
OPENCODE_WORKING_EXPIRY_S = 900
OPENCODE_STEP_GRACE_S = 60
# Candidate prefilter margin: live evidence shows step-start bumps the
# session row within ~1 s, so sessions touched inside expiry + margin
# provably include every working session on the observed store. This is
# recall-grade evidence with a 300 s margin, not a proof of exhaustive
# recall — see OPENCODE_ACTIVITY_POLICY.
OPENCODE_PREFILTER_MARGIN_S = 300
# Activity rescan backstop (wall-clock seconds): even if every cheap
# signal below missed a store change, cached lifecycle staleness is
# bounded by this. The storage-byte key already catches every committed
# write class (inserts, same-rowid UPDATEs, same-max DELETEs,
# retained-writer WAL commits, replacements); the backstop only covers
# theoretical residuals such as filesystem timestamp granularity or
# same-inode page surgery. Correctness takes priority over skipping
# scans: a rescan is one bounded statement, never a history scan.
OPENCODE_ACTIVITY_RESCAN_S = 60

# Expiry/grace are candidate policies fitted to one live sample, not
# proven running/completion semantics. The basis, confidence and known
# false positives/negatives travel with every snapshot so consumers
# never mistake the policy for a verified lifecycle proof.
OPENCODE_ACTIVITY_POLICY = {
    'expiry_s': 900,
    'grace_s': 60,
    'prefilter_margin_s': 300,
    'basis': ('live sample: 2933 message-paired steps (durations median '
              '3.3s, p99 109s, max 597s); 2893 inter-step gaps (median 6s, '
              'p90 50s); step-start bumps session row within ~1s (3/3 '
              'open sessions)'),
    'confidence': ('single-machine sample; candidate policy, not proven '
                   'running/completion semantics'),
    'false_positives': ('a closed/crashed app or completed request inside '
                        'the 60s grace window still reports working; an '
                        'abandoned open step reports working until the '
                        '900s expiry lapses',),
    'false_negatives': ('silent work with an open age beyond 900s drops '
                        'the badge until the next lifecycle event; '
                        'inter-step gaps beyond 60s briefly drop the badge '
                        'and self-heal on the next start',),
    'recall_basis': ('one statement covers recently-touched sessions, '
                     'window-fresh parts store-wide, and timeless step '
                     'parts anywhere: no usable recent lifecycle evidence '
                     'can hide behind a stale session row; sessions holding '
                     'none of those are soundly idle'),
}

# Canonical verified capabilities. Anything else (working context with
# bound tokens, quotas, currency, completion) is unsupported until proven.
OPENCODE_CAPABILITIES = frozenset({
    'scopes',            # global / project / conversation, provider-local
    'history',           # session rows + daily buckets from message metadata
    'cost_recorded',     # recorded amount only, currency unstated
    'nullable_fields',   # explicit unknown instead of zero-filled
    'incremental_cache',  # coherent snapshot+diff sessions (no detector);
                         # fingerprinted pending+floor history cache
    'activity',          # session-linked open-step working signal + expiry
})

# Allowlisted session projection. Deliberately excludes titles, slugs,
# paths, share URLs, summary diffs/counts, revert/permission payloads,
# workspace bookkeeping and metadata blobs. The session `version`
# (the OpenCode app version that created the row, e.g. '1.18.31') is
# projected because it gates the recorded-total semantics below; it is
# a version string, never user text.
SESSION_COLUMNS = ('id', 'project_id', 'parent_id', 'directory', 'agent',
                   'model', 'version', 'tokens_input', 'tokens_output',
                   'tokens_reasoning', 'tokens_cache_read',
                   'tokens_cache_write', 'cost', 'time_created',
                   'time_updated')
TOKEN_COLUMNS = ('tokens_input', 'tokens_output', 'tokens_reasoning',
                 'tokens_cache_read', 'tokens_cache_write')
# Session app versions whose stored rollup semantics were verified
# against upstream source (see docs/PROVIDERS.md): their stored input
# already excludes cache read/write, their stored output already
# excludes reasoning, and their own stats code sums all five stored
# categories. Any other version stays Total N/A until reviewed.
OPENCODE_RECORDED_TOTAL_VERSIONS = frozenset({'1.18.31', '1.18.32'})
# Envelope token categories mirror the raw columns one-to-one. Total
# is an OpenCode recorded usage total (sum of the five stored
# categories) for verified versions with complete coverage only —
# never a provider-billed total or current context size.
TOKEN_CATEGORIES = ('input', 'output', 'reasoning', 'cache_read',
                    'cache_write')
_COLUMN_TO_CATEGORY = dict(zip(TOKEN_COLUMNS, TOKEN_CATEGORIES))


def default_db_path():
    return Path(os.environ.get('USERPROFILE') or Path.home()).joinpath(
        '.local', 'share', 'opencode', 'opencode.db')


def scoped_session_id(raw_id):
    return f'{PROVIDER_ID}:{raw_id}'


def scoped_project_id(raw_id):
    return f'{PROVIDER_ID}:{raw_id}'


def strip_scope(value):
    prefix = f'{PROVIDER_ID}:'
    value = (value or '').strip()
    return value[len(prefix):] if value.startswith(prefix) else value


# Display mapping for the existing panel/pet (V1.2 slice 5). These are
# presentation aliases only: raw categories travel under their own
# names, no cross-category sums are formed, and anything without a
# verified meaning stays None (rendered N/A downstream). Unavailable
# adapter reasons map to existing generic catalog keys.
OPENCODE_DISPLAY_STATUS = {
    '': '',
    'session_not_found': 'waiting_available_task',
    'project_unknown': 'waiting_available_task',
    'no_sessions': 'waiting_available_task',
    'missing_store': 'no_reliable_record',
    'store_locked': 'no_reliable_record',
    'unsupported_schema': 'no_reliable_record',
}


def _display_basename(directory):
    cleaned = (directory or '').replace('\\', '/').rstrip('/')
    if '/' in cleaned:
        _, _, base = cleaned.rpartition('/')
        return base or None
    return cleaned or None


def opencode_session_row(read_result, raw_session_id):
    """Find one raw session row by raw id. None when absent: callers
    show unavailable instead of borrowing another session's values."""
    if not raw_session_id:
        return None
    payload = (read_result or {}).get('payload') or {}
    for row in payload.get('sessions') or []:
        if isinstance(row, dict) and row.get('id') == raw_session_id:
            return row
    return None


def opencode_session_identity(read_result):
    """Resolve the selected session row behind a scoped read.

    Returns (row_or_None, raw_session_id_or_None). A missing row stays
    missing: callers show unavailable instead of borrowing another
    session's values.
    """
    read_result = read_result or {}
    identity = read_result.get('identity') or {}
    raw_id = strip_scope(identity.get('session_id') or '')
    if not raw_id:
        return None, None
    return opencode_session_row(read_result, raw_id), raw_id


def _parsed_session_model(row):
    """(model_id_or_None, detail_dict) with arbitrary IDs verbatim."""
    row = row or {}
    model = parse_model(row.get('model'))
    if model is None:
        return None, dict(provider=None, variant=None, agent=row.get('agent'))
    return model.get('id'), dict(provider=model.get('provider'),
                                 variant=model.get('variant'),
                                 agent=row.get('agent'))


def opencode_display(read_result):
    """Render-shape mapping of one OpenCode scoped read.

    Presentation aliases only: raw categories travel under their own
    names (input/output/reasoning/cache_read/cache_write); total is the
    recorded five-category sum for verified versions with complete
    coverage, else None (N/A) — never summed ad hoc, never borrowed.
    Cost keeps amount with currency None, and anything without a
    verified meaning stays None for N/A display.
    Global scope reuses the provider-agnostic all-usage labels; only
    the conversation scope names a single session/model.
    """
    read_result = read_result or {}
    payload = read_result.get('payload') or {}
    identity = read_result.get('identity') or {}
    scope = payload.get('scope') or 'conversation'
    reason = read_result.get('reason') or ''
    available = bool(read_result.get('available', False))
    status = '' if available else OPENCODE_DISPLAY_STATUS.get(
        reason, 'no_reliable_record')
    tokens = dict(read_result.get('tokens') or {})
    for category in ('input', 'output', 'reasoning', 'cache_read',
                     'cache_write', 'total'):
        tokens.setdefault(category, None)
    # Total travels from _token_sums: the recorded five-category sum
    # for verified versions with complete coverage, else None (N/A).
    # It is never recomputed or borrowed here.
    coverage = ((read_result.get('scope_result') or {}).get('coverage')
                or payload.get('coverage') or {})
    cost = read_result.get('cost') or {}
    row, raw_id = opencode_session_identity(read_result)
    model_id, detail = _parsed_session_model(row)
    project_id = identity.get('project_id')
    # Slice 6 analytics breakdown: sanitized per-session rows for the
    # selected scope only (raw categories, verbatim model IDs, scoped
    # identities). No directories/paths, no message content — those never
    # leave the adapter. History aggregates ride along untouched.
    breakdown = []
    for record in payload.get('sessions') or []:
        if not isinstance(record, dict) or not record.get('id'):
            continue
        session_model, _ = _parsed_session_model(record)
        five = [record.get(column) for column in TOKEN_COLUMNS]
        breakdown.append(dict(
            session_id=scoped_session_id(record['id']),
            project_id=(scoped_project_id(record['project_id'])
                        if record.get('project_id') else None),
            parent_id=(scoped_session_id(record['parent_id'])
                       if record.get('parent_id') else None),
            model=session_model, agent=record.get('agent'),
            version=record.get('version'),
            tokens={category: record.get(column) for category, column in
                    (('input', 'tokens_input'), ('output', 'tokens_output'),
                     ('reasoning', 'tokens_reasoning'),
                     ('cache_read', 'tokens_cache_read'),
                     ('cache_write', 'tokens_cache_write'))},
            total=_recorded_total(record.get('version'), five),
            cost_amount=record.get('cost')))
    history = payload.get('history')
    if scope == 'global':
        # Many projects: reuse the provider-agnostic all-usage labels
        # that render/analytics already translate.
        project_name, project_source = 'display_all_usage', 'scope_global'
        title, model_id = 'display_local_history', None
        detail = dict(detail, variant=None)
        raw_id = None
    elif scope == 'project':
        # Many sessions, one project: the adapter's project name fills
        # both project and title slots, like the Codex project scope.
        project_name = identity.get('project_name')
        project_source = ('directory_basename' if project_name
                          else 'unavailable')
        title, model_id = project_name, None
        detail = dict(detail, variant=None)
        raw_id = None
    else:
        project_name = None
        project_source = 'unavailable'
        title = raw_id
        if row is not None:
            project_name = _display_basename(row.get('directory'))
            if project_name:
                project_source = 'directory_basename'
    return dict(
        provider_id=PROVIDER_ID, status=status, available=available,
        scope=scope, scope_identity=dict(identity),
        project=project_name, project_source=project_source,
        project_id=project_id,
        session_id=scoped_session_id(raw_id) if raw_id else None,
        title=title,
        model=model_id, model_detail=detail,
        effort=detail.get('variant'),
        tokens=tokens, token_coverage=dict(coverage),
        cost=dict(amount=cost.get('amount'), currency=None,
                  coverage=cost.get('coverage'),
                  recorded_sessions=cost.get('recorded_sessions'),
                  total_sessions=cost.get('total_sessions')),
        notes=tuple(read_result.get('notes') or ()),
        breakdown_sessions=breakdown, history=history,
        working_context=None, generation=None, selection=None)


def opencode_active_display(row, scope, reason):
    """Main-panel presentation of the verified live OpenCode session.

    Used only when the requested scope names no session (empty/foreign
    pin, unknown project) while selection holds fresh working evidence
    bound to this exact cached row. Every displayed value — project,
    session, model, raw token categories, recorded cost — comes from
    that one row: project/session/model/tokens stay coherent by
    construction. Total is the recorded five-category sum for verified
    versions with complete data (else N/A), currency stays None,
    context/quota/reset stay N/A downstream.

    The identity is scope_type 'active_session' with the requested
    scope preserved alongside the scope-miss status, so live-session
    data can never be mistaken for scoped aggregate data and analytics
    keeps its independent (genuinely empty) scope view.
    """
    if not isinstance(row, dict) or not row.get('id'):
        return None
    tokens, coverage, token_notes = OpenCodeProvider._token_sums([row])
    cost = OpenCodeProvider._cost_summary([row])
    model_id, detail = _parsed_session_model(row)
    project_name = _display_basename(row.get('directory'))
    miss_status = OPENCODE_DISPLAY_STATUS.get(reason or '',
                                             'no_reliable_record')
    notes = [reason, 'active_session_presented'] if reason else [
        'active_session_presented']
    notes.extend(token_notes)
    return dict(
        provider_id=PROVIDER_ID, status='', available=True,
        presentation='active_session', scope=scope,
        scope_identity=dict(
            scope_type='active_session', requested_scope=scope,
            session_id=scoped_session_id(row['id']),
            project_id=(scoped_project_id(row['project_id'])
                        if row.get('project_id') else None)),
        scope_status=miss_status,
        project=project_name,
        project_source=('directory_basename' if project_name
                        else 'unavailable'),
        project_id=(scoped_project_id(row['project_id'])
                    if row.get('project_id') else None),
        session_id=scoped_session_id(row['id']),
        title=row['id'],
        model=model_id, model_detail=detail,
        effort=detail.get('variant'),
        tokens=tokens, token_coverage=coverage,
        cost=dict(amount=cost.get('amount'), currency=None,
                  coverage=cost.get('coverage'),
                  recorded_sessions=cost.get('recorded_sessions'),
                  total_sessions=cost.get('total_sessions')),
        notes=tuple(notes),
        breakdown_sessions=[], history=None,
        working_context=None, generation=None, selection=None)


def opencode_working_context(session_row):
    """Pet-bubble context bound to one OpenCode session row.

    Returns None when the row is missing: the bubble clears instead of
    borrowing another session's values. Token categories stay raw and
    separate; total is the recorded five-category sum for verified
    session versions with complete data, else None (N/A).
    """
    if not isinstance(session_row, dict) or not session_row.get('id'):
        return None
    raw = session_row
    model_id, detail = _parsed_session_model(raw)
    project_name = _display_basename(raw.get('directory'))
    five = [raw.get(column) for column in TOKEN_COLUMNS]
    return dict(
        provider_id=PROVIDER_ID,
        thread=raw.get('id'), title=raw.get('id'),
        project=project_name,
        project_source=('directory_basename' if project_name
                        else 'unavailable'),
        project_id=(scoped_project_id(raw.get('project_id'))
                    if raw.get('project_id') else None),
        status='working',
        tokens=dict(input=raw.get('tokens_input'),
                    output=raw.get('tokens_output'),
                    reasoning=raw.get('tokens_reasoning'),
                    cache_read=raw.get('tokens_cache_read'),
                    cache_write=raw.get('tokens_cache_write'),
                    total=_recorded_total(raw.get('version'), five)),
        available=True, model=model_id, effort=detail.get('variant'),
        context=None)


def _local_day(milliseconds):
    return datetime.fromtimestamp(milliseconds / 1000).date().isoformat()


def _is_number(value):
    """Finite non-boolean number. Booleans, NaN/inf and text are corrupt."""
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    return isinstance(value, float) and math.isfinite(value)


def _valid_token_cell(value):
    return _is_number(value) and value >= 0


def _valid_cost_cell(value):
    # Credits/refunds may be negative; non-finite and text are corrupt.
    return _is_number(value)


def _valid_timestamp(value):
    return _is_number(value) and value >= 0


def _sanitize_session(raw):
    """Keep the row, reject corrupt cells to unknown. Returns (record, bad)."""
    record = dict(raw)
    bad = 0
    for column in TOKEN_COLUMNS:
        value = record.get(column)
        if value is None:
            continue
        if not _valid_token_cell(value):
            record[column] = None
            bad += 1
    cost = record.get('cost')
    if cost is not None and not _valid_cost_cell(cost):
        record['cost'] = None
        bad += 1
    for column in ('time_created', 'time_updated'):
        value = record.get(column)
        if value is None:
            continue
        if not _valid_timestamp(value):
            record[column] = None
            bad += 1
    version = record.get('version')
    if version is not None and not (
            isinstance(version, str) and version.strip()):
        record['version'] = None
        bad += 1
    return record, bad


def _recorded_total(version, values):
    """OpenCode recorded usage total for one scope/row: the sum of the
    five stored categories, exactly as OpenCode's own stats aggregates
    its session rollups. Only for verified session versions with every
    category a valid non-None number (real zeros stay zero); anything
    missing, malformed, partial, or unverified returns None (N/A) —
    never zero-filled, never borrowed. Never a billed total or a
    context size, and never derived from message-level upstream
    totals."""
    if version not in OPENCODE_RECORDED_TOTAL_VERSIONS:
        return None
    if any(value is None for value in values):
        return None
    return sum(values)


def parse_model(raw):
    """Arbitrary model JSON passes through verbatim; unusable stays unknown."""
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    return dict(id=data.get('id'), provider=data.get('providerID'),
                variant=data.get('variant'))


def _valid_delta_cell(value):
    """Message delta cells: None is unknown; booleans, negatives and
    non-finite/wrong-typed numbers invalidate the whole row."""
    if value is None:
        return True
    return _valid_token_cell(value)


def parse_message_tokens(raw):
    """Numeric-only message delta; invalid rows are skipped by callers."""
    if not raw:
        return None
    try:
        inner = raw if isinstance(raw, dict) else json.loads(raw)
        data = inner if isinstance(inner, dict) else json.loads(inner)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    try:
        values = [data.get(key) for key in ('input', 'output', 'reasoning')]
        cache = data.get('cache') or {}
        values += [cache.get('read'), cache.get('write')]
    except AttributeError:
        return None
    if not all(_valid_delta_cell(v) for v in values):
        return None
    return dict(zip(TOKEN_CATEGORIES, values))


class OpenCodeProvider:
    """Read-only incremental adapter over the OpenCode SQLite store."""

    provider_id = PROVIDER_ID

    def __init__(self, db_path=None):
        self.db_path = Path(db_path) if db_path else default_db_path()
        self._sessions = {}
        # File identity (ino/dev only) guards history-cache validity
        # across store replacement. It is NEVER a change detector for
        # session data: every refresh projects fresh regardless.
        self._file_id = None
        self._history_cache = {}
        self.history_scans = 0
        # Incremental lifecycle probe: the last coherent part projection
        # plus the commit generation it was read at. Reused only while a
        # commit-aware signal, the session rows and the recall window
        # prove nothing changed; every reuse re-runs the identical state
        # machine with a fresh clock. A wall-clock backstop supplements
        # the signal but is never the only protection.
        self._activity_probe = None
        self.activity_scans = 0
        # Commit detector: ONE persistent read-only connection whose
        # PRAGMA data_version is read on every snapshot. Validated
        # a connection that has previously read data_version observes
        # every committed change on re-read — same-size/same-rowid
        # UPDATEs, same-max DELETEs, retained-writer WAL commits (no
        # checkpoint), session-table writes — while a fresh connection's
        # data_version misses them all. Uncommitted writes stay
        # invisible; rollback leaves the version untouched. The
        # connection is bound to one file identity: any replacement
        # closes and reopens it, forcing a rescan. Guarded by _dv_lock;
        # closed by close() (also best-effort from __del__).
        self._dv_lock = threading.Lock()
        self._dv_conn = None
        self._dv_file_id = None
        # Terminal shutdown (poller teardown only): once set under
        # _dv_lock, the detector is never opened or reopened. close()
        # stays reusable and never sets this flag.
        self._dv_shutdown = False

    def close(self):
        """Release the persistent commit-detector connection. Idempotent
        and reusable: the detector reopens lazily on the next snapshot
        (unless shutdown() was called); safe to call twice or on a
        provider that never snapshotted."""
        with self._dv_lock:
            self._dv_close_locked()

    def shutdown(self):
        """Terminal shutdown for poller teardown: under the detector
        lock, mark shutdown and close the handle. Afterwards the
        detector is never opened or reopened — in-flight workers
        observe None and evaluate at most once without caching — so no
        handle, live publication, or working context can be recreated.
        Idempotent and prompt: never joins workers or waits on I/O.
        Distinct from reusable close(), which never sets this flag."""
        with self._dv_lock:
            self._dv_shutdown = True
            self._dv_close_locked()

    def _dv_close_locked(self):
        connection, self._dv_conn = self._dv_conn, None
        self._dv_file_id = None
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    def __del__(self):  # pragma: no cover - best-effort GC safety
        try:
            self.close()
        except Exception:
            pass

    @property
    def capabilities(self):
        return OPENCODE_CAPABILITIES

    def cached_session(self, raw_session_id):
        """Read-only copy of one cached session row (or None).

        The cache is refreshed by every read/activity call, so this is
        fresh without extra I/O. Used to bind the working session's
        own project/model/tokens even when the analytics scope points
        elsewhere; a missing row stays missing.
        """
        record = self._sessions.get(raw_session_id or '')
        return dict(record) if isinstance(record, dict) else None

    def _connect(self):
        return sqlite3.connect(self.db_path.as_uri() + '?mode=ro', uri=True,
                               timeout=DB_TIMEOUT_S)

    def _schema(self, connection):
        tables = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        if 'session' not in tables:
            return False, False
        columns = {row[1] for row in connection.execute(
            'PRAGMA table_info(session)')}
        if any(column not in columns for column in SESSION_COLUMNS):
            return False, False
        message = False
        if 'message' in tables:
            message_columns = {row[1] for row in connection.execute(
                'PRAGMA table_info(message)')}
            message = {'id', 'session_id', 'time_created',
                       'data'}.issubset(message_columns)
        return True, message

    def _current_file_id(self):
        try:
            stat = self.db_path.stat()
        except OSError:
            return None
        return (stat.st_ino, stat.st_dev)

    def _dv_open_locked(self, file_id):
        """(Re)open the commit-detector on the current file. Caller holds
        _dv_lock. Returns True when the detector is ready; False leaves
        any old state closed and forces a fresh projection. Refuses
        outright after shutdown(): a closed poller must never regain a
        detector through a late worker. Read-only: the same mode=ro URI
        as every other adapter connection, used only for PRAGMA
        data_version (never content). check_same_thread is off because
        snapshots run on worker threads; all uses are serialized by
        _dv_lock.
        """
        if self._dv_shutdown:
            return False
        self._dv_close_locked()
        try:
            connection = sqlite3.connect(
                self.db_path.as_uri() + '?mode=ro', uri=True,
                timeout=DB_TIMEOUT_S, check_same_thread=False)
            connection.execute('PRAGMA data_version').fetchone()
        except Exception:
            self._dv_close_locked()
            return False
        self._dv_conn = connection
        self._dv_file_id = file_id
        return True

    def _dv_read_locked(self):
        """Current commit generation, or None on any failure. Caller
        holds _dv_lock. A failure closes the detector so the next call
        reopens it; reuse is never allowed on error.
        """
        connection = self._dv_conn
        if connection is None:
            return None
        try:
            return connection.execute(
                'PRAGMA data_version').fetchone()[0]
        except Exception:
            self._dv_close_locked()
            return None

    def refresh(self):
        """Refresh the provider-scoped session cache from a fresh snapshot.

        Every refresh re-projects the allowlisted session table with a
        single SELECT and diffs by stable id. There is deliberately NO
        stat-based skip-if-unchanged detector for session data:
        file-size, mtime and fresh-connection data_version reads all
        missed committed writes under adversarial probes. A fresh read
        transaction observes every committed write — including
        un-checkpointed WAL frames — so this path cannot serve stale
        rows. Replacements (any size), timestamp rollbacks and
        deletions are picked up by the value diff itself.
        Store failures are reported, never raised, so one provider can
        never break the other.
        """
        if not self.db_path.exists():
            return dict(ok=False, reason='missing_store')
        try:
            with closing(self._connect()) as connection:
                connection.row_factory = sqlite3.Row
                columns = ', '.join(SESSION_COLUMNS)
                rows = connection.execute(
                    f'SELECT {columns} FROM session').fetchall()
        except sqlite3.OperationalError as error:
            if 'locked' in str(error).lower():
                return dict(ok=False, reason='store_locked')
            return dict(ok=False, reason='unsupported_schema')
        except sqlite3.Error:
            return dict(ok=False, reason='unsupported_schema')
        fresh = {}
        invalid = 0
        for row in rows:
            record, bad = _sanitize_session(dict(zip(SESSION_COLUMNS,
                                                     tuple(row))))
            invalid += bad
            if record['id'] is None:
                invalid += 1
                continue
            fresh[record['id']] = record
        revised = sum(1 for key, record in fresh.items()
                      if self._sessions.get(key) != record)
        revised += sum(1 for key in self._sessions if key not in fresh)
        file_id = self._current_file_id()
        if file_id is not None and file_id != self._file_id:
            # Different file (replacement): no cached history can be valid.
            self._history_cache = {}
            self._file_id = file_id
        elif revised:
            # Ordinary writes: keep serving cached history but mark every
            # entry pending. Invalidation must not bypass the refresh floor
            # by forcing an immediate rescan.
            for entry in self._history_cache.values():
                entry['pending'] = True
        self._sessions = fresh
        return dict(ok=True, sessions=len(self._sessions), revised=revised,
                    invalid=invalid)

    def _selected(self, scope, pinned):
        records = list(self._sessions.values())
        if scope == 'global':
            identity = dict(scope_type='global', locally_recorded=True)
            return records, identity, ''
        wanted = strip_scope(pinned)
        match = next((r for r in records if r['id'] == wanted), None)
        if match is None:
            identity = dict(scope_type=scope, unavailable=True)
            if scope == 'conversation':
                identity['session_id'] = scoped_session_id(wanted) if wanted else None
            return [], identity, 'session_not_found'
        if scope == 'conversation':
            identity = dict(scope_type='conversation',
                            session_id=scoped_session_id(match['id']),
                            project_id=scoped_project_id(match['project_id'])
                            if match['project_id'] else None)
            return [match], identity, ''
        project_id = match['project_id']
        if not project_id:
            return [], dict(scope_type='project', unavailable=True), 'project_unknown'
        identity = dict(scope_type='project',
                        project_id=scoped_project_id(project_id),
                        project_name=self._project_display(
                            [r for r in records if r['project_id'] == project_id]))
        return [r for r in records if r['project_id'] == project_id], identity, ''

    @staticmethod
    def _project_display(records):
        for record in sorted(records, key=lambda r: r['id']):
            directory = (record.get('directory') or '').replace('\\', '/').rstrip('/')
            if '/' in directory:
                _, _, base = directory.rpartition('/')
                if base:
                    return base
            elif directory:
                return directory
        return None

    @staticmethod
    def _token_sums(records):
        tokens = {}
        coverage = {}
        notes = []
        for category in TOKEN_CATEGORIES:
            column = next(c for c, k in _COLUMN_TO_CATEGORY.items() if k == category)
            values = [r[column] for r in records]
            known = [v for v in values if v is not None]
            if not records:
                tokens[category] = None
                coverage[category] = 'unavailable'
            elif not known:
                # Unknown must not become zero.
                tokens[category] = None
                coverage[category] = 'unknown'
                notes.append(f'{category}_unknown')
            elif len(known) < len(values):
                tokens[category] = sum(known)
                coverage[category] = 'partial'
                notes.append(f'{category}_incomplete')
            else:
                # A real zero (including all-zero rows) stays a complete zero.
                tokens[category] = sum(known)
                coverage[category] = 'complete'
        # OpenCode recorded usage total: the sum of the five stored
        # categories, exactly as OpenCode's own stats aggregates its
        # session rollups — only when every record carries a verified
        # session version and every category is completely known.
        # Anything missing, partial, malformed, or unverified keeps
        # Total N/A (never a subtotal, never zero-filled). Never a
        # billed total, never a context size, never derived from
        # message-level upstream totals.
        if (records and all(r.get('version')
                            in OPENCODE_RECORDED_TOTAL_VERSIONS
                            for r in records)
                and all(coverage.get(category) == 'complete'
                        for category in TOKEN_CATEGORIES)):
            tokens['total'] = sum(tokens[category]
                                  for category in TOKEN_CATEGORIES)
            coverage['total'] = 'complete'
            notes.append('total_recorded_sum')
        else:
            tokens['total'] = None
            coverage['total'] = 'unknown' if records else 'unavailable'
            if records:
                notes.append('total_unavailable_unverified_or_incomplete')
        return tokens, coverage, notes

    @staticmethod
    def _cost_summary(records):
        amounts = [r['cost'] for r in records]
        known = [a for a in amounts if a is not None]
        if not records:
            return dict(amount=None, currency=None, coverage='unknown',
                        recorded_sessions=0, total_sessions=0)
        if len(known) < len(amounts):
            coverage = 'partial'
        else:
            coverage = 'recorded'
        # A recorded 0.0 is a real zero (e.g. free-tier models), not unknown.
        return dict(amount=sum(known) if known else None, currency=None,
                    coverage=coverage if known else 'unknown',
                    recorded_sessions=len(known), total_sessions=len(amounts))

    def _history(self, records, include_history, cache_key):
        if not include_history:
            return None
        sessions = [dict(session_id=scoped_session_id(r['id']),
                         project_id=scoped_project_id(r['project_id'])
                         if r['project_id'] else None,
                         parent_id=scoped_session_id(r['parent_id'])
                         if r['parent_id'] else None,
                         model=parse_model(r['model']), agent=r['agent'],
                         version=r.get('version'),
                         tokens={c: r[next(col for col, key in
                                           _COLUMN_TO_CATEGORY.items()
                                           if key == c)]
                                 for c in TOKEN_CATEGORIES},
                         total=_recorded_total(
                             r.get('version'),
                             [r[column] for column in TOKEN_COLUMNS]),
                         cost_amount=r['cost'], cost_currency=None,
                         time_created=r['time_created'],
                         time_updated=r['time_updated'])
                    for r in sorted(records, key=lambda r: r['id'])]
        daily = self._daily_cached(records, cache_key)
        return dict(sessions=sessions, daily=daily['daily'],
                    daily_coverage=daily['daily_coverage'],
                    skipped_message_rows=daily['skipped'],
                    as_of=daily['scanned_at'], cached=daily['served_cache'],
                    refresh_pending=daily['pending'])

    def _message_fingerprint(self, connection, wanted):
        marks = ', '.join('?' * len(wanted))
        row = connection.execute(
            f"""SELECT COUNT(*), MAX(time_updated) FROM message
                WHERE session_id IN ({marks})""",
            tuple(sorted(wanted))).fetchone()
        return (row[0], row[1] if row[1] is not None else 0)

    def _daily_cached(self, records, cache_key):
        """Coalescing bounded message scan.

        The first history read for a selection scans immediately (there
        is nothing to serve otherwise). Afterwards a rescan happens only
        when an entry is pending AND the 30-second floor since the last
        scan has elapsed. Fingerprint changes and session-revision
        invalidation only mark the entry pending and coalesce — the
        previous scan keeps serving with its as_of — so rapid successive
        writes can never force scans faster than the floor.
        """
        empty = dict(daily=None, daily_coverage=None, skipped=0,
                     pending=False, scanned_at=None, served_cache=False)
        try:
            with closing(self._connect()) as connection:
                _, message_ok = self._schema(connection)
                if not message_ok:
                    return empty
                wanted = {r['id'] for r in records}
                if not wanted:
                    return empty
                fingerprint = self._message_fingerprint(connection, wanted)
                now = time.time()
                entry = self._history_cache.get(cache_key)
                need_scan = entry is None
                if entry is not None:
                    if fingerprint != entry['fingerprint']:
                        # Coalesce: record the newest fingerprint, stay
                        # pending. Successive writes collapse into one
                        # future rescan instead of one scan each.
                        entry['fingerprint'] = fingerprint
                        entry['pending'] = True
                    need_scan = (entry['pending']
                                 and now - entry['scanned_at'] >= HISTORY_TTL_S)
                    if not need_scan:
                        return dict(daily=entry['daily'],
                                    daily_coverage=entry['daily_coverage'],
                                    skipped=entry['skipped'],
                                    pending=entry['pending'],
                                    scanned_at=entry['scanned_at'],
                                    served_cache=True)
                rows = connection.execute(
                    f"""SELECT time_created,
                        json_extract(data,'$.role'), json_extract(data,'$.tokens')
                        FROM message WHERE session_id IN (
                        {', '.join('?' * len(wanted))})""",
                    tuple(sorted(wanted))).fetchall()
        except sqlite3.Error:
            return empty
        daily, daily_coverage, skipped = self._daily_from_rows(rows)
        self.history_scans += 1
        scanned_at = time.time()
        self._history_cache[cache_key] = dict(
            fingerprint=fingerprint, daily=daily,
            daily_coverage=daily_coverage, skipped=skipped,
            pending=False, scanned_at=scanned_at)
        return dict(daily=daily, daily_coverage=daily_coverage,
                    skipped=skipped, pending=False, scanned_at=scanned_at,
                    served_cache=False)

    @staticmethod
    def _daily_from_rows(rows):
        buckets = {}
        skipped = 0
        for created, role, raw_tokens in rows:
            try:
                day_key = _local_day(created)
            except (OverflowError, OSError, ValueError, TypeError):
                # Out-of-range or corrupt timestamps never break the scan.
                skipped += 1
                continue
            bucket = buckets.setdefault(day_key, dict(
                cells={c: [0, 0, 0] for c in TOKEN_CATEGORIES},
                messages=0, user_messages=0, skipped=0))
            deltas = parse_message_tokens(raw_tokens)
            if deltas is None:
                bucket['skipped'] += 1
                skipped += 1
                continue
            bucket['messages'] += 1
            if role == 'user':
                bucket['user_messages'] += 1
            for category in TOKEN_CATEGORIES:
                total, known, seen = bucket['cells'][category]
                value = deltas[category]
                buckets[day_key]['cells'][category] = [
                    total + (value or 0), known + (value is not None), seen + 1]
        if not buckets:
            return None, None, skipped
        daily = {}
        daily_coverage = {}
        for day_key, bucket in sorted(buckets.items()):
            values = dict(messages=bucket['messages'],
                          user_messages=bucket['user_messages'],
                          skipped=bucket['skipped'])
            coverage = {}
            for category in TOKEN_CATEGORIES:
                total, known, seen = bucket['cells'][category]
                if known == 0:
                    values[category] = None
                    coverage[category] = 'unknown'
                else:
                    values[category] = total
                    coverage[category] = ('complete'
                                          if known == seen and not bucket['skipped']
                                          else 'partial')
            daily[day_key] = values
            daily_coverage[day_key] = coverage
        return daily, daily_coverage, skipped

    def activity_snapshot(self, now=None):
        """Session-linked working evidence for provider selection.

        Pairing runs an ordered per-message state machine: live evidence
        shows step-start/finish pairs belong to their message_id, and one
        step-start per message is NOT assumed (start→finish→start leaves
        the latest step open; several completed steps in one message
        close it; equal timestamps close deterministically). A message
        holding an unmatched step-start is open even when a later
        message already finished. A session works while any open message
        is younger than OPENCODE_WORKING_EXPIRY_S, or its latest finish
        is inside OPENCODE_STEP_GRACE_S (inter-step model latency, not
        completion: 'tool-calls' and 'stop' finishes are both followed
        by new starts live). Fresh part writes are reported as evidence
        but never required, so long silent tools stay active.

        All lifecycle metadata comes from ONE statement (one coherent
        snapshot — concurrent writes cannot split it) projecting
        type/reason/timing only, never part state or contents. Recall
        does not depend on unproven session metadata: the statement
        covers recently-touched sessions' parts, window-fresh parts
        store-wide, and timeless step parts anywhere — so a stale
        session row can never hide a fresh valid open step, and idle is
        sound for sessions holding none of those. Timestamps must be
        finite, non-boolean, non-negative and not in the future;
        unusable evidence stays unknown per message/session and can
        never crash the adapter, prove work, or prove idleness.

        Steady-state cost: the projection above is re-executed only
        when the store may have changed — the persistent reader's
        commit generation differs from the cached one, any
        session-table revision occurred since the last projection
        (counted in ``activity_scans``), the recall window widens (an
        older explicit clock always rescans), or the wall-clock
        backstop (OPENCODE_ACTIVITY_RESCAN_S) elapsed as a supplement.
        Otherwise the cached coherent rows are filtered by the current
        window and run through the identical state machine with a fresh
        clock. The generation signal (PRAGMA data_version on one
        persistent read-only connection, validated by probe) observes
        every committed write class that filesystem metadata missed:
        same-size/same-rowid UPDATEs with restored mtimes, same-max
        DELETEs, retained-writer WAL commits without checkpoint, and
        session-table writes; file identity separately forces a rescan
        (with detector reopen) on database replacement. A rollback
        leaves the generation untouched and safely reuses the cache;
        uncommitted writes are never visible to the read-only
        projection. The projection itself is straddle-safe: the
        generation is read before and after the single statement and a
        surrounding commit forces a bounded redo, so the cached rows
        always belong to the cached generation; if every redo still
        straddles a commit, the candidate is discarded and the snapshot
        reports unstable-unknown (valid=False) without evaluation.
        When ``now`` is not
        supplied it is sampled AFTER the probe, so observed times
        cannot predate the clock through sampling order.

        Unproven activity stays unknown: an unreadable store yields
        valid=False (not idle). Expiry/grace are candidate policies,
        not proven semantics: their basis, confidence and known false
        positives/negatives travel in the ``policy`` record.
        """
        if now is None:
            pre_ms = int(time.time() * 1000)
            explicit = False
        else:
            pre_ms = int(now * 1000)
            explicit = True
        unknown = dict(provider_id=PROVIDER_ID, valid=False, working=False,
                       primary_session_id=None, sessions=[],
                       last_lifecycle_at=None, evidence_unknown=False,
                       checked=0, policy=OPENCODE_ACTIVITY_POLICY)
        refreshed = self.refresh()
        if not refreshed.get('ok'):
            unknown['reason'] = refreshed.get('reason', 'missing_store')
            return unknown
        recent_ms = pre_ms - (OPENCODE_WORKING_EXPIRY_S
                              + OPENCODE_PREFILTER_MARGIN_S) * 1000
        file_id = self._current_file_id()
        recent_ids = {sid for sid, record in self._sessions.items()
                      if (record.get('time_updated')
                          if isinstance(record.get('time_updated'),
                                         (int, float))
                          else -1) >= recent_ms}
        probe = self._activity_probe
        now_ms = pre_ms if explicit else int(time.time() * 1000)
        by_session = {}
        use_cache = False
        if (probe is not None and file_id is not None
                and not refreshed.get('revised')
                and recent_ms >= probe['recent_ms']
                and time.monotonic() - probe['scanned_at']
                < OPENCODE_ACTIVITY_RESCAN_S):
            # Commit generation check (serialized with detector
            # maintenance): reuse only when the persistent reader
            # reports the exact generation the rows were projected at.
            # A racing delete/replace yields no file identity and never
            # reuses; a detector failure never reuses.
            with self._dv_lock:
                if self._dv_file_id == file_id:
                    data_version = self._dv_read_locked()
                    use_cache = (data_version is not None
                                 and probe.get('data_version')
                                 == data_version)
        if use_cache:
            # No commit, no session revision, and a window no wider
            # than the cached projection's: the fresh statement would
            # return exactly these rows filtered by the current window,
            # so filter the cached rows instead of rescanning. (A wider
            # window — e.g. an older explicit clock — always rescans.)
            # The identical state machine below then runs with a fresh
            # clock, which is exactly what a fresh fetch would evaluate.
            for row in probe['rows']:
                if (row[0] in recent_ids
                        or (row[2] is not None and row[2] >= recent_ms)
                        or (row[2] is None
                            and row[4] in ('step-start', 'step-finish'))):
                    by_session.setdefault(row[0], []).append(row[1:])
        else:
            rows, data_version, problem = self._project_lifecycle(
                recent_ms, file_id)
            if rows is None:
                unknown['reason'] = (
                    problem or 'activity_unavailable')
                return unknown
            if data_version is not None:
                self._activity_probe = {
                    'data_version': data_version,
                    'recent_ms': recent_ms,
                    'rows': [tuple(row) for row in rows],
                    'scanned_at': time.monotonic()}
            else:
                # Detector unavailable: this coherent projection is
                # evaluated once but never cached, so the next call
                # rescans instead of reusing blind.
                self._activity_probe = None
            for row in rows:
                by_session.setdefault(row[0], []).append(row[1:])
        outcome = dict(provider_id=PROVIDER_ID, valid=True, reason='',
                       working=False, primary_session_id=None, sessions=[],
                       last_lifecycle_at=None, evidence_unknown=False,
                       checked=len(by_session),
                       policy=OPENCODE_ACTIVITY_POLICY)
        lifecycle = []
        best = None
        for sid in sorted(by_session):
            entry, instant = self._evaluate_session(
                sid, by_session[sid], now_ms, lifecycle)
            outcome['sessions'].append(entry)
            if entry['working'] and (
                    best is None or instant > best[0]
                    or (instant == best[0] and sid < best[1])):
                best = (instant, sid)
        outcome['last_lifecycle_at'] = max(lifecycle, default=None)
        outcome['evidence_unknown'] = any(
            e['unknown'] for e in outcome['sessions'])
        if best is not None:
            outcome['working'] = True
            outcome['primary_session_id'] = scoped_session_id(best[1])
        return outcome

    def _dv_current(self, file_id):
        """Commit generation for this file, opening the detector on
        first use. Returns None when the file is gone, the detector
        cannot run, or shutdown() was called (callers rescan and never
        reuse on None, and never reopen after shutdown). Serializes
        detector open/read so worker threads share one connection.
        """
        if file_id is None:
            return None
        with self._dv_lock:
            if self._dv_shutdown:
                return None
            if self._dv_conn is None or self._dv_file_id != file_id:
                if not self._dv_open_locked(file_id):
                    return None
            return self._dv_read_locked()

    def _project_lifecycle(self, recent_ms, file_id):
        """One coherent lifecycle projection with straddle protection.

        Runs the single-statement projection, then re-reads the commit
        generation: a commit landing around the projection forces a
        bounded redo, so returned rows always belong to the returned
        generation. Returns (rows, data_version, reason): reason is None
        when the rows are usable (cached only when data_version is not
        None); 'activity_unavailable' when the store is unreadable; and
        'activity_unstable' when every attempt straddled a real commit —
        the last candidate is discarded entirely and must never be
        evaluated, cached, or published as working or idle. Every
        executed projection counts in ``activity_scans``.
        """
        candidate = None
        for _ in range(3):
            dv_before = self._dv_current(file_id)
            try:
                with closing(self._connect()) as connection:
                    candidate = connection.execute(
                        """SELECT session_id, message_id, time_created, id,
                            json_extract(data,'$.type'),
                            json_extract(data,'$.reason')
                            FROM part
                            WHERE session_id IN (
                                SELECT id FROM session WHERE time_updated >= ?)
                            OR time_created >= ?
                            OR (time_created IS NULL AND
                                json_extract(data,'$.type')
                                IN ('step-start','step-finish'))
                            ORDER BY session_id, message_id, time_created,
                            CASE json_extract(data,'$.type')
                                WHEN 'step-start' THEN 0 ELSE 1 END, id""",
                        (recent_ms, recent_ms)).fetchall()
            except sqlite3.Error:
                return None, None, 'activity_unavailable'
            self.activity_scans += 1
            dv_after = self._dv_current(file_id)
            if dv_before is None or dv_after is None:
                return candidate, None, None
            if dv_after == dv_before:
                return candidate, dv_after, None
        return None, None, 'activity_unstable'

    def _evaluate_session(self, sid, rows, now_ms, lifecycle):
        """Run the ordered per-message lifecycle state machine.

        Returns (entry, working instant). Starts append; a finish
        closes the earliest unmatched start (FIFO: the latest start
        stays the freshest evidence); a finish with nothing open is a
        stray completion signal. Unusable timestamps flag the message
        unknown and are skipped: they prove neither work nor idleness.
        """
        from collections import deque
        session_opens = []
        session_finishes = []
        newest_parts = []
        session_unknown = False
        grouped = []
        for mid, created, pid, typ, reason in rows:
            if not grouped or grouped[-1][0] != mid:
                grouped.append((mid, []))
            grouped[-1][1].append((created, pid, typ, reason))
        for _mid, events in grouped:
            unmatched = deque()
            message_unknown = False
            for created, _pid, typ, reason in events:
                if _valid_timestamp(created) and created <= now_ms:
                    newest_parts.append(created)
                if typ not in ('step-start', 'step-finish'):
                    continue
                if not (_valid_timestamp(created) and created <= now_ms):
                    message_unknown = True
                    continue
                if typ == 'step-start':
                    unmatched.append(created)
                    lifecycle.append(created)
                elif unmatched:
                    unmatched.popleft()
                    session_finishes.append((created, reason))
                    lifecycle.append(created)
                else:
                    session_finishes.append((created, reason))
                    lifecycle.append(created)
            if message_unknown:
                session_unknown = True
            session_opens.extend(unmatched)
        open_age = (now_ms - max(session_opens)) / 1000 if session_opens else None
        latest = None
        for moment, reason in session_finishes:
            if latest is None or moment > latest[0]:
                latest = (moment, reason)
        finish_age = (now_ms - latest[0]) / 1000 if latest else None
        if open_age is not None and open_age < OPENCODE_WORKING_EXPIRY_S:
            state, evidence, instant = True, 'open_step', max(session_opens)
        elif finish_age is not None and finish_age < OPENCODE_STEP_GRACE_S:
            state, evidence, instant = True, 'step_gap', latest[0]
        else:
            state, evidence, instant = False, 'idle', None
        entry = dict(
            session_id=scoped_session_id(sid),
            working=state, evidence=evidence,
            open_age_s=open_age, finish_age_s=finish_age,
            finish_reason=latest[1] if latest else None,
            newest_part_age_s=((now_ms - max(newest_parts)) / 1000
                               if newest_parts else None),
            unknown=session_unknown)
        return entry, instant

    def read(self, pinned='', scope='conversation', include_history=False,
             active_title=''):
        """Read provider-local scoped usage. Activity is reported separately
        via activity_snapshot so scope availability never depends on it.

        ``active_title`` is accepted for selector-signature parity and
        ignored: without a verified OpenCode activity rule, foreground
        titles must not influence the result.
        """
        notes = []
        if scope not in ('global', 'project', 'conversation'):
            scope = 'conversation'
        refreshed = self.refresh()
        if not refreshed.get('ok'):
            reason = refreshed.get('reason', 'missing_store')
            return base_result(PROVIDER_ID, available=False,
                               status='unavailable', reason=reason,
                               capabilities=OPENCODE_CAPABILITIES,
                               notes=(reason,), payload=None)
        if refreshed.get('invalid'):
            notes.append('invalid_values_rejected')
        records, identity, error = self._selected(scope, pinned)
        if error:
            notes.append(error)
            return base_result(PROVIDER_ID, available=False,
                               status='unavailable', reason=error,
                               identity=identity,
                               capabilities=OPENCODE_CAPABILITIES,
                               notes=tuple(notes),
                               payload=dict(scope=scope, scope_identity=identity,
                                            sessions=[], notes=tuple(notes)))
        tokens, coverage, token_notes = self._token_sums(records)
        notes.extend(token_notes)
        cost = self._cost_summary(records)
        if cost['coverage'] == 'partial':
            notes.append('cost_partial')
        cache_key = (scope, strip_scope(pinned))
        history = self._history(records, include_history, cache_key)
        if include_history and (history is None or history['daily'] is None):
            notes.append('daily_unavailable')
        if history is not None and history['skipped_message_rows']:
            notes.append('message_rows_skipped')
        if history is not None and history['refresh_pending']:
            # Stale-but-explicit: a change is recorded, the rescan waits
            # for the 30-second floor. Freshness travels with as_of.
            notes.append('history_refresh_pending')
        activity_at = max((r['time_updated'] for r in records
                           if r['time_updated'] is not None), default=None)
        if not records:
            notes.append('no_sessions')
            return base_result(PROVIDER_ID, available=False,
                               status='unavailable', reason='no_sessions',
                               identity=identity, tokens=tokens,
                               capabilities=OPENCODE_CAPABILITIES,
                               partial=True, notes=tuple(notes),
                               payload=dict(scope=scope,
                                            scope_identity=identity,
                                            sessions=[], tokens=tokens,
                                            coverage=coverage, cost=cost,
                                            history=history,
                                            notes=tuple(notes)))
        scope_result = dict(identity=identity, tokens=tokens,
                            coverage=coverage, available=True,
                            count=len(records),
                            last_activity_at=activity_at,
                            # The recorded total is informational: its
                            # absence never marks the scope's own
                            # categories partial.
                            partial=any(c != 'complete'
                                        for key, c in coverage.items()
                                        if key != 'total'
                                        and c != 'unavailable')
                            or cost['coverage'] != 'recorded')
        partial = scope_result['partial']
        if history is not None and history['daily'] is not None:
            if any(cov != 'complete'
                   for day_cov in history['daily_coverage'].values()
                   for cov in day_cov.values()):
                partial = True
        else:
            if include_history:
                partial = True
        if history is not None and history['skipped_message_rows']:
            partial = True
        return base_result(
            PROVIDER_ID, available=True, status='', identity=identity,
            tokens=tokens, scope_result=scope_result, cost=cost,
            capabilities=OPENCODE_CAPABILITIES,
            partial=partial, notes=tuple(notes),
            payload=dict(scope=scope, scope_identity=identity,
                         sessions=[dict(r) for r in sorted(
                             records, key=lambda r: r['id'])],
                         tokens=tokens, coverage=coverage, cost=cost,
                         history=history, last_activity_at=activity_at,
                         notes=tuple(notes)),
            last_success_at=time.time(),
            source_event_at=activity_at / 1000 if activity_at else None)
