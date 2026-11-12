"""கோயம்புத்தூர் 360 — cinematic 9:16 Tamil news reel builder.
Usage: python3 reel.py spec.json out.mp4 [page]   (page = coimbatore, the only page)
Env VOICE_FILE=<audio>: use a real recorded voice for the whole reel instead of the voice model.
spec: {"date": "...", "category": "...", "location": "...", "voice": "male|female",
       "scenes": [{"say": "<Tamil narration, numbers in words>", "type": "...", ...}, ...]}
Scene types: title(kicker,line1,line2,stamp,icon) | big(number,unit,icon,sub) |
             card(num,icon,title,lines[],pill) | advice(icon,title,text) | outro
Needs: tts.py (Tamil voice), Playwright Chromium, ffmpeg, node_modules fonts/icons (kit).
"""
import json, sys, os, re, subprocess, html, wave, math
from pathlib import Path
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
KIT = Path(os.environ.get("KIT", HERE.parent / "kit"))
NM = KIT / "node_modules"
FS = NM / "@fontsource"
ICONS = NM / "@fortawesome" / "fontawesome-free" / "svgs" / "solid"
# Coimbatore 360: ONE page (no second page). Page name / handle / logo in this one place.
PAGES = {
    "coimbatore": {"logo": "logo_coimbatore.png", "name": "கோயம்புத்தூர் 360", "handle": "coimbatore360_official", "tagline": "நம்ம கோவை செய்திகள்", "follow": "கோவை மாவட்டச்<br>செய்திகளுக்கு",
                   "ticker": "கோயம்புத்தூர் 360  •  கோவை மாவட்டச் செய்திகள்  •  Follow செய்யுங்கள்", "footer": "footer_coimbatore.png", "hashtag": "#Coimbatore360"},
    "trichy": {"logo": "logo_trichy.png", "style": "T", "name": "திருச்சி 360", "handle": "trichy360.official", "tagline": "நம்ம திருச்சி செய்திகள்", "follow": "திருச்சி மாவட்டச்<br>செய்திகளுக்கு",
                   "ticker": "திருச்சி 360  •  திருச்சி மாவட்டச் செய்திகள்  •  Follow செய்யுங்கள்", "footer": "footer_trichy.png", "hashtag": "#Coimbatore360"},
}
PAGE = PAGES["coimbatore"]
LOGO = KIT / PAGE["logo"]
W, H, FPS = 1080, 1920, 30

def ff(family, pkg, weights):
    out = []
    for w in weights:
        for sub, rng in (("tamil", ""), ("latin", "unicode-range:U+0000-00FF,U+2022,U+2013,U+2014;")):
            f = FS / pkg / "files" / f"{pkg}-{sub}-{w}-normal.woff2"
            if f.exists():
                out.append(f"@font-face{{font-family:'{family}';font-weight:{w};src:url('file://{f}') format('woff2');{rng}}}")
    return "\n".join(out)

def icon(name):
    p = ICONS / f"{name}.svg"
    if not p.exists():
        raise SystemExit(f"missing icon: {name}")
    svg = re.sub(r"<!--.*?-->", "", p.read_text(), flags=re.S)
    return svg.replace("<svg ", '<svg class="ic" fill="currentColor" ', 1)

E = html.escape

CSS = ff("CT", "catamaran", [700, 800, 900]) + ff("NST", "noto-sans-tamil", [600, 700, 800]) + ff("BT", "baloo-thambi-2", [800]) + """
:root{--red:#E3151B;--red2:#9E0B10;--navy:#06132F;--navy2:#0E2A63;--yellow:#FFCC1F;--white:#fff}
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:1080px;height:1920px;overflow:hidden;background:#000}
body{font-family:'CT','NST',sans-serif;color:#fff;position:relative}
.ic{width:1em;height:1em;display:block}
/* ---------- persistent layers ---------- */
#bg{position:absolute;inset:-200px;background:
  radial-gradient(900px 900px at 20% 15%,#1B3F8F 0%,transparent 60%),
  radial-gradient(800px 800px at 85% 70%,#5A0B12 0%,transparent 60%),
  linear-gradient(160deg,#071739 0%,#040B1E 100%);
  animation:drift 30s linear forwards}
@keyframes drift{from{transform:translate(0,0) scale(1.05) rotate(0)}to{transform:translate(-80px,60px) scale(1.18) rotate(4deg)}}
#grid{position:absolute;inset:0;background-image:linear-gradient(rgba(255,255,255,.05) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.05) 1px,transparent 1px);background-size:90px 90px;
  mask-image:radial-gradient(circle at 50% 45%,#000 0%,transparent 75%);animation:gridmove 30s linear forwards}
@keyframes gridmove{to{background-position:0 540px}}
.beam{position:absolute;width:260px;height:2600px;top:-400px;background:linear-gradient(90deg,transparent,rgba(255,255,255,.08),transparent);transform:rotate(25deg);filter:blur(10px)}
#b1{left:-300px;animation:beam 9s linear infinite}
#b2{left:-600px;animation:beam 13s linear 3s infinite}
@keyframes beam{from{transform:translateX(0) rotate(25deg)}to{transform:translateX(2200px) rotate(25deg)}}
#vig{position:absolute;inset:0;background:radial-gradient(ellipse at 50% 45%,transparent 45%,rgba(0,0,0,.75) 100%);pointer-events:none;z-index:40}
#bars{position:absolute;inset:0;z-index:41;pointer-events:none}
#bars:before,#bars:after{content:"";position:absolute;left:0;right:0;height:0;background:#000}
#bars:before{top:0}#bars:after{bottom:0}
/* top brand strip */
#top{position:absolute;top:70px;left:60px;right:250px;display:flex;align-items:center;gap:18px;z-index:30}
#live{background:var(--red);font:800 34px 'CT','NST';padding:10px 22px 4px;border-radius:8px;display:flex;gap:12px;align-items:center;letter-spacing:.04em}
#live i{width:16px;height:16px;border-radius:50%;background:#fff;animation:blink 1s steps(2) infinite}
@keyframes blink{50%{opacity:.15}}
#date{font:700 32px 'CT','NST';color:#CFD8F0;display:flex;gap:10px;align-items:center}
#date .ic{font-size:28px;color:var(--yellow)}
#logo{position:absolute;top:50px;right:50px;width:170px;height:170px;z-index:45}
/* bottom ticker */
#ticker{position:absolute;left:0;right:0;bottom:0;height:96px;background:var(--yellow);color:var(--navy);display:flex;align-items:center;z-index:30;overflow:hidden}
#tk-l{flex:0 0 auto;height:100%;background:var(--red);color:#fff;font:800 36px 'CT','NST';padding:30px 30px 0;z-index:2}
#tk-t{white-space:nowrap;font:800 36px 'CT','NST';padding-top:10px;animation:tick 30s linear forwards}
@keyframes tick{from{transform:translateX(100px)}to{transform:translateX(-2600px)}}
/* subtitles */
#sub{position:absolute;left:60px;right:60px;bottom:150px;z-index:35;display:flex;justify-content:center}
.cap{position:absolute;bottom:0;max-width:960px;text-align:center;font:800 46px/1.45 'NST','CT';background:rgba(4,11,30,.82);border-left:8px solid var(--yellow);padding:16px 30px 12px;border-radius:10px;opacity:0}
/* scenes */
.scene{position:absolute;left:0;right:0;top:260px;bottom:330px;opacity:0;z-index:20}
.center{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:34px;text-align:center}
.kicker{font:800 44px 'CT','NST';background:var(--red);padding:14px 34px 8px;border-radius:10px;transform-origin:left}
.l1{white-space:pre-line;font:900 104px/1.18 'CT','NST';text-shadow:0 10px 40px rgba(0,0,0,.6)}
.l2{font:900 150px/1 'CT','NST';color:var(--yellow);text-shadow:0 10px 50px rgba(255,204,31,.35)}
.stamp{position:absolute;right:90px;top:40px;font:900 96px 'CT','NST';color:var(--red);border:10px solid var(--red);padding:8px 30px 0;border-radius:14px;transform:rotate(-14deg);opacity:0}
.hero-ic{font-size:300px;color:rgba(255,255,255,.12);position:absolute;left:50%;top:48%;transform:translate(-50%,-50%)}
.bignum{font:900 520px/0.9 'CT';color:var(--yellow);text-shadow:0 20px 80px rgba(255,204,31,.4)}
.unit{font:900 120px 'CT','NST'}
.subl{font:700 54px 'CT','NST';color:#CFD8F0}
.ring{position:absolute;left:50%;top:44%;width:760px;height:760px;margin:-380px 0 0 -380px;border-radius:50%;border:6px solid rgba(255,204,31,.35);opacity:0}
.card{text-align:left;margin:0 60px;background:linear-gradient(160deg,rgba(255,255,255,.12),rgba(255,255,255,.04));border:2px solid rgba(255,255,255,.18);border-radius:36px;padding:56px 50px;display:flex;flex-direction:column;gap:30px;backdrop-filter:blur(6px);box-shadow:0 40px 100px rgba(0,0,0,.5)}
.card-h{display:flex;align-items:center;gap:28px}
.num{flex:0 0 110px;height:110px;border-radius:50%;background:var(--red);font:900 70px 'CT';display:flex;align-items:center;justify-content:center;padding-top:10px}
.tile{flex:0 0 150px;height:150px;border-radius:30px;background:var(--yellow);color:var(--navy);font-size:84px;display:flex;align-items:center;justify-content:center}
.ct{font:900 64px/1.2 'CT','NST'}
.ln{font:700 54px/1.4 'NST','CT';color:#E6ECFA;opacity:0}
.ln b{color:var(--yellow)}
.pill{align-self:flex-start;background:var(--red);font:900 64px 'CT','NST';padding:16px 40px 8px;border-radius:999px;opacity:0;box-shadow:0 0 0 0 rgba(227,21,27,.6)}
.adv-ic{font-size:220px;color:var(--yellow)}
.adv-t{font:900 96px 'CT','NST';color:var(--yellow)}
.adv-x{font:800 66px/1.4 'NST','CT';max-width:900px}
.f-ic{font-size:200px;color:#fff}
.f1{font:900 84px/1.3 'CT','NST'}
.fbtn{background:var(--red);font:900 74px 'CT','NST';padding:22px 54px 10px;border-radius:999px}
.fname{font:800 56px 'CT','NST';color:var(--yellow)}
.flash{position:absolute;inset:0;background:#fff;opacity:0;z-index:42;pointer-events:none}
/* photo scenes (your realistic images, moving camera) */
.scene.photo{top:0;bottom:0;left:0;right:0;z-index:12;overflow:hidden}
.pimg{position:absolute;inset:-90px;background-size:cover;background-position:center;background-repeat:no-repeat;will-change:transform}
.pshade{position:absolute;inset:0;background:linear-gradient(180deg,rgba(4,11,30,.72) 0%,rgba(4,11,30,0) 24%,rgba(4,11,30,0) 46%,rgba(4,11,30,.86) 78%,rgba(4,11,30,.96) 100%)}
.ptag{position:absolute;left:60px;top:190px;background:var(--red);font:800 46px 'CT','NST';padding:14px 34px 6px;border-radius:12px;transform-origin:left;box-shadow:0 10px 30px rgba(0,0,0,.4)}
.pbig{position:absolute;left:60px;right:60px;bottom:420px;font:900 92px/1.16 'CT','NST';text-shadow:0 8px 0 rgba(4,11,30,.9),0 14px 36px rgba(0,0,0,.6);white-space:pre-line}
.pbig b{color:var(--yellow)}
#aichip{position:absolute;left:60px;top:132px;z-index:36;font:700 26px 'NST','CT';background:rgba(0,0,0,.55);border:1.5px solid rgba(255,255,255,.55);padding:6px 16px 2px;border-radius:999px}
"""

def scene_html(i, s):
    t = s["type"]
    if t == "title":
        return f"""<div class="scene center" id="s{i}">
  <div class="hero-ic a-ic">{icon(s.get('icon','file-signature'))}</div>
  <div class="kicker a-k">{E(s.get('kicker',''))}</div>
  <div class="l1 a-l1">{E(s['line1'])}</div>
  <div class="l2 a-l2">{E(s.get('line2',''))}</div>
  {f'<div class="stamp a-st">{E(s["stamp"])}</div>' if s.get('stamp') else ''}
</div>"""
    if t == "big":
        return f"""<div class="scene center" id="s{i}">
  <div class="ring a-ring"></div>
  <div class="hero-ic a-ic" style="top:40%">{icon(s.get('icon','handcuffs'))}</div>
  <div class="bignum a-num" data-to="{E(str(s['number']))}">0</div>
  <div class="unit a-u">{E(s['unit'])}</div>
  <div class="subl a-sl">{E(s.get('sub',''))}</div>
</div>"""
    if t == "card":
        lines = "".join(f'<div class="ln a-ln" style="--d:{k}">{l}</div>' for k, l in enumerate(s.get('lines', [])))
        return f"""<div class="scene center" id="s{i}">
  <div class="card a-card">
    <div class="card-h">{f'<div class="num">{E(str(s["num"]))}</div>' if s.get('num') else ''}<div class="tile">{icon(s['icon'])}</div><div class="ct">{E(s['title'])}</div></div>
    {lines}
    {f'<div class="pill a-pill">{E(s["pill"])}</div>' if s.get('pill') else ''}
  </div>
</div>"""
    if t == "advice":
        return f"""<div class="scene center" id="s{i}">
  <div class="adv-ic a-pop">{icon(s.get('icon','shield-halved'))}</div>
  <div class="adv-t a-up">{E(s['title'])}</div>
  <div class="adv-x a-up2">{E(s['text'])}</div>
</div>"""
    if t == "photo":
        big = f'<div class="pbig a-up">{E(s["big"])}</div>' if s.get("big") else ""
        tag = f'<div class="ptag a-k">{E(s["tag"])}</div>' if s.get("tag") else ""
        img = "file://" + str(Path(s["image"]).resolve())
        return f"""<div class="scene photo" id="s{i}" data-dir="{i % 4}">
  <div class="pimg a-kb" style="background-image:url('{img}')"></div><div class="pshade"></div>{tag}{big}
</div>"""
    if t == "outro":
        return f"""<div class="scene center" id="s{i}">
  <div class="f-ic a-pop">{icon('bullhorn')}</div>
  <div class="f1 a-up">{PAGE["follow"]}</div>
  <div class="fbtn a-btn">Follow செய்யுங்கள்</div>
  <div class="fname a-up2">{PAGE["name"]}</div>
</div>"""
    raise SystemExit("unknown scene type " + t)

def build_html(spec, starts, ends, total):
    scenes = "\n".join(scene_html(i, s) for i, s in enumerate(spec["scenes"]))
    caps = "\n".join(f'<div class="cap" id="c{i}">{E(s.get("caption", s["say"]))}</div>' for i, s in enumerate(spec["scenes"]))
    ticker = E(spec.get("ticker", PAGE["ticker"]))
    logo = f"file://{LOGO.resolve()}"
    timing = json.dumps({"starts": starts, "ends": ends, "total": total})
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>
<div id="bg"></div><div id="grid"></div><div class="beam" id="b1"></div><div class="beam" id="b2"></div>
<div id="top"><div id="live"><i></i>செய்திகள்</div><div id="date">{icon('calendar-days')}{E(spec['date'])}</div></div>
<img id="logo" src="{logo}">
{'<div id="aichip">AI பிரதிநிதித்துவப் படங்கள்</div>' if spec.get('ai_label') else ''}
{scenes}
<div id="sub">{caps}</div>
<div id="ticker"><div id="tk-l">{icon('location-dot').replace('class="ic"','class="ic" style="display:inline-block;vertical-align:-4px"')} {E(spec.get('location','கோவை'))}</div><div id="tk-t">{ticker} &nbsp;&nbsp;•&nbsp;&nbsp; {ticker}</div></div>
<div id="vig"></div><div class="flash" id="flash"></div>
<script>
const T={timing};
const ease=x=>1-Math.pow(1-x,3), back=x=>{{const c=1.70158,c3=c+1;return 1+c3*Math.pow(x-1,3)+c*Math.pow(x-1,2)}};
const cl=(x)=>Math.max(0,Math.min(1,x));
function seg(t,a,d){{return cl((t-a)/d)}}
window.renderAt=function(t){{
  // flash on scene cuts
  let fl=0; T.starts.forEach((s,i)=>{{if(i>0){{const k=t-s; if(k>=0&&k<0.25) fl=Math.max(fl,(1-k/0.25)*0.35)}}}});
  document.getElementById('flash').style.opacity=fl;
  T.starts.forEach((s,i)=>{{
    const el=document.getElementById('s'+i), e=T.ends[i], next=(i+1<T.starts.length)?T.starts[i+1]:T.total;
    const tin=seg(t,s-0.05,0.45), tout=seg(t,next-0.3,0.3);
    const vis=(t>=s-0.05&&t<next)?1:0;
    el.style.opacity=vis*ease(tin)*(1-tout);
    const zoom=1+0.06*cl((t-s)/Math.max(1,next-s));
    el.style.transform=`scale(${{zoom}}) translateY(${{(1-ease(tin))*60}}px)`;
    const lt=t-s;
    if(el.classList.contains('photo')){{
      el.style.transform='none';
      const dur=Math.max(1,next-s), pr=cl((t-s)/dur), dir=+el.dataset.dir;
      const sc=1.06+0.16*pr, px=[-1,1,0,0][dir]*50*(pr-0.5)*2, py=[0,0,-1,1][dir]*50*(pr-0.5)*2;
      el.querySelectorAll('.a-kb').forEach(x=>{{x.style.transform=`translate(${{px}}px,${{py}}px) scale(${{sc}})`}});
    }}
    el.querySelectorAll('.a-k').forEach(x=>{{const p=back(seg(lt,0.1,0.5));x.style.transform=`scaleX(${{p}})`;x.style.opacity=cl(p*2)}});
    el.querySelectorAll('.a-l1').forEach(x=>{{const p=ease(seg(lt,0.3,0.6));x.style.transform=`translateY(${{(1-p)*80}}px)`;x.style.opacity=p;x.style.filter=`blur(${{(1-p)*12}}px)`}});
    el.querySelectorAll('.a-l2').forEach(x=>{{const p=back(seg(lt,0.7,0.6));x.style.transform=`scale(${{0.6+0.4*p}})`;x.style.opacity=cl(p)}});
    el.querySelectorAll('.a-st').forEach(x=>{{const p=seg(lt,1.2,0.25);x.style.opacity=p;x.style.transform=`rotate(-14deg) scale(${{2.2-1.2*ease(p)}})`}});
    el.querySelectorAll('.a-ic').forEach(x=>{{x.style.transform=`translate(-50%,-50%) scale(${{1+0.15*cl(lt/6)}}) rotate(${{-6+8*cl(lt/6)}}deg)`}});
    el.querySelectorAll('.a-ring').forEach(x=>{{const p=seg(lt,0.2,1.2);x.style.opacity=(1-p)*0.9;x.style.transform=`scale(${{0.4+0.9*ease(p)}})`}});
    el.querySelectorAll('.a-num').forEach(x=>{{const to=+x.dataset.to,p=ease(seg(lt,0.15,0.9));x.textContent=Math.round(to*p);x.style.transform=`scale(${{0.7+0.3*back(seg(lt,0.15,0.9))}})`;x.style.opacity=cl(p*3)}});
    el.querySelectorAll('.a-u').forEach(x=>{{const p=ease(seg(lt,0.6,0.5));x.style.opacity=p;x.style.transform=`translateY(${{(1-p)*50}}px)`}});
    el.querySelectorAll('.a-sl').forEach(x=>{{const p=ease(seg(lt,1.0,0.5));x.style.opacity=p;x.style.letterSpacing=`${{(1-p)*0.3}}em`}});
    el.querySelectorAll('.a-card').forEach(x=>{{const p=back(seg(lt,0.05,0.6));x.style.transform=`perspective(1600px) rotateX(${{(1-p)*25}}deg) translateY(${{(1-p)*120}}px)`}});
    el.querySelectorAll('.a-ln').forEach(x=>{{const d=+getComputedStyle(x).getPropertyValue('--d');const p=ease(seg(lt,0.5+d*0.55,0.5));x.style.opacity=p;x.style.transform=`translateX(${{(1-p)*-60}}px)`}});
    el.querySelectorAll('.a-pill').forEach(x=>{{const a=Math.max(0.9,(e-s)*0.55);const p=back(seg(lt,a,0.45));x.style.opacity=cl(p);x.style.transform=`scale(${{0.5+0.5*p}})`;const g=cl((lt-a-0.4)/1.2);x.style.boxShadow=`0 0 0 ${{g*40}}px rgba(227,21,27,${{0.5*(1-g)}})`}});
    el.querySelectorAll('.a-pop').forEach(x=>{{const p=back(seg(lt,0.05,0.6));x.style.transform=`scale(${{p}})`;x.style.opacity=cl(p)}});
    el.querySelectorAll('.a-up').forEach(x=>{{const p=ease(seg(lt,0.35,0.5));x.style.opacity=p;x.style.transform=`translateY(${{(1-p)*60}}px)`}});
    el.querySelectorAll('.a-up2').forEach(x=>{{const p=ease(seg(lt,0.7,0.5));x.style.opacity=p;x.style.transform=`translateY(${{(1-p)*60}}px)`}});
    el.querySelectorAll('.a-btn').forEach(x=>{{const p=back(seg(lt,0.6,0.5));x.style.opacity=cl(p);x.style.transform=`scale(${{(0.6+0.4*p)*(1+0.03*Math.sin(lt*6))}})`}});
    const c=document.getElementById('c'+i);
    const cin=seg(t,s,0.25), cout=seg(t,e+0.15,0.2);
    c.style.opacity=(t>=s&&t<next)?cin*(1-cout):0;
    c.style.transform=`translateY(${{(1-ease(cin))*20}}px)`;
  }});
  document.getAnimations().forEach(a=>{{a.pause();a.currentTime=t*1000}});
}};
</script></body></html>"""

def wav_dur(p):
    with wave.open(str(p)) as w:
        return w.getnframes() / w.getframerate()

def main(spec_path, out_mp4, page="coimbatore"):
    global PAGE, LOGO
    PAGE = PAGES.get(page, PAGES["coimbatore"]); LOGO = KIT / PAGE["logo"]
    spec = json.loads(Path(spec_path).read_text())
    work = Path(out_mp4).with_suffix("")
    work = work.parent / (work.name + "_work"); work.mkdir(parents=True, exist_ok=True)
    texts = [s["say"] for s in spec["scenes"]]
    gap, lead = 0.35, 0.6
    voice_file = os.environ.get("VOICE_FILE")
    if voice_file:
        # real recorded voice: trim silence, normalise, split scene times by text length
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", voice_file, "-af",
                        "silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
                        "highpass=f=80,acompressor=threshold=0.12:ratio=3,loudnorm=I=-16:TP=-1.5", "-ar", "44100", "-ac", "1",
                        str(work / "rec.wav")], check=True)
        dur = wav_dur(work / "rec.wav")
        weights = [max(1, len(t)) for t in texts]
        tot_w = sum(weights)
        starts, ends, t = [], [], lead
        for w in weights:
            d = dur * w / tot_w
            starts.append(round(t, 3)); ends.append(round(t + d, 3)); t += d
        total = round(t + 0.8, 3)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(work / "rec.wav"), "-af",
                        f"adelay={int(lead*1000)}|{int(lead*1000)},apad,atrim=0:{total}", str(work / "voice.wav")], check=True)
    else:
        # 1. voice per scene (free Tamil voice model)
        (work / "lines.json").write_text(json.dumps(texts, ensure_ascii=False))
        subprocess.run([sys.executable, str(HERE / "tts.py"), str(work / "lines.json"), str(work), spec.get("voice", "female")], check=True)
        # keep the reel within 30 s: speed the voice up a little (max 1.25x) if needed
        speech = sum(wav_dur(work / f"line{i}.wav") for i in range(len(texts)))
        room = 29.5 - lead - 0.6 - gap * (len(texts) - 1)
        if room > 0 and speech > room:
            factor = min(1.25, speech / room)
            for i in range(len(texts)):
                src, tmp = work / f"line{i}.wav", work / f"line{i}_fast.wav"
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-af", f"atempo={factor:.3f}", str(tmp)], check=True)
                tmp.replace(src)
            print(f"voice sped up x{factor:.2f} to fit 30 s")
        starts, ends, t = [], [], lead
        for i in range(len(texts)):
            d = wav_dur(work / f"line{i}.wav")
            starts.append(round(t, 3)); ends.append(round(t + d, 3)); t += d + gap
        total = round(t + 0.6, 3)
    if total > 30.5:
        print(f"WARNING: reel is {total:.1f}s (>30s) - shorten the narration")
    if not voice_file:
        make_voice_track(work, texts, starts, total)
    build_rest(spec, work, starts, ends, total, out_mp4)

def make_voice_track(work, texts, starts, total):
    # 2. voice track
    inputs, filt = [], []
    for i in range(len(texts)):
        inputs += ["-i", str(work / f"line{i}.wav")]
        filt.append(f"[{i}:a]adelay={int(starts[i]*1000)}|{int(starts[i]*1000)},aresample=44100[a{i}]")
    n = len(texts)
    filt.append("".join(f"[a{i}]" for i in range(n)) + f"amix=inputs={n}:normalize=0,apad,atrim=0:{total}[v]")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(filt), "-map", "[v]", "-ac", "1", str(work / "voice.wav")], check=True)

def build_rest(spec, work, starts, ends, total, out_mp4):
    import json as _j
    try:
        _c = _j.loads((Path(__file__).resolve().parent.parent / "poster" / "config.json").read_text())
    except Exception:
        _c = {}
    BED_VOL = 0.16 if _c.get("bgm", False) else 0.0  # default: no background music; you add Tamil music in the Instagram app
    # 3. music bed (synthesised, royalty-free) + whooshes at cuts
    pulse = "0.5*sin(2*PI*55*t)*(0.6+0.4*sin(2*PI*0.5*t))+0.25*sin(2*PI*110*t)*exp(-6*mod(t,0.5))+0.12*sin(2*PI*220*t)*exp(-12*mod(t,0.5))"
    pad = "0.18*sin(2*PI*196*t)+0.14*sin(2*PI*246.94*t)+0.12*sin(2*PI*293.66*t)"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"aevalsrc='{pulse}+{pad}':s=44100:d={total}",
                    "-af", f"lowpass=f=1200,volume={BED_VOL},afade=t=in:d=1,afade=t=out:st={total-1.2}:d=1.2", str(work / "bed.wav")], check=True)
    wh = []
    for i, s in enumerate(starts[1:], 1):
        wh.append(f"anoisesrc=d=0.5:c=pink:a=0.5,bandpass=f=1800:w=1500,afade=t=in:d=0.25,afade=t=out:st=0.25:d=0.25,adelay={int((s-0.25)*1000)}[w{i}]")
    if wh:
        mix = ";".join(wh) + ";" + "".join(f"[w{i}]" for i in range(1, len(starts))) + f"amix=inputs={len(starts)-1}:normalize=0,volume=0.35,apad,atrim=0:{total}[o]"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-filter_complex", mix, "-map", "[o]", str(work / "whoosh.wav")], check=True)
        sfx = ["-i", str(work / "whoosh.wav")]
    else:
        sfx = []
    mixf = "[1:a]volume=1.0[bd];[0:a]volume=1.9,acompressor=threshold=0.2:ratio=3[vo];" + ("[2:a]volume=1[wh];[vo][bd][wh]amix=inputs=3" if sfx else "[vo][bd]amix=inputs=2") + ":normalize=0,alimiter=limit=0.8:level=0[m]"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(work / "voice.wav"), "-i", str(work / "bed.wav"), *sfx,
                    "-filter_complex", mixf, "-map", "[m]", "-ar", "44100", str(work / "mix.wav")], check=True)
    # 4. frames
    page = work / "reel.html"
    page.write_text(build_html(spec, starts, ends, total))
    nframes = int(math.ceil(total * FPS))
    enc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-c:v", "mjpeg", "-i", "-",
                            "-i", str(work / "mix.wav"), "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-pix_fmt", "yuv420p",
                            "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(out_mp4)], stdin=subprocess.PIPE)
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": W, "height": H})
        pg.goto(page.resolve().as_uri())
        pg.wait_for_function("document.fonts.status==='loaded'")
        pg.evaluate("document.fonts.ready")
        for f in range(nframes):
            pg.evaluate(f"renderAt({f / FPS})")
            enc.stdin.write(pg.screenshot(type="jpeg", quality=92))
            if f % 150 == 0:
                print(f"frame {f}/{nframes}", flush=True)
        b.close()
    enc.stdin.close(); enc.wait()
    print(f"done {out_mp4} {total:.1f}s")
    # stills for checking
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(viewport={"width": W, "height": H})
        pg.goto(page.resolve().as_uri()); pg.evaluate("document.fonts.ready")
        for i, (s, e) in enumerate(zip(starts, ends)):
            pg.evaluate(f"renderAt({e - 0.1})")
            pg.screenshot(path=str(work / f"check_{i}.png"))
        b.close()

if __name__ == "__main__":
    main(*sys.argv[1:])
