"""Cloudinary clean-up (owner 12 Nov): the free plan filled up because every reel / picture was kept for ever.
Instagram and Facebook copy a file when they post it, so the Cloudinary copy is only needed until the post (and the Facebook
retries, at most 24 h) are done.

Every run (from the post workflow; at most once an hour):
  - files of THIS page's folder only (FOLDER, e.g. "trichy360") older than KEEP_H (72 h) are deleted
    (a story is posted only on the news day or the day after, so nothing still waiting is ever older than 48 h)
  - when the account has used CLEAN_AT % (50) of its monthly credits, reel VIDEOS (the big files) older than
    FULL_KEEP_H (26 h - the Facebook retries stay safe) are deleted too. Pictures are small and stay 72 h.
  - a prebuilt reel whose link was deleted is uploaded again by post.py (load_cache checks the links), so nothing fails.
Never touches other folders (other pages may share the same Cloudinary account).
Needs CLOUDINARY_CLOUD + CLOUDINARY_API_KEY + CLOUDINARY_API_SECRET (Cloudinary -> Settings -> API Keys); skipped without them.
Usage: python poster/cloudclean.py [--force] [--dry]       (prints counts only - the repo is public)
"""
import os, sys, time
from datetime import datetime, timedelta, timezone

import requests

FOLDER = "trichy360"
KEEP_H = float(os.environ.get("CLOUDINARY_KEEP_HOURS", "72") or 72)
FULL_KEEP_H = float(os.environ.get("CLOUDINARY_FULL_KEEP_HOURS", "26") or 26)
CLEAN_AT = float(os.environ.get("CLOUDINARY_CLEAN_AT", "50") or 50)
API = "https://api.cloudinary.com/v1_1/{}/"


def log(*a):
    print("cloudinary:", *a, flush=True)


def _auth():
    return (os.environ.get("CLOUDINARY_API_KEY", "").strip(), os.environ.get("CLOUDINARY_API_SECRET", "").strip())


def used_percent(cloud, auth):
    """the share of the monthly free credits used (the free plan counts storage + bandwidth + transformations as credits)"""
    r = requests.get(API.format(cloud) + "usage", auth=auth, timeout=60)
    r.raise_for_status()
    j = r.json()
    c = j.get("credits") or {}
    if c.get("used_percent") is not None:
        return float(c["used_percent"])
    return max([float((j.get(k) or {}).get("used_percent") or 0) for k in ("storage", "bandwidth", "transformations")] or [0])


def mine(res):
    """this page's file? (fixed folders put the folder in the public_id; dynamic folders keep it in asset_folder)"""
    pid, af = str(res.get("public_id") or ""), str(res.get("asset_folder") or res.get("folder") or "")
    return af == FOLDER or af.startswith(FOLDER + "/") or pid.startswith(FOLDER + "/")


def listing(cloud, auth, kind, pages=20):
    out, cursor = [], None
    for _ in range(pages):
        prm = {"max_results": 500, "type": "upload", "fields": "public_id,asset_folder,folder,created_at,bytes"}
        if cursor:
            prm["next_cursor"] = cursor
        r = requests.get(API.format(cloud) + f"resources/{kind}", params=prm, auth=auth, timeout=60)
        r.raise_for_status()
        j = r.json()
        out += [x for x in j.get("resources", []) if mine(x)]
        cursor = j.get("next_cursor")
        if not cursor:
            break
    return out


def age_h(res, now):
    try:
        t = datetime.strptime(str(res.get("created_at")), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return 0.0      # unknown age: kept
    return (now - t).total_seconds() / 3600


def delete(cloud, auth, kind, ids):
    gone = 0
    for i in range(0, len(ids), 100):
        part = ids[i:i + 100]
        r = requests.delete(API.format(cloud) + f"resources/{kind}/upload", params=[("public_ids[]", p) for p in part], auth=auth, timeout=120)
        r.raise_for_status()
        gone += sum(1 for v in (r.json().get("deleted") or {}).values() if v == "deleted")
    return gone


def plan(files, kind, now, full):
    """which files to delete: older than KEEP_H, or (videos, when the account is CLEAN_AT % full) older than FULL_KEEP_H"""
    keep = FULL_KEEP_H if (full and kind == "video") else KEEP_H
    return [f["public_id"] for f in files if age_h(f, now) > keep]


def run(force=False, dry=False, now=None):
    cloud = os.environ.get("CLOUDINARY_CLOUD", "").strip()
    auth = _auth()
    if not (cloud and all(auth)):
        log("skipped - CLOUDINARY_API_KEY / CLOUDINARY_API_SECRET not set")
        return 0
    now = now or datetime.now(timezone.utc)
    if not force and now.minute >= 10:      # the post check runs every 5 minutes; the clean-up once an hour is enough
        return 0
    try:
        pct = used_percent(cloud, auth)
    except Exception as e:
        log(f"usage not read ({type(e).__name__}) - normal clean-up only")
        pct = 0.0
    full = pct >= CLEAN_AT
    log(f"{pct:.0f}% of the monthly credits used" + (f" (>= {CLEAN_AT:.0f}%: reels older than {FULL_KEEP_H:.0f} h are deleted too)" if full else ""))
    total, freed = 0, 0
    for kind in ("video", "image"):
        try:
            files = listing(cloud, auth, kind)
            ids = plan(files, kind, now, full)
            freed += sum(int(f.get("bytes") or 0) for f in files if f["public_id"] in set(ids))
            n = len(ids) if dry else (delete(cloud, auth, kind, ids) if ids else 0)
            total += n
            log(f"{kind}: {len(files)} files in {FOLDER}, {n} {'would be ' if dry else ''}deleted")
        except Exception as e:
            log(f"{kind}: clean-up skipped ({type(e).__name__}: {str(e)[:120]})")
    log(f"{total} files, about {freed / 1e6:.0f} MB {'would be ' if dry else ''}freed")
    return total


if __name__ == "__main__":
    run(force="--force" in sys.argv, dry="--dry" in sys.argv)
    sys.exit(0)      # never fails the posting run
