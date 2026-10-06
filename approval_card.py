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
from PySide6.QtWidgets import (QApplication, QButtonGroup, QDialog, QFrame, QHBoxLayout, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QPushButton,
                               QVBoxLayout, QWidget)

import claude_approval
import theme
from localization import text
from providers import PROVIDER_NAMES

POLL_MS = 400
HEARTBEAT_S = 2.0
CARD_WIDTH = 300
QUESTION_WIDTH = 340
PLAN_LINES = 8
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
QPushButton#option {{ text-align:left; padding:5px 10px; }}
QPushButton#option:checked {{ background:{theme.TAB_SELECTED_BG}; border-color:{theme.SELECT_BAR}; font-weight:600; }}
QLineEdit {{ background:{theme.TABLE_BG}; border:1px solid {theme.BORDER_CONTROL}; border-radius:7px;
             padding:4px 7px; color:{theme.INK}; }}
QPushButton#deny {{ color:{theme.DANGER_TEXT}; border-color:{theme.DANGER_BORDER}; }}
QPushButton#deny:hover {{ background:{theme.DANGER_HOVER_BG}; }}
QLabel#chip {{ background:{theme.BADGE_BG}; border:1px solid {theme.BORDER_SOFT}; border-radius:8px;
                padding:1px 8px; color:{theme.VIOLET}; font-size:11px; }}
QPushButton#link {{ background:transparent; border:none; color:{theme.ICE}; padding:0; min-height:0;
                    text-decoration:underline; font-size:11px; }}
'''


def request_title(request, language):
    provider = PROVIDER_NAMES.get(request.get('provider', 'claude'), 'Claude Code')
    tool = request.get('tool') or ''
    tool_input = request.get('input') or {}
    if request.get('provider') == 'codex':   # Codex tool names differ; judge by what is asked.
        if tool_input.get('command'):
            return text('approval_title_shell', language, provider=provider)
        if tool_input.get('file_path'):
            return text('approval_title_edit', language, provider=provider)
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
        seconds = max(0, round(request['at'] + request.get('wait', claude_approval.WAIT_S) - now))
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


class QuestionCard(QWidget):
    """Claude's clarifying questions (AskUserQuestion) beside the pet.

    One block per question: Claude's options as buttons (several may be
    chosen when the question allows it) and a field for your own answer,
    which wins over the buttons. Unlike the approval card it can take
    keyboard focus once you click into it, so you can type; it still
    appears without stealing focus.
    """

    answered = Signal(str, str, object)   # request id, 'answer' | 'ask', answers

    def __init__(self, language, request):
        super().__init__(None)
        self.language = language
        self.request = request
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setStyleSheet(STYLE)
        self.setFixedWidth(QUESTION_WIDTH)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        frame = QFrame()
        frame.setObjectName('approval')
        outer.addWidget(frame)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)
        title = QLabel(text('question_title', language, provider=PROVIDER_NAMES.get('claude', 'Claude Code')))
        title.setObjectName('title')
        title.setWordWrap(True)
        layout.addWidget(title)
        if request.get('project'):
            project = QLabel(text('approval_project', language, project=request['project']))
            project.setObjectName('muted')
            layout.addWidget(project)
        self.blocks = []
        for question in request['questions']:
            if question.get('header'):
                chip = QLabel(question['header'])
                chip.setObjectName('chip')
                layout.addWidget(chip, 0, Qt.AlignLeft)
            label = QLabel(question['question'])
            label.setWordWrap(True)
            label.setTextFormat(Qt.PlainText)
            layout.addWidget(label)
            group = QButtonGroup(self)
            group.setExclusive(not question['multi'])
            buttons = []
            for option in question['options']:
                button = QPushButton(option['label'])
                button.setObjectName('option')
                button.setCheckable(True)
                button.setCursor(Qt.PointingHandCursor)
                button.setToolTip(option.get('description') or '')
                group.addButton(button)
                button.toggled.connect(lambda _=False: self._sync())
                layout.addWidget(button)
                buttons.append(button)
            other = QLineEdit()
            other.setPlaceholderText(text('question_other', language))
            other.textChanged.connect(lambda _='': self._sync())
            layout.addWidget(other)
            self.blocks.append((question, buttons, other))
        if any(q['multi'] for q in request['questions']):
            hint = QLabel(text('question_multi', language))
            hint.setObjectName('muted')
            layout.addWidget(hint)
        row = QHBoxLayout()
        self.ask = QPushButton(text('approval_ask', language))
        self.ask.setObjectName('link')
        self.ask.setCursor(Qt.PointingHandCursor)
        self.ask.clicked.connect(lambda: self.answered.emit(request['id'], 'ask', None))
        self.submit = QPushButton(text('question_submit', language))
        self.submit.setObjectName('allow')
        self.submit.setCursor(Qt.PointingHandCursor)
        self.submit.clicked.connect(self._submit)
        row.addWidget(self.ask)
        row.addStretch(1)
        row.addWidget(self.submit)
        layout.addLayout(row)
        self.countdown = QLabel()
        self.countdown.setObjectName('muted')
        layout.addWidget(self.countdown, 0, Qt.AlignRight)
        self._sync()
        self.adjustSize()

    def answers(self):
        """question text -> typed text, the chosen label, or chosen labels."""
        result = {}
        for question, buttons, other in self.blocks:
            typed = other.text().strip()
            chosen = [b.text() for b in buttons if b.isChecked()]
            if typed:
                result[question['question']] = typed
            elif chosen:
                result[question['question']] = chosen if question['multi'] else chosen[0]
        return result

    def _sync(self):
        self.submit.setEnabled(len(self.answers()) == len(self.blocks))

    def _submit(self):
        answers = self.answers()
        if len(answers) == len(self.blocks):
            self.answered.emit(self.request['id'], 'answer', answers)

    def show_request(self, request, waiting=0, now=None):
        now = time.time() if now is None else now
        seconds = max(0, round(request['at'] + request.get('wait', claude_approval.QUESTION_WAIT_S) - now))
        minutes, rest = divmod(seconds, 60)
        line = text('question_countdown', self.language, time=f'{minutes}:{rest:02d}')
        if waiting:
            line = text('approval_more', self.language, count=waiting) + ' · ' + line
        self.countdown.setText(line)

    place_beside = ApprovalCard.place_beside


class PlanCard(QWidget):
    """Claude's plan (ExitPlanMode): accept, accept and allow edits, or ask
    for changes with a note Claude reads. Takes keyboard focus once
    clicked so the note can be typed."""

    answered = Signal(str, str, object)   # request id, choice, feedback text

    def __init__(self, language, request):
        super().__init__(None)
        self.language = language
        self.request = request
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setStyleSheet(STYLE)
        self.setFixedWidth(QUESTION_WIDTH)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        frame = QFrame()
        frame.setObjectName('approval')
        outer.addWidget(frame)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)
        title = QLabel(text('plan_title', language, provider=PROVIDER_NAMES.get('claude', 'Claude Code')))
        title.setObjectName('title')
        layout.addWidget(title)
        if request.get('project'):
            project = QLabel(text('approval_project', language, project=request['project']))
            project.setObjectName('muted')
            layout.addWidget(project)
        summary = QLabel()
        summary.setObjectName('summary')
        summary.setTextFormat(Qt.PlainText)
        summary.ensurePolished()
        summary.setText(elide_lines(request.get('plan') or '', QFontMetrics(summary.font()),
                                    QUESTION_WIDTH - 46, lines=PLAN_LINES))
        summary.setToolTip((request.get('plan') or '')[:3000])
        layout.addWidget(summary)
        if request.get('plan_file'):
            open_file = QPushButton(text('plan_open', language))
            open_file.setObjectName('link')
            open_file.setCursor(Qt.PointingHandCursor)
            open_file.clicked.connect(self.open_plan)
            layout.addWidget(open_file, 0, Qt.AlignLeft)
        self.feedback = QLineEdit()
        self.feedback.setPlaceholderText(text('plan_feedback', language))
        layout.addWidget(self.feedback)
        row = QHBoxLayout()
        row.setSpacing(6)
        self.revise = QPushButton(text('plan_revise', language))
        self.revise.setObjectName('deny')
        self.accept = QPushButton(text('plan_accept', language))
        self.accept_edits = QPushButton(text('plan_accept_edits', language))
        self.accept_edits.setObjectName('allow')
        self.accept_edits.setToolTip(text('plan_accept_edits_tip', language))
        for button, choice in ((self.revise, 'revise'), (self.accept, 'accept'),
                               (self.accept_edits, 'accept_edits')):
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(lambda _=False, c=choice: self.answered.emit(
                request['id'], c, self.feedback.text() if c == 'revise' else None))
            row.addWidget(button)
        layout.addLayout(row)
        foot = QHBoxLayout()
        ask = QPushButton(text('approval_ask', language))
        ask.setObjectName('link')
        ask.setCursor(Qt.PointingHandCursor)
        ask.clicked.connect(lambda: self.answered.emit(request['id'], 'ask', None))
        self.countdown = QLabel()
        self.countdown.setObjectName('muted')
        foot.addWidget(ask)
        foot.addStretch(1)
        foot.addWidget(self.countdown)
        layout.addLayout(foot)
        self.adjustSize()

    def open_plan(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.request['plan_file']))

    show_request = QuestionCard.show_request
    place_beside = ApprovalCard.place_beside


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

    def answer(self, request_id, choice, answers=None):
        self.broker.answer(request_id, choice, answers)
        self.queue = [r for r in self.queue if r['id'] != request_id]
        self._show()

    def _language(self):
        return self.panel.prefs.get('language')

    def _show(self, now=None):
        if not self.queue:
            self._hide()
            return
        request = self.queue[0]
        kind = QuestionCard if request.get('questions') else PlanCard if request.get('plan') is not None else None
        if kind is not None:
            if self.card is None or getattr(self.card, 'request', None) is not request \
                    or not isinstance(self.card, kind) or self.card.language != self._language():
                self._hide()
                self.card = kind(self._language(), request)
                self.card.answered.connect(self.answer)
        elif (self.card is None or isinstance(self.card, (QuestionCard, PlanCard))
              or self.card.language != self._language()):
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
        self.list.setStyleSheet('QListWidget { outline: 0px; }')   # No focus frame.
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
