"""owner 19 Nov: every news post gets the page's own first comment, made automatically from the news (no owner approval) - "News Source"
(paper + article link), "News Date", a line for its kind of news (every category has one), corrections / objections by DM. A death /
accident or sexual-offence news has no Follow line; a sensitive news is posted ONLY with its source link. Never asks for comments."""
import inspect
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research_free"))
sys.path.insert(0, str(ROOT / "poster"))
import post      # noqa: E402

LINK = "https://www.dinamalar.com/news/tamil-nadu-district-news/x/4001"
DM = "செய்தி தொடர்பான திருத்தம், விளக்கம் அல்லது பகிர்வில் ஆட்சேபனை இருந்தால் எங்கள் DM மூலம் தெரிவிக்கலாம்."
NOTE = "📌 Note: தகவல்கள் கிடைத்த செய்தி ஆதாரத்தின் அடிப்படையில் பகிரப்பட்டுள்ளன."
FOLLOW = "🙏 நமது ஊர் செய்திகளுக்கு Follow செய்யுங்கள்."
OWNER_TEXT = ("📰 News Source: தினமலர் - " + LINK + "\n"
              "📅 News Date: 18 நவம்பர் 2026\n\n"
              "இந்த செய்தி பொதுமக்களின் தகவல் மற்றும் விழிப்புணர்வுக்காக மட்டுமே மூல ஆதாரத்தின் அடிப்படையில் பகிரப்பட்டுள்ளது. "
              "உள்ளூர் செய்திகளை மக்களிடம் கொண்டு சேர்ப்பதே எங்கள் நோக்கம்.\n\n" + DM + "\n\n" + NOTE + "\n" + FOLLOW)


def row(head="குமாரபாளையத்தில் புத்தகக் கண்காட்சி தொடக்கம்", cat="", en="Book fair begins in Kumarapalayam", **kw):
    r = {"story_id": "RN-T19", "row": 9, "headline_ta": head, "headline_en": en, "category": cat,
         "source": LINK, "published": "2026-11-18T09:15:00+05:30", "caption": head}
    r.update(kw)
    return r


# real headlines from the pages' own collector (19 Nov review of 1,024 headlines) -> the kind of line their comment gets
REAL = [
    ("வாடிப்பட்டி அருகே கார்-லாரி மோதல்: 2 பேர் உயிரிழப்பு", "Crime & Safety", "death"),
    ("அந்தியூரில் தனியார் பஸ் பூக்கடைக்குள் பாய்ந்தது; தாயும் மகளும் உயிர் தப்பினர்", "Crime & Safety", "death"),
    ("பொள்ளாச்சி அருகே கோவில் விழாவில் பட்டாசு வெடித்து 16 பேர் காயம்", "Crime & Safety", "death"),
    ("புங்கம்பள்ளி குட்டையில் உடல் மிதந்தது: 26 வயது மயில்சாமி என அடையாளம்", "Crime & Safety", "death"),
    ("எருமப்பட்டியில் பீர் பாட்டிலால் வாலிபரின் தலையில் தாக்கிய நபர் கைது", "Crime & Safety", "crime"),
    ("கோவையில் 4 கிலோ நகை கொள்ளை: மூவருக்கு தலா 7 ஆண்டு சிறை", "Crime & Safety", "court"),
    ("ராசிபுரம் அருகே பள்ளி மாணவி மாயம்: போலீசார் தேடுதல்", "Crime & Safety", "safety"),
    ("ஆத்தூரில் நாளை மின் தடை: 12 பகுதிகள்", "", "power_cut"),
    ("கரூர் இடைத்தேர்தல்: அ.தி.மு.க. ஆலோசனைக் கூட்டம் நவம்பர் 29", "Government & Services", "politics"),
    ("தி.மு.க ஆட்சியில் சட்டம், ஒழுங்கு சரியாக இருந்ததா? அமைச்சர் ஷாஜஹான் கேள்வி", "Government & Services", "politics"),
    ("மருத்துவத் துறையில் 9 ஒப்பந்த காலிப் பணியிடங்களுக்கு விண்ணப்பிக்கலாம்", "Government & Services", "jobs"),
    ("சேலம் பழங்குடியினர் நலக் குழுவில் 5 உறுப்பினர்கள்: நவ. 16க்குள் விண்ணப்பம்", "Government & Services", "govt"),
    ("மேட்டுப்பாளையம் நகராட்சிக்கு புதிய கமிஷனர் நியமனம்", "Government & Services", "admin"),
    ("குமாரபாளையத்தில் மாவட்ட சதுரங்கப் போட்டி: 80 பேருக்குப் பரிசு", "Education", "education"),
    ("பள்ளப்பட்டி அரசு மருத்துவமனையில் ரூ.6.37 கோடியில் புதிய கட்டடம் திறப்பு", "Health", "health"),
    ("பி.ஏ.பி. அணைகளின் நீர்மட்டம் சரிவு: பாசன விவசாயிகள் கவலை", "Weather & Agriculture", "weather_agri"),
    ("முட்டை விலை 20 காசுகள் குறைந்து ரூ. 6.50-ஆக நிர்ணயம்", "Business & Prices", "business"),
    ("இளம்பிள்ளை சேலம் மெயின் ரோடு அருகே குப்பைகள் அள்ளப்படாமல் குவிந்து கிடக்கின்றன", "Civic Issues", "civic"),
    ("தலைவாசல் வசந்தபுரத்துக்கு புதிய டவுன் பஸ் சேவை தொடக்கம்", "Roads & Transport", "roads"),
    ("பொள்ளாச்சியில் மேம்பாலம் கீழ் சர்வீஸ் ரோடு மோசம்: கேபிள் நீட்டிக்கொண்டு விபத்து அபாயம்", "Roads & Transport", "roads"),
    ("கரூர் கல்யாண பசுபதீஸ்வரர் கோவிலில் கந்த சஷ்டி உற்சவர் ஊர்வலம்", "Temples & Events", "events"),
    ("சின்னதடாகத்தில் ஒற்றை யானை நடமாட்டம்: விவசாயிகள் பீதி", "Weather & Agriculture", "wildlife"),
    ("கரூரில் 2 வீடுகளில் அடுத்தடுத்து தீ விபத்து", "Crime & Safety", "fire"),
    ("ஈரோட்டில் தாலி கட்டிய மறுநாளே மாயமான தேனி நபர்: பணம், ஐபோனுடன் மறைவு", "Crime & Safety", "safety"),
    ("ராசிபுரம் அருகே 70 அடி கிணற்றில் விழுந்த பசுமாடு உயிருடன் மீட்பு", "Crime & Safety", "other"),
    ("பள்ளிப்பாளையத்தில் வீடு புகுந்து திருடிய 3 பேர் பிடிபட்டனர்", "Crime & Safety", "crime"),
    ("சேலம்: சாலையைக் கடந்த 12 அடி மலைப்பாம்பு, வீட்டுச் சுற்றுச்சுவர் அருகே பிடிபட்டது", "Crime & Safety", "wildlife"),
]


class SourceComment(unittest.TestCase):
    def test_owner_text_with_the_new_labels(self):
        self.assertEqual(post.source_comment(row()), OWNER_TEXT)

    def test_every_category_has_its_own_line(self):
        for head, cat, kind in REAL:
            with self.subTest(head=head):
                self.assertEqual(post.comment_kind(row(head, cat, ""))["kind"], kind)
                msg = post.source_comment(row(head, cat, ""))
                self.assertIn("\n\n" + post.COMMENT_PURPOSE[kind], msg)
                self.assertTrue(msg.startswith("📰 News Source: "))      # a power cut: "மின்வாரிய அறிவிப்பு • தினமலர் - ..."
                self.assertIn("தினமலர் - " + LINK + "\n📅 News Date: 18 நவம்பர் 2026\n\n", msg)
                self.assertIn(DM, msg)
                self.assertIn(NOTE, msg)
        self.assertEqual(set(post.COMMENT_PURPOSE), {k for _, _, k in REAL})      # no line without a test

    def test_english_headline_does_not_mislead(self):
        self.assertEqual(post.comment_kind(row("நாமக்கல்லில் இயற்கை மருத்துவ விழிப்புணர்வுப் பேரணி", "Health",
                                               "Natural medicine awareness rally held in Namakkal"))["kind"], "health")
        self.assertEqual(post.comment_kind(row("திருப்பூர் கிப்ட் ஷாப்பில் ரூ.2,000 டெடி பொம்மை திருட்டு", "Crime & Safety",
                                               "Rs 2,000 teddy bear stolen from Tiruppur gift shop"))["kind"], "safety")

    def test_death_and_sexual_offence_have_no_follow_line(self):
        for head in ("வாடிப்பட்டி அருகே கார்-லாரி மோதல்: 2 பேர் உயிரிழப்பு",
                     "சேலத்தில் 11 வயது சிறுமிக்குப் பாலியல் தொல்லை: தொழிலாளி போக்சோ சட்டத்தில் கைது"):
            msg = post.source_comment(row(head, "Crime & Safety", ""))
            self.assertNotIn("Follow", msg)
            self.assertTrue(msg.endswith(NOTE))
        self.assertTrue(post.source_comment(row("எருமப்பட்டியில் பீர் பாட்டிலால் வாலிபரின் தலையில் தாக்கிய நபர் கைது", "Crime & Safety", ""))
                        .endswith(FOLLOW))

    def test_death_with_someone_accused_adds_not_guilty(self):
        msg = post.source_comment(row("திருச்சியில் 2 பவுன் நகைக்காக மூதாட்டி கொலை: போதை சகோதரர்கள் உட்பட 3 பேர் கைது", "Crime & Safety", ""))
        self.assertIn(post.COMMENT_PURPOSE["death"] + " " + post.NOT_GUILTY, msg)
        court = post.source_comment(row("கோவையில் 4 கிலோ நகை கொள்ளை: மூவருக்கு தலா 7 ஆண்டு சிறை", "Crime & Safety", ""))
        self.assertNotIn(post.NOT_GUILTY, court)      # convicted: "not guilty until proven" would be wrong

    def test_never_asks_for_comments_no_tags_fits_instagram(self):
        for head, cat, _ in REAL:
            msg = post.source_comment(row(head, cat, ""))
            self.assertNotIn("கமெண்ட", msg)
            self.assertNotIn("#", msg)
            self.assertNotIn("@", msg)
            self.assertLessEqual(len(msg), 2200)

    def test_date_in_india_time(self):      # 18 Nov 20:00 UTC = 19 Nov 01:30 IST
        self.assertIn("📅 News Date: 19 நவம்பர் 2026", post.source_comment(row(published="2026-11-18T20:00:00Z")))
        self.assertEqual(post.news_day(row(published="2026-11-18T20:00:00+00:00")), "19 நவம்பர் 2026")
        self.assertEqual(post.source_credit(row(published="2026-11-18T20:00:00Z"))[1], "தினமலர் (19 நவம்பர் 2026)")      # caption / end card agree

    def test_unknown_date_line_left_out(self):
        msg = post.source_comment(row(published=""))
        self.assertNotIn("📅", msg)
        self.assertTrue(msg.startswith("📰 News Source: தினமலர் - " + LINK + "\n\nஇந்த செய்தி"))

    def test_unknown_paper_link_only_and_no_source_no_comment(self):
        self.assertTrue(post.source_comment(row(source="https://local-blog.example/a/1")).startswith(
            "📰 News Source: https://local-blog.example/a/1\n📅"))
        self.assertEqual(post.source_comment(row(source="")), "")
        self.assertEqual(post.source_comment(row(source="manual")), "")

    def test_power_cut_names_the_board_notice(self):
        with mock.patch.object(post, "is_shutdown", return_value=True):
            self.assertTrue(post.source_comment(row()).startswith("📰 News Source: மின்வாரிய அறிவிப்பு • தினமலர் - "))

    def test_very_long_link_keeps_the_paper(self):
        msg = post.source_comment(row(source=LINK + "/" + "a" * 2100))
        self.assertTrue(msg.startswith("📰 News Source: தினமலர்\n📅"))
        self.assertLessEqual(len(msg), 2200)

    def test_marker_for_the_comment_bot(self):
        self.assertTrue(post.is_source_comment(post.source_comment(row())))
        self.assertFalse(post.is_source_comment("இது உண்மையா? எந்த பேப்பர்?"))


class SensitiveNewsNeedsItsLink(unittest.TestCase):
    def test_held_without_link(self):
        for head in ("வாடிப்பட்டி அருகே கார்-லாரி மோதல்: 2 பேர் உயிரிழப்பு", "எருமப்பட்டியில் பீர் பாட்டிலால் வாலிபரின் தலையில் தாக்கிய நபர் கைது",
                     "கோவையில் 4 கிலோ நகை கொள்ளை: மூவருக்கு தலா 7 ஆண்டு சிறை", "ராசிபுரம் அருகே பள்ளி மாணவி மாயம்: போலீசார் தேடுதல்",
                     "சேலத்தில் 11 வயது சிறுமிக்குப் பாலியல் தொல்லை: தொழிலாளி போக்சோ சட்டத்தில் கைது"):
            with self.subTest(head=head):
                self.assertTrue(post.link_hold(row(head, "Crime & Safety", "", source="")).startswith("held: no source link"))      # owner 21 Nov: every news
                self.assertEqual(post.link_hold(row(head, "Crime & Safety", "")), "")      # with its link it posts

    def test_other_news_and_owner_reels_not_held(self):
        self.assertIn("no source link", post.link_hold(row("முட்டை விலை 20 காசுகள் குறைந்து ரூ. 6.50-ஆக நிர்ணயம்", "Business & Prices", "", source="")))      # owner 21 Nov: every news needs its link
        with mock.patch.object(post, "is_ready_reel", return_value=True):
            self.assertEqual(post.link_hold(row("வாடிப்பட்டி அருகே கார்-லாரி மோதல்: 2 பேர் உயிரிழப்பு", "Crime & Safety", "", source="")), "")

    def test_checked_before_an_owner_pick(self):
        src = inspect.getsource(post._skip_reason_base)
        self.assertLess(src.index("link_hold(row)"), src.index("owner_picked(row)"))


class FirstCommentPosting(unittest.TestCase):
    def test_posted_automatically_once(self):
        calls = []
        with mock.patch.dict(post.CONFIG, {"first_comment": True}), \
                mock.patch.object(post, "ig", side_effect=lambda *a, **k: calls.append((a, k)) or {"id": "C1"}):
            post.first_comment("tok", "M1", "RN-T19", row())
        self.assertEqual(calls, [(("POST", "M1/comments", "tok"), {"message": OWNER_TEXT})])

    def test_never_raises_and_respects_the_switch(self):
        with mock.patch.dict(post.CONFIG, {"first_comment": True}), mock.patch.object(post, "ig", side_effect=RuntimeError("no permission")):
            post.first_comment("tok", "M1", "RN-T19", row())      # logged, the post is fine
        with mock.patch.dict(post.CONFIG, {"first_comment": False}), mock.patch.object(post, "ig") as ig:
            post.first_comment("tok", "M1", "RN-T19", row())
        ig.assert_not_called()
        with mock.patch.dict(post.CONFIG, {"first_comment": True}), mock.patch.object(post, "ig") as ig:
            post.first_comment("tok", "M1", "RN-T19", row(source=""))      # no source: nothing is guessed, no comment
        ig.assert_not_called()

    def test_switched_on_and_after_the_post_is_recorded(self):
        self.assertIs(json.loads((ROOT / "poster" / "config.json").read_text(encoding="utf-8"))["first_comment"], True)
        src = (ROOT / "poster" / "post.py").read_text(encoding="utf-8")
        self.assertNotIn("FIRST_COMMENTS", src)      # the old prompts asked people to comment (owner: never)
        self.assertEqual(src.count("first_comment(token, mid, sid, row)"), 3)      # carousel, reel and (owner 21 Nov) the owner's ready reel
        for publish in ("= publish_carousel(token, urls, caption, collab", "= publish_reel(token, url, caption, collab, cover_url)"):
            seg = src[src.index(publish):][:1500]
            self.assertLess(seg.index('bridge_post("posted"'), seg.index("first_comment(token, mid, sid, row)"))


class CommentBotSkipsIt(unittest.TestCase):
    def test_own_source_comment_never_reaches_the_owner(self):
        import comments
        page = next(iter(comments.HANDLES))
        own = post.source_comment(row())
        texts = {"1": own, "2": "இது உண்மையா? எந்த பேப்பர்?"}
        sent = []

        def ig(m, path, tok, **kw):
            if path.endswith("/media"):
                return {"data": [{"id": "M", "caption": "c", "comments_count": 2,
                                  "timestamp": comments.datetime.now(comments.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S%z")}]}
            return {"data": [{"id": i, "text": t, "username": "not.the.handle"} for i, t in texts.items()]}
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(comments.post, "bridge_get", side_effect=lambda a, **k: {"token": "t", "ids": []}), \
                mock.patch.object(comments.post, "ig_account", return_value=("U", "u")), mock.patch.object(comments.post, "ig", side_effect=ig), \
                mock.patch.object(comments, "options_for", side_effect=lambda cap, t: ("question", ["ok"])), \
                mock.patch.object(comments.post, "bridge_post", side_effect=lambda a, p: sent.append(p) or {"ok": True, "added": len(p["items"])}):
            if hasattr(comments, "IGNORED"):
                comments.IGNORED = Path(d) / "i.json"
            comments.run(page)
        self.assertEqual([x["comment_id"] for x in sent[0]["items"]], ["2"])


if __name__ == "__main__":
    unittest.main()
