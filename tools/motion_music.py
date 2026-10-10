"""Upbeat music and sound effects for the motion videos (pure Python, original).

Electro-pop at 124 BPM in A minor / C major (Am F C G): four-on-the-floor
kick, claps, off-beat hats, a pumping bass, a bright pluck arpeggio, chord
stabs and a pentatonic hook in the drops. Sections: intro, build, drop,
break, drop... cut to the requested length. Sound effects (whoosh, pop, ding,
riser, impact, sparkle) are made here too. Nothing is sampled, so there are
no rights to worry about.
"""
import math
import random
import struct
import wave

SR = 32000
BPM = 124
BEAT = 60 / BPM
BAR = 4 * BEAT
# Am F C G, two bars each.
CHORDS = [(57, 60, 64), (53, 57, 60), (48, 52, 55), (55, 59, 62)]
ROOTS = [45, 41, 48, 43]
HOOK = [69, 72, 74, 76, 79, 81]
_CACHE = {}


def hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def _tone(kind, midi, seconds):
    key = (kind, midi, round(seconds, 3))
    if key in _CACHE:
        return _CACHE[key]
    n = int(seconds * SR)
    f = hz(midi)
    out = [0.0] * n
    tau = 2 * math.pi
    release = max(1, int(.03 * SR))
    for i in range(n):
        t = i / SR
        tail = 1.0 if i < n - release else (n - i) / release
        attack = min(1.0, t / .004)
        if kind == 'pluck':                       # Bright, short: a few harmonics decaying fast.
            env = math.exp(-t * 9) * attack * tail
            v = sum(math.sin(tau * f * k * t) * math.exp(-t * 6 * k) / k for k in (1, 2, 3, 4))
            out[i] = .07 * env * v
        elif kind == 'stab':                      # Detuned chord stab.
            env = math.exp(-t * 3.2) * attack * tail
            v = math.sin(tau * f * t) + .7 * math.sin(tau * f * 1.006 * t) + .7 * math.sin(tau * f * .994 * t)
            out[i] = .035 * env * v
        elif kind == 'bass':
            env = math.exp(-t * 7) * attack * tail
            v = math.sin(tau * f * t) + .45 * math.sin(tau * 2 * f * t) + .2 * math.sin(tau * 3 * f * t)
            out[i] = .2 * env * v
        elif kind == 'pad':
            swell = min(1.0, t / .3) * tail
            v = math.sin(tau * f * t) + .5 * math.sin(tau * f * 1.004 * t)
            out[i] = .022 * swell * v
        elif kind == 'lead':
            env = math.exp(-t * 2.5) * attack * tail
            vib = 1 + .004 * math.sin(tau * 5.5 * t) * min(1.0, t / .2)
            v = math.sin(tau * f * vib * t) + .3 * math.sin(tau * 2 * f * vib * t)
            out[i] = .065 * env * v
    _CACHE[key] = out
    return out


def _drum(kind):
    if kind in _CACHE:
        return _CACHE[kind]
    rng = random.Random(kind)
    out = []
    if kind == 'kick':
        phase = 0.0
        for i in range(int(.32 * SR)):
            t = i / SR
            phase += 2 * math.pi * (45 + 110 * math.exp(-t * 35)) / SR
            out.append(.55 * math.exp(-t * 11) * math.sin(phase) + (.15 * math.exp(-t * 400) * rng.uniform(-1, 1)))
    elif kind == 'clap':
        last = 0.0
        for i in range(int(.2 * SR)):
            t = i / SR
            last = .3 * last + .7 * rng.uniform(-1, 1)
            bursts = sum(math.exp(-(t - d) * 120) for d in (0, .011, .022) if t >= d)
            out.append(.11 * last * (bursts + math.exp(-t * 18)))
    elif kind in ('hat', 'open'):
        prev = 0.0
        decay = 70 if kind == 'hat' else 14
        for i in range(int((.06 if kind == 'hat' else .25) * SR)):
            t = i / SR
            x = rng.uniform(-1, 1)
            out.append(.03 * math.exp(-t * decay) * (x - prev))
            prev = x
    _CACHE[kind] = out
    return out


def _add(buf, at, sound, gain=1.0):
    start = int(at * SR)
    if start >= len(buf) or start < 0:
        return
    end = min(len(buf), start + len(sound))
    buf[start:end] = [a + gain * b for a, b in zip(buf[start:end], sound)]


def _section(kind, bars=8, seed=0):
    buf = [0.0] * int(bars * BAR * SR + SR)
    rng = random.Random(seed)
    hook = [(rng.choice((0, .5, 1, 1.5, 2, 2.5, 3)), rng.choice(HOOK)) for _ in range(5)]
    for bar in range(bars):
        at = bar * BAR
        step = (bar // 2) % 4
        chord, root = CHORDS[step], ROOTS[step]
        drop = kind == 'drop'
        # Pad underneath everything except the drop.
        if kind in ('intro', 'build', 'break'):
            for midi in chord:
                _add(buf, at, _tone('pad', midi + 12, BAR + .2))
        # Arpeggio in sixteenths (eighths in the intro).
        notes = list(chord) + [chord[0] + 12]
        division = 2 if kind == 'intro' else 4
        for k in range(4 * division):
            midi = notes[(k + bar) % len(notes)] + 12
            _add(buf, at + k * BEAT / division, _tone('pluck', midi, .22), .8 if drop else .6)
        if kind in ('build', 'drop'):
            for beat in range(4):
                if drop or beat in (0, 2):
                    _add(buf, at + beat * BEAT, _drum('kick'))
                _add(buf, at + beat * BEAT + BEAT / 2, _drum('hat'))
                _add(buf, at + beat * BEAT + BEAT / 2, _tone('bass', root, BEAT * .45))
            _add(buf, at + BEAT, _drum('clap'))
            _add(buf, at + 3 * BEAT, _drum('clap'))
        if drop:
            for midi in chord:
                _add(buf, at, _tone('stab', midi + 12, .5))
                _add(buf, at + 1.5 * BEAT, _tone('stab', midi + 12, .4))
            _add(buf, at + 3.5 * BEAT, _drum('open'))
            if bar % 2 == 0:
                for offset, midi in hook:
                    _add(buf, at + offset * BEAT, _tone('lead', midi, .6))
        if kind == 'build' and bar == bars - 1:
            for k in range(8):                     # Snare-roll into the drop.
                _add(buf, at + k * BEAT / 2, _drum('clap'), .4 + k * .08)
    return buf


ARRANGEMENT = (('intro', 4), ('build', 4), ('drop', 8), ('drop', 8), ('break', 4), ('build', 4), ('drop', 8),
               ('drop', 8), ('break', 4), ('drop', 8), ('drop', 8), ('drop', 8), ('drop', 8))


def render(seconds):
    total = int(seconds * SR)
    out = [0.0] * (total + SR)
    position, index = 0, 0
    blocks = {}
    while position < total:
        kind, bars = ARRANGEMENT[min(index, len(ARRANGEMENT) - 1)]
        key = (kind, bars, index % 3)
        if key not in blocks:
            blocks[key] = _section(kind, bars, seed=index % 3)
        piece = blocks[key]
        end = min(len(out), position + len(piece))
        out[position:end] = [a + b for a, b in zip(out[position:end], piece)]
        position += int(bars * BAR * SR)
        index += 1
    # Fade out over the last two seconds.
    fade = int(2 * SR)
    for i in range(max(0, total - fade), total):
        out[i] *= (total - i) / fade
    return out[:total]


# Sound effects --------------------------------------------------------------------

def sfx(kind, seed=0):
    rng = random.Random(f'{kind}{seed}')
    out = []
    if kind == 'whoosh':                          # Noise swept up and down.
        n, low, y = int(.45 * SR), 0.0, 0.0
        for i in range(n):
            t = i / n
            cutoff = .02 + .5 * math.sin(math.pi * t) ** 2
            low += cutoff * (rng.uniform(-1, 1) - low)
            y = low - .6 * y * 0
            out.append(.5 * math.sin(math.pi * t) ** 1.5 * low)
    elif kind == 'pop':
        phase = 0.0
        for i in range(int(.12 * SR)):
            t = i / SR
            phase += 2 * math.pi * (300 + 900 * math.exp(-t * 45)) / SR
            out.append(.35 * math.exp(-t * 30) * math.sin(phase))
    elif kind == 'ding':
        for i in range(int(.9 * SR)):
            t = i / SR
            v = sum(a * math.sin(2 * math.pi * f * t) for f, a in ((1318.5, 1), (2637, .4), (3956, .15)))
            out.append(.16 * math.exp(-t * 4.5) * v * min(1.0, t / .002))
    elif kind == 'riser':
        n, low = int(1.6 * SR), 0.0
        phase = 0.0
        for i in range(n):
            t = i / n
            low += (.05 + .4 * t) * (rng.uniform(-1, 1) - low)
            phase += 2 * math.pi * (180 + 1400 * t * t) / SR
            out.append(t ** 1.6 * (.22 * low + .08 * math.sin(phase)))
    elif kind == 'impact':
        phase, low = 0.0, 0.0
        for i in range(int(1.0 * SR)):
            t = i / SR
            phase += 2 * math.pi * (38 + 60 * math.exp(-t * 12)) / SR
            low += .15 * (rng.uniform(-1, 1) - low)
            out.append(.6 * math.exp(-t * 4) * math.sin(phase) + .25 * math.exp(-t * 9) * low)
    elif kind == 'sparkle':
        out = [0.0] * int(.8 * SR)
        for k in range(6):
            start = int(k * .07 * SR)
            f = rng.choice((2093, 2349, 2637, 3136, 3520))
            for i in range(int(.25 * SR)):
                if start + i < len(out):
                    t = i / SR
                    out[start + i] += .07 * math.exp(-t * 14) * math.sin(2 * math.pi * f * t)
    return out


def write(path, samples, peak_to=.9):
    peak = max(1e-6, max(abs(s) for s in samples))
    scale = min(1.0, peak_to / peak) * 32767
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(b''.join(struct.pack('<h', max(-32767, min(32767, int(s * scale)))) for s in samples))
