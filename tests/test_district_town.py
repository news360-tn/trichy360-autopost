import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "research_free"))
import collect


class DistrictTown(unittest.TestCase):
    """owner 3 Nov (RN-160 / RN-163 / RN-272): a location that is only the district gets the town the article names"""

    def test_town_from_article(self):
        self.assertEqual(collect.district_town({"title": "செய்தி", "text": "பொள்ளாச்சி அருகே கிராம மக்கள் போராட்டம்"}), "பொள்ளாச்சி")

    def test_no_town_in_article(self):
        self.assertEqual(collect.district_town({"title": "மாவட்ட செய்தி", "text": "மாவட்டம் முழுவதும் மழை"}), "")


if __name__ == "__main__":
    unittest.main()
