"""owner 12 Nov / 21 Nov: reels go to Instagram and Facebook as FILES (direct upload), not as Cloudinary links.

Before: Instagram reel, Instagram story, Facebook reel and Facebook story each downloaded the video from Cloudinary - up to 4
downloads per reel, and the free Cloudinary plan counts every download.
Now (owner 21 Nov: "do not use Cloudinary"): the job keeps the file it just made and every upload sends that file.
  ref(path)          a "file://..." name for a file made in this job - used in place of a Cloudinary link when the page can
                     send files (igdirect.ready); nothing is uploaded to Cloudinary for it
  get(url)           the local file for a link or file:// name of THIS job, else None. Nothing is downloaded (a reel made in an
                     earlier run is sent by its link, as before)
  hosted(url, kind)  a public link for Instagram's / Facebook's old link method: an http(s) link as it is; a file:// name is
                     uploaded to Cloudinary only now - when sending the file itself failed - so a post is never lost
  shown(url)         what the Sheet notes as the video: the link, or '' for a file that never went to Cloudinary
  send(...)          binary upload to a Facebook / Instagram "rupload" address
DIRECT_UPLOAD=0 (post.yml) switches it all off: every file goes to Cloudinary exactly as before."""
import hashlib
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

_LOCAL = {}                                                   # link or file:// name -> local file in this job
_HOSTED = {}                                                  # file:// name -> the Cloudinary link made for it (fallback only)
_UPLOADER = [None]                                            # post.upload(path, kind) - set by post.py
_DIR = Path(tempfile.gettempdir()) / "news360-media"
MAX_BYTES = 300 * 1024 * 1024


def log(*a):
    print(datetime.now(timezone(timedelta(hours=5, minutes=30))).strftime("%H:%M:%S"), "  direct upload:", *a, flush=True)


def enabled():
    """ON unless the page sets DIRECT_UPLOAD=0 (owner 21 Nov: files go directly wherever Meta allows it)"""
    return os.environ.get("DIRECT_UPLOAD", "auto").strip().lower() not in ("0", "false", "no", "off")


def set_uploader(fn):
    _UPLOADER[0] = fn


def _keep(path, key):
    keep = _DIR / (hashlib.sha1(key.encode()).hexdigest()[:16] + Path(path).suffix)
    _DIR.mkdir(parents=True, exist_ok=True)
    if not keep.exists():
        keep.write_bytes(Path(path).read_bytes())      # a copy: the build folder may be cleaned before the post
    return str(keep)


def remember(url, path):
    """the job just uploaded this file to Cloudinary: keep the local copy, so Facebook gets the file instead of the link"""
    try:
        if enabled() and url and path and Path(path).is_file():
            _LOCAL[url] = _keep(path, url)
    except Exception as e:
        log("local copy not kept:", str(e)[:120])


def ref(path):
    """file:// name for a file made in this job (it is never uploaded to Cloudinary unless sending the file fails)"""
    p = str(Path(path).resolve())
    name = "file://" + p
    _LOCAL[name] = _keep(p, name)
    return name


def is_ref(url):
    return str(url or "").startswith("file://")


def get(url):
    """local file for this link / file:// name (made or kept in this job); None = use the link"""
    if not enabled() or not url:
        return None
    p = _LOCAL.get(url)
    if p and Path(p).is_file():
        return p
    if is_ref(url) and Path(url[7:]).is_file():
        return url[7:]
    return None


def hosted(url, kind="video"):
    """a public link for the old link method - a file:// name is uploaded (Cloudinary) only now, as the last resort"""
    if not is_ref(url):
        return url
    if url in _HOSTED:
        return _HOSTED[url]
    path = get(url) or (url[7:] if Path(url[7:]).is_file() else None)
    if not path or not _UPLOADER[0]:
        raise RuntimeError("the file was not sent directly and no copy is left for the link method")
    log("sending the file directly did not work - this one goes by a Cloudinary link (the post is never lost)")
    _HOSTED[url] = _UPLOADER[0](Path(path), kind)
    return _HOSTED[url]


def shown(url):
    """the video link for the Sheet's notes; '' for a file that went directly (no Cloudinary copy)"""
    if is_ref(url):
        return _HOSTED.get(url, "")
    return url or ""


def download(url, name="media.mp4"):
    """ONE download of a video Instagram already has (the story catch-up) - into this job's folder; None on any problem"""
    try:
        dst = _DIR / hashlib.sha1(url.encode()).hexdigest()[:16] / Path(name).name
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.is_file():
            r = requests.get(url, timeout=180)
            r.raise_for_status()
            data = r.content
            if len(data) > MAX_BYTES:
                raise RuntimeError("file too large")
            dst.write_bytes(data)
        return str(dst)
    except Exception as e:
        log("video not downloaded:", str(e)[:150])
        return None


def send(upload_url, token, path, timeout=600):
    """binary upload to a Facebook / Instagram 'rupload' address; raises on failure"""
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        r = requests.post(upload_url, headers={"Authorization": "OAuth " + token, "offset": "0", "file_size": str(size)},
                          data=f, timeout=timeout)
    try:
        j = r.json() or {}
    except ValueError:
        j = {}
    if r.status_code != 200 or j.get("success") is False or "error" in j:
        raise RuntimeError(f"upload refused (HTTP {r.status_code}): {r.text[:200]}")
    return j
