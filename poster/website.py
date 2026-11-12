"""Coimbatore 360 website (OFF for now - no site yet): when switched on, every posted story is sent there with all its details.

    send(row, reel_link)          called by the posting job right after a reel is posted
    python poster/website.py backfill [--from RN-1]   one-time: all posted stories from the Sheet, oldest first

The website files each story under its taluk / town / news type itself. A website problem never stops Instagram posting:
send() only logs and returns False. Needs WEBSITE_INGEST_KEY (GitHub secret) AND WEBSITE_URL; without them send() does nothing at all
(no translation, no network call) - the workflows do not pass them."""
import datetime, json, os, re, sys, time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research_free"))
URL = (os.environ.get("WEBSITE_URL") or "").rstrip("/")      # no Coimbatore 360 site yet
IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}

EN_SYSTEM = """You translate Tamil local news from Coimbatore district into clear, simple Indian English for a news website.
Keep every fact exactly: names, places, numbers, amounts, dates and times. Do not add anything. Use the English spelling of
Coimbatore place names (Pollachi, Mettupalayam, Sulur, Valparai, Gandhipuram, Peelamedu ...). Leave out any "follow our page" line.
Return ONLY JSON: {"title_en": "headline, max 110 characters", "story_en": "the full story as plain sentences"}"""


def log(*a):
    print(time.strftime("%H:%M:%S"), "[website]", *a, flush=True)


def filed_iso(row):
    """'22 Oct 2026, 10:26' (researched) or the published date -> ISO time in India"""
    m = re.search(r"(\d{1,2})\s+([A-Za-z]{3})[a-z]*\s+(\d{4}),?\s+(\d{1,2}):(\d{2})", str(row.get("researched") or ""))
    if m and m.group(2).lower() in MONTHS:
        d = datetime.datetime(int(m.group(3)), MONTHS[m.group(2).lower()], int(m.group(1)), int(m.group(4)), int(m.group(5)), tzinfo=IST)
        return d.isoformat()
    p = str(row.get("published") or "")
    return p if re.match(r"\d{4}-\d{2}-\d{2}", p) else datetime.datetime.now(IST).isoformat(timespec="minutes")


def images_of(row):
    try:
        imgs = json.loads(row.get("images") or "[]")
    except Exception:
        imgs = []
    return [u for u in imgs if isinstance(u, str) and u.startswith("https://") and "NOIMAGE" not in u][:6]


def english(row):
    """English headline + story (free models first, Claude as the backup). {} when it cannot be made: the site then shows Tamil."""
    if row.get("_en"):
        return row["_en"]
    try:
        import llm
    except Exception as e:
        log("translator not available:", e)
        return {}
    user = f"Headline: {row.get('headline_ta', '')}\nEnglish headline idea: {row.get('headline_en', '')}\n\nStory:\n{row.get('reel_script', '')}"
    for ask in (lambda: llm.ask_json(EN_SYSTEM, user), lambda: llm.ask_claude(EN_SYSTEM, user, max_tokens=2500)):
        try:
            data, _ = ask()
            if isinstance(data, dict) and len(str(data.get("story_en", ""))) > 40:
                return {"title_en": str(data.get("title_en") or row.get("headline_en") or "")[:140], "story_en": str(data["story_en"])}
        except Exception as e:
            log("translation try failed:", str(e)[:120])
    return {}


def payload(row, reel_link="", en=None):
    """one Sheet row -> what the website's /api/ingest expects"""
    en = en if en is not None else {}
    return {
        "story_id": row.get("story_id", ""), "headline_ta": row.get("headline_ta", ""),
        "headline_en": en.get("title_en") or row.get("headline_en", ""), "story_en": en.get("story_en", ""),
        "reel_script": row.get("reel_script", ""), "caption": row.get("caption", ""),
        "location": row.get("location", ""), "category": row.get("category", ""), "images": images_of(row),
        "reel_link": reel_link or row.get("reel_link", "") or row.get("trichy_link", ""),
        "source": row.get("source", ""), "published": row.get("published", ""), "filed_at": filed_iso(row),
    }


def enabled():
    """the website step runs only when both WEBSITE_INGEST_KEY and WEBSITE_URL are set"""
    return bool(os.environ.get("WEBSITE_INGEST_KEY")) and bool(URL)


def post(items):
    key = os.environ.get("WEBSITE_INGEST_KEY")
    if not key or not URL:
        log("website off (WEBSITE_INGEST_KEY / WEBSITE_URL not set) - story not sent to the website")
        return None
    for k in range(3):
        try:
            r = requests.post(URL + "/api/ingest", json=items, timeout=60,
                              headers={"authorization": "Bearer " + key, "user-agent": "coimbatore360-pipeline"})
            if r.status_code == 200:
                return r.json()
            log("website answered", r.status_code, r.text[:200])
            if r.status_code in (400, 401, 403):
                return None
        except Exception as e:
            log("website not reachable:", str(e)[:150])
        time.sleep(5 * (k + 1))
    return None


def send(row, reel_link=""):
    """after a reel is posted: the story goes to the website at once. Never raises. Does nothing when the website is off."""
    if not enabled():
        return False
    try:
        res = post([payload(row, reel_link, english(row))])
        ok = bool(res and row.get("story_id") in res.get("saved", []))
        log("story on the website" if ok else "story NOT on the website (posting is not affected)", row.get("story_id"))
        return ok
    except Exception as e:
        log("website step skipped:", str(e)[:200])
        return False


def backfill(start="RN-1"):
    """every posted story from the Sheet, oldest first, in small groups"""
    if not enabled():
        log("website off (WEBSITE_INGEST_KEY / WEBSITE_URL not set) - nothing to backfill")
        return 0
    sys.path.insert(0, str(ROOT / "poster"))
    import post as P
    rows = P.bridge_get("posted_rows").get("rows", [])
    num = lambda r: int(re.sub(r"\D", "", r.get("story_id", "")) or 0)
    rows = sorted([r for r in rows if num(r) >= num({"story_id": start})], key=num)
    log(len(rows), "posted stories to send, from", start)
    sent = 0
    for i in range(0, len(rows), 10):
        group = [payload(r, "", english(r)) for r in rows[i:i + 10]]
        res = post(group)
        sent += len((res or {}).get("saved", []))
        log(f"{min(i + 10, len(rows))}/{len(rows)} done, {sent} on the website")
    return sent


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "backfill":
        frm = sys.argv[sys.argv.index("--from") + 1] if "--from" in sys.argv else "RN-1"
        n = backfill(frm)
        print(f"backfill finished: {n} stories on the website")
    else:
        print(__doc__)
