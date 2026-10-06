"""Settings > Her poses (2.0): every pose she has, and when it appears.

Many poses only show in particular moments (late at night, after a long
break, when a goal is nearly used up), so some people would never see
them. The guide lists them all by group with a picture, a name, what
brings it on, and a Show me button that plays it right away.
"""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
                               QVBoxLayout, QWidget)

import pet_assets as assets
import theme
from localization import text

# Groups, each with its poses in the order they are most often seen.
GROUPS = (
    ('ai', ('idle', 'typing', 'codex_working', 'curious', 'thinking', 'celebrate', 'thumbs_up', 'surprised',
            'wave', 'sad', 'music', 'guitar', 'microphone')),
    ('touch', ('poked', 'pout', 'headpat_happy', 'shy', 'coquettish', 'dragged', 'landing')),
    ('mood', ('greet_morning', 'bored', 'peek', 'yawn', 'greet_night', 'sleep', 'wake_stretch', 'hug')),
    ('focus', ('cheer', 'focus_read', 'stretch_break', 'focus_tea', 'focus_done')),
    ('projects', ('ready_go', 'hold_card', 'packing', 'heart', 'clap', 'worried', 'grievance', 'proud')),
)


def pose_count():
    return sum(len(states) for _group, states in GROUPS)


def thumbnail(state, side):
    """The pose's first picture, scaled for the guide."""
    pixmap = None
    if assets.frame_count(state):
        pixmap = assets.frame_for(state, 0)
    if pixmap is None:
        pixmap = assets.sprite_for(state)
    return pixmap.scaled(QSize(side, side), Qt.KeepAspectRatio, Qt.SmoothTransformation) if pixmap else None


class PoseGuide(QDialog):
    def __init__(self, parent, panel):
        super().__init__(parent)
        self.panel = panel
        language = self.language = panel.prefs.get('language')
        self.setWindowTitle(text('pose_guide_title', language))
        self.resize(720, 720)
        layout = QVBoxLayout(self)
        intro = QLabel(text('pose_guide_intro', language, count=pose_count()))
        intro.setWordWrap(True)
        intro.setObjectName('muted')
        layout.addWidget(intro)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        body = QWidget()
        column = QVBoxLayout(body)
        column.setContentsMargins(0, 0, 8, 0)
        column.setSpacing(10)
        self.show_buttons = {}
        for group, states in GROUPS:
            title = QLabel(text(f'pose_group_{group}', language))
            title.setStyleSheet(f'font-size:14px; font-weight:600; color:{theme.VIOLET}; padding-top:6px;')
            column.addWidget(title)
            grid = QGridLayout()
            grid.setHorizontalSpacing(10)
            grid.setVerticalSpacing(10)
            for index, state in enumerate(states):
                grid.addWidget(self._card(state), index // 2, index % 2)
            column.addLayout(grid)
        column.addStretch()
        body.setObjectName('poseBody')
        body.setStyleSheet('QWidget#poseBody { background:transparent; }')
        scroll.setWidget(body)
        scroll.setStyleSheet('QScrollArea { background:transparent; border:0; }')
        scroll.viewport().setAutoFillBackground(False)
        layout.addWidget(scroll, 1)
        row = QHBoxLayout()
        row.addStretch()
        close = QPushButton(text('focus_card_close', language))
        close.clicked.connect(self.accept)
        row.addWidget(close)
        layout.addLayout(row)

    def _card(self, state):
        language = self.language
        card = QFrame()
        card.setObjectName('poseCard')
        card.setStyleSheet(f'QFrame#poseCard {{ background:{theme.CONTROL_BG}; border:1px solid {theme.BORDER_SOFT};'
                           ' border-radius:10px; }')
        row = QHBoxLayout(card)
        row.setContentsMargins(8, 8, 10, 8)
        row.setSpacing(10)
        picture = QLabel()
        picture.setFixedSize(72, 72)
        picture.setAlignment(Qt.AlignCenter)
        image = thumbnail(state, 72)
        if image is not None:
            picture.setPixmap(image)
        row.addWidget(picture)
        words = QVBoxLayout()
        words.setSpacing(2)
        name = QLabel(text(f'pose_name_{state}', language))
        name.setStyleSheet('font-weight:600;')
        when = QLabel(text(f'pose_when_{state}', language))
        when.setWordWrap(True)
        when.setStyleSheet(f'color:{theme.MUTED}; font-size:11px;')
        words.addWidget(name)
        words.addWidget(when, 1)
        show = QPushButton(text('pose_show', language))
        show.setCursor(Qt.PointingHandCursor)
        show.clicked.connect(lambda _=False, s=state: self.demo(s))
        self.show_buttons[state] = show
        words.addWidget(show, 0, Qt.AlignLeft)
        row.addLayout(words, 1)
        return card

    def demo(self, state):
        pet = getattr(self.panel, 'pet', None)
        if pet is not None:
            pet.demo_pose(state)
