"""python tools/repost.py RN-158 [RN-155 ...]  -> post a reel again after the owner removed it from Instagram (28 Oct: wrong text).
The Sheet takes the page's reel link out and queues the story again (bridge action 'repost'); the ready-made reel and its checked
text are deleted, so the posting job checks the text again (with the fixed proofread) and builds a new reel. Run by repost.yml."""
import json, os, sys
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "poster" / "prebuilt"


def main(ids):
    ids = [i.strip().upper() for i in ids if i.strip()]
    if not ids:
        sys.exit("give the story ids, e.g. RN-158")
    r = requests.post(os.environ["BRIDGE_URL"], params={"key": os.environ["BRIDGE_KEY"]},
                      data=json.dumps({"action": "repost", "ids": ids}), timeout=180)
    r.raise_for_status()
    res = r.json()
    if not res.get("ok"):
        sys.exit(f"Sheet did not accept the repost: {res.get('error')} (redeploy the Apps Script after updating Code.gs)")
    print("queued again in the Sheet:", res.get("reposted"))
    for sid in res.get("reposted") or []:
        for f in list(CACHE.glob(f"{sid}.json")) + list(CACHE.glob(f"{sid}_*.json")):
            if "_gvoice_" not in f.name:      # the free-voice usage record stays (monthly count)
                f.unlink()
                print("removed ready-made", f.name)


if __name__ == "__main__":
    main(" ".join(sys.argv[1:]).replace(",", " ").split())
