"""One-off probe: can the stored Instagram tokens (1) read the page's recent posts and (2) read reel insights? Writes poster/probe/ig_probe.json."""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import post

out = {}
METRICS = ["reach", "views", "saved", "shares", "likes", "comments", "total_interactions", "ig_reels_avg_watch_time", "ig_reels_video_view_total_time", "plays"]
for page in ("coimbatore",):
    r = out[page] = {}
    try:
        tok = post.bridge_get("token", page=page)["token"]
        uid, name = post.ig_account(tok)
        r["account"] = name
        m = post.ig("GET", f"{uid}/media", tok, fields="id,caption,timestamp,media_product_type,permalink,like_count,comments_count", limit=12)
        items = m.get("data", [])
        r["media_ok"] = len(items)
        r["recent"] = [{"t": i.get("timestamp"), "type": i.get("media_product_type"), "likes": i.get("like_count"), "comments": i.get("comments_count"),
                        "caption": (i.get("caption") or "")[:60].replace("\n", " ")} for i in items]
        reel = next((i for i in items if i.get("media_product_type") == "REELS"), None)
        r["insights"] = {}
        if reel:
            for met in METRICS:
                try:
                    d = post.ig("GET", f"{reel['id']}/insights", tok, metric=met)
                    r["insights"][met] = (d.get("data") or [{}])[0].get("values")
                except Exception as e:
                    r["insights"][met] = "ERR " + str(e)[:160]
        try:
            q = post.ig("GET", f"{uid}/content_publishing_limit", tok, fields="quota_usage,config")
            r["publishing_quota"] = (q.get("data") or [{}])[0]
        except Exception as e:
            r["publishing_quota"] = "ERR " + str(e)[:160]
        try:
            d = post.ig("GET", f"{uid}/insights", tok, metric="reach", period="day")
            r["account_reach"] = (d.get("data") or [{}])[0].get("values")
        except Exception as e:
            r["account_reach"] = "ERR " + str(e)[:160]
    except Exception as e:
        r["error"] = str(e)[:300]
def _redact(o):
    """the result is committed to a PUBLIC repo: never write the token or bridge key (an error message can carry the request URL)"""
    import re
    if isinstance(o, dict):
        return {k: _redact(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_redact(v) for v in o]
    if isinstance(o, str):
        o = re.sub(r"(access_token|key|token)=[^&\s'\"]+", r"\1=***", o)
        for secret in (os.environ.get("BRIDGE_KEY"), os.environ.get("BRIDGE_URL")):
            if secret:
                o = o.replace(secret, "***")
    return o


def check_locations(out):
    """owner 31 Oct: which config.json "locations" ids does Instagram accept? (Namakkal 30-31 Oct: all 30 tries refused - 'not a valid
    location page ID': old Instagram explore ids; the API wants the Facebook Page id of the place). One UNPUBLISHED image container per id
    - nothing is posted, unused containers expire by themselves. Accepted ids -> probe/locations_ok.json; posting uses only those."""
    import glob
    ids = sorted({str(v).strip() for k, v in (post.CONFIG.get("locations") or {}).items() if str(v).strip().isdigit()})
    covers = [json.load(open(f)).get("cover") for f in sorted(glob.glob(os.path.join(os.path.dirname(__file__), "prebuilt", "RN-*.json")))]
    image = next((c for c in reversed(covers) if c), "")
    res = out["locations"] = {}
    if not ids or not image:
        res["note"] = "no location ids in config.json" if not ids else "no picture to test with"
        return []
    try:
        tok = post.bridge_get("token", page="coimbatore")["token"]
        uid, _ = post.ig_account(tok)
    except Exception as e:
        res["note"] = f"no token for coimbatore ({type(e).__name__})"
        return []
    ok = []
    for pid in ids:
        try:
            post.ig("POST", f"{uid}/media", tok, image_url=image, caption="location check - not published", location_id=pid)
            res[pid] = "ok"
            ok.append(pid)
        except Exception as e:
            res[pid] = "refused: " + str(e)[:140]
    return ok


ok_ids = check_locations(out)
out = _redact(out)
os.makedirs(os.path.join(os.path.dirname(__file__), "probe"), exist_ok=True)
if "note" not in out.get("locations", {}):
    json.dump(ok_ids, open(os.path.join(os.path.dirname(__file__), "probe", "locations_ok.json"), "w"))
json.dump(out, open(os.path.join(os.path.dirname(__file__), "probe", "ig_probe.json"), "w"), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False)[:1500])
