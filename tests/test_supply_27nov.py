"""owner 27 Nov: 30 news a day are allowed but only ~12 were found. The news was lost before any check:
 1. a search result older than the round's own 1-4 hour window was never opened (an article Google indexed late was lost for ever)
    -> search results of the last 24 hours are opened; the pool / posted checks still stop a second offer;
 2. the taluk towns (Lalgudi, Musiri, Thuraiyur, Thiruverumbur, Manachanallur) were never searched;
 3. dropped links and Google links that could not be decoded left no trace in the log;
 4. Trichy places the papers name without the word Trichy were 'no Trichy place'; other districts' towns passed as ours;
 5. a news every AI writer failed on (busy / quota) was blocked for ever by its 'refused' mark.
No network: every source is mocked."""
import datetime, json, sys, tempfile, unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research_free"))
import pick      # noqa: E402
import allnews      # noqa: E402

IST = pick.IST
H = datetime.timedelta(hours=1)
NOW = datetime.datetime(2026, 11, 27, 12, 30, tzinfo=IST)
DINAMANI = "https://www.dinamani.com/all-editions/edition-trichy/trichy/2026/Nov/27/"
BUSY = "not filed: all free models failed: no usable answer from the models"


def named(f, name):
    def fn(q):
        return f(q)
    fn.__name__ = name
    return fn


def gitem(n, pub, title="திருச்சியில் விபத்து"):
    return {"key": f"guid-{n}", "url": f"https://news.google.com/rss/articles/{n}", "site": "https://www.dinamani.com", "title": title,
            "published": pub.isoformat(), "via": "google"}


class Candidates(unittest.TestCase):
    """pick.candidates() with every source mocked"""

    def setUp(self):
        self._pause = pick.GOOGLE_PAUSE
        pick.GOOGLE_PAUSE = 0
        self.asked = {"google": [], "bing": []}
        self.resolved = []

    def tearDown(self):
        pick.GOOGLE_PAUSE = self._pause
        pick._ROUND.clear()

    def run_cands(self, google=lambda q: [], bing=lambda q: [], since=NOW - 2 * H, mem=None, resolve=None):
        def g(q):
            self.asked["google"].append(q)
            return google(q)

        def b(q):
            self.asked["bing"].append(q)
            return bing(q)

        def res(u):
            self.resolved.append(u)
            return DINAMANI + u.rsplit("/", 1)[-1]
        pick._ROUND.clear()
        if mem is not None:
            pick._ROUND.update(t_end=NOW, seen=mem)
        lines = []
        with mock.patch.object(pick, "now", return_value=NOW), \
                mock.patch.object(allnews, "from_dinamalar_list", return_value=[]), mock.patch.object(allnews, "from_listing", return_value=[]), \
                mock.patch.object(allnews, "from_google", new=named(g, "from_google")), mock.patch.object(allnews, "from_bing", new=named(b, "from_bing")), \
                mock.patch.object(allnews, "resolve", side_effect=resolve or res):
            return pick.candidates(lines, since), lines

    # ---- 1. the search limit
    def test_search_floor_is_24_hours_not_the_round_window(self):
        self.assertEqual(pick.search_floor(NOW - 2 * H, NOW), NOW - 24 * H)
        self.assertEqual(pick.search_floor(NOW - 30 * H, NOW), NOW - 30 * H)      # a long window (a skipped day) is never cut short
        self.assertIsNone(pick.search_floor(None, NOW))      # no window given: no limit, as before
        with mock.patch.object(pick, "SEARCH_HOURS", 0):      # switch back to the rule before 27 Nov
            self.assertEqual(pick.search_floor(NOW - 2 * H, NOW), NOW - 2 * H)

    def test_a_late_indexed_search_result_is_opened_an_old_one_is_not(self):
        def google(q):
            if q != "திருச்சி site:dinamani.com":
                return []
            return [gitem("late", NOW - 6 * H), gitem("old", NOW - 30 * H), gitem("inwindow", NOW - H)]
        out, lines = self.run_cands(google)
        urls = [o["url"] for o in out]
        self.assertIn(DINAMANI + "late", urls)      # published 6 h ago, the round window is 2 h: was dropped unopened before 27 Nov
        self.assertIn(DINAMANI + "inwindow", urls)
        self.assertNotIn(DINAMANI + "old", urls)      # older than 24 h: still not opened

    def test_a_google_link_is_decoded_once_not_every_round(self):
        mem = {}
        google = lambda q: [gitem("a", NOW - 6 * H)] if q == "திருச்சி site:dinamani.com" else []      # noqa: E731
        out, _ = self.run_cands(google, mem=mem)
        self.assertEqual(len(self.resolved), 1)
        self.assertEqual([o["url"] for o in out], [DINAMANI + "a"])
        out2, lines2 = self.run_cands(google, mem=mem)      # the next round: the same Google link is known
        self.assertEqual(len(self.resolved), 1)
        self.assertEqual(out2, [])
        self.assertTrue(any("1 known from an earlier round" in l for l in lines2), lines2)

    def test_decode_failure_is_logged_and_tried_again_at_most_3_times(self):
        mem = {}
        google = lambda q: [gitem("x", NOW - H, "திருச்சி அருகே லாரி மோதி ஒருவர் பலி")] if q == "திருச்சி site:dinamani.com" else []      # noqa: E731

        def boom(u):
            self.resolved.append(u)
            raise RuntimeError("google news link not decoded (429)")
        for k in range(4):
            out, lines = self.run_cands(google, mem=mem, resolve=boom)
            self.assertEqual(out, [])
            if k < 3:
                self.assertTrue(any(l.startswith("google link not decoded") and "லாரி மோதி" in l for l in lines), lines)      # no silent drop
        self.assertEqual(len(self.resolved), 3)      # the 4th round does not ask Google's decoder again

    def test_decodes_a_round_are_capped_newest_first(self):
        google = lambda q: [gitem(i, NOW - datetime.timedelta(minutes=10 * (i + 1))) for i in range(8)] if q == "திருச்சி site:dinamani.com" else []      # noqa: E731
        with mock.patch.object(pick, "DECODE_MAX", 3):
            out, lines = self.run_cands(google, mem={})
        self.assertEqual([u.rsplit("/", 1)[-1] for u in self.resolved], ["0", "1", "2"])      # the newest three
        self.assertTrue(any("5 left for the next round" in l for l in lines), lines)

    def test_a_refusing_decoder_does_not_hold_the_round(self):
        google = lambda q: [gitem(i, NOW - datetime.timedelta(minutes=10 * (i + 1))) for i in range(12)] if q == "திருச்சி site:dinamani.com" else []      # noqa: E731

        def boom(u):
            self.resolved.append(u)
            raise RuntimeError("429 Too Many Requests")
        out, lines = self.run_cands(google, mem={}, resolve=boom)
        self.assertEqual(len(self.resolved), pick.DECODE_FAIL_STOP)      # not 12 x 40 seconds
        self.assertTrue(any(f"{12 - pick.DECODE_FAIL_STOP} left for the next round" in l for l in lines), lines)

    def test_another_districts_headline_is_not_decoded(self):
        google = lambda q: [gitem("m", NOW - H, "மதுரையில் பேருந்து விபத்து: 3 பேர் பலி")] if q == "திருச்சி site:dinamani.com" else []      # noqa: E731
        out, lines = self.run_cands(google, mem={})
        self.assertEqual((out, self.resolved), ([], []))
        self.assertTrue(any("1 of another district by their headline" in l for l in lines), lines)

    # ---- 2. the taluk towns
    def test_every_taluk_town_is_searched(self):
        for w in ("லால்குடி", "முசிறி", "துறையூர்", "திருவெறும்பூர்", "மண்ணச்சநல்லூர்", "மணப்பாறை", "ஸ்ரீரங்கம்"):
            self.assertIn(w, pick.TALUK_TOWNS)
        self.run_cands()
        for w in pick.TALUK_TOWNS:
            self.assertIn(w, self.asked["bing"])      # one open Bing search each (no decode, the links are direct)
        google_towns = [q for q in self.asked["google"] if q in pick.TALUK_TOWNS]
        self.assertEqual(google_towns, pick.google_towns(NOW))
        self.assertEqual(len(google_towns), pick.TOWN_GOOGLE)

    def test_requests_a_round_stay_small(self):
        self.run_cands()
        self.assertEqual((len(self.asked["google"]), len(self.asked["bing"])), (17, 15))      # before 27 Nov: 15 Google + 8 Bing
        self.assertEqual(pick.search_requests(NOW), {"google": 17, "bing": 15})
        self.assertLessEqual(pick.TOWN_GOOGLE, 2)      # Google already answers 429 / 503 some rounds

    def test_google_asks_every_town_within_a_day(self):
        got = set()
        for h in (4, 8, 12, 16, 20, 22):      # the six scheduled rounds
            got |= set(pick.google_towns(NOW.replace(hour=h)))
        self.assertEqual(got, set(pick.TALUK_TOWNS))

    def test_town_results_only_from_our_outlets_and_a_failure_never_stops_the_round(self):
        def bing(q):
            if q == "லால்குடி":
                return [{"url": "https://www.dinakaran.com/news/lalgudi-x", "title": "லால்குடி அருகே விபத்து", "published": (NOW - 5 * H).isoformat(), "via": "bing"},
                        {"url": "https://blog.example/lalgudi", "title": "லால்குடி", "published": (NOW - H).isoformat(), "via": "bing"}]
            if q == "முசிறி":
                raise RuntimeError("503")
            return []
        out, lines = self.run_cands(bing=bing)
        self.assertEqual([o["url"] for o in out], ["https://www.dinakaran.com/news/lalgudi-x"])
        self.assertTrue(any("town search from_bing 'முசிறி' failed" in l for l in lines), lines)


def art(url, title, pub, **kw):
    return dict({"id": pick.pid(url), "url": url, "title": title, "summary": "s", "source": "தினமணி", "published": pub.isoformat(),
                 "category": "பொது", "score": 5, "power_cut": False}, **kw)


class Round(unittest.TestCase):
    """pick.cmd_collect() with the sources and the Sheet mocked"""

    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.old = (pick.STATE, pick.URLS, pick.DRY, pick.EMAIL)
        pick.STATE = Path(self.d.name) / "pick_state.json"
        pick.URLS = Path(self.d.name) / "urls.txt"
        pick.DRY, pick.EMAIL = False, False
        self.logs, self.checked = [], []

    def tearDown(self):
        pick.STATE, pick.URLS, pick.DRY, pick.EMAIL = self.old
        self.d.cleanup()

    def state(self):
        return json.loads(pick.STATE.read_text(encoding="utf-8"))

    def run_collect(self, now, found, recent=(), refuse=None, via="google"):
        cands = [{"url": a["url"], "via": via, "title": a["title"]} for a in found]
        by = {a["url"]: a for a in found}

        def check(it, r):
            self.checked.append(it["url"])
            it["_title"] = by[it["url"]]["title"]
            why = (refuse or {}).get(it["url"], "")
            return (None, why) if why else (dict(by[it["url"]]), "")
        with mock.patch.object(pick, "now", return_value=now), \
                mock.patch.object(pick, "candidates", side_effect=lambda l, since=None: [dict(c) for c in cands]), \
                mock.patch.object(pick, "check_article", side_effect=check), \
                mock.patch.object(pick, "recent_rows", return_value=list(recent)), \
                mock.patch.object(pick, "is_posted", side_effect=lambda u, t, r: any(x.get("source") == u for x in r)), \
                mock.patch.object(pick, "log", side_effect=lambda *a: self.logs.append(" ".join(str(x) for x in a))), \
                mock.patch("builtins.print"):
            rid = pick.cmd_collect()
        return self.state()["rounds"][rid]["ids"]

    # ---- 1. listed once, never twice
    def test_late_indexed_news_is_listed_once_and_the_log_says_so(self):
        pick.STATE.write_text(json.dumps({"last_end": (NOW - 2 * H).isoformat(), "pool": {}, "rounds": {}}))
        a = art(DINAMANI + "late", "சமயபுரத்தில் போதைப் பொருள்கள் விற்றவர் கைது", NOW - 6 * H)
        ids = self.run_collect(NOW, [a])
        self.assertEqual(ids, [a["id"]])
        self.assertTrue(self.state()["pool"][a["id"]].get("late_listed"))
        log = "\n".join(self.logs)
        self.assertIn(f"news published {NOW - 2 * H:%d %b %H:%M} -> {NOW:%d %b %H:%M}", log)      # the round's own window, as before
        self.assertIn(f"+ news published since {NOW - 24 * H:%d %b %H:%M}", log)      # ... and the truth about older news in the list
        self.assertIn("found only now", log)
        # the next round finds the same link again: it is in the pool - only an 'earlier' news, never a second new one
        self.checked.clear()
        ids2 = self.run_collect(NOW + 2 * H, [a])
        self.assertEqual((ids2, self.checked), ([a["id"]], []))
        self.assertEqual(len(self.state()["pool"]), 1)
        # posted meanwhile: gone from the list for ever, although every later search still returns it
        ids3 = self.run_collect(NOW + 4 * H, [a], recent=[{"source": a["url"]}])
        self.assertEqual(ids3, [])
        ids4 = self.run_collect(NOW + 6 * H, [a], recent=[{"source": a["url"]}], refuse={a["url"]: "already posted"})
        self.assertEqual(ids4, [])

    def test_same_headline_under_another_link_is_not_a_second_news(self):
        pick.STATE.write_text(json.dumps({"last_end": (NOW - 2 * H).isoformat(), "pool": {}, "rounds": {}}))
        a = art(DINAMANI + "one", "முசிறி அருகே லாரி மோதி விவசாயி உயிரிழப்பு", NOW - 3 * H)
        b = art("https://www.dinamani.com/tamilnadu/2026/Nov/27/one-copy", "முசிறி அருகே லாரி மோதி விவசாயி உயிரிழப்பு", NOW - 3 * H)
        self.run_collect(NOW, [a])
        ids = self.run_collect(NOW + 2 * H, [a, b])
        self.assertEqual(ids, [a["id"]])
        self.assertTrue(any("already listed in an earlier round" in l for l in self.logs))

    def test_older_than_24_hours_is_still_refused(self):
        pick.STATE.write_text(json.dumps({"last_end": (NOW - 2 * H).isoformat(), "pool": {}, "rounds": {}}))
        a = art(DINAMANI + "old", "பழைய செய்தி", NOW - 30 * H)
        self.assertEqual(self.run_collect(NOW, [a]), [])
        self.assertTrue(any(l.startswith("skipped:") and "published before this window=1" in l for l in self.logs))

    # ---- 3. the drop log + the link memory
    def test_dropped_links_are_logged_once_and_a_refused_search_link_is_not_opened_again(self):
        pick.STATE.write_text(json.dumps({"last_end": (NOW - 2 * H).isoformat(), "pool": {}, "rounds": {}}))
        a = art("https://www.dailythanthi.com/news/tamilnadu/x", "டாஸ்மாக் கடைகளை திறக்கக் கூடாது: உயர் நீதிமன்றம்", NOW - H)
        self.run_collect(NOW, [a], refuse={a["url"]: "not Trichy district"})
        drops = [l for l in self.logs if l.strip().startswith("drop [")]
        self.assertEqual(len(drops), 1)
        self.assertIn("[not Trichy district]", drops[0])
        self.assertIn("டாஸ்மாக்", drops[0])      # the headline
        self.assertIn("dailythanthi.com", drops[0])      # the link
        self.logs.clear()
        self.checked.clear()
        self.run_collect(NOW + 2 * H, [a], refuse={a["url"]: "not Trichy district"})
        self.assertEqual(self.checked, [])      # a search link: not opened again
        self.assertFalse([l for l in self.logs if l.strip().startswith("drop [")])      # and not logged again
        self.assertTrue(any("checked in an earlier round=1" in l for l in self.logs))

    def test_a_district_page_link_is_read_every_round_as_before(self):
        pick.STATE.write_text(json.dumps({"last_end": (NOW - 2 * H).isoformat(), "pool": {}, "rounds": {}}))
        a = art(DINAMANI + "page", "ஒரு செய்தி", NOW - H)
        self.run_collect(NOW, [a], refuse={a["url"]: "only a headline"}, via="listing")
        self.run_collect(NOW + 2 * H, [a], via="listing")      # the paper filled the article in: it is news now
        self.assertEqual(self.checked, [a["url"], a["url"]])
        self.assertEqual(list(self.state()["pool"]), [a["id"]])

    def test_drop_log_is_capped_and_the_memory_is_cleaned(self):
        pick.STATE.write_text(json.dumps({"last_end": (NOW - 2 * H).isoformat(), "pool": {}, "rounds": {},
                                          "seen": {"Gold": (NOW - 70 * H).strftime("%Y-%m-%dT%H:%M") + " D", "Gnew": (NOW - 5 * H).strftime("%Y-%m-%dT%H:%M") + " D"}}))
        found = [art(f"https://www.maalaimalar.com/news/state/{i}", f"செய்தி {i}", NOW - H) for i in range(pick.DROP_LOG_MAX + 7)]
        self.run_collect(NOW, found, refuse={a["url"]: "not Trichy district" for a in found})
        self.assertEqual(len([l for l in self.logs if l.strip().startswith("drop [")]), pick.DROP_LOG_MAX)
        self.assertTrue(any("(+ 7 more dropped links not shown)" in l for l in self.logs))
        seen = self.state()["seen"]
        self.assertNotIn("Gold", seen)      # older than SEEN_HOURS
        self.assertIn("Gnew", seen)

    # ---- 5. every AI writer failed
    def pool_with(self, refused, **kw):
        a = art(DINAMANI + "w", "திருச்சி அருகே சுவர் இடிந்து விழுந்து முதியவர் உயிரிழப்பு", NOW - 5 * H)
        st = {"last_end": (NOW - 2 * H).isoformat(), "rounds": {},
              "pool": {a["id"]: dict(a, listed_at=(NOW - 4 * H).isoformat(), picked_at=(NOW - 4 * H).isoformat(), refused=refused, **kw)}}
        pick.STATE.write_text(json.dumps(st))
        return a

    def test_writer_failure_is_offered_again(self):
        a = self.pool_with(BUSY)
        self.assertEqual(self.run_collect(NOW, []), [a["id"]])
        it = self.state()["pool"][a["id"]]
        self.assertNotIn("refused", it)
        self.assertNotIn("picked_at", it)
        self.assertEqual(it["writer_retries"], 1)
        self.assertTrue(any("every AI writer failed last time - offered again (try 1 of 2)" in l for l in self.logs))

    def test_writer_failure_retries_are_bounded(self):
        a = self.pool_with(BUSY, writer_retries=pick.WRITER_RETRIES)
        self.assertEqual(self.run_collect(NOW, []), [])
        self.assertEqual(self.state()["pool"][a["id"]]["refused"], BUSY)
        # the whole life of one news: 1 first try + WRITER_RETRIES more, then it stays refused
        it, released = {"refused": BUSY}, 0
        for _ in range(6):
            if pick.writer_retry(it):
                released += 1
                it["refused"] = BUSY      # the writer failed again
        self.assertEqual(released, pick.WRITER_RETRIES)

    def test_a_real_no_from_the_writer_stays_a_no(self):
        for why in ("not filed: duplicate after write", "not filed: not Trichy district news (the story's first lines name another place and no Trichy place)",
                    "not filed: all free models failed: not Trichy city news (Thuraiyur)", "article has no text beyond its headline",
                    "not written: the day's maximum of 30 news was reached"):
            self.assertFalse(pick.writer_retry({"refused": why}), why)
        a = self.pool_with("not filed: duplicate after write")
        self.assertEqual(self.run_collect(NOW, []), [])
        self.assertEqual(self.state()["pool"][a["id"]]["refused"], "not filed: duplicate after write")

    def test_mark_refused_marks_the_released_news_again(self):
        a = self.pool_with(BUSY)
        self.run_collect(NOW, [])
        ref = Path(self.d.name) / "pick_refused.json"
        ref.write_text(json.dumps({a["url"]: BUSY}), encoding="utf-8")
        st = self.state()
        with mock.patch.object(pick, "REFUSED_FILE", ref):
            self.assertEqual(pick.mark_refused(st), 1)
        self.assertEqual(st["pool"][a["id"]]["refused"], BUSY)
        self.assertEqual(st["pool"][a["id"]]["writer_retries"], 1)      # the count is kept: one more try, then no more


# real headlines this page posted in November (research_free/archive/2026-11.csv, status 'filed'): none may be lost by a district rule
REAL_TRICHY = [
    "துவரங்குறிச்சி அருகே வீட்டில் பதுக்கிய 300 கிலோ புகையிலை பொருட்கள் பறிமுதல்: 45 வயது நபர் கைது",
    "பொக்லைன் இயந்திரத்தில் பேட்டரிகள் திருடிய 4 பேர் அரியமங்கலத்தில் கைது",
    "துவரங்குறிச்சி அருகே 12,501 அகல் விளக்குகளால் ஜொலித்த பிரம்மாண்ட சிவலிங்கம்!",
    "பொன்னம்பட்டி பேரூராட்சியில் மழைநீர் சேகரிப்பு விழிப்புணர்வு கூட்டம்",
    "மணப்பாறை அருகே சபரிமலை பக்தர்கள் கார் கவிழ்ந்து 4 பேர் காயம்",
    "சமயபுரத்தில் போதைப் பொருள்கள் விற்றவர் கைது",
    "திருச்சி அருகே சுவர் இடிந்து விழுந்து முதியவர் உயிரிழப்பு",
    "முசிறி அருகே கோர விபத்து: ஆம்னி வேன் மரத்தில் மோதி 8 பேர் பலி",
    "திருச்சி காந்தி மார்க்கெட் பகுதியில் போதை மாத்திரை விற்ற ரவுடி கைது",
    "திருச்சி மாநகரில் பலத்த மழை",
]
# real headlines posted with NO place in them (the paper's Trichy page / the article's first lines carried the place): still not 'another district'
REAL_NO_PLACE = [
    "போதாவூரில் முன்விரோதத்தில் விவசாயி வெட்டிக் கொலை: 11 பேரிடம் விசாரணை",
    "பள்ளி மாணவியை தலைமை ஆசிரியை தாக்கியதாகப் புகார்",
    "ராணுவ வாகனம் மீது அரசுப் பேருந்து மோதல்: இருவர் காயம்",
    "பேருந்தில் பெண்ணிடம் 16 பவுன் நகைகள் திருட்டு: 3 பெண்கள் தேடப்படுகின்றனர்",
    "ஓய்வு பெற்ற அரசு ஊழியரிடம் ரூ.49 லட்சம் மோசடி",
    "தலையில் அம்மிக்கல்லை போட்டு கணவனை கொன்ற மனைவி கைது",
    "போசம்பட்டி அரசுப் பள்ளியில் அரசமைப்பு தினம் கடைப்பிடிப்பு",
    "பெருவளை வாய்க்காலில் தண்ணீர் கோரி விவசாயிகள் ஆட்சியர் அலுவலகத்தில் போராட்டம்",
    "குண்டூர் அருகே ஆபத்தான கேபிள் கம்பம்: விபத்து அபாயம்",
]
# state news that WAS posted as Trichy news (17-26 Nov) - towns of other districts
NOT_OURS = [
    "காயல்பட்டினத்தில் 18 செ.மீ. மிக கனமழை பதிவு",
    "பாம்பன் அருகே 77 கிலோ கஞ்சா பறிமுதல், இருவர் கைது",
    "பரனூர் சுங்கச்சாவடியில் 40 நாட்களில் 3.85 லட்சம் வாகனங்கள் விதிமீறல்",
    "மேல்மருவத்தூரில் 114 ரயில்கள் நின்று செல்லும்: டிச. 4 முதல் டிச. 31 வரை",
    "திருச்செந்தூரில் உடைந்த பாதாள சாக்கடை மூடி: விபத்து ஏற்படும் முன் சீரமைக்க மக்கள் கோரிக்கை",
    "திண்டிவனம் அருகே பேருந்து-வேன் மோதல்: 2 பேர் உயிரிழப்பு",
    "ராமேஸ்வரத்திலிருந்து காரில் கடத்திய 7.50 கிலோ தங்கம் பறிமுதல்: 3 பேர் கைது",
]
BODY_OTHER = ("சிறுகனூர் அருகே லாரி மோதியதில் பெரம்பலூர் மாவட்டத்தைச் சேர்ந்த இளைஞர் உயிரிழந்தார். இதுகுறித்து போலீஸார் வழக்குப் பதிந்து "
              "விசாரிக்கின்றனர். விபத்தில் காயமடைந்த மற்றொருவர் அரசு மருத்துவமனையில் சிகிச்சை பெற்று வருகிறார். லாரி ஓட்டுநரை போலீஸார் தேடி வருகின்றனர்.")
BODY_NO_OWN = ("நெடுஞ்சாலையில் லாரி மோதியதில் பெரம்பலூர் மாவட்டத்தைச் சேர்ந்த இளைஞர் உயிரிழந்தார். இதுகுறித்து போலீஸார் வழக்குப் பதிந்து "
               "விசாரிக்கின்றனர். விபத்தில் காயமடைந்த மற்றொருவர் அரசு மருத்துவமனையில் சிகிச்சை பெற்று வருகிறார். லாரி ஓட்டுநரை போலீஸார் தேடி வருகின்றனர்.")


class District(unittest.TestCase):
    # ---- 4. accept
    def test_new_places_are_trichy_places(self):
        for t in ("துவரங்குறிச்சி அருகே விபத்து", "அரியமங்கலத்தில் 4 பேர் கைது", "சிறுகனூரில் லாரி மோதி இளைஞர் பலி", "தா.பேட்டையில் மறியல்",
                  "புத்தாநத்தம் அருகே வீடு புகுந்து திருட்டு", "பஞ்சப்பூர் பேருந்து முனையத்தில் ஆய்வு", "ராம்ஜி நகரில் கஞ்சா விற்ற இருவர் கைது",
                  "மணச்சநல்லூர் அருகே பைக் மோதி முதியவர் பலி", "திருவானைக்கோவிலில் தேரோட்டம்", "பூவாளூரில் குடிநீர் கேட்டு சாலை மறியல்"):
            self.assertTrue(allnews.has_place(t), t)
            self.assertFalse(allnews.other_district(t), t)

    def test_no_real_trichy_headline_is_lost(self):
        for t in REAL_TRICHY:
            self.assertTrue(allnews.has_place(t), t)
        for t in REAL_TRICHY + REAL_NO_PLACE:
            self.assertFalse(allnews.other_district(t), t)
            self.assertFalse(allnews.outside_district(t), t)
            self.assertTrue(allnews.local_ok(DINAMANI + "x", t), t)

    def test_new_places_name_the_town_of_a_story(self):
        self.assertEqual(allnews.places_in("துவரங்குறிச்சி அருகே வீட்டில் பதுக்கிய புகையிலை பறிமுதல்"), {"துவரங்குறிச்சி"})
        self.assertTrue(allnews.different_places("சிறுகனூரில் கிராம சபை கூட்டம்", "புத்தாநத்தத்தில் கிராம சபை கூட்டம்"))

    # ---- 4. reject
    def test_names_that_only_look_like_ours(self):
        for t in ("மணிகண்டன் கைது", "குணசீலன் மீது வழக்கு", "அன்பில் மகேஷ் பேட்டி", "திருச்சிற்றம்பலம் அருகே விபத்து: இருவர் பலி",
                  "திருச்சிலுவை ஆலயத்தில் தேர் பவனி", "திருச்செங்கோட்டில் லாரி மோதி ஒருவர் பலி", "திருச்செந்தூர் கோயிலில் கந்த சஷ்டி"):
            self.assertFalse(allnews.has_place(t), t)
        self.assertTrue(allnews.has_place("திருச்சி திருச்சிலுவை கல்லூரியில் கருத்தரங்கம்"))      # the city itself is still named

    def test_other_districts_towns_are_not_ours(self):
        for t in NOT_OURS:
            self.assertFalse(allnews.has_place(t), t)
            self.assertTrue(allnews.other_district(t), t)
            self.assertFalse(allnews.local_ok("https://www.maalaimalar.com/news/tamilnadu/x", t), t)

    def test_trichy_url(self):
        self.assertTrue(allnews.trichy_url(DINAMANI + "x"))
        self.assertTrue(allnews.trichy_url("https://www.dinamalar.com/news/tamil-nadu-district-news-trichirappalli/x/4386480"))
        self.assertFalse(allnews.trichy_url("https://www.dinamani.com/all-editions/edition-trichy/karur/2026/Nov/27/x"))
        self.assertFalse(allnews.trichy_url("https://www.dailythanthi.com/news/tamilnadu/x"))

    # ---- 4. the paper's own Trichy page + another district named in the first lines
    def check(self, url, title, body):
        page = {"title": title, "published": (pick.now() - H).isoformat(), "text": body}
        with mock.patch.object(allnews, "article_any", return_value=dict(page)), mock.patch.object(pick, "is_posted", return_value=False):
            import collect
            with mock.patch.object(collect, "same_event_filed", return_value=False):
                return pick.check_article({"url": url, "via": "listing"}, [])

    def test_trichy_page_story_is_not_refused_for_a_neighbour_named_in_its_first_lines(self):
        title = "லாரி மோதி இளைஞர் உயிரிழப்பு"
        self.assertTrue(allnews.written_elsewhere(title, BODY_NO_OWN))      # the rule that refused it
        item, why = self.check(DINAMANI + "lorry", title, BODY_NO_OWN)
        self.assertEqual(why, "")
        self.assertEqual(item["title"], title)

    def test_same_story_on_a_state_page_is_still_refused(self):
        item, why = self.check("https://www.dailythanthi.com/news/tamilnadu/lorry-accident", "லாரி மோதி இளைஞர் உயிரிழப்பு", BODY_NO_OWN)
        self.assertEqual((item, why), (None, "not Trichy district"))

    def test_state_politics_on_the_trichy_page_is_still_refused(self):
        body = ("சென்னையில் நடைபெற்ற கூட்டத்தில் கட்சியின் மாநிலச் செயலாளர் பேசினார். அரசின் செயல்பாடுகள் குறித்து அவர் கடுமையாக விமர்சித்தார். "
                "வரும் தேர்தலில் கட்சி தனித்துப் போட்டியிடும் என்றும் அவர் தெரிவித்தார். கூட்டத்தில் நிர்வாகிகள் பலர் பங்கேற்றனர்.")
        item, why = self.check(DINAMANI + "politics", "அரசின் செயல்பாடு குறித்து அமைச்சர் மீது விமர்சனம்", body)
        self.assertEqual((item, why), (None, "not Trichy district"))

    def test_new_place_in_the_first_lines_is_enough(self):
        self.assertTrue(allnews.has_place(BODY_OTHER[:400]))      # சிறுகனூர்
        self.assertFalse(allnews.written_elsewhere("லாரி மோதி இளைஞர் உயிரிழப்பு", BODY_OTHER))


class Wiring(unittest.TestCase):
    def test_only_the_trichy_page_and_no_cap_changed(self):
        wf = (ROOT / ".github" / "workflows" / "pick.yml").read_text(encoding="utf-8")
        self.assertIn('DAILY_CAP: "30"', wf)      # the supply fixes never touch the day's maximum
        src = (ROOT / "research_free" / "pick.py").read_text(encoding="utf-8")
        self.assertIn("if pid(it[\"url\"]) in pool:", src)      # the pool is still the first check of every link
        self.assertNotIn("except Exception:\n                continue\n        u = u.split", src)      # the silent decode drop is gone


if __name__ == "__main__":
    unittest.main()
