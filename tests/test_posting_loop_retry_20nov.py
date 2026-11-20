"""owner 20 Nov: starting the next posting run is tried 3 times (Trichy 20 Nov: one HTTP 500 stopped the loop for an hour)"""
import unittest
from pathlib import Path

WF = (Path(__file__).resolve().parent.parent / ".github" / "workflows" / "post.yml").read_text(encoding="utf-8")


class PostingLoopRetry(unittest.TestCase):
    def test_every_restart_of_the_loop_is_retried(self):
        for line in WF.splitlines():
            if ("post.yml/dispatches" in line or "workflow run post.yml" in line) and not line.strip().startswith("#"):
                self.assertIn("for i in 1 2 3", line, line.strip()[:120])
                self.assertIn("break", line)

    def test_the_live_loop_restart_is_there(self):
        self.assertIn("next posting run started", WF)
        self.assertIn("next run not started after 3 tries", WF)


if __name__ == "__main__":
    unittest.main()
