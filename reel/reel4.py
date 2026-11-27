"""திருச்சி 360 — news reel v4 (the design the posting job uses: poster/config.json "reel_design": "v4").
Usage: python3 reel4.py spec.json out.mp4 [page]      (same spec as reel3.py; page = trichy, the only page)

What changed from v3 (why):
- Everything that matters sits inside Instagram's safe zone (y 150-1600, x 48-950): v3 put its logo strip at the very bottom and the caption box
  under the like/share buttons, where Instagram's own caption and buttons cover them.
- No scrolling ticker and no bottom logo bar: they repeated the headline and competed with the captions.
- A short headline stays on screen after the hook, so a viewer who joins late still knows what the story is (watch time is the first ranking signal).
- 5W fact cards (where / when / who / how many / action) with an icon, instead of one yellow sticker: the details people ask for in comments.
- Captions are whole short phrases (never a sentence cut in the middle), large, outlined, the spoken word highlighted, 2 lines max.
- Location pin from frame 1: local news is watched because it is about the viewer's own town.
- Viewer feedback 26 Oct: no top progress line; page logo top-RIGHT (Instagram shows the profile picture on the left); footer logo strip at the
  bottom; the existing follow end card; the reel opens with a one-line story, a short beat, then the full news.
Env PREVIEW_TTS=edge: preview voice from edge-tts (no local Tamil voice model needed); the posting job keeps tts.py.
Coimbatore 360: FREE voice only (Valluvar, edge-tts; AI4Bharat if it fails - never Google), and ONE picture per story: every camera
shot uses the same picture with its own move (zoom in / zoom out / pan / tilt / a different part of the picture), cross-dissolved.
"""
import json, sys, os, re, subprocess, html, math
from pathlib import Path
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
import reel as R
import reel3 as V3
import clock360      # owner 20 Nov: the 360 clock branding layer over every news reel (never fails the reel)
import design360      # owner 20 Nov: the design team's reel look (off; poster/config.json reel_look: handoff switches it on)
from digits import to_digits

def E(s):
    """on-screen text: drop the <b>..</b> marks the writer puts for the carousel (27 Oct: '<b>90,703</b>' showed in a reel)"""
    return html.escape(re.sub(r"</?[a-zA-Z][^>]*>", "", str(s)))

W, H, FPS = 1080, 1920, 30

CSS = R.ff("CT", "catamaran", [700, 800, 900]) + R.ff("NST", "noto-sans-tamil", [600, 700, 800]) + R.ff("BT", "baloo-thambi-2", [800]) + """
:root{--acc:#E3151B;--navy:#071433;--yellow:#FFD233}
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:1080px;height:1920px;overflow:hidden;background:#000}
body{font-family:'NST','CT',sans-serif;color:#fff;position:relative}
.ic{width:1em;height:1em;display:block}
#stage{position:absolute;inset:0;overflow:hidden}
.pic{position:absolute;left:0;top:0;width:1080px;height:1920px;object-fit:cover;opacity:0;will-change:transform,filter}
#shade{position:absolute;inset:0;z-index:5;background:linear-gradient(180deg,rgba(3,8,22,.80) 0%,rgba(3,8,22,.35) 18%,rgba(3,8,22,0) 34%,rgba(3,8,22,0) 50%,rgba(3,8,22,.30) 62%,rgba(3,8,22,.66) 78%,rgba(3,8,22,.88) 100%)}
#flash{position:absolute;inset:0;z-index:7;background:#fff;opacity:0}
/* top: story-style progress segments (one per sentence) */
/* header */
#hdr{position:absolute;left:48px;top:150px;z-index:30;display:flex;align-items:center;gap:22px}
#plogo{position:absolute;right:48px;top:140px;width:128px;height:128px;border-radius:50%;border:4px solid #fff;z-index:30;box-shadow:0 8px 24px rgba(0,0,0,.5)}
#foot{position:absolute;left:44px;bottom:28px;width:300px;height:auto;z-index:35;pointer-events:none;opacity:.92}
#hdr .nm{font:800 50px/1.05 'BT','NST';text-shadow:0 3px 12px rgba(0,0,0,.7)}
#hdr .sub{display:flex;align-items:center;gap:12px;margin-top:6px;font:700 30px 'NST','CT';color:#E8ECF5;text-shadow:0 2px 8px rgba(0,0,0,.8)}
#hdr .tag{background:var(--acc);color:#fff;padding:4px 16px 0;border-radius:8px;font:800 28px 'NST','CT'}
/* location pin (frame 1) */
#pin{position:absolute;left:48px;top:300px;z-index:30;display:flex;align-items:center;gap:14px;max-width:880px;background:rgba(255,255,255,.96);color:var(--navy);
  padding:12px 28px 8px 18px;border-radius:999px;font:800 40px/1.2 'NST','CT';box-shadow:0 10px 30px rgba(0,0,0,.45)}
#pin .ic{font-size:40px;color:var(--acc);flex:none;margin-top:-4px}
#pin span{display:block;white-space:normal;overflow-wrap:break-word;max-width:800px;line-height:1.25}
/* hook (first seconds) */
#hook{position:absolute;left:48px;right:48px;top:560px;z-index:22;text-align:left;opacity:0}
#hook .h1{font:900 104px/1.1 'CT','NST';color:#fff;-webkit-text-stroke:14px #000;paint-order:stroke fill;text-shadow:0 10px 30px rgba(0,0,0,.5)}
#hook .h2{display:inline-block;margin-top:22px;font:900 84px/1.15 'CT','NST';color:var(--navy);background:var(--yellow);padding:10px 26px 0;border-radius:14px;box-shadow:0 12px 34px rgba(0,0,0,.45)}
/* persistent mini headline after the hook */
#mini{position:absolute;left:48px;right:130px;top:410px;z-index:22;opacity:0;font:800 46px/1.28 'NST','CT';color:#fff;
  border-left:10px solid var(--yellow);padding:4px 0 0 22px;text-shadow:0 3px 14px rgba(0,0,0,.85)}
/* 5W fact cards */
.card{position:absolute;left:48px;top:640px;width:820px;z-index:23;opacity:0;display:flex;align-items:stretch;background:#fff;border-radius:26px;
  box-shadow:0 18px 50px rgba(0,0,0,.5);overflow:hidden}
.card .ico{flex:none;width:150px;display:flex;align-items:center;justify-content:center;background:var(--acc);color:#fff;font-size:72px}
.card .tx{padding:22px 30px 16px;display:flex;flex-direction:column;justify-content:center;gap:4px;min-width:0;flex:1 1 auto}
.card .lb{font:800 30px 'NST','CT';color:var(--acc);letter-spacing:.5px}
.card .vl{font:800 52px/1.25 'NST','CT';color:var(--navy);overflow-wrap:break-word;word-break:normal}
/* captions: whole phrases, outlined, in the safe zone above Instagram's caption */
#cap{position:absolute;left:56px;right:140px;top:1190px;height:330px;z-index:25}
.ph{position:absolute;left:0;right:0;bottom:0;text-align:left;font:800 70px/1.3 'CT','NST';color:#fff;opacity:0;-webkit-text-stroke:12px #000;paint-order:stroke fill;text-shadow:0 6px 18px rgba(0,0,0,.6)}
.ph span{display:inline-block;transform-origin:50% 70%;margin-right:.32em}      /* owner 27 Nov: .22em ran Tamil words together */
.ph span.on{color:var(--yellow)}
/* full-details summary (last news sentence): every key fact in one place - people pause on it or screenshot it */
#sum{position:absolute;left:48px;right:48px;top:540px;z-index:24;opacity:0;background:rgba(255,255,255,.97);border-radius:30px;overflow:hidden;box-shadow:0 20px 60px rgba(0,0,0,.55)}
#sum .st{background:var(--acc);color:#fff;font:900 46px 'CT','NST';padding:18px 34px 10px;display:flex;align-items:center;gap:16px}
#sum .st .ic{font-size:42px;margin-top:-6px}
#sum .row{display:flex;align-items:center;gap:22px;padding:14px 30px 8px;border-top:2px solid #E6E9F0;opacity:0}
#sum .row .ic{flex:none;font-size:42px;color:var(--acc);margin-top:-6px}
#sum .row .l{flex:none;width:200px;font:800 30px/1.2 'NST','CT';color:#6B7280;overflow:hidden}
#sum .row .v{font:800 38px/1.3 'NST','CT';color:var(--navy)}
/* end card */
#end{position:absolute;inset:0;z-index:40;opacity:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:34px;text-align:center;
  padding:0 70px 260px;background:rgba(3,8,22,.62)}
#end img{width:250px;height:250px;border-radius:50%;border:6px solid #fff;box-shadow:0 14px 50px rgba(0,0,0,.6)}
#end .e1{font:900 76px/1.25 'CT','NST'}
#end .e2{background:var(--red,#E3151B);font:900 56px 'CT','NST';padding:16px 46px 8px;border-radius:999px}
#end .e4{font:800 44px 'NST','CT';color:#fff;background:rgba(0,0,0,.35);padding:12px 30px 6px;border-radius:16px}
#end .e3{font:800 50px 'CT','NST';color:var(--yellow)}
#end .e5{font:700 36px 'NST','CT';color:#fff;background:rgba(0,0,0,.45);padding:10px 26px 4px;border-radius:14px}      /* owner 11 Nov: news source */
#hdr .src{font:800 26px 'NST','CT';color:#fff;background:rgba(255,255,255,.18);padding:4px 12px 0;border-radius:8px;white-space:nowrap;max-width:820px;overflow:hidden;text-overflow:ellipsis}
#hdr .sub{flex-wrap:nowrap}
#hdr .sub .dt,#hdr .src{display:inline-flex;align-items:center;gap:8px}      /* owner 20 Nov: 📅 date, then 📰 Source: paper on its own line */
#hdr .src{margin-top:8px}
#hdr .sub .ic,#hdr .src .ic{width:.9em;height:.9em;color:#FFD233;fill:#FFD233;flex:none;display:block}
#end .send{display:flex;align-items:center;gap:24px;background:#fff;color:var(--navy);padding:22px 40px 16px;border-radius:28px;font:900 58px/1.2 'CT','NST';box-shadow:0 14px 40px rgba(0,0,0,.5)}
#end .send .ic{font-size:64px;color:var(--acc);flex:none;margin-top:-6px}
#end .fol{display:flex;align-items:center;gap:18px;background:var(--acc);font:900 52px 'CT','NST';padding:16px 44px 10px;border-radius:999px}
#end .fol .ic{font-size:46px;margin-top:-6px}
#end .pl{font:800 44px 'NST','CT';color:var(--yellow)}
"""

# three looks for the same layout and timing (REEL_STYLE=A|B|C, or config "reel_style"); A = the original v4 look
STYLES = {
    "A": "",
    # B - TV broadcast: red headline band, yellow tags, dark cards, captions on a black bar
    "B": """
#hdr{background:rgba(7,20,51,.88);padding:12px 26px 12px 12px;border-radius:999px 24px 24px 999px}

#pin{background:var(--yellow);color:var(--navy)}
#pin .ic{color:var(--navy)}
#hook{text-align:center}
#hook .h1{display:inline-block;background:var(--acc);color:#fff;-webkit-text-stroke:0;padding:18px 34px 6px;border-radius:12px;font-size:92px;text-shadow:none;box-shadow:0 14px 40px rgba(0,0,0,.5)}
#hook .h2{background:#fff;color:var(--navy)}
#mini{left:0;right:0;top:405px;background:var(--acc);border-left:0;padding:14px 48px 6px;font-size:42px;text-shadow:none;box-shadow:0 10px 30px rgba(0,0,0,.4)}
.card{background:rgba(7,20,51,.94);border:3px solid var(--yellow)}
.card .ico{background:var(--yellow);color:var(--navy)}
.card .lb{color:var(--yellow)}
.card .vl{color:#fff}
#cap{left:48px;right:48px}
.ph{text-align:center;-webkit-text-stroke:0;background:rgba(0,0,0,.78);padding:16px 30px 6px;border-radius:16px;font-size:62px;text-shadow:none;border-bottom:8px solid var(--acc)}
#sum{background:rgba(7,20,51,.96);border:3px solid var(--yellow)}
#sum .st{background:var(--yellow);color:var(--navy)}
#sum .row{border-top:2px solid rgba(255,255,255,.12)}
#sum .row .ic{color:var(--yellow)}
#sum .row .l{color:#AAB4C8}
#sum .row .v{color:#fff}
#end .send{background:var(--yellow)}
""",
    # C - minimal glass: centred text, frosted cards, more of the photo visible
    "C": """
#shade{background:linear-gradient(180deg,rgba(0,0,0,.65) 0%,rgba(0,0,0,0) 26%,rgba(0,0,0,0) 55%,rgba(0,0,0,.55) 75%,rgba(0,0,0,.85) 100%)}
#hdr{left:0;right:0;justify-content:center}

#hdr .nm{font-size:44px}
#hdr .tag{background:transparent;border:2px solid #fff;padding:2px 14px 0}
#pin{left:0;right:0;margin:0 auto;width:fit-content;transform-origin:50% 50%;background:rgba(255,255,255,.16);color:#fff;border:2px solid rgba(255,255,255,.45);backdrop-filter:blur(16px);box-shadow:none}
#pin .ic{color:var(--yellow)}
#hook{text-align:center;top:640px}
#hook .h1{-webkit-text-stroke:0;font-size:100px;text-shadow:0 6px 40px rgba(0,0,0,.85)}
#hook .h2{background:transparent;color:var(--yellow);box-shadow:none;padding:0;border-bottom:8px solid var(--yellow);border-radius:0;font-size:80px}
#mini{left:90px;right:90px;text-align:center;border-left:0;padding:0;font-size:40px;top:420px;color:#F1F3F8}
.card{left:90px;width:900px;background:rgba(255,255,255,.14);backdrop-filter:blur(22px);border:2px solid rgba(255,255,255,.4);box-shadow:0 20px 60px rgba(0,0,0,.35)}
.card .ico{width:130px;background:transparent;color:var(--yellow);font-size:66px}
.card .lb{color:var(--yellow)}
.card .vl{color:#fff;text-shadow:0 2px 10px rgba(0,0,0,.4)}
#cap{left:60px;right:60px}
.ph{text-align:center;-webkit-text-stroke:0;font-size:68px;text-shadow:0 4px 24px rgba(0,0,0,.95),0 2px 4px rgba(0,0,0,.9)}
.ph span.on{color:#fff;text-decoration:underline;text-decoration-color:var(--yellow);text-decoration-thickness:8px;text-underline-offset:12px}
#sum{background:rgba(20,24,36,.55);backdrop-filter:blur(26px);border:2px solid rgba(255,255,255,.35)}
#sum .st{background:transparent;border-bottom:2px solid rgba(255,255,255,.3)}
#sum .row{border-top:1px solid rgba(255,255,255,.15)}
#sum .row .ic{color:var(--yellow)}
#sum .row .l{color:#C9D0DE}
#sum .row .v{color:#fff}
#end .send{background:rgba(255,255,255,.95)}
""",
}

# ==== owner 13 Nov: PREMIUM STORY PANEL (new pages; config "reel_style": "P") ==========================================================
# Photo in the top 60 %, an emerald panel below holds the headline and captions (text never sits on the photo); champagne-gold accent,
# ivory cards, serif Tamil headline; NO black anywhere. Motion: district map with the town pin (first seconds), headline word by word,
# count-up numbers, karaoke caption pill, one news-type layer (power-cut time bar / accident sweep / rain / police band), smooth loop,
# light sound effects. Voice, timing, captions and every fact are exactly as before - only the look and the motion layer change.
PREMIUM_ACCENT = "#C9A24B"


def _premium_fonts():
    out = []
    av = R.NM / "@fontsource-variable" / "anek-tamil" / "files"      # condensed news cut = font-stretch 75 %
    for sub, rng in (("tamil", ""), ("latin", "unicode-range:U+0000-00FF,U+2022,U+2013,U+2014;")):
        f = av / f"anek-tamil-{sub}-standard-normal.woff2"
        if f.exists():
            out.append(f"@font-face{{font-family:'AT';font-weight:100 800;font-stretch:75% 125%;src:url('file://{f}') format('woff2-variations');{rng}}}")
    return "\n".join(out) + R.ff("NSR", "noto-serif-tamil", [700, 800])


STYLES["P"] = _premium_fonts() + """
:root{--acc:#C9A24B;--navy:#0B3B2E;--yellow:#F3DFA2}
body{background:#0B3B2E}
#stage{height:1150px;border-bottom:8px solid #C9A24B}
.pic{height:1150px}
#shade{bottom:auto;height:1150px;background:linear-gradient(180deg,rgba(11,59,46,.85) 0%,rgba(11,59,46,.15) 24%,rgba(11,59,46,0) 40%,rgba(11,59,46,0) 82%,rgba(11,59,46,.55) 100%)}
#flash{display:none}
#hdr .nm{font:800 46px/1 'NSR','NST';letter-spacing:1px;color:#F3DFA2;text-shadow:0 2px 12px rgba(4,32,24,.6)}
#hdr .sub{font:600 27px 'AT','NST';color:rgba(255,248,236,.85);gap:16px;margin-top:10px;text-shadow:0 2px 8px rgba(4,32,24,.8)}
#hdr .tag{background:linear-gradient(100deg,#C9A24B,#F3DFA2);color:#0B3B2E;border-radius:4px;padding:6px 14px 1px;font:800 27px 'AT','NST'}
#hdr .src{background:none;padding:0;color:rgba(255,248,236,.85);font:600 27px 'AT','NST'}
#plogo{width:112px;height:112px;top:146px;border:3px solid #C9A24B;box-shadow:0 8px 24px rgba(4,32,24,.5)}
#pin{top:296px;max-width:700px;background:rgba(11,59,46,.74);box-shadow:none;color:#FFF8EC;padding:10px 24px 6px 16px;gap:10px;
  font:700 38px/1.2 'AT','NST';font-stretch:87.5%;border:1.5px solid rgba(201,162,75,.6)}
#pin span{max-width:620px}
#pin .ic{color:#F3DFA2}
#hook{top:1196px;left:56px;right:56px}
#hook .h1{font:800 92px/1.12 'NSR','NST';color:#FFF8EC;-webkit-text-stroke:0;letter-spacing:0;text-shadow:none}
#hook .h1 .w{display:inline-block}
#hook .h2{margin-top:18px;background:linear-gradient(100deg,#C9A24B,#F3DFA2 48%,#C9A24B);color:#0B3B2E;border-radius:6px;padding:10px 24px 2px;
  font:800 60px/1.1 'AT','CT';font-stretch:87.5%;box-shadow:none}
#mini{top:1196px;left:56px;right:56px;font:700 44px/1.28 'NSR','NST';color:#FFF8EC;border-left:4px solid #C9A24B;padding:2px 0 0 22px;text-shadow:none}
#cap{top:1330px;height:262px;left:56px;right:56px}
.ph{-webkit-text-stroke:0;font:800 62px/1.24 'AT','CT';font-stretch:87.5%;color:#FFF8EC;text-shadow:none}
.ph span{padding:0 8px;margin-right:.12em;border-radius:6px}
.ph span.on{color:#0B3B2E;background:linear-gradient(100deg,#C9A24B,#F3DFA2)}
.card{top:700px;background:#FFF8EC;border:1.5px solid #C9A24B;border-radius:18px;box-shadow:0 24px 60px rgba(4,32,24,.45)}
.card .ico{background:#0B3B2E;color:#F3DFA2;width:128px;margin:14px 0 14px 14px;border-radius:12px;font-size:60px}
.card .tx{padding:20px 32px 16px 24px}
.card .lb{font:700 27px 'AT','NST';color:#8A6A23;letter-spacing:2px}
.card .vl{font:800 56px/1.15 'AT','NST';font-stretch:87.5%;color:#0B3B2E}
#sum{top:330px;background:#FFF8EC;border:1.5px solid #C9A24B;border-radius:20px;box-shadow:0 24px 60px rgba(4,32,24,.5)}
#sum .st{background:#0B3B2E;color:#F3DFA2;font:800 44px 'NSR','NST'}
#sum .row{border-top:1px solid rgba(201,162,75,.35)}
#sum .row .ic{color:#C9A24B}
#sum .row .l{font:700 28px/1.2 'AT','NST';color:#8A6A23}
#sum .row .v{font:700 40px/1.22 'AT','NST';font-stretch:87.5%;color:#0B3B2E}
#end{background:linear-gradient(170deg,rgba(20,86,63,.9),rgba(11,59,46,.96))}
#end img{border:4px solid #C9A24B;box-shadow:0 14px 50px rgba(4,32,24,.6)}
#end .e1{font:800 80px/1.2 'NSR','NST';color:#FFF8EC}
#end .e2{background:linear-gradient(100deg,#C9A24B,#F3DFA2 48%,#C9A24B);color:#0B3B2E;border-radius:999px;font:800 54px 'AT','CT';padding:18px 48px 8px}
#end .e4{background:none;color:rgba(255,248,236,.88);font:700 40px 'AT','NST'}
#end .e3{color:#F3DFA2;font:800 46px 'AT','NST'}
#end .e5{background:none;color:rgba(255,248,236,.7);font:600 32px 'AT','NST'}
#foot{opacity:.8}
#fxmap{position:absolute;right:48px;top:292px;width:250px;z-index:21;background:rgba(11,59,46,.74);border:1.5px solid rgba(201,162,75,.6);border-radius:18px;padding:10px 10px 6px;opacity:0}
#fxmap svg{width:230px;height:230px;display:block;overflow:visible}
#fxd{fill:rgba(201,162,75,0);stroke:#F3DFA2;stroke-width:2.6;stroke-linejoin:round}
#fxdot{fill:#F3DFA2;stroke:#0B3B2E;stroke-width:3}
.fxring{fill:none;stroke:#F3DFA2;stroke-width:3}
#fxmap .lb{font:700 24px/1.15 'AT','NST';font-stretch:87.5%;color:#FFF8EC;text-align:center;margin-top:2px}
#fxmap .lb b{color:#F3DFA2}
#fxmap .osm{font:500 13px 'NST',sans-serif;color:rgba(255,248,236,.5);text-align:right}
#fxloop{position:absolute;inset:0;z-index:60;background:#0B3B2E;opacity:0;pointer-events:none}
#fxtl{position:absolute;left:48px;right:48px;top:960px;z-index:22;opacity:0;background:rgba(11,59,46,.9);border:1.5px solid rgba(201,162,75,.55);border-radius:14px;padding:18px 26px 16px}
#fxtl .row{display:flex;justify-content:space-between;align-items:center;font:800 34px 'AT','NST';font-stretch:87.5%;color:#FFF8EC}
#fxtl .row .ic{width:40px;height:40px;color:#F3DFA2}
#fxtl .bar{margin-top:12px;height:18px;border-radius:9px;background:rgba(255,248,236,.16);overflow:hidden}
#fxtl .fill{height:100%;width:0;background:linear-gradient(100deg,#C9A24B,#F3DFA2 48%,#C9A24B);border-radius:9px}
#fxsweep{position:absolute;left:-1400px;top:960px;width:1300px;height:140px;z-index:21;background:#B4232C;transform:skewX(-18deg);display:flex;align-items:center;
  justify-content:center;gap:24px;font:800 66px 'AT','CT';font-stretch:75%;color:#FFF8EC;letter-spacing:2px;opacity:0}
#fxsweep .ic{width:60px;height:60px}
#fxedge{position:absolute;left:0;right:0;top:0;height:1150px;z-index:6;pointer-events:none;opacity:0}
#fxrain{position:absolute;left:0;top:0;width:1080px;height:1150px;z-index:6;pointer-events:none}
#fxalert{position:absolute;left:48px;right:48px;top:960px;z-index:22;opacity:0;border-radius:14px;padding:16px 26px 10px;display:flex;align-items:center;gap:18px;
  font:800 40px 'AT','NST';font-stretch:87.5%;color:#FFF8EC;box-shadow:0 14px 40px rgba(4,32,24,.4)}
#fxalert .ic{width:46px;height:46px;flex:none}
.cnt{font-variant-numeric:tabular-nums}
"""
PREMIUM_ALERTS = {"rain": ("triangle-exclamation", "வானிலை எச்சரிக்கை", "#1E5FAF"), "crime": ("handcuffs", "போலீஸ் நடவடிக்கை", "#1E4A9C")}


# ==== owner 27 Nov: NEWS THEMES - each kind of news gets its own look (views test, poster/config.json views_test.topic_themes) =====
# Every text sits on a solid box or band (readable on any photo); each theme has its own colours and one mark of its own.
def _theme(c, extra=""):
    return f"""
#shade{{background:linear-gradient(180deg,{c['sh']}E6 0%,{c['sh']}66 20%,{c['sh']}00 34%,{c['sh']}00 50%,{c['sh']}88 64%,{c['sh']}F2 100%)}}
#hdr .tag{{background:{c['tag']};color:{c.get('tag_fg', '#fff')}}}
#pin{{background:{c['pin_bg']};color:{c['pin_fg']}}}
#pin .ic{{color:{c['pin_ic']}}}
#hook .h1{{display:inline-block;background:{c['h1_bg']};color:{c['h1_fg']};-webkit-text-stroke:0;text-shadow:none;padding:16px 30px 4px;border-radius:{c['r']};
  font-size:94px;box-shadow:0 14px 40px rgba(0,0,0,.45)}}
#hook .h2{{background:{c['h2_bg']};color:{c['h2_fg']};border-radius:{c['r']}}}
#mini{{background:{c['mini_bg']};color:{c['mini_fg']};border-left:10px solid {c['acc2']};padding:12px 24px 4px 22px;border-radius:0 {c['r']} {c['r']} 0;text-shadow:none;font-size:42px}}
.card{{background:{c['card_bg']};border-radius:{c['r']}}}
.card .ico{{background:{c['ico_bg']};color:{c['ico_fg']}}}
.card .lb{{color:{c['lb']}}}
.card .vl{{color:{c['card_fg']}}}
#cap{{left:48px;right:48px}}
.ph{{-webkit-text-stroke:0;text-shadow:none;background:{c['cap_bg']};color:{c['cap_fg']};padding:14px 28px 4px;border-radius:{c['r']};font-size:62px;border-bottom:8px solid {c['acc2']}}}
.ph span.on{{color:{c['cap_on']}}}
#sum{{background:{c['card_bg']};border-radius:{c['r']}}}
#sum .st{{background:{c['ico_bg']};color:{c['ico_fg']}}}
#sum .row .ic{{color:{c['lb']}}}
#sum .row .l{{color:{c['muted']}}}
#sum .row .v{{color:{c['card_fg']}}}
#end{{background:{c['end_bg']}}}
#end .e2{{background:{c['acc']};color:{c.get('e2_fg', '#fff')}}}
#end .e3{{color:{c['acc2']}}}
""" + extra


_SERIF = R.ff("NSR", "noto-serif-tamil", [700, 800])
THEME_ACCENT = {"ACC": "#D7141A", "POL": "#1D4ED8", "WX": "#0284C7", "PWR": "#FFB000", "TMP": "#B45309", "GOV": "#0F5132",
                "CIV": "#0F766E", "EDU": "#1D4ED8", "JOB": "#059669", "AGR": "#4D7C0F", "SPT": "#7C3AED"}
STYLES.update({
    # accident - hazard: red headline box, black/yellow hazard stripe, dark cards with a yellow edge
    "ACC": _theme(dict(sh="#0B0B0B", tag="#D7141A", pin_bg="#FFC700", pin_fg="#111", pin_ic="#D7141A", h1_bg="#D7141A", h1_fg="#fff",
                       h2_bg="#111", h2_fg="#FFC700", mini_bg="rgba(10,10,10,.86)", mini_fg="#fff", acc2="#FFC700", card_bg="#141414",
                       card_fg="#fff", ico_bg="#D7141A", ico_fg="#fff", lb="#FFC700", cap_bg="rgba(10,10,10,.86)", cap_fg="#fff",
                       cap_on="#FFC700", muted="#A3A3A3", end_bg="rgba(10,10,10,.82)", acc="#D7141A", r="8px"), """
#hook::before{content:"";display:block;width:540px;height:24px;margin-bottom:20px;border-radius:4px;background:repeating-linear-gradient(-45deg,#FFC700 0 30px,#111 30px 60px)}
.card{border:3px solid #FFC700}
"""),
    # crime / police - navy, red-blue light bar over the headline
    "POL": _theme(dict(sh="#06122B", tag="#1D4ED8", pin_bg="#fff", pin_fg="#06122B", pin_ic="#1D4ED8", h1_bg="#06122B", h1_fg="#fff",
                       h2_bg="#1D4ED8", h2_fg="#fff", mini_bg="rgba(6,18,43,.88)", mini_fg="#fff", acc2="#3B82F6", card_bg="#fff",
                       card_fg="#06122B", ico_bg="#06122B", ico_fg="#60A5FA", lb="#1D4ED8", cap_bg="rgba(6,18,43,.9)", cap_fg="#fff",
                       cap_on="#60A5FA", muted="#64748B", end_bg="rgba(6,18,43,.86)", acc="#1D4ED8", r="6px"), """
#hook::before{content:"";display:block;width:560px;height:20px;margin-bottom:18px;border-radius:10px;background:linear-gradient(90deg,#E11D48 0 50%,#2563EB 50% 100%);
  box-shadow:0 0 30px rgba(225,29,72,.7),0 0 30px rgba(37,99,235,.7)}
#hook .h1{border-left:14px solid #E11D48}
"""),
    # rain / weather - deep blue glass, centred, sky line
    "WX": _theme(dict(sh="#031B3A", tag="#0284C7", pin_bg="rgba(3,27,58,.86)", pin_fg="#fff", pin_ic="#38BDF8", h1_bg="rgba(3,27,58,.88)", h1_fg="#fff",
                      h2_bg="#38BDF8", h2_fg="#03203F", mini_bg="rgba(3,27,58,.86)", mini_fg="#fff", acc2="#38BDF8", card_bg="rgba(3,27,58,.92)",
                      card_fg="#fff", ico_bg="#0284C7", ico_fg="#fff", lb="#7DD3FC", cap_bg="rgba(3,27,58,.88)", cap_fg="#fff", cap_on="#7DD3FC",
                      muted="#A5C8E4", end_bg="rgba(3,27,58,.84)", acc="#0284C7", r="28px"), """
#hook{text-align:center}
#hook::before{content:"";display:block;margin:0 auto 18px;width:320px;height:14px;border-radius:7px;background:linear-gradient(90deg,#7DD3FC,#0284C7,#7DD3FC)}
.ph{text-align:center}
.card{border:2px solid rgba(125,211,252,.6)}
"""),
    # power cut - amber and black, double ring round the headline
    "PWR": _theme(dict(sh="#0A0A0A", tag="#FFB000", tag_fg="#111", pin_bg="#FFB000", pin_fg="#111", pin_ic="#111", h1_bg="#FFB000", h1_fg="#111",
                       h2_bg="#111", h2_fg="#FFB000", mini_bg="rgba(10,10,10,.88)", mini_fg="#fff", acc2="#FFB000", card_bg="#111",
                       card_fg="#fff", ico_bg="#FFB000", ico_fg="#111", lb="#FFB000", cap_bg="rgba(10,10,10,.88)", cap_fg="#fff",
                       cap_on="#FFB000", muted="#A3A3A3", end_bg="rgba(10,10,10,.86)", acc="#FFB000", e2_fg="#111", r="14px"), """
#hook .h1{box-shadow:0 0 0 6px #111,0 0 0 12px #FFB000,0 14px 40px rgba(0,0,0,.5)}
.card{border:3px solid #FFB000}
"""),
    # temple / festival - maroon, saffron and gold, serif, centred, double gold frame
    "TMP": _SERIF + _theme(dict(sh="#3B0A10", tag="#B45309", pin_bg="#FFF7E6", pin_fg="#7A1020", pin_ic="#D97706", h1_bg="#7A1020", h1_fg="#FFF3D6",
                                h2_bg="#F59E0B", h2_fg="#3B0A10", mini_bg="rgba(59,10,16,.88)", mini_fg="#FFF3D6", acc2="#E8C15A",
                                card_bg="#FFF7E6", card_fg="#5B0B16", ico_bg="#7A1020", ico_fg="#E8C15A", lb="#B45309",
                                cap_bg="rgba(59,10,16,.9)", cap_fg="#FFF3D6", cap_on="#F5C451", muted="#8A5A44", end_bg="rgba(59,10,16,.86)",
                                acc="#B45309", r="18px"), """
#hook{text-align:center}
#hook .h1{font-family:'NSR','NST';font-weight:800;border:5px double #E8C15A}
.ph{text-align:center}
.card{border:2px solid #E8C15A}
"""),
    # government / politics - official notice: white paper, green and maroon, serif headline
    "GOV": _SERIF + _theme(dict(sh="#0B1F17", tag="#0F5132", pin_bg="#fff", pin_fg="#0F5132", pin_ic="#8B1E2D", h1_bg="#fff", h1_fg="#0F2E22",
                                h2_bg="#0F5132", h2_fg="#fff", mini_bg="rgba(255,255,255,.95)", mini_fg="#0F2E22", acc2="#8B1E2D",
                                card_bg="#fff", card_fg="#0F2E22", ico_bg="#0F5132", ico_fg="#fff", lb="#8B1E2D",
                                cap_bg="rgba(255,255,255,.96)", cap_fg="#0F2E22", cap_on="#8B1E2D", muted="#6B7280",
                                end_bg="rgba(11,31,23,.86)", acc="#0F5132", r="4px"), """
#hook .h1{border-top:14px solid #8B1E2D;font-family:'NSR','NST';font-weight:800}
.ph span.on{background:#FDE68A;border-radius:6px}
#end .e3{color:#FDE68A}
"""),
    # civic (water, roads, buses, town council) - teal public notice
    "CIV": _theme(dict(sh="#042F2E", tag="#0F766E", pin_bg="#fff", pin_fg="#134E4A", pin_ic="#0F766E", h1_bg="#0F766E", h1_fg="#fff",
                       h2_bg="#fff", h2_fg="#0F766E", mini_bg="rgba(4,47,46,.88)", mini_fg="#fff", acc2="#5EEAD4", card_bg="#fff",
                       card_fg="#134E4A", ico_bg="#0F766E", ico_fg="#fff", lb="#0F766E", cap_bg="rgba(4,47,46,.88)", cap_fg="#fff",
                       cap_on="#5EEAD4", muted="#64748B", end_bg="rgba(4,47,46,.86)", acc="#0F766E", r="22px"), """
#hook .h1{border-radius:22px 22px 22px 0}
"""),
    # education - notebook: white page with the red margin line, blue
    "EDU": _theme(dict(sh="#0B1B4D", tag="#1D4ED8", pin_bg="#fff", pin_fg="#1E3A8A", pin_ic="#DC2626", h1_bg="#fff", h1_fg="#1E3A8A",
                       h2_bg="#1D4ED8", h2_fg="#fff", mini_bg="rgba(255,255,255,.95)", mini_fg="#1E3A8A", acc2="#FACC15", card_bg="#fff",
                       card_fg="#1E3A8A", ico_bg="#1D4ED8", ico_fg="#fff", lb="#DC2626", cap_bg="rgba(11,27,77,.88)", cap_fg="#fff",
                       cap_on="#FACC15", muted="#64748B", end_bg="rgba(11,27,77,.86)", acc="#1D4ED8", r="10px"), """
#hook .h1{border-left:12px solid #DC2626;box-shadow:inset 0 -10px 0 #BFDBFE,0 14px 40px rgba(0,0,0,.45)}
"""),
    # jobs - green with a yellow pill
    "JOB": _theme(dict(sh="#022C22", tag="#059669", pin_bg="#fff", pin_fg="#065F46", pin_ic="#059669", h1_bg="#059669", h1_fg="#fff",
                       h2_bg="#FDE047", h2_fg="#064E3B", mini_bg="rgba(2,44,34,.88)", mini_fg="#fff", acc2="#FDE047", card_bg="#fff",
                       card_fg="#064E3B", ico_bg="#059669", ico_fg="#fff", lb="#059669", cap_bg="rgba(2,44,34,.88)", cap_fg="#fff",
                       cap_on="#FDE047", muted="#6B7280", end_bg="rgba(2,44,34,.86)", acc="#059669", r="16px"), """
#hook .h2{border-radius:999px;padding:12px 40px 2px}
"""),
    # farming / prices - wheat and leaf green
    "AGR": _theme(dict(sh="#1F2A0A", tag="#4D7C0F", pin_bg="#FEF3C7", pin_fg="#3F2A0B", pin_ic="#4D7C0F", h1_bg="#FEF3C7", h1_fg="#3F2A0B",
                       h2_bg="#4D7C0F", h2_fg="#fff", mini_bg="rgba(31,42,10,.88)", mini_fg="#FEF3C7", acc2="#A3E635", card_bg="#FEF3C7",
                       card_fg="#3F2A0B", ico_bg="#4D7C0F", ico_fg="#FEF3C7", lb="#4D7C0F", cap_bg="rgba(31,42,10,.88)", cap_fg="#FEF3C7",
                       cap_on="#BEF264", muted="#78716C", end_bg="rgba(31,42,10,.86)", acc="#4D7C0F", r="20px"), """
#hook .h1{border-bottom:12px solid #4D7C0F}
"""),
    # sports / culture - purple and orange, slanted boxes
    "SPT": _theme(dict(sh="#1E0B3A", tag="#7C3AED", pin_bg="#fff", pin_fg="#4C1D95", pin_ic="#F97316", h1_bg="#6D28D9", h1_fg="#fff",
                       h2_bg="#F97316", h2_fg="#fff", mini_bg="rgba(30,11,58,.88)", mini_fg="#fff", acc2="#F97316", card_bg="#fff",
                       card_fg="#3B0764", ico_bg="#F97316", ico_fg="#fff", lb="#7C3AED", cap_bg="rgba(30,11,58,.88)", cap_fg="#fff",
                       cap_on="#FDBA74", muted="#6B7280", end_bg="rgba(30,11,58,.86)", acc="#7C3AED", r="6px"), """
#hook .h1,#hook .h2{transform:skewX(-6deg)}
"""),
})
# owner 27 Nov: C was hard to read on bright photos (white frosted cards, yellow underline over a busy picture) - dark glass instead
STYLES["C"] += """
#hook .h1{-webkit-text-stroke:12px rgba(0,0,0,.85);paint-order:stroke fill}
#hook .h2{background:rgba(0,0,0,.62);padding:10px 26px 0;border-radius:12px;border-bottom:0}
#pin{background:rgba(0,0,0,.55);border-color:rgba(255,255,255,.35)}
#mini{background:rgba(0,0,0,.6);padding:10px 22px 2px;border-radius:14px}
.card{background:rgba(8,12,24,.8);border-color:rgba(255,255,255,.3)}
.ph{-webkit-text-stroke:12px #000;paint-order:stroke fill}
#sum{background:rgba(8,12,24,.86)}
"""


def views_test_cfg():
    try:
        vt = json.loads((Path(__file__).resolve().parent.parent / "poster" / "config.json").read_text()).get("views_test") or {}
        return vt if vt.get("enabled") else {}
    except Exception:
        return {}


def news_topic(spec):
    """the topic insights uses (research_free/learned.py), from the category, headline and hook of this reel"""
    try:
        rf = str(Path(__file__).resolve().parent.parent / "research_free")
        if rf not in sys.path:
            sys.path.append(rf)
        import learned
        return learned.topic(" ".join([str(spec.get("cat") or ""), str(spec.get("mini") or "")] + [str(x) for x in (spec.get("hook") or [])]))
    except Exception:
        return "other"


SHARE_TOWNS = ("மணப்பாறை", "லால்குடி", "முசிறி", "துறையூர்", "ஸ்ரீரங்கம்", "திருவெறும்பூர்", "மண்ணச்சநல்லூர்", "சமயபுரம்", "தொட்டியம்", "துவாக்குடி")


def share_town(spec):
    """owner 27 Nov: the town whose people this news is for ('share with your Manapparai friends'), else Trichy"""
    loc = str(spec.get("location") or "")
    return next((t for t in SHARE_TOWNS if t in loc), "திருச்சி")


def theme_for(spec):
    """owner 27 Nov: the news theme of this reel's topic (views_test.topic_themes), '' = none (then the designs take turns)"""
    th = str((views_test_cfg().get("topic_themes") or {}).get(news_topic(spec)) or "").upper()
    return th if th in STYLES else ""


def test_styles():
    """owner 26 Nov: poster/config.json views_test.styles - the designs that take turns on this page ([] = one design)"""
    return [str(x).upper() for x in (views_test_cfg().get("styles") or []) if str(x).upper() in STYLES]


def reel_style(spec):
    """REEL_STYLE env, the story's own style, then poster/config.json "reel_style", else the original look A"""
    cfg = ""
    try:
        cfg = json.loads((Path(__file__).resolve().parent.parent / "poster" / "config.json").read_text()).get("reel_style", "")
    except Exception:
        pass
    return (os.environ.get("REEL_STYLE") or spec.get("style") or cfg or "A").upper()


def premium_kind(spec):
    """the one news-type layer of the premium look ('' = the shared motion only)"""
    t = " ".join([str(spec.get("cat") or ""), str(spec.get("mini") or "")] + [str(x) for x in (spec.get("hook") or [])])
    if re.search(r"மின்\s*தடை|மின்தடை|மின்\s*நிறுத்த", t):
        return "power"
    if re.search(r"விபத்து|மோதி|கவிழ்ந்", t):
        return "accident"
    if re.search(r"மழை|வானிலை|வெள்ள|புயல்", t):
        return "rain"
    if re.search(r"குற்ற|கைது|கஞ்சா|திருட்டு|கொலை|போலீஸ்", t):
        return "crime"
    return ""


def time_span(spec):
    """('காலை 9', 'மாலை 5') for the power-cut time bar, or None when the story does not say both ends clearly"""
    t = " ".join([str(spec.get("mini") or "")] + [str(x) for x in (spec.get("hook") or [])])
    got = []
    for w, n in re.findall(r"(காலை|மதியம்|பிற்பகல்|மாலை|இரவு)\s*(\d{1,2}(?:[.:]\d{2})?)", t):
        if f"{w} {n}" not in got:
            got.append(f"{w} {n}")
    return (got[0], got[1]) if len(got) >= 2 else None


def district_map(location):
    """(svg path, town x, town y or None, label html) from reel/assets/district_map.json (OpenStreetMap), or None"""
    try:
        m = json.loads((Path(__file__).resolve().parent / "assets" / "district_map.json").read_text(encoding="utf-8"))
    except Exception:
        return None
    loc = str(location or "")
    town = next((t for t in sorted(m.get("towns", {}), key=len, reverse=True) if t in loc), "")
    xy = m["towns"].get(town) if town else None
    label = (f"<b>{E(town)}</b> · " if town else "") + E(m.get("district_ta", "")) + " மாவட்டம்"
    return m["path"], (xy[0] if xy else None), (xy[1] if xy else None), label, m.get("credit", "© OpenStreetMap")


PREMIUM_JS = """
<script>
(function(){
const cl=x=>Math.max(0,Math.min(1,x)), ease=x=>1-Math.pow(1-x,3), back=x=>{const c=1.70158,c3=c+1;return 1+c3*Math.pow(x-1,3)+c*Math.pow(x-1,2)};
const KIND="__KIND__";
const h1=document.querySelector('#hook .h1');
h1.innerHTML=h1.textContent.trim().split(/\\s+/).map(w=>'<span class="w">'+w+'</span>').join(' ');
const words=[...h1.querySelectorAll('.w')];
const RX=/(\\d[\\d,]*)(?=\\s*(பேர்|லட்ச|கோடி|கிலோ|டன்|சதவீத|மூட்டை|பணியிட|ஏக்கர்|அடி|%))/g;
document.querySelectorAll('#hook .h2,#mini,.card .vl,#sum .v').forEach(el=>{el.innerHTML=el.innerHTML.replace(RX,(m,n)=>'<span class="cnt" data-n="'+n.replace(/,/g,'')+'">'+n+'</span>');});
function startOf(el){
  if(el.closest('#hook'))return 0.35; if(el.closest('#mini'))return D.hook_end;
  const c=el.closest('.card'); if(c){const s=D.sents[+c.id.slice(1)];return Math.max(s.a+0.15,D.hook_end+0.1);}
  const r=el.closest('.row'); if(r)return D.sum_a+0.25+(+r.id.slice(1))*0.28; return 0;}
const cnts=[...document.querySelectorAll('.cnt')].map(e=>({e,n:+e.dataset.n,a:startOf(e)}));
const path=document.getElementById('fxd'), L=path?path.getTotalLength():0; if(path)path.style.strokeDasharray=L;
let placed=false;
const _r=window.renderAt;
window.renderAt=function(t){
  _r(t);
  const live=t<D.end_t?1:0, T=D.total;
  if(!placed){placed=true;      // the news-type band sits just above the headline panel
    const top_=document.querySelector('#hook .h1').getBoundingClientRect().top;
    ['fxtl','fxalert'].forEach(id=>{const e=document.getElementById(id); if(e)e.style.top=Math.max(560,Math.round(Math.min(1150,top_)-e.offsetHeight-40))+'px';});}
  document.getElementById('cap').style.opacity=t<D.hook_end?0:1;      // the headline and the captions share the panel: captions after the headline
  const m=document.getElementById('fxmap');
  if(m){m.style.opacity=live*ease(cl(t/0.25))*(1-cl((t-(D.hook_end-0.2))/0.35));
    path.style.strokeDashoffset=L*(1-ease(cl(t/0.7))); path.style.fill='rgba(201,162,75,'+(0.16*cl((t-0.45)/0.4))+')';
    const dot=document.getElementById('fxdot');
    if(dot){const dp=cl((t-0.65)/0.35); dot.setAttribute('opacity',dp>0?1:0); dot.setAttribute('transform','translate(0,'+(-46*(1-back(dp)))+')');
      for(let i=0;i<2;i++){const ph=((t-1.0-i*0.6)%1.2+1.2)%1.2/1.2, on=t>1.0+i*0.6, r=document.getElementById('fxr'+i);
        r.setAttribute('r',6+34*ph); r.setAttribute('opacity',on?0.8*(1-ph):0);}}}
  words.forEach((w,i)=>{const p=cl((t-0.05-i*0.09)/0.28); w.style.opacity=ease(p); w.style.transform='translateY('+(46*(1-ease(p)))+'px)';});
  cnts.forEach(c=>{const p=ease(cl((t-c.a)/0.8)); c.e.textContent=Math.round(c.n*p).toLocaleString('en-IN');});
  const tl=document.getElementById('fxtl');
  if(tl){const on=t>0.45&&t<D.hook_end; tl.style.opacity=on?ease(cl((t-0.45)/0.25))*(1-cl((t-(D.hook_end-0.25))/0.25)):0;
    tl.querySelector('.fill').style.width=(100*ease(cl((t-0.6)/1.1)))+'%';}
  const sw=document.getElementById('fxsweep');
  if(sw){sw.style.opacity=(t<0.95)?1:0; sw.style.left=(-1400+2700*ease(cl(t/0.9)))+'px';
    const g=document.getElementById('fxedge'), pulse=0.5+0.5*Math.sin(t*Math.PI*2/0.9);
    g.style.opacity=live; g.style.boxShadow='inset 0 0 '+(80+60*pulse)+'px '+(14+10*pulse)+'px rgba(180,35,44,'+(t<D.hook_end?0.5:0.2)+')';}
  const cv=document.getElementById('fxrain');
  if(cv){const x=cv.getContext('2d'); x.clearRect(0,0,1080,1150);
    if(live){x.strokeStyle='rgba(225,236,255,.42)'; x.lineWidth=3; x.lineCap='round';
      for(let i=0;i<150;i++){const h=Math.sin(i*12.9898)*43758.5453, fr=h-Math.floor(h), sp=1500+900*fr, len=50+60*fr;
        const px=(i*97.3+fr*400)%1180-50, py=((fr*1150+sp*t)%1300)-120;
        x.beginPath(); x.moveTo(px,py); x.lineTo(px-len*0.22,py+len); x.stroke();}}}
  const al=document.getElementById('fxalert');
  if(al){const on=t>0.45&&t<D.hook_end; al.style.opacity=on?(0.8+0.2*Math.sin(t*Math.PI*2/0.8))*ease(cl((t-0.45)/0.25))*(1-cl((t-(D.hook_end-0.25))/0.25)):0;}
  document.getElementById('fxloop').style.opacity=t<0.14?1-t/0.14:(t>T-0.4?cl((t-(T-0.4))/0.4):0);      // smooth replay
};
})();
</script>
"""


def _ic(name):
    """an icon, or nothing when the icon set is missing (an icon never stops a reel)"""
    try:
        return R.icon(name)
    except (SystemExit, Exception):
        return ""


def premium_layer(html_, spec):
    """the premium motion layer, added to the finished page (map, news-type layer, loop, script)"""
    kind = premium_kind(spec)
    h = '<div id="fxloop"></div>'
    dm = district_map(spec.get("location"))
    if dm:
        path, tx, ty, label, credit = dm
        pin = "" if tx is None else ("".join(f'<circle class="fxring" id="fxr{i}" cx="{tx}" cy="{ty}" r="6" opacity="0"/>' for i in range(2))
                                     + f'<circle id="fxdot" cx="{tx}" cy="{ty}" r="11" opacity="0"/>')
        h += f'<div id="fxmap"><svg viewBox="0 0 260 260"><path id="fxd" d="{path}"/>{pin}</svg><div class="lb">{label}</div><div class="osm">{E(credit)}</div></div>'
    if kind == "power" and time_span(spec):
        a, b = time_span(spec)
        h += f'<div id="fxtl"><div class="row"><span>{E(a)}</span>{_ic("bolt")}<span>{E(b)}</span></div><div class="bar"><div class="fill"></div></div></div>'
    if kind == "accident":
        h += f'<div id="fxedge"></div><div id="fxsweep">{_ic("car-burst")}<span>விபத்து</span></div>'
    if kind == "rain":
        h += '<canvas id="fxrain" width="1080" height="1150"></canvas>'
    if kind in PREMIUM_ALERTS:
        ic, tx_, col = PREMIUM_ALERTS[kind]
        h += f'<div id="fxalert" style="background:{col}">{_ic(ic)}<span>{tx_}</span></div>'
    return html_.replace("</script></body></html>", "</script>" + h + PREMIUM_JS.replace("__KIND__", kind) + "</body></html>")


def premium_sfx(work, spec, sents, hook_end, end_t):
    """light sound effects mixed under the voice (pin pop, card whoosh, accident alert, rain bed); never fails the reel"""
    import wave
    mix = work / "mix.wav"
    with wave.open(str(mix)) as w_:
        rate = w_.getframerate()
    gen = {"whoosh": "anoisesrc=d=0.45:c=pink:a=0.5,highpass=f=500,lowpass=f=4500,afade=t=in:d=0.18,afade=t=out:st=0.2:d=0.25",
           "pop": "sine=f=880:d=0.09,afade=t=out:st=0.02:d=0.07",
           "alert": "sine=f=740:d=0.16,apad=pad_dur=0.05,afade=t=out:st=0.1:d=0.06",
           "rainbed": "anoisesrc=d=%.2f:c=brown:a=0.35,lowpass=f=1800,highpass=f=200,afade=t=in:d=0.6,afade=t=out:st=%.2f:d=0.6" % (end_t, max(0.1, end_t - 0.6))}
    kind = premium_kind(spec)
    ev = [("pop", 0.68, 0.5)] + [("whoosh", max(s["a"] + 0.15, hook_end + 0.1) - 0.1, 0.3) for s in sents if s.get("has_card")]
    if kind == "accident":
        ev += [("whoosh", 0.0, 0.4), ("alert", 0.05, 0.22), ("alert", 0.3, 0.22)]
    if kind == "rain":
        ev += [("rainbed", 0.0, 0.3)]
    if kind in ("power", "rain", "crime"):
        ev += [("whoosh", 0.4, 0.25)]
    for n in {e[0] for e in ev}:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", gen[n], "-ar", str(rate), "-ac", "2", str(work / f"sfx_{n}.wav")], check=True)
    inputs, chains = [], []
    for i, (n, at, vol) in enumerate(ev):
        inputs += ["-i", str(work / f"sfx_{n}.wav")]
        ms = int(max(0.0, at) * 1000)
        chains.append(f"[{i + 1}:a]adelay={ms}|{ms},volume={vol}[s{i}]")
    fc = (f"[0:a]aformat=sample_rates={rate}:channel_layouts=stereo[v];" + ";".join(chains) + ";[v]" + "".join(f"[s{i}]" for i in range(len(ev)))
          + f"amix=inputs={len(ev) + 1}:normalize=0:duration=first[a]")
    out = work / "mix_sfx.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mix), *inputs, "-filter_complex", fc, "-map", "[a]", str(out)], check=True)
    out.replace(mix)
# ==== end of the premium story panel ===================================================================================================


ACCENT = {"மின் தடை": "#F59E0B", "மழை": "#1E88E5", "வானிலை": "#1E88E5", "வெள்ள": "#1E88E5", "விபத்து": "#E3151B", "குற்ற": "#B91C1C",
          "கோவில்": "#C2410C", "திருவிழா": "#C2410C", "வேலை": "#059669", "கல்வி": "#2563EB", "தாக்குதல்": "#DC2626"}

# what a fact is about -> icon + label (the label tells the viewer which of the 5W the card answers)
KINDS = [      # owner 27 Nov: a pattern matches a whole word start - "கரூர்" (Karur) gave a ₹ "தொகை" card, "தினமணி" a clock card
    (r"(?<![\u0B80-\u0BFF])ரூ\.?\s*\d|₹|\d[\d,.]*\s*(லட்சம்|கோடி)|ரூபாய்", "indian-rupee-sign", "தொகை"),
    (r"\d\s*மணி|நேரம்", "clock", "நேரம்"),
    (r"தேதி|ஜனவரி|பிப்ரவரி|மார்ச்|ஏப்ரல்|ஜூன்|ஜூலை|ஆகஸ்ட்|செப்டம்பர்|அக்டோபர்|நவம்பர்|டிசம்பர்|இன்று|நாளை", "calendar-days", "நாள்"),
    (r"மருத்துவமனை|சிகிச்சை", "hospital", "சிகிச்சை"),
    (r"கைது|போலீஸ்|போலீசார்|காவல்", "handcuffs", "நடவடிக்கை"),
    (r"வயது|குழந்தை|சிறுமி|சிறுவன்|மாணவ", "child", "யார்"),
    (r"\d+\s*பேர்|பலர்", "users", "எத்தனை பேர்"),      # owner 27 Nov: "மக்கள்" alone is not a count (it gave "எத்தனை பேர்" on a meeting)
    (r"நடவடிக்கை|கோரிக்கை|உத்தரவு|அறிவிப்பு", "bullhorn", "நடவடிக்கை"),
    (r"நகர்|சாலை|கிராம|ஊராட்சி|பகுதி", "location-dot", "இடம்"),
]


def accent_for(cat):
    for k, v in ACCENT.items():
        if k in (cat or ""):
            return v
    return "#E3151B"


def card_for(fact):
    """{"icon","label","text"} or a plain fact string -> card"""
    if isinstance(fact, dict):
        return fact if fact.get("text") else None
    t = re.sub(r"<[^>]+>", "", str(fact or "")).strip()
    if not t:
        return None
    for pat, ic, lb in KINDS:
        if re.search(pat, t):
            return {"icon": ic, "label": lb, "text": t}
    return {"icon": "circle-info", "label": "முக்கிய தகவல்", "text": t}


def phrases(words, maxw=4):
    """whole short phrases: break after punctuation, otherwise every ~maxw words; never leave one word alone"""
    out, cur = [], []
    for w in words:
        cur.append(w)
        if re.search(r"[,.!?।:]$", w[0]) or len(cur) >= maxw:
            out.append(cur); cur = []
    if cur:
        if out and len(cur) <= 2 and len(out[-1]) + len(cur) <= maxw + 2:
            out[-1] += cur
        else:
            out.append(cur)
    return out


def edge_lines(work, texts, voice="ta-IN-ValluvarNeural", rate="+8%", pitch="+0Hz"):
    """preview voice: edge-tts per line (numbers and abbreviations prepared exactly like the real voice)"""
    import tts
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "research_free"))
    import names
    for i, t in enumerate(texts):
        mp3, wav = work / f"line{i}.mp3", work / f"line{i}.wav"
        say = tts.clean(names.spoken(t))
        for k in range(4):      # the free voice service fails now and then: try again
            r = subprocess.run([sys.executable, "-m", "edge_tts", "--voice", voice, f"--rate={rate}", f"--pitch={pitch}", "--text", say, "--write-media", str(mp3)], timeout=90)
            if r.returncode == 0 and mp3.exists() and mp3.stat().st_size > 1000:
                break
            import time; time.sleep(5 * (k + 1))
        else:
            raise RuntimeError(f"preview voice failed for line {i}")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp3), "-af",
                        "silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse,loudnorm=I=-16:TP=-1.5",
                        "-ar", "22050", "-ac", "1", str(wav)], check=True)


def pick_voice(spec):
    """Coimbatore 360: FREE voice only - Valluvar (edge-tts ta-IN-ValluvarNeural) reads EVERY reel. Google's paid-tier voice (Charon) is
    never used, also when GOOGLE_TTS_API_KEY is set or poster/config.json still has "reel_voice_alt". Returns (voice, None);
    when Valluvar fails, main() falls back to the AI4Bharat voice (tts.py)."""
    cfg = voice_setting()
    vs = {"engine": "edge", "voice": "ta-IN-ValluvarNeural", "rate": "+12%", "pitch": "+4Hz", "outro_voice": "en-IN-PrabhatNeural"}
    for k in ("rate", "pitch", "outro_voice"):      # only the speed / pitch / English voice may come from config - never another engine
        v = cfg.get(k)
        if isinstance(v, str) and v and "Chirp" not in v and (k != "outro_voice" or v.endswith("Neural")):
            vs[k] = v
    ab = [v for v in (cfg.get("ab_voices") or []) if isinstance(v, str) and re.match(r"ta-(IN|MY|SG|LK)-\w+Neural$", v)]      # owner 27 Nov: every free Tamil edge voice
    if spec and len(ab) > 1:      # owner 26 Nov (Trichy views test): free edge voices A/B, the same story always gets the same voice
        import hashlib
        key = " ".join([str(spec.get("mini") or "")] + [str(x) for x in (spec.get("hook") or [])])
        vs["voice"] = ab[int(hashlib.md5(key.encode("utf-8")).hexdigest(), 16) % len(ab)]
    return vs, None


# ---- owner 27 Oct: words Tamil Nadu says in everyday English, not formal Tamil (voice + subtitles; headline cards stay as written)
EVERYDAY = [("காவல்துறையினர்", "போலீசார்"), ("காவலர்கள்", "போலீசார்"), ("போலீஸார்", "போலீசார்"), ("காவல் நிலைய", "போலீஸ் ஸ்டேஷன்"),
            ("காவல் ஆய்வாளர்", "இன்ஸ்பெக்டர்"), ("ஆட்சியர", "கலெக்டர"), ("பேருந்து நிலைய", "பஸ் ஸ்டாண்ட்"), ("பேருந்தில்", "பஸ்ஸில்"),
            ("பேருந்துகள்", "பஸ்கள்"), ("பேருந்து", "பஸ்"), ("இருசக்கர வாகனத்தில்", "டூவீலரில்"), ("இருசக்கர வாகனங்கள்", "டூவீலர்கள்"),
            ("இருசக்கர வாகனம்", "டூவீலர்"), ("இருசக்கர வாகன", "டூவீலர்")]


def everyday(t):
    if not t or not everyday_on():
        return t
    for a, b in EVERYDAY:
        t = t.replace(a, b)
    return t


def abbr_on():
    """config "reel_english_abbreviations" (default on): MLA / LPG / DSP shown in English letters on the reel"""
    try:
        return bool(json.loads((Path(__file__).resolve().parent.parent / "poster" / "config.json").read_text()).get("reel_english_abbreviations", True))
    except Exception:
        return True


def everyday_on():
    try:
        return bool(json.loads((Path(__file__).resolve().parent.parent / "poster" / "config.json").read_text()).get("reel_everyday_words", True))
    except Exception:
        return True


MONTHS_TA = ["ஜனவரி", "பிப்ரவரி", "மார்ச்", "ஏப்ரல்", "மே", "ஜூன்", "ஜூலை", "ஆகஸ்ட்", "செப்டம்பர்", "அக்டோபர்", "நவம்பர்", "டிசம்பர்"]


def fix_dates(t, today=None):
    """fix 2: a date without its month ("22-ஆம் தேதி", "30 வரை") is read with the month ("அக்டோபர் 22ஆம் தேதி")"""
    import datetime
    today = today or datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5, minutes=30))).date()
    def month_for(d, until):
        cands = []
        for k in (-1, 0, 1):
            m = (today.month - 1 + k) % 12 + 1
            y = today.year + ((today.month - 1 + k) // 12)
            try:
                cands.append(datetime.date(y, m, d))
            except ValueError:
                pass
        if until:      # "... வரை" is about the coming days
            fut = [c for c in cands if c >= today]
            cands = fut or cands
        return min(cands, key=lambda c: abs((c - today).days)).month
    def rep(m):
        pre = t[max(0, m.start() - 14):m.start()]
        if any(x in pre for x in MONTHS_TA) or re.search(r"\d[./-]\s*$", pre):
            return m.group(0)
        d = int(m.group(1))
        if not 1 <= d <= 31:
            return m.group(0)
        until = bool(m.group(3))
        return f"{MONTHS_TA[month_for(d, until) - 1]} {d}ஆம் தேதி" + (" வரை" if until else "")
    t2 = re.sub(r"(?<![\d:.,])(?:<b>)?(\d{1,2})(?:</b>)?\s*-?\s*(?:(ம்|ஆம்)\s*தேதி|(?=\s*வரை))(\s*வரை)?", rep, t)
    return t2


def punch_on():
    """change 1 (strong 2-second opening): on when poster/config.json "reel_punch" is true, or REEL_PUNCH=1 (sample renders)"""
    if os.environ.get("REEL_PUNCH") in ("0", "1"):
        return os.environ["REEL_PUNCH"] == "1"
    try:
        return bool(json.loads((Path(__file__).resolve().parent.parent / "poster" / "config.json").read_text()).get("reel_punch"))
    except Exception:
        return False


def punch_line(spec):
    """the shortest striking line: the writer's own "punch" if given, else the yellow number + the headline line
    ("90,703 குழந்தைகளுக்கு வைட்டமின் ஏ முகாம்!"), else the headline line alone"""
    if spec.get("punch"):
        return re.sub(r"<[^>]+>", "", str(spec["punch"])).strip()
    h1, h2 = (re.sub(r"<[^>]+>", "", str(x or "")).strip() for x in (spec.get("hook") or ["", ""])[:2])
    if h2 and h1 and re.fullmatch(r"(ரூ\.?\s*|₹\s*)?[\d,.]+\s*(%|பேர்|பேருக்கு|ஏக்கர்|கோடி|லட்சம்|டன்|மி\.?மீ\.?|கி\.?மீ\.?)?", h2):
        return f"{h2} {h1}!"      # "90,703 குழந்தைகளுக்கு வைட்டமின் ஏ முகாம்!"
    return f"{h1}!" if h1 else ""


def _words(t):
    return {w[:5] for w in re.findall(r"[\u0B80-\u0BFF\w]{3,}", re.sub(r"<[^>]+>", "", t))}


def repeats(punch, first):
    """fix 1: the one-line story already says what the punch line says -> the punch is not spoken (no double reading)"""
    a, b = _words(punch), _words(first)
    return bool(a) and len(a & b) / len(a) >= 0.6


def voice_setting():
    """poster/config.json "reel_voice": the news voice (owner 26 Oct: Valluvar, news style). Falls back to the AI4Bharat model."""
    try:
        cfg = json.loads((Path(__file__).resolve().parent.parent / "poster" / "config.json").read_text())
        return cfg.get("reel_voice") or {}
    except Exception:
        return {}


def english_outro(work, idx, voice):
    """the follow line in Indian English (free edge-tts voice), in a voice that matches the news voice"""
    try:
        mp3 = work / "outro_en.mp3"
        if True:
            txt = V3.OUTRO_EN
            try:      # owner 26 Nov (Trichy views test): the spoken end asks people to SEND the news (sends reach new viewers)
                cfg = json.loads((Path(__file__).resolve().parent.parent / "poster" / "config.json").read_text())
                if (cfg.get("views_test") or {}).get("enabled") and (cfg.get("reel_voice") or {}).get("outro_text"):
                    txt = str(cfg["reel_voice"]["outro_text"])
            except Exception:
                pass
            subprocess.run([sys.executable, "-m", "edge_tts", "--voice", voice, "--rate=+0%", "--text", txt, "--write-media", str(mp3)], check=True, timeout=60)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp3), "-af",
                        "silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
                        "highpass=f=80,acompressor=threshold=0.12:ratio=3:attack=5:release=80,loudnorm=I=-16:TP=-1.5", "-ar", "22050", "-ac", "1",
                        str(work / f"line{idx}.wav")], check=True)
        print("outro spoken in English", voice)
    except Exception as e:
        print("English outro failed, keeping the Tamil line:", e)


# ---- Coimbatore 360: ONE picture per story. Each camera shot shows the same picture with its own move, so the reel never looks static.
# (zoom start, zoom end, focus x, focus y, pan px x, pan px y); pans stay inside the zoom margin so no picture edge shows
SINGLE_MOVES = [(1.06, 1.30, .50, .40, 0, 0),       # slow push-in on the subject (opening)
                (1.40, 1.14, .50, .50, 0, 0),       # pull back: the whole scene
                (1.28, 1.32, .50, .45, 200, 0),     # pan across (left -> right)
                (1.30, 1.42, .28, .36, 0, 0),       # close on the upper-left part
                (1.16, 1.24, .50, .55, 0, -150),    # tilt (top -> bottom)
                (1.28, 1.32, .50, .48, -200, 0),    # pan back (right -> left)
                (1.30, 1.42, .72, .62, 0, 0),       # close on the lower-right part
                (1.42, 1.10, .40, .45, 0, 0)]       # big pull back


def pic_layers(images):
    """the <img> layers of the reel: one picture is used as two layers, so a cut between two moves of the same picture is a
    soft cross-dissolve (like a cut between two different pictures), never a jump"""
    images = list(images or [])
    return images * 2 if len(images) == 1 else images


def plan_shots(n_img, content_end, snaps):
    """camera shots: 2+ pictures -> the v3 plan (pictures spread over the story); 1 picture -> a cut about every V3.CUT s
    (snapped to a word start), each cut a different move from SINGLE_MOVES, the two layers alternating"""
    if n_img != 1:
        shots = V3.plan_shots(n_img, content_end, snaps)
        if views_test_cfg().get("cycle_pictures"):      # owner 27 Nov: every cut shows another picture (was: each picture once, for a third of the reel)
            for i, sh in enumerate(shots):
                sh["img"] = i % n_img
        return shots
    n = max(2, int(round(content_end / V3.CUT)))
    cuts = [0.0]
    for i in range(1, n):
        t = content_end * i / n
        near = min(snaps, key=lambda x: abs(x - t)) if snaps else t
        cuts.append(near if abs(near - t) < 0.55 and near > cuts[-1] + 0.9 else t)
    cuts.append(content_end + 5)
    shots = []
    for i in range(len(cuts) - 1):
        z0, z1, fx, fy, px, py = SINGLE_MOVES[i % len(SINGLE_MOVES)]
        shots.append({"a": round(cuts[i], 3), "b": round(cuts[i + 1], 3), "img": i % 2,
                      "z0": min(z0, V3.MAX_ZOOM), "z1": min(z1, V3.MAX_ZOOM), "fx": fx, "fy": fy, "px": px, "py": py})
    return shots


def head_icon(name):
    """owner 20 Nov: the 📰 / 📅 marks drawn as icons (an emoji font is not on every render machine); nothing if missing"""
    try:
        return R.icon(name)
    except BaseException:
        return ""


def build_html(spec, shots, sents, caps, hook_end, end_t, total, page):
    logo = f"file://{R.KIT.resolve() / page['logo']}"
    foot = f"file://{(Path(__file__).resolve().parent / 'assets' / page.get('footer', 'footer_trichy.png')).as_posix()}"
    acc = PREMIUM_ACCENT if reel_style(spec) == "P" else THEME_ACCENT.get(reel_style(spec)) or accent_for(spec.get("cat", ""))      # premium / news themes: one fixed accent
    layers = pic_layers(spec["images"])
    imgs = "".join(f'<img class="pic" id="p{i}" src="file://{Path(p).resolve()}">' for i, p in enumerate(layers))
    cards = ""
    for i, s in enumerate(sents):
        c = card_for(s.get("card") or s.get("fact"))
        s["has_card"] = bool(c)
        if c:
            cards += (f'<div class="card" id="c{i}"><div class="ico">{R.icon(c["icon"])}</div>'
                      f'<div class="tx"><div class="lb">{E(c["label"])}</div><div class="vl">{E(to_digits(c["text"]))}</div></div></div>')
    # one row per kind of fact (the longest text wins), the most useful kinds first
    best = {}
    for c in [{"icon": "location-dot", "label": "இடம்", "text": spec.get("location", "")}] + [card_for(s.get("card") or s.get("fact")) for s in sents] + list(spec.get("summary") or []):
        if c and c.get("text"):
            k = c["label"]
            if k not in best or len(c["text"]) > len(best[k]["text"]):
                best[k] = c
    ORDER = ["இடம்", "நாள்", "நேரம்", "என்ன நடந்தது", "யார்", "பலத்த காயம்", "எத்தனை பேர்", "காயமடைந்தோர்", "தொகை", "சிகிச்சை",
             "நடவடிக்கை", "கோரிக்கை", "மக்கள் புகார்", "மக்கள் கவனத்திற்கு", "முக்கிய தகவல்"]
    must = ["இடம்", "சிகிச்சை", "நடவடிக்கை", "மக்கள் கவனத்திற்கு", "தொகை", "நேரம்", "நாள்"]      # never dropped for space
    keys = sorted(best, key=lambda k: (k not in must, ORDER.index(k) if k in ORDER else 99))[:6]
    rows = [best[k] for k in sorted(keys, key=lambda k: ORDER.index(k) if k in ORDER else 99)]
    summary = "" if len(rows) < 3 else ('<div id="sum"><div class="st">' + R.icon('circle-info') + '<span>முழு விவரம்</span></div>' + "".join(
        f'<div class="row" id="r{i}">{R.icon(c["icon"])}<div class="l">{E(c["label"])}</div><div class="v">{E(to_digits(c["text"]))}</div></div>' for i, c in enumerate(rows)) + '</div>')
    cap_html = ""
    for gi, g in enumerate(caps):
        spans = "".join(f'<span id="w{gi}_{k}">{E(w[0])}</span>' for k, w in enumerate(g["words"]))
        cap_html += f'<div class="ph" id="g{gi}">{spans}</div>'
    hook = spec.get("hook") or ["", ""]
    mini = spec.get("mini") or " ".join(x for x in hook if x)
    data = json.dumps({"shots": shots, "sents": [{"a": s["a"], "b": s["b"], "card": s["has_card"]} for s in sents],
                       "caps": [{"a": g["a"], "b": g["b"], "w": [[x[1], x[2]] for x in g["words"]]} for g in caps],
                       "hook_end": hook_end, "end_t": end_t, "total": total, "n": len(layers), "single": len(spec["images"]) == 1, "clean_hook": views_test_cfg().get("clean_hook", False),
                       "sum_a": (sents[-2]["a"] if len(sents) > 5 else sents[-1]["a"]) if len(sents) > 3 else end_t, "rows": len(rows) if summary else 0})
    style = reel_style(spec)
    low = "#hook{top:900px}#hook .h1{font-size:88px}" if views_test_cfg().get("hook_low") and style != "P" else ""      # owner 27 Nov: headline under the picture's subject, not on it
    html_ = f"""<!doctype html><html><head><meta charset="utf-8"><style>{CSS}{STYLES.get(style, "")}{low}</style></head><body style="--acc:{acc}">
<div id="stage">{imgs}</div><div id="shade"></div><div id="flash"></div>
<img id="plogo" src="{logo}">
<div id="hdr"><div><div class="nm">{page['name']}</div>
<div class="sub"><span class="tag">{E(spec.get('cat', ''))}</span><span class="dt">{head_icon('calendar-days')}{E(spec['date'])}</span></div>{('<div class="src">' + head_icon('newspaper') + 'Source: ' + E(spec['source']) + '</div>') if spec.get('source') else ''}</div></div>
<img id="foot" src="{foot}">
<div id="pin">{R.icon('location-dot')}<span>{E(spec.get('location', ''))}</span></div>
<div id="hook"><div class="h1">{E(hook[0])}</div><div class="h2">{E(hook[1])}</div></div>
<div id="mini">{E(mini)}</div>
{cards}
{summary}
<div id="cap">{cap_html}</div>
<div id="end"><img src="{logo}"><div class="e1">{E(page['tagline'])}</div><div class="e2">ஃபாலோ பண்ணுங்க @{page['handle']}</div><div class="e4">📌 சேவ் பண்ணுங்க • தேவைப்படுவோருக்கு ஷேர் பண்ணுங்க</div><div class="e3">{E(spec.get('location',''))}</div>{('<div class="e5">Source: ' + E(spec['source_full']) + '</div>') if spec.get('source_full') else ''}</div>
<script>
const D={data};
const cl=x=>Math.max(0,Math.min(1,x)), ease=x=>1-Math.pow(1-x,3), back=x=>{{const c=1.70158,c3=c+1;return 1+c3*Math.pow(x-1,3)+c*Math.pow(x-1,2)}};
function place(sh_,t,el,extra){{
  const dur=Math.max(0.5,sh_.b-sh_.a), tt=Math.min(t,sh_.b), pr=cl((tt-sh_.a)/Math.min(dur,2.4));
  const pe=pr<0.5?2*pr*pr:1-Math.pow(-2*pr+2,2)/2, z=sh_.z0+(sh_.z1-sh_.z0)*pe;
  el.style.transformOrigin=(sh_.fx*100)+'% '+(sh_.fy*100)+'%';
  el.style.transform='translate('+(sh_.px*(pe-0.5)+(extra||0))+'px,'+(sh_.py*(pe-0.5))+'px) scale('+(z*1.02)+')';
}}
window.renderAt=function(t){{
  let ai=D.shots.length-1; D.shots.forEach((s,i)=>{{if(t>=s.a&&t<s.b)ai=i}});
  const active=D.shots[ai], k=t-active.a, prev=ai>0?D.shots[ai-1]:null;
  // one picture (two layers of it): a soft dissolve between two camera moves - no slide, no white flash
  const TR=D.single?0.45:0.3, S=D.single?0:1, trans=(prev&&prev.img!==active.img&&k<TR)?cl(k/TR):1;
  for(let i=0;i<D.n;i++){{const e=document.getElementById('p'+i);e.style.opacity=0;e.style.zIndex=0;e.style.filter='none';}}
  const el=document.getElementById('p'+active.img); el.style.opacity=ease(trans); el.style.zIndex=2; place(active,t,el,(1-ease(trans))*90*S);
  if(trans<1){{const pe_=document.getElementById('p'+prev.img);pe_.style.opacity=1;pe_.style.zIndex=1;place(prev,t,pe_,-ease(trans)*120*S);}}
  if(t>=D.end_t)el.style.filter='blur('+(18*Math.min(1,(t-D.end_t)/0.3))+'px)';
  document.getElementById('flash').style.opacity=(!D.single&&active.a>0&&k<0.1&&prev&&prev.img!==active.img)?0.12*(1-k/0.1):0;
  // progress segments: one per sentence
  // hook: frame 1 -> hook_end, then the mini headline stays
  const h=document.getElementById('hook'), hin=back(cl(t/0.3)), hout=cl((t-(D.hook_end-0.25))/0.25);
  h.style.opacity=(t<D.hook_end)?(1-hout):0; h.style.transform='translateY('+(30*(1-Math.min(1,hin)))+'px)';
  const m=document.getElementById('mini'), min_=ease(cl((t-D.hook_end)/0.35));
  m.style.opacity=(t>=D.hook_end&&t<D.end_t)?min_:0; m.style.transform='translateX('+(-(1-min_)*60)+'px)';
  // pin + header always (until the end card)
  const live=t<D.end_t?1:0;
  ['pin','hdr','plogo'].forEach(id=>document.getElementById(id).style.opacity=live);
  document.getElementById('pin').style.transform='scale('+(0.9+0.1*back(cl(t/0.35)))+')';
  // 5W cards: with the sentence they belong to (not during the hook)
  D.sents.forEach((s,i)=>{{
    if(!s.card)return; const c=document.getElementById('c'+i);
    const a=Math.max(s.a+0.15,D.hook_end+0.1), b=s.b+0.25;
    const p=back(cl((t-a)/0.4)), out=cl((t-(b-0.2))/0.2);
    c.style.opacity=(t>=a&&t<b&&t<D.end_t)?cl(p*1.5)*(1-out):0;
    c.style.transform='translateX('+((1-Math.min(1,p))*-260)+'px)';
  }});
  // full-details summary: during the last news sentence, rows appear one by one
  const sm=document.getElementById('sum');
  if(sm){{const u=ease(cl((t-D.sum_a)/0.4)); sm.style.opacity=(t>=D.sum_a&&t<D.end_t)?u:0; sm.style.transform='translateY('+(40*(1-u))+'px)';
    for(let i=0;i<D.rows;i++){{const r=document.getElementById('r'+i), a=D.sum_a+0.25+i*0.28; r.style.opacity=cl((t-a)/0.25); r.style.transform='translateX('+(-40*(1-ease(cl((t-a)/0.3))))+'px)';}}
    if(t>=D.sum_a)document.querySelectorAll('.card').forEach(c=>c.style.opacity=0);}}
  // captions
  D.caps.forEach((g,gi)=>{{
    const ge=document.getElementById('g'+gi), on=(t>=g.a&&t<g.b)&&t<D.end_t&&(!D.clean_hook||t>=D.hook_end-0.05);      // owner 27 Nov: first seconds = picture + headline only
    ge.style.opacity=on?cl((t-g.a)/0.08):0;
    if(on){{const u=ease(cl((t-g.a)/0.2)); ge.style.transform='translateY('+(22*(1-u))+'px)';
      g.w.forEach((w,k)=>{{const sp=document.getElementById('w'+gi+'_'+k),act=(t>=w[0]&&t<w[1]);sp.className=act?'on':'';
        sp.style.transform=act?'scale(1.04)':'none';}});}}
  }});
  const e=document.getElementById('end'); e.style.opacity=ease(cl((t-D.end_t)/0.3));
  e.style.transform='scale('+(0.94+0.06*ease(cl((t-D.end_t)/0.4)))+')';
}};
function fitEl(el,maxH,min){{let fs=parseFloat(getComputedStyle(el).fontSize),n=0;while((el.scrollWidth>el.clientWidth+1||el.offsetHeight>maxH)&&fs>min&&n++<60){{fs-=2;el.style.fontSize=fs+'px';}}}}
window.fitAll=function(){{
  document.querySelectorAll('.ph').forEach(e=>fitEl(e,200,58));
  document.querySelectorAll('.card .vl').forEach(e=>fitEl(e,200,34));
  fitEl(document.querySelector('#hook .h1'),360,56); fitEl(document.querySelector('#hook .h2'),210,48);
  fitEl(document.getElementById('mini'),124,30); document.querySelectorAll('#sum .v').forEach(e=>fitEl(e,104,26)); document.querySelectorAll('#sum .l').forEach(e=>fitEl(e,76,20)); fitEl(document.querySelector('#pin span'),70,28);
}};
</script></body></html>"""
    return premium_layer(html_, spec) if style == "P" else html_


def max_seconds(spec=None):
    """60 s for a reel; owner 30 Oct: a power-cut notice (every area read out) may run to config "power_cut" max_seconds (88 s,
    under verify.py's 90 s check)"""
    try:
        cfg = json.loads((Path(__file__).resolve().parent.parent / "poster" / "config.json").read_text())
    except Exception:
        return 90.0
    limit = float(cfg.get("reel_max_seconds", 90))
    if spec:
        poster = str(Path(__file__).resolve().parent.parent / "poster")
        if poster not in sys.path:
            sys.path.append(poster)
        import freshness
        if freshness.is_power_cut(spec.get("cat"), spec.get("mini"), *(spec.get("hook") or [])):
            limit = float((cfg.get("power_cut") or {}).get("max_seconds") or limit)
    return limit


def fit_max(work, n, lead, gap, limit=None):
    """owner 28 Oct: a reel is at most 90 s. Never cut a fact - when the full news runs longer, the news lines (not the
    English outro) are read a little faster, at most 1.2x"""
    limit = limit or max_seconds()
    durs = [V3.wav_dur(work / f"line{i}.wav") for i in range(n)]
    pauses = lead + sum(V3.PAUSE if i == n - 2 else (0.55 if i == 0 else gap) for i in range(n - 1))
    total = sum(durs) + pauses + 2.4
    if total <= limit + 0.5:
        return 1.0
    news = sum(durs[:-1])
    f = min(1.2, news / max(1.0, news - (total - limit)))
    for i in range(n - 1):
        wav, tmp = work / f"line{i}.wav", work / f"line{i}_fit.wav"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-af", f"atempo={f:.3f}", str(tmp)], check=True)
        tmp.replace(wav)
    print(f"reel {total:.1f}s is over {limit:.0f}s: news voice read {f:.2f}x faster (nothing cut)")
    return f


def main(spec_path, out_mp4, page_key="trichy"):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "research_free"))
    import names      # owner 2 Nov: screen abbreviations (names.latin_abbr) - the voice functions import it on their own
    R.PAGE = R.PAGES.get(page_key, R.PAGES["trichy"]); R.LOGO = R.KIT / R.PAGE["logo"]      # one page only (no second page)
    spec = json.loads(Path(spec_path).read_text())
    rot = test_styles()
    th = "" if os.environ.get("REEL_STYLE") or spec.get("style") else theme_for(spec)
    if th:      # owner 27 Nov: each kind of news has its own theme (accident, police, rain, power cut, temple, government ...)
        spec["style"] = th
        print("views test news theme:", th, "for", news_topic(spec))
    elif rot and not os.environ.get("REEL_STYLE") and not spec.get("style"):      # owner 26 Nov (Trichy views test): several designs on one page
        import hashlib
        key = "style " + " ".join([str(spec.get("mini") or "")] + [str(x) for x in (spec.get("hook") or [])])
        spec["style"] = rot[int(hashlib.md5(key.encode("utf-8")).hexdigest(), 16) % len(rot)]
        print("views test design:", spec["style"])
    work = Path(out_mp4).with_suffix("")
    work = work.parent / (work.name + "_work"); work.mkdir(parents=True, exist_ok=True)
    sents, outro = spec["sentences"], spec["outro"]
    sents = [dict(x, say=everyday(fix_dates(x["say"])), caption=everyday(fix_dates(x.get("caption", x["say"])))) for x in sents]
    # owner 27 Oct: the on-screen cards use the same everyday words as the voice (headline, number line, fact cards, summary)
    spec["hook"] = [everyday(h) for h in (spec.get("hook") or ["", ""])]
    if spec.get("mini"):
        spec["mini"] = everyday(spec["mini"])
    for x in sents:
        for k in ("fact", "card"):
            v = x.get(k)
            if isinstance(v, str):
                x[k] = everyday(fix_dates(v))
            elif isinstance(v, dict) and v.get("text"):
                x[k] = dict(v, text=everyday(fix_dates(v["text"])))
    if spec.get("summary"):
        spec["summary"] = [dict(r, text=everyday(r.get("text", ""))) if isinstance(r, dict) else r for r in spec["summary"]]
    if abbr_on():      # owner 2 Nov: the screen shows MLA / LPG / DSP in English letters (the voice still says them in Tamil)
        spec["hook"] = [names.latin_abbr(h) for h in spec["hook"]]
        if spec.get("mini"):
            spec["mini"] = names.latin_abbr(spec["mini"])
        for x in sents:
            for k in ("fact", "card"):
                v = x.get(k)
                if isinstance(v, str):
                    x[k] = names.latin_abbr(v)
                elif isinstance(v, dict) and v.get("text"):
                    x[k] = dict(v, text=names.latin_abbr(v["text"]))
        if spec.get("summary"):
            spec["summary"] = [dict(r, text=names.latin_abbr(r.get("text", ""))) if isinstance(r, dict) else r for r in spec["summary"]]
    punch = everyday(punch_line(spec)) if punch_on() else ""
    if punch and sents and repeats(punch, sents[0]["say"]):
        print("opening: the one-line story already says it - read at once with the big headline (no double reading):", punch)
        punch = ""
    if punch:      # owner 27 Oct (change 1): the most striking fact is SPOKEN first (~2 s) while the big headline + number are on screen
        sents = [{"say": punch, "caption": punch, "fact": ""}] + sents
        print("opening punch line:", punch)
    short_end = str(views_test_cfg().get("end_line_ta") or "").strip().replace("{town}", share_town(spec))
    if short_end:      # owner 27 Nov: ONE short Tamil share + follow line (was Tamil follow + English share line = a 6 s still end card)
        outro = dict(outro, say=short_end)
    texts = [s["say"] for s in sents] + [outro["say"]]
    gap, lead = 0.16, 0.08
    if os.environ.get("REUSE_VOICE") == "1" and all((work / f"line{i}.wav").exists() for i in range(len(texts))):
        print("voice of an earlier render reused (design comparison: same story, same voice)")
    else:
        vs, _ = pick_voice(spec)      # always Valluvar (free)
        used = ""
        if os.environ.get("PREVIEW_TTS") == "edge" or vs.get("engine") == "edge":
            try:
                edge_lines(work, texts, vs.get("voice", "ta-IN-ValluvarNeural"), vs.get("rate", "+8%"), vs.get("pitch", "+0Hz"))
                used = "edge"
                print("news voice:", vs.get("voice", "ta-IN-ValluvarNeural"), vs.get("rate", ""), vs.get("pitch", ""))
            except Exception as e:
                print("news voice not available, using the AI4Bharat voice instead:", str(e)[:120])
        if not used:
            (work / "lines.json").write_text(json.dumps(texts, ensure_ascii=False))
            subprocess.run([sys.executable, str(Path(__file__).resolve().parent / "tts.py"), str(work / "lines.json"), str(work), spec.get("voice", "female")], check=True)
        if not short_end:
            english_outro(work, len(texts) - 1, vs.get("outro_voice", "en-IN-PrabhatNeural") if used else "en-IN-NeerjaNeural")
    fit_max(work, len(texts), lead, gap, max_seconds(spec))
    starts, ends, t = [], [], lead
    for i in range(len(texts)):
        d = V3.wav_dur(work / f"line{i}.wav")
        starts.append(round(t, 3)); ends.append(round(t + d, 3))
        t += d + (V3.PAUSE if i == len(texts) - 2 else (0.55 if i == 0 else gap))      # a beat after the one-line story, then the full news
    V3.CHIME_T = round(ends[-2] + 0.12, 3)
    try:      # owner 27 Nov: the share line is spoken over the full-details card; the still logo card shows only the last end_card_s seconds (was 6 s)
        ec = float(views_test_cfg().get("end_card_s") or 0)
    except (TypeError, ValueError):
        ec = 0
    end_t = round(max(V3.CHIME_T, ends[-1] + 0.6 - ec), 3) if short_end and ec >= 1.8 else V3.CHIME_T      # the chime stays at the end of the news
    total = round(max(ends[-1] + 0.6, end_t + 1.8), 3)
    R.make_voice_track(work, texts, starts, total)
    for i, s in enumerate(sents):
        s["a"], s["b"] = starts[i], ends[i]
    caps = []
    for i, s in enumerate(sents):
        wt = V3.word_times(to_digits(s["say"]), starts[i], ends[i])
        if abbr_on():
            wt = names.latin_abbr_words(wt)      # subtitles only - the voice track is already made from s["say"]
        for g in phrases(wt):
            caps.append({"a": g[0][1], "b": g[-1][2], "words": g})
    if short_end and end_t > starts[-1] + 0.5:      # owner 27 Nov: the share line is on screen too (most viewers watch without sound)
        for g in phrases(V3.word_times(to_digits(texts[-1]), starts[-1], ends[-1])):
            caps.append({"a": g[0][1], "b": g[-1][2], "words": g})
    snaps = [w[1] for g in caps for w in g["words"]]
    shots = plan_shots(len(spec["images"]), end_t, snaps)
    hook_end = max(2.6, min(6.0, ends[0] + 0.3))      # the hook stays while the one-line story is spoken
    try:      # owner 27 Nov: the big headline stays at most hook_max_s (the same still screen for 5-6 s lost viewers); captions follow at once
        hm = float(views_test_cfg().get("hook_max_s") or 0)
        if hm:
            hook_end = max(2.2, min(hm, hook_end))
    except (TypeError, ValueError):
        pass
    V3.build_audio(work, starts, shots, [dict(s, fact="") for s in sents], total)
    page = work / "reel4.html"
    new_page = None
    if design360.on():      # owner 20 Nov: the design team's design on every page; the earlier design if it cannot be made
        try:
            new_page = design360.page(spec, shots, sents, caps, end_t, total, R.PAGE,
                                      {"a": starts[-1], "b": ends[-1], "text": outro.get("say", "")})
        except Exception as e:
            print("new design not made, the earlier design is used:", str(e)[:200])
    page.write_text(clock360.add(new_page or build_html(spec, shots, sents, caps, hook_end, end_t, total, R.PAGE)))
    if os.environ.get("PROMO_JSON"):      # owner 20 Nov: the approved sponsor ad (poster/promo.py chose it; never stops the reel)
        try:
            import promo360
            page.write_text(promo360.add(page.read_text(), json.loads(Path(os.environ["PROMO_JSON"]).read_text(encoding="utf-8"))))
        except Exception as e:
            print("promotion not added (the reel is made without it):", str(e)[:150])
    if reel_style(spec) == "P":      # owner 13 Nov: light sound effects under the voice (premium look only)
        try:
            premium_sfx(work, spec, sents, hook_end, end_t)
        except Exception as e:
            print("sound effects skipped (the reel is fine):", str(e)[:150])
    nframes = int(math.ceil(total * FPS))
    enc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-c:v", "mjpeg", "-i", "-",
                            "-i", str(work / "mix.wav"), "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                            "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out_mp4)], stdin=subprocess.PIPE)
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": W, "height": H})
        pg.goto(page.resolve().as_uri())
        pg.wait_for_function("document.fonts.status==='loaded'")
        pg.evaluate("document.fonts.ready")
        pg.evaluate("fitAll()")
        for f in range(nframes):
            pg.evaluate(f"renderAt({f / FPS})")
            enc.stdin.write(pg.screenshot(type="jpeg", quality=95))
            if f % 150 == 0:
                print(f"frame {f}/{nframes}", flush=True)
        pg.evaluate("renderAt(0.9)")
        pg.evaluate("var c=document.getElementById('cap');if(c)c.style.display='none';var h=document.getElementById('hook');if(h)h.style.opacity=1;")
        pg.screenshot(path=str(Path(out_mp4).with_name(Path(out_mp4).stem + "_cover.jpg")), type="jpeg", quality=95)
        b.close()
    enc.stdin.close()
    rc = enc.wait()
    if rc:      # owner 2 Nov (review): a failed encode must fail here, not later as an unclear 'Build failed'
        raise SystemExit(f"ffmpeg encoder failed (exit {rc})")
    print(f"done {out_mp4} {total:.1f}s")
    try:      # owner 26 Nov: the voice and length of this reel, kept with the post for the views test (poster/insights)
        Path(out_mp4).with_suffix(".meta.json").write_text(json.dumps({"voice": (locals().get("vs") or {}).get("voice", "recorded"),
                                                                   "secs": round(total, 1), "words": sum(len(str(x["say"]).split()) for x in sents),
                                                                   "design": reel_style(spec), "pictures": len(spec.get("images") or [])}))
    except Exception as e:
        print("reel meta not saved:", str(e)[:100])


if __name__ == "__main__":
    main(*sys.argv[1:])
