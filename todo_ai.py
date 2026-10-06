"""Todos handed to Claude Code or Codex (V1.7 C).

A todo can be given to an AI now or at a set time (workbench > Todos >
Give to AI…). ``TodoScheduler`` checks every TICK_MS:

- A waiting todo whose time has come starts like quick launch: a new
  terminal runs the CLI on the todo's prompt in its folder. A start that is
  more than MISSED_AFTER_S late (Petoken or the PC was off) follows the
  user's choice: remind (state "missed"; the user runs or cancels it) or
  run it now.
- The new task is matched to the todo: for Claude Code, the first session
  a person opened in that folder after the start (its live registry); for
  Codex, the newest thread in that folder that started after it.
- When that task first finishes, the todo is ticked and a note records
  what the AI did (files, time, cost); a failure is marked on the todo.
"""
from __future__ import annotations

import json
import threading
import time
from datetime import datetime
from pathlib import Path, PureWindowsPath

from PySide6.QtCore import QDateTime, QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import (QButtonGroup, QComboBox, QDateTimeEdit, QDialog, QHBoxLayout, QLabel,
                               QPlainTextEdit, QPushButton, QRadioButton, QVBoxLayout)

from localization import text
from notifications import parse_recap, recap_text
from providers import PROVIDER_NAMES

TICK_MS = 30_000
MISSED_AFTER_S = 10 * 60
MATCH_WINDOW_S = 6 * 3600
# A started todo whose task never shows up (the CLI failed to start, the
# window was closed at once) stops waiting after this long.
MATCH_TIMEOUT_S = 15 * 60
MISSED_POLICIES = ('ask', 'run')


def _folder_key(value):
    if not isinstance(value, str) or not value:
        return ''
    if value.startswith('\\\\?\\'):
        value = value[4:]
    return str(PureWindowsPath(value)).rstrip('\\/').lower()


def claude_session_for(folder, since, home=None):
    """Scoped key of the first Claude session opened in ``folder`` at or
    after ``since``, from Claude Code's live registry, or None."""
    from claude_usage import default_home, scoped_session_id
    root = Path(home if home is not None else default_home()) / 'sessions'
    wanted, best = _folder_key(folder), None
    for path in root.glob('*.json'):
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict) or data.get('kind', 'interactive') != 'interactive':
            continue
        started = data.get('startedAt')
        started = started / 1000 if isinstance(started, (int, float)) and started > 1e11 else started
        if (_folder_key(data.get('cwd')) == wanted and isinstance(started, (int, float))
                and since - 5 <= started <= since + MATCH_WINDOW_S and data.get('sessionId')):
            if best is None or started < best[0]:
                best = (started, data['sessionId'])
    return scoped_session_id(best[1]) if best else None


def codex_thread_for(folder, since):
    """Newest Codex thread in ``folder`` that started after ``since``, or None."""
    try:
        import codex_recap
        from usage import CodexStore
        home = CodexStore().home
        rows = [row for row in codex_recap.thread_rows(home) if _folder_key(row.get('cwd')) == _folder_key(folder)]
    except Exception:
        return None
    best = None
    for row in rows[:20]:
        try:
            started = codex_recap.recap_row(home, row).get('started_at')
        except Exception:
            continue
        if isinstance(started, (int, float)) and since - 5 <= started <= since + MATCH_WINDOW_S:
            if best is None or started < best[0]:
                best = (started, row['id'])
    return best[1] if best else None


def recap_note(language, todo_title, schedule, event, currency='USD', rates=None):
    """(title, body) of the note written when the AI finishes a todo."""
    app = PROVIDER_NAMES.get(schedule['provider_id'], schedule['provider_id'])
    lines = [text('todo_ai_note_intro', language, app=app, title=todo_title),
             text('todo_ai_note_prompt', language, prompt=schedule['prompt']),
             text('todo_ai_note_folder', language, folder=schedule['folder'])]
    summary = recap_text(event.get('detail'), language, currency, rates)
    if summary:
        lines.append(text('todo_ai_note_summary', language, summary=summary))
    names = (parse_recap(event.get('detail')) or {}).get('names') or []
    if names:
        lines.append(text('todo_ai_note_files', language))
        lines += [f'- {name}' for name in names]
    lines.append(text('todo_ai_note_check', language))
    return text('todo_ai_note_title', language, title=todo_title)[:200], '\n'.join(lines)


class TodoScheduler(QObject):
    changed = Signal()              # The workbench should refresh.
    matched = Signal(str, str)      # todo id, task key (from the matching worker)

    def __init__(self, panel, store=None, launcher=None, match=None):
        super().__init__()
        self.panel = panel
        self._store = store
        # Only the running app (start()) or an injected store touches the
        # user's workbench; a test or preview panel never opens it.
        self.enabled = store is not None
        self.launcher = launcher
        self.match = match or self._match
        self._announced_missed = set()
        self._matching = False
        self.matched.connect(self._matched)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)

    # Store --------------------------------------------------------------
    @property
    def store(self):
        if self._store is None:
            from widget import PREF_DIR
            from workbench_store import WorkbenchStore
            self._store = WorkbenchStore(PREF_DIR / 'workbench.sqlite3')
        return self._store

    def start(self):
        self.enabled = True
        self.timer.start(TICK_MS)
        QTimer.singleShot(5_000, self.tick)

    def stop(self):
        self.timer.stop()
        if self._store is not None:
            try:
                self._store.close()
            except Exception:
                pass
            self._store = None

    # Scheduling ---------------------------------------------------------
    def tick(self, now=None):
        if not self.enabled or getattr(self.panel, 'closing', False):
            return
        now = time.time() if now is None else now
        try:
            waiting = self.store.list_schedules(['waiting'])
            started = self.store.list_schedules(['started'])
        except Exception:
            return
        missed = []
        for schedule in waiting:
            if schedule['run_at'] > now:
                continue
            late = now - schedule['run_at'] > MISSED_AFTER_S
            if late and self.panel.prefs.get('schedule_missed', 'ask') != 'run':
                self.store.update_schedule(schedule['todo_id'], state='missed')
                missed.append(schedule)
            else:
                self.run(schedule['todo_id'], now)
        lost = [s for s in started if not s['task_key'] and now - (s['started_at'] or now) > MATCH_TIMEOUT_S]
        for schedule in lost:
            self.store.update_schedule(schedule['todo_id'], state='failed', task_key='')
        if lost:
            language = self.panel.prefs.get('language')
            self.panel.tray_notice(text('todo_ai_lost', language, count=len(lost)), text('todo_ai_lost_body', language))
            self.changed.emit()
        unmatched = [s for s in started if not s['task_key'] and s not in lost]
        if unmatched and not self._matching:
            # Reading Codex threads can take a moment: never on the UI thread.
            self._matching = True

            def work():
                try:
                    for schedule in unmatched:
                        key = self.match(schedule)
                        if key:
                            self.matched.emit(schedule['todo_id'], key)
                finally:
                    self._matching = False
            threading.Thread(target=work, daemon=True).start()
        fresh = [s for s in missed if s['todo_id'] not in self._announced_missed]
        if fresh:
            self._announced_missed.update(s['todo_id'] for s in fresh)
            self.panel.tray_notice(text('todo_ai_missed', self.panel.prefs.get('language'), count=len(fresh)),
                                   text('todo_ai_missed_body', self.panel.prefs.get('language')))
        if missed:
            self.changed.emit()

    def bind(self, bindings):
        """Codex hook launch bindings: {thread_id, external_id (todo id)}."""
        if not self.enabled:
            return
        for binding in bindings or []:
            todo_id, thread = binding.get('external_id'), binding.get('thread_id')
            try:
                schedule = self.store.get_schedule(todo_id) if todo_id and thread else None
            except Exception:
                continue
            if schedule and schedule['state'] == 'started' and schedule['provider_id'] == 'codex':
                self._matched(todo_id, thread)

    def _matched(self, todo_id, key):
        try:
            self.store.update_schedule(todo_id, task_key=key)
        except Exception:
            return
        self.changed.emit()

    def run(self, todo_id, now=None):
        """Start a todo's task now (also for a missed one the user wants to run)."""
        now = time.time() if now is None else now
        schedule = self.store.get_schedule(todo_id)
        if schedule is None:
            return False
        try:
            from quick_launch import build_command
            import claude_launch
            argv = build_command(schedule['provider_id'], schedule['folder'], schedule['prompt'],
                                 external_id=todo_id, model=schedule.get('model') or None,
                                 effort=schedule.get('effort') or None)
            (self.launcher or claude_launch.launch)(argv)
        except (ValueError, RuntimeError, OSError):
            self.store.update_schedule(todo_id, state='failed')
            self.changed.emit()
            return False
        self.store.update_schedule(todo_id, state='started', started_at=now, task_key=None)
        self.changed.emit()
        return True

    def _match(self, schedule):
        if schedule['provider_id'] == 'claude':
            return claude_session_for(schedule['folder'], schedule['started_at'] or 0)
        return codex_thread_for(schedule['folder'], schedule['started_at'] or 0)

    # Outcomes -----------------------------------------------------------
    def on_event(self, event):
        """A stored notification: finish or fail the todo its task belongs to."""
        kind = (event or {}).get('kind')
        if not self.enabled or kind not in ('finished', 'failed'):
            return
        key = (event.get('provider'), event.get('task_key'))
        try:
            started = self.store.list_schedules(['started'])
        except Exception:
            return
        for schedule in started:
            if (schedule['provider_id'], schedule['task_key']) != key:
                continue
            if kind == 'failed':
                self.store.update_schedule(schedule['todo_id'], state='failed')
            else:
                self._finish(schedule, event)
            self.changed.emit()

    def _finish(self, schedule, event):
        store, prefs = self.store, self.panel.prefs
        todo = next((t for t in store.list_todos() if t['id'] == schedule['todo_id']), None)
        if todo is None:
            return
        title, body = recap_note(prefs.get('language'), todo['title'], schedule, event,
                                 getattr(self.panel, 'currency', 'USD'),
                                 (getattr(self.panel, 'fx', None) or {}).get('rates'))
        note = store.create_note(title, body, todo['project_id'])
        store.update_todo(todo['id'], todo['title'], todo['project_id'], True)
        store.update_schedule(schedule['todo_id'], state='finished', note_id=note['id'])


class GiveToAiDialog(QDialog):
    """Who does a todo, where, what exactly, and when."""

    def __init__(self, parent, panel, todo, schedule=None, folders=()):
        super().__init__(parent)
        self.todo = todo
        language = self.language = panel.prefs.get('language')
        self.setWindowTitle(text('todo_ai_title', language))
        self.setMinimumWidth(480)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(text('todo_ai_prompt', language)))
        self.prompt = QPlainTextEdit((schedule or {}).get('prompt') or todo['title'])
        self.prompt.setFixedHeight(80)
        layout.addWidget(self.prompt)
        layout.addWidget(QLabel(text('launch_folder', language)))
        self.folder = QComboBox()
        self.folder.setEditable(True)
        for folder in ([schedule['folder']] if schedule else []) + list(folders):
            if folder and self.folder.findText(folder) < 0:
                self.folder.addItem(folder)
        layout.addWidget(self.folder)
        apps = QHBoxLayout()
        self.claude = QRadioButton(PROVIDER_NAMES['claude'])
        self.codex = QRadioButton(PROVIDER_NAMES['codex'])
        group = QButtonGroup(self)
        for button in (self.claude, self.codex):
            group.addButton(button)
            apps.addWidget(button)
        apps.addStretch(1)
        (self.codex if (schedule or {}).get('provider_id', panel.prefs.get('launch_app')) == 'codex'
         else self.claude).setChecked(True)
        layout.addLayout(apps)
        choices = QHBoxLayout()
        self.model = QComboBox()
        self.effort = QComboBox()
        choices.addWidget(QLabel(text('launch_model', language)))
        choices.addWidget(self.model, 1)
        choices.addWidget(QLabel(text('launch_effort', language)))
        choices.addWidget(self.effort, 1)
        layout.addLayout(choices)
        self._saved = dict(model=(schedule or {}).get('model') or '', effort=(schedule or {}).get('effort') or '')
        self.claude.toggled.connect(lambda _: self._fill_options())
        self.model.currentIndexChanged.connect(lambda _: self._fill_efforts())
        self._fill_options()
        when = QHBoxLayout()
        self.now = QRadioButton(text('todo_ai_now', language))
        self.later = QRadioButton(text('todo_ai_at', language))
        timing = QButtonGroup(self)
        timing.addButton(self.now)
        timing.addButton(self.later)
        self.at = QDateTimeEdit(QDateTime.fromSecsSinceEpoch(int((schedule or {}).get('run_at')
                                                                 or time.time() + 3600)))
        self.at.setCalendarPopup(True)
        self.at.setDisplayFormat('yyyy-MM-dd HH:mm')
        (self.later if schedule and schedule['state'] == 'waiting' else self.now).setChecked(True)
        when.addWidget(self.now)
        when.addWidget(self.later)
        when.addWidget(self.at)
        when.addStretch(1)
        layout.addLayout(when)
        self.error = QLabel('')
        self.error.setStyleSheet('color:#8A2E4A;')
        self.error.setWordWrap(True)
        self.error.hide()
        layout.addWidget(self.error)
        note = QLabel(text('todo_ai_note', language))
        note.setObjectName('muted')
        note.setWordWrap(True)
        layout.addWidget(note)
        row = QHBoxLayout()
        cancel = QPushButton(text('launch_cancel', language))
        cancel.clicked.connect(self.reject)
        ok = QPushButton(text('todo_ai_ok', language))
        ok.setDefault(True)
        ok.clicked.connect(self._ok)
        row.addStretch(1)
        row.addWidget(cancel)
        row.addWidget(ok)
        layout.addLayout(row)

    def _app(self):
        return 'codex' if self.codex.isChecked() else 'claude'

    def _fill_options(self):
        from quick_launch import launch_options
        app = self._app()
        self._models = launch_options(app, self.language)
        saved = self._saved   # A model the other app lacks just falls back to its default.
        self.model.blockSignals(True)
        self.model.clear()
        self.model.addItem(text('launch_model_default', self.language), '')
        for model in self._models:
            self.model.addItem(model['label'], model['id'])
        self.model.setCurrentIndex(max(0, self.model.findData(saved.get('model', ''))))
        self.model.blockSignals(False)
        self._fill_efforts(saved.get('effort', ''))

    def _fill_efforts(self, keep=None):
        from quick_launch import default_efforts
        keep = self.effort.currentData() if keep is None else keep
        model = next((m for m in self._models if m['id'] == self.model.currentData()), None)
        efforts = model['efforts'] if model else default_efforts(self._app())
        self.effort.clear()
        self.effort.addItem(text('launch_effort_default', self.language), '')
        for value, label in efforts:
            self.effort.addItem(label, value)
        self.effort.setCurrentIndex(max(0, self.effort.findData(keep or '')))
        self.effort.setEnabled(bool(efforts))

    def values(self):
        from quick_launch import _clean_folder
        return dict(prompt=self.prompt.toPlainText().strip(), folder=_clean_folder(self.folder.currentText()),
                    provider_id=self._app(), model=self.model.currentData() or '',
                    effort=self.effort.currentData() or '',
                    run_at=None if self.now.isChecked() else float(self.at.dateTime().toSecsSinceEpoch()))

    def _ok(self):
        values = self.values()
        if not values['prompt']:
            self.error.setText(text('launch_need_prompt', self.language))
        elif not values['folder']:
            self.error.setText(text('launch_need_folder', self.language))
        else:
            self.accept()
            return
        self.error.show()


def schedule_badge(schedule, language):
    """Short state shown after a todo's title."""
    if not schedule:
        return ''
    app = PROVIDER_NAMES.get(schedule['provider_id'], '')
    state = schedule['state']
    if state == 'waiting':
        when = datetime.fromtimestamp(schedule['run_at']).strftime('%m-%d %H:%M')
        return text('todo_ai_badge_waiting', language, when=when, app=app)
    return text(f'todo_ai_badge_{state}', language, app=app)
