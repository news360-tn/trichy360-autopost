"""owner 14 Nov: health tips and day functions are not written automatically; sexual-harassment / POCSO news counts as crime."""
import sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research_free"))
import collect, learned      # noqa: E402


class Selection14Nov(unittest.TestCase):
    def test_health_tips_and_day_functions_skipped(self):
        for t in ("சாதாரண சளிக்கும் நிமோனியாவுக்கும் என்ன வித்தியாசம்", "புற்றுநோய் அபாயத்தை அதிகரிக்கும் அன்றாட பழக்கங்கள்",
                  "குழந்தைகளுக்கு தடுப்பூசி போடுவதின் அவசியம்", "நாயக்கன்பாளையத்தில் குழந்தைகள் தின விழா"):
            self.assertTrue(collect.low_interest(t, ""), t)

    def test_real_news_still_written(self):
        for t in ("பள்ளி விழாவுக்கு சென்ற மாணவர் விபத்தில் பலி", "நாளை மின்தடை பகுதிகள்", "டெங்கு காய்ச்சல்: 5 பேர் மருத்துவமனையில் அனுமதி"):
            self.assertEqual(collect.low_interest(t, ""), "", t)

    def test_harassment_arrest_is_crime(self):
        t = "பெண் நிர்வாகிக்கு பாலியல் தொல்லை: நிர்வாகி கைது"
        self.assertEqual(learned.topic(t), "crime")
        self.assertGreaterEqual(collect.interest({"title": "பெண் நிர்வாகிக்கு பாலியல் தொல்லை", "text": ""}), 10)
