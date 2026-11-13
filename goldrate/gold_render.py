"""Gold + silver rate carousel (2 slides, owner design 14 Nov) for every 360 page.
render(page_cfg, rates, outdir) -> [gold.jpg, silver.jpg]   (silver slide left out when today's silver rate is not confirmed)"""
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
FONTS = HERE / "fonts"


def ff(fam, folder, weights):
    out = []
    for w in weights:
        for s in ("tamil", "latin"):
            f = FONTS / f"{folder}-{s}-{w}-normal.woff2"
            if f.exists():
                out.append(f"@font-face{{font-family:'{fam}';font-weight:{w};src:url('file://{f}') format('woff2')}}")
    return "\n".join(out)


def inr(n):
    s = str(int(round(n))); last, rest = s[-3:], s[:-3]
    parts = []
    while len(rest) > 2:
        parts.insert(0, rest[-2:]); rest = rest[:-2]
    if rest:
        parts.insert(0, rest)
    return ",".join(parts + [last]) if parts else last


def change_words(d):
    if d < 0:
        return "down", "குறைவு", "▼"
    if d > 0:
        return "up", "உயர்வு", "▲"
    return "same", "மாற்றமில்லை", "●"


def pill(d):
    cls, word, ar = change_words(d)
    if cls == "same":
        return f'<div class="pill same">● மாற்றமில்லை</div>'
    return f'<div class="pill {cls}">{ar} ₹{inr(abs(d))} {word}</div>'


def chart(points, theme):
    """points: [(label, value)] -> inline SVG line chart, last point highlighted"""
    W, H, L, R, T, B = 940, 290, 60, 60, 60, 64
    vals = [v for _, v in points]
    lo, hi = min(vals), max(vals)
    lo = lo - max(hi - lo, 1) * 1.2      # headroom below: a small move stays a small slope
    span = (hi - lo) or 1
    n = len(points)
    xs = [L + i * (W - L - R) / (n - 1) for i in range(n)]
    ys = [T + (hi - v) / span * (H - T - B - 20) for v in vals]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
    area = f"{xs[0]:.1f},{H - B} " + line + f" {xs[-1]:.1f},{H - B}"
    c1, c2 = ("#FFD54A", "rgba(255,196,64,.35)") if theme == "gold" else ("#F2F5FA", "rgba(220,230,245,.28)")
    g = [f'<defs><linearGradient id="ar{theme}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{c2}"/><stop offset="1" stop-color="rgba(0,0,0,0)"/></linearGradient></defs>',
         f'<polygon points="{area}" fill="url(#ar{theme})"/>',
         f'<line x1="{L - 30}" y1="{H - B}" x2="{W - R + 30}" y2="{H - B}" stroke="rgba(255,255,255,.55)" stroke-width="2"/>',
         f'<polyline points="{line}" fill="none" stroke="{c1}" stroke-width="6" stroke-linejoin="round" stroke-linecap="round"/>']
    for i, ((lab, v), x, y) in enumerate(zip(points, xs, ys)):
        last = i == n - 1
        g.append(f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{x:.1f}" y2="{H - B}" stroke="{c1}" stroke-opacity=".45" stroke-dasharray="3 5" stroke-width="2"/>')
        g.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="11" fill="#fff" stroke="{c1}" stroke-width="5"/>')
        g.append(f'<text x="{x:.1f}" y="{y - 24:.1f}" text-anchor="middle" class="pv">₹{inr(v)}</text>')
        if last:
            g.append(f'<rect x="{x - 58:.1f}" y="{H - B + 14}" width="116" height="44" rx="22" fill="{"#FFD233" if theme == "gold" else "#E9EEF6"}"/>')
        g.append(f'<text x="{x:.1f}" y="{H - B + 46}" text-anchor="middle" class="pd{" pl" if last else ""}">{lab}</text>')
    return f'<svg viewBox="0 0 {W} {H}" width="{W}" height="{H}">{"".join(g)}</svg>'


CSS = """
{fonts}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{width:1080px;height:1350px;position:relative;overflow:hidden;font-family:'NST','CT',sans-serif;color:#fff;background:{bg}}}
.bokeh{{position:absolute;inset:0;background:{bokeh};pointer-events:none}}
.deco{{position:absolute;right:-230px;top:120px;width:470px;height:470px;pointer-events:none;opacity:.35;z-index:1}}
.deco i{{position:absolute;border-radius:50%;border-style:solid}}
.top{{position:absolute;left:44px;right:44px;top:34px;display:flex;align-items:center;gap:22px;z-index:5}}
.top img{{width:126px;height:126px;border-radius:50%;object-fit:cover;border:5px solid {ring};box-shadow:0 0 0 3px rgba(0,0,0,.4),0 10px 30px rgba(0,0,0,.6)}}
.brand{{font:900 {bsize}px/1 'NST';font-style:italic;letter-spacing:-1px;white-space:nowrap;text-shadow:0 4px 14px rgba(0,0,0,.6)}}
.brand b{{color:#FFD233;font:900 {bsize2}px 'CT';font-style:italic;margin-left:4px}}
.brand:after{{content:'';display:block;height:6px;margin-top:6px;border-radius:6px;background:linear-gradient(90deg,transparent,#E3151B 25%,#E3151B 75%,transparent)}}
.vbar{{width:3px;height:80px;background:rgba(255,255,255,.7);margin:0 6px}}
.date{{margin-left:auto;display:flex;align-items:center;gap:14px;padding:16px 26px 10px;border-radius:999px;border:3px solid {ring};
  background:{datebg};font:800 31px 'NST';white-space:nowrap;padding:12px 22px 6px}}
.date svg{{width:36px;height:36px;margin-top:-6px}}
.kick{{position:absolute;left:64px;top:196px;font:800 38px 'NST';z-index:5}}
.kick em{{color:#FFD233;font-style:normal;margin:0 10px}}
.title{{position:absolute;left:56px;top:244px;font:900 116px/1.12 'NST';white-space:nowrap;z-index:5;{titlefill}filter:drop-shadow(0 6px 10px rgba(0,0,0,.55))}}
.uline{{position:absolute;left:120px;top:392px;width:520px;height:5px;background:linear-gradient(90deg,transparent,{ul},transparent);z-index:5}}
.head{{position:absolute;left:60px;top:410px;font:900 56px 'NST';z-index:5;white-space:nowrap}}
.head.down{{color:#FF3B3B}} .head.up{{color:#27D46A}} .head.same{{color:#E7ECF5}}
.cards{{position:absolute;left:44px;right:44px;top:500px;display:flex;gap:26px;z-index:5}}
.card{{flex:1;height:290px;display:flex;flex-direction:column;align-items:center;justify-content:space-between;border-radius:26px;padding:18px 22px 20px;text-align:center;border:3px solid {cardborder};background:{cardbg};box-shadow:0 16px 40px rgba(0,0,0,.55)}}
.card .lbl{{align-self:flex-start;display:flex;align-items:center;gap:16px;font:800 34px 'NST';color:#fff}}
.chip{{background:linear-gradient(180deg,#FFE36A,#F4B81E);color:#1A1200;font:900 40px 'CT';padding:6px 20px 0;border-radius:14px}}
.chip.s{{background:linear-gradient(180deg,#FFFFFF,#C9D2E0);color:#0D1526;font:800 32px 'NST';padding:8px 22px 2px;border-radius:999px}}
.card .v{{font:900 {vsize}px/1.05 'CT';margin:0;letter-spacing:-1px;text-shadow:0 4px 12px rgba(0,0,0,.5)}}

.card .yd{{font:600 27px 'NST';color:#E8E0D8;margin-top:2px}}
.pill{{display:inline-block;margin-top:0;padding:10px 28px 4px;border-radius:999px;font:900 34px 'NST'}}
.pill.down{{background:linear-gradient(180deg,#D8262E,#8E0C12);color:#fff}}
.pill.up{{background:linear-gradient(180deg,#1FA35A,#0B6A33);color:#fff}}
.pill.same{{background:rgba(255,255,255,.18);color:#fff}}
.trend{{position:absolute;left:36px;right:36px;top:{trendtop}px;border-radius:30px;border:3px solid {cardborder};background:{cardbg};padding:14px 30px 2px;z-index:5;box-shadow:0 16px 40px rgba(0,0,0,.55)}}
.trend h3{{display:flex;align-items:center;gap:16px;justify-content:center;font:900 36px 'NST';padding-bottom:8px;white-space:nowrap;border-bottom:2px solid rgba(255,255,255,.18)}}
.trend h3 b{{color:#FFD233}}
.bars{{display:flex;align-items:flex-end;gap:5px;height:40px}} .bars i{{width:10px;background:{barc};border-radius:2px}}
.pv{{font:800 27px 'CT';fill:#fff}} .pd{{font:700 27px 'NST';fill:#fff}} .pd.pl{{fill:#111;font-weight:900}}
.note{{position:absolute;left:20px;right:20px;top:{notetop}px;text-align:center;white-space:nowrap;font:600 25px 'NST';color:#E9E4DC;z-index:5}}
.src{{position:absolute;left:40px;right:40px;top:{srctop}px;text-align:center;font:600 23px 'NST';color:rgba(255,255,255,.7);z-index:5}}
.bottom{{position:absolute;left:50px;right:50px;bottom:34px;display:flex;align-items:center;justify-content:center;z-index:5}}
.fol{{padding:12px 30px 6px;border-radius:999px;border:3px solid {ring};background:rgba(10,10,14,.85);font:800 34px 'CT','NST';white-space:nowrap}}
.fol b{{color:#FFD233}}
.sep{{width:3px;height:60px;background:rgba(255,215,90,.8)}}
.next{{padding:12px 34px 6px;border-radius:999px;background:linear-gradient(180deg,#FFE36A,#F4B81E);color:#1A1200;font:900 36px 'NST';white-space:nowrap;box-shadow:0 8px 24px rgba(0,0,0,.5)}}
"""

CAL = '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2"><rect x="3" y="5" width="18" height="16" rx="2" fill="#B5121B"/><path d="M3 10h18M8 3v4M16 3v4"/><path d="M7 14h2M11 14h2M15 14h2M7 17h2M11 17h2" stroke-width="2.4"/></svg>'


def slide(p, r, kind):
    gold = kind == "gold"
    th = dict(
        fonts=ff("NST", "noto-sans-tamil", [600, 700, 800, 900]) + ff("CT", "catamaran", [700, 800, 900]),
        bg="radial-gradient(90% 60% at 80% 20%,#3A1408 0%,#140808 45%,#07070B 100%)" if gold else
           "radial-gradient(90% 60% at 80% 20%,#16325E 0%,#0A1428 50%,#050A16 100%)",
        bokeh=("radial-gradient(60px 60px at 520px 210px,rgba(255,190,90,.35),transparent),radial-gradient(90px 90px at 980px 90px,rgba(255,170,60,.28),transparent),"
               "radial-gradient(40px 40px at 860px 520px,rgba(255,200,120,.25),transparent),radial-gradient(70px 70px at 120px 980px,rgba(255,170,60,.12),transparent)") if gold else
              ("radial-gradient(60px 60px at 920px 120px,rgba(170,200,255,.35),transparent),radial-gradient(90px 90px at 1020px 300px,rgba(140,180,255,.25),transparent),"
               "radial-gradient(40px 40px at 760px 80px,rgba(200,220,255,.3),transparent)"),
        ring="#F2C14E" if gold else "#DDE5F2",
        titlefill=("background:linear-gradient(180deg,#FFF3B0 0%,#FFD23F 45%,#D98A0B 100%);-webkit-background-clip:text;color:transparent;" if gold else
                   "background:linear-gradient(180deg,#FFFFFF 0%,#E6ECF5 50%,#9AA8BE 100%);-webkit-background-clip:text;color:transparent;"),
        ul="#FFC83D" if gold else "#8FB4FF",
        cardborder="rgba(242,170,70,.9)" if gold else "rgba(225,232,245,.85)",
        cardbg="linear-gradient(180deg,rgba(110,14,20,.82),rgba(40,6,10,.9))" if gold else "linear-gradient(180deg,rgba(28,44,74,.85),rgba(10,18,34,.92))",
        barc="#F4B81E" if gold else "#E6ECF5", trendtop=830, bsize=p.get('brand_px', 54), bsize2=p.get('brand_px', 54) + 10, notetop=1158, srctop=1196, vsize=88 if gold else 80, datebg=('linear-gradient(180deg,rgba(130,10,20,.85),rgba(60,4,10,.9))' if gold else 'linear-gradient(180deg,rgba(40,62,104,.9),rgba(14,24,46,.95))'))
    css = CSS.format(**th)
    deco = ("".join(f'<i style="left:{x}px;top:{y}px;width:{w}px;height:{w}px;border-width:{b}px;border-color:{c};box-shadow:0 0 30px {g}"></i>'
                    for x, y, w, b, c, g in ((40, 30, 300, 26, "#E9B53A #8C5A0C #F7D774 #B67A12", "rgba(255,190,70,.45)"),
                                             (190, 140, 230, 20, "#F7D774 #B67A12 #E9B53A #8C5A0C", "rgba(255,190,70,.4)")))
            if gold else
            "".join(f'<i style="left:{x}px;top:{y}px;width:{w}px;height:{w}px;border-width:{b}px;border-color:{c};box-shadow:0 0 30px {g}"></i>'
                    for x, y, w, b, c, g in ((40, 30, 300, 26, "#F5F7FB #7E8796 #DDE3EC #A3ACBA", "rgba(200,215,240,.45)"),
                                             (190, 140, 230, 20, "#DDE3EC #A3ACBA #F5F7FB #7E8796", "rgba(200,215,240,.4)"))))
    if gold:
        d22 = r["g22"] - r["g22_prev"]; d24 = r["g24"] - r["g24_prev"]
        cls, word, ar = change_words(d22)
        head = f'{ar} 22K கிராமுக்கு ₹{inr(abs(d22))} {word}' if d22 else '22K விலையில் மாற்றமில்லை'
        cards = (f'<div class="card"><div class="lbl"><span class="chip">22K</span>ஒரு கிராம்</div><div class="v">₹{inr(r["g22"])}</div>'
                 f'<div class="yd">{r["vs"]}</div>{pill(d22)}</div>'
                 f'<div class="card"><div class="lbl"><span class="chip">24K</span>ஒரு கிராம்</div><div class="v">₹{inr(r["g24"])}</div>'
                 f'<div class="yd">{r["vs"]}</div>{pill(d24)}</div>')
        trend_t = 'ஒரு வாரத்தில் <b>22K</b> தங்கம் விலை மாற்றம்'
        pts = r["week22"]; title = "தங்கம் விலை"; nxt = "வெள்ளி விலை ›"; tsize = 116; src = r.get("source", "")
    else:
        ds = r["silver"] - r["silver_prev"]
        cls, word, ar = change_words(ds)
        head = f'{ar} கிராமுக்கு ₹{inr(abs(ds))} {word}' if ds else 'வெள்ளி விலையில் மாற்றமில்லை'
        cards = (f'<div class="card"><div class="lbl"><span class="chip s">1 கிராம்</span></div><div class="v">₹{inr(r["silver"])}</div>'
                 f'<div class="yd">{r["vs"]}</div>{pill(ds)}</div>'
                 f'<div class="card"><div class="lbl"><span class="chip s">1 கிலோ</span></div><div class="v">₹{inr(r["silver"] * 1000)}</div>'
                 f'<div class="yd">{r["vs"]}</div>{pill(ds * 1000)}</div>')
        trend_t = 'ஒரு வாரத்தில் வெள்ளி விலை மாற்றம்'
        pts = r["weeksilver"]; title = "வெள்ளி விலை"; nxt = "தங்கம் விலை ›"; tsize = 100; src = r.get("source_silver", "")
    body = f"""<div class="bokeh"></div><div class="deco">{deco}</div>
<div class="top"><img src="file://{Path(p['logo']).resolve()}"><div class="brand">{p['name1']}<b>360</b></div><div class="vbar"></div>
 <div class="date">{CAL}{r['date']}</div></div>
<div class="kick">{p['town']}<em>●</em>காலை நிலவரம்</div>
<div class="title" style="font-size:{tsize}px">{title}</div><div class="uline"></div>
<div class="head {cls}">{head}</div>
<div class="cards">{cards}</div>
<div class="trend"><h3><span class="bars"><i style="height:16px"></i><i style="height:26px"></i><i style="height:38px"></i></span><span>{trend_t}</span></h3>{chart(pts, kind)}</div>
<div class="bottom"><div class="fol">Follow <b>@{p['handle']}</b></div></div>"""
    return f'<!doctype html><html><head><meta charset="utf-8"><style>{css}</style></head><body>{body}</body></html>'


def render(p, r, outdir, log=print):
    """p: page (town, name1, logo, handle, brand_px); r: rates (see gold_daily.py). Returns the JPEG paths in slide order."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    kinds = ["gold"] + (["silver"] if r.get("silver") else [])
    out = []
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": 1080, "height": 1350})
        for i, kind in enumerate(kinds, 1):
            h = outdir / f"{i}_{kind}.html"
            h.write_text(slide(p, r, kind), encoding="utf-8")
            pg.goto(f"file://{h.resolve()}")
            pg.wait_for_timeout(900)
            j = outdir / f"{i}_{kind}.jpg"
            pg.screenshot(path=str(j), type="jpeg", quality=92)      # Instagram takes JPEG only
            out.append(j)
            log("slide", j.name)
        b.close()
    return out
