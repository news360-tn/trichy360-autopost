"""owner 24 Nov ("my final goal: post to Instagram, Facebook and YouTube without anything stopping"): when Cloudinary refuses a file
(monthly credits used up, account disabled, any error), the file is kept in THIS page's own public GitHub repository
(media/<YYYYMMDD>/<hash>.<ext>) through the GitHub contents API, and its raw link is used instead - so a news picture, a rasipalan /
gold photo or (last resort) a video still gets a public link. Pictures are served as image/jpeg / image/png. Folders older than
KEEP_DAYS are removed by cloudclean.yml. Needs GH_MEDIA_TOKEN (the workflow's own github.token) and GITHUB_REPOSITORY (set by GitHub
Actions); without them nothing changes (Cloudinary's error is raised as before). Never prints the token."""
import base64
import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path

import requests

KEEP_DAYS = 1      # owner 25 Nov: old media kept 24 hours only (cloudclean.yml)
API = "https://api.github.com/repos/{repo}/contents/{path}"


def enabled():
    return bool(os.environ.get("GH_MEDIA_TOKEN") and os.environ.get("GITHUB_REPOSITORY"))


def host(data, name="file.jpg", kind="image"):
    """bytes -> raw.githubusercontent.com link (pinned to the commit, so it works at once). Raises on failure."""
    if not enabled():
        raise RuntimeError("GitHub media fallback not set up (GH_MEDIA_TOKEN)")
    repo = os.environ["GITHUB_REPOSITORY"]
    ext = Path(name).suffix.lower() or (".mp4" if kind == "video" else ".jpg")
    path = f"media/{datetime.now(timezone.utc):%Y%m%d}/{hashlib.sha1(data).hexdigest()[:16]}{ext}"
    head = {"Authorization": "Bearer " + os.environ["GH_MEDIA_TOKEN"], "Accept": "application/vnd.github+json"}
    r = requests.put(API.format(repo=repo, path=path), headers=head, timeout=300,
                     json={"message": f"media fallback (Cloudinary refused) {path}", "content": base64.b64encode(data).decode()})
    if r.status_code == 422:      # the same file was stored before: its link on the branch
        return f"https://raw.githubusercontent.com/{repo}/HEAD/{path}"
    r.raise_for_status()
    sha = (r.json().get("commit") or {}).get("sha") or "HEAD"
    return f"https://raw.githubusercontent.com/{repo}/{sha}/{path}"


def host_file(path, kind="image"):
    p = Path(path)
    return host(p.read_bytes(), p.name, kind)


def fallback(cloud_fn, path_or_data, kind="image", name="file.jpg", log=print):
    """owner 25 Nov: Cloudflare R2 first (poster/r2host.py, when its secrets are saved), then cloud_fn() (the Cloudinary upload),
    and when that raises too and the fallback is set up, the GitHub link"""
    try:
        import r2host
        if r2host.enabled():
            try:
                if isinstance(path_or_data, (bytes, bytearray)):
                    return r2host.put(bytes(path_or_data), name, kind)
                return r2host.put_file(path_or_data, kind)
            except Exception as e:
                log(f"Cloudflare R2 refused ({str(e)[:160]}) - trying Cloudinary")
    except ImportError:
        pass
    try:
        return cloud_fn()
    except Exception as e:
        if not enabled():
            raise
        log(f"Cloudinary refused ({str(e)[:160]}) - this {kind} is kept in the page's GitHub repository instead (posting goes on)")
        if isinstance(path_or_data, (bytes, bytearray)):
            return host(bytes(path_or_data), name, kind)
        return host_file(path_or_data, kind)
