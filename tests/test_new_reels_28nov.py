"""owner 28 Nov (approved after the samples): the parrot rasipalan on every page, the evening top 5 on every page, the map-zoom opening
on Trichy only. These check the text parts (the video parts are made on GitHub)."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "rasipalan"))
sys.path.insert(0, str(ROOT / "goldrate"))
sys.path.insert(0, str(ROOT / "poster"))


class ParrotRasipalan(unittest.TestCase):
    def setUp(self):
        try:
            import rasi_parrot
        except ImportError as e:      # numpy is installed by tests.yml on GitHub
            self.skipTest(str(e))
        self.rp = rasi_parrot

    def test_time_words(self):
        self.assertEqual(self.rp.with_period("9:00 – 10:30"), "காலை 9:00 – 10:30")
        self.assertEqual(self.rp.with_period("1:30 – 3:00"), "மதியம் 1:30 – 3:00")
        self.assertEqual(self.rp.with_period("4:30 – 6:00"), "மாலை 4:30 – 6:00")
        self.assertEqual(self.rp.with_period("காலை 7:00 – 8:00"), "காலை 7:00 – 8:00")
        self.assertEqual(self.rp.spoken_span("காலை 9:00 – 10:30"), "காலை 9:00 முதல் 10:30 வரை")

    def test_times_go_before_the_hashtags(self):
        cap = "இன்றைய ராசிபலன்\nமேஷம் ...\n\n#ராசிபலன் #RasiPalan"
        out = self.rp.with_times(cap, "⏱ உங்கள் ராசி எந்த நேரத்தில்:\nமேஷம் 0:16")
        self.assertTrue(out.endswith("#ராசிபலன் #RasiPalan"))
        self.assertIn("மேஷம் 0:16\n\n#ராசிபலன்", out)
        self.assertEqual(self.rp.with_times("no tags", ""), "no tags")

    def test_times_block(self):
        rasis = [{"rasi": f"R{i}"} for i in range(12)]
        segs = [{"kind": "hook", "t0": 0}, {"kind": "panch", "t0": 5}] + [{"kind": "rasi", "i": i, "t0": 9 + 4 * i} for i in range(12)]
        b = self.rp.times_block(rasis, segs)
        self.assertIn("R0 0:10", b)
        self.assertIn("R11 0:54", b)
        self.assertEqual(len(b.split("\n")), 5)      # the title + 4 lines of 3


class ParrotWiring(unittest.TestCase):
    def test_daily_job_uses_it_with_the_old_reel_as_fallback(self):
        src = (ROOT / "rasipalan" / "rasi_daily.py").read_text(encoding="utf-8")
        self.assertIn("rasi_parrot.make(reel_cfg(cfg, token), ctx", src)
        self.assertLess(src.index("rasi_parrot.make("), src.index("mp4 = rasi_reel.make(reel_cfg(cfg, token), ctx"))
        self.assertIn("edge-tts==7.2.3", (ROOT / ".github" / "workflows" / "rasipalan.yml").read_text(encoding="utf-8"))


class TopFive(unittest.TestCase):
    def test_workflow_and_no_view_counts(self):
        wf = (ROOT / ".github" / "workflows" / "top5.yml").read_text(encoding="utf-8")
        self.assertIn('cron: "30 15 * * *"', wf)      # 21:00 IST, before the 22:00 night rule
        src = (ROOT / "poster" / "top5.py").read_text(encoding="utf-8")
        self.assertNotIn("பார்வைகள்", src)      # owner 28 Nov: no view count on the reel
        self.assertIn("ig_paused_page(PAGE)", src)


@unittest.skipUnless((ROOT / "poster" / "mapintro.py").exists(), "the map opening is on the Trichy page only")
class MapOpening(unittest.TestCase):
    def test_only_where_switched_on(self):
        cfg = json.loads((ROOT / "poster" / "config.json").read_text(encoding="utf-8"))
        src = (ROOT / "poster" / "post.py").read_text(encoding="utf-8")
        self.assertIn('if CONFIG.get("map_intro"):', src)
        self.assertTrue(cfg.get("map_intro", False) in (True, False))

    def test_town(self):
        import mapintro
        towns = {"திருச்சி": [1, 1], "ஸ்ரீரங்கம்": [2, 2], "மணப்பாறை": [3, 3]}
        self.assertEqual(mapintro.town_of("ஸ்ரீரங்கம், திருச்சி", towns), "ஸ்ரீரங்கம்")
        self.assertEqual(mapintro.town_of("மணப்பாறை அருகே", towns), "மணப்பாறை")
        self.assertEqual(mapintro.town_of("திருச்சி", towns), "திருச்சி")
        self.assertEqual(mapintro.town_of("துவாக்குடி, திருச்சி", towns), "")      # a town not on the map: no wrong pin
        self.assertEqual(mapintro.town_of("", towns), "")


if __name__ == "__main__":
    unittest.main()
