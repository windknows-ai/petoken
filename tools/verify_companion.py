"""Isolated, synthetic Qt lifecycle/visual QA; no user settings or logs changed.

Run once per configured Qt screen scale; output includes the measured DPR.
Desktop captures are cropped to the test windows and must remain private.
"""
import json
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from analytics import aggregate, normalize_usage
from pet import DesktopPet
from widget import Panel, PANEL_MIN


def main(output):
    output.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory() as temporary, patch('widget.PREF_DIR', Path(temporary)):
        panel = Panel(live=False)
        panel.pet = pet = DesktopPet(panel)
        pet.activity_timer.stop()  # Feed signals explicitly; keep the real animation timer.
        tokens = normalize_usage(dict(input_tokens=1234567890123, cached_input_tokens=900000000000,
            output_tokens=345678901234, reasoning_output_tokens=100000000000))
        analysis = aggregate([dict(session='qa', model='gpt-6-astra', event_id='qa',
            timestamp='2026-09-20T12:00:00Z', tokens=tokens)])
        data = dict(title='Companion visual QA', project='petoken', available=True,
            scope='conversation', model='gpt-6-astra', effort='high', mode='fixed',
            tokens=tokens, analytics=analysis, usd=1.23, context=42,
            context_tokens=84000, context_window=200000, scope_activity=dict(valid=True, active=False))
        panel.render(data)
        panel.receive_limits(dict(sampled=time.time(), limits={
            'primary':dict(usedPercent=35, windowDurationMins=300, resetsAt=time.time()+3600),
            'secondary':dict(usedPercent=20, windowDurationMins=10080, resetsAt=time.time()+86400)}))
        panel.restore_companion()
        screen = pet.screen()
        r = screen.availableGeometry()
        pet.move_clamped(QPoint(r.x()+60, r.bottom()-pet.height()-20))
        state = panel.activity.state
        evidence = dict(dpr=pet.devicePixelRatioF(), pet_size=[pet.width(),pet.height()],
                        transitions=[], anchors=[], captures=[])

        def capture(name, both=False):
            QTest.qWait(100)
            pet.grab().save(str(output/f'{name}-pet.png'))
            if both:
                panel.grab().save(str(output/f'{name}-panel.png'))
                bounds = panel.geometry().united(pet.geometry())
                # Native desktop capture proves these are adjacent top-level windows.
                shot = screen.grabWindow(0, bounds.x(), bounds.y(), bounds.width(), bounds.height())
                assert not shot.isNull()
                shot.save(str(output/f'{name}-desktop.png'))
                # Transparent composition allows clean alpha inspection independent of wallpaper.
                dpr = pet.devicePixelRatioF()
                canvas = QPixmap(round(bounds.width()*dpr), round(bounds.height()*dpr))
                canvas.setDevicePixelRatio(dpr)
                canvas.fill(Qt.transparent)
                painter = QPainter(canvas)
                painter.drawPixmap(pet.pos()-bounds.topLeft(), pet.grab())
                painter.drawPixmap(panel.pos()-bounds.topLeft(), panel.grab())
                painter.end()
                canvas.save(str(output/f'{name}-pair.png'))
            evidence['captures'].append(name)

        pet.update_activity()
        capture('idle')
        for number in (1, 2):
            state.key(time.monotonic())
            pet.update_activity()
            evidence['transitions'].append(pet.current_state)
            capture(f'typing-{number}')
            QTest.qWait(130)
        state.last_key = 0
        for name in ('microphone', 'music'):
            state.stable = dict(microphone=name=='microphone', music=name=='music')
            state.sampled = time.monotonic()
            pet.update_activity()
            assert pet.current_state == name
            capture(name)
        data.update(scope_activity=dict(valid=True, active=True), codex_activity=dict(valid=True, active=True))
        panel.app_mode.update(True, True, now=1)
        panel.app_mode.update(True, True, now=2)
        pet.update_data(dict(data, working_context=dict(project='petoken', title=data['title'],
            tokens=tokens, context=42)))
        panel.render(data)
        pet.update_activity()
        assert pet.current_state == 'working'
        capture('working')
        for side in ('right', 'left', 'edge'):
            x = r.x()+60 if side=='right' else r.right()-pet.width()-(0 if side=='edge' else 60)
            pet.move_clamped(QPoint(x, r.bottom()-pet.height()-20))
            before = pet.pos()
            for _ in range(5):
                pet.show_panel()
                app.processEvents()
                assert pet.pos() == before and pet.isVisible()
                assert r.contains(panel.geometry())
                assert not panel.geometry().intersects(pet.geometry())
                panel.hide()
                assert pet.pos() == before
            pet.show_panel()
            evidence['anchors'].append(dict(side=side, pet=[before.x(),before.y()],
                panel=[panel.x(),panel.y()], drift=0))
            capture(side, both=True)
        panel.toggle_pin()
        capture('pinned', both=True)
        panel.resize(*PANEL_MIN)
        for language in ('zh_CN','en'):
            panel.prefs.update(language=language, token_number_format='full')
            panel.apply_language()
            panel.render(data)
            app.processEvents()
            assert panel.body.width() <= panel.body_scroll.viewport().width()
            assert panel.total.fontMetrics().horizontalAdvance(panel.total.text()) <= panel.total.width()
            capture(f'min-full-{language}', both=True)
        (output/'evidence.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
        pet.close()
        panel.tray.hide()
        panel.closing = True
        panel.close()
        panel.deleteLater()
        app.processEvents()
    print(json.dumps(dict(dpr=evidence['dpr'], zero_drift=True, captures=len(evidence['captures']))))


if __name__ == '__main__':
    main(Path(sys.argv[1] if len(sys.argv)>1 else '.private/companion-acceptance'))
