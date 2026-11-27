"""owner 27 Nov: the gold-rate and rasipalan reels have each page's own colour theme; the content (every word and number) is the same."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "goldrate"))
import gold360_render as D      # noqa: E402

PAGE = '<html><head><style>body{color:#3A070B;background:#8E1218} .x{color:#F0DADB;box-shadow:0 0 0 rgba(58,7,11,.3)}</style></head><body>₹92,880 திருப்பூர்</body></html>'


def strip_colours(h):
    return re.sub(r"#[0-9A-Fa-f]{6}|rgba\(\d+,\d+,\d+,|\.scene\.gold\{--bg:[^}]*\}", "", h)


def test_every_page_has_its_own_colour():
    darks = [t[0] for t in D.THEMES.values()]
    assert len(set(darks)) == len(darks)
    for name in ("திருப்பூர்", "கோவை", "ஈரோடு", "கரூர்", "நாமக்கல்", "இராசிபுரம்", "சேலம்", "திருச்சி"):
        assert name in D.THEMES


def test_only_colours_change():
    for name, t in D.THEMES.items():
        out = D.themed(PAGE, {"name1": name}, rasi=True)
        assert strip_colours(out) == strip_colours(PAGE), name
        if name != "திருப்பூர்":
            assert "#3A070B" not in out and "58,7,11" not in out and t[0] in out


def test_unknown_page_keeps_maroon():
    assert D.themed(PAGE, {"name1": "x"}) == PAGE
