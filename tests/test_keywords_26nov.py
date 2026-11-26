"""owner 26 Nov: the best search keywords go LAST (after the hashtags) on Instagram, Facebook and YouTube."""
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "poster"))
sys.path.insert(0, str(ROOT / "research_free"))
import facebook      # noqa: E402
import post          # noqa: E402
import youtube       # noqa: E402

ROW = {"story_id": "RN-9", "headline_ta": "பள்ளியில் புதிய கட்டடம் திறப்பு", "headline_en": "New school building opens", "location": "Pollachi", "category": "Education",
       "post_to": "", "source": "https://www.dinamalar.com/news/x",
       "caption": "🏫 பள்ளியில் புதிய கட்டடம் திறப்பு\n\n📍 பள்ளி | 27 நவம்பர்\n🙏 Follow செய்யுங்கள்\n#School #Education #Local360"}


class KeywordTest(unittest.TestCase):
    def test_keyword_line_comes_after_the_hashtags_and_before_the_source(self):
        cap = post.final_caption(dict(ROW))
        i_tag, i_kw, i_src = cap.rfind("#"), cap.find("🔎"), cap.find("📰 Source")
        self.assertGreater(i_kw, i_tag)      # after the hashtags
        self.assertGreater(i_src, i_kw)      # the source stays the very last line
        self.assertLessEqual(cap.count("#"), 5)
        self.assertLessEqual(post.ig_len(cap), post.CAPTION_LIMIT)
        kw_line = next(l for l in cap.split("\n") if l.startswith("🔎"))
        self.assertNotIn("#", kw_line)
        self.assertNotIn("http", kw_line)
        self.assertLessEqual(len(kw_line), 180)
        self.assertIn("Pollachi news", kw_line)      # the story's own place first
        self.assertIn("education news", kw_line)      # then the topic

    def test_sensitive_news_gets_only_place_words(self):
        row = dict(ROW, headline_ta="சாலை விபத்தில் ஒருவர் உயிரிழப்பு", headline_en="One dead in road accident", category="Crime", location="Pollachi")
        kw = post.keywords_for(row)
        self.assertIn("Pollachi news", kw)
        for topic in ("accident", "crime", "police", "விபத்து", "கொலை"):
            self.assertNotIn(topic, kw)

    def test_switch_off_and_no_double_line(self):
        with mock.patch.dict(post.CONFIG, {"keywords": False}):
            self.assertNotIn("🔎", post.final_caption(dict(ROW)))
        cap = post.final_caption(dict(ROW))
        self.assertEqual(cap.count("🔎"), 1)

    def test_facebook_keeps_the_keywords_last_after_its_own_hashtags(self):
        cap = post.final_caption(dict(ROW))
        fb = facebook.fb_caption(cap, post.TAG)
        self.assertEqual(fb.count("🔎"), 1)
        self.assertGreater(fb.find("🔎"), fb.rfind("#"))
        self.assertTrue(fb.rstrip().split("\n")[-1].startswith("🔎"))

    def test_youtube_gets_them_last_in_the_description_and_in_the_tags(self):
        cap = post.final_caption(dict(ROW))
        d = youtube.details({"caption": cap, "timestamp": "2026-11-26T08:00:00+0000"}, post.PAGE, "x")
        self.assertTrue(d["description"].rstrip().split("\n")[-1].startswith("🔎"))
        self.assertIn("Pollachi news", d["tags"])
        self.assertLessEqual(len(d["tags"].split(", ")), 15)
        self.assertNotIn("🔎", d["description"].split("🔔")[0])      # not repeated in the middle of the description


if __name__ == "__main__":
    unittest.main()
