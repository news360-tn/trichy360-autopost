"""owner 21 Nov (Instagram-safe): the story share only for power cuts / urgent news on every page, as Kovai and Chennai Minnal do"""
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "poster"))
import post      # noqa: E402

PLAIN = {"story_id": "RN-1", "headline_ta": "சாலை சீரமைப்புப் பணி தொடக்கம்", "headline_en": "road work", "category": "civic", "importance": "Medium"}
CUT = {"story_id": "RN-2", "headline_ta": "நாளை மின் தடை: பகுதிகள் விவரம்", "headline_en": "power cut tomorrow", "category": "மின் தடை",
       "importance": "High"}


class UrgentStoriesOnly(unittest.TestCase):
    def test_switched_on(self):
        cfg = json.loads((ROOT / "poster" / "config.json").read_text(encoding="utf-8"))
        self.assertIs(cfg["stories_urgent_only"], True)

    def test_only_urgent_news_gets_a_story(self):
        with mock.patch.dict(post.CONFIG, {"stories_urgent_only": True}):
            self.assertFalse(post.wants_story(PLAIN))
            self.assertTrue(post.wants_story(CUT))
            with mock.patch.object(post, "ig") as ig:
                self.assertEqual(post.publish_story("t", "https://x/v.mp4", "video", PLAIN), "")
                ig.assert_not_called()

    def test_every_caller_passes_the_news(self):
        src = (ROOT / "poster" / "post.py").read_text(encoding="utf-8")
        calls = [l.strip() for l in src.splitlines() if l.strip().startswith("publish_story(token")]
        self.assertTrue(calls)
        for c in calls:
            self.assertTrue(c.endswith(", row)"), c)
        catch = src[src.index("def story_catchup("):]
        self.assertIn("if urgent_stories_only()", catch[:catch.index("\ndef ", 10)])


if __name__ == "__main__":
    unittest.main()
