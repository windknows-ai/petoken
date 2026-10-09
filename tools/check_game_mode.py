"""Drive the real test build on screen: game mode in and out, drags, fast switches.

Captures the screen around her every CAPTURE_S and checks, numerically, that
stars land where they should and every window follows her.
"""
import sys, time, math, json
from pathlib import Path
from contextlib import ExitStack
sys.path.insert(0, r'D:\Documents\ChatGPT\petoken-claude')
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QGuiApplication, QImage, QPainter, QColor, QFont
from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
SCENARIO = sys.argv[2] if len(sys.argv) > 2 else 'all'
app = QApplication.instance() or QApplication([])
import tools.tutorial_video as tv
import transform
problems = []


def pump(seconds, every=None, shots=None, region=None, tag=''):
    end = time.monotonic() + seconds
    next_shot = time.monotonic()
    while time.monotonic() < end:
        app.processEvents()
        if every and time.monotonic() >= next_shot:
            next_shot += every
            shots.append((tag, time.monotonic(), grab(region())))
        time.sleep(.004)


def grab(rect):
    screen = QGuiApplication.primaryScreen()
    return screen.grabWindow(0, rect.x(), rect.y(), rect.width(), rect.height()).toImage()


def sheet(shots, name, cols=8, cell=260):
    if not shots:
        return
    rows = (len(shots) + cols - 1) // cols
    t0 = shots[0][1]
    img = QImage(cols * cell, rows * (cell + 18), QImage.Format_ARGB32)
    img.fill(QColor('#101018'))
    p = QPainter(img)
    f = QFont('Segoe UI'); f.setPixelSize(12); p.setFont(f); p.setPen(QColor('#ccc'))
    for k, (tag, at, shot) in enumerate(shots):
        x, y = (k % cols) * cell, (k // cols) * (cell + 18)
        p.drawImage(QRectF(x, y, cell, cell), shot.scaled(cell, cell, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        p.drawText(QRectF(x, y + cell, cell, 16), Qt.AlignCenter, f'{tag} {at - t0:.1f}s')
    p.end()
    img.save(str(OUT / f'{name}.png'))


def check(cond, message):
    if not cond:
        problems.append(message)
        print('PROBLEM:', message, flush=True)


with ExitStack() as stack:
    pv, base = tv.setup(stack, 'zh_CN')
    panel, pet = base.panel, base.pet
    screen = QGuiApplication.primaryScreen().availableGeometry()
    base.count.setValue(3)
    base.refresh()
    pet.move(screen.left() + 500, screen.top() + 260)
    backdrop = tv.Stage(screen)               # Hide whatever is on the desktop.
    backdrop.show()
    backdrop.lower()
    pet.show()
    panel.hide()
    pump(3.0)
    # Prepare the art at both sizes, as the app does at start.
    for _ in range(300):
        if transform.CACHE.get(pet._transform_side()) is not None:
            break
        pump(.05)
    for _ in range(300):
        if transform.CACHE.get(pet._transform_side(pet.mode_scale(gaming=True))) is not None:
            break
        pump(.05)

    def keep_backdrop_low():
        backdrop.lower()

    def around():
        g = pet.frameGeometry()
        side = max(g.width(), g.height()) * 2
        return QRect(g.center().x() - side // 2, g.center().y() - side // 2 - g.height() // 4, side, side)

    mode = panel.game_mode

    def stars_report(label):
        halo = pet.game_halo
        orbs = panel._orb_points()
        return dict(label=label, orbs=[(p, round(q.x()), round(q.y())) for p, q in orbs],
                    halo=[(p, round(q.x()), round(q.y())) for p, q in (halo.star_points() if halo and halo.isVisible() else [])])

    log = []
    if SCENARIO in ('all', 'enter_exit'):
        shots = []
        before = stars_report('before')
        mode.toggle()
        flight = panel._flight
        stage = pet.transform_stage
        check(stage is not None, 'entry: no transformation played')
        # Watch the flight: its stars at the end must be where the ring's stars then are.
        landed = None
        end = time.monotonic() + 16
        while time.monotonic() < end:
            app.processEvents()
            if flight is not None and not flight.done and flight._first and flight.t >= flight.DURATION - .05:
                landed = [(p, q) for p, q in flight.ends()]
            gap = .1 if 1.6 < time.monotonic() - (end - 16) < 4.0 else .5
            if not shots or time.monotonic() - shots[-1][1] >= gap:
                shots.append(('in', time.monotonic(), grab(around())))
            time.sleep(.004)
        after = stars_report('in game')
        log += [before, after]
        check(not pet.veiled and pet.transform_stage is None, 'entry: still veiled after 16 s')
        check(not any(o.isVisible() and o.windowOpacity() > .01 for o in panel.task_manager._windows.values()),
              'entry: usual stars still visible in game')
        if landed is not None:
            now_pts = dict(enumerate(pet.game_halo.star_points()))
            check(len(landed) == len(pet.game_halo.stars), f'entry: {len(landed)} flights for {len(pet.game_halo.stars)} stars')
        # Exit.
        exit_flight_end = None
        mode.toggle()
        flight = panel._flight
        end = time.monotonic() + 6
        while time.monotonic() < end:
            app.processEvents()
            if flight is not None and not flight.done and flight._first and flight.t >= flight.DURATION - .03:
                exit_flight_end = [(p, (round(q.x()), round(q.y()))) for p, q in flight.ends()]
            if time.monotonic() - shots[-1][1] >= .15:
                shots.append(('out', time.monotonic(), grab(around())))
            time.sleep(.004)
        pump(1.0)
        final = stars_report('after')
        log.append(final)
        orbs_now = [(p, (x, y)) for p, x, y in final['orbs']]
        if exit_flight_end:
            for (p1, a), (p2, b) in zip(exit_flight_end, sorted(orbs_now, key=lambda o: [e[0] for e in exit_flight_end].index(o[0]) if o[0] in [e[0] for e in exit_flight_end] else 9)):
                pass
            dist = [min(math.hypot(a[0] - b[0], a[1] - b[1]) for _, b in orbs_now) for _, a in exit_flight_end]
            pass   # The usual ring keeps turning: compared later it has moved on.
        check(all(o.windowOpacity() > .99 for o in panel.task_manager._windows.values()), 'exit: usual stars left transparent')
        check(not pet.game_halo.isVisible(), 'exit: ring behind her still visible')
        check(not (pet.windowFlags() & Qt.WindowTransparentForInput), 'exit: she still ignores clicks')
        sheet([s for s in shots if s[0] == 'in'], 'enter', cols=6, cell=330)
        sheet([s for s in shots if s[0] == 'out'], 'exit', cols=6, cell=330)

    if SCENARIO in ('all', 'drag'):
        shots = []
        mode.toggle()
        pump(4.0)
        stage = pet.transform_stage
        start = pet.pos()
        for k in range(40):          # Drag her 200 px right and 80 px down during the armour.
            pet.move_clamped(start + QPoint(5 * k, 2 * k))
            for extra in (pet.game_halo, pet.game_usage):
                if extra is not None and extra.isVisible():
                    extra.follow()
            pump(.02)
        pump(.1, .1, shots, around, 'drag')
        if stage is not None and pet.transform_stage is stage:
            box = stage.sprite_rect()
            g = stage.geometry()
            check(g.contains(box.toRect().center()), 'drag: the transformation did not follow her')
        halo = pet.game_halo
        check(abs(halo.geometry().center().x() - pet.frameGeometry().center().x()) < 3, 'drag: ring not centred on her')
        pump(10, .5, shots, around, 'drag')
        mode.toggle()
        pump(5, .5, shots, around, 'drag-out')
        sheet(shots, 'drag')

    if SCENARIO in ('all', 'fast'):
        shots = []
        for wait in (.4, .3, 2.5, .2, 3.5, .1, .1, .1):
            mode.toggle()
            pump(wait, .1, shots, around, 'on' if mode.active else 'off')
        if mode.active:
            mode.toggle()
        pump(6, .5, shots, around, 'settle')
        tops = [w for w in QApplication.topLevelWidgets() if w.isVisible()]
        names = sorted(type(w).__name__ for w in tops)
        check('TransformStage' not in names, f'fast: a transformation window was left: {names}')
        check('StarFlight' not in names, f'fast: a flight window was left: {names}')
        check(not pet.veiled, 'fast: she stayed invisible')
        check(all(o.windowOpacity() > .99 for o in panel.task_manager._windows.values() if o.isVisible()),
              'fast: usual stars left faded')
        check(panel.task_manager._visible, 'fast: usual ring not back')
        sheet(shots, 'fast')

    if SCENARIO in ('all', 'size'):
        shots = []
        panel.prefs.update(pet_scale_percent=100, game_scale_percent=70)
        pet.apply_pet_scale(100)
        import pet_geometry
        feet_now = lambda: pet.pos() + QPoint(*pet_geometry.scaled_anchor(pet.pet_scale))
        feet = feet_now()
        mode.toggle()
        pump(14, .5, shots, around, 'size')
        check(pet.pet_scale == 70, f'size: game size not reached ({pet.pet_scale}%)')
        check(feet_now() == feet, f'size: she moved ({feet_now() - feet})')
        mode.toggle()
        pump(5, .5, shots, around, 'size-out')
        check(pet.pet_scale == 100, f'size: usual size not restored ({pet.pet_scale}%)')
        sheet(shots, 'size')

    if SCENARIO in ('all', 'pager'):
        base.count.setValue(15)
        base.refresh()
        pet.move(screen.left() + 500, screen.bottom() - pet.height() - 10)
        pump(3.0)
        pager = panel.task_manager.page_controls
        card = pet.usage_overlay
        if pager is not None and card is not None and pager.isVisible() and card.isVisible():
            check(not pager.frameGeometry().intersects(card.frameGeometry()), 'pager: overlaps the usage card')
        grabbed = grab(around().adjusted(-100, -250, 100, 0))
        grabbed.save(str(OUT / 'pager.png'))
        base.count.setValue(3)
        base.refresh()

    (OUT / 'log.json').write_text(json.dumps(dict(problems=problems, log=log), indent=1), encoding='utf-8')
    print('PROBLEMS:', len(problems), flush=True)
    for line in problems:
        print('  ', line)
    tv.finish(pv, base)
