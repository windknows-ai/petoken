"""Local visual QA helper. Writes only synthetic screenshots to an ignored path."""
import sys
import time
from pathlib import Path

from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).parents[1]))
from analytics import aggregate, normalize_usage
from pet import DesktopPet
from pet_assets import PREVIEW_STATES
from widget import Panel

# Render QA enumerates the asset registry; adding a future approved asset
# needs no tool change.
STATES = PREVIEW_STATES


def main(output):
    app = QApplication.instance() or QApplication([])
    panel = Panel(live=False)
    panel.pet = DesktopPet(panel)
    tokens = normalize_usage(dict(input_tokens=120000, cached_input_tokens=90000,
        cache_write_input_tokens=0, output_tokens=18000,
        reasoning_output_tokens=7000, total_tokens=138000))
    analysis = aggregate([dict(session='visual-fixture', model='gpt-6-astra',
        timestamp='2026-09-16T12:00:00Z', event_id='visual', tokens=tokens)])
    panel.render(dict(title='开发实时用量悬浮 widget', project='petoken',
        model='gpt-6-astra', effort='high', mode='follow', scope='task',
        tokens=tokens, available=True, analytics=analysis, usd=2.19,
        context=42, context_tokens=84000, context_window=200000,
        raw_total=tokens, raw_last=tokens, notes=[], unknown=[], partial=False,
        count=1, session_names={'visual-fixture':'Visual fixture'}))
    output.mkdir(parents=True, exist_ok=True)
    panel.pet.activity_timer.stop()
    panel.pet.motion = False
    panel.pet.show()
    for state in STATES:
        panel.pet.preview_state = state
        panel.pet.update_activity()
        app.processEvents()
        panel.pet.grab().save(str(output / f'pet-{state}.png'))
    # Guitar has no independent activity trigger yet; render the registered
    # pose directly so the asset is still visually verified.
    panel.pet.preview_state = 'guitar'
    panel.pet.update_activity()
    app.processEvents()
    panel.pet.grab().save(str(output / 'pet-guitar.png'))
    # Typing tap phases via synthetic timestamp-only pulses (no key content).
    # With no V1.1 frame files present these are fallback-state renders.
    from types import SimpleNamespace
    from activity import ActivityState
    panel.activity = SimpleNamespace(state=ActivityState(), close=lambda: None,
                                       status={'microphone': None, 'music': True,
                                               'music_text': None})
    # Frame-accurate typing renders need motion on: the frame branch only
    # runs when motion is enabled (motion pause shows the static pose).
    panel.pet.motion = True
    panel.pet.preview_state = 'typing'
    panel.pet.update_activity()
    app.processEvents()
    panel.pet.grab().save(str(output / 'pet-typing.png'))
    base = time.monotonic()
    panel.activity.state.key(base)
    panel.pet.update_activity()
    app.processEvents()
    panel.pet.grab().save(str(output / 'pet-typing-tap1.png'))
    panel.activity.state.key(base + 0.2)
    panel.pet.update_activity()
    app.processEvents()
    panel.pet.grab().save(str(output / 'pet-typing-tap0.png'))
    panel.pet.motion = False
    # Music subtitle pill with synthetic clearly-labeled test content.
    panel.activity.status['music_text'] = {
        'text': 'Synthetic QA subtitle line', 'source': 'qa-stub',
        'identity': ('qa-stub', 'QA track', 'QA artist')}
    panel.pet.preview_state = 'music'
    panel.pet.update_activity()
    app.processEvents()
    panel.pet.grab().save(str(output / 'pet-music-text.png'))
    panel.activity.status['music_text'] = None
    panel.pet.preview_state = None
    panel.app_mode.update(True, True)
    panel.app_mode.update(True, True, panel.app_mode.pending_since + 1.0)
    panel.pet.update_activity()
    panel.pet.update_data(dict(panel.snapshot, working_context=dict(
        project='petoken', title='Visual fixture', model='gpt-6-astra',
        effort='high', context=42, tokens=tokens)))
    app.processEvents()
    panel.pet.grab().save(str(output / 'pet-token.png'))
    panel.show()
    panel.open_analytics()
    app.processEvents()
    panel.grab().save(str(output / 'panel.png'))
    panel.analytics_window.grab().save(str(output / 'analytics.png'))
    panel.shutdown()
    return 0


if __name__ == '__main__':
    raise SystemExit(main(Path(sys.argv[1] if len(sys.argv) > 1 else '.private/states')))
