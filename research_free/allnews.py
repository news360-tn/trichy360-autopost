"""Collect EVERY Coimbatore-district news item from many outlets (Dinamalar list + Google News + Bing News RSS, any extra
listing pages in sources.json), tag each one with the page area ('N' = the one Coimbatore 360 page; there is no second page),
merge duplicates reported by several outlets, and give the owner a full list to analyse. Nothing here writes posts; collect.py
ranks and writes the best ones. Every request is wrapped so one broken outlet never stops the others."""
import datetime, difflib, email.utils, html, json, os, re, time, urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
import requests
import sources as dinamalar

HERE = Path(__file__).resolve().parent
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "ta-IN,ta;q=0.9,en;q=0.5"}
IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))

# the page area code: Coimbatore 360 is a single page, so every story is "N" (kept as the code so collect.py stays like the Namakkal copy)
AREA = "N"
# the district as the newspapers write it in their links (url_district)
DISTRICT_SLUGS = ("coimbatore", "kovai")
# searches that cover the whole district (every taluk, big town and the city areas)
QUERIES = ["கோவை", "கோயம்புத்தூர்", "பொள்ளாச்சி", "மேட்டுப்பாளையம்", "சூலூர்", "அன்னூர்", "கிணத்துக்கடவு", "மதுக்கரை", "பேரூர்",
           "தொண்டாமுத்தூர்", "ஆனைமலை", "வால்பாறை", "காரமடை", "கருமத்தம்பட்டி", "கோவை மாவட்டம்", "கோயம்புத்தூர் மாவட்டம்",
           # government / TNEB announcements: the newspapers carry the official notices every day
           "கோவை மின்தடை", "பொள்ளாச்சி மின்தடை", "மேட்டுப்பாளையம் மின்தடை", "சூலூர் மின்தடை", "கோயம்புத்தூர் மின்தடை",
           "கோவை ஆட்சியர் அறிவிப்பு", "கோவை மாவட்ட நிர்வாகம்", "கோவை வேலைவாய்ப்பு முகாம்", "கோவை ஆட்சேர்ப்பு",
           "கோவை சிறப்பு முகாம்", "கோவை குறைதீர் கூட்டம்", "Coimbatore power shutdown", "Coimbatore collector",
           # the city areas, smaller towns and English reports are searched too
           "சிங்காநல்லூர்", "பீளமேடு", "சரவணம்பட்டி", "உக்கடம்", "காந்திபுரம்", "துடியலூர்", "பெரியநாயக்கன்பாளையம்", "சிறுமுகை",
           "போத்தனூர்", "வடவள்ளி", "குனியமுத்தூர்", "நெகமம்", "சோமனூர்", "மருதமலை",
           "Coimbatore", "Kovai", "Pollachi", "Mettupalayam", "Valparai", "Sulur", "Singanallur"]
# every outlet is also searched on its own (so a channel like News7 Tamil or NDTV Tamil is never missed)
# owner 29 Oct (17:59): Coimbatore news ONLY from these researched outlets - no other source is searched or kept.
# (approx. Coimbatore-city news per day: Dinamalar 10-20, Dinamani 8-12, Covai Mail 4-6, Arasiyal Today 3-5, Dinakaran 2-4,
#  Daily Thanthi / Maalaimalar / Thanthi TV 1-3 each, Hindu Tamil / Polimer 1-2 each, Malai Murasu / News18 Tamil 0-2, Indian Express Tamil 0-1)
SITES = {"தினமலர்": "dinamalar.com", "தினமணி": "dinamani.com", "கோவை மெயில்": "covaimail.com", "அரசியல் டுடே": "arasiyaltoday.com",
         "தினகரன்": "dinakaran.com", "தினத்தந்தி": "dailythanthi.com", "மாலைமலர்": "maalaimalar.com", "தந்தி டிவி": "thanthitv.com",
         "இந்து தமிழ்": "hindutamil.in", "பாலிமர்": "polimernews.com", "மாலை முரசு": "malaimurasu.com", "நியூஸ்18 தமிழ்": "tamil.news18.com",
         "இந்தியன் எக்ஸ்பிரஸ் தமிழ்": "tamil.indianexpress.com"}
SITE_QUERIES = ["கோவை", "கோயம்புத்தூர்", "பொள்ளாச்சி"]      # English for the English papers
OUTLET_WORDS = ["தினமலர்", "தினத்தந்தி", "தினமணி", "மாலைமலர்", "தினகரன்", "இந்து தமிழ்", "தி இந்து", "புதிய தலைமுறை", "நியூஸ்18", "நியூஸ் 18",
                "விகடன்", "ஏபிபி", "சமயம்", "polimer", "பாலிமர்", "தந்தி டிவி", "ஜீ தமிழ்", "நக்கீரன்", "டைம்ஸ்"]


def _get(url, timeout=40, headers=None):
    """owner 2 Nov (review): 38 of 77 articles 'could not be opened' in one round - a server error / timeout is tried again (3 tries)"""
    last = None
    for k in range(3):
        try:
            r = requests.get(url, headers=headers or UA, timeout=timeout, allow_redirects=True)
            r.raise_for_status()
            return r
        except requests.HTTPError as e:
            last = e
            if e.response is not None and e.response.status_code < 500 and e.response.status_code != 429:
                raise      # 403 / 404: trying again does not help
        except (requests.ConnectionError, requests.Timeout) as e:
            last = e
            if k >= 1:
                break      # a server that timed out twice is given up (a round must not wait minutes per link)
        time.sleep(3 * (k + 1))
    raise last


# Coimbatore district places (city areas / taluks / towns / well-known villages). A story that names none of them AND names a state-wide or
# another district's place is not Coimbatore district news (e.g. "17 districts rain alert", "Tiruppur accident", "Ooty landslide").
COIMBATORE_WORDS = ["கோவை", "கோயம்புத்தூர்", "பொள்ளாச்சி", "மேட்டுப்பாளையம்", "சூலூர்", "அன்னூர்", "கிணத்துக்கடவு", "மதுக்கரை", "பேரூர்",
                    "தொண்டாமுத்தூர்", "ஆனைமலை", "வால்பாறை", "காரமடை", "கருமத்தம்பட்டி", "சிறுமுகை", "பெரியநாயக்கன்பாளையம்", "துடியலூர்",
                    "காந்திபுரம்", "ஆர்.எஸ்.புரம்", "உக்கடம்", "சிங்காநல்லூர்", "பீளமேடு", "சரவணம்பட்டி", "போத்தனூர்", "குனியமுத்தூர்", "வடவள்ளி",
                    "கவுண்டம்பாளையம்", "சாய்பாபா காலனி", "டவுன்ஹால்", "ஒண்டிப்புதூர்", "இருகூர்", "நீலாம்பூர்", "செட்டிபாளையம்", "வெள்ளலூர்",
                    "மருதமலை", "வெள்ளியங்கிரி", "ஆழியாறு", "டாப்சிலிப்", "நெகமம்", "கோவில்பாளையம்", "சோமனூர்", "எட்டிமடை", "தடாகம்", "ஆலாந்துறை",
                    "கணுவாய்", "காளப்பட்டி", "வேடப்பட்டி", "ஜோதிபுரம்",
                    "Coimbatore", "Kovai", "Pollachi", "Mettupalayam", "Sulur", "Annur", "Valparai", "Kinathukadavu", "Madukkarai", "Perur",
                    "Thondamuthur", "Anaimalai", "Karamadai", "Singanallur", "Peelamedu", "Gandhipuram", "Ukkadam", "Saravanampatti", "Podanur",
                    "Vadavalli", "Thudiyalur", "Periyanaickenpalayam", "Sirumugai", "Karumathampatti", "Aliyar", "Topslip", "Marudhamalai"]
OUTSIDE_WORDS = ["தமிழகத்தில்", "தமிழ்நாட்டில்", "மாவட்டங்களில்", "மாவட்டங்களுக்கு", "மாவட்டங்கள்", "தென் மாவட்ட", "டெல்டா", "சென்னை", "மதுரை", "நாமக்கல்",
                 "திருச்சி", "திருச்சி", "ஈரோடு", "திருப்பூர்", "நீலகிரி", "ஊட்டி", "நெல்லை", "தூத்துக்குடி", "வேலூர்", "தஞ்சை", "கடலூர்", "காஞ்சிபுரம்", "புதுச்சேரி",
                 "தமிழக", "இந்தியா", "பிரதமர்", "முதல்வர் ஸ்டாலின்", "விஜய்", "டெல்லி", "கேரளா", "கர்நாடக", "Chennai", "Tamil Nadu"]


# other districts and their towns (Coimbatore's neighbours first): a headline that names one of these and no Coimbatore place is not ours
OTHER_PLACES = ["திருப்பூர்", "அவிநாசி", "பல்லடம்", "உடுமலை", "தாராபுரம்", "காங்கேயம்", "வெள்ளகோவில்", "மடத்துக்குளம்", "குண்டடம்", "ஊத்துக்குளி",
                "நீலகிரி", "ஊட்டி", "உதகை", "குன்னூர்", "கோத்தகிரி", "கூடலூர்", "ஈரோடு", "சத்தியமங்கலம்", "கோபி", "பவானி", "பெருந்துறை", "அந்தியூர்",
                "பாலக்காடு", "கொச்சி", "திருச்சூர்", "மைசூரு", "சாம்ராஜ்நகர்",
                "நாமக்கல்", "ராசிபுரம்", "திருச்செங்கோடு", "பரமத்தி", "குமாரபாளையம்", "பள்ளிபாளையம்", "சேந்தமங்கலம்", "கொல்லிமலை", "மோகனூர்",
                "நாமகிரிப்பேட்டை", "வெண்ணந்தூர்", "எருமப்பட்டி",
                "திருச்சி", "சங்ககிரி", "எடப்பாடி", "ஓமலூர்", "மேட்டூர்", "தம்மம்பட்டி", "கெங்கவல்லி", "வாழப்பாடி", "ஆத்தூர்", "தலைவாசல்", "ஏற்காடு",
                "மல்லூர்", "பனமரத்துப்பட்டி", "ஆட்டையாம்பட்டி", "புகழூர்", "வேலாயுதம்பாளையம்", "மேச்சேரி", "காட்டுப்புத்தூர்",
                "கரூர்", "குளித்தலை", "திருச்சி", "முசிறி", "தொட்டியம்", "துறையூர்", "தர்மபுரி",
                "கிருஷ்ணகிரி", "ஓசூர்", "சென்னை", "கோயம்பேடு", "காசிமேடு", "செங்கல்பட்டு", "காஞ்சிபுரம்", "திருவள்ளூர்", "வேலூர் மாவட்ட", "ராணிப்பேட்டை", "திருப்பத்தூர்",
                "திருவண்ணாமலை", "விழுப்புரம்", "கள்ளக்குறிச்சி", "கடலூர்", "பெரம்பலூர்", "அரியலூர்", "தஞ்சா", "திருவாரூர்", "நாகை", "நாகப்பட்டினம்",
                "மயிலாடுதுறை", "புதுக்கோட்டை", "சிவகங்கை", "ராமநாதபுரம்", "மதுரை", "தேனி", "திண்டுக்கல்", "விருதுநகர்", "தூத்துக்குடி",
                "திருநெல்வேலி", "நெல்லை", "தென்காசி", "கன்னியாகுமரி", "நாகர்கோவில்", "புதுச்சேரி", "பெங்களூரு", "கேரளா", "கர்நாடக"]
STATE_WIDE = ["TN Rain", "Tamil Nadu", "தமிழகம்", "தமிழ்நாடு", "புயல் எதிரொலி", "புயல் எச்சரிக்கை", "தீவிர புயல்", "புயல் உருவாக", "வங்கக்கடலில்", "அரபிக்கடலில்"]
# roads inside Coimbatore city named after other towns ("அவிநாசி சாலை" = Avinashi Road, Trichy Road, Sathy Road, Palakkad Road):
# they never make a headline "another district" - the headline / article must still name a Coimbatore place or be on the paper's Coimbatore page
CITY_ROADS = ["அவிநாசி சாலை", "அவிநாசி ரோடு", "திருச்சி சாலை", "திருச்சி ரோடு", "சத்தி சாலை", "சத்தியமங்கலம் சாலை", "பாலக்காடு சாலை",
              "Avinashi Road", "Avinashi road", "Trichy Road", "Trichy road", "Sathy Road", "Sathy road", "Palakkad Road", "Palakkad road"]


def _forms(w):
    """a place name and the forms it takes before a Tamil ending: திருவாரூர் -> திருவாரூரில், திருச்சி -> சேலத்தில்"""
    out = [w]
    if w.endswith("\u0bcd") and len(w) > 3:
        out.append(w[:-1])
    if w.endswith("ம்") and len(w) > 3:
        out.append(w[:-2] + "த்")
    if w.endswith("டு") and len(w) > 3:      # ஏற்காடு -> ஏற்காட்டில், திருச்செங்கோடு -> திருச்செங்கோட்டில்
        out.append(w[:-1] + "்ட")
    return out


OTHER_EN = ["tiruppur", "tirupur", "avinashi", "palladam", "udumalpet", "udumalaipettai", "udumalai", "dharapuram", "kangeyam", "nilgiris", "ooty",
            "udhagamandalam", "coonoor", "kotagiri", "gudalur", "erode", "sathyamangalam", "gobichettipalayam", "palakkad", "kochi", "mysuru",
            "namakkal", "rasipuram", "tiruchengode", "trichy", "yercaud", "chennai", "madurai", "trichy", "tiruchirappalli", "tiruvarur",
            "karur", "dharmapuri", "krishnagiri", "hosur", "vellore", "thanjavur", "kanniyakumari", "kanyakumari", "dindigul",
            "tirunelveli", "thoothukudi", "puducherry", "bengaluru", "kerala", "karnataka"]


def url_district(url):
    """the district a newspaper filed the article under, read from its link ('' when the link does not say)"""
    u = (url or "").lower()
    for pat in (r"district-news-([a-z]+)", r"/edition-[a-z]+/([a-z]+)/", r"dinakaran\.com/district/([a-z]+)[-_/]", r"tamil\.oneindia\.com/news/([a-z]+)/",
                r"/districts?/([a-z]+)[-_/]", r"/news/district/([a-z]+)"):
        m = re.search(pat, u)
        if m:
            return m.group(1)
    return ""


NON_NEWS = ("weekly-supplements", "/cinema", "/entertainment", "/lifestyle", "/recipe", "/food/", "/health/", "/technology", "/tech/",
            "/astrology", "/photogallery", "/videos/", "/video/", "/sports/", "/world/", "/national/", "/trending/", "/web-stories")


LISTING = re.compile(r"/(topic|topics|tag|tags|author|authors|search)/|/page-?\d+(/|$)|[?&]page=\d", re.I)


def is_listing(url):
    """a topic / tag / author / search page lists many stories from everywhere - it is not one news article
    (29 Oct RN-194: tamil.abplive.com/topic/missing-girl/page-2 gave a Panruti (Cuddalore) story to Namakkal 360)"""
    return bool(LISTING.search(url or ""))


def local_ok(url, title):
    """the link and headline allow this to be Coimbatore-district news: not filed under another district, not a supplement / cinema / recipe
    page, no other district or state-wide wording in the headline - unless the headline itself names a Coimbatore-district place"""
    if is_listing(url):
        return False
    if other_district(title):
        return False
    if has_place(title):
        return True
    d = url_district(url)
    if d and d not in DISTRICT_SLUGS:
        return False
    return not any(s in (url or "").lower() for s in NON_NEWS)


def other_district(title):
    """headline names another district / town / the whole state and no Coimbatore-district place"""
    t = _no_city_roads(title)
    low = t.lower()
    return not has_place(t) and (any(f in t for w in OTHER_PLACES for f in _forms(w)) or any(w in t for w in STATE_WIDE)
                                 or any(re.search(r"\b" + w + r"\b", low) for w in OTHER_EN))


# these headlines are never Coimbatore-district news, even when Coimbatore is one name in a long list
ALWAYS_OUTSIDE = ["மாவட்டங்களில்", "மாவட்டங்களுக்கு", "மாவட்டங்கள்", "தமிழகத்தில்", "தமிழ்நாட்டில்", "தமிழகம் முழுவதும்", "மாநிலம் முழுவதும்",
                  "மத்தியப் பிரதேச", "மத்திய பிரதேச", "ராஜ்யசபா", "மாநிலங்களவை", "பிரதமர்", "இடைத்தேர்தல்", "தேர்தல் ஆணையம்", "உச்ச நீதிமன்றம்"]
# weather forecasts / alerts are not local reporting
WEATHER_FORECAST = ["மழை எச்சரிக்கை", "மஞ்சள் எச்சரிக்கை", "ஆரஞ்சு எச்சரிக்கை", "சிவப்பு எச்சரிக்கை", "வானிலை", "ரெட் அலர்ட்", "ஆரஞ்சு அலர்ட்", "மஞ்சள் அலர்ட்", "மழைக்கு வாய்ப்பு", "மழை பெய்ய வாய்ப்பு",
                    "கனமழை பெய்யும்", "கனமழைக்கு வாய்ப்பு", "காற்றழுத்த", "புயல் உருவாக", "வளிமண்டல", "பள்ளிகளுக்கு விடுமுறை"]


def _no_city_roads(text):
    t = text or ""
    for r in CITY_ROADS:
        t = t.replace(r, " ")
    return t


def _stem_forms(w):
    """a Tamil place name and the stem it keeps before an ending (சூலூர் -> சூலூரில், ஆர்.எஸ்.புரம் -> ஆர்.எஸ்.புரத்தில்,
    ஆழியாறு -> ஆழியாற்றில்), plus the old print spelling some outlets use (சூலுார், பீளமேடு stays)"""
    if w.endswith("ம்") and len(w) > 4:
        st = w[:-2]
    elif w.endswith(("\u0bcd", "\u0bc1")) and len(w) > 3:
        st = w[:-1]
    else:
        st = w
    return list(dict.fromkeys([st, st.replace("\u0bc2", "\u0bc1\u0bbe")]))


# Tamil joins a place name to its ending (பொள்ளாச்சியில், சூலூரில், ஆர்.எஸ்.புரத்தில்), so match the stems too
PLACE_STEMS = list(dict.fromkeys(f for w in COIMBATORE_WORDS if not w.isascii() for f in _stem_forms(w))) + [
    "ஆர்.எஸ். புர", "ஆர் எஸ் புர", "சாய்பாபா காலனி", "சாய்பாபாகாலனி", "டாப் சிலிப்", "டாப்சிலிப்", "ஆழியார்"]
# words that contain a place stem but are not the place: பேரூராட்சி = town panchayat (every district), கோவைக்காய் = a vegetable,
# கோபிசெட்டிபாளையம் = Gobi in Erode district (contains செட்டிபாளையம்)
NOT_PLACE = ["பேரூராட்சி", "பேரூர் கழக", "பேரூர் செயலாளர்", "கோவைக்காய்", "கோபிசெட்டிபாளைய", "கோபிச்செட்டிபாளைய"]


# owner 29 Oct: START WITH COIMBATORE CITY ONLY (the whole district later: env CITY_ONLY=0 in the workflows).
# A story about a town outside the city is skipped unless it also names a city area; "கோவை" alone stays (the papers write it for city news).
CITY_ONLY = os.environ.get("CITY_ONLY", "1") == "1"
TOWNS = ["பொள்ளாச்சி", "மேட்டுப்பாளையம்", "சூலூர்", "அன்னூர்", "வால்பாறை", "கிணத்துக்கடவு", "மதுக்கரை", "பேரூர்", "தொண்டாமுத்தூர்", "ஆனைமலை",
         "ஆழியாறு", "காரமடை", "சிறுமுகை", "கருமத்தம்பட்டி", "பெரியநாயக்கன்பாளையம்", "நெகமம்", "சோமனூர்", "தடாகம்", "ஆலாந்துறை", "டாப்சிலிப்",
         "வெள்ளியங்கிரி", "எட்டிமடை", "Pollachi", "Mettupalayam", "Sulur", "Annur", "Valparai", "Kinathukadavu", "Madukkarai", "Perur",
         "Thondamuthur", "Anaimalai", "Aliyar", "Karamadai", "Sirumugai", "Karumathampatti", "Periyanaickenpalayam", "Topslip", "Negamam", "Somanur"]
# city roads named after a town are inside the city
TOWN_ROADS = ["மேட்டுப்பாளையம் சாலை", "மேட்டுப்பாளையம் ரோடு", "பொள்ளாச்சி சாலை", "பொள்ளாச்சி ரோடு", "Mettupalayam Road", "Pollachi Road"]
CITY_AREAS = ["காந்திபுர", "ஆர்.எஸ்.புர", "உக்கட", "சிங்காநல்லூ", "பீளமேடு", "பீளமேட்", "சரவணம்பட்டி", "போத்தனூ", "குனியமுத்தூ", "வடவள்ளி",
              "கவுண்டம்பாளைய", "சாய்பாபா", "டவுன்ஹால்", "ஒண்டிப்புதூ", "கணபதி", "செல்வபுர", "மருதமலை", "நஞ்சுண்டாபுர", "ரேஸ்கோர்ஸ்", "துடியலூ",
              "காளப்பட்டி", "வெள்ளலூ", "இருகூ", "நீலாம்பூ", "மாநகராட்சி", "மாநகர", "Gandhipuram", "R.S. Puram", "RS Puram", "Ukkadam",
              "Singanallur", "Peelamedu", "Saravanampatti", "Podanur", "Kuniyamuthur", "Vadavalli", "Race Course", "Town Hall", "Ganapathy",
              "Thudiyalur", "Corporation"]


POWER_CUT = re.compile(r"மின்\s*தடை|மின்தடை|மின்\s*நிறுத்த|மின்வெட்டு|மின்\s*வெட்டு|மின்\s*விநியோக(ம்)?\s*(நிறுத்த|தடை|இருக்காது)|"
                       r"power\s*(cut|shut|outage|supply\s*will)", re.I)


def outside_city(*texts):
    """CITY_ONLY: '' when the story can be Coimbatore city news, else the town outside the city it is about"""
    if not CITY_ONLY:
        return ""
    t = " ".join(x or "" for x in texts)
    if POWER_CUT.search(t):      # owner 29 Oct: power-cut news is taken from the WHOLE Coimbatore district (all other news: city only)
        return ""
    for w in TOWN_ROADS + NOT_PLACE:
        t = t.replace(w, " ")
    low = t.lower()
    if any(w.lower() in low for w in CITY_AREAS):
        return ""
    for w in TOWNS:
        if w.isascii():
            if re.search(r"\b" + re.escape(w.lower()) + r"\b", low):
                return w
        elif any(f in t for f in _forms(w)):
            return w
    return ""


# city only: the searches for the towns outside the city are not run (the paper's district pages are still read)
if CITY_ONLY:
    QUERIES = [q for q in QUERIES if not outside_city(q)]      # power-cut searches always stay (outside_city never blocks a power cut)
    SITE_QUERIES = [q for q in SITE_QUERIES if not outside_city(q)]
# owner 29 Oct: never miss a power cut anywhere in the district - every town is searched for its shutdown notice
QUERIES += [q for q in [f"{t} மின்தடை" for t in ("பொள்ளாச்சி", "மேட்டுப்பாளையம்", "சூலூர்", "அன்னூர்", "கிணத்துக்கடவு", "மதுக்கரை",
            "வால்பாறை", "காரமடை", "தொண்டாமுத்தூர்", "பேரூர்", "ஆனைமலை", "கருமத்தம்பட்டி", "பெரியநாயக்கன்பாளையம்")]
            + ["கோவை மின்தடை நாளை", "கோவை மின்தடை பகுதிகள்", "Coimbatore power cut tomorrow", "Pollachi power cut", "Mettupalayam power cut"]
            if q not in QUERIES]


def has_place(text):
    t = text or ""
    for w in NOT_PLACE:
        t = t.replace(w, " ")
    low = t.lower()
    return any(w in t for w in PLACE_STEMS) or any(w.lower() in low for w in COIMBATORE_WORDS if w.isascii())


def outside_district(text, via=""):
    """True when the headline is clearly NOT Coimbatore-district news: state-wide / multi-district / national news, weather forecasts, or a headline
    that names another place and none of ours. A headline that names no place at all is KEPT (many local reports omit it) - the article itself
    is checked for a Coimbatore place before anything is written (collect.py)."""
    text = text or ""
    if any(w in text for w in ALWAYS_OUTSIDE):
        return True
    if any(w in text for w in WEATHER_FORECAST) and not has_place(text):      # owner 31 Oct: a rain alert FOR Coimbatore is news; a general forecast is not
        return True
    if has_place(text):
        return False
    if via == "dinamalar-list":
        return False
    return any(w in _no_city_roads(text) for w in OUTSIDE_WORDS)


# owner 31 Oct (reel RN-98, NDRF at Aliyar dam - every outlet in the state carried it): news about the whole state / another district is
# never in a round's top 3, even when its headline also names a Coimbatore place
STATE_NEWS = ["NDRF", "தேசிய பேரிடர் மீட்பு", "சிறப்பு ரயில்", "அமைச்சர்", "முதல்வர்", "தமிழக", "தமிழ்நாடு", "தமிழகம்", "மாநில", "உள்ளிட்ட",
              "மாவட்டங்க", "இந்தியா", "மத்திய அரசு", "பிரதமர்",
              # owner 31 Oct (RN-103): a state leader's reaction is state politics, not Coimbatore news
              "உதயநிதி", "ஸ்டாலின்", "எடப்பாடி", "அன்புமணி", "அண்ணாமலை", "சீமான்", "விமர்சனம்", "விமர்சித்", "ரவுண்டு கட்ட"]


def statewide(title, rain=False):
    """True when the headline is about the whole state, the country or another district too (not a Coimbatore-only event).
    rain=True: a Coimbatore rain / fog report may also name a neighbour (Nilgiris, the Kerala border at Walayar) - only state-wide or
    many-district wording counts then"""
    t = _no_city_roads(title or "")
    low = t.lower()
    if rain:
        return not has_place(t) or any(w in t for w in ALWAYS_OUTSIDE + ["NDRF", "தேசிய பேரிடர் மீட்பு", "மாவட்டங்க", "தமிழகம் முழுவதும்"])
    if re.search(r"\d+\s*இடங்களில்", t):      # RN-38: raids at 25 places across the state
        return True
    return (any(w in t for w in STATE_NEWS + STATE_WIDE + ALWAYS_OUTSIDE) or any(f in t for w in OTHER_PLACES if w not in ("கோபி", "பவானி") for f in _forms(w))      # also people's names
            or any(re.search(r"\b" + w + r"\b", low) for w in OTHER_EN))


def area_of(text, default=AREA):
    """single page: every story goes to the Coimbatore 360 page (area code "N"); there is no Rasipuram-style second page"""
    return AREA


def area_of_story(title, lead):
    """single page: always the Coimbatore 360 page (area code "N")"""
    return AREA


def _clean_title(t):
    t = html.unescape(t or "").strip()
    return re.sub(r"\s+[-|–]\s+[^-|–]{2,40}$", "", t).strip()      # drop the " - outlet" suffix of RSS titles


def _outlet(t, fallback=""):
    m = re.search(r"\s[-|–]\s+([^-|–]{2,40})$", html.unescape(t or ""))
    return (m.group(1).strip() if m else fallback) or fallback


def _parse_pub(s):
    try:
        return email.utils.parsedate_to_datetime(s).astimezone(IST).isoformat()
    except Exception:
        return ""


def from_google(q):
    url = "https://news.google.com/rss/search?q=" + urllib.parse.quote(q + " when:2d") + "&hl=ta&gl=IN&ceid=IN:ta"
    root = ET.fromstring(_get(url).content)
    out = []
    for it in root.iter("item"):
        title = it.findtext("title") or ""
        src = it.find("source")
        out.append({"key": it.findtext("guid") or it.findtext("link"), "url": it.findtext("link"), "title": _clean_title(title),
                    "site": (src.get("url") if src is not None else "") or "",
                    "source": (src.text if src is not None and src.text else _outlet(title, "Google News")), "published": _parse_pub(it.findtext("pubDate") or ""),
                    "via": "google", "query": q, "snippet": re.sub(r"<[^>]+>", " ", html.unescape(it.findtext("description") or ""))[:300]})
    return out


def from_bing(q):
    url = "https://www.bing.com/news/search?q=" + urllib.parse.quote(q) + "&format=rss&setmkt=ta-IN&qft=sortbydate%3d%221%22"
    root = ET.fromstring(_get(url).content)
    out = []
    for it in root.iter("item"):
        link = it.findtext("link") or ""
        real = urllib.parse.parse_qs(urllib.parse.urlparse(link).query).get("url", [link])[0]
        title = it.findtext("title") or ""
        src = [e.text for e in it if e.tag.lower().endswith("source")]
        out.append({"key": real, "url": real, "title": _clean_title(title), "source": (src[0] if src else _outlet(title, "Bing News")),
                    "published": _parse_pub(it.findtext("pubDate") or ""), "via": "bing", "query": q,
                    "snippet": re.sub(r"<[^>]+>", " ", html.unescape(it.findtext("description") or ""))[:300]})
    return out


def from_dinamalar_list():
    out = []
    for u in dinamalar.candidate_links(60):
        out.append({"key": u, "url": u, "title": "", "source": "தினமலர்", "published": "", "via": "dinamalar-list", "query": "district list", "snippet": ""})
    return out


def from_listing(cfg):
    """extra outlet pages from sources.json: {"name","url","link_regex"} -> article links (the article page gives title/date/text)"""
    h = _get(cfg["url"]).text
    base = "{0.scheme}://{0.netloc}".format(urllib.parse.urlparse(cfg["url"]))
    seen, out = set(), []
    for m in re.finditer(cfg.get("link_regex", r'href="([^"#?]+/\d{5,}[^"]*)"'), h):
        u = urllib.parse.urljoin(base, m.group(1))
        if u not in seen:
            seen.add(u)
            out.append({"key": u, "url": u, "title": "", "source": cfg["name"], "published": "", "via": "listing", "query": cfg["url"], "snippet": ""})
    return out[: cfg.get("limit", 30)]


def _listing_hosts():
    try:
        return [urllib.parse.urlparse(c["url"]).netloc.replace("www.", "") for c in json.loads((HERE / "sources.json").read_text(encoding="utf-8"))]
    except Exception:
        return []


def tamil_outlet(it):
    """True when the item comes from one of the Tamil-language Tamil Nadu outlets in SITES (or a sources.json listing page).
    Google items carry the outlet's own site; Bing and listing items carry the article link itself."""
    if it.get("via") in ("dinamalar-list", "listing"):
        return True
    allowed = list(SITES.values()) + _listing_hosts()
    for u in (it.get("site") or "", it.get("url") or ""):
        pu = urllib.parse.urlparse(u)
        hp = (pu.netloc.replace("www.", "") + pu.path).lower()
        if "news.google.com" in hp or not pu.netloc:
            continue
        if any(a.lower() in hp or (it.get("via") == "google" and a.split("/")[0].lower() == pu.netloc.replace("www.", "").lower()) for a in allowed):
            return True
        return False
    return False


def collect(log):
    """every item from every source, merged. Returns a list of dicts (see keys above + area, mentions, outlets)."""
    items = []

    def add(fn, *a, label=""):
        try:
            got = fn(*a)
            log.append(f"source {label or fn.__name__}: {len(got)} items")
            items.extend(got)
        except Exception as e:
            log.append(f"source {label or fn.__name__} FAILED: {str(e)[:120]}")
    add(from_dinamalar_list, label="dinamalar list")
    for q in QUERIES:
        add(from_google, q, label=f"google '{q}'")
        add(from_bing, q, label=f"bing '{q}'")
    for name, dom in SITES.items():
        for q in SITE_QUERIES:
            add(from_google, f"{q} site:{dom}", label=f"google {name} '{q}'")
            add(from_bing, f"{q} site:{dom}", label=f"bing {name} '{q}'")
    try:
        for cfg in json.loads((HERE / "sources.json").read_text(encoding="utf-8")):
            add(from_listing, cfg, label=cfg["name"])
    except FileNotFoundError:
        pass
    before = len(items)
    items = [it for it in items if tamil_outlet(it)]      # owner 29 Oct: Tamil Nadu Tamil-language outlets only
    log.append(f"Tamil outlets only: kept {len(items)} of {before} items")
    # merge: same URL or very similar headline = one story reported by several outlets
    merged = []
    for it in items:
        if not it.get("key"):
            continue
        hit = None
        for m in merged:
            if m["key"] == it["key"] or m["url"] == it["url"]:
                hit = m
                break
            if it["title"] and m["title"] and difflib.SequenceMatcher(None, it["title"], m["title"]).ratio() > 0.62:
                hit = m
                break
        if hit:
            hit["outlets"].add(it["source"])
            hit["alts"].append(it["url"])
            if not hit["title"] and it["title"]:
                hit["title"] = it["title"]
            if not hit["published"] and it["published"]:
                hit["published"] = it["published"]
            if len(it.get("snippet", "")) > len(hit.get("snippet", "")):
                hit["snippet"] = it["snippet"]
            if it["via"] == "dinamalar-list" or (it["via"] == "bing" and hit["via"] == "google"):
                hit["url"] = it["url"]          # prefer a direct publisher link
                hit["via"] = it["via"]
        else:
            it = dict(it)
            it["outlets"] = {it["source"]}
            it["alts"] = [it["url"]]
            merged.append(it)
    for m in merged:
        m["mentions"] = len(m["outlets"])
        m["area"] = area_of(m["title"] + " " + m.get("snippet", ""))
        m["outlets"] = sorted(m["outlets"])
    log.append(f"all sources: {len(items)} items -> {len(merged)} different news")
    return merged


# ---------------------------------------------------------------- article text
def resolve(url):
    """Google News links are redirects; turn one into the publisher's page (needs the googlenewsdecoder package)."""
    if "news.google.com" not in url:
        return url
    err = ""
    for attempt in range(3):      # the decoder is rate-limited when many links come at once: pause and try again
        try:
            from googlenewsdecoder import gnewsdecoder
            r = gnewsdecoder(url, interval=2)
            if (r.get("success") or r.get("status")) and r.get("decoded_url"):      # 0.2.x answers "success", older versions "status"
                return r["decoded_url"]
            err = str(r.get("message") or "no decoded url")[:80]
        except Exception as e:
            err = f"decoder: {str(e)[:70]}"
        time.sleep(6 * (attempt + 1))
    try:
        final = _get(url, timeout=30).url
        if "news.google.com" not in final:
            return final
        raise RuntimeError("google page, not the article")
    except Exception as e:
        raise RuntimeError(f"google news link not decoded ({err}; {str(e)[:60]})")


def article_any(url):
    """title / published / text from any outlet's article page (JSON-LD first, then page paragraphs)."""
    if "dinamalar.com" in url:
        return dinamalar.article(url)
    h = _get(url, timeout=40).text
    title = pub = body = ""
    for blk in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', h, flags=re.S):
        try:
            data = json.loads(blk)
        except Exception:
            continue
        for d in (data if isinstance(data, list) else [data]):
            for e in (d.get("@graph", [d]) if isinstance(d, dict) else []):
                if isinstance(e, dict) and "Article" in str(e.get("@type", "")):
                    title = title or e.get("headline", "")
                    pub = pub or e.get("datePublished", "")
                    body = body or e.get("articleBody", "")
    if not title:
        m = re.search(r'property="og:title"\s+content="([^"]+)"', h) or re.search(r"<title>([^<]+)</title>", h)
        title = html.unescape(m.group(1)).strip() if m else ""
    if not pub:
        m = re.search(r'property="article:published_time"\s+content="([^"]+)"', h)
        pub = m.group(1) if m else ""
    body = dinamalar.clean_body(body) if body else ""
    if len(body) < 200:      # owner 31 Oct: the paragraphs INSIDE the article body (short ones too, never side columns / other stories)
        body = max(body, dinamalar.article_paragraphs(h), key=len)
    if len(body) < 200:      # last resort: the page's long Tamil lines
        body = max(body, dinamalar.long_lines(h), key=len)
    return {"url": url, "title": html.unescape(title).strip(), "published": pub, "text": html.unescape(body).strip()}


SENTENCE_END = re.compile(r"[.!?।\u0964\u201d\"')\]]\s*$")


def incomplete(text):
    """owner 31 Oct: an article that stops in the middle of a sentence (RN-241: '... அரசு பஸ்சை') or is only a few lines - the writer
    must not write a reel from a fragment"""
    t = (text or "").strip()
    return len(re.findall(r"[஀-௿]", t)) < 120 or not SENTENCE_END.search(t)


def _place_norm(t):
    return (t or "").replace("\u0bc1\u0bbe", "\u0bc2").replace("ப்ப", "ப")      # மோகனுார் = மோகனூர், பள்ளிப்பாளையம் = பள்ளிபாளையம்


CANON_PLACES = [w for w in dict.fromkeys(COIMBATORE_WORDS + TOWNS) if not w.isascii() and w not in ("கோவை", "கோயம்புத்தூர்")]


def places_in(text):
    """the district's towns / villages a text names (the district / city name itself is not counted) - owner 2 Nov (review)"""
    t = text or ""
    try:
        import names
        t = names.full_places(t)      # ப.வேலூர் -> பரமத்தி வேலூர், மே.பாளையம் -> மேட்டுப்பாளையம்
    except Exception:
        pass
    for w in globals().get("NOT_PLACE", []):
        t = t.replace(w, " ")
    if "_no_city_roads" in globals():
        t = globals()["_no_city_roads"](t)      # 'மேட்டுப்பாளையம் சாலை' is a road inside the city
    for r_ in globals().get("TOWN_ROADS", []):
        t = t.replace(r_, " ")
    t = _place_norm(t)
    return {w for w in CANON_PLACES if any(_place_norm(f) in t for f in _stem_forms(w) if len(f) >= 4)}


def different_places(a, b):
    """True when both headlines name a town / village of the district and they share none: 'வெண்ணந்தூர் கிராம சபை' and
    'மோகனூர் கிராம சபை' are two news, never one (owner 2 Nov review: 30 of ~40 writer skips were such false duplicates)"""
    x, y = places_in(a), places_in(b)
    return bool(x and y and not (x & y))


def written_elsewhere(headline, script):
    """a written story whose headline names no Coimbatore-district place and whose first two sentences name another district / the
    whole state is not Coimbatore news (the Namakkal RN-195 fix: Erode onion prices were written for the page)"""
    if has_place(headline or ""):
        return ""
    body = re.sub(r"மேலும் செய்திகளுக்கு.*$", "", script or "")
    first2 = " ".join(re.split(r"(?<=[.!?])\s+", body.strip())[:2])
    if first2 and other_district(first2):
        return "not Coimbatore district news (the story's first lines name another place and no Coimbatore place)"
    return ""
