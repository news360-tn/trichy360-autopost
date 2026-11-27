"""owner 26 Nov: Trichy views test - compare reels posted BEFORE the test with reels posted DURING it (poster/config.json views_test).
Reads poster/insights/history.json (written by insights.yml). Run:  python3 tools/views_test.py
Fair comparison: a reel is counted only once it is at least 24 h old (r24 numbers when there are any)."""
import json, statistics, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "poster" / "config.json").read_text(encoding="utf-8"))
START = (CFG.get("views_test") or {}).get("start_ist", "2026-11-27")
IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))


def when(ts):
    return datetime.datetime.fromisoformat(str(ts).replace("+0000", "+00:00").replace("Z", "+00:00")).astimezone(IST)


def summary(name, rows):
    if not rows:
        print(f"{name:<22} no reels yet")
        return
    v = [r.get("views") or 0 for r in rows]
    w = [(r.get("ig_reels_avg_watch_time") or 0) / 1000 for r in rows]
    sk = [r["reels_skip_rate"] for r in rows if r.get("reels_skip_rate") is not None]
    reach = sum(r.get("reach") or 0 for r in rows) or 1
    sh = sum(r.get("shares") or 0 for r in rows) / reach * 100
    sv = sum(r.get("saved") or 0 for r in rows) / reach * 100
    print(f"{name:<22} reels {len(rows):>4} | median views {statistics.median(v):>7.0f} | mean {statistics.mean(v):>7.0f} | "
          f"under 500: {sum(x < 500 for x in v) / len(v) * 100:>3.0f}% | watch {statistics.median(w):>4.1f}s | "
          f"shares/reach {sh:.2f}% | saves/reach {sv:.2f}%" + (f" | skip {statistics.median(sk):.0f}%" if sk else ""))


def main():
    hist = json.loads((ROOT / "poster" / "insights" / "history.json").read_text(encoding="utf-8"))
    now = datetime.datetime.now(IST)
    rows = [r for r in hist.values() if isinstance(r, dict) and r.get("type") != "FEED" and r.get("views") is not None
            and (now - when(r["t"])).total_seconds() >= 24 * 3600]
    before = [r for r in rows if when(r["t"]).date().isoformat() < START]
    during = [r for r in rows if when(r["t"]).date().isoformat() >= START]
    print(f"Trichy 360 views test (start {START} IST) - reels at least 24 h old\n")
    summary("BEFORE (long reels)", before[-300:])
    summary("DURING (short reels)", during)
    print("\nDuring the test, by voice:")
    voices = sorted({(r.get("variant") or {}).get("voice", "?") for r in during})
    for vc in voices:
        summary("  " + vc.replace("ta-IN-", "").replace("Neural", ""), [r for r in during if (r.get("variant") or {}).get("voice", "?") == vc])
    print("\nDuring the test, by design (A classic, B TV band, C centred, P premium):")
    for dz in sorted({(r.get("variant") or {}).get("design", "?") for r in during}):
        summary("  design " + dz, [r for r in during if (r.get("variant") or {}).get("design", "?") == dz])
    print("\nDuring the test, by number of pictures:")
    for pn in sorted({(r.get("variant") or {}).get("pictures", 0) for r in during}):
        summary(f"  {pn} pictures", [r for r in during if (r.get("variant") or {}).get("pictures", 0) == pn])
    print("\nDuring the test, by reel length:")
    for lo, hi in ((0, 25), (25, 35), (35, 50), (50, 999)):
        summary(f"  {lo}-{hi if hi < 999 else '+'} s", [r for r in during if lo <= ((r.get("variant") or {}).get("secs") or -1) < hi])
    print("\nDuring the test, by topic:")
    for tp in sorted({r.get("topic") for r in during}):
        summary("  " + str(tp), [r for r in during if r.get("topic") == tp])
    by_day = {}
    for r in before + during:
        by_day.setdefault(when(r["t"]).date().isoformat(), []).append(r.get("views") or 0)
    print("\nPer day (posting count stays the same - compare the totals):")
    for d in sorted(by_day)[-10:]:
        print(f"  {d}  reels {len(by_day[d]):>3}  total views {sum(by_day[d]):>8}  median {statistics.median(by_day[d]):>6.0f}"
              + ("   <- test" if d >= START else ""))


def other_platforms():
    """owner 27 Nov: Facebook reels and YouTube Shorts per day (poster/insights/facebook.json, youtube.json - written by insights.yml)"""
    for name, fname, key in (("Facebook reels (plays)", "facebook.json", "plays"), ("YouTube Shorts (views)", "youtube.json", "views")):
        try:
            rows = json.loads((ROOT / "poster" / "insights" / fname).read_text(encoding="utf-8")).values()
        except Exception:
            print(f"\n{name}: no numbers yet (the next insights run writes them)")
            continue
        by_day = {}
        for r in rows:
            if r.get(key) is not None and r.get("at"):
                by_day.setdefault(when(r["at"]).date().isoformat(), []).append(r[key])
        print(f"\n{name} per day:")
        for d in sorted(by_day)[-10:]:
            print(f"  {d}  videos {len(by_day[d]):>3}  total {sum(by_day[d]):>8}  median {statistics.median(by_day[d]):>6.0f}" + ("   <- test" if d >= START else ""))


if __name__ == "__main__":
    main()
    other_platforms()
