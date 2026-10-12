"""2.5: forms drawn in Qt Quick through the widget mirror (widget_mirror.py, workbench_shell.py)."""
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QVBoxLayout)

import widget_mirror

APP = QApplication.instance() or QApplication([])


def pump(seconds):
    end = time.time() + seconds
    while time.time() < end:
        APP.processEvents()
        time.sleep(.01)


class Form(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('petoken · 测试')
        layout = QVBoxLayout(self)
        self.hint = QLabel('<b>名字</b>')
        self.name = QLineEdit()
        self.typed = []
        self.name.textEdited.connect(self.typed.append)
        self.kind = QComboBox()
        self.kind.addItems(['一', '二', '三'])
        self.flag = QCheckBox('提醒我')
        self.items = QListWidget()
        for title, checkable in (('甲', True), ('乙', False)):
            item = QListWidgetItem(title)
            if checkable:
                item.setCheckState(Qt.Unchecked)
            self.items.addItem(item)
        self.go = QPushButton('出发')
        self.go.setObjectName('primary')
        self.clicked = 0
        self.go.clicked.connect(lambda: setattr(self, 'clicked', self.clicked + 1))
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(self.go)
        for widget in (self.hint, self.name, self.kind, self.flag, self.items):
            layout.addWidget(widget)
        layout.addLayout(row)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)


class MirrorTests(unittest.TestCase):
    def test_tree_values_and_actions_reach_the_real_widgets(self):
        form = Form()
        form.setAttribute(Qt.WA_DontShowOnScreen)
        form.show()
        mirror = widget_mirror.Mirror(form, widget_mirror.images())
        self.addCleanup(form.deleteLater)
        self.assertEqual(mirror.tree['t'], 'container')
        ident = lambda widget: widget.property('_mirrorId')
        values = mirror.values
        self.assertTrue(values[ident(form.hint)]['rich'])
        self.assertEqual(values[ident(form.kind)]['items'], ['一', '二', '三'])
        rows = values[ident(form.items)]['rows']
        self.assertEqual([r['check'] for r in rows], [True, False])   # Only a row with a check state.
        mirror.setText(ident(form.name), '星星')
        self.assertEqual(form.name.text(), '星星')
        self.assertEqual(form.typed, ['星星'])                         # The same signal typing sends.
        mirror.setIndex(ident(form.kind), 2)
        self.assertEqual(form.kind.currentIndex(), 2)
        mirror.click(ident(form.flag))
        self.assertTrue(form.flag.isChecked())
        mirror.listCheck(ident(form.items), 0, True)
        self.assertEqual(form.items.item(0).checkState(), Qt.Checked)
        mirror.listSelect(ident(form.items), 1)
        self.assertEqual(form.items.currentRow(), 1)
        mirror.click(ident(form.go))
        self.assertEqual(form.clicked, 1)
        mirror.poll()
        self.assertEqual(mirror.values[ident(form.name)]['text'], '星星')
        form.go.hide()
        mirror.poll()
        self.assertFalse(mirror.values[ident(form.go)]['v'])            # Hidden widgets are hidden there too.

    def test_every_dialog_opens_in_its_mirror_window_and_answers(self):
        widget_mirror.install(APP)
        self.addCleanup(widget_mirror.uninstall, APP)
        patcher = patch.object(widget_mirror, 'LANGUAGE', 'zh_CN')
        patcher.start()
        self.addCleanup(patcher.stop)
        form = Form()
        form.show()
        pump(1.2)
        self.assertTrue(form.testAttribute(Qt.WA_DontShowOnScreen))     # The plain window never shows.
        window = form._mirror_window
        self.assertTrue(window.isVisible())
        self.assertEqual(window.errors, [])
        self.assertEqual(window.bridge.title, '测试')                     # Without the app's name.
        window.bridge.close()                                            # The window's x is Cancel.
        self.assertEqual(form.result(), QDialog.Rejected)
        pump(.3)
        self.assertFalse(window.isVisible())
        box = QMessageBox(QMessageBox.Question, '工作台', '删除吗？', QMessageBox.Yes | QMessageBox.No)
        box.show()
        pump(1.0)
        mirror = box._mirror_window.mirror
        texts = [v.get('text') for v in mirror.values.values()]
        self.assertIn('是', texts)                                        # Qt's buttons in her language.
        yes = next(i for i, v in mirror.values.items() if v.get('text') == '是')
        mirror.click(yes)
        self.assertEqual(box.standardButton(box.clickedButton()), QMessageBox.Yes)
        form.deleteLater()
        box.deleteLater()


class WorkbenchShellTests(unittest.TestCase):
    def test_workbench_in_its_qt_quick_window(self):
        widget_mirror.install(APP)
        self.addCleanup(widget_mirror.uninstall, APP)
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        with patch('widget.PREF_DIR', Path(temp.name)):
            import widget
            panel = widget.Panel(live=False)
            self.addCleanup(lambda: (panel.tray.hide(), setattr(panel, 'closing', True), panel.close()))
            panel.prefs['workbench_tutorial_seen'] = True
            panel.open_workbench()
            pump(1.5)
            wb = panel.workbench_window
            shell = wb.shell
            self.assertIsNotNone(shell)
            self.assertEqual(shell.errors, [])
            self.assertTrue(shell.isVisible())
            self.assertTrue(wb.testAttribute(Qt.WA_DontShowOnScreen))
            wb.add_todo('写周报')
            pump(.4)
            self.assertIn('1', shell.bridge.summaryText)
            self.assertEqual(len(shell.bridge.nav), 8)
            shell.mirror.setIndex(shell.bridge.ids['tabs'], 1)            # The rail picks the page.
            self.assertEqual(wb.tabs.currentIndex(), 1)
            todo_list = wb.todo_list.property('_mirrorId')
            shell.mirror.poll()
            self.assertEqual(shell.mirror.values[todo_list]['rows'][0]['text'], '写周报')
            shell.close()                                                 # Closing it closes the workbench.
            pump(.3)
            self.assertFalse(wb.isVisible())
            wb.shutdown()


if __name__ == '__main__':
    unittest.main()
