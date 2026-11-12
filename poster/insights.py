"""Daily: read each page's recent Reels + their insights from Instagram, keep a history, and write research_free/learned.json
(topic weights, best hours, strong openings, average watch time). Collection of news uses it only to ORDER stories and to hint the writer."""
import json, os, statistics, sys, datetime
HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "research_free"))
import post, learned

MET = ["reach", "views", "saved", "shares", "total_interactions", "ig_reels_avg_watch_time"]
HIST = os.path.join(HERE, "insights", "history.json")
MIN_PER_TOPIC, MIN_POSTS = 3, 12
IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))


def metrics(mid, tok):
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
    for page in ("coimbatore",):
        try:
            tok = post.bridge_get("token", page=page)["token"]
            uid, _ = post.ig_account(tok)
            items = post.ig("GET", f"{uid}/media", tok, fields="id,caption,timestamp,media_product_type", limit=50).get("data", [])
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
        except Exception as e:
            print(page, "read failed:", str(e)[:200]); continue
        for i in items:
            if i.get("media_product_type") != "REELS":
                continue
            cap = i.get("caption") or ""
            age_h = (datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.fromisoformat(i["timestamp"].replace("+0000", "+00:00"))).total_seconds() / 3600
            old = hist.get(i["id"])
            if old and old.get("final"):
                continue
            row = {"page": page, "t": i["timestamp"], "caption": cap[:400], "topic": learned.topic(cap)}
            row.update(metrics(i["id"], tok))
            row["final"] = age_h > 72            # numbers settle after ~3 days
            hist[i["id"]] = row
    os.makedirs(os.path.dirname(HIST), exist_ok=True)
    json.dump(hist, open(HIST, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    rows = [h for h in hist.values() if h.get("reach") is not None and (h.get("reach") or 0) > 0]
    # relative score = post score / the page's median (one page: Coimbatore 360)
    for pg in ("coimbatore",):
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


main()
