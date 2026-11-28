"""owner 28 Nov: make the parrot rasipalan SAMPLE reel for the owner's review. Never posts: no Instagram / Facebook / Sheet code is used.
Uses the rasipalan text this page already wrote for the day (rasipalan/state/rasis_<page>_<day>.json) and today's panchangam.
  python tools/parrot_sample.py [YYYY-MM-DD]      -> out/samples/parrot/parrot_rasipalan_sample.mp4 + stills + script.txt"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "rasipalan"))
import rasi_panchang as P      # noqa: E402
import rasi_parrot      # noqa: E402

PAGE = os.environ.get("PAGE", "trichy")
_P = {"trichy": ("திருச்சி", "trichy360.official"), "namakkal": ("நாமக்கல்", "namakkal360.official"),
      "coimbatore": ("கோயம்புத்தூர்", "coimbatore360.official"), "erode": ("ஈரோடு", "erode360.official"),
      "salem": ("சேலம்", "salem360.official"), "karur": ("கரூர்", "karur360.official"), "tirupur": ("திருப்பூர்", "tiruppur360.official")}
PAGES = {k: {"town": n, "name1": n, "logo": ROOT / "kit" / f"logo_{k}.png", "handle": h} for k, (n, h) in _P.items()}


def main():
    st = ROOT / "rasipalan" / "state"
    day = sys.argv[1] if len(sys.argv) > 1 else datetime.now(P.IST).date().isoformat()
    f = st / f"rasis_trichy_{day}.json"      # the same 12 rasis on every page (each page's own panchangam, logo and colours)
    if not f.exists():      # the latest day written
        f = sorted(st.glob("rasis_trichy_*.json"))[-1]
        day = f.stem.split("_")[-1]
    rasis = json.loads(f.read_text(encoding="utf-8"))
    try:
        p = P.compute(datetime.fromisoformat(day).date(), PAGE)
    except Exception:
        p = P.compute(datetime.fromisoformat(day).date(), "trichy")
    out = ROOT / "out" / "samples" / "parrot"
    print(f"parrot sample for {PAGE} {day} from {f.name}", flush=True)
    mp4 = rasi_parrot.make(PAGES[PAGE], {"p": p, "rasis": rasis}, out, lambda *a: print(*a, flush=True))
    print("done:", mp4, flush=True)


if __name__ == "__main__":
    main()
