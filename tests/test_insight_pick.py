"""owner 14 Nov: each round writes AT LEAST its count (01:00 2, 05:00 5, 09:00 5, 13:00 3, 17:00 5, 21:00 4) chosen from this round's
new news + earlier rounds' leftovers by THIS page's insights (the proven pattern until a topic has 5 measured reels), up to 3 more of
well-watched topics, every power cut on top. Plan A: the Instagram story share only for power cuts / urgent news."""
import datetime, sys, tempfile, unittest
from pathlib import Path
from unittest import mock
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research_free"))
sys.path.insert(0, str(ROOT / "poster"))
import pick, learned      # noqa: E402

IST = pick.IST
T = datetime.datetime(2026, 11, 15, 1, 0, tzinfo=IST)


def art(n, title, hours_old=1, score=5, pc=False, left=False):
    url = f"https://www.dinamalar.com/news/{n}"
    return {"id": pick.pid(url), "url": url, "title": title, "summary": "s", "source": "தினமலர்", "category": "பொது", "score": score,
            "power_cut": pc, "published": (T - datetime.timedelta(hours=hours_old)).isoformat(), "leftover": left}


class RoundCounts(unittest.TestCase):
    def test_owner_counts_per_round(self):
        got = {h: pick.round_top(T.replace(hour=h, minute=5)) for h in (1, 5, 9, 13, 17, 21)}
        self.assertEqual(got, {1: 2, 5: 5, 9: 5, 13: 3, 17: 5, 21: 4})
        self.assertEqual(sum(got.values()), 24)

    def test_a_late_run_keeps_its_round(self):
        self.assertEqual(pick.round_top(T.replace(hour=10, minute=40)), 5)      # the 9 AM round started late
        self.assertEqual(pick.round_top(T.replace(hour=0, minute=30)), 4)       # after midnight, before 1 AM: the 9 PM round


class InsightWeights(unittest.TestCase):
    def test_pattern_until_the_page_has_enough_reels(self):
        d = {"topic_weight": {"politics": 1.5}, "topic_n": {"politics": 2}}      # 2 reels: not trusted yet
        w, t, how = learned.reach_weight("அமைச்சர் ஆய்வு", d)
        self.assertEqual((t, how), ("politics", "pattern"))
        self.assertLess(w, 0)

    def test_page_insights_once_measured(self):
        d = {"topic_weight": {"temple": 1.2}, "topic_n": {"temple": 7}}
        self.assertEqual(learned.reach_weight("கோயில் திருவிழா", d), (1.2, "temple", "page"))


class InsightPick(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.old = (pick.STATE, pick.URLS, pick.DRY, pick.EMAIL, pick.INSIGHT_RANK)
        pick.STATE, pick.URLS, pick.DRY, pick.EMAIL, pick.INSIGHT_RANK = Path(self.d.name) / "s.json", Path(self.d.name) / "u.txt", False, False, True

    def tearDown(self):
        pick.STATE, pick.URLS, pick.DRY, pick.EMAIL, pick.INSIGHT_RANK = self.old
        self.d.cleanup()

    def decide(self, items, at=T):
        st = {"last_end": "", "pool": {x["id"]: x for x in items}, "rounds": {
            at.strftime("%Y-%m-%d_%H"): {"window": [(at - datetime.timedelta(hours=4)).isoformat(), at.isoformat()],
                                         "ids": [x["id"] for x in items], "sent": False, "deadline": at.isoformat(), "decided": None, "written": []}}}
        pick.save_state(st)
        data = {"topic_weight": {}, "topic_n": {}}
        with mock.patch.object(learned, "load", return_value=data), mock.patch.object(pick, "bridge_post", return_value={"ok": True}), \
                mock.patch.object(pick, "now", return_value=at):
            pick.cmd_decide()
        return [u for u in pick.URLS.read_text().split("\n") if u]

    def test_one_am_writes_2_and_the_rest_waits_for_5_am(self):
        news = [art(i, f"கோவை மாநகராட்சி கூட்டம் {i}") for i in range(10)]      # civic: weight 0, no extra
        self.assertEqual(len(self.decide(news)), 2)

    def test_more_well_watched_news_is_written_beyond_the_count(self):
        news = [art(i, f"கோவை மாநகராட்சி கூட்டம் {i}") for i in range(6)] + [art(10 + i, f"லாரி மோதி விபத்து {i}") for i in range(5)]
        urls = self.decide(news)
        self.assertEqual(len(urls), 2 + 3)      # 2 + at most 3 more accident news
        self.assertTrue(all("/news/1" in u for u in urls))

    def test_power_cut_on_top_and_leftovers_compete(self):
        news = [art(1, "கோவையில் நாளை மின்தடை", pc=True), art(2, "கோவை மாநகராட்சி கூட்டம்"),
                art(3, "கொள்ளை: இருவர் கைது", hours_old=5, left=True)]
        urls = self.decide(news)
        self.assertIn(news[0]["url"], urls)
        self.assertIn(news[2]["url"], urls)      # an earlier round's crime news beats a new civic one


class StoryPlanA(unittest.TestCase):
    def test_story_only_for_urgent(self):
        import post
        with mock.patch.dict(post.CONFIG, {"stories_urgent_only": True, "post_stories": True}), \
                mock.patch.object(post, "ig") as ig, mock.patch.object(post, "is_urgent", side_effect=lambda r: r.get("u")):
            self.assertEqual(post.publish_story("t", "https://x/v.mp4", "video", {"u": False}), "")
            ig.assert_not_called()
        self.assertTrue(post.CONFIG.get("stories_urgent_only"))
