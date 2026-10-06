"""Reports > Analysis (2.0): line charts of AI use over time.

``series`` turns the report data (the same events, turns and sessions the
data board uses) into one value per day or per week; ``LineChart`` draws
one metric with a line per app, a total in the corner, axes that scale to
the data, and the exact values under the mouse.
"""
from __future__ import annotations

import bisect
import math
from datetime import datetime, timedelta

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

import theme

RANGES = ('7d', '30d', '12w')
COLORS = {'claude': QColor('#E0A43C'), 'codex': QColor('#5B8FE8'), 'total': QColor(theme.VIOLET)}


def buckets(kind, now):
    """[(start, end, label)] oldest first: days, or weeks starting Monday."""
    local = datetime.fromtimestamp(now)
    midnight = local.replace(hour=0, minute=0, second=0, microsecond=0)
    out = []
    if kind == '12w':
        monday = midnight - timedelta(days=local.weekday())
        for n in range(11, -1, -1):
            start = monday - timedelta(weeks=n)
            out.append((start.timestamp(), (start + timedelta(weeks=1)).timestamp(),
                        f'{start.month}/{start.day}'))
    else:
        days = 30 if kind == '30d' else 7
        for n in range(days - 1, -1, -1):
            start = midnight - timedelta(days=n)
            out.append((start.timestamp(), (start + timedelta(days=1)).timestamp(),
                        f'{start.month}/{start.day}'))
    return out


def series(data, kind, now):
    """Values per bucket: tokens, cost and tasks per app, AI working hours."""
    spans = buckets(kind, now)
    starts = [start for start, _, _ in spans]
    n = len(spans)
    tokens = {'claude': [0] * n, 'codex': [0] * n}
    usd = {'claude': [0.0] * n, 'codex': [0.0] * n}
    sessions = {'claude': [set() for _ in range(n)], 'codex': [set() for _ in range(n)]}
    for event in (data or {}).get('events') or []:
        at, provider = event.get('at'), event.get('provider')
        if provider not in tokens or not isinstance(at, (int, float)):
            continue
        index = bisect.bisect_right(starts, at) - 1
        if index < 0 or at >= spans[index][1]:
            continue
        tokens[provider][index] += event.get('tokens') or 0
        usd[provider][index] += event.get('usd') or 0
        if event.get('session'):
            sessions[provider][index].add(event['session'])
    hours = [0.0] * n
    for turn in ((data or {}).get('activity') or {}).get('turns') or []:
        begin, stop = turn[0], turn[1]
        for index, (start, end, _) in enumerate(spans):
            overlap = min(stop, end) - max(begin, start)
            if overlap > 0:
                hours[index] += overlap / 3600
    return dict(labels=[label for _, _, label in spans], tokens=tokens, usd=usd,
                tasks={p: [len(s) for s in sessions[p]] for p in sessions}, hours=hours)


def nice_max(value):
    """A round axis top at or above ``value`` (1, 2, 2.5, 5 × 10^k)."""
    if value <= 0:
        return 1
    power = 10 ** math.floor(math.log10(value))
    for step in (1, 2, 2.5, 5, 10):
        if value <= step * power:
            return step * power
    return 10 * power


class LineChart(QWidget):
    """One metric over time: a line per series, total in the corner, hover values."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setMinimumHeight(220)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.title = ''
        self.total = ''
        self.labels = []
        self.lines = []          # [(name, QColor, [values])]
        self.fmt = str
        self.hover = None

    def set_data(self, title, total, labels, lines, fmt=str):
        self.title, self.total, self.labels, self.lines, self.fmt = title, total, labels, lines, fmt
        self.hover = None
        self.update()

    def _top(self):
        return nice_max(max((max(values) for _, _, values in self.lines if values), default=0))

    def _plot(self):
        # The left margin fits the widest axis label.
        from PySide6.QtGui import QFontMetrics
        metrics = QFontMetrics(QFont('Segoe UI', 8))
        top = self._top()
        width = max(metrics.horizontalAdvance(self.fmt(top * step / 4, axis=True)) for step in range(5))
        left = max(40, width + 20)
        return QRectF(left, 64, self.width() - left - 16, self.height() - 64 - 52)

    def _x(self, plot, index):
        count = max(1, len(self.labels) - 1)
        return plot.left() + plot.width() * index / count

    def mouseMoveEvent(self, event):
        plot = self._plot()
        if not self.labels or not plot.adjusted(-8, -8, 8, 8).contains(event.position()):
            hover = None
        else:
            count = max(1, len(self.labels) - 1)
            hover = round((event.position().x() - plot.left()) / plot.width() * count)
            hover = max(0, min(len(self.labels) - 1, hover))
        if hover != self.hover:
            self.hover = hover
            self.update()

    def leaveEvent(self, event):
        self.hover = None
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        card = QRectF(.5, .5, self.width() - 1, self.height() - 1)
        p.setPen(QPen(QColor(theme.BORDER), 1))
        p.setBrush(QColor(theme.CARD))
        p.drawRoundedRect(card, 12, 12)
        # Title and the period's total.
        p.setPen(QColor(theme.MUTED))
        p.setFont(QFont('Microsoft YaHei UI', 9, QFont.DemiBold))
        p.drawText(QRectF(16, 10, self.width() - 32, 18), Qt.AlignLeft | Qt.AlignVCenter, self.title)
        p.setPen(QColor(theme.INK))
        p.setFont(QFont('Segoe UI', 17, QFont.DemiBold))
        p.drawText(QRectF(16, 28, self.width() - 32, 28), Qt.AlignLeft | Qt.AlignVCenter, self.total)
        plot = self._plot()
        top = self._top()
        # Grid and y labels.
        p.setFont(QFont('Segoe UI', 8))
        for step in range(5):
            y = plot.bottom() - plot.height() * step / 4
            grid = QColor(theme.DIVIDER)
            p.setPen(QPen(grid, 1, Qt.SolidLine if step == 0 else Qt.DotLine))
            p.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            p.setPen(QColor(theme.MUTED))
            p.drawText(QRectF(0, y - 8, plot.left() - 8, 16), Qt.AlignRight | Qt.AlignVCenter,
                       self.fmt(top * step / 4, axis=True))
        # X labels: first, last, and evenly in between.
        n = len(self.labels)
        if n:
            shown = sorted({0, n - 1, *range(0, n, max(1, round(n / 6)))})
            for index in shown:
                x = self._x(plot, index)
                p.drawText(QRectF(x - 30, plot.bottom() + 6, 60, 16), Qt.AlignCenter, self.labels[index])
        # Lines.
        for name, color, values in self.lines:
            if not values:
                continue
            path = QPainterPath()
            for index, value in enumerate(values):
                point = QPointF(self._x(plot, index), plot.bottom() - plot.height() * value / top)
                path.moveTo(point) if index == 0 else path.lineTo(point)
            p.setPen(QPen(color, 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)
        # Legend.
        x = 16.0
        p.setFont(QFont('Segoe UI', 9))
        for name, color, _ in self.lines:
            p.setPen(Qt.NoPen)
            p.setBrush(color)
            p.drawEllipse(QRectF(x, self.height() - 22, 9, 9))
            p.setPen(QColor(theme.INK))
            width = p.fontMetrics().horizontalAdvance(name)
            p.drawText(QRectF(x + 14, self.height() - 27, width + 4, 18), Qt.AlignLeft | Qt.AlignVCenter, name)
            x += width + 34
        # Hover: a guide line, the points, and the values.
        if self.hover is not None and n:
            x = self._x(plot, self.hover)
            p.setPen(QPen(QColor(theme.BORDER_CONTROL), 1, Qt.DashLine))
            p.drawLine(QPointF(x, plot.top()), QPointF(x, plot.bottom()))
            rows = [self.labels[self.hover]]
            for name, color, values in self.lines:
                value = values[self.hover]
                p.setPen(QPen(QColor(theme.CARD), 2))
                p.setBrush(color)
                p.drawEllipse(QPointF(x, plot.bottom() - plot.height() * value / top), 4, 4)
                rows.append(f'{name}  {self.fmt(value)}')
            p.setFont(QFont('Segoe UI', 9))
            width = max(p.fontMetrics().horizontalAdvance(row) for row in rows) + 20
            height = 18 * len(rows) + 10
            box_x = x + 12 if x + 12 + width < self.width() - 8 else x - 12 - width
            box = QRectF(box_x, plot.top(), width, height)
            p.setPen(QPen(QColor(theme.BORDER), 1))
            p.setBrush(QColor(theme.CONTROL_BG))
            p.drawRoundedRect(box, 8, 8)
            for index, row in enumerate(rows):
                p.setPen(QColor(theme.MUTED if index == 0 else theme.INK))
                p.drawText(QRectF(box.left() + 10, box.top() + 5 + 18 * index, width - 20, 18),
                           Qt.AlignLeft | Qt.AlignVCenter, row)
