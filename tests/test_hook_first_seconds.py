"""owner 13 Nov: the first 3 seconds of a reel - the spoken sentence 1 names the town and states the news (no question / teaser)."""
import sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research_free"))
import validate      # noqa: E402

LOC = "ஆலம்பட்டி, மாவட்டம்"


def draft(rs, hl1="ஆலம்பட்டி: 3 பேர் கைது"):
    return {"reel_script": rs, "slides_spec": {"loc": "ஆலம்பட்டி", "hl1": hl1, "hl2": ""}}


class FirstSeconds(unittest.TestCase):
    def test_good_opening_passes(self):
        self.assertEqual(validate.place_problems(draft("ஆலம்பட்டியில் மணல் கடத்திய 3 பேர் கைது. போலீசார் விசாரணை.")), [])

    def test_town_missing_in_spoken_sentence_1(self):
        p = validate.place_problems(draft("மணல் கடத்திய 3 பேர் கைது. ஆலம்பட்டியில் போலீசார் விசாரணை."))
        self.assertTrue(any("sentence 1" in x and "ஆலம்பட்டி" in x for x in p), p)

    def test_question_or_teaser_refused(self):
        for rs in ("ஆலம்பட்டியில் என்ன நடந்தது தெரியுமா? 3 பேர் கைது.", "ஆலம்பட்டியில் ஒரு அதிர்ச்சி சம்பவம். 3 பேர் கைது."):
            p = validate.place_problems(draft(rs))
            self.assertTrue(any("teaser" in x for x in p), (rs, p))

    def test_dotted_initials_are_not_a_sentence_end(self):
        self.assertEqual(validate.first_sentence("ப.வேலூரில் 2 பேர் கைது. போலீசார் விசாரணை."), "ப.வேலூரில் 2 பேர் கைது.")

    def test_on_screen_rule_still_first(self):
        p = validate.place_problems(draft("மணல் கடத்தல். விசாரணை.", hl1="3 பேர் கைது"))
        self.assertEqual(len(p), 1)
        self.assertIn("hl1", p[0])


if __name__ == "__main__":
    unittest.main()
