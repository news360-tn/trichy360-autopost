"""owner 23 Nov: a ready reel posts about 5 minutes after the last one; a temporary Instagram error waits 10 minutes (no manual e-mail)."""
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "poster"))
import post      # noqa: E402


class FastPosting(unittest.TestCase):
    def test_temporary_error_waits_ten_minutes(self):
        d = Path(tempfile.mkdtemp())
        with mock.patch.object(post, "CACHE", d), mock.patch.dict(post.LIMIT, {}, clear=True):
            post.ig_pause("x", RuntimeError("500 temporary"), "retry")
            self.assertEqual(post.ig_pause_kind("x"), "retry")
            self.assertIn("temporary", post.ig_paused("x"))
            until = datetime.fromisoformat(__import__("json").loads((d / "_ig_paused_x.json").read_text())["until"])
            left = (until - datetime.now(timezone.utc)).total_seconds() / 60
            self.assertTrue(4 <= left <= 10.1, left)      # owner 23 Nov: 5 minutes (config ig_retry_wait_min)
            post.ig_pause("x", RuntimeError("blocked"), "block")      # a block is longer and replaces it
            self.assertEqual(post.ig_pause_kind("x"), "block")
            post.ig_pause("x", RuntimeError("500 again"), "retry")      # never shortens the block
            self.assertEqual(post.ig_pause_kind("x"), "block")

    def test_wired_in(self):
        src = (ROOT / "poster" / "post.py").read_text(encoding="utf-8")
        self.assertEqual(src.count('ig_pause(PAGE, e, "retry")'), 2)
        self.assertIn('"" if ig_pause_kind(p) == "retry" else ig_paused(p)', src)
        wf = (ROOT / ".github" / "workflows" / "post.yml").read_text(encoding="utf-8")
        self.assertIn('then sleep 120; else sleep 420; fi', wf)
        import json
        self.assertEqual(json.loads((ROOT / "poster" / "config.json").read_text(encoding="utf-8"))["posting"]["spacing_min"], 5)


if __name__ == "__main__":
    unittest.main()
