"""Focus companion mode (2.0).

Start a timed focus session from the pet's menu. While it runs she quietly
reads beside you and only urgent notices get through (approval requests,
failures, quota and context warnings); everything else is still recorded.
When the time is up she shows what got done in that time (todos ticked
off, AI tasks finished, files changed, tokens used) and a short break
starts: she drinks tea and reminds you to get up for a moment.

Sessions are kept in the workbench database, so reports can show how long
you focused this week.
"""
from __future__ import annotations

import time

from PySide6.QtCore import QObject, QPoint, Qt, QTimer, Signal
from PySide6.QtWidgets import (QApplication, QComboBox, QDialog, QFrame, QHBoxLayout, QLabel,
                               QPushButton, QSpinBox, QVBoxLayout, QWidget)

import theme
from approval_card import GAP, STYLE
from localization import text

CHOICES = (25, 45, 60)
BREAK_S = 5 * 60
LONG_BREAK_S = 15 * 60
LONG_BREAK_EVERY = 4
URGENT = ('needs_approval', 'failed', 'quota_low', 'context_full', 'stuck')


def clock_text(seconds):
    seconds = max(0, int(round(seconds)))
    return f'{seconds // 60:02d}:{seconds % 60:02d}'


def minutes_text(seconds, language):
    minutes = max(1, round(seconds / 60))
    hours, rest = divmod(minutes, 60)
    if hours:
        return text('focus_hours', language, hours=hours, minutes=rest)
    return text('focus_minutes', language, minutes=minutes)


class _Summary(QObject):
    ready = Signal(dict)


class FocusMode(QObject):
    """Phases: ``idle`` → ``focus`` → ``break`` → ``idle``."""

    changed = Signal()          # Phase change, and once a second while running.
    ended = Signal(dict)        # A focus phase ended: the summary (filled in further later).
    summary_ready = Signal(dict)

    def __init__(self, panel, store=None, clock=time.time):
        super().__init__(panel)
        self.panel = panel
        self._store = store
        self.clock = clock
        self.phase = 'idle'
        self.ends = 0.0
        self.started = 0.0
        self.planned = 0.0
        self.session = None
        self.project_id = None
        self.todo_id = None
        self.rounds = 0
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.tick)
        self._summary = _Summary()
        self._summary.ready.connect(self.summary_ready)

    @property
    def store(self):
        if self._store is None:
            opener = getattr(self.panel, 'workbench_store', None)
            self._store = opener() if callable(opener) else None
        return self._store

    @property
    def active(self):
        return self.phase == 'focus'

    def remaining(self, now=None):
        return max(0.0, self.ends - (self.clock() if now is None else now)) if self.phase != 'idle' else 0.0

    def quiet(self, kind):
        """True when a notice of ``kind`` should stay silent right now."""
        return self.active and kind not in URGENT

    # Phases ---------------------------------------------------------------
    def start(self, minutes, project_id=None, todo_id=None):
        now = self.clock()
        self.phase, self.started, self.planned = 'focus', now, float(minutes) * 60
        self.ends = now + self.planned
        self.project_id, self.todo_id = project_id, todo_id
        self.session = None
        if self.store is not None:
            try:
                self.session = self.store.start_focus(now, self.planned, project_id, todo_id)
            except Exception:
                self.session = None
        self.panel.prefs['focus_minutes'] = int(minutes)
        self.timer.start()
        self.changed.emit()

    def stop(self):
        """End the focus early (summary, no break), or end the break."""
        if self.phase == 'focus':
            self._finish(completed=False)
        elif self.phase == 'break':
            self._idle()

    def abandon(self):
        """Petoken is closing: record an unfinished focus, no card, no break."""
        if self.phase == 'focus' and self.session is not None and self.store is not None:
            try:
                self.store.end_focus(self.session['id'], min(self.clock(), self.ends), False)
            except Exception:
                pass
        self.phase = 'idle'
        self.timer.stop()

    def skip_break(self):
        if self.phase == 'break':
            self._idle()

    def tick(self):
        now = self.clock()
        if self.phase == 'focus' and now >= self.ends:
            self._finish(completed=True)
        elif self.phase == 'break' and now >= self.ends:
            self._idle()
            language = self.panel.prefs.get('language')
            self.panel.tray_notice(text('focus_break_over', language), text('focus_break_over_body', language))
        else:
            self.changed.emit()

    def _idle(self):
        self.phase = 'idle'
        self.timer.stop()
        self.changed.emit()

    def _finish(self, completed):
        end = min(self.clock(), self.ends)
        if self.session is not None and self.store is not None:
            try:
                self.store.end_focus(self.session['id'], end, completed)
            except Exception:
                pass
        summary = dict(start=self.started, end=end, planned=self.planned, completed=completed,
                       session=(self.session or {}).get('id'), todos=[], ai_finished=0,
                       files=None, tokens=None, loading=True)
        try:
            summary['todos'] = [row['title'] for row in self.store.todos_done_between(self.started, end + 1)]
        except Exception:
            pass
        center = getattr(self.panel, 'notifications', None)
        try:
            events = center.store.list_events(kind='finished', limit=500) if center is not None else []
            summary['ai_finished'] = sum(1 for e in events if self.started <= (e.get('at') or 0) <= end + 1)
        except Exception:
            pass
        if completed:
            self.rounds += 1
            long_break = self.rounds % LONG_BREAK_EVERY == 0
            self.phase = 'break'
            self.ends = self.clock() + (LONG_BREAK_S if long_break else BREAK_S)
            language = self.panel.prefs.get('language')
            self.panel.tray_notice(text('focus_break', language, minutes=round((self.ends - self.clock()) / 60)),
                                   text('focus_break_body', language))
            self.timer.start()
        else:
            self.rounds = 0
            self.phase = 'idle'
            self.timer.stop()
        self.changed.emit()
        self.ended.emit(dict(summary))
        self._load_usage(summary)

    def _load_usage(self, summary):
        """Files and tokens come from the report data, read in a worker."""
        # Only the running app reads Claude Code and Codex data; tests and
        # previews never start a background read of the real history.
        cache = getattr(self.panel, 'report_cache', None) if getattr(self.panel, 'live', False) else None
        if cache is None:
            self._summary.ready.emit(dict(summary, loading=False))
            return

        def done(data):
            import reports
            out = dict(summary, loading=False)
            try:
                providers, _ = reports._usage(data.get('events') or [], summary['start'], summary['end'] + 1)
                out['tokens'] = sum(p['tokens'] for p in providers.values())
                edits = (data.get('activity') or {}).get('edits') or []
                out['files'] = len({f'{project}/{path}' for at, project, path in edits
                                    if summary['start'] <= at <= summary['end'] + 1})
            except Exception:
                pass
            self._summary.ready.emit(out)

        if not cache.refresh(done):
            # A load is already running; ours joins it.
            pass


class FocusDialog(QDialog):
    """How long, and (optionally) for which project and todo."""

    def __init__(self, panel, store=None, parent=None):
        super().__init__(parent)
        self.language = panel.prefs.get('language')
        language = self.language
        self.setWindowTitle(text('focus_start_title', language))
        self.setStyleSheet(panel.styleSheet())
        layout = QVBoxLayout(self)
        intro = QLabel(text('focus_start_intro', language))
        intro.setWordWrap(True)
        intro.setObjectName('muted')
        layout.addWidget(intro)
        row = QHBoxLayout()
        row.addWidget(QLabel(text('focus_length', language)))
        self.minutes = QSpinBox()
        self.minutes.setRange(5, 180)
        self.minutes.setSingleStep(5)
        self.minutes.setSuffix(text('focus_minute_suffix', language))
        self.minutes.setValue(int(panel.prefs.get('focus_minutes', 25)))
        row.addWidget(self.minutes, 1)
        layout.addLayout(row)
        self.project = QComboBox()
        self.todo = QComboBox()
        self._todos = []
        projects, todos = [], []
        if store is not None:
            try:
                projects, todos = store.list_projects(), store.list_todos(include_completed=False)
            except Exception:
                pass
        self._todos = todos
        self.project.addItem(text('focus_no_project', language), None)
        for project in projects:
            self.project.addItem(project['name'], project['id'])
        self.project.currentIndexChanged.connect(lambda _: self._fill_todos())
        for label, widget in ((text('focus_project', language), self.project),
                              (text('focus_todo', language), self.todo)):
            line = QHBoxLayout()
            line.addWidget(QLabel(label))
            line.addWidget(widget, 1)
            layout.addLayout(line)
        self._fill_todos()
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton(text('launch_cancel', language))
        cancel.clicked.connect(self.reject)
        start = QPushButton(text('focus_start', language))
        start.setDefault(True)
        start.clicked.connect(self.accept)
        buttons.addWidget(cancel)
        buttons.addWidget(start)
        layout.addLayout(buttons)
        self.setMinimumWidth(360)

    def _fill_todos(self):
        project = self.project.currentData()
        self.todo.clear()
        self.todo.addItem(text('focus_no_todo', self.language), None)
        for todo in self._todos:
            if project is None or todo.get('project_id') == project:
                self.todo.addItem(todo['title'], todo['id'])

    def values(self):
        return dict(minutes=self.minutes.value(), project_id=self.project.currentData(),
                    todo_id=self.todo.currentData())


class FocusCard(QWidget):
    """What got done in a focus session, beside the pet."""

    again = Signal()

    def __init__(self, language, summary, token_style=None):
        super().__init__(None)
        self.language = language
        self.token_style = token_style
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setStyleSheet(STYLE)
        self.setFixedWidth(280)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        frame = QFrame()
        frame.setObjectName('approval')
        outer.addWidget(frame)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(5)
        self.title = QLabel()
        self.title.setObjectName('title')
        layout.addWidget(self.title)
        self.lines = QLabel()
        self.lines.setWordWrap(True)
        layout.addWidget(self.lines)
        self.note = QLabel()
        self.note.setObjectName('muted')
        self.note.setWordWrap(True)
        layout.addWidget(self.note)
        row = QHBoxLayout()
        row.addStretch(1)
        self.close_button = QPushButton(text('focus_card_close', language))
        self.close_button.clicked.connect(self.close)
        self.again_button = QPushButton(text('focus_again', language))
        self.again_button.setObjectName('allow')
        self.again_button.clicked.connect(lambda: (self.again.emit(), self.close()))
        row.addWidget(self.close_button)
        row.addWidget(self.again_button)
        layout.addLayout(row)
        self.update_summary(summary)

    def update_summary(self, summary):
        language = self.language
        spent = minutes_text(summary['end'] - summary['start'], language)
        self.title.setText(text('focus_done_title' if summary['completed'] else 'focus_stopped_title',
                                language, time=spent))
        lines = []
        todos = summary.get('todos') or []
        if todos:
            shown = '、'.join(todos[:3]) if (language or '').startswith('zh') else ', '.join(todos[:3])
            lines.append(text('focus_line_todos', language, count=len(todos), names=shown))
        if summary.get('ai_finished'):
            lines.append(text('focus_line_ai', language, count=summary['ai_finished']))
        if summary.get('files'):
            lines.append(text('focus_line_files', language, count=summary['files']))
        if summary.get('tokens'):
            from token_format import format_tokens
            shown = format_tokens(summary['tokens'], self.token_style) if self.token_style else format_tokens(summary['tokens'])
            lines.append(text('focus_line_tokens', language, tokens=shown))
        if not lines and not summary.get('loading'):
            lines.append(text('focus_line_none', language))
        self.lines.setText('\n'.join('· ' + line for line in lines))
        self.lines.setVisible(bool(lines))
        self.note.setText(text('focus_counting', language) if summary.get('loading') else
                          (text('focus_break_note', language) if summary['completed'] else ''))
        self.note.setVisible(bool(self.note.text()))
        self.adjustSize()

    def place_beside(self, pet):
        screen = (pet.screen() or QApplication.primaryScreen()).availableGeometry()
        box = pet.geometry()
        x = box.left() - self.width() - GAP
        if x < screen.left():
            x = box.right() + GAP
        y = box.center().y() - self.height() // 2
        x = max(screen.left(), min(x, screen.right() - self.width() + 1))
        y = max(screen.top(), min(y, screen.bottom() - self.height() + 1))
        self.move(QPoint(x, y))
