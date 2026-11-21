"""owner 21 Nov: Instagram 'action is blocked' (2207051, Trichy) pauses that page's posting for hours - news waits, never retried every run"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "poster"))
import post      # noqa: E402

ERR = RuntimeError("Instagram 1/media_publish: {'message': 'Application request limit reached', 'type': 'OAuthException', "
                   "'is_transient': False, 'code': 4, 'error_subcode': 2207051, 'error_user_title': 'action is blocked'}")


class InstagramBlock(unittest.TestCase):
    def test_block_waits_and_pauses(self):
        with mock.patch.object(post, "CACHE", Path(tempfile.mkdtemp())), mock.patch.object(post, "PAGE", "x"):
            self.assertTrue(post.is_limit_error(ERR))      # waits like the daily limit, never marked failed
            self.assertIn("paused until", post.ig_paused("x"))
            post.LIMIT.pop("x", None)
            self.assertTrue(post.limit_reached("x"))      # later runs hold the page's news
            post.LIMIT.pop("x", None)
            self.assertEqual(post.ig_paused("y"), "")

    def test_old_pause_ends(self):
        with mock.patch.object(post, "CACHE", Path(tempfile.mkdtemp())):
            post.ig_pause_file("x").write_text(json.dumps({"until": "2020-01-01T00:00:00+00:00"}))
            self.assertEqual(post.ig_paused("x"), "")

    def test_setting(self):
        cfg = json.loads((ROOT / "poster" / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(cfg["ig_block_pause_hours"], 6)


if __name__ == "__main__":
    unittest.main()
