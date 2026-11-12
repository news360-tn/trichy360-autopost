"""Daily rasipalan carousel - collects at 7:31 AM IST, writes, checks, renders and posts at once (one post per page per day).

  PAGE=rasipuram  python rasipalan/rasi_daily.py   -> இராசிபுரம் 360, temple design, நாமக்கல் 360 invited as collaborator
  PAGE=coimbatore python rasipalan/rasi_daily.py   -> கோயம்புத்தூர் 360, calendar design, no collaborator
  DRY_RUN=1 -> everything except publishing (slides kept in out/rasipalan for review)
Environment: BRIDGE_URL, BRIDGE_KEY (page tokens), CLOUDINARY_CLOUD, CLOUDINARY_PRESET, model keys (see research_free/llm.py)."""
import json, os, sys, time
from datetime import datetime
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import rasi_panchang as P      # noqa: E402
import rasi_festivals as festivals, rasi_sources as sources, rasi_writer as writer, rasi_render as render      # noqa: E402

PAGE = os.environ.get("PAGE", "rasipuram")
DRY = os.environ.get("DRY_RUN", "") in ("1", "true", "yes")
START_AT = os.environ.get("START_AT", "07:31")      # owner 31 Oct: collect sharply at 7:31 AM
# owner 1 Nov: never miss a day - post as soon as the sources have it. 2 sources wanted; after ONE_SOURCE_AT one source is enough;
# trying continues until GIVE_UP_AT (only then the run fails and GitHub e-mails the owner)
ONE_SOURCE_AT = os.environ.get("ONE_SOURCE_AT", "09:30")
GIVE_UP_AT = os.environ.get("GIVE_UP_AT", "12:30")
MIN_SOURCES = int(os.environ.get("MIN_SOURCES", "2"))
REPOST = os.environ.get("REPOST", "") == "1"      # by hand: today's post was deleted by the owner - post it again (state file ignored)
FORCE_DATE = os.environ.get("RASI_DATE", "")      # testing only: YYYY-MM-DD
PAGES = {
    "rasipuram": {"brand": "இராசிபுரம் 360", "town": "இராசிபுரம்", "design": "temple", "logo": "logo_rasipuram.png",
                  "collab": "namakkal.360", "tags": ["#ராசிபலன்", "#RasiPalan", "#இன்றையராசிபலன்", "#Namakkal360", "#Rasipuram360"]},
    "trichy": {"brand": "திருச்சி 360", "town": "திருச்சி", "design": "calendar", "logo": "logo_trichy.png",      # SALEM: add kit/logo_trichy.png
              "collab": "", "tags": ["#ராசிபலன்", "#RasiPalan", "#இன்றையராசிபலன்", "#Trichy", "#Trichy360"]},
}
FEST_TAG = {"diwali": "#Deepavali", "pongal": "#Pongal", "christmas": "#Christmas", "islamic": "#Eid", "murugan": "#Murugan",
            "karthigai": "#KarthigaiDeepam", "newyear": "#NewYear", "tamilnewyear": "#TamilNewYear", "vinayagar": "#VinayagarChathurthi",
            "navaratri": "#AyudhaPooja", "perumal": "#Perumal", "shiva": "#Shivaratri", "krishna": "#KrishnaJayanthi", "national": "#India"}
STATE = HERE / "state" / f"{PAGE}.json"
OUT = ROOT / "out" / "rasipalan" / PAGE
IG = "https://graph.instagram.com"


def log(*a):
    print(datetime.now(P.IST).strftime("%H:%M:%S"), *a, flush=True)


def bridge_get(action, **params):
    r = requests.get(os.environ["BRIDGE_URL"], params={"action": action, "key": os.environ["BRIDGE_KEY"], **params}, timeout=120)
    r.raise_for_status()
    d = r.json()
    if not d.get("ok"):
        raise RuntimeError(f"bridge {action}: {d.get('error')}")
    return d


def ig(method, path, token, **params):
    params["access_token"] = token
    r = requests.request(method, f"{IG}/{path}", params=params if method == "GET" else None, data=params if method == "POST" else None, timeout=120)
    d = r.json()
    if r.status_code >= 400 or "error" in d:
        raise RuntimeError(f"Instagram {path}: {d.get('error', d)}")
    return d


def wait_ready(cid, token, minutes=6):
    end = time.time() + minutes * 60
    while time.time() < end:
        st = ig("GET", cid, token, fields="status_code").get("status_code")
        if st == "FINISHED":
            return
        if st in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"container {cid} {st}")
        time.sleep(5)
    raise RuntimeError(f"container {cid} not ready")


def upload(path):
    with open(path, "rb") as f:
        r = requests.post(f"https://api.cloudinary.com/v1_1/{os.environ['CLOUDINARY_CLOUD']}/image/upload",
                          data={"upload_preset": os.environ["CLOUDINARY_PRESET"], "folder": "rasipalan"}, files={"file": f}, timeout=300)
    r.raise_for_status()
    return r.json()["secure_url"]


def clock(hhmm, day):
    h, m = map(int, hhmm.split(":"))
    return datetime(day.year, day.month, day.day, h, m, tzinfo=P.IST)


def date_line(p):
    return f"இன்றைய ராசி பலன் | {p['date_ta']}, {p.get('weekday_full') or p['weekday'] + 'க்கிழமை'} ({p['tamil_month']} {p['tamil_day']})"


def already_posted(day, p, token=None):
    try:
        if REPOST:
            raise ValueError("repost: state file ignored")
        st = json.loads(STATE.read_text(encoding="utf-8"))
        if st.get("date") == day.isoformat() and st.get("media_id"):
            return f"state file: posted {st.get('permalink')}"
    except Exception:
        pass
    if token:
        try:
            uid = ig("GET", "me", token, fields="user_id")["user_id"]
            for m in ig("GET", f"{uid}/media", token, fields="caption,timestamp,permalink", limit=15).get("data", []):
                if f"இன்றைய ராசி பலன் | {p['date_ta']}," in (m.get("caption") or ""):      # (day-name spelling changed 1 Nov)
                    return f"Instagram already has today's post {m.get('permalink')}"
        except Exception as e:
            log("could not read recent posts:", str(e)[:150])
    return ""


def hook(rs):
    best = [r["rasi"] for r in rs if r["stars"] == 5][:3] or [r["rasi"] for r in rs if r["stars"] == 4][:2]
    return "இன்று அதிர்ஷ்டம்: " + ", ".join(best) if best else "12 ராசிகளுக்கும் இன்றைய பலன்"


def caption(cfg, p, fest, notes, rs):
    L = [f"🔆 {date_line(p)}"]
    if fest:
        L.append(f"🪔 {render.greeting(fest)}!" if fest["theme"] not in render.SOLEMN else f"🕊️ {fest['name']}")
    L.append(f"⭐ {hook(rs)}")
    L.append(f"⚠️ சந்திராஷ்டமம்: {p['chandrashtamam']}")
    if notes:
        L.append("📿 இன்று: " + " · ".join(notes))
    L.append("")
    for i, r in enumerate(rs):
        L.append(f"{render.GLYPH[i]} {r['rasi']} {'⭐' * r['stars']} – {r['work']}")
    L += ["", f"✨ நல்ல நேரம்: காலை {p['nalla_morning']}, மாலை {p['nalla_evening']}" if p.get("nalla_morning") else "",
          f"🕘 ராகு காலம் {p['rahu']} | எமகண்டம் {p['emagandam']} | குளிகை {p['kuligai']}",
          "👉 ஸ்வைப் செய்து உங்கள் ராசியின் முழு பலனைப் பாருங்கள். குடும்பத்தினருடன் பகிருங்கள்.",
          f"Today Rasi Palan in Tamil | {datetime.fromisoformat(p['date']).strftime('%d %B %Y')} | Daily Horoscope", ""]
    tags = list(cfg["tags"])
    if fest and FEST_TAG.get(fest["theme"]):
        tags = tags[:2] + [FEST_TAG[fest["theme"]]] + tags[3:]      # Instagram: at most 5 tags (owner rule); page tag stays last
    L.append(" ".join(tags[:5]))
    return "\n".join(L)


def publish(token, urls, cap, collab):
    uid = ig("GET", "me", token, fields="user_id")["user_id"]
    kids = []
    for i, u in enumerate(urls, 1):
        kids.append(ig("POST", f"{uid}/media", token, image_url=u, is_carousel_item="true")["id"])
    for k in kids:
        wait_ready(k, token)
    prm = dict(media_type="CAROUSEL", children=",".join(kids), caption=cap)
    collab_ok = False
    if collab:
        try:
            cid = ig("POST", f"{uid}/media", token, collaborators=json.dumps([collab]), **prm)["id"]
            collab_ok = True
        except RuntimeError as e:
            log("collaborator refused, posting without it:", str(e)[:200])
            cid = ig("POST", f"{uid}/media", token, **prm)["id"]
    else:
        cid = ig("POST", f"{uid}/media", token, **prm)["id"]
    wait_ready(cid, token)
    mid = ig("POST", f"{uid}/media_publish", token, creation_id=cid)["id"]
    link = ig("GET", mid, token, fields="permalink").get("permalink", "")
    return mid, link, collab_ok


def accept_collab(mid):
    """best effort: the Namakkal 360 account accepts the invite itself so the post shows on both pages"""
    try:
        tok = bridge_get("token", page="namakkal")["token"]
        uid = ig("GET", "me", tok, fields="user_id")["user_id"]
        ig("POST", f"{uid}/collaboration_invites", tok, media_id=mid, accept="true")
        log("Namakkal 360 accepted the collaboration")
    except Exception as e:
        log("collaboration not accepted automatically (accept it in the Namakkal 360 app):", str(e)[:200])


def main():
    cfg = PAGES[PAGE]
    now = datetime.now(P.IST)
    day = datetime.fromisoformat(FORCE_DATE).date() if FORCE_DATE else now.date()
    p = P.compute(day, PAGE)
    log(f"{cfg['brand']} - {date_line(p)}{' (DRY RUN)' if DRY else ''}")
    token = None
    if not DRY:
        token = bridge_get("token", page=PAGE)["token"]
    done = already_posted(day, p, token)
    if done and REPOST:      # wait (max 2 hours) until the owner has deleted the old post, then post again
        for _ in range(60):
            log("REPOST: waiting for the old post to be deleted -", done)
            time.sleep(120)
            done = already_posted(day, p, token)
            if not done:
                break
    if done:
        log("already posted today -", done)
        return 0
    start = clock(START_AT, day)
    if not FORCE_DATE and datetime.now(P.IST) < start:
        wait = (start - datetime.now(P.IST)).total_seconds()
        log(f"waiting {int(wait)} s until {START_AT}")
        time.sleep(max(0, wait))
    got = []
    while True:
        log("collecting today's rasipalan")
        got = sources.collect(day, log)
        t = datetime.now(P.IST)
        need = MIN_SOURCES if t < clock(ONE_SOURCE_AT, day) else 1
        if len(got) >= need or (FORCE_DATE and got):
            break
        if FORCE_DATE or t >= clock(GIVE_UP_AT, day):
            raise SystemExit(f"no source had today's rasipalan by {GIVE_UP_AT} - nothing posted")
        log(f"only {len(got)} source(s) so far (need {need}) - trying again in 4 minutes")
        time.sleep(240)
    if len(got) < MIN_SOURCES:
        log(f"posting with {len(got)} source - the others did not publish today's rasipalan in time")
    art = sources.panchang_article(day, log)
    sources.panchang_extras(art, p, log)
    sources.panchang_vakya(art, p, log)      # owner 1 Nov: திதி / நட்சத்திரம் as Tamil daily calendars print them
    fest, notes, why = festivals.today(day, p, art)
    if why:
        log(why)
    if festivals.table_runs_out_soon(day):
        log("NOTE: festivals.py OFFICIAL table ends soon - add next year's Tamil Nadu Government holiday list")
    rs = writer.write(got, p["chandrashtamam"], log)
    ctx = {"p": p, "fest": fest, "rasis": rs, "logo": f"file://{ROOT / 'kit' / cfg['logo']}", "brand": cfg["brand"], "hook": hook(rs),
           "prows": render.panchang_rows(p, cfg["town"])}
    jpgs = render.render(cfg["design"], ctx, OUT)
    cap = caption(cfg, p, fest, notes, rs)
    (OUT / "caption.txt").write_text(cap, encoding="utf-8")
    (OUT / "content.json").write_text(json.dumps({"sources": [g["url"] for g in got], "festival": fest, "notes": notes, "rasis": rs,
                                                  "panchang": p}, ensure_ascii=False, indent=1), encoding="utf-8")
    log("caption:\n" + cap)
    if DRY:
        log(f"DRY RUN: {len(jpgs)} slides in {OUT} - not posted")
        return 0
    if already_posted(day, p, token):      # another run finished meanwhile
        log("already posted meanwhile - stop")
        return 0
    urls = [upload(j) for j in jpgs]
    mid, link, collab_ok = publish(token, urls, cap, cfg["collab"])
    log(f"POSTED {link} (collaborator {'invited' if collab_ok else 'none'})")
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({"date": day.isoformat(), "media_id": mid, "permalink": link, "posted_at": datetime.now(P.IST).isoformat(),
                                 "festival": fest, "sources": [g["name"] for g in got]}, ensure_ascii=False, indent=1), encoding="utf-8")
    if collab_ok:
        accept_collab(mid)
    try:      # owner 2 Nov: the same carousel + a story also go to the page's Facebook page (never touches the Instagram post)
        sys.path.insert(0, str(ROOT / "poster"))
        import facebook
        facebook.share(PAGE, f"rasipalan-{day.isoformat()}", "photos", urls, cap, cfg["tags"][-1], tags=cfg["tags"][:2], always=True)      # owner 11 Nov: the daily rasipalan always goes to Facebook
    except Exception as e:
        log("Facebook step skipped:", str(e)[:150])
    return 0


if __name__ == "__main__":
    sys.exit(main())
