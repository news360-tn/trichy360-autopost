"""owner 20 Nov: Facebook gets 15-20 news a day per page (every news, 45 min apart); the 368 pause stays"""
import importlib
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "poster"))


class FacebookLimit(unittest.TestCase):
    def test_settings(self):
        import facebook
        importlib.reload(facebook)
        self.assertEqual(facebook.TOP_PER_DAY, 25)      # owner 21 Nov: every news on Facebook too
        self.assertEqual(facebook.GAP_MIN, 30)      # owner 21 Nov: a sooner news waits
        self.assertFalse(facebook.TOP_ONLY)
        self.assertLess(facebook.TOP_PER_DAY, facebook.REEL_CAP)      # under Facebook's 30 API reels a day
        ok, why = facebook.top_news({"urgent": False, "topic": "education", "weight": -0.5, "best": False})
        self.assertTrue(ok, why)
        self.assertEqual(facebook.PAUSE_HOURS, 2)      # owner 27 Nov: a block with no stated time waits 2 hours


if __name__ == "__main__":
    unittest.main()
