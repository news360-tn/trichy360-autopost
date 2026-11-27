"""owner 27 Nov: 06:00-22:00 IST every news posts as soon as it is ready; 22:00-06:00 only urgent news (an upcoming power cut, or a topic
whose reels on this page often pass 10,000 views). Was (21 Nov): any time from 04:00, nothing at all 00:00-04:00."""
import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "poster"))
sys.path.insert(0, str(ROOT / "research_free"))
import post      # noqa: E402
import learned      # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))
ROW = {"story_id": "RN-1", "headline_ta": "சாலை சீரமைப்பு", "headline_en": "road work", "category": "civic"}
CUT = {"story_id": "RN-2", "headline_ta": "நாளை மின் தடை", "headline_en": "power cut tomorrow", "category": "மின் தடை"}


def at(h, m=0):
    return datetime(2026, 11, 21, h, m, tzinfo=IST)


class PostingHours(unittest.TestCase):
    def setUp(self):
        self.p = mock.patch.object(learned, "load", return_value={"urgent_topics": []})
        self.p.start()

    def tearDown(self):
        self.p.stop()

    def test_settings(self):
        cfg = json.loads((ROOT / "poster" / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(cfg["prime_time"]["windows"], [["06:00", "22:00"]])
        self.assertEqual(cfg["prime_time"]["quiet_ist"], [])
        self.assertEqual(cfg["prime_time"]["immediate"], "priority")
        self.assertEqual(cfg["posting"]["spacing_min"], 5)

    def test_any_time_from_6_to_22(self):
        for h, m in ((6, 0), (7, 30), (13, 10), (16, 0), (21, 30), (21, 59)):
            self.assertEqual(post.prime_wait(ROW, at(h, m)), "", (h, m))

    def test_only_urgent_news_at_night(self):
        with mock.patch.object(post, "age_hours", return_value=30):      # even a news that waited long
            for h, m in ((22, 0), (23, 30), (0, 30), (3, 0), (5, 59)):
                self.assertIn("night", post.prime_wait(ROW, at(h, m)), (h, m))
                self.assertEqual(post.prime_wait(CUT, at(h, m)), "", (h, m))      # an upcoming power cut posts at once

    def test_10k_topic_is_urgent(self):
        with mock.patch.object(learned, "load", return_value={"urgent_topics": ["civic"]}):
            self.assertTrue(post.is_priority_news(ROW))      # 'சாலை' = civic
            self.assertEqual(post.prime_wait(ROW, at(2)), "")
        self.assertFalse(post.is_priority_news(ROW))
        self.assertTrue(post.is_priority_news(CUT))


if __name__ == "__main__":
    unittest.main()
