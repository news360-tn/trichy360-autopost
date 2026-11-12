"""owner 12 Nov: the Salem reel ended with 'Follow Coimbatore Three Sixty' - the spoken follow line must name THIS page."""
import re, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class SpokenFollowLine(unittest.TestCase):
    def test_outro_names_this_page(self):
        src = (ROOT / "reel" / "reel3.py").read_text(encoding="utf-8")
        line = re.search(r'^OUTRO_EN = "([^"]+)"', src, re.M).group(1)
        self.assertIn("Trichy Three Sixty", line)
        for other in ("Coimbatore", "Namakkal", "Rasipuram", "Salem", "Erode", "Tiruppur", "Trichy", "Karur"):
            if other != "Trichy":
                self.assertNotIn(other, line)


if __name__ == "__main__":
    unittest.main()
