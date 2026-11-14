"""owner 1 Nov (Trichy): collection only at 6 AM / 4 PM from Dinamalar + Dinamani, by published-time windows; the owner ticks the
news in an e-mail page, else the top 8; posted news never listed again; listed-not-posted news returns while < 24 h old."""
import datetime, json, sys, tempfile, unittest
from pathlib import Path
from unittest import mock
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research_free"))
import pick      # noqa: E402

IST = pick.IST


def art(url, title, pub, score=5, pc=False):
    return {"id": pick.pid(url), "url": url, "title": title, "summary": "s", "source": "தினமலர்", "published": pub.isoformat(),
            "category": "பொது", "score": score, "power_cut": pc}


class PickFlow(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.old = (pick.STATE, pick.URLS, pick.DRY, pick.EMAIL)
        self._ir = pick.INSIGHT_RANK
        pick.INSIGHT_RANK = False      # owner 14 Nov: the insight pick has its own tests (test_insight_pick.py)
        pick.EMAIL = True      # these tests cover the e-mail flow (it can be switched on again with PICK_EMAIL=1)
        pick.STATE = Path(self.d.name) / "pick_state.json"
        pick.URLS = Path(self.d.name) / "urls.txt"
        pick.DRY = False
        self.sent = []

    def tearDown(self):
        pick.STATE, pick.URLS, pick.DRY, pick.EMAIL = self.old
        pick.INSIGHT_RANK = getattr(self, "_ir", pick.INSIGHT_RANK)
        self.d.cleanup()

    def run_collect(self, now, found, recent=()):
        cands = [{"url": a["url"], "via": "listing"} for a in found]
        by = {a["url"]: a for a in found}
        with mock.patch.object(pick, "now", return_value=now), \
                mock.patch.object(pick, "candidates", side_effect=lambda l, since=None: cands), \
                mock.patch.object(pick, "check_article", side_effect=lambda it, r: (dict(by[it["url"]]), "")), \
                mock.patch.object(pick, "recent_rows", return_value=list(recent)), \
                mock.patch.object(pick, "is_posted", side_effect=lambda u, t, r: any(x.get("source") == u for x in r)), \
                mock.patch.object(pick, "bridge_post", side_effect=lambda a, p: self.sent.append((a, p)) or {"ok": True}):
            return pick.cmd_collect()

    def test_windows_by_published_time_and_no_repeats(self):
        d = datetime.date(2026, 11, 1)
        m6 = datetime.datetime.combine(d, datetime.time(6, 0), IST)
        st = {"last_end": (m6 - datetime.timedelta(hours=14)).isoformat(), "pool": {}, "rounds": {}}
        pick.STATE.write_text(json.dumps(st))
        a_old = art("https://www.dinamalar.com/a", "பழைய செய்தி", m6 - datetime.timedelta(hours=20))
        a_in = art("https://www.dinamani.com/b", "இரவு செய்தி", m6 - datetime.timedelta(hours=3))
        self.run_collect(m6, [a_old, a_in])
        items = self.sent[-1][1]["items"]
        self.assertEqual([x["title"] for x in items], ["இரவு செய்தி"])      # published before the window: not listed
        # evening: the morning item (not posted) comes back as an earlier news; a new 6 AM-4 PM item is listed as new
        e4 = datetime.datetime.combine(d, datetime.time(16, 0), IST)
        a_new = art("https://www.dinamalar.com/c", "மதியச் செய்தி", e4 - datetime.timedelta(hours=2))
        self.run_collect(e4, [a_in, a_new])
        items = self.sent[-1][1]["items"]
        self.assertEqual([(x["title"], x["leftover"]) for x in items], [("மதியச் செய்தி", False), ("இரவு செய்தி", True)])
        self.assertEqual(json.loads(pick.STATE.read_text())["last_end"], e4.isoformat())
        # next morning: the item was posted meanwhile -> never listed again
        n6 = m6 + datetime.timedelta(days=1)
        self.run_collect(n6, [], recent=[{"source": a_in["url"]}, {"source": a_new["url"]}])
        self.assertEqual(len(self.sent), 2, "nothing left to list: no e-mail")

    def test_leftovers_older_than_a_day_are_dropped(self):
        t = datetime.datetime(2026, 11, 2, 16, 0, tzinfo=IST)
        old = art("https://www.dinamalar.com/x", "நேற்றைய செய்தி", t - datetime.timedelta(hours=30))
        pick.STATE.write_text(json.dumps({"last_end": (t - datetime.timedelta(hours=10)).isoformat(), "rounds": {},
                                          "pool": {old["id"]: dict(old, listed_at=(t - datetime.timedelta(hours=28)).isoformat())}}))
        self.run_collect(t, [])
        self.assertEqual(self.sent, [])
        self.assertEqual(json.loads(pick.STATE.read_text())["pool"], {})

    def test_power_cut_first_then_score(self):
        t = datetime.datetime(2026, 11, 1, 6, 0, tzinfo=IST)
        xs = [art("https://www.dinamani.com/1", "a", t, 5), art("https://www.dinamani.com/2", "b", t, 9), art("https://www.dinamani.com/3", "c", t, 3, pc=True)]
        self.assertEqual([x["title"] for x in pick.rank(xs)], ["c", "b", "a"])

    def decide(self, status, items=15):
        t = datetime.datetime(2026, 11, 1, 6, 0, tzinfo=IST)
        pool = {}
        for i in range(items):
            a = art(f"https://www.dinamani.com/{i}", f"n{i}", t, score=i)
            pool[a["id"]] = a
        rid = "2026-11-01_morning"
        pick.STATE.write_text(json.dumps({"last_end": t.isoformat(), "pool": pool, "rounds": {rid: {
            "ids": list(pool), "deadline": t.isoformat(), "written": [], "decided": None, "sent": True}}}))
        with mock.patch.object(pick, "bridge_get", return_value=status), \
                mock.patch.object(pick, "bridge_post", side_effect=lambda a, p: self.sent.append((a, p)) or {"ok": True}):
            pick.cmd_decide()
        return [l for l in pick.URLS.read_text().split("\n") if l], pool

    def test_owner_pick_is_posted_exactly(self):
        urls, pool = self.decide({"ok": True, "submitted": True, "ids": [pick.pid("https://www.dinamani.com/2"), pick.pid("https://www.dinamani.com/0")]})
        self.assertEqual(urls, ["https://www.dinamani.com/2", "https://www.dinamani.com/0"])      # low score too: the owner decides

    def test_no_reply_top_8(self):
        urls, _ = self.decide({"ok": True, "submitted": False})
        self.assertEqual(len(urls), 4)      # owner 12 Nov: 4 per round, 12 a day
        self.assertEqual(urls[0], "https://www.dinamani.com/14")
        self.assertEqual(self.sent[-1][0], "pickAuto")

    def test_list_not_emailed_means_top_8_at_once(self):
        t = datetime.datetime(2026, 11, 1, 6, 0, tzinfo=IST)
        a = art("https://www.dinamani.com/z", "z", t)
        far = (datetime.datetime.now(IST) + datetime.timedelta(hours=1)).isoformat()
        pick.STATE.write_text(json.dumps({"last_end": t.isoformat(), "pool": {a["id"]: a}, "rounds": {"r": {
            "ids": [a["id"]], "deadline": far, "written": [], "decided": None, "sent": False}}}))
        with mock.patch.object(pick, "bridge_get", side_effect=AssertionError("must not wait")), \
                mock.patch.object(pick, "bridge_post", return_value={"ok": True}):
            pick.cmd_decide()
        self.assertEqual(pick.URLS.read_text(), a["url"])

    def test_fewer_than_8_all_posted(self):
        urls, _ = self.decide({"ok": True, "submitted": False}, items=3)
        self.assertEqual(len(urls), 3)

    def test_auto_pick_never_takes_suicide_or_obituary(self):
        t = datetime.datetime(2026, 11, 1, 6, 0, tzinfo=IST)
        xs = [art("https://www.dinamani.com/s", "தொழில் நஷ்டம்: நகை தொழிலாளி தற்கொலை", t, 99),
              art("https://www.dinamani.com/o", "பொன்னுசாமி கவுண்டா் (108) காலமானாா்", t, 98),
              art("https://www.dinamalar.com/c", "ஸ்ரீ சேஷாத்ரி சுவாமிகள் அதிஷ்டானத்தில் ஆராதனை திருவிழா!", t, 97),
              art("https://www.dinamalar.com/f", "டிரெஸ் பர்ச்சேசில் ஏ.ஐ., அணிந்து பார்க்காமலே வாங்கலாம்!", t, 96),
              art("https://www.dinamani.com/k", "திருச்சியில் லாரி மோதி இருவர் பலி", t, 5)]
        pool = {a["id"]: a for a in xs}
        pick.STATE.write_text(json.dumps({"last_end": t.isoformat(), "pool": pool, "rounds": {"2026-11-01_morning": {
            "ids": list(pool), "deadline": t.isoformat(), "written": [], "decided": None, "sent": True}}}))
        with mock.patch.object(pick, "bridge_get", return_value={"ok": True, "submitted": False}), \
                mock.patch.object(pick, "bridge_post", return_value={"ok": True}):
            pick.cmd_decide()
        self.assertEqual(pick.URLS.read_text(), "https://www.dinamani.com/k")
        # the owner ticks the suicide news: it is posted (the owner decides)
        urls, _ = self.decide({"ok": True, "submitted": True, "ids": [pick.pid("https://www.dinamani.com/3")]})
        self.assertEqual(urls, ["https://www.dinamani.com/3"])

    def test_late_ticks_are_added_once(self):
        self.decide({"ok": True, "submitted": False})
        st = json.loads(pick.STATE.read_text())
        rid = next(iter(st["rounds"]))
        not_written = [i for i in st["rounds"][rid]["ids"] if i not in st["rounds"][rid]["written"]]
        with mock.patch.object(pick, "bridge_get", return_value={"ok": True, "submitted": True, "ids": not_written[:2] + st["rounds"][rid]["written"][:1]}):
            pick.cmd_late()
            self.assertEqual(len([l for l in pick.URLS.read_text().split("\n") if l]), 2)
            pick.cmd_late()
            self.assertEqual(pick.URLS.read_text(), "")      # never written twice


class Wiring(unittest.TestCase):
    def test_writer_writes_only_the_picked_links(self):
        src = (ROOT / "research_free" / "collect.py").read_text(encoding="utf-8")
        self.assertIn("if PICK_ONLY:", src)
        wf = (ROOT / ".github" / "workflows" / "pick.yml").read_text(encoding="utf-8")
        for s in ('PICK_ONLY: "1"', 'PICK_EMAIL: "0"', 'PICK_WAIT_MIN: "60"', 'MANUAL_URL="$urls"'):
            self.assertIn(s, wf)

    def test_bridge_has_the_check_box_page(self):
        gs = (ROOT / "apps_script" / "Code.gs").read_text(encoding="utf-8")
        for s in ("function pickList_", "function makePickForm_", "FormApp.openById", "pickStatus_", "function authorizeForms"):
            self.assertIn(s, gs)

class OwnerPickIsPosted(unittest.TestCase):
    """1 Nov: 7 news the owner ticked at 9 AM (published 31 Oct evening) were held by the poster as 'stale: not today'"""
    def test_picked_story_has_no_skip(self):
        sys.path.insert(0, str(ROOT / "poster"))
        import post
        url = "https://www.dinamalar.com/news/tamil-nadu-district-news-trichirappalli/x/1"
        post._PICKED = {pick.pid(url)}
        try:
            row = {"story_id": "RN-1", "source": url, "published": "2020-01-01T10:00:00+05:30", "headline_ta": "செய்தி", "reel_script": "",
                   "caption": ""}
            self.assertTrue(post.owner_picked(row))
            self.assertTrue(post.owner_picked(dict(row, source=url.replace("www.", "l-www."))))
            self.assertFalse(post.owner_picked(dict(row, source="https://www.dinamani.com/other")))
        finally:
            post._PICKED = None

class EndToEndOwnerPick(unittest.TestCase):
    """owner 1 Nov: ticked -> written -> POSTED, for every ticked news. A rule anywhere between (freshness, duplicate, place) may never
    hold a picked news back again, and one that is not posted is reported (the pick workflow then fails loudly)."""
    def test_every_picked_news_goes_through(self):
        sys.path.insert(0, str(ROOT / "poster"))
        import post
        urls = ["https://www.dinamalar.com/news/tamil-nadu-district-news-trichirappalli/old-news/1",          # published yesterday evening
                "https://l-www.dinamalar.com/news/tamil-nadu-district-news-trichirappalli/l-www-link/2",     # listed as l-www, written as www
                "https://www.dinamani.com/all-editions/edition-trichy/trichy/2026/Oct/31/x"]
        rnd = {"ids": [pick.pid(u) for u in urls], "written": [pick.pid(u) for u in urls],
               "decided": {"how": "owner ticked 3", "ids": [pick.pid(u) for u in urls]}}
        post._PICKED = set(rnd["written"])
        posted_before = {"story_id": "RN-1", "headline_ta": "திருச்சி மாநகராட்சி குடிநீர் கட்டணம் உயர்வு இல்லை", "headline_en": "",
                         "post_status": "Posted", "trichy_link": "https://instagram.com/p/x", "researched": "01 Nov 2026, 08:00",
                         "source": "https://other.example/a"}
        rows = []
        for k, u in enumerate(urls):
            rows.append({"story_id": f"RN-{10 + k}", "source": u.replace("l-www.", "www."), "published": "2026-10-20T18:00:00+05:30",
                         "researched": "20 Oct 2026, 18:00", "headline_ta": posted_before["headline_ta"],      # looks like a duplicate
                         "headline_en": "", "category": "Civic", "location": "Chennai", "reel_script": "", "caption": "",
                         "images": "x" * 50, "slides_spec": "{}", "review": "Auto", "post_to": "trichy"})
        old_all = post.ALL_ROWS
        post.ALL_ROWS = rows + [posted_before]
        try:
            for r in rows:
                self.assertEqual(post.skip_reason(r), "", r["story_id"])
        finally:
            post.ALL_ROWS = old_all
            post._PICKED = None
        # verify: 1 posted, 2 waiting -> reported, the workflow retries and then fails loudly
        rows[0]["post_status"] = "Posted"
        post.ALL_ROWS, post._PICKED = rows + [posted_before], set(rnd["written"])      # verify uses the same posting rule as post.py
        try:
            st = pick.picked_status(rnd, rows)
            self.assertEqual(list(st.values()).count("posted"), 1)
            self.assertTrue(all(v.startswith("queued") for k, v in st.items() if v != "posted"), st)
            self.assertEqual(pick.picked_status(rnd, rows[:1])[pick.pid(urls[2])], "not written")
        finally:
            post.ALL_ROWS, post._PICKED = old_all, None

    def test_held_news_is_skipped_not_waiting(self):      # 2 Nov run 41436128396: RN-141/142/143/146 held -> every round red
        rnd = {"written": ["a1", "a2"], "decided": {"ids": ["a1", "a2"]}}
        rows = [{"source": "https://x/a1", "story_id": "RN-141", "post_status": "Queued"},
                {"source": "https://x/a2", "story_id": "RN-144", "post_status": "Queued"}]
        old = (pick.pid, pick._never_posted)
        pick.pid = lambda u: u.rstrip("/").split("/")[-1]
        pick._never_posted = lambda r: "held: fact-check problems - numbers not found in the article: 1000" if r["story_id"] == "RN-141" else ""
        try:
            st = pick.picked_status(rnd, rows)
        finally:
            pick.pid, pick._never_posted = old
        self.assertTrue(st["a1"].startswith("skipped RN-141: held"))
        self.assertTrue(st["a2"].startswith("queued RN-144"))      # still waiting: the run keeps checking / fails if never posted

    def test_never_posted_uses_the_posting_rule(self):
        row = {"story_id": "RN-141", "verification": "NOT CLEAN problems: numbers not found in the article: 1000",
               "location": "திருச்சி, உறையூர்", "source": "", "caption": "", "reel_script": ""}
        import post
        old = post._location_still_wrong, post._real_numbers, post._skip_reason_base
        post._location_still_wrong = lambda r, f: True
        post._real_numbers = lambda p: p
        post._skip_reason_base = lambda r: ""
        try:
            self.assertTrue(pick._never_posted(row).startswith("held: fact-check problems"))
            row["verification"] = "CLEAN"
            self.assertEqual(pick._never_posted(row), "")
        finally:
            post._location_still_wrong, post._real_numbers, post._skip_reason_base = old

    def test_refused_pick_is_skipped_and_not_offered_again(self):      # 3 Nov: the gold-seizure news ('duplicate after write') kept 3 rounds red
        import tempfile
        url = "https://www.dinamalar.com/news/tamil-nadu-district-news-trichirappalli/gold/1"
        k = pick.pid(url)
        st = {"pool": {k: {"url": url, "title": "பெண் பயணி கடத்தி வந்த ரூ.1 கோடி தங்கம் பறிமுதல்"}},
              "rounds": {"2026-11-03_07": {"written": [k], "decided": {"ids": [k]}}}}
        old = pick.REFUSED_FILE
        pick.REFUSED_FILE = Path(tempfile.mkdtemp()) / "pick_refused.json"
        pick.REFUSED_FILE.write_text(json.dumps({url: "not filed: duplicate after write"}), encoding="utf-8")
        try:
            self.assertEqual(pick.mark_refused(st), 1)
        finally:
            pick.REFUSED_FILE = old
        self.assertEqual(st["pool"][k]["refused"], "not filed: duplicate after write")
        rnd = st["rounds"]["2026-11-03_07"]
        self.assertTrue(pick.picked_status(rnd, [])[k].startswith("skipped: the writer refused it"))
        self.assertEqual(pick.picked_status({"written": [k]}, [])[k], "not written")      # not refused -> still reported
        src = (ROOT / "research_free" / "pick.py").read_text(encoding="utf-8")
        self.assertIn('if it.get("refused"):', src)      # never a leftover again

    def test_collect_saves_refusals_for_the_pick(self):
        import collect
        self.assertTrue("not filed: duplicate after write".startswith(collect.REFUSED))
        self.assertFalse("could not open the article: 502".startswith(collect.REFUSED))      # tried again, not refused

    def test_workflow_checks_and_fails_loudly(self):
        wf = (ROOT / ".github" / "workflows" / "pick.yml").read_text(encoding="utf-8")
        self.assertIn("pick.py verify", wf)
        self.assertIn("some picked news is still not posted after 2.5 hours", wf)
        self.assertIn("actions/workflows/post.yml/dispatches", wf)
        # 1 Nov: a manual post.yml run defaults to TEST (dry_run) - every start must say dry_run=false or nothing is posted
        for line in wf.splitlines():
            if "post.yml/dispatches" in line:
                self.assertIn("inputs[dry_run]=false", line)

class RoundOrder(unittest.TestCase):
    """1 Nov: the 4 PM round took the morning round as the latest (text sort: 'evening' < 'morning') and posted nothing"""
    def test_evening_is_latest(self):
        st = {"rounds": {"2026-11-01_morning": {"x": 1}, "2026-11-01_evening": {"x": 2}, "2026-10-31_evening": {"x": 0}}}
        self.assertEqual(pick.current_round(st)[0], "2026-11-01_evening")
        st["rounds"]["2026-11-02_morning"] = {"x": 3}
        self.assertEqual(pick.current_round(st)[0], "2026-11-02_morning")


if __name__ == "__main__":
    unittest.main()


class AutomaticTwentyADay(unittest.TestCase):
    """owner 2 Nov: "do not ask me to confirm" - 20 news a day (8 + 6 + 6) picked automatically from more Tamil outlets"""

    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.old = (pick.STATE, pick.URLS, pick.DRY, pick.EMAIL)
        pick.STATE, pick.URLS, pick.DRY, pick.EMAIL = Path(self.d.name) / "s.json", Path(self.d.name) / "u.txt", False, False
        self._ir, pick.INSIGHT_RANK = pick.INSIGHT_RANK, False      # owner 14 Nov: the insight pick has its own tests
        self.sent = []

    def tearDown(self):
        pick.STATE, pick.URLS, pick.DRY, pick.EMAIL = self.old
        pick.INSIGHT_RANK = getattr(self, "_ir", pick.INSIGHT_RANK)
        self.d.cleanup()

    def collect(self, now, cands, check):
        with mock.patch.object(pick, "now", return_value=now), \
                mock.patch.object(pick, "candidates", side_effect=lambda l, since=None: [dict(c) for c in cands]), \
                mock.patch.object(pick, "check_article", side_effect=check), \
                mock.patch.object(pick, "recent_rows", return_value=[]), \
                mock.patch.object(pick, "is_posted", return_value=False), \
                mock.patch.object(pick, "bridge_post", side_effect=lambda a, p: self.sent.append((a, p)) or {"ok": True}):
            return pick.cmd_collect()

    def test_no_email_and_the_top_news_are_written_at_once(self):
        t = datetime.datetime(2026, 11, 3, 6, 0, tzinfo=IST)
        pick.STATE.write_text(json.dumps({"last_end": (t - datetime.timedelta(hours=9)).isoformat(), "pool": {}, "rounds": {}}))
        heads = ["பீளமேட்டில் நகை திருட்டு", "லால்குடியில் லாரி விபத்து", "துறையூரில் யானை நடமாட்டம்", "குடிநீர் கட்டண உயர்வு ரத்து",
                 "முசிறியில் மின் கம்பம் சாய்ந்தது", "மணப்பாறை சந்தையில் தேங்காய் விலை", "சத்திரம் மேம்பால பணி தாமதம்",
                 "ஸ்ரீரங்கத்தில் கனமழை எச்சரிக்கை", "கிணத்துக்கடவில் பள்ளி மாணவர் சாதனை", "ரயில் நேர மாற்றம் அறிவிப்பு"]
        arts = {f"https://www.dinakaran.com/n{i}": art(f"https://www.dinakaran.com/n{i}", heads[i], t - datetime.timedelta(hours=1), i) for i in range(10)}
        rid = self.collect(t, [{"url": u} for u in arts], lambda it, r: (dict(arts[it["url"]]), ""))
        self.assertEqual(rid, "2026-11-03_06")
        self.assertFalse([a for a, _ in self.sent if a == "pickList"])      # nothing e-mailed
        with mock.patch.object(pick, "bridge_get", side_effect=AssertionError("must not wait for the owner")), \
                mock.patch.object(pick, "bridge_post", return_value={"ok": True}), mock.patch.object(pick, "AUTO_TOP", 8):
            pick.cmd_decide()
        self.assertEqual(len([l for l in pick.URLS.read_text().split("\n") if l]), 8)

    def test_a_link_that_failed_to_open_is_tried_again_next_round(self):
        t = datetime.datetime(2026, 11, 3, 6, 0, tzinfo=IST)
        pick.STATE.write_text(json.dumps({"last_end": (t - datetime.timedelta(hours=9)).isoformat(), "pool": {}, "rounds": {}}))
        u = "https://www.dinamalar.com/news/tamil-nadu-district-news-trichirappalli/x/123456"
        a = art(u, "திருச்சியில் விபத்து", t - datetime.timedelta(hours=2))
        self.collect(t, [{"url": u}], lambda it, r: (None, "could not open (502)"))
        self.assertIn(u, json.loads(pick.STATE.read_text())["retry"])
        t2 = t + datetime.timedelta(hours=4)      # the next round: the link is not in the papers' lists any more
        self.collect(t2, [], lambda it, r: (dict(a), ""))
        st = json.loads(pick.STATE.read_text())
        self.assertIn(a["id"], st["pool"])      # listed although published before this window
        self.assertNotIn(u, st["retry"])

    def test_round_names_by_hour_sort_with_the_old_names(self):
        self.assertLess(pick.round_order("2026-11-02_morning"), pick.round_order("2026-11-02_10"))
        self.assertLess(pick.round_order("2026-11-02_10"), pick.round_order("2026-11-02_evening"))
        self.assertLess(pick.round_order("2026-11-02_evening"), pick.round_order("2026-11-02_19"))

    def test_more_outlets(self):
        src = (ROOT / "research_free" / "pick.py").read_text(encoding="utf-8")
        for d in ("dinakaran.com", "dailythanthi.com", "maalaimalar.com", "hindutamil.in", "polimernews.com"):
            self.assertIn(d, pick.OUTLETS)
        self.assertIn("any(d in cfg[\"url\"] for d in OUTLETS)", src)

    def test_a_picked_news_never_written_comes_back(self):
        t = datetime.datetime(2026, 11, 3, 10, 0, tzinfo=IST)
        a = art("https://www.dinamani.com/p", "திருச்சி குடிநீர் பிரச்சனை", t - datetime.timedelta(hours=5))
        for picked_h, listed in ((1, False), (4, True)):
            pool = {a["id"]: dict(a, listed_at=(t - datetime.timedelta(hours=5)).isoformat(), picked_at=(t - datetime.timedelta(hours=picked_h)).isoformat())}
            pick.STATE.write_text(json.dumps({"last_end": (t - datetime.timedelta(hours=4)).isoformat(), "pool": pool, "rounds": {}}))
            self.collect(t, [], lambda it, r: (None, "x"))
            ids = json.loads(pick.STATE.read_text())["rounds"].get("2026-11-03_10", {}).get("ids", [])
            self.assertEqual(a["id"] in ids, listed, picked_h)

    def test_a_failed_link_still_in_the_list_is_a_retry_too(self):
        t = datetime.datetime(2026, 11, 3, 6, 0, tzinfo=IST)
        pick.STATE.write_text(json.dumps({"last_end": (t - datetime.timedelta(hours=9)).isoformat(), "pool": {}, "rounds": {}}))
        u = "https://www.dinamalar.com/news/tamil-nadu-district-news-trichirappalli/y/654321"
        a = art(u, "திருச்சியில் தீ விபத்து", t - datetime.timedelta(hours=1))
        self.collect(t, [{"url": u}], lambda it, r: (None, "could not open (502)"))
        self.collect(t + datetime.timedelta(hours=4), [{"url": u}], lambda it, r: (dict(a), ""))      # still in the paper's list
        self.assertIn(a["id"], json.loads(pick.STATE.read_text())["pool"])

