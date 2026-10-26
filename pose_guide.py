"""Workbench > Guide (2.0): her clinginess levels and every pose she has.

Many poses only show in particular moments (late at night, after a long
break, when a goal is nearly used up), so some people would never see
them. The guide first explains the three clinginess levels in detail (and
switches between them), then lists every pose by group with a picture, a
name, what brings it on, and a Show me button that plays it right away.
"""
from __future__ import annotations

import threading

import shiboken6
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
                               QVBoxLayout, QWidget)

import pet_assets as assets
import theme
from localization import text

LEVELS = ('quiet', 'moderate', 'clingy')
# Groups, each with its poses in the order they are most often seen.
GROUPS = (
    ('ai', ('idle', 'typing', 'codex_working', 'curious', 'thinking', 'celebrate', 'thumbs_up', 'surprised',
            'wave', 'sad', 'music', 'guitar', 'microphone')),
    ('touch', ('poked', 'pout', 'headpat_happy', 'shy', 'coquettish', 'dragged', 'landing')),
    ('mood', ('greet_morning', 'bored', 'peek', 'yawn', 'greet_night', 'sleep', 'wake_stretch', 'hug')),
    ('focus', ('cheer', 'focus_read', 'stretch_break', 'focus_tea', 'focus_done')),
    ('projects', ('ready_go', 'hold_card', 'packing', 'heart', 'clap', 'worried', 'grievance', 'proud')),
    # 2.1 game mode: the transformation, then her second form.
    ('game', ('transform', 'form2_idle', 'game_watch', 'game_tense', 'game_cheer', 'game_drink', 'game_bored',
              'game_victory', 'game_defeat')),
    # 2.3 late-night mode: the pajama change, then her night poses.
    ('night', ('night_change', 'night_idle', 'night_yawn', 'night_milk', 'night_read', 'night_goodnight',
               'night_sleep', 'night_wake')),
    # 2.4 Starsea (1000 stardust): the awakening, then her third form.
    ('starsea', ('awaken', 'star_idle', 'star_typing', 'star_thinking', 'star_celebrate', 'star_wave', 'star_sad',
                 'star_headpat', 'star_poked', 'star_dragged', 'star_sleep')),
)
# Cards that are not a pose: their button does something else.
SPECIAL = {'transform': 'xform_weapon_2', 'night_change': 'night_change_2', 'awaken': 'awaken_3'}


def pose_count():
    return sum(len(states) for _group, states in GROUPS)


def thumbnail(state, side):
    """The pose's first picture, scaled for the guide."""
    pixmap = None
    if state in ('night_change', 'awaken'):
        pixmap = assets.sprite_for(SPECIAL[state])
        return pixmap.scaled(QSize(side, side), Qt.KeepAspectRatio, Qt.SmoothTransformation) if pixmap else None
    if state in SPECIAL:
        state = SPECIAL[state]
        import transform
        folder = transform.art_dir()
        if folder is not None:
            from PySide6.QtGui import QPixmap
            pixmap = QPixmap(str(folder / f'{state}.png'))
            if not pixmap.isNull():
                return pixmap.scaled(QSize(side, side), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        return None
    if assets.frame_count(state):
        pixmap = assets.frame_for(state, 0)
    if pixmap is None:
        pixmap = assets.sprite_for(state)
    return pixmap.scaled(QSize(side, side), Qt.KeepAspectRatio, Qt.SmoothTransformation) if pixmap else None


_THUMBS = {}                  # state -> its picture for the guide, kept across rebuilds.


def thumbnail_file(state):
    """The file of an ordinary pose's first picture (read off the main thread), or None."""
    if state in SPECIAL:
        return None
    try:
        entry = assets.entry_for(state)
        frames = assets.existing_frames(entry)
        for path in (frames[0] if frames else None, entry.path, entry.fallback):   # Exists, not loaded.
            if path and assets._file(path).is_file():
                return str(assets._file(path))
        return None
    except Exception:
        return None


def _card_frame(name):
    card = QFrame()
    card.setObjectName(name)
    card.setStyleSheet(f'QFrame#{name} {{ background:{theme.CONTROL_BG}; border:1px solid {theme.BORDER_SOFT};'
                       ' border-radius:10px; }')
    return card


class GuidePage(QWidget):
    thumbReady = Signal(str, QImage)

    def __init__(self, panel):
        super().__init__()
        self.panel = panel
        self._waiting = {}                                 # state -> its picture label
        self.thumbReady.connect(self._thumb_ready)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)
        self.intro = QLabel()
        self.intro.setWordWrap(True)
        self.intro.setObjectName('muted')
        layout.addWidget(self.intro)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet('QScrollArea { background:transparent; border:0; }')
        scroll.viewport().setAutoFillBackground(False)
        self.body = QWidget()
        self.body.setObjectName('guideBody')
        self.body.setStyleSheet('QWidget#guideBody { background:transparent; }')
        self.column = QVBoxLayout(self.body)
        self.column.setContentsMargins(0, 0, 8, 0)
        self.column.setSpacing(10)
        scroll.setWidget(self.body)
        layout.addWidget(scroll, 1)
        self.show_buttons = {}
        self.level_buttons = {}
        self.built_language = None

    @property
    def language(self):
        return self.panel.prefs.get('language')

    def apply_language(self):
        self.intro.setText(text('pose_guide_intro', self.language, count=pose_count()))
        if self.built_language != self.language:
            self.build()
        self.refresh()

    def _title(self, key):
        title = QLabel(text(key, self.language))
        title.setStyleSheet(f'font-size:14px; font-weight:600; color:{theme.VIOLET}; padding-top:6px;')
        return title

    def build(self):
        while self.column.count():
            item = self.column.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
            elif item.layout() is not None:
                self._clear(item.layout())
        self.show_buttons, self.level_buttons = {}, {}
        self._waiting = {}
        language = self.language
        # The three clinginess levels, in detail.
        self.column.addWidget(self._title('guide_levels_title'))
        note = QLabel(text('guide_levels_intro', language))
        note.setWordWrap(True)
        note.setStyleSheet(f'color:{theme.MUTED}; font-size:12px;')
        self.column.addWidget(note)
        levels = QHBoxLayout()
        levels.setSpacing(10)
        self.level_cards = {}
        for level in LEVELS:
            card = _card_frame('levelCard')
            box = QVBoxLayout(card)
            box.setContentsMargins(12, 10, 12, 10)
            box.setSpacing(6)
            name = QLabel(text(f'clinginess_{level}', language))
            name.setStyleSheet('font-size:14px; font-weight:600;')
            box.addWidget(name)
            body = QLabel(text(f'guide_level_{level}', language))
            body.setWordWrap(True)
            body.setTextFormat(Qt.PlainText)
            body.setStyleSheet('font-size:12px;')
            box.addWidget(body, 1)
            choose = QPushButton()
            choose.setCursor(Qt.PointingHandCursor)
            choose.clicked.connect(lambda _=False, value=level: self.choose(value))
            self.level_buttons[level] = choose
            box.addWidget(choose)
            self.level_cards[level] = card
            levels.addWidget(card, 1)
        self.column.addLayout(levels)
        common = QLabel(text('guide_levels_common', language))
        common.setWordWrap(True)
        common.setStyleSheet(f'color:{theme.MUTED}; font-size:11px;')
        self.column.addWidget(common)
        # Every pose, by group.
        for group, states in GROUPS:
            self.column.addWidget(self._title(f'pose_group_{group}'))
            grid = QGridLayout()
            grid.setHorizontalSpacing(10)
            grid.setVerticalSpacing(10)
            for index, state in enumerate(states):
                grid.addWidget(self._pose_card(state), index // 2, index % 2)
            self.column.addLayout(grid)
        self.column.addStretch()
        self.built_language = language
        self._load_thumbs()

    def _load_thumbs(self):
        """Read the waiting pictures in a worker (full-size art takes a while to decode), so the
        page opens at once and its pictures arrive a moment later."""
        jobs = [(state, thumbnail_file(state)) for state in self._waiting]
        jobs = [(state, path) for state, path in jobs if path]
        if not jobs:
            return
        side = 72 * 2                                      # Sharp on a 200% screen.

        def work():
            for state, path in jobs:
                image = QImage(path)
                if image.isNull():
                    continue
                image = image.scaled(side, side, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                if not shiboken6.isValid(self):             # The workbench closed meanwhile.
                    return
                try:
                    self.thumbReady.emit(state, image)
                except (RuntimeError, TypeError):
                    return
        threading.Thread(target=work, name='petoken-guide-thumbs', daemon=True).start()

    def _thumb_ready(self, state, image):
        pixmap = QPixmap.fromImage(image)
        pixmap.setDevicePixelRatio(2.0)
        _THUMBS[state] = pixmap
        label = self._waiting.pop(state, None)
        if label is not None and shiboken6.isValid(label):
            label.setPixmap(pixmap)

    def _clear(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget() is not None:
                item.widget().setParent(None)
                item.widget().deleteLater()
            elif item.layout() is not None:
                self._clear(item.layout())

    def _pose_card(self, state):
        language = self.language
        card = _card_frame('poseCard')
        row = QHBoxLayout(card)
        row.setContentsMargins(8, 8, 10, 8)
        row.setSpacing(10)
        picture = QLabel()
        picture.setFixedSize(72, 72)
        picture.setAlignment(Qt.AlignCenter)
        if state in _THUMBS:
            picture.setPixmap(_THUMBS[state])
        elif thumbnail_file(state):
            self._waiting[state] = picture                  # Filled in by _load_thumbs.
        else:
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
        show = QPushButton(text('pose_show_transform' if state == 'transform' else 'pose_show', language))
        show.setCursor(Qt.PointingHandCursor)
        show.clicked.connect(lambda _=False, s=state: self.demo(s))
        self.show_buttons[state] = show
        words.addWidget(show, 0, Qt.AlignLeft)
        row.addLayout(words, 1)
        return card

    def refresh(self):
        """Mark the level in use."""
        current = self.panel.prefs.get('clinginess', 'moderate')
        for level, button in self.level_buttons.items():
            active = level == current
            button.setText(text('guide_level_current' if active else 'guide_level_use', self.language))
            button.setEnabled(not active)
            button.setObjectName('primary' if not active else '')
            button.style().unpolish(button)
            button.style().polish(button)
            self.level_cards[level].setStyleSheet(
                f'QFrame#levelCard {{ background:{theme.CONTROL_BG}; border:{2 if active else 1}px solid '
                f'{theme.VIOLET if active else theme.BORDER_SOFT}; border-radius:10px; }}')

    def choose(self, level):
        self.panel.prefs['clinginess'] = level
        pet = getattr(self.panel, 'pet', None)
        if pet is not None and hasattr(pet, 'mood'):
            pet.mood.set_clinginess(level)
        try:
            self.panel.persist()
        except Exception:
            pass
        self.refresh()

    def demo(self, state):
        if state == 'transform':
            # Watch it for real: game mode by hand (the right-click menu or the tray turns it off).
            mode = getattr(self.panel, 'game_mode', None)
            if mode is not None and not mode.active:
                mode.toggle()
            return
        pet = getattr(self.panel, 'pet', None)
        if state == 'awaken':
            # Into Starsea, a moment in it, and back (her chosen form returns after).
            from starsea import awaken_steps
            if pet is not None:
                pet.play_change(awaken_steps(True) + (('star_idle', 2.0),) + awaken_steps(False))
            return
        if state == 'night_change':
            # Into the pajamas, a moment in them, and back out.
            from night_mode import CHANGE_OFF, CHANGE_ON
            if pet is not None:
                pet.play_change(CHANGE_ON + (('night_idle', 2.5),) + CHANGE_OFF)
            return
        if pet is not None:
            pet.demo_pose(state)
