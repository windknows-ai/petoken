"""Synthetic V1.3 visual QA; no provider reads or saved user preferences.

Run: python tools/preview_v1_3.py --count 3 --language en
Bounded native capture: add --smoke 2 --output /absolute/path/preview.png
"""
import argparse
from contextlib import ExitStack
import json
import math
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFormLayout,
                              QLabel, QPushButton, QSpinBox, QWidget)

from pet import DesktopPet
from providers import active_task
from widget import Panel

FIXTURE_CASES = ('known', 'zero', 'unknown', 'partial', 'same_project', 'long_labels')
ANCHORS = ('center', 'left', 'right', 'top', 'bottom',
           'top-left', 'top-right', 'bottom-left', 'bottom-right')


def fixture_tasks(count=3, case='known'):
    """Build explicitly synthetic, distinct Codex task-local projections."""
    tasks = []
    for index in range(count):
        unknown, zero = case == 'unknown', case == 'zero'
        values = ([None] * 6 if unknown else [0] * 6 if zero else
                  [value * (index + 1) for value in (120000, 18000, 7000, 90000, 0, 138000)])
        names = ('input_tokens', 'output_tokens', 'reasoning_output_tokens',
                 'cached_input_tokens', 'cache_write_input_tokens', 'total_tokens')
        tokens = dict(zip(names, values))
        if case == 'partial':
            tokens['cache_write_input_tokens'] = None
        project = ('Synthetic QA shared project' if case == 'same_project'
                   else f'Synthetic QA project {index + 1}')
        model = None if unknown else 'synthetic-qa-model'
        if case == 'long_labels':
            project += ' — Long project label / 较长项目名称' * 8
            model += '-long-model-label' * 12
        tasks.append(active_task('codex', f'synthetic-qa-{index + 1}',
            activity_at=time.time(), display=dict(project=project),
            presentation=dict(tokens=tokens, model=model,
                effort=None if unknown else 'high', context=None,
                cost_amount=0.0 if zero else None,
                available=not unknown, source_available=True,
                partial=case == 'partial', notes=())))
    return tasks


class Preview(QWidget):
    def __init__(self, count=3, language='en', case='known', anchor='center'):
        super().__init__()
        self.closed = False
        self.generation = 0
        self.panel = Panel(live=False)
        self.panel.prefs.update(language=language, panel_pinned=True, tracking_provider='codex')
        self.panel.pet = self.pet = DesktopPet(self.panel)
        self.pet.activity_timer.stop()
        # Arm only the existing presentation timer; Panel remains live=False.
        self.panel.task_manager._live_armed = lambda: True
        screen = QApplication.primaryScreen().availableGeometry()
        self.setWindowTitle('SYNTHETIC QA / 合成预览 — Petoken V1.3')
        layout = QFormLayout(self)
        banner = QLabel('Synthetic fixtures only / 仅合成数据\nNo provider reads; temporary settings / 不读取提供方；设置不保存')
        banner.setWordWrap(True)
        layout.addRow(banner)
        self.count = QSpinBox()
        self.count.setRange(0, 8)
        self.count.setValue(count)
        layout.addRow('Tasks / 任务数量', self.count)
        layout.addRow('Source / 来源', QLabel('Codex — SYNTHETIC / 合成数据'))
        self.case = self.combo(FIXTURE_CASES, case)
        layout.addRow('Usage fixture / 用量样例', self.case)
        self.language = self.combo(('en', 'zh_CN'), language)
        layout.addRow('Language / 语言', self.language)
        self.anchor = self.combo(ANCHORS, anchor)
        layout.addRow('Pet position / 桌宠位置', self.anchor)
        self.pose = self.combo(('idle', 'typing', 'working'), 'idle')
        layout.addRow('Pet fixture / 桌宠状态', self.pose)
        self.motion = QCheckBox('Motion / 动画')
        self.motion.setChecked(True)
        self.motion.toggled.connect(self.pet.toggle_motion)
        layout.addRow(self.motion)
        self.visible = QCheckBox('Show Hub and Stars / 显示 Hub 和 Star')
        self.visible.setChecked(True)
        self.visible.toggled.connect(self.set_scene_visible)
        layout.addRow(self.visible)
        self.source = QCheckBox('Source available / 来源可用')
        self.source.setChecked(True)
        self.source.toggled.connect(self.refresh)
        layout.addRow(self.source)
        self.topmost = QCheckBox('Always on top / 始终置顶')
        self.topmost.setChecked(True)
        self.topmost.toggled.connect(self.panel.set_always_on_top)
        layout.addRow(self.topmost)
        add = QPushButton('Add task / 添加任务')
        add.clicked.connect(lambda: self.count.setValue(self.count.value() + 1))
        retire = QPushButton('Retire task / 移除任务')
        retire.clicked.connect(lambda: self.count.setValue(self.count.value() - 1))
        layout.addRow(add, retire)
        self.detail_task = QSpinBox()
        self.detail_task.setRange(1, 8)
        layout.addRow('Detail task number / 详情任务编号', self.detail_task)
        self.detail_button = QPushButton('Open / collapse task detail / 打开或收起任务详情')
        self.detail_button.clicked.connect(self.toggle_detail)
        layout.addRow(self.detail_button)
        self.detail_status = QLabel('')
        self.detail_status.setWordWrap(True)
        layout.addRow(self.detail_status)
        quit_button = QPushButton('Exit preview / 退出预览')
        quit_button.clicked.connect(self.close)
        layout.addRow(quit_button)
        for control in (self.count, self.case, self.language):
            signal = control.valueChanged if isinstance(control, QSpinBox) else control.currentTextChanged
            signal.connect(self.refresh)
        self.pose.currentTextChanged.connect(self.set_pose)
        self.anchor.currentTextChanged.connect(self.move_anchor)
        self.move(screen.left() + 20, screen.top() + 20)
        self.move_anchor()
        self.pet.show()
        self.panel.show()
        self.refresh()
        self.set_pose()

    @staticmethod
    def combo(values, current):
        combo = QComboBox()
        combo.addItems(values)
        combo.setCurrentText(current)
        return combo

    def refresh(self, *_):
        if self.closed:
            return
        self.generation += 1
        self.panel.prefs.update(language=self.language.currentText(),
                                tracking_provider='codex')
        self.panel.apply_language()
        tasks = fixture_tasks(self.count.value(), self.case.currentText())
        if not self.source.isChecked():
            tasks = []
        self.panel.render(dict(provider_id='codex', generation=self.generation,
            preference='codex', active_tasks=tasks,
            scope='global', available=False, tokens={}, partial=False,
            selection=dict(selected='codex', source_available=self.source.isChecked(), live=bool(tasks),
                           stale=False, activity_unknown=not self.source.isChecked()),
            codex_activity=dict(active=bool(tasks), valid=self.source.isChecked())))
        # Explicit fixture marking remains visible on the real Hub surface.
        self.panel.title.setFullText('Synthetic QA overview / 合成预览总览')
        self.panel.connection.setText('SYNTHETIC QA — no provider connection / 无提供方连接')
        self.panel.task_manager.set_visible(self.visible.isChecked())

    def move_anchor(self, *_):
        screen = (self.pet.screen() or QApplication.primaryScreen()).availableGeometry()
        anchor = self.anchor.currentText()
        x = (screen.left() if 'left' in anchor else
             screen.right() - self.pet.width() + 1 if 'right' in anchor else
             screen.center().x() - self.pet.width() // 2)
        y = (screen.top() if 'top' in anchor else
             screen.bottom() - self.pet.height() + 1 if 'bottom' in anchor else
             screen.center().y() - self.pet.height() // 2)
        self.pet.move_clamped(QPoint(x, y))

    def set_pose(self, *_):
        self.pet.preview_state = self.pose.currentText()
        self.pet.current_state = self.pet.preview_state
        self.pet.update()

    def toggle_detail(self):
        manager = self.panel.task_manager
        number = self.detail_task.value()
        key = next((identity for identity in manager.window_identities()
                    if manager._labels.get(identity) == number
                    and manager.window_for(identity).isVisible()), None)
        if key is None:
            self.detail_status.setText('Select a visible task number / 请选择可见任务的编号')
            return
        manager.orb_activated(key)
        self.detail_status.clear()

    def set_scene_visible(self, visible):
        self.panel.setVisible(visible)
        self.panel.task_manager.set_visible(visible)

    def capture(self, output):
        """Compose own Qt windows only; never capture desktop contents."""
        QApplication.processEvents()
        manager = self.panel.task_manager
        stars = [manager.window_for(key) for key in manager.window_identities()]
        detail = getattr(manager, 'detail_window', None)
        windows = [window for window in (*manager.capture_windows(), self.panel, self)
                   if window.isVisible()]
        bounds = windows[0].geometry()
        for window in windows[1:]:
            bounds = bounds.united(window.geometry())
        dpr = self.devicePixelRatioF()
        canvas = QPixmap(round(bounds.width() * dpr), round(bounds.height() * dpr))
        canvas.setDevicePixelRatio(dpr)
        canvas.fill(Qt.transparent)
        painter = QPainter(canvas)
        for window in windows:
            painter.drawPixmap(window.pos() - bounds.topLeft(), window.grab())
        painter.end()
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        if not canvas.save(str(output)):
            raise OSError(f'Could not save preview: {output}')
        output.with_suffix('.json').write_text(json.dumps(dict(
            kind='SYNTHETIC_QA', language=self.panel.language,
            fixture=self.case.currentText(), provider='codex',
            anchor=self.anchor.currentText(),
            live_provider_polling=bool(self.panel.live),
            task_count=manager.window_count(),
            visible_star_count=sum(window.isVisible() for window in stars),
            expanded_task_number=manager._labels.get(manager.expanded_identity),
            detail_visible=bool(detail and detail.isVisible()),
            motion=bool(self.panel.prefs.get('pet_motion')),
            pose=self.pet.preview_state, source_available=self.source.isChecked(),
        ), ensure_ascii=False, indent=2), encoding='utf-8')

    def cleanup(self):
        if self.closed:
            return
        self.closed = True
        self.panel.clock.stop()
        self.panel.size_timer.stop()
        self.pet.activity_timer.stop()
        self.pet.timer.stop()
        if not self.panel.closing:
            self.panel.shutdown()
        self.panel.task_manager.shutdown()

    def closeEvent(self, event):
        self.cleanup()
        event.accept()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--count', type=int, choices=range(9), default=3)
    parser.add_argument('--language', choices=('en', 'zh_CN'), default='en')
    parser.add_argument('--provider', choices=('codex',), default='codex')
    parser.add_argument('--anchor', choices=ANCHORS, default='center')
    parser.add_argument('--case', choices=FIXTURE_CASES, default='known')
    parser.add_argument('--expand', type=int, choices=range(1, 9), metavar='TASK_NUMBER')
    parser.add_argument('--motion', choices=('on', 'off'), default='on')
    parser.add_argument('--pose', choices=('idle', 'typing', 'working'), default='idle')
    parser.add_argument('--smoke', type=float, metavar='SECONDS')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    if args.smoke is not None and (not math.isfinite(args.smoke)
                                  or not 0 < args.smoke <= 2147483647 / 1000):
        parser.error('--smoke must be finite, positive, and fit the Qt timer range')
    if args.output and args.smoke is None:
        parser.error('--output requires --smoke SECONDS')
    if args.expand is not None and args.expand > args.count:
        parser.error('--expand must name a task within --count')
    app = QApplication.instance() or QApplication([])
    with ExitStack() as stack:
        directory = stack.enter_context(tempfile.TemporaryDirectory(prefix='petoken-synthetic-qa-'))
        stack.enter_context(patch('widget.PREF_DIR', Path(directory)))
        preview = Preview(args.count, args.language, args.case, args.anchor)
        preview.motion.setChecked(args.motion == 'on')
        preview.pose.setCurrentText(args.pose)
        if args.expand is not None:
            preview.detail_task.setValue(args.expand)
            QTimer.singleShot(0, preview.toggle_detail)
        stack.callback(preview.cleanup)
        app.aboutToQuit.connect(preview.cleanup)
        preview.show()
        failed = []
        if args.smoke is not None:
            def finish():
                try:
                    if args.output:
                        preview.capture(args.output)
                except Exception as error:
                    failed.append(str(error))
                finally:
                    preview.close()
            QTimer.singleShot(round(args.smoke * 1000), finish)
        result = app.exec()
    if failed:
        print(failed[0], file=sys.stderr)
        return 1
    return result


if __name__ == '__main__':
    raise SystemExit(main())
