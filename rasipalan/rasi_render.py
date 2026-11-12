"""15 carousel slides (1080x1350 JPEG): cover, panchangam, 12 rasis, closing slide.

Two designs - each page has its own look (owner 31 Oct):
  temple   (இராசிபுரம் 360): sandal-cream, temple maroon + gold, mango-leaf thoranam, kovil-karai border, gold rasi medallions
  calendar (கோவை 360):      the Tamil daily tear-off calendar sheet, red + black
A festival day changes the colours, the cover emblem and adds the greeting (themes below). Text that is too wide is shrunk to fit."""
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
FONTS = HERE / "fonts"
RASI_EN = ["ARIES", "TAURUS", "GEMINI", "CANCER", "LEO", "VIRGO", "LIBRA", "SCORPIO", "SAGITTARIUS", "CAPRICORN", "AQUARIUS", "PISCES"]
GLYPH = ["♈", "♉", "♊", "♋", "♌", "♍", "♎", "♏", "♐", "♑", "♒", "♓"]
ELEMENT = ["நெருப்பு", "நிலம்", "காற்று", "நீர்"] * 3
LUCKY_NUM = ["9", "6", "5", "2", "1", "5", "6", "9", "3", "8", "8", "3"]
LUCKY_COL = [("சிவப்பு", "#e53935"), ("வெள்ளை", "#f5f5f5"), ("பச்சை", "#2e7d32"), ("வெள்ளி", "#c0c7d0"), ("ஆரஞ்சு", "#fb8c00"),
             ("இளம் பச்சை", "#9ccc65"), ("இளஞ்சிவப்பு", "#f48fb1"), ("மெரூன்", "#8e2440"), ("மஞ்சள்", "#fdd835"), ("நீலம்", "#1e63d6"),
             ("கருநீலம்", "#1a237e"), ("பொன் மஞ்சள்", "#d4a017")]
LABELS = ["தொழில்", "பணம்", "குடும்பம்", "உடல்நலம்", "பரிகாரம்"]
KEYS = ["work", "money", "family", "health", "remedy"]

# theme: dark, deep, gold, light gold, background top, background bottom, emblem
THEMES = {
    "normal":       ("#7a0f1e", "#4d0712", "#e8b23a", "#b8801a", "#fffaf0", "#f7deb3", "lamp"),
    "diwali":       ("#5b1a8c", "#2e0b4d", "#ffc23d", "#c98a00", "#fff7e6", "#ffd9a0", "diyas"),
    "pongal":       ("#b23a00", "#6e2300", "#f6b100", "#b07a00", "#fffbe8", "#ffe7a3", "pot"),
    "murugan":      ("#b3122e", "#6d0a1a", "#ffb300", "#c27c00", "#fff6ec", "#ffd8b0", "vel"),
    "karthigai":    ("#8a1c00", "#4f1000", "#ffb627", "#c47d00", "#fff6e0", "#ffd28a", "diyas"),
    "perumal":      ("#0d3b8c", "#071f4d", "#f2c14e", "#b8892a", "#f6f8ff", "#dbe4ff", "namam"),
    "shiva":        ("#3b2a6b", "#1d1238", "#e9c46a", "#b08a2e", "#f7f5ff", "#ddd5f5", "trident"),
    "amman":        ("#a3123a", "#5e0a21", "#f4b400", "#b88600", "#fff5f7", "#ffd6e0", "lamp"),
    "navaratri":    ("#8e1b5a", "#4f0d31", "#f6b93b", "#b9821c", "#fff6fb", "#ffd9ec", "lamp"),
    "vinayagar":    ("#c2410c", "#7c2d12", "#fbbf24", "#b7791f", "#fff8ef", "#ffe0b8", "lotus"),
    "krishna":      ("#1d4ed8", "#1e3a8a", "#facc15", "#b8941a", "#f5f9ff", "#d6e6ff", "lotus"),
    "tamilnewyear": ("#047857", "#064e3b", "#fbbf24", "#b7791f", "#f3fff8", "#ccf3df", "pot"),
    "newyear":      ("#1e3a8a", "#0f1f4d", "#fbbf24", "#b7791f", "#f5f8ff", "#d8e2ff", "star"),
    "christmas":    ("#b91c1c", "#14532d", "#fbbf24", "#b7791f", "#fffaf5", "#f7e3cf", "star"),
    "christian_solemn": ("#4b3b2a", "#2b2016", "#d6b46a", "#a3843e", "#fbf8f2", "#e9e0cf", "cross"),
    "islamic":      ("#0f6b4f", "#073d2d", "#e6c15a", "#b0912e", "#f4fff9", "#d3f0e2", "crescent"),
    "islamic_solemn": ("#1f4f45", "#0f2a24", "#d4b86a", "#a38a40", "#f5faf8", "#dce9e4", "crescent"),
    "national":     ("#1e3a8a", "#0b1f4d", "#ff9933", "#138808", "#ffffff", "#fff2e0", "flag"),
}
SOLEMN = ("christian_solemn", "islamic_solemn")


def font_css():
    def ff(name, f, w=400):
        return f"@font-face{{font-family:'{name}';src:url('file://{FONTS / f}') format('woff2');font-weight:{w};}}"
    return "".join([ff("Baloo", "baloo-thambi-2-tamil-800-normal.woff2", 800), ff("BalooL", "baloo-thambi-2-latin-800-normal.woff2", 800),
                    ff("Mukta", "mukta-malar-tamil-600-normal.woff2", 600), ff("Mukta", "mukta-malar-tamil-700-normal.woff2", 700),
                    ff("Zod", "noto-sans-symbols-symbols-400-normal.woff2")])


FIT_JS = """<script>
document.fonts.ready.then(()=>{document.querySelectorAll('.fit').forEach(e=>{let s=parseFloat(getComputedStyle(e).fontSize);
 while(e.scrollWidth>e.clientWidth+1&&s>14){s-=1;e.style.fontSize=s+'px';}});document.body.dataset.ready='1';});
</script>"""


def greeting(fest):
    if not fest:
        return ""
    return fest["name"] if fest["theme"] in SOLEMN else f"{fest['name']} நல்வாழ்த்துகள்"


# ------------------------------------------------------------------ emblems (simple original SVG drawings)
def emblem(kind, c):
    D, G, G2 = c[0], c[2], c[3]
    flame = lambda x, y, s=1: (f'<path d="M{x} {y-40*s} C {x+14*s} {y-18*s}, {x+12*s} {y-2*s}, {x} {y+4*s} C {x-12*s} {y-2*s}, {x-14*s} {y-18*s}, {x} {y-40*s}Z" fill="#ffb300"/>'
                               f'<path d="M{x} {y-22*s} C {x+5*s} {y-12*s}, {x+4*s} {y-4*s}, {x} {y} C {x-4*s} {y-4*s}, {x-5*s} {y-12*s}, {x} {y-22*s}Z" fill="#fff59d"/>')
    diya = lambda x, y, s=1: flame(x, y - 6 * s, s) + f'<path d="M{x-34*s} {y} Q {x} {y+34*s} {x+34*s} {y} Z" fill="{G}" stroke="{G2}" stroke-width="2"/>'
    if kind == "diyas":
        return "".join(diya(x, y, s) for x, y, s in ((150, 190, 1.5), (70, 215, 1.0), (230, 215, 1.0)))
    if kind == "pot":
        return (f'<path d="M70 120 Q 150 60 230 120 L 215 135 Q 150 105 85 135Z" fill="#fff8e1"/>'
                f'<circle cx="110" cy="105" r="12" fill="#fff"/><circle cx="150" cy="95" r="14" fill="#fff"/><circle cx="190" cy="105" r="12" fill="#fff"/>'
                f'<path d="M80 135 Q 60 230 150 260 Q 240 230 220 135Z" fill="{G}" stroke="{G2}" stroke-width="4"/>'
                f'<path d="M85 165 Q 150 185 215 165" stroke="{D}" stroke-width="10" fill="none"/>'
                f'<path d="M40 270 L 60 40 M 260 270 L 240 40" stroke="#2e7d32" stroke-width="10" stroke-linecap="round"/>')
    if kind == "vel":
        return (f'<path d="M150 20 C 195 70, 195 130, 150 175 C 105 130, 105 70, 150 20Z" fill="{G}" stroke="{G2}" stroke-width="4"/>'
                f'<path d="M150 55 C 170 85, 170 115, 150 140 C 130 115, 130 85, 150 55Z" fill="{D}"/>'
                f'<rect x="142" y="170" width="16" height="110" rx="6" fill="{G2}"/><rect x="128" y="170" width="44" height="12" rx="6" fill="{G}"/>')
    if kind == "namam":
        return (f'<path d="M95 60 L 120 60 L 140 240 L 115 240Z" fill="#fff" stroke="{G2}" stroke-width="2"/>'
                f'<path d="M205 60 L 180 60 L 160 240 L 185 240Z" fill="#fff" stroke="{G2}" stroke-width="2"/>'
                f'<path d="M140 80 L 160 80 L 156 245 L 144 245Z" fill="#e53935"/><path d="M95 60 Q 150 30 205 60" stroke="{G}" stroke-width="6" fill="none"/>')
    if kind == "trident":
        return (f'<rect x="143" y="70" width="14" height="210" rx="6" fill="{G2}"/>'
                f'<path d="M150 20 L 165 80 L 135 80Z M 85 50 Q 90 120 150 125 Q 210 120 215 50 Q 195 100 150 100 Q 105 100 85 50Z" fill="{G}"/>'
                f'<circle cx="150" cy="170" r="16" fill="{D}" stroke="{G}" stroke-width="4"/>')
    if kind == "star":
        pts = " ".join(f"{150 + (100 if k % 2 == 0 else 42) * math.cos(-math.pi / 2 + k * math.pi / 5):.0f},"
                       f"{150 + (100 if k % 2 == 0 else 42) * math.sin(-math.pi / 2 + k * math.pi / 5):.0f}" for k in range(10))
        return f'<polygon points="{pts}" fill="{G}" stroke="{G2}" stroke-width="4"/>' + "".join(
            f'<circle cx="{150 + 125 * math.cos(k):.0f}" cy="{150 + 125 * math.sin(k):.0f}" r="6" fill="{G}"/>' for k in (0.3, 1.4, 2.6, 3.9, 5.1))
    if kind == "cross":
        return f'<rect x="135" y="40" width="30" height="220" rx="6" fill="{G}"/><rect x="85" y="95" width="130" height="28" rx="6" fill="{G}"/>'
    if kind == "crescent":
        return (f'<circle cx="140" cy="150" r="100" fill="{G}"/><circle cx="180" cy="130" r="90" fill="{c[4]}"/>'
                f'<polygon points="215,95 223,120 249,120 228,135 236,160 215,145 194,160 202,135 181,120 207,120" fill="{G}"/>')
    if kind == "flag":
        return ('<rect x="40" y="70" width="220" height="50" fill="#ff9933"/><rect x="40" y="120" width="220" height="50" fill="#fff" stroke="#ddd"/>'
                '<rect x="40" y="170" width="220" height="50" fill="#138808"/><circle cx="150" cy="145" r="20" fill="none" stroke="#000080" stroke-width="3"/>'
                + "".join(f'<line x1="150" y1="145" x2="{150 + 20 * math.cos(k * math.pi / 12):.1f}" y2="{145 + 20 * math.sin(k * math.pi / 12):.1f}" stroke="#000080" stroke-width="1"/>' for k in range(24)))
    if kind == "lotus":
        return "".join(f'<ellipse cx="150" cy="150" rx="28" ry="90" fill="{G}" stroke="{G2}" stroke-width="3" transform="rotate({a} 150 230)" opacity=".95"/>'
                       for a in (-60, -30, 0, 30, 60)) + f'<rect x="60" y="230" width="180" height="14" rx="7" fill="{D}"/>'
    # lamp (kuthu vilakku)
    return (flame(150, 70, 1.6) + f'<path d="M60 108 Q 150 175 240 108 Q 150 118 60 108Z" fill="{G}" stroke="{G2}" stroke-width="2"/>'
            f'<rect x="138" y="140" width="24" height="90" fill="{G}"/><ellipse cx="150" cy="144" rx="30" ry="8" fill="{G}"/>'
            f'<path d="M85 285 Q 150 230 215 285Z" fill="{G}" stroke="{G2}" stroke-width="2"/><rect x="70" y="283" width="160" height="12" rx="6" fill="{G2}"/>')


def emblem_svg(kind, c, size):
    return f'<svg width="{size}" height="{size}" viewBox="0 0 300 300">{emblem(kind, c)}</svg>'


def star_row(n, on1, on2, off, size=44):
    p = "M12 2.6l2.9 6 6.5.8-4.8 4.5 1.2 6.5L12 17.2l-5.8 3.2 1.2-6.5L2.6 9.4l6.5-.8z"
    return "".join(f'<svg width="{size}" height="{size}" viewBox="0 0 24 24"><defs><linearGradient id="sg" x1="0" y1="0" x2="0" y2="1">'
                   f'<stop offset="0" stop-color="{on1}"/><stop offset="1" stop-color="{on2}"/></linearGradient></defs>'
                   f'<path d="{p}" fill="{"url(#sg)" if i < n else off}"/></svg>' for i in range(5))


def page(css, body):
    return f"<!doctype html><html><head><meta charset='utf-8'><style>{font_css()}{css}</style></head><body>{body}{FIT_JS}</body></html>"


# ================================================================== TEMPLE design (Rasipuram)
class Temple:
    def __init__(s, ctx):
        s.x = ctx
        s.c = THEMES.get((ctx["fest"] or {}).get("theme", "normal"), THEMES["normal"])
        D, DD, G, G2, B1, B2, _ = s.c
        s.css = f"""*{{margin:0;padding:0;box-sizing:border-box}}html,body{{width:1080px;height:1350px;overflow:hidden}}
body{{position:relative;font-family:'Mukta','BalooL',sans-serif;color:#3a1408;background:radial-gradient(ellipse at 50% 40%,{B1} 0%,{B1} 40%,{B2} 100%)}}
.kolam{{position:absolute;inset:0;background-image:radial-gradient({D} 2.2px,transparent 2.6px);background-size:44px 44px;opacity:.07}}
.frame{{position:absolute;inset:22px;border:4px solid {G2};border-radius:6px}}.frame2{{position:absolute;inset:32px;border:1.5px solid {G};border-radius:4px}}
.h{{font-family:'Baloo','BalooL';font-weight:800}}.zod{{font-family:'Zod';font-variant-emoji:text}}.nw{{white-space:nowrap}}.fit{{white-space:nowrap;overflow:hidden}}
.goldtxt{{background:linear-gradient(180deg,#fff1b8 0%,{G} 45%,{G2} 100%);-webkit-background-clip:text;color:transparent}}
.pill{{background:linear-gradient(180deg,{D},{DD});box-shadow:0 0 0 3px {G};color:#fff3c4}}"""

    def thoranam(s):
        y, n, items = 56, 15, ""
        for i in range(n):
            x = 36 + i * (1008 / (n - 1)); cy = y + 8 + 26 * math.sin(math.pi * i / (n - 1))
            items += (f'<g transform="translate({x:.1f},{cy:.1f})"><path d="M0 0 C 16 22, 14 58, 0 78 C -14 58, -16 22, 0 0Z" fill="url(#lf)"/>'
                      f'<path d="M0 4 L0 74" stroke="#1b5e20" stroke-width="1.6"/></g>') if i % 2 == 0 else \
                (f'<g transform="translate({x:.1f},{cy + 8:.1f})"><circle r="15" fill="#ff8f00"/><circle r="10" fill="#ffb300"/><circle r="4" fill="#e65100"/></g>')
        rope = " ".join(f"{36 + i * (1008 / 40):.1f},{y + 8 + 26 * math.sin(math.pi * i / 40):.1f}" for i in range(41))
        return (f'<svg style="position:absolute;left:0;top:0" width="1080" height="200"><defs><linearGradient id="lf" x1="0" y1="0" x2="1" y2="1">'
                f'<stop offset="0" stop-color="#66bb6a"/><stop offset="1" stop-color="#2f7d32"/></linearGradient></defs>'
                f'<polyline points="{rope}" fill="none" stroke="{s.c[3]}" stroke-width="3"/>{items}</svg>')

    def band(s):
        D, DD, G = s.c[0], s.c[1], s.c[2]
        tri = "".join(f'<path d="M{x} 34 L{x + 18} 0 L{x + 36} 34Z" fill="{G}"/><circle cx="{x + 18}" cy="22" r="3" fill="{D}"/>' for x in range(0, 1080, 36))
        return (f'<svg style="position:absolute;left:0;top:1294px" width="1080" height="56"><rect width="1080" height="56" fill="{DD}"/>'
                f'<rect width="1080" height="22" y="34" fill="{D}"/>{tri}</svg>')

    def header(s):
        D, G = s.c[0], s.c[2]
        return (f'<div style="position:absolute;top:150px;left:62px;right:62px;display:flex;align-items:center;justify-content:space-between">'
                f'<div style="display:flex;align-items:center;gap:16px"><img src="{s.x["logo"]}" style="width:112px;height:112px;border-radius:50%;box-shadow:0 0 0 4px {G}">'
                f'<div class="h nw" style="font-size:38px;color:{D}">{s.x["brand"]}</div></div>'
                f'<div class="pill nw" style="font-weight:700;font-size:25px;padding:12px 26px;border-radius:999px">{s.x["p"]["date_ta"]} · {s.x["p"]["weekday"]}</div></div>')

    def footer(s, n, nxt=True):
        D = s.c[0]
        arrow = (f'<span style="display:inline-flex;align-items:center;gap:10px">அடுத்த ராசி <svg width="34" height="20"><path d="M2 10h28M22 2l8 8-8 8" '
                 f'stroke="{D}" stroke-width="3" fill="none" stroke-linecap="round"/></svg></span>') if nxt else ""
        return (f'<div style="position:absolute;bottom:84px;left:62px;right:62px;display:flex;justify-content:space-between;align-items:center;'
                f'font-weight:700;font-size:24px;color:{D}"><div><span style="font-family:BalooL;font-size:28px">{n:02d}</span>'
                f'<span style="opacity:.5"> / 15</span></div>{arrow}</div>')

    def base(s, inner):
        G, DD = s.c[2], s.c[1]
        return page(s.css, f'<div class="kolam"></div>{s.thoranam()}{inner}{s.band()}<div class="frame"></div><div class="frame2"></div>'
                           f'<img src="{s.x["logo"]}" style="position:absolute;left:487px;top:1232px;width:106px;height:106px;border-radius:50%;'
                           f'box-shadow:0 0 0 4px {G},0 0 0 7px {DD},0 6px 16px rgba(0,0,0,.35)">')

    def cover(s):
        D, DD, G, G2 = s.c[:4]
        p, f = s.x["p"], s.x["fest"]
        ring = "".join(f'<div style="position:absolute;left:{540 + 285 * math.cos(-math.pi / 2 + i * math.pi / 6) - 40:.0f}px;'
                       f'top:{640 + 285 * math.sin(-math.pi / 2 + i * math.pi / 6) - 40:.0f}px;width:80px;height:80px;border-radius:50%;'
                       f'background:radial-gradient({D},{DD});box-shadow:0 0 0 4px {G};display:grid;place-items:center">'
                       f'<span class="zod" style="font-size:42px;color:#ffd54f;line-height:1">{GLYPH[i]}&#xFE0E;</span></div>' for i in range(12))
        kind = s.c[6] if f else "lamp"
        greet = greeting(f)
        top_line = (f'<div class="h fit" style="width:1000px;margin:0 auto;font-size:44px;color:{D}">{greet}</div>') if greet else ""
        hook = s.x["hook"]
        inner = f'''{s.header()}
        <svg style="position:absolute;left:225px;top:325px" width="630" height="630"><circle cx="315" cy="315" r="285" fill="none" stroke="{G2}" stroke-width="3"/>
          <circle cx="315" cy="315" r="250" fill="none" stroke="{G}" stroke-width="1.5" stroke-dasharray="4 8"/><circle cx="315" cy="315" r="205" fill="{G}" opacity=".18"/></svg>
        {ring}
        <div style="position:absolute;left:540px;top:640px;transform:translate(-50%,-56%);text-align:center;width:400px">
          <div style="height:120px;display:flex;justify-content:center">{emblem_svg(kind, s.c, 120)}</div>
          <div style="font-family:BalooL;font-weight:800;font-size:165px;line-height:.9;color:{D};text-shadow:0 5px 0 {G}">{int(p["date"][8:])}</div>
          <div class="h" style="font-size:36px;margin-top:4px">{p["date_ta"].split(" ", 1)[1]}</div>
          <div class="h pill nw" style="display:inline-block;margin-top:4px;font-size:30px;padding:4px 26px;border-radius:999px">{p["tamil_month"]} {p["tamil_day"]} · {p["weekday"]}</div></div>
        <div style="position:absolute;top:{960 if greet else 990}px;left:40px;right:40px;text-align:center">{top_line}
          <div class="h fit" style="font-size:{82 if greet else 86}px;line-height:1.1;color:{D};text-shadow:0 4px 0 {G}">இன்றைய ராசி பலன்</div>
          <div class="pill nw" style="display:inline-block;margin-top:14px;font-weight:700;font-size:30px;padding:8px 30px;border-radius:999px">{hook}</div></div>'''
        return s.base(inner)

    def panchang(s):
        D, G = s.c[0], s.c[2]
        p = s.x["p"]
        tiles = ""
        small = len(s.x["prows"]) > 8      # 10 rows since 1 Nov (நல்ல நேரம், சூலம்): smaller tiles so nothing hides behind the சந்திராஷ்டமம் bar
        pad, fl, fv, fs = ("7px 22px", 22, 34, 19) if small else ("12px 24px", 25, 40, 21)
        for label, val, sub, col in s.x["prows"]:
            colr = {"bad": "#c62828", "good": "#2e7d32"}.get(col, D)
            tiles += (f'<div style="background:#fffdf7;border:2.5px solid {G};border-radius:22px;padding:{pad};border-left:12px solid {colr}">'
                      f'<div style="font-weight:700;font-size:{fl}px;color:{colr}">{label}</div>'
                      f'<div class="h fit" style="font-size:{fv}px;line-height:1.2">{val}</div>'
                      + (f'<div class="fit" style="font-weight:600;font-size:{fs}px;color:#7b5a3c">{sub}</div>' if sub or not small else "") + '</div>')
        ch = p["chandrashtamam"] + (f' ({p["chandrashtamam_end"]}, பின் {p["chandrashtamam_next"]})' if p["chandrashtamam_end"] else "")
        inner = f'''{s.header()}
        <div class="h nw" style="position:absolute;top:278px;left:0;right:0;text-align:center;font-size:66px;color:{D};text-shadow:0 3px 0 {G}">இன்றைய பஞ்சாங்கம்</div>
        <div data-stack="top" style="position:absolute;top:370px;left:62px;right:62px;display:grid;grid-template-columns:1fr 1fr;gap:{10 if small else 14}px">{tiles}</div>
        <div data-stack="below" class="pill" style="position:absolute;top:1100px;left:62px;right:62px;border-radius:22px;padding:14px 30px;display:flex;align-items:center;gap:20px">
          <div class="nw" style="font-weight:700;font-size:27px;color:#fde7b0">சந்திராஷ்டமம்</div><div class="h goldtxt fit" style="font-size:40px;flex:1">{ch}</div></div>
        {s.footer(2)}'''
        return s.base(inner)

    def rasi(s, i, r):
        D, DD, G, G2 = s.c[:4]
        petals = "".join(f'<ellipse cx="180" cy="22" rx="12" ry="26" fill="url(#gp)" transform="rotate({k * 22.5} 180 180)"/>' for k in range(16))
        med = (f'<svg width="360" height="360" style="position:absolute;inset:0"><defs><linearGradient id="gp" x1="0" y1="0" x2="0" y2="1">'
               f'<stop offset="0" stop-color="#ffe082"/><stop offset="1" stop-color="{G2}"/></linearGradient><radialGradient id="md">'
               f'<stop offset="0" stop-color="{D}"/><stop offset="1" stop-color="{DD}"/></radialGradient></defs>{petals}'
               f'<circle cx="180" cy="180" r="140" fill="url(#gp)"/><circle cx="180" cy="180" r="128" fill="url(#md)"/>'
               f'<circle cx="180" cy="180" r="116" fill="none" stroke="{G}" stroke-width="2" stroke-dasharray="3 7"/></svg>'
               f'<div class="zod goldtxt" style="position:absolute;inset:0;display:grid;place-items:center;font-size:170px;line-height:1;padding-bottom:8px">{GLYPH[i]}&#xFE0E;</div>')
        lines = ""
        for k, key in enumerate(KEYS):
            rem = k == 4
            tag_bg = f"linear-gradient(180deg,#ffe082,{G})" if rem else f"linear-gradient(180deg,{D},{DD})"
            lines += (f'<div style="display:flex;gap:18px;align-items:center;padding:11px 0;{"border-top:2px dashed rgba(184,128,26,.35);" if k else ""}">'
                      f'<div class="h" style="flex:none;width:168px;text-align:center;font-size:25px;padding:6px 0;border-radius:12px;color:{D if rem else "#fff3c4"};'
                      f'background:{tag_bg};box-shadow:0 0 0 2px {G}">{LABELS[k]}</div>'
                      f'<div class="fit" style="flex:1;font-weight:700;font-size:36px;line-height:1.3;color:{D if rem else "#3a1408"}">{r[key]}</div></div>')
        chand = ('<div class="h" style="display:inline-block;margin:12px 12px 0 0;font-size:24px;color:#fff;background:#c62828;padding:6px 18px;border-radius:999px">'
                 'சந்திராஷ்டமம்</div>') if r["rasi"] == s.x["p"]["chandrashtamam"] else ""
        cn, chex = LUCKY_COL[i]
        inner = f'''{s.header()}
        <div style="position:absolute;top:280px;left:56px;width:360px;height:360px">{med}</div>
        <div style="position:absolute;top:320px;left:450px;right:62px">
          <div style="font-family:BalooL;font-weight:800;letter-spacing:6px;font-size:24px;color:{G2}">{RASI_EN[i]}</div>
          <div class="h fit" style="font-size:{104 if len(r["rasi"]) < 8 else 84}px;line-height:1.1;color:{D};text-shadow:0 3px 0 rgba(232,178,58,.45)">{r["rasi"]}</div>
          <div style="display:flex;gap:4px;margin-top:10px">{star_row(r["stars"], "#ffd54f", "#e09100", "rgba(0,0,0,.12)")}</div>
          {chand}<div style="margin-top:14px;display:inline-block;font-weight:700;font-size:23px;padding:6px 20px;border-radius:999px;color:{D};background:#fde7b0;border:2px solid {G}">{ELEMENT[i]} ராசி</div></div>
        <div style="position:absolute;top:668px;left:62px;right:62px;bottom:150px;display:flex;flex-direction:column;gap:20px">
          <div style="flex:1;background:#fffdf7;border:3px solid {G};border-radius:28px;box-shadow:0 0 0 6px #fff6e4,0 0 0 8px rgba(184,128,26,.5);padding:8px 34px;display:flex;flex-direction:column;justify-content:center">{lines}</div>
          <div style="display:grid;grid-template-columns:1fr 1.25fr;gap:18px">
            <div class="pill" style="border-radius:24px;padding:16px 26px;display:flex;align-items:center;justify-content:space-between"><div style="font-weight:700;font-size:25px;color:#fde7b0">அதிர்ஷ்ட எண்</div>
              <div class="goldtxt" style="font-family:BalooL;font-weight:800;font-size:58px;line-height:1">{LUCKY_NUM[i]}</div></div>
            <div class="pill" style="border-radius:24px;padding:16px 26px;display:flex;align-items:center;justify-content:space-between;gap:12px"><div class="nw" style="font-weight:700;font-size:25px;color:#fde7b0">அதிர்ஷ்ட நிறம்</div>
              <div style="display:flex;align-items:center;gap:12px"><div class="h nw" style="font-size:{28 if len(cn) > 7 else 34}px;color:#fff">{cn}</div>
              <div style="width:40px;height:40px;border-radius:50%;background:{chex};box-shadow:0 0 0 3px {G}"></div></div></div></div></div>
        {s.footer(i + 3, i < 11)}'''
        return s.base(inner)

    def end(s):
        D, DD, G = s.c[:3]
        chip = lambda t, sub: (f'<div class="pill" style="border-radius:26px;padding:24px 10px;text-align:center"><div class="h goldtxt" style="font-size:40px;line-height:1.1">{t}</div>'
                               f'<div style="font-weight:600;font-size:22px;color:#fde7b0;margin-top:6px">{sub}</div></div>')
        inner = f'''<div style="position:absolute;top:190px;left:0;right:0;display:flex;justify-content:center"><img src="{s.x["logo"]}" style="width:380px;height:380px;border-radius:50%;box-shadow:0 0 0 8px {G},0 0 0 14px {D}"></div>
        <div style="position:absolute;top:640px;left:62px;right:62px;text-align:center"><div class="h" style="font-size:74px;line-height:1.15;color:{D}">நாளை காலையும்<br>ராசி பலன் தொடரும்</div>
          <div style="font-weight:700;font-size:32px;margin-top:14px">குடும்பத்தினருடன் பகிருங்கள்</div></div>
        <div style="position:absolute;top:980px;left:62px;right:62px;display:grid;grid-template-columns:1fr 1fr 1fr;gap:18px">{chip("Save", "நாளை பார்க்க")}{chip("Share", "குடும்பத்துக்கு")}{chip("Follow", "தினமும் காலை")}</div>
        {s.footer(15, False)}'''
        return s.base(inner)


# ================================================================== CALENDAR design (Coimbatore)
class Calendar:
    def __init__(s, ctx):
        s.x = ctx
        th = (ctx["fest"] or {}).get("theme", "normal")
        t = THEMES.get(th, THEMES["normal"])
        s.c = t
        s.RED = "#d0191f" if th == "normal" else t[0]
        s.ACC = "#d0191f" if th == "normal" else t[2]
        s.css = f"""*{{margin:0;padding:0;box-sizing:border-box}}html,body{{width:1080px;height:1350px;overflow:hidden}}
body{{position:relative;font-family:'Mukta','BalooL',sans-serif;color:#1c1c1c;background:{"#e9e2d0" if th == "normal" else t[5]}}}
.sheet{{position:absolute;left:44px;right:44px;top:70px;bottom:44px;background:#fffdf6;border-radius:8px;box-shadow:0 10px 30px rgba(0,0,0,.18);
 background-image:repeating-linear-gradient(0deg,transparent 0 59px,rgba(208,25,31,.06) 59px 60px)}}
.h{{font-family:'Baloo','BalooL';font-weight:800}}.zod{{font-family:'Zod';font-variant-emoji:text;line-height:1}}.nw{{white-space:nowrap}}.fit{{white-space:nowrap;overflow:hidden}}"""

    def top(s):
        holes = "".join(f'<div style="position:absolute;top:-20px;left:{x}px;width:30px;height:46px;border-radius:15px;background:#9e9e9e;box-shadow:inset 0 3px 4px rgba(0,0,0,.4)"></div>' for x in (260, 700))
        return holes + '<div style="position:absolute;top:58px;left:0;right:0;border-top:3px dashed #d7cdb5"></div>'

    def brand(s):
        p = s.x["p"]
        return (f'<div style="position:absolute;top:84px;left:36px;right:36px;display:flex;justify-content:space-between;align-items:center">'
                f'<div style="display:flex;align-items:center;gap:14px"><img src="{s.x["logo"]}" style="width:100px;height:100px;border-radius:50%">'
                f'<div class="h nw" style="font-size:36px;color:{s.RED}">{s.x["brand"]}</div></div>'
                f'<div class="nw" style="font-weight:700;font-size:26px">{p["date_ta"]} · {p["weekday"]}</div></div>')

    def foot(s, n):
        return (f'<div style="position:absolute;bottom:26px;left:56px;right:56px;display:flex;justify-content:space-between;align-items:center">'
                f'<div style="font-family:BalooL;font-weight:800;font-size:24px;color:{s.RED}">{n:02d} <span style="color:#999">/ 15</span></div>'
                f'<div style="display:flex;align-items:center;gap:12px"><img src="{s.x["logo"]}" style="width:64px;height:64px;border-radius:50%">'
                f'<span class="h nw" style="font-size:26px;color:{s.RED}">{s.x["brand"]}</span></div></div>')

    def cover(s):
        p, f = s.x["p"], s.x["fest"]
        greet = greeting(f)
        emb = (f'<div style="position:absolute;top:150px;right:60px">{emblem_svg(s.c[6], s.c, 170)}</div>' if f else "")
        body = f'''<div class="sheet">{s.top()}{s.brand()}{emb}
          <div style="position:absolute;top:230px;left:0;right:0;text-align:center">
            <div style="font-family:BalooL;font-weight:800;font-size:300px;line-height:1;color:{s.RED}">{int(p["date"][8:])}</div>
            <div class="h nw" style="font-size:58px">{p["tamil_month"]} {p["tamil_day"]} · {p.get("weekday_full") or p["weekday"] + "க்கிழமை"}</div>
            <div class="nw" style="font-weight:700;font-size:28px;color:#555;margin-top:4px">{p["date_ta"].split(" ", 1)[1]} · {p["tithi"]} · {p["nakshatra"]}</div></div>
          {f'<div class="h fit" style="position:absolute;top:735px;left:56px;right:56px;text-align:center;font-size:44px;color:{s.RED}">{greet}</div>' if greet else ""}
          <div style="position:absolute;top:810px;left:56px;right:56px;border-top:3px solid #1c1c1c;border-bottom:3px solid #1c1c1c;padding:18px 0;text-align:center">
            <div class="h fit" style="font-size:80px;line-height:1.1;color:{s.RED}">இன்றைய ராசி பலன்</div>
            <div style="display:flex;justify-content:center;gap:16px;margin-top:10px">{"".join(f'<span class="zod" style="font-size:40px">{g}&#xFE0E;</span>' for g in GLYPH)}</div></div>
          <div class="nw" style="position:absolute;top:1060px;left:0;right:0;text-align:center;font-weight:700;font-size:30px">{s.x["hook"]}</div>
          <div class="nw" style="position:absolute;top:1110px;left:0;right:0;text-align:center;font-weight:700;font-size:28px">ராகு காலம் <b style="color:{s.RED}">{p["rahu"]}</b> · எமகண்டம் <b style="color:{s.RED}">{p["emagandam"]}</b></div>
          {s.foot(1)}</div>'''
        return page(s.css, body)

    def panchang(s):
        p = s.x["p"]
        small = len(s.x["prows"]) > 8
        pad, fl, fv, fs = (2, 27, 31, 19) if small else (7, 30, 38, 22)
        rows = "".join(f'<div style="display:grid;grid-template-columns:290px 1fr;align-items:center;padding:{pad}px 0;border-bottom:1.5px solid #e5dccb">'
                       f'<div style="font-weight:700;font-size:{fl}px;color:{ {"bad": s.RED, "good": "#2e7d32"}.get(col, "#1c1c1c") }">{label}</div>'
                       f'<div style="min-width:0"><div class="h fit" style="font-size:{fv}px;line-height:1.15">{val}</div>'
                       + (f'<div class="fit" style="font-weight:600;font-size:{fs}px;color:#666">{sub}</div>' if sub or not small else "") + '</div></div>'
                       for label, val, sub, col in s.x["prows"])
        ch = p["chandrashtamam"] + (f' ({p["chandrashtamam_end"]}, பின் {p["chandrashtamam_next"]})' if p["chandrashtamam_end"] else "")
        body = f'''<div class="sheet">{s.top()}{s.brand()}
          <div style="position:absolute;top:220px;left:0;right:0;height:110px;background:{s.RED};display:flex;align-items:center;justify-content:center">
            <div class="h nw" style="font-size:64px;color:#fff">இன்றைய பஞ்சாங்கம்</div></div>
          <div data-stack="top" style="position:absolute;top:{335 if small else 345}px;left:56px;right:56px">{rows}</div>
          <div data-stack="below" style="position:absolute;bottom:110px;left:56px;right:56px;border:3px solid {s.RED};padding:14px 24px;display:flex;align-items:center;gap:22px">
            <div class="nw" style="font-weight:700;font-size:30px;color:{s.RED}">சந்திராஷ்டமம்</div><div class="h fit" style="font-size:38px;flex:1">{ch}</div></div>
          {s.foot(2)}</div>'''
        return page(s.css, body)

    def rasi(s, i, r):
        lines = "".join(f'<div style="display:flex;gap:18px;align-items:center;padding:12px 0;{"border-top:1.5px solid #e5dccb;" if k else ""}">'
                        f'<div class="h" style="flex:none;width:170px;text-align:center;font-size:26px;padding:4px 0;border:2.5px solid {s.RED};'
                        f'color:{"#fff" if k == 4 else s.RED};background:{s.RED if k == 4 else "#fff"}">{LABELS[k]}</div>'
                        f'<div class="fit" style="flex:1;font-weight:700;font-size:38px;line-height:1.35;color:{s.RED if k == 4 else "#1c1c1c"}">{r[key]}</div></div>'
                        for k, key in enumerate(KEYS))
        chand = ('<span class="h" style="margin-left:14px;font-size:24px;color:#d0191f;background:#fff;padding:4px 14px;border-radius:999px">சந்திராஷ்டமம்</span>'
                 if r["rasi"] == s.x["p"]["chandrashtamam"] else "")
        cn, chex = LUCKY_COL[i]
        body = f'''<div class="sheet">{s.top()}{s.brand()}
          <div style="position:absolute;top:230px;left:0;right:0;height:250px;background:{s.RED};display:flex;align-items:center;padding:0 40px;gap:30px">
            <div class="zod" style="font-size:180px;color:#fff;width:200px;text-align:center">{GLYPH[i]}&#xFE0E;</div>
            <div style="min-width:0;flex:1"><div style="font-family:BalooL;font-weight:800;letter-spacing:6px;font-size:24px;color:#ffd6d6">{RASI_EN[i]}</div>
              <div class="h fit" style="font-size:{100 if len(r["rasi"]) < 8 else 84}px;line-height:1.1;color:#fff">{r["rasi"]}</div>
              <div style="display:flex;align-items:center">{star_row(r["stars"], "#ffe082", "#ffc107", "rgba(255,255,255,.3)", 40)}{chand}</div></div></div>
          <div style="position:absolute;top:500px;left:56px;right:56px;bottom:230px;display:flex;flex-direction:column;justify-content:center">{lines}</div>
          <div style="position:absolute;bottom:110px;left:56px;right:56px;display:grid;grid-template-columns:1fr 1.2fr;border:2px solid #1c1c1c">
            <div style="padding:16px 22px;border-right:2px solid #1c1c1c;display:flex;justify-content:space-between;align-items:center"><span style="font-weight:700;font-size:26px">அதிர்ஷ்ட எண்</span><span style="font-family:BalooL;font-weight:800;font-size:56px;color:{s.RED};line-height:1">{LUCKY_NUM[i]}</span></div>
            <div style="padding:16px 22px;display:flex;justify-content:space-between;align-items:center;gap:8px"><span class="nw" style="font-weight:700;font-size:26px">அதிர்ஷ்ட நிறம்</span><span class="h nw" style="font-size:{28 if len(cn) > 7 else 34}px;color:{s.RED};display:flex;gap:10px;align-items:center">{cn}<i style="width:32px;height:32px;border-radius:50%;background:{chex};border:2px solid #1c1c1c;display:inline-block"></i></span></div></div>
          {s.foot(i + 3)}</div>'''
        return page(s.css, body)

    def end(s):
        box = lambda t, sub: (f'<div style="border:3px solid #1c1c1c;padding:22px 10px;text-align:center"><div style="font-family:BalooL;font-weight:800;font-size:42px;color:{s.RED}">{t}</div>'
                              f'<div style="font-weight:700;font-size:24px">{sub}</div></div>')
        body = f'''<div class="sheet">{s.top()}
          <div style="position:absolute;top:120px;left:0;right:0;display:flex;justify-content:center"><img src="{s.x["logo"]}" style="width:380px;height:380px;border-radius:50%;box-shadow:0 10px 30px rgba(0,0,0,.25)"></div>
          <div style="position:absolute;top:540px;left:40px;right:40px;text-align:center"><div class="h" style="font-size:76px;line-height:1.2;color:{s.RED}">நாளை காலையும்<br>ராசி பலன் தொடரும்</div>
            <div style="font-weight:700;font-size:32px;margin-top:12px">குடும்பத்தினருடன் பகிருங்கள்</div></div>
          <div style="position:absolute;top:900px;left:56px;right:56px;display:grid;grid-template-columns:1fr 1fr 1fr;gap:18px">{box("Save", "நாளை பார்க்க")}{box("Share", "குடும்பத்துக்கு")}{box("Follow", "தினமும் காலை")}</div>
          {s.foot(15)}</div>'''
        return page(s.css, body)


def panchang_rows(p, town):
    day = p.get("weekday_full") or p["weekday"] + "க்கிழமை"
    if p.get("subha_muhurtham"):
        day += " · சுபமுகூர்த்த நாள்"
    rows = [("தமிழ் தேதி", f'{p["tamil_month"]} {p["tamil_day"]}', day, ""),
            ("திதி", p["tithi"], f'{p["paksha"]} · {p["tithi_end"]} · பின் {p["tithi_next"]}', ""),
            ("நட்சத்திரம்", p["nakshatra"], f'{p["nakshatra_end"]} · பின் {p["nakshatra_next"]}', ""),
            ("யோகம்", p["yogam"], p["yogam_end"], ""),
            ("சூரிய உதயம்", p["sunrise"].split(" ", 1)[1], f'{town} · அஸ்தமனம் {p["sunset"].split(" ", 1)[1]}', "good")]
    if p.get("nalla_morning"):      # owner 1 Nov: நல்ல நேரம் and சூலம் too
        rows.append(("நல்ல நேரம்", f'காலை {p["nalla_morning"]}', f'மாலை {p["nalla_evening"]}', "good"))
    rows += [("ராகு காலம்", p["rahu"], "", "bad"),
             ("எமகண்டம்", p["emagandam"], "", "bad"),
             ("குளிகை", p["kuligai"], "", "bad")]
    if p.get("sulam"):
        rows.append(("சூலம்", p["sulam"], f'பரிகாரம்: {p["sulam_parigaram"]}', ""))
    return rows


def slides_html(design, ctx):
    D = Temple(ctx) if design == "temple" else Calendar(ctx)
    return [D.cover(), D.panchang()] + [D.rasi(i, r) for i, r in enumerate(ctx["rasis"])] + [D.end()]


def render(design, ctx, out_dir):
    """-> list of 15 JPEG paths; raises if any text still does not fit"""
    from playwright.sync_api import sync_playwright
    from PIL import Image
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    paths, problems = [], []
    with sync_playwright() as pw:
        br = pw.chromium.launch()
        pg = br.new_page(viewport={"width": 1080, "height": 1350})
        for n, html in enumerate(slides_html(design, ctx), 1):
            f = out_dir / f"s{n:02d}.html"
            f.write_text(html, encoding="utf-8")
            pg.goto(f"file://{f}")
            pg.wait_for_function("document.body.dataset.ready==='1'", timeout=20000)
            pg.wait_for_timeout(150)
            bad = pg.evaluate("[...document.querySelectorAll('.fit')].filter(e=>e.scrollWidth>e.clientWidth+1).map(e=>e.textContent.trim())")
            problems += [f"slide {n}: '{b}' does not fit" for b in bad]
            # a block must end above the bar under it (1 Nov: 10 panchangam rows ran under the சந்திராஷ்டமம் bar)
            if pg.evaluate("(()=>{const a=document.querySelector('[data-stack=top]'),b=document.querySelector('[data-stack=below]');"
                           "return !!(a&&b&&a.getBoundingClientRect().bottom>b.getBoundingClientRect().top-4)})()"):
                problems.append(f"slide {n}: the panchangam rows run under the bar below them")
            png = out_dir / f"slide_{n:02d}.png"
            pg.screenshot(path=str(png))
            jpg = out_dir / f"slide_{n:02d}.jpg"
            Image.open(png).convert("RGB").save(jpg, quality=93, optimize=True)
            paths.append(jpg)
        br.close()
    if problems:
        raise RuntimeError("; ".join(problems))
    return paths
