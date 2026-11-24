"""owner 24 Nov ("post immediately all the news - daily some problem found"): a news HELD by the fact-check (a detail that is not in
the article: a wrong age / name, an invented date ...) is written again from its source article. The writer is told the exact problems
of the first version; the new draft goes through the same writer checks and the same posting hold rules (poster/post.py news_hold).
Only a draft with NO fact problem left is saved to poster/fixed/<story>.json - the posting job then posts that corrected text
(poster/post.py apply_fixes). Today's and yesterday's news only, at most 2 tries per news, AUTOFIX_MAX news per run. Never prints a key."""
import datetime
import json
import os
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "poster"))
import allnews      # noqa: E402
import collect      # noqa: E402
import freshness      # noqa: E402
import post      # noqa: E402
import run      # noqa: E402

IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
FIX = ROOT / "poster" / "fixed"
TRIES = FIX / "_tries.json"
MAX_TRIES = 2
MAX_PER_RUN = int(os.environ.get("AUTOFIX_MAX", "6") or 6)


def log(*a):
    print(datetime.datetime.now(IST).strftime("%H:%M:%S"), *a, flush=True)


def images_of(row):
    return [u for u in re.split(r"[\s,]+", str(row.get("images") or "")) if u.startswith("http")]


def problems_of(row):
    v = str(row.get("verification") or "")
    return v.split("problems:", 1)[1].strip() if "problems:" in v else v


def candidates(rows, now):
    today = now.date()
    out = []
    for row in rows:
        sid = row.get("story_id") or ""
        if not sid or (FIX / f"{sid}.json").exists() or not str(row.get("source") or "").startswith("http"):
            continue
        if all(post.page_done(row, p) for p in post.pages_of(row)):
            continue
        why = post.news_hold(row) or ""
        if not why.startswith("held: fact-check problems"):
            continue
        nd = freshness.news_date(row.get("published"), row.get("source"), None)
        if not nd or (today - nd).days > 1:      # today's and yesterday's news only (the posting rule)
            continue
        out.append(row)
    return out


def rewrite(row, now):
    n = len(images_of(row))
    art = allnews.article_any(row["source"])
    art = art if isinstance(art, dict) else {"title": "", "text": str(art)}
    art.setdefault("published", row.get("published", ""))
    art["url"] = row["source"]
    shape = (f"this story already has exactly {n} images: slides_spec.slides must have exactly {n - 1} items and scenes exactly {n} items."
             if n > 1 else "this story already has its ONE image: scenes must have exactly 1 item.")
    run.EXTRA[0] = ("IMPORTANT: " + shape + " This news was written once before and the fact-check found these mistakes - do NOT repeat "
                    "them; leave out anything the article does not say (no invented date, age, name, time or place); copy every place name, "
                    "number and amount exactly as the article writes it. Mistakes found: " + problems_of(row)[:1500])
    try:
        res = run.write(art, now.strftime("%A %d %B %Y"))
    except Exception as e:
        res = e
    story, why = collect.file_story(art, res, [], [], scenes=["(the existing image is kept)"])
    if not story:
        return None, why
    spec = story.get("slides_spec")
    if n > 1 and isinstance(spec, dict) and len(spec.get("slides") or []) != n - 1:
        return None, f"slides must be {n - 1}"
    fixed = {"headline_ta": story["tamil_headline"], "headline_en": story["english_headline"], "caption": story["caption"],
             "reel_script": story["reel_script"], "location": story.get("location") or row.get("location"),
             "slides_spec": json.dumps(spec, ensure_ascii=False) if isinstance(spec, dict) else spec,
             "verification": story.get("verification") or ""}
    still = post.news_hold(dict(row, **fixed))
    if still:
        return None, "still held: " + still[:200]
    return fixed, ""


def main():
    now = datetime.datetime.now(IST)
    FIX.mkdir(parents=True, exist_ok=True)
    try:
        tries = json.loads(TRIES.read_text(encoding="utf-8"))
    except Exception:
        tries = {}
    rows = post.bridge_get("queue")["rows"]
    todo = [r for r in candidates(rows, now) if int(tries.get(r["story_id"], 0)) < MAX_TRIES][:MAX_PER_RUN]
    log(f"{len(todo)} held news to fix:", [r["story_id"] for r in todo])
    for row in todo:
        sid = row["story_id"]
        tries[sid] = int(tries.get(sid, 0)) + 1
        try:
            fixed, why = rewrite(row, now)
        except Exception as e:
            fixed, why = None, f"failed: {str(e)[:150]}"
        if not fixed:
            log(sid, "NOT fixed (try", tries[sid], "of", MAX_TRIES, "):", why)
            continue
        fixed.update(source=row["source"], story_id=sid, fixed_at=now.isoformat(timespec="seconds"), old_problems=problems_of(row)[:600])
        fixed["verification"] = "AUTO-FIXED (owner 24 Nov) - " + fixed["verification"]
        (FIX / f"{sid}.json").write_text(json.dumps(fixed, ensure_ascii=False, indent=1), encoding="utf-8")
        log(sid, "FIXED - posts with the corrected text:", fixed["headline_ta"][:80])
    cut = (now - datetime.timedelta(days=3)).isoformat()
    for f in FIX.glob("RN-*.json"):      # corrected texts older than 3 days are not needed any more
        try:
            if json.loads(f.read_text(encoding="utf-8")).get("fixed_at", "") < cut:
                f.unlink()
        except Exception:
            pass
    TRIES.write_text(json.dumps(tries, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
