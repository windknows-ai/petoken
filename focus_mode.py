"""Focus companion mode (2.0).

Start a timed focus session from the pet's menu, optionally on one todo
(its name shows beside the countdown, and the end card can tick it off).
While it runs she quietly reads beside you and only urgent notices get
through (approval requests, failures, quota and context warnings);
everything else is still recorded. When the time is up she shows what got
done in that time (todos ticked off, AI tasks finished, files changed,
tokens used) and a break starts: she drinks tea and reminds you to get up.
Break lengths and how often a long break comes are your choice.

Sessions are kept in the workbench database, so reports can show how long
you focused this week.
"""
from __future__ import annotations

import time

from PySide6.QtCore import QObject, QPoint, Qt, QTimer, Signal
from PySide6.QtWidgets import (QApplication, QComboBox, QDialog, QFormLayout, QFrame, QHBoxLayout, QLabel,
                               QPushButton, QSpinBox, QVBoxLayout, QWidget)

import theme
from approval_card import GAP, STYLE
from localization import text

CHOICES = (25, 45, 60)
# Defaults for the break settings (minutes; rounds). 0 turns a break off.
BREAK_MIN = 5
LONG_BREAK_MIN = 15
LONG_BREAK_EVERY = 4


def break_settings(prefs):
    """(break, long break, long break every n rounds) from the preferences."""
    def number(key, default, top):
        value = prefs.get(key, default)
        return value if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= top else default
    return (number('focus_break', BREAK_MIN, 60), number('focus_long_break', LONG_BREAK_MIN, 120),
            number('focus_long_every', LONG_BREAK_EVERY, 12))
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
    """Phases: ``idle`` → ``focus`` → ``focus_over`` → ``break`` → ``break_over`` → ``idle``.

    Time running out never moves on by itself (2.0.4): at the end of the
    focus she waits (``focus_over``) until you press OK, and only then the
    break starts; at the end of the break she waits again (``break_over``)
    until you press OK. Ending early, or a break of 0 minutes, skips them.
    """

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
        self.todo_title = ''
        self.rounds = 0
        self.break_completed = False      # The last break ran its full time.
        self.pending_break = 0            # Minutes of the break waiting for OK.
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
        return (max(0.0, self.ends - (self.clock() if now is None else now))
                if self.phase in ('focus', 'break') else 0.0)

    @property
    def waiting(self):
        """Time is up and she waits for OK."""
        return self.phase in ('focus_over', 'break_over')

    def quiet(self, kind):
        """True when a notice of ``kind`` should stay silent right now."""
        return self.active and kind not in URGENT

    # Phases ---------------------------------------------------------------
    def start(self, minutes, todo=None):
        """Focus for ``minutes``, optionally on ``todo`` (a todo record)."""
        now = self.clock()
        self.break_completed = False
        self.pending_break = 0
        self.phase, self.started, self.planned = 'focus', now, float(minutes) * 60
        self.ends = now + self.planned
        self.todo_id = (todo or {}).get('id')
        self.todo_title = (todo or {}).get('title') or ''
        self.project_id = (todo or {}).get('project_id')
        project_id, todo_id = self.project_id, self.todo_id
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
        """End the focus early (summary, no break), end the break, or skip the waiting."""
        if self.phase == 'focus':
            self._finish(completed=False)
        elif self.phase in ('break', 'focus_over', 'break_over'):
            self._idle()

    def acknowledge(self):
        """OK: after the focus, start the break; after the break, back to normal."""
        if self.phase == 'focus_over':
            minutes = self.pending_break
            self.pending_break = 0
            if not minutes:
                self._idle()
                return
            self.phase = 'break'
            self.ends = self.clock() + minutes * 60
            self.timer.start()
            self.changed.emit()
        elif self.phase == 'break_over':
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
        if self.phase in ('break', 'focus_over'):
            self.break_completed = False
            self.pending_break = 0
            self._idle()
        elif self.phase == 'break_over':
            self._idle()

    def tick(self):
        now = self.clock()
        if self.phase == 'focus' and now >= self.ends:
            self._finish(completed=True)
        elif self.phase == 'break' and now >= self.ends:
            self.break_completed = True
            self.phase = 'break_over'        # She waits for OK.
            self.timer.stop()
            self.changed.emit()
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
                       files=None, tokens=None, loading=True, todo_id=self.todo_id,
                       todo_title=self.todo_title, todo_done=False)
        if self.todo_id and self.store is not None:
            try:
                summary['todo_done'] = any(t['id'] == self.todo_id and t['done'] for t in self.store.list_todos())
            except Exception:
                pass
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
        rest, long_rest, every = break_settings(self.panel.prefs)
        if completed:
            self.rounds += 1
        minutes = (long_rest if completed and every and long_rest and self.rounds % every == 0
                   else rest if completed else 0)
        summary['break_min'] = minutes
        if minutes:
            self.phase = 'focus_over'        # The break starts when you press OK.
            self.pending_break = minutes
            language = self.panel.prefs.get('language')
            self.panel.tray_notice(text('focus_break', language, minutes=minutes),
                                   text('focus_break_body', language))
            self.timer.stop()
        else:
            if not completed:
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


class FocusTag(QWidget):
    """The countdown and its End button, a small window under her.

    Placed under the task page buttons (or where they would be), clear of
    the stars circling her; without tasks, just below her feet.
    """

    GAP = 4

    def __init__(self, pet):
        super().__init__(None)
        self.pet = pet
        flags = Qt.Tool | Qt.FramelessWindowHint | Qt.WindowDoesNotAcceptFocus
        if pet.panel.prefs.get('always_on_top', True):
            flags |= Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setMouseTracking(True)
        self.text = ''
        self.label = ''
        self.hover = False
        self.tag_rect = self.stop_rect = None

    def _font(self):
        from PySide6.QtGui import QFont
        font = QFont('Segoe UI', self.pet._px(8))
        font.setWeight(QFont.DemiBold)
        return font

    def sync(self):
        """Show, update or hide to match the focus state; follow her."""
        pet = self.pet
        text = pet.focus_subtitle() if pet.isVisible() else None
        if text is None:
            if self.isVisible():
                self.hide()
                self._pager()
            return
        from PySide6.QtCore import QRectF, QSize
        from PySide6.QtGui import QFontMetrics
        mode = pet.panel.focus_mode
        label = text_for(pet, {'focus': 'focus_end_button', 'break': 'focus_end_break_button',
                               'focus_over': 'focus_start_break_button'}.get(mode.phase, 'focus_card_close'))
        if (text, label) != (self.text, self.label) or self.tag_rect is None:
            self.text, self.label = text, label
            metrics = QFontMetrics(self._font())
            h, gap = pet._px(24), pet._px(5)
            shown = metrics.elidedText(text, Qt.ElideRight, pet._px(200))
            w = metrics.horizontalAdvance(shown) + pet._px(24)
            bw = metrics.horizontalAdvance(label) + pet._px(20)
            self.shown = shown
            self.tag_rect = QRectF(.5, .5, w, h - 1)
            self.stop_rect = QRectF(w + gap, .5, bw, h - 1)
            size = QSize(int(w + gap + bw + 1), h)
            if self.size() != size:
                self.setFixedSize(size)
            self.update()
        self.follow()
        now = time.monotonic()
        if not self.isVisible():
            self.show()
            self._raised = 0.0
            self._pager()
        if now - getattr(self, '_raised', 0.0) > 1.0:
            self.raise_()          # Above stars that appeared after it.
            self._raised = now

    def _pager(self):
        manager = getattr(self.pet.panel, 'task_manager', None)
        if manager is not None:
            try:
                manager._update_page_controls()
            except Exception:
                pass

    def follow(self):
        pet = self.pet
        manager = getattr(pet.panel, 'task_manager', None)
        try:
            spot = manager.focus_tag_position(self.width(), self.height()) if manager else None
        except Exception:
            spot = None
        if spot is not None:
            x, y = spot          # Under the page buttons, or where they would be.
        else:
            # No task ring: just below her feet, or above her head near the bottom.
            x = pet.x() + (pet.width() - self.width()) // 2
            y = pet.y() + pet.height() + self.GAP
            screen = (pet.screen() or QApplication.primaryScreen()).availableGeometry()
            if y + self.height() > screen.bottom() + 1:
                overlay = getattr(pet, 'usage_overlay', None)
                top = overlay.y() if overlay is not None and overlay.isVisible() else pet.y() + pet._px(56)
                y = top - self.height() - self.GAP
        screen = (pet.screen() or QApplication.primaryScreen()).availableGeometry()
        x = max(screen.left(), min(x, screen.right() - self.width() + 1))
        y = max(screen.top(), min(y, screen.bottom() - self.height() + 1))
        if self.pos() != QPoint(x, y):
            self.move(x, y)

    def paintEvent(self, event):
        from PySide6.QtGui import QColor, QPainter, QPen
        if self.tag_rect is None:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setFont(self._font())
        fill = QColor(theme.CARD)
        fill.setAlpha(245)
        p.setPen(QPen(QColor(theme.VIOLET), 1))
        p.setBrush(fill)
        radius = self.tag_rect.height() / 2
        p.drawRoundedRect(self.tag_rect, radius, radius)
        p.setPen(QColor(theme.VIOLET))
        p.drawText(self.tag_rect, Qt.AlignCenter, self.shown)
        p.setPen(QPen(QColor(theme.PRIMARY_FILL_PRESSED), 1))
        p.setBrush(QColor(theme.PRIMARY_FILL_HOVER if self.hover else theme.PRIMARY_FILL))
        p.drawRoundedRect(self.stop_rect, radius, radius)
        p.setPen(QColor(theme.PRIMARY_TEXT))
        p.drawText(self.stop_rect, Qt.AlignCenter, self.label)

    def mouseMoveEvent(self, event):
        hover = self.stop_rect is not None and self.stop_rect.contains(event.position())
        if hover != self.hover:
            self.hover = hover
            self.setCursor(Qt.PointingHandCursor if hover else Qt.ArrowCursor)
            self.update()

    def leaveEvent(self, event):
        if self.hover:
            self.hover = False
            self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.stop_rect is not None \
                and self.stop_rect.contains(event.position()):
            self.end()

    def end(self):
        mode = self.pet.panel.focus_mode
        if mode.phase == 'focus':
            mode.stop()
        elif mode.waiting:
            mode.acknowledge()          # Start the break, or back to normal.
        else:
            mode.skip_break()
        self.sync()


def text_for(pet, key):
    return text(key, pet.panel.prefs.get('language'))


class FocusDialog(QDialog):
    """How long, on which todo (optional), and how breaks go."""

    def __init__(self, panel, store=None, parent=None):
        super().__init__(parent)
        self.language = language = panel.prefs.get('language')
        self.setWindowTitle(text('focus_start_title', language))
        self.setStyleSheet(panel.styleSheet())
        layout = QVBoxLayout(self)
        intro = QLabel(text('focus_start_intro', language))
        intro.setWordWrap(True)
        intro.setObjectName('muted')
        layout.addWidget(intro)
        form = QFormLayout()
        self.minutes = QSpinBox()
        self.minutes.setRange(1, 180)
        self.minutes.setSingleStep(5)
        self.minutes.setSuffix(text('focus_minute_suffix', language))
        self.minutes.setValue(int(panel.prefs.get('focus_minutes', 25)))
        form.addRow(text('focus_length', language), self.minutes)
        self.todo = QComboBox()
        self._todos = []
        try:
            projects = {p['id']: p['name'] for p in store.list_projects()} if store is not None else {}
            self._todos = store.list_todos(include_completed=False) if store is not None else []
        except Exception:
            projects = {}
        self.todo.addItem(text('focus_no_todo', language), None)
        for todo in self._todos:
            name = projects.get(todo.get('project_id'))
            self.todo.addItem(f"{name} · {todo['title']}" if name else todo['title'], todo['id'])
        form.addRow(text('focus_todo', language), self.todo)
        todo_note = QLabel(text('focus_todo_note', language))
        todo_note.setObjectName('muted')
        todo_note.setWordWrap(True)
        form.addRow('', todo_note)
        rest, long_rest, every = break_settings(panel.prefs)
        self.rest = self._spin(0, 60, rest, text('focus_minute_suffix', language), text('focus_no_break', language))
        self.long_rest = self._spin(0, 120, long_rest, text('focus_minute_suffix', language),
                                    text('focus_no_break', language))
        self.every = self._spin(0, 12, every, text('focus_rounds_suffix', language), text('focus_never', language))
        form.addRow(text('focus_break_length', language), self.rest)
        form.addRow(text('focus_long_break_length', language), self.long_rest)
        form.addRow(text('focus_long_break_every', language), self.every)
        layout.addLayout(form)
        # The whole plan in one sentence, following the numbers as you change them.
        self.plan = QLabel()
        self.plan.setWordWrap(True)
        self.plan.setStyleSheet(f'background:{theme.BADGE_BG}; border-radius:8px; padding:8px 10px;'
                                f' color:{theme.VIOLET}; font-weight:600;')
        layout.addWidget(self.plan)
        explain = QLabel(text('focus_break_explain', language))
        explain.setWordWrap(True)
        explain.setObjectName('muted')
        layout.addWidget(explain)
        for spin in (self.minutes, self.rest, self.long_rest, self.every):
            spin.valueChanged.connect(lambda _: self._update_plan())
        self._update_plan()
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
        self.setMinimumWidth(400)

    def _update_plan(self):
        focus, rest, long_rest, every = (self.minutes.value(), self.rest.value(),
                                         self.long_rest.value(), self.every.value())
        if not rest and not (every and long_rest):
            key = 'focus_plan_none'
        elif every and long_rest:
            key = 'focus_plan_long' if rest else 'focus_plan_long_only'
        else:
            key = 'focus_plan_rest'
        self.plan.setText(text(key, self.language, focus=focus, rest=rest, long=long_rest, every=every))

    @staticmethod
    def _spin(low, high, value, suffix, zero):
        spin = QSpinBox()
        spin.setRange(low, high)
        spin.setValue(value)
        spin.setSuffix(suffix)
        spin.setSpecialValueText(zero)
        return spin

    def values(self):
        todo = next((t for t in self._todos if t['id'] == self.todo.currentData()), None)
        return dict(minutes=self.minutes.value(), todo=todo, focus_break=self.rest.value(),
                    focus_long_break=self.long_rest.value(), focus_long_every=self.every.value())


CARD_WIDTH = 280


class FocusCard(QWidget):
    """What got done in a focus session, beside the pet."""

    again = Signal()
    todo_done = Signal(str)
    acknowledged = Signal()     # OK: the break may start.

    def __init__(self, language, summary, token_style=None):
        super().__init__(None)
        self.language = language
        self.token_style = token_style
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setStyleSheet(STYLE)
        self.setFixedWidth(CARD_WIDTH)
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
        self.todo_button = QPushButton(text('focus_todo_done', language))
        self.todo_button.clicked.connect(self._todo_done)
        row.addWidget(self.todo_button)
        row.addStretch(1)
        self.close_button = QPushButton(text('focus_card_close', language))
        self.close_button.clicked.connect(lambda: (self.acknowledged.emit(), self.close()))
        self.again_button = QPushButton(text('focus_again', language))
        self.again_button.setObjectName('allow')
        self.again_button.clicked.connect(lambda: (self.again.emit(), self.close()))
        row.addWidget(self.close_button)
        row.addWidget(self.again_button)
        layout.addLayout(row)
        self.update_summary(summary)

    def _todo_done(self):
        todo_id = (self.summary or {}).get('todo_id')
        if todo_id:
            self.todo_done.emit(todo_id)
            self.summary['todo_done'] = True
            self.update_summary(self.summary)

    def update_summary(self, summary):
        self.summary = dict(summary)
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
        if summary.get('todo_title'):
            lines.insert(0, text('focus_line_focused', language, todo=summary['todo_title']))
            self.lines.setText('\n'.join('· ' + line for line in lines))
            self.lines.setVisible(True)
        self.todo_button.setVisible(bool(summary.get('todo_id')) and not summary.get('todo_done'))
        self.note.setText(text('focus_counting', language) if summary.get('loading') else
                          (text('focus_break_note', language, minutes=summary['break_min'])
                           if summary.get('break_min') else ''))
        self.note.setVisible(bool(self.note.text()))
        self.fit_height()

    def fit_height(self):
        """Tall enough for the wrapped lines (adjustSize alone cuts long todo names off)."""
        self.ensurePolished()
        layout = self.layout()
        layout.invalidate()
        # 280 px, or wider when the buttons need it (English is longer).
        self.setFixedWidth(max(CARD_WIDTH, layout.minimumSize().width()))
        self.adjustSize()
        layout.activate()
        if layout.hasHeightForWidth():
            self.resize(self.width(), max(self.height(), layout.totalHeightForWidth(self.width())))

    def showEvent(self, event):
        # The style sheet sets the final fonts when the card is shown.
        super().showEvent(event)
        self.fit_height()

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
