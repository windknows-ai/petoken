"""Usage overlay above the desktop pet (V1.5).

A small card above the pet shows, for every supported app that is open on
this computer (Codex, Claude Code or both), how much is left of the 5-hour
and the weekly window and when each resets. The limits are account-wide,
so neither a project nor a task's context is shown (2.0.4: context lives in
the usage panel, and a task whose context is nearly full still notifies).
Each window is a ring gauge: the number in the middle is what is left, the
arc turns amber and then red as it runs low, and the label and reset
countdown sit beside it. A window the account does not have (Codex Pro has
no 5-hour window) shows as a dashed N/A ring.

Input-transparent: clicks pass through to the pet and the desktop.
"""
from __future__ import annotations

import threading
import time

from PySide6.QtCore import QPoint, QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QConicalGradient, QFont, QPainter, QPen
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

# Ring colours (2.0): plenty left in the app's own tone, then amber, then red.
RING = {'five': QColor('#5FA8F0'), 'week': QColor('#6A55D8')}
RING_LOW = QColor('#F2A33A')       # Under LOW_AT left.
RING_CRITICAL = QColor('#F0545C')  # Under CRITICAL_AT left.
LOW_AT, CRITICAL_AT = 40, 20
RING_SWEEP = 270                   # Degrees; the gap is at the bottom.

# Layout in overlay units: one unit is a logical pixel at 100% size. The
# card follows the character size between MIN_SCALE and MAX_SCALE only.
WIDTH = 228
PAD = 8
RADIUS = 12
HEADER_H = 18
COL_GAP = 8
RING_D = 46                        # Ring diameter.
RING_W = 5                         # Ring stroke.
TEXT_GAP = 6                       # Between a ring and its label.
SECTION_H = HEADER_H + 2 + RING_D + 2
HINT_H = 15                    # Optional advice line under a section (forecast.py).
HINT = QColor('#B07612')
SECTION_GAP = 7
GAP_ABOVE_SPRITE = 2
MIN_SCALE = 90
MAX_SCALE = 150
# role: (pixel size at 100%, smallest pixel size ever drawn, family)
FONTS = {
    'name': (12, 11, 'Segoe UI'),
    'label': (10, 10, 'Microsoft YaHei UI'),
    'cell': (11, 10, 'Microsoft YaHei UI'),
    'value': (16, 12, 'Segoe UI'),
    'percent': (10, 10, 'Segoe UI'),
    'na': (10, 10, 'Segoe UI'),
    'reset': (10, 10, 'Segoe UI'),
    'note': (10, 10, 'Microsoft YaHei UI'),
    'hint': (10, 10, 'Microsoft YaHei UI'),
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
    """Rows for one provider: the 5-hour and weekly windows. ``note``
    replaces them when none are known (for example Claude usage sync is
    off). ``context_used`` is no longer shown (the limits are account-wide)."""
    rows = []
    windows = 0
    plan = str((limits or {}).get('planType') or (limits or {}).get('plan_type') or '').lower() \
        if isinstance(limits, dict) else ''
    for minutes, kind, key in ((300, 'five', 'usage_five_hour'),
                               (10080, 'week', 'usage_week')):
        window = quota_window(limits, minutes, now)
        if kind == 'five' and provider == 'codex' and plan == 'pro':
            window = None   # Codex Pro has no 5-hour limit, whatever else arrives.
        if window is None:
            rows.append(dict(kind=kind, label=text(key, language), remaining=None,
                             reset=None, na=True))
            continue  # The account has no such window (Codex Pro: no 5h): N/A.
        windows += 1
        reset = window.get('reset')
        rows.append(dict(kind=kind, label=text(key, language),
                         remaining=window.get('remaining'),
                         reset=None if reset is None else reset - now,
                         expired=window.get('expired'), stale=stale))
    if not windows:
        # Nothing known yet (or usage sync is off): a note instead of two N/A rings.
        rows = []
    return dict(provider=provider, name=PROVIDER_NAMES.get(provider, provider),
                project=project or '', rows=rows,
                note=None if windows else (note or text('usage_quota_unknown', language)))


def _working_task(panel, provider):
    """Most recent running task of ``provider``: context, project, task key."""
    universe = getattr(getattr(panel, 'task_manager', None), '_universe', None) or {}
    tasks = [task for task in universe.values()
             if (task or {}).get('provider_id') == provider]
    if tasks:
        task = max(tasks, key=lambda t: _number(t.get('activity_at')) or 0)
        return ((task.get('presentation') or {}).get('context'),
                (task.get('display') or {}).get('project'), task.get('task_key'))
    working = (getattr(panel, 'snapshot', None) or {}).get('working_context') or {}
    if working.get('provider_id', (panel.snapshot or {}).get('provider_id')) == provider:
        return working.get('context'), working.get('project'), None
    return None, None, None


def section_hint(assistant, provider, task_key, context, quotas, language, now):
    """One line of advice for a section, or None."""
    advice = section_advice(assistant, provider, task_key, context, quotas, language, now)
    return advice[0] if advice else None


def section_advice(assistant, provider, task_key, context, quotas, language, now):
    """(text, used_up) for a section, or None. ``used_up`` lines are drawn in red."""
    from forecast import OUT_HINTS
    advice = assistant.hint(provider, task_key, context, quotas, now) if assistant else None
    if advice is None:
        return None
    key, values = advice
    return _advice_text(key, values, language), key in OUT_HINTS


def _advice_text(key, values, language):
    values = dict(values)
    if 'time' in values:
        values['time'] = format_duration(values['time'])
    if 'other' in values:
        values['other'] = PROVIDER_NAMES.get(values['other'], values['other'])
    if 'left' in values:
        values['left'] = f"{values['left']:.0f}"
    if 'minutes' in values:
        values['minutes'] = f"{values['minutes']:.0f}"
    return text(key, language, **values)


def build_sections(panel, presence, now=None, idle=False):
    """One section per open app, in registry order.

    ``idle``: the card is kept on while nothing runs. With no app open,
    it then shows each app whose limits are known, instead of nothing.
    """
    now = time.time() if now is None else now
    language = panel.prefs.get('language')
    apps = presence.apps
    if apps is None:
        # Process list unreadable: fall back to the apps with running tasks.
        universe = getattr(getattr(panel, 'task_manager', None), '_universe', None) or {}
        apps = {(task or {}).get('provider_id') for task in universe.values()}
    if idle and not apps:
        known = {'codex': ((getattr(panel, 'quota', None) or {}).get('limits')
                           if (getattr(panel, 'quota_provider', None) or 'codex') == 'codex' else None),
                 'claude': presence.claude_limits}
        apps = {provider for provider, limits in known.items() if limits}
    sections, quotas, tasks = [], {}, {}
    for provider in PROVIDER_ORDER:
        if provider not in apps:
            continue
        context, project, task_key = _working_task(panel, provider)
        tasks[provider] = (task_key, context)
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
        if not stale:
            quotas[provider] = limits
        sections.append(provider_section(provider, limits, context, project,
                                         language, now, note=note, stale=stale))
    assistant = (getattr(panel, 'assistant', None)
                 if panel.prefs.get('assistant_hints', True) else None)
    for section in sections:
        task_key, context = tasks[section['provider']]
        advice = section_advice(assistant, section['provider'], task_key, context,
                                       quotas, language, now)
        section['hint'], section['hint_out'] = advice if advice else (None, False)
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
        # Nothing is shown until the first scan has run; None afterwards
        # means the scan itself failed (then running tasks decide).
        self.apps = frozenset()
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
        sections = list(sections)
        scale = overlay_scale(self.pet.pet_scale)
        if sections == self.sections and scale == self.scale:
            self.follow()
            return  # Nothing changed this second: no relayout or repaint.
        self.sections, self.scale = sections, scale
        count = len(sections)
        height = (2 * PAD + count * SECTION_H + max(0, count - 1) * SECTION_GAP
                  + sum(HINT_H for section in sections if section.get('hint')))
        size = QSize(round(self._u(WIDTH)), round(self._u(height)))
        if self.size() != size:
            self.setFixedSize(size)
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
        try:
            self.pet.sync_usage_overlay()
        except RuntimeError:  # The pet is already gone.
            self.clock.stop()
            self.hide()

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
            if section.get('hint'):
                p.setFont(self._font('hint', bold=True))
                p.setPen(RING_CRITICAL if section.get('hint_out') else HINT)
                width = self.width() - 2 * u(PAD)
                p.drawText(QRectF(u(PAD), y, width, u(HINT_H)), Qt.AlignLeft | Qt.AlignVCenter,
                           p.fontMetrics().elidedText(section['hint'], Qt.ElideRight, int(width)))
                y += u(HINT_H)

    def _paint_section(self, p, section, y):
        u = self._u
        language = self.pet.panel.prefs.get('language')
        left, right = u(PAD), self.width() - u(PAD)
        # Title line: provider dot and name, and one "left" caption for the rings.
        # No project: the limits are account-wide.
        dot = PROVIDER_DOT.get(section['provider'], QColor(theme.ICE))
        size = u(7)
        p.setPen(QPen(dot.darker(135), 1))
        p.setBrush(dot)
        p.drawEllipse(QRectF(left, y + (u(HEADER_H) - size) / 2, size, size))
        p.setFont(self._font('name', bold=True))
        p.setPen(QColor(theme.INK))
        name_x = left + size + u(5)
        p.drawText(QRectF(name_x, y, right - name_x, u(HEADER_H)),
                   Qt.AlignLeft | Qt.AlignVCenter, section['name'])
        caption = text('usage_remaining', language)
        p.setFont(self._font('label'))
        p.setPen(QColor(theme.MUTED))
        p.drawText(QRectF(left, y, right - left, u(HEADER_H)), Qt.AlignRight | Qt.AlignVCenter, caption)
        top = y + u(HEADER_H) + u(2)
        width = (right - left - u(COL_GAP)) / 2
        for index, row in enumerate(section['rows']):
            self._paint_cell(p, row, left + index * (width + u(COL_GAP)), top, width)
        if section['note']:
            p.setFont(self._font('note'))
            p.setPen(QColor(theme.MUTED))
            p.drawText(QRectF(left, top, right - left, u(RING_D)),
                       Qt.AlignLeft | Qt.AlignVCenter | Qt.TextWordWrap, section['note'])

    @staticmethod
    def ring_color(row):
        remaining = row.get('remaining')
        if remaining is None:
            return QColor(theme.MUTED)
        if remaining < CRITICAL_AT:
            return RING_CRITICAL
        if remaining < LOW_AT:
            return RING_LOW
        return RING.get(row['kind'], QColor(theme.VIOLET))

    def _paint_cell(self, p, row, x, y, width):
        """One gauge: the ring with what is left inside, the label and reset beside it."""
        u = self._u
        language = self.pet.panel.prefs.get('language')
        remaining = row.get('remaining')
        na = bool(row.get('na'))
        dim = bool(row.get('stale') or row.get('expired'))
        d, stroke = u(RING_D), u(RING_W)
        ring = QRectF(x + stroke / 2, y + stroke / 2, d - stroke, d - stroke)
        start = (90 + RING_SWEEP / 2) * 16          # Qt: 0 at 3 o'clock, counter-clockwise.
        color = self.ring_color(row)
        # A soft disc behind the ring, tinted with its colour.
        if not na and remaining is not None:
            halo = QColor(color)
            halo.setAlpha(28)
            p.setPen(Qt.NoPen)
            p.setBrush(halo)
            p.drawEllipse(ring.adjusted(stroke * .9, stroke * .9, -stroke * .9, -stroke * .9))
        track = QColor(theme.TRACK)
        pen = QPen(track, stroke, Qt.DashLine if na else Qt.SolidLine, Qt.RoundCap)
        if na:
            pen.setDashPattern([1.2, 2.2])
        p.setBrush(Qt.NoBrush)
        p.setPen(pen)
        p.drawArc(ring, int(start), int(-RING_SWEEP * 16))
        if remaining is not None and remaining > 0:
            sweep = RING_SWEEP * min(100.0, remaining) / 100
            gradient = QConicalGradient(ring.center(), 90 + RING_SWEEP / 2)
            gradient.setColorAt(0, color.lighter(125))
            gradient.setColorAt(.75, color)
            gradient.setColorAt(1, color.darker(110))
            p.setOpacity(.45 if dim else 1)
            p.setPen(QPen(gradient, stroke, Qt.SolidLine, Qt.RoundCap))
            p.drawArc(ring, int(start), int(-sweep * 16))
            p.setOpacity(1)
        # The number in the middle, with a small % (N/A for a window the account lacks).
        if na:
            p.setFont(self._font('na', bold=True))
            p.setPen(QColor(theme.MUTED))
            p.drawText(ring, Qt.AlignCenter, 'N/A')
        elif remaining is None:
            p.setFont(self._font('value', bold=True))
            p.setPen(QColor(theme.MUTED))
            p.drawText(ring, Qt.AlignCenter, '—')
        else:
            value = f'{remaining:.0f}'
            big, small = self._font('value', bold=True), self._font('percent', bold=True)
            from PySide6.QtGui import QFontMetricsF
            wide = QFontMetricsF(big).horizontalAdvance(value)
            tail = QFontMetricsF(small).horizontalAdvance('%')
            left = ring.center().x() - (wide + tail) / 2
            p.setFont(big)
            p.setPen(QColor(theme.MUTED if dim else (RING_CRITICAL if remaining < CRITICAL_AT else theme.INK)))
            p.drawText(QRectF(left, ring.top(), wide + 1, ring.height() - u(1)), Qt.AlignLeft | Qt.AlignVCenter,
                       value)
            p.setFont(small)
            p.setPen(QColor(theme.MUTED))
            p.drawText(QRectF(left + wide, ring.top() + u(3), tail + 2, ring.height() - u(1)),
                       Qt.AlignLeft | Qt.AlignVCenter, '%')
        # Label and reset beside the ring.
        tx = x + d + u(TEXT_GAP)
        tw = max(0.0, x + width - tx)
        p.setFont(self._font('cell', bold=True))
        p.setPen(QColor(theme.INK if not na else theme.MUTED))
        p.drawText(QRectF(tx, y + d / 2 - u(15), tw, u(14)), Qt.AlignLeft | Qt.AlignVCenter,
                   p.fontMetrics().elidedText(row['label'], Qt.ElideRight, int(tw)))
        reset = row.get('reset')
        if row.get('expired'):
            detail = text('awaiting_reset', language)
        elif reset is not None:
            detail = '↻ ' + format_duration(reset)
        elif na:
            detail = text('usage_na_short', language)
        else:
            return
        p.setFont(self._font('reset'))
        p.setPen(QColor(theme.MUTED))
        p.drawText(QRectF(tx, y + d / 2 + u(1), tw, u(13)), Qt.AlignLeft | Qt.AlignVCenter,
                   p.fontMetrics().elidedText(detail, Qt.ElideRight, int(tw)))
