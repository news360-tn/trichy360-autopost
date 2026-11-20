"""owner 20 Nov: the design team's reel design on every page (reel/design360.py) - the earlier design one switch away"""
import os
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "reel"))
if "playwright" not in sys.modules:      # the test machine has no browser
    pw = types.ModuleType("playwright"); api = types.ModuleType("playwright.sync_api"); api.sync_playwright = None
    sys.modules.update({"playwright": pw, "playwright.sync_api": api})
import clock360  # noqa: E402
import design360 as D  # noqa: E402

SPEC = {"hook": ["இதயத் துடிப்பு சிறப்பு முகாம்", "நவம்பர் 26 வரை அனுமதி"], "location": "கோவை", "date": "19 நவம்பர் 2026",
        "source": "தினமலர்", "images": ["/tmp/a.jpg", "/tmp/b.jpg"]}
SENTS = [{"a": 0.1, "b": 5.0, "say": "x", "fact": ""}, {"a": 5.6, "b": 12.0, "say": "y", "fact": "இடம்: KMCH, அவிநாசி சாலை"},
         {"a": 12.2, "b": 18.0, "say": "z", "fact": {"not": "text"}}]
CAPS = [{"a": 0.1, "b": 5.0, "words": [("கோவையில்", 0.1, 1.0), ("முகாம்", 1.0, 2.0)]},
        {"a": 5.6, "b": 12.0, "words": [("அவிநாசி", 5.6, 6.5), ("சாலையில்", 6.5, 7.5)]}]
SHOTS = [{"a": 0.0, "b": 9.0, "img": 0}, {"a": 9.0, "b": 25.0, "img": 1}]
PAGE = {"name": "கோயம்புத்தூர் 360", "tagline": "நம்ம கோவை செய்திகள்", "logo": "logo.png"}
OUTRO = {"a": 19.0, "b": 22.0, "text": "மேலும் செய்திகளுக்கு கோயம்புத்தூர் த்ரீ சிக்ஸ்டி பக்கத்தை பின்தொடருங்கள்."}


class Design360(unittest.TestCase):
    def test_on_unless_classic(self):      # owner 20 Nov (final): config says classic; REEL_DESIGN=handoff switches it on
        with mock.patch.dict(os.environ, {"REEL_DESIGN": "handoff"}):
            self.assertTrue(D.on())
        with mock.patch.dict(os.environ, {"REEL_DESIGN": "classic"}):
            self.assertFalse(D.on())

    def test_band_follows_the_facts(self):      # no fact yet: the hook's 2nd line; a sentence without a fact keeps the last one
        self.assertEqual(D.bands(SPEC, SENTS), ["நவம்பர் 26 வரை அனுமதி", "இடம்: KMCH, அவிநாசி சாலை", "இடம்: KMCH, அவிநாசி சாலை"])
        self.assertEqual(D.bands({"hook": ["தலைப்பு"]}, [{"fact": ""}, {"fact": "A"}]), ["A", "A"])
        self.assertEqual(D.bands({"hook": ["தலைப்பு"]}, [{"fact": ""}]), ["தலைப்பு"])

    def test_spoken_words_and_closing_line(self):
        w = D.words(CAPS, SENTS, OUTRO)
        self.assertEqual([x[0] for x in w[0]], ["கோவையில்", "முகாம்"])
        self.assertIn("360", w[-1][0][0])      # the spoken "த்ரீ சிக்ஸ்டி" is written 360 on screen
        self.assertNotIn("சிக்ஸ்டி", w[-1][0][0])

    def page(self):
        return D.page(SPEC, SHOTS, SENTS, CAPS, 18.0, 23.0, PAGE, OUTRO)

    def test_the_layout(self):
        h = self.page()
        for x in ('id="acc"', 'id="pub"', 'id="desc"', 'id="plogo"', 'id="loc"', 'id="hl"', 'id="band"', 'id="sup"', 'id="rule"',
                  'id="foot"', "window.renderAt", "window.fitAll", "window.DUR", "top:493px", "top:1180px", "top:1312px", "top:1442px"):
            self.assertIn(x, h)
        self.assertIn("Source: தினமலர்", h)      # owner 20 Nov: "Source: paper", no "ஆதாரம்"
        self.assertNotIn("ஆதாரம்", h)
        self.assertIn("19 நவம்பர் 2026", h)
        for gone in ('id="end"', 'class="card"', 'id="sum"', "மாதிரிப் படம்", 'id="disc"'):      # owner 20 Nov: not in this design
            self.assertNotIn(gone, h)
        self.assertNotIn('id="loc"', D.page(dict(SPEC, location=""), SHOTS, SENTS, CAPS, 18.0, 23.0, PAGE, OUTRO))

    def test_text_is_fitted_never_cut(self):      # owner 20 Nov: no overlapping or cut text
        h = self.page()
        self.assertIn("[70,64,58,52]", h)      # headline steps down only when it does not fit 2 lines
        self.assertIn("[38,34,30]", h)      # the band text
        self.assertIn("m.offsetHeight>lim", h)      # the supporting lines are cut by measurement
        self.assertNotIn("text-overflow", h)

    def test_clock_branding_on_top(self):      # owner 20 Nov: the 360 clock branding on this design too
        h = clock360.add(self.page())
        for x in ('id="cklogo"', 'id="ckhand"', "const old=window.renderAt"):
            self.assertIn(x, h)

    def test_wired_with_the_earlier_design_as_fallback(self):
        src = (ROOT / "reel" / "reel4.py").read_text(encoding="utf-8")
        self.assertIn("import design360", src)
        self.assertIn("if design360.on():", src)
        self.assertIn("new_page or build_html(", src)
        self.assertIn("if(c)c.style.display='none'", src)      # the cover step works on both designs
        self.assertNotIn("document.getElementById('cap').style.display='none';document.getElementById('hook')", src)


if __name__ == "__main__":
    unittest.main()
