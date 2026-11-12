import sys, unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "poster"))
import cloudclean as cc      # noqa: E402


def res(pid, hours, now, folder=None):
    t = (now - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
    d = {"public_id": pid, "created_at": t, "bytes": 1000}
    if folder is not None:
        d["asset_folder"] = folder
    return d


class CloudClean(unittest.TestCase):
    now = datetime(2026, 11, 12, 10, 3, tzinfo=timezone.utc)

    def test_only_this_page_folder(self):
        self.assertTrue(cc.mine({"public_id": "trichy360/abc"}))
        self.assertTrue(cc.mine({"public_id": "abc", "asset_folder": "trichy360"}))
        for other in ({"public_id": "rasipalan/abc"}, {"public_id": "otherpage360/abc"}, {"public_id": "abc", "asset_folder": "namakkal"},
                      {"public_id": "trichy3600/abc"}, {"public_id": "abc"}):
            self.assertFalse(cc.mine(other), other)

    def test_normal_keeps_three_days(self):
        files = [res("trichy360/a", 80, self.now), res("trichy360/b", 50, self.now), res("trichy360/c", 2, self.now)]
        self.assertEqual(cc.plan(files, "video", self.now, full=False), ["trichy360/a"])
        self.assertEqual(cc.plan(files, "image", self.now, full=False), ["trichy360/a"])

    def test_half_full_deletes_old_reels_but_keeps_pictures_and_fb_retry_window(self):
        files = [res("trichy360/a", 80, self.now), res("trichy360/b", 30, self.now), res("trichy360/c", 20, self.now)]
        self.assertEqual(cc.plan(files, "video", self.now, full=True), ["trichy360/a", "trichy360/b"])
        self.assertEqual(cc.plan(files, "image", self.now, full=True), ["trichy360/a"])      # a waiting story's picture is never removed

    def test_skipped_without_keys_and_off_the_hour(self):
        with mock.patch.dict("os.environ", {"CLOUDINARY_CLOUD": "x", "CLOUDINARY_API_KEY": "", "CLOUDINARY_API_SECRET": ""}):
            self.assertEqual(cc.run(force=True), 0)
        with mock.patch.dict("os.environ", {"CLOUDINARY_CLOUD": "x", "CLOUDINARY_API_KEY": "k", "CLOUDINARY_API_SECRET": "s"}), \
                mock.patch.object(cc.requests, "get") as g:
            self.assertEqual(cc.run(now=self.now.replace(minute=30)), 0)
            g.assert_not_called()

    def test_run_deletes_only_old_own_files(self):
        now = self.now
        listed = {"video": [res("trichy360/old", 30, now), res("trichy360/new", 3, now), res("namakkal/old", 300, now)],
                  "image": [res("trichy360/pic", 30, now), res("trichy360/oldpic", 100, now)]}

        def get(url, params=None, auth=None, timeout=None):
            r = mock.Mock(status_code=200)
            r.raise_for_status = lambda: None
            if url.endswith("usage"):
                r.json = lambda: {"credits": {"used_percent": 61.0}}
            else:
                r.json = lambda: {"resources": listed["video" if url.endswith("/video") else "image"]}
            return r
        deleted = []

        def delete(url, params=None, auth=None, timeout=None):
            ids = [v for _, v in params]
            deleted.extend(ids)
            r = mock.Mock(status_code=200)
            r.raise_for_status = lambda: None
            r.json = lambda: {"deleted": {i: "deleted" for i in ids}}
            return r
        with mock.patch.dict("os.environ", {"CLOUDINARY_CLOUD": "x", "CLOUDINARY_API_KEY": "k", "CLOUDINARY_API_SECRET": "s"}), \
                mock.patch.object(cc.requests, "get", side_effect=get), mock.patch.object(cc.requests, "delete", side_effect=delete):
            self.assertEqual(cc.run(now=now), 2)
        self.assertEqual(sorted(deleted), ["trichy360/old", "trichy360/oldpic"])


class CachedLinks(unittest.TestCase):
    def test_deleted_link_means_upload_again(self):
        import post
        media = {"reel": "https://res.cloudinary.com/x/video/upload/v1/trichy360/a.mp4", "carousel": [], "cover": "", "story": ""}
        with mock.patch.object(post.requests, "head", return_value=mock.Mock(status_code=404)):
            self.assertFalse(post.links_alive(media))
        with mock.patch.object(post.requests, "head", return_value=mock.Mock(status_code=200)):
            self.assertTrue(post.links_alive(media))
        with mock.patch.object(post.requests, "head", side_effect=OSError("net")):
            self.assertTrue(post.links_alive(media))      # a network error is not a deleted file


if __name__ == "__main__":
    unittest.main()
