"""owner 18 Nov: rasipalan 6:40, gold 9:40, afternoon gold change at 3:30 PM, and the watchdog that starts them on time."""
import datetime as d, importlib, os, sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "poster")); sys.path.insert(0, str(ROOT / "goldrate")); sys.path.insert(0, str(ROOT / "rasipalan"))
import watchdog as W      # noqa: E402

UTC = d.timezone.utc
def ist(h, m):
    return d.datetime(2026, 11, 19, h, m, tzinfo=W.IST).astimezone(UTC)
OLD = [("completed", ist(0, 1) - d.timedelta(hours=8))]      # last run long ago, finished


class Watchdog(unittest.TestCase):
    def test_rasipalan_from_6_43(self):
        self.assertEqual(W.decide(ist(6, 30), False, None, OLD, OLD, "", None), [])
        self.assertEqual(W.decide(ist(6, 50), False, None, OLD, OLD, "", None), ["rasipalan.yml"])
        self.assertEqual(W.decide(ist(6, 50), True, None, OLD, OLD, "", None), [])          # posted: nothing
        self.assertEqual(W.decide(ist(8, 35), False, None, OLD, OLD, "", None), ["rasipalan.yml"])
        self.assertEqual(W.decide(ist(8, 45), False, None, OLD, OLD, "", None), [])      # owner 19 Nov: never started after 8:40

    def test_gold_from_9_40_and_afternoon_from_15_40(self):
        self.assertEqual(W.decide(ist(9, 30), True, False, OLD, OLD, "", None), [])
        self.assertEqual(W.decide(ist(9, 45), True, False, OLD, OLD, "", None), ["goldrate.yml"])
        self.assertEqual(W.decide(ist(14, 0), True, True, OLD, OLD, "", None, False), [])
        self.assertEqual(W.decide(ist(15, 45), True, True, OLD, OLD, "", None, False), ["goldrate.yml pm"])
        self.assertEqual(W.decide(ist(15, 45), True, True, OLD, OLD, "", None, True), [])      # afternoon already checked

    def test_never_starts_a_busy_or_recent_job(self):
        self.assertEqual(W.decide(ist(9, 45), True, False, OLD, [("in_progress", ist(9, 35))], "", None), [])
        self.assertEqual(W.decide(ist(9, 45), True, False, OLD, [("completed", ist(9, 20))], "", None), [])      # tried 25 min ago
        self.assertEqual(W.decide(ist(9, 45), True, False, OLD, None, "", None), [])      # GitHub did not answer: never blind

    def test_overdue_round_only(self):
        self.assertEqual(W.decide(ist(14, 0), True, True, OLD, OLD, "pick.yml", [("completed", ist(10, 0))], True), [])
        self.assertEqual(W.decide(ist(14, 30), True, True, OLD, OLD, "pick.yml", [("completed", ist(10, 0))], True), ["pick.yml"])


class Times(unittest.TestCase):
    def test_rasipalan_starts_6_40(self):
        src = (ROOT / "rasipalan" / "rasi_daily.py").read_text(encoding="utf-8")
        self.assertIn('START_AT = os.environ.get("START_AT", "06:40")', src)
        self.assertIn('cron: "5 1 * * *"', (ROOT / ".github/workflows/rasipalan.yml").read_text(encoding="utf-8"))

    def test_gold_pm_schedule(self):
        wf = (ROOT / ".github/workflows/goldrate.yml").read_text(encoding="utf-8")
        self.assertIn('cron: "5 10 * * *"', wf)
        self.assertIn("GOLD_MODE:", wf)


class AfternoonGold(unittest.TestCase):
    def setUp(self):
        import gold_daily
        self.G = gold_daily
        self.am = {"g22": 12470, "g24": 13604, "silver": 185}

    def test_change_detection(self):
        G = self.G
        self.assertFalse(G.pm_changed(self.am, {"g22": 12470, "g24": 13604}, {"silver": 185}))
        self.assertTrue(G.pm_changed(self.am, {"g22": 12400, "g24": 13530}, {"silver": 185}))
        self.assertTrue(G.pm_changed(self.am, None, {"silver": 180}))
        self.assertFalse(G.pm_changed(self.am, None, None))

    def test_slides_and_caption_compare_with_morning(self):
        G = self.G
        r = G.pm_rates([], d.date(2026, 11, 19), self.am, {"g22": 12400, "g24": 13530}, None)
        self.assertEqual((r["g22_prev"], r["kick"], r["vs"]), (12470, "மாலை நிலவரம்", "காலை விலையைவிட"))
        self.assertEqual(r["silver"], 185)
        cap = G.pm_caption(dict(G.PAGES["namakkal"]), d.date(2026, 11, 19), r)
        self.assertIn("மாலை விலை மாற்றம்", cap)
        self.assertIn("₹70 குறைவு", cap)
        self.assertNotIn("இன்றைய தங்கம், வெள்ளி விலை |", cap)      # never mistaken for the morning post

    def test_morning_slide_text_unchanged(self):
        import gold_render as R
        r = {"date": "19 நவம்பர் 2026", "g22": 1, "g24": 1, "g22_prev": 1, "g24_prev": 1, "vs": "நேற்றைய விலையைவிட", "week22": [("1", 1), ("2", 1)]}
        self.assertIn("காலை நிலவரம்", R.slide({"town": "x", "name1": "x", "handle": "h", "logo": "/x.png"}, r, "gold"))
