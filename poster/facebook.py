"""Facebook Pages (owner 2 Nov): everything posted on Instagram also goes to the page's own Facebook page, with a Facebook story.

  news reel / owner ready reel  -> Facebook Reel  + Facebook video story
  news carousel / rasipalan     -> multi-photo post + Facebook photo story (first slide)

Secrets per page: FB_PAGE_ID_<PAGE> and FB_TOKEN_<PAGE> (never-expiring Page token), e.g. FB_PAGE_ID_RASIPURAM.
A page without both secrets is skipped quietly. A Facebook problem NEVER stops, undoes or repeats the Instagram post.

Every post gets one small record poster/fb_posted/<page>-<story>-<kind>.json (committed by the workflows):
  posted  -> never posted to Facebook again (link kept)
  failed  -> the post.yml check step tries it again, at most 2 more times, within 24 hours
  skipped -> the Facebook daily reel limit was reached (not tried again)
"""
import datetime as dt
import json
import os
import re
import sys
import time
from pathlib import Path

import requests

import localmedia      # owner 12 Nov: direct reel upload (OFF unless DIRECT_UPLOAD=1)

HERE = Path(__file__).resolve().parent
STATE = HERE / "fb_posted"
VER = os.environ.get("FB_GRAPH_VER", "v26.0")      # the version the owner's Graph API Explorer uses
GRAPH = "https://graph.facebook.com"
MAX_TRIES = 3            # first try + 2 retries
RETRY_HOURS = 24
REEL_CAP = int(os.environ.get("FB_DAILY_CAP", "30") or 30)      # Facebook allows about 30 API reels a day per page
WAIT_READY_S = int(os.environ.get("FB_WAIT_S", "300") or 300)
FB_TAGS = 3              # Facebook: town + topic + page tag (many hashtags do not help there)
# owner 11 Nov: from 7 Nov Facebook refused most reels (error 368 "we limit how often you can post") - new pages, 13-17 API reels a day.
# Facebook now gets only the TOP news (urgent, or a topic the page's insights rank best), few a day, spaced; a 368 pauses the page 24 h.
TOP_PER_DAY = int(os.environ.get("FB_TOP_PER_DAY", "5") or 5)
GAP_MIN = int(os.environ.get("FB_GAP_MIN", "120") or 120)
MIN_WEIGHT = float(os.environ.get("FB_MIN_WEIGHT", "0.4") or 0.4)
PAUSE_HOURS = 24


def log(*a):
    print("[facebook]", *a, flush=True)


def creds(page):
    k = re.sub(r"[^A-Z0-9]", "_", page.upper())
    pid, tok = os.environ.get("FB_PAGE_ID_" + k, "").strip(), os.environ.get("FB_TOKEN_" + k, "").strip()
    return (pid, tok) if pid and tok else None


def _now():
    return dt.datetime.now(dt.timezone.utc)


def _file(page, sid, kind):
    return STATE / f"{page}-{re.sub(r'[^A-Za-z0-9_.-]', '_', str(sid))}-{kind}.json"


def state(page, sid, kind):
    try:
        return json.loads(_file(page, sid, kind).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(page, sid, kind, data):
    STATE.mkdir(parents=True, exist_ok=True)
    data = dict(data, page=page, story=sid, kind=kind, updated=_now().isoformat(timespec="seconds"))
    _file(page, sid, kind).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def posted_last_day(page, kind="reel"):
    cut = _now() - dt.timedelta(hours=24)
    n = 0
    for f in STATE.glob(f"{page}-*-{kind}.json") if STATE.exists() else []:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            if d.get("status") == "posted" and dt.datetime.fromisoformat(d.get("posted_at", "")) > cut:
                n += 1
        except Exception:
            pass
    return n


def _blocked(e):
    return " 368/" in str(e) or "limit how often" in str(e).lower()


def _pause_file(page):
    return STATE / f"_paused-{page}.json"


def paused(page):
    """'' or why this page's Facebook posting is paused (Facebook limited it - posting again too soon makes it longer)"""
    try:
        d = json.loads(_pause_file(page).read_text(encoding="utf-8"))
        if dt.datetime.fromisoformat(d["until"]) > _now():
            return f"Facebook limited this page - paused until {d['until'][:16]} UTC"
    except Exception:
        pass
    return ""


def _pause(page, why):
    STATE.mkdir(parents=True, exist_ok=True)
    until = (_now() + dt.timedelta(hours=PAUSE_HOURS)).isoformat(timespec="seconds")
    _pause_file(page).write_text(json.dumps({"until": until, "why": str(why)[:300]}, indent=1), encoding="utf-8")
    log(f"Facebook limited {page} - Facebook posting paused for {PAUSE_HOURS} h (until {until[:16]} UTC); Instagram goes on")


def _last_posted(page):
    last = None
    for f in STATE.glob(f"{page}-*.json") if STATE.exists() else []:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            t = dt.datetime.fromisoformat(d["posted_at"]) if d.get("status") == "posted" else None
            if t and (last is None or t > last):
                last = t
        except Exception:
            pass
    return last


def top_news(rank):
    """rank = {"urgent": bool, "weight": insights topic weight, "best": topic is among the page's best topics, "topic": name}"""
    if not rank:
        return True, "no rank given"
    if rank.get("urgent"):
        return True, "urgent"
    if rank.get("best"):
        return True, f"top topic for this page ({rank.get('topic')})"
    if float(rank.get("weight") or 0) >= MIN_WEIGHT:
        return True, f"strong topic ({rank.get('topic')} {rank.get('weight')})"
    return False, f"not a top news on this page's insights ({rank.get('topic')} {rank.get('weight')})"


def gate(page, rank, always=False):
    """'' when this post may go to Facebook now, else why not (owner 11 Nov: top news only, few a day, spaced)"""
    why = paused(page)
    if why:
        return why
    if always:      # the daily rasipalan
        return ""
    ok, why = top_news(rank)
    if not ok:
        return why
    if posted_last_day(page, "reel") + posted_last_day(page, "photos") >= TOP_PER_DAY and not (rank or {}).get("urgent"):
        return f"Facebook top-news limit {TOP_PER_DAY} a day reached"
    last = _last_posted(page)
    if last and (_now() - last).total_seconds() < GAP_MIN * 60 and not (rank or {}).get("urgent"):
        return f"less than {GAP_MIN} min since the last Facebook post"
    return ""


def fb_caption(cap, page_tag, tags=None):
    """the Instagram caption (location line first, full news) with only 3 hashtags at the end.
    Instagram's tag line is: area, town, topic, Tamil place, page -> Facebook keeps town + topic + page tag."""
    found, body = [], []
    for l in (cap or "").split("\n"):
        t = re.findall(r"#[^\s#]+", l)
        rest = re.sub(r"#[^\s#]+", "", l).rstrip()
        found += t
        if not t or rest.strip():
            body.append(rest)
    if tags is None:
        seen, others = {page_tag.lower()}, []
        for t in found:
            t = t.rstrip(".,!")
            if t.lower() not in seen:
                seen.add(t.lower())
                others.append(t)
        tags = others[1:FB_TAGS] if len(others) >= FB_TAGS else others[:FB_TAGS - 1]
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(body)).strip()
    return (text + "\n\n" + " ".join(list(tags)[:FB_TAGS - 1] + [page_tag])).strip()


def _err(r):
    try:
        e = r.json().get("error") or {}
        return f"{r.status_code} {e.get('code', '')}/{e.get('error_subcode', '')} {e.get('message', '')}"[:300]
    except Exception:
        return f"{r.status_code} {r.text[:200]}"


def _call(method, path, token, **data):
    url = f"{GRAPH}/{VER}/{path}"
    data = dict(data, access_token=token)
    for i in range(3):
        try:
            r = requests.request(method, url, data=data if method == "POST" else None,
                                 params=data if method == "GET" else None, timeout=90)
        except requests.RequestException as e:
            if i == 2:
                raise RuntimeError(f"Facebook not reachable: {str(e)[:150]}")
            time.sleep(5 * (i + 1))
            continue
        if r.status_code >= 500 and i < 2:
            time.sleep(5 * (i + 1))
            continue
        if r.status_code != 200:
            raise RuntimeError("Facebook " + path.split("/")[-1] + ": " + _err(r))
        return r.json()


def _hosted_upload(token, vid, video_url, upload_url=""):
    """Facebook fetches the already-hosted (Cloudinary) video itself - nothing is downloaded here"""
    up = upload_url or f"https://rupload.facebook.com/video-upload/{VER}/{vid}"
    path = localmedia.get(video_url)      # None unless DIRECT_UPLOAD=1
    if path:
        try:
            localmedia.send(up, token, path)
            log("video sent as a file (direct upload)")
            return
        except Exception as e:
            log("direct upload not used - Facebook fetches the link as before:", str(e)[:150])
    r = requests.post(up, headers={"Authorization": "OAuth " + token, "file_url": video_url}, timeout=180)
    if r.status_code != 200:
        raise RuntimeError("Facebook upload: " + _err(r))
    try:
        ok = (r.json() or {}).get("success", True)
    except Exception:
        ok = True
    if not ok:
        raise RuntimeError("Facebook upload refused: " + r.text[:200])


def _link(token, obj_id, fallback):
    try:
        p = (_call("GET", obj_id, token, fields="permalink_url") or {}).get("permalink_url") or ""
        if p:
            return p if p.startswith("http") else "https://www.facebook.com" + p
    except RuntimeError:
        pass
    return fallback


def publish_reel(page_id, token, video_url, caption):
    """Page video_reels flow: start -> hosted upload -> finish (published); returns (video_id, link)"""
    st = _call("POST", f"{page_id}/video_reels", token, upload_phase="start")
    vid = st.get("video_id")
    if not vid:
        raise RuntimeError(f"Facebook reel start: no video id ({str(st)[:150]})")
    _hosted_upload(token, vid, video_url, st.get("upload_url", ""))
    _call("POST", f"{page_id}/video_reels", token, upload_phase="finish", video_id=vid,
          video_state="PUBLISHED", description=caption[:2200])
    end = time.time() + WAIT_READY_S
    last = {}
    while time.time() < end:
        time.sleep(10)
        try:
            last = (_call("GET", vid, token, fields="status") or {}).get("status") or {}
        except RuntimeError as e:
            log("status not read yet:", str(e)[:120])
            continue
        if last.get("video_status") == "error" or any((last.get(p) or {}).get("status") == "error"
                                                      for p in ("uploading_phase", "processing_phase", "publishing_phase")):
            raise RuntimeError("Facebook processing failed: " + json.dumps(last)[:300])
        if (last.get("publishing_phase") or {}).get("status") == "complete" or last.get("video_status") == "published":
            break
    else:
        log("still processing after", WAIT_READY_S, "s - Facebook publishes it by itself when ready:", json.dumps(last)[:200])
    return vid, _link(token, vid, f"https://www.facebook.com/reel/{vid}")


def _photo(page_id, token, url):
    return _call("POST", f"{page_id}/photos", token, url=url, published="false")["id"]


def publish_photos(page_id, token, image_urls, caption):
    """multi-photo page post (all carousel slides, in order); returns (post_id, link, first_photo_id)"""
    ids = [_photo(page_id, token, u) for u in image_urls[:10]]
    if not ids:
        raise RuntimeError("Facebook photos: no pictures")
    data = {f"attached_media[{i}]": json.dumps({"media_fbid": p}) for i, p in enumerate(ids)}
    pid = _call("POST", f"{page_id}/feed", token, message=caption[:5000], **data)["id"]
    return pid, _link(token, pid, f"https://www.facebook.com/{pid}"), ids[0]


def story_video(page_id, token, video_url):
    st = _call("POST", f"{page_id}/video_stories", token, upload_phase="start")
    vid = st.get("video_id")
    if not vid:
        raise RuntimeError(f"Facebook story start: no video id ({str(st)[:150]})")
    _hosted_upload(token, vid, video_url, st.get("upload_url", ""))
    r = _call("POST", f"{page_id}/video_stories", token, upload_phase="finish", video_id=vid)
    return r.get("post_id") or vid


def story_photo(page_id, token, image_url="", photo_id=""):
    """owner 4 Nov (3 Nov rasipalan: 400 Invalid parameter 2522009): the photo inside the feed post is already published and
    Facebook refuses it for a story - the story gets its own fresh unpublished upload of the first slide"""
    photo_id = photo_id or _photo(page_id, token, image_url)
    r = _call("POST", f"{page_id}/photo_stories", token, photo_id=photo_id)
    return r.get("post_id") or photo_id


def _attempt(page, sid, kind, media, caption, prev, story=True):
    pid, tok = creds(page)
    tries = int(prev.get("tries", 0)) + 1
    try:
        if kind == "reel":
            obj, link = publish_reel(pid, tok, media[0], caption)
            first = ""
        else:
            obj, link, first = publish_photos(pid, tok, media, caption)
    except Exception as e:
        if _blocked(e):      # Facebook limited the page: pause it, and this post is not tried again (a retry extends the limit)
            _pause(page, e)
            _save(page, sid, kind, {"status": "skipped", "why": "Facebook limited the page: " + str(e)[:300], "media": media})
            return ""
        _save(page, sid, kind, {"status": "failed", "tries": tries, "error": str(e)[:400], "media": media, "caption": caption,
                                "first_try": prev.get("first_try") or _now().isoformat(timespec="seconds")})
        log(f"NOT posted to Facebook ({page} {sid} {kind}, try {tries}/{MAX_TRIES}; Instagram is fine):", str(e)[:250])
        return ""
    rec = {"status": "posted", "tries": tries, "id": obj, "link": link, "media": media, "posted_at": _now().isoformat(timespec="seconds")}
    _save(page, sid, kind, rec)
    log(f"posted to Facebook ({page} {sid} {kind}):", link)
    if story:      # the Facebook story of the same post (a story problem never changes the post record to failed)
        try:
            rec["fb_story"] = story_video(pid, tok, media[0]) if kind == "reel" else story_photo(pid, tok, image_url=media[0])
            log(f"Facebook story made ({page} {sid}):", rec["fb_story"])
        except Exception as e:
            rec["story_error"] = str(e)[:300]
            log(f"Facebook story not made ({page} {sid}; the post itself is fine):", str(e)[:200])
        _save(page, sid, kind, rec)
    return link


def share(page, sid, kind, media, caption, page_tag, dry=False, tags=None, story=True, rank=None, always=False, source_link=""):
    """kind 'reel' (media = [video url]) or 'photos' (media = image urls). Called right after the Instagram post is published.
    Never raises. Returns the Facebook link or ''."""
    try:
        media = [m for m in (media or []) if m]
        if not creds(page):
            log(f"Facebook not set up for {page} (secrets FB_PAGE_ID_{page.upper()} / FB_TOKEN_{page.upper()}) - skipped")
            return ""
        if not media:
            return ""
        prev = state(page, sid, kind)
        if prev.get("status") == "posted":
            log(f"already on Facebook ({page} {sid} {kind}) - not posted again:", prev.get("link"))
            return prev.get("link", "")
        cap = fb_caption(caption, page_tag, tags)
        if source_link and source_link not in cap:      # owner 11 Nov: Facebook allows links - the article itself, so readers can check the news
            cap = cap.replace("\n\n#", f"\n🔗 {source_link}\n\n#", 1) if "\n\n#" in cap else cap + f"\n🔗 {source_link}"
        why = gate(page, rank, always)
        if why:
            if not dry:
                _save(page, sid, kind, {"status": "skipped", "why": why, "media": media})
            log(f"Facebook: {sid} not posted ({why}) - Instagram only")
            return ""
        if dry:
            log(f"DRY RUN - not posting to Facebook ({page} {sid} {kind}, {len(media)} file(s)); caption would be:\n{cap}")
            return ""
        if kind == "reel" and posted_last_day(page, "reel") >= REEL_CAP:
            _save(page, sid, kind, {"status": "skipped", "why": f"Facebook daily reel limit {REEL_CAP} reached", "media": media})
            log(f"Facebook daily reel limit {REEL_CAP} reached for {page} - {sid} stays Instagram only")
            return ""
        return _attempt(page, sid, kind, media, cap, prev, story)
    except Exception as e:      # never let Facebook break the Instagram run
        log("Facebook step skipped:", str(e)[:200])
        return ""


def retry_failed(limit=2):
    """post.yml check step: failed Facebook posts of the last 24 h are tried again (at most MAX_TRIES in total)"""
    cut = _now() - dt.timedelta(hours=RETRY_HOURS)
    done = 0
    for f in sorted(STATE.glob("*.json")) if STATE.exists() else []:
        if done >= limit:
            break
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            if d.get("status") != "failed" or int(d.get("tries", 0)) >= MAX_TRIES or _blocked(d.get("error", "")):
                continue
            if dt.datetime.fromisoformat(d.get("first_try") or d.get("updated")) < cut:
                continue
            page, sid, kind = d["page"], d["story"], d.get("kind", "reel")
            if not creds(page) or paused(page) or (kind == "reel" and posted_last_day(page, "reel") >= REEL_CAP):
                continue
            log(f"trying Facebook again: {page} {sid} {kind} (try {int(d.get('tries', 0)) + 1}/{MAX_TRIES})")
            _attempt(page, sid, kind, d["media"], d["caption"], d)
            done += 1
        except Exception as e:
            log("retry skipped for", f.name, str(e)[:150])
    return done


def status(pages):
    """which pages are set up (never prints a token) and which Facebook page each id points to"""
    for page in pages:
        c = creds(page)
        if not c:
            print(f"{page}: NOT set up (FB_PAGE_ID_{page.upper()} / FB_TOKEN_{page.upper()} missing)")
            continue
        try:
            d = _call("GET", c[0], c[1], fields="id,name")
            print(f"{page}: OK -> Facebook page '{d.get('name')}' ({d.get('id')})")
        except Exception as e:
            print(f"{page}: token/page problem - {str(e)[:200]}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "retry":
        retry_failed()
    elif cmd == "status":
        status(sys.argv[2:])
    else:
        print("usage: facebook.py retry | status <page> [<page>...]")
