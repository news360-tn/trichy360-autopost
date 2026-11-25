"""owner 24 Nov: any problem - tried again after 5 minutes (3 times), then after 15 minutes (2 times), then Hold + ONE e-mail.
'The Instagram account is restricted' (code 25 / 2207050) follows the same plan; the 5-minute posting gap is unchanged."""
import json, sys, tempfile, unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "poster"))
import post      # noqa: E402

ERR = ("Instagram 17841473413980585/media: {'message': 'User access is restricted', 'type': 'OAuthException', 'code': 25, "
       "'error_subcode': 2207050, 'is_transient': False, 'error_user_title': 'User is restricted', 'error_user_msg': 'The Instagram account is restricted.'}")


class RetryPlan24Nov(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.p = [mock.patch.object(post, "CACHE", self.tmp), mock.patch.dict(post.LIMIT, {}, clear=True)]
        for x in self.p:
            x.start()
        self.sent = []
        self.b = mock.patch.object(post, "bridge_post", side_effect=lambda a, b: self.sent.append((a, b)))
        self.b.start()

    def tearDown(self):
        self.b.stop()
        for x in self.p:
            x.stop()

    def wait_min(self):
        d = json.loads(post.ig_pause_file(post.PAGE).read_text(encoding="utf-8"))
        return (datetime.fromisoformat(d["until"]) - datetime.now(timezone.utc)).total_seconds() / 60

    def test_restricted_is_not_a_long_pause(self):
        self.assertEqual(post.ig_limit_kind(ERR), "restricted")
        self.assertFalse(post.is_limit_error(ERR))
        self.assertFalse(post.ig_pause_file(post.PAGE).exists())

    def test_5_5_5_15_15_then_hold(self):
        row = {"row": 9, "story_id": "RN-1"}
        for want in (10, 10, 10, 15, 15):      # owner 25 Nov
            post.ig_pause_file(post.PAGE).unlink(missing_ok=True)
            post.report_failure(row, "reel", ERR)
            self.assertAlmostEqual(self.wait_min(), want, delta=0.2)
            self.assertEqual(self.sent, [])      # no Hold, no e-mail yet
        post.report_failure(row, "reel", ERR)      # the 6th failure
        self.assertEqual([a for a, _ in self.sent], ["error"] * 3)      # the sheet holds it at the 3rd report: one e-mail
        self.assertEqual(post._tries_load(), {})

    def test_posted_news_forgets_its_tries(self):
        post.report_failure({"row": 9, "story_id": "RN-2"}, "reel", ERR)
        self.assertIn("RN-2:reel", post._tries_load())
        post.tries_clear("RN-2")
        self.assertEqual(post._tries_load(), {})


if __name__ == "__main__":
    unittest.main()
