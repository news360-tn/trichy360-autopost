"""owner 27 Nov evening: political news shows the REAL party flag / election symbol and the REAL photo of a leader the news names.

Only freely licensed files from Wikimedia Commons (public domain / CC0 / CC BY / CC BY-SA), kept in reel/assets/political/ with
their licence and author in manifest.json - never an AI-made or redrawn flag or face (a made-up picture of a real leader would be a
fake). A CC BY / BY-SA picture is credited on screen and in the caption (credit_line).

Matching is strict on purpose: a wrong face on a news reel is far worse than no face. A leader is matched only by a full-name form
(or a short name together with the party), never by a common first name alone (விஜய், பழனிசாமி, ராமதாஸ் are also ordinary names;
அண்ணாமலை is also part of திருவண்ணாமலை).

  parties(text) -> [party keys in order of first mention]   leaders(text) -> [leader keys]
  asset(kind, key) -> manifest entry with an absolute "path", or None   credit_line(keys) -> caption line or ""
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSETS = HERE / "assets" / "political"
TA = r"஀-௿"
NB = rf"(?<![{TA}])"      # a word start (not inside another Tamil word)

# party key -> Tamil forms (dotted / undotted short forms and the full name). Longest / most specific first.
PARTY_FORMS = {
    "ammk": ["அமமுக", "அ.ம.மு.க", "அம்மா மக்கள் முன்னேற்றக் கழக"],
    "aiadmk": ["அதிமுக", "அ.தி.மு.க", "அஇஅதிமுக", "அ.இ.அ.தி.மு.க"],
    "dmdk": ["தேமுதிக", "தே.மு.தி.க", "தேசிய முற்போக்கு திராவிடக் கழக"],
    "mdmk": ["மதிமுக", "ம.தி.மு.க", "மறுமலர்ச்சி திராவிட முன்னேற்றக் கழக"],
    "dmk": ["திமுக", "தி.மு.க", "திராவிட முன்னேற்றக் கழக"],
    "tvk": ["தவெக", "த.வெ.க", "தமிழக வெற்றிக் கழக"],
    "bjp": ["பாஜக", "பா.ஜ.க", "பாரதிய ஜனதா"],
    "pmk": ["பாமக", "பா.ம.க", "பாட்டாளி மக்கள் கட்சி"],
    "ntk": ["நாதக", "நா.த.க", "நாம் தமிழர் கட்சி"],
    "vck": ["விசிக", "வி.சி.க", "விடுதலைச் சிறுத்தைகள்"],
    "tmc": ["தமாகா", "த.மா.கா", "தமிழ் மாநில காங்கிரஸ்"],
    "congress": ["காங்கிரஸ்"],
    "mnm": ["மநீம", "மக்கள் நீதி மய்யம்"],
    "cpim": ["மார்க்சிஸ்ட் கம்யூனிஸ்ட்", "சிபிஎம்", "சி.பி.எம்"],
    "cpi": ["இந்திய கம்யூனிஸ்ட் கட்சி"],      # not சிபிஐ: that is also the CBI
    "iuml": ["முஸ்லிம் லீக்"],
}

# leader key -> (full-name forms, short forms that count only when the leader's party is in the same news, party key)
# Names only, never a post ("முதல்வர் ஸ்டாலின்"): who holds a post changes with elections, a name does not.
LEADER_FORMS = {
    "udhayanidhi_stalin": (["உதயநிதி ஸ்டாலின்"], ["உதயநிதி"], "dmk"),
    "mk_stalin": (["மு.க.ஸ்டாலின்", "மு.க. ஸ்டாலின்", "மு க ஸ்டாலின்"], ["ஸ்டாலின்"], "dmk"),
    "edappadi_palaniswami": (["எடப்பாடி பழனிசாமி", "எடப்பாடி கே. பழனிசாமி", "இபிஎஸ்", "இ.பி.எஸ்"], ["எடப்பாடி"], "aiadmk"),
    "vijay": (["தவெக தலைவர் விஜய்", "த.வெ.க. தலைவர் விஜய்", "தவெக விஜய்"], ["விஜய்"], "tvk"),
    "seeman": (["சீமான்"], [], "ntk"),
    "nainar_nagendran": (["நயினார் நாகேந்திரன்"], ["நயினார்"], "bjp"),
    "annamalai": (["கே.அண்ணாமலை", "கே. அண்ணாமலை"], ["அண்ணாமலை"], "bjp"),
    "anbumani_ramadoss": (["அன்புமணி ராமதாஸ்", "அன்புமணி"], [], "pmk"),
    "s_ramadoss": (["மருத்துவர் ராமதாஸ்", "டாக்டர் ராமதாஸ்", "எஸ்.ராமதாஸ்"], ["ராமதாஸ்"], "pmk"),
    "thirumavalavan": (["திருமாவளவன்"], [], "vck"),
    "vaiko": (["வைகோ"], [], "mdmk"),
    "premalatha_vijayakant": (["பிரேமலதா விஜயகாந்த்", "பிரேமலதா"], [], "dmdk"),
    "ttv_dhinakaran": (["டிடிவி தினகரன்", "டி.டி.வி. தினகரன்", "டி.டி.வி.தினகரன்"], ["தினகரன்"], "ammk"),
    "o_panneerselvam": (["ஓ.பன்னீர்செல்வம்", "ஓ. பன்னீர்செல்வம்", "ஓபிஎஸ்", "ஓ.பி.எஸ்"], [], ""),
    "kamal_haasan": (["கமல்ஹாசன்", "கமல் ஹாசன்"], [], "mnm"),
    "narendra_modi": (["நரேந்திர மோடி", "பிரதமர் மோடி"], ["மோடி"], "bjp"),
    "rahul_gandhi": (["ராகுல் காந்தி"], [], "congress"),
    "amit_shah": (["அமித் ஷா", "அமித்ஷா"], [], "bjp"),
    "selvaperunthagai": (["செல்வப்பெருந்தகை"], [], "congress"),
}


def _find(text, form):
    """first position of a form at a Tamil word start; -1 when absent"""
    m = re.search(NB + re.escape(form), text or "")
    return m.start() if m else -1


def parties(text):
    text = str(text or "")
    t = text.replace("தமிழ் மாநில காங்கிரஸ்", "தமாகா")      # its own party, not the Congress
    hits = {}
    for key, forms in PARTY_FORMS.items():
        pos = [p for p in (_find(t, f) for f in forms) if p >= 0]
        if pos:
            hits[key] = min(pos)
    return sorted(hits, key=hits.get)      # அதிமுக / மதிமுக hold திமுக only inside the word: _find needs a word start


def leaders(text):
    text = str(text or "")
    ps = set(parties(text))
    hits = {}
    for key, (full, short, party) in LEADER_FORMS.items():
        pos = [p for p in (_find(text, f) for f in full) if p >= 0]
        if not pos and short and party and party in ps:
            pos = [p for p in (_find(text, f) for f in short) if p >= 0]
        if key == "mk_stalin" and pos and "udhayanidhi_stalin" in hits:      # 'உதயநிதி ஸ்டாலின்' is not M. K. Stalin
            pos = [p for p in pos if not text[max(0, p - 9):p].strip().endswith("உதயநிதி")]
        if key == "annamalai":      # திருவண்ணாமலை, அண்ணாமலை பல்கலைக்கழகம் are places
            pos = [p for p in pos if not text[p:p + 20].startswith(("அண்ணாமலை பல்கலை", "அண்ணாமலையார்"))]
        if pos:
            hits[key] = min(pos)
    return sorted(hits, key=hits.get)


_MAN = None


def manifest():
    global _MAN
    if _MAN is None:
        try:
            _MAN = json.loads((ASSETS / "manifest.json").read_text(encoding="utf-8"))
        except Exception:
            _MAN = {}
    return _MAN


FREE = re.compile(r"^(public domain|pd|cc0|cc[ -]by(-sa)?( \d\.\d)?)", re.I)


def asset(kind, key):
    """kind 'flags' or 'leaders': the manifest entry with an absolute path; None when there is no free file for it"""
    e = (manifest().get(kind) or {}).get(key)
    if not e or not FREE.match(str(e.get("license") or "").strip()):
        return None
    p = ASSETS / str(e.get("file") or "")
    return dict(e, path=str(p)) if e.get("file") and p.exists() else None


def needs_credit(e):
    lic = str((e or {}).get("license") or "").lower()
    return bool(e) and not (lic.startswith("public domain") or lic.startswith("pd") or lic.startswith("cc0"))


def short_credit(e):
    """on-screen credit: 'படம்: author / Wikimedia Commons, CC BY-SA 4.0'"""
    a = re.sub(r"\s+", " ", str(e.get("author") or "")).strip()[:40]
    return f"படம்: {a + ' / ' if a else ''}Wikimedia Commons, {e.get('license')}"


def credit_line(flag_keys=(), leader_keys=()):
    """the caption line crediting the CC BY / BY-SA pictures used ('' when none needs a credit)"""
    out = []
    for kind, keys in (("leaders", leader_keys), ("flags", flag_keys)):
        for k in keys:
            e = asset(kind, k)
            if needs_credit(e):
                a = re.sub(r"\s+", " ", str(e.get("author") or "")).strip()[:50]
                out.append(f"{e.get('commons', '').replace('File:', '')} - {a}, {e.get('license')}")
    return ("📷 படங்கள் (Wikimedia Commons): " + "; ".join(out)) if out else ""


def for_reel(text, max_flags=3):
    """(flag entries, leader entries) that have a free file, for one reel's text"""
    fl = [dict(e, key=k) for k, e in ((k, asset("flags", k)) for k in parties(text)) if e][:max_flags]
    ld = [dict(e, key=k) for k, e in ((k, asset("leaders", k)) for k in leaders(text)) if e]
    return fl, ld


# the name shown under a leader's photo (as Tamil papers write it)
LEADER_NAME = {"udhayanidhi_stalin": "உதயநிதி ஸ்டாலின்", "mk_stalin": "மு.க. ஸ்டாலின்", "edappadi_palaniswami": "எடப்பாடி பழனிசாமி",
               "vijay": "விஜய்", "seeman": "சீமான்", "nainar_nagendran": "நயினார் நாகேந்திரன்", "annamalai": "அண்ணாமலை",
               "anbumani_ramadoss": "அன்புமணி ராமதாஸ்", "s_ramadoss": "ராமதாஸ்", "thirumavalavan": "திருமாவளவன்", "vaiko": "வைகோ",
               "premalatha_vijayakant": "பிரேமலதா விஜயகாந்த்", "ttv_dhinakaran": "டிடிவி தினகரன்", "o_panneerselvam": "ஓ. பன்னீர்செல்வம்",
               "kamal_haasan": "கமல்ஹாசன்", "narendra_modi": "நரேந்திர மோடி", "rahul_gandhi": "ராகுல் காந்தி", "amit_shah": "அமித் ஷா",
               "selvaperunthagai": "செல்வப்பெருந்தகை"}


def mentions(text, key):
    """does this one sentence name the leader (any of the leader's forms - the reel as a whole already matched strictly)"""
    full, short, _ = LEADER_FORMS.get(key, ([], [], ""))
    return any(_find(text, f) >= 0 for f in list(full) + list(short))


# where the face is in each photo (CSS object-position for the photo card); the rest: 50% 22%
FOCUS = {"thirumavalavan": "50% 8%", "seeman": "50% 6%", "kamal_haasan": "50% 8%", "narendra_modi": "40% 10%", "amit_shah": "50% 12%",
         "o_panneerselvam": "40% 20%"}
