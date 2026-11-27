"""owner 27 Nov: 30 news a day per page on Instagram / Facebook / YouTube (rasipalan and gold rate not counted), best by views first;
after an error 5 tries 10 minutes apart then one try 1 hour later; a temporary block waits the time the platform states, else 2 hours;
news collected every 2 hours."""
import json
import re
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "poster"))
sys.path.insert(0, str(ROOT / "research_free"))
import blockwait      # noqa: E402
import facebook      # noqa: E402
import learned      # noqa: E402
import post      # noqa: E402
import youtube      # noqa: E402
import ytupload      # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))


class ThirtyNewsADay(unittest.TestCase):
    def test_settings(self):
        wf = (ROOT / ".github" / "workflows" / "post.yml").read_text(encoding="utf-8")
        self.assertIn('DAILY_CAP: "30"', wf)
        self.assertIn('FB_TOP_PER_DAY: "30"', wf)
        cfg = json.loads((ROOT / "poster" / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(cfg["youtube_upload"]["per_day"], 30)
        self.assertEqual(cfg["youtube_upload"]["hours"], [6, 22])

    def test_news_today_counts_only_todays_news(self):
        tmp = Path(tempfile.mkdtemp())
        now = datetime(2026, 11, 27, 12, 0, tzinfo=timezone.utc)      # 17:30 IST; the IST day began 26 Nov 18:30 UTC
        for name in ("20261126-120000-pg-RN-1.json",      # yesterday (IST)
                     "20261126-190000-pg-RN-2.json", "20261127-080000-pg-RN-3.json",      # today
                     "20261127-090000-other-RN-4.json",      # another page
                     "20261127-100000-pg-rasipalan-1.json", "20261127-100500-pg-goldrate-1.json"):      # daily posts: not counted
            (tmp / name).write_text("{}")
        with mock.patch.object(post, "POSTED_DIR", tmp):
            self.assertEqual(post.news_today("pg", now), 2)

    def test_over_30_only_urgent(self):
        src = (ROOT / "poster" / "post.py").read_text(encoding="utf-8")
        self.assertIn("news_today(pg) >= SOFT_CAP and not is_priority_news(row)", src)
        self.assertIn("(is_priority_news(r) or news_today(p) < SOFT_CAP)", src)

    def test_youtube_best_watched_topic_first(self):
        items = [{"caption": "கோவில் திருவிழா", "timestamp": "2026-11-27T05:00:00"},
                 {"caption": "நகை திருட்டு: 2 பேர் கைது", "timestamp": "2026-11-27T01:00:00"}]
        with mock.patch.object(learned, "load", return_value={"topic_weight": {"crime": 1.5, "temple": -0.2}}):
            self.assertEqual(youtube.pick(items, 1)[0]["caption"], "நகை திருட்டு: 2 பேர் கைது")
        with mock.patch.object(learned, "load", return_value={"topic_weight": {"crime": -0.5, "temple": 1.0}}):
            self.assertEqual(youtube.pick(items, 1)[0]["caption"], "கோவில் திருவிழா")


class RetryPlan(unittest.TestCase):
    def test_instagram_plan(self):
        self.assertEqual(post.RETRY_PLAN_MIN, (10, 10, 10, 10, 10, 60))

    def test_facebook_plan(self):
        self.assertEqual(facebook.MAX_TRIES, 7)
        self.assertEqual([facebook.retry_wait_min(n) for n in range(1, 7)], [10, 10, 10, 10, 10, 60])

    def test_facebook_post_never_sent_again_at_once(self):
        calls = []
        def boom(*a, **k):
            calls.append(a[0])
            raise facebook.requests.ConnectionError("down")
        with mock.patch.object(facebook.requests, "request", side_effect=boom), mock.patch.object(facebook.time, "sleep"):
            with self.assertRaises(RuntimeError):
                facebook._call("POST", "1/video_reels", "t", x=1)
            self.assertEqual(calls, ["POST"])      # one try only - the next one 10 minutes later
            calls.clear()
            with self.assertRaises(RuntimeError):
                facebook._call("GET", "1", "t")
            self.assertEqual(len(calls), 3)      # a read may be repeated

    def test_youtube_plan(self):
        tmp = Path(tempfile.mkdtemp())
        now = datetime(2026, 11, 27, 6, 0, tzinfo=timezone.utc)
        s = ytupload.settings({"youtube_upload": {"per_day": 30, "gap_min": 5, "hours": [0, 24]}})
        with mock.patch.object(ytupload, "STATE", tmp):
            st = ytupload._state("pg")
            st.update(failed_at=now.isoformat(), fail_n=5, fail_ig="m1")
            ytupload._save("pg", st)
            self.assertIn("10 min", ytupload.due("pg", s, now + timedelta(minutes=5)))
            self.assertEqual(ytupload.due("pg", s, now + timedelta(minutes=11)), "")
            st.update(fail_n=6)
            ytupload._save("pg", st)
            self.assertIn("60 min", ytupload.due("pg", s, now + timedelta(minutes=30)))
            self.assertEqual(ytupload.due("pg", s, now + timedelta(minutes=61)), "")


class TemporaryBlock(unittest.TestCase):
    def test_stated_time_is_used(self):
        self.assertEqual(blockwait.wait_hours("{'estimated_time_to_regain_access': 90}"), 1.5)
        self.assertEqual(blockwait.wait_hours("You're temporarily blocked. Please try again in 3 hours."), 3.0)
        self.assertEqual(blockwait.wait_hours("Try again in 45 minutes"), 0.75)
        self.assertEqual(blockwait.wait_hours("You can't post for 2 days"), 48.0)

    def test_no_stated_time_2_hours(self):
        self.assertEqual(blockwait.wait_hours("(#368) The action attempted has been deemed abusive or is otherwise disallowed"), 2.0)
        self.assertEqual(blockwait.wait_hours("Media Creation Limit Exceeded 2207069"), 2.0)

    def test_instagram_block_waits_the_stated_time(self):
        tmp = Path(tempfile.mkdtemp())
        with mock.patch.object(post, "CACHE", tmp), mock.patch.dict(post.LIMIT, {}, clear=True):
            post.ig_pause("pg", "action is blocked 2207051")
            until = datetime.fromisoformat(json.loads(post.ig_pause_file("pg").read_text())["until"])
            self.assertAlmostEqual((until - datetime.now(timezone.utc)).total_seconds() / 3600, 2.0, delta=0.02)
            post.ig_pause_file("pg").unlink()
            post.ig_pause("pg", "blocked - try again in 5 hours")
            until = datetime.fromisoformat(json.loads(post.ig_pause_file("pg").read_text())["until"])
            self.assertAlmostEqual((until - datetime.now(timezone.utc)).total_seconds() / 3600, 5.0, delta=0.02)

    def test_facebook_block_waits_the_stated_time(self):
        tmp = Path(tempfile.mkdtemp())
        with mock.patch.object(facebook, "STATE", tmp):
            facebook._pause("pg", "(#368) temporarily blocked")
            until = datetime.fromisoformat(json.loads(facebook._pause_file("pg").read_text())["until"])
            self.assertAlmostEqual((until - facebook._now()).total_seconds() / 3600, 2.0, delta=0.02)


class CollectEveryTwoHours(unittest.TestCase):
    def test_rounds(self):
        import watchdog
        self.assertEqual([h for h, _ in watchdog.ROUNDS], list(range(0, 24, 2)))


class UrgentTopics(unittest.TestCase):
    def test_urgent_topic(self):
        with mock.patch.object(learned, "load", return_value={"urgent_topics": ["crime"]}):
            self.assertTrue(learned.urgent_topic("நகை திருட்டு: 2 பேர் கைது"))
            self.assertFalse(learned.urgent_topic("கோவில் திருவிழா"))

    def test_insights_writes_them(self):
        src = (ROOT / "poster" / "insights.py").read_text(encoding="utf-8")
        self.assertIn('out["urgent_topics"]', src)
        self.assertTrue(re.search(r"URGENT_VIEWS, URGENT_SHARE = 10000, 0\.2", src))


if __name__ == "__main__":
    unittest.main()
