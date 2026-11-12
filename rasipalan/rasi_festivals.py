"""Which festival / special day is today, and which carousel theme it gets.

Three kinds of days:
  OFFICIAL  - dates from the Tamil Nadu Government holiday lists (2026 remaining days, 2027) and fixed calendar days: trusted as they are.
  VERIFY    - moon-based days (Islamic festivals, and temple festivals the government list does not carry): calculated / expected date
              +-2 days, and the theme is used ONLY when the day's Tamil panchangam article names the festival. Never a guess.
  monthly special days (pournami, amavasai, ekadasi, sashti, pradosham, kiruthigai...) come from the calculated panchangam and are only
  mentioned in one line on the cover (no theme).
Update OFFICIAL when the next year's Government holiday list comes out (the tests warn 30 days before the table runs out)."""
from datetime import date

OFFICIAL = {
    # 2026 (remaining)
    date(2026, 11, 8): ("தீபாவளி", "diwali"),
    date(2026, 12, 25): ("கிறிஸ்துமஸ்", "christmas"),
    # 2027 - Tamil Nadu Government holiday list
    date(2027, 1, 1): ("ஆங்கிலப் புத்தாண்டு", "newyear"),
    date(2027, 1, 15): ("தைப்பொங்கல்", "pongal"),
    date(2027, 1, 16): ("மாட்டுப் பொங்கல் - திருவள்ளுவர் தினம்", "pongal"),
    date(2027, 1, 17): ("காணும் பொங்கல் - உழவர் திருநாள்", "pongal"),
    date(2027, 1, 22): ("தைப்பூசம்", "murugan"),
    date(2027, 1, 26): ("குடியரசு தினம்", "national"),
    date(2027, 3, 26): ("புனித வெள்ளி", "christian_solemn"),
    date(2027, 4, 14): ("தமிழ்ப் புத்தாண்டு", "tamilnewyear"),
    date(2027, 8, 15): ("சுதந்திர தினம்", "national"),
    date(2027, 8, 25): ("கிருஷ்ண ஜெயந்தி", "krishna"),
    date(2027, 9, 4): ("விநாயகர் சதுர்த்தி", "vinayagar"),
    date(2027, 10, 2): ("காந்தி ஜெயந்தி", "national"),
    date(2027, 10, 8): ("ஆயுத பூஜை - சரஸ்வதி பூஜை", "navaratri"),
    date(2027, 10, 9): ("விஜயதசமி", "navaratri"),
    date(2027, 10, 28): ("தீபாவளி", "diwali"),
    date(2027, 12, 25): ("கிறிஸ்துமஸ்", "christmas"),
}
OFFICIAL_UNTIL = date(2027, 12, 31)

# (name, theme, expected date, words one of which must be in the day's panchangam article)
VERIFY = [
    ("கந்த சஷ்டி - சூரசம்ஹாரம்", "murugan", date(2026, 11, 15), ("சூரசம்ஹார", "சூர சம்ஹார")),
    ("திருக்கார்த்திகை தீபம்", "karthigai", date(2026, 11, 24), ("கார்த்திகை தீப", "திருக்கார்த்திகை", "மகா தீப", "மகாதீப")),
    ("வைகுண்ட ஏகாதசி", "perumal", date(2026, 12, 20), ("வைகுண்ட ஏகாதசி", "சொர்க்கவாசல்", "சொர்க்க வாசல்", "பரமபத வாசல்")),
    ("போகிப் பண்டிகை", "pongal", date(2027, 1, 14), ("போகி",)),
    ("மகா சிவராத்திரி", "shiva", date(2027, 3, 6), ("சிவராத்திரி",)),
    ("ரம்ஜான் பண்டிகை", "islamic", date(2027, 3, 10), ("ரம்ஜான்", "ரமலான்", "ஈகைத் திருநாள்", "ஈதுல் பித்ர்")),
    ("பங்குனி உத்திரம்", "murugan", date(2027, 3, 22), ("பங்குனி உத்திர",)),
    ("ஈஸ்டர் பண்டிகை", "christmas", date(2027, 3, 28), ("ஈஸ்டர்",)),
    ("ஸ்ரீ ராம நவமி", "perumal", date(2027, 4, 15), ("ராம நவமி", "ராமநவமி")),
    ("பக்ரீத் பண்டிகை", "islamic", date(2027, 5, 17), ("பக்ரீத்", "தியாகத் திருநாள்", "ஈதுல் அழ்ஹா")),
    ("வைகாசி விசாகம்", "murugan", date(2027, 5, 20), ("வைகாசி விசாக",)),
    ("மொகரம்", "islamic_solemn", date(2027, 6, 15), ("மொகரம்", "முஹர்ரம்")),
    ("ஆடிப்பெருக்கு", "amman", date(2027, 8, 3), ("ஆடிப்பெருக்கு", "ஆடி பெருக்கு", "ஆடி 18")),
    ("மிலாடி நபி", "islamic", date(2027, 8, 15), ("மிலாடி நபி", "மீலாது நபி", "மிலாது நபி")),
    ("கந்த சஷ்டி - சூரசம்ஹாரம்", "murugan", date(2027, 11, 4), ("சூரசம்ஹார", "சூர சம்ஹார")),
    ("திருக்கார்த்திகை தீபம்", "karthigai", date(2027, 12, 11), ("கார்த்திகை தீப", "திருக்கார்த்திகை", "மகா தீப", "மகாதீப")),
]
WINDOW = 2


def today(day, p, article_text=""):
    """-> (main festival or None, special-day notes, log line). main = {name, theme, how}"""
    main, why = None, ""
    if day in OFFICIAL:
        n, th = OFFICIAL[day]
        main, why = {"name": n, "theme": th, "how": "official list"}, f"festival {n}: Tamil Nadu Government list"
    else:
        for n, th, exp, words in VERIFY:
            if abs((day - exp).days) <= WINDOW:
                hit = [w for w in words if w in (article_text or "")]
                if hit:
                    main, why = {"name": n, "theme": th, "how": f"panchangam article says '{hit[0]}'"}, f"festival {n}: confirmed ({hit[0]})"
                    break
                why = f"{n} expected near {exp} but today's panchangam article does not name it - normal design"
    t, star = p["tithi_idx"], p["nakshatra_idx"]
    notes = []
    if t == 14:
        notes.append("பௌர்ணமி")
    if t == 29:
        notes.append("அமாவாசை")
    if t in (10, 25):
        notes.append("ஏகாதசி")
    if t == 5:
        notes.append("சஷ்டி விரதம்")
    if t == 18:
        notes.append("சங்கடஹர சதுர்த்தி")
    if t in (12, 27):
        notes.append("பிரதோஷம்")
    if star == 2:
        notes.append("கிருத்திகை")
    if main:
        notes = [x for x in notes if x not in main["name"]]
    return main, notes, why


def table_runs_out_soon(day, days=30):
    return (OFFICIAL_UNTIL - day).days < days
