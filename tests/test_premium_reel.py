"""owner 13 Nov: the premium story panel on the new pages - the look and the motion layer only; voice, timing and facts unchanged."""
import json, re, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "reel"))
try:
    import reel4
except Exception as e:      # playwright is not installed on every machine that runs the tests
    reel4 = None
    WHY = str(e)


def spec(**kw):
    s = {"cat": "மின் தடை", "location": "", "hook": ["நாளை மின்தடை", "காலை 9 முதல் 5 வரை"], "mini": "நாளை காலை 9 முதல் மாலை 5 வரை மின்தடை",
         "date": "13 நவம்பர் 2026", "source": "தினமலர்", "source_full": "தினமலர் (13 நவம்பர் 2026)", "images": ["/x.jpg"]}
    s.update(kw)
    return s


@unittest.skipIf(reel4 is None, "reel4 needs playwright")
class PremiumReel(unittest.TestCase):
    def test_page_uses_the_namakkal_design(self):
        """owner 13 Nov 23:10: every page uses the Namakkal 360 design (look A); the premium look P stays in the code, switched off"""
        self.assertEqual(json.loads((ROOT / "poster" / "config.json").read_text(encoding="utf-8"))["reel_style"], "A")
        self.assertEqual(reel4.reel_style({}), "A")
        deps = json.loads((ROOT / "kit" / "package.json").read_text(encoding="utf-8"))["dependencies"]
        self.assertIn("@fontsource-variable/anek-tamil", deps)
        self.assertIn("@fontsource/noto-serif-tamil", deps)

    def test_no_black_in_the_premium_look(self):
        css = reel4.STYLES["P"].lower()
        self.assertNotRegex(css, r"#000\b|#000000|rgba\(0,\s*0,\s*0|\bblack\b")

    def test_news_type_layer(self):
        self.assertEqual(reel4.premium_kind(spec()), "power")
        self.assertEqual(reel4.premium_kind(spec(cat="விபத்து", hook=["பேருந்து கவிழ்ந்தது", "15 பேர் காயம்"], mini="")), "accident")
        self.assertEqual(reel4.premium_kind(spec(cat="வானிலை", hook=["கனமழை எச்சரிக்கை", ""], mini="")), "rain")
        self.assertEqual(reel4.premium_kind(spec(cat="குற்றம்", hook=["கஞ்சா பறிமுதல்", "2 பேர் கைது"], mini="")), "crime")
        self.assertEqual(reel4.premium_kind(spec(cat="கோவில்", hook=["கும்பாபிஷேக விழா", ""], mini="")), "")

    def test_power_cut_time_bar_needs_both_ends(self):
        self.assertEqual(reel4.time_span(spec()), ("காலை 9", "மாலை 5"))
        self.assertIsNone(reel4.time_span(spec(mini="நாளை மின்தடை", hook=["நாளை மின்தடை", "காலை 9 மணி முதல்"])))

    def test_district_map_and_town_pin(self):
        m = json.loads((ROOT / "reel" / "assets" / "district_map.json").read_text(encoding="utf-8"))
        self.assertTrue(m["path"].startswith("M") and len(m["towns"]) >= 10)
        for x, y in m["towns"].values():
            self.assertTrue(0 <= x <= 260 and 0 <= y <= 260)
        town = sorted(m["towns"], key=len)[-1]
        path, tx, ty, label, credit = reel4.district_map(town + ", " + m["district_ta"])
        self.assertEqual([tx, ty], m["towns"][town])
        self.assertIn(town, label)
        self.assertIsNone(reel4.district_map("வேறு ஊர்")[1])      # an unknown town: the district outline without a pin

    def test_layer_added_only_to_the_premium_look(self):
        page = "<html><body><script>window.renderAt=function(t){}</script></body></html>"
        out = reel4.premium_layer(page, spec())
        for k in ('id="fxloop"', 'id="fxtl"', "window.renderAt", 'const KIND="power"'):
            self.assertIn(k, out)
        self.assertEqual(out.count("</body></html>"), 1)


if __name__ == "__main__":
    unittest.main()
