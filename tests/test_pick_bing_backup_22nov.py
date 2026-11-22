"""owner 22 Nov: when Google News is busy (503) for a paper, the round reads that paper through Bing instead."""
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research_free"))
import pick      # noqa: E402


class BingBackup(unittest.TestCase):
    def test_google_503_uses_bing(self):
        def boom(q):
            raise RuntimeError("503 Server Error")
        asked = []

        def from_bing(q):
            asked.append(q)
            return [{"url": "https://www.dailythanthi.com/news/x-1", "site": "", "title": "t", "published": ""}]
        boom.__name__ = "from_google"
        with mock.patch.object(pick.allnews, "from_google", boom), mock.patch.object(pick.allnews, "from_bing", from_bing), \
                mock.patch.object(pick.allnews, "from_dinamalar_list", return_value=[]), mock.patch.object(pick.allnews, "from_listing", return_value=[]):
            out = pick.candidates([])
        self.assertTrue(any("dailythanthi.com/news/x-1" in x["url"] for x in out))
        self.assertTrue(any("dailythanthi.com" in q for q in asked))


if __name__ == "__main__":
    unittest.main()
