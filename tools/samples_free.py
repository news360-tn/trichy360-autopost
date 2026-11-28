"""owner 28 Nov: SAMPLES of the free news-reel ideas, for the owner's review only - never posted (no Instagram / Facebook / Sheet code).
  news     : 4 real Trichy news, one per news type, each with ALL the free ideas together:
             (1) big word-by-word captions (place and numbers highlighted) timed by the voice's own word clock,
             (2) a picture change about every 2 s (other crop / zoom, a map-pin card, a number counter),
             (3) the format of its news type (accident = BREAKING, power cut = notice board, scheme = amount / last date / steps,
                 rain = rain + alert), (4) "living pictures" (the AI picture moves in depth, from a free depth model).
  morning  : "காலை 5 செய்திகள்" - the morning bulletin (same look as the evening top 5, the latest news by importance).
  comments : the first comment for each of today's news, by news type.
  python tools/samples_free.py news|morning|comments  -> out/samples/free/..."""
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from html import escape as E
from pathlib import Path

import numpy as np
import requests

ROOT = Path(__file__).resolve().parent.parent
for d in ("rasipalan", "goldrate", "poster", "research_free", "reel"):
    sys.path.insert(0, str(ROOT / d))
os.environ.setdefault("PAGE", "trichy")
import gold360_render as G      # noqa: E402
import gold_reel      # noqa: E402
import rasi_parrot as RP      # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))
FPS, W, H, SR = 30, 1080, 1920, RP.SR
OUT = ROOT / "out" / "samples" / "free"
PAGE = {"town": "திருச்சி", "name1": "திருச்சி", "logo": ROOT / "kit" / "logo_trichy.png", "handle": "trichy360.official"}
MAROON, MAROON2, GOLD = G.MAROON, G.MAROON2, G.GOLD
VOICE = ("ta-IN-ValluvarNeural", "+12%", "+4Hz")
SHOT_S, MOVE_FRAMES = 2.2, 96

STORIES = [
    {"id": "RN-184", "kind": "breaking", "prompts": [
        "A wrecked silver sedan car crashed into a huge roadside tree on a rural two-lane highway in Tamil Nadu, broken windscreen, "
        "police barricade and traffic cones, evening light, photorealistic news photo, no people, no text",
        "Close view of a damaged car front bonnet and shattered headlight near a tree trunk on an Indian village road, dusk, "
        "photorealistic, no people, no text"]},
    {"id": "RN-185", "kind": "power", "prompts": [
        "Electricity board linemen in safety helmets repairing overhead power lines on a utility pole in a Tamil Nadu town, "
        "daytime, photorealistic news photo, faces not visible, no text",
        "A Tamil Nadu electricity substation with transformers and transmission lines under a clear sky, photorealistic, no text"]},
    {"id": "RN-199", "kind": "scheme", "prompts": [
        "Rural Tamil Nadu village women in sarees standing with healthy milch cows in front of a cattle shed, morning sunlight, "
        "photorealistic, no text",
        "Two dairy cows with a steel milk can in a clean village cattle shed in Tamil Nadu, soft morning light, photorealistic, no text"]},
    {"id": "RN-197", "kind": "rain", "prompts": [
        "A waterfall in green Eastern Ghats hills of Tamil Nadu in heavy monsoon flow, rain falling, mist, a closed barricade "
        "in front, photorealistic, no people, no text",
        "Rain-soaked forest road in Pachamalai hills Tamil Nadu with dark rain clouds and a flowing stream, photorealistic, no text"]},
]
TYPE_LABEL = {"breaking": "சாலை விபத்து", "power": "மின் தடை அறிவிப்பு", "scheme": "அரசுத் திட்டம்", "rain": "மழை எச்சரிக்கை"}
COMMENT = {      # owner 28 Nov (idea 6): the first comment asks the question people of that kind of news answer
    "power_cut": "உங்கள் பகுதியிலும் மின்தடையா? பகுதி பெயரை கமெண்டில் சொல்லுங்க 👇",
    "accident": "இந்த சாலையில் வேகத்தடை / எச்சரிக்கை பலகை வேண்டுமா? உங்கள் கருத்தை சொல்லுங்க 👇",
    "crime": "உங்கள் பகுதியிலும் இதுபோல் நடந்ததா? கமெண்டில் சொல்லுங்க 👇",
    "jobs": "யாருக்கு இந்த வேலை தேவைப்படும்? அவர்களை டேக் செய்யுங்க 👇",
    "weather": "உங்கள் ஊரில் இப்போது மழையா? ஊர் பெயரை சொல்லுங்க 👇",
    "temple": "நீங்கள் இந்த கோவிலுக்கு சென்றிருக்கிறீர்களா? 👇",
    "civic": "உங்கள் பகுதியில் இதுபோல் பிரச்சனை உள்ளதா? கமெண்டில் சொல்லுங்க 👇",
    "education": "மாணவர்களுக்கு பயன்படும் - பகிருங்கள், டேக் செய்யுங்க 👇",
    "politics": "இதைப் பற்றி உங்கள் கருத்து என்ன? 👇",
    "poultry_agri": "விவசாயிகளுக்கு பயன்படும் - அவர்களுக்கு பகிருங்கள் 👇",
    "sports_culture": "உங்கள் வாழ்த்துகளை கமெண்டில் சொல்லுங்க 👇",
    "other": "இந்த செய்தி பற்றி உங்கள் கருத்து? கமெண்டில் சொல்லுங்க 👇",
}


def log(*a):
    print(*a, flush=True)


def ff(*args):
    subprocess.run([gold_reel.ffmpeg(), "-y", "-loglevel", "error", *map(str, args)], check=True)


def clean(s):
    return re.sub(r"<[^>]+>", "", str(s or "")).strip()


def story(sid):
    t = json.loads((ROOT / "poster" / "prebuilt" / f"{sid}_trichy_text.json").read_text(encoding="utf-8"))
    spec = json.loads(t["slides_spec"]) if isinstance(t.get("slides_spec"), str) else (t.get("slides_spec") or {})
    script = re.split(r"\s*மேலும் செய்திகளுக்கு", t["reel_script"])[0].strip()
    return {"id": sid, "head": t["headline_ta"], "script": script, "spec": spec, "loc": spec.get("loc") or "", "cat": spec.get("cat") or ""}


# ---------------------------------------------------------------- (4) living pictures

def depth_map(img):
    """a depth map 0 (far) .. 1 (near) from the free Depth-Anything-V2-small model (ONNX, CPU); a top-far / bottom-near ramp when
    the model cannot be loaded"""
    import cv2
    h, w = img.shape[:2]
    try:
        import onnxruntime as ort
        mp = OUT / "depth.onnx"
        if not mp.exists():
            r = requests.get("https://huggingface.co/onnx-community/depth-anything-v2-small/resolve/main/onnx/model.onnx", timeout=300)
            r.raise_for_status()
            mp.write_bytes(r.content)
        s = ort.InferenceSession(str(mp), providers=["CPUExecutionProvider"])
        x = cv2.resize(cv2.cvtColor(img, cv2.COLOR_BGR2RGB), (518, 518)).astype(np.float32) / 255
        x = ((x - [0.485, 0.456, 0.406]) / [0.229, 0.224, 0.225]).transpose(2, 0, 1)[None].astype(np.float32)
        d = s.run(None, {s.get_inputs()[0].name: x})[0]
        d = np.squeeze(d).astype(np.float32)
        d = cv2.resize(d, (w, h))
        d = (d - d.min()) / ((d.max() - d.min()) or 1)
        log("depth: model")
        return cv2.GaussianBlur(d, (0, 0), 6)
    except Exception as e:
        log("depth: ramp (model not used):", str(e)[:120])
        return np.tile(np.linspace(0.1, 0.9, h, dtype=np.float32)[:, None], (1, w))


def living_frames(jpg, out_dir, seed):
    """MOVE_FRAMES frames of a slow 3D camera move: near things move more than far things"""
    import cv2
    img = cv2.imread(str(jpg))
    img = cv2.resize(img, (W, H)) if img.shape[:2] != (H, W) else img
    d = depth_map(img)
    gy, gx = np.mgrid[0:H, 0:W].astype(np.float32)
    rng = np.random.default_rng(seed)
    dx, dy = rng.choice([-1, 1]) * 34.0, rng.choice([-1, 1]) * 16.0
    out_dir.mkdir(parents=True, exist_ok=True)
    for f in range(MOVE_FRAMES):
        u = f / (MOVE_FRAMES - 1) - 0.5
        z = 1.07 + 0.04 * (f / (MOVE_FRAMES - 1))      # zoomed in a little: no empty edge
        mx = (gx - W / 2) / z + W / 2 - dx * u * (d - 0.35)
        my = (gy - H / 2) / z + H / 2 - dy * u * (d - 0.35)
        cv2.imwrite(str(out_dir / f"f{f:03d}.jpg"), cv2.remap(img, mx.astype(np.float32), my.astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT),
                    [cv2.IMWRITE_JPEG_QUALITY, 88])
    return [str((out_dir / f"f{f:03d}.jpg").resolve()) for f in range(MOVE_FRAMES)]


# ---------------------------------------------------------------- the voice with its word clock

def voice(text, work):
    mp3, wjs, raw = work / "voice.mp3", work / "voice.words.json", work / "voice.raw"
    subprocess.run([sys.executable, str(ROOT / "reel" / "edge_words.py"), *VOICE, text, str(mp3), str(wjs)], check=True, timeout=180)
    ff("-i", mp3, "-ac", "1", "-ar", SR, "-f", "s16le", raw)
    a = np.frombuffer(raw.read_bytes(), dtype=np.int16).astype(np.float32) / 32768
    words = json.loads(wjs.read_text(encoding="utf-8"))["words"]
    return a, words


def siren():
    t = np.arange(int(1.4 * SR)) / SR
    f = np.where((t * 2.5) % 1 < 0.5, 960, 720)
    return (0.09 * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.minimum(1, (1.4 - t) * 3)).astype(np.float32)


def whoosh():
    n = int(0.28 * SR)
    noise = np.random.default_rng(3).standard_normal(n)
    env = np.sin(np.linspace(0, np.pi, n)) ** 2
    sm = np.convolve(noise, np.ones(40) / 40, mode="same")
    return (0.05 * sm * env / (np.abs(sm).max() or 1)).astype(np.float32)


# ---------------------------------------------------------------- the page

def type_layer(kind, s):
    slides = s["spec"].get("slides") or []
    lines = lambda k: [clean(x) for sl in slides if k in str(sl.get("title", "")) for x in sl.get("lines", [])]
    if kind == "breaking":
        return f'<div id="brk"><i></i>BREAKING<span>{E(s["cat"] or TYPE_LABEL[kind])}</span></div><div id="redglow"></div>'
    if kind == "power":
        when = lines("எப்போது") or [clean(s["spec"].get("hl2"))]
        areas = lines("பகுதி")[:4]
        rows = "".join(f"<li>{E(a)}</li>" for a in areas)
        return (f'<div id="board"><div class="bt">⚡ மின் தடை அறிவிப்பு</div><div class="bw">{E(" • ".join(when[:2]))}</div>'
                f'<div class="bar"><b></b></div><ul>{rows}</ul></div>')
    if kind == "scheme":
        allx = [clean(x) for sl in slides for x in sl.get("lines", [])]
        gain = next((x for x in allx if re.search(r"ரூ|₹|இலவச|மானிய|உதவி", x)), clean(s["spec"].get("hl2")))
        last = next((x for x in allx if re.search(r"கடைசி|வரை|தேதி", x)), "")
        last = re.sub(r"^\s*(விண்ணப்பிக்க\s*)?கடைசி\s*நாள்\s*[:：-]?\s*", "", last)      # the label says it already
        how = lines("எப்படி")[:3]      # numbered steps ONLY from the 'how to apply' card (owner 28 Nov: never number who is NOT eligible)
        st = "".join(f'<div class="st"><b>{i + 1}</b>{E(x)}</div>' for i, x in enumerate(how))
        if how:
            st = '<div class="sh">எப்படி விண்ணப்பிப்பது?</div>' + st
        return (f'<div id="sch"><div class="c1"><small>பயன்</small>{E(gain)}</div>'
                + (f'<div class="c2"><small>கடைசி நாள்</small>{E(last)}</div>' if last else "") + f'<div class="steps">{st}</div></div>')
    if kind == "rain":
        return f'<canvas id="rain" width="{W}" height="{H}"></canvas><div id="alert">⚠ மழை எச்சரிக்கை • {E(s["loc"].split(",")[0])}</div>'
    return ""


def page(s, kind, frames, segs, words, dur, end_t, town_xy, number):
    logo = f"file://{Path(PAGE['logo']).resolve()}"
    m = json.loads((ROOT / "reel" / "assets" / "district_map.json").read_text(encoding="utf-8"))
    place_words = [w for w in re.split(r"[\s,]+", s["loc"])      # place names only - never "near" / "area" / "district"
                   if len(w) > 2 and not re.match(r"(மாவட்ட|அருகே|அருகில்|பகுதி|மாநகர|நகர)", w)]
    mapcard = ""
    if town_xy:
        tx, ty = town_xy[1]
        mapcard = (f'<div id="mapc"><svg viewBox="0 0 260 260"><path d="{m["path"]}"/><circle class="r" cx="{tx}" cy="{ty}" r="10"/>'
                   f'<circle class="p" cx="{tx}" cy="{ty}" r="6"/></svg><b>📍 {E(town_xy[0])}</b></div>').replace("📍 ", "")
    num = f'<div id="num"><b>{E(number[0])}</b><span>{E(number[1])}</span></div>' if number else ""
    hl1, hl2 = clean(s["spec"].get("hl1") or s["head"]), clean(s["spec"].get("hl2"))
    css = f"""
body{{margin:0;width:{W}px;height:{H}px;overflow:hidden;background:#000;font-family:'Noto Sans Tamil',sans-serif}}
#bg{{position:absolute;left:0;top:0;width:{W}px;height:{H}px;object-fit:cover;transform-origin:50% 45%}}
#shade{{position:absolute;inset:0;background:linear-gradient(180deg,rgba(0,0,0,.55) 0%,rgba(0,0,0,0) 28%,rgba(0,0,0,0) 52%,rgba(0,0,0,.78) 100%)}}
.band{{position:absolute;left:0;right:0;top:0;height:150px;display:flex;align-items:center;gap:20px;padding:0 36px;z-index:8;
 background:linear-gradient(180deg,{MAROON2},{MAROON})}}
.band img{{width:104px;height:104px;border-radius:50%;background:#fff;box-shadow:0 0 0 5px {GOLD}}}
.band b{{color:#fff;font-size:48px;font-weight:900}} .band b i{{font-style:normal;color:{GOLD};font-family:'Catamaran'}}
.band span{{margin-left:auto;background:{GOLD};color:{MAROON};border-radius:30px;padding:4px 22px;font-size:30px;font-weight:900}}
#hook{{position:absolute;left:44px;right:44px;top:250px;z-index:6;text-align:left}}
#hook .h1{{display:inline;background:#fff;color:#111;font-size:76px;font-weight:900;line-height:1.42;padding:4px 16px;
 box-decoration-break:clone;-webkit-box-decoration-break:clone}}
#hook .h2{{display:inline-block;margin-top:18px;background:{GOLD};color:{MAROON};font-size:50px;font-weight:900;padding:4px 18px;border-radius:8px}}
#cap{{position:absolute;left:40px;right:40px;bottom:250px;z-index:7;text-align:center;font-size:86px;font-weight:900;line-height:1.25;color:#fff;
 text-shadow:0 0 6px #000,0 6px 18px rgba(0,0,0,.9),3px 3px 0 #000,-3px -3px 0 #000,3px -3px 0 #000,-3px 3px 0 #000}}
#cap .w{{display:inline-block;margin:0 10px}} #cap .w.on{{color:#FFE14D;transform:scale(1.12)}} #cap .w.num{{color:#5BF08A}}
#cap .w.pl{{color:#6FD3FF}}
#mapc{{position:absolute;right:40px;top:262px;width:360px;z-index:6;background:rgba(10,10,20,.78);border-radius:26px;padding:16px;
 box-shadow:0 14px 34px rgba(0,0,0,.5),0 0 0 4px {GOLD};text-align:center;opacity:0}}
#mapc svg{{width:328px;height:328px}} #mapc path{{fill:rgba(233,178,51,.25);stroke:{GOLD};stroke-width:2}}
#mapc .p{{fill:#FF3B30;stroke:#fff;stroke-width:2}} #mapc .r{{fill:none;stroke:#FF3B30;stroke-width:2}}
#mapc b{{display:block;color:#fff;font-size:44px;font-weight:900}}
#num{{position:absolute;left:0;right:0;top:640px;z-index:6;text-align:center;opacity:0}}
#num b{{display:block;font-family:'Catamaran';font-size:300px;font-weight:900;line-height:1;color:#fff;text-shadow:0 10px 40px rgba(0,0,0,.8)}}
#num span{{display:inline-block;background:#E53935;color:#fff;font-size:62px;font-weight:900;padding:6px 30px;border-radius:14px}}
#brk{{position:absolute;left:0;right:0;top:150px;height:84px;z-index:7;background:#D32F2F;color:#fff;font-family:'Catamaran';font-size:52px;
 font-weight:900;letter-spacing:3px;display:flex;align-items:center;gap:20px;padding:0 36px}}
#brk i{{width:26px;height:26px;border-radius:50%;background:#fff}} #brk span{{font-family:'Noto Sans Tamil';letter-spacing:0;font-size:40px;opacity:.95}}
#redglow{{position:absolute;inset:0;z-index:5;box-shadow:inset 0 0 160px 40px rgba(255,0,0,.75);opacity:0}}
#board{{position:absolute;left:40px;right:40px;top:560px;z-index:6;background:linear-gradient(160deg,#0E3B2E,#062118);border-radius:24px;
 padding:24px 30px;color:#fff;box-shadow:0 18px 40px rgba(0,0,0,.6),inset 0 0 0 5px #F5C518;opacity:0}}
#board .bt{{font-size:54px;font-weight:900;color:#F5C518}} #board .bw{{margin-top:8px;font-size:40px;font-weight:800}}
#board .bar{{margin-top:16px;height:22px;border-radius:12px;background:rgba(255,255,255,.18);overflow:hidden}}
#board .bar b{{display:block;height:100%;width:0;background:linear-gradient(90deg,#F5C518,#FF7043)}}
#board ul{{margin:16px 0 0;padding-left:40px;font-size:38px;font-weight:800;line-height:1.45}}
#sch{{position:absolute;left:40px;right:40px;top:560px;z-index:6}}
#sch .c1,#sch .c2{{background:#fff;border-radius:22px;padding:16px 26px;margin-bottom:18px;font-size:50px;font-weight:900;color:{MAROON};
 box-shadow:0 14px 30px rgba(0,0,0,.5);opacity:0}}
#sch .c2{{background:#FFE14D}} #sch small{{display:block;font-size:30px;font-weight:800;opacity:.7}}
#sch .st{{display:flex;gap:16px;align-items:center;background:rgba(0,0,0,.72);color:#fff;border-radius:18px;padding:12px 20px;margin-bottom:12px;
 font-size:38px;font-weight:800;opacity:0}}
#sch .sh{{display:inline-block;background:{MAROON};color:{GOLD};border-radius:14px;padding:6px 20px;margin-bottom:12px;font-size:36px;font-weight:900;opacity:0}}
#sch .st b{{flex:none;width:58px;height:58px;border-radius:50%;background:{GOLD};color:{MAROON};text-align:center;line-height:58px;font-size:36px}}
#rain{{position:absolute;inset:0;z-index:4;pointer-events:none}}
#alert{{position:absolute;left:0;right:0;top:150px;height:84px;z-index:7;background:#F9A825;color:#1A1A1A;font-size:44px;font-weight:900;
 display:flex;align-items:center;justify-content:center}}
#end{{position:absolute;inset:0;z-index:9;background:radial-gradient(circle at 50% 40%,#FFFBEA,#FCEBB8);text-align:center;padding-top:520px;opacity:0}}
#end img{{width:300px;height:300px;border-radius:50%;box-shadow:0 0 0 10px {GOLD}}}
#end .n{{margin-top:30px;color:{MAROON};font-size:96px;font-weight:900}} #end .n i{{font-style:normal;color:{GOLD};font-family:'Catamaran'}}
#end .f{{display:inline-block;margin-top:30px;background:{MAROON};color:{GOLD};border-radius:50px;padding:14px 46px;font-size:52px;
 font-weight:900;font-family:'Catamaran'}}
"""
    data = {"segs": segs, "words": words, "frames": frames, "dur": dur, "end": end_t, "kind": kind, "place": place_words,
            "hasMap": bool(town_xy), "hasNum": bool(number)}
    js = ("const D=" + json.dumps(data, ensure_ascii=False) + ";window.DUR=D.dur;window.COVER_T=0.4;" + """
const BG=document.getElementById('bg'),CAP=document.getElementById('cap'),HK=document.getElementById('hook'),MC=document.getElementById('mapc'),
 NUM=document.getElementById('num'),END=document.getElementById('end'),RG=document.getElementById('redglow'),BRK=document.getElementById('brk'),
 BOARD=document.getElementById('board'),RAIN=document.getElementById('rain');
const cl=u=>Math.max(0,Math.min(1,u)),ez=u=>{u=cl(u);return 1-Math.pow(1-u,3)},pop=u=>{u=cl(u);const c=1.70158;return 1+(c+1)*Math.pow(u-1,3)+c*Math.pow(u-1,2)};
const groups=[];{let g=[];D.words.forEach((w,i)=>{g.push(i);if(g.length>=3||/[.,?!]$/.test(w[0])||i===D.words.length-1){groups.push(g);g=[]}})}
const isNum=w=>/\\d/.test(w),isPl=w=>D.place.some(p=>w.indexOf(p.slice(0,4))===0);
window.seek=async function(t){
 const sh=D.segs.findIndex(s=>t>=s.t0&&t<s.t1),s=D.segs[sh<0?D.segs.length-1:sh],u=t-s.t0,d=s.t1-s.t0;
 const fr=D.frames[s.img],src=fr[Math.min(fr.length-1,Math.floor(cl(u/d)*(fr.length-1)))];
 if(BG.getAttribute('src')!==src){BG.setAttribute('src',src);try{await BG.decode()}catch(e){}}
 BG.style.transform='scale('+(s.z+0.03*ez(u/d))+') translate('+s.x+'px,'+s.y+'px)';
 HK.style.opacity=t<D.segs[0].t1?1:cl(1-(t-D.segs[0].t1)/0.25);HK.style.transform='scale('+(t<0.35?pop(t/0.35):1)+')';
 if(MC){const a=D.segs[1]?D.segs[1].t0:9;MC.style.opacity=t>=a&&t<a+2.4?ez((t-a)/0.25)*cl((a+2.4-t)/0.25):0;
  MC.querySelector('.r').setAttribute('r',8+18*(((t-a)%0.8)/0.8))}
 if(NUM){const a=D.segs[2]?D.segs[2].t0:9;NUM.style.opacity=t>=a&&t<a+2.0?cl((a+2.0-t)/0.2):0;NUM.style.transform='scale('+(0.5+0.5*pop((t-a)/0.35))+')'}
 if(RG){RG.style.opacity=t<1.6?0.5+0.5*Math.sin(t*12):0;BRK.querySelector('i').style.opacity=(Math.floor(t*3)%2)?1:0.2}
 if(BOARD){const a=D.segs[0].t1;BOARD.style.opacity=t>a&&t<D.end?ez((t-a)/0.3):0;BOARD.querySelector('.bar b').style.width=(100*cl((t-a)/(D.end-a)))+'%';
  BOARD.style.transform='translateY('+(40*(1-ez((t-a)/0.3)))+'px)'}
 if(D.kind==='scheme'){const a=D.segs[0].t1;[...document.querySelectorAll('#sch .c1,#sch .c2,#sch .sh,#sch .st')].forEach((e,i)=>{const b=a+i*0.9;
  e.style.opacity=t>b&&t<D.end?ez((t-b)/0.3):0;e.style.transform='translateX('+(-60*(1-ez((t-b)/0.3)))+'px)'})}
 if(RAIN){const c=RAIN.getContext('2d');c.clearRect(0,0,1080,1920);c.strokeStyle='rgba(200,220,255,.55)';c.lineWidth=3;
  for(let i=0;i<220;i++){const x=(i*97.3)%1080,sp=1400+(i%7)*160,y=((i*233.1)+t*sp)%2100-100;c.beginPath();c.moveTo(x,y);c.lineTo(x-14,y+46);c.stroke()}}
 const wi=D.words.findIndex(w=>t>=w[1]&&t<w[2]+0.12),gi=groups.findIndex(g=>g.includes(wi));
 if(gi>=0&&t<D.end){CAP.innerHTML=groups[gi].map(i=>{const w=D.words[i][0];return '<span class="w'+(i===wi?' on':'')+(isNum(w)?' num':isPl(w)?' pl':'')+'">'+w+'</span>'}).join(' ')}
 else if(t>=D.end||wi<0&&!groups.some(g=>D.words[g[0]][1]-0.05<=t&&t<=D.words[g[g.length-1]][2]+0.3))CAP.innerHTML='';
 END.style.opacity=t>=D.end?ez((t-D.end)/0.3):0;
};""")
    band = (f'<div class="band"><img src="{logo}"><b>{G.brand_html(PAGE)}</b>' + (f'<span>{E(TYPE_LABEL[kind])}</span>' if kind in ("power", "scheme") else "") + '</div>')
    body = (f'<img id="bg" src="{frames[0][0]}"><div id="shade"></div>{type_layer(kind, s)}{band}'
            f'<div id="hook"><span class="h1">{E(hl1)}</span>' + (f'<br><span class="h2">{E(hl2)}</span>' if hl2 else "") + '</div>'
            f'{mapcard}{num}<div id="cap"></div>'
            f'<div id="end"><img src="{logo}"><div class="n">{G.brand_html(PAGE)}</div><div class="f">Follow @{PAGE["handle"]}</div></div>')
    return G.themed(f'<!doctype html><html><head><meta charset="utf-8"><style>{G.css()}{css}</style></head><body>{body}'
                    f'<script>{js}</script></body></html>', PAGE)


def record(html_path, dur, mp4, audio, stills=()):
    from playwright.sync_api import sync_playwright
    cmd = [gold_reel.ffmpeg(), "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-c:v", "mjpeg", "-i", "-",
           "-i", str(audio), "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
           "-ar", "44100", "-shortest", "-movflags", "+faststart", str(mp4)]
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": W, "height": H})
        pg.goto(f"file://{Path(html_path).resolve()}")
        pg.evaluate("document.fonts.ready.then(() => 1)")
        pg.wait_for_timeout(800)
        for k, t in enumerate(stills):
            pg.evaluate(f"window.seek({t:.3f})")
            pg.screenshot(path=str(Path(mp4).with_name(f"{Path(mp4).stem}_still{k}.png")))
        enc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        try:
            for i in range(int(round(dur * FPS))):
                pg.evaluate(f"window.seek({i / FPS:.4f})")
                enc.stdin.write(pg.screenshot(type="jpeg", quality=90))
        finally:
            enc.stdin.close()
            enc.wait()
        b.close()
    if enc.returncode:
        raise RuntimeError(f"ffmpeg failed for {mp4}")


def make_news(item):
    import imagegen
    s = story(item["id"])
    kind = item["kind"]
    work = OUT / "news" / f"{item['id']}_{kind}"
    work.mkdir(parents=True, exist_ok=True)
    frames = []
    for k, prompt in enumerate(item["prompts"]):
        jpg = work / f"pic{k}.jpg"
        if not jpg.exists():
            jpg.write_bytes(imagegen.generate(prompt, seed=17 + k, free_only=True))      # free picture services only
        frames.append(living_frames(jpg, work / f"live{k}", 5 + k))
    a, words = voice(s["script"], work)
    lead = 0.3
    words = [[w, round(st + lead, 3), round(en + lead, 3)] for w, st, en in words]
    end_t = round(lead + len(a) / SR + 0.4, 2)
    dur = round(end_t + 2.2, 2)
    segs, t, k = [], 0.0, 0
    variants = [(1.0, 0, 0), (1.16, -50, -30), (1.1, 45, 25), (1.22, 0, -60), (1.08, -30, 40)]
    while t < end_t:
        d = 2.8 if k == 0 else SHOT_S
        z, x, y = variants[k % len(variants)]
        segs.append({"t0": round(t, 2), "t1": round(min(end_t, t + d), 2), "img": k % 2, "z": z, "x": x, "y": y})
        t += d
        k += 1
    segs.append({"t0": end_t, "t1": dur, "img": 0, "z": 1.0, "x": 0, "y": 0})
    m = json.loads((ROOT / "reel" / "assets" / "district_map.json").read_text(encoding="utf-8"))
    import mapintro
    town = mapintro.town_of(s["loc"], m["towns"]) or next((tn for tn in sorted(m["towns"], key=len, reverse=True) if tn in s["loc"]), "")
    town_xy = (town, m["towns"][town]) if town else None
    nm = re.search(r"(\d[\d,.]*)\s*(பேர்[^\s]*|லட்ச\w*|கோடி|ரூபாய்|ஏக்கர்|டன்|கிலோ)", clean(s["spec"].get("hl1")) + " " + s["head"] + " " + clean(s["spec"].get("hl2")))      # a count, never a time (owner 28 Nov: '3 மணி' is not a counter)
    number = (nm.group(1), nm.group(2)) if nm else None
    track = np.zeros(int(dur * SR) + SR, dtype=np.float32)
    i0 = int(lead * SR)
    track[i0:i0 + len(a)] += a
    if kind == "breaking":
        sr_ = siren()
        track[:len(sr_)] += sr_
    wh = whoosh()
    for sg in segs[1:-1]:
        i = int(sg["t0"] * SR)
        track[i:i + len(wh)] += wh[:max(0, len(track) - i)]
    track = track[:int(dur * SR)]
    vwav, mwav, awav = work / "voice.wav", work / "music.wav", work / "audio.wav"
    RP.write_wav(vwav, track)
    music = gold_reel.soundtrack(dur, mwav, log)
    if music:
        ff("-i", vwav, "-i", music, "-filter_complex", "[1:a]volume=0.12[m];[0:a][m]amix=inputs=2:duration=first:normalize=0[a]",
           "-map", "[a]", "-ar", "44100", awav)
    html = work / "news.html"
    html.write_text(page(s, kind, frames, segs, words, dur, end_t, town_xy, number), encoding="utf-8")
    mp4 = OUT / "news" / f"{item['id']}_{kind}.mp4"
    record(html, dur, mp4, awav if music else vwav, stills=(0.5, segs[1]["t0"] + 1.0, segs[2]["t0"] + 0.8, end_t * 0.6, end_t - 1.0))
    log(f"news sample {mp4.name}: {dur:.1f} s, {kind}, town {town or '-'}, number {number}")


# ---------------------------------------------------------------- (5) the morning bulletin, (6) first comments

def recent_posts(hours):
    sys.path.insert(0, str(ROOT / "poster"))
    hist = {}
    try:
        hist = json.loads((ROOT / "poster" / "insights" / "history.json").read_text(encoding="utf-8"))
    except Exception:
        pass
    since = datetime.now(IST) - timedelta(hours=hours)
    out = []
    for f in sorted((ROOT / "poster" / "posted").glob("*-trichy-*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            at = datetime.fromisoformat(d["at"]).astimezone(IST)
            if at < since or re.search(r"rasipalan|gold", str(d.get("story")), re.I):
                continue
            pre = json.loads((ROOT / "poster" / "prebuilt" / f"{d['story']}.json").read_text(encoding="utf-8"))
        except Exception:
            continue
        head = re.sub(r"^[^஀-௿A-Za-z0-9]+", "", str(d.get("headline") or "")).strip()
        if head and pre.get("cover"):
            out.append({"story": d["story"], "head": head, "at": at, "cover": pre["cover"],
                        "views": int((hist.get(str(d.get("media_id"))) or {}).get("views") or 0)})
    return out


def make_morning():
    import learned
    import top5
    posts = recent_posts(16)
    pc = re.compile(r"மின்\s*தடை|மின்தடை")
    items = sorted(posts, key=lambda x: (bool(pc.search(x["head"])), learned.boost(x["head"]), x["at"]), reverse=True)[:5]
    if len(items) < 5:
        raise SystemExit(f"morning: only {len(items)} news")
    out = OUT / "morning"
    work = out / "voice"
    work.mkdir(parents=True, exist_ok=True)
    for i, x in enumerate(items):
        r = requests.get(x["cover"], timeout=120)
        r.raise_for_status()
        (work / f"c{i}.jpg").write_bytes(r.content)
        x["img"] = str((work / f"c{i}.jpg").resolve())
    nums = ["ஒன்று", "இரண்டு", "மூன்று", "நான்கு", "ஐந்து"]
    texts = ["காலை வணக்கம்! அறுபது வினாடியில் திருச்சியின் ஐந்து முக்கிய செய்திகள்."]
    texts += [f"{nums[i]}. {top5.say_head(x['head'])}." for i, x in enumerate(items)]
    texts += ["முழு செய்திகளுக்கு திருச்சி த்ரீ சிக்ஸ்டி பக்கத்தை ஃபாலோ பண்ணுங்க."]
    voices = [RP.say(t, work, n, log) for n, t in enumerate(texts)]
    segs, t = [], 0.0
    for n, a in enumerate(voices):
        lead = 0.3 if n else 0.15
        segs.append({"t0": round(t, 2), "v0": round(t + lead, 2), "t1": round(t + max(3.0, lead + len(a) / SR + 0.45), 2)})
        t = segs[-1]["t1"]
    dur = t
    vwav, mwav, awav = out / "voice.wav", out / "music.wav", out / "audio.wav"
    RP.write_wav(vwav, RP.voice_track(voices, segs, dur))
    music = gold_reel.soundtrack(dur, mwav, log)
    if music:
        ff("-i", vwav, "-i", music, "-filter_complex", f"[1:a]volume={RP.MUSIC_VOL}[m];[0:a][m]amix=inputs=2:duration=first:normalize=0[a]",
           "-map", "[a]", "-ar", "44100", awav)
    html = top5.page_html(PAGE, items, segs, dur)
    ranks = iter(range(1, 6))
    html = re.sub(r'<div class="rk">#\d</div>', lambda _m: f'<div class="rk">#{next(ranks)}</div>', html)
    thumbs = iter(range(1, 6))
    html = re.sub(r'(<div class="th"><img src="[^"]+">)<b>\d</b>', lambda mm: f"{mm.group(1)}<b>{next(thumbs)}</b>", html)
    cur = iter(range(1, 6))

    def dots(_m):
        n = next(cur)
        return '<div class="dots">' + "".join(f'<b class="{"on" if r == n else "done" if r < n else ""}">{r}</b>' for r in range(1, 6)) + "</div>"
    html = re.sub(r'<div class="dots">.*?</div>', dots, html)
    html = (html.replace("இன்றைய<br>டாப் 5", "காலை<br>5 செய்திகள்").replace("இன்று அதிகம் பார்த்த செய்திகள்", "60 வினாடியில் முக்கிய செய்திகள்")
            .replace("இன்றைய டாப் 5 •", "காலை செய்திகள் •").replace("தினமும் இரவு இன்றைய டாப் 5", "தினமும் காலை 7:30 • 5 செய்திகள்"))
    hp = out / "morning.html"
    hp.write_text(html, encoding="utf-8")
    record(hp, dur, out / "morning_bulletin.mp4", awav if music else vwav, stills=(0.3, segs[1]["t0"] + 1.0, segs[3]["t0"] + 1.0))
    log(f"morning sample: {dur:.1f} s - " + " | ".join(x["story"] for x in items))


MEANING = [      # owner 28 Nov (review): what the news IS about decides the question - checked before the topic word
    ("court", r"நீதிமன்ற|ஐகோர்ட்|உயர் நீதிமன்ற|தீர்ப்பு|வழக்கு", "இந்த தீர்ப்பு / வழக்கு பற்றி உங்கள் கருத்து என்ன? 👇"),
    ("scheme", r"விண்ணப்ப|இலவச|மானியம்|உதவித்தொகை|திட்டம்|முகாம்", "யாருக்கு இது பயன்படும்? அவர்களை டேக் செய்யுங்க 👇"),
    ("ban", r"தடை(?!\s*செய்)|மூடல்|மூடப்ப|அனுமதி இல்லை", "இந்த அறிவிப்பு பற்றி உங்கள் கருத்து? நண்பர்களுக்கு தெரியப்படுத்துங்க 👇"),
    ("power_cut", r"மின்\s*தடை|மின்தடை", COMMENT["power_cut"]),
    ("rain", r"மழை|வெள்ளம்|புயல்", COMMENT["weather"]),
    ("accident", r"விபத்து|மோதி|கவிழ்ந்து|பலி|உயிரிழ", COMMENT["accident"]),
    ("traffic", r"ரயில்|பஸ்|சாலை|போக்குவரத்து|தாமத", "இந்த வழியில் நீங்களும் பயணிக்கிறீர்களா? உங்கள் அனுபவம் 👇"),
]


def comment_for(head):
    import learned
    for name, rx, text in MEANING:
        if name == "power_cut" and re.search(rx, head):
            return name, text      # a power cut notice: the area question, even with "தடை"
    for name, rx, text in MEANING:
        if re.search(rx, head):
            return name, text
    tp = learned.topic(head)
    return tp, COMMENT.get(tp, COMMENT["other"])


def make_comments():
    out = OUT / "comments"
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for x in recent_posts(30)[-15:]:
        tp, text = comment_for(x["head"])
        rows.append(f"{x['story']} [{tp}] {x['head']}\n   → {text}")
    (out / "first_comments.txt").write_text("\n\n".join(rows), encoding="utf-8")
    log(f"comments sample: {len(rows)} news")


def main():
    what = sys.argv[1] if len(sys.argv) > 1 else "news"
    OUT.mkdir(parents=True, exist_ok=True)
    if what == "news":
        only = sys.argv[2] if len(sys.argv) > 2 else ""
        for item in [x for x in STORIES if not only or x["id"] == only]:
            try:
                make_news(item)
            except Exception as e:
                import traceback
                traceback.print_exc()
                log(f"news sample {item['id']} failed: {e}")
    elif what == "morning":
        make_morning()
    else:
        make_comments()


if __name__ == "__main__":
    main()
