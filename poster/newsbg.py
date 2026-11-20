"""owner 20 Nov: the background of a reel that has NO picture (the image models failed) - never the page logo. A designed, realistic
night-city look: soft out-of-focus lights (bokeh), light streaks, a dark vignette and film grain, coloured by the kind of news
(power cut: warm street lights on deep blue / rain: blue-grey with rain streaks / accident, police, fire: red and blue siren lights /
the rest: navy with gold and teal lights). Each story gets its own variation (seeded by its id). No AI, no cost.
make(row, dst) -> dst (a 1080x1920 JPEG)."""
import hashlib
import random
import re
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

W, H = 1080, 1920
THEMES = {      # top colour, bottom colour, light colours
    "power": ((6, 12, 30), (18, 30, 62), [(255, 190, 90), (255, 160, 60), (255, 220, 150), (120, 170, 255)]),
    "rain": ((12, 20, 32), (40, 56, 74), [(170, 200, 230), (120, 160, 210), (230, 240, 255), (255, 200, 120)]),
    "alert": ((10, 8, 18), (34, 16, 30), [(255, 60, 60), (60, 120, 255), (255, 120, 80), (120, 160, 255)]),
    "news": ((8, 14, 30), (22, 36, 66), [(255, 200, 90), (60, 200, 210), (255, 235, 180), (120, 160, 255)]),
}
WORDS = [("power", r"மின்\s*தடை|மின்\s*நிறுத்த|power ?cut|shutdown"),      # word stems: Tamil endings change (விபத்து / விபத்தில்)
         ("rain", r"மழை|புயல்|வெள்ள|வானிலை|rain|weather|flood|cyclone"),
         ("alert", r"விபத்|காவல்|போலீ|கொலை|திருட|கைது|தீப்பிடி|accident|police|fire|crime|murder|theft|arrest")]


def theme(row):
    txt = " ".join(str((row or {}).get(k) or "") for k in ("category", "headline_ta", "headline_en"))
    for name, rx in WORDS:
        if re.search(rx, txt, re.I):
            return name
    return "news"


def make(row, dst):
    row = row or {}
    name = theme(row)
    top, bot, lights = THEMES[name]
    rnd = random.Random(int(hashlib.md5(str(row.get("story_id") or row.get("headline_ta") or "x").encode()).hexdigest()[:8], 16))
    im = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(im)
    for y in range(H):      # sky: dark at the top, lighter towards the street
        t = (y / H) ** 1.3
        d.line([(0, y), (W, y)], fill=tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)))
    glow = Image.new("RGB", (W, H))      # big soft glow behind the middle of the reel
    g = ImageDraw.Draw(glow)
    c = lights[0]
    g.ellipse([W * 0.1, H * 0.3, W * 0.9, H * 0.75], fill=tuple(int(v * 0.35) for v in c))
    im = ImageChops.add(im, glow.filter(ImageFilter.GaussianBlur(220)))
    for blur, count, rmin, rmax, k in ((60, 9, 90, 170, 0.55), (22, 26, 30, 80, 0.7), (6, 40, 6, 22, 0.9)):      # 3 depths of out-of-focus lights
        layer = Image.new("RGB", (W, H))
        ld = ImageDraw.Draw(layer)
        for _ in range(count):
            x = rnd.uniform(-60, W + 60)
            y = rnd.uniform(H * 0.15, H * 0.95) if rnd.random() < 0.8 else rnd.uniform(0, H)
            r = rnd.uniform(rmin, rmax)
            col = rnd.choice(lights)
            a = rnd.uniform(0.35, 1.0) * k
            ld.ellipse([x - r, y - r, x + r, y + r], fill=tuple(int(v * a) for v in col))
        im = ImageChops.add(im, layer.filter(ImageFilter.GaussianBlur(blur)))
    streak = Image.new("RGB", (W, H))      # light trails of traffic, low in the frame
    s = ImageDraw.Draw(streak)
    for _ in range(5):
        y0 = rnd.uniform(H * 0.62, H * 0.9)
        col = rnd.choice(lights)
        s.line([(-50, y0), (W + 50, y0 + rnd.uniform(-160, 160))], fill=tuple(int(v * 0.6) for v in col), width=int(rnd.uniform(4, 10)))
    im = ImageChops.add(im, streak.filter(ImageFilter.GaussianBlur(9)))
    if name == "rain":      # rain streaks
        rain = Image.new("RGB", (W, H))
        rd = ImageDraw.Draw(rain)
        for _ in range(240):
            x, y, ln = rnd.uniform(0, W), rnd.uniform(0, H), rnd.uniform(30, 90)
            rd.line([(x, y), (x - ln * 0.25, y + ln)], fill=(95, 110, 128), width=2)
        im = ImageChops.add(im, rain.filter(ImageFilter.GaussianBlur(1.2)))
    vig = Image.new("L", (W, H), 0)      # dark edges keep the captions readable
    ImageDraw.Draw(vig).ellipse([-W * 0.35, -H * 0.15, W * 1.35, H * 1.15], fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(160))
    im = Image.composite(im, Image.new("RGB", (W, H), (0, 0, 0)), vig)
    noise = Image.effect_noise((W, H), 22).convert("RGB")      # film grain
    im = Image.blend(im, ImageChops.overlay(im, noise), 0.18)
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    im.save(dst, "JPEG", quality=92)
    return dst
