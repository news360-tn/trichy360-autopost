"""owner 16 Nov: a skipped round's count is written by the next round; lifestyle columns are not written automatically."""
import datetime, sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research_free"))
import pick, collect      # noqa: E402

T = lambda d, h, m=0: datetime.datetime(2026, 11, d, h, m, tzinfo=pick.IST)


class Catchup(unittest.TestCase):
    def test_normal_round(self):
        self.assertEqual(pick.window_top(T(15, 13, 50), T(15, 17, 38)), 5)
        self.assertEqual(pick.window_top(T(15, 21, 30), T(16, 1, 40)), 2)

    def test_skipped_21_round_is_added(self):      # 15 Nov: 17:38 round, 21:00 skipped, next run 01:57
        self.assertEqual(pick.window_top(T(15, 17, 38), T(16, 1, 57)), 4 + 2)

    def test_late_run_and_second_run_same_round(self):
        self.assertEqual(pick.window_top(T(16, 1, 40), T(16, 4, 59)), 2)      # the 01:00 round ran 4 hours late: still 2
        self.assertEqual(pick.window_top(T(16, 5, 1), T(16, 5, 46)), 5)       # no round time inside: its own count

    def test_capped(self):
        self.assertLessEqual(pick.window_top(T(15, 1, 0), T(16, 0, 30)), pick.CATCHUP_MAX)


class Lifestyle(unittest.TestCase):
    def test_columns_skipped(self):
        for t in ("பகிர்ந்து செய்வதே மகிழ்ச்சி! | ஆண்கள் ஸ்பெஷல்", "ஓரமாக அமரும் காலமல்ல, ஓய்வு காலம்! மனசுக்கு பிடித்ததை செய்யுங்கள்"):
            self.assertTrue(collect.low_interest(t, ""), t)

    def test_news_kept(self):
        for t in ("தீபாவளி சிறப்பு ரயில்கள் இயக்கம்", "புத்தக கொள்முதல் முறைகேடு வழக்கு: 5 அதிகாரிகள் சஸ்பெண்ட்"):
            self.assertEqual(collect.low_interest(t, ""), "", t)
