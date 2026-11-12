"""Coimbatore 360 - owner 1 Nov: POWER-SHUTDOWN news is posted at once, WITHOUT the owner's tick (every other news waits for the
6 AM / 4 PM pick e-mail).

Every hour 6 AM - 10 PM IST (.github/workflows/powercut.yml):
  find    Dinamani + Dinamalar Coimbatore pages (main) and Covai Mail (backup) -> power-cut notices of Coimbatore district whose cut day
          is today (and not over) or later -> research_free/results/powercut_urls.txt (written by collect.py, then posted at once)
  verify  exit 0 when every power cut written today is on Instagram, exit 3 when one is not (the workflow retries, then fails loudly)

Never twice: the same cut day + the same place (Dinamani, Dinamalar and Covai Mail print the same notice) is written once, and a cut
already in the Sheet is skipped. Never late: a cut whose day has passed, or that ends within the hour, is skipped.
"""
import datetime, json, os, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import allnews      # noqa: E402

# ---- the only part that differs between the Coimbatore and the Namakkal copy of this file
QUERIES = ["கோவை மின்தடை", "கோயம்புத்தூர் மின்தடை", "நாளைய மின்தடை கோவை", "பொள்ளாச்சி மின்தடை", "மேட்டுப்பாளையம் மின்தடை",
           "சூலூர் மின்தடை", "அன்னூர் மின்தடை", "கோவை மின் நிறுத்தம்"]
SITES = ("dinamani.com", "dinamalar.com", "covaimail.com")      # order = preference when two papers print the same cut
DISTRICT_URL = ("district-news-coimbatore", "edition-coimbatore", "covaimail.com")      # a link of the district's own page
# ----

STATE = HERE / "archive" / "powercut_state.json"
URLS = HERE / "results" / "powercut_urls.txt"
IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
DRY = os.environ.get("POWERCUT_DRY", "") == "1"


def pid(url):
    """the same id as poster/post.py owner_picked() uses"""
    import hashlib
    return "C" + hashlib.sha1(url.encode()).hexdigest()[:7]


def pid_forms(url):
    u = str(url or "").strip()
    forms = {u, u.replace("://www.dinamalar", "://l-www.dinamalar"), u.replace("://l-www.dinamalar", "://www.dinamalar"),
             u.replace("/amp/story/", "/"), u.rstrip("/")}
    return {pid(x) for x in forms if x}


def bridge_get(action):
    import collect
    return collect.bridge(action)


def recent_rows():
    rr = bridge_get("recent")
    if not rr.get("ok"):
        raise RuntimeError(f"bridge recent: {rr}")
    return rr["rows"]


def status(ids, rows):
    """{id: 'posted' | 'queued RN-x (...)' | 'not written'}"""
    by = {}
    for r in rows:
        for i in pid_forms(r.get("source")):
            by.setdefault(i, r)
    out = {}
    for i in ids:
        r = by.get(i)
        if not r:
            out[i] = "not written"
        elif any(str(v).startswith("http") for k, v in r.items() if k.endswith("_link")) or str(r.get("post_status") or "").lower().startswith(("posted", "partly")):
            out[i] = "posted"
        else:
            out[i] = f"queued {r.get('story_id')} ({r.get('post_status') or 'no status'})"
    return out


def log(*a):
    print(datetime.datetime.now(IST).strftime("%H:%M:%S"), *a, flush=True)


def fr():
    sys.path.insert(0, str(HERE.parent / "poster"))
    import freshness
    return freshness


def load():
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return {"seen": {}, "done": {}}


def save(st):
    cut = (datetime.datetime.now(IST) - datetime.timedelta(days=4)).isoformat()
    st["seen"] = {u: v for u, v in st.get("seen", {}).items() if v.get("at", "") >= cut}      # 4 days of opened links
    st["done"] = {k: v for k, v in st.get("done", {}).items() if v.get("at", "") >= cut}
    st["retried"] = {k: v for k, v in st.get("retried", {}).items() if v.get("at", "") >= cut}
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")


def norm(u):
    return u.split("?")[0].rstrip("/").replace("dinamani.com/amp/story/", "dinamani.com/").replace("://l-www.dinamalar.com", "://www.dinamalar.com")


def links():
    """article links: the two papers' own district pages (every link, opened once and remembered) + news searches for power cuts
    (only results whose HEADLINE is a power cut are kept - 1 Nov: resolving every search result took over 20 minutes)"""
    items = []
    try:
        items += allnews.from_dinamalar_list()
    except Exception as e:
        log(f"Dinamalar list failed: {str(e)[:120]}")
    try:
        for cfg in json.loads((HERE / "sources.json").read_text(encoding="utf-8")):
            if "dinamani.com" in cfg["url"]:
                items += allnews.from_listing(dict(cfg, limit=80))
    except Exception as e:
        log(f"Dinamani list failed: {str(e)[:120]}")
    F = fr()
    for q in QUERIES:
        for dom in SITES:
            for fn in (allnews.from_google, allnews.from_bing):
                try:
                    items += [x for x in fn(f"{q} site:{dom}") if dom in (x.get("site", "") + x.get("url", "")) and F.is_power_cut(x.get("title", ""))]
                except Exception as e:
                    log(f"{fn.__name__} '{q}' {dom} failed: {str(e)[:80]}")
    out, seen = [], set()
    for it in items:
        u = it["url"]
        if "news.google.com" in u:
            try:
                u = allnews.resolve(u)
            except Exception:
                continue
        u = norm(u)
        if u in seen or not any(d in u for d in SITES):
            continue
        seen.add(u)
        out.append(dict(it, url=u))
    return out


def site_rank(u):
    return next((i for i, d in enumerate(SITES) if d in u), 9)


def check(it, today, now):
    """-> (notice dict, '') or (None, reason)"""
    F = fr()
    title_hint = it.get("title") or ""
    if title_hint and not F.is_power_cut(title_hint):
        return None, "not a power cut"
    try:
        art = allnews.article_any(it["url"])
    except Exception as e:
        return None, f"could not open ({str(e)[:40]})"
    title = re.sub(r"\s+", " ", (art.get("title") or title_hint).replace("ுா", "ூ")).strip()
    text = art.get("text") or ""
    it["_title"] = title
    if not F.is_power_cut(title):
        return None, "not a power cut"
    if not (allnews.has_place(title) or allnews.has_place(text[:800]) or any(d in it["url"] for d in DISTRICT_URL)):
        return None, "not this district"
    if allnews.other_district(title):
        return None, "other district"
    pub = art.get("published") or it.get("published") or ""
    day, _ = F.cut_day(title + " " + text[:300], pub)
    if not day:
        return None, "cut day unknown"
    if day < today:
        return None, f"cut day {day} has passed"
    over = F.power_cut_over(title, "", pub, now)
    if over:
        return None, over
    return {"id": pid(it["url"]), "url": it["url"], "title": title, "published": pub, "cut_day": day.isoformat()}, ""


def same_cut(a, b):
    F = fr()
    return a["url"] == b["url"] or (a.get("cut_day") == b.get("cut_day") and F.same_power_cut(a["title"], a["published"], b["title"], b["published"]))


def _change_without_original(n, recent):
    """owner 11 Nov: a cancellation / postponement / day change is news for our followers ONLY when we posted that power cut"""
    from freshness import cut_change, change_of_posted
    if not cut_change(n["title"]) or not recent:      # the Sheet could not be read: never block on missing data
        return False
    posted_heads = [str(r.get("headline_ta") or "") for r in recent
                    if any(str(v).startswith("http") for k, v in r.items() if k.endswith("_link"))
                    or str(r.get("post_status") or "").lower().startswith(("posted", "partly"))]
    return not any(change_of_posted(n["title"], h) for h in posted_heads)


def cmd_find():
    now = datetime.datetime.now(IST)
    today = now.date()
    st = load()
    try:
        recent = recent_rows()
    except Exception as e:
        log("Sheet rows not available - duplicate check uses this job's own list only:", str(e)[:120])
        recent = []
    posted = [{"url": norm(str(r.get("source") or "")), "title": r.get("headline_ta") or "", "published": r.get("published") or r.get("researched") or "",
               "cut_day": ""} for r in recent if fr().is_power_cut(r.get("headline_ta") or "")]
    for p in posted:
        d, _ = fr().cut_day(p["title"], p["published"])
        p["cut_day"] = d.isoformat() if d else ""
    # owner 2 Nov (review): a notice found earlier whose story never reached the Sheet (the writer failed) is tried again
    try:
        rows_all = list(recent) + list(bridge_get("queue").get("rows", []))
    except Exception:
        rows_all = list(recent)
    for k, v in list(st.get("done", {}).items()):
        age_min = (now - datetime.datetime.fromisoformat(v.get("at") or now.isoformat())).total_seconds() / 60
        tries = (st.setdefault("retried", {}).get(k) or {}).get("n", 0)
        if 30 < age_min < 12 * 60 and tries < 2 and rows_all and status([k], rows_all).get(k) == "not written":
            st["retried"][k] = {"n": tries + 1, "at": now.isoformat()}      # owner 2 Nov (review): a notice the writer refuses is not retried for ever
            log(f"not written last time - tried again ({tries + 1}/2): {v.get('title', '')[:70]}")
            st["done"].pop(k, None)
            st["seen"].pop(v.get("url", ""), None)
    found, reasons = [], {}
    for it in sorted(links(), key=lambda x: site_rank(x["url"])):
        u = it["url"]
        old = st["seen"].get(u)
        if old and (not old.get("power_cut") or old.get("why", "").startswith("cut day")):
            continue      # opened before: not a power cut / its day has passed
        if old and old.get("power_cut") and u in {v["url"] for v in st["done"].values()}:
            continue
        n, why = check(it, today, now)
        if why.startswith("could not open"):      # owner 2 Nov (review): a 502 is not 'not a power cut' - opened again next run
            reasons[why[:14]] = reasons.get(why[:14], 0) + 1
            continue
        st["seen"][u] = {"at": now.isoformat(), "power_cut": bool(n) or why.startswith(("cut day", "power cut ends")), "why": why,
                         "title": it.get("_title", it.get("title", ""))}
        if not n:
            reasons[why] = reasons.get(why, 0) + 1
            if why in ("not this district", "other district", "cut day unknown"):
                log(f"  {why}: {st['seen'][u].get('title', '')[:70]} <{u}>")
            continue
        if _change_without_original(n, recent):
            reasons["cancellation / change of a cut we never posted"] = reasons.get("cancellation / change of a cut we never posted", 0) + 1
            continue
        if any(same_cut(n, d) for d in list(st["done"].values()) + posted + found):
            reasons["already written / posted"] = reasons.get("already written / posted", 0) + 1
            continue
        found.append(n)
    log("skipped:", ", ".join(f"{k}={v}" for k, v in sorted(reasons.items(), key=lambda x: -x[1])) or "-")
    for n in found:
        log(f"POWER CUT {n['cut_day']}: {n['title'][:80]} <{n['url']}>")
        if not DRY:
            st["done"][n["id"]] = dict(n, at=now.isoformat())
    if not found:
        log("no new power-cut notice")
    URLS.parent.mkdir(parents=True, exist_ok=True)
    URLS.write_text("\n".join(n["url"] for n in found), encoding="utf-8")
    if not DRY:
        save(st)
    return 0


def remember_refused(st=None):
    """owner 11 Nov (பழங்கரை notice refused as a duplicate in an earlier run turned later checks red): the writer's refusals of
    this job are kept in powercut_state.json (committed), so every later check knows them. Kept 2 days."""
    own = st is None
    st = st if st is not None else load()
    now = datetime.datetime.now(IST)
    keep = st.setdefault("refused", {})
    try:
        ref = json.loads((HERE / "results" / "pick_refused.json").read_text(encoding="utf-8"))
    except Exception:
        ref = {}
    for u, why in ref.items():
        keep.setdefault(pid(u), {"why": why, "at": now.isoformat()})
    cut = (now - datetime.timedelta(days=2)).isoformat()
    st["refused"] = {k: v for k, v in keep.items() if v.get("at", "") >= cut}
    if own:
        save(st)
    return st["refused"]


def cmd_verify():
    """every power cut written in the last 12 hours must be on Instagram (or its cut already over)"""
    st = load()
    now = datetime.datetime.now(IST)
    want = {k: v for k, v in st.get("done", {}).items() if v.get("at", "") >= (now - datetime.timedelta(hours=12)).isoformat()}
    if not want:
        log("verify: nothing written")
        return 0
    rows = []
    for a in ("queue", "recent"):
        try:
            rows += bridge_get(a).get("rows", [])
        except Exception as e:
            log(f"verify: bridge {a} failed: {e}")
    stat = status(list(want), rows)
    refused = {k: v.get("why", "") for k, v in remember_refused(st).items()}      # this job's and earlier jobs' refusals
    by = {}
    for r in rows:
        for i in pid_forms(r.get("source")):
            by.setdefault(i, r)
    bad = {}
    for k, v in stat.items():
        if v == "posted":
            continue
        why = refused.get(k, "") if v == "not written" else _never_posted(by.get(k)) if v.startswith("queued") else ""
        if why:
            log(f"   SKIPPED {k}: {why[:150]} - {want[k]['title'][:60]}")      # never posted on purpose - not a failure
            continue
        if fr().power_cut_over(want[k]["title"], "", want[k]["published"], now) or want[k]["cut_day"] < now.date().isoformat():
            log(f"   {k}: cut over before it was posted - {want[k]['title'][:60]}")
            continue
        bad[k] = v
    log(f"verify: {len(stat) - len(bad)} of {len(stat)} power cuts posted")
    for k, v in bad.items():
        log(f"   NOT POSTED {k}: {v} - {want[k]['title'][:60]}")
    return 3 if bad else 0


def _never_posted(row):
    """the posting rule of poster/post.py: held / stale, or the same power cut already on Instagram -> never posted"""
    if not row:
        return ""
    try:
        sys.path.insert(0, str(HERE.parent / "poster"))
        import post
        why = post.skip_reason(row) or ""
        if not why:
            d = post._ig_dup_for_check(row, "coimbatore")
            why = f"already on Instagram ({d})" if d else ""
        return why
    except Exception as e:
        log("verify: posting rule not checked:", str(e)[:120])
        return ""


def ids():
    """ids of the power cuts this job wrote (poster/post.py posts them with no other check)"""
    return set(load().get("done", {}))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "find":
        sys.exit(cmd_find())
    if cmd == "remember":
        remember_refused()
        sys.exit(0)
    if cmd == "verify":
        sys.exit(cmd_verify())
    sys.exit(__doc__)
