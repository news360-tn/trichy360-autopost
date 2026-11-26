"""Daily: read each page's recent Reels + their insights from Instagram, keep a history, and write research_free/learned.json
(topic weights, best hours, strong openings, average watch time). Collection of news uses it only to ORDER stories and to hint the writer.
19 Nov: every post of the last 8 days is read, final numbers at 7 days (was the latest 50 = about 2 days on a 20-posts-a-day page, so almost no reel got its final
numbers); carousels (rasipalan, gold rate) are kept too but never change learned.json; reach at about 24 h and 48 h is kept for fair
before / after comparisons; once a day the page's follower / non-follower reach and follower cities go to insights/account.json."""
import json, os, statistics, sys, datetime
HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "research_free"))
import post, learned

MET = ["reach", "views", "saved", "shares", "total_interactions", "ig_reels_avg_watch_time"]
HIST = os.path.join(HERE, "insights", "history.json")
ACCOUNT = os.path.join(HERE, "insights", "account.json")
MET_FEED = ["reach", "views", "saved", "shares", "total_interactions"]      # carousels / photos have no watch time
WINDOW_DAYS, FINAL_H, DAILY_AFTER_H, REREAD_H = 8, 168, 72, 20      # read 8 days; final after 7; after 3 days at most once in 20 h
MAX_READS = 120      # posts read per page per run, newest first (the first run after the change reads about 190; the rest follow next run)
SAME_AGE = (("r24", 20, 32), ("r48", 44, 56))      # numbers kept when a post is about 1 day / 2 days old (runs are 4 h apart)
MIN_PER_TOPIC, MIN_POSTS = 3, 12
IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))


def metrics(mid, tok, MET=MET):      # 19 Nov: carousels pass MET_FEED (no watch time)
    """owner 2 Nov: insights are read before EVERY collection round - all metrics in ONE call per reel (was 6), so the extra reads
    stay light for Instagram's API (posting uses the same allowance). One metric at a time only if the combined call is refused."""
    try:
        d = post.ig("GET", f"{mid}/insights", tok, metric=",".join(MET)).get("data") or []
        got = {m: None for m in MET}
        for x in d:
            v = (x.get("values") or [{}])[0].get("value")
            if v is None and isinstance(x.get("total_value"), dict):
                v = x["total_value"].get("value")
            got[x.get("name")] = v
        if any(v is not None for v in got.values()):
            return {m: got.get(m) for m in MET}
    except Exception:
        pass
    out = {}
    for m in MET:
        try:
            v = (post.ig("GET", f"{mid}/insights", tok, metric=m).get("data") or [{}])[0].get("values") or [{}]
            out[m] = v[0].get("value")
        except Exception:
            out[m] = None
    return out


def _when(ts):
    return datetime.datetime.fromisoformat(str(ts).replace("+0000", "+00:00").replace("Z", "+00:00"))


def recent_media(uid, tok, days=WINDOW_DAYS, max_pages=6, now=None):
    """19 Nov: every post of the last `days` days, newest first (Instagram gives 50 per page; the next page is asked for only while
    the oldest post seen is still inside the window, at most max_pages pages)"""
    cut = (now or datetime.datetime.now(datetime.timezone.utc)) - datetime.timedelta(days=days)
    fields = "id,caption,timestamp,media_product_type,permalink"      # owner 26 Nov: the post's own link, for the team dashboard
    d = post.ig("GET", f"{uid}/media", tok, fields=fields, limit=50)
    items = list(d.get("data") or [])
    for _ in range(max_pages - 1):
        after = ((d.get("paging") or {}).get("cursors") or {}).get("after")
        if not items or not after or not (d.get("paging") or {}).get("next") or _when(items[-1]["timestamp"]) < cut:
            break
        try:
            d = post.ig("GET", f"{uid}/media", tok, fields=fields, limit=50, after=after)
        except Exception as e:      # a later page failing never loses the posts already read
            print("older posts not read this run:", str(e)[:150])
            break
        items += list(d.get("data") or [])
    return [i for i in items if _when(i["timestamp"]) >= cut]


def _results(d):
    """the breakdown results of one /insights answer (total_value form), [] when there are none"""
    tv = ((d.get("data") or [{}])[0].get("total_value") or {}) if d.get("data") else {}
    return ((tv.get("breakdowns") or [{}])[0].get("results") or []), tv.get("value")


def account_insights(uid, tok, page, now=None):
    """19 Nov: once a day - people reached who follow the page vs who do not (the answer to "why do my followers not see my reels")
    and the followers' cities. A metric Instagram refuses (new page, permission) is noted and skipped; posting is never touched."""
    try:
        try:
            acc = json.load(open(ACCOUNT, encoding="utf-8"))
        except Exception:
            acc = {}
        day = (now or datetime.datetime.now(IST)).date().isoformat()
        if (acc.get(day) or {}).get(page):
            return acc[day][page]
        out = {}
        try:
            res, total = _results(post.ig("GET", f"{uid}/insights", tok, metric="reach", period="day", metric_type="total_value",
                                          breakdown="follow_type"))
            out["reach"] = total
            out["reach_by_follow_type"] = {str((r.get("dimension_values") or ["?"])[0]): r.get("value") for r in res}
        except Exception as e:
            out["reach_error"] = str(e)[:160]
        try:
            res, _ = _results(post.ig("GET", f"{uid}/insights", tok, metric="follower_demographics", period="lifetime",
                                      metric_type="total_value", breakdown="city"))
            top = sorted(res, key=lambda r: -(r.get("value") or 0))[:15]
            out["follower_cities"] = {str((r.get("dimension_values") or ["?"])[0]): r.get("value") for r in top}
        except Exception as e:
            out["cities_error"] = str(e)[:160]
        acc.setdefault(day, {})[page] = out
        os.makedirs(os.path.dirname(ACCOUNT), exist_ok=True)
        json.dump(acc, open(ACCOUNT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(page, "account insights:", json.dumps(out, ensure_ascii=False)[:300])
        return out
    except Exception as e:      # never stop the insights run for this
        print(page, "account insights skipped:", str(e)[:150])
        return {}


def read_row(i, page, tok, old, now):
    """the history row of one post, or None when it need not be read this run (final, or 3-7 days old and read in the last 20 h)"""
    kind = i.get("media_product_type")
    if kind not in ("REELS", "FEED"):
        return None
    age_h = (now - _when(i["timestamp"])).total_seconds() / 3600
    if old and old.get("final"):
        return None
    if old and age_h > DAILY_AFTER_H and old.get("read") and (now - _when(old["read"])).total_seconds() / 3600 < REREAD_H:
        return None
    cap = i.get("caption") or ""
    row = {"page": page, "t": i["timestamp"], "caption": cap[:400], "topic": learned.topic(cap)}
    if kind == "FEED":
        row["type"] = "FEED"
    row.update(metrics(i["id"], tok, MET if kind == "REELS" else MET_FEED))
    row["final"] = age_h > FINAL_H
    row["read"] = now.isoformat(timespec="minutes")
    for key, lo, hi in SAME_AGE:
        if old and old.get(key):
            row[key] = old[key]
        elif lo <= age_h < hi and row.get("reach") is not None:
            row[key] = {"age_h": round(age_h, 1), "reach": row.get("reach"), "shares": row.get("shares"), "saved": row.get("saved"),
                        "watch_ms": row.get("ig_reels_avg_watch_time")}
    return row


def score(h):
    """what we want people to do: watch it through, save it, share it, react. Weighted per reach."""
    reach = max(h.get("reach") or 0, 1)
    return (10 * (h.get("shares") or 0) + 6 * (h.get("saved") or 0) + 2 * (h.get("total_interactions") or 0)) / reach * 100 \
        + (h.get("ig_reels_avg_watch_time") or 0) / 1000.0


def main():
    try:
        hist = json.load(open(HIST, encoding="utf-8"))
    except Exception:
        hist = {}
    for page in ("trichy",):
        try:
            tok = post.bridge_get("token", page=page)["token"]
            uid, _ = post.ig_account(tok)
            items = recent_media(uid, tok)      # 19 Nov: 8 days (was the latest 50 posts)
            try:      # owner 2 Nov (review): followers per page per day - the one number that shows whether a change grows the page
                acc = post.ig("GET", uid, tok, fields="followers_count,media_count")
                fpath = os.path.join(HERE, "insights", "followers.json")
                try:
                    fol = json.load(open(fpath, encoding="utf-8"))
                except Exception:
                    fol = {}
                fol.setdefault(datetime.datetime.now(IST).date().isoformat(), {})[page] = {"followers": acc.get("followers_count"), "posts": acc.get("media_count")}
                os.makedirs(os.path.dirname(fpath), exist_ok=True)
                json.dump(fol, open(fpath, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
                print(page, "followers:", acc.get("followers_count"))
            except Exception as e:
                print(page, "followers not read:", str(e)[:150])
            account_insights(uid, tok, page)      # 19 Nov: follower / non-follower reach + follower cities, once a day
        except Exception as e:
            print(page, "read failed:", str(e)[:200]); continue
        now, reads = datetime.datetime.now(datetime.timezone.utc), 0
        for i in items:
            if reads >= MAX_READS:
                print(page, f"read {reads} posts this run - the older ones follow next run")
                break
            row = read_row(i, page, tok, hist.get(i["id"]), now)
            if row:
                hist[i["id"]] = row
                reads += 1
            if i.get("permalink") and i["id"] in hist:      # owner 26 Nov: also for posts that are already final (not read again)
                hist[i["id"]]["permalink"] = i["permalink"]
    os.makedirs(os.path.dirname(HIST), exist_ok=True)
    json.dump(hist, open(HIST, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    rows = [h for h in hist.values() if h.get("type", "REELS") == "REELS" and h.get("reach") is not None and (h.get("reach") or 0) > 0]      # learned.json: reels only
    # relative score = post score / the page's median (one page: Trichy 360)
    for pg in ("trichy",):
        sc = [score(h) for h in rows if h["page"] == pg]
        med = statistics.median(sc) if sc else 1
        for h in rows:
            if h["page"] == pg:
                h["rel"] = score(h) / (med or 1)
    out = {"updated": datetime.datetime.now(IST).isoformat(timespec="minutes"), "posts_measured": len(rows)}
    if len(rows) >= MIN_POSTS:
        tw, by = {}, {}
        for h in rows:
            h["topic"] = learned.topic(h["caption"])      # topics of older posts follow the current topic list (28 Oct: power_cut, jobs split out)
            by.setdefault(h["topic"], []).append(h["rel"])
        for t, v in by.items():
            if t != "other" and len(v) >= MIN_PER_TOPIC:
                m = statistics.median(v)
                tw[t] = round(max(-0.5, min(1.5, (m - 1.0) * 2)), 2)      # +1.5 max, -0.5 min: public-service news (weather, power cuts) is never buried the page median (clamped)
        out["topic_weight"] = tw
        out["topic_n"] = {t: len(v) for t, v in by.items() if t != "other"}      # owner 14 Nov: reels measured per topic (learned.TRUST_N)
        hours = {}
        for h in rows:
            hr = datetime.datetime.fromisoformat(h["t"].replace("+0000", "+00:00")).astimezone(IST).hour
            hours.setdefault(hr, []).append(h["rel"])
        out["best_hours_ist"] = [k for k, v in sorted(hours.items(), key=lambda kv: -statistics.median(kv[1])) if len(v) >= 2][:4]
        top = sorted(rows, key=lambda h: -h["rel"])[:6]
        out["top_openings"] = [h["caption"].split("\n")[0][:80] for h in top if h["rel"] > 1.2][:4]
        aw = [h["ig_reels_avg_watch_time"] for h in rows if h.get("ig_reels_avg_watch_time")]
        out["avg_watch_s"] = round(statistics.mean(aw) / 1000, 1) if aw else None
        out["best_topics"] = sorted(tw, key=lambda k: -tw[k])[:3]
        out["weak_topics"] = sorted(tw, key=lambda k: tw[k])[:2]
    json.dump(out, open(os.path.join(HERE, "..", "research_free", "learned.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False)[:1500])


if __name__ == "__main__":
    main()
