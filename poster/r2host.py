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
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import requests

TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".gif": "image/gif",
         ".mp4": "video/mp4", ".mov": "video/quicktime", ".mp3": "audio/mpeg", ".m4a": "audio/mp4"}


def _cfg():
    return {k: (os.environ.get(k) or "").strip() for k in
            ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET", "R2_PUBLIC_URL")}


def enabled():
    return all(_cfg().values())


def _sign(key, msg):
    return hmac.new(key, msg.encode(), hashlib.sha256).digest()


def put(data, name="file.jpg", kind="image", page=None):
    """bytes -> public https link on the bucket's r2.dev address. Raises on failure."""
    c = _cfg()
    if not all(c.values()):
        raise RuntimeError("Cloudflare R2 not set up (R2_* secrets)")
    page = (page or os.environ.get("PAGE") or (os.environ.get("GITHUB_REPOSITORY", "news360/x").split("/")[-1].replace("-autopost", ""))
            or "news360").strip().lower()
    ext = Path(name).suffix.lower() or (".mp4" if kind == "video" else ".jpg")
    now = datetime.now(timezone.utc)
    key = f"{page}/{now:%Y%m%d}/{hashlib.sha1(data).hexdigest()[:16]}{ext}"
    host = f"{c['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com"
    path = "/" + quote(f"{c['R2_BUCKET']}/{key}")
    ctype = TYPES.get(ext, "application/octet-stream")
    amz = now.strftime("%Y%m%dT%H%M%SZ")
    day = now.strftime("%Y%m%d")
    body_hash = hashlib.sha256(data).hexdigest()
    head = {"content-type": ctype, "host": host, "x-amz-content-sha256": body_hash, "x-amz-date": amz}
    signed = ";".join(sorted(head))
    canon = "\n".join(["PUT", path, "", "".join(f"{k}:{head[k]}\n" for k in sorted(head)), signed, body_hash])
    scope = f"{day}/auto/s3/aws4_request"
    to_sign = "\n".join(["AWS4-HMAC-SHA256", amz, scope, hashlib.sha256(canon.encode()).hexdigest()])
    k = _sign(("AWS4" + c["R2_SECRET_ACCESS_KEY"]).encode(), day)
    for part in ("auto", "s3", "aws4_request"):
        k = _sign(k, part)
    sig = hmac.new(k, to_sign.encode(), hashlib.sha256).hexdigest()
    h = {kk: vv for kk, vv in head.items() if kk != "host"}
    h["Authorization"] = f"AWS4-HMAC-SHA256 Credential={c['R2_ACCESS_KEY_ID']}/{scope}, SignedHeaders={signed}, Signature={sig}"
    last = None
    for attempt in range(3):
        try:
            r = requests.put(f"https://{host}{path}", data=data, headers=h, timeout=600)
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
