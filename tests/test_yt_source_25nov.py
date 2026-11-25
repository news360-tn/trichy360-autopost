"""owner 25 Nov: the Instagram first comment (source + link) is kept and goes at the top of the YouTube description."""
import json, sys, tempfile, unittest
from pathlib import Path
from unittest import mock
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "poster"))
import post      # noqa: E402


class YouTubeSource(unittest.TestCase):
    def test_comment_kept_and_found_by_media_id(self):
        d = Path(tempfile.mkdtemp())
        with mock.patch.object(post, "POSTED_DIR", d), mock.patch.object(post, "combined_mode", return_value=False), \
                mock.patch.object(post, "tries_clear", lambda *a: None):
            post.record_posted("RN-1", {"headline_ta": "செய்தி"}, "https://instagram.com/reel/a", "reel", "M1", "cap")
            self.assertEqual(post.comment_for("M1"), "")
            post.remember_comment("M1", "📰 News Source: Dinamalar https://example.com/n/1")
            self.assertIn("example.com/n/1", post.comment_for("M1"))
            self.assertEqual(post.comment_for("OTHER"), "")

    def test_youtube_uses_it(self):
        src = (ROOT / "poster" / "ytupload.py").read_text(encoding="utf-8")
        self.assertIn("post.comment_for(m.get(\"id\"))", src)


if __name__ == "__main__":
    unittest.main()
