"""Full place names and spoken forms. News sites shorten names (மே.பாளையம், பெ.நா.பாளையம்) and use abbreviations (ஆர்.டி.ஓ.): a voice engine reads
those badly and many viewers do not recognise them. Everything we publish uses the full name; the reel voice also gets spoken role words."""
import re

# (pattern, full name). The ending (-ில், -இல், -க்கு ...) after the matched name is kept.
PLACES = [
    (r"மே\s?\.\s?பாளைய", "மேட்டுப்பாளைய"),
    (r"பெ\s?\.\s?நா\s?\.\s?பாளைய", "பெரியநாயக்கன்பாளைய"),
    (r"கோயமுத்தூ", "கோயம்புத்தூ"),
    (r"கோயம்புத்துா", "கோயம்புத்தூ"),
]
# only for the spoken reel script (the screen text may keep the short, well-known forms)
D = r"\s?\.\s?"      # the dot between the letters of a Tamil abbreviation (எஸ்.ஐ. / எஸ் . ஐ)
ROLES = [
    # longest first: ஏ.டி.எஸ்.பி. must not become ஏ.+டி.எஸ்.பி.
    (r"ஏ" + D + r"டி" + D + r"எஸ்" + D + r"பி\s?\.?,?|(?<![A-Za-z])ADSP(?![A-Za-z])", "கூடுதல் காவல் கண்காணிப்பாளர்"),
    (r"எஸ்" + D + r"எஸ்" + D + r"ஐ\s?\.?,?|(?<![A-Za-z])SSI(?![A-Za-z])", "சிறப்பு உதவி ஆய்வாளர்"),
    (r"(?<![அ-ஹ.])எஸ்" + D + r"ஐ\s?\.?,?|(?<![A-Za-z])SI(?![A-Za-z])", "காவல் உதவி ஆய்வாளர்"),
    (r"(?<![A-Za-z])DSP(?![A-Za-z])", "காவல் துணை கண்காணிப்பாளர்"),
    (r"(?<![A-Za-z])SP(?![A-Za-z])", "காவல் கண்காணிப்பாளர்"),
    (r"எம்" + D + r"எல்" + D + r"ஏ\s?\.?,?|(?<![A-Za-z])MLA(?![A-Za-z])", "சட்டமன்ற உறுப்பினர்"),
    (r"(?<![அ-ஹ.])எம்" + D + r"பி\s?\.?,?(?!\s?[அ-ஹ]\s?\.)|(?<![A-Za-z])MP(?![A-Za-z])", "நாடாளுமன்ற உறுப்பினர்"),
    (r"வி" + D + r"ஏ" + D + r"ஓ\s?\.?,?|(?<![A-Za-z])VAO(?![A-Za-z])", "கிராம நிர்வாக அலுவலர்"),
    (r"(?<![அ-ஹ.])ஆர்" + D + r"ஐ\s?\.?,?(?!\s?[அ-ஹ]\s?\.)", "வருவாய் ஆய்வாளர்"),
    (r"(?<![A-Za-z])RDO(?![A-Za-z])", "வருவாய் கோட்டாட்சியர்"),
    (r"(?<![A-Za-z])BDO(?![A-Za-z])", "வட்டார வளர்ச்சி அலுவலர்"),
    (r"(?<![A-Za-z])DRO(?![A-Za-z])", "மாவட்ட வருவாய் அலுவலர்"),
    (r"டி" + D + r"என்" + D + r"இ" + D + r"பி\s?\.?,?|(?<![A-Za-z])TNEB(?![A-Za-z])", "மின்சார வாரியம்"),
    (r"(?<![A-Za-z])TNSTC(?![A-Za-z])", "அரசுப் போக்குவரத்துக் கழகம்"),
    (r"மி" + D + r"மீ\s?\.?,?", "மில்லிமீட்டர்"),
    (r"செ" + D + r"மீ\s?\.?,?", "சென்டிமீட்டர்"),
    (r"கி" + D + r"கி\s?\.?,?", "கிலோகிராம்"),
    (r"ச" + D + r"அடி", "சதுர அடி"),
    (r"(?<![A-Za-z])No\.\s?", "எண் "),
    (r"(?<![A-Za-z])NEET(?![A-Za-z])", "நீட்"),
    (r"(?<![A-Za-z])TASMAC(?![A-Za-z])", "டாஸ்மாக்"),
    (r"(?<![A-Za-z])COVID(?![A-Za-z])", "கோவிட்"),
    (r"ஆர்\s?\.\s?டி\s?\.\s?ஓ\s?\.?,?", "வருவாய் கோட்டாட்சியர்"),
    (r"டி\s?\.\s?ஆர்\s?\.\s?ஓ\s?\.?,?", "மாவட்ட வருவாய் அலுவலர்"),
    (r"பி\s?\.\s?டி\s?\.\s?ஓ\s?\.?,?", "வட்டார வளர்ச்சி அலுவலர்"),
    (r"டி\s?\.\s?எஸ்\s?\.\s?பி\s?\.?,?", "காவல் துணை கண்காணிப்பாளர்"),
    (r"எஸ்\s?\.\s?பி\s?\.?,?", "காவல் கண்காணிப்பாளர்"),
    (r"ஜி\s?\.\s?ஹெச்\s?\.?,?|ஜி\s?\.\s?எச்\s?\.?,?", "அரசு மருத்துவமனை"),
    (r"கி\s?\.\s?மீ\s?\.?,?", "கிலோமீட்டர்"),
    (r"அக்\s?\.", "அக்டோபர்"),
]


def full_places(text):
    for pat, full in PLACES:
        text = re.sub(pat, full, text or "")
    return ages(text)


MONTH_WORDS = ("ஜனவரி", "பிப்ரவரி", "மார்ச்", "ஏப்ரல்", "மே", "ஜூன்", "ஜூலை", "ஆகஸ்ட்", "செப்டம்பர்", "அக்டோபர்", "நவம்பர்", "டிசம்பர்")


def ages(text):
    """owner 28 Oct (RN-156 'செல்வம், 47,' / 'செல்வம் (47)'): newspaper shorthand ages are said with the word வயது -
    'செல்வம் (47 வயது)' - so a viewer hears it is an age, not a bare number"""
    W = r"(?<![\u0B80-\u0BFF])([\u0B80-\u0BFF]+)"
    keep = lambda f: lambda m: m.group(0) if m.group(1) in MONTH_WORDS else f(m)
    text = re.sub(W + r",\s?(\d{1,2}),(?!\s*\d)", keep(lambda m: f"{m.group(1)} ({m.group(2)} வயது),"), text or "")
    return re.sub(W + r"\s?\((\d{1,2})\)", keep(lambda m: f"{m.group(1)} ({m.group(2)} வயது)"), text)


# English letters as a Tamil news reader says them (the voice model drops Latin letters completely: "TNPSC" was silent)
LATIN = {"A": "ஏ", "B": "பி", "C": "சி", "D": "டி", "E": "இ", "F": "எஃப்", "G": "ஜி", "H": "ஹெச்", "I": "ஐ", "J": "ஜே", "K": "கே", "L": "எல்", "M": "எம்",
         "N": "என்", "O": "ஓ", "P": "பி", "Q": "க்யூ", "R": "ஆர்", "S": "எஸ்", "T": "டி", "U": "யு", "V": "வி", "W": "டபிள்யூ", "X": "எக்ஸ்", "Y": "ஒய்", "Z": "இசட்"}


def spoken(text):
    text = full_places(text)
    for pat, full in ROLES:
        text = re.sub(pat, full, text)
    # any other abbreviation is read letter by letter: TNPSC -> டி என் பி எஸ் சி, ஐ.பி.எஸ். -> ஐ பி எஸ், தி.மு.க. -> தி மு க
    text = re.sub(r"(?<![A-Za-z])[A-Z]{2,7}(?![A-Za-z])", lambda m: " ".join(LATIN[c] for c in m.group()), text)
    L = r"[அ-ஹ](?:[\u0bbe-\u0bcc]|[அ-ஹ]\u0bcd|\u0bcd)?"      # one spoken letter: ஐ, பி, எஸ், எம், தி, க
    text = re.sub(r"(?<![அ-ஹ\u0bbe-\u0bcd])((?:" + L + r"\s?\.\s?){2,}" + L + r")\.?",
                  lambda m: " ".join(x.strip() for x in m.group(1).split(".") if x.strip()), text)
    for a, b in (("ர்வும்", "ரும்"), ("ர்வின்", "ரின்"), ("ர்வுக்கு", "ருக்கு")):      # the ending that followed the abbreviation (ஆர்.டி.ஓ.,வும்)
        text = text.replace(a, b)
    return text


# ---- owner 2 Nov: SCREEN text shows the English abbreviations people know (MLA, LPG, DSP ...); the VOICE is not changed.
# Tamil spells D and T the same (டி) and B and P the same (பி): a word is shown in English ONLY when one of its readings is a known
# abbreviation below - an unknown one stays in Tamil (a wrong English abbreviation is worse than the Tamil spelling).
KNOWN_ABBR = {
    "MLA", "MP", "DSP", "ADSP", "SP", "ASP", "SI", "SSI", "DIG", "IG", "DGP", "VAO", "RDO", "BDO", "DRO", "RTO", "IAS", "IPS", "CBI", "CBCID",
    "NIA", "TNPSC", "TNEB", "EB", "TNSTC", "LPG", "CNG", "GST", "CCTV", "ATM", "IT", "AC", "TV", "AI", "GH", "ICU", "MBBS", "MD",
    "PG", "UG", "SSLC", "ITI", "IIT", "NSS", "NCC", "LIC", "SBI", "UPI", "OTP", "KYC", "EMI", "SIM", "PDF", "USB", "PWD", "NH", "CEO",
    "DMK", "ADMK", "BJP", "PMK", "AIADMK", "TVK", "SIPCOT", "SIDCO", "TIDEL", "COVID", "HIV", "DNA", "CM", "PM", "RTI", "FIR", "ESI", "PF",
}
_LETTER_OPTS = {}
for _k, _v in LATIN.items():
    _LETTER_OPTS.setdefault(_v, []).append(_k)
_LETTER_OPTS.update({"எச்": ["H"], "எப்": ["F"], "ஜெட்": ["Z"]})
LETTER = {k: v[0] for k, v in _LETTER_OPTS.items()}      # a Tamil letter name (used to find runs of spoken letters)
_LET = "|".join(sorted(map(re.escape, _LETTER_OPTS), key=len, reverse=True))
DISPLAY_ROLES = [      # the voice says the role in Tamil (spoken() above); the screen shows the abbreviation - longest first
    ("கூடுதல் காவல் கண்காணிப்பாளர்", "ADSP"), ("காவல் துணை கண்காணிப்பாளர்", "DSP"), ("காவல் கண்காணிப்பாளர்", "SP"),
    ("சிறப்பு உதவி ஆய்வாளர்", "SSI"), ("காவல் உதவி ஆய்வாளர்", "SI"), ("சட்டமன்ற உறுப்பினர்", "MLA"), ("நாடாளுமன்ற உறுப்பினர்", "MP"),
    ("கிராம நிர்வாக அலுவலர்", "VAO"), ("வருவாய் கோட்டாட்சியர்", "RDO"), ("வட்டார வளர்ச்சி அலுவலர்", "BDO"), ("மாவட்ட வருவாய் அலுவலர்", "DRO"),
]


# owner 2 Nov: an abbreviation that is also a Tamil word is shown in English only when the next / previous word shows the meaning
# ('ஏசி பஸ்' = AC bus; 'ஏசி பேசினார்' = scolded - stays Tamil)
CONTEXT = {"AC": ("பஸ்", "பேருந்து", "அறை", "வசதி", "இயந்திர", "மெஷின்", "ரயில்", "பெட்டி", "மெக்கானிக்", "கடை", "பழுது", "ஓட்டல்", "தியேட்டர்", "திரையரங்க", "காற்று")}


def _context_ok(en, prev, nxt):
    words = CONTEXT.get(en)
    return not words or any(w and any(w.startswith(c) for c in words) for w in (prev, nxt))


def _readings(parts):
    out = [""]
    for p in parts:
        out = [o + x for o in out for x in _LETTER_OPTS[p]]
        if len(out) > 64:
            return []
    return out


def _known(parts):
    """the known abbreviation these Tamil letter names spell ('டி','எஸ்','பி' -> 'DSP'), else ''"""
    if len(parts) < 2 or not all(p in _LETTER_OPTS for p in parts):
        return ""
    return next((r for r in _readings(parts) if r in KNOWN_ABBR), "")


def _split_letters(tok):
    out, i = [], 0
    while i < len(tok):
        m = re.match(_LET, tok[i:])
        if not m:
            return []
        out.append(m.group(0))
        i += len(m.group(0))
    return out


def _abbr_token(tok, prev="", nxt=""):
    """one screen word: 'எல்பிஜி' / 'டி.எஸ்.பி.' / 'எம்எல்ஏ-வின்' -> 'LPG' / 'DSP' / 'MLA-வின்' (else unchanged)"""
    m = re.match(r"^([\u0B80-\u0BFF.]+?)(-[\u0B80-\u0BFF]+)?([,.!?:;]*)$", tok)
    if not m:
        return tok
    core, suf, punct = m.group(1), m.group(2) or "", m.group(3)
    dotted = "." in core or punct.startswith(".")
    parts = [p for p in core.split(".") if p] if "." in core else _split_letters(core)
    en = _known(parts)
    if en and not _context_ok(en, prev, nxt):
        return tok
    if en and dotted and punct.startswith(".") and len(parts) >= 2 and "." in core:
        punct = punct[1:]      # 'டி.எஸ்.பி.' -> 'DSP' (the last dot belongs to the abbreviation)
    return (en + suf + punct) if en else tok


def latin_abbr(text):
    """screen text (headline, fact cards, summary): Tamil-spelled English abbreviations -> English letters"""
    if not text:
        return text
    for ta, en in DISPLAY_ROLES:
        text = re.sub(re.escape(ta) + r"(?=$|[\s,.!?:;])", en, text)
    toks = text.split(" ")
    out, run = [], []
    def flush():
        en = _known(run) if len(run) >= 2 else ""
        out.extend([en] if en else run)
        run.clear()
    for k, t in enumerate(toks):
        if t in _LETTER_OPTS:
            run.append(t)
            continue
        flush()
        out.append(_abbr_token(t, toks[k - 1] if k else "", toks[k + 1] if k + 1 < len(toks) else ""))
    flush()
    return " ".join(out)


def latin_abbr_words(words):
    """timed subtitle words [(word, start, end)]: spoken letters ('எல்', 'பி', 'ஜி') shown as one word 'LPG' over the same time,
    the voice's role words shown as the abbreviation, other words through _abbr_token"""
    out, i = [], 0
    strip = lambda w: w.rstrip(",.!?:;")
    while i < len(words):
        hit = None
        for ta, en in DISPLAY_ROLES:
            n = len(ta.split())
            seg = [w[0] for w in words[i:i + n]]
            if len(seg) == n and strip(" ".join(seg)) == ta:
                hit = (en + seg[-1][len(strip(seg[-1])):], n)
                break
        if hit:
            out.append((hit[0], words[i][1], words[i + hit[1] - 1][2]))
            i += hit[1]
            continue
        j = i
        while j < len(words) and strip(words[j][0]) in _LETTER_OPTS:
            j += 1
            if words[j - 1][0] != strip(words[j - 1][0]):
                break
        en = _known([strip(w[0]) for w in words[i:j]]) if j - i >= 2 else ""
        if en:
            last = words[j - 1][0]
            out.append((en + last[len(strip(last)):], words[i][1], words[j - 1][2]))
            i = j
            continue
        out.append((_abbr_token(words[i][0], words[i - 1][0] if i else "", words[i + 1][0] if i + 1 < len(words) else ""), words[i][1], words[i][2]))
        i += 1
    return out
