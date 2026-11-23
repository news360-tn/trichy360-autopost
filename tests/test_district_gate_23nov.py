"""owner 23 Nov: a picked news never skips the district check; the 7 neighbouring districts' towns are other pages' news;
Palaniswami (a person) is not the town Palani."""
import sys, unittest
from pathlib import Path
from unittest import mock
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "poster"))
sys.path.insert(0, str(ROOT / "research_free"))
import post      # noqa: E402
import allnews      # noqa: E402

KALLAKURICHI = "கள்ளக்குறிச்சியில் ஷேர் ஆட்டோக்களால் விபத்து அபாயம்"
PUGALUR = "புகளூர் தவிட்டுப்பாளையத்தில் சர்வீஸ் சாலையில் வாகனங்கள் நிறுத்தம்: விபத்து அபாயம்"


class DistrictGate23Nov(unittest.TestCase):
    def test_picked_news_of_another_district_is_stopped(self):
        with mock.patch.object(post, "owner_picked", return_value=True), mock.patch.object(post, "is_ready_reel", return_value=True), \
                mock.patch.object(post, "link_hold", return_value=""):
            self.assertIn("another district", post._skip_reason_base({"headline_ta": KALLAKURICHI, "source": "https://x"}))
            own = allnews.NEIGHBOUR_TOWNS[[allnews.has_place(w) for w in allnews.NEIGHBOUR_TOWNS].index(True)]
            self.assertEqual(post._skip_reason_base({"headline_ta": f"{own} அருகே சாலை விபத்து", "source": "https://x"}), "")

    def test_pugalur_belongs_to_karur_only(self):
        karur = allnews.has_place("கரூர்")
        self.assertEqual(allnews.other_district(PUGALUR), not karur)

    def test_own_towns_are_never_other(self):
        for w in allnews.NEIGHBOUR_TOWNS:
            if allnews.has_place(w):
                self.assertFalse(allnews.other_district(f"{w} அருகே விபத்து"), w)

    def test_palaniswami_is_a_person(self):
        self.assertFalse(allnews.other_district("அதிமுகவில் 2 கோடி தொண்டர்களா? ஓட்டு ஒரு கோடி தானே: கே.சி. பழனிசாமி கேள்வி"))


if __name__ == "__main__":
    unittest.main()
