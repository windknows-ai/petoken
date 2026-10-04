"""Native personal workbench; user records are separate from Codex telemetry."""
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, QTimer
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMessageBox, QPlainTextEdit, QPushButton, QSplitter, QTabWidget,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget, QScrollArea, QProgressBar,
)

from localization import text
from pet_assets import sprite_for
import theme
from workbench_store import WorkbenchError


class WorkbenchWindow(QWidget):
    def __init__(self, panel, store):
        super().__init__(panel, Qt.Window)
        self.panel, self.store = panel, store
        self.project_scope = None
        self.note_id = None
        self._baseline = ('', '', None)
        self._projects, self._todos, self._links = [], {}, {}
        self._loading = False
        self._shutdown = False
        self._tutorial_auto_shown = False
        self._captions = []
        self.setObjectName('workbench')
        self.setWindowIcon(panel.windowIcon())
        self.setMinimumSize(680, 460)
        self.resize(980, 700)
        self.setStyleSheet(f'''
            QWidget#workbench {{background:{theme.BG}; color:{theme.INK};}}
            QDialog {{background:{theme.BG};}}
            QWidget {{color:{theme.INK}; font-family:{theme.FONT_UI}; font-size:13px;}}
            QFrame#hero {{background:{theme.SURFACE_TOP}; border:1px solid {theme.BORDER}; border-radius:20px;}}
            QLabel {{background:transparent;}}
            QLabel#heading {{font-size:25px; font-weight:600;}}
            QLabel#muted {{color:{theme.MUTED};}}
            QLabel#section {{font-size:17px; font-weight:600; color:{theme.VIOLET};}}
            QLabel#summary {{background:{theme.CARD}; border-radius:12px; padding:12px; color:{theme.VIOLET};}}
            QTabWidget::pane {{background:{theme.SURFACE_BOTTOM}; border:1px solid {theme.BORDER}; border-radius:12px;}}
            QTabBar::tab {{background:{theme.CONTROL_BG}; padding:11px 18px; margin-right:4px; border-top-left-radius:9px; border-top-right-radius:9px;}}
            QTabBar::tab:selected {{background:{theme.TAB_SELECTED_BG}; color:{theme.INK};}}
            QTabBar::tab:hover {{background:{theme.HOVER_BG};}}
            QListWidget,QTreeWidget,QPlainTextEdit,QLineEdit,QComboBox {{background:{theme.TABLE_BG}; border:1px solid {theme.BORDER_CONTROL}; border-radius:8px; padding:6px; selection-background-color:{theme.TAB_SELECTED_BG};}}
            QListWidget::item {{padding:9px 5px; border-radius:5px;}}
            QListWidget::item:selected,QTreeWidget::item:selected {{background:{theme.TAB_SELECTED_BG};}}
            QPushButton {{background:{theme.CONTROL_BG}; border:1px solid {theme.BORDER_CONTROL}; border-radius:8px; padding:8px 13px;}}
            QPushButton:hover {{background:{theme.HOVER_BG}; border-color:{theme.VIOLET};}}
            QPushButton:focus,QLineEdit:focus,QPlainTextEdit:focus,QComboBox:focus {{border:1px solid {theme.VIOLET};}}
            QPushButton:disabled {{color:{theme.MUTED};}}
            QPushButton#primary {{background:#514674; border-color:{theme.VIOLET};}}
            QCheckBox {{spacing:8px; padding:5px;}}
            QHeaderView::section {{background:{theme.TABLE_HEADER}; color:{theme.INK}; padding:9px; border:0;}}
            QScrollBar:vertical {{background:{theme.BG}; width:12px;}}
            QScrollBar::handle:vertical {{background:{theme.BORDER}; min-height:24px; border-radius:5px;}}
            QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {{height:0;}}
            QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical {{background:{theme.TABLE_BG};}}
            QScrollBar:horizontal {{background:{theme.TABLE_BG}; height:12px;}}
            QScrollBar::handle:horizontal {{background:{theme.BORDER}; min-width:24px; border-radius:5px;}}
            QScrollBar::add-line:horizontal,QScrollBar::sub-line:horizontal {{width:0;}}
            QScrollBar::add-page:horizontal,QScrollBar::sub-page:horizontal {{background:{theme.TABLE_BG};}}
            QAbstractScrollArea::corner {{background:{theme.TABLE_BG};}}
            QSplitter::handle {{background:{theme.DIVIDER};}}
        ''')
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 16, 22, 12)
        root.setSpacing(12)
        hero = QFrame()
        hero.setObjectName('hero')
        header = QHBoxLayout(hero)
        header.setContentsMargins(20, 14, 20, 14)
        avatar = QLabel()
        pixmap = sprite_for('idle')
        if pixmap is not None:
            avatar.setPixmap(pixmap.scaled(68, 68, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        header.addWidget(avatar)
        words = QVBoxLayout()
        words.addWidget(self.caption('wb_heading', 'heading'))
        words.addWidget(self.caption('wb_subtitle', 'muted'))
        header.addLayout(words, 1)
        self.tutorial_button = self.button(header, 'wb_tutorial', self.open_tutorial)
        root.addWidget(hero)
        split = QSplitter()
        sidebar = QWidget()
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(0, 0, 8, 0)
        side.addWidget(self.caption('wb_spaces', 'section'))
        self.project_list = QListWidget()
        self.project_list.setMinimumWidth(155)
        self.project_list.currentItemChanged.connect(self._project_changed)
        side.addWidget(self.project_list, 1)
        side.addWidget(self.caption('wb_local', 'muted'))
        split.addWidget(sidebar)
        self.tabs = QTabWidget()
        split.addWidget(self.tabs)
        split.setStretchFactor(1, 1)
        split.setSizes([185, 730])
        root.addWidget(split, 1)
        self._build_home()
        self._build_todos()
        self._build_notes()
        self._build_projects()
        self.status = QLabel('')
        self.status.setWordWrap(True)
        self.status.setObjectName('muted')
        self.status.hide()
        root.addWidget(self.status)
        self.save_shortcut = QShortcut(QKeySequence.Save, self)
        self.save_shortcut.activated.connect(self.save_note)
        self.tutorial = WorkbenchTutorial(self)
        self.apply_language()

    @property
    def language(self):
        return self.panel.prefs.get('language', 'zh_CN')

    def tr(self, key, **values):
        return text(key, self.language, **values)

    def caption(self, key, style=''):
        label = QLabel()
        label.setWordWrap(True)
        label.setObjectName(style)
        self._captions.append((label, key))
        return label

    def button(self, layout, key, callback, primary=False):
        button = QPushButton()
        if primary:
            button.setObjectName('primary')
        self._captions.append((button, key))
        button.clicked.connect(callback)
        layout.addWidget(button)
        return button

    def page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        self.tabs.addTab(page, '')
        return layout

    def _build_home(self):
        layout = self.page()
        self.summary = QLabel()
        self.summary.setObjectName('summary')
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        columns = QSplitter()
        for key, attr in [('wb_next', 'pending_list'), ('wb_codex_tasks', 'task_list')]:
            card = QWidget()
            body = QVBoxLayout(card)
            body.setContentsMargins(0, 0, 0, 0)
            body.addWidget(self.caption(key, 'section'))
            listing = QListWidget()
            setattr(self, attr, listing)
            body.addWidget(listing, 1)
            hint = self.caption('wb_empty_todos' if attr == 'pending_list' else 'wb_empty_tasks', 'muted')
            setattr(self, attr + '_empty', hint)
            body.addWidget(hint)
            if attr == 'task_list':
                listing.itemSelectionChanged.connect(self._update_actions)
                actions = QHBoxLayout()
                self.task_detail_button = self.button(actions, 'wb_details', self.open_selected_task)
                self.task_link_button = self.button(actions, 'wb_link', self.link_selected_task)
                body.addLayout(actions)
            columns.addWidget(card)
        columns.setSizes([300, 300])
        layout.addWidget(columns, 1)
        self.pending_list.itemDoubleClicked.connect(lambda _: self.tabs.setCurrentIndex(1))
        self.task_list.itemDoubleClicked.connect(lambda _: self.open_selected_task())

    def _build_todos(self):
        layout = self.page()
        layout.addWidget(self.caption('wb_todo_intro', 'muted'))
        add = QHBoxLayout()
        self.todo_input = QLineEdit()
        self.todo_input.setMaxLength(200)
        self.todo_input.returnPressed.connect(self.add_todo)
        self.todo_project = QComboBox()
        add.addWidget(self.todo_input, 1)
        add.addWidget(self.todo_project)
        self.button(add, 'wb_add', self.add_todo, True)
        layout.addLayout(add)
        self.todo_list = QListWidget()
        self.todo_list.itemChanged.connect(self._todo_changed)
        self.todo_list.itemSelectionChanged.connect(self._update_actions)
        layout.addWidget(self.todo_list, 1)
        self.todo_empty = self.caption('wb_empty_todos', 'muted')
        layout.addWidget(self.todo_empty)
        actions = QHBoxLayout()
        self.show_completed = QCheckBox()
        self._captions.append((self.show_completed, 'wb_completed'))
        self.show_completed.setChecked(True)
        self.show_completed.toggled.connect(lambda _: self.refresh())
        actions.addWidget(self.show_completed)
        actions.addStretch()
        self.todo_edit_button = self.button(actions, 'wb_edit', self.edit_todo)
        self.todo_delete_button = self.button(actions, 'wb_delete', self.delete_todo)
        layout.addLayout(actions)

    def _build_notes(self):
        layout = self.page()
        actions = QHBoxLayout()
        self.button(actions, 'wb_new_note', self.new_note, True)
        actions.addStretch()
        self.save_button = self.button(actions, 'wb_save', self.save_note)
        self.note_delete_button = self.button(actions, 'wb_delete', self.delete_note)
        layout.addLayout(actions)
        split = QSplitter()
        self.notes_list = QListWidget()
        # Current-item changes precede mouse selection; guard the committed selection.
        self.notes_list.itemSelectionChanged.connect(self._note_changed)
        self.notes_list.itemSelectionChanged.connect(self._update_actions)
        split.addWidget(self.notes_list)
        editor = QWidget()
        body = QVBoxLayout(editor)
        body.setContentsMargins(6, 0, 0, 0)
        self.note_title = QLineEdit()
        self.note_title.setMaxLength(200)
        self.note_project = QComboBox()
        self.note_body = QPlainTextEdit()
        body.addWidget(self.note_title)
        body.addWidget(self.note_project)
        body.addWidget(self.note_body, 1)
        self.draft_status = QLabel()
        self.draft_status.setObjectName('muted')
        body.addWidget(self.draft_status)
        split.addWidget(editor)
        split.setSizes([180, 460])
        layout.addWidget(split, 1)
        for signal in [self.note_title.textChanged, self.note_body.textChanged,
                       self.note_project.currentIndexChanged]:
            signal.connect(lambda *_: self._draft_changed())

    def _build_projects(self):
        layout = self.page()
        layout.addWidget(self.caption('wb_projects_intro', 'muted'))
        self.projects_table = QTreeWidget()
        self.projects_table.setRootIsDecorated(False)
        self.projects_table.setColumnCount(2)
        self.projects_table.setColumnWidth(0, 180)
        self.projects_table.itemSelectionChanged.connect(self._update_actions)
        layout.addWidget(self.projects_table, 1)
        self.projects_empty = self.caption('wb_empty_projects', 'muted')
        layout.addWidget(self.projects_empty)
        actions = QHBoxLayout()
        self.button(actions, 'wb_new_project', lambda: self.edit_project(), True)
        self.project_edit_button = self.button(actions, 'wb_edit', self.edit_selected_project)
        self.project_folder_button = self.button(actions, 'wb_folder_open', self.open_folder)
        actions.addStretch()
        self.project_delete_button = self.button(actions, 'wb_delete', self.delete_project)
        layout.addLayout(actions)

    def _attempt(self, callback, *args, **kwargs):
        try:
            result = callback(*args, **kwargs)
        except (WorkbenchError, OSError, ValueError):
            self.status.setText(self.tr('wb_error'))
            self.status.show()
            return False, None
        self.status.clear()
        self.status.hide()
        return True, result

    def _combo(self, combo, selected):
        combo.blockSignals(True)
        combo.clear()
        combo.addItem(self.tr('wb_inbox'), None)
        for project in self._projects:
            combo.addItem(project['name'], project['id'])
        index = combo.findData(selected)
        combo.setCurrentIndex(max(0, index))
        combo.blockSignals(False)

    def refresh(self, note_id=None):
        if self._shutdown:
            return
        ok, records = self._attempt(lambda: (self.store.list_projects(),
            self.store.list_todos(), self.store.list_notes(), self.store.task_links()))
        if not ok:
            return
        self._projects, todos, notes, self._links = records
        dirty = self.note_dirty
        self._todos = {r['id']: r for r in todos}
        scope_exists = self.project_scope in (None, '') or any(
            r['id'] == self.project_scope for r in self._projects)
        if not scope_exists:
            self.project_scope = ''
        self._loading = True
        self.project_list.clear()
        for name, identity in [(self.tr('wb_all'), None), (self.tr('wb_inbox'), '')] + [
                (r['name'], r['id']) for r in self._projects]:
            item = QListWidgetItem(name)
            item.setData(Qt.UserRole, identity)
            self.project_list.addItem(item)
            if identity == self.project_scope:
                self.project_list.setCurrentItem(item)
        self._combo(self.todo_project, self.todo_project.currentData())
        # A passive refresh must not rebind a draft to a different project.
        if not dirty:
            self._combo(self.note_project, self.note_project.currentData())
        self.projects_table.clear()
        for project in self._projects:
            item = QTreeWidgetItem([project['name'], project['directory']])
            item.setData(0, Qt.UserRole, project['id'])
            item.setToolTip(1, project['directory'])
            self.projects_table.addTopLevelItem(item)
        self.projects_empty.setVisible(not self._projects)
        self.todo_list.clear()
        self.pending_list.clear()
        scoped = [r for r in todos if self._in_scope(r['project_id'])]
        pending = [r for r in scoped if not r['done']]
        for record in scoped:
            if record['done'] and not self.show_completed.isChecked():
                continue
            item = QListWidgetItem(record['title'])
            item.setData(Qt.UserRole, record['id'])
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if record['done'] else Qt.Unchecked)
            item.setToolTip(record['title'])
            self.todo_list.addItem(item)
        for record in pending:
            item = QListWidgetItem(record['title'])
            item.setData(Qt.UserRole, record['id'])
            self.pending_list.addItem(item)
        self.todo_empty.setVisible(self.todo_list.count() == 0)
        self.pending_list_empty.setVisible(not pending)
        self.notes_list.clear()
        scoped_notes = [r for r in notes if self._in_scope(r['project_id'])]
        target = note_id if note_id is not None else self.note_id
        for record in scoped_notes:
            item = QListWidgetItem(record['title'])
            item.setData(Qt.UserRole, record['id'])
            self.notes_list.addItem(item)
            if record['id'] == target:
                self.notes_list.setCurrentItem(item)
        if not dirty:
            record = next((r for r in scoped_notes if r['id'] == target), None)
            if record is None and scoped_notes:
                record = scoped_notes[0]
                self.notes_list.setCurrentRow(0)
            self._load_note(record)
        self._loading = False
        self.summary.setText(self.tr('wb_summary', projects=len(self._projects),
                                    todos=len(pending), notes=len(scoped_notes)))
        self._draft_changed()
        self.update_tasks()

    def _in_scope(self, project):
        return self.project_scope is None or project == (self.project_scope or None)

    def update_tasks(self):
        if self._shutdown:
            return
        manager = self.panel.task_manager
        rows = [(key, manager.label_text(key, self.language))
                for key in manager.task_identities()
                if key[0] == 'codex' and key in manager._universe
                and self._in_scope(self._links.get(key))]
        fingerprint = tuple(rows), frozenset(manager._ring_staged)
        if fingerprint == getattr(self, '_task_fingerprint', None):
            return
        self._task_fingerprint = fingerprint
        current = self.task_list.currentItem()
        selected = current.data(Qt.UserRole) if current and current.isSelected() else None
        self.task_list.clear()
        for key, title in rows:
            item = QListWidgetItem(title + ' · Codex')
            item.setData(Qt.UserRole, key)
            if key in manager._ring_staged:
                item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
            self.task_list.addItem(item)
            if key == selected:
                self.task_list.setCurrentItem(item)
        self.task_list_empty.setVisible(not rows)
        self._update_actions()

    def _selected_task(self):
        item = self.task_list.currentItem()
        manager = self.panel.task_manager
        if (item and item.isSelected() and item.flags() & Qt.ItemIsEnabled
                and item.data(Qt.UserRole) in manager._universe
                and item.data(Qt.UserRole) not in manager._ring_staged):
            return item
        return None

    def open_selected_task(self):
        item = self._selected_task()
        if item is None:
            return
        self.panel.task_manager.activate_task(item.data(Qt.UserRole), keyboard=True)

    def assign_task(self, identity, project_id):
        if (identity not in self.panel.task_manager._universe
                or identity in self.panel.task_manager._ring_staged):
            return False
        ok, _ = self._attempt(self.store.link_task, *identity, project_id)
        if ok:
            self.refresh()
        return ok

    def link_selected_task(self):
        item = self._selected_task()
        if item is None:
            return
        # Task refresh can delete list items during the modal event loop.
        identity = item.data(Qt.UserRole)
        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr('wb_link'))
        layout = QVBoxLayout(dialog)
        combo = QComboBox()
        self._combo(combo, self._links.get(identity))
        layout.addWidget(combo)
        self._dialog_buttons(dialog, layout)
        if dialog.exec() == QDialog.Accepted:
            self.assign_task(identity, combo.currentData())

    def _project_changed(self, current, previous):
        if not self._loading and current is not None:
            self.select_project(current.data(Qt.UserRole))

    def select_project(self, project_id):
        if project_id != self.project_scope and not self._guard_note():
            self._restore_selection(self.project_list, self.project_scope)
            return False
        self.project_scope = project_id
        self.refresh()
        if project_id:
            self.todo_project.setCurrentIndex(self.todo_project.findData(project_id))
        else:
            self.todo_project.setCurrentIndex(0)
        return True

    @staticmethod
    def _restore_selection(listing, identity):
        listing.blockSignals(True)
        for index in range(listing.count()):
            if listing.item(index).data(Qt.UserRole) == identity:
                listing.setCurrentRow(index)
                break
        listing.blockSignals(False)

    def add_todo(self):
        ok, _ = self._attempt(self.store.create_todo, self.todo_input.text(),
                              self.todo_project.currentData())
        if ok:
            self.todo_input.clear()
            self.refresh()
        return ok

    def _todo_changed(self, item):
        if self._loading:
            return
        record = self._todos.get(item.data(Qt.UserRole))
        if not record:
            return
        done = item.checkState() == Qt.Checked
        ok, _ = self._attempt(self.store.update_todo, record['id'], record['title'],
                              record['project_id'], done)
        if ok:
            self.refresh()
        else:
            self.todo_list.blockSignals(True)
            item.setCheckState(Qt.Checked if record['done'] else Qt.Unchecked)
            self.todo_list.blockSignals(False)

    def _dialog_buttons(self, dialog, layout):
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

    def _record_dialog(self, title, value='', project=None, directory=None, save=None):
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setMinimumWidth(400)
        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        name = QLineEdit(value)
        name.setMaxLength(200)
        form.addRow(self.tr('wb_name'), name)
        extra = QLineEdit(directory) if directory is not None else QComboBox()
        if directory is None:
            self._combo(extra, project)
            form.addRow(self.tr('wb_project'), extra)
        else:
            row = QHBoxLayout()
            row.addWidget(extra, 1)
            browse = QPushButton(self.tr('wb_browse'))
            browse.clicked.connect(lambda: self._browse(extra, dialog))
            row.addWidget(browse)
            form.addRow(self.tr('wb_folder'), row)
        layout.addLayout(form)
        error = QLabel(self.tr('wb_error'))
        error.setWordWrap(True)
        error.hide()
        layout.addWidget(error)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        def submit():
            values = name.text(), extra.text() if directory is not None else extra.currentData()
            if save and self._attempt(save, *values)[0]:
                dialog.accept()
            else:
                error.show()
        buttons.accepted.connect(submit)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        return dialog.exec() == QDialog.Accepted

    def _browse(self, edit, dialog):
        directory = QFileDialog.getExistingDirectory(dialog, self.tr('wb_folder'), edit.text())
        if directory:
            edit.setText(directory)

    def _selected_todo(self):
        item = self.todo_list.currentItem()
        return self._todos.get(item.data(Qt.UserRole)) if item and item.isSelected() else None

    def _update_actions(self):
        if self._loading:
            return
        todo = self._selected_todo()
        project = self._selected_project()
        note = self.notes_list.currentItem()
        selected_note = bool(note and note.isSelected() and note.data(Qt.UserRole) == self.note_id)
        task = self._selected_task()
        for button, available in [
                (self.task_detail_button, bool(task)), (self.task_link_button, bool(task)),
                (self.todo_edit_button, bool(todo)), (self.todo_delete_button, bool(todo)),
                (self.project_edit_button, bool(project)), (self.project_delete_button, bool(project)),
                (self.project_folder_button, bool(project and project['directory'])),
                (self.note_delete_button, selected_note)]:
            button.setVisible(available)
            button.setEnabled(available)
        self.save_button.setVisible(self.note_id is not None)

    def edit_todo(self):
        record = self._selected_todo()
        if not record:
            return
        saved = self._record_dialog(self.tr('wb_edit'), record['title'], record['project_id'],
            save=lambda title, project: self.store.update_todo(record['id'], title, project, record['done']))
        if saved:
            self.refresh()

    def delete_todo(self):
        record = self._selected_todo()
        if record and self._confirm('wb_delete_confirm'):
            if self._attempt(self.store.delete_todo, record['id'])[0]:
                self.refresh()

    @property
    def note_dirty(self):
        return self.note_id is not None and self._draft() != self._baseline

    def _draft(self):
        return self.note_title.text(), self.note_body.toPlainText(), self.note_project.currentData()

    def _draft_changed(self):
        if self._loading:
            return
        self.save_button.setEnabled(self.note_id is not None)
        self._update_actions()
        self.draft_status.setText(self.tr('wb_unsaved' if self.note_dirty else
                                        'wb_saved' if self.note_id else 'wb_empty_notes'))

    def _load_note(self, record):
        self.note_id = record['id'] if record else None
        self.note_title.setText(record['title'] if record else '')
        self.note_body.setPlainText(record['body'] if record else '')
        self._combo(self.note_project, record['project_id'] if record else None)
        self._baseline = self._draft()
        for editor in [self.note_title, self.note_body, self.note_project]:
            editor.setEnabled(record is not None)

    def _guard_note(self):
        if not self.note_dirty:
            return True
        answer = QMessageBox.question(self, self.tr('workbench_open'), self.tr('wb_save_confirm'),
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Cancel)
        if answer == QMessageBox.Save:
            return self.save_note()
        if answer == QMessageBox.Discard:
            ok, record = self._attempt(self.store.get_note, self.note_id)
            if ok:
                self._loading = True
                self._load_note(record)
                self._loading = False
                self._draft_changed()
            return ok
        return False

    def _note_changed(self):
        selected = self.notes_list.selectedItems()
        if not self._loading and selected:
            self.select_note(selected[0].data(Qt.UserRole))

    def select_note(self, identity):
        if identity == self.note_id:
            return True
        if not self._guard_note():
            self._restore_selection(self.notes_list, self.note_id)
            return False
        ok, record = self._attempt(self.store.get_note, identity)
        if ok:
            self._loading = True
            self._load_note(record)
            self._restore_selection(self.notes_list, identity)
            self._loading = False
            self._draft_changed()
        return ok

    def new_note(self):
        if not self._guard_note():
            return False
        ok, record = self._attempt(self.store.create_note, self.tr('wb_untitled'), '', self.project_scope or None)
        if ok:
            self.refresh(note_id=record['id'])
            self.tabs.setCurrentIndex(2)
            self.note_title.setFocus()
            self.note_title.selectAll()
        return ok

    def save_note(self):
        if self.note_id is None:
            return False
        ok, _ = self._attempt(self.store.update_note, self.note_id, *self._draft())
        if ok:
            self._baseline = self._draft()
            self.refresh()
        return ok

    def delete_note(self):
        item = self.notes_list.currentItem()
        if (not item or not item.isSelected() or item.data(Qt.UserRole) != self.note_id
                or not self._confirm('wb_delete_note_confirm')):
            return
        if self._attempt(self.store.delete_note, self.note_id)[0]:
            self._loading = True
            self._load_note(None)
            self._loading = False
            self.refresh()

    def _selected_project(self):
        item = self.projects_table.currentItem()
        return next((r for r in self._projects if item and item.isSelected()
                     and r['id'] == item.data(0, Qt.UserRole)), None)

    def edit_project(self, record=None):
        def save(name, directory):
            if record:
                return self.store.update_project(record['id'], name, directory)
            return self.store.create_project(name, directory)
        saved = self._record_dialog(self.tr('wb_edit' if record else 'wb_new_project'),
                                    record['name'] if record else '',
                                    directory=record['directory'] if record else '', save=save)
        if saved:
            self.refresh()

        return saved

    def edit_selected_project(self):
        record = self._selected_project()
        if record:
            self.edit_project(record)

    def _confirm(self, key):
        return QMessageBox.question(self, self.tr('workbench_open'), self.tr(key),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes

    def delete_project(self):
        record = self._selected_project()
        if record and self._guard_note() and self._confirm('wb_delete_project_confirm'):
            if self._attempt(self.store.delete_project, record['id'])[0]:
                self.refresh()

    def open_folder(self):
        record = self._selected_project()
        if record and record['directory']:
            if not Path(record['directory']).is_dir() or not QDesktopServices.openUrl(
                    QUrl.fromLocalFile(record['directory'])):
                self.status.setText(self.tr('wb_folder_error'))
                self.status.show()

    def apply_language(self):
        self.setWindowTitle(self.tr('workbench_open') + ' · Petoken')
        for widget, key in self._captions:
            widget.setText(self.tr(key))
        for index, key in enumerate(['wb_home', 'wb_todos', 'wb_notes', 'wb_projects']):
            self.tabs.setTabText(index, self.tr(key))
        self.projects_table.setHeaderLabels([self.tr('wb_name'), self.tr('wb_folder')])
        self.todo_input.setPlaceholderText(self.tr('wb_todo_placeholder'))
        self.note_title.setPlaceholderText(self.tr('wb_note_title'))
        self.note_body.setPlaceholderText(self.tr('wb_note_body'))
        for widget, key in [(self.project_list, 'wb_spaces'), (self.todo_input, 'wb_todo_placeholder'),
                            (self.todo_project, 'wb_project'), (self.note_title, 'wb_note_title'),
                            (self.note_body, 'wb_note_body'), (self.note_project, 'wb_project'),
                            (self.notes_list, 'wb_notes'), (self.task_list, 'wb_codex_tasks')]:
            widget.setAccessibleName(self.tr(key))
        self.refresh()
        self.tutorial.apply_language()

    def open_tutorial(self):
        if self._shutdown:
            return
        if self.panel.prefs.get('workbench_tutorial_seen') is True:
            self.tutorial.set_step(0)
        self.tutorial.open_guide()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._tutorial_auto_shown:
            self._tutorial_auto_shown = True
            def first_visit():
                if (not self._shutdown and self.isVisible()
                        and self.panel.prefs.get('workbench_tutorial_seen') is not True):
                    self.open_tutorial()
            QTimer.singleShot(0, self, first_visit)

    def closeEvent(self, event):
        if self._guard_note():
            self.tutorial.hide()
            event.accept()
        else:
            event.ignore()

    def shutdown(self):
        if self._shutdown:
            return True
        if not self.close():
            return False
        self.store.close()
        self._shutdown = True
        return True


class WorkbenchTutorial(QDialog):
    """Nonmodal first-use guide; actions reuse the actual workbench controls."""
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.step = 0
        self.setWindowIcon(owner.windowIcon())
        self.setMinimumSize(440, 360)
        self.resize(500, 440)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(14)
        self.position_label = QLabel()
        self.position_label.setObjectName('section')
        layout.addWidget(self.position_label)
        self.title = QLabel()
        self.title.setObjectName('heading')
        self.title.setWordWrap(True)
        layout.addWidget(self.title)
        self.progress = QProgressBar()
        self.progress.setRange(0, 5)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(5)
        self.progress.setStyleSheet(f'QProgressBar {{border:0; background:{theme.TRACK};}} '
                                   f'QProgressBar::chunk {{background:{theme.VIOLET};}}')
        layout.addWidget(self.progress)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.viewport().setStyleSheet(f'background:{theme.BG};')
        self.body = QLabel()
        self.body.setWordWrap(True)
        self.body.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.body.setMargin(4)
        self.body.setStyleSheet(f'background:{theme.BG};')
        scroll.setWidget(self.body)
        layout.addWidget(scroll, 1)
        self.action = QPushButton()
        self.action.setObjectName('primary')
        self.action.clicked.connect(self.perform_action)
        layout.addWidget(self.action)
        self.hint = QLabel()
        self.hint.setObjectName('muted')
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.hide()
        layout.addWidget(self.error)
        buttons = QHBoxLayout()
        self.skip = QPushButton()
        self.skip.clicked.connect(self.finish)
        buttons.addWidget(self.skip)
        buttons.addStretch()
        self.back = QPushButton()
        self.back.clicked.connect(lambda: self.set_step(self.step - 1))
        buttons.addWidget(self.back)
        self.next = QPushButton()
        self.next.clicked.connect(self.advance)
        buttons.addWidget(self.next)
        layout.addLayout(buttons)

    def apply_language(self):
        tr = self.owner.tr
        self.setWindowTitle(tr('wb_tutorial') + ' · Petoken')
        self.position_label.setText(tr('wb_tutorial_step', n=self.step + 1))
        self.title.setText(tr(f'wb_tutorial_title_{self.step}'))
        self.body.setText(tr(f'wb_tutorial_body_{self.step}'))
        self.action.setText(tr(f'wb_tutorial_action_{self.step}'))
        self.hint.setText(tr('wb_tutorial_hint'))
        self.skip.setText(tr('wb_tutorial_skip'))
        self.back.setText(tr('wb_tutorial_back'))
        self.next.setText(tr('wb_tutorial_done' if self.step == 4 else 'wb_tutorial_next'))
        self.error.setText(tr('settings_save_failed'))
        self.back.setEnabled(self.step > 0)
        self.progress.setValue(self.step + 1)
        for button in [self.skip, self.back, self.next, self.action]:
            button.setAccessibleName(button.text())

    def set_step(self, step):
        self.step = max(0, min(4, step))
        self.apply_language()

    def advance(self):
        if self.step == 4:
            self.finish()
        else:
            self.set_step(self.step + 1)

    def open_guide(self):
        self.apply_language()
        self.show()
        area = self.owner.screen().availableGeometry()
        center = self.owner.frameGeometry().center()
        self.move(max(area.left(), min(center.x() - self.width() // 2, area.right() - self.width() + 1)),
                  max(area.top(), min(center.y() - self.height() // 2, area.bottom() - self.height() + 1)))
        self.raise_()
        self.activateWindow()

    def finish(self):
        prefs = self.owner.panel.prefs
        present = 'workbench_tutorial_seen' in prefs
        previous = prefs.get('workbench_tutorial_seen')
        prefs['workbench_tutorial_seen'] = True
        if self.owner.panel.persist() is False:
            if present:
                prefs['workbench_tutorial_seen'] = previous
            else:
                prefs.pop('workbench_tutorial_seen', None)
            self.error.show()
            return False
        self.error.hide()
        self.hide()
        return True

    def perform_action(self):
        self.hide()
        window = self.owner
        window.raise_()
        if self.step == 1:
            window.tabs.setCurrentIndex(3)
            if not window.edit_project():
                self.open_guide()
        elif self.step == 2:
            window.tabs.setCurrentIndex(1)
            window.todo_input.setFocus()
        elif self.step == 3:
            if not window.new_note():
                self.open_guide()
        else:
            window.tabs.setCurrentIndex(0)
            if self.step == 4:
                window.task_list.setFocus()
