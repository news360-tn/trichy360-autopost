"""14 Nov: Gmail's daily email limit stops the bridge's owner email (its LAST step, after the sheet row is saved).
That must count as recorded - not retried 5 times (which wrote the link into the sheet 5 times) and not reported as an error."""
import sys, unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "poster"))
import post      # noqa: E402


class EmailQuota(unittest.TestCase):
    def test_email_limit_counts_as_saved(self):
        err = RuntimeError("bridge posted: Exception: Service invoked too many times for one day: email.")
        with mock.patch.object(post, "_bridge_post", side_effect=err) as bp, mock.patch.object(post.time, "sleep"):
            self.assertTrue(post.bridge_post("posted", {"row": 5})["ok"])
        self.assertEqual(bp.call_count, 1)

    def test_other_errors_still_retry(self):
        with mock.patch.object(post, "_bridge_post", side_effect=[RuntimeError("timeout"), {"ok": True}]) as bp, \
                mock.patch.object(post.time, "sleep"):
            self.assertTrue(post.bridge_post("posted", {"row": 5})["ok"])
        self.assertEqual(bp.call_count, 2)


if __name__ == "__main__":
    unittest.main()
