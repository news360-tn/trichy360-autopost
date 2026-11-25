"""19 Nov: insights read every post of the last 8 days (was the latest 50 = about 2 days, so almost no reel got final numbers), keep
carousels apart from learned.json, keep same-age numbers (about 24 h / 48 h) and once a day the follower / non-follower reach."""
import datetime
import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UTC = datetime.timezone.utc
NOW = datetime.datetime.now(UTC).replace(minute=0, second=0, microsecond=0)      # owner 25 Nov: today (a fixed date drifted out of the 8-day window)


def load():
    """poster/insights.py with stand-ins for post / learned (no network, nothing real is written)"""
    fake_post = types.ModuleType("post")
    fake_post.ig = None
    fake_learned = types.ModuleType("learned")
    fake_learned.topic = lambda cap: "crime" if "கைது" in cap else "other"
    saved = {k: sys.modules.get(k) for k in ("post", "learned")}
    sys.modules.update(post=fake_post, learned=fake_learned)
    try:
        spec = importlib.util.spec_from_file_location("insights_19nov", ROOT / "poster" / "insights.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
    return mod


def media(n, hours_old, kind="REELS", cap="செய்தி"):
    t = (NOW - datetime.timedelta(hours=hours_old)).strftime("%Y-%m-%dT%H:%M:%S+0000")
    return {"id": str(n), "timestamp": t, "media_product_type": kind, "caption": cap}


def insights_answer(metrics, value=100):
    return {"data": [{"name": m, "values": [{"value": value}]} for m in metrics.split(",")]}


class RecentMedia(unittest.TestCase):
    def setUp(self):
        self.ins = load()

    def test_follows_pages_until_the_window_ends(self):
        page1 = {"data": [media(i, i * 3) for i in range(50)], "paging": {"cursors": {"after": "A"}, "next": "x"}}      # 0 .. 147 h
        page2 = {"data": [media(100 + i, 150 + i * 3) for i in range(50)], "paging": {"cursors": {"after": "B"}, "next": "y"}}      # 150 .. 297 h
        calls = []

        def ig(method, path, tok, **p):
            calls.append(p.get("after"))
            return page1 if not p.get("after") else page2
        self.ins.post.ig = ig
        got = self.ins.recent_media("U", "t", now=NOW)
        self.assertEqual(calls, [None, "A"])      # page 2 read, page 3 not (page 2 already ends past 8 days)
        self.assertTrue(all((NOW - self.ins._when(i["timestamp"])).total_seconds() <= 8 * 86400 for i in got))
        self.assertEqual(len(got), 50 + 15)      # page 2 posts up to 192 h (150 .. 192 h = 15 posts)

    def test_a_failing_second_page_keeps_the_first(self):
        page1 = {"data": [media(i, i) for i in range(50)], "paging": {"cursors": {"after": "A"}, "next": "x"}}

        def ig(method, path, tok, **p):
            if p.get("after"):
                raise RuntimeError("Instagram busy")
            return page1
        self.ins.post.ig = ig
        self.assertEqual(len(self.ins.recent_media("U", "t")), 50)


class ReadRow(unittest.TestCase):
    def setUp(self):
        self.ins = load()
        self.asked = []

        def ig(method, path, tok, **p):
            self.asked.append(p.get("metric"))
            return insights_answer(p["metric"])
        self.ins.post.ig = ig

    def row(self, m, old=None, now=NOW):
        return self.ins.read_row(m, "salem", "t", old, now)

    def test_reel_and_carousel_metrics(self):
        r = self.row(media(1, 5))
        self.assertNotIn("type", r)
        self.assertIn("ig_reels_avg_watch_time", self.asked[-1])
        c = self.row(media(2, 5, "FEED"))
        self.assertEqual(c["type"], "FEED")
        self.assertNotIn("ig_reels_avg_watch_time", self.asked[-1])      # carousels have no watch time
        self.assertIsNone(self.row(media(3, 5, "STORY")))

    def test_final_after_7_days_and_once_a_day_after_3(self):
        self.assertFalse(self.row(media(1, 100))["final"])
        self.assertTrue(self.row(media(1, 170))["final"])
        self.assertIsNone(self.row(media(1, 200), old={"final": True}))
        recent = {"read": (NOW - datetime.timedelta(hours=5)).isoformat()}
        self.assertIsNone(self.row(media(1, 100), old=recent))      # 4 days old, read 5 h ago: not again
        self.assertIsNotNone(self.row(media(1, 30), old=recent))     # 1 day old: every run
        day_ago = {"read": (NOW - datetime.timedelta(hours=21)).isoformat()}
        self.assertIsNotNone(self.row(media(1, 100), old=day_ago))

    def test_same_age_numbers_are_kept(self):
        r24 = self.row(media(1, 25))
        self.assertEqual(r24["r24"]["reach"], 100)
        self.assertNotIn("r48", r24)
        later = self.row(media(1, 50), old=r24)
        self.assertEqual(later["r24"], r24["r24"])      # the 24 h numbers never change afterwards
        self.assertEqual(later["r48"]["age_h"], 50.0)
        self.assertNotIn("r24", self.row(media(2, 5)))


class AccountInsights(unittest.TestCase):
    def setUp(self):
        self.ins = load()
        self.tmp = tempfile.TemporaryDirectory()
        self.ins.ACCOUNT = str(Path(self.tmp.name) / "account.json")

    def tearDown(self):
        self.tmp.cleanup()

    def test_followers_vs_non_followers_and_cities_once_a_day(self):
        n = []

        def ig(method, path, tok, **p):
            n.append(p["metric"])
            if p["metric"] == "reach":
                return {"data": [{"total_value": {"value": 900, "breakdowns": [{"results": [
                    {"dimension_values": ["FOLLOWER"], "value": 200}, {"dimension_values": ["NON_FOLLOWER"], "value": 700}]}]}}]}
            return {"data": [{"total_value": {"breakdowns": [{"results": [
                {"dimension_values": ["Salem, Tamil Nadu"], "value": 800}, {"dimension_values": ["Chennai, Tamil Nadu"], "value": 90}]}]}}]}
        self.ins.post.ig = ig
        out = self.ins.account_insights("U", "t", "salem", now=NOW)
        self.assertEqual(out["reach_by_follow_type"], {"FOLLOWER": 200, "NON_FOLLOWER": 700})
        self.assertEqual(list(out["follower_cities"])[0], "Salem, Tamil Nadu")
        self.ins.account_insights("U", "t", "salem", now=NOW)
        self.assertEqual(len(n), 2)      # the second run of the day asks nothing

    def test_a_refused_metric_never_stops_the_run(self):
        def ig(method, path, tok, **p):
            raise RuntimeError("(#10) not enough followers")
        self.ins.post.ig = ig
        out = self.ins.account_insights("U", "t", "salem", now=NOW)
        self.assertIn("reach_error", out)
        self.assertIn("cities_error", out)


class LearnedStaysReelsOnly(unittest.TestCase):
    def test_carousels_never_change_learned_json(self):
        ins = load()
        tmp = tempfile.TemporaryDirectory()
        base = Path(tmp.name)
        (base / "poster" / "insights").mkdir(parents=True)
        (base / "research_free").mkdir()
        ins.HERE = str(base / "poster")
        ins.HIST = str(base / "poster" / "insights" / "history.json")
        ins.ACCOUNT = str(base / "poster" / "insights" / "account.json")
        posts = [media(i, 30 + i, cap="கைது செய்தி") for i in range(14)] + [media(100 + i, 40 + i, "FEED", "ராசி பலன்") for i in range(5)]

        def ig(method, path, tok, **p):
            if path.endswith("/media"):
                return {"data": posts}
            if path.endswith("/insights") and "/" in path and path.split("/")[0] in ("U",):
                raise RuntimeError("no account insights in this test")
            if path == "U":
                return {"followers_count": 10, "media_count": 19}
            return insights_answer(p["metric"], 50)
        ins.post.ig = ig
        ins.post.bridge_get = lambda *a, **k: {"token": "t"}
        ins.post.ig_account = lambda tok: ("U", "salem")
        try:
            ins.main()
            hist = json.load(open(ins.HIST, encoding="utf-8"))
            learned = json.load(open(base / "research_free" / "learned.json", encoding="utf-8"))
        finally:
            tmp.cleanup()
        self.assertEqual(sum(1 for h in hist.values() if h.get("type") == "FEED"), 5)
        self.assertEqual(learned["posts_measured"], 14)      # reels only


if __name__ == "__main__":
    unittest.main()
