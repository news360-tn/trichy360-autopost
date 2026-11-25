"""owner 21 Nov: every posted news leaves a tiny record (poster/posted/) and ONE report e-mail for all 8 pages goes out 4 times a day
(news360 posted_report.py; the watchdog starts a skipped report)."""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "poster"))
import post          # noqa: E402
import watchdog as W      # noqa: E402


class PostedRecord(unittest.TestCase):
    def test_a_posted_news_leaves_its_record_and_old_ones_go(self):
        d = Path(tempfile.mkdtemp())
        (d / "20200101-000000-x-RN-1.json").write_text("{}", encoding="utf-8")
        with mock.patch.object(post, "POSTED_DIR", d), mock.patch.object(post, "PAGE", "x"):
            post.record_posted("RN-9", {"headline_ta": "சாலை பணி"}, "https://instagram.com/reel/x")
        files = sorted(f.name for f in d.glob("*.json"))
        self.assertEqual(len(files), 1)
        self.assertRegex(files[0], r"^\d{8}-\d{6}-x-RN-9\.json$")
        rec = json.loads((d / files[0]).read_text(encoding="utf-8"))
        self.assertEqual((rec["page"], rec["story"], rec["headline"], rec["link"]), ("x", "RN-9", "சாலை பணி", "https://instagram.com/reel/x"))

    def test_both_reel_paths_record_it(self):
        src = (ROOT / "poster" / "post.py").read_text(encoding="utf-8")
        self.assertIn('log("reel posted", sid, link)\n                record_posted(sid, row, link, "reel", mid, caption)', src)
        self.assertIn('log("ready reel posted", sid, link)\n        record_posted(sid, row, link, "ready reel", mid, caption)', src)
        wf = (ROOT / ".github" / "workflows" / "post.yml").read_text(encoding="utf-8")
        self.assertIn("git add -f poster/posted", wf)

    def test_a_skipped_report_is_started_by_the_watchdog(self):
        at = lambda h, m: datetime(2026, 11, 21, h, m, tzinfo=W.IST)
        old = [("completed", at(9, 2))]
        self.assertFalse(W.report_due(at(13, 10), old))      # not 25 minutes late yet
        self.assertTrue(W.report_due(at(13, 30), old))
        self.assertFalse(W.report_due(at(13, 30), [("completed", at(13, 3))]))      # it ran
        self.assertFalse(W.report_due(at(16, 0), old))      # too late - the 6 PM one comes next
        self.assertFalse(W.report_due(at(13, 30), None))      # the repository has no report
        self.assertIn("posted_report.yml", W.decide(at(18, 40), True, True, [], [], "", None, True, rep_runs=old))


@unittest.skipUnless((ROOT / "poster" / "posted_report.py").exists(), "the report runs in news360-autopost")
class Report(unittest.TestCase):
    def setUp(self):
        import posted_report
        self.R = posted_report
        self.now = datetime(2026, 11, 21, 12, 30, tzinfo=timezone.utc)      # 6 PM IST

    def test_window_starts_at_the_last_report(self):
        d = Path(tempfile.mkdtemp()) / "s.json"
        with mock.patch.object(self.R, "STATE", d):
            self.assertEqual(self.R.window(self.now)[0], self.now - timedelta(hours=4))      # first report: last 4 hours
            d.write_text(json.dumps({"last": (self.now - timedelta(hours=5)).isoformat()}), encoding="utf-8")
            self.assertEqual(self.R.window(self.now), (self.now - timedelta(hours=5), self.now))

    def test_posted_news_of_the_window_are_read(self):
        names = ["20261121-070000-salem-RN-1.json", "20261121-100000-salem-RN-2.json", "20261121-123500-salem-RN-3.json",
                 "20261120-200000-salem-RN-0.json"]
        recs = {n: json.dumps({"page": "salem", "story": n.split("-", 3)[3][:-5], "at": "x"}) for n in names}
        with mock.patch.object(self.R, "api", return_value=[{"name": n} for n in names]), \
                mock.patch.object(self.R, "raw", side_effect=lambda repo, path: recs[path.split("/")[-1]]):
            got, today = self.R.posted_records("salem360-autopost", self.now - timedelta(hours=4), self.now,
                                               datetime(2026, 11, 21, 0, 0, tzinfo=self.R.IST))
        self.assertEqual([r["story"] for r in got], ["RN-2"])      # the window is 08:30-12:30 UTC: only 10:00 is in it
        self.assertEqual(today, {"salem": 3})      # 20 Nov 20:00 UTC (01:30 IST), 07:00 and 10:00 UTC - 12:35 is after the report

    def test_the_check_says_ready_waiting_and_paused(self):
        check = ("17:15:33 12 stories in the queue, ready to post: 3\n"
                 "17:15:33 Instagram's limit on new posts (too many made in 24 h) on trichy - paused until 2026-11-21T17:38 UTC\n"
                 "17:15:34    RN-109 waits: Instagram's 24-hour post limit is (almost) used on ['trichy']\n"
                 "17:15:34    RN-108 skipped: already on Instagram ['trichy']\n")
        with mock.patch.object(self.R, "raw", return_value=check):
            st = self.R.check_status("trichy360-autopost", ("trichy",))
        self.assertEqual(st["ready"], 2)      # the one already on Instagram is not counted
        self.assertIn("paused until 11:08 PM", st["paused"]["trichy"])
        self.assertEqual(list(st["waits"].values()), [1])

    def test_one_email_for_all_pages(self):
        pages = [{"page": "salem", "label": "Salem 360", "posted": [{"at": "2026-11-21T10:00:00+00:00", "headline": "செய்தி",
                                                                      "link": "https://instagram.com/reel/a", "story": "RN-2"}],
                  "today": 5, "ready": 1, "waits": {}, "quota": "", "problems": [], "gold": "posted", "rasipalan": "posted", "shared": False},
                 {"page": "trichy", "label": "Trichy 360", "posted": [], "today": 0, "ready": 2, "waits": {}, "quota": "",
                  "problems": ["Instagram's limit on new posts - paused until 11:08 PM"], "gold": "not yet", "rasipalan": "not yet",
                  "shared": False}]
        subject, text, html_body = self.R.email(self.now - timedelta(hours=4), self.now, pages)
        self.assertIn("1 news posted", subject)
        self.assertIn("1 problem", subject)
        self.assertIn("https://instagram.com/reel/a", html_body)
        self.assertIn("paused until 11:08 PM", html_body)
        self.assertIn("Trichy 360: 0 posted now", text)

    def test_four_times_a_day(self):
        wf = (ROOT / ".github" / "workflows" / "posted_report.yml").read_text(encoding="utf-8")
        for c in ("30 3 * * *", "30 7 * * *", "30 12 * * *", "30 16 * * *"):
            self.assertIn(c, wf)


if __name__ == "__main__":
    unittest.main()
