"""Finite, interruptible detail-card motion without resizing its layout."""
from __future__ import annotations

from PySide6.QtCore import (QEasingCurve, QObject, QPoint, QPointF, QRectF,
                           Qt, QVariantAnimation)
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import QWidget


DURATION_MS = 220
START_SCALE_X = 0.72
START_SCALE_Y = 0.88


def transformed_rect(card_rect, origin, progress):
    """Scale about the Star in global logical pixels, never from zero."""
    progress = max(0.0, min(1.0, float(progress)))
    sx = START_SCALE_X + (1.0 - START_SCALE_X) * progress
    sy = START_SCALE_Y + (1.0 - START_SCALE_Y) * progress
    return QRectF(origin.x() + (card_rect.x() - origin.x()) * sx,
                  origin.y() + (card_rect.y() - origin.y()) * sy,
                  card_rect.width() * sx, card_rect.height() * sy)


class _SnapshotLayer(QWidget):
    def __init__(self):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint
                         | Qt.NoDropShadowWindowHint
                         | Qt.WindowTransparentForInput)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.NoFocus)
        self.pixmap = QPixmap()
        self.card_rect = QRectF()
        self.origin = QPointF()
        self.progress = 0.0
        self.opacity = 1.0

    def prepare(self, card, origin, pixmap, opacity):
        flags = self.windowFlags()
        if card.windowFlags() & Qt.WindowStaysOnTopHint:
            flags |= Qt.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowStaysOnTopHint
        if flags != self.windowFlags():
            self.setWindowFlags(flags)
        self.pixmap = pixmap
        self.card_rect = QRectF(QPointF(card.mapToGlobal(QPoint())),
                               card.size().toSizeF())
        self.origin = origin
        self.opacity = opacity
        start = transformed_rect(self.card_rect, origin, 0.0)
        self.setGeometry(start.united(self.card_rect).adjusted(-2, -2, 2, 2)
                         .toAlignedRect())

    def clear(self):
        self.hide()
        self.pixmap = QPixmap()

    def paintEvent(self, event):
        if self.pixmap.isNull():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.setOpacity(self.progress * self.opacity)
        target = transformed_rect(self.card_rect, self.origin, self.progress)
        target.translate(-self.x(), -self.y())
        painter.drawPixmap(target, self.pixmap, QRectF(self.pixmap.rect()))


class DetailTransition(QObject):
    """Manager-owned snapshot layer; all calls belong to the Qt GUI thread.

    ``open`` shows the real card immediately. ``close`` hides it immediately.
    Neither method activates a window or changes card geometry. Cancellation
    restores its original opacity without changing caller-owned visibility.
    The manager must cancel before retiring/replacing/hiding the detail card.
    ``animated=False`` is the reduced-motion and deterministic lifecycle path.
    """

    def __init__(self, parent=None, duration_ms=DURATION_MS):
        super().__init__(parent)
        self.animation = QVariantAnimation(self)
        self.animation.setDuration(max(1, int(duration_ms)))
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        self.overlay = None
        self.running = False
        self._generation = 0
        self._shutdown = False
        self._card = None
        self._opacity = 1.0
        self._on_finished = None
        self._connections = []

    def open(self, card, global_star_center, animated=True, on_finished=None):
        self._start(card, global_star_center, True, animated, on_finished)

    def close(self, card, global_star_center, animated=True, on_finished=None):
        self._start(card, global_star_center, False, animated, on_finished)

    def _start(self, card, center, opening, animated, callback):
        if self._shutdown:
            return
        continuing = self.running and self._card is card
        progress = self.overlay.progress if continuing else (0.0 if opening else 1.0)
        was_visible = card.isVisible()
        self.cancel()
        if isinstance(center, (QPoint, QPointF)):
            center = QPointF(center)
        else:
            center = QPointF(*center)
        if opening:
            card.setAttribute(Qt.WA_ShowWithoutActivating)
            card.show()
        if not animated or (not opening and not was_visible and not continuing):
            if not opening:
                card.hide()
            if callback is not None:
                callback()
            return

        self._card = card
        self._opacity = card.windowOpacity()
        self._on_finished = callback
        if self.overlay is None:
            self.overlay = _SnapshotLayer()
        self.overlay.prepare(card, center, card.grab(), self._opacity)
        self.overlay.progress = progress
        if opening:
            card.setWindowOpacity(0.0)
        else:
            card.hide()
        self.running = True
        generation = self._generation
        self._connections = [
            self.animation.valueChanged.connect(
                lambda value: self._frame(generation, value), Qt.DirectConnection),
            self.animation.finished.connect(
                lambda: self._finish(generation), Qt.DirectConnection),
            card.destroyed.connect(lambda: self._cancel_generation(generation)),
        ]
        self.animation.setStartValue(progress)
        self.animation.setEndValue(1.0 if opening else 0.0)
        self.overlay.show()
        self.overlay.raise_()
        self.animation.start()

    def _frame(self, generation, value):
        if generation == self._generation and self.running:
            self.overlay.progress = float(value)
            self.overlay.update()

    def _restore(self):
        if self._card is not None:
            try:
                self._card.setWindowOpacity(self._opacity)
            except RuntimeError:
                pass  # The owning manager may already have deleted the card.
        self._card = None

    def _disconnect(self):
        for connection in self._connections:
            QObject.disconnect(connection)
        self._connections.clear()

    def _finish(self, generation):
        if generation != self._generation or not self.running:
            return
        callback = self._on_finished
        self._on_finished = None
        self.running = False
        self._disconnect()
        self._restore()
        self.overlay.clear()
        if callback is not None:
            callback()

    def _cancel_generation(self, generation):
        if generation == self._generation:
            self.cancel()

    def cancel(self):
        self._generation += 1
        self.animation.stop()
        self.running = False
        self._on_finished = None
        self._disconnect()
        self._restore()
        if self.overlay is not None:
            self.overlay.clear()

    def shutdown(self):
        self._shutdown = True
        self.cancel()
        if self.overlay is not None:
            self.overlay.close()
            self.overlay.deleteLater()
            self.overlay = None
