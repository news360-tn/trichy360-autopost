"""Checks on a free-model draft. Returns a list of problems (empty = passes). Used for the retry loop and as the first gate."""
import json, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "poster"))
OUTLETS = ["தினமலர்", "தினத்தந்தி", "தினமணி", "மாலைமலர்", "தினகரன்", "இந்து தமிழ்", "தி இந்து", "புதிய தலைமுறை", "நியூஸ்18", "நியூஸ் 18",
           "பாலிமர்", "சன் நியூஸ்", "நியூஸ்7", "நியூஸ் 7", "கலைஞர் செய்திகள்", "விகடன்", "ஒன்இந்தியா", "வே2நியூஸ்", "டாப் தமிழ்",
           "தமிழ் மணி", "டைம்ஸ் ஆஃப் இந்தியா", "dinamalar", "dinamani", "dinathanthi", "daily thanthi", "maalaimalar", "dinakaran",
           "the hindu", "hindu tamil", "times of india", "dt next", "indian express", "news18", "polimer", "sun news", "news7", "vikatan",
           "oneindia", "way2news", "puthiya thalaimurai", "kalaignar", "toptamilnews", "ஆதாரம்", "source:", "http", "www."]
PAGE = "Coimbatore 360"      # post_to value (the only page)
LAST = "மேலும் செய்திகளுக்கு கோயம்புத்தூர் த்ரீ சிக்ஸ்டி பக்கத்தை பின்தொடருங்கள்."
FOLLOW = "உள்ளூர் செய்திகளுக்கு Follow செய்யுங்கள் 🙏"
KEYS = ["tamil_headline", "english_headline", "category", "location", "importance", "post_to", "slides_spec", "reel_script", "caption", "scenes"]


def _tags(t):
    return re.sub(r"<[^>]+>", "", t or "")


def _digits_in(text):
    t = text or ""
    # "2,600" counts as 2600 as well
    return set(re.findall(r"\d+", t)) | set(re.findall(r"\d+", re.sub(r"(?<=\d),(?=\d{2,3}\b)", "", t)))


def _num(n):
    """owner 2 Nov: a number by its value - '02' is 2 ('📍 இடம் | 02 நவம்பர் 2026' held every story on 1-9 Nov), '000' is 0"""
    return n.lstrip("0") or "0"


_SCALE = {"ஆயிரம்": 1000, "ஆயிர": 1000, "லட்சம்": 100000, "லட்ச": 100000, "கோடி": 10000000}


def _scaled_digits(text):
    """'10 ஆயிரம்' / '2 லட்சம்' / '1.5 கோடி' in the article: the script may write 10000 / 200000 / 15000000"""
    out = set()
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*(ஆயிர|லட்ச|கோடி)", text or ""):
        out.add(str(int(round(float(m.group(1)) * _SCALE[m.group(2)]))))
    return out


def _calendar_digits():
    """today's / yesterday's / tomorrow's day, the month number and the year (IST): a story written today may name them"""
    import datetime as _dt
    now = _dt.datetime.now(_dt.timezone(_dt.timedelta(hours=5, minutes=30)))
    out = {str(now.year), str(now.month)}
    for k in (-2, -1, 0, 1, 2):
        out.add(str((now + _dt.timedelta(days=k)).day))
    return out


def _tamil_words(t):
    return [w for w in re.findall(r"[\u0B80-\u0BFF]+", t or "") if len(w) >= 4]


def _stem(w):
    return w.replace("\u0bc1\u0bbe", "\u0bc2")[:4]      # Dinamalar writes ூ as ுா ('வேலுார்' = 'வேலூர்')


def _initial(w):
    """the first letter of a word as papers abbreviate it: 'பரமத்தி' -> 'ப', 'திருச்செங்கோடு' -> 'தி'"""
    return w[:2] if len(w) > 1 and "\u0bbe" <= w[1] <= "\u0bcd" else w[:1]


def _initials(article):
    """{('ப', stem of 'வேலுார்')} for every 'ப.வேலுார்' in the article (owner 2 Nov, RN-284: 'பரமத்தி வேலூர்' was 'not in the article')"""
    return {(m.group(1), _stem(m.group(2))) for m in re.finditer(r"(?<![\u0B80-\u0BFF])([\u0B85-\u0BB9][\u0BBE-\u0BCD]?)\.\s*([\u0B80-\u0BFF]{3,})", article or "")}


NO_PLACE = re.compile(r"விவரம்|தெரியவில்லை|இல்லை|குறிப்பிடப்பட|unknown", re.I)
NOT_A_PLACE = {"மாவட்டம்", "மாவட்டத்தில்", "மாவட்ட", "அருகே", "அருகில்", "பகுதி", "பகுதியில்", "பகுதிகள்", "மற்றும்"}


def place_words(loc):
    """the town / village / area words of slides_spec.loc ('பள்ளிப்பாளையம், குமாரபாளையம்' -> both; 'நாமக்கல் மாவட்டம்' -> district only)"""
    return [w for w in re.findall(r"[\u0B80-\u0BFF]+", loc or "") if len(w) >= 3 and w not in NOT_A_PLACE]


def district_only(loc):
    return bool(re.search(r"மாவட்ட", loc or "")) and len(place_words(loc)) <= 1 and "," not in (loc or "")


def names_place(text, loc):
    t = (text or "").replace("\u0bc1\u0bbe", "\u0bc2")
    return any(_stem(w) in t for w in place_words(loc))


def place_problems(d):
    """owner 2 Nov: people share news of THEIR area - the place is on the first screen. loc = the town / village / area (never only the
    district, never 'not known'); hl1 / hl2 (the headline the reel opens with) name that place"""
    sp = d.get("slides_spec") or {}
    loc = sp.get("loc", "") if isinstance(sp, dict) else ""
    if not loc.strip() or NO_PLACE.search(loc):
        return []      # reported by grounding_problems
    if district_only(loc):
        return [f"slides_spec.loc '{loc}' is only the district: write the town / village / area the article names (people share news of their own area)"]
    if not names_place(sp.get("hl1", "") + " " + sp.get("hl2", ""), loc):
        return [f"hl1 (the first headline on screen) must name the place '{loc.split(',')[0].strip()}', e.g. '{loc.split(',')[0].strip()}: ...' or "
                f"'{loc.split(',')[0].strip()}-இல் ...' - viewers share news of their own area"]
    return []


def grounding_problems(d, article):
    """a draft built from the article re-uses the article's words. Invented places/garbled words do not appear in it."""
    art_words = _tamil_words(article)
    try:      # owner 2 Nov (review): 'கு.பாளையம்' / 'மே.பாளையம்' in the article = 'குமாரபாளையம்' / 'மேட்டுப்பாளையம்' in the draft
        import names
        art_words = art_words + _tamil_words(names.full_places(article))
    except Exception:
        pass
    stems = {_stem(w) for w in art_words}
    out = []
    # 1) the place named in the headline / location must be in the article
    for fld in ("tamil_headline",):
        for w in _tamil_words(d.get(fld, ""))[:3]:
            if re.search(r"(ூர்|புரம்|பாளையம்|பட்டி|பேட்டை|கோடு|மலை|நகர்|பாளை|ம்பட்டி)", w) and _stem(w) not in stems:
                out.append(f"not grounded: place word '{w}' is not in the article")
    loc = (d.get("slides_spec") or {}).get("loc", "")
    if NO_PLACE.search(loc):      # owner 2 Nov (RN-289: loc 'விவரம் இல்லை') - a location never says that it is not known
        out.append(f"not grounded: location '{loc}' is not a place: write the town or village the article names (never 'விவரம் இல்லை' / unknown)")
        loc = ""
    loc_words = re.findall(r"[\u0B80-\u0BFF]+", loc)
    inits = _initials(article)
    for i, w in enumerate(loc_words):
        if len(w) < 4 or (i + 1 < len(loc_words) and (_initial(w), _stem(loc_words[i + 1])) in inits):
            continue      # 'பரமத்தி வேலூர்' when the article writes 'ப.வேலுார்'
        if _stem(w) not in stems and w not in ("மாவட்டம்", "கோவை", "கோயம்புத்தூர்"):
            out.append(f"not grounded: location '{w}' is not in the article")
    # 2) most words of the reel script and slides must come from the article
    body = LAST
    rs = (d.get("reel_script") or "").replace(body, "")
    sl = " ".join(l for s_ in (d.get("slides_spec") or {}).get("slides", []) for l in s_.get("lines", []))
    words = _tamil_words(rs + " " + _tags(sl))
    if words:
        miss = [w for w in words if _stem(w) not in stems]
        ratio = 1 - len(miss) / len(words)
        if ratio < 0.5:
            out.append(f"not grounded: only {int(ratio*100)}% of the words come from the article (e.g. {', '.join(miss[:5])}); use the article's own words and facts")
    return out


DANGLING = re.compile(r"(க்|ச்|த்|ப்)$")      # a Tamil word ending in a doubling consonant always runs into the next word


def _cut(text, n):
    """shorten to at most n characters at a word boundary (keeps the words that fit; the facts stay whole)"""
    t = (text or "").strip()
    if len(t) <= n:
        return t
    c = t[:n]
    c = (c[:c.rfind(" ")] if " " in c else c).rstrip(" ,;:-")
    while " " in c and DANGLING.search(c):      # 29 Oct RN-34 'சிறந்த 3 இறுதிப்': never end on a word that joins the next one
        c = c[:c.rfind(" ")].rstrip(" ,;:-")
    return c


def autofix(d):
    """Small mechanical repairs of a draft, done BEFORE the checks, so a fine story is not thrown away for a length or a label.
    It never adds or changes a fact: it only shortens lines at a word boundary, fixes the version number and the page label."""
    if not isinstance(d, dict):
        return d
    sp = d.get("slides_spec")
    if isinstance(sp, dict):
        sp["v"] = 3
        sp["hl1"] = _cut(sp.get("hl1", ""), 40)
        loc_ = str(sp.get("loc") or "")
        town = loc_.split(",")[0].strip()
        if town and place_words(town) and not NO_PLACE.search(loc_) and not district_only(loc_) \
                and ":" not in sp["hl1"] and not names_place(sp["hl1"] + " " + str(sp.get("hl2") or ""), loc_) and len(town) + 2 + len(sp["hl1"]) <= 40:
            sp["hl1"] = f"{town}: {sp['hl1']}"      # owner 2 Nov: the place is in the first headline on screen
        sp["hl2"] = _cut(sp.get("hl2", ""), 28)
        sl = sp.get("slides") or []
        sl = sl[:4]
        for x in sl:
            tt = x.get("title", "")
            if len(_tags(tt)) > 18:
                x["title"] = _cut(tt, 18)
            ln = x.get("lines") or []
            x["lines"] = [_cut(l, 60) if len(_tags(l)) > 60 else l for l in ln[:3]]
        sp["slides"] = sl
    d["post_to"] = PAGE      # single page: always Coimbatore 360 (no collab)
    sc = d.get("scenes")
    if isinstance(sc, str) and sc.strip():
        d["scenes"] = [sc.strip()]
    elif isinstance(sc, list):
        d["scenes"] = [x for x in sc if isinstance(x, str) and x.strip()][:2]      # Coimbatore: exactly ONE image prompt per story
    return d


META = ["கட்டுரை", "தகவல் இல்லை", "விவரம் இல்லை", "தெரியவந்ததும் பகிரப்படும்", "தொடர்புடையது அல்ல", "செய்தியில் இல்லை",
        "குறிப்பிடப்படவில்லை", "the article", "this article", "not mentioned in", "no information"]


def _reach():
    """owner 29 Oct views plan: poster/config.json "reach" switches ({} = the old behaviour)"""
    try:
        from pathlib import Path
        return json.loads((Path(__file__).resolve().parent.parent / "poster" / "config.json").read_text(encoding="utf-8")).get("reach") or {}
    except Exception:
        return {}


def _power_cut():
    """owner 30 Oct: poster/config.json "power_cut" limits ({} = a power cut has the normal limits)"""
    try:
        from pathlib import Path
        return json.loads((Path(__file__).resolve().parent.parent / "poster" / "config.json").read_text(encoding="utf-8")).get("power_cut") or {}
    except Exception:
        return {}


def caption_problems(cap, reach=None):
    """the caption carries the FULL story (viewers ask for 'full details') and one English search line"""
    reach = _reach() if reach is None else reach
    p = []
    lines = [l.strip() for l in str(cap or "").split("\n")]
    if reach.get("caption_full_details"):
        if not any("முழு விவரம்" in l for l in lines):
            p.append('caption has no "📰 முழு விவரம்:" block - put the whole story (every fact) in the caption')
        else:
            i = next(k for k, l in enumerate(lines) if "முழு விவரம்" in l)
            body = [l for l in lines[i + 1:] if len(l.split()) >= 4 and not l.startswith("#")]
            if len(body) < 3:
                p.append("caption full details are too short - at least 3-4 sentences with every fact of the article")
    return p      # the English search line is ADDED at posting when missing (poster/post.py final_caption) - no rewrite needed


def _stems4(t):
    return {w[:4] for w in re.findall(r"[\u0B80-\u0BFF]{4,}", t or "")}


GENERIC4 = {"நாமக்", "மாவட", "கோவை", "கோயம", "ராசி", "இராச", "செய்", "தெரி", "இந்த", "அந்த", "பகுத", "மேலு", "நடைப", "வருக", "உள்ள", "என்ற",
            "அதிக", "போலீ", "தமிழ", "அரசு", "மக்க", "இதனா", "அருக", "நகரா", "ஊராட"}


def caption_missing_facts(cap, article, story):
    """owner 29 Oct: the caption must hold ALL the information of the news. Every number and place in the article sentences that are
    about THIS story (they share 2+ words with the headline / script - other headlines on the same web page are ignored) must be in the caption."""
    if not article or not cap:
        return []
    ref = _stems4(story) - GENERIC4      # district / filler words link every headline on a page - they do not mark THIS story
    capd = set(n.replace(",", "") for n in re.findall(r"\d[\d,]*", cap))
    try:
        import allnews
        places = [w for w in getattr(allnews, "COIMBATORE_WORDS", None) or getattr(allnews, "NAMAKKAL_WORDS", []) if not w.isascii()]
    except Exception:
        places = []
    miss = []
    for sent in re.split(r"(?<=[.!?])\s+|\n+", article[:4000]):
        sent = re.sub(r"^[\u0B80-\u0BFF.\s]+,\s*[\u0B80-\u0BFF]+\.?\s*\d{1,2}\s*:", "", sent.strip())      # dateline 'சேந்தமங்கலம், அக்.29:'
        if len(ref & _stems4(sent)) < 3:
            continue
        for n in re.findall(r"\d[\d,]*", sent):
            k = n.replace(",", "")
            if k in ("0", "00") or (len(k) == 4 and k.startswith("20")) or k in capd:
                continue
            miss.append(f"{n} ('{sent.strip()[:60]}')")
        for w in places:
            stem = w[:-1] if w.endswith("ம்") else w
            if stem in sent and stem not in cap:
                miss.append(f"{w} ('{sent.strip()[:60]}')")
    return list(dict.fromkeys(miss))



# owner 31 Oct: what finally happened, as the article's last lines tell it - a reel must never stop before the end of the story.
# Matched by MEANING (any verb form: விடுவித்தனர் / விடுவிக்கப்பட்டது / விடுவத்தனர் are all 'released')
OUTCOME = {"complaint": r"புகார்", "promise": r"உறுதியளி|உறுதி\s*அளி|உறுதி\s*கூறி", "released": r"விடுவி|விடுவத்|விடுதலை",
           "arrest": r"கைது", "case": r"வழக்குப்?\s*பதிவு", "jail": r"சிறையில்\s*அடை", "seizure": r"பறிமுதல்", "fine": r"அபராத",
           "rescue": r"மீட்க|மீட்ட", "order": r"உத்தரவிட்|உத்தரவு\s*பிறப்பி", "action": r"நடவடிக்கை", "traffic": r"போக்குவரத்து\s*(?:பாதி|சீரா|நெரிசல்)",
           "handed": r"ஒப்படை", "dispersed": r"கலைந்து", "fire_out": r"தீயை\s*அணை|தீ\s*அணைக்கப்", "treatment": r"சிகிச்சை", "death": r"உயிரிழ|பலியான"}


def _outcomes(t):
    return {k for k, p in OUTCOME.items() if re.search(p, t or "")}


def ending_missing(script, article):
    """'' or the article's ending sentence when it tells an outcome and the reel script mentions none of it"""
    sents = [x.strip() for x in re.split(r"(?<=[.!?])\s+", (article or "").strip()) if len(x.strip()) > 15]
    want = _outcomes(" ".join(sents[-2:]))
    return sents[-1] if want and not (want & _outcomes(script)) else ""


def validate(d, article, today_digits=("2026",)):
    p = []
    if not isinstance(d, dict):
        return ["output is not a JSON object"]
    for k in KEYS:
        if not d.get(k):
            p.append(f"missing key: {k}")
    if p:
        return p
    # 29 Oct (Namakkal RN-189, owner deleted it): the paper's page had no news, and the model wrote ABOUT the article ("the price is not
    # given in this article ... will be shared when known") and mixed in another story. A news reel never talks about "the article".
    for k in ("reel_script", "caption", "tamil_headline"):      # 29 Oct RN-20: 'ச監獄탈옥 ... பயிற்சি' - Chinese / Korean / Bengali letters in Tamil text
        bad = re.findall(r"[\u0980-\u0AFF\u0C00-\u0DFF\u3000-\u9FFF\uAC00-\uD7AF\u0400-\u04FF\u0600-\u06FF]", str(d.get(k) or ""))
        if bad:
            p.append(f"{k} has letters of another script ({''.join(bad[:4])}) - write only Tamil (and English names)")
    for k in ("reel_script", "caption", "tamil_headline"):
        t = re.sub(r"கட்டுரைப்?\s*போட்டி", " ", str(d.get(k) or ""))      # an essay competition is real school news
        hit = [w for w in META if w.lower() in t.lower()]
        if hit:
            p.append(f"{k} talks about the article instead of the news ({hit[0]}) - if the article has no real news, return an empty reel_script")
    eng = sorted(set(re.findall(r"[A-Za-z]{2,}", str(d.get("reel_script") or ""))))
    if eng:      # 29 Oct RN-34: the voice drops every English letter ('FBN Global Summit' was not read at all)
        p.append(f"reel_script has English words ({', '.join(eng[:4])}) - the voice cannot read them; write them in Tamil letters")
    sp = d["slides_spec"]
    if sp.get("v") != 3:
        p.append("slides_spec.v must be 3")
    sl = sp.get("slides") or []
    if not 3 <= len(sl) <= 4:
        p.append("slides must have 3 or 4 items")
    if len(sp.get("hl1", "")) > 40:
        p.append("hl1 longer than 40 characters")
    if len(sp.get("hl2", "")) > 28:
        p.append("hl2 longer than 28 characters")
    for i, s in enumerate(sl, 1):
        if len(_tags(s.get("title", ""))) > 18:
            p.append(f"slide {i} title longer than 18 characters")
        ln = s.get("lines") or []
        if not 2 <= len(ln) <= 3:
            p.append(f"slide {i} must have 2-3 lines")
        for j, l in enumerate(ln, 1):
            if len(_tags(l)) > 60:
                p.append(f"slide {i} line {j} longer than 60 characters")
            if DANGLING.search(_tags(l).strip(" .,;:")):
                p.append(f"slide {i} line {j} is cut off mid-phrase ('{_tags(l)[-20:]}') - write a complete short phrase")
    # scenes: exactly ONE image prompt (the main scene of this news); the reel moves the camera over that one picture
    sc = d.get("scenes")
    if not isinstance(sc, list) or not 1 <= len(sc) <= 2 or not all(isinstance(x, str) and len(x.strip()) >= 40 for x in sc):
        p.append("scenes must be a list of TWO clear English image prompts (1: the main scene of this news, 2: a detail of it; each at least 40 characters)")
    rs = d["reel_script"].strip()
    if re.search(r"[A-Za-z]", rs):
        p.append("reel_script must have no English letters (write English words and abbreviations in Tamil script)")
    if not rs.endswith(LAST):
        p.append("reel_script must end with exactly: " + LAST)
    wc = len(rs.split())
    maxw = int(_reach().get("script_max_words") or 170)      # owner 29 Oct: reels at most 60 s (105 words); the caption keeps every detail
    need = min(130, int(len(_tamil_words(article)) * 0.55)) if article else 60      # owner 28 Oct: full detail - a longer article needs a longer reel
    need = min(need, maxw - 20, 100)      # owner 31 Oct: up to 90 s for the full news, but a long article never FORCES more than ~100 words
    import freshness
    if freshness.is_power_cut(d.get("tamil_headline"), d.get("english_headline"), d.get("category")):      # owner 30 Oct: a power cut reads EVERY area (up to 90 s)
        maxw = int(_power_cut().get("script_max_words") or maxw)      # only the upper limit grows; the minimum stays the normal one
    if not max(60, need) <= wc <= maxw + 5:
        p.append(f"reel_script has {wc} words; need {max(60, need)}-{maxw} (the key facts once each, in at most {60 if maxw <= 110 else 90} seconds; "
                 "every other detail goes in the caption's 📰 முழு விவரம் block)")
    ages = re.findall(r"[\u0B80-\u0BFF]+,\s?\d{1,2},", rs)
    if ages:      # owner 28 Oct (RN-158): "ராஜா, 12," is newspaper shorthand; read aloud it is confusing
        p.append(f"reel_script writes ages as newspaper shorthand ({', '.join(ages[:3])}); say it as a news reader: '12 வயது மகன் ராஜா', 'கவுசிக் (14 வயது)' -> '14 வயதான கவுசிக்'")
    end = ending_missing(rs, article)
    if end:      # owner 31 Oct (RN-241 stopped before 'the depot manager promised action, the bus was released, 15 min traffic'): tell how it ended
        p.append(f"reel_script must tell how the story ENDED, as the article's last lines say ('{end[:160]}') - say what finally happened "
                 "(complaint, action promised, released, arrested, case filed, how long it lasted); never write that details are unknown")
    first = rs.split(".")[0].split()
    if len(first) > 11:      # owner 28 Oct: the one-line story is heard in the first 2-3 seconds, then the explanation
        p.append(f"sentence 1 (one-line story) has {len(first)} words; make it 6-9 words (about 2-3 seconds), the details follow in the next sentences")
    MONTHS = "ஜனவரி|பிப்ரவரி|மார்ச்|ஏப்ரல்|மே|ஜூன்|ஜூலை|ஆகஸ்ட்|செப்டம்பர்|அக்டோபர்|நவம்பர்|டிசம்பர்"
    bare = [m.group(0).strip() for m in re.finditer(r"(?:^|[\s,(])(\d{1,3}(?:,\d{3})*)(?=\s*[,.)](?:\s|$))", rs)
            if not re.search(rf"({MONTHS}|வயது)[\s\d,]*$", rs[max(0, m.start(1) - 30):m.start(1)])]      # "அக்டோபர் 13, 14, 15", "வயது 40" are clear
    if bare:      # owner 28 Oct: "ஸ்ரீதர், 15," - a number with no word is not understood when it is heard
        p.append(f"reel_script has numbers without their meaning ({', '.join(bare[:4])}); write what each number is: '15 வயது', '30 பாட்டில்கள்', 'அக்டோபர் 26ஆம் தேதி'")
    if "வணக்கம்" in rs.split(".")[0]:
        p.append("reel_script must not start with a greeting")
    cap = d["caption"]
    if FOLLOW not in cap:
        p.append("caption must contain the exact follow line")
    tags = re.findall(r"#\S+", cap)
    if not 3 <= len(tags) <= 5:
        p.append(f"caption needs 5 hashtags (Instagram max), has {len(tags)}")
    if d.get("importance") not in ("High", "Medium", "Low"):
        p.append("importance must be High, Medium or Low")
    if d["post_to"] != PAGE:
        p.append(f"post_to must be '{PAGE}'")
    blob = json.dumps(d, ensure_ascii=False).lower()
    hits = [o for o in OUTLETS if o.lower() in blob]
    if hits:
        p.append("source/outlet name or link appears: " + ", ".join(hits[:3]))
    if re.search(r"AI (image|generated)|AI பிரதிநிதித்துவ", blob, re.I):
        p.append("no AI-image notes allowed")
    # every number must come from the article
    src = {_num(n) for n in _digits_in(article) | _scaled_digits(article) | set(today_digits) | _calendar_digits() | {"1", "2", "3", "4", "5"}}
    text = " ".join([d["tamil_headline"], d["english_headline"], _tags(json.dumps(sp, ensure_ascii=False)), cap.split("#")[0], rs])      # the spoken script too
    stray = sorted(n for n in _digits_in(text) if _num(n) not in src and _num(n) not in ("0", "360"))
    if stray:
        p.append("numbers not found in the article: " + ", ".join(stray[:6]))
    p += grounding_problems(d, article)
    p += place_problems(d)
    blob_all = " ".join([d.get("tamil_headline", ""), rs, cap, json.dumps(sp, ensure_ascii=False)])
    foreign = sorted(set(re.findall(r"[\u0900-\u0B7F\u0C00-\u0D7F\u3040-\u30FF\u3400-\u9FFF\uAC00-\uD7AF]", blob_all)))
    if foreign:      # owner 29 Oct: letters of another script inside Tamil words (Coimbatore RN-5, RN-20 ...)
        p.append("letters of another script inside Tamil words: " + " ".join(foreign[:8]) + " - write every word only in Tamil letters")
    try:
        from verify import tamil_sequence_problems
        for t in [d["tamil_headline"], rs, _tags(cap)]:
            p += tamil_sequence_problems(t) or []
    except Exception:
        pass
    p += caption_problems(d.get("caption"))
    if _reach().get("caption_all_facts"):
        miss = caption_missing_facts(d.get("caption"), article, " ".join(str(d.get(k) or "") for k in ("tamil_headline", "reel_script")))
        if miss:
            p.append("caption misses facts of the article (put every one in 📰 முழு விவரம்): " + "; ".join(miss[:6]))
    try:      # owner 29 Oct: every known issue is checked here AND right before posting (research_free/known_issues.py)
        import known_issues
        seen = " ".join(p)
        for iid, why in known_issues.problems(d):
            if why not in seen:
                p.append(f"known issue {iid}: {why} - rewrite so it does not happen again")
    except ImportError:
        pass
    return p
