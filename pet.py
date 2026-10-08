"""Transparent character desktop pet; click to reveal the existing dashboard."""
import math
import time
from collections import OrderedDict
from datetime import datetime
from PySide6.QtCore import Qt,QTimer,QPoint,QPointF,QRectF,QSize
from PySide6.QtGui import (QColor,QImage,QPainter,QPainterPath,QPixmap,QFont,QFontMetrics,QPen,
                           QKeySequence,QShortcut)
from PySide6.QtWidgets import QWidget,QApplication,QMenu
from localization import text
from providers import PROVIDER_NAMES, PROVIDER_REGISTRY
import pet_assets as assets
import pet_geometry as geometry
import pet_motion as motion
from pet_mood import Mood, fullscreen_now, input_idle_seconds
import halo_geometry
import theme
from token_format import format_tokens
from usage_overlay import UsageOverlay, UsagePresence, build_sections


POKES_TO_POUT=5        # Clicks on her within POKE_WINDOW_S seconds.
PAT_FLIPS=5            # Direction changes of a head rub...
PAT_WINDOW_S=2.5       # ...within this long...
PAT_HOLD_S=.9          # ...kept up at least this long...
PAT_STROKE=12          # ...each stroke this many px (at 100% size).
POKE_WINDOW_S=4
POUT_S=2.4            # Each further click while pouting restarts this.


class DesktopPet(QWidget):
    def __init__(self,panel):
        super().__init__()
        self.panel=panel
        flags=Qt.Tool|Qt.FramelessWindowHint
        if panel.prefs.get('always_on_top',True):
            flags|=Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        # 100% is the approved V1.1 size; the user setting only scales it.
        self.pet_scale = geometry.normalize_pet_scale(
            panel.prefs.get('pet_scale_percent', geometry.PET_SCALE_DEFAULT))
        self.setFixedSize(*geometry.scaled_window_size(self.pet_scale))
        # Full-resolution sources from the central registry; paintEvent scales
        # them into the small logical sprite box each frame so high-DPI
        # screens stay sharp. Missing art can never crash the pet: unresolvable
        # states are simply absent and fall back to the idle source.
        self.sprites={k:v for k,v in assets.load_sprites().items() if v is not None}
        self.sprite=self.sprites.get('idle',QPixmap())
        self._render_cache=OrderedDict()
        self._render_dpr=None
        self.current_state='idle'
        self.preview_state=None
        # V1.6: a short pose after a notification (finished, failed, waiting).
        self.reaction_state=None
        self.reaction_until=0.0
        self.activity_timer=QTimer(self)
        self.activity_timer.timeout.connect(self.update_activity)
        self.activity_timer.start(100)
        self.phase=0
        self.reaction=0
        self.motion=panel.prefs.get('pet_motion',True)
        self.timer=QTimer(self)
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.timeout.connect(self.tick)
        self.timer.setInterval(1000//motion.FPS_CALM)
        # 2.0 animation: springs, breathing, cross-fades, frames and blinks.
        self.animator=motion.Animator(assets.frame_count, assets.has_blink, own_art=assets.has_own_art)
        self.frame=None
        self._last_tick=None
        # Interaction layer (head pat, poke, long press, drag) and mood layer.
        self.interaction_state=None
        self.interaction_until=0.0
        self.dragging=False
        self._drag_last=None
        self._drag_started=0.0
        self._pokes=[]
        self._pat_last=None
        self._pat_flips=[]
        self._pat_started=None
        self._pat_seen=0.0
        self._long_fired=False
        self.focus_tag=None
        self.long_press=QTimer(self)
        self.long_press.setSingleShot(True)
        self.long_press.setInterval(700)
        self.long_press.timeout.connect(self._long_pressed)
        self.setMouseTracking(True)
        # Mood follows the real clock and input, so only the live app has one:
        # tests and previews stay on their exact states.
        self.mood=Mood(panel.prefs.get('clinginess'), greeted_day=panel.prefs.get('mood_greeted_day'))
        self.mood_enabled=bool(getattr(panel,'live',False))
        self._mood_next=0.0
        self.snapshot={}
        self.working_context=None
        self.pressed=None
        screen=QApplication.primaryScreen().availableGeometry()
        position=panel.prefs.get('pet_position')
        width,height=geometry.window_size()
        default=QPoint(screen.right()-width+1-geometry.MARGIN_RIGHT,
                       screen.bottom()-height+1-geometry.MARGIN_BOTTOM)
        self.move_clamped(QPoint(*position) if isinstance(position,list) and len(position)==2 else default)
        for name,d in [('Left',(-10,0)),('Right',(10,0)),('Up',(0,-10)),('Down',(0,10))]:
            QShortcut(QKeySequence('Alt+'+name),self,activated=lambda delta=d:self.move_clamped(self.pos()+QPoint(*delta)))
        QShortcut(QKeySequence('Return'),self,activated=self.toggle_panel)
        QShortcut(QKeySequence('Space'),self,activated=self.toggle_panel)
        # While tasks run, a separate click-through card above the head
        # shows what is left of context and quotas for each open app.
        self.presence=UsagePresence()
        if getattr(panel,'live',False):
            self.presence.start()
        # Created on first use: most pets never enter Token Mode.
        self.usage_overlay=None
        # 2.1 game mode: the ring behind her, the compact display, her place.
        self.game_halo=None
        self.game_usage=None
        self.game_place=None
        self.game_drag=None
        self.veiled=False           # True while the transformation draws her instead.
        self.transform_stage=None
        self.apply_language()

    def tr_text(self,key,**values):
        return text(key,self.panel.prefs.get('language'),**values)

    def _px(self, logical):
        """Scale one logical pixel value by the user character size."""
        return max(1, round(logical * self.pet_scale / 100))

    def apply_pet_scale(self, percent):
        """Resize the visible character around its feet anchor.

        The anchor's screen position is preserved so the pet never teleports;
        the panel re-docks to the new bounds. Returns True when resized.
        """
        percent = geometry.normalize_pet_scale(percent)
        if percent == self.pet_scale:
            return False
        anchor_global = self.pos() + QPoint(*geometry.scaled_anchor(self.pet_scale))
        self.pet_scale = percent
        self.setFixedSize(*geometry.scaled_window_size(percent))
        self._render_cache.clear()
        self.move_clamped(anchor_global - QPoint(*geometry.scaled_anchor(percent)))
        if self.panel.isVisible():
            self.panel.anchor_to_pet()
        self.update()
        return True

    def typing_phase(self):
        monitor=getattr(self.panel,'activity',None)
        return getattr(getattr(monitor,'state',None),'tap_phase',0)

    def music_subtitle(self):
        """Verified media text for the Music state, or None.

        Memory-only, never translated, never persisted. Shown only when Music
        is the visible state; Token Mode and higher priorities take precedence
        by construction (the token card branch runs first).
        """
        if self.token_bubble_visible() or self.current_state!='music':
            return None
        monitor=getattr(self.panel,'activity',None)
        info=(getattr(monitor,'status',None) or {}).get('music_text') or {}
        line=info.get('text')
        return line.strip() if isinstance(line,str) and line.strip() else None

    def focus_subtitle(self):
        """Focus countdown pill, e.g. 'Focus 18:42'; None when not focusing."""
        mode=getattr(self.panel,'focus_mode',None)
        if mode is None or mode.phase=='idle':
            return None
        from focus_mode import clock_text
        if mode.phase=='focus' and mode.todo_title:
            return self.tr_text('focus_pill_todo',time=clock_text(mode.remaining()),todo=mode.todo_title)
        key={'focus':'focus_pill','break':'focus_pill_break','focus_over':'focus_pill_over'}.get(mode.phase,'focus_pill_break_over')
        return self.tr_text(key,time=clock_text(mode.remaining()))

    def apply_language(self):
        self.setWindowTitle(self.tr_text('pet_title'))
        self.setAccessibleName(self.tr_text('pet_accessible'))
        if self.snapshot:
            self.update_data(self.snapshot)
        else:
            self.setToolTip(self.tr_text('pet_tooltip_actions'))
        self.update()

    def tick(self):
        now=time.monotonic()
        dt=.05 if self._last_tick is None else min(.1,max(0.,now-self._last_tick))
        self._last_tick=now
        self.phase+=dt*1.5
        self.reaction=max(0,self.reaction-dt)
        self.animator.set_state(self.current_state,now)
        self.frame=self.animator.step(now)
        # 60 fps while something moves quickly, 30 for calm breathing.
        interval=1000//(motion.FPS_LIVELY if self.frame.lively else motion.FPS_CALM)
        if self.timer.interval()!=interval:
            self.timer.setInterval(interval)
        self.update()

    def showEvent(self,event):
        import transform
        if transform.available():
            # Ready before the first game, at her size and her corner size.
            from game_mode import CORNER_SCALE
            transform.CACHE.get(self._transform_side())
            transform.CACHE.get(self._transform_side(max(50,round(self.pet_scale*CORNER_SCALE/100))))
        if self.motion:
            self._last_tick=None
            self.timer.start()

    def hideEvent(self,event):
        self.timer.stop()
        if self.focus_tag is not None:
            self.focus_tag.hide()
        if self.usage_overlay is not None:
            self.usage_overlay.hide()
        for widget in (self.game_halo,self.game_usage):
            if widget is not None:
                widget.hide()

    def usage_overlay_wanted(self):
        """Always while an AI works; when idle too if the user keeps it on (the default).
        Never in game mode: the compact display replaces it."""
        return (self.isVisible() and not self.game_active() and self.transform_stage is None
                and (self.token_bubble_visible() or self.usage_card_idle()))

    def game_active(self):
        mode=getattr(self.panel,'game_mode',None)
        return bool(mode and mode.active)

    def enter_game(self):
        """Game mode starts: corner and click-through if needed, the ring behind
        her, the compact display."""
        from game_mode import GameHalo, GameUsage, Placement
        if self.game_place is None:
            self.game_place=Placement(self)
        self.game_place.enter(getattr(self.panel.game_mode,'monitor',None))
        from game_mode import LongPressDrag
        if self.game_drag is None:
            self.game_drag=LongPressDrag(self)
        self.game_drag.start()
        if self.game_halo is None:
            self.game_halo=GameHalo(self)
        if self.game_usage is None:
            self.game_usage=GameUsage(self)
        self._load_form2()
        played=self._play_transform(leaving=False)
        self.sync_game()
        if played and self.game_halo is not None and self.transform_stage is not None:
            stage=self.transform_stage
            self.game_halo.intro=stage._ring_intro(*stage.timeline.at(stage.t))
        self.update_activity()
        # Seconds until the ring flies in behind her (stars join it then).
        if played and self.transform_stage is not None:
            stage=self.transform_stage
            return max(0.0,stage.timeline.until('ring')-stage.t)/stage.speed
        return 0.0

    # Game moods: (pose, weight, seconds). Mostly she stands guard; now and then
    # she watches closely, gets tense, cheers, sips, or twirls her sword.
    GAME_MOODS=(('game_watch',5,9),('game_tense',2,5),('game_cheer',2,4),('game_drink',2,6),('game_bored',2,6))

    def _game_pose(self,now):
        import random
        pose,until=getattr(self,'_game_mood',(None,0.0))
        if pose is not None and now<until:
            return pose
        if pose is not None or not hasattr(self,'_game_next'):
            # Between moods: her second-form idle for 40-90 s.
            self._game_mood=(None,0.0)
            self._game_next=now+random.uniform(40,90)
        elif now>=self._game_next:
            choices=[m for m in self.GAME_MOODS if assets.has_own_art(m[0])]
            if choices:
                name,_,seconds=random.choices(choices,weights=[m[1] for m in choices])[0]
                self._game_mood=(name,now+seconds)
                return name
            self._game_next=now+60
        return 'form2_idle' if 'form2_idle' in self.sprites else 'idle'

    def _transform_side(self,scale=None):
        sx,sy,sw,sh=geometry.scaled_sprite_rect(scale or self.pet_scale)
        dpr=self.devicePixelRatioF() or 1.0
        return min(768,max(128,round(sw*dpr)))

    def _load_form2(self):
        """Her second form's pose: form2_idle once it exists, else the finished armour."""
        import transform
        if assets.has_own_art('form2_idle') or not transform.available():
            return
        path=transform.art_dir()/f'{transform.FORM2}.png'
        pixmap=QPixmap(str(path))
        if not pixmap.isNull():
            self.sprites['form2_idle']=pixmap

    def _play_transform(self,leaving):
        """Start the transformation (or its reverse); False when it can't play now."""
        import transform
        if not transform.available() or not self.isVisible():
            return False
        pieces=transform.CACHE.get(self._transform_side())
        if pieces is None:
            return False        # Being prepared (first time): this switch is immediate.
        level=None
        if self.transform_stage is not None:
            old=self.transform_stage
            level=old.timeline.level_at(old.t)      # Carry on from where she is now.
            self.transform_stage=None
            old.timer.stop()
            old.close()
            old.deleteLater()
        idle=None
        source=self.sprites.get('idle')     # The rise starts, and the reverse ends, on her idle pose.
        if source is not None and not source.isNull():
            idle=source.toImage().scaled(pieces.side,pieces.side,Qt.IgnoreAspectRatio,
                                         Qt.SmoothTransformation).convertToFormat(QImage.Format_ARGB32_Premultiplied)
        speed=2.0 if self.panel.prefs.get('game_fast') else 1.0
        stage=transform.TransformStage(self,pieces,leaving=leaving,speed=speed,idle=idle)
        if level is not None:
            stage.t=stage.timeline.time_for(level)
        self.transform_stage=stage
        self.veiled=True
        self.update()

        def done():
            if self.transform_stage is not stage:
                return          # Replaced by a newer switch.
            self.veiled=False
            self.transform_stage=None
            stage.close()
            stage.deleteLater()
            if self.game_halo is not None:
                self.game_halo.intro=1.0
                self.game_halo.flare=0.0
            if leaving:
                self._finish_leave()
            self.update_activity()
            # Straight to the pose she ends in: no cross-fade from the pose
            # she had before the transformation (it flashed for a moment).
            self.animator.cut(self.current_state,time.monotonic())
            self.update()
        stage.finished.connect(done)
        stage.start()
        return True

    def leave_game(self):
        """Game mode ends: back to her own place and size, the armour comes off,
        then clicks reach her again. She can still be long-pressed and dragged
        while it plays."""
        if self.game_usage is not None:
            self.game_usage.hide()
        if self.game_place is not None:
            self.game_place.leave_place()
        if self.isVisible() and self._play_transform(leaving=True):
            return      # The rest happens when the armour has come off.
        self._finish_leave()

    def _finish_leave(self):
        for widget in (self.game_halo,self.game_usage):
            if widget is not None:
                widget.hide()
        if self.game_drag is not None:
            self.game_drag.stop()
        if self.game_place is not None:
            self.game_place.leave_input()
        self.update_activity()

    def sync_game(self):
        """Once a second in game mode: the ring's stars and the compact display."""
        mode=getattr(self.panel,'game_mode',None)
        if not (mode and mode.active and self.isVisible()):
            for widget in (self.game_halo,self.game_usage):
                if widget is not None and widget.isVisible():
                    widget.hide()
            return
        universe=getattr(getattr(self.panel,'task_manager',None),'_universe',None) or {}
        stars=[(task or {}).get('provider_id') for task in universe.values()]
        halo=self.game_halo
        if halo is not None:
            # "Always deep space": the ring without task stars.
            halo.set_stars(stars if mode.ring_style=='tasks' else [],space=True)
            halo.follow()
            if not halo.isVisible():
                halo.show()
                self.raise_()
        usage=self.game_usage
        if usage is None:
            return
        if mode.display=='hidden' or self.transform_stage is not None:
            usage.hide()        # Not while she transforms.
            return
        sections=build_sections(self.panel,self.presence,idle=True)
        stats=None
        items=mode.bar_items
        if mode.display=='bar' and any(i!='limits' for i in items):
            if self.panel.stats_sampler is None:
                from system_stats import StatsSampler
                self.panel.stats_sampler=StatsSampler(
                    lambda: bool(self.game_active() and mode.display=='bar'))
                self.panel.stats_sampler.start()
            stats=self.panel.stats_sampler.latest
        usage.set_content(mode.display,sections,stats,items,self.panel.prefs.get('language'))
        if not usage.isVisible():
            usage.show()

    def usage_card_idle(self):
        return bool(self.panel.prefs.get('usage_card_idle',True))

    def toggle_usage_card_idle(self,enabled):
        self.panel.prefs['usage_card_idle']=bool(enabled)
        self.panel.persist()
        self.sync_usage_overlay()

    def usage_overlay_visible(self):
        return self.usage_overlay is not None and self.usage_overlay.isVisible()

    def sync_usage_overlay(self):
        """Show, refresh or hide the usage card to match Token Mode."""
        sections=(build_sections(self.panel,self.presence,idle=not self.token_bubble_visible())
                  if self.usage_overlay_wanted() else [])
        if not sections:
            if self.usage_overlay_visible():
                self.usage_overlay.hide()
            return
        if self.usage_overlay is None:
            self.usage_overlay=UsageOverlay(self)
        overlay=self.usage_overlay
        on_top=bool(self.panel.prefs.get('always_on_top',True))
        if bool(overlay.windowFlags() & Qt.WindowStaysOnTopHint)!=on_top:
            overlay.setWindowFlag(Qt.WindowStaysOnTopHint,on_top)
        overlay.set_sections(sections)
        if not overlay.isVisible():
            overlay.show()

    def _workarea_changed(self, *_):
        self.move_clamped(self.pos())

    def closeEvent(self, event):
        self.presence.stop()
        if self.usage_overlay is not None:
            self.usage_overlay.close()
            self.usage_overlay.deleteLater()
            self.usage_overlay=None
        if self.focus_tag is not None:
            self.focus_tag.close()
            self.focus_tag.deleteLater()
            self.focus_tag=None
        for name in ('game_halo','game_usage'):
            widget=getattr(self,name)
            if widget is not None:
                widget.close()
                widget.deleteLater()
                setattr(self,name,None)
        screen = getattr(self, '_halo_screen', None)
        if screen is not None:
            try:
                screen.availableGeometryChanged.disconnect(self._workarea_changed)
            except (RuntimeError, TypeError):
                pass
            self._halo_screen = None
        super().closeEvent(event)

    def update_activity(self):
        monitor=getattr(self.panel,'activity',None)
        codex_working=getattr(self.panel,'app_mode',None)
        now=time.monotonic()
        # Opening usage is an overlay, not a pose: keep the same live companion.
        if self.reaction_state and now>=self.reaction_until:
            self.reaction_state=None
        if self.interaction_state and not self.dragging and now>=self.interaction_until:
            self.interaction_state=None
        task=(monitor.state.state(codex_working=bool(codex_working and codex_working.is_token))
              if monitor else 'idle')
        gaming=self.game_active()
        if self.mood_enabled and not gaming and now>=self._mood_next:
            self._mood_next=now+1
            self.update_mood(now,task)
        focus=getattr(getattr(self.panel,'focus_mode',None),'phase','idle')
        focus_pose={'focus':'focus_read','break':'focus_tea','focus_over':'focus_done','break_over':'stretch_break'}.get(focus)
        if task=='music' and int(time.time()//120)%2:
            task='guitar'   # Every other two minutes of music she plays along.
        # Game mode: her game pose (form 2 once its art exists); tasks and moods wait.
        game_pose=self._game_pose(now) if gaming else None
        # Being dragged > notification > preview > interaction > game > focus > task > mood.
        state=(('dragged' if self.dragging and 'dragged' in self.sprites else None)
               or self.reaction_state or self.preview_state or self.interaction_state
               or game_pose
               or (focus_pose if focus_pose in self.sprites else None)
               or (task if task!='idle' else None)
               or (self.mood.pose if self.mood_enabled and self.mood.pose in self.sprites else None)
               or 'idle')
        if state!=self.current_state:
            self.current_state=state
            self.update()
        if self.usage_overlay_wanted()!=self.usage_overlay_visible():
            self.sync_usage_overlay()
        self.sync_focus_tag()

    def update_data(self,data):
        if (data or {}).get('provider_id', 'codex') not in PROVIDER_REGISTRY:
            return
        self.snapshot=data
        # An explicitly absent working_context retires the previous
        # live context at once: hysteresis may preserve animation
        # timing, never a false Working label or stale token data.
        self.working_context=(data or {}).get('working_context') or None
        if (self.working_context or {}).get('provider_id', 'codex') not in PROVIDER_REGISTRY:
            self.working_context = None
        context=self.working_context or data
        t=context.get('tokens',{})
        style=self.panel.prefs.get('token_number_format')
        # The provider is read from the context itself only: a retained
        # context is always self-described, and a missing one never
        # inherits the new panel payload's provider.
        provider = (context or {}).get('provider_id')
        total_text=format_tokens(t.get('total_tokens'),style)
        in_text=format_tokens(t.get('input_tokens'),style)
        out_text=format_tokens(t.get('output_tokens'),style)
        provider_line=(PROVIDER_NAMES[provider] + ' · ') if provider in PROVIDER_NAMES else ''
        title=context.get('title') or self.tr_text(
            'claude_working' if provider == 'claude' else 'codex_working')
        project=context.get('project') or self.tr_text('project_unavailable')
        self.setToolTip(provider_line+f"{project} · {title}\n{context.get('model') or '—'} · {context.get('effort') or '—'}\n"+
                       self.tr_text('pet_tooltip_tokens',total=total_text,
                           input=in_text,output=out_text)+
                       '\n'+self.tr_text('pet_tooltip_actions'))
        self.update()

    def update_mood(self,now,task):
        from notifications import quiet_now
        focusing=getattr(getattr(self.panel,'focus_mode',None),'phase','idle')!='idle'
        self.mood.update(now,datetime.now(),input_idle_seconds(),busy=task!='idle' or focusing,
                         quiet=quiet_now(self.panel.prefs),fullscreen=fullscreen_now())
        if self.mood.greeted_day and self.mood.greeted_day!=self.panel.prefs.get('mood_greeted_day'):
            self.panel.prefs['mood_greeted_day']=self.mood.greeted_day
            self.panel.persist()

    def demo_pose(self,pose,seconds=3.5):
        """Show ``pose`` now for a few seconds (the pose guide's Show me)."""
        token=object()
        self._demo=token
        self.preview_state=pose
        self.update_activity()

        def done():
            if getattr(self,'_demo',None) is token:
                self.preview_state=None
                self.update_activity()
        QTimer.singleShot(int(seconds*1000),done)

    def interact(self,pose,seconds):
        """Show an interaction pose for a moment; she notices you."""
        now=time.monotonic()
        if self.mood_enabled:
            self.mood.interacted(now)
        if pose in self.sprites:
            self.interaction_state=pose
            self.interaction_until=now+seconds
        self.update_activity()

    REACTIONS={'finished':('celebrate',6),'failed':('sad',8),'needs_approval':('wave',12),
               'quota_low':('sad',6),'reminder':('wave',8),'forecast':('wave',8),
               'context_full':('wave',8),'stuck':('sad',6),'quota_back':('celebrate',6),
               'question':('thinking',12)}

    def react(self,kind,event=None):
        """Play the pose for a notification for a few seconds.

        A finished task: surprised when it took under a minute, otherwise
        cheering and a thumbs-up take turns.
        """
        pose,seconds=self.REACTIONS.get(kind,(None,0))
        if kind=='finished':
            from notifications import parse_recap
            took=(parse_recap((event or {}).get('detail')) or {}).get('seconds')
            if isinstance(took,(int,float)) and took<60:
                pose='surprised'
            else:
                turn=getattr(self,'_finish_turn',False)
                pose='thumbs_up' if turn else 'celebrate'
                self._finish_turn=not turn
        if pose is None or pose not in self.sprites:
            return
        self.reaction_state=pose
        self.reaction_until=time.monotonic()+seconds
        self.reaction=1.0
        self.update_activity()

    def token_bubble_visible(self):
        mode=getattr(self.panel,'app_mode',None)
        return bool(mode and mode.is_token)

    def paintEvent(self,event):
        if self.veiled:
            return      # The transformation (transform.py) draws her right now.
        p=QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        bubble=QColor(theme.CARD)
        bubble.setAlpha(235)
        if (subtitle:=self.music_subtitle()) is not None:
            # One small secondary pill in the idle card area. No text means no
            # box at all; Token Mode never reaches this branch.
            p.setFont(QFont('Segoe UI',self._px(8)))
            shown=p.fontMetrics().elidedText(subtitle,Qt.ElideRight,self._px(208))
            pill_w=min(self._px(232),p.fontMetrics().horizontalAdvance(shown)+self._px(24))
            pill_x=(self.width()-pill_w)/2
            pill_y, pill_h, pill_r = self._px(16), self._px(26), self._px(13)
            p.setPen(QPen(QColor(theme.BORDER),1))
            p.setBrush(bubble)
            p.drawRoundedRect(QRectF(pill_x,pill_y,pill_w,pill_h),pill_r,pill_r)
            p.setPen(QColor(theme.INK))
            p.drawText(QRectF(pill_x,pill_y,pill_w,pill_h),Qt.AlignCenter,shown)
        if self.motion and self.frame is not None:
            self.paint_animated(p,self.frame)
            return
        bob_amp, typing_amp = geometry.scaled_amplitudes(self.pet_scale)
        offset=math.sin(self.phase)*bob_amp if self.motion else 0
        p.save()
        if self.reaction:
            px,py=geometry.scaled_reaction_pivot(self.pet_scale)
            p.translate(px,py);p.rotate(math.sin(self.phase*3)*self.reaction*4);p.translate(-px,-py)
        sprite=self.sprites.get(self.current_state,self.sprite)
        # Every state shares one logical sprite box around one feet anchor;
        # only approved-asset pixels change between states, never the geometry.
        tap_shift=0
        if self.current_state=='typing' and self.motion:
            framed=assets.frame_for('typing',self.typing_phase())
            if framed is not None:
                sprite=framed
            else:
                # Fallback tap until approved V1.1 frames exist: tiny alternating
                # tilt around the feet anchor plus a small lateral shift. The
                # source art is never modified; motion stays inside the box.
                tilt=1.2 if self.typing_phase() else -1.2
                tap_shift=self._px(2) if self.typing_phase() else -self._px(2)
                ax,ay=geometry.scaled_anchor(self.pet_scale)
                p.translate(ax,ay);p.rotate(tilt);p.translate(-ax,-ay)
                offset+=math.sin(self.phase*8)*typing_amp
        sx,sy,sw,sh=geometry.scaled_sprite_rect(self.pet_scale,round(offset))
        if sprite is not None and not sprite.isNull():
            rendered=self.render_sprite(sprite)
            size=rendered.deviceIndependentSize()
            dpr=self.devicePixelRatioF()
            x=round((sx+(sw-size.width())/2+tap_shift)*dpr)/dpr
            y=round((sy+sh-size.height())*dpr)/dpr
            p.drawPixmap(QPointF(x,y),rendered)
        p.restore()

    def sync_focus_tag(self):
        """The countdown window above her head (created on first focus)."""
        if self.focus_tag is None:
            if self.focus_subtitle() is None:
                return
            from focus_mode import FocusTag
            self.focus_tag=FocusTag(self)
        self.focus_tag.sync()

    def pose_pixmap(self,state,index=0,blink=False):
        """The image for one pose frame: blink, frame, then the still pose."""
        if blink:
            closed=assets.blink_for(state)
            if closed is not None:
                return closed
        if state=='typing':
            index=self.typing_count()
        if assets.frame_count(state):
            framed=assets.frame_for(state,index)
            if framed is not None:
                return framed
        return self.sprites.get(state,self.sprite)

    def typing_count(self):
        monitor=getattr(self.panel,'activity',None)
        return getattr(getattr(monitor,'state',None),'tap_count',self.typing_phase())

    def paint_animated(self,p,f):
        sx,sy,sw,sh=geometry.scaled_sprite_rect(self.pet_scale)
        scale=self.pet_scale/100
        feet_x,feet_y=sx+sw/2,sy+sh
        p.save()
        p.translate(0,-f.lift*scale)
        px,py=sx+f.pivot[0]*sw,sy+f.pivot[1]*sh
        p.translate(px,py);p.rotate(f.angle);p.translate(-px,-py)
        p.translate(feet_x,feet_y);p.scale(f.scale_x,f.scale_y);p.translate(-feet_x,-feet_y)

        def layer(pixmap,opacity):
            if pixmap is None or pixmap.isNull() or opacity<=0.01:
                return
            rendered=self.render_sprite(pixmap)
            size=rendered.deviceIndependentSize()
            p.setOpacity(min(1.,opacity))
            p.drawPixmap(QPointF(sx+(sw-size.width())/2,sy+sh-size.height()),rendered)

        if f.previous:
            # The new pose is solid at once; only the old pose's edges that
            # stick out fade away, so there is never a see-through double.
            layer(self.pose_pixmap(f.previous,f.previous_index),1-f.fade)
        layer(self.pose_pixmap(f.state,f.index,f.blink),1.)
        if f.next_index is not None and f.state!='typing':
            layer(self.pose_pixmap(f.state,f.next_index),f.next_alpha)
        p.setOpacity(1.)
        # Symbols drawn by code stand in for art that does not exist yet; a
        # pose with its own picture (hearts, bubbles) needs no second set.
        if not assets.has_own_art(f.state) or f.state in assets.registered_states():
            for particle in f.particles:
                self.paint_particle(p,particle,sx,sy,sw)
        p.restore()

    PARTICLE_COLORS={'heart':'#FF6F9F','sparkle':'#FFD36E','note':'#9B8CFF','z':'#A9B8FF',
                     'sweat':'#7FD3FF','question':'#8F7CFF'}

    def paint_particle(self,p,part,sx,sy,sw):
        size=part.size*sw
        if part.alpha<=.02 or size<2:
            return
        cx,cy=sx+part.x*sw,sy+part.y*sw
        path=QPainterPath()
        if part.kind=='heart':
            path.moveTo(0,.35)
            path.cubicTo(-.55,-.05,-.45,-.55,0,-.22)
            path.cubicTo(.45,-.55,.55,-.05,0,.35)
        elif part.kind=='sparkle':
            path.moveTo(0,-.5)
            for x,y in ((.12,-.12),(.5,0),(.12,.12),(0,.5),(-.12,.12),(-.5,0),(-.12,-.12)):
                path.lineTo(x,y)
            path.closeSubpath()
        elif part.kind=='sweat':
            path.moveTo(0,-.5)
            path.cubicTo(.32,-.05,.36,.4,0,.42)
            path.cubicTo(-.36,.4,-.32,-.05,0,-.5)
        else:
            glyph={'note':'\u266a','z':'Z','question':'?'}.get(part.kind,'?')
            font=QFont('Segoe UI',64,QFont.Bold)
            path.addText(0,0,font,glyph)
            box=path.boundingRect()
            side=max(box.width(),box.height()) or 1
            path.translate(-box.center().x(),-box.center().y())
            p.save()
            p.translate(cx,cy);p.rotate(part.angle);p.scale(size/side,size/side)
            p.setOpacity(part.alpha)
            p.setPen(QPen(QColor(255,255,255,220),side*.09))
            p.setBrush(QColor(self.PARTICLE_COLORS.get(part.kind,'#8F7CFF')))
            p.drawPath(path)
            p.restore()
            return
        p.save()
        p.translate(cx,cy);p.rotate(part.angle);p.scale(size,size)
        p.setOpacity(part.alpha)
        p.setPen(QPen(QColor(255,255,255,220),.07))
        p.setBrush(QColor(self.PARTICLE_COLORS.get(part.kind,'#FF6F9F')))
        p.drawPath(path)
        p.restore()

    def render_sprite(self, sprite):
        # Resample the original once at the actual screen density, never a
        # thumbnail or a previous DPR's scaled image. Preserve alpha and ratio.
        # The target is the user-scaled sprite box, so every state scales
        # identically regardless of source dimensions.
        dpr=self.devicePixelRatioF()
        if self._render_dpr!=dpr:
            self._render_cache.clear()
            self._render_dpr=dpr
        key=(sprite.cacheKey(),self.pet_scale)
        if key not in self._render_cache:
            side=geometry.scaled_sprite_rect(self.pet_scale)[2]
            target=QSize(geometry.device_pixels(side,dpr),
                         geometry.device_pixels(side,dpr))
            result=sprite.scaled(target,Qt.KeepAspectRatio,Qt.SmoothTransformation)
            result.setDevicePixelRatio(dpr)
            self._render_cache[key]=result
            while len(self._render_cache)>64:
                self._render_cache.popitem(last=False)
        else:
            self._render_cache.move_to_end(key)
        return self._render_cache[key]

    def moveEvent(self,event):
        super().moveEvent(event)
        if self.usage_overlay_visible():
            self.usage_overlay.follow()
        if self.focus_tag is not None and self.focus_tag.isVisible():
            self.focus_tag.follow()
        if self.panel.isVisible():
            self.panel.anchor_to_pet()
        manager = getattr(self.panel, 'task_manager', None)
        if manager is not None and getattr(self.panel, 'pet', None) is self:
            manager.anchor_changed(transport=getattr(self, '_anchor_transporting', False))

    def box_fraction(self,point):
        """A widget point as a fraction of the sprite box."""
        sx,sy,sw,sh=geometry.scaled_sprite_rect(self.pet_scale)
        return ((point.x()-sx)/sw,(point.y()-sy)/sh)

    def mousePressEvent(self,event):
        if event.button()==Qt.LeftButton:
            self.pressed=event.globalPosition().toPoint()
            self.original=self.pos()
            self._press_local=event.position()
            self._long_fired=False
            if self.motion:
                self.long_press.start()

    def mouseMoveEvent(self,event):
        if self.pressed is not None and event.buttons() & Qt.LeftButton:
            if self._long_fired:
                return   # Holding her to be cute: this press never turns into a drag.
            point=event.globalPosition().toPoint()
            self.move_clamped(self.original+point-self.pressed)
            now=time.monotonic()
            if not self.dragging and (point-self.pressed).manhattanLength()>=5:
                self.long_press.stop()
                self.dragging=True
                self._drag_started=now
                self._drag_last=(point.x(),now)
                self.animator.start_drag(self.box_fraction(self._press_local))
                self.interact('dragged',1)
            elif self.dragging and self._drag_last is not None:
                last_x,last_t=self._drag_last
                if now-last_t>1e-3:
                    self.animator.drag((point.x()-last_x)/(now-last_t)/(self.pet_scale/100))
                    self._drag_last=(point.x(),now)
        elif not event.buttons():
            self.track_pat(event.position())

    def mouseReleaseEvent(self,event):
        if event.button()==Qt.LeftButton and self.pressed is not None:
            self.long_press.stop()
            moved=(event.globalPosition().toPoint()-self.pressed).manhattanLength()
            self.pressed=None
            if self._long_fired:
                return
            now=time.monotonic()
            if self.dragging:
                self.dragging=False
                self.animator.end_drag()
                self.interact('landing',.7)
            if self._long_fired:
                return
            if moved<5:
                local=getattr(self,'_press_local',None)
                side=(self.box_fraction(local)[0]-.5)*2 if local is not None else 0
                self.animator.poke(max(-1.,min(1.,side)))
                # Only clicking her again and again on purpose makes her pout,
                # and more clicks while she pouts keep her pouting.
                self._pokes=[t for t in self._pokes if now-t<POKE_WINDOW_S]+[now]
                pouting=self.interaction_state=='pout' and now<self.interaction_until
                if pouting or len(self._pokes)>=POKES_TO_POUT:
                    self.interact('pout',POUT_S)
                else:
                    self.interact('poked',.45)
                # A left click is for her; the panel opens from the right-click menu.
            else:
                self.panel.prefs['pet_position']=[self.x(),self.y()]
                self.panel.persist()

    def _long_pressed(self):
        """Held without moving: she acts cute instead of opening the panel."""
        if self.pressed is None or self.dragging:
            return
        self._long_fired=True
        self.animator.hop(90)
        self.interact('coquettish',3.5)

    def track_pat(self,point):
        """Rubbing back and forth over the head is a head pat.

        Deliberate only: PAT_FLIPS turns within PAT_WINDOW_S seconds, each
        stroke at least PAT_STROKE px long, kept up for PAT_HOLD_S seconds.
        Passing over her head on the way somewhere never counts.
        """
        fx,fy=self.box_fraction(point)
        now=time.monotonic()
        if not (.18<=fx<=.82 and 0<=fy<=.38):
            self._pat_last=None
            return
        x=point.x()
        if self._pat_last is not None:
            last_x,last_t,direction,stroke_from=self._pat_last
            dx=x-last_x
            if now-last_t>.4:
                direction,stroke_from=0,x
            elif abs(dx)>=2:
                turn=1 if dx>0 else -1
                if direction and turn!=direction:
                    if abs(last_x-stroke_from)>=self._px(PAT_STROKE):
                        self._pat_flips.append(now)
                    stroke_from=last_x
                direction=turn
            else:
                return
            self._pat_last=(x,now,direction,stroke_from)
        else:
            self._pat_last=(x,now,0,x)
        self._pat_flips=[t for t in self._pat_flips if now-t<PAT_WINDOW_S]
        if len(self._pat_flips)>=PAT_FLIPS and now-self._pat_flips[0]>=PAT_HOLD_S:
            if self._pat_started is None or now-self._pat_seen>2:
                self._pat_started=now
            self._pat_seen=now
            # Patted for a while: she gets shy.
            self.interact('shy' if now-self._pat_started>5 else 'headpat_happy',1.6)

    def leaveEvent(self,event):
        self._pat_last=None
        super().leaveEvent(event)

    def toggle_panel(self):
        if self.panel.isVisible() and not self.panel.is_pinned():
            self.panel.hide_to_tray()
        else:self.show_panel()

    def show_panel(self):
        self.panel.anchor_to_pet()
        self.panel.show();self.panel.raise_()

    def contextMenuEvent(self,event):
        menu=self.context_menu()
        try:
            menu.exec(event.globalPos())
        finally:
            menu.deleteLater()

    def context_menu(self):
        menu=QMenu(self)
        menu.setStyleSheet(self.panel.styleSheet())
        menu.setToolTipsVisible(True)
        usage=menu.addAction(self.tr_text('usage_panel'))
        usage.setCheckable(True)
        usage.setChecked(self.panel.is_pinned())
        usage.setToolTip(self.tr_text('panel_pinned_help'))
        usage.toggled.connect(self.panel.set_panel_pinned)
        card=menu.addAction(self.tr_text('usage_card_menu'))
        card.setCheckable(True)
        card.setChecked(self.usage_card_idle())
        card.setToolTip(self.tr_text('usage_card_help'))
        card.toggled.connect(self.toggle_usage_card_idle)
        mode=getattr(self.panel,'game_mode',None)
        if mode is not None:
            game=menu.addAction(self.tr_text('game_mode_menu'))
            game.setCheckable(True)
            game.setChecked(mode.active)
            game.setToolTip(self.tr_text('game_mode_menu_tip'))
            game.triggered.connect(lambda _=False,game_mode=mode: game_mode.toggle())   # Bound now: 'mode' is reused below.
        # Everyday actions on top; occasional ones and toggles under More.
        menu.addAction(self.tr_text('launch_menu'),self.panel.open_quick_launch).setToolTip(self.tr_text('menu_tip_launch'))
        mode=getattr(self.panel,'focus_mode',None)
        if mode is not None:
            from focus_mode import CHOICES, clock_text
            if mode.phase!='idle':
                note=menu.addAction(self.tr_text({'focus':'focus_menu_running','break':'focus_menu_resting',
                                                  'focus_over':'focus_menu_over'}.get(mode.phase,'focus_menu_break_over'),
                                                 time=clock_text(mode.remaining())))
                note.setEnabled(False)
            else:
                focus=menu.addMenu(self.tr_text('focus_menu'))
                focus.menuAction().setToolTip(self.tr_text('menu_tip_focus'))
                focus.setStyleSheet(self.panel.styleSheet())
                for minutes in CHOICES:
                    focus.addAction(self.tr_text('focus_minutes',minutes=minutes),
                                    lambda m=minutes:self.panel.start_focus(m))
                focus.addSeparator()
                focus.addAction(self.tr_text('focus_custom'),self.panel.open_focus_dialog)
        menu.addAction(self.tr_text('menu_workbench'),self.panel.open_workbench).setToolTip(self.tr_text('menu_tip_workbench'))
        menu.addAction(self.tr_text('wb_reports'),self.panel.open_reports).setToolTip(self.tr_text('menu_tip_reports'))
        menu.addSeparator()
        more=menu.addMenu(self.tr_text('menu_more'))
        more.setStyleSheet(self.panel.styleSheet())
        more.addAction(self.tr_text('analytics_button'),self.panel.open_analytics)
        more.addAction(self.tr_text('wb_tutorial'),self.panel.open_workbench_tutorial)
        more.addSeparator()
        topmost=more.addAction(self.tr_text('always_on_top'));topmost.setCheckable(True)
        topmost.setChecked(bool(self.panel.prefs.get('always_on_top',True)))
        topmost.triggered.connect(self.toggle_topmost)
        motion=more.addAction(self.tr_text('idle_motion'));motion.setCheckable(True);motion.setChecked(self.motion)
        motion.triggered.connect(self.toggle_motion)
        more.addAction(self.tr_text('hide_pet'),self.hide)
        menu.addAction(self.tr_text('pet_settings'),self.panel.open_settings).setToolTip(self.tr_text('menu_tip_settings'))
        menu.addSeparator();menu.addAction(self.tr_text('exit'),self.panel.shutdown)
        return menu

    def toggle_topmost(self,enabled):
        self.panel.set_always_on_top(enabled)
        self.update()

    def toggle_motion(self,enabled):
        self.motion=enabled
        self.panel.prefs['pet_motion']=enabled
        self.timer.start() if enabled and self.isVisible() else self.timer.stop()
        try:
            self.panel.task_manager.sync_motion()
        except Exception:
            pass
        self.panel.persist();self.update()

    def move_clamped(self,point):
        screen=QApplication.screenAt(point+self.rect().center()) or QApplication.primaryScreen()
        r=screen.availableGeometry()
        previous = getattr(self, '_halo_screen', None)
        if previous is not screen:
            if previous is not None:
                try:
                    previous.availableGeometryChanged.disconnect(self._workarea_changed)
                except (RuntimeError, TypeError):
                    pass
            screen.availableGeometryChanged.connect(self._workarea_changed)
            self._halo_screen = screen
        self.halo_screen_rect = (r.left(), r.top(), r.right(), r.bottom())
        self.halo_placement = halo_geometry.clamp_composition(
            (point.x(), point.y(), self.width(), self.height()),
            (r.left(), r.top(), r.right(), r.bottom()))
        x, y = self.halo_placement.pet_rect[:2]
        # Explicit drag/keyboard/position commands carry the whole composition.
        # A queued geometry observation still uses the manager's bounded glide.
        self._anchor_transporting = True
        try:
            self.move(x,y)
        finally:
            self._anchor_transporting = False
        # QWidget emits no moveEvent when resize/clamping keeps the same origin.
        manager = getattr(self.panel, 'task_manager', None)
        if manager is not None and getattr(self.panel, 'pet', None) is self:
            manager.anchor_changed(transport=True)
