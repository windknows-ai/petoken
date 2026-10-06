"""Petoken 2.0 test build with adjustable data / 2.0 可调数据测试版.

Everything runs on synthetic data in a temporary folder: no Claude Code or
Codex data is read, no real terminal is opened, and nothing is saved to your
real settings or workbench. Two control windows drive the same pet:

- the 1.x window (tools/preview_v1_3.py): tasks and the star ring, the hub,
  usage cards, task details, notifications and approval requests;
- the 2.0 window (this file): poses, interactions and moods, focus mode at
  higher speed, project notes and the where-I-left-off card, usage goals
  with any numbers, todos waiting for review, points and stickers.

Run: petoken.exe --preview-v2-0 [--language zh_CN]
"""
import argparse
from contextlib import ExitStack
from datetime import datetime, timedelta
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox,
                               QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QSpinBox,
                               QVBoxLayout, QWidget)

import pet_assets
from companion import STICKERS
from widget import Panel


class VirtualClock:
    """Wall time that can run faster, for focus sessions and goals."""

    def __init__(self):
        self.real = time.time()
        self.virtual = self.real
        self.speed = 1.0
        self.days = 0

    def __call__(self):
        now = time.time()
        self.virtual += (now - self.real) * self.speed
        self.real = now
        return self.virtual + self.days * 86400

    def set_speed(self, speed):
        self()
        self.speed = speed


def button(text, callback):
    widget = QPushButton(text)
    widget.clicked.connect(callback)
    return widget


def row(*widgets):
    box = QWidget()
    line = QHBoxLayout(box)
    line.setContentsMargins(0, 0, 0, 0)
    for widget in widgets:
        line.addWidget(widget)
    line.addStretch(1)
    return box


class Preview(QWidget):
    def __init__(self, language='zh_CN', base=None):
        """``base``: the 1.x synthetic preview whose panel and pet are shared."""
        super().__init__()
        self.base = base
        self.clock = VirtualClock()
        self.folder = tempfile.TemporaryDirectory(prefix='petoken-v2-preview-')
        root = Path(self.folder.name)
        from pet import DesktopPet
        from workbench_store import WorkbenchStore
        if base is not None:
            self.panel, self.pet = base.panel, base.pet
            # The 1.x window pins a pose; its "idle" means "let her act".
            original = base.set_pose

            def set_pose(*_):
                original()
                if base.pose.currentText() == 'idle':
                    self.pet.preview_state = None
                    self.pet.update_activity()
            base.pose.currentTextChanged.disconnect()
            base.pose.currentTextChanged.connect(set_pose)
            set_pose()
            self.pet.activity_timer.start(100)
        else:
            self.panel = Panel(live=False)
            self.panel.pet = self.pet = DesktopPet(self.panel)
        self.panel.preview_toasts = True
        self.panel.prefs.update(language=language)
        self.store = WorkbenchStore(root / 'workbench.sqlite3')
        self.panel.workbench_store = lambda: self.store
        self.panel.focus_mode.clock = self.clock
        self.panel.companion.clock = self.clock
        # A scheduler on the preview store that never opens a terminal.
        self.panel.todo_ai._store = self.store
        self.panel.todo_ai.enabled = True
        self.panel.todo_ai.launcher = lambda argv: self.panel.tray_notice('（测试版）已模拟启动 AI', '不会真的打开终端')
        self.panel.report_cache.data = dict(events=[], history=[], missing=[], activity=dict(turns=[], edits=[]))
        self.panel.report_cache.at = time.time()
        self.panel.report_cache.max_age = 10 ** 9      # Synthetic data never goes stale.
        self.projects = []
        for name in ('petoken', 'website'):
            directory = root / name
            directory.mkdir()
            project = self.store.create_project(name, str(directory))
            self.projects.append(project)
            for title in (f'{name}：修登录按钮', f'{name}：写测试'):
                self.store.create_todo(title, project['id'])
        (root / 'petoken' / 'HANDOFF.md').write_text('# 交接\n- 下一步：做用量目标的界面\n- 注意：先跑测试\n',
                                                    encoding='utf-8')
        self.idle_minutes = 0
        self._demo = None
        self.hour = None
        self.mood_on = False
        self._build()
        self.ensure_workbench()     # Before anything opens the panel's own (empty) workbench.
        self.pet.show()
        self.move(20, 20)

    # Layout ---------------------------------------------------------------
    def _build(self):
        self.setWindowTitle('Petoken 2.0 测试版 · 陪伴功能 / companionship')
        outer = QVBoxLayout(self)
        banner = QLabel('只用合成数据：不读 Claude Code / Codex，不开终端，不保存你的设置和工作台。\n'
                        'Synthetic data only: nothing real is read, opened or saved.')
        banner.setWordWrap(True)
        outer.addWidget(banner)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        layout = QVBoxLayout(body)
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)
        self.resize(460, 860)

        def group(title):
            box = QGroupBox(title)
            form = QFormLayout(box)
            layout.addWidget(box)
            return form

        # Poses and interactions.
        form = group('动作和互动 / Poses')
        self.pose = QComboBox()
        self.pose.addItem('（自动 / auto）', None)
        for state in pet_assets.registered_states() + pet_assets.companion_states():
            own = '★ ' if pet_assets.has_own_art(state) and state in pet_assets.companion_states() else ''
            self.pose.addItem(own + state, state)
        self.pose.currentIndexChanged.connect(self.set_pose)
        form.addRow('固定动作（★ = 已有新图）', self.pose)
        motion = QCheckBox('动画 / motion')
        motion.setChecked(self.pet.motion)
        motion.toggled.connect(self.pet.toggle_motion)
        form.addRow(motion)
        form.addRow(row(button('摸头', lambda: self.pet.interact('headpat_happy', 2)),
                        button('戳一下', lambda: (self.pet.animator.poke(.6), self.pet.interact('poked', .5))),
                        button('连戳→鼓脸', lambda: self.pet.interact('pout', 2.4)),
                        button('长按→撒娇', lambda: (self.pet.animator.hop(90), self.pet.interact('coquettish', 3.5)))))
        form.addRow(row(button('拎起来', self.drag_start), button('松手落地', self.drag_end),
                        button('通知：完成', lambda: self.notify('finished')),
                        button('通知：要审批', lambda: self.notify('needs_approval'))))

        # Mood.
        form = group('心情 / Mood')
        why = QLabel('真实使用时，心情动作只在没有 AI 任务、你也没在打字时出现（任务状态优先）。'
                     '下面的「演示」按钮直接显示动作；勾选「模拟心情」会暂时把 1.x 窗口的任务数设为 0，'
                     '再按你设的时刻和离开时间让心情自己变化。')
        why.setWordWrap(True)
        form.addRow(why)
        enable = QCheckBox('模拟心情（按下面的时刻和离开时间）')
        enable.toggled.connect(self.set_mood)
        form.addRow(enable)
        self.clinginess = QComboBox()
        for key, label in (('quiet', '安静'), ('moderate', '适中'), ('clingy', '黏人')):
            self.clinginess.addItem(label, key)
        self.clinginess.setCurrentIndex(1)
        self.clinginess.currentIndexChanged.connect(
            lambda _: self.pet.mood.set_clinginess(self.clinginess.currentData()))
        form.addRow('粘人程度', self.clinginess)
        self.clinginess_note = QLabel()
        self.clinginess_note.setWordWrap(True)
        form.addRow(self.clinginess_note)
        self.clinginess.currentIndexChanged.connect(lambda _: self._describe())
        self._describe()
        hour = QSpinBox()
        hour.setRange(-1, 23)
        hour.setSpecialValueText('现在')
        hour.setValue(-1)
        hour.valueChanged.connect(lambda value: setattr(self, 'hour', None if value < 0 else value))
        form.addRow('模拟时刻（点）', hour)
        idle = QSpinBox()
        idle.setRange(0, 600)
        idle.setSuffix(' 分钟')
        idle.valueChanged.connect(lambda value: setattr(self, 'idle_minutes', value))
        form.addRow('模拟你离开电脑多久', idle)
        form.addRow(QLabel('演示（直接显示这个动作几秒）：'))
        form.addRow(row(button('早安', lambda: self.mood_pose('greet_morning')),
                        button('打哈欠', lambda: self.mood_pose('yawn')),
                        button('发呆', lambda: self.mood_pose('bored')),
                        button('偷看你', lambda: self.mood_pose('peek'))))
        form.addRow(row(button('睡着', lambda: self.mood_pose('sleep', 60)),
                        button('醒来', lambda: self.mood_pose('wake_stretch')),
                        button('欢迎回来', lambda: self.mood_pose('hug'))))

        # Focus.
        form = group('专注 / Focus')
        speed = QComboBox()
        for label, value in (('1×（真实速度）', 1), ('10×', 10), ('60×（1 分钟 = 1 秒）', 60), ('300×', 300)):
            speed.addItem(label, value)
        speed.currentIndexChanged.connect(lambda _: self.clock.set_speed(speed.currentData()))
        form.addRow('时间倍速', speed)
        form.addRow(row(button('开始专注（选待办、休息）…', self.panel.open_focus_dialog),
                        button('25 分钟', lambda: self.panel.start_focus(25))))
        form.addRow(row(button('立刻到时间', self.focus_now), button('提前结束', self.panel.focus_mode.stop),
                        button('跳过休息', self.panel.focus_mode.skip_break)))

        # Projects and notes.
        form = group('项目、开工和「上次做到哪」 / Projects')
        self.project = QComboBox()
        for project in self.projects:
            self.project.addItem(project['name'], project['id'])
        form.addRow('项目', self.project)
        self.last_task = QLineEdit('给登录页加上表单校验')
        form.addRow('上次 AI 做的任务', self.last_task)
        self.last_ago = QSpinBox()
        self.last_ago.setRange(0, 720)
        self.last_ago.setValue(5)
        self.last_ago.setSuffix(' 小时前')
        form.addRow('', self.last_ago)
        self.note = QLineEdit('提交按钮还没接上，下次先做它')
        form.addRow(row(self.note, button('留言', self.add_note)))
        form.addRow(row(button('显示「上次做到哪」', self.show_card),
                        button('模拟回到这个项目', self.come_back),
                        button('打开项目页', lambda: self.open_tab(3))))

        # Goals.
        form = group('用量目标（数字随便填） / Usage goals')
        self.goal_project = QComboBox()
        for project in self.projects:
            self.goal_project.addItem(project['name'], project['id'])
        form.addRow('项目', self.goal_project)
        self.goal_amount = QDoubleSpinBox()
        self.goal_amount.setRange(0, 999_999)
        self.goal_amount.setDecimals(2)
        self.goal_amount.setValue(5)
        self.goal_unit = self._units()
        form.addRow('每周目标', row(self.goal_amount, self.goal_unit))
        self.used_amount = QDoubleSpinBox()
        self.used_amount.setRange(0, 999_999)
        self.used_amount.setDecimals(2)
        self.used_amount.setValue(4.2)
        self.used_unit = self._units()
        form.addRow('本周已用', row(self.used_amount, self.used_unit))
        self.used_usd = QDoubleSpinBox()
        self.used_usd.setRange(0, 1_000_000)
        self.used_usd.setPrefix('$ ')
        form.addRow('本周花费（API 价格）', self.used_usd)
        form.addRow(row(button('设目标并检查', self.apply_goal), button('只检查', self.check_goals),
                        button('跳到下周', self.next_week)))

        # Review and points.
        form = group('待办验收、点数和贴纸 / Review, points, stickers')
        form.addRow(row(button('造一个「等你验收」的待办', self.make_review),
                        button('打开待办', lambda: self.open_tab(1))))
        self.sticker = QComboBox()
        for sticker in STICKERS:
            self.sticker.addItem(sticker, sticker)
        form.addRow(row(button('+10 点数', lambda: self.panel.companion.award('focus_done', f'preview-{time.time()}')),
                        self.sticker, button('获得贴纸', self.earn)))
        form.addRow(row(button('打开收藏', lambda: self.open_tab(6)), button('打开报告', self.panel.open_reports)))
        language = QComboBox()
        language.addItems(('zh_CN', 'en'))
        language.setCurrentText(self.panel.prefs.get('language'))
        language.currentTextChanged.connect(self.set_language)
        layout.addWidget(row(QLabel('语言 / Language'), language, button('退出 / Exit', self.close)))

    def _units(self):
        unit = QComboBox()
        unit.addItem('百万 tokens', 1_000_000)
        unit.addItem('十亿 tokens', 1_000_000_000)
        return unit

    # Actions --------------------------------------------------------------
    def set_pose(self):
        self.pet.preview_state = self.pose.currentData()
        self.pet.update_activity()

    def drag_start(self):
        self.pet.dragging = True
        self.pet.animator.start_drag((.5, .25))
        self.pet.interact('dragged', 1)
        swings = [0]

        def swing():
            if not self.pet.dragging or swings[0] > 40:
                return
            swings[0] += 1
            self.pet.animator.drag(900 if swings[0] % 20 < 10 else -900)
            QTimer.singleShot(50, swing)
        swing()

    def drag_end(self):
        if self.pet.dragging:
            self.pet.dragging = False
            self.pet.animator.end_drag()
            self.pet.interact('landing', .7)

    def notify(self, kind):
        self.panel.notifications.ingest(dict(kind=kind, provider='claude', task_key=f'preview:{time.time()}',
                                             at=time.time(), project='petoken', detail='',
                                             dedupe=f'preview:{kind}:{time.time()}'))

    def set_mood(self, enabled):
        import pet as pet_module
        self.mood_on = enabled
        self.pet.mood_enabled = enabled
        self.pet._mood_next = 0
        if self.base is not None:
            # Mood is the lowest layer: tasks would cover it.
            if enabled:
                self._tasks_before = self.base.count.value()
                self.base.count.setValue(0)
            else:
                self.base.count.setValue(getattr(self, '_tasks_before', 3))
        preview = self

        class Clock(datetime):
            @classmethod
            def now(cls, tz=None):
                now = datetime.now()
                return now.replace(hour=preview.hour) if preview.hour is not None else now
        pet_module.datetime = Clock
        pet_module.input_idle_seconds = lambda: preview.idle_minutes * 60
        if not enabled:
            self.pet.mood.pose = None

    def _describe(self):
        from localization import text
        self.clinginess_note.setText(text(f'clinginess_desc_{self.clinginess.currentData()}',
                                          self.panel.prefs.get('language')))

    def mood_pose(self, pose, seconds=4):
        """Show a mood pose for a few seconds, above the synthetic tasks."""
        token = object()
        self._demo = token
        self.pet.preview_state = pose
        self.pet.update_activity()

        def restore():
            if self._demo is token:
                self.pet.preview_state = None
                self.pet.update_activity()
        QTimer.singleShot(int(seconds * 1000), restore)

    def focus_now(self):
        mode = self.panel.focus_mode
        if mode.phase != 'idle':
            self.clock.virtual += max(0, mode.ends - self.clock()) + 1
            mode.tick()

    def _project(self, combo):
        return next(p for p in self.projects if p['id'] == combo.currentData())

    def add_note(self):
        if self.note.text().strip():
            self.store.add_handoff(self.project.currentData(), self.note.text().strip())

    def _history(self):
        project = self._project(self.project)
        at = time.time() - self.last_ago.value() * 3600
        self.panel.report_cache.data['history'] = [
            dict(provider='claude', id='preview', title=self.last_task.text(), project=project['name'],
                 started_at=at - 600, finished_at=at, tokens=0, usd=None)]

    def show_card(self):
        self._history()
        if not self.panel.show_continuation(self._project(self.project), self.store):
            self.panel.tray_notice('这个项目没有可显示的内容', '先留一句话或者填上次的任务')

    def come_back(self):
        self._history()
        project = self._project(self.project)
        seen = dict(self.panel.prefs.get('project_seen') or {})
        seen[project['id']] = time.time() - 5 * 3600
        self.panel.prefs['project_seen'] = seen
        watcher = self.panel.continuation
        watcher.known = set()
        found = watcher.observe([dict(provider_id='claude', task_key=f'preview-{time.time()}',
                                      display=dict(project=project['name']))])
        if found is not None:
            self.panel.show_continuation(found, self.store)

    def apply_goal(self):
        project = self.goal_project.currentData()
        self.store.set_goal(project, weekly_tokens=round(self.goal_amount.value() * self.goal_unit.currentData()) or None)
        self.check_goals()

    def check_goals(self):
        project = self._project(self.goal_project)
        now = self.clock()
        events = [e for e in self.panel.report_cache.data['events'] if e.get('project') != project['name']]
        events.append(dict(provider='claude', session='preview', at=now - 60, project=project['name'],
                           tokens=round(self.used_amount.value() * self.used_unit.currentData()),
                           usd=self.used_usd.value() or None))
        self.panel.report_cache.data['events'] = events
        alerts = self.panel.companion.check_goals(events, now)
        if not alerts:
            self.panel.tray_notice('（测试版）没有新的目标提醒', '每档提醒每周只出一次；可以先「跳到下周」')
        window = self.panel.workbench_window
        if window is not None:
            window.refresh()

    def next_week(self):
        # Last week's usage stays as it was; the new week starts empty.
        self.clock.days += 7
        project = self._project(self.goal_project)
        alerts = self.panel.companion.check_goals(self.panel.report_cache.data['events'], self.clock())
        self.used_amount.setValue(0)
        self.used_usd.setValue(0)
        if not alerts:
            self.panel.tray_notice('（测试版）进入下一周', f'{project["name"]} 上周超出了目标，所以没有表扬')

    def make_review(self):
        project = self.projects[0]
        todo = self.store.create_todo(f'给设置页加深色模式 #{int(time.time()) % 1000}', project['id'])
        self.store.schedule_todo(todo['id'], time.time(), 'claude', project['directory'], '给设置页加深色模式')
        self.store.update_schedule(todo['id'], state='started', started_at=time.time(), task_key='claude:preview')
        from notifications import recap_detail
        with patch('todo_ai.TodoScheduler._outcome', return_value=None):
            self.panel.todo_ai.on_event(dict(kind='finished', provider='claude', task_key='claude:preview',
                                             detail=recap_detail(dict(files=['src/theme.css', 'src/settings.py'],
                                                                      duration_s=420, usd=.35))))
        self.open_tab(1)

    def earn(self):
        self.panel.companion.earn(self.sticker.currentData())
        window = self.panel.workbench_window
        if window is not None:
            window.collection_page.refresh()

    def open_tab(self, index):
        self.ensure_workbench()
        window = self.panel.workbench_window
        window.tabs.setCurrentIndex(index)
        window.refresh()
        window.show()
        window.raise_()

    def ensure_workbench(self):
        if self.panel.workbench_window is None:
            from workbench import WorkbenchWindow
            self.panel.workbench_window = WorkbenchWindow(self.panel, self.store)

    def set_language(self, language):
        self.panel.prefs['language'] = language
        self.panel.apply_language() if hasattr(self.panel, 'apply_language') else None
        self.pet.apply_language()

    def closeEvent(self, event):
        self.panel.focus_mode.abandon()
        if self.base is not None:
            self.base.close()
        self.panel.tray.hide()
        self.pet.close()
        QApplication.instance().quit()
        super().closeEvent(event)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--language', choices=('en', 'zh_CN'), default='zh_CN')
    args = parser.parse_args(argv)
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    with ExitStack() as stack:
        directory = stack.enter_context(tempfile.TemporaryDirectory(prefix='petoken-v2-qa-'))
        stack.enter_context(patch('widget.PREF_DIR', Path(directory)))
        # No real terminal is ever opened from the test build.
        stack.enter_context(patch('quick_launch.build_command', lambda *a, **k: ['preview']))
        from tools.preview_v1_3 import Preview as BasePreview
        base = BasePreview(3, args.language)
        base.panel.preview_toasts = True
        base.setWindowTitle('Petoken 测试版 · 任务、星环、用量卡片、审批、通知 / tasks, star ring, cards')
        app.aboutToQuit.connect(base.cleanup)
        preview = Preview(args.language, base)
        stack.enter_context(patch('claude_launch.launch', lambda argv: preview.panel.tray_notice(
            '（测试版）已模拟打开终端', '真实版本会在这里打开 Claude Code 或 Codex')))
        base.show()
        preview.show()

        def place():
            # Side by side once both windows have their real frames.
            screen = QApplication.primaryScreen().availableGeometry()
            base.move(screen.left() + 20, screen.top() + 20)
            preview.move(base.frameGeometry().right() + 12, screen.top() + 20)
        QTimer.singleShot(200, place)
        return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
