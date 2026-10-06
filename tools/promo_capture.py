"""Capture real Petoken UI (synthetic data) as transparent PNGs for the promo video.

Usage: python tools/promo_capture.py OUTPUT_DIR [--language en|zh_CN]
Nothing is read from Codex or Claude Code; settings live in a temporary folder.
"""
import argparse
import datetime
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('PETOKEN_CLAUDE_HOME', os.path.join(tempfile.gettempdir(), 'petoken-promo-no-claude'))

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import QApplication


PROJECTS = ('petoken', 'website', 'api-server', 'docs')


def compose(windows, path):
    """Paint the given visible windows into one transparent image."""
    windows = [w for w in windows if w is not None and w.isVisible()]
    bounds = windows[0].geometry()
    for window in windows[1:]:
        bounds = bounds.united(window.geometry())
    dpr = windows[0].devicePixelRatioF()
    canvas = QPixmap(round(bounds.width() * dpr), round(bounds.height() * dpr))
    canvas.setDevicePixelRatio(dpr)
    canvas.fill(Qt.transparent)
    painter = QPainter(canvas)
    for window in windows:
        painter.setOpacity(window.windowOpacity())
        painter.drawPixmap(window.pos() - bounds.topLeft(), window.grab())
    painter.end()
    canvas.save(str(path))


def settle(app, rounds=30):
    for _ in range(rounds):
        app.processEvents()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--language', default='en', choices=('en', 'zh_CN'))
    args = parser.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    import tools.preview_v1_3 as preview_tool
    synthetic = preview_tool.fixture_tasks

    def promo_tasks(count=3, case='known', source='mixed'):
        """Same synthetic numbers, with everyday project and model names."""
        tasks = synthetic(count, case, source)
        for index, task in enumerate(tasks):
            task['display'] = dict(project=PROJECTS[index % len(PROJECTS)])
            task['presentation'] = dict(task['presentation'], model=(
                'claude-opus-5-5' if task['provider_id'] == 'claude' else 'gpt-5-codex'))
        return tasks
    snapshot = preview_tool.Preview.hub_snapshot

    def promo_snapshot(self, prefs=None):
        data = snapshot(self, prefs)
        data['usd'], data['partial'] = 12.84, False
        return data
    with patch('widget.PREF_DIR', Path(tempfile.mkdtemp(prefix='petoken-promo-'))),             patch.object(preview_tool, 'fixture_tasks', promo_tasks),             patch.object(preview_tool.Preview, 'hub_snapshot', promo_snapshot):
        Preview = preview_tool.Preview
        preview = Preview(4, args.language, 'known', 'center', 'mixed')
        preview.panel.preview_toasts = False
        preview.hide()
        panel, pet, manager = preview.panel, preview.pet, preview.panel.task_manager
        screen = app.primaryScreen().availableGeometry()
        pet.move_clamped(QPoint(screen.center().x() - pet.width() // 2,
                                screen.center().y() - pet.height() // 2 + 60))
        panel.set_panel_pinned(False)
        panel.hide()
        settle(app)
        scene = [w for w in manager.capture_windows()
                 if w not in (manager.detail_window, manager.detail_transition.overlay)]
        compose(scene + [pet], out / 'ring.png')
        # Usage card above the character (both apps open).
        pet.sync_usage_overlay()
        settle(app)
        compose(scene + [pet, pet.usage_overlay], out / 'overlay.png')
        pet.usage_overlay.grab().save(str(out / 'overlay_card.png'))
        # Hub and a star's detail card.
        panel.set_panel_pinned(True)
        panel.connection.setText('')
        settle(app)
        panel.grab().save(str(out / 'hub.png'))
        panel.open_analytics()
        settle(app, 40)
        if panel.analytics_window is not None:
            panel.analytics_window.resize(1100, 720)
            settle(app, 20)
            panel.analytics_window.grab().save(str(out / 'analytics.png'))
            panel.analytics_window.close()
        panel.set_panel_pinned(False)
        panel.hide()
        key = manager.task_identities()[0]
        manager.activate_task(key)
        settle(app, 60)
        if manager.detail_window is not None:
            manager.detail_window.grab().save(str(out / 'detail.png'))
        manager.collapse_detail() if hasattr(manager, 'collapse_detail') else None
        # Workbench with a few records and notifications.
        import time as _time
        now = _time.time()
        for offset, (kind, provider, project, detail) in enumerate([
                ('finished', 'claude', 'website', ''), ('needs_approval', 'codex', 'api-server', ''),
                ('failed', 'claude', 'docs', 'rate_limit'), ('quota_low', 'codex', '', '18'),
                ('finished', 'codex', 'petoken', '')]):
            panel.notifications.ingest(dict(
                kind=kind, provider=provider, task_key=f'promo-{offset}', at=now - 600 * (5 - offset),
                project=project, detail=detail, dedupe=f'promo:{offset}'), now=now + offset * 1000)
        panel.open_workbench()
        window = panel.workbench_window
        store = window.store
        zh = args.language == 'zh_CN'
        project = store.create_project('Petoken')
        store.create_project('学习' if zh else 'Study')
        todos = (('看看 Codex 的结果', '规划下一个版本', '回复 issue') if zh else
                 ('Review the Codex result', 'Plan the next release', 'Reply to issues'))
        for title in todos:
            store.create_todo(title, project['id'])
        store.create_note('发布清单' if zh else 'Release checklist',
                          '跑测试、打包、发布。' if zh else 'Run the tests, build, publish.', project['id'])
        window.add_reminder('起来活动一下，喝口水' if zh else 'Stretch and drink water', 'daily',
                            datetime.datetime.now() + datetime.timedelta(hours=2))
        window.resize(1060, 720)
        window.refresh()
        settle(app)
        window.tabs.setCurrentIndex(0)
        settle(app)
        window.grab().save(str(out / 'workbench_home.png'))
        window.tabs.setCurrentIndex(window.notifications_tab)
        settle(app)
        window.grab().save(str(out / 'workbench_notifications.png'))
        window.shutdown()
        preview.cleanup()
    print('captured', sorted(p.name for p in out.glob('*.png')))


if __name__ == '__main__':
    main()
