"""19 Nov: Instagram answered 9007 "media is not ready for publishing" (Erode rasipalan) and Cloudinary refused an upload
once (Rasipuram rasipalan, 18 Nov). Publishing is tried again only for 9007 (nothing was posted), never for other errors."""
import importlib
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent


class Resp:
    def __init__(self, code, data):
        self.status_code, self._d = code, data
        self.ok = code < 400
        self.text = str(data)

    def json(self):
        return self._d

    def raise_for_status(self):
        if not self.ok:
            raise RuntimeError(f"HTTP {self.status_code}")


NOT_READY = Resp(400, {"error": {"code": 9007, "error_subcode": 2207027, "message": "Media ID is not available"}})
OTHER = Resp(400, {"error": {"code": 190, "message": "token expired"}})


def load(folder, name):
    sys.path.insert(0, str(ROOT / folder))
    try:
        return importlib.import_module(name)
    except ImportError as e:      # rasi_daily needs pyswisseph (installed by tests.yml)
        raise unittest.SkipTest(f"{name}: {e}")


class PublishRetry:
    mod = None

    def test_not_ready_then_published(self):
        calls = [NOT_READY, NOT_READY, Resp(200, {"id": "M1"})]
        with mock.patch.object(self.mod.requests, "request", side_effect=calls) as rq, mock.patch.object(self.mod.time, "sleep"):
            self.assertEqual(self.mod.ig("POST", "U/media_publish", "t", creation_id="C")["id"], "M1")
        self.assertEqual(rq.call_count, 3)

    def test_gives_up_after_six_tries(self):
        with mock.patch.object(self.mod.requests, "request", return_value=NOT_READY) as rq, mock.patch.object(self.mod.time, "sleep"):
            with self.assertRaises(RuntimeError):
                self.mod.ig("POST", "U/media_publish", "t", creation_id="C")
        self.assertEqual(rq.call_count, 6)

    def test_other_errors_never_retried(self):
        for path in ("U/media_publish", "U/media"):
            with mock.patch.object(self.mod.requests, "request", return_value=OTHER) as rq, mock.patch.object(self.mod.time, "sleep"):
                with self.assertRaises(RuntimeError):
                    self.mod.ig("POST", path, "t")
            self.assertEqual(rq.call_count, 1)

    def test_9007_on_other_calls_not_retried(self):
        with mock.patch.object(self.mod.requests, "request", return_value=NOT_READY) as rq, mock.patch.object(self.mod.time, "sleep"):
            with self.assertRaises(RuntimeError):
                self.mod.ig("POST", "U/media", "t")
        self.assertEqual(rq.call_count, 1)

    def test_upload_tries_again(self, tmp=None):
        f = ROOT / "tests" / "_upload_probe.jpg"
        f.write_bytes(b"x")
        try:
            calls = [Resp(400, {"error": "busy"}), Resp(200, {"secure_url": "https://x/y.jpg"})]
            with mock.patch.dict("os.environ", {"CLOUDINARY_CLOUD": "c", "CLOUDINARY_PRESET": "p"}), \
                 mock.patch.object(self.mod.requests, "post", side_effect=calls) as rp, mock.patch.object(self.mod.time, "sleep"):
                self.assertEqual(self.mod.upload(str(f)), "https://x/y.jpg")
            self.assertEqual(rp.call_count, 2)
        finally:
            f.unlink()


class Gold(PublishRetry, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load("goldrate", "gold_daily")


class Rasi(PublishRetry, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load("rasipalan", "rasi_daily")


if __name__ == "__main__":
    unittest.main()
