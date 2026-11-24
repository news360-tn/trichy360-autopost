"""owner 24 Nov: a Dinamalar article dated at its print time but listed hours later is offered once (it was always
'published before this window' and never posted - Tiruppur 0 news on 24 Nov)."""
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent


class LateListed24Nov(unittest.TestCase):
    def test_wired(self):
        src = (ROOT / "research_free" / "pick.py").read_text(encoding="utf-8")
        i = src.index('item["late_listed"] = True')
        block = src[i - 700:i + 300]
        self.assertIn("(t_end - pt).total_seconds() < LEFT_HOURS * 3600", block)
        self.assertIn('reasons["published before this window"]', block)      # older than LEFT_HOURS: still skipped
        self.assertLess(src.index("if pid(it[\"url\"]) in pool:"), i)      # never offered twice (the pool is checked first)


if __name__ == "__main__":
    unittest.main()
