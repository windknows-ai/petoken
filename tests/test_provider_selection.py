# Historical multi-provider ranking is isolated through explicit provider-ID
# injection. Production defaults and preference migration are tested separately.
"""Slice 4: deterministic provider selection. Fake clock, no I/O."""
import copy
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from app_config import load_preferences, normalize_preferences, save_preferences
from app_mode import DAILY_MODE, TOKEN_MODE, AppModeState
from provider_selection import (FRESHNESS_S, STABILITY_S, ProviderSelection,
                                codex_provider_status,
                                normalize_tracking_provider)
from providers import CodexProvider
from usage import CodexStore

NOW = 2000000.0


def status(pid, available=True, working=False, activity_at=None,
           success_at=NOW, error='', **junk):
    """Verified-fixture shorthand.

    Every produced status carries EXPLICIT source_available and
    activity_valid keys (verified unless a test overrides them with
    explicit False through junk). This is test infrastructure, not a
    production default: fail-closed production behavior with omitted
    flags is pinned separately by FailClosedDefaultsTests using raw
    dicts, and real envelopes flow through the shapers in the
    integration tests below.
    """
    snap = dict(provider_id=pid, available=available, working=working,
                activity_at=activity_at, last_success_at=success_at,
                error=error, source_available=True, activity_valid=True)
    snap.update(junk)
    return snap


class FailClosedDefaultsTests(unittest.TestCase):
    """Historical generic-selector flags: raw dicts, no helper."""

    def test_omitted_flags_exclude_from_workers(self):
        sel = ProviderSelection(('codex', 'opencode'))
        bare_working = {'provider_id': 'codex', 'available': True,
                        'working': True, 'activity_at': NOW,
                        'last_success_at': NOW}
        idle = {'provider_id': 'opencode', 'available': True,
                'source_available': True, 'activity_valid': True,
                'working': False, 'activity_at': NOW - 500,
                'last_success_at': NOW}
        snap = sel.update({'codex': bare_working, 'opencode': idle},
                          now=NOW)
        # An unverified working claim cannot force selection, even with
        # a known instant: validity defaults to unknown/False.
        self.assertEqual(snap['selected'], 'opencode')
        self.assertFalse(snap['live'])

    def test_omitted_flags_stay_unknown_in_output(self):
        sel = ProviderSelection(('codex', 'opencode'))
        sel.mark_used('codex', now=NOW - 5)
        bare = {'provider_id': 'codex', 'available': True,
                'source_available': True, 'last_success_at': NOW}
        snap = sel.update({'codex': bare}, now=NOW)
        # Omitted validity stays unknown in the output: selected through
        # use-time, but never presented as confirmed idle.
        self.assertEqual(snap['selected'], 'codex')
        self.assertTrue(snap['activity_unknown'])
        self.assertFalse(snap['live'])

    def test_manual_requires_explicit_source(self):
        sel = ProviderSelection(('codex', 'opencode'))
        bare = {'provider_id': 'opencode', 'available': True,
                'last_success_at': NOW}
        snap = sel.update({'codex': {'provider_id': 'codex',
                                     'available': False,
                                     'source_available': False,
                                     'activity_valid': False,
                                     'last_success_at': NOW},
                           'opencode': bare},
                          preference='opencode', now=NOW)
        self.assertIsNone(snap['selected'])
        self.assertEqual(snap['reason'], 'manual_unavailable')

    def test_helper_injects_explicit_validity(self):
        snap = status('codex', working=True, activity_at=NOW)
        self.assertTrue(snap['source_available'])
        self.assertTrue(snap['activity_valid'])


class PreferenceTests(unittest.TestCase):
    def test_normalize_tracking_provider(self):
        self.assertEqual(normalize_tracking_provider('auto'), 'auto')
        self.assertEqual(normalize_tracking_provider(' Codex '), 'codex')
        self.assertEqual(normalize_tracking_provider(' Claude '), 'claude')
        self.assertEqual(normalize_tracking_provider('OPENCODE'), 'auto')
        for legacy in (None, '', 'all', 'All Providers', 5, True, ['auto']):
            self.assertEqual(normalize_tracking_provider(legacy), 'auto')

    def test_preferences_round_trip_isolated(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'prefs.json'
            save_preferences(path, {'tracking_provider': 'opencode'})
            self.assertEqual(load_preferences(path)['tracking_provider'],
                             'auto')
            save_preferences(path, {'tracking_provider': 'bogus'})
            loaded = load_preferences(path)
            self.assertEqual(loaded['tracking_provider'], 'auto')
            # Legacy files without the key gain the default; old keys stay.
            save_preferences(path, {'scope': 'global'})
            loaded = load_preferences(path)
            self.assertEqual(loaded['tracking_provider'], 'auto')
            self.assertEqual(loaded['scope'], 'global')

    def test_normalize_keeps_existing_keys(self):
        prefs = normalize_preferences({'tracking_provider': 'codex',
                                       'settings_schema_version': 2,
                                       'custom': 1})
        self.assertEqual((prefs['tracking_provider'], prefs['custom']),
                         ('codex', 1))

    def test_forced_codex_from_codex_only_builds_migrates_once_to_auto(self):
        # V1.3/V1.4 had no provider choice and saved the forced value.
        for raw in ({'tracking_provider': 'codex'},
                    {'tracking_provider': 'codex', 'settings_schema_version': 1}):
            migrated = normalize_preferences(raw)
            self.assertEqual(migrated['tracking_provider'], 'auto')
            self.assertEqual(migrated['settings_schema_version'], 2)
            # A Codex choice saved by V1.5 itself is a real choice and stays.
            again = normalize_preferences(dict(migrated, tracking_provider='codex'))
            self.assertEqual(again['tracking_provider'], 'codex')
        claude = normalize_preferences({'tracking_provider': 'claude'})
        self.assertEqual(claude['tracking_provider'], 'claude')


class ManualSelectionTests(unittest.TestCase):
    def test_manual_wins_immediately_over_working_other(self):
        sel = ProviderSelection(('codex', 'opencode'))
        inputs = {'codex': status('codex', working=True, activity_at=NOW),
                  'opencode': status('opencode', working=True,
                                     activity_at=NOW - 10)}
        snap = sel.update(inputs, preference='opencode', now=NOW)
        self.assertEqual((snap['selected'], snap['live'], snap['reason']),
                         ('opencode', True, 'manual'))
        self.assertFalse(snap['historical'])

    def test_manual_unavailable_lands_daily_immediately(self):
        sel = ProviderSelection(('codex', 'opencode'))
        sel.update({'codex': status('codex', working=True,
                                   activity_at=NOW)}, now=NOW)
        snap = sel.update({'codex': status('codex', working=True,
                                           activity_at=NOW),
                           'opencode': status('opencode', available=False,
                                              source_available=False,
                                              activity_valid=False,
                                              error='missing_store')},
                          preference='opencode', now=NOW)
        self.assertIsNone(snap['selected'])
        self.assertFalse(snap['live'])
        self.assertEqual(snap['reason'], 'manual_unavailable')

    def test_manual_marks_use_time_externally(self):
        sel = ProviderSelection(('codex', 'opencode'))
        sel.mark_used('opencode', now=NOW)
        self.assertEqual(sel.last_use, {'opencode': NOW})
        sel.mark_used('bogus', now=NOW)
        self.assertEqual(sel.last_use, {'opencode': NOW})


class AutoRankingTests(unittest.TestCase):
    def test_sole_working_wins(self):
        sel = ProviderSelection(('codex', 'opencode'))
        snap = sel.update(
            {'codex': status('codex', activity_at=NOW - 100),
             'opencode': status('opencode', working=True,
                                activity_at=NOW - 50)}, now=NOW)
        self.assertEqual((snap['selected'], snap['live'], snap['reason']),
                         ('opencode', True, 'working'))

    def test_both_working_newest_activity_wins(self):
        sel = ProviderSelection(('codex', 'opencode'))
        snap = sel.update(
            {'codex': status('codex', working=True, activity_at=NOW - 30),
             'opencode': status('opencode', working=True,
                                activity_at=NOW - 5)}, now=NOW)
        self.assertEqual(snap['selected'], 'opencode')
        self.assertEqual(snap['reason'], 'both_working_recency')
        self.assertTrue(snap['live'])

    def test_both_working_tie_retains_current(self):
        sel = ProviderSelection(('codex', 'opencode'))
        first = {'codex': status('codex', working=True, activity_at=NOW),
                 'opencode': status('opencode', working=True,
                                    activity_at=NOW - 5)}
        sel.update(first, now=NOW)
        tied = {'codex': status('codex', working=True, activity_at=NOW),
                'opencode': status('opencode', working=True,
                                   activity_at=NOW)}
        snap = sel.update(tied, now=NOW)
        self.assertEqual(snap['selected'], 'codex')
        self.assertTrue(snap['tie_broken'])

    def test_both_working_tie_fresh_prefers_stable_order(self):
        sel = ProviderSelection(('codex', 'opencode'))
        snap = sel.update(
            {'opencode': status('opencode', working=True, activity_at=NOW),
             'codex': status('codex', working=True, activity_at=NOW)},
            now=NOW)
        self.assertEqual(snap['selected'], 'codex')
        self.assertTrue(snap['tie_broken'])

    def test_unknown_activity_sorts_last(self):
        sel = ProviderSelection(('codex', 'opencode'))
        snap = sel.update(
            {'codex': status('codex', working=True, activity_at=None),
             'opencode': status('opencode', working=True,
                                activity_at=NOW - 999)}, now=NOW)
        self.assertEqual(snap['selected'], 'opencode')

    def test_neither_working_newest_activity_wins_historical(self):
        sel = ProviderSelection(('codex', 'opencode'))
        snap = sel.update(
            {'codex': status('codex', activity_at=NOW - 100),
             'opencode': status('opencode', activity_at=NOW - 10)}, now=NOW)
        self.assertEqual(snap['selected'], 'opencode')
        self.assertEqual(snap['reason'], 'idle_recency')
        self.assertFalse(snap['live'])
        self.assertTrue(snap['historical'])

    def test_explicit_use_beats_older_activity(self):
        sel = ProviderSelection(('codex', 'opencode'))
        sel.mark_used('codex', now=NOW - 5)
        snap = sel.update(
            {'codex': status('codex', activity_at=NOW - 100),
             'opencode': status('opencode', activity_at=NOW - 10)}, now=NOW)
        self.assertEqual(snap['selected'], 'codex')

    def test_auto_selection_never_refreshes_use_time(self):
        sel = ProviderSelection(('codex', 'opencode'))
        sel.update({'codex': status('codex', activity_at=NOW),
                    'opencode': status('opencode', activity_at=NOW - 50)},
                   now=NOW)
        self.assertEqual(sel.last_use, {})

    def test_all_unknown_retains_current(self):
        sel = ProviderSelection(('codex', 'opencode'))
        sel.update({'codex': status('codex', activity_at=NOW)}, now=NOW)
        snap = sel.update({'codex': status('codex'),
                           'opencode': status('opencode')}, now=NOW)
        self.assertEqual((snap['selected'], snap['reason']),
                         ('codex', 'retained_current'))

    def test_all_unknown_fresh_uses_stable_order(self):
        sel = ProviderSelection(('codex', 'opencode'))
        snap = sel.update({'opencode': status('opencode'),
                           'codex': status('codex')}, now=NOW)
        self.assertEqual((snap['selected'], snap['reason']),
                         ('codex', 'stable_order'))

    def test_no_provider_means_unavailable_empty(self):
        sel = ProviderSelection(('codex', 'opencode'))
        snap = sel.update({'codex': status('codex', available=False,
                                           source_available=False,
                                           activity_valid=False,
                                           error='missing_store'),
                           'opencode': status('opencode', available=False,
                                              source_available=False,
                                              activity_valid=False,
                                              error='missing_store')},
                          now=NOW)
        self.assertIsNone(snap['selected'])
        self.assertFalse(snap['live'])
        self.assertEqual(snap['reason'], 'no_provider')

    def test_foreground_keys_cannot_change_ranking(self):
        sel = ProviderSelection(('codex', 'opencode'))
        base = {'codex': status('codex', activity_at=NOW - 100),
                'opencode': status('opencode', activity_at=NOW - 10)}
        plain = sel.update(dict(base), now=NOW)
        loaded = ProviderSelection(('codex', 'opencode'))
        spiked = loaded.update(
            {'codex': status('codex', activity_at=NOW - 100,
                             foreground=True, active_title='Codex Task'),
             'opencode': status('opencode', activity_at=NOW - 10)},
            now=NOW)
        self.assertEqual(plain['selected'], spiked['selected'])
        self.assertEqual(spiked['selected'], 'opencode')


class StabilityTests(unittest.TestCase):
    def test_switch_waits_one_second(self):
        sel = ProviderSelection(('codex', 'opencode'))
        sel.update({'codex': status('codex', working=True, activity_at=NOW),
                    'opencode': status('opencode', activity_at=NOW - 50)},
                   now=NOW)
        changed = {'codex': status('codex', activity_at=NOW),
                   'opencode': status('opencode', working=True,
                                      activity_at=NOW)}
        snap = sel.update(changed, now=NOW)
        self.assertEqual(snap['selected'], 'codex')
        self.assertEqual(snap['pending_switch'], 'opencode')
        snap = sel.update(changed, now=NOW + STABILITY_S - 0.5)
        self.assertEqual(snap['selected'], 'codex')
        snap = sel.update(changed, now=NOW + STABILITY_S)
        self.assertEqual(snap['selected'], 'opencode')
        self.assertIsNone(snap['pending_switch'])

    def test_flapping_never_switches(self):
        sel = ProviderSelection(('codex', 'opencode'))
        sel.update({'codex': status('codex', working=True, activity_at=NOW),
                    'opencode': status('opencode', activity_at=NOW - 50)},
                   now=NOW)
        alt_b = {'codex': status('codex', activity_at=NOW),
                 'opencode': status('opencode', working=True,
                                    activity_at=NOW)}
        alt_a = {'codex': status('codex', working=True, activity_at=NOW),
                 'opencode': status('opencode', activity_at=NOW)}
        tick = NOW
        for batch in (alt_b, alt_a, alt_b, alt_a, alt_b):
            tick += 0.4
            snap = sel.update(batch, now=tick)
        self.assertEqual(snap['selected'], 'codex')

    def test_unavailable_current_switches_immediately(self):
        sel = ProviderSelection(('codex', 'opencode'))
        sel.update({'codex': status('codex', working=True, activity_at=NOW),
                    'opencode': status('opencode', activity_at=NOW - 50)},
                   now=NOW)
        snap = sel.update(
            {'codex': status('codex', available=False,
                             source_available=False, activity_valid=False,
                             error='store_locked'),
             'opencode': status('opencode', activity_at=NOW - 50)}, now=NOW)
        self.assertEqual(snap['selected'], 'opencode')
        self.assertIsNone(snap['pending_switch'])

    def test_badge_drops_immediately_on_stop(self):
        sel = ProviderSelection(('codex', 'opencode'))
        sel.update({'codex': status('codex', working=True, activity_at=NOW),
                    'opencode': status('opencode', activity_at=NOW - 500)},
                   now=NOW)
        snap = sel.update(
            {'codex': status('codex', activity_at=NOW),
             'opencode': status('opencode', activity_at=NOW - 500)}, now=NOW)
        self.assertEqual(snap['selected'], 'codex')
        self.assertFalse(snap['live'])
        self.assertTrue(snap['historical'])
        self.assertEqual(snap['reason'], 'idle_recency')


class FreshnessFailureTests(unittest.TestCase):
    def test_stale_working_loses_live_but_stays_selectable(self):
        sel = ProviderSelection(('codex', 'opencode'))
        snap = sel.update(
            {'codex': status('codex', working=True, activity_at=NOW - 100,
                             success_at=NOW - FRESHNESS_S - 1),
             'opencode': status('opencode', activity_at=NOW - 500)},
            now=NOW)
        self.assertEqual(snap['selected'], 'codex')
        self.assertFalse(snap['live'])
        self.assertTrue(snap['stale'])
        self.assertTrue(snap['historical'])

    def test_failure_removes_live_immediately(self):
        sel = ProviderSelection(('codex', 'opencode'))
        sel.update({'codex': status('codex', working=True, activity_at=NOW)},
                   now=NOW)
        snap = sel.update({'codex': status('codex', available=False,
                                           source_available=False,
                                           activity_valid=False,
                                           working=True, activity_at=NOW,
                                           error='store_locked')}, now=NOW)
        self.assertIsNone(snap['selected'])
        self.assertFalse(snap['live'])


class GenerationTests(unittest.TestCase):
    def test_late_generation_rejected(self):
        sel = ProviderSelection(('codex', 'opencode'))
        first = sel.update(
            {'codex': status('codex', activity_at=NOW)}, now=NOW,
            generation=5)
        late = sel.update(
            {'codex': status('codex', activity_at=NOW),
             'opencode': status('opencode', working=True,
                                activity_at=NOW)}, now=NOW, generation=3)
        # Payload ignored, but the recompute correctly records that the
        # retained winner is now current (detail evolves, outcome not).
        for key in ('selected', 'live', 'stale', 'historical', 'reason',
                    'preference', 'applied_generation'):
            self.assertEqual(late[key], first[key], key)
        self.assertEqual(late['applied_generation'], 5)
        current = sel.update(
            {'codex': status('codex', activity_at=NOW),
             'opencode': status('opencode', working=True,
                                activity_at=NOW)}, now=NOW, generation=5)
        self.assertEqual(current['applied_generation'], 5)
        advanced = sel.update(
            {'codex': status('codex', activity_at=NOW),
             'opencode': status('opencode', working=True,
                                activity_at=NOW)}, now=NOW + STABILITY_S,
            generation=7)
        self.assertEqual(advanced['selected'], 'opencode')

    def test_late_result_after_switch_ignored(self):
        sel = ProviderSelection(('codex', 'opencode'))
        sel.update({'codex': status('codex', working=True, activity_at=NOW)},
                   now=NOW, generation=1)
        sel.update({'opencode': status('opencode', working=True,
                                       activity_at=NOW)}, now=NOW,
                   generation=2)
        sel.update({'opencode': status('opencode', working=True,
                                       activity_at=NOW)},
                   now=NOW + STABILITY_S, generation=3)
        self.assertEqual(sel.snapshot()['selected'], 'opencode')
        stale = sel.update(
            {'codex': status('codex', working=True, activity_at=NOW)},
            now=NOW + STABILITY_S, generation=2)
        self.assertEqual(stale['selected'], 'opencode')
        self.assertEqual(stale['applied_generation'], 3)


class ModeFeedTests(unittest.TestCase):
    def test_provider_agnostic_feed_preserves_hysteresis(self):
        mode = AppModeState()
        self.assertEqual(mode.update(True, True, now=1), DAILY_MODE)
        self.assertEqual(mode.update(True, True, now=1.5), TOKEN_MODE)
        self.assertEqual(mode.update(False, True, now=2), TOKEN_MODE)
        self.assertEqual(mode.update(False, True, now=4.1), DAILY_MODE)
        mode = AppModeState()
        mode.update(True, reliable=False, now=1)
        self.assertEqual(mode.update(True, reliable=False, now=2),
                         DAILY_MODE)




class ManualBypassTests(unittest.TestCase):
    def test_manual_bypasses_debounce_both_directions(self):
        sel = ProviderSelection(('codex', 'opencode'))
        codex_live = {'codex': status('codex', working=True,
                                      activity_at=NOW),
                      'opencode': status('opencode', working=True,
                                         activity_at=NOW - 5)}
        sel.update(codex_live, now=NOW)
        self.assertEqual(sel.snapshot()['selected'], 'codex')
        # Choosing OpenCode while Codex is selected must switch at once,
        # clearing the pending Auto state — not via pending_switch.
        sel.mark_used('opencode', now=NOW)
        switched = sel.update(codex_live, preference='opencode', now=NOW)
        self.assertEqual(switched['selected'], 'opencode')
        self.assertIsNone(switched['pending_switch'])
        self.assertEqual(switched['reason'], 'manual')
        # And back: manual Codex while OpenCode is selected.
        sel.mark_used('codex', now=NOW)
        back = sel.update(codex_live, preference='codex', now=NOW)
        self.assertEqual(back['selected'], 'codex')
        self.assertIsNone(back['pending_switch'])

    def test_manual_during_pending_auto_discards_pending(self):
        sel = ProviderSelection(('codex', 'opencode'))
        sel.update({'codex': status('codex', working=True, activity_at=NOW),
                    'opencode': status('opencode', activity_at=NOW - 50)},
                   now=NOW)
        rising = {'codex': status('codex', activity_at=NOW),
                  'opencode': status('opencode', working=True,
                                     activity_at=NOW)}
        staged = sel.update(rising, now=NOW)
        self.assertEqual(staged['pending_switch'], 'opencode')
        sel.mark_used('codex', now=NOW)
        held = sel.update(rising, preference='codex', now=NOW)
        self.assertEqual(held['selected'], 'codex')
        self.assertIsNone(held['pending_switch'])


class ValiditySeparationTests(unittest.TestCase):
    def test_missing_scope_working_provider_still_wins(self):
        sel = ProviderSelection(('codex', 'opencode'))
        codex = status('codex', available=False, source_available=True,
                       activity_valid=True, working=True, activity_at=NOW,
                       error='status_pinned_unavailable')
        opencode = status('opencode', available=True, source_available=True,
                          activity_valid=True, working=False,
                          activity_at=NOW - 500)
        snap = sel.update({'codex': codex, 'opencode': opencode}, now=NOW)
        # Scope availability never gates provider liveness.
        self.assertEqual(snap['selected'], 'codex')
        self.assertTrue(snap['live'])
        self.assertTrue(snap['source_available'])
        self.assertFalse(snap['data_available'])
        self.assertFalse(snap['activity_unknown'])

    def test_unverified_activity_stays_unknown(self):
        sel = ProviderSelection(('codex', 'opencode'))
        sel.mark_used('opencode', now=NOW - 5)
        codex = status('codex', available=True, source_available=True,
                       activity_valid=True, working=False, activity_at=None)
        opencode = status('opencode', available=True, source_available=True,
                          activity_valid=False, working=False,
                          activity_at=None)
        snap = sel.update({'codex': codex, 'opencode': opencode}, now=NOW)
        # Use-time wins, but the winner must not claim confirmed idle.
        self.assertEqual(snap['selected'], 'opencode')
        self.assertFalse(snap['live'])
        self.assertTrue(snap['activity_unknown'])
        self.assertTrue(snap['historical'])

    def test_invalid_activity_blocks_working_claim(self):
        sel = ProviderSelection(('codex', 'opencode'))
        codex = status('codex', available=True, source_available=True,
                       activity_valid=False, working=True, activity_at=NOW)
        opencode = status('opencode', available=True, source_available=True,
                          activity_valid=True, working=False,
                          activity_at=NOW - 500)
        snap = sel.update({'codex': codex, 'opencode': opencode}, now=NOW)
        # An unverified working claim cannot force selection.
        self.assertEqual(snap['selected'], 'opencode')
        self.assertFalse(snap['live'])

    def test_error_excludes_despite_history(self):
        sel = ProviderSelection(('codex', 'opencode'))
        codex = status('codex', available=False, source_available=False,
                       activity_valid=False, working=False, activity_at=None,
                       error='store_locked')
        opencode = status('opencode', available=True, source_available=True,
                          activity_valid=True, working=False,
                          activity_at=NOW - 500)
        snap = sel.update({'codex': codex, 'opencode': opencode}, now=NOW)
        self.assertEqual(snap['selected'], 'opencode')
        self.assertFalse(snap['live'])
        manual = sel.update({'codex': codex, 'opencode': opencode},
                            preference='codex', now=NOW)
        self.assertIsNone(manual['selected'])
        self.assertEqual(manual['reason'], 'manual_unavailable')


class LateReevaluationTests(unittest.TestCase):
    def test_late_batch_reevaluates_freshness(self):
        # Reviewer repro: generation 2 live at t, rejected generation 1
        # at t+6 must return live=False/stale=True, not frozen values.
        sel = ProviderSelection(('codex', 'opencode'))
        live_batch = {'codex': status('codex', working=True,
                                      activity_at=NOW)}
        sel.update(live_batch, now=NOW, generation=2)
        self.assertTrue(sel.snapshot()['live'])
        reevaluated = sel.update(live_batch, now=NOW + 6, generation=1)
        self.assertEqual(reevaluated['applied_generation'], 2)
        self.assertEqual(reevaluated['selected'], 'codex')
        self.assertFalse(reevaluated['live'])
        self.assertTrue(reevaluated['stale'])
        self.assertTrue(reevaluated['historical'])

    def test_manual_change_during_inflight_poll(self):
        sel = ProviderSelection(('codex', 'opencode'))
        sel.update({'codex': status('codex', working=True, activity_at=NOW),
                    'opencode': status('opencode', activity_at=NOW - 50)},
                   now=NOW, generation=5)
        sel.mark_used('opencode', now=NOW)
        # A late poll batch cannot block the current manual preference.
        switched = sel.update(
            {'codex': status('codex', working=True, activity_at=NOW),
             'opencode': status('opencode', activity_at=NOW - 50)},
            preference='opencode', now=NOW, generation=4)
        self.assertEqual(switched['selected'], 'opencode')
        self.assertEqual(switched['reason'], 'manual')
        self.assertEqual(switched['applied_generation'], 5)

    def test_mismatched_provider_tags_dropped(self):
        sel = ProviderSelection(('codex', 'opencode'))
        swapped = {'codex': status('opencode', working=True,
                                   activity_at=NOW),
                   'opencode': status('codex', working=False)}
        snap = sel.update(swapped, now=NOW)
        self.assertIsNone(snap['selected'])
        self.assertEqual(snap['reason'], 'no_provider')


class AttributableRecencyTests(unittest.TestCase):
    # Codex fixture latest token_count event time ('2026-09-19T12:00:02Z').
    TOKEN_EPOCH = datetime(2026, 9, 19, 12, 0, 2,
                           tzinfo=timezone.utc).timestamp()
    # Codex fixture task_started event time ('2026-09-19T12:00:01Z').
    SAMPLE_EPOCH = datetime(2026, 9, 19, 12, 0, 1,
                            tzinfo=timezone.utc).timestamp()

    def test_codex_shaper_uses_lifecycle_not_row_clock(self):
        import tests.test_providers as codex_fixture
        home_dir = tempfile.TemporaryDirectory()
        self.addCleanup(home_dir.cleanup)
        home = codex_fixture.write_home(home_dir.name,
                                        [{'id': 't1', 'working': True}])
        read = CodexProvider(CodexStore(home)).read(
            active_title='t1', scope='conversation',
            activity_detection_valid=True)
        shaped = codex_provider_status(read, last_success_at=NOW)
        # Latest token_count event time, not thread updated_at.
        self.assertEqual(shaped['activity_at'], self.TOKEN_EPOCH)
        self.assertTrue(shaped['source_available'])
        self.assertTrue(shaped['activity_valid'])
        self.assertTrue(shaped['working'])
        idle = CodexProvider(CodexStore(home)).read(scope='conversation')
        shaped_idle = codex_provider_status(idle, last_success_at=NOW)
        # No foreground/UIA info, but the verified thread is genuinely
        # working in the background: UIA absence must not veto provider
        # live state, so the shaper still reports Working with the
        # attributable token instant.
        self.assertTrue(shaped_idle['working'])
        self.assertEqual(shaped_idle['activity_at'], self.TOKEN_EPOCH)

    def test_codex_missing_scope_keeps_source_and_working(self):
        import tests.test_providers as codex_fixture
        home_dir = tempfile.TemporaryDirectory()
        self.addCleanup(home_dir.cleanup)
        home = codex_fixture.write_home(home_dir.name,
                                        [{'id': 't1', 'working': True},
                                         {'id': 't2'}])
        read = CodexProvider(CodexStore(home)).read(
            active_title='t1', pinned='ghost', scope='conversation',
            activity_detection_valid=True)
        self.assertFalse(read['available'])
        shaped = codex_provider_status(read, last_success_at=NOW)
        self.assertTrue(shaped['source_available'])
        self.assertFalse(shaped['available'])
        self.assertTrue(shaped['working'])
        self.assertTrue(shaped['activity_valid'])




class EndToEndValidityTests(unittest.TestCase):
    def test_absent_result_is_fully_unknown(self):
        shaped = codex_provider_status(None)
        self.assertFalse(shaped['source_available'])
        self.assertFalse(shaped['activity_valid'])
        self.assertFalse(shaped['working'])
        self.assertIsNone(shaped['activity_at'])
        sel = ProviderSelection(('codex', 'opencode'))
        opencode = status('opencode', activity_at=NOW - 500)
        snap = sel.update({'codex': shaped, 'opencode': opencode}, now=NOW)
        self.assertEqual(snap['selected'], 'opencode')

    def test_missing_detector_block_stays_unknown(self):
        import tests.test_providers as codex_fixture
        home_dir = tempfile.TemporaryDirectory()
        self.addCleanup(home_dir.cleanup)
        home = codex_fixture.write_home(home_dir.name,
                                        [{'id': 't1', 'working': True}])
        read = CodexProvider(CodexStore(home)).read(
            active_title='t1', scope='conversation',
            activity_detection_valid=True)
        del read['payload']['codex_activity']
        shaped = codex_provider_status(read, last_success_at=NOW)
        self.assertFalse(shaped['activity_valid'])
        self.assertFalse(shaped['working'])
        sel = ProviderSelection(('codex', 'opencode'))
        snap = sel.update(
            {'codex': shaped,
             'opencode': status('opencode', activity_at=NOW - 500)},
            now=NOW)
        # Cached context never proves current work; unknown output flagged.
        self.assertEqual(snap['selected'], 'opencode')
        unused = sel.update(
            {'codex': shaped}, now=NOW, preference='codex')
        self.assertEqual(unused['selected'], 'codex')
        self.assertTrue(unused['activity_unknown'])
        self.assertFalse(unused['live'])

    def test_source_failure_with_cached_working_context_excluded(self):
        import tests.test_providers as codex_fixture
        home_dir = tempfile.TemporaryDirectory()
        self.addCleanup(home_dir.cleanup)
        home = codex_fixture.write_home(home_dir.name,
                                        [{'id': 't1', 'working': True}])
        read = CodexProvider(CodexStore(home)).read(
            active_title='t1', scope='conversation',
            activity_detection_valid=True)
        # Explicit source failure over cached working data.
        read['payload']['status'] = 'status_database_unavailable'
        read['reason'] = 'status_database_unavailable'
        shaped = codex_provider_status(read, last_success_at=NOW)
        self.assertFalse(shaped['source_available'])
        self.assertFalse(shaped['working'])
        self.assertTrue(shaped['available'])  # cached data displayable
        sel = ProviderSelection(('codex', 'opencode'))
        snap = sel.update(
            {'codex': shaped,
             'opencode': status('opencode', activity_at=NOW - 500)},
            now=NOW)
        self.assertEqual(snap['selected'], 'opencode')
        self.assertFalse(snap['live'])
        self.assertTrue(snap['historical'])

    def test_missing_scope_verified_working_wins_live(self):
        import tests.test_providers as codex_fixture
        home_dir = tempfile.TemporaryDirectory()
        self.addCleanup(home_dir.cleanup)
        home = codex_fixture.write_home(home_dir.name,
                                        [{'id': 't1', 'working': True},
                                         {'id': 't2'}])
        read = CodexProvider(CodexStore(home)).read(
            active_title='t1', pinned='ghost', scope='conversation',
            activity_detection_valid=True)
        shaped = codex_provider_status(read, last_success_at=NOW)
        sel = ProviderSelection(('codex', 'opencode'))
        snap = sel.update(
            {'codex': shaped,
             'opencode': status('opencode', activity_at=NOW - 500)},
            now=NOW)
        self.assertEqual(snap['selected'], 'codex')
        self.assertTrue(snap['live'])
        self.assertFalse(snap['data_available'])
        self.assertFalse(snap['activity_unknown'])

    def test_verified_idle_beats_unknown(self):
        import tests.test_providers as codex_fixture
        home_dir = tempfile.TemporaryDirectory()
        self.addCleanup(home_dir.cleanup)
        home = codex_fixture.write_home(home_dir.name, [{'id': 't1'}])
        read = CodexProvider(CodexStore(home)).read(
            scope='global', activity_detection_valid=True)
        shaped = codex_provider_status(read, last_success_at=NOW)
        self.assertTrue(shaped['source_available'])
        self.assertTrue(shaped['activity_valid'])
        self.assertFalse(shaped['working'])
        sel = ProviderSelection(('codex', 'opencode'))
        opencode = status('opencode', activity_at=None)
        opencode['activity_valid'] = False
        snap = sel.update({'codex': shaped, 'opencode': opencode}, now=NOW)
        # Verified idle outranks unknown; output confirms no unknown flag.
        self.assertEqual(snap['selected'], 'codex')
        self.assertFalse(snap['live'])
        self.assertFalse(snap['activity_unknown'])
        self.assertTrue(snap['historical'])

    def test_outer_reason_failure_invalidates_cached_working(self):
        import tests.test_providers as codex_fixture
        home_dir = tempfile.TemporaryDirectory()
        self.addCleanup(home_dir.cleanup)
        home = codex_fixture.write_home(home_dir.name,
                                        [{'id': 't1', 'working': True}])
        read = CodexProvider(CodexStore(home)).read(
            active_title='t1', scope='conversation',
            activity_detection_valid=True)
        # ONLY the outer reason changes: cached successful payload and
        # working_context stay exactly as read.
        read['reason'] = 'status_database_unavailable'
        shaped = codex_provider_status(read, last_success_at=NOW)
        self.assertFalse(shaped['source_available'])
        self.assertFalse(shaped['working'])
        self.assertTrue(shaped['available'])  # cached data displayable
        sel = ProviderSelection(('codex', 'opencode'))
        snap = sel.update(
            {'codex': shaped,
             'opencode': status('opencode', activity_at=NOW - 500)},
            now=NOW)
        self.assertEqual(snap['selected'], 'opencode')
        self.assertFalse(snap['live'])


    def test_verified_working_carries_no_unknown_flag(self):
        import tests.test_providers as codex_fixture
        home_dir = tempfile.TemporaryDirectory()
        self.addCleanup(home_dir.cleanup)
        home = codex_fixture.write_home(home_dir.name,
                                        [{'id': 't1', 'working': True}])
        read = CodexProvider(CodexStore(home)).read(
            active_title='t1', scope='global',
            activity_detection_valid=True)
        shaped = codex_provider_status(read, last_success_at=NOW)
        sel = ProviderSelection(('codex', 'opencode'))
        snap = sel.update(
            {'codex': shaped,
             'opencode': status('opencode', activity_at=NOW - 500)},
            now=NOW)
        self.assertEqual((snap['selected'], snap['live'],
                          snap['activity_unknown']),
                         ('codex', True, False))




class SyntheticThirdProviderTests(unittest.TestCase):
    """Slice A: deterministic N-provider selection with a TEST-ONLY
    third ID. 'synthetic' is never registered at runtime; it proves
    the engine is not inherently two-provider limited."""

    THIRD = 'synthetic'
    IDS = ('codex', 'opencode', 'synthetic')

    def _sel(self):
        return ProviderSelection(provider_ids=self.IDS)

    def _third(self, **kw):
        return status(self.THIRD, **kw)

    def test_sole_third_worker_wins(self):
        sel = self._sel()
        snap = sel.update(
            {'codex': status('codex', activity_at=NOW - 100),
             'opencode': status('opencode', activity_at=NOW - 90),
             self.THIRD: self._third(working=True, activity_at=NOW - 5)},
            now=NOW)
        self.assertEqual((snap['selected'], snap['live'], snap['reason']),
                         (self.THIRD, True, 'working'))

    def test_three_working_newest_activity_wins(self):
        sel = self._sel()
        snap = sel.update(
            {'codex': status('codex', working=True, activity_at=NOW - 50),
             'opencode': status('opencode', working=True,
                                activity_at=NOW - 30),
             self.THIRD: self._third(working=True, activity_at=NOW - 5)},
            now=NOW)
        self.assertEqual(snap['selected'], self.THIRD)
        self.assertTrue(snap['live'])
        sel = self._sel()
        snap = sel.update(
            {'codex': status('codex', working=True, activity_at=NOW - 5),
             'opencode': status('opencode', working=True,
                                activity_at=NOW - 30),
             self.THIRD: self._third(working=True, activity_at=NOW - 50)},
            now=NOW)
        self.assertEqual(snap['selected'], 'codex')

    def test_equal_timestamps_are_deterministic(self):
        sel = self._sel()
        snap = sel.update(
            {pid: status(pid, working=True, activity_at=NOW - 10)
             for pid in self.IDS}, now=NOW)
        first = snap['selected']
        for _ in range(3):
            again = self._sel().update(
                {pid: status(pid, working=True, activity_at=NOW - 10)
                 for pid in self.IDS}, now=NOW)
            self.assertEqual(again['selected'], first)
        self.assertTrue(snap['tie_broken'])

    def test_all_unknown_recency_is_deterministic(self):
        seen = set()
        for _ in range(3):
            snap = self._sel().update(
                {pid: status(pid) for pid in self.IDS}, now=NOW)
            seen.add(snap['selected'])
            self.assertFalse(snap['live'])
        self.assertEqual(seen, {'codex'})

    def test_current_eligible_provider_retained_on_tie(self):
        sel = self._sel()
        sel.update({'codex': status('codex', activity_at=NOW - 100),
                    'opencode': status('opencode', working=True,
                                       activity_at=NOW - 50),
                    self.THIRD: status(self.THIRD, activity_at=NOW - 60)},
                   now=NOW)
        self.assertEqual(sel.snapshot()['selected'], 'opencode')
        snap = sel.update(
            {pid: status(pid, working=True, activity_at=NOW - 10)
             for pid in self.IDS}, now=NOW + 2)
        self.assertEqual(snap['selected'], 'opencode')
        self.assertTrue(snap['tie_broken'])

    def test_default_selector_drops_synthetic_id(self):
        sel = ProviderSelection()
        snap = sel.update(
            {'codex': status('codex', activity_at=NOW - 100),
             'opencode': status('opencode', activity_at=NOW - 90),
             self.THIRD: self._third(working=True, activity_at=NOW - 5)},
            now=NOW)
        # The synthetic worker is inadmissible at runtime: it can
        # neither be selected nor go live, even while "working".
        self.assertNotEqual(snap['selected'], self.THIRD)
        self.assertFalse(snap['live'])
        self.assertNotIn(self.THIRD, sel._last_inputs)


class TrackingPreferenceTests(unittest.TestCase):
    def test_unknown_persisted_preference_falls_back_to_auto(self):
        self.assertEqual(normalize_tracking_provider('synthetic'), 'auto')
        self.assertEqual(normalize_tracking_provider(''), 'auto')
        self.assertEqual(normalize_tracking_provider(None), 'auto')

    def test_manual_codex_back_to_auto_resumes_ranking(self):
        sel = ProviderSelection(('codex', 'opencode'))
        sel.mark_used('codex', now=NOW - 20)
        manual = sel.update(
            {'codex': status('codex', activity_at=NOW - 100),
             'opencode': status('opencode', working=True,
                                activity_at=NOW - 5)},
            preference='codex', now=NOW)
        self.assertEqual((manual['selected'], manual['live'],
                          manual['reason']), ('codex', False, 'manual'))
        pending = sel.update(
            {'codex': status('codex', activity_at=NOW - 100),
             'opencode': status('opencode', working=True,
                                activity_at=NOW - 5)},
            preference='auto', now=NOW + 0.5)
        self.assertEqual(pending['pending_switch'], 'opencode')
        auto = sel.update(
            {'codex': status('codex', activity_at=NOW - 100),
             'opencode': status('opencode', working=True,
                                activity_at=NOW - 5)},
            preference='auto', now=NOW + 2)
        self.assertEqual((auto['selected'], auto['live']),
                         ('opencode', True))


if __name__ == '__main__':
    unittest.main()
