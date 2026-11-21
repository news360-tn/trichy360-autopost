"""owner 21 Nov: news reels and stories go to Instagram as FILES - no Cloudinary ("do not use Cloudinary").

Meta allows a file upload to Instagram ("resumable upload") ONLY on the Instagram API with Facebook login: graph.facebook.com
with the page's Facebook token and the Instagram account linked to that Facebook page. The Instagram login the pages use today
(graph.instagram.com) refuses it - "The parameter video_url is required" (trial 12-21 Nov). So:
  * a page whose Facebook secrets FB_PAGE_ID_<PAGE> / FB_TOKEN_<PAGE> are set, whose Facebook page is linked to its Instagram
    account and whose token has instagram_basic + instagram_content_publish sends its reels and stories as files: nothing goes
    to Cloudinary;
  * every other page posts exactly as before (Cloudinary link) - nothing stops while the tokens are being made;
  * if sending a file fails before it is published, that one reel goes by a Cloudinary link (never lost, never posted twice).
The check costs one call and is kept 6 hours in poster/prebuilt/_direct_<page>.json (a NEW token is checked at once).
ready(page, ig_uid=None) -> (instagram id, facebook token) or None
off(page, why)            -> after a refusal (e.g. no instagram_content_publish): this page uses the link for 6 hours
python poster/igdirect.py <page> ...  -> prints whether each page can send files (never prints a token)"""
import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import facebook
import localmedia

CACHE = Path(__file__).resolve().parent / "prebuilt"
HOURS = 6
RUPLOAD = "https://rupload.facebook.com/ig-api-upload/{}/{}"
_MEM = {}
_SAID = set()


def log(*a):
    print(datetime.now(timezone(timedelta(hours=5, minutes=30))).strftime("%H:%M:%S"), "  direct upload:", *a, flush=True)


def _say(key, *a):
    if key not in _SAID:
        _SAID.add(key)
        log(*a)


def _file(page):
    return CACHE / f"_direct_{page}.json"


def _th(tok):
    return hashlib.sha1(tok.encode()).hexdigest()[:10]


def _read(page, tok):
    try:
        d = json.loads(_file(page).read_text(encoding="utf-8"))
        if d.get("tok") == _th(tok) and datetime.fromisoformat(d["until"]) > datetime.now(timezone.utc):
            return d
    except Exception:
        pass
    return None


def _write(page, tok, ok, ig_id, why):
    d = {"ok": bool(ok), "ig": str(ig_id or ""), "why": str(why or "")[:300], "tok": _th(tok),
         "until": (datetime.now(timezone.utc) + timedelta(hours=HOURS)).isoformat(timespec="seconds")}
    try:
        CACHE.mkdir(parents=True, exist_ok=True)
        _file(page).write_text(json.dumps(d, indent=1), encoding="utf-8")
    except Exception as e:
        log("check not saved:", str(e)[:120])
    return d


def is_permission_error(e):
    t = str(e).lower()
    return any(x in t for x in ("'code': 10,", "'code': 200,", "'code': 190,", " 10/", " 200/", " 190/", "permission",
                                "not authorized", "missing permissions", "unsupported post request", "unsupported get request"))


def ready(page, ig_uid=None):
    """(instagram account id, facebook token) when this page's reels and stories can go to Instagram as files; else None"""
    if not localmedia.enabled():
        return None
    c = facebook.creds(page)
    if not c:
        _say(("nocreds", page), f"{page}: no Facebook token for this page yet (FB_PAGE_ID_{page.upper()} / FB_TOKEN_{page.upper()})"
                                " - Instagram gets the Cloudinary link as before")
        return None
    pid, tok = c
    key = (page, _th(tok))
    d = _MEM.get(key) or _read(page, tok)
    if d is None:
        try:
            r = facebook._call("GET", pid, tok, fields="instagram_business_account")
            ig = str(((r or {}).get("instagram_business_account") or {}).get("id") or "")
            d = _write(page, tok, bool(ig), ig, "" if ig else "the Facebook page is not linked to an Instagram account, or the token has "
                                                              "no instagram_basic permission")
        except Exception as e:
            d = _write(page, tok, False, "", str(e))
    _MEM[key] = d
    if not d.get("ok"):
        _say(("off", page), f"{page}: Instagram files not possible yet ({d.get('why')}) - the Cloudinary link is used")
        return None
    if ig_uid and str(d.get("ig")) != str(ig_uid):
        _say(("other", page), f"{page}: the Facebook page is linked to another Instagram account ({d.get('ig')}, not {ig_uid})"
                              " - the Cloudinary link is used")
        return None
    _say(("ok", page), f"{page}: reels and stories go to Instagram as files (no Cloudinary)")
    return d["ig"], tok


def cached_ok(page):
    """True when the saved check says this page sends files (no call - used by the posting check)"""
    c = facebook.creds(page) if localmedia.enabled() else None
    d = _read(page, c[1]) if c else None
    return bool(d and d.get("ok"))


def off(page, why):
    c = facebook.creds(page)
    if c:
        _MEM[(page, _th(c[1]))] = _write(page, c[1], False, "", "Instagram refused the file: " + str(why)[:250])
        log(f"{page}: Instagram refused the file ({str(why)[:150]}) - the Cloudinary link is used for {HOURS} hours")


def upload_url(container_id):
    return RUPLOAD.format(facebook.VER, container_id)


if __name__ == "__main__":      # facebook_check.yml
    for pg in sys.argv[1:]:
        _file(pg).unlink(missing_ok=True)      # a fresh check
        r = ready(pg)
        why = next((v.get("why") for k, v in _MEM.items() if k[0] == pg), "") or "no Facebook token for this page yet"
        print(f"Instagram files {pg}: " + ("READY - reels and stories go to Instagram as files, no Cloudinary (the first post confirms "
                                           "the instagram_content_publish permission)" if r else f"NOT READY - {why}; the Cloudinary link is used"))
