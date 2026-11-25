"""owner 25 Nov (option B): a separate e-mail per post, at most 60 a day for ALL 7 pages together (one Gmail account)."""
import json, sys, tempfile, unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "poster"))
import post      # noqa: E402

NOW = datetime(2026, 11, 25, 10, 0, tzinfo=timezone.utc)      # 15:30 IST


class Resp:
    def __init__(self, names, code=200):
        self.status_code = code
        self._j = [{"name": n} for n in names]

    def json(self):
        return self._j


class EmailCap(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        post._EMAILS.clear()
        self.p = [mock.patch.object(post, "POSTED_DIR", self.d), mock.patch.object(post, "DRY", False),
                  mock.patch.dict(post.CONFIG, {"posted_email": "each"}),
                  mock.patch.dict("os.environ", {"GITHUB_REPOSITORY": "news360-tn/salem360-autopost"})]
        for x in self.p:
            x.start()

    def tearDown(self):
        for x in self.p:
            x.stop()
        post._EMAILS.clear()

    def own(self, n, stamp="20261125-090000"):
        for i in range(n):
            (self.d / f"{stamp}-salem-RN-{i}.json").write_text("{}")

    def test_counts_all_pages_for_the_ist_day(self):
        self.own(3)
        (self.d / "20261124-170000-salem-RN-x.json").write_text("{}")      # 22:30 IST yesterday - not today
        (self.d / "20261124-190000-salem-RN-y.json").write_text("{}")      # 00:30 IST today
        others = ["20261125-080000-erode-RN-1.json", "20261123-080000-erode-RN-2.json"]
        with mock.patch.object(post.requests, "get", return_value=Resp(others)) as g:
            self.assertEqual(post.posts_today_all_pages(NOW), 4 + 6)      # 4 own + 1 on each of the 6 other repos
        urls = [c.args[0] for c in g.call_args_list]
        self.assertEqual(len(urls), 6)
        self.assertFalse(any("salem360" in u for u in urls))      # its own folder is read locally

    def test_under_the_limit_each_post_has_its_email(self):
        with mock.patch.object(post, "posts_today_all_pages", return_value=60):
            self.assertFalse(post.posted_quiet())      # the 60th post still has its e-mail

    def test_over_the_limit_quiet(self):
        with mock.patch.object(post, "posts_today_all_pages", return_value=61):
            self.assertTrue(post.posted_quiet())

    def test_unreadable_other_pages_count_zero(self):
        self.own(2)
        with mock.patch.object(post.requests, "get", side_effect=OSError("down")):
            self.assertEqual(post.posts_today_all_pages(NOW), 2)

    def test_all_posted_calls_pass_quiet(self):
        src = (ROOT / "poster" / "post.py").read_text(encoding="utf-8")
        import re
        calls = re.findall(r'bridge_post\("posted", \{(.*?)\}\)', src, re.S)
        real = [c for c in calls if '"dry_run": True' not in c]
        self.assertTrue(real)
        for c in real:
            self.assertIn('"quiet"', c)


if __name__ == "__main__":
    unittest.main()
