"""owner 20 Nov: the YouTube details e-mail - every page posts its own news reels on its own YouTube channel by hand.
Twice a day (youtube.yml: 12:05 and 21:05 IST) ONE e-mail per page, through the Promo Hub (PROMO_URL / PROMO_KEY):
  the news reels posted on the page's Instagram since the last e-mail (gold rate and rasipalan left out), at most 10 a day per page
  (the most useful first: power cuts and alerts, then camps / jobs / schemes, then the rest, newest first) - the midday e-mail at most
  5, the night e-mail the rest of the 10. For each reel: YouTube title, description (with 📰 Source and 📅 date), tags, a suggested
  upload time and the video download link (owner 21 Nov "do not use Cloudinary": Instagram's own video link - download
  within 1 day).
Usage: python poster/youtube.py [am|pm]   (no argument: decided by the time)"""
import html as _h
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
IST = timezone(timedelta(hours=5, minutes=30))
E = _h.escape
DAY_MAX, AM_MAX = 10, 5
SKIP = re.compile(r"ராசிபலன்|GoldRate|தங்கம்.{0,25}விலை|Gold rate|வெள்ளி விலை", re.I)
RANK = [(3, re.compile(r"மின்\s*தடை|மின்தடை|power ?cut", re.I)),
        (2, re.compile(r"எச்சரிக்கை|கனமழை|வெள்ளம்|புயல்|விடுமுறை|போக்குவரத்து மாற்றம்|alert", re.I)),
        (1, re.compile(r"முகாம்|வேலைவாய்ப்பு|விண்ணப்ப|திட்டம்|ரயில்|பஸ்|தேர்வு|camp|job", re.I))]
PAGE_EN = {"namakkal": "Namakkal", "rasipuram": "Rasipuram", "coimbatore": "Coimbatore", "salem": "Salem", "erode": "Erode",
           "karur": "Karur", "tirupur": "Tirupur", "trichy": "Trichy"}


def log(*a):
    print("youtube:", *a, flush=True)


def window(slot, now):
    """am: last night 21:05 -> 12:05 today; pm: 12:05 -> 21:05 today (IST)"""
    d = now.astimezone(IST).replace(second=0, microsecond=0)
    if slot == "am":
        return (d - timedelta(days=1)).replace(hour=21, minute=5), d.replace(hour=12, minute=5)
    return d.replace(hour=12, minute=5), d.replace(hour=21, minute=5)


def rank(cap):
    for score, rx in RANK:
        if rx.search(cap or ""):
            return score
    return 0


def pick(items, n):
    """the n most useful: by rank, then newest"""
    return sorted(items, key=lambda m: (rank(m.get("caption")), m.get("timestamp") or ""), reverse=True)[:n]


def when(ts):
    return datetime.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).astimezone(IST)


TITLE_MAX = 70
SEARCH_WORD = {"crime": "crime news", "accident": "accident news", "power_cut": "power cut", "jobs": "jobs", "weather": "weather",
               "temple": "temple news", "politics": "politics", "civic": "news", "education": "education news", "poultry_agri": "agri news",
               "sports_culture": "sports news"}


def search_word(cap):
    """owner 25 Nov: the English search word for the title, from the news topic (the same topics the insights use)"""
    if re.search(r"ராசிபலன்", cap or ""):
        return "rasi palan today"
    if re.search(r"தங்கம்.{0,25}விலை|Gold rate|GoldRate", cap or "", re.I):
        return "gold rate today"
    try:
        import sys as _s, os as _o
        _s.path.insert(0, _o.path.join(_o.path.dirname(__file__), "..", "research_free"))
        import learned
        return SEARCH_WORD.get(learned.topic(cap or ""), "news")
    except Exception:
        return "news"


def details(m, page, uname):
    """YouTube title / description / tags from the Instagram caption (it already has the headline, 📰 Source and 📅 date)"""
    cap = m.get("caption") or ""
    lines = [x.strip() for x in cap.split("\n")]
    head = re.sub(r"^[^\w஀-௿]+", "", lines[0] if lines else "").strip()
    name = PAGE_EN.get(page, page.title())
    suffix = f" | {name} {search_word(cap)}"      # owner 25 Nov: an English search word (people search YouTube in English too)
    room = TITLE_MAX - len(suffix)
    title = (head if len(head) <= room else head[:room - 1].rstrip() + "…") + suffix      # owner 25 Nov: about 70 characters (Shorts feed)
    tags = [t.lstrip("#") for t in re.findall(r"#[^\s#]+", cap)][:12]
    kw_line = next((x for x in lines if x.startswith("🔎")), "")      # owner 26 Nov: the keyword line: last in the description + in the hidden Tags
    body = [x for x in lines[1:] if x and not x.startswith("#") and not x.startswith("🤝 Sponsored") and not x.startswith("🔎")]
    for kwd in [w.strip() for w in kw_line.lstrip("🔎").split(",") if w.strip()][:6]:
        if len(kwd) <= 30 and kwd not in tags:
            tags.append(kwd)
    src = next((x for x in body if x.startswith("📰 Source")), "")
    body = [x for x in body if x != src]
    date = when(m["timestamp"]).strftime("%d %b %Y")
    desc = "\n".join([f"#{name} #TamilNews #Shorts", "", head, ""] + body[:12] + ["", src or "", f"📅 {date}", "",      # owner 25 Nov: YouTube shows the first 3 hashtags above the title
                      f"🔔 Subscribe for daily {name} news", f"#{name}News #{name}360"] + (["", kw_line] if kw_line else [])).strip()      # owner 25 Nov: keep viewers on YouTube
    for extra in (f"{name} news", "Tamil news", f"{name} 360", "Shorts"):
        if extra not in tags:
            tags.append(extra)
    return {"title": title, "description": re.sub(r"\n{3,}", "\n\n", desc), "tags": ", ".join(tags[:15])}


def download_link(post, cap):
    """owner 21 Nov ("do not use Cloudinary"): no Cloudinary download link any more - the e-mail gives Instagram's own video link"""
    return ""


def times(slot, n, now):
    """suggested upload times, about an hour apart, never between 23:00 and 06:30"""
    t = now.astimezone(IST).replace(second=0, microsecond=0) + timedelta(minutes=25)
    out = []
    while len(out) < n:
        if t.hour >= 23 or t.hour < 6 or (t.hour == 6 and t.minute < 30):
            t = (t + timedelta(days=1 if t.hour >= 23 else 0)).replace(hour=6, minute=30)
        out.append(t.strftime("%d %b, %I:%M %p"))
        t += timedelta(minutes=60)
    return out


def email(page, label, uname, slot, chosen, now):
    tms = times(slot, len(chosen), now)
    part = "midday" if slot == "am" else "night"
    subject = f"[YouTube] {label} - {len(chosen)} reels to upload - {now.astimezone(IST):%d %b} ({part})"
    blocks, text = [], [subject, "Download within 1 day (Instagram's own video link).", ""]
    for i, (m, d, link) in enumerate(chosen, 1):
        dl = link or m.get("media_url") or m.get("permalink") or ""
        blocks.append(
            f"<div style='border:1px solid #ddd;border-radius:10px;padding:14px;margin:14px 0;font-family:Arial,sans-serif'>"
            f"<div style='font-size:13px;color:#888'>#{i} - upload at <b>{E(tms[i - 1])}</b> - "
            f"<a href='{E(m.get('permalink') or '')}'>Instagram post</a></div>"
            f"<div style='margin:8px 0'><a href='{E(dl)}' style='background:#FF0000;color:#fff;padding:8px 14px;border-radius:6px;"
            f"text-decoration:none;font-weight:bold'>⬇ Download video</a></div>"
            f"<div><b>Title</b> (copy):</div><pre style='white-space:pre-wrap;background:#f6f6f6;padding:8px'>{E(d['title'])}</pre>"
            f"<div><b>Description</b> (copy):</div><pre style='white-space:pre-wrap;background:#f6f6f6;padding:8px'>{E(d['description'])}</pre>"
            f"<div><b>Tags</b> (copy):</div><pre style='white-space:pre-wrap;background:#f6f6f6;padding:8px'>{E(d['tags'])}</pre></div>")
        text += [f"#{i}  upload at {tms[i - 1]}", f"Download: {dl}", f"Instagram: {m.get('permalink') or ''}", "TITLE:", d["title"],
                 "DESCRIPTION:", d["description"], "TAGS:", d["tags"], "-" * 40]
    html = (f"<div style='font-family:Arial,sans-serif'><h2 style='margin:0'>{E(label)} - YouTube</h2>"
            f"<p>{len(chosen)} news reels to upload as YouTube Shorts on the {E(label)} channel. "
            f"<b>Download within 1 day</b> (the link is kept 2 days).</p>" + "".join(blocks) + "</div>")
    return subject, "\n".join(text), html


def run(slot=None, now=None, send=True):
    import post
    import promo
    now = now or datetime.now(timezone.utc)
    slot = slot or ("am" if now.astimezone(IST).hour < 17 else "pm")
    a, b = window(slot, now)
    sent = 0
    for page, label in post.LABEL.items():
        try:
            token = post.bridge_get("token", page=page)["token"]
            uname = post.ig_account(token)[1]
            data = post.ig("GET", "me/media", token, fields="id,caption,media_type,permalink,timestamp,media_url", limit=50).get("data") or []
        except Exception as e:
            log(f"{page}: Instagram not read:", str(e)[:200])
            continue
        news = [m for m in data if m.get("media_type") == "VIDEO" and m.get("timestamp") and not SKIP.search(m.get("caption") or "")]
        if slot == "am":
            n = AM_MAX
        else:      # the night e-mail fills the day to 10: the midday e-mail took the best (at most 5) of last night 21:05 -> 12:05
            am_a, am_b = window("am", now)
            n = DAY_MAX - min(AM_MAX, len([m for m in news if am_a <= when(m["timestamp"]) < am_b]))
        mine = [m for m in news if a <= when(m["timestamp"]) < b]
        chosen = [(m, details(m, page, uname), download_link(post, m.get("caption"))) for m in pick(mine, max(0, n))]
        if not chosen:
            log(f"{page}: no news reels in this window")
            continue
        subject, text, html = email(page, label, uname, slot, chosen, now)
        if send and promo.enabled():
            promo.hub_post("digest", {"subject": subject, "text": text, "html": html})
            log(f"{page}: e-mail sent ({len(chosen)} reels)")
            sent += 1
        else:
            log(f"{page}: not sent (PROMO_URL / PROMO_KEY not set)\n{text}")
    return sent


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in ("am", "pm") else None)
