"""Every Petoken form, drawn in Qt Quick (2.5).

Petoken's settings, dialogs and workbench pages are built from ordinary widgets, and their logic
(what a choice changes, what Save checks, what a list holds) lives in those widgets. A `Mirror`
reads such a widget tree (its layouts, labels, buttons, fields, lists) and offers it to QML,
which draws it in Petoken's look (ui/Petoken/mirror). What the person does there is done to the
real widgets (a click is a click, typing sets the text and sends the same signals), so all the
logic stays where it was. The real window is laid out but never put on the screen
(WA_DontShowOnScreen); its mirror window is what the person sees.

`install(app)` does this for every dialog the app opens (Settings, giving a todo to the AI,
reviews, message boxes...). Native file pickers keep their own system window.
"""
from __future__ import annotations

import hashlib
import re
import weakref

import shiboken6
from PySide6.QtCore import (QDateTime, QEvent, QObject, QPoint, QPointF, QSize, Qt, QTimer, Property,
                            Signal, Slot)
from PySide6.QtGui import QDesktopServices, QImage, QMouseEvent, QRegion, QWheelEvent
from PySide6.QtQuick import QQuickImageProvider
from PySide6.QtWidgets import (QAbstractButton, QAbstractSpinBox, QBoxLayout, QCheckBox, QComboBox,
                               QDateTimeEdit, QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog,
                               QFormLayout, QFrame, QGridLayout, QGroupBox, QLabel, QLineEdit,
                               QListWidget, QPlainTextEdit, QProgressBar, QPushButton, QRadioButton,
                               QScrollArea, QSizePolicy, QSlider, QSpinBox, QSplitter, QStackedLayout, QTableWidget,
                               QStackedWidget, QTabWidget, QTextEdit, QToolButton, QTreeWidget, QWidget)

POLL_MS = 250
_HIDDEN = {'v': False}
_HEAVY = ('layout', 'pages', 'child', 'kids', 'items')
CANVAS_MS = 1200
LANGUAGE = 'zh_CN'                   # The app's language (set by the panel): names Qt's standard buttons.
_STANDARD = {QDialogButtonBox.Ok: '好', QDialogButtonBox.Cancel: '取消', QDialogButtonBox.Yes: '是',
             QDialogButtonBox.No: '否', QDialogButtonBox.Save: '保存', QDialogButtonBox.Discard: '不保存',
             QDialogButtonBox.Close: '关闭', QDialogButtonBox.Apply: '应用', QDialogButtonBox.Reset: '重置',
             QDialogButtonBox.Retry: '重试', QDialogButtonBox.Ignore: '忽略', QDialogButtonBox.Abort: '中止',
             QDialogButtonBox.Help: '帮助', QDialogButtonBox.YesToAll: '全部是', QDialogButtonBox.NoToAll: '全部否'}
_EXPANDING = (QSizePolicy.Expanding, QSizePolicy.MinimumExpanding, QSizePolicy.Ignored)


def empty_hint(listing, label):
    """Show ``label`` (a list's "nothing here yet" line) inside the drawn ``listing`` while it is
    empty, instead of as a line of its own under a big blank box."""
    listing._mirror_empty = label
    label.setProperty('mirrorSkip', True)


def _alive(obj):
    return obj is not None and shiboken6.isValid(obj)


def _draw(widget):
    """What a drawn widget paints itself (and its children), on transparency: no window background."""
    ratio = widget.devicePixelRatioF() or 1.0
    image = QImage(max(1, round(widget.width() * ratio)), max(1, round(widget.height() * ratio)),
                   QImage.Format_ARGB32_Premultiplied)
    image.setDevicePixelRatio(ratio)
    image.fill(0)
    widget.render(image, QPoint(), QRegion(), QWidget.DrawChildren)
    return image


def _art(name):
    if not name:
        return ''
    from quick_ui import ui_art
    return ui_art(name)


def _font(widget):
    """Its font where it differs from the app's (a style sheet makes big numbers big)."""
    from PySide6.QtWidgets import QApplication

    def px(font):
        return font.pixelSize() if font.pixelSize() > 0 else round(font.pointSizeF() * 96 / 72)
    font = widget.font()
    out = {}
    if abs(px(font) - px(QApplication.font())) >= 2:
        out['size'] = px(font)
    if font.weight() >= 600:
        out['bold'] = True
    return out


def _style(widget):
    """Colour, weight and size its style sheet gives a label (the part Petoken's sheets use)."""
    sheet = widget.styleSheet() or ''
    out = {}
    colour = re.search(r'(?<![-\w])color\s*:\s*(#[0-9a-fA-F]{3,8}|[a-z]+)', sheet)
    if colour:
        out['color'] = colour.group(1)
    weight = re.search(r'font-weight\s*:\s*(\d+|bold)', sheet)
    if weight:
        out['bold'] = weight.group(1) == 'bold' or int(weight.group(1)) >= 600
    size = re.search(r'font-size\s*:\s*(\d+)px', sheet)
    if size:
        out['size'] = int(size.group(1))
    if widget.font().bold():
        out['bold'] = True
    return out


class Images(QQuickImageProvider):
    """image://mirror/...: pictures the widgets hold (pixmaps, icons) and drawn widgets (canvases)."""

    def __init__(self):
        super().__init__(QQuickImageProvider.Image)
        self.pictures = {}               # key -> QImage
        self.canvases = weakref.WeakValueDictionary()

    def picture(self, pixmap):
        if pixmap is None or pixmap.isNull():
            return ''
        key = f'p{pixmap.cacheKey()}'
        if key not in self.pictures:
            if len(self.pictures) > 400:
                self.pictures.clear()
            self.pictures[key] = pixmap.toImage()
        return f'image://mirror/{key}'

    def icon(self, icon, size=48):
        if icon is None or icon.isNull():
            return ''
        return self.picture(icon.pixmap(QSize(size, size)))

    def requestImage(self, ident, size, requested):
        kind, _, rest = ident.partition('/')
        if kind == 'canvas':
            widget = self.canvases.get(rest.split('/')[0])
            if _alive(widget):
                return _draw(widget)
            return QImage(1, 1, QImage.Format_ARGB32_Premultiplied)
        return self.pictures.get(kind, QImage(1, 1, QImage.Format_ARGB32_Premultiplied))


class Mirror(QObject):
    """One widget tree, offered to QML as ``tree`` (its structure) and ``values`` (what each
    piece shows now); its slots act on the real widgets."""
    treeChanged = Signal()
    valuesChanged = Signal()
    reshaped = Signal()                  # Some pieces' own structure changed (isReshaped tells which).
    updated = Signal()                   # Some pieces' values changed (isUpdated tells which).

    def __init__(self, root, images, parent=None, dense=False):
        super().__init__(parent)
        self.root = root
        self._dense = dense              # Tighter spacing: a fixed-size window (the usage panel).
        self.images = images
        self._widgets = {}               # id -> widget
        self._counter = 0
        self._tree = {}
        self._nodes = {}
        self._updated = self._reshaped = frozenset()
        self._values = {}
        self._fingerprint = None
        self._canvas_serial = {}
        self._canvas_hash = {}
        self._canvas_due = 0
        self.timer = QTimer(self)
        self.timer.setInterval(POLL_MS)
        self.timer.timeout.connect(self.poll)
        self.poll()

    # Reading the widgets ------------------------------------------------------------------
    def _id(self, widget):
        ident = widget.property('_mirrorId')
        if not ident:
            self._counter += 1
            ident = f'w{self._counter}_{shiboken6.getCppPointer(widget)[0] % 100000}'
            widget.setProperty('_mirrorId', ident)
        self._widgets[ident] = widget
        return ident

    def widget(self, ident):
        widget = self._widgets.get(ident)
        return widget if _alive(widget) else None

    def _layout(self, layout):
        if layout is None:
            return None
        if isinstance(layout, QFormLayout):
            rows = []
            for row in range(layout.rowCount()):
                label = layout.itemAt(row, QFormLayout.LabelRole)
                field = layout.itemAt(row, QFormLayout.FieldRole)
                span = layout.itemAt(row, QFormLayout.SpanningRole)
                rows.append(dict(label=self._item(label), field=self._item(field), span=self._item(span)))
            return dict(t='form', rows=rows, spacing=max(6, layout.verticalSpacing()))
        if isinstance(layout, QGridLayout):
            cells = []
            for index in range(layout.count()):
                r, c, rs, cs = layout.getItemPosition(index)
                node = self._item(layout.itemAt(index))
                if node is not None:
                    cells.append(dict(node=node, r=r, c=c, rs=rs, cs=cs))
            return dict(t='grid', cells=cells, cols=max(1, layout.columnCount()),
                        spacing=max(6, layout.horizontalSpacing()))
        if isinstance(layout, QStackedLayout):
            return dict(t='stack', pages=[self._item(layout.itemAt(i)) for i in range(layout.count())],
                        owner=self._id(layout.parentWidget()) if layout.parentWidget() else '')
        if isinstance(layout, QBoxLayout):
            horizontal = layout.direction() in (QBoxLayout.LeftToRight, QBoxLayout.RightToLeft)
            items = []
            for index in range(layout.count()):
                node = self._item(layout.itemAt(index))
                if node is None:
                    continue
                node = dict(node, stretch=layout.stretch(index))
                items.append(node)
            margins = layout.contentsMargins()
            return dict(t='box', dir='h' if horizontal else 'v', items=items, spacing=layout.spacing(),
                        margins=[margins.left(), margins.top(), margins.right(), margins.bottom()])
        return None

    def _item(self, item):
        if item is None:
            return None
        if item.widget() is not None:
            node = self._child(item.widget())
            if node is not None and item.alignment():
                node['align'] = int(item.alignment())
            return node
        if item.layout() is not None:
            return self._layout(item.layout())
        spacer = item.spacerItem()
        if spacer is not None:
            policy = spacer.sizePolicy()
            hint = spacer.sizeHint()
            return dict(t='space', w=hint.width(), h=hint.height(),
                        hx=policy.horizontalPolicy() in _EXPANDING, vx=policy.verticalPolicy() in _EXPANDING)
        return None

    def _sizing(self, widget):
        policy = widget.sizePolicy()
        out = dict(hx=policy.horizontalPolicy() in _EXPANDING, vx=policy.verticalPolicy() in _EXPANDING,
                   hg=bool(policy.horizontalPolicy().value & 1), vg=bool(policy.verticalPolicy().value & 1))
        if widget.minimumWidth() == widget.maximumWidth() and widget.minimumWidth() > 0:
            out['fw'] = widget.minimumWidth()
        elif widget.minimumWidth() > 0:
            out['mw'] = widget.minimumWidth()
        if widget.maximumWidth() < 10000:
            out['xw'] = widget.maximumWidth()
        if widget.minimumHeight() == widget.maximumHeight() and widget.minimumHeight() > 0:
            out['fh'] = widget.minimumHeight()
        elif widget.minimumHeight() > 0:
            out['mh'] = widget.minimumHeight()
        return out

    def _child(self, widget):
        """A widget inside another: built (and kept in _nodes under its id), handed to its parent as
        just its spec (what it is and how it sizes, not what it holds). QML asks for the rest by id, so
        when one part of a page is rebuilt only that part is redrawn."""
        node = self._node(widget)
        if node is None:
            return None
        self._nodes[node['id']] = node
        return {k: v for k, v in node.items() if k not in _HEAVY} | {'ref': True}

    def _node(self, widget):
        if not _alive(widget) or widget.property('mirrorSkip'):
            return None
        ident = self._id(widget)
        node = dict(id=ident, role=widget.objectName(), **self._sizing(widget))
        if isinstance(widget, QLabel):
            node['t'] = 'label'
        elif isinstance(widget, QDialogButtonBox):
            node.update(t='box', dir='h', spacing=10, margins=[0, 0, 0, 0],
                        items=[dict(t='space', w=0, h=0, hx=True, vx=False)]
                        + [n for n in (self._child(b) for b in self._box_buttons(widget)) if n])
        elif isinstance(widget, QCheckBox):
            node['t'] = 'check'
        elif isinstance(widget, QRadioButton):
            node['t'] = 'radio'
        elif isinstance(widget, (QPushButton, QToolButton)):
            node['t'] = 'button'
            node['primary'] = widget.objectName() == 'primary' or (isinstance(widget, QPushButton)
                                                                   and widget.isDefault())
            node['danger'] = widget.objectName() == 'danger'
        elif isinstance(widget, QComboBox):
            node['t'] = 'combo'
        elif isinstance(widget, QLineEdit):
            node['t'] = 'line'
        elif isinstance(widget, (QPlainTextEdit, QTextEdit)):
            node['t'] = 'text'
        elif isinstance(widget, QDateTimeEdit):
            node['t'] = 'date'
            node['format'] = widget.displayFormat()
        elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
            node['t'] = 'spin'
        elif isinstance(widget, QSlider):
            node['t'] = 'slider'
        elif isinstance(widget, QProgressBar):
            node['t'] = 'progress'
        elif isinstance(widget, QListWidget):
            node['t'] = 'list'
            node['empty'] = _art(widget.property('emptyArt'))
        elif isinstance(widget, (QTreeWidget, QTableWidget)):
            node['t'] = 'tree'
            node['empty'] = _art(widget.property('emptyArt'))
        elif isinstance(widget, QTabWidget):
            node['t'] = 'tabs'
            node['pages'] = [self._child(widget.widget(i)) for i in range(widget.count())]
        elif isinstance(widget, QStackedWidget):
            node['t'] = 'stacked'
            node['pages'] = [self._child(widget.widget(i)) for i in range(widget.count())]
        elif isinstance(widget, QScrollArea):
            node['t'] = 'scroll'
            node['child'] = self._child(widget.widget()) if widget.widget() is not None else None
        elif isinstance(widget, QSplitter):
            node['t'] = 'splitter'
            node['dir'] = 'h' if widget.orientation() == Qt.Horizontal else 'v'
            node['kids'] = [self._child(widget.widget(i)) for i in range(widget.count())]
        elif widget.layout() is not None:
            node['t'] = 'container'
            node['title'] = widget.title() if isinstance(widget, QGroupBox) else ''
            node['layout'] = self._layout(widget.layout())
        elif type(widget).paintEvent is not QWidget.paintEvent and type(widget).paintEvent is not QFrame.paintEvent:
            node['t'] = 'canvas'
            self.images.canvases[ident] = widget
        else:
            node['t'] = 'empty'
        return node

    @staticmethod
    def _box_buttons(box):
        """A button box's buttons, the accepting ones last (where Windows puts OK)."""
        buttons = list(box.buttons())
        order = {QDialogButtonBox.RejectRole: 0, QDialogButtonBox.AcceptRole: 1}
        return sorted(buttons, key=lambda b: order.get(box.buttonRole(b), -1))

    def _value(self, ident, widget):
        out = dict(v=widget.isVisibleTo(self.root) if widget is not self.root else True, en=widget.isEnabled(),
                   tip=widget.toolTip())
        if isinstance(widget, QLabel):
            pixmap = widget.pixmap()
            out.update(text=getattr(widget, 'full_text', None) or widget.text(), rich=widget.textFormat() == Qt.RichText or (
                widget.textFormat() == Qt.AutoText and bool(re.search(r'<[a-zA-Z/][^>]*>', widget.text()))),
                wrap=widget.wordWrap(), align=int(widget.alignment()), links=widget.openExternalLinks(),
                img=self.images.picture(pixmap) if pixmap is not None and not pixmap.isNull() else '',
                imgw=pixmap.width() / max(1.0, pixmap.devicePixelRatio()) if pixmap is not None else 0,
                imgh=pixmap.height() / max(1.0, pixmap.devicePixelRatio()) if pixmap is not None else 0,
                **{**_font(widget), **_style(widget)})
        elif isinstance(widget, QAbstractButton):
            words = widget.text().replace('&&', '\0').replace('&', '').replace('\0', '&')
            box = widget.parentWidget()
            if isinstance(box, QDialogButtonBox) and LANGUAGE.startswith('zh'):
                words = _STANDARD.get(box.standardButton(widget), words)
            out.update(text=words,
                       checkable=widget.isCheckable(), checked=widget.isChecked(),
                       icon=self.images.icon(widget.icon()))
            menu = widget.menu() if isinstance(widget, (QPushButton, QToolButton)) else None
            if menu is not None:
                out['menu'] = [dict(text=a.text().replace('&', ''), sep=a.isSeparator(), en=a.isEnabled(),
                                    tip=a.toolTip() if a.toolTip() != a.text() else '')
                               for a in menu.actions() if a.isVisible()]
        elif isinstance(widget, QComboBox):
            out.update(items=[widget.itemText(i) for i in range(widget.count())], current=widget.currentIndex(),
                       editable=widget.isEditable(), edit=widget.currentText())
        elif isinstance(widget, QLineEdit):
            out.update(text=widget.text(), hint=widget.placeholderText(), ro=widget.isReadOnly(),
                       secret=widget.echoMode() != QLineEdit.Normal, max=widget.maxLength())
        elif isinstance(widget, (QPlainTextEdit, QTextEdit)):
            out.update(text=widget.toPlainText(), hint=widget.placeholderText(), ro=widget.isReadOnly())
        elif isinstance(widget, QDateTimeEdit):
            out.update(text=widget.dateTime().toString(widget.displayFormat()),
                       iso=widget.dateTime().toString(Qt.ISODate))
        elif isinstance(widget, QAbstractSpinBox):
            out.update(value=widget.value(), min=widget.minimum(), max=widget.maximum(), step=widget.singleStep(),
                       suffix=widget.suffix(), prefix=widget.prefix(),
                       decimals=widget.decimals() if isinstance(widget, QDoubleSpinBox) else 0)
        elif isinstance(widget, QSlider):
            out.update(value=widget.value(), min=widget.minimum(), max=widget.maximum(), step=widget.singleStep(),
                       horizontal=widget.orientation() == Qt.Horizontal)
        elif isinstance(widget, QProgressBar):
            span = max(1, widget.maximum() - widget.minimum())
            out.update(fraction=(widget.value() - widget.minimum()) / span if widget.maximum() > widget.minimum() else 0,
                       text=widget.text() if widget.isTextVisible() else '')
        elif isinstance(widget, QListWidget):
            rows = []
            for row in range(widget.count()):
                item = widget.item(row)
                if item.isHidden():
                    continue
                checkable = bool(item.flags() & Qt.ItemIsUserCheckable) and item.data(Qt.CheckStateRole) is not None
                colour = item.foreground().color() if item.foreground().style() != Qt.NoBrush else None
                rows.append(dict(row=row, text=item.text(), tip=item.toolTip(), sel=item.isSelected(),
                                 en=bool(item.flags() & Qt.ItemIsEnabled), check=checkable,
                                 on=checkable and item.checkState() == Qt.Checked, bold=item.font().bold(),
                                 color=colour.name() if colour is not None else '',
                                 icon=self.images.icon(item.icon(), 32)))
            hint = getattr(widget, '_mirror_empty', None)        # Its "nothing here yet" line, shown inside it.
            empty = hint.text() if not rows and hint is not None and _alive(hint) else ''
            out.update(rows=rows, scroll=widget.verticalScrollBar().value(), empty=empty)
        elif isinstance(widget, QTreeWidget):
            header = widget.headerItem()
            heads = [header.text(c) for c in range(widget.columnCount())] if header is not None else []
            rows = []
            for row in range(widget.topLevelItemCount()):
                item = widget.topLevelItem(row)
                if item.isHidden():
                    continue
                rows.append(dict(row=row, cells=[item.text(c) for c in range(widget.columnCount())],
                                 sel=item.isSelected(), tip=item.toolTip(0)))
            hint = getattr(widget, '_mirror_empty', None)
            out.update(heads=heads, rows=rows, header=not widget.isHeaderHidden(),
                       widths=[widget.columnWidth(c) for c in range(widget.columnCount())],
                       empty=hint.text() if not rows and hint is not None and _alive(hint) else '')
        elif isinstance(widget, QTableWidget):           # A table: its header and its cells, as text.
            columns = widget.columnCount()
            heads = [(widget.horizontalHeaderItem(c).text() if widget.horizontalHeaderItem(c) else '')
                     for c in range(columns)]
            rows = []
            for row in range(min(widget.rowCount(), 400)):
                if widget.isRowHidden(row):
                    continue
                cells = [(widget.item(row, c).text() if widget.item(row, c) else '') for c in range(columns)]
                first = widget.item(row, 0)
                rows.append(dict(row=row, cells=cells, sel=bool(first and first.isSelected()),
                                 tip=first.toolTip() if first else ''))
            out.update(heads=heads, rows=rows, header=widget.horizontalHeader().isVisible(),
                       widths=[widget.columnWidth(c) for c in range(columns)])
        elif isinstance(widget, QTabWidget):
            out.update(labels=[widget.tabText(i).replace('&', '') for i in range(widget.count())],
                       tips=[widget.tabToolTip(i) for i in range(widget.count())],
                       icons=[self.images.icon(widget.tabIcon(i), 32) for i in range(widget.count())],
                       shown=[widget.isTabVisible(i) for i in range(widget.count())],
                       current=widget.currentIndex())
        elif isinstance(widget, QStackedWidget):
            out.update(current=widget.currentIndex())
        elif isinstance(widget, QGroupBox):
            out.update(title=widget.title(), checkable=widget.isCheckable(), checked=widget.isChecked())
        if self.images.canvases.get(ident) is widget:
            out.update(img=f'image://mirror/canvas/{ident}/{self._canvas_serial.get(ident, 0)}',
                       w=widget.width(), h=widget.height(), hw=widget.sizeHint().width(),
                       hh=widget.sizeHint().height())
        return out

    def _fingerprint_of(self, widget, out):
        """The tree's shape: which widgets and layouts, in which order (not what they show)."""
        if not _alive(widget):
            return
        out.append(type(widget).__name__ + str(shiboken6.getCppPointer(widget)[0]))
        layout = widget.layout() if not isinstance(widget, (QScrollArea, QSplitter, QTabWidget)) else None
        if layout is not None:
            self._layout_print(layout, out)
        if isinstance(widget, QScrollArea) and widget.widget() is not None:
            self._fingerprint_of(widget.widget(), out)
        if isinstance(widget, (QSplitter, QTabWidget, QStackedWidget)):
            for i in range(widget.count()):
                self._fingerprint_of(widget.widget(i), out)
        if isinstance(widget, QDialogButtonBox):
            out.extend(str(shiboken6.getCppPointer(b)[0]) for b in widget.buttons())

    def _layout_print(self, layout, out):
        out.append('[')
        for index in range(layout.count()):
            item = layout.itemAt(index)
            if item.widget() is not None:
                self._fingerprint_of(item.widget(), out)
            elif item.layout() is not None:
                self._layout_print(item.layout(), out)
            else:
                out.append('_')
        out.append(']')

    @Slot()
    def poll(self):
        if not _alive(self.root):
            self.timer.stop()
            return
        shape = []
        self._fingerprint_of(self.root, shape)
        shape = tuple(shape)
        if shape != self._fingerprint:
            self._fingerprint = shape
            self._widgets = {}
            old = self._nodes
            self._nodes = {}
            self._tree = self._child(self.root) or {}
            reshaped = [ident for ident, node in self._nodes.items() if old.get(ident) != node]
            self._reshaped = set(reshaped)
            self.reshaped.emit()
            self.treeChanged.emit()
        import time
        now = time.monotonic()
        if now >= self._canvas_due:                         # Drawn widgets: re-read now and then.
            self._canvas_due = now + CANVAS_MS / 1000
            self._refresh_canvases()
        values = {}
        for ident, widget in list(self._widgets.items()):
            if not _alive(widget):
                continue
            if widget is not self.root and not widget.isVisibleTo(self.root):
                values[ident] = _HIDDEN                     # Not shown: nothing else to read.
            else:
                values[ident] = self._value(ident, widget)
        old = self._values
        changed = [ident for ident, value in values.items() if old.get(ident) != value]
        if changed or len(values) != len(old):
            self._values = values
            self._updated = set(changed)
            self.updated.emit()
            self.valuesChanged.emit()

    def _refresh_canvases(self):
        for ident, widget in list(self.images.canvases.items()):
            if ident not in self._widgets or not _alive(widget) or not widget.isVisibleTo(self.root):
                continue
            image = _draw(widget)
            digest = hashlib.blake2b(bytes(image.constBits()), digest_size=12).digest() if not image.isNull() else b''
            if digest != self._canvas_hash.get(ident):
                self._canvas_hash[ident] = digest
                self._canvas_serial[ident] = self._canvas_serial.get(ident, 0) + 1

    def soon(self):
        self._canvas_due = 0
        QTimer.singleShot(0, self, self.poll)

    @Property(bool, constant=True)
    def dense(self):
        return self._dense

    @Property('QVariant', notify=treeChanged)
    def tree(self):
        return self._tree

    @Property('QVariant', notify=valuesChanged)
    def values(self):
        return self._values

    @Slot(str, result=bool)
    def isUpdated(self, ident):
        return ident in self._updated

    @Slot(str, result=bool)
    def isReshaped(self, ident):
        return ident in self._reshaped

    @Slot(str, result='QVariant')
    def nodeOf(self, ident):
        """A piece's whole node (its layout and its children's specs)."""
        return self._nodes.get(ident, {})

    @Slot(str, result='QVariant')
    def value(self, ident):
        """What one piece shows (QML asks per piece, so a change converts only that piece)."""
        return self._values.get(ident, {})

    # Acting on them -----------------------------------------------------------------------
    @Slot(str)
    def click(self, ident):
        widget = self.widget(ident)
        if isinstance(widget, QAbstractButton) and widget.isEnabled():
            widget.click()
        self.soon()

    @Slot(str, int)
    def menu(self, ident, index):
        widget = self.widget(ident)
        menu = widget.menu() if isinstance(widget, (QPushButton, QToolButton)) else None
        if menu is not None:
            actions = [a for a in menu.actions() if a.isVisible()]
            if 0 <= index < len(actions) and actions[index].isEnabled() and not actions[index].isSeparator():
                actions[index].trigger()
        self.soon()

    @Slot(str, str)
    def setText(self, ident, value):
        widget = self.widget(ident)
        if isinstance(widget, QLineEdit):
            if widget.text() != value:
                widget.setText(value)
                widget.textEdited.emit(value)
        elif isinstance(widget, (QPlainTextEdit, QTextEdit)):
            if widget.toPlainText() != value:
                widget.setPlainText(value)
        elif isinstance(widget, QComboBox) and widget.isEditable():
            if widget.currentText() != value:
                widget.setEditText(value)
        self.soon()

    @Slot(str)
    def finish(self, ident):
        widget = self.widget(ident)
        if isinstance(widget, QLineEdit):
            widget.editingFinished.emit()
            widget.returnPressed.emit()
        self.soon()

    @Slot(str, int)
    def setIndex(self, ident, index):
        widget = self.widget(ident)
        if isinstance(widget, QComboBox):
            if widget.currentIndex() != index:
                widget.setCurrentIndex(index)
            widget.activated.emit(index)
        elif isinstance(widget, (QTabWidget, QStackedWidget)):
            widget.setCurrentIndex(index)
        self.soon()

    @Slot(str, float)
    def setValue(self, ident, value):
        widget = self.widget(ident)
        if isinstance(widget, QDoubleSpinBox):
            widget.setValue(value)
        elif isinstance(widget, (QSpinBox, QSlider)):
            widget.setValue(int(round(value)))
        self.soon()

    @Slot(str, str)
    def setDate(self, ident, iso):
        widget = self.widget(ident)
        if isinstance(widget, QDateTimeEdit):
            moment = QDateTime.fromString(iso, Qt.ISODate)
            if moment.isValid():
                widget.setDateTime(moment)
        self.soon()

    @Slot(str, bool)
    def setChecked(self, ident, checked):
        widget = self.widget(ident)
        if isinstance(widget, QGroupBox) and widget.isCheckable():
            widget.setChecked(checked)
        self.soon()

    @Slot(str, int)
    def listSelect(self, ident, row):
        widget = self.widget(ident)
        # Choosing may rebuild the list (a project space refreshes everything): re-read the row after.
        if isinstance(widget, QListWidget) and 0 <= row < widget.count():
            if widget.item(row).flags() & Qt.ItemIsEnabled:
                widget.setCurrentRow(row)
                item = widget.item(row) if _alive(widget) and row < widget.count() else None
                if _alive(item) and not item.isSelected():
                    item.setSelected(True)
        elif isinstance(widget, QTreeWidget) and 0 <= row < widget.topLevelItemCount():
            widget.setCurrentItem(widget.topLevelItem(row))
            item = widget.topLevelItem(row) if _alive(widget) and row < widget.topLevelItemCount() else None
            if _alive(item) and not item.isSelected():
                item.setSelected(True)
        self.soon()

    @Slot(str, int, bool)
    def listCheck(self, ident, row, checked):
        widget = self.widget(ident)
        if isinstance(widget, QListWidget) and 0 <= row < widget.count():
            widget.item(row).setCheckState(Qt.Checked if checked else Qt.Unchecked)
        self.soon()

    @Slot(str, int)
    def listActivate(self, ident, row):
        widget = self.widget(ident)
        if isinstance(widget, QListWidget) and 0 <= row < widget.count():
            widget.setCurrentRow(row)
            item = widget.item(row) if row < widget.count() else None
            if _alive(item):
                widget.itemDoubleClicked.emit(item)
        elif isinstance(widget, QTreeWidget) and 0 <= row < widget.topLevelItemCount():
            widget.setCurrentItem(widget.topLevelItem(row))
            item = widget.topLevelItem(row) if row < widget.topLevelItemCount() else None
            if _alive(item):
                widget.itemDoubleClicked.emit(item, 0)
        self.soon()

    @Slot(str, str, float, float)
    def canvasMouse(self, ident, kind, x, y):
        """A press, release, double click, move or wheel ('wheel+'/'wheel-') on a drawn widget."""
        widget = self.widget(ident)
        if widget is None:
            return
        point = QPointF(x, y)
        glob = QPointF(widget.mapToGlobal(QPoint(int(x), int(y))))
        if kind.startswith('wheel'):
            delta = 120 if kind.endswith('+') else -120
            event = QWheelEvent(point, glob, QPoint(), QPoint(0, delta), Qt.NoButton, Qt.NoModifier,
                                Qt.NoScrollPhase, False)
        else:
            types = dict(press=QEvent.MouseButtonPress, release=QEvent.MouseButtonRelease,
                         double=QEvent.MouseButtonDblClick, move=QEvent.MouseMove)
            button = Qt.NoButton if kind == 'move' else Qt.LeftButton
            buttons = Qt.LeftButton if kind in ('press', 'double') else Qt.NoButton
            event = QMouseEvent(types[kind], point, glob, button, buttons, Qt.NoModifier)
        from PySide6.QtWidgets import QApplication
        QApplication.sendEvent(widget, event)
        self.soon()

    @Slot(str, str)
    def link(self, ident, href):
        widget = self.widget(ident)
        if isinstance(widget, QLabel):
            if widget.openExternalLinks():
                from PySide6.QtCore import QUrl
                QDesktopServices.openUrl(QUrl(href))
            else:
                widget.linkActivated.emit(href)
        self.soon()

    @Slot(str, int, int)
    def resizeTo(self, ident, width, height):
        """The space QML gives a mirrored window or page: the real one is laid out to match."""
        widget = self.widget(ident) if ident else self.root
        if widget is not None and width > 0 and height > 0 and (widget.width(), widget.height()) != (width, height):
            widget.resize(max(widget.minimumWidth(), width), max(widget.minimumHeight(), height))
            self.soon()


# Dialogs ---------------------------------------------------------------------------------------
_IMAGES = None


def images():
    global _IMAGES
    if _IMAGES is None:
        _IMAGES = Images()
    return _IMAGES


class MirrorWindow:
    """The window a mirrored dialog is shown in (quick_ui.QuickWindow with its mirror)."""

    @staticmethod
    def open(dialog, panel=None):
        from PySide6.QtWidgets import QApplication
        from quick_ui import MARGIN, HostBridge, QuickWindow

        class DialogBridge(HostBridge):
            titleChanged = Signal()

            @Property(str, notify=titleChanged)
            def title(self):
                words = dialog.windowTitle() if _alive(dialog) else ''
                return re.sub(r'^\s*[Pp]etoken\s*·\s*|\s*·\s*[Pp]etoken\s*$', '', words)

            @Slot()
            def close(self):
                if _alive(dialog):
                    dialog.reject()

            @Slot(float)
            def fit(self, height):
                """Tall enough for everything, within the screen (then it scrolls). Later, not while
                the page is being laid out: resizing the view inside its own frame breaks the frame."""
                self._wanted = height
                QTimer.singleShot(0, window, self._fit)

            @Slot(float)
            def fitWidth(self, width):
                QTimer.singleShot(0, window, lambda: self._fit_width(width))

            def _fit_width(self, width):
                if not _alive(window):
                    return
                screen = (window.screen() or QApplication.primaryScreen()).availableGeometry()
                wanted = int(min(screen.width() - 40, width))
                if wanted > window.width() + 4:              # Only ever wider, keeping its centre.
                    window.setGeometry(window.x() - (wanted - window.width()) // 2, window.y(), wanted, window.height())

            def _fit(self):
                if not _alive(window):
                    return
                screen = (window.screen() or QApplication.primaryScreen()).availableGeometry()
                wanted = int(min(screen.height() - 40, max(200, getattr(self, '_wanted', 0))))
                if window.isVisible():
                    wanted = max(wanted, window.height())     # Open: it may grow, never jump smaller.
                if abs(window.height() - wanted) > 4:
                    top = window.y() - (wanted - window.height()) // 2
                    window.setGeometry(window.x(), max(screen.top() + 10, min(top, screen.bottom() - wanted)),
                                       window.width(), wanted)

        class Prefs:
            prefs = {}
        window = QuickWindow(dialog, Qt.Window)       # Goes away with its dialog.
        window.setWindowTitle(dialog.windowTitle())
        if dialog.isModal() or dialog.testAttribute(Qt.WA_ShowModal):
            window.setWindowModality(Qt.ApplicationModal)
        bridge = DialogBridge(window, panel or getattr(dialog, 'panel', None) or Prefs())
        mirror = Mirror(dialog, images(), window)
        engine = window.view.engine()
        if engine.imageProvider('mirror') is None:
            engine.addImageProvider('mirror', _Shared(images()))
        window.load('MirrorDialog.qml', bridge=bridge, mirror=mirror)
        hint = dialog.size().expandedTo(dialog.sizeHint())
        w = min(1180, max(440, int(hint.width() * 1.12))) + 2 * MARGIN
        if any(tabs.count() > 5 for tabs in dialog.findChildren(QTabWidget)):
            w = max(w, 1000 + 2 * MARGIN)                  # Its pages get a rail down the left (MTabs).
        h = min(900, max(220, int(hint.height() * 1.18) + 70)) + 2 * MARGIN
        window.resize(w, h)
        parent = dialog.parentWidget()
        anchor = parent.window() if parent is not None else None
        if anchor is not None and anchor.isVisible() and not anchor.testAttribute(Qt.WA_DontShowOnScreen):
            centre = anchor.frameGeometry().center()
        else:
            shell = getattr(anchor, 'shell', None) if anchor is not None else None
            if shell is not None and shell.isVisible():
                centre = shell.frameGeometry().center()
            else:
                centre = (QApplication.screenAt(dialog.geometry().center()) or QApplication.primaryScreen()
                          ).availableGeometry().center()
        window.move(centre.x() - w // 2, centre.y() - h // 2)
        root = window.view.rootObject()
        if root is not None:
            bridge._wanted = root.property('wantHeight') or h
            bridge._fit()
        window.mirror = mirror
        window.bridge = bridge
        mirror.timer.start()
        window.show()
        window.raise_()
        window.activateWindow()
        return window


class Follower(QObject):
    """A window of the app that is not a dialog (the usage panel beside her) shown through its mirror:
    the real one stays laid out and off the screen, and the mirror window takes its place, its
    position, its size and its showing and hiding."""

    def __init__(self, target, qml='MirrorPanel.qml'):
        super().__init__(target)
        from quick_ui import MARGIN
        self.target, self.margin, self.qml = target, MARGIN, qml
        self.window = self.mirror = self.bridge = None
        target.setAttribute(Qt.WA_DontShowOnScreen)
        target.installEventFilter(self)
        if target.isVisible():
            QTimer.singleShot(0, self, self._show)

    def _ensure(self):
        """The mirror window, made the first time it is needed (never inside the target's own events)."""
        if self.window is None or not _alive(self.window):
            from quick_ui import HostBridge, QuickWindow
            target = self.target
            flags = target.windowFlags() & (Qt.Tool | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus)
            self.window = QuickWindow(None, Qt.Window | flags)
            self.window.setWindowTitle(target.windowTitle())
            self.window.setWindowIcon(target.windowIcon())
            if target.testAttribute(Qt.WA_ShowWithoutActivating):
                self.window.setAttribute(Qt.WA_ShowWithoutActivating)
            self.bridge = HostBridge(self.window, getattr(target, 'panel', None) or target)
            self.mirror = Mirror(target, images(), self.window, dense=True)
            self.window.view.engine().addImageProvider('mirror', _Shared(images()))
            self.window.load(self.qml, bridge=self.bridge, mirror=self.mirror)
            root = self.window.view.rootObject()
            if root is not None:
                root.wantHeightChanged.connect(lambda: QTimer.singleShot(0, self, self._replace))
                root.wantWidthChanged.connect(lambda: QTimer.singleShot(0, self, self._replace))
            target.destroyed.connect(self.window.deleteLater)
        return self.window

    def _flags(self):
        wanted = self.target.windowFlags() & (Qt.Tool | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus)
        current = self.window.windowFlags() & (Qt.Tool | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus)
        if wanted != current:                               # Always on top was switched.
            self.window.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | wanted)

    def _place(self):
        g = self.target.geometry()
        m = self.margin
        root = self.window.view.rootObject()
        wanted = (root.property('wantHeight') or 0) if root is not None else 0
        # As tall as its words need (they are never squeezed), at least the real one's height.
        wide = (root.property('wantWidth') or 0) if root is not None else 0
        self.window.setGeometry(g.x() - m, g.y() - m, max(g.width() + 2 * m, int(wide) + 1),
                                max(g.height() + 2 * m, int(wanted) + 1))

    def _replace(self):
        if self.window is not None and _alive(self.window) and self.window.isVisible():
            self._place()

    def _show(self):
        if not _alive(self.target) or not self.target.isVisible():
            return
        self._ensure()
        self._flags()
        self._place()
        self.mirror.timer.start()
        self.mirror.soon()
        self.window.show()
        self.window.raise_()

    def eventFilter(self, obj, event):
        kind = event.type()
        if obj is self.target and kind == QEvent.Show:
            QTimer.singleShot(0, self, self._show)
        elif obj is self.target and self.window is not None and _alive(self.window):
            if kind == QEvent.Hide:
                self.mirror.timer.stop()
                self.window.hide()
            elif kind in (QEvent.Move, QEvent.Resize) and self.window.isVisible():
                self._place()
            elif kind == QEvent.ZOrderChange and self.window.isVisible():
                self.window.raise_()
        return False


class _Shared(QQuickImageProvider):
    """The one Images store, registered in each engine (a provider belongs to its engine)."""

    def __init__(self, store):
        super().__init__(QQuickImageProvider.Image)
        self.store = store

    def requestImage(self, ident, size, requested):
        return self.store.requestImage(ident, size, requested)


# Windows beside her that are drawn from widgets too, shown through a follower window.
FOLLOWED = frozenset({'ApprovalCard', 'QuestionCard', 'PlanCard', 'FocusCard', 'ContinuationCard', 'TaskPanelWindow'})


class _Skin(QObject):
    """Puts every dialog the app opens into a mirror window instead of a plain one."""

    def eventFilter(self, obj, event):
        kind = event.type()
        if (kind == QEvent.Polish and isinstance(obj, QWidget) and type(obj).__name__ in FOLLOWED
                and obj.isWindow() and getattr(obj, '_mirror_follower', None) is None):
            obj._mirror_follower = Follower(obj)
            return False
        if kind == QEvent.Polish and isinstance(obj, QDialog) and obj.isWindow() and _wanted(obj):
            obj.setAttribute(Qt.WA_DontShowOnScreen)
            obj.setProperty('_mirrored', True)
        elif kind == QEvent.Show and isinstance(obj, QDialog) and obj.property('_mirrored'):
            QTimer.singleShot(0, obj, lambda d=obj: _show_mirror(d))       # Not inside its own show.
        elif kind == QEvent.Hide and isinstance(obj, QDialog) and obj.property('_mirrored'):
            window = getattr(obj, '_mirror_window', None)
            if window is not None and _alive(window):
                window.mirror.timer.stop()
                window.hide()
        return False


def _show_mirror(dialog):
    if not _alive(dialog) or not dialog.isVisible():
        return
    window = getattr(dialog, '_mirror_window', None)
    if window is None or not _alive(window):
        dialog._mirror_window = MirrorWindow.open(dialog)
    else:
        window.mirror.timer.start()
        window.mirror.soon()
        window.show()
        window.raise_()
        window.activateWindow()


def _wanted(dialog):
    if isinstance(dialog, QFileDialog) or dialog.property('mirrorNative'):
        return False
    return True


_FILTER = None


def install(app):
    """From now on every dialog opens in Petoken's own look."""
    global _FILTER
    if _FILTER is None:
        _FILTER = _Skin()
        app.installEventFilter(_FILTER)
    return _FILTER


def uninstall(app):
    global _FILTER
    if _FILTER is not None:
        app.removeEventFilter(_FILTER)
        _FILTER = None

