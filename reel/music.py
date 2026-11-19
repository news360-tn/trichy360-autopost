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


# owner 19 Nov: the gold & silver reel (10 s, music only, Kovai Minnal pattern - "better music no sad music") uses a brighter, quicker
# bed; every other reel keeps the soft one exactly as before
MOODS = {"soft": {"roots": [220.0, 196.0, 233.08, 207.65], "scale": [1, 6 / 5, 4 / 3, 3 / 2, 9 / 5, 2], "bpm": 84, "prog": [0, 3, 4, 3],
                  "pluck": 0.72, "kicks": 1, "fade_in": 0.8, "hats": False},      # A3 / G3 / Bb3 / Ab3, minor pentatonic, i - iv - v - iv
         "bright": {"roots": [261.63, 293.66, 246.94, 277.18], "scale": [1, 9 / 8, 5 / 4, 3 / 2, 5 / 3, 2], "bpm": 116,
                    "prog": [0, 3, 4, 2], "pluck": 0.88, "kicks": 4, "fade_in": 0.03, "hats": True}}      # C4 / D4 / B3 / C#4, major


def make(seconds, seed=0, mood="soft"):
    m_ = MOODS.get(mood, MOODS["soft"])
    rng = np.random.default_rng(seed)
    n = int(seconds * SR)
    out = np.zeros(n)
    root = m_["roots"][seed % 4]
    scale = m_["scale"]
    bpm = m_["bpm"]
    beat = int(SR * 60 / bpm)
    bar = beat * 4
    prog = m_["prog"]                                           # scale degrees
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
            if rng.random() < m_["pluck"]:
                st = s + k * (beat // 2)
                note = root * scale[rng.integers(0, len(scale))] * (2 if k % 4 else 1)
                m = min(n - st, int(SR * 0.7))
                if m > 0:
                    out[st:st + m] += 0.07 * tone(note, m, "pluck")
        for kk in range(m_["kicks"]):                           # soft: one low pulse each bar; bright: on every beat
            kick = s + kk * beat
            m = min(n - kick, int(SR * 0.25))
            if m > 0:
                tt = np.arange(m) / SR
                out[kick:kick + m] += 0.12 * np.sin(2 * np.pi * (60 + 80 * np.exp(-tt * 25)) * tt) * np.exp(-tt * 12)
        if m_["hats"]:                                          # bright: a light off-beat tick (its own random numbers)
            hr = np.random.default_rng(seed + 99)
            for kk in range(4):
                st = s + kk * beat + beat // 2
                m = min(n - st, int(SR * 0.05))
                if m > 0:
                    tt = np.arange(m) / SR
                    out[st:st + m] += 0.035 * np.diff(hr.standard_normal(m + 1)) * np.exp(-tt * 90)
    out /= max(1e-6, np.abs(out).max())
    out *= 0.9
    fi = max(1, int(SR * m_["fade_in"])); fo = int(SR * 1.2)
    out[:fi] *= np.linspace(0, 1, fi); out[-fo:] *= np.linspace(1, 0, fo)
    return out


def main(path, seconds, seed=0, mood="soft"):
    y = make(float(seconds), int(seed), mood)
    pcm = (y * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())


if __name__ == "__main__":
    main(*sys.argv[1:])
