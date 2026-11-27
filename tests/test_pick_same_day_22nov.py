"""owner 22 Nov: every news of a round is written (30 of today's news a day + yesterday's pending + urgent news after the 30)."""
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research_free"))
import pick      # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))


class PickSameDay(unittest.TestCase):
    def test_same_day(self):
        ref = datetime(2026, 11, 22, 4, 0, tzinfo=IST)
        self.assertFalse(pick.same_day(datetime(2026, 11, 21, 23, 50, tzinfo=IST), ref))
        self.assertTrue(pick.same_day(datetime(2026, 11, 22, 0, 10, tzinfo=IST), ref))
        self.assertTrue(pick.same_day(None, ref))

    def test_defaults_on(self):
        self.assertFalse(pick.SAME_DAY)      # owner 22 Nov evening: yesterday's pending news is listed and written too
        self.assertTrue(pick.PICK_ALL)
        src = (ROOT / "research_free" / "pick.py").read_text(encoding="utf-8")
        self.assertIn("pick_ = power + rest\n", src)
        wf = (ROOT / ".github" / "workflows" / "pick.yml").read_text(encoding="utf-8")
        self.assertIn('DAILY_CAP: "30"', wf)
        self.assertIn('cron: "30 0,2,4,6,8,10,12,14,16,18,20,22 * * *"', wf)      # owner 27 Nov: every 2 hours (22:00 IST included)


if __name__ == "__main__":
    unittest.main()
