"""One projected halo clock and two compact, input-transparent depth layers."""
from collections import deque
import math
import sys

from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QRadialGradient, QPolygonF
from PySide6.QtWidgets import QWidget

import halo_geometry as geometry
import pet_geometry


class HaloLayer(QWidget):
    AGE = 3.6
    MAX_SAMPLES = 96

    def __init__(self, front):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint
                         | Qt.WindowStaysOnTopHint | Qt.WindowTransparentForInput)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.front = front
        self.pose = None
        self.now = 0.0
        self.stars = {}
        self._trails = {}

    def record_sample(self, identity, x, y, stamp, depth=0.0):
        self._trails.setdefault(identity, deque(maxlen=self.MAX_SAMPLES)).append(
            (x, y, stamp, depth))

    def prune(self, now):
        self.now = now
        for key, trail in list(self._trails.items()):
            while trail and now - trail[0][2] > self.AGE:
                trail.popleft()
            if not trail:
                del self._trails[key]

    def drop(self, key):
        return self._trails.pop(key, None) is not None

    def clear_all(self):
        had = bool(self._trails)
        self._trails.clear()
        self.update()
        return had

    def has_trails(self):
        return any(len(t) > 1 for t in self._trails.values())

    def trail_length(self, key):
        return len(self._trails.get(key, ()))

    def set_scene(self, pose, now):
        self.pose = pose
        self.prune(now)
        bounds = list(geometry.projected_bounds(pose))
        for trail in self._trails.values():
            for x, y, _, _ in trail:
                bounds[0] = min(bounds[0], x - 12)
                bounds[1] = min(bounds[1], y - 12)
                bounds[2] = max(bounds[2], x + 12)
                bounds[3] = max(bounds[3], y + 12)
        left, top = math.floor(bounds[0]), math.floor(bounds[1])
        width, height = math.ceil(bounds[2]) - left + 1, math.ceil(bounds[3]) - top + 1
        if (self.x(), self.y(), self.width(), self.height()) != (left, top, width, height):
            self.setGeometry(left, top, width, height)
        self.update()

    def paintEvent(self, event):
        if self.pose is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        start = 0 if self.front else math.pi
        path = QPainterPath()
        for i in range(97):
            x, y, _ = geometry.project(self.pose, start + math.pi * i / 96)
            point = QPointF(x - self.x(), y - self.y())
            path.moveTo(point) if i == 0 else path.lineTo(point)
        for width, color in ((13, QColor(132, 112, 255, 22 if self.front else 13)),
                             (7, QColor(158, 144, 255, 42 if self.front else 25)),
                             (3.4, QColor(177, 177, 255, 165 if self.front else 105)),
                             (1.15, QColor(252, 250, 255, 255 if self.front else 215))):
            pen = QPen(color, width)
            pen.setCapStyle(Qt.RoundCap)
            painter.setPen(pen)
            painter.drawPath(path)
        # All ornament shares the projected plane and existing clock, and
        # stays inside the hit-disc margin; no extra native input surfaces.
        inlay = QPainterPath()
        inset = self.pose._replace(rx=self.pose.rx - 4, ry=self.pose.ry - 4)
        for i in range(33):
            x, y, _ = geometry.project(inset, start + math.pi * (.15 + .55 * i / 32))
            point = QPointF(x - self.x(), y - self.y())
            inlay.moveTo(point) if i == 0 else inlay.lineTo(point)
        painter.setPen(QPen(QColor(255, 218, 170, 210 if self.front else 145), 1.0))
        painter.drawPath(inlay)
        outer = self.pose._replace(rx=self.pose.rx + 11, ry=self.pose.ry + 8)
        guide = QPainterPath()
        for begin, end in ((.01, .47), (.53, .99)):
            for i in range(25):
                x, y, _ = geometry.project(outer, start + math.pi * (begin + (end - begin) * i / 24))
                point = QPointF(x - self.x(), y - self.y())
                guide.moveTo(point) if i == 0 else guide.lineTo(point)
        pen = QPen(QColor(173, 153, 255, 210 if self.front else 150), 1.0)
        pen.setDashPattern([1.5, 4])
        painter.setPen(pen)
        painter.drawPath(guide)
        for index in range(12):
            angle = start + math.pi * (index + .4) / 12
            x, y, _ = geometry.project(outer if index % 3 else inset, angle)
            point = QPointF(x - self.x(), y - self.y())
            strength = .8 + .2 * math.sin(self.now * 1.8 + index * 2.4)
            glow = QRadialGradient(point, 8)
            glow.setColorAt(0, QColor(205, 190, 255, int(155 * strength)))
            glow.setColorAt(1, QColor(160, 140, 255, 0))
            painter.setPen(Qt.NoPen)
            painter.setBrush(glow)
            painter.drawEllipse(point, 8, 8)
            painter.setPen(QPen(QColor(172, 151, 246, 225), .7))
            painter.setBrush(QColor(250, 245, 255, 245 if self.front else 190))
            if index % 3 == 0:
                size = 3.2 if index % 2 == 0 else 2.4
                painter.drawPolygon(QPolygonF([point + QPointF(0, -size * 1.5),
                                                point + QPointF(size, 0),
                                                point + QPointF(0, size * 1.5),
                                                point + QPointF(-size, 0)]))
            else:
                radius = 1.6 if index % 2 else 2.3
                painter.drawEllipse(point, radius, radius)
        for x, y, depth in self.stars.values():
            if (depth >= 0) != self.front:
                continue
            x, y = x - self.x(), y - self.y()
            painter.setPen(QPen(QColor(220, 198, 166, 155 if self.front else 80), .65))
            painter.drawLine(QPointF(x, y + 19), QPointF(x, y + geometry.LABEL_TOP))
            painter.setBrush(QColor('#f7f6ff'))
            painter.drawEllipse(QPointF(x, y + 24), 1.1, 1.1)
        for trail in self._trails.values():
            for first, last in zip(trail, list(trail)[1:]):
                x, y, stamp, depth = last
                if (depth >= 0) != self.front:
                    continue
                fade = max(0.0, 1 - (self.now - stamp) / self.AGE) ** 1.5
                if fade == 0:
                    continue
                strength = fade * (.60 + .40 * (depth + 1) / 2)
                a, b = QPointF(first[0] - self.x(), first[1] - self.y()), QPointF(x - self.x(), y - self.y())
                for width, color in ((8, QColor(158, 144, 255, int(30 * strength))),
                                     (2.5, QColor(184, 218, 255, int(150 * strength))),
                                     (.9, QColor(252, 249, 255, int(230 * strength)))):
                    pen = QPen(color, width * (.7 + .3 * fade))
                    pen.setCapStyle(Qt.RoundCap)
                    painter.setPen(pen)
                    painter.drawLine(a, b)
            # A few pearl motes recede along the ribbon, never a particle cloud.
            for x, y, stamp, depth in list(trail)[::18]:
                age = self.now - stamp
                if .35 < age < self.AGE and (depth >= 0) == self.front:
                    fade = (1 - age / self.AGE) ** 1.5
                    painter.setPen(Qt.NoPen)
                    painter.setBrush(QColor(212, 204, 255, int(160 * fade)))
                    radius = .8 + .5 * (depth + 1) / 2
                    painter.drawEllipse(QPointF(x - self.x(), y - self.y()), radius, radius)


class HaloScene:
    """Mixin keeping projected motion separate from historical exterior routes."""

    def _init_halo(self):
        self._halo_pose = None
        self._halo_target = None
        self._halo_offsets = {}
        self._halo_targets = {}
        self._halo_depths = {}
        self._halo_stack = None
        self.back_overlay = HaloLayer(False)
        self.trail_overlay = HaloLayer(True)

    def _clear_trails(self):
        self.trail_overlay.clear_all()
        if not self.legacy_exterior_motion:
            self.back_overlay.clear_all()

    def _fit_halo_pose(self, pet, screen):
        placement = getattr(getattr(self.panel, 'pet', None), 'halo_placement', None)
        companion = getattr(self.panel, 'pet', None)
        if (placement is not None and tuple(pet) == placement.pet_rect
                and tuple(screen) == getattr(companion, 'halo_screen_rect', None)):
            if placement.pose is not None:
                return placement.pose
            # Impossible workareas keep a centered decorative hoop; fixed hit
            # containment is unavailable here, never an excuse for a GUI crash.
            return geometry.HaloPose(pet[0] + pet[2] / 2, pet[1] + pet[3] * .60,
                                     max(12, min(pet[2] * .58, (screen[2] - screen[0]) / 2)),
                                     max(12, min(pet[3] * .25, (screen[3] - screen[1]) / 2)),
                                     geometry.DEFAULT_TILT)
        return geometry.fit_pose(pet, screen)

    def _halo_apply(self, pet, screen):
        target = self._fit_halo_pose(pet, screen)
        self._halo_target = target
        if self._halo_pose is None:
            self._halo_pose = target
        keys = sorted(self._windows, key=lambda k: self._slots[k])
        offsets = geometry.phase_offsets(self._slots[k] for k in keys)
        survivors = [k for k in keys if k in self._halo_offsets]
        if not survivors:
            self._halo_pose = target
        shift = (self._halo_offsets[survivors[0]] - offsets[self._slots[survivors[0]]]
                 if survivors else 0.0)
        self._halo_targets = {k: offsets[self._slots[k]] + shift for k in keys}
        old = {k: self._halo_offsets[k] for k in survivors}
        # Unwrap cyclic order before interpolating. Removing tasks enlarges gaps;
        # new tasks stay staged until the equally spaced destinations are ready.
        for index, key in enumerate(survivors):
            if index:
                while old[key] <= old[survivors[index - 1]]:
                    old[key] += math.tau
            target_angle = self._halo_targets[key]
            while target_angle < old[survivors[0]] - .001:
                target_angle += math.tau
            self._halo_targets[key] = target_angle
        newcomers = set(keys) - set(old)
        self._halo_offsets = old
        transitioning = any(abs(old[k] - self._halo_targets[k]) > .001 for k in old)
        if transitioning:
            self._stage_keys(newcomers)
        else:
            self._halo_offsets.update(self._halo_targets)
            self._ring_staged.clear()
        self._ring_offsets = dict(self._halo_offsets)
        self._orbit_mode = ('halo',)
        self._last_motion_enabled = self._motion_enabled()
        self._halo_commit(self._last_tick or 0.0, record=False)
        self.sync_motion()

    def _halo_positions(self):
        centers, depths = {}, {}
        if self._halo_pose is not None:
            for key, offset in self._halo_offsets.items():
                if key not in self._windows or key in self._ring_staged:
                    continue
                x, y, depth = geometry.project(self._halo_pose, self._ring_t * math.tau / 24 + offset)
                centers[key], depths[key] = (x, y), depth
        return centers, depths

    def _halo_pending(self):
        return (self._halo_pose != self._halo_target
                or any(abs(self._halo_offsets.get(k, v) - v) > .001
                       for k, v in self._halo_targets.items()) or bool(self._ring_staged))

    def _tick_halo(self, now, pet, screen):
        if self._shutdown or not self._visible:
            self._last_tick = None
            return
        target = self._fit_halo_pose(pet, screen)
        self._halo_target = target
        dt = 0 if self._last_tick is None else max(0.0, min(.04, now - self._last_tick))
        self._last_tick = now
        enabled = self._motion_enabled()
        if enabled != self._last_motion_enabled:
            self._clear_interaction_holds()
            self._last_motion_enabled = enabled
        held = bool(self._hover_holds or self._press_holds)
        if dt and not held:
            # Convex interpolation between fitted poses preserves screen bounds.
            # Budget translation and angular recomposition before adding orbit.
            delta = [b - a for a, b in zip(self._halo_pose, target)]
            cost = abs(delta[0]) + abs(delta[1]) + abs(delta[2]) + abs(delta[3])
            fraction = min(1.0, (6 * dt / .04) / cost) if cost else 1.0
            self._halo_pose = geometry.HaloPose(*(a + fraction * d for a, d in zip(self._halo_pose, delta)))
            largest = max((abs(self._halo_targets[k] - v) for k, v in self._halo_offsets.items()), default=0)
            angular = min(1.0, .018 * dt / .04 / largest) if largest else 1.0
            for key in self._halo_offsets:
                self._halo_offsets[key] += (self._halo_targets[key] - self._halo_offsets[key]) * angular
            if angular == 1:
                self._halo_offsets = dict(self._halo_targets)
                self._ring_staged.clear()
            if enabled:
                self._ring_t += dt
                self._motion_t += dt
        self._ring_offsets = dict(self._halo_offsets)
        self._last_pet_rect, self._last_screen_rect = pet, screen
        self._halo_commit(now, record=bool(dt and enabled and not held))
        self.sync_motion()

    def _halo_commit(self, now, record):
        centers, depths = self._halo_positions()
        self._halo_depths = depths
        for key, (x, y) in centers.items():
            orb = self._windows[key]
            position = pet_geometry.star_center_to_window_position(x, y)
            if self._placed.get(key) != position:
                orb.move(*position)
                self._placed[key] = position
            orb.depth = depths[key]
            orb.star_scale = .57 + .13 * (depths[key] + 1) / 2
            paint = (round(orb.depth, 3), round(orb.star_scale, 3))
            if paint != getattr(orb, '_halo_paint', None):
                orb.update()
                orb._halo_paint = paint
            if self._visible:
                orb.show()
            else:
                orb.hide()
            if record:
                for layer in (self.back_overlay, self.trail_overlay):
                    layer.record_sample(key, x, y, now, depths[key])
        for layer in (self.back_overlay, self.trail_overlay):
            layer.stars = {k: (self._placed[k][0] + pet_geometry.TASK_STAR_CENTER[0],
                               self._placed[k][1] + pet_geometry.TASK_STAR_CENTER[1],
                               depths[k]) for k in centers}
            for key in set(layer._trails) - set(self._windows):
                layer.drop(key)
            layer.set_scene(self._halo_pose, now)
            layer.setVisible(self._visible)
        if self.page_controls is not None:
            self._update_page_controls()
        self._stack_halo()

    def capture_windows(self):
        pet = getattr(self.panel, 'pet', None)
        back = [w for k, w in self._windows.items() if self._halo_depths.get(k, 0) < 0]
        front = [w for k, w in self._windows.items() if self._halo_depths.get(k, 0) >= 0]
        result = [self.back_overlay, *back, pet, self.trail_overlay, *front]
        if self.page_controls is not None:
            result.append(self.page_controls)
        if self.detail_window is not None:
            result.append(self.detail_window)
        transition = getattr(self, 'detail_transition', None)
        if transition is not None and transition.overlay is not None:
            result.append(transition.overlay)
        return [w for w in result if w is not None and w.isVisible()]

    def _stack_halo(self, force=False):
        windows = self.capture_windows()
        signature = tuple(int(w.winId()) for w in windows)
        if sys.platform == 'win32' and not force and signature == self._halo_stack:
            import ctypes
            from ctypes import wintypes
            get_window = getattr(self, '_halo_get_window', None)
            if get_window is None:
                get_window = ctypes.WinDLL('user32', use_last_error=True).GetWindow
                get_window.argtypes = (wintypes.HWND, wintypes.UINT)
                get_window.restype = wintypes.HWND
                self._halo_get_window = get_window
            # Clicking/raising the pet changes actual HWND order even when
            # depths and handles are unchanged. The cached signature alone
            # cannot prove that the front plane is still in front.
            force = any(get_window(lower, 3) != upper
                        for lower, upper in zip(signature, signature[1:]))
        if force or signature != self._halo_stack:
            pet = getattr(self.panel, 'pet', None)
            if sys.platform == 'win32' and pet in windows:
                import ctypes
                from ctypes import wintypes
                user32 = ctypes.WinDLL('user32', use_last_error=True)
                get_window = user32.GetWindow
                get_window.argtypes = (wintypes.HWND, wintypes.UINT)
                get_window.restype = wintypes.HWND
                set_position = user32.SetWindowPos
                set_position.argtypes = (wintypes.HWND, wintypes.HWND,
                                         ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                         ctypes.c_int, wintypes.UINT)
                set_position.restype = wintypes.BOOL
                # Preserve the pet's place among other applications. Relative
                # insertion changes only our depth order, without activation.
                flags = 0x0001 | 0x0002 | 0x0010 | 0x0200
                index = windows.index(pet)
                anchor = signature[index]
                for handle in reversed(signature[:index]):
                    if not set_position(handle, anchor, 0, 0, 0, 0, flags):
                        raise ctypes.WinError(ctypes.get_last_error())
                    anchor = handle
                anchor = signature[index]
                for handle in signature[index + 1:]:
                    previous = get_window(anchor, 3)  # GW_HWNDPREV, directly above.
                    if previous != handle:
                        if not set_position(handle, previous or 0, 0, 0, 0, 0, flags):
                            raise ctypes.WinError(ctypes.get_last_error())
                    anchor = handle
            else:
                for window in windows:
                    window.raise_()
            self._halo_stack = signature
