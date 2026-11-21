"""owner 21 Nov: every news that is on Instagram also goes to Facebook - a news that comes within the gap waits and is posted later
(never dropped); gap 30 min, up to 25 a day."""
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


class Queue(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.p = [mock.patch.object(facebook, "STATE", self.d),
                  mock.patch.dict(os.environ, {"FB_PAGE_ID_X": "PG", "FB_TOKEN_X": "T"})]
        for x in self.p:
            x.start()

    def tearDown(self):
        for x in self.p:
            x.stop()

    def rec(self, sid, **kw):
        return json.loads((self.d / f"x-{sid}-reel.json").read_text(encoding="utf-8")) if (self.d / f"x-{sid}-reel.json").exists() else kw

    def test_settings(self):
        self.assertEqual((facebook.GAP_MIN, facebook.TOP_PER_DAY), (30, 25))

    def test_a_news_within_the_gap_waits(self):
        facebook._save("x", "RN-1", "reel", {"status": "posted", "posted_at": datetime.now(timezone.utc).isoformat()})
        with mock.patch.object(facebook, "_attempt") as att:
            self.assertEqual(facebook.share("x", "RN-2", "reel", ["file:///r.mp4"], "cap", "#X360", ig_media="M2"), "")
        att.assert_not_called()
        r = self.rec("RN-2")
        self.assertEqual((r["status"], r["ig_media"]), ("waiting", "M2"))
        self.assertIn("less than 30 min", r["why"])

    def test_the_oldest_waiting_news_goes_first_and_too_old_ones_are_dropped(self):
        now = datetime.now(timezone.utc)
        for sid, h in (("RN-1", 30), ("RN-2", 3), ("RN-3", 1)):
            facebook._save("x", sid, "reel", {"status": "waiting", "ig_media": "M" + sid, "waiting_since": (now - timedelta(hours=h)).isoformat()})
        self.assertEqual(facebook.next_waiting("x")["story"], "RN-2")
        self.assertEqual(self.rec("RN-1")["status"], "skipped")      # more than 24 h old

    def test_catch_up_sends_the_instagram_video_when_the_gap_is_over(self):
        facebook._save("x", "RN-5", "reel", {"status": "waiting", "ig_media": "M5", "caption": "cap", "link": "https://a/1",
                                             "comment": "src", "with_story": True,
                                             "waiting_since": datetime.now(timezone.utc).isoformat()})
        f = self.d / "v.mp4"
        f.write_bytes(b"0" * 100)
        with mock.patch.object(post, "LABEL", {"x": "X"}), mock.patch.object(post, "DRY", False), \
                mock.patch.object(post, "quiet_now", return_value=""), mock.patch.object(facebook, "gate", return_value=""), \
                mock.patch.object(post, "bridge_get", return_value={"token": "IGT"}), \
                mock.patch.object(post, "ig", return_value={"media_url": "https://cdn/v.mp4"}), \
                mock.patch.object(post.localmedia, "download", return_value=str(f)), mock.patch.object(facebook, "_attempt") as att:
            post.facebook_catchup()
        att.assert_called_once()
        a = att.call_args.args
        self.assertEqual((a[0], a[1], a[4]), ("x", "RN-5", "cap"))
        self.assertTrue(a[3][0].startswith("file://"))      # the file - no Cloudinary

    def test_catch_up_waits_while_the_gap_is_not_over(self):
        facebook._save("x", "RN-6", "reel", {"status": "waiting", "ig_media": "M6", "waiting_since": datetime.now(timezone.utc).isoformat()})
        with mock.patch.object(post, "LABEL", {"x": "X"}), mock.patch.object(post, "DRY", False), \
                mock.patch.object(post, "quiet_now", return_value=""), \
                mock.patch.object(facebook, "gate", return_value="less than 30 min since the last Facebook post"), \
                mock.patch.object(facebook, "_attempt") as att:
            post.facebook_catchup()
        att.assert_not_called()
        self.assertEqual(self.rec("RN-6")["status"], "waiting")

    def test_wired_in(self):
        src = (ROOT / "poster" / "post.py").read_text(encoding="utf-8")
        self.assertIn("ig_media=mid", src)
        self.assertIn("facebook_catchup()      # owner 21 Nov", src)
        self.assertIn("git add -f poster/fb_posted;", (ROOT / ".github" / "workflows" / "post.yml").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
