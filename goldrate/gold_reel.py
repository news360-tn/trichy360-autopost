"""owner 19 Nov: the daily gold & silver rate also as a REEL (carousels reach few people). Made from the same 2 slides as the carousel:
owner 19 Nov 'modern theme': full-screen scenes (hook, 22K, 24K, silver, follow), one per spoken line, slide transitions, Tamil voice (Valluvar) reading today's
rate and the change, soft music. Posted AFTER the carousel, separately: a reel problem never touches the carousel or the news posts.
make(page, rates, slide_jpgs, outdir, log) -> (mp4 path, spoken script)"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FPS = 30
W, H = 1080, 1920


def ffmpeg():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def change_line(d, vs, what="கிராமுக்கு"):
    if d < 0:
        return f"{vs} {what} {abs(d)} ரூபாய் குறைந்துள்ளது."
    if d > 0:
        return f"{vs} {what} {d} ரூபாய் உயர்ந்துள்ளது."
    return f"{vs} மாற்றம் இல்லை."


def script(p, r):
    """owner 19 Nov 'very slow': short punchy lines, one per scene (hook, 22K, 24K, [silver], follow)"""
    pm = r.get("kick") == "மாலை நிலவரம்"
    d = r["g22"] - r["g22_prev"]
    when = "இன்று மாலை" if pm else "இன்று"
    if d:
        first = f"{when} தங்கம் விலை கிராமுக்கு {abs(d)} ரூபாய் {'குறைந்தது' if d < 0 else 'உயர்ந்தது'}!"
    else:
        first = f"{when} தங்கம் விலையில் மாற்றம் இல்லை!"
    lines = [first, f"22 கேரட் ஒரு கிராம் {r['g22']} ரூபாய்.", f"24 கேரட் ஒரு கிராம் {r['g24']} ரூபாய்."]
    if r.get("silver"):
        ds = r["silver"] - r["silver_prev"]
        lines.append(f"வெள்ளி ஒரு கிராம் {r['silver']} ரூபாய்." + (f" {abs(ds)} ரூபாய் {'குறைவு' if ds < 0 else 'உயர்வு'}." if ds else ""))
    lines.append(f"தினமும் விலை அறிய {p['town']} த்ரீ சிக்ஸ்டி பின்தொடருங்கள்!")
    return lines


def hook(r, kind):
    """the short line on top of the frame"""
    if kind == "gold":
        d = r["g22"] - r["g22_prev"]
        word = "குறைவு" if d < 0 else "உயர்வு" if d > 0 else ""
        return ("தங்கம் விலை " + (f"₹{abs(d)} {word}" if d else "மாற்றமில்லை"), "22K ஒரு கிராம்", d)
    d = r["silver"] - r["silver_prev"]
    word = "குறைவு" if d < 0 else "உயர்வு" if d > 0 else ""
    return ("வெள்ளி விலை " + (f"₹{abs(d)} {word}" if d else "மாற்றமில்லை"), "ஒரு கிராம்", d)


def sparkline(points, color, w=860, h=200):
    """the week as a smooth line with a soft fill and a glowing last point"""
    vals = [v for _, v in points] if points and isinstance(points[0], (list, tuple)) else list(points or [])
    if len(vals) < 2:
        return ""
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1
    xs = [20 + i * (w - 40) / (len(vals) - 1) for i in range(len(vals))]
    ys = [h - 30 - (v - lo) / span * (h - 70) for v in vals]
    line = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}" for i, (x, y) in enumerate(zip(xs, ys)))
    area = line + f" L{xs[-1]:.1f},{h} L{xs[0]:.1f},{h} Z"
    dots = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="6" fill="rgba(255,255,255,.55)"/>' for x, y in zip(xs[:-1], ys[:-1]))
    return (f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}"><defs><linearGradient id="f" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="{color}" stop-opacity=".45"/><stop offset="1" stop-color="{color}" stop-opacity="0"/></linearGradient></defs>'
            f'<path d="{area}" fill="url(#f)"/><path d="{line}" fill="none" stroke="{color}" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>'
            f'{dots}<circle cx="{xs[-1]:.1f}" cy="{ys[-1]:.1f}" r="22" fill="{color}" opacity=".25"/><circle cx="{xs[-1]:.1f}" cy="{ys[-1]:.1f}" r="11" fill="{color}"/></svg>')


def chip(d, unit=""):
    if d < 0:
        return f'<span class="chip down">▼ ₹{abs(d):,}{unit} குறைவு</span>'
    if d > 0:
        return f'<span class="chip up">▲ ₹{d:,}{unit} உயர்வு</span>'
    return '<span class="chip same">● மாற்றமில்லை</span>'


def inr(n):
    import gold_render as render
    return render.inr(n)


def scene_list(r):
    """one scene per spoken line (script order)"""
    out = ["hook", "g22", "g24"]
    if r.get("silver"):
        out.append("silver")
    return out + ["outro"]


def badge(d, unit="கிராமுக்கு"):
    if d < 0:
        return f'<div class="badge down">▼ ₹{abs(d):,} <small>{unit} குறைவு</small></div>'
    if d > 0:
        return f'<div class="badge up">▲ ₹{d:,} <small>{unit} உயர்வு</small></div>'
    return '<div class="badge same">● மாற்றமில்லை</div>'


def scene_html(p, r, kind, i, n):
    """owner 19 Nov 'use other design': bright news-poster look - solid gold / silver colour, huge black numbers, black tags, diagonal band"""
    import gold_render as render
    fonts = render.ff("NST", "noto-sans-tamil", [700, 800, 900]) + render.ff("CT", "catamaran", [800, 900])
    silver = kind == "silver"
    pm = r.get("kick") == "மாலை நிலவரம்"
    bg = ("linear-gradient(160deg,#F4F7FB 0%,#D9E1EC 55%,#B9C6D8 100%)" if silver
          else "#111" if kind in ("hook", "outro") else "linear-gradient(160deg,#FFE27A 0%,#FFC93C 45%,#F5A623 100%)")
    ink = "#fff" if kind in ("hook", "outro") else "#111"
    logo = f'<img class="logo" src="file://{Path(p["logo"]).resolve()}">' if p.get("logo") and Path(p["logo"]).exists() else ""
    top = (f'<div class="top">{logo}<div class="brand">@{p["handle"]}</div>'
           f'<div class="date">{"மாலை • " if pm else ""}{r["date"]}</div></div><div class="step">{i + 1}/{n}</div>')
    if kind == "hook":
        d = r["g22"] - r["g22_prev"]
        col = "#2EE58A" if d < 0 else "#FF4D4D" if d > 0 else "#FFC93C"
        word = "குறைந்தது" if d < 0 else "உயர்ந்தது" if d > 0 else "மாற்றமில்லை"
        body = f"""<div class="band"><span>{"இன்று மாலை" if pm else "இன்று"} • தங்கம் விலை • {"இன்று மாலை" if pm else "இன்று"} • தங்கம் விலை •</span></div>
<div class="hk"><div class="hk1">தங்கம்<br>விலை</div>
<div class="hk2" style="color:{col}">{"▼" if d < 0 else "▲" if d > 0 else "●"} {"₹" + f"{abs(d):,}" if d else ""}</div>
<div class="hk3" style="background:{col}">{word}</div><div class="hk4">22K • ஒரு கிராமுக்கு</div></div>"""
    elif kind in ("g22", "g24", "silver"):
        if silver:
            v, prev, tag, big2, lab2 = r["silver"], r["silver_prev"], "வெள்ளி • 1 கிராம்", r["silver"] * 1000, "1 கிலோ"
        else:
            v, prev = r[kind], r[kind + "_prev"]
            tag, big2, lab2 = ("22K" if kind == "g22" else "24K") + " தங்கம் • 1 கிராம்", v * 8, "1 சவரன்"
        body = f"""<div class="tag">{tag}</div>
<div class="num"><small>₹</small>{inr(v)}</div>
{badge(v - prev)}
<div class="strip"><span>{lab2}</span><b>₹{inr(big2)}</b></div>
<div class="kar">{"Ag" if silver else ("22" if kind == "g22" else "24")}</div>"""
    else:
        body = f"""<div class="out">{logo.replace('class="logo"', 'class="big"')}
<div class="o1">தினமும்<br><span>தங்கம் • வெள்ளி</span><br>விலை</div>
<div class="o2">FOLLOW</div><div class="o3">@{p["handle"]}</div></div>"""
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{fonts}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{width:{W}px;height:{H}px;overflow:hidden;background:{bg};color:{ink};font-family:NST,CT,sans-serif;position:relative}}
.top{{position:absolute;top:90px;left:60px;right:60px;display:flex;align-items:center;gap:18px}}
.logo{{width:90px;height:90px;border-radius:50%;object-fit:cover;border:4px solid {ink}}}
.brand{{font:900 38px CT,NST}}
.date{{margin-left:auto;font:800 30px NST,CT;padding:12px 26px;border-radius:12px;background:{ink};color:{"#111" if ink == "#fff" else "#FFC93C" if not silver else "#E9EEF6"}}}
.step{{position:absolute;top:210px;right:60px;font:900 34px CT;opacity:.5}}
.band{{position:absolute;top:330px;left:-80px;right:-80px;transform:rotate(-6deg);background:#FFC93C;color:#111;padding:20px 0;white-space:nowrap;overflow:hidden;font:900 54px NST}}
.hk{{position:absolute;top:600px;left:70px;right:70px}}
.hk1{{font:900 190px/1.0 NST;letter-spacing:-3px}}
.hk2{{margin-top:40px;font:900 230px/1 CT;letter-spacing:-6px}}
.hk3{{display:inline-block;margin-top:24px;font:900 76px NST;color:#111;padding:8px 40px;border-radius:16px}}
.hk4{{margin-top:30px;font:800 40px NST;opacity:.7}}
.tag{{position:absolute;top:440px;left:60px;font:900 52px NST;background:#111;color:{"#E9EEF6" if silver else "#FFC93C"};padding:16px 34px;border-radius:14px}}
.num{{position:absolute;top:580px;left:50px;right:40px;font:900 300px/1 CT;letter-spacing:-12px}}
.num small{{font-size:150px;letter-spacing:0;margin-right:6px;vertical-align:70px}}
.badge{{position:absolute;top:950px;left:60px;font:900 70px CT,NST;padding:14px 36px;border-radius:18px;color:#fff}}
.badge small{{font:800 40px NST}}
.badge.down{{background:#0E9F5B}} .badge.up{{background:#D92D2D}} .badge.same{{background:#111;font-size:56px}}
.strip{{position:absolute;top:1170px;left:60px;right:60px;background:#111;color:#fff;border-radius:26px;padding:34px 44px;display:flex;align-items:center;justify-content:space-between}}
.strip span{{font:800 48px NST;color:{"#E9EEF6" if silver else "#FFC93C"}}} .strip b{{font:900 92px CT;letter-spacing:-2px}}
.kar{{position:absolute;right:-40px;bottom:250px;font:900 520px/1 CT;letter-spacing:-30px;color:rgba(0,0,0,.08)}}
.out{{position:absolute;top:330px;left:70px;right:70px;text-align:center}}
.big{{width:260px;height:260px;border-radius:50%;object-fit:cover;border:8px solid #FFC93C}}
.o1{{margin-top:50px;font:900 112px/1.08 NST}} .o1 span{{color:#FFC93C}}
.o2{{display:inline-block;margin-top:60px;font:900 110px CT;letter-spacing:6px;background:#FFC93C;color:#111;padding:10px 60px;border-radius:20px}}
.o3{{margin-top:26px;font:900 64px CT}}
</style></head><body>{top}{body}</body></html>"""


def scenes(p, r, outdir, log):
    from playwright.sync_api import sync_playwright
    kinds, out = scene_list(r), []
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": W, "height": H})
        for i, kind in enumerate(kinds):
            h = outdir / f"reel_{i}_{kind}.html"
            h.write_text(scene_html(p, r, kind, i, len(kinds)), encoding="utf-8")
            pg.goto(f"file://{h.resolve()}")
            pg.wait_for_timeout(700)
            png = outdir / f"reel_{i}_{kind}.png"
            pg.screenshot(path=str(png))
            out.append(png)
        b.close()
    log(f"reel scenes: {', '.join(kinds)}")
    return out


def voice(lines, work, log):
    """each line -> wav (Valluvar, the news reels' voice; numbers said in Tamil words); returns [(wav, seconds)]"""
    sys.path.insert(0, str(ROOT / "reel"))
    import tts
    ff, out = ffmpeg(), []
    for i, t in enumerate(lines):
        mp3, wav = work / f"v{i}.mp3", work / f"v{i}.wav"
        say = tts.clean(t)
        for k in range(4):      # the free voice service fails now and then
            rr = subprocess.run([sys.executable, "-m", "edge_tts", "--voice", "ta-IN-ValluvarNeural", "--rate=+18%", "--text", say,
                                 "--write-media", str(mp3)], capture_output=True, timeout=90)
            if rr.returncode == 0 and mp3.exists() and mp3.stat().st_size > 1000:
                break
            time.sleep(5 * (k + 1))
        else:
            raise RuntimeError(f"voice failed for line {i}")
        subprocess.run([ff, "-y", "-loglevel", "error", "-i", str(mp3), "-af",
                        "silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse,loudnorm=I=-16:TP=-1.5",
                        "-ar", "44100", "-ac", "1", str(wav)], check=True)
        out.append((wav, dur(wav)))
        log(f"voice line {i}: {out[-1][1]:.1f} s")
    return out


def dur(path):
    import wave
    with wave.open(str(path)) as w:
        return w.getnframes() / w.getframerate()


def make(p, r, jpgs, outdir, log=print):
    """owner 19 Nov 'use modern theme': full-screen scenes (hook, 22K, 24K, silver, follow) that change with each spoken line.
    jpgs (the carousel slides) are no longer needed here - kept in the call for compatibility."""
    outdir = Path(outdir)
    work = outdir / "reel_work"
    work.mkdir(parents=True, exist_ok=True)
    ff = ffmpeg()
    lines = script(p, r)
    pngs = scenes(p, r, outdir, log)
    assert len(pngs) == len(lines), (len(pngs), len(lines))
    vs = voice(lines, work, log)
    GAP, LEAD, TAIL, T = 0.12, 0.15, 0.7, 0.22
    sil, lead = work / "gap.wav", work / "lead.wav"
    for f, t in ((sil, GAP), (lead, LEAD)):
        subprocess.run([ff, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", str(t), str(f)], check=True)
    parts = [lead]
    for i, (w, _) in enumerate(vs):
        parts += [w] + ([sil] if i < len(vs) - 1 else [])
    lst = work / "voice.txt"
    lst.write_text("".join(f"file '{x.resolve()}'\n" for x in parts))
    vo = work / "voice.wav"
    subprocess.run([ff, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(vo)], check=True)
    durs = [s + GAP for _, s in vs]
    durs[0] += LEAD
    durs[-1] += TAIL - GAP
    total = sum(durs)
    music = work / "music.wav"
    try:
        sys.path.insert(0, str(ROOT / "reel"))
        import music as M
        M.main(str(music), total + 0.5, seed=7)
    except Exception as e:
        log("music skipped:", str(e)[:120])
        music = None
    inputs, fc = [], []
    moves = ["x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'", "x='0':y='ih/2-(ih/zoom/2)'", "x='iw-iw/zoom':y='ih/2-(ih/zoom/2)'"]
    for i, (png, d) in enumerate(zip(pngs, durs)):
        n = int(round((d + (T if i < len(pngs) - 1 else 0)) * FPS))
        inputs += ["-i", str(png)]
        fc.append(f"[{i}:v]scale=1188:2112,zoompan=z='max(1.0,1.10-0.006*on)':{moves[0]}:d={n}:s={W}x{H}:fps={FPS},format=yuv420p,setsar=1[s{i}]")
    prev, off = "s0", 0.0
    trans = ["slideleft", "slideup", "slideleft", "slideup", "fade"]
    for i in range(1, len(pngs)):
        off += durs[i - 1]
        fc.append(f"[{prev}][s{i}]xfade=transition={trans[min(i, len(trans) - 1)] if i < len(pngs) - 1 else 'fade'}:duration={T}:offset={off:.3f}[x{i}]")
        prev = f"x{i}"
    fc.append(f"[{prev}]copy[v]")
    a = len(pngs)
    inputs += ["-i", str(vo)]
    if music:
        inputs += ["-i", str(music)]
        fc.append(f"[{a + 1}:a]volume=0.16[m];[{a}:a]apad[vv];[vv][m]amix=inputs=2:duration=longest:normalize=0,atrim=0:{total:.3f}[a]")
    else:
        fc.append(f"[{a}:a]apad,atrim=0:{total:.3f}[a]")
    mp4 = outdir / "gold_reel.mp4"
    subprocess.run([ff, "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[a]",
                    "-t", f"{total:.3f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS),
                    "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-movflags", "+faststart", str(mp4)], check=True)
    log(f"reel {mp4.name}: {total:.1f} s")
    (outdir / "reel_script.json").write_text(json.dumps(lines, ensure_ascii=False, indent=1), encoding="utf-8")
    return mp4, lines
