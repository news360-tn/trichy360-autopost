"""கோயம்புத்தூர் 360 — photo carousel renderer (v3).
Usage: python3 render_photo.py spec.json images_dir out_dir [--ai-label] [--page coimbatore]

spec (v3):
 {"v":3,"story":"RN-26","date":"20 அக்டோபர் 2026","cat":"மழை","loc":"கோவை",
  "hl1":"கோவையில் கனமழை","hl2":"அடுத்த 5 நாட்கள் தொடரும்",
  "slides":[{"title":"என்ன நடந்தது","lines":["...","...","..."]}, ...]}
images_dir holds img1.jpg, img2.jpg ... (img1 = cover, img2.. = detail slides, in order).
Output: <story>_slide1_cover.png ... + the follow slide last. The logo is added afterwards (overlay_logo_v2.py).
"""
import os, json, re, sys, html
from pathlib import Path
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import render_v2 as R2  # fonts, icons, the follow slide

E = html.escape

CSS = R2.CSS + """
html,body{width:1080px;height:1350px}
.photo{position:absolute;background-size:cover;background-position:center 40%;background-repeat:no-repeat}
.full{inset:0}
.shade{position:absolute;inset:0;background:
  linear-gradient(180deg,rgba(6,18,50,.55) 0%,rgba(6,18,50,0) 22%,rgba(6,18,50,0) 38%,rgba(6,18,50,.88) 66%,#061232 100%)}
.top-img{left:0;right:0;top:0;height:1350px;background-position:center 30%}
.top-shade{position:absolute;left:0;right:0;top:0;height:1350px;background:linear-gradient(180deg,rgba(6,18,50,.55) 0%,rgba(6,18,50,0) 20%,rgba(6,18,50,0) 30%,rgba(6,18,50,.82) 47%,rgba(6,18,50,.95) 60%,#061232 100%)}
.cut,.panel{display:none}
.cat2{position:absolute;left:36px;top:420px;z-index:3;background:var(--red);color:#fff;font:800 40px 'BT','NST';padding:10px 30px 2px;border-radius:12px;transform:rotate(-2deg)}
.brush2{position:absolute;left:30px;top:520px;max-width:1010px;background:var(--yellow);color:var(--navy);padding:12px 36px 4px 30px;border-radius:10px;transform:rotate(-1deg);z-index:3}
.brush2 h2{font:800 66px/1.15 'BT','NST';white-space:nowrap}
.pts{position:absolute;left:36px;right:36px;top:650px;bottom:60px;display:flex;flex-direction:column;gap:18px;z-index:3;justify-content:flex-start}
.pt{display:flex;gap:20px;align-items:flex-start;background:rgba(255,255,255,.07);border:2px solid rgba(255,255,255,.14);border-radius:22px;padding:16px 24px 12px}
.pt .dot{flex:0 0 58px;height:58px;border-radius:50%;background:var(--yellow);color:#061232;font:900 40px/58px 'CT';text-align:center;margin-top:8px;padding-top:4px}
.pt .tx{font:700 46px/1.38 'NST','CT';color:#fff}
.pt .tx b{color:var(--yellow)}
.cover-cat{position:absolute;left:40px;top:640px;z-index:3;background:var(--red);color:#fff;font:800 52px 'BT','NST';padding:12px 40px 2px;clip-path:polygon(4% 0,100% 6%,96% 100%,0 92%);transform:rotate(-3deg)}
.cover-h1{position:absolute;left:40px;right:40px;top:740px;height:330px;z-index:3;font:800 104px/1.12 'BT','NST';color:#fff;text-shadow:0 6px 0 #061232,0 12px 26px rgba(0,0,0,.55);display:flex;align-items:center}
.cover-h2{position:absolute;left:40px;right:40px;top:1086px;z-index:3;font:800 76px/1.15 'BT','NST';color:var(--yellow);text-shadow:0 5px 0 #6b4700,0 10px 22px rgba(0,0,0,.5);white-space:nowrap}
.cover-loc{position:absolute;left:40px;right:40px;bottom:34px;z-index:3;display:flex;align-items:center;gap:14px;font:800 38px 'CT','NST';color:#fff;border-top:2px solid rgba(255,255,255,.35);padding-top:16px}
.cover-loc .ic{font-size:40px;color:var(--red)}
.ai{position:absolute;right:30px;bottom:34px;z-index:5;background:rgba(0,0,0,.55);color:#fff;font:700 24px 'NST','CT';padding:6px 16px 2px;border-radius:999px;border:1.5px solid rgba(255,255,255,.5)}
.ai.l{left:30px;right:auto}
.date{z-index:6}
"""

FIT = """
function fitBox(el,maxH,min){var s=parseFloat(getComputedStyle(el).fontSize);while(el.scrollHeight>maxH&&s>min){s-=2;el.style.fontSize=s+'px';}}
function fitW(el,max,min){var s=parseFloat(getComputedStyle(el).fontSize);while(el.scrollWidth>max&&s>min){s-=2;el.style.fontSize=s+'px';}}
document.fonts.ready.then(function(){
  var h=document.querySelector('.cover-h1'); if(h){fitBox(h,330,56);}
  var h2=document.querySelector('.cover-h2'); if(h2){fitW(h2,1000,36);}
  var b=document.querySelector('.brush2 h2'); if(b){fitW(b,940,34);}
  var pts=document.querySelector('.pts');
  if(pts){var lim=pts.clientHeight,t=null;
    document.querySelectorAll('.pt .tx').forEach(function(x){x.dataset.s=parseFloat(getComputedStyle(x).fontSize)});
    var size=46;while(pts.scrollHeight>lim&&size>26){size-=2;document.querySelectorAll('.pt .tx').forEach(function(x){x.style.fontSize=size+'px'});}}
  var bad=0;
  if(h&&h.scrollHeight>334)bad=1;
  if(h2&&h2.scrollWidth>1004)bad=1;
  if(b&&b.scrollWidth>944)bad=1;
  if(pts&&pts.scrollHeight>pts.clientHeight+2)bad=1;
  document.body.dataset.overflow=bad;
  document.body.dataset.ready='1';
});
"""

def uri(p):
    return "file://" + str(Path(p).resolve())

def cover_html(spec, img, ai):
    return f"""<div class="photo full" style="background-image:url('{uri(img)}')"></div><div class="shade"></div>
<div class="date"><i data-ic="calendar-days"></i>{E(spec['date'])}</div>
<div class="cover-cat">{E(spec.get('cat',''))}</div>
<div class="cover-h1">{E(spec['hl1'])}</div>
<div class="cover-h2">{E(spec.get('hl2',''))}</div>
<div class="cover-loc"><i data-ic="location-dot"></i>{E(spec.get('loc','கோவை'))}</div>
<div style="position:absolute;right:34px;bottom:34px;z-index:6;display:flex;align-items:center;gap:12px;background:#FFCC1F;color:#06132F;font:800 34px/1 'NST','CT',sans-serif;padding:16px 26px 12px;border-radius:999px;box-shadow:0 8px 24px rgba(0,0,0,.45)">முழு விவரம் <span style="display:inline-block;width:30px;height:30px"><i data-ic="arrow-right"></i></span></div>
{AI_CHIP if ai else ''}"""

def detail_html(spec, s, img, ai):
    pts = "".join(f'<div class="pt"><div class="dot">{n}</div><div class="tx">{l}</div></div>' for n, l in enumerate(s["lines"], 1))
    return f"""<div class="photo top-img" style="background-image:url('{uri(img)}')"></div><div class="top-shade"></div>
<div class="panel"></div><div class="cut"></div>
<div class="date"><i data-ic="calendar-days"></i>{E(spec['date'])}</div>
<div class="cat2">{E(spec.get('cat',''))}</div>
<div class="brush2"><h2>{E(s['title'])}</h2></div>
<div class="pts">{pts}</div>
{AI_CHIP if ai else ''}"""

AI_CHIP = '<div class="ai">AI பிரதிநிதித்துவப் படம்</div>'

def page(inner, light=False):
    inner = re.sub(r'<i data-ic="([a-z0-9-]+)"></i>', lambda m: R2.icon(m.group(1)), inner)
    return f"""<!doctype html><html lang="ta"><head><meta charset="utf-8"><style>{CSS}</style></head>
<body><div class="layer" style="z-index:1">{inner}</div><script>{FIT}</script></body></html>"""

def follow_slide(date):
    ex = json.loads((HERE / f"example_slides_{os.environ.get('PAGE_KEY', 'coimbatore')}.json").read_text())
    h = ex["slides"][-1]["html"]
    h = re.sub(r'(<i data-ic="calendar-days"></i>)[^<]+(</div>)', lambda m: m.group(1) + date + m.group(2), h, count=1)
    # shares and saves push a post further than likes: ask for them on the last slide
    h = h.replace('<i data-ic="bell"></i>', '<i data-ic="share-nodes"></i>')
    return h.replace("புதிய பதிவுகளுக்கு Notification-ஐ ON செய்யுங்கள்", "Save செய்யுங்கள் • தேவைப்படுவோருக்கு Share செய்யுங்கள்")

def shot(pg, path):
    """screenshot at 2x then downscale to 1080x1350: crisp text and photo edges"""
    from PIL import Image
    pg.screenshot(path=str(path), clip={"x": 0, "y": 0, "width": 1080, "height": 1350})
    im = Image.open(path).convert("RGB")
    if im.size != (1080, 1350):
        im = im.resize((1080, 1350), Image.LANCZOS)
    im.save(path)


def main(spec_path, images_dir, out_dir, ai=False):
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    imgs = sorted(Path(images_dir).glob("img*.jpg"), key=lambda p: int(re.search(r"(\d+)", p.stem).group(1)))
    n_detail = len(spec["slides"])
    if len(imgs) < 1 + min(n_detail, 1):
        raise SystemExit("not enough images")
    os.makedirs(out_dir, exist_ok=True)
    story = spec.get("story", "X")
    pages = [(f"{story}_slide1_cover.png", cover_html(spec, imgs[0], ai))]
    for k, s in enumerate(spec["slides"]):
        img = imgs[min(k + 1, len(imgs) - 1)]
        pages.append((f"{story}_slide{k + 2}_{k + 2}.png", detail_html(spec, s, img, ai)))
    clipped = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1080, "height": 1350}, device_scale_factor=2)
        for name, inner in pages:
            hp = (Path(out_dir) / (Path(name).stem + ".html")).resolve()
            hp.write_text(page(inner), encoding="utf-8")
            pg.goto("file://" + str(hp))
            pg.wait_for_function("document.body.dataset.ready === '1'", timeout=20000)
            pg.wait_for_timeout(250)
            if pg.evaluate("document.body.dataset.overflow") == "1":
                clipped.append(name)
            shot(pg, Path(out_dir) / name)
            print("rendered", name)
        name = f"{story}_slide{len(pages) + 1}_follow.png"
        fs = {"file": name, "html": follow_slide(spec["date"])}
        hp = (Path(out_dir) / (Path(name).stem + ".html")).resolve()
        hp.write_text(R2.render_page(fs, 0, 0), encoding="utf-8")
        pg.goto("file://" + str(hp))
        pg.wait_for_function("document.body.dataset.ready === '1'", timeout=20000)
        pg.wait_for_timeout(250)
        shot(pg, Path(out_dir) / name)
        print("rendered", name)
        b.close()
    if clipped:
        print("TEXT DOES NOT FIT on: " + ", ".join(clipped))
        sys.exit(3)

if __name__ == "__main__":
    a = sys.argv[1:]
    ai = "--ai-label" in a
    a = [x for x in a if not x.startswith("--")]
    main(a[0], a[1], a[2], ai)
