"""owner 25 Nov: other pages' Shorts went to the Namakkal channel (their logins were made on the wrong channel). With verify_channel
a page uploads only when YouTube confirms the login's channel is this page's."""
import sys, tempfile, unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "poster"))
import ytupload      # noqa: E402

NOW = datetime.now(timezone.utc).replace(hour=4, minute=0, second=0, microsecond=0)      # 09:30 IST: +3 h stays the same IST day (failed 21:00-24:00 IST)
S = {"verify_channel": True}


class R:
    def __init__(self, code, title=""):
        self.status_code = code
        self._j = {"items": [{"snippet": {"title": title}}]} if title else {}

    def json(self):
        return self._j


class Channel(unittest.TestCase):
    def setUp(self):
        self.p = mock.patch.object(ytupload, "STATE", Path(tempfile.mkdtemp()))
        self.p.start()

    def tearDown(self):
        self.p.stop()

    def check(self, page, resp, now=NOW):
        with mock.patch.object(ytupload.requests, "get", return_value=resp) as g:
            return ytupload.channel_ok(page, "t", S, now), g

    def test_right_channel_uploads(self):
        self.assertEqual(self.check("karur", R(200, "Karur 360"))[0], "")
        self.assertEqual(self.check("tirupur", R(200, "Tiruppur 360"))[0], "")
        self.assertEqual(self.check("trichy", R(200, "திருச்சி 360"))[0], "")

    def test_wrong_channel_never_uploads(self):
        why, _ = self.check("karur", R(200, "Namakkal 360"))
        self.assertIn("Namakkal 360", why)
        self.assertIn("NOT uploaded", why)

    def test_upload_only_login_waits(self):
        self.assertIn("permission", self.check("salem", R(403))[0])

    def test_checked_once_a_day_when_ok(self):
        self.check("erode", R(200, "Erode 360"))
        why, g = self.check("erode", R(500), NOW + timedelta(hours=3))
        self.assertEqual(why, "")
        g.assert_not_called()

    def test_off_without_the_setting(self):
        self.assertEqual(ytupload.channel_ok("karur", "t", {}), "")


if __name__ == "__main__":
    unittest.main()
