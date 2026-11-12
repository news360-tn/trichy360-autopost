"""கோயம்புத்தூர் 360 — news reel v4 (the design the posting job uses: poster/config.json "reel_design": "v4").
Usage: python3 reel4.py spec.json out.mp4 [page]      (same spec as reel3.py; page = coimbatore, the only page)

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
#pin span{display:block;white-space:nowrap;overflow:hidden;max-width:800px}
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
.card .tx{padding:22px 30px 16px;display:flex;flex-direction:column;justify-content:center;gap:4px}
.card .lb{font:800 30px 'NST','CT';color:var(--acc);letter-spacing:.5px}
.card .vl{font:800 52px/1.25 'NST','CT';color:var(--navy)}
/* captions: whole phrases, outlined, in the safe zone above Instagram's caption */
#cap{position:absolute;left:56px;right:140px;top:1190px;height:330px;z-index:25}
.ph{position:absolute;left:0;right:0;bottom:0;text-align:left;font:800 70px/1.3 'CT','NST';color:#fff;opacity:0;-webkit-text-stroke:12px #000;paint-order:stroke fill;text-shadow:0 6px 18px rgba(0,0,0,.6)}
.ph span{display:inline-block;transform-origin:50% 70%;margin-right:.22em}
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
#hdr .src{font:800 26px 'NST','CT';color:#fff;background:rgba(255,255,255,.18);padding:4px 12px 0;border-radius:8px;white-space:nowrap;max-width:300px;overflow:hidden;text-overflow:ellipsis}
#hdr .sub{flex-wrap:nowrap}
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
    # owner 12 Nov: each page has its own look (page "style" in reel/reel.py). Same layout and timing, different colours and shapes.
    "S": """
#hook .h1{display:inline-block;background:linear-gradient(90deg,#B3121C,#E3151B);color:#fff;padding:14px 30px 4px;border-radius:0 0 22px 0;font-size:88px;text-shadow:none;box-shadow:0 12px 34px rgba(0,0,0,.5)}
#hook .h2{display:inline-block;background:#fff;color:#B3121C;padding:6px 26px 2px;border-radius:0 0 18px 0;font-size:56px;margin-top:0}
#mini{background:#B3121C;border-left:10px solid #FFD400;font-size:40px}
#pin{background:#FFD400;color:#1a1a1a;border-radius:0 30px 30px 0}
#pin .ic{color:#B3121C}
.card{background:#fff;color:#1a1a1a;border-left:12px solid #B3121C;border-radius:8px}
.card .lb{color:#B3121C}.card .vl{color:#1a1a1a}
#sum{background:rgba(179,18,28,.92);border-radius:10px}
#end .e2{background:#B3121C}
""",
    # K - Karur: white cards and a gold frame, dark green text
    "K": """
#hdr{background:#fff;color:#0B3D2E;border-radius:999px;border:4px solid #D4A017;padding:10px 26px 10px 12px}
#hdr .nm{color:#0B3D2E;text-shadow:none}#hdr .sub{color:#0B3D2E;text-shadow:none}
#hook .h1{background:#fff;color:#0B3D2E;border:5px solid #D4A017;padding:16px 30px 6px;border-radius:18px;font-size:86px;text-shadow:none;box-shadow:0 12px 34px rgba(0,0,0,.45)}
#hook .h2{background:#D4A017;color:#0B3D2E;border-radius:12px;padding:6px 22px 2px}
#mini{background:#fff;color:#0B3D2E;border-left:0;border-bottom:8px solid #D4A017;text-shadow:none}
#pin{background:#0B3D2E;color:#fff;border:3px solid #D4A017}
.card{background:#fff;color:#0B3D2E;border:4px solid #D4A017;border-radius:18px}
.card .lb{color:#8a6d00}.card .vl{color:#0B3D2E}
#sum{background:#fff;color:#0B3D2E;border:4px solid #D4A017;border-radius:18px}
#sum .st,#sum .l{color:#0B3D2E}#sum .v{color:#0B3D2E}
""",
    # T - Trichy: teal bands and round tags, strong bottom shade
    "T": """
#shade{background:linear-gradient(to bottom,rgba(0,0,0,.15),rgba(0,0,0,.05) 35%,rgba(0,40,45,.85) 100%)}
#hdr{background:rgba(0,70,75,.85);border-radius:20px;padding:12px 22px}
#pin{background:#00A6A6;color:#fff;border-radius:40px}
#pin .ic{color:#fff}
#hook .h1{background:rgba(0,70,75,.9);color:#fff;border-left:12px solid #FFC93C;padding:16px 26px 6px;border-radius:6px;font-size:84px}
#hook .h2{color:#FFC93C;text-shadow:0 2px 10px rgba(0,0,0,.7)}
#mini{background:#00A6A6;border-radius:999px;left:40px;right:40px;padding:12px 36px 6px;font-size:40px;text-shadow:none}
.card{background:rgba(0,70,75,.95);border:3px solid #00A6A6;border-radius:40px 10px 40px 10px}
.card .lb{color:#FFC93C}
#sum{background:rgba(0,70,75,.95);border:3px solid #00A6A6;border-radius:30px}
#end .e2{background:#00A6A6}
""",
    # P - Tirupur: deep blue panels, straight edges, white headline strip
    "P": """
#hdr{background:#0A2A6B;border-radius:6px;padding:12px 24px 12px 14px;border-left:10px solid #FFFFFF}
#hook .h1{background:#fff;color:#0A2A6B;padding:14px 28px 4px;border-radius:4px;font-size:88px;text-shadow:none;box-shadow:0 12px 30px rgba(0,0,0,.45)}
#hook .h2{background:#0A2A6B;color:#fff;border-radius:4px;padding:6px 22px 2px}
#mini{background:#0A2A6B;border-radius:0;left:0;right:0;border-top:6px solid #fff;padding:14px 48px 8px;font-size:40px;text-shadow:none}
#pin{background:#fff;color:#0A2A6B;border-radius:6px}
#pin .ic{color:#0A2A6B}
.card{background:rgba(10,42,107,.95);border:0;border-left:10px solid #fff;border-radius:4px}
#sum{background:rgba(10,42,107,.95);border-radius:4px;border-top:6px solid #fff}
#end .e2{background:#fff;color:#0A2A6B}
""",
    # E - Erode: green rounded frame with a turmeric-gold accent
    "E": """
#hdr{background:#14532D;border-radius:26px;border:3px solid #E9B949;padding:12px 26px 12px 12px}
#hook .h1{background:#14532D;color:#fff;border:4px solid #E9B949;border-radius:60px;padding:16px 40px 6px;font-size:84px;text-shadow:none}
#hook .h2{background:#E9B949;color:#14532D;border-radius:60px;padding:6px 30px 2px}
#mini{background:rgba(20,83,45,.92);border-radius:22px;left:60px;right:60px;border:3px solid #E9B949;text-shadow:none;font-size:40px}
#pin{background:#E9B949;color:#14532D;border-radius:60px}
#pin .ic{color:#14532D}
.card{background:rgba(20,83,45,.94);border:3px solid #E9B949;border-radius:60px}
.card .lb{color:#E9B949}
#sum{background:rgba(20,83,45,.94);border:3px solid #E9B949;border-radius:30px}
#end .e2{background:#14532D;border:3px solid #E9B949}
""",
}

ACCENT = {"மின் தடை": "#F59E0B", "மழை": "#1E88E5", "வானிலை": "#1E88E5", "வெள்ள": "#1E88E5", "விபத்து": "#E3151B", "குற்ற": "#B91C1C",
          "கோவில்": "#C2410C", "திருவிழா": "#C2410C", "வேலை": "#059669", "கல்வி": "#2563EB", "தாக்குதல்": "#DC2626"}

# what a fact is about -> icon + label (the label tells the viewer which of the 5W the card answers)
KINDS = [
    (r"ரூ\.?|₹|லட்சம்|கோடி|ரூபாய்", "indian-rupee-sign", "தொகை"),
    (r"மணி|நேரம்", "clock", "நேரம்"),
    (r"தேதி|ஜனவரி|பிப்ரவரி|மார்ச்|ஏப்ரல்|ஜூன்|ஜூலை|ஆகஸ்ட்|செப்டம்பர்|அக்டோபர்|நவம்பர்|டிசம்பர்|இன்று|நாளை", "calendar-days", "நாள்"),
    (r"மருத்துவமனை|சிகிச்சை", "hospital", "சிகிச்சை"),
    (r"கைது|போலீஸ்|போலீசார்|காவல்", "handcuffs", "நடவடிக்கை"),
    (r"வயது|குழந்தை|சிறுமி|சிறுவன்|மாணவ", "child", "யார்"),
    (r"\d+\s*பேர்|பலர்|மக்கள்", "users", "எத்தனை பேர்"),
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
            subprocess.run([sys.executable, "-m", "edge_tts", "--voice", voice, "--rate=+0%", "--text", V3.OUTRO_EN, "--write-media", str(mp3)], check=True, timeout=60)
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
        return V3.plan_shots(n_img, content_end, snaps)
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


def build_html(spec, shots, sents, caps, hook_end, end_t, total, page):
    logo = f"file://{R.KIT.resolve() / page['logo']}"
    foot = f"file://{(Path(__file__).resolve().parent / 'assets' / page.get('footer', 'footer_coimbatore.png')).as_posix()}"
    acc = accent_for(spec.get("cat", ""))
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
                       "hook_end": hook_end, "end_t": end_t, "total": total, "n": len(layers), "single": len(spec["images"]) == 1,
                       "sum_a": (sents[-2]["a"] if len(sents) > 5 else sents[-1]["a"]) if len(sents) > 3 else end_t, "rows": len(rows) if summary else 0})
    style = (os.environ.get("REEL_STYLE") or spec.get("style") or page.get("style") or "A").upper()
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{CSS}{STYLES.get(style, "")}</style></head><body style="--acc:{acc}">
<div id="stage">{imgs}</div><div id="shade"></div><div id="flash"></div>
<img id="plogo" src="{logo}">
<div id="hdr"><div><div class="nm">{page['name']}</div>
<div class="sub"><span class="tag">{E(spec.get('cat', ''))}</span><span>{E(spec['date'])}</span>{('<span class="src">📰 ' + E(spec['source']) + '</span>') if spec.get('source') else ''}</div></div></div>
<img id="foot" src="{foot}">
<div id="pin">{R.icon('location-dot')}<span>{E(spec.get('location', ''))}</span></div>
<div id="hook"><div class="h1">{E(hook[0])}</div><div class="h2">{E(hook[1])}</div></div>
<div id="mini">{E(mini)}</div>
{cards}
{summary}
<div id="cap">{cap_html}</div>
<div id="end"><img src="{logo}"><div class="e1">{E(page['tagline'])}</div><div class="e2">FOLLOW @{page['handle']}</div><div class="e4">📌 Save • தேவைப்படுவோருக்கு Share</div><div class="e3">{E(spec.get('location',''))}</div>{('<div class="e5">Source: ' + E(spec['source_full']) + '</div>') if spec.get('source_full') else ''}</div>
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
    const ge=document.getElementById('g'+gi), on=(t>=g.a&&t<g.b)&&t<D.end_t;
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


def main(spec_path, out_mp4, page_key="coimbatore"):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "research_free"))
    import names      # owner 2 Nov: screen abbreviations (names.latin_abbr) - the voice functions import it on their own
    R.PAGE = R.PAGES.get(page_key, R.PAGES["coimbatore"]); R.LOGO = R.KIT / R.PAGE["logo"]      # one page only (no second page)
    spec = json.loads(Path(spec_path).read_text())
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
        english_outro(work, len(texts) - 1, vs.get("outro_voice", "en-IN-PrabhatNeural") if used else "en-IN-NeerjaNeural")
    fit_max(work, len(texts), lead, gap, max_seconds(spec))
    starts, ends, t = [], [], lead
    for i in range(len(texts)):
        d = V3.wav_dur(work / f"line{i}.wav")
        starts.append(round(t, 3)); ends.append(round(t + d, 3))
        t += d + (V3.PAUSE if i == len(texts) - 2 else (0.55 if i == 0 else gap))      # a beat after the one-line story, then the full news
    V3.CHIME_T = round(ends[-2] + 0.12, 3)
    end_t = V3.CHIME_T
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
    snaps = [w[1] for g in caps for w in g["words"]]
    shots = plan_shots(len(spec["images"]), end_t, snaps)
    hook_end = max(2.6, min(6.0, ends[0] + 0.3))      # the hook stays while the one-line story is spoken
    V3.build_audio(work, starts, shots, [dict(s, fact="") for s in sents], total)
    page = work / "reel4.html"
    page.write_text(build_html(spec, shots, sents, caps, hook_end, end_t, total, R.PAGE))
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
        pg.evaluate("document.getElementById('cap').style.display='none';document.getElementById('hook').style.opacity=1;")
        pg.screenshot(path=str(Path(out_mp4).with_name(Path(out_mp4).stem + "_cover.jpg")), type="jpeg", quality=95)
        b.close()
    enc.stdin.close()
    rc = enc.wait()
    if rc:      # owner 2 Nov (review): a failed encode must fail here, not later as an unclear 'Build failed'
        raise SystemExit(f"ffmpeg encoder failed (exit {rc})")
    print(f"done {out_mp4} {total:.1f}s")


if __name__ == "__main__":
    main(*sys.argv[1:])
