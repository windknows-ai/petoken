"""Transparent character desktop pet; click to reveal the existing dashboard."""
import math
import time
from PySide6.QtCore import Qt,QTimer,QPoint,QPointF,QRectF,QSize
from PySide6.QtGui import QColor,QPainter,QPixmap,QFont,QFontMetrics,QPen,QKeySequence,QShortcut
from PySide6.QtWidgets import QWidget,QApplication,QMenu
from localization import text
from providers import PROVIDER_NAMES, PROVIDER_REGISTRY
import pet_assets as assets
import pet_geometry as geometry
import halo_geometry
import theme
from token_format import format_tokens
from usage_overlay import UsageOverlay, UsagePresence, build_sections


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
        self._render_cache={}
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
        self.timer.timeout.connect(self.tick)
        self.timer.setInterval(50)
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

    def apply_language(self):
        self.setWindowTitle(self.tr_text('pet_title'))
        self.setAccessibleName(self.tr_text('pet_accessible'))
        if self.snapshot:
            self.update_data(self.snapshot)
        else:
            self.setToolTip(self.tr_text('pet_tooltip_actions'))
        self.update()

    def tick(self):
        self.phase+=.075
        self.reaction=max(0,self.reaction-.05)
        self.update()

    def showEvent(self,event):
        if self.motion:self.timer.start()

    def hideEvent(self,event):
        self.timer.stop()
        if self.usage_overlay is not None:
            self.usage_overlay.hide()

    def usage_overlay_wanted(self):
        return self.token_bubble_visible() and self.isVisible()

    def usage_overlay_visible(self):
        return self.usage_overlay is not None and self.usage_overlay.isVisible()

    def sync_usage_overlay(self):
        """Show, refresh or hide the usage card to match Token Mode."""
        sections=build_sections(self.panel,self.presence) if self.usage_overlay_wanted() else []
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
        # Opening usage is an overlay, not a pose: keep the same live companion.
        if self.reaction_state and time.monotonic()>=self.reaction_until:
            self.reaction_state=None
        state=self.reaction_state or self.preview_state or (monitor.state.state(
            codex_working=bool(codex_working and codex_working.is_token)) if monitor else 'idle')
        if state!=self.current_state:
            self.current_state=state
            self.update()
        if self.usage_overlay_wanted()!=self.usage_overlay_visible():
            self.sync_usage_overlay()

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

    REACTIONS={'finished':('celebrate',6),'failed':('sad',8),'needs_approval':('wave',12),
               'quota_low':('sad',6),'reminder':('wave',8)}

    def react(self,kind):
        """Play the pose for a notification for a few seconds."""
        pose,seconds=self.REACTIONS.get(kind,(None,0))
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
        return self._render_cache[key]

    def moveEvent(self,event):
        super().moveEvent(event)
        if self.usage_overlay_visible():
            self.usage_overlay.follow()
        if self.panel.isVisible():
            self.panel.anchor_to_pet()
        manager = getattr(self.panel, 'task_manager', None)
        if manager is not None and getattr(self.panel, 'pet', None) is self:
            manager.anchor_changed(transport=getattr(self, '_anchor_transporting', False))

    def mousePressEvent(self,event):
        if event.button()==Qt.LeftButton:
            self.pressed=event.globalPosition().toPoint()
            self.original=self.pos()

    def mouseMoveEvent(self,event):
        if self.pressed is not None and event.buttons() & Qt.LeftButton:
            self.move_clamped(self.original+event.globalPosition().toPoint()-self.pressed)

    def mouseReleaseEvent(self,event):
        if event.button()==Qt.LeftButton and self.pressed is not None:
            moved=(event.globalPosition().toPoint()-self.pressed).manhattanLength()
            self.pressed=None
            if moved<5:
                self.toggle_panel()
            else:
                self.panel.prefs['pet_position']=[self.x(),self.y()]
                self.panel.persist()

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
        menu.addAction(self.tr_text('analytics_button'),self.panel.open_analytics)
        menu.addAction(self.tr_text('workbench_open'),self.panel.open_workbench)
        menu.addAction(self.tr_text('wb_tutorial'),self.panel.open_workbench_tutorial)
        menu.addAction(self.tr_text('pet_settings'),self.panel.open_settings)
        topmost=menu.addAction(self.tr_text('always_on_top'));topmost.setCheckable(True)
        topmost.setChecked(bool(self.panel.prefs.get('always_on_top',True)))
        topmost.triggered.connect(self.toggle_topmost)
        motion=menu.addAction(self.tr_text('idle_motion'));motion.setCheckable(True);motion.setChecked(self.motion)
        motion.triggered.connect(self.toggle_motion)
        menu.addAction(self.tr_text('hide_pet'),self.hide)
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
