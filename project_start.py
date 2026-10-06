"""Project start presets and the continuation card (2.0).

A preset says how a project starts work: which app, folder, model, effort
and opening prompt. "Start" opens a terminal with it in one click; the
latest "where to continue" note is added to the prompt, so the AI picks up
where you left off.

The continuation card answers "where was I?" when you come back to a
project: your last note, the last AI task, open todos, todos the AI did not
finish, and the first lines of the project's own HANDOFF.md if it has one.
It appears beside the pet (she holds it up) when a task starts in a project
you have not worked on for a while, or when you start it from the
workbench, and it can be switched off in Settings.
"""
from __future__ import annotations

import re
import time
from pathlib import Path

from datetime import datetime

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import (QApplication, QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QPushButton, QVBoxLayout, QWidget)

import theme
from approval_card import GAP, STYLE
from localization import text
from providers import PROVIDER_NAMES
from todo_ai import GiveToAiDialog

RETURN_GAP_S = 4 * 3600         # Away from a project this long counts as coming back.
HANDOFF_LINES = 4
HANDOFF_FILES = ('HANDOFF.md', 'handoff.md', 'docs/HANDOFF.md')


class ProjectPresetDialog(GiveToAiDialog):
    """The give-to-AI form without a time: how this project starts."""

    def __init__(self, parent, panel, project, preset=None, folders=()):
        start = dict(preset or {}, state='', run_at=None)
        if not preset:
            start = dict(provider_id=panel.prefs.get('launch_app') or 'claude',
                         folder=project.get('directory') or '', prompt='', state='', run_at=None)
        if project.get('directory'):
            start['folder'] = project['directory']
        folders = ([project['directory']] if project.get('directory') else []) + list(folders)
        super().__init__(parent, panel, dict(title=''), start, folders)
        language = self.language
        if project.get('directory'):
            # One folder per project: the one set under Edit, never a stale copy.
            self.folder.hide()
            self.folder_label.setText(text('preset_folder_fixed', language, folder=project['directory']))
            self.folder_label.setWordWrap(True)
        self.setWindowTitle(text('preset_title', language, project=project['name']))
        self.prompt_label.setText(text('preset_prompt', language))
        self.prompt.setPlainText((preset or {}).get('prompt') or '')
        self.prompt.setPlaceholderText(text('preset_default_prompt', language))
        self.when.hide()
        self.note.setText(text('preset_note', language))
        self.ok_button.setText(text('preset_save', language))

    def _ok(self):
        if not self.values()['folder']:
            self.error.setText(text('launch_need_folder', self.language))
            self.error.show()
            return
        self.accept()


def opening_prompt(preset_prompt, handoff, language):
    """The preset's prompt (or a default) plus the latest note, if any."""
    prompt = (preset_prompt or '').strip() or text('preset_default_prompt', language)
    if handoff:
        prompt += '\n\n' + text('preset_handoff_line', language, note=handoff['body'].strip())
    return prompt


def start_project(panel, store, project, starter=None, builder=None):
    """Open a terminal for ``project``; returns None, or an error text key."""
    from quick_launch import _clean_folder, build_command, remember_folder
    import claude_launch
    language = panel.prefs.get('language')
    preset = store.get_preset(project['id']) or {}
    app = preset.get('provider_id') or panel.prefs.get('launch_app') or 'claude'
    folder = _clean_folder(project.get('directory') or preset.get('folder') or '')
    if not folder:
        return 'preset_need_folder'
    prompt = opening_prompt(preset.get('prompt'), store.latest_handoff(project['id']), language)
    try:
        argv = (builder or build_command)(app, folder, prompt, model=preset.get('model') or None,
                                          effort=preset.get('effort') or None)
        (starter or claude_launch.launch)(argv)
    except ValueError:
        return 'launch_bad_choice' if preset.get('model') or preset.get('effort') else 'launch_need_folder'
    except (RuntimeError, OSError):
        return 'launch_failed'
    remember_folder(panel.prefs, folder)
    seen = dict(panel.prefs.get('project_seen') or {})
    seen[project['id']] = time.time()
    panel.prefs['project_seen'] = seen
    pet = getattr(panel, 'pet', None)
    if pet is not None:
        pet.interact('ready_go', 3)
    return None


def read_handoff_md(directory, lines=HANDOFF_LINES):
    """The first meaningful lines of a project's HANDOFF.md, markdown removed."""
    if not directory:
        return []
    for name in HANDOFF_FILES:
        path = Path(directory) / name
        try:
            if not path.is_file() or path.stat().st_size > 2_000_000:
                continue
            raw = path.read_text(encoding='utf-8', errors='replace')
        except OSError:
            continue
        out = []
        for line in raw.splitlines():
            line = re.sub(r'^\s*(#+|[-*+]|\d+[.)]|>)\s*', '', line)
            line = re.sub(r'[*_`]+', '', line).strip()
            if not line or line.startswith('<!--') or set(line) <= set('-=|: '):
                continue
            out.append(line[:140])
            if len(out) >= lines:
                break
        return out
    return []


def continuation(store, project, history=(), now=None):
    """What the card shows for ``project``; None when there is nothing to say."""
    now = time.time() if now is None else now
    note = store.latest_handoff(project['id'])
    todos = store.list_todos(project['id'], include_completed=False)
    schedules = {s['todo_id']: s for s in store.list_schedules(('failed', 'missed'))}
    unfinished = [t['title'] for t in todos if t['id'] in schedules]
    names = {project['name'].lower()}
    if project.get('directory'):
        names.add(Path(project['directory']).name.lower())
    last = next((row for row in history if (row.get('project') or '').lower() in names), None)
    info = dict(project=project, note=note['body'] if note else '', note_at=note['created_at'] if note else '',
                note_id=note['id'] if note else None,
                todos=[t['title'] for t in todos], unfinished=unfinished,
                last_task=dict(title=last.get('title') or '', provider=last.get('provider'),
                               at=last.get('finished_at') or last.get('started_at')) if last else None,
                handoff_md=read_handoff_md(project.get('directory')))
    if not (info['note'] or info['todos'] or info['last_task'] or info['handoff_md']):
        return None
    return info


def _epoch(stamp):
    """An ISO time from the store as epoch seconds (None when unreadable)."""
    try:
        return datetime.fromisoformat(stamp).timestamp()
    except (TypeError, ValueError):
        return None


def _ago(at, now, language):
    if isinstance(at, str):
        at = _epoch(at)
    if not at:
        return ''
    minutes = max(1, int((now - at) // 60))
    if minutes < 60:
        return text('ago_minutes', language, n=minutes)
    if minutes < 48 * 60:
        return text('ago_hours', language, n=minutes // 60)
    return text('ago_days', language, n=minutes // 1440)


class ContinuationCard(QWidget):
    """'Where was I?' beside the pet, with a box for the next note."""

    start = Signal(dict)
    note_saved = Signal(dict, str)
    note_deleted = Signal(dict, str)      # project, note id
    history = Signal(dict)

    def __init__(self, language, info, now=None):
        super().__init__(None)
        self.language = language
        self.info = info
        now = time.time() if now is None else now
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setStyleSheet(STYLE)
        self.setFixedWidth(300)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        frame = QFrame()
        frame.setObjectName('approval')
        outer.addWidget(frame)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(5)
        self.title = QLabel(text('handoff_title', language, project=info['project']['name']))
        self.title.setObjectName('title')
        self.title.setWordWrap(True)
        layout.addWidget(self.title)
        # Your own note comes first and stands out: it is what you meant to remember.
        self.note_box = QFrame()
        self.note_box.setObjectName('note')
        self.note_box.setStyleSheet(f'QFrame#note {{ background:{theme.BADGE_BG}; border:1px solid {theme.VIOLET};'
                                    ' border-radius:8px; }')
        box = QVBoxLayout(self.note_box)
        box.setContentsMargins(9, 7, 9, 7)
        box.setSpacing(3)
        self.note_heading = QLabel()
        self.note_heading.setObjectName('muted')
        box.addWidget(self.note_heading)
        self.note_text = QLabel()
        self.note_text.setWordWrap(True)
        self.note_text.setStyleSheet(f'font-size:13px; font-weight:600; color:{theme.VIOLET};')
        box.addWidget(self.note_text)
        links = QHBoxLayout()
        links.setSpacing(12)
        self.delete_button = QPushButton(text('handoff_delete', language))
        self.delete_button.setObjectName('link')
        self.delete_button.clicked.connect(self._delete)
        self.history_button = QPushButton(text('handoff_history', language))
        self.history_button.setObjectName('link')
        self.history_button.clicked.connect(lambda: self.history.emit(self.info['project']))
        links.addWidget(self.delete_button)
        links.addWidget(self.history_button)
        links.addStretch(1)
        box.addLayout(links)
        layout.addWidget(self.note_box)
        self._now = now
        self.set_note(dict(id=info.get('note_id'), body=info['note'], created_at=info.get('note_at'))
                      if info['note'] else None)
        lines = []
        task = info.get('last_task')
        if task:
            lines.append(text('handoff_last_task', language, app=PROVIDER_NAMES.get(task['provider'], ''),
                              title=task['title'] or '—', ago=_ago(task['at'], now, language)))
        if info['unfinished']:
            lines.append(text('handoff_unfinished', language, names=', '.join(info['unfinished'][:3])))
        if info['todos']:
            lines.append(text('handoff_todos', language, count=len(info['todos']),
                              names=', '.join(info['todos'][:3])))
        self.lines = QLabel('\n'.join('· ' + line for line in lines))
        self.lines.setWordWrap(True)
        self.lines.setVisible(bool(lines))
        layout.addWidget(self.lines)
        if info['handoff_md']:
            md = QLabel(text('handoff_md', language) + '\n' + '\n'.join(info['handoff_md']))
            md.setObjectName('summary')
            md.setWordWrap(True)
            layout.addWidget(md)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText(text('handoff_placeholder', language))
        self.edit.returnPressed.connect(self._save)
        layout.addWidget(self.edit)
        row = QHBoxLayout()
        self.save_button = QPushButton(text('handoff_save', language))
        self.save_button.clicked.connect(self._save)
        row.addWidget(self.save_button)
        row.addStretch(1)
        close = QPushButton(text('focus_card_close', language))
        close.clicked.connect(self.close)
        self.start_button = QPushButton(text('preset_start', language))
        self.start_button.setObjectName('allow')
        self.start_button.clicked.connect(lambda: (self.start.emit(info['project']), self.close()))
        row.addWidget(close)
        row.addWidget(self.start_button)
        layout.addLayout(row)
        self.adjustSize()

    def set_note(self, note):
        """Show ``note`` (a handoff record) at the top, or hide the box."""
        self.note = note
        self.note_box.setVisible(bool(note))
        if note:
            self.note_heading.setText(text('handoff_note_heading', self.language,
                                           ago=_ago(note.get('created_at'), time.time(), self.language)
                                           or text('ago_minutes', self.language, n=1)))
            self.note_text.setText(note['body'])
            self.delete_button.setVisible(bool(note.get('id')))
        self.adjustSize()

    def _delete(self):
        if self.note and self.note.get('id'):
            self.note_deleted.emit(self.info['project'], self.note['id'])

    def _save(self):
        body = self.edit.text().strip()
        if body:
            self.note_saved.emit(self.info['project'], body)
            self.edit.clear()
            self.edit.setPlaceholderText(text('handoff_saved', self.language))

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


class HandoffHistory(QDialog):
    """Every note left for a project, newest first, with delete."""

    def __init__(self, parent, language, store, project):
        super().__init__(parent)
        self.store, self.project, self.language = store, project, language
        self.setWindowTitle(text('handoff_history_title', language, project=project['name']))
        self.setMinimumSize(420, 320)
        layout = QVBoxLayout(self)
        self.listing = QListWidget()
        self.listing.setWordWrap(True)
        layout.addWidget(self.listing, 1)
        row = QHBoxLayout()
        self.delete_button = QPushButton(text('handoff_history_delete', language))
        self.delete_button.clicked.connect(self.delete_selected)
        row.addWidget(self.delete_button)
        row.addStretch(1)
        close = QPushButton(text('focus_card_close', language))
        close.clicked.connect(self.accept)
        row.addWidget(close)
        layout.addLayout(row)
        self.refresh()

    def refresh(self):
        self.listing.clear()
        try:
            notes = self.store.list_handoffs(self.project['id'])
        except Exception:
            notes = []
        for note in notes:
            when = _epoch(note['created_at'])
            stamp = datetime.fromtimestamp(when).strftime('%Y-%m-%d %H:%M') if when else ''
            item = QListWidgetItem(f"{stamp}\n{note['body']}")
            item.setData(Qt.UserRole, note['id'])
            self.listing.addItem(item)
        if not notes:
            empty = QListWidgetItem(text('handoff_history_empty', self.language))
            empty.setFlags(Qt.NoItemFlags)
            self.listing.addItem(empty)
        self.delete_button.setEnabled(bool(notes))

    def delete_selected(self):
        item = self.listing.currentItem()
        if item is None or not item.data(Qt.UserRole):
            return
        try:
            self.store.delete_handoff(item.data(Qt.UserRole))
        except Exception:
            return
        self.refresh()


def match_project(projects, name):
    """The workbench project a task's project name belongs to, or None."""
    if not name:
        return None
    key = name.lower()
    for project in projects:
        if project['name'].lower() == key or (project.get('directory')
                                              and Path(project['directory']).name.lower() == key):
            return project
    return None


class ContinuationWatcher:
    """Spots a task starting in a project you come back to."""

    def __init__(self, panel):
        self.panel = panel
        self.known = None          # Task keys seen in the previous snapshot.

    def observe(self, tasks, now=None):
        """Returns the project to show a card for, or None."""
        now = time.time() if now is None else now
        current = {(t.get('provider_id'), t.get('task_key')): t for t in tasks or []}
        if self.known is None:
            self.known = set(current)
            return None             # A first snapshot is not "starting" anything.
        fresh = [task for key, task in current.items() if key not in self.known]
        self.known = set(current)
        if not fresh or not self.panel.prefs.get('continuation_card', True):
            return None
        store = self.panel.workbench_store()
        if store is None:
            return None
        try:
            projects = store.list_projects()
        except Exception:
            return None
        seen = dict(self.panel.prefs.get('project_seen') or {})
        chosen = None
        for task in fresh:
            project = match_project(projects, (task.get('display') or {}).get('project'))
            if project is None:
                continue
            last = seen.get(project['id'])
            seen[project['id']] = now
            if chosen is None and (last is None or now - last >= RETURN_GAP_S):
                chosen = project
        self.panel.prefs['project_seen'] = seen
        return chosen
