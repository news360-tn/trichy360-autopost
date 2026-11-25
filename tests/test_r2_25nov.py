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
      "R2_PUBLIC_URL": "https://pub-x.r2.dev/", "PAGE": "erode", "GITHUB_REPOSITORY": ""}
NO_R2 = {k: "" for k in R2 if k != "PAGE"}


class Resp:
    def __init__(self, code):
        self.status_code, self.text = code, "x"


class R2Test(unittest.TestCase):
    def test_disabled_without_secrets(self):
        with mock.patch.dict(os.environ, NO_R2):
            self.assertFalse(r2host.enabled())

    def fake(self, calls, put_code=200, listing="<ListBucketResult><IsTruncated>false</IsTruncated></ListBucketResult>", list_code=200):
        def req(method, url, **k):
            calls.append((method, url, k))
            if method == "GET":
                r = Resp(list_code)
                r.text = listing
                return r
            return Resp(put_code)
        return mock.patch.object(r2host.requests, "request", side_effect=req)

    def test_put_signs_and_returns_public_link(self):
        calls = []
        with mock.patch.dict(os.environ, R2), self.fake(calls):
            link = r2host.put(b"abc", "a.mp4", "video")
        method, url, k = calls[-1]
        self.assertEqual(method, "PUT")
        key = f"erode/{link.split('/erode/')[1]}"
        self.assertTrue(url.startswith("https://0123456789abcdef0123456789abcdef.r2.cloudflarestorage.com/news360-media/erode/"))
        self.assertEqual(link, "https://pub-x.r2.dev/" + key)
        h = k["headers"]
        self.assertEqual(h["content-type"], "video/mp4")
        self.assertEqual(h["x-amz-content-sha256"], hashlib.sha256(b"abc").hexdigest())
        self.assertIn("Credential=AKID/", h["Authorization"])
        self.assertIn("SignedHeaders=content-type;host;x-amz-content-sha256;x-amz-date", h["Authorization"])
        self.assertNotIn("SECRET", str(h))
        self.assertEqual(calls[0][0], "GET")      # today's usage is read first
        self.assertIn("list-type=2", calls[0][1])

    def test_signature_matches_sigv4(self):
        """recompute the AWS SigV4 signature independently, for the PUT and for the usage listing (query string)"""
        calls = []
        with mock.patch.dict(os.environ, R2), self.fake(calls):
            r2host.put(b"hello", "p.jpg")
        for method, url, k in calls:
            h = k["headers"]
            amz, day = h["x-amz-date"], h["x-amz-date"][:8]
            rest = url.split(".com", 1)[1]
            path, _, q = rest.partition("?")
            ct = f"content-type:{h['content-type']}\n" if "content-type" in h else ""
            signed = ("content-type;" if ct else "") + "host;x-amz-content-sha256;x-amz-date"
            canon = (f"{method}\n{path}\n{q}\n{ct}host:0123456789abcdef0123456789abcdef.r2.cloudflarestorage.com\n"
                     f"x-amz-content-sha256:{h['x-amz-content-sha256']}\nx-amz-date:{amz}\n\n{signed}\n{h['x-amz-content-sha256']}")
            sts = f"AWS4-HMAC-SHA256\n{amz}\n{day}/auto/s3/aws4_request\n{hashlib.sha256(canon.encode()).hexdigest()}"
            kk = b"AWS4SECRET"
            for m in (day, "auto", "s3", "aws4_request"):
                kk = hmac.new(kk, m.encode(), hashlib.sha256).digest()
            self.assertIn("Signature=" + hmac.new(kk, sts.encode(), hashlib.sha256).hexdigest(), h["Authorization"], method)

    def test_daily_size_limit_stops_r2(self):
        big = "<ListBucketResult><Contents><Size>%d</Size></Contents><IsTruncated>false</IsTruncated></ListBucketResult>" % (299 * 1048576)
        calls = []
        with mock.patch.dict(os.environ, R2), self.fake(calls, listing=big):
            r2host.put(b"x" * 1000, "a.jpg")      # still under 300 MB
            with self.assertRaises(RuntimeError) as e:
                r2host.put(b"x" * (2 * 1048576), "b.jpg")      # would pass 300 MB
        self.assertIn("safety limit", str(e.exception))
        self.assertEqual([c[0] for c in calls].count("PUT"), 1)

    def test_daily_file_limit_and_env_can_only_lower(self):
        many = "<ListBucketResult>" + "<Contents><Size>1</Size></Contents>" * 400 + "<IsTruncated>false</IsTruncated></ListBucketResult>"
        calls = []
        with mock.patch.dict(os.environ, R2), self.fake(calls, listing=many):
            with self.assertRaises(RuntimeError):
                r2host.put(b"x")
        with mock.patch.dict(os.environ, dict(R2, R2_DAILY_MB="99999")):
            self.assertEqual(r2host._limits()[0], 300 * 1048576)
        with mock.patch.dict(os.environ, dict(R2, R2_DAILY_MB="50")):
            self.assertEqual(r2host._limits()[0], 50 * 1048576)

    def test_usage_unreadable_means_no_upload(self):
        calls = []
        with mock.patch.dict(os.environ, R2), self.fake(calls, list_code=403):
            with self.assertRaises(RuntimeError):
                r2host.put(b"x")
        self.assertNotIn("PUT", [c[0] for c in calls])

    def test_too_big_file_never_uploaded(self):
        calls = []
        with mock.patch.dict(os.environ, R2), self.fake(calls), mock.patch.object(r2host, "MAX_FILE_MB", 0):
            with self.assertRaises(RuntimeError):
                r2host.put(b"xx")
        self.assertEqual(calls, [])

    def test_account_id_paste_mistakes(self):
        good = "0123456789abcdef0123456789abcdef"
        self.assertEqual(r2host.account_id(" " + good.upper() + "\n"), good)
        self.assertEqual(r2host.account_id(f"https://{good}.r2.cloudflarestorage.com"), good)
        for bad in ("a" * 64, "abc", ""):
            with self.assertRaises(RuntimeError) as e:
                r2host.account_id(bad)
            self.assertNotIn(bad or "zz", str(e.exception))

    def test_clean_deletes_only_this_pages_old_files(self):
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        old = (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        new = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        listing = ("<ListBucketResult>"
                   f"<Contents><Key>erode/20261124/a.mp4</Key><LastModified>{old}</LastModified><Size>5000000</Size></Contents>"
                   f"<Contents><Key>erode/20261125/b.jpg</Key><LastModified>{new}</LastModified><Size>100</Size></Contents>"
                   f"<Contents><Key>salem/20261124/c.mp4</Key><LastModified>{old}</LastModified><Size>9</Size></Contents>"
                   "<IsTruncated>false</IsTruncated></ListBucketResult>")
        calls = []
        with mock.patch.dict(os.environ, R2), self.fake(calls, listing=listing):
            deleted, kept, freed = r2host.clean(24, log=lambda *a: None)
        self.assertEqual((deleted, kept, freed), (1, 1, 5000000))
        dels = [u for m, u, k in calls if m == "DELETE"]
        self.assertEqual(len(dels), 1)
        self.assertTrue(dels[0].endswith("/news360-media/erode/20261124/a.mp4"))
        self.assertIn("prefix=erode%2F", calls[0][1])
        calls.clear()
        with mock.patch.dict(os.environ, R2), self.fake(calls, listing=listing):
            self.assertEqual(r2host.clean(24, dry=True, log=lambda *a: None)[0], 1)
        self.assertNotIn("DELETE", [c[0] for c in calls])

    def test_one_folder_per_repository(self):
        with mock.patch.dict(os.environ, {"GITHUB_REPOSITORY": "news360-tn/salem360-autopost", "PAGE": "salem"}):
            self.assertEqual(r2host._page(), "salem360")
        with mock.patch.dict(os.environ, {"GITHUB_REPOSITORY": "", "PAGE": "erode"}):
            self.assertEqual(r2host._page(), "erode")

    def test_wrong_key_is_not_retried(self):
        calls = []
        with mock.patch.dict(os.environ, R2), self.fake(calls, put_code=403):
            with self.assertRaises(RuntimeError):
                r2host.put(b"x")
        self.assertEqual([c[0] for c in calls].count("PUT"), 1)

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
