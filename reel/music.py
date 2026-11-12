"""Original royalty-free background bed (generated, so no copyright claim): soft pad + gentle pluck pattern in a warm minor pentatonic mood.
Usage: python3 music.py out.wav seconds [seed]"""
import sys, wave
import numpy as np

SR = 44100


def tone(f, n, kind="pad"):
    t = np.arange(n) / SR
    if kind == "pad":
        y = sum(np.sin(2 * np.pi * f * k * t + p) / k for k, p in ((1, 0), (2, .7), (3, 1.9)))
        y *= 0.5 + 0.5 * np.sin(2 * np.pi * 0.11 * t)
    else:  # pluck
        y = (np.sin(2 * np.pi * f * t) + 0.4 * np.sin(2 * np.pi * 2 * f * t)) * np.exp(-t * 5.5)
    return y


def make(seconds, seed=0):
    rng = np.random.default_rng(seed)
    n = int(seconds * SR)
    out = np.zeros(n)
    root = [220.0, 196.0, 233.08, 207.65][seed % 4]            # A3 / G3 / Bb3 / Ab3
    scale = [1, 6 / 5, 4 / 3, 3 / 2, 9 / 5, 2]                 # minor pentatonic ratios
    bpm = 84
    beat = int(SR * 60 / bpm)
    bar = beat * 4
    prog = [0, 3, 4, 3]                                         # i - iv - v - iv (scale degrees)
    for b in range((n // bar) + 1):
        deg = scale[prog[b % 4]]
        s = b * bar
        e = min(n, s + bar)
        if s >= n:
            break
        seg = e - s
        for ratio in (1, 1.5, 2):                               # open fifth pad
            y = tone(root * deg * ratio / 2, seg, "pad")
            fade = np.minimum(1, np.minimum(np.arange(seg), seg - np.arange(seg)) / (0.4 * SR))
            out[s:e] += 0.10 * y * fade
        for k in range(8):                                      # pluck pattern, 8th notes
            if rng.random() < 0.72:
                st = s + k * (beat // 2)
                note = root * scale[rng.integers(0, len(scale))] * (2 if k % 4 else 1)
                m = min(n - st, int(SR * 0.7))
                if m > 0:
                    out[st:st + m] += 0.07 * tone(note, m, "pluck")
        kick = s + 0
        m = min(n - kick, int(SR * 0.25))
        if m > 0:
            tt = np.arange(m) / SR
            out[kick:kick + m] += 0.12 * np.sin(2 * np.pi * (60 + 80 * np.exp(-tt * 25)) * tt) * np.exp(-tt * 12)   # soft low pulse each bar
    out /= max(1e-6, np.abs(out).max())
    out *= 0.9
    fi = int(SR * 0.8); fo = int(SR * 1.2)
    out[:fi] *= np.linspace(0, 1, fi); out[-fo:] *= np.linspace(1, 0, fo)
    return out


def main(path, seconds, seed=0):
    y = make(float(seconds), int(seed))
    pcm = (y * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())


if __name__ == "__main__":
    main(*sys.argv[1:])
