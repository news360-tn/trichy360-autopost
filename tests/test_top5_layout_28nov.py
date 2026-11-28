"""owner 28 Nov ("top 5 news ... verify and update"): the Top 5 reel goes to Instagram, Facebook and YouTube Shorts as one video, so
its parts sit inside the area that is free on all three (x 48-950, y 100-1600) - nothing under the buttons or the caption."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = (ROOT / "poster" / "top5.py").read_text(encoding="utf-8")


def px(rule, prop):
    """the px value of one property in one CSS rule of the page (the f-string's doubled braces)"""
    body = re.search(re.escape(rule) + r"\{\{(.*?)\}\}", SRC, re.S).group(1)
    return int(re.search(r"(?:^|;)\s*" + prop + r":(-?\d+)px", body).group(1))


class TopFiveLayout(unittest.TestCase):
    def test_headline_clear_of_the_buttons_and_the_caption(self):
        self.assertGreaterEqual(px(".news .txt", "right"), 130)      # x <= 950: the like / comment / share buttons are right of it
        top, lines = px(".news .txt", "top"), 3 * px(".news .hd", "font-size") * 1.3
        self.assertIn("-webkit-line-clamp:3", SRC)      # at most 3 lines
        self.assertLessEqual(top + lines + 12 + 60, 1600)      # the time chip ends above the caption area

    def test_rank_row_is_down_the_left_side(self):      # it was at the very bottom, under the caption on every platform
        self.assertIn("flex-direction:column", re.search(r"\.dots\{\{(.*?)\}\}", SRC, re.S).group(1))
        self.assertNotIn("bottom:70px", SRC)
        top, left = px(".dots", "top"), px(".dots", "left")
        self.assertTrue(48 <= left <= 200 and top >= 440)      # under the rank badge, left of the cover
        self.assertLessEqual(top + 5 * px(".dots b", "height") + 4 * 16, 1000)
        self.assertLess(left + px(".dots b", "width"), 540 - px(".news .cv", "width") // 2)      # never over the cover

    def test_cover_and_opening_inside_the_safe_area(self):
        self.assertGreaterEqual(px(".news .cv", "top"), 285)
        self.assertLessEqual(px(".news .cv", "top") + px(".news .cv", "height"), px(".news .txt", "top"))
        self.assertEqual(px(".news .cv", "width") * 16, px(".news .cv", "height") * 9)      # a reel cover: 9:16
        self.assertLessEqual(3 * px(".th", "width") + 2 * 18, 950 - 130)      # the five small covers of the opening: three in a row, inside x 950
        self.assertIn("align-items:flex-end", re.search(r"\.band\{\{(.*?)\}\}", SRC, re.S).group(1))      # the page name below the top bar

    def test_no_view_counts(self):
        self.assertNotIn("பார்வைகள்", SRC)


if __name__ == "__main__":
    unittest.main()
