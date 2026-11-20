"""owner 20 Nov: the reel length stays the FULL news - 70-160 words, at most 88-90 s ("news details are not fully covered in 45 s");
19 Nov kept: sentence 1 is short with the strongest fact; active voice; respectful words for deaths."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research_free"))
sys.path.insert(0, str(ROOT / "poster"))


class FullNewsLength(unittest.TestCase):
    def test_reel_up_to_90_seconds_and_160_words(self):
        c = json.loads((ROOT / "poster" / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(88, c["reel_max_seconds"])
        self.assertEqual(160, c["reach"]["script_max_words"])
        rules = (ROOT / "research_free" / "rules.md").read_text(encoding="utf-8")
        self.assertIn("70-160 words", rules)
        self.assertNotIn("60-90 words", rules)


class WriterRules(unittest.TestCase):
    rules = (ROOT / "research_free" / "rules.md").read_text(encoding="utf-8")

    def test_short_first_sentence_strongest_fact(self):
        self.assertIn("5-7 words, about 3 seconds", self.rules)
        self.assertIn("The strongest fact first", self.rules)

    def test_active_voice_and_death_words(self):
        self.assertIn("ACTIVE voice", self.rules)
        self.assertIn("never \"சாவு\"", self.rules)


if __name__ == "__main__":
    unittest.main()
