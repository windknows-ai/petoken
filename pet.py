"""Transparent character desktop pet; click to reveal the existing dashboard."""
import math
import time
from PySide6.QtCore import Qt,QTimer,QPoint,QRectF
from PySide6.QtGui import QColor,QPainter,QPixmap,QFont,QFontMetrics,QPen,QKeySequence,QShortcut,QCursor
from PySide6.QtWidgets import QWidget,QApplication,QMenu
from localization import text
import pet_assets as assets
import pet_geometry as geometry
import theme
from token_format import format_tokens


class DesktopPet(QWidget):
    def __init__(self,panel):
        super().__init__()
        self.panel=panel
        flags=Qt.Tool|Qt.FramelessWindowHint
        if panel.prefs.get('always_on_top',True):
            flags|=Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(*geometry.window_size())
        # Full-resolution sources from the central registry; paintEvent scales
        # them into the small logical sprite box each frame so high-DPI
        # screens stay sharp. Missing art can never crash the pet: unresolvable
        # states are simply absent and fall back to the idle source.
        self.sprites={k:v for k,v in assets.load_sprites().items() if v is not None}
        self.sprite=self.sprites.get('idle',QPixmap())
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
        state=self.preview_state or (monitor.state.state(usage_open=self.panel.isVisible(),
            codex_working=bool(codex_working and codex_working.is_token)) if monitor else 'idle')
        if state!=self.current_state:
            self.current_state=state
            self.update()

    def update_data(self,data):
        self.snapshot=data
        if data.get('working_context'):
            self.working_context=data['working_context']
        elif not self.token_bubble_visible():
            self.working_context=None
        context=self.working_context or data
        t=context.get('tokens',{})
        style=self.panel.prefs.get('token_number_format')
        project=context.get('project') or self.tr_text('project_unavailable')
        title=context.get('title') or self.tr_text('codex_working')
        self.setToolTip(f"{project} · {title}\n{context.get('model') or '—'} · {context.get('effort') or '—'}\n"+
                       self.tr_text('pet_tooltip_tokens',total=format_tokens(t.get('total_tokens'),style),
                           input=format_tokens(t.get('input_tokens'),style),output=format_tokens(t.get('output_tokens'),style))+
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
            bx,by,bw,bh=geometry.bubble_rect()
            p.drawRoundedRect(QRectF(bx,by,bw,bh),theme.RADIUS_CARD,theme.RADIUS_CARD)
            width=geometry.BUBBLE_TEXT_WIDTH
            project=context.get('project') or self.tr_text('project_unavailable')
            status=self.tr_text('working')
            used=context.get('context')
            ctx_text=f"{self.tr_text('context_short')} {'—' if used is None else f'{used:.0f}%'}"
            main_font=QFont('Microsoft YaHei UI',9,QFont.DemiBold)
            p.setFont(main_font)
            metrics=p.fontMetrics()
            dot='● '
            dot_w=metrics.horizontalAdvance(dot)
            ctx_w=QFontMetrics(QFont('Segoe UI',8)).horizontalAdvance(ctx_text)
            status_text=f' · {status}'
            status_w=metrics.horizontalAdvance(status_text)
            shown=metrics.elidedText(project,Qt.ElideRight,max(0,width-dot_w-status_w-ctx_w-8))
            x=13.0
            p.setPen(QColor(theme.ICE))
            p.drawText(QRectF(x,7,width,20),Qt.AlignLeft|Qt.AlignVCenter,dot)
            x+=dot_w
            p.setPen(QColor(theme.INK))
            p.drawText(QRectF(x,7,width,20),Qt.AlignLeft|Qt.AlignVCenter,shown+status_text)
            p.setPen(QColor(theme.MUTED))
            p.setFont(QFont('Segoe UI',8))
            p.drawText(QRectF(13,7,width,20),Qt.AlignRight|Qt.AlignVCenter,ctx_text)
            total=format_tokens(tokens.get('total_tokens'),style)
            p.setPen(QColor(theme.INK))
            p.setFont(QFont('Segoe UI',12,QFont.DemiBold))
            p.drawText(QRectF(13,30,width,22),Qt.AlignLeft|Qt.AlignVCenter,
                       p.fontMetrics().elidedText(total,Qt.ElideRight,width))
        elif (subtitle:=self.music_subtitle()) is not None:
            # One small secondary pill in the idle card area. No text means no
            # box at all; Token Mode never reaches this branch.
            p.setFont(QFont('Segoe UI',8))
            shown=p.fontMetrics().elidedText(subtitle,Qt.ElideRight,208)
            pill_w=min(232,p.fontMetrics().horizontalAdvance(shown)+24)
            pill_x=(self.width()-pill_w)/2
            p.setPen(QPen(QColor(theme.BORDER),1))
            p.setBrush(bubble)
            p.drawRoundedRect(QRectF(pill_x,16,pill_w,26),13,13)
            p.setPen(QColor(theme.INK))
            p.drawText(QRectF(pill_x,16,pill_w,26),Qt.AlignCenter,shown)
        offset=math.sin(self.phase)*geometry.BOB_AMPLITUDE if self.motion else 0
        p.save()
        if self.reaction:
            px,py=geometry.REACTION_PIVOT
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
                tap_shift=2 if self.typing_phase() else -2
                ax,ay=geometry.anchor()
                p.translate(ax,ay);p.rotate(tilt);p.translate(-ax,-ay)
                offset+=math.sin(self.phase*8)*geometry.TYPING_AMPLITUDE
        sx,sy,sw,sh=geometry.sprite_rect(round(offset))
        if sprite is not None and not sprite.isNull():
            p.drawPixmap(QRectF(sx+round(tap_shift),sy,sw,sh).toRect(),sprite)
        p.restore()

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
                self.reaction=1
                self.toggle_panel()
            self.panel.prefs['pet_position']=[self.x(),self.y()]
            self.panel.persist()

    def toggle_panel(self):
        if self.panel.isVisible():
            self.panel.hide();self.dismiss_until_leave=True
        else:self.show_panel()

    def show_panel(self):
        self.panel.move_clamped(QPoint(self.x()-self.panel.width()-10,self.y()))
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
        self.timer.start() if enabled else self.timer.stop()
        self.panel.persist();self.update()

    def move_clamped(self,point):
        screen=QApplication.screenAt(point+QPoint(121,30)) or QApplication.primaryScreen()
        r=screen.availableGeometry()
        x,y=geometry.clamp_position(point.x(),point.y(),self.width(),self.height(),
                                    (r.left(),r.top(),r.right(),r.bottom()))
        self.move(x,y)
