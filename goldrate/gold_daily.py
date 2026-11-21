"""Daily gold & silver rate carousel - one post per page per day, every morning (owner 14 Nov).

  python goldrate/gold_daily.py            -> every page in GOLD_PAGES (default: this repo's pages)
  DRY_RUN=1 -> read the rates and make the slides only, never post (slides in out/goldrate/<page>)

When: the Chennai jewellers' association fixes the day's rate at 9:30 AM; the rate pages show it a little later. The job starts
09:40 IST and checks every 5 minutes until GIVE_UP_AT. It posts only when at least 2 pages show TODAY's date and the same 22K
rate (silver: the same per-gram rate). If silver is not confirmed by SILVER_WAIT_UNTIL, the gold slide is posted alone.
Today is compared with the last day saved in goldrate/state/history.json (normally yesterday).
Environment: BRIDGE_URL, BRIDGE_KEY (page tokens), CLOUDINARY_CLOUD, CLOUDINARY_PRESET, FB_* (optional)."""
import json, os, sys, time
from datetime import datetime, timedelta, timezone, date
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import gold_sources as sources      # noqa: E402
import gold_render as render      # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))
IG = "https://graph.instagram.com"
DRY = os.environ.get("DRY_RUN", "") in ("1", "true", "yes")
START_AT = os.environ.get("START_AT", "09:40")
SILVER_WAIT_UNTIL = os.environ.get("SILVER_WAIT_UNTIL", "11:30")
GIVE_UP_AT = os.environ.get("GIVE_UP_AT", "13:00")
# owner 18 Nov: MJDTA publishes the rate twice a day, 9:30 AM and 3:30 PM. GOLD_MODE=pm checks from PM_START until PM_UNTIL and posts
# a 'மாலை விலை மாற்றம்' update only when 2 rate pages show a 22K (or silver) rate different from this morning's post.
MODE = os.environ.get("GOLD_MODE", "am").strip().lower() or "am"
PM_START = os.environ.get("PM_START", "15:40")
PM_UNTIL = os.environ.get("PM_UNTIL", "16:45")
FORCE_DATE = os.environ.get("GOLD_DATE", "")      # testing only (dry runs): YYYY-MM-DD the pages still show
HISTORY = HERE / "state" / "history.json"
STATE_DIR = HERE / "state"

PAGES = {      # owner 14 Nov: every page, each with its own logo and handle; the rate is the same Tamil Nadu (Chennai) rate
    "namakkal": {"town": "நாமக்கல்", "name1": "நாமக்கல்", "handle": "namakkal.360", "tag": "#Namakkal360", "brand_px": 54},
    "rasipuram": {"town": "இராசிபுரம்", "name1": "இராசிபுரம்", "handle": "rasipuram.360", "tag": "#Rasipuram360", "brand_px": 50},
    "coimbatore": {"town": "கோவை", "name1": "கோவை", "handle": "coimbatore360_official", "tag": "#Coimbatore360", "brand_px": 54},
    "salem": {"town": "சேலம்", "name1": "சேலம்", "handle": "salem360.official", "tag": "#Salem360", "brand_px": 54},
    "erode": {"town": "ஈரோடு", "name1": "ஈரோடு", "handle": "erode360.official", "tag": "#Erode360", "brand_px": 54},
    "tirupur": {"town": "திருப்பூர்", "name1": "திருப்பூர்", "handle": "tiruppur360.official", "tag": "#Tiruppur360", "brand_px": 52},
    "trichy": {"town": "திருச்சி", "name1": "திருச்சி", "handle": "trichy360.official", "tag": "#Trichy360", "brand_px": 54},
    "karur": {"town": "கரூர்", "name1": "கரூர்", "handle": "karur360.official", "tag": "#Karur360", "brand_px": 54},
}
MONTH_TA = ["ஜனவரி", "பிப்ரவரி", "மார்ச்", "ஏப்ரல்", "மே", "ஜூன்", "ஜூலை", "ஆகஸ்ட்", "செப்டம்பர்", "அக்டோபர்", "நவம்பர்", "டிசம்பர்"]
MONTH_SHORT = ["ஜன", "பிப்", "மார்", "ஏப்", "மே", "ஜூன்", "ஜூலை", "ஆக", "செப்", "அக்", "நவ", "டிச"]


def log(*a):
    print(datetime.now(IST).strftime("%H:%M:%S"), *a, flush=True)


def clock(hhmm, day):
    h, m = map(int, hhmm.split(":"))
    return datetime(day.year, day.month, day.day, h, m, tzinfo=IST)


def date_ta(day):
    return f"{day.day} {MONTH_TA[day.month - 1]} {day.year}"


def bridge_get(action, **params):
    r = requests.get(os.environ["BRIDGE_URL"], params={"action": action, "key": os.environ["BRIDGE_KEY"], **params}, timeout=120)
    r.raise_for_status()
    d = r.json()
    if not d.get("ok"):
        raise RuntimeError(f"bridge {action}: {d.get('error')}")
    return d


def ig(method, path, token, **params):
    params["access_token"] = token
    for attempt in range(6):
        r = requests.request(method, f"{IG}/{path}", params=params if method == "GET" else None, data=params if method == "POST" else None, timeout=120)
        d = r.json()
        # 19 Nov: Instagram sometimes answers 9007 "media is not ready for publishing" just after the container said FINISHED.
        # Nothing was posted then, so waiting and publishing again is safe (never a double post).
        err = d.get("error") if isinstance(d.get("error"), dict) else {}
        if path.endswith("/media_publish") and err.get("code") == 9007 and attempt < 5:
            time.sleep(10)
            continue
        break
    if r.status_code >= 400 or "error" in d:
        raise RuntimeError(f"Instagram {path}: {d.get('error', d)}")
    return d


def wait_ready(cid, token, minutes=6):
    end = time.time() + minutes * 60
    while time.time() < end:
        st = ig("GET", cid, token, fields="status_code").get("status_code")
        if st == "FINISHED":
            return
        if st in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"container {cid} {st}")
        time.sleep(5)
    raise RuntimeError(f"container {cid} not ready")


def upload(path):
    for attempt in range(3):      # 19 Nov: Cloudinary sometimes refuses once (400 / 5xx) - try again and log its reason
        with open(path, "rb") as f:
            r = requests.post(f"https://api.cloudinary.com/v1_1/{os.environ['CLOUDINARY_CLOUD']}/image/upload",
                              data={"upload_preset": os.environ["CLOUDINARY_PRESET"], "folder": "goldrate"}, files={"file": f}, timeout=300)
        if r.ok:
            break
        print(f"cloudinary upload {r.status_code} (try {attempt + 1}/3): {r.text[:300]}", flush=True)
        time.sleep(10 * (attempt + 1))
    r.raise_for_status()
    return r.json()["secure_url"]


def publish(token, urls, cap):
    uid = ig("GET", "me", token, fields="user_id")["user_id"]
    if len(urls) == 1:
        cid = ig("POST", f"{uid}/media", token, image_url=urls[0], caption=cap)["id"]
    else:
        kids = []
        for u in urls:
            kids.append(ig("POST", f"{uid}/media", token, image_url=u, is_carousel_item="true")["id"])
        for k in kids:
            wait_ready(k, token)
        cid = ig("POST", f"{uid}/media", token, media_type="CAROUSEL", children=",".join(kids), caption=cap)["id"]
    wait_ready(cid, token)
    mid = ig("POST", f"{uid}/media_publish", token, creation_id=cid)["id"]
    link = ig("GET", mid, token, fields="permalink").get("permalink", "")
    return mid, link


# ---------- owner 19 Nov: the same rate as a REEL too (carousels reach few people) - in the Kovai Minnal reel pattern with our 360
# brand (gold_reel.py + gold360_render.py: 10 s, today's price from the first frame, music only) ----------
REEL = os.environ.get("GOLD_REEL", "1") not in ("0", "false", "no")
CAROUSEL = os.environ.get("GOLD_CAROUSEL", "0") in ("1", "true", "yes")      # owner 19 Nov: gold & silver rate - REELS ONLY on every page
REEL_UNTIL = os.environ.get("GOLD_REEL_UNTIL", "15:15")      # a late catch-up never shows the morning rate after the 3:30 PM change


def reel_path(page):
    return STATE_DIR / f"reel_{page}.json"


def reel_done(page, day, token=None):
    try:
        st = json.loads(reel_path(page).read_text(encoding="utf-8"))
        if st.get("date") == day.isoformat():
            return f"state file: {st.get('permalink')}"
    except Exception:
        pass
    if token:      # never twice: Instagram may already have today's reel (state file lost)
        try:
            uid = ig("GET", "me", token, fields="user_id")["user_id"]
            for m in ig("GET", f"{uid}/media", token, fields="caption,permalink,media_product_type", limit=15).get("data", []):
                if m.get("media_product_type") == "REELS" and f"தங்கம், வெள்ளி விலை | {date_ta(day)}" in (m.get("caption") or ""):
                    return f"Instagram already has today's reel {m.get('permalink')}"
        except Exception as e:
            log("could not read recent reels:", str(e)[:150])
    return ""


def upload_video(path):
    for attempt in range(3):      # 19 Nov: Cloudinary sometimes refuses once (400 / 5xx) - try again and log its reason
        with open(path, "rb") as f:
            r = requests.post(f"https://api.cloudinary.com/v1_1/{os.environ['CLOUDINARY_CLOUD']}/video/upload",
                              data={"upload_preset": os.environ["CLOUDINARY_PRESET"], "folder": "goldrate"}, files={"file": f}, timeout=600)
        if r.ok:
            break
        print(f"cloudinary upload {r.status_code} (try {attempt + 1}/3): {r.text[:300]}", flush=True)
        time.sleep(10 * (attempt + 1))
    r.raise_for_status()
    return r.json()["secure_url"]


def publish_reel(token, url, cap):
    uid = ig("GET", "me", token, fields="user_id")["user_id"]
    import gold_reel      # the cover: the gold screen fully built (not the first frame)
    cid = ig("POST", f"{uid}/media", token, media_type="REELS", video_url=url, caption=cap, share_to_feed="true",
             thumb_offset=str(gold_reel.COVER_MS))["id"]
    wait_ready(cid, token, 15)
    mid = ig("POST", f"{uid}/media_publish", token, creation_id=cid)["id"]
    return mid, ig("GET", mid, token, fields="permalink").get("permalink", "")


def page_cfg(pg, token=None):
    """the page's slide / reel settings (PAGES + its logo). owner 19 Nov: the "Follow @..." line shows the page's REAL Instagram
    username when its token can read it - PAGES holds placeholder handles for the new pages. Never raises."""
    p = dict(PAGES[pg], logo=ROOT / "kit" / f"logo_{pg}.png")
    if token and not DRY:
        try:
            name = (ig("GET", "me", token, fields="username") or {}).get("username")
            if name:
                p["handle"] = name
        except Exception as e:
            log(f"{pg}: Instagram username not read - the saved handle is used ({str(e)[:120]})")
    return p


def reel_caption(cap):
    return "🎬 " + cap


def post_reel(pg, p, r, jpgs, cap, out, token, day, pm=False):
    """make + post today's reel; any problem is only logged (the news posts are never touched). -> (media id, permalink) or None.
    pm: the 3:30 PM change update (its own once-a-day check, pm_done; the morning reel does not block it)"""
    if not REEL:
        return None
    try:
        import gold_reel
        mp4, _ = gold_reel.make(p, r, jpgs, out, log)
        if DRY:
            log(f"DRY RUN: {pg} reel {mp4} - not posted")
            return None
        if not pm and reel_done(pg, day, token):
            log(f"{pg}: reel already posted today")
            return None
        url = upload_video(mp4)
        mid, link = publish_reel(token, url, reel_caption(cap))
        log(f"{pg}: {'AFTERNOON ' if pm else ''}REEL POSTED {link}")
        if not pm:
            reel_path(pg).write_text(json.dumps({"date": day.isoformat(), "media_id": mid, "permalink": link,
                                                 "posted_at": datetime.now(IST).isoformat()}, ensure_ascii=False), encoding="utf-8")
        if not CAROUSEL:      # reels only: the reel goes to the page's Facebook page too (when it is set up)
            try:
                sys.path.insert(0, str(ROOT / "poster"))
                import facebook
                facebook.share(pg, f"goldrate-{'pm-' if pm else ''}reel-{day.isoformat()}", "reel", [url], cap, p.get("tag", ""),
                               always=True, story=False)
            except Exception as e:
                log("Facebook step skipped:", str(e)[:150])
        return mid, link
    except Exception as e:
        log(f"{pg}: reel NOT POSTED - {str(e)[:300]}")
        return None


def reel_catchup(pages, day, tokens):
    """carousel posted earlier today but its reel was not (failed, or the reel came later): make only the reel from today's saved rate"""
    if not REEL or DRY or (not FORCE_DATE and datetime.now(IST) >= clock(REEL_UNTIL, day)):
        return
    pages = [pg for pg in pages if not reel_done(pg, day, tokens.get(pg))]
    hist = load_history()
    row = next((h for h in hist if h["date"] == day.isoformat()), None)
    if not pages or not row or not row.get("g22"):
        return
    gold = {"g22": row.get("g22_am", row["g22"]), "g24": row.get("g24_am", row["g24"])}
    sv = row.get("silver_am", row.get("silver"))
    r = rates_for_slides(hist, day, gold, {"silver": sv} if sv else None)
    for pg in pages:
        log(f"{pg}: carousel already posted, reel not yet - making the reel")
        p = page_cfg(pg, tokens.get(pg))
        out = ROOT / "out" / "goldrate" / pg
        jpgs = render.render(p, r, out, log)
        post_reel(pg, p, r, jpgs, caption(p, day, r), out, tokens[pg], day)


# ---------- history: one row per day {"date", "g22", "g24", "silver"} ----------
def load_history():
    try:
        return json.loads(HISTORY.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_today(hist, day, gold, silver):
    row = next((h for h in hist if h["date"] == day.isoformat()), None)
    if row is None:
        row = {"date": day.isoformat()}
        hist.append(row)
    row.update({"g22": gold["g22"], "g24": gold["g24"], "gold_sources": gold["sources"]})
    if silver:
        row.update({"silver": silver["silver"], "silver_sources": silver["sources"]})
    hist.sort(key=lambda h: h["date"])
    del hist[:-60]      # keep two months
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    HISTORY.write_text(json.dumps(hist, ensure_ascii=False, indent=1), encoding="utf-8")


def previous(hist, day, key):
    """the last saved value before today (normally yesterday) and its date"""
    rows = [h for h in hist if h["date"] < day.isoformat() and h.get(key)]
    return (rows[-1][key], date.fromisoformat(rows[-1]["date"])) if rows else (None, None)


def week(hist, day, key, today_val):
    """the last 7 days for the chart: a day with no saved rate (e.g. Sunday) keeps the day before's rate"""
    have = {h["date"]: h[key] for h in hist if h.get(key)}
    start = (day - timedelta(days=6)).isoformat()
    before = [d for d in have if d < start]
    last = have[max(before)] if before else None      # a quiet first day (Sunday) keeps the rate of the last day before it
    pts = []
    first = min(have) if have else day.isoformat()
    for i in range(6, -1, -1):
        d = day - timedelta(days=i)
        v = today_val if i == 0 else have.get(d.isoformat(), last)
        if v is None:
            continue
        last = v
        if d.isoformat() >= first or i == 0:
            pts.append((f"{d.day} {MONTH_SHORT[d.month - 1]}", v))
    return pts


def rates_for_slides(hist, day, gold, silver):
    g22p, pday = previous(hist, day, "g22")
    g24p, _ = previous(hist, day, "g24")
    r = {"date": date_ta(day), "g22": gold["g22"], "g24": gold["g24"],
         "g22_prev": g22p if g22p is not None else gold["g22"], "g24_prev": g24p if g24p is not None else gold["g24"],
         "vs": "நேற்றைய விலையைவிட" if pday == day - timedelta(days=1) else "முந்தைய விலையைவிட",
         "week22": week(hist, day, "g22", gold["g22"])}
    if silver:
        sp, _ = previous(hist, day, "silver")
        r.update({"silver": silver["silver"], "silver_prev": sp if sp is not None else silver["silver"],
                  "weeksilver": week(hist, day, "silver", silver["silver"])})
    return r


def change_text(d, unit):
    if d < 0:
        return f"₹{abs(d):,} குறைவு{unit}"
    if d > 0:
        return f"₹{d:,} உயர்வு{unit}"
    return "மாற்றமில்லை"


def caption(p, day, r):
    lines = [f"💰 இன்றைய தங்கம், வெள்ளி விலை | {date_ta(day)}", "",
             f"🟡 22K தங்கம் (1 கிராம்): ₹{render.inr(r['g22'])} ({change_text(r['g22'] - r['g22_prev'], '')})",
             f"🟡 24K தங்கம் (1 கிராம்): ₹{render.inr(r['g24'])} ({change_text(r['g24'] - r['g24_prev'], '')})"]
    if r.get("silver"):
        lines.append(f"⚪ வெள்ளி (1 கிராம்): ₹{render.inr(r['silver'])} ({change_text(r['silver'] - r['silver_prev'], '')})")
    lines += ["", "சென்னை சந்தை விலை (தமிழ்நாடு). ஜிஎஸ்டி, செய்கூலி, சேதாரம் தனி; கடைகளுக்கு ஏற்ப விலை சற்று மாறலாம்.", "",
              f"தினமும் காலை தங்கம், வெள்ளி விலை அறிய Follow செய்யுங்கள் 🙏 @{p['handle']}", "",
              f"#தங்கம்விலை #GoldRate #SilverRate #{p['town']} {p['tag']}"]      # owner 19 Nov: at most 5 hashtags
    return "\n".join(lines)


def state_path(page):
    return STATE_DIR / f"posted_{page}.json"


def already_posted(page, day, token=None):
    try:
        st = json.loads(state_path(page).read_text(encoding="utf-8"))
        if st.get("date") == day.isoformat():
            return f"state file: {st.get('permalink')}"
    except Exception:
        pass
    if token:
        try:
            uid = ig("GET", "me", token, fields="user_id")["user_id"]
            for m in ig("GET", f"{uid}/media", token, fields="caption,permalink", limit=15).get("data", []):
                if f"இன்றைய தங்கம், வெள்ளி விலை | {date_ta(day)}" in (m.get("caption") or ""):
                    return f"Instagram already has today's post {m.get('permalink')}"
        except Exception as e:
            log("could not read recent posts:", str(e)[:150])
    return ""


def pm_path(page):
    return STATE_DIR / f"pmcheck_{page}.json"


def pm_done(page, day):
    try:
        return json.loads(pm_path(page).read_text(encoding="utf-8")).get("date") == day.isoformat()
    except Exception:
        return False


def pm_caption(p, day, r):
    lines = [f"📢 மாலை விலை மாற்றம் | {date_ta(day)}", "",
             f"🟡 22K தங்கம் (1 கிராம்): ₹{render.inr(r['g22'])} (காலை விலையைவிட {change_text(r['g22'] - r['g22_prev'], '')})",
             f"🟡 24K தங்கம் (1 கிராம்): ₹{render.inr(r['g24'])} (காலை விலையைவிட {change_text(r['g24'] - r['g24_prev'], '')})"]
    if r.get("silver"):
        lines.append(f"⚪ வெள்ளி (1 கிராம்): ₹{render.inr(r['silver'])} (காலை விலையைவிட {change_text(r['silver'] - r['silver_prev'], '')})")
    lines += ["", "சென்னை சந்தை விலை (தமிழ்நாடு) - மதியம் 3:30 மணி நிலவரம். ஜிஎஸ்டி, செய்கூலி, சேதாரம் தனி.", "",
              f"தினமும் தங்கம், வெள்ளி விலை அறிய Follow செய்யுங்கள் 🙏 @{p['handle']}", "",
              f"#தங்கம்விலை #GoldRate #SilverRate #{p['town']} {p['tag']}"]      # owner 19 Nov: at most 5 hashtags
    return "\n".join(lines)


def pm_rates(hist, day, am, gold, silver):
    """the afternoon slides: today's afternoon rate against this morning's posted rate"""
    g22 = gold["g22"] if gold else am["g22"]
    g24 = gold["g24"] if gold else am["g24"]
    r = {"date": date_ta(day), "g22": g22, "g24": g24, "g22_prev": am["g22"], "g24_prev": am["g24"], "vs": "காலை விலையைவிட",
         "kick": "மாலை நிலவரம்", "week22": week(hist, day, "g22", g22)}
    if am.get("silver"):
        s = silver["silver"] if silver else am["silver"]
        r.update({"silver": s, "silver_prev": am["silver"], "weeksilver": week(hist, day, "silver", s)})
    return r


def pm_changed(am, gold, silver):
    return bool((gold and gold["g22"] != am["g22"]) or (silver and am.get("silver") and silver["silver"] != am["silver"]))


def pm_main(pages, day):
    hist = load_history()
    row = next((h for h in hist if h["date"] == day.isoformat()), None)
    if not row:
        log("no morning rate saved for today - afternoon check skipped")
        return 0
    am = {"g22": row.get("g22_am", row["g22"]), "g24": row.get("g24_am", row["g24"]), "silver": row.get("silver_am", row.get("silver"))}
    pages = [pg for pg in pages if DRY or (already_posted(pg, day) and not pm_done(pg, day))]
    if not pages:
        log("afternoon check: nothing to do (no morning post today, or already checked)")
        return 0
    log(f"afternoon gold check for {', '.join(pages)} - morning 22K ₹{am['g22']}, silver ₹{am.get('silver')}{' (DRY RUN)' if DRY else ''}")
    tokens = {}
    if not DRY:
        for pg in pages:
            try:
                tokens[pg] = bridge_get("token", page=pg)["token"]
            except Exception as e:
                log(f"{pg}: no Instagram token - skipped ({str(e)[:120]})")
        pages = [pg for pg in pages if pg in tokens]
    start = clock(PM_START, day)
    if not FORCE_DATE and datetime.now(IST) < start:
        wait = (start - datetime.now(IST)).total_seconds()
        log(f"waiting {int(wait)} s until {PM_START} (MJDTA fixes the afternoon rate at 3:30 PM)")
        time.sleep(max(0, wait))
    while True:
        got = sources.collect(day, log)
        gold, silver = got["gold"], got["silver"]
        if pm_changed(am, gold, silver):
            break
        if FORCE_DATE or datetime.now(IST) >= clock(PM_UNTIL, day):
            log(f"no afternoon change by {PM_UNTIL} - nothing posted")
            if not DRY:
                for pg in pages:
                    pm_path(pg).write_text(json.dumps({"date": day.isoformat(), "changed": False}), encoding="utf-8")
            return 0
        log("afternoon rate not changed (yet) - trying again in 5 minutes")
        time.sleep(300)
    r = pm_rates(hist, day, am, gold, silver)
    log(f"AFTERNOON CHANGE: 22K ₹{am['g22']} -> ₹{r['g22']}" + (f", silver ₹{am.get('silver')} -> ₹{r.get('silver')}" if r.get("silver") else ""))
    if not DRY:      # tomorrow compares with today's last rate; the morning rate is kept as *_am
        row.setdefault("g22_am", am["g22"]); row.setdefault("g24_am", am["g24"])
        if am.get("silver"):
            row.setdefault("silver_am", am["silver"])
        row.update({"g22": r["g22"], "g24": r["g24"]})
        if r.get("silver"):
            row["silver"] = r["silver"]
        HISTORY.write_text(json.dumps(hist, ensure_ascii=False, indent=1), encoding="utf-8")
    for pg in pages:
        p = page_cfg(pg, tokens.get(pg))
        out = ROOT / "out" / "goldrate" / f"{pg}_pm"
        cap = pm_caption(p, day, r)
        if not CAROUSEL:      # owner 19 Nov: reels only - the afternoon change is a reel too
            out.mkdir(parents=True, exist_ok=True)
            (out / "caption.txt").write_text(cap, encoding="utf-8")
            got = post_reel(pg, p, r, [], cap, out, None if DRY else tokens[pg], day, pm=True)
            if got:
                pm_path(pg).write_text(json.dumps({"date": day.isoformat(), "changed": True, "media_id": got[0], "permalink": got[1],
                                                   "kind": "reel", "posted_at": datetime.now(IST).isoformat()}, ensure_ascii=False),
                                       encoding="utf-8")
            continue
        jpgs = render.render(p, r, out, log)
        (out / "caption.txt").write_text(cap, encoding="utf-8")
        log(f"{pg} caption:\n{cap}")
        if DRY:
            log(f"DRY RUN: {pg} afternoon slides in {out} - not posted")
            continue
        try:
            urls = [upload(j) for j in jpgs]
            mid, link = publish(tokens[pg], urls, cap)
            log(f"{pg}: AFTERNOON UPDATE POSTED {link}")
            pm_path(pg).write_text(json.dumps({"date": day.isoformat(), "changed": True, "media_id": mid, "permalink": link,
                                               "posted_at": datetime.now(IST).isoformat()}, ensure_ascii=False), encoding="utf-8")
            try:
                sys.path.insert(0, str(ROOT / "poster"))
                import facebook
                facebook.share(pg, f"goldrate-pm-{day.isoformat()}", "photos", urls, cap, p["tag"], always=True, story=False)
            except Exception as e:
                log("Facebook step skipped:", str(e)[:150])
        except Exception as e:
            log(f"{pg}: NOT POSTED - {str(e)[:300]}")
            continue
        post_reel(pg, p, r, jpgs, cap, out, tokens[pg], day)      # owner 19 Nov: the reel, after (and apart from) the carousel
    return 0


def ig_paused_page(pg):
    """owner 21 Nov: the posting job paused this page after an Instagram block / limit (poster/prebuilt/_ig_paused_<page>.json)"""
    import json as _json
    from datetime import datetime as _dt, timezone as _tz
    try:
        d = _json.loads((ROOT / "poster" / "prebuilt" / f"_ig_paused_{pg}.json").read_text(encoding="utf-8"))
        return _dt.fromisoformat(d["until"]) > _dt.now(_tz.utc)
    except Exception:
        return False


def main():
    pages = [p for p in os.environ.get("GOLD_PAGES", "namakkal rasipuram").split() if p in PAGES]
    held = [pg for pg in pages if ig_paused_page(pg)]
    if held and not DRY:      # owner 21 Nov: a paused page is not tried (that makes the block / limit longer)
        log(f"Instagram posting is paused on {', '.join(held)} (a block / limit) - no gold post there now; it is started again after the pause")
        pages = [pg for pg in pages if pg not in held]
    if MODE == "pm":
        return pm_main(pages, date.fromisoformat(FORCE_DATE) if FORCE_DATE else datetime.now(IST).date())
    now = datetime.now(IST)
    day = date.fromisoformat(FORCE_DATE) if FORCE_DATE else now.date()
    log(f"gold & silver rate for {', '.join(pages)} - {date_ta(day)}{' (DRY RUN)' if DRY else ''}")
    tokens = {}
    if not DRY:
        for pg in pages:
            try:
                tokens[pg] = bridge_get("token", page=pg)["token"]
            except Exception as e:
                log(f"{pg}: no Instagram token - skipped ({str(e)[:120]})")
        pages = [pg for pg in pages if pg in tokens]
    todo = [pg for pg in pages if not (DRY is False and already_posted(pg, day, tokens.get(pg)))]
    for pg in set(pages) - set(todo):
        log(f"{pg}: already posted today - {already_posted(pg, day, tokens.get(pg))}")
    reel_catchup([pg for pg in pages if pg not in todo], day, tokens)
    if not todo:
        return 0
    start = clock(START_AT, day)
    if not FORCE_DATE and datetime.now(IST) < start:
        wait = (start - datetime.now(IST)).total_seconds()
        log(f"waiting {int(wait)} s until {START_AT} (the rate is fixed at 9:30 AM)")
        time.sleep(max(0, wait))
    while True:
        log("reading today's rate")
        got = sources.collect(day, log)
        gold, silver = got["gold"], got["silver"]
        t = datetime.now(IST)
        if gold and (silver or FORCE_DATE or t >= clock(SILVER_WAIT_UNTIL, day)):
            break
        if FORCE_DATE or t >= clock(GIVE_UP_AT, day):
            if gold:
                break
            raise SystemExit(f"today's gold rate was not confirmed by 2 pages by {GIVE_UP_AT} - nothing posted")
        log(f"not confirmed yet (gold {'ok' if gold else 'waiting'}, silver {'ok' if silver else 'waiting'}) - trying again in 5 minutes")
        time.sleep(300)
    log(f"CONFIRMED gold 22K ₹{gold['g22']} 24K ₹{gold['g24']} ({', '.join(gold['sources'])})"
        + (f"; silver ₹{silver['silver']}/g ({', '.join(silver['sources'])})" if silver else "; silver not confirmed - gold slide only"))
    hist = load_history()
    r = rates_for_slides(hist, day, gold, silver)
    if not DRY:
        save_today(hist, day, gold, silver)
    for pg in todo:
        p = page_cfg(pg, tokens.get(pg))
        out = ROOT / "out" / "goldrate" / pg
        cap = caption(p, day, r)
        if not CAROUSEL:      # owner 19 Nov: gold & silver rate - the REEL is the day's post (no carousel)
            out.mkdir(parents=True, exist_ok=True)
            (out / "caption.txt").write_text(cap, encoding="utf-8")
            log(f"{pg} caption:\n{cap}")
            if DRY:
                post_reel(pg, p, r, [], cap, out, None, day)
                continue
            if already_posted(pg, day, tokens[pg]):
                log(f"{pg}: posted meanwhile - stop")
                continue
            got = post_reel(pg, p, r, [], cap, out, tokens[pg], day)
            if got:      # the day's post is saved: the watchdog and the 3:30 PM check read this file
                state_path(pg).write_text(json.dumps({"date": day.isoformat(), "media_id": got[0], "permalink": got[1], "kind": "reel",
                                                      "posted_at": datetime.now(IST).isoformat()}, ensure_ascii=False), encoding="utf-8")
            continue
        jpgs = render.render(p, r, out, log)
        (out / "caption.txt").write_text(cap, encoding="utf-8")
        log(f"{pg} caption:\n{cap}")
        if DRY:
            log(f"DRY RUN: {pg} slides in {out} - not posted")
            post_reel(pg, p, r, jpgs, cap, out, None, day)
            continue
        try:
            if already_posted(pg, day, tokens[pg]):
                log(f"{pg}: posted meanwhile - stop")
                continue
            urls = [upload(j) for j in jpgs]
            mid, link = publish(tokens[pg], urls, cap)
            log(f"{pg}: POSTED {link}")
            state_path(pg).write_text(json.dumps({"date": day.isoformat(), "media_id": mid, "permalink": link,
                                                  "posted_at": datetime.now(IST).isoformat()}, ensure_ascii=False), encoding="utf-8")
            try:      # same carousel to the page's Facebook page when it is set up (never touches the Instagram post)
                sys.path.insert(0, str(ROOT / "poster"))
                import facebook
                facebook.share(pg, f"goldrate-{day.isoformat()}", "photos", urls, cap, p["tag"], always=True, story=False)
            except Exception as e:
                log("Facebook step skipped:", str(e)[:150])
        except Exception as e:
            log(f"{pg}: NOT POSTED - {str(e)[:300]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
