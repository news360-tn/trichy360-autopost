import os, sys, unittest
from unittest import mock
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "poster"))
import requests
import post


class BridgeGetRetry(unittest.TestCase):
    """4 Nov: a slow Apps Script answer (read timeout) failed the whole post job before posting; the read is retried"""

    def _ok(self):
        r = mock.Mock(status_code=200)
        r.json.return_value = {"ok": True, "rows": []}
        r.raise_for_status.return_value = None
        return r

    def test_timeout_then_ok(self):
        calls = [requests.exceptions.ReadTimeout("slow"), self._ok()]
        with mock.patch.object(post.requests, "get", side_effect=calls) as g, mock.patch.object(post.time, "sleep"):
            self.assertEqual(post.bridge_get("queue")["rows"], [])
        self.assertEqual(g.call_count, 2)

    def test_gives_up_after_three(self):
        with mock.patch.object(post.requests, "get", side_effect=requests.exceptions.ReadTimeout("slow")) as g, \
                mock.patch.object(post.time, "sleep"):
            with self.assertRaises(requests.exceptions.ReadTimeout):
                post.bridge_get("queue")
        self.assertEqual(g.call_count, 3)


if __name__ == "__main__":
    unittest.main()
