"""owner 20 Nov: promotion ads on news reels - ONLY what the owner approved, on the chosen pages and dates.

The Promo Hub (apps_script_hub/PromoHub.gs in news360-autopost, one Apps Script for every page) keeps the requests from the
Google Form. A page's posting job asks it (GitHub secrets PROMO_URL + PROMO_KEY; without them nothing here runs):
  active_for(page)      the APPROVED promotion for this page today (start <= today <= end, under its reels-a-day count), else None
  reel_promo(p, work)   what reel/promo360.py lays over the reel: the big ad box at the BOTTOM, during the news only (the footer logo
                        strip is hidden while it shows; the page's FOLLOW end card never changes)
  with_line(cap, p)     the caption says it is an ad: "🤝 Sponsored: <brand>" under the first line
  mark_used(p, page, sid)  counted after the reel is posted
  python poster/promo.py samples   (promo.yml) a new request / the owner's REJECTED points -> a sample reel e-mailed by the hub:
                        the page's latest posted news reel with the ad laid over it (the real reel, voice and all)
Nothing here ever stops a news reel: any problem = no ad on that reel."""
import base64
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

IST = timezone(timedelta(hours=5, minutes=30))
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
_CACHE = {}


def url():
    return os.environ.get("PROMO_URL", "").strip()


def key():
    return os.environ.get("PROMO_KEY", "").strip()


def enabled():
    return bool(url() and key())


def log(*a):
    print("promo:", *a, flush=True)


def today():
    return datetime.now(IST).strftime("%Y-%m-%d")


def hub_get(action, **params):
    r = requests.get(url(), params={"action": action, "key": key(), **params}, timeout=90)
    r.raise_for_status()
    d = r.json()
    if not d.get("ok"):
        raise RuntimeError(f"promo hub {action}: {d.get('error')}")
    return d


def hub_post(action, payload):
    r = requests.post(url(), params={"key": key()}, data=json.dumps({"action": action, **payload}, ensure_ascii=False).encode("utf-8"),
                      headers={"Content-Type": "application/json"}, timeout=120)
    r.raise_for_status()
    d = r.json()
    if not d.get("ok"):
        raise RuntimeError(f"promo hub {action}: {d.get('error')}")
    return d


def promos(fresh=False):
    if fresh or "p" not in _CACHE:
        d = hub_get("promos")
        _CACHE["p"] = (d.get("promos") or [], d.get("used") or {})
    return _CACHE["p"]


def pages_of(p):
    return [x.strip() for x in str(p.get("pages") or "").split(",") if x.strip()]


def per_day(p):
    v = str(p.get("per_day") or "all").strip()
    return int(v) if v.isdigit() else None


def choose(rows, used, page, day):
    """the oldest APPROVED promotion for this page and day that still has room today"""
    for p in rows:
        if str(p.get("status")) != "approved" or page not in pages_of(p):
            continue
        if not (str(p.get("start") or "") <= day <= str(p.get("end") or "")):
            continue
        n = per_day(p)
        if n is not None and int(used.get(f"{p.get('id')}|{page}|{day}", 0)) >= n:
            continue
        return p
    return None


def active_for(page, day=None):
    """never raises: no hub / no answer / no approved promotion = None (the reel is made as always)"""
    if not enabled():
        return None
    try:
        rows, used = promos()
        return choose(rows, used, page, day or today())
    except Exception as e:
        log("not read (no ad on this reel):", str(e)[:150])
        return None


def with_line(cap, p):
    """the ad is said in the caption too, under the first line"""
    line = f"🤝 Sponsored: {p.get('brand') or p.get('title')}"
    if not cap or line in cap:
        return cap
    first, _, rest = cap.partition("\n")
    return f"{first}\n{line}\n{rest}" if rest else f"{first}\n{line}"


def asset(p, work):
    """the logo / picture from the form (Google Drive, through the hub) -> a local file, or None"""
    ids = [x.strip() for x in str(p.get("file_ids") or "").split(",") if x.strip()]
    if not ids:
        return None
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    try:
        d = hub_get("file", id=ids[0])
        ext = {"image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}.get(d.get("mime"), ".jpg")
        f = work / f"promo_{ids[0][:12]}{ext}"
        f.write_bytes(base64.b64decode(d["data"]))
        return f
    except Exception as e:
        log("picture not read (the ad is shown without it):", str(e)[:150])
        return None


def reel_promo(p, work):
    pic = asset(p, work)
    return {"id": p.get("id"), "title": p.get("title") or p.get("brand") or "", "message": p.get("message") or "",
            "image": str(pic.resolve()) if pic else ""}


def mark_used(p, page, sid):
    try:
        hub_post("used", {"id": p.get("id"), "page": page, "date": today(), "story": sid})
    except Exception as e:
        log("use not recorded:", str(e)[:150])


# ---------------------------------------------------------------- the sample reel for the owner
PAGE_EN = {"namakkal": "Namakkal 360", "rasipuram": "Rasipuram 360", "coimbatore": "Coimbatore 360", "salem": "Salem 360",
           "erode": "Erode 360", "karur": "Karur 360", "tirupur": "Tirupur 360", "trichy": "Trichy 360"}
SKIP_REEL = re.compile(r"ராசிபலன்|GoldRate|தங்கம்.{0,25}விலை|Gold rate", re.I)


def latest_reel(post, page):
    """the page's latest posted NEWS reel on Instagram: (mp4 url, headline)"""
    token = post.bridge_get("token", page=page)["token"]
    data = post.ig("GET", "me/media", token, fields="id,caption,media_type,media_product_type,media_url,timestamp", limit=25).get("data") or []
    for m in data:
        cap = m.get("caption") or ""
        if m.get("media_type") == "VIDEO" and m.get("media_url") and not SKIP_REEL.search(cap):
            return m["media_url"], cap.split("\n")[0].strip()
    raise RuntimeError("no posted news reel found")


def ad_png(promo, out):
    """the ad box exactly as on the reels (reel/promo360.py), on a see-through 1080x1920 picture, with the footer strip covered"""
    sys.path.insert(0, str(ROOT / "reel"))
    import reel as R
    import promo360
    from playwright.sync_api import sync_playwright
    fonts = R.ff("CT", "catamaran", [700, 800, 900]) + R.ff("NST", "noto-sans-tamil", [600, 700, 800])
    page = ("<!doctype html><html><head><meta charset='utf-8'><style>" + fonts +
            "html,body{margin:0;width:1080px;height:1920px;background:transparent;overflow:hidden}"
            "#cover{position:absolute;left:0;top:1820px;width:420px;height:100px;background:linear-gradient(180deg,rgba(6,10,18,.0),#060a12 40%)}"
            "</style></head><body><div id='cover'></div><script>window.renderAt=function(){};const D={end_t:1};</script></body></html>")
    html = promo360.add(page, promo).replace("opacity:0;", "opacity:1;", 1)
    f = Path(out).with_suffix(".html")
    f.write_text(html, encoding="utf-8")
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": 1080, "height": 1920})
        pg.goto(f.resolve().as_uri())
        pg.wait_for_function("document.fonts.status==='loaded'")
        pg.screenshot(path=str(out), omit_background=True)
        b.close()
    return Path(out)


def make_sample(post, p, page, work):
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    mp4_url, headline = latest_reel(post, page)
    src = work / "news.mp4"
    with requests.get(mp4_url, stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(src, "wb") as fh:
            for chunk in r.iter_content(1 << 20):
                fh.write(chunk)
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(src)],
                               capture_output=True, text=True, check=True).stdout.strip())
    png = ad_png(reel_promo(p, work), work / "ad.png")
    out = work / f"{p['id']}_sample.mp4"
    end = max(4.0, dur - 4.2)      # the ad leaves before the FOLLOW end card (about the last 4 s)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-i", str(png), "-filter_complex",
                    f"[0:v][1:v]overlay=0:0:enable='between(t,3,{end:.2f})'[v]", "-map", "[v]", "-map", "0:a?", "-c:v", "libx264",
                    "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", str(out)], check=True)
    return out, headline


def apply_points(p):
    """the owner's REJECTED points -> a new title / message (only what the owner asked; nothing invented). -> (title, message, not_applied)"""
    pts = str(p.get("owner_points") or "").strip()
    if not pts:
        return p.get("title"), p.get("message"), ""
    try:
        sys.path.insert(0, str(ROOT / "research_free"))
        import llm
        system = ("You edit a short Tamil/English sponsor ad for a news reel. Apply ONLY the owner's requested changes to the title "
                  "(max 40 characters) and the message (max 80 characters). Never add offers, prices, phone numbers, addresses or claims "
                  "the owner did not write. Answer only JSON: {\"title\": \"...\", \"message\": \"...\", \"not_applied\": \"requests about "
                  "anything else (design, colours, size, place), in short, or empty\"}")
        user = json.dumps({"title": p.get("title"), "message": p.get("message"), "brand": p.get("brand"), "owner_changes": pts},
                          ensure_ascii=False)
        d, _ = llm.ask_claude(system, user, max_tokens=600)      # the answer comes back as JSON already
        return (str(d.get("title") or p.get("title"))[:40], str(d.get("message") or p.get("message"))[:80],
                str(d.get("not_applied") or ""))
    except Exception as e:
        log("points not applied automatically:", str(e)[:150])
        return p.get("title"), p.get("message"), pts


def samples():
    """promo.yml: make the samples this repo is responsible for (the first chosen page that belongs to this repo)"""
    if not enabled():
        log("PROMO_URL / PROMO_KEY not set - nothing to do")
        return 0
    sys.path.insert(0, str(HERE))
    import post
    mine = list(post.LABEL)
    rows, _ = promos(fresh=True)
    n = 0
    for p in rows:
        st = str(p.get("status"))
        if st not in ("sample_needed", "changes"):
            continue
        chosen = pages_of(p)
        pg = chosen[0] if chosen else None
        if pg not in mine:      # the sample is made by the repo of the FIRST chosen page (one sample per request)
            continue
        not_applied = ""
        if st == "changes":
            title, message, not_applied = apply_points(p)
            p = dict(p, title=title, message=message)
            hub_post("update", {"id": p["id"], "title": title, "message": message, "status": "sample_needed"})
        try:
            mp4, headline = make_sample(post, p, pg, ROOT / "out" / "promo" / p["id"])
            link = post.upload(mp4, "video")
            hub_post("sample", {"id": p["id"], "page": pg, "page_label": post.LABEL.get(pg, pg), "video_url": link, "headline": headline,
                                "title": p.get("title"), "message": p.get("message"), "not_applied": not_applied})
            log(f"{p['id']}: sample e-mailed ({link})")
            n += 1
        except Exception as e:
            log(f"{p['id']}: sample not made:", str(e)[:300])
    return n


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "samples":
        samples()
