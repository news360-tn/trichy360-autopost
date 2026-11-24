"""owner 24 Nov: a news held by the fact-check is written again (problems told to the writer), checked again, and posted with the
corrected text (poster/fixed/<story>.json read by post.apply_fixes). A draft still holding a fact problem is never used."""
import json, sys, tempfile, unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research_free"))
sys.path.insert(0, str(ROOT / "poster"))
import post      # noqa: E402
import autofix      # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))
NOW = datetime.now(IST)
HELD = "DRAFT (x) - NOT CLEAN, held from posting - problems: fact-check: the caption gives an age (55) that the article does not state"


def row(**k):
    r = {"story_id": "RN-9", "row": 10, "source": "https://www.dinamalar.com/news/a/1", "published": NOW.isoformat(), "verification": HELD,
         "headline_ta": "பழைய தலைப்பு", "caption": "old", "reel_script": "old", "location": "ஊர், மாவட்டம்", "images": "https://img/1.jpg"}
    r.update(k)
    return r


class AutoFix24Nov(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.p = [mock.patch.object(autofix, "FIX", self.tmp), mock.patch.object(autofix, "TRIES", self.tmp / "_tries.json"),
                  mock.patch.object(post, "FIXED_DIR", self.tmp)]
        for x in self.p:
            x.start()

    def tearDown(self):
        for x in self.p:
            x.stop()

    def test_only_todays_fact_held_news(self):
        with mock.patch.object(post, "page_done", return_value=False), \
                mock.patch.object(post, "news_hold", side_effect=lambda r: "held: fact-check problems - x" if "NOT CLEAN" in r["verification"] else ""):
            old = (NOW - timedelta(days=3)).isoformat()
            got = autofix.candidates([row(), row(story_id="RN-8", verification="DRAFT - fact-check: no problems found"),
                                      row(story_id="RN-7", published=old)], NOW)
        self.assertEqual([r["story_id"] for r in got], ["RN-9"])

    def test_clean_rewrite_is_saved_and_used_for_posting(self):
        story = {"tamil_headline": "சரியான தலைப்பு", "english_headline": "Right", "caption": "new caption", "reel_script": "new script",
                 "location": "ஊர், மாவட்டம்", "slides_spec": {"v": 3, "slides": []}, "verification": "DRAFT (y) - fact-check: no problems found"}
        with mock.patch.object(post, "bridge_get", return_value={"ok": True, "rows": [row()]}), \
                mock.patch.object(autofix, "candidates", side_effect=lambda rows, now: rows), \
                mock.patch.object(autofix.allnews, "article_any", return_value={"title": "t", "text": "x"}), \
                mock.patch.object(autofix.run, "write", return_value=({}, "y", [], 1)), \
                mock.patch.object(autofix.collect, "file_story", return_value=(story, "")), \
                mock.patch.object(post, "news_hold", return_value=""):
            autofix.main()
            self.assertIn("55", autofix.run.EXTRA[0])      # the writer was told the mistakes of the first version
        d = json.loads((self.tmp / "RN-9.json").read_text(encoding="utf-8"))
        self.assertEqual(d["caption"], "new caption")
        rows = post.apply_fixes([row()])
        self.assertEqual((rows[0]["headline_ta"], rows[0]["reel_script"]), ("சரியான தலைப்பு", "new script"))
        self.assertTrue(rows[0]["verification"].startswith("AUTO-FIXED"))
        other = post.apply_fixes([row(source="https://other/2")])      # a different source: never overwritten
        self.assertEqual(other[0]["caption"], "old")

    def test_still_held_draft_is_not_used(self):
        story = {"tamil_headline": "x", "english_headline": "x", "caption": "c", "reel_script": "s", "slides_spec": {"v": 3},
                 "verification": HELD}
        with mock.patch.object(post, "bridge_get", return_value={"ok": True, "rows": [row()]}), \
                mock.patch.object(autofix, "candidates", side_effect=lambda rows, now: rows), \
                mock.patch.object(autofix.allnews, "article_any", return_value={"title": "t", "text": "x"}), \
                mock.patch.object(autofix.run, "write", return_value=({}, "y", [], 1)), \
                mock.patch.object(autofix.collect, "file_story", return_value=(story, "")), \
                mock.patch.object(post, "news_hold", return_value="held: fact-check problems - again"):
            autofix.main()
            autofix.main()
            autofix.main()      # a third run: the 2-try limit is reached
        self.assertFalse((self.tmp / "RN-9.json").exists())
        self.assertEqual(json.loads((self.tmp / "_tries.json").read_text())["RN-9"], 2)


if __name__ == "__main__":
    unittest.main()
