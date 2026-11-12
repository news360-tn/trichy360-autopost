"""Comment replies with the owner's approval (owner 11 Nov). NOTHING is posted from here.

Every run: the page's recent posts (last 60 days, never answered) -> comments not handled before -> 5-7 short Tamil reply options each (AI) ->
sent to the Apps Script bridge (action commentNew), which keeps them in the private "Comments" tab and e-mails the owner.
The owner picks / edits a reply on the confirmation page; only Apps Script posts it (apps_script/Code.gs, comment replies part).

The GitHub repository and its logs are PUBLIC: comment text and usernames are never printed or saved here - only counts.
Needs the Instagram permission instagram_business_manage_comments on the page tokens (without it Instagram returns no comment text).
Usage: python poster/comments.py <page> [<page> ...]      (DRY_RUN=1: options are made but nothing is sent / e-mailed)
"""
import os, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "research_free"))
import post      # noqa: E402

DAYS = int(os.environ.get("COMMENT_DAYS", "60") or 60)      # owner 11 Nov: the old comments never answered are offered too, not only new ones
MAX_PER_RUN = int(os.environ.get("COMMENT_MAX", "20") or 20)      # one Google Form holds up to 20 comments
DRY = os.environ.get("DRY_RUN", "") in ("1", "true", "yes")
HANDLES = {"trichy": "trichy.360"}      # the page's Instagram handle (placeholder - confirm before going live)

SYSTEM = """You help the owner of a Tamil local-news Instagram page reply to viewers' comments. You NEVER post anything - the owner chooses.
Return JSON: {"kind": one of "question" | "doubt_or_fake_claim" | "complaint" | "praise" | "info_from_viewer" | "spam_or_abuse" | "other",
"options": [5 to 7 different replies - different tones: thanks + source, a direct answer from the post, "we will check and update",
asking for more details, an invitation to share / follow, a very short thank-you]}.
Rules for every reply:
- Tamil, polite, warm, short (at most 2 sentences, under 220 characters). No hashtags, no links, no emoji spam (one emoji at most).
- Use ONLY facts in the post text given below. Never add a new fact, number, name or promise. If the answer is not in the post, say we will check and update.
- A viewer who says the news is false / fake / old: thank them, give the source and date from the post's source line if present, and invite them to share correct details.
- A complaint about a local problem: thank them and say we will bring it to the notice of the officials / follow up.
- Praise: a short thank-you (one option may ask them to share the page with friends).
- spam_or_abuse: "options" is an empty list.
- Never argue, never blame, never take a political side."""


def log(*a):
    print(*a, flush=True)


def options_for(post_text, comment):
    user = f"POST (our news, the only facts you may use):\n{post_text[:1800]}\n\nVIEWER COMMENT:\n{comment[:600]}"
    import llm
    try:
        d, model = llm.ask_json(SYSTEM, user)
    except Exception:
        d, model = llm.ask_claude(SYSTEM, user, max_tokens=1500)
    opts = [str(o).strip()[:400] for o in (d.get("options") or []) if str(o).strip()][:7]
    return str(d.get("kind") or "other"), opts


def recent_media(page, tok):
    uid, _ = post.ig_account(tok)
    m = post.ig("GET", f"{uid}/media", tok, fields="id,caption,timestamp,permalink,comments_count", limit=100)
    cut = datetime.now(timezone.utc) - timedelta(days=DAYS)
    out = []
    for it in m.get("data", []):
        try:
            t = datetime.strptime(it.get("timestamp", ""), "%Y-%m-%dT%H:%M:%S%z")
        except Exception:
            continue
        if t >= cut and it.get("comments_count"):
            out.append(it)
    return out


def run(page):
    tok = post.bridge_get("token", page=page)["token"]
    seen = set(post.bridge_get("commentsSeen").get("ids", [])) if not DRY else set()
    items, read, own = [], 0, HANDLES.get(page, "")
    for it in recent_media(page, tok):
        try:
            c = post.ig("GET", f"{it['id']}/comments", tok, fields="id,text,username,timestamp,replies{username}", limit=50)
        except Exception as e:
            log(f"{page}: comments of one post not read ({str(e)[:120]})")
            continue
        for cm in c.get("data", []):
            read += 1
            if str(cm.get("id")) in seen or not (cm.get("text") or "").strip() or (cm.get("username") or "") == own:
                continue
            if any((x.get("username") or "") == own for x in ((cm.get("replies") or {}).get("data") or [])):
                continue      # the page already answered it (by hand in the app) - never offered again
            if len(items) >= MAX_PER_RUN:
                break
            cap = it.get("caption") or ""
            try:
                kind, opts = options_for(cap, cm["text"])
            except Exception as e:
                log(f"{page}: reply options not made for one comment ({str(e)[:120]}) - tried again next run")
                continue
            items.append({"comment_id": cm["id"], "media_id": it["id"], "permalink": it.get("permalink", ""),
                          "post_title": cap.split("\n")[0][:120], "post_text": cap[:3000], "user": cm.get("username", ""), "text": cm["text"],
                          "kind": kind, "options": opts})
    log(f"{page}: {read} comments read, {len(items)} new")      # counts only - the repo is public
    if items and not DRY:
        r = post.bridge_post("commentNew", {"page": page, "items": items, "form_base": post.BRIDGE_URL})
        log(f"{page}: {r.get('added', 0)} sent to the owner for approval")
    elif items:
        log(f"{page}: DRY RUN - {len(items)} would be e-mailed")
    return len(items)


def send_test(page):
    """owner 11 Nov: ONE sample e-mail so the owner sees how it looks - a made-up viewer comment on the page's latest post, with 5-7 real
    AI reply options. The comment id starts with TEST-, so no reply can ever be posted from it (Instagram refuses an unknown id)."""
    tok = post.bridge_get("token", page=page)["token"]
    uid, _ = post.ig_account(tok)
    it = (post.ig("GET", f"{uid}/media", tok, fields="id,caption,permalink", limit=1).get("data") or [{}])[0]
    cap = it.get("caption") or ""
    text = "இது உண்மையான செய்தியா? எந்த பேப்பரில் வந்தது?"
    kind, opts = options_for(cap, text)
    item = {"comment_id": f"TEST-{int(datetime.now(timezone.utc).timestamp())}", "media_id": it.get("id", ""), "permalink": it.get("permalink", ""),
            "post_title": "[TEST - sample e-mail, nothing will be posted] " + cap.split("\n")[0][:100], "post_text": cap[:3000], "user": "sample_viewer",
            "text": text, "kind": kind, "options": opts}
    r = post.bridge_post("commentNew", {"page": page, "items": [item], "form_base": post.BRIDGE_URL})
    log(f"{page}: test e-mail sent ({r.get('added', 0)} sample comment, {len(opts)} reply options)")


if __name__ == "__main__":
    if os.environ.get("TEST_EMAIL", "") == "1":      # manual run only: one sample e-mail for the first page
        send_test(sys.argv[1])
        sys.exit(0)
    total = 0
    for pg in sys.argv[1:]:
        try:
            total += run(pg)
        except Exception as e:
            log(f"{pg}: comment check skipped - {str(e)[:200]}")
    log(f"done: {total} new comment(s) sent for approval")
