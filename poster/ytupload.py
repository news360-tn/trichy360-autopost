"""owner 21 Nov: news reels go to each page's YouTube channel as Shorts AUTOMATICALLY (YouTube Data API v3, the official way).

A page uploads only when its YouTube keys are in GitHub Secrets (one Google Cloud project per page - each project gets
10,000 quota units a day and one upload costs 1,600, so about 6 uploads a day):
  YT_CLIENT_ID_<PAGE>, YT_CLIENT_SECRET_<PAGE>, YT_REFRESH_TOKEN_<PAGE>   (e.g. YT_REFRESH_TOKEN_NAMAKKAL)
Without them nothing happens for that page (the twice-a-day YouTube e-mail stays as it is).
Rules (config.json "youtube_upload"):
  per_day 5      the most useful news reels of the day first (power cuts / alerts, camps / jobs / schemes, then the newest)
  gap_min 90     never a burst: at least 90 minutes between two uploads on one channel
  hours 9-21     IST, only in the day
  privacy        "private" until Google approves the project's YouTube API audit (Google keeps uploads of an unaudited project
                 private anyway); then "public"
The video is read from the Instagram post (no Cloudinary); title / description / tags as in the YouTube e-mail (youtube.py).
Called by post.py's posting check - at most ONE upload per page per run. Records: poster/yt_uploaded/<page>.json (committed).
Never raises."""
import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
STATE = HERE / "yt_uploaded"
IST = timezone(timedelta(hours=5, minutes=30))
TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"


def log(*a):
    print(datetime.now(IST).strftime("%H:%M:%S"), "  youtube upload:", *a, flush=True)


def keys(page):
    k = re.sub(r"[^A-Z0-9]", "_", page.upper())
    vals = [os.environ.get(f"YT_{n}_{k}", "").strip() for n in ("CLIENT_ID", "CLIENT_SECRET", "REFRESH_TOKEN")]
    return vals if all(vals) else None


def settings(config):
    s = dict({"enabled": True, "per_day": 5, "gap_min": 90, "hours": [9, 21], "privacy": "private"}, **((config or {}).get("youtube_upload") or {}))
    s["per_day"] = min(int(s["per_day"]), 30)      # owner 23 Nov: uploads now have their own 100-a-day API allowance (was 6 x 1,600 units); 30 keeps the channel safe
    return s


def _state(page):
    try:
        return json.loads((STATE / f"{page}.json").read_text(encoding="utf-8"))
    except Exception:
        return {"uploads": []}


def _save(page, d):
    STATE.mkdir(parents=True, exist_ok=True)
    cut = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    d["uploads"] = [u for u in d.get("uploads", []) if u.get("at", "") >= cut]
    (STATE / f"{page}.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def due(page, s, now):
    """'' when this channel may upload now, else why not"""
    ist = now.astimezone(IST)
    if not (s["hours"][0] <= ist.hour < s["hours"][1]):
        return "outside the upload hours"
    ups = _state(page).get("uploads", [])
    day = ist.strftime("%Y-%m-%d")
    today = [u for u in ups if u.get("day") == day]
    if len(today) >= s["per_day"]:
        return f"{len(today)} uploads today - the day's limit"
    last = max((u.get("at", "") for u in ups), default="")
    if last and (now - datetime.fromisoformat(last)).total_seconds() < s["gap_min"] * 60:
        return f"less than {s['gap_min']} min since the last upload"
    return ""


def access_token(page):
    cid, sec, ref = keys(page)
    r = requests.post(TOKEN_URL, data={"client_id": cid, "client_secret": sec, "refresh_token": ref, "grant_type": "refresh_token"}, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"YouTube login refused ({r.status_code}): {r.text[:200]}")
    return r.json()["access_token"]


def upload(token, path, title, description, tags, privacy):
    """resumable upload (YouTube Data API v3 videos.insert); returns the video id"""
    meta = {"snippet": {"title": title[:100], "description": description[:4900], "tags": [t.strip() for t in tags.split(",") if t.strip()][:15],
                        "categoryId": "25"},      # 25 = News & Politics
            "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False}}
    size = os.path.getsize(path)
    r = requests.post(UPLOAD_URL, params={"uploadType": "resumable", "part": "snippet,status"},
                      headers={"Authorization": "Bearer " + token, "Content-Type": "application/json; charset=UTF-8",
                               "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(size)},
                      data=json.dumps(meta, ensure_ascii=False).encode("utf-8"), timeout=60)
    if r.status_code != 200 or not r.headers.get("Location"):
        raise RuntimeError(f"YouTube upload not started ({r.status_code}): {r.text[:300]}")
    with open(path, "rb") as f:
        u = requests.put(r.headers["Location"], headers={"Authorization": "Bearer " + token, "Content-Type": "video/mp4"}, data=f, timeout=600)
    if u.status_code not in (200, 201):
        raise RuntimeError(f"YouTube upload refused ({u.status_code}): {u.text[:300]}")
    return u.json()["id"]


def catchup(post, now=None):
    """one upload per page per run, for every page with its YouTube keys"""
    import localmedia
    import youtube
    now = now or datetime.now(timezone.utc)
    s = settings(post.CONFIG)
    if not s["enabled"] or post.DRY:
        return
    for page in post.LABEL:
        try:
            if not keys(page):
                continue
            why = due(page, s, now)
            if why:
                log(f"{page}: waits ({why})")
                continue
            st = _state(page)
            done = {u.get("ig") for u in st.get("uploads", [])}
            token = post.bridge_get("token", page=page)["token"]
            uname = post.ig_account(token)[1]
            day = now.astimezone(IST).strftime("%Y-%m-%d")
            feed = post.ig("GET", "me/media", token, fields="id,caption,media_type,permalink,timestamp,media_url", limit=40).get("data") or []
            news = [m for m in feed if m.get("media_type") == "VIDEO" and m.get("id") not in done and m.get("timestamp")
                    and not youtube.SKIP.search(m.get("caption") or "") and youtube.when(m["timestamp"]).strftime("%Y-%m-%d") == day]
            best = youtube.pick(news, 1)
            if not best:
                log(f"{page}: no new news reel to upload")
                continue
            m = best[0]
            path = localmedia.download(m.get("media_url") or "", "youtube.mp4") if m.get("media_url") else None
            if not path:
                log(f"{page}: the reel's video could not be read - tried again in a later run")
                continue
            d = youtube.details(m, page, uname)
            vid = upload(access_token(page), path, d["title"], d["description"], d["tags"], s["privacy"])
            st.setdefault("uploads", []).append({"ig": m["id"], "youtube": vid, "day": day, "at": now.isoformat(timespec="seconds"),
                                                 "title": d["title"]})
            _save(page, st)
            log(f"{page}: uploaded to YouTube ({s['privacy']}) https://youtube.com/shorts/{vid} - {d['title'][:60]}")
        except Exception as e:
            log(f"{page}: not uploaded (tried again in a later run):", str(e)[:250])
            if "quotaExceeded" in str(e) or "uploadLimitExceeded" in str(e):      # the day's YouTube limit: no more tries today
                st = _state(page)
                st.setdefault("uploads", []).extend({"ig": "", "youtube": "", "day": now.astimezone(IST).strftime("%Y-%m-%d"),
                                                     "at": now.isoformat(timespec="seconds"), "title": "limit"} for _ in range(6))
                _save(page, st)
