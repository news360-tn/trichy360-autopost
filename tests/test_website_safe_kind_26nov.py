"""owner 26 Nov: the website gets the story's kind of news (comment_kind) so it shows the same safe line as the social-media source comment."""
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "poster"))
sys.path.insert(0, str(ROOT / "research_free"))
import website      # noqa: E402


class WebsiteSafeKindTest(unittest.TestCase):
    def test_payload_carries_the_kind(self):
        row = {"story_id": "RN-1", "headline_ta": "செய்தி", "_safe_kind": "crime"}
        self.assertEqual(website.payload(row, "")["safe_kind"], "crime")
        self.assertEqual(website.payload({"story_id": "RN-2", "headline_ta": "x"}, "")["safe_kind"], "")

    def test_post_py_sets_it_before_sending(self):
        src = (ROOT / "poster" / "post.py").read_text(encoding="utf-8")
        self.assertIn('row["_safe_kind"] = k["kind"]', src)
        self.assertLess(src.index('row["_safe_kind"]'), src.index("website.send(row, link)"))


if __name__ == "__main__":
    unittest.main()
