"""owner 25 Nov: platform-specific text - Facebook short news caption + Tamil tag; YouTube short title with an English search word,
3 hashtags first, Subscribe line, Tamil language."""
import sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "poster"))
import facebook      # noqa: E402
import youtube      # noqa: E402

CAP = ("🔴 சேலம் அருகே பைக் விபத்து: இளைஞர் பலி\n\nவரி 1.\nவரி 2.\nவரி 3.\nவரி 4.\nவரி 5.\n"
       "📰 Source: தினமலர் https://x.com/a (25 Nov)\n\n#Omalur #Salem #Accident #Salem360")


class PlatformText(unittest.TestCase):
    def test_facebook_news_is_short_with_tamil_tag(self):
        c = facebook.fb_caption(CAP, "#Salem360", short=True, tamil_tag="#சேலம்")
        self.assertTrue(c.startswith("🔴 சேலம் அருகே பைக் விபத்து"))
        self.assertIn("வரி 3.", c)
        self.assertNotIn("வரி 4.", c)
        self.assertIn("📰 Source: தினமலர்", c)
        self.assertNotIn("https://", c)
        self.assertTrue(c.split("\n")[-1].endswith("#சேலம் #Salem360"))

    def test_facebook_daily_posts_unchanged(self):
        self.assertIn("வரி 5.", facebook.fb_caption(CAP, "#Salem360"))      # rasipalan / gold: full text, no extra tag

    def test_youtube_title_and_description(self):
        d = youtube.details({"caption": CAP, "timestamp": "2026-11-25T10:00:00"}, "salem", "salem360")
        self.assertLessEqual(len(d["title"]), 70)
        self.assertTrue(d["title"].endswith(" | Salem accident news"))
        self.assertTrue(d["description"].startswith("#Salem #TamilNews #Shorts"))
        self.assertIn("Subscribe for daily Salem news", d["description"])
        self.assertNotIn("Follow on Instagram", d["description"])
        self.assertIn("rasi palan", youtube.search_word("இன்றைய ராசிபலன்"))

    def test_youtube_language_tamil(self):
        src = (ROOT / "poster" / "ytupload.py").read_text(encoding="utf-8")
        self.assertIn('"defaultLanguage": "ta", "defaultAudioLanguage": "ta"', src)


if __name__ == "__main__":
    unittest.main()
