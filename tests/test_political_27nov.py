"""owner 27 Nov evening: real party flags / leader photos (reel/political.py) - strict matching, free licences only, credits;
party short forms read letter by letter (research_free/names.py). No network, no browser."""
import json, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "reel"))
sys.path.insert(0, str(ROOT / "research_free"))
import political      # noqa: E402
import names      # noqa: E402


class Matching(unittest.TestCase):
    def test_parties_in_order_and_not_inside_words(self):
        self.assertEqual(political.parties("அதிமுக, திமுக, தவெக ஆதரித்தால்"), ["aiadmk", "dmk", "tvk"])
        self.assertEqual(political.parties("அதிமுகவினர் ஆர்ப்பாட்டம்"), ["aiadmk"])      # not also திமுக
        self.assertEqual(political.parties("தமிழ் மாநில காங்கிரஸ் கூட்டம்"), ["tmc"])      # not the Congress
        self.assertEqual(political.parties("சிபிஐ விசாரணை"), [])      # CBI, not a party

    def test_leaders_need_a_full_name_or_the_party(self):
        self.assertEqual(political.leaders("விஜய் என்ற இளைஞர் கைது"), [])
        self.assertEqual(political.leaders("தவெக தலைவர் விஜய் பேச்சு"), ["vijay"])
        self.assertEqual(political.leaders("பழனிசாமி என்பவர் விபத்தில் காயம்"), [])
        self.assertEqual(political.leaders("எடப்பாடி பழனிசாமி அறிக்கை"), ["edappadi_palaniswami"])
        self.assertEqual(political.leaders("திருவண்ணாமலை தீபம்; பாஜக கூட்டம்"), [])
        self.assertEqual(political.leaders("ராமதாஸ் என்பவர்"), [])

    def test_udhayanidhi_is_not_mk_stalin(self):
        self.assertEqual(political.leaders("உதயநிதி ஸ்டாலின் பேசினார், திமுக"), ["udhayanidhi_stalin"])
        self.assertEqual(political.leaders("திமுக தலைவர் மு.க. ஸ்டாலின்"), ["mk_stalin"])

    def test_no_post_titles(self):      # who holds a post changes with elections
        self.assertEqual(political.leaders("முதல்வர் ஸ்டாலின் வருகை"), [])


class Assets(unittest.TestCase):
    def test_every_manifest_file_is_free_and_present(self):
        m = political.manifest()
        for kind in ("flags", "leaders"):
            for k, e in (m.get(kind) or {}).items():
                self.assertTrue(political.FREE.match(str(e.get("license") or "")), f"{kind}/{k}: {e.get('license')}")
                self.assertTrue((political.ASSETS / e["file"]).exists(), f"{kind}/{k}: {e['file']} missing")
                self.assertTrue(str(e.get("commons") or "").startswith("File:"), f"{kind}/{k}")

    def test_leader_keys_known(self):
        for k in (political.manifest().get("leaders") or {}):
            self.assertIn(k, political.LEADER_FORMS)
            self.assertIn(k, political.LEADER_NAME)

    def test_credit_line_only_for_attribution_licences(self):
        m = {"flags": {"x": {"license": "Public domain", "file": "f.png", "commons": "File:F.svg"},
                       "y": {"license": "CC BY-SA 4.0", "file": "f.png", "commons": "File:Y.svg", "author": "Someone"}}}
        old, political._MAN = political._MAN, m
        try:
            real = political.asset
            political.asset = lambda kind, key: dict(m[kind][key], path="f.png") if key in m.get(kind, {}) else None
            self.assertEqual(political.credit_line(["x"]), "")
            self.assertIn("Someone, CC BY-SA 4.0", political.credit_line(["x", "y"]))
        finally:
            political.asset = real
            political._MAN = old


class Voice(unittest.TestCase):
    def test_party_short_forms_letter_by_letter(self):
        s = names.spoken("அஇஅதிமுக, திமுகவினர், தமாகா, மநீம, இபிஎஸ், எஸ்டிபிஐ")
        for want in ("அ இ அ தி மு க", "தி மு க வினர்", "த மா கா", "ம நீ ம", "இ பி எஸ்", "எஸ் டி பி ஐ"):
            self.assertIn(want, s)


if __name__ == "__main__":
    unittest.main()
