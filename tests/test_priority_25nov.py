"""owner 25 Nov: posting order = power cut / shutdown first, then High, then the topic this page's insights rank best, then oldest."""
import sys, unittest
from pathlib import Path
from unittest import mock
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "poster"))
import post      # noqa: E402


def row(sid, head, imp="Medium", age=1):
    return {"story_id": sid, "headline_ta": head, "importance": imp, "_age": age}


class Priority(unittest.TestCase):
    def order(self, rows, weights):
        post.insight_weight.__defaults__[0].clear()
        post.insight_weight.__defaults__[0].update({"weights": weights})
        sys.path.insert(0, str(ROOT / "research_free"))
        import learned
        post.insight_weight.__defaults__[0]["learned"] = learned
        with mock.patch.object(post, "ready", return_value=True), mock.patch.object(post, "set_started", return_value=True), \
                mock.patch.object(post, "is_shutdown", return_value=False), \
                mock.patch.object(post, "age_hours", side_effect=lambda r, *a, **k: r["_age"]):
            out = [r["story_id"] for r in post.pick_all(rows)]
        post.insight_weight.__defaults__[0].clear()
        return out

    def test_power_cut_first_then_high_then_insights(self):
        rows = [row("civic", "சாலை பணி தொடக்கம்", age=9), row("crime", "நகை திருட்டு: இருவர் கைது", age=1),
                row("power", "நாளை மின் தடை பகுதிகள்", "Low", age=0), row("high", "பள்ளி விடுமுறை அறிவிப்பு", "High", age=2),
                row("accident", "பைக் விபத்து: ஒருவர் பலி", age=3)]
        got = self.order(rows, {"crime": 1.5, "accident": 0.4, "civic": -0.5, "education": -0.4})
        self.assertEqual(got, ["power", "high", "crime", "accident", "civic"])

    def test_same_topic_oldest_first(self):
        rows = [row("new", "கொலை வழக்கு கைது", age=1), row("old", "திருட்டு கைது", age=5)]
        self.assertEqual(self.order(rows, {"crime": 1.0}), ["old", "new"])

    def test_unknown_insights_keeps_the_old_order(self):
        rows = [row("low", "கபடி போட்டி", "Low", age=9), row("med", "கோயில் விழா", "Medium", age=1)]
        self.assertEqual(self.order(rows, {}), ["med", "low"])


if __name__ == "__main__":
    unittest.main()
