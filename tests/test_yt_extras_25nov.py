"""owner 25 Nov: after a YouTube upload - the Instagram source comment as first comment, and the Short into its topic playlist.
With the upload-only login YouTube refuses (403): both are switched off for a day, and the upload is never affected."""
import json, sys, tempfile, unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "poster"))
import ytupload      # noqa: E402

NOW = datetime.now(timezone.utc)


class R:
    def __init__(self, code, body=None, text=""):
        self.status_code, self._b, self.text = code, body or {}, text or json.dumps(body or {})

    def json(self):
        return self._b


class Extras(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.p = mock.patch.object(ytupload, "STATE", self.d)
        self.p.start()
        self.calls = []

    def tearDown(self):
        self.p.stop()

    def post(self, answers):
        def f(url, **k):
            self.calls.append(url.rsplit("/", 1)[-1])
            return answers.pop(0)
        return mock.patch.object(ytupload.requests, "post", side_effect=f)

    def test_comment_then_playlist_made_once(self):
        with self.post([R(200), R(200, {"id": "PL1"}), R(200)]):
            ytupload.extras("salem", "t", "V1", "📰 Source: Dinamalar https://x", "சேலம் விபத்து: ஒருவர் பலி", NOW)
        self.assertEqual(self.calls, ["commentThreads", "playlists", "playlistItems"])
        self.assertEqual(ytupload._state("salem")["playlists"], {"accident news": "PL1"})
        self.calls.clear()
        with self.post([R(200), R(200)]):
            ytupload.extras("salem", "t", "V2", "c", "பைக் விபத்து", NOW)
        self.assertEqual(self.calls, ["commentThreads", "playlistItems"])      # the playlist is reused

    def test_upload_only_login_switches_off_for_a_day(self):
        no = R(403, text='{"error": {"errors": [{"reason": "insufficientPermissions"}]}}')
        with self.post([no]):
            ytupload.extras("salem", "t", "V1", "c", "x", NOW)
        self.assertEqual(self.calls, ["commentThreads"])
        self.calls.clear()
        with self.post([]):
            ytupload.extras("salem", "t", "V2", "c", "x", NOW + timedelta(hours=2))
        self.assertEqual(self.calls, [])      # no repeated refused calls
        with self.post([R(200), R(200, {"id": "P"}), R(200)]):
            ytupload.extras("salem", "t", "V3", "c", "x", NOW + timedelta(days=1, minutes=1))
        self.assertEqual(len(self.calls), 3)      # tried again the next day

    def test_never_raises(self):
        with mock.patch.object(ytupload.requests, "post", side_effect=OSError("down")):
            ytupload.extras("salem", "t", "V1", "c", "x", NOW)

    def test_playlist_names(self):
        self.assertEqual(ytupload._playlist_name("இன்றைய ராசிபலன்"), "rasi palan")
        self.assertEqual(ytupload._playlist_name("நாளை மின் தடை"), "power cut news")


if __name__ == "__main__":
    unittest.main()
