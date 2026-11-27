"""owner 27 Nov ("do not miss power cut news"): power cuts were written but HELD by the fact-check and never posted.
- Dinamani prints ர் as ா் ('குமாா் நகா்'): the place word 'நகர்' was 'not in the article' (Tirupur RN-259).
- autofix.py never fixed them: the free writers answered 429 / 413 and the run stopped at the first news. Now power cuts go first,
  by their cut day, a 413 / 400 for one news does not stop the run, and only a power cut may use the paid backup (AUTOFIX_CLAUDE).
- powercut.py verify counted a held power cut as 'never posted on purpose' - now it fails (and the workflow rewrites it).
No network."""
import json, os, sys, tempfile, unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research_free"))
sys.path.insert(0, str(ROOT / "poster"))
import post      # noqa: E402
import validate      # noqa: E402
import autofix      # noqa: E402
import llm      # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))
NOW = datetime.now(IST)
ARTICLE = ("குமாா் நகா் துணை மின் நிலையத்தில் பராமரிப்புப் பணிகள் நடைபெறுவதால் நாளை காலை 9 முதல் மாலை 5 மணி வரை மின் விநியோகம் "
           "இருக்காது என மின்வாரியம் தெரிவித்துள்ளது. குமாா் நகா், அனுப்பா்பாளையம், திலகா் நகா் ஆகிய பகுதிகளில் மின்தடை.")
HELD = "DRAFT (x) - NOT CLEAN, held from posting - problems: numbers not found in the article: 13"


class OldPrintForms(unittest.TestCase):
    def test_ra_written_as_aa_virama(self):
        self.assertEqual(validate._stem("நகா்"), validate._stem("நகர்"))
        self.assertEqual(validate._stem("குமாா்"), validate._stem("குமார்"))
        self.assertEqual(validate._stem("வேலுார்"), validate._stem("வேலூர்"))

    def test_kumar_nagar_headline_is_grounded(self):
        d = {"tamil_headline": "குமார் நகர் பகுதியில் நாளை மின்தடை", "slides_spec": {"loc": "குமார் நகர்"},
             "reel_script": "", "caption": ""}
        self.assertEqual([p for p in validate.grounding_problems(d, ARTICLE) if p.startswith("not grounded")], [])

    def test_invented_place_still_held(self):
        d = {"tamil_headline": "சின்னப்பாளையம் பகுதியில் நாளை மின்தடை", "slides_spec": {"loc": "குமார் நகர்"}, "reel_script": "", "caption": ""}
        self.assertTrue(any("சின்னப்பாளையம்" in p for p in validate.grounding_problems(d, ARTICLE)))

    def test_saved_place_word_note_judged_again(self):
        row = {"story_id": "RN-259", "source": "https://www.dinamani.com/x", "headline_ta": "நாளைய மின்தடை: குமார் நகர்",
               "slides_spec": json.dumps({"loc": "குமார் நகர், திருப்பூர்"}, ensure_ascii=False),
               "verification": "DRAFT - NOT CLEAN - problems: not grounded: place word 'நகர்' is not in the article"}
        with mock.patch.dict(post._ARTICLE_TEXT, {row["source"]: ARTICLE * 3}):
            self.assertFalse(post._location_still_wrong(row, "not grounded: place word 'நகர்' is not in the article"))


def row(**k):
    r = {"story_id": "RN-9", "row": 10, "source": "https://www.dinamani.com/a/1", "published": NOW.isoformat(), "verification": HELD,
         "headline_ta": "பழைய தலைப்பு", "headline_en": "", "caption": "old", "reel_script": "old", "location": "ஊர்", "images": "https://img/1.jpg"}
    r.update(k)
    return r


class AutofixPowerCut(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.p = [mock.patch.object(autofix, "FIX", self.tmp), mock.patch.object(autofix, "TRIES", self.tmp / "_tries.json"),
                  mock.patch.object(post, "FIXED_DIR", self.tmp), mock.patch.object(post, "page_done", return_value=False),
                  mock.patch.object(post, "news_hold", return_value="held: fact-check problems - numbers not found in the article: 13")]
        for x in self.p:
            x.start()

    def tearDown(self):
        for x in self.p:
            x.stop()

    def test_power_cut_first_and_by_cut_day(self):
        two_days = (NOW - timedelta(days=2)).isoformat()      # printed 2 days ago; the cut is today
        day = f"{NOW.day:02d}.{NOW.month:02d}.{NOW.year % 100:02d}"
        rows = [row(story_id="RN-1", headline_ta="விபத்தில் ஒருவர் காயம்"),
                row(story_id="RN-2", headline_ta=f"{day} மின்தடை: பொங்கலூர்", headline_en="Power cut", published=two_days),
                row(story_id="RN-3", headline_ta="சாலை விபத்து", published=two_days)]
        with mock.patch.object(autofix.freshness, "power_cut_over", return_value=False):
            got = [r["story_id"] for r in autofix.candidates(rows, NOW)]
        self.assertEqual(got, ["RN-2", "RN-1"])

    def test_one_refused_news_does_not_stop_the_run(self):
        calls = []

        def rewrite(r, now):
            calls.append(r["story_id"])
            return (None, "all free models failed: groq qwen 413: Request too large") if r["story_id"] == "RN-1" else (None, "still held: x")
        with mock.patch.object(post, "bridge_get", return_value={"rows": [row(story_id="RN-1"), row(story_id="RN-2")]}), \
                mock.patch.object(autofix, "candidates", side_effect=lambda rows, now: rows), \
                mock.patch.object(autofix, "rewrite", side_effect=rewrite):
            autofix.main()
        self.assertEqual(calls, ["RN-1", "RN-2"])
        self.assertEqual(json.loads((self.tmp / "_tries.json").read_text())["RN-1"], 1)      # counted

    def test_rate_limit_stops_other_news_not_power_cuts(self):
        calls = []

        def rewrite(r, now):
            calls.append(r["story_id"])
            return None, "all free models failed: no free model answered: groq 429: Rate limit reached"
        rows = [row(story_id="RN-1"), row(story_id="RN-2"), row(story_id="RN-3", headline_ta="நாளை மின்தடை: அவிநாசி")]
        with mock.patch.object(post, "bridge_get", return_value={"rows": rows}), \
                mock.patch.object(autofix, "candidates", side_effect=lambda rows, now: rows), \
                mock.patch.object(autofix, "rewrite", side_effect=rewrite):
            autofix.main()
        self.assertEqual(calls, ["RN-1", "RN-3"])
        self.assertNotIn("RN-1", {k: v for k, v in json.loads((self.tmp / "_tries.json").read_text()).items() if v})

    def test_paid_backup_only_for_power_cuts(self):
        seen = {}

        def rewrite(r, now):
            seen[r["story_id"]] = llm.claude_available()
            return None, "still held: x"
        rows = [row(story_id="RN-5", headline_ta="நாளை மின்தடை: அவிநாசி"), row(story_id="RN-6"), row(story_id="RN-7", headline_ta="மின்தடை: பல்லடம்")]
        env = {"AUTOFIX_CLAUDE": "power_cut", "ANTHROPIC_API_KEY": "x"}
        with mock.patch.dict(os.environ, env), mock.patch.object(llm, "CLAUDE_MAX", 12), mock.patch.object(llm, "CLAUDE_CALLS", [0]), \
                mock.patch.object(post, "bridge_get", return_value={"rows": rows}), \
                mock.patch.object(autofix, "candidates", side_effect=lambda rows, now: rows), \
                mock.patch.object(autofix, "rewrite", side_effect=rewrite):
            autofix.main()
            self.assertEqual(llm.CLAUDE_CALLS[0], 0)      # the real count is back after the run
        self.assertEqual(seen, {"RN-5": True, "RN-6": False, "RN-7": True})

    def test_powercut_mode_only_power_cuts(self):
        calls = []
        rows = [row(story_id="RN-1"), row(story_id="RN-2", headline_ta="நாளை மின்தடை: அவிநாசி")]
        with mock.patch.object(post, "bridge_get", return_value={"rows": rows}), \
                mock.patch.object(autofix, "candidates", side_effect=lambda rows, now: rows), \
                mock.patch.object(autofix, "rewrite", side_effect=lambda r, now: (calls.append(r["story_id"]), (None, "x"))[1]):
            autofix.main(power_cut_only=True)
        self.assertEqual(calls, ["RN-2"])


class Workflows(unittest.TestCase):
    def test_powercut_job_rewrites_held_notices(self):
        t = (ROOT / ".github" / "workflows" / "powercut.yml").read_text(encoding="utf-8")
        self.assertGreaterEqual(t.count("autofix.py powercut"), 2)      # right after writing, and in the verify loop
        self.assertIn("poster/fixed", t)


if __name__ == "__main__":
    unittest.main()
