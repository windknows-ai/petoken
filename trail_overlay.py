"""Manager-owned decorative comet-trail overlay (V1.3 D2B).

UI-only layer: no provider/data imports, no task membership, no
accounting. It paints short fading light ribbons behind moving task
stars in screen coordinates. Fully non-interactive
(WA_TransparentForMouseEvents): it can never eat clicks meant for
stars, Petoken, or desktop apps beneath it.

Ownership and lifetimes belong to TaskPanelManager: bounded per-task
histories, expiry on stillness, immediate removal on task retire /
provider failure / shutdown. When still, trails fade and the overlay
hides itself so zero paint work remains.
"""
from __future__ import annotations

from collections import deque

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QApplication, QWidget

import pet_geometry as pet_geometry


def _trail_pen(fraction):
    """Icy-cyan head fading to violet tail (fraction 0 = oldest)."""
    head = (140, 200, 255)
    tail = (150, 130, 255)
    color = tuple(int(tail[k] + (head[k] - tail[k]) * fraction)
                  for k in range(3))
    pen = QPen(QColor(*color, max(0, min(90, int(90 * fraction)))))
    pen.setWidthF(1.0 + 4.0 * fraction)
    pen.setCapStyle(Qt.RoundCap)
    return pen


class TrailOverlay(QWidget):
    """One transparent fullscreen-ish layer for all task trails."""

    def __init__(self):
        super().__init__(
            None,
            Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._trails = {}
        self._lowered = False

    def record_sample(self, identity, x, y, stamp):
        """Append one screen-center sample (hard-bounded history).

        Centers are the float nominal positions, so slow sub-pixel
        motion still accumulates a visible ribbon; integer
        quantization would erase it. Stillness adds identical points
        that never satisfy the visibility span.
        """
        trail = self._trails.get(identity)
        if trail is None:
            trail = deque(maxlen=pet_geometry.TRAIL_MAX_SAMPLES)
            self._trails[identity] = trail
        trail.append((x, y, stamp))

    def visual_signature(self):
        """Hashable snapshot of everything paintEvent renders.

        Lets callers request a repaint only when the visible output
        would actually change (never blind per-tick repaints).
        Positions round to 0.1 px: finer drift is invisible anyway.
        """
        return tuple(sorted(
            (identity, tuple((round(x, 1), round(y, 1))
                             for x, y, _ in trail))
            for identity, trail in self._trails.items()))

    def prune(self, now):
        """Drop expired samples; forget emptied trails.

        Returns True when anything was actually removed.
        """
        max_age = pet_geometry.TRAIL_MAX_AGE_S
        removed = False
        for identity in list(self._trails):
            trail = self._trails[identity]
            while trail and now - trail[0][2] > max_age:
                trail.popleft()
                removed = True
            if not trail:
                del self._trails[identity]
        return removed

    def drop(self, identity):
        """Remove one task's trail immediately (retire/failure/hide).

        Returns True when a trail actually existed.
        """
        return self._trails.pop(identity, None) is not None

    def clear_all(self):
        """Remove every trail (shutdown). Returns True if any existed."""
        had_trails = bool(self._trails)
        self._trails.clear()
        return had_trails

    def has_trails(self):
        """Whether any visible ribbon remains to paint.

        Needs at least two samples spanning real movement: a frozen
        star's identical points never qualify, however many pile up.
        """
        span = pet_geometry.TRAIL_VISIBILITY_SPAN_PX
        for trail in self._trails.values():
            if len(trail) < 2:
                continue
            xs = [p[0] for p in trail]
            ys = [p[1] for p in trail]
            if max(xs) - min(xs) > span or max(ys) - min(ys) > span:
                return True
        return False

    def trail_length(self, identity):
        """Current sample count for one task (bounded)."""
        return len(self._trails.get(identity) or ())

    def ensure_geometry(self):
        """Cover the virtual desktop; apply only when changed."""
        rects = [s.availableGeometry() for s in QApplication.screens()]
        if not rects:
            return
        left = min(r.left() for r in rects)
        top = min(r.top() for r in rects)
        right = max(r.right() for r in rects)
        bottom = max(r.bottom() for r in rects)
        if (self.x() != left or self.y() != top
                or self.width() != right - left + 1
                or self.height() != bottom - top + 1):
            self.setGeometry(left, top, right - left + 1,
                             bottom - top + 1)

    def show_behind_stars(self):
        """Show (once) stacked below sibling task windows."""
        if not self.isVisible():
            self.show()
            self._lowered = False
        if not self._lowered:
            try:
                self.lower()
            except Exception:
                pass
            self._lowered = True

    def paintEvent(self, event):
        if not self.has_trails():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        origin = (self.x(), self.y())
        for trail in self._trails.values():
            points = [(x - origin[0], y - origin[1], t)
                      for x, y, t in trail]
            if len(points) < 2:
                continue
            count = len(points) - 1
            for index in range(count):
                fraction = (index + 1) / count
                painter.setPen(_trail_pen(fraction))
                painter.drawLine(points[index][0], points[index][1],
                                 points[index + 1][0], points[index + 1][1])
