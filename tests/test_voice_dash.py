"""owner 1 Nov (RN-256): 'சேலம் - நாமக்கல்' was read 'சேலம் மைனஸ் நாமக்கல்'. No dash of any kind may ever reach the voice."""
import re, sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "reel"))
import tts      # noqa: E402


class NoDashInVoice(unittest.TestCase):
    def test_place_dash_place(self):
        self.assertEqual(tts.clean("சேலம் - நாமக்கல் மாவட்ட எல்லையில்"), "சேலம், நாமக்கல் மாவட்ட எல்லையில்")
        self.assertEqual(tts.clean("காளிப்பட்டி - பாவடி பஞ்சாயத்தில்"), "காளிப்பட்டி, பாவடி பஞ்சாயத்தில்")

    def test_route(self):
        self.assertEqual(tts.clean("கோவை - நாகர்கோவில் ரயில் மாற்றுப்பாதை"), "கோவை முதல் நாகர்கோவில் வரை ரயில் மாற்றுப்பாதை")

    def test_number_range(self):
        self.assertEqual(tts.clean("10-15 பேர்"), "பத்து முதல் பதினைந்து பேர்")

    def test_every_dash_kind(self):
        for d in "-‐‑‒–—―−﹘﹣－":
            for s in (f"சேலம் {d} நாமக்கல்", f"சேலம்{d}நாமக்கல்", f"டி{d}20", f"{d} செய்தி {d}", f"மழை {d}{d} வெள்ளம்"):
                out = tts.clean(s)
                self.assertFalse(re.search("[" + re.escape(tts.DASH) + "]", out), f"{s!r} -> {out!r}")
                self.assertNotIn("மைனஸ்", out)

    def test_every_voice_goes_through_clean(self):
        src = (ROOT / "reel" / "reel4.py").read_text(encoding="utf-8")
        self.assertGreaterEqual(src.count("say = tts.clean(names.spoken(t))"), 1)
        self.assertEqual(src.count("--text\", say"), src.count("say = tts.clean(names.spoken(t))"))      # every Tamil voice call speaks the cleaned text


if __name__ == "__main__":
    unittest.main()
