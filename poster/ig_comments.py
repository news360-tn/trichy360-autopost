"""READ-ONLY: fetch the comments on the page's recent posts (Instagram Graph API) into an encrypted report.
Nothing is posted, replied, hidden or deleted. Comment text is never printed to the (public) log - only counts.
Usage: python poster/ig_comments.py <page> [<page> ...]   -> comments_report.json"""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(__file__))
import post

pages = sys.argv[1:]
report = {"generated": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()), "pages": {}}
for page in pages:
    pr = report["pages"][page] = {"posts": [], "errors": []}
    try:
        tok = post.bridge_get("token", page=page)["token"]
        uid, name = post.ig_account(tok)
        pr["account"] = name
        m = post.ig("GET", f"{uid}/media", tok, fields="id,caption,timestamp,media_product_type,permalink,comments_count,like_count", limit=50)
        items = m.get("data", [])
    except Exception as e:
        pr["errors"].append("media: " + str(e)[:300]); print(page, "media error"); continue
    total = 0
    for it in items:
        p = {k: it.get(k) for k in ("id", "timestamp", "media_product_type", "permalink", "comments_count", "like_count")}
        p["caption"] = (it.get("caption") or "")[:140]
        p["comments"] = []
        if it.get("comments_count"):
            try:
                after, n = None, 0
                while n < 4:
                    kw = dict(fields="id,text,username,timestamp,like_count,replies{id,text,username,timestamp}", limit=50)
                    if after: kw["after"] = after
                    c = post.ig("GET", f"{it['id']}/comments", tok, **kw)
                    p["comments"] += c.get("data", [])
                    after = ((c.get("paging") or {}).get("cursors") or {}).get("after")
                    n += 1
                    if not (c.get("paging") or {}).get("next"): break
            except Exception as e:
                p["error"] = str(e)[:300]
        total += len(p["comments"])
        pr["posts"].append(p)
    print(f"{page}: {len(items)} posts checked, {total} comments read")
json.dump(report, open("comments_report.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
