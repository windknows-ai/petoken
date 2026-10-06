"""Native personal workbench; user records are separate from Codex and Claude Code telemetry."""
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, QTimer, QRectF, QSize, QDateTime
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut, QPainter, QPainterPath, QColor, QPen, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMessageBox, QPlainTextEdit, QPushButton, QSplitter, QTabWidget,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget, QScrollArea, QProgressBar,
    QDateTimeEdit,
)

from localization import text
from providers import PROVIDER_NAMES, PROVIDER_REGISTRY
from pet_assets import sprite_for, ASSETS_DIR
import theme
from workbench_store import WorkbenchError
from notifications import KINDS as NOTIFY_KINDS, REPEATS, parse_recap, recap_text

NOTIFY_COLORS = dict(finished='#3E7D61', failed=theme.DANGER_TEXT, needs_approval='#C98A1E',
                     quota_low=theme.VIOLET, reminder=theme.ICE, forecast='#C98A1E',
                     context_full=theme.INK, stuck=theme.DANGER_TEXT, quota_back='#3E7D61')
_DOTS = {}


def _kind_dot(kind):
    """Small coloured dot that marks a notification's type in the list."""
    if kind not in _DOTS:
        pixmap = QPixmap(20, 20)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(NOTIFY_COLORS.get(kind, theme.MUTED)))
        painter.drawEllipse(3, 3, 14, 14)
        painter.end()
        _DOTS[kind] = QIcon(pixmap)
    return _DOTS[kind]

def provider_dot(provider_id, size=10):
    """A small round marker in the provider's star colour (blue / gold)."""
    pixmap = QPixmap(size * 2, size * 2)
    pixmap.setDevicePixelRatio(2)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    ring = theme.star_palette(provider_id)['ring']
    painter.setPen(QPen(QColor(*(round(c * .7) for c in ring)), .8))
    painter.setBrush(QColor(*ring))
    painter.drawEllipse(QRectF(1, 1, size - 2, size - 2))
    painter.end()
    return QIcon(pixmap)


# Providers whose tasks may be linked to projects in the local store.
LINKABLE_PROVIDERS = ('codex', 'claude')


class CompanionPortrait(QWidget):
    """Paint the original portrait once at the target device resolution."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(92, 92)
        self.setAccessibleName('Petoken')
        self.source = sprite_for('idle')
        self._portrait = None
        self._portrait_dpr = None

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(theme.BORDER_SOFT))
        painter.drawRoundedRect(QRectF(4, 7, 84, 82), 24, 24)
        frame = QRectF(4, 3, 84, 82)
        painter.setBrush(QColor(theme.CHECKED_BG))
        painter.setPen(QPen(QColor(theme.BORDER_CONTROL), 1.5))
        painter.drawRoundedRect(frame, 24, 24)
        if self.source is not None:
            target = QRectF(8, 7, 76, 76)
            clip = QPainterPath()
            clip.addRoundedRect(target, 20, 20)
            painter.setClipPath(clip)
            width, height = self.source.width(), self.source.height()
            # A head portrait stays recognizable at this size; retain the full
            # source so moving between DPI scales never enlarges a 68px thumbnail.
            source = QRectF(width * .24, height * .23, width * .65, height * .65)
            dpr = self.devicePixelRatioF()
            if self._portrait_dpr != dpr:
                # Qt's direct pixmap paint downsamples bilinearly. Smooth scaled
                # thumbnails use area filtering, retaining fine lines without
                # speckling; allocate physical pixels for this screen's DPI.
                self._portrait = self.source.copy(source.toAlignedRect()).scaled(
                    round(76 * dpr), round(76 * dpr), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                self._portrait.setDevicePixelRatio(dpr)
                self._portrait_dpr = dpr
            painter.drawPixmap(target.topLeft(), self._portrait)


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
            QFrame#hero {{background:transparent; border:0;}}
            QLabel {{background:transparent;}}
            QLabel#heading {{font-family:{theme.FONT_DISPLAY}; font-size:22px; font-weight:600;}}
            QLabel#muted {{color:{theme.MUTED};}}
            QLabel#section {{font-size:14px; font-weight:600; color:{theme.VIOLET}; padding:2px 0px 4px 2px;}}
            QLabel#summary {{background:{theme.SURFACE_TOP}; border:1px solid {theme.BORDER_SOFT}; border-radius:12px;
                             padding:5px 12px; color:{theme.VIOLET};}}
            QTabWidget::pane {{background:{theme.CARD}; border:1px solid {theme.BORDER}; border-radius:12px;}}
            QTabBar::tab {{background:{theme.TABLE_HEADER}; border:1px solid {theme.BORDER_CONTROL}; padding:8px 12px; margin:5px 5px 0px 0px; border-top-left-radius:10px; border-top-right-radius:10px;}}
            QTabBar::tab:selected {{background:{theme.CARD}; color:{theme.INK}; margin-top:0px; padding-top:13px; border-bottom-color:{theme.CARD};}}
            QTabBar::tab:hover {{background:{theme.HOVER_BG};}}
            QListWidget,QTreeWidget {{background:transparent; border:0; padding:4px; selection-background-color:{theme.TAB_SELECTED_BG}; selection-color:{theme.INK};}}
            QPlainTextEdit,QLineEdit,QComboBox {{background:{theme.TABLE_BG}; border:1px solid {theme.BORDER_CONTROL}; border-radius:10px; padding:6px; selection-background-color:{theme.TAB_SELECTED_BG}; selection-color:{theme.INK};}}
            QListWidget::item {{padding:8px 10px; margin:1px 0px; border-radius:8px; border-left:3px solid transparent;}}
            QTreeWidget::item {{padding:9px 7px; border-bottom:1px solid {theme.DIVIDER};}}
            QListWidget::item:hover,QTreeWidget::item:hover {{background:{theme.HOVER_BG};}}
            QListWidget::item:selected {{background:{theme.TAB_SELECTED_BG}; border-left:3px solid {theme.SELECT_BAR};}}
            QTreeWidget::item:selected {{background:{theme.TAB_SELECTED_BG};}}
            QListWidget::indicator {{width:16px; height:16px; border:1px solid {theme.BORDER_CONTROL}; border-radius:5px; background:{theme.CONTROL_BG};}}
            QListWidget::indicator:checked {{background:{theme.CHECK_BG}; border-color:{theme.VIOLET}; image:url("{ASSETS_DIR.as_posix()}/checkmark.svg");}}
            QPushButton {{background:{theme.CONTROL_BG}; border:1px solid {theme.BORDER_SOFT}; border-bottom:2px solid {theme.BORDER_CONTROL};
                          border-radius:9px; padding:6px 14px; min-height:18px; font-weight:500;}}
            QPushButton:hover {{background:{theme.HOVER_BG}; border-color:{theme.HOVER_BORDER};}}
            QPushButton:pressed {{border-bottom-width:1px; padding-top:7px; background:{theme.HOVER_BG};}}
            QPushButton:focus {{border-color:{theme.VIOLET};}}
            QLineEdit:focus,QPlainTextEdit:focus,QComboBox:focus {{border:1px solid {theme.VIOLET};}}
            QPushButton:disabled {{color:{theme.MUTED}; background:{theme.TABLE_ALT}; border-color:{theme.BORDER_SOFT};}}
            QPushButton#primary {{background:{theme.PRIMARY_FILL}; color:{theme.PRIMARY_TEXT};
                                  border:1px solid {theme.PRIMARY_FILL_PRESSED}; border-bottom:2px solid {theme.PRIMARY_FILL_PRESSED};}}
            QPushButton#primary:hover {{background:{theme.PRIMARY_FILL_HOVER};}}
            QPushButton#primary:pressed {{background:{theme.PRIMARY_FILL_PRESSED}; border-bottom-width:1px; padding-top:7px;}}
            QPushButton#primary:focus {{border-color:{theme.INK};}}
            QPushButton#danger {{color:{theme.DANGER_TEXT}; border-color:{theme.DANGER_BORDER}; border-bottom-color:{theme.DANGER_BORDER};}}
            QPushButton#danger:hover {{background:{theme.DANGER_HOVER_BG}; border-color:{theme.DANGER_TEXT};}}
            QPushButton#danger:pressed {{background:{theme.DANGER_HOVER_BG}; border-bottom-width:1px; padding-top:7px;}}
            QCheckBox {{spacing:8px; padding:5px;}}
            QHeaderView::section {{background:{theme.TABLE_HEADER}; color:{theme.INK}; padding:9px; border:0;}}
            QScrollBar:vertical {{background:transparent; width:9px;}}
            QScrollBar::handle:vertical {{background:{theme.BORDER}; min-height:24px; border-radius:5px;}}
            QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {{height:0;}}
            QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical {{background:transparent;}}
            QScrollBar:horizontal {{background:transparent; height:9px;}}
            QScrollBar::handle:horizontal {{background:{theme.BORDER}; min-width:24px; border-radius:5px;}}
            QScrollBar::add-line:horizontal,QScrollBar::sub-line:horizontal {{width:0;}}
            QScrollBar::add-page:horizontal,QScrollBar::sub-page:horizontal {{background:transparent;}}
            QAbstractScrollArea::corner {{background:transparent;}}
            QSplitter::handle {{background:transparent;}}
            QComboBox {{padding:6px 30px 6px 10px;}}
            QWidget#projectShelf {{background:{theme.SURFACE_TOP}; border:1px solid {theme.BORDER_SOFT}; border-radius:12px;}}
            QListWidget#projectSpaces {{background:transparent; border:0; padding:4px 0px;}}
            QListWidget#projectSpaces::item {{padding:10px 7px; border-radius:7px;}}
            QListWidget#projectSpaces::item:hover {{background:{theme.HOVER_BG};}}
            QListWidget#projectSpaces::item:selected {{background:{theme.TAB_SELECTED_BG}; color:{theme.INK};}}
        ''')
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 16, 22, 12)
        root.setSpacing(12)
        hero = QFrame()
        hero.setObjectName('hero')
        header = QHBoxLayout(hero)
        header.setContentsMargins(0, 4, 0, 8)
        header.setSpacing(14)
        self.avatar = CompanionPortrait()
        header.addWidget(self.avatar)
        words = QVBoxLayout()
        words.setSpacing(4)
        words.addStretch()
        words.addWidget(self.caption('wb_heading', 'heading'))
        words.addWidget(self.caption('wb_subtitle', 'muted'))
        words.addStretch()
        header.addLayout(words, 1)
        self.tutorial_button = self.button(header, 'wb_tutorial', self.open_tutorial)
        root.addWidget(hero)
        split = QSplitter()
        split.setHandleWidth(16)
        sidebar = QWidget()
        sidebar.setObjectName('projectShelf')
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(10, 12, 10, 10)
        side.addWidget(self.caption('wb_spaces', 'section'))
        self.project_list = QListWidget()
        self.project_list.setObjectName('projectSpaces')
        self.project_list.setMinimumWidth(155)
        self.project_list.currentItemChanged.connect(self._project_changed)
        side.addWidget(self.project_list, 1)
        side.addWidget(self.caption('wb_local', 'muted'))
        split.addWidget(sidebar)
        self.tabs = QTabWidget()
        self.tabs.setIconSize(QSize(16, 16))
        split.addWidget(self.tabs)
        split.setStretchFactor(1, 1)
        split.setSizes([185, 730])
        root.addWidget(split, 1)
        self._build_home()
        self._build_todos()
        self._build_notes()
        self._build_projects()
        self._build_notifications()
        for index, name in enumerate(('home', 'todos', 'notes', 'projects', 'notifications')):
            self.tabs.setTabIcon(index, QIcon(str(ASSETS_DIR / f'workbench-{name}.svg')))
        self.status = QLabel('')
        self.status.setWordWrap(True)
        self.status.setObjectName('muted')
        self.status.hide()
        root.addWidget(self.status)
        self.save_shortcut = QShortcut(QKeySequence.Save, self)
        self.save_shortcut.activated.connect(self.save_note)
        # Lists elide long titles instead of growing a horizontal scrollbar.
        for listing in self.findChildren(QListWidget):
            listing.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            listing.setTextElideMode(Qt.ElideRight)
            # No dotted/dark focus frame around the clicked row.
            style = 'QListWidget { outline: 0px; }'
            if listing is not self.project_list:
                # Rows share one colour; a divider tells them apart.
                style += f' QListWidget::item {{ border-bottom: 1px solid {theme.DIVIDER}; }}'
            listing.setStyleSheet(style)
        self.projects_table.setStyleSheet('QTreeWidget { outline: 0px; }')
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

    def button(self, layout, key, callback, primary=False, danger=False):
        button = QPushButton()
        button.setCursor(Qt.PointingHandCursor)
        if primary:
            button.setObjectName('primary')
        elif danger:
            button.setObjectName('danger')
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
        self.summary.setWordWrap(False)  # One line: the pill sizes to its text.
        layout.addWidget(self.summary, 0, Qt.AlignLeft)  # A compact pill, not a full-width bar.
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
        self.button(add, 'wb_add_todo', lambda: self.add_todo(), True)
        add.addStretch()
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
        self.todo_delete_button = self.button(actions, 'wb_delete', self.delete_todo, danger=True)
        layout.addLayout(actions)

    def _build_notes(self):
        layout = self.page()
        actions = QHBoxLayout()
        # A lambda: clicked(bool) would otherwise arrive as the note title.
        self.new_note_button = self.button(actions, 'wb_new_note', lambda: self.new_note())
        actions.addStretch()
        # While editing, saving is the main action; a new note is secondary.
        self.save_button = self.button(actions, 'wb_save', self.save_note, True)
        self.note_delete_button = self.button(actions, 'wb_delete', self.delete_note, danger=True)
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
        self.projects_table.setUniformRowHeights(True)
        self.projects_table.setWordWrap(False)
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
        self.project_delete_button = self.button(actions, 'wb_delete', self.delete_project, danger=True)
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
        # A passive refresh must not rebind a draft to a different project.
        if not dirty:
            self._combo(self.note_project, self.note_project.currentData())
        self.projects_table.clear()
        for project in self._projects:
            item = QTreeWidgetItem([project['name'], project['directory']])
            item.setData(0, Qt.UserRole, project['id'])
            item.setToolTip(0, project['name'])
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
        self.refresh_notifications()

    # --- V1.6 notifications ---------------------------------------------
    def _build_notifications(self):
        layout = self.page()
        self.notifications_tab = self.tabs.count() - 1
        layout.addWidget(self.caption('wb_notify_intro', 'muted'))
        top = QHBoxLayout()
        self.notify_filter = QComboBox()
        for key in (None,) + NOTIFY_KINDS:
            self.notify_filter.addItem('', key)
        self.notify_filter.currentIndexChanged.connect(lambda _: self.refresh_notifications())
        top.addWidget(self.notify_filter)
        top.addStretch()
        layout.addLayout(top)
        self.notify_list = QListWidget()
        self.notify_list.setObjectName('notifyList')
        # Rows are told apart by a coloured dot per type and a divider line.
        self.notify_list.setIconSize(QSize(10, 10))
        self.notify_list.itemDoubleClicked.connect(self._open_notice_item)
        layout.addWidget(self.notify_list, 3)
        self.notify_empty = self.caption('wb_notify_empty', 'muted')
        layout.addWidget(self.notify_empty)
        header = QHBoxLayout()
        header.addWidget(self.caption('wb_reminders', 'heading'))
        header.addStretch()
        self.button(header, 'wb_add_reminder', lambda: self.add_reminder(), True)
        layout.addLayout(header)
        self.reminder_list = QListWidget()
        self.reminder_list.setMinimumHeight(70)
        self.reminder_list.itemSelectionChanged.connect(self._reminder_selected)
        layout.addWidget(self.reminder_list, 1)
        actions = QHBoxLayout()
        actions.addStretch()
        # Like todos: Delete appears only once a reminder is selected.
        self.reminder_delete_button = self.button(actions, 'wb_delete', self.delete_reminder, danger=True)
        layout.addLayout(actions)
        self._reminder_selected()

    def show_notifications(self):
        self.tabs.setCurrentIndex(self.notifications_tab)
        self.refresh_notifications()
        self.show()
        self.raise_()

    def _when(self, at):
        return datetime.fromtimestamp(at).strftime('%m-%d %H:%M')

    def refresh_notifications(self):
        center = getattr(self.panel, 'notifications', None)
        if self._shutdown or center is None:
            return
        # Keep the reader's place: refreshing must not jump back to the top.
        scroll = self.notify_list.verticalScrollBar().value()
        current = self.notify_list.currentItem()
        selected = (current.data(Qt.UserRole) or {}).get('dedupe') if current else None
        self.notify_list.clear()
        for event in center.store.list_events(self.notify_filter.currentData()):
            provider = PROVIDER_NAMES.get(event['provider'], '')
            kind = self.tr(f"notify_kind_{event['kind']}")
            detail = event['detail'] if event['kind'] in ('failed', 'reminder') else (
                f"{event['detail']}%" if event['kind'] in ('quota_low', 'context_full') else '')
            if event['kind'] == 'finished':
                detail = recap_text(event['detail'], self.language, getattr(self.panel, 'currency', 'USD'),
                                    (getattr(self.panel, 'fx', None) or {}).get('rates'))
            parts = [self._when(event['at']), provider, kind, event['project'], detail]
            item = QListWidgetItem(_kind_dot(event['kind']), ' · '.join(part for part in parts if part))
            item.setData(Qt.UserRole, event)
            if event['kind'] in ('needs_approval', 'stuck', 'context_full'):
                item.setToolTip(self.tr('wb_notify_open_hint'))
            elif (parse_recap(event['detail']) or {}).get('names'):
                item.setToolTip('\n'.join(parse_recap(event['detail'])['names']))
            self.notify_list.addItem(item)
            if selected and event['dedupe'] == selected:
                self.notify_list.setCurrentItem(item)
        self.notify_list.verticalScrollBar().setValue(scroll)
        self.notify_empty.setVisible(self.notify_list.count() == 0)
        reminder = self.reminder_list.currentItem()
        reminder_id = reminder.data(Qt.UserRole) if reminder and reminder.isSelected() else None
        self.reminder_list.clear()
        days = self.tr('wb_weekday_names').split(',')
        for row in center.store.list_reminders():
            time_text = f"{row['minute'] // 60:02}:{row['minute'] % 60:02}"
            if row['repeat'] == 'once':
                when = f"{row['day']} {time_text}"
            elif row['repeat'] == 'daily':
                when = self.tr('wb_every_day', time=time_text)
            else:
                when = self.tr('wb_every_week', day=days[row['weekday']], time=time_text)
            todo = (getattr(self, '_todos', {}) or {}).get(row['todo_id'])
            text_ = ' · '.join(part for part in (when, row['title'], todo and todo['title']) if part)
            if row['next_at'] is None:
                text_ += ' · ' + self.tr('wb_reminder_done')
            item = QListWidgetItem(text_)
            item.setData(Qt.UserRole, row['id'])
            self.reminder_list.addItem(item)
            if row['id'] == reminder_id:
                self.reminder_list.setCurrentItem(item)
        self._reminder_selected()

    def _reminder_selected(self):
        item = self.reminder_list.currentItem()
        available = bool(item and item.isSelected())
        self.reminder_delete_button.setVisible(available)
        self.reminder_delete_button.setEnabled(available)

    def _open_notice_item(self, item):
        """Only a pending approval whose task still runs is worth opening;
        everything else is history, and the list stays where it is."""
        event = item.data(Qt.UserRole) or {}
        identity = (event.get('provider'), event.get('task_key'))
        if event.get('kind') == 'needs_approval' and identity in self.panel.task_manager._universe:
            self.panel.open_notice(event)

    def _reminder_dialog(self):
        """Content, repeat, time and linked todo, or None when cancelled."""
        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr('wb_add_reminder'))
        dialog.setMinimumWidth(420)
        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        title = QLineEdit()
        title.setMaxLength(200)
        title.setPlaceholderText(self.tr('wb_reminder_placeholder'))
        repeat = QComboBox()
        for value in REPEATS:
            repeat.addItem(self.tr(f'wb_repeat_{value}'), value)
        when = QDateTimeEdit(QDateTime.currentDateTime().addSecs(3600))
        when.setDisplayFormat('yyyy-MM-dd HH:mm')
        when.setCalendarPopup(True)
        todo = QComboBox()
        todo.addItem(self.tr('wb_reminder_no_todo'), None)
        for record in (getattr(self, '_todos', None) or {}).values():
            if not record.get('done'):
                todo.addItem(record['title'], record['id'])
        form.addRow(self.tr('wb_todo_content'), title)
        form.addRow(self.tr('wb_reminder_repeat'), repeat)
        form.addRow(self.tr('wb_reminder_time'), when)
        form.addRow(self.tr('wb_reminder_todo'), todo)
        layout.addLayout(form)
        error = QLabel()
        error.setWordWrap(True)
        error.hide()
        layout.addWidget(error)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        result = {}

        def submit():
            moment = when.dateTime().toPython()
            ok = self.add_reminder(title.text(), repeat.currentData(), moment, todo.currentData())
            if ok:
                result['ok'] = True
                dialog.accept()
            else:
                error.setText(self.tr('wb_reminder_past' if title.text().strip() else 'wb_reminder_empty'))
                error.show()
        buttons.accepted.connect(submit)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()
        return bool(result)

    def add_reminder(self, title=None, repeat='once', when=None, todo_id=None):
        """Add opens a dialog; values passed in are added directly."""
        center = getattr(self.panel, 'notifications', None)
        if center is None:
            return False
        if title is None:
            return self._reminder_dialog()
        if not (title or '').strip() or when is None:
            return False
        try:
            center.store.add_reminder(title, repeat, when.hour * 60 + when.minute,
                                      weekday=when.weekday() if repeat == 'weekly' else None,
                                      day=when.strftime('%Y-%m-%d') if repeat == 'once' else None,
                                      todo_id=todo_id)
        except ValueError:
            return False
        self.refresh_notifications()
        return True

    def delete_reminder(self):
        item = self.reminder_list.currentItem()
        center = getattr(self.panel, 'notifications', None)
        if item is None or center is None:
            return
        center.store.delete_reminder(item.data(Qt.UserRole))
        self.refresh_notifications()

    def _in_scope(self, project):
        return self.project_scope is None or project == (self.project_scope or None)

    def update_tasks(self):
        if self._shutdown:
            return
        manager = self.panel.task_manager
        rows = [(key, manager.label_text(key, self.language))
                for key in manager.task_identities()
                if key[0] in PROVIDER_REGISTRY and key in manager._universe
                and self._in_scope(self._links.get(key))]
        fingerprint = tuple(rows), frozenset(manager._ring_staged)
        if fingerprint == getattr(self, '_task_fingerprint', None):
            return
        self._task_fingerprint = fingerprint
        current = self.task_list.currentItem()
        selected = current.data(Qt.UserRole) if current and current.isSelected() else None
        self.task_list.clear()
        for key, title in rows:
            item = QListWidgetItem(provider_dot(key[0]), title + ' · ' + PROVIDER_NAMES.get(key[0], key[0]))
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
        if (identity[0] not in LINKABLE_PROVIDERS
                or identity not in self.panel.task_manager._universe
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
        return True

    @staticmethod
    def _restore_selection(listing, identity):
        listing.blockSignals(True)
        for index in range(listing.count()):
            if listing.item(index).data(Qt.UserRole) == identity:
                listing.setCurrentRow(index)
                break
        listing.blockSignals(False)

    def add_todo(self, title=None, project=None):
        """Add opens a dialog: write, confirm, then the todo is added.
        A title passed in (tests, scripts) is added directly."""
        if title is None:
            saved = self._record_dialog(self.tr('wb_add_todo'), '', self.project_scope or None,
                                        save=self.store.create_todo, label='wb_todo_content')
            if saved:
                self.refresh()
            return saved
        ok, _ = self._attempt(self.store.create_todo, title, project)
        if ok:
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

    def _record_dialog(self, title, value='', project=None, directory=None, save=None, label='wb_name'):
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setMinimumWidth(400)
        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        name = QLineEdit(value)
        name.setMaxLength(200)
        form.addRow(self.tr(label), name)
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
        linkable = bool(task and task.data(Qt.UserRole)[0] in LINKABLE_PROVIDERS)
        for button, available in [
                (self.task_detail_button, bool(task)), (self.task_link_button, linkable),
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

    def _note_dialog(self):
        """Title, project and text for a new note, or None when cancelled."""
        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr('wb_new_note'))
        dialog.setMinimumWidth(460)
        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        title = QLineEdit()
        title.setMaxLength(200)
        title.setPlaceholderText(self.tr('wb_note_title'))
        project = QComboBox()
        self._combo(project, self.project_scope or None)
        body = QPlainTextEdit()
        body.setPlaceholderText(self.tr('wb_note_body'))
        form.addRow(self.tr('wb_name'), title)
        form.addRow(self.tr('wb_project'), project)
        layout.addLayout(form)
        layout.addWidget(body, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(lambda: dialog.accept() if title.text().strip() else title.setFocus())
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.Accepted:
            return None
        return title.text().strip(), body.toPlainText(), project.currentData()

    def new_note(self, title=None, body='', project=None):
        """Add opens a dialog: write, confirm, then the note is added."""
        if not self._guard_note():
            return False
        if title is None:
            values = self._note_dialog()
            if values is None:
                return False
            title, body, project = values
        else:
            project = project if project is not None else (self.project_scope or None)
        ok, record = self._attempt(self.store.create_note, title, body, project)
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
        for index, key in enumerate(['wb_home', 'wb_todos', 'wb_notes', 'wb_projects', 'wb_notifications']):
            self.tabs.setTabText(index, self.tr(key))
        self.projects_table.setHeaderLabels([self.tr('wb_name'), self.tr('wb_folder')])
        for index, key in enumerate(('wb_notify_all',) + tuple(f'notify_kind_{k}' for k in NOTIFY_KINDS)):
            self.notify_filter.setItemText(index, self.tr(key))
        self.note_title.setPlaceholderText(self.tr('wb_note_title'))
        self.note_body.setPlaceholderText(self.tr('wb_note_body'))
        for widget, key in [(self.project_list, 'wb_spaces'), (self.note_title, 'wb_note_title'),
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
            if not window.add_todo():
                self.open_guide()
        elif self.step == 3:
            if not window.new_note():
                self.open_guide()
        else:
            window.tabs.setCurrentIndex(0)
            if self.step == 4:
                window.task_list.setFocus()
