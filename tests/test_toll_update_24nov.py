"""owner 24 Nov: a death-toll update ('மேலும் ஒருவர் உயிரிழப்பு', 'எண்ணிக்கை 9 ஆக உயர்வு') is new news, not a duplicate of the first report."""
import sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "poster"))
sys.path.insert(0, str(ROOT / "research_free"))
import freshness      # noqa: E402
import collect      # noqa: E402


class TollUpdate24Nov(unittest.TestCase):
    def test_detect(self):
        self.assertTrue(freshness.toll_update({"headline_ta": "முசிறி விபத்து: மேலும் ஒருவா் உயிரிழப்பு இறந்தோா் எண்ணிக்கை 9 ஆக உயா்வு"}))
        self.assertTrue(freshness.toll_update({"headline_ta": "பலி எண்ணிக்கை 5 ஆக உயர்வு"}))
        self.assertFalse(freshness.toll_update({"headline_ta": "துறையூர் அருகே வேன் மரத்தில் மோதி 8 தொழிலாளர்கள் பலி"}))

    def test_follow_up_next_day(self):
        old = {"headline_ta": "துறையூர் அருகே வேன் மோதி 8 பேர் பலி", "researched": "23 Nov 2026, 08:00"}
        new = {"headline_ta": "முசிறி விபத்து: மேலும் ஒருவர் உயிரிழப்பு - எண்ணிக்கை 9 ஆக உயர்வு", "researched": "24 Nov 2026, 09:00"}
        self.assertTrue(freshness.follow_up(old, new))

    def test_writer_does_not_drop_it(self):
        art = {"url": "https://www.dinamani.com/x/toll", "title": "மேலும் ஒருவர் உயிரிழப்பு"}
        recent = [{"source": "https://www.dinamani.com/x/first", "headline_ta": "மேலும் ஒருவர் உயிரிழப்பு", "researched": "24 Nov 2026"}]
        self.assertFalse(collect.is_dup(art, {"tamil_headline": "முசிறி விபத்து: மேலும் ஒருவர் உயிரிழப்பு"}, recent))
        self.assertTrue(collect.is_dup(art, {"tamil_headline": "x"}, [{"source": "https://www.dinamani.com/x/toll"}]))      # never the same article twice


if __name__ == "__main__":
    unittest.main()
