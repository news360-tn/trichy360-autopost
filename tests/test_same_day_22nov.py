"""owner 22 Nov: only news published that same day (IST) is posted - yesterday's news never; a power-cut notice still is."""
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "poster"))
import post      # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))
NOW = datetime(2026, 11, 22, 10, 0, tzinfo=IST)


class SameDay(unittest.TestCase):
    def test_yesterday_is_not_posted(self):
        self.assertTrue(post.published_before_today({"published": "2026-11-21T22:30:00+05:30"}, NOW))
        self.assertTrue(post.published_before_today({"published": "2026-11-21"}, NOW))

    def test_today_is_posted(self):
        self.assertFalse(post.published_before_today({"published": "2026-11-22T00:05:00+05:30"}, NOW))
        self.assertFalse(post.published_before_today({"published": "2026-11-21T19:00:00Z"}, NOW))      # 00:30 IST today

    def test_unknown_date_and_power_cut_still_posted(self):
        self.assertFalse(post.published_before_today({"published": ""}, NOW))
        self.assertFalse(post.published_before_today({"published": "22 Nov"}, NOW))
        self.assertFalse(post.published_before_today({"published": "2026-11-21", "category": "மின் தடை"}, NOW))

    def test_wired_in(self):
        src = (ROOT / "poster" / "post.py").read_text(encoding="utf-8")
        self.assertIn("if not is_ready_reel(row) and published_before_today(row):", src)


if __name__ == "__main__":
    unittest.main()
