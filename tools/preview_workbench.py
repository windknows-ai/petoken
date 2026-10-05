"""Isolated native V1.4 workbench QA; temporary records and synthetic tasks."""
import argparse
from contextlib import ExitStack
import json
import math
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QLabel
from tools.preview_v1_3 import Preview


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--count', type=int, choices=range(65), default=3)
    parser.add_argument('--language', choices=('en', 'zh_CN'), default='zh_CN')
    parser.add_argument('--tab', choices=('home', 'todos', 'notes', 'projects'), default='home')
    parser.add_argument('--width', type=int, default=980)
    parser.add_argument('--height', type=int, default=700)
    parser.add_argument('--empty', action='store_true', help='No sample projects, todos or notes')
    parser.add_argument('--tutorial', action='store_true', help='Show/capture the native first-use tutorial')
    parser.add_argument('--tutorial-step', type=int, choices=range(5), default=0)
    parser.add_argument('--smoke', type=float, metavar='SECONDS')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    if not 680 <= args.width <= 4096 or not 460 <= args.height <= 2160:
        parser.error('Window size must be 680..4096 by 460..2160')
    if args.smoke is not None and (not math.isfinite(args.smoke) or not 0 < args.smoke <= 2147483647 / 1000):
        parser.error('--smoke must be finite, positive and fit the Qt timer range')
    if args.output and args.smoke is None:
        parser.error('--output requires --smoke SECONDS')
    return args


def seed(window):
    """Only used by this disposable preview, never by the real workbench."""
    store = window.store
    first = store.create_project('QA · Petoken / 桌宠')
    second = store.create_project('QA · Study / 学习')
    store.create_project('QA · Personal / 个人')
    for title, project, done in [
        ('QA · 看看工作台首页 / Review the home', first['id'], False),
        ('QA · 整理下一阶段想法 / Plan next steps', first['id'], False),
        ('QA · 保存一张便签 / Save a note', second['id'], False),
        ('QA · 完成的事项 / Finished item', first['id'], True),
        ('QA · 随手记录 / Capture a thought', None, False),
    ]:
        store.create_todo(title, project, done)
    store.create_note('QA · 下一步 / Next steps',
        '这些都是临时合成数据。关闭预览后会删除。\n\n'
        '✧ 项目空间：把相关的待办和便签放在一起。\n'
        '✧ 便签：Ctrl+S 保存，切换或关闭前会保护未保存的编辑。\n'
        '✧ 任务：选择 Codex 或 Claude Code 任务可打开已验证的任务详情。\n\n'
        'Temporary synthetic records; removed when this preview closes.\n', first['id'])
    store.create_note('QA · 学习笔记 / Study notes', 'A small idea, ready to grow.\n给想法留一点空间。', second['id'])
    store.create_note('QA · 灵感 / Ideas', 'This note is unassigned. / 这张便签没有关联项目。')
    identities = window.panel.task_manager.task_identities()
    for key in identities[:2]:
        store.link_task(*key, first['id'])
    window.refresh()


def main(argv=None):
    args = parse_args(argv)
    app = QApplication.instance() or QApplication([])
    with ExitStack() as stack:
        directory = Path(stack.enter_context(tempfile.TemporaryDirectory(prefix='petoken-workbench-preview-')))
        stack.enter_context(patch('widget.PREF_DIR', directory))
        preview = Preview(args.count, args.language)
        # Bounded ordinary captures retain their previous content; tutorial
        # captures and interactive previews exercise a fresh first visit.
        preview.panel.prefs['workbench_tutorial_seen'] = args.smoke is not None and not args.tutorial
        preview.setWindowTitle('SYNTHETIC QA / 合成预览 — V1.4 Workbench')
        stack.callback(preview.cleanup)
        preview.panel.open_workbench()
        window = preview.panel.workbench_window
        if not args.empty:
            seed(window)
        window.setWindowTitle('Petoken V1.4 · Workbench PREVIEW / 工作台预览')
        banner = QLabel('SYNTHETIC QA · 临时样例，不保存个人数据 / Temporary sample records only')
        banner.setWordWrap(True)
        banner.setObjectName('muted')
        window.layout().insertWidget(1, banner)
        window.tabs.setCurrentIndex(('home', 'todos', 'notes', 'projects').index(args.tab))
        screen = app.primaryScreen().availableGeometry()
        window.resize(min(args.width, screen.width()), min(args.height, screen.height()))
        window.move(screen.center().x() - window.width() // 2,
                    screen.center().y() - window.height() // 2)
        preview.visible.setChecked(False)
        preview.anchor.setCurrentText('bottom-right')
        preview.move(screen.topLeft())
        app.aboutToQuit.connect(preview.cleanup)
        preview.show()
        window.show()
        window.raise_()
        if args.tutorial:
            window.open_tutorial()
            window.tutorial.set_step(args.tutorial_step)
        failed = []
        if args.smoke is not None:
            def finish():
                try:
                    if args.output:
                        args.output.parent.mkdir(parents=True, exist_ok=True)
                        target = window.tutorial if args.tutorial else window
                        if not target.grab().save(str(args.output)):
                            raise OSError('Could not save workbench capture')
                        manager = preview.panel.task_manager
                        report = dict(kind='SYNTHETIC_WORKBENCH_QA', language=args.language,
                            tab=args.tab, live_provider_polling=preview.panel.live,
                            temporary_records=window.store.path.parent == Path(preview.panel._workbench_temp.name),
                            projects=len(window.store.list_projects()), todos=len(window.store.list_todos()),
                            notes=len(window.store.list_notes()), tasks=manager.total_task_count(),
                            visible_task_rows=window.task_list.count(), ring_enabled=preview.ring.isChecked(),
                            star_windows=manager.window_count(), star_visible=sum(
                                manager.window_for(key).isVisible() for key in manager.window_identities()),
                            width=window.width(), height=window.height(), provider='codex',
                            tutorial_visible=window.tutorial.isVisible(), tutorial_step=window.tutorial.step,
                            tutorial_seen=preview.panel.prefs['workbench_tutorial_seen'],
                            opencode_adapter_imported='opencode_provider' in sys.modules)
                        args.output.with_suffix('.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
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
