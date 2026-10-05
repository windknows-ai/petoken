"""petoken — a small, local Windows desktop companion."""
from __future__ import annotations

import argparse
from bisect import bisect_right
import json
import math
import os
import sys
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal, QObject, QPoint, QPointF, QRect, QRectF, QSize, QLockFile
from PySide6.QtGui import QColor, QCursor, QFont, QFontMetrics, QIcon, QPainter, QPainterPath, QPen, QLinearGradient, QRadialGradient, QPixmap, QPolygonF, QKeySequence, QRegion, QShortcut
from PySide6.QtWidgets import (QApplication, QWidget, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QFrame, QProgressBar, QMenu, QSystemTrayIcon, QDialog,
    QFormLayout, QComboBox, QCheckBox, QSlider, QDialogButtonBox, QScrollArea, QSizePolicy)

from desktop import ActiveTask, RateLimits, fetch_fx
from usage import quota_window, sample_age
from analytics_view import AnalyticsWindow, help_text
from trail_overlay import TrailOverlay
from halo_scene import HaloScene
from detail_transition import DetailTransition
import halo_geometry
import pet_assets as assets
import pet_geometry as pet_geometry
from app_config import APP_VERSION, load_preferences, save_preferences
from app_mode import AppModeState
from provider_poller import ProviderPoller
from provider_selection import TRACKING_CHOICES, normalize_tracking_provider
from providers import PROVIDER_NAMES, PROVIDER_REGISTRY
from activity import activity_diagnostics
from localization import DEFAULT_LANGUAGE, normalize_language, scope_text, text
from pricing import (DEFAULT_CURRENCY, SUPPORTED_CURRENCIES, convert_usd, format_cost,
                     normalize_currency, normalize_rates)
import theme
from token_format import (DEFAULT_TOKEN_NUMBER_FORMAT, format_token_value,
                          format_tokens, normalize_token_format)

INK, MUTED, ICE, VIOLET, BG = theme.INK, theme.MUTED, theme.ICE, theme.VIOLET, theme.BG
PREF_DIR = Path(os.environ.get('LOCALAPPDATA', str(Path.home()/'.local/share')))/'CodexWisp'
STYLE = f'''
QWidget {{ color:{theme.INK}; font-family:{theme.FONT_UI}; font-size:12px; }}
QAbstractItemView,QLineEdit,QTextEdit,QPlainTextEdit {{ selection-background-color:{theme.TAB_SELECTED_BG}; selection-color:{theme.INK}; }}
QWidget#surface {{ background:{theme.SURFACE_TOP}; border:2px solid {theme.BORDER}; border-radius:{theme.RADIUS_SURFACE}px; }}
QWidget#hubSurface {{ background:{theme.SURFACE_TOP}; border:2px solid {theme.BORDER}; border-radius:{theme.RADIUS_SURFACE}px; }}
QWidget#hubSurface QPushButton {{ background:{theme.SURFACE_BOTTOM}; }}
QWidget#hubSurface QPushButton:hover,QWidget#hubSurface QPushButton:pressed {{ background:{theme.HOVER_BG}; }}
QWidget#hubSurface QPushButton:checked {{ background:{theme.CHECKED_BG}; }}
QWidget#hubHeader QPushButton {{ min-height:0; padding:0; }}
QLabel {{ background:transparent; border:none; }}
QLabel#muted {{ color:{theme.MUTED}; font-size:11px; }}
QLabel#brand {{ color:{theme.INK}; font-family:{theme.FONT_DISPLAY}; font-size:14px; font-weight:600; }}
QLabel#number {{ font-family:{theme.FONT_NUM}; font-size:30px; font-weight:600; }}
QLabel#smallnumber {{ font-family:{theme.FONT_NUM}; font-size:16px; }}
QLabel#cost {{ color:{theme.ICE}; font-family:{theme.FONT_NUM}; font-size:22px; font-weight:600; }}
QLabel#badge {{ color:{theme.VIOLET}; background:{theme.BADGE_BG}; border:1px solid {theme.BORDER_SOFT}; border-radius:{theme.RADIUS_BADGE}px; padding:4px 10px; font-size:11px; }}
QFrame#card {{ background:{theme.CARD}; border:1px solid {theme.BORDER_SOFT}; border-radius:{theme.RADIUS_CARD}px; }}
QPushButton {{ background:{theme.CONTROL_BG}; border:1px solid {theme.BORDER_CONTROL}; border-bottom:2px solid {theme.BORDER_CONTROL}; border-radius:{theme.RADIUS_BUTTON}px; padding:5px 8px; min-height:24px; }}
QPushButton:pressed {{ background:{theme.HOVER_BG}; border-bottom-width:1px; padding-top:6px; }}
QWidget#pages QPushButton {{ min-height:18px; padding:1px 3px; }}
QWidget#pages QPushButton:pressed {{ padding-top:2px; }}
QPushButton:hover {{ background:{theme.HOVER_BG}; border-color:{theme.HOVER_BORDER}; }}
QPushButton:focus {{ border-color:{theme.ICE}; }}
QPushButton:checked {{ background:{theme.CHECKED_BG}; color:{theme.ICE}; border-color:{theme.BORDER_CONTROL}; }}
QFrame#divider {{ background:{theme.DIVIDER}; max-height:1px; border:0; }}
QProgressBar {{ background:{theme.TRACK}; border:0; border-radius:{theme.RADIUS_BAR}px; min-height:5px; max-height:5px; }}
QProgressBar::chunk {{ background:{theme.ICE}; border-radius:{theme.RADIUS_BAR}px; }}
QMenu {{ background:{theme.MENU_BG}; border:1px solid {theme.BORDER_CONTROL}; padding:6px; }}
QMenu::item {{ padding:9px 18px; border-radius:8px; }}
QMenu::item:selected {{ background:{theme.MENU_SELECTED}; }}
QToolTip {{ background:{theme.TOOLTIP_BG}; color:{theme.INK}; border:1px solid {theme.TOOLTIP_BORDER}; padding:7px; }}
QDialog {{ background:{theme.BG}; }}
QLineEdit,QPlainTextEdit {{ background:{theme.CONTROL_BG}; border:1px solid {theme.BORDER_CONTROL}; border-radius:8px; padding:5px; }}
QComboBox {{ background:{theme.CONTROL_BG}; border:1px solid {theme.BORDER_CONTROL}; border-radius:8px; padding:6px 30px 6px 10px; min-height:24px; }}
QComboBox:focus {{ border-color:{theme.VIOLET}; }}
QComboBox::drop-down {{ subcontrol-origin:padding; subcontrol-position:top right; width:26px; border:0; background:transparent; }}
QComboBox::down-arrow {{ image:url("{assets.ASSETS_DIR.as_posix()}/chevron-down.svg"); }}
QComboBox QAbstractItemView {{ background:{theme.CONTROL_BG}; selection-background-color:{theme.TAB_SELECTED_BG}; selection-color:{theme.INK}; }}
QScrollArea {{ border:0; background:transparent; }}
QCheckBox {{ spacing:8px; }}
QCheckBox::indicator {{ width:16px; height:16px; border:1px solid {theme.BORDER_CONTROL}; border-radius:5px; background:{theme.CONTROL_BG}; }}
QCheckBox::indicator:checked {{ background:{theme.CHECK_BG}; border-color:{theme.VIOLET}; image:url("{assets.ASSETS_DIR.as_posix()}/checkmark.svg"); }}
QSlider::groove:horizontal {{ background:{theme.TRACK}; height:6px; border-radius:3px; }}
QSlider::handle:horizontal {{ background:{theme.ICE}; width:16px; height:16px; margin:-5px 0; border-radius:8px; border:none; }}
'''


def label(text='', name='', parent=None):
    w = QLabel(text, parent)
    w.setTextFormat(Qt.PlainText)
    if name:
        w.setObjectName(name)
    return w


def button(text, tip, slot):
    w = QPushButton(text)
    w.setToolTip(tip)
    w.setAccessibleName(tip)
    w.clicked.connect(slot)
    return w


def divider():
    w = QFrame()
    w.setObjectName('divider')
    w.setFixedHeight(1)
    return w


PANEL_MIN = (420, 400)
PANEL_MAX = (650, 800)
PANEL_DEFAULT = (420, 500)
# Fixed overview footprint; legacy saved sizes remain readable but no longer
# control this window. Compact mode has the same width and its own height.
HUB_SIZE = (440, 720)
# Intentional compact footprint: identity + task + one metrics row + one
# control strip. Tuned from real renders, not from the expanded stack.
COMPACT_HEIGHT = 316



def valid_panel_size(value):
    """Clamp a saved expanded-panel size into supported bounds, or None when
    the saved value is malformed. Never raises on user-edited settings."""
    try:
        width, height = int(value[0]), int(value[1])
    except (TypeError, ValueError, OverflowError, IndexError, KeyError):
        return None
    return [max(PANEL_MIN[0], min(width, PANEL_MAX[0])),
            max(PANEL_MIN[1], min(height, PANEL_MAX[1]))]


def read_preferences():
    return load_preferences(PREF_DIR/'settings.json')


def write_preferences(data):
    save_preferences(PREF_DIR/'settings.json', data)


class Spirit(QWidget):
    """Original vector ice spirit; all artwork ships as editable source."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(54, 60)
        self.setAccessibleName('')

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor('#353956'))
        p.drawEllipse(QRectF(9, 49, 38, 7))
        for points, color in [([(24,13),(8,5),(10,27),(1,34),(20,38)], VIOLET),
                              ([(31,14),(47,2),(44,25),(54,33),(37,39)], ICE)]:
            path = QPainterPath(QPoint(*points[0]))
            for point in points[1:]:
                path.lineTo(*point)
            path.closeSubpath()
            p.setBrush(QColor(color))
            p.drawPath(path)
        g = QLinearGradient(14, 12, 42, 48)
        g.setColorAt(0, QColor('#FFFFFF'))
        g.setColorAt(.6, QColor('#CFD7F8'))
        g.setColorAt(1, QColor('#AFA1EB'))
        p.setBrush(g)
        path = QPainterPath()
        path.moveTo(27, 11)
        path.cubicTo(4, 15, 9, 36, 15, 42)
        path.lineTo(23, 46)
        path.lineTo(28, 52)
        path.lineTo(33, 45)
        path.cubicTo(49, 39, 47, 14, 27, 11)
        p.drawPath(path)
        p.setPen(QPen(QColor('#434965'), 2.5, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(20, 29, 20, 33)
        p.drawLine(35, 29, 35, 33)
        p.setPen(QPen(QColor('#957ECD'), 1.3))
        p.drawArc(QRectF(25,33,6,5), 200*16, 140*16)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor('#B9B1EB'))
        p.drawEllipse(QRectF(13,34,7,3))
        p.drawEllipse(QRectF(36,34,7,3))


class ElidedLabel(QLabel):
    def __init__(self, text=''):
        super().__init__()
        self.full_text = text
        self.setTextFormat(Qt.PlainText)
        self.setMinimumWidth(0)
        self.setFixedHeight(25)

    def setFullText(self, text):
        self.full_text = text
        self.setToolTip(text)
        self.fit()

    def fit(self):
        self.setText(self.fontMetrics().elidedText(self.full_text, Qt.ElideRight, max(1,self.width())))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit()


class TokenTotalLabel(QLabel):
    """Fit full integers to the viewport without changing their numeric text."""
    def __init__(self, base_size=30, object_name='number'):
        super().__init__('—')
        self._base_size = base_size
        self.setObjectName(object_name)
        self.setWordWrap(True)
        self.setTextFormat(Qt.PlainText)

    def fit(self):
        font = QFont(self.font())
        font.setPixelSize(self._base_size)
        width = QFontMetrics(font).horizontalAdvance(self.text())
        size = max(12, min(self._base_size,
                           int(self._base_size * max(1, self.contentsRect().width()-2) / max(1, width))))
        style = f'font-size:{size}px;'
        if self.styleSheet() != style:
            self.setStyleSheet(style)

    def setText(self, value):
        super().setText(value)
        self.fit()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit()

    def minimumSizeHint(self):
        return QSize(1, super().minimumSizeHint().height())


class Meter(QWidget):
    def __init__(self, title, color):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        row = QHBoxLayout()
        self.title = label(title)
        row.addWidget(self.title)
        row.addStretch()
        self.value = label('—')
        row.addWidget(self.value)
        layout.addLayout(row)
        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setValue(0)
        self.bar.setTextVisible(False)
        self.bar.setStyleSheet(f'QProgressBar::chunk {{ background:{color}; }}')
        self.bar.setAccessibleName(title)
        layout.addWidget(self.bar)
        self.reset = label('', 'muted')
        self.reset.setVisible(False)
        layout.addWidget(self.reset)

    def set_title(self, title):
        self.title.setText(title)
        self.bar.setAccessibleName(title)

    def update_value(self, value, suffix='', tip='', stale=False):
        self.value.setText('N/A' if value is None else f'{value:.0f}% {suffix}')
        self.bar.setValue(0 if value is None else round(value*10))
        self.bar.setEnabled(not stale)
        self.value.setStyleSheet(f'color:{MUTED if stale else INK};')
        self.setToolTip(tip)


class Bridge(QObject):
    data = Signal(dict)
    limits = Signal(dict)
    fx = Signal(dict)


# --- V1.3 Slice C: multi-task panels (one pet, N windows) ---
#
# The manager below consumes the accepted coherent active-task sets built
# by Slice B (provider_poller.filter_active_tasks output carried on each
# poll envelope). It never reads provider stores, never parses lifecycle
# data, and never computes accounting: every visible value comes from the
# task's own presentation projection, with N/A for unknown fields.

def task_identity(task):
    """Stable provider-scoped panel key: (provider_id, task_key).

    Raw IDs from different providers never collide, and visible labels
    are never used as identity.
    """
    task = task or {}
    return (task.get('provider_id'), task.get('task_key'))


def order_tasks(tasks):
    """Deterministic initial order for visible tasks.

    Registry provider order first, then trustworthy adapter activity
    (newest first, unknown last), then the stable task key. Used only
    for initial placement; surviving panels never reorder per tick.
    """
    order = {pid: index for index, pid in enumerate(PROVIDER_REGISTRY)}
    def key(task):
        pid, tkey = task_identity(task)
        activity = (task or {}).get('activity_at')
        return (order.get(pid, len(order)),
                0 if isinstance(activity, (int, float)) else 1,
                -(activity or 0),
                str(tkey))
    return sorted(tasks or [], key=key)


def filter_tasks_for_preference(tasks, preference):
    """Multi-task provider filter, independent of primary selection.

    Auto shows every accepted task; a manual preference shows only that
    provider's tasks. Pure subset over already-accepted sets: no debounce,
    no provider reads, and the underlying snapshots are never mutated.
    """
    preference = normalize_tracking_provider(preference)
    if preference == 'auto':
        return list(tasks or [])
    return [t for t in (tasks or []) if (t or {}).get('provider_id') == preference]


def format_recorded_cost(amount):
    """Task-local recorded cost without a currency symbol (unknown).

    Unknown stays N/A; real zero shows 0.00; ordinary values keep two
    decimals; small positives keep enough precision to stay visibly
    non-zero (0.001 never collapses to 0.00). Shared by task surfaces so
    orb/card presentations interpret cost identically.
    """
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        return 'N/A'
    if amount == 0:
        return '0.00'
    if abs(amount) >= 0.01:
        return f'{amount:.2f}'
    trimmed = f'{amount:.6f}'.rstrip('0').rstrip('.')
    return trimmed if trimmed not in ('0', '-0', '') else repr(amount)


def format_task_metrics(provider_id, presentation, language, token_style=None):
    """Shared task-local display strings for one Slice B task entry.

    Returns {row: (value_text, tip)}. Task surfaces read the same
    values, so orb and card presentations can never disagree on one
    task's metrics. Unknown stays N/A and is never zero-filled; real
    zeroes render as zeroes.
    """
    presentation = presentation or {}
    tokens = presentation.get('tokens') or {}
    return dict(
        total=(format_tokens(tokens.get('total_tokens'), token_style),
               text('help_total_tokens', language)),
        input=(format_tokens(tokens.get('input_tokens'), token_style), ''),
        output=(format_tokens(tokens.get('output_tokens'), token_style), ''),
        model=(presentation.get('model') or text('unknown', language), ''))


class TaskPanelWindow(QWidget):
    """One manager-owned task detail, rendered only from its own projection."""

    def __init__(self, provider_id='codex', manager=None):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.provider_id = provider_id or 'codex'
        self.manager = manager
        self.setFocusPolicy(Qt.StrongFocus)
        self.window_size = (252, 340)
        self.setFixedSize(*self.window_size)
        self.setStyleSheet(STYLE)
        self.entry = None
        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 6)
        surface = QWidget()
        surface.setObjectName('surface')
        outer.addWidget(surface)
        layout = QVBoxLayout(surface)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(4)
        head = QHBoxLayout()
        self.title_label = ElidedLabel()
        self.title_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.title_label.setStyleSheet('font-size:13px;font-weight:600;')
        head.addWidget(self.title_label, 1)
        self.collapse_button = button('', '', self.collapse)
        head.addWidget(self.collapse_button)
        layout.addLayout(head)
        status = QHBoxLayout()
        self.provider_label = QLabel('')
        self.provider_label.setObjectName('muted')
        status.addWidget(self.provider_label)
        status.addStretch()
        self.status_dot = QLabel('●')
        status.addWidget(self.status_dot)
        self.status_text = QLabel('')
        self.status_text.setObjectName('muted')
        status.addWidget(self.status_text)
        layout.addLayout(status)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.viewport().setStyleSheet(f'background:{BG};')
        layout.addWidget(self.scroll, 1)
        body = QWidget()
        body.setStyleSheet(f'background:{BG};')
        rows = QVBoxLayout(body)
        rows.setContentsMargins(0, 0, 0, 0)
        rows.setSpacing(4)
        self.project_label = ElidedLabel()
        self.project_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.project_label.setObjectName('muted')
        rows.addWidget(self.project_label)
        rows.addWidget(divider())
        self._rows = {}
        for key in self._row_keys():
            row = QHBoxLayout()
            name = QLabel('')
            name.setObjectName('muted')
            row.addWidget(name)
            value = ElidedLabel()
            value.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
            value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            row.addWidget(value, 1)
            rows.addLayout(row)
            self._rows[key] = (name, value)
        self.warning = QLabel('')
        self.warning.setTextFormat(Qt.PlainText)
        self.warning.setWordWrap(True)
        self.warning.setObjectName('muted')
        rows.addWidget(self.warning)
        rows.addStretch()
        self.scroll.setWidget(body)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.collapse()
            event.accept()
        else:
            super().keyPressEvent(event)

    def _row_keys(self):
        return ('total', 'input', 'output', 'model', 'effort', 'context')

    def collapse(self):
        if self.manager is not None:
            self.manager.collapse_detail()
        else:
            self.hide()

    def closeEvent(self, event):
        self.collapse()
        event.accept()

    def _set_row(self, key, name_text, value_text, tip=''):
        name, value = self._rows[key]
        name.setText(name_text)
        value.setFullText(str(value_text))
        value.setToolTip(str(value_text) + ('\n' + tip if tip else ''))

    def set_task(self, entry, label_text, language, token_style=None):
        self.entry = dict(entry or {})
        presentation = self.entry.get('presentation') or {}
        display = self.entry.get('display') or {}
        provider_name = PROVIDER_NAMES.get(self.provider_id, self.provider_id)
        self.title_label.setFullText(label_text)
        self.provider_label.setText(provider_name)
        self.provider_label.setToolTip(str(presentation.get('version') or ''))
        self.project_label.setFullText(display.get('project') or '—')
        self.status_dot.setStyleSheet(f'color:{ICE};')
        self.status_text.setText(text('working', language))
        self.setWindowTitle(f'{provider_name} · {label_text}')
        self.setAccessibleName(self.windowTitle())
        collapse = text('task_collapse', language)
        self.collapse_button.setText('×')
        self.collapse_button.setToolTip(collapse)
        self.collapse_button.setAccessibleName(collapse)
        metrics = format_task_metrics(self.provider_id, presentation, language, token_style)
        metrics['effort'] = (presentation.get('effort') or text('unknown', language), '')
        context = presentation.get('context')
        metrics['context'] = ('N/A' if context is None else f'{context:.0f}%', '')
        for key in self._rows:
            caption = 'task_panel_' + key
            self._set_row(key, text(caption, language), *metrics[key])
        warnings = []
        if presentation.get('partial'):
            warnings.append(text('coverage_partial', language) + ' · ' + text('partial_records', language))
        if presentation.get('source_available') is False:
            warnings.append(text('task_source_unavailable', language))
        if presentation.get('available') is False:
            warnings.append(text('task_usage_unavailable', language))
        for note in presentation.get('notes') or ():
            translated = text(note, language) if isinstance(note, str) and note.startswith('note_') else note
            warning = translated if translated != note else text('task_record_note', language)
            if warning not in warnings:
                warnings.append(warning)
        self.warning.setText('\n'.join(warnings))
        self.warning.setVisible(bool(warnings))

    def panel_text(self):
        parts = [self.title_label.full_text, self.provider_label.text(),
                 self.provider_label.toolTip(), self.project_label.full_text,
                 self.status_text.text(), self.windowTitle(), self.warning.text(),
                 self.collapse_button.toolTip()]
        for name, value in self._rows.values():
            parts.extend((name.text(), value.full_text, value.toolTip()))
        return '\n'.join(parts)


class TaskOrbWindow(QWidget):
    """One crystalline task star for a single verified working task.

    D2A collapsed visual: a custom-painted four-point crystal star
    (white core, cyan/lavender facets, violet edges, static halo, two
    deterministic micro-sparkles) with a tiny neutral number beneath.
    No provider text, no metrics, no button chrome — the star is the
    focus; provider identity lives in the tooltip only.

    No timers, no motion, no trail in D2A. Paint parameters are
    instance attributes (halo_alpha, halo_radius, core_intensity,
    facet_intensity, star_scale) with static defaults so D2B breathing
    can vary them per-frame without a repaint rewrite. D2B hover/press
    pause must use accumulated active orbit time (never absolute wall
    clock) so resume cannot teleport; the shared D2B timer may call
    update() on phase change even when stationary (this replaces the
    old "update only when moving" idea). A D2B trail, if added, must
    be a manager-owned screen-coordinate overlay — never painted
    inside this ~112px widget, where old positions would clip.

    Hit behavior: an OS-level mask limits the clickable region to the
    star/halo disc plus the number label, and press handling rejects
    anything outside it, so overlapping transparent bounds can never
    misroute a click to a neighboring star.

    Press + release below the drag threshold counts as a click
    (reported to the manager; D2C attaches expand here). Pressing and
    moving beyond the threshold does nothing: collapsed stars are not
    draggable (Product Owner direction) — no reposition, no override,
    no click. Hover pauses this star's orbit (via the manager);
    breathing continues. One task owns one effective anchor: the
    automatic ring home for its lifetime slot. D2C expands the panel
    from the current star center and collapses back to the same
    anchor.
    """

    def __init__(self, identity, provider_id='codex', manager=None):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.identity = identity
        self.provider_id = provider_id or 'codex'
        self.manager = manager
        self.compact_halo = manager is not None and not manager.legacy_exterior_motion
        self.depth = 1.0
        self.setFocusPolicy(Qt.StrongFocus)
        self.orb_size = pet_geometry.TASK_STAR_SIZE
        self.setFixedSize(*self.orb_size)
        # No surface stylesheet: the star floats directly on the
        # desktop with no box behind it.
        self._press_global = None
        self._press_offset = None
        self._dragging = False
        self._number = ''
        # D2A static paint parameters; D2B breathing varies these.
        self.halo_alpha = 1.0
        self.halo_radius = 1.0
        self.core_intensity = 1.0
        self.facet_intensity = 1.0
        self.star_scale = 1.0
        self.number_label = QLabel('', self)
        self.number_label.setTextFormat(Qt.PlainText)
        self.number_label.setAlignment(Qt.AlignCenter)
        self.number_label.setStyleSheet('color:#E4E9FF;font-size:11px;')
        # Canonical clickable strip: same rect the geometry solver
        # validates, so hit-test and mask can never disagree.
        if self.compact_halo:
            cx, cy = pet_geometry.TASK_STAR_CENTER
            self.number_label.setGeometry(cx - 9, cy + halo_geometry.LABEL_TOP, 18, 14)
            self.number_label.setStyleSheet(
                'color:#F7F5FF;background:transparent;border:none;'
                'font-family:"Segoe UI";font-size:10px;font-weight:600;')
            self.star_scale = .7
        else:
            self.number_label.setGeometry(*pet_geometry.STAR_LABEL_RECT)
        self._apply_hit_mask()

    def _star_center(self):
        return QPointF(*pet_geometry.TASK_STAR_CENTER)

    def _scaled_points(self):
        center = self._star_center()
        return [QPointF(center.x() + dx * self.star_scale,
                        center.y() + dy * self.star_scale)
                for dx, dy in pet_geometry.star_ray_points()]

    def _alpha(self, base, factor=1.0):
        return max(0, min(255, int(base * factor)))

    def _sparkle_offsets(self):
        """Two deterministic micro-sparkle centers (slot-stable)."""
        import zlib
        seed = zlib.crc32(repr(self.identity).encode('utf-8'))
        center = self._star_center()
        points = []
        for shift in (0, 11):
            frac = ((seed >> shift) % 1000) / 1000.0
            frac2 = ((seed >> (shift + 5)) % 1000) / 1000.0
            angle = frac * 6.283185307
            dist = 30 + frac2 * 12
            points.append((center.x() + dist * math.cos(angle),
                           center.y() + dist * math.sin(angle) * 0.8))
        return points

    def _apply_hit_mask(self):
        """OS-level clickable region: star/halo disc plus label only."""
        cx, cy = pet_geometry.TASK_STAR_CENTER
        radius = halo_geometry.HIT_RADIUS if self.compact_halo else pet_geometry.TASK_STAR_HIT_R
        region = QRegion(QRect(cx - radius, cy - radius, radius * 2,
                               radius * 2), QRegion.Ellipse)
        region = region.united(
            QRegion(self.number_label.geometry()))
        self.setMask(region)

    def is_star_hit(self, local):
        """Whether a widget-local point is an intentional star click."""
        cx, cy = pet_geometry.TASK_STAR_CENTER
        radius = halo_geometry.HIT_RADIUS if self.compact_halo else pet_geometry.TASK_STAR_HIT_R
        dx, dy = local.x() - cx, local.y() - cy
        if dx * dx + dy * dy <= radius * radius:
            return True
        return self.number_label.geometry().contains(local)

    def paintEvent(self, event):
        if self.compact_halo:
            self._paint_compact_star()
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        center = self._star_center()
        cx, cy = center.x(), center.y()
        halo_r = 34.0 * self.halo_radius
        # Static halo: soft blue/violet glow, no box behind the star.
        halo = QRadialGradient(cx, cy, halo_r)
        halo.setColorAt(0.0, QColor(255, 255, 255,
                                    self._alpha(30, self.halo_alpha)))
        halo.setColorAt(0.5, QColor(140, 200, 255,
                                     self._alpha(20, self.halo_alpha)))
        halo.setColorAt(0.85, QColor(140, 130, 255,
                                    self._alpha(9, self.halo_alpha)))
        halo.setColorAt(1.0, QColor(140, 130, 255, 0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(halo)
        painter.drawEllipse(center, halo_r, halo_r)
        # Outer rays: blue-violet edges into icy cyan.
        outer = QPolygonF(self._scaled_points())
        body = QLinearGradient(cx, cy - 30 * self.star_scale,
                               cx, cy + 30 * self.star_scale)
        body.setColorAt(0.0, QColor(208, 194, 255,
                                    self._alpha(235, self.facet_intensity)))
        body.setColorAt(0.5, QColor(245, 249, 255,
                                    self._alpha(235, self.facet_intensity)))
        body.setColorAt(1.0, QColor(137, 165, 255,
                                    self._alpha(235, self.facet_intensity)))
        painter.setBrush(body)
        painter.drawPolygon(outer)
        painter.setPen(Qt.NoPen)
        # Inner facets: pale cyan/lavender, slightly inset.
        inner_pts = [QPointF(cx + (pt.x() - cx) * 0.58,
                             cy + (pt.y() - cy) * 0.58)
                     for pt in self._scaled_points()]
        inner = QLinearGradient(cx, cy - 18 * self.star_scale,
                                cx, cy + 18 * self.star_scale)
        inner.setColorAt(0.0, QColor(216, 246, 255,
                                     self._alpha(230, self.facet_intensity)))
        inner.setColorAt(1.0, QColor(165, 230, 255,
                                     self._alpha(230, self.facet_intensity)))
        painter.setBrush(inner)
        painter.drawPolygon(QPolygonF(inner_pts))
        # Facet glints: vertical highlight + pink-violet edge accent.
        painter.setPen(QPen(QColor(255, 255, 255,
                                          self._alpha(120, self.facet_intensity)), 1.2))
        painter.drawLine(QPointF(cx, cy - 24 * self.star_scale),
                         QPointF(cx, cy + 8 * self.star_scale))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 182, 240,
                                self._alpha(80, self.facet_intensity)))
        accent = QPolygonF([QPointF(cx + 4 * self.star_scale, cy - 14 * self.star_scale),
                            QPointF(cx + 9 * self.star_scale, cy - 4 * self.star_scale),
                            QPointF(cx + 4 * self.star_scale, cy + 2 * self.star_scale)])
        painter.drawPolygon(accent)
        # Brilliant core: white diamond over pale icy fill.
        core_r = pet_geometry.TASK_STAR_CORE_R * self.star_scale
        core = QPolygonF([QPointF(cx, cy - core_r), QPointF(cx + core_r, cy),
                          QPointF(cx, cy + core_r), QPointF(cx - core_r, cy)])
        painter.setBrush(QColor(242, 251, 255,
                                self._alpha(255, self.core_intensity)))
        painter.drawPolygon(core)
        tiny = core_r * 0.45
        spark = QPolygonF([QPointF(cx, cy - tiny), QPointF(cx + tiny, cy),
                           QPointF(cx, cy + tiny), QPointF(cx - tiny, cy)])
        painter.setBrush(QColor(255, 255, 255,
                                self._alpha(255, self.core_intensity)))
        painter.drawPolygon(spark)
        # Micro-sparkles: two tiny diamonds, slot-deterministic.
        for index, (sx, sy) in enumerate(self._sparkle_offsets()):
            r = 2.6 if index == 0 else 2.0
            diamond = QPolygonF([QPointF(sx, sy - r), QPointF(sx + r, sy),
                                 QPointF(sx, sy + r), QPointF(sx - r, sy)])
            painter.setBrush(QColor(220, 240, 255,
                                     self._alpha(200 if index == 0 else 150,
                                                 self.facet_intensity)))
            painter.drawPolygon(diamond)

    def _paint_compact_star(self):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setOpacity(.72 + .28 * (self.depth + 1) / 2)
        cx, cy = pet_geometry.TASK_STAR_CENTER
        glow = QRadialGradient(cx, cy, 22)
        glow.setColorAt(0, QColor(245, 240, 255, 170))
        glow.setColorAt(.35, QColor(173, 156, 255, 95))
        glow.setColorAt(1, QColor(158, 144, 222, 0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(QPointF(cx, cy), 22, 22)
        scale = self.star_scale / .7
        points = [(0, -20), (4, -5), (14, 0), (4, 5),
                  (0, 20), (-4, 5), (-14, 0), (-4, -5)]
        polygon = QPolygonF([QPointF(cx + x * scale, cy + y * scale) for x, y in points])
        fill = QLinearGradient(cx - 12, cy - 20, cx + 12, cy + 20)
        fill.setColorAt(0, QColor('#eee8ff'))
        fill.setColorAt(.38, QColor('#ffffff'))
        fill.setColorAt(.55, QColor('#d6eaff'))
        fill.setColorAt(1, QColor('#a498e0'))
        painter.setPen(QPen(QColor('#9b84ea'), 1.15))
        painter.setBrush(fill)
        painter.drawPolygon(polygon)
        # Alternating cuts keep the crystal legible at its real desktop size.
        painter.setPen(Qt.NoPen)
        center = QPointF(cx, cy)
        for index, color in ((0, '#d7cafa'), (2, '#a4bce9'),
                             (4, '#b4a0e5'), (6, '#f5f2ff')):
            painter.setBrush(QColor(color))
            painter.drawPolygon(QPolygonF([center, polygon[index], polygon[index + 1]]))
        painter.setPen(QPen(QColor(255, 255, 255, 230), .7))
        painter.drawLine(polygon[0], polygon[4])
        painter.drawLine(polygon[2], polygon[6])
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor('#ffffff'))
        painter.drawEllipse(center, 1.4, 1.4)
        # The medallion stays inside the already verified number hit strip.
        badge_y = cy + halo_geometry.LABEL_TOP + halo_geometry.LABEL_HEIGHT / 2
        badge = QLinearGradient(cx, badge_y - 6, cx, badge_y + 6)
        badge.setColorAt(0, QColor('#44405e'))
        badge.setColorAt(1, QColor('#24233c'))
        painter.setBrush(badge)
        painter.setPen(QPen(QColor('#dcc6a6'), .8))
        painter.drawEllipse(QPointF(cx, badge_y), 8, 6.2)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(218, 210, 249, 100), .5))
        painter.drawEllipse(QPointF(cx, badge_y), 6.5, 4.7)

    def refresh(self, number_text, provider_name, language):
        """Update visible identity text. Values only, never raw sources."""
        self._number = number_text
        self.number_label.setText(number_text)
        tip = (f'{text("task_panel_label", language, n=number_text)} · '
               f'{provider_name} · {text("working", language)}')
        self.setToolTip(tip)
        self.setWindowTitle(text('task_panel_label', language, n=number_text))
        self.setAccessibleName(text('task_accessible', language,
                                   label=self.windowTitle(), provider=provider_name))
        self.update()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space) and self.manager:
            self.manager.orb_activated(self.identity, keyboard=True)
            event.accept()
        elif event.key() == Qt.Key_Escape and self.manager:
            self.manager.collapse_detail()
            event.accept()
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if not self.is_star_hit(event.position().toPoint()):
                event.ignore()
                return
            self._press_global = event.globalPosition().toPoint()
            self._press_offset = self._press_global - self.pos()
            self._dragging = False
            manager = self.manager
            if manager is not None:
                try:
                    manager.add_press_hold(self.identity)
                except Exception:
                    pass
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (event.buttons() & Qt.LeftButton and self._press_global is not None
                and self._press_offset is not None):
            delta = event.globalPosition().toPoint() - self._press_global
            if delta.manhattanLength() > pet_geometry.TASK_ORB_DRAG_THRESHOLD_PX:
                # Collapsed stars are not draggable: a genuine move
                # suppresses the click and repositions nothing.
                self._dragging = True
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._press_global is not None:
            if not self._dragging:
                manager = self.manager
                if manager is not None:
                    try:
                        manager.orb_activated(self.identity)
                    except Exception:
                        pass
            manager = self.manager
            if manager is not None:
                try:
                    manager.release_press_hold(self.identity)
                except Exception:
                    pass
            self._press_global = None
            self._press_offset = None
            self._dragging = False
        super().mouseReleaseEvent(event)

    def enterEvent(self, event):
        manager = self.manager
        if manager is not None:
            try:
                manager.add_hover_hold(self.identity)
            except Exception:
                pass
        super().enterEvent(event)

    def leaveEvent(self, event):
        manager = self.manager
        if manager is not None:
            try:
                manager.release_hover_hold(self.identity)
            except Exception:
                pass
        super().leaveEvent(event)

    def panel_text(self):
        """All user-visible star text, for privacy assertions."""
        return '\n'.join((self.number_label.text(), self.toolTip(),
                          self.windowTitle()))


def _plan_parking_routes(inputs):
    """Pure scheduler over immutable pixels; never reads a manager or Qt object."""
    (start_items, home_items, static_items, signature, pet_rect, screen_rect,
     cooperative) = inputs
    starts, homes = dict(start_items), dict(home_items)
    # Windows native Qt calls repeatedly release/reacquire the GIL. Yield at
    # bounded pixel batches so a CPU planner cannot delay those GUI callbacks.
    # sleep(0) did not let native callbacks reacquire the GIL on Windows. One
    # millisecond per bounded batch gives those callbacks a scheduling window.
    yield_work = (lambda: time.sleep(pet_geometry.PARKING_WORK_YIELD_S)) if cooperative else None
    # Partition first: survivors already home hold still visibly
    # (no glide, never staged); only genuine movers enter path
    # validation. Otherwise the greedy drop would stage the very
    # stars that must glide while "parking" stars going nowhere.
    still = set()
    moving = []
    for key in starts:
        if (math.hypot(homes[key][0] - starts[key][0],
                        homes[key][1] - starts[key][1]) < 1.0):
            still.add(key)
        else:
            moving.append(key)
    static = dict(static_items)
    for key in still:
        static[key] = pet_geometry.star_center_to_window_position(*homes[key])

    ordered = sorted(moving)
    paths = {}
    failed = set()

    def schedule(parked):
        if len(parked) == len(ordered):
            return []
        if parked in failed or len(failed) >= 256:
            return None
        for key in ordered:
            if key in parked:
                continue
            cache_key = (parked, key)
            if cache_key not in paths:
                context = dict(static)
                context.update({
                    other: pet_geometry.star_center_to_window_position(
                        *(homes[other] if other in parked else starts[other]))
                    for other in ordered if other != key})
                paths[cache_key] = pet_geometry.parking_route(
                    pet_geometry.star_center_to_window_position(*starts[key]),
                    pet_geometry.star_center_to_window_position(*homes[key]),
                    context, pet_rect, screen_rect, yield_work=yield_work)
            path = paths[cache_key]
            if path is None:
                continue
            tail = schedule(parked | {key})
            if tail is not None:
                return [(key, path)] + tail
        failed.add(parked)
        return None

    complete = schedule(frozenset())
    if not complete:
        if not ordered:
            return None
        # Invalid endpoints or a bounded route-search failure preserve the
        # exact visible frame; changed geometry/membership can retry.
        return {
            'signature': signature, 'blocked': 'no_safe_parking_schedule',
            't': 0.0, 'dur': 0.0, 'starts': dict(starts), 'windows': {},
            'homes': dict(homes), 'pet_rect': pet_rect,
            'screen_rect': screen_rect, 'deferred': set(ordered)}
    else:
        windows, routes = {}, {}
        cursor = 0.0
        for key, path in complete:
            distances = [0]
            for first, last in zip(path, path[1:]):
                distances.append(distances[-1] + abs(last[0] - first[0])
                                 + abs(last[1] - first[1]))
            # Manhattan length budgets diagonal pixels and quantization.
            duration = max(
                pet_geometry.RING_BLEND_MIN_S,
                distances[-1] * pet_geometry.RING_BLEND_EASE_PEAK
                * pet_geometry.RING_BLEND_FRAME_S
                / pet_geometry.RING_BLEND_TARGET_PX_PER_FRAME)
            windows[key] = (cursor, duration)
            routes[key] = (tuple(path), tuple(distances))
            cursor += duration
        return {
            'signature': signature, 't': 0.0, 'dur': cursor,
            'starts': {key: starts[key] for key, _ in complete},
            'windows': windows, 'routes': routes,
            'homes': {key: homes[key] for key, _ in complete},
            'pet_rect': pet_rect, 'screen_rect': screen_rect,
            'deferred': set()}


class TaskPageControls(QWidget):
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(theme.SURFACE_TOP))
        painter.setPen(QPen(QColor(theme.BORDER_CONTROL), 1))
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(.5, .5, -.5, -.5), 14, 14)


class TaskPanelManager(HaloScene):
    """Own stable task Stars, task-local detail and the compact halo scene.

    Current motion uses a fitted projected ellipse, shared phase and depth
    layers. Autonomous pose/membership changes retain exact boundary pixels
    and bounded steps; intentional pet movement transports the attached scene.
    The exterior route implementation is retained only for explicit historical
    regression fixtures, never for a product preference.
    """

    def __init__(self, panel, *, legacy_exterior_motion=False):
        self.panel = panel
        # Only historical exterior-route fixtures opt in; no product setting.
        self.legacy_exterior_motion = legacy_exterior_motion
        self._shutdown = False
        self._universe = {}
        self._labels = {}
        self._slots = {}
        self._windows = {}
        self._placed = {}
        self._ring_slots = []
        self._orbit = {}
        self._orbit_t = {}
        self._arc_dirs = {}
        self._ring_offsets = {}
        self._ring_t = 0.0
        self._ring_blend = None
        self._park_blend = None
        self._park_plan_revision = 0
        self._park_plan_request = None
        self._park_plan_job = None
        self._ring_staged = set()
        self._hover_holds = set()
        self._press_holds = set()
        self._motion_t = 0.0
        self._last_tick = None
        self._hovered = None
        self._orbit_mode = ('static',)
        self._last_motion_enabled = None
        self._last_pet_rect = None
        self._last_screen_rect = None
        self._last_tick_center = None
        self._last_generation = None
        self._visible = True
        self.page_index = 0
        self._page_keys = []
        self.page_controls = None
        self.last_activated = None
        self.detail_window = None
        self.detail_transition = DetailTransition(panel)
        self.expanded_identity = None
        self.expanded_anchor = None
        self._expansion_geometry = None
        self._expansion_dirty = False
        self._task_preference = 'auto'
        self._task_language = DEFAULT_LANGUAGE
        self.motion_timer = QTimer()
        self.motion_timer.setInterval(pet_geometry.MOTION_TICK_MS)
        self.motion_timer.timeout.connect(self._on_motion_timeout)
        self.trail_overlay = TrailOverlay()
        if not self.legacy_exterior_motion:
            self.trail_overlay.close()
            self._init_halo()

    def window_identities(self):
        return sorted(self._windows)

    def window_for(self, identity):
        return self._windows.get(identity)

    def slot_for(self, identity):
        return self._slots.get(identity)

    def label_number_for(self, identity):
        return self._labels.get(identity)

    def window_count(self):
        return len(self._windows)

    def task_identities(self):
        return sorted(self._universe, key=lambda k: self._slots[k])

    def total_task_count(self):
        return len(self._page_keys)

    @property
    def page_count(self):
        return max(1, math.ceil(self.total_task_count() / halo_geometry.MAX_SAFE_STARS))

    def set_page(self, index):
        if self._shutdown or self.legacy_exterior_motion:
            return
        index = max(0, min(int(index), self.page_count - 1))
        if index == self.page_index:
            return
        self.collapse_detail(replan=False)
        self.page_index = index
        self.apply_snapshot(list(self._universe.values()), self._task_preference,
                            self._last_generation, self._task_language,
                            self._last_pet_rect, self._last_screen_rect)

    def activate_task(self, identity, keyboard=False):
        if identity not in self._page_keys or self._shutdown:
            return
        if not self.legacy_exterior_motion:
            self.set_page(self._page_keys.index(identity) // halo_geometry.MAX_SAFE_STARS)
        self.orb_activated(identity, keyboard=keyboard)

    def _update_page_controls(self):
        if self.legacy_exterior_motion:
            return
        if self.page_controls is None and self.total_task_count() > halo_geometry.MAX_SAFE_STARS:
            self.page_controls = TaskPageControls(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
            self.page_controls.setAttribute(Qt.WA_ShowWithoutActivating)
            self.page_controls.setAttribute(Qt.WA_TranslucentBackground)
            self.page_controls.setObjectName('pages')
            self.page_controls.setStyleSheet(STYLE)
            row = QHBoxLayout(self.page_controls)
            row.setContentsMargins(4, 1, 4, 1)
            self.page_previous = QPushButton('‹')
            self.page_next = QPushButton('›')
            self.page_caption = QLabel()
            self.page_caption.setAlignment(Qt.AlignCenter)
            for control, direction in ((self.page_previous, -1), (self.page_next, 1)):
                control.setFixedWidth(28)
                control.clicked.connect(lambda checked=False, d=direction: self.set_page(self.page_index + d))
            row.addWidget(self.page_previous)
            row.addWidget(self.page_caption, 1)
            row.addWidget(self.page_next)
            self.page_controls.setFixedSize(168, 32)
        if self.page_controls is None:
            return
        start = self.page_index * halo_geometry.MAX_SAFE_STARS + 1
        end = min(start + halo_geometry.MAX_SAFE_STARS - 1, self.total_task_count())
        self.page_caption.setText(f'{start}–{end} / {self.total_task_count()}')
        self.page_previous.setEnabled(self.page_index > 0)
        self.page_next.setEnabled(self.page_index + 1 < self.page_count)
        zh = self._task_language == 'zh_CN'
        self.page_previous.setAccessibleName('上一页任务' if zh else 'Previous task page')
        self.page_next.setAccessibleName('下一页任务' if zh else 'Next task page')
        self.page_controls.setToolTip('全部任务可在 Usage Panel 的任务菜单中直接选择' if zh else 'Select any task directly from the Usage Panel task menu')
        x, y, width, height = self._last_pet_rect
        pose = self._halo_pose or self._fit_halo_pose(self._last_pet_rect, self._last_screen_rect)
        left, top, right, bottom = halo_geometry.projected_bounds(pose)
        left, top = min(left, x), min(top, y)
        right, bottom = max(right, x + width), max(bottom, y + height)
        candidates = ((round(pose.cx - 84), math.ceil(bottom) + 8),
                      (round(pose.cx - 84), math.floor(top) - 40),
                      (math.ceil(right) + 8, round(pose.cy - 16)),
                      (math.floor(left) - 176, round(pose.cy - 16)))
        area = QRect(self._last_screen_rect[0], self._last_screen_rect[1],
                     self._last_screen_rect[2] - self._last_screen_rect[0] + 1,
                     self._last_screen_rect[3] - self._last_screen_rect[1] + 1)
        position = next((p for p in candidates if area.contains(QRect(*p, 168, 32))), None)
        # When no adjacent strip fits, the Hub menu still exposes every task.
        # An opaque pager must never cover the ring's interactive numbers.
        if position is not None:
            self.page_controls.move(*position)
        on_top = bool((getattr(self.panel, 'prefs', None) or {}).get('always_on_top', True))
        if bool(self.page_controls.windowFlags() & Qt.WindowStaysOnTopHint) != on_top:
            self.page_controls.setWindowFlag(Qt.WindowStaysOnTopHint, on_top)
        self.page_controls.setVisible(position is not None and self._visible
                                      and self.total_task_count() > halo_geometry.MAX_SAFE_STARS)

    def label_text(self, identity, language):
        return text('task_panel_label', language, n=self._labels.get(identity, 0))

    def _claim_number(self, taken):
        number = 1
        while number in taken:
            number += 1
        return number

    def _anchor(self):
        """Live (pet_rect, screen_rect) for placement; pure otherwise."""
        panel = self.panel
        pet = getattr(panel, 'pet', None)
        source = pet if pet is not None else panel
        geometry = source.geometry()
        pet_rect = (geometry.x(), geometry.y(), geometry.width(), geometry.height())
        screen = (QApplication.screenAt(geometry.center())
                  or QApplication.primaryScreen())
        r = screen.availableGeometry()
        screen_rect = (r.left(), r.top(), r.right(), r.bottom())
        if (pet is not None and not self.legacy_exterior_motion
                and getattr(pet, 'halo_screen_rect', None) != screen_rect):
            pet.move_clamped(pet.pos())
            g = pet.geometry()
            pet_rect = (g.x(), g.y(), g.width(), g.height())
        return pet_rect, screen_rect

    def apply_snapshot(self, tasks, preference='auto', generation=None,
                       language=None, pet_rect=None, screen_rect=None):
        """Apply one authoritative accepted task list.

        Late generations (older than the last applied) never resurrect
        retired orbs and never overwrite newer UI-owned position state.
        Every visible task gets exactly one orb; surviving orbs are
        reused in place and only retired keys close. User drag
        overrides are never moved by normal refreshes. Returns the
        ordered visible orb identities.
        """
        if self._shutdown:
            return []
        if (generation is not None and self._last_generation is not None
                and generation < self._last_generation):
            return self.window_identities()
        if generation is not None:
            self._last_generation = generation
        language = normalize_language(language or DEFAULT_LANGUAGE)
        preference = normalize_tracking_provider(preference)
        self._task_preference = preference
        self._task_language = language
        previous_keys = set(self._windows)
        seen = {}
        for task in tasks or []:
            if (task or {}).get('provider_id') == 'codex':
                seen[task_identity(task)] = task
        for key, task in seen.items():
            self._universe[key] = task
        retired = [k for k in self._universe if k not in seen]
        for key in retired:
            self._universe.pop(key, None)
        card = self.detail_window
        if (self.detail_transition.running and card is not None and card.entry is not None
                and task_identity(card.entry) not in self._universe):
            self.detail_transition.cancel()
        for key in [k for k in self._labels if k not in self._universe]:
            self._labels.pop(key, None)
            self._slots.pop(key, None)
            self._placed.pop(key, None)
            self._orbit.pop(key, None)
            self._orbit_t.pop(key, None)
            self._ring_offsets.pop(key, None)
        for task in order_tasks(list(self._universe.values())):
            key = task_identity(task)
            if key not in self._labels:
                self._labels[key] = self._claim_number(set(self._labels.values()))
            if key not in self._slots:
                self._slots[key] = self._claim_number(set(self._slots.values()))
        ordered_universe = order_tasks(list(self._universe.values()))
        wanted = [t for t in filter_tasks_for_preference(ordered_universe, preference)]
        self._page_keys = sorted((task_identity(t) for t in wanted), key=lambda k: self._slots[k])
        if not self.legacy_exterior_motion:
            self._visible = bool((getattr(self.panel, 'prefs', None) or {}).get('star_ring_enabled', True))
            self.page_index = min(self.page_index, self.page_count - 1)
            if self.expanded_identity in self._page_keys:
                self.page_index = self._page_keys.index(self.expanded_identity) // halo_geometry.MAX_SAFE_STARS
            page_keys = set(self._page_keys[self.page_index * halo_geometry.MAX_SAFE_STARS:
                                            (self.page_index + 1) * halo_geometry.MAX_SAFE_STARS])
            wanted = [t for t in wanted if task_identity(t) in page_keys]
        wanted_keys = [task_identity(t) for t in wanted]
        if self.expanded_identity is not None and self.expanded_identity not in wanted_keys:
            self.collapse_detail(replan=False)
        self._ring_slots = sorted(self._slots[k] for k in wanted_keys
                                  if k in self._slots)
        for key in [k for k in self._windows if k not in wanted_keys]:
            orb = self._windows.pop(key)
            self._placed.pop(key, None)
            self._orbit.pop(key, None)
            self._orbit_t.pop(key, None)
            self._arc_dirs.pop(key, None)
            self._ring_offsets.pop(key, None)
            # Filter-hide and retire share this loop: interaction
            # holds are visibility-local, so a hidden surface can
            # never keep the ring paused (no mouse-leave will come).
            self.release_hover_hold(key)
            self.release_press_hold(key)
            # Staged recovery bookkeeping is visibility-local too: a
            # filtered/retired key leaves the pending set with it.
            self._ring_staged.discard(key)
            if self.trail_overlay.drop(key):
                # The retired ribbon must vanish at once: the overlay
                # stays up for surviving trails, so erase explicitly.
                self.trail_overlay.update()
            try:
                orb.close()
                orb.deleteLater()
            except Exception:
                pass
        self._reconcile_holds()
        if pet_rect is None or screen_rect is None:
            live_pet, live_screen = self._anchor()
            pet_rect = live_pet if pet_rect is None else pet_rect
            screen_rect = live_screen if screen_rect is None else screen_rect
        prev_pet_rect = getattr(self, '_last_pet_rect', None)
        prev_screen_rect = getattr(self, '_last_screen_rect', None)
        if (self.expanded_identity is not None
                and (tuple(pet_rect), tuple(screen_rect)) != self._expansion_geometry):
            self._expansion_dirty = True
            self.collapse_detail(replan=False)
        self._last_pet_rect = pet_rect
        self._last_screen_rect = screen_rect
        self._update_page_controls()
        on_top = bool((getattr(self.panel, 'prefs', None) or {}).get('always_on_top', True))
        for task in wanted:
            key = task_identity(task)
            orb = self._windows.get(key)
            if orb is None:
                orb = TaskOrbWindow(key, provider_id=task.get('provider_id'),
                                    manager=self)
                self._windows[key] = orb
            if bool(orb.windowFlags() & Qt.WindowStaysOnTopHint) != on_top:
                visible, position = orb.isVisible(), orb.pos()
                orb.setWindowFlag(Qt.WindowStaysOnTopHint, on_top)
                orb.move(position)
                if visible and self._visible:
                    orb.show()
            orb.refresh(str(self._labels[key]),
                        PROVIDER_NAMES.get(task.get('provider_id'),
                                           task.get('provider_id')),
                        language)
        if self.expanded_identity is not None:
            newcomers = set(wanted_keys) - previous_keys
            self._stage_keys(newcomers)
            self._expansion_dirty |= (set(wanted_keys) != previous_keys
                                      or self._motion_enabled() != self._last_motion_enabled)
            self._refresh_detail()
            return self.window_identities()
        if not self.legacy_exterior_motion:
            self._halo_apply(pet_rect, screen_rect)
            return self.window_identities()
        self._compute_orbit_params(pet_rect, screen_rect)
        previous_motion = (self._orbit_mode, self._ring_offsets)
        self._orbit_mode = self._select_orbit_mode(pet_rect, screen_rect)
        # Selection before show: newly created stars are exposed only
        # at their selected orbit position, never at a static home.
        self._maybe_start_blend(previous_motion[0], previous_motion[1],
                                pet_rect, screen_rect,
                                prev_pet_rect, prev_screen_rect)
        motion_changed = (self._motion_enabled()
                          != self._last_motion_enabled)
        self._last_motion_enabled = self._motion_enabled()
        if not self._motion_enabled() and self._windows:
            # ON->OFF through an apply: survivors glide home from
            # exact current pixels (frame zero); newcomers appear at
            # homes via the place path below. Never snap.
            self._begin_park_glide(pet_rect, screen_rect)
        self._place_all(wanted_keys, pet_rect, screen_rect)
        for task in wanted:
            orb = self._windows.get(task_identity(task))
            if orb is None:
                continue
            if task_identity(task) in self._ring_staged:
                # Staged newcomers stay hidden until revealed at
                # their final slots; never flash them beforehand.
                continue
            if self._visible:
                orb.show()
            else:
                orb.hide()
        if (self._orbit_mode, self._ring_offsets) != previous_motion:
            # Recomposition (ring in/out, new radius, new spacing):
            # never paint a streak between the old path and the new.
            self._clear_trails()
        if motion_changed:
            # Motion OFF->ON/OFF toggles swap geometry spaces
            # (static homes vs animated ring): stale ribbons must not
            # bridge the two.
            self._clear_trails()
        if not self._windows:
            self.stop_motion()
            self._clear_trails()
            try:
                if self.trail_overlay.isVisible():
                    self.trail_overlay.hide()
            except Exception:
                pass
        return self.window_identities()

    def _auto_home(self, key, pet_rect, screen_rect):
        """Deterministic static ring home for a lifetime slot."""
        return pet_geometry.star_ring_anchor(
            self._ring_slots or [self._slots[key]], self._slots[key],
            pet_rect, screen_rect)

    def _place_all(self, wanted_keys, pet_rect, screen_rect):
        """Move every visible orb to its authoritative nominal position.

        First placement lands directly on the selected path (no home
        flash); refreshes with unchanged clocks are exact no-ops (no
        yank); pet moves ride the new hub rigidly. Same math as the
        animation tick, so placement and motion can never disagree by
        one frame.

        Keys covered by an active parking glide are skipped: their
        exact current positions are frame zero and ticks own them.
        Staged (hidden) newcomers are skipped too: they stay inert
        until a validated reveal exposes them, never pre-moved into
        an unvalidated home. Ring-blend survivors need no skip: the
        cartesian commit makes placement at blend start a proven
        no-op.
        """
        if self.expanded_identity is not None:
            return
        nominal, _ = self._nominal_positions(pet_rect, screen_rect)
        parked = (self._park_blend['starts']
                  if self._park_blend is not None else {})
        for key in wanted_keys:
            if key in parked or key in self._ring_staged:
                continue
            pos = nominal.get(key)
            orb = self._windows.get(key)
            if pos is None or orb is None:
                continue
            if self._placed.get(key) != pos:
                self._placed[key] = pos
                orb.move(*pos)

    def _static_center(self, key, pet_rect, screen_rect):
        """Home center for one star (parking + static-mode anchor)."""
        params = self._orbit.get(key)
        if params is not None:
            pcx = pet_rect[0] + pet_rect[2] / 2.0
            pcy = pet_rect[1] + pet_rect[3] / 2.0
            return pet_geometry.orbit_center_at(
                pcx, pcy, params['radius'], params['radius'],
                params['base_deg'])
        return self._home_center(key, pet_rect, screen_rect)

    def _nominal_positions(self, pet_rect, screen_rect, ring_t=None,
                           orbit_times=None, blend_t=None):
        """Authoritative window+center positions for the current mode.

        Single math source for first placement, animation ticks, and
        refresh. Ring uses the shared active-time phase plus slot
        offsets (blend-interpolated while recomposing); arc uses
        per-key clocks with the hovered star frozen; static or
        motion-disabled uses homes. Returns ({key: window},
        {key: float center}).
        """
        if not self.legacy_exterior_motion:
            centers, _ = self._halo_positions()
            return ({k: pet_geometry.star_center_to_window_position(*v)
                     for k, v in centers.items()}, centers)
        mode = self._orbit_mode
        kind = mode[0] if isinstance(mode, tuple) else 'static'
        pcx = pet_rect[0] + pet_rect[2] / 2.0
        pcy = pet_rect[1] + pet_rect[3] / 2.0
        windows = {}
        centers = {}
        if not self._motion_enabled():
            kind = 'static'
        if kind == 'ring':
            rt = self._ring_t if ring_t is None else ring_t
            omega = 2.0 * math.pi / mode[3]
            phase = mode[5] + mode[4] * math.degrees(omega * rt)
            blend = self._ring_blend
            bt = blend['t'] if blend is not None else 0.0
            if blend_t is not None:
                bt = blend_t
            for key in self._windows:
                if key in self._ring_staged:
                    # Staged newcomers are hidden pending reveal:
                    # excluded from motion, validity, and trails
                    # until they join the visible ring.
                    continue
                target = phase + self._ring_offsets.get(key, 0.0)
                if blend is not None:
                    start_center = blend.get('start_centers', {}).get(key)
                    start = blend.get('start', {}).get(key)
                    if start_center is not None and start is not None:
                        # Chase-path continuity glide: the angle eases
                        # toward the live ring target while the center
                        # chases the advancing ring point. Frame zero is
                        # the exact visible position (ease(0) == 0, so
                        # placement at blend start is a proven no-op),
                        # arrival is the exact ring target, and the
                        # spiral-like path routes around the hub instead
                        # of cutting straight chords through it.
                        ease = pet_geometry.ring_blend_ease(
                            bt / blend['dur'])
                        delta = pet_geometry.ring_shortest_delta_deg(
                            start, target)
                        center = self._chase_point(
                            start_center, start, delta, ease,
                            (pcx, pcy), mode[1], mode[2])
                    elif start is not None:
                        ease = pet_geometry.ring_blend_ease(
                            bt / blend['dur'])
                        delta = pet_geometry.ring_shortest_delta_deg(
                            start, target)
                        theta = start + ease * delta
                        center = pet_geometry.orbit_center_at(
                            pcx, pcy, mode[1], mode[2], theta)
                    else:
                        theta = target
                        center = pet_geometry.orbit_center_at(
                            pcx, pcy, mode[1], mode[2], theta)
                else:
                    theta = target
                    center = pet_geometry.orbit_center_at(
                        pcx, pcy, mode[1], mode[2], theta)
                centers[key] = center
                windows[key] = (
                    pet_geometry.star_center_to_window_position(
                        center[0], center[1]))
        elif kind == 'arc':
            times = self._orbit_t if orbit_times is None else orbit_times
            omega = 2.0 * math.pi / mode[2]
            for key, orb in self._windows.items():
                if key in self._ring_staged:
                    # Staged newcomers are hidden pending reveal:
                    # excluded from motion, validity, and trails
                    # until they join the visible arc (same rule as
                    # the ring branch above).
                    continue
                params = self._orbit.get(key)
                if key == self._hovered or params is None:
                    windows[key] = (orb.x(), orb.y())
                    centers[key] = (orb.x() + 56.0, orb.y() + 48.0)
                    continue
                cycle = ((omega * times.get(key, 0.0))
                         % (2.0 * math.pi)) / (2.0 * math.pi)
                theta = pet_geometry.arc_angle_at(
                    params['base_deg'], mode[1],
                    self._arc_dirs.get(key, +1), cycle)
                center = pet_geometry.orbit_center_at(
                    pcx, pcy, params['radius'], params['radius'], theta)
                centers[key] = center
                windows[key] = (
                    pet_geometry.star_center_to_window_position(
                        center[0], center[1]))
        else:
            for key in self._windows:
                if key in self._ring_staged:
                    # Staged newcomers are hidden pending reveal:
                    # excluded from motion, validity, and trails
                    # until they join the visible set (same rule as
                    # the ring/arc branches above).
                    continue
                center = self._static_center(key, pet_rect, screen_rect)
                centers[key] = center
                windows[key] = (
                    pet_geometry.star_center_to_window_position(
                        center[0], center[1]))
        return windows, centers

    @staticmethod
    def _chase_point(start_center, start_angle, delta, ease, hub,
                     radius_x, radius_y):
        """One chase-path center: angle eases toward the ring target
        while the center chases the advancing ring point.

        Frame zero is the exact start (ease == 0) and arrival is the
        exact ring target (ease == 1); the spiral-like path routes
        around the hub instead of cutting chords through it. Shared
        by the runtime, the commit-time budget sampler, and the
        plan-time path validator so all three agree exactly.
        """
        chase = pet_geometry.orbit_center_at(
            hub[0], hub[1], radius_x, radius_y,
            start_angle + ease * delta)
        return (start_center[0] + ease * (chase[0] - start_center[0]),
                start_center[1] + ease * (chase[1] - start_center[1]))

    @staticmethod
    def _clamped_dt(dt):
        """Bound one tick's active-time advance to a single frame.

        A delayed timer callback (process hibernate, debugger pause,
        CI stall) must never apply hidden elapsed time as one large
        visible step: ring phase, blend progress, parking progress,
        arc clocks, and breathing all share this bound, so a 5 s gap
        advances at most one nominal 40 ms frame and the next tick
        resumes from there. The excess is discarded (clocks reset to
        the callback time), never caught up, so no giant first trail
        segment is possible either.
        """
        if dt <= 0.0:
            return 0.0
        return min(dt, pet_geometry.RING_BLEND_FRAME_S)

    def _validate_path_frames(self, points_at, movers, static_windows,
                              pet_rect, screen_rect, fractions=25):
        """Sample a planned transition path against footprint rules.

        points_at(progress) returns {key: float center} for the
        movers at linear progress 0..1 (each policy applies its own
        easing); static_windows are integer windows that hold still
        (newcomers already at targets, parked newcomers at homes).
        Every sampled frame — including both endpoints — must
        validate as one complete set. Pure: commits nothing.
        """
        for step in range(fractions + 1):
            progress = step / fractions
            centers = points_at(progress)
            frame = dict(static_windows)
            for key, center in centers.items():
                frame[key] = (
                    pet_geometry.star_center_to_window_position(
                        center[0], center[1]))
            if not self._nominal_valid(frame, pet_rect, screen_rect):
                return False
        return True

    def _greedy_path_subset(self, movers, delta_of, validate):
        """Largest lead-mover subset whose path validates end to end.

        Drops the longest-travel mover first (deterministic tie-break
        by identity): crossing paths in crowded order-mismatched sets
        come from long angular hauls. Returns the surviving ordered
        list, possibly empty (caller stages the dropped remainder and
        reveals it through the validated atomic reveal path).
        """
        candidates = list(movers)
        while candidates and not validate(candidates):
            candidates.sort()
            dropped = max(
                candidates,
                key=lambda key: (abs(delta_of(key)), key))
            candidates = [k for k in candidates if k != dropped]
        return candidates

    def _plan_direct_blend(self, starts, newcomers, pet_rect,
                             screen_rect):
        """One safe base rotation, or None (hard frame-0 rejection).

        Scores whole-pattern base rotations (per-survivor anchors
        plus circular midpoints) by survivor travel, but a candidate
        whose arrival frame violates the final footprint rules is
        DISCARDED — not ranked last, never returned — even when every
        candidate fails. Returns (phi, travels) or None when no
        direct blend is safe. Pure planning: commits nothing
        (offsets, clocks, and windows untouched).
        """
        mode = self._orbit_mode
        hub = (pet_rect[0] + pet_rect[2] / 2.0,
               pet_rect[1] + pet_rect[3] / 2.0)
        omega = 2.0 * math.pi / mode[3]
        phase = mode[5] + mode[4] * math.degrees(omega * self._ring_t)
        ordered = sorted(starts)
        if not ordered:
            return None
        anchors = []
        for anchor in ordered:
            anchors.append(pet_geometry.ring_shortest_delta_deg(
                phase + self._ring_offsets[anchor], starts[anchor]))
        # Anchor alignments plus circular midpoints between them:
        # the minimax rotation often sits between anchors (e.g. half
        # the gap), which anchors alone would miss. Anchors evaluate
        # first so exact alignments win ties deterministically.
        candidates = list(anchors)
        uniq = sorted(set(anchors))
        for first, second in zip(uniq, uniq[1:] + uniq[:1]):
            half = pet_geometry.ring_shortest_delta_deg(first, second)
            if abs(half) > 1e-9:
                candidates.append(first + half / 2.0)
        best = None
        for phi in candidates:
            travels = {}
            for key in ordered:
                travels[key] = abs(
                    pet_geometry.ring_shortest_delta_deg(
                        starts[key], phase + phi
                        + self._ring_offsets[key]))
            # Frame-0 check: survivors sit where they are while
            # newcomers appear at this candidate's targets. A
            # candidate that overlaps on arrival (e.g. bulk appear on
            # a survivor's current slot) is discarded, never ranked.
            frame = {key: (self._windows[key].x(), self._windows[key].y())
                     for key in ordered}
            for key in newcomers:
                theta = phase + phi + self._ring_offsets[key]
                center = pet_geometry.orbit_center_at(
                    hub[0], hub[1], mode[1], mode[2], theta)
                frame[key] = (
                    pet_geometry.star_center_to_window_position(
                        center[0], center[1]))
            if not self._nominal_valid(frame, pet_rect, screen_rect):
                continue
            cost = (max(travels.values()), sum(travels.values()))
            if best is None or cost < best[0]:
                best = (cost, phi, travels)
            # Strict improvement only: earlier candidates (anchors,
            # lowest slot first) win ties deterministically.
        if best is None:
            return None
        return best[1], best[2]

    def _commit_blend_plan(self, starts, phi, travels, hub):
        """Install a planned survivor glide: sub-pixel changes
        place directly, else rebase the shared phase so targets absorb
        the rotation and run an easing-aware adaptive duration.

        The glide eases angle and center together along a chase
        path (not angle-only): a static home far off the ring
        radius travels continuously instead of snapping radially,
        routing around the hub rather than cutting chords through
        it. Duration derives from the longest budgeted chase
        polyline, so the eased peak frame step keeps the D2B frame
        budget by construction. Takes over any parking glide (at most
        one transition blend is ever active)."""
        self._park_blend = None
        if not travels:
            self._ring_blend = None
            return
        mode = self._orbit_mode
        rate = mode[4] * 360.0 / mode[3]
        if rate:
            self._ring_t = self._ring_t + phi / rate
        omega = 2.0 * math.pi / mode[3]
        phase = (mode[5] + mode[4]
                 * math.degrees(omega * self._ring_t))
        start_centers = {}
        max_dist = 0.0
        for key in travels:
            orb = self._windows.get(key)
            if orb is None:
                continue
            current = (orb.x() + 56.0, orb.y() + 48.0)
            start_centers[key] = current
            goal = pet_geometry.orbit_center_at(
                hub[0], hub[1], mode[1], mode[2],
                phase + self._ring_offsets.get(key, 0.0))
            chord = math.hypot(goal[0] - current[0],
                               goal[1] - current[1])
            # Budget against the actual chase polyline (angle and
            # center ease together, so the path can exceed the
            # straight chord): sampled deterministically at commit
            # time, so the eased peak frame step keeps the D2B frame
            # budget without sluggish overestimates.
            start = starts.get(key)
            if start is not None:
                delta = pet_geometry.ring_shortest_delta_deg(
                    start, phase + self._ring_offsets.get(key, 0.0))
                path = 0.0
                prev_point = current
                for step in range(1, 26):
                    ease = pet_geometry.ring_blend_ease(step / 25.0)
                    point = self._chase_point(
                        current, start, delta, ease, hub,
                        mode[1], mode[2])
                    path += math.hypot(point[0] - prev_point[0],
                                       point[1] - prev_point[1])
                    prev_point = point
                # Keep the larger of the sampled walk and the straight
                # chord so sampling can never shrink the budget below
                # the true end-to-end displacement.
                max_dist = max(max_dist, path, chord)
            else:
                max_dist = max(max_dist, chord)
        if max(travels.values()) < 0.5 and max_dist < 1.0:
            self._ring_blend = None
            return
        self._ring_blend = {
            't': 0.0,
            'dur': pet_geometry.ring_blend_duration_s(max_dist),
            'hub': hub,
            'start': starts,
            'start_centers': start_centers}

    def _park_survivors(self, pet_rect, screen_rect):
        """Visible survivors that must glide home (never newcomers).

        Staged (hidden) orbs and never-placed newcomers are excluded:
        they appear at homes through the normal place path, which is
        an appearance, not motion. Only previously positioned,
        currently visible-geometry survivors glide.
        """
        survivors = []
        for key, orb in self._windows.items():
            if key in self._ring_staged:
                continue
            if key not in self._placed:
                continue
            survivors.append(key)
        return survivors

    def _max_home_distance(self, keys, pet_rect, screen_rect):
        """Longest current-center to static-home distance (float px)."""
        peak = 0.0
        for key in keys:
            orb = self._windows.get(key)
            if orb is None:
                continue
            home = self._home_center(key, pet_rect, screen_rect)
            peak = max(peak, math.hypot(
                orb.x() + 56.0 - home[0], orb.y() + 48.0 - home[1]))
        return peak

    def _begin_park_glide(self, pet_rect, screen_rect):
        """Start a finite parking glide from exact visible positions.

        Frame zero is a proven no-op: nothing moves here; ticks ease
        each survivor along a validated pixel route from its current
        center to its static home over an adaptive duration (same frame
        budget as ring blends). Production plans immutable pixels on one
        daemon worker; the visual clock commits a complete memoized
        sequential schedule before moving any survivor. Newcomers remain
        staged until landing. Invalid endpoints or a bounded search failure
        record a blocked constraint and hold the exact
        frame without an endless timer or retry. Changed membership
        or geometry can replan. Stale ring glides are abandoned; trails are
        cleared so the transition paints no streak. Returns True
        while a glide (or a visible hold) is in flight, False when
        every survivor already sits home (staged remainder, if any,
        is revealed at homes at once).
        """
        if self.expanded_identity is not None:
            self._expansion_dirty = True
            return True
        self._ring_blend = None
        if not self._motion_enabled():
            # Motion-off parking: stale hover/press holds die here
            # (backstop for direct callers) so neither the glide
            # finish nor a later re-enable can freeze on them.
            self._clear_interaction_holds()
        survivors = self._park_survivors(pet_rect, screen_rect)
        starts = {}
        for key in survivors:
            orb = self._windows.get(key)
            if orb is not None:
                starts[key] = (orb.x() + 56.0, orb.y() + 48.0)
        # Poll refreshes retain elapsed easing, but membership and every
        # obstacle target belong to the plan, including hidden newcomers.
        signature = (tuple(pet_rect), tuple(screen_rect), tuple(
            (key, self._auto_home(key, pet_rect, screen_rect))
            for key in sorted(self._windows)))
        existing = self._park_blend
        if existing is not None and existing.get('signature') == signature:
            if not existing.get('pending'):
                return True
            request = self._park_plan_request
            if request is not None and request[1] == self._parking_fence(signature):
                return True
        # New surfaces cannot obstruct an already planned survivor path.
        # They join atomically at landing; visible survivors never hide.
        self._stage_keys([key for key in self._windows
                          if key not in self._placed])
        self._last_tick = None
        if not starts:
            self._cancel_park_planning()
            self._park_blend = None
            # No visible survivors to glide: staged newcomers (if any)
            # are exposed only as a validated complete set.
            self._try_reveal_staged_at_homes(pet_rect, screen_rect)
            return False
        homes = {}
        for key in starts:
            homes[key] = self._home_center(key, pet_rect, screen_rect)
        if all(math.hypot(homes[key][0] - center[0],
                          homes[key][1] - center[1]) < 1.0
               for key, center in starts.items()):
            self._cancel_park_planning()
            self._park_blend = None
            self._reveal_parked_at_homes(pet_rect, screen_rect)
            return False
        static = tuple((key, self._auto_home(key, pet_rect, screen_rect))
                       for key in self._windows
                       if key not in starts and key not in self._ring_staged)
        inputs = (tuple(starts.items()), tuple(homes.items()), static,
                  signature, tuple(pet_rect), tuple(screen_rect), self._live_armed())
        if self._live_armed():
            fence = self._parking_fence(signature)
            self._park_plan_revision += 1
            self._park_plan_request = (self._park_plan_revision, fence, inputs)
            self._park_blend = {
                'signature': signature, 'pending': True, 't': 0.0, 'dur': 0.0,
                'starts': dict(starts), 'homes': dict(homes), 'windows': {},
                'pet_rect': tuple(pet_rect), 'screen_rect': tuple(screen_rect)}
            self._dispatch_park_plan()
            if self._visible:
                self.start_motion()
        else:
            self._park_blend = _plan_parking_routes(inputs)
            if self._park_blend is None:
                self._reveal_parked_at_homes(pet_rect, screen_rect)
                return False
        self._clear_trails()
        try:
            if self.trail_overlay.isVisible():
                self.trail_overlay.hide()
        except Exception:
            pass
        return True


    def _parking_fence(self, signature):
        return (signature, self._visible, self._motion_enabled(), self.expanded_identity, tuple(
            (key, id(orb), orb.x(), orb.y(), key in self._ring_staged)
            for key, orb in sorted(self._windows.items())))

    def _cancel_park_planning(self):
        self._park_plan_revision += 1
        self._park_plan_request = None
        if (self._park_blend or {}).get('pending'):
            self._park_blend = None

    def _dispatch_park_plan(self):
        # One running job plus one latest immutable request; no growing queue.
        if (self._shutdown or self.expanded_identity is not None or not self._visible or self._park_plan_job is not None
                or self._park_plan_request is None):
            return
        revision, fence, inputs = self._park_plan_request
        done, result = threading.Event(), []
        self._park_plan_job = (revision, fence, done, result)

        def work():
            try:
                result.append((_plan_parking_routes(inputs), None))
            except Exception as error:
                result.append((None, str(error)))
            finally:
                done.set()

        threading.Thread(target=work, daemon=True, name='star-parking-plan').start()

    def _poll_park_plan(self, pet_rect, screen_rect):
        """Commit only on the visual clock, with an exact held frame zero."""
        if self.expanded_identity is not None or self._shutdown:
            return False
        blend = self._park_blend
        if not (blend or {}).get('pending'):
            return False
        # A drag, accepted membership change or external orb move supersedes
        # the desired request. The running pure job is allowed to finish.
        signature = (tuple(pet_rect), tuple(screen_rect), tuple(
            (key, self._auto_home(key, pet_rect, screen_rect))
            for key in sorted(self._windows)))
        request = self._park_plan_request
        if request is None or request[1] != self._parking_fence(signature):
            self._begin_park_glide(pet_rect, screen_rect)
            request = self._park_plan_request
            if request is None:
                self.sync_motion()
        job = self._park_plan_job
        if job is not None and job[2].is_set():
            self._park_plan_job = None
            if (request is not None and job[:2] == request[:2]
                    and self._visible and not self._shutdown):
                plan, error = job[3][0]
                self._park_plan_request = None
                if error is not None:
                    self._park_blend.pop('pending', None)
                    self._park_blend['blocked'] = 'parking_planner_error'
                else:
                    self._park_blend = plan
                    if plan is None:
                        self._reveal_parked_at_homes(pet_rect, screen_rect)
                self._last_tick = None
                if plan is None or (self._park_blend or {}).get('blocked'):
                    self.sync_motion()
            self._dispatch_park_plan()
        else:
            self._dispatch_park_plan()
        return True

    def _advance_park_glide(self, pet_rect, screen_rect, dt):
        """Advance the parking glide by dt seconds of active time.

        Holds (no move, no clock advance) on any frame that would
        violate the final footprint rules, so an awkward path can
        never teleport through forbidden geometry. Deferred movers
        hold visibly at their exact starts for the whole round. Live
        geometry replans from exact current pixels, so pet moves cannot
        invalidate a previously accepted route. Returns True in flight.
        """
        blend = self._park_blend
        if blend is None:
            return False
        if (tuple(blend['pet_rect']) != tuple(pet_rect)
                or tuple(blend['screen_rect']) != tuple(screen_rect)):
            self._begin_park_glide(pet_rect, screen_rect)
            return True
        if blend.get('blocked') or blend.get('pending'):
            return True
        # Never fast-forward through hidden time (process hibernate
        # with an armed timer): one tick advances at most a single
        # nominal frame (RING_BLEND_FRAME_S) and the glide resumes
        # next tick — no catch-up teleport, ever. The single-frame
        # bound keeps the eased peak step inside the D2B 16 px per
        # 40 ms budget (diagonal Manhattan + quantization included).
        dt = min(dt, pet_geometry.RING_BLEND_FRAME_S)
        if dt <= 0.0:
            return True
        proposal = blend['t'] + dt
        windows = blend.get('windows') or {}
        deferred = set(blend.get('deferred') or set())
        frame = {}
        for key, orb in self._windows.items():
            if key in self._ring_staged:
                continue
            start = blend['starts'].get(key)
            if start is None or orb is None:
                continue
            home = self._home_center(key, pet_rect, screen_rect)
            if key in deferred:
                center = start
            else:
                window = windows.get(key, (0.0, blend['dur']))
                local = ((proposal - window[0]) / window[1]
                         if window[1] > 0 else 1.0)
                if local <= 0.0:
                    center = start
                elif local >= 1.0:
                    center = home
                else:
                    fractions = max(25, math.ceil(window[1] / 0.005))
                    sampled = math.floor(local * fractions) / fractions
                    path, distances = blend['routes'][key]
                    travel = pet_geometry.ring_blend_ease(sampled) * distances[-1]
                    index = max(0, bisect_right(distances, travel) - 1)
                    pos = path[index]
                    center = (pos[0] + pet_geometry.TASK_STAR_CENTER[0],
                              pos[1] + pet_geometry.TASK_STAR_CENTER[1])
            frame[key] = pet_geometry.star_center_to_window_position(
                center[0], center[1])
        for key, orb in self._windows.items():
            if key in frame or key in self._ring_staged:
                continue
            frame[key] = (orb.x(), orb.y())
        if not self._nominal_valid(frame, pet_rect, screen_rect):
            return True
        blend['t'] = proposal
        for key, pos in frame.items():
            if key not in blend['starts']:
                continue
            if key in deferred:
                continue
            orb = self._windows.get(key)
            if orb is None:
                continue
            if self._placed.get(key) != pos:
                self._placed[key] = pos
                orb.move(*pos)
        if proposal < blend['dur'] - 1e-9:
            return True
        return self._finish_park_glide(pet_rect, screen_rect)

    def _finish_park_glide(self, pet_rect, screen_rect):
        """Land the scheduled movers exactly on static homes.

        Deferred movers are untouched at their exact held pixels; if
        any still sits away from home, a new round replans from those
        pixels at once (successive rounds converge as more stars sit
        home). Park-staged orbs are revealed only on the final round,
        when the full home set is valid again. With motion enabled
        the selected mode resumes without a jump: arc clocks restart
        at their home origins, and a ring selection plans a fresh
        cartesian blend outward on the next tick. Returns True while
        another round is in flight.
        """
        blend = self._park_blend
        deferred = set((blend or {}).get('deferred') or set())
        self._park_blend = None
        for key, orb in self._windows.items():
            if key in self._ring_staged or key in deferred:
                continue
            try:
                home = self._auto_home(key, pet_rect, screen_rect)
                self._placed[key] = home
                orb.move(*home)
                orb.halo_alpha = 1.0
                orb.halo_radius = 1.0
                orb.core_intensity = 1.0
                orb.facet_intensity = 1.0
                orb.update()
            except Exception:
                pass
        if self._motion_enabled():
            if self._orbit_mode[0] == 'arc':
                for key in self._windows:
                    self._orbit_t[key] = 0.0
            elif self._orbit_mode[0] == 'ring':
                # Next tick transfers to a ring blend from these exact
                # homes via the motion-changed path: mark the
                # transition so the shortcut cannot skip planning.
                self._last_motion_enabled = False
        live_deferred = [key for key in deferred
                         if key in self._windows
                         and key not in self._ring_staged]
        if live_deferred and self._max_home_distance(
                live_deferred, pet_rect, screen_rect) >= 1.0:
            # Successive round from the exact held pixels (movers now
            # home unblock the deferred paths). Staged orbs stay
            # hidden until the final landing, when homes validate.
            self._begin_park_glide(pet_rect, screen_rect)
            return True
        self._reveal_parked_at_homes(pet_rect, screen_rect)
        return False

    def _reveal_parked_at_homes(self, pet_rect, screen_rect):
        """Expose park-staged orbs at their static homes, atomically.

        Crowded parking glides a validated subset while the longest
        hauls wait hidden; once the movers land, the remainder
        appears at homes (hidden-to-shown is an appearance, not
        motion) — but only when the complete frame (landed survivors
        at homes plus staged candidates at homes) validates. A
        blocked remainder stays staged for a later apply instead of
        overlapping a survivor. Homes are D2A-valid by construction,
        so the full set is valid on return whenever anything was
        revealed.
        """
        if not self._ring_staged:
            return
        self._try_reveal_staged_at_homes(pet_rect, screen_rect)

    def _stage_keys(self, newcomers):
        """Hide blocking newcomers pending safe reveal (staging).

        Membership, slots, labels, and offsets are untouched —
        presentation only. Trails cleared, holds released: hidden
        orbs are inert until revealed at validated final slots.
        """
        for key in newcomers:
            orb = self._windows.get(key)
            if orb is not None:
                orb.hide()
            self.trail_overlay.drop(key)
            self.release_hover_hold(key)
            self.release_press_hold(key)
        self._ring_staged |= set(newcomers)

    def _try_reveal_staged_at_homes(self, pet_rect, screen_rect):
        """Reveal staged orbs at static homes only as a valid set.

        Builds the complete frame — staged candidates at their live
        static homes plus every survivor at its exact current pixels
        — and reveals nothing unless the whole frame validates
        (work-area containment, pet/star and star/star clearance).
        Blocked newcomers stay staged (hidden, inert) until the
        survivors glide to a safe frame or a later apply replans;
        a parking glide in flight reveals them at landing through
        _reveal_parked_at_homes. Returns True when nothing remains
        staged.
        """
        if self._park_blend is not None and self._ring_staged:
            return False
        if not self._ring_staged:
            return True
        frame = {}
        for key, orb in self._windows.items():
            if key in self._ring_staged:
                try:
                    home = self._auto_home(key, pet_rect, screen_rect)
                except Exception:
                    return False
                frame[key] = home
            elif orb is None:
                continue
            else:
                frame[key] = (orb.x(), orb.y())
        if not self._nominal_valid(frame, pet_rect, screen_rect):
            return False
        for key in sorted(self._ring_staged):
            orb = self._windows.get(key)
            if orb is None:
                continue
            try:
                home = self._auto_home(key, pet_rect, screen_rect)
                self.trail_overlay.drop(key)
                self.release_hover_hold(key)
                self.release_press_hold(key)
                if self._placed.get(key) != home:
                    self._placed[key] = home
                    orb.move(*home)
                if self._visible:
                    orb.show()
            except Exception:
                pass
        self._ring_staged = set()
        return True

    def _reveal_all_staged(self, pet_rect, screen_rect):
        """Legacy reveal entry: now routes through validation.

        Historically showed every staged orb without checking the
        combined frame; that could overlap a survivor mid-ring. All
        internal callers now use _try_reveal_staged_at_homes
        directly — this alias delegates there so no path can bypass
        complete-frame validation again.
        """
        self._try_reveal_staged_at_homes(pet_rect, screen_rect)

    def _maybe_reveal_staged(self, pet_rect, screen_rect):
        """Reveal staged orbs whose final slots validate, atomically.

        Tick-path check once survivors circulate with no active
        blend: staged targets at the CURRENT shared phase plus live
        survivor positions must validate as one complete set; then
        the whole staged group is placed, shown, and untracked in the
        same turn — never one-by-one through an invalid transient.
        """
        if not self._ring_staged:
            return
        mode = self._orbit_mode
        if mode[0] != 'ring':
            return
        pcx = pet_rect[0] + pet_rect[2] / 2.0
        pcy = pet_rect[1] + pet_rect[3] / 2.0
        omega = 2.0 * math.pi / mode[3]
        phase = mode[5] + mode[4] * math.degrees(omega * self._ring_t)
        frame = {}
        for key, orb in self._windows.items():
            if key in self._ring_staged:
                theta = phase + self._ring_offsets.get(key, 0.0)
                center = pet_geometry.orbit_center_at(
                    pcx, pcy, mode[1], mode[2], theta)
                frame[key] = (
                    pet_geometry.star_center_to_window_position(
                        center[0], center[1]))
            else:
                frame[key] = (orb.x(), orb.y())
        if not self._nominal_valid(frame, pet_rect, screen_rect):
            return
        for key in sorted(self._ring_staged):
            orb = self._windows.get(key)
            if orb is None:
                continue
            pos = frame[key]
            self.trail_overlay.drop(key)
            self.release_hover_hold(key)
            self.release_press_hold(key)
            if self._placed.get(key) != pos:
                self._placed[key] = pos
                orb.move(*pos)
            if self._visible:
                orb.show()
        self._ring_staged = set()

    def _maybe_reveal_staged_arc(self, pet_rect, screen_rect):
        """Reveal staged orbs into the live arc, atomically.

        Arc-mode counterpart of _maybe_reveal_staged: staged targets
        at the CURRENT per-key arc clocks plus live survivor pixels
        must validate as one complete set; then the whole staged
        group is placed, shown, and untracked in the same turn.
        Staged orbs stay hidden and inert until then, so arc ticks
        can retry every frame until a safe envelope arrives.
        """
        if not self._ring_staged:
            return
        mode = self._orbit_mode
        if mode[0] != 'arc' or not self._motion_enabled():
            return
        omega = 2.0 * math.pi / mode[2]
        frame = {}
        for key, orb in self._windows.items():
            if key in self._ring_staged:
                params = self._orbit.get(key)
                if params is None:
                    return
                cycle = ((omega * self._orbit_t.get(key, 0.0))
                         % (2.0 * math.pi)) / (2.0 * math.pi)
                theta = pet_geometry.arc_angle_at(
                    params['base_deg'], mode[1],
                    self._arc_dirs.get(key, +1), cycle)
                center = pet_geometry.orbit_center_at(
                    pet_rect[0] + pet_rect[2] / 2.0,
                    pet_rect[1] + pet_rect[3] / 2.0,
                    params['radius'], params['radius'], theta)
                frame[key] = (
                    pet_geometry.star_center_to_window_position(
                        center[0], center[1]))
            else:
                frame[key] = (orb.x(), orb.y())
        if not self._nominal_valid(frame, pet_rect, screen_rect):
            return
        for key in sorted(self._ring_staged):
            orb = self._windows.get(key)
            if orb is None:
                continue
            pos = frame[key]
            self.trail_overlay.drop(key)
            self.release_hover_hold(key)
            self.release_press_hold(key)
            if self._placed.get(key) != pos:
                self._placed[key] = pos
                orb.move(*pos)
            if self._visible:
                orb.show()
        self._ring_staged = set()

    def _maybe_start_blend(self, prev_mode, prev_offsets, pet_rect,
                             screen_rect, prev_pet_rect=None,
                             prev_screen_rect=None):
        """Recomposition glide for ring survivors (manager-owned).

        Tries a direct all-visible blend first; when every candidate
        rotation overlaps on arrival, the blocking newcomers are
        staged hidden and survivors glide alone to final slots, with
        staged stars revealed once the complete set validates. Rank
        order and identities untouched; unchanged refreshes leave any
        blend or staged set alone; leaving ring (or no survivors)
        clears blend state and reveals staged orbs only when the
        complete frame validates (blocked newcomers stay staged).

        Frame zero is always the exact visible geometry: planning
        never moves an orb (the chase-path commit makes placement at
        blend start a proven no-op), and any entry that cannot start
        from current pixels detours through the parking glide
        instead of teleporting.
        """
        mode = self._orbit_mode
        if mode[0] != 'ring' or not self._windows:
            self._ring_blend = None
            if self._park_blend is not None and self._windows:
                # Membership changes during an arc bridge must invalidate
                # its obstacle set just as motion-off changes do.
                self._begin_park_glide(pet_rect, screen_rect)
            # Ring exit: never show staged stars into an unvalidated
            # frame. Survivors at exact current pixels plus staged
            # candidates at homes must validate as one complete set;
            # blocked newcomers stay staged (hidden, inert) until a
            # later apply finds a safe frame.
            self._try_reveal_staged_at_homes(pet_rect, screen_rect)
            enabled = self._motion_enabled()
            motion_changed = (enabled != self._last_motion_enabled)
            if motion_changed:
                # Motion-state transitions drop stale interaction
                # holds: an old hover/press must never freeze the
                # resumed mode (no release event will come for a
                # pre-toggle hold).
                self._clear_interaction_holds()
            if enabled and motion_changed:
                # Motion re-enabled under arc/static: orbs already at
                # homes restart cleanly; stranded orbs glide home
                # first instead of snapping to clock origins.
                if self._park_blend is None and self._max_home_distance(
                        self._park_survivors(pet_rect, screen_rect),
                        pet_rect, screen_rect) >= 1.0:
                    self._begin_park_glide(pet_rect, screen_rect)
                elif self._park_blend is None:
                    for key in self._windows:
                        self._orbit_t[key] = 0.0
            elif (enabled and self._park_blend is None
                    and self._ring_staged):
                # Steady-motion ring exit (pet moved to an arc/edge
                # layout) with newcomers still staged: survivors sit
                # at ring pixels while arc clocks sit at homes, so a
                # synchronous _place_all would teleport them. Glide
                # home first from exact pixels instead; the arc (at
                # t == 0 its positions ARE homes) then resumes
                # without a jump, and the park finish reveals the
                # staged set through the validated path. The bridge
                # runs only when the survivors' current pixels are
                # themselves valid under the new geometry (so the
                # glide starts from a legal frame); when the hub jump
                # itself stranded them inside the pet, validity wins
                # and the synchronous placement below lands them on
                # valid homes instead of deadlocking inside the pet.
                survivors_now = {}
                for key, orb in self._windows.items():
                    if key in self._ring_staged or orb is None:
                        continue
                    if key not in self._placed:
                        continue
                    survivors_now[key] = (orb.x(), orb.y())
                if (survivors_now
                        and self._max_home_distance(
                            self._park_survivors(pet_rect, screen_rect),
                            pet_rect, screen_rect) >= 1.0
                        and self._nominal_valid(
                            survivors_now, pet_rect, screen_rect)):
                    self._begin_park_glide(pet_rect, screen_rect)
            elif enabled and self._park_blend is None:
                # Steady-motion ring-to-arc/static mode change or
                # pet/screen-geometry move under a non-ring mode: the
                # selected clocks were recomputed above
                # (_compute_orbit_params resets changed lanes to
                # t == 0, i.e. homes), so a synchronous _place_all
                # would teleport survivors from exact current pixels
                # to the new nominal frame. Glide home first from
                # those pixels instead; the arc (at t == 0 its
                # positions ARE homes) then resumes without a jump.
                # Membership changes can alter lanes even when the
                # mode tuple and work area are unchanged. Compare pixels.
                try:
                    nominal, _ = self._nominal_positions(
                        pet_rect, screen_rect)
                except Exception:
                    nominal = {}
                survivors_now = {}
                peak_jump = 0.0
                import math as _rej_math
                for key, orb in self._windows.items():
                    if key in self._ring_staged or orb is None:
                        continue
                    if key not in self._placed:
                        continue
                    target = nominal.get(key)
                    if target is None:
                        continue
                    survivors_now[key] = (orb.x(), orb.y())
                    peak_jump = max(
                        peak_jump,
                        _rej_math.hypot(
                            target[0] - orb.x(),
                            target[1] - orb.y()))
                if (survivors_now and peak_jump >= 1.0
                        and self._nominal_valid(
                            survivors_now, pet_rect, screen_rect)):
                    self._begin_park_glide(pet_rect, screen_rect)
            # Motion-steady arc/static frames that need no glide keep
            # the accepted synchronous placement below via _place_all
            # (exact no-op when nominal matches current pixels).
            return
        if not self._motion_enabled():
            self._ring_blend = None
            # Motion off: keep staged newcomers hidden until the
            # parking glide lands them safely. Revealing them now at
            # static homes while survivors still sit mid-ring would
            # bypass complete-frame validation (staged home vs live
            # survivor overlap); the park finish reveals through the
            # validated path instead.
            if self._motion_enabled() != self._last_motion_enabled:
                # ON->OFF through an apply: stale holds die here so
                # the parked state — and any later re-enable — is
                # never frozen by a pre-toggle hover/press.
                self._clear_interaction_holds()
            return
        had_park = self._park_blend is not None
        self._cancel_park_planning()
        # A parking glide transfers into the ring blend: current
        # pixels (possibly mid-parking) become the chase starts.
        self._park_blend = None
        survivors = [k for k in self._windows
                     if k in self._placed and k not in self._ring_staged]
        if not survivors:
            self._ring_blend = None
            return
        # A motion OFF->ON (or ON->OFF handled above) transition is a
        # real presentation recomposition even when membership, mode,
        # and offsets look unchanged: static homes and animated ring
        # positions live in different geometry spaces, so the
        # unchanged-snapshot shortcut must not skip planning.
        motion_changed = (self._motion_enabled()
                           != self._last_motion_enabled)
        if motion_changed:
            # OFF->ON through an apply (or a stale-flag resync):
            # stale holds die here so the fresh ring can never
            # start frozen by a pre-toggle hover/press.
            self._clear_interaction_holds()
        if ((mode, self._ring_offsets) == (prev_mode, prev_offsets)
                and not motion_changed and not had_park):
            return
        hub = (pet_rect[0] + pet_rect[2] / 2.0,
               pet_rect[1] + pet_rect[3] / 2.0)
        starts = {}
        for key in survivors:
            orb = self._windows.get(key)
            if orb is None:
                continue
            starts[key] = pet_geometry.ring_abs_angle_deg(
                orb.x() + 56.0, orb.y() + 48.0, hub[0], hub[1])
        if not starts:
            self._ring_blend = None
            return
        newcomers = [k for k in self._windows
                     if k not in starts and k not in self._ring_staged]
        plan = self._plan_direct_blend(starts, newcomers, pet_rect,
                                       screen_rect)
        if plan is None:
            if not newcomers:
                # Survivors-only frame rejected (e.g. a toggle landing
                # on a pet-moved hub where old-hub homes overlap the
                # pet): no direct chase is safe, so detour through
                # the parking glide from these exact pixels — homes
                # always validate as a set, and the ring resumes from
                # homes on landing without a jump.
                self._begin_park_glide(pet_rect, screen_rect)
                return
            self._stage_keys(newcomers)
            newcomers = []
            plan = self._plan_direct_blend(starts, [], pet_rect,
                                           screen_rect)
            if plan is None:
                # Even survivors alone cannot chase safely: park
                # first from exact pixels, then blend outward.
                self._begin_park_glide(pet_rect, screen_rect)
                return
        if motion_changed:
            # Toggle-time path check: a chase that would cut through
            # forbidden geometry (crowded order-mismatched sets) must
            # not run — stage the longest hauls until the remaining
            # simultaneous paths validate end to end. Ordinary
            # recomposition keeps the runtime hold-guard behavior.
            shrunk = self._shrink_to_valid_chase(
                starts, newcomers, plan, pet_rect, screen_rect)
            if shrunk is None:
                return
            plan, kept = shrunk
            starts = kept
        phi, travels = plan
        self._commit_blend_plan(starts, phi, travels, hub)

    def _shrink_to_valid_chase(self, starts, newcomers, plan, pet_rect,
                               screen_rect):
        """Stage blocking survivors until the chase validates.

        Plan-time counterpart of the runtime hold guard, used only
        for motion-toggle transitions (frame zero is exact current
        pixels for every survivor). Samples the full chase —
        survivors gliding plus newcomers holding at arrival targets
        — and greedily stages the longest haul until the remainder
        validates end to end, replanning the base rotation for each
        smaller set. Returns (plan, kept_starts) with the plan's
        starts restricted to the kept movers, or None when every
        survivor staged (the tick reveal path then exposes the whole
        set atomically once it validates). Commits nothing itself;
        the caller commits the returned plan.
        """
        mode = self._orbit_mode
        hub = (pet_rect[0] + pet_rect[2] / 2.0,
               pet_rect[1] + pet_rect[3] / 2.0)
        kept = dict(starts)
        while True:
            phi, travels = plan
            # Re-derive the commit-time rebased phase (the commit adds
            # phi/rate to the shared clock, which advances the phase
            # by exactly phi) without touching any clock: validation
            # must see the exact arrival frame the commit will
            # produce.
            omega = 2.0 * math.pi / mode[3]
            phase = (mode[5] + mode[4]
                     * math.degrees(omega * self._ring_t) + phi)
            deltas = {}
            centers = {}
            for key in kept:
                orb = self._windows.get(key)
                if orb is None:
                    continue
                centers[key] = (orb.x() + 56.0, orb.y() + 48.0)
                deltas[key] = pet_geometry.ring_shortest_delta_deg(
                    kept[key], phase + self._ring_offsets.get(key, 0.0))
            static = {}
            for key in newcomers:
                theta = phase + self._ring_offsets.get(key, 0.0)
                goal = pet_geometry.orbit_center_at(
                    hub[0], hub[1], mode[1], mode[2], theta)
                static[key] = (
                    pet_geometry.star_center_to_window_position(
                        goal[0], goal[1]))

            movers = sorted(kept)

            def validate(candidates):
                def points_at(progress):
                    ease = pet_geometry.ring_blend_ease(progress)
                    return {
                        key: self._chase_point(
                            centers[key], kept[key], deltas[key],
                            ease, hub, mode[1], mode[2])
                        for key in candidates if key in centers}
                return self._validate_path_frames(
                    points_at, candidates, static, pet_rect,
                    screen_rect)

            subset = self._greedy_path_subset(
                movers, lambda key: deltas.get(key, 0.0), validate)
            if len(subset) == len(movers):
                return (plan, kept)
            for key in movers:
                if key not in subset:
                    self._stage_keys([key])
            if not subset:
                self._ring_blend = None
                return None
            kept = {key: kept[key] for key in subset}
            plan = self._plan_direct_blend(kept, newcomers, pet_rect,
                                           screen_rect)
            if plan is None:
                self._ring_blend = None
                return None

    def _motion_enabled(self):
        """Single V1.3 visual-motion preference (shared with the pet)."""
        prefs = getattr(self.panel, 'prefs', None) or {}
        return bool(prefs.get('pet_motion', True))

    def _live_armed(self):
        """Real timer arming is production-only (Panel live=True).

        Unit tests construct live=False panels, so no render, filter,
        or toggle path can ever arm a real 40ms loop under test:
        motion tests drive tick_visual() manually with fake clocks.
        """
        return bool(getattr(self.panel, 'live', False))

    def start_motion(self):
        """Arm the shared visual clock (explicit production/test act)."""
        if self._shutdown:
            return
        if not self.motion_timer.isActive():
            self._last_tick = None
            self.motion_timer.start(pet_geometry.MOTION_TICK_MS)

    def stop_motion(self):
        """Disarm the shared visual clock."""
        if self.motion_timer.isActive():
            self.motion_timer.stop()
        self._last_tick = None

    def sync_motion(self):
        """Arm the shared clock while visible stars need ticks.

        Ticks are needed for live motion and, separately, while a
        parking glide is in flight (which advances even though motion
        reads off). Called from UI paths; the live gate keeps unit
        tests deterministic. Returns the motion-based want so
        historical callers keep their semantics; timer arming
        additionally covers an in-flight park. Never teleports: with
        motion off, stray orbs begin a parking glide from their exact
        current positions instead of snapping home."""
        if self._shutdown:
            return False
        if not self.legacy_exterior_motion:
            want = bool(self._windows) and self._visible and self.expanded_identity is None
            need = want and (self._motion_enabled() or self._halo_pending()
                             or self.trail_overlay.has_trails() or self.back_overlay.has_trails())
            if self._live_armed():
                self.start_motion() if need else self.stop_motion()
            return bool(want and self._motion_enabled() and self._live_armed())
        if self.expanded_identity is not None:
            self._expansion_dirty |= self._motion_enabled() != self._last_motion_enabled
            return False
        want = (bool(self._windows) and self._visible
                and self._motion_enabled() and self._live_armed())
        if not self._live_armed():
            # Test panels (live=False) only query: a wall-clock
            # status tick must never clear trails, hide the overlay,
            # park orbs, or arm a real loop mid-test.
            return want
        if self._visible and self._windows and not self._motion_enabled():
            pet_rect = self._last_pet_rect
            screen_rect = self._last_screen_rect
            if pet_rect is None or screen_rect is None:
                pet_rect, screen_rect = self._anchor()
            # Timer-driven ON->OFF (no apply in between): stale
            # hover/press holds die here so the parked state — and
            # any later re-enable — never freezes on them.
            self._clear_interaction_holds()
            # Validated reveal only: blocked staged newcomers stay
            # hidden while survivors park; the park finish exposes
            # them once the complete home set validates.
            self._try_reveal_staged_at_homes(pet_rect, screen_rect)
            self._begin_park_glide(pet_rect, screen_rect)
            self._last_motion_enabled = False
        elif (self._windows and self._motion_enabled()
                and self._last_motion_enabled is False):
            # Timer-driven OFF->ON (prefs flipped with no apply):
            # stale holds die here too. The flag itself stays False
            # so the tick path still sees the transition and plans
            # the continuous resume from exact pixels.
            self._clear_interaction_holds()
        timer_want = (bool(self._windows) and self._visible
                      and self._live_armed()
                      and not (self._park_blend or {}).get('blocked')
                      and (self._motion_enabled()
                           or self._park_blend is not None))
        if timer_want and not self.motion_timer.isActive():
            self._last_tick = None
            self.motion_timer.start(pet_geometry.MOTION_TICK_MS)
        elif not timer_want and self.motion_timer.isActive():
            self.motion_timer.stop()
            self._last_tick = None
        if not timer_want:
            self._clear_trails()
            try:
                if self.trail_overlay.isVisible():
                    self.trail_overlay.hide()
            except Exception:
                pass
        return want

    def _park_all(self):
        """Begin the motion-off parking glide (no teleport).

        Starts a finite glide from exact current positions to static
        homes; ticks own the movement. Parking invalidates any
        in-flight ring glide and keeps staged newcomers hidden until
        the complete home set validates, so a later re-enable — with
        or without an apply in between — always rebuilds from honest
        geometry. Records the transition so re-enable plans
        continuity. Idles (no glide) when every survivor already sits
        home.
        """
        self._ring_blend = None
        self._last_motion_enabled = False
        # Motion-off entry: stale interaction holds die here so the
        # parked state — and any later re-enable — never freezes.
        self._clear_interaction_holds()
        pet_rect = self._last_pet_rect
        screen_rect = self._last_screen_rect
        if pet_rect is None or screen_rect is None:
            pet_rect, screen_rect = self._anchor()
        self._try_reveal_staged_at_homes(pet_rect, screen_rect)
        self._begin_park_glide(pet_rect, screen_rect)

    def _on_motion_timeout(self):
        """Production driver: advance to the current monotonic clock."""
        try:
            self.tick_visual(time.monotonic())
        except Exception:
            pass

    def set_hovered(self, identity):
        """Legacy hover entry: entering adds a hold, leaving (None)
        releases all. Production enter/leave events use the hold
        methods below so nested ordering cannot strand a pause."""
        if identity is None:
            self._hover_holds = set()
            self._hovered = None
        else:
            self.add_hover_hold(identity)

    def add_hover_hold(self, identity):
        """Pointer entered a star: hold the whole ring group."""
        self._hover_holds.add(identity)
        self._hovered = identity

    def release_hover_hold(self, identity):
        """Pointer left a star: release its hold, keep others'."""
        self._hover_holds.discard(identity)
        if self._hovered == identity:
            remaining = sorted(self._hover_holds)
            self._hovered = remaining[0] if remaining else None

    def add_press_hold(self, identity):
        """Pointer pressed a star: hold the group, ease the click."""
        self._press_holds.add(identity)
        if self._hovered is None:
            self._hovered = identity

    def release_press_hold(self, identity):
        """Pointer released: release the press hold only."""
        self._press_holds.discard(identity)
        if (self._hovered == identity
                and identity not in self._hover_holds):
            self._hovered = None

    def _ring_paused(self):
        """Whole-group pause: any hover or press hold is active."""
        return bool(self._hover_holds or self._press_holds)

    def _clear_interaction_holds(self):
        """Drop all hover/press holds (motion-transition backstop).

        Motion OFF->ON/ON->OFF transitions invalidate any in-flight
        interaction: the pointer may be long gone (or the orb may
        have parked elsewhere), and no leave/release event will
        arrive to unpause the ring. Called on every motion-state
        change (apply-driven and timer-driven) so resumed motion
        can never stay frozen by a stale hold.
        """
        self._hover_holds = set()
        self._press_holds = set()
        self._hovered = None

    def _reconcile_holds(self):
        """Drop holds for keys with no surface; repair _hovered.

        Uniform backstop after any visibility update (retire,
        filter, provider failure): no dead key pauses the ring,
        and _hovered always names a live hold or None.
        """
        live = set(self._windows)
        self._hover_holds &= live
        self._press_holds &= live
        if self._hovered not in self._hover_holds:
            remaining = sorted(self._hover_holds)
            self._hovered = remaining[0] if remaining else None

    def trail_for(self, identity):
        """Current trail sample count for one task (bounded)."""
        return self.trail_overlay.trail_length(identity)

    def orb_activated(self, identity, keyboard=False):
        if (self._shutdown or not self._visible or identity not in self._universe
                or identity not in self._windows or identity in self._ring_staged):
            return
        self.last_activated = identity
        if self.expanded_identity == identity:
            self.collapse_detail()
            return
        if self.expanded_identity is None:
            pending = bool((self._park_blend or {}).get('pending'))
            self._cancel_park_planning()
            self._expansion_dirty = pending
            self._expansion_geometry = (tuple(self._last_pet_rect), tuple(self._last_screen_rect))
        self.expanded_identity = identity
        orb = self._windows[identity]
        self.expanded_anchor = (orb.x(), orb.y())
        self._last_tick = None
        self._clear_trails()
        self._refresh_detail(preserve_transition=True)
        self.detail_transition.open(self.detail_window,
            (orb.x() + pet_geometry.TASK_STAR_CENTER[0], orb.y() + pet_geometry.TASK_STAR_CENTER[1]),
            animated=self._motion_enabled() and not self.legacy_exterior_motion)
        self.detail_window.raise_()
        if not self.legacy_exterior_motion:
            self._stack_halo(force=True)
        if keyboard:
            self.detail_window.activateWindow()
            self.detail_window.collapse_button.setFocus(Qt.ShortcutFocusReason)

    def _refresh_detail(self, preserve_transition=False):
        identity = self.expanded_identity
        if identity is None or identity not in self._universe:
            return
        provider = identity[0]
        card = self.detail_window
        if (not preserve_transition or card is None or card.entry is None
                or task_identity(card.entry) != identity):
            self.detail_transition.cancel()
        if card is not None and card.provider_id != provider:
            card.manager = None
            card.close()
            card.deleteLater()
            card = self.detail_window = None
        if card is None:
            card = self.detail_window = TaskPanelWindow(provider, self)
        prefs = getattr(self.panel, 'prefs', None) or {}
        position, visible = card.pos(), card.isVisible()
        on_top = bool(prefs.get('always_on_top', True))
        if bool(card.windowFlags() & Qt.WindowStaysOnTopHint) != on_top:
            card.setWindowFlag(Qt.WindowStaysOnTopHint, on_top)
            card.move(position)
            if visible:
                card.show()
        card.set_task(self._universe[identity], self.label_text(identity, self._task_language),
                      self._task_language, prefs.get('token_number_format'))
        left, top, right, bottom = self._last_screen_rect
        card.setFixedSize(min(card.window_size[0], right - left + 1),
                          min(card.window_size[1], bottom - top + 1))
        x, y = self.expanded_anchor
        cx, cy = x + pet_geometry.TASK_STAR_CENTER[0], y + pet_geometry.TASK_STAR_CENTER[1]
        target_x = (cx + pet_geometry.TASK_STAR_SIZE[0] - pet_geometry.TASK_STAR_CENTER[0]
                    + pet_geometry.TASK_WINDOW_GAP)
        if target_x + card.width() > right + 1:
            target_x = x - card.width() - pet_geometry.TASK_WINDOW_GAP
        card.move(*pet_geometry.clamp_position(target_x, round(cy - card.height() / 2),
                                               card.width(), card.height(), self._last_screen_rect))

    def collapse_detail(self, replan=True):
        if self.expanded_identity is None:
            return
        dirty = self._expansion_dirty or self._motion_enabled() != self._last_motion_enabled
        anchor = self.expanded_anchor
        self.expanded_identity = None
        self.expanded_anchor = None
        self._expansion_geometry = None
        self._expansion_dirty = False
        if self.detail_window is not None:
            self.detail_transition.close(self.detail_window,
                (anchor[0] + pet_geometry.TASK_STAR_CENTER[0], anchor[1] + pet_geometry.TASK_STAR_CENTER[1]),
                animated=replan and self._visible and not self._shutdown
                         and self._motion_enabled() and not self.legacy_exterior_motion)
        else:
            self.detail_transition.cancel()
        self._clear_interaction_holds()
        self._last_tick = None
        if dirty:
            self._cancel_park_planning()
            self._park_blend = None
            self._ring_blend = None
            # Force the accepted planner to rebuild from current pixels,
            # even when deferred geometry leaves mode/offsets unchanged.
            self._orbit_mode = ('expanded_resume',)
        if replan and not self._shutdown and self._visible:
            if dirty:
                self.apply_snapshot(list(self._universe.values()), self._task_preference,
                                    self._last_generation, self._task_language,
                                    self._last_pet_rect, self._last_screen_rect)
            self.sync_motion()

    def anchor_changed(self, *, transport=False):
        if not self.legacy_exterior_motion:
            if self._shutdown or getattr(self.panel, 'closing', False):
                return
            self.detail_transition.cancel()
            pet_rect, screen_rect = self._anchor()
            if self.expanded_identity is not None:
                self._expansion_dirty = True
                self.collapse_detail(replan=False)
            self._halo_target = self._fit_halo_pose(pet_rect, screen_rect)
            if transport and self._halo_pose is not None:
                # Intentional pet movement transports the attached scene. The
                # shared orbit phase/slot offsets do not jump or catch up.
                self._halo_pose = self._halo_target
                self._last_pet_rect, self._last_screen_rect = pet_rect, screen_rect
                self._clear_trails()
                self._clear_interaction_holds()
                self._last_tick = None
                self._halo_commit(0.0, record=False)
                self._update_page_controls()
            self.sync_motion()
            return
        if (self._shutdown or getattr(self.panel, 'closing', False)
                or self.expanded_identity is None):
            return
        pet_rect, screen_rect = self._anchor()
        if (tuple(pet_rect), tuple(screen_rect)) == self._expansion_geometry:
            return
        self._expansion_dirty = True
        self.collapse_detail(replan=False)
        self.apply_snapshot(list(self._universe.values()), self._task_preference,
                            self._last_generation, self._task_language,
                            pet_rect, screen_rect)

    def _compute_orbit_params(self, pet_rect, screen_rect):
        """Per-star hub-centered lane from static homes.

        Stores (radius, base_deg) per visible star, where the radius
        is the true home distance from the pet center: replaying the
        base angle reproduces the static home exactly, and advancing
        the angle moves along a pet-centered arc lane around the hub. Resets that star's accumulated orbit time
        only when its frame actually changed, so unrelated refreshes
        never restart its motion. Pet moves ride along via the
        current pet center.
        """
        pcx = pet_rect[0] + pet_rect[2] / 2.0
        pcy = pet_rect[1] + pet_rect[3] / 2.0
        for key in self._windows:
            center = self._home_center(key, pet_rect, screen_rect)
            dx, dy = center[0] - pcx, center[1] - pcy
            params = dict(radius=math.hypot(dx, dy),
                          base_deg=math.degrees(math.atan2(dx, -dy)) % 360.0)
            if self._orbit.get(key) != params:
                self._orbit[key] = params
                self._orbit_t[key] = 0.0

    def _home_center(self, key, pet_rect, screen_rect):
        """Static home center for one star (orbit anchor origin)."""
        x, y = self._auto_home(key, pet_rect, screen_rect)
        return (x + pet_geometry.TASK_STAR_CENTER[0],
                y + pet_geometry.TASK_STAR_CENTER[1])

    def _select_orbit_mode(self, pet_rect, screen_rect):
        """Best safe orbit motion for the current composition.

        Hierarchy: full ring (largest valid circle, else largest valid
        ellipse) first — a ring is only accepted if its ENTIRE cycle
        passes the final footprint rules phase by phase. Only when no
        circle or ellipse fits (pet near an edge, tiny work area) does
        selection fall to one-sided tangent arcs, else static. Ring
        offsets come from sorted lifetime slots (equal 360/N spacing),
        so identities never reorder on recency or poll timing; a
        membership change simply recomposes the spacing. Deterministic
        for the same composition and clocks.
        """
        ring = self._select_full_ring(pet_rect, screen_rect)
        if ring is not None:
            self._arc_dirs = {}
            return ring
        pcx = pet_rect[0] + pet_rect[2] / 2.0
        pcy = pet_rect[1] + pet_rect[3] / 2.0
        steps = pet_geometry.ORBIT_SWEEP_SAMPLES
        radii = {}
        bases = {}
        for key in self._windows:
            params = self._orbit.get(key)
            if params is None:
                self._ring_offsets = {}
                return ('static',)
            radii[key] = params['radius']
            bases[key] = params['base_deg']

        def envelope_ok(angles_for):
            for step in range(steps):
                centers = {}
                for key in self._windows:
                    theta = angles_for(key, step / steps)
                    centers[key] = pet_geometry.orbit_center_at(
                        pcx, pcy, radii[key], radii[key], theta)
                windows = pet_geometry._finalize_candidate(
                    centers, screen_rect)
                if (windows is None or not pet_geometry._windows_valid(
                        windows, pet_rect, screen_rect)):
                    return False
            return True

        homes = {
            key: pet_geometry.orbit_center_at(
                pcx, pcy, radii[key], radii[key], bases[key])
            for key in self._windows}
        direction_sets = [self._greedy_arc_dirs(homes, pet_rect,
                                                screen_rect)]
        for uniform in (+1, -1):
            direction_sets.append({key: uniform for key in self._windows})
        seen = []
        for dirs in direction_sets:
            marker = tuple(sorted(dirs.items()))
            if marker in seen:
                continue
            seen.append(marker)
            for amplitude in pet_geometry.ORBIT_ARC_CANDIDATES_DEG:
                def arc_angle(key, s, amplitude=amplitude, dirs=dirs):
                    return pet_geometry.arc_angle_at(
                        bases[key], amplitude, dirs[key], s)

                if envelope_ok(arc_angle):
                    self._arc_dirs = dict(dirs)
                    self._ring_offsets = {}
                    return ('arc', amplitude,
                            pet_geometry.arc_period_s(amplitude))
        self._arc_dirs = {}
        self._ring_offsets = {}
        return ('static',)

    def _ring_offsets_for(self):
        """Equal 360/N spacing by sorted lifetime-slot rank (pure).

        Rank order is deterministic and independent of recency,
        foreground, or poll timing; surviving identities keep their
        windows while a membership change recomposes the spacing.
        """
        ranked = sorted(
            (self._slots.get(key, 0), key) for key in self._windows)
        count = len(ranked)
        if count == 0:
            return {}
        return {key: 360.0 * rank / count
                for rank, (_, key) in enumerate(ranked)}

    def _select_full_ring(self, pet_rect, screen_rect):
        """Largest safe full ring, or None (pure geometry + validation).

        Searches circles largest-first over the geometry-derived
        range, then ellipses largest-area-first (capped), validating
        RING_SWEEP_SAMPLES phases of the rigid ring — common
        direction, slot-rank offsets — against the final footprint
        rules. Returns ('ring', rx, ry, period, direction, base_deg)
        and stores per-key offsets, else None. Pet moves ride along
        via the per-tick hub; nothing here touches the clocks, so
        hover-frozen phases survive recomposition.
        """
        keys = list(self._windows)
        if not keys:
            return None
        (hub, circle_lo, circle_hi,
         rx_lo, rx_hi, ry_lo, ry_hi) = (
            pet_geometry.ring_search_bounds(pet_rect, screen_rect))
        pcx, pcy = hub
        base = pet_geometry.RING_BASE_DEG
        direction = pet_geometry.RING_DIRECTION
        samples = pet_geometry.RING_SWEEP_SAMPLES
        offsets = self._ring_offsets_for()

        def ring_ok(rx, ry):
            for step in range(samples):
                phase = base + direction * 360.0 * step / samples
                centers = {}
                for key in keys:
                    centers[key] = pet_geometry.orbit_center_at(
                        pcx, pcy, rx, ry, phase + offsets[key])
                windows = pet_geometry._finalize_candidate(
                    centers, screen_rect)
                if (windows is None or not pet_geometry._windows_valid(
                        windows, pet_rect, screen_rect)):
                    return False
            return True

        step = pet_geometry.RING_RADIUS_STEP_PX
        radius = circle_hi
        while radius >= circle_lo - 1e-9:
            if ring_ok(radius, radius):
                self._ring_offsets = dict(offsets)
                return ('ring', radius, radius,
                        pet_geometry.ring_period_s(radius),
                        direction, base)
            radius -= step
        estep = pet_geometry.RING_ELLIPSE_STEP_PX
        combos = []
        rx = rx_hi
        while rx >= rx_lo - 1e-9:
            ry = ry_hi
            while ry >= ry_lo - 1e-9:
                combos.append((rx, ry))
                ry -= estep
            rx -= estep
        combos.sort(key=lambda pair: (-pair[0] * pair[1],
                                      -pair[0], -pair[1]))
        for rx, ry in combos[:pet_geometry.RING_ELLIPSE_COMBO_CAP]:
            if ring_ok(rx, ry):
                self._ring_offsets = dict(offsets)
                return ('ring', rx, ry,
                        pet_geometry.ring_period_s((rx + ry) / 2.0),
                        direction, base)
        return None

    def _greedy_arc_dirs(self, homes, pet_rect, screen_rect):
        """Per-star one-sided arc direction with the most room.

        For each star independently, extends 5-degree steps up to 100
        degrees both ways (footprint-validated vs pet exclusion and
        bounds, others held at home) and keeps the farther side.
        Deterministic; the joint envelope stays authoritative, so a
        greedy pick that collides later simply loses to the next
        candidate.
        """
        import math
        pcx = pet_rect[0] + pet_rect[2] / 2.0
        pcy = pet_rect[1] + pet_rect[3] / 2.0
        dirs = {}
        for key in self._windows:
            home = homes.get(key)
            if home is None:
                dirs[key] = +1
                continue
            radius = math.hypot(home[0] - pcx, home[1] - pcy)
            base = math.degrees(math.atan2(home[0] - pcx,
                                           -(home[1] - pcy))) % 360.0
            best = (+1, -1)
            for direction in (+1, -1):
                extent = 0
                for step in range(1, 21):
                    theta = base + direction * 5.0 * step
                    point = pet_geometry.orbit_center_at(
                        pcx, pcy, radius, radius, theta)
                    window = pet_geometry.star_center_to_window_position(
                        point[0], point[1])
                    width, height = pet_geometry.TASK_STAR_SIZE
                    left, top, right, bottom = screen_rect
                    if not (left <= window[0]
                            and window[0] + width <= right + 1
                            and top <= window[1]
                            and window[1] + height <= bottom + 1):
                        break
                    if pet_geometry.footprint_hits_pet(
                            pet_geometry.star_window_footprint(*window),
                            pet_rect):
                        break
                    extent = step
                if best == (+1, -1):
                    best = (direction, extent)
                elif extent > best[1]:
                    best = (direction, extent)
            dirs[key] = best[0]
        return dirs

    def _nominal_valid(self, windows, pet_rect, screen_rect):
        """Per-tick full-set check on integer windows (hold on fail)."""
        if not self.legacy_exterior_motion:
            cx, cy = pet_geometry.TASK_STAR_CENTER
            return halo_geometry.frame_valid({k: (x + cx, y + cy)
                                               for k, (x, y) in windows.items()}, screen_rect)
        left, top, right, bottom = screen_rect
        width, height = pet_geometry.TASK_STAR_SIZE
        for wx, wy in windows.values():
            if not (left <= wx and wx + width <= right + 1
                    and top <= wy and wy + height <= bottom + 1):
                return False
        return pet_geometry._windows_valid(windows, pet_rect, screen_rect)

    def _apply_breathing(self, orb, identity):
        """Subtle luminous breathing from the broadcast clock.

        Light only, never position: halo opacity, halo radius, and
        core/facet luminance breathe gently with per-slot phase
        offsets. No scale modulation, so the star center cannot move
        under breathing by construction.
        """
        seed = pet_geometry.star_phase_seed(self._slots.get(identity, 0))
        period = 2.2 + seed * 1.0
        wave = math.sin(2.0 * math.pi * (self._motion_t / period)
                        + seed * 2.0 * math.pi)
        lift = 0.5 + 0.5 * wave
        orb.halo_alpha = 1.0 - 0.35 * lift
        orb.halo_radius = 1.0 + 0.08 * wave
        orb.core_intensity = 1.0 - 0.15 * lift
        orb.facet_intensity = 1.0 - 0.15 * lift
        orb.update()

    def _update_trails(self, now, centers=None):
        """Prune, record, and paint trail state for visible stars.

        Records the float nominal centers (not quantized widget
        positions) so slow sub-pixel drift accumulates; visibility
        requires a real span, so stillness paints nothing.
        Hover-paused stars record nothing: their trail fades to none
        while frozen, and resumes cleanly on unhover.

        Repaint rule: compare the overlay's visual signature before
        and after the mutation block and request update() only on
        change — new samples, expired samples, and removed trails
        repaint; identical state never does. While a visible trail
        ages toward expiry, prune changes the signature each time a
        sample drops, so fading keeps repainting until nothing is
        left; afterwards the signature is stable and repaints stop.
        """
        overlay = self.trail_overlay
        before = overlay.visual_signature()
        overlay.prune(now)
        centers = centers or {}
        for key, orb in self._windows.items():
            if not orb.isVisible():
                overlay.drop(key)
                continue
            if key == self._hovered:
                continue
            center = centers.get(key)
            if center is None:
                center = (orb.x() + 56, orb.y() + 48)
            overlay.record_sample(key, center[0], center[1], now)
        if overlay.visual_signature() != before:
            overlay.update()
        if overlay.has_trails():
            overlay.ensure_geometry()
            overlay.show_behind_stars()
        elif overlay.isVisible():
            overlay.hide()

    def _prune_trails_only(self, now):
        """Fade expired trail samples without recording new ones.

        Used while motion is off or a parking glide is in flight, so
        transitions leave no streak: old ribbons age out and the
        layer hides itself once nothing remains.
        """
        overlay = self.trail_overlay
        before = overlay.visual_signature()
        overlay.prune(now)
        if overlay.visual_signature() != before:
            overlay.update()
        if not overlay.has_trails() and overlay.isVisible():
            try:
                overlay.hide()
            except Exception:
                pass

    def tick_visual(self, now, pet_rect=None, screen_rect=None):
        """Advance celestial motion to monotonic time `now`.

        The production QTimer drives this ~25fps; tests drive it
        manually with synthetic clocks (fully deterministic, no real
        waiting). All motion clocks are active-time: hover/press holds
        freeze the whole ring group (breathing continues), and a
        safety-hold freezes phase too — the guard can never reject a
        position while the phase runs ahead, so no catch-up teleport
        is possible. Invalid nominal sets hold all stars in place.

        A parking glide in flight advances first under either motion
        flag (it is a finite transition to homes, not orbit): each
        step eases from exact visible pixels, holds on invalid
        frames, and idles the production timer on completion when
        motion reads off.
        """
        if not self._windows:
            return
        if pet_rect is None or screen_rect is None:
            live_pet, live_screen = self._anchor()
            pet_rect = live_pet if pet_rect is None else pet_rect
            screen_rect = live_screen if screen_rect is None else screen_rect
        if self.expanded_identity is not None:
            self._last_tick = now
            self._expansion_dirty |= self._motion_enabled() != self._last_motion_enabled
            if (tuple(pet_rect), tuple(screen_rect)) != self._expansion_geometry:
                self._expansion_dirty = True
                self.collapse_detail(replan=False)
                self.apply_snapshot(list(self._universe.values()), self._task_preference,
                                    self._last_generation, self._task_language,
                                    pet_rect, screen_rect)
            return
        self._last_pet_rect = pet_rect
        self._last_screen_rect = screen_rect
        if not self.legacy_exterior_motion:
            self._tick_halo(now, pet_rect, screen_rect)
            return
        if self._poll_park_plan(pet_rect, screen_rect):
            self._last_tick = now
            return
        if not self._motion_enabled():
            # Motion off: a parking glide owns all movement. Without
            # one, stray orbs begin gliding from their exact current
            # pixels (timer-only OFF needs no apply); parked orbs
            # stay frozen with a fresh clock (no hidden catch-up).
            self._last_motion_enabled = False
            last = self._last_tick
            dt = self._clamped_dt(
                0.0 if last is None else max(0.0, now - last))
            self._last_tick = now
            if self._park_blend is None:
                stray = self._park_survivors(pet_rect, screen_rect)
                if (stray and self._max_home_distance(
                        stray, pet_rect, screen_rect) >= 1.0):
                    self._begin_park_glide(pet_rect, screen_rect)
                    self._clear_trails()
                    last = self._last_tick
                    dt = self._clamped_dt(
                        0.0 if last is None else max(0.0, now - last))
                    self._last_tick = now
            if self._park_blend is not None:
                self._advance_park_glide(pet_rect, screen_rect, dt)
                self._prune_trails_only(now)
                if (self._park_blend is None
                        and self._live_armed()
                        and self.motion_timer.isActive()):
                    self.motion_timer.stop()
                return
            self._last_tick = now
            self._prune_trails_only(now)
            return
        if self._motion_enabled() != self._last_motion_enabled:
            # Motion re-enabled without an intervening apply (parked
            # static homes, possibly stale blend/clocks): stale holds
            # die here, then continuity is planned from the currently
            # visible geometry before the first animated frame,
            # exactly as an apply would. Ordinary ticks see matching
            # flags and skip this.
            self._clear_interaction_holds()
            self._maybe_start_blend(self._orbit_mode,
                                    dict(self._ring_offsets),
                                    pet_rect, screen_rect)
            self._last_motion_enabled = self._motion_enabled()
        if self._park_blend is not None:
            # Motion re-enabled into arc/static (or a recomposition
            # stranded orbs): finish gliding home first; the selected
            # mode resumes from homes on arrival without a jump.
            last = self._last_tick
            dt = self._clamped_dt(
                0.0 if last is None else max(0.0, now - last))
            self._last_tick = now
            if dt <= 0.0:
                return
            self._motion_t += dt
            still = self._advance_park_glide(pet_rect, screen_rect, dt)
            self._prune_trails_only(now)
            if not still and self._ring_blend is not None:
                # Parking landed under a ring selection: the next
                # ordinary tick glides outward from these homes.
                pass
            for key, orb in self._windows.items():
                try:
                    self._apply_breathing(orb, key)
                except Exception:
                    pass
            return
        pet_center = (pet_rect[0] + pet_rect[2] / 2.0,
                      pet_rect[1] + pet_rect[3] / 2.0)
        previous_center = getattr(self, '_last_tick_center', None)
        self._last_tick_center = pet_center
        if previous_center is not None:
            jump = math.hypot(pet_center[0] - previous_center[0],
                              pet_center[1] - previous_center[1])
            if jump > 120.0:
                # Pet teleported (not smooth-tracked): never paint a
                # full-screen streak for the jump itself.
                self._clear_trails()
        last = self._last_tick
        dt = self._clamped_dt(
            0.0 if last is None else max(0.0, now - last))
        self._last_tick = now
        if dt <= 0.0:
            return
        self._motion_t += dt
        mode = self._orbit_mode
        kind = mode[0] if isinstance(mode, tuple) else 'static'
        if kind == 'ring':
            if self._ring_paused():
                prop_ring_t = self._ring_t
                prop_blend_t = (self._ring_blend['t']
                                if self._ring_blend is not None else None)
            elif self._ring_blend is not None:
                # Recomposition glide: shared phase frozen, blend
                # progress is the only thing that advances. A blend
                # that cannot advance past a blocked path must not
                # stall the ring forever: after STALL_LIMIT_S of hold,
                # blockers are staged hidden and survivors glide alone
                # (or positions are preserved via rebase hold).
                prop_ring_t = self._ring_t
                prop_blend_t = self._ring_blend['t'] + dt
            else:
                prop_ring_t = self._ring_t + dt
                prop_blend_t = None
            nominal, float_centers = self._nominal_positions(
                pet_rect, screen_rect, ring_t=prop_ring_t,
                blend_t=prop_blend_t)
            if self._nominal_valid(nominal, pet_rect, screen_rect):
                self._ring_t = prop_ring_t
                if self._ring_blend is not None:
                    if prop_blend_t >= self._ring_blend['dur'] - 1e-9:
                        self._ring_blend = None
                    else:
                        self._ring_blend['t'] = prop_blend_t
                        self._ring_blend['stalled'] = 0.0
                self._move_orbs(nominal)
            else:
                if self._ring_blend is not None:
                    blend_hub = self._ring_blend.get('hub')
                    hub_now = (pet_rect[0] + pet_rect[2] / 2.0,
                               pet_rect[1] + pet_rect[3] / 2.0)
                    if blend_hub is None or blend_hub == hub_now:
                        stalled = (self._ring_blend.get('stalled', 0.0)
                                   + dt)
                        self._ring_blend['stalled'] = stalled
                    else:
                        # Hub moved mid-glide: the held frame belongs
                        # to the old hub, so this hold must not count
                        # toward the stall abort (which rebases around
                        # the current hub). The blend waits for hub
                        # return or apply-driven reselection.
                        stalled = self._ring_blend.get('stalled', 0.0)
                    if stalled >= pet_geometry.RING_BLEND_STALL_LIMIT_S:
                        # Blocked glide: newcomers parked across the
                        # path stall it indefinitely. Hide the
                        # blockers and glide survivors alone to final
                        # slots (staged recovery) rather than
                        # dead-holding a valid final ring. With no
                        # visible newcomers, preserve positions via
                        # the rebase hold instead.
                        blend = self._ring_blend
                        newcomers = [
                            k for k in self._windows
                            if k not in blend.get('start', {})
                            and k not in self._ring_staged]
                        if newcomers:
                            self._stage_keys(newcomers)
                            hub_now = (
                                pet_rect[0] + pet_rect[2] / 2.0,
                                pet_rect[1] + pet_rect[3] / 2.0)
                            starts_now = {}
                            for key, orb in self._windows.items():
                                if key in self._ring_staged:
                                    continue
                                starts_now[key] = (
                                    pet_geometry.ring_abs_angle_deg(
                                        orb.x() + 56.0, orb.y() + 48.0,
                                        hub_now[0], hub_now[1]))
                            plan = self._plan_direct_blend(
                                starts_now, [], pet_rect, screen_rect)
                            if plan is not None:
                                self._commit_blend_plan(
                                    starts_now, plan[0], plan[1],
                                    hub_now)
                            else:
                                # No safe rotation from the held frame:
                                # keep holding the last valid frame and
                                # retry later; never teleport to force
                                # the transition.
                                self._ring_blend['stalled'] = 0.0
                        else:
                            # Survivors-only glide blocked mid-path: keep
                            # holding the last valid frame and retry on
                            # later ticks; pet moves, retires, or fresh
                            # applies replan from these exact pixels.
                            # Positions never move here by construction.
                            self._ring_blend['stalled'] = 0.0
                self._hold_centers(float_centers)
            if (self._ring_staged and not self._ring_paused()
                    and self._ring_blend is None):
                # Survivors circulate blend-free: reveal staged stars
                # the moment their final slots validate with the live
                # set (possibly the same tick a blend just completed).
                self._maybe_reveal_staged(pet_rect, screen_rect)
        elif kind == 'arc':
            prop_times = {}
            for key in self._windows:
                if key in self._ring_staged:
                    # Staged newcomers are inert: their clocks must
                    # not advance while hidden, so a later reveal
                    # starts them exactly at the validated frame.
                    continue
                if key == self._hovered:
                    prop_times[key] = self._orbit_t.get(key, 0.0)
                else:
                    prop_times[key] = self._orbit_t.get(key, 0.0) + dt
            nominal, float_centers = self._nominal_positions(
                pet_rect, screen_rect, orbit_times=prop_times)
            if self._nominal_valid(nominal, pet_rect, screen_rect):
                self._orbit_t.update(prop_times)
                self._move_orbs(nominal)
            else:
                self._hold_centers(float_centers)
            if self._ring_staged and not self._ring_paused():
                # Survivors circulate: reveal staged stars the moment
                # their live arc slots validate with the visible set
                # (retries every tick until a safe envelope arrives).
                self._maybe_reveal_staged_arc(pet_rect, screen_rect)
        else:
            nominal, float_centers = self._nominal_positions(
                pet_rect, screen_rect)
            if self._nominal_valid(nominal, pet_rect, screen_rect):
                self._move_orbs(nominal)
            else:
                self._hold_centers(float_centers)
            if self._ring_staged and not self._ring_paused():
                # Static-mode survivors sit at homes: reveal staged
                # stars the moment the complete home set validates
                # (retries every tick until a safe frame arrives;
                # blocked newcomers stay hidden and inert).
                self._try_reveal_staged_at_homes(pet_rect, screen_rect)
        for key, orb in self._windows.items():
            try:
                self._apply_breathing(orb, key)
            except Exception:
                pass
        try:
            self._update_trails(now, float_centers)
        except Exception:
            pass

    def _move_orbs(self, nominal):
        """Commit validated window positions (shared tick/arc path)."""
        if self.expanded_identity is not None:
            return
        for key, pos in nominal.items():
            orb = self._windows.get(key)
            if orb is None:
                continue
            if self._placed.get(key) != pos:
                self._placed[key] = pos
                orb.move(*pos)

    def _hold_centers(self, float_centers):
        """Safety hold: report current positions as trail centers so a
        rejected frame paints no streak toward forbidden geometry.
        Clocks stay untouched by the caller (active-time rule)."""
        for key, orb in self._windows.items():
            float_centers[key] = (orb.x() + 56.0, orb.y() + 48.0)

    def retranslate(self, language):
        """Refresh orb wording after a language change."""
        language = normalize_language(language)
        self._task_language = language
        for key, orb in self._windows.items():
            try:
                task = self._universe.get(key) or {}
                orb.refresh(str(self._labels.get(key, 0)),
                            PROVIDER_NAMES.get(task.get('provider_id'),
                                               task.get('provider_id')),
                            language)
            except Exception:
                pass
        self._refresh_detail()

    def set_visible(self, visible):
        """Explicitly enable/disable the ring independently of the Hub.

        Staged newcomers stay hidden on restore: only the staged
        reveal path (validated final slots) may expose them.
        """
        if self._shutdown:
            return
        self._visible = bool(visible)
        if not self.legacy_exterior_motion:
            (getattr(self.panel, 'prefs', None) or {})['star_ring_enabled'] = self._visible
        if not self._visible:
            self.detail_transition.cancel()
            self._clear_trails()
            self.collapse_detail(replan=False)
            self._cancel_park_planning()
        elif self._orbit_mode == ('expanded_resume',):
            self.apply_snapshot(list(self._universe.values()), self._task_preference,
                                self._last_generation, self._task_language,
                                self._last_pet_rect, self._last_screen_rect)
        for key, orb in self._windows.items():
            try:
                if self._visible and key in self._ring_staged:
                    continue
                orb.show() if self._visible else orb.hide()
            except Exception:
                pass
        if not self._visible:
            # Nothing is hoverable while hidden: interaction holds
            # are visibility-local and must not outlive the hide.
            self._hover_holds = set()
            self._press_holds = set()
            self._hovered = None
        self.sync_motion()
        if not self.legacy_exterior_motion:
            self.back_overlay.setVisible(self._visible and self._halo_pose is not None)
            self.trail_overlay.setVisible(self._visible and self._halo_pose is not None)
            self._update_page_controls()
            self._stack_halo(force=True)
        if not self._visible:
            try:
                if self.trail_overlay.isVisible():
                    self.trail_overlay.hide()
            except Exception:
                pass

    def apply_topmost(self, on_top):
        """Mirror the always-on-top preference onto task stars."""
        self.detail_transition.cancel()
        if not self.legacy_exterior_motion:
            layer = self.back_overlay
            visible = layer.isVisible()
            layer.setWindowFlag(Qt.WindowStaysOnTopHint, bool(on_top))
            layer.setVisible(visible)
            self._halo_stack = None
        for orb in list(self._windows.values()) + ([self.detail_window] if self.detail_window else []):
            try:
                if bool(orb.windowFlags() & Qt.WindowStaysOnTopHint) != bool(on_top):
                    visible, position = orb.isVisible(), orb.pos()
                    orb.setWindowFlag(Qt.WindowStaysOnTopHint, bool(on_top))
                    if visible:
                        orb.show()
                    orb.move(position)
            except Exception:
                pass
        try:
            overlay = self.trail_overlay
            if bool(overlay.windowFlags() & Qt.WindowStaysOnTopHint) != bool(on_top):
                was_visible = overlay.isVisible()
                overlay.setWindowFlag(Qt.WindowStaysOnTopHint, bool(on_top))
                if was_visible:
                    overlay.show()
        except Exception:
            pass
        if not self.legacy_exterior_motion:
            # OFF/settled scenes have no timer to restore depth after HWND
            # recreation, so the preference boundary owns the native order.
            self._stack_halo(force=True)
            self._update_page_controls()

    def shutdown(self):
        """Stop motion, close every task star and the trail layer."""
        if self._shutdown:
            return
        self._shutdown = True
        if self.page_controls is not None:
            self.page_controls.close()
            self.page_controls.deleteLater()
            self.page_controls = None
        self.collapse_detail(replan=False)
        self.detail_transition.shutdown()
        if self.detail_window is not None:
            self.detail_window.manager = None
            self.detail_window.close()
            self.detail_window.deleteLater()
            self.detail_window = None
        self._cancel_park_planning()
        if not self.legacy_exterior_motion:
            self.back_overlay.clear_all()
            self.back_overlay.close()
        try:
            self.stop_motion()
        except Exception:
            pass
        try:
            self._clear_trails()
            self.trail_overlay.close()
        except Exception:
            pass
        for key in list(self._windows):
            orb = self._windows.pop(key)
            try:
                orb.close()
            except Exception:
                pass
        self._universe.clear()
        self._labels.clear()
        self._slots.clear()
        self._placed.clear()
        self._ring_slots = []
        self._orbit.clear()
        self._orbit_t.clear()
        self._arc_dirs.clear()
        self._ring_offsets = {}
        self._ring_t = 0.0
        self._ring_blend = None
        self._park_blend = None
        self._ring_staged = set()
        self._hover_holds = set()
        self._press_holds = set()
        self._hovered = None
        self._last_motion_enabled = None
        self._last_tick_center = None
        self.last_activated = None


class Settings(QDialog):
    def __init__(self, panel):
        super().__init__(panel)
        self.setMinimumWidth(540)
        layout = QVBoxLayout(self)
        self.form = QFormLayout()
        self.task = QComboBox()
        self.task.addItem('', '')
        for row in panel.snapshot.get('rows', []):
            self.task.addItem(row.get('name') or row.get('title','').split('\n')[0][:60] or
                              text('task_unnamed', panel.prefs.get('language')), row['id'])
        self.task.setCurrentIndex(max(0, self.task.findData(panel.prefs.get('pinned', ''))))
        self.task.setMaximumWidth(390)
        self.task_label = label()
        self.form.addRow(self.task_label, self.task)
        self.scope = QComboBox()
        for key in ('global','project','conversation'):
            self.scope.addItem('', key)
        selected_scope = {'task':'conversation'}.get(panel.prefs.get('scope'), panel.prefs.get('scope'))
        selected_index = self.scope.findData(selected_scope)
        self.scope.setCurrentIndex(selected_index if selected_index >= 0 else self.scope.findData('conversation'))
        self.scope_label = label()
        self.form.addRow(self.scope_label, self.scope)
        self.tracking = QComboBox()
        for key in TRACKING_CHOICES:
            self.tracking.addItem('', key)
        self.tracking.setCurrentIndex(max(0, self.tracking.findData(
            normalize_tracking_provider(panel.prefs.get('tracking_provider')))))
        self.tracking_label = label()
        # A single source needs no provider chooser. Retain the hidden field
        # only for old preference readers; normalized output is always Codex.
        self.tracking.hide()
        self.tracking_label.hide()
        self.language = QComboBox()
        initial_language = normalize_language(panel.prefs.get('language'))
        self.language.addItem(text('language_zh_CN', initial_language), 'zh_CN')
        self.language.addItem(text('language_en', initial_language), 'en')
        self.language.setCurrentIndex(self.language.findData(normalize_language(panel.prefs.get('language'))))
        self.language_label = label()
        self.form.addRow(self.language_label, self.language)
        self.token_format = QComboBox()
        self.token_format.addItem('', 'full')
        self.token_format.addItem('', 'compact')
        self.token_format.setCurrentIndex(self.token_format.findData(
            normalize_token_format(panel.prefs.get('token_number_format'))))
        self.token_format_label = label()
        self.form.addRow(self.token_format_label, self.token_format)
        self.currency = QComboBox()
        for code in SUPPORTED_CURRENCIES:
            self.currency.addItem(code, code)
        self.currency.setCurrentIndex(self.currency.findData(
            normalize_currency(panel.prefs.get('currency'))))
        self.currency_label = label()
        self.form.addRow(self.currency_label, self.currency)
        self.topmost = QCheckBox()
        self.topmost.setChecked(bool(panel.prefs.get('always_on_top', True)))
        self.topmost_label = label()
        self.form.addRow(self.topmost_label, self.topmost)
        self.star_ring = QCheckBox()
        self.star_ring.setChecked(bool(panel.prefs.get('star_ring_enabled', True)))
        self.star_ring_label = label()
        self.form.addRow(self.star_ring_label, self.star_ring)
        self._initial_scale = pet_geometry.normalize_pet_scale(
            panel.prefs.get('pet_scale_percent', pet_geometry.PET_SCALE_DEFAULT))
        self.pet_scale = QSlider(Qt.Horizontal)
        self.pet_scale.setRange(pet_geometry.PET_SCALE_MIN, pet_geometry.PET_SCALE_MAX)
        self.pet_scale.setSingleStep(5)
        self.pet_scale.setPageStep(25)
        self.pet_scale.setTickPosition(QSlider.TicksBelow)
        self.pet_scale.setTickInterval(25)
        self.pet_scale.setValue(self._initial_scale)
        self.pet_scale_value = label(f'{self._initial_scale}%')
        self.pet_scale_value.setFixedWidth(48)
        self.pet_scale_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        scale_row = QHBoxLayout()
        scale_row.addWidget(self.pet_scale, 1)
        scale_row.addWidget(self.pet_scale_value)
        scale_box = QWidget()
        scale_box.setLayout(scale_row)
        self.pet_scale_label = label()
        self.form.addRow(self.pet_scale_label, scale_box)
        self.pet_scale.valueChanged.connect(self._preview_pet_scale)
        layout.addLayout(self.form)
        layout.addWidget(divider())
        self.about_heading = label('')
        self.about_heading.setStyleSheet(f'color:{ICE}; font-size:13px; font-weight:600;')
        layout.addWidget(self.about_heading)
        self.about_titles = []
        self.about_bodies = []
        for _ in range(4):
            title = label('')
            title.setStyleSheet(f'color:{ICE}; font-weight:600;')
            body = label('', 'muted')
            body.setWordWrap(True)
            layout.addWidget(title)
            layout.addWidget(body)
            self.about_titles.append(title)
            self.about_bodies.append(body)
            layout.addSpacing(6)
        self.error = label('', 'muted')
        layout.addWidget(self.error)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.save)
        self.buttons.rejected.connect(self.reject)
        self.reset_armed = False
        self.reset_button = button('', '', self.reset_to_defaults)
        reset_row = QHBoxLayout()
        reset_row.addStretch()
        reset_row.addWidget(self.reset_button)
        layout.addLayout(reset_row)
        layout.addWidget(self.buttons)
        self.language.currentIndexChanged.connect(self.apply_language)
        self.apply_language()

    def tr_text(self, key, **values):
        return text(key, self.language.currentData(), **values)

    def _preview_pet_scale(self, value):
        # Live preview only: the pet resizes immediately, but nothing is
        # written to disk until Save. Cancel restores the saved value.
        self.pet_scale_value.setText(f'{int(value)}%')
        pet = getattr(self.parentWidget(), 'pet', None)
        if pet is not None:
            pet.apply_pet_scale(int(value))

    def reject(self):
        pet = getattr(self.parentWidget(), 'pet', None)
        if pet is not None:
            pet.apply_pet_scale(self._initial_scale)
        super().reject()

    def apply_language(self):
        t = self.tr_text
        self.setWindowTitle(t('settings_title'))
        self.task.setItemText(0, t('task_auto'))
        for index, scope in enumerate(('global','project','conversation')):
            self.scope.setItemText(index, scope_text(scope, self.language.currentData(), recorded=scope == 'global'))
        for index, key in enumerate(TRACKING_CHOICES):
            self.tracking.setItemText(index, t(f'tracking_{key}'))
        self.tracking_label.setText(t('tracking_provider'))
        self.language.setItemText(0, t('language_zh_CN'))
        self.language.setItemText(1, t('language_en'))
        self.token_format.setItemText(self.token_format.findData('full'), t('token_format_full'))
        self.token_format.setItemText(self.token_format.findData('compact'), t('token_format_compact'))
        self.task_label.setText(t('task_selection'))
        self.scope_label.setText(t('token_scope'))
        self.language_label.setText(t('language'))
        self.token_format_label.setText(t('token_number_format'))
        self.currency_label.setText(t('currency'))
        for index, code in enumerate(SUPPORTED_CURRENCIES):
            self.currency.setItemText(index, code)
        self.topmost_label.setText(t('always_on_top'))
        self.topmost.setToolTip(t('always_on_top'))
        self.topmost.setAccessibleName(t('always_on_top'))
        self.star_ring_label.setText(t('star_ring_enabled'))
        self.star_ring.setAccessibleName(t('star_ring_enabled'))
        self.pet_scale_label.setText(t('character_size'))
        self.pet_scale.setToolTip(t('character_size'))
        self.pet_scale.setAccessibleName(t('character_size'))
        self.pet_scale_value.setText(f'{int(self.pet_scale.value())}%')
        self.about_heading.setText(t('about_data'))
        for index in range(4):
            self.about_titles[index].setText(f"{index + 1}. {t(f'about_{index + 1}_title')}")
            self.about_bodies[index].setText(t(f'about_{index + 1}_body'))
        self.buttons.button(QDialogButtonBox.Save).setText(t('save'))
        self.buttons.button(QDialogButtonBox.Cancel).setText(t('cancel'))
        self.reset_button.setText(t('confirm_reset' if self.reset_armed else 'reset_defaults'))
        self.reset_button.setToolTip(t('confirm_reset' if self.reset_armed else 'reset_defaults'))

    def reset_to_defaults(self):
        # Two-click inline confirmation (no system-language modal dialog):
        # first click arms, second click restores factory defaults into the
        # form. Nothing persists until Save.
        if not self.reset_armed:
            self.reset_armed = True
            self.apply_language()
            return
        self.reset_armed = False
        self.task.setCurrentIndex(0)
        self.scope.setCurrentIndex(self.scope.findData('conversation'))
        self.tracking.setCurrentIndex(self.tracking.findData('codex'))
        self.language.setCurrentIndex(self.language.findData(DEFAULT_LANGUAGE))
        self.token_format.setCurrentIndex(
            self.token_format.findData(DEFAULT_TOKEN_NUMBER_FORMAT))
        self.currency.setCurrentIndex(self.currency.findData(DEFAULT_CURRENCY))
        self.topmost.setChecked(True)
        self.star_ring.setChecked(True)
        self.pet_scale.setValue(pet_geometry.PET_SCALE_DEFAULT)
        self.apply_language()

    def save(self):
        panel = self.parentWidget()
        prefs = dict(panel.prefs)
        old_tracking = normalize_tracking_provider(panel.prefs.get('tracking_provider'))
        tracking = normalize_tracking_provider(self.tracking.currentData())
        prefs.update(pinned=self.task.currentData(), scope=self.scope.currentData(),
                     tracking_provider=tracking,
                     language=normalize_language(self.language.currentData()),
                     token_number_format=self.token_format.currentData(),
                     currency=self.currency.currentData(),
                     always_on_top=self.topmost.isChecked(),
                     star_ring_enabled=self.star_ring.isChecked(),
                     pet_scale_percent=int(self.pet_scale.value()))
        # Legacy `manual_fx` / `prices` keys stay untouched in the file for
        # backward-compatible loading, but no longer drive pricing or FX.
        try:
            write_preferences(prefs)
        except OSError:
            self.error.setText(self.tr_text('settings_save_error'))
            return
        panel.prefs = prefs
        panel.task_manager.set_visible(prefs['star_ring_enabled'])
        # Every save retires outstanding requests for the previous
        # settings, even when only scope/pinned changed: the new epoch
        # makes late completions identifiable as old. Only a changed-to-
        # explicit tracking choice stamps use time. The snapshot
        # publishes synchronously — no slow poll is awaited.
        poller = getattr(panel, 'provider_poller', None)
        if poller is not None:
            snapshot = poller.apply_settings(
                prefs,
                mark_provider=(tracking if tracking != old_tracking
                               and tracking != 'auto' else None))
            panel.publish_snapshot(snapshot)
        pet = getattr(panel, 'pet', None)
        if pet is not None:
            pet.apply_pet_scale(prefs['pet_scale_percent'])
        panel.reset_store.set()
        panel.apply_language()
        panel.apply_topmost()
        self.accept()


class Panel(QWidget):
    def __init__(self, live=True):
        super().__init__()
        # Live panels run background loops and the shared star-motion
        # clock; unit tests construct live=False and must never arm
        # real timers (deterministic assertions).
        self.live = bool(live)
        self.prefs = read_preferences()
        self.app_mode = AppModeState()
        self.codex_activity = dict(active=False, valid=False, reason='starting')
        self.provider_poller = ProviderPoller()
        self._render_generation = None
        self.quota_provider = None
        self.snapshot = {}
        self.analytics_window = None
        self.workbench_window = None
        self._workbench_temp = None
        self.want_history = threading.Event()
        self.quota = {}
        self.fx_data = self.prefs.get('fx_cache') or dict(
            date='2026-09-15', source='Bank of Canada · bundled', rates={'CAD': 1.3917})
        self.closing = False
        self.stop = threading.Event()
        self.reset_store = threading.Event()
        self.bridge = Bridge()
        self.bridge.data.connect(self.render)
        self.bridge.limits.connect(self.receive_limits)
        self.bridge.fx.connect(self.receive_fx)
        # One pet owns the accepted task Stars; Hub inspection has its own
        # pinned conversation and scope without changing Star selection.
        self.task_manager = TaskPanelManager(self)
        self.setWindowTitle('petoken')
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFixedSize(*HUB_SIZE)
        self.setStyleSheet(STYLE)
        # The character remains in its own anchored window; this is its satellite.
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        self.surface = QWidget()
        self.surface.setObjectName('hubSurface')
        outer.addWidget(self.surface)
        layout = QVBoxLayout(self.surface)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(8)
        self.header = QWidget()
        self.header.setObjectName('hubHeader')
        self.header.setCursor(Qt.SizeAllCursor)
        head = QHBoxLayout(self.header)
        head.setContentsMargins(0,0,0,0)
        head.setSpacing(12)
        brand = QVBoxLayout()
        brand.setSpacing(3)
        brand.addWidget(label('PETOKEN', 'brand'))
        self.connection = label('', 'muted')
        brand.addWidget(self.connection)
        head.addLayout(brand)
        head.addStretch()
        controls = QHBoxLayout()
        controls.setSpacing(6)
        self.collapse_button = button('−', '', self.toggle_compact)
        self.collapse_button.setFixedSize(30, 28)
        controls.addWidget(self.collapse_button)
        self.hide_button = button('×', '', self.hide_to_tray)
        self.hide_button.setFixedSize(30, 28)
        controls.addWidget(self.hide_button)
        head.addLayout(controls)
        layout.addWidget(self.header)
        self.project = label('', 'muted')
        layout.addWidget(self.project)
        self.title = ElidedLabel('')
        self.title.setStyleSheet('font-size:17px; font-weight:600;')
        layout.addWidget(self.title)
        self.tasks_button = button('', '', lambda: None)
        self.task_menu = QMenu(self.tasks_button)
        self.tasks_button.setMenu(self.task_menu)
        self.task_menu.aboutToShow.connect(self.refresh_task_menu)
        layout.addWidget(self.tasks_button)
        self.task_provenance = ElidedLabel()
        self.task_provenance.setFixedHeight(18)
        self.task_provenance.setObjectName('muted')
        layout.addWidget(self.task_provenance)
        model_row = QHBoxLayout()
        model_row.setSpacing(8)
        self.model = ElidedLabel('—')
        self.model.setStyleSheet(f'color:{ICE}; font-size:13px;')
        model_row.addWidget(self.model)
        self.effort = label('—', 'badge')
        model_row.addWidget(self.effort)
        model_row.addStretch()
        layout.addLayout(model_row)
        # Intentional compact composition (A3): one metrics row (cost hero +
        # token hero sharing the width) plus one control strip. The expanded
        # bars lend their widgets here while compact; nothing is duplicated.
        self.compact_box = QWidget()
        compact_layout = QVBoxLayout(self.compact_box)
        compact_layout.setContentsMargins(0, 0, 0, 0)
        compact_layout.setSpacing(8)
        compact_layout.addWidget(divider())
        metrics = QHBoxLayout()
        metrics.setSpacing(12)
        cost_hero = QVBoxLayout()
        cost_hero.setSpacing(4)
        # Compact cost twins auto-fit like the token hero, so Full numbers
        # plus large costs share one 360 px row without overlap. The expanded
        # cost widgets stay untouched in their hidden bar.
        self.compact_cost_label = label('', 'muted')
        cost_hero.addWidget(self.compact_cost_label)
        self.compact_cost = TokenTotalLabel(base_size=22, object_name='cost')
        self.compact_cost.setWordWrap(False)
        cost_hero.addWidget(self.compact_cost)
        metrics.addLayout(cost_hero, 1)
        token_hero = QVBoxLayout()
        token_hero.setSpacing(4)
        self.compact_token_header = label('', 'muted')
        self.compact_token_header.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        token_hero.addWidget(self.compact_token_header)
        self.compact_total = TokenTotalLabel()
        self.compact_total.setWordWrap(False)
        self.compact_total.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        token_hero.addWidget(self.compact_total)
        metrics.addLayout(token_hero, 1)
        compact_layout.addLayout(metrics)
        self.compact_foot = QHBoxLayout()
        self.compact_foot.setSpacing(8)
        self.compact_foot.addStretch()
        compact_layout.addLayout(self.compact_foot)
        self.compact_box.setVisible(False)
        self._compact_docked = False
        layout.addWidget(self.compact_box)
        self.body = QWidget()
        body = QVBoxLayout(self.body)
        body.setContentsMargins(0,0,0,0)
        body.setSpacing(6)
        token_header = QHBoxLayout()
        self.total_header = label('', 'muted')
        token_header.addWidget(self.total_header)
        token_header.addStretch()
        self.scope_button = button('', '', self.scope_menu)
        self.scope_button.setStyleSheet(f'color:{MUTED};font-size:11px;padding:0px 3px;min-height:24px;')
        token_header.addWidget(self.scope_button)
        body.addLayout(token_header)
        self.total = TokenTotalLabel()
        body.addWidget(self.total)
        status_row = QHBoxLayout()
        status_row.setSpacing(6)
        self.status_dot = label('●')
        status_row.addWidget(self.status_dot)
        self.status_text = label('', 'muted')
        status_row.addWidget(self.status_text)
        status_row.addStretch()
        body.addLayout(status_row)
        self.io_line = label('', 'muted')
        self.io_line.setWordWrap(True)
        body.addWidget(self.io_line)
        self.insights = label('', 'muted')
        self.insights.setWordWrap(True)
        body.addWidget(self.insights)
        details_row = QHBoxLayout()
        self.workbench_button = button('', '', self.open_workbench)
        details_row.addWidget(self.workbench_button)
        details_row.addStretch()
        self.details_button = button('', '', self.open_analytics)
        details_row.addWidget(self.details_button)
        body.addLayout(details_row)
        self.quota_divider = divider()
        body.addWidget(self.quota_divider)
        self.context = Meter('', VIOLET)
        self.five = Meter('', ICE)
        self.week = Meter('', VIOLET)
        body.addWidget(self.context)
        body.addWidget(self.five)
        body.addWidget(self.week)
        # Pin content to the top so tall windows keep one compact visual
        # group instead of spreading sections apart.
        body.addStretch(1)
        layout.addWidget(self.body, 1)
        cost_row = QHBoxLayout()
        cost_row.setContentsMargins(0, 0, 0, 0)
        self.cost_row_layout = cost_row
        cost_left = QVBoxLayout()
        cost_left.setSpacing(4)
        self.cost_label = label('', 'muted')
        self.cost = label('—', 'cost')
        cost_left.addWidget(self.cost_label)
        cost_left.addWidget(self.cost)
        cost_row.addLayout(cost_left)
        cost_row.addStretch()
        self.cost_bar = QWidget()
        self.cost_bar.setLayout(cost_row)
        layout.addWidget(self.cost_bar)
        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)
        self.bottom_layout = bottom
        self.status = label('', 'muted')
        bottom.addWidget(self.status)
        # Provider mode (Auto / Manual) lives here, visually separate from
        # the task/session context shown in the header connection line.
        self.provider_mode = label('', 'muted')
        bottom.addWidget(self.provider_mode)
        bottom.addStretch()
        self.settings_button = button('⚙', '', self.open_settings)
        bottom.addWidget(self.settings_button)
        self.bottom_bar = QWidget()
        self.bottom_bar.setLayout(bottom)
        layout.addWidget(self.bottom_bar)
        self.header.mousePressEvent = self.begin_drag
        self.header.mouseMoveEvent = self.drag
        self.header.mouseReleaseEvent = self.end_drag
        # Keep the vector spirit for the tray/window icon only.
        self.spirit = Spirit()
        self.spirit.setVisible(False)
        for text, delta in [('Left',(-10,0)),('Right',(10,0)),('Up',(0,-10)),('Down',(0,10))]:
            QShortcut(QKeySequence('Alt+'+text), self, activated=lambda d=delta:self.move_clamped(self.pos()+QPoint(*d)))
        QShortcut(QKeySequence('Escape'), self, activated=self.handle_escape)
        self.tray = QSystemTrayIcon(self)
        pix = QPixmap(64,64)
        pix.fill(Qt.transparent)
        self.spirit.render(pix)
        self.setWindowIcon(QIcon(pix))
        self.tray.setIcon(QIcon(pix))
        menu = QMenu()
        self.tray_actions = {
            'show_hide': menu.addAction('', self.toggle_visible),
            'show_hide_pet': menu.addAction('', self.toggle_pet),
            'workbench_open': menu.addAction('', self.open_workbench),
            'wb_tutorial': menu.addAction('', self.open_workbench_tutorial),
            'analytics_button': menu.addAction('', self.open_analytics),
            'collapse_expand': menu.addAction('', self.toggle_compact),
            'settings_help': menu.addAction('', self.open_settings),
            'move_right': menu.addAction('', self.reset_position),
        }
        menu.addSeparator()
        self.tray_actions['exit_petoken'] = menu.addAction('', self.shutdown)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason:self.toggle_visible() if reason == QSystemTrayIcon.DoubleClick else None)
        self.tray.show()
        self.tray_menu = menu
        self.compact = bool(self.prefs.get('compact', False))
        self.apply_language()
        self.apply_compact()
        self.apply_topmost()
        if isinstance(self.prefs.get('position'), list) and len(self.prefs['position']) == 2:
            self.move_clamped(QPoint(*map(int,self.prefs['position'])))
        else:
            self.reset_position()
        self.active = ActiveTask()
        self.rates = RateLimits(self.bridge.limits.emit)
        from activity import ActivityMonitor
        self.activity=ActivityMonitor()
        if live:
            self.activity.start()
            self.active.start()
            self.rates.start()
            threading.Thread(target=self.read_loop, daemon=True, name='codex-local-usage').start()
            threading.Thread(target=self.fx_loop, daemon=True, name='cad-rate').start()
        self.clock = QTimer(self)
        self.clock.timeout.connect(self.refresh_status)
        self.clock.start(1000)

    def anchor_to_pet(self):
        pet = getattr(self, 'pet', None)
        if pet is None:
            return
        import pet_geometry as geometry
        screen = QApplication.screenAt(pet.geometry().center()) or pet.screen()
        r = screen.availableGeometry()
        point = geometry.panel_position((pet.x(), pet.y(), pet.width(), pet.height()),
            (self.width(), self.height()), (r.left(), r.top(), r.right(), r.bottom()))
        self.move(*point)

    def restore_companion(self):
        """Called after both windows exist; pinned startup uses the same anchor."""
        self.pet.show()
        self.task_manager.apply_snapshot(list(self.task_manager._universe.values()))
        if self.is_pinned():
            self.pet.show_panel()

    def showEvent(self, event):
        super().showEvent(event)
        self.anchor_to_pet()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.isVisible():
            self.anchor_to_pet()

    @property
    def language(self):
        return normalize_language(self.prefs.get('language'))

    def tr_text(self, key, **values):
        return text(key, self.language, **values)

    def display_text(self, value, fallback):
        return self.tr_text(value) if value in (
            'display_all_usage', 'display_local_history', 'display_untitled',
            'project_unavailable') else (value or self.tr_text(fallback))

    def apply_language(self):
        self.prefs['language'] = self.language
        t = self.tr_text
        self.spirit.setAccessibleName(t('spirit_accessible'))
        self.connection.setText(t('connecting'))
        self.collapse_button.setToolTip(t('collapse_expand'))
        self.collapse_button.setAccessibleName(t('collapse_expand'))
        self.hide_button.setToolTip(t('hide_to_tray'))
        self.hide_button.setAccessibleName(t('hide_to_tray'))
        self.project.setText(t('waiting_codex'))
        self.title.setFullText(t('open_codex_task'))
        self.total_header.setText(t('total_tokens'))
        self.compact_token_header.setText(t('total_tokens'))
        self.scope_button.setToolTip(t('switch_scope'))
        self.scope_button.setAccessibleName(t('switch_scope'))
        self.scope_button.setText(scope_text(self.snapshot.get('scope', self.prefs.get('scope')),
                                             self.language, recorded=self.snapshot.get('scope') == 'global') + ' ▾')
        self.insights.setText(t('cache_hit_new_work', ratio='—', work='—'))
        self.insights.setToolTip(help_text('cache_hit_ratio', self.language)+'\n'+help_text('new_work', self.language))
        self.details_button.setText(t('analytics_button'))
        self.details_button.setToolTip(t('analytics_button_tip'))
        self.details_button.setAccessibleName(t('analytics_button_tip'))
        self.workbench_button.setText(t('workbench_open'))
        self.workbench_button.setAccessibleName(t('workbench_open'))
        self.context.set_title(t('context_used'))
        self.five.set_title(t('five_hour_limit'))
        self.week.set_title(t('weekly_limit'))
        self.cost_label.setText(t('estimated_cost')+f" · {normalize_currency(self.prefs.get('currency'))}")
        self.compact_cost_label.setText(self.cost_label.text())
        self.update_panel_controls()
        self.status.setText(t('checking_wait'))
        self.refresh_provider_mode(self.snapshot or {})
        self.refresh_task_controls()
        self.task_manager.retranslate(self.language)
        self.settings_button.setToolTip(t('settings_help'))
        self.settings_button.setAccessibleName(t('settings_help'))
        self.tray.setToolTip(t('tray_tip'))
        for key, action in self.tray_actions.items():
            action.setText(t(key))
        if self.analytics_window:
            self.analytics_window.apply_language()
        if self.workbench_window:
            self.workbench_window.apply_language()
        if hasattr(self, 'pet'):
            self.pet.apply_language()
        if self.snapshot:
            self.render(self.snapshot)

    def read_loop_once(self):
        """One production provider-loop iteration.

        Always returns a context-tagged snapshot (generation plus the
        tick's preference/scope/pinned): fallback construction lives in
        ProviderPoller.loop_tick, so no caller can emit an untagged
        provider payload to the Qt bridge. Never stamps use-time.
        """
        prefs = dict(self.prefs)
        reset_requested = False
        if self.reset_store.is_set():
            self.reset_store.clear()
            reset_requested = True
        detection_valid = time.time()-self.active.seen < 5
        active = self.active.title if detection_valid else ''
        return self.provider_poller.loop_tick(
            prefs, active_title=active,
            detection_valid=detection_valid,
            want_history=self.want_history.is_set(),
            reset_requested=reset_requested)

    def read_loop(self):
        # One sequential background loop polls both providers through the
        # shared poller: each provider fails independently, selection is
        # computed off the GUI thread, and exactly one atomic snapshot
        # is published per tick with a rising generation.
        while not self.stop.is_set():
            start = time.monotonic()
            try:
                snapshot = self.read_loop_once()
                self.publish_snapshot(snapshot)
            except Exception:
                # All expected failures already return tagged snapshots
                # from loop_tick. An unexpected error here (torn-down
                # prefs/bridge during shutdown) must never emit an
                # untagged payload that could overwrite newer UI.
                pass
            self.stop.wait(max(0,1-(time.monotonic()-start)))

    def fx_loop(self):
        while not self.stop.is_set():
            try:
                self.bridge.fx.emit(fetch_fx())
            except Exception:
                pass  # Last-known rate remains dated and visible in the tooltip.
            self.stop.wait(6*60*60)

    def receive_fx(self, data):
        self.fx_data = data
        self.prefs['fx_cache'] = data
        self.persist()
        self.refresh_cost()

    @property
    def currency(self):
        return normalize_currency(self.prefs.get('currency'))

    @property
    def fx(self):
        return normalize_rates(self.fx_data)

    def receive_limits(self, data):
        self.quota.update(data)
        # Quota payloads are Codex-sidecar data; the provider tag keeps a
        # foreign or late mismatched payload from supplying current quota chrome.
        if isinstance(data, dict) and data.get('provider_id'):
            self.quota_provider = data['provider_id']
        self.refresh_status()

    def render(self, data):
        if self.closing:
            return
        data = data or {}
        if (data.get('provider_id') or 'codex') != 'codex':
            return
        generation = data.get('generation')
        # Legacy generation-less payloads (synthetic fixtures, old local
        # callers) still render below; the production provider loop can
        # no longer produce them — read_loop_once always returns a
        # poller-tagged generation — so this path can never bypass the
        # multi-provider generation guard for live emissions.
        if (generation is not None and self._render_generation is not None
                and generation < self._render_generation):
            return  # Late result: never restore an older provider/scope.
        if generation is not None:
            self._render_generation = generation
        self.snapshot = data
        provider = data.get('provider_id') or 'codex'
        provider_label = 'Codex'
        self.apply_provider_chrome(provider)
        selection = data.get('selection')
        if selection is None:
            # Legacy/raw shape (synthetic fixtures, old callers): the
            # long-standing Codex behavior below is unchanged.
            self.codex_activity = data.get('codex_activity') or dict(active=False,valid=False,reason='missing')
            self.app_mode.update(self.codex_activity.get('active',False), self.codex_activity.get('valid',False))
        else:
            # Slice 5: the shared selection drives mode; widgets never
            # re-derive activity from provider payloads here.
            live = bool(selection.get('live'))
            reliable = bool(selection.get('selected')
                            and selection.get('source_available')
                            and not selection.get('stale')
                            and not selection.get('activity_unknown'))
            self.app_mode.update(live, reliable)
            self.codex_activity = dict(active=live, valid=reliable,
                                       reason=selection.get('reason', ''))
        if hasattr(self,'pet'):
            self.pet.update_data(data)
        # Multi-task snapshot first: the manager designates the main task
        # (if any) from the authoritative universe before legacy widgets
        # render, so the task-mode override below always sees fresh state.
        self.refresh_task_panels(data)
        if data.get('status') or not data.get('available'):
            status = self.tr_text(data.get('status') or 'no_reliable_record')
            self.connection.setText(f'{provider_label} · {status}')
            self.connection.setToolTip(status)
            self.title.setFullText(self.tr_text('waiting_available_task'))
            self.project.setText(provider_label.upper())
            self.project.setToolTip(provider_label.upper())
            self.model.setFullText('—')
            for w in (self.total,self.effort,self.cost,self.compact_total,
                        self.compact_cost):
                w.setText('—')
                w.setToolTip(status)
            self.io_line.setText('—')
            self.io_line.setToolTip(status)
            self.insights.setText(self.tr_text('cache_hit_new_work', ratio='N/A', work='N/A'))
            self.scope_button.setText(scope_text(data.get('scope', self.prefs.get('scope')), self.language)+' ▾')
            self.status_dot.setVisible(False)
            self.status_text.setVisible(False)
            self.context.update_value(None, tip=status)
            if self.analytics_window:
                self.analytics_window.update_data(data)
            # Same-transaction clearing: provider-specific quota, cost,
            # context and status widgets must not keep previous values.
            self.refresh_cost()
            self.refresh_status()
            return
        modes = {'follow':'mode_follow', 'fixed':'mode_fixed', 'recent':'mode_recent', 'working':'mode_working'}
        self.connection.setText(f'{provider_label} · {self.tr_text(modes.get(data.get("mode"),"waiting_data"))}')
        self.connection.setToolTip(self.tr_text('task_detection_tip'))
        project_text = self.display_text(data.get('project'), 'waiting_codex').upper()
        self.project.setText(project_text)
        self.project.setToolTip(project_text)
        self.title.setFullText(self.display_text(data.get('title'), 'unnamed_task'))
        self.model.setFullText(data.get('model') or self.tr_text('model_not_recorded'))
        self.model.setToolTip(self.model.full_text + '\n' + self.tr_text('model_tip'))
        self.effort.setText((data.get('effort') or '—')+(' · fast' if data.get('tier') in ('priority','fast') else ''))
        self.effort.setToolTip(self.tr_text('effort_tip'))
        tokens = data.get('tokens', {})
        token_style = self.prefs.get('token_number_format')
        total = tokens.get('total_tokens',0)
        total_text = format_token_value(total, token_style) if data.get('available') else '—'
        total_tip = ((format_tokens(total, 'full') if data.get('available')
                      else self.tr_text('no_reliable_record'))
                     + '\n' + help_text('total_tokens', self.language))
        self.total.setText(total_text)
        self.total.setToolTip(total_tip)
        self.compact_total.setText(total_text)
        self.compact_total.setToolTip(total_tip)
        if data.get('available'):
            cached = self.tr_text('cached_input_line', value=format_tokens(tokens.get('cached_input_tokens'), token_style))
            self.io_line.setText(f"{self.tr_text('input')} {format_tokens(tokens.get('input_tokens'), token_style)} · {self.tr_text('output')} {format_tokens(tokens.get('output_tokens'), token_style)}")
            self.io_line.setToolTip(cached+'\n'+self.tr_text('output_includes_reasoning'))
        else:
            self.io_line.setText('—')
            self.io_line.setToolTip(self.tr_text('no_reliable_record'))
        activity = data.get('scope_activity') or {}
        if selection is not None:
            # Selection owns liveness: scope activity never overrides it.
            if selection.get('live'):
                activity = dict(valid=True, active=True)
            elif selection.get('stale'):
                activity = dict(valid=True, active=False, stale=True)
            elif selection.get('activity_unknown'):
                activity = dict(valid=False, active=False)
            else:
                activity = dict(valid=True, active=False)
        working = bool(activity.get('valid') and activity.get('active'))
        self.status_dot.setVisible(True)
        self.status_text.setVisible(True)
        self.status_dot.setStyleSheet(f'color:{ICE if working else MUTED};')
        if working:
            state_key = 'working'
        elif activity.get('stale'):
            state_key = 'status_stale'
        elif activity.get('valid'):
            state_key = 'idle'
        else:
            state_key = 'unknown'
        self.status_text.setText(self.tr_text(state_key))
        self.scope_button.setText(scope_text(data.get('scope'), self.language, recorded=data.get('scope') == 'global')+' ▾')
        self.context.update_value(data.get('context'), 'used', self.tr_text('context_tip',
            used=data.get('context_tokens'), window=data.get('context_window')))
        self.refresh_cost()
        self.refresh_status()
        derived=(data.get('analytics') or {}).get('derived',{})
        hit=derived.get('cache_hit_ratio')
        self.insights.setText(self.tr_text('cache_hit_new_work',
            ratio='N/A' if hit is None else f'{hit:.1f}%',
            work=format_tokens(derived.get('new_work'), token_style)))
        if self.analytics_window and self.analytics_window.isVisible():
            self.analytics_window.update_data(
                self.analytics_payload(data, provider))
        self.apply_hub_neutralization(provider_label, data)

    def publish_snapshot(self, snapshot):
        """Emit one poll envelope to the GUI thread with task sets attached.

        The bridge carries the legacy result plus the accepted coherent
        active-task list and the tick preference, so the manager filters
        and renders without any provider re-read.
        """
        if self.closing:
            return
        snapshot = snapshot or {}
        out = dict(snapshot.get('result') or {})
        out['active_tasks'] = list(snapshot.get('active_tasks') or [])
        out['preference'] = snapshot.get('preference') or 'auto'
        self.bridge.data.emit(out)

    def refresh_provider_mode(self, data):
        """Display the current sole source without obsolete selection modes."""
        self.provider_mode.setText('Codex')
        self.provider_mode.setToolTip('Codex')

    def refresh_task_panels(self, data):
        """Apply accepted active tasks to the orb manager.

        Every visible task gets exactly one orb independent of Hub
        inspection. Only the Slice C envelope
        carries an authoritative task set: the Codex lane payload embeds
        its own raw per-lane set inside ``result`` for poller-internal
        use, which is deliberately ignored here (unfiltered,
        coherence-untagged). Legacy result-only renders therefore behave
        exactly as before Slice C.
        """
        data = data or {}
        self.refresh_provider_mode(data)
        preference = (data.get('preference')
                      or normalize_tracking_provider(self.prefs.get('tracking_provider')))
        tasks = data.get('active_tasks') if 'preference' in data else []
        try:
            self.task_manager.apply_snapshot(
                tasks or [], preference=preference,
                generation=data.get('generation'),
                language=self.language)
        except Exception:
            # Task orbs are additive presentation: they must never break
            # the legacy companion panel render.
            pass
        self.refresh_task_controls(data)
        self.task_manager.sync_motion()

    def refresh_task_controls(self, data=None):
        data = self.snapshot if data is None else data
        count = self.task_manager.total_task_count()
        overview = self.tr_text('task_overview', count=count)
        identity = ('codex', self.prefs.get('pinned'))
        if identity in self.task_manager._universe:
            overview = self.task_manager.label_text(identity, self.language) + ' · ' + overview
        self.tasks_button.setText(overview + ' ▾')
        self.tasks_button.setAccessibleName(overview)
        self.tasks_button.setEnabled(True)
        provider = PROVIDER_NAMES.get(data.get('provider_id') or 'codex', 'Codex')
        provenance = self.tr_text('task_metric_scope', provider=provider,
                                  scope=scope_text(data.get('scope', self.prefs.get('scope')), self.language))
        self.task_provenance.setFullText(provenance)
        self.tasks_button.setToolTip(provenance)
        if self.workbench_window and self.workbench_window.isVisible():
            self.workbench_window.update_tasks()

    def refresh_task_menu(self):
        self.task_menu.clear()
        manager = self.task_manager
        automatic = self.task_menu.addAction(self.tr_text('task_auto'))
        automatic.setCheckable(True)
        automatic.setChecked(not self.prefs.get('pinned'))
        automatic.triggered.connect(lambda checked=False: self.select_hub_task(None))
        self.task_menu.addSeparator()
        for identity in manager.task_identities():
            name = manager.label_text(identity, self.language)
            provider = PROVIDER_NAMES.get(identity[0], identity[0])
            action = self.task_menu.addAction(f'{name} · {provider}')
            action.setCheckable(True)
            action.setChecked(self.prefs.get('pinned') == identity[1])
            action.setEnabled(identity not in manager._ring_staged)
            action.triggered.connect(lambda checked=False, key=identity: self.select_hub_task(key))

    def select_hub_task(self, identity):
        # Menu actions can outlive a task refresh; retired/staged tasks must
        # never change the inspected identity. Stars keep their own details.
        if self.closing:
            return
        if identity is not None:
            if (identity[0] != 'codex' or identity not in self.task_manager._universe
                    or identity in self.task_manager._ring_staged):
                return
            self.prefs.update(pinned=identity[1], scope='conversation')
        else:
            self.prefs['pinned'] = ''
        self.persist()
        self.publish_snapshot(self.provider_poller.apply_settings(dict(self.prefs)))

    def apply_hub_neutralization(self, provider_label, data):
        """Frame automatic aggregate views by scope; preserve actual titles
        when inspecting a conversation or an explicitly selected task."""
        manager = getattr(self, 'task_manager', None)
        if (manager is None or manager.window_count() < 1
                or data.get('scope') in ('task', 'conversation') or self.prefs.get('pinned')):
            return
        scope = (data or {}).get('scope', self.prefs.get('scope'))
        neutral = f'{provider_label} · {scope_text(scope, self.language)}'
        self.title.setFullText(neutral)
        hub_project = (provider_label or '').upper()
        self.project.setText(hub_project)
        self.project.setToolTip(hub_project)

    def analytics_payload(self, data, provider):
        # Current Codex scope/selection/generation are guarded before dispatch.
        return data

    def apply_provider_chrome(self, provider):
        """The sole current source supplies Codex context and quota chrome."""
        for widget in (self.quota_divider, self.context, self.five,
                       self.week, self.status):
            widget.setVisible(True)

    def refresh_cost(self):
        d = self.snapshot
        if not d.get('available'):
            self.cost.setText('—')
            self.compact_cost.setText('—')
            return
        currency = self.currency
        fx = self.fx
        value = convert_usd(d.get('usd', 0), currency, fx['rates'])
        if value is None:
            # Honest fallback: no usable rate for the selected currency.
            currency = 'USD'
            value = d.get('usd', 0)
            rate_line = self.tr_text('fx_unavailable_usd')
        else:
            rate = 1.0 if currency == 'USD' else fx['rates'][currency]
            rate_line = (self.tr_text('one_usd_equals', rate=f'{rate:.4f}', currency=currency) +
                         f" · {fx['date']}\n{fx['source']}")
        partial = bool(d.get('unknown') or d.get('partial') or 'note_cache_write_unavailable' in d.get('notes',[]))
        self.cost.setText('≈ ' + format_cost(value, currency))
        self.compact_cost.setText('≈ ' + format_cost(value, currency))
        self.cost_label.setText(self.tr_text('partial_estimate' if partial else 'estimated_cost')+f' · {currency}')
        self.compact_cost_label.setText(self.cost_label.text())
        tip = (self.tr_text('local_conversations',
                scope=scope_text(d.get('scope'), self.language, recorded=d.get('scope') == 'global'),
                count=d.get('count',1))+'\n'+
               self.tr_text('known_price_usd', usd=f"{d.get('usd',0):,.4f}")+'\n'+
               rate_line+'\n'+
               self.tr_text('not_subscription_bill'))
        if d.get('unknown'):
            names = ', '.join(self.tr_text(name) if name == 'unknown_breakdown' else name for name in d['unknown'])
            tip += '\n'+self.tr_text('unpriced_models', models=names)
        if d.get('partial'):
            tip += '\n'+self.tr_text('partial_records')
        self.cost.setToolTip(tip)
        self.cost_label.setToolTip(tip)
        self.compact_cost.setToolTip(tip)
        self.compact_cost_label.setToolTip(tip)

    def refresh_status(self):
        if self.closing:
            return
        # Both providers share the same visual-clock arming path.
        try:
            self.task_manager.sync_motion()
        except Exception:
            pass
        quota = self.quota
        # Codex quota widgets blank unless the Codex provider is both
        # selected and the quota source: no Codex limits, countdowns or
        # errors may linger from a foreign or late mismatched payload.
        quota_usable = ((self.snapshot.get('provider_id') or 'codex') == 'codex'
                        and (self.quota_provider or 'codex') == 'codex')
        limits = (quota.get('limits') or self.snapshot.get('limits')) if quota_usable else None
        sampled = quota.get('sampled',0) if quota_usable else 0
        age = time.time()-sampled
        stale = age > 10 or bool(quota.get('error')) if quota_usable else True
        for widget,minutes in ((self.five,300),(self.week,10080)):
            widget.reset.hide()
            widget.reset.setText('')
            w = quota_window(limits, minutes)
            if not w:
                widget.update_value(None, tip=self.tr_text('quota_unavailable'))
                widget.reset.setVisible(False)
                continue
            reset = datetime.fromtimestamp(w['reset']).strftime('%m/%d %H:%M') if w.get('reset') is not None else self.tr_text('unknown')
            tip = (self.tr_text('account_quota')+'\n'+self.tr_text('reset_time', reset=reset)+'\n'+
                   self.tr_text('quota_stale' if stale or w['expired'] else 'quota_live'))
            suffix = self.tr_text('left')+(' · '+self.tr_text('stale') if stale or w['expired'] else '')
            widget.update_value(w['remaining'], suffix, tip, stale or w['expired'])
            if w.get('reset') is not None:
                seconds=max(0,int(w['reset']-time.time()))
                days,seconds=divmod(seconds,86400);hours,seconds=divmod(seconds,3600);minutes,seconds=divmod(seconds,60)
                duration=f"{'%dd ' % days if days else ''}{hours:02}:{minutes:02}:{seconds:02}"
                widget.reset.setText(self.tr_text('awaiting_reset') if w['expired'] else self.tr_text('reset_in', duration=duration))
                widget.reset.setVisible(True)
        self.status.setText(self.tr_text('quota_waiting') if stale else self.tr_text('syncing', time=time.strftime('%H:%M:%S')))
        token_age = sample_age(self.snapshot.get('sample'))
        error = quota.get('error') if quota_usable else None
        if error in ('quota_error',):
            error = self.tr_text(error)
        self.status.setToolTip((self.tr_text('token_last_written', seconds=int(token_age))+'\n' if token_age is not None else self.tr_text('no_token_events')+'\n')+
            (error or self.tr_text('no_model_usage')))

    def scope_menu(self):
        menu = QMenu(self)
        selected = {'task':'conversation'}.get(self.prefs.get('scope'), self.prefs.get('scope'))
        for key in ('global','project','conversation'):
            action = menu.addAction(scope_text(key, self.language, recorded=key == 'global'))
            action.setCheckable(True)
            action.setChecked(selected == key)
            action.triggered.connect(lambda checked=False,k=key:self.change_scope(k))
        menu.exec(self.scope_button.mapToGlobal(QPoint(0,self.scope_button.height())))

    def change_scope(self, scope):
        self.prefs['scope'] = scope
        self.persist()
        poller = getattr(self, 'provider_poller', None)
        if poller is not None:
            # Retire outstanding requests for the old scope and repaint
            # from cached state at once instead of waiting a poll tick.
            # The full envelope (active tasks + preference) travels with
            # the result so task surfaces survive scope presentation
            # changes; generation coherence comes from apply_settings.
            snapshot = poller.apply_settings(dict(self.prefs))
            self.publish_snapshot(snapshot)

    def open_settings(self):
        self.show()
        Settings(self).exec()

    def open_workbench(self):
        from workbench import WorkbenchWindow
        from workbench_store import WorkbenchError, WorkbenchStore
        from PySide6.QtWidgets import QMessageBox
        if self.workbench_window is None:
            if not self.live:
                self._workbench_temp = tempfile.TemporaryDirectory(prefix='petoken-workbench-qa-')
            directory = Path(self._workbench_temp.name) if self._workbench_temp else PREF_DIR
            try:
                store = WorkbenchStore(directory / 'workbench.sqlite3')
            except WorkbenchError:
                QMessageBox.warning(self, self.tr_text('workbench_open'), self.tr_text('wb_open_error'))
                return
            try:
                self.workbench_window = WorkbenchWindow(self, store)
            except Exception:
                store.close()
                raise
        self.workbench_window.refresh()
        self.workbench_window.show()
        self.workbench_window.raise_()
        self.workbench_window.activateWindow()

    def open_workbench_tutorial(self):
        if self.closing:
            return
        self.open_workbench()
        if self.workbench_window:
            self.workbench_window.open_tutorial()

    def open_analytics(self):
        self.want_history.set()
        if self.analytics_window is None:
            self.analytics_window=AnalyticsWindow(self)
        data = self.snapshot
        provider = (data.get('provider_id') or 'codex') if isinstance(data, dict) else 'codex'
        self.analytics_window.update_data(self.analytics_payload(data, provider))
        self.analytics_window.show()
        self.analytics_window.raise_()

    def toggle_pet(self):
        if hasattr(self,'pet'):
            if self.pet.isVisible():
                self.pet.hide()
            else:
                self.pet.show()

    def is_pinned(self):
        """Whether the expanded panel stays open independent of hover."""
        return bool(self.prefs.get('panel_pinned', False))

    def update_panel_controls(self):
        self.hide_button.setEnabled(not self.is_pinned())
        tip = self.tr_text('panel_pinned_help' if self.is_pinned() else 'hide_to_tray')
        self.hide_button.setToolTip(tip)
        self.hide_button.setAccessibleName(tip)

    def set_panel_pinned(self, enabled):
        if self.closing:
            return
        self.prefs['panel_pinned'] = bool(enabled)
        self.update_panel_controls()
        self.apply_topmost()
        if enabled:
            self.showNormal()
            self.raise_()
        else:
            self.hide()
        self.persist()

    def toggle_pin(self):
        self.set_panel_pinned(not self.is_pinned())

    def apply_topmost(self):
        """Apply the persistent always-on-top preference to panel and pet."""
        on_top = bool(self.prefs.get('always_on_top', True))
        for window in (self, getattr(self, 'pet', None)):
            target = on_top or (window is self and self.is_pinned())
            if window is None or bool(window.windowFlags() & Qt.WindowStaysOnTopHint) == target:
                continue
            visible, position = window.isVisible(), window.pos()
            window.setWindowFlag(Qt.WindowStaysOnTopHint, target)
            if visible:
                window.show()
            window.move(position)
        self.task_manager.apply_topmost(on_top)


    def set_always_on_top(self, enabled):
        self.prefs['always_on_top'] = bool(enabled)
        self.apply_topmost()
        self.persist()

    def apply_compact(self):
        for widget in (self.project, self.task_provenance, self.model, self.effort):
            widget.setVisible(not self.compact)
        self.body.setVisible(not self.compact)
        self.cost_bar.setVisible(not self.compact)
        self.bottom_bar.setVisible(not self.compact)
        self.compact_box.setVisible(self.compact)
        self.collapse_button.setText('+' if self.compact else '−')
        if self.compact:
            self._dock_compact_widgets()
            self.setFixedSize(HUB_SIZE[0], COMPACT_HEIGHT)
        else:
            self._restore_expanded_widgets()
            self.setFixedSize(*HUB_SIZE)
        QTimer.singleShot(0, lambda: self.anchor_to_pet() if self.isVisible() else None)

    def _dock_compact_widgets(self):
        # The expanded bars lend status/pin/settings to the compact
        # composition; the flag keeps repeated calls order-stable.
        if self._compact_docked:
            return
        self.compact_foot.insertWidget(0, self.status)
        self.compact_foot.addWidget(self.settings_button)
        self._compact_docked = True

    def _restore_expanded_widgets(self):
        if not self._compact_docked:
            return
        self.bottom_layout.insertWidget(0, self.status)
        self.bottom_layout.insertWidget(2, self.settings_button)
        self._compact_docked = False

    def toggle_compact(self):
        self.compact = not self.compact
        self.prefs['compact'] = self.compact
        self.apply_compact()
        self.persist()

    def begin_drag(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start = event.globalPosition().toPoint()-self.pos()

    def drag(self, event):
        if event.buttons() & Qt.LeftButton and hasattr(self,'drag_start'):
            self.move_clamped(event.globalPosition().toPoint()-self.drag_start)

    def end_drag(self, event):
        self.prefs['position'] = [self.x(), self.y()]
        self.persist()

    def move_clamped(self, point):
        screen = QApplication.screenAt(point+QPoint(self.width()//2,30)) or QApplication.primaryScreen()
        r = screen.availableGeometry()
        self.move(max(r.left(),min(point.x(),r.right()-self.width()+1)),
                  max(r.top(),min(point.y(),r.bottom()-self.height()+1)))

    def reset_position(self):
        r = QApplication.primaryScreen().availableGeometry()
        self.move_clamped(QPoint(r.right()-self.width()-24, r.top()+70))

    def persist(self):
        try:
            write_preferences(self.prefs)
            return True
        except OSError:
            self.status.setText(self.tr_text('settings_save_failed'))
            return False

    def handle_escape(self):
        if self.task_manager.expanded_identity is not None:
            self.task_manager.collapse_detail()
        else:
            self.hide_to_tray()

    def hide_to_tray(self):
        if self.is_pinned() and not self.closing:
            return
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.hide()
        else:
            self.showMinimized()
        if self.task_manager.legacy_exterior_motion:
            self.task_manager.set_visible(False)
        else:
            self.task_manager._stack_halo(force=True)

    def toggle_visible(self):
        if self.isVisible():
            self.hide_to_tray()
        else:
            self.showNormal()
            self.raise_()
            if self.task_manager.legacy_exterior_motion:
                self.task_manager.set_visible(True)
            else:
                self.task_manager._stack_halo(force=True)

    def closeEvent(self, event):
        if self.closing:
            event.accept()
        else:
            event.ignore()
            self.hide_to_tray()

    def shutdown(self):
        if self.workbench_window and not self.workbench_window.shutdown():
            return False
        self.closing = True
        self.stop.set()
        self.active.stop.set()
        self.activity.close()
        self.task_manager.shutdown()
        if getattr(self, 'provider_poller', None) is not None:
            self.provider_poller.close()
        if hasattr(self,'pet'):
            self.prefs['pet_position']=[self.pet.x(),self.pet.y()]
            self.pet.close()
        if self.rates.thread.is_alive():
            self.rates.close()
        self.prefs['position'] = [self.x(),self.y()]
        self.persist()
        self.tray.hide()
        if self._workbench_temp:
            self._workbench_temp.cleanup()
            self._workbench_temp = None
        QApplication.instance().quit()
        return True


def main():
    if '--preview-workbench' in sys.argv[1:]:
        if __name__ == '__main__':
            sys.modules['widget'] = sys.modules[__name__]
        from tools.preview_workbench import main as preview_main
        return preview_main([argument for argument in sys.argv[1:]
                             if argument != '--preview-workbench'])
    if any(argument in ('--preview-v1-3', '--preview-v1-4') for argument in sys.argv[1:]):
        # Frozen/script entry is __main__; keep the preview on this module's
        # globals so its temporary preference directory isolates the real UI.
        if __name__ == '__main__':
            sys.modules['widget'] = sys.modules[__name__]
        from tools.preview_v1_3 import main as preview_main
        return preview_main([argument for argument in sys.argv[1:]
                             if argument not in ('--preview-v1-3', '--preview-v1-4')])
    parser = argparse.ArgumentParser()
    parser.add_argument('--smoke', type=Path, help='Save a local screenshot after five seconds and exit')
    args = parser.parse_args()
    app = QApplication(sys.argv)
    app.setApplicationName('petoken')
    app.setApplicationVersion(APP_VERSION)
    app.setQuitOnLastWindowClosed(False)
    PREF_DIR.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(PREF_DIR/'widget.lock'))
    if not lock.tryLock(100):
        return 0
    panel = Panel()
    from pet import DesktopPet
    panel.pet=DesktopPet(panel)
    panel.restore_companion()
    if not args.smoke and panel.prefs.get('workbench_tutorial_seen') is not True:
        QTimer.singleShot(0, panel, panel.open_workbench_tutorial)
    if args.smoke:
        panel.show()
        panel.open_analytics()
        panel.pet.activity_timer.stop()
    if args.smoke:
        def finish():
            args.smoke.parent.mkdir(parents=True,exist_ok=True)
            panel.grab().save(str(args.smoke))
            panel.pet.grab().save(str(args.smoke.with_name(args.smoke.stem+'-pet.png')))
            panel.analytics_window.grab().save(str(args.smoke.with_name(args.smoke.stem+'-analytics.png')))
            settings = Settings(panel)
            settings.show()
            app.processEvents()
            settings.grab().save(str(args.smoke.with_name(args.smoke.stem+'-settings.png')))
            settings.close()
            report = dict(visible=panel.isVisible(), task=panel.snapshot.get('title'),
                          has_usage=panel.snapshot.get('available'), mode=panel.snapshot.get('mode'),
                          language=panel.language,
                          app_mode=panel.app_mode.mode, codex_activity=panel.codex_activity,
                          scope_identity=panel.snapshot.get('scope_identity'),
                          working_context={k:(v.get('total_tokens') if k=='tokens' else v)
                              for k,v in (panel.snapshot.get('working_context') or {}).items()
                              if k in ('thread','title','project','project_source','tokens','selection')},
                          quota_live=bool(panel.quota.get('sampled')),
                          activity_status=activity_diagnostics(panel.activity.status),
                          keyboard_hook_error=panel.activity.keyboard.error,
                          width=panel.width(),height=panel.height())
            args.smoke.with_suffix('.json').write_text(json.dumps(report, ensure_ascii=False,indent=2),encoding='utf-8')
            panel.shutdown()
        QTimer.singleShot(6000, finish)
    result = app.exec()
    lock.unlock()
    return result


if __name__ == '__main__':
    raise SystemExit(main())
