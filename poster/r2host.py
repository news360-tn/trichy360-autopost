"""owner 25 Nov ("Cloudinary alternate - Cloudflare R2"): pictures and reels get their public link from ONE shared Cloudflare R2 bucket
(news360-media) instead of Cloudinary. Free tier: 10 GB stored, no download fees; the bucket's own rule deletes files after 3 days, so
it never fills up. Every page keeps its files under <page>/<YYYYMMDD>/.

Order used by githost.fallback / post.upload:  R2 -> Cloudinary -> the page's GitHub repository (and reels still go as a direct file
first). Without the three secrets R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY nothing changes.
R2_BUCKET / R2_PUBLIC_URL are not secret (set in the workflows). The upload is signed here (AWS Signature V4, the S3 API that R2 speaks),
so no extra library is needed. Never prints a key."""
import hashlib
import hmac
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import requests

TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".gif": "image/gif",
         ".mp4": "video/mp4", ".mov": "video/quicktime", ".mp3": "audio/mpeg", ".m4a": "audio/mp4"}


def account_id(v):
    """owner 25 Nov: the Account ID is 32 letters/digits; a pasted endpoint link (https://<id>.r2.cloudflarestorage.com) or extra
    spaces still work. Anything else raises a clear message (never shows the value)."""
    v = (v or "").strip()
    if re.fullmatch(r"[0-9a-fA-F]{32}", v):
        return v.lower()
    m = re.search(r"(?<![0-9a-fA-F])([0-9a-fA-F]{32})(?![0-9a-fA-F])", v)
    if m:
        return m.group(1).lower()
    raise RuntimeError(f"R2_ACCOUNT_ID is not the 32-character Cloudflare Account ID (the saved value has {len(v)} characters) - "
                       "update that secret with the Account ID from the R2 overview page")


def _cfg():
    return {k: (os.environ.get(k) or "").strip() for k in
            ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET", "R2_PUBLIC_URL")}


def enabled():
    return all(_cfg().values())


def _sign(key, msg):
    return hmac.new(key, msg.encode(), hashlib.sha256).digest()


# owner 25 Nov ("R2 carefully - my card is on Cloudflare"): hard limits so the free tier (10 GB stored, 1 million writes and
# 10 million reads a month, downloads free) is never passed. With the bucket's 3-day delete rule, 7 pages x 300 MB x 3 days = 6.3 GB
# at most. When a limit is reached, R2 is skipped for that page for the rest of the day (Cloudinary / GitHub / direct upload instead).
DAILY_MB = 300        # most this page may store in R2 per day (env R2_DAILY_MB can only LOWER it)
DAILY_FILES = 400     # most uploads per page per day (each upload = 2 writes: list + put)
MAX_FILE_MB = 100     # one file bigger than this never goes to R2


def _page(page=None):
    return (page or os.environ.get("PAGE") or (os.environ.get("GITHUB_REPOSITORY", "news360/x").split("/")[-1].replace("-autopost", ""))
            or "news360").strip().lower()


def _limits():
    mb = DAILY_MB
    try:
        mb = min(DAILY_MB, max(0, int(os.environ.get("R2_DAILY_MB") or DAILY_MB)))
    except ValueError:
        pass
    return mb * 1024 * 1024, DAILY_FILES


def _request(method, key="", query=None, data=b"", ctype=None):
    """one signed (AWS Signature V4) request to the bucket; returns the response (never raises for an HTTP status)"""
    c = _cfg()
    if not all(c.values()):
        raise RuntimeError("Cloudflare R2 not set up (R2_* secrets)")
    host = f"{account_id(c['R2_ACCOUNT_ID'])}.r2.cloudflarestorage.com"
    path = "/" + quote(f"{c['R2_BUCKET']}/{key}" if key else c["R2_BUCKET"])
    q = "&".join(f"{quote(k, safe='-_.~')}={quote(str(v), safe='-_.~')}" for k, v in sorted((query or {}).items()))
    now = datetime.now(timezone.utc)
    amz, day = now.strftime("%Y%m%dT%H%M%SZ"), now.strftime("%Y%m%d")
    body_hash = hashlib.sha256(data).hexdigest()
    head = {"host": host, "x-amz-content-sha256": body_hash, "x-amz-date": amz}
    if ctype:
        head["content-type"] = ctype
    signed = ";".join(sorted(head))
    canon = "\n".join([method, path, q, "".join(f"{k}:{head[k]}\n" for k in sorted(head)), signed, body_hash])
    scope = f"{day}/auto/s3/aws4_request"
    to_sign = "\n".join(["AWS4-HMAC-SHA256", amz, scope, hashlib.sha256(canon.encode()).hexdigest()])
    k = _sign(("AWS4" + c["R2_SECRET_ACCESS_KEY"]).encode(), day)
    for part in ("auto", "s3", "aws4_request"):
        k = _sign(k, part)
    sig = hmac.new(k, to_sign.encode(), hashlib.sha256).hexdigest()
    h = {kk: vv for kk, vv in head.items() if kk != "host"}
    h["Authorization"] = f"AWS4-HMAC-SHA256 Credential={c['R2_ACCESS_KEY_ID']}/{scope}, SignedHeaders={signed}, Signature={sig}"
    url = f"https://{host}{path}" + (f"?{q}" if q else "")
    return requests.request(method, url, data=data or None, headers=h, timeout=600)


def used_today(page=None):
    """(bytes, files) this page stored in R2 today - read from the bucket itself (all runs / retries count). Raises if unreadable."""
    prefix = f"{_page(page)}/{datetime.now(timezone.utc):%Y%m%d}/"
    total = files = 0
    token = None
    for _ in range(20):
        q = {"list-type": "2", "prefix": prefix, "max-keys": "1000"}
        if token:
            q["continuation-token"] = token
        r = _request("GET", query=q)
        if r.status_code >= 300:
            raise RuntimeError(f"R2 usage not readable (HTTP {r.status_code})")
        sizes = [int(x) for x in re.findall(r"<Size>(\d+)</Size>", r.text)]
        total += sum(sizes)
        files += len(sizes)
        m = re.search(r"<NextContinuationToken>([^<]+)</NextContinuationToken>", r.text)
        if "<IsTruncated>true</IsTruncated>" not in r.text or not m:
            break
        token = m.group(1)
    return total, files


def put(data, name="file.jpg", kind="image", page=None):
    """bytes -> public https link on the bucket's r2.dev address. Raises on failure or when a free-tier safety limit is reached."""
    c = _cfg()
    if not all(c.values()):
        raise RuntimeError("Cloudflare R2 not set up (R2_* secrets)")
    page = _page(page)
    if len(data) > MAX_FILE_MB * 1024 * 1024:
        raise RuntimeError(f"file too big for R2 ({len(data) // 1048576} MB > {MAX_FILE_MB} MB) - not uploaded")
    cap_bytes, cap_files = _limits()
    used, files = used_today(page)      # unreadable -> raises -> R2 is skipped (never upload blind)
    if used + len(data) > cap_bytes or files >= cap_files:
        raise RuntimeError(f"R2 daily safety limit reached for {page} ({used // 1048576} MB, {files} files today) - "
                           "R2 is skipped until tomorrow (free tier protected)")
    ext = Path(name).suffix.lower() or (".mp4" if kind == "video" else ".jpg")
    key = f"{page}/{datetime.now(timezone.utc):%Y%m%d}/{hashlib.sha1(data).hexdigest()[:16]}{ext}"
    last = None
    for attempt in range(3):
        try:
            r = _request("PUT", key, data=data, ctype=TYPES.get(ext, "application/octet-stream"))
            if r.status_code < 300:
                return c["R2_PUBLIC_URL"].rstrip("/") + "/" + quote(key)
            last = RuntimeError(f"R2 upload refused (HTTP {r.status_code}): {r.text[:200]}")
            if r.status_code in (400, 401, 403, 404):
                break      # a wrong key / bucket never gets better by trying again
        except requests.RequestException as e:
            last = RuntimeError(f"R2 upload failed: {str(e)[:200]}")
    raise last


def put_file(path, kind="image", page=None):
    p = Path(path)
    return put(p.read_bytes(), p.name, kind, page)
