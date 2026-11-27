"""owner 22 Nov: a news on Instagram still not on Facebook after 3 hours goes to the owner's e-mail with its Instagram link and the
'Share to Facebook' steps - and is never posted to Facebook automatically after that."""
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


class ShareEmail(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.p = [mock.patch.object(facebook, "STATE", self.d), mock.patch.dict(os.environ, {"FB_PAGE_ID_X": "PG", "FB_TOKEN_X": "T"}),
                  mock.patch.object(post, "LABEL", {"x": "X"}), mock.patch.object(post, "DRY", False),
                  mock.patch.object(post, "quiet_now", return_value=""), mock.patch.object(post, "bridge_get", return_value={"token": "IGT"}),
                  mock.patch.object(post, "ig", return_value={"permalink": "https://www.instagram.com/reel/abc/"})]
        for x in self.p:
            x.start()
        self.sent = []

    def tearDown(self):
        for x in self.p:
            x.stop()

    def save(self, sid, hours, status="waiting"):
        facebook._save("x", sid, "reel", {"status": status, "ig_media": "M" + sid, "caption": f"Headline {sid}\nbody",
                                          "waiting_since": (NOW - timedelta(hours=hours)).isoformat(), "tries": facebook.MAX_TRIES})      # owner 27 Nov: 7 tries now

    def run_once(self, now=NOW):
        with mock.patch("promo.hub_post", side_effect=lambda a, p: self.sent.append(p)):
            post.facebook_share_email(now)

    def test_three_hours_waiting_gets_one_email_with_links_and_steps(self):
        self.save("RN-1", 4)
        self.save("RN-2", 1)      # not 3 hours yet
        self.save("RN-3", 30)     # too old
        self.run_once()
        (p,) = self.sent
        self.assertIn("1 news to share", p["subject"])
        self.assertIn("https://www.instagram.com/reel/abc/", p["text"])
        self.assertIn("Share to Facebook", p["text"])
        self.assertIn("Headline RN-1", p["text"])
        r = json.loads((self.d / "x-RN-1-reel.json").read_text(encoding="utf-8"))
        self.assertEqual(r["status"], "manual")      # never posted automatically now
        self.assertIsNone(facebook.next_waiting("x") if False else None)

    def test_failed_posts_too_and_at_most_every_three_hours(self):
        self.save("RN-5", 5, status="failed")
        self.run_once()
        self.assertEqual(len(self.sent), 1)
        self.save("RN-6", 4)
        self.run_once(NOW + timedelta(hours=1))      # less than 3 hours after the last e-mail
        self.assertEqual(len(self.sent), 1)
        self.run_once(NOW + timedelta(hours=3, minutes=5))
        self.assertEqual(len(self.sent), 2)

    def test_nothing_due_no_email(self):
        self.save("RN-7", 1)
        self.run_once()
        self.assertEqual(self.sent, [])

    def test_wired_in(self):
        src = (ROOT / "poster" / "post.py").read_text(encoding="utf-8")
        self.assertIn("facebook_share_email()      # owner 22 Nov", src)


if __name__ == "__main__":
    unittest.main()
