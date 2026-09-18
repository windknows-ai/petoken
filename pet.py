"""Transparent character desktop pet; click to reveal the existing dashboard."""
import math
import time
from pathlib import Path
from PySide6.QtCore import Qt,QTimer,QPoint,QRectF
from PySide6.QtGui import QColor,QPainter,QPixmap,QFont,QPen,QKeySequence,QShortcut,QCursor
from PySide6.QtWidgets import QWidget,QApplication,QMenu


class DesktopPet(QWidget):
    def __init__(self,panel):
        super().__init__()
        self.panel=panel
        self.setWindowTitle('petoken · 丝柯克桌宠')
        self.setWindowFlags(Qt.Tool|Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(242,378)
        self.setAccessibleName('丝柯克桌宠。点击展开用量，拖动移动，右键打开菜单。')
        self.sprite=QPixmap(str(Path(__file__).parent/'assets/skirk-pet.png'))
        self.sprite=self.sprite.scaled(214,290,Qt.KeepAspectRatio,Qt.SmoothTransformation)
        self.sprites={'idle':self.sprite}
        for state in ('typing','microphone','music'):
            image=QPixmap(str(Path(__file__).parent/f'assets/skirk-{state}.png'))
            if not image.isNull():self.sprites[state]=image.scaled(214,290,Qt.KeepAspectRatio,Qt.SmoothTransformation)
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
        self.pressed=None
        screen=QApplication.primaryScreen().availableGeometry()
        position=panel.prefs.get('pet_position')
        self.move_clamped(QPoint(*position) if isinstance(position,list) and len(position)==2 else QPoint(screen.right()-280,screen.bottom()-400))
        for name,d in [('Left',(-10,0)),('Right',(10,0)),('Up',(0,-10)),('Down',(0,10))]:
            QShortcut(QKeySequence('Alt+'+name),self,activated=lambda delta=d:self.move_clamped(self.pos()+QPoint(*delta)))
        QShortcut(QKeySequence('Return'),self,activated=self.toggle_panel)
        QShortcut(QKeySequence('Space'),self,activated=self.toggle_panel)

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
        state=self.preview_state or (monitor.state.state(usage_open=self.panel.isVisible()) if monitor else 'idle')
        if state!=self.current_state:
            self.current_state=state
            self.update()

    def update_data(self,data):
        self.snapshot=data
        t=data.get('tokens',{})
        self.setToolTip(f"{data.get('project','Codex')} · {data.get('title','等待任务')}\n{data.get('model','—')} · {data.get('effort','—')}\n"
                       f"Total {t.get('total_tokens','N/A')} · Input {t.get('input_tokens','N/A')} · Output {t.get('output_tokens','N/A')}\n点击展开用量 · 拖动移动 · 右键菜单")
        self.update()

    def paintEvent(self,event):
        p=QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor('#777AA4'),1))
        p.setBrush(QColor(29,33,57,235))
        p.drawRoundedRect(QRectF(1,1,240,70),16,16)
        p.setPen(QColor('#EEF2FF'))
        p.setFont(QFont('Microsoft YaHei UI',9,QFont.DemiBold))
        title=self.snapshot.get('title') or '丝柯克 · 等待 Codex'
        p.drawText(QRectF(13,8,216,22),Qt.AlignLeft|Qt.AlignVCenter,p.fontMetrics().elidedText(title,Qt.ElideRight,216))
        p.setFont(QFont('Segoe UI',8))
        p.setPen(QColor('#B9A7F8'))
        project=self.snapshot.get('project','点击查看用量')
        p.drawText(QRectF(13,30,216,16),p.fontMetrics().elidedText(project,Qt.ElideRight,216))
        p.setPen(QColor('#91E4F2'))
        context=self.snapshot.get('context')
        context='—' if context is None else f'{context:.0f}%'
        quota=self.panel.five.value.text().replace(' left','')
        p.drawText(QRectF(13,47,220,18),f'Context {context}  ·  5h {quota} left')
        offset=math.sin(self.phase)*3 if self.motion else 0
        p.save()
        if self.reaction:
            p.translate(121,225);p.rotate(math.sin(self.phase*3)*self.reaction*4);p.translate(-121,-225)
        sprite=self.sprites.get(self.current_state,self.sprite)
        # New poses share the original bounding box and baseline. Idle rendering
        # and its approved asset are left byte-for-byte unchanged.
        if self.current_state=='typing' and self.motion:
            offset+=math.sin(self.phase*8)*1.5
        p.drawPixmap(QPoint((self.width()-sprite.width())//2,82+round(offset)),sprite)
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
        menu.addAction('打开 / 收起用量面板',self.toggle_panel)
        menu.addAction('Token Analytics',self.panel.open_analytics)
        menu.addAction('设置与任务选择',self.panel.open_settings)
        motion=menu.addAction('待机动作');motion.setCheckable(True);motion.setChecked(self.motion)
        motion.triggered.connect(self.toggle_motion)
        menu.addAction('隐藏桌宠（托盘可恢复）',self.hide)
        menu.addSeparator();menu.addAction('退出',self.panel.shutdown)
        menu.exec(event.globalPos())

    def toggle_motion(self,enabled):
        self.motion=enabled
        self.panel.prefs['pet_motion']=enabled
        self.timer.start() if enabled else self.timer.stop()
        self.panel.persist();self.update()

    def move_clamped(self,point):
        screen=QApplication.screenAt(point+QPoint(121,30)) or QApplication.primaryScreen()
        r=screen.availableGeometry()
        self.move(max(r.left(),min(point.x(),r.right()-self.width()+1)),max(r.top(),min(point.y(),r.bottom()-self.height()+1)))
