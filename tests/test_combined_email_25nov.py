"""owner 25 Nov: ONE e-mail per news with its Instagram, Facebook and YouTube links; Instagram's own e-mail is off."""
import json, sys, tempfile, unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "poster"))
import post      # noqa: E402
import combined_email as ce      # noqa: E402
import promo      # noqa: E402
import ytupload      # noqa: E402

PG = next(iter(post.LABEL))
NOW = datetime.now(timezone.utc).replace(microsecond=0)


class Combined(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        (self.d / "posted").mkdir()
        (self.d / "fb").mkdir()
        self.sent = []
        self.p = [mock.patch.object(post, "POSTED_DIR", self.d / "posted"), mock.patch.object(post, "DRY", False),
                  mock.patch.dict(post.CONFIG, {"posted_email": "combined"}),
                  mock.patch.object(ce, "HERE", self.d), mock.patch.object(ce, "STATE_FILE", self.d / "fb" / "_combined_email.json"),
                  mock.patch.object(promo, "enabled", return_value=True),
                  mock.patch.object(promo, "hub_post", side_effect=lambda a, b: self.sent.append((a, b)) or {"ok": True}),
                  mock.patch.object(ce, "sent_today_all", side_effect=lambda post_, day, st: sum(1 for v in st["sent"].values() if v.get("how") == "sent")),
                  mock.patch.object(post, "log", lambda *a: None)]
        for x in self.p:
            x.start()
        (self.d / "fb_posted").mkdir()

    def tearDown(self):
        for x in self.p:
            x.stop()

    def rec(self, sid, minutes_ago, combined=True):
        t = NOW - timedelta(minutes=minutes_ago)
        r = {"page": PG, "story": sid, "kind": "reel", "headline": "செய்தி " + sid, "link": f"https://www.instagram.com/reel/{sid}/",
             "at": t.isoformat(), "media_id": "m" + sid, "caption": "cap"}
        if combined:
            r["combined"] = True
        (self.d / "posted" / f"{t:%Y%m%d-%H%M%S}-{PG}-{sid}.json").write_text(json.dumps(r, ensure_ascii=False))

    def fb(self, sid, status="posted"):
        (self.d / "fb_posted" / f"{PG}-{sid}-reel.json").write_text(json.dumps(
            {"status": status, "link": f"https://www.facebook.com/reel/{sid}/" if status == "posted" else "", "page": PG}))

    def yt(self, uploads, keys=True, why=""):
        return [mock.patch.object(ytupload, "keys", return_value=("a", "b", "c") if keys else None),
                mock.patch.object(ytupload, "_state", return_value={"uploads": uploads}),
                mock.patch.object(ytupload, "due", return_value=why)]

    def go(self, uploads=(), keys=True, why=""):
        ps = self.yt(list(uploads), keys, why)
        for x in ps:
            x.start()
        try:
            return ce.run(post, NOW)
        finally:
            for x in ps:
                x.stop()

    def test_instagram_post_has_no_own_email_in_combined_mode(self):
        self.assertTrue(post.combined_mode())
        self.assertTrue(post.posted_quiet())

    def test_waits_for_facebook_and_youtube(self):
        self.rec("RN-1", 10)
        self.assertEqual(self.go(), 0)      # nothing on Facebook / YouTube yet, only 10 minutes
        self.fb("RN-1")
        self.assertEqual(self.go(), 0)      # YouTube not yet
        self.assertEqual(self.go([{"ig": "mRN-1", "youtube": "YT1"}]), 1)
        a, b = self.sent[0]
        self.assertEqual(a, "digest")
        self.assertIn("https://www.instagram.com/reel/RN-1/", b["text"])
        self.assertIn("https://www.facebook.com/reel/RN-1/", b["text"])
        self.assertIn("https://youtube.com/shorts/YT1", b["text"])
        self.assertEqual(self.go([{"ig": "mRN-1", "youtube": "YT1"}]), 0)      # never twice

    def test_sent_after_45_minutes_with_what_is_done(self):
        self.rec("RN-2", 50)
        self.assertEqual(self.go(), 1)
        self.assertIn("not posted yet", self.sent[0][1]["text"])
        self.assertIn("not uploaded yet", self.sent[0][1]["text"])

    def test_youtube_not_connected_or_limit_does_not_wait(self):
        self.rec("RN-3", 5)
        self.fb("RN-3")
        self.assertEqual(self.go(keys=False), 1)
        self.rec("RN-4", 5)
        self.fb("RN-4")
        self.assertEqual(self.go(why="30 uploads today - the day's limit"), 1)

    def test_old_posts_are_not_emailed_again(self):
        self.rec("RN-5", 50, combined=False)      # posted before the switch: it had its own e-mail
        self.assertEqual(self.go(), 0)

    def test_daily_limit_60(self):
        with mock.patch.object(ce, "sent_today_all", return_value=60):
            self.rec("RN-6", 50)
            self.assertEqual(self.go(), 0)
        self.assertEqual(self.sent, [])

    def test_failed_email_tried_3_times(self):
        self.rec("RN-7", 50)
        with mock.patch.object(promo, "hub_post", side_effect=RuntimeError("quota")):
            for _ in range(4):
                self.go()
        st = json.loads((self.d / "fb" / "_combined_email.json").read_text())
        self.assertEqual(st["sent"][f"{PG}:RN-7"]["how"], "failed")

    def test_without_promo_hub_old_email_stays(self):
        with mock.patch.object(promo, "enabled", return_value=False):
            self.assertFalse(post.combined_mode())


if __name__ == "__main__":
    unittest.main()
