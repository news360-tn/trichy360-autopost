"""Last Tamil proofread before a reel is built: spelling, sandhi (புணர்ச்சி), grammar and unclear sentences in everything that goes out
(headline, slide texts shown in the reel, the spoken script, the caption). Free models first, Claude only when they are not available.
Only exact, small corrections are applied; a correction that changes a number, or makes broken Tamil, is ignored."""
import difflib, json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "research_free"))

PROOF = """You are a senior Tamil news editor and proofreader. You get the texts of ONE Tamil news post as JSON.
Find every real mistake: wrong spelling, wrong sandhi (புணர்ச்சி, e.g. missing க்/ச்/த்/ப் doubling), wrong case ending, wrong verb or
plural agreement, a word that does not exist, a broken or unclear sentence, a sentence that mixes two facts, spoken/colloquial forms in the
news text (இருக்கு -> உள்ளது), and English words written in English letters inside Tamil text.
For each mistake give the EXACT wrong text as it appears (a few words, copied character by character) and the corrected text.
STRICT: never change a number, date, time, amount, name, place or fact; never add information; do not rewrite text that is already correct;
keep the closing follow line and hashtags as they are. If everything is correct, return an empty list.
Return ONLY JSON: {"fixes": [{"wrong": "exact text", "right": "corrected text", "why": "short reason"}]}"""

FIELDS = ("headline_ta", "reel_script", "caption")


def _texts(row):
    spec = json.loads(row.get("slides_spec") or "{}")
    slides = [{"title": s.get("title", ""), "lines": s.get("lines", [])} for s in spec.get("slides", [])]
    return {"headline_ta": row.get("headline_ta", ""), "hl1": spec.get("hl1", ""), "hl2": spec.get("hl2", ""), "slides": slides,
            "reel_script": row.get("reel_script", ""), "caption": (row.get("caption") or "").split("#")[0].strip()}


def _digits(t):
    return re.findall(r"\d+", t or "")


LAST = "மேலும் செய்திகளுக்கு திருச்சி த்ரீ சிக்ஸ்டி பக்கத்தை பின்தொடருங்கள்."
# page name, follow line and Trichy-district place names are never "corrected"
KEEP = ("திருச்சி", "திருச்சிராப்பள்ளி", "த்ரீ", "சிக்ஸ்டி", "360", "ஸ்ரீரங்கம்", "திருவெறும்பூர்", "லால்குடி", "மணப்பாறை", "முசிறி", "தொட்டியம்",
        "துறையூர்", "மண்ணச்சநல்லூர்", "உப்பிலியபுரம்", "மருங்காபுரி", "சமயபுரம்", "திருவானைக்காவல்", "துவாக்குடி", "நவல்பட்டு", "சோமரசம்பேட்டை",
        "புள்ளம்பாடி", "வையம்பட்டி", "காட்டுப்புத்தூர்", "தாத்தையங்கார்பேட்டை", "ஜீயபுரம்", "கல்லக்குடி", "பொன்மலை", "அந்தநல்லூர்", "தில்லை நகர்", "உறையூர்",
        "சத்திரம்", "பாலக்கரை", "கண்டோன்மென்ட்", "கே.கே.நகர்", "தென்னூர்", "புத்தூர்", "காஜாமலை", "மலைக்கோட்டை", "எடமலைப்பட்டி புதூர்")
NEG = ("அற்ற", "இல்லை", "இல்லாத", "மாட்டா", "கூடாது", "வேண்டாம்", "அல்ல", "இன்றி")      # a fix that adds "not" flips the meaning
TA = "\u0B80-\u0BFF\\w"


def _whole(w):
    return re.compile(f"(?<![{TA}]){re.escape(w)}(?![{TA}])")


def _repeats(t):
    """'X X' or 'X Y X' word runs (28 Oct RN-158: 'செல்லாமல் சென்றனர் செல்லாமல்')"""
    w = re.findall(r"\S+", t or "")
    return {" ".join(w[i:i + 3]) for i in range(len(w) - 2) if w[i] == w[i + 2] and len(w[i]) > 3} | \
        {" ".join(w[i:i + 2]) for i in range(len(w) - 1) if w[i] == w[i + 1] and len(w[i]) > 3}


def _article(row):
    try:
        import allnews
        a = allnews.article_any((row.get("source") or "").strip())
        return (a.get("title", "") + " " + a.get("text", "")) if isinstance(a, dict) else str(a[-1] if isinstance(a, (tuple, list)) else a or "")
    except Exception:
        return ""


VERB_ENDS = ("க்க", "க்கும்", "க்கப்", "ப்பட்டது", "ப்பட்ட", "த்து", "ந்து", "ட்டு", "ற்று")


def unsafe(w, ok, article=""):
    """why a proposed fix must NOT be applied ('' = safe). 28 Oct: the proofreader turned மீட்கப்பட்டனர் into மீட்டப்பட்டனர்,
    a place name into a wrong spelling (நாமக்கல் into நம்மக்கல்), 'வர வேண்டிய' into 'வரத் தேவையற்ற', deleted facts and doubled words - only small spelling fixes go in."""
    if not w or not ok or w == ok or len(w) < 2:
        return "empty"
    if re.search(r"[A-Za-z]", w + ok):
        return "English text / follow line"
    if _digits(w) != _digits(ok):
        return "number changed"
    if any(k in w for k in KEEP):
        return "page or place name"
    if any(n in ok and n not in w for n in NEG):
        return "meaning flipped"
    if abs(len(ok.split()) - len(w.split())) > 1 or difflib.SequenceMatcher(None, w, ok).ratio() < 0.6:
        return "rewrite, not a spelling fix"
    # 29 Oct (Trichy RN-1): 'நிர்வாகிக்க' (a verb, misspelt) became 'நிர்வாகம்' (a noun) - a fix must keep the word's grammatical ending
    lw, lo = w.split()[-1].strip(".,;:!?()\"'"), ok.split()[-1].strip(".,;:!?()\"'")
    if any(lw.endswith(e) and not lo.endswith(e) for e in VERB_ENDS):
        return "word form changed (verb into another word)"
    words = [x.strip(".,;:!?()\"'") for x in w.split()]
    if article and all(_whole(x).search(article) for x in words if x):
        return "the article itself writes it this way"
    import verify
    if verify.tamil_sequence_problems(ok):
        return "broken Tamil"
    return ""


def proofread(row, log=print, article=None):
    """corrects row in place; returns the number of corrections applied. Only whole-word, single-place, small spelling/sandhi
    fixes are applied; anything that could change a fact or the meaning is ignored."""
    import llm
    user = json.dumps(_texts(row), ensure_ascii=False)
    try:
        try:
            r, m = llm.ask_json(PROOF, user)
        except Exception:
            if not llm.claude_available():
                raise
            r, m = llm.ask_claude(PROOF, user, max_tokens=3000)
    except Exception as e:
        log("Tamil proofread unavailable (posting goes on):", str(e)[:150])
        return 0
    fixes = (r or {}).get("fixes") if isinstance(r, dict) else None
    if not fixes:
        log(f"Tamil proofread by {m}: no mistakes found")
        return 0
    if article is None:
        article = _article(row)
    spec = row.get("slides_spec") or ""
    done = 0
    for f in fixes[:25]:
        w, ok = str(f.get("wrong") or "").strip(), str(f.get("right") or "").strip()
        why = unsafe(w, ok, article)
        if why:
            log(f"proofread fix ignored ({why}):", w[:40], "->", ok[:40])
            continue
        hit = False
        for k in FIELDS:
            t = row.get(k) or ""
            if len(_whole(w).findall(t)) != 1:      # not there, or in several places: never replace blindly
                continue
            body, last = (t[:-len(LAST)], LAST) if k == "reel_script" and t.rstrip().endswith(LAST) else (t, "")
            new = _whole(w).sub(lambda _: ok, body, count=1) + last
            if _repeats(new) - _repeats(t):
                log("proofread fix ignored (would double words):", w[:40], "->", ok[:40])
                continue
            row[k], hit = new, True
        jw, jo = json.dumps(w, ensure_ascii=False)[1:-1], json.dumps(ok, ensure_ascii=False)[1:-1]
        if len(_whole(jw).findall(spec)) == 1:
            spec, hit = _whole(jw).sub(lambda _: jo, spec, count=1), True
        if hit:
            done += 1
            log(f"Tamil fix: «{w}» -> «{ok}» ({str(f.get('why', ''))[:60]})")
    try:
        json.loads(spec)
        row["slides_spec"] = spec
    except Exception:
        log("proofread fixes in the slide texts skipped (would break the format)")
    log(f"Tamil proofread by {m}: {done} of {len(fixes)} corrections applied")
    return done
