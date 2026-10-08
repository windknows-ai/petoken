import unittest

from forecast import (Assistant, CONTEXT_FULL_USED, QuotaPace, RECENT_SPAN_S, STUCK_AFTER_S,
                      WARN_WITHIN_S)

NOW = 1_800_000_000.0


def limits(five_used=None, five_reset=None, week_used=None, week_reset=None):
    data = {}
    if five_used is not None:
        data['primary'] = dict(windowDurationMins=300, usedPercent=five_used, resetsAt=five_reset)
    if week_used is not None:
        data['secondary'] = dict(windowDurationMins=10080, usedPercent=week_used, resetsAt=week_reset)
    return data


def task(key, tokens=1, context=10, provider='claude', **extra):
    return dict(provider_id=provider, task_key=key, display=dict(project='site'),
                presentation=dict(tokens=dict(total=tokens), context=context), **extra)


class PaceTests(unittest.TestCase):
    def test_window_average_before_recent_samples(self):
        pace = QuotaPace()
        # Window opened 2 h ago (reset in 3 h) and 60 % is used: 30 %/h,
        # so the 40 % left lasts 80 minutes, before the reset.
        pace.observe('claude', limits(60, NOW + 3 * 3600), NOW)
        status = pace.short('claude', 300, NOW)
        self.assertAlmostEqual(status['run_out_in'], 80 * 60, delta=1)
        self.assertAlmostEqual(status['reset_in'], 3 * 3600)

    def test_recent_pace_wins_and_a_pause_is_not_running_out(self):
        pace = QuotaPace()
        reset = NOW + 3 * 3600
        pace.observe('claude', limits(60, reset), NOW)
        pace.observe('claude', limits(60, reset), NOW + RECENT_SPAN_S)
        self.assertIsNone(pace.status('claude', 300, NOW + RECENT_SPAN_S)['run_out_in'])
        pace.observe('claude', limits(70, reset), NOW + 2 * RECENT_SPAN_S)
        # 10 % in 20 minutes: the remaining 30 % lasts an hour.
        status = pace.status('claude', 300, NOW + 2 * RECENT_SPAN_S)
        self.assertAlmostEqual(status['run_out_in'], 3600, delta=1)

    def test_lasting_until_reset_is_not_short(self):
        pace = QuotaPace()
        pace.observe('codex', limits(10, NOW + 3600), NOW)
        self.assertIsNone(pace.short('codex', 300, NOW))

    def test_new_window_restarts_samples(self):
        pace = QuotaPace()
        pace.observe('codex', limits(90, NOW + 600), NOW)
        pace.observe('codex', limits(2, NOW + 600 + 5 * 3600), NOW + 700)
        self.assertEqual(len(pace._samples[('codex', 300)]), 1)

    def test_unknown_windows_have_no_status(self):
        pace = QuotaPace()
        pace.observe('claude', None, NOW)
        self.assertIsNone(pace.status('claude', 300, NOW))


class AssistantTaskTests(unittest.TestCase):
    def test_stuck_once_per_stall(self):
        assistant = Assistant()
        assistant.observe_tasks([task('a')], NOW)
        self.assertEqual(assistant.observe_tasks([task('a')], NOW + STUCK_AFTER_S - 1), [])
        events = assistant.observe_tasks([task('a')], NOW + STUCK_AFTER_S)
        self.assertEqual([e['kind'] for e in events], ['stuck'])
        self.assertEqual(events[0]['detail'], '20')
        self.assertEqual(assistant.observe_tasks([task('a')], NOW + STUCK_AFTER_S + 60), [])
        # Progress, then another long stall: a new notice.
        assistant.observe_tasks([task('a', tokens=2)], NOW + STUCK_AFTER_S + 120)
        events = assistant.observe_tasks([task('a', tokens=2)], NOW + 2 * STUCK_AFTER_S + 120)
        self.assertEqual([e['kind'] for e in events], ['stuck'])

    def test_waiting_for_approval_is_not_stuck(self):
        assistant = Assistant()
        assistant.observe_tasks([task('a', provider='codex', awaiting_approval=True)], NOW)
        self.assertEqual(assistant.observe_tasks(
            [task('a', provider='codex', awaiting_approval=True)], NOW + STUCK_AFTER_S), [])
        assistant.observe_tasks([task('b')], NOW)
        assistant.note_event(dict(kind='needs_approval', provider='claude', task_key='b'))
        self.assertEqual(assistant.observe_tasks([task('b')], NOW + STUCK_AFTER_S), [])
        self.assertIsNone(assistant.hint('claude', 'b', 10, {}, NOW + STUCK_AFTER_S))

    def test_context_full_once_until_compacted(self):
        assistant = Assistant()
        events = assistant.observe_tasks([task('a', context=CONTEXT_FULL_USED + 2)], NOW)
        self.assertEqual([(e['kind'], e['detail']) for e in events], [('context_full', '8')])
        self.assertEqual(assistant.observe_tasks([task('a', context=95)], NOW + 5), [])
        assistant.observe_tasks([task('a', context=20)], NOW + 10)     # /compact
        events = assistant.observe_tasks([task('a', context=93)], NOW + 20)
        self.assertEqual([e['kind'] for e in events], ['context_full'])


class AssistantQuotaTests(unittest.TestCase):
    def test_forecast_with_switch_suggestion(self):
        assistant = Assistant()
        quotas = {'claude': limits(70, NOW + 3 * 3600), 'codex': limits(10, NOW + 4 * 3600, 20, NOW + 86400)}
        events = assistant.observe_quota(quotas, NOW)
        self.assertEqual([e['kind'] for e in events], ['forecast'])
        seconds, _, other = events[0]['detail'].partition('|')
        self.assertAlmostEqual(float(seconds), 30 / 35 * 3600, delta=1)
        self.assertLess(float(seconds), WARN_WITHIN_S)
        self.assertEqual((events[0]['provider'], other), ('claude', 'codex'))
        self.assertEqual(assistant.hint('claude', None, 10, quotas, NOW)[0], 'hint_run_out_switch')

    def test_no_forecast_far_from_running_out(self):
        assistant = Assistant()
        self.assertEqual(assistant.observe_quota({'claude': limits(10, NOW + 3 * 3600)}, NOW), [])
        self.assertIsNone(assistant.hint('claude', None, 10, {}, NOW))

    def test_used_up_window_comes_back(self):
        assistant = Assistant()
        reset = NOW + 600
        assistant.observe_quota({'codex': limits(100, reset)}, NOW)
        self.assertEqual(assistant.hint('codex', None, 10, {'codex': limits(100, reset)}, NOW),
                         ('hint_out', {}))
        self.assertEqual(assistant.observe_quota({'codex': limits(100, reset)}, NOW + 300), [])
        events = assistant.observe_quota({'codex': limits(0, reset + 5 * 3600)}, reset + 1)
        self.assertEqual([e['kind'] for e in events], ['quota_back'])

    def test_rate_limit_error_counts_down_to_reset(self):
        assistant = Assistant()
        reset = NOW + 900
        assistant.expect_reset('claude', limits(97, reset, 40, NOW + 86400), NOW)
        self.assertEqual(assistant.observe_quota({}, reset - 1), [])
        self.assertEqual([e['kind'] for e in assistant.observe_quota({}, reset)], ['quota_back'])

    def test_context_hint_and_weekly_hint(self):
        assistant = Assistant()
        # A nearly full context is a notification now, not a line on the account-wide card.
        self.assertIsNone(assistant.hint('claude', 'a', 94, {}, NOW))
        # Four days into the week, 80 % used: out in a day, three days before reset.
        assistant.observe_quota({'codex': limits(week_used=80, week_reset=NOW + 3 * 86400)}, NOW)
        key, values = assistant.hint('codex', None, 10, {}, NOW)
        self.assertEqual(key, 'hint_week_run_out')
        self.assertAlmostEqual(values['time'], 86400, delta=1)


class OverlayHintTests(unittest.TestCase):
    def test_section_hint_text(self):
        from usage_overlay import section_hint
        assistant = Assistant()
        quotas = {'claude': limits(60, NOW + 3 * 3600), 'codex': limits(10, NOW + 4 * 3600)}
        assistant.observe_quota(quotas, NOW)
        self.assertEqual(section_hint(assistant, 'claude', None, 10, quotas, 'en', NOW),
                         'Out in ~1h 20m · switch to Codex?')
        self.assertIsNone(section_hint(assistant, 'codex', None, 91, quotas, 'zh_CN', NOW))  # Context: not on the card.
        self.assertIsNone(section_hint(None, 'codex', None, 91, quotas, 'en', NOW))


if __name__ == '__main__':
    unittest.main()
