"""owner 27 Nov (Trichy views test on all three platforms): views of each Facebook reel and each YouTube Short, read once a day by
insights.py, so a change can be compared on Facebook and YouTube too (Instagram already has insights/history.json).

  poster/insights/facebook.json   {video id: {story, at, plays, reach, avg_watch_s, follows, read}}
  poster/insights/youtube.json    {video id: {title, at, daily, views, likes, comments, read}}

Read-only. A refused metric, a missing secret or a network error is logged and skipped - posting and the Instagram insights are never
touched. A reel is read while it is younger than KEEP_DAYS; older rows stay as their last reading."""
import datetime
import json
import os

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "insights")
KEEP_DAYS = 8
FB_MAX_READS = 60      # Meta calls per run (one per reel)
FB_METRICS = ("fb_reels_total_plays", "post_impressions_unique", "post_video_avg_time_watched", "post_video_followers")


def _load(name):
    try:
        return json.load(open(os.path.join(OUT, name), encoding="utf-8"))
    except Exception:
        return {}


def _save(name, d):
    os.makedirs(OUT, exist_ok=True)
    json.dump(d, open(os.path.join(OUT, name), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def _age_days(ts, now):
    try:
        t = datetime.datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        if t.tzinfo is None:
            t = t.replace(tzinfo=datetime.timezone.utc)
        return (now - t).total_seconds() / 86400
    except Exception:
        return 999


def _fb_values(data):
    """{metric: value} from a video_insights answer"""
    out = {}
    for d in data or []:
        v = (d.get("values") or [{}])[0].get("value")
        if isinstance(v, (int, float)):
            out[d.get("name")] = v
    return out


def facebook_reels(page, now=None, call=None):
    """plays / reach / average watch time / new followers of this page's Facebook reels posted in the last KEEP_DAYS days"""
    import facebook
    now = now or datetime.datetime.now(datetime.timezone.utc)
    c = facebook.creds(page)
    if not c:
        print(page, "Facebook reel views not read (page secrets missing)")
        return 0
    call = call or facebook._call
    hist, reads = _load("facebook.json"), 0
    folder = os.path.join(HERE, "fb_posted")
    for name in sorted(os.listdir(folder) if os.path.isdir(folder) else [], reverse=True):
        if reads >= FB_MAX_READS:
            break
        if not (name.startswith(page + "-") and name.endswith(".json")):
            continue
        try:
            rec = json.load(open(os.path.join(folder, name), encoding="utf-8"))
        except Exception:
            continue
        vid, at = str(rec.get("id") or ""), rec.get("posted_at") or ""
        if rec.get("status") != "posted" or rec.get("kind") != "reel" or not vid or _age_days(at, now) > KEEP_DAYS:
            continue
        got = {}
        try:
            got = _fb_values((call("GET", f"{vid}/video_insights", c[1], metric=",".join(FB_METRICS)) or {}).get("data"))
        except Exception:      # one unknown metric refuses the whole list: ask for the plays alone
            try:
                got = _fb_values((call("GET", f"{vid}/video_insights", c[1], metric=FB_METRICS[0]) or {}).get("data"))
            except Exception as e:
                print(page, "Facebook reel not read:", vid, str(e)[:120])
        reads += 1
        if not got:
            continue
        ms = got.get("post_video_avg_time_watched")
        hist[vid] = {"page": page, "story": rec.get("story") or "", "at": at, "plays": got.get("fb_reels_total_plays"),
                     "reach": got.get("post_impressions_unique"), "avg_watch_s": round(ms / 1000, 1) if isinstance(ms, (int, float)) else None,
                     "follows": got.get("post_video_followers"), "read": now.isoformat(timespec="minutes")}
    _save("facebook.json", hist)
    print(page, "Facebook reels read:", reads)
    return reads


def youtube_shorts(page, now=None, get=None):
    """views / likes / comments of this page's Shorts uploaded in the last KEEP_DAYS days (one API unit per 50 videos)"""
    import ytupload
    now = now or datetime.datetime.now(datetime.timezone.utc)
    if not ytupload.keys(page):
        print(page, "YouTube views not read (the page's YT secrets are not in this job)")
        return 0
    hist = _load("youtube.json")
    for u in ytupload._state(page).get("uploads", []):      # the upload job keeps 3 days; this file keeps every Short it has seen
        vid = u.get("youtube")
        if vid and vid not in hist:
            hist[vid] = {"page": page, "title": u.get("title") or "", "at": u.get("at") or "", "daily": bool(u.get("daily"))}
    ids = [v for v, r in hist.items() if r.get("page") == page and _age_days(r.get("at"), now) <= KEEP_DAYS]
    if not ids:
        _save("youtube.json", hist)
        return 0
    get = get or requests.get
    tok, n = ytupload.access_token(page), 0
    for i in range(0, len(ids), 50):
        r = get("https://www.googleapis.com/youtube/v3/videos", params={"part": "statistics", "id": ",".join(ids[i:i + 50])},
                headers={"Authorization": "Bearer " + tok}, timeout=60)
        if r.status_code != 200:
            print(page, "YouTube views not read:", r.status_code, r.text[:150])
            break
        for it in r.json().get("items") or []:
            st = it.get("statistics") or {}
            hist[it["id"]].update(views=int(st.get("viewCount") or 0), likes=int(st.get("likeCount") or 0),
                                  comments=int(st.get("commentCount") or 0), read=now.isoformat(timespec="minutes"))
            n += 1
    _save("youtube.json", hist)
    print(page, "YouTube Shorts read:", n)
    return n


def read_all(page):
    for name, fn in (("Facebook", facebook_reels), ("YouTube", youtube_shorts)):
        try:
            fn(page)
        except Exception as e:
            print(page, name, "views not read:", str(e)[:200])
