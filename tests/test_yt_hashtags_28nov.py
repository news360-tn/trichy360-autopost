"""owner 28 Nov: 40 hashtags on every YouTube Short - 25 for the video, 5 for the page, 5 for the district, 5 for the area
(poster/yt_hashtags.py). Only the YouTube description changes: the first line, the title and the hidden Tags stay as they were."""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "poster"))
import youtube      # noqa: E402
import yt_hashtags      # noqa: E402

HASH = re.compile(r"#[^\s#]+")
CFG = {"reach": {"district_tag": "#Salem", "broad_tag": "#SalemNews", "extra_tag": "#SalemDistrict",
                 "place_tags": {"ஓமலூ": "#Omalur", "மேட்டூ": "#Mettur", "ஆத்தூ": "#Attur", "ஏற்காடு": "#Yercaud", "எடப்பாடி": "#Edappadi",
                                "சங்ககிரி": "#Sankagiri"},
                 "hashtag_profiles": {"#salem360": {"page": "#Salem360", "area": "#Salem", "news": "#SalemNews", "tamil": "#சேலம்",
                                                    "fallback": "#SalemDistrict", "topic": {"power_cut": "#SalemPowerCut"}}}}}
NEWS = ("🚌 ஓமலூரில் புதிய பஸ் நிலையம் திறப்பு\n\n📰 முழு விவரம்:\nஓமலூரில் புதிய பஸ் நிலையம் நேற்று திறக்கப்பட்டது.\n\n"
        "Omalur new bus stand opened | Salem news\n📍 ஓமலூர், சேலம் மாவட்டம் | 27 நவம்பர் 2026\n\n"
        "#Salem #Omalur #SalemNews #சேலம் #Salem360\n\n"
        "🔎 ஓமலூர் செய்திகள், சேலம் செய்திகள், Salem news, சேலம் மாவட்ட செய்திகள், Salem district news, போக்குவரத்து, traffic update, "
        "Tamil Nadu local news, இன்றைய செய்திகள், Salem 360\n\n"
        "📰 Source: தினமலர் (27 நவம்பர் 2026): https://example.com/news/omalur-bus-stand#district-section")
CRIME = ("🚨 ஓமலூர் அருகே வீட்டில் திருட்டு: போலீசார் விசாரணை\n\nவரி 1.\n📍 ஓமலூர், சேலம் மாவட்டம் | 27 நவம்பர் 2026\n\n"
         "#Salem #Omalur #SalemNews #சேலம் #Salem360\n\n"
         "🔎 ஓமலூர் செய்திகள், சேலம் செய்திகள், Salem news, Tamil Nadu local news, இன்றைய செய்திகள், Salem 360")
POWER = ("⚡ நாளை மின்தடை: ஓமலூர், மேட்டூர், ஆத்தூர், சங்ககிரி பகுதிகள்\n\nஓமலூர், மேட்டூர், ஆத்தூர், சங்ககிரி பகுதிகளில் நாளை மின்தடை.\n"
         "📍 சேலம் மாவட்டம் | 27 நவம்பர் 2026\n\n#Salem #SalemDistrict #SalemPowerCut #சேலம் #Salem360\n\n"
         "🔎 சேலம் செய்திகள், Salem news, மின்தடை, power cut today, Tamil Nadu local news, இன்றைய செய்திகள், Salem 360")
RASI = "🔮 இன்றைய ராசிபலன் - 28 நவம்பர் 2026\n\nமேஷம்: நல்ல நாள்.\n\n#ராசிபலன் #RasiPalan #இன்றையராசிபலன் #Salem #Salem360"
GOLD = "💰 இன்றைய தங்கம் விலை\n\n22 காரட்: ₹ 11,500\n\n#தங்கம்விலை #GoldRate #SilverRate #சேலம் #Salem360"


def groups(cap, page="salem", name="Salem", cfg=CFG):
    return yt_hashtags.build(cap, page, name, "", cfg)


def flat(g):
    return [t for k in ("video", "page", "district", "area") for t in g[k]]


class FortyHashtags(unittest.TestCase):
    def test_always_40_different_tags_in_25_5_5_5(self):
        for cap in (NEWS, CRIME, POWER, RASI, GOLD, "", "தலைப்பு மட்டும்"):
            g = groups(cap)
            self.assertEqual([len(g[k]) for k in ("video", "page", "district", "area")], [25, 5, 5, 5], cap[:30])
            tags = flat(g)
            self.assertEqual(len({t.lower() for t in tags}), 40, cap[:30])      # YouTube reads #Salem and #salem as one tag
            for t in tags:
                self.assertRegex(t, r"^#[\w஀-௿]{2,32}$")      # no space, dot or dash inside a hashtag

    def test_each_group_is_about_its_own_thing(self):
        g = groups(NEWS)
        self.assertEqual(g["page"][0], "#Salem360")
        self.assertTrue(all("360" in t for t in g["page"]))
        self.assertEqual(g["district"][:3], ["#Salem", "#SalemNews", "#சேலம்"])
        self.assertEqual(g["area"][:3], ["#Omalur", "#ஓமலூர்", "#OmalurNews"])      # the town of THIS news, English and Tamil
        self.assertTrue(all("Omalur" in t or "ஓமலூர்" in t for t in g["area"]))
        self.assertEqual(g["video"][:2], ["#TamilNews", "#Shorts"])
        self.assertIn("#Traffic", g["video"])      # the topic of this news, from its own keyword line
        self.assertIn("#போக்குவரத்து", g["video"])

    def test_sensitive_news_gets_no_topic_tag(self):      # owner 26 Nov: a crime / death news gets place words only
        g = groups(CRIME)
        topic = {t.lower() for tags in yt_hashtags.KIND_TAGS.values() for t in tags}
        self.assertFalse([t for t in g["video"] if t.lower() in topic])
        self.assertEqual(g["area"][0], "#Omalur")

    def test_topic_is_found_from_the_tamil_keyword_alone(self):      # a long keyword line keeps only the Tamil word of the pair
        g = groups(NEWS.replace(", traffic update", ""))
        self.assertIn("#Traffic", g["video"])

    def test_a_state_wide_place_is_not_a_town(self):
        g = groups(NEWS.replace("📍 ஓமலூர், சேலம் மாவட்டம்", "📍 தமிழ்நாடு").replace("ஓமலூர் செய்திகள், ", ""))
        self.assertFalse([t for t in g["area"] if "தமிழ்நாடு" in t])

    def test_power_cut_names_every_town_of_the_list(self):
        g = groups(POWER)
        for t in ("#Omalur", "#Mettur", "#Attur", "#Sankagiri"):
            self.assertIn(t, g["area"])
        self.assertIn("#SalemPowerCut", g["video"])      # the reel's own Instagram topic tag
        self.assertIn("#PowerCut", g["video"])
        self.assertIn("#மின்தடை", g["video"])

    def test_a_news_with_no_town_never_borrows_other_towns(self):
        g = groups("🏛️ சேலம் கலெக்டர் அலுவலகத்தில் கூட்டம்\n\nவரி.\n📍 சேலம் | 27 நவம்பர் 2026\n\n#Salem #SalemDistrict #SalemNews #சேலம் #Salem360")
        self.assertFalse([t for t in g["area"] if t in ("#Omalur", "#Mettur", "#Attur", "#Yercaud", "#Edappadi", "#Sankagiri")])
        self.assertIn("#SalemCity", g["area"])

    def test_daily_reels(self):
        r, gd = groups(RASI), groups(GOLD)
        self.assertIn("#RasiPalan", r["video"])
        self.assertIn("#ராசிபலன்", r["video"])
        self.assertIn("#GoldRate", gd["video"])
        self.assertIn("#தங்கம்விலை", gd["video"])
        self.assertNotIn("#LocalNews", r["video"])      # a rasipalan reel is not news

    def test_a_link_part_is_never_a_hashtag(self):      # 28 Nov: '#district-section' at the end of a source link
        self.assertFalse([t for t in flat(groups(NEWS)) if "district" in t.lower() and "section" in t.lower()])

    def test_town_page_keeps_its_town_in_the_area_group(self):      # Rasipuram 360 is a town page inside Namakkal district
        cfg = {"reach": {"district_tag": "#Namakkal", "broad_tag": "#NamakkalNews", "extra_tag": "#TamilNadu",
                         "place_tags": {"வெண்ணந்தூ": "#Vennandur"},
                         "hashtag_profiles": {"#rasipuram360": {"page": "#Rasipuram360", "area": "#Rasipuram", "news": "#RasipuramNews",
                                                                "tamil": "#ராசிபுரம்", "fallback": "#Namakkal"}}}}
        g = groups("தலைப்பு\n\nவரி.\n\n#Rasipuram #Vennandur #RasipuramNews #ராசிபுரம் #Rasipuram360", "rasipuram", "Rasipuram", cfg)
        self.assertEqual(g["page"][0], "#Rasipuram360")
        self.assertEqual(g["district"][:3], ["#Namakkal", "#NamakkalNews", "#நாமக்கல்"])
        self.assertEqual(g["area"][:4], ["#Rasipuram", "#RasipuramNews", "#ராசிபுரம்", "#Vennandur"])
        self.assertNotIn("#TamilNadu", g["district"])

    def test_this_repo_pages_with_the_real_settings(self):
        cfg = json.loads((ROOT / "poster" / "config.json").read_text(encoding="utf-8"))
        for key, prof in ((cfg.get("reach") or {}).get("hashtag_profiles") or {}).items():
            page = next((p for p in youtube.PAGE_EN if key.lstrip("#").startswith(p)), "")
            self.assertTrue(page, key)
            name = youtube.PAGE_EN[page]
            for cap in (NEWS, RASI, GOLD):
                g = yt_hashtags.build(cap, page, name, "", cfg)
                self.assertEqual(len({t.lower() for t in flat(g)}), 40, f"{page} {cap[:20]}")
                self.assertIn(f"#{name}360", g["page"])
                self.assertIn(prof["page"].lower(), [t.lower() for t in g["page"]])


class YouTubeDescription(unittest.TestCase):
    def details(self, cap=NEWS):
        return youtube.details({"caption": cap, "timestamp": "2026-11-27T10:00:00"}, "salem", "salem360")

    def test_description_has_40_hashtags_and_the_first_line_is_unchanged(self):
        d = self.details()
        self.assertTrue(d["description"].startswith("#Salem #TamilNews #Shorts\n"))      # YouTube shows these 3 above the title
        tags = HASH.findall(re.sub(r"https?://\S+", "", d["description"]))
        self.assertEqual(len(tags), 40)
        self.assertEqual(len({t.lower() for t in tags}), 40)
        self.assertLessEqual(len(tags), 60)      # past 60 YouTube ignores every hashtag
        for t in ("#SalemNews", "#Salem360"):      # the two tags the description had before stay
            self.assertIn(t, tags)

    def test_nothing_else_in_the_description_moves(self):
        d = self.details()["description"]
        lines = d.split("\n")
        i = next(n for n, l in enumerate(lines) if l.startswith("🔔 Subscribe for daily Salem news"))
        self.assertTrue(lines[i + 1].startswith("#"))      # the hashtags come right after the Subscribe line
        self.assertTrue(lines[-1].startswith("🔎"))      # the keyword line stays last (owner 26 Nov)
        self.assertNotIn("#", "\n".join(l for l in lines[1:i] if not l.startswith("📰")))      # no hashtag inside the news text

    def test_title_and_hidden_tags_are_not_touched(self):
        d = self.details()
        self.assertNotIn("#", d["title"])
        self.assertLessEqual(len(d["title"]), 70)
        hidden = d["tags"].split(", ")
        self.assertLessEqual(len(hidden), 15)
        self.assertEqual(hidden[:5], ["Salem", "Omalur", "SalemNews", "சேலம்", "Salem360"])

    def test_switch_off_brings_the_old_line_back(self):
        old = yt_hashtags._CFG
        try:
            yt_hashtags._CFG = {"youtube_hashtags": False}
            self.assertIn("\n#SalemNews #Salem360\n", self.details()["description"])
        finally:
            yt_hashtags._CFG = old

    def test_a_fault_in_the_hashtags_never_stops_the_upload_text(self):
        keep = yt_hashtags.lines
        try:
            yt_hashtags.lines = lambda *a, **k: 1 / 0
            d = self.details()
            self.assertIn("\n#SalemNews #Salem360\n", d["description"])
            self.assertTrue(d["title"])
        finally:
            yt_hashtags.lines = keep


if __name__ == "__main__":
    unittest.main()
