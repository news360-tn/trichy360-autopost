"""கோயம்புத்தூர் 360 — bold carousel renderer (v2).
Usage: python3 render_v2.py slides.json outdir
Needs (npm, in this folder): @fontsource/baloo-thambi-2 @fontsource/catamaran @fontsource/noto-sans-tamil @fortawesome/fontawesome-free
Icons: write <i data-ic="handcuffs"></i> in slide html (Font Awesome solid names).
Top-right 200x200 (30px margin) is kept clear for the official logo (overlay_logo_v2.py).
"""
import json, sys, os, re, html
from pathlib import Path
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
NM = HERE / "node_modules"
FS = NM / "@fontsource"
ICONS = NM / "@fortawesome" / "fontawesome-free" / "svgs" / "solid"

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
    svg = p.read_text()
    svg = re.sub(r"<!--.*?-->", "", svg, flags=re.S)
    return svg.replace("<svg ", '<svg class="ic" fill="currentColor" ', 1)

CSS = ff("BT", "baloo-thambi-2", [700, 800]) + ff("CT", "catamaran", [700, 800, 900]) + ff("NST", "noto-sans-tamil", [600, 700, 800]) + """
:root{--red:#E3151B;--red2:#B30F14;--navy:#0A1C46;--navy2:#13306E;--yellow:#FFCC1F;--white:#FFFFFF;--ink:#0A1C46;--grey:#4A5570;--paper:#F5F7FC}
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:1080px;height:1350px}
body{font-family:'CT','NST',sans-serif;color:var(--white);position:relative;overflow:hidden;background:var(--navy)}
.ic{width:1em;height:1em;display:block}
/* backgrounds */
.bg{position:absolute;inset:0;z-index:0;
  background:
   linear-gradient(160deg, rgba(255,255,255,.06) 0 30%, transparent 30%),
   radial-gradient(1100px 800px at 85% 0%, #1D3F8F 0%, transparent 60%),
   radial-gradient(900px 700px at 0% 100%, #0F2A63 0%, transparent 60%), var(--navy)}
.bg::after{content:"";position:absolute;inset:0;background-image:radial-gradient(rgba(255,255,255,.07) 2px, transparent 2px);background-size:26px 26px}
.slash{position:absolute;z-index:0;right:-120px;bottom:120px;width:520px;height:46px;background:var(--red);transform:rotate(-28deg);opacity:.9}
.slash.s2{bottom:60px;right:-160px;width:420px;height:20px;background:var(--yellow);opacity:.8}
.light .bg{background:linear-gradient(180deg,#E9EEF8 0%, #F7F9FD 40%, #FFFFFF 100%)}
.light .bg::after{background-image:radial-gradient(rgba(10,28,70,.06) 2px, transparent 2px)}
.layer{position:absolute;inset:0;z-index:1}
.logozone{position:absolute;top:30px;right:30px;width:200px;height:200px}
/* date chip */
.date{position:absolute;top:36px;left:40px;display:flex;align-items:center;gap:12px;background:var(--red);color:#fff;font:800 32px 'CT','NST';padding:10px 22px 8px;border-radius:14px;border:3px solid rgba(255,255,255,.85);box-shadow:0 6px 18px rgba(0,0,0,.25)}
.date .ic{font-size:30px}
/* brush title */
.brush{position:absolute;left:28px;top:120px;width:max-content;max-width:none;padding:18px 40px 10px 34px;background:var(--yellow);color:var(--navy);
  clip-path:polygon(2% 8%,10% 0,40% 6%,70% 0,98% 5%,100% 40%,97% 92%,70% 100%,35% 94%,8% 100%,0 70%);transform:rotate(-2deg)}
.brush h2{font:800 96px/1.05 'BT','NST';letter-spacing:-1px}
.brush.red{background:var(--red);color:#fff}
.underline{position:absolute;left:60px;top:268px;width:560px;height:12px;background:var(--red);transform:rotate(-2deg);border-radius:6px}
.subchip{position:absolute;left:44px;top:300px;background:#fff;color:var(--navy);font:800 30px 'CT','NST';padding:8px 22px 6px;border-radius:30px;display:flex;gap:10px;align-items:center}
/* rows */
.rows{position:absolute;left:24px;right:24px;top:345px;bottom:40px;display:flex;flex-direction:column;gap:18px}
.row{flex:1;background:#fff;color:var(--ink);border-radius:26px;display:flex;align-items:center;gap:24px;padding:18px 28px;box-shadow:0 10px 28px rgba(0,0,0,.22);position:relative;min-height:0}
.num{flex:0 0 78px;height:78px;border-radius:50%;background:var(--red);color:#fff;font:900 48px/1 'CT';display:flex;align-items:center;justify-content:center;border:5px solid #fff;box-shadow:0 0 0 4px var(--red)}
.tile{flex:0 0 150px;height:150px;border-radius:24px;background:linear-gradient(145deg,#EEF2FB,#DCE4F5);color:var(--navy);display:flex;align-items:center;justify-content:center;font-size:84px;position:relative}
.tile.red{color:var(--red)}
.tile .badge{position:absolute;right:-10px;bottom:-10px;background:var(--red);color:#fff;font:800 22px 'CT','NST';padding:4px 12px 2px;border-radius:10px;transform:rotate(-8deg);border:3px solid #fff}
.txt{flex:1;min-width:0}
.t1{font:800 40px/1.25 'CT','NST';color:var(--navy)}
.t2{font:700 31px/1.32 'CT','NST';color:var(--grey);margin-top:6px}
.red-t{color:var(--red)}
.pillY{display:inline-block;background:var(--yellow);color:var(--navy);font:800 42px/1.2 'CT','NST';padding:6px 22px 2px;border-radius:14px;margin-top:8px}
.arrow{position:absolute;left:70px;bottom:-26px;color:var(--red);font-size:32px;z-index:2}
/* bottom banner */
.banner{position:absolute;left:0;right:0;bottom:0;height:120px;background:var(--red);display:flex;align-items:center;justify-content:center;font:800 56px 'BT','NST';color:#fff;white-space:nowrap;
  clip-path:polygon(0 18%,30% 6%,62% 14%,100% 0,100% 100%,0 100%)}
.banner b{color:var(--yellow);font-size:72px;margin:0 12px}
.note .ic{font-size:40px;flex:0 0 auto}
/* cover */
.doc{position:absolute;left:110px;top:150px;width:560px;height:520px;background:#fff;border-radius:10px;transform:rotate(-7deg);box-shadow:0 30px 60px rgba(0,0,0,.45);padding:44px 46px;color:var(--navy)}
.doc.back{left:150px;top:170px;transform:rotate(4deg);background:#E7ECF6}
.doc h3{font:800 44px 'CT','NST';text-align:center;margin-bottom:26px}
.doc .ln{height:14px;background:#CFD6E6;border-radius:7px;margin:18px 0}
.doc .ln.s{width:70%}
.stampmark{position:absolute;left:170px;top:330px;border:10px solid var(--red);color:var(--red);font:800 110px/1 'BT','NST';padding:22px 40px 6px;border-radius:22px;transform:rotate(-16deg);background:rgba(255,255,255,.85);letter-spacing:2px}
.bigic{position:absolute;color:#fff}
.cover-bottom{position:absolute;left:0;right:0;bottom:0;height:640px;background:linear-gradient(180deg,rgba(10,28,70,0) 0%, rgba(10,28,70,.92) 18%, var(--navy) 40%)}
.cat{position:absolute;left:40px;top:668px;background:var(--red);color:#fff;font:800 58px 'BT','NST';padding:14px 44px 4px;clip-path:polygon(4% 0,100% 6%,96% 100%,0 92%);transform:rotate(-3deg)}
.hl1{position:absolute;left:40px;right:40px;top:800px;font:800 120px/1.02 'BT','NST';color:#fff;text-align:center;text-shadow:0 6px 0 #061232, 0 12px 26px rgba(0,0,0,.5)}
.hl2{position:absolute;left:40px;right:40px;top:1080px;white-space:nowrap;font:800 150px/1 'BT','NST';color:var(--yellow);text-align:center;text-shadow:0 7px 0 #8A5A00, 0 14px 28px rgba(0,0,0,.5)}
.redline{position:absolute;left:150px;right:150px;height:10px;background:var(--red);border-radius:5px}
.loc{position:absolute;left:40px;right:40px;bottom:36px;display:flex;align-items:center;justify-content:center;gap:16px;font:800 40px 'CT','NST';color:#fff;border-top:2px solid rgba(255,255,255,.35);padding-top:18px}
.loc .ic{font-size:44px;color:var(--red)}
/* sources */
.src{background:#fff;border-radius:24px;display:flex;align-items:center;gap:26px;padding:24px 30px;box-shadow:0 8px 24px rgba(10,28,70,.14);color:var(--navy)}
.src .name{flex:0 0 300px;font:800 52px 'BT','NST';color:var(--red);border-right:3px solid #DCE2EF}
.src .meta{font:800 36px 'CT','NST';display:flex;flex-direction:column;gap:6px}
.src .meta span{display:flex;gap:12px;align-items:center}
.src .meta small{font:700 26px 'CT';color:var(--grey);word-break:break-all}
.note{display:flex;gap:14px;align-items:center;background:#E4E9F4;color:var(--navy);border-radius:40px;padding:14px 28px;font:700 30px 'CT','NST'}
.follow{background:var(--red);color:#fff;border-radius:30px;padding:30px;display:flex;align-items:center;gap:28px}
.follow .ic{font-size:110px;flex:0 0 auto}
.follow .f1{font:800 50px/1.2 'BT','NST'}
.follow .fy{display:inline-block;background:var(--yellow);color:var(--navy);font:800 46px 'CT','NST';padding:6px 28px 2px;border-radius:16px;margin-top:10px}
.share{background:var(--yellow);color:var(--navy);border-radius:26px;padding:24px 30px;display:flex;align-items:center;gap:24px;font:800 42px/1.25 'CT','NST'}
.share .ic{font-size:76px;color:var(--navy)}
"""

def render_page(s, total, i):
    inner = re.sub(r'<i data-ic="([a-z0-9-]+)"></i>', lambda m: icon(m.group(1)), s["html"])
    light = s.get("light", False)
    deco = "" if light else '<div class="slash"></div><div class="slash s2"></div>'
    return f"""<!doctype html><html lang="ta"><head><meta charset="utf-8"><style>{CSS}</style></head>
<body class="{'light' if light else ''}"><div class="bg"></div>{deco}<div class="layer">{inner}</div><div class="logozone"></div>
<script>{FIT_JS}</script></body></html>"""

# Auto-fit: titles shrink to one line (stay clear of the logo), then the underline, sub-chip
# and content rows are placed below the title so nothing overlaps.
FIT_JS = """
function fit(el,max,min){var s=parseFloat(getComputedStyle(el).fontSize);el.style.whiteSpace='nowrap';
  while(el.scrollWidth>max&&s>min){s-=2;el.style.fontSize=s+'px';}}
document.fonts.ready.then(function(){
  document.querySelectorAll('.brush h2').forEach(function(h){fit(h,660,44);});
  document.querySelectorAll('.fit').forEach(function(h){fit(h,+(h.dataset.max||1000),48);});
  var b=document.querySelector('.brush');
  if(b){var y=b.getBoundingClientRect().bottom;
    var u=document.querySelector('.underline'); if(u){u.style.top=(y+4)+'px';y+=22;}
    var sc=document.querySelector('.subchip'); if(sc){sc.style.top=(y+6)+'px';y=sc.getBoundingClientRect().bottom;}
    var r=document.querySelector('.rows'); if(r&&!r.dataset.fixed){r.style.top=Math.max(y+22,250)+'px';}}
  document.body.dataset.ready='1';
});
"""

def main(spec_path, outdir):
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    os.makedirs(outdir, exist_ok=True)
    total = len(spec["slides"])
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1080, "height": 1350}, device_scale_factor=1)
        for i, s in enumerate(spec["slides"], 1):
            name = s.get("file", f"slide_{i}.png")
            hp = (Path(outdir) / (Path(name).stem + ".html")).resolve()
            hp.write_text(render_page(s, total, i), encoding="utf-8")
            pg.goto(f"file://{hp}")
            pg.wait_for_function("document.body.dataset.ready === '1'", timeout=15000)
            pg.wait_for_timeout(150)
            pg.screenshot(path=str(Path(outdir) / name), clip={"x": 0, "y": 0, "width": 1080, "height": 1350})
            print("rendered", name)
        b.close()

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
