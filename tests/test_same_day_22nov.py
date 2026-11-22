"""owner 22 Nov: today's news and yesterday's pending news are posted; news older than yesterday never (a power-cut notice always)."""
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
    def test_yesterday_pending_is_posted_older_is_not(self):
        self.assertFalse(post.published_before_today({"published": "2026-11-21T22:30:00+05:30"}, NOW))
        self.assertFalse(post.published_before_today({"published": "2026-11-21"}, NOW))
        self.assertTrue(post.published_before_today({"published": "2026-11-20T23:00:00+05:30"}, NOW))

    def test_today_is_posted(self):
        self.assertFalse(post.published_before_today({"published": "2026-11-22T00:05:00+05:30"}, NOW))
        self.assertFalse(post.published_before_today({"published": "2026-11-21T19:00:00Z"}, NOW))      # 00:30 IST today

    def test_unknown_date_and_power_cut_still_posted(self):
        self.assertFalse(post.published_before_today({"published": ""}, NOW))
        self.assertFalse(post.published_before_today({"published": "22 Nov"}, NOW))
        self.assertFalse(post.published_before_today({"published": "2026-11-19", "category": "மின் தடை"}, NOW))

    def test_wired_in(self):
        src = (ROOT / "poster" / "post.py").read_text(encoding="utf-8")
        self.assertIn("if not is_ready_reel(row) and published_before_today(row):", src)


if __name__ == "__main__":
    unittest.main()


sys.path.insert(0, str(ROOT / "research_free"))


class DailyThirtyCountsTodaysNews(unittest.TestCase):
    def test_only_todays_news_uses_the_30(self):
        import collect
        self.assertTrue(collect._published_before({"published": "2026-11-21T20:00:00+05:30"}, NOW))      # yesterday's pending: outside the 30
        self.assertFalse(collect._published_before({"published": "2026-11-22T06:00:00+05:30"}, NOW))
        self.assertFalse(collect._published_before({"published": ""}, NOW))
