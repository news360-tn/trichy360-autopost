"""owner 21 Nov: a news picture that can no longer be downloaded (old Cloudinary account: 401) never blocks the page"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "poster"))
import post      # noqa: E402


def dead(url, timeout=0):
    r = requests.Response()
    r.status_code = 401
    r.url = url
    return r


class DeadPicture(unittest.TestCase):
    def test_reel_made_on_the_designed_background(self):
        work = Path(tempfile.mkdtemp())
        row = {"story_id": "RN-502", "images": json.dumps(["https://res.cloudinary.com/old/image/upload/x.jpg"] * 2), "category": "மின் தடை"}
        with mock.patch.object(post.requests, "get", side_effect=dead):
            out = post.fetch_images(row, work)
        self.assertTrue(out)
        self.assertTrue(all(Path(x).name == "plain_bg.jpg" for x in out))

    def test_other_errors_still_raise(self):
        def boom(url, timeout=0):
            r = requests.Response()
            r.status_code = 500
            r.url = url
            return r
        row = {"story_id": "RN-1", "images": json.dumps(["https://x/y.jpg"])}
        with mock.patch.object(post.requests, "get", side_effect=boom):
            with self.assertRaises(requests.HTTPError):
                post.fetch_images(row, Path(tempfile.mkdtemp()))


if __name__ == "__main__":
    unittest.main()
