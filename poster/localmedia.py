"""owner 12 Nov: reels are sent to Instagram and Facebook as FILES (direct upload), not as Cloudinary links.

Before: Instagram reel, Instagram story, Facebook reel and Facebook story each downloaded the video from Cloudinary - up to 4
downloads per reel, and the free Cloudinary plan counts every download (38 GB in 30 days on the Namakkal account).
Now: the job keeps ONE local copy of each video - the file it just made (no download at all), or one download of a prebuilt
reel - and every upload sends that file. Anything that goes wrong returns None and the caller uses the old link method,
so a post is never lost because of this."""
import hashlib, os, tempfile, time
from pathlib import Path

import requests

_LOCAL = {}                                                   # Cloudinary link -> local file in this job
_DIR = Path(tempfile.gettempdir()) / "news360-media"
MAX_BYTES = 300 * 1024 * 1024


def log(*a):
    print(time.strftime("%H:%M:%S"), "  direct upload:", *a, flush=True)


def enabled():
    """OFF unless the page sets DIRECT_UPLOAD=1 (owner 12 Nov: never change a working page without a trial first)"""
    return os.environ.get("DIRECT_UPLOAD", "0").strip().lower() in ("1", "true", "yes", "on")


def remember(url, path):
    """the job just uploaded this file to Cloudinary: keep the local copy for the direct uploads"""
    try:
        if url and path and Path(path).is_file():
            keep = _DIR / (hashlib.sha1(url.encode()).hexdigest()[:16] + Path(path).suffix)
            _DIR.mkdir(parents=True, exist_ok=True)
            if not keep.exists():
                keep.write_bytes(Path(path).read_bytes())      # a copy: the build folder may be cleaned before the post
            _LOCAL[url] = str(keep)
    except Exception as e:
        log("local copy not kept:", str(e)[:120])


def get(url):
    """local file for this link (made in this job, or downloaded ONCE); None = use the link"""
    if not enabled() or not url or not str(url).startswith("http"):
        return None
    p = _LOCAL.get(url)
    if p and Path(p).is_file():
        return p
    try:
        _DIR.mkdir(parents=True, exist_ok=True)
        ext = Path(url.split("?")[0]).suffix or ".mp4"
        dst = _DIR / (hashlib.sha1(url.encode()).hexdigest()[:16] + ext)
        if not dst.is_file():
            n = 0
            with requests.get(url, stream=True, timeout=120) as r:
                r.raise_for_status()
                tmp = dst.with_suffix(dst.suffix + ".part")
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(1 << 20):
                        n += len(chunk)
                        if n > MAX_BYTES:
                            raise RuntimeError("file too large")
                        f.write(chunk)
                tmp.rename(dst)
            log(f"downloaded once ({n / 1e6:.1f} MB)")
        _LOCAL[url] = str(dst)
        return str(dst)
    except Exception as e:
        log("no local copy - the link is used:", str(e)[:150])
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
