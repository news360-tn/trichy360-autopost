"""owner 23 Nov: more trusted Tamil outlets + one open Google News search for the district each round (Bing when Google is busy)."""
import sys, unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research_free"))
import pick      # noqa: E402
import allnews      # noqa: E402


class MoreSources23Nov(unittest.TestCase):
    def setUp(self):
        self.now = pick.now()
        self.p = (self.now - timedelta(minutes=30)).isoformat()

    @staticmethod
    def named(f, name):
        def fn(q):
            return f(q)
        fn.__name__ = name
        return fn

    def run_cands(self, google, bing=lambda q: []):
        with mock.patch.object(allnews, "from_dinamalar_list", return_value=[]), mock.patch.object(allnews, "from_listing", return_value=[]), \
                mock.patch.object(allnews, "from_google", new=self.named(google, "from_google")), \
                mock.patch.object(allnews, "from_bing", new=self.named(bing, "from_bing")), mock.patch.object(allnews, "resolve", side_effect=lambda u: u):
            lines = []
            return pick.candidates(lines, self.now - timedelta(hours=4)), lines

    def test_new_outlets_are_trusted(self):
        for d in ("vikatan.com", "tamil.abplive.com", "tamil.news18.com", "tamil.indianexpress.com", "puthiyathalaimurai.com", "thanthitv.com"):
            self.assertIn(d, pick.OUTLETS)

    def test_open_search_keeps_only_our_outlets(self):
        def google(q):
            if "site:" in q:
                return []
            return [{"url": "https://www.vikatan.com/news/a-child-killed", "site": "https://www.vikatan.com", "title": "x", "published": self.p},
                    {"url": "https://randomblog.example/post", "site": "https://randomblog.example", "title": "y", "published": self.p}]
        out, lines = self.run_cands(google)
        urls = [o["url"] for o in out]
        self.assertIn("https://www.vikatan.com/news/a-child-killed", urls)
        self.assertNotIn("https://randomblog.example/post", urls)

    def test_bing_when_google_is_busy(self):
        def google(q):
            raise RuntimeError("503 Service Unavailable")
        def bing(q):
            return [] if "site:" in q else [{"url": "https://tamil.abplive.com/news/x", "title": "z", "published": self.p}]
        out, lines = self.run_cands(google, bing)
        self.assertIn("https://tamil.abplive.com/news/x", [o["url"] for o in out])

    def test_new_outlets_not_searched_one_by_one(self):
        qs = []
        self.run_cands(lambda q: qs.append(q) or [])
        self.assertFalse([q for q in qs if "vikatan.com" in q or "abplive" in q])


if __name__ == "__main__":
    unittest.main()
