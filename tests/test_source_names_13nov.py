"""owner 13 Nov: news from ABP Nadu / Samayam (the state-wide power-cut lists) still names its source on the reel and caption."""
import sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "poster"))
import post      # noqa: E402


class SourceNames(unittest.TestCase):
    def test_state_list_sites_are_named(self):
        for url, name in (("https://tamil.abplive.com/news/tamil-nadu/power-cut#district-section", "ABP நாடு"),
                          ("https://tamil.samayam.com/tamil-nadu/news/power-outage/1", "சமயம் தமிழ்"),
                          ("https://tamil.news18.com/photogallery/tamil-nadu/power-outage", "நியூஸ்18 தமிழ்")):
            self.assertEqual(post.source_names({"source": url}), [name])


if __name__ == "__main__":
    unittest.main()
