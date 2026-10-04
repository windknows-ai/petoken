"""Transparent character desktop pet; click to reveal the existing dashboard."""
import math
import time
from PySide6.QtCore import Qt,QTimer,QPoint,QPointF,QRectF,QSize
from PySide6.QtGui import QColor,QPainter,QPixmap,QFont,QFontMetrics,QPen,QKeySequence,QShortcut,QCursor
from PySide6.QtWidgets import QWidget,QApplication,QMenu
from localization import text
import pet_assets as assets
import pet_geometry as geometry
import halo_geometry
import theme
from token_format import format_tokens


# Compact-card state marker: the status dot takes the live state's accent so
# the small card reads as part of the companion, not a plain data pill.
STATE_DOT = {'codex_working': theme.ICE, 'working': theme.ICE,
             'typing': theme.VIOLET, 'microphone': theme.ICE,
             'music': theme.VIOLET, 'idle': theme.MUTED, 'usage': theme.MUTED}


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
        self.hover_since=None
        self.left_since=None
        self.dismiss_until_leave=False
        self.preview_state=None
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

    def _workarea_changed(self, *_):
        self.move_clamped(self.pos())

    def closeEvent(self, event):
        screen = getattr(self, '_halo_screen', None)
        if screen is not None:
            try:
                screen.availableGeometryChanged.disconnect(self._workarea_changed)
            except (RuntimeError, TypeError):
                pass
            self._halo_screen = None
        super().closeEvent(event)

    def update_activity(self):
        now=time.monotonic()
        cursor=QCursor.pos()
        pet_hover=self.isVisible() and self.frameGeometry().contains(cursor)
        panel_hover=self.panel.isVisible() and self.panel.frameGeometry().adjusted(-12,-12,12,12).contains(cursor)
        # Brief dwell avoids opening while the cursor merely passes over the pet.
        if not pet_hover and not panel_hover:
            self.hover_since=None
            self.dismiss_until_leave=False
            self.left_since=self.left_since or now
            if self.panel.isVisible() and now-self.left_since>.7 and not QApplication.activeModalWidget() \
                    and not self.panel.is_pinned():
                self.panel.hide()
        else:
            self.left_since=None
            if pet_hover and self.pressed is None and not self.dismiss_until_leave:
                self.hover_since=self.hover_since or now
                if now-self.hover_since>.35 and not self.panel.isVisible():self.show_panel()
        monitor=getattr(self.panel,'activity',None)
        codex_working=getattr(self.panel,'app_mode',None)
        # Opening usage is an overlay, not a pose: keep the same live companion.
        state=self.preview_state or (monitor.state.state(
            codex_working=bool(codex_working and codex_working.is_token)) if monitor else 'idle')
        if state!=self.current_state:
            self.current_state=state
            self.update()

    def update_data(self,data):
        if (data or {}).get('provider_id', 'codex') != 'codex':
            return
        self.snapshot=data
        # An explicitly absent working_context retires the previous
        # live context at once: hysteresis may preserve animation
        # timing, never a false Working label or stale token data.
        self.working_context=(data or {}).get('working_context') or None
        if (self.working_context or {}).get('provider_id', 'codex') != 'codex':
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
        provider_line='Codex · ' if provider == 'codex' else ''
        title=context.get('title') or self.tr_text('codex_working')
        project=context.get('project') or self.tr_text('project_unavailable')
        self.setToolTip(provider_line+f"{project} · {title}\n{context.get('model') or '—'} · {context.get('effort') or '—'}\n"+
                       self.tr_text('pet_tooltip_tokens',total=total_text,
                           input=in_text,output=out_text)+
                       '\n'+self.tr_text('pet_tooltip_actions'))
        self.update()

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
        if self.token_bubble_visible():
            context=self.working_context or {}
            tokens=context.get('tokens') or {}
            style=self.panel.prefs.get('token_number_format')
            p.setPen(QPen(QColor(theme.BORDER),1))
            p.setBrush(bubble)
            bx,by,bw,bh=geometry.scaled_bubble_rect(self.pet_scale)
            p.drawRoundedRect(QRectF(bx,by,bw,bh),theme.RADIUS_CARD,theme.RADIUS_CARD)
            width=geometry.scaled_bubble_text_width(self.pet_scale)
            project=context.get('project') or self.tr_text('project_unavailable')
            status=self.tr_text('working' if context else 'unknown')
            used=context.get('context')
            ctx_text=f"{self.tr_text('context_short')} {'—' if used is None else f'{used:.0f}%'}"
            main_font=QFont('Microsoft YaHei UI',self._px(9),QFont.DemiBold)
            p.setFont(main_font)
            metrics=p.fontMetrics()
            dot='● '
            dot_w=metrics.horizontalAdvance(dot)
            ctx_w=QFontMetrics(QFont('Segoe UI',self._px(8))).horizontalAdvance(ctx_text)
            status_text=f' · {status}'
            status_w=metrics.horizontalAdvance(status_text)
            shown=metrics.elidedText(project,Qt.ElideRight,max(0,width-dot_w-status_w-ctx_w-self._px(8)))
            pad=self._px(12)
            x=bx+pad
            p.setPen(QColor(STATE_DOT.get(self.current_state, theme.ICE)))
            p.drawText(QRectF(x,self._px(7),width,self._px(20)),Qt.AlignLeft|Qt.AlignVCenter,dot)
            x+=dot_w
            p.setPen(QColor(theme.INK))
            p.drawText(QRectF(x,self._px(7),width,self._px(20)),Qt.AlignLeft|Qt.AlignVCenter,shown+status_text)
            p.setPen(QColor(theme.MUTED))
            p.setFont(QFont('Segoe UI',self._px(8)))
            p.drawText(QRectF(bx+pad,self._px(7),width,self._px(20)),Qt.AlignRight|Qt.AlignVCenter,ctx_text)
            total=format_tokens(tokens.get('total_tokens'),style)
            p.setPen(QColor(theme.INK))
            p.setFont(QFont('Segoe UI',self._px(12),QFont.DemiBold))
            p.drawText(QRectF(bx+pad,self._px(30),width,self._px(22)),Qt.AlignLeft|Qt.AlignVCenter,
                       p.fontMetrics().elidedText(total,Qt.ElideRight,width))
        elif (subtitle:=self.music_subtitle()) is not None:
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
        if self.panel.isVisible():
            self.panel.hide();self.dismiss_until_leave=True
        else:self.show_panel()

    def show_panel(self):
        self.panel.anchor_to_pet()
        self.panel.show();self.panel.raise_()
        self.left_since=None

    def contextMenuEvent(self,event):
        menu=QMenu(self)
        menu.setStyleSheet(self.panel.styleSheet())
        menu.addAction(self.tr_text('pet_toggle_panel'),self.toggle_panel)
        menu.addAction(self.tr_text('analytics_button'),self.panel.open_analytics)
        menu.addAction(self.tr_text('pet_settings'),self.panel.open_settings)
        topmost=menu.addAction(self.tr_text('always_on_top'));topmost.setCheckable(True)
        topmost.setChecked(bool(self.panel.prefs.get('always_on_top',True)))
        topmost.triggered.connect(self.toggle_topmost)
        motion=menu.addAction(self.tr_text('idle_motion'));motion.setCheckable(True);motion.setChecked(self.motion)
        motion.triggered.connect(self.toggle_motion)
        menu.addAction(self.tr_text('hide_pet'),self.hide)
        menu.addSeparator();menu.addAction(self.tr_text('exit'),self.panel.shutdown)
        menu.exec(event.globalPos())

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
