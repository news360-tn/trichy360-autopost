"""owner 31 Oct: the reel uses the news's OWN photo from the source article when one really shows this news.

Steps (any failure -> [] and the story gets its AI pictures exactly as before):
  1. every image on the source page (og:image, JSON-LD, article <img>) - logos, icons, avatars, ads are skipped
  2. a photo the paper labels 'file photo' (பிரதிப் படம் / கோப்புப் படம்) or uploaded weeks before the news is not used
  3. a free vision model (Gemini) says whether it shows THIS news and where the real photograph is (the outlet's text panel,
     logo or graphic borders are cut away - e.g. a Thanthi TV thumbnail is half red text box)
  4. too small to be presentable (< MIN_SIDE px after the cut) -> not used
  5. small / soft photo -> AI super-resolution (OpenCV FSRCNN, free, < 1 s) + gentle sharpening and contrast
  6. a 9:16 picture: the photo on a blurred copy of itself (owner 31 Oct: no credit on it; the watermark / channel logo printed on
     the photo is removed - cut off at an edge, painted over inside)
Pictures for a reel: the cover is the best photo; the next ones are other relevant photos of the page, else a closer crop of the cover.
"""
import base64, datetime, html, io, json, os, re, sys, time
from urllib.parse import urljoin, urlparse

import requests
from PIL import Image, ImageEnhance, ImageFilter, ImageFont, ImageOps, ImageStat

try:      # some outlets serve AVIF only
    import pillow_avif  # noqa: F401
except Exception:
    pass

W, H = 1152, 2048          # same size the AI pictures are made at (imagegen.to_story_size)
MIN_SIDE = int(os.environ.get("REAL_PHOTO_MIN_SIDE", "320"))      # shorter side of the photo itself (after the cut), in px
MAX_CANDIDATES = 6
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
      "Accept": "image/jpeg,image/png,image/webp,image/*;q=0.8,*/*;q=0.5"}

SKIP_URL = re.compile(r"logo|icon|avatar|author|profile|sprite|placeholder|default[-_.]|banner|advert|/ads?/|[-_/]ad[-_/]|whatsapp|favicon|"
                      r"share|button|badge|\.svg|\.gif|1x1|pixel|member_avatars|insta_BG|google_news|newsletter|app-?store|play-?store|"
                      r"subscribe|follow|qr[-_]?code|emoji|flag[-_]|weather-icon|lazy|blank\.", re.I)
FILE_PHOTO = re.compile(r"பிரதிப்\s*படம்|பிரதி\s*படம்|கோப்புப்\s*படம்|கோப்பு\s*படம்|மாதிரிப்\s*படம்|சித்தரிப்புப்\s*படம்|சித்தரிப்பு|"
                        r"representational|representative image|file photo|file image|file pic|stock image|for representation", re.I)
CREDIT = [("dinamalar", "Dinamalar"), ("dinamani", "Dinamani"), ("dinakaran", "Dinakaran"), ("dailythanthi", "Daily Thanthi"),
          ("thanthitv", "Thanthi TV"), ("maalaimalar", "Maalaimalar"), ("newindianexpress", "The New Indian Express"),
          ("indianexpress", "Indian Express Tamil"), ("hindutamil", "Hindu Tamil Thisai"), ("thehindu", "The Hindu"),
          ("puthiyathalaimurai", "Puthiya Thalaimurai"), ("polimernews", "Polimer News"), ("news18", "News18 Tamil"),
          ("oneindia", "Oneindia Tamil"), ("vikatan", "Vikatan"), ("sunnews", "Sun News"), ("kalaignarseithigal", "Kalaignar Seithigal"),
          ("abplive", "ABP Nadu"), ("timesofindia", "Times of India"), ("dtnext", "DT Next"), ("tamilmurasu", "Tamil Murasu"),
          ("nakkheeran", "Nakkheeran"), ("lotusnews", "Lotus News"), ("tamil.samayam", "Samayam Tamil"), ("zeenews", "Zee Tamil News"),
          ("bbc", "BBC Tamil"), ("tamilmaninewstoday", "Tamilmani News")]


NEEDS_RETRY = [False]      # True when for_story() gave up only because the Gemini photo check was out of quota

def credit_of(url):
    host = (urlparse(url or "").netloc or "").lower()
    for k, name in CREDIT:
        if k in host:
            return name
    return re.sub(r"^www\.", "", host).split(":")[0]


def _best_src(tag):
    """the largest picture an <img> tag offers (srcset > data-src > src)"""
    m = re.search(r'srcset="([^"]+)"', tag) or re.search(r'data-srcset="([^"]+)"', tag)
    if m:
        best, bw = None, -1
        for part in m.group(1).split(","):
            bits = part.strip().split()
            if not bits:
                continue
            w = int(re.sub(r"\D", "", bits[1]) or 0) if len(bits) > 1 else 0
            if w >= bw:
                best, bw = bits[0], w
        if best:
            return best
    m = re.search(r'(?:data-src|data-original|data-lazy-src|src)="([^"]+)"', tag)
    return m.group(1) if m else ""


def _key(u):
    """one picture in many sizes (?w=800 / fit-in/1280x960 / _lrg) counts once"""
    u = re.sub(r"[?#].*$", "", u)
    u = re.sub(r"/fit-in/\d+x\d+(/filters:[^/]+)?", "", u)
    return u.lower()


def candidates(page, url):
    """[(image_url, caption_text, is_main)] of the article page, the main picture (og:image / JSON-LD) first"""
    page = page or ""
    out, seen = [], set()

    def add(u, cap="", main=False):
        u = html.unescape((u or "").strip())
        if not u or u.startswith("data:"):
            return
        u = urljoin(url, u)
        if not u.startswith("http") or SKIP_URL.search(u):
            return
        k = _key(u)
        if k in seen:
            return
        seen.add(k)
        out.append((u, cap, main))

    for pat in (r'<meta[^>]+(?:property|name)="og:image(?::url)?"[^>]+content="([^"]+)"', r'<meta[^>]+content="([^"]+)"[^>]+(?:property|name)="og:image"',
                r'<meta[^>]+name="twitter:image(?::src)?"[^>]+content="([^"]+)"'):
        for m in re.finditer(pat, page, re.I):
            add(m.group(1), main=True)
    for blk in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', page, flags=re.S):
        for m in re.finditer(r'"(?:image|thumbnailUrl|contentUrl)"\s*:\s*(?:\[\s*)?(?:\{[^{}]*?"url"\s*:\s*)?"(https?:[^"]+)"', blk):
            if not SKIP_URL.search(m.group(1)):
                add(m.group(1).replace("\\/", "/"), main=True)
    body = re.sub(r"<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", page, flags=re.S)
    for m in re.finditer(r"<img\b[^>]*>", body, re.I):
        tag = m.group(0)
        if re.search(r'(?:width|height)="(\d{1,2})(?:px)?"', tag):      # 16 x 16 icons
            continue
        after = re.sub(r"<[^>]+>", " ", body[m.end():m.end() + 600])
        alt = re.search(r'alt="([^"]*)"', tag)
        add(_best_src(tag), cap=((alt.group(1) if alt else "") + " " + re.sub(r"\s+", " ", after)[:220]).strip())
    # a caption written right after the main picture applies to it too (Dinamani: '<img ...><p>சிறை - பிரதிப் படம்</p>')
    for i, (u, cap, main) in enumerate(out):
        if main and not cap:
            for u2, cap2, _ in out:
                if _key(u2) == _key(u) or os.path.basename(_key(u2)) == os.path.basename(_key(u)):
                    out[i] = (u, cap2, main)
    for i, (u, cap, main) in enumerate(out):
        if main:
            m = re.search(re.escape(os.path.basename(_key(u)))[:60], body, re.I) if os.path.basename(_key(u)) else None
            if m:
                near = re.sub(r"<[^>]+>", " ", body[m.end():m.end() + 800])
                out[i] = (u, (cap + " " + re.sub(r"\s+", " ", near)[:220]).strip(), main)
    return out[:MAX_CANDIDATES * 2]


def _dates_in_url(u):
    out = []
    for y, mo, d in re.findall(r"(20\d\d)[-/_]?(\d\d)[-/_]?(\d\d)(?!\d{3,})", u):
        try:
            out.append(datetime.date(int(y), int(mo), int(d)))
        except ValueError:
            pass
    return out


def is_file_photo(u, caption, published=None):
    """the paper's own label says file / representative picture, or the picture was uploaded long before the news"""
    if FILE_PHOTO.search(caption or ""):
        return "labelled file / representative photo"
    ref = published or datetime.date.today()
    for d in _dates_in_url(u):
        if (ref - d).days > int(os.environ.get("REAL_PHOTO_MAX_AGE_DAYS", "4")):
            return f"photo uploaded {d.isoformat()} (older than the news)"
    return ""


def download(u, timeout=30):
    r = requests.get(u, headers=UA, timeout=timeout)
    r.raise_for_status()
    im = Image.open(io.BytesIO(r.content))
    im.load()
    return ImageOps.exif_transpose(im).convert("RGB")


def _jpeg(im, q=92):
    b = io.BytesIO()
    im.save(b, "JPEG", quality=q)
    return b.getvalue()


VISION_DOWN = [0.0]      # owner 31 Oct: when Gemini says 'too many requests' (429) the photo check rests 30 min - the free quota is the writer's


def vision_resting():
    return time.time() - VISION_DOWN[0] < float(os.environ.get("REAL_PHOTO_VISION_REST", "1800"))


def vision(im, headline, key=None):
    """{"match": bool, "real_photo": bool, "box": [x0,y0,x1,y1] in px or None, "why": str} from a free Gemini vision model; None if unavailable"""
    key = key or os.environ.get("GEMINI_API_KEY")
    if not key or vision_resting():
        return None
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import imagegen
        models = imagegen._vision_models(key)
    except Exception:
        models = ["gemini-2.5-flash"]
    small = im.copy()
    small.thumbnail((1024, 1024))
    prompt = (f'News headline: "{headline}"\n'
              "Look at this picture from the news article. Answer only JSON:\n"
              '{"real_photo": true if it is a real camera photograph (false for a logo, poster, text card, map, chart, cartoon, AI art or '
              'a screenshot of text), "match": true only if the photograph shows THIS news (its place, event, people or objects) - '
              'false for a generic or stock picture, "box_2d": [ymin, xmin, ymax, xmax] (0-1000) of the largest area that is ONLY the real '
              'photograph - leave out any text panel, big headline text, channel logo, watermark band or graphic border, '
              '"marks": [[ymin, xmin, ymax, xmax], ...] (0-1000) of EVERY watermark, channel / newspaper logo, website name, '
              'copyright text, date stamp or caption text that is printed ON the photograph itself ([] if none), '
              '"why": "short reason"}')
    body = {"contents": [{"parts": [{"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(_jpeg(small, 88)).decode()}},
                                    {"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0}}
    last = None
    for model in models[:4]:
        try:
            r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                              headers={"x-goog-api-key": key, "Content-Type": "application/json"}, json=body, timeout=40)
            r.raise_for_status()
            j = json.loads(r.json()["candidates"][0]["content"]["parts"][0]["text"])
            if isinstance(j, list):
                j = j[0] if j else {}
            def px(b):
                if not (isinstance(b, list) and len(b) == 4):
                    return None
                try:
                    y0, x0, y1, x1 = [max(0, min(1000, float(v))) for v in b]
                except Exception:
                    return None
                if x1 <= x0 or y1 <= y0:
                    return None
                return [round(x0 * im.width / 1000), round(y0 * im.height / 1000), round(x1 * im.width / 1000), round(y1 * im.height / 1000)]
            marks = [m for m in (px(b) for b in (j.get("marks") or [])[:8] if isinstance(j.get("marks"), list)) if m]
            return {"match": bool(j.get("match")), "real_photo": bool(j.get("real_photo", True)), "box": px(j.get("box_2d")), "marks": marks,
                    "why": str(j.get("why", ""))[:160]}
        except Exception as e:
            last = e
            if "429" in str(e) or "Too Many Requests" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                VISION_DOWN[0] = time.time()      # one 429 is enough: no other model / picture is asked now
                break
    print("real photo: vision check unavailable:", str(last)[:120], flush=True)
    return None


def cut(im, box):
    """keep only the real photograph (Gemini's box); a box covering under a tenth of the picture is not trusted"""
    if not box:
        return im
    x0, y0, x1, y1 = box
    if (x1 - x0) * (y1 - y0) < 0.10 * im.width * im.height:
        return im
    pad = 4      # stay just inside the edge of the photo (no line of the text panel)
    return im.crop((min(x1, x0 + pad), min(y1, y0 + pad), max(x0, x1 - pad), max(y0, y1 - pad)))


def remove_marks(ph, marks, origin=(0, 0)):
    """owner 31 Oct: the source's watermark / channel logo / printed text is removed from the photo. A mark at an edge is cut away with that
    edge strip; one inside the photo is painted over from its surroundings (OpenCV inpainting). None when the photo cannot be cleaned
    (marks cover too much of it, or a mark inside it and no OpenCV) - that photo is then not used."""
    ox, oy = origin
    w, h = ph.size
    inner = []
    l = t = 0
    r, b = w, h
    for x0, y0, x1, y1 in marks or []:
        x0, y0, x1, y1 = max(0, x0 - ox), max(0, y0 - oy), min(w, x1 - ox), min(h, y1 - oy)
        if x1 <= x0 or y1 <= y0:
            continue      # outside the part that is kept
        bw, bh = x1 - x0, y1 - y0
        # at an edge and thin compared with the photo: cut that strip off (the cheapest, cleanest removal)
        ex, ey = max(3, 0.04 * w), max(3, 0.04 * h)      # 'at the edge' allows a small gap
        if y1 >= h - ey and bh <= 0.18 * h:
            b = min(b, y0 - 2); continue
        if y0 <= ey and bh <= 0.18 * h:
            t = max(t, y1 + 2); continue
        if x0 <= ex and bw <= 0.18 * w:
            l = max(l, x1 + 2); continue
        if x1 >= w - ex and bw <= 0.18 * w:
            r = min(r, x0 - 2); continue
        inner.append((x0, y0, x1, y1))
    if r - l < 0.6 * w or b - t < 0.6 * h:
        return None
    ph = ph.crop((l, t, r, b))
    inner = [(x0 - l, y0 - t, x1 - l, y1 - t) for x0, y0, x1, y1 in inner]
    inner = [(max(0, x0), max(0, y0), min(ph.width, x1), min(ph.height, y1)) for x0, y0, x1, y1 in inner if x1 > 0 and y1 > 0]      # owner 2 Nov (review): x1 > l dropped real marks
    if not inner:
        return ph
    if sum((x1 - x0) * (y1 - y0) for x0, y0, x1, y1 in inner) > 0.10 * ph.width * ph.height:
        return None      # too much would be painted: it would not look like a real photo any more
    try:
        import cv2
        import numpy as np
    except Exception:
        return None
    a = cv2.cvtColor(np.array(ph), cv2.COLOR_RGB2BGR)
    mask = np.zeros(a.shape[:2], np.uint8)
    for x0, y0, x1, y1 in inner:
        pad = max(3, round(0.08 * max(x1 - x0, y1 - y0)))
        mask[max(0, y0 - pad):y1 + pad, max(0, x0 - pad):x1 + pad] = 255
    out = cv2.inpaint(a, mask, 5, cv2.INPAINT_TELEA)
    return Image.fromarray(cv2.cvtColor(out, cv2.COLOR_BGR2RGB))


_SR = {}


def _super_res(im, scale):
    """free AI super-resolution (OpenCV FSRCNN, ~0.3 s); None when OpenCV / the model is not available"""
    try:
        import cv2
        import numpy as np
    except Exception:
        return None
    scale = 4 if scale > 3 else (3 if scale > 2 else 2)
    try:
        if scale not in _SR:
            path = os.path.join(os.environ.get("RUNNER_TEMP", "/tmp"), f"FSRCNN_x{scale}.pb")
            if not os.path.exists(path):
                r = requests.get(f"https://raw.githubusercontent.com/Saafke/FSRCNN_Tensorflow/master/models/FSRCNN_x{scale}.pb", timeout=60)
                r.raise_for_status()
                open(path, "wb").write(r.content)
            sr = cv2.dnn_superres.DnnSuperResImpl_create()
            sr.readModel(path)
            sr.setModel("fsrcnn", scale)
            _SR[scale] = sr
        out = _SR[scale].upsample(cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR))
        return Image.fromarray(cv2.cvtColor(out, cv2.COLOR_BGR2RGB))
    except Exception as e:
        print("real photo: super-resolution not available:", str(e)[:120], flush=True)
        return None


def enhance(im, target=W):
    """a presentable picture: a small photo is enlarged with AI super-resolution (else Lanczos), then gently cleaned and sharpened"""
    if im.width < target:
        f = target / im.width
        big = _super_res(im, f) if f > 1.15 else None
        im = big if big is not None else im
        if im.width != target:
            im = im.resize((target, round(im.height * target / im.width)), Image.LANCZOS)
    elif im.width > 2 * target:
        im = im.resize((2 * target, round(im.height * 2 * target / im.width)), Image.LANCZOS)
    im = ImageOps.autocontrast(im, cutoff=0.5)
    im = ImageEnhance.Contrast(im).enhance(1.05)
    im = ImageEnhance.Color(im).enhance(1.06)
    im = im.filter(ImageFilter.UnsharpMask(radius=1.6, percent=55, threshold=2))
    return im


def sharpness(im):
    """edge strength of the photo at reel size (a very blurred / blocky picture scores low)"""
    g = im.convert("L")
    g = g.resize((540, max(1, round(g.height * 540 / g.width))), Image.LANCZOS)
    return ImageStat.Stat(g.filter(ImageFilter.FIND_EDGES)).stddev[0]


def _font(size):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def compose(photo, credit, zoom=1.0):
    """9:16 picture: the whole photo (or a closer crop of it with zoom > 1) on a blurred, darkened copy of itself, photo in the upper
    middle (the reel's headline and subtitles sit lower). Owner 31 Oct: nothing is written on the picture (no source credit)."""
    if zoom > 1:
        cw, ch = round(photo.width / zoom), round(photo.height / zoom)
        photo = photo.crop(((photo.width - cw) // 2, (photo.height - ch) // 3, (photo.width - cw) // 2 + cw, (photo.height - ch) // 3 + ch))
    bg = ImageOps.fit(photo, (W, H), Image.LANCZOS).filter(ImageFilter.GaussianBlur(42))
    bg = ImageEnhance.Brightness(bg).enhance(0.5)
    if photo.height / photo.width >= 1.45:      # a tall photo fills the frame
        fg = ImageOps.fit(photo, (W, H), Image.LANCZOS, centering=(0.5, 0.35))
        y = 0
    else:
        w = W if photo.height / photo.width >= 0.75 else round(W * 1.12)      # a wide photo is shown a little larger (sides cropped)
        h = min(round(photo.height * w / photo.width), round(H * 0.62))
        fg = ImageOps.fit(photo.resize((w, round(photo.height * w / photo.width)), Image.LANCZOS), (W, h), Image.LANCZOS)
        y = round(H * 0.40 - h / 2)
    bg.paste(fg, (0, max(0, y)))
    return bg


def for_story(url, headline, n=2, published=None, page=None, fetch=None, log=print):
    """up to n 9:16 JPEG pictures (bytes) made from the source article's own relevant photos, and the credit; ([], "") when none fits.
    Never raises: the caller falls back to AI pictures."""
    NEEDS_RETRY[0] = False      # owner 2 Nov (review): never a stale flag from the story before
    if os.environ.get("REAL_PHOTOS", "1") != "1" or not url or not url.startswith("http"):
        return [], ""
    t0 = time.time()
    try:
        if page is None:
            page = (fetch or (lambda u: requests.get(u, headers={**UA, "Accept": "text/html"}, timeout=40).text))(url)
        cands = candidates(page, url)
        if not cands:
            log("real photo: no picture on the source page -> AI pictures")
            return [], ""
        credit = credit_of(url)
        key = os.environ.get("GEMINI_API_KEY")
        NEEDS_RETRY[0] = False
        good = []
        for u, cap, main in cands[:MAX_CANDIDATES]:
            if time.time() - t0 > float(os.environ.get("REAL_PHOTO_SECONDS", "120")):
                break
            why = is_file_photo(u, cap, published)
            if why:
                log(f"real photo skipped ({why}): {u[:90]}")
                continue
            try:
                im = download(u)
            except Exception as e:
                log(f"real photo not downloaded: {str(e)[:80]}")
                continue
            if min(im.size) < 200 or im.width / im.height > 3.2 or im.height / im.width > 3.2:
                continue      # icon / strip / banner
            if key and vision_resting():
                NEEDS_RETRY[0] = True      # owner 2 Nov (review): the article HAS a photo - checked again in a later run
                log("real photo: vision check resting (free quota busy)")
                return [], ""
            v = vision(im, headline, key) if key else None
            if v is None and key and vision_resting():
                NEEDS_RETRY[0] = True
                log("real photo: vision check out of free quota")
                return [], ""
            if v is None and (key or not main):
                continue      # without the vision check only the page's own main picture is trusted (still never a file photo)
            if v is not None and not (v["match"] and v["real_photo"]):
                log(f"real photo not this news ({v['why'][:80]}): {u[:80]}")
                continue
            ph = cut(im, v and v["box"])
            if v and v.get("marks"):
                kept = v["box"] if v["box"] and ph.size != im.size else None
                clean = remove_marks(ph, v["marks"], (kept[0] + 4, kept[1] + 4) if kept else (0, 0))
                if clean is None:
                    log(f"real photo has a watermark / logo that cannot be removed cleanly: {u[:80]}")
                    continue
                log(f"real photo: {len(v['marks'])} watermark / logo mark(s) removed")
                ph = clean
            if min(ph.size) < MIN_SIDE:
                log(f"real photo too small to be presentable ({ph.width}x{ph.height}): {u[:80]}")
                continue
            ph = enhance(ph)
            s = sharpness(ph)
            if s < float(os.environ.get("REAL_PHOTO_MIN_SHARP", "24")):
                log(f"real photo too blurred (sharpness {s:.1f}): {u[:80]}")
                continue
            good.append(ph)
            log(f"real photo used ({ph.width}x{ph.height}, sharpness {s:.1f}" + (f", {v['why'][:60]}" if v else "") + f"): {u[:90]}")
            if len(good) >= n:
                break
        if not good:
            return [], ""
        pics = [compose(good[0], credit)]
        for i in range(1, n):
            pics.append(compose(good[i], credit) if i < len(good) else compose(good[0], credit, zoom=1.0 + 0.35 * i))
        return [_jpeg(p, 93) for p in pics], credit
    except Exception as e:
        log(f"real photo step failed ({str(e)[:120]}) -> AI pictures")
        return [], ""
