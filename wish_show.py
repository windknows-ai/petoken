"""The wishing show (2.5).

A meteor shower drifts across the night sky, every streak radiating from one
point like a real shower. She flies in, looks around among the falling stars,
spots hers and catches it (a single wish), or sweeps through the shower
catching ten that then circle her (ten wishes). Each find bursts in its
rarity's light, then becomes the card of what she found. A click skips to the
cards; another closes.

The lights are pre-rendered with real bloom and lens streaks
(tools/render_wish_fx.py) and drawn additively, so they mix like light. Each
rarity has its own shape, not just its own colour:
Stars a sapphire four-point star, Moon a full moon in a pale halo ring that
flashes, Sun a gold sun with a ragged corona and rays, Galaxy a tilted silver
spiral that turns, Starsea a prism star in turning rainbow rings.
"""
from __future__ import annotations

import math
import random
from concurrent.futures import Future, ThreadPoolExecutor

from PySide6.QtCore import QEvent, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import (QColor, QConicalGradient, QFont, QImage, QLinearGradient, QPainter, QPainterPath, QPen,
                           QPixmap)
from PySide6.QtWidgets import QWidget

import pet_assets
import shop
from localization import text

FX_DIR = pet_assets.ASSETS_DIR / 'v2_5' / 'wish'
SHOWER = ('ice', 'champagne', 'lavender', 'pearl')                 # The task-star palette.
POSES = dict(fly=('dragged', 'star_dragged'), look=('curious', 'star_thinking'), spot=('surprised', 'star_poked'),
             reach=('wave', 'star_wave'), cheer=('cheer', 'star_celebrate'))
_FX = {}
SEQ_DIR = FX_DIR / 'seq'            # After Effects frame sequences (tools/ae), 30 fps.
SEQ_FPS = 30
_SEQ = {}
_FRAMES = {}                        # (name, index) -> QImage, or the Future decoding it.
# Decoding happens off the main thread, ahead of need, so a burst never waits on a file.
_POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix='wish')


def fx(name):
    """A pre-rendered light (on black, drawn additively); a null pixmap when missing."""
    if name not in _FX:
        path = FX_DIR / (name + ('.jpg' if name == 'sky' or name.startswith('sky_') else '.webp'))
        _FX[name] = QPixmap(str(path)) if path.is_file() else QPixmap()
    return _FX[name]


def _ease(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def _out(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def _back(x, s=1.7):
    x = max(0.0, min(1.0, x)) - 1
    return x * x * ((s + 1) * x + s) + 1


def _lerp(a, b, f):
    return a + (b - a) * f


def _distance(a, b):
    return math.hypot(a.x() - b.x(), a.y() - b.y())


def _rgba(colour, alpha):
    return QColor(colour.red(), colour.green(), colour.blue(), max(0, min(255, int(alpha))))


def seq_length(name):
    if name not in _SEQ:
        folder = SEQ_DIR / name
        _SEQ[name] = sorted(folder.glob('*.jpg')) if folder.is_dir() else []
    return len(_SEQ[name])


def _decode(path):
    image = QImage(path)
    return image.convertToFormat(QImage.Format_RGB32) if not image.isNull() else image


def _scaled_pose(path, height):
    image = QImage(path)
    return image.scaledToHeight(height, Qt.SmoothTransformation) if not image.isNull() else None


def preload(name):
    """Start decoding every frame of ``name`` in the background."""
    for index in range(seq_length(name)):
        key = (name, index)
        if key not in _FRAMES:
            _FRAMES[key] = _POOL.submit(_decode, str(_SEQ[name][index]))


def release(name):
    """Let a finished sequence's frames go (they are big)."""
    for key in [k for k in _FRAMES if k[0] == name]:
        del _FRAMES[key]


def seq_frame(name, index):
    """One frame of a sequence: preloaded if it was asked for in time, else decoded now."""
    key = (name, index)
    item = _FRAMES.get(key)
    if item is None:
        item = _decode(str(_SEQ[name][index]))
    elif isinstance(item, Future):
        item = item.result()
    _FRAMES[key] = item
    return item


def play(p, name, centre, width, t, alpha=1.0, loop=False, angle=0.0, height=None):
    """Draw sequence ``name`` at ``t`` seconds into it; False once a one-shot is over."""
    count = seq_length(name)
    if not count or t < 0 or alpha <= .01:
        return False
    index = int(t * SEQ_FPS)
    if loop:
        index %= count
    elif index >= count:
        return False
    image = seq_frame(name, index)
    p.save()
    p.translate(centre)
    if angle:
        p.rotate(angle)
    p.setOpacity(min(1.0, alpha))
    height = width if height is None else height
    p.drawImage(QRectF(-width / 2, -height / 2, width, height), image, QRectF(image.rect()))
    p.restore()
    return True


def play_loop(p, name, centre, width, t, alpha=1.0, angle=0.0, height=None):
    """A seamless loop: two copies half a loop apart, each fading in and out."""
    count = seq_length(name)
    if not count:
        return
    period = count / SEQ_FPS
    u = (t / period) % 1.0
    for shift in (0.0, .5):
        v = (u + shift) % 1.0
        weight = math.sin(math.pi * v) ** 2
        play(p, name, centre, width, v * period, alpha * weight, angle=angle, height=height)


def _scaled_layer(path, w, h, cover, ratio, add=None):
    image = QImage(path)
    if image.isNull():
        return None
    if add is not None:                                    # Light added onto it (the stars onto the far sky).
        extra = QImage(add)
        if not extra.isNull():
            image = image.convertToFormat(QImage.Format_RGB32)
            p = QPainter(image)
            p.setCompositionMode(QPainter.CompositionMode_Plus)
            p.drawImage(QRectF(image.rect()), extra, QRectF(extra.rect()))
            p.end()
    scale = max(w / image.width(), h / image.height()) * cover
    scaled = image.scaled(int(image.width() * scale * ratio), int(image.height() * scale * ratio),
                          Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    scaled.setDevicePixelRatio(ratio)
    return scaled


def _scaled_card(path, w, h, ratio):
    image = QImage(path)
    if image.isNull():
        return None
    image = image.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    image.setDevicePixelRatio(ratio)
    return image


def _fitted_art(path, side, ratio):
    image = QImage(path)
    if image.isNull():
        return None
    image = image.scaled(side, side, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    image.setDevicePixelRatio(ratio)
    return image


def light(p, name, centre, width, alpha=1.0, angle=0.0, squash=1.0, tilt=0.0):
    """Draw light ``name`` centred at ``centre``, ``width`` wide. ``squash`` flattens it
    after turning (a tilted disc that turns, like the galaxy), ``tilt`` turns the
    flattened result."""
    pm = fx(name)
    if pm.isNull() or alpha <= .01 or width < 1:
        return
    p.save()
    p.translate(centre)
    if tilt:
        p.rotate(tilt)
    if squash != 1.0:
        p.scale(1.0, squash)
    if angle:
        p.rotate(angle)
    p.setOpacity(min(1.0, alpha))
    height = width * pm.height() / pm.width()
    turned = tilt or angle or squash != 1.0
    scale = abs(p.transform().m11()) if not turned else 0.0
    if not turned and scale > 0:
        # Upright and unturned (most lights): drawn from a copy already at its size on screen.
        # Shrinking the big source every frame was most of the show's cost.
        ratio = p.device().devicePixelRatioF() if p.device() is not None else 1.0
        side = max(2, int(width * scale * ratio / 4 + .5) * 4)     # Sizes in steps of 4 px: few copies.
        sized = _sized(name, side)
        p.drawPixmap(QRectF(-width / 2, -height / 2, width, height), sized, QRectF(sized.rect()))
    else:
        p.drawPixmap(QRectF(-width / 2, -height / 2, width, height), pm, QRectF(pm.rect()))
    p.restore()


_SIZED = {}


def _sized(name, side):
    """Light ``name`` scaled once to ``side`` device pixels wide (a small cache of recent sizes)."""
    key = (name, side)
    pm = _SIZED.get(key)
    if pm is None:
        source = fx(name)
        pm = source.scaledToWidth(side, Qt.SmoothTransformation) if side < source.width() else source
        if len(_SIZED) > 240:
            _SIZED.pop(next(iter(_SIZED)))
        _SIZED[key] = pm
    return pm


def streak(p, name, head, angle, length, alpha=1.0, grow=1.0):
    """A meteor sprite with its head at ``head`` flying at ``angle`` degrees; its tail is
    ``length`` long and grows out of the head for ``grow`` < 1."""
    pm = fx(name)
    if pm.isNull() or alpha <= .01:
        return
    hero = pm.width() >= 1280
    hx = pm.width() - (72 if hero else 56)
    scale = length / (hx * .55)                                     # The visible tail is about half the sprite.
    start = hx * (1 - max(.02, min(1.0, grow)))
    p.save()
    p.translate(head)
    p.rotate(angle)
    p.scale(scale, scale)
    p.setOpacity(min(1.0, alpha))
    p.drawPixmap(QRectF(start - hx, -pm.height() / 2, pm.width() - start, pm.height()), pm,
                 QRectF(start, 0, pm.width() - start, pm.height()))
    p.restore()


class WishShow(QWidget):
    FPS_MS = 16
    INTRO = 1.4                   # She flies in by herself, then she is yours to steer.
    CHARGE = .65                  # A caught star gathers light (and climbs the rarities) before it bursts.
    NEVER = 1e9
    # How much each rarity's opening makes of itself (the higher, the longer and grander):
    # slow motion after the burst, how far the view leans in, how dark the sky goes, the flash.
    SLOW = (0, 0, .45, .75, .95)
    ZOOM = (0, .015, .045, .07, .09)
    DARK = (0, 0, .3, .58, .68)
    FLASH = (0, .04, .14, .18, .22)
    EXCLUSIVE = 1.85              # Galaxy and Starsea play their own opening first (its flash is the burst).

    def __init__(self, parent, results, language, starsea=False, sound=False, on_sound=None):
        # Inside the window it was opened from (it moves and resizes with it), or its own
        # window when there is none (tests, previews).
        self.host = parent.window() if parent is not None else None
        if self.host is not None:
            super().__init__(self.host)
        else:
            super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.results, self.language, self.starsea = results, language, starsea
        self.ten = len(results) > 1
        self.t = 0.0
        if self.host is not None:
            self.setGeometry(self.host.overlay_rect() if hasattr(self.host, "overlay_rect") else self.host.rect())
            self.host.installEventFilter(self)
        else:
            self.resize(1000, 640)
        self.rng = random.Random(len(results) * 31 + sum(map(ord, results[0]['item']['id'])))
        best = max(range(len(results)), key=lambda i: shop.RARITIES.index(results[i]['item']['rarity']))
        others = sorted((i for i in range(len(results)) if i != best),
                        key=lambda i: shop.RARITIES.index(results[i]['item']['rarity']))
        # What each star holds was decided when the wish was made (shop.Shop.wish): catching
        # only chooses when it is shown, never what it is. The best one is always shown last.
        self.order = others + [best]
        self.best = best
        self.queue = list(self.order)
        self.catch = {}               # index -> when its light bursts
        self.touch = {}               # index -> (when she touched it, where)
        self.flip0 = self.length = self.NEVER
        self.progress = self.INTRO    # Last moment something was caught (for the helping hand).
        w, h = self.width(), self.height()
        self.her = QPointF(-.14 * w, 1.0 * h)
        self.velocity = QPointF()
        self.facing_left = False
        self.wake = []                # Her recent positions: the stardust she leaves.
        self.pointer = None           # Where the mouse is (window coordinates), once it moved.
        self.keys = set()
        self.stars = []               # Wishing stars still in the sky.
        self._next_star = .6
        self._star_ids = 0
        self.shower = self._shower()
        self.twinkles = [(self.rng.random(), self.rng.random() * .92, self.rng.uniform(.010, .028),
                          self.rng.random() * 6.3, self.rng.uniform(.7, 1.8), self.rng.choice(SHOWER))
                         for _ in range(70)]
        self.burst_at = {}            # Per catch: where its burst stays (it does not follow her).
        self.exclusive = {}           # index -> when its own opening starts (Galaxy, Starsea).
        self._layers = {}
        self._used = set()
        self._prepare_poses()                               # Her pictures first: she shows at once.
        # Everything this show will play starts decoding now: the results are known, and a burst read
        # from disk only when it is caught made the first show of the day stop for a second.
        rarities = {res['item']['rarity'] for res in results}
        for name in ['wishstar', 'charge'] + [f'{kind}_{r}' for r in rarities for kind in ('emblem', 'cardbeam')]:
            self._preload(name)
        # The big bursts a moment later, once the opening plays: hundreds of MB decoded all at once
        # stalled the whole app while the opening started.
        self._later = [f'{kind}_{r}' for r in rarities for kind in ('reveal', 'pillar')]
        self._later += [f'exclusive_{r}' for r in rarities if shop.RARITIES.index(r) >= 3]
        self._prepare_layers()
        self._prepare_art()
        from wish_sound import Sounds
        self.sounds = Sounds(sound)
        self.on_sound = on_sound
        self._cues = [(0.0, 'open')]                        # (show time, sound): played as time passes.
        self._played = {}
        self._skipping = False
        self._poses = {}
        self._sky = None
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.setInterval(self.FPS_MS)
        self.timer.timeout.connect(self._step)
        self.timer.start()

    # Setup ------------------------------------------------------------------------------
    def _preload(self, name):
        self._used.add(name)
        preload(name)

    def _prepare_poses(self):
        """Scale every pose of the show once, in the background, before she needs it."""
        self._pose_jobs = {}
        size = self.height() * (.34 if self.ten else .40) * self.devicePixelRatioF()
        for name in POSES:
            path = self._pose_file(name)
            if path is not None:                            # Read and scaled off the main thread.
                self._pose_jobs[name] = _POOL.submit(_scaled_pose, path, int(size))

    def _prepare_art(self):
        """Each find's picture, decoded and scaled to its card in the background."""
        self._art = {}
        ratio = self.devicePixelRatioF()
        for k, index in enumerate(self.order if self.ten else [0]):
            frames = self.results[index]['item'].get('art')
            if not frames:
                continue
            centre, (cw, ch) = self.slot(k)
            side = int(min(cw * .86, ch * .36) * ratio)
            art_dir = self.results[index]['item'].get('art_dir')
            folder = shop.ASSETS.parent / art_dir if art_dir else shop.ASSETS
            self._art[index] = _POOL.submit(_fitted_art, str(folder / frames[0]), side, ratio)
        self._frames = {}                                   # The card frames, scaled to the cards.
        for k, index in enumerate(self.order if self.ten else [0]):
            rarity = self.rarity(index)
            centre, (cw, ch) = self.slot(k)
            key = (rarity, int(cw * ratio), int(ch * ratio))
            path = FX_DIR / f'card_{rarity}.webp'
            if key not in self._frames and path.is_file():
                self._frames[key] = _POOL.submit(_scaled_card, str(path), key[1], key[2], ratio)

    def _prepare_layers(self):
        w, h, ratio = self.width(), self.height(), self.devicePixelRatioF()
        # The far sky and its stars are joined once into one picture (one blit a frame, not two).
        far, stars = FX_DIR / 'sky_far.jpg', FX_DIR / 'sky_stars.jpg'
        if far.is_file() and ('sky_far', w, h) not in self._layers:
            self._layers[('sky_far', w, h)] = _POOL.submit(_scaled_layer, str(far), w, h, 1.12, ratio,
                                                           str(stars) if stars.is_file() else None)
        dust = FX_DIR / 'sky_dust.jpg'
        if dust.is_file() and ('sky_dust', w, h) not in self._layers:
            self._layers[('sky_dust', w, h)] = _POOL.submit(_scaled_layer, str(dust), w, h, 1.24, ratio)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_art'):
            self._prepare_art()                             # Cards and pictures at the new size.

    def eventFilter(self, obj, event):
        if obj is self.host and event.type() == QEvent.Resize:
            self.setGeometry(self.host.overlay_rect() if hasattr(self.host, "overlay_rect") else self.host.rect())
        return False

    def closeEvent(self, event):
        self.sounds.close()
        if self.host is not None:
            self.host.removeEventFilter(self)
        for name in self._used:                             # The frames are big; let them go.
            release(name)
        super().closeEvent(event)

    def _shower(self):
        """Background meteors for the whole show: (start, life, x, y, depth, colour key)."""
        rng = self.rng
        out, t = [], .15
        while t < 90:
            rate = 5 + 7 * _ease((t - .1) / .8)                    # Never a gap: evenly jittered.
            t += rng.uniform(.35, 1.65) / rate
            out.append((t, rng.uniform(1.0, 1.7), rng.uniform(-.15, 1.05), rng.uniform(-.25, .75), rng.random() ** 1.4,
                        rng.choice(SHOWER)))
        return out

    def _pose_file(self, name):
        """The file of her first picture for a moment of the show (her Starsea one when she is in it)."""
        state = POSES[name][1 if self.starsea else 0]
        for candidate in (state, POSES[name][0], 'idle'):
            try:
                entry = pet_assets.entry_for(candidate)
            except KeyError:
                continue
            frames = pet_assets.existing_frames(entry)
            path = frames[0] if frames else pet_assets.resolve_path(entry)
            if path:
                return str(pet_assets._file(path))
        return None

    def _pose_source(self, name):
        state = POSES[name][1 if self.starsea else 0]
        for candidate in (state, POSES[name][0], 'idle'):
            source = (pet_assets.frame_for(candidate, 0) if pet_assets.frame_count(candidate)
                      else pet_assets.sprite_for(candidate))
            if source is not None and not source.isNull():
                return source
        return None

    def pose(self, name, size=None):
        """Her picture for a moment of the show (scaled in the background at the start)."""
        if name not in self._poses:
            job = self._pose_jobs.get(name)
            if job is not None and not job.done():
                return None                                 # Still being scaled: drawn from the next frame.
            image = job.result() if job is not None else None
            if image is not None:
                image.setDevicePixelRatio(self.devicePixelRatioF())
            self._poses[name] = image
        return self._poses[name]

    def colour(self, index, t=None):
        from shop_view import rarity_colour
        return rarity_colour(self.rarity(index), self.t if t is None else t, index / 10)

    def rarity(self, index):
        return self.results[index]['item']['rarity']

    def rank(self, index):
        return shop.RARITIES.index(self.rarity(index))

    # Time and play ----------------------------------------------------------------------
    def playing(self):
        return self.INTRO <= self.t and bool(self.queue)

    def _step(self):
        # Real time, not a fixed tick: a slow frame never makes the show lurch or crawl.
        import time as clock
        now = clock.perf_counter()
        last = getattr(self, '_last_step', None)
        self._last_step = now
        self.advance(min(.05, now - last) if last is not None else self.FPS_MS / 1000)
        if self._later and self.t > .6:
            for name in self._later:
                self._preload(name)
            self._later = []
        if self.t > self.length + 30:
            self.timer.stop()
        self.update()

    def time_scale(self):
        """Below 1 for a moment after a fine find bursts: the world slows down to show it."""
        scale = 1.0
        for index, burst in self.catch.items():
            hold = self.SLOW[self.rank(index)]
            if hold and burst - .12 <= self.t <= burst + hold + .35:
                env = _ease((self.t - burst + .12) / .12) * (1 - _ease((self.t - burst - hold) / .35))
                scale = min(scale, 1 - .62 * env)
        return scale

    def advance(self, dt):
        """Move the show on by ``dt`` seconds: her, the wishing stars, the catches."""
        dt *= self.time_scale()
        self.t += dt
        if self._cues and self._cues[0][0] <= self.t:
            due = [cue for cue in self._cues if cue[0] <= self.t]
            self._cues = [cue for cue in self._cues if cue[0] > self.t]
            for _, name in due[-4:]:                        # Never a pile-up after a skip.
                last = self._played.get(name)
                if last is not None and self.t - last < .45:
                    continue                                # The same sound again so soon: once is enough.
                self._played[name] = self.t
                self.sounds.play(name)
        t, w, h = self.t, self.width(), self.height()
        self._move_her(dt)
        self.wake.append((t, QPointF(self.her)))
        self.wake = [(at, point) for at, point in self.wake if t - at < .7]
        if self.playing():
            self._spawn_stars()
        reach = self.her_size() * .42
        centre = self.her + QPointF(0, -self.her_size() * .08)
        helper = None
        if self.queue and t - self.progress > (4.0 if self.ten else 5.5):
            # Nothing caught for a while: the nearest star comes to her by itself.
            helper = min(self.stars, key=lambda s: _distance(s['pos'], centre), default=None)
        for star in list(self.stars):
            if star is helper:
                to = centre - star['pos']
                n = max(1.0, math.hypot(to.x(), to.y()))
                star['vel'] = star['vel'] * .9 + QPointF(to.x() / n, to.y() / n) * (h * .7) * .1
            sway = math.sin(t * 1.7 + star['phase']) * h * .02
            star['pos'] += star['vel'] * dt + QPointF(sway * dt, 0)
            if t - star.get('marked', 0) > .045:            # A dot of its trail every few frames.
                star['marked'] = t
                star['trail'] = (star['trail'] + [QPointF(star['pos'])])[-14:]
            if self.playing() and self.in_play(star['pos']) and _distance(star['pos'], centre) < reach:
                self.stars.remove(star)
                self._caught(star['pos'])
            elif star['pos'].x() < -w * .15 or star['pos'].y() > h * 1.15:
                self.stars.remove(star)

    def _spawn_stars(self):
        w, h, rng = self.width(), self.height(), self.rng
        wanted = 5 if self.ten else 3
        if self.t < self._next_star or len(self.stars) >= wanted or self.exclusive_now() is not None:
            return
        self._next_star = self.t + rng.uniform(.35, .8)
        start = QPointF(w * rng.uniform(.3, .95), -h * .06)     # From above, drifting into where she can reach.
        speed = h * rng.uniform(.13, .2)
        heading = math.radians(rng.uniform(112, 138))             # Down and to the left, like the shower.
        self._star_ids += 1
        self.stars.append(dict(id=self._star_ids, pos=start, born=self.t, phase=rng.random() * 6.3,
                               vel=QPointF(math.cos(heading), math.sin(heading)) * speed,
                               key=rng.choice(SHOWER), trail=[]))

    def _caught(self, where):
        index = self.queue.pop(0)
        rarity = self.rarity(index)
        for name in (f'reveal_{rarity}', f'pillar_{rarity}') + ((f'exclusive_{rarity}',) if self.rank(index) >= 3 else ()):
            self._preload(name)
        self.touch[index] = (self.t, QPointF(where))
        if self.rank(index) >= 3:                           # Its own opening, then the burst on its flash.
            self.exclusive[index] = self.t + .35
            self.catch[index] = self.exclusive[index] + self.EXCLUSIVE
            if not self._skipping:
                self._cue(self.t, 'catch')
            self._cue(self.exclusive[index], 'rise_xinghai' if rarity == 'xinghai' else 'rise')
        else:
            self.catch[index] = self.t + self.CHARGE
            if not self._skipping:
                self._cue(self.t, 'catch')
                self._cue(self.t + .02, 'charge')
        if not self._skipping or not self.queue:            # Skipped: only the last (finest) one sounds.
            self._cue(self.catch[index], f'burst_{rarity}')
        self.progress = self.catch[index]
        if not self.queue:
            self.flip0 = self.catch[index] + (1.25 if not self.ten else 1.3)
            # One turn sound for the row, and a bell for the finest card only: ten cards turn in
            # under a second, ten sounds would pile into noise.
            cards = self.order if self.ten else [0]
            self._cue(self._flip_time(0), 'flip')
            best = max(range(len(cards)), key=lambda k: self.rank(cards[k]))
            if self.rank(cards[best]) >= 2:
                self._cue(self._flip_time(best), 'flip_fine')
            self.length = self.flip0 + (1.0 if not self.ten else 9 * self.STAGGER + 1.0)

    def _cue(self, at, name):
        self._cues.append((at, name))
        self._cues.sort(key=lambda cue: cue[0])

    def sound_rect(self):
        return QRectF(self.width() - 160, 16, 32, 32)

    def toggle_sound(self):
        enabled = not self.sounds.enabled
        self.sounds.set_enabled(enabled)
        if self.on_sound is not None:
            self.on_sound(enabled)

    def skip(self):
        """Every star still to find comes to her at once, then the cards."""
        if self.flip0 < self.NEVER and self.t > self.flip0 - .8:
            return                                          # The cards are coming: no skipping now.
        hand = self.hand()
        if self.t < self.INTRO:
            self.t = self.INTRO
        self._skipping = True
        while self.queue:
            self._caught(hand)
            self.t += .02
        self._skipping = False
        self.t = max(self.t, self.flip0 - .3)

    def her_size(self):
        h = self.height()
        size = h * (.40 if not self.ten else .34)
        if self.ten and self.flip0 < self.NEVER:
            size *= 1 - .5 * _ease((self.t - (self.flip0 - .8)) / .8)
        return size

    def _move_her(self, dt):
        w, h, t = self.width(), self.height(), self.t
        if t < self.INTRO:                                  # Flying in on a curve.
            f = _out((t - .1) / (self.INTRO - .1))
            start, bend, rest = QPointF(-.14 * w, h * 1.0), QPointF(w * .06, h * .32), QPointF(w * .36, h * .60)
            a, b = (1 - f) ** 2, 2 * (1 - f) * f
            new = start * a + bend * b + rest * (f * f)
            self.velocity = (new - self.her) / max(dt, 1e-3)
            self.her = new
            return
        showing = self.exclusive_now()
        if showing is not None and self.flip0 == self.NEVER or (showing is not None and t < self.flip0 - .9):
            # Her own opening: she carries the star to the middle of the sky.
            target = QPointF(w * .5 - self.her_size() * .4, h * .5 + self.her_size() * .3)
        elif self.flip0 < self.NEVER:                       # Cards: she steps aside.
            aim = QPointF(w * (.9 if self.ten else .26), h * (.87 if self.ten else .62))
            target = aim if t > self.flip0 - .9 else self.her
        elif self.keys:
            dx = (('right' in self.keys) - ('left' in self.keys))
            dy = (('down' in self.keys) - ('up' in self.keys))
            target = self.her + QPointF(dx, dy) * h * .35
        elif self.pointer is not None:
            target = self.pointer + QPointF(0, self.her_size() * .1)
        else:
            target = self.her
        if self.flip0 == self.NEVER:
            area = self.play_area()                         # She stays where her light fits on screen.
            target = QPointF(min(max(target.x(), area.left()), area.right()),
                             min(max(target.y(), area.top()), area.bottom()))
        want = (target - self.her) * 4.2
        top = h * 1.8
        n = math.hypot(want.x(), want.y())
        if n > top:
            want *= top / n
        blend = 1 - math.exp(-7 * dt)
        self.velocity = self.velocity + (want - self.velocity) * blend
        self.her += self.velocity * dt
        if self.velocity.x() < -h * .12:
            self.facing_left = True
        elif self.velocity.x() > h * .12:
            self.facing_left = False

    def exclusive_now(self):
        """The index whose own opening plays now (until its burst has faded), or None."""
        for index, start in self.exclusive.items():
            if self.touch[index][0] <= self.t <= self.catch[index] + .9:
                return index
        return None

    def play_area(self):
        """Where she may fly and stars may be caught: inside, so every burst is seen whole."""
        w, h = self.width(), self.height()
        return QRectF(w * .16, h * .28, w * .62, h * .52)

    def in_play(self, point):
        return self.play_area().adjusted(-self.width() * .06, -self.height() * .14,
                                         self.width() * .06, self.height() * .08).contains(point)

    def her_place(self):
        """Her centre, size, lean (degrees) and whether she faces left."""
        h = self.height()
        lean = max(-16.0, min(16.0, self.velocity.x() / h * 9))
        bob = math.sin(self.t * 2.1) * h * .008
        return self.her + QPointF(0, bob), self.her_size(), lean, self.facing_left

    def pose_name(self):
        t = self.t
        if t < self.INTRO:
            return 'fly'
        if self.flip0 < self.NEVER and t > self.flip0 - .9:
            return 'cheer'
        for index, (at, where) in self.touch.items():
            if at <= t < self.catch[index]:
                return 'spot'                               # Holding her star while it lights up.
            if self.catch[index] <= t < self.catch[index] + 1.0:
                return 'cheer'
        speed = math.hypot(self.velocity.x(), self.velocity.y())
        centre = self.her
        near = min((_distance(s['pos'], centre) for s in self.stars), default=self.NEVER)
        if near < self.her_size() * 1.1:
            return 'reach'
        return 'fly' if speed > self.height() * .45 else 'look'

    def hand(self):
        pos, size, lean, facing_left = self.her_place()
        dx = size * .40 * (-1 if facing_left else 1)
        return QPointF(pos.x() + dx, pos.y() - size * .30)      # Just past her raised hand, clear of her face.

    def slot(self, k):
        """Where card ``k`` sits: tall cards side by side (ten) or one tall card (one)."""
        w, h = self.width(), self.height()
        if not self.ten:
            ch = h * .74
            return QPointF(w * .64, h * .5), (ch / 2.4, ch)
        cw = min(w * .9 / (10 + 9 * .14), h * .2)          # All ten fit, side by side.
        ch = min(cw * 2.4, h * .62)
        cw = ch / 2.4
        gap = cw * .14
        x0 = w * .5 - 4.5 * (cw + gap)
        return QPointF(x0 + k * (cw + gap), h * .43), (cw, ch)

    def skip_rect(self):
        return QRectF(self.width() - 118, 16, 100, 32)

    # Input --------------------------------------------------------------------------------
    KEYS = {Qt.Key_Left: 'left', Qt.Key_A: 'left', Qt.Key_Right: 'right', Qt.Key_D: 'right',
            Qt.Key_Up: 'up', Qt.Key_W: 'up', Qt.Key_Down: 'down', Qt.Key_S: 'down'}

    def mouseMoveEvent(self, event):
        self.pointer = event.position()

    def mousePressEvent(self, event):
        point = event.position() if event is not None else None
        if point is not None and self.sound_rect().contains(point):
            self.toggle_sound()                             # Sound on or off, any time.
            return
        if self.flip0 < self.NEVER:                          # Cards: wait until all have turned.
            if self.cards_done():
                self.close()
            return
        if point is None or self.skip_rect().contains(point):
            self.skip()
            return
        to = point - self.her                               # A click is a little dash that way.
        n = max(1.0, math.hypot(to.x(), to.y()))
        self.velocity += QPointF(to.x() / n, to.y() / n) * self.height() * 1.1
        self.pointer = point

    def keyPressEvent(self, event):
        key = event.key()
        if key in self.KEYS:
            self.keys.add(self.KEYS[key])
        elif key in (Qt.Key_Escape, Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter):
            if self.flip0 < self.NEVER:
                if self.cards_done():
                    self.close()
            else:
                self.skip()

    def keyReleaseEvent(self, event):
        self.keys.discard(self.KEYS.get(event.key()))

    # Painting ---------------------------------------------------------------------------
    def framing(self):
        """(zoom, centre, darkness, flash, shake) of the openings happening now."""
        zoom, centre, dark, flash, shake = 1.0, QPointF(self.width() / 2, self.height() / 2), 0.0, 0.0, QPointF()
        t, h = self.t, self.height()
        for index, (touched, where) in self.touch.items():
            burst, rank = self.catch[index], self.rank(index)
            if not touched <= t <= burst + 1.6:
                continue
            env = _ease((t - touched) / .35) * (1 - _ease((t - burst - .7) / .8))
            if self.ZOOM[rank] * env > zoom - 1:
                zoom, centre = 1 + self.ZOOM[rank] * env, self.burst_at.get(index, where)
            dark = max(dark, self.DARK[rank] * env)
            flash = max(flash, self.FLASH[rank] * max(0.0, 1 - (t - burst) / .4) if t >= burst else 0)
            if rank == 4 and burst <= t <= burst + .4:          # Starsea shakes the sky.
                k = (1 - (t - burst) / .4) * h * .007
                shake = QPointF(math.sin(t * 91) * k, math.cos(t * 77) * k)
        return zoom, centre, dark, flash, shake

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        zoom, centre, dark, flash, shake = self.framing()
        p.save()
        p.translate(centre + shake)
        p.scale(zoom, zoom)
        p.translate(-centre)
        self._paint_sky(p)
        if dark > .01:
            p.fillRect(QRectF(-self.width(), -self.height(), self.width() * 3, self.height() * 3),
                       QColor(0, 0, 6, int(255 * dark)))
        p.setCompositionMode(QPainter.CompositionMode_Plus)
        self._paint_twinkles(p)
        self._paint_shower(p)
        for index in self.exclusive:
            self._paint_exclusive(p, index)
        if self.ten:
            self._paint_orbit(p, behind=True)
        for index in self.catch:                            # Catches light her from behind.
            self._paint_burst(p, index)
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        self._paint_her(p)
        p.setCompositionMode(QPainter.CompositionMode_Plus)
        if self.ten:
            self._paint_orbit(p, behind=False)
        self._paint_wishing_stars(p)
        for index in self.touch:
            self._paint_charge(p, index)
        if not self.ten:
            self._paint_found(p)
        if flash > .01:
            p.fillRect(QRectF(-self.width(), -self.height(), self.width() * 3, self.height() * 3),
                       QColor(255, 250, 240, int(255 * flash)))
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        p.restore()
        self._paint_results_backdrop(p)
        p.setCompositionMode(QPainter.CompositionMode_Plus)
        self._paint_card_lights(p)
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        self._paint_cards(p)
        p.setOpacity(1)
        self._paint_hud(p)
        p.end()

    def _paint_hud(self, p):
        w, h, t = self.width(), self.height(), self.t
        box = self.sound_rect()                             # Sound on / off.
        p.setPen(QPen(QColor(220, 215, 255, 150), 1))
        p.setBrush(QColor(20, 16, 50, 120))
        p.drawEllipse(box)
        p.setPen(QPen(QColor(235, 232, 255, 230), 1.6))
        c = box.center()
        cone = QPainterPath()
        cone.moveTo(c.x() - 8, c.y() - 3)
        cone.lineTo(c.x() - 4, c.y() - 3)
        cone.lineTo(c.x() + 1, c.y() - 8)
        cone.lineTo(c.x() + 1, c.y() + 8)
        cone.lineTo(c.x() - 4, c.y() + 3)
        cone.lineTo(c.x() - 8, c.y() + 3)
        cone.closeSubpath()
        p.setBrush(QColor(235, 232, 255, 230))
        p.drawPath(cone)
        p.setBrush(Qt.NoBrush)
        if self.sounds.enabled:
            p.drawArc(QRectF(c.x() - 3, c.y() - 5, 10, 10), -50 * 16, 100 * 16)
            p.drawArc(QRectF(c.x() - 5, c.y() - 9, 18, 18), -50 * 16, 100 * 16)
        else:
            p.drawLine(QPointF(c.x() + 4, c.y() - 4), QPointF(c.x() + 10, c.y() + 4))
            p.drawLine(QPointF(c.x() + 10, c.y() - 4), QPointF(c.x() + 4, c.y() + 4))
        p.setFont(QFont('Microsoft YaHei UI', 10))
        if self.cards_done():
            done = self._flip_time(9 if self.ten else 0) + self.FLIP + .15
            p.setPen(QColor(220, 220, 255, int(200 * _ease((t - done) / .3))))
            p.drawText(QRectF(0, h - 44, w, 26), Qt.AlignCenter, text('shop_wish_close', self.language))
            return
        if self.flip0 < self.NEVER and t > self.flip0 - .8:
            return                                          # No skipping once the cards are coming.
        fade = _ease((t - self.INTRO + .2) / .5) * (1 - _ease((t - self.flip0 + 1.2) / .4))
        if fade <= .01:
            return
        caught, total = len(self.results) - len(self.queue), len(self.results)
        hint = text('shop_wish_hint', self.language, caught=caught, total=total)
        p.setPen(QColor(232, 228, 255, int(220 * fade)))
        p.drawText(QRectF(0, h - 46, w, 26), Qt.AlignCenter, hint)
        box = self.skip_rect()
        p.setPen(QPen(QColor(220, 215, 255, int(150 * fade)), 1))
        p.setBrush(QColor(20, 16, 50, int(120 * fade)))
        p.drawRoundedRect(box, 16, 16)
        p.setPen(QColor(235, 232, 255, int(230 * fade)))
        p.drawText(box, Qt.AlignCenter, text('shop_wish_skip', self.language))

    def _paint_wishing_stars(self, p):
        """The stars she can catch: bright, slow, all alike until caught (no hint of rarity)."""
        h, t = self.height(), self.t
        hush = 1 - .85 * self.framing()[2]                  # A grand opening quiets the other stars.
        for star in self.stars:
            age = t - star['born']
            fade = _ease(age / .5) * hush
            v = star['vel']
            angle = math.degrees(math.atan2(v.y(), v.x()))
            trail = star['trail']
            for k, point in enumerate(reversed(trail)):      # Stardust it leaves behind.
                light(p, f'sparkle_{SHOWER[(star["id"] + k) % 4]}', point, h * (.045 - k * .0028),
                      fade * (1 - k / len(trail)) * .7)
            pulse = .9 + .1 * math.sin(t * 4 + star['phase'])
            streak(p, f'meteor_{star["key"]}', star['pos'], angle, h * .32, fade, grow=age / .6)
            light(p, f'sparkle_{star["key"]}', star['pos'], h * .16 * pulse, .55 * fade)
            play_loop(p, 'wishstar', star['pos'], h * .3 * pulse, age + star['phase'], fade)

    def _paint_charge(self, p, index):
        """Her star lights up in her hands, climbing the rarities until it reaches its own."""
        at, where = self.touch[index]
        t, h = self.t, self.height()
        if not at <= t < self.catch[index]:
            return
        f = (t - at) / self.CHARGE
        hand = self.hand()
        point = where + (hand - where) * _out(f / .35)
        rank = self.rank(index)
        step = min(rank, int(f * (rank + 1.0)))                 # Blue, then white, gold ... up to its own.
        shown = shop.RARITIES[step]
        grow = .6 + .8 * f
        play(p, 'charge', point, h * .42, t - at)
        play_loop(p, 'wishstar', point, h * .22 * grow, t * 1.5)
        light(p, f'hero_{shown}', point, h * .16 * grow, .45 + .45 * f, angle=t * 60)
        light(p, 'flare_gold' if shown == 'haori' else 'flare', point, h * (.5 + .6 * f), .3 + .4 * f)

    def _layer(self, name, cover):
        """A sky layer scaled to cover the window (scaled in the background)."""
        w, h = self.width(), self.height()
        key = (name, w, h)
        if key not in self._layers:
            self._prepare_layers()
        item = self._layers.get(key)
        if isinstance(item, Future):
            if not item.done():
                return None                                 # Still being scaled: the sky fades in anyway.
            item = item.result()
            self._layers[key] = item
        return item

    def _paint_sky(self, p):
        """Three layers drifting at different speeds (and a little with her): depth."""
        w, h, t = self.width(), self.height(), self.t
        p.fillRect(QRectF(-w, -h, w * 3, h * 3), QColor(3, 4, 16))
        drift = min(1.0, t / 16.0)
        lean = (self.her.x() / max(1, w) - .5)
        p.setOpacity(_ease(t / .5))
        for name, cover, speed, parallax, mode in (('sky_far', 1.12, .7, .014, None),
                                                    ('sky_dust', 1.24, 1.3, .045, QPainter.CompositionMode_Plus)):
            layer = self._layer(name, cover)
            if layer is None:
                continue
            sw, sh = layer.width() / layer.devicePixelRatio(), layer.height() / layer.devicePixelRatio()
            x = -(sw - w) * (.2 + .6 * drift * speed / 1.3) - lean * w * parallax
            y = -(sh - h) * (.55 - .25 * drift * speed / 1.3)
            if mode is not None:
                p.setCompositionMode(mode)
            p.drawImage(QPointF(round(x), round(y)), layer)
            p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        p.setOpacity(1)

    def _paint_twinkles(self, p):
        w, h, t = self.width(), self.height(), self.t
        fade = _ease(t / .6)
        for x, y, size, phase, speed, key in self.twinkles:
            a = max(0.0, math.sin(t * speed + phase)) ** 3
            if a > .02:
                light(p, f'sparkle_{key}', QPointF(x * w, y * h), size * h * (.7 + .5 * a), a * .9 * fade,
                      angle=15 * math.sin(t * .5 + phase))

    def _paint_shower(self, p):
        w, h, t = self.width(), self.height(), self.t
        radiant = QPointF(w * 1.22, -h * .38)
        focus = 1.0
        if not self.ten:                                    # The sky hushes while hers comes.
            focus = 1 - .45 * math.exp(-((t - self.catch.get(0, self.NEVER) + .3) / .7) ** 2)
        for at, life, x, y, depth, key in self.shower:
            age = t - at
            if not 0 <= age <= life:
                continue
            f = age / life
            centre = QPointF(x * w, y * h)
            d = centre - radiant
            n = math.hypot(d.x(), d.y()) or 1
            ux, uy = d.x() / n, d.y() / n
            speed = h * (.45 + .75 * depth)
            head = centre + QPointF(ux, uy) * (speed * (age - life * .4))
            angle = math.degrees(math.atan2(uy, ux))
            env = _ease(f / .12) * (1 - _ease((f - .5) / .5))
            alpha = env * (.3 + .7 * depth) * focus
            thin = depth < .5
            length = h * (.14 + .36 * depth)
            streak(p, f'meteor_{key}{"_thin" if thin else ""}', head, angle, length, alpha, grow=f / .3)
            if depth > .62:                                 # The near ones shed sparkles behind them.
                seed = int(at * 1000)
                for j in range(1, 7):
                    back = j * .055
                    if age - back < 0:
                        break
                    was = centre + QPointF(ux, uy) * (speed * (age - back - life * .4))
                    drift = ((seed * (j + 3)) % 17 - 8) / 8 * h * .02 * back * 4
                    q = was + QPointF(-uy * drift, ux * drift)
                    light(p, f'sparkle_{SHOWER[(seed + j) % 4]}', q, h * .026 * depth * (1 - j / 8),
                          alpha * (1 - j / 7) * .8)
            if depth > .72:                                 # The near ones flare at the head.
                flicker = .75 + .25 * math.sin(t * 31 + at * 17)
                light(p, f'sparkle_{key}', head, h * .05 * depth * flicker, alpha * .8, angle=angle * .2)
            if depth > .93 and f > .82:                     # A fireball bursts as it burns out.
                pop = math.sin(math.pi * (f - .82) / .18)
                light(p, f'sparkle_{key}', head, h * .14 * pop, pop * env * focus)
                light(p, 'flare', head, h * .5 * pop, pop * .5 * focus)

    def _paint_burst(self, p, index):
        """The catch: its rarity's burst (After Effects), with a lens streak across the sky."""
        t = self.t - self.catch[index]
        if not 0 <= t <= 1.7:
            return
        h, w = self.height(), self.width()
        rarity, rank = self.rarity(index), self.rank(index)
        strength = (1 + rank) / 5 * (1.0 if not self.ten or index == self.best else .5)
        if index in self.exclusive:
            self.burst_at.setdefault(index, QPointF(self.width() / 2, self.height() / 2))
        centre = self.burst_at.setdefault(index, QPointF(self.hand()))
        tall = h * (1.0 + .6 * strength)                    # The beam shoots up from the catch.
        play(p, f'pillar_{rarity}', centre - QPointF(0, tall * .47), tall * .25, t, height=tall)
        if not play(p, f'reveal_{rarity}', centre, h * (.55 + .55 * strength), t):
            light(p, f'shock_{rarity}', centre, h * (.15 + 1.1 * strength) * _out(t / .9), 1 - _ease(t / 1.0))
        light(p, 'flare_gold' if rarity == 'haori' else 'flare', centre, w * (.45 + .55 * strength),
              (1 - _ease(t / .7)) * (.35 + .5 * strength))

    def _paint_exclusive(self, p, index):
        """Galaxy and Starsea: their own opening around her hands before the burst."""
        start = self.exclusive[index]
        t = self.t - start
        if not 0 <= t <= self.EXCLUSIVE + .4:
            return
        middle = QPointF(self.width() / 2, self.height() / 2)
        w = self.width() * 1.25
        fade = _ease(t / .25) * (1 - .35 * math.exp(-((t - self.EXCLUSIVE) / .12) ** 2))
        play(p, f'exclusive_{self.rarity(index)}', middle, w, t, alpha=fade, height=w * 9 / 16)

    def _emblem(self, p, rarity, centre, width, alpha, t):
        """A find's star (After Effects loop); the drawn look while the loop is missing."""
        if seq_length(f'emblem_{rarity}'):
            play_loop(p, f'emblem_{rarity}', centre, width * 1.25, t, alpha)
        else:
            self._star_look(p, rarity, centre, width, alpha, t)

    def _star_look(self, p, rarity, centre, width, alpha, t):
        """A find's light, alive: each rarity moves in its own way."""
        if rarity == 'fanxing':                             # A twinkle that turns a little.
            light(p, 'hero_fanxing', centre, width, alpha, angle=8 * math.sin(t * 1.3))
            light(p, 'hero_fanxing', centre, width * .7, alpha * .35 * (.5 + .5 * math.sin(t * 4)), angle=45)
        elif rarity == 'mingyue':                           # The moon flashes white.
            flash = .78 + .22 * max(0.0, math.sin(t * 3.2)) ** 6
            light(p, 'hero_mingyue', centre, width * (1.15 + .03 * flash), alpha * flash)
            light(p, 'sparkle_mingyue', centre, width * .5, alpha * (.3 + .7 * max(0.0, math.sin(t * 3.2)) ** 12))
        elif rarity == 'haori':                             # The sun's rays turn.
            light(p, 'rays_haori', centre, width * 1.3, alpha * .45, angle=-t * 12)
            light(p, 'hero_haori', centre, width, alpha, angle=t * 8)
        elif rarity == 'yinhe':                             # A tilted silver galaxy, turning.
            light(p, 'hero_yinhe', centre, width * 1.55, alpha, angle=t * 35, squash=.6, tilt=-18)
            light(p, 'sparkle_yinhe', centre, width * .35, alpha * .8)
        else:                                               # Prism star in turning rainbow rings.
            light(p, 'rays_xinghai', centre, width * 1.4, alpha * .35, angle=t * 10)
            light(p, 'hero_xinghai_ring', centre, width * 1.15, alpha * .9, angle=t * 50, squash=.62, tilt=-14)
            light(p, 'hero_xinghai_ring', centre, width * .8, alpha * .5, angle=-t * 70, squash=.9)
            light(p, 'hero_xinghai', centre, width, alpha * .7, angle=t * 6)

    def _paint_found(self, p):
        """One wish: the caught star rises from her hands, grows, then becomes the card."""
        t, h = self.t, self.height()
        at = self.catch.get(0, self.NEVER)
        if not at <= t < self.flip0 + .3:
            return
        rarity, rank = self.rarity(0), self.rank(0)
        rise = _out((t - at) / .9)
        hand = self.hand()
        above = hand + QPointF(self.width() * .13, -h * .17) * rise
        width = h * (.06 + (.36 + .04 * rank) * rise)
        point = above
        self._emblem(p, rarity, point, width, _ease((t - at - .1) / .35) * (1 - _ease((t - self.flip0 + .5) / .4)), t)

    def _orbit_point(self, k, t):
        pos, size, lean, left = self.her_place()
        angle = k * math.tau / 10 + t * .9
        return QPointF(pos.x() + math.cos(angle) * size * .72, pos.y() - size * .08 + math.sin(angle) * size * .2), \
            math.sin(angle)

    def _paint_orbit(self, p, behind):
        """Ten wishes: each caught star circles her until the cards come."""
        t, h = self.t, self.height()
        for k, index in enumerate(self.order):
            at = self.catch.get(index, self.NEVER)
            if t < at:
                continue
            point, depth = self._orbit_point(k, t)
            settle = _out((t - at) / .4)
            point = self.hand() + (point - self.hand()) * settle
            fly = 0.0
            if (depth < 0) != behind:
                continue
            rarity, rank = self.rarity(index), self.rank(index)
            width = h * (.09 + .02 * rank)
            dim = .55 if depth < 0 else 1.0
            fade = 1 - _ease((t - self.flip0 + .7) / .5)     # Gone before the cards turn.
            if fade > 0:
                self._emblem(p, rarity, point, width, dim * fade, t + k)

    def _paint_her(self, p):
        pos, size, lean, facing_left = self.her_place()
        if pos.x() < -size:
            return
        name = self.pose_name()
        sprite = self.pose(name, self.height() * (.34 if self.ten else .40))
        if sprite is None:
            return
        p.setCompositionMode(QPainter.CompositionMode_Plus)    # Her own soft light, and a stardust wake.
        light(p, 'sparkle_lavender', pos, size * 1.3, .35)
        for k, (at, was) in enumerate(reversed(self.wake[::3])):
            if k >= 14 or at < .7:
                break
            light(p, f'sparkle_{SHOWER[k % 4]}', was + QPointF(0, size * .18), size * (.16 - k * .009),
                  .5 * (1 - k / 14))
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        sw = sprite.width() * size / sprite.height()
        p.save()
        p.translate(pos)
        p.rotate(lean)
        if facing_left:
            p.scale(-1, 1)
        p.setOpacity(_ease((self.t - .7) / .3))
        p.drawImage(QRectF(-sw / 2, -size / 2, sw, size), sprite, QRectF(sprite.rect()))
        p.restore()

    FLIP = .26                    # How long one card takes to turn.
    STAGGER = .07                 # Between one card and the next.

    def _flip_time(self, k):
        return self.flip0 + (k * self.STAGGER if self.ten else 0)

    def cards_done(self):
        """Every card has turned (only then does a click close)."""
        last = self._flip_time(9 if self.ten else 0)
        return self.flip0 < self.NEVER and self.t > last + self.FLIP + .15

    def _paint_results_backdrop(self, p):
        """When the cards come, the sky steps back so they stand out."""
        if self.flip0 >= self.NEVER:
            return
        f = _ease((self.t - self.flip0 + .4) / .6)
        if f > .01:
            p.fillRect(self.rect(), QColor(2, 2, 10, int(110 * f)))

    def _paint_card_lights(self, p):
        """Behind each turned card its own beam of light, and its star above it."""
        for k, index in enumerate(self.order if self.ten else [0]):
            flip = self._flip_time(k)
            f = _ease((self.t - flip) / .45)
            if f <= 0:
                continue
            centre, (cw, ch) = self.slot(k)
            rarity, rank = self.rarity(index), self.rank(index)
            beam = (.55 + .12 * rank) * f
            play_loop(p, f'cardbeam_{rarity}', centre, cw * 2.1, self.t + k * .37, beam, height=ch * 1.6)
            if rank >= 2:                                   # A fine card shoots a beam as it turns.
                play(p, f'pillar_{rarity}', centre - QPointF(0, ch * .1), cw * 1.6, self.t - flip, .8,
                     height=ch * 2.0)

    def _paint_cards(self, p):
        for k, index in enumerate(self.order if self.ten else [0]):
            f = (self.t - self._flip_time(k)) / self.FLIP
            if f <= 0:
                continue
            centre, (cw, ch) = self.slot(k)
            self._card(p, index, centre, cw, ch, f)

    def _card(self, p, index, centre, cw, ch, f):
        """A result card: its frame (rendered, tools/render_card_frames.py), the find's picture on
        the face, its name on the plate and its rarity under the plate's line."""
        from shop_view import draw_item, item_name
        result = self.results[index]
        item = result['item']
        colour = self.colour(index)
        rank = self.rank(index)
        rarity = self.rarity(index)
        rise = (1 - _out(min(1.0, f))) * ch * .06            # It rises a little as it turns.
        flipped = max(.02, abs(math.cos(math.pi * (1 - _back(min(1.0, f))) / 2))) if f < 1 else 1.0
        p.save()
        p.translate(centre + QPointF(0, rise))
        p.scale(flipped, 1.0)
        box = QRectF(-cw / 2, -ch / 2, cw, ch)
        ratio = self.devicePixelRatioF()
        job = self._frames.get((rarity, int(cw * ratio), int(ch * ratio)))
        frame = job.result() if job is not None else None
        if frame is not None:
            p.drawImage(box, frame, QRectF(frame.rect()))
        else:
            p.setPen(QPen(colour, 2))
            p.setBrush(QColor(14, 12, 36, 240))
            p.drawRoundedRect(box, cw * .1, cw * .1)
        p.setCompositionMode(QPainter.CompositionMode_Plus)
        face = QPainterPath()
        face.addRoundedRect(box.adjusted(cw * .05, ch * .04, -cw * .05, -ch * .02), cw * .06, cw * .06)
        p.setClipPath(face)
        self._emblem(p, rarity, QPointF(0, -ch * .13), cw * 1.05, .5, self.t + index)   # Its star behind the art.
        p.setClipping(False)
        if rank >= 3:                                       # Fine cards keep a light running over them.
            y = -ch / 2 + ch * ((self.t * .45 + index * .13) % 1.3 - .15)
            g = QLinearGradient(QPointF(0, y - ch * .08), QPointF(0, y + ch * .08))
            g.setColorAt(0, QColor(255, 255, 255, 0))
            g.setColorAt(.5, _rgba(colour, 40))
            g.setColorAt(1, QColor(255, 255, 255, 0))
            path = QPainterPath()
            path.addRoundedRect(box.adjusted(cw * .05, ch * .04, -cw * .05, -ch * .02), cw * .06, cw * .06)
            p.setClipPath(path)
            p.fillRect(box, g)
            p.setClipping(False)
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        art = min(cw * .86, ch * .36)
        job = self._art.get(index)
        picture = job.result() if job is not None else None
        if picture is not None:
            aw, ah = picture.width() / picture.devicePixelRatio(), picture.height() / picture.devicePixelRatio()
            p.drawImage(QRectF(-aw / 2, -ch * .13 - ah / 2, aw, ah), picture, QRectF(picture.rect()))
        else:
            draw_item(p, item, QRectF(-art / 2, -ch * .13 - art / 2, art, art), colour)
        shine = (f - 1) / .5                                 # A gleam sweeps down once.
        if 0 < shine < 1:
            y = -ch * .6 + ch * 1.2 * shine
            g = QLinearGradient(QPointF(0, y - ch * .1), QPointF(0, y + ch * .1))
            g.setColorAt(0, QColor(255, 255, 255, 0))
            g.setColorAt(.5, QColor(255, 255, 255, 70 + 20 * rank))
            g.setColorAt(1, QColor(255, 255, 255, 0))
            path = QPainterPath()
            path.addRoundedRect(box.adjusted(cw * .05, ch * .04, -cw * .05, -ch * .02), cw * .06, cw * .06)
            p.setClipPath(path)
            p.fillRect(box, g)
            p.setClipping(False)
        size = max(8, int(min(cw * .12, ch * .046)))
        p.setPen(QColor('#FFFFFF'))
        p.setFont(QFont('Microsoft YaHei UI', size, QFont.Bold))
        p.drawText(QRectF(-cw * .4, ch * .205, cw * .8, ch * .12), Qt.AlignCenter | Qt.TextWordWrap,
                   item_name(item, self.language))
        p.setPen(_rgba(colour.lighter(130), 255))
        p.setFont(QFont('Microsoft YaHei UI', max(7, int(size * .78)), QFont.DemiBold))
        p.drawText(QRectF(-cw * .4, ch * .335, cw * .8, ch * .06), Qt.AlignCenter,
                   text(f'shop_rarity_{item["rarity"]}', self.language))
        if result['refund']:
            p.setPen(QColor(220, 215, 255))
            p.setFont(QFont('Microsoft YaHei UI', max(7, int(size * .7))))
            p.drawText(QRectF(-cw / 2, ch * .41, cw, ch * .06), Qt.AlignCenter,
                       text('shop_refund', self.language, points=result['refund']))
        p.restore()
