"""owner 27 Nov (Trichy views test, second round): news themes by topic, readable fact-card labels, the short ending, the voice pool,
prebuilt reels keep their voice / design, YouTube titles that keep whole words. No network, no browser."""
import json, re, sys, types, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "reel"))
sys.path.insert(0, str(ROOT / "poster"))
if "playwright.sync_api" not in sys.modules:      # reel4 only needs the browser in main(); these tests never render
    try:
        import playwright.sync_api      # noqa: F401
    except Exception:
        _pw, _sa = types.ModuleType("playwright"), types.ModuleType("playwright.sync_api")
        _sa.sync_playwright = None
        sys.modules["playwright"], sys.modules["playwright.sync_api"] = _pw, _sa
try:
    import reel4
except BaseException as e:      # a render dependency is missing on this machine
    reel4 = None
    WHY = str(e)
CFG = json.loads((ROOT / "poster" / "config.json").read_text(encoding="utf-8"))
VT = CFG.get("views_test") or {}


def spec(cat, mini, hook=("", "")):
    return {"cat": cat, "mini": mini, "hook": list(hook), "location": "மறவனூர், மணப்பாறை"}


@unittest.skipIf(reel4 is None, "reel4 could not be imported")
class FactCards(unittest.TestCase):
    def label(self, text):
        return reel4.card_for(text)["label"]

    def test_karur_is_not_money(self):
        """RN-171 (27 Nov): 'திருச்சி - கரூர் தேசிய நெடுஞ்சாலை' showed a ₹ 'தொகை' card - 'கரூர்' contains 'ரூ'"""
        self.assertEqual(self.label("திருச்சி - கரூர் தேசிய நெடுஞ்சாலையில் விபத்து"), "இடம்")

    def test_real_money_is_money(self):
        for t in ("ரூ.5,000 அபராதம்", "ரூ 3 லட்சம் வருமானம்", "2 கோடி மதிப்பில்", "ரூபாய் வழங்கப்பட்டது", "₹500 கட்டணம்"):
            self.assertEqual(self.label(t), "தொகை", t)

    def test_people_word_alone_is_not_a_count(self):
        """RN-169: 'மக்கள் நலனைக் கருத்தில் கொண்டு' showed 'எத்தனை பேர்'"""
        self.assertEqual(self.label("மக்கள் நலனைக் கருத்தில் கொண்டு பணியாற்ற வேண்டும்"), "முக்கிய தகவல்")
        self.assertEqual(self.label("4 பேர் காயம்"), "எத்தனை பேர்")

    def test_paper_name_is_not_a_time(self):
        self.assertEqual(self.label("தினமணி செய்தி"), "முக்கிய தகவல்")
        self.assertEqual(self.label("காலை 10 மணிக்கு"), "நேரம்")


@unittest.skipIf(reel4 is None, "reel4 could not be imported")
class NewsThemes(unittest.TestCase):
    def test_every_configured_theme_exists(self):
        for topic, th in (VT.get("topic_themes") or {}).items():
            self.assertIn(th, reel4.STYLES, f"{topic} -> {th}")
            self.assertIn(th, reel4.THEME_ACCENT, th)
        for st in VT.get("styles") or []:
            self.assertIn(st, reel4.STYLES)

    @unittest.skipUnless(VT.get("enabled") and VT.get("topic_themes"), "news themes are switched off")
    def test_topic_picks_its_theme(self):
        cases = [(spec("சாலை விபத்து", "மணப்பாறை அருகே கார் கவிழ்ந்து விபத்து"), "accident"),
                 (spec("குற்றம்", "ஸ்ரீரங்கத்தில் கஞ்சாவுடன் 2 பேர் கைது"), "crime"),
                 (spec("மின் தடை", "லால்குடியில் நாளை மின் தடை"), "power_cut"),
                 (spec("மழை எச்சரிக்கை", "திருச்சியில் இன்று கனமழை"), "weather")]
        for sp, topic in cases:
            self.assertEqual(reel4.news_topic(sp), topic)
            self.assertEqual(reel4.theme_for(sp), VT["topic_themes"][topic])

    def test_unknown_topic_has_no_theme(self):
        self.assertEqual(reel4.theme_for(spec("", "xyz")), "")

    def test_themes_keep_text_on_solid_boxes(self):
        """a theme never leaves the caption or the headline as bare text on the photo"""
        for th in reel4.THEME_ACCENT:
            css = reel4.STYLES[th]
            self.assertRegex(css, r"\.ph\{[^}]*background:", th)
            self.assertRegex(css, r"#hook \.h1\{[^}]*background:", th)

    def test_design_c_is_dark_glass(self):
        """27 Nov: white frosted cards on a bright photo could not be read"""
        self.assertIn(".card{background:rgba(8,12,24,.8)", reel4.STYLES["C"])


@unittest.skipIf(reel4 is None, "reel4 could not be imported")
class EndingAndVoices(unittest.TestCase):
    def test_share_town(self):
        self.assertEqual(reel4.share_town({"location": "மறவனூர், மணப்பாறை"}), "மணப்பாறை")
        self.assertEqual(reel4.share_town({"location": "திருச்சி ஆட்சியரகம்"}), "திருச்சி")
        self.assertEqual(reel4.share_town({}), "திருச்சி")

    def test_end_line_is_tamil_and_short(self):
        line = str(VT.get("end_line_ta") or "")
        if line:
            said = line.replace("{town}", "மண்ணச்சநல்லூர்")
            self.assertLessEqual(len(said.split()), 12)
            self.assertNotRegex(said, r"[A-Za-z{}]")      # the Tamil voice reads it

    def test_voice_pool_is_free_tamil_voices(self):
        pool = (CFG.get("reel_voice") or {}).get("ab_voices") or []
        for v in pool:
            self.assertRegex(v, r"^ta-(IN|MY|SG|LK)-\w+Neural$")
        self.assertEqual(len(pool), len(set(pool)))

    @unittest.skipUnless(VT.get("enabled") and len((CFG.get("reel_voice") or {}).get("ab_voices") or []) > 1, "one voice only (no voice test)")
    def test_same_story_same_voice_and_every_voice_used(self):
        pool = CFG["reel_voice"]["ab_voices"]
        seen = set()
        for i in range(200):
            sp = spec("", f"செய்தி {i}", (f"தலைப்பு {i}", "x"))
            v = reel4.pick_voice(sp)[0]["voice"]
            self.assertEqual(v, reel4.pick_voice(sp)[0]["voice"])
            seen.add(v)
        self.assertEqual(seen, set(pool))

    def test_pictures_take_turns(self):
        if not VT.get("cycle_pictures"):
            self.skipTest("cycle_pictures is off")
        shots = reel4.plan_shots(3, 24.0, [])
        self.assertEqual([s["img"] for s in shots[:6]], [0, 1, 2, 0, 1, 2])


class PrebuiltKeepsVariant(unittest.TestCase):
    def test_cache_carries_the_variant(self):
        """RN-168 / 169 / 171 (27 Nov) were posted from the prebuilt cache without voice / design - the views test could not count them"""
        src = (ROOT / "poster" / "post.py").read_text(encoding="utf-8")
        save = src[src.index("def save_cache("):src.index("VIA_FB = [False]")]
        self.assertIn('"variant": LAST_REEL_META', save)
        self.assertIn('LAST_REEL_META.get("story") == sid', save)
        self.assertRegex(src, r'cached\["variant"\]\.get\("story"\) == sid')


class YouTubeTitles(unittest.TestCase):
    def setUp(self):
        import youtube
        self.yt = youtube

    def title(self, head, body=""):
        return self.yt.details({"caption": head + "\n\n" + body + "\n#Trichy360", "timestamp": "2026-11-26T05:00:00+0000"}, "trichy", "x")["title"]

    def test_long_headline_is_cut_at_a_word(self):
        head = "காட்டுப்புத்தூரில் இளைஞரைக் குத்திக் கொன்ற மூவருக்கு ஆயுள் தண்டனை"
        t = self.title("🚨 " + head)
        self.assertLessEqual(len(t), self.yt.TITLE_MAX)
        kept = t.split("…")[0].strip()
        self.assertTrue(head.startswith(kept))
        self.assertIn(head[len(kept):len(kept) + 1], (" ", ""))      # the cut is at a word end
        self.assertTrue(t.endswith("| Trichy"))

    def test_topic_comes_from_the_headline(self):
        """26 Nov: a murder was titled 'Trichy sports news' because the caption body had போட்டி in it"""
        t = self.title("🚨 லால்குடி அருகே பைக் விபத்தில் இளைஞர் பலி", "கபடி போட்டி விளையாட்டு விருது")
        self.assertTrue(t.endswith("| Trichy accident news"), t)

    def test_daily_reels_keep_their_search_word(self):
        t = self.title("இன்றைய ராசிபலன் | 26 நவம்பர் 2026, வியாழக்கிழமை")
        self.assertTrue(t.endswith("| Trichy rasi palan today"), t)
        self.assertNotIn("…", t)


class DailyReels(unittest.TestCase):
    def test_rasipalan_opens_with_the_12_rasis(self):
        sys.path.insert(0, str(ROOT / "goldrate"))
        sys.path.insert(0, str(ROOT / "rasipalan"))
        import rasi360_render as R
        if not R.grid_on():
            self.skipTest("rasi_grid is off")
        win, dur = R.timeline()
        self.assertEqual(len(win), 15)      # grid + 12 rasis + panchangam + follow card
        P = {"date_ta": "27 நவம்பர் 2026", "weekday_full": "வெள்ளிக்கிழமை", "chandrashtamam": "விருச்சிகம்"}
        rs = [{"rasi": n, "stars": 1 + i % 5} for i, n in enumerate(["மேஷம்", "ரிஷபம்", "மிதுனம்", "கடகம்", "சிம்மம்", "கன்னி", "துலாம்",
                                                                    "விருச்சிகம்", "தனுசு", "மகரம்", "கும்பம்", "மீனம்"])]
        html = R.grid_scene({"logo": "/x.png", "name1": "திருச்சி"}, P, rs, lambda k: "")
        self.assertEqual(html.count('class="cell'), 12)
        self.assertEqual(html.count("top3"), 3)
        self.assertIn("கவனம்", html)

    def test_gold_change_is_on_the_first_frame(self):
        sys.path.insert(0, str(ROOT / "goldrate"))
        import gold360_render as G
        if not G.change_first():
            self.skipTest("gold_change_first is off")
        r = {"date": "27 நவம்பர் 2026", "g22": 11600, "g22_prev": 11540, "g24": 12655, "g24_prev": 12589, "vs": "நேற்றைய விலையைவிட"}
        page = G.reel_page({"town": "திருச்சி", "name1": "திருச்சி", "handle": "x", "logo": "/x.png"}, r)
        self.assertRegex(page, r'class="chg up" data-a="-1\.00')


if __name__ == "__main__":
    unittest.main()
