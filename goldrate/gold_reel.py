"""owner 19 Nov: the daily gold & silver rate also as a REEL (carousels reach few people). Made from the same 2 slides as the carousel:
a 9:16 frame per slide (hook line on top, the slide, Follow line at the bottom), slow zoom, Tamil voice (Valluvar) reading today's
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


def frame_html(p, r, kind, slide):
    import gold_render as render
    big, small, d = hook(r, kind)
    col = "#2ECC71" if d < 0 else "#FF5A5A" if d > 0 else "#F2C14E"
    arrow = "▼" if d < 0 else "▲" if d > 0 else "●"
    bg = ("radial-gradient(90% 60% at 80% 15%,#3A1408 0%,#140808 45%,#07070B 100%)" if kind == "gold"
          else "radial-gradient(90% 60% at 80% 15%,#16325E 0%,#0A1428 50%,#050A16 100%)")
    fonts = render.ff("NST", "noto-sans-tamil", [700, 800, 900]) + render.ff("CT", "catamaran", [800, 900])
    when = "இன்று மாலை" if r.get("kick") == "மாலை நிலவரம்" else "இன்று"
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{fonts}
*{{margin:0;padding:0;box-sizing:border-box}} body{{width:{W}px;height:{H}px;background:{bg};font-family:CT,NST,sans-serif;color:#fff;overflow:hidden}}
.top{{position:absolute;top:150px;left:0;right:0;text-align:center}}
.when{{display:inline-block;font:800 40px CT,NST;letter-spacing:1px;color:#111;background:#FFD23F;padding:8px 30px;border-radius:40px}}
.big{{margin-top:22px;font:900 70px/1.1 CT,NST;color:{col};text-shadow:0 6px 24px rgba(0,0,0,.6)}}
.big b{{font-size:64px;margin-right:12px}}
.small{{margin-top:6px;font:700 36px NST;color:#E8E8E8}}
.slide{{position:absolute;top:490px;left:40px;width:1000px;height:1250px;border-radius:28px;overflow:hidden;
 box-shadow:0 20px 60px rgba(0,0,0,.65);border:3px solid rgba(255,210,63,.55)}}
.slide img{{width:100%;height:100%;object-fit:cover}}
</style></head><body>
<div class="top"><div class="when">{when} • {r['date']}</div>
<div class="big"><b>{arrow}</b>{big}</div><div class="small">{small} • @{p['handle']}</div></div>
<div class="slide"><img src="file://{Path(slide).resolve()}"></div>
</body></html>"""


def frames(p, r, jpgs, outdir, log):
    from playwright.sync_api import sync_playwright
    out = []
    kinds = ["gold", "silver"][:len(jpgs)]
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": W, "height": H})
        for kind, j in zip(kinds, jpgs):
            h = outdir / f"reel_{kind}.html"
            h.write_text(frame_html(p, r, kind, j), encoding="utf-8")
            pg.goto(f"file://{h.resolve()}")
            pg.wait_for_timeout(900)
            png = outdir / f"reel_{kind}.png"
            pg.screenshot(path=str(png))
            out.append(png)
            log("reel frame", png.name)
        b.close()
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
    outdir = Path(outdir)
    work = outdir / "reel_work"
    work.mkdir(parents=True, exist_ok=True)
    ff = ffmpeg()
    lines = script(p, r)
    pngs = frames(p, r, jpgs, outdir, log)
    vs = voice(lines, work, log)
    GAP = 0.35
    # voice track: lines with short gaps, 0.4 s lead-in
    lst = work / "voice.txt"
    sil = work / "gap.wav"
    subprocess.run([ff, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", str(GAP), str(sil)], check=True)
    lead = work / "lead.wav"
    subprocess.run([ff, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", "0.4", str(lead)], check=True)
    parts = [lead]
    for i, (w, _) in enumerate(vs):
        parts.append(w)
        if i < len(vs) - 1:
            parts.append(sil)
    lst.write_text("".join(f"file '{x.resolve()}'\n" for x in parts))
    vo = work / "voice.wav"
    subprocess.run([ff, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(vo)], check=True)
    total = dur(vo) + 1.0
    # gold frame while lines 0-2 are read, silver frame for the rest
    n_gold = 3 if len(pngs) > 1 else len(vs)
    t_gold = 0.4 + sum(s for _, s in vs[:n_gold]) + GAP * n_gold - GAP / 2
    t_gold = min(t_gold, total) if len(pngs) > 1 else total
    t_silver = max(1.0, total - t_gold)
    music = work / "music.wav"
    try:
        sys.path.insert(0, str(ROOT / "reel"))
        import music as M
        M.main(str(music), total + 0.5, seed=7)
    except Exception as e:
        log("music skipped:", str(e)[:120])
        music = None
    mp4 = outdir / "gold_reel.mp4"
    inputs, fc = [], []
    durs = [t_gold] + ([t_silver] if len(pngs) > 1 else [])
    for i, (png, t) in enumerate(zip(pngs, durs)):
        n = int(round((t + (0.5 if i < len(pngs) - 1 else 0)) * FPS))
        inputs += ["-i", str(png)]
        fc.append(f"[{i}:v]scale=1188:2112,zoompan=z='min(1+0.0006*on,1.08)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={n}:s={W}x{H}:fps={FPS},"
                  f"format=yuv420p,setsar=1[v{i}]")
    if len(pngs) > 1:
        fc.append(f"[v0][v1]xfade=transition=fade:duration=0.5:offset={t_gold:.3f}[v]")
    else:
        fc.append("[v0]copy[v]")
    a = len(pngs)
    inputs += ["-i", str(vo)]
    if music:
        inputs += ["-i", str(music)]
        fc.append(f"[{a + 1}:a]volume=0.16[m];[{a}:a]apad[vv];[vv][m]amix=inputs=2:duration=longest:normalize=0,atrim=0:{total:.3f}[a]")
    else:
        fc.append(f"[{a}:a]apad,atrim=0:{total:.3f}[a]")
    subprocess.run([ff, "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[a]",
                    "-t", f"{total:.3f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS),
                    "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-movflags", "+faststart", str(mp4)], check=True)
    log(f"reel {mp4.name}: {total:.1f} s")
    (outdir / "reel_script.json").write_text(json.dumps(lines, ensure_ascii=False, indent=1), encoding="utf-8")
    return mp4, lines
