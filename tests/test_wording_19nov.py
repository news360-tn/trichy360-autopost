"""19 Nov audit of 7 days of reel scripts (real cases): what the voice reads and how the reel splits its sentences."""
import datetime
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research_free"))
sys.path.insert(0, str(ROOT / "poster"))
import names      # noqa: E402
import post       # noqa: E402

D = datetime.date


class VoiceWords(unittest.TestCase):
    def test_two_letter_initials_are_letters(self):
        self.assertEqual(names.spoken("ஆணையர் ஆர்.வி. ஜெயக்குமார் தெரிவித்தார்."), "ஆணையர் ஆர் வி ஜெயக்குமார் தெரிவித்தார்.")
        self.assertIn("கே கே நகர்", names.spoken("கே.கே. நகர் பகுதியில் மின்தடை."))
        self.assertIn("தி மு க", names.spoken("தி.மு.க. கூட்டம் நடந்தது."))      # three letters: as before

    def test_party_names_letter_by_letter(self):
        out = names.spoken("அதிமுக, திமுகவினர் மற்றும் தவெக நிர்வாகிகள்.")
        self.assertIn("அ தி மு க,", out)
        self.assertIn("தி மு க வினர்", out)
        self.assertIn("த வெ க நிர்வாகிகள்", out)
        self.assertNotIn("திமுக", out)

    def test_symbols_the_voice_dropped(self):
        self.assertIn("எல் அண்ட் டி பைபாஸ்", names.spoken("கொச்சி L&T பைபாஸ் சாலையில்"))
        self.assertIn("4 இன்டு 400 மீட்டர்", names.spoken("4 X 400 மீட்டர் தொடர் ஓட்டத்தில்"))
        self.assertIn("300 மில்லிமீட்டர் குழாய்", names.spoken("சாலையில் 300 எம்.எம். குழாய் உடைந்தது."))

    def test_ordinary_words_untouched(self):
        t = "போலீசார் வழக்குப் பதிவு செய்தனர்."
        self.assertEqual(names.spoken(t), t)


class Sentences(unittest.TestCase):
    def test_initials_do_not_end_a_sentence(self):
        s = post.split_sentences("காவல் ஆணையருமான ஆர்.வி. ஜெயக்குமார் ஆய்வு செய்தார். சாலையில் 300 எம்.எம். குழாய் உடைந்தது. மக்கள் அவதி.")
        self.assertEqual(len(s), 3)
        self.assertTrue(s[0].endswith("ஆய்வு செய்தார்."))
        self.assertIn("300 எம்.எம். குழாய்", s[1])

    def test_normal_split_unchanged(self):
        self.assertEqual(post.split_sentences("ஒன்று நடந்தது. இரண்டு நடந்தது! மூன்று?"), ["ஒன்று நடந்தது.", "இரண்டு நடந்தது!", "மூன்று?"])


class RelativeDays(unittest.TestCase):
    def test_posted_next_day(self):
        self.assertEqual(post.fix_relative_days("நேற்று இரவு விபத்து நடந்தது.", D(2026, 11, 12), D(2026, 11, 15)),
                         "நவம்பர் 11ஆம் தேதி இரவு விபத்து நடந்தது.")
        self.assertEqual(post.fix_relative_days("இன்று காலை முகாம், நாளை மறுநாள் கூட்டம்.", D(2026, 11, 13), D(2026, 11, 14)),
                         "நவம்பர் 13ஆம் தேதி காலை முகாம், நவம்பர் 15ஆம் தேதி கூட்டம்.")
        self.assertEqual(post.fix_relative_days("நேற்று முன்தினம்", D(2026, 11, 1), D(2026, 11, 2)), "அக்டோபர் 30ஆம் தேதி")

    def test_same_day_and_other_words_unchanged(self):
        self.assertEqual(post.fix_relative_days("இன்று மின்தடை.", D(2026, 11, 19), D(2026, 11, 19)), "இன்று மின்தடை.")
        self.assertEqual(post.fix_relative_days("இன்றைய விலை.", D(2026, 11, 18), D(2026, 11, 19)), "இன்றைய விலை.")


class Filler(unittest.TestCase):
    def test_filler_only_sentence(self):
        self.assertTrue(post.FILLER_ONLY.match("இந்தச் சம்பவம் அந்தப் பகுதியில் பெரும் பரபரப்பை ஏற்படுத்தியுள்ளது."))
        self.assertTrue(post.FILLER_ONLY.match("இந்த சம்பவத்தால் அப்பகுதியில் சோகத்தை ஏற்படுத்தியது."))
        self.assertFalse(post.FILLER_ONLY.match("மகன் தந்தையைத் தாக்கியதால் பரபரப்பு ஏற்பட்டது."))      # has a fact: kept


if __name__ == "__main__":
    unittest.main()
