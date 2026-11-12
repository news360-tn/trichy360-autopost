"""Daily panchangam, calculated (not scraped) with the Swiss Ephemeris (Lahiri ayanamsa, Moshier model - no data files).

Gives the Tamil date (month + day), tithi / nakshatra / yogam with their end times, sunrise / sunset for the page's town,
chandrashtamam rasi and the fixed weekday Rahu kalam / Emagandam / Kuligai used by Tamil calendars.
Every value is calculated from the sky, so it never depends on a web page being up."""
from datetime import datetime, timedelta, timezone
import swisseph as swe

IST = timezone(timedelta(hours=5, minutes=30))
swe.set_sid_mode(swe.SIDM_LAHIRI)
FLAGS = swe.FLG_MOSEPH | swe.FLG_SIDEREAL

PLACES = {"rasipuram": (11.4553, 78.1847), "coimbatore": (11.0168, 76.9558), "namakkal": (11.2189, 78.1674)}

RASI = ["மேஷம்", "ரிஷபம்", "மிதுனம்", "கடகம்", "சிம்மம்", "கன்னி", "துலாம்", "விருச்சிகம்", "தனுசு", "மகரம்", "கும்பம்", "மீனம்"]
TAMIL_MONTH = ["சித்திரை", "வைகாசி", "ஆனி", "ஆடி", "ஆவணி", "புரட்டாசி", "ஐப்பசி", "கார்த்திகை", "மார்கழி", "தை", "மாசி", "பங்குனி"]
NAKSHATRA = ["அசுவினி", "பரணி", "கார்த்திகை", "ரோகிணி", "மிருகசீரிடம்", "திருவாதிரை", "புனர்பூசம்", "பூசம்", "ஆயில்யம்", "மகம்",
             "பூரம்", "உத்திரம்", "அஸ்தம்", "சித்திரை", "சுவாதி", "விசாகம்", "அனுஷம்", "கேட்டை", "மூலம்", "பூராடம்", "உத்திராடம்",
             "திருவோணம்", "அவிட்டம்", "சதயம்", "பூரட்டாதி", "உத்திரட்டாதி", "ரேவதி"]
TITHI = ["பிரதமை", "துவிதியை", "திருதியை", "சதுர்த்தி", "பஞ்சமி", "சஷ்டி", "சப்தமி", "அஷ்டமி", "நவமி", "தசமி", "ஏகாதசி",
         "துவாதசி", "திரயோதசி", "சதுர்த்தசி"]
YOGAM = ["விஷ்கம்பம்", "பிரீதி", "ஆயுஷ்மான்", "சௌபாக்கியம்", "சோபனம்", "அதிகண்டம்", "சுகர்மம்", "திருதி", "சூலம்", "கண்டம்",
         "விருத்தி", "துருவம்", "வியாகாதம்", "ஹர்ஷணம்", "வஜ்ரம்", "சித்தி", "வியதீபாதம்", "வரியான்", "பரிகம்", "சிவம்", "சித்தம்",
         "சாத்தியம்", "சுபம்", "சுப்பிரம்", "பிராம்யம்", "ஐந்திரம்", "வைதிருதி"]
WEEKDAY = ["திங்கள்", "செவ்வாய்", "புதன்", "வியாழன்", "வெள்ளி", "சனி", "ஞாயிறு"]      # datetime.weekday() order
# owner 1 Nov: the full day name as written ('ஞாயிறுக்கிழமை' was printed - wrong; it is ஞாயிற்றுக்கிழமை)
WEEKDAY_FULL = ["திங்கட்கிழமை", "செவ்வாய்க்கிழமை", "புதன்கிழமை", "வியாழக்கிழமை", "வெள்ளிக்கிழமை", "சனிக்கிழமை", "ஞாயிற்றுக்கிழமை"]
MONTH_EN_TA = ["ஜனவரி", "பிப்ரவரி", "மார்ச்", "ஏப்ரல்", "மே", "ஜூன்", "ஜூலை", "ஆகஸ்ட்", "செப்டம்பர்", "அக்டோபர்", "நவம்பர்", "டிசம்பர்"]

# fixed weekday periods printed in Tamil calendars (Monday first)
RAHU = ["7:30 – 9:00", "3:00 – 4:30", "12:00 – 1:30", "1:30 – 3:00", "10:30 – 12:00", "9:00 – 10:30", "4:30 – 6:00"]
EMA = ["10:30 – 12:00", "9:00 – 10:30", "7:30 – 9:00", "6:00 – 7:30", "3:00 – 4:30", "1:30 – 3:00", "12:00 – 1:30"]
# நல்ல நேரம் (morning, evening) and சூலம் (direction, பரிகாரம்) by weekday - as printed in Maalaimalar's daily panchangam
# (checked against its articles 26 Oct - 1 Nov 2026); the day's article, when found, overrides these
NALLA = [("6:00 – 7:00", "3:00 – 4:00"), ("8:00 – 9:00", "5:00 – 6:00"), ("6:00 – 7:00", "4:00 – 5:00"), ("9:00 – 10:00", "4:00 – 5:00"),
         ("6:00 – 7:00", "5:00 – 6:00"), ("7:00 – 8:00", "5:00 – 6:00"), ("7:00 – 8:00", "3:00 – 4:00")]
SULAM = [("கிழக்கு", "தயிர்"), ("வடக்கு", "பால்"), ("வடக்கு", "பால்"), ("தெற்கு", "தைலம்"), ("மேற்கு", "வெல்லம்"), ("கிழக்கு", "தயிர்"),
         ("மேற்கு", "வெல்லம்")]
KULIGAI = ["1:30 – 3:00", "12:00 – 1:30", "10:30 – 12:00", "9:00 – 10:30", "7:30 – 9:00", "6:00 – 7:30", "3:00 – 4:30"]


def jd(dt):
    u = dt.astimezone(timezone.utc)
    return swe.julday(u.year, u.month, u.day, u.hour + u.minute / 60 + u.second / 3600)


def from_jd(j):
    y, m, d, h = swe.revjul(j)
    return (datetime(y, m, d, tzinfo=timezone.utc) + timedelta(hours=h)).astimezone(IST)


def sun(j):
    return swe.calc_ut(j, swe.SUN, FLAGS)[0][0]


def moon(j):
    return swe.calc_ut(j, swe.MOON, FLAGS)[0][0]


def tithi_angle(j):
    return (moon(j) - sun(j)) % 360


def _end(j, fn, step):
    """first time after j when fn(t) // step changes (bisection, ~1 minute)"""
    start = int(fn(j) // step)
    lo, hi = j, j
    while int(fn(hi) // step) == start and hi - j < 2.5:
        lo, hi = hi, hi + 1 / 24
    for _ in range(30):
        mid = (lo + hi) / 2
        if int(fn(mid) // step) == start:
            lo = mid
        else:
            hi = mid
    return hi


def sunrise_sunset(day, lat, lon):
    j0 = jd(datetime(day.year, day.month, day.day, 0, 0, tzinfo=IST))
    geo = (lon, lat, 0)
    rise = swe.rise_trans(j0, swe.SUN, swe.CALC_RISE | swe.BIT_DISC_CENTER, geo, 0, 0, swe.FLG_MOSEPH)[1][0]
    sset = swe.rise_trans(j0, swe.SUN, swe.CALC_SET | swe.BIT_DISC_CENTER, geo, 0, 0, swe.FLG_MOSEPH)[1][0]
    return rise, sset


def tamil_date(day, lat, lon):
    """Tamil solar month and day: the month starts on the day the sun enters the sign if that happens before sunset, else the next day"""
    rise, sset = sunrise_sunset(day, lat, lon)
    sign = int(sun(sset) // 30)
    d = day
    for back in range(0, 33):
        cand = day - timedelta(days=back)
        _, cs = sunrise_sunset(cand, lat, lon)
        _, ps = sunrise_sunset(cand - timedelta(days=1), lat, lon)
        if int(sun(cs) // 30) == sign and int(sun(ps) // 30) != sign:
            d = cand
            break
    return TAMIL_MONTH[sign], (day - d).days + 1, sign


def hm(t):
    h = t.hour % 12 or 12
    part = "காலை" if t.hour < 12 else ("மதியம்" if t.hour < 16 else ("மாலை" if t.hour < 19 else "இரவு"))
    return f"{part} {h}:{t.minute:02d}"


def until(end_dt, day):
    """'மாலை 4:57 வரை' for today, 'நாளை காலை 6:10 வரை' when it runs past midnight"""
    pre = "" if end_dt.date() == day else ("நாளை " if end_dt.date() == day + timedelta(days=1) else "")
    return f"{pre}{hm(end_dt)} வரை"


def tithi_name(i):
    paksha = "வளர்பிறை" if i < 15 else "தேய்பிறை"
    k = i % 15
    if k == 14:
        return "பௌர்ணமி" if i < 15 else "அமாவாசை", paksha
    return TITHI[k], paksha


def compute(day, page="rasipuram"):
    lat, lon = PLACES.get(page, PLACES["rasipuram"])
    rise, sset = sunrise_sunset(day, lat, lon)
    t_i = int(tithi_angle(rise) // 12)
    t_end = from_jd(_end(rise, tithi_angle, 12))
    n_i = int(moon(rise) // (360 / 27))
    n_end = from_jd(_end(rise, moon, 360 / 27))
    y_fn = lambda j: (sun(j) + moon(j)) % 360
    y_i = int(y_fn(rise) // (360 / 27))
    y_end = from_jd(_end(rise, y_fn, 360 / 27))
    m_sign = int(moon(rise) // 30)
    m_end = from_jd(_end(rise, moon, 30))
    month, mday, sun_sign = tamil_date(day, lat, lon)
    wd = day.weekday()
    t_name, paksha = tithi_name(t_i)
    nt_name, _ = tithi_name((t_i + 1) % 30)
    chandra = RASI[(m_sign - 7) % 12]
    chandra_next = RASI[(m_sign + 1 - 7) % 12]
    return {
        "date": day.isoformat(), "weekday": WEEKDAY[wd], "weekday_idx": wd, "weekday_full": WEEKDAY_FULL[wd],
        "date_ta": f"{day.day} {MONTH_EN_TA[day.month - 1]} {day.year}",
        "tamil_month": month, "tamil_day": mday, "sun_sign": sun_sign,
        "tithi": t_name, "tithi_idx": t_i, "paksha": paksha, "tithi_end": until(t_end, day), "tithi_next": nt_name,
        "nakshatra": NAKSHATRA[n_i], "nakshatra_idx": n_i, "nakshatra_end": until(n_end, day), "nakshatra_next": NAKSHATRA[(n_i + 1) % 27],
        "yogam": YOGAM[y_i], "yogam_end": until(y_end, day),
        "moon_sign": m_sign, "moon_rasi": RASI[m_sign],
        "chandrashtamam": chandra, "chandrashtamam_end": until(m_end, day) if m_end.date() == day else "",
        "chandrashtamam_next": chandra_next if m_end.date() == day else "",
        "sunrise": hm(from_jd(rise)), "sunset": hm(from_jd(sset)),
        "rahu": RAHU[wd], "emagandam": EMA[wd], "kuligai": KULIGAI[wd],
        "nalla_morning": NALLA[wd][0], "nalla_evening": NALLA[wd][1], "sulam": SULAM[wd][0], "sulam_parigaram": SULAM[wd][1], "subha_muhurtham": False,
    }


if __name__ == "__main__":
    import json, sys
    d = datetime.strptime(sys.argv[1], "%Y-%m-%d").date() if len(sys.argv) > 1 else datetime.now(IST).date()
    print(json.dumps(compute(d), ensure_ascii=False, indent=1))
