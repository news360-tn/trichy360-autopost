"""owner 24 Nov: when Google refuses the news-link decoder (429), the same headline on Bing (same newspaper) gives the real link."""
import sys, unittest
from pathlib import Path
from unittest import mock
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research_free"))
import allnews      # noqa: E402

G = "https://news.google.com/rss/articles/CBMiXYZ"
T = "முசிறி விபத்து: மேலும் ஒருவர் உயிரிழப்பு இறந்தோர் எண்ணிக்கை 9 ஆக உயர்வு"


class GnewsBing24Nov(unittest.TestCase):
    def setUp(self):
        allnews._GMETA[G] = (T, "https://www.dinamani.com")

    def test_found_on_bing(self):
        bing = [{"url": "https://www.other.com/x", "title": T},
                {"url": "https://www.dinamani.com/all-editions/edition-trichy/trichy/2026/Nov/23/musiri", "title": T + " - Dinamani"}]
        with mock.patch.object(allnews, "from_bing", return_value=bing) as b:
            self.assertEqual(allnews._bing_same_article(G), bing[1]["url"])
            self.assertIn("site:dinamani.com", b.call_args.args[0])

    def test_other_headline_is_not_taken(self):
        with mock.patch.object(allnews, "from_bing", return_value=[{"url": "https://www.dinamani.com/y", "title": "வேறு செய்தி முற்றிலும்"}]):
            self.assertEqual(allnews._bing_same_article(G), "")

    def test_resolve_uses_it_when_google_refuses(self):
        with mock.patch.dict(sys.modules, {"googlenewsdecoder": None}), mock.patch.object(allnews.time, "sleep"), \
                mock.patch.object(allnews, "_get", side_effect=RuntimeError("429")), \
                mock.patch.object(allnews, "_bing_same_article", return_value="https://www.dinamani.com/z"):
            self.assertEqual(allnews.resolve(G), "https://www.dinamani.com/z")


if __name__ == "__main__":
    unittest.main()
