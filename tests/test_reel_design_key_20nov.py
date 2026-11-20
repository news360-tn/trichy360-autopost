"""20 Nov: poster/config.json reel_design picks the reel builder for the posting job - it must be "v4" (reel4.py).
It was overwritten by mistake for 2 hours (17:15-19:10 IST) and the posting job fell back to reel3.py."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class ReelDesignKey(unittest.TestCase):
    def test_posting_job_uses_reel4(self):
        cfg = json.loads((ROOT / "poster" / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(cfg.get("reel_design"), "v4")
        src = (ROOT / "poster" / "post.py").read_text(encoding="utf-8")
        self.assertIn('design = "reel4.py" if CONFIG.get("reel_design") == "v4" else "reel3.py"', src)

    def test_cached_reels_made_again(self):
        self.assertIn('"reel-r7"', (ROOT / "poster" / "post.py").read_text(encoding="utf-8"))
