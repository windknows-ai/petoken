"""Claude Code provider (V1.5): mapping, pricing, privacy, scopes, liveness and lanes."""
import json
import os
import tempfile
import unittest
from pathlib import Path

# Hermetic Claude lane for any default store built by imported modules.
os.environ.setdefault('PETOKEN_CLAUDE_HOME', os.path.join(
    tempfile.gettempdir(), 'petoken-tests-no-claude-home'))

from claude_usage import (ClaudeProvider, ClaudeStore, ClaudeTranscript,
                          map_usage, project_identity, read_registry,
                          scoped_session_id, strip_scope)
from pricing import claude_price_model, estimate_claude_usd
from provider_selection import claude_provider_status

SECRET = 'TOP SECRET PROMPT TEXT'


def usage(plain=10, read=1000, write=200, out=50, thinking=20, split=None,
          **extra):
    value = dict(input_tokens=plain, cache_read_input_tokens=read,
                 cache_creation_input_tokens=write, output_tokens=out,
                 output_tokens_details=dict(thinking_tokens=thinking), **extra)
    if split is not None:
        value['cache_creation'] = split
    return value


def assistant(session, message_id, cwd, stamp, model='claude-opus-5-5',
              stop='end_turn', sidechain=False, **usage_args):
    return dict(
        parentUuid=None, isSidechain=sidechain, type='assistant',
        message=dict(id=message_id, model=model, role='assistant',
                     stop_reason=stop, usage=usage(**usage_args),
                     content=[dict(type='text', text=SECRET)]),
        requestId=f'req-{message_id}', uuid=f'u-{message_id}-{stamp}',
        timestamp=stamp, cwd=cwd, sessionId=session, version='2.1.286',
        gitBranch='main', effort='high')


def user(session, cwd, stamp):
    return dict(type='user', message=dict(role='user', content=SECRET),
                timestamp=stamp, cwd=cwd, sessionId=session)


class ClaudeHome:
    """A disposable ~/.claude with transcripts and a live-session registry."""

    def __init__(self, root):
        self.root = Path(root)
        (self.root / 'projects').mkdir(parents=True, exist_ok=True)

    def transcript(self, project, session, entries, raw_tail=b''):
        folder = self.root / 'projects' / project
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f'{session}.jsonl'
        with path.open('ab') as handle:
            for entry in entries:
                handle.write(json.dumps(entry).encode('utf-8') + b'\n')
            handle.write(raw_tail)
        return path

    def registry(self, session, status='busy', pid=None, cwd='C:/work/alpha',
                 updated=1_791_000_000_000, name=None):
        folder = self.root / 'sessions'
        folder.mkdir(exist_ok=True)
        pid = os.getpid() if pid is None else pid
        data = dict(pid=pid, sessionId=session, cwd=cwd, status=status,
                    statusUpdatedAt=updated, procStart=None)
        if name:
            data['name'] = name
        (folder / f'{pid}.json').write_text(json.dumps(data), encoding='utf-8')


class MappingAndPricingTests(unittest.TestCase):
    def test_anthropic_usage_maps_to_disjoint_shared_categories(self):
        tokens = map_usage(usage(plain=10, read=1000, write=200, out=50, thinking=20))
        self.assertEqual(tokens, dict(
            input_tokens=1210, cached_input_tokens=1000,
            cache_write_input_tokens=200, output_tokens=50,
            reasoning_output_tokens=20, total_tokens=1260))

    def test_missing_fields_stay_unknown_never_zero(self):
        tokens = map_usage({'input_tokens': 5, 'output_tokens': 7})
        self.assertIsNone(tokens['input_tokens'])
        self.assertIsNone(tokens['total_tokens'])
        self.assertIsNone(tokens['reasoning_output_tokens'])
        self.assertEqual(tokens['output_tokens'], 7)

    def test_opus_5_5_rates_with_one_hour_cache_split(self):
        cost = estimate_claude_usd(usage(
            plain=1_000_000, read=1_000_000, write=1_000_000, out=1_000_000,
            split=dict(ephemeral_5m_input_tokens=500_000,
                       ephemeral_1h_input_tokens=500_000)), 'claude-opus-5-5')
        # 4 input + 0.20 read + 0.5*5 (5m) + 0.5*8 (1h) + 20 output.
        self.assertAlmostEqual(cost, 4 + .2 + 2.5 + 4 + 20)

    def test_fast_mode_and_us_inference_multipliers(self):
        base = usage(plain=1_000_000, read=0, write=0, out=0)
        self.assertAlmostEqual(estimate_claude_usd(dict(base, speed='fast'), 'claude-opus-5-5'), 8)
        self.assertAlmostEqual(estimate_claude_usd(dict(base, speed='fast'), 'claude-sonnet-5-5'), 2)
        self.assertAlmostEqual(estimate_claude_usd(dict(base, inference_geo='us'), 'claude-opus-5-5'), 4.4)
        self.assertAlmostEqual(estimate_claude_usd(dict(base, inference_geo='us'), 'claude-haiku-4-5'), 1)

    def test_unknown_models_never_borrow_prices_and_snapshots_resolve(self):
        self.assertIsNone(estimate_claude_usd(usage(), 'claude-future-9'))
        self.assertIsNone(estimate_claude_usd(usage(), None))
        self.assertEqual(claude_price_model('claude-haiku-4-5-20251001'), 'claude-haiku-4-5')
        self.assertIsNone(estimate_claude_usd({'output_tokens': 3}, 'claude-opus-5-5'))

    def test_scoped_ids_and_project_identity(self):
        self.assertEqual(strip_scope(scoped_session_id('abc')), 'abc')
        self.assertEqual(strip_scope('codex-thread'), '')
        name, source, project_id = project_identity('D:\\Work\\Petoken\\')
        self.assertEqual((name, source), ('Petoken', 'cwd_basename'))
        self.assertTrue(project_id.startswith('claude-project:'))
        self.assertEqual(project_identity(None), (None, 'unavailable', None))


class TranscriptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = ClaudeHome(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_repeated_blocks_count_once_and_content_is_never_retained(self):
        entries = [user('s1', 'C:/work/alpha', '2026-10-05T01:00:00Z'),
                   assistant('s1', 'm1', 'C:/work/alpha', '2026-10-05T01:00:01Z'),
                   assistant('s1', 'm1', 'C:/work/alpha', '2026-10-05T01:00:02Z'),
                   assistant('s1', 'm2', 'C:/work/alpha', '2026-10-05T01:00:03Z',
                             model='<synthetic>')]
        transcript = ClaudeTranscript(self.home.transcript('alpha', 's1', entries))
        transcript.refresh()
        self.assertEqual(list(transcript.records), ['m1'])
        self.assertNotIn(SECRET, repr(transcript.__dict__))

    def test_partial_line_waits_for_its_newline(self):
        complete = assistant('s1', 'm1', 'C:/work/alpha', '2026-10-05T01:00:01Z')
        tail = json.dumps(assistant('s1', 'm2', 'C:/work/alpha',
                                    '2026-10-05T01:00:02Z')).encode()[:40]
        path = self.home.transcript('alpha', 's1', [complete], raw_tail=tail)
        transcript = ClaudeTranscript(path)
        transcript.refresh()
        self.assertEqual(list(transcript.records), ['m1'])
        self.assertFalse(transcript.partial)

    def test_session_belongs_to_its_start_directory(self):
        entries = [assistant('s1', 'm1', 'C:/work/alpha', '2026-10-05T01:00:01Z'),
                   assistant('s1', 'm2', 'C:/work/elsewhere', '2026-10-05T01:00:02Z')]
        self.home.transcript('alpha', 's1', entries)
        data = ClaudeStore(self.home.root).read(scope='project')
        self.assertEqual(data['project'], 'alpha')


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = ClaudeHome(self.temp.name)
        self.home.transcript('alpha', 's1', [
            assistant('s1', 'a1', 'C:/work/alpha', '2026-10-05T01:00:00Z'),
            assistant('s1', 'a2', 'C:/work/alpha', '2026-10-05T01:05:00Z')])
        self.home.transcript('alpha', 's2', [
            assistant('s2', 'b1', 'C:/work/alpha', '2026-10-05T02:00:00Z',
                      model='claude-sonnet-5-5'),
            dict(type='custom-title', customTitle='Refactor', sessionId='s2')])
        self.home.transcript('beta', 's3', [
            assistant('s3', 'c1', 'C:/work/beta', '2026-10-05T03:00:00Z',
                      model='claude-future-9')])
        self.store = ClaudeStore(self.home.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_scopes_partition_sessions_and_projects(self):
        conversation = self.store.read(scope='conversation', pinned='claude:s1')
        project = self.store.read(scope='project', pinned='claude:s1')
        everything = self.store.read(scope='global')
        self.assertEqual(conversation['tokens']['total_tokens'], 2 * 1260)
        self.assertEqual(project['tokens']['total_tokens'], 3 * 1260)
        self.assertEqual(everything['tokens']['total_tokens'], 4 * 1260)
        self.assertEqual((conversation['mode'], conversation['thread']), ('fixed', 'claude:s1'))
        self.assertEqual(project['project'], 'alpha')
        self.assertEqual(everything['project'], 'display_all_usage')
        self.assertEqual(everything['unknown'], ['claude-future-9'])
        self.assertIsNone(everything['limits'])
        self.assertIsNone(everything['context'])

    def test_latest_session_and_titles(self):
        data = self.store.read(scope='conversation')
        self.assertEqual((data['mode'], data['thread'], data['title']),
                         ('recent', 'claude:s3', 'display_untitled'))
        titled = self.store.read(scope='conversation', pinned='claude:s2')
        self.assertEqual(titled['title'], 'Refactor')
        self.assertEqual(titled['model'], 'claude-sonnet-5-5')

    def test_foreign_pin_is_ignored_and_missing_pin_is_honest(self):
        self.assertEqual(self.store.read(pinned='codex-thread-1')['thread'], 'claude:s3')
        missing = self.store.read(pinned='claude:gone')
        self.assertEqual(missing['status'], 'status_pinned_unavailable')

    def test_no_local_data_is_a_source_failure(self):
        empty = ClaudeStore(Path(self.temp.name) / 'missing').read()
        self.assertEqual(empty['status'], 'status_claude_no_local_data')
        envelope = ClaudeProvider(ClaudeStore(Path(self.temp.name) / 'missing')).read()
        self.assertFalse(claude_provider_status(envelope, 1.0)['source_available'])

    def test_idle_without_registry_is_unknown_activity(self):
        data = self.store.read()
        self.assertEqual(data['claude_activity']['reason'], 'registry_unavailable')
        self.assertFalse(data['claude_activity']['valid'])
        self.assertEqual(data['active_tasks'], [])

    def test_busy_live_session_is_working_with_one_task(self):
        self.home.registry('s2', status='busy', name='Live name')
        data = self.store.read()
        self.assertEqual(data['claude_activity']['reason'], 'registry_busy')
        self.assertEqual(data['mode'], 'working')
        self.assertEqual(data['working_context']['title'], 'Live name')
        self.assertEqual([t['task_key'] for t in data['active_tasks']], ['claude:s2'])
        task = data['active_tasks'][0]
        self.assertEqual(task['display'], {'project': 'alpha'})
        self.assertEqual(task['presentation']['tokens']['total_tokens'], 1260)
        status = claude_provider_status(ClaudeProvider(self.store).read(), last_success_at=2.0)
        self.assertTrue(status['working'] and status['activity_valid'])
        self.assertEqual(status['activity_at'], 1_791_000_000.0)

    def test_idle_or_dead_process_never_claims_work(self):
        self.home.registry('s2', status='idle')
        self.assertFalse(self.store.read()['claude_activity']['active'])
        self.assertTrue(self.store.read()['claude_activity']['valid'])
        self.home.registry('s1', status='busy', pid=2_000_000_000)
        self.assertEqual(read_registry(self.home.root, alive=lambda pid, start: False), {})
        self.assertEqual(self.store.read()['active_tasks'], [])


class PollerLaneTests(unittest.TestCase):
    def setUp(self):
        from provider_poller import ProviderPoller
        from tests.test_provider_poller import NOW_S, PollerFixture
        self.now = NOW_S
        self.temp = tempfile.TemporaryDirectory()
        codex = PollerFixture(self.temp.name).codex([{'id': 't1'}])
        self.home = ClaudeHome(Path(self.temp.name) / 'claude')
        self.home.transcript('alpha', 's1', [
            assistant('s1', 'a1', 'C:/work/alpha', '2026-10-05T01:00:00Z')])
        self.home.registry('s1', status='busy')
        self.poller = ProviderPoller(codex, claude_store=ClaudeStore(self.home.root))

    def tearDown(self):
        self.poller.close()
        self.temp.cleanup()

    def settle(self, prefs):
        out = None
        for _ in range(3):
            out = self.poller.poll(prefs, now=self.now)
            self.assertTrue(self.poller.drain())
        return out

    def test_auto_follows_the_working_claude_session(self):
        out = self.settle({'scope': 'conversation', 'tracking_provider': 'auto'})
        self.assertEqual(out['provider_id'], 'claude')
        self.assertTrue(out['selection']['live'])
        self.assertEqual(out['result']['working_context']['provider_id'], 'claude')
        self.assertEqual([(t['provider_id'], t['task_key']) for t in out['active_tasks']],
                         [('claude', 'claude:s1')])

    def test_manual_codex_hides_claude_stars_and_hub(self):
        out = self.settle({'scope': 'global', 'tracking_provider': 'codex'})
        self.assertEqual(out['provider_id'], 'codex')
        self.assertEqual(out['active_tasks'], [])

    def test_pinned_task_routes_hub_to_its_provider_without_filtering_stars(self):
        out = self.settle({'scope': 'conversation', 'tracking_provider': 'auto',
                           'pinned': 't1'})
        self.assertEqual(out['provider_id'], 'codex')
        self.assertEqual(out['preference'], 'auto')
        self.assertEqual([t['task_key'] for t in out['active_tasks']], ['claude:s1'])
        out = self.settle({'scope': 'conversation', 'tracking_provider': 'auto',
                           'pinned': 'claude:s1'})
        self.assertEqual((out['provider_id'], out['result']['thread']), ('claude', 'claude:s1'))

    def test_claude_read_failure_isolated_from_codex_lane(self):
        from unittest.mock import patch
        self.settle({'scope': 'global', 'tracking_provider': 'auto'})
        with patch.object(ClaudeProvider, 'read', side_effect=RuntimeError('boom')):
            out = self.settle({'scope': 'global', 'tracking_provider': 'auto'})
        self.assertEqual(out['active_tasks'], [])
        self.assertFalse(self.poller._status['claude']['source_available'])
        self.assertTrue(self.poller._status['codex']['source_available'])
        self.assertEqual(out['provider_id'], 'codex')


class StarColorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def mean_color(self, provider_id):
        from widget import TaskOrbWindow
        import pet_geometry
        orb = TaskOrbWindow(('x', provider_id), provider_id=provider_id)
        image = orb.grab().toImage()
        cx, cy = pet_geometry.TASK_STAR_CENTER
        totals = [0, 0, 0]
        count = 0
        for dx in range(-6, 7):
            for dy in range(-12, 13):
                color = image.pixelColor(cx + dx, cy + dy)
                if color.alpha() > 200:
                    totals = [totals[0] + color.red(), totals[1] + color.green(),
                              totals[2] + color.blue()]
                    count += 1
        orb.close()
        self.assertGreater(count, 0)
        return [value / count for value in totals]

    def test_codex_stars_are_blue_and_claude_stars_are_gold(self):
        from widget import star_palette
        self.assertNotEqual(star_palette('codex'), star_palette('claude'))
        self.assertEqual(star_palette('unknown'), star_palette('codex'))
        red, _green, blue = self.mean_color('codex')
        self.assertGreater(blue, red)
        red, _green, blue = self.mean_color('claude')
        self.assertGreater(red, blue)




class RingTintTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_ring_takes_nearby_star_colors_and_meets_in_lavender(self):
        import math
        from halo_scene import RING_MEET, ring_tint
        from theme import star_palette
        blue, gold = star_palette('codex')['ring'], star_palette('claude')['ring']
        self.assertIsNone(ring_tint(1.0, []))
        self.assertEqual(ring_tint(2.5, [(0.0, gold)]), gold)
        self.assertEqual(ring_tint(2.5, [(0.0, blue), (math.pi, blue)]), blue)
        mixed = [(0.0, blue), (math.pi, gold)]
        self.assertEqual(ring_tint(0.0, mixed), blue)
        self.assertEqual(ring_tint(math.pi, mixed), gold)
        self.assertEqual(ring_tint(math.pi / 2, mixed), RING_MEET)
        self.assertEqual(ring_tint(3 * math.pi / 2, mixed), RING_MEET)
        self.assertEqual(ring_tint(math.tau, mixed), blue)

    def ring_color(self, tints):
        import math
        from halo_scene import HaloLayer
        from halo_geometry import HaloPose, project
        pose = HaloPose(200, 200, 120, 60, 0.0)
        layer = HaloLayer(True)
        layer.tints = tints
        layer.set_scene(pose, 0.0)
        image = layer.grab().toImage()
        x, y, _ = project(pose, math.pi / 2)
        ratio = image.devicePixelRatio()
        color = image.pixelColor(round((x - layer.x()) * ratio), round((y - layer.y()) * ratio))
        layer.close()
        return color

    def test_ornament_stars_follow_the_ring_colour(self):
        import math
        from halo_scene import HaloLayer
        from halo_geometry import HaloPose, project
        from theme import star_palette
        pose = HaloPose(200, 200, 120, 60, 0.0)
        colours = {}
        for provider in ('codex', 'claude'):
            layer = HaloLayer(True)
            layer.tints = [(math.pi / 2, star_palette(provider)['ring'])]
            layer.set_scene(pose, 0.0)
            image = layer.grab().toImage()
            ratio = image.devicePixelRatio()
            # Bead 0 sits on the inset ring at angle 0.4 * pi / 12.
            x, y, _ = project(pose._replace(rx=pose.rx - 4, ry=pose.ry - 4), math.pi * .4 / 12)
            cx, cy = (x - layer.x()) * ratio, (y - layer.y()) * ratio
            samples = [image.pixelColor(round(cx + dx), round(cy + dy))
                       for dx in range(-6, 7) for dy in range(-6, 7)]
            glow = [c for c in samples if c.alpha() > 40]
            colours[provider] = (sum(c.red() for c in glow) / len(glow), sum(c.blue() for c in glow) / len(glow))
            layer.close()
        self.assertGreater(colours['claude'][0] - colours['claude'][1],
                           colours['codex'][0] - colours['codex'][1])

    def test_front_ring_paints_its_star_color(self):
        import math
        from theme import star_palette
        gold = self.ring_color([(math.pi / 2, star_palette('claude')['ring'])])
        self.assertGreater(gold.red(), gold.blue())
        blue = self.ring_color([(math.pi / 2, star_palette('codex')['ring'])])
        self.assertGreater(blue.blue(), blue.red())


class ContextAndAnalyticsTests(unittest.TestCase):
    def test_context_uses_the_official_model_window(self):
        from claude_usage import context_percent, context_window
        self.assertEqual(context_window('claude-opus-5-5'), 1_000_000)
        self.assertEqual(context_window('claude-haiku-4-5-20251001'), 200_000)
        self.assertAlmostEqual(context_percent(831_157, 'claude-opus-5-5'), 83.1157)
        self.assertIsNone(context_percent(250_000, 'claude-haiku-4-5'))  # Beyond window: unknown.
        self.assertIsNone(context_percent(10, 'claude-future-9'))
        self.assertIsNone(context_percent(None, 'claude-opus-5-5'))

    def test_store_reports_context_of_the_latest_request(self):
        with tempfile.TemporaryDirectory() as root:
            home = ClaudeHome(root)
            home.transcript('alpha', 's1', [assistant('s1', 'm1', 'C:/a', '2026-10-05T01:00:00Z'),
                                            assistant('s1', 'm2', 'C:/a', '2026-10-05T01:01:00Z',
                                                      read=400_000)])
            data = ClaudeStore(home.root).read()
            self.assertEqual(data['context_tokens'], 400_210)
            self.assertEqual(data['context_window'], 1_000_000)
            self.assertAlmostEqual(data['context'], 40.021)


class HubProviderPresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from unittest.mock import patch
        from widget import Panel
        from pet import DesktopPet
        self.temp = tempfile.TemporaryDirectory()
        self.pref_patch = patch('widget.PREF_DIR', Path(self.temp.name))
        self.pref_patch.start()
        self.panel = Panel(live=False)
        self.panel.pet = DesktopPet(self.panel)
        self.panel.pet.activity_timer.stop()

    def tearDown(self):
        self.panel.tray.hide()
        self.panel.pet.close()
        self.panel.close()
        self.pref_patch.stop()
        self.temp.cleanup()

    def render(self, provider_id, language='en', **extra):
        self.panel.prefs.update(language=language)
        self.panel.apply_language()
        data = dict(provider_id=provider_id, title='Task', project='Project',
                    model='m', mode='follow', scope='global', available=True,
                    tokens=map_usage(usage()), usd=1.0, notes=[], unknown=[],
                    partial=False, count=1)
        data.update(extra)
        self.panel.render(data)
        self.app.processEvents()
        return self.panel.connection

    def test_codex_compatibility_notice_only_when_not_fully_supported(self):
        partial = dict(status='partial', codex_version='0.156.1',
                       reasons=['unknown_quota_structure'])
        label = self.render('codex', compatibility=partial)
        self.assertIn('Partly compatible', label.text())
        self.assertIn('0.156.1', label.toolTip())
        self.assertIn('unknown_quota_structure', label.toolTip())
        label = self.render('codex', language='zh_CN',
                            compatibility=dict(status='unsupported', reasons=[]))
        self.assertIn('格式无法识别', label.text())
        self.assertNotIn('compatible', self.render(
            'codex', compatibility=dict(status='supported', reasons=[])).text())
        # A Claude payload never carries or shows the Codex notice.
        self.assertNotIn('compatible', self.render('claude', compatibility=partial).text())

    def test_token_analytics_window_renders_claude_data(self):
        from analytics_view import AnalyticsWindow
        with tempfile.TemporaryDirectory() as root:
            home = ClaudeHome(root)
            home.transcript('alpha', 's1', [assistant('s1', 'm1', 'C:/a', '2026-10-05T01:00:00Z')])
            data = dict(ClaudeStore(home.root).read(scope='global', include_history=True),
                        provider_id='claude')
        window = AnalyticsWindow(self.panel)
        window.update_data(data)
        self.assertIn('Claude Code', window.heading.text())
        self.assertGreater(window.models.rowCount(), 0)
        self.assertIn('Claude Code JSONL', window.raw.toPlainText())
        window.close()

    def test_total_tooltip_keeps_normal_size_and_names_the_provider_rule(self):
        from PySide6.QtWidgets import QApplication, QToolTip
        self.render('claude')
        total = self.panel.total
        self.assertTrue(total.styleSheet().startswith('QLabel#number'))
        self.assertIn('Claude Code', total.toolTip())
        self.assertNotIn('OpenAI', total.toolTip())
        self.panel.show()
        QToolTip.showText(total.mapToGlobal(total.rect().center()), total.toolTip(), total)
        self.app.processEvents()
        # The tooltip label inherits the number's style sheet when one is
        # unscoped; the old 'font-size:30px;' made it 30px (verified).
        tips = [w for w in QApplication.topLevelWidgets() if w.objectName() == 'qtooltip_label']
        self.assertTrue(tips)
        self.assertLess(tips[0].fontInfo().pixelSize(), 20)
        QToolTip.hideText()
        self.render('codex')
        self.assertIn('OpenAI', self.panel.total.toolTip())

    def test_hub_model_name_is_not_collapsed_to_an_ellipsis(self):
        self.panel.show()
        self.render('claude', model='claude-opus-5-5', effort='high')
        self.app.processEvents()
        self.assertEqual(self.panel.model.text(), 'claude-opus-5-5')

    def test_claude_hub_names_provider_and_states_missing_limits(self):
        label = self.render('claude')
        self.assertTrue(label.text().startswith('Claude Code · '))
        self.assertEqual(self.panel.status.text(), 'No limits from this source')


if __name__ == '__main__':
    unittest.main()
