"""owner 28 Nov: 40 hashtags on every YouTube Short (YouTube allows 60; past 60 it ignores all of them):
  25 for the video itself (its topic, its own tags and keywords), 5 for the page, 5 for the district, 5 for the area the news is from.
The first line of the description stays "#<Page> #TamilNews #Shorts" (YouTube shows the first 3 above the title); those 3 are counted
in the 40, and the two tags the description had before (#<Page>News, #<Page>360) are always kept.
Every tag comes from the page's own lists (config.json "reach"), the news's own place and its keyword line - a tag is never a
free guess. Sensitive news (crime, accident, death) gets no topic tags, as with the keywords (owner 26 Nov).
Only the YouTube description uses this: the title, the hidden Tags, Instagram and Facebook are not touched.
Switch off: config.json "youtube_hashtags": false (the old "#<Page>News #<Page>360" line comes back)."""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SLOTS = {"video": 25, "page": 5, "district": 5, "area": 5}      # owner 28 Nov: "video related 25, page 5, district 5, area 5"
TOTAL = sum(SLOTS.values())      # 40 (YouTube's limit is 60)
HASH = re.compile(r"#[^\s#]+")
TAMIL = re.compile(r"[஀-௿]")
DISTRICT_TA = {"namakkal": "நாமக்கல்", "rasipuram": "நாமக்கல்", "coimbatore": "கோவை", "salem": "சேலம்", "erode": "ஈரோடு", "karur": "கரூர்",
               "tirupur": "திருப்பூர்", "trichy": "திருச்சி"}
HOME_TA = {"rasipuram": "ராசிபுரம்"}      # a page for one town, not for a whole district
NOT_A_DISTRICT = ("#tamilnadu", "#tamilnews")
# The topic tags follow the news's OWN keyword line (post.py keywords_for: the English topic keyword names the kind of news). A news
# with no topic keyword - sensitive news (a death, a crime, a court case: owner 26 Nov) or an unknown kind - gets general news tags
# only: a guessed topic gave farming tags to a lorry accident.
KIND_TAGS = {
    "power cut today": ["#PowerCut", "#மின்தடை", "#PowerShutdown", "#TNEB", "#PowerCutToday", "#மின்நிறுத்தம்", "#PowerCutAlert", "#TNPDCL",
                        "#PowerCutNews", "#மின்வாரியம்", "#ElectricityBoard", "#PowerOutage", "#மின்தடைஅறிவிப்பு", "#ShutdownAlert", "#PowerSupply"],
    "job alert": ["#Jobs", "#வேலைவாய்ப்பு", "#JobAlert", "#TNJobs", "#Employment", "#JobNews", "#வேலை", "#JobOpportunity", "#Recruitment",
                  "#JobSeekers", "#வேலைவாய்ப்புசெய்திகள்", "#Careers", "#JobUpdates", "#TamilNaduJobs"],
    "weather update": ["#Rain", "#மழை", "#RainAlert", "#Weather", "#வானிலை", "#WeatherUpdate", "#TNRains", "#RainNews", "#WeatherNews",
                       "#TNWeather", "#மழைசெய்திகள்", "#WeatherAlert", "#TamilNaduWeather", "#வானிலைஅறிக்கை", "#RainUpdate"],
    "farmers news": ["#Farmers", "#விவசாயம்", "#Agriculture", "#விவசாயிகள்", "#AgriNews", "#Farming", "#TNFarmers", "#விவசாயசெய்திகள்",
                     "#AgricultureNews", "#உழவர்", "#Crops", "#TamilNaduFarmers", "#FarmingNews"],
    "politics news": ["#Politics", "#அரசியல்", "#TNPolitics", "#PoliticalNews", "#TamilNaduPolitics", "#TNPoliticalNews", "#PoliticalUpdate",
                      "#தமிழகஅரசியல்", "#PoliticsToday", "#TNPoliticsToday"],
    "government notice": ["#GovernmentNotice", "#அரசுஅறிவிப்பு", "#Government", "#அரசு", "#PublicNotice", "#GovtNews", "#TNGovt",
                          "#GovernmentNews", "#அரசுசெய்திகள்", "#TamilNaduGovernment", "#GovtUpdates", "#PublicInformation"],
    "district administration": ["#DistrictAdministration", "#அரசுசெய்திகள்", "#Government", "#அரசு", "#GovtNews", "#PublicNews", "#Administration",
                                "#மாவட்டநிர்வாகம்", "#TNGovt", "#GovernmentNews", "#PublicService", "#GovtUpdates"],
    "education news": ["#Education", "#கல்வி", "#Students", "#மாணவர்கள்", "#EducationNews", "#கல்விசெய்திகள்", "#TNEducation", "#StudentNews",
                       "#Learning", "#EducationUpdates", "#TamilNaduEducation", "#Student"],
    "health news": ["#Health", "#மருத்துவம்", "#HealthNews", "#உடல்நலம்", "#HealthCare", "#PublicHealth", "#Medical", "#சுகாதாரம்",
                    "#HealthUpdate", "#TNHealth", "#MedicalNews", "#HealthAwareness"],
    "price today": ["#PriceToday", "#விலைநிலவரம்", "#MarketPrice", "#MarketNews", "#Business", "#வணிகம்", "#TodayPrice", "#இன்றையவிலை",
                    "#MarketRate", "#PriceUpdate", "#BusinessNews", "#சந்தைநிலவரம்"],
    "civic issue": ["#CivicIssues", "#மக்கள்பிரச்சினை", "#PublicIssue", "#CivicNews", "#மக்கள்குரல்", "#PublicNews", "#PeopleIssues",
                    "#PublicProblems", "#பொதுமக்கள்", "#CitizenVoice", "#LocalIssues", "#PublicVoice"],
    "traffic update": ["#Traffic", "#போக்குவரத்து", "#TrafficUpdate", "#Roads", "#சாலை", "#TransportNews", "#TrafficNews", "#Transport",
                       "#RoadNews", "#போக்குவரத்துசெய்திகள்", "#TrafficAlert", "#Commute"],
    "local events": ["#LocalEvents", "#நிகழ்ச்சி", "#Events", "#விழா", "#CommunityEvents", "#Culture", "#EventNews", "#நிகழ்வுகள்", "#Community",
                     "#CulturalEvents", "#LocalCulture", "#EventUpdates"],
    "wildlife news": ["#Wildlife", "#வனவிலங்கு", "#WildlifeNews", "#Forest", "#வனத்துறை", "#Nature", "#ForestDepartment", "#WildAnimals",
                      "#வனம்", "#WildlifeAlert", "#Environment", "#ForestNews"],
    "fire safety": ["#FireSafety", "#தீவிபத்து", "#FireService", "#தீயணைப்பு", "#SafetyAlert", "#FireNews", "#FireAndRescue",
                    "#தீயணைப்புத்துறை", "#Safety", "#FireAlert"],
}
KIND_TA = {"மின்தடை": "power cut today", "வேலைவாய்ப்பு": "job alert", "மழை எச்சரிக்கை": "weather update", "விவசாயம்": "farmers news",
           "அரசியல் செய்திகள்": "politics news", "அரசு அறிவிப்பு": "government notice", "அரசு செய்திகள்": "district administration",
           "கல்வி செய்திகள்": "education news", "மருத்துவம்": "health news", "விலை நிலவரம்": "price today", "மக்கள் பிரச்சினை": "civic issue",
           "போக்குவரத்து": "traffic update", "நிகழ்ச்சி": "local events", "வனவிலங்கு": "wildlife news", "தீ விபத்து": "fire safety"}      # a long keyword line keeps only the Tamil word of the pair
NO_KEYWORD_LINE = {"power_cut": "power cut today", "jobs": "job alert"}      # a caption from before the keyword line: only these two sure topics
NOT_A_PLACE = ("தமிழ்நாடு", "தமிழகம்", "இந்தியா", "tamil nadu", "tamilnadu", "india")      # a state-wide news has no town of its own
RASI = ["#RasiPalan", "#ராசிபலன்", "#இன்றையராசிபலன்", "#TodayRasiPalan", "#Horoscope", "#DailyHoroscope", "#ஜோதிடம்", "#Astrology",
        "#RasiPalanToday", "#TamilHoroscope", "#DailyRasiPalan", "#தினராசிபலன்", "#Rasi", "#ராசி", "#Zodiac", "#TodayHoroscope",
        "#TamilAstrology", "#Jothidam", "#இன்றையராசி", "#HoroscopeToday", "#RasiPalanTamil"]
GOLD = ["#GoldRate", "#தங்கம்விலை", "#GoldRateToday", "#இன்றையதங்கம்விலை", "#SilverRate", "#வெள்ளிவிலை", "#GoldPrice", "#TodayGoldRate",
        "#தங்கம்", "#Gold", "#GoldPriceToday", "#SilverPrice", "#வெள்ளி", "#Silver", "#22KGold", "#24KGold", "#GoldRateTamilNadu",
        "#தங்கவிலை", "#GoldNews", "#Jewellery", "#நகை", "#GoldUpdate"]
GENERAL = ["#TamilNadu", "#தமிழ்நாடு", "#LocalNews", "#இன்றையசெய்திகள்", "#TamilNewsToday", "#தமிழ்செய்திகள்", "#உள்ளூர்செய்திகள்", "#NewsShorts",
           "#TamilShorts", "#TamilNaduNews", "#TodayNews", "#NewsUpdate", "#DistrictNews", "#YTShorts", "#ShortsNews", "#TamilNaduToday",
           "#TNNews", "#தமிழகம்", "#DailyNews", "#NewsToday", "#ShortsFeed", "#Tamil", "#தமிழ்", "#TamilUpdates", "#LocalUpdates",
           "#TamilNaduUpdates", "#NewsInTamil", "#TamilLocalNews", "#TodayTamilNews", "#இன்றையசெய்தி", "#தமிழ்நாடுசெய்திகள்", "#செய்திகள்",
           "#TamilNewsShorts", "#ShortNews", "#LatestNews", "#TamilNewsLive", "#தமிழகசெய்திகள்", "#NewsFeed"]
DAILY_GENERAL = ["#TamilNadu", "#தமிழ்நாடு", "#TamilShorts", "#YTShorts", "#Tamil", "#தமிழ்", "#DailyUpdate", "#ShortsFeed", "#தமிழகம்",
                 "#TamilUpdates", "#TamilNaduToday", "#DailyShorts"]
_CFG = None


def config():
    global _CFG
    if _CFG is None:
        try:
            _CFG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
        except Exception:
            _CFG = {}
    return _CFG


def clean(t):
    """one hashtag: letters, digits and Tamil only (a space, dot or dash ends a hashtag on YouTube); '' when nothing sensible is left"""
    t = re.sub(r"[^\w஀-௿]", "", str(t or "")).strip("_")
    if len(t) < 2 or len(t) > 32 or t.isdigit():
        return ""
    return "#" + t


def from_phrase(p):
    """a keyword phrase as one hashtag: 'power cut today' -> #PowerCutToday, 'இன்றைய செய்திகள்' -> #இன்றையசெய்திகள்"""
    words = re.sub(r"\s+", " ", str(p or "")).strip().split(" ")
    if TAMIL.search(p or ""):
        return clean("".join(words))
    return clean("".join(w if any(c.isupper() for c in w) else w.capitalize() for w in words))


def profile(page, reach):
    for k, p in (reach.get("hashtag_profiles") or {}).items():
        if k.lower().lstrip("#").startswith(str(page).lower()):
            return p or {}
    return {}


def topic(head):
    try:
        sys.path.insert(0, str(HERE.parent / "research_free"))
        import learned
        return learned.topic(head or "")
    except Exception:
        return "other"


def _place_keyword(kws, generic):
    """the news's own place from the keyword line: its first keyword is '<place> news' / '<place> செய்திகள்' when the news names a place"""
    k = kws[0] if kws else ""
    stem = re.sub(r"\s+(news|செய்திகள்)$", "", k, flags=re.I).strip()
    if (stem == k or not stem or len(stem.split()) > 2 or stem.lower() in generic or stem.lower() in NOT_A_PLACE
            or re.search(r"district|மாவட்ட|\d", stem, re.I)):
        return "", ""
    return stem, k


def build(cap, page, name, head="", cfg=None):
    """{"video": [...25], "page": [...5], "district": [...5], "area": [...5]} - 40 different hashtags for this reel"""
    cfg = config() if cfg is None else cfg
    reach = cfg.get("reach") or {}
    prof = profile(page, reach)
    if not prof:
        reach = {}      # a page this repo has no lists for: only tags from the page's own name and the news itself
    lines = [x.strip() for x in (cap or "").split("\n")]
    text = [re.sub(r"https?://\S+", "", l) for l in lines]      # a link's own '#part' is not a hashtag
    head = head or (lines[0] if lines else "")
    cap_tags = [t for t in (clean(x.rstrip(".,!")) for l in text for x in HASH.findall(l)) if t]
    kw_line = next((x for x in reversed(lines) if x.startswith("🔎")), "")      # the keyword line is the LAST 🔎 line (a news line can start with 🔎 too)
    kws = [w.strip() for w in kw_line.lstrip("🔎").split(",") if w.strip()]
    kws = [w for w in kws if len(w) <= 30 and len(w.split()) <= 4 and "." not in w]      # keyword phrases only, never a sentence
    body = "\n".join(l for l in text if l and not l.startswith(("#", "🔎", "📰")))
    daily = RASI if re.search(r"ராசிபலன்", cap or "") else GOLD if re.search(r"தங்கம்.{0,25}விலை|Gold ?rate", cap or "", re.I) else None

    home = "#" + name      # the tag the first line of the description already has
    district = reach.get("district_tag") or home
    extra = reach.get("extra_tag") or ""
    district_page = not reach or home.lower() in (district.lower(), extra.lower())
    d_en = district.lstrip("#")
    d_ta = DISTRICT_TA.get(page) or str(prof.get("tamil") or "").lstrip("#")
    h_ta = HOME_TA.get(page) or (d_ta if district_page else str(prof.get("tamil") or "").lstrip("#"))

    used, out = set(), {g: [] for g in SLOTS}

    def take(group, cands, limit=None):
        limit = SLOTS[group] if limit is None else limit
        for c in cands:
            t = clean(c)
            if t and t.lower() not in used and len(out[group]) < limit:
                used.add(t.lower())
                out[group].append(t)

    take("district" if district_page else "area", [home])      # the first line: #<Page> #TamilNews #Shorts
    take("video", ["#TamilNews", "#Shorts"])

    take("page", [f"{home}360", prof.get("page"), f"{home}360News", f"#{h_ta}360" if h_ta else "", f"{home}360Official",
                  f"{home}360Shorts", f"{home}360Updates", f"{home}360Tamil", f"{home}360Channel"])

    alt = [t for t in (extra, prof.get("fallback") if district_page else "") if t and t.lower() not in NOT_A_DISTRICT]
    take("district", ([f"{home}News"] if district_page else []) +
         [district, f"#{d_en}News", f"#{d_ta}" if d_ta else "", prof.get("area") if district_page else "",
          prof.get("news") if district_page else "", reach.get("broad_tag")] + alt +
         [f"#{d_en}District", f"#{d_ta}செய்திகள்" if d_ta else "", f"#{d_ta}மாவட்டம்" if d_ta else "", f"#{d_en}Today",
          f"#{d_en}Updates", f"#{d_en}LocalNews", f"#{d_en}Shorts"])

    place_tags = reach.get("place_tags") or {}
    known = {str(v).lower() for v in place_tags.values()}
    named = [t for t in cap_tags if t.lower() in known]      # the town tag the Instagram caption already carries
    hits = sorted((body.find(k), -len(k), t) for k, t in place_tags.items() if k and k in body)
    named += [t for _, _, t in hits]      # other towns the news names (a power-cut list names many)
    pins = [x for x in lines if x.startswith("📍")]      # the place line is "📍 இடம்: <place>, ..." or the footer "📍 <place>, ... | <date>"
    loc = next((x for x in pins if re.match(r"📍\s*இடம்\s*:", x)), "") or next((x for x in pins if "|" in x), "")
    seg = re.split(r"[,|/]", re.sub(r"^📍\s*(இடம்\s*:)?", "", loc))[0].strip()
    ok = 2 < len(seg) <= 25 and len(seg.split()) <= 2 and not re.search(r"மாவட்ட|district|\d|:", seg, re.I) and seg.lower() not in NOT_A_PLACE
    t_place = seg.replace(" ", "") if ok and TAMIL.search(seg) else ""
    e_place = from_phrase(seg) if ok and not TAMIL.search(seg) and re.fullmatch(r"[A-Za-z. ]+", seg) else ""
    generic = {x.lower() for x in (name, d_en, d_ta, h_ta, home.lstrip("#"), "tamil nadu local", "இன்றைய") if x}
    stem, place_kw = _place_keyword(kws, generic)
    first = named[0] if named else e_place
    towns = []
    for v in place_tags.values():
        if v not in towns:
            towns.append(v)
    # a news with no town of its own (district-wide news, the daily reels) is about the page's home town: its own names, not other towns
    home_area = [f"{home}City" if district_page else f"{home}Town", f"#{h_ta}நகர்" if h_ta else "", f"{home}Local", f"{home}Area",
                 f"{home}Town", f"{home}CityNews", f"{home}LocalNews", f"{home}TownNews"]
    own_place = [e_place, from_phrase(stem), from_phrase(place_kw), f"#{t_place}செய்திகள்" if t_place else "",
                 f"{first}Today" if first else "", f"{first}Updates" if first else "", f"{first}LocalNews" if first else ""]
    many = len({t.lower() for t in named}) >= 3      # a list of towns (a power-cut notice): every town named comes before one town's extra tags
    take("area", ([f"{home}News", f"#{h_ta}" if h_ta else ""] if not district_page else []) +
         [first, t_place, f"{first}News" if first else ""] + (named[1:] + own_place if many else own_place + named[1:]) + home_area + towns)

    spoken_for = known | {t.lower() for g in ("page", "district", "area") for t in out[g]}
    own = [t for t in cap_tags if t.lower() not in spoken_for]      # the reel's own topic tags (#NamakkalPowerCut, #GoldRate ...)
    if daily:
        take("video", own + daily + DAILY_GENERAL)
    else:
        kind = (next((k.lower() for k in kws if k.lower() in KIND_TAGS), "") or next((KIND_TA[k] for k in kws if k in KIND_TA), "")
                or ("" if kw_line else NO_KEYWORD_LINE.get(topic(head), "")))
        names = [x.lower() for x in (name, d_en, d_ta, h_ta, "rasipuram", "ராசிபுரம்") if x]
        kw_tags = [from_phrase(k) for k in kws[1:] if not any(n in k.lower() for n in names)]      # the first keyword is the place
        take("video", own + KIND_TAGS.get(kind, []) + kw_tags + GENERAL)
    short = TOTAL - sum(len(v) for v in out.values())      # a group with too few tags of its own: general tags keep the count at 40
    if short > 0:
        take("video", DAILY_GENERAL + GENERAL if daily else GENERAL, len(out["video"]) + short)
    return out


def lines(cap, page, name, head="", cfg=None):
    """the hashtag lines for the end of the YouTube description (the first line's 3 tags are left out here - they stay on top).
    [] when it is switched off or the count is not exactly 40 - the description then keeps its old two tags."""
    cfg = config() if cfg is None else cfg
    if cfg.get("youtube_hashtags", True) is False:
        return []
    g = build(cap, page, name, head, cfg)
    tags = [t for k in SLOTS for t in g[k]]
    if len(tags) != TOTAL or len({t.lower() for t in tags}) != TOTAL:
        return []
    top = {("#" + name).lower(), "#tamilnews", "#shorts"}
    out = [" ".join(t for t in g[k] if t.lower() not in top) for k in ("district", "page", "area", "video")]
    return [x for x in out if x]
