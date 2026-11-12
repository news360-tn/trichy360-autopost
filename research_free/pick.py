"""Coimbatore 360 - owner's pick flow (owner 1 Nov).

Twice a day (6:00 AM and 4:00 PM IST) the news of Dinamalar and Dinamani's Coimbatore pages ONLY is collected - by the article's own
published time, in back-to-back windows (yesterday 4 PM -> 6 AM, then 6 AM -> 4 PM; a late or failed round continues from the last end).
The list goes to the owner by e-mail with a check-box page (Apps Script bridge). The owner ticks news and presses Submit:
EVERY ticked news is written and posted (no other check). No submit within 1 hour: the top 8 by importance are written and posted
(owner 2 Nov: 12 -> 8; never a suicide, an obituary or a ceremony - only the owner's tick posts those).
A submit after the automatic pick ADDS the extra ticked news. Already posted news is never listed again; news listed but not posted
comes back in the next round's list while it is less than 24 hours old.

  python research_free/pick.py collect   -> collect, save the round, send the list (prints the round id)
  python research_free/pick.py decide    -> wait for the submit (max WAIT_MIN) or pick the top 8; writes the links to pick_urls.txt
  python research_free/pick.py late      -> links ticked after the decision and not written yet -> pick_urls.txt ('' when none)
State: research_free/archive/pick_state.json (committed by the workflow)."""
import datetime, difflib, hashlib, json, os, re, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import allnews      # noqa: E402

IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
STATE = HERE / "archive" / "pick_state.json"
URLS = HERE / "results" / "pick_urls.txt"
AUTO_TOP = int(os.environ.get("PICK_AUTO_TOP", "4"))      # owner 2 Nov: 12 -> 8
WAIT_MIN = int(os.environ.get("PICK_WAIT_MIN", "60"))
LEFT_HOURS = 24
AD = re.compile(r"தள்ளுபடி|ஆஃபர்|ஆபர்|அள்ளுங்க|அள்ளுவோம்|விற்பனை தொடக்கம்|ஷோரூம்|புதிய கிளை திறப்பு|சிறப்பு விற்பனை")      # advertorials, not news
DRY = os.environ.get("PICK_DRY", "") in ("1", "true", "yes")
# owner 2 Nov: "do not ask me to confirm" - no e-mail; every round's top news (PICK_AUTO_TOP, 8 + 6 + 6 = 20 a day) is written at once.
EMAIL = os.environ.get("PICK_EMAIL", "0") == "1"
# owner 2 Nov: more than two papers - every Tamil outlet the collector already trusts for Coimbatore
OUTLETS = {"dinamalar.com": "தினமலர்", "dinamani.com": "தினமணி", "dinakaran.com": "தினகரன்", "dailythanthi.com": "தினத்தந்தி",
           "maalaimalar.com": "மாலைமலர்", "hindutamil.in": "இந்து தமிழ்", "polimernews.com": "பாலிமர்"}


def log(*a):
    print(datetime.datetime.now(IST).strftime("%H:%M:%S"), *a, flush=True)


def now():
    return datetime.datetime.now(IST)


def load_state():
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return {"last_end": "", "pool": {}, "rounds": {}}


def save_state(st):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    rounds = dict(sorted(st.get("rounds", {}).items(), key=lambda kv: round_order(kv[0]))[-20:])      # keep the last 10 days of rounds
    st["rounds"] = rounds
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")


def pid(url):
    return "C" + hashlib.sha1(url.encode()).hexdigest()[:7]


def when(s):
    try:
        t = datetime.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return t if t.tzinfo else t.replace(tzinfo=IST)
    except Exception:
        return None


def first_start(t):
    """very first round: the owner's window boundary before it (06:00 or 16:00, yesterday 16:00 for a morning round)"""
    d = t.date()
    six, four = (datetime.datetime.combine(d, datetime.time(h), IST) for h in (6, 16))
    if t >= four:
        return six
    return four - datetime.timedelta(days=1)


def summary(text, title):
    """the first one or two sentences of the article that add to the headline (max ~220 characters)"""
    t = re.sub(r"\s+", " ", text or "").strip()
    out = ""
    for s in re.split(r"(?<=[.!?])\s+", t):
        if len(s) < 25 or difflib.SequenceMatcher(None, s, title or "").ratio() > 0.8:
            continue
        out = (out + " " + s).strip()
        if len(out) > 140:
            break
    return (out[:217] + "...") if len(out) > 220 else out


def category(title):
    import collect
    k = collect.top_kind(title) or ""
    names = {"power_cut": "மின்தடை", "rain": "மழை / வானிலை", "crime": "குற்றம்", "accident": "விபத்து"}
    if k in names:
        return names[k]
    for w, c in (("குடிநீர்", "குடிநீர்"), ("மாநகராட்சி", "மாநகராட்சி"), ("சாலை", "சாலை"), ("ரயில்", "ரயில்"), ("பேருந்து", "போக்குவரத்து"),
                 ("நீதிமன்ற", "நீதிமன்றம்"), ("கல்லூரி", "கல்வி"), ("பள்ளி", "கல்வி"), ("வேலைவாய்ப்பு", "வேலைவாய்ப்பு"), ("விலை", "விலை"),
                 ("கோயில்", "ஆன்மிகம்"), ("கோவில்", "ஆன்மிகம்")):
        if w in title:
            return c
    return "பொது"


def candidates(log_lines, since=None):
    """Dinamalar Coimbatore district list + Dinamani Coimbatore edition: article links"""
    items = []
    try:
        items += allnews.from_dinamalar_list()
    except Exception as e:
        log_lines.append(f"Dinamalar list failed: {str(e)[:120]}")
    try:
        cfgs = json.loads((HERE / "sources.json").read_text(encoding="utf-8"))
        for cfg in cfgs:
            if any(d in cfg["url"] for d in OUTLETS):      # owner 2 Nov: every Tamil outlet's Coimbatore page (was Dinamani only)
                try:
                    items += allnews.from_listing(dict(cfg, limit=80))
                except Exception as e:
                    log_lines.append(f"{cfg.get('name', cfg['url'])} list failed: {str(e)[:100]}")
    except Exception as e:
        log_lines.append(f"Dinamani list failed: {str(e)[:120]}")
    # the district list pages show only the latest ~20-40 news: Google / Bing news searches limited to the two papers fill the rest of the window
    both = (allnews.from_google, allnews.from_bing)
    searches = [(q, d, both) for q in ("கோவை", "கோயம்புத்தூர்", "பொள்ளாச்சி", "மேட்டுப்பாளையம்") for d in ("dinamalar.com", "dinamani.com")]
    # owner 2 Nov: the other Tamil outlets - one Google search each (a round must stay a few minutes, not half an hour)
    searches += [("கோவை", d, (allnews.from_google,)) for d in OUTLETS if d not in ("dinamalar.com", "dinamani.com")]
    for q, dom, fns in searches:
        if True:
            for fn in fns:
                try:
                    got = [x for x in fn(f"{q} site:{dom}") if dom in (x.get("site", "") + x.get("url", ""))
                           and not (since and when(x.get("published")) and when(x.get("published")) < since)]      # older than the window: not opened
                    got.sort(key=lambda x: str(x.get("published") or ""), reverse=True)
                    items += got[:25]      # the newest 25 of a search (each Google link costs a decode)
                except Exception as e:
                    log_lines.append(f"{fn.__name__} {dom} '{q}' failed: {str(e)[:80]}")
    seen, out = set(), []
    for it in items:
        u = it["url"]
        if "news.google.com" in u:
            try:
                u = allnews.resolve(u)
            except Exception:
                continue
        u = u.split("?")[0].rstrip("/").replace("dinamani.com/amp/story/", "dinamani.com/").replace("://l-www.dinamalar.com", "://www.dinamalar.com")
        if u not in seen and ("dinamalar.com/news" in u or any(d in u for d in OUTLETS if d != "dinamalar.com")):
            seen.add(u)
            out.append(dict(it, url=u))
    return out


def is_posted(url, title, recent):
    import collect
    for r in recent:
        if r.get("source") and r["source"].split("?")[0].rstrip("/") == url:
            return True
        if title and collect._fr().similar(r.get("headline_ta", ""), title, 0.6, r.get("researched")):
            return True
    return False


def check_article(it, recent):
    """-> (item dict, '') when it is real Coimbatore district news, else (None, reason)"""
    import collect
    try:
        art = allnews.article_any(it["url"])
    except Exception as e:
        return None, f"could not open ({str(e)[:50]})"
    art["url"] = it["url"]
    title = re.sub(r"\s+", " ", (art.get("title") or "").replace("ுா", "ூ")).strip()
    if not title:
        return None, "no title"
    if len(collect.body_words(art)) < collect.HEADLINE_ONLY_MIN:
        return None, "only a headline"
    if not collect.tamil_source(art):
        return None, "not Tamil"
    if not (allnews.has_place(title) or allnews.has_place(art["text"][:400]) or allnews.url_district(it["url"]) in allnews.DISTRICT_SLUGS
            or it.get("via") == "dinamalar-list") or not allnews.local_ok(it["url"], title):
        return None, "not Coimbatore district"
    if allnews.other_district(title):
        return None, "other district"
    # 1 Nov: a Dinamalar page of another district / state section (puducherry, tamil-nadu-news, premium-news ...) is taken only when
    # its headline or first lines name a Coimbatore-district place ("போதையில் தகராறு 18 பேர்" was Puducherry news)
    if "dinamalar.com" in it["url"] and "district-news-coimbatore" not in it["url"] \
            and not (allnews.has_place(title) or allnews.has_place(art["text"][:300])):
        return None, "not Coimbatore district"
    if AD.search(title):
        return None, "shop offer / advertisement"
    # owner 3 Nov: the writer's own district check, run here too - a picked story the writer then refuses (another place in its first
    # lines, e.g. a state political story on the district list) left the round short (10 AM round: 4 of 6 written)
    if allnews.written_elsewhere(title, art.get("text") or ""):
        return None, "not Coimbatore district"
    low = collect.low_interest(title, it["url"])
    if low and ("feature" in low or "editorial" in low):
        return None, low      # recipes, tips, opinion: not news (ceremonies / awards stay - the owner decides)
    if is_posted(it["url"], title, recent):
        return None, "already posted"
    if collect.same_event_filed(dict(art, title=title), recent, days=2):
        return None, "same event already posted"
    pub = art.get("published") or ""
    n = {"title": title, "snippet": art["text"][:400], "published": pub, "mentions": 1}
    return {"id": pid(it["url"]), "url": it["url"], "title": title, "summary": summary(art["text"], title),
            "source": next((v for k, v in OUTLETS.items() if k in it["url"]), "செய்தி"), "published": pub, "category": category(title),
            "score": collect.score(n), "power_cut": bool(collect._fr().is_power_cut(title))}, ""


def merge_same(items):
    """the same news from both papers is listed once (both sources noted)"""
    out = []
    for it in items:
        hit = next((o for o in out if difflib.SequenceMatcher(None, o["title"], it["title"]).ratio() > 0.62), None)
        if hit:
            if it["source"] not in hit["source"]:
                hit["source"] += " + " + it["source"]
            hit.setdefault("alts", []).append(it["url"])
            hit["score"] = max(hit["score"], it["score"]) + 1
        else:
            out.append(it)
    return out


# owner 2 Nov (morning round: a suicide, a 108-year-old's obituary, a temple ceremony were in the automatic 12): the automatic pick takes
# only news people watch. The owner can still tick any of these - a ticked news is always posted.
AUTO_SKIP = re.compile(r"தற்கொலை|தூக்கிட்டு|தூக்கில் தொங்கி|தூக்குப்போட்டு|தீக்குளி|விஷம் குடித்து|பூச்சிக்கொல்லி மருந்தை குடித்து|"
                       r"காலமான|மறைவு|இரங்கல்|அஞ்சலி|நினைவு நாள்|suicide", re.I)
# 2 Nov morning list: 'ஆராதனை திருவிழா', 'பொன் விழா, கருத்தரங்கம்', 'டிரெஸ் பர்ச்சேசில் ... வாங்கலாம்!', 'ஷாப்பிங் திருவிழா', 'மாடித்தோட்டம்'
AUTO_LOW = re.compile(r"ஆராதனை|குருபூஜை|பொன் விழா|வெள்ளி விழா|வைர விழா|கருத்தரங்க|ஷாப்பிங்|பர்ச்சேஸ்|வாங்கலாம்|மாடித்தோட்ட")


def auto_ok(it):
    """'' = may be picked automatically, else why not"""
    t = it.get("title") or ""
    if AUTO_SKIP.search(t):
        return "suicide / obituary - only when the owner ticks it"
    if AUTO_LOW.search(t):
        return "ceremony / shopping feature - only when the owner ticks it"
    try:
        import collect
        return collect.low_interest(t, it.get("url") or "")
    except Exception:
        return ""


def rank(items):
    return sorted(items, key=lambda x: (not x.get("power_cut"), -x.get("score", 0), str(x.get("published", ""))), reverse=False)


def bridge_get(action, **kw):
    import collect
    return collect.bridge(action, **kw)


def bridge_post(action, payload):
    import requests
    r = requests.post(os.environ["BRIDGE_URL"], params={"key": os.environ["BRIDGE_KEY"]},
                      data=json.dumps({"action": action, **payload}, ensure_ascii=False).encode("utf-8"),
                      headers={"Content-Type": "application/json"}, timeout=120)
    r.raise_for_status()
    d = r.json()
    if not d.get("ok"):
        raise RuntimeError(f"bridge {action}: {d.get('error')}")
    return d


def recent_rows():
    rr = bridge_get("recent")
    if not rr.get("ok"):
        raise RuntimeError(f"bridge recent: {rr}")
    return rr["rows"]


def cmd_collect():
    st = load_state()
    t_end = now()
    t_start = when(st.get("last_end")) or first_start(t_end)
    rid = t_end.strftime("%Y-%m-%d_%H")      # owner 2 Nov: 3 rounds a day (06 / 10 / 19); a late round keeps its own name
    log(f"round {rid}: news published {t_start:%d %b %H:%M} -> {t_end:%d %b %H:%M} (" + ", ".join(OUTLETS.values()) + " - Coimbatore)")
    try:      # owner 2 Nov: this round's order follows the insights read a moment ago
        import learned
        d_ = learned.load()
        log(f"insights {d_.get('updated', '?')} ({d_.get('posts_measured', 0)} reels): topic weights {d_.get('topic_weight')}; best openings {(d_.get('top_openings') or [])[:2]}")
    except Exception as e:
        log("insights not loaded:", str(e)[:80])
    recent = recent_rows()
    lines = []
    cands = candidates(lines, t_start)
    retry = st.setdefault("retry", {})      # owner 2 Nov (review): links that could not be opened are tried again (max 24 h)
    have = {c["url"] for c in cands}
    for u, r_ in list(retry.items()):
        if (t_end - (when(r_.get("first")) or t_end)).total_seconds() > LEFT_HOURS * 3600:
            retry.pop(u)
        elif u not in have:
            cands.append(dict(r_.get("it") or {"url": u}, _retry=True))
    for c in cands:      # owner 2 Nov (review): still in the paper's list - a retry all the same (its window check is relaxed)
        if c["url"] in retry:
            c["_retry"] = True
    for l in lines:
        log(l)
    log(f"{len(cands)} links on the two papers' Coimbatore pages")
    pool = st.setdefault("pool", {})
    try:
        power_done = set(json.loads((HERE / "archive" / "powercut_state.json").read_text(encoding="utf-8")).get("done", {}))
    except Exception:
        power_done = set()
    new, reasons = [], {}
    for it in cands:
        if pid(it["url"]) in pool:      # listed in an earlier round: it comes back only as a leftover (below)
            continue
        if pid(it["url"]) in power_done:      # owner 1 Nov: a power cut is posted at once by powercut.py - not asked again
            reasons["power cut - posted automatically"] = reasons.get("power cut - posted automatically", 0) + 1
            continue
        item, why = check_article(it, recent)
        if why.startswith("could not open"):
            retry.setdefault(it["url"], {"it": {k: v for k, v in it.items() if not k.startswith("_")}, "first": t_end.isoformat()})
        else:
            retry.pop(it["url"], None)
        if not item:
            reasons[why] = reasons.get(why, 0) + 1
            continue
        pt = when(item["published"])
        if pt and pt < t_start and not (it.get("_retry") and (t_end - pt).total_seconds() < LEFT_HOURS * 3600):
            reasons["published before this window"] = reasons.get("published before this window", 0) + 1
            continue
        if pt and pt > t_end + datetime.timedelta(minutes=5):
            continue
        new.append(item)
    log("skipped: " + ", ".join(f"{k}={v}" for k, v in sorted(reasons.items(), key=lambda x: -x[1])))
    new = merge_same(new)
    # leftovers: listed before, never posted, less than 24 hours old
    left = []
    for k, it in list(pool.items()):
        pt = when(it.get("published")) or when(it.get("listed_at"))
        if it.get("posted") or it.get("written") or (pt and (t_end - pt).total_seconds() > LEFT_HOURS * 3600):
            pool.pop(k)
            continue
        if is_posted(it["url"], it["title"], recent):
            pool.pop(k)
            continue
        # 1 Nov: a story listed before a filter existed (Puducherry news) must not come back as a leftover
        if allnews.other_district(it["title"]) or ("dinamalar.com" in it["url"] and "district-news-coimbatore" not in it["url"]
                                                  and not (allnews.has_place(it["title"]) or allnews.has_place(it.get("summary", "")[:300]))):
            pool.pop(k)
            continue
        if it.get("refused"):
            continue      # owner 4 Nov: the writer said no (e.g. duplicate after write) - kept in the pool so it is not "new" again
        pk = when(it.get("picked_at"))
        if pk and (t_end - pk).total_seconds() < 3 * 3600:
            continue      # picked a moment ago: still being written
        if pk:
            log(f"picked but never written - offered again: {it['title'][:60]}")
        left.append(dict(it, leftover=True))
    new = rank(new)
    left = rank(left)
    for it in new:
        pool[it["id"]] = dict(it, listed_at=t_end.isoformat())
    items = new + left
    log(f"list: {len(new)} new + {len(left)} earlier news not posted yet")
    for i, it in enumerate(items, 1):
        log(f"  {i:2}. [{it['category']}] {it['title'][:70]} ({it['source']}){' (earlier)' if it.get('leftover') else ''}")
    deadline = t_end + datetime.timedelta(minutes=WAIT_MIN)
    st["rounds"][rid] = {"window": [t_start.isoformat(), t_end.isoformat()], "ids": [x["id"] for x in items], "sent": False,
                         "deadline": deadline.isoformat(), "decided": None, "written": []}
    if not DRY and items and not EMAIL:
        log(f"automatic pick (owner 2 Nov): no e-mail - the top {AUTO_TOP} are written at once")
    elif not DRY and items:
        try:
            bridge_post("pickList", {"round": rid, "deadline": deadline.strftime("%I:%M %p").lstrip("0"), "auto_top": AUTO_TOP,
                                     "window": f"{t_start:%d %b %I:%M %p} – {t_end:%d %b %I:%M %p}",
                                     "items": [{k: x.get(k, "") for k in ("id", "title", "summary", "source", "published", "category", "url")}
                                               | {"leftover": bool(x.get("leftover"))} for x in items]})
            st["rounds"][rid]["sent"] = True
            log("list e-mailed with the check-box page")
        except Exception as e:      # the Apps Script was not updated yet / did not answer: the top 8 are posted without waiting
            log("COULD NOT E-MAIL THE LIST (update + redeploy apps_script/Code.gs):", str(e)[:200])
            if os.environ.get("PICK_REQUIRE_EMAIL") == "1":      # a round started by hand: stop, post nothing, the window stays open
                raise SystemExit("the list could not be e-mailed - nothing posted; the next round collects this window again")
    elif not items:
        log("no news in this window - no e-mail")
    st["last_end"] = t_end.isoformat()      # the next round starts here (also when this round found nothing)
    if DRY:
        log("DRY RUN: list shown only - no e-mail, the round is not saved")
    else:
        save_state(st)
    print(f"ROUND={rid}")
    return rid


def round_order(rid):
    """'2026-11-01_morning' < '2026-11-01_evening' < '2026-11-02_morning' (1 Nov: sorted as text, 'evening' came BEFORE 'morning' -
    the 4 PM round decided on the morning round's ticks and posted nothing)"""
    day, _, part = str(rid).partition("_")
    hour = {"morning": 6, "evening": 16}.get(part, int(part) if part.isdigit() else 99)
    return day, hour, part


def current_round(st):
    rs = sorted(st.get("rounds", {}).items(), key=lambda kv: round_order(kv[0]))
    return rs[-1] if rs else (None, None)


def write_urls(urls):
    URLS.parent.mkdir(parents=True, exist_ok=True)
    URLS.write_text("\n".join(urls), encoding="utf-8")
    print("PICK_URLS=" + " ".join(urls))


def cmd_decide():
    st = load_state()
    rid, rnd = current_round(st)
    if not rid or not rnd.get("ids"):
        log("no list this round - nothing to post")
        return write_urls([])
    pool = st.get("pool", {})
    deadline = when(rnd["deadline"])
    chosen, how = None, ""
    while rnd.get("sent"):      # no e-mail went out: no one can tick - the top 8 at once
        try:
            s = bridge_get("pickStatus", round=rid)
            if s.get("ok") and s.get("submitted"):
                chosen, how = [i for i in s.get("ids", []) if i in pool], f"owner ticked {len(s.get('ids', []))} at {s.get('at')}"
                break
        except Exception as e:
            log("status check failed (tried again):", str(e)[:120])
        if DRY or now() >= deadline:
            break
        time.sleep(60)
    if chosen is None:
        items = rank([pool[i] for i in rnd["ids"] if i in pool])
        left_out = [(x["title"], auto_ok(x)) for x in items if auto_ok(x)]
        items = [x for x in items if not auto_ok(x)]
        for t_, why_ in left_out:
            log(f"   not picked automatically ({why_}): {t_[:70]}")
        chosen, how = [x["id"] for x in items[:AUTO_TOP]], f"no submit by {deadline:%I:%M %p} - automatic top {AUTO_TOP}"
        if not DRY:
            try:
                bridge_post("pickAuto", {"round": rid, "ids": chosen})
            except Exception as e:
                log("could not mark the automatic pick on the page:", str(e)[:120])
    log(f"decided: {how} -> {len(chosen)} news to write and post")
    rnd["decided"] = {"how": how, "ids": chosen, "at": now().isoformat()}
    rnd["written"] = sorted(set(rnd.get("written", [])) | set(chosen))
    for i in chosen:
        if i in pool:
            pool[i]["picked_at"] = now().isoformat()      # owner 2 Nov (review): 'written' only once it is really in the Sheet
    save_state(st)
    return write_urls([pool[i]["url"] for i in chosen if i in pool])


def cmd_late():
    """news the owner ticked after the decision (late submit or a second submit) and not written yet"""
    st = load_state()
    rid, rnd = current_round(st)
    if not rid:
        return write_urls([])
    pool = st.get("pool", {})
    try:
        s = bridge_get("pickStatus", round=rid)
    except Exception as e:
        log("status check failed:", str(e)[:120])
        return write_urls([])
    extra = [i for i in (s.get("ids") or []) if i in pool and i not in rnd.get("written", [])] if s.get("submitted") else []
    if extra:
        log(f"owner ticked {len(extra)} more news after the decision - written now")
        rnd["written"] = sorted(set(rnd.get("written", [])) | set(extra))
        for i in extra:
            pool[i]["picked_at"] = now().isoformat()
        save_state(st)
    return write_urls([pool[i]["url"] for i in extra])


def pid_forms(url):
    """the ids a story's link can have (Dinamalar l-www / www, Dinamani amp) - the same rule as poster/post.py owner_picked()"""
    u = str(url or "").strip()
    forms = {u, u.replace("://www.dinamalar", "://l-www.dinamalar"), u.replace("://l-www.dinamalar", "://www.dinamalar"),
             u.replace("/amp/story/", "/"), u.rstrip("/")}
    return {pid(x) for x in forms if x}


def _never_posted(row):
    """owner 2 Nov (pick run 41436128396): a picked news that post.py will never post - held for a wrong fact / no town, stale,
    a duplicate - is 'skipped', not 'still waiting' (it stayed 'Queued' and turned every round red). The same rule as post.py."""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "poster"))
        import post
        why = post.skip_reason(row) or ""
        if not why:      # owner 11 Nov: the same news is already on Instagram (posted from another row) - the post job skips it for ever
            d = post._ig_dup_for_check(row, "coimbatore")
            why = f"already on Instagram ({d})" if d else ""
        return why
    except Exception as e:
        log("verify: posting rule not checked:", str(e)[:120])
        return ""


def picked_status(rnd, rows):
    """owner 1 Nov: every picked news must be POSTED. -> {id: 'posted' | 'queued RN-x' | 'skipped RN-x: why' | 'not written'}"""
    want = list(dict.fromkeys(list(rnd.get("written") or []) + list((rnd.get("decided") or {}).get("ids") or [])))
    by = {}
    for r in rows:
        for i in pid_forms(r.get("source")):
            by.setdefault(i, r)
    out = {}
    refused = rnd.get("refused") or {}
    for i in want:
        r = by.get(i)
        if not r and i in refused:
            out[i] = f"skipped: the writer refused it - {refused[i]}"
        elif not r:
            out[i] = "not written"
        elif r.get("trichy_link") or str(r.get("post_status") or "").lower().startswith("posted"):
            out[i] = "posted"
        else:
            why = _never_posted(r)
            out[i] = f"skipped {r.get('story_id')}: {why}" if why else f"queued {r.get('story_id')} ({r.get('post_status') or 'no status'})"
    return out


def _article_gone(url):
    """True only when the paper answers 404 / 410 for the article (deleted). A timeout or 5xx is NOT gone - it is tried again."""
    if not url:
        return False
    try:
        import requests
        r = requests.get(url, timeout=30, allow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
        return r.status_code in (404, 410)
    except Exception:
        return False


def cmd_verify():
    """exit 0 = every news picked in the latest round is on Instagram; exit 3 = some are not (the workflow retries, then fails loudly)"""
    st = load_state()
    rid, rnd = current_round(st)
    if not rid or not rnd.get("decided"):
        log("verify: no decided round")
        return 0
    rows = []
    for a in ("queue", "recent"):
        try:
            rows += bridge_get(a).get("rows", [])
        except Exception as e:
            log(f"verify: bridge {a} failed: {e}")
    stat = picked_status(rnd, rows)
    pool = st.get("pool", {})
    for k, v in list(stat.items()):      # 5 Nov (pick runs 41973850497 + 01:42 UTC): the paper deleted the article - it can never be written
        if v == "not written" and _article_gone((pool.get(k) or {}).get("url", "")):
            stat[k] = "skipped (not written): the newspaper removed the article (page not found)"
    title = {k: v.get("title", "") for k, v in pool.items()}
    skipped = {k: v for k, v in stat.items() if v.startswith("skipped")}
    bad = {k: v for k, v in stat.items() if v != "posted" and k not in skipped}
    log(f"verify {rid}: {len(stat) - len(bad) - len(skipped)} of {len(stat)} picked news posted, {len(skipped)} skipped on purpose")
    for k, v in skipped.items():
        log(f"   SKIPPED {k}: {v[:160]} - {title.get(k, '')[:60]}")      # held / stale / duplicate: post.py never posts it
    for k, v in bad.items():
        log(f"   NOT POSTED {k}: {v} - {title.get(k, '')[:60]}")
    return 3 if bad else 0


REFUSED_FILE = HERE / "results" / "pick_refused.json"


def mark_refused(st):
    """owner 4 Nov (3 Nov rounds all red): a picked news the writer refused (duplicate after write, other district, no text) is
    remembered - never offered again as a leftover, and the round check counts it as skipped, not 'not written'"""
    try:
        ref = json.loads(REFUSED_FILE.read_text(encoding="utf-8"))
    except Exception:
        return 0
    rid, rnd = current_round(st)
    pool, n = st.get("pool", {}), 0
    for url, why in ref.items():
        for k in pid_forms(url):
            if k in pool and not pool[k].get("refused"):
                pool[k]["refused"] = why
                n += 1
            if rnd is not None and k in (rnd.get("written") or []) + list((rnd.get("decided") or {}).get("ids") or []):
                rnd.setdefault("refused", {})[k] = why
    return n


def mark_posted(rows):
    """pool items whose link is now in the Sheet are 'posted' (never listed again)"""
    st = load_state()
    srcs = {str(r.get("source") or "").split("?")[0].rstrip("/") for r in rows}
    n = 0
    for it in st.get("pool", {}).values():
        if it["url"] in srcs and not it.get("posted"):
            it["posted"] = True
            n += 1
    r = mark_refused(st)
    if r:
        log(f"{r} picked news refused by the writer - not offered again")
    save_state(st)
    return n


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "collect":
        cmd_collect()
    elif cmd == "decide":
        cmd_decide()
    elif cmd == "late":
        cmd_late()
    elif cmd == "verify":
        sys.exit(cmd_verify())
    elif cmd == "mark":
        log(f"{mark_posted(recent_rows())} listed news now in the Sheet")
    else:
        sys.exit(__doc__)
