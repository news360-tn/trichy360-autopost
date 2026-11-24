"""owner 24 Nov: a self-immolation / suicide ATTEMPT where nobody died (a protest) is picked automatically; a death still needs the
owner's tick. Samayam Tamil is a trusted outlet (open search)."""
import sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research_free"))
import pick      # noqa: E402


class AttemptSamayam24Nov(unittest.TestCase):
    def ok(self, t):
        return pick.auto_ok({"title": t, "url": "https://www.dinakaran.com/x"})

    def test_attempt_is_news(self):
        self.assertEqual(self.ok("கலெக்டர் ஆபீசில் பெண், முதியவர் தீக்குளிக்க முயற்சி"), "")
        self.assertEqual(self.ok("பல்லடத்தில் பெண் தீக்குளிக்க முயற்சி"), "")

    def test_death_still_needs_the_tick(self):
        self.assertIn("suicide", self.ok("தனியார் வங்கி அட்டூழியத்தால் மகன் தற்கொலை"))
        self.assertIn("suicide", self.ok("தீக்குளிக்க முயன்ற பெண் உயிரிழப்பு"))

    def test_samayam(self):
        self.assertIn("tamil.samayam.com", pick.OUTLETS)
        self.assertIn("tamil.samayam.com", pick.OPEN_OUTLETS)


if __name__ == "__main__":
    unittest.main()
