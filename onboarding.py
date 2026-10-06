"""Welcome guide for a first start (V1.7 B).

Shown once to new users (preferences file did not exist yet; people who
upgrade never see it unless they open it from Settings > General). Pages:
language; Claude Code integrations (only when Claude Code is installed),
each explained with what it changes; assistant options (quick-launch
shortcut, predictions, update checks); and how to find everything. Skip
keeps the defaults. Nothing is changed before Finish.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel,
                               QPushButton, QStackedWidget, QVBoxLayout, QWidget)

from localization import normalize_language, text

CLAUDE_FEATURES = ('claude_sync', 'claude_notify', 'claude_approval', 'mute_claude_toasts')


def codex_installed():
    try:
        from usage import CodexStore
        return Path(CodexStore().home).is_dir()
    except Exception:
        return False


def claude_installed():
    try:
        from claude_usage import default_home
        return Path(default_home()).is_dir()
    except Exception:
        return False


class OnboardingWizard(QDialog):
    def __init__(self, panel, claude=None, codex=None):
        super().__init__(panel if isinstance(panel, QWidget) else None)
        self.panel = panel
        self.claude = claude_installed() if claude is None else claude
        self.codex = codex_installed() if codex is None else codex
        self.setWindowTitle('Petoken')
        self.setMinimumSize(560, 420)
        self.language = normalize_language(panel.prefs.get('language'))
        layout = QVBoxLayout(self)
        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)
        self.pages = []
        self._welcome()
        if self.claude:
            self._claude_page()
        if self.codex:
            self._codex_page()
        self._assistant_page()
        self._done_page()
        row = QHBoxLayout()
        self.skip = QPushButton()
        self.back = QPushButton()
        self.next = QPushButton()
        self.next.setDefault(True)
        row.addWidget(self.skip)
        row.addStretch(1)
        row.addWidget(self.back)
        row.addWidget(self.next)
        layout.addLayout(row)
        self.skip.clicked.connect(self.skip_all)
        self.back.clicked.connect(lambda: self.go(self.stack.currentIndex() - 1))
        self.next.clicked.connect(self.forward)
        self.retranslate()
        self.go(0)

    # Pages ------------------------------------------------------------------
    def _page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        title = QLabel()
        title.setStyleSheet('font-size:18px; font-weight:600;')
        title.setWordWrap(True)
        body = QLabel()
        body.setWordWrap(True)
        body.setTextFormat(Qt.PlainText)
        layout.addWidget(title)
        layout.addWidget(body)
        self.stack.addWidget(page)
        self.pages.append((title, body))
        return layout

    def _welcome(self):
        layout = self._page()
        form = QFormLayout()
        self.language_box = QComboBox()
        self.language_box.addItem('English', 'en')
        self.language_box.addItem('简体中文', 'zh_CN')
        self.language_box.setCurrentIndex(max(0, self.language_box.findData(self.language)))
        self.language_box.currentIndexChanged.connect(self._language_changed)
        self.language_label = QLabel()
        form.addRow(self.language_label, self.language_box)
        layout.addLayout(form)
        layout.addStretch(1)

    def _claude_page(self):
        layout = self._page()
        self.claude_boxes = {}
        for key in CLAUDE_FEATURES:
            box = QCheckBox()
            box.setChecked(True)
            note = QLabel()
            note.setObjectName('muted')
            note.setWordWrap(True)
            note.setContentsMargins(26, 0, 0, 6)
            layout.addWidget(box)
            layout.addWidget(note)
            self.claude_boxes[key] = (box, note)
        layout.addStretch(1)

    def _codex_page(self):
        layout = self._page()
        self.codex_box = QCheckBox()
        self.codex_box.setChecked(True)
        self.codex_note = QLabel()
        self.codex_note.setObjectName('muted')
        self.codex_note.setWordWrap(True)
        self.codex_note.setContentsMargins(26, 0, 0, 6)
        layout.addWidget(self.codex_box)
        layout.addWidget(self.codex_note)
        layout.addStretch(1)

    def _assistant_page(self):
        layout = self._page()
        from quick_launch import HOTKEYS
        form = QFormLayout()
        self.hotkey = QComboBox()
        for name in (*HOTKEYS, 'off'):
            self.hotkey.addItem(name, name)
        self.hotkey.setCurrentIndex(max(0, self.hotkey.findData(
            self.panel.prefs.get('quick_launch_hotkey', 'Ctrl+Alt+Space'))))
        self.hotkey_label = QLabel()
        form.addRow(self.hotkey_label, self.hotkey)
        layout.addLayout(form)
        self.hints = QCheckBox()
        self.hints.setChecked(bool(self.panel.prefs.get('assistant_hints', True)))
        self.update_check = QCheckBox()
        self.update_check.setChecked(bool(self.panel.prefs.get('update_check', True)))
        self.update_auto = QCheckBox()
        self.update_auto.setChecked(bool(self.panel.prefs.get('update_auto', False)))
        for box in (self.hints, self.update_check, self.update_auto):
            layout.addWidget(box)
        layout.addStretch(1)

    def _done_page(self):
        layout = self._page()
        self.tutorial = QCheckBox()
        self.tutorial.setChecked(self.panel.prefs.get('workbench_tutorial_seen') is not True)
        layout.addWidget(self.tutorial)
        layout.addStretch(1)

    # Text -------------------------------------------------------------------
    def tr(self, key, **values):
        return text(key, self.language, **values)

    def _language_changed(self):
        self.language = self.language_box.currentData()
        self.retranslate()

    def retranslate(self):
        titles = (['welcome'] + (['claude'] if self.claude else []) + (['codex'] if self.codex else [])
                  + ['assistant', 'done'])
        for (title, body), key in zip(self.pages, titles):
            title.setText(self.tr(f'onboard_{key}_title'))
            body.setText(self.tr(f'onboard_{key}_body'))
        self.language_label.setText(self.tr('language'))
        if self.claude:
            for key, (box, note) in self.claude_boxes.items():
                box.setText(self.tr(f'onboard_{key}'))
                note.setText(self.tr(f'onboard_{key}_note'))
        if self.codex:
            self.codex_box.setText(self.tr('codex_hooks'))
            self.codex_note.setText(self.tr('onboard_codex_note'))
        self.hotkey_label.setText(self.tr('launch_hotkey'))
        self.hotkey.setItemText(self.hotkey.count() - 1, self.tr('launch_hotkey_off'))
        self.hints.setText(self.tr('assistant_hints'))
        self.update_check.setText(self.tr('update_check'))
        self.update_auto.setText(self.tr('update_auto'))
        self.tutorial.setText(self.tr('onboard_tutorial'))
        self.skip.setText(self.tr('onboard_skip'))
        self.back.setText(self.tr('onboard_back'))
        self.go(self.stack.currentIndex())

    def go(self, index):
        index = max(0, min(index, self.stack.count() - 1))
        self.stack.setCurrentIndex(index)
        self.back.setEnabled(index > 0)
        last = index == self.stack.count() - 1
        self.next.setText(self.tr('onboard_finish' if last else 'onboard_next'))

    def forward(self):
        if self.stack.currentIndex() == self.stack.count() - 1:
            self.finish()
        else:
            self.go(self.stack.currentIndex() + 1)

    # Result -----------------------------------------------------------------
    def choices(self):
        claude = ({key: box.isChecked() for key, (box, _note) in self.claude_boxes.items()}
                  if self.claude else {})
        return dict(language=self.language, claude=claude, codex_hooks=self.codex and self.codex_box.isChecked(),
                    quick_launch_hotkey=self.hotkey.currentData(),
                    assistant_hints=self.hints.isChecked(), update_check=self.update_check.isChecked(),
                    update_auto=self.update_auto.isChecked(), tutorial=self.tutorial.isChecked())

    def skip_all(self):
        self.panel.finish_onboarding(None)
        self.reject()

    def finish(self):
        self.panel.finish_onboarding(self.choices())
        self.accept()
