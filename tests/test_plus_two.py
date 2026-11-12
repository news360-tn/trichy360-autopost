"""owner 12 Nov (RN-534): 'பிளஸ் 2 மாணவர்' was read 'பிளஸ் இரண்டு' - it is said 'பிளஸ் டூ'."""
import sys, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "reel"))
from tamilnum import speak_numbers      # noqa: E402


class PlusTwo(unittest.TestCase):
    def test_plus_two_and_one(self):
        for src in ("பிளஸ் 2 மாணவர்", "பிளஸ்2 மாணவர்", "பிளஸ்-2 மாணவர்", "Plus 2 மாணவர்", "+2 மாணவர்"):
            self.assertEqual(speak_numbers(src), "பிளஸ் டூ மாணவர்", src)
        self.assertEqual(speak_numbers("பிளஸ் 1 தேர்வு"), "பிளஸ் ஒன் தேர்வு")

    def test_other_numbers_unchanged(self):
        self.assertEqual(speak_numbers("17 வயது மகன்"), "பதினேழு வயது மகன்")
        self.assertEqual(speak_numbers("10ம் வகுப்பு"), "பத்தாம் வகுப்பு")
        self.assertEqual(speak_numbers("2 பேர் காயம்"), "இரண்டு பேர் காயம்")
        self.assertNotIn("டூ", speak_numbers("பிளஸ் 25 கிலோ"))      # not a school year


if __name__ == "__main__":
    unittest.main()
