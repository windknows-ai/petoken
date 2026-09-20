"""petoken — a small, local Windows desktop companion."""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal, QObject, QPoint, QRect, QRectF, QSize, QLockFile
from PySide6.QtGui import QColor, QCursor, QFont, QFontMetrics, QIcon, QPainter, QPainterPath, QPen, QLinearGradient, QPixmap, QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QWidget, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QFrame, QProgressBar, QMenu, QSystemTrayIcon, QDialog,
    QFormLayout, QComboBox, QCheckBox, QSlider, QDialogButtonBox, QScrollArea)

from desktop import ActiveTask, RateLimits, fetch_fx
from usage import CodexStore, quota_window, sample_age
from analytics_view import AnalyticsWindow, help_text
import pet_assets as assets
import pet_geometry as pet_geometry
from app_config import APP_VERSION, load_preferences, save_preferences
from app_mode import AppModeState
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
QWidget#surface {{ background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 {theme.SURFACE_TOP},stop:1 {theme.SURFACE_BOTTOM}); border:1px solid {theme.BORDER}; border-radius:{theme.RADIUS_SURFACE}px; }}
QLabel {{ background:transparent; border:none; }}
QLabel#muted {{ color:{theme.MUTED}; font-size:11px; }}
QLabel#brand {{ color:{theme.INK}; font-size:14px; font-weight:600; letter-spacing:2px; }}
QLabel#number {{ font-family:{theme.FONT_NUM}; font-size:30px; font-weight:600; }}
QLabel#smallnumber {{ font-family:{theme.FONT_NUM}; font-size:16px; }}
QLabel#cost {{ color:{theme.ICE}; font-family:{theme.FONT_NUM}; font-size:22px; font-weight:600; }}
QLabel#badge {{ color:{theme.VIOLET}; background:{theme.BADGE_BG}; border:1px solid {theme.BORDER_SOFT}; border-radius:{theme.RADIUS_BADGE}px; padding:4px 10px; font-size:11px; }}
QFrame#card {{ background:{theme.CARD}; border:1px solid {theme.BORDER_SOFT}; border-radius:{theme.RADIUS_CARD}px; }}
QPushButton {{ background:transparent; border:1px solid transparent; border-radius:{theme.RADIUS_BUTTON}px; padding:5px 8px; min-height:24px; }}
QPushButton:hover {{ background:{theme.HOVER_BG}; border-color:{theme.HOVER_BORDER}; }}
QPushButton:focus {{ border-color:{theme.ICE}; }}
QPushButton:checked {{ background:{theme.CHECKED_BG}; color:{theme.ICE}; border-color:#515777; }}
QFrame#divider {{ background:{theme.DIVIDER}; max-height:1px; border:0; }}
QProgressBar {{ background:{theme.TRACK}; border:0; border-radius:{theme.RADIUS_BAR}px; min-height:5px; max-height:5px; }}
QProgressBar::chunk {{ background:{theme.ICE}; border-radius:{theme.RADIUS_BAR}px; }}
QMenu {{ background:{theme.MENU_BG}; border:1px solid #515777; padding:6px; }}
QMenu::item {{ padding:9px 18px; border-radius:8px; }}
QMenu::item:selected {{ background:{theme.MENU_SELECTED}; }}
QToolTip {{ background:{theme.TOOLTIP_BG}; color:{theme.INK}; border:1px solid {theme.TOOLTIP_BORDER}; padding:7px; }}
QDialog {{ background:{theme.BG}; }}
QComboBox {{ background:{theme.CONTROL_BG}; border:1px solid {theme.BORDER_CONTROL}; border-radius:8px; padding:6px; min-height:24px; }}
QComboBox:focus {{ border-color:{theme.ICE}; }}
QComboBox QAbstractItemView {{ background:{theme.CONTROL_BG}; selection-background-color:#4B527A; }}
QScrollArea {{ border:0; background:transparent; }}
QCheckBox {{ spacing:8px; }}
QCheckBox::indicator {{ width:16px; height:16px; border:1px solid {theme.BORDER_CONTROL}; border-radius:5px; background:{theme.CONTROL_BG}; }}
QCheckBox::indicator:checked {{ background:{theme.ICE}; border-color:{theme.ICE}; }}
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
# Intentional compact footprint: identity + task + one metrics row + one
# control strip. Tuned from real renders, not from the expanded stack.
COMPACT_HEIGHT = 316



def valid_panel_size(value):
    """Clamp a saved expanded-panel size into supported bounds, or None when
    the saved value is malformed. Never raises on user-edited settings."""
    try:
        width, height = int(value[0]), int(value[1])
    except (TypeError, ValueError, IndexError, KeyError):
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
        self.value.setText('—' if value is None else f'{value:.0f}% {suffix}')
        self.bar.setValue(0 if value is None else round(value*10))
        self.bar.setEnabled(not stale)
        self.value.setStyleSheet(f'color:{MUTED if stale else INK};')
        self.setToolTip(tip)


class Bridge(QObject):
    data = Signal(dict)
    limits = Signal(dict)
    fx = Signal(dict)


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
        self.language.setCurrentIndex(self.language.findData(DEFAULT_LANGUAGE))
        self.token_format.setCurrentIndex(
            self.token_format.findData(DEFAULT_TOKEN_NUMBER_FORMAT))
        self.currency.setCurrentIndex(self.currency.findData(DEFAULT_CURRENCY))
        self.topmost.setChecked(True)
        self.pet_scale.setValue(pet_geometry.PET_SCALE_DEFAULT)
        self.apply_language()

    def save(self):
        panel = self.parentWidget()
        prefs = dict(panel.prefs)
        prefs.update(pinned=self.task.currentData(), scope=self.scope.currentData(),
                     language=normalize_language(self.language.currentData()),
                     token_number_format=self.token_format.currentData(),
                     currency=self.currency.currentData(),
                     always_on_top=self.topmost.isChecked(),
                     pet_scale_percent=int(self.pet_scale.value()))
        # Legacy `manual_fx` / `prices` keys stay untouched in the file for
        # backward-compatible loading, but no longer drive pricing or FX.
        try:
            write_preferences(prefs)
        except OSError:
            self.error.setText(self.tr_text('settings_save_error'))
            return
        panel.prefs = prefs
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
        self.prefs = read_preferences()
        self.app_mode = AppModeState()
        self.codex_activity = dict(active=False, valid=False, reason='starting')
        self.snapshot = {}
        self.analytics_window = None
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
        self.setWindowTitle('petoken')
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setMinimumSize(PANEL_MIN[0], 250)
        self.setMaximumSize(600, 640)
        self.setStyleSheet(STYLE)
        # The character remains in its own anchored window; this is its satellite.
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        self.surface = QWidget()
        self.surface.setObjectName('surface')
        outer.addWidget(self.surface)
        layout = QVBoxLayout(self.surface)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(10)
        self.header = QWidget()
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
        controls = QVBoxLayout()
        controls.setSpacing(0)
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
        model_row = QHBoxLayout()
        model_row.setSpacing(8)
        self.model = label('—')
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
        self.body.setStyleSheet(f'background:{BG};')
        body = QVBoxLayout(self.body)
        body.setContentsMargins(0,0,0,0)
        body.setSpacing(10)
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
        details_row.addStretch()
        self.details_button = button('', '', self.open_analytics)
        details_row.addWidget(self.details_button)
        body.addLayout(details_row)
        body.addWidget(divider())
        self.context = Meter('', VIOLET)
        self.five = Meter('', ICE)
        self.week = Meter('', VIOLET)
        body.addWidget(self.context)
        body.addWidget(self.five)
        body.addWidget(self.week)
        # Pin content to the top so tall windows keep one compact visual
        # group instead of spreading sections apart.
        body.addStretch(1)
        self.body_scroll = QScrollArea()
        self.body_scroll.viewport().setStyleSheet(f'background:{BG};')
        self.body_scroll.setWidgetResizable(True)
        self.body_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.body_scroll.setWidget(self.body)
        layout.addWidget(self.body_scroll,1)
        cost_row = QHBoxLayout()
        self.cost_row_layout = cost_row
        cost_left = QVBoxLayout()
        cost_left.setSpacing(4)
        self.cost_label = label('', 'muted')
        self.cost = label('—', 'cost')
        cost_left.addWidget(self.cost_label)
        cost_left.addWidget(self.cost)
        cost_row.addLayout(cost_left)
        cost_row.addStretch()
        self.pin = button('◇', '', self.toggle_pin)
        self.pin.setCheckable(True)
        self.pin.setChecked(bool(self.prefs.get('panel_pinned', False)))
        self.pin.setFixedSize(34,34)
        cost_row.addWidget(self.pin)
        self.cost_bar = QWidget()
        self.cost_bar.setLayout(cost_row)
        layout.addWidget(self.cost_bar)
        bottom = QHBoxLayout()
        self.bottom_layout = bottom
        self.status = label('', 'muted')
        bottom.addWidget(self.status)
        bottom.addStretch()
        self.settings_button = button('⚙', '', self.open_settings)
        bottom.addWidget(self.settings_button)
        self.size_grip = label('⋰', 'muted')
        self.size_grip.setCursor(Qt.SizeFDiagCursor)
        bottom.addWidget(self.size_grip)
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
        QShortcut(QKeySequence('Escape'), self, activated=self.hide_to_tray)
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
        self.size_grip.mousePressEvent = self.begin_resize
        self.size_grip.mouseMoveEvent = self.do_resize
        self.size_grip.mouseReleaseEvent = self.end_resize
        self.size_timer = QTimer(self)
        self.size_timer.setSingleShot(True)
        self.size_timer.timeout.connect(self.persist)
        self._edge_resize = None
        self.compact = bool(self.prefs.get('compact', False))
        self.apply_language()
        self.resize(*(valid_panel_size(self.prefs.get('panel_size')) or PANEL_DEFAULT))
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
        self.context.set_title(t('context_used'))
        self.five.set_title(t('five_hour_limit'))
        self.week.set_title(t('weekly_limit'))
        self.cost_label.setText(t('estimated_cost')+f" · {normalize_currency(self.prefs.get('currency'))}")
        self.compact_cost_label.setText(self.cost_label.text())
        self.update_pin_button()
        self.status.setText(t('checking_wait'))
        self.settings_button.setToolTip(t('settings_help'))
        self.settings_button.setAccessibleName(t('settings_help'))
        self.tray.setToolTip(t('tray_tip'))
        for key, action in self.tray_actions.items():
            action.setText(t(key))
        if self.analytics_window:
            self.analytics_window.apply_language()
        if hasattr(self, 'pet'):
            self.pet.apply_language()
        if self.snapshot:
            self.render(self.snapshot)

    def read_loop(self):
        store = None
        while not self.stop.is_set():
            start = time.monotonic()
            try:
                prefs = dict(self.prefs)
                if store is None or self.reset_store.is_set():
                    self.reset_store.clear()
                    store = CodexStore()
                detection_valid = time.time()-self.active.seen < 5
                active = self.active.title if detection_valid else ''
                self.bridge.data.emit(store.read(active, prefs.get('pinned',''), prefs.get('scope','conversation'),
                                                 self.want_history.is_set(), detection_valid))
            except Exception:
                self.bridge.data.emit(dict(status='status_read_failed', rows=[]))
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
        self.refresh_status()

    def render(self, data):
        self.snapshot = data
        self.codex_activity = data.get('codex_activity') or dict(active=False,valid=False,reason='missing')
        self.app_mode.update(self.codex_activity.get('active',False), self.codex_activity.get('valid',False))
        if hasattr(self,'pet'):
            self.pet.update_data(data)
        if data.get('status') or not data.get('available'):
            status = self.tr_text(data.get('status') or 'no_reliable_record')
            self.connection.setText(status)
            self.connection.setToolTip(status)
            self.title.setFullText(self.tr_text('waiting_available_task'))
            self.project.setText('CODEX')
            for w in (self.total,self.model,self.effort,self.cost,self.compact_total,
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
            return
        modes = {'follow':'mode_follow', 'fixed':'mode_fixed', 'recent':'mode_recent', 'working':'mode_working'}
        self.connection.setText(self.tr_text(modes.get(data.get('mode'),'waiting_data')))
        self.connection.setToolTip(self.tr_text('task_detection_tip'))
        self.project.setText(self.display_text(data.get('project'), 'waiting_codex').upper())
        self.title.setFullText(self.display_text(data.get('title'), 'unnamed_task'))
        self.model.setText(data.get('model') or self.tr_text('model_not_recorded'))
        self.model.setToolTip(self.tr_text('model_tip'))
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
        working = bool(activity.get('valid') and activity.get('active'))
        self.status_dot.setVisible(True)
        self.status_text.setVisible(True)
        self.status_dot.setStyleSheet(f'color:{ICE if working else MUTED};')
        self.status_text.setText(self.tr_text('working' if working else
            ('idle' if activity.get('valid') else 'unknown')))
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
            self.analytics_window.update_data(data)

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
        quota = self.quota
        limits = quota.get('limits') or self.snapshot.get('limits')
        sampled = quota.get('sampled',0)
        age = time.time()-sampled
        stale = age > 10 or bool(quota.get('error'))
        for widget,minutes in ((self.five,300),(self.week,10080)):
            w = quota_window(limits, minutes)
            if not w:
                widget.update_value(None, tip=self.tr_text('quota_unavailable'))
                widget.reset.setVisible(False)
                continue
            reset = datetime.fromtimestamp(w['reset']).strftime('%m/%d %H:%M') if w.get('reset') else self.tr_text('unknown')
            tip = (self.tr_text('account_quota')+'\n'+self.tr_text('reset_time', reset=reset)+'\n'+
                   self.tr_text('quota_stale' if stale or w['expired'] else 'quota_live'))
            suffix = self.tr_text('left')+(' · '+self.tr_text('stale') if stale or w['expired'] else '')
            widget.update_value(w['remaining'], suffix, tip, stale or w['expired'])
            if w.get('reset'):
                seconds=max(0,int(w['reset']-time.time()))
                days,seconds=divmod(seconds,86400);hours,seconds=divmod(seconds,3600);minutes,seconds=divmod(seconds,60)
                duration=f"{'%dd ' % days if days else ''}{hours:02}:{minutes:02}:{seconds:02}"
                widget.reset.setText(self.tr_text('awaiting_reset') if w['expired'] else self.tr_text('reset_in', duration=duration))
                widget.reset.setVisible(True)
        self.status.setText(self.tr_text('quota_waiting') if stale else self.tr_text('syncing', time=time.strftime('%H:%M:%S')))
        token_age = sample_age(self.snapshot.get('sample'))
        error = quota.get('error')
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

    def open_settings(self):
        self.show()
        Settings(self).exec()

    def open_analytics(self):
        self.want_history.set()
        if self.analytics_window is None:
            self.analytics_window=AnalyticsWindow(self)
        self.analytics_window.update_data(self.snapshot)
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

    def update_pin_button(self):
        pinned = self.is_pinned()
        self.pin.setChecked(pinned)
        self.pin.setText('◆' if pinned else '◇')
        tip = self.tr_text('panel_unpin' if pinned else 'panel_pin')
        self.pin.setToolTip(tip)
        self.pin.setAccessibleName(tip)

    def toggle_pin(self):
        self.prefs['panel_pinned'] = not self.is_pinned()
        self.update_pin_button()
        self.persist()

    def apply_topmost(self):
        """Apply the persistent always-on-top preference to panel and pet."""
        on_top = bool(self.prefs.get('always_on_top', True))
        for window in (self, getattr(self, 'pet', None)):
            if window is None or bool(window.windowFlags() & Qt.WindowStaysOnTopHint) == on_top:
                continue
            visible, position = window.isVisible(), window.pos()
            window.setWindowFlag(Qt.WindowStaysOnTopHint, on_top)
            if visible:
                window.show()
            window.move(position)


    def set_always_on_top(self, enabled):
        self.prefs['always_on_top'] = bool(enabled)
        self.apply_topmost()
        self.persist()

    def apply_compact(self):
        self.body.setVisible(not self.compact)
        self.body_scroll.setVisible(not self.compact)
        self.size_grip.setVisible(not self.compact)
        self.cost_bar.setVisible(not self.compact)
        self.bottom_bar.setVisible(not self.compact)
        self.compact_box.setVisible(self.compact)
        self.collapse_button.setText('+' if self.compact else '−')
        if self.compact:
            self._dock_compact_widgets()
            self.setFixedHeight(COMPACT_HEIGHT)
        else:
            self._restore_expanded_widgets()
            self.setMinimumSize(*PANEL_MIN)
            self.setMaximumSize(*PANEL_MAX)
            self.resize(*(valid_panel_size(self.prefs.get('panel_size')) or PANEL_DEFAULT))
        QTimer.singleShot(0, lambda: self.anchor_to_pet() if self.isVisible() else None)

    def _dock_compact_widgets(self):
        # The expanded bars lend status/pin/settings to the compact
        # composition; the flag keeps repeated calls order-stable.
        if self._compact_docked:
            return
        self.compact_foot.insertWidget(0, self.status)
        self.compact_foot.addWidget(self.pin)
        self.compact_foot.addWidget(self.settings_button)
        self._compact_docked = True

    def _restore_expanded_widgets(self):
        if not self._compact_docked:
            return
        self.cost_row_layout.addWidget(self.pin)
        self.bottom_layout.insertWidget(0, self.status)
        self.bottom_layout.insertWidget(2, self.settings_button)
        self._compact_docked = False

    def toggle_compact(self):
        self.compact = not self.compact
        self.prefs['compact'] = self.compact
        self.apply_compact()
        self.persist()
        pet = getattr(self, 'pet', None)
        if pet is not None:
            # The click counts as fresh presence: an expand-then-anchor jump
            # must not immediately read as a cursor leave (auto-hide grace).
            pet.left_since = None

    def begin_drag(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start = event.globalPosition().toPoint()-self.pos()

    def drag(self, event):
        if event.buttons() & Qt.LeftButton and hasattr(self,'drag_start'):
            self.move_clamped(event.globalPosition().toPoint()-self.drag_start)

    def end_drag(self, event):
        self.prefs['position'] = [self.x(), self.y()]
        self.persist()

    def begin_resize(self, event):
        if event.button() == Qt.LeftButton:
            self.resize_start = (event.globalPosition().toPoint(), self.size())

    def do_resize(self, event):
        if event.buttons() & Qt.LeftButton and hasattr(self, 'resize_start'):
            origin, size = self.resize_start
            delta = event.globalPosition().toPoint() - origin
            self.resize(max(PANEL_MIN[0], min(size.width() + delta.x(), PANEL_MAX[0])),
                        max(PANEL_MIN[1], min(size.height() + delta.y(), PANEL_MAX[1])))
            self.prefs['panel_size'] = [self.width(), self.height()]
            self.size_timer.start(600)

    def end_resize(self, event):
        if hasattr(self, 'resize_start'):
            del self.resize_start
        self.persist()

    RESIZE_MARGIN = 8

    def _resize_hit(self, pos):
        """Which window borders the point grabs: (dx, dy) in {-1, 0, 1}."""
        w, h, m = self.width(), self.height(), self.RESIZE_MARGIN
        dx = -1 if pos.x() < m else (1 if pos.x() > w - m else 0)
        dy = -1 if pos.y() < m else (1 if pos.y() > h - m else 0)
        return dx, dy

    @staticmethod
    def _resize_cursor(dx, dy):
        if dx != 0 and dy != 0:
            return Qt.SizeFDiagCursor if dx == dy else Qt.SizeBDiagCursor
        if dx != 0:
            return Qt.SizeHorCursor
        if dy != 0:
            return Qt.SizeVerCursor
        return None

    def mousePressEvent(self, event):
        hit = (0, 0) if self.compact else self._resize_hit(event.position().toPoint())
        if event.button() == Qt.LeftButton and hit != (0, 0):
            self._edge_resize = (event.globalPosition().toPoint(), self.geometry(), hit)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._edge_resize is not None and event.buttons() & Qt.LeftButton:
            origin, geom, (dx, dy) = self._edge_resize
            delta = event.globalPosition().toPoint() - origin
            ww, hh = geom.width(), geom.height()
            if dx == 1:
                ww += delta.x()
            elif dx == -1:
                ww -= delta.x()
            if dy == 1:
                hh += delta.y()
            elif dy == -1:
                hh -= delta.y()
            new_w = max(PANEL_MIN[0], min(ww, PANEL_MAX[0]))
            new_h = max(PANEL_MIN[1], min(hh, PANEL_MAX[1]))
            x, y = geom.x(), geom.y()
            if dx == -1:
                x = geom.right() - new_w + 1
            if dy == -1:
                y = geom.bottom() - new_h + 1
            self.setGeometry(x, y, new_w, new_h)
            self.prefs['panel_size'] = [new_w, new_h]
            self.size_timer.start(600)
            event.accept()
        elif not self.compact and not (event.buttons() & Qt.LeftButton):
            cursor = self._resize_cursor(*self._resize_hit(event.position().toPoint()))
            self.setCursor(QCursor(cursor)) if cursor is not None else self.unsetCursor()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._edge_resize is not None and event.button() == Qt.LeftButton:
            self._edge_resize = None
            self.persist()
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def leaveEvent(self, event):
        if self._edge_resize is None:
            self.unsetCursor()
        super().leaveEvent(event)

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
        except OSError:
            self.status.setText(self.tr_text('settings_save_failed'))

    def hide_to_tray(self):
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.hide()
        else:
            self.showMinimized()

    def toggle_visible(self):
        if self.isVisible():
            self.hide_to_tray()
        else:
            self.showNormal()
            self.raise_()

    def closeEvent(self, event):
        if self.closing:
            event.accept()
        else:
            event.ignore()
            self.hide_to_tray()

    def shutdown(self):
        self.closing = True
        self.stop.set()
        self.active.stop.set()
        self.activity.close()
        if hasattr(self,'pet'):
            self.prefs['pet_position']=[self.pet.x(),self.pet.y()]
            self.pet.close()
        if self.rates.thread.is_alive():
            self.rates.close()
        self.prefs['position'] = [self.x(),self.y()]
        self.persist()
        self.tray.hide()
        QApplication.instance().quit()


def main():
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
