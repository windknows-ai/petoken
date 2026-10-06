"""Update check schedule and the "new version" dialog (V1.7 B).

``UpdateController`` checks GitHub (``updater.latest``) two minutes after
start and then whenever a day has passed, in a worker thread. A newer,
not-skipped version opens ``UpdateDialog`` (what changed; Update now /
Later / Skip this version; "Update automatically from now on"). With
automatic updates on, Petoken installs by itself, but only while no task
is running or waiting for an answer, so work is never interrupted.
"""
from __future__ import annotations

import threading
import time

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import (QCheckBox, QDialog, QHBoxLayout, QLabel, QPushButton, QTextBrowser,
                               QVBoxLayout)

import updater
from app_config import APP_VERSION
from localization import text

FIRST_CHECK_MS = 120_000
TICK_MS = 3600_000


class UpdateDialog(QDialog):
    def __init__(self, controller, release):
        super().__init__(None)
        self.controller = controller
        self.release = release
        language = self.language = controller.panel.prefs.get('language')
        self.setWindowTitle(text('update_title', language, version=release['version']))
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.resize(520, 440)
        layout = QVBoxLayout(self)
        head = QLabel(text('update_heading', language, version=release['version'], current=APP_VERSION))
        head.setWordWrap(True)
        head.setStyleSheet('font-size:14px; font-weight:600;')
        layout.addWidget(head)
        notes = QTextBrowser()
        notes.setOpenExternalLinks(True)
        notes.setMarkdown(release.get('notes') or text('update_no_notes', language))
        layout.addWidget(notes, 1)
        self.auto = QCheckBox(text('update_auto', language))
        self.auto.setChecked(bool(controller.panel.prefs.get('update_auto')))
        layout.addWidget(self.auto)
        self.status = QLabel('')
        self.status.setObjectName('muted')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        row = QHBoxLayout()
        self.skip = QPushButton(text('update_skip', language))
        self.later = QPushButton(text('update_later', language))
        self.now = QPushButton(text('update_now', language))
        self.now.setDefault(True)
        row.addWidget(self.skip)
        row.addStretch(1)
        row.addWidget(self.later)
        row.addWidget(self.now)
        layout.addLayout(row)
        self.skip.clicked.connect(self._skip)
        self.later.clicked.connect(self._later)
        self.now.clicked.connect(self._now)

    def _remember_auto(self):
        self.controller.set_auto(self.auto.isChecked())

    def _skip(self):
        self._remember_auto()
        self.controller.skip(self.release['version'])
        self.accept()

    def _later(self):
        self._remember_auto()
        self.reject()

    def _now(self):
        self._remember_auto()
        for button in (self.skip, self.later, self.now):
            button.setEnabled(False)
        self.status.setText(text('update_downloading', self.language))
        self.controller.install(self.release, self)

    def failed(self, reason):
        for button in (self.skip, self.later, self.now):
            button.setEnabled(True)
        self.status.setText(text('update_failed', self.language) + (f' ({reason})' if reason else ''))


class UpdateController(QObject):
    checked = Signal(object, bool)      # release or None, asked by the user
    installed = Signal(object, object)  # dialog, error text or None

    def __init__(self, panel, check=None, download=None, start=None):
        super().__init__()
        self.panel = panel
        self.check = check or updater.latest
        self.download = download or (lambda release: updater.download(release, self.folder()))
        self.start = start or updater.start_install
        self.dialog = None
        self.pending = None       # A release waiting for an idle moment (automatic updates).
        self._busy = False
        self.checked.connect(self._checked)
        self.installed.connect(self._installed)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)

    def folder(self):
        from widget import PREF_DIR
        return PREF_DIR / 'updates'

    def start_schedule(self):
        QTimer.singleShot(FIRST_CHECK_MS, self.tick)
        self.timer.start(TICK_MS)

    def stop(self):
        self.timer.stop()

    def tick(self):
        if getattr(self.panel, 'closing', False):
            return
        if self.pending is not None and self.idle():
            release, self.pending = self.pending, None
            self.install(release, None)
            return
        if updater.due(self.panel.prefs):
            self.check_now(manual=False)

    def check_now(self, manual=True):
        if self._busy:
            return False
        self._busy = True

        def work():
            try:
                release = self.check()
            except Exception:
                release = None
            self.checked.emit(release, manual)
        threading.Thread(target=work, daemon=True).start()
        return True

    def _checked(self, release, manual):
        self._busy = False
        prefs = self.panel.prefs
        prefs['update_checked_at'] = time.time()
        self._persist()
        found = updater.offer(release, APP_VERSION, {} if manual else prefs)
        if found is None:
            if manual:
                self.panel.tray_notice(text('update_none' if release is not None else 'update_check_failed',
                                            prefs.get('language'), version=APP_VERSION), '')
            return
        if prefs.get('update_auto') and not manual:
            if self.idle():
                self.install(found, None)
            else:
                self.pending = found   # Installed at the next idle tick.
            return
        self.show(found)

    def show(self, release):
        if self.dialog is not None and self.dialog.isVisible():
            self.dialog.raise_()
            return
        self.dialog = UpdateDialog(self, release)
        self.dialog.show()
        self.panel.tray_notice(text('update_title', self.panel.prefs.get('language'),
                                    version=release['version']), '')

    def idle(self):
        """No running task and no open approval question."""
        manager = getattr(self.panel, 'task_manager', None)
        approvals = getattr(self.panel, 'approvals', None)
        running = manager.total_task_count() if manager is not None else 0
        waiting = len(getattr(approvals, 'queue', []) or [])
        return running == 0 and waiting == 0

    def set_auto(self, value):
        self.panel.prefs['update_auto'] = bool(value)
        self._persist()

    def skip(self, version):
        self.panel.prefs['update_skip'] = version
        self._persist()

    def _persist(self):
        try:
            self.panel.persist()
        except Exception:
            pass

    def install(self, release, dialog):
        def work():
            try:
                installer = self.download(release)
                self.start(installer)
                error = None
            except Exception as exc:   # Network, checksum or launch problems.
                error = str(exc)[:120]
            self.installed.emit(dialog, error)
        threading.Thread(target=work, daemon=True).start()

    def _installed(self, dialog, error):
        if error is not None:
            if dialog is not None:
                dialog.failed(error)
            return
        # The installer replaces Petoken's files and reopens it.
        QTimer.singleShot(300, self.panel.shutdown)
