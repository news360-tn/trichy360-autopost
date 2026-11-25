"""owner 21 Nov: the day's best news reels go to the page's YouTube channel automatically - only with its YT_* keys, at most 5 a
day, 90 minutes apart, 9 AM - 9 PM, private until Google's audit."""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "poster"))
import post          # noqa: E402
import ytupload      # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))
NOW = datetime.now(timezone.utc).replace(hour=6, minute=0, second=0, microsecond=0)      # 11:30 IST today (owner 24 Nov: a fixed date broke after 3 days - old uploads are forgotten)
KEYS = {"YT_CLIENT_ID_X": "id", "YT_CLIENT_SECRET_X": "sec", "YT_REFRESH_TOKEN_X": "ref"}


def reel(i, cap, hours_ago):
    t = (NOW - timedelta(hours=hours_ago)).strftime("%Y-%m-%dT%H:%M:%S+0000")
    return {"id": f"M{i}", "media_type": "VIDEO", "caption": cap, "timestamp": t, "media_url": f"https://cdn/{i}.mp4", "permalink": "p"}


class YouTubeUpload(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.f = self.d / "v.mp4"
        self.f.write_bytes(b"0" * 10)
        self.feed = [reel(1, "சாலை பணி தொடக்கம்", 3), reel(2, "நாளை மின் தடை: பல பகுதிகள்", 2), reel(3, "இன்றைய ராசிபலன்", 1)]
        self.p = [mock.patch.object(ytupload, "STATE", self.d / "yt"), mock.patch.object(post, "LABEL", {"x": "X"}),
                  mock.patch.object(post, "DRY", False), mock.patch.object(post, "bridge_get", return_value={"token": "IGT"}),
                  mock.patch.object(post, "ig_account", return_value=("U", "page360")),
                  mock.patch.object(post, "ig", side_effect=lambda *a, **k: {"data": self.feed}),
                  mock.patch.object(post.localmedia, "download", return_value=str(self.f)),
                  mock.patch.object(ytupload, "access_token", return_value="AT")]
        for x in self.p:
            x.start()

    def tearDown(self):
        for x in self.p:
            x.stop()

    def run_once(self, now=NOW, **kw):
        with mock.patch.object(ytupload, "upload", return_value="VID", **kw) as up:
            ytupload.catchup(post, now)
        return up

    def test_no_keys_no_upload(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            for k in KEYS:
                os.environ.pop(k, None)
            self.run_once().assert_not_called()

    def test_the_most_useful_reel_goes_first_and_once(self):
        with mock.patch.dict(os.environ, KEYS):
            up = self.run_once()
            up.assert_called_once()
            self.assertIn("மின் தடை", up.call_args.args[2])      # the power cut first (rasipalan never)
            self.assertEqual(up.call_args.args[5], "public")      # owner 23 Nov: uploads go out public
            self.run_once(NOW + timedelta(minutes=3)).assert_not_called()      # owner 25 Nov: 5 minutes apart, like Instagram
            up = self.run_once(NOW + timedelta(minutes=10))
            self.assertIn("சாலை", up.call_args.args[2])      # then the next one - never the same reel twice
            self.run_once(NOW + timedelta(minutes=200)).assert_not_called()      # nothing new left (rasipalan is not uploaded)

    def test_day_limit_hours_and_quota(self):
        s = ytupload.settings({"youtube_upload": {"per_day": 20}})
        self.assertEqual(s["per_day"], 20)      # owner 23 Nov: 20 a day is allowed (own 100-a-day upload allowance)
        self.assertEqual(ytupload.settings({"youtube_upload": {"per_day": 200}})["per_day"], 30)      # never more than 30
        night = datetime(2026, 11, 21, 17, 0, tzinfo=timezone.utc)      # 22:30 IST
        self.assertEqual(ytupload.due("x", s, night), "outside the upload hours")
        with mock.patch.dict(os.environ, KEYS):
            self.run_once(side_effect=RuntimeError("YouTube upload not started (403): quotaExceeded"))
            self.assertIn("limit", ytupload.due("x", ytupload.settings({}), NOW + timedelta(hours=3)))      # no more tries today

    def test_wired_in(self):
        self.assertIn("ytupload.catchup(sys.modules[__name__])", (ROOT / "poster" / "post.py").read_text(encoding="utf-8"))
        wf = (ROOT / ".github" / "workflows" / "post.yml").read_text(encoding="utf-8")
        self.assertIn("YT_REFRESH_TOKEN_", wf)
        self.assertIn("git add -f poster/yt_uploaded", wf)
        self.assertEqual(json.loads((ROOT / "poster" / "config.json").read_text(encoding="utf-8"))["youtube_upload"]["privacy"], "public")      # owner 23 Nov


if __name__ == "__main__":
    unittest.main()
