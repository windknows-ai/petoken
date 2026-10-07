"""Find text that does not fit in any Petoken window, in Chinese and English.

Usage:
    python tools/check_text_fit.py [--language zh_CN|en|both]

Opens every window, card, menu and dialog of the test build (sandboxed,
sample data) the same way the tutorial video does, plus the modal editors,
the onboarding pages, the update dialog and every approval card kind. For
each visible label, button, checkbox, combo box and tab it checks that the
text fits the widget and the widget fits inside its parent. Prints one line
per problem and exits 1 when there are any.
"""
import argparse
import sys
import time
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QRect, Qt
from PySide6.QtWidgets import (QAbstractButton, QAbstractScrollArea, QApplication, QComboBox, QDialog, QLabel,
                               QMenu, QMessageBox, QTabBar, QWidget)

import tools.tutorial_video as tv

SLACK = 1          # Pixels of rounding allowed.


def _snippet(text):
    text = ' '.join(str(text).split())
    return text if len(text) <= 40 else text[:38] + '…'


def _scrolled(widget, top):
    """Inside a scroll area: being cut off at the edge there is fine."""
    parent = widget.parentWidget()
    while parent is not None and parent is not top:
        if isinstance(parent.parentWidget(), QAbstractScrollArea) and parent is parent.parentWidget().viewport():
            return True
        parent = parent.parentWidget()
    return False


def problems(top, where):
    """Text cut off inside ``top`` (a shown window)."""
    found = []
    widgets = [top] + top.findChildren(QWidget)
    for w in widgets:
        if w is not top and not w.isVisibleTo(top):
            continue
        if w.width() <= 0 or w.height() <= 0:
            continue
        issue = None
        if isinstance(w, QLabel):
            text = w.text()
            if not text.strip() or (w.pixmap() is not None and not w.pixmap().isNull()):
                continue
            if w.wordWrap():
                need = w.heightForWidth(w.width())
                if need > w.height() + SLACK:
                    issue = f'label needs {need}px high, has {w.height()}'
            else:
                hint = w.minimumSizeHint()
                if hint.width() > w.width() + SLACK:
                    issue = f'label needs {hint.width()}px wide, has {w.width()}'
                elif hint.height() > w.height() + SLACK:
                    issue = f'label needs {hint.height()}px high, has {w.height()}'
        elif isinstance(w, QAbstractButton):
            text = w.text()
            if not text.strip():
                continue
            hint = w.sizeHint()
            if hint.width() > w.width() + SLACK:
                issue = f'button needs {hint.width()}px wide, has {w.width()}'
            elif hint.height() > w.height() + 4:
                issue = f'button needs {hint.height()}px high, has {w.height()}'
        elif isinstance(w, QComboBox):
            text = w.currentText()
            if not text.strip():
                continue
            if w.minimumSizeHint().width() > w.width() + SLACK and w.sizeAdjustPolicy() != QComboBox.AdjustToMinimumContentsLengthWithIcon:
                pass        # Combos usually shrink their minimum; measure the shown text instead.
            room = w.width() - 34          # Arrow and padding.
            if w.fontMetrics().horizontalAdvance(text) > room + SLACK:
                issue = f'combo text needs {w.fontMetrics().horizontalAdvance(text)}px, has {room}'
        elif isinstance(w, QTabBar):
            for index in range(w.count()):
                text = w.tabText(index)
                if w.tabRect(index).width() + SLACK < w.fontMetrics().horizontalAdvance(text) + 12:
                    issue = f'tab "{_snippet(text)}" is too narrow'
                    break
            else:
                continue
            text = ''
        else:
            continue
        if issue is None and w is not top and not _scrolled(w, top):
            parent = w.parentWidget()
            if parent is not None and not parent.rect().contains(w.geometry().adjusted(SLACK, SLACK, -SLACK, -SLACK)):
                visible = w.geometry().intersected(parent.rect())
                if visible.width() < w.width() - 2 or visible.height() < w.height() - 2:
                    issue = f'cut off by its parent ({w.geometry().width()}x{w.geometry().height()} in ' \
                            f'{parent.width()}x{parent.height()})'
        if issue:
            name = w.objectName() or type(w).__name__
            found.append(f'{where}: {name} "{_snippet(text)}": {issue}')
    return found


class Checker:
    def __init__(self):
        self.found = []
        self.seen = 0

    def check(self, widget, where):
        for _ in range(3):              # Let paints and the layout passes they cause settle.
            widget.repaint()
            tv.pump(.05)
        widget.ensurePolished()
        layout = widget.layout()
        if layout is not None:
            layout.activate()
        self.seen += 1
        self.found += problems(widget, where)

    def shown(self, widget, where):
        """Show ``widget`` off screen if needed, check it, put it back."""
        hidden = not widget.isVisible()
        if hidden:
            widget.setAttribute(Qt.WA_DontShowOnScreen)
            widget.show()
            tv.pump(.15)
        self.check(widget, where)
        if hidden:
            widget.hide()
            widget.setAttribute(Qt.WA_DontShowOnScreen, False)


def run(language):
    checker = Checker()
    original_grab = tv.grab
    names = iter(range(10 ** 6))

    def checking_grab(widget):
        checker.shown(widget, f'{type(widget).__name__}#{next(names)}')
        return original_grab(widget)

    def fake_exec(dialog, *args):
        checker.shown(dialog, type(dialog).__name__ + ' ' + (dialog.windowTitle() or ''))
        return QDialog.Rejected

    with ExitStack() as stack:
        pv, base = tv.setup(stack, language)
        stack.enter_context(patch.object(tv, 'grab', checking_grab))
        stack.enter_context(patch.object(QDialog, 'exec', fake_exec))
        stack.enter_context(patch.object(QMessageBox, 'question', lambda *a, **k: QMessageBox.No))
        stack.enter_context(patch.object(QMessageBox, 'warning', lambda *a, **k: QMessageBox.Ok))
        panel = pv.panel
        # Everything the video shows, at the sizes windows open with.
        tv.capture_all(pv, base, size=None)
        window = panel.workbench_window
        window.show()
        tv.pump(.3)
        # Each workbench tab at its default size, and every "More" menu.
        for index in range(window.tabs.count()):
            window.tabs.setCurrentIndex(index)
            window.refresh()
            tv.pump(.2)
            checker.check(window, f'Workbench tab {index}')
        for button in window.findChildren(QAbstractButton):
            menu = button.menu() if hasattr(button, 'menu') else None
            if menu is not None:
                checker.shown(menu, f'menu {button.text()}')
        # The editors that open as modal dialogs.
        window.tabs.setCurrentIndex(1)
        window.refresh()
        window.todo_list.setCurrentRow(0)
        for name in ('add_todo', 'edit_todo', 'add_reminder', 'new_note', 'edit_project', 'edit_preset',
                     'edit_goal', 'edit_selected_project'):
            method = getattr(window, name, None)
            if method is None:
                continue
            try:
                if name in ('edit_preset', 'edit_goal', 'edit_selected_project'):
                    window.tabs.setCurrentIndex(3)
                    window.refresh()
                    table = window.projects_table
                    table.setCurrentItem(table.topLevelItem(0))
                method()
            except Exception as error:                      # Report, don't stop.
                checker.found.append(f'{name}: could not open ({error!r})')
        # Tutorial steps.
        tutorial = getattr(window, 'tutorial', None)
        if tutorial is not None:
            from workbench import TUTORIAL_STEPS
            for step in range(TUTORIAL_STEPS):
                tutorial.set_step(step)
                checker.shown(tutorial, f'Workbench tutorial step {step + 1}')
        window.hide()
        # Right-click menu and its submenus.
        menu = base.pet.context_menu()
        for action in menu.actions():
            if action.menu() is not None:
                checker.shown(action.menu(), f'pet menu > {action.text()}')
        menu.deleteLater()
        # Every approval card kind.
        import json
        import claude_approval
        from tools.preview_v1_3 import PREVIEW_REQUESTS
        controller = base.panel.approvals
        folder = Path(base._approval_dir.name)
        for kind in PREVIEW_REQUESTS:
            for leftover in folder.glob('*.request.json'):
                leftover.unlink()
            controller.tick()
            data = dict(session_id='check', cwd=r'C:\work\website', hook_event_name='PermissionRequest',
                        **PREVIEW_REQUESTS[kind])
            (folder / f'{claude_approval.new_request_id()}.request.json').write_text(json.dumps(data),
                                                                                    encoding='utf-8')
            controller.tick()
            tv.pump(.3)
            if controller.card is not None:
                checker.shown(controller.card, f'approval card {kind}')
        for leftover in folder.glob('*.request.json'):
            leftover.unlink()
        controller.tick()
        from approval_card import ApprovalRulesDialog
        checker.shown(ApprovalRulesDialog(None, language), 'ApprovalRulesDialog')
        # Onboarding pages.
        from onboarding import OnboardingWizard
        wizard = OnboardingWizard(panel, claude=True, codex=True)
        for index in range(wizard.stack.count()):
            wizard.stack.setCurrentIndex(index)
            checker.shown(wizard, f'Onboarding page {index + 1}')
        # Update dialog.
        from types import SimpleNamespace
        from update_ui import UpdateDialog
        dialog = UpdateDialog(SimpleNamespace(panel=panel), dict(version='9.9.9', notes='- One\n- Two'))
        checker.shown(dialog, 'UpdateDialog')
        # Analytics window and settings at their own size.
        from analytics_view import AnalyticsWindow
        checker.shown(AnalyticsWindow(panel), 'AnalyticsWindow')
        from widget import Settings
        settings = Settings(panel)
        settings.show()
        for index in range(settings.tabs.count()):
            settings.tabs.setCurrentIndex(index)
            tv.pump(.2)
            checker.check(settings, f'Settings tab {index + 1}')
        settings.close()
        # The task detail that opens when a star is clicked.
        base.pet.show()
        tv.pump(2.0)
        manager = base.panel.task_manager
        base.count.setValue(3)            # The video's last shot had no tasks.
        base.refresh()
        tv.pump(2.0)
        if not getattr(manager, '_windows', {}):
            checker.found.append('star detail: no stars to open (check skipped)')
        for key in list(getattr(manager, '_windows', {})):
            try:
                manager.orb_activated(key)
                tv.pump(.3)
                if manager.detail_window is not None and manager.detail_window.isVisible():
                    checker.check(manager.detail_window, f'star detail {key[0]}')
                manager.collapse_detail()
            except Exception as error:
                checker.found.append(f'star detail {key}: could not open ({error!r})')
        # The countdown under her, during focus and during a break.
        base.panel.start_focus(25, dict(id='x', title='一个名字很长很长的待办：把设置页做成深色模式并且记住选择',
                                        project_id=None))
        tv.pump(.8)
        if base.pet.focus_tag is not None:
            checker.check(base.pet.focus_tag, 'Focus countdown')
        base.panel.focus_mode.abandon()
        base.pet.hide()
        tv.finish(pv, base)
    return checker


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--language', choices=('zh_CN', 'en', 'both'), default='both')
    args = parser.parse_args(argv)
    QApplication.instance() or QApplication([])
    languages = ('zh_CN', 'en') if args.language == 'both' else (args.language,)
    total = 0
    for language in languages:
        checker = run(language)
        print(f'[{language}] {checker.seen} windows checked, {len(checker.found)} problems', flush=True)
        for line in dict.fromkeys(checker.found):
            print('  ' + line, flush=True)
        total += len(checker.found)
    return 1 if total else 0


if __name__ == '__main__':
    raise SystemExit(main())
