"""Date checks for announcement-type news (power cuts, job fairs / interviews, camps, 'today' / 'tomorrow' items):
such a story is only worth posting while the date it announces has not passed. Pure functions, used by the poster and by the collector."""
import datetime, re

IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
EN_M = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}
TA_FULL = {"ஜனவரி": 1, "பிப்ரவரி": 2, "மார்ச்": 3, "ஏப்ரல்": 4, "மே": 5, "ஜூன்": 6, "ஜூலை": 7, "ஆகஸ்ட்": 8, "செப்டம்பர்": 9, "அக்டோபர்": 10, "நவம்பர்": 11, "டிசம்பர்": 12}
TA_ABB = {"ஜன": 1, "பிப்": 2, "மார்": 3, "ஏப்": 4, "ஆக": 8, "செப்": 9, "அக்": 10, "நவ": 11, "டிச": 12}
TRIGGER = re.compile(r"மின்\s?தடை|power\s?cut|shutdown|வேலைவாய்ப்பு|job\s?fair|interview|recruitment|camp\b|முகாம்|நேர்முகத்|walk-?in|இன்று|நாளை|tonight|\btoday\b|\btomorrow\b", re.I)
SHUT = re.compile(r"மின்\s?தடை|power\s?cut|shutdown", re.I)
TODAY = re.compile(r"இன்று|\btoday\b|tonight", re.I)
TOMORROW = re.compile(r"நாளை|\btomorrow\b", re.I)


def _mon_en(t):
    return EN_M.get(t[:3].lower())


def dates_in(text, year):
    """explicit dates ('23 Oct', 'Oct 23', '23 அக்டோபர்', 'அக். 23') found in the text -> list of date objects"""
    out = []
    pats_en = [(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*", 1, 2),
               (r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{1,2})\b", 2, 1)]
    for p, di, mi in pats_en:
        for m in re.finditer(p, text, re.I):
            out.append((int(m.group(di)), _mon_en(m.group(mi))))
    tamil_mon = "|".join(sorted(list(TA_FULL) + list(TA_ABB), key=len, reverse=True))
    tam = {**TA_ABB, **TA_FULL}
    for m in re.finditer(r"(\d{1,2})\s*-?\s*(%s)\.?(?![஀-௿])" % tamil_mon, text):
        out.append((int(m.group(1)), tam[m.group(2)]))
    for m in re.finditer(r"(%s)\.?\s*-?\s*(\d{1,2})(?!\d)" % tamil_mon, text):
        out.append((int(m.group(2)), tam[m.group(1)]))
    res = []
    for d, mo in out:
        try:
            res.append(datetime.date(year, mo, d))
        except (ValueError, TypeError):
            pass
    return res


def pub_date(s):
    """date of the 'published' cell: ISO or '21 Oct 2026, 05:24 IST'"""
    s = str(s or "")
    try:      # owner 29 Oct: an ISO time with a zone ('...T22:17:23Z' = 03:47 next morning in IST) is read in IST, not by its UTC date
        t = datetime.datetime.fromisoformat(s.strip().replace("Z", "+00:00"))
        if t.tzinfo is not None:
            return t.astimezone(IST).date()
    except ValueError:
        pass
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.search(r"(\d{1,2})\s+([A-Za-z]{3})[a-z]*\s+(\d{4})", s)
    if m and _mon_en(m.group(2)):
        return datetime.date(int(m.group(3)), _mon_en(m.group(2)), int(m.group(1)))
    return None


def stale_reason(headline_ta, headline_en, category, published, today=None):
    """'' when the story is still current, else why it must not be posted"""
    today = today or datetime.datetime.now(IST).date()
    text = f"{headline_ta} {headline_en} {category}"
    price = bool(RECUR.search(text))
    if not TRIGGER.search(text) and not price:
        return ""
    pub = pub_date(published)
    ds = dates_in(f"{headline_ta} {headline_en}", today.year)
    ds = [d for d in ds if (d - today).days < 300]
    if ds:
        if max(ds) < today:
            return f"announced date {max(ds):%d %b} has passed"
        return ""
    if pub:
        if price and pub < today:           # a daily price is only news on the day it applies to
            return f"price news from {pub:%d %b}, not today"
        if TODAY.search(text) and pub < today:
            return f"says 'today' but was published {pub:%d %b}"
        if TOMORROW.search(text) and pub + datetime.timedelta(days=1) < today:
            return f"says 'tomorrow' but was published {pub:%d %b}"
        if SHUT.search(text) and pub < today and not TOMORROW.search(text):
            return f"power-cut notice from {pub:%d %b} with no date"
    return ""


def news_date(published, source_url="", filed=None):
    """the day the news was published: the 'published' cell, else the date in the newspaper's link (/2026/Oct/26/, 2026-10-26,
    dinakaran coimbatore-261026-3), else the day it was filed (never earlier than the real day, so it can only be lenient)"""
    d = pub_date(published)
    if d:
        return d
    u = str(source_url or "")
    m = re.search(r"/(20\d\d)/([A-Za-z]{3})[a-z]*/(\d{1,2})/", u)
    if m and _mon_en(m.group(2)):
        return datetime.date(int(m.group(1)), _mon_en(m.group(2)), int(m.group(3)))
    m = re.search(r"/(20\d\d)[/-](\d{2})[/-](\d{2})(?:/|\b)", u)
    if m:
        try:
            return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    m = re.search(r"dinakaran\.com/district/[a-z]+-(\d{2})(\d{2})(\d{2})", u)
    if m:
        try:
            return datetime.date(2000 + int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass
    return filed.date() if filed else None


def power_cut_over(headline_ta, headline_en, published, now=None):
    """'' or why a power-cut notice is too late to post: the cut is today and its end time ('மதியம் 2 வரை', 'till 5 pm') is less
    than 1 hour away or past. Checked even for stories filed today (27 Oct: a 9-2 cut was about to go out at 1:40 pm as 'tomorrow')."""
    text = f"{headline_ta} {headline_en}"
    if not SHUT.search(text):
        return ""
    now = now or datetime.datetime.now(IST)
    today, pub = now.date(), pub_date(published)
    ds = [d for d in dates_in(text, today.year) if abs((d - today).days) < 300]
    day = max(ds) if ds else (pub + datetime.timedelta(days=1) if pub and TOMORROW.search(text) else pub)
    if day != today:
        return ""
    m = (re.search(r"(மதியம்|மாலை|இரவு|பிற்பகல்)?\s*(\d{1,2})(?:[.:](\d{2}))?\s*(?:மணி\s*)?வரை", headline_ta or "")
         or re.search(r"(?:till|to|until)\s*(\d{1,2})(?:[.:](\d{2}))?\s*(pm|am)?", headline_en or "", re.I))
    if not m:
        return ""
    if m.re.pattern.startswith("(மதியம்"):
        pm, h, mi = bool(m.group(1)) or int(m.group(2)) <= 7, int(m.group(2)), int(m.group(3) or 0)
    else:
        h, mi = int(m.group(1)), int(m.group(2) or 0)
        pm = (m.group(3) or "").lower() == "pm" or (not m.group(3) and h <= 7)
    if pm and h < 12:
        h += 12
    end = now.replace(hour=min(h, 23), minute=mi, second=0, microsecond=0)
    if now >= end - datetime.timedelta(minutes=60):
        return f"power cut ends today at {end:%H:%M} - too late to post"
    return ""


# ---- repeating topics (daily egg price, gold rate, fuel price ...): the same headline every day is NEW news each day
RECUR = re.compile(r"முட்டை\s*(விலை|கொள்முதல்)|egg\s*(price|rate)|தங்கம்\s*விலை|gold\s*(rate|price)|பெட்ரோல்\s*விலை|டீசல்\s*விலை|petrol|diesel", re.I)


def recurring(text):
    return bool(RECUR.search(text or ""))


def different_numbers(a, b):
    """both headlines give numbers and none of them match: a different event (8 arrested / Rs 1,47,000 is not 6 people / Rs 11,600)"""
    na = set(re.findall(r"\d+", (a or "").replace(",", "")))
    nb = set(re.findall(r"\d+", (b or "").replace(",", "")))
    return bool(na) and bool(nb) and not (na & nb)


POWER = re.compile(r"மின்\s*தடை|மின்\s*நிறுத்த|power\s*(cut|shut)", re.I)
POWER_ANY = re.compile(r"(?:" + POWER.pattern + r"|மின்\s*வெட்டு|மின்\s*விநியோகம்\s*(?:நிறுத்த|தடை))(?!க்கும்|யால்)", re.I)      # not a bare 'shutdown' (TASMAC / shop shutdown); 31 Oct: not 'மின் தடைக்கும்' (a remark) / 'மின் தடையால்' (a complaint)


def is_power_cut(*texts):
    """owner 30 Oct (Coimbatore): the ONE test for 'this is a power-cut notice' - such a reel may run to 90 s, is judged by the day of
    the cut (power_cut_ahead) and is never held back by a daily cap"""
    return bool(POWER_ANY.search(" ".join(str(t or "") for t in texts)))


NUM_DATE = re.compile(r"(?<![\d.])(\d{1,2})[./-](\d{1,2})[./-](20\d\d|\d\d)(?![\d.])")


def _num_dates(text):
    """day-first number dates of power-cut notices: 'நாளை 29.10.26', '(29.10.2026)', '30-10-2026' (30 Oct archive titles)"""
    out = []
    for m in NUM_DATE.finditer(text or ""):
        y = int(m.group(3))
        try:
            out.append(datetime.date(y + 2000 if y < 100 else y, int(m.group(2)), int(m.group(1))))
        except ValueError:
            pass
    return out


def power_cut_ahead(headline, published, today=None):
    """owner 30 Oct (Coimbatore): a power cut is judged by the day of the CUT, not the day it was published - 'நாளை மின்தடை' published
    last evening is TODAY's cut and is still posted. True only when the headline is a power cut whose day is today or later
    (a cut that is over is still skipped by power_cut_over)."""
    if not is_power_cut(headline):
        return False
    today = today or datetime.datetime.now(IST).date()
    ds = [d for d in dates_in(headline or "", today.year) + _num_dates(headline) if abs((d - today).days) < 300]
    if ds:
        return max(ds) >= today
    pub = pub_date(published)
    return bool(pub and TOMORROW.search(headline or "") and pub + datetime.timedelta(days=1) >= today)


_POWER_COMMON = ("மின்", "தடை", "நாளை", "இன்று", "இன்றை", "காலை", "மதியம", "மாலை", "வரை", "முதல்", "பகுதி", "துணை", "நிலைய",
                 "பராமர", "பணி", "காரண", "அறிவி", "மணி", "கோவை", "கோயம்", "மாவட", "எந்தெ", "power", "cut", "shut", "tomorr", "today",
                 "areas", "mainte", "substa", "kovai", "coimb", "from", "till", "will", "the")


def different_power_cut(a, b, other_filed=None, today=None):
    """two power-cut notices look alike ('நாளை மின்தடை ... 9 முதல் 2 வரை'); they are the same news only when they name the same
    place and were filed within 3 days (27 Oct: Kalappanaickenpatti's cut was skipped as a 'duplicate' of an older notice)"""
    if not (POWER.search(a or "") and POWER.search(b or "")):
        return False
    def places(t):
        return {w[:6] for w in re.findall(r"[\u0B80-\u0BFFa-zA-Z]{4,}", t.lower()) if not w.startswith(_POWER_COMMON)}
    pa, pb = places(a), places(b)
    if pa and pb and not (pa & pb):
        return True
    d = pub_date(other_filed)
    today = today or datetime.datetime.now(IST).date()
    return bool(d and (today - d).days >= 3)


# words of a power-cut headline that are no place of their own ('நேரு நகர்' and 'காந்தி நகர்' are not the same place)
_PLACE_COMMON = _POWER_COMMON + ("நகர்", "நகரில்", "காலனி", "சாலை", "ரோடு", "வீதி", "தெரு", "கிராம", "ஊராட்", "பஞ்சா", "மற்றும்", "உள்ளிட்",
                                 "இடங்க", "இடங்கள", "விநியோ", "நிறுத்", "பகுதிக", "தமிழ்", "முக்கி", "அறிவிப்")


def cut_day(headline, published):
    """the day of the cut a power-cut headline announces: its own date ('29.10.26', '30 அக்டோபர்'), else the day after publishing
    for 'நாளை', else the day it was published"""
    pub = pub_date(published)
    ref = pub or datetime.datetime.now(IST).date()
    ds = [d for d in dates_in(headline or "", ref.year) + _num_dates(headline) if abs((d - ref).days) < 300]
    if ds:
        return max(ds), True
    if pub and TOMORROW.search(headline or ""):
        return pub + datetime.timedelta(days=1), False
    return pub, False


def same_power_cut(a, a_published, b, b_published):
    """owner 30 Oct (Coimbatore): two power-cut notices are the SAME news when they announce the same cut day and name the same place
    ('நாளை காளப்பட்டியில் மின் தடை' posted last night = 'காளப்பட்டி பகுதியில் இன்று மின் தடை' this morning). The headline check alone
    misses these (different words). Without a shared place nothing is blocked: a power cut is never lost as a false duplicate.
    A day from 'நாளை' may be one day off (posted after midnight, Instagram time), so it may differ by 1; two printed dates must match."""
    if not (is_power_cut(a) and is_power_cut(b)):
        return False
    (da, fa), (db, fb) = cut_day(a, a_published), cut_day(b, b_published)
    if not da or not db or abs((da - db).days) > (0 if fa and fb else 1):
        return False
    def places(t):
        return {w[:6] for w in re.findall(r"[\u0B80-\u0BFFa-zA-Z]{4,}", (t or "").lower()) if not w.startswith(_PLACE_COMMON)}
    return bool(places(a) & places(b))


_GENERIC = ("கோவை", "கோயம்", "மாவட்", "kovai", "coimb", "அருகே", "அருகில்", "இன்று", "நாளை", "நேற்று", "உயிரிழ",
            "தொழிலா", "கைது", "பகுதி", "நடந்த", "வழங்க")


def shares_words(a, b):
    """Tamil headlines share many letters, so a letter match alone is weak (27 Oct: 'கோவை நீதிமன்றத்திலிருந்து தப்பியோடிய
    கைதி பிடிப்பு' was taken for 'கோவையில் நீதிமன்ற உத்தரவுப்படி ஆர்எஸ்எஸ் ஊர்வலம்'). The same news also shares a third of
    its own words (place names and common words left out), or is almost letter-for-letter the same."""
    import difflib
    n = lambda t: (t or "").replace("ா்", "ர்").lower()
    w = lambda t: {x[:4] for x in re.findall(r"[\u0B80-\u0BFFa-z0-9]{3,}", n(t)) if not x.startswith(_GENERIC)}
    x, y = w(a), w(b)
    if x and y and len(x & y) / min(len(x), len(y)) >= 0.34:
        return True
    return difflib.SequenceMatcher(None, n(a), n(b)).ratio() >= 0.75


def different_places(a, b):
    """owner 2 Nov (review): two headlines naming different towns of the district are two news (research_free/allnews.places_in)"""
    try:
        import sys as _sys, pathlib as _pl
        p = str(_pl.Path(__file__).resolve().parent.parent / "research_free")
        if p not in _sys.path:
            _sys.path.append(p)
        import allnews
        return allnews.different_places(a, b)
    except Exception:
        return False


def similar(a, b, thr, other_filed=None, today=None):
    """True when headline a and b are the same news. A repeating-price topic (e.g. today's egg price) counts as the same
    only when the other story was filed the same day - tomorrow's price is a new post."""
    import difflib
    if (not a or not b or difflib.SequenceMatcher(None, a, b).ratio() <= thr or different_numbers(a, b)
            or different_power_cut(a, b, other_filed, today) or not shares_words(a, b) or different_places(a, b)):
        return False
    if recurring(a) or recurring(b):
        today = today or datetime.datetime.now(IST).date()
        return pub_date(other_filed) == today
    return True


FOLLOW = re.compile(r"கைது|சிறை|தீர்ப்பு|மீட்பு|மீட்கப்|பறிமுதல்|இழப்பீடு|குற்றப்பத்திரிகை|ஜாமீன்|சரண்|உயிரிழப்பு|பலி|"
                    r"arrest|held|nabbed|sentenc|verdict|convict|rescued|recovered|seized|compensation|bail|surrender|died|dead", re.I)


def follow_up(old, new, days=2):
    """28 Oct (RN-159 '3 arrested for stealing laptops' was blocked as a duplicate of RN-42 'laptops stolen', 6 days earlier):
    a later report that brings a new development (arrest, verdict, rescue, seizure ...) about a story filed more than `days`
    days before is new news, not a duplicate"""
    o, n = pub_date(old.get("researched")), pub_date(new.get("researched"))
    if not o or not n or (n - o).days <= days:
        return False
    text = lambda r: (r.get("headline_ta") or "") + " " + (r.get("headline_en") or "")
    return bool(FOLLOW.search(text(new))) and not FOLLOW.search(text(old))


# owner 29 Oct (RN-189 egg price): a story that only says the article has no facts is NOT news and is never filed or posted.
# The writer sometimes "explains" a page it could not read (price in an image, wrong text scraped) instead of reporting news.
NO_NEWS_TA = ("கட்டுரையில் இல்லை", "கட்டுரையில் குறிப்பிடப்படவில்லை", "கட்டுரையில் வெளியிடப்படவில்லை", "இந்தக் கட்டுரையில்",
              "விவரம் இன்னும் தெரியவரவில்லை", "விவரம் தெரியவரவில்லை", "விவரம் இன்னும் தெரியவில்லை", "தகவல் இல்லை",
              "எண்ணோ தகவலோ இல்லை", "விவரம் கிடைத்ததும் பகிரப்படும்",
              # owner 31 Oct (Coimbatore RN-102: "முழு விவரங்கள் இன்னும் தெரியவரவில்லை ... வெளியானதும் தெரிவிக்கப்படும்")
              "விவரங்கள் இன்னும் தெரியவரவில்லை", "விவரங்கள் தெரியவரவில்லை", "இன்னும் தெரியவரவில்லை", "வெளியானதும் தெரிவிக்கப்படும்",
              "வெளியானதும் பகிரப்படும்", "தெரியவந்ததும் தெரிவிக்கப்படும்", "முழுமையாக வெளியிடப்படவில்லை", "விவரங்களுக்கு காத்திருங்கள்", "தெரியவந்ததும் பகிரப்படும்", "தொடர்புடையது அல்ல", "தொடர்பில்லை")
NO_NEWS_EN = ("not in the article", "not mentioned in the article", "article does not", "article doesn't", "no details available",
              "details not available", "details are not available", "will be shared when", "not related to")


# owner 31 Oct (RN-241 'மேலும் விவரங்கள் இன்னும் தெரியவரவில்லை'): every form - plural, மேலும் / இன்னும், 'இவ்வளவுதான்' (that is all)
NO_DETAILS = re.compile(r"(?:விவரம்|விவரங்கள்|விவரங்களும்|தகவல்|தகவல்கள்)\S*\s+(?:(?:மேலும்|இன்னும்)\s+)*"
                        r"(?:தெரியவரவில்லை|தெரியவில்லை|வெளியாகவில்லை|வெளியிடப்படவில்லை|கிடைக்கவில்லை|தெரியவரும்)|இவ்வளவுதான்|இவ்வளவே")


def _meta(sentence):
    low = sentence.lower()
    return [x for x in NO_NEWS_TA if x in sentence] + [x for x in NO_NEWS_EN if x in low] + [m.group(0) for m in NO_DETAILS.finditer(sentence)]


def _sentences(text):
    import re as _re
    return [x.strip() for x in _re.split(r"(?<=[.!?\u0964])\s+|\n+", str(text or "")) if x.strip()]


def no_news(headline, reel_script="", caption=""):
    """'' = real news. Otherwise why the story is only about missing facts: the headline/hook says so, or at least
    40% of the reel script's news sentences (the follow line not counted) talk about details that are missing."""
    found = _meta(str(headline or ""))
    if found:
        return f"not news: the headline says the details are missing ({found[0]})"
    sents = [x for x in _sentences(reel_script) if "பின்தொடரு" not in x and "follow" not in x.lower()]
    bad = [x for x in sents if _meta(x)]
    if sents and len(bad) / len(sents) >= 0.4:
        return f"not news: {len(bad)} of {len(sents)} sentences only say the article has no details"
    return ""


def strip_no_news(text):
    """remove the sentences/lines that only say a detail is missing from the article (the rest of a real story stays)"""
    import re as _re
    out = []
    for line in str(text or "").split("\n"):
        keep = [x for x in _re.split(r"(?<=[.!?\u0964])\s+", line) if not _meta(x)]
        if line.strip() and not "".join(keep).strip():
            continue
        out.append(" ".join(keep))
    return "\n".join(out)


# owner 29 Oct (Coimbatore RN-29, a 2025 wedding re-told in a new article): a story whose every dated fact is months old and that
# has no sign of anything happening now (today / yesterday / a weekday / "so far" / an arrest or verdict) is an old event.
RECENT_WORDS = ("இன்று", "நேற்று", "நேற்றிரவு", "முன்தினம்", "இன்றிரவு", "இந்த வாரம்", "நாளை", "இதுவரை", "தற்போது", "இன்னும்",
                "சமீபத்தில்", "திங்கள்", "செவ்வாய்", "புதன்", "வியாழ", "வெள்ளிக்கிழமை", "சனிக்கிழமை", "ஞாயிற்று")


def old_event(text, today=None):
    t = text or ""
    today = today or datetime.datetime.now(IST).date()
    if any(w in t for w in RECENT_WORDS) or FOLLOW.search(t):
        return ""
    if any(abs((d - today).days) <= 7 for d in dates_in(t, today.year)):
        return ""
    tam = {**TA_ABB, **TA_FULL}
    mon = "|".join(sorted(tam, key=len, reverse=True))
    olds = []
    for m in re.finditer(r"(\d{1,2})?\s*(%s)\.?\s*,?\s*(20\d\d)" % mon, t):
        try:
            olds.append(datetime.date(int(m.group(3)), tam[m.group(2)], int(m.group(1) or 1)))
        except (ValueError, KeyError):
            pass
    if olds and all((today - d).days >= 60 for d in olds):
        return f"old event: the story is about {max(olds):%d %b %Y}, nothing in it happened in the last days"
    return ""


# owner 29 Oct (Coimbatore RN-13 / RN-24 bus fight, Namakkal RN-86 / RN-115 Collector wall): the same event reported by two outlets
# in different words. Compared on the DISTINCTIVE words of the two reel scripts (words that appear in few other stories: names,
# places, numbers), not on the headline wording.
def _event_stems(t):
    t = re.sub(r"மேலும் செய்திகளுக்கு.*$", "", t or "")
    return {w[:5] for w in re.findall(r"[஀-௿]{5,}", t)} | set(re.findall(r"\d{2,}", t))


def event_df(scripts):
    import collections
    df = collections.Counter()
    for s in scripts:
        df.update(_event_stems(s))
    return df, max(1, len(scripts))


def same_event(a, b, df_n):
    df, n = df_n
    rare = lambda t: {s for s in _event_stems(t) if df[s] <= max(2, n * 0.05)}
    x, y = rare(a), rare(b)
    if len(x) < 4 or len(y) < 4:
        return False
    shared = len(x & y)
    r = shared / min(len(x), len(y))
    # 30 Oct RN-214 = RN-209 (short scripts, 8 shared rare stems, 0.62): short reports of one event share fewer words.
    # In 80 filed Namakkal stories no two different events shared more than 5 rare stems.
    return (shared >= 9 and r >= 0.45) or (shared >= 6 and r >= 0.55) or same_incident(a, b, df_n, shared, r)


# 31 Oct (Coimbatore RN-96 = RN-95, one prisoner's escape told by two outlets; earlier RN-39 = RN-76, RN-17 = RN-54 posted twice):
# word overlap cannot tell "the same event" from "the same kind of story" (two temple poojas share as many rare words as two reports of one
# escape). An INCIDENT is the same event when both reports name the same person or the same distinctive number - or share many rare words.
INCIDENT = {"escape": r"தப்பி", "arrest": r"கைது", "verdict": r"தண்டனை", "accident": r"விபத்து|மோதி", "death": r"உயிரிழ|பலி|சடலம",
            "fire": r"தீப்பிடி|தீப்பற்|தீ விபத்து", "transfer": r"இடமாற்ற", "seizure": r"பறிமுதல்", "fraud": r"மோசடி", "theft": r"திருட|கொள்ளை",
            "murder": r"கொலை", "fight": r"அடிதடி|கைகலப்பு|தாக்கிக்கொண்|மோதிக்கொண்",
            "collapse": r"இடிந்து|இடிந்த|சரிந்து விழு"}      # owner 31 Oct: Namakkal RN-115 = RN-86 (collector bungalow wall, two outlets)      # owner 31 Oct: RN-13 = RN-24 (bus drivers' fight) posted twice
_NAME = (re.compile(r"([஀-௿]{3,})\s*\(\d{1,3}\)"), re.compile(r"([஀-௿]{3,})\s+(?:என்பவ|என்ற\s)"),
         re.compile(r"\d{1,3}\s*வயது(?:டைய|ான|ுடைய)?\s+([஀-௿]{3,})"))


def _incidents(t):
    return {k for k, p in INCIDENT.items() if re.search(p, t or "")}


# role words written like a name before an age ('இளைஞர் (25)', 'பெண் (40)') - not a person's name
_ROLES = ("இளைஞ", "வாலிப", "பெண்", "முதிய", "மூதாட", "தொழில", "விவசா", "மாணவ", "சிறுவ", "சிறுமி", "கணவர", "மனைவ", "டிரைவ", "ஓட்டுந",
          "கூலித", "ஒருவர", "நபர்", "தந்தை", "தாய்", "மகன்", "மகள்", "குழந்", "நண்பர", "உறவின", "ஊழியர", "காவலர", "போலீஸ", "அதிகா")


def _names(t):
    return {m.group(1)[:5] for p in _NAME for m in p.finditer(t or "") if not m.group(1).startswith(_ROLES)}


def _numbers(t):
    """distinctive numbers: 3+ digits or with a decimal point (2015, 2.25, 11.15) - not this year or last year, not round amounts"""
    y = datetime.datetime.now(IST).year
    t = re.sub(r"(?<=\d),(?=\d)", "", t or "")
    return {n for n in re.findall(r"\d+(?:\.\d+)?", t)
            if (len(n) >= 3 or "." in n) and n not in (str(y), str(y - 1)) and not ("." not in n and int(n) % 100 == 0)}      # 1,000 police / Rs 500 are not distinctive


def same_incident(a, b, df_n, shared=None, r=None):
    """two reports of one incident: a common incident type AND (the same rarely seen person's name, the same rarely seen distinctive number,
    or 8+ shared rare words). Two different poojas / health tips / recipes are no incident, so they are never matched here."""
    if not (_incidents(a) & _incidents(b)):
        return False
    df, n = df_n
    if any(df[x] <= 3 for x in _names(a) & _names(b)):
        return True
    if any("." in x or df[x] <= 3 for x in _numbers(a) & _numbers(b)):
        return True
    # owner 31 Oct: RN-13 = RN-24 (one bus drivers' fight, two outlets: 8 shared rare words, 0.50) - on all posted stories of both pages this
    # matched no two different incidents
    # owner 31 Oct (Coimbatore RN-102 / RN-103 = RN-95): an escape of a prisoner from the same town's prison is one event, however it is
    # told (the follow-ups named no prisoner)
    if "escape" in _incidents(a) & _incidents(b) and "கைதி" in a and "கைதி" in b and _prison_towns(a) & _prison_towns(b):
        return True
    return shared is not None and ((shared >= 9 and r >= 0.3) or (shared >= 7 and r >= 0.45))


_PRISON = re.compile(r"([஀-௿]{2,})\s+(?:மத்திய(?:ச்)?\s+|மாவட்ட(?:ச்)?\s+|கிளை(?:ச்)?\s+|பெண்கள்\s+)?சிறை")


def _prison_towns(t):
    return {m.group(1)[:4] for m in _PRISON.finditer(t or "") if not m.group(1).startswith(("மத்திய", "மாவட்ட", "இந்த", "அந்த", "எந்த"))}


# ---- owner 11 Nov (Coimbatore): a power cut that was CANCELLED / POSTPONED / moved to another day after it was posted is NEW news -
# people stay home or plan for it. It names the same place and day as the original notice, so every duplicate test took it for the
# same news and it was never posted. A notice and its cancellation / change are now never the same news.
CUT_CHANGE = re.compile(r"ரத்து|ரத்தா|நிறுத்தி\s*வைப்பு|ஒத்தி\s*வை|ஒத்திவை|தள்ளி\s*வை|தள்ளிவை|நடைபெறாது|இருக்காது|"
                        r"மாற்றம்|மாற்றப்பட|cancel|postpone|deferred|withdrawn|rescheduled", re.I)      # மாற்றம் = changed (not மின்மாற்றி, a transformer)
_POW = re.compile(r"மின்\s*தடை|மின்\s*நிறுத்த|மின்\s*வெட்டு|power\s*(cut|shut|outage)", re.I)


def cut_change(text):
    """True when the text is about a power cut being cancelled / postponed / moved"""
    return bool(_POW.search(text or "") and CUT_CHANGE.search(text or ""))


def cancel_differs(a, b):
    """one text is a power cut, the other its cancellation / change - never the same news"""
    a, b = str(a or ""), str(b or "")
    return bool((_POW.search(a) or _POW.search(b)) and cut_change(a) != cut_change(b))



_similar, _same_power_cut, _different_power_cut, _same_event, _same_incident = similar, same_power_cut, different_power_cut, same_event, same_incident


def similar(a, b, thr, other_filed=None, today=None):
    return False if cancel_differs(a, b) else _similar(a, b, thr, other_filed, today)


def same_power_cut(a, a_published, b, b_published):
    return False if cancel_differs(a, b) else _same_power_cut(a, a_published, b, b_published)


def different_power_cut(a, b, other_filed=None, today=None):
    return True if cancel_differs(a, b) else _different_power_cut(a, b, other_filed, today)


def same_event(a, b, df_n):
    return False if cancel_differs(a, b) else _same_event(a, b, df_n)


def same_incident(a, b, df_n, shared=None, r=None):
    return False if cancel_differs(a, b) else _same_incident(a, b, df_n, shared, r)


_CUT_COMMON = ("மின்தடை", "மின்தட", "மின்நி", "நாளை", "இன்று", "காலை", "மாலை", "மதியம்", "முதல்", "வரை", "பகுதி", "ரத்து", "ரத்தா",
               "ஒத்தி", "தள்ளி", "மாற்ற", "நிறுத", "அறிவி", "துணை", "நிலைய", "மின்வா", "பராமரி", "தேதி", "power", "outag")


def change_of_posted(change, original):
    """owner 11 Nov: a cancellation / change is posted ONLY for a power cut this page already posted - True when `original` (a posted
    power-cut headline, not itself a change) names the same place as the cancellation / change `change`"""
    if not (cut_change(change) and _POW.search(original or "") and not cut_change(original)):
        return False
    try:
        import sys as _s
        from pathlib import Path as _P
        _s.path.insert(0, str(_P(__file__).resolve().parent.parent / "research_free"))
        import allnews
        pa, pb = set(allnews.places_in(change)), set(allnews.places_in(original))
        if pa and pb:
            return bool(pa & pb)
    except Exception:
        pass
    st = lambda t: {w[:5] for w in re.findall(r"[஀-௿a-zA-Z]{4,}", t.lower()) if not w.startswith(_CUT_COMMON)}
    return bool(st(change) & st(original))
