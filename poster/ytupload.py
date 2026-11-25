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


RETRY_WAIT_MIN = 10      # owner 25 Nov: a failed upload waits 10 minutes before the next try


def log(*a):
    print(datetime.now(IST).strftime("%H:%M:%S"), "  youtube upload:", *a, flush=True)


def keys(page):
    k = re.sub(r"[^A-Z0-9]", "_", page.upper())
    vals = [os.environ.get(f"YT_{n}_{k}", "").strip() for n in ("CLIENT_ID", "CLIENT_SECRET", "REFRESH_TOKEN")]
    return vals if all(vals) else None


def settings(config):
    s = dict({"enabled": True, "per_day": 5, "gap_min": 90, "hours": [9, 21], "privacy": "private"}, **((config or {}).get("youtube_upload") or {}))
    s["per_day"] = min(int(s["per_day"]), 35)      # owner 25 Nov: up to 35 a day, the same as Instagram      # owner 23 Nov: uploads now have their own 100-a-day API allowance (was 6 x 1,600 units); 30 keeps the channel safe
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


def due(page, s, now, daily=False):
    """'' when this channel may upload now, else why not. owner 25 Nov: the daily rasipalan / gold rate (daily=True) never count
    for the day's news limit and still go when it is reached - but not after YouTube itself refused (quota / upload limit)"""
    ist = now.astimezone(IST)
    if not (s["hours"][0] <= ist.hour < s["hours"][1]):
        return "outside the upload hours"
    ups = _state(page).get("uploads", [])
    day = ist.strftime("%Y-%m-%d")
    today = [u for u in ups if u.get("day") == day]
    if daily:
        if any(u.get("title") == "limit" for u in today):
            return "YouTube's own daily limit was reached (quota) - no more uploads today"
    else:
        news = [u for u in today if not u.get("daily")]
        if len(news) >= s["per_day"]:
            return f"{len(news)} uploads today - the day's limit"
    err = _state(page).get("failed_at")
    if err and (now - datetime.fromisoformat(err)).total_seconds() < RETRY_WAIT_MIN * 60:
        return f"an upload error less than {RETRY_WAIT_MIN} min ago - tried again after {RETRY_WAIT_MIN} minutes"
    last = max((u.get("at", "") for u in ups), default="")
    if last and (now - datetime.fromisoformat(last)).total_seconds() < s["gap_min"] * 60:
        return f"less than {s['gap_min']} min since the last upload"
    return ""


API = "https://www.googleapis.com/youtube/v3"
PLAYLIST_TOPIC = {"power_cut": "power cut news", "accident": "accident news", "crime": "crime news", "jobs": "jobs news",
                  "weather": "weather news", "temple": "temple news", "politics": "politics news"}


def _playlist_name(cap):
    """the topic playlist of a Short: rasipalan / gold rate / power cut / accident / crime / jobs / ... / other news"""
    if re.search(r"ராசிபலன்", cap or ""):
        return "rasi palan"
    if re.search(r"தங்கம்.{0,25}விலை|Gold rate|GoldRate", cap or "", re.I):
        return "gold rate"
    try:
        import sys as _s
        _s.path.insert(0, str(HERE.parent / "research_free"))
        import learned
        return PLAYLIST_TOPIC.get(learned.topic(cap or ""), "news")
    except Exception:
        return "news"


def extras(page, tok, vid, comment, cap, now=None):
    """owner 25 Nov: after an upload - (1) the Instagram source comment as the Short's first comment, (2) the Short into its topic
    playlist (created once per channel). Both need the channel's login WITH the youtube.force-ssl permission; with the upload-only login
    YouTube refuses (403) and both are switched off for a day (no repeated refused calls). YouTube's API cannot PIN a comment.
    Never raises: the upload itself is already done."""
    now = now or datetime.now(timezone.utc)
    st = _state(page)
    off = st.get("extras_off_until")
    if off and now < datetime.fromisoformat(off):
        return
    head = {"Authorization": "Bearer " + tok, "Content-Type": "application/json"}

    def refused(r, what):
        if r.status_code == 403 and ("insufficient" in r.text.lower() or "permission" in r.text.lower() or "scope" in r.text.lower()):
            st["extras_off_until"] = (now + timedelta(days=1)).isoformat(timespec="seconds")
            _save(page, st)
            log(f"{page}: {what} not added - the channel login needs the extra YouTube permission (youtube.force-ssl); tried again tomorrow")
            return True
        log(f"{page}: {what} not added ({r.status_code}): {r.text[:200]}")
        return r.status_code == 403
    try:
        if comment:
            r = requests.post(f"{API}/commentThreads", params={"part": "snippet"}, headers=head, timeout=60, data=json.dumps(
                {"snippet": {"videoId": vid, "topLevelComment": {"snippet": {"textOriginal": comment.strip()[:9000]}}}}, ensure_ascii=False).encode("utf-8"))
            if r.status_code < 300:
                log(f"{page}: first comment added (pin it in YouTube Studio if you want it on top)")
            elif refused(r, "first comment"):
                return
        import youtube
        name = youtube.PAGE_EN.get(page, page.title())
        topic = _playlist_name(cap)
        lists = st.setdefault("playlists", {})
        pid = lists.get(topic)
        if not pid:
            r = requests.post(f"{API}/playlists", params={"part": "snippet,status"}, headers=head, timeout=60, data=json.dumps(
                {"snippet": {"title": f"{name} {topic} | {name} 360", "description": f"Daily {name} {topic} - {name} 360",
                             "defaultLanguage": "ta"}, "status": {"privacyStatus": "public"}}, ensure_ascii=False).encode("utf-8"))
            if r.status_code >= 300:
                refused(r, "playlist")
                return
            pid = lists[topic] = r.json()["id"]
            _save(page, st)
            log(f"{page}: playlist made: {name} {topic}")
        r = requests.post(f"{API}/playlistItems", params={"part": "snippet"}, headers=head, timeout=60, data=json.dumps(
            {"snippet": {"playlistId": pid, "resourceId": {"kind": "youtube#video", "videoId": vid}}}).encode("utf-8"))
        if r.status_code < 300:
            log(f"{page}: added to the playlist '{name} {topic}'")
        else:
            if r.status_code == 404:      # the playlist was deleted on YouTube - made again next time
                lists.pop(topic, None)
                _save(page, st)
            refused(r, "playlist item")
    except Exception as e:
        log(f"{page}: comment / playlist skipped:", str(e)[:200])


CHANNEL_NAMES = {"namakkal": ["namakkal", "நாமக்கல்"], "rasipuram": ["rasipuram", "ராசிபுரம்", "இராசிபுரம்"],
                 "coimbatore": ["coimbatore", "kovai", "கோவை", "கோயம்புத்தூர்"], "erode": ["erode", "ஈரோடு"], "karur": ["karur", "கரூர்"],
                 "salem": ["salem", "சேலம்"], "tirupur": ["tirupur", "tiruppur", "திருப்பூர்"], "trichy": ["trichy", "tiruchi", "திருச்சி"]}


def channel_ok(page, tok, s, now=None):
    """owner 25 Nov (other pages' Shorts appeared on the Namakkal channel - their logins were made on the wrong channel): with
    "verify_channel" on, a page uploads ONLY when YouTube confirms the login's channel name is this page's (e.g. 'Karur 360').
    Needs the login with the youtube.force-ssl permission; until then the page does not upload. Checked once a day. ('' = ok)"""
    if not s.get("verify_channel"):
        return ""
    now = now or datetime.now(timezone.utc)
    day = now.astimezone(IST).strftime("%Y-%m-%d")
    st = _state(page)
    v = st.get("channel_check") or {}
    if v.get("day") == day and v.get("ok"):
        return ""
    if v.get("day") == day and v.get("checked_at") and (now - datetime.fromisoformat(v["checked_at"])).total_seconds() < 3600:
        return v.get("why") or "channel not confirmed"
    why, title = "", ""
    try:
        r = requests.get("https://www.googleapis.com/youtube/v3/channels", params={"part": "snippet", "mine": "true"},
                         headers={"Authorization": "Bearer " + tok}, timeout=60)
        if r.status_code == 200 and (r.json().get("items") or []):
            title = r.json()["items"][0]["snippet"].get("title", "")
            low = title.lower()
            mine = CHANNEL_NAMES.get(page, [page])
            others = [w for pg, ws in CHANNEL_NAMES.items() if pg != page for w in ws if not any(w in m or m in w for m in mine)]
            if not any(w in low for w in mine) or any(w in low for w in others):
                why = f"the login is for the channel '{title}', not this page's channel - NOT uploaded (make the login again on the right channel)"
        elif r.status_code == 403:
            why = "the channel cannot be confirmed - the login needs the extra permission (youtube.force-ssl); not uploaded until then"
        else:
            why = f"the channel could not be read ({r.status_code}) - not uploaded this hour"
    except Exception as e:
        why = f"the channel could not be read ({str(e)[:80]}) - not uploaded this hour"
    st["channel_check"] = {"day": day, "ok": not why, "why": why, "title": title, "checked_at": now.isoformat(timespec="seconds")}
    _save(page, st)
    if not why:
        log(f"{page}: channel confirmed: {title}")
    return why


def access_token(page):
    cid, sec, ref = keys(page)
    r = requests.post(TOKEN_URL, data={"client_id": cid, "client_secret": sec, "refresh_token": ref, "grant_type": "refresh_token"}, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"YouTube login refused ({r.status_code}): {r.text[:200]}")
    return r.json()["access_token"]


def upload(token, path, title, description, tags, privacy):
    """resumable upload (YouTube Data API v3 videos.insert); returns the video id"""
    meta = {"snippet": {"title": title[:100], "description": description[:4900], "tags": [t.strip() for t in tags.split(",") if t.strip()][:15],
                        "categoryId": "25", "defaultLanguage": "ta", "defaultAudioLanguage": "ta"},      # 25 = News & Politics; owner 25 Nov: Tamil
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
            daily_only = False
            if "the day's limit" in why:      # owner 25 Nov: the news limit is reached - the rasipalan / gold rate may still go
                why, daily_only = due(page, s, now, daily=True), True
            if why:
                log(f"{page}: waits ({why})")
                continue
            if s.get("verify_channel"):      # owner 25 Nov: never upload to another page's channel
                bad = channel_ok(page, access_token(page), s, now)
                if bad:
                    log(f"{page}: {bad}")
                    continue
            st = _state(page)
            done = {u.get("ig") for u in st.get("uploads", [])}
            token = post.bridge_get("token", page=page)["token"]
            uname = post.ig_account(token)[1]
            day = now.astimezone(IST).strftime("%Y-%m-%d")
            feed = post.ig("GET", "me/media", token, fields="id,caption,media_type,permalink,timestamp,media_url", limit=40).get("data") or []
            todays = [m for m in feed if m.get("media_type") == "VIDEO" and m.get("id") not in done and m.get("timestamp")
                      and youtube.when(m["timestamp"]).strftime("%Y-%m-%d") == day]
            daily = [m for m in todays if youtube.SKIP.search(m.get("caption") or "")]      # owner 25 Nov: rasipalan / gold rate on YouTube too, first
            news = [m for m in todays if not youtube.SKIP.search(m.get("caption") or "")]
            best = daily[:1] or ([] if daily_only else youtube.pick(news, 1))
            if not best:
                log(f"{page}: no new news reel to upload")
                continue
            m = best[0]
            path = localmedia.download(m.get("media_url") or "", "youtube.mp4") if m.get("media_url") else None
            if not path:
                log(f"{page}: the reel's video could not be read - tried again in a later run")
                continue
            d = youtube.details(m, page, uname)
            src = post.comment_for(m.get("id")) if hasattr(post, "comment_for") else ""
            if src:      # owner 25 Nov: the Instagram first comment (source + link) at the top, after the 3 hashtags line
                tagline, _, rest = d["description"].partition("\n")
                d["description"] = (tagline + "\n\n" + src.strip() + "\n" + rest)[:4900]
            tok = access_token(page)
            vid = upload(tok, path, d["title"], d["description"], d["tags"], s["privacy"])
            st.setdefault("uploads", []).append({"ig": m["id"], "youtube": vid, "day": day, "at": now.isoformat(timespec="seconds"),
                                                 "title": d["title"], **({"daily": True} if m in daily else {})})
            st.pop("failed_at", None)
            _save(page, st)
            log(f"{page}: uploaded to YouTube ({s['privacy']}) https://youtube.com/shorts/{vid} - {d['title'][:60]}")
            extras(page, tok, vid, src, m.get("caption") or "")      # owner 25 Nov: first comment + topic playlist (needs the extra permission)
        except Exception as e:
            log(f"{page}: not uploaded (tried again in {RETRY_WAIT_MIN} minutes):", str(e)[:250])
            try:      # owner 25 Nov: after an error wait 10 minutes before the next try
                st = _state(page)
                st["failed_at"] = now.isoformat(timespec="seconds")
                _save(page, st)
            except Exception:
                pass
            if "quotaExceeded" in str(e) or "uploadLimitExceeded" in str(e):      # the day's YouTube limit: no more tries today
                st = _state(page)
                st.setdefault("uploads", []).extend({"ig": "", "youtube": "", "day": now.astimezone(IST).strftime("%Y-%m-%d"),
                                                     "at": now.isoformat(timespec="seconds"), "title": "limit"} for _ in range(int(s["per_day"])))      # owner 24 Nov: the whole day's allowance (was 6 - with 20 a day it kept trying after the quota)
                _save(page, st)
