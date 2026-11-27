"""owner 27 Nov evening: captions follow the voice's own word clock (reel/edge_words.py -> lineN.words.json); letter count only
when the clock is missing. Also: the first picture change at 1.2 s and the end card length. No network, no browser."""
import json, sys, tempfile, types, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "reel"))
if "playwright.sync_api" not in sys.modules:      # reel4 only needs the browser in main(); these tests never render
    try:
        import playwright.sync_api      # noqa: F401
    except Exception:
        _pw, _sa = types.ModuleType("playwright"), types.ModuleType("playwright.sync_api")
        _sa.sync_playwright = None
        sys.modules["playwright"], sys.modules["playwright.sync_api"] = _pw, _sa
try:
    import reel4
except BaseException:      # a render dependency is missing on this machine
    reel4 = None

# a real word clock of ta-IN-ValluvarNeural (+12%, +4Hz) for this sentence ("5" is read as "ஐந்து")
CLOCK = {"words": [["ஐந்து", 0.045, 0.39], ["தொகுதி", 0.402, 0.81], ["இடைத்தேர்தலுக்குத்", 0.826, 1.65], ["தடை", 1.663, 1.94],
                   ["கோரிய", 1.953, 2.31], ["வழக்கில்", 2.321, 2.77], ["இன்று", 2.779, 3.05], ["தீர்ப்பு", 3.058, 3.5],
                   ["வழங்கப்படுகிறது", 3.516, 4.3]], "dur": 4.31}
TEXT = "5 தொகுதி இடைத்தேர்தலுக்குத் தடை கோரிய வழக்கில் இன்று தீர்ப்பு வழங்கப்படுகிறது."


@unittest.skipIf(reel4 is None, "reel4 could not be imported")
class CaptionClock(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.work = Path(self.tmp.name)
        (self.work / "line0.words.json").write_text(json.dumps(CLOCK, ensure_ascii=False), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_each_word_at_its_spoken_time(self):
        wt = reel4.voice_word_times(self.work, 0, TEXT, 10.0, 14.31)
        self.assertEqual([w[0] for w in wt], TEXT.split())
        for (w, a, _), sp in zip(wt, CLOCK["words"]):
            self.assertAlmostEqual(a, 10.0 + sp[1] - 0.045, places=2, msg=w)
        self.assertEqual(wt[-1][2], 14.31)

    def test_a_faster_line_is_scaled(self):      # fit_max read the line 1.2x faster
        wt = reel4.voice_word_times(self.work, 0, TEXT, 0.0, 4.31 / 1.2)
        self.assertAlmostEqual(wt[3][1], (1.663 - 0.045) / 1.2, places=2)

    def test_different_word_count_still_in_order(self):
        text = "5 தொகுதி இடைத்தேர்தல் தடை வழக்கு இன்று தீர்ப்பு"
        wt = reel4.voice_word_times(self.work, 0, text, 0.0, 4.31)
        self.assertEqual(len(wt), 7)
        self.assertTrue(all(b[1] > a[1] for a, b in zip(wt, wt[1:])))
        self.assertTrue(all(0.0 <= a <= b <= 4.31 for _, a, b in wt))

    def test_no_clock_means_letter_count(self):
        self.assertIsNone(reel4.voice_word_times(self.work, 1, TEXT, 0.0, 4.0))
        (self.work / "line2.words.json").write_text("not json", encoding="utf-8")
        self.assertIsNone(reel4.voice_word_times(self.work, 2, TEXT, 0.0, 4.0))


@unittest.skipIf(reel4 is None, "reel4 could not be imported")
class FirstCut(unittest.TestCase):
    def test_first_picture_change_at_1_2_s(self):
        if not reel4.views_test_cfg().get("cycle_pictures"):
            self.skipTest("cycle_pictures is off")
        shots = reel4.plan_shots(3, 30.0, [])
        self.assertEqual(shots[0]["b"], reel4.FIRST_CUT_S)
        self.assertEqual(shots[1]["a"], reel4.FIRST_CUT_S)
        self.assertNotEqual(shots[0]["img"], shots[1]["img"])


if __name__ == "__main__":
    unittest.main()
