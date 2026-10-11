"""Synthesises the wishing show's sounds (2.5, round 6) with numpy (Blender's Python has it):

    "D:/Program Files/Blender Foundation/Blender 5.2/5.2/python/bin/python.exe" tools/render_wish_sounds.py

Bells are built from inharmonic partials, the choir from detuned, filtered voices, the harp
from plucked strings (Karplus-Strong); everything shares one stereo reverb. The rarer the
find, the deeper and longer its sound. Writes 44.1 kHz stereo WAVs to assets/v2_5/wish/sound/.
"""
from __future__ import annotations

import os
import wave

import numpy as np

RATE = 44100
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'assets', 'v2_5', 'wish', 'sound')
RNG = np.random.default_rng(2025)


def seconds(n):
    return np.arange(int(n * RATE)) / RATE


def note(name):
    """Frequency of a note like 'C5', 'G#4'."""
    names = {'C': -9, 'C#': -8, 'D': -7, 'D#': -6, 'E': -5, 'F': -4, 'F#': -3, 'G': -2, 'G#': -1, 'A': 0, 'A#': 1, 'B': 2}
    pitch, octave = name[:-1], int(name[-1])
    return 440.0 * 2 ** ((names[pitch] + (octave - 4) * 12) / 12)


def envelope(t, attack, decay):
    return np.minimum(1, t / max(attack, 1e-4)) * np.exp(-t / decay)


def bell(freq, length, decay=1.2, bright=1.0):
    """A glassy bell: partials at bell-like ratios, the higher ones dying sooner."""
    t = seconds(length)
    out = np.zeros_like(t)
    for ratio, amp, dk in ((1, 1, 1), (2.0, .5, .7), (2.76, .45 * bright, .45), (5.4, .25 * bright, .25),
                           (8.93, .12 * bright, .15)):
        detune = 1 + RNG.normal(0, .0008)
        out += amp * np.sin(2 * np.pi * freq * ratio * detune * t + RNG.random() * 6.28) * envelope(t, .002, decay * dk)
    return out


def pluck(freq, length, damping=.996):
    """A harp string (Karplus-Strong)."""
    n = int(length * RATE)
    period = max(2, int(RATE / freq))
    buf = RNG.uniform(-1, 1, period)
    out = np.zeros(n)
    for i in range(n):
        out[i] = buf[i % period]
        buf[i % period] = damping * .5 * (buf[i % period] + buf[(i + 1) % period])
    return out * envelope(seconds(length), .001, length * .6)


def lowpass(x, cutoff):
    spectrum = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / RATE)
    return np.fft.irfft(spectrum / np.sqrt(1 + (f / cutoff) ** 4), n=len(x))


def bandpass(x, low, high):
    spectrum = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / RATE)
    gain = 1 / np.sqrt(1 + (f / high) ** 4) * (1 - 1 / np.sqrt(1 + (f / max(low, 1)) ** 4))
    return np.fft.irfft(spectrum * gain, n=len(x))


def choir(freqs, length, attack=.4, release=1.0):
    """Soft 'aah' voices: detuned saw-like voices through vowel formants."""
    t = seconds(length)
    out = np.zeros_like(t)
    for f in freqs:
        for k in range(4):
            detune = 1 + RNG.normal(0, .004)
            vib = 1 + .004 * np.sin(2 * np.pi * (5 + RNG.random()) * t + RNG.random() * 6)
            phase = np.cumsum(2 * np.pi * f * detune * vib / RATE)
            voice = sum(np.sin(phase * h) / h for h in range(1, 9))
            out += voice
    vowel = bandpass(out, 500, 1300) + .6 * bandpass(out, 2400, 3200)
    env = np.minimum(1, t / attack) * np.minimum(1, np.maximum(0, (length - t) / release))
    return vowel * env


def noise_sweep(length, start, end, rise=True):
    """Filtered noise whose colour moves from ``start`` to ``end`` Hz (a whoosh / riser)."""
    x = RNG.normal(0, 1, int(length * RATE))
    chunks = 24
    out = np.zeros_like(x)
    size = len(x) // chunks
    for c in range(chunks):
        f = start * (end / start) ** (c / (chunks - 1))
        seg = bandpass(x, f * .6, f * 1.6)[c * size:(c + 1) * size]
        out[c * size:(c + 1) * size] = seg
    t = seconds(length)[:len(out)]
    env = (t / length) ** 2 if rise else np.exp(-t / (length * .3))
    return out * env


def boom(length=2.0, freq=48):
    """A deep impact: a falling sine thump and a noise crack."""
    t = seconds(length)
    pitch = freq * (1 + 1.5 * np.exp(-t / .05))
    thump = np.sin(2 * np.pi * np.cumsum(pitch) / RATE) * envelope(t, .002, .45)
    crack = lowpass(RNG.normal(0, 1, len(t)), 1800) * envelope(t, .001, .08) * .5
    return thump + crack


def sparkle(length, density=30, low=3000, high=9000):
    """Many tiny high bells: shimmering dust."""
    t = seconds(length)
    out = np.zeros_like(t)
    for _ in range(int(density * length)):
        at = RNG.uniform(0, length * .85)
        f = RNG.uniform(low, high)
        n = int(.25 * RATE)
        i = int(at * RATE)
        seg = np.sin(2 * np.pi * f * seconds(.25)) * envelope(seconds(.25), .001, .06) * RNG.uniform(.2, 1)
        out[i:i + n] += seg[:len(out) - i]
    return out * np.exp(-t / (length * .6))


def reverb(x, length=2.4, mix=.35):
    """Stereo reverb: decaying noise impulse responses, a little different per side."""
    n = int(length * RATE)
    tail = seconds(length)
    sides = []
    for side in range(2):
        ir = RNG.normal(0, 1, n) * np.exp(-tail / (length * .28))
        ir = lowpass(ir, 7000 - side * 600)
        ir /= np.sqrt(np.sum(ir ** 2))
        size = len(x) + n
        wet = np.fft.irfft(np.fft.rfft(x, size) * np.fft.rfft(ir, size), n=size)
        dry = np.concatenate([x, np.zeros(n)])
        sides.append(dry * (1 - mix) + wet * mix * 3)
    return np.stack(sides, -1)


def save(name, mono, gain=.8, verb=2.4, mix=.35):
    stereo = reverb(mono, verb, mix)
    stereo = np.tanh(stereo / (np.abs(stereo).max() + 1e-9) * 1.4) * gain     # Gentle limit.
    fade = int(.05 * RATE)
    stereo[-fade:] *= np.linspace(1, 0, fade)[:, None]
    os.makedirs(OUT, exist_ok=True)
    data = (stereo * 32767).astype('<i2')
    with wave.open(os.path.join(OUT, name + '.wav'), 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(data.tobytes())
    print('wrote', name, f'{len(stereo) / RATE:.1f}s')


def pad(names, length):
    return choir([note(n) for n in names], length, attack=length * .4, release=length * .45)


def mix(length, *parts):
    out = np.zeros(int(length * RATE))
    for at, part, level in parts:
        i = int(at * RATE)
        n = min(len(part), len(out) - i)
        out[i:i + n] += part[:n] * level
    return out


def main():
    # The sky opens: a soft high pad with dust.
    save('open', mix(3.0, (0, pad(['E4', 'B4', 'D#5', 'G#5'], 3.0), .25), (0, sparkle(3.0, 14), .5),
                     (0, noise_sweep(3.0, 3000, 800, rise=False), .05)), gain=.55, verb=3.0, mix=.5)
    # Touching a wishing star.
    save('catch', mix(1.0, (0, bell(note('E6'), 1.0, .5), .6), (.03, bell(note('B6'), .9, .4), .35),
                      (0, sparkle(.8, 25), .4)), gain=.6, verb=1.6, mix=.4)
    # Light pouring into her hands: a rising shimmer.
    t = seconds(.7)
    rise = np.sin(2 * np.pi * np.cumsum(600 * 2 ** (t * 2.2)) / RATE) * (t / .7) ** 2 * .3
    save('charge', mix(.75, (0, rise, 1), (0, noise_sweep(.7, 1500, 9000), .35), (0, sparkle(.7, 50), .5)),
         gain=.55, verb=1.4, mix=.35)
    # Galaxy and Starsea gather themselves first: a long riser with a drum swell.
    t = seconds(1.9)
    roll = lowpass(RNG.normal(0, 1, len(t)), 220) * (t / 1.9) ** 2.5
    tones = sum(np.sin(2 * np.pi * np.cumsum(f * 2 ** (t * .9)) / RATE) for f in (220, 330, 440)) * (t / 1.9) ** 2 * .12
    save('rise', mix(1.95, (0, noise_sweep(1.9, 300, 6000), .5), (0, roll, .8), (0, tones, 1),
                     (0, sparkle(1.9, 40), .3)), gain=.7, verb=2.0, mix=.35)
    # Bursts, from modest to grand.
    save('burst_fanxing', mix(1.6, (0, bell(note('G5'), 1.6, .9), .6), (.06, bell(note('D6'), 1.5, .8), .4),
                              (0, sparkle(1.2, 20), .35)), gain=.55, verb=2.0, mix=.38)
    save('burst_mingyue', mix(2.0, (0, bell(note('A5'), 2.0, 1.1, 1.3), .6), (.16, bell(note('E6'), 1.8, 1.0, 1.3), .55),
                              (0, sparkle(1.6, 35, 4000, 10000), .45), (0, pad(['A4', 'E5'], 1.8), .12)),
         gain=.6, verb=2.4, mix=.42)
    save('burst_haori', mix(3.0, (0, boom(1.6, 52), .45), (0, bell(note('D5'), 2.8, 1.4), .45),
                            (.02, bell(note('F#5'), 2.6, 1.3), .35), (.04, bell(note('A5'), 2.6, 1.3), .35),
                            (.0, pad(['D4', 'A4', 'F#5'], 2.6), .18), (.05, sparkle(2.4, 45), .45)),
         gain=.72, verb=2.8, mix=.42)
    arp = mix(1.4, *[(k * .07, bell(note(n), 1.2, .8), .35) for k, n in enumerate(['C6', 'E6', 'G6', 'B6', 'D7', 'E7'])])
    save('burst_yinhe', mix(3.6, (0, boom(2.0, 44), .6), (0, pad(['C4', 'G4', 'B4', 'E5'], 3.4), .3),
                            (.08, arp, 1), (0, bell(note('C5'), 3.2, 1.8), .4), (.1, sparkle(3.0, 50), .5)),
         gain=.78, verb=3.2, mix=.45)
    harp = mix(1.2, *[(k * .045, pluck(note(n), 1.0), .4) for k, n in
                      enumerate(['C5', 'E5', 'G5', 'B5', 'D6', 'E6', 'G6', 'B6', 'D7', 'E7'])])
    save('burst_xinghai', mix(4.2, (0, boom(2.2, 40), .7), (.05, harp, 1), (0, pad(['C4', 'G4', 'E5', 'B5'], 4.0), .34),
                              (.5, pad(['F4', 'C5', 'A5', 'E6'], 3.6), .22), (0, bell(note('C6'), 3.6, 2.0, 1.4), .4),
                              (.1, sparkle(3.6, 70, 3000, 11000), .55)), gain=.82, verb=3.6, mix=.48)
    # Cards turning.
    flick = noise_sweep(.22, 6000, 1500, rise=False) * .6
    save('flip', mix(.3, (0, flick, 1), (.02, bell(note('E7'), .25, .08), .08)), gain=.4, verb=.8, mix=.25)
    save('flip_fine', mix(1.2, (0, flick, 1), (.03, bell(note('B6'), 1.1, .6), .5), (.03, sparkle(.9, 30), .3)),
         gain=.5, verb=1.6, mix=.35)


if __name__ == '__main__':
    main()
