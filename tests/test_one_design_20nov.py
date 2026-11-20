"""owner 20 Nov (final): one design on every page - the earlier design, with '📅 date  📰 Source: paper' and the clock branding"""
import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "reel"))


class OneDesign(unittest.TestCase):
    def test_the_earlier_design_is_on(self):
        cfg = json.loads((ROOT / "poster" / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(cfg["reel_design"], "classic")
        import design360
        with mock.patch.dict(os.environ, {"REEL_DESIGN": ""}):
            self.assertFalse(design360.on())

    def test_source_and_date_in_the_header(self):
        src = (ROOT / "reel" / "reel4.py").read_text(encoding="utf-8")
        self.assertIn("head_icon('calendar-days')", src)
        self.assertIn("head_icon('newspaper') + 'Source: '", src)
        self.assertIn("max-width:820px", src)

    def test_clock_branding_still_on(self):
        src = (ROOT / "reel" / "reel4.py").read_text(encoding="utf-8")
        self.assertIn("clock360.add(new_page or build_html(", src)


if __name__ == "__main__":
    unittest.main()
