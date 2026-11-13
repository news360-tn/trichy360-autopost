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
import localmedia      # owner 12 Nov: direct reel upload (OFF unless DIRECT_UPLOAD=1)
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
                log(f"bridge 'posted' failed (try {k + 1}):", str(e)[:150])
                time.sleep(15 * (k + 1))
    return _bridge_post(action, payload)


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


def prime_urgent(row):
    """time-sensitive news (power cut, accident, rain warning, Collector / Govt notice, jobs, exam, today / tomorrow) never waits"""
    return bool(URGENT.search(f"{row.get('headline_ta', '')} {row.get('headline_en', '')} {row.get('category', '')}"))


def in_prime_time(now=None):
    now = now or datetime.now(IST)
    hm = now.strftime("%H:%M")
    return any(a <= hm < b for a, b in (CONFIG.get("prime_time") or {}).get("windows", []))


def prime_wait(row, now=None):
    """'' = post now. Otherwise why this reel waits (a high-view window is coming). Urgent news and reels that have already
    waited max_wait_hours never wait, so every news still goes out."""
    pt = CONFIG.get("prime_time") or {}
    if not pt.get("enabled") or prime_urgent(row) or is_urgent(row) or in_prime_time(now):
        return ""
    waited = age_hours(row)
    if waited is not None and waited >= float(pt.get("max_wait_hours", 12)):
        return ""
    nxt = next((a for a, b in sorted(pt.get("windows", [])) if a > (now or datetime.now(IST)).strftime("%H:%M")), (pt.get("windows") or [["09:00"]])[0][0])
    return f"waits for prime time ({nxt} IST)"


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


def source_credit(row):
    """(short for the reel header, full line for the end card / caption) - ('', '') when the source site is unknown"""
    names = source_names(row)
    if not names:
        return "", ""
    pre = "மின்வாரிய அறிவிப்பு • " if is_shutdown(row) and "மின்வாரியம்" not in names else ""
    day = ""
    try:
        d = datetime.fromisoformat(str(row.get("published") or "").replace("Z", "+00:00"))
        day = f"{d.day} {TAMIL_MONTHS[d.month - 1]} {d.year}"
    except Exception:
        pass
    full = pre + ", ".join(names) + (f" ({day})" if day else "")
    short = {"The New Indian Express": "Indian Express", "Times of India": "TOI", "நியூஸ்18 தமிழ்": "நியூஸ்18", "நியூஸ்7 தமிழ்": "நியூஸ்7"}
    return short.get(names[0], names[0]), full      # the reel header has little room - the end card / caption carry the full name


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
    return cap


# ---------------------------------------------------------------- images
def fetch_images(row, work):
    """Trichy 360: ONE picture per reel (the reel makes its scenes from different moves / crops of it)"""
    urls = json.loads(row["images"])[:int((CONFIG.get("free_images") or {}).get("pictures_per_reel", 1))]      # owner 30 Oct: 2 per reel
    work.mkdir(parents=True, exist_ok=True)
    if urls and urls[0] == "NOIMAGE":
        return plain_background(work, 1)
    out = []
    for i, u in enumerate(urls, 1):
        r = requests.get(u, timeout=120)
        r.raise_for_status()
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
    sents = [s.strip() for s in re.split(r"(?<=[.!?\u0964])\s+", (txt or "").strip()) if s.strip()]
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
    sentences = [s.strip() for s in re.split(r"(?<=[.!?।])\s+", txt) if s.strip()]
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
    if kind == "video" and localmedia.enabled():
        localmedia.remember(link, path)      # the direct upload sends this file instead of the link
    return link


def cache_key(row, spec, caption):
    import hashlib
    raw = json.dumps([row.get("reel_script"), row.get("slides_spec"), caption, row.get("images"), spec.get("date"), row.get("post_to")]
                     + ["reel-r5"], ensure_ascii=False)      # r2 (27 Oct): reels built before the <b>-tag fix are made again
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


def ig_url(path):
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
        return ig("POST", f"{uid}/media", token, **extra, **p)["id"]

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


IG_RUPLOAD = "https://rupload.facebook.com/ig-api-upload/{}/{}"


def _ig_direct(uid, token, prm, path, collab):
    """owner 12 Nov: Instagram container with upload_type=resumable, then the FILE is sent (no Cloudinary download).
    Raises on any problem - the caller then uses the old video_url method."""
    global IG_VER
    p = {k: v for k, v in prm.items() if k != "video_url"}
    p["upload_type"] = "resumable"
    ver = IG_VER or os.environ.get("IG_UPLOAD_VER", "v26.0")
    old_ver = IG_VER
    IG_VER = ver      # 12 Nov (Salem RN-1): the unversioned API said "video_url is required" - resumable needs a versioned call
    try:
        cid, collab_ok, why = create_with_collab(uid, token, p, collab)
    finally:
        IG_VER = old_ver
    localmedia.send(IG_RUPLOAD.format(ver, cid), token, path)
    return cid, collab_ok, why


def publish_reel(token, video_url, caption, collab, cover_url=""):
    uid, _ = ig_account(token)
    prm = dict(media_type="REELS", video_url=video_url, caption=caption, share_to_feed="true")
    if cover_url:
        prm["cover_url"] = cover_url   # chosen cover photo (sharp frame with the hook headline)
    path = localmedia.get(video_url)      # None unless DIRECT_UPLOAD=1 (then: the file, made here or downloaded once)
    if path:
        cid = None
        try:
            cid, collab_ok, why = _ig_direct(uid, token, prm, path, collab)
            wait_ready(cid, token, 15)
        except Exception as e:
            log("direct upload not used - posting with the link as before:", str(e)[:200])
            cid = None
        if cid:      # the file is on Instagram: publish it; from here on NO fallback (a reel is never posted twice)
            mid = ig("POST", f"{uid}/media_publish", token, creation_id=cid)["id"]
            log("reel sent as a file (direct upload)")
            try:
                link = ig("GET", mid, token, fields="permalink").get("permalink", "")
            except Exception:
                link = ""
            return mid, link, collab_ok, why
    try:
        cid, collab_ok, why = create_with_collab(uid, token, prm, collab)
    except RuntimeError as e:
        if not cover_url:
            raise
        log("reel refused with the cover, posting with Instagram's own cover:", e)
        prm.pop("cover_url", None)
        cid, collab_ok, why = create_with_collab(uid, token, prm, collab)
    wait_ready(cid, token, 15)
    mid = ig("POST", f"{uid}/media_publish", token, creation_id=cid)["id"]
    return mid, ig("GET", mid, token, fields="permalink").get("permalink", ""), collab_ok, why


FIRST_COMMENTS = [
    "இந்த செய்தி உங்களுக்கு பயனுள்ளதா? தேவைப்படும் நண்பர்களுக்கு Share செய்யுங்கள் 🙏",
    "உங்கள் பகுதியில் இதன் நிலை என்ன? கமெண்டில் சொல்லுங்கள் 👇",
    SAVE_LINE,
]


def first_comment(token, media_id, sid, k=0):
    """the page's own first comment (a question / share prompt, no hashtags) to start the conversation. Never raises."""
    try:
        if not CONFIG.get("first_comment", False) or not media_id:
            return
        msg = FIRST_COMMENTS[(sum(map(ord, sid)) + k) % len(FIRST_COMMENTS)]
        ig("POST", f"{media_id}/comments", token, message=msg)
        log("first comment added", media_id)
    except Exception as e:
        log("first comment not added (post itself is fine):", e)


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


def publish_story(token, media_url, kind):
    """Instagram Story (image or video) on the same account. Never raises: a story problem must not undo the post."""
    try:
        if not CONFIG.get("post_stories", True):
            return ""
        if not _story_room():
            log(f"story waits: {USED[PAGE]}/{TOTAL[PAGE]} posts in 24 h - posted by the story catch-up when the limit allows")
            return ""
        uid, _ = ig_account(token)
        prm = dict(media_type="STORIES")
        prm["video_url" if kind == "video" else "image_url"] = media_url
        cid = None
        path = localmedia.get(media_url) if kind == "video" else None      # None unless DIRECT_UPLOAD=1
        if path:
            try:
                cid = _ig_direct(uid, token, prm, path, False)[0]
            except Exception as e:
                log("story: direct upload not used - the link is used:", str(e)[:150])
                cid = None
        if not cid:
            cid = ig("POST", f"{uid}/media", token, **prm)["id"]
        wait_ready(cid, token, 10)
        mid = ig("POST", f"{uid}/media_publish", token, creation_id=cid)["id"]
        USED[PAGE] = USED.get(PAGE, 0) + 1
        log("story posted", kind, mid)
        return mid
    except Exception as e:
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
    reserve = int(CONFIG.get("story_reserve", 5))
    try:
        shared = json.loads(SHARED.read_text(encoding="utf-8"))
    except Exception:
        shared = {}
    cut = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    shared = {k: v for k, v in shared.items() if v.get("at", "") >= cut}
    for pg in LABEL:
        try:
            token = bridge_get("token", page=pg)["token"]
            uid, _ = ig_account(token)
            me = ig("GET", "me", token, fields="id,user_id")
            mine = {str(x) for x in (uid, me.get("id"), me.get("user_id")) if x}      # 1 Nov: a post's owner id is the app id, not user_id
            q = (ig("GET", f"{uid}/content_publishing_limit", token, fields="quota_usage,config").get("data") or [{}])[0]
            used, total = int(q.get("quota_usage", 0)), min(int((q.get("config") or {}).get("quota_total", 50) or 50), IG_LIMIT)
            feed = ig("GET", f"{uid}/media", token, fields="id,media_type,media_url,timestamp,owner,children{media_type,media_url}", limit=40).get("data", [])
            stories = sorted(t for t in (_ts(x.get("timestamp", "")) for x in ig("GET", f"{uid}/stories", token, fields="id,timestamp").get("data", [])) if t)
            now = datetime.now(timezone.utc)
            made = tries = 0
            log(f"story catch-up {pg}: quota {used}/{total}, {len(feed)} recent posts, {len(stories)} live stories, owner ids {sorted(mine)}")
            for m in sorted(feed, key=lambda x: x.get("timestamp", "")):
                t = _ts(m.get("timestamp", ""))
                if not t or str((m.get("owner") or {}).get("id") or uid) not in mine:
                    continue      # a collab post of the other page: that page shares it
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
                    if kind == "video":      # 1 Nov: Instagram refuses its own CDN video link for a story - the file is hosted again first
                        import tempfile
                        tmp = Path(tempfile.mkdtemp()) / "story.mp4"
                        rr = requests.get(url, timeout=180)
                        rr.raise_for_status()
                        tmp.write_bytes(rr.content)
                        url = upload(tmp, "video")
                    prm = dict(media_type="STORIES")
                    prm["video_url" if kind == "video" else "image_url"] = url
                    cid = ig("POST", f"{uid}/media", token, **prm)["id"]
                    wait_ready(cid, token, 8)
                    sid = ig("POST", f"{uid}/media_publish", token, creation_id=cid)["id"]
                    used += 1
                    made += 1
                    shared[m.get("id")] = shared[tkey] = {"story": sid, "page": pg, "at": now.isoformat()}
                    log(f"story catch-up {pg}: story {sid} for the post of {t:%d %b %H:%M} UTC ({m.get('media_type')})")
                except Exception as e:
                    log(f"story catch-up {pg}: post {m.get('id')} not shared ({str(e)[:150]}) - tried again next run")
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


def is_limit_error(e):
    t = str(e).lower()
    return "2207042" in t or "publish limit" in t or "publishing limit" in t or "maximum number of" in t and "posts" in t


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
        if limit_reached(pg):
            log("LIMIT: 24-hour Instagram post limit reached for", pg, "- ", row.get("story_id"), "waits")
            continue
        if limit_reached(pg) is False and USED.get(pg, 0) >= SOFT_CAP and not is_urgent(row):
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
        try:
            publish_story(token, url, "video")
        except Exception as e:
            log("story not made (post itself is fine):", e)
        share_facebook(sid, "reel", [url], caption, row=row)
        bridge_post("posted", {"row": row["row"], "page": PAGE, "kind": "reel", "permalink": link, "media_id": mid, "media_urls": [url],
                               "caption": caption, "voice": "ready-made", "collab": False, "checks": "ready reel posted as received (owner verified; no duplicate check)"})
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
    work = OUT / sid
    key = cache_key(row, spec, caption)
    cached = None if PREBUILD else load_cache(sid, key)
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
                media["reel"] = upload(mp4, "video")
                try:
                    media["cover"] = upload(reel_cover, "image") if reel_cover else ""
                except Exception as e:
                    log("cover upload failed:", e)
            if media["reel"] and (media["carousel"] or not need_carousel):
                save_cache(sid, key, dict(media, caption=caption), checks)      # owner 2 Nov: the caption that goes with THIS reel
        except Exception as e:
            return fail(row, "carousel", f"Upload failed: {e}")
    if PREBUILD:
        log("PREBUILT (not posted):", sid, "carousel", len(media["carousel"]), "slides, reel", bool(media["reel"]))
        return [("prebuilt", sid)]

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
                first_comment(token, mid, sid, 0)
                bridge_post("posted", {"row": row["row"], "page": PAGE, "kind": "carousel", "permalink": link, "media_id": mid,
                                       "media_urls": urls, "caption": caption, "slides": len(urls), "collab": collab_ok, "checks": note})
                done.append(("carousel", link))
                try:
                    if media.get("story"):
                        publish_story(token, media["story"], "image")
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
                USED[PAGE] = USED.get(PAGE, 0) + 1
                bridge_post("posted", {"row": row["row"], "page": PAGE, "kind": "reel", "permalink": link, "media_id": mid,
                                       "media_urls": [url], "caption": caption, "voice": voice, "collab": collab_ok, "checks": note})
                done.append(("reel", link))
                first_comment(token, mid, sid, 1)
                publish_story(token, url, "video")
                try:      # website OFF for now: website.send does nothing without WEBSITE_INGEST_KEY (a website problem never stops posting)
                    import website
                    website.send(row, link)
                except Exception as e:
                    log("website step skipped:", str(e)[:150])
                fb = share_facebook(sid, "reel", [url], caption, row=row)
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


def share_facebook(sid, kind, media, caption, dry=False, row=None):
    """owner 2 Nov: Instagram posts also go to this page's Facebook page with a story; owner 11 Nov: only the top news (fb_rank),
    with the article link. kind 'reel' or 'photos'. Never raises - Instagram is never touched."""
    try:
        import facebook
        src = str((row or {}).get("source") or "").strip()
        return facebook.share(PAGE, sid, kind, media, caption, TAG, dry=dry, rank=fb_rank(row) if row else None,
                              source_link=src if src.startswith("http") else "")
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


def plain_background(work, n):
    """a plain branded background for a reel made without pictures (one file, used for every scene)"""
    from PIL import Image as _I, ImageDraw as _D
    work.mkdir(parents=True, exist_ok=True)
    im = _I.new("RGB", (1080, 1920), (14, 22, 36))
    d = _D.Draw(im)
    for y in range(1920):           # soft vertical gradient
        t = y / 1920
        d.line([(0, y), (1080, y)], fill=(int(14 + 20 * t), int(22 + 30 * t), int(36 + 40 * t)))
    try:      # owner 29 Oct: no free picture -> the page logo, large and soft, so the reel still looks like ours
        lg = _I.open(LOGO).convert("RGBA").resize((760, 760))
        lg.putalpha(lg.getchannel("A").point(lambda v: int(v * 0.35)))
        im.paste(lg, (160, 560), lg)
    except Exception:
        pass
    dst = work / "plain_bg.jpg"
    im.save(dst, "JPEG", quality=95)
    return [dst] * n


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
        log(f"{len(rows)} stories in the queue, ready to post: {n}")
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
                        pg = [p for p in todo if p not in full and left.get(p, per_story) >= per_story
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
                        busy = [p for p in pg if p in slots or minutes_since_last_post(p) < spacing]
                        if busy and not is_urgent(r):
                            waiting.append(r["story_id"])
                            log("  ", r["story_id"], f"waits for the {spacing:.0f}-minute gap after the last post on {busy}")
                            continue
                        k = max([slots.get(p, -1) for p in pg]) + 1      # urgent news of one run: 6 minutes apart
                        ids.append((r["story_id"], k * 6))
                        for p in pg:
                            slots[p] = k
                            left[p] = left.get(p, 99) - per_story
                        if len(ids) >= 12:
                            break
                    inc = [{"story": i, "slot": sl, "prebuild": ""} for i, sl in ids]
                    ids = [i for i, _ in ids]
                    # stories whose set has not started yet: make the carousel/reel ahead, so they go out the moment it starts
                    urgent = set(ids)
                    pre = [r["story_id"] for r in rows if ready(r) and r["story_id"] not in urgent and (not set_started(r) or r["story_id"] in waiting) and not all(cache_path(r["story_id"], p).exists() for p in pages_of(r) if not page_done(r, p))][:12]      # waiting reels are made ahead, so they go out the minute prime time starts
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
        facts_ = [p for p in facts_ if not re.search(r"[-—–,;:(]\s*(acceptable|this is acceptable|is fine|not an error|no (real )?(issue|problem)|ok)\.?\)?\s*$", p, re.I)]
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
