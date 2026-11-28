"""owner 28 Nov (approved after review of the samples): இன்றைய டாப் 5 - every evening one reel with today's 5 most watched news of this
page (Instagram views), 5 -> 1, each on its own reel cover; the Valluvar voice reads the headlines. No view counts are shown.
Posted once a day by .github/workflows/top5.yml (before 22:00 IST); it is not one of the day's 30 news (poster/posted is not touched).
Uses the rasipalan job's page settings and posting steps (rasipalan/rasi_daily.py) - the same upload, Instagram and Facebook way.
  PAGE=<page> python poster/top5.py      (DRY_RUN=1: make the reel only)"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from html import escape as E
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
for d in ("rasipalan", "goldrate", "poster"):
    sys.path.insert(0, str(ROOT / d))
import gold360_render as G      # noqa: E402
import gold_reel      # noqa: E402
import rasi_daily as D      # noqa: E402  (the page settings, upload, Instagram posting)
import rasi_parrot as RP      # noqa: E402  (the voice, the audio mix)

IST = timezone(timedelta(hours=5, minutes=30))
FPS, W, H, SR = 30, 1080, 1920, RP.SR
PAGE = D.PAGE
OUT = ROOT / "out" / "top5" / PAGE
STATE = ROOT / "poster" / "top5_state" / f"{PAGE}.json"
DRY = D.DRY
MAROON, MAROON2, GOLD = G.MAROON, G.MAROON2, G.GOLD
NUM = ["ஐந்து", "நான்கு", "மூன்று", "இரண்டு", "ஒன்று"]
IN_TOWN = {"திருச்சி": "திருச்சியில்", "நாமக்கல்": "நாமக்கல்லில்", "இராசிபுரம்": "இராசிபுரத்தில்", "சேலம்": "சேலத்தில்", "ஈரோடு": "ஈரோட்டில்",
           "கரூர்": "கரூரில்", "திருப்பூர்": "திருப்பூரில்", "கோயம்புத்தூர்": "கோயம்புத்தூரில்", "கோவை": "கோவையில்"}      # "in <town>" in Tamil


def in_town(p):
    return IN_TOWN.get(p["name1"], p["name1"] + " பகுதியில்")


def log(*a):
    print(*a, flush=True)


def ff(*args):
    subprocess.run([gold_reel.ffmpeg(), "-y", "-loglevel", "error", *map(str, args)], check=True)


def todays_posts(token, day):
    """today's news reels of this page: headline, cover, time and Instagram views (read now; the insights file when not readable)"""
    try:
        hist = json.loads((ROOT / "poster" / "insights" / "history.json").read_text(encoding="utf-8"))
    except Exception:
        hist = {}
    out = []
    for f in sorted((ROOT / "poster" / "posted").glob(f"*-{PAGE}-*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            at = datetime.fromisoformat(d["at"]).astimezone(IST)
            if at.date() != day or re.search(r"rasipalan|gold", str(d.get("story")), re.I):
                continue
            pre = json.loads((ROOT / "poster" / "prebuilt" / f"{d['story']}.json").read_text(encoding="utf-8"))
        except Exception:
            continue
        if not pre.get("cover") or not d.get("media_id"):
            continue
        views = int((hist.get(str(d["media_id"])) or {}).get("views") or 0)
        if token:
            try:
                r = D.ig("GET", f"{d['media_id']}/insights", token, metric="views")
                views = int(((r.get("data") or [{}])[0].get("values") or [{}])[0].get("value") or views)
            except Exception:
                pass
        head = re.sub(r"^[^஀-௿A-Za-z0-9]+", "", str(d.get("headline") or "")).strip()
        if head:
            out.append({"story": d["story"], "head": head, "at": at, "cover": pre["cover"], "views": views})
    return out


def page_html(p, items, segs, dur):
    logo = f"file://{Path(p['logo']).resolve()}"
    thumbs = "".join(f'<div class="th"><img src="file://{x["img"]}"><b>{5 - i}</b></div>' for i, x in enumerate(items))
    sc = [f'<div class="s hook"><div class="t1">இன்றைய<br>டாப் 5</div><div class="t2">{E(in_town(p))} இன்று அதிகம் பார்த்த செய்திகள்</div>'
          f'<div class="grid">{thumbs}</div></div>']
    for i, x in enumerate(items):
        rank = 5 - i
        sc.append(f'<div class="s news"><img class="bg" src="file://{x["img"]}"><div class="shade"></div><img class="cv" src="file://{x["img"]}">'
                  f'<div class="rk">#{rank}</div><div class="txt"><div class="hd">{E(x["head"])}</div><div class="vw">இன்று {x["at"]:%I:%M %p}</div></div>'
                  + '<div class="dots">' + "".join(f'<b class="{"on" if r == rank else "done" if r > rank else ""}">{r}</b>' for r in (5, 4, 3, 2, 1))
                  + '</div></div>')
    sc.append(f'<div class="s end"><img src="{logo}"><div class="n">{G.brand_html(p)}</div><div class="sub">தினமும் இரவு இன்றைய டாப் 5</div>'
              f'<div class="f">Follow @{E(p["handle"])}</div></div>')
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
.hook .t2{{margin:20px 40px 0;color:#fff;font-size:48px;font-weight:800}}
.grid{{display:flex;flex-wrap:wrap;justify-content:center;gap:22px;margin:60px 50px 0}}
.th{{position:relative;width:300px;height:400px;border-radius:24px;overflow:hidden;box-shadow:0 14px 30px rgba(0,0,0,.45),0 0 0 5px {GOLD}}}
.th img{{width:100%;height:100%;object-fit:cover}}
.th b{{position:absolute;left:14px;top:10px;background:{GOLD};color:{MAROON};border-radius:50%;width:76px;height:76px;line-height:76px;
 font-family:'Catamaran';font-size:52px;font-weight:900}}
.news .bg{{position:absolute;inset:-60px;width:calc(100% + 120px);height:calc(100% + 120px);object-fit:cover;filter:blur(22px) brightness(.5)}}
.news .cv{{position:absolute;left:50%;top:236px;width:610px;height:1084px;margin-left:-305px;object-fit:cover;border-radius:34px;
 box-shadow:0 26px 60px rgba(0,0,0,.6),0 0 0 7px {GOLD};transform-origin:50% 50%}}
.news .shade{{position:absolute;inset:0;background:linear-gradient(180deg,rgba(0,0,0,0) 55%,rgba(0,0,0,.75) 75%)}}
.news .rk{{position:absolute;left:40px;top:220px;z-index:3;background:{GOLD};color:{MAROON};border-radius:30px;padding:0 34px;font-family:'Catamaran';
 font-size:130px;font-weight:900;line-height:1.25;box-shadow:0 14px 30px rgba(0,0,0,.45)}}
.news .txt{{position:absolute;left:50px;right:50px;top:1360px}}
.news .hd{{color:#fff;font-size:66px;font-weight:900;line-height:1.3;text-shadow:0 4px 12px rgba(0,0,0,.6)}}
.news .vw{{margin-top:18px;display:inline-block;background:rgba(255,255,255,.92);color:{MAROON};border-radius:40px;padding:8px 30px;
 font-size:38px;font-weight:800}}
.dots{{position:absolute;left:0;right:0;bottom:120px;display:flex;justify-content:center;gap:18px}}
.dots b{{width:78px;height:78px;border-radius:50%;line-height:78px;text-align:center;font-family:'Catamaran';font-size:40px;font-weight:900;
 color:rgba(255,255,255,.55);border:3px solid rgba(255,255,255,.35)}} .dots b.on{{background:{GOLD};color:{MAROON};border-color:{GOLD}}}
.dots b.done{{color:rgba(255,255,255,.3);border-color:rgba(255,255,255,.15)}}
.end{{background:radial-gradient(circle at 50% 40%,#FFFBEA,#FCEBB8);text-align:center;padding-top:420px}}
.end img{{width:320px;height:320px;border-radius:50%;box-shadow:0 0 0 10px {GOLD},0 20px 40px rgba(58,7,11,.35)}}
.end .n{{margin-top:40px;color:{MAROON};font-size:100px;font-weight:900}} .end .n i{{font-style:normal;color:{GOLD};font-family:'Catamaran'}}
.end .sub{{color:{MAROON};font-size:48px;font-weight:800}}
.end .f{{display:inline-block;margin-top:46px;background:{MAROON};color:{GOLD};border-radius:50px;padding:16px 50px;font-size:54px;font-weight:900;
 font-family:'Catamaran'}}
"""
    js = ("const SEG=" + json.dumps(segs) + f";window.DUR={dur};window.COVER_T=0.5;" + """
const S=[...document.querySelectorAll('.s')],cl=u=>Math.max(0,Math.min(1,u)),ez=u=>{u=cl(u);return 1-Math.pow(1-u,3)};
window.seek=function(t){
 let k=SEG.findIndex(s=>t>=s.t0&&t<s.t1);if(k<0)k=SEG.length-1;const u=t-SEG[k].t0,d=SEG[k].t1-SEG[k].t0;
 S.forEach((e,j)=>{e.style.opacity=j===k?(k===0?1:ez(u/0.25)):(j===k-1&&u<0.25?1:0);e.style.zIndex=j===k?2:1});
 const e=S[k],cv=e.querySelector('.cv');if(cv)cv.style.transform='scale('+((0.86+0.14*ez(u/0.35))*(1+0.04*u/d))+')';
 const rk=e.querySelector('.rk');if(rk)rk.style.transform='scale('+(0.6+0.4*ez(u/0.3))+')';
 const tx=e.querySelector('.txt');if(tx){tx.style.opacity=ez((u-0.2)/0.3);tx.style.transform='translateY('+(40*(1-ez((u-0.2)/0.3)))+'px)'}
 e.querySelectorAll('.th').forEach((th,i)=>{const q=k===0&&t<0.05?1:ez((u-0.15-i*0.12)/0.3);th.style.opacity=q;th.style.transform='scale('+(0.8+0.2*q)+')'});
};
window.seek(0);""")      # the cover (frame 0) shows all five pictures
    band = (f'<div class="band"><img src="{logo}"><div><b>{G.brand_html(p)}</b><small>இன்றைய டாப் 5 • {datetime.now(IST):%d.%m.%Y}</small>'
            f'</div></div>')
    return G.themed(f'<!doctype html><html><head><meta charset="utf-8"><style>{G.css()}{css}</style></head><body>{band}{"".join(sc)}'
                    f'<script>{js}</script></body></html>', p)


def record(html_path, dur, out_mp4, audio):
    from playwright.sync_api import sync_playwright
    cmd = [gold_reel.ffmpeg(), "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-c:v", "mjpeg", "-i", "-",
           "-i", str(audio), "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
           "-ar", "44100", "-shortest", "-movflags", "+faststart", str(out_mp4)]
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
        b.close()
    if enc.returncode or not Path(out_mp4).exists():
        raise RuntimeError("ffmpeg could not make the top 5 reel")


def say_head(s):
    return re.sub(r"\s*[:–-]\s*", ", ", s)      # a headline read aloud: "X: Y" -> "X, Y"


def caption(p, cfg, top, day):
    lines = [f"🔥 இன்றைய டாப் 5 | {cfg['brand']} | {day:%d.%m.%Y}", "", f"{in_town(p)} இன்று அதிகம் பார்த்த செய்திகள்:"]
    lines += [f"{n}. {x['head']}" for n, x in enumerate(reversed(top), 1)]      # 1 = the most watched
    lines += ["", f"தினமும் இரவு இன்றைய டாப் 5 - முழு செய்திகளுக்கு @{p['handle']} Follow செய்யுங்கள்.", "",
              f"#இன்றையடாப்5 #{cfg['brand'].replace(' ', '')} {cfg['tags'][-1]} #TamilNews"]
    return "\n".join(lines)


def make(p, top, out):
    work = out / "voice"
    work.mkdir(parents=True, exist_ok=True)
    for i, x in enumerate(top):
        r = requests.get(x["cover"], timeout=120)
        r.raise_for_status()
        (work / f"c{i}.jpg").write_bytes(r.content)
        x["img"] = str((work / f"c{i}.jpg").resolve())
    texts = [f"இன்று {in_town(p)} அதிகம் பார்த்த ஐந்து செய்திகள்."]
    texts += [f"{NUM[i]}. {say_head(x['head'])}." for i, x in enumerate(top)]
    texts += [f"முழு செய்திகளுக்கு {p['name1']} த்ரீ சிக்ஸ்டி பக்கத்தை ஃபாலோ பண்ணுங்க."]
    voices = [RP.say(t, work, n, log) for n, t in enumerate(texts)]
    segs, t = [], 0.0
    for n, a in enumerate(voices):
        lead = 0.3 if n else 0.15
        segs.append({"t0": round(t, 2), "v0": round(t + lead, 2), "t1": round(t + max(3.2 if n else 3.0, lead + len(a) / SR + 0.5), 2)})
        t = segs[-1]["t1"]
    dur = t
    vwav, mwav, awav = out / "voice.wav", out / "music.wav", out / "audio.wav"
    RP.write_wav(vwav, RP.voice_track(voices, segs, dur))
    music = gold_reel.soundtrack(dur, mwav, log)
    if music:
        ff("-i", vwav, "-i", music, "-filter_complex", f"[1:a]volume={RP.MUSIC_VOL}[m];[0:a][m]amix=inputs=2:duration=first:normalize=0[a]",
           "-map", "[a]", "-ar", "44100", awav)
    html = out / "top5.html"
    html.write_text(page_html(p, top, segs, dur), encoding="utf-8")
    mp4 = out / "top5.mp4"
    record(html, dur, mp4, awav if music else vwav)
    log(f"top 5 reel {mp4.name}: {dur:.1f} s")
    return mp4


def main():
    cfg = D.PAGES[PAGE]
    day = datetime.now(IST).date()
    try:
        st = json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        st = {}
    if st.get("date") == day.isoformat():
        log("today's top 5 is already posted -", st.get("permalink"))
        return 0
    if not DRY and D.ig_paused_page(PAGE):      # a page paused after a block / limit is not tried (that makes the pause longer)
        log(f"Instagram posting is paused on {PAGE} - no top 5 today")
        return 0
    token = None if DRY else D.bridge_get("token", page=PAGE)["token"]
    posts = todays_posts(token, day)
    top = sorted(posts, key=lambda x: -x["views"])[:5][::-1]      # shown 5 -> 1
    if len(top) < 5:
        log(f"only {len(top)} news posted today - no top 5")
        return 0
    p = D.reel_cfg(cfg, token)
    OUT.mkdir(parents=True, exist_ok=True)
    mp4 = make(p, top, OUT)
    cap = caption(p, cfg, top, day)
    (OUT / "caption.txt").write_text(cap, encoding="utf-8")
    log("caption:\n" + cap)
    if DRY:
        log(f"DRY RUN: {mp4} - not posted")
        return 0
    vurl = D.upload_video(mp4)
    mid, link, _ = D.publish_reel(token, vurl, cap, "")
    log("POSTED top 5", link)
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({"date": day.isoformat(), "media_id": mid, "permalink": link,
                                 "stories": [x["story"] for x in top]}, ensure_ascii=False, indent=1), encoding="utf-8")
    try:      # the same reel on the page's Facebook page
        import facebook
        facebook.share(PAGE, f"top5-{day.isoformat()}", "reel", [vurl], cap, cfg["tags"][-1], tags=cfg["tags"][-2:], always=True)
    except Exception as e:
        log("Facebook step skipped:", str(e)[:150])
    return 0


if __name__ == "__main__":
    sys.exit(main())
