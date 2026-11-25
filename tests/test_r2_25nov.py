"""owner 25 Nov: one shared Cloudflare R2 bucket replaces Cloudinary for every page. Order: R2 -> Cloudinary -> GitHub; without the
R2 secrets nothing changes."""
import hashlib, hmac, os, sys, tempfile, unittest
from pathlib import Path
from unittest import mock
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "poster"))
import githost      # noqa: E402
import r2host      # noqa: E402

R2 = {"R2_ACCOUNT_ID": "0123456789abcdef0123456789abcdef", "R2_ACCESS_KEY_ID": "AKID", "R2_SECRET_ACCESS_KEY": "SECRET", "R2_BUCKET": "news360-media",
      "R2_PUBLIC_URL": "https://pub-x.r2.dev/", "PAGE": "erode"}
NO_R2 = {k: "" for k in R2 if k != "PAGE"}


class Resp:
    def __init__(self, code):
        self.status_code, self.text = code, "x"


class R2Test(unittest.TestCase):
    def test_disabled_without_secrets(self):
        with mock.patch.dict(os.environ, NO_R2):
            self.assertFalse(r2host.enabled())

    def test_put_signs_and_returns_public_link(self):
        calls = []
        with mock.patch.dict(os.environ, R2), mock.patch.object(r2host.requests, "put",
                                                                 side_effect=lambda u, **k: calls.append((u, k)) or Resp(200)):
            link = r2host.put(b"abc", "a.mp4", "video")
        url, k = calls[0]
        key = f"erode/{link.split('/erode/')[1]}"
        self.assertTrue(url.startswith("https://0123456789abcdef0123456789abcdef.r2.cloudflarestorage.com/news360-media/erode/"))
        self.assertEqual(link, "https://pub-x.r2.dev/" + key)
        self.assertTrue(link.endswith(".mp4"))
        h = k["headers"]
        self.assertEqual(h["content-type"], "video/mp4")
        self.assertEqual(h["x-amz-content-sha256"], hashlib.sha256(b"abc").hexdigest())
        self.assertIn("Credential=AKID/", h["Authorization"])
        self.assertIn("SignedHeaders=content-type;host;x-amz-content-sha256;x-amz-date", h["Authorization"])
        self.assertNotIn("SECRET", str(h))

    def test_signature_matches_sigv4(self):
        """recompute the AWS SigV4 signature independently from the sent headers"""
        calls = []
        with mock.patch.dict(os.environ, R2), mock.patch.object(r2host.requests, "put",
                                                                 side_effect=lambda u, **k: calls.append((u, k)) or Resp(200)):
            r2host.put(b"hello", "p.jpg")
        url, k = calls[0]
        h = k["headers"]
        amz, day = h["x-amz-date"], h["x-amz-date"][:8]
        path = url.split(".com", 1)[1]
        canon = (f"PUT\n{path}\n\ncontent-type:image/jpeg\nhost:0123456789abcdef0123456789abcdef.r2.cloudflarestorage.com\n"
                 f"x-amz-content-sha256:{h['x-amz-content-sha256']}\nx-amz-date:{amz}\n\n"
                 f"content-type;host;x-amz-content-sha256;x-amz-date\n{h['x-amz-content-sha256']}")
        sts = f"AWS4-HMAC-SHA256\n{amz}\n{day}/auto/s3/aws4_request\n{hashlib.sha256(canon.encode()).hexdigest()}"
        kk = b"AWS4SECRET"
        for m in (day, "auto", "s3", "aws4_request"):
            kk = hmac.new(kk, m.encode(), hashlib.sha256).digest()
        self.assertIn("Signature=" + hmac.new(kk, sts.encode(), hashlib.sha256).hexdigest(), h["Authorization"])

    def test_account_id_paste_mistakes(self):
        good = "0123456789abcdef0123456789abcdef"
        self.assertEqual(r2host.account_id(" " + good.upper() + "\n"), good)
        self.assertEqual(r2host.account_id(f"https://{good}.r2.cloudflarestorage.com"), good)
        for bad in ("a" * 64, "abc", ""):
            with self.assertRaises(RuntimeError) as e:
                r2host.account_id(bad)
            self.assertNotIn(bad or "zz", str(e.exception))

    def test_wrong_key_is_not_retried(self):
        n = []
        with mock.patch.dict(os.environ, R2), mock.patch.object(r2host.requests, "put", side_effect=lambda u, **k: n.append(1) or Resp(403)):
            with self.assertRaises(RuntimeError):
                r2host.put(b"x")
        self.assertEqual(len(n), 1)

    def test_fallback_uses_r2_before_cloudinary(self):
        cloud = mock.Mock(return_value="https://res.cloudinary.com/x")
        with mock.patch.dict(os.environ, R2), mock.patch.object(r2host, "put", return_value="https://pub-x.r2.dev/a.jpg"):
            self.assertEqual(githost.fallback(cloud, b"img", "image", "a.jpg", log=lambda *a: None), "https://pub-x.r2.dev/a.jpg")
        cloud.assert_not_called()

    def test_r2_refused_then_cloudinary(self):
        with mock.patch.dict(os.environ, R2), mock.patch.object(r2host, "put", side_effect=RuntimeError("R2 down")):
            self.assertEqual(githost.fallback(lambda: "https://res.cloudinary.com/x", b"img", log=lambda *a: None),
                             "https://res.cloudinary.com/x")

    def test_r2_and_cloudinary_refused_then_github(self):
        def bad():
            raise RuntimeError("credits used up")
        env = dict(R2, GH_MEDIA_TOKEN="t", GITHUB_REPOSITORY="news360-tn/x")
        with mock.patch.dict(os.environ, env), mock.patch.object(r2host, "put", side_effect=RuntimeError("R2 down")), \
                mock.patch.object(githost, "host", return_value="https://raw.githubusercontent.com/x"):
            self.assertEqual(githost.fallback(bad, b"img", log=lambda *a: None), "https://raw.githubusercontent.com/x")

    def test_without_r2_cloudinary_as_before(self):
        with mock.patch.dict(os.environ, NO_R2), mock.patch.object(r2host, "put") as p:
            self.assertEqual(githost.fallback(lambda: "C", b"img", log=lambda *a: None), "C")
        p.assert_not_called()

    def test_reel_video_upload_r2_first(self):
        sys.path.insert(0, str(ROOT / "research_free"))
        import post
        with tempfile.TemporaryDirectory() as t:
            f = Path(t) / "r.mp4"
            f.write_bytes(b"v")
            with mock.patch.dict(os.environ, R2), mock.patch.object(r2host, "put", return_value="https://pub-x.r2.dev/r.mp4"), \
                    mock.patch.object(post, "upload_cloudinary") as c:
                self.assertEqual(post.upload(f, "video"), "https://pub-x.r2.dev/r.mp4")
            c.assert_not_called()
            with mock.patch.dict(os.environ, R2), mock.patch.object(r2host, "put", side_effect=RuntimeError("no")), \
                    mock.patch.object(post, "upload_cloudinary", return_value="C") as c:
                self.assertEqual(post.upload(f, "video"), "C")


if __name__ == "__main__":
    unittest.main()
