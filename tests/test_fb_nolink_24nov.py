"""owner 24 Nov: the Facebook post text never carries an outside link (less reach); the paper's name and date stay, the link is in the
first comment."""
import sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "poster"))
import facebook      # noqa: E402


class FbNoLink24Nov(unittest.TestCase):
    def test_no_url(self):
        cap = "செய்தி\n\n📰 Source: தினமணி (24 நவம்பர் 2026): https://www.dinamani.com/x/y\n\n#A #B #Page360"
        out = facebook.fb_caption(cap, "#Page360")
        self.assertNotIn("http", out)
        self.assertIn("📰 Source: தினமணி (24 நவம்பர் 2026)", out)
        self.assertTrue(out.endswith("#Page360"))


if __name__ == "__main__":
    unittest.main()
