"""owner 24 Nov ("post immediately all the news - daily some problem found"): a news HELD by the fact-check (a detail that is not in
the article: a wrong age / name, an invented date ...) is written again from its source article. The writer is told the exact problems
of the first version; the new draft goes through the same writer checks and the same posting hold rules (poster/post.py news_hold).
Only a draft with NO fact problem left is saved to poster/fixed/<story>.json - the posting job then posts that corrected text
(poster/post.py apply_fixes). Today's and yesterday's news only, at most 2 tries per news, AUTOFIX_MAX news per run. Never prints a key.

owner 27 Nov ("do not miss power cut news"): held POWER CUTS were never fixed - the free writers answered 429 / 413 and the run stopped
at the first news every time. Now: power cuts first, judged by their CUT day (not the day the paper printed them), 3 tries, and on the
pages that keep autofix free (AUTOFIX_CLAUDE=power_cut) the paid Claude backup may answer only for a power cut, when every free
writer failed (needs ANTHROPIC_API_KEY; every other news stays free-models-only). A writer that refuses ONE news (413 too large, 400) no longer stops the run - only a rate limit / quota does.
`python autofix.py powercut` = power cuts only (run by .github/workflows/powercut.yml right after writing)."""
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
import llm      # noqa: E402
import freshness      # noqa: E402
import post      # noqa: E402
import run      # noqa: E402

IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
FIX = ROOT / "poster" / "fixed"
TRIES = FIX / "_tries.json"
MAX_TRIES = 2
MAX_TRIES_POWER_CUT = 3
BUSY = re.compile(r"\b429\b|quota|rate.?limit|too many requests|resource.?exhausted", re.I)
MAX_PER_RUN = int(os.environ.get("AUTOFIX_MAX", "6") or 6)


def log(*a):
    print(datetime.datetime.now(IST).strftime("%H:%M:%S"), *a, flush=True)


def images_of(row):
    return [u for u in re.split(r"[\s,]+", str(row.get("images") or "")) if u.startswith("http")]


def problems_of(row):
    v = str(row.get("verification") or "")
    return v.split("problems:", 1)[1].strip() if "problems:" in v else v


POWER_CUT = re.compile(r"மின்\s*தடை|மின்\s*நிறுத்த|மின்\s*வெட்டு|power\s*(cut|shut)", re.I)


def is_power_cut(row):
    texts = (row.get("headline_ta"), row.get("headline_en"), row.get("category"))
    if hasattr(freshness, "is_power_cut"):
        return freshness.is_power_cut(*texts)
    return bool(POWER_CUT.search(" ".join(str(t or "") for t in texts)))      # Namakkal's freshness.py has no is_power_cut


def power_cut_still_ahead(row, now):
    """a held power cut is worth fixing until its cut is over (it may be printed 2 days before the cut day)"""
    head = f"{row.get('headline_ta') or ''} {row.get('headline_en') or ''}"
    if freshness.power_cut_over(row.get("headline_ta"), row.get("headline_en"), row.get("published"), now):
        return False
    if hasattr(freshness, "cut_day"):
        day, _ = freshness.cut_day(head, row.get("published"))
    else:
        pub = freshness.pub_date(row.get("published"))
        ds = list(freshness.dates_in(head, now.year))
        for d_, m_, y_ in re.findall(r"(?<![\d.])(\d{1,2})[./-](\d{1,2})[./-](20\d\d|\d\d)(?![\d.])", head):      # '27.11.26'
            try:
                ds.append(datetime.date(int(y_) + (2000 if len(y_) == 2 else 0), int(m_), int(d_)))
            except ValueError:
                pass
        day = max(ds) if ds else pub and pub + datetime.timedelta(days=1 if re.search(r"நாளை|tomorrow", head, re.I) else 0)
    return bool(day and day >= now.date())


def max_tries(row):
    return MAX_TRIES_POWER_CUT if is_power_cut(row) else MAX_TRIES


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
        if is_power_cut(row):
            if power_cut_still_ahead(row, now):
                out.append(row)
            continue
        nd = freshness.news_date(row.get("published"), row.get("source"), None)
        if not nd or (today - nd).days > 1:      # today's and yesterday's news only (the posting rule)
            continue
        out.append(row)
    return sorted(out, key=lambda r: not is_power_cut(r))      # power cuts first


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


_REAL_CLAUDE = [0]      # Claude calls really made in this run
_LAST_PC = [False]


def _claude_only_for_power_cut(row):
    """AUTOFIX_CLAUDE=power_cut (the pages whose owner keeps autofix free): the paid backup answers only for a power cut - for any
    other news the per-run Claude counter is set to its limit. Unset: Claude as the workflow allows (Namakkal)."""
    if os.environ.get("AUTOFIX_CLAUDE", "") != "power_cut":
        return
    if _LAST_PC[0]:
        _REAL_CLAUDE[0] = llm.CLAUDE_CALLS[0]
    _LAST_PC[0] = is_power_cut(row)
    llm.CLAUDE_CALLS[0] = _REAL_CLAUDE[0] if _LAST_PC[0] else llm.CLAUDE_MAX


def main(power_cut_only=False):
    now = datetime.datetime.now(IST)
    _REAL_CLAUDE[0], _LAST_PC[0] = llm.CLAUDE_CALLS[0], False
    FIX.mkdir(parents=True, exist_ok=True)
    try:
        tries = json.loads(TRIES.read_text(encoding="utf-8"))
    except Exception:
        tries = {}
    rows = post.bridge_get("queue")["rows"]
    todo = [r for r in candidates(rows, now) if int(tries.get(r["story_id"], 0)) < max_tries(r)]
    if power_cut_only:
        todo = [r for r in todo if is_power_cut(r)]
    todo = todo[:MAX_PER_RUN]
    log(f"{len(todo)} held news to fix:", [r["story_id"] + (" (power cut)" if is_power_cut(r) else "") for r in todo])
    busy = False
    for row in todo:
        sid = row["story_id"]
        if busy and not is_power_cut(row):
            continue      # the free writers are rate-limited for the other news too
        _claude_only_for_power_cut(row)
        tries[sid] = int(tries.get(sid, 0)) + 1
        try:
            fixed, why = rewrite(row, now)
        except Exception as e:
            fixed, why = None, f"failed: {str(e)[:150]}"
        if not fixed:
            if re.search(r"all free models failed|no free model answered", why or "") and BUSY.search(why or ""):      # owner 24 Nov: busy AI writers are not the news's fault
                tries[sid] -= 1
                log(sid, "NOT fixed - the free AI writers are busy; tried again in a later run (this try is not counted):", (why or "")[:160])
                busy = True
                continue
            log(sid, "NOT fixed (try", tries[sid], "of", max_tries(row), "):", (why or "")[:200])
            continue
        fixed.update(source=row["source"], story_id=sid, fixed_at=now.isoformat(timespec="seconds"), old_problems=problems_of(row)[:600])
        fixed["verification"] = "AUTO-FIXED (owner 24 Nov) - " + fixed["verification"]
        (FIX / f"{sid}.json").write_text(json.dumps(fixed, ensure_ascii=False, indent=1), encoding="utf-8")
        log(sid, "FIXED - posts with the corrected text:", fixed["headline_ta"][:80])
    if os.environ.get("AUTOFIX_CLAUDE", "") == "power_cut" and not _LAST_PC[0]:
        llm.CLAUDE_CALLS[0] = _REAL_CLAUDE[0]      # the real count again
    cut = (now - datetime.timedelta(days=3)).isoformat()
    for f in FIX.glob("RN-*.json"):      # corrected texts older than 3 days are not needed any more
        try:
            if json.loads(f.read_text(encoding="utf-8")).get("fixed_at", "") < cut:
                f.unlink()
        except Exception:
            pass
    TRIES.write_text(json.dumps(tries, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(power_cut_only=sys.argv[1:2] == ["powercut"])
