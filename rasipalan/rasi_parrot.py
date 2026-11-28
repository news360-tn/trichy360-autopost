"""owner 28 Nov (approved after review of the samples): the daily rasipalan told by a parrot - கிளி ஜோசியம் - on every page.
rasi_daily.py makes this reel first; when it cannot be made the usual rasipalan reel (rasi_reel.py) goes out, so a day is never missed.

A green parrot sits on its cage; 12 rasi cards stand on a red mat. For each rasi the parrot hops to the card, picks it with its beak,
the card flies up and opens into the big fortune card (stars, the four lines, lucky number + colour, remedy) while the parrot reads
the rasi's work and money line in the Valluvar voice - its beak moves with the voice. Opens with today's lucky rasis (the hook, from
the first frame = the cover) and ends with the follow card. Our own music bed stays low under the voice.

make(p, ctx, outdir, log) -> mp4 path     p: town, name1, handle, logo     ctx: {"p": panchangam, "rasis": the 12 written rasis}
Same frame-by-frame recording as rasi_reel.py (window.DUR, window.seek(t)), so it can replace that reel later without other changes."""
import json
import re
import subprocess
import sys
import wave
from html import escape as E
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "goldrate"))
sys.path.insert(0, str(HERE))
import gold360_render as G      # noqa: E402
import gold_reel      # noqa: E402
import rasi360_render as R      # noqa: E402
from rasi_render import GLYPH, LUCKY_NUM, LUCKY_COL, RASI_EN      # noqa: E402

FPS, W, H = 30, 1080, 1920
SR = 24000
VOICE = ("ta-IN-ValluvarNeural", "+12%", "+4Hz")      # the page's news voice (poster/config.json reel_voice)
MUSIC_VOL = 0.18
MAROON, MAROON2, GOLD = G.MAROON, G.MAROON2, G.GOLD

# geometry (px)
CARD_TOP, CARD_H = 250, 830                   # the big fortune card
HOME = (30, 1162)                             # the parrot on its cage (top-left of the parrot box)
SMALL_W, SMALL_H, SMALL_Y, SMALL_X0, SMALL_GAP = 52, 150, 1650, 318, 10
BIG_C = (540, CARD_TOP + CARD_H // 2)
PARROT_Y_AT_CARD = 1520
HOP_S, PECK_S, BACK_S = 0.45, 0.35, 0.45      # hop to the card, pick it, hop back
VOICE_AT = 1.0                                # the voice starts once the card is open

PARROT = """<svg viewBox="0 0 260 300" width="221" height="255" overflow="visible">
<path d="M72 196 L8 296 L34 298 L98 214 Z" fill="#2E9E57"/><path d="M84 204 L38 299 L58 299 L106 220 Z" fill="#1F7FB8"/>
<ellipse cx="110" cy="170" rx="62" ry="82" fill="#43B649"/><ellipse cx="130" cy="192" rx="38" ry="58" fill="#8BD46A"/>
<g id="wing" style="transform-origin:96px 128px"><path d="M96 124 C48 140 44 216 86 252 C112 230 122 170 96 124 Z" fill="#2E8F3E"/>
<path d="M70 200 C80 215 90 230 86 248" stroke="#1E6B2C" stroke-width="4" fill="none"/>
<path d="M60 176 C72 190 80 206 82 222" stroke="#1E6B2C" stroke-width="4" fill="none"/></g>
<path d="M100 246 l-10 30 M100 246 l2 32 M100 246 l12 28 M136 244 l-8 33 M136 244 l4 35 M136 244 l14 30" stroke="#7A7A7A"
 stroke-width="7" stroke-linecap="round"/>
<g id="head" style="transform-origin:140px 122px">
<circle cx="150" cy="82" r="50" fill="#4CC456"/>
<path d="M112 112 Q150 150 192 108" stroke="#111" stroke-width="7" fill="none"/>
<path d="M114 122 Q150 158 190 118" stroke="#F48FB1" stroke-width="6" fill="none"/>
<circle cx="165" cy="70" r="13" fill="#fff"/><circle cx="168" cy="70" r="7" fill="#111"/><circle cx="171" cy="66" r="2.5" fill="#fff"/>
<ellipse id="lid" cx="165" cy="70" rx="14.5" ry="14.5" fill="#4CC456" style="transform-origin:165px 70px;transform:scaleY(0)"/>
<g id="beak" style="transform-origin:190px 97px"><path d="M188 96 Q211 104 206 117 Q193 118 186 104 Z" fill="#8E1B16"/></g>
<path d="M184 60 Q232 66 226 104 Q222 117 212 112 Q214 92 190 98 Q180 84 184 60 Z" fill="#E53935"/>
</g></svg>"""

CAGE = f"""<svg viewBox="0 0 240 280" width="240" height="280" style="position:absolute;left:18px;top:1380px">
<path d="M20 70 Q120 -10 220 70" fill="none" stroke="#8D5A2B" stroke-width="12"/>
<rect x="14" y="66" width="212" height="200" rx="10" fill="rgba(255,255,255,.12)" stroke="#8D5A2B" stroke-width="10"/>
{''.join(f'<line x1="{x}" y1="70" x2="{x}" y2="262" stroke="#A9743F" stroke-width="5"/>' for x in range(38, 220, 26))}
<rect x="6" y="252" width="228" height="24" rx="8" fill="#6D4220"/><circle cx="120" cy="18" r="12" fill="none" stroke="#8D5A2B" stroke-width="7"/>
</svg>"""

CSS = f"""
.pr{{position:absolute;inset:0;overflow:hidden}}
.band{{position:absolute;left:0;right:0;top:0;height:220px;display:flex;align-items:center;gap:26px;padding:0 44px;
 background:linear-gradient(180deg,{MAROON2},{MAROON});box-shadow:0 10px 26px rgba(58,7,11,.35)}}
.band img{{width:150px;height:150px;border-radius:50%;background:#fff;box-shadow:0 0 0 6px {GOLD}}}
.band .bn{{flex:1;min-width:0;color:#fff;font-size:60px;font-weight:900;line-height:1.15;white-space:nowrap}}
.band .bn i{{font-style:normal;color:{GOLD};font-family:'Catamaran'}}
.band .bn small{{display:block;font-size:34px;font-weight:800;color:#F6E3A6}}
.band .dt{{color:{GOLD};font-size:34px;font-weight:800;text-align:right;line-height:1.3;white-space:nowrap}}
.fc{{position:absolute;left:46px;width:988px;top:{CARD_TOP}px;height:{CARD_H}px;border-radius:44px;overflow:hidden;
 background:linear-gradient(165deg,#FFFBEA 0%,#FCEBB8 100%);box-shadow:0 22px 44px rgba(58,7,11,.35),inset 0 0 0 6px {GOLD},inset 0 0 0 14px #FFF6D8;
 opacity:0;backface-visibility:hidden}}
.fcin{{position:absolute;left:40px;top:34px;width:1135px;transform:scale(.8);transform-origin:0 0}}
.fc .rhead{{margin-top:0}} .fc .rlines{{margin-top:26px}} .fc .rl{{min-height:122px}} .fc .luck{{margin-top:26px}} .fc .rem{{margin-top:24px}}
.fc .kick{{font-size:38px;font-weight:800;color:{MAROON};opacity:.8;margin-bottom:6px}}
.hk{{text-align:center;padding-top:92px}}
.fc .ptitle{{font-size:66px}} .fc .ptable{{padding:4px 34px}} .fc .prow{{min-height:116px}} .fc .prow .v{{font-size:42px}}
.hk .t1{{font-size:98px;font-weight:900;color:{MAROON};line-height:1.2;white-space:nowrap}}
.hk .t2{{margin-top:6px;font-size:42px;font-weight:800;color:{MAROON};opacity:.85}}
.hk .t3{{display:inline-block;margin-top:34px;background:{MAROON};color:{GOLD};border-radius:40px;padding:10px 40px;font-size:46px;font-weight:900}}
.hk .best{{display:flex;justify-content:center;gap:26px;margin-top:34px}}
.hk .best>div{{width:290px;background:linear-gradient(160deg,{MAROON2},{MAROON});border-radius:30px;padding:16px 8px 20px;color:#fff;
 box-shadow:0 14px 28px rgba(58,7,11,.3),inset 0 0 0 4px {GOLD}}}
.hk .best .g{{font-family:'Zod';font-size:86px;line-height:1.1;color:{GOLD}}}
.hk .best .n{{font-size:50px;font-weight:900;line-height:1.3;white-space:nowrap}}
.hk .best .s{{font-size:34px;color:{GOLD};letter-spacing:2px}}
.hk .w{{margin-top:34px;font-size:40px;font-weight:800;color:#C62828}}
.en{{text-align:center;padding-top:90px}}
.en img{{width:300px;height:300px;border-radius:50%;background:#fff;box-shadow:0 0 0 10px {GOLD},0 20px 40px rgba(58,7,11,.35)}}
.en .n{{margin-top:40px;font-size:96px;font-weight:900;color:{MAROON}}} .en .n i{{font-style:normal;color:{GOLD};font-family:'Catamaran'}}
.en .s{{margin-top:10px;font-size:46px;font-weight:800;color:{MAROON};opacity:.85}}
.en .f{{display:inline-block;margin-top:46px;background:{MAROON};color:{GOLD};border-radius:50px;padding:16px 50px;font-size:52px;font-weight:900;
 font-family:'Catamaran'}}
.table{{position:absolute;left:0;right:0;top:1560px;bottom:0;background:linear-gradient(180deg,#9C6435 0%,#6E4220 100%)}}
.mat{{position:absolute;left:292px;right:18px;top:1606px;height:270px;border-radius:18px;background:#B71C1C;
 box-shadow:inset 0 0 0 8px {GOLD},inset 0 0 0 14px #B71C1C,inset 0 0 0 17px {GOLD},0 10px 20px rgba(0,0,0,.35)}}
.sc{{position:absolute;top:{SMALL_Y}px;width:{SMALL_W}px;height:{SMALL_H}px;border-radius:8px;background:linear-gradient(180deg,#FFF8E1,#F3D98B);
 box-shadow:0 6px 10px rgba(0,0,0,.35),inset 0 0 0 3px {MAROON};text-align:center;transform-origin:50% 50%}}
.sc b{{display:block;margin-top:10px;font-family:'Zod';font-size:34px;line-height:1;color:{MAROON}}}
.sc i{{position:absolute;left:8px;right:8px;bottom:14px;height:58px;border-radius:6px;background:repeating-linear-gradient(45deg,{MAROON} 0 6px,#C49A2C 6px 12px)}}
#parrot{{position:absolute;left:0;top:0;z-index:5;will-change:transform;transform-origin:0 100%}}
.sc.fly{{z-index:6}}
"""


def _ffmpeg():
    return gold_reel.ffmpeg()


def say(text, work, n, log=print):
    """one line in the Valluvar voice -> float32 samples at SR, the silence at both ends trimmed"""
    mp3, raw = work / f"v{n}.mp3", work / f"v{n}.raw"
    v, rate, pitch = VOICE
    for _ in range(3):
        r = subprocess.run([sys.executable, "-m", "edge_tts", "--voice", v, f"--rate={rate}", f"--pitch={pitch}", "--text", text,
                            "--write-media", str(mp3)], timeout=120)
        if r.returncode == 0 and mp3.exists() and mp3.stat().st_size > 1000:
            break
    else:
        raise RuntimeError(f"voice not made for: {text[:60]}")
    subprocess.run([_ffmpeg(), "-y", "-loglevel", "error", "-i", str(mp3), "-ac", "1", "-ar", str(SR), "-f", "s16le", str(raw)], check=True)
    a = np.frombuffer(raw.read_bytes(), dtype=np.int16).astype(np.float32) / 32768
    nz = np.where(np.abs(a) > 0.012)[0]
    if len(nz):
        a = a[max(0, nz[0] - int(.03 * SR)): nz[-1] + int(.1 * SR)]
    log(f"voice {n}: {len(a) / SR:.1f} s - {text[:70]}")
    return a


def lines(p, P, rasis):
    """what the parrot says: the hook (today's lucky rasis), each rasi's work + money line, the follow line"""
    stars = [int(r.get("stars") or 3) for r in rasis]
    best = sorted(range(12), key=lambda i: -stars[i])[:3] if len(set(stars)) > 1 else []
    hook = ("கிளி ஜோசியம்! இன்று " + ", ".join(rasis[i]["rasi"] for i in best) + " ராசிக்கு அதிர்ஷ்ட நாள்."
            if best else "கிளி ஜோசியம்! இன்று பன்னிரண்டு ராசிகளுக்கும் பலன் பார்க்கலாம்.")
    say_r = []
    for r in rasis:
        t = f'{r["rasi"]}. {str(r.get("work") or "").rstrip(".")}.'      # one line spoken (the card shows all four) - a shorter reel
        if r.get("rasi") == P.get("chandrashtamam"):
            t += " இன்று சந்திராஷ்டமம், கவனம் தேவை."
        say_r.append(t)
    end = f'தினமும் கிளி ஜோசியம் கேட்க, {p["name1"]} த்ரீ சிக்ஸ்டி பக்கத்தை ஃபாலோ பண்ணுங்க.'
    parts = []      # owner 28 Nov: the parrot also reads today's good time and rahu kalam (the old reel's panchangam screen)
    if P.get("nalla_morning"):
        parts.append(f'நல்ல நேரம் காலை {spoken_span(P["nalla_morning"])}')
    if P.get("rahu"):
        parts.append(f'ராகு காலம் {spoken_span(with_period(P["rahu"]))}')
    panch = "இன்றைய பஞ்சாங்கம். " + ". ".join(parts) + "." if parts else "இன்றைய பஞ்சாங்கம் பாருங்கள்."
    return best, hook, panch, say_r, end


def spoken_span(s):
    """'10:30 - 12:00' -> '10:30 முதல் 12:00 வரை' (how a news reader says a time span)"""
    s = str(s or "").strip()
    return re.sub(r"\s*[-–]\s*", " முதல் ", s, count=1) + " வரை" if re.search(r"\d\s*[-–]\s*\d", s) else s


def with_period(s):
    """owner 28 Nov: '9:00 – 10:30' -> 'காலை 9:00 – 10:30', '1:30 – 3:00' -> 'மதியம் 1:30 – 3:00' (12-hour times without AM / PM are
    unclear when heard); a value that already says காலை / மதியம் / மாலை / இரவு is kept"""
    s = str(s or "").strip()
    m = re.match(r"(\d{1,2}):\d{2}", s)
    if not s or not m or re.match(r"(காலை|மதியம்|மாலை|இரவு|அதிகாலை)", s):
        return s
    h = int(m.group(1))
    word = "காலை" if 5 <= h <= 11 else "மதியம்" if h == 12 or h <= 3 else "மாலை" if h <= 7 else "இரவு"
    return f"{word} {s}"


def panch_rows(P):
    rows = [("நல்ல நேரம்", f'காலை {P["nalla_morning"]}', f'மாலை {P["nalla_evening"]}' if P.get("nalla_evening") else "", "good")
            if P.get("nalla_morning") else None,
            ("ராகு காலம்", with_period(P.get("rahu")), "", "bad"), ("எமகண்டம்", with_period(P.get("emagandam")), "", "bad"),
            ("திதி", P.get("tithi"), P.get("tithi_end") or "", ""), ("நட்சத்திரம்", P.get("nakshatra"), P.get("nakshatra_end") or "", ""),
            ("சந்திராஷ்டமம்", P.get("chandrashtamam"), "இந்த ராசிக்கு இன்று கவனம்", "bad")]
    return [r for r in rows if r and r[1]]


def chirp():
    """the parrot's two short tweets when it picks a card (made here - no sound file needed)"""
    out = []
    for f0, f1 in ((2900, 4300), (3300, 4700)):
        n = int(0.075 * SR)
        f = np.linspace(f0, f1, n)
        out += [0.32 * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.hanning(n), np.zeros(int(0.045 * SR))]
    return np.concatenate(out).astype(np.float32)


def flip():
    """a soft paper flip when the card opens"""
    n = int(0.11 * SR)
    noise = np.random.default_rng(7).standard_normal(n)
    noise = np.diff(noise, prepend=0) * np.exp(-np.linspace(0, 6, n))
    return (0.16 * noise / (np.abs(noise).max() or 1)).astype(np.float32)


LAST = {}      # the last reel's caption block (rasi_daily.py puts it into the page's own caption)


def times_block(rasis, segs):
    """'⏱ உங்கள் ராசி எந்த நேரத்தில்:' + each rasi's start time in the reel, three a line"""
    times = [f'{rasis[s["i"]]["rasi"]} {int(s["t0"] + 1) // 60}:{int(s["t0"] + 1) % 60:02d}' for s in segs if s["kind"] == "rasi"]
    return "⏱ உங்கள் ராசி எந்த நேரத்தில்:\n" + "\n".join(" • ".join(times[k:k + 3]) for k in range(0, 12, 3))


def with_times(cap, block):
    """the page's caption with the rasi times block put in just before the hashtags (or at the end)"""
    if not block:
        return cap
    lines = cap.rstrip().split("\n")
    k = next((i for i in range(len(lines) - 1, -1, -1) if lines[i].strip().startswith("#")), None)
    if k is None:
        return cap.rstrip() + "\n\n" + block
    while k > 0 and lines[k - 1].strip().startswith("#"):
        k -= 1
    return "\n".join(lines[:k]).rstrip() + "\n\n" + block + "\n\n" + "\n".join(lines[k:])


def caption_text(p, P, best, rasis, segs):
    """owner 28 Nov: the caption tells each viewer where his rasi starts (people jump to their own rasi instead of leaving)"""
    rows = times_block(rasis, segs).split("\n", 1)[1]
    luck = ", ".join(rasis[i]["rasi"] for i in best)
    pan = "\n".join(f"{k}: {v}" + (f" ({s})" if s else "") for k, v, s, _ in panch_rows(P)[:3])
    return (f"🦜 கிளி ஜோசியம் | {P['date_ta']}, {P['weekday_full']}\n"
            + (f"✨ இன்று அதிர்ஷ்டம்: {luck}\n" if luck else "") +
            f"\n⏱ உங்கள் ராசி எந்த நேரத்தில்:\n{rows}\n\n📿 {pan}\n\n"
            f"தினமும் காலை கிளி ஜோசியம் பார்க்க @{p['handle']} Follow செய்யுங்கள்.\n\n#ராசிபலன் #RasiPalan #கிளிஜோசியம் #{p['name1']}360")


PINNED_COMMENT = "உங்கள் ராசி என்ன? கமெண்டில் சொல்லுங்க 👇 கிளி உங்களுக்கு என்ன சொன்னது?"


def timeline(voices):
    """voices: [hook, panchangam, 12 rasis, end] sample arrays -> scenes [{kind, i, t0, t1, v0}] and the whole length"""
    segs, t = [], 0.0
    d = len(voices[0]) / SR
    segs.append({"kind": "hook", "i": -1, "t0": 0.0, "v0": 0.3, "t1": round(max(3.2, 0.3 + d + 0.5), 2)})
    t = segs[-1]["t1"]
    d = len(voices[1]) / SR
    segs.append({"kind": "panch", "i": -1, "t0": round(t, 2), "v0": round(t + 0.4, 2), "t1": round(t + max(3.4, 0.4 + d + 0.5), 2)})
    t = segs[-1]["t1"]
    for i in range(12):
        d = len(voices[2 + i]) / SR
        t1 = round(t + max(3.8, VOICE_AT + d + 0.3), 2)
        segs.append({"kind": "rasi", "i": i, "t0": round(t, 2), "v0": round(t + VOICE_AT, 2), "t1": t1})
        t = t1
    d = len(voices[14]) / SR
    segs.append({"kind": "end", "i": -1, "t0": round(t, 2), "v0": round(t + 0.4, 2), "t1": round(t + 0.4 + d + 0.9, 2)})
    return segs, segs[-1]["t1"]


def voice_track(voices, segs, dur):
    track = np.zeros(int(dur * SR) + SR, dtype=np.float32)
    for a, s in zip(voices, segs):
        k = int(s["v0"] * SR)
        track[k:k + len(a)] += a[:len(track) - k]
    return track[:int(dur * SR)]


def envelope(track):
    """how wide the beak opens, per video frame (0..1), from the voice's loudness"""
    hop = SR // FPS
    n = len(track) // hop
    rms = np.sqrt(np.mean(track[:n * hop].reshape(n, hop) ** 2, axis=1))
    top = np.percentile(rms[rms > 0.005], 95) if np.any(rms > 0.005) else 1.0
    env = np.clip(rms / (top or 1.0), 0, 1) ** 0.7
    env[env < 0.12] = 0
    return [round(float(x), 2) for x in env]


def write_wav(path, a):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(a, -1, 1) * 32767).astype(np.int16).tobytes())


def card_x(i):
    return SMALL_X0 + i * (SMALL_W + SMALL_GAP)


def fortune(p, P, i, r):
    stars = int(r.get("stars") or 3)
    st = "".join(f'<b class="{"" if k < stars else "off"}">★</b>' for k in range(5))
    warn = '<span class="warn">சந்திராஷ்டமம் • கவனம்</span>' if r.get("rasi") == P.get("chandrashtamam") else ""
    rows = "".join(f'<div class="rl"><em>{lab}</em><span class="fit">{E(str(r.get(key) or ""))}</span></div>' for key, lab in R.LABELS)
    col_name, col_hex = LUCKY_COL[i]
    rem = r.get("remedy") or ""
    return (f'<div class="fc"><div class="fcin"><div class="kick">கிளி எடுத்த சீட்டு • {i + 1}/12</div>'
            f'<div class="rhead"><div class="med">{G.dial()}<span class="g">{GLYPH[i]}&#xFE0E;</span></div>'
            f'<div><div class="rname fit">{E(r.get("rasi") or "")}</div><div class="ren">{RASI_EN[i]}</div>'
            f'<div><span class="stars">{st}</span>{warn}</div></div></div>'
            f'<div class="rlines">{rows}</div>'
            f'<div class="luck"><div>அதிர்ஷ்ட எண் <b>{LUCKY_NUM[i]}</b></div><div>நிறம் <i style="background:{col_hex}"></i> {col_name}</div></div>'
            + (f'<div class="rem">பரிகாரம்<b>{E(rem)}</b></div>' if rem else "") + '</div></div>')


def page(p, ctx, segs, dur, env, best):
    P, rasis = ctx["p"], ctx["rasis"]
    logo = f"file://{Path(p['logo']).resolve()}"
    day = f'{P["weekday_full"]} • {P["tamil_month"]} {P["tamil_day"]}'
    stars = [int(r.get("stars") or 3) for r in rasis]
    cells = "".join(f'<div><div class="g">{GLYPH[i]}&#xFE0E;</div><div class="n">{E(rasis[i]["rasi"])}</div>'
                    f'<div class="s">{"★" * stars[i]}</div></div>' for i in best)
    warn = f'<div class="w">சந்திராஷ்டமம்: {E(P.get("chandrashtamam") or "")} • கவனம்</div>' if P.get("chandrashtamam") else ""
    hook = (f'<div class="fc"><div class="hk"><div class="t1">கிளி ஜோசியம்</div><div class="t2">{E(P["date_ta"])} • {E(P["weekday_full"])}</div>'
            f'<div class="t3">இன்று அதிர்ஷ்டம்</div><div class="best">{cells}</div>{warn}</div></div>')
    end = (f'<div class="fc"><div class="en"><img src="{logo}"><div class="n">{G.brand_html(p)}</div>'
           f'<div class="s">தினமும் காலை கிளி ஜோசியம்</div><div class="f">Follow @{E(p["handle"])}</div></div></div>')
    prow = "".join(f'<div class="prow {c}"><div class="k">{k}</div><div class="v"><div class="fit">{E(str(v))}</div>'
                   f'{f"<small>{E(str(s))}</small>" if s else ""}</div></div>' for k, v, s, c in panch_rows(P))
    panch = (f'<div class="fc"><div class="fcin"><div class="kick">{E(day)}</div><div class="ptitle fit">இன்றைய பஞ்சாங்கம்</div>'
             f'<div class="ptable">{prow}</div></div></div>')
    cards = hook + panch + "".join(fortune(p, P, i, r) for i, r in enumerate(rasis)) + end
    small = "".join(f'<div class="sc" style="left:{card_x(i)}px"><b>{GLYPH[i]}&#xFE0E;</b><i></i></div>' for i in range(12))
    band = (f'<div class="band"><img src="{logo}"><div class="bn">{G.brand_html(p)}<small>கிளி ஜோசியம் • இன்றைய ராசிபலன்</small></div>'
            f'</div>')
    js = ("const SEG=" + json.dumps(segs) + ",ENV=" + json.dumps(env) + f",FPS={FPS},HOME={list(HOME)},BIG={list(BIG_C)},"
          f"CX={json.dumps([card_x(i) for i in range(12)])},SY={SMALL_Y},SW={SMALL_W},SH={SMALL_H},PY={PARROT_Y_AT_CARD},"
          f"BIGP=1.3,HOP={HOP_S},PECK={PECK_S},BACK={BACK_S},VAT={VOICE_AT};window.DUR={dur};window.COVER_T=0.5;" + """
const FC=[...document.querySelectorAll('.fc')],SC=[...document.querySelectorAll('.sc')],PR=document.getElementById('parrot'),
 HD=document.getElementById('head'),WG=document.getElementById('wing'),BK=document.getElementById('beak'),LD=document.getElementById('lid');
const cl=u=>Math.max(0,Math.min(1,u)),ez=u=>{u=cl(u);return u<.5?2*u*u:1-Math.pow(-2*u+2,2)/2},lp=(a,b,u)=>a+(b-a)*u;
function fitAll(){document.querySelectorAll('.fit').forEach(e=>{let s=parseFloat(getComputedStyle(e).fontSize);
 while(e.scrollWidth>e.clientWidth+1&&s>16){s-=1;e.style.fontSize=s+'px'}})}
let fitted=0;
window.seek=function(t){
 if(document.fonts.status==='loaded')fitAll();
 let k=SEG.findIndex(s=>t>=s.t0&&t<s.t1);if(k<0)k=SEG.length-1;const s=SEG[k],u=t-s.t0;
 FC.forEach((e,j)=>{let o=0,ry=0;if(j===k){if(s.kind==='rasi'){const q=ez((u-0.95)/0.35);o=q;ry=(1-q)*85}else o=s.kind==='hook'?1:ez(u/0.3)}
  else if(j===k-1){o=s.kind==='rasi'?cl(1-(u-0.85)/0.15):cl(1-u/0.3)}      // the last card stays until the new one opens
  e.style.opacity=o;e.style.transform='perspective(1600px) rotateY('+ry+'deg)'});
 SC.forEach(e=>{e.style.transform='';e.style.opacity=1;e.classList.remove('fly')});
 let px=HOME[0],py=HOME[1],dip=0,flap=0,sz=BIGP,talk=s.kind!=='rasi'||u>VAT;      // owner 28 Nov: the parrot is bigger while it speaks
 if(s.kind==='rasi'){const cx=CX[s.i],tx=cx-196,ty=PY;
  if(u<HOP){const q=ez(u/HOP);sz=lp(BIGP,1,q);px=lp(HOME[0],tx,q);py=lp(HOME[1],ty,q)-140*Math.sin(Math.PI*q);flap=Math.sin(u*38)}
  else if(u<HOP+PECK){sz=1;px=tx;py=ty;dip=Math.sin(Math.PI*(u-HOP)/PECK)}
  else if(u<HOP+PECK+BACK){const q=ez((u-HOP-PECK)/BACK);sz=lp(1,BIGP,q);px=lp(tx,HOME[0],q);py=lp(ty,HOME[1],q)-140*Math.sin(Math.PI*q);flap=Math.sin(u*38)}
  const e=SC[s.i];
  if(u>=0.6){const q=ez((u-0.6)/0.45);e.classList.add('fly');
   e.style.transform='translate('+(BIG[0]-cx-SW/2)*q+'px,'+(BIG[1]-SY-SH/2)*q+'px) scale('+(1+3*q)+') rotate('+(-10*q)+'deg)';
   e.style.opacity=u<1.0?1:cl(1-(u-1.0)/0.18)}
  if(u>1.2){e.style.transform='';e.style.opacity=0.35}}      // back in its place, dimmed (taken)
 const bob=talk?3*Math.sin(t*6.5):0;
 PR.style.transform='translate('+px+'px,'+(py+bob)+'px) scale('+sz+')';
 HD.style.transform='rotate('+(dip*30+(talk?2*Math.sin(t*3.1):0))+'deg)';
 WG.style.transform='rotate('+(-38*Math.abs(flap))+'deg)';
 const f=Math.min(ENV.length-1,Math.max(0,Math.round(t*FPS)));
 BK.style.transform='rotate('+(talk?ENV[f]*26:0)+'deg)';
 LD.style.transform='scaleY('+(((t+0.7)%2.9)<0.13?1:0)+')';
};
window.seek(0);""")
    html = (f'<!doctype html><html><head><meta charset="utf-8"><style>{G.css()}{R.font_zod()}{R.CSS}{CSS}</style></head>'
            f'<body class="reel rp" style="height:{H}px"><div class="scene gold pr"><div class="metal"></div>{band}{cards}'
            f'<div class="table"></div><div class="mat"></div>{CAGE}{small}<div id="parrot">{PARROT}</div></div>'
            f'<script>{js}</script></body></html>')
    return G.themed(html, p, rasi=True)


def make(p, ctx, outdir, log=print, stills=(0.5,)):
    from playwright.sync_api import sync_playwright
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    work = outdir / "voice"
    work.mkdir(exist_ok=True)
    P, rasis = ctx["p"], ctx["rasis"]
    if len(rasis) != 12:
        raise ValueError("parrot reel: 12 rasis needed")
    best, hook, panch, say_r, end = lines(p, P, rasis)
    texts = [hook, panch] + say_r + [end]
    (outdir / "script.txt").write_text("\n".join(texts), encoding="utf-8")
    voices = [say(t, work, n, log) for n, t in enumerate(texts)]
    segs, dur = timeline(voices)
    track = voice_track(voices, segs, dur)
    env = envelope(track)      # the beak follows the voice only, not the sounds below
    ch, fl = chirp(), flip()
    for s in segs:      # owner 28 Nov: a chirp when the parrot picks the card, a paper flip when the card opens
        if s["kind"] == "rasi":
            for snd, at in ((ch, s["t0"] + HOP_S + 0.05), (fl, s["t0"] + 0.95)):
                k = int(at * SR)
                track[k:k + len(snd)] += snd[:max(0, len(track) - k)]
    (outdir / "caption.txt").write_text(caption_text(p, P, best, rasis, segs), encoding="utf-8")
    (outdir / "pinned_comment.txt").write_text(PINNED_COMMENT, encoding="utf-8")
    LAST.clear()
    LAST.update(times=times_block(rasis, segs), comment=PINNED_COMMENT)
    vwav, mwav, awav = outdir / "voice.wav", outdir / "music.wav", outdir / "audio.wav"
    write_wav(vwav, track)
    music = gold_reel.soundtrack(dur, mwav, log)
    if music:
        subprocess.run([_ffmpeg(), "-y", "-loglevel", "error", "-i", str(vwav), "-i", str(music), "-filter_complex",
                        f"[1:a]volume={MUSIC_VOL}[m];[0:a][m]amix=inputs=2:duration=first:normalize=0[a]", "-map", "[a]",
                        "-ar", "44100", str(awav)], check=True)
    else:
        awav = vwav
    html = outdir / "parrot.html"
    html.write_text(page(p, ctx, segs, dur, env, best), encoding="utf-8")
    mp4 = outdir / "rasipalan_parrot.mp4"
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": W, "height": H})
        pg.goto(f"file://{html.resolve()}")
        pg.evaluate("document.fonts.ready.then(() => 1)")
        pg.wait_for_timeout(600)
        for k, s in enumerate(list(stills) + [segs[1]["t0"] + 1.5, segs[2]["t0"] + 0.75, segs[2]["t0"] + 2.2, segs[6]["t0"] + 2.5,
                                              segs[-1]["t0"] + 1.0]):
            pg.evaluate(f"window.seek({s:.3f})")
            pg.screenshot(path=str(outdir / f"still_{k}.png"))
        cmd = [_ffmpeg(), "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-c:v", "mjpeg", "-i", "-",
               "-i", str(awav), "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac",
               "-b:a", "160k", "-ar", "44100", "-shortest", "-movflags", "+faststart", str(mp4)]
        enc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        try:
            for i in range(int(round(dur * FPS))):
                pg.evaluate(f"window.seek({i / FPS:.4f})")
                enc.stdin.write(pg.screenshot(type="jpeg", quality=90))
        finally:
            enc.stdin.close()
            enc.wait()
        b.close()
    if enc.returncode or not mp4.exists():
        raise RuntimeError("ffmpeg could not make the parrot reel")
    log(f"parrot rasipalan reel {mp4.name}: {dur:.1f} s")
    return mp4
