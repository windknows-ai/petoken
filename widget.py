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

from PySide6.QtCore import Qt, QTimer, Signal, QObject, QPoint, QRectF, QLockFile
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QLinearGradient, QPixmap, QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QWidget, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QGridLayout, QFrame, QProgressBar, QMenu, QSystemTrayIcon, QDialog,
    QFormLayout, QComboBox, QDoubleSpinBox, QCheckBox, QDialogButtonBox, QScrollArea)

from desktop import ActiveTask, RateLimits, fetch_fx
from usage import CodexStore, PRICES, quota_window, sample_age
from analytics_view import AnalyticsWindow, HELP

INK = '#EEF2FF'
MUTED = '#A7AEC8'
ICE = '#91E4F2'
VIOLET = '#B9A7F8'
BG = '#171B32'
PREF_DIR = Path(os.environ.get('LOCALAPPDATA', str(Path.home()/'.local/share')))/'CodexWisp'

STYLE = f'''
QWidget {{ color:{INK}; font-family:"Segoe UI","Microsoft YaHei UI"; font-size:12px; }}
QWidget#surface {{ background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #242641,stop:.5 {BG},stop:1 #22243D); border:1px solid #515473; border-radius:23px; }}
QLabel {{ background:transparent; border:none; }}
QLabel#muted {{ color:{MUTED}; font-size:11px; }}
QLabel#brand {{ color:{INK}; font-size:15px; font-weight:600; letter-spacing:2px; }}
QLabel#number {{ font-family:"Cascadia Mono","Consolas"; font-size:32px; font-weight:600; }}
QLabel#smallnumber {{ font-family:"Cascadia Mono","Consolas"; font-size:17px; }}
QLabel#cost {{ color:{ICE}; font-family:"Cascadia Mono","Consolas"; font-size:26px; font-weight:600; }}
QLabel#badge {{ color:{VIOLET}; background:#34304F; border:1px solid #575076; border-radius:8px; padding:4px 8px; font-size:11px; }}
QPushButton {{ background:transparent; border:1px solid transparent; border-radius:8px; padding:5px 8px; min-height:22px; }}
QPushButton:hover {{ background:#383B57; border-color:#555A7B; }}
QPushButton:focus {{ border-color:{ICE}; }}
QPushButton:checked {{ background:#34344F; color:{ICE}; border-color:#515777; }}
QFrame#divider {{ background:#3C405B; max-height:1px; border:0; }}
QProgressBar {{ background:#33374F; border:0; border-radius:3px; min-height:5px; max-height:5px; }}
QProgressBar::chunk {{ background:{ICE}; border-radius:3px; }}
QMenu {{ background:#232740; border:1px solid #515777; padding:6px; }}
QMenu::item {{ padding:9px 18px; border-radius:6px; }}
QMenu::item:selected {{ background:#3D4263; }}
QToolTip {{ background:#252B46; color:{INK}; border:1px solid #626A8C; padding:7px; }}
QDialog {{ background:{BG}; }}
QComboBox,QDoubleSpinBox {{ background:#282D48; border:1px solid #555C80; border-radius:6px; padding:6px; min-height:24px; }}
QComboBox:focus,QDoubleSpinBox:focus {{ border-color:{ICE}; }}
QComboBox QAbstractItemView {{ background:#282D48; selection-background-color:#4B527A; }}
QScrollArea {{ border:0; background:transparent; }}
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


def compact_number(n):
    if n is None:
        return 'N/A'
    if n >= 1_000_000:
        return f'{n/1_000_000:.2f}M'
    if n >= 10_000:
        return f'{n/1000:.1f}K'
    return f'{n:,}'


def read_preferences():
    try:
        data = json.loads((PREF_DIR/'settings.json').read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def write_preferences(data):
    PREF_DIR.mkdir(parents=True, exist_ok=True)
    temp = PREF_DIR/'settings.tmp'
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(PREF_DIR/'settings.json')


class Spirit(QWidget):
    """Original vector ice spirit; all artwork ships as editable source."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(54, 60)
        self.setAccessibleName('冰晶小精灵')

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


class Meter(QWidget):
    def __init__(self, title, color):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        row = QHBoxLayout()
        row.addWidget(label(title))
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
        self.setWindowTitle('petoken · 设置')
        self.setMinimumWidth(430)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.task = QComboBox()
        self.task.addItem('自动跟随 Codex 当前任务', '')
        for row in panel.snapshot.get('rows', []):
            self.task.addItem(row.get('name') or row.get('title','').split('\n')[0][:60] or '未命名任务', row['id'])
        self.task.setCurrentIndex(max(0, self.task.findData(panel.prefs.get('pinned', ''))))
        self.task.setMaximumWidth(325)
        form.addRow('跟随 / 固定任务', self.task)
        self.scope = QComboBox()
        self.scope.addItem('当前任务', 'task')
        self.scope.addItem('整个项目（本地记录）', 'project')
        self.scope.setCurrentIndex(1 if panel.prefs.get('scope') == 'project' else 0)
        form.addRow('Tokens 与费用范围', self.scope)
        self.fx = QDoubleSpinBox()
        self.fx.setRange(.01, 9.9999)
        self.fx.setDecimals(4)
        self.fx.setValue(panel.fx_rate()['rate'])
        self.manual = QCheckBox('手动汇率（取消后使用加拿大央行）')
        self.manual.setChecked(bool(panel.prefs.get('manual_fx')))
        self.fx.setEnabled(self.manual.isChecked())
        self.manual.toggled.connect(self.fx.setEnabled)
        form.addRow('1 USD = CAD', self.fx)
        form.addRow('', self.manual)
        self.price_model = panel.snapshot.get('model')
        self.custom = QCheckBox('覆盖当前模型的 Standard 单价')
        self.custom.setChecked(self.price_model in panel.prefs.get('prices', {}))
        form.addRow(self.price_model or '模型尚未记录', self.custom)
        self.price_fields = []
        rates = panel.prefs.get('prices', {}).get(self.price_model, PRICES.get(self.price_model, (0,0,0,0)))
        for caption, value in zip(('普通输入', '缓存输入', '缓存写入', '输出（含 reasoning）'), rates):
            spin = QDoubleSpinBox()
            spin.setRange(0, 10000)
            spin.setDecimals(4)
            spin.setValue(value)
            spin.setEnabled(self.custom.isChecked())
            self.custom.toggled.connect(spin.setEnabled)
            self.price_fields.append(spin)
            form.addRow(f'{caption} · USD / 1M', spin)
        self.custom.setEnabled(bool(self.price_model))
        layout.addLayout(form)
        note = label('费用是 API 等价估算，不是订阅账单。\n按已记录的模型、缓存、快速模式与长上下文计算；不含工具费用。\n未知单价显示部分估算。fork 去除继承历史，保留新增用量。\n模型 / reasoning 是最近一次已发送配置；发送前的菜单改动可能尚未记录。\n每秒检查；Tokens 在 Codex 写入新事件后更新。\nContext = 最近记录的上下文 tokens ÷ 可用窗口；非累计总量。\n桌宠优先级：用量 > 麦克风 > 媒体播放 > 打字 > 待机。\n只读取活动状态，不保存按键、录音或媒体标题。', 'muted')
        note.setWordWrap(True)
        layout.addWidget(note)
        self.error = label('', 'muted')
        layout.addWidget(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText('保存')
        buttons.button(QDialogButtonBox.Cancel).setText('取消')
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def save(self):
        panel = self.parentWidget()
        prefs = dict(panel.prefs)
        prefs.update(pinned=self.task.currentData(), scope=self.scope.currentData(),
                     manual_fx=self.fx.value() if self.manual.isChecked() else None)
        prices = dict(prefs.get('prices', {}))
        if self.custom.isChecked() and self.price_model:
            prices[self.price_model] = [w.value() for w in self.price_fields]
        else:
            prices.pop(self.price_model, None)
        prefs['prices'] = prices
        try:
            write_preferences(prefs)
        except OSError:
            self.error.setText('无法保存设置，请检查用户文件夹的写入权限。')
            return
        panel.prefs = prefs
        panel.reset_store.set()
        self.accept()


class Panel(QWidget):
    def __init__(self, live=True):
        super().__init__()
        self.prefs = read_preferences()
        self.snapshot = {}
        self.analytics_window = None
        self.want_history = threading.Event()
        self.quota = {}
        self.fx_data = self.prefs.get('fx_cache') or dict(rate=1.3917, date='2026-09-15', source='Bank of Canada · bundled')
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
        self.setFixedWidth(360)
        self.setStyleSheet(STYLE)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 6)
        self.surface = QWidget()
        self.surface.setObjectName('surface')
        outer.addWidget(self.surface)
        layout = QVBoxLayout(self.surface)
        layout.setContentsMargins(20, 14, 20, 16)
        layout.setSpacing(14)
        self.header = QWidget()
        self.header.setCursor(Qt.SizeAllCursor)
        head = QHBoxLayout(self.header)
        head.setContentsMargins(0,0,0,0)
        head.setSpacing(9)
        self.spirit = Spirit()
        head.addWidget(self.spirit)
        brand = QVBoxLayout()
        brand.setSpacing(3)
        brand.addWidget(label('PETOKEN', 'brand'))
        self.connection = label('正在连接…', 'muted')
        brand.addWidget(self.connection)
        head.addLayout(brand)
        head.addStretch()
        controls = QVBoxLayout()
        controls.setSpacing(0)
        self.collapse_button = button('−', '收起 / 展开', self.toggle_compact)
        self.collapse_button.setFixedSize(30, 28)
        controls.addWidget(self.collapse_button)
        hide = button('×', '隐藏到系统托盘', self.hide_to_tray)
        hide.setFixedSize(30, 28)
        controls.addWidget(hide)
        head.addLayout(controls)
        layout.addWidget(self.header)
        self.project = label('等待 Codex', 'muted')
        layout.addWidget(self.project)
        self.title = ElidedLabel('打开 Codex 中的任务')
        self.title.setStyleSheet('font-size:17px; font-weight:600;')
        layout.addWidget(self.title)
        self.body = QWidget()
        self.body.setStyleSheet(f'background:{BG};')
        body = QVBoxLayout(self.body)
        body.setContentsMargins(0,0,0,0)
        body.setSpacing(18)
        model_row = QHBoxLayout()
        self.model = label('—')
        self.model.setStyleSheet(f'color:{ICE}; font-size:13px;')
        model_row.addWidget(self.model)
        model_row.addStretch()
        self.effort = label('—', 'badge')
        model_row.addWidget(self.effort)
        body.addLayout(model_row)
        token_box = QVBoxLayout()
        token_box.setSpacing(6)
        token_header = QHBoxLayout()
        token_header.addWidget(label('TOTAL TOKENS', 'muted'))
        token_header.addStretch()
        self.scope_button = button('当前任务 ▾', '切换统计范围', self.scope_menu)
        self.scope_button.setStyleSheet(f'color:{MUTED};font-size:11px;padding:0px 3px;min-height:24px;')
        token_header.addWidget(self.scope_button)
        token_box.addLayout(token_header)
        self.total = label('—', 'number')
        token_box.addWidget(self.total)
        io = QGridLayout()
        io.setVerticalSpacing(5)
        self.input = label('—', 'smallnumber')
        self.output = label('—', 'smallnumber')
        io.addWidget(label('INPUT', 'muted'), 0,0)
        io.addWidget(label('OUTPUT', 'muted'), 0,1)
        io.addWidget(self.input, 1,0)
        io.addWidget(self.output, 1,1)
        io.setColumnStretch(0,1)
        io.setColumnStretch(1,1)
        token_box.addLayout(io)
        self.insights = label('Cache hit —   ·   New work —', 'muted')
        self.insights.setToolTip(HELP['cache_hit_ratio']+'\n'+HELP['new_work'])
        token_box.addWidget(self.insights)
        details_button = button('Token Analytics  ↗', '展开完整原始用量、派生指标、模型、会话与历史', self.open_analytics)
        token_box.addWidget(details_button)
        body.addLayout(token_box)
        divider = QFrame()
        divider.setObjectName('divider')
        body.addWidget(divider)
        self.context = Meter('Context used', VIOLET)
        self.five = Meter('5-hour limit', ICE)
        self.week = Meter('Weekly limit', '#B9A7F8')
        body.addWidget(self.context)
        body.addWidget(self.five)
        body.addWidget(self.week)
        self.body_scroll = QScrollArea()
        self.body_scroll.viewport().setStyleSheet(f'background:{BG};')
        self.body_scroll.setWidgetResizable(True)
        self.body_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.body_scroll.setWidget(self.body)
        layout.addWidget(self.body_scroll,1)
        cost_row = QHBoxLayout()
        cost_left = QVBoxLayout()
        cost_left.setSpacing(4)
        self.cost_label = label('API 等价估算 · CAD', 'muted')
        self.cost = label('—', 'cost')
        cost_left.addWidget(self.cost_label)
        cost_left.addWidget(self.cost)
        cost_row.addLayout(cost_left)
        cost_row.addStretch()
        self.pin = button('◇', '置顶开关', self.toggle_top)
        self.pin.setCheckable(True)
        self.pin.setChecked(self.prefs.get('topmost', True))
        self.pin.setFixedSize(34,34)
        cost_row.addWidget(self.pin)
        layout.addLayout(cost_row)
        bottom = QHBoxLayout()
        self.status = label('每秒检查 · 等待数据', 'muted')
        bottom.addWidget(self.status)
        bottom.addStretch()
        bottom.addWidget(button('⚙', '设置与数据说明', self.open_settings))
        layout.addLayout(bottom)
        self.header.mousePressEvent = self.begin_drag
        self.header.mouseMoveEvent = self.drag
        self.header.mouseReleaseEvent = self.end_drag
        for w in (self.spirit,):
            w.mousePressEvent = self.begin_drag
            w.mouseMoveEvent = self.drag
            w.mouseReleaseEvent = self.end_drag
        for text, delta in [('Left',(-10,0)),('Right',(10,0)),('Up',(0,-10)),('Down',(0,10))]:
            QShortcut(QKeySequence('Alt+'+text), self, activated=lambda d=delta:self.move_clamped(self.pos()+QPoint(*d)))
        QShortcut(QKeySequence('Escape'), self, activated=self.hide_to_tray)
        self.tray = QSystemTrayIcon(self)
        pix = QPixmap(64,64)
        pix.fill(Qt.transparent)
        self.spirit.render(pix)
        self.setWindowIcon(QIcon(pix))
        self.tray.setIcon(QIcon(pix))
        self.tray.setToolTip('petoken · 双击显示')
        menu = QMenu()
        menu.addAction('显示 / 隐藏', self.toggle_visible)
        menu.addAction('显示 / 隐藏桌宠', self.toggle_pet)
        menu.addAction('Token Analytics', self.open_analytics)
        menu.addAction('收起 / 展开', self.toggle_compact)
        menu.addAction('设置与数据说明', self.open_settings)
        menu.addAction('移回屏幕右侧', self.reset_position)
        menu.addSeparator()
        menu.addAction('退出 petoken', self.shutdown)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason:self.toggle_visible() if reason == QSystemTrayIcon.DoubleClick else None)
        self.tray.show()
        self.tray_menu = menu
        self.compact = bool(self.prefs.get('compact', False))
        self.apply_compact()
        if not self.pin.isChecked():
            self.setWindowFlag(Qt.WindowStaysOnTopHint, False)
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

    def read_loop(self):
        store = None
        while not self.stop.is_set():
            start = time.monotonic()
            try:
                prefs = dict(self.prefs)
                if store is None or self.reset_store.is_set():
                    self.reset_store.clear()
                    store = CodexStore(prices=PRICES | prefs.get('prices', {}))
                active = self.active.title if time.time()-self.active.seen < 5 else ''
                self.bridge.data.emit(store.read(active, prefs.get('pinned',''), prefs.get('scope','task'), self.want_history.is_set()))
            except Exception:
                self.bridge.data.emit(dict(status='读取暂时失败，下一秒重试。', rows=[]))
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

    def fx_rate(self):
        manual = self.prefs.get('manual_fx')
        return dict(rate=manual, date='手动', source='自定义') if manual else self.fx_data

    def receive_limits(self, data):
        self.quota.update(data)
        self.refresh_status()

    def render(self, data):
        self.snapshot = data
        if hasattr(self,'pet'):
            self.pet.update_data(data)
        if data.get('status'):
            self.connection.setText(data['status'])
            self.connection.setToolTip(data['status'])
            self.title.setFullText('等待可用任务')
            self.project.setText('CODEX')
            for w in (self.total,self.input,self.output,self.model,self.effort,self.cost):
                w.setText('—')
            self.context.update_value(None)
            return
        modes = {'follow':'● 自动跟随', 'fixed':'◇ 已固定任务', 'recent':'◌ 最近活动 · 未识别前台'}
        self.connection.setText(modes.get(data.get('mode'),'等待数据'))
        self.connection.setToolTip('通过 Codex 窗口的辅助功能标题识别当前任务。无法识别时明确退回最近活动；可在设置中固定。')
        self.project.setText(data.get('project','CODEX').upper())
        self.title.setFullText(data.get('title','未命名任务'))
        self.model.setText(data.get('model') or '尚未记录模型')
        self.model.setToolTip('最近一次已发送的模型配置。发送前的模型菜单改动可能尚未写入记录。')
        self.effort.setText((data.get('effort') or '—')+(' · fast' if data.get('tier') in ('priority','fast') else ''))
        self.effort.setToolTip('Reasoning effort · 最近一次已发送的配置')
        tokens = data.get('tokens', {})
        for w,k in ((self.total,'total_tokens'),(self.input,'input_tokens'),(self.output,'output_tokens')):
            n = tokens.get(k,0)
            w.setText(compact_number(n) if data.get('available') else '—')
            w.setToolTip(f'{n:,} tokens' if data.get('available') and n is not None else 'N/A · 没有可靠记录')
        self.total.setToolTip(self.total.toolTip()+'\n'+HELP['total_tokens'])
        self.input.setToolTip(self.input.toolTip()+f"\nCached input: {compact_number(tokens.get('cached_input_tokens'))}")
        self.output.setToolTip(self.output.toolTip()+'\n已包含 reasoning output，不重复相加。')
        self.scope_button.setText('整个项目 ▾' if data.get('scope')=='project' else '当前任务 ▾')
        self.context.update_value(data.get('context'), 'used',
            f"当前任务 · {data.get('context_tokens')} / {data.get('context_window')} tokens\n最近一次记录的上下文占用，非累计 token；与 CLI 的保留空间算法可能略有不同。")
        self.refresh_cost()
        self.refresh_status()
        derived=(data.get('analytics') or {}).get('derived',{})
        hit=derived.get('cache_hit_ratio')
        self.insights.setText(f"Cache hit {'N/A' if hit is None else f'{hit:.1f}%'}  ·  New work {compact_number(derived.get('new_work'))}")
        if self.analytics_window and self.analytics_window.isVisible():
            self.analytics_window.update_data(data)

    def refresh_cost(self):
        d = self.snapshot
        if not d.get('available'):
            self.cost.setText('—')
            return
        fx = self.fx_rate()
        partial = bool(d.get('unknown') or d.get('partial') or any('write split unavailable' in x for x in d.get('notes',[])))
        self.cost.setText(f"≈ ${d.get('usd',0)*fx['rate']:,.2f}")
        self.cost_label.setText(('部分估算' if partial else 'API 等价估算')+' · CAD')
        tip = (f"{'项目' if d.get('scope')=='project' else '任务'} · {d.get('count',1)} 个本地会话\n"
               f"已知单价部分 USD ${d.get('usd',0):,.4f}\n1 USD = {fx['rate']:.4f} CAD · {fx['date']}\n{fx['source']}\n"
               '不是订阅账单；按已记录的模型和服务档位折算，不含工具费用。')
        if d.get('unknown'):
            tip += '\n尚无单价：'+', '.join(d['unknown'])+'（可在设置中填写）'
        if d.get('partial'):
            tip += '\n部分记录缺失 / 重置，或排除了继承历史的 fork。'
        self.cost.setToolTip(tip)
        self.cost_label.setToolTip(tip)

    def refresh_status(self):
        quota = self.quota
        limits = quota.get('limits') or self.snapshot.get('limits')
        sampled = quota.get('sampled',0)
        age = time.time()-sampled
        stale = age > 10 or bool(quota.get('error'))
        for widget,minutes in ((self.five,300),(self.week,10080)):
            w = quota_window(limits, minutes)
            if not w:
                widget.update_value(None, tip='当前账户未提供此额度。')
                widget.reset.setVisible(False)
                continue
            reset = datetime.fromtimestamp(w['reset']).strftime('%m/%d %H:%M') if w.get('reset') else '未知'
            tip = f'账户额度 · 剩余比例\n重置时间：{reset}\n'+('上次记录，等待刷新' if stale or w['expired'] else '官方接口 · 每秒查询')
            widget.update_value(w['remaining'], 'left'+(' · 旧' if stale or w['expired'] else ''), tip, stale or w['expired'])
            if w.get('reset'):
                seconds=max(0,int(w['reset']-time.time()))
                days,seconds=divmod(seconds,86400);hours,seconds=divmod(seconds,3600);minutes,seconds=divmod(seconds,60)
                widget.reset.setText('等待服务端确认重置' if w['expired'] else f"{'%dd ' % days if days else ''}{hours:02}:{minutes:02}:{seconds:02} 后重置")
                widget.reset.setVisible(True)
        self.status.setText('额度等待刷新' if stale else '每秒同步 · '+time.strftime('%H:%M:%S'))
        token_age = sample_age(self.snapshot.get('sample'))
        self.status.setToolTip((f'Tokens 最近写入：{int(token_age)} 秒前\n' if token_age is not None else '尚无 token 事件\n')+
            (quota.get('error') or '读取不会调用模型或消耗模型 tokens。'))

    def scope_menu(self):
        menu = QMenu(self)
        for text,key in [('当前任务', 'task'),('整个项目（本地记录）','project')]:
            action = menu.addAction(text)
            action.setCheckable(True)
            action.setChecked(self.prefs.get('scope','task') == key)
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
            self.pet.hide() if self.pet.isVisible() else self.pet.show()

    def toggle_top(self):
        self.prefs['topmost'] = self.pin.isChecked()
        self.setWindowFlag(Qt.WindowStaysOnTopHint, self.pin.isChecked())
        self.show()
        if hasattr(self,'pet'):
            visible=self.pet.isVisible()
            self.pet.setWindowFlag(Qt.WindowStaysOnTopHint,self.pin.isChecked())
            if visible:self.pet.show()
        self.persist()

    def apply_compact(self):
        self.body.setVisible(not self.compact)
        self.body_scroll.setVisible(not self.compact)
        self.collapse_button.setText('+' if self.compact else '−')
        self.setFixedHeight(274 if self.compact else min(730,QApplication.primaryScreen().availableGeometry().height()-24))
        QTimer.singleShot(0, lambda:self.move_clamped(self.pos()))

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
        except OSError:
            self.status.setText('设置暂时无法保存')

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
    app.setQuitOnLastWindowClosed(False)
    PREF_DIR.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(PREF_DIR/'widget.lock'))
    if not lock.tryLock(100):
        return 0
    panel = Panel()
    from pet import DesktopPet
    panel.pet=DesktopPet(panel)
    panel.pet.show()
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
            report = dict(visible=panel.isVisible(), task=panel.snapshot.get('title'),
                          has_usage=panel.snapshot.get('available'), mode=panel.snapshot.get('mode'),
                          quota_live=bool(panel.quota.get('sampled')),
                          activity_status=panel.activity.status,
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
