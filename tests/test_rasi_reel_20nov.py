"""owner 20 Nov: the daily rasipalan is a REEL in the gold-reel 360 pattern (music only); the carousel only when the reel fails"""
import datetime
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "rasipalan"))
sys.path.insert(0, str(ROOT / "goldrate"))

RASI = ["மேஷம்", "ரிஷபம்", "மிதுனம்", "கடகம்", "சிம்மம்", "கன்னி", "துலாம்", "விருச்சிகம்", "தனுசு", "மகரம்", "கும்பம்", "மீனம்"]


class RasiReel(unittest.TestCase):
    def page(self):
        import rasi360_render as RR
        import rasi_panchang as P
        pan = P.compute(datetime.date(2026, 11, 21), "salem")
        rs = [{"rasi": r, "stars": 4, "work": "புதிய வாய்ப்புகள் கிடைக்கும்", "money": "வருமானம் உயரும்", "family": "மகிழ்ச்சி",
               "health": "உடல்நலம் சீராக இருக்கும்", "remedy": "முருகன் வழிபாடு"} for r in RASI]
        p = {"town": "சேலம்", "name1": "சேலம்", "handle": "salem360.official", "logo": ROOT / "kit" / "logo_salem.png"}
        return RR, pan, RR.reel_page(p, {"p": pan, "rasis": rs})

    def test_screens(self):
        RR, pan, html = self.page()
        self.assertEqual(html.count('class="scene gold"'), 13)      # panchangam + 12 rasis
        self.assertEqual(html.count('class="scene end"'), 1)
        for r in RASI:
            self.assertIn(r, html)
        self.assertIn("இன்றைய பஞ்சாங்கம்", html)
        self.assertIn("சந்திராஷ்டமம் • கவனம்", html)      # the badge on today's சந்திராஷ்டமம் rasi
        self.assertIn("Follow @salem360.official", html)
        self.assertIn("fitAll", html)      # long lines shrink to fit
        self.assertNotIn("voice", html.lower())
        _, dur = RR.timeline()
        self.assertAlmostEqual(dur, 43.6, delta=0.01)

    def test_twelve_needed(self):
        import rasi360_render as RR
        with self.assertRaises(ValueError):
            RR.reel_page({"town": "x", "name1": "x", "handle": "x", "logo": "x"}, {"p": {}, "rasis": []})

    def test_daily_job_posts_the_reel(self):
        src = (ROOT / "rasipalan" / "rasi_daily.py").read_text(encoding="utf-8")
        self.assertIn('media_type="REELS"', src)
        self.assertIn("rasi_reel.make(reel_cfg(cfg, token), ctx", src)
        self.assertIn("the carousel goes out instead", src)      # a day is never missed
        self.assertIn('"reel", [reel[0]], reel[1]', src)      # Facebook gets the reel
        self.assertIn("Reel-ல் பாருங்கள்", src)
        wf = (ROOT / ".github" / "workflows" / "rasipalan.yml").read_text(encoding="utf-8")
        self.assertIn("imageio-ffmpeg", wf)
        self.assertIn("numpy", wf)


if __name__ == "__main__":
    unittest.main()
