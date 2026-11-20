"""owner 20 Nov: a reel with no picture never shows the page logo - a designed background coloured by the kind of news"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "poster"))

import newsbg      # noqa: E402


class NoPictureBackground(unittest.TestCase):
    def test_theme(self):
        self.assertEqual(newsbg.theme({"category": "மின் தடை"}), "power")
        self.assertEqual(newsbg.theme({"headline_ta": "நாளை கனமழை எச்சரிக்கை"}), "rain")
        self.assertEqual(newsbg.theme({"headline_ta": "சாலை விபத்தில் இருவர் காயம்"}), "alert")
        self.assertEqual(newsbg.theme({"headline_ta": "இசை நிகழ்ச்சி"}), "news")
        self.assertEqual(newsbg.theme(None), "news")

    def test_make(self):
        from PIL import Image
        d = Path(tempfile.mkdtemp())
        a = newsbg.make({"story_id": "RN-1", "category": "மின் தடை"}, d / "a.jpg")
        b = newsbg.make({"story_id": "RN-2", "category": "மின் தடை"}, d / "b.jpg")
        self.assertEqual(Image.open(a).size, (1080, 1920))
        self.assertNotEqual(a.read_bytes(), b.read_bytes())      # each story its own variation

    def test_no_logo(self):
        src = (ROOT / "poster" / "post.py").read_text(encoding="utf-8")
        body = src.split("def plain_background(", 1)[1].split("\ndef ", 1)[0]
        self.assertNotIn("LOGO", body)
        self.assertIn("newsbg.make(row,", body)
        self.assertIn("plain_background(work, ", src.split("def fetch_images", 1)[1].split("\ndef ", 1)[0])


if __name__ == "__main__":
    unittest.main()
