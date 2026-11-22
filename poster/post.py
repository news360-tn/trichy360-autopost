"""Trichy 360 Instagram poster (runs in GitHub Actions) - photo reel flow.

Flow: the research task queues a story (text + ONE image prompt) -> the picture is made automatically (free models first) ->
the Apps Script bridge saves the image and sets the story to "Queued" -> this job builds the reel and posts it to திருச்சி 360.
One page only (no second page, no collaborator), reels only (no carousel).

  python poster/post.py check   # prints ready=<n> (for the workflow); decides whether the heavy job must run
  python poster/post.py run     # posts the top ready story (reel); one story per run

Environment (GitHub Secrets): BRIDGE_URL, BRIDGE_KEY, CLOUDINARY_CLOUD, CLOUDINARY_PRESET.  DRY_RUN=1 -> render + upload, no publishing.
"""
import base64, json, os, re, subprocess, sys, time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
import localmedia      # owner 21 Nov: reels / stories sent as FILES (no Cloudinary) wherever Meta allows it
import igdirect       # owner 21 Nov: the Instagram file upload (Instagram API with Facebook login)
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parent.parent
KIT = ROOT / "kit"
REEL = ROOT / "reel"
OUT = ROOT / "out"
IST = timezone(timedelta(hours=5, minutes=30))
CONFIG = json.loads((Path(__file__).resolve().parent / "config.json").read_text())

BRIDGE_URL = os.environ.get("BRIDGE_URL", "")
BRIDGE_KEY = os.environ.get("BRIDGE_KEY", "")
CLOUD = os.environ.get("CLOUDINARY_CLOUD", "")
PRESET = os.environ.get("CLOUDINARY_PRESET", "")
START = time.time()
DRY = os.environ.get("DRY_RUN", "") in ("1", "true", "yes")
PREBUILD = os.environ.get("PREBUILD", "") in ("1", "true", "yes")   # build + upload only; the posting run then publishes at once
CACHE = ROOT / "poster" / "prebuilt"
IG_HOST = "https://graph.instagram.com"
IG_VER = os.environ.get("IG_API_VERSION", "")

# ---- the page (Trichy 360; placeholders until the owner decides - change them HERE only)
PAGE = "trichy"
PAGES = ("trichy",)      # the only page (no collab)
ALL_ROWS = []      # every row of the queue (set in main) - used to spot the same news posted before
LOGO = KIT / "logo_trichy.png"
TAG = "#Trichy360"
PAGE_EN = "Trichy 360"      # post_to value in the Sheet
FOLLOW_LINE = "மேலும் செய்திகளுக்கு திருச்சி த்ரீ சிக்ஸ்டி பக்கத்தை பின்தொடருங்கள்."
SAVE_LINE = "திருச்சி செய்திகளைத் தவறவிடாமல் இருக்க Save செய்து Follow செய்யுங்கள் 📌"
DISTRICTS = ('trichy', 'tiruchirappalli', 'trichirappalli', 'tiruchi', 'tiruchy')      # allnews.url_district values that are our district
IMPORTANCE = {"High": 0, "Medium": 1, "Low": 2}
MAX_AGE_H = 48
AI_LINE = "📌 படங்கள் செய்தியை விளக்க AI மூலம் உருவாக்கப்பட்ட பிரதிநிதித்துவப் படங்கள்."

# news outlets must never appear on a post, a slide or in a reel
OUTLETS = ["தினமலர்", "தினத்தந்தி", "தினமணி", "மாலைமலர்", "தினகரன்", "இந்து தமிழ்", "தி இந்து", "புதிய தலைமுறை", "நியூஸ்18",
           "நியூஸ் 18", "பாலிமர்", "சன் நியூஸ்", "நியூஸ்7", "நியூஸ் 7", "கலைஞர் செய்திகள்", "விகடன்", "ஒன்இந்தியா", "வே2நியூஸ்",
           "டாப் தமிழ்", "தமிழ் மணி", "டைம்ஸ் ஆஃப் இந்தியா", "டி.டி. நெக்ஸ்ட்",
           "dinamalar", "dinamani", "dinathanthi", "daily thanthi", "maalaimalar", "dinakaran", "the hindu", "hindu tamil", "times of india",
           "toi", "dt next", "indian express", "news18", "polimer", "sun news", "news7", "vikatan", "oneindia", "way2news", "puthiya thalaimurai",
           "kalaignar", "toptamilnews", "tamil mani", "ஆதாரம்", "source:"]


def log(*a):
    print(datetime.now(IST).strftime("%H:%M:%S"), *a, flush=True)


# ---------------------------------------------------------------- bridge (Apps Script)
def bridge_get(action, **params):
    # 4 Nov: Apps Script sometimes answers after more than 120 s and the whole post job failed before posting.
    # A read is safe to repeat, so slow / failed answers are retried before giving up.
    for k in range(3):
        try:
            r = requests.get(BRIDGE_URL, params={"action": action, "key": BRIDGE_KEY, **params}, timeout=120)
            if r.status_code < 500:
                break
            err = f"HTTP {r.status_code}"
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            if k == 2:
                raise
            err = str(e)[:150]
        log(f"bridge get '{action}' failed (try {k + 1}):", err)
        time.sleep(20 * (k + 1))
    r.raise_for_status()
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(f"bridge {action}: {data.get('error')}")
    return data


def bridge_post(action, payload):
    if action == "posted":      # a published post that is not recorded would be posted again: retry
        for k in range(4):
            try:
                return _bridge_post(action, payload)
            except Exception as e:
                if EMAIL_QUOTA in str(e):      # 14 Nov: the sheet row is already saved - only the owner's email (the bridge's last step) hit Gmail's daily limit
                    log("bridge 'posted' saved; the owner email was skipped (Gmail daily email limit reached)")
                    return {"ok": True, "email_skipped": True}
                log(f"bridge 'posted' failed (try {k + 1}):", str(e)[:150])
                time.sleep(15 * (k + 1))
    return _bridge_post(action, payload)


EMAIL_QUOTA = "Service invoked too many times for one day: email"


def _bridge_post(action, payload):
    r = requests.post(BRIDGE_URL, params={"key": BRIDGE_KEY},
                      data=json.dumps({"action": action, **payload}, ensure_ascii=False).encode("utf-8"),
                      headers={"Content-Type": "application/json"}, timeout=120)
    r.raise_for_status()
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(f"bridge {action}: {data.get('error')}")
    return data


# ---------------------------------------------------------------- selection
# ---- prime time (owner 27 Oct): non-urgent reels go out in the high-view hours; urgent news never waits; nothing is dropped
URGENT = re.compile(r"மின்\s*தடை|மின்தடை|power\s*(cut|shut)|விபத்து|மோதி|உயிரிழ|பலி|accident|died|கனமழை|மழை\s*எச்சரிக்கை|எச்சரிக்கை|"
                    r"alert|warning|flood|வெள்ள|ஆட்சியர்|கலெக்டர்|collector|அறிவிப்பு|announce|முகாம்|camp|வேலைவாய்ப்பு|ஆட்சேர்ப்பு|"
                    r"recruit|job|விண்ணப்ப|apply|கடைசி\s*நாள்|last\s*date|deadline|இன்று|நாளை|today|tomorrow|தேர்வு|exam|result|"
                    r"தீ\s*விபத்து|fire|காணவில்லை|missing|சாலை\s*மறியல்|traffic\s*diversion|போக்குவரத்து\s*மாற்றம்", re.I)


POWER_CUT = re.compile(r"மின்\s*தடை|மின்தடை|மின்\s*நிறுத்தம்|power\s*(cut|shut)", re.I)


def prime_urgent(row):
    """time-sensitive news (power cut, accident, rain warning, Collector / Govt notice, jobs, exam, today / tomorrow) never waits"""
    return bool(URGENT.search(f"{row.get('headline_ta', '')} {row.get('headline_en', '')} {row.get('category', '')}"))


def in_prime_time(now=None):
    now = now or datetime.now(IST)
    hm = now.strftime("%H:%M")
    return any(a <= hm < b for a, b in (CONFIG.get("prime_time") or {}).get("windows", []))


def quiet_now(now=None):
    """owner 21 Nov: nothing is posted on Instagram from 00:00 to 05:00 IST (config prime_time.quiet_ist) - not even power cuts"""
    q = (CONFIG.get("prime_time") or {}).get("quiet_ist") or []
    if len(q) != 2:
        return ""
    hm = (now or datetime.now(IST)).strftime("%H:%M")
    return f"night: nothing is posted {q[0]}-{q[1]} IST (owner 21 Nov)" if q[0] <= hm < q[1] else ""


def prime_wait(row, now=None):
    """'' = post now. Otherwise why this reel waits. owner 13 Nov: news is collected every 4 hours; a story waits for the first posting
    START time (config prime_time.starts) after it was filed, then posts with all the other waiting news - there is NO end time and
    nothing is skipped. Only power cuts post at once; a story that has waited max_wait_hours goes out whatever the hour."""
    night = quiet_now(now)
    if night:      # owner 21 Nov: before every other rule
        return night
    pt = CONFIG.get("prime_time") or {}
    if not pt.get("enabled"):
        return ""
    if pt.get("immediate") == "power_cut":      # owner 13 Nov: ONLY power cuts post at once (found by category or headline)
        now_ok = is_shutdown(row) or bool(POWER_CUT.search(f"{row.get('headline_ta', '')} {row.get('headline_en', '')}"))
    else:
        now_ok = prime_urgent(row) or is_urgent(row)
    if now_ok:
        return ""
    waited = age_hours(row)
    if waited is not None and waited >= float(pt.get("max_wait_hours", 12)):
        return ""
    now = now or datetime.now(IST)
    if pt.get("starts"):
        start = posting_start(row, pt["starts"], float(pt.get("grace_min", 60)))
        return "" if start is None or now >= start else f"waits for posting start ({start:%H:%M} IST)"
    if in_prime_time(now):
        return ""
    nxt = next((a for a, b in sorted(pt.get("windows", [])) if a > now.strftime("%H:%M")), (pt.get("windows") or [["09:00"]])[0][0])
    return f"waits for prime time ({nxt} IST)"


def posting_start(row, starts, grace_min=60):
    """the posting start time of a story: the first start (e.g. 08:00 / 12:00 / 18:00 IST) at or after it was filed minus grace_min
    (a batch whose writing runs past its start still belongs to that start). None = filed time unknown (posts at once)."""
    f = filed_at(row)
    if f is None:
        return None
    ref = f - timedelta(minutes=grace_min)
    for day in (0, 1):
        for st in sorted(starts):
            h, mi = (int(x) for x in st.split(":"))
            cand = datetime(ref.year, ref.month, ref.day, h, mi, tzinfo=ref.tzinfo) + timedelta(days=day)
            if cand >= ref:
                return cand
    return None


def age_hours(row):
    for key in ("researched", "published"):
        v = (row.get(key) or "").lstrip("'").replace(" IST", "").strip()
        for fmt in ("%d %b %Y, %H:%M", "%d %b %Y %H:%M", "%d %b %Y"):
            try:
                t = datetime.strptime(v, fmt).replace(tzinfo=IST)
                return (datetime.now(IST) - t).total_seconds() / 3600
            except ValueError:
                pass
    return 0.0


def is_shutdown(row):
    import freshness      # owner 30 Oct: a power cut is found by its headline too, not only by the category the writer chose
    return ("மின் தடை" in (row.get("category") or "") or "shutdown" in (row.get("category") or "").lower()
            or freshness.is_power_cut(row.get("headline_ta"), row.get("headline_en")))


LABEL = {"trichy": "திருச்சி 360"}      # must match PAGE_LABEL in apps_script/Code.gs (reel_link lines are "<label>: <link>")


def pages_of(row):
    """the ONE page that posts this story: always Trichy 360 (post_to "Trichy 360"; there is no second page)"""
    return ["trichy"]


def collab_page(row, page):
    """no collaborator page for Trichy 360 (collab is always off)"""
    return ""


def page_done(row, page):
    car_ok = bool(row.get(page + "_link")) or not spec_has_carousel(row)
    reel_ok = LABEL[page] in (row.get("reel_link") or "")
    return car_ok and reel_ok


def spec_has_carousel(row):
    """stories written in the reel-first plan carry "carousel": false in slides_spec when only a reel is wanted (older stories: both)"""
    return False      # Trichy 360: reels only, never a carousel (config.json "carousel": false)


_SKIPPED = set()


_EVENT_DF = None
_SCRIPTS = None


def script_of(o):
    """the reel script of an earlier story: from the row, else from its saved prebuilt file (the bridge's 'recent' rows carry
    no script)"""
    global _SCRIPTS
    if o.get("reel_script"):
        return o["reel_script"]
    if _SCRIPTS is None:
        _SCRIPTS = {}
        for f in CACHE.glob("RN-*.json"):
            try:
                sid = f.stem.split("_")[0]
                s = json.loads(f.read_text(encoding="utf-8")).get("reel_script") or ""
                if s:      # 30 Oct: RN-x.json has no script - it must not hide the one in RN-x_trichy_text.json (21 of 46 stories were missed)
                    _SCRIPTS.setdefault(sid, s)
            except Exception:
                pass
    return _SCRIPTS.get(o.get("story_id") or "", "")


_PICKED = None


def owner_picked(row):
    """owner 1 Nov (Trichy pick flow): a news the owner ticked (or the automatic top 12) is posted - no freshness / duplicate /
    place check may hold it back (31 Oct articles picked at 9 AM on 1 Nov were held as 'stale: not today')"""
    global _PICKED
    if _PICKED is None:
        _PICKED = set()
        try:
            st = json.loads((ROOT / "research_free" / "archive" / "pick_state.json").read_text(encoding="utf-8"))
            for r in (st.get("rounds") or {}).values():
                _PICKED |= set(r.get("written") or []) | set((r.get("decided") or {}).get("ids") or [])
        except Exception:
            pass
        try:      # owner 1 Nov: power-shutdown notices are posted at once, without a tick (research_free/powercut.py)
            _PICKED |= set(json.loads((ROOT / "research_free" / "archive" / "powercut_state.json").read_text(encoding="utf-8")).get("done", {}))
        except Exception:
            pass
    u = str(row.get("source") or "").strip()
    if not u or not _PICKED:
        return False
    import hashlib
    forms = {u, u.replace("://www.dinamalar", "://l-www.dinamalar"), u.replace("://l-www.dinamalar", "://www.dinamalar"),
             u.replace("/amp/story/", "/"), u.rstrip("/")}
    return any("C" + hashlib.sha1(x.encode()).hexdigest()[:7] in _PICKED for x in forms)


def _skip_reason_base(row):
    """'' = fine to post. Otherwise why this story must not go out: its announced date has passed (power cut, job fair, 'today' news ...),
    or the same news was already posted under another story id."""
    import freshness
    if not is_ready_reel(row):      # owner 29 Oct: an issue found once never goes out again (research_free/known_issues.py)
        sys.path.insert(0, str(ROOT / "research_free"))
        import known_issues, verify
        fixed = known_issues.repair(dict(row, **{k: verify.clean_text(row.get(k) or "") for k in ("headline_ta", "reel_script", "caption")}))      # what the post will really say (repairable issues fixed)
        ki = known_issues.problems(fixed)
        if ki:
            return f"known issue {ki[0][0]}: {ki[0][1]}"
    if link_hold(row):      # owner 21 Nov: every news only with its source link (an owner pick too - add the link to post it)
        return link_hold(row)
    if owner_picked(row):
        return ""
    f = filed_at(row)
    same_day = bool(f and f.date() == datetime.now(IST).date())      # filed today: it goes out today, whatever the clock says
    nd = freshness.news_date(row.get("published"), row.get("source"), f)
    manual = "manual" in " ".join(str(row.get(k) or "") for k in ("notes", "batch", "review", "source")).lower()
    max_age = int(os.environ.get("POST_MAX_AGE_DAYS", "1") or 1)      # owner 29 Oct 18:29: Trichy 0 = only news published TODAY
    if not manual and max_age == 0 and not nd:
        return "stale: no publish date known - today's news only"
    if (nd and not manual and (datetime.now(IST).date() - nd).days > max_age      # owner: only today's (or yesterday's) news is posted
            and not freshness.power_cut_ahead(f"{row.get('headline_ta') or ''} {row.get('headline_en') or ''}", nd.isoformat())):      # owner 30 Oct: a power cut by its CUT day
        return f"stale: published {nd:%d %b}, " + ("not today" if max_age == 0 else "older than yesterday")      # (27 Oct: a 25 Oct story went out two days late)
    why = freshness.power_cut_over(row.get("headline_ta") or "", row.get("headline_en") or "", row.get("published") or (nd.isoformat() if nd else ""))
    if why:
        return "stale: " + why
    if not is_ready_reel(row):      # owner 29 Oct (RN-189): never post a story that only says the article has no details
        try:
            spec_ = json.loads(row.get("slides_spec") or "{}")
        except Exception:
            spec_ = {}
        why = freshness.no_news(" ".join([row.get("headline_ta") or "", str(spec_.get("hl1", "")), str(spec_.get("hl2", ""))]),
                                row.get("reel_script") or "", row.get("caption") or "")
        if why:
            return why
        why = freshness.old_event((row.get("headline_ta") or "") + " " + (row.get("reel_script") or ""))
        if why:      # owner 29 Oct (RN-29): an old event re-told in a new article
            return why
        if row.get("reel_script"):      # owner 29 Oct (RN-13/RN-24): the same event from another outlet, in other words
            global _EVENT_DF
            if _EVENT_DF is None:
                _EVENT_DF = freshness.event_df([script_of(o) for o in ALL_ROWS])
            mine = freshness.pub_date(row.get("researched"))
            for o in ALL_ROWS:
                went = o.get("rasipuram_link") or o.get("namakkal_link") or o.get("reel_link") or str(o.get("post_status") or "").lower().startswith(("posted", "partly"))
                if o.get("story_id") == row.get("story_id") or not went or not script_of(o):
                    continue
                od = freshness.pub_date(o.get("researched"))
                if mine and od and abs((mine - od).days) > 1:
                    continue
                if freshness.same_event(script_of(o), row["reel_script"], _EVENT_DF) and not freshness.follow_up(o, row):
                    return f"duplicate of {o.get('story_id')} (same event, other outlet)"
    why = "" if same_day else freshness.stale_reason(row.get("headline_ta") or "", row.get("headline_en") or "", row.get("category") or "", row.get("published") or "")
    if why:
        return "stale: " + why
    why = not_trichy(row)
    if why:
        return why
    for o in ALL_ROWS:
        went_out = o.get("trichy_link") or o.get("reel_link") or str(o.get("post_status") or "").lower().startswith(("posted", "partly"))
        if o.get("story_id") == row.get("story_id") or not went_out:
            continue
        if (freshness.similar(o.get("headline_ta") or "", row.get("headline_ta") or "", 0.62, o.get("researched"))
                or freshness.similar((o.get("headline_en") or "").lower(), (row.get("headline_en") or "").lower(), 0.65, o.get("researched"))
                or freshness.same_power_cut(o.get("headline_ta"), o.get("published") or o.get("researched"),      # owner 30 Oct: same cut day + same place
                                            row.get("headline_ta"), row.get("published") or row.get("researched"))):
            if freshness.follow_up(o, row):
                continue
            return f"duplicate of {o.get('story_id')}"
    return ""


def not_trichy(row):
    """last gate (ONLY Trichy-district news): a story whose source link is filed under another district, or whose headline
    and caption name no Trichy-district place, is not posted. Stories e-mailed by the owner are not checked."""
    try:
        sys.path.insert(0, str(ROOT / "research_free"))
        import allnews
    except Exception:
        return ""
    src, head = (row.get("source") or "").strip(), row.get("headline_ta") or ""
    if not src.startswith("http"):
        return ""
    if getattr(allnews, "is_listing", lambda u: False)(src):      # 29 Oct RN-194: a topic page, not one article
        return "not one news article (the source is a topic / listing page)"
    cap = (row.get("caption") or "")[:600]
    if allnews.other_district(head):
        return "not Trichy district news (the headline names another district)"
    loc = row.get("location") or ""
    paper_page = (allnews.url_district(src) or "").lower() in DISTRICTS
    if loc and not allnews.has_place(loc) and re.search(r"தமிழ்நாடு|தமிழகம்|மாநில|Tamil Nadu", loc) and (not paper_page or "உள்ளிட்ட" in head):
        return f"not Trichy city news (state-wide: {loc[:40]})"      # 29 Oct RN-8 TNEB promotions, RN-20 prison staffing
    town = allnews.outside_city(head, loc)
    if town:      # owner 29 Oct: Trichy city only for now (CITY_ONLY=0 for the whole district)
        return f"not Trichy city news ({town})"
    if allnews.has_place(head):
        return ""
    d = (allnews.url_district(src) or "").lower()
    if d in DISTRICTS:      # the paper's own Trichy page (same rule as the collector)
        return ""
    if d:
        return f"not Trichy district news (source filed under {d})"
    if not allnews.has_place(cap) and not allnews.has_place(row.get("location") or ""):
        return "not Trichy district news (no Trichy-district place in the headline or caption)"
    return ""


not_namakkal = not_trichy      # old name (same call site as the Namakkal project)


def is_ready_reel(row):
    try:
        return bool(json.loads(row.get("slides_spec") or "{}").get("ready_reel"))
    except Exception:
        return False


def published_before_today(row, now=None):
    """owner 22 Nov: True when the news' own published date (IST) is before YESTERDAY - today's news and yesterday's pending news are
    posted (yesterday's outside the day's 30); older news never. No / unreadable date: False (posted as before)."""
    if re.search(r"மின்\s*தடை|power", str(row.get("category") or ""), re.I):
        return False      # a power-cut notice from yesterday is about today's cut: still posted
    p = str(row.get("published") or "").strip()
    if not re.match(r"\d{4}-\d{2}-\d{2}", p):
        return False
    try:
        t = datetime.fromisoformat(p.replace("Z", "+00:00"))
        d = (t.astimezone(IST) if t.tzinfo else t).date()
    except Exception:
        try:
            d = datetime.strptime(p[:10], "%Y-%m-%d").date()
        except Exception:
            return False
    return d < (now or datetime.now(IST)).astimezone(IST).date() - timedelta(days=1)


def ready(row):
    if (row.get("review") or "").strip().lower() == "hold":
        return False
    if not row.get("images") or not row.get("slides_spec"):
        return False
    pg = pages_of(row)
    if all(page_done(row, p) for p in pg):
        return False
    why = news_hold(row) if is_ready_reel(row) else skip_reason(row)    # owner reels: no news checks, but the fact-check / location hold always applies
    if why:
        if row.get("story_id") not in _SKIPPED:
            _SKIPPED.add(row.get("story_id"))
            log("SKIP", row.get("story_id"), why)
            if why.startswith("held") and age_hours(row) <= 24:      # owner 2 Nov: a run that posts nothing must not look like a plain success
                print(f"::warning title=Held from posting {row.get('story_id')}::{why[:300]}", flush=True)
        return False
    # a story that already went out on one page is only carried over to its other page while it is still fresh (same day);
    # an older one is never posted again later (stale news, e.g. yesterday's power cut)
    if any(page_done(row, p) or row.get(p + "_link") for p in pg) and age_hours(row) > 20:
        return False
    if not is_ready_reel(row) and published_before_today(row):      # owner 22 Nov: news older than yesterday is never posted
        if row.get("story_id") not in _SKIPPED:
            _SKIPPED.add(row.get("story_id"))
            log("SKIP", row.get("story_id"), "published before yesterday - only today's and yesterday's pending news is posted")
        return False
    return True      # a story with its images is never dropped for age or time of day: it posts as soon as its set has started


def _starts():
    """the three daily posting start times (IST minutes after midnight) from config.json post_windows_ist ("06:30-09:30" -> 06:30)"""
    try:
        cfg = json.loads((Path(__file__).parent / "config.json").read_text())
    except Exception:
        cfg = {}
    out = []
    for w in cfg.get("post_windows_ist") or []:
        a = w.split("-")[0]
        out.append(int(a[:2]) * 60 + int(a[3:5]))
    return sorted(out)


def filed_at(row):
    """IST datetime the story was filed ('22 Oct 2026, 10:26' in the researched column), or None"""
    import re as _re
    from datetime import datetime, timedelta, timezone
    m = _re.search(r"(\d{1,2})\s+([A-Za-z]{3})[a-z]*\s+(\d{4}),?\s+(\d{1,2}):(\d{2})", str(row.get("researched") or ""))
    if not m:
        return None
    mon = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"].index(m.group(2).lower()) + 1
    return datetime(int(m.group(3)), mon, int(m.group(1)), int(m.group(4)), int(m.group(5)), tzinfo=timezone(timedelta(hours=5, minutes=30)))


def set_started(row, now=None):
    """Every story belongs to the posting set (morning / afternoon / evening) it was written for: the first start time that is not
    earlier than 90 min before it was filed. From that start time on it posts as soon as it is ready - a late image reply is posted at
    once, it never waits for (or is pushed into) the next set. Manual runs ignore this."""
    if os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch" or True:     # owner (23 Oct): no fixed posting times - a story posts the moment its images are in
        return True
    from datetime import datetime, timedelta, timezone
    starts = _starts()
    f = filed_at(row)
    if not starts or f is None:
        return True
    now = now or datetime.now(timezone(timedelta(hours=5, minutes=30)))
    # the set of a story = the latest start time that is not later than 2 h after it was filed (a round that runs late still belongs to the set
    # whose start has already passed, so its stories post as soon as their images are in; a round before a start waits for that start)
    hi = f + timedelta(minutes=120)
    best = None
    for day in (-1, 0):
        for st in starts:
            cand = datetime(hi.year, hi.month, hi.day, st // 60, st % 60, tzinfo=hi.tzinfo) + timedelta(days=day)
            if cand <= hi and (best is None or cand > best):
                best = cand
    return True if best is None else now >= best


def is_urgent(row):
    return is_shutdown(row) or (row.get("importance") or "").strip() == "High"


def pick_all(rows):
    """every ready story whose set has started (urgent ones always), urgent first, then the rest oldest first"""
    c = [r for r in rows if ready(r) and (set_started(r) or is_urgent(r))]
    c.sort(key=lambda r: (IMPORTANCE.get((r.get("importance") or "").strip(), 1), -age_hours(r)))
    return c


def pick(rows):
    c = pick_all(rows)
    return c[0] if c else None


# ---------------------------------------------------------------- checks before posting
TAMIL_MONTHS = ["ஜனவரி", "பிப்ரவரி", "மார்ச்", "ஏப்ரல்", "மே", "ஜூன்", "ஜூலை", "ஆகஸ்ட்", "செப்டம்பர்", "அக்டோபர்", "நவம்பர்", "டிசம்பர்"]


def tamil_date_today():
    d = datetime.now(IST)
    return f"{d.day} {TAMIL_MONTHS[d.month - 1]} {d.year}"


def all_text(row, spec):
    parts = [row.get("caption") or "", row.get("reel_script") or "", spec.get("hl1", ""), spec.get("hl2", ""), spec.get("cat", ""), spec.get("loc", "")]
    for s in spec.get("slides", []):
        parts.append(s.get("title", ""))
        parts += s.get("lines", [])
    return "\n".join(parts)


def clean_caption(row):
    """caption fixes instead of rejects: outlet names and links removed, hashtags capped at 30, length capped at 2150 characters"""
    cap = row.get("caption") or ""
    orig = cap
    cap = re.sub(r"https?://\S+", "", cap)
    cap = cap.replace("\ufffd", "")
    for o in OUTLETS:
        cap = cap.replace(o, "")
    lines = [l for l in cap.split("\n")]
    tags = [w for w in cap.split() if w.startswith("#")]
    if len(tags) > 30:
        extra = set(tags[30:])
        cap = "\n".join(" ".join(w for w in l.split() if w not in extra) for l in lines)
    import verify      # 29 Oct: this name was not imported here - every post job crashed (NameError) from 13:00 UTC
    cap = verify.clean_text(cap)[:2150]      # owner 29 Oct: letters of other scripts fixed in the caption too
    if not cap.strip():
        cap = (row.get("headline_ta") or "") + "\n" + (row.get("location") or "")
    row["caption"] = cap.strip()
    return cap != orig


def check_text(row, spec):
    cap = row.get("caption") or ""
    problems = []
    if not cap.strip():
        problems.append("empty caption")
    if len(cap) > 2150:
        problems.append(f"caption too long ({len(cap)})")
    if cap.count("#") > 30:
        problems.append("more than 30 hashtags")
    if re.search(r"https?://", cap):
        problems.append("caption contains a link")
    if "�" in cap:
        problems.append("broken characters in caption")
    low = all_text(row, spec).lower()
    hits = [o for o in OUTLETS if o.lower() in low]
    if hits:
        problems.append("a news source name appears in the post text: " + ", ".join(hits[:3]))
    if spec.get("v") != 3 or not spec.get("slides"):
        problems.append("slides spec is not the photo format (v3)")
    if not (row.get("reel_script") or "").strip():
        problems.append("empty reel script")
    return problems


def _digits_in_spec(spec):
    """numbers/times/dates shown as digits (10 மணி, 11ஆம் தேதி), never as Tamil words"""
    sys.path.insert(0, str(REEL))
    from digits import to_digits
    for k in ("hl1", "hl2", "cat", "loc"):
        if spec.get(k):
            spec[k] = to_digits(spec[k])
    for sl in spec.get("slides", []):
        sl["title"] = to_digits(sl.get("title", ""))
        sl["lines"] = [to_digits(x) for x in sl.get("lines", [])]


def hashtags_for(row, cap, reach, prof):
    """owner 2 Nov (hashtag review): the writer's own tags gave #AndagalurGate (5 views), #Trichy on a Namakkal reel, Namakkal page tags
    on Rasipuram reels and two spellings of one town. Now every tag comes from config: page, area, the town the story names
    (the earliest one in the headline; a village maps to its town tag), the local topic (rain / power cut) else the page's news tag,
    and the Tamil place tag. Always exactly 5."""
    sys.path.insert(0, str(ROOT / "research_free"))
    import learned
    head = str(row.get("headline_ta") or "")
    where = head + " " + str(row.get("location") or "") + " " + (cap.split("\n")[0] if cap else "")
    hits = []
    for k, t in (reach.get("place_tags") or {}).items():
        i = where.find(k)
        if i >= 0 and t.lower() not in (prof["page"].lower(), prof["area"].lower()):
            hits.append((i, -len(k), t))
    place = min(hits)[2] if hits else ""
    topic = (prof.get("topic") or {}).get(learned.topic(head), "") or prof["news"]
    out, seen = [], set()
    for t in (prof["page"], prof["area"], place or prof["fallback"], topic, prof["tamil"], prof["news"], prof["fallback"]):
        if t and t.lower() not in seen and len(out) < 5:
            seen.add(t.lower()); out.append(t)
    return out


# owner 11 Nov: viewers called some news "fake" - every news now names its source (paper + publish date) on the reel and in the captions
SOURCE_NAMES = [("dinamalar.com", "தினமலர்"), ("dinamani.com", "தினமணி"), ("dailythanthi.com", "தினத்தந்தி"), ("maalaimalar.com", "மாலைமலர்"),
                ("dinakaran.com", "தினகரன்"), ("hindutamil.in", "இந்து தமிழ்"), ("puthiyathalaimurai.com", "புதிய தலைமுறை"),
                ("news18.com", "நியூஸ்18 தமிழ்"), ("vikatan.com", "விகடன்"), ("oneindia.com", "ஒன்இந்தியா"), ("polimernews.com", "பாலிமர் நியூஸ்"),
                ("sunnews.in", "சன் நியூஸ்"), ("news7tamil.live", "நியூஸ்7 தமிழ்"), ("kalaignarseithigal.com", "கலைஞர் செய்திகள்"),
                ("thehindu.com", "The Hindu"), ("timesofindia", "Times of India"), ("dtnext.in", "DT Next"),
                ("newindianexpress.com", "The New Indian Express"),
                ("abplive.com", "ABP நாடு"), ("samayam.com", "சமயம் தமிழ்"),      # owner 13 Nov: the state-wide power-cut lists
                ("tnebltd", "மின்வாரியம்"), ("tangedco", "மின்வாரியம்"), ("tnpdcl", "மின்வாரியம்")]


def source_names(row):
    """the papers this news came from, in Tamil, main source first (unknown sites are left out - never a guessed name)"""
    out = []
    for u in [str(row.get("source") or "")] + re.split(r"[\s,]+", str(row.get("other_sources") or row.get("other_source") or "")):
        n = next((t for d, t in SOURCE_NAMES if d in u.lower()), "")
        if n and n not in out:
            out.append(n)
    return out[:2]


def news_day(row):
    """the news date in Tamil ("18 நவம்பர் 2026") from the paper's publish time, in India time - '' when unknown (never guessed).
    owner 19 Nov: a publish time stamped in UTC ("...Z") showed the day before for news published between 00:00 and 05:30 IST"""
    try:
        d = datetime.fromisoformat(str(row.get("published") or "").replace("Z", "+00:00"))
    except Exception:
        return ""
    if d.tzinfo:
        d = d.astimezone(IST)
    return f"{d.day} {TAMIL_MONTHS[d.month - 1]} {d.year}"


def source_credit(row):
    """(short for the reel header, full line for the end card / caption) - ('', '') when the source site is unknown"""
    names = source_names(row)
    if not names:
        return "", ""
    pre = "மின்வாரிய அறிவிப்பு • " if is_shutdown(row) and "மின்வாரியம்" not in names else ""
    day = news_day(row)
    full = pre + ", ".join(names) + (f" ({day})" if day else "")
    short = {"The New Indian Express": "Indian Express", "Times of India": "TOI", "நியூஸ்18 தமிழ்": "நியூஸ்18", "நியூஸ்7 தமிழ்": "நியூஸ்7"}
    return short.get(names[0], names[0]), full      # the reel header has little room - the end card / caption carry the full name


def posted_quiet():
    """owner 20 Nov: no e-mail per posted reel once the twice-a-day YouTube details e-mail runs (config posted_email "digest" and the
    Promo Hub set up) - Gmail's daily limit was reached with ~200 e-mails a day. Problem e-mails stay instant."""
    return CONFIG.get("posted_email") == "digest" and bool(os.environ.get("PROMO_URL") and os.environ.get("PROMO_KEY"))


def final_caption(row):
    sys.path.insert(0, str(REEL))
    from digits import to_digits
    cap = to_digits((row.get("caption") or "").strip())
    cap = "\n".join(l for l in cap.split("\n") if "கமெண்டி" not in l)      # owner: never ask people to comment
    # Instagram allows at most 5 hashtags: keep #Trichy360 + the first 4 others, as ONE line at the end
    tags, seen = [], set()
    for t in [TAG] + re.findall(r"#[^\s#]+", cap):
        k = t.lower().rstrip(".,!")
        if k not in seen:
            seen.add(k); tags.append(t.rstrip(".,!"))
    tags = [TAG] + [t for t in tags if t != TAG][:4]
    reach = CONFIG.get("reach") or {}
    prof = (reach.get("hashtag_profiles") or {}).get(TAG.lower())
    if prof:      # owner 2 Nov: 5 tags from fixed lists only - page + area + town + local topic + Tamil place
        try:
            tags = hashtags_for(row, cap, reach, prof)
        except Exception as e:
            log("hashtag profile skipped (old pattern used):", e)
            prof = None
    if not prof and reach.get("hashtag_pattern"):      # owner 29 Oct: page + district + town/area + topic + broad tag (no junk tags)
        try:
            sys.path.insert(0, str(ROOT / "research_free"))
            import learned
            where = " ".join(str(row.get(k) or "") for k in ("headline_ta", "location", "headline_en")) + " " + cap.split("\n")[0]
            place = next((t for k, t in (reach.get("place_tags") or {}).items() if k in where), "")
            topic = (reach.get("topic_tags") or {}).get(learned.topic(row.get("headline_ta") or ""), "") or (reach.get("topic_tags") or {}).get("other", "")
            own = [t for t in tags[1:] if re.fullmatch(r"#[A-Za-z][A-Za-z0-9]{2,}", t)]      # the writer's clean English tags as fillers
            want = [TAG, reach.get("district_tag", ""), place, topic, reach.get("broad_tag", "")] + own + [reach.get("extra_tag", "")]
            seen2, tags = set(), []
            for t in want:
                if t and t.lower() not in seen2 and len(tags) < 5:
                    seen2.add(t.lower()); tags.append(t)
        except Exception as e:
            log("hashtag pattern skipped (the writer's tags are used):", e)
    body = "\n".join(re.sub(r"#[^\s#]+", "", l).rstrip() for l in cap.split("\n")).rstrip()
    en = re.sub(r"\s+", " ", str(row.get("headline_en") or "")).strip()
    if (CONFIG.get("reach") or {}).get("english_search_line") and en and not any(
            len(re.findall(r"[A-Za-z]{3,}", l)) >= 2 and not re.search(r"\b(Follow|Share)\b", l) for l in body.split("\n")):
        en = en if len(en) <= 90 else en[:90].rsplit(" ", 1)[0].rstrip(" ,;:-")      # never cut a word in the middle
        line = en + " | " + (CONFIG.get("reach") or {}).get("search_suffix", "news")      # owner 29 Oct: people search in English too
        bl = body.split("\n")
        k = next((i for i, l in enumerate(bl) if l.strip().startswith("📍")), len(bl))
        bl[k:k] = [line]
        body = "\n".join(bl)
    body = re.sub(r"\n{3,}", "\n\n", body)
    cap = body + "\n\n" + " ".join(tags[1:] + [TAG])
    if CONFIG.get("ai_label", True) and "AI" not in cap.split("#")[0][-300:]:
        lines = cap.split("\n")
        idx = max([i for i, l in enumerate(lines) if l.strip().startswith("#")] or [len(lines)])
        if idx < len(lines):
            lines[idx:idx] = [AI_LINE, ""]
        else:
            lines += ["", AI_LINE]
        cap = "\n".join(lines)
    # owner 11 Nov: the source at the very END of the caption - "Source: <paper>: <article link>" (not as a comment)
    _, src_full = source_credit(row)
    src = str(row.get("source") or "").strip()
    if src_full:
        line = f"📰 Source: {src_full}" + (f": {src}" if src.startswith("http") else "")
        if len(cap) + len(line) + 2 > 2200:      # Instagram caption limit: the link is dropped before the caption is cut
            line = f"📰 Source: {src_full}"
        cap = cap.rstrip() + "\n\n" + line
    return fit_caption(cap)


CAPTION_LIMIT = 2190      # Instagram refuses a caption over 2,200 (counted in UTF-16 units: an emoji counts 2)


def ig_len(text):
    return len(text.encode("utf-16-le")) // 2


def fit_caption(cap, limit=CAPTION_LIMIT):
    """20 Nov (Erode RN-163, a power-cut list: 2,356 characters, Instagram refused the reel 3 times): the long text is cut at its last
    whole item / sentence and ends with "…"; the English search line, the hashtags and the source line always stay"""
    if ig_len(cap) <= limit:
        return cap
    lines = cap.split("\n")
    j = next((i for i, l in enumerate(lines) if l.strip().startswith("#")), len(lines))      # the hashtags and everything after stay
    while j > 0 and (not lines[j - 1].strip() or (re.search(r"[A-Za-z]{3,}", lines[j - 1]) and not re.search(r"[\u0B80-\u0BFF]", lines[j - 1]))):
        j -= 1      # the English search line just above the hashtags stays too
    body = "\n".join(lines[:j]).rstrip()
    tail = "\n".join(lines[j:]).strip("\n")
    room = limit - ig_len(tail) - 3
    cut = body
    while cut and ig_len(cut) > room:
        cut = cut[:max(0, len(cut) - max(1, ig_len(cut) - room))]
    k = max(cut.rfind(", "), cut.rfind(". "), cut.rfind("\n"))
    if k > len(cut) * 0.6:
        cut = cut[:k]
    cut = cut.rstrip(" ,.\n") + "…"
    return (cut + "\n\n" + tail) if tail else cut


# ---------------------------------------------------------------- images
def fetch_images(row, work):
    """Trichy 360: ONE picture per reel (the reel makes its scenes from different moves / crops of it)"""
    urls = json.loads(row["images"])[:int((CONFIG.get("free_images") or {}).get("pictures_per_reel", 1))]      # owner 30 Oct: 2 per reel
    work.mkdir(parents=True, exist_ok=True)
    if urls and urls[0] == "NOIMAGE":
        return plain_background(work, 1, row)
    out = []
    for i, u in enumerate(urls, 1):
        try:
            r = requests.get(u, timeout=120)
            r.raise_for_status()
        except requests.HTTPError as e:      # owner 21 Nov (Coimbatore RN-502: a picture on the old, disabled Cloudinary account blocked the page)
            code = e.response.status_code if e.response is not None else 0
            if code in (401, 403, 404, 410):
                log(f"picture {i} cannot be downloaded ({code}) - left out; the reel is made without it")
                continue
            raise
        raw = work / f"raw{i}"
        raw.write_bytes(r.content)
        im = Image.open(raw).convert("RGB")
        if im.width < 2160:  # upscale small AI images so zooming and cropping stay sharp
            f = 2160 / im.width
            im = im.resize((round(im.width * f), round(im.height * f)), Image.LANCZOS)
        # enhance: gentle denoise, local contrast, colour, sharpening (keeps the look natural)
        im = im.filter(ImageFilter.MedianFilter(3)) if im.width * im.height < 6_000_000 else im
        im = ImageOps.autocontrast(im, cutoff=0.4)
        im = ImageEnhance.Contrast(im).enhance(1.06)
        im = ImageEnhance.Color(im).enhance(1.08)
        im = im.filter(ImageFilter.UnsharpMask(radius=2.0, percent=60, threshold=2))
        im = im.filter(ImageFilter.UnsharpMask(radius=0.8, percent=45, threshold=2))
        im.thumbnail((2600, 4000))
        dst = work / f"img{i}.jpg"
        im.save(dst, "JPEG", quality=96, subsampling=0)
        raw.unlink()
        out.append(dst)
    if not out:      # owner 21 Nov: no picture could be downloaded - the designed background, never a blocked page
        log("no picture could be downloaded - the reel is made on the designed background")
        return plain_background(work, 1, row)
    return out


# ---------------------------------------------------------------- rendering
def render_carousel(row, spec, work):
    (work / "spec.json").write_text(json.dumps(spec, ensure_ascii=False))
    raw, final = work / "raw", work / "final"
    cmd = [sys.executable, str(KIT / "render_photo.py"), str(work / "spec.json"), str(work), str(raw)]
    if CONFIG.get("ai_label", True):
        cmd.append("--ai-label")
    subprocess.run(cmd, check=True)
    subprocess.run([sys.executable, str(KIT / "overlay_logo_v2.py"), str(LOGO), str(raw), str(final)], check=True)
    jpgs = []
    for png in sorted(final.glob("*.png"), key=lambda p: int(re.search(r"slide(\d+)", p.name).group(1))):
        jpg = png.with_suffix(".jpg")
        Image.open(png).convert("RGB").save(jpg, "JPEG", quality=92, optimize=True)
        jpgs.append(jpg)
    if not 2 <= len(jpgs) <= 10:
        raise RuntimeError(f"{row['story_id']}: {len(jpgs)} slides (Instagram allows 2-10)")
    return jpgs


_KEY_FACT = re.compile(r"\d|கைது|வழக்கு|உயிரிழ|பலி|காயம்|மீட்|பறிமுதல்|அபராதம்|சிறை|உத்தரவு|நடவடிக்கை|புகார்|உறுதி|விடுவி|மின்\s*தடை|"
                       r"நேரம்|மணி|தேதி|ரூ\.|லட்சம்|கோடி|ஆயிரம்")


_ONE_LETTER = r"[அ-ஹ](?:[\u0bbe-\u0bcc]|[அ-ஹ]\u0bcd|\u0bcd)?"
_INITIALS = re.compile(r"^\(?(?:" + _ONE_LETTER + r"\.){1,}$")      # 'ஆர்.வி.', 'எம்.எம்.', 'அக்.' - the dot is not a sentence end


def split_sentences(txt):
    """19 Nov: the sentences of a script. A dot after Tamil initials / short forms (ஆர்.வி. ஜெயக்குமார், 300 எம்.எம். குழாய், கே.கே. நகர்)
    no longer ends the sentence - the voice stopped in the middle of a name and the next card started with the surname."""
    out, cur = [], ""
    for part in re.split(r"(?<=[.!?\u0964])\s+", (txt or "").strip()):
        part = part.strip()
        if not part:
            continue
        cur = f"{cur} {part}" if cur else part
        if _INITIALS.match(cur.split()[-1]):
            continue      # joined with the next part
        out.append(cur)
        cur = ""
    if cur:
        out.append(cur)
    return out


_REL_DAYS = (("நேற்று முன்தினம்", -2), ("நாளை மறுநாள்", 2), ("நேற்று", -1), ("இன்று", 0), ("நாளை", 1))


def fix_relative_days(text, written, today=None):
    """19 Nov: a reel posted on a LATER day than it was written must not say இன்று / நேற்று / நாளை about the writing day (the audit
    found 'நேற்று' in a reel written on 12 Nov and posted on 15 Nov). Those words then become the date ('நவம்பர் 12ஆம் தேதி'),
    which stays right for everyone who watches the reel later. Same day: unchanged."""
    today = today or datetime.now(IST).date()
    if not text or not written or today <= written:
        return text
    for word, k in _REL_DAYS:
        d = written + timedelta(days=k)
        text = re.sub(r"(?<![\u0B80-\u0BFF])" + word + r"(?![\u0B80-\u0BFF])", f"{TAMIL_MONTHS[d.month - 1]} {d.day}ஆம் தேதி", text)
    return text


# 19 Nov: a sentence that only says the news caused a stir carries no fact - it is not read (the writer's rules already forbid it)
FILLER_ONLY = re.compile(r"^(?:இந்த(?:ச்)?|இச்)\s*சம்பவ[ம்த்][^.]*?(?:பரபரப்ப|அதிர்ச்சி|சோகத்த)[^.]*\.?$")


def shorten_script_detail(txt, ratio):
    """owner 2 Nov (review): a reel over 90 s loses the LEAST informative sentences first (no number, no outcome, no time/place fact),
    never the first one (the one-line story); returns (script, dropped sentences in story order)"""
    sents = [s.strip() for s in re.split(r"(?<=[.!?\u0964])\s+", (txt or "").strip()) if s.strip()]
    follow = [s for s in sents[-1:] if "பின்தொடரு" in s or "Follow" in s]
    body = sents[:-1] if follow else sents
    if len(body) <= 2:
        return txt, []
    budget = sum(len(s) for s in body) * max(0.3, min(ratio, 0.95))
    order = sorted(range(1, len(body)), key=lambda i: (len(_KEY_FACT.findall(body[i])) > 0, len(_KEY_FACT.findall(body[i])), i))
    drop, total = set(), sum(len(s) for s in body)
    for i in order:
        if total <= budget or len(body) - len(drop) <= 2:
            break
        drop.add(i)
        total -= len(body[i])
    if not drop:
        drop.add(order[0])
    keep = [s for i, s in enumerate(body) if i not in drop]
    return " ".join(keep + follow), [body[i] for i in sorted(drop)]


def add_to_caption(caption, sentences):
    """the sentences a long reel could not say go into the caption (before the hashtags) unless the caption already tells them"""
    cap = caption or ""
    def stems(t):
        return {w[:4] for w in re.findall(r"[\u0B80-\u0BFF]{4,}", t)}
    have = stems(cap)
    extra = [x for x in sentences if stems(x) and len(stems(x) - have) / len(stems(x)) > 0.5]
    if not extra:
        return cap
    i = cap.find("\n#")
    add = "\n" + "\n".join(extra)
    return (cap[:i] + add + cap[i:]) if i >= 0 else cap + add


def shorten_script(txt, ratio):
    """owner 28 Oct: a reel longer than 90 s is shortened, never skipped. Keeps the first sentence (the one-line story),
    then the next sentences in order while they fit in ratio x the original length; the follow line stays last.
    Always keeps at least 2 news sentences (+ the follow line), so reel_spec still has its 3 sentences."""
    sents = split_sentences(txt)
    follow = [s for s in sents[-1:] if "பின்தொடரு" in s or "Follow" in s]
    body = sents[:-1] if follow else sents
    if len(body) <= 2:
        return txt
    budget = sum(len(s) for s in body) * max(0.3, min(ratio, 0.95))
    keep, used = [], 0
    for i, s in enumerate(body):
        if i >= 2 and used + len(s) > budget:
            continue
        keep.append(s)
        used += len(s)
    if len(keep) == len(body):      # nothing could be dropped by the budget: drop the last news sentence
        keep = keep[:-1]
    return " ".join(keep + follow)


def reel_spec(row, spec, images):
    txt = (row.get("reel_script") or "").strip()
    sentences = split_sentences(txt)
    if len(sentences) > 4:
        sentences = [s for s in sentences if not FILLER_ONLY.match(s)]
    if len(sentences) < 3:
        raise RuntimeError(f"{row['story_id']}: reel script needs at least 3 sentences")
    # every reel ends with the same follow line (spoken in English by the system)
    STD = FOLLOW_LINE
    if "பின்தொடரு" in sentences[-1] or "Follow" in sentences[-1]:
        sentences = sentences[:-1]
    sentences.append(STD)
    body, last = sentences[:-1], sentences[-1]
    # an on-screen fact is shown ONLY while the sentence it matches is spoken (matched by shared word stems);
    # the old code cycled slide lines in order, so the chip often showed a different fact than the voice said.
    def _stems(t):
        return {w[:4] for w in re.findall(r"[\u0B80-\u0BFF]{4,}", re.sub(r"<[^>]+>", "", t))}
    pool = [re.sub(r"<[^>]+>", "", ln) for sl in spec.get("slides", []) for ln in sl.get("lines", [])]
    used, sents = set(), []
    for i, sent in enumerate(body):
        best, bs = "", 1
        st = _stems(sent)
        for j, ln in enumerate(pool):
            sc = len(st & _stems(ln))
            if j not in used and sc > bs and len(ln) <= (60 if CONFIG.get("reel_design") == "v4" else 48) and not re.search(r"(க்|ச்|த்|ப்)$", ln.strip(" .,;:")):
                best, bs, bj = ln, sc, j
        if best and i >= 1:
            used.add(bj)
        sents.append({"say": sent, "caption": sent, "fact": best if i >= 1 else ""})
    hook = [(spec.get("hl1") or "").strip(), (spec.get("hl2") or "").strip()]
    written = (filed_at(row) or datetime.now(IST)).date()      # 19 Nov: இன்று / நேற்று / நாளை as dates when posted on a later day
    for s in sents:
        for k in ("say", "caption", "fact"):
            s[k] = fix_relative_days(s[k], written)
    hook = [fix_relative_days(h, written) for h in hook]
    return {"v": 3, "story": row["story_id"], "date": spec["date"], "cat": (spec.get("cat") or "").strip(),
            "location": (spec.get("loc") or "திருச்சி")[:60], "voice": "male", "hook": hook,
            "mini": (row.get("headline_ta") or "").strip(), "source": source_credit(row)[0], "source_full": source_credit(row)[1],
            "images": [str(p) for p in images], "sentences": sents, "outro": {"say": last},
            "scenes": [{"caption": x["caption"]} for x in sents] + [{"caption": last}]}


def render_reel(row, spec, images, work, voice_file=None):
    rs = reel_spec(row, spec, images)
    (work / "reel.json").write_text(json.dumps(rs, ensure_ascii=False))
    env = dict(os.environ)
    if voice_file:
        env["VOICE_FILE"] = str(voice_file)
    if PROMO_NOW:      # owner 20 Nov: the approved sponsor ad (reel/promo360.py: bottom, during the news only)
        try:
            import promo
            pj = work / "promo.json"
            pj.write_text(json.dumps(promo.reel_promo(PROMO_NOW, work), ensure_ascii=False), encoding="utf-8")
            env["PROMO_JSON"] = str(pj)
        except Exception as e:
            log("promotion not added to the reel:", str(e)[:150])
    mp4 = work / f"{row['story_id']}_reel.mp4"
    design = "reel4.py" if CONFIG.get("reel_design") == "v4" else "reel3.py"      # v4: full-detail design (safe zone, 5W cards, summary, send CTA)
    subprocess.run([sys.executable, str(REEL / design), str(work / "reel.json"), str(mp4), PAGE], check=True, env=env)
    return mp4


# ---------------------------------------------------------------- hosting + Instagram
def upload(path, kind):
    url = f"https://api.cloudinary.com/v1_1/{CLOUD}/{'video' if kind == 'video' else 'image'}/upload"
    with open(path, "rb") as f:
        r = requests.post(url, data={"upload_preset": PRESET, "folder": "trichy360"}, files={"file": f}, timeout=600)
    r.raise_for_status()
    link = r.json()["secure_url"]
    if kind == "video":
        localmedia.remember(link, path)      # owner 21 Nov: Facebook gets the file, not the link
    return link


localmedia.set_uploader(lambda path, kind: upload(path, kind))      # owner 21 Nov: Cloudinary only when a file could not go directly


def cache_key(row, spec, caption):
    import hashlib
    raw = json.dumps([row.get("reel_script"), row.get("slides_spec"), caption, row.get("images"), spec.get("date"), row.get("post_to")]
                     + ["reel-r7"], ensure_ascii=False)      # r7 (20 Nov 19:10 IST): reels made in reel3 while config reel_design was overwritten are made again      # r6 (13 Nov 23:10): waiting premium-look reels are made again in the Namakkal design      # r2 (27 Oct): reels built before the <b>-tag fix are made again
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def cache_path(sid, page=None):
    page = page or PAGE
    return CACHE / (f"{sid}.json" if page == "trichy" else f"{sid}_{page}.json")


def load_cache(sid, key):
    try:
        d = json.loads(cache_path(sid).read_text(encoding="utf-8"))
        if d.get("key") == key and d.get("reel") and (d.get("carousel") or d.get("reel_only")):
            if not links_alive(d):
                log("prebuilt files were removed from Cloudinary (clean-up) - made and uploaded again")
                return None
            return d
    except Exception:
        pass
    return None


def links_alive(media):
    """owner 12 Nov: poster/cloudclean.py deletes old Cloudinary files; a cached link that is gone (404) means: upload again.
    A network error is not proof of a deleted file, so the cache is still used then."""
    urls = [media.get("reel"), media.get("cover"), media.get("story")] + list(media.get("carousel") or [])
    for u in [u for u in urls if u]:
        try:
            if requests.head(u, timeout=20, allow_redirects=True).status_code in (404, 410):
                return False
        except Exception:
            pass
    return True


def save_cache(sid, key, media, checks):
    try:
        CACHE.mkdir(parents=True, exist_ok=True)
        cache_path(sid).write_text(json.dumps(dict(media, key=key, checks=checks, reel_only=not media.get("carousel")), ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        log("cache not saved:", e)


VIA_FB = [False]      # owner 21 Nov: True while a reel / story goes to Instagram as a FILE (Instagram API with Facebook login)
LAST_CONTAINER = {}      # owner 21 Nov: the last container Instagram made - a file upload's address ("uri") comes with it


def ig_url(path):
    if VIA_FB[0]:
        return f"{igdirect.facebook.GRAPH}/{igdirect.facebook.VER}/{path}"
    return f"{IG_HOST}/{IG_VER + '/' if IG_VER else ''}{path}"


def ig(method, path, token, **params):
    params["access_token"] = token
    r = requests.request(method, ig_url(path), params=params if method == "GET" else None,
                         data=params if method == "POST" else None, timeout=120)
    try:
        data = r.json()
    except ValueError:
        r.raise_for_status()
        raise
    if r.status_code >= 400 or "error" in data:
        raise RuntimeError(f"Instagram {path}: {data.get('error', data)}")
    return data


def wait_ready(cid, token, minutes=10):
    end = time.time() + minutes * 60
    while time.time() < end:
        st = ig("GET", cid, token, fields="status_code,status").get("status_code")
        if st == "FINISHED":
            return
        if st in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram container {cid} {st}")
        time.sleep(10)
    raise RuntimeError(f"Instagram container {cid} not ready after {minutes} min")


def ig_account(token):
    me = ig("GET", "me", token, fields="user_id,username")
    return me.get("user_id") or me.get("id"), me.get("username")


PROMO_NOW = None      # owner 20 Nov: the approved promotion whose ad goes on the reel being made (poster/promo.py)
LOC_ID = ""   # Instagram location (place) id for the story being posted; set in run_story


def verified_locations():
    """location ids the ig-probe workflow found valid (poster/probe/locations_ok.json); none until it has run - then no location is tried
    (Namakkal 30-31 Oct: 30 of 30 tries refused with old Instagram explore ids)"""
    try:
        return {str(x) for x in json.loads((Path(__file__).resolve().parent / "probe" / "locations_ok.json").read_text())}
    except Exception:
        return set()


def pick_location(row, spec):
    """Instagram place id from config.json "locations" (keyword -> id).
    The place named FIRST in the Tamil headline wins, then the English headline, then the story's location fields;
    the district-wide 'trichy' tags are used only when no town, temple or hill is named.
    Trichy 360: config.json has no location ids yet, so this returns ''. 31 Oct: an id is used only after the ig-probe check accepted it."""
    ok = verified_locations()
    locs = {k: v for k, v in (CONFIG.get("locations") or {}).items() if str(v).strip() in ok}
    generic = {"trichy", "திருச்சி"}
    fields = [row.get("headline_ta", ""), row.get("headline_en", ""), spec.get("loc", ""), row.get("location", "")]
    for specific_only in (True, False):
        for f in fields:
            low = (f or "").lower()
            best = None
            for key, pid in locs.items():
                if key == "default" or not str(pid).strip().isdigit():
                    continue
                if specific_only and key in generic:
                    continue
                i = low.find(key.lower())
                if i >= 0 and (best is None or (i, -len(key)) < best[0]):
                    best = ((i, -len(key)), str(pid).strip())
            if best:
                return best[1]
    d = str(locs.get("default", "")).strip()
    return d if d.isdigit() else ""


COLLAB = ""      # page invited as collaborator for the story being posted (set in run_story_page)


def collab_user():
    """the account invited as collaborator: none for Trichy 360 (config.json collab_username is empty, collab_page() is always '')"""
    return CONFIG.get("collab_username", "")


def create_with_collab(uid, token, params, collab):
    """Create the media container with the location tag and the collaborator invite; if either is refused, retry without it (and say so)."""
    base = dict(params)
    if LOC_ID:
        base["location_id"] = LOC_ID

    def attempt(extra, p):
        try:
            r = ig("POST", f"{uid}/media", token, **extra, **p)
            LAST_CONTAINER.clear()
            LAST_CONTAINER.update(r)
            return r["id"]
        except RuntimeError as e:
            if ig_limit_kind(e):      # owner 21 Nov: a limit is never tried again at once without the collaborator / location
                raise IgLimit(str(e)) from None
            raise

    for use_loc in ([True, False] if LOC_ID else [False]):
        p = dict(base) if use_loc else dict(params)
        if collab and collab_user():
            try:
                return attempt(dict(collaborators=json.dumps([collab_user()])), p), True, ("" if use_loc or not LOC_ID else "location refused")
            except RuntimeError as e:
                log("container refused with collaborator" + (" + location" if use_loc and LOC_ID else "") + ":", e)
                try:
                    return attempt({}, p), False, str(e)[:300]
                except RuntimeError as e2:
                    log("container refused:", e2)
                    if not (use_loc and LOC_ID):
                        raise
                    continue
        try:
            return attempt({}, p), False, ""
        except RuntimeError as e:
            log("container refused:", e)
            if not (use_loc and LOC_ID):
                raise
    raise RuntimeError("could not create the media container")


def publish_carousel(token, urls, caption, collab, alt=""):
    uid, _ = ig_account(token)

    def kid(u, i):
        # alt text helps Instagram understand the picture (search / accessibility); dropped if the API refuses it
        if alt:
            try:
                return ig("POST", f"{uid}/media", token, image_url=u, is_carousel_item="true", alt_text=f"{alt} - slide {i}")["id"]
            except Exception as e:
                log("alt text refused, posting without it:", e)
        return ig("POST", f"{uid}/media", token, image_url=u, is_carousel_item="true")["id"]
    kids = [kid(u, i) for i, u in enumerate(urls, 1)]
    for k in kids:
        wait_ready(k, token, 5)
    cid, collab_ok, why = create_with_collab(uid, token, dict(media_type="CAROUSEL", children=",".join(kids), caption=caption), collab)
    wait_ready(cid, token, 5)
    mid = ig("POST", f"{uid}/media_publish", token, creation_id=cid)["id"]
    return mid, ig("GET", mid, token, fields="permalink").get("permalink", ""), collab_ok, why


class IgLimit(Exception):
    """owner 21 Nov: Instagram refused because of a limit - never tried again at once in another way (without the cover / collaborator)"""


def _ig_direct(d, prm, path, collab, page=None):
    """owner 21 Nov: the reel / story goes to Instagram as a FILE - the container is made with upload_type=resumable on the Instagram
    API with Facebook login (the only way Meta allows a file; the Instagram login said "video_url is required"), the file is sent to
    rupload.facebook.com and Instagram processes it. No Cloudinary. Raises on any problem before publishing (the caller uses the link)."""
    ig_id, tok = d
    p = {k: v for k, v in prm.items() if k not in ("video_url", "cover_url")}
    p["upload_type"] = "resumable"
    try:
        VIA_FB[0] = True
        try:
            cid, collab_ok, why = create_with_collab(ig_id, tok, p, collab)
        finally:
            VIA_FB[0] = False
        uri = str(LAST_CONTAINER.get("uri") or "") if str(LAST_CONTAINER.get("id")) == str(cid) else ""
        localmedia.send(uri if uri.startswith("https://rupload.facebook.com/") else igdirect.upload_url(cid), tok, path)
        VIA_FB[0] = True
        try:
            wait_ready(cid, tok, 15)
        finally:
            VIA_FB[0] = False
    except Exception as e:
        if igdirect.is_permission_error(e) and not ig_limit_kind(e):
            igdirect.off(page or PAGE, e)
        raise
    return cid, collab_ok, why


def _publish_direct(d, cid, link=True):
    """publish a container made by _ig_direct (graph.facebook.com); (media id, permalink)"""
    VIA_FB[0] = True
    try:
        mid = ig("POST", f"{d[0]}/media_publish", d[1], creation_id=cid)["id"]
        url = ""
        if link:
            try:
                url = ig("GET", mid, d[1], fields="permalink").get("permalink", "")
            except Exception:
                url = ""
    finally:
        VIA_FB[0] = False
    return mid, url


COVER_AT_MS = 900      # owner 21 Nov: a file has no cover link - Instagram takes the cover frame at 0.9 s (reel4.py's cover moment)


def publish_reel(token, video_url, caption, collab, cover_url=""):
    uid, _ = ig_account(token)
    prm = dict(media_type="REELS", caption=caption, share_to_feed="true")
    path = localmedia.get(video_url)      # this job's own file; None for a reel made in an earlier run (it goes by its link)
    d = igdirect.ready(PAGE, uid) if path else None
    if d:      # owner 21 Nov: the file goes straight to Instagram - no Cloudinary
        cid = None
        try:
            cid, collab_ok, why = _ig_direct(d, dict(prm, thumb_offset=str(COVER_AT_MS)), path, collab)
        except Exception as e:
            if ig_limit_kind(e):
                raise      # owner 21 Nov: a limit waits - never a second try by the link at once
            log("direct upload not used - posting with the link as before:", str(e)[:200])
        if cid:      # the file is on Instagram: publish it; from here on NO fallback (a reel is never posted twice)
            mid, link = _publish_direct(d, cid)
            log("reel sent as a file (direct upload, no Cloudinary)")
            return mid, link, collab_ok, why
    prm = dict(media_type="REELS", video_url=localmedia.hosted(video_url, "video"), caption=caption, share_to_feed="true")
    if cover_url:
        try:
            prm["cover_url"] = localmedia.hosted(cover_url, "image")   # chosen cover photo (sharp frame with the hook headline)
        except Exception as e:
            log("cover not uploaded - Instagram picks a frame:", str(e)[:120])
    try:
        cid, collab_ok, why = create_with_collab(uid, token, prm, collab)
    except RuntimeError as e:
        if not prm.get("cover_url"):
            raise
        log("reel refused with the cover, posting with Instagram's own cover:", e)
        prm.pop("cover_url", None)
        cid, collab_ok, why = create_with_collab(uid, token, prm, collab)
    wait_ready(cid, token, 15)
    mid = ig("POST", f"{uid}/media_publish", token, creation_id=cid)["id"]
    return mid, ig("GET", mid, token, fields="permalink").get("permalink", ""), collab_ok, why


# owner 19 Nov: viewers called some news fake and families were hurt - the page's OWN first comment on every news post gives the source
# (paper + article link) and the news date, a line for its kind of news (owner 19 Nov: every category has its own line) and that a
# correction / objection can come by DM. Made automatically from each news (no owner approval); it never asks people to comment.
# No source -> no comment (never guessed).
_TA = "஀-௿"
# someone died (Tamil headline only - English headlines add words such as "murders" to political statements)
_DEATH_TA = re.compile(rf"உயிரிழ|உயிர்\s*இழ|உயிர்ப்?\s*பலி|பலியா|பலி(?![{_TA}])|மரண|இறந்த|இறப்பு|காலமான|மறைவால்|மறைவுக்கு|மறைந்தார்|சடல|"
                       r"தற்கொலை|சாவு|மூளைச்சாவு|கொலை(?!\s*(?:மிரட்ட|முயற்சி|வெறி))|உடல்\s*(?:மிதந்த|மீட்பு|கண்டெடுப்பு|கண்டுபிடிப்பு)")
# an accident - counted only when people are in it (a shop fire with only goods burnt is not); "frequent accidents" on a road is a civic story
_ACCIDENT_TA = re.compile(r"(?<!அடிக்கடி )விபத்தில்|விபத்துக்குள்ளா|(?<!அடிக்கடி )விபத்து\s*(?:[:;,!|\-–—]|$)|(?<!பிரதமர் )(?<!நரேந்திர )மோதி(?!ர)|"
                          r"மோதல்|கவிழ்ந்|(?:கடைக்குள்|வீட்டுக்குள்|பள்ளத்தில்|கால்வாயில்|குளத்தில்)\s*பாய்ந்த|தவறி\s*விழு|மின்சாரம்\s*தாக்கி|"
                          r"வெடித்து|வெடி\s*விபத்து|தீப்பிடித்து|தீக்காய|"
                          r"(?:கிணற்றில்|தொட்டியில்|குளத்தில்|ஆற்றில்|கால்வாயில்|பள்ளத்தில்|குண்டத்தில்|மாடியிலிருந்து|மாடியில்\s*இருந்து)\s*(?:தவறி\s*)?விழு")
_INJURY = re.compile(r"காய|பலி|உயிர்|சிகிச்சை|மருத்துவமனை")
_ANIMAL = re.compile(rf"யானை|சிறுத்தை|புலி(?![{_TA}])|கரடி(?![{_TA}])|கரடிகள்|மாடு|பசு(?![{_TA}])|பசுக்கள்|எருமை|ஆடு(?![{_TA}])|ஆடுகள்|"
                     rf"நாய்|மயில்(?![{_TA}])|மயில்கள்|மான்(?![{_TA}])|மான்கள்|காட்டெருமை|குரங்கு(?![{_TA}])|குரங்குகள்|கால்நடை")
_PERSON = re.compile(rf"பேர்|நபர்|மாணவ|பெண்|ஆண்(?![{_TA}])|சிறுவன்|சிறுவர்|சிறுமி|முதியவர்|மூதாட்டி|இளைஞர்|வாலிபர்|குழந்தை|கணவ|மனைவி|"
                     r"தொழிலாளி|தொழிலாளர்|விவசாயி|டிரைவர்|ஓட்டுநர்|பயணி|தாய்|தந்தை|மகன்|மகள்|போலீஸ்|காவலர்|ஊழியர்|ஆசிரியர்|தொழிலதிபர்")
# someone arrested / booked / accused / in a court case (a missing-person report is not)
_ACCUSED_TA = re.compile(r"கைது|பிடிபட்டனர்|பிடிபட்டார்|பிடிபட்டான்|வழக்கு|குற்றம்\s*சாட்ட|குற்றஞ்சாட்ட|போக்சோ|சஸ்பெண்ட்|பணியிடை\s*நீக்க|சிறையில்|சிறைக்கு|ஜாமீன்|"
                         r"மோசடி|லஞ்ச|தலைமறைவ|குண்டர்\s*(?:தடுப்பு|சட்ட)")
_ACCUSED_EN = re.compile(r"\b(?:arrest(?:ed|s)?|booked\s+(?:for|under|on)|held\s+(?:for|with)|accused|pocso|jailed|nabbed|detained|absconding)\b",
                         re.I)
_CONVICTED = re.compile(r"\d+\s*(?:ஆண்டு|ஆண்டுகள்|மாதம்|மாத)\s*(?:கடுங்காவல்\s*)?(?:சிறை|தண்டனை)|ஆயுள்\s*(?:சிறை|தண்டனை)|மரண\s*தண்டனை|"
                        r"தண்டனை\s*விதி|அபராதம்\s*விதி|\b(?:convicted|sentenced|life\s+imprisonment)\b", re.I)
_SEXUAL = re.compile(r"பாலியல்|போக்சோ|பலாத்கார|\b(?:pocso|sexual(?:ly)?|rape[ds]?|molest(?:ed|ation)?)\b", re.I)
_POLITICS_TA = re.compile(r"திமுக|அதிமுக|தவெக|பாஜக|காங்கிரஸ்|பாமக|நாதக|விசிக|மதிமுக|தேமுதிக|அமமுக|கம்யூனிஸ்ட்|கட்சி|தேர்தல்|வேட்பாளர்|"
                          r"வாக்குப்பதிவு")
_POLITICS_EN = re.compile(r"\b(?:dmk|aiadmk|tvk|bjp|pmk|ntk|vck|mdmk|dmdk|ammk|congress|bypolls?|by-elections?|elections?|polls?)\b", re.I)
_JOBS = re.compile(r"வேலை\s*வாய்ப்பு\s*முகாம்|வேலைவாய்ப்பு\s*முகாம்|காலிப்\s*பணி|காலிப்பணி|பணியிடங்கள்|ஆட்சேர்ப்பு|"
                   r"\b(?:job\s*fair|recruitment|vacanc(?:y|ies))\b", re.I)
# a notice people act on: a camp, a scheme, applications, a deadline, free / subsidised items, a new rule
_GOVT = re.compile(r"முகாம்|விண்ணப்ப|திட்டம்|திட்டத்தி|உதவித்தொகை|கடைசி\s*(?:நாள்|தேதி)|இலவச|மானிய|பதிவு\s*செய்ய|டோக்கன்|ரேஷன்|"
                   r"கட்டாயம்|குறைதீர்")
_WILD = re.compile(rf"யானை|சிறுத்தை|புலி(?![{_TA}])|கரடி(?![{_TA}])|கரடிகள்|காட்டெருமை|காட்டுப்\s*பன்றி|மலைப்பாம்பு|பாம்பு|முதலை|"
                   r"\b(?:elephants?|leopards?|tigers?|bison|gaur|wild\s*boars?|pythons?|snakes?|crocodiles?)\b", re.I)
_FIRE = re.compile(r"தீ\s*விபத்து|தீப்பிடித்து|தீ\s*பற்றி|வீட்டில்\s*தீ|எரிந்து\s*(?:நாசம்|சேதம்|சாம்பல்)")
_CATEGORY_KIND = ((("wildlife", "forest"), "wildlife"), (("water", "irrigation", "dam"), "weather_agri"),
                  (("tourism", "entertainment", "cinema", "சுற்றுலா"), "events"),
                  (("crime", "safety", "குற்ற"), "safety"), (("government", "service", "அரசு"), "admin"), (("education", "கல்வி"), "education"),
                  (("health", "சுகாதார", "மருத்துவ"), "health"), (("weather", "agri", "வானிலை", "விவசாய"), "weather_agri"),
                  (("business", "price", "வணிக", "விலை"), "business"), (("civic",), "civic"), (("road", "transport", "போக்குவரத்து"), "roads"),
                  (("temple", "event", "கோவில்", "கோயில்"), "events"))


def comment_kind(row):
    """owner 19 Nov (every category gets its own line): {"kind", "not_guilty", "no_follow", "needs_link"} of a news.
    The Tamil headline's words decide first - a power cut, a death / an accident with people, someone convicted / accused, politics,
    jobs, a notice to act on - then the writer's category; "other" = the owner's own line.
    no_follow: a death / accident or sexual-offence news has no "Follow" line. needs_link: a death / accident / crime / court /
    missing-person / sexual-offence news is posted ONLY with its source link (owner 19 Nov)."""
    head = str(row.get("headline_ta") or "")
    ta = re.sub(rf"(?<=[{_TA}])\.", "", head)      # அ.தி.மு.க. -> அதிமுக (the headline only: a caption line can add other words)
    en = str(row.get("headline_en") or "")
    cat = str(row.get("category") or "")
    sexual = bool(_SEXUAL.search(ta + " " + en))
    out = {"kind": "other", "not_guilty": False, "no_follow": sexual, "needs_link": sexual}
    if "மின் தடை" in cat or "shutdown" in cat.lower() or POWER_CUT.search(head + " " + en):
        return dict(out, kind="power_cut")
    convicted = bool(_CONVICTED.search(ta + " " + en))
    accused = bool(_ACCUSED_TA.search(ta) or _ACCUSED_EN.search(en))
    people = not (_ANIMAL.search(ta) and not _PERSON.search(ta))      # an animal's death alone is not a family's loss
    if people and (_DEATH_TA.search(ta) or (_ACCIDENT_TA.search(ta) and (_INJURY.search(ta) or _PERSON.search(ta)))):
        return dict(out, kind="death", not_guilty=accused and not convicted, no_follow=True, needs_link=True)
    if convicted:
        return dict(out, kind="court", needs_link=True)
    if accused:
        return dict(out, kind="crime", needs_link=True)
    if _POLITICS_TA.search(ta) or _POLITICS_EN.search(en):
        return dict(out, kind="politics")
    if _JOBS.search(ta + " " + en):
        return dict(out, kind="jobs")
    if _GOVT.search(ta):
        return dict(out, kind="govt")
    if _WILD.search(ta + " " + en):
        return dict(out, kind="wildlife")
    if _FIRE.search(ta + " " + en):
        return dict(out, kind="fire")
    low = cat.lower()
    kind = next((k for keys, k in _CATEGORY_KIND if any(w in low for w in keys)), "other")
    if kind == "safety" and _ANIMAL.search(ta) and not _PERSON.search(ta):
        kind = "other"      # a cow rescued from a well: the owner's own line, not the police line
    return dict(out, kind=kind, needs_link=out["needs_link"] or kind == "safety")


SOURCE_COMMENT = ("📰 News Source: {source}\n"
                  "📅 News Date: {date}\n\n"
                  "{purpose}\n\n"
                  "செய்தி தொடர்பான திருத்தம், விளக்கம் அல்லது பகிர்வில் ஆட்சேபனை இருந்தால் எங்கள் DM மூலம் தெரிவிக்கலாம்.\n\n"
                  "📌 Note: தகவல்கள் கிடைத்த செய்தி ஆதாரத்தின் அடிப்படையில் பகிரப்பட்டுள்ளன.\n"
                  "🙏 நமது ஊர் செய்திகளுக்கு Follow செய்யுங்கள்.")
COMMENT_PURPOSE = {      # owner 19 Nov: one line per kind of news (comment_kind); "other" is the owner's own line
    "other": "இந்த செய்தி பொதுமக்களின் தகவல் மற்றும் விழிப்புணர்வுக்காக மட்டுமே மூல ஆதாரத்தின் அடிப்படையில் பகிரப்பட்டுள்ளது. "
             "உள்ளூர் செய்திகளை மக்களிடம் கொண்டு சேர்ப்பதே எங்கள் நோக்கம்.",
    "death": "இந்த செய்தி பொதுமக்களின் விழிப்புணர்வுக்காக மட்டுமே மூல ஆதாரத்தின் அடிப்படையில் பகிரப்பட்டுள்ளது. "
             "பாதிக்கப்பட்ட குடும்பத்தினரின் உணர்வுகளை நாங்கள் மதிக்கிறோம்.",
    "crime": "இந்த செய்தி மூல ஆதாரத்தின் அடிப்படையில் விழிப்புணர்வுக்காக மட்டுமே பகிரப்பட்டுள்ளது. "
             "நீதிமன்றத்தில் நிரூபிக்கப்படும் வரை குற்றம் சாட்டப்பட்டவர்கள் குற்றவாளிகள் அல்ல.",
    "court": "இந்த செய்தி நீதிமன்றத் தீர்ப்பு குறித்து மூல ஆதாரத்தின் அடிப்படையில் விழிப்புணர்வுக்காக மட்டுமே பகிரப்பட்டுள்ளது. "
             "தீர்ப்பு, மேல்முறையீடு போன்ற தொடர் சட்ட நடைமுறைகளுக்கு உட்பட்டது.",
    "safety": "இந்த செய்தி மூல ஆதாரத்தின் அடிப்படையில் விழிப்புணர்வுக்காக மட்டுமே பகிரப்பட்டுள்ளது. "
              "இது தொடர்பான தகவல் தெரிந்தால் அருகிலுள்ள காவல் நிலையத்தைத் தொடர்புகொள்ளுங்கள்.",
    "power_cut": "மின் தடை நேரமும் பகுதிகளும் மின்வாரிய அறிவிப்பின் அடிப்படையில் பகிரப்பட்டுள்ளன. பணிகளைப் பொறுத்து நேரம் மாறலாம், "
                 "சந்தேகம் இருந்தால் உங்கள் பகுதி மின்வாரிய அலுவலகத்தைத் தொடர்புகொள்ளுங்கள்.",
    "politics": "இந்த செய்தி மூல ஆதாரத்தின் அடிப்படையில் தகவலுக்காக மட்டுமே பகிரப்பட்டுள்ளது. "
                "நாங்கள் எந்தக் கட்சிக்கும் ஆதரவாகவோ எதிராகவோ செயல்படவில்லை.",
    "jobs": "இந்த தகவல் மூல ஆதாரத்தின் அடிப்படையில் பகிரப்பட்டுள்ளது. விண்ணப்பிக்கும் முன் தகுதி, கடைசி தேதியை அதிகாரப்பூர்வ அறிவிப்பில் "
            "சரிபாருங்கள். வேலை தருவதாகச் சொல்லிப் பணம் கேட்பவர்களிடம் எச்சரிக்கையாக இருங்கள்.",
    "govt": "இந்த தகவல் மூல ஆதாரத்தின் அடிப்படையில் பகிரப்பட்டுள்ளது. "
            "தேதி, விண்ணப்பம் போன்ற விவரங்களை அதிகாரப்பூர்வ அறிவிப்பில் உறுதி செய்துகொள்ளுங்கள்.",
    "admin": "இந்த செய்தி மூல ஆதாரத்தின் அடிப்படையில் பகிரப்பட்டுள்ளது. உள்ளூர் நிர்வாகத் தகவல்களை மக்களிடம் கொண்டு சேர்ப்பதே எங்கள் நோக்கம்.",
    "education": "இந்த தகவல் மூல ஆதாரத்தின் அடிப்படையில் பகிரப்பட்டுள்ளது. "
                 "மாணவர்களுக்கும் பெற்றோருக்கும் பயனுள்ள தகவல்களைக் கொண்டு சேர்ப்பதே எங்கள் நோக்கம்.",
    "health": "இந்த தகவல் மூல ஆதாரத்தின் அடிப்படையில் விழிப்புணர்வுக்காக மட்டுமே பகிரப்பட்டுள்ளது. மருத்துவ ஆலோசனைக்கு மருத்துவரை அணுகுங்கள்.",
    "weather_agri": "இந்த தகவல் மூல ஆதாரத்தின் அடிப்படையில் பகிரப்பட்டுள்ளது. "
                    "வானிலை, விவசாயம் தொடர்பான அதிகாரப்பூர்வ அறிவிப்புகளையும் கவனியுங்கள்.",
    "business": "இந்த தகவல் மூல ஆதாரத்தின் அடிப்படையில் பகிரப்பட்டுள்ளது. விலை, சந்தை நிலவரங்கள் இடத்துக்கும் நேரத்துக்கும் ஏற்ப மாறலாம்.",
    "civic": "இந்த செய்தி மூல ஆதாரத்தின் அடிப்படையில் பகிரப்பட்டுள்ளது. "
             "மக்களின் பிரச்சினைகள் அதிகாரிகளின் கவனத்துக்குச் செல்வதே எங்கள் நோக்கம்.",
    "roads": "இந்த தகவல் மூல ஆதாரத்தின் அடிப்படையில் பகிரப்பட்டுள்ளது. பயணத்துக்கு முன் சமீபத்திய நிலவரத்தை உறுதி செய்துகொள்ளுங்கள்.",
    "events": "இந்த தகவல் மூல ஆதாரத்தின் அடிப்படையில் பகிரப்பட்டுள்ளது. நம் ஊர் நிகழ்வுகளை மக்களிடம் கொண்டு சேர்ப்பதே எங்கள் நோக்கம்.",
    "wildlife": "இந்த தகவல் மூல ஆதாரத்தின் அடிப்படையில் விழிப்புணர்வுக்காக மட்டுமே பகிரப்பட்டுள்ளது. "
                "வனவிலங்குகள் நடமாட்டம் தெரிந்தால் வனத்துறைக்குத் தகவல் தெரிவியுங்கள்.",
    "fire": "இந்த செய்தி மூல ஆதாரத்தின் அடிப்படையில் விழிப்புணர்வுக்காக மட்டுமே பகிரப்பட்டுள்ளது. தீ விபத்து ஏற்பட்டால் உடனே 101 எண்ணை அழைக்கவும்.",
}
NOT_GUILTY = "நீதிமன்றத்தில் நிரூபிக்கப்படும் வரை குற்றம் சாட்டப்பட்டவர்கள் குற்றவாளிகள் அல்ல."      # a death with someone accused (not convicted)
COMMENT_MAX = 2000      # Instagram allows 2,200 characters in a comment


def source_comment(row):
    """the first comment for this news: "<paper> - <article link>", the news date and the line for its kind of news ('' when the source
    is unknown). A paper not in SOURCE_NAMES is shown by its link only; an unknown date leaves its line out; a death / accident or
    sexual-offence news has no "Follow" line."""
    link = str(row.get("source") or "").strip()
    link = link if re.fullmatch(r"https?://\S+", link) else ""
    names = source_names(row)
    paper = (("மின்வாரிய அறிவிப்பு • " if is_shutdown(row) and "மின்வாரியம்" not in names else "") + ", ".join(names)) if names else ""
    src = " - ".join(x for x in (paper, link) if x)
    if not src:
        return ""
    k = comment_kind(row)
    purpose = COMMENT_PURPOSE.get(k["kind"], COMMENT_PURPOSE["other"]) + (" " + NOT_GUILTY if k["not_guilty"] else "")
    day = news_day(row)
    msg = "\n".join(l for l in SOURCE_COMMENT.format(source=src, date=day, purpose=purpose).split("\n")
                    if not (l.startswith("📅") and not day) and not (l.startswith("🙏") and k["no_follow"]))
    if len(msg) > COMMENT_MAX and paper:      # a very long link: the paper's name is kept, the link left out
        msg = msg.replace(src, paper, 1)
    return msg if len(msg) <= COMMENT_MAX else ""


def is_source_comment(text):
    """True for the page's own automatic source comment (comments.py never treats it as a viewer's comment)"""
    t = str(text or "").lstrip()
    return t.startswith("📰 News Source:") and "DM மூலம் தெரிவிக்கலாம்" in t


def link_hold(row):
    """owner 21 Nov: ONLY news with its source link is posted (19 Nov: only sensitive news needed it) - so every news reel carries the
    source comment with the article link. '' = fine. The owner's own ready reels are posted as they are."""
    if is_ready_reel(row) or re.fullmatch(r"https?://\S+", str(row.get("source") or "").strip()):
        return ""
    return "held: no source link (owner 21 Nov: only news with its source link is posted) - add the article link in the source column to post it"


POSTED_DIR = ROOT / "poster" / "posted"      # owner 21 Nov: one small record per posted news (the posted report reads them)


def record_posted(sid, row, link, kind="reel"):
    """owner 21 Nov ("news posted e-mail not received - I don't know if news is posted"): every posted news leaves a tiny file
    poster/posted/<UTC time>-<page>-<story>.json (committed by post.yml); news360's posted_report.py e-mails ONE report for all
    pages 4 times a day. Files older than 3 days are removed. Never raises."""
    try:
        now = datetime.now(timezone.utc)
        POSTED_DIR.mkdir(parents=True, exist_ok=True)
        cut = (now - timedelta(days=3)).strftime("%Y%m%d")
        for f in POSTED_DIR.glob("*.json"):
            if f.name[:8] < cut:
                f.unlink()
        rec = {"page": PAGE, "story": sid, "kind": kind, "headline": str((row or {}).get("headline_ta") or "")[:200], "link": link or "",
               "at": now.isoformat(timespec="seconds")}
        (POSTED_DIR / f"{now:%Y%m%d-%H%M%S}-{PAGE}-{sid}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception as e:
        log("posted record not saved:", str(e)[:120])


def first_comment(token, media_id, sid, row):
    """owner 19 Nov: the source comment above, posted by the page right after the news post is recorded - automatically, no approval.
    owner 21 Nov: every news reel has it - only news with its source link is posted (link_hold); a refused comment is tried once more.
    Never raises: a comment problem never touches the post."""
    try:
        if not CONFIG.get("first_comment", False) or not media_id or not row:
            return
        msg = source_comment(row)
        if not msg:
            log("source comment not added: the news source is not known", sid)
            return
        for attempt in (1, 2):
            try:
                ig("POST", f"{media_id}/comments", token, message=msg)
                log("source comment added", sid, media_id)
                return
            except Exception as e:
                if attempt == 2 or not is_transient(e) or ig_limit_kind(e):
                    raise
                log("source comment refused once - trying again:", str(e)[:150])
                time.sleep(8)
    except Exception as e:
        k = ig_limit_kind(e)
        if k in ("block", "rate"):      # owner 21 Nov: too many requests - the page slows down
            ig_pause(PAGE, e, k)
        log("source comment not added (post itself is fine):", str(e)[:300])


def _story_room():
    """owner 1 Nov: EVERY post also goes to the story. Only the last few posts of Instagram's 24-hour limit are kept for news posts
    (config story_reserve, default 5); a story that has to wait is posted later by story_catchup() - never lost."""
    reserve = int(CONFIG.get("story_reserve", 5))
    LIMIT.pop(PAGE, None)      # owner 2 Nov (review): the count read when this job started is old - other jobs posted meanwhile
    try:
        limit_reached(PAGE)
    except Exception:
        pass
    if USED.get(PAGE) is None or PAGE not in TOTAL:
        return True
    return USED[PAGE] + 1 <= TOTAL[PAGE] - reserve


def urgent_stories_only():
    """owner 14 Nov (plan A): 24 news a day x 2 posts would use all 50 of Instagram's 24-hour posts - the story share is kept for
    power cuts / urgent news only (config stories_urgent_only; false = every post gets its story as before)"""
    return bool(CONFIG.get("stories_urgent_only", False))


def wants_story(row):
    return not urgent_stories_only() or row is None or is_urgent(row)


def publish_story(token, media_url, kind, row=None):
    """Instagram Story (image or video) on the same account. Never raises: a story problem must not undo the post."""
    try:
        if not CONFIG.get("post_stories", True):
            return ""
        if not wants_story(row):
            log("no story share: only power cuts / urgent news go to the story (owner 14 Nov)")
            return ""
        if not _story_room():
            log(f"story waits: {USED[PAGE]}/{TOTAL[PAGE]} posts in 24 h - posted by the story catch-up when the limit allows")
            return ""
        uid, _ = ig_account(token)
        prm = dict(media_type="STORIES")
        path = localmedia.get(media_url) if kind == "video" else None      # this job's own file
        d = igdirect.ready(PAGE, uid) if path else None
        if d:      # owner 21 Nov: the file goes straight to Instagram - no Cloudinary
            cid = None
            try:
                cid = _ig_direct(d, prm, path, False)[0]
            except Exception as e:
                if ig_limit_kind(e):
                    raise
                log("story: direct upload not used - the link is used:", str(e)[:150])
            if cid:
                mid = _publish_direct(d, cid, link=False)[0]
                USED[PAGE] = USED.get(PAGE, 0) + 1
                log("story posted", kind, mid, "(sent as a file)")
                return mid
        prm["video_url" if kind == "video" else "image_url"] = localmedia.hosted(media_url, kind)
        cid = ig("POST", f"{uid}/media", token, **prm)["id"]
        wait_ready(cid, token, 10)
        mid = ig("POST", f"{uid}/media_publish", token, creation_id=cid)["id"]
        USED[PAGE] = USED.get(PAGE, 0) + 1
        log("story posted", kind, mid)
        return mid
    except Exception as e:
        k = ig_limit_kind(e)
        if k in ("block", "create", "rate"):      # owner 21 Nov: a limit pauses the page (never tried every run)
            ig_pause(PAGE, e, k)
        log("story not posted (post itself is fine - the story catch-up tries again):", e)
        return ""


def _ts(s):
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S%z")
    except Exception:
        return None


SHARED = Path(__file__).resolve().parent / "story_shared.json"      # post id -> story id of the catch-up (committed by post.yml's check step)


def story_catchup(max_new=6):
    """owner 1 Nov: every post of the page - news reel, carousel, the daily rasipalan, a post made by any other job - also goes to the
    story. A post less than 20 hours old with no story made within 30 minutes after it gets its story now (while the 24-hour limit
    leaves room for news posts). Never raises."""
    if DRY or not CONFIG.get("post_stories", True):
        log("story catch-up off (test run or post_stories false)")
        return
    if quiet_now():      # owner 21 Nov: no Instagram posts at night, stories included
        log("story catch-up waits:", quiet_now())
        return
    reserve = int(CONFIG.get("story_reserve", 5))
    try:
        shared = json.loads(SHARED.read_text(encoding="utf-8"))
    except Exception:
        shared = {}
    cut = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    shared = {k: v for k, v in shared.items() if v.get("at", "") >= cut}
    tries_max = int(CONFIG.get("story_catchup_tries", 2))      # owner 21 Nov: a story that fails twice is given up (no endless tries)
    for pg in LABEL:
        try:
            why = ig_paused(pg)
            if why:      # owner 21 Nov: a paused page makes no story either
                log(f"story catch-up {pg} waits: {why}")
                continue
            token = bridge_get("token", page=pg)["token"]
            uid, _ = ig_account(token)
            me = ig("GET", "me", token, fields="id,user_id")
            mine = {str(x) for x in (uid, me.get("id"), me.get("user_id")) if x}      # 1 Nov: a post's owner id is the app id, not user_id
            q = (ig("GET", f"{uid}/content_publishing_limit", token, fields="quota_usage,config").get("data") or [{}])[0]
            used, total = int(q.get("quota_usage", 0)), min(int((q.get("config") or {}).get("quota_total", 50) or 50), IG_LIMIT)
            feed = ig("GET", f"{uid}/media", token, fields="id,media_type,media_url,timestamp,owner,caption,children{media_type,media_url}", limit=40).get("data", [])
            stories = sorted(t for t in (_ts(x.get("timestamp", "")) for x in ig("GET", f"{uid}/stories", token, fields="id,timestamp").get("data", [])) if t)
            now = datetime.now(timezone.utc)
            made = tries = 0
            log(f"story catch-up {pg}: quota {used}/{total}, {len(feed)} recent posts, {len(stories)} live stories, owner ids {sorted(mine)}")
            for m in sorted(feed, key=lambda x: x.get("timestamp", "")):
                t = _ts(m.get("timestamp", ""))
                if not t or str((m.get("owner") or {}).get("id") or uid) not in mine:
                    continue      # a collab post of the other page: that page shares it
                if urgent_stories_only():      # owner 14 Nov (plan A): only a power-cut post is caught up
                    import freshness
                    if not freshness.is_power_cut((m.get("caption") or "")[:300]):
                        continue
                tkey = f"t:{pg}:{t:%Y-%m-%dT%H:%M}"
                if not timedelta(minutes=20) <= now - t <= timedelta(hours=20) or m.get("id") in shared or tkey in shared:
                    continue      # (1 Nov: a late story is not inside the 30-minute window - the rasipalan got a 2nd story)
                hit = next((s for s in stories if t - timedelta(minutes=2) <= s <= t + timedelta(minutes=30)), None)
                if hit:
                    stories.remove(hit)      # one story belongs to one post
                    continue
                if used + 1 > total - reserve:
                    log(f"story catch-up {pg}: {used}/{total} posts in 24 h - the rest waits for room")
                    break
                if made >= max_new:
                    break
                if m.get("media_type") == "CAROUSEL_ALBUM":
                    ch = ((m.get("children") or {}).get("data") or [{}])[0]
                    url, kind = ch.get("media_url"), ("video" if ch.get("media_type") == "VIDEO" else "image")
                else:
                    url, kind = m.get("media_url"), ("video" if m.get("media_type") == "VIDEO" else "image")
                if not url:
                    continue
                if tries >= max_new * 2:
                    break
                tries += 1
                try:
                    prm = dict(media_type="STORIES")
                    d = path = None
                    if kind == "video":      # 1 Nov: Instagram refuses its own CDN video link for a story - the file is sent again
                        path = localmedia.download(url, "story.mp4")
                        if not path:
                            raise RuntimeError("the post's video could not be read")
                        d = igdirect.ready(pg, uid)
                        if not d:      # no Facebook token for this page yet: hosted again on Cloudinary, as before
                            url = upload(Path(path), "video")
                    if d:      # owner 21 Nov: straight to Instagram as a file - no Cloudinary
                        cid = _ig_direct(d, prm, path, False, page=pg)[0]
                        sid = _publish_direct(d, cid, link=False)[0]
                    else:
                        prm["video_url" if kind == "video" else "image_url"] = url
                        cid = ig("POST", f"{uid}/media", token, **prm)["id"]
                        wait_ready(cid, token, 8)
                        sid = ig("POST", f"{uid}/media_publish", token, creation_id=cid)["id"]
                    used += 1
                    made += 1
                    shared[m.get("id")] = shared[tkey] = {"story": sid, "page": pg, "at": now.isoformat()}
                    log(f"story catch-up {pg}: story {sid} for the post of {t:%d %b %H:%M} UTC ({m.get('media_type')})")
                except Exception as e:
                    k = ig_limit_kind(e)
                    if k:      # owner 21 Nov (Trichy): a limit stops the catch-up - no more tries this run, the page pauses
                        if k != "quota":
                            ig_pause(pg, e, k)
                        log(f"story catch-up {pg}: Instagram limit ({k}) - no more story tries now:", str(e)[:150])
                        break
                    fk = f"f:{m.get('id')}"
                    n = int((shared.get(fk) or {}).get("n", 0)) + 1
                    shared[fk] = {"n": n, "page": pg, "at": now.isoformat()}
                    if n >= tries_max:      # owner 21 Nov: never tried every run (Trichy 20-21 Nov: 400+ tries made Instagram stop the page)
                        shared[m.get("id")] = shared[tkey] = {"story": "", "failed": str(e)[:150], "page": pg, "at": now.isoformat()}
                        log(f"story catch-up {pg}: post {m.get('id')} not shared ({str(e)[:150]}) - tried {n} times, given up")
                    else:
                        log(f"story catch-up {pg}: post {m.get('id')} not shared ({str(e)[:150]}) - tried again in a later run ({n}/{tries_max})")
        except Exception as e:
            log(f"story catch-up {pg} skipped:", str(e)[:200])
    try:
        SHARED.write_text(json.dumps(shared, indent=1), encoding="utf-8")
    except Exception as e:
        log("story list not saved:", e)


def story_image(jpg, dst):
    """9:16 story frame from a carousel slide: slide centred on a blurred, darkened copy of itself"""
    im = Image.open(jpg).convert("RGB")
    bg = im.resize((1080, 1920), Image.LANCZOS).filter(ImageFilter.GaussianBlur(40))
    bg = ImageEnhance.Brightness(bg).enhance(0.55)
    w = 1080
    h = round(im.height * w / im.width)
    if h > 1920:
        h = 1920
        w = round(im.width * h / im.height)
    fg = im.resize((w, h), Image.LANCZOS)
    bg.paste(fg, ((1080 - w) // 2, (1920 - h) // 2))
    bg.save(dst, "JPEG", quality=94)
    return dst


# ---------------------------------------------------------------- main flows
def fail(row, kind, msg):
    log("NOT POSTED -", row["story_id"], msg)
    bridge_post("error", {"row": row["row"], "page": PAGE, "kind": kind, "error": msg[:900]})


def still_needed(sid, page, kind):
    """last check right before publishing: the sheet may have changed while this slow job was building (row marked skipped / already posted),
    and another job may have posted the same news meanwhile (Instagram feeds of both pages and the Sheet are read again)"""
    try:
        rows = bridge_get("queue")["rows"]
    except Exception:
        try:
            time.sleep(20)
            rows = bridge_get("queue")["rows"]
        except Exception as e:      # owner 2 Nov (review): without the Sheet we cannot know it is not posted yet - wait for the next run
            log("Sheet not readable right before publishing - waits for the next run:", str(e)[:120])
            return False
    r = next((x for x in rows if x.get("story_id") == sid), None)
    if r is not None and kind == "reel":
        global ALL_ROWS
        try:
            fresh_rows = rows + [x for x in bridge_get("recent").get("rows", []) if x.get("story_id") not in {y.get("story_id") for y in rows}]
            ALL_ROWS = fresh_rows
        except Exception:
            pass
        IG_RECENT.clear()
        for pg in PAGES:      # the one page's Instagram feed is read again
            if r.get(pg + "_link") or LABEL[pg] in (r.get("reel_link") or ""):
                continue      # this story's own earlier post on that page is not a duplicate
            dup = ig_duplicate(r, pg)
            if dup:
                log(f"same news already on {LABEL[pg]} ({dup}) - not publishing", sid)
                return False
        why = skip_reason(r)
        if why.startswith("duplicate"):
            log(why, "- not publishing", sid)
            return False
    if r is None:
        return False
    if (r.get("review") or "").strip().lower() == "hold":
        return False
    if str(r.get("post_status") or "").strip().lower().startswith(("skipped", "expired")):
        return False
    if kind == "carousel":
        return not r.get(page + "_link")
    return LABEL[page] not in (r.get("reel_link") or "")


IG_LIMIT = int(os.environ.get("IG_DAILY_LIMIT", "50"))      # real Instagram limit per page per 24 h (feed posts AND stories count)
TOTAL = {}
SOFT_CAP = int(os.environ.get("DAILY_CAP", "25") or 25)     # Trichy 360 starts at 25 reels per 24 h (post.yml sets DAILY_CAP); above the cap only High / power-cut news goes out. Instagram's own limit is IG_LIMIT (50)
USED = {}


LIMIT = {}      # page -> True once Instagram's 24-hour publishing limit (50 posts per account) is reached


def ig_pause_file(page):
    return CACHE / f"_ig_paused_{page}.json"      # in poster/prebuilt: committed by the posting job, read by every later run


PAUSE_WHY = {"block": "Instagram blocked publishing", "create": "Instagram's limit on new posts (too many made in 24 h)",
             "rate": "Instagram asked to slow down (too many requests)"}


def ig_paused(page):
    """'' or why this page's Instagram publishing is paused (owner 21 Nov: a block, or one of Instagram's limits)"""
    try:
        d = json.loads(ig_pause_file(page).read_text(encoding="utf-8"))
        if datetime.fromisoformat(d["until"]) > datetime.now(timezone.utc):
            return f"{PAUSE_WHY.get(d.get('kind') or 'block', 'Instagram limit')} on {page} - paused until {d['until'][:16]} UTC"
    except Exception:
        pass
    return ""


def ig_pause(page, e, kind="block"):
    """owner 21 Nov (Trichy: 5 reels in 3 minutes, then 'action is blocked' 2207051; later 400+ story tries, then 'Media Creation Limit
    Exceeded' 2207069): trying again every few minutes makes a block / limit longer - this page's Instagram posting waits
    (block: config ig_block_pause_hours 6; too many posts made: ig_create_pause_hours 6; too many requests: ig_rate_pause_min 60).
    Its news is posted after that, nothing is lost. A longer pause that is already running is never shortened."""
    try:
        if kind == "rate":
            hours = float(CONFIG.get("ig_rate_pause_min", 60)) / 60
        elif kind == "create":
            hours = float(CONFIG.get("ig_create_pause_hours", 6))
        else:
            hours = float(CONFIG.get("ig_block_pause_hours", 6))
        until_dt = datetime.now(timezone.utc) + timedelta(hours=hours)
        try:
            old = json.loads(ig_pause_file(page).read_text(encoding="utf-8"))
            if datetime.fromisoformat(old["until"]) >= until_dt:
                LIMIT[page] = True
                return
        except Exception:
            pass
        until = until_dt.isoformat(timespec="seconds")
        CACHE.mkdir(parents=True, exist_ok=True)
        ig_pause_file(page).write_text(json.dumps({"until": until, "kind": kind, "why": str(e)[:300]}, indent=1), encoding="utf-8")
        LIMIT[page] = True
        word = "BLOCKED" if kind == "block" else "PAUSED"
        log(f"{word}: {PAUSE_WHY.get(kind, 'Instagram limit')} on {page} - its posting pauses {hours:g} h (until {until[:16]} UTC), news waits")
    except Exception as x:
        log("pause not saved:", str(x)[:150])


def is_blocked(e):
    t = str(e).lower()
    return "2207051" in t or "action is blocked" in t


def ig_limit_kind(e):
    """owner 21 Nov (Trichy 20-21 Nov: the story catch-up tried every run - 'Fatal', then 'Application request limit reached', then
    'Media Creation Limit Exceeded' 2207069 from 10:30 IST, after which no reel could be made): which Instagram limit refused this.
    '' not a limit | 'block' publishing blocked (2207051) | 'create' too many posts made in 24 h (2207069) |
    'quota' the 50 posts of 24 h are used (2207042) | 'rate' too many requests (code 4 / 9 / 17 / 32 / 613, 80002)"""
    t = str(e).lower()
    if "2207051" in t or "action is blocked" in t:
        return "block"
    if "2207069" in t or "media creation limit" in t or "allowed to be created" in t:
        return "create"
    if "2207042" in t or "publish limit" in t or "publishing limit" in t or ("maximum number of" in t and "posts" in t):
        return "quota"
    if ("request limit reached" in t or "too many calls" in t or "too many actions" in t or "80002" in t
            or any(f"'code': {c}," in t for c in (4, 9, 17, 32, 613))):
        return "rate"
    return ""


def is_limit_error(e):
    k = ig_limit_kind(e)
    if k in ("block", "create", "rate"):      # owner 21 Nov: these wait like the daily limit (never "tried again in the next run" every few minutes)
        ig_pause(PAGE, e, k)
    return bool(k)


def is_transient(e):
    """Instagram / network trouble that goes away by itself: the story is tried again in the next run, nothing is marked failed"""
    t = str(e).lower()
    return ("'is_transient': true" in t or "request limit reached" in t or "'code': 4," in t or "'code': 17," in t or "'code': 32," in t
            or "please retry" in t or "timed out" in t or ("connection" in t and "error" in t) or "server error" in t)


def limit_reached(page):
    """True when this page already used its 50 API posts of the last 24 h. The only reason a prepared story is held back (it is posted later,
    nothing is marked failed)."""
    if page in LIMIT:
        return LIMIT[page]
    why = ig_paused(page)
    if why:      # owner 21 Nov: the page's Instagram publishing is paused after a block
        log(why)
        LIMIT[page] = True
        return True
    LIMIT[page] = False
    if DRY:
        return False
    try:
        token = bridge_get("token", page=page)["token"]
        uid, _ = ig_account(token)
        d = ig("GET", f"{uid}/content_publishing_limit", token, fields="quota_usage,config")
        row = (d.get("data") or [{}])[0]
        used, total = int(row.get("quota_usage", 0)), int((row.get("config") or {}).get("quota_total", 50) or 50)
        total = min(total, IG_LIMIT)      # the API says 100, but Instagram blocked the Namakkal page at 50/100 (25 Oct)
        USED[page] = used
        TOTAL[page] = total
        log(f"publishing quota {page}: {used}/{total}")
        LIMIT[page] = used >= total
    except Exception as e:
        log("quota check failed (posting goes on):", e)
    return LIMIT[page]


IG_RECENT = {}   # page -> [(iso time, caption)] of the page's latest Instagram posts


def ig_recent(page):
    """last ~50 posts of the page read from Instagram itself (the sheet can miss posts made by hand or by an older run)"""
    if page in IG_RECENT:
        return IG_RECENT[page]
    IG_RECENT[page] = []
    if DRY:
        return []
    try:
        token = bridge_get("token", page=page)["token"]
        uid, _ = ig_account(token)
        d = ig("GET", f"{uid}/media", token, fields="caption,timestamp", limit=50)
        IG_RECENT[page] = [(m.get("timestamp") or "", m.get("caption") or "") for m in d.get("data") or []]
        log(f"instagram duplicate check {page}: {len(IG_RECENT[page])} recent posts read")
    except Exception as e:
        log("instagram duplicate check unavailable (posting goes on):", e)
    return IG_RECENT[page]


def _ig_dup_for_check(row, page):
    """the same Instagram-duplicate rule as run_story (owner reels and a page's own earlier half-post are never duplicates)"""
    try:
        if json.loads(row.get("slides_spec") or "{}").get("ready_reel") or row.get(page + "_link") or row.get("reel_link"):
            return ""
        return ig_duplicate(row, page)
    except Exception:
        return ""


def minutes_since_last_post(page):
    """minutes since this page's newest Instagram post (1e9 when unknown) - owner 2 Nov: posts are spread, never a burst"""
    try:
        ts = max((t for t, _ in ig_recent(page) if t), default="")
        if not ts:
            return 1e9
        t = datetime.fromisoformat(ts.replace("+0000", "+00:00"))
        return (datetime.now(timezone.utc) - t).total_seconds() / 60
    except Exception:
        return 1e9


def ig_duplicate(row, page):
    """the story id/time of a recent Instagram post of this page that is the same news, else ''"""
    import freshness
    ta, en = (row.get("headline_ta") or "").strip(), (row.get("headline_en") or "").strip().lower()
    for ts, cap in ig_recent(page):
        head = cap.strip().split("\n")[0]
        if hasattr(freshness, "cancel_differs") and freshness.cancel_differs(ta or row.get("caption") or "", head):
            continue      # owner 11 Nov: a power cut and its cancellation / change are different news
        if ta and freshness.similar(head[:len(ta) + 8], ta, 0.62, ts):
            return ts
        if en and freshness.similar(cap.strip()[:len(en) + 8].lower(), en, 0.65, ts):
            return ts
        if ta and freshness.same_power_cut(head, ts, ta, row.get("published") or row.get("researched")):      # owner 30 Oct: same cut day + same place
            return ts
        # the whole caption of this story against the page's recent captions (stems of the first 40 words): same news worded differently
        mine = (row.get("caption") or "").strip()
        if len(mine) > 80 and len(cap.strip()) > 80:
            def stems(t):
                return {w[:5] for w in re.findall(r"[\u0B80-\u0BFF]{3,}", t)[:40]}
            a, b = stems(mine), stems(cap)
            if a and b and len(a & b) / min(len(a), len(b)) >= 0.7 and not freshness.different_numbers(ta or mine[:120], head):
                return ts
    return ""


MANUAL = os.environ.get("MANUAL", "") == "1"      # owner 22 Nov: this job e-mails the reel for a manual post instead of posting
MANUAL_PAGE = os.environ.get("MANUAL_PAGE", "").strip()
MANUAL_FILE = ROOT / "poster" / "manual_sent.json"      # page:story -> first seen ready / queued / sent (committed)
MANUAL_AFTER_H = 3      # a ready news not posted after 3 hours goes to the owner's e-mail
MANUAL_DAY_MAX = 20     # at most 20 such e-mails a day (Gmail's daily sending limit is about 100)


def manual_state():
    try:
        return json.loads(MANUAL_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def manual_save(st):
    try:
        cut = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
        st = {k: v for k, v in st.items() if str(v.get("first", "")) >= cut}
        MANUAL_FILE.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception as e:
        log("manual-post list not saved:", str(e)[:120])


def manual_due(rows, posting_now, now=None):
    """owner 22 Nov: ready news a page cannot post - Instagram paused / limit reached, or still not posted 3 hours after it was ready.
    [(story, page)] to e-mail now (at most 4 per run, 20 a day, each news once)."""
    if DRY or PREBUILD or quiet_now():
        return []
    if os.environ.get("GITHUB_ACTIONS") != "true" and MANUAL_FILE == ROOT / "poster" / "manual_sent.json":
        return []      # only the posting job keeps this list (a local test run never touches it)
    now = now or datetime.now(timezone.utc)
    day = now.astimezone(IST).strftime("%Y-%m-%d")
    st = manual_state()
    sent_today = sum(1 for v in st.values() if v.get("day") == day)
    out = []
    for r in pick_all(rows):
        sid = r.get("story_id")
        for p in pages_of(r):
            if page_done(r, p) or sid in posting_now:
                continue
            v = st.setdefault(f"{p}:{sid}", {"first": now.isoformat(timespec="seconds")})
            if v.get("sent") and (v.get("video", True) or v.get("resent")):      # owner 22 Nov: sent without its video - once more
                continue
            if int(v.get("tries", 0)) >= 3:
                continue
            if v.get("queued") and now - datetime.fromisoformat(v["queued"]) < timedelta(minutes=60):
                continue      # its e-mail job is running
            why = ig_paused(p) or ("Instagram's 24-hour post limit is reached" if LIMIT.get(p) else "")
            if not why and now - datetime.fromisoformat(v["first"]) >= timedelta(hours=MANUAL_AFTER_H):
                why = f"ready for more than {MANUAL_AFTER_H} hours and still not posted"
            if why and sent_today + len(out) < MANUAL_DAY_MAX and len(out) < 4:
                v.update(queued=now.isoformat(timespec="seconds"), why=why)
                out.append((sid, p))
    manual_save(st)
    if out:
        log("manual post e-mail (the page cannot post them):", [f"{p}:{s}" for s, p in out])
    return out


def email_copy(path, limit=15 * 1024 * 1024):
    """owner 22 Nov: a full-quality reel is too big for an e-mail - a 720p copy that fits (same picture and sound); None if it cannot"""
    import shutil
    if not path or not os.path.exists(path):
        return None
    if os.path.getsize(path) <= limit:
        return path
    ff = shutil.which("ffmpeg")
    if not ff:
        return None
    for crf in (28, 32, 36):
        out = Path(path).with_name(Path(path).stem + f"_email{crf}.mp4")
        try:
            subprocess.run([ff, "-y", "-loglevel", "error", "-i", str(path), "-vf", "scale=720:-2", "-c:v", "libx264", "-preset", "veryfast",
                            "-crf", str(crf), "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(out)], check=True, timeout=600)
        except Exception as e:
            log("e-mail copy of the reel not made:", str(e)[:150])
            return None
        if out.exists() and os.path.getsize(out) <= limit:
            return str(out)
    return None


def manual_email(row, sid, media, caption):
    """the reel file attached + caption with hashtags + first comment, to the owner's e-mail (Promo Hub). Never posts anything."""
    import base64
    import html as _h
    import promo
    st = manual_state()
    key = f"{PAGE}:{sid}"
    v = st.setdefault(key, {"first": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    try:
        reel = media.get("reel") or ""
        path = localmedia.get(reel) or (localmedia.download(reel, f"{sid}.mp4") if str(reel).startswith("http") else None)
        name = f"{PAGE.title()} 360"
        com = source_comment(row) if CONFIG.get("first_comment", False) else ""
        src = str(row.get("source") or "").strip()
        head = str(row.get("headline_ta") or sid)
        attach, note = None, "the reel video is attached to this e-mail"
        small = email_copy(path)      # owner 22 Nov: a 720p copy - the full reel is too big for an e-mail
        if small:
            attach = {"name": f"{PAGE}_{sid}.mp4", "type": "video/mp4", "data": base64.b64encode(Path(small).read_bytes()).decode()}
        else:
            note = "the reel video could not be attached (" + ("too large" if path else "not built") + ")"
        text = (f"Please post this news on {name} by hand - the page could not post it: {v.get('why') or 'not posted'}.\n\n"
                f"1. Video: {note}.\n\n2. Caption (copy all, hashtags included):\n\n{caption}\n\n"
                + (f"3. First comment (post it right after the reel):\n\n{com}\n\n" if com else "")
                + (f"Source: {src}\n" if src else "")
                + "\nAfter you post it, the automatic posting sees it on Instagram and will not post it again.")
        promo.hub_post("digest", {"subject": f"[{name} MANUAL POST] {sid} - {head}"[:180], "text": text,
                                  "html": "<pre style='white-space:pre-wrap;font-family:Arial,sans-serif;font-size:14px'>" + _h.escape(text) + "</pre>",
                                  "attachment": attach})
        v.update(sent=datetime.now(timezone.utc).isoformat(timespec="seconds"), day=datetime.now(IST).strftime("%Y-%m-%d"),
                 video=bool(attach), resent=bool(v.get("sent")))
        log("MANUAL POST e-mail sent:", PAGE, sid, "-", note)
    except Exception as e:
        v["tries"] = int(v.get("tries", 0)) + 1
        log("manual post e-mail not sent (tried again later):", str(e)[:200])
    manual_save(st)
    return [("manual", sid)]


def run_story(row):
    """every page named in post_to gets its own carousel + reel (own logo and follow line), one page after the other"""
    done = []
    for pg in pages_of(row):
        if page_done(row, pg):
            continue
        try:
            owner_reel = bool(json.loads(row.get("slides_spec") or "{}").get("ready_reel"))
        except Exception:
            owner_reel = False
        # owner-made reels (e-mailed) are posted without the duplicate check (owner decision, 24 Oct); own earlier half-post is not a duplicate
        dup = "" if (owner_reel or row.get(pg + "_link") or row.get("reel_link")) else ig_duplicate(row, pg)
        if dup:
            log("SKIP instagram duplicate:", row.get("story_id"), pg, "already posted", dup)
            continue
        if MANUAL and MANUAL_PAGE and pg != MANUAL_PAGE:      # owner 22 Nov: the manual-post e-mail is for this page only
            continue
        if limit_reached(pg) and not MANUAL:
            log("LIMIT: 24-hour Instagram post limit reached for", pg, "- ", row.get("story_id"), "waits")
            continue
        if not MANUAL and limit_reached(pg) is False and USED.get(pg, 0) >= SOFT_CAP and not is_urgent(row):
            log(f"CAP: {pg} already has {USED[pg]} posts in 24 h (cap {SOFT_CAP}) - only important news now,", row.get("story_id"), "waits")
            continue
        done += run_story_page(row, pg) or []
    return done


def run_ready_reel(row, page):
    """a reel video + caption made by the owner: post it as it is (after the Instagram duplicate check in run_story). No rebuild, no voice."""
    global PAGE, LOGO, TAG
    PAGE = page
    LOGO = KIT / f"logo_{PAGE}.png"
    TAG = "#Trichy360"
    sid = row["story_id"]
    if PREBUILD:
        return []
    if LABEL[page] in (row.get("reel_link") or ""):
        return []
    try:
        url = json.loads(row["images"])[0]
        # owner reels are posted as they are (owner decision, 24 Oct): no technical checks
        caption = (row.get("caption") or "").strip()     # the .md caption exactly as the owner wrote it
        if DRY:
            log("DRY RUN ready reel - not publishing", sid, url)
            bridge_post("posted", {"row": row["row"], "page": PAGE, "kind": "reel", "dry_run": True, "permalink": "", "media_urls": [url],
                                   "caption": caption, "voice": "ready-made", "collab": False, "checks": "ready reel"})
            return []
        if not still_needed(sid, PAGE, "reel"):
            log("ready reel no longer needed (sheet changed) - not publishing", sid, PAGE)
            return []
        token = bridge_get("token", page=PAGE)["token"]
        global COLLAB
        COLLAB = collab_page(row, PAGE)
        mid, link, collab_ok, why = publish_reel(token, url, caption, bool(COLLAB), "")
        log("ready reel posted", sid, link)
        record_posted(sid, row, link, "ready reel")      # owner 21 Nov: for the posted report
        try:
            publish_story(token, url, "video", row)
        except Exception as e:
            log("story not made (post itself is fine):", e)
        share_facebook(sid, "reel", [url], caption, row=row)
        bridge_post("posted", {"row": row["row"], "page": PAGE, "kind": "reel", "permalink": link, "media_id": mid, "media_urls": [url],
                               "caption": caption, "voice": "ready-made", "collab": False, "checks": "ready reel posted as received (owner verified; no duplicate check)"})
        first_comment(token, mid, sid, row)      # owner 21 Nov: the owner's own reel gets the source comment too (when its source is known)
        return [("reel", link)]
    except Exception as e:
        if is_limit_error(e):
            LIMIT[PAGE] = True
            log("LIMIT: Instagram post limit hit while posting ready reel", sid, "- waits, not a failure")
        else:
            log("ERROR ready reel", sid, e)
            bridge_post("error", {"row": row["row"], "page": PAGE, "kind": "reel", "error": str(e)[:900]})
    return []


def run_story_page(row, page):
    """Build the carousel and the reel, run every check, and only then publish (carousel first, then reel)."""
    global PAGE, LOGO, TAG
    import verify
    sid = row["story_id"]
    sys.path.insert(0, str(ROOT / "research_free"))
    import names      # full place names + spoken words for the voice, also for stories written earlier
    row["reel_script"] = names.spoken(row.get("reel_script") or "")
    row["caption"] = names.full_places(row.get("caption") or "")
    row["slides_spec"] = names.full_places(row["slides_spec"])
    try:      # owner 30 Oct: repairable known issues (card cut mid-phrase, a sentence said twice, a sentence about 'the article') are fixed, not lost
        import known_issues
        rep = known_issues.repair(row)
        if any(rep.get(k) != row.get(k) for k in ("reel_script", "caption", "slides_spec")):
            log("known issues repaired before posting")
        row.update({k: rep[k] for k in ("reel_script", "caption", "slides_spec") if rep.get(k)})
    except Exception as e:
        log("known-issue repair skipped:", e)
    spec = json.loads(row["slides_spec"])
    if spec.get("ready_reel"):
        return run_ready_reel(row, page)
    _digits_in_spec(spec)
    spec["date"] = tamil_date_today()  # date shown on poster/reel = actual posting date (IST)
    global LOC_ID
    LOC_ID = pick_location(row, spec) if CONFIG.get("location_tags", False) else ""
    if LOC_ID:
        log("location tag:", LOC_ID)
    # owner 25 Oct: text problems are fixed automatically, the story is never skipped for them
    clean_caption(row)      # fixes row['caption'] in place
    problems = check_text(row, spec)
    if problems:
        log("text fixed automatically:", "; ".join(problems))
    # the checked text of an earlier run (fact-check corrections + Tamil proofread) is reused, so a retry posts exactly the same words
    tc = CACHE / f"{sid}_{page}_text.json"
    text_done = False
    try:
        saved = json.loads(tc.read_text(encoding="utf-8"))
        row.update({k: saved[k] for k in ("headline_ta", "reel_script", "caption", "slides_spec") if saved.get(k)})
        spec = json.loads(row["slides_spec"])
        _digits_in_spec(spec)
        spec["date"] = tamil_date_today()
        text_done = True
        log("checked text of an earlier run reused")
    except Exception:
        pass
    if not DRY and not text_done:
        try:
            import factgate
            notes = factgate.check(row)      # second fact check: only problems a second model can prove from the article are returned
            if notes:
                # a confirmed false / invented detail is corrected first; the story is held only when it cannot be corrected
                # (a correct story is never stopped; FACTGATE_HOLD=0 = post anyway, as before 26 Oct)
                log("fact-check problems:", str(notes)[:300])
                fixed = factgate.fix(row, notes)
                if fixed:
                    row.update(fixed)
                    row["reel_script"] = names.spoken(row["reel_script"])
                    row["caption"] = names.full_places(row["caption"])
                    row["slides_spec"] = names.full_places(row["slides_spec"])
                    spec = json.loads(row["slides_spec"])
                    _digits_in_spec(spec)
                    spec["date"] = tamil_date_today()
                    clean_caption(row)
                    check_text(row, spec)
                    log("fact-check problems corrected automatically")
                elif os.environ.get("FACTGATE_HOLD", "1") != "0":
                    PAGE = page
                    return fail(row, "reel", "Fact check: could not correct " + "; ".join(notes)[:700])
                else:
                    log("fact-check problems not corrected (FACTGATE_HOLD=0, posting goes on)")
        except Exception as e:
            log("fact-check unavailable (posting goes on):", str(e)[:120])
    if not text_done:
        try:      # last Tamil spelling / grammar / sentence check of everything that goes out
            import tamilcheck
            if tamilcheck.proofread(row, log):
                spec = json.loads(row["slides_spec"])
                _digits_in_spec(spec)
                spec["date"] = tamil_date_today()
        except Exception as e:
            log("Tamil proofread failed (posting goes on):", str(e)[:120])
        try:
            if DRY:
                raise RuntimeError("test run: not saved (the real run fact-checks first)")
            CACHE.mkdir(parents=True, exist_ok=True)
            tc.write_text(json.dumps({k: row.get(k) for k in ("headline_ta", "reel_script", "caption", "slides_spec")}, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            log("checked text not saved:", e)
    PAGE = page
    LOGO = KIT / f"logo_{PAGE}.png"
    TAG = "#Trichy360"
    os.environ["PAGE_KEY"] = PAGE
    global COLLAB
    COLLAB = collab_page(row, PAGE)
    collab = bool(COLLAB)      # always False for Trichy 360 (no collaborator page)
    log(f"posting on {LABEL[PAGE]} with the {PAGE} logo" + (f", {LABEL[COLLAB]} invited as collaborator" if COLLAB else ""))
    caption = final_caption(row)
    global PROMO_NOW
    PROMO_NOW = None
    try:      # owner 20 Nov: an APPROVED promotion for this page today puts its ad on this reel (no hub / no promotion: nothing changes)
        import promo
        PROMO_NOW = promo.active_for(PAGE)
        if PROMO_NOW:
            caption = fit_caption(promo.with_line(caption, PROMO_NOW))      # the caption says it is an ad; its own cache key too
            log(f"promotion {PROMO_NOW.get('id')} ({PROMO_NOW.get('brand')}): its ad goes on this reel")
    except Exception as e:
        log("promotion check skipped:", str(e)[:150])
    work = OUT / sid
    key = cache_key(row, spec, caption)
    cached = None if PREBUILD else load_cache(sid, key)
    if PREBUILD and igdirect.ready(PAGE):      # owner 21 Nov: a page that sends files makes its reel right before posting
        log("prebuild skipped:", sid, "- this page sends its reels to Instagram as files (no Cloudinary copy is made ahead)")
        return []
    if cached:
        log("prebuilt carousel + reel found - publishing without rebuilding")
    images = [] if cached else fetch_images(row, work)
    need_carousel, need_reel = False, LABEL[PAGE] not in (row.get("reel_link") or "")      # Trichy 360: reel only, no carousel
    jpgs = mp4 = None
    reel_cover = None
    voice_file = None
    rs = None
    checks = []

    # 1. build everything (nothing is published yet)
    if cached:
        checks = list(cached.get('checks') or [])
    else:
        try:
            if need_reel:
                rs = reel_spec(row, spec, images)
            spec = verify.clean_obj(spec)      # owner 25 Oct: broken Tamil is cleaned, never a reason to skip
            if rs:
                rs = verify.clean_obj(rs)
            probs = verify.check_texts(spec, [sc.get("caption", "") for sc in (rs or {}).get("scenes", [])])
            if probs:
                log("Tamil text auto-cleaned:", "; ".join(probs)[:300])
                checks.append("Tamil text cleaned automatically")
            else:
                checks.append("Tamil text and fonts OK")
            if need_carousel:
                jpgs = render_carousel(row, spec, work)
                checks.append(f"{len(jpgs)} slides rendered, no clipped text")
            if need_reel:
                try:
                    if CONFIG.get("reel_design") == "v4":
                        raise RuntimeError("the v4 reel design always uses the voice model")
                    v = bridge_get("voice", story=sid)
                    if v.get("found"):
                        voice_file = work / f"voice{v.get('ext', '.m4a')}"
                        voice_file.write_bytes(base64.b64decode(v["data"]))
                        log("using recorded human voice", v.get("name"))
                except Exception as e:
                    log("voice lookup failed, using the voice model:", e)
                for shrink in range(4):      # owner 28 Oct: too long -> the script is shortened automatically, the story is never held for length
                    mp4 = render_reel(row, spec, images, work, voice_file)
                    probs = verify.check_reel(mp4, [x["say"] for x in rs["sentences"]] + [rs["outro"]["say"]])
                    dur = verify.reel_duration(mp4)
                    if not (probs and dur > 90 and not voice_file and all("outside 10-90" in p for p in probs)):
                        break
                    shorter, dropped = shorten_script_detail(row.get("reel_script") or "", 84.0 / dur)
                    if shorter == row.get("reel_script"):
                        break
                    log(f"reel {dur:.1f}s is longer than 90 s: script shortened from {len(row.get('reel_script') or '')} to {len(shorter)} characters")
                    for x in dropped:
                        log("   sentence moved to the caption only:", x[:120])
                    caption = add_to_caption(caption, dropped)      # owner 2 Nov: every fact stays available (the caption has the full news)
                    row["reel_script"] = shorter
                    rs = verify.clean_obj(reel_spec(row, spec, images))
                    checks.append(f"reel script shortened automatically (was {dur:.0f} s)")
                if probs:
                    return fail(row, "reel", "Reel check failed: " + "; ".join(probs))
                checks.append("reel 1080x1920, 10-90 s, voice present and fully pronounceable")
                cov = mp4.with_name(mp4.stem + "_cover.jpg")
                reel_cover = cov if cov.exists() else None
                if not reel_cover:
                    log("no cover image made, Instagram will pick a frame")
        except subprocess.CalledProcessError as e:
            return fail(row, "carousel", f"Build failed ({e.cmd[1].split('/')[-1]}, exit {e.returncode})")
        except Exception as e:
            return fail(row, "carousel", f"Build failed: {e}")
    checks.append("news marked verified: " + (row.get("verification") or "")[:60])
    note = "; ".join(checks)
    log("all checks passed:", note)

    # 1b. upload the finished files once and remember the links (a later run, or a retry after an Instagram error, publishes at once)
    if cached:
        media = cached
        caption = cached.get("caption") or caption      # a prebuilt long reel brings its extended caption
    else:
        media = {"carousel": [], "reel": "", "cover": "", "story": ""}
        try:
            if need_carousel and jpgs:
                media["carousel"] = [upload(j, "image") for j in jpgs]
                try:
                    media["story"] = upload(story_image(jpgs[0], work / "story_cover.jpg"), "image")
                except Exception as e:
                    log("story image not made (post itself is fine):", e)
            if need_reel and mp4:
                if not DRY and (MANUAL or igdirect.ready(PAGE)):      # owner 21 Nov: the file goes straight to Instagram / Facebook - no Cloudinary
                    media["reel"] = localmedia.ref(mp4)
                    media["cover"] = localmedia.ref(reel_cover) if reel_cover else ""      # uploaded only if the file cannot go directly
                else:
                    media["reel"] = upload(mp4, "video")
                    try:
                        media["cover"] = upload(reel_cover, "image") if reel_cover else ""
                    except Exception as e:
                        log("cover upload failed:", e)
            if str(media["reel"]).startswith("http") and (media["carousel"] or not need_carousel):
                save_cache(sid, key, dict(media, caption=caption), checks)      # owner 2 Nov: the caption that goes with THIS reel
        except Exception as e:
            return fail(row, "carousel", f"Upload failed: {e}")
    if PREBUILD:
        log("PREBUILT (not posted):", sid, "carousel", len(media["carousel"]), "slides, reel", bool(media["reel"]))
        return [("prebuilt", sid)]
    if MANUAL:      # owner 22 Nov: the page cannot post - the reel, caption and first comment go to the owner's e-mail instead
        return manual_email(row, sid, media, caption)

    # stagger: stories of one run are published SLOT_MIN minutes apart (account reach is better than a burst of posts)
    try:
        slot = float(os.environ.get("SLOT_MIN", "0") or 0)
    except ValueError:
        slot = 0
    wait_s = START + slot * 60 - time.time()
    if slot and not DRY and wait_s > 0:
        log(f"waiting {wait_s / 60:.0f} min for this story's posting slot")
        time.sleep(wait_s)

    # 2. upload and publish
    done = []
    voice = "recorded" if voice_file else "voice model"
    if need_carousel:
        try:
            urls = media["carousel"]
            if DRY:
                log("DRY RUN carousel - not publishing", urls)
                bridge_post("posted", {"row": row["row"], "page": PAGE, "kind": "carousel", "dry_run": True, "permalink": "",
                                       "media_urls": urls, "caption": caption, "slides": len(urls), "collab": collab, "checks": note})
                share_facebook(sid, "photos", urls, caption, dry=True, row=row)
            elif not still_needed(sid, PAGE, "carousel"):
                log("carousel no longer needed (sheet changed) - not publishing", sid, PAGE)
            else:
                token = bridge_get("token", page=PAGE)["token"]
                mid, link, collab_ok, why = publish_carousel(token, urls, caption, collab, (row.get('headline_en') or '')[:200] + ' - ' + PAGE_EN + ' news')
                log("carousel posted", sid, link)
                USED[PAGE] = USED.get(PAGE, 0) + 1
                bridge_post("posted", {"row": row["row"], "page": PAGE, "kind": "carousel", "permalink": link, "media_id": mid,
                                       "media_urls": urls, "caption": caption, "slides": len(urls), "collab": collab_ok, "checks": note})
                first_comment(token, mid, sid, row)      # owner 19 Nov: the source comment, after the post is recorded (as for reels)
                done.append(("carousel", link))
                try:
                    if media.get("story"):
                        publish_story(token, media["story"], "image", row)
                except Exception as e:
                    log("story image not made (post itself is fine):", e)
                fb = share_facebook(sid, "photos", urls, caption, row=row)
                if fb:
                    done.append(("facebook", fb))
        except Exception as e:
            if is_limit_error(e):
                LIMIT[PAGE] = True
                log("LIMIT: Instagram post limit hit while posting carousel", sid, "- waits, not a failure")
            elif is_transient(e):
                log("TEMPORARY Instagram problem while posting carousel", sid, "- tried again in the next run, not a failure:", str(e)[:200])
            else:
                log("ERROR carousel", sid, e)
                bridge_post("error", {"row": row["row"], "page": PAGE, "kind": "carousel", "error": str(e)[:900]})
    if need_reel:
        published = False
        try:
            url = media["reel"]
            if DRY:
                log("DRY RUN reel - not publishing", url)
                bridge_post("posted", {"row": row["row"], "page": PAGE, "kind": "reel", "dry_run": True, "permalink": "",
                                       "media_urls": [url], "caption": caption, "voice": voice, "collab": collab, "checks": note})
                share_facebook(sid, "reel", [url], caption, dry=True, row=row)
            elif not still_needed(sid, PAGE, "reel"):
                log("reel no longer needed (sheet changed) - not publishing", sid, PAGE)
            else:
                token = bridge_get("token", page=PAGE)["token"]
                cover_url = media.get("cover") or ""
                mid, link, collab_ok, why = publish_reel(token, url, caption, collab, cover_url)
                published = True
                log("reel posted", sid, link)
                record_posted(sid, row, link)      # owner 21 Nov: for the posted report
                if PROMO_NOW:      # owner 20 Nov: counted for the promotion's reels-a-day limit
                    import promo
                    promo.mark_used(PROMO_NOW, PAGE, sid)
                USED[PAGE] = USED.get(PAGE, 0) + 1
                bridge_post("posted", {"row": row["row"], "page": PAGE, "kind": "reel", "permalink": link, "media_id": mid,
                                       "media_urls": [localmedia.shown(url) or link], "caption": caption, "voice": voice, "collab": collab_ok, "checks": note,
                                       "quiet": posted_quiet()})
                done.append(("reel", link))
                first_comment(token, mid, sid, row)
                publish_story(token, url, "video", row)
                try:      # website OFF for now: website.send does nothing without WEBSITE_INGEST_KEY (a website problem never stops posting)
                    import website
                    website.send(row, link)
                except Exception as e:
                    log("website step skipped:", str(e)[:150])
                fb = share_facebook(sid, "reel", [url], caption, row=row, ig_media=mid)      # owner 21 Nov: waits if the gap is not over
                if fb:
                    done.append(("facebook", fb))
        except Exception as e:
            if published:      # owner 2 Nov (review): it IS on Instagram - never "tried again in the next run"
                log("ERROR after the reel was published (it is on Instagram, NOT posted again):", sid, str(e)[:200])
                print(f"::error title=Reel {sid} published but not fully recorded::{str(e)[:200]}", flush=True)
            elif is_limit_error(e):
                LIMIT[PAGE] = True
                log("LIMIT: Instagram post limit hit while posting reel", sid, "- waits, not a failure")
            elif is_transient(e):
                log("TEMPORARY Instagram problem while posting reel", sid, "- tried again in the next run, not a failure:", str(e)[:200])
            else:
                log("ERROR reel", sid, e)
                bridge_post("error", {"row": row["row"], "page": PAGE, "kind": "reel", "error": str(e)[:900]})
    return done


def fb_rank(row):
    """owner 11 Nov: Facebook gets only the top news - urgent, or a topic this page's insights rank best (research_free/learned.json)"""
    try:
        if json.loads(row.get("slides_spec") or "{}").get("ready_reel"):
            return {"urgent": False, "topic": "owner reel", "weight": 0, "best": True}      # the owner's own reel is always a top post
        sys.path.insert(0, str(ROOT / "research_free"))
        import learned
        head = str(row.get("headline_ta") or "")
        t = learned.topic(head)
        d = learned.load()
        ws = d.get("topic_weight") or {}
        best = set(d.get("best_topics") or sorted(ws, key=lambda k: -float(ws[k]))[:3])
        return {"urgent": bool(is_urgent(row)), "topic": t, "weight": round(learned.boost(head), 2), "best": t in best}
    except Exception as e:
        log("Facebook rank not read (treated as top news):", str(e)[:120])
        return None


def dashboard_status(ready_n=None):
    """owner 22 Nov: one small file per repo for the owner's private dashboard - what is posted today on Instagram / Facebook /
    YouTube, what waits and why, the manual to-do (manual-post and Facebook-share e-mails), gold rate and rasipalan. Never raises."""
    if not os.environ.get("GITHUB_ACTIONS"):
        return      # 22 Nov: only the posting job writes it (a local test run must not overwrite the real file)
    try:
        import facebook
        now = datetime.now(timezone.utc)
        day = now.astimezone(IST).strftime("%Y-%m-%d")
        day_utc = (now.astimezone(IST).replace(hour=0, minute=0, second=0, microsecond=0)).astimezone(timezone.utc).strftime("%Y%m%d-%H%M%S")
        out = {"updated": now.isoformat(timespec="seconds"), "day": day, "ready": ready_n, "pages": {}}
        man = manual_state()
        for pg in LABEL:
            posted = []
            for f in sorted(POSTED_DIR.glob(f"*-{pg}-*.json")) if POSTED_DIR.exists() else []:
                if f.name[:15] >= day_utc:
                    try:
                        r = json.loads(f.read_text(encoding="utf-8"))
                        posted.append({"id": r.get("story"), "head": r.get("headline", "")[:120], "link": r.get("link", ""), "at": r.get("at", ""),
                                       "kind": r.get("kind", "reel")})
                    except Exception:
                        pass
            fb = {"posted": 0, "waiting": 0, "share": [], "paused": ""}
            if facebook.creds(pg):
                fb["paused"] = facebook.paused(pg)
                for f in facebook.STATE.glob(f"{pg}-*.json") if facebook.STATE.exists() else []:
                    try:
                        d = json.loads(f.read_text(encoding="utf-8"))
                    except Exception:
                        continue
                    if str(d.get("updated", "")) < (now - timedelta(hours=24)).isoformat():
                        continue
                    stt = d.get("status")
                    if stt == "posted" and str(d.get("posted_at", "")) >= day_utc[:8]:
                        fb["posted"] += 1
                    elif stt == "waiting":
                        fb["waiting"] += 1
                    elif stt == "manual":
                        fb["share"].append({"id": d.get("story"), "head": str(d.get("caption") or "").split("\n")[0][:120],
                                            "link": d.get("ig_link", ""), "emailed": d.get("emailed", "")})
            else:
                fb["paused"] = "no Facebook token"
            todo = [{"id": k.split(":", 1)[1], "why": v.get("why", ""), "sent": v.get("sent", ""), "video": v.get("video", True)}
                    for k, v in man.items() if k.startswith(pg + ":") and v.get("sent") and v.get("day") == day]
            daily = {}
            for key, path in (("gold", ROOT / "goldrate" / "state" / f"posted_{pg}.json"), ("rasipalan", ROOT / "rasipalan" / "state" / f"{pg}.json")):
                try:
                    d = json.loads(path.read_text(encoding="utf-8"))
                    daily[key] = {"posted": d.get("date") == day, "link": d.get("permalink", "") if d.get("date") == day else ""}
                except Exception:
                    daily[key] = None
            yt = {"uploads": [], "keys": False}
            try:
                import ytupload
                yt["keys"] = bool(ytupload.keys(pg))
                yt["uploads"] = [u for u in ytupload._state(pg).get("uploads", []) if u.get("day") == day]
            except Exception:
                pass
            out["pages"][pg] = {"label": LABEL[pg], "instagram": {"posted": posted, "paused": ig_paused(pg),
                                                                  "quota": f"{USED.get(pg)}/{TOTAL.get(pg)}" if pg in TOTAL else ""},
                                "facebook": fb, "manual_post": todo, "daily": daily, "youtube": yt}
        (ROOT / "poster" / "dashboard_status.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception as e:
        log("dashboard status not written:", str(e)[:200])


def facebook_share_email(now=None):
    """owner 22 Nov ("Instagram posted, Facebook not - send me the link, I share it from Instagram"): a news that is on Instagram but
    still not on Facebook after 3 hours (waiting for the gap / Facebook limited the page / failed) goes to the owner's e-mail with
    its Instagram link and the steps; from then on it is the owner's (status 'manual' - never posted to Facebook automatically).
    ONE e-mail per page, at most every 3 hours, never at night. Never raises."""
    if DRY or quiet_now():
        return
    try:
        import facebook
        import promo
    except Exception:
        return
    now = now or datetime.now(timezone.utc)
    for pg in LABEL:
        try:
            if not facebook.creds(pg) or not facebook.STATE.exists():
                continue
            mark = facebook.STATE / f"_share_email_{pg}.json"
            try:
                last = datetime.fromisoformat(json.loads(mark.read_text(encoding="utf-8"))["at"])
                if now - last < timedelta(hours=1 if facebook.day_full(pg) else 3):      # owner 22 Nov: day's 15 done - every hour
                    continue
            except Exception:
                pass
            due = []
            for f in sorted(facebook.STATE.glob(f"{pg}-*.json")):
                try:
                    d = json.loads(f.read_text(encoding="utf-8"))
                    since = datetime.fromisoformat(d.get("waiting_since") or d.get("first_try") or d.get("updated"))
                except Exception:
                    continue
                stuck = d.get("status") == "waiting" or (d.get("status") == "failed" and int(d.get("tries", 0)) >= facebook.MAX_TRIES)
                full = facebook.day_full(pg)      # owner 22 Nov: once the day's 15 are on Facebook, the rest goes to the e-mail at once
                if stuck and d.get("ig_media") and (full or timedelta(hours=3) <= now - since) and now - since <= timedelta(hours=24):
                    due.append((f, d))
            if not due:
                continue
            token = bridge_get("token", page=pg)["token"]
            items = []
            for f, d in due[:15]:
                try:
                    link = ig("GET", d["ig_media"], token, fields="permalink").get("permalink", "")
                except Exception:
                    link = ""
                if not link:
                    continue
                head = str(d.get("caption") or d.get("story") or "").split("\n")[0][:120]
                items.append((head, link))
                d.update(status="manual", why="e-mailed to the owner to share from Instagram", emailed=now.isoformat(timespec="seconds"), ig_link=link)
                f.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
            if not items:
                continue
            name = f"{pg.title()} 360"
            steps = ("How to share each one to Facebook (1 minute each):\n"
                     "1. Open the Instagram link below in the Instagram app (on the " + name + " account).\n"
                     "2. Tap the 3 dots (...) on the reel.\n"
                     "3. Tap 'Share to' / 'Share to Facebook' and choose the " + name + " Facebook page.\n"
                     "4. Tap Share. (Space them out - a few minutes between each.)\n")
            lines = [f"{i}. {h}\n   {l}" for i, (h, l) in enumerate(items, 1)]
            text = (f"These {len(items)} news are on {name} Instagram but not on its Facebook page "
                    f"(the day's {facebook.TOP_PER_DAY} Facebook posts are done, or Facebook was waiting / limited the page).\n\n{steps}\n" + "\n".join(lines)
                    + "\n\nThe automatic Facebook posting will not post these again.")
            import html as _h
            promo.hub_post("digest", {"subject": f"[{name} FACEBOOK SHARE] {len(items)} news to share from Instagram", "text": text,
                                      "html": "<pre style='white-space:pre-wrap;font-family:Arial,sans-serif;font-size:14px'>" + _h.escape(text) + "</pre>"})
            mark.write_text(json.dumps({"at": now.isoformat(timespec="seconds"), "count": len(items)}), encoding="utf-8")
            log(f"Facebook share e-mail {pg}: {len(items)} news (Instagram links) sent to the owner")
        except Exception as e:
            log(f"Facebook share e-mail {pg} skipped:", str(e)[:200])


def facebook_catchup():
    """owner 21 Nov ("Facebook also posts all the news Instagram posts"): a news that came within the Facebook gap waits
    (poster/fb_posted status 'waiting'); here, in every posting check, the oldest one per page goes out once the gap has passed -
    its video is read back from the Instagram post (no Cloudinary) and sent to Facebook as a file. Never raises."""
    if DRY or quiet_now():
        return
    try:
        import facebook
    except Exception:
        return
    for pg in LABEL:
        try:
            if not facebook.creds(pg):
                continue
            d = facebook.next_waiting(pg)
            if not d:
                continue
            why = facebook.gate(pg, d.get("rank"))      # owner 22 Nov: the waiting news' own priority (urgent may pass the gap)
            if why:
                log(f"Facebook catch-up {pg}: {d.get('story')} still waits ({why})")
                continue
            token = bridge_get("token", page=pg)["token"]
            url = (ig("GET", d["ig_media"], token, fields="media_url") or {}).get("media_url")
            path = localmedia.download(url, "facebook.mp4") if url else None
            if not path:
                d["tries"] = int(d.get("tries", 0)) + 1
                facebook._save(pg, d["story"], d.get("kind", "reel"), d)
                log(f"Facebook catch-up {pg}: the video of {d.get('story')} could not be read (try {d['tries']})")
                continue
            log(f"Facebook catch-up {pg}: {d.get('story')} goes to Facebook now (waited since {str(d.get('waiting_since'))[:16]} UTC)")
            facebook._attempt(pg, d["story"], d.get("kind", "reel"), [localmedia.ref(path)], d.get("caption", ""), d,
                              d.get("with_story", True), d.get("link", ""), d.get("comment", ""))
        except Exception as e:
            log(f"Facebook catch-up {pg} skipped:", str(e)[:200])


def share_facebook(sid, kind, media, caption, dry=False, row=None, ig_media=""):
    """owner 2 Nov: Instagram posts also go to this page's Facebook page with a story; owner 11 Nov: only the top news (fb_rank),
    with the article link. kind 'reel' or 'photos'. Never raises - Instagram is never touched."""
    try:
        import facebook
        src = str((row or {}).get("source") or "").strip()
        com = source_comment(row) if row and CONFIG.get("first_comment", False) else ""      # owner 20 Nov: the Instagram first comment
        return facebook.share(PAGE, sid, kind, media, caption, TAG, dry=dry, rank=fb_rank(row) if row else None,
                              source_link=src if src.startswith("http") else "", comment=com, ig_media=ig_media)
    except Exception as e:
        log("Facebook step skipped:", str(e)[:150])
        return ""


def live_allowed():
    if DRY:
        return True
    if os.environ.get("GITHUB_EVENT_NAME") == "schedule" and not (ROOT / "LIVE").exists():
        log("Not live yet (no LIVE file in the repository) - scheduled posting is switched off.")
        return False
    return True


def missing_setup():
    for name, val in (("BRIDGE_URL", BRIDGE_URL), ("BRIDGE_KEY", BRIDGE_KEY), ("CLOUDINARY_CLOUD", CLOUD), ("CLOUDINARY_PRESET", PRESET)):
        if not val:
            log(f"Setup not finished: secret {name} is missing - nothing to do.")
            return True
    return False


def auto_images():
    """stories without a picture: exactly ONE new AI picture per story (free first - Cloudflare, NVIDIA - then FAL, inside
    imagegen.generate; earlier pictures are never reused); if no model works, the reel is made without pictures (setImages with NOIMAGE).
    Credit guard: at most 40 images per run."""
    pend = bridge_get("autoPending").get("rows", [])
    if pend and not all(r.get("source") for r in pend):      # owner 2 Nov (review): the Apps Script list has no article link -
        try:                                                  # without it the real photo step never ran (AI pictures every time)
            srcs = {x.get("story_id"): x.get("source") for x in bridge_get("queue").get("rows", [])}
            for r in pend:
                r["source"] = r.get("source") or srcs.get(r.get("story_id")) or ""
        except Exception as e:
            log("article links for the real photos not read:", str(e)[:120])
    if not pend:
        return
    budget = time.time() + int(os.environ.get("AUTO_IMG_SECONDS", "420"))      # the check job must finish; the rest waits for the next run
    giveup_h = float(os.environ.get("AUTO_IMG_GIVEUP_H", "0.5"))      # owner 29 Oct: free first, then FAL; if even FAL fails for 30 min, the plain background (urgent news never waits 3 h)
    sys.path.insert(0, str(ROOT / "research_free"))
    import imagegen
    cap = int(os.environ.get("IMG_MAX_PER_RUN", "40"))
    made_total = 0
    for r in pend:
        prompts = [p.strip() for p in str(r.get("prompts", "")).split("\n---\n") if p.strip()][:int((CONFIG.get("free_images") or {}).get("pictures_per_reel", 1))]      # owner 30 Oct: 2 per reel
        if not prompts:
            continue
        if time.time() > budget:
            log("auto images: time for this run used up, the rest waits for the next run")
            break
        if made_total + len(prompts) > cap:
            log("auto images: credit cap reached for this run, the rest waits for the next run")
            break
        work = OUT / r["story_id"]
        work.mkdir(parents=True, exist_ok=True)
        try:      # owner 31 Oct: the source article's own relevant photo first (enhanced when small); else the AI pictures below
            import realphoto
            pics, credit = realphoto.for_story(r.get("source") or "", r.get("headline_en") or "", n=len(prompts), log=log)
            if pics:
                urls = []
                for k, b in enumerate(pics, 1):
                    f = work / f"real_{k}.jpg"
                    f.write_bytes(b)
                    urls.append(upload(f, "image"))
                bridge_post("setImages", {"row": r["row"], "story_id": r["story_id"], "images": urls})
                log("real photos queued:", r["story_id"], len(urls), credit)
                continue
            if getattr(realphoto, "NEEDS_RETRY", [False])[0] and age_hours(r) < float(CONFIG.get("real_photo_wait_hours", 2)):
                log("real photo check out of free quota - the article's photo is tried again next run (no AI pictures yet):", r["story_id"])
                continue      # owner 2 Nov (review): one Gemini 429 used to replace the real photo with AI art for good
        except Exception as e:
            log("real photo step skipped:", r.get("story_id"), str(e)[:120])
        try:
            urls = []
            for k, pr in enumerate(prompts, 1):
                data = None
                last_err = None
                for attempt in range(3):      # owner 25 Oct: a picture that does not show the news is generated again (up to 3 times)
                    try:
                        cand = imagegen.generate(pr[:1800], seed=k + 7 + attempt * 13)      # free models first (order inside imagegen)
                    except Exception as e:
                        last_err = e
                        log("image attempt", attempt + 1, "failed:", str(e)[:140])
                        time.sleep(20 * (attempt + 1))
                        continue
                    data = cand
                    if imagegen.matches(cand, r.get("headline_en") or ""):
                        break
                    log("picture does not match the news, generating again:", r.get("story_id"), k)
                if data is None:
                    if urls:      # owner 30 Oct: the cover (and any picture already made) is kept - only the extra picture is missing
                        log("picture", k, "not made for", r.get("story_id"), "- the reel uses the", len(urls), "made:", str(last_err)[:120])
                        break
                    raise RuntimeError(str(last_err))
                f = work / f"auto_{k}.jpg"
                f.write_bytes(data)
                urls.append(upload(f, "image"))
            made_total += len(prompts)
            bridge_post("setImages", {"row": r["row"], "story_id": r["story_id"], "images": urls})
            log("automatic images queued:", r["story_id"], len(urls))
        except Exception as e:
            if age_hours(r) < giveup_h:      # image models down for a while (credits / rate limit): tried again in the next run
                log("image models failed for", r["story_id"], str(e)[:160], f"- tried again in the next run (gives up after {giveup_h:g} h)")
                continue
            log("image models failed for", r["story_id"], str(e)[:160], "- the reel is made without pictures")
            bridge_post("setImages", {"row": r["row"], "story_id": r["story_id"], "images": ["NOIMAGE"]})


def plain_background(work, n, row=None):
    """owner 20 Nov: a reel with no picture gets a designed, realistic background (poster/newsbg.py: night-city lights coloured by the
    kind of news) - never the page logo. One file, used for every scene."""
    import newsbg
    work.mkdir(parents=True, exist_ok=True)
    return [newsbg.make(row, work / "plain_bg.jpg")] * n


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "run"
    if missing_setup() or not live_allowed():
        n = 0
        rows = []
    else:
        try:
            if mode == "check" and not PREBUILD and not DRY:      # once per cycle; the 12 posting jobs used to make the same pictures 12 times
                auto_images()
        except Exception as e:
            log("automatic images step failed (posting goes on):", e)
        rows = bridge_get("queue")["rows"]
        global ALL_ROWS
        ALL_ROWS = list(rows)
        try:      # recent rows of the Sheet (already posted ones included) so the same news is never posted twice
            ALL_ROWS += [r for r in bridge_get("recent").get("rows", []) if r.get("story_id") not in {x.get("story_id") for x in rows}]
        except Exception as e:
            log("recent rows not available (duplicate check uses the queue only):", e)
        n = len(pick_all(rows))
    if mode == "check":
        story_catchup()      # owner 1 Nov: no post without its story
        facebook_catchup()      # owner 21 Nov: every news that is on Instagram also goes to Facebook
        facebook_share_email()      # owner 22 Nov: still not on Facebook after 3 h - the Instagram link to the owner
        try:      # owner 21 Nov: the day's best news reels also go to the page's YouTube channel (only with its YT_* keys)
            import ytupload
            ytupload.catchup(sys.modules[__name__])
        except Exception as e:
            log("YouTube upload skipped:", str(e)[:150])
        log(f"{len(rows)} stories in the queue, ready to post: {n}")
        dashboard_status(n)      # owner 22 Nov: the owner's private dashboard reads poster/dashboard_status.json
        if rows:
            log("  keys:", sorted(rows[0].keys()))
        for r in rows:
            log("  ", r.get("story_id"), "review=", repr(r.get("review")), "images=", len(r.get("images") or ""),
                "spec=", len(r.get("slides_spec") or ""), "pages=", pages_of(r), "links=", repr(r.get("trichy_link")), repr(r.get("reel_link")),
                "age_h=", round(age_hours(r), 1), "ready=", ready(r), "set_started=", set_started(r))
        out = os.environ.get("GITHUB_OUTPUT")
        if out:
            with open(out, "a") as f:
                if PREBUILD:   # prebuild: every waiting story, built at once, nothing published
                    ids = [r["story_id"] for r in pick_all(rows)] if n else []
                    f.write(f"ready={1 if n else 0}\n")
                    f.write("matrix=" + json.dumps({"include": [{"story": i, "slot": 0} for i in ids]}) + "\n")
                else:
                    full = {p for p in PAGES if n and limit_reached(p)}
                    if full:
                        log("Instagram 24-hour limit reached for", sorted(full), "- their stories wait (nothing is dropped)")
                    # owner 2 Nov (review): a reel AND its Instagram story both count in the 50 posts of 24 h
                    per_story = 2 if CONFIG.get("post_stories", True) else 1
                    left = {p: TOTAL[p] - USED[p] for p in TOTAL if p in USED}      # posts this page may still make in the 24-hour window
                    # owner 2 Nov (review): no bursts and no hour-long runs - one story per page per run, at least spacing_min after
                    # the page's last post; the next run (every few minutes) posts the next one. Urgent news never waits.
                    spacing = float((CONFIG.get("posting") or {}).get("spacing_min", 12))
                    ids, waiting, slots = [], [], {}
                    for r in (pick_all(rows) if n else []):
                        todo = [p for p in pages_of(r) if not page_done(r, p)]
                        # owner 11 Nov: the post job skips news already on Instagram but nothing records it, so the check chose the
                        # same 3 (RN-220/236/295) every 5 minutes from 6 Nov and the 41 others waited - the same test runs here first
                        dups = [p for p in todo if _ig_dup_for_check(r, p)]
                        if todo and len(dups) == len(todo):
                            log("  ", r["story_id"], "skipped: already on Instagram", dups)
                            continue
                        ps = per_story if wants_story(r) else 1      # owner 14 Nov: no story share = 1 post for this news
                        pg = [p for p in todo if p not in full and left.get(p, ps) >= ps
                              and (is_urgent(r) or USED.get(p, 0) < SOFT_CAP)]      # owner 2 Nov (review): over the cap only urgent news
                        if todo and not pg:
                            log("  ", r["story_id"], "waits: Instagram's 24-hour post limit is (almost) used on", todo)
                            continue
                        why = prime_wait(r)
                        if pg and why:
                            waiting.append(r["story_id"]); log("  ", r["story_id"], why)
                            continue
                        if not pg:
                            continue
                        # owner 19 Nov: spacing_min 0 = no gap - every ready news of the window posts at once
                        busy = [] if spacing <= 0 else [p for p in pg if p in slots or minutes_since_last_post(p) < spacing]
                        if busy and not is_urgent(r):
                            waiting.append(r["story_id"])
                            log("  ", r["story_id"], f"waits for the {spacing:.0f}-minute gap after the last post on {busy}")
                            continue
                        k = 0 if spacing <= 0 else max([slots.get(p, -1) for p in pg]) + 1      # urgent news of one run: 6 minutes apart
                        ids.append((r["story_id"], k * 6))
                        for p in pg:
                            slots[p] = k
                            left[p] = left.get(p, 99) - per_story
                        if len(ids) >= 12:
                            break
                    inc = [{"story": i, "slot": sl, "prebuild": ""} for i, sl in ids]
                    try:      # owner 22 Nov: news a page cannot post go to the owner's e-mail, one by one, for a manual post
                        inc += [{"story": s, "slot": 0, "prebuild": "", "manual": "1", "page": p}
                                for s, p in manual_due(rows, {i for i, _ in ids})]
                    except Exception as e:
                        log("manual post list skipped:", str(e)[:150])
                    ids = [i for i, _ in ids]
                    # stories whose set has not started yet: make the carousel/reel ahead, so they go out the moment it starts
                    urgent = set(ids)
                    pre = [r["story_id"] for r in rows if ready(r) and r["story_id"] not in urgent and (not set_started(r) or r["story_id"] in waiting) and not all(cache_path(r["story_id"], p).exists() for p in pages_of(r) if not page_done(r, p)) and not all(igdirect.cached_ok(p) for p in pages_of(r) if not page_done(r, p))][:12]      # waiting reels are made ahead, so they go out the minute prime time starts
                    inc += [{"story": i, "slot": 0, "prebuild": "1"} for i in pre]
                    if pre:
                        log("prebuilding ahead of the set start:", pre)
                    f.write(f"ready={1 if inc else 0}\n")
                    f.write("matrix=" + json.dumps({"include": inc}) + "\n")
        return
    want = sys.argv[2] if len(sys.argv) > 2 else ""
    row = next((r for r in (rows if PREBUILD else pick_all(rows)) if r.get("story_id") == want and (not PREBUILD or ready(r))), None) if want else pick(rows)
    if not row:
        log("no story with images is waiting")
        return
    log("->", row["story_id"], row.get("headline_ta"))
    done = run_story(row)
    log("finished:", done or "nothing posted")




def _real_numbers(problem):
    """owner 2 Nov: 'numbers not found in the article: 02' was only the caption's date line ('📍 இடம் | 02 நவம்பர் 2026') - every story
    written on 1-9 Nov was held. A zero-padded day (01-09) or '000' is not a stray number; the others still hold the story."""
    m = re.match(r"(numbers not found in the article:\s*)(.*)$", problem)
    if not m:
        return problem
    left = [n.strip() for n in m.group(2).split(",") if n.strip() and not re.fullmatch(r"0+|0[1-9]", n.strip())]
    return m.group(1) + ", ".join(left) if left else ""


_ARTICLE_TEXT = {}


def _location_still_wrong(row, problem):
    """owner 2 Nov (RN-284 'பரமத்தி வேலூர்' vs the article's 'ப.வேலுார்'): a 'location not in the article' note saved before the check was
    fixed is judged again against the article with today's check. Article not readable -> the note stands (held)."""
    if not problem.startswith("not grounded: location"):
        return True
    src = str(row.get("source") or "").strip()
    if not src.startswith("http"):
        return True
    try:
        sys.path.insert(0, str(ROOT / "research_free"))
        import allnews, validate
        if src not in _ARTICLE_TEXT:
            _ARTICLE_TEXT[src] = ""      # a failed fetch is remembered too: ready() asks ~4 times per check
            _ARTICLE_TEXT[src] = allnews.article_any(src).get("text") or ""
        art = _ARTICLE_TEXT[src]
        if len(art) < 200:
            return True
        sp = json.loads(row.get("slides_spec") or "{}")
        now = [p for p in validate.grounding_problems({"slides_spec": sp, "tamil_headline": "", "reel_script": "", "caption": ""}, art)
               if p.startswith("not grounded: location")]
        if not now:
            log("hold lifted:", row.get("story_id"), "-", problem[:80], "- the location IS in the article (checked again)")
        return bool(now)
    except Exception as e:
        log("location re-check failed (stays held):", row.get("story_id"), str(e)[:80])
        return True



_TA_SMALL = {1: ("ஒன்று", "ஒரு "), 2: ("இரண்டு", "இரு "), 3: ("மூன்று",), 4: ("நான்கு",), 5: ("ஐந்து",), 6: ("ஆறு",), 7: ("ஏழு",),
             8: ("எட்டு",), 9: ("ஒன்பது",), 10: ("பத்து",)}


def _number_in_article(n, art):
    """owner 3 Nov: the article writes many numbers in words or with commas ('10 ஆயிரம்', '1,000', 'ஆறு') - those are in the article"""
    if not art or not n.isdigit():
        return False
    v = int(n)
    forms = {f"{v:,}"}
    if v % 1000 == 0 and v < 100000:
        forms |= {f"{v // 1000} ஆயிரம்", f"{v // 1000}ஆயிரம்"} | ({"ஆயிரம்"} if v == 1000 else set())
    if v % 100000 == 0:
        forms |= {f"{v // 100000} லட்சம்", f"{v // 100000}லட்சம்"} | ({"லட்சம்"} if v == 100000 else set())
    if v in _TA_SMALL:
        forms |= set(_TA_SMALL[v])
    return any(f in art for f in forms)


def _numbers_still_missing(row, problem):
    """a 'numbers not found' note is judged again against the article: numbers it writes in words / with commas are dropped"""
    m = re.match(r"(numbers not found in the article:\s*)(.*)$", problem)
    if not m:
        return problem
    art = _article_text(row)
    if not art:
        return problem
    left = [n.strip() for n in m.group(2).split(",") if n.strip() and not _number_in_article(n.strip(), art)]
    return m.group(1) + ", ".join(left) if left else ""


def _article_text(row):
    src = str(row.get("source") or "").strip()
    if not src.startswith("http"):
        return ""
    try:
        sys.path.insert(0, str(ROOT / "research_free"))
        import allnews
        if src not in _ARTICLE_TEXT:
            _ARTICLE_TEXT[src] = ""
            _ARTICLE_TEXT[src] = allnews.article_any(src).get("text") or ""
        return _ARTICLE_TEXT[src]
    except Exception:
        return ""


def _town_in_story(row):
    """owner 3 Nov: a story written before the town fix may have 'district' alone as location while its own headline / text names
    the town - that story is fine"""
    try:
        sys.path.insert(0, str(ROOT / "research_free"))
        import allnews
        return bool(allnews.places_in(" ".join(str(row.get(k) or "") for k in ("headline_ta", "caption", "reel_script"))))
    except Exception:
        return False

def news_hold(row):
    """owner 2 Nov (RN-272): a story with any fact-check problem, or whose location is unknown or only a district, is held"""
    v_ = str(row.get("verification") or "")
    if "NOT CLEAN" in v_:
        # owner 2 Nov: only FACTUAL problems hold a story; formatting-only flags (word count, line length, cut-off slide text) do not
        probs_ = v_.split("problems:", 1)[1] if "problems:" in v_ else v_
        facts_ = [p.strip() for p in probs_.split("; ") if re.search(r"fact-check|numbers not found|not grounded|invented|made up|wrong|contradict", p, re.I)]      # owner 2 Nov: "caption misses facts" is a missing detail, not a wrong fact - it posts
        # owner 3 Nov: a "fact-check:" flag about cut-off text, line length or word count is formatting, not a wrong fact - it posts
        facts_ = [p for p in facts_ if not re.search(r"cut off|mid-sentence|mid-phrase|longer than|too long|too short|characters|\d+ words|word count|incomplete sentence|ends abruptly|sentence fragment|incomplete|ungrammatical|unclear|awkward|spelling|grammar", p, re.I)]
        # 4 Nov (RN-334): the checker itself says the point is fine ("- acceptable", "not an error") - that is a note, not a problem
        facts_ = [p for p in facts_ if not re.search(r"[-—–,;:(]\s*(so\s+)?(acceptable|this is acceptable|is fine|not an error|not a problem|no (real )?(issue|problem)|ok)\.?\)?\s*$", p, re.I)]
        facts_ = [f for f in (_real_numbers(p) for p in facts_) if f]
        facts_ = [f for f in (_numbers_still_missing(row, p) for p in facts_) if f]
        # owner 3 Nov (RN-151): the district / city name itself (திருச்சிராப்பள்ளி vs the article's திருச்சி) is not an invented place
        facts_ = [p for p in facts_ if not re.match(r"not grounded: place word '(திருச்சிராப்பள்ளி|திருச்சி|நாமக்கல்|ராசிபுரம்)[^']*'", p)]
        facts_ = [f for f in facts_ if _location_still_wrong(row, f)]
        if facts_:
            return "held: fact-check problems - " + "; ".join(facts_)[:200]
    loc_ = str(row.get("location") or "").strip()
    if re.fullmatch(r"[^,]*\b(district|மாவட்டம்)\.?", loc_, re.I) and not _town_in_story(row):      # a district alone is not a place
        return "held: location is only the district - the town from the article is missing"
    txt_ = " ".join([str(row.get("caption") or ""), str(row.get("reel_script") or "")])
    if loc_.lower() in ("unknown", "தெரியவில்லை") or re.search(r"இடம்\W*தெரியவில்லை|Location unknown", txt_, re.I):
        return "held: location unknown"
    return ""


def skip_reason(row):
    """owner 2 Nov (RN-272): the usual checks first, then the news hold"""
    why = _skip_reason_base(row)
    return why or news_hold(row) or change_hold(row)


def change_hold(row):
    """owner 11 Nov: a power-cut cancellation / postponement is posted ONLY when this page posted that power cut before"""
    import freshness
    head = " ".join(str(row.get(k) or "") for k in ("headline_ta", "headline_en"))
    if not freshness.cut_change(head):
        return ""
    known = False
    for pg in pages_of(row):
        recent = ig_recent(pg)
        known = known or bool(recent)
        if any(freshness.change_of_posted(head, cap.strip().split("\n")[0]) for _, cap in recent):
            return ""
    if not known:
        return ""      # Instagram could not be read: never block on missing data
    return "skipped: a power-cut cancellation / change, but that power cut was never posted on this page"

if __name__ == "__main__":
    main()
