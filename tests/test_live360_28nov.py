"""owner 28 Nov: design A + improvements on every page (the sample the owner chose) - pictures take turns, a BREAKING tag on serious
news, a place card with the district map; no clock-hand line across the picture. A layer over the finished page: the reel never fails."""
import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "reel"))
import clock360  # noqa: E402
import live360  # noqa: E402

MAP = json.loads((ROOT / "reel" / "assets" / "district_map.json").read_text(encoding="utf-8"))
CENTRE = MAP["towns"][MAP["district_ta"]]
TOWN = next(t for t, xy in MAP["towns"].items() if xy != CENTRE)      # a town of this district that is not the district town


def page(n=2, cuts=8, rows=4):
    shots = [{"a": i * 2.0, "b": i * 2.0 + 2, "img": 0 if i < cuts // 2 else 1, "z0": 1, "z1": 1.1} for i in range(cuts)]
    shots.append({"a": cuts * 2.0, "b": cuts * 2.0 + 6, "img": 1, "z0": 1, "z1": 1.1})      # the end card's shot
    D = {"shots": shots, "sents": [], "caps": [], "hook_end": 4.2, "end_t": cuts * 2.0 - 0.5, "total": cuts * 2.0 + 4, "n": n,
         "single": n == 1, "sum_a": cuts * 2.0 - 5, "rows": rows}
    return ('<!doctype html><html><head><style>body{}</style></head><body><img id="plogo" src="x"><div id="pin"><span>x</span></div>'
            '<div id="hook"></div><div id="mini"></div><div class="card" id="c1"></div><div id="cap"></div><div id="end"><img src="x"></div>'
            f'<script>const D={json.dumps(D, ensure_ascii=False)};window.renderAt=function(t){{}};</script></body></html>')


def spec(mini="சாலையில் கார் விபத்தில் 3 பேர் பலி", loc=None, hook=None):
    return {"mini": mini, "hook": hook or [mini, "விவரம்"], "location": TOWN + " அருகே" if loc is None else loc, "cat": "செய்தி"}


def cfg(**k):
    return mock.patch.object(live360, "config", lambda: dict(k))


class Live360(unittest.TestCase):
    def setUp(self):
        os.environ.pop("REEL_LIVE360", None)

    def test_pictures_take_turns_every_second_cut(self):
        with cfg():
            D = live360.page_data(live360.add(page(), spec()))[0]
        self.assertEqual([s["img"] for s in D["shots"]], [0, 0, 1, 1, 0, 0, 1, 1, 1])      # the last one is the end card's: unchanged
        with cfg():
            one = live360.page_data(live360.add(page(n=1), spec()))[0]
        self.assertEqual([s["img"] for s in one["shots"]], [s["img"] for s in live360.page_data(page(n=1))[0]["shots"]])      # one picture: as before
        three = {"n": 3, "end_t": 99, "shots": [{"a": i, "img": 0} for i in range(8)]}
        self.assertTrue(live360.turn_pictures(three))
        self.assertEqual([s["img"] for s in three["shots"]], [0, 0, 1, 1, 2, 2, 0, 0])

    def test_breaking_only_on_serious_news(self):
        for mini in ("சாலையில் கார் விபத்தில் 3 பேர் பலி", "மின்சாரம் தாக்கி விவசாயி உயிரிழப்பு", "வாலிபர் கொலை: 2 பேர் கைது",
                     "பஸ் கவிழ்ந்து 12 பேர் படுகாயம்"):
            self.assertTrue(live360.serious(spec(mini)), mini)
            with cfg():
                self.assertEqual(live360.add(page(), spec(mini)).count('id="lvbrk"'), 1, mini)
        for mini in ("நாளை மின்தடை அறிவிப்பு", "தங்கம் விலை உயர்வு", "பலித்த கனவு: மாணவி சாதனை", "கொலை மிரட்டல் விடுத்தவர் கைது",
                     "மகளிர் உரிமைத் தொகை முகாம்"):
            self.assertFalse(live360.serious(spec(mini)), mini)
            with cfg():
                self.assertNotIn('id="lvbrk"', live360.add(page(), spec(mini)), mini)
        self.assertTrue(live360.serious(spec("விபத்து", hook=["கார் மோதல்", "பலி எண்ணிக்கை <b>10</b>"])))      # the headline's second line counts

    def test_place_card_for_a_known_town_only(self):
        with cfg():
            out = live360.add(page(), spec("பள்ளி ஆண்டு விழா"))
        x, y = MAP["towns"][TOWN]
        for k in ('id="lvmap"', f'cx="{x}" cy="{y}"', f"<b>{TOWN}</b>", MAP["district_ta"] + " மாவட்டம்", MAP["path"][:40]):
            self.assertIn(k, out)
        self.assertNotIn('id="lvbrk"', out)
        with cfg():
            self.assertNotIn('id="lvmap"', live360.add(page(), spec("பள்ளி ஆண்டு விழா", loc="தெரியாத ஊர்")))
            self.assertNotIn('id="lvmap"', live360.add(page(cuts=3, rows=0), spec("பள்ளி ஆண்டு விழா")))      # a very short reel: no room in time
        with cfg(map_intro=True):      # the reel already opens with the map (Trichy): no second map
            self.assertNotIn('id="lvmap"', live360.add(page(), spec("பள்ளி ஆண்டு விழா")))

    def test_village_of_the_district_town_gets_no_pin(self):
        d = MAP["district_ta"]
        self.assertEqual(live360.town_of(d, MAP), d)
        self.assertEqual(live360.town_of(d + " மாநகர்", MAP), d)
        self.assertEqual(live360.town_of("தெரியாத கிராமம், " + d, MAP), "")
        self.assertEqual(live360.town_of(TOWN + ", " + d, MAP), TOWN)
        self.assertEqual(live360.town_of("", MAP), "")

    def test_every_town_pin_is_on_the_map(self):
        self.assertGreaterEqual(len(MAP["towns"]), 10)
        for t, (x, y) in MAP["towns"].items():
            self.assertTrue(20 <= x <= 240 and 20 <= y <= 240, t)

    def test_layer_once_and_page_kept(self):
        with cfg():
            out = live360.add(page(), spec())
            self.assertEqual(live360.add(out, spec()), out)      # never twice
        for k in ('id="lvbrk"', 'id="lvmap"', "const old=window.renderAt", "</style>", "</body>"):
            self.assertEqual(out.count(k), 1, k)
        for k in ('<img id="plogo" src="x">', '<div id="hook"></div>', '<div id="cap"></div>'):
            self.assertIn(k, out)      # the design's own parts are untouched
        with cfg():
            self.assertIn('id="cklogo"', clock360.add(out))      # the clock ring still goes on after it, and the other way round
            self.assertIn('id="lvmap"', live360.add(clock360.add(page()), spec()))

    def test_every_addition_inside_the_shared_safe_area(self):      # owner 28 Nov: one video for Instagram, Facebook and YouTube Shorts
        css = live360.CSS + live360.JS
        for k in ("#lvmap{position:absolute;left:48px", "max-width:880px", "brk.style.right='48px'", "box($('cap')).top-12-mapTop",
                  "p.right+24<=1080-48-brk.offsetWidth", "y>=p.bottom+10", "map.scrollWidth>MW", "MW=950-L-(rd?0:42)",
                  "L=rd?48+rd.offsetWidth+22:48"):      # the card stays left of x 950, beside the news reader when there is one
            self.assertIn(k, css, k)

    def test_never_fails_the_reel(self):
        with cfg():
            for bad in ("", None, "<html></html>", page().replace("const D=", "const E="), page().replace('id="pin"', 'id="x"'),
                        page().replace("</style>", "</style><style></style>"), page().replace("</body>", '<div id="fxloop"></div></body>')):
                self.assertEqual(live360.add(bad, spec()), bad)
            self.assertEqual(live360.add(page(), {}), live360.add(page(), {"location": None}))
            self.assertIn("const D=", live360.add(page(), {}))

    def test_switch_off(self):
        with cfg(reel_live=False):
            self.assertEqual(live360.add(page(), spec()), page())
        os.environ["REEL_LIVE360"] = "0"
        with cfg():
            self.assertEqual(live360.add(page(), spec()), page())
        os.environ.pop("REEL_LIVE360")

    def test_reel_uses_it_and_no_clock_hand_line(self):
        src = (ROOT / "reel" / "reel4.py").read_text(encoding="utf-8")
        self.assertIn("import live360", src)
        self.assertIn("live360.add(clock360.add(new_page or build_html(spec, shots, sents, caps, hook_end, end_t, total, R.PAGE)), spec)", src)
        self.assertIn("if(0&&D.shots", clock360.JS)      # owner 28 Nov: "this clock line do not use"
        self.assertNotIn("if(D.shots", clock360.JS)


if __name__ == "__main__":
    unittest.main()
