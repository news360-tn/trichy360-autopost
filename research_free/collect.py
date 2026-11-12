"""Every-3-hours collector (free models). Fetch Coimbatore-district news for the ONE page Coimbatore 360 -> write posts -> validate -> send to the Apps Script bridge
(Sheet rows + ONE prompt file + ONE email). Usage: python research_free/collect.py [--dry]"""
import datetime, difflib, json, os, random, re, sys, time
from pathlib import Path
import requests
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import llm, run, allnews

IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
BRIDGE_URL, BRIDGE_KEY = os.environ.get("BRIDGE_URL", ""), os.environ.get("BRIDGE_KEY", "")
def _slot_count():
    """stories per round: no practical limit (owner 25 Oct: every news published today in the district is written and posted, priority first)"""
    return 200


SET_NEWS = int(os.environ.get("SET_NEWS_COUNT", "0") or 0) or _slot_count()
PAGE_NAME = "Coimbatore 360"      # post_to value in the Sheet (the only page; no second page, no collab)
AREA = allnews.AREA          # "N" = the Coimbatore 360 page (the only area code)
MAX_STORIES = int(os.environ.get("MAX_STORIES", "0") or 0) or SET_NEWS       # Coimbatore 360: district news per round
ARCHIVE = HERE / "archive"
DRY = "--dry" in sys.argv
IMG_BUDGET = int(os.environ.get("IMG_BUDGET_MIN", "22")) * 60
IMG_MAX = int(os.environ.get("IMG_MAX_PER_RUN", "40"))     # credit guard: at most this many automatic images per run     # minutes spent on automatic images per send
DEADLINE = time.time() + int(os.environ.get("BUDGET_MIN", "22")) * 60
llm.DEADLINE[0] = DEADLINE

TEMPLATE = ("ONE single continuous photograph from one camera angle (not a collage, grid, strips or panels). Ultra-sharp photorealistic documentary-style news photo, tall vertical portrait (9:16 if possible, highest resolution), "
            "MAXIMUM CLARITY: 4K, tack-sharp focus across the whole frame, deep depth of field, shot like a professional full-frame camera with a 35mm lens at f/8, crisp fine detail and edges, clean noise-free image, balanced high dynamic range, natural lighting; no blur, no soft focus, no motion blur, no haze, no painterly, plastic or over-smoothed AI look. {scene} "
            "Natural colours, realistic light, sharp detail, modern news-photography look. STRICT: no text, letters, numbers, signboard writing, logos or watermarks anywhere in the image; "
            "no recognisable real person, politician or celebrity face (show people only from behind, far away or blurred); no blood, injuries or dead bodies. "
            "Keep the top-right corner and the lower third of the image visually simple (sky, road, wall, field) because Tamil text will be placed there.")


BRIEF_SYSTEM = """You are the photo editor of a Tamil local-news page for COIMBATORE CITY, Tamil Nadu, India. You plan the ONE photograph that illustrates ONE news story,
so that a reader who sees only the picture already knows WHICH news it is.
You get the English headline, place, category and the article text. Work in two steps and return both.

STEP 1 - "facts": read the article and list ONLY what a camera could see, copied in meaning from the article:
 what happened (the event itself), the exact place and its type, the people by role and their number, vehicles (exact type and colour if given),
 objects (seized goods, damaged things, tools), animals, buildings, weather, time of day. Write "unknown" for anything the article does not say. Never invent.

STEP 2 - "scenes": exactly TWO photographs of THIS news (owner 30 Oct: 2 pictures per reel): scene 1 = the COVER - the main event itself;
 scene 2 = a DETAIL close-up of the one object or sign that tells the story (seized goods, the damaged vehicle, the transformer, the garbage
 heap, water on the road, the documents) or, if there is no such object, a WIDE shot of the place with the event in it. Each scene
 100-150 words of plain English, written in THIS order:
 1. SUBJECT + ACTION: the main thing of THIS news happening, in the first sentence (e.g. "A TNEB lineman on a ladder repairs a transformer ...").
 2. PLACE: the real place type in Coimbatore city with its look (see CITY LOOK), named area if the article gives it.
 3. PEOPLE: by role, number, clothes, what each group is doing; seen from behind or far away.
 4. VEHICLES / OBJECTS: exact types from the article (two-wheeler, autorickshaw, town bus, lorry, car; seized ganja packets, liquor bottles,
    gold jewellery laid on a table; garbage heap; pothole; overflowing drain; water pots).
 5. TIME + LIGHT + WEATHER: from the article, else daylight.
 6. CAMERA: eye level or slightly high, 35 mm, wide enough to show the place.
 It MUST contain at least THREE concrete facts from STEP 1 (place type, action, objects, numbers) - never a generic scene.
CITY LOOK (Coimbatore city): Gandhipuram / Ukkadam / Singanallur bus stands with town buses, Avinashi Road and Trichy Road with flyovers and
 heavy traffic, Town Hall and R.S. Puram streets with shops, the Coimbatore Corporation office, Ukkadam and Valankulam lakes, the railway junction,
 Peelamedu and Saravanampatti IT and college campuses, textile mills and pump/foundry units, TNEB substations and transformers on concrete poles,
 Marudhamalai hill and the Western Ghats in the far background; two-wheelers, autorickshaws, private and TNSTC buses; men in shirts with veshti or
 trousers, women in sarees or salwar; Tamil Nadu police in khaki; corporation workers; TNEB linemen.
CATEGORY GUIDE: power cut = TNEB lineman on a pole or a substation, shops and a street without lights; crime = the place only (house exterior,
 police jeep, police station gate) or the seized goods on a table with police in khaki behind, never a body or a weapon at a person;
 accident = the damaged vehicles of the article on that road, police and onlookers at a distance, no injured people; civic = the problem itself
 (garbage heap on the roadside, pothole filled with rain water, overflowing drain, broken street light, people waiting with water pots,
 corporation workers fixing it); rain or flood = water on that road, vehicles wading; protest = a crowd with flags or placards seen from behind;
 government meeting or scheme = officials at a table in a government hall, people queuing; jobs = job seekers queuing at a hall or campus from
 behind; school = students in Tamil Nadu school uniform from behind; temple = the gopuram and devotees; wild elephant = elephants at the forest edge.
NEVER: readable text, letters, numbers, signboards, logos, brand or company names, product labels, watermarks, a recognisable face of any real person or politician, blood, injuries,
 dead bodies, weapons pointed at people, collages or split frames. People only from behind, far away or slightly blurred.
Return ONLY JSON: {"facts": "...", "scenes": ["cover scene", "detail scene"]}"""

# owner 29 Oct: the news scene comes FIRST (some image models read only the start of a long prompt), the photo style after it
IMG_TEMPLATE = ("{scene} "
                "Photorealistic press photograph from Coimbatore city, Tamil Nadu, India. One single continuous frame (no collage, no panels), "
                "tall vertical 9:16 composition, the main subject in the centre, full-frame camera, sharp focus across the frame, natural light, "
                "true-to-life colours, documentary photojournalism. No text, no letters, no numbers, no signboards, no logos, no watermarks, "
                "no brand names, no company logos, no product labels, no recognisable faces. Keep the lower third visually simple (road, wall, ground, sky).")

_STOP = {"the", "a", "an", "of", "in", "on", "at", "to", "for", "and", "with", "near", "by", "from", "as", "is", "are", "was", "were", "after",
         "over", "into", "coimbatore", "city", "kovai", "tamil", "nadu", "district", "news", "says", "said", "held", "two", "three", "four"}


def _key_words(t):
    return {w for w in re.findall(r"[a-z]{4,}", (t or "").lower()) if w not in _STOP}


def scene_ok(scene, headline):
    """the scene shows THIS news: long enough and it names at least two main words of the headline (or all when the headline is short)"""
    if len((scene or "").split()) < 60:
        return False
    need = _key_words(headline)
    if not need:
        return True
    have = _key_words(scene) | {w.rstrip("s") for w in _key_words(scene)}
    hit = sum(1 for w in need if w in have or w.rstrip("s") in have)
    return hit >= min(2, len(need))


def pictures_per_reel():
    """poster/config.json free_images.pictures_per_reel (owner 30 Oct: 2 on every page)"""
    try:
        return max(1, int(json.loads((HERE.parent / "poster" / "config.json").read_text(encoding="utf-8")).get("free_images", {}).get("pictures_per_reel", 1)))
    except Exception:
        return 1


def image_scenes(art, d):
    """ONE detailed image prompt (the main scene of this news) built from the article itself (not a generic scene); returns a 1-item list.
    owner 29 Oct: a scene that is too short or does not name the main things of the headline is sent back once."""
    user = f"HEADLINE: {d.get('english_headline', '')}\nPLACE: {d.get('location', '')}\nCATEGORY: {d.get('category', '')}\nARTICLE:\n{(art.get('text') or '')[:3000]}"
    best = []
    for attempt in range(2):
        try:
            data, _ = llm.ask_json(BRIEF_SYSTEM, user)
        except Exception:
            if not llm.claude_available():
                if best:
                    break
                raise
            data, _ = llm.ask_claude(BRIEF_SYSTEM, user, max_tokens=1500)
        sc = [s.strip() for s in (data.get("scenes") or []) if isinstance(s, str) and len(s.strip()) > 40][:pictures_per_reel()]
        if sc and scene_ok(sc[0], d.get("english_headline", "")):
            return sc
        best = best or sc
        user += ("\n\nYOUR SCENE WAS TOO GENERIC OR TOO SHORT. Start with the main event of THIS headline, name its place type, people, "
                 "vehicles or objects, and write 100-150 words.")
    return best


def bridge(action, **kw):
    """30 Oct: the Apps Script sometimes does not answer within 120 s (the writer crashed once on 'recent'): tried 3 times"""
    last = None
    for i in range(3):
        try:
            r = requests.get(BRIDGE_URL, params={"action": action, "key": BRIDGE_KEY, **kw}, timeout=120)
            r.raise_for_status()
            return r.json()
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            last = e
            print(f"bridge '{action}' did not answer (try {i + 1} of 3): {str(e)[:120]}", flush=True)
            time.sleep(10 * (i + 1))
    raise last


# what Coimbatore readers care about most (higher = picked first, so it is never missed).
# owner 29 Oct (Coimbatore): power cut (TNEB) > crime > accident > civic (roads, water, garbage, corporation) > the rest
INTEREST = [
    (10, ("மின்தடை", "மின் தடை", "மின்நிறுத்த", "மின் நிறுத்த", "மின் வெட்டு", "மின்வெட்டு", "மின் விநியோகம் நிறுத்தம்")),
    (9, ("கொலை", "கைது", "திருட்டு", "கொள்ளை", "மோசடி", "தற்கொலை", "வழிப்பறி", "நகை பறிப்பு", "பறிமுதல்", "போலீஸ்", "போலீசார்")),
    (8, ("விபத்து", "மோதி", "தீ விபத்து", "பலி", "உயிரிழ", "மீட்பு", "கவிழ்ந்")),
    (7, ("குடிநீர்", "குப்பை", "சாக்கடை", "பாதாளச் சாக்கடை", "கொசு", "தெருவிளக்கு", "சாலை பள்ளம்", "சாலை மறியல்", "மாநகராட்சி",
         "போக்குவரத்து நெரிசல்", "போக்குவரத்து மாற்றம்", "தண்ணீர்", "கழிவுநீர்", "சாலை சீரமைப்பு")),
    (6, ("வேலைவாய்ப்பு", "வேலை வாய்ப்பு", "ஆட்சேர்ப்பு", "பணியிடம்", "பணியிடங்கள்", "காலிப்பணி")),
    (9, ("மழை", "வானிலை", "புயல்", "வெள்ளம்", "வெப்பம்", "பள்ளி விடுமுறை", "விடுமுறை")),      # owner 31 Oct: rain = crime (Namakkal insights: weather 1,804 median views)
    (5, ("விலை", "காய்கறி", "தக்காளி", "தேங்காய்", "உழவர் சந்தை", "சந்தை")),
    (5, ("பள்ளி", "கல்லூரி", "மாணவ", "தேர்வு", "தேர்வு முடிவு", "உதவித்தொகை", "சேர்க்கை")),
    (5, ("ரேஷன்", "மகளிர் உரிமை", "ஓய்வூதியம்", "திட்டம்", "மானியம்", "ஆட்சியர்", "அறிவிப்பு", "முகாம்", "சிறப்பு முகாம்")),
    (4, ("பேருந்து", "சாலை", "போக்குவரத்து", "ரயில்", "பாலம்", "மேம்பாலம்", "விமான நிலையம்")),
    (8, ("காட்டு யானை", "யானை", "சிறுத்தை", "கரடி")),      # owner 31 Oct: wildlife is the most shared Coimbatore-only news (was 4)
    (7, ("அணை நீர்மட்டம்", "சிறுவாணி", "பில்லூர்", "ஆழியாறு", "குடிநீர் நிறுத்த")),      # dams / water supply of the city
    (9, ("ஆன்லைன் மோசடி", "சைபர் கிரைம்", "சைபர் க்ரைம்")),      # fraud warnings are forwarded to family
    (9, ("கனமழை", "மழை எச்சரிக்கை", "ஆரஞ்சு அலர்ட்", "ரெட் அலர்ட்", "வெள்ளப்பெருக்கு", "பனிமூட்டம்")),      # owner 31 Oct: rain warnings 2nd only to power cuts
    (3, ("திருவிழா", "கோவில்", "கோயில்", "தேரோட்ட", "மருதமலை", "சுற்றுலா")),
]


# owner 31 Oct (17:07): each Coimbatore round posts its top 3 ONLY from these four kinds - power cut, rain, crime, accident (Namakkal insights,
# 193 reels, median views: power cut 23,720 > weather 1,804 > crime 882 > accident 792; temple / civic / education / politics 280-512).
# Judged on the HEADLINE. Env TOP_KINDS_ONLY=0 turns it off. Links given by hand are never filtered.
TOP_KINDS = [
    ("power_cut", re.compile(r"power (cut|shutdown|outage)|no power supply", re.I)),
    ("rain", re.compile(r"மழை|வெள்ளம்|வெள்ளப்|வெள்ளத்|புயல்|அலர்ட்|நிலச்சரிவு|மண் சரிவு|பனிமூட்ட|சூறைக்காற்று|மின்னல்|\brain|flood|landslide|\bfog\b|\balert\b|நீர்வரத்து|அணை.{0,12}(திறப்பு|நிரம்)", re.I)),
    ("crime", re.compile(r"கொலை|கைது|திருட|கொள்ளை|மோசடி|வழிப்பறி|நகை பறிப்பு|பறிமுதல்|தற்கொலை|தப்பி|கடத்த|போக்சோ|பாலியல்|"
                         r"தாக்குதல்|தாக்கிய|அடிதடி|கஞ்சா|சிறை|தண்டனை|லஞ்ச|சைபர்|குண்டர்|வெட்டிக்|ரவுடி|வழக்குப்பதிவு|வழக்குப் பதிவு|"
                         r"arrest|murder|theft|thie[fv]|robber|fraud|scam|escape|ganja|drugs?\b|sentenced|jail|prison|pocso|cyber|bribe|assault|attack", re.I)),
    ("accident", re.compile(r"விபத்து|மோதி|மோதல்|பலி|உயிரிழ|சடலம|தீப்பிடி|தீப்பற்|கவிழ்ந்|மூழ்கி|மின்சாரம் தாக்கி|மின் தாக்கி|தவறி விழு|இடிந்து|"
                            r"accident|collision|crash|killed|\bdies\b|\bdied\b|dead\b|death|fire\b|blaze|drown|electrocut|overturn|collapse", re.I)),
]
TOP_KINDS_ONLY = os.environ.get("TOP_KINDS_ONLY", "1") == "1"


def top_kind(title):
    """'power_cut' / 'rain' / 'crime' / 'accident' when the headline is one of the four kinds a round posts, else ''"""
    t = title or ""
    for k, p in TOP_KINDS:
        if p.search(t) or (k == "power_cut" and _fr().is_power_cut(t)):
            return k
    return ""


# owner 31 Oct: only news Instagram users watch is written. 30-31 Oct posts showed what they do not: recipes, health / building tips and
# an editorial (RN-75, 77, 84, 86-91), awareness days, awards, trophies, a tender, a walkout, a tribute (RN-10, 18, 31, 34, 42, 68, 70, 74, 78);
# Namakkal + Coimbatore insights agree (ceremonies / education events / politics lowest). Never for a power cut or urgent news.
LOW_EDITORIAL_URL = re.compile(r"thalayangam|editorial|/opinion|/columns?/|/others/", re.I)
LOW_FEATURE = re.compile(r"எப்படி|காரணங்கள்|அறிகுறி|கவனிக்க வேண்டிய|டிப்ஸ்|ரெசிபி|செய்முறை|நன்மைகள்|தெரியுமா|ஆபத்து யாருக்கு|"
                         r"தாக்கும்\s+\S+\s+நோய்|ஸ்டைல்|கொத்சு|ரப்டி|சுவையான|காரசாரமான|தீர்வு|என்ன செய்வது|எதைக் குறிக்கின்றன")
LOW_FEATURE_URL = re.compile(r"how-to|how-does|causes-of|recipe|-curry|who-is-most-at-risk|benefits-of|tips-for|symptoms|-in-children|"
                             r"with-all-the-flavours", re.I)
LOW_CEREMONY = re.compile(r"விழிப்புணர்வு\s*(பேரணி|நிகழ்ச்சி|ஊர்வலம்)|கருத்தரங்கு|பட்டமளிப்பு|விருது|கௌரவ|சிலைக்கு.{0,20}மரியாதை|மாலை அணிவித்|"
                          r"ஒளிர்ந்த|உலக\s+\S+\s+தின|ஆண்டு விழா|ஆலோசனைக் கூட்டம்|ஆய்வுக் கூட்டம்|டெண்டர்|வெளிநடப்பு|சாம்பியன்|பதக்க|"
                          r"போட்டியில்.{0,25}(முதலிடம்|வெற்றி)|தலைவராக.{0,30}தேர்வு|பதவி உயர்வு")
NEVER_LOW = re.compile(r"மின்\s*தடை|மின்தடை|மின்\s*நிறுத்த|மின்\s*வெட்டு|பலி|உயிரிழ|விபத்து|கைது|தீ\s*விபத்து|தீப்பொறி|தீப்பிடி|மோசடி|பறிமுதல்|கொலை|"
                       r"திருட|காணவில்லை|யானை|சிறுத்தை|வெள்ள|கனமழை|எச்சரிக்கை|குடிநீர்|வேலைவாய்ப்பு|ஆட்சேர்ப்பு")


def low_interest(title, url=""):
    """'' = worth writing; else why Coimbatore viewers would not watch it (config "selection": {"skip_low_interest": false} = off)"""
    t, u = title or "", url or ""
    if not _selection().get("skip_low_interest", True) or NEVER_LOW.search(t) or _fr().is_power_cut(t):
        return ""
    if LOW_EDITORIAL_URL.search(u):
        return "editorial / opinion, not news"
    if (LOW_FEATURE.search(t) or LOW_FEATURE_URL.search(u)) and not allnews.has_place(t):
        return "feature / tips / recipe, not a Coimbatore event"
    if LOW_CEREMONY.search(t):
        return "ceremony / award / awareness event (low views)"
    return ""


def _selection():
    try:
        return json.loads((HERE.parent / "poster" / "config.json").read_text(encoding="utf-8")).get("selection") or {}
    except Exception:
        return {}


def interest(art):
    t = art.get("title", "") + " " + art.get("text", "")[:600]
    head = art.get("title", "")
    best = 2
    for score, keys in INTEREST:
        for k in keys:
            if k in head:
                best = max(best, score + 1)
            elif k in t:
                best = max(best, score)
    return best


def _start_at():
    """the moment automatic collecting was last started (research_free/START_AT, UTC). News published before it is never collected."""
    try:
        return datetime.datetime.fromisoformat((HERE / "START_AT").read_text().strip().replace("Z", "+00:00"))
    except Exception:
        return None


def fresh(published):
    try:
        t = datetime.datetime.fromisoformat(published)
        d = t.astimezone(IST).date()
    except Exception:
        return True
    st = _start_at()
    if st is not None and t.tzinfo is not None and t < st:
        return False      # published before the automation was started: already covered by the posted/e-mailed news
    # owner 29 Oct (Coimbatore): news published TODAY - plus anything published in the last FRESH_HOURS, so a story published at 11:30 pm
    # is still taken by the 1 am round ("do not miss any news")
    if t.tzinfo is not None and datetime.datetime.now(IST) - t <= datetime.timedelta(hours=FRESH_HOURS):
        return True
    return (datetime.datetime.now(IST).date() - d).days < FRESH_DAYS


FRESH_HOURS = float(os.environ.get("FRESH_HOURS", "0") or 0)      # owner 29 Oct 18:29 (Coimbatore): TODAY's news only, no late-night carry-over


def published_today(published):
    """owner 29 Oct 18:29 (Coimbatore): the article itself must show a publish date, and that date must be today (IST)"""
    try:
        t = datetime.datetime.fromisoformat(str(published))
    except Exception:
        return False
    d = t.astimezone(IST).date() if t.tzinfo is not None else t.date()
    return d == datetime.datetime.now(IST).date()      # late-night news crosses midnight: still fresh for 3 h
FRESH_DAYS = int(os.environ.get("FRESH_DAYS", "1") or 1)      # owner 29 Oct (Coimbatore): 1 = news published TODAY only; 2 = today + yesterday


def _fr():
    sys.path.insert(0, str(HERE.parent / "poster"))
    import freshness
    return freshness


def is_dup(art, d, recent):
    for r in recent:
        if r.get("source") and r["source"] == art["url"]:
            return True
        if _fr().similar(r.get("headline_ta", ""), (d or {}).get("tamil_headline", art["title"]), 0.72, r.get("researched")):
            return True
        if _fr().same_power_cut(r.get("headline_ta"), r.get("researched"), (d or {}).get("tamil_headline", art["title"]), art.get("published")):
            return True      # owner 30 Oct: the same power cut (same day, same place) already filed
    # 31 Oct (Coimbatore RN-96 = RN-95: one escape, two outlets, written in the same round; RN-39 = RN-76): the new SCRIPT against every story
    # filed in the last 2 days (owner 31 Oct: Namakkal RN-115 repeated RN-86 24 h 8 min later) - this round's included - so the same event
    # in other words is never filed twice
    s = (d or {}).get("reel_script") or ""
    if s:
        today = datetime.datetime.now(_fr().IST).date()
        olds = [o for o in (_filed_script(r) for r in recent
                            if (lambda od: od is None or abs((today - od).days) <= 2)(_fr().pub_date(r.get("researched")))) if o]
        if olds:
            df = _fr().event_df(olds + [s])
            if any(_fr().same_event(o, s, df) for o in olds):
                return True
    return False


def score(n):
    """how likely readers are to open / share it: topic interest + how many outlets carry it + how fresh it is"""
    s = interest({"title": n.get("title", ""), "text": n.get("snippet", "")})
    m = n.get("mentions", 1)
    s += 2 if m >= 3 else (1 if m == 2 else 0)
    try:
        import learned
        s += learned.boost(n.get("title", ""))        # topics our own Instagram insights show people watch / save / share
    except Exception:
        pass
    try:
        age_h = (datetime.datetime.now(IST) - datetime.datetime.fromisoformat(n["published"])).total_seconds() / 3600
        s += 1 if age_h < 6 else 0
    except Exception:
        pass
    if any(w in n.get("title", "") for w in allnews.CITY_AREAS):
        s += 1      # owner 31 Oct: whole district, but most followers live in the city - a city story wins a tie
    return s


# collect / write split (owner 26 Oct): the 4-hourly round only COLLECTS and queues every eligible news by priority;
# the writer round (every 20 min) takes the queue in priority order, writes the story, and the posting job posts it at once.
MODE = os.environ.get("COLLECT_MODE", "both")      # collect | write | both
# owner 4 Nov: a final "no" from the writer (a link that could not be opened is NOT here - it is tried again)
REFUSED = ("not filed", "not written", "not Coimbatore", "already filed", "old", "article has no text", "not a Tamil", "duplicate",
           "checked earlier")
PICK_ONLY = os.environ.get("PICK_ONLY", "") == "1"      # owner 1 Nov: write only MANUAL_URL links (the owner's / automatic pick)
QUEUE = ARCHIVE / "queue.json"
QFIELDS = ("key", "url", "title", "source", "published", "via", "query", "snippet", "outlets", "alts", "mentions", "area", "score", "queued_at", "verified")


def load_queue():
    """news collected earlier and not written yet (kept 2 days; the freshness check still applies when it is written)"""
    try:
        q = json.loads(QUEUE.read_text(encoding="utf-8"))
    except Exception:
        return []
    # owner 31 Oct: each day starts fresh - only news queued TODAY (IST) is compared again in the next round (a power cut for today
    # published last evening is found again by the collection and kept by its cut day)
    cut = datetime.datetime.now(IST).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    return [dict(x, outlets=list(x.get("outlets") or []), alts=list(x.get("alts") or [x["url"]])) for x in q if x.get("queued_at", "") >= cut]


def save_queue(items):
    now = datetime.datetime.now(IST).isoformat()
    out, seen = [], set()
    for n in sorted(items, key=lambda x: (not x.get("verified"), -x.get("score", 0))):
        if n["key"] in seen or n.get("manual"):
            continue
        seen.add(n["key"])
        out.append({k: (n.get(k) if k != "queued_at" else n.get("queued_at") or now) for k in QFIELDS})
    ARCHIVE.mkdir(exist_ok=True)
    QUEUE.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    return len(out)


SAME_WORDS = {"கலெக்டர்": "ஆட்சியர்", "பங்களா": "குடியிருப்பு", "போலீசார்": "காவல்துறை", "போலீஸ்": "காவல்துறை", "உயிரிழப்பு": "பலி",
              "உயிரிழந்தார்": "பலி", "இறந்தார்": "பலி", "ஊர்வலம்": "பேரணி", "மருத்துவமனை": "ஆஸ்பத்திரி"}


def _stems(t):
    t = (t or "").replace("\u0bbe\u0bcd", "ர்")      # old print form: ஆட்சியா் = ஆட்சியர், சுவா் = சுவர்
    for a, b in SAME_WORDS.items():
        t = t.replace(a, b)
    return {w[:4] for w in re.findall(r"[\u0B80-\u0BFF]{4,}", t)}


def same_news(a, b, filed=None, days=3):
    """the same event in different words (ஆட்சியா் பங்களா சுவா் இடிந்து ~ கலெக்டர் குடியிருப்பின் சுற்றுச்சுவர் இடிந்தது): shared word stems.
    28 Oct: two shared words in short headlines matched old, other news ('140 மி.மீ. மழை' ~ RN-58, 'சர்வீஸ் சாலை குப்பை' ~ RN-69,
    '30ல் விவசாயிகள் குறைதீர் கூட்டம்' ~ RN-140): at least 3 shared stems, and only against stories filed in the last `days` days"""
    x, y = _stems(a), _stems(b)
    if len(x) < 3 or len(y) < 3 or _fr().different_numbers(a, b) or _fr().different_power_cut(a, b) or allnews.different_places(a, b):
        return False
    f = _fr().pub_date(filed) if filed else None
    if f and (datetime.datetime.now(_fr().IST).date() - f).days > days:
        return False
    shared = len(x & y)
    return shared >= 3 and shared / min(len(x), len(y)) >= 0.5


_EVENT_DF = {}


def _filed_script(r):
    """the reel script of a filed story. 30 Oct: the Sheet's 'recent' rows carry no script, so this check never ran - the script is
    read from the saved prebuilt file, as post.py does"""
    if r.get("reel_script"):
        return r["reel_script"]
    try:
        sys.path.insert(0, str(HERE.parent / "poster"))
        import post
        return post.script_of(r)
    except Exception:
        return ""


def same_event_filed(art, recent, days=1):
    """story id of a story filed in the last `days` day(s) that reports the same event as this article (shared rare word stems of
    the article text and that story's reel script), else ''. 29 Oct: Namakkal RN-193 was written again after RN-168
    (posted 28 Oct) because the headlines differ by one number."""
    fr = _fr()
    scripts = [s for s in (_filed_script(r) for r in recent) if s]
    if not scripts:
        return ""
    key = len(scripts)
    df = _EVENT_DF.get(key)
    if df is None:      # owner 2 Nov (review): 3 writer threads share this cache - never clear-then-read (KeyError)
        df = fr.event_df(scripts)
        _EVENT_DF.clear()
        _EVENT_DF[key] = df
    mine = fr.pub_date(art.get("published")) or datetime.datetime.now(fr.IST).date()
    text = (art.get("title") or "") + " " + (art.get("text") or "")[:2500]
    for r in recent:
        s = _filed_script(r)
        if not s:
            continue
        od = fr.pub_date(r.get("researched")) or fr.pub_date(r.get("published"))
        if od and abs((mine - od).days) > days:
            continue
        if fr.same_event(s, text, df):
            return r.get("story_id") or "a filed story"
    return ""


def open_article(n):
    """resolved link + article (title, date, text) of a news item; raises when it cannot be opened"""
    links = [u for u in [n["url"]] + n.get("alts", []) if u]
    links = list(dict.fromkeys([u for u in links if "news.google.com" not in u] + links))      # a direct publisher link first
    url, last = None, None
    for u in links[:4]:
        try:
            url = allnews.resolve(u)
            break
        except Exception as e:
            last = e
    if url is None:
        raise last or RuntimeError("no link")
    art = allnews.article_any(url)
    art["url"] = url
    for k in ("text", "title"):      # some outlets type ூ as ு+ா (ப.வேலுார்)
        if art.get(k):
            art[k] = art[k].replace("\u0bc1\u0bbe", "\u0bc2")
    art["title"] = art.get("title") or n["title"]
    art["published"] = art.get("published") or n["published"]
    return art


def local_score(n, text=""):
    """priority: real local news first (a district place in the headline), then topic interest, outlets and freshness"""
    s = score(n)
    if allnews.has_place(n.get("title", "")):
        s += 3
    elif allnews.has_place(text[:600]):
        s += 1
    return round(s, 2)


def recheck_once(st, url):
    """27 Oct: stories on a paper's own Coimbatore page, and 'duplicates' found by the old letter-only match, are checked once more.
    The old verdict is removed, so the writer (a separate run) does not skip the item as 'checked earlier'; a new check sets a new one.
    True when this item gets its second check now (st is changed in place)."""
    if st.get("r27b") or not ((st.get("s") == "notdistrict" and allnews.url_district(url) in allnews.DISTRICT_SLUGS) or st.get("s") == "dup"):
        return False
    st["r27b"] = 1
    st.pop("s", None)
    return True


def verify_candidates(items, state, log):
    """collect round: open every candidate now, keep only real Coimbatore-district news of today / yesterday, merge the same event
    reported by several outlets. The queue then holds only news that will really be written (no time lost on other districts)."""
    from concurrent.futures import ThreadPoolExecutor
    todo = [n for n in items if not n.get("verified")]

    def check(n):
        try:
            return n, open_article(n), None
        except Exception as e:
            return n, None, e
    kept = {"ok": 0, "old": 0, "notdistrict": 0, "notext": 0, "open": 0}
    results = []
    with ThreadPoolExecutor(max_workers=int(os.environ.get("VERIFY_WORKERS", "4"))) as ex:
        results = list(ex.map(check, todo))
    again = [n for n, art, err in results if err is not None]
    if again:      # second try, two at a time, after a pause (Google's link decoder limits bursts)
        time.sleep(20)
        with ThreadPoolExecutor(max_workers=2) as ex:
            second = {id(n): (n, a, e) for n, a, e in ex.map(check, again)}
        results = [second.get(id(n), (n, a, e)) if e is not None else (n, a, e) for n, a, e in results]
    if True:
        for n, art, err in results:
            stt = state.setdefault(n["key"], {"n": 0})
            stt["t"] = datetime.datetime.now(IST).isoformat()
            if err is not None:
                n["status"] = f"could not open the article: {str(err)[:60]}"      # stays in the queue, tried again later
                stt["n"] = stt.get("n", 0) + 1
                kept["open"] += 1
                continue
            if len(art["text"]) < 20 or len(body_words(art)) < HEADLINE_ONLY_MIN:      # empty page, or only the headline (RN-12)
                n["status"], stt["s"] = "article has no text beyond its headline", "notext"; kept["notext"] += 1
                continue
            if not tamil_source(art) and not n.get("manual"):      # owner 29 Oct: Tamil sources only
                n["status"], stt["s"] = "not a Tamil-language article", "notext"; kept["notext"] += 1
                continue
            if not published_today(art["published"]) and not n.get("manual") and not _fr().power_cut_ahead(art["title"], art["published"]):      # owner 29 Oct: published TODAY only (30 Oct: a power cut by its CUT day)
                n["status"], stt["s"] = "old", "old"; kept["old"] += 1
                continue
            # owner 26 Oct: ONLY Coimbatore-district news - a district place in the headline or in the opening lines (not just a sidebar or a
            # long list of districts), and a headline that names no other district / town and is not state-wide
            if (not allnews.local_ok(art["url"], art["title"]) or not allnews.local_ok(art["url"], n.get("title", "") or art["title"])
                    or not (allnews.has_place(art["title"]) or allnews.has_place(art["text"][:300]) or allnews.url_district(art["url"]) in allnews.DISTRICT_SLUGS)
                    or allnews.outside_district(art["title"])):      # 27 Oct: a story on the paper's own Coimbatore page is Coimbatore news even when it names no town
                n["status"], stt["s"] = "not Coimbatore district news (article names no Coimbatore place)", "notdistrict"; kept["notdistrict"] += 1
                continue
            town = allnews.outside_city(art["title"], art["text"][:300])
            if town and not n.get("manual"):      # owner 29 Oct: Coimbatore city only for now
                n["status"], stt["s"] = f"not Coimbatore city news ({town})", "notcity"; kept["notdistrict"] += 1
                continue
            n.update(url=art["url"], title=art["title"], published=art["published"], verified=True)
            n["area"] = allnews.area_of_story(art["title"], art["text"])
            n["score"] = local_score(n, art["text"])
            kept["ok"] += 1
    # the same event from several outlets = one item (the highest priority one; the outlets add to its priority)
    good = sorted([n for n in items if n.get("verified") and str(n["status"]).startswith("collected")], key=lambda x: -x["score"])
    merged = []
    for n in good:
        twin = next((m for m in merged if difflib.SequenceMatcher(None, m["title"], n["title"]).ratio() > 0.6), None)
        if twin:
            n["status"] = "duplicate of a queued news"
            twin["alts"] = list(dict.fromkeys(twin.get("alts", []) + [n["url"]] + n.get("alts", [])))
            twin["mentions"] = twin.get("mentions", 1) + 1
        else:
            merged.append(n)
    log.append(f"checked at collection: {kept['ok']} real local news, {len(good) - len(merged)} duplicates merged, {kept['old']} old, "
               f"{kept['notdistrict']} other district / state-wide, {kept['notext']} empty, {kept['open']} could not be opened (tried again later)")


def mark_run(kind):
    """research_free/archive/last_run.json: when the last collect / write round ran (the posting check restarts an overdue one)"""
    if DRY:
        return
    f = ARCHIVE / "last_run.json"
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        d = {}
    d[kind] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    ARCHIVE.mkdir(exist_ok=True)
    f.write_text(json.dumps(d), encoding="utf-8")


def load_state():
    try:
        st = json.loads((ARCHIVE / "state.json").read_text(encoding="utf-8"))
    except Exception:
        st = {}
    cut = (datetime.datetime.now(IST) - datetime.timedelta(days=5)).isoformat()
    return {k: v for k, v in st.items() if v.get("t", "") >= cut}


def save_state(st):
    ARCHIVE.mkdir(exist_ok=True)
    (ARCHIVE / "state.json").write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")


PRIORITY_ONLY = [False]


def assign_carousel(group):
    """Coimbatore 360 posts reels only: no carousel for any story (kept as a function so the posting code stays like the Namakkal copy)"""
    for x in group:
        if isinstance(x.get("slides_spec"), dict):
            x["slides_spec"]["carousel"] = False


STYLE = ""      # the full photo style is in IMG_TEMPLATE (the old square / "dramatic golden hour" prefix fought the 9:16 news-photo template)


def _upload_image(data):
    cloud, preset = os.environ.get("CLOUDINARY_CLOUD"), os.environ.get("CLOUDINARY_PRESET")
    if not cloud or not preset:
        raise RuntimeError("Cloudinary secrets missing")
    r = requests.post(f"https://api.cloudinary.com/v1_1/{cloud}/image/upload", data={"upload_preset": preset, "folder": "coimbatore360"},
                      files={"file": ("img.jpg", data)}, timeout=300)
    r.raise_for_status()
    return r.json()["secure_url"]


_RECENT_IMG = []
IMG_DOWN = [False]
IMG_SPENT = [0.0]      # seconds spent on images in this run (stories are now sent one by one)


def reuse_images(st, need):
    """earlier posted stories' pictures that fit this news: same category and place first, then same category (partial match).
    Returns `need` picture URLs, or [] when nothing suitable exists."""
    if os.environ.get("REUSE_IMAGES", "0") != "1":      # owner 25 Oct: never reuse earlier pictures, always make fresh ones
        return []
    if not _RECENT_IMG:
        try:
            _RECENT_IMG.extend(bridge("recent").get("rows", []))
        except Exception as e:
            print("recent pictures not available:", str(e)[:120]); _RECENT_IMG.append({})
    cat, loc = (st.get("category") or "").strip(), (st.get("location") or "").strip()
    best, best_score = None, 0
    for r in _RECENT_IMG:
        if not r.get("story_id") or not str(r.get("post_status", "")).lower().startswith(("posted", "partly")):
            continue
        try:
            imgs = json.loads(r.get("images") or "[]")
        except Exception:
            continue
        if len(imgs) < need or "NOIMAGE" in str(imgs):
            continue
        score = (2 if cat and r.get("category") == cat else 0) + (2 if loc and loc.split(",")[0].strip() and loc.split(",")[0].strip() in str(r.get("location", "")) else 0)
        if score >= 2 and score > best_score:
            best, best_score = imgs, score
    return list(best[:need]) if best else []


def make_images(group, log=None):
    """AUTO images: the story's ONE image prompt -> free image API first (Cloudflare, NVIDIA; FAL only when both fail) -> Cloudinary.
    A story gets story["images"] (one URL) when its picture was made; the bridge then queues it for posting at once. Any failure ->
    "Auto images": the posting job tries the image models again within minutes."""
    if os.environ.get("AUTO_IMAGES", "0") != "1" or not (os.environ.get("FAL_KEY") or os.environ.get("NVIDIA_API_KEY") or os.environ.get("CLOUDFLARE_API_TOKEN")) or DRY:
        return
    try:
        import imagegen
    except Exception as e:
        print("imagegen import failed:", e)
        return
    t0 = time.time()
    for st in group:
        if time.time() - t0 > IMG_BUDGET or IMG_SPENT[0] > IMG_BUDGET:
            st["auto_images"] = True
            msg = "image budget used up: the remaining stories get their images in the posting job"
            print(msg); log is not None and log.append(msg)
            break
        prompts = [p.strip() for p in str(st.get("prompts", "")).split("\n---\n") if p.strip()][:pictures_per_reel()]      # owner 30 Oct: 2 per reel
        if not prompts:
            continue
        if IMG_DOWN[0]:
            st["auto_images"] = True
            continue
        sid = st.get("english_headline", "")[:40]
        if IMG_MAX and sum(imagegen.USED.values()) + len(prompts) > IMG_MAX:
            st["auto_images"] = True
            msg = f"image cap {IMG_MAX} per run reached (credit guard): the remaining stories get their images in the posting job"
            print(msg); log is not None and log.append(msg)
            break
        # owner 31 Oct: the news's OWN photo from the source article first (only a photo that shows this news, enhanced to a presentable
        # picture when small); no relevant / presentable photo -> the AI pictures exactly as before
        try:
            import realphoto
            pub = None
            try:
                pub = datetime.datetime.fromisoformat(str(st.get("published", ""))).date()
            except Exception:
                pass
            notes = []
            pics, credit = realphoto.for_story(st.get("source", ""), st.get("english_headline", ""), n=len(prompts), published=pub,
                                               fetch=lambda u: allnews._get(u, timeout=40).text, log=notes.append)
            for m in notes:
                print(m, flush=True)
            if pics:
                st["images"] = [_upload_image(b) for b in pics]
                st["real_photo"] = credit
                print(f"real photos used for '{sid}' ({credit})")
                if log is not None:
                    log.append(f"real photo from the source ({credit}) for '{sid}'")
                continue
        except Exception as e:
            print(f"real photo step skipped for '{sid}': {str(e)[:120]}")
        reused = reuse_images(st, len(prompts))
        if reused:
            st["images"] = reused
            print(f"earlier pictures reused for '{sid}'")
            if log is not None:
                log.append(f"earlier picture reused for '{sid}' (matching news)")
            continue
        try:
            urls = []
            for n_, pr0 in enumerate(prompts):
                pr = (STYLE + pr0)[:1800]
                try:
                    data = imagegen.generate(pr, seed=random.randint(1, 10**6))      # free first (Cloudflare, Pollinations, NVIDIA); only then FAL
                except Exception as e:
                    if not urls:
                        raise      # no cover: the story is handled as before (posting job retries)
                    print(f"picture {n_ + 1} not made for '{sid}' (the reel uses the pictures made): {str(e)[:120]}")
                    break
                if not imagegen.matches(data, st.get("english_headline", "")):
                    try:      # a picture that does not show this news is made once more (free sources only), then the better one is used
                        again = imagegen.generate(pr, seed=random.randint(1, 10**6), free_only=True)
                        data = again if imagegen.matches(again, st.get("english_headline", "")) else data
                    except Exception as e:
                        print(f"second try not made for '{sid}' (the first one is used): {str(e)[:120]}")
                urls.append(_upload_image(data))
            st["images"] = urls
            print(f"images made: {len(urls)} for '{sid}'")
        except Exception as e:
            print(f"image NOT made for '{sid}': {str(e)[:200]}")
            st["auto_images"] = True      # the bridge queues it as "Auto images": the posting job tries the image models again within minutes
            if log is not None:
                log.append(f"auto image failed for '{sid}': {str(e)[:120]} -> posting job retries")
            again = reuse_images(st, len(prompts))
            if again:
                st["images"] = again
                if log is not None:
                    log.append(f"earlier picture reused (second check) for '{sid}'")
                continue
            if "all image models failed" in str(e):
                IMG_DOWN[0] = True      # no image model works right now (credits/limit): the next stories go straight to the posting job's retry
                break
    IMG_SPENT[0] += time.time() - t0
    if log is not None:
        log.append(f"auto images: {sum(1 for x in group if x.get('images'))} of {len(group)} stories ({imagegen.USED})")


def pending_ids(max_hours=2):
    """stories of earlier rounds still waiting for the owner's images (not older than a day): they are listed again in this round's e-mail"""
    if not BRIDGE_URL or DRY:
        return []
    try:
        rows = bridge("recent").get("rows", [])
    except Exception as e:
        print("pending list not available:", e)
        return []
    out, now = [], datetime.datetime.now(IST)
    TODAY[0] = 0
    mon = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
    for r in rows:
        m = re.search(r"(\d{1,2}) (\w{3}) (\d{4}), (\d{1,2}):(\d{2})", str(r.get("researched", "")))
        if not m or m.group(2).lower() not in mon:
            continue
        t = datetime.datetime(int(m.group(3)), mon.index(m.group(2).lower()) + 1, int(m.group(1)), int(m.group(4)), int(m.group(5)), tzinfo=IST)
        if t.date() == now.date() and not str(r.get("post_status", "")).lower().startswith("skipped"):
            TODAY[0] += 1          # stories written today (each one is one reel)
        if str(r.get("post_status", "")).strip() != "Awaiting images":
            continue
        if (now - t).total_seconds() <= max_hours * 3600:
            out.append(r["story_id"])
    return out


REOFFER = []
TODAY = [0]
DAILY_CAP = int(os.environ.get("DAILY_CAP", "1000"))      # owner: after 40 posts in a day only the main / important news is written and posted


def send_batch(group, log=None, images=True):
    """write these stories to the Sheet (stories without all images: "Auto images" = the posting job makes them, or the images-needed e-mail);
    returns True when the bridge accepted them. Retried, because a story that is not saved here is lost."""
    if not group or not BRIDGE_URL or DRY:
        return False
    assign_carousel(group)
    if images:
        make_images(group, log)           # AI image API; stories whose images could not all be made are marked auto_images
    if os.environ.get("AUTO_IMAGES", "0") == "1":
        for x in group:
            if not x.get("images"):
                x["auto_images"] = True
    clean = [{k: v for k, v in x.items() if not k.startswith("_")} for x in group]
    last = None
    for k in range(3):
        try:
            r = requests.post(BRIDGE_URL, params={"key": BRIDGE_KEY}, data=json.dumps({"action": "addStories", "stories": clean, "reoffer_ids": REOFFER}), timeout=180)
            print("bridge:", r.status_code, r.text[:300])
            r.raise_for_status()
            if not r.json().get("ok"):
                raise RuntimeError(r.text[:200])
            REOFFER[:] = []      # earlier stories still waiting for images are listed once per round, not with every story
            return True
        except Exception as e:
            last = e
            time.sleep(10 * (k + 1))
    try:
        raise last
    except Exception as e:
        print("bridge failed:", e)
        if log is not None:
            log.append(f"addStories failed: {e}")
        return False


_LAST_TRIGGER = [0.0]


def trigger_workflow(name, inputs=None, log=None):
    """start another workflow now (GitHub's own schedule is often late or skipped); never fails the run"""
    tok, repo = os.environ.get("GH_TOKEN"), os.environ.get("GH_REPO")
    if not tok or not repo or DRY:
        return False
    try:
        r = requests.post(f"https://api.github.com/repos/{repo}/actions/workflows/{name}/dispatches", timeout=30,
                          headers={"Authorization": "Bearer " + tok, "Accept": "application/vnd.github+json"},
                          json={"ref": "main", "inputs": inputs or {}})
        msg = f"{name} started" if r.status_code == 204 else f"{name} not started ({r.status_code} {r.text[:80]})"
    except Exception as e:
        msg = f"{name} not started ({str(e)[:80]})"
    print(msg, flush=True)
    if log is not None:
        log.append(msg)
    return msg.endswith("started")


def trigger_posting(log=None):
    """start the posting workflow now (a story with pictures was just saved) instead of waiting for its schedule; at most every 8 minutes.
    Never fails the run: without a token the normal schedule posts it."""
    tok, repo = os.environ.get("GH_TOKEN"), os.environ.get("GH_REPO")
    if not tok or not repo or DRY or time.time() - _LAST_TRIGGER[0] < 480:
        return
    try:
        r = requests.post(f"https://api.github.com/repos/{repo}/actions/workflows/post.yml/dispatches", timeout=30,
                          headers={"Authorization": "Bearer " + tok, "Accept": "application/vnd.github+json"},
                          json={"ref": "main", "inputs": {"dry_run": "false", "prebuild": "false"}})
        _LAST_TRIGGER[0] = time.time()
        msg = "posting job started at once" if r.status_code == 204 else f"posting job not started ({r.status_code}): the schedule posts it"
    except Exception as e:
        msg = f"posting job not started ({str(e)[:80]}): the schedule posts it"
    print(msg, flush=True)
    if log is not None:
        log.append(msg)


def body_words(art):
    """owner 29 Oct (RN-12 Coimbatore, K.N. Nehru raid): words of the article BEYOND its headline. A page that is only a headline
    (breaking-news stub, video page) gives the writer nothing to report, so it invents details."""
    title = set(re.findall(r"\w+", (art.get("title") or "").lower()))
    return [w for w in re.findall(r"\w+", (art.get("text") or "").lower()) if w not in title and len(w) > 1]


def tamil_source(art):
    """owner 29 Oct: news is taken ONLY from Tamil-language articles. English pages (New Indian Express, DT Next, Times of India ...)
    gave the worst reels: the writer's translation was garbled and the facts could not be checked against the article."""
    t = (art.get("text") or "") + " " + (art.get("title") or "")
    ta = len(re.findall(r"[\u0B80-\u0BFF]", t))
    en = len(re.findall(r"[A-Za-z]", t))
    return ta >= max(40, en)          # mostly Tamil letters


# owner 30 Oct: a story refused for a reason in the ARTICLE is not written again and again - 'not Coimbatore city news' drafts
# (Thondamuthur, Periyanaickenpalayam) were written and refused 4-5 times on 30 Oct (a free-model call each time, until the 10-try
# limit). Final at once: a stale date, an old event, a duplicate cannot change. One more try: the place / 'not news' verdicts depend on
# the model's wording. A real model failure ('all free models failed: ...', 'bad draft') is always tried again.
REFUSED_FINAL = (("stale:", "old"), ("old event", "old"), ("duplicate", "dup"))
REFUSED_ONCE_MORE = (("all free models failed: not Coimbatore city news", "notcity"), ("not news:", "notext"))


def refusal_verdict(why, st):
    """the state verdict that stops another write of a refused story ('' = it may be written again); st counts the refusals"""
    w = str(why or "")
    for k, v in REFUSED_FINAL:
        if w.startswith(k):
            return v
    for k, v in REFUSED_ONCE_MORE:
        if w.startswith(k):
            st["refused"] = st.get("refused", 0) + 1
            return v if st["refused"] >= 2 else ""
    return ""


HEADLINE_ONLY_MIN = 12     # fewer new words than this after the headline = nothing to report (a 2-line police brief has ~20)



def district_town(art):
    """the first town / village of the district named in the article (title first, then text), or ''"""
    body = (art.get("title") or "") + "\n" + (art.get("text") or "")[:3000]
    found = allnews.places_in(body)
    if not found:
        return ""
    return min(found, key=lambda w: (body.find(w) if w in body else 10 ** 6, -len(w)))

def file_story(art, res, errors_log, recent, scenes=None):
    """quality gate for one written story; returns the story dict, or (None, reason)"""
    if isinstance(res, Exception):
        return None, f"all free models failed: {str(res)[:80]}"
    try:
        d, model, errors, att = res
        d["scenes"], d["tamil_headline"]
    except Exception as e:
        return None, f"bad draft: {e}"
    # owner 25 Oct: a draft is NOT rejected for length, word count or validator problems. It is rewritten by the models (free, then Claude),
    # and whatever is left goes out with the problems written in its verification note for the owner to see.
    # owner 29 Oct (RN-12): a draft whose words mostly do NOT come from a Tamil article is made up -> never filed (fake news rule).
    # Only for Tamil articles: an English article has no Tamil words to compare with, so the check would always fail there.
    if not art.get("manual"):
        try:
            why = allnews.written_elsewhere(d.get("tamil_headline") or "", d.get("reel_script") or "")
        except Exception:
            why = ""
        if why:      # owner 2 Nov (review): the Namakkal RN-195 fix, now here too
            return None, why
    m_ = next((re.search(r"not grounded: only (\d+)%", e) for e in errors if "not grounded: only" in e), None)
    tamil_words = len(re.findall(r"[\u0B80-\u0BFF]{4,}", art.get("text") or ""))
    if m_ and int(m_.group(1)) < 50 and tamil_words >= 60:
        return None, f"not news: draft not grounded in the article (only {m_.group(1)}% of its words come from it) - likely made up"
    try:
        sys.path.insert(0, str(HERE.parent / "poster"))
        import freshness
        why = freshness.stale_reason(d.get("tamil_headline", ""), d.get("english_headline", ""), d.get("category", ""), art.get("published", ""))
        if why:
            return None, "stale: " + why
        spec_ = d.get("slides_spec") if isinstance(d.get("slides_spec"), dict) else {}
        why = freshness.no_news(" ".join([d.get("tamil_headline", ""), str(spec_.get("hl1", "")), str(spec_.get("hl2", ""))]),
                                d.get("reel_script", ""), d.get("instagram_caption", "") or d.get("caption", ""))
        if why:      # owner 29 Oct (RN-189): a draft that only says "the article has no details" is not news
            return None, why
        why = freshness.old_event(d.get("tamil_headline", "") + " " + d.get("reel_script", ""))
        if why:      # owner 29 Oct (Coimbatore RN-29): an old event re-told in a new article
            return None, why
        for k_ in ("reel_script", "caption"):      # a real story keeps its facts; only the "not in the article" sentences go (RN-112)
            if d.get(k_):
                d[k_] = freshness.strip_no_news(d[k_])
        for sl_ in (d.get("slides_spec") or {}).get("slides") or [] if isinstance(d.get("slides_spec"), dict) else []:      # 31 Oct: cards too
            kept_ = [ln_ for ln_ in sl_.get("lines") or [] if not freshness._meta(re.sub(r"<[^>]+>", "", str(ln_)))]
            sl_["lines"] = kept_ or sl_.get("lines")
        import verify as verify_
        for k_ in ("tamil_headline", "reel_script", "caption", "location", "slides_spec"):      # other-script letters -> Tamil (29 Oct)
            if d.get(k_):
                d[k_] = verify_.clean_obj(d[k_])
    except ImportError:
        pass
    if is_dup(art, d, recent):
        return None, "duplicate after write"
    if isinstance(d.get("slides_spec"), dict):
        d["slides_spec"]["v"] = 3          # the poster only reads format v3; a model writing v4 made RN-48 unpostable
    if not scenes:
        try:
            scenes = image_scenes(art, d)
        except Exception as e:
            print("image brief failed, using the writer's image prompt:", str(e)[:120], flush=True)
    if not scenes:
        scenes = [s for s in (d["scenes"] if isinstance(d["scenes"], list) else [d["scenes"]]) if isinstance(s, str) and s.strip()]
        scenes = scenes or [f"The main scene of this news: {d.get('english_headline', '')}, {d.get('location', '')}."]
    prompts = "\n---\n".join(IMG_TEMPLATE.format(scene=x.strip()) for x in scenes[:pictures_per_reel()])      # owner 30 Oct: 2 pictures per reel
    # owner 3 Nov: the writer still gives "<district> district" alone sometimes (RN-160 / RN-163 held). The town comes from the
    # article itself: the first town / village of the district the article names is put in front. No town in the article -> left as it is.
    if re.fullmatch(r"[^,]*\b(district|மாவட்டம்)\.?", str(d.get("location") or "").strip(), re.I):
        town_ = district_town(art)
        if town_:
            d["location"] = f"{town_}, {str(d['location']).strip()}"
    ver = f"DRAFT ({model}) - fact-check: no problems found" if not errors else f"DRAFT ({model}) - NOT CLEAN, held from posting - problems: {'; '.join(errors)}"
    return {"tamil_headline": d["tamil_headline"], "english_headline": d["english_headline"], "category": d["category"], "location": d["location"],
            "importance": d["importance"], "scope": d.get("scope", ""), "post_to": PAGE_NAME, "slides_spec": d["slides_spec"], "reel_script": d["reel_script"],
            "caption": d["caption"], "prompts": prompts, "source": art["url"], "published": art["published"], "verification": ver,
            "note": f"free-model draft {model}, {att} attempt(s), {len(errors)} validator problem(s)",
            "post_time": "right after your reply, same day"}, ""


def instagram_recent(log=None):
    """headlines of what the Instagram page ALREADY shows (last 50 posts), as sheet-like rows, so nothing already posted is written or posted again"""
    rows = []
    try:
        sys.path.insert(0, str(HERE.parent / "poster"))
        import post
        for page in ("coimbatore",):      # page key of Coimbatore 360 (the only page)
            try:
                tok = post.bridge_get("token", page=page)["token"]
                uid, _ = post.ig_account(tok)
                for m in post.ig("GET", f"{uid}/media", tok, fields="caption,timestamp", limit=50).get("data", []):
                    head = re.sub(r"^[^\w]+", "", (m.get("caption") or "").strip().split("\n")[0]).strip()
                    if head:
                        rows.append({"story_id": "IG-" + page, "headline_ta": head, "headline_en": "", "researched": m.get("timestamp"), "source": "", "post_status": "posted"})
            except Exception as e:
                if log is not None:
                    log.append(f"instagram check {page} failed: {str(e)[:120]}")
    except Exception as e:
        if log is not None:
            log.append(f"instagram check unavailable: {str(e)[:120]}")
    if log is not None:
        log.append(f"instagram check: {len(rows)} recent posts read from the page")
    return rows


def main():
    if MODE == "write" and not load_queue() and not os.environ.get("MANUAL_URL", "").strip():
        print("write round: the queue is empty - nothing to write until the next collection")
        mark_run("write")
        return
    recent = []
    if BRIDGE_URL:
        rr = bridge("recent")
        if rr.get("ok"):
            recent = rr["rows"]
        elif DRY:
            print("bridge 'recent' not available yet (Apps Script not updated):", rr)
        else:
            raise SystemExit(f"bridge 'recent' failed: {rr}")
    seen_src = {r.get("source") for r in recent}
    ig_log = []
    if BRIDGE_URL and not DRY:
        recent += instagram_recent(ig_log)
    today = datetime.datetime.now(IST).strftime("%A %d %B %Y")
    out, log = [], []
    state = load_state()
    REOFFER[:] = pending_ids()
    log.append(f"earlier stories still waiting for images: {REOFFER}")
    log += ig_log
    if MODE == "write":
        news = [n for n in load_queue() if n.get("verified") and allnews.local_ok(n["url"], n.get("title", ""))]
        log.append(f"write round: {len(news)} news waiting in the queue (written in priority order)")
    else:
        if PICK_ONLY:      # owner 1 Nov (Coimbatore pick flow): ONLY the links the owner ticked / the automatic top 12 are written
            news = []
            log.append("pick round: only the picked links are written (research_free/pick.py)")
        else:
            news = allnews.collect(log)                               # EVERY item from every source
            have = {n["key"] for n in news}
            news += [q for q in load_queue() if q["key"] not in have]      # earlier collected, not written yet: stays in the queue
    for n in news:
        n["score"] = score(n)
        n["status"] = "collected"
        n["story"] = ""
    for r in recent:   # already posted/filed earlier: never write them twice
        for n in news:
            if r.get("source") and (r["source"] == n["url"] or r["source"] in n["alts"]):
                n["status"] = "already filed"
            elif n["title"] and _fr().similar(r.get("headline_ta", ""), n["title"], 0.6, r.get("researched")):
                n["status"] = "already filed"
    for n in news:
        st = state.get(n["key"], {})
        if not recheck_once(st, n.get("url", "")) and (st.get("s") in ("filed", "dup", "notext", "old", "notdistrict", "notcity") or st.get("n", 0) >= 10):      # 30 Oct: notcity was missing (checked again every round)
            n["status"] = n["status"] if n["status"] != "collected" else "checked earlier: " + st.get("s", "failed")
    manual_links = [u.strip() for u in re.split(r"[\s,]+", os.environ.get("MANUAL_URL", "")) if u.strip().startswith("http")]
    for mu in manual_links:     # owner 26 Oct: links given by hand are written whatever their date; still skipped if already filed or no article text
        news.insert(0, {"key": mu, "url": mu, "title": "", "source": "manual", "published": "", "via": "dinamalar-list",
                        "query": "manual", "snippet": "", "outlets": ["manual link"], "alts": [mu], "mentions": 3,
                        "area": AREA, "score": 999, "status": "collected", "story": "", "manual": True})
        log.append(f"manual link added: {mu}")
    queues = {AREA: []}      # one page: one queue
    rechecks = 0
    for n in sorted(news, key=lambda x: -x["score"]):
        if n["status"] == "collected" and (allnews.other_district(n["title"]) or allnews.outside_district(n["title"], n.get("via", ""))):
            n["status"] = "not Coimbatore district news (state-wide / other district)"
            continue
        if n["status"] == "collected" and TOP_KINDS_ONLY and not n.get("manual"):
            if not top_kind(n["title"]):
                n["status"] = "not written: not power cut / rain / crime / accident"
                continue
            if allnews.statewide(n["title"], rain=top_kind(n["title"]) == "rain"):
                n["status"] = "not written: state-wide / other-district news"
                continue
        low = low_interest(n["title"], n.get("url", "")) if n["status"] == "collected" and not n.get("manual") else ""
        if low:      # owner 31 Oct: only news Instagram users watch is written (nothing opened, no model call)
            n["status"] = "not written: " + low
            continue
        if n["status"] == "collected" and (fresh(n["published"]) or _fr().power_cut_ahead(n["title"], n["published"])):
            queues[AREA].append(n)
        elif n["status"] == "collected" and any(w in (n.get("source") or "") for w in ("தினமணி", "தினமலர்")) and rechecks < 60:
            # the feed date of a Dinamani / Dinamalar item can be older than the story: open the article and use ITS date (checked when opened)
            rechecks += 1
            queues[AREA].append(n)
        elif n["status"] == "collected":
            n["status"] = "old"
    for a_ in queues:      # links given by hand go first, before any time is used up
        queues[a_] = [q for q in queues[a_] if q.get("manual")] + [q for q in queues[a_] if not q.get("manual")]
    from collections import Counter
    log.append("candidate filter: " + ", ".join(f"{k.split(':')[0][:40]}={v}" for k, v in Counter(n["status"] for n in news).most_common()))
    log.append(f"to write: {len(queues[AREA])} Coimbatore district candidates (max {MAX_STORIES} stories)")
    target, done, tried = {AREA: MAX_STORIES}, {AREA: 0}, {AREA: 0}
    if MODE == "both" and not PRIORITY_ONLY[0]:
        # owner 31 Oct: each round writes the TOP 3 by expected views; every power cut is written on top of them, first
        pcs = [q for q in queues[AREA] if _fr().is_power_cut(q["title"])]
        queues[AREA] = pcs + [q for q in queues[AREA] if q not in pcs]
        target = {AREA: MAX_STORIES + len(pcs)}
        log.append(f"round: top {MAX_STORIES} of {len(queues[AREA])} candidates" + (f" + {len(pcs)} power cut(s)" if pcs else ""))
    if TODAY[0] >= DAILY_CAP:
        log.append(f"daily cap: {TODAY[0]} stories already written today (cap {DAILY_CAP}) - only main / important news is written now")
    if os.environ.get("WRITE_STORIES", "1") == "0" or TODAY[0] >= DAILY_CAP:      # archive-only round: collect and store everything, write nothing, send no email
        # priority scan: only a really urgent local story (accident / death / fire / blast / murder / flood / power shutdown, or reported by 3+
        # outlets) is written between the three normal rounds; if the writer rates it High it is filed and its images-needed email goes at once
        PRIO = ("பலி", "உயிரிழ", "விபத்து", "வெடி", "கொலை", "தீப்பிடி", "தீ விபத்து", "மின்தடை", "மின் தடை", "வெள்ளம்", "தற்கொலை", "கைது")
        target = {AREA: 2}
        for a_ in queues:
            pc = [q for q in queues[a_] if _fr().is_power_cut(q["title"])]      # owner 30 Oct: every power cut is written, cap or no cap - first
            queues[a_] = pc + [q for q in queues[a_] if q not in pc and (q["mentions"] >= 3 or any(w in q["title"] for w in PRIO))][:max(0, 4 - len(pc))]
            target = {AREA: max(2, len(pc))}
        PRIORITY_ONLY[0] = True
        log.append("archive round: priority scan only (urgent local news, if any)")
    if MODE == "collect":
        try:
            verify_candidates(queues[AREA], state, log)
        except Exception as e:
            log.append(f"checking at collection failed (the writer checks each news instead): {str(e)[:120]}")
        target = {AREA: 0}
        log.append("collect round: nothing is written now - the writer job takes the queue by priority and posts each story at once")
    # every story -> ONE post on Coimbatore 360 (single page, no collaborator)
    tries_cap = {AREA: MAX_STORIES * int(os.environ.get("TRIES_PER_STORY", "40"))}      # owner 31 Oct: 30 tries left a round with 0 of its top 3 (old / repeated news first) - keep going until 3 are written or time runs out
    log.append(f"candidates waiting: {len(queues[AREA])} Coimbatore; time left {int((DEADLINE - time.time()) / 60)} min")

    def prepare(n, area):
        """worker thread: open the article, check it, write the story and its image brief. Never raises; returns a result dict."""
        try:
            links = [u for u in [n["url"]] + n.get("alts", []) if u]
            links = list(dict.fromkeys([u for u in links if "news.google.com" not in u] + links))      # a direct publisher link first, Google redirects last
            url, last = None, None
            for u in links[:4]:
                try:
                    url = allnews.resolve(u)
                    break
                except Exception as e:
                    last = e
            if url is None:
                raise last or RuntimeError("no link")
            art = allnews.article_any(url)
            art["url"] = url
            for k in ("text", "title"):      # some outlets type ூ as ு+ா (ப.வேலுார்): normalise so the writer copies the correct spelling
                if art.get(k):
                    art[k] = art[k].replace("ுா", "ூ")
            art["title"] = art.get("title") or n["title"]
            art["published"] = art.get("published") or n["published"]
            if allnews.incomplete(art.get("text", "")):      # owner 31 Oct: never write from a fragment - the same story at its other outlets
                for alt in [u for u in links if u != url][:3]:
                    try:
                        u2 = allnews.resolve(alt)
                        a2 = allnews.article_any(u2)
                    except Exception:
                        continue
                    if len(a2.get("text", "")) > len(art.get("text", "")):
                        art.update(text=a2["text"], url=u2, title=a2.get("title") or art["title"], published=a2.get("published") or art["published"])
                        url = u2
                    if not allnews.incomplete(art["text"]):
                        break
        except Exception as e:
            return {"skip": f"could not open the article: {str(e)[:60]}", "log": f"skip ({area}) could not open: {n['title'][:50]} [{n['url'][:60]}] {str(e)[:80]}"}
        if url in seen_src or any(r.get("source") == url for r in recent):
            return {"skip": "already filed", "s": "dup", "log": f"skip ({area}) already filed: {art['title'][:50]}"}
        bw = len(body_words(art))
        if len(art["text"]) < 20 or bw < HEADLINE_ONLY_MIN:      # owner 25 Oct: never skipped for length - but a page with only a headline has no facts (RN-12)
            return {"skip": "article has no text beyond its headline", "s": "notext", "log": f"skip ({area}) only a headline, {bw} words of text: {art['title'][:50]} [{url[:60]}]"}
        if not tamil_source(art) and not n.get("manual"):      # owner 29 Oct: Tamil sources only (a link given by hand is still written)
            return {"skip": "not a Tamil-language article", "s": "notext", "log": f"skip ({area}) not a Tamil article: {art['title'][:50]} [{url[:60]}]"}
        if not published_today(art["published"]) and not n.get("manual") and not _fr().power_cut_ahead(art["title"], art["published"]):      # owner 29 Oct: published TODAY only (a hand-given link: any date; 30 Oct: a power cut by its CUT day)
            return {"skip": "old", "s": "old", "log": f"skip ({area}) too old ({art['published'] or 'no date'}): {art['title'][:50]}"}
        if ((not (allnews.has_place(n["title"]) or allnews.has_place(art["title"]) or allnews.has_place(art["text"][:300])
                  or allnews.url_district(art["url"]) in allnews.DISTRICT_SLUGS) and n.get("via", "") != "dinamalar-list")
                or not allnews.local_ok(art["url"], art["title"])) and not n.get("manual"):
            return {"skip": "not Coimbatore district news (article names no Coimbatore place)", "s": "notdistrict", "log": f"skip ({area}) no Coimbatore place in article: {art['title'][:50]}"}
        town = allnews.outside_city(art["title"], art["text"][:300])
        if town and not n.get("manual"):      # owner 29 Oct: Coimbatore city only for now
            return {"skip": f"not Coimbatore city news ({town})", "s": "notcity", "log": f"skip ({area}) outside the city ({town}): {art['title'][:50]}"}
        low = "" if n.get("manual") else low_interest(art["title"], art["url"])
        if low:      # owner 31 Oct: the article's own headline (a listing title can differ) - checked before any model call
            return {"skip": "not written: " + low, "s": "notext", "log": f"skip ({area}) low interest ({low}): {art['title'][:50]}"}
        if not n.get("manual") and any(_fr().similar(r.get("headline_ta", ""), art["title"], 0.55, r.get("researched"))
                                       or same_news(r.get("headline_ta", ""), art["title"], r.get("researched"))
                                       or _fr().same_power_cut(r.get("headline_ta"), r.get("researched"), art["title"], art["published"]) for r in recent):      # already posted / written
            return {"skip": "already filed", "s": "dup", "log": f"skip ({area}) similar to a filed story: {art['title'][:50]}"}
        dup = "" if n.get("manual") else same_event_filed(art, recent)
        if dup:      # 29 Oct (Namakkal RN-193 = RN-168): the same event from another outlet under another headline is not written again
            return {"skip": "already filed", "s": "dup", "log": f"skip ({area}) same event as {dup}: {art['title'][:50]}"}
        area = allnews.area_of_story(art["title"], art["text"])      # always AREA ("N"): the one Coimbatore 360 page
        art["interest"] = interest(art)
        print(f"writing [{area}]: {art['title'][:60]}", flush=True)
        try:
            res = run.write(art, today)
        except Exception as e:
            res = e
        scenes = None
        if not isinstance(res, Exception) and not n.get("manual"):
            d0 = res[0] if isinstance(res, tuple) else {}
            town = allnews.outside_city(d0.get("tamil_headline", ""), d0.get("location", ""), d0.get("english_headline", ""))
            loc0 = d0.get("location", "") or ""
            paper_page = (allnews.url_district(art.get("url", "")) or "").lower() in allnews.DISTRICT_SLUGS
            if (not town and loc0 and not allnews.has_place(loc0) and re.search(r"தமிழ்நாடு|தமிழகம்|மாநில|Tamil Nadu", loc0)
                    and (not paper_page or "உள்ளிட்ட" in d0.get("tamil_headline", ""))):
                town = "state-wide: " + loc0[:40]      # 29 Oct RN-8 / RN-20: written for the whole state, not the city
            if town:      # 29 Oct RN-2 (Valparai): written, then blocked at posting - now dropped before the picture is made
                print(f"not Coimbatore city news after writing ({town}): {art['title'][:60]}", flush=True)
                res = RuntimeError(f"not Coimbatore city news ({town})")
        if not isinstance(res, Exception):
            try:
                scenes = image_scenes(art, res[0])
            except Exception as e:
                print("image brief failed, using the writer's image prompt:", str(e)[:120], flush=True)
        return {"art": art, "res": res, "scenes": scenes, "area": area}

    for a_ in queues:      # owner 26 Oct: ONE priority order (highest first); links given by hand first
        queues[a_].sort(key=lambda q: (not q.get("manual"), not q.get("verified"), -q.get("score", 0)))

    def next_item():
        """the highest-priority waiting news; the same event already filed this round is never written again"""
        while True:
            open_ = [a for a in queues if queues[a] and done[a] < target[a] and tried[a] < tries_cap[a]]
            if not open_:
                return None
            area = max(open_, key=lambda a: (queues[a][0].get("manual", False), bool(queues[a][0].get("verified")), queues[a][0].get("score", 0)))
            q = queues[area].pop(0)
            if q["title"] and any(difflib.SequenceMatcher(None, q["title"], t).ratio() > 0.8 for t in filed_titles):      # owner 25 Oct: only the same event
                q["status"] = "duplicate of a story filed this round"
                continue
            return q, area

    from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
    workers = max(1, int(os.environ.get("WRITE_WORKERS", "3")))      # stories written at the same time (the models answer in parallel)
    reserve = int(os.environ.get("RESERVE_MIN", "6")) * 60           # no new story is started this close to the deadline
    filed_titles, unsent = [], []
    running = {}
    pool = ThreadPoolExecutor(max_workers=workers)
    while True:
        while len(running) < workers and time.time() < DEADLINE - reserve:
            nx = next_item()
            if not nx:
                break
            n, area = nx
            tried[area] += 1
            log.append(f"try ({area}) manual={bool(n.get('manual'))}: {(n.get('title') or n.get('url') or '')[:60]}")
            stt = state.setdefault(n["key"], {"n": 0})
            stt["n"] = stt.get("n", 0) + 1
            stt["t"] = datetime.datetime.now(IST).isoformat()
            running[pool.submit(prepare, n, area)] = (n, stt)
        if not running or time.time() > DEADLINE + 240:
            break
        fin, _ = wait(list(running), timeout=30, return_when=FIRST_COMPLETED)
        for f in fin:
            n, stt = running.pop(f)
            r = f.result()
            if r.get("skip"):
                n["status"] = r["skip"]
                if r.get("s"):
                    stt["s"] = r["s"]
                log.append(r["log"])
                continue
            art, area = r["art"], r["area"]
            story, why = file_story(art, r["res"], log, recent, r["scenes"])
            if not story:
                n["status"] = "not filed: " + why
                v = refusal_verdict(why, stt)
                if v:      # owner 30 Oct: not written again and again (checked earlier from now on)
                    stt["s"] = v
                log.append(f"NOT filed ({area}) {art['title'][:50]}: {why}")
                continue
            if (PRIORITY_ONLY[0] and str(story.get("importance", "")).strip() != "High"
                    and not _fr().is_power_cut(art["title"], story.get("tamil_headline"), story.get("category"))):      # owner 30 Oct: a power cut is never left out
                n["status"] = "checked: not urgent, left for the next normal round"
                log.append(f"not urgent ({area}) {art['title'][:50]}")
                continue
            story["post_to"] = PAGE_NAME      # single page: every story is posted on Coimbatore 360 only (no collab)
            story["_area"], story["_score"] = area, n["score"]
            out.append(story)
            recent.append({"headline_ta": story["tamil_headline"], "source": art["url"], "reel_script": story.get("reel_script") or "",      # 30 Oct RN-214 = RN-209,
                           "story_id": story.get("story_id") or "a story filed this round",                                                    # filed 20 min apart in one round
                           "researched": datetime.datetime.now(_fr().IST).strftime("%d %b %Y, %H:%M")})
            filed_titles.append(art["title"])
            n["status"], n["story"], stt["s"] = "filed", story["tamil_headline"], "filed"
            done[area] += 1
            # saved in the Sheet at once (images first): a story written in this round is never lost if the run is stopped later
            if time.time() > DEADLINE:
                story["auto_images"] = True      # no time left for images here: the posting job makes them within minutes
            if not DRY:
                if send_batch([story], log):
                    trigger_posting(log)      # posts within minutes (pictures still missing are made by that job's check step)
                else:
                    unsent.append(story)
    pool.shutdown(wait=False, cancel_futures=True)
    log.append(f"candidate loop ended: left {len(queues[AREA])}, tried={tried}, done={done}, time left {int((DEADLINE - time.time()) / 60)} min")
    log.append(f"filed: {done[AREA]} Coimbatore district stories (target {MAX_STORIES}), reels only")
    # the queue: every eligible news not written yet (new, not tried this round, or a try that can be repeated) - highest priority first
    # owner 26 Oct: ONLY news that was opened and checked (real Coimbatore-district news that can be written) goes into the queue.
    # A link that could not be opened is not queued - the next collection finds it again and checks it then.
    waiting = [n for n in news if str(n["status"]).startswith(("collected", "could not open", "not filed"))
               and (n.get("verified") or n.get("manual") or MODE == "both") and allnews.local_ok(n["url"], n.get("title", ""))]      # 31 Oct: a round's leftovers compete again next round (checked when written)
    for k in (["collect"] if MODE == "collect" else ["write"] if MODE == "write" else ["collect", "write"]):
        mark_run(k)
    left = 0
    if PICK_ONLY:
        waiting = []      # the pick flow keeps its own list (pick_state.json): nothing is queued for the 2-hourly writer
    try:
        left = save_queue(waiting) if not PICK_ONLY else 0
        log.append(f"queue: {left} news waiting to be written")
    except Exception as e:
        log.append(f"queue not saved: {e}")
    if left and MODE == "collect":      # owner 31 Oct: a writer round never restarts itself - the next round compares the rest again
        # the writer goes on at once (after this run has saved the queue - both share one concurrency group, so it starts when this one ends);
        # a writer round that could not write anything does not restart itself (no loop) - its 20-minute schedule tries again
        trigger_workflow("write_stories.yml", None, log)
    for n in news:
        if n["status"] == "collected":
            n["status"] = "queued for writing" if MODE == "collect" else "collected (not in this round's top)"
    if PICK_ONLY:      # owner 4 Nov: the pick round must know which picked news the writer REFUSED (else offered and refused every round)
        try:
            (HERE / "results" / "pick_refused.json").write_text(json.dumps(
                {n["url"]: n["status"] for n in news if str(n.get("status", "")).startswith(REFUSED)}, ensure_ascii=False, indent=1), encoding="utf-8")
        except Exception as e:
            log.append(f"pick refusals not saved: {e}")
    # --- the list of ELIGIBLE news only (owner 26 Oct): Coimbatore-district news of today / yesterday that was not posted before.
    # Other-district, old and already posted items are dropped silently (they used to fill the "All News" tab: 24,000 rows in 5 days).
    NOT_ELIGIBLE = ("old", "not Coimbatore", "already filed", "checked earlier", "duplicate of a story filed")
    news = [n for n in news if not str(n["status"]).startswith(NOT_ELIGIBLE)]
    rows = [{"source": ", ".join(n["outlets"])[:80], "area": "Coimbatore district", "url": n["url"], "title": n["title"],
             "published": n["published"][:16].replace("T", " "), "mentions": n["mentions"], "score": n["score"], "status": n["status"], "story": n["story"]} for n in news]
    try:
        import csv
        ARCHIVE.mkdir(exist_ok=True)
        f = ARCHIVE / (datetime.datetime.now(IST).strftime("%Y-%m") + ".csv")
        new = not f.exists()
        with open(f, "a", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            if new:
                w.writerow(["collected_ist", "source", "area", "url", "title", "published", "mentions", "score", "status", "story"])
            stamp = datetime.datetime.now(IST).strftime("%Y-%m-%d %H:%M")
            for r in rows:
                w.writerow([stamp, r["source"], r["area"], r["url"], r["title"], r["published"], r["mentions"], r["score"], r["status"], r["story"]])
        save_state(state)
    except Exception as e:
        log.append(f"archive file not written: {e}")
    if BRIDGE_URL and not DRY and rows:
        try:
            for i in range(0, len(rows), 60):
                rr = requests.post(BRIDGE_URL, params={"key": BRIDGE_KEY}, data=json.dumps({"action": "archiveNews", "rows": rows[i:i + 60]}), timeout=180)
                log.append(f"All News sheet: {rr.text[:100]}")
        except Exception as e:
            log.append(f"All News sheet not updated: {e}")
    Path(HERE / "results").mkdir(exist_ok=True)
    (HERE / "results" / "collect.json").write_text(json.dumps({"log": log, "llm": llm.LOG, "stories": out}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n".join(log), f"\nstories: {len(out)}")
    if unsent and not DRY:
        for st in unsent:
            st["auto_images"] = st.get("auto_images") or not st.get("images")
        if not send_batch(unsent, log, images=False):      # last try for stories the bridge refused earlier
            raise RuntimeError("addStories failed for the final batch")
    elif not out and REOFFER and not DRY and MODE != "write":      # the reminder e-mail only from the 4-hourly round, never every 20 min
        try:      # no new story, but earlier stories still wait for images: ask for those again
            rr = requests.post(BRIDGE_URL, params={"key": BRIDGE_KEY}, data=json.dumps({"action": "reoffer", "ids": REOFFER}), timeout=180)
            print("reoffer:", rr.status_code, rr.text[:200])
        except Exception as e:
            print("reoffer failed:", e)
    elif not out and not DRY and os.environ.get("NO_NEWS_EMAIL", "") in ("1", "true", "yes"):
        # tell the owner why there is no email with prompts this time (never fails the run)
        try:
            why = "\n".join("- " + x[:170] for x in log if not x.startswith("source ")) or "- no new story this round"
            requests.post(BRIDGE_URL, params={"key": BRIDGE_KEY}, data=json.dumps({"action": "addStories", "stories": [], "no_news": why[:1500]}), timeout=120)
        except Exception as e:
            print("no-news email not sent:", e)


if __name__ == "__main__":
    main()
