"""owner 1 Nov: every post (news reel, carousel, daily rasipalan, any job) also goes to the story - a missing story is caught up."""
import sys, unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "poster"))
import post      # noqa: E402


class StoryCatchUp(unittest.TestCase):
    def run_catchup(self, used):
        now = datetime.now(timezone.utc)
        f = lambda d: (now - d).strftime("%Y-%m-%dT%H:%M:%S+0000")
        feed = [{"id": "1", "media_type": "VIDEO", "media_url": "https://cdn/v1.mp4", "timestamp": f(timedelta(hours=3)), "owner": {"id": "U"}},
                {"id": "2", "media_type": "CAROUSEL_ALBUM", "timestamp": f(timedelta(hours=2)), "owner": {"id": "U"},
                 "children": {"data": [{"media_type": "IMAGE", "media_url": "https://cdn/s1.jpg"}]}},          # rasipalan: no story yet
                {"id": "3", "media_type": "VIDEO", "media_url": "https://cdn/v3.mp4", "timestamp": f(timedelta(hours=1)), "owner": {"id": "U"}},
                {"id": "4", "media_type": "VIDEO", "media_url": "https://cdn/v4.mp4", "timestamp": f(timedelta(hours=1)), "owner": {"id": "OTHER"}},   # collab of the other page
                {"id": "5", "media_type": "VIDEO", "media_url": "https://cdn/v5.mp4", "timestamp": f(timedelta(hours=30)), "owner": {"id": "U"}}]      # too old
        stories = [{"id": "s", "timestamp": f(timedelta(hours=3) - timedelta(minutes=1))}]      # post 1 already has its story
        made = []

        def ig(method, path, token, **kw):
            if path == "me":
                return {"id": "U", "user_id": "UU"}
            if path.endswith("content_publishing_limit"):
                return {"data": [{"quota_usage": used, "config": {"quota_total": 50}}]}
            if path.endswith("/media") and method == "GET":
                return {"data": feed}
            if path.endswith("/stories"):
                return {"data": stories}
            if path.endswith("/media") and method == "POST":
                made.append(kw.get("video_url") or kw.get("image_url"))
                return {"id": "c"}
            return {"id": "p"}
        with mock.patch.object(post, "DRY", False), mock.patch.object(post, "LABEL", {"x": "X"}), \
                mock.patch.dict(post.CONFIG, {"stories_urgent_only": False}), \
                mock.patch.object(post, "bridge_get", return_value={"token": "t"}), mock.patch.object(post, "ig_account", return_value=("U", "u")), \
                mock.patch.object(post, "ig", side_effect=ig), mock.patch.object(post, "wait_ready"), \
                mock.patch.object(post, "upload", side_effect=lambda p, k: "https://cloud/" + Path(p).name), \
                mock.patch.object(post.requests, "get", return_value=mock.Mock(content=b"x", raise_for_status=lambda: None)):
            post.story_catchup()
        return made

    def test_missing_stories_are_made(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d, mock.patch.object(post, "SHARED", Path(d) / "s.json"):
            got = self.run_catchup(10)
        self.assertEqual(got, ["https://cdn/s1.jpg", "https://cloud/story.mp4"])
        return
        self.assertEqual(self.run_catchup(10), ["https://cdn/s1.jpg", "https://cloud/story.mp4"])      # a video is hosted again first

    def test_a_post_gets_one_story_only(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d, mock.patch.object(post, "SHARED", Path(d) / "s.json"):
            self.assertEqual(len(self.run_catchup(10)), 2)
            self.assertEqual(self.run_catchup(10), [])      # next run: the late stories are remembered, not made again

    def test_news_posts_keep_room(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d, mock.patch.object(post, "SHARED", Path(d) / "s.json"):
            self.assertEqual(self.run_catchup(45), [])      # 45 + 1 > 50 - 5: the last 5 posts of the day stay for news

    def test_no_fixed_25_limit(self):
        src = (ROOT / "poster" / "post.py").read_text(encoding="utf-8")
        self.assertNotIn("stories_below_quota", src)
        self.assertIn("story_catchup()", src)


if __name__ == "__main__":
    unittest.main()
