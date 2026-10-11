"""Record a piece of the screen while the real app plays something (2.3 videos).

Some things only exist on screen as several windows working together: the
transformation, the star ring flying behind her, the game-mode rings. The
tutorial video records them live: a plain backdrop (tutorial_video.Stage)
covers part of the screen, the scenario runs on it, and ffmpeg's gdigrab
records that rectangle. Recordings are decoded back frame by frame
(Decoder) when the video is drawn, so they never sit in memory.
"""
from __future__ import annotations

import subprocess

from PySide6.QtCore import QRect
from PySide6.QtGui import QGuiApplication, QImage


def physical(rect):
    """A logical rectangle on the primary screen in physical pixels (even sizes)."""
    dpr = QGuiApplication.primaryScreen().devicePixelRatio()
    x, y = round(rect.x() * dpr), round(rect.y() * dpr)
    w, h = round(rect.width() * dpr) // 2 * 2, round(rect.height() * dpr) // 2 * 2
    return QRect(x, y, w, h)


class Recorder:
    """ffmpeg recording one rectangle of the screen until stop()."""

    def __init__(self, ffmpeg, rect, out, fps=30):
        box = physical(rect)
        self.size = (box.width(), box.height())
        self.out = out
        self.proc = subprocess.Popen(
            [ffmpeg, '-y', '-loglevel', 'error', '-f', 'gdigrab', '-framerate', str(fps), '-draw_mouse', '0',
             '-offset_x', str(box.x()), '-offset_y', str(box.y()),
             '-video_size', f'{box.width()}x{box.height()}', '-i', 'desktop',
             '-c:v', 'h264_nvenc', '-preset', 'p5', '-rc', 'vbr', '-cq', '17', '-b:v', '0',
             '-pix_fmt', 'yuv420p', str(out)],
            stdin=subprocess.PIPE)

    def stop(self):
        try:
            self.proc.stdin.write(b'q')
            self.proc.stdin.flush()
        except OSError:
            pass
        self.proc.wait(timeout=30)


def composite(region, skip=()):
    """The app's own windows inside ``region`` (logical, global), drawn into one
    transparent image in their real stacking order. Nothing is read off the
    screen, so the windows can be fully transparent (ghost()) while recording."""
    import ctypes
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QPainter
    from PySide6.QtWidgets import QApplication
    dpr = QGuiApplication.primaryScreen().devicePixelRatio()
    image = QImage(round(region.width() * dpr), round(region.height() * dpr), QImage.Format_ARGB32_Premultiplied)
    image.setDevicePixelRatio(dpr)
    image.fill(0)
    windows = {}
    for widget in QApplication.topLevelWidgets():
        if widget in skip or not widget.isVisible() or not widget.frameGeometry().intersects(region):
            continue
        windows[int(widget.winId())] = widget
    order = []
    user32 = ctypes.windll.user32
    user32.GetTopWindow.restype = user32.GetWindow.restype = ctypes.c_void_p
    handle = user32.GetTopWindow(None)
    while handle:
        if handle in windows:
            order.append(windows[handle])
        handle = user32.GetWindow(ctypes.c_void_p(handle), 2)          # GW_HWNDNEXT: the next one down.
    painter = QPainter(image)
    for widget in reversed(order):                                     # Bottom first.
        spot = widget.mapToGlobal(QPoint(0, 0)) - region.topLeft()
        painter.drawPixmap(spot, widget.grab())
    painter.end()
    return image


class Ghost:
    """While on, every window the app shows is fully transparent on screen:
    nothing pops up in front of the person, yet grab() still draws it."""

    def __init__(self, app):
        from PySide6.QtCore import QEvent, QObject

        class Filter(QObject):
            def eventFilter(self, obj, event):
                if event.type() == QEvent.Show and getattr(obj, 'isWindow', lambda: False)():
                    obj.setWindowOpacity(0.0)
                return False
        self.app = app
        self.filter = Filter()
        app.installEventFilter(self.filter)
        from PySide6.QtWidgets import QApplication
        for widget in QApplication.topLevelWidgets():
            widget.setWindowOpacity(0.0)

    def stop(self):
        self.app.removeEventFilter(self.filter)


class CompositeRecorder:
    """Records composite() frames of ``region`` to a video with transparency
    (QuickTime Animation), at ``fps`` in real time, until stop()."""

    def __init__(self, ffmpeg, region, out, fps=30):
        import time
        from PySide6.QtCore import QTimer
        self.region, self.fps = region, fps
        dpr = QGuiApplication.primaryScreen().devicePixelRatio()
        self.size = (round(region.width() * dpr) // 2 * 2, round(region.height() * dpr) // 2 * 2)
        self.proc = subprocess.Popen(
            [ffmpeg, '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'bgra',
             '-s', f'{self.size[0]}x{self.size[1]}', '-r', str(fps), '-i', '-', '-c:v', 'qtrle',
             '-pix_fmt', 'argb', str(out)], stdin=subprocess.PIPE)
        self.start = time.monotonic()
        self.written = 0
        self.clock = time.monotonic
        self.timer = QTimer()
        self.timer.timeout.connect(self.frame)
        self.timer.start(int(1000 / fps))

    def frame(self):
        image = composite(self.region).convertToFormat(QImage.Format_ARGB32)
        if (image.width(), image.height()) != self.size:
            image = image.copy(0, 0, *self.size)
        data = bytes(image.constBits())[:self.size[0] * self.size[1] * 4]
        due = int((self.clock() - self.start) * self.fps) + 1      # Catch up if a frame took long.
        while self.written < due:
            self.proc.stdin.write(data)
            self.written += 1

    def stop(self):
        self.timer.stop()
        self.proc.stdin.close()
        self.proc.wait(timeout=60)


def probe_size(ffmpeg, path):
    """(width, height) of a recording, read from ffmpeg's banner."""
    import re
    info = subprocess.run([ffmpeg, '-hide_banner', '-i', str(path)], capture_output=True, text=True,
                          errors='replace').stderr
    found = re.search(r'Video:.*?(\d{2,5})x(\d{2,5})', info)
    return (int(found.group(1)), int(found.group(2))) if found else None


class Decoder:
    """Frames of a recording as QImages, in order, scaled to ``size`` (w, h)."""

    def __init__(self, ffmpeg, path, size, fps=30, start=0.0, crop=None, alpha=False):
        self.size = size
        self.alpha = alpha
        self.frame_bytes = size[0] * size[1] * (4 if alpha else 3)
        cut = f'crop={crop[0]}:{crop[1]},' if crop else ''     # Centred.
        self.proc = subprocess.Popen(
            [ffmpeg, '-loglevel', 'error', '-ss', f'{start:.2f}', '-i', str(path), '-vf',
             f'fps={fps},{cut}scale={size[0]}:{size[1]}:flags=lanczos', '-f', 'rawvideo',
             '-pix_fmt', 'rgba' if alpha else 'rgb24',
             '-'], stdout=subprocess.PIPE)
        self.last = None

    def next(self):
        """The next frame; the last one again once the recording has ended."""
        data = self.proc.stdout.read(self.frame_bytes) if self.proc else b''
        if len(data) == self.frame_bytes:
            if self.alpha:
                self.last = QImage(data, self.size[0], self.size[1], self.size[0] * 4,
                                   QImage.Format_RGBA8888).copy()
            else:
                self.last = QImage(data, self.size[0], self.size[1], self.size[0] * 3, QImage.Format_RGB888).copy()
        elif self.proc is not None:
            self.close()
        return self.last

    def close(self):
        if self.proc is not None:
            self.proc.stdout.close()
            self.proc.kill()
            self.proc.wait()
            self.proc = None
