"""owner 25 Nov: ONE e-mail per news with its Instagram, Facebook and YouTube links (config posted_email "combined").

The Instagram post no longer sends its own e-mail (the bridge gets quiet=True). Every check run (post.py check, after the Facebook
catch-up and the YouTube upload) looks at this page's news posted today (poster/posted/*.json with "combined": true) and sends one
e-mail per news through the Promo Hub ("digest" action, the same Gmail account as before) when
  - Facebook is posted and YouTube is uploaded (or YouTube is not connected / its daily limit is reached), or
  - WAIT_MIN minutes have passed since the Instagram post (the e-mail then says what is still waiting).
At most 60 e-mails a day for all 7 pages together (owner 25 Nov, option B) - after that the news is only in the daily summary.
Sent ones are kept in poster/fb_posted/_combined_email.json (committed by post.yml). Never raises: a problem here never touches posting."""
import base64
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
IST = timezone(timedelta(hours=5, minutes=30))
STATE_FILE = HERE / "fb_posted" / "_combined_email.json"
WAIT_MIN = 45          # the longest an e-mail waits for Facebook / YouTube
PER_RUN = 6            # e-mails per check run at most
DAY_MAX = 60           # all 7 pages together (one Gmail account)
KEEP_DAYS = 3


def _day(t):
    return t.astimezone(IST).strftime("%Y-%m-%d")


def state():
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"sent": {}}


def save(st):
    cut = _day(datetime.now(timezone.utc) - timedelta(days=KEEP_DAYS))
    st["sent"] = {k: v for k, v in st.get("sent", {}).items() if str(v.get("day", "")) >= cut}
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")


def sent_today_all(post, day, st):
    """combined e-mails sent today by all 7 pages (this repo: local state; the others: their state file on GitHub)"""
    n = sum(1 for v in st.get("sent", {}).values() if v.get("day") == day and v.get("how") == "sent")
    me = (os.environ.get("GITHUB_REPOSITORY") or "").split("/")[-1]
    head = {"Accept": "application/vnd.github+json"}
    if os.environ.get("GH_MEDIA_TOKEN"):
        head["Authorization"] = "Bearer " + os.environ["GH_MEDIA_TOKEN"]
    for repo in post.PAGE_REPOS:
        if repo == me:
            continue
        try:
            r = requests.get(f"https://api.github.com/repos/news360-tn/{repo}/contents/poster/fb_posted/_combined_email.json",
                             headers=head, timeout=20)
            if r.status_code != 200:
                continue
            other = json.loads(base64.b64decode(r.json().get("content", "")).decode("utf-8"))
            n += sum(1 for v in other.get("sent", {}).values() if v.get("day") == day and v.get("how") == "sent")
        except Exception:
            continue
    return n


def facebook(sid):
    """[(facebook page, status, link)] for this news"""
    out = []
    for f in sorted((HERE / "fb_posted").glob(f"*-{sid}-reel.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        out.append((d.get("page") or f.name.split("-")[0], str(d.get("status") or ""), d.get("link") or ""))
    return out


def youtube(post, page, media_id, now):
    """(done, text) for this news on the page's YouTube channel"""
    import ytupload
    if not ytupload.keys(page):
        return True, "not connected"
    ups = ytupload._state(page).get("uploads", [])
    for u in ups:
        if media_id and u.get("ig") == media_id and u.get("youtube"):
            return True, f"https://youtube.com/shorts/{u['youtube']}"
    why = ytupload.due(page, ytupload.settings(post.CONFIG), now)
    if "limit" in why:
        return True, "not uploaded (YouTube's daily limit is reached)"
    return False, "not uploaded yet (it goes up in the next few minutes)"


def body(post, rec, fbs, yt_text):
    label = post.LABEL.get(rec["page"], rec["page"])
    fb_lines = []
    for pg, stt, link in fbs:
        name = post.LABEL.get(pg, pg)
        fb_lines.append(f"Facebook ({name}): {link}" if stt == "posted" and link else f"Facebook ({name}): not posted yet ({stt or 'waiting'})")
    if not fbs:
        fb_lines.append("Facebook: not posted yet (waiting)")
    at = datetime.fromisoformat(rec["at"]).astimezone(IST).strftime("%d %b %I:%M %p")
    lines = [f"{label} - {rec.get('headline', '')}", f"Posted at {at} IST", "",
             f"Instagram: {rec.get('link') or '(link not read)'}", *fb_lines, f"YouTube: {yt_text}", ""]
    if rec.get("caption"):
        lines += ["CAPTION:", rec["caption"]]
    return f"[NEWS360 POSTED] {label} - {rec.get('headline', '')[:120]}", "\n".join(lines)


def run(post, now=None):
    """send the e-mails that are due; returns how many were sent"""
    import promo
    if post.CONFIG.get("posted_email") != "combined" or post.DRY or not promo.enabled():
        return 0
    now = now or datetime.now(timezone.utc)
    day = _day(now)
    st = state()
    sent = st.setdefault("sent", {})
    total_today = None
    done = 0
    for f in sorted(post.POSTED_DIR.glob("*.json")) if post.POSTED_DIR.exists() else []:
        if done >= PER_RUN:
            break
        try:
            rec = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not rec.get("combined") or rec.get("page") not in post.LABEL:
            continue      # posted before the switch (it had its own e-mail) or another page's file
        try:
            t = datetime.fromisoformat(rec["at"])
        except Exception:
            continue
        if _day(t) != day:
            continue
        key = f"{rec['page']}:{rec.get('story')}"
        if sent.get(key, {}).get("how") in ("sent", "summary", "failed"):
            continue
        fbs = facebook(rec.get("story"))
        fb_done = bool(fbs) and all(s == "posted" for _, s, _ in fbs)
        yt_done, yt_text = youtube(post, rec["page"], rec.get("media_id"), now)
        if not ((fb_done and yt_done) or now - t >= timedelta(minutes=WAIT_MIN)):
            continue
        if total_today is None:
            total_today = sent_today_all(post, day, st)
        cap = int(post.CONFIG.get("posted_email_max") or DAY_MAX)
        if total_today >= cap:
            sent[key] = {"day": day, "how": "summary", "at": now.isoformat(timespec="seconds")}
            post.log(f"posted e-mail {key}: not sent - {cap} e-mails today on all pages (it is in the daily summary)")
            continue
        subject, text = body(post, rec, fbs, yt_text)
        try:
            promo.hub_post("digest", {"subject": subject, "text": text})
            sent[key] = {"day": day, "how": "sent", "at": now.isoformat(timespec="seconds"), "fb": fb_done, "yt": yt_text.startswith("http")}
            total_today += 1
            done += 1
            post.log(f"posted e-mail {key}: sent (Instagram + Facebook {'yes' if fb_done else 'waiting'} + YouTube "
                     f"{'yes' if yt_text.startswith('http') else 'no'})")
        except Exception as e:
            v = sent.setdefault(key, {"day": day})
            v["tries"] = int(v.get("tries", 0)) + 1
            if v["tries"] >= 3:
                v["how"] = "failed"
            post.log(f"posted e-mail {key}: not sent (try {v['tries']}/3):", str(e)[:150])
    try:
        save(st)
    except Exception as e:
        post.log("combined e-mail list not saved:", str(e)[:120])
    return done
