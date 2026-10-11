"""Offline renderer for the wishing show's light effects (2.5).

Run with any Python that has numpy (Blender's bundled one works):

    "D:/Program Files/Blender Foundation/Blender 5.2/5.2/python/bin/python.exe" tools/render_wish_fx.py

Everything is rendered as light energy on black in linear space, then given
real bloom (several blur radii), diffraction spikes and lens streaks, tone
mapped and gamma encoded. The show draws these additively, so black adds
nothing and the glows mix like light instead of looking like stickers.

Writes PNGs into build/wish_fx_png/; tools/pack_wish_fx.py turns the sky into JPEG
and the sprites into WebP under assets/v2_5/wish/.
"""
from __future__ import annotations

import colorsys
import math
import os
import struct
import sys
import zlib

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'build', 'wish_fx_png')
RNG = np.random.default_rng(20261011)

# The star palette (task stars and ring skins) and the five rarities.
PALETTE = dict(ice=(.55, .78, 1.0), champagne=(1.0, .80, .55), lavender=(.72, .60, 1.0), pearl=(.92, .93, 1.0))
RARITY = dict(fanxing=(.22, .40, 1.0), mingyue=(.96, .98, 1.0), haori=(1.0, .66, .18),
              yinhe=(.70, .80, 1.0), xinghai=None)


# Helpers ------------------------------------------------------------------------------------
def edge_window(h, w, radial):
    """Fades a sprite to pure black before its border so no square edge ever shows."""
    y, x = np.mgrid[0:h, 0:w].astype(float)
    if radial:
        r = np.hypot(x - w / 2 + .5, y - h / 2 + .5) / (min(w, h) / 2)
        f = np.clip((1 - r) / .35, 0, 1)
    else:
        m = min(h, w) * .18
        f = np.clip(np.minimum.reduce([x, w - 1 - x, y, h - 1 - y]) / m, 0, 1)
    return (f * f * (3 - 2 * f))[..., None]


def save_png(name, rgb, window=None):
    """rgb: HxWx3 floats in 0..1 (display space). ``window``: 'radial', 'box' or None."""
    os.makedirs(OUT, exist_ok=True)
    if window:
        rgb = rgb * edge_window(rgb.shape[0], rgb.shape[1], window == 'radial')
    data = (np.clip(rgb, 0, 1) * 255 + .5).astype(np.uint8)
    h, w, _ = data.shape
    raw = b''.join(b'\x00' + data[y].tobytes() for y in range(h))

    def chunk(kind, body):
        return struct.pack('>I', len(body)) + kind + body + struct.pack('>I', zlib.crc32(kind + body) & 0xffffffff)
    png = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
           + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))
    with open(os.path.join(OUT, name + '.png'), 'wb') as f:
        f.write(png)
    print('wrote', name, w, h)


def blur(img, sigma):
    if sigma <= 0:
        return img
    h, w = img.shape[:2]
    fy = np.fft.fftfreq(h)[:, None]
    fx = np.fft.rfftfreq(w)[None, :]
    k = np.exp(-2 * np.pi ** 2 * sigma * sigma * (fx * fx + fy * fy))
    if img.ndim == 2:
        return np.fft.irfft2(np.fft.rfft2(img) * k, s=(h, w))
    return np.stack([np.fft.irfft2(np.fft.rfft2(img[..., c]) * k, s=(h, w)) for c in range(img.shape[2])], -1)


def convolve(img, kernel):
    """FFT convolution with a kernel of the same size whose centre is at the middle."""
    h, w = img.shape[:2]
    if kernel.ndim == 2:
        kernel = np.repeat(kernel[..., None], 3, -1)
    if img.ndim == 2 or img.shape[2] == 1:
        img = np.repeat(img.reshape(h, w, 1), 3, -1)
    return np.stack([np.fft.irfft2(np.fft.rfft2(img[..., c]) * np.fft.rfft2(np.fft.ifftshift(kernel[..., c])),
                                   s=(h, w)) for c in range(3)], -1)


def bloom(energy, radii=((1.5, .7), (5, .45), (16, .28), (40, .1))):
    out = energy.copy()
    for sigma, weight in radii:
        out += weight * blur(energy, sigma)
    return out


def spikes(h, w, arms, length, width=.9, falloff=None, chroma=0.0):
    """A diffraction kernel: thin lines out of the centre, fading with distance.
    ``arms``: list of (angle degrees, relative length, strength)."""
    y, x = np.mgrid[0:h, 0:w].astype(float)
    x -= w / 2
    y -= h / 2
    k = np.zeros((h, w, 3))
    for angle, rel, strength in arms:
        a = math.radians(angle)
        along = x * math.cos(a) + y * math.sin(a)
        across = -x * math.sin(a) + y * math.cos(a)
        for c, stretch in enumerate((1 + chroma, 1.0, 1 - chroma)):      # Chromatic: red reaches further.
            reach = length * rel * stretch
            line = np.exp(-np.abs(along) / (reach * .35)) * np.exp(-(across / width) ** 2)
            line *= np.abs(along) < reach * 2.5
            k[..., c] += strength * line
    return k


def tonemap(energy, exposure=1.0, gamma=1 / 1.8):
    return (1 - np.exp(-np.maximum(energy, 0) * exposure)) ** gamma


def fbm(h, w, beta, seed):
    """1/f^beta noise in -1..1: beta ~3 is cloudy, ~2 is grainy."""
    rng = np.random.default_rng(seed)
    white = rng.normal(size=(h, w))
    fy = np.fft.fftfreq(h)[:, None]
    fx = np.fft.rfftfreq(w)[None, :]
    f = np.sqrt(fx * fx + fy * fy)
    f[0, 0] = 1
    field = np.fft.irfft2(np.fft.rfft2(white) / f ** (beta / 2), s=(h, w))
    field -= field.mean()
    return field / (np.abs(field).max() + 1e-9)


def sample(field, x, y):
    """Bilinear lookup with wrap."""
    h, w = field.shape
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    fx, fy = x - x0, y - y0
    x0, y0 = x0 % w, y0 % h
    x1, y1 = (x0 + 1) % w, (y0 + 1) % h
    return (field[y0, x0] * (1 - fx) * (1 - fy) + field[y0, x1] * fx * (1 - fy)
            + field[y1, x0] * (1 - fx) * fy + field[y1, x1] * fx * fy)


def splat(img, xs, ys, values):
    """Add point lights at sub-pixel positions (bilinear)."""
    h, w = img.shape[:2]
    x0, y0 = np.floor(xs).astype(int), np.floor(ys).astype(int)
    fx, fy = xs - x0, ys - y0
    for dx, dy, wt in ((0, 0, (1 - fx) * (1 - fy)), (1, 0, fx * (1 - fy)), (0, 1, (1 - fx) * fy), (1, 1, fx * fy)):
        xi, yi = x0 + dx, y0 + dy
        ok = (xi >= 0) & (xi < w) & (yi >= 0) & (yi < h)
        for c in range(3):
            np.add.at(img[..., c], (yi[ok], xi[ok]), (values[ok, c] if values.ndim == 2 else values[ok]) * wt[ok])


def grid(size):
    y, x = np.mgrid[0:size, 0:size].astype(float)
    x -= size / 2 - .5
    y -= size / 2 - .5
    return x, y, np.hypot(x, y), np.arctan2(y, x)


def hue(h, s=.6, v=1.0):
    return np.array(colorsys.hsv_to_rgb(h % 1, s, v))


def star_temperature(n):
    """Random star colours from blue-white to warm."""
    t = RNG.random(n)
    blue, white, warm = np.array([.72, .82, 1.0]), np.array([1, 1, 1.0]), np.array([1, .86, .68])
    out = np.where(t[:, None] < .55, blue + (white - blue) * (t[:, None] / .55),
                   white + (warm - white) * ((t[:, None] - .55) / .45))
    return out


# The night sky ------------------------------------------------------------------------------
def sky(w=1920, h=1200):
    y, x = np.mgrid[0:h, 0:w].astype(float)
    base = np.zeros((h, w, 3))
    top, mid, bottom = np.array([5, 6, 26]) / 255, np.array([14, 11, 44]) / 255, np.array([30, 18, 62]) / 255
    f = (y / h)[..., None]
    base += np.where(f < .6, top + (mid - top) * (f / .6), mid + (bottom - mid) * ((f - .6) / .4))
    base = base ** 2.2                                                  # To linear.

    # Clouds: domain-warped 1/f noise gives wisps instead of blobs.
    warp_x, warp_y = fbm(h, w, 3.4, 1) * 90, fbm(h, w, 3.4, 2) * 90
    big = fbm(h, w, 3.6, 3)
    fine = fbm(h, w, 2.4, 4)
    cloud = sample(big, x + warp_x, y + warp_y) * .75 + sample(fine, x + warp_x * .5, y + warp_y * .5) * .35
    ridge = 1 - np.abs(sample(fbm(h, w, 2.9, 5), x + warp_x * 1.3, y + warp_y * 1.3))
    ridge = ridge ** 6                                                  # Bright filaments.
    nebula = np.zeros((h, w, 3))
    for (cx, cy), rgb, size, seed in (((.22, .30), (.47, .31, .86), .42, 6), ((.76, .20), (.24, .43, .9), .38, 7),
                                      ((.56, .72), (.82, .35, .70), .36, 8), ((.10, .80), (.24, .70, .78), .30, 9),
                                      ((.88, .62), (1.0, .80, .58), .22, 10)):
        reach = np.exp(-(((x / w - cx) / size) ** 2 + ((y / h - cy) / (size * 1.25)) ** 2))
        local = np.clip(cloud * 1.3 + .05 + fbm(h, w, 3.2, seed) * .5, 0, None) ** 3
        nebula += np.array(rgb) * (reach * (local * .10 + ridge * local * .08))[..., None]

    # The Milky Way: a diagonal band of glow and dense stars, cut by dark dust lanes.
    a = math.radians(-24)
    along = (x - w * .5) * math.cos(a) + (y - h * .42) * math.sin(a)
    across = -(x - w * .5) * math.sin(a) + (y - h * .42) * math.cos(a)
    wobble = sample(fbm(h, w, 3.3, 11), x, y) * 70
    band = np.exp(-((across + wobble) / 150) ** 2)
    core = np.exp(-((across + wobble) / 60) ** 2) * np.exp(-(along / (w * .45)) ** 2)
    dust = np.clip(sample(fbm(h, w, 2.7, 12), x + warp_x, y + warp_y) * 1.8 + .25, 0, 1)
    lanes = 1 - .85 * dust * np.exp(-((across + wobble * .6 - 10) / 55) ** 2)
    grain = np.clip(cloud + .6, 0, 1.6) ** 2
    milky = (band * .5 + core) * grain * lanes
    nebula += (np.array([.70, .66, 1.0]) * (band * grain * lanes * .035)[..., None]
               + np.array([1.0, .86, .70]) * (core * grain * lanes * .05)[..., None])

    # Stars: a sprinkle everywhere, many more in the band (and fewer in its dust lanes).
    stars = np.zeros((h, w, 3))
    n = 6000
    xs, ys = RNG.random(n) * w, RNG.random(n) * h
    extra = 14000
    t = RNG.random(extra) * 2 - 1
    off = RNG.normal(size=extra) * 110
    bx = w * .5 + t * w * .8 * math.cos(a) - off * math.sin(a)
    by = h * .42 + t * w * .8 * math.sin(a) + off * math.cos(a)
    xs, ys = np.concatenate([xs, bx]), np.concatenate([ys, by])
    bright = (RNG.pareto(2.4, xs.size) + 1) ** 1.5 * .035
    keep = sample(lanes, xs % w, ys % h)
    bright = np.minimum(bright * keep, 6)
    colours = star_temperature(xs.size) * bright[:, None]
    splat(stars, xs, ys, colours)
    peak = stars.max(-1, keepdims=True)
    hot = stars * (peak > np.quantile(peak[peak > 0], .997))           # Only a few dozen get spikes.
    cross = spikes(h, w, [(0, 1, .5), (90, 1, .5)], 9, .6)
    stars = stars + convolve(hot, cross) * .3
    energy = base + nebula + bloom(stars, ((1.0, .5), (3, .2), (9, .08))) + blur(nebula, 24) * .25
    vignette = 1 - .35 * (((x / w - .5) * 1.6) ** 2 + ((y / h - .5) * 1.4) ** 2)
    energy *= np.clip(vignette, .4, 1)[..., None]
    out = tonemap(energy, 1.5, 1 / 2.2)
    lum = out.mean(-1, keepdims=True)
    save_png('sky', lum + (out - lum) * 1.5)                           # A little richer colour.


def sky_layers(w=2560, h=1440):
    """The night sky as three parallax layers (2.5, round 5):
    sky_far   - deep gradient, nebulae (two-level domain warp), dark dust, the Milky Way;
    sky_stars - the star field on black (drawn additively, drifts a little faster);
    sky_dust  - faint near wisps on black (drifts fastest)."""
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    u, v = x / w, y / h
    f = v[..., None]
    top, mid, bottom = np.array([3, 4, 16]) / 255, np.array([9, 8, 32]) / 255, np.array([22, 13, 46]) / 255
    base = np.where(f < .6, top + (mid - top) * (f / .6), mid + (bottom - mid) * ((f - .6) / .4)) ** 2.2

    def field(beta, seed, scale=1.0):
        return fbm(h, w, beta, seed).astype(np.float32) * scale

    # Two-level domain warp: turbulent, wispy gas rather than blobs.
    q1, q2 = field(3.5, 101, 140), field(3.5, 102, 140)
    r1 = sample(field(3.2, 103, 110), x + q1, y + q2)
    r2 = sample(field(3.2, 104, 110), x + q1 * .7, y + q2 * .7)
    gas = sample(field(3.0, 105), x + r1, y + r2)
    detail = sample(field(2.3, 106), x + r1 * .5, y + r2 * .5)
    density = np.clip(gas * 1.25 + detail * .35 + .12, 0, None) ** 2.4
    filaments = (1 - np.abs(sample(field(2.7, 107), x + r1 * 1.4, y + r2 * 1.4))) ** 9
    # Where the gas glows at all: large soft regions, leaving clear dark sky between them.
    regions = np.clip(field(4.2, 108) * 1.6 + .25, 0, 1) ** 1.5
    regions *= np.clip(1.15 - ((u - .5) ** 2 * 1.2 + (v - .48) ** 2 * 1.8), 0, 1)
    # Colour drifts across the sky: violet, star blue, teal, rose, a little champagne.
    palette = np.array([[.50, .30, .95], [.25, .45, 1.0], [.20, .75, .85], [.90, .35, .70], [1.0, .78, .52]],
                       np.float32)
    hue_field = (np.clip(field(4.4, 109) * .5 + .5, 0, .999) * (len(palette) - 1))
    k = np.floor(hue_field).astype(int)
    t = (hue_field - k)[..., None]
    colour = palette[k] * (1 - t) + palette[np.minimum(k + 1, len(palette) - 1)] * t
    emission = colour * ((density * .09 + filaments * density * .09) * regions)[..., None]
    # Bright knots where stars are born.
    for cx, cy, rad, rgb in ((.26, .32, .05, (.75, .55, 1)), (.71, .24, .04, (.45, .7, 1)), (.6, .7, .035, (1, .55, .8))):
        knot = np.exp(-(((u - cx) / rad) ** 2 + ((v - cy) / (rad * 1.6)) ** 2))
        emission += np.array(rgb, np.float32) * (knot * (density + .2) * .12)[..., None]
    # Dark dust: absorbs the glow in ragged lanes.
    dust = np.clip(sample(field(2.9, 110), x + q1 * 1.2, y + q2 * 1.2) * 2.2 + .1, 0, 1) ** 1.3
    absorb = 1 - .8 * dust * np.clip(regions * 1.4, 0, 1)
    # The Milky Way, diagonal, with its own dust lanes.
    a = math.radians(-24)
    along = (x - w * .5) * math.cos(a) + (y - h * .42) * math.sin(a)
    across = -(x - w * .5) * math.sin(a) + (y - h * .42) * math.cos(a)
    wobble = sample(field(3.3, 111), x, y) * 90
    band = np.exp(-((across + wobble) / 210) ** 2)
    core = np.exp(-((across + wobble) / 80) ** 2) * np.exp(-(along / (w * .42)) ** 2)
    lanes = 1 - .9 * np.clip(sample(field(2.6, 112), x + r1, y + r2) * 2 + .2, 0, 1) * \
        np.exp(-((across + wobble * .5 - 12) / 70) ** 2)
    mottled = np.clip(gas + .7, 0, 1.8) ** 2
    milky = (np.array([.66, .64, 1.0], np.float32) * (band * mottled * .03)[..., None]
             + np.array([1.0, .88, .74], np.float32) * (core * mottled * .045)[..., None]) * lanes[..., None]
    nebula = (emission + milky) * absorb[..., None]
    far = base + nebula + blur(nebula, 30) * .35
    vignette = np.clip(1 - .4 * (((u - .5) * 1.5) ** 2 + ((v - .5) * 1.3) ** 2), .45, 1)
    far *= vignette[..., None]
    out = tonemap(far, 1.7, 1 / 2.2)
    lum = out.mean(-1, keepdims=True)
    out = lum + (out - lum) * 1.35
    out += RNG.normal(0, .6 / 255, out.shape)                        # Dither: no banding in the gradients.
    save_png('sky_far', out)

    # Stars: everywhere, denser in the band and in a few clusters, thinned by the dust.
    count = 30000
    xs, ys = RNG.random(count) * w, RNG.random(count) * h
    band_n = 26000
    tt = RNG.random(band_n) * 2 - 1
    off = RNG.normal(size=band_n) * 150
    bx = w * .5 + tt * w * .8 * math.cos(a) - off * math.sin(a)
    by = h * .42 + tt * w * .8 * math.sin(a) + off * math.cos(a)
    clusters = []
    for cx, cy, spread, n in ((.18, .64, 40, 900), (.8, .52, 34, 700), (.44, .2, 30, 500)):
        clusters.append((RNG.normal(cx * w, spread, n), RNG.normal(cy * h, spread * .8, n)))
    xs = np.concatenate([xs, bx] + [c[0] for c in clusters])
    ys = np.concatenate([ys, by] + [c[1] for c in clusters])
    inside = (xs >= 0) & (xs < w - 1) & (ys >= 0) & (ys < h - 1)
    xs, ys = xs[inside], ys[inside]
    bright = (RNG.pareto(2.6, xs.size) + 1) ** 1.6 * .03
    bright *= np.clip(sample(absorb, xs, ys), .15, 1)
    bright = np.minimum(bright, 7)
    stars = np.zeros((h, w, 3), np.float32)
    splat(stars, xs, ys, star_temperature(xs.size).astype(np.float32) * bright[:, None])
    peak = stars.max(-1, keepdims=True)
    hot = stars * (peak > np.quantile(peak[peak > 0], .9993))
    stars = stars + convolve(hot, spikes(h, w, [(0, 1, .5), (90, 1, .5)], 7, .55)) * .22
    stars = bloom(stars, ((.8, .5), (2.5, .22), (8, .06)))
    save_png('sky_stars', tonemap(stars, 1.3, 1 / 2.0))

    # Near wisps: faint, soft, warm and cool.
    wisp = np.clip(sample(field(3.8, 113), x + q1 * 2, y + q2 * 2) * 1.6 - .25, 0, None) ** 2
    tint = np.where((field(4.5, 114) > 0)[..., None], np.array([.62, .56, 1.0], np.float32),
                    np.array([1.0, .82, .62], np.float32))
    near = blur(tint * (wisp * .05)[..., None], 6)
    save_png('sky_dust', tonemap(near, 1.0, 1 / 2.0))


# Meteors -----------------------------------------------------------------------------------
def meteor(name, colour, w=1024, h=96, tail=260.0, seed=0, rainbow=False, sparkly=False, hero=False):
    """A meteor pointing right: the head near the right end, its tail fading left.
    The tail widens and breaks into bits as it cools, the head is a white-hot core."""
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:h, 0:w].astype(float)
    hx, cy = w - (72 if hero else 56), h / 2
    u = hx - x                                                        # Distance behind the head.
    v = y - cy
    behind = np.clip(u, 0, None)
    noise1 = np.interp(behind, np.linspace(0, w, 220), rng.random(220))
    noise2 = np.interp(behind, np.linspace(0, w, 60), rng.random(60))
    frag = .55 + .3 * noise1 + .3 * noise2
    sway = np.interp(behind, np.linspace(0, w, 9), rng.normal(size=9)) * behind * .004
    sigma = .9 + behind * (.011 if not hero else .016)
    fade = np.exp(-behind / tail) * (u > -1)
    core = fade * frag * np.exp(-((v - sway) / sigma) ** 2) * (1.2 / sigma ** .5)
    halo = fade * np.exp(-((v - sway) / (sigma * 4 + 2)) ** 2) * .16
    if rainbow:
        hues = np.stack([hue(.0 + k / 9, .7) for k in range(10)])
        tint = np.stack([np.interp(behind / tail, np.linspace(0, 2.5, 10), hues[:, c]) for c in range(3)], -1)
    else:
        tint = np.broadcast_to(np.array(colour), (h, w, 3))
    hot = np.exp(-behind / 34)[..., None]                               # White near the head.
    tint = tint * (1 - hot) + hot
    energy = (core + halo)[..., None] * tint
    r2 = (x - hx) ** 2 + v ** 2
    head = np.exp(-r2 / (2.2 if not hero else 4.5)) * (9 if not hero else 14)
    energy += head[..., None] * (np.array(colour if not rainbow else (1, 1, 1)) * .3 + .7)
    count = 26 if sparkly else 12
    for k in range(count):                                             # Bits breaking off.
        d = rng.exponential(tail * .5) + 8
        if d > w - 80:
            continue
        px, py = hx - d, cy + rng.normal() * (1.5 + d * .02)
        s = rng.uniform(.6, 1.4) * math.exp(-d / (tail * 1.4)) * (2.4 if sparkly else 1.4)
        dot = np.exp(-((x - px) ** 2 + (y - py) ** 2) / rng.uniform(.6, 1.6)) * s
        c = hue(k / count, .6) if rainbow else np.array(colour) * .6 + .4
        energy += dot[..., None] * c
    energy = bloom(energy, ((1.2, .6), (4, .4), (12, .22), (30, .1)))
    save_png(name, tonemap(energy, 1.25), window='box')


# Sparkles and glows --------------------------------------------------------------------------
def sparkle(name, colour, size=96, six=False):
    x, y, r, th = grid(size)
    energy = np.zeros((size, size, 3))
    point = np.exp(-(r / 1.6) ** 2) * 10
    arms = [(0, 1, .9), (90, 1, .9), (45, .38, .3), (135, .38, .3)] if not six else \
        [(a, 1 if k % 2 == 0 else .6, .7) for k, a in enumerate(range(0, 180, 30))]
    c = np.array(colour)
    energy += point[..., None] * (c * .4 + .6)
    energy += convolve(point[..., None] * c, spikes(size, size, arms, size * .16, .8)) * .25
    energy += (np.exp(-r / 9) * .5)[..., None] * c
    energy = bloom(energy, ((1, .5), (4, .3), (10, .15)))
    save_png(name, tonemap(energy, 1.1), window='radial')


def flare(name, colour, w=1024, h=48):
    y, x = np.mgrid[0:h, 0:w].astype(float)
    x -= w / 2
    y -= h / 2
    c = np.array(colour)
    energy = (np.exp(-np.abs(x) / 150) * np.exp(-(y / 1.3) ** 2) * 2.2
              + np.exp(-np.abs(x) / 60) * np.exp(-(y / 5) ** 2) * .5)[..., None] * c
    energy += (np.exp(-(x * x + y * y) / 30) * 3)[..., None]
    save_png(name, tonemap(bloom(energy, ((2, .3), (8, .15))), 1.0), window='box')


def rainbow_of(th, s=.6):
    band = (th / math.tau) % 1
    return np.stack([np.interp(band, np.linspace(0, 1, 13), [hue(i / 12, s)[c] for i in range(13)])
                     for c in range(3)], -1)


def shock(name, colour, size=384):
    x, y, r, th = grid(size)
    c = rainbow_of(th) if colour is None else np.array(colour)
    R = size * .40
    breakup = .65 + .35 * np.interp(th, np.linspace(-np.pi, np.pi, 50), RNG.random(50))
    ring = np.exp(-((r - R) / 2.6) ** 2) * 2.2 * breakup
    inner = np.exp(-((r - R) / 26) ** 2) * (r < R) * .45
    energy = (ring + inner)[..., None] * (c * .6 + .4 * (ring[..., None] > .8))
    save_png(name, tonemap(bloom(energy, ((1.5, .5), (6, .35), (18, .2))), 1.2), window='radial')


def rays(name, colour, size=512, count=44):
    x, y, r, th = grid(size)
    c = rainbow_of(th * 3, .5) if colour is None else np.array(colour)
    rng = np.random.default_rng(len(name))
    beams = np.zeros_like(r)
    for k in range(count):                                              # Uneven god rays.
        a = rng.uniform(-np.pi, np.pi)
        width = rng.uniform(.008, .04)
        d = np.angle(np.exp(1j * (th - a)))
        beams += np.exp(-(d / width) ** 2) * rng.uniform(.2, .8) * np.exp(-r / rng.uniform(60, 150))
    beams *= np.clip(r / 14, 0, 1)
    energy = beams[..., None] * c + (np.exp(-r / 30) * .35)[..., None] * c
    save_png(name, tonemap(bloom(energy, ((2, .4), (8, .3), (24, .15))), 1.0), window='radial')


# Rarity hero lights ---------------------------------------------------------------------------
def hero_fanxing(size=512):
    """Deep blue: a sapphire star with long spikes and a cloud of tiny blue sparks."""
    x, y, r, th = grid(size)
    c = np.array(RARITY['fanxing'])
    point = np.exp(-(r / 3.2) ** 2) * 18
    energy = point[..., None] * (c * .35 + .65)
    energy += convolve(point[..., None] * c, spikes(size, size, [(0, 1, 1), (90, 1, 1), (45, .4, .35), (135, .4, .35)],
                                                      70, 1.1, chroma=.05)) * .16
    energy += (np.exp(-r / 30) * 1.0 + np.exp(-r / 90) * .12)[..., None] * c
    n = 140
    ang, dist = RNG.random(n) * math.tau, RNG.gamma(2, 40, n)
    dots = np.zeros_like(energy)
    splat(dots, size / 2 + np.cos(ang) * dist, size / 2 + np.sin(ang) * dist,
          np.outer(RNG.pareto(3, n) * .4 + .2, c * .6 + .4))
    energy += bloom(dots, ((1, .6), (3, .3)))
    save_png('hero_fanxing', tonemap(bloom(energy), 1.0), window='radial')


def hero_mingyue(size=512):
    """Flashing white: a full bright moon in a wide pale halo, like a moonlit sky ring."""
    x, y, r, th = grid(size)
    R = 62.0
    inside = r < R
    z = np.sqrt(np.clip(1 - (r / R) ** 2, 0, 1))
    light = np.array([-.35, -.35, .87])
    light /= np.linalg.norm(light)
    lit = np.clip((x / R) * light[0] + (y / R) * light[1] + z * light[2], 0, 1) ** .7
    maria = 1 - .45 * np.clip(fbm(size, size, 2.6, 21) * 1.8 + .2, 0, 1)    # Soft lunar seas.
    disc = inside * (lit * maria * 1.7 + .2)
    limb = np.exp(-((r - R) / 1.6) ** 2) * .8
    energy = (disc + limb)[..., None] * np.array([1.0, .98, .93])
    halo_r = 168.0
    for c, shift in enumerate((-3.0, 0.0, 3.5)):                         # A 22° halo: red inside, blue outside.
        energy[..., c] += np.exp(-((r - halo_r - shift) / 7) ** 2) * .55
    energy += (np.exp(-(r - R).clip(0) / 14) * .3 * (~inside) + np.exp(-r / 120) * .03)[..., None] * \
        np.array([.86, .92, 1.0])
    save_png('hero_mingyue', tonemap(bloom(energy, ((1.5, .35), (6, .2), (20, .08))), .9), window='radial')


def hero_haori(size=512):
    """Warm gold: a small sun with a ragged corona and eight long rays."""
    x, y, r, th = grid(size)
    c = np.array(RARITY['haori'])
    ragged = np.interp(th, np.linspace(-np.pi, np.pi, 181), RNG.random(181)) ** 3
    corona = np.exp(-np.clip(r - 22, 0, None) / (24 + 60 * ragged)) * (r > 18) * 1.4
    core = np.exp(-(r / 20) ** 4) * 6
    energy = core[..., None] * (c * .4 + .6) + corona[..., None] * c
    hot = (np.exp(-(r / 6) ** 2) * 20)[..., None] * c
    energy += convolve(hot, spikes(size, size, [(a, 1 if k % 2 == 0 else .55, 1) for k, a in
                                                enumerate(range(0, 180, 22))], 60, 1.2)) * .028
    energy += (np.exp(-r / 80) * .15)[..., None] * c
    save_png('hero_haori', tonemap(bloom(energy), 1.0), window='radial')


def hero_yinhe(size=512):
    """Flowing silver: a face-on spiral galaxy (the show tilts and turns it)."""
    x, y, r, th = grid(size)
    energy = np.zeros((size, size, 3))
    n = 26000
    arm = RNG.integers(0, 2, n)
    t = RNG.random(n) ** .8
    theta = t * 3.4 * math.pi + arm * math.pi
    rad = 10 * np.exp(.26 * t * 3.4 * math.pi)
    spread = rad * .10 + 1.5
    px = size / 2 + rad * np.cos(theta) + RNG.normal(size=n) * spread
    py = size / 2 + rad * np.sin(theta) + RNG.normal(size=n) * spread
    silver = np.array([.78, .86, 1.0])
    young = np.array([.62, .74, 1.0])
    mix = RNG.random(n)[:, None]
    colours = (silver * mix + young * (1 - mix)) * ((RNG.pareto(2.6, n) + 1) ** 1.4 * .05)[:, None]
    splat(energy, px, py, colours)
    hot = energy * (energy.max(-1, keepdims=True) > .5)
    energy += convolve(hot, spikes(size, size, [(0, 1, 1), (90, 1, 1)], 6, .6)) * .4
    dusty = blur(energy, 4) * 1.3                                       # Arm glow.
    bulge = np.exp(-(r / 20) ** 2) * 2.2 + np.exp(-r / 50) * .14
    energy = energy + dusty + bulge[..., None] * np.array([1.0, .97, .92])
    save_png('hero_yinhe', tonemap(bloom(energy, ((1, .5), (4, .25), (14, .1))), 1.0), window='radial')


def hero_xinghai(size=512):
    """Iridescent: a prism star with rainbow spikes, and (separately) rainbow rings."""
    x, y, r, th = grid(size)
    point = np.exp(-(r / 3.5) ** 2) * 10
    energy = point[..., None] * np.ones(3)
    k = spikes(size, size, [(a, 1 if n % 2 == 0 else .55, 1) for n, a in enumerate(range(0, 180, 30))], 80, 1.2,
               chroma=.18)
    energy += convolve(point[..., None], k) * .2
    swirl = (th / math.tau + r / 260) % 1
    rainbow = np.stack([np.interp(swirl, np.linspace(0, 1, 13), [hue(i / 12, .85)[c] for i in range(13)])
                        for c in range(3)], -1)
    energy += rainbow * (np.exp(-r / 45) * .45)[..., None]
    save_png('hero_xinghai', tonemap(bloom(energy), 1.0), window='radial')
    ring = np.zeros_like(energy)
    for R, wdt, s in ((118, 4, 1.0), (176, 7, .6), (220, 2.5, .5)):
        band = (th / math.tau + R / 400) % 1
        col = np.stack([np.interp(band, np.linspace(0, 1, 13), [hue(i / 12, .7)[c] for i in range(13)])
                        for c in range(3)], -1)
        ring += col * (np.exp(-((r - R) / wdt) ** 2) * s)[..., None]
    save_png('hero_xinghai_ring', tonemap(bloom(ring, ((2, .5), (8, .3), (20, .15))), 1.2), window='radial')


def main():
    only = set(sys.argv[1:])

    def want(name):
        return not only or name in only
    if want('sky'):
        sky()
    if want('skylayers'):
        sky_layers()
    if want('meteors'):
        for k, (name, colour) in enumerate(PALETTE.items()):
            meteor(f'meteor_{name}', colour, seed=k)
            meteor(f'meteor_{name}_thin', colour, w=768, h=64, tail=170, seed=k + 10)
        for name, colour in RARITY.items():
            meteor(f'meteor_{name}', colour or (1, 1, 1), w=1280, h=128, tail=360, seed=40 + len(name),
                   rainbow=colour is None, sparkly=name in ('yinhe', 'xinghai'), hero=True)
    if want('sparkles'):
        for name, colour in list(PALETTE.items()) + [(k, v or (1, .85, 1)) for k, v in RARITY.items()]:
            sparkle(f'sparkle_{name}', colour, six=name in ('haori', 'xinghai'))
        flare('flare', (.75, .85, 1.0))
        flare('flare_gold', (1.0, .78, .4))
    if want('bursts'):
        for name, colour in RARITY.items():
            shock(f'shock_{name}', colour)
            rays(f'rays_{name}', colour)
    if want('heroes'):
        hero_fanxing()
        hero_mingyue()
        hero_haori()
        hero_yinhe()
        hero_xinghai()


if __name__ == '__main__':
    main()
