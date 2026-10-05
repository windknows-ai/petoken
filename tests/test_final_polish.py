"""Final V1.1 polish: free edge/corner resize (P1) and Settings About section (P2)."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QPoint, QEvent, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from pet import DesktopPet
from widget import HUB_SIZE, PANEL_DEFAULT, PANEL_MAX, PANEL_MIN, Panel, Settings

ZH_ABOUT = [
    ("关于数据", None),
    ("1. 费用估算", "显示的是 API 等价费用估算，不代表 ChatGPT / Codex 或 Claude 订阅的实际扣费。"),
    ("2. Token 统计", "数据来自本地可读取的 Codex 和 Claude Code 记录。缓存、Context 等根据现有记录计算；缺失记录时，结果可能只是部分统计，且不包含工具调用费用。"),
    ("3. 模型与推理强度", "模型和 reasoning 通常以会话首次记录的配置为准。通过启动器或会话中途修改的设置，不一定会被完整记录。"),
    ("4. 状态与隐私", "状态优先级：Codex / Claude Code 工作 ＞ 麦克风 ＞ 音乐 ＞ 打字 ＞ 待机。浮窗会跟随桌宠展开。Petoken 不保存你输入的按键内容，也不会持久化保存媒体字幕内容。"),
]
EN_ABOUT = [
    ("About the Data", None),
    ("1. Cost Estimate", "The displayed cost is an API-equivalent estimate and does not represent your actual ChatGPT, Codex or Claude subscription charge."),
    ("2. Token Usage", "Usage is calculated from readable local Codex and Claude Code records. Cache and context values are derived from available data; missing records may result in partial totals, and tool-call costs are not included."),
    ("3. Model & Reasoning", "Model and reasoning values usually follow the first configuration recorded for the session. Launcher-side or mid-session changes may not always be fully captured."),
    ("4. Status & Privacy", "Status priority: Codex / Claude Code Working ＞ Microphone ＞ Music ＞ Typing ＞ Idle. The panel opens beside the desktop pet. Petoken never stores keystroke content or persistently saves media subtitle text."),
]


class FinalPolishTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.pref_dir = Path(self.temp.name)
        self.pref_patch = patch('widget.PREF_DIR', self.pref_dir)
        self.pref_patch.start()
        self.panels = []

    def tearDown(self):
        for panel in self.panels:
            panel.tray.hide()
            if panel.analytics_window:
                panel.analytics_window.close()
            if hasattr(panel, 'pet'):
                panel.pet.close()
            panel.closing = True
            panel.close()
            panel.deleteLater()
        self.app.processEvents()
        self.pref_patch.stop()
        self.temp.cleanup()

    def make_panel(self, prefs=None):
        if prefs is not None:
            (self.pref_dir / 'settings.json').write_text(json.dumps(prefs), encoding='utf-8')
        panel = Panel(live=False)
        self.panels.append(panel)
        return panel

    def edge_point(self, panel, edge):
        w, h = panel.width(), panel.height()
        return {'left': QPoint(2, h // 2), 'right': QPoint(w - 2, h // 2),
                'top': QPoint(w // 2, 2), 'bottom': QPoint(w // 2, h - 2),
                'topleft': QPoint(2, 2), 'bottomright': QPoint(w - 2, h - 2)}[edge]

    def edge_drag(self, panel, edge, delta):
        start = self.edge_point(panel, edge)
        panel.mousePressEvent(QMouseEvent(QEvent.MouseButtonPress, start,
            panel.mapToGlobal(start), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
        moved = start + delta
        panel.mouseMoveEvent(QMouseEvent(QEvent.MouseMove, moved,
            panel.mapToGlobal(moved), Qt.NoButton, Qt.LeftButton, Qt.NoModifier))
        panel.mouseReleaseEvent(QMouseEvent(QEvent.MouseButtonRelease, moved,
            panel.mapToGlobal(moved), Qt.LeftButton, Qt.NoButton, Qt.NoModifier))
        self.app.processEvents()

    # -- P1: fixed overview ---------------------------------------------------------

    def test_hub_does_not_install_edge_resize_handlers(self):
        panel = self.make_panel()
        self.assertFalse(hasattr(panel, '_resize_hit'))
        self.assertFalse(hasattr(panel, '_edge_resize'))
        self.assertEqual(panel.minimumSize(), panel.maximumSize())

    def test_width_ignores_resize_both_directions(self):
        panel = self.make_panel({'panel_size': [500, 500]})
        panel.show()
        for edge in ('left', 'right', 'top', 'bottom', 'topleft', 'bottomright'):
            self.edge_drag(panel, edge, QPoint(120, 120))
            self.assertEqual(panel.size().toTuple(), HUB_SIZE)
        panel.persist()
        self.assertEqual(self.make_panel().size().toTuple(), HUB_SIZE)

    def test_height_ignores_resize_both_directions(self):
        panel = self.make_panel({'panel_size': [500, 500]})
        panel.show()
        for edge in ('left', 'right', 'top', 'bottom', 'topleft', 'bottomright'):
            self.edge_drag(panel, edge, QPoint(120, 120))
            self.assertEqual(panel.size().toTuple(), HUB_SIZE)
        panel.persist()
        self.assertEqual(self.make_panel().size().toTuple(), HUB_SIZE)

    def test_minimum_size_stays_fixed(self):
        panel = self.make_panel({'panel_size': [500, 500]})
        panel.show()
        for edge in ('left', 'right', 'top', 'bottom', 'topleft', 'bottomright'):
            self.edge_drag(panel, edge, QPoint(120, 120))
            self.assertEqual(panel.size().toTuple(), HUB_SIZE)
        panel.persist()
        self.assertEqual(self.make_panel().size().toTuple(), HUB_SIZE)

    def test_maximum_size_stays_fixed(self):
        panel = self.make_panel({'panel_size': [500, 500]})
        panel.show()
        for edge in ('left', 'right', 'top', 'bottom', 'topleft', 'bottomright'):
            self.edge_drag(panel, edge, QPoint(120, 120))
            self.assertEqual(panel.size().toTuple(), HUB_SIZE)
        panel.persist()
        self.assertEqual(self.make_panel().size().toTuple(), HUB_SIZE)

    def test_custom_size_persists_across_restart(self):
        panel = self.make_panel({'panel_size': [500, 500]})
        panel.show()
        for edge in ('left', 'right', 'top', 'bottom', 'topleft', 'bottomright'):
            self.edge_drag(panel, edge, QPoint(120, 120))
            self.assertEqual(panel.size().toTuple(), HUB_SIZE)
        panel.persist()
        self.assertEqual(self.make_panel().size().toTuple(), HUB_SIZE)

    def test_compact_expand_restores_both_dimensions(self):
        panel = self.make_panel({'panel_size': [520, 700]})
        panel.show()
        self.app.processEvents()
        panel.toggle_compact()
        panel.toggle_compact()
        self.app.processEvents()
        self.assertEqual((panel.width(), panel.height()), HUB_SIZE)

    def test_repeated_cycles_preserve_size(self):
        panel = self.make_panel({'panel_size': [520, 700]})
        panel.show()
        for _ in range(3):
            panel.toggle_compact()
            panel.toggle_compact()
            self.app.processEvents()
            self.assertEqual((panel.width(), panel.height()), HUB_SIZE)

    def test_compact_ignores_edge_resize(self):
        panel = self.make_panel()
        panel.show()
        panel.toggle_compact()
        before = (panel.width(), panel.height())
        self.edge_drag(panel, 'bottomright', QPoint(100, 100))
        self.assertEqual((panel.width(), panel.height()), before)
        self.assertFalse(hasattr(panel, '_edge_resize'))

    def test_resizing_panel_never_moves_pet(self):
        panel = self.make_panel({'panel_size': [500, 500]})
        pet = DesktopPet(panel)
        panel.pet = pet
        pet.activity_timer.stop()
        pet.show()
        panel.show()
        self.app.processEvents()
        pet.show_panel()
        self.app.processEvents()
        original = pet.pos()
        for edge, delta in (('right', QPoint(60, 0)), ('bottom', QPoint(0, 60)),
                            ('left', QPoint(-40, 0)), ('top', QPoint(0, -40)),
                            ('topleft', QPoint(-30, -30))):
            self.edge_drag(panel, edge, delta)
            self.assertEqual(pet.pos(), original, edge)
        panel.hide()

    # -- P2: About section ---------------------------------------------------------

    def check_about(self, language, expected):
        panel = self.make_panel({'language': language})
        settings = Settings(panel)
        try:
            settings.show()
            self.app.processEvents()
            self.assertEqual(settings.about_heading.text(), expected[0][0])
            self.assertEqual(len(settings.about_titles), 4)
            self.assertEqual(len(settings.about_bodies), 4)
            for index, (title, body) in enumerate(expected[1:], start=1):
                self.assertEqual(settings.about_titles[index - 1].text(), title)
                self.assertEqual(settings.about_bodies[index - 1].text(), body)
                self.assertTrue(settings.about_titles[index - 1].isVisibleTo(settings))
                self.assertTrue(settings.about_bodies[index - 1].isVisibleTo(settings))
        finally:
            settings.deleteLater()

    def test_zh_information_section(self):
        self.check_about('zh_CN', ZH_ABOUT)

    def test_en_information_section(self):
        self.check_about('en', EN_ABOUT)

    def test_reset_and_save_leave_about_section_intact(self):
        panel = self.make_panel({'language': 'en'})
        settings = Settings(panel)
        try:
            settings.reset_button.click()
            settings.reset_button.click()
            self.assertEqual(settings.about_heading.text(), 'About the Data')
            settings.save()
        finally:
            settings.deleteLater()
        self.assertEqual(panel.prefs['language'], 'en')
        check = Settings(panel)
        try:
            self.assertEqual(check.about_heading.text(), 'About the Data')
        finally:
            check.deleteLater()


if __name__ == '__main__':
    unittest.main()
