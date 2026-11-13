"""owner 13 Nov: power cuts printed only in the daily STATE-WIDE lists (News18 / ABP Live / Samayam): only Trichy's part is written;
a list without one is refused; a notice filed under another district's page is refused."""
import datetime, json, sys, unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research_free"))
import allnews      # noqa: E402
import powercut     # noqa: E402

IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
LIST_URL = "https://tamil.abplive.com/news/tamil-nadu/tamilnadu-power-shutdown-12-11-2026"
BODY = ("தமிழ்நாட்டில் நாளை காலை 9 மணி முதல் மாலை 5 மணி வரை பராமரிப்புப் பணிகள் காரணமாக மின் விநியோகம் நிறுத்தப்படும். "
        "வேலூர் மாவட்டம் காட்பாடி, சத்துவாச்சாரி. திருச்சி மாவட்டம் ஆலயபுரம், புதுநகர், காந்திபுரம். "
        "கரூர் மாவட்டம் பாலம்பாள்புரம், ஐந்து ரோடு.")


def page(title, body):
    ld = json.dumps({"@type": "NewsArticle", "headline": title, "datePublished": "2026-11-11T19:15:00+05:30", "articleBody": body}, ensure_ascii=False)
    return mock.Mock(text=f'<html><script type="application/ld+json">{ld}</script></html>')


class StateWideList(unittest.TestCase):
    def test_only_our_district_part(self):
        with mock.patch.object(allnews, "_get", return_value=page("தமிழகத்தில் நாளை (12-11-2026) மின் தடை", BODY)):
            a = allnews.article_any(LIST_URL + allnews.SECTION_MARK)
        self.assertEqual(a["title"], "திருச்சி மாவட்டத்தில் நாளை (12-11-2026) மின்தடை: ஆலயபுரம், புதுநகர், காந்திபுரம்")
        self.assertIn("காலை 9 மணி", a["text"])
        for other in ("வேலூர்", "காட்பாடி", "கரூர்", "பாலம்பாள்புரம்"):
            self.assertNotIn(other, a["text"] + a["title"], other)

    def test_list_without_our_district_gives_no_text(self):
        body = BODY.replace("திருச்சி மாவட்டம் ஆலயபுரம், புதுநகர், காந்திபுரம். ", "")
        with mock.patch.object(allnews, "_get", return_value=page("தமிழகத்தில் நாளை மின்தடை", body)):
            self.assertEqual(allnews.article_any(LIST_URL + allnews.SECTION_MARK)["text"], "")

    def test_state_lists_are_searched_and_marked(self):
        hit = {"url": LIST_URL, "title": "தமிழகத்தில் நாளை (12-11-2026) மின்தடை அறிவிப்பு", "site": "tamil.abplive.com", "published": ""}
        with mock.patch.object(allnews, "from_dinamalar_list", return_value=[]), mock.patch.object(allnews, "from_listing", return_value=[]), \
                mock.patch.object(allnews, "from_google", side_effect=lambda q: [hit] if "abplive" in q else []), \
                mock.patch.object(allnews, "from_bing", return_value=[]):
            got = [x["url"] for x in powercut.links()]
        self.assertIn(LIST_URL + allnews.SECTION_MARK, got)

    def test_other_district_page_refused(self):
        now = datetime.datetime(2026, 11, 10, 19, 0, tzinfo=IST)
        url = "https://www.dinamalar.com/news/tamil-nadu-district-news-namakkal/power-outage/1"
        art = {"title": "நாளைய மின் தடை", "text": "திருச்சி சாலை பகுதிகளில் காலை 9 மணி முதல் மின்தடை", "published": "2026-11-10T18:00:00+05:30"}
        with mock.patch.object(allnews, "article_any", return_value=dict(art, url=url)):
            got, why = powercut.check({"url": url, "title": art["title"]}, now.date(), now)
        self.assertIsNone(got)
        self.assertEqual(why, "other district")


class SamayamFormat(unittest.TestCase):
    def test_quoted_headings_and_two_parts_of_one_district(self):
        body = ('தமிழகத்தில் நாளை காலை 9 மணி முதல் பராமரிப்பு பணிகள் காரணமாக மின்தடை."திருச்சி/மெட்ரோ மின் தடை பகுதிகள்":- "இருகூர், ஒண்டிப்புதூர்",'
                '"திருச்சி /வடக்கு மின்வெட்டு பகுதிகள்":- "யமுனா நகர், கணுவாய்","திண்டுக்கல் மின்வெட்டு பகுதிகள்": - "நிலக்கோட்டை, சாணார்பட்டி"')
        with mock.patch.object(allnews, "_get", return_value=page("தமிழகத்தில் நாளை (13-11-2026) மின்தடை அறிவிப்பு", body)):
            a = allnews.article_any(LIST_URL + allnews.SECTION_MARK)
        for w in ("இருகூர்", "ஒண்டிப்புதூர்", "யமுனா நகர்", "கணுவாய்"):
            self.assertIn(w, a["text"], w)
        for w in ("திண்டுக்கல்", "நிலக்கோட்டை"):
            self.assertNotIn(w, a["text"] + a["title"], w)
        self.assertTrue(a["title"].startswith("திருச்சி மாவட்டத்தில் நாளை (13-11-2026) மின்தடை: இருகூர், ஒண்டிப்புதூர்"), a["title"])


if __name__ == "__main__":
    unittest.main()
