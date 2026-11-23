"""owner 23 Nov: reels only on Instagram and Facebook - no stories on any page; a temporary Instagram error waits 5 minutes."""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "poster"))
import facebook      # noqa: E402
import post          # noqa: E402

CFG = json.loads((ROOT / "poster" / "config.json").read_text(encoding="utf-8"))


class ReelsOnly(unittest.TestCase):
    def test_no_instagram_story(self):
        self.assertFalse(CFG["post_stories"])
        with mock.patch.dict(post.CONFIG, {"post_stories": False}):
            self.assertEqual(post.publish_story("T", "file:///r.mp4", "video", None), "")

    def test_no_facebook_story(self):
        self.assertFalse(facebook.FB_STORIES)
        calls = []
        with mock.patch.object(facebook, "creds", return_value=("PG", "T")), \
                mock.patch.object(facebook, "STATE", Path(tempfile.mkdtemp())), \
                mock.patch.object(facebook, "publish_reel", return_value=("v1", "https://fb/v1")), \
                mock.patch.object(facebook, "story_video", side_effect=lambda *a: calls.append(a) or "s1"), \
                mock.patch.object(facebook, "source_comment", return_value=""):
            facebook._attempt("x", "RN-1", "reel", ["file:///r.mp4"], "cap", {}, story=True)
        self.assertEqual(calls, [])      # the reel only

    def test_temporary_error_waits_five_minutes(self):
        self.assertEqual(CFG["ig_retry_wait_min"], 5)
        d = Path(tempfile.mkdtemp())
        with mock.patch.object(post, "CACHE", d), mock.patch.dict(post.CONFIG, {"ig_retry_wait_min": 5}), mock.patch.dict(post.LIMIT, {}, clear=True):
            post.ig_pause("x", RuntimeError("temporary"), "retry")
            until = datetime.fromisoformat(json.loads((d / "_ig_paused_x.json").read_text())["until"])
            left = (until - datetime.now(timezone.utc)).total_seconds() / 60
            self.assertTrue(4 <= left <= 5.1, left)


if __name__ == "__main__":
    unittest.main()
