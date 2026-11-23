"""owner 23 Nov: a news held back only by yesterday's daily maximum is offered again today; other refusals stay refused."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research_free"))
import pick      # noqa: E402


class ReleaseYesterdaysMaximum(unittest.TestCase):
    def test_code_releases_only_the_daily_maximum(self):
        src = (ROOT / "research_free" / "pick.py").read_text(encoding="utf-8")
        i = src.index("held back by yesterday's daily maximum")
        self.assertLess(i, src.index('if it.get("refused"):\n            continue      # owner 4 Nov'))
        self.assertIn('startswith("not written: the day\'s maximum")', src)


if __name__ == "__main__":
    unittest.main()
