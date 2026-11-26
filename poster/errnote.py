"""owner 26 Nov (Trichy): a posting error on ANY platform (Instagram, Facebook, YouTube) is noted at once - in the job log as a GitHub
error line and in poster/posting_errors.json (the last 300 errors, committed by post.yml / youtube.yml) - and that post is NOT tried
again straight away: the next try is after config "post_error_wait_min" minutes (10). Never raises."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILE = ROOT / "poster" / "posting_errors.json"
KEEP = 300


def config():
    try:
        return json.loads((ROOT / "poster" / "config.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def wait_min():
    """minutes before a failed post is tried again (owner 26 Nov: 10)"""
    try:
        return float(config().get("post_error_wait_min", 10))
    except (TypeError, ValueError):
        return 10.0


def strict():
    """True: no quick repeat inside the same run after a posting error (the post waits wait_min minutes)"""
    return bool(config().get("no_quick_retry", False))


def note(platform, story, error, wait=None, page=""):
    """write the error down now; returns the time of the next try (ISO, UTC)"""
    try:
        now = datetime.now(timezone.utc)
        w = wait_min() if wait is None else float(wait)
        nxt = (now + timedelta(minutes=w)).isoformat(timespec="seconds")
        msg = str(error).replace("\n", " ")[:400]
        print(f"::error title={platform} post error {story}::{msg[:200]} - next try after {w:g} min", flush=True)
        try:
            items = json.loads(FILE.read_text(encoding="utf-8")) if FILE.exists() else []
        except Exception:
            items = []
        items.append({"at": now.isoformat(timespec="seconds"), "platform": platform, "page": page, "story": str(story or ""),
                      "error": msg, "next_try": nxt})
        FILE.write_text(json.dumps(items[-KEEP:], ensure_ascii=False, indent=1), encoding="utf-8")
        return nxt
    except Exception as e:
        print("posting error not noted:", str(e)[:120], flush=True)
        return ""
