"""A light, original background track for the tutorial video (pure Python).

Usage:
    python tools/tutorial_music.py OUT.wav SECONDS

Lo-fi pop in F major at 96 BPM: electric piano chords, a round bass, a bell
melody and soft drums, arranged from 8-bar sections (intro, verse, chorus,
breakdown) so it does not loop like a jingle. Everything is synthesized
here, so there are no rights to worry about. tools/tutorial_video.py adds
reverb, fades and the mix level with ffmpeg.
"""
import math
import random
import struct
import sys
import wave

SR = 32000
BPM = 96
BEAT = 60 / BPM
BAR = 4 * BEAT
# Fmaj7 Em7 Dm7 Cmaj7 | Bbmaj7 Am7 Gm7 C7
CHORDS = [(53, 57, 60, 64), (52, 55, 59, 62), (50, 53, 57, 60), (48, 52, 55, 59),
          (46, 50, 53, 57), (45, 48, 52, 55), (43, 46, 50, 53), (48, 52, 55, 58)]
ROOTS = [41, 40, 38, 36, 34, 33, 31, 36]
PENTATONIC = [65, 67, 69, 72, 74, 77, 79, 81]          # F G A C D, two octaves.


def hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


_CACHE = {}


def _note(kind, midi, seconds):
    key = (kind, midi, round(seconds, 3))
    if key in _CACHE:
        return _CACHE[key]
    n = int(seconds * SR)
    f = hz(midi)
    out = [0.0] * n
    two_pi = 2 * math.pi
    release = int(.08 * SR)
    for i in range(n):
        t = i / SR
        attack = min(1.0, t / .006)
        tail = 1.0 if i < n - release else (n - i) / release
        if kind == 'ep':                     # Soft electric piano.
            env = math.exp(-t / 2.2) * attack * tail
            v = (math.sin(two_pi * f * t) + .22 * math.exp(-t * 3) * math.sin(two_pi * 2 * f * t)
                 + .06 * math.exp(-t * 9) * math.sin(two_pi * 7 * f * t))
            out[i] = .085 * env * v
        elif kind == 'bass':
            env = math.exp(-t / .9) * attack * tail
            out[i] = .22 * env * (math.sin(two_pi * f * t) + .25 * math.sin(two_pi * 2 * f * t))
        elif kind == 'pad':                  # Warm bed under the chords.
            swell = min(1.0, t / .45) * (1.0 if i < n - int(.5 * SR) else (n - i) / (.5 * SR))
            out[i] = .028 * swell * (math.sin(two_pi * f * t) + .6 * math.sin(two_pi * 1.004 * f * t)
                                     + .15 * math.sin(two_pi * 2 * f * t))
        elif kind == 'bell':                 # Music-box melody.
            env = math.exp(-t / .55) * min(1.0, t / .003) * tail
            out[i] = .075 * env * (math.sin(two_pi * f * t) + .35 * math.sin(two_pi * 2.01 * f * t)
                                   + .12 * math.sin(two_pi * 3.98 * f * t))
    _CACHE[key] = out
    return out


def _drum(kind):
    if kind in _CACHE:
        return _CACHE[kind]
    rng = random.Random(kind)
    if kind == 'kick':
        n, phase, out = int(.3 * SR), 0.0, []
        for i in range(n):
            t = i / SR
            phase += 2 * math.pi * (48 + 70 * math.exp(-t * 30)) / SR
            out.append(.42 * math.exp(-t * 14) * math.sin(phase))
    elif kind == 'snare':
        n, out, last = int(.16 * SR), [], 0.0
        for i in range(n):
            t = i / SR
            last = .55 * last + .45 * rng.uniform(-1, 1)        # A softer, brushed noise.
            out.append(.09 * math.exp(-t * 28) * last + .04 * math.exp(-t * 40) * math.sin(2 * math.pi * 190 * t))
    else:                                                   # Hi-hat.
        n, out, prev = int(.05 * SR), [], 0.0
        for i in range(n):
            t = i / SR
            x = rng.uniform(-1, 1)
            out.append(.016 * math.exp(-t * 110) * (x - prev))
            prev = x
    _CACHE[kind] = out
    return out


def _add(buf, start, sound):
    start = int(start * SR)
    if start >= len(buf):
        return
    end = min(len(buf), start + len(sound))
    buf[start:end] = [a + b for a, b in zip(buf[start:end], sound)]


def _melody(seed):
    """Eight bars of (beat offset in the block, midi, length in beats), built from a two-bar motif."""
    rng = random.Random(seed)
    rhythms = [(0, 1, 1.5, 2.5, 3), (0, .5, 1, 2, 3), (0, 1.5, 2, 3.5), (.5, 1, 2, 2.5, 3)]
    motif = []
    for bar in range(2):
        for beat in rng.choice(rhythms):
            motif.append((bar * 4 + beat, rng.randrange(1, 6)))
    notes = []
    for phrase in range(4):
        shift = (0, 1, -1, 0)[phrase]
        for offset, degree in motif:
            if phrase == 3 and offset >= 6:
                continue                                    # Leave room to land.
            index = max(0, min(len(PENTATONIC) - 1, degree + shift + rng.choice((0, 0, 0, 1, -1))))
            notes.append((phrase * 8 + offset, PENTATONIC[index], .9))
    notes.append((3 * 8 + 6, 72, 2.0))                      # Land on C.
    return notes


def block(kind, seed=0):
    """Eight bars of one section."""
    buf = [0.0] * int(8 * BAR * SR + SR)                    # One second of tail.
    for bar in range(8):
        at = bar * BAR
        chord, root = CHORDS[bar], ROOTS[bar]
        for midi in chord[:3]:
            _add(buf, at, _note('pad', midi + 12, BAR + .4))
        if kind in ('intro', 'breakdown', 'outro'):
            for midi in chord:
                _add(buf, at, _note('ep', midi, BAR * .98))
        else:
            for midi in chord:
                _add(buf, at, _note('ep', midi, 1.4 * BEAT))
                _add(buf, at + 2.5 * BEAT, _note('ep', midi, 1.2 * BEAT))
        if kind != 'intro':
            _add(buf, at, _note('bass', root, 1.8 * BEAT))
            _add(buf, at + 2 * BEAT, _note('bass', root + (7 if bar % 2 else 12), 1.4 * BEAT))
            if bar % 4 == 3:
                _add(buf, at + 3.5 * BEAT, _note('bass', root + 10, .45 * BEAT))
        if kind in ('verse', 'chorus'):
            _add(buf, at, _drum('kick'))
            _add(buf, at + 2.5 * BEAT, _drum('kick'))
            _add(buf, at + BEAT, _drum('snare'))
            _add(buf, at + 3 * BEAT, _drum('snare'))
            for eighth in range(8):
                swing = .07 * BEAT if eighth % 2 else 0
                _add(buf, at + eighth * BEAT / 2 + swing, _drum('hat'))
    if kind in ('chorus', 'breakdown'):
        for offset, midi, beats in _melody(seed):
            _add(buf, offset * BEAT, _note('bell', midi, beats * BEAT))
    return buf


ARRANGEMENT = ('intro', 'verse', 'chorus', 'verse', 'chorus2', 'breakdown', 'verse', 'chorus', 'chorus2',
               'verse', 'breakdown2', 'chorus', 'verse', 'chorus2', 'breakdown', 'verse', 'chorus', 'chorus2',
               'verse', 'chorus', 'outro')


def render(seconds):
    blocks = {}
    for name in set(ARRANGEMENT):
        kind = name.rstrip('2')
        blocks[name] = block(kind, seed=name)
    total = int(seconds * SR)
    out = [0.0] * (total + SR * 2)
    length = int(8 * BAR * SR)
    position, index = 0, 0
    while position < total:
        name = ARRANGEMENT[index % len(ARRANGEMENT)]
        piece = blocks[name]
        end = min(len(out), position + len(piece))
        out[position:end] = [a + b for a, b in zip(out[position:end], piece)]
        position += length
        index += 1
    return out[:total]


def write(path, samples):
    peak = max(1e-6, max(abs(s) for s in samples))
    scale = .9 / peak * 32767
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(b''.join(struct.pack('<h', int(s * scale)) for s in samples))


if __name__ == '__main__':
    write(sys.argv[1], render(float(sys.argv[2])))
