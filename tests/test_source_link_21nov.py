"""owner 21 Nov: only news with its source link is written and posted; every news reel gets the source comment (tried twice);
the day's maximum is exact; the watchdog's rounds and the pick counts follow the 4-hourly collection"""
import re
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "poster"))
import post      # noqa: E402

LINK = "https://www.dinamalar.com/news/tamil-nadu/x/1"
ROW = {"story_id": "RN-1", "headline_ta": "சாலை சீரமைப்புப் பணி தொடக்கம்", "headline_en": "road work begins", "category": "civic",
       "published": "21 Nov 2026", "source": LINK}


def ist_hours(wf_text):
    return sorted(((int(h) * 60 + int(m) + 330) % 1440) / 60 for m, hs in re.findall(r'cron: "(\d+) ([\d,]+) \* \* \*"', wf_text)
                  for h in hs.split(","))


class OnlyNewsWithItsSourceLink(unittest.TestCase):
    def test_no_link_is_held(self):
        for src in ("", "தினமலர்", "manual", "www.dinamalar.com/news/1"):
            self.assertIn("no source link", post.link_hold(dict(ROW, source=src)), src)
        self.assertEqual(post.link_hold(ROW), "")

    def test_owner_ready_reel_posts_as_it_is(self):
        with mock.patch.object(post, "is_ready_reel", return_value=True):
            self.assertEqual(post.link_hold(dict(ROW, source="")), "")

    def test_nothing_written_without_a_link(self):
        src = (ROOT / "research_free" / "collect.py").read_text(encoding="utf-8")
        prep = src[src.index("    def prepare("):] if "    def prepare(" in src else src
        guard = prep.index('"skip": "no source link"')
        self.assertLess(guard, prep.index("file_story(") if "file_story(" in prep else len(prep))


class SourceCommentOnEveryReel(unittest.TestCase):
    def sent(self, row, errors=()):
        got, errs = [], list(errors)
        def ig(method, path, token, **kw):
            if errs:
                raise RuntimeError(errs.pop(0))
            got.append(kw["message"])
            return {"id": "c"}
        with mock.patch.object(post, "ig", side_effect=ig) as m, mock.patch.object(post.time, "sleep"), \
                mock.patch.dict(post.CONFIG, {"first_comment": True}):
            post.first_comment("t", "m", "RN-1", row)
        return got, m.call_count

    def test_comment_has_the_link(self):
        got, _ = self.sent(ROW)
        self.assertEqual(len(got), 1)
        self.assertIn(LINK, got[0])
        self.assertTrue(post.is_source_comment(got[0]))

    def test_tried_again_once(self):
        got, calls = self.sent(ROW, ["Instagram m/comments: {'is_transient': True, 'code': 2}"])
        self.assertEqual((len(got), calls), (1, 2))
        got, calls = self.sent(ROW, ["Instagram m/comments: (#10) permission denied"])      # a real refusal: not repeated
        self.assertEqual((len(got), calls), (0, 1))

    def test_owner_ready_reel_too(self):
        src = (ROOT / "poster" / "post.py").read_text(encoding="utf-8")
        ready = src[src.index("def run_ready_reel("):]
        ready = ready[:ready.index("\ndef ", 10)]
        self.assertIn("first_comment(token, mid, sid, row)", ready)
        self.assertNotIn("உள்ளூர் செய்தி ஆதாரங்கள்", src)      # no comment without a real source


class DailyMaximumAndRounds(unittest.TestCase):
    def test_round_never_past_the_maximum(self):
        src = (ROOT / "research_free" / "collect.py").read_text(encoding="utf-8")
        self.assertIn("room = DAILY_CAP - TODAY[0]", src)
        self.assertLess(src.index("room = DAILY_CAP - TODAY[0]"), src.index("    if TODAY[0] >= DAILY_CAP:"))

    def test_capped_picks_are_skipped_not_failed(self):
        if not (ROOT / ".github" / "workflows" / "pick.yml").exists():
            self.skipTest("this repository collects with research_free.yml")
        src = (ROOT / "research_free" / "collect.py").read_text(encoding="utf-8")
        self.assertIn("not written: the day's maximum of", src)
        refused = re.search(r"^REFUSED = \(([^)]*)", src, re.M).group(1)
        self.assertIn('"not written"', refused)      # pick.py verify counts it as skipped on purpose

    def test_watchdog_rounds_are_the_collection_times(self):
        import watchdog
        wf = ROOT / ".github" / "workflows" / ("pick.yml" if (ROOT / ".github" / "workflows" / "pick.yml").exists() else "research_free.yml")
        self.assertEqual(ist_hours(wf.read_text(encoding="utf-8")), [h + m / 60 for h, m in watchdog.ROUNDS])
        self.assertEqual(watchdog.ROUNDS, ((4, 0), (8, 0), (12, 0), (16, 0), (20, 0), (22, 0)))

    def test_pick_counts_follow_the_rounds(self):
        wf = ROOT / ".github" / "workflows" / "pick.yml"
        if not wf.exists():
            self.skipTest("this repository collects with research_free.yml")
        top = re.search(r'PICK_ROUND_TOP: "([^"]+)"', wf.read_text(encoding="utf-8")).group(1)
        slots = [tuple(map(int, x.split("="))) for x in top.split(",")]
        self.assertEqual([h for h, _ in slots], [4, 8, 12, 16, 20, 22])
        self.assertLessEqual(sum(n for _, n in slots), 35)
        self.assertIn('DAILY_CAP: "30"', wf.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
