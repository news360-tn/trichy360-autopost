"""Daily rasipalan carousel (owner 31 Oct): panchangam values, festival days, writer checks, caption rules."""
import sys, unittest
from datetime import date
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "rasipalan"))
import importlib.util
HAVE_SWE = importlib.util.find_spec("swisseph") is not None


@unittest.skipUnless(HAVE_SWE, "pyswisseph is installed by tests.yml")
class Panchangam(unittest.TestCase):
    def test_31_october_2026_matches_published_panchangam(self):
        import rasi_panchang as P
        p = P.compute(date(2026, 10, 31))
        self.assertEqual((p["tamil_month"], p["tamil_day"], p["weekday"]), ("ஐப்பசி", 14, "சனி"))
        self.assertEqual((p["tithi"], p["paksha"], p["nakshatra"]), ("சஷ்டி", "தேய்பிறை", "திருவாதிரை"))
        self.assertIn("4:5", p["tithi_end"])          # published: 4:57 PM
        self.assertIn("7:1", p["nakshatra_end"])      # published: 7:11 AM
        self.assertEqual(p["chandrashtamam"], "விருச்சிகம்")
        self.assertEqual(p["rahu"], "9:00 – 10:30")

    def test_tamil_month_starts(self):
        import rasi_panchang as P
        self.assertEqual((P.compute(date(2027, 1, 15))["tamil_month"], P.compute(date(2027, 1, 15))["tamil_day"]), ("தை", 1))
        self.assertEqual(P.compute(date(2027, 4, 14))["tamil_month"], "சித்திரை")


class Festivals(unittest.TestCase):
    P = {"tithi_idx": 20, "nakshatra_idx": 5}

    def test_official_day_gets_its_theme(self):
        import rasi_festivals as festivals
        f, _, _ = festivals.today(date(2026, 11, 8), self.P)
        self.assertEqual((f["name"], f["theme"]), ("தீபாவளி", "diwali"))

    def test_moon_festival_needs_the_article(self):
        import rasi_festivals as festivals
        f, _, why = festivals.today(date(2027, 3, 10), self.P, "இன்றைய பஞ்சாங்கம் ...")
        self.assertIsNone(f)
        f, _, _ = festivals.today(date(2027, 3, 10), self.P, "இன்று ரம்ஜான் பண்டிகை கொண்டாட்டம்")
        self.assertEqual(f["theme"], "islamic")

    def test_normal_day(self):
        import rasi_festivals as festivals
        f, notes, _ = festivals.today(date(2026, 11, 2), {"tithi_idx": 14, "nakshatra_idx": 2})
        self.assertIsNone(f)
        self.assertEqual(notes, ["பௌர்ணமி", "கிருத்திகை"])

    def test_table_is_not_running_out(self):
        import rasi_festivals as festivals
        self.assertFalse(festivals.table_runs_out_soon(date.today()), "add next year's Tamil Nadu Government holiday list to festivals.OFFICIAL")


class WriterChecks(unittest.TestCase):
    def good(self):
        import rasi_writer as writer
        return {"rasis": [{"rasi": r, "stars": 4, "work": "பணியில் முன்னேற்றம் உண்டு", "money": "வருமானம் சீராக இருக்கும்",
                           "family": "குடும்பத்தில் மகிழ்ச்சி", "health": "உடல்நலம் சீராக இருக்கும்"} for r in writer.RASI]}

    def test_clean_draft_passes_and_chandrashtamam_is_capped(self):
        import rasi_writer as writer
        d = self.good()
        self.assertEqual(writer.check(d, [{"rasis": {"மேஷம்": "வேறு வார்த்தைகள்"}}], "விருச்சிகம்"), [])
        self.assertEqual(d["rasis"][7]["stars"], 2)

    def test_copied_words_english_and_fear_are_caught(self):
        import rasi_writer as writer
        d = self.good()
        d["rasis"][0]["work"] = "புதிய திட்டங்கள் நல்ல பலன் தரும்"
        d["rasis"][1]["money"] = "money வரும்"
        d["rasis"][2]["health"] = "ஆபத்து உண்டு"
        src = [{"rasis": {"மேஷம்": "இன்று புதிய திட்டங்கள் நல்ல பலன் தரும் நாள்"}}]
        errs = " ".join(writer.check(d, src, "விருச்சிகம்"))
        self.assertIn("copied", errs)
        self.assertIn("English", errs)
        self.assertIn("fear", errs)

    def test_proofreader_may_only_fix_sandhi(self):
        import rasi_writer as writer
        self.assertEqual(writer.sandhi_key("நிலுவை தொகை"), writer.sandhi_key("நிலுவைத் தொகை"))
        self.assertNotEqual(writer.sandhi_key("கேட்ட சலுகை"), writer.sandhi_key("கெட்ட சலுகை"))      # 31 Oct test run

    def test_missing_rasi(self):
        import rasi_writer as writer
        d = self.good()
        d["rasis"].pop()
        self.assertTrue(writer.check(d, [], "மேஷம்"))


class Sources(unittest.TestCase):
    def test_split_twelve_rasis(self):
        import rasi_sources as sources
        text = "\n".join(f"{r}\nஇன்று உங்களுக்கு நல்ல நாள். பணியில் முன்னேற்றம் உண்டு." for r in sources.RASI)
        rs = sources.split_rasis(text)
        self.assertEqual(len(rs), 12)
        self.assertTrue(all(v.startswith("இன்று") for v in rs.values()))
        tv9 = "\n".join(f"{sources.STEM[r]} ராசிக்காரர்களுக்கு இன்று நல்ல நாள். பணியில் முன்னேற்றம் உண்டு." for r in sources.RASI)
        self.assertEqual(len(sources.split_rasis(tv9)), 12)

    def test_date_tokens_match_real_urls(self):
        import rasi_sources as sources
        toks = sources.date_tokens(date(2026, 10, 31))
        for u in ("today-rasi-palan-in-tamil-daily-horoscope-october-31-2026-predictions-116738.html",
                  "today-rasi-palan-in-tamil-31-october-2026", "rasipalan-on-31st-october-2026-saturday-tns26103100481",
                  "todays-rasipalan-in-tamil-31102026"):
            self.assertTrue(any(t in u for t in toks), u)


class CaptionRules(unittest.TestCase):
    def test_caption(self):
        import rasi_daily as run, rasi_writer as writer
        p = {"date": "2026-10-31", "date_ta": "31 அக்டோபர் 2026", "weekday": "சனி", "tamil_month": "ஐப்பசி", "tamil_day": 14,
             "chandrashtamam": "விருச்சிகம்", "rahu": "9:00 – 10:30", "emagandam": "1:30 – 3:00", "kuligai": "6:00 – 7:30"}
        rs = [{"rasi": r, "stars": 5 if r == "சிம்மம்" else 3, "work": "பணியில் முன்னேற்றம்"} for r in writer.RASI]
        for page in ("rasipuram", "coimbatore"):
            cap = run.caption(run.PAGES[page], p, {"name": "தீபாவளி", "theme": "diwali"}, ["பிரதோஷம்"], rs)
            tags = [w for w in cap.split() if w.startswith("#")]
            self.assertLessEqual(len(tags), 5)
            self.assertEqual(tags[-1], "#Rasipuram360" if page == "rasipuram" else "#Coimbatore360")
            self.assertIn("#Deepavali", tags)
            self.assertIn("தீபாவளி நல்வாழ்த்துகள்", cap)
            self.assertIn("சிம்மம்", cap.split("\n")[2])
            self.assertNotIn("கமெண்ட்", cap)
            self.assertLess(len(cap), 2200)


class DateLinks1Nov(unittest.TestCase):
    """1 Nov 2026: nothing posted - TV9 wrote the day as 01 and Maalaimalar's link had no date"""
    def test_zero_padded_day(self):
        import rasi_sources as rs
        from datetime import date
        toks = rs.date_tokens(date(2026, 11, 1))
        self.assertTrue(any(t in "daily-horoscope-november-01-2026-predictions" for t in toks))

    def test_published_today_in_india(self):
        import rasi_sources as rs
        from datetime import date
        self.assertTrue(rs.is_today({"published": "2026-10-31T20:31:00Z", "url": "x"}, date(2026, 11, 1)))
        self.assertFalse(rs.is_today({"published": "2026-10-31T10:00:00Z", "url": "x"}, date(2026, 11, 1)))


class NeverMiss(unittest.TestCase):
    """owner 1 Nov: never miss a day - one source is enough after 9:30, trying until 12:30, backups through the morning"""
    def test_rules(self):
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent
        src = (root / "rasipalan" / "rasi_daily.py").read_text(encoding="utf-8")
        for s in ('ONE_SOURCE_AT = os.environ.get("ONE_SOURCE_AT", "09:30")', 'GIVE_UP_AT = os.environ.get("GIVE_UP_AT", "12:30")'):
            self.assertIn(s, src)
        wf = (root / ".github" / "workflows" / "rasipalan.yml").read_text(encoding="utf-8")
        for s in ('"30 1 * * *"', '"15 2 * * *"', '"15 4 * * *"', '"15 6 * * *"', "timeout-minutes: 340"):
            self.assertIn(s, wf)


class NallaNeram(unittest.TestCase):
    """owner 1 Nov: நல்ல நேரம் and சூலம் on the panchangam slide and in the caption; the day name spelt right"""
    ART = ("இன்றைய பஞ்சாங்கம்பராபவ ஆண்டு, ஐப்பசி - 15 (ஞாயிற்றுக்கிழமை)ராகுகாலம் : மாலை 4.30 மணி முதல் 6 மணி வரைசூலம் : மேற்கு"
           "நல்ல நேரம் : காலை 7 மணி முதல் 8 மணி வரை, மாலை 3 மணி முதல் 4 மணி வரை ஆஞ்சனேயருக்கு திருமஞ்சனம்சுபமுகூர்த்த தினம்.")

    def test_weekday_table_matches_maalaimalar_week(self):
        import rasi_panchang as P
        # Maalaimalar 26 Oct (Mon) .. 1 Nov (Sun) 2026
        want = [("6:00 – 7:00", "3:00 – 4:00", "கிழக்கு"), ("8:00 – 9:00", "5:00 – 6:00", "வடக்கு"), ("6:00 – 7:00", "4:00 – 5:00", "வடக்கு"),
                ("9:00 – 10:00", "4:00 – 5:00", "தெற்கு"), ("6:00 – 7:00", "5:00 – 6:00", "மேற்கு"), ("7:00 – 8:00", "5:00 – 6:00", "கிழக்கு"),
                ("7:00 – 8:00", "3:00 – 4:00", "மேற்கு")]
        self.assertEqual([(a, b, c[0]) for (a, b), c in zip(P.NALLA, P.SULAM)], want)
        self.assertEqual(P.WEEKDAY_FULL[6], "ஞாயிற்றுக்கிழமை")
        self.assertEqual(P.WEEKDAY_FULL[0], "திங்கட்கிழமை")

    def test_article_read(self):
        import rasi_sources as S
        p = {"nalla_morning": "x", "nalla_evening": "y", "sulam": "கிழக்கு", "sulam_parigaram": "தயிர்"}
        S.panchang_extras(self.ART, p, lambda *a: None)
        self.assertEqual((p["nalla_morning"], p["nalla_evening"], p["sulam"], p["sulam_parigaram"], p["subha_muhurtham"]),
                         ("7:00 – 8:00", "3:00 – 4:00", "மேற்கு", "வெல்லம்", True))

    def test_rows_and_caption(self):
        import rasi_render as R, rasi_daily as run, rasi_writer as writer
        p = {"date": "2026-11-01", "date_ta": "1 நவம்பர் 2026", "weekday": "ஞாயிறு", "weekday_full": "ஞாயிற்றுக்கிழமை", "tamil_month": "ஐப்பசி",
             "tamil_day": 15, "tithi": "சப்தமி", "paksha": "தேய்பிறை", "tithi_end": "x", "tithi_next": "அஷ்டமி", "nakshatra": "பூசம்",
             "nakshatra_end": "x", "nakshatra_next": "ஆயில்யம்", "yogam": "சாத்தியம்", "yogam_end": "x", "sunrise": "காலை 6:10",
             "sunset": "மாலை 5:51", "rahu": "4:30 – 6:00", "emagandam": "12:00 – 1:30", "kuligai": "3:00 – 4:30", "chandrashtamam": "தனுசு",
             "nalla_morning": "7:00 – 8:00", "nalla_evening": "3:00 – 4:00", "sulam": "மேற்கு", "sulam_parigaram": "வெல்லம்", "subha_muhurtham": True}
        labels = [r[0] for r in R.panchang_rows(p, "இராசிபுரம்")]
        self.assertIn("நல்ல நேரம்", labels)
        self.assertIn("சூலம்", labels)
        self.assertIn("சுபமுகூர்த்த நாள்", R.panchang_rows(p, "x")[0][2])
        rs = [{"rasi": r, "stars": 3, "work": "w"} for r in writer.RASI]
        cap = run.caption(run.PAGES["rasipuram"], p, None, [], rs)
        self.assertIn("நல்ல நேரம்: காலை 7:00 – 8:00, மாலை 3:00 – 4:00", cap)
        self.assertIn("ஞாயிற்றுக்கிழமை", cap)
        self.assertNotIn("ஞாயிறுக்கிழமை", cap)


class WriterNeverFailsOnOneLine(unittest.TestCase):
    """1 Nov (Coimbatore repost): 3 drafts each had 1 bad line -> the whole post failed. Now the best draft is used and only the
    bad lines are replaced by own safe lines."""
    def test_one_bad_line_is_repaired(self):
        import rasi_writer as W
        from unittest import mock
        src = [{"name": "A", "rasis": {r: "குடும்ப வாழ்க்கை அமைதியாக இருக்கும் நாள்" for r in W.RASI}}]
        def draft():
            rs = [{"rasi": r, "stars": 4, "work": "பணியில் முன்னேற்றம் உண்டு", "money": "வருமானம் சீராக இருக்கும்",
                   "family": "வீட்டில் சந்தோஷம் நிறையும்", "health": "உடல்நலம் சீராக இருக்கும்"} for r in W.RASI]
            rs[1]["family"] = "குடும்ப வாழ்க்கை அமைதியாக இருக்கும்"      # copied
            rs[0]["money"] = "பணம் " * 12                                # too long
            return {"rasis": rs}
        with mock.patch.object(W, "ask", side_effect=lambda *a: (draft(), "m")), mock.patch.object(W, "proofread", return_value=0):
            rs = W.write(src, "தனுசு", lambda *a: None)
        self.assertEqual(len(rs), 12)
        self.assertEqual(W.check({"rasis": rs}, src, "தனுசு"), [])
        self.assertIn(rs[1]["family"], W.SAFE["family"]["good"])

    def test_safe_lines_are_clean(self):
        import rasi_writer as W
        for lv in W.SAFE.values():
            for xs in lv.values():
                for x in xs:
                    self.assertLessEqual(len(x), W.MAX_CHARS + 6)
                    self.assertFalse(any(z in x for z in W.FEAR))


class VakyaFromMaalaimalar(unittest.TestCase):
    """owner 1 Nov: திதி / நட்சத்திரம் / யோகம் as Maalaimalar's daily panchangam (Vakya) prints them"""
    def test_read(self):
        import rasi_sources as S
        art = ("பிறை : தேய்பிறைதிதி : சப்தமி இரவு 7.19 மணி வரை பிறகு அஷ்டமி நட்சத்திரம் : புனர்பூசம் காலை 10.32 வரை பிறகு பூசம் "
               "யோகம் : சித்தயோகம்ராகுகாலம் : மாலை 4.30 மணி முதல் 6 மணி வரை")
        p = {"tithi": "x", "nakshatra": "y", "yogam": "z"}
        S.panchang_vakya(art, p, lambda *a: None)
        self.assertEqual((p["tithi"], p["tithi_end"], p["tithi_next"]), ("சப்தமி", "இரவு 7:19 வரை", "அஷ்டமி"))
        self.assertEqual((p["nakshatra"], p["nakshatra_end"], p["nakshatra_next"]), ("புனர்பூசம்", "காலை 10:32 வரை", "பூசம்"))
        self.assertEqual((p["yogam"], p["paksha"]), ("சித்தயோகம்", "தேய்பிறை"))

    def test_no_article_keeps_ours(self):
        import rasi_sources as S
        p = {"tithi": "சப்தமி", "tithi_end": "மதியம் 2:52 வரை"}
        S.panchang_vakya("", p, lambda *a: None)
        self.assertEqual(p["tithi_end"], "மதியம் 2:52 வரை")


if __name__ == "__main__":
    unittest.main()
