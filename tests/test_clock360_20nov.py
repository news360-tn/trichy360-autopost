"""owner 20 Nov: the 360 clock branding on every news reel - a layer over the finished page, the reel itself never changes or fails"""
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "reel"))
import clock360  # noqa: E402

PAGE = ('<!doctype html><html><head><style>body{}</style></head><body><img id="plogo" src="x">'
        '<div id="end"><img src="x"></div><script>const D={};window.renderAt=function(t){};</script></body></html>')


class Clock360(unittest.TestCase):
    def setUp(self):
        os.environ.pop("REEL_CLOCK360", None)

    def test_layer_added_once(self):
        out = clock360.add(PAGE)
        for x in ('id="cklogo"', 'id="ckend"', 'id="ckhand"', 'id="ckpiv"', "#ckend .tk line", "const old=window.renderAt"):
            self.assertEqual(out.count(x), 1, x)
        self.assertLess(out.index('id="cklogo"'), out.index('<div id="end">'))
        self.assertEqual(clock360.add(out), out)      # never twice
        self.assertTrue(out.startswith(PAGE.split("<style>")[0]))
        self.assertIn('<img id="plogo" src="x">', out)      # the design is untouched

    def test_unexpected_page_unchanged(self):
        for bad in (PAGE.replace('id="plogo"', 'id="x"'), PAGE.replace('<div id="end">', "<div>"),
                    PAGE.replace("window.renderAt", "window.r"), "", PAGE.replace("</style>", "</style><style></style>")):
            self.assertEqual(clock360.add(bad), bad)
        self.assertEqual(clock360.add(None), None)

    def test_switch_off(self):
        os.environ["REEL_CLOCK360"] = "0"
        self.assertEqual(clock360.add(PAGE), PAGE)
        os.environ.pop("REEL_CLOCK360")

    def test_wired_into_news_reel(self):
        src = (ROOT / "reel" / "reel4.py").read_text(encoding="utf-8")
        self.assertIn("page.write_text(clock360.add(build_html(spec, shots, sents, caps, hook_end, end_t, total, R.PAGE)))", src)


if __name__ == "__main__":
    unittest.main()
