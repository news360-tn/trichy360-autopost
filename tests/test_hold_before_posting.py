import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "poster"))
import post


class HoldBeforePosting(unittest.TestCase):
    """owner 2 Nov (RN-272): a draft with fact-check problems, or an unknown location, is never posted"""

    def row(self, **kw):
        base = dict(verification="DRAFT (m) - fact-check: no problems found", location="Tiruchengode town, Namakkal district", caption="x", reel_script="y",
                    source="", published="", headline_ta="", category="", notes="", batch="", review="Auto")
        base.update(kw)
        return base

    def test_fact_check_problem_is_held(self):
        r = self.row(verification="DRAFT (m) - NOT CLEAN, held from posting - problems: fact-check: wrong vehicle")
        self.assertTrue(post.skip_reason(r).startswith("held: fact-check problems"))

    def test_unknown_location_is_held(self):
        self.assertEqual(post.skip_reason(self.row(caption="இடம்: தெரியவில்லை")), "held: location unknown")
        self.assertEqual(post.skip_reason(self.row(location="unknown")), "held: location unknown")

    def test_clean_row_is_not_held_by_the_new_rules(self):
        self.assertNotIn("held:", post.skip_reason(self.row()))

    def test_district_only_location_is_held(self):
        self.assertTrue(post.skip_reason(self.row(location="Namakkal district")).startswith("held: location is only the district"))

    def test_town_and_district_is_fine(self):
        self.assertNotIn("held:", post.skip_reason(self.row(location="Tiruchengode town, Namakkal district")))

    def test_ready_reel_is_held_too(self):
        r = self.row(caption="இடம்: தெரியவில்லை", location="Namakkal district")
        self.assertTrue(post.news_hold(r).startswith("held:"))


class FormattingOnlyPosts(unittest.TestCase):
    """owner 2 Nov: formatting-only fact-check flags do not hold a story; factual flags do"""

    def row(self, verification):
        return dict(verification=verification, location="Tiruchengode town, Namakkal district", caption="x", reel_script="y",
                    source="", published="", headline_ta="", category="", notes="", batch="", review="Auto")

    def test_formatting_only_posts(self):
        r = self.row("DRAFT (m) - NOT CLEAN, held from posting - problems: reel_script has 84 words; need 85-105; sentence 1 has 14 words")
        self.assertEqual(post.news_hold(r), "")

    def test_fact_check_flag_about_cut_off_text_posts(self):
        r = self.row("DRAFT (m) - NOT CLEAN, held from posting - problems: fact-check: The slides_spec slide's third line is cut off mid-sentence ('x')")
        self.assertEqual(post.news_hold(r), "")

    def test_factual_problem_is_held(self):
        r = self.row("DRAFT (m) - NOT CLEAN, held from posting - problems: reel_script has 84 words; fact-check: caption misses facts of the article")
        self.assertTrue(post.news_hold(r).startswith("held: fact-check problems"))


class Recheck3Nov(unittest.TestCase):
    """owner 3 Nov: numbers written in words, incomplete-sentence flags, and a district-only location whose story names the town"""

    def test_numbers_in_words_are_in_the_article(self):
        art = "சுமார் 10 ஆயிரம் பேர் கலந்து கொண்டனர். ஆறு பேர் காயம். 1,500 ரூபாய்"
        for n in ("10000", "6", "1500"):
            self.assertTrue(post._number_in_article(n, art), n)
        self.assertFalse(post._number_in_article("9547", art))

    def test_incomplete_sentence_flag_posts(self):
        r = dict(verification="DRAFT (m) - NOT CLEAN, held from posting - problems: fact-check: Slide 1 line 1 ends abruptly with an incomplete sentence fragment",
                 location="X town, Y district", caption="x", reel_script="y", source="")
        self.assertEqual(post.news_hold(r), "")

    def test_wording_flag_and_district_name_post(self):
        for prob in ("fact-check: Slide title 'x' is ungrammatical/unclear in Tamil", "not grounded: place word 'கோயம்புத்தூர்' is not in the article"):
            r = dict(verification="DRAFT (m) - NOT CLEAN, held from posting - problems: " + prob, location="X town, Y district", caption="x", reel_script="y", source="")
            self.assertEqual(post.news_hold(r), "", prob)

    def test_district_only_with_town_in_story_posts(self):
        r = dict(verification="DRAFT (m) - fact-check: no problems found", location="Coimbatore district", caption="", reel_script="", source="",
                 headline_ta="பொள்ளாச்சி அருகே விபத்து")
        self.assertEqual(post.news_hold(r), "")


class CheckerNoteAcceptable(unittest.TestCase):
    """4 Nov RN-334: a checker note it marks itself as acceptable posts; a real conflict still holds"""

    def r(self, prob):
        return dict(verification="DRAFT (m) - NOT CLEAN, held from posting - problems: " + prob, location="X town, Y district",
                    caption="x", reel_script="y", source="")

    def test_acceptable_note_posts(self):
        self.assertEqual(post.news_hold(self.r("fact-check: reel_script says the trees were grown but also cut \u2014 acceptable")), "")

    def test_real_conflict_still_holds(self):
        self.assertTrue(post.news_hold(self.r("fact-check: reel_script says 5 trees were cut but the article says the trees were not cut")))


class EntryPointLast(unittest.TestCase):
    """the posting job runs main() when the file is executed: every function it uses must be defined above that line (2 Nov, NameError)"""

    def test_main_block_is_the_last_statement(self):
        import ast
        tree = ast.parse(Path(post.__file__).read_text(encoding="utf-8"))
        self.assertIsInstance(tree.body[-1], ast.If)
        self.assertIn("skip_reason", [n.name for n in tree.body if isinstance(n, ast.FunctionDef)])


if __name__ == "__main__":
    unittest.main()
