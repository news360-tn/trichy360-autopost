"""owner 24 Nov: a news refused by Facebook's 24-hour reel limit WAITS (posted later or e-mailed) - never silently skipped."""
import sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent


class FbCapWait24Nov(unittest.TestCase):
    def test_wired(self):
        fb = (ROOT / "poster" / "facebook.py").read_text(encoding="utf-8")
        self.assertIn('"why": f"Facebook 24-hour reel limit {REEL_CAP} reached", "ig_media": ig_media', fb)
        post = (ROOT / "poster" / "post.py").read_text(encoding="utf-8")
        self.assertIn('stuck and (d.get("ig_media") or d.get("ig_link"))', post)
        self.assertIn('link = link or d.get("ig_link", "")', post)


if __name__ == "__main__":
    unittest.main()
