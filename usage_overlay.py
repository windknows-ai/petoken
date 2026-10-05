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

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer
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

# Layout in overlay units: one unit is a logical pixel at 100% size. The
# card follows the character size between MIN_SCALE and MAX_SCALE only.
WIDTH = 228
PAD = 8
RADIUS = 10
HEADER_H = 17
COL_GAP = 9
VALUE_H = 15
BAR_H = 5
BAR_GAP = 3
RESET_H = 13
SECTION_H = HEADER_H + VALUE_H + BAR_GAP + BAR_H + BAR_GAP + RESET_H
SECTION_GAP = 7
GAP_ABOVE_SPRITE = 2
MIN_SCALE = 90
MAX_SCALE = 150
# role: (pixel size at 100%, smallest pixel size ever drawn, family)
FONTS = {
    'name': (12, 11, 'Segoe UI'),
    'label': (10, 10, 'Microsoft YaHei UI'),
    'value': (12, 11, 'Segoe UI'),
    'reset': (10, 10, 'Segoe UI'),
    'note': (10, 10, 'Microsoft YaHei UI'),
}


def overlay_scale(pet_scale):
    return max(MIN_SCALE, min(MAX_SCALE, pet_scale)) / 100


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
        return f'{hours}h {minutes}m'
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
    """Frameless, click-through card that sits just above the pet's head.

    Each open app gets a title line and three side-by-side cells (context,
    5h, week): what is left, a slim bar and the reset countdown. The card
    follows the character size only down to MIN_SCALE and every font has a
    pixel floor, so it stays readable on a small character.
    """

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
        self.scale = overlay_scale(pet.pet_scale)
        self.clock = QTimer(self)
        self.clock.setInterval(1000)
        self.clock.timeout.connect(self.refresh)

    def _u(self, value):
        """Overlay layout units to logical pixels."""
        return value * self.scale

    def _font(self, role, bold=False):
        base, floor, family = FONTS[role]
        font = QFont(family)
        font.setPixelSize(max(floor, round(base * self.scale)))
        if bold:
            font.setWeight(QFont.DemiBold)
        return font

    def set_sections(self, sections):
        self.sections = list(sections)
        self.scale = overlay_scale(self.pet.pet_scale)
        count = len(self.sections)
        height = 2 * PAD + count * SECTION_H + max(0, count - 1) * SECTION_GAP
        self.setFixedSize(round(self._u(WIDTH)), round(self._u(height)))
        self.follow()
        self.update()

    def follow(self):
        """Centre above the pet's sprite box, kept on the pet's screen."""
        pet = self.pet
        top = pet.pos().y() + pet._px(64 - GAP_ABOVE_SPRITE)
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
        u = self._u
        card = QColor(theme.CARD)
        card.setAlpha(242)
        p.setPen(QPen(QColor(theme.BORDER), 1))
        p.setBrush(card)
        p.drawRoundedRect(QRectF(.5, .5, self.width() - 1, self.height() - 1), u(RADIUS), u(RADIUS))
        y = u(PAD)
        for index, section in enumerate(self.sections):
            if index:
                p.setPen(QPen(QColor(theme.DIVIDER), 1))
                middle = y + u(SECTION_GAP) / 2
                p.drawLine(QPointF(u(PAD), middle), QPointF(self.width() - u(PAD), middle))
                y += u(SECTION_GAP)
            self._paint_section(p, section, y)
            y += u(SECTION_H)

    def _paint_section(self, p, section, y):
        u = self._u
        language = self.pet.panel.prefs.get('language')
        left, right = u(PAD), self.width() - u(PAD)
        # Title line: provider dot and name, project, and one "left" caption
        # that covers every percentage below it.
        dot = PROVIDER_DOT.get(section['provider'], QColor(theme.ICE))
        size = u(7)
        p.setPen(QPen(dot.darker(135), 1))
        p.setBrush(dot)
        p.drawEllipse(QRectF(left, y + (u(HEADER_H) - size) / 2, size, size))
        p.setFont(self._font('name', bold=True))
        p.setPen(QColor(theme.INK))
        name_x = left + size + u(4)
        p.drawText(QRectF(name_x, y, right - name_x, u(HEADER_H)),
                   Qt.AlignLeft | Qt.AlignVCenter, section['name'])
        name_end = name_x + p.fontMetrics().horizontalAdvance(section['name'])
        caption = text('usage_remaining', language)
        p.setFont(self._font('label'))
        p.setPen(QColor(theme.MUTED))
        caption_w = p.fontMetrics().horizontalAdvance(caption)
        p.drawText(QRectF(right - caption_w, y, caption_w, u(HEADER_H)),
                   Qt.AlignRight | Qt.AlignVCenter, caption)
        project_x = name_end + u(6)
        project_w = right - caption_w - u(8) - project_x
        if section['project'] and project_w > u(12):
            p.drawText(QRectF(project_x, y, project_w, u(HEADER_H)), Qt.AlignLeft | Qt.AlignVCenter,
                       p.fontMetrics().elidedText(section['project'], Qt.ElideRight, int(project_w)))
        # Cells.
        top = y + u(HEADER_H)
        width = (right - left - 2 * u(COL_GAP)) / 3
        for index, row in enumerate(section['rows']):
            self._paint_cell(p, row, left + index * (width + u(COL_GAP)), top, width)
        if section['note']:
            x = left + len(section['rows']) * (width + u(COL_GAP))
            p.setFont(self._font('note'))
            p.setPen(QColor(theme.MUTED))
            p.drawText(QRectF(x, top, right - x, u(SECTION_H - HEADER_H)),
                       Qt.AlignLeft | Qt.AlignVCenter | Qt.TextWordWrap, section['note'])

    def _paint_cell(self, p, row, x, y, width):
        u = self._u
        language = self.pet.panel.prefs.get('language')
        remaining = row.get('remaining')
        dim = bool(row.get('stale') or row.get('expired'))
        # Line 1: label left, what is left right.
        value = '—' if remaining is None else f'{remaining:.0f}%'
        p.setFont(self._font('value', bold=True))
        p.setPen(QColor(theme.MUTED if dim else theme.INK))
        value_w = p.fontMetrics().horizontalAdvance(value)
        p.drawText(QRectF(x, y, width, u(VALUE_H)), Qt.AlignRight | Qt.AlignVCenter, value)
        p.setFont(self._font('label'))
        p.setPen(QColor(theme.MUTED))
        label_w = max(0, width - value_w - u(3))
        p.drawText(QRectF(x, y, label_w, u(VALUE_H)), Qt.AlignLeft | Qt.AlignVCenter,
                   p.fontMetrics().elidedText(row['label'], Qt.ElideRight, int(label_w)))
        # Line 2: slim bar of what is left.
        bar = QRectF(x, y + u(VALUE_H + BAR_GAP), width, u(BAR_H))
        radius = bar.height() / 2
        p.setPen(Qt.NoPen)
        p.setBrush(TRACK)
        p.drawRoundedRect(bar, radius, radius)
        if remaining is not None and remaining > 0:
            fill = QRectF(bar.left(), bar.top(), max(bar.height(), bar.width() * remaining / 100),
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
        # Line 3: reset countdown.
        reset = row.get('reset')
        if row.get('expired'):
            detail = text('awaiting_reset', language)
        elif reset is not None:
            detail = '↻ ' + format_duration(reset)
        else:
            return
        p.setFont(self._font('reset'))
        p.setPen(QColor(theme.MUTED))
        p.drawText(QRectF(x, bar.bottom() + u(BAR_GAP), width, u(RESET_H)),
                   Qt.AlignLeft | Qt.AlignVCenter,
                   p.fontMetrics().elidedText(detail, Qt.ElideRight, int(width)))
