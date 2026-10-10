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


def probe_size(ffmpeg, path):
    """(width, height) of a recording, read from ffmpeg's banner."""
    import re
    info = subprocess.run([ffmpeg, '-hide_banner', '-i', str(path)], capture_output=True, text=True,
                          errors='replace').stderr
    found = re.search(r'Video:.*?(\d{2,5})x(\d{2,5})', info)
    return (int(found.group(1)), int(found.group(2))) if found else None


class Decoder:
    """Frames of a recording as QImages, in order, scaled to ``size`` (w, h)."""

    def __init__(self, ffmpeg, path, size, fps=30, start=0.0, crop=None):
        self.size = size
        self.frame_bytes = size[0] * size[1] * 3
        cut = f'crop={crop[0]}:{crop[1]},' if crop else ''     # Centred.
        self.proc = subprocess.Popen(
            [ffmpeg, '-loglevel', 'error', '-ss', f'{start:.2f}', '-i', str(path), '-vf',
             f'fps={fps},{cut}scale={size[0]}:{size[1]}:flags=lanczos', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
             '-'], stdout=subprocess.PIPE)
        self.last = None

    def next(self):
        """The next frame; the last one again once the recording has ended."""
        data = self.proc.stdout.read(self.frame_bytes) if self.proc else b''
        if len(data) == self.frame_bytes:
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
