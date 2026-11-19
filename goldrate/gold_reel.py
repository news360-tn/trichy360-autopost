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
    """the spoken lines; [0..2] go with the gold slide, the rest with the silver slide"""
    pm = r.get("kick") == "மாலை நிலவரம்"
    lines = [("இன்று மாலை தங்கம் விலை மாற்றம்!" if pm else "இன்றைய தங்கம் விலை நிலவரம்!") + f" {r['date'].rsplit(' ', 1)[0]}.",
             f"22 கேரட் தங்கம் ஒரு கிராம் {r['g22']} ரூபாய். " + change_line(r["g22"] - r["g22_prev"], r["vs"]),
             f"24 கேரட் தங்கம் ஒரு கிராம் {r['g24']} ரூபாய்."]
    if r.get("silver"):
        lines.append(f"வெள்ளி ஒரு கிராம் {r['silver']} ரூபாய். " + change_line(r["silver"] - r["silver_prev"], r["vs"]))
    lines.append(f"தினமும் தங்கம், வெள்ளி விலை அறிய {p['town']} த்ரீ சிக்ஸ்டி பக்கத்தை பின்தொடருங்கள்.")
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


def scene_html(p, r, kind, i, n):
    import gold_render as render
    fonts = render.ff("NST", "noto-sans-tamil", [500, 700, 800, 900]) + render.ff("CT", "catamaran", [700, 800, 900])
    silver = kind == "silver"
    acc, acc2 = ("#E9EEF6", "#9FB3CF") if silver else ("#FFD66B", "#F2A93B")
    glow = "rgba(140,170,220,.35)" if silver else "rgba(255,180,60,.32)"
    pm = r.get("kick") == "மாலை நிலவரம்"
    logo = f'<img class="logo" src="file://{Path(p["logo"]).resolve()}">' if p.get("logo") and Path(p["logo"]).exists() else ""
    bars = "".join(f'<i class="{"on" if k <= i else ""}"></i>' for k in range(n))
    head = (f'<div class="bars">{bars}</div><div class="top">{logo}<div class="brand">{p["name1"]}<b>360</b></div>'
            f'<div class="date">{"மாலை • " if pm else ""}{r["date"]}</div></div>')
    if kind == "hook":
        d = r["g22"] - r["g22_prev"]
        word = "குறைந்தது" if d < 0 else "உயர்ந்தது" if d > 0 else "மாற்றமில்லை"
        col = "#3BE08C" if d < 0 else "#FF5D5D" if d > 0 else acc
        arrow = "↓" if d < 0 else "↑" if d > 0 else "→"
        body = f"""<div class="center">
<div class="eyebrow">{"இன்று மாலை" if pm else "இன்றைய"} விலை நிலவரம்</div>
<div class="title">தங்கம்<br><span class="grad">விலை</span></div>
<div class="delta" style="color:{col}"><span class="arr" style="background:{col}22;border-color:{col}66">{arrow}</span>{"₹" + f"{abs(d):,}" if d else ""}</div>
<div class="word" style="color:{col}">{word}</div>
<div class="sub">22K • ஒரு கிராமுக்கு • {r["vs"]}</div></div>"""
    elif kind in ("g22", "g24", "silver"):
        if kind == "silver":
            v, prev, lab, k = r["silver"], r["silver_prev"], "வெள்ளி", "1 கிராம்"
            extra = (f'<div class="row"><div class="mini"><span>1 கிலோ</span><b>₹{inr(v * 1000)}</b></div>'
                     f'<div class="mini"><span>கிலோவுக்கு</span>{chip((v - prev) * 1000)}</div></div>')
            chart = sparkline(r.get("weeksilver") or [], acc)
        else:
            v, prev = r[kind], r[kind + "_prev"]
            lab, k = "தங்கம்", ("22 கேரட்" if kind == "g22" else "24 கேரட்") + " • 1 கிராம்"
            extra = (f'<div class="row"><div class="mini"><span>1 சவரன் (8 கிராம்)</span><b>₹{inr(v * 8)}</b></div>'
                     f'<div class="mini"><span>சவரனுக்கு</span>{chip((v - prev) * 8)}</div></div>')
            chart = sparkline(r.get("week22") or [], acc) if kind == "g22" else ""
        body = f"""<div class="card">
<div class="label"><span class="dot"></span>{lab}<em>{k}</em></div>
<div class="price"><small>₹</small>{inr(v)}</div>
<div class="vs">{r["vs"]} {chip(v - prev)}</div>
{extra}
{f'<div class="chart"><div class="ct">கடந்த 7 நாட்கள்</div>{chart}</div>' if chart else ''}
</div>"""
    else:
        body = f"""<div class="center">
{logo.replace('class="logo"', 'class="biglogo"')}
<div class="eyebrow">தினமும் காலை 9:40 மணிக்கு</div>
<div class="title small">தங்கம், வெள்ளி<br><span class="grad">விலை நிலவரம்</span></div>
<div class="follow">Follow <b>@{p["handle"]}</b></div></div>"""
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{fonts}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{width:{W}px;height:{H}px;overflow:hidden;color:#fff;font-family:NST,CT,sans-serif;
 background:radial-gradient(70% 45% at 85% 8%,{glow},transparent 70%),radial-gradient(60% 40% at 0% 95%,{"rgba(80,110,170,.25)" if silver else "rgba(200,90,30,.22)"},transparent 70%),#0B0B10}}
body:before{{content:"";position:absolute;inset:0;background-image:linear-gradient(rgba(255,255,255,.035) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.035) 1px,transparent 1px);background-size:60px 60px;mask:linear-gradient(#000,transparent 75%)}}
.bars{{position:absolute;top:70px;left:60px;right:60px;display:flex;gap:10px}}
.bars i{{flex:1;height:7px;border-radius:7px;background:rgba(255,255,255,.18)}} .bars i.on{{background:linear-gradient(90deg,{acc},{acc2})}}
.top{{position:absolute;top:110px;left:60px;right:60px;display:flex;align-items:center;gap:18px}}
.logo{{width:84px;height:84px;border-radius:50%;object-fit:cover;border:3px solid rgba(255,255,255,.25)}}
.brand{{font:900 46px CT,NST;letter-spacing:.5px}} .brand b{{color:{acc};margin-left:4px}}
.date{{margin-left:auto;font:700 30px NST,CT;padding:12px 24px;border-radius:40px;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.16)}}
.center{{position:absolute;top:260px;bottom:360px;left:70px;right:70px;display:flex;flex-direction:column;justify-content:center;align-items:flex-start}}
.eyebrow{{font:800 40px NST;color:{acc};letter-spacing:1px;text-transform:uppercase}}
.title{{margin-top:14px;font:900 168px/1.02 NST,CT;letter-spacing:-2px}} .title.small{{font-size:96px;letter-spacing:-1px}}
.grad{{background:linear-gradient(100deg,{acc} 10%,{acc2} 90%);-webkit-background-clip:text;color:transparent}}
.delta{{margin-top:44px;font:900 190px/1 CT,NST;display:flex;align-items:center;gap:30px;letter-spacing:-4px}}
.arr{{width:150px;height:150px;border-radius:40px;border:3px solid;display:flex;align-items:center;justify-content:center;font-size:110px;letter-spacing:0}}
.word{{margin-top:10px;font:900 84px NST}}
.sub{{margin-top:26px;white-space:nowrap;font:700 34px NST;color:rgba(255,255,255,.7)}}
.card{{position:absolute;top:calc(50% - 30px);transform:translateY(-50%);left:50px;right:50px;padding:56px 56px 44px;border-radius:48px;background:linear-gradient(160deg,rgba(255,255,255,.10),rgba(255,255,255,.03));
 border:1.5px solid rgba(255,255,255,.16);box-shadow:0 40px 90px rgba(0,0,0,.45),inset 0 1px 0 rgba(255,255,255,.18)}}
.label{{display:flex;align-items:center;gap:18px;font:900 64px NST}} .label em{{font:700 36px NST;font-style:normal;color:rgba(255,255,255,.65);margin-left:6px}}
.dot{{width:26px;height:26px;border-radius:50%;background:linear-gradient(135deg,{acc},{acc2});box-shadow:0 0 30px {acc}}}
.price{{margin-top:22px;font:900 210px/1 CT;letter-spacing:-6px;background:linear-gradient(180deg,#fff 30%,{acc} 120%);-webkit-background-clip:text;color:transparent}}
.price small{{font-size:120px;margin-right:10px;vertical-align:28px}}
.vs{{margin-top:22px;white-space:nowrap;display:flex;align-items:center;gap:18px;font:700 34px NST;color:rgba(255,255,255,.7)}}
.chip{{font:800 36px NST,CT;padding:10px 24px;border-radius:40px;color:#fff;white-space:nowrap}}
.chip.down{{background:rgba(40,200,120,.18);color:#4CF0A0;border:1.5px solid rgba(76,240,160,.45)}}
.chip.up{{background:rgba(255,80,80,.16);color:#FF7A7A;border:1.5px solid rgba(255,122,122,.45)}}
.chip.same{{background:rgba(255,255,255,.08);border:1.5px solid rgba(255,255,255,.25)}}
.row{{margin-top:40px;display:flex;gap:22px}}
.mini{{flex:1;padding:26px 30px;border-radius:30px;background:rgba(0,0,0,.28);border:1px solid rgba(255,255,255,.10);display:flex;flex-direction:column;gap:12px;align-items:flex-start}}
.mini span{{white-space:nowrap;font:700 28px NST;color:rgba(255,255,255,.62)}} .mini b{{font:900 62px CT}}
.chart{{margin-top:34px}} .ct{{font:700 30px NST;color:rgba(255,255,255,.6);margin-bottom:6px}}
.biglogo{{width:220px;height:220px;border-radius:50%;object-fit:cover;border:5px solid {acc};box-shadow:0 0 80px {glow};margin-bottom:46px}}
.follow{{margin-top:56px;font:800 54px CT,NST;padding:26px 48px;border-radius:70px;color:#111;background:linear-gradient(100deg,{acc},{acc2})}}
.follow b{{font-weight:900}}
</style></head><body>{head}{body}</body></html>"""


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
            rr = subprocess.run([sys.executable, "-m", "edge_tts", "--voice", "ta-IN-ValluvarNeural", "--rate=+6%", "--text", say,
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
    GAP, LEAD, TAIL, T = 0.35, 0.4, 1.2, 0.35
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
        fc.append(f"[{i}:v]scale=1188:2112,zoompan=z='min(1+0.0007*on,1.06)':{moves[i % 3]}:d={n}:s={W}x{H}:fps={FPS},format=yuv420p,setsar=1[s{i}]")
    prev, off = "s0", 0.0
    trans = ["slideup", "smoothleft", "smoothleft", "smoothleft", "fade"]
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
