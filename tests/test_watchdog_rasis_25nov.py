"""owner 25 Nov: the shared rasipalan text files (rasipalan/state/rasis_<page>_<date>.json, a list) must not break the watchdog."""
import json, sys, unittest
from pathlib import Path
from unittest import mock
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "poster"))
import watchdog      # noqa: E402

PAGE = json.loads((ROOT / "poster" / "config.json").read_text(encoding="utf-8")).get("page") or "x"


class RasisFiles(unittest.TestCase):
    def run_with(self, files):
        with mock.patch.object(watchdog, "names", return_value=list(files)), \
                mock.patch.object(watchdog, "raw", side_effect=lambda p: files[p.split("/")[-1]]), \
                mock.patch.object(watchdog, "page_names", return_value=[PAGE], create=True):
            return watchdog.posted_today("rasipalan/state", "", "2026-11-25")

    def test_shared_text_file_is_ignored(self):
        files = {f"{PAGE}.json": json.dumps({"date": "2026-11-25"}),
                 f"rasis_{PAGE}_2026-11-25.json": json.dumps([{"rasi": "mesham", "text": "x"}])}
        self.assertTrue(self.run_with(files))

    def test_old_post_still_counts(self):
        files = {f"{PAGE}.json": json.dumps({"date": "2026-11-24"}), f"rasis_{PAGE}_2026-11-25.json": "[]"}
        self.assertFalse(self.run_with(files))


if __name__ == "__main__":
    unittest.main()
