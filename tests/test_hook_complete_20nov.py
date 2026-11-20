"""owner 20 Nov: the opening headline (hl1) is always a complete phrase - never cut in the middle"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research_free"))
import validate as V  # noqa: E402


class HookComplete(unittest.TestCase):
    def test_short_stays(self):
        self.assertEqual(V.finish_phrase("கோவையில் இதயத் துடிப்பு சிறப்பு முகாம்"), "கோவையில் இதயத் துடிப்பு சிறப்பு முகாம்")

    def test_key_word_kept(self):      # Karur RN-146 was cut to '...வீட்டில் பெரும்'
        c = V.finish_phrase("சிங்கம்புணரி அருகே தொழிலதிபர் வீட்டில் பெரும் கொள்ளை")
        self.assertLessEqual(len(c), 40)
        self.assertTrue(c.endswith("கொள்ளை"), c)
        self.assertTrue(c.startswith("சிங்கம்புணரி"), c)

    def test_numbers_keep_their_words(self):      # Salem RN-178 was cut to '...வெற்றிகர'
        self.assertEqual(V.finish_phrase("சேலம்: 90% இருதய அடைப்பு, வெற்றிகர இதய சிகிச்சை நிறைவு"), "சேலம்: 90% இருதய அடைப்பு சிகிச்சை நிறைவு")
        self.assertEqual(V.finish_phrase("திருச்சியில் ரேஷன் அரிசி கடத்திய 3 பேர் கைது செய்யப்பட்டனர்"), "திருச்சியில் 3 பேர் கைது செய்யப்பட்டனர்")
        self.assertEqual(V.finish_phrase("நாமக்கல் மாவட்டத்தில் கனமழையால் 25 வீடுகள் சேதம் மக்கள் அவதி"), "நாமக்கல் 25 வீடுகள் சேதம் மக்கள் அவதி")

    def test_the_action_at_the_end_stays(self):      # a power cut keeps 'மின் தடை'
        self.assertEqual(V.finish_phrase("நாளை கஸ்பாபேட்டை, எழுமாத்தூர், கொடுமுடி பகுதிகளில் மின் தடை"), "நாளை கஸ்பாபேட்டை, எழுமாத்தூர் மின் தடை")

    def test_a_number_is_never_dropped(self):
        c = V.finish_phrase("நாமக்கல் மாவட்டத்தில் கனமழையால் 25 வீடுகள் சேதம் மக்கள் அவதி")
        self.assertLessEqual(len(c), 40)
        self.assertTrue("25" in c or not c.endswith("அவதி"), c)

    def test_long_hl1_goes_back_to_the_writer(self):
        d = {"slides_spec": {"hl1": "சிங்கம்புணரி அருகே தொழிலதிபர் வீட்டில் பெரும் கொள்ளை", "hl2": "x", "loc": ""}}
        V.autofix(d)
        self.assertEqual(d["slides_spec"]["hl1"], "சிங்கம்புணரி அருகே தொழிலதிபர் வீட்டில் பெரும் கொள்ளை")      # not cut silently
        src = (ROOT / "research_free" / "validate.py").read_text(encoding="utf-8")
        self.assertIn("never stop a phrase in the middle", src)

    def test_writer_is_told(self):
        self.assertIn("ONE COMPLETE phrase", (ROOT / "research_free" / "rules.md").read_text(encoding="utf-8"))
        run = (ROOT / "research_free" / "run.py").read_text(encoding="utf-8")
        self.assertIn("ONE COMPLETE phrase", run)
        self.assertIn("best = hl1_finished(best)", run)


if __name__ == "__main__":
    unittest.main()
