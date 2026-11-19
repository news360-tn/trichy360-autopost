"""Gold + silver rate REEL in the Kovai Minnal / Chennai Minnal pattern (owner 19 Nov: "Kovai Minnal and Chennai Minnal page refer ...
use that design ... update logo branding all are used in my page"): their layout, numbers and timing, in OUR 360 brand - each page's
own logo and name with the gold "360", the logo's maroon + gold colours, and the 360-DEGREE CLOCK style (owner 19 Nov: "use the clock
360 degree style, because all my pages use 360"): a clock dial with "360°" on the coin whose gold ring sweeps a full turn, a clockwise
clock-hand wipe from one screen to the next, slowly turning clock bezels in the bands, a 360° ring closing round the logo at the end.

The look: the GOLD screen is a warm gold field, the SILVER screen a cool brushed-silver field; on both, the 360 maroon carries the
brand (header band with the page logo, the maroon price plate with the metal-foil number, the week plate, the base band) and the
gold accent sits on the maroon only (never on the metal, where it would vanish).
Every number is the confirmed rate or plain arithmetic on it - nothing estimated:
  gold:   1 சவரன் (8 g) 22K = the hero (how Tamil Nadu buys gold), 22K / 24K per gram, 24K 10 g, 1 சவரன் + 3% GST (GST on
          gold is 3%; making charges / wastage vary by shop, so they are left out and said so), this week's bars + high / low
  silver: 1 kg = the hero, 1 g / 10 g / 100 g, this week's bars + high / low
reel_page(page_cfg, rates) -> html   1080 x 1920: gold, silver (when confirmed), follow card. window.DUR, window.seek(t) (every frame
                                     is computed from t) and window.COVER_T (the fully built gold screen = the reel's cover)
page_cfg: town, name1, handle, logo (gold_daily.PAGES + logo); rates: gold_daily.rates_for_slides / pm_rates ("kick" = மாலை நிலவரம்)"""
import json
from pathlib import Path

from gold_render import ff, inr, change_words

MAROON, MAROON2, GOLD, WHITE, DOWN, UP = "#3A070B", "#8E1218", "#FFD233", "#FFFFFF", "#E53935", "#2E9E5B"
GST = 0.03      # GST on gold and silver (CGST 1.5% + SGST 1.5%)
CLOCK = ('<svg class="clk" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9.6"/><path d="M12 6.2V12l4 2.6"/></svg>')      # the tip icon


def dial(cls="dial"):
    """a clock bezel - 60 ticks, every 5th long: the 360-degree motif"""
    ticks = "".join(f'<line x1="50" y1="{3 if i % 5 == 0 else 5}" x2="50" y2="{13 if i % 5 == 0 else 9}" '
                    f'stroke-width="{2.6 if i % 5 == 0 else 1.2}" transform="rotate({i * 6} 50 50)"/>' for i in range(60))
    return f'<svg class="{cls}" viewBox="0 0 100 100"><circle cx="50" cy="50" r="48.5" stroke-width="1.4"/>{ticks}</svg>'


ARC_R = 44.0      # the emblem's sweeping ring (viewBox 100)
ARC_C = round(2 * 3.14159265 * ARC_R, 2)


def chip(d, unit="", a=""):
    cls, word, ar = change_words(d)
    if cls == "same":
        return f'<span class="chg same"{a}>● மாற்றமில்லை</span>'
    return f'<span class="chg {cls}"{a}>{ar} ₹{inr(abs(d))}{unit} {word}</span>'


def bars(points, a=lambda k: ""):
    """this week's rates as bars (today = the gold one) + the week's high / low"""
    vals = [v for _, v in points]
    if not vals:
        return ""
    hi, lo = max(vals), min(vals)
    base = lo - max(hi - lo, 1) * 0.6      # a small move stays a small step
    out = []
    for i, (lab, v) in enumerate(points):
        h = 24 + int((v - base) / ((hi - base) or 1) * 76)      # % of the bar track
        today = i == len(points) - 1
        out.append(f'<div class="bar{" today" if today else ""}"><div class="trk"><div class="in"><b{a("barv%d" % i)}>₹{inr(v)}</b>'
                   f'<i style="height:{h}%"{a("bar%d" % i)}></i></div></div><span>{lab}</span></div>')
    return (f'<div class="bars">{"".join(out)}</div>'
            f'<div class="hl"{a("hl")}><span>▲ வாரத்தின் அதிகம் ₹{inr(hi)}</span><span>▼ வாரத்தின் குறைவு ₹{inr(lo)}</span></div>')


def css():
    fonts = ff("Noto Sans Tamil", "noto-sans-tamil", (600, 700, 800, 900)) + "\n" + ff("Catamaran", "catamaran", (800, 900))
    return fonts + f"""
*{{margin:0;padding:0;box-sizing:border-box}}
body{{width:1080px;overflow:hidden;font-family:'Noto Sans Tamil',sans-serif;color:{MAROON};position:relative;background:{MAROON}}}
.dial{{display:block}} .dial circle,.dial line{{stroke:currentColor;fill:none}}
.clk{{display:block}} .clk circle,.clk path{{fill:none;stroke:currentColor;stroke-width:2.4;stroke-linecap:round;stroke-linejoin:round}}
/* the two metals */
.gold{{--bg:linear-gradient(140deg,#FFF1B8 0%,#F7CF5E 22%,#E9B233 45%,#F9DC7F 63%,#DDA021 82%,#BC800F 100%);
 --tex:repeating-conic-gradient(from 8deg at 92% 14%,rgba(255,255,255,.13) 0 3deg,rgba(255,255,255,0) 3deg 9deg);
 --foil:linear-gradient(180deg,#FFF6CF 0%,#FFD95C 42%,#E9A91F 58%,#FFE894 100%);
 --bar:linear-gradient(180deg,#F3CD62,#A9771A);--panel:rgba(255,250,232,.66);--edge:rgba(255,255,255,.75);
 --rim:#E9B233;--soft:#F6E3A6;--r:34px}}
.silver{{--bg:linear-gradient(140deg,#FBFCFE 0%,#D7DDE6 22%,#B6BFCC 45%,#EEF1F6 63%,#ABB5C3 82%,#838EA0 100%);
 --tex:repeating-linear-gradient(4deg,rgba(255,255,255,.2) 0 1px,rgba(255,255,255,0) 1px 5px);
 --foil:linear-gradient(180deg,#FFFFFF 0%,#E3E8EF 42%,#A3AEBD 58%,#F4F6FA 100%);
 --bar:linear-gradient(180deg,#EDF1F6,#8691A2);--panel:rgba(255,255,255,.62);--edge:rgba(255,255,255,.85);
 --rim:#C3CBD7;--soft:#E9D9DA;--r:12px}}
.metal{{position:absolute;inset:0;background:var(--bg)}}
.metal:before{{content:"";position:absolute;inset:0;background:var(--tex)}}
.metal:after{{content:"";position:absolute;inset:0;background:radial-gradient(90% 60% at 20% 30%,rgba(255,255,255,.35),rgba(255,255,255,0) 70%)}}
/* brand band: the page logo, "<town> 360" with the gold 360 */
.top{{position:relative;background:linear-gradient(100deg,{MAROON} 0%,{MAROON2} 100%);color:{WHITE};display:flex;align-items:center;
 gap:22px;padding:0 48px;border-bottom:7px solid {GOLD};overflow:hidden}}
.top img{{width:108px;height:108px;border-radius:50%;border:4px solid {GOLD};background:#fff;flex:none}}
.brand b{{display:block;font-size:46px;font-weight:900;line-height:1.2;white-space:nowrap}}
.brand b i{{font-family:'Catamaran';font-style:italic;font-weight:900;color:{GOLD};margin-left:6px}}
.brand small{{display:block;font-family:'Catamaran';font-weight:800;font-size:23px;letter-spacing:6px;color:{GOLD};white-space:nowrap}}
.top .deco{{position:absolute;right:120px;top:-70px;width:250px;color:{GOLD};opacity:.16}}
.date{{background:{MAROON};color:{GOLD};border-radius:40px;padding:8px 24px;font-size:26px;font-weight:800;white-space:nowrap;line-height:1.45}}
.col{{position:relative;display:flex;flex-direction:column;padding:0 48px}}
.kickrow{{display:flex;align-items:center;justify-content:space-between}}
.kick{{font-size:30px;font-weight:800;color:{MAROON};opacity:.82;white-space:nowrap;line-height:1.5}}
.titlerow{{display:flex;align-items:center;justify-content:space-between}}
.title{{font-size:96px;font-weight:900;line-height:1.3;color:{MAROON};white-space:nowrap;text-shadow:0 2px 0 rgba(255,255,255,.45)}}
/* the emblem: a 360-degree clock dial on a gold / silver coin, its ring sweeps a full turn */
.emb{{position:absolute;right:40px;top:50%;width:184px;height:184px;margin-top:-92px;border-radius:50%;display:flex;align-items:center;
 justify-content:center;color:{MAROON};box-shadow:inset 0 0 0 8px rgba(255,255,255,.38),0 0 0 6px rgba(255,210,51,.16),0 14px 30px rgba(0,0,0,.5)}}
.gold .emb{{background:radial-gradient(circle at 34% 28%,#FFF8D6,#F4C847 48%,#B47C14 100%)}}
.silver .emb{{background:radial-gradient(circle at 34% 28%,#FFFFFF,#D6DCE5 50%,#7F8A9C 100%)}}
.emb .dial{{position:absolute;left:10px;top:10px;width:164px;height:164px;color:rgba(58,7,11,.72)}}
.emb .ring{{position:absolute;left:0;top:0;width:184px;height:184px;transform:rotate(-90deg)}}
.emb .ring circle{{fill:none;stroke:{MAROON};stroke-width:5.5;stroke-linecap:round;stroke-dasharray:{ARC_C};stroke-dashoffset:0}}
.emb .e3{{position:relative;font-family:'Catamaran';font-style:italic;font-weight:900;font-size:46px;line-height:1;letter-spacing:-1px;
 color:{MAROON};text-shadow:0 2px 0 rgba(255,255,255,.55)}}
/* the price plate */
.hero{{position:relative;overflow:hidden;background:linear-gradient(120deg,{MAROON2} 0%,{MAROON} 70%);color:{WHITE};border-radius:var(--r);
 padding:20px 40px 26px;box-shadow:0 18px 36px rgba(58,7,11,.38),inset 0 0 0 3px var(--rim),inset 0 0 0 9px {MAROON}}}
.hero .sheen{{position:absolute;top:-20%;bottom:-20%;left:0;width:150px;background:linear-gradient(90deg,rgba(255,255,255,0),rgba(255,255,255,.2),rgba(255,255,255,0));
 transform:translateX(-400px) skewX(-18deg);pointer-events:none}}
.hero .lbl{{position:relative;font-size:30px;font-weight:800;color:var(--soft);white-space:nowrap;line-height:1.5}}
.hero .v{{position:relative;display:inline-block;font-family:'Catamaran';font-size:112px;font-weight:900;line-height:1.08;letter-spacing:-1px;
 padding-right:8px;white-space:nowrap;background:var(--foil);-webkit-background-clip:text;background-clip:text;color:transparent;
 filter:drop-shadow(0 3px 0 rgba(0,0,0,.35))}}
.hero .cv{{position:relative;display:flex;align-items:center;gap:14px;margin-top:2px}}
.chg{{display:inline-block;border-radius:30px;padding:6px 22px;font-size:28px;font-weight:800;color:#fff;white-space:nowrap;line-height:1.5}}
.chg.down{{background:{DOWN}}} .chg.up{{background:{UP}}} .chg.same{{background:#6E6470}}
.hero .vs{{font-size:24px;font-weight:700;color:#E3C9CB;white-space:nowrap}}
/* the rate rows */
.rows{{background:var(--panel);border:2px solid var(--edge);border-radius:24px;padding:0 28px;box-shadow:0 10px 22px rgba(58,7,11,.12)}}
.row{{display:flex;align-items:center;gap:16px;height:70px;border-top:2px solid rgba(58,7,11,.12)}}
.row:first-child{{border-top:0}}
.row .k{{font-size:28px;font-weight:800;white-space:nowrap}}
.row .k em{{font-style:normal;display:inline-block;background:{MAROON};color:{GOLD};border-radius:10px;padding:0 12px;margin-right:12px;
 font-family:'Catamaran';font-weight:900;font-size:28px;line-height:1.5}}
.row .chg{{font-size:21px;padding:3px 14px}}
.row .n{{margin-left:auto;font-family:'Catamaran';font-size:54px;font-weight:900;line-height:1;white-space:nowrap}}
/* the tip */
.tip{{display:flex;align-items:center;gap:20px;border:3px dashed rgba(58,7,11,.55);border-radius:22px;padding:10px 24px;background:rgba(255,255,255,.22)}}
.tip .ic{{flex:none;width:62px;height:62px;border-radius:50%;background:{MAROON};color:{GOLD};display:flex;align-items:center;justify-content:center}}
.tip .ic .clk{{width:36px}}
.tip p{{font-size:26px;font-weight:800;line-height:1.5;white-space:nowrap}}
.tip p b{{display:inline-block;background:{MAROON};color:{GOLD};border-radius:12px;padding:0 14px;font-family:'Catamaran';font-weight:900;font-size:34px;line-height:1.3;vertical-align:middle}}
.tip p.s{{font-size:23px;font-weight:700;opacity:.85}}
/* the week */
.week{{display:flex;flex-direction:column;background:linear-gradient(180deg,{MAROON2},{MAROON});color:{WHITE};border-radius:26px;padding:14px 26px 12px;
 box-shadow:0 14px 28px rgba(58,7,11,.3)}}
.week h3{{font-size:27px;font-weight:800;color:var(--soft);white-space:nowrap;line-height:1.5}}
.bars{{flex:1;display:flex;align-items:stretch;gap:12px;min-height:0}}
.bar{{flex:1;max-width:190px;display:flex;flex-direction:column;align-items:center;margin:0 auto}}
.bar .trk{{flex:1;width:100%;position:relative;min-height:0}}
.bar .trk .in{{position:absolute;left:0;right:0;top:30px;bottom:0;display:flex;flex-direction:column;align-items:center;justify-content:flex-end}}
.bar i{{display:block;flex:none;width:64%;border-radius:9px 9px 0 0;background:var(--bar);opacity:.8;transform-origin:50% 100%}}
.bar b{{font-family:'Catamaran';font-size:20px;font-weight:900;color:#F0DADB;white-space:nowrap;line-height:1.3}}
.bar.today i{{background:linear-gradient(180deg,#FFE680,{GOLD});opacity:1;box-shadow:0 0 22px rgba(255,210,51,.55)}}
.bar.today b{{color:{GOLD};font-size:24px}}
.bar span{{font-size:20px;font-weight:700;color:#F0DADB;white-space:nowrap;line-height:1.7}}
.bar.today span{{color:{MAROON};background:{GOLD};border-radius:14px;padding:0 10px;font-weight:800}}
.hl{{display:flex;justify-content:space-between;gap:20px;font-size:22px;font-weight:700;color:#F0DADB;border-top:2px solid rgba(255,255,255,.14);
 margin-top:8px;padding-top:4px;white-space:nowrap;line-height:1.6}}
.src{{font-size:22px;font-weight:700;white-space:nowrap;line-height:1.5}}
"""


def brand_html(p):
    """"<town> 360" with the gold 360 - the name on the page's own logo"""
    return f'{p["name1"]}<i>360</i>'


def blocks(p, r, kind, a=lambda k: ""):
    """the pieces of one metal's screen; a(key) -> the reel's animation attribute"""
    src = r.get("source" if kind == "gold" else "source_silver") or ""
    b = {"top": (f'<div class="top"><div class="deco">{dial()}</div><img src="file://{Path(p["logo"]).resolve()}"{a("logo")}>'
                 f'<div class="brand"{a("brand")}><b>{brand_html(p)}</b><small>GOLD &amp; SILVER RATE</small></div>%s</div>'),
         "date": f'<div class="date"{a("date")}>{r["date"]}</div>',
         "kick": f'<div class="kick"{a("kick")}>{p["town"]} • {r.get("kick") or "காலை நிலவரம்"}</div>',
         "market": f'{p["town"]} நிலவரம்{" • " + src if src else ""}'}
    if kind == "gold":
        sov, sov_prev = r["g22"] * 8, r["g22_prev"] * 8
        title, lbl, val, prev = "தங்கம் விலை", "22 காரட் • 1 சவரன் (8 கிராம்)", sov, sov_prev
        rows = [("<em>22K</em>1 கிராம்", r["g22"], r["g22"] - r["g22_prev"]), ("<em>24K</em>1 கிராம்", r["g24"], r["g24"] - r["g24_prev"]),
                ("<em>24K</em>10 கிராம்", r["g24"] * 10, None)]
        tip = (f'1 சவரன் + 3% ஜிஎஸ்டி = <b>₹{inr(sov * (1 + GST))}</b>', "செய்கூலி, சேதாரம் கடைக்கு ஏற்ப தனியாகச் சேரும்")
        wk, pts = "இந்த வாரம் • 22K, 1 கிராம்", r.get("week22") or []
    else:
        kg, kg_prev = r["silver"] * 1000, r["silver_prev"] * 1000
        title, lbl, val, prev = "வெள்ளி விலை", "வெள்ளி • 1 கிலோ", kg, kg_prev
        rows = [("1 கிராம்", r["silver"], r["silver"] - r["silver_prev"]), ("10 கிராம்", r["silver"] * 10, None),
                ("100 கிராம்", r["silver"] * 100, None)]
        tip = (f'1 கிலோ + 3% ஜிஎஸ்டி = <b>₹{inr(kg * (1 + GST))}</b>', "கொலுசு, பாத்திரம் போன்றவற்றுக்கு செய்கூலி தனி")
        wk, pts = "இந்த வாரம் • வெள்ளி, 1 கிராம்", r.get("weeksilver") or []
    b["title"] = f'<div class="titlerow"><div class="title"{a("title")}>{title}</div></div>'
    cnt = a("count")      # the reel counts up from yesterday's price (from 97% when unchanged) and lands on today's
    if cnt:
        cnt += f' data-from="{int(round(prev if prev != val else val * 0.97))}" data-to="{int(round(val))}"'
    emb = (f'<div class="emb"{a("emb")}>{dial()}<svg class="ring" viewBox="0 0 100 100"><circle cx="50" cy="50" r="{ARC_R}"/></svg>'
           f'<span class="e3">360°</span></div>')
    b["hero"] = (f'<div class="hero"{a("hero")}>{emb}<div class="sheen"></div>'
                 f'<div class="lbl">{lbl}</div><div class="v"{cnt}>₹{inr(val)}</div>'
                 f'<div class="cv">{chip(val - prev, a=a("chip"))}<span class="vs"{a("vs")}>{r["vs"]}</span></div></div>')
    b["rows"] = '<div class="rows"%s>' % a("rows") + "".join(
        f'<div class="row"{a("row%d" % i)}><div class="k">{k}</div>{chip(d) if d is not None else ""}<div class="n">₹{inr(n)}</div></div>'
        for i, (k, n, d) in enumerate(rows)) + "</div>"
    b["tip"] = f'<div class="tip"{a("tip")}><div class="ic">{CLOCK}</div><div><p>{tip[0]}</p><p class="s">{tip[1]}</p></div></div>'
    b["week"] = f'<div class="week"{a("week")}><h3>{wk}</h3>{bars(pts, a)}</div>'
    return b


# ---------------------------------------------------------------- the reel, 1080 x 1920
# One metal's screen, seconds after its clock wipe: key -> (start, length, effect). Everything on the page comes from this one table.
# Kovai Minnal's tuning (their owner 17 Nov): the reel opens ALREADY showing the brand, the title and the price (FIRST: shown from
# frame 0 on the first screen), every block is in by ~2 s, then ~3 s to read; 10 s in all - gold 4.3 s + silver 4.3 s + follow 1.4 s
# (no silver: 5.7 s).
SCENE = 4.3                                             # one metal's screen
END = 1.4                                               # the follow card
STEPS = {"logo": (0.00, 0.20, "pop"), "brand": (0.00, 0.20, "fade"), "date": (0.04, 0.20, "fade"),
         "kick": (0.04, 0.20, "fade"), "title": (0.04, 0.25, "wipe"), "emb": (0.12, 0.25, "pop"),
         "hero": (0.06, 0.22, "pop"), "count": (0.12, 0.48, "count"), "chip": (0.62, 0.20, "pop"), "vs": (0.66, 0.20, "fade"),
         "rows": (0.70, 0.20, "fade"), "row0": (0.72, 0.20, "fade"), "row1": (0.84, 0.20, "fade"), "row2": (0.96, 0.20, "fade"),
         "week": (1.05, 0.25, "pop"), "hl": (1.65, 0.20, "fade"), "tip": (1.72, 0.25, "pop"), "src": (1.85, 0.20, "fade")}
FIRST = ("logo", "brand", "date", "kick", "title", "emb", "hero", "count")      # already on screen at frame 0 (today's price, no count-up)
BAR0, BAR_STEP, BAR_LEN = 1.10, 0.05, 0.25             # the week's bars grow one after another; today's lands last
COVER = 3.4                                            # the gold screen is fully built here (the reel's cover)
WIPE = 0.42                                            # the clockwise clock-hand wipe into the next screen (silver, follow card)
SWEEP = (0.05, 1.30)                                   # the emblem's ring: one full 360° turn while the price lands
LOGO_R = 196.0                                         # the follow card's ring round the logo (px)
END_STEPS = {"elogo": (0.05, 0.30, "pop"), "ename": (0.18, 0.25, "fade"), "esub": (0.28, 0.25, "fade"), "efollow": (0.40, 0.30, "pop")}

REEL_CSS = f"""
body.reel{{height:1920px}}
.scene{{position:absolute;left:0;top:0;width:1080px;height:1920px;overflow:hidden;visibility:hidden}}
.reel .metal{{left:-60px;right:-60px}}
.reel .top{{height:352px;align-items:flex-start;padding-top:228px}}
.reel .top .deco{{right:-40px;top:-60px;width:400px}}
.reel .top .date{{margin-left:auto;margin-top:24px;background:{GOLD};color:{MAROON}}}
.reel .col{{position:absolute;left:0;right:0;top:352px;padding-top:12px}}
.reel .title{{font-size:100px}}
.reel .titlerow{{margin-top:-8px}}
.reel .hero{{margin-top:2px;padding:22px 40px 28px}}
.reel .hero .v{{font-size:124px}}
.reel .rows{{margin-top:16px}}
.reel .row{{height:78px}}
.reel .low{{margin-right:104px}}
.reel .week{{margin-top:18px;height:344px}}
.reel .tip{{margin-top:16px}}
.reel .tip p{{font-size:25px}}
.reel .tip p.s{{font-size:21px}}
.reel .src{{margin-top:8px;opacity:.85}}
.end{{background:radial-gradient(90% 55% at 50% 42%,{MAROON2} 0%,{MAROON} 75%);color:{WHITE};text-align:center}}
.end .deco{{position:absolute;left:50%;top:305px;width:660px;margin-left:-330px;color:{GOLD};opacity:.16}}
.end .lring{{position:absolute;left:50%;top:635px;width:{int(LOGO_R * 2 + 24)}px;height:{int(LOGO_R * 2 + 24)}px;margin-left:-{int(LOGO_R + 12)}px;
 margin-top:-{int(LOGO_R + 12)}px;transform:rotate(-90deg)}}
.end .lring circle{{fill:none;stroke:{GOLD};stroke-width:9;stroke-linecap:round;stroke-dasharray:{round(2 * 3.14159265 * LOGO_R, 1)};
 filter:drop-shadow(0 0 12px rgba(255,210,51,.7))}}
.end img{{position:absolute;left:50%;top:470px;width:330px;height:330px;margin-left:-165px;border-radius:50%;border:7px solid {GOLD};
 background:#fff;box-shadow:0 0 90px rgba(255,210,51,.35)}}
.end .nm{{position:absolute;left:60px;right:60px;top:836px;font-size:84px;font-weight:900;line-height:1.3;white-space:nowrap}}
.end .nm i{{font-family:'Catamaran';font-style:italic;font-weight:900;color:{GOLD};margin-left:10px}}
.end .sub{{position:absolute;left:60px;right:60px;top:952px;font-size:34px;font-weight:700;color:#F0DADB;line-height:1.5;white-space:nowrap}}
.end .fw{{position:absolute;left:0;right:0;top:1024px}}
.end .fw span{{display:inline-block;background:{GOLD};color:{MAROON};border-radius:50px;padding:10px 44px;font-size:42px;font-weight:900;
 line-height:1.5;white-space:nowrap;box-shadow:0 12px 30px rgba(0,0,0,.4)}}
.hand{{position:absolute;left:536px;top:-340px;width:8px;height:1300px;border-radius:4px;visibility:hidden;pointer-events:none;z-index:9;
 transform-origin:50% 100%;background:linear-gradient(0deg,{GOLD} 0%,#FFF3B0 70%,rgba(255,243,176,0) 100%);
 box-shadow:0 0 18px rgba(255,210,51,.9),0 0 46px rgba(255,210,51,.55)}}
.pivot{{position:absolute;left:510px;top:930px;width:60px;height:60px;border-radius:50%;background:{GOLD};border:8px solid {MAROON};
 visibility:hidden;z-index:10;box-shadow:0 0 24px rgba(255,210,51,.8)}}
.base{{position:absolute;left:0;right:0;top:1700px;bottom:0;background:linear-gradient(100deg,{MAROON} 0%,{MAROON2} 100%);border-top:7px solid {GOLD};overflow:hidden}}
.base .dial{{position:absolute;right:-60px;top:-40px;width:330px;color:{GOLD};opacity:.16}}
"""

REEL_JS = """
const cl=x=>x<0?0:x>1?1:x, eo=x=>1-Math.pow(1-x,3), back=x=>1+2.4*Math.pow(x-1,3)+1.4*Math.pow(x-1,2);
function inr(n){let s=String(Math.round(n)),l=s.slice(-3),r=s.slice(0,-3),p=[];while(r.length>2){p.unshift(r.slice(-2));r=r.slice(0,-2)}
 if(r)p.unshift(r);p.push(l);return p.join(',')}
const scenes=[...document.querySelectorAll('.scene')], hand=document.querySelector('.hand'), pivot=document.querySelector('.pivot');
const els=[...document.querySelectorAll('[data-a]')].map(e=>{const a=e.dataset.a.split(',');
 return {e,t0:+a[0],d:+a[1],fx:a[2],fin:e.textContent,from:+e.dataset.from,to:+e.dataset.to}});
window.seek=t=>{
 t=Math.max(0,Math.min(window.DUR,+t||0));
 let hv=0, ha=0;
 scenes.forEach((s,i)=>{
  const u=t-SC[i][0], wip=i>0&&u>=0&&u<WIPE, under=i<scenes.length-1&&t>=SC[i+1][0]&&t<SC[i+1][0]+WIPE;
  const on=(t>=SC[i][0]&&(t<SC[i][1]||i==scenes.length-1))||under;
  s.style.visibility=on?'visible':'hidden'; s.style.zIndex=wip?2:1;
  if(wip){const a=360*eo(u/WIPE), m='conic-gradient(from 0deg at 50% 50%,#000 0deg '+a.toFixed(1)+'deg,transparent '+a.toFixed(1)+'deg 360deg)';
   s.style.webkitMaskImage=m; s.style.maskImage=m; hv=1; ha=a;}      // the clock hand sweeps the next screen in, clockwise
  else {s.style.webkitMaskImage='none'; s.style.maskImage='none';}
  s.querySelectorAll('.deco .dial,.base .dial,.end .deco .dial').forEach(d=>d.style.transform='rotate('+(t*14).toFixed(2)+'deg)');
  const rg=s.querySelector('.emb .ring circle'); if(rg){const q=eo(cl((u-SWEEP[0])/SWEEP[1]));      // the emblem ring: one full turn
   rg.style.strokeDashoffset=(ARC_C*(1-q)).toFixed(2);}
  const lr=s.querySelector('.lring circle'); if(lr){const q=eo(cl((u-0.30)/0.75));      // the 360° ring closes round the logo
   lr.style.strokeDashoffset=(LRC*(1-q)).toFixed(2);}
  const m=s.querySelector('.metal'); if(m) m.style.transform='translateX('+(-30+u*8).toFixed(2)+'px)';
  const sh=s.querySelector('.sheen'); if(sh){const q=cl((u-2.1)/0.9);      // one glint across the plate, done long before the cover frame
   sh.style.transform='translateX('+(-400+q*1700).toFixed(1)+'px) skewX(-18deg)';}
 });
 for(const o of els){
  const x=cl((t-o.t0)/o.d), k=eo(x), st=o.e.style;
  if(o.fx=='count'){o.e.textContent=x>=1?o.fin:'\\u20B9'+inr(o.from+(o.to-o.from)*k);continue}
  st.visibility=x<=0?'hidden':'inherit';
  if(o.fx=='pop'){st.opacity=cl(x*2.5).toFixed(3);st.transform='scale('+(0.9+0.1*back(x)).toFixed(4)+')'}
  else if(o.fx=='fade'){st.opacity=k.toFixed(3)}
  else if(o.fx=='wipe'){st.clipPath='inset(-10% '+((1-k)*100).toFixed(2)+'% -10% 0)'}
  else if(o.fx=='grow'){st.transform='scaleY('+k.toFixed(4)+')'}
 }
 hand.style.visibility=pivot.style.visibility=hv?'visible':'hidden';      // never over the opening screen
 hand.style.transform='rotate('+ha.toFixed(1)+'deg)';
};
window.seek(0);
"""


def reel_timeline(r):
    """-> (kinds, scene windows [(start, end)], DUR, COVER_T) for today's rates (no silver screen when silver is not confirmed)"""
    kinds = ["gold"] + (["silver"] if r.get("silver") else [])
    win = [(round(i * SCENE, 2), round((i + 1) * SCENE, 2)) for i in range(len(kinds))]
    end0 = win[-1][1]
    win.append((end0, round(end0 + END, 2)))
    return kinds, win, win[-1][1], COVER


def reel_page(p, r):
    kinds, win, dur, cover = reel_timeline(r)

    def anim(s0, steps):
        def a(k):
            if k.startswith("bar"):
                i = int(k.lstrip("barv"))
                t = BAR0 + i * BAR_STEP
                st = (t + BAR_LEN - 0.1, 0.25, "fade") if k.startswith("barv") else (t, BAR_LEN, "grow")
            else:
                st = steps.get(k)
                if st and s0 == 0 and k in FIRST:
                    st = (-1.0, st[1], st[2])      # the reel's first frame already shows it
            return f' data-a="{s0 + st[0]:.2f},{st[1]},{st[2]}"' if st else ""
        return a

    scenes = []
    for i, kind in enumerate(kinds):
        a = anim(win[i][0], STEPS)
        b = blocks(p, r, kind, a)
        scenes.append(f'<div class="scene {kind}"><div class="metal"></div>{b["top"] % b["date"]}<div class="col">'
                      f'<div class="kickrow">{b["kick"]}</div>{b["title"]}{b["hero"]}{b["rows"]}'
                      f'<div class="low">{b["week"]}{b["tip"]}<div class="src"{a("src")}>{b["market"]}</div></div></div>'
                      f'<div class="base">{dial()}</div></div>')
    a = anim(win[-1][0], END_STEPS)
    both = "தங்கம், வெள்ளி" if len(kinds) > 1 else "தங்கம்"
    scenes.append(f'<div class="scene end"><div class="deco">{dial()}</div>'
                  f'<svg class="lring" viewBox="0 0 {int(LOGO_R * 2 + 24)} {int(LOGO_R * 2 + 24)}"><circle cx="{LOGO_R + 12}" cy="{LOGO_R + 12}" '
                  f'r="{LOGO_R}"/></svg><img src="file://{Path(p["logo"]).resolve()}"{a("elogo")}>'
                  f'<div class="nm"{a("ename")}>{brand_html(p)}</div><div class="sub"{a("esub")}>தினமும் {both} விலை நிலவரம்</div>'
                  f'<div class="fw"><span{a("efollow")}>Follow @{p["handle"]}</span></div></div>')
    js = (f'window.DUR={dur};window.COVER_T={cover};const SC={json.dumps(win)},WIPE={WIPE},SWEEP={json.dumps(SWEEP)},'
          f'ARC_C={ARC_C},LRC={round(2 * 3.14159265 * LOGO_R, 1)};' + REEL_JS)
    return (f'<!doctype html><html><head><meta charset="utf-8"><style>{css()}{REEL_CSS}</style></head><body class="reel">'
            f'{"".join(scenes)}<div class="hand"></div><div class="pivot"></div><script>{js}</script></body></html>')
