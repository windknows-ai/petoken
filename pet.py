"""Transparent character desktop pet; click to reveal the existing dashboard."""
import math
import time
from PySide6.QtCore import Qt,QTimer,QPoint,QRectF
from PySide6.QtGui import QColor,QPainter,QPixmap,QFont,QPen,QKeySequence,QShortcut,QCursor
from PySide6.QtWidgets import QWidget,QApplication,QMenu
from localization import text
import pet_assets as assets
import pet_geometry as geometry
from token_format import format_tokens


class DesktopPet(QWidget):
    def __init__(self,panel):
        super().__init__()
        self.panel=panel
        self.setWindowFlags(Qt.Tool|Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint)
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
            if self.panel.isVisible() and now-self.left_since>.7 and not QApplication.activeModalWidget():
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
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        if self.token_bubble_visible():
            context=self.working_context or {}
            tokens=context.get('tokens') or {}
            p.setPen(QPen(QColor('#777AA4'),1))
            p.setBrush(QColor(29,33,57,235))
            bx,by,bw,bh=geometry.bubble_rect()
            p.drawRoundedRect(QRectF(bx,by,bw,bh),16,16)
            p.setPen(QColor('#EEF2FF'))
            p.setFont(QFont('Microsoft YaHei UI',9,QFont.DemiBold))
            title=context.get('title') or self.tr_text('codex_working')
            p.drawText(QRectF(13,8,216,22),Qt.AlignLeft|Qt.AlignVCenter,p.fontMetrics().elidedText(title,Qt.ElideRight,216))
            p.setFont(QFont('Segoe UI',8))
            p.setPen(QColor('#B9A7F8'))
            project=context.get('project') or self.tr_text('project_unavailable')
            project_tokens=f"{project} · {format_tokens(tokens.get('total_tokens'),self.panel.prefs.get('token_number_format'))}"
            p.drawText(QRectF(13,30,216,16),p.fontMetrics().elidedText(project_tokens,Qt.ElideRight,216))
            p.setPen(QColor('#91E4F2'))
            context_used=context.get('context')
            context_used='—' if context_used is None else f'{context_used:.0f}%'
            quota=self.panel.five.value.text().replace(' '+self.tr_text('left'),'')
            p.drawText(QRectF(13,47,220,18),
                       f"● {self.tr_text('working')} · {self.tr_text('context_short')} {context_used} · 5h {quota}")
        offset=math.sin(self.phase)*geometry.BOB_AMPLITUDE if self.motion else 0
        p.save()
        if self.reaction:
            px,py=geometry.REACTION_PIVOT
            p.translate(px,py);p.rotate(math.sin(self.phase*3)*self.reaction*4);p.translate(-px,-py)
        sprite=self.sprites.get(self.current_state,self.sprite)
        # Every state shares one logical sprite box around one feet anchor;
        # only approved-asset pixels change between states, never the geometry.
        if self.current_state=='typing' and self.motion:
            offset+=math.sin(self.phase*8)*geometry.TYPING_AMPLITUDE
        sx,sy,sw,sh=geometry.sprite_rect(round(offset))
        if sprite is not None and not sprite.isNull():
            p.drawPixmap(QRectF(sx,sy,sw,sh).toRect(),sprite)
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
        motion=menu.addAction(self.tr_text('idle_motion'));motion.setCheckable(True);motion.setChecked(self.motion)
        motion.triggered.connect(self.toggle_motion)
        menu.addAction(self.tr_text('hide_pet'),self.hide)
        menu.addSeparator();menu.addAction(self.tr_text('exit'),self.panel.shutdown)
        menu.exec(event.globalPos())

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
