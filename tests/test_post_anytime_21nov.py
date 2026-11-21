"""owner 21 Nov: no best-time waiting - news posts as soon as it is ready from 05:00 to midnight; nothing at all from 00:00 to 05:00 IST"""
import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "poster"))
import post      # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))
ROW = {"story_id": "RN-1", "headline_ta": "சாலை சீரமைப்பு", "headline_en": "road work", "category": "civic"}
CUT = {"story_id": "RN-2", "headline_ta": "நாளை மின் தடை", "headline_en": "power cut tomorrow", "category": "மின் தடை"}


def at(h, m=0):
    return datetime(2026, 11, 21, h, m, tzinfo=IST)


class PostAnyTime(unittest.TestCase):
    def test_settings(self):
        cfg = json.loads((ROOT / "poster" / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(cfg["prime_time"]["windows"], [["05:00", "24:00"]])
        self.assertEqual(cfg["prime_time"]["quiet_ist"], ["00:00", "05:00"])
        self.assertEqual(cfg["posting"]["spacing_min"], 5)

    def test_any_time_from_5_am(self):
        for h, m in ((5, 0), (7, 30), (13, 10), (16, 0), (21, 30), (23, 59)):
            self.assertEqual(post.prime_wait(ROW, at(h, m)), "", (h, m))

    def test_nothing_at_night(self):
        with mock.patch.object(post, "age_hours", return_value=30):      # even a news that waited long
            for h in (0, 2, 4):
                self.assertIn("night", post.prime_wait(ROW, at(h, 30)))
                self.assertIn("night", post.prime_wait(CUT, at(h, 30)))      # even a power cut
        self.assertEqual(post.prime_wait(CUT, at(5, 0)), "")


if __name__ == "__main__":
    unittest.main()
