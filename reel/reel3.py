"""கோயம்புத்தூர் 360 — MODERN reel v3 (hook in frame 1, multi-angle cuts across the story's photos, word-by-word captions).
Usage: python3 reel3.py spec.json out.mp4 [page]
spec: {"date","cat","location","hook":[line1,line2],"images":[paths],"voice":"female",
       "sentences":[{"say":"...","fact":"short on-screen fact or ''"}], "outro":{"say":"..."}}
No intro, no ticker, no AI label. One story per reel. The photos are never stretched: zoom is capped at 1.45.
"""
import json, sys, os, re, subprocess, html, wave, math
from pathlib import Path
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
import reel as R  # fonts, icons, page branding, voice helpers

E = html.escape
W, H, FPS = 1080, 1920, 30
CUT = 1.9           # seconds per camera angle
MAX_ZOOM = 1.45

CSS = R.ff("CT", "catamaran", [700, 800, 900]) + R.ff("NST", "noto-sans-tamil", [600, 700, 800]) + R.ff("BT", "baloo-thambi-2", [800]) + """
:root{--red:#E3151B;--navy:#06132F;--yellow:#FFCC1F}
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:1080px;height:1920px;overflow:hidden;background:#000}
body{font-family:'NST','CT',sans-serif;color:#fff;position:relative}
.ic{width:1em;height:1em;display:block}
#stage{position:absolute;inset:0;overflow:hidden}
.pic{position:absolute;left:0;top:0;width:1080px;height:1920px;object-fit:cover;opacity:0;will-change:transform,filter}
#shade{position:absolute;inset:0;z-index:5;background:linear-gradient(180deg,rgba(4,10,28,.78) 0%,rgba(4,10,28,.05) 22%,rgba(4,10,28,0) 52%,rgba(4,10,28,.55) 74%,rgba(4,10,28,.9) 100%)}
#vig{position:absolute;inset:0;z-index:6;background:radial-gradient(ellipse at 50% 45%,transparent 55%,rgba(0,0,0,.45) 100%)}
#flash{position:absolute;inset:0;z-index:7;background:#fff;opacity:0}
#prog{position:absolute;left:0;top:0;height:9px;width:0;z-index:30}
#brand{position:absolute;left:44px;top:56px;z-index:30;display:flex;flex-direction:column;gap:10px}
#brand .row1{display:flex;align-items:stretch;gap:14px}
#brand .bar{width:9px;border-radius:5px}
#brand .nm{font:800 46px/1.1 'BT','NST';text-shadow:0 3px 0 rgba(0,0,0,.6),0 6px 18px rgba(0,0,0,.5)}
#brand .pill{align-self:flex-start;font:800 30px 'NST','CT';padding:6px 20px 0;border-radius:10px;color:#fff;box-shadow:0 6px 18px rgba(0,0,0,.4)}
#brand .dt{display:flex;align-items:center;gap:10px;font:700 30px 'NST','CT';text-shadow:0 2px 8px rgba(0,0,0,.8)}
#brand .dt .ic{font-size:26px;color:var(--yellow)}
#logo{position:absolute;right:44px;top:50px;width:124px;height:124px;border-radius:50%;z-index:30;box-shadow:0 6px 22px rgba(0,0,0,.5)}
#foot{position:absolute;left:44px;bottom:28px;width:300px;height:auto;z-index:35;pointer-events:none;opacity:.92}
#big{position:absolute;left:0;right:0;top:760px;z-index:21;text-align:center;opacity:0;font:900 230px/1.1 'CT','NST';color:var(--yellow);-webkit-text-stroke:16px #000;paint-order:stroke fill;text-shadow:0 12px 40px rgba(0,0,0,.6)}
#bigu{position:absolute;left:0;right:0;top:1010px;z-index:21;text-align:center;opacity:0;font:900 70px/1.2 'CT','NST';color:#fff;-webkit-text-stroke:12px #000;paint-order:stroke fill}
#hook{position:absolute;left:50px;right:50px;top:380px;z-index:20;text-align:center;opacity:0}
#hook .h1{font:900 96px/1.12 'CT','NST';color:#fff}
#hook .h2{font:900 108px/1.12 'CT','NST';color:var(--yellow);margin-top:6px}
#hook div{-webkit-text-stroke:14px #000;paint-order:stroke fill;text-shadow:0 10px 30px rgba(0,0,0,.5)}
#dust{position:absolute;inset:0;z-index:4;pointer-events:none;overflow:hidden}
.dp{position:absolute;border-radius:50%;background:radial-gradient(circle,rgba(255,244,214,.95),rgba(255,244,214,0) 70%)}
#sweep{position:absolute;inset:-300px;z-index:4;pointer-events:none;mix-blend-mode:soft-light;background:linear-gradient(105deg,transparent 40%,rgba(255,236,190,.55) 50%,transparent 60%)}
#grain{position:absolute;inset:0;z-index:8;pointer-events:none;opacity:.10;mix-blend-mode:overlay}
.sticker{position:absolute;left:0;top:360px;max-width:940px;z-index:22;background:var(--yellow);color:var(--navy);font:800 46px/1.3 'NST','CT';padding:16px 34px 10px 30px;border-radius:0 24px 24px 0;box-shadow:0 10px 30px rgba(0,0,0,.45);opacity:0}
.sticker b{color:#C4100F}
#cap{position:absolute;left:40px;right:40px;top:1110px;height:310px;z-index:25;text-align:center;background:linear-gradient(90deg,rgba(6,19,47,.93),rgba(6,19,47,.82));border-left:16px solid var(--accent);border-radius:8px 30px 30px 8px;box-shadow:0 14px 40px rgba(0,0,0,.5);opacity:0}
.ph{position:absolute;left:52px;right:46px;top:50%;transform:translateY(-50%);font:800 62px/1.35 'CT','NST';color:#fff;opacity:0;text-shadow:0 4px 14px rgba(0,0,0,.7)}
#tick{position:absolute;left:0;right:0;top:1446px;height:96px;z-index:26;display:flex;overflow:hidden;background:rgba(6,19,47,.95);border-top:6px solid var(--accent)}
#tick .lab{flex:none;background:var(--red);padding:12px 34px 0;font:900 46px/1.5 'CT','NST';color:#fff}
#tick .trk{position:relative;flex:1;overflow:hidden}
#tick .txt{position:absolute;left:0;top:10px;white-space:nowrap;font:700 44px/1.5 'NST','CT';color:#fff}
.ph span{display:inline-block;transform-origin:50% 80%}
.ph span.on{color:var(--yellow)}
#pulse{display:inline-block;width:22px;height:22px;border-radius:50%;background:#fff;margin-right:12px;vertical-align:middle}
#end{position:absolute;inset:0;z-index:40;opacity:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:30px;text-align:center;background:rgba(4,10,28,.55)}
#end img{width:330px;height:330px;border-radius:50%;box-shadow:0 14px 50px rgba(0,0,0,.6)}
#end .e1{font:900 76px/1.25 'CT','NST'}
#end .e2{background:var(--red);font:900 56px 'CT','NST';padding:16px 46px 8px;border-radius:999px}
#end .e3{font:800 50px 'CT','NST';color:var(--yellow)}
"""

ACCENT = {"மின் தடை": "#F5A100", "மழை": "#1E88E5", "வானிலை": "#1E88E5"}

def accent_for(cat):
    for k, v in ACCENT.items():
        if k in cat:
            return v
    return "#E3151B"


def wav_dur(p):
    with wave.open(str(p)) as w:
        return w.getnframes() / w.getframerate()


def word_times(text, s, e):
    """spread a sentence's duration over its words by letter count (no word clock from the voice model)."""
    words = text.split()
    wts = [max(2, len(w)) for w in words]
    tot = sum(wts)
    out, t = [], s
    for w, k in zip(words, wts):
        d = (e - s) * k / tot
        out.append((w, round(t, 3), round(t + d, 3)))
        t += d
    return out


def phrases(words, n=6):
    """groups of up to 3 words, breaking after a comma/full stop"""
    out, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) >= n or re.search(r"[,.!?।]$", w[0]):
            out.append(cur); cur = []
    if cur:
        if out and len(cur) == 1:
            out[-1] += cur
        else:
            out.append(cur)
    return out


def plan_shots(n_img, content_end, snaps):
    """camera angles: a cut about every CUT s, snapped to a word start; images spread evenly over the story."""
    n = max(2, int(round(content_end / CUT)))
    cuts = [0.0]
    for i in range(1, n):
        t = content_end * i / n
        near = min(snaps, key=lambda x: abs(x - t)) if snaps else t
        cuts.append(near if abs(near - t) < 0.55 and near > cuts[-1] + 0.9 else t)
    cuts.append(content_end + 5)
    # angle presets: (zoom start, zoom end, focus x, focus y, pan px x, pan px y)
    angles = [(1.30, 1.40, .50, .36, 0, -20),   # tight on the subject (upper centre)
              (1.12, 1.22, .50, .50, 0, 0),     # medium
              (1.04, 1.12, .50, .55, 0, 0),     # wide push-in
              (1.22, 1.32, .30, .45, 30, 0),    # left pan
              (1.22, 1.32, .70, .45, -30, 0)]   # right pan
    shots = []
    for i in range(len(cuts) - 1):
        img = min(n_img - 1, int(i * n_img / (len(cuts) - 1)))
        z0, z1, fx, fy, px, py = angles[(i + (0 if i == 0 else 1)) % len(angles)] if i else angles[0]
        shots.append({"a": round(cuts[i], 3), "b": round(cuts[i + 1], 3), "img": img,
                      "z0": min(z0, MAX_ZOOM), "z1": min(z1, MAX_ZOOM), "fx": fx, "fy": fy, "px": px, "py": py})
    return shots


def build_html(spec, shots, sents, caps, hook_end, end_t, total, page):
    logo = f"file://{R.KIT.resolve() / page['logo']}"
    foot = f"file://{(Path(__file__).resolve().parent / 'assets' / page.get('footer', 'footer_coimbatore.png')).as_posix()}"
    imgs = "".join(f'<img class="pic" id="p{i}" src="file://{Path(p).resolve()}">' for i, p in enumerate(spec["images"]))
    acc = accent_for(spec.get("cat", ""))
    stick = "".join(f'<div class="sticker" id="k{i}">{s["fact"]}</div>' for i, s in enumerate(sents) if s.get("fact"))
    import random
    rnd = random.Random(7)
    dust = "".join(f'<div class="dp" style="left:{rnd.randint(0,1040)}px;top:{rnd.randint(0,1880)}px;width:{(sz:=rnd.randint(6,22))}px;height:{sz}px;opacity:.0" data-s="{rnd.random()*6.28:.2f}" data-v="{rnd.uniform(.4,1.3):.2f}"></div>' for _ in range(34))
    cap_html = ""
    for gi, g in enumerate(caps):
        spans = "".join(f'<span id="w{gi}_{k}">{E(w[0])}</span> ' for k, w in enumerate(g["words"]))
        cap_html += f'<div class="ph" id="g{gi}">{spans}</div>'
    hook = spec.get("hook") or ["", ""]
    big = None
    for src in []:  # big-number pop-up removed: a giant number with no context confused viewers
        m_ = re.search(r"(\d[\d,]*(?:\.\d+)?)\s*([^\d\s,.:;•]{0,14})", src or "")
        if m_:
            big = {"n": m_.group(1), "u": m_.group(2)}
            break
    tick = E("  •  ".join(x for x in [hook[0], hook[1], spec.get("location", "")] if x)) + "  •  "
    data = json.dumps({"shots": shots, "sents": [{"a": s["a"], "b": s["b"], "fact": bool(s.get("fact"))} for s in sents],
                       "caps": [{"a": g["a"], "b": g["b"], "w": [[x[1], x[2]] for x in g["words"]]} for g in caps],
                       "big": big, "hook_end": hook_end, "end_t": end_t, "total": total, "n": len(spec["images"])})
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body style="--accent:{acc}">
<svg width="0" height="0" style="position:absolute"><filter id="wob" x="-5%" y="-5%" width="110%" height="110%"><feTurbulence id="tb" type="fractalNoise" baseFrequency="0.006 0.010" numOctaves="2" seed="3" result="n"/><feDisplacementMap in="SourceGraphic" in2="n" scale="7" xChannelSelector="R" yChannelSelector="G"/></filter>
<filter id="gr" x="0" y="0" width="100%" height="100%"><feTurbulence id="gt" type="fractalNoise" baseFrequency="0.85" numOctaves="2" seed="1"/><feColorMatrix type="saturate" values="0"/></filter></svg>
<div id="stage">{imgs}</div><div id="dust">{dust}</div><div id="sweep"></div><svg id="grain" width="1080" height="1920"><rect width="1080" height="1920" filter="url(#gr)"/></svg><div id="shade"></div><div id="vig"></div><div id="flash"></div>
<div id="prog" style="background:{acc}"></div>
<div id="brand"><div class="row1"><div class="bar" style="background:{acc}"></div><div class="nm">{page['name']}</div></div>
<div class="pill" style="background:{acc}">{E(spec.get('cat',''))}</div>
<div class="dt">{R.icon('calendar-days')}{E(spec['date'])}</div></div>
<img id="logo" src="{logo}">
<img id="foot" src="{foot}">
<div id="big"></div><div id="bigu"></div>
<div id="hook"><div class="h1">{E(hook[0])}</div><div class="h2">{E(hook[1])}</div></div>
{stick}
<div id="cap">{cap_html}</div>
<div id="tick"><div class="lab" id="lab"><span id="pulse"></span>செய்தி</div><div class="trk"><div class="txt" id="ttxt"><span id="cyc">{tick}</span>{tick}{tick}{tick}</div></div></div>
<div id="end"><img src="{logo}"><div class="e1">{E(page['tagline'])}</div><div class="e2">FOLLOW @{page['handle']}</div><div style="font:800 44px 'NST','CT';color:#fff;background:rgba(0,0,0,.35);padding:12px 30px 6px;border-radius:16px">📌 Save • தேவைப்படுவோருக்கு Share</div><div class="e3">{E(spec.get('location',''))}</div></div>
<script>
const D={data};
const cl=x=>Math.max(0,Math.min(1,x)), ease=x=>1-Math.pow(1-x,3), back=x=>{{const c=1.70158,c3=c+1;return 1+c3*Math.pow(x-1,3)+c*Math.pow(x-1,2)}};
function place(sh_,t,el,extra){{
  const dur=Math.max(0.5,sh_.b-sh_.a), tt=Math.min(t,sh_.b), pr=cl((tt-sh_.a)/Math.min(dur,CUTMAX)), k=tt-sh_.a;
  const pe=pr<0.5?2*pr*pr:1-Math.pow(-2*pr+2,2)/2;
  const z=sh_.z0+(sh_.z1-sh_.z0)*pe;
  const punch=1+0.07*Math.max(0,1-k/0.22);
  const sh=0.45+0.5*Math.max(0,1-k/0.5);
  const hx=(5*Math.sin(t*1.3)+2.6*Math.sin(t*2.9+1)+1.2*Math.sin(t*7.1))*sh, hy=(4.2*Math.sin(t*1.1+2)+2.2*Math.sin(t*3.3)+1.0*Math.sin(t*6.3+1))*sh, hr=0.32*Math.sin(t*0.9)+0.12*Math.sin(t*2.3);
  el.style.transformOrigin=(sh_.fx*100)+'% '+(sh_.fy*100)+'%';
  el.style.transform='translate('+(sh_.px*(pe-0.5)+hx+(extra||0))+'px,'+(sh_.py*(pe-0.5)+hy)+'px) rotate('+hr+'deg) scale('+(z*punch*1.025)+')';
}}
window.renderAt=function(t){{
  let ai=D.shots.length-1;
  D.shots.forEach((s,i)=>{{if(t>=s.a&&t<s.b)ai=i}});
  const active=D.shots[ai], k=t-active.a;
  const blurEnd=t>=D.end_t?Math.min(1,(t-D.end_t)/0.3):0;
  const prev=ai>0?D.shots[ai-1]:null;
  const TR=0.28, trans=(prev&&prev.img!==active.img&&k<TR)?cl(k/TR):1;   // push + dissolve between photos
  for(let i=0;i<D.n;i++){{const e=document.getElementById('p'+i); e.style.opacity=0; e.style.zIndex=0; e.style.filter='none';}}
  const el=document.getElementById('p'+active.img);
  el.style.opacity=ease(trans); el.style.zIndex=2;
  place(active,t,el,(1-ease(trans))*120);
  if(trans<1){{const pe_=document.getElementById('p'+prev.img); pe_.style.opacity=1; pe_.style.zIndex=1; place(prev,t,pe_,-ease(trans)*160);}}
  const wb=(k<0.14&&active.a>0&&trans>=1)?(6*(1-k/0.14)):0;
  if(wb+blurEnd>0)el.style.filter='blur('+(wb+blurEnd*22)+'px)';
  document.querySelectorAll('.dp').forEach(d=>{{const sd=+d.dataset.s,v=+d.dataset.v;d.style.transform='translate('+(30*Math.sin(t*0.5*v+sd))+'px,'+(-(t*40*v)%1900)+'px)';d.style.opacity=0.18+0.18*Math.sin(t*1.2*v+sd);}});
  document.getElementById('sweep').style.transform='translateX('+(((t*90)%2600)-900)+'px)';
  document.getElementById('gt').setAttribute('seed',''+Math.floor(t*24));
  document.getElementById('flash').style.opacity=(active.a>0&&k<0.12)?0.16*(1-k/0.12):0;
  document.getElementById('prog').style.width=(100*cl(t/D.end_t))+'%';
  // hook: visible from frame 1
  const h=document.getElementById('hook');
  const hin=ease(cl(t/0.18)), hout=cl((t-(D.hook_end-0.3))/0.3);
  h.style.opacity=(t<D.hook_end)?hin*(1-hout):0;
  h.style.transform='scale('+(0.92+0.08*back(cl(t/0.35)))+')';
  // big number pop (first 1.9 s): the number counts up and punches in
  const bg=document.getElementById('big'), bu=document.getElementById('bigu');
  if(D.big&&t<2.1){{
    const u=ease(cl((t-0.12)/0.5)), pp=back(cl((t-0.12)/0.35)), out=cl((t-1.7)/0.35);
    const raw=D.big.n.replace(/,/g,''), val=parseFloat(raw);
    bg.textContent=(isNaN(val)||raw.indexOf('.')>=0)?D.big.n:Math.round(val*u).toLocaleString('en-IN');
    bg.style.opacity=(t>=0.12)?cl(pp*2)*(1-out):0; bg.style.transform='scale('+(0.6+0.4*Math.min(1.1,pp))+')';
    bu.textContent=D.big.u; bu.style.opacity=(t>=0.3&&D.big.u)?cl((t-0.3)/0.2)*(1-out):0;
  }} else {{bg.style.opacity=0; bu.style.opacity=0;}}
  // fact stickers
  let ki=0;
  D.sents.forEach((s,i)=>{{
    if(!s.fact)return;
    const st=document.getElementById('k'+i); if(!st)return;
    const a=s.a+0.1,b=s.b+0.15;
    const p=back(cl((t-a)/0.35)), out=cl((t-(b-0.2))/0.2);
    st.style.opacity=(t>=a&&t<b)?cl(p*2)*(1-out):0;
    st.style.transform='translateX('+((1-Math.min(1,p))*-900)+'px) scale('+(1+0.05*Math.sin(Math.PI*cl((t-a)/0.5)))+')';
  }});
  const pin=ease(cl((t-0.15)/0.45)), pend=t<D.end_t?1:0;
  const capE=document.getElementById('cap'), tkE=document.getElementById('tick');
  capE.style.opacity=pend; capE.style.transform='translateX('+(-(1-pin)*1100)+'px)';
  tkE.style.opacity=pend; tkE.style.transform='translateY('+((1-ease(cl((t-0.35)/0.45)))*140)+'px)';
  document.getElementById('pulse').style.opacity=0.55+0.45*Math.sin(t*6);
  const lab=document.getElementById('lab'); lab.style.filter='brightness('+(1+0.25*Math.max(0,Math.sin(t*3.1)))+')';
  const cy=document.getElementById('cyc').offsetWidth||1;
  document.getElementById('ttxt').style.transform='translateX('+(-((t*150)%cy))+'px)';
  // captions
  D.caps.forEach((g,gi)=>{{
    const ge=document.getElementById('g'+gi);
    const on=(t>=g.a&&t<g.b)&&t<D.end_t;
    ge.style.opacity=on?cl((t-g.a)/0.1):0;
    if(on){{const u=ease(cl((t-g.a)/0.22)); ge.style.transform='translateY(calc(-50% + '+(26*(1-u))+'px))';
      g.w.forEach((w,k)=>{{const sp=document.getElementById('w'+gi+'_'+k),act=(t>=w[0]&&t<w[1]); sp.className=act?'on':''; sp.style.transform=act?'scale('+(1+0.04*Math.sin(Math.PI*cl((t-w[0])/Math.max(0.12,w[1]-w[0])))) +')':'none';}});}}
  }});
  const e=document.getElementById('end');
  e.style.opacity=ease(cl((t-D.end_t)/0.3));
}};
const CUTMAX=2.4;
function fitEl(el,maxH,min){{let fs=parseFloat(getComputedStyle(el).fontSize);let n=0;while((el.scrollWidth>el.clientWidth+1||el.offsetHeight>maxH)&&fs>min&&n++<60){{fs-=2;el.style.fontSize=fs+'px';}}}}
window.fitAll=function(){{
  document.querySelectorAll('.ph').forEach(e=>fitEl(e,250,36));
  document.querySelectorAll('.sticker').forEach(e=>fitEl(e,190,28));
  fitEl(document.querySelector('#hook .h1'),230,44); fitEl(document.querySelector('#hook .h2'),125,44);
}};
</script></body></html>"""


from digits import to_digits  # display-only: numbers as digits, 360

PAUSE = 0.8      # quiet beat + soft chime between the end of the news and the "follow" line
CHIME_T = 0.0
OUTRO_EN = "Follow Coimbatore Three Sixty for more local news."


def english_outro(work, idx):
    """The brand line is spoken in clear Indian English (Tamil TTS cannot say English words well). Falls back to the Tamil line on any error."""
    try:
        mp3 = work / "outro_en.mp3"
        subprocess.run([sys.executable, "-m", "edge_tts", "--voice", "en-IN-NeerjaNeural", "--rate=+0%", "--text", OUTRO_EN, "--write-media", str(mp3)], check=True, timeout=60)
        out = work / f"line{idx}.wav"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp3), "-af",
                        "silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
                        "highpass=f=80,acompressor=threshold=0.12:ratio=3:attack=5:release=80,loudnorm=I=-16:TP=-1.5", "-ar", "22050", "-ac", "1", str(out)], check=True)
        print("outro spoken in English")
    except Exception as e:
        print("English outro failed, keeping the Tamil line:", e)


def main(spec_path, out_mp4, page_key="coimbatore"):
    R.PAGE = R.PAGES.get(page_key, R.PAGES["coimbatore"]); R.LOGO = R.KIT / R.PAGE["logo"]      # one page only
    spec = json.loads(Path(spec_path).read_text())
    work = Path(out_mp4).with_suffix("")
    work = work.parent / (work.name + "_work"); work.mkdir(parents=True, exist_ok=True)
    sents = spec["sentences"]
    for _s in sents:
        _s["fact"] = to_digits(_s.get("fact", ""))
    outro = spec["outro"]
    texts = [s["say"] for s in sents] + [outro["say"]]
    gap, lead = 0.18, 0.08
    (work / "lines.json").write_text(json.dumps(texts, ensure_ascii=False))
    voice_file = os.environ.get("VOICE_FILE")
    if voice_file:
        raise SystemExit("VOICE_FILE not supported in reel3 yet")
    subprocess.run([sys.executable, str(Path(__file__).resolve().parent / "tts.py"), str(work / "lines.json"), str(work), spec.get("voice", "female")], check=True)
    english_outro(work, len(texts) - 1)
    speech = sum(wav_dur(work / f"line{i}.wav") for i in range(len(texts)))
    room = 26.0 - lead - 0.5 - gap * (len(texts) - 1) - (PAUSE - gap)
    if room > 0 and speech > room:
        factor = min(1.1, speech / room)
        for i in range(len(texts)):
            src, tmp = work / f"line{i}.wav", work / f"line{i}_fast.wav"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-af", f"atempo={factor:.3f}", str(tmp)], check=True)
            tmp.replace(src)
        print(f"voice sped up x{factor:.2f} to fit the time limit")
    starts, ends, t = [], [], lead
    for i in range(len(texts)):
        d = wav_dur(work / f"line{i}.wav")
        starts.append(round(t, 3)); ends.append(round(t + d, 3)); t += d + (PAUSE if i == len(texts) - 2 else gap)
    global CHIME_T
    CHIME_T = round(ends[-2] + 0.12, 3)
    end_t = CHIME_T                      # ending card + chime come in together, then a short beat, then the follow-us line
    total = round(max(ends[-1] + 0.6, end_t + 1.6), 3)
    if total > 30.5:
        print(f"WARNING: reel is {total:.1f}s (>30s)")
    R.make_voice_track(work, texts, starts, total)
    for i, s in enumerate(sents):
        s["a"], s["b"] = starts[i], ends[i]
    # captions: words timed inside each sentence, phrases of up to 3 words
    caps = []
    for i, s in enumerate(sents):
        wt = word_times(to_digits(s["say"]), starts[i], ends[i])  # show digits, speak words
        for g in phrases(wt):
            caps.append({"a": g[0][1], "b": g[-1][2], "words": g})
    snaps = [w[1] for g in caps for w in g["words"]]
    shots = plan_shots(len(spec["images"]), end_t, snaps)
    hook_end = min(2.7, ends[0])
    build_audio(work, starts, shots, sents, total)
    page = work / "reel3.html"
    page.write_text(build_html(spec, shots, sents, caps, hook_end, end_t, total, R.PAGE))
    nframes = int(math.ceil(total * FPS))
    enc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-c:v", "mjpeg", "-i", "-",
                            "-i", str(work / "mix.wav"), "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-profile:v", "high",
                            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out_mp4)], stdin=subprocess.PIPE)
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": W, "height": H})
        pg.goto(page.resolve().as_uri())
        pg.wait_for_function("document.fonts.status==='loaded'")
        pg.evaluate("document.fonts.ready")
        pg.evaluate("fitAll()")
        for f in range(nframes):
            pg.evaluate(f"renderAt({f / FPS})")
            enc.stdin.write(pg.screenshot(type="jpeg", quality=96))
            if f % 150 == 0:
                print(f"frame {f}/{nframes}", flush=True)
        b.close()
    enc.stdin.close(); enc.wait()
    print(f"done {out_mp4} {total:.1f}s")
    # cover photo for Instagram: sharp 9:16 frame with the hook headline, without the moving caption/progress bar
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page(viewport={"width": W, "height": H})
            pg.goto(page.resolve().as_uri())
            pg.wait_for_function("document.fonts.status==='loaded'")
            pg.evaluate("fitAll()")
            pg.evaluate("renderAt(0.9)")
            pg.evaluate("document.getElementById('cap').style.display='none';document.getElementById('tick').style.display='none';document.getElementById('big').style.display='none';document.getElementById('bigu').style.display='none';document.getElementById('prog').style.display='none';document.getElementById('hook').style.opacity=1;")
            pg.screenshot(path=str(Path(out_mp4).with_name(Path(out_mp4).stem + "_cover.jpg")), type="jpeg", quality=95)
            b.close()
    except Exception as e:
        print("cover failed:", e)


def build_audio(work, starts, shots, sents, total):
    """voice + a soft whoosh on each camera cut + a pop on each fact sticker (no music; add Tamil music in the Instagram app)."""
    parts, labels = [], []
    k = 0
    for s in shots[1:]:
        if s["a"] < total - 1:
            parts.append(f"anoisesrc=d=0.4:c=pink:a=0.5,bandpass=f=1800:w=1500,afade=t=in:d=0.2,afade=t=out:st=0.2:d=0.2,adelay={int(max(0,s['a']-0.2)*1000)}|{int(max(0,s['a']-0.2)*1000)}[w{k}]")
            labels.append(f"[w{k}]"); k += 1
    n_cut = k
    for i, s in enumerate(sents):
        if s.get("fact"):
            d = int((s["a"] + 0.1) * 1000)
            parts.append(f"sine=f=880:d=0.12,afade=t=out:st=0.04:d=0.08,volume=0.5,adelay={d}|{d}[w{k}]")
            labels.append(f"[w{k}]"); k += 1
    d = int(CHIME_T * 1000)       # soft two-note chime as the news ends and the ending card appears
    parts.append(f"sine=f=784:d=0.55,afade=t=in:d=0.02,afade=t=out:st=0.05:d=0.5,volume=1.4,adelay={d}|{d}[w{k}]")
    labels.append(f"[w{k}]"); k += 1
    d2 = d + 140
    parts.append(f"sine=f=1175:d=0.5,afade=t=in:d=0.02,afade=t=out:st=0.05:d=0.45,volume=1.1,adelay={d2}|{d2}[w{k}]")
    labels.append(f"[w{k}]"); k += 1
    if not labels:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(work / "voice.wav"), "-af", "volume=1.9,alimiter=limit=0.8:level=0",
                        "-ar", "44100", str(work / "mix.wav")], check=True)
        add_music(work, total)
        return
    fx = ";".join(parts) + ";" + "".join(labels) + f"amix=inputs={len(labels)}:normalize=0,volume=0.22,apad,atrim=0:{total}[o]"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-filter_complex", fx, "-map", "[o]", "-ar", "44100", str(work / "sfx.wav")], check=True)
    mixf = "[0:a]volume=1.9,acompressor=threshold=0.2:ratio=3[vo];[1:a]volume=1[sf];[vo][sf]amix=inputs=2:normalize=0,alimiter=limit=0.8:level=0[m]"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(work / "voice.wav"), "-i", str(work / "sfx.wav"),
                    "-filter_complex", mixf, "-map", "[m]", "-ar", "44100", str(work / "mix.wav")], check=True)
    add_music(work, total)


def add_music(work, total):
    """quiet background bed under the voice (ducks while the voice speaks). Own tracks in reel/music/ are used if present, otherwise an
    original generated bed. Any failure keeps the reel without music."""
    if os.environ.get("REEL_MUSIC") != "1":      # owner (23 Oct): no background music at all (set REEL_MUSIC=1 to bring it back)
        print("background music off")
        return
    try:
        mix = work / "mix.wav"
        here = Path(__file__).resolve().parent
        tracks = sorted([p for p in (here / "music").glob("*") if p.suffix.lower() in (".mp3", ".wav", ".m4a")])
        bed = work / "bed_music.wav"
        if tracks:
            src = tracks[sum(map(ord, work.name)) % len(tracks)]
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "-1", "-i", str(src), "-t", f"{total:.2f}", "-ac", "1", "-ar", "44100", str(bed)], check=True)
        else:
            subprocess.run([sys.executable, str(here / "music.py"), str(bed), f"{total:.2f}", str(sum(map(ord, work.name)) % 4)], check=True)
        out = work / "mix_music.wav"
        fx = ("[1:a]volume=0.4,afade=t=out:st=%.2f:d=1.2[mu];[0:a]asplit=2[vo][sc];"
              "[mu][sc]sidechaincompress=threshold=0.02:ratio=10:attack=15:release=350[duck];"
              "[vo][duck]amix=inputs=2:normalize=0,alimiter=limit=0.9:level=0[m]") % max(0.5, total - 1.3)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mix), "-i", str(bed), "-filter_complex", fx, "-map", "[m]", "-ar", "44100", str(out)], check=True)
        out.replace(mix)
        print("background music added")
    except Exception as e:
        print("music skipped:", e)


if __name__ == "__main__":
    main(*sys.argv[1:])
