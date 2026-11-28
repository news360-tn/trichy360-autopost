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
PAGES = {"trichy": {"town": "திருச்சி", "name1": "திருச்சி", "logo": ROOT / "kit" / "logo_trichy.png", "handle": "trichy360.official"}}


def main():
    st = ROOT / "rasipalan" / "state"
    day = sys.argv[1] if len(sys.argv) > 1 else datetime.now(P.IST).date().isoformat()
    f = st / f"rasis_{PAGE}_{day}.json"
    if not f.exists():      # the latest day this page wrote
        f = sorted(st.glob(f"rasis_{PAGE}_*.json"))[-1]
        day = f.stem.split("_")[-1]
    rasis = json.loads(f.read_text(encoding="utf-8"))
    p = P.compute(datetime.fromisoformat(day).date(), PAGE)
    out = ROOT / "out" / "samples" / "parrot"
    print(f"parrot sample for {PAGE} {day} from {f.name}", flush=True)
    mp4 = rasi_parrot.make(PAGES[PAGE], {"p": p, "rasis": rasis}, out, lambda *a: print(*a, flush=True))
    print("done:", mp4, flush=True)


if __name__ == "__main__":
    main()
