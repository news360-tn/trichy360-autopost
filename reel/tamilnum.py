"""Numbers -> Tamil words for the voice. The old voice code read every digit separately ("56" -> "ஐந்து ஆறு", "1,200" -> digit by digit)."""
import re

ONES = ["", "ஒன்று", "இரண்டு", "மூன்று", "நான்கு", "ஐந்து", "ஆறு", "ஏழு", "எட்டு", "ஒன்பது"]
TEENS = {10: "பத்து", 11: "பதினொன்று", 12: "பன்னிரண்டு", 13: "பதிமூன்று", 14: "பதினான்கு", 15: "பதினைந்து", 16: "பதினாறு",
         17: "பதினேழு", 18: "பதினெட்டு", 19: "பத்தொன்பது"}
TENS = {2: "இருபது", 3: "முப்பது", 4: "நாற்பது", 5: "ஐம்பது", 6: "அறுபது", 7: "எழுபது", 8: "எண்பது", 9: "தொண்ணூறு"}
TENS_JOIN = {2: "இருபத்து", 3: "முப்பத்து", 4: "நாற்பத்து", 5: "ஐம்பத்து", 6: "அறுபத்து", 7: "எழுபத்து", 8: "எண்பத்து", 9: "தொண்ணூற்று"}
HUND = {1: "நூறு", 2: "இருநூறு", 3: "முந்நூறு", 4: "நானூறு", 5: "ஐந்நூறு", 6: "அறுநூறு", 7: "எழுநூறு", 8: "எண்ணூறு", 9: "தொள்ளாயிரம்"}
HUND_JOIN = {1: "நூற்று", 2: "இருநூற்று", 3: "முந்நூற்று", 4: "நானூற்று", 5: "ஐந்நூற்று", 6: "அறுநூற்று", 7: "எழுநூற்று", 8: "எண்ணூற்று", 9: "தொள்ளாயிரத்து"}


def _below_100(n):
    if n < 10:
        return ONES[n]
    if n < 20:
        return TEENS[n]
    t, o = divmod(n, 10)
    return TENS[t] if o == 0 else TENS_JOIN[t] + " " + ONES[o]


def _below_1000(n):
    h, r = divmod(n, 100)
    if h == 0:
        return _below_100(r)
    if r == 0:
        return HUND[h]
    return HUND_JOIN[h] + " " + _below_100(r)


def _mult(w):
    """number used before ஆயிரம்/லட்சம்/கோடி: ஒன்று -> ஒரு, பதினொன்று -> பதினொரு"""
    return re.sub(r"பதினொன்று$", "பதினொரு", re.sub(r"ஒன்று$", "ஒரு", w))


def words(n):
    """0 .. 99,99,99,999"""
    if n == 0:
        return "பூஜ்ஜியம்"
    parts = []
    crore, n = divmod(n, 10_000_000)
    lakh, n = divmod(n, 100_000)
    thou, n = divmod(n, 1000)
    if crore:
        parts.append(_mult(_below_1000(crore)) + (" கோடியே" if (lakh or thou or n) else " கோடி"))
    if lakh:
        parts.append(_mult(_below_1000(lakh)) + (" லட்சத்து" if (thou or n) else " லட்சம்"))
    if thou:
        parts.append(("" if thou == 1 else _mult(_below_1000(thou)) + " ") + ("ஆயிரத்து" if n else "ஆயிரம்"))
    if n:
        parts.append(_below_1000(n))
    out = " ".join(p for p in parts if p).strip()
    for a, b in _AYIRAM:      # இரண்டு ஆயிரம் -> இரண்டாயிரம் (the form a news reader says)
        out = re.sub(a + r" ஆயிர", b + "ாயிர", out)
    return out


_AYIRAM = [("பதினொரு", "பதினோர"), ("பன்னிரண்டு", "பன்னிரண்ட"), ("இரண்டு", "இரண்ட"), ("மூன்று", "மூவ"), ("நான்கு", "நால"), ("ஐந்து", "ஐய"), ("ஏழு", "ஏழ"), ("எட்டு", "எட்ட"), ("ஒன்பது", "ஒன்பத"), ("பத்து", "பத்த"), ("ஆறு", "ஆற")]


ORD = re.compile(r"(\d[\d,]*)\s*-?\s*(ஆம்|ம்)(?![ெ-௔ா-ௌ])")
ORD_VADU = re.compile(r"(\d[\d,]*)\s*-?\s*(?:ஆவது|வது)")
NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")
MONTHS = ["ஜனவரி", "பிப்ரவரி", "மார்ச்", "ஏப்ரல்", "மே", "ஜூன்", "ஜூலை", "ஆகஸ்ட்", "செப்டம்பர்", "அக்டோபர்", "நவம்பர்", "டிசம்பர்"]
DAYPART = r"(காலை|மாலை|இரவு|மதியம்|அதிகாலை|பிற்பகல்|முற்பகல்|நண்பகல்|நள்ளிரவு)"


def half(n):
    """2.5 -> இரண்டரை, 10.5 -> பத்தரை (how a news reader says a half)"""
    w = words(n)
    return w[:-1] + "ரை" if w.endswith("ு") else w + " அரை"


def _time(h, mm):
    h, mm = int(h), int(mm)
    if mm == 0:
        return words(h)
    if mm == 30:
        return half(h)
    return words(h) + " " + words(mm)



# ---- owner 12 Nov (RN-534): numbers that belong to an ENGLISH name are said in English, as people say them -------------------
EN = {0: "ஜீரோ", 1: "ஒன்", 2: "டூ", 3: "த்ரீ", 4: "ஃபோர்", 5: "ஃபைவ்", 6: "சிக்ஸ்", 7: "செவன்", 8: "எய்ட்", 9: "நைன்", 10: "டென்",
      11: "லெவன்", 12: "ட்வெல்வ்", 13: "தர்டீன்", 14: "ஃபோர்டீன்", 15: "ஃபிஃப்டீன்", 16: "சிக்ஸ்டீன்", 17: "செவன்டீன்",
      18: "எய்டீன்", 19: "நைன்டீன்"}
EN_TENS = {2: "ட்வென்டி", 3: "தர்டி", 4: "ஃபோர்டி", 5: "ஃபிஃப்டி", 6: "சிக்ஸ்டி", 7: "செவன்டி", 8: "எய்டி", 9: "நைன்டி"}
LET = dict(zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ", ["ஏ", "பி", "சி", "டி", "இ", "எஃப்", "ஜி", "ஹெச்", "ஐ", "ஜே", "கே", "எல்", "எம்", "என்", "ஓ",
                                              "பி", "க்யூ", "ஆர்", "எஸ்", "டி", "யூ", "வி", "டபிள்யூ", "எக்ஸ்", "வை", "இசட்"]))
# words / letter names that are followed by an English number: பிளஸ் 2, குரூப் 4, டி20, ஆர்15, ஏ1 (accused), வி3, ஐ50
EN_WORD = r"பிளஸ்|குரூப்|லெவல்|மாடல்|டைப்|வெர்ஷன்"      # may have a space before the number: பிளஸ் 2, குரூப் 4
EN_LETTER = r"ஏ|பி|சி|டி|ஜி|ஐ|ஜே|கே|எல்|எம்|என்|ஆர்|எஸ்|வி|எக்ஸ்|எஃப்|யூ|வை|இசட்|க்யூ|டபிள்யூ|[A-Za-z]{1,3}"      # attached only: டி20, ஆர்15, ஏ1, T20
# ('எம்.எல்.ஏ. 3 பேர்' keeps 'மூன்று': a letter with a SPACE before the number is not an English name)
EN_SUFFIX = r"ஜி|டி|ஏ|பி|சி|எக்ஸ்|[A-Za-z]"      # 4ஜி, 5G, 3டி, குரூப் 2ஏ
TA = "\u0B80-\u0BFF"


def en_number(n):
    if n < 20:
        return EN[n]
    if n < 100:
        t, o = divmod(n, 10)
        return EN_TENS[t] + ("" if o == 0 else " " + EN[o])
    return " ".join(EN[int(c)] for c in str(n))      # model numbers: 150 -> ஒன் ஃபைவ் ஜீரோ


def _letters(w):
    return " ".join(LET.get(c.upper(), c) for c in w) if re.fullmatch(r"[A-Za-z]+", w) else w


def english_names(t):
    t = re.sub(r"(?<![\d.,])(\d{1,2})[-–]?(" + EN_SUFFIX + r")(?![" + TA + r"A-Za-z])",
               lambda m: en_number(int(m.group(1))) + " " + _letters(m.group(2)), t)
    t = re.sub(r"(?<![" + TA + r"A-Za-z\d])(?:(" + EN_WORD + r")\s*[-–]?\s*|(?!NH|SH)(" + EN_LETTER + r")[-–]?)(\d{1,3})(?![\d,.])",
               lambda m: _letters(m.group(1) or m.group(2)) + " " + en_number(int(m.group(3))), t)
    t = re.sub(r"\+\s*([12])(?![\d.,])", lambda m: "பிளஸ் " + en_number(int(m.group(1))), t)      # +2 / +1
    return t


# ---- owner 12 Nov: a case ending written after a number is part of the word: 40-க்கும் -> நாற்பதுக்கும், 2021-ல் -> ...ஒன்றில் ---------
ENDINGS = r"இலிருந்து|லிருந்து|க்குள்|க்கும்|க்குப்|க்கு|ஆகவும்|ஆகும்|ஆக|ஆல்|இல்|ல்|உம்|ஐ|ஓடு|உடன்"
NUM_END = re.compile(r"(?P<n>\d[\d,]*(?:\.\d+)?)(?:\s*[-–]\s*)?(?P<end>" + ENDINGS + r")(?![" + TA + r"])")
VSIGN = {"அ": "", "ஆ": "ா", "இ": "ி", "ஈ": "ீ", "உ": "ு", "ஊ": "ூ", "எ": "ெ", "ஏ": "ே", "ஐ": "ை", "ஒ": "ொ", "ஓ": "ோ"}


def join_ending(w, e):
    w = w.rstrip()
    if e in ("ல்", "லிருந்து"):
        e = "இ" + e                                  # 2021ல் = 2021இல்
    if e[0] in VSIGN:
        sign, rest = VSIGN[e[0]], e[1:]
        if w.endswith("ு"):
            return w[:-1] + sign + rest                 # ஒன்று+இல் -> ஒன்றில், ஆறு+ஆக -> ஆறாக
        if w.endswith("ம்"):
            if e[0] in "இஐஓ" or e == "ஆல்":
                return w[:-2] + "த்த" + sign + rest      # ஆயிரம்+இல் -> ஆயிரத்தில்
            if e == "உடன்":
                return w[:-2] + "த்துடன்"
            return w[:-1] + sign + rest                 # ஆயிரம்+ஆக -> ஆயிரமாக
        if w.endswith("்"):
            return w[:-1] + sign + rest                 # ரூபாய்+ஆக -> ரூபாயாக
        return w + "ய" + sign + rest                    # கோடி+இல் -> கோடியில்
    if w.endswith("ம்"):
        return w[:-2] + "த்து" + e                      # ஆயிரம்+க்கு -> ஆயிரத்துக்கு
    return w + e                                        # நாற்பது+க்கும் -> நாற்பதுக்கும், ரூபாய்+க்கு -> ரூபாய்க்கு


def speak_numbers(t):
    """replace every number in a Tamil sentence by its Tamil words (12ம் -> பன்னிரண்டாம், 11,600 -> பதினோராயிரத்து அறுநூறு style)"""
    t = re.sub(r"<[^>]+>", "", t)                       # stray html (<b>56</b>)
    t = re.sub(r"(?<![" + TA + r"])நெ\.\s*(?=\d)", "எண் ", t)      # நெ.4 வார்டு -> எண் நான்கு வார்டு
    t = english_names(t)      # owner 12 Nov (RN-534 'பிளஸ் 2'): a number that is part of an English name is said in English
    # dates 26.10.2026 / 26/10/2026 / 26-10-2026 -> அக்டோபர் 26ஆம் தேதி (2026)
    def _date(m):
        d, mo, y = int(m.group(1)), int(m.group(2)), m.group(3)
        if not (1 <= d <= 31 and 1 <= mo <= 12):
            return m.group()
        import datetime
        y = ("20" + y) if len(y) == 2 else y
        year = "" if y == str(datetime.date.today().year) else f" {y}"      # the current year is not read out
        return f"{MONTHS[mo - 1]} {d}ஆம் தேதி{year} "
    t = re.sub(r"(?<![\d.])(\d{1,2})[./-](\d{1,2})[./-](\d{4}|\d{2})(?![\d.])\s*(தேதி)?", lambda m: _date(m), t)
    # times: காலை 10.30 மணி / 4:30 மணிக்கு -> பத்தரை மணி / நான்கரை மணிக்கு; 10.45 மணி -> பத்து நாற்பத்து ஐந்து மணி
    t = re.sub(r"(?<![\d.])(\d{1,2})[.:](\d{2})(?=\s*(?:மணி|ம\.|hrs))", lambda m: _time(m.group(1), m.group(2)), t)
    t = re.sub(DAYPART + r"\s*(\d{1,2})[.:](\d{2})(?![\d])", lambda m: m.group(1) + " " + _time(m.group(2), m.group(3)), t)
    # money with paise: ரூ.5.70 -> 5 ரூபாய் 70 காசு (not "five point seven zero")
    def _paise(m):
        rs, ps = m.group(1), (m.group(2) + "0")[:2]
        return f"{rs} ரூபாய்" + ("" if int(ps) == 0 else f" {int(ps)} காசு")
    t = re.sub(r"(?:₹|ரூ\.?)\s*(\d[\d,]*)\.(\d{1,2})(?![\d])(?!\s*(?:லட்சம்|ஆயிரம்|கோடி))", _paise, t)
    # ranges: 10-12 வகுப்பு -> 10 முதல் 12; a year range 2025-26 is read as two numbers
    t = re.sub(r"(?<![\d.])(\d{4})\s*[-–]\s*(\d{2})(?![\d])", r"\1 \2", t)
    t = re.sub(r"(?<![\d.])(\d[\d,]*)\s*[-–]\s*(\d[\d,]*)(?![\d.])", r"\1 முதல் \2", t)
    t = re.sub(r"(?:₹|ரூ\.?)\s*(\d[\d,]*(?:\.\d+)?)\s*(லட்சம்|ஆயிரம்|கோடி)", r"\1 \2 ரூபாய்", t)      # ரூ.9 லட்சம் -> 9 லட்சம் ரூபாய்
    t = re.sub(r"(?:₹|ரூ\.?)\s*(\d[\d,]*(?:\.\d+)?)(?:(?:\s*[-–]\s*)?(" + ENDINGS + r")(?![" + TA + r"]))?",
               lambda m: m.group(1) + " " + (join_ending("ரூபாய்", m.group(2)) if m.group(2) else "ரூபாய்"), t)      # ரூ.11,600 -> 11,600 ரூபாய்
    t = t.replace("%", " சதவீதம்")

    def ordinal(m):
        n = int(m.group(1).replace(",", ""))
        w = words(n)
        return (w[:-1] + "ாம்" if w.endswith("ு") else w + "ஆம்") + " "

    def vadu(m):
        w = words(int(m.group(1).replace(",", "")))
        return (w[:-1] + "ாவது" if w.endswith("ு") else (w[:-2] + "மாவது" if w.endswith("ம்") else w + "ஆவது")) + " "

    def num(m):
        s = m.group().replace(",", "")
        if "." in s:
            a, b = s.split(".", 1)
            if b.rstrip("0") == "5":
                return half(int(a)) + " "
            if b.rstrip("0") == "":
                return words(int(a)) + " "
            return words(int(a)) + " புள்ளி " + " ".join(ONES[int(c)] or "பூஜ்ஜியம்" for c in b) + " "
        if len(s) > 9:
            return " ".join(ONES[int(c)] or "பூஜ்ஜியம்" for c in s) + " "
        return words(int(s)) + " "
    t = ORD_VADU.sub(vadu, t)
    t = ORD.sub(ordinal, t)
    t = NUM_END.sub(lambda m: join_ending(num(NUM.match(m.group("n"))), m.group("end")) + " ", t)      # 40-க்கும் -> நாற்பதுக்கும்
    t = NUM.sub(num, t)
    return re.sub(r"\s+", " ", t).strip()


if __name__ == "__main__":
    for s in ["56 தென்னை மரங்கள்", "ரூ.11,600 பறிமுதல்", "1,200 வாக்காளர்கள்", "12ம் தேதி 20ம் தேதி", "2,600 டன்", "10 ரூபாய் இயக்கம்", "<b>200</b> சவுக்கு", "24 ஏக்கர்", "45%", "3.5 கோடி", "105 பேர்", "2026"]:
        print(s, "->", speak_numbers(s))
