"""owner 20 Nov: the daily RASIPALAN REEL (no carousel) in the same 360 pattern as the gold & silver rate reel - music only, no voice.

Built from the gold reel's parts (goldrate/gold360_render.py: the 360 maroon + gold brand band with the page logo, the 360-degree clock
dial, the clockwise clock-hand wipe from one screen to the next, the follow card with the 360 ring round the logo) on the warm gold
field. Screens:
  1. today's panchangam (shown from frame 0 - the reel's cover): date, திதி, நட்சத்திரம், நல்ல நேரம், ராகு காலம், எமகண்டம், சந்திராஷ்டமம்
  2-13. the 12 rasis, one each: the rasi medallion (its symbol on a gold coin with the clock dial; the ring sweeps a full turn), the
        name, today's stars, the four lines (தொழில் / பணம் / குடும்பம் / உடல்நலம்), lucky number + colour, the remedy; the rasi of
        today's சந்திராஷ்டமம் carries a gentle "கவனம்" badge; the base band shows all 12 symbols with today's one lit
  14. the follow card
reel_page(p, ctx) -> html   p = the page (town, name1, handle, logo - goldrate gold_daily.page_cfg); ctx = {"p": panchangam,
                            "rasis": rasi_writer.write(...)}. window.DUR, window.seek(t), window.COVER_T as in the gold reel."""
import json
import sys
from html import escape as E
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "goldrate"))
import gold360_render as G      # noqa: E402
from rasi_render import GLYPH, LUCKY_NUM, LUCKY_COL, RASI_EN      # noqa: E402

MAROON, MAROON2, GOLD = G.MAROON, G.MAROON2, G.GOLD
OPEN = 3.6       # the panchangam screen
SCENE = 3.2      # one rasi
END = 1.6        # the follow card
LABELS = [("work", "தொழில்"), ("money", "பணம்"), ("family", "குடும்பம்"), ("health", "உடல்நலம்")]
P_STEPS = {"logo": (0.0, 0.2, "pop"), "brand": (0.0, 0.2, "fade"), "date": (0.0, 0.2, "fade"), "kick": (0.0, 0.2, "fade"),
           "title": (0.0, 0.25, "wipe"), "prow0": (0.0, 0.2, "fade"), "prow1": (0.0, 0.2, "fade"), "prow2": (0.0, 0.2, "fade"),
           "prow3": (0.0, 0.2, "fade"), "prow4": (0.0, 0.2, "fade"), "prow5": (0.0, 0.2, "fade"), "prow6": (0.0, 0.2, "fade"),
           "pnote": (0.0, 0.2, "fade")}
R_STEPS = {"logo": (0.0, 0.2, "pop"), "brand": (0.0, 0.2, "fade"), "date": (0.04, 0.2, "fade"), "kick": (0.04, 0.2, "fade"),
           "med": (0.08, 0.28, "pop"), "name": (0.12, 0.25, "wipe"), "en": (0.2, 0.2, "fade"), "stars": (0.3, 0.25, "pop"),
           "warn": (0.4, 0.2, "pop"), "rows": (0.38, 0.2, "fade"), "r0": (0.42, 0.2, "fade"), "r1": (0.52, 0.2, "fade"),
           "r2": (0.62, 0.2, "fade"), "r3": (0.72, 0.2, "fade"), "luck": (0.85, 0.25, "pop"), "rem": (0.95, 0.25, "pop")}

CSS = f"""
.rp .top small{{letter-spacing:5px}}
.rp .col{{top:352px}}
.ptitle{{overflow:hidden;font-size:78px;font-weight:900;line-height:1.3;color:{MAROON};white-space:nowrap;text-shadow:0 2px 0 rgba(255,255,255,.45)}}
.ptable{{margin-top:10px;background:linear-gradient(120deg,{MAROON2} 0%,{MAROON} 70%);border-radius:34px;padding:10px 38px;color:#fff;
 box-shadow:0 18px 36px rgba(58,7,11,.38),inset 0 0 0 3px #E9B233,inset 0 0 0 9px {MAROON}}}
.prow{{display:flex;align-items:center;gap:20px;min-height:138px;border-top:2px solid rgba(255,210,51,.22)}}
.prow:first-child{{border-top:0}}
.prow .k{{flex:none;width:310px;font-size:36px;font-weight:800;color:#F6E3A6;white-space:nowrap}}
.prow .v{{flex:1;min-width:0;overflow:hidden;font-size:44px;font-weight:900;line-height:1.3;white-space:nowrap}}
.prow .v small{{display:block;font-size:27px;font-weight:700;color:#E3C9CB}}
.prow.bad .v{{color:#FFB4A8}} .prow.good .v{{color:{GOLD}}}
.pnote{{margin-top:30px;font-size:33px;font-weight:800;color:{MAROON};text-align:center;white-space:nowrap}}
.rhead{{display:flex;align-items:center;gap:34px;margin-top:18px}}
.med{{position:relative;flex:none;width:250px;height:250px;border-radius:50%;display:flex;align-items:center;justify-content:center;
 background:radial-gradient(circle at 34% 28%,#FFF8D6,#F4C847 48%,#B47C14 100%);
 box-shadow:inset 0 0 0 9px rgba(255,255,255,.38),0 0 0 7px rgba(58,7,11,.85),0 18px 36px rgba(0,0,0,.45)}}
.med .dial{{position:absolute;left:12px;top:12px;width:226px;height:226px;color:rgba(58,7,11,.6)}}
.med .ring{{position:absolute;left:0;top:0;width:250px;height:250px;transform:rotate(-90deg)}}
.med .ring circle{{fill:none;stroke:{MAROON};stroke-width:5.5;stroke-linecap:round;stroke-dasharray:{G.ARC_C};stroke-dashoffset:0}}
.med .g{{position:relative;font-family:'Zod';font-size:132px;line-height:1;color:{MAROON};text-shadow:0 3px 0 rgba(255,255,255,.55)}}
.rname{{overflow:hidden;max-width:620px;font-size:118px;font-weight:900;line-height:1.2;color:{MAROON};white-space:nowrap;text-shadow:0 2px 0 rgba(255,255,255,.45)}}
.ren{{font-family:'Catamaran';font-size:32px;font-weight:900;letter-spacing:8px;color:{MAROON};opacity:.75}}
.stars{{display:inline-flex;gap:6px;margin-top:10px;background:{MAROON};border-radius:40px;padding:6px 22px}}
.stars b{{font-size:50px;line-height:1.2;color:{GOLD}}} .stars b.off{{color:rgba(255,210,51,.25)}}
.warn{{display:inline-block;margin-left:12px;vertical-align:top;margin-top:14px;background:#E53935;color:#fff;border-radius:30px;padding:6px 20px;
 font-size:26px;font-weight:800;white-space:nowrap;line-height:1.5}}
.rlines{{margin-top:40px;background:rgba(255,250,232,.7);border:2px solid rgba(255,255,255,.75);border-radius:28px;padding:4px 30px;
 box-shadow:0 10px 22px rgba(58,7,11,.12)}}
.rl{{display:flex;align-items:center;gap:22px;min-height:150px;border-top:2px solid rgba(58,7,11,.12)}}
.rl:first-child{{border-top:0}}
.rl em{{flex:none;width:210px;font-style:normal;text-align:center;background:{MAROON};color:{GOLD};border-radius:14px;padding:6px 0;
 font-size:33px;font-weight:900;line-height:1.5}}
.rl span{{flex:1;min-width:0;overflow:hidden;font-size:45px;font-weight:800;line-height:1.3;color:{MAROON};white-space:nowrap}}
.luck{{display:flex;gap:18px;margin-top:40px}}
.luck div{{flex:1;display:flex;align-items:center;justify-content:center;gap:14px;background:linear-gradient(180deg,{MAROON2},{MAROON});color:#fff;
 border-radius:24px;padding:20px 10px;font-size:34px;font-weight:800;white-space:nowrap;box-shadow:0 12px 24px rgba(58,7,11,.3)}}
.luck b{{font-family:'Catamaran';font-size:54px;font-weight:900;color:{GOLD};line-height:1}}
.luck i{{display:inline-block;width:40px;height:40px;border-radius:50%;border:3px solid #fff}}
.rem{{margin-top:34px;text-align:center;font-size:36px;font-weight:800;color:{MAROON};white-space:nowrap}}
.rem b{{background:{MAROON};color:{GOLD};border-radius:12px;padding:2px 16px;margin-left:8px}}
.zrow{{position:absolute;left:40px;right:40px;top:58px;display:flex;justify-content:space-between}}
.zrow span{{font-family:'Zod';font-size:46px;width:66px;height:66px;line-height:66px;text-align:center;border-radius:50%;color:rgba(255,210,51,.45)}}
.zrow span.on{{background:{GOLD};color:{MAROON};box-shadow:0 0 22px rgba(255,210,51,.8)}}
"""


def font_zod():
    return f"@font-face{{font-family:'Zod';src:url('file://{HERE / 'fonts' / 'noto-sans-symbols-symbols-400-normal.woff2'}') format('woff2')}}"


def anim(s0, steps, first=False):
    def a(k):
        st = steps.get(k)
        if not st:
            return ""
        t0 = -1.0 if first else s0 + st[0]      # the opening screen is complete from frame 0 (the cover)
        return f' data-a="{t0:.2f},{st[1]},{st[2]}"'
    return a


def top(p, date, a):
    return (f'<div class="top"><div class="deco">{G.dial()}</div><img src="file://{Path(p["logo"]).resolve()}"{a("logo")}>'
            f'<div class="brand"{a("brand")}><b>{G.brand_html(p)}</b><small>இன்றைய ராசிபலன்</small></div>'
            f'<div class="date"{a("date")}>{E(date)}</div></div>')


def zrow(i):
    return '<div class="zrow">' + "".join(f'<span class="{"on" if k == i else ""}">{g}&#xFE0E;</span>' for k, g in enumerate(GLYPH)) + "</div>"


def panch_scene(p, P, a):
    rows = [("திதி", P["tithi"], f'{P["paksha"]} • {P["tithi_end"]}', ""),
            ("நட்சத்திரம்", P["nakshatra"], P["nakshatra_end"], ""),
            ("நல்ல நேரம்", f'காலை {P["nalla_morning"]}', f'மாலை {P["nalla_evening"]}', "good") if P.get("nalla_morning") else None,
            ("ராகு காலம்", P["rahu"], "", "bad"), ("எமகண்டம்", P["emagandam"], "", "bad"),
            ("சூலம்", P.get("sulam") or "", f'பரிகாரம்: {P.get("sulam_parigaram") or ""}' if P.get("sulam") else "", ""),
            ("சந்திராஷ்டமம்", P["chandrashtamam"], "இந்த ராசிக்கு இன்று கவனம்", "bad")]
    rows = [r for r in rows if r and r[1]]
    body = "".join(f'<div class="prow {c}"{a("prow%d" % i)}><div class="k">{k}</div><div class="v"><div class="fit">{E(v)}</div>'
                   f'{f"<small>{E(s)}</small>" if s else ""}</div></div>' for i, (k, v, s, c) in enumerate(rows))
    day = f'{P["weekday_full"]} • {P["tamil_month"]} {P["tamil_day"]}'
    return (f'<div class="scene gold"><div class="metal"></div>{top(p, P["date_ta"], a)}<div class="col">'
            f'<div class="kick"{a("kick")}>{E(day)}</div><div class="ptitle fit"{a("title")}>இன்றைய பஞ்சாங்கம்</div>'
            f'<div class="ptable">{body}</div><div class="pnote"{a("pnote")}>அடுத்து: 12 ராசிகளுக்கும் இன்றைய பலன் ➜</div></div>'
            f'<div class="base">{G.dial()}{zrow(-1)}</div></div>')


def rasi_scene(p, P, i, r, a):
    stars = int(r.get("stars") or 3)
    st = "".join(f'<b class="{"" if k < stars else "off"}">★</b>' for k in range(5))
    warn = (f'<span class="warn"{a("warn")}>சந்திராஷ்டமம் • கவனம்</span>' if r.get("rasi") == P.get("chandrashtamam") else "")
    lines = "".join(f'<div class="rl"{a("r%d" % k)}><em>{lab}</em><span class="fit">{E(str(r.get(key) or ""))}</span></div>'
                    for k, (key, lab) in enumerate(LABELS))
    col_name, col_hex = LUCKY_COL[i]
    rem = r.get("remedy") or ""
    return (f'<div class="scene gold"><div class="metal"></div>{top(p, P["date_ta"], a)}<div class="col">'
            f'<div class="kick"{a("kick")}>{i + 1}/12 • இன்றைய ராசிபலன்</div>'
            f'<div class="rhead"><div class="med"{a("med")}>{G.dial()}<svg class="ring" viewBox="0 0 100 100"><circle cx="50" cy="50" '
            f'r="{G.ARC_R}"/></svg><span class="g">{GLYPH[i]}&#xFE0E;</span></div>'
            f'<div><div class="rname fit"{a("name")}>{E(r.get("rasi") or "")}</div><div class="ren"{a("en")}>{RASI_EN[i]}</div>'
            f'<div><span class="stars"{a("stars")}>{st}</span>{warn}</div></div></div>'
            f'<div class="rlines"{a("rows")}>{lines}</div>'
            f'<div class="luck"{a("luck")}><div>அதிர்ஷ்ட எண் <b>{LUCKY_NUM[i]}</b></div>'
            f'<div>நிறம் <i style="background:{col_hex}"></i> {col_name}</div></div>'
            + (f'<div class="rem"{a("rem")}>பரிகாரம்<b>{E(rem)}</b></div>' if rem else "") +
            f'</div><div class="base">{G.dial()}{zrow(i)}</div></div>')


def timeline():
    win = [(0.0, OPEN)] + [(round(OPEN + k * SCENE, 2), round(OPEN + (k + 1) * SCENE, 2)) for k in range(12)]
    e0 = win[-1][1]
    win.append((e0, round(e0 + END, 2)))
    return win, win[-1][1]


def reel_page(p, ctx):
    P, rasis = ctx["p"], ctx["rasis"]
    if len(rasis) != 12:
        raise ValueError("rasipalan reel: 12 rasis needed")
    win, dur = timeline()
    scenes = [panch_scene(p, P, anim(0, P_STEPS, first=True))]
    scenes += [rasi_scene(p, P, i, r, anim(win[i + 1][0], R_STEPS)) for i, r in enumerate(rasis)]
    a = anim(win[-1][0], G.END_STEPS)
    scenes.append(f'<div class="scene end"><div class="deco">{G.dial()}</div>'
                  f'<svg class="lring" viewBox="0 0 {int(G.LOGO_R * 2 + 24)} {int(G.LOGO_R * 2 + 24)}"><circle cx="{G.LOGO_R + 12}" '
                  f'cy="{G.LOGO_R + 12}" r="{G.LOGO_R}"/></svg><img src="file://{Path(p["logo"]).resolve()}"{a("elogo")}>'
                  f'<div class="nm"{a("ename")}>{G.brand_html(p)}</div><div class="sub"{a("esub")}>தினமும் ராசிபலன் • பஞ்சாங்கம்</div>'
                  f'<div class="fw"><span{a("efollow")}>Follow @{p["handle"]}</span></div></div>')
    fit = ("function fitAll(){document.querySelectorAll('.fit').forEach(e=>{let s=parseFloat(getComputedStyle(e).fontSize);"
           "while(e.scrollWidth>e.clientWidth+1&&s>16){s-=1;e.style.fontSize=s+'px'}})}"
           "const _seek0=window.seek;let _fitted=0;window.seek=t=>{if(!_fitted&&document.fonts.status==='loaded'){fitAll();_fitted=1}_seek0(t)};")
    js = (f'window.DUR={dur};window.COVER_T=0.5;const SC={json.dumps(win)},WIPE={G.WIPE},SWEEP={json.dumps(G.SWEEP)},'
          f'ARC_C={G.ARC_C},LRC={round(2 * 3.14159265 * G.LOGO_R, 1)};' + G.REEL_JS.replace(".emb .ring circle", ".emb .ring circle,.med .ring circle") + fit)      # long lines shrink to fit their box
    return (f'<!doctype html><html><head><meta charset="utf-8"><style>{G.css()}{font_zod()}{G.REEL_CSS}{CSS}</style></head>'
            f'<body class="reel rp">{"".join(scenes)}<div class="hand"></div><div class="pivot"></div><script>{js}</script></body></html>')
