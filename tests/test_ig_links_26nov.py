"""owner 26 Nov: the insights job keeps each Instagram post's own link (permalink) so the team dashboard can open the post."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class InsightsPermalinkTest(unittest.TestCase):
    def test_posts_are_asked_for_their_permalink_and_it_is_kept_even_for_final_rows(self):
        src = (ROOT / "poster" / "insights.py").read_text(encoding="utf-8")
        self.assertIn('fields = "id,caption,timestamp,media_product_type,permalink"', src)
        self.assertIn('hist[i["id"]]["permalink"] = i["permalink"]', src)
        # kept after read_row, so a post that is already final (not read again) still gets its link
        self.assertGreater(src.index('hist[i["id"]]["permalink"]'), src.index("row = read_row(i, page, tok"))


if __name__ == "__main__":
    unittest.main()
