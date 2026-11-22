"""owner 22 Nov: a news a page cannot post (Instagram paused / limit, or ready 3+ hours) goes to the owner's e-mail - one e-mail per news
with the reel attached, the caption with hashtags and the first comment - so the owner posts it by hand."""
import base64
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

NOW = datetime(2026, 11, 22, 6, 0, tzinfo=timezone.utc)      # 11:30 IST
ROW = {"story_id": "RN-9", "headline_ta": "சாலை பணி", "source": "https://example.com/n/9"}


class ManualPost(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.p = [mock.patch.object(post, "MANUAL_FILE", self.d / "m.json"), mock.patch.object(post, "DRY", False),
                  mock.patch.object(post, "PREBUILD", ""), mock.patch.object(post, "quiet_now", return_value=""),
                  mock.patch.object(post, "pick_all", return_value=[ROW]), mock.patch.object(post, "pages_of", return_value=["x"]),
                  mock.patch.object(post, "page_done", return_value=False), mock.patch.dict(post.LIMIT, {}, clear=True)]
        for x in self.p:
            x.start()

    def tearDown(self):
        for x in self.p:
            x.stop()

    def test_a_paused_page_sends_its_news_once(self):
        with mock.patch.object(post, "ig_paused", return_value="Instagram blocked publishing on x - paused until 06:14 UTC"):
            self.assertEqual(post.manual_due([ROW], set(), NOW), [("RN-9", "x")])
            self.assertEqual(post.manual_due([ROW], set(), NOW + timedelta(minutes=10)), [])      # its e-mail job is running

    def test_three_hours_ready_then_e_mail(self):
        with mock.patch.object(post, "ig_paused", return_value=""):
            self.assertEqual(post.manual_due([ROW], set(), NOW), [])      # first seen now
            self.assertEqual(post.manual_due([ROW], set(), NOW + timedelta(hours=2)), [])
            self.assertEqual(post.manual_due([ROW], set(), NOW + timedelta(hours=3, minutes=1)), [("RN-9", "x")])
            self.assertEqual(post.manual_due([ROW], {"RN-9"}, NOW + timedelta(hours=5)), [])      # being posted now

    def test_the_e_mail_has_the_video_caption_and_first_comment(self):
        f = self.d / "r.mp4"
        f.write_bytes(b"0123")
        sent = []
        with mock.patch.object(post, "PAGE", "trichy"), mock.patch.object(post.localmedia, "get", return_value=str(f)), \
                mock.patch.object(post, "source_comment", return_value="📰 Source: Dinamalar"), \
                mock.patch.dict(post.CONFIG, {"first_comment": True}), \
                mock.patch("promo.hub_post", side_effect=lambda a, p: sent.append((a, p))):
            self.assertEqual(post.manual_email(ROW, "RN-9", {"reel": "file:///r.mp4"}, "Caption text #Trichy360"), [("manual", "RN-9")])
        (action, p), = sent
        self.assertEqual(action, "digest")
        self.assertIn("[Trichy 360 MANUAL POST] RN-9", p["subject"])
        self.assertIn("Caption text #Trichy360", p["text"])
        self.assertIn("📰 Source: Dinamalar", p["text"])
        self.assertEqual(base64.b64decode(p["attachment"]["data"]), b"0123")
        st = json.loads((self.d / "m.json").read_text(encoding="utf-8"))
        self.assertTrue(st["trichy:RN-9"]["sent"])
        with mock.patch.object(post, "ig_paused", return_value="paused"), mock.patch.object(post, "pages_of", return_value=["trichy"]):
            self.assertEqual(post.manual_due([ROW], set(), NOW), [])      # sent once - never again

    def test_wired_in(self):
        src = (ROOT / "poster" / "post.py").read_text(encoding="utf-8")
        self.assertIn("return manual_email(row, sid, media, caption)", src)
        self.assertIn('if limit_reached(pg) and not MANUAL:', src)
        wf = (ROOT / ".github" / "workflows" / "post.yml").read_text(encoding="utf-8")
        self.assertIn("MANUAL: ${{ matrix.manual", wf)
        self.assertIn("git add -f poster/manual_sent.json", wf)


if __name__ == "__main__":
    unittest.main()
