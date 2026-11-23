"""owner 23 Nov: a number the article writes in Indian grouping (29,86,950) is in the article - the news is not held."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "poster"))
import post      # noqa: E402


class IndianGrouping(unittest.TestCase):
    def test_indian_commas(self):
        self.assertTrue(post._number_in_article("2986950", "ரூ.29,86,950 மதிப்பில்"))
        self.assertTrue(post._number_in_article("1500000", "15,00,000 பேர்"))

    def test_wrong_number_still_held(self):
        self.assertFalse(post._number_in_article("46", "45 பேர் கைது"))


if __name__ == "__main__":
    unittest.main()
