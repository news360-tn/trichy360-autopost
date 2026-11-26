"""owner 26 Nov: with Cloudflare R2 set up, Cloudinary (backup) credit / login problems no longer turn the clean-up run red."""
import os, sys, unittest
from pathlib import Path
from unittest import mock
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "poster"))
import cloudclean      # noqa: E402
import r2host      # noqa: E402


class CloudcleanAlert(unittest.TestCase):
    def setUp(self):
        cloudclean.PROBLEMS[:] = ["85% of the monthly credits used"]

    def tearDown(self):
        cloudclean.PROBLEMS[:] = []

    def test_with_r2_yellow_and_exit_0(self):
        with mock.patch.object(r2host, "enabled", return_value=True), mock.patch("builtins.print") as p:
            self.assertEqual(cloudclean.exit_code(True), 0)
        self.assertIn("::warning", str(p.call_args_list))
        self.assertNotIn("::error", str(p.call_args_list))

    def test_without_r2_still_red(self):
        with mock.patch.object(r2host, "enabled", return_value=False), mock.patch("builtins.print") as p:
            self.assertEqual(cloudclean.exit_code(True), 1)
        self.assertIn("::error", str(p.call_args_list))

    def test_no_problems_or_no_alert_is_green(self):
        self.assertEqual(cloudclean.exit_code(False), 0)
        cloudclean.PROBLEMS[:] = []
        self.assertEqual(cloudclean.exit_code(True), 0)


if __name__ == "__main__":
    unittest.main()
