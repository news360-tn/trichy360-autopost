"""owner 22 Nov: Facebook one post every 60 minutes, at most 15 a day, the most important waiting news first; after the 15 the rest
goes to the owner's e-mail at once (share from the Instagram app)."""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "poster"))
import facebook      # noqa: E402
import post          # noqa: E402

NOW = datetime(2026, 11, 22, 6, 0, tzinfo=timezone.utc)


class FacebookPriority(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.p = [mock.patch.object(facebook, "STATE", self.d), mock.patch.object(facebook, "_now", return_value=NOW)]
        for x in self.p:
            x.start()

    def tearDown(self):
        for x in self.p:
            x.stop()

    def wait(self, sid, minutes, rank):
        facebook._save("x", sid, "reel", {"status": "waiting", "ig_media": "M", "caption": sid, "rank": rank,
                                          "waiting_since": (NOW - timedelta(minutes=minutes)).isoformat()})

    def test_most_important_first_then_oldest(self):
        self.wait("RN-1", 50, {"urgent": False, "best": False, "weight": 0.1})
        self.wait("RN-2", 10, {"urgent": False, "best": True, "weight": 0.5})
        self.wait("RN-3", 40, {"urgent": False, "best": True, "weight": 0.5})
        self.assertEqual(facebook.next_waiting("x")["story"], "RN-3")
        self.wait("RN-4", 1, {"urgent": True, "best": False, "weight": 0})
        self.assertEqual(facebook.next_waiting("x")["story"], "RN-4")

    def test_day_full_is_a_hard_limit(self):
        with mock.patch.object(facebook, "news_posted_today", return_value=15), \
                mock.patch.object(facebook, "TOP_PER_DAY", 15), mock.patch.object(facebook, "paused", return_value=""), \
                mock.patch.object(facebook, "top_news", return_value=(True, "")):
            self.assertTrue(facebook.day_full("x"))
            self.assertIn("limit", facebook.gate("x", {"urgent": True}))

    def test_settings(self):
        wf = (ROOT / ".github" / "workflows" / "post.yml").read_text(encoding="utf-8")
        self.assertIn('FB_GAP_MIN: "5"', wf)      # owner 23 Nov: 5 minutes, like Instagram
        self.assertIn('FB_TOP_PER_DAY: "30"', wf)      # owner 24 Nov: every news like Instagram (Meta's 30-a-day limit)
        self.assertEqual(wf.count("FB_TOP_PER_DAY"), 1)


class FifteenPerCalendarDay(unittest.TestCase):
    def test_yesterday_and_daily_posts_do_not_count(self):
        d = Path(tempfile.mkdtemp())
        with mock.patch.object(facebook, "STATE", d), mock.patch.object(facebook, "_now", return_value=NOW):      # 11:30 IST
            facebook._save("x", "RN-1", "reel", {"status": "posted", "posted_at": "2026-11-22T05:00:00+00:00"})      # today 10:30 IST
            facebook._save("x", "RN-2", "reel", {"status": "posted", "posted_at": "2026-11-21T17:00:00+00:00"})      # yesterday 22:30 IST
            facebook._save("x", "rasipalan-2026-11-22", "reel", {"status": "posted", "posted_at": "2026-11-22T01:00:00+00:00"})
            facebook._save("x", "goldrate-reel-2026-11-22", "reel", {"status": "posted", "posted_at": "2026-11-22T04:00:00+00:00"})
            self.assertEqual(facebook.news_posted_today("x"), 1)


class AfterFifteenToEmail(unittest.TestCase):
    def test_day_full_sends_at_once(self):
        d = Path(tempfile.mkdtemp())
        sent = []
        with mock.patch.object(facebook, "STATE", d), mock.patch.dict(os.environ, {"FB_PAGE_ID_X": "PG", "FB_TOKEN_X": "T"}), \
                mock.patch.object(post, "LABEL", {"x": "X"}), mock.patch.object(post, "DRY", False), \
                mock.patch.object(post, "quiet_now", return_value=""), mock.patch.object(post, "bridge_get", return_value={"token": "T"}), \
                mock.patch.object(post, "ig", return_value={"permalink": "https://www.instagram.com/reel/a/"}), \
                mock.patch.object(facebook, "day_full", return_value=True), \
                mock.patch("promo.hub_post", side_effect=lambda a, p: sent.append(p)):
            facebook._save("x", "RN-9", "reel", {"status": "waiting", "ig_media": "M", "caption": "Head\nbody",
                                                 "waiting_since": (NOW - timedelta(minutes=5)).isoformat()})
            post.facebook_share_email(NOW)
        self.assertEqual(len(sent), 1)      # only 5 minutes waiting, but the day's 15 are done: e-mailed at once
        self.assertIn("Share to Facebook", sent[0]["text"])
        r = json.loads((d / "x-RN-9-reel.json").read_text(encoding="utf-8"))
        self.assertEqual(r["status"], "manual")


if __name__ == "__main__":
    unittest.main()
