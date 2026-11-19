"""19 Nov trial (new pages): a normal reel tells the key facts in 60-90 words (about 35-45 s; 60-80 word reels reached the most
people), a power cut keeps up to 160 words with every area; sentence 1 is short; active voice; respectful words for deaths."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research_free"))
sys.path.insert(0, str(ROOT / "poster"))
import validate      # noqa: E402


def draft(n_words, power=False):
    body = n_words - len(validate.LAST.split())
    sent = "ஆத்தூர் சாலையில் பஸ் மோதி இருவர் காயமடைந்தனர்.".split()
    words = []
    while len(words) < body:
        words += sent
    d = {k: "x" for k in validate.KEYS}
    d.update({"tamil_headline": "ஆத்தூரில் நாளை மின் தடை" if power else "ஆத்தூரில் பஸ் விபத்து",
              "english_headline": "Attur power cut tomorrow" if power else "Attur bus accident",
              "category": "மின் தடை" if power else "Crime & Safety",
              "reel_script": " ".join(words[:body]).rstrip(".") + ". " + validate.LAST,
              "slides_spec": {"v": 3, "cat": "விபத்து", "loc": "ஆத்தூர்", "hl1": "ஆத்தூரில் பஸ் விபத்து", "hl2": "இருவர் காயம்",
                              "slides": [{"title": "விபத்து", "lines": ["ஆத்தூரில் பஸ் மோதி இருவர் காயம்", "போலீசார் விசாரணை"]}] * 3},
              "scenes": ["A town road after a bus hit two people, a police jeep nearby, evening light, wide view"] * 2})
    return d


def length_problem(d):
    return [x for x in validate.validate(d, "") if x.startswith("reel_script has")]


class ReelLength(unittest.TestCase):
    def test_normal_news_60_to_90_words(self):
        self.assertFalse(length_problem(draft(75)))
        self.assertTrue(length_problem(draft(120)))      # was accepted up to 160 words
        self.assertIn("need 60-90", length_problem(draft(120))[0])

    def test_power_cut_keeps_every_area(self):
        self.assertFalse(length_problem(draft(150, power=True)))


class MaxSeconds(unittest.TestCase):
    def test_news_reel_at_most_60_seconds(self):
        import json
        c = json.loads((ROOT / "poster" / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(60, c["reel_max_seconds"])      # owner 19 Nov
        self.assertGreaterEqual(c["power_cut"]["max_seconds"], 60)      # a power cut keeps its own limit (every area)


class WriterRules(unittest.TestCase):
    rules = (ROOT / "research_free" / "rules.md").read_text(encoding="utf-8")

    def test_rules_ask_for_the_new_length_and_hook(self):
        self.assertIn("60-90 words", self.rules)
        self.assertNotIn("70-160 words", self.rules)
        self.assertIn("5-7 words, about 3 seconds", self.rules)
        self.assertIn("never more than 60 seconds", self.rules)

    def test_active_voice_and_death_words(self):
        self.assertIn("ACTIVE voice", self.rules)
        self.assertIn("never \"சாவு\"", self.rules)


if __name__ == "__main__":
    unittest.main()
