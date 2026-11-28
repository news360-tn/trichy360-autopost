"""owner 28 Nov: two more SAMPLE reels for the owner's review - never posted (no Instagram / Facebook / Sheet code is used).
  map  : a real posted Trichy reel whose first 2.6 s become a district-map zoom to the news town (pin + town name + headline);
         the reel's own voice runs from 0 s, so the spoken hook is not delayed. The original reel is saved next to it.
  top5 : "இன்றைய டாப் 5" - today's 5 most viewed Trichy news (Instagram views), 5 -> 1, each on its own cover picture.
  python tools/samples_extra.py <live repo folder with poster/>      -> out/samples/map, out/samples/top5"""
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from html import escape as E
from pathlib import Path

import numpy as np
import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "rasipalan"))
sys.path.insert(0, str(ROOT / "goldrate"))
import gold360_render as G      # noqa: E402
import gold_reel      # noqa: E402
import rasi_parrot as RP      # noqa: E402  (the voice, the recorder settings)

IST = timezone(timedelta(hours=5, minutes=30))
FPS, W, H, SR = 30, 1080, 1920, RP.SR
PAGE = {"town": "திருச்சி", "name1": "திருச்சி", "logo": ROOT / "kit" / "logo_trichy.png", "handle": "trichy360.official"}
MAROON, MAROON2, GOLD = G.MAROON, G.MAROON2, G.GOLD
INTRO_S = 2.6


def log(*a):
    print(*a, flush=True)


def ff(*args):
    subprocess.run([gold_reel.ffmpeg(), "-y", "-loglevel", "error", *map(str, args)], check=True)


def record(html_path, dur, out_mp4, audio=None):
    """the page drawn frame by frame (window.seek) -> H.264 mp4 (with the audio file when given)"""
    from playwright.sync_api import sync_playwright
    cmd = [gold_reel.ffmpeg(), "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-c:v", "mjpeg", "-i", "-"]
    cmd += (["-i", str(audio)] if audio else []) + ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p"]
    cmd += (["-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-shortest"] if audio else []) + ["-movflags", "+faststart", str(out_mp4)]
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": W, "height": H})
        pg.goto(f"file://{Path(html_path).resolve()}")
        pg.evaluate("document.fonts.ready.then(() => 1)")
        pg.wait_for_timeout(800)
        enc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        try:
            for i in range(int(round(dur * FPS))):
                pg.evaluate(f"window.seek({i / FPS:.4f})")
                enc.stdin.write(pg.screenshot(type="jpeg", quality=90))
        finally:
            enc.stdin.close()
            enc.wait()
        for k, t in enumerate((0.3, dur * 0.35, dur * 0.7)):
            pg.evaluate(f"window.seek({t:.3f})")
            pg.screenshot(path=str(Path(out_mp4).with_name(f"still_{k}.png")))
        b.close()
    if enc.returncode:
        raise RuntimeError(f"ffmpeg failed for {out_mp4}")


def todays_posts(live):
    """this page's posted news (newest first): story, headline, media_id, reel / cover links, views"""
    hist = json.loads((live / "poster" / "insights" / "history.json").read_text(encoding="utf-8"))
    out = []
    for f in sorted((live / "poster" / "posted").glob("*-trichy-*.json"), reverse=True):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            pre = json.loads((live / "poster" / "prebuilt" / f"{d['story']}.json").read_text(encoding="utf-8"))
        except Exception:
            continue
        if not pre.get("reel") or not pre.get("cover") or re.search(r"rasipalan|gold", str(d.get("story")), re.I):
            continue
        at = datetime.fromisoformat(d["at"]).astimezone(IST)
        h = hist.get(str(d.get("media_id"))) or {}
        out.append({"story": d["story"], "head": str(d.get("headline") or "").strip(), "at": at, "reel": pre["reel"], "cover": pre["cover"],
                    "caption": pre.get("caption") or d.get("caption") or "", "views": int(h.get("views") or 0)})
    return out


def get(url, path):
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    Path(path).write_bytes(r.content)
    return path


# ---------------------------------------------------------------- the map-zoom opening

def map_intro_html(m, town, xy, head):
    tx, ty = xy
    path = m["path"]
    js = (f"window.DUR={INTRO_S};const TX={tx},TY={ty};" + """
const P=document.getElementById('d'),L=P.getTotalLength(),CAM=document.getElementById('cam'),PIN=document.getElementById('pin'),
 R1=document.getElementById('r1'),R2=document.getElementById('r2'),LB=document.getElementById('lb'),HD=document.getElementById('hd'),FL=document.getElementById('fl');
P.style.strokeDasharray=L;
const cl=u=>Math.max(0,Math.min(1,u)),ez=u=>{u=cl(u);return 1-Math.pow(1-u,3)};
window.seek=function(t){
 P.style.strokeDashoffset=L*(1-ez(t/0.8));
 P.style.fillOpacity=0.18*ez((t-0.5)/0.4);
 const z=1+2.4*ez((t-0.7)/1.0);                       // the camera zooms to the town
 CAM.setAttribute('transform','translate(130 130) scale('+z+') translate('+(-(130+(TX-130)*ez((t-0.7)/1.0)))+' '+(-(130+(TY-130)*ez((t-0.7)/1.0)))+')');
 const p=ez((t-1.0)/0.35);PIN.style.opacity=p;PIN.setAttribute('transform','translate(0 '+(-30*(1-p))+')');
 [R1,R2].forEach((r,i)=>{const q=((t-1.2-i*0.35)%0.9+0.9)%0.9/0.9;r.setAttribute('r',4+14*q);r.style.opacity=t>1.2+i*0.35?(1-q):0});
 LB.style.opacity=ez((t-1.25)/0.3);LB.style.transform='scale('+(0.7+0.3*ez((t-1.25)/0.3))+')';
 HD.style.opacity=ez((t-0.2)/0.3);
 FL.style.opacity=t>2.35?cl((t-2.35)/0.12)*(1-cl((t-2.47)/0.13)):0;
};
window.seek(0);""")
    css = f"""
body{{margin:0;width:{W}px;height:{H}px;overflow:hidden;background:radial-gradient(circle at 50% 42%,{MAROON2} 0%,{MAROON} 70%);
 font-family:'Noto Sans Tamil',sans-serif}}
#map{{position:absolute;left:40px;top:330px;width:1000px;height:1000px;overflow:visible}}
#d{{fill:{GOLD};stroke:{GOLD};stroke-width:1.6;stroke-linejoin:round;fill-opacity:0}}
#pin circle.dot{{fill:#FF3B30;stroke:#fff;stroke-width:1.6}} .ring{{fill:none;stroke:#FF3B30;stroke-width:1.2}}
#top{{position:absolute;left:0;right:0;top:120px;text-align:center;color:#F6E3A6;font-size:46px;font-weight:800;letter-spacing:2px}}
#lb{{position:absolute;left:0;right:0;top:1080px;text-align:center;transform-origin:50% 50%}}
#lb span{{display:inline-block;background:#fff;color:{MAROON};border-radius:60px;padding:14px 46px;font-size:76px;font-weight:900;
 box-shadow:0 18px 40px rgba(0,0,0,.45),inset 0 0 0 6px {GOLD}}}
#hd{{position:absolute;left:60px;right:60px;bottom:250px;text-align:center;color:#fff;font-size:58px;font-weight:900;line-height:1.3;
 text-shadow:0 4px 14px rgba(0,0,0,.6)}}
#fl{{position:absolute;inset:0;background:#fff;opacity:0}}
"""
    return G.themed(f"""<!doctype html><html><head><meta charset="utf-8"><style>{G.css()}{css}</style></head><body>
<div id="top">{E(m.get('district_ta',''))} மாவட்டம்</div>
<svg id="map" viewBox="0 0 260 260"><g id="cam"><path id="d" d="{path}"/>
<g id="pin" style="opacity:0"><circle id="r1" class="ring" cx="{tx}" cy="{ty}" r="4"/><circle id="r2" class="ring" cx="{tx}" cy="{ty}" r="4"/>
<circle class="dot" cx="{tx}" cy="{ty}" r="4.2"/></g></g></svg>
<div id="lb"><span><svg viewBox="0 0 24 34" width="44" height="62" style="vertical-align:-10px;margin-right:14px"><path d="M12 0C5.4 0 0 5.2 0 11.6 0 20.3 12 34 12 34s12-13.7 12-22.4C24 5.2 18.6 0 12 0z" fill="#FF3B30"/><circle cx="12" cy="11.5" r="4.6" fill="#fff"/></svg>{E(town)}</span></div><div id="hd">{E(head)}</div><div id="fl"></div>
<script>{js}</script></body></html>""", PAGE)


def make_map(live, posts):
    m = json.loads((ROOT / "reel" / "assets" / "district_map.json").read_text(encoding="utf-8"))
    towns = sorted((t for t in m["towns"] if t not in ("திருச்சி", "திருச்சிராப்பள்ளி")), key=len, reverse=True)
    pick = None
    for p in posts:      # the newest reel that names a town of the district (not just "Trichy")
        t = next((t for t in towns if t in p["head"] or t in p["caption"][:300]), "")
        if t:
            pick, town = p, t
            break
    if not pick:
        pick, town = posts[0], "திருச்சி"
    out = ROOT / "out" / "samples" / "map"
    out.mkdir(parents=True, exist_ok=True)
    orig = get(pick["reel"], out / "original_reel.mp4")
    head = re.sub(r"^[^஀-௿A-Za-z0-9]+", "", pick["head"])
    html = out / "map_intro.html"
    html.write_text(map_intro_html(m, town, m["towns"][town], head), encoding="utf-8")
    intro = out / "map_intro.mp4"
    record(html, INTRO_S, intro)
    final = out / "map_zoom_sample.mp4"
    ff("-i", intro, "-i", orig, "-filter_complex",
       f"[0:v]fps={FPS},scale={W}:{H},setsar=1,format=yuv420p[i];[1:v]trim=start={INTRO_S},setpts=PTS-STARTPTS,fps={FPS},scale={W}:{H},setsar=1,format=yuv420p[r];"
       "[i][r]concat=n=2:v=1:a=0[v]", "-map", "[v]", "-map", "1:a", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
       "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", final)
    (out / "about.txt").write_text(f"{pick['story']} • {town}\n{pick['head']}\nreel: {pick['reel']}\n", encoding="utf-8")
    log(f"map sample: {pick['story']} - {town} - {final}")


# ---------------------------------------------------------------- இன்றைய டாப் 5

def k_views(n):
    return f"{n / 1000:.1f}K".replace(".0K", "K") if n >= 1000 else str(n)


def top5_html(items, segs, dur, env):
    logo = f"file://{Path(PAGE['logo']).resolve()}"
    sc = []
    thumbs = "".join(f'<div class="th"><img src="file://{x["img"]}"><b>{5 - i}</b></div>' for i, x in enumerate(items))
    sc.append(f'<div class="s hook"><div class="t1">இன்றைய<br>டாப் 5</div><div class="t2">திருச்சியில் இன்று அதிகம் பார்த்த செய்திகள்</div>'
              f'<div class="grid">{thumbs}</div></div>')
    for i, x in enumerate(items):
        rank = 5 - i
        sc.append(f'<div class="s news"><img class="bg" src="file://{x["img"]}"><div class="shade"></div><img class="cv" src="file://{x["img"]}"><div class="rk">#{rank}</div>'
                  f'<div class="txt"><div class="hd">{E(x["head"])}</div><div class="vw">{k_views(x["views"])} பார்வைகள் • {x["at"]:%I:%M %p}</div></div></div>')
    sc.append(f'<div class="s end"><img src="{logo}"><div class="n">{G.brand_html(PAGE)}</div><div class="sub">தினமும் இரவு இன்றைய டாப் 5</div>'
              f'<div class="f">Follow @{E(PAGE["handle"])}</div></div>')
    css = f"""
body{{margin:0;width:{W}px;height:{H}px;overflow:hidden;background:{MAROON};font-family:'Noto Sans Tamil',sans-serif}}
.band{{position:absolute;left:0;right:0;top:0;height:200px;z-index:9;display:flex;align-items:center;gap:24px;padding:0 44px;
 background:linear-gradient(180deg,{MAROON2},{MAROON})}}
.band img{{width:136px;height:136px;border-radius:50%;background:#fff;box-shadow:0 0 0 6px {GOLD}}}
.band b{{color:#fff;font-size:58px;font-weight:900}} .band b i{{font-style:normal;color:{GOLD};font-family:'Catamaran'}}
.band small{{display:block;color:#F6E3A6;font-size:32px;font-weight:800}}
.s{{position:absolute;inset:0;opacity:0;overflow:hidden}}
.hook{{background:radial-gradient(circle at 50% 30%,{MAROON2},{MAROON} 70%);text-align:center;padding-top:300px}}
.hook .t1{{color:{GOLD};font-size:150px;font-weight:900;line-height:1.1}}
.hook .t2{{margin-top:20px;color:#fff;font-size:48px;font-weight:800}}
.grid{{display:flex;flex-wrap:wrap;justify-content:center;gap:22px;margin:60px 50px 0}}
.th{{position:relative;width:300px;height:400px;border-radius:24px;overflow:hidden;box-shadow:0 14px 30px rgba(0,0,0,.45),0 0 0 5px {GOLD}}}
.th img{{width:100%;height:100%;object-fit:cover}}
.th b{{position:absolute;left:14px;top:10px;background:{GOLD};color:{MAROON};border-radius:50%;width:76px;height:76px;line-height:76px;
 font-family:'Catamaran';font-size:52px;font-weight:900}}
.news .bg{{position:absolute;inset:-60px;width:calc(100% + 120px);height:calc(100% + 120px);object-fit:cover;filter:blur(22px) brightness(.5);transform-origin:50% 40%}}
.news .cv{{position:absolute;left:50%;top:250px;width:560px;height:996px;margin-left:-280px;object-fit:cover;border-radius:34px;box-shadow:0 26px 60px rgba(0,0,0,.6),0 0 0 7px {GOLD};transform-origin:50% 50%}}
.news .shade{{position:absolute;inset:0;background:linear-gradient(180deg,rgba(0,0,0,0) 55%,rgba(0,0,0,.75) 75%)}}
.news .rk{{position:absolute;left:40px;top:220px;z-index:3;background:{GOLD};color:{MAROON};border-radius:30px;padding:0 34px;font-family:'Catamaran';
 font-size:130px;font-weight:900;line-height:1.25;box-shadow:0 14px 30px rgba(0,0,0,.45)}}
.news .txt{{position:absolute;left:50px;right:50px;top:1290px}}
.news .hd{{color:#fff;font-size:66px;font-weight:900;line-height:1.3;text-shadow:0 4px 12px rgba(0,0,0,.6)}}
.news .vw{{margin-top:18px;display:inline-block;background:rgba(255,255,255,.92);color:{MAROON};border-radius:40px;padding:8px 30px;
 font-size:38px;font-weight:800}}
.end{{background:radial-gradient(circle at 50% 40%,#FFFBEA,#FCEBB8);text-align:center;padding-top:420px}}
.end img{{width:320px;height:320px;border-radius:50%;box-shadow:0 0 0 10px {GOLD},0 20px 40px rgba(58,7,11,.35)}}
.end .n{{margin-top:40px;color:{MAROON};font-size:100px;font-weight:900}} .end .n i{{font-style:normal;color:{GOLD};font-family:'Catamaran'}}
.end .sub{{color:{MAROON};font-size:48px;font-weight:800}}
.end .f{{display:inline-block;margin-top:46px;background:{MAROON};color:{GOLD};border-radius:50px;padding:16px 50px;font-size:54px;font-weight:900;
 font-family:'Catamaran'}}
"""
    js = ("const SEG=" + json.dumps(segs) + f";window.DUR={dur};" + """
const S=[...document.querySelectorAll('.s')],cl=u=>Math.max(0,Math.min(1,u)),ez=u=>{u=cl(u);return 1-Math.pow(1-u,3)};
window.seek=function(t){
 let k=SEG.findIndex(s=>t>=s.t0&&t<s.t1);if(k<0)k=SEG.length-1;const u=t-SEG[k].t0,d=SEG[k].t1-SEG[k].t0;
 S.forEach((e,j)=>{e.style.opacity=j===k?(k===0?1:ez(u/0.25)):(j===k-1&&u<0.25?1:0);e.style.zIndex=j===k?2:1});
 const e=S[k],cv=e.querySelector('.cv');if(cv)cv.style.transform='scale('+((0.86+0.14*ez(u/0.35))*(1+0.04*u/d))+')';      // the reel card comes forward, then a slow push in
 const rk=e.querySelector('.rk');if(rk)rk.style.transform='scale('+(0.6+0.4*ez(u/0.3))+')';
 const tx=e.querySelector('.txt');if(tx){tx.style.opacity=ez((u-0.2)/0.3);tx.style.transform='translateY('+(40*(1-ez((u-0.2)/0.3)))+'px)'}
 e.querySelectorAll('.th').forEach((th,i)=>{const q=ez((u-0.15-i*0.12)/0.3);th.style.opacity=q;th.style.transform='scale('+(0.8+0.2*q)+')'});
};
window.seek(0);""")
    band = (f'<div class="band"><img src="{logo}"><div><b>{G.brand_html(PAGE)}</b><small>இன்றைய டாப் 5 • {datetime.now(IST):%d.%m.%Y}</small>'
            f'</div></div>')
    return G.themed(f'<!doctype html><html><head><meta charset="utf-8"><style>{G.css()}{css}</style></head><body>{band}{"".join(sc)}'
                    f'<script>{js}</script></body></html>', PAGE)


def make_top5(live, posts):
    today = datetime.now(IST).date()
    pool = [p for p in posts if p["at"].date() == today and p["views"] > 0]
    if len(pool) < 5:      # early in the day: the last 24 hours
        pool = [p for p in posts if p["at"] > datetime.now(IST) - timedelta(hours=24) and p["views"] > 0]
    top = sorted(pool, key=lambda p: -p["views"])[:5][::-1]      # shown 5 -> 1
    if len(top) < 5:
        raise SystemExit(f"top5: only {len(top)} news with views")
    out = ROOT / "out" / "samples" / "top5"
    work = out / "voice"
    work.mkdir(parents=True, exist_ok=True)
    for i, p in enumerate(top):
        p["img"] = str(get(p["cover"], work / f"c{i}.jpg").resolve())
        p["head"] = re.sub(r"^[^஀-௿A-Za-z0-9]+", "", p["head"])
    say = lambda s: re.sub(r"\s*[:–-]\s*", ", ", s)      # a headline read aloud: "X: Y" -> "X, Y"
    texts = ["இன்று திருச்சியில் அதிகம் பார்த்த ஐந்து செய்திகள்."]
    texts += [f"{['ஐந்து', 'நான்கு', 'மூன்று', 'இரண்டு', 'ஒன்று'][i]}. {say(p['head'])}." for i, p in enumerate(top)]
    texts += ["முழு செய்திகளுக்கு திருச்சி த்ரீ சிக்ஸ்டி பக்கத்தை ஃபாலோ பண்ணுங்க."]
    (out / "script.txt").write_text("\n".join(texts), encoding="utf-8")
    voices = [RP.say(t, work, n, log) for n, t in enumerate(texts)]
    segs, t = [], 0.0
    for n, a in enumerate(voices):
        d = len(a) / SR
        lead = 0.3 if n else 0.15
        segs.append({"t0": round(t, 2), "v0": round(t + lead, 2), "t1": round(t + max(3.2 if n else 3.0, lead + d + 0.5), 2)})
        t = segs[-1]["t1"]
    dur = t
    track = RP.voice_track(voices, segs, dur)
    vwav, mwav, awav = out / "voice.wav", out / "music.wav", out / "audio.wav"
    RP.write_wav(vwav, track)
    music = gold_reel.soundtrack(dur, mwav, log)
    if music:
        ff("-i", vwav, "-i", music, "-filter_complex", f"[1:a]volume={RP.MUSIC_VOL}[m];[0:a][m]amix=inputs=2:duration=first:normalize=0[a]",
           "-map", "[a]", "-ar", "44100", awav)
    html = out / "top5.html"
    html.write_text(top5_html(top, segs, dur, None), encoding="utf-8")
    final = out / "top5_sample.mp4"
    record(html, dur, final, awav if music else vwav)
    log(f"top5 sample: {dur:.1f} s - " + " | ".join(f"{p['story']} {p['views']}" for p in top))


def main():
    live = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT)
    posts = todays_posts(live)
    log(f"{len(posts)} posted news with a reel and a cover")
    which = sys.argv[2:] or ["map", "top5"]
    for w in which:
        try:
            (make_map if w == "map" else make_top5)(live, posts)
        except SystemExit:
            raise
        except Exception as e:
            log(f"{w} sample failed: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
