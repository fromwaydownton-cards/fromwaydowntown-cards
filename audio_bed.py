"""An original, synthesized hip-hop style beat (no samples, no copyrighted music).

92 BPM, Am - F - C - G, kick / snare / hats / bass / soft pad, with fades.
Each call can pass a seed so different videos get slightly different patterns.
"""
import wave

import numpy as np

SR = 44100


def _env(n, attack=0.005, decay=0.25):
    t = np.arange(n) / SR
    a = np.clip(t / attack, 0, 1)
    return a * np.exp(-t / decay)


def _kick():
    n = int(0.35 * SR)
    t = np.arange(n) / SR
    f = 110 * np.exp(-t * 18) + 45
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(n, 0.001, 0.18)


def _snare(rng):
    n = int(0.25 * SR)
    noise = rng.standard_normal(n)
    noise = np.convolve(noise, [1, -0.6], "same")
    tone = np.sin(2 * np.pi * 190 * np.arange(n) / SR)
    return (0.7 * noise + 0.4 * tone) * _env(n, 0.001, 0.09)


def _hat(rng, open_=False):
    n = int((0.18 if open_ else 0.05) * SR)
    noise = np.diff(rng.standard_normal(n + 1))
    return noise * _env(n, 0.0005, 0.06 if open_ else 0.015)


def _note(freq, dur, kind="saw", decay=0.5):
    n = int(dur * SR)
    t = np.arange(n) / SR
    if kind == "saw":
        w = 2 * (t * freq % 1) - 1
        w = np.convolve(w, np.ones(24) / 24, "same")      # soften
    else:
        w = np.sin(2 * np.pi * freq * t) + 0.3 * np.sin(4 * np.pi * freq * t)
    return w * _env(n, 0.01, decay)


def write_beat(path, seconds, seed=7):
    rng = np.random.default_rng(seed)
    bpm = 92
    beat = 60 / bpm
    total = int(seconds * SR) + SR
    mix = np.zeros(total)

    def add(sig, at, gain):
        i = int(at * SR)
        j = min(total, i + len(sig))
        if i < total:
            mix[i:j] += gain * sig[: j - i]

    kick, snare = _kick(), _snare(rng)
    chords = [(220.0, [220.0, 261.63, 329.63]), (174.61, [174.61, 220.0, 261.63]),
              (130.81, [261.63, 329.63, 392.0]), (196.0, [196.0, 246.94, 293.66])]
    bar = 4 * beat
    t, b = 0.0, 0
    while t < seconds:
        root, triad = chords[b % 4]
        for s in range(8):                      # eighth notes
            at = t + s * beat / 2
            if s in (0, 5) or (s == 3 and b % 2):
                add(kick, at, 0.9)
            if s in (2, 6):
                add(snare, at, 0.5)
            add(_hat(rng, open_=(s == 7)), at + (0.02 if s % 2 else 0), 0.18)
        for s, off in enumerate((0, 1.5, 2.5)):
            add(_note(root / 2, beat * 0.9, "sine", 0.35), t + off * beat, 0.55)
        for f in triad:
            add(_note(f, bar, "saw", 1.4), t, 0.05)
        t += bar
        b += 1
    mix = mix[: int(seconds * SR)]
    fade = int(1.5 * SR)
    mix[:fade] *= np.linspace(0, 1, fade)
    mix[-fade:] *= np.linspace(1, 0, fade)
    mix = mix / (np.max(np.abs(mix)) + 1e-9) * 0.7
    data = (mix * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())
