"""owner 20 Nov: old files are cleaned every 6 hours and a clean-up that cannot work turns red (never silent again)"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "poster"))
import cloudclean as cc      # noqa: E402

ENV = {"CLOUDINARY_CLOUD": "x", "CLOUDINARY_API_KEY": "k", "CLOUDINARY_API_SECRET": "s"}


def answer(code, body):
    r = mock.Mock(status_code=code)
    r.json = lambda: body
    r.raise_for_status = (lambda: None) if code == 200 else mock.Mock(side_effect=requests.HTTPError(f"{code} Client Error: Unauthorized"))
    return r


class Alert(unittest.TestCase):
    def setUp(self):
        cc.PROBLEMS.clear()

    def run_with(self, usage, listing):
        def get(url, params=None, auth=None, timeout=None):
            return usage if url.endswith("usage") else listing
        with mock.patch.dict("os.environ", ENV), mock.patch.object(cc.requests, "get", side_effect=get):
            cc.run(force=True, dry=True)
        return list(cc.PROBLEMS)

    def test_refused_login_is_a_problem(self):      # Coimbatore 18-20 Nov: 401 on every call, the job was green
        p = self.run_with(answer(401, {}), answer(401, {}))
        self.assertTrue(any("usage not read" in x for x in p))
        self.assertTrue(any("video: clean-up skipped" in x for x in p))

    def test_nearly_full_is_a_problem(self):
        p = self.run_with(answer(200, {"credits": {"used_percent": 85.0}}), answer(200, {"resources": []}))
        self.assertEqual(len(p), 1)
        self.assertIn("85% of the monthly credits", p[0])

    def test_healthy_run_has_no_problem(self):
        self.assertEqual(self.run_with(answer(200, {"credits": {"used_percent": 54.0}}), answer(200, {"resources": []})), [])

    def test_only_the_alert_run_fails(self):      # the posting job never fails because of the clean-up
        env = dict(ENV, CLOUDINARY_API_KEY="", CLOUDINARY_API_SECRET="")      # no keys: skipped, no network
        script = str(ROOT / "poster" / "cloudclean.py")
        self.assertEqual(subprocess.run([sys.executable, script, "--force"], env=env).returncode, 0)

    def test_schedule_every_6_hours_with_alert(self):
        wf = (ROOT / ".github" / "workflows" / "cloudclean.yml").read_text(encoding="utf-8")
        self.assertIn('cron: "40 1,7,13,19 * * *"', wf)
        self.assertIn("cloudclean.py --force --alert", wf)
        self.assertEqual(cc.KEEP_H, 48.0)      # owner 12 Nov: the last 48 hours are kept
        self.assertEqual(cc.FOLDER, "trichy360")


if __name__ == "__main__":
    unittest.main()
