"""Render the Petoken 2.0 tutorial video (Chinese narration and subtitles).

Usage:
    python tools/tutorial_video.py OUT_DIR --ffmpeg PATH [--minutes 6.8] [--only N] [--stills]

With --minutes there is no narration: subtitles only, scenes timed by text length.

Everything runs on synthetic data in a temporary folder (the same sandbox
as the adjustable test build): no real Claude Code or Codex data is read and
nothing is saved. The script captures the real windows, renders her real
animation, synthesizes the narration with the Windows Chinese voice
(System.Speech, Huihui), draws every frame with Qt and pipes them to
ffmpeg. The scene list lives in tools/tutorial_script.py.
"""
import argparse
import json
import math
import re
import subprocess
import sys
import tempfile
import time
import wave
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, QTimer
from PySide6.QtGui import (QColor, QFont, QFontMetrics, QGuiApplication, QImage, QLinearGradient, QPainter,
                           QPainterPath, QPen, QPixmap)
from PySide6.QtWidgets import QApplication, QWidget

from tools.tutorial_script import CHAPTERS, SCENES

W, H, FPS = 1920, 1080, 30
INK, VIOLET, MUTED = QColor('#231E56'), QColor('#483F86'), QColor('#5C5577')
BG_TOP, BG_BOTTOM = QColor('#ECE8F8'), QColor('#D6CEEE')
FONT = 'Microsoft YaHei UI'
CONTENT = QRectF(60, 118, 1230, 790)        # Where captures and her clips go.
SIDE = QRectF(1330, 118, 530, 790)          # Chapter, scene title and steps.
SUB = QRectF(60, 932, 1800, 118)            # Subtitle bar.
FADE_S = .35
PAD_S = .9                                  # Silence after each narration.
LEAD_S = .25                                # Silence before it.


def pump(seconds):
    end = time.time() + seconds
    while time.time() < end:
        QApplication.processEvents()
        time.sleep(.01)


# Capturing ------------------------------------------------------------------

class Stage(QWidget):
    """A plain backdrop behind on-screen captures, so no desktop shows."""

    def __init__(self, rect):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setGeometry(rect)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

    def paintEvent(self, event):
        p = QPainter(self)
        g = QLinearGradient(0, 0, 0, self.height())
        g.setColorAt(0, QColor('#3B3F58'))
        g.setColorAt(1, QColor('#23263A'))
        p.fillRect(self.rect(), g)


def rect_in(widget, top):
    return QRect(widget.mapTo(top, QPoint(0, 0)), widget.size())


def grab(widget):
    """The widget drawn at a resolution that stays sharp when enlarged in the video."""
    hidden = not widget.isVisible()
    if hidden:                             # Lay it out like a shown window, without showing it.
        widget.setAttribute(Qt.WA_DontShowOnScreen)
        widget.show()
        pump(.2)
    size = widget.size()
    dpr = max(1.25, min(3.0, 1500 / max(size.width(), size.height(), 1)))
    image = QImage(size * dpr, QImage.Format_ARGB32_Premultiplied)
    image.setDevicePixelRatio(dpr)
    image.fill(Qt.transparent)
    QWidget.render(widget, image)          # The usage panel has its own render().
    if hidden:
        widget.hide()
        widget.setAttribute(Qt.WA_DontShowOnScreen, False)
    return dict(image=image, dpr=dpr, marks={})


def realistic_fixtures():
    """The synthetic tasks, with names a viewer would recognise."""
    import tools.preview_v1_3 as base_module
    original = base_module.fixture_tasks
    names = ('website', 'api-server', 'petoken', 'mobile-app', 'docs', 'data-pipeline')

    def tasks(count=3, case='known', source='mixed'):
        out = original(count, case, source)
        for index, task in enumerate(out):
            task['display'] = dict(task['display'], project=names[index % len(names)])
            presentation = task['presentation']
            presentation['model'] = 'claude-opus-5-5' if task['provider_id'] == 'claude' else 'gpt-5.5'
        return out
    base_module.fixture_tasks = tasks


def seed(pv):
    """Sample todos, notes, notes for next time, goals, points and history."""
    import random
    store, panel = pv.store, pv.panel
    # Plain folder names instead of the temporary folder (which shows the Windows user name).
    for index, project in enumerate(pv.projects):
        pv.projects[index] = store.update_project(project['id'], project['name'],
                                                  'D:\\work\\' + project['name']) or dict(
            project, directory='D:\\work\\' + project['name'])
    website, petoken = pv.projects[1], pv.projects[0]
    for title in ('写首页的深色模式', '整理 README 截图'):
        store.create_todo(title, website['id'])
    store.create_note('周会记录', '下周发布 2.0：先做验收，再写发布说明。', petoken['id'])
    store.create_note('API 想法', '登录接口加上限流；错误信息改成中文。', website['id'])
    store.add_handoff(website['id'], '旧的留言：先把表单样式统一')
    store.add_handoff(website['id'], '提交按钮还没接上，下次先做它')
    store.set_goal(website['id'], weekly_tokens=50_000_000)
    store.set_goal(petoken['id'], weekly_tokens=2_000_000_000)
    now = time.time()
    for n, reason in enumerate(('todo_done', 'todo_done', 'focus_done', 'break_taken', 'todo_accepted')):
        store.add_points(reason, f'seed-{n}', {'todo_done': 2, 'focus_done': 10, 'break_taken': 3,
                                               'todo_accepted': 5}[reason], now - n * 3600)
    store.earn('first_project', now - 86400)
    store.earn('first_weekly', now - 3600)
    rng = random.Random(7)
    events, turns, history = [], [], []
    for d in range(84):
        for k in range(rng.randint(1, 6)):
            at = now - d * 86400 - rng.random() * 70000
            provider = rng.choice(('claude', 'claude', 'codex'))
            tokens = rng.randint(300_000, 9_000_000)
            project = rng.choice(('website', 'petoken', 'api-server'))
            events.append(dict(provider=provider, session=f'{provider}{d}{k}', at=at, tokens=tokens,
                               usd=tokens / 1e6 * 2.1, project=project))
            turns.append((at, at + rng.randint(300, 4000), project))
            if d < 6:
                history.append(dict(provider=provider, id=f'{provider}{d}{k}',
                                    title=rng.choice(('给登录页加上表单校验', '修复首页布局', '写单元测试',
                                                      '整理依赖', '优化图片加载')),
                                    project=project, started_at=at - 900, finished_at=at, tokens=tokens,
                                    usd=tokens / 1e6 * 2.1))
    history.sort(key=lambda row: -row['finished_at'])
    files = [(t[0], t[2], f'src/file{n % 9}.py') for n, t in enumerate(turns)]
    panel.report_cache.data = dict(events=events, history=history, missing=[],
                                   activity=dict(turns=turns, edits=files), focus=[(now - 7200, now - 5700, True)])
    for n, (kind, project) in enumerate((('finished', 'website'), ('needs_approval', 'api-server'),
                                         ('finished', 'petoken'), ('quota_low', ''), ('failed', 'website'))):
        panel.notifications.ingest(dict(kind=kind, provider='claude' if n % 2 == 0 else 'codex',
                                        task_key=f'seed-{n}', at=now - n * 1800, project=project,
                                        detail={'quota_low': '18', 'failed': 'rate_limit'}.get(kind, ''),
                                        dedupe=f'seed-{n}'), now=now - n * 1800)


def capture_all(pv, base):
    """Every still the script refers to: {name: dict(image, dpr, marks)}."""
    from workbench import QDialog  # noqa: F401  (ensures workbench is importable)
    out = {}
    panel, store = pv.panel, pv.store
    window = panel.workbench_window
    window.resize(1120, 820)
    window.apply_language()
    window.show()
    pump(.5)
    pet = base.pet
    # Right-click menu.
    menu = pet.context_menu()
    menu.popup(QPoint(200, 200))
    pump(.3)
    out['menu'] = grab(menu)
    menu.close()
    # Workbench pages.
    tabs = window.tabs

    def tab(index, name, prepare=None, marks=None):
        tabs.setCurrentIndex(index)
        window.refresh()
        if prepare:
            prepare()
        window._update_actions()
        pump(.4)
        shot = grab(window)
        for key, widget in (marks or {}).items():
            shot['marks'][key] = rect_in(widget, window)
        out[name] = shot

    pv.make_review()
    tab(0, 'wb_home')
    tab(1, 'wb_todos', lambda: window.todo_list.setCurrentRow(1), dict(todo_ai=window.todo_ai_button))
    tab(2, 'wb_notes', lambda: window.notes_list.setCurrentRow(0))

    def select_project():
        table = window.projects_table
        item = table.topLevelItem(1)
        table.setCurrentItem(item)
        item.setSelected(True)
    tab(3, 'wb_projects', select_project, dict(start_work=window.project_start_button))
    tab(4, 'wb_notify')
    window.report_page.cache.at = time.time()
    window.report_page.cache.max_age = 10 ** 9
    tab(5, 'report_board', lambda: (window.report_page.refresh(), window.report_page.show_sub(0),
                                    window.report_page.set_kind('week')))
    tab(5, 'report_analysis', lambda: (window.report_page.show_sub(1),
                                       window.report_page.analysis.range.setCurrentIndex(
                                           window.report_page.analysis.range.findData('30d'))))
    tab(window.collection_tab, 'collection')
    guide = window.guide_page
    tabs.setCurrentIndex(window.guide_tab)
    guide.apply_language()
    pump(.4)
    shot = grab(window)
    cards = list(guide.level_cards.values())
    union = rect_in(cards[0], window).united(rect_in(cards[-1], window))
    shot['marks']['levels'] = union
    out['guide_levels'] = shot
    scroll = guide.body.parentWidget().parentWidget()
    scroll.verticalScrollBar().setValue(int(scroll.verticalScrollBar().maximum() * .35))
    pump(.3)
    out['guide_poses'] = grab(window)
    # Dialogs from the workbench.
    from todo_ai import GiveToAiDialog, ReviewDialog
    from project_start import HandoffHistory, ProjectPresetDialog
    from collection_view import GoalDialog
    todos = store.list_todos()
    todo = next(t for t in todos if t['title'].endswith('写首页的深色模式'))
    with patch('quick_launch.launch_options', return_value=[
            dict(id='claude-opus-5-5', label='Opus 5.5', efforts=[('high', '高'), ('medium', '中')])]):
        dialog = GiveToAiDialog(window, panel, todo, None, [r'D:\work\website'])
        dialog.prompt.setPlainText('把首页做成支持深色模式：跟随系统，也能手动切换。')
        out['give_ai'] = grab(dialog)
        dialog.deleteLater()
        website = pv.projects[1]
        dialog = ProjectPresetDialog(window, panel, website, dict(provider_id='claude', folder=website['directory'],
                                     prompt='', model='', effort=''))
        out['preset'] = grab(dialog)
        dialog.deleteLater()
    review = next(s for s in store.list_schedules() if s['state'] == 'review')
    record = next(t for t in store.list_todos() if t['id'] == review['todo_id'])
    note = store.get_note(review['note_id']) if review.get('note_id') else None
    dialog = ReviewDialog(window, panel, record, review, note)
    out['review'] = grab(dialog)
    dialog.deleteLater()
    pv.last_task.setText('给登录页加上表单校验')
    pv.project.setCurrentIndex(1)
    pv._history()
    panel.show_continuation(pv.projects[1], store)
    pump(.3)
    out['continuation'] = grab(panel._continuation_card)
    panel._continuation_card.close()
    dialog = HandoffHistory(window, 'zh_CN', store, pv.projects[1])
    out['history'] = grab(dialog)
    dialog.deleteLater()
    dialog = GoalDialog(window, 'zh_CN', pv.projects[1], store.get_goal(pv.projects[1]['id']))
    out['goal'] = grab(dialog)
    dialog.deleteLater()
    # Focus.
    from focus_mode import FocusCard, FocusDialog
    dialog = FocusDialog(panel, store)
    dialog.setStyleSheet(panel.styleSheet())
    out['focus_dialog'] = grab(dialog)
    dialog.deleteLater()
    card = FocusCard('zh_CN', dict(start=0, end=1500, planned=1500, completed=True,
                                   todos=['写首页的深色模式', '整理 README 截图'], ai_finished=2, files=6,
                                   tokens=1_840_000, loading=False, todo_id='x', todo_title='写首页的深色模式',
                                   todo_done=False, break_min=5),
                     panel.prefs.get('token_number_format'))
    card.adjustSize()
    card.show()
    pump(.3)
    out['focus_card'] = grab(card)
    card.close()
    card.deleteLater()
    # Quick launch.
    from quick_launch import QuickLaunchDialog
    from widget import STYLE
    with patch('quick_launch.launch_options', return_value=[
            dict(id='claude-opus-5-5', label='Opus 5.5', efforts=[('high', '高')])]):
        dialog = QuickLaunchDialog(panel)
        dialog.setStyleSheet(STYLE)
        dialog.prompt.setPlainText('给登录页加上表单校验，错误信息用中文。')
        dialog.folder.clear()
        dialog.folder.addItems(['D:\\work\\website', 'D:\\work\\petoken'])
        out['quick_launch'] = grab(dialog)
        dialog.deleteLater()
    # Settings pages.
    from widget import Settings
    settings = Settings(panel)
    settings.show()
    names = ('settings_general', 'settings_tracking', 'settings_claude', 'settings_assistant', 'settings_about')
    for index, name in enumerate(names):
        settings.tabs.setCurrentIndex(index)
        pump(.3)
        shot = grab(settings)
        for key, widget in (('claude_probe', settings.claude_probe), ('dnd', settings.dnd)):
            frame = widget
            while frame is not None and frame.objectName() != 'settingCard':
                frame = frame.parentWidget()
            if frame is not None and frame.isVisible():
                shot['marks'][key] = rect_in(frame, settings)
        out[name] = shot
    settings.close()
    # Approval cards.
    import claude_approval
    from tools.preview_v1_3 import PREVIEW_REQUESTS
    controller = base.panel.approvals
    folder = Path(base._approval_dir.name)
    for name, kind in (('approval', 'command'), ('question', 'question'), ('plan', 'plan')):
        for leftover in folder.glob('*.request.json'):
            leftover.unlink()
        controller.tick()
        request_id = claude_approval.new_request_id()
        data = dict(session_id='tutorial', cwd=r'C:\work\website', hook_event_name='PermissionRequest',
                    **PREVIEW_REQUESTS[kind])
        (folder / f'{request_id}.request.json').write_text(json.dumps(data), encoding='utf-8')
        controller.tick()
        pump(.4)
        out[name] = grab(controller.card)
    for leftover in folder.glob('*.request.json'):
        leftover.unlink()
    controller.tick()
    window.hide()
    # Usage card with N/A and the sync note.
    import usage_overlay as uo
    now = time.time()
    pro = dict(planType='pro', secondary=dict(windowDurationMins=10080, usedPercent=37, resetsAt=now + 3 * 86400))
    overlay = uo.UsageOverlay(pet)
    overlay.set_sections([uo.provider_section('codex', pro, 70, '', 'zh_CN', now),
                          uo.provider_section('claude', None, 20, '', 'zh_CN', now,
                                              note='在设置里打开「同步 Claude 用量」')])
    out['card_na'] = grab(overlay)
    overlay.deleteLater()
    # On screen: the ring, the card and the panel, on a plain backdrop.
    screen = QGuiApplication.primaryScreen().availableGeometry()
    stage_rect = QRect(screen.left() + 40, screen.top() + 40, 1300, 900)
    stage = Stage(stage_rect)
    stage.show()
    base.pet.move(stage_rect.left() + 520, stage_rect.top() + 420)
    base.pet.show()
    base.pet.raise_()
    pump(3.0)
    for orb in QApplication.topLevelWidgets():
        if orb is not stage and orb.isVisible() and orb.windowFlags() & Qt.Tool and orb is not base:
            orb.raise_()
    pump(1.0)

    def shoot(name, marks):
        """The screen around her (and her card and countdown), on the backdrop."""
        region = base.pet.frameGeometry()
        for extra in QApplication.topLevelWidgets():       # Her card, star ring and countdown.
            box = extra.frameGeometry()
            if (extra is not stage and extra.isVisible() and box.intersects(stage_rect)
                    and box.width() < 900 and box.height() < 700):
                region = region.united(box)
        region = region.adjusted(-90, -60, 90, 60).intersected(stage_rect)
        image = QGuiApplication.primaryScreen().grabWindow(0, region.x(), region.y(),
                                                         region.width(), region.height()).toImage()
        shot = dict(image=image, dpr=image.devicePixelRatio() or 1.0, marks={}, underlay=False)
        for key, rect in marks.items():
            shot['marks'][key] = rect.translated(-region.x(), -region.y())
        out[name] = shot

    overlay = base.pet.usage_overlay
    base.panel.hide()
    pump(.8)
    pet_rect = base.pet.frameGeometry()
    shoot('ring', {})
    out['card'] = grab(overlay) if overlay is not None else out['ring']
    base.panel.set_panel_pinned(True)
    pump(1.0)
    out['panel'] = grab(base.panel)
    base.panel.set_panel_pinned(False)
    # Focus countdown at her feet.
    base.count.setValue(0)
    pump(1.0)
    panel_b = base.panel
    panel_b.start_focus(25, dict(id='x', title='写首页的深色模式', project_id=None))
    base.pet.interaction_state = None
    pump(1.5)
    tag = base.pet.focus_tag
    shoot('focus_tag', dict(focus_tag=tag.frameGeometry() if tag is not None else QRect()))
    panel_b.focus_mode.abandon()
    stage.close()
    base.pet.hide()
    return out


# Her animation ------------------------------------------------------------

CLIPS = {
    'idle': [('idle', 4)], 'greet_morning': [('greet_morning', 3), ('idle', 2)],
    'poked': [('poked', .9), ('idle', 1.2)], 'pout': [('poked', .5), ('poked', .5), ('pout', 3)],
    'headpat': [('headpat_happy', 3.5), ('shy', 2.5)], 'coquettish': [('coquettish', 4)],
    'mood_day': [('greet_morning', 2.8), ('bored', 3.5), ('yawn', 2.5), ('peek', 2.5)],
    'mood_sleep': [('sleep', 4), ('wake_stretch', 2.4), ('hug', 3)],
    'notify': [('celebrate', 2.4), ('thumbs_up', 2.2), ('surprised', 1.8), ('sad', 2.2)],
    'cheer': [('cheer', 2.5), ('focus_read', 4)], 'break': [('stretch_break', 2.5), ('focus_tea', 4)],
    'proud': [('proud', 4)], 'heart': [('heart', 2.5), ('clap', 2.5)],
}


class PetClip:
    """Plays poses on a hidden pet with a simulated clock, one image per frame."""

    def __init__(self, panel):
        import pet as pet_module
        from pet import DesktopPet

        class Clock:
            now = 1000.0

            @classmethod
            def monotonic(cls):
                return cls.now

            @classmethod
            def time(cls):
                return 1_700_000_000 + cls.now

            @staticmethod
            def sleep(seconds):
                pass

        self.clock = Clock
        self.module = pet_module
        self.real_time = pet_module.time
        self.pet = DesktopPet(panel)
        self.pet.activity_timer.stop()
        self.pet.timer.stop()
        self.pet.apply_pet_scale(150)
        self.pet.mood_enabled = False

    def frames(self, clip, seconds):
        """Images for ``seconds`` of ``clip`` (looping its poses)."""
        pet, clock = self.pet, self.clock
        self.module.time = clock
        try:
            pet.animator = type(pet.animator)(pet.animator.frame_count, pet.animator.has_blink,
                                              own_art=pet.animator.own_art)
            pet._last_tick = None
            pet.dragging = False
            pet.interaction_state = None
            frames = []
            total = int(seconds * FPS)
            if clip == 'drag':
                return self._drag(total)
            plan = CLIPS[clip]
            length = sum(s for _, s in plan)
            for n in range(total):
                t = (n / FPS) % length
                for pose, span in plan:
                    if t < span:
                        break
                    t -= span
                pet.preview_state = pose
                pet.update_activity()
                clock.now += 1 / FPS
                pet.tick()
                frames.append(self._image())
            return frames
        finally:
            self.module.time = self.real_time

    def _drag(self, total):
        pet, clock = self.pet, self.clock
        frames = []
        cycle = int(4.5 * FPS)
        for n in range(total):
            k = n % cycle
            if k == 0:
                pet.preview_state = None
                pet.dragging = True
                pet.animator.start_drag((.5, .25))
                pet.interact('dragged', 1)
            if k < int(2.6 * FPS):
                pet.animator.drag(1100 * math.sin(k / FPS * 4.2))
            elif k == int(2.6 * FPS):
                pet.dragging = False
                pet.animator.end_drag()
                pet.interact('landing', .9)
            elif k == int(3.6 * FPS):
                pet.interaction_state = None
            clock.now += 1 / FPS
            pet.update_activity()
            pet.tick()
            frames.append(self._image())
        return frames

    def _image(self):
        image = QImage(self.pet.size() * 2, QImage.Format_ARGB32_Premultiplied)
        image.setDevicePixelRatio(2)
        image.fill(Qt.transparent)
        self.pet.render(image)
        return image


# Narration ----------------------------------------------------------------

def narrate(lines, folder):
    """One WAV per line with the Windows Chinese voice; returns their paths."""
    folder.mkdir(parents=True, exist_ok=True)
    jobs = [dict(text=line, path=str(folder / f'{n:03d}.wav')) for n, line in enumerate(lines)]
    spec = folder / 'jobs.json'
    spec.write_text(json.dumps(jobs, ensure_ascii=False), encoding='utf-8')
    script = folder / 'speak.ps1'
    script.write_text(r'''
Add-Type -AssemblyName System.Speech
$jobs = Get-Content -Raw -Encoding UTF8 $args[0] | ConvertFrom-Json
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.SelectVoice('Microsoft Huihui Desktop')
$s.Rate = 1
foreach ($job in $jobs) {
    $format = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(24000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
    $s.SetOutputToWaveFile($job.path, $format)
    $s.Speak($job.text)
}
$s.SetOutputToNull()
$s.Dispose()
''', encoding='utf-8-sig')
    subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script), str(spec)],
                   check=True)
    return [Path(job['path']) for job in jobs]


def wav_seconds(path):
    with wave.open(str(path), 'rb') as w:
        return w.getnframes() / w.getframerate()


def join_audio(paths, durations, out):
    """All narrations back to back, each padded to its scene's length."""
    with wave.open(str(paths[0]), 'rb') as first:
        params = first.getparams()
    with wave.open(str(out), 'wb') as target:
        target.setparams(params)
        rate, width = params.framerate, params.sampwidth * params.nchannels
        for path, seconds in zip(paths, durations):
            with wave.open(str(path), 'rb') as source:
                data = source.readframes(source.getnframes())
            need = int(seconds * rate) * width
            lead = int(LEAD_S * rate) * width
            data = (b'\0' * lead + data)[:need]
            target.writeframes(data + b'\0' * (need - len(data)))


# Drawing ------------------------------------------------------------------

def font(size, bold=False):
    f = QFont(FONT)
    f.setPixelSize(size)
    if bold:
        f.setWeight(QFont.DemiBold)
    return f


def wrap(text, metrics, width):
    lines, line = [], ''
    for ch in text:
        if ch in '，。、；：！？」）' and line:     # Never start a line with punctuation.
            line += ch
        elif metrics.horizontalAdvance(line + ch) > width and line:
            lines.append(line)
            line = ch
        else:
            line += ch
    if line:
        lines.append(line)
    return lines


def chunks(text, width):
    """The narration in pieces of at most two subtitle lines, split at sentence ends."""
    metrics = QFontMetrics(font(30))
    out = []

    def add(piece):
        if out and len(wrap(out[-1] + piece, metrics, width)) <= 2:
            out[-1] += piece
        else:
            out.append(piece)
    for sentence in [s for s in re.split(r'(?<=[。；！？])', text) if s.strip()]:
        if len(wrap(sentence, metrics, width)) <= 2:
            add(sentence)
        else:                                  # One long sentence: split at commas too.
            for part in [s for s in re.split(r'(?<=[，、：])', sentence) if s]:
                add(part)
    return out or [text]


class Renderer:
    def __init__(self, stills, clips, speech):
        self.stills, self.clips = stills, clips
        self.chapter_index = {key: n for n, (key, _) in enumerate(CHAPTERS)}
        # Subtitle pieces, each shown for its share of the spoken length.
        self.captions = []
        for scene, seconds in zip(SCENES, speech):
            pieces = chunks(scene['say'], SUB.width() - 80)
            total = sum(len(piece) for piece in pieces)
            at, timed = LEAD_S, []
            for piece in pieces:
                timed.append((at, piece))
                at += seconds * len(piece) / total
            self.captions.append(timed)

    def caption(self, n_scene, t):
        text = self.captions[n_scene][0][1]
        for at, piece in self.captions[n_scene]:
            if t >= at - .15:
                text = piece
        return text

    def background(self, p):
        g = QLinearGradient(0, 0, 0, H)
        g.setColorAt(0, BG_TOP)
        g.setColorAt(1, BG_BOTTOM)
        p.fillRect(0, 0, W, H, g)

    def header(self, p, scene):
        p.setPen(VIOLET)
        p.setFont(font(26, True))
        p.drawText(QRectF(60, 34, 600, 50), Qt.AlignLeft | Qt.AlignVCenter, 'Petoken 2.0 使用说明')
        index = self.chapter_index[scene['chapter']]
        x = 1860
        for n in range(len(CHAPTERS) - 1, -1, -1):
            label = CHAPTERS[n][1]
            p.setFont(font(17, n == index))
            width = p.fontMetrics().horizontalAdvance(label) + 26
            x -= width
            rect = QRectF(x, 40, width - 6, 36)
            if n == index:
                p.setPen(Qt.NoPen)
                p.setBrush(VIOLET)
                p.drawRoundedRect(rect, 18, 18)
                p.setPen(QColor('#F6F4FC'))
            else:
                p.setPen(MUTED)
            p.drawText(rect, Qt.AlignCenter, label)

    def side(self, p, scene, n_scene):
        r = SIDE
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 150))
        p.drawRoundedRect(r, 22, 22)
        index = self.chapter_index[scene['chapter']]
        p.setPen(MUTED)
        p.setFont(font(20))
        p.drawText(QRectF(r.left() + 34, r.top() + 28, r.width() - 68, 30), Qt.AlignLeft,
                   f'第 {index + 1} 章 · {CHAPTERS[index][1]}')
        p.setPen(INK)
        p.setFont(font(40, True))
        y = r.top() + 68
        for line in wrap(scene['title'], QFontMetrics(font(40, True)), r.width() - 68):
            p.drawText(QRectF(r.left() + 34, y, r.width() - 68, 54), Qt.AlignLeft | Qt.AlignVCenter, line)
            y += 54
        y += 18
        steps = scene['steps']
        if not steps and scene['chapter'] in ('intro', 'end'):
            steps = [label for key, label in CHAPTERS if key not in ('intro', 'end')]
            scene = dict(scene, step=None)
        if steps:
            for i, step in enumerate(steps):
                active = i == scene['step']
                box = QRectF(r.left() + 26, y, r.width() - 52, 46)
                if active:
                    p.setPen(Qt.NoPen)
                    p.setBrush(VIOLET)
                    p.drawRoundedRect(box, 14, 14)
                p.setPen(QColor('#F6F4FC') if active else (INK if scene['step'] is None else MUTED))
                p.setFont(font(22, active))
                p.drawText(box.adjusted(18, 0, -10, 0), Qt.AlignLeft | Qt.AlignVCenter, f'{i + 1}. {step}')
                y += 52
                if y > r.bottom() - 60:
                    break

    def subtitle(self, p, text, alpha=1.0):
        metrics = QFontMetrics(font(30))
        lines = wrap(text, metrics, SUB.width() - 80)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(35, 30, 86, int(225 * alpha)))
        p.drawRoundedRect(SUB, 20, 20)
        p.setPen(QColor(255, 255, 255, int(255 * alpha)))
        p.setFont(font(30))
        top = SUB.center().y() - len(lines) * 21
        for i, line in enumerate(lines):
            p.drawText(QRectF(SUB.left() + 40, top + i * 42, SUB.width() - 80, 42), Qt.AlignCenter, line)

    def still(self, p, name, marks, t, duration):
        shot = self.stills[name]
        image, dpr = shot['image'], shot['dpr']
        logical_w, logical_h = image.width() / dpr, image.height() / dpr
        scale = min(CONTENT.width() / logical_w, CONTENT.height() / logical_h, 2.3)
        w, h = logical_w * scale, logical_h * scale
        x = CONTENT.center().x() - w / 2
        y = CONTENT.center().y() - h / 2
        target = QRectF(x, y, w, h)
        # Shadow and card.
        p.setPen(Qt.NoPen)
        for k in range(6):
            p.setBrush(QColor(35, 30, 86, 10))
            p.drawRoundedRect(target.adjusted(-k * 2, -k * 2 + 6, k * 2, k * 2 + 6), 18, 18)
        path = QPainterPath()
        path.addRoundedRect(target, 14, 14)
        p.save()
        p.setClipPath(path)
        if shot.get('underlay', True):      # Her windows are see-through; show them on white.
            p.fillPath(path, QColor('#F7F5FC'))
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.drawImage(target, image)
        p.restore()
        # Outline what the narration talks about.
        pulse = .7 + .3 * math.sin(t * 3.2)
        for key in marks:
            rect = shot['marks'].get(key)
            if rect is None or rect.isEmpty():
                continue
            box = QRectF(x + rect.x() * scale, y + rect.y() * scale, rect.width() * scale, rect.height() * scale)
            box = box.adjusted(-8, -8, 8, 8)
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor(240, 84, 92, int(255 * pulse)), 5))
            p.drawRoundedRect(box, 14, 14)

    def clip(self, p, frames, t):
        if not frames:
            return
        image = frames[min(len(frames) - 1, int(t * FPS))]
        glow = QRectF(CONTENT.center().x() - 330, CONTENT.center().y() - 330, 660, 660)
        g = QLinearGradient(glow.topLeft(), glow.bottomLeft())
        g.setColorAt(0, QColor(255, 255, 255, 120))
        g.setColorAt(1, QColor(255, 255, 255, 30))
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawEllipse(glow)
        logical_w = image.width() / image.devicePixelRatio()
        logical_h = image.height() / image.devicePixelRatio()
        scale = 1.75
        target = QRectF(CONTENT.center().x() - logical_w * scale / 2, CONTENT.bottom() - logical_h * scale - 10,
                        logical_w * scale, logical_h * scale)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.drawImage(target, image)

    def frame(self, n_scene, t, duration, image):
        scene = SCENES[n_scene]
        p = QPainter(image)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        self.background(p)
        self.header(p, scene)
        kind, name = scene['visual']
        if kind == 'still':
            self.still(p, name, scene['highlight'], t, duration)
        else:
            self.clip(p, self.clips[n_scene], t)
        self.side(p, scene, n_scene)
        self.subtitle(p, self.caption(n_scene, t))
        fade = min(1.0, t / FADE_S, (duration - t) / FADE_S)
        if fade < 1.0:
            p.fillRect(0, 0, W, H, QColor(236, 232, 248, int(255 * (1 - max(0.0, fade)))))
        p.end()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('out_dir', type=Path)
    parser.add_argument('--ffmpeg', required=True)
    parser.add_argument('--only', type=int, default=None, help='Render only the first N scenes (a quick check)')
    parser.add_argument('--stills', action='store_true', help='Save one still per scene and stop')
    parser.add_argument('--minutes', type=float, default=None,
                        help='No narration: subtitles only, the whole video this many minutes long')
    args = parser.parse_args(argv)
    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    scenes = SCENES[:args.only] if args.only else SCENES
    with ExitStack() as stack:
        directory = stack.enter_context(tempfile.TemporaryDirectory(prefix='petoken-tutorial-'))
        stack.enter_context(patch('widget.PREF_DIR', Path(directory)))
        stack.enter_context(patch('quick_launch.build_command', lambda *a, **k: ['tutorial']))
        stack.enter_context(patch('claude_launch.launch', lambda argv: None))
        realistic_fixtures()
        from tools.preview_v1_3 import Preview as BasePreview
        from tools.preview_v2_0 import Preview
        base = BasePreview(3, 'zh_CN')
        base.panel.connection.setText('')
        pv = Preview('zh_CN', base)
        base.hide()
        pv.hide()
        seed(pv)
        print('capturing…', flush=True)
        stills = capture_all(pv, base)
        print(f'{len(stills)} captures', flush=True)
        if args.minutes:
            # Subtitles only: each scene gets time in proportion to its text.
            weights = [len(scene['say']) + 10 for scene in scenes]
            durations = [args.minutes * 60 * w / sum(weights) for w in weights]
            speech = [d - LEAD_S - .6 for d in durations]
            wavs = None
        else:
            # Narration first: it decides how long each scene lasts.
            wavs = narrate([scene['say'] for scene in scenes], out_dir / 'voice')
            speech = [wav_seconds(w) for w in wavs]
            durations = [max(4.0, s + LEAD_S + PAD_S) for s in speech]
        print(f'length {sum(durations) / 60:.1f} min', flush=True)
        clipper = PetClip(base.panel)
        clips = {}
        for n, scene in enumerate(scenes):
            if scene['visual'][0] == 'pet':
                clips[n] = clipper.frames(scene['visual'][1], durations[n])
        renderer = Renderer(stills, clips, speech)
        if args.stills:
            for name, shot in stills.items():
                shot['image'].save(str(out_dir / f'cap_{name}.png'))
            for n, scene in enumerate(scenes):
                image = QImage(W, H, QImage.Format_RGB888)
                renderer.frame(n, min(1.5, durations[n] / 2), durations[n], image)
                image.save(str(out_dir / f'scene_{n:02d}.png'))
            finish(pv, base)
            return 0
        silent = out_dir / 'video_only.mp4'
        proc = subprocess.Popen([args.ffmpeg, '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
                                 '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-', '-c:v', 'h264_nvenc', '-preset', 'p7',
                                 # Without -g/-bf this ffmpeg build's NVENC spends ~20 Mbps on still frames.
                                 '-rc', 'vbr', '-cq', '23', '-b:v', '0', '-g', '300', '-bf', '2',
                                 '-pix_fmt', 'yuv420p',
                                 '-movflags', '+faststart', str(silent)], stdin=subprocess.PIPE)
        image = QImage(W, H, QImage.Format_RGB888)
        done = 0
        for n, duration in enumerate(durations):
            for k in range(int(duration * FPS)):
                renderer.frame(n, k / FPS, duration, image)
                proc.stdin.write(bytes(image.constBits()))
            done += 1
            print(f'scene {done}/{len(durations)}', flush=True)
        proc.stdin.close()
        proc.wait()
        final = out_dir / 'Petoken-2.0-使用说明.mp4'
        if wavs is None:
            silent.replace(final)
        else:
            audio = out_dir / 'narration.wav'
            join_audio(wavs, durations, audio)
            subprocess.run([args.ffmpeg, '-y', '-loglevel', 'error', '-i', str(silent), '-i', str(audio),
                            '-c:v', 'copy', '-c:a', 'aac', '-b:a', '128k', '-shortest', '-movflags', '+faststart',
                            str(final)], check=True)
        print('done', final, flush=True)
        finish(pv, base)
    return 0


def finish(pv, base):
    """Close the sample databases so their temporary folders can be removed."""
    for action in (base.panel.focus_mode.abandon, pv.panel.focus_mode.abandon, pv.store.close,
                   getattr(base, 'cleanup', None)):
        try:
            if action is not None:
                action()
        except Exception:
            pass


if __name__ == '__main__':
    raise SystemExit(main())
