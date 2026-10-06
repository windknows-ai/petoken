"""Permission requests on the pet (V1.6 B).

``ApprovalController`` keeps Petoken's side of ``claude_approval`` going
(heartbeat, new requests, answers) while the hook is installed, and
``ApprovalCard`` shows the oldest open request beside the pet: what Claude
Code wants to do, Allow / Always allow / Deny, "Answer in Claude", and how
long until the question goes back to Claude Code by itself.

The card never takes keyboard focus, so typing in a terminal or editor is
not interrupted when it appears.
"""
from __future__ import annotations

import time

from PySide6.QtCore import QObject, QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (QApplication, QDialog, QFrame, QHBoxLayout, QLabel, QListWidget,
                               QListWidgetItem, QPushButton,
                               QVBoxLayout, QWidget)

import claude_approval
import theme
from localization import text
from providers import PROVIDER_NAMES

POLL_MS = 400
HEARTBEAT_S = 2.0
CARD_WIDTH = 300
SUMMARY_LINES = 4
GAP = 8

STYLE = f'''
QFrame#approval {{ background:{theme.CARD}; border:1px solid {theme.BORDER}; border-radius:12px; }}
QLabel {{ background:transparent; border:none; color:{theme.INK}; }}
QLabel#title {{ font-weight:600; font-size:13px; }}
QLabel#muted {{ color:{theme.MUTED}; font-size:11px; }}
QLabel#summary {{ background:{theme.TABLE_BG}; border:1px solid {theme.BORDER_SOFT}; border-radius:6px;
                  padding:5px 7px; font-family:Consolas,'Microsoft YaHei UI'; font-size:12px; }}
QPushButton {{ background:{theme.CONTROL_BG}; border:1px solid {theme.BORDER_SOFT};
               border-bottom:2px solid {theme.BORDER_CONTROL}; border-radius:7px; padding:4px 10px;
               min-height:22px; color:{theme.INK}; }}
QPushButton:hover {{ background:{theme.HOVER_BG}; border-color:{theme.HOVER_BORDER}; }}
QPushButton:disabled {{ color:{theme.BORDER}; }}
QPushButton#allow {{ background:{theme.PRIMARY_FILL}; color:{theme.PRIMARY_TEXT}; border-color:{theme.PRIMARY_FILL_PRESSED}; }}
QPushButton#allow:hover {{ background:{theme.PRIMARY_FILL_HOVER}; }}
QPushButton#deny {{ color:{theme.DANGER_TEXT}; border-color:{theme.DANGER_BORDER}; }}
QPushButton#deny:hover {{ background:{theme.DANGER_HOVER_BG}; }}
QPushButton#link {{ background:transparent; border:none; color:{theme.ICE}; padding:0; min-height:0;
                    text-decoration:underline; font-size:11px; }}
'''


def request_title(request, language):
    provider = PROVIDER_NAMES.get('claude', 'Claude Code')
    tool = request.get('tool') or ''
    if tool in claude_approval.SHELL_TOOLS:
        return text('approval_title_shell', language, provider=provider)
    if tool in claude_approval.EDIT_TOOLS:
        return text('approval_title_edit', language, provider=provider)
    if tool in ('WebFetch', 'WebSearch'):
        return text('approval_title_web', language, provider=provider)
    return text('approval_title_tool', language, provider=provider, tool=tool)


def elide_lines(value, metrics, width, lines=SUMMARY_LINES):
    """Wrap ``value`` to ``width`` pixels, at most ``lines`` lines."""
    out = []
    for paragraph in (value or '').splitlines() or ['']:
        rest = paragraph
        while True:
            if len(out) == lines:
                out[-1] = metrics.elidedText(out[-1] + '…', Qt.ElideRight, width)
                return '\n'.join(out)
            if metrics.horizontalAdvance(rest) <= width:
                out.append(rest)
                break
            cut = len(rest)
            while cut > 1 and metrics.horizontalAdvance(rest[:cut]) > width:
                cut -= 1
            out.append(rest[:cut])
            rest = rest[cut:]
    return '\n'.join(out)


class ApprovalCard(QWidget):
    answered = Signal(str, str)   # request id, choice

    def __init__(self, language):
        super().__init__(None)
        self.language = language
        self.request = None
        self.ensurePolished()
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                            | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setStyleSheet(STYLE)
        self.setFixedWidth(CARD_WIDTH)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        frame = QFrame()
        frame.setObjectName('approval')
        outer.addWidget(frame)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)
        self.title = QLabel()
        self.title.setObjectName('title')
        self.title.setWordWrap(True)
        layout.addWidget(self.title)
        self.project = QLabel()
        self.project.setObjectName('muted')
        layout.addWidget(self.project)
        self.summary = QLabel()
        self.summary.setObjectName('summary')
        self.summary.setTextFormat(Qt.PlainText)
        layout.addWidget(self.summary)
        self.description = QLabel()
        self.description.setObjectName('muted')
        self.description.setWordWrap(True)
        layout.addWidget(self.description)
        buttons = QHBoxLayout()
        buttons.setSpacing(6)
        self.allow = QPushButton()
        self.allow.setObjectName('allow')
        self.always = QPushButton()
        self.deny = QPushButton()
        self.deny.setObjectName('deny')
        for button, choice in ((self.allow, 'allow'), (self.always, 'always'), (self.deny, 'deny')):
            button.setFocusPolicy(Qt.NoFocus)
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(lambda _=False, c=choice: self._answer(c))
            buttons.addWidget(button)
        layout.addLayout(buttons)
        foot = QHBoxLayout()
        self.ask = QPushButton()
        self.ask.setObjectName('link')
        self.ask.setFocusPolicy(Qt.NoFocus)
        self.ask.setCursor(Qt.PointingHandCursor)
        self.ask.clicked.connect(lambda: self._answer('ask'))
        self.countdown = QLabel()
        self.countdown.setObjectName('muted')
        foot.addWidget(self.ask)
        foot.addStretch(1)
        foot.addWidget(self.countdown)
        layout.addLayout(foot)

    def _answer(self, choice):
        if self.request is not None:
            self.answered.emit(self.request['id'], choice)

    def show_request(self, request, waiting=0, now=None):
        language = self.language
        changed = request is not self.request
        self.request = request
        if changed:
            self.title.setText(request_title(request, language))
            project = request.get('project') or ''
            self.project.setVisible(bool(project))
            self.project.setText(QFontMetrics(self.project.font()).elidedText(
                text('approval_project', language, project=project), Qt.ElideMiddle, CARD_WIDTH - 30))
            self.summary.ensurePolished()   # Measure with the stylesheet's monospace font.
            metrics = QFontMetrics(self.summary.font())
            self.summary.setText(elide_lines(request.get('summary') or '', metrics, CARD_WIDTH - 46))
            self.summary.setToolTip(request.get('summary') or '')
            self.description.setText(request.get('description') or '')
            self.description.setVisible(bool(request.get('description')))
            self.allow.setText(text('approval_allow', language))
            self.always.setText(text('approval_always', language))
            self.deny.setText(text('approval_deny', language))
            self.ask.setText(text('approval_ask', language))
            self.always.setEnabled(bool(request.get('can_always')))
            if request.get('can_always'):
                tool, content = request['rule']
                rule = claude_approval.rule_text(dict(toolName=tool, ruleContent=content))
                self.always.setToolTip(text('approval_always_tip', language,
                                            project=request.get('project') or '', rule=rule))
            else:
                self.always.setToolTip(text('approval_always_unavailable', language))
            self.adjustSize()
        now = time.time() if now is None else now
        seconds = max(0, round(request['at'] + claude_approval.WAIT_S - now))
        line = text('approval_countdown', language, seconds=seconds)
        if waiting:
            line = text('approval_more', language, count=waiting) + ' · ' + line
        self.countdown.setText(line)

    def place_beside(self, pet):
        """Left of the pet when there is room, otherwise right; on its screen."""
        screen = (pet.screen() or QApplication.primaryScreen()).availableGeometry()
        box = pet.geometry()
        x = box.left() - self.width() - GAP
        if x < screen.left():
            x = box.right() + GAP
        y = box.center().y() - self.height() // 2
        x = max(screen.left(), min(x, screen.right() - self.width() + 1))
        y = max(screen.top(), min(y, screen.bottom() - self.height() + 1))
        if self.pos() != QPoint(x, y):
            self.move(x, y)


class ApprovalController(QObject):
    """Runs the exchange while the hook is installed."""

    requested = Signal(dict)

    def __init__(self, panel, broker=None):
        super().__init__()
        self.panel = panel
        self.broker = broker or claude_approval.ApprovalBroker()
        self.queue = []
        self.card = None
        self._beat = 0.0
        self.timer = QTimer(self)
        self.timer.setInterval(POLL_MS)
        self.timer.timeout.connect(self.tick)

    @property
    def active(self):
        return self.timer.isActive()

    def start(self):
        if not self.timer.isActive():
            self._beat = 0.0
            self.timer.start()
            self.tick()

    def stop(self):
        self.timer.stop()
        self.queue.clear()
        self.broker.shutdown()
        self._hide()

    def tick(self, now=None):
        now = time.time() if now is None else now
        if now - self._beat >= HEARTBEAT_S:
            self._beat = now
            self.broker.heartbeat()
        new, gone = self.broker.poll()
        if gone:
            self.queue = [r for r in self.queue if r['id'] not in gone]
        for request in new:
            self.queue.append(request)
            self.requested.emit(request)
        self._show(now)

    def answer(self, request_id, choice):
        self.broker.answer(request_id, choice)
        self.queue = [r for r in self.queue if r['id'] != request_id]
        self._show()

    def _language(self):
        return self.panel.prefs.get('language')

    def _show(self, now=None):
        if not self.queue:
            self._hide()
            return
        if self.card is None or self.card.language != self._language():
            self._hide()
            self.card = ApprovalCard(self._language())
            self.card.answered.connect(self.answer)
        self.card.show_request(self.queue[0], waiting=len(self.queue) - 1, now=now)
        pet = getattr(self.panel, 'pet', None)
        if pet is not None:
            self.card.place_beside(pet)
        if not self.card.isVisible():
            self.card.show()

    def _hide(self):
        if self.card is not None:
            self.card.hide()
            self.card.deleteLater()
            self.card = None


class ApprovalRulesDialog(QDialog):
    """Rules that "Always allow" added, per project, each one revocable."""

    def __init__(self, parent, language, ledger=None):
        super().__init__(parent)
        self.language = language
        self.ledger = ledger
        self.setWindowTitle(text('approval_rules_title', language))
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)
        intro = QLabel(text('approval_rules_intro', language))
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.list = QListWidget()
        self.list.currentRowChanged.connect(lambda _: self._sync())
        layout.addWidget(self.list)
        row = QHBoxLayout()
        self.revoke_button = QPushButton(text('approval_revoke', language))
        self.revoke_button.clicked.connect(self.revoke)
        close = QPushButton(text('approval_rules_close', language))
        close.clicked.connect(self.accept)
        row.addWidget(self.revoke_button)
        row.addStretch(1)
        row.addWidget(close)
        layout.addLayout(row)
        self.refresh()

    def refresh(self):
        self.list.clear()
        self.entries = claude_approval.list_rules(self.ledger)
        for entry in self.entries:
            what = ', '.join(entry.get('rules') or entry.get('directories') or [])
            item = QListWidgetItem(f"{entry.get('project') or entry['cwd']} · {what}")
            item.setToolTip(entry['cwd'])
            self.list.addItem(item)
        if not self.entries:
            self.list.addItem(QListWidgetItem(text('approval_rules_empty', self.language)))
        self._sync()

    def _sync(self):
        self.revoke_button.setEnabled(bool(self.entries) and self.list.currentRow() >= 0)

    def revoke(self):
        row = self.list.currentRow()
        if 0 <= row < len(self.entries):
            claude_approval.revoke(self.entries[row], self.ledger)
            self.refresh()
