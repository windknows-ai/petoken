"""Usage overlay above the desktop pet (V1.5).

While tasks run, a small card above the pet shows, for every supported app
that is open on this computer (Codex, Claude Code or both), how much is
left of the context window, the 5-hour window and the weekly window, and
when each quota resets. A window the account does not have (Codex Pro has
no 5-hour window) is simply not drawn. It replaces the single-task token
bubble; the Hub keeps its own quota rows.

Input-transparent: clicks pass through to the pet and the desktop.
"""
from __future__ import annotations

import threading
import time

from PySide6.QtCore import QPoint, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QApplication, QWidget

import claude_statusline
import theme
from localization import text
from providers import PROVIDER_NAMES
from usage import quota_window

PROVIDER_ORDER = ('codex', 'claude')
PRESENCE_INTERVAL_S = 3.0
# Codex quota samples arrive every few seconds; older than this they are
# drawn dimmed rather than presented as current.
CODEX_QUOTA_STALE_S = 120

# Bar colours from the clothing palette. Context runs from white (empty)
# to deep blue (full); 5h is a pale blue-white; the week is deep indigo.
CONTEXT_EMPTY = QColor('#FFFFFF')
CONTEXT_FULL = QColor(theme.INK)
FIVE_HOUR = QColor('#E3ECFF')
WEEK_LIGHT = QColor(theme.VIOLET)
WEEK_DARK = QColor(theme.INK)
TRACK = QColor(theme.TRACK)
PROVIDER_DOT = {'codex': QColor(112, 162, 255), 'claude': QColor(240, 182, 70)}

# Logical layout at 100% character size.
WIDTH = 284
PAD = 10
HEADER_H = 19
ROW_H = 17
LABEL_W = 46
VALUE_W = 132
BAR_H = 7
SECTION_GAP = 7
GAP_ABOVE_SPRITE = 2


def context_color(used):
    """White at 0% used, deep blue at 100%."""
    share = max(0.0, min(1.0, (used or 0) / 100))
    a, b = CONTEXT_EMPTY, CONTEXT_FULL
    return QColor(round(a.red() + (b.red() - a.red()) * share),
                  round(a.green() + (b.green() - a.green()) * share),
                  round(a.blue() + (b.blue() - a.blue()) * share))


def format_duration(seconds):
    """Compact countdown: 42m, 2h 13m, 3d 4h."""
    minutes = max(0, int(seconds) + 59) // 60
    days, minutes = divmod(minutes, 1440)
    hours, minutes = divmod(minutes, 60)
    if days:
        return f'{days}d {hours}h'
    if hours:
        return f'{hours}h {minutes:02}m'
    return f'{minutes}m'


def _number(value):
    return (value if isinstance(value, (int, float)) and not isinstance(value, bool)
            else None)


def provider_section(provider, limits, context_used, project, language, now,
                     note=None, stale=False):
    """Rows for one provider: remaining context, then each quota window
    the account actually has. ``note`` replaces the quota rows when none
    are known (for example Claude usage sync is off)."""
    used = _number(context_used)
    rows = [dict(kind='context', label=text('usage_context', language),
                 remaining=None if used is None else max(0.0, 100 - used),
                 used=used, reset=None)]
    windows = 0
    for minutes, kind, key in ((300, 'five', 'usage_five_hour'),
                               (10080, 'week', 'usage_week')):
        window = quota_window(limits, minutes, now)
        if window is None:
            continue  # The account has no such window (Codex Pro: no 5h).
        windows += 1
        reset = window.get('reset')
        rows.append(dict(kind=kind, label=text(key, language),
                         remaining=window.get('remaining'),
                         reset=None if reset is None else reset - now,
                         expired=window.get('expired'), stale=stale))
    return dict(provider=provider, name=PROVIDER_NAMES.get(provider, provider),
                project=project or '', rows=rows,
                note=None if windows else (note or text('usage_quota_unknown', language)))


def _working_task(panel, provider):
    """Most recent running task of ``provider`` (context and project)."""
    universe = getattr(getattr(panel, 'task_manager', None), '_universe', None) or {}
    tasks = [task for task in universe.values()
             if (task or {}).get('provider_id') == provider]
    if tasks:
        task = max(tasks, key=lambda t: _number(t.get('activity_at')) or 0)
        return ((task.get('presentation') or {}).get('context'),
                (task.get('display') or {}).get('project'))
    working = (getattr(panel, 'snapshot', None) or {}).get('working_context') or {}
    if working.get('provider_id', (panel.snapshot or {}).get('provider_id')) == provider:
        return working.get('context'), working.get('project')
    return None, None


def build_sections(panel, presence, now=None):
    """One section per open app, in registry order."""
    now = time.time() if now is None else now
    language = panel.prefs.get('language')
    apps = presence.apps
    if apps is None:
        # Process list unreadable: fall back to the apps with running tasks.
        universe = getattr(getattr(panel, 'task_manager', None), '_universe', None) or {}
        apps = {(task or {}).get('provider_id') for task in universe.values()}
    sections = []
    for provider in PROVIDER_ORDER:
        if provider not in apps:
            continue
        context, project = _working_task(panel, provider)
        if provider == 'codex':
            quota = getattr(panel, 'quota', None) or {}
            usable = (getattr(panel, 'quota_provider', None) or 'codex') == 'codex'
            limits = quota.get('limits') if usable else None
            sampled = _number(quota.get('sampled')) or 0
            stale = bool(quota.get('error')) or now - sampled > CODEX_QUOTA_STALE_S
            note = text('usage_quota_waiting_codex', language)
        else:
            limits, stale = presence.claude_limits, False
            note = text('usage_claude_sync_on' if presence.claude_sync == 'on'
                        else 'usage_claude_sync_off', language)
        sections.append(provider_section(provider, limits, context, project,
                                         language, now, note=note, stale=stale))
    return sections


class UsagePresence:
    """Background watcher: which apps are open, and Claude's bridge data.

    Process scanning takes tens of milliseconds, so it never runs on the
    UI thread. Readers only ever see whole, immutable values.
    """

    def __init__(self, scan=None, interval=PRESENCE_INTERVAL_S):
        if scan is None:
            from desktop import running_apps
            scan = running_apps
        self._scan = scan
        self.interval = interval
        self.apps = None
        self.claude_limits = None
        self.claude_sync = 'off'
        self._stop = threading.Event()
        self._thread = None

    def poll(self):
        try:
            apps = self._scan()
        except Exception:
            apps = None
        self.apps = None if apps is None else frozenset(apps)
        try:
            self.claude_limits = claude_statusline.account_limits(
                claude_statusline.read_snapshots())[0]
            self.claude_sync = claude_statusline.state()
        except Exception:
            self.claude_limits = None

    def start(self):
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, daemon=True,
                                            name='usage-presence')
            self._thread.start()

    def _run(self):
        while not self._stop.is_set():
            self.poll()
            self._stop.wait(self.interval)

    def stop(self):
        self._stop.set()


class UsageOverlay(QWidget):
    """Frameless, click-through card that sits just above the pet's head."""

    def __init__(self, pet):
        super().__init__(None)
        self.pet = pet
        flags = (Qt.Tool | Qt.FramelessWindowHint | Qt.WindowTransparentForInput
                 | Qt.WindowDoesNotAcceptFocus)
        if pet.panel.prefs.get('always_on_top', True):
            flags |= Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.sections = []
        self.clock = QTimer(self)
        self.clock.setInterval(1000)
        self.clock.timeout.connect(self.refresh)

    def _px(self, logical):
        return self.pet._px(logical)

    def set_sections(self, sections):
        self.sections = list(sections)
        height = PAD * 2
        for index, section in enumerate(self.sections):
            rows = len(section['rows']) + (1 if section['note'] else 0)
            height += HEADER_H + rows * ROW_H + (SECTION_GAP if index else 0)
        self.setFixedSize(self._px(WIDTH), self._px(height))
        self.follow()
        self.update()

    def follow(self):
        """Centre above the pet's sprite box, kept on the pet's screen."""
        pet = self.pet
        top = pet.pos().y() + self._px(64 - GAP_ABOVE_SPRITE)
        x = pet.pos().x() + (pet.width() - self.width()) // 2
        y = top - self.height()
        screen = (pet.screen() or QApplication.primaryScreen()).availableGeometry()
        x = max(screen.left(), min(x, screen.right() - self.width() + 1))
        y = max(screen.top(), min(y, screen.bottom() - self.height() + 1))
        if self.pos() != QPoint(x, y):
            self.move(x, y)

    def refresh(self):
        self.pet.sync_usage_overlay()

    def showEvent(self, event):
        self.clock.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self.clock.stop()
        super().hideEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        px = self._px
        card = QColor(theme.CARD)
        card.setAlpha(242)
        p.setPen(QPen(QColor(theme.BORDER), 1))
        p.setBrush(card)
        p.drawRoundedRect(QRectF(.5, .5, self.width() - 1, self.height() - 1),
                          px(theme.RADIUS_CARD), px(theme.RADIUS_CARD))
        y = px(PAD)
        for index, section in enumerate(self.sections):
            if index:
                y += px(SECTION_GAP)
                divider = QColor(theme.DIVIDER)
                p.setPen(QPen(divider, 1))
                p.drawLine(px(PAD), y - px(SECTION_GAP) // 2,
                           self.width() - px(PAD), y - px(SECTION_GAP) // 2)
            y = self._paint_header(p, section, y)
            for row in section['rows']:
                y = self._paint_row(p, row, y)
            if section['note']:
                p.setFont(QFont('Microsoft YaHei UI', px(8)))
                p.setPen(QColor(theme.MUTED))
                rect = QRectF(px(PAD), y, self.width() - 2 * px(PAD), px(ROW_H))
                p.drawText(rect, Qt.AlignLeft | Qt.AlignVCenter,
                           p.fontMetrics().elidedText(section['note'], Qt.ElideRight,
                                                      int(rect.width())))
                y += px(ROW_H)

    def _paint_header(self, p, section, y):
        px = self._px
        dot = PROVIDER_DOT.get(section['provider'], QColor(theme.ICE))
        p.setPen(QPen(dot.darker(135), 1))
        p.setBrush(dot)
        p.drawEllipse(QRectF(px(PAD), y + px(HEADER_H) / 2 - px(4), px(8), px(8)))
        p.setFont(QFont('Segoe UI', px(9), QFont.DemiBold))
        p.setPen(QColor(theme.INK))
        name_x = px(PAD) + px(13)
        p.drawText(QRectF(name_x, y, px(120), px(HEADER_H)),
                   Qt.AlignLeft | Qt.AlignVCenter, section['name'])
        name_w = p.fontMetrics().horizontalAdvance(section['name'])
        if section['project']:
            p.setFont(QFont('Microsoft YaHei UI', px(8)))
            p.setPen(QColor(theme.MUTED))
            left = name_x + name_w + px(10)
            width = self.width() - px(PAD) - left
            p.drawText(QRectF(left, y, width, px(HEADER_H)), Qt.AlignRight | Qt.AlignVCenter,
                       p.fontMetrics().elidedText(section['project'], Qt.ElideRight, int(width)))
        return y + px(HEADER_H)

    def _paint_row(self, p, row, y):
        px = self._px
        language = self.pet.panel.prefs.get('language')
        p.setFont(QFont('Microsoft YaHei UI', px(8)))
        p.setPen(QColor(theme.MUTED))
        p.drawText(QRectF(px(PAD), y, px(LABEL_W), px(ROW_H)),
                   Qt.AlignLeft | Qt.AlignVCenter, row['label'])
        bar_x = px(PAD) + px(LABEL_W)
        bar_w = self.width() - px(PAD) - px(VALUE_W) - px(6) - bar_x
        bar = QRectF(bar_x, y + (px(ROW_H) - px(BAR_H)) / 2, bar_w, px(BAR_H))
        radius = px(BAR_H) / 2
        p.setPen(Qt.NoPen)
        p.setBrush(TRACK)
        p.drawRoundedRect(bar, radius, radius)
        remaining = row.get('remaining')
        dim = bool(row.get('stale') or row.get('expired'))
        if remaining is not None and remaining > 0:
            fill = QRectF(bar.left(), bar.top(), max(px(BAR_H), bar.width() * remaining / 100),
                          bar.height())
            if row['kind'] == 'context':
                brush = context_color(row.get('used'))
            elif row['kind'] == 'five':
                brush = FIVE_HOUR
            else:
                brush = QLinearGradient(fill.topLeft(), fill.topRight())
                brush.setColorAt(0, WEEK_DARK)
                brush.setColorAt(1, WEEK_LIGHT)
            p.setOpacity(.45 if dim else 1)
            p.setBrush(brush)
            outline = QColor(theme.BORDER)
            outline.setAlpha(150)
            p.setPen(QPen(outline, 1))
            p.drawRoundedRect(fill.adjusted(.5, .5, -.5, -.5), radius, radius)
            p.setOpacity(1)
        value = ('—' if remaining is None
                 else text('usage_left', language, pct=f'{remaining:.0f}%'))
        reset = row.get('reset')
        detail = ''
        if row.get('expired'):
            detail = text('awaiting_reset', language)
        elif reset is not None:
            detail = text('usage_resets', language, time=format_duration(reset))
        value_rect = QRectF(self.width() - px(PAD) - px(VALUE_W), y, px(VALUE_W), px(ROW_H))
        p.setFont(QFont('Segoe UI', px(8), QFont.DemiBold))
        p.setPen(QColor(theme.MUTED if dim else theme.INK))
        p.drawText(value_rect, Qt.AlignLeft | Qt.AlignVCenter, value)
        if detail:
            value_w = p.fontMetrics().horizontalAdvance(value)
            p.setFont(QFont('Microsoft YaHei UI', px(8)))
            p.setPen(QColor(theme.MUTED))
            rest = QRectF(value_rect.left() + value_w, y, value_rect.width() - value_w, px(ROW_H))
            p.drawText(rest, Qt.AlignLeft | Qt.AlignVCenter,
                       p.fontMetrics().elidedText(' · ' + detail, Qt.ElideRight,
                                                  int(rest.width())))
        return y + px(ROW_H)
