"""owner 25 Nov ("2"): when every AI writer is busy, a page uses the same day's rasipalan text another 360 page already wrote."""
import sys, unittest
from datetime import date
from pathlib import Path
from unittest import mock
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "rasipalan"))
sys.path.insert(0, str(ROOT / "poster"))
import rasi_daily      # noqa: E402


class Resp:
    def __init__(self, code, data=None):
        self.status_code, self._d = code, data

    def json(self):
        return self._d


class RasiShare25Nov(unittest.TestCase):
    def test_takes_the_first_page_that_has_it(self):
        calls = []
        def get(url, timeout=0):
            calls.append(url)
            return Resp(200, [{"rasi": "மேஷம்", "text": "நல்ல நாள்"}]) if len(calls) == 2 else Resp(404)
        with mock.patch("requests.get", side_effect=get):
            rs = rasi_daily.borrowed_rasis(date(2026, 11, 25))
        self.assertEqual(rs[0]["rasi"], "மேஷம்")
        self.assertTrue(all("rasis_" in u and "2026-11-25" in u for u in calls))
        self.assertFalse(any(f"/rasis_{rasi_daily.PAGE}_" in u for u in calls))      # never its own

    def test_none_when_no_page_has_it(self):
        with mock.patch("requests.get", return_value=Resp(404)):
            self.assertIsNone(rasi_daily.borrowed_rasis(date(2026, 11, 25)))

    def test_wired(self):
        src = (ROOT / "rasipalan" / "rasi_daily.py").read_text(encoding="utf-8")
        self.assertIn("rs = borrowed_rasis(day)", src)
        self.assertIn('f"rasis_{PAGE}_{day.isoformat()}.json"', src)


if __name__ == "__main__":
    unittest.main()
