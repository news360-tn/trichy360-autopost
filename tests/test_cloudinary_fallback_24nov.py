"""owner 24 Nov: posting never stops for Cloudinary - a refused picture is kept in the page's GitHub repository; a refused reel goes
directly to Instagram (fresh check), and only then by its GitHub link; rasipalan / gold the same."""
import os, sys, tempfile, unittest
from pathlib import Path
from unittest import mock
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "poster"))
sys.path.insert(0, str(ROOT / "research_free"))
import githost      # noqa: E402
import post      # noqa: E402

ENV = {"GH_MEDIA_TOKEN": "t", "GITHUB_REPOSITORY": "news360-tn/x"}


class Put:
    def __init__(self, code=201):
        self.status_code = code
        self.calls = []

    def __call__(self, url, **k):
        self.calls.append((url, k))
        me = self

        class R:
            status_code = me.status_code
            def raise_for_status(self):
                if me.status_code >= 400 and me.status_code != 422:
                    raise RuntimeError("http")
            def json(self):
                return {"commit": {"sha": "abc123"}}
        return R()


def refuse(*a, **k):
    raise RuntimeError("420 Cloudinary: account disabled")


class CloudinaryFallback24Nov(unittest.TestCase):
    def test_off_without_token(self):
        with mock.patch.dict(os.environ, {"GH_MEDIA_TOKEN": "", "GITHUB_REPOSITORY": ""}):
            with self.assertRaises(RuntimeError):
                githost.fallback(refuse, b"x")

    def test_picture_goes_to_github(self):
        put = Put()
        with mock.patch.dict(os.environ, ENV), mock.patch.object(githost.requests, "put", put):
            url = githost.fallback(refuse, b"jpegdata", "image", "img.jpg", log=lambda *a: None)
        self.assertTrue(url.startswith("https://raw.githubusercontent.com/news360-tn/x/abc123/media/"))
        self.assertTrue(url.endswith(".jpg"))
        self.assertIn("/contents/media/", put.calls[0][0])

    def test_cloudinary_ok_is_used_first(self):
        with mock.patch.dict(os.environ, ENV), mock.patch.object(githost.requests, "put", side_effect=AssertionError):
            self.assertEqual(githost.fallback(lambda: "https://res.cloudinary.com/a.jpg", b"x"), "https://res.cloudinary.com/a.jpg")

    def test_news_picture_in_collect(self):
        import collect
        put = Put()
        with mock.patch.dict(os.environ, ENV), mock.patch.object(collect, "_upload_cloudinary", side_effect=refuse), \
                mock.patch.object(githost.requests, "put", put):
            self.assertIn("raw.githubusercontent.com", collect._upload_image(b"pic"))

    def test_post_picture_and_video(self):
        f = Path(tempfile.mkdtemp()) / "a.jpg"
        f.write_bytes(b"pic")
        put = Put()
        with mock.patch.dict(os.environ, ENV), mock.patch.object(post, "upload_cloudinary", side_effect=refuse), \
                mock.patch.object(githost.requests, "put", put):
            self.assertIn("raw.githubusercontent.com", post.upload(f, "image"))
            with self.assertRaises(RuntimeError):      # a video is NOT sent to GitHub here - publish_reel tries direct first
                post.upload(f, "video")

    def test_reel_direct_when_cloudinary_refuses(self):
        f = Path(tempfile.mkdtemp()) / "r.mp4"
        f.write_bytes(b"vid")
        with mock.patch.object(post, "ig_account", return_value=("U", None)), \
                mock.patch.object(post.localmedia, "get", return_value=str(f)), \
                mock.patch.object(post.localmedia, "hosted", side_effect=refuse), \
                mock.patch.object(post.igdirect, "ready", side_effect=lambda page, uid=None, fresh=False: ("IG", "tok") if fresh else None), \
                mock.patch.object(post, "_ig_direct", return_value=("C1", True, "")) as direct, \
                mock.patch.object(post, "_publish_direct", return_value=("M1", "https://instagram.com/reel/x")):
            out = post.publish_reel("tok", "file://" + str(f), "cap", False)
        self.assertEqual(out[0], "M1")
        direct.assert_called_once()

    def test_reel_github_link_last(self):
        f = Path(tempfile.mkdtemp()) / "r.mp4"
        f.write_bytes(b"vid")
        put = Put()
        seen = {}
        def create(uid, token, prm, collab):
            seen.update(prm)
            return "C2", False, ""
        with mock.patch.dict(os.environ, ENV), mock.patch.object(githost.requests, "put", put), \
                mock.patch.object(post, "ig_account", return_value=("U", None)), \
                mock.patch.object(post.localmedia, "get", return_value=str(f)), \
                mock.patch.object(post.localmedia, "hosted", side_effect=refuse), \
                mock.patch.object(post.igdirect, "ready", return_value=None), \
                mock.patch.object(post, "create_with_collab", side_effect=create), mock.patch.object(post, "wait_ready"), \
                mock.patch.object(post, "ig", side_effect=lambda m, p, t, **k: {"id": "M2"} if m == "POST" else {"permalink": "L"}):
            out = post.publish_reel("tok", "file://" + str(f), "cap", False)
        self.assertEqual(out[0], "M2")
        self.assertIn("raw.githubusercontent.com", seen["video_url"])

    def test_rasipalan_and_gold_use_it(self):
        for rel in ("rasipalan/rasi_daily.py", "goldrate/gold_daily.py"):
            src = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIn("githost.fallback(lambda: _upload_cloudinary(path)", src)
            self.assertIn("githost.fallback(lambda: _upload_video_cloudinary(path)", src)


if __name__ == "__main__":
    unittest.main()
