"""owner 21 Nov (safe method only): the direct-upload trial stays OFF - Instagram refused it on every reel ("The parameter video_url
is required"), the reel then went by its Cloudinary link anyway, and the trial had downloaded each reel from Cloudinary once more first"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class DirectUploadOff(unittest.TestCase):
    def test_switched_off(self):
        wf = (ROOT / ".github" / "workflows" / "post.yml").read_text(encoding="utf-8")
        m = re.search(r'^\s*DIRECT_UPLOAD:\s*"?([^"\s#]*)"?', wf, re.M)
        self.assertIsNotNone(m)
        self.assertNotIn(m.group(1).lower(), ("1", "true", "yes", "on"))


if __name__ == "__main__":
    unittest.main()
