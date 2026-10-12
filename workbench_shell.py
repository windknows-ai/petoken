"""The workbench in Petoken's own Qt Quick window (2.5).

workbench.WorkbenchWindow keeps all the workbench's logic and its widgets; it is laid out but never
put on the screen. `WorkbenchShell` is the window the person sees (ui/Petoken/Workbench.qml): a
navigation rail with the pages and the project spaces, a greeting banner on the home page, and
each page drawn by the widget mirror (widget_mirror.Mirror), so what is done there is done to the
workbench itself.
"""
from __future__ import annotations

import time

from PySide6.QtCore import Property, QTimer, Signal, Slot

import pet_assets
from quick_ui import MARGIN, HostBridge, QuickWindow, file_url, ui_art
import widget_mirror

PAGES = ('home', 'todos', 'notes', 'projects', 'notifications', 'reports', 'collection', 'guide')
ICONS = dict(home='house', todos='check-square', notes='note', projects='folder-simple', notifications='bell',
             reports='chart-bar', collection='medal', guide='map-trifold', wardrobe='t-shirt', settings='gear-six')


class WorkbenchBridge(HostBridge):
    changed = Signal()
    summaryChanged = Signal()

    def __init__(self, window, workbench):
        super().__init__(window, workbench.panel)
        self.workbench = workbench
        self._clock = QTimer(self)                          # The greeting follows the time of day.
        self._clock.setInterval(60_000)
        self._clock.timeout.connect(self.changed)
        self._clock.start()

    def _mirror_id(self, widget):
        return widget.property('_mirrorId') or '' if widget is not None else ''

    @Property('QVariant', notify=changed)
    def ids(self):
        wb = self.workbench
        return dict(tabs=self._mirror_id(wb.tabs), spaces=self._mirror_id(wb.project_list),
                    status=self._mirror_id(wb.status))

    @Property(str, notify=summaryChanged)
    def summaryText(self):
        """'3 projects · 5 todos · 2 notes' (the page's own pill stays out of the mirror: it is in the title bar)."""
        return self.workbench.summary.text()

    @Property('QVariant', notify=changed)
    def nav(self):
        out = []
        for key in PAGES:
            art = ui_art(f'nav_{key}')
            out.append(dict(key=key, label=self._t(f'wb_{key}'), tip=self._t(f'wb_{key}_tab_tip'), art=art,
                            icon=ICONS[key]))
        return out

    @Property('QVariant', notify=changed)
    def extras(self):
        return [dict(key=key, label=self._t(f'wb_nav_{key}'), art=ui_art(f'nav_{key}'), icon=ICONS[key])
                for key in ('wardrobe', 'settings')]

    @Property(str, notify=changed)
    def title(self):
        return self._t('workbench_open')

    @Property(str, notify=changed)
    def greeting(self):
        hour = time.localtime().tm_hour
        key = ('night' if hour < 5 else 'morning' if hour < 11 else 'noon' if hour < 13 else
               'afternoon' if hour < 18 else 'evening' if hour < 23 else 'night')
        return self._t(f'wb_greet_{key}')

    @Property(str, notify=changed)
    def heading(self):
        return self._t('wb_heading')

    @Property(str, notify=changed)
    def subtitle(self):
        return self._t('wb_subtitle')

    @Property(str, notify=changed)
    def tutorialText(self):
        return self._t('wb_tutorial')

    @Property(str, notify=changed)
    def spacesTitle(self):
        return self._t('wb_spaces')

    @Property(str, notify=changed)
    def herUrl(self):
        """Her on the greeting banner: Codex's drawing when there is one, else her own picture."""
        art = ui_art('hero_her')
        if art:
            return art
        try:
            entry = pet_assets.entry_for('greet_morning')
            frames = pet_assets.existing_frames(entry)
            return file_url(pet_assets._file(frames[0] if frames else entry.path))
        except Exception:
            return ''

    @Slot()
    def tutorial(self):
        self.workbench.open_tutorial()

    @Slot(str)
    def extra(self, key):
        panel = self.panel
        if key == 'wardrobe' and hasattr(panel, 'open_wardrobe'):
            panel.open_wardrobe()
        elif key == 'settings' and hasattr(panel, 'open_settings'):
            QTimer.singleShot(0, panel.open_settings)          # Its own (modal) window, after this click.

    @Slot()
    def close(self):
        self.workbench.close()


class WorkbenchShell(QuickWindow):
    def __init__(self, workbench):
        super().__init__()
        self.workbench = workbench
        self.setWindowTitle(workbench.windowTitle())
        self.setWindowIcon(workbench.windowIcon())
        self.resize(1240 + 2 * MARGIN, 820 + 2 * MARGIN)
        self.setMinimumSize(980, 640)
        self.bridge = WorkbenchBridge(self, workbench)
        workbench.summary.setProperty('mirrorSkip', True)    # Shown in the title bar instead.
        for listing, art in ((workbench.todo_list, 'empty_todos'), (workbench.pending_list, 'empty_todos'),
                             (workbench.notes_list, 'empty_notes'), (workbench.projects_table, 'empty_projects'),
                             (workbench.notify_list, 'empty_notifications'), (workbench.task_list, 'empty_tasks')):
            listing.setProperty('emptyArt', art)              # Her little scene where a list is empty.
        self.mirror = widget_mirror.Mirror(workbench, widget_mirror.images(), self)
        self.mirror.treeChanged.connect(self.bridge.changed)
        self.mirror.valuesChanged.connect(self.bridge.summaryChanged)
        self.view.engine().addImageProvider('mirror', widget_mirror._Shared(widget_mirror.images()))
        self.load('Workbench.qml', bridge=self.bridge, mirror=self.mirror)

    def showEvent(self, event):
        super().showEvent(event)
        self.mirror.timer.start()
        self.mirror.soon()

    def hideEvent(self, event):
        super().hideEvent(event)
        self.mirror.timer.stop()

    def closeEvent(self, event):
        # Closing the window is closing the workbench (which may ask about an unsaved note first).
        if self.workbench.isVisible() and not self.workbench.close():
            event.ignore()
            return
        super().closeEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # The real workbench is laid out at about the size its pages have here.
        self.workbench.resize(max(self.workbench.minimumWidth(), self.width() - 60),
                              max(self.workbench.minimumHeight(), self.height() - 40))


def wanted():
    """The shell replaces the plain window when the app draws its windows in Qt Quick."""
    return widget_mirror._FILTER is not None

