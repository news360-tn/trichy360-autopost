"""owner 23 Nov: common words of a location (நகரம், நிலையம், ரோடு ...) never hold a news; the real place word is still checked."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research_free"))
import validate      # noqa: E402

ART = "வெள்ளகோவில் நகர் பகுதியில் உள்ள பேருந்து நிலையத்தில் இன்று காலை கூட்டம் நடந்தது. உழவர் சந்தையில் காய்கறி விலை உயர்ந்தது."


def loc_problems(loc):
    return [p for p in validate.grounding_problems({"slides_spec": {"loc": loc}, "tamil_headline": "", "reel_script": "", "caption": ""}, ART)
            if "location" in p]


class GenericLocationWords(unittest.TestCase):
    def test_common_words_do_not_hold(self):
        for loc in ("வெள்ளகோவில் நகரம்", "வெள்ளகோவில் பஸ் நிலையம்", "வெள்ளகோவில் ரோடு", "வெள்ளகோவில் உழவர் சந்தை"):
            self.assertEqual(loc_problems(loc), [], loc)

    def test_a_wrong_place_still_holds(self):
        self.assertTrue(loc_problems("மேட்டுப்பாளையம் நகரம்"))


if __name__ == "__main__":
    unittest.main()
