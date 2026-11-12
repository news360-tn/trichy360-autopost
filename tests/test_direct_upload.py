"""owner 12 Nov: direct reel upload (file, not Cloudinary link) - OFF unless DIRECT_UPLOAD=1, never posts twice, falls back to the link."""
import os, sys, tempfile, unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "poster"))
import localmedia      # noqa: E402
import post            # noqa: E402
import facebook        # noqa: E402

LINK = "https://res.cloudinary.com/x/video/upload/v1/trichy360/r.mp4"


class Base(unittest.TestCase):
    def setUp(self):
        localmedia._LOCAL.clear()
        self.f = Path(tempfile.mkdtemp()) / "r.mp4"
        self.f.write_bytes(b"0" * 1000)
        self.calls = []

        def ig(method, path, token, **prm):
            self.calls.append((method, path, prm))
            if path.endswith("/media_publish"):
                return {"id": "M1"}
            if path == "M1":
                return {"permalink": "https://instagram.com/reel/x"}
            return {}
        self.p = [mock.patch.object(post, "ig", side_effect=ig),
                  mock.patch.object(post, "ig_account", return_value=("U", "page")),
                  mock.patch.object(post, "wait_ready", return_value=None),
                  mock.patch.object(post, "create_with_collab", side_effect=lambda uid, tok, prm, c: (self.containers.append(dict(prm)) or "C1", False, ""))]
        self.containers = []
        for x in self.p:
            x.start()

    def tearDown(self):
        for x in self.p:
            x.stop()

    def publishes(self):
        return [c for c in self.calls if c[1].endswith("/media_publish")]


class Off(Base):
    def test_off_by_default_exactly_as_before(self):
        with mock.patch.dict(os.environ, {"DIRECT_UPLOAD": ""}), mock.patch.object(localmedia, "send") as send, \
                mock.patch.object(localmedia.requests, "get") as dl:
            localmedia.remember(LINK, str(self.f))
            post.publish_reel("T", LINK, "cap", False)
            send.assert_not_called(); dl.assert_not_called()
        self.assertEqual(self.containers, [dict(media_type="REELS", video_url=LINK, caption="cap", share_to_feed="true")])
        self.assertEqual(len(self.publishes()), 1)

    def test_facebook_off_uses_the_link(self):
        with mock.patch.dict(os.environ, {"DIRECT_UPLOAD": "0"}), mock.patch.object(facebook.requests, "post",
                                                                                     return_value=mock.Mock(status_code=200, json=lambda: {"success": True})) as rp:
            facebook._hosted_upload("T", "V1", LINK)
        self.assertEqual(rp.call_args.kwargs["headers"]["file_url"], LINK)


class On(Base):
    def setUp(self):
        super().setUp()
        self.env = mock.patch.dict(os.environ, {"DIRECT_UPLOAD": "1"}); self.env.start()
        localmedia.remember(LINK, str(self.f))

    def tearDown(self):
        self.env.stop(); super().tearDown()

    def test_file_is_sent_and_posted_once(self):
        with mock.patch.object(localmedia, "send") as send:
            mid, link, _, _ = post.publish_reel("T", LINK, "cap", False)
        self.assertEqual(mid, "M1")
        self.assertEqual(len(self.containers), 1)
        self.assertEqual(self.containers[0].get("upload_type"), "resumable")
        self.assertNotIn("video_url", self.containers[0])
        self.assertIn("/ig-api-upload/", send.call_args.args[0])
        self.assertEqual(len(self.publishes()), 1)

    def test_upload_failure_falls_back_to_the_link(self):
        with mock.patch.object(localmedia, "send", side_effect=RuntimeError("refused")):
            post.publish_reel("T", LINK, "cap", False)
        self.assertEqual([c.get("video_url") for c in self.containers], [None, LINK])      # resumable try, then the old way
        self.assertEqual(len(self.publishes()), 1)

    def test_published_reel_is_never_posted_again(self):
        orig = post.ig.side_effect

        def ig(method, path, token, **prm):
            if path == "M1":
                raise RuntimeError("permalink not ready")
            return orig(method, path, token, **prm)
        post.ig.side_effect = ig
        with mock.patch.object(localmedia, "send"):
            mid, link, _, _ = post.publish_reel("T", LINK, "cap", False)
        self.assertEqual((mid, link), ("M1", ""))
        self.assertEqual(len(self.containers), 1)
        self.assertEqual(len(self.publishes()), 1)

    def test_facebook_sends_the_file_and_falls_back(self):
        with mock.patch.object(localmedia, "send") as send, mock.patch.object(facebook.requests, "post") as rp:
            facebook._hosted_upload("T", "V1", LINK)
            send.assert_called_once(); rp.assert_not_called()
        with mock.patch.object(localmedia, "send", side_effect=RuntimeError("no")), \
                mock.patch.object(facebook.requests, "post", return_value=mock.Mock(status_code=200, json=lambda: {"success": True})) as rp:
            facebook._hosted_upload("T", "V1", LINK)
            self.assertEqual(rp.call_args.kwargs["headers"]["file_url"], LINK)

    def test_download_failure_means_link(self):
        localmedia._LOCAL.clear()
        with mock.patch.object(localmedia.requests, "get", side_effect=OSError("net")):
            self.assertIsNone(localmedia.get("https://res.cloudinary.com/x/video/upload/v1/trichy360/other.mp4"))


if __name__ == "__main__":
    unittest.main()
