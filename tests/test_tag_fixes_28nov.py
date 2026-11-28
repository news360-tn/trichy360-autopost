"""owner 28 Nov (hashtag check): two small faults.
1. A source link that ends in '#district-section' gave YouTube the junk hidden tag 'district-section'.
2. The top 5 reel would have gone to Facebook with the page tag twice ('#Salem #Salem360 #Salem360')."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "poster"))
import facebook      # noqa: E402
import youtube      # noqa: E402

HASH = re.compile(r"#[^\s#]+")
CAP = ("⚡ நாளை மின்தடை: ஓமலூர் பகுதிகள்\n\nவரி 1.\n📍 ஓமலூர், சேலம் மாவட்டம் | 27 நவம்பர் 2026\n\n"
       "#Salem #Omalur #SalemPowerCut #சேலம் #Salem360\n\n"
       "📰 Source: Times of India (27 நவம்பர் 2026): https://example.com/salem/power-shutdown-280608#district-section")


class JunkYouTubeTag(unittest.TestCase):
    def details(self, cap=CAP):
        return youtube.details({"caption": cap, "timestamp": "2026-11-27T10:00:00"}, "salem", "salem360")

    def test_a_link_part_is_not_a_hidden_tag(self):
        hidden = self.details()["tags"].split(", ")
        self.assertNotIn("district-section", hidden)
        self.assertFalse([t for t in hidden if "/" in t or "http" in t])

    def test_the_real_hashtags_are_still_hidden_tags_in_the_same_order(self):
        self.assertEqual(self.details()["tags"].split(", ")[:5], ["Salem", "Omalur", "SalemPowerCut", "சேலம்", "Salem360"])

    def test_a_caption_without_a_link_is_unchanged(self):
        plain = CAP.replace(": https://example.com/salem/power-shutdown-280608#district-section", "")
        self.assertEqual(self.details(plain)["tags"], self.details()["tags"])

    def test_the_source_link_itself_stays_in_the_description(self):
        self.assertIn("https://example.com/salem/power-shutdown-280608#district-section", self.details()["description"])


class NoRepeatedFacebookTag(unittest.TestCase):
    TOP5 = "🔥 இன்றைய டாப் 5 | சேலம் 360 | 28.11.2026\n\n1. செய்தி\n\n#இன்றையடாப்5 #சேலம்360 #Salem360 #TamilNews"

    def tags(self, *a, **k):
        return HASH.findall(facebook.fb_caption(*a, **k).split("\n")[-1])

    def test_the_page_tag_given_twice_is_written_once(self):      # the old top 5 call: tags = the last two of the page's tag list
        t = self.tags(self.TOP5, "#Salem360", tags=["#Salem", "#Salem360"])
        self.assertEqual(t, ["#Salem", "#Salem360"])

    def test_no_tag_is_ever_repeated(self):
        for given in (["#Salem360", "#salem360"], ["#Salem", "#SALEM"], ["#Salem360"], []):
            t = [x.lower() for x in self.tags(self.TOP5, "#Salem360", tags=given)]
            self.assertEqual(len(t), len(set(t)), given)
            self.assertEqual(t[-1], "#salem360")      # the page tag stays last

    def test_top5_reel_gets_topic_district_and_page(self):
        src = (ROOT / "poster" / "top5.py").read_text(encoding="utf-8")
        self.assertIn('tags=["#இன்றையடாப்5", cfg["tags"][-2]]', src)
        self.assertNotIn('tags=cfg["tags"][-2:]', src)
        self.assertEqual(self.tags(self.TOP5, "#Salem360", tags=["#இன்றையடாப்5", "#Salem"]), ["#இன்றையடாப்5", "#Salem", "#Salem360"])

    def test_news_rasipalan_and_gold_are_as_before(self):
        news = "தலைப்பு\n\nவரி 1.\n\n#Salem #Omalur #SalemNews #சேலம் #Salem360"
        self.assertEqual(self.tags(news, "#Salem360", short=True, tamil_tag="#சேலம்"), ["#Omalur", "#SalemNews", "#சேலம்", "#Salem360"])
        rasi = "ராசிபலன்\n\n#ராசிபலன் #RasiPalan #இன்றையராசிபலன் #Salem #Salem360"
        self.assertEqual(self.tags(rasi, "#Salem360", tags=["#ராசிபலன்", "#RasiPalan"]), ["#ராசிபலன்", "#RasiPalan", "#Salem360"])
        gold = "தங்கம் விலை\n\n#தங்கம்விலை #GoldRate #SilverRate #சேலம் #Salem360"
        self.assertEqual(self.tags(gold, "#Salem360"), ["#GoldRate", "#SilverRate", "#Salem360"])


if __name__ == "__main__":
    unittest.main()
