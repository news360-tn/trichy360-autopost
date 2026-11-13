"""Today's Chennai (Tamil Nadu) gold and silver rate from several public pages.

Owner 14 Nov: real data only. A rate is used only when at least 2 pages show TODAY's date and the same 22K gold rate
(silver: the same per-gram rate). Every page is read as plain text, so a small layout change on one site does not break the others.
collect(day, log) -> {"gold": {...} or None, "silver": {...} or None, "pages": [per-page results for the log]}"""
import re
import html as htmllib
from collections import Counter

import requests

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
      "Accept-Language": "en-IN,en;q=0.9,ta;q=0.8"}

GOLD_PAGES = [
    ("GoodReturns", "https://www.goodreturns.in/gold-rates/chennai.html"),
    ("Groww", "https://groww.in/gold-rates/gold-rate-today-in-chennai"),
    ("RateToday", "https://ratetoday.co.in/gold/chennai"),
    ("BankBazaar", "https://www.bankbazaar.com/gold-rate-chennai.html"),
]
SILVER_PAGES = [
    ("GoodReturns", "https://www.goodreturns.in/silver-rates/chennai.html"),
    ("Groww", "https://groww.in/silver-rates/silver-rate-today-in-chennai"),
    ("RateToday", "https://ratetoday.co.in/silver/chennai"),
    ("BankBazaar", "https://www.bankbazaar.com/silver-rate-chennai.html"),
]

MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
NUM = r"([0-9]{1,2}(?:,[0-9]{2})*,?[0-9]{3}|[0-9]{2,6})(?:\.[0-9]+)?"      # 12,695 / 1,01,560 / 12695 / 195 (decimals dropped)
RS = r"(?:₹|rs\.?|inr)\s*"


def text_of(raw):
    raw = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", raw)
    t = htmllib.unescape(re.sub(r"(?s)<[^>]+>", " ", raw))
    return re.sub(r"\s+", " ", t)


def fetch(url, timeout=25):
    r = requests.get(url, headers=UA, timeout=timeout)
    r.raise_for_status()
    return text_of(r.text)


def num(s):
    return int(s.replace(",", ""))


def page_dates(t):
    """every date written on the page (13 November 2026 / 13 Nov 2026 / November 13, 2026 / 13.11.2026)"""
    out = set()
    for d, m, y in re.findall(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]{3,9})\.?,?\s+(20\d\d)\b", t):
        if m[:3].lower() in MONTHS:
            out.add((int(y), MONTHS[m[:3].lower()], int(d)))
    for m, d, y in re.findall(r"\b([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(20\d\d)\b", t):
        if m[:3].lower() in MONTHS:
            out.add((int(y), MONTHS[m[:3].lower()], int(d)))
    for d, m, y in re.findall(r"\b(\d{1,2})[./-](\d{1,2})[./-](20\d\d)\b", t):
        if 1 <= int(m) <= 12:
            out.add((int(y), int(m), int(d)))
    return out


def has_today(t, day):
    return (day.year, day.month, day.day) in page_dates(t[:6000]) or (day.year, day.month, day.day) in page_dates(t)


def first(t, patterns, lo, hi):
    for p in patterns:
        for m in re.finditer(p, t, re.I):
            v = num(m.group(1))
            if lo <= v <= hi:
                return v
    return None


def parse_gold(t):
    g22 = first(t, [RS + NUM + r"\s*(?:per gram|/\s*(?:1\s*)?g(?:ram)?)\s*for 22\s*(?:karat|carat|k)\b",
                    r"22\s*(?:k|karat|carat)[^₹]{0,60}?(?:today|rate)[^₹]{0,40}?" + RS + NUM,
                    RS + NUM + r"\s*/\s*1\s*gram\s*\(22\s*k\)",
                    r"22\s*(?:k|karat|carat)\s*(?:gold)?\s*(?:rate)?\s*(?:per|1)\s*gram[^₹]{0,30}" + RS + NUM], 4000, 40000)
    g24 = first(t, [RS + NUM + r"\s*(?:per gram|/\s*(?:1\s*)?g(?:ram)?)\s*for 24\s*(?:karat|carat|k)\b",
                    r"24\s*(?:k|karat|carat)[^₹]{0,60}?(?:today|rate)[^₹]{0,40}?" + RS + NUM,
                    RS + NUM + r"\s*/\s*1\s*gram\s*\(24\s*k\)",
                    r"24\s*(?:k|karat|carat)\s*(?:gold)?\s*(?:rate)?\s*(?:per|1)\s*gram[^₹]{0,30}" + RS + NUM], 4000, 44000)
    if g22 and g24 and not 1.06 <= g24 / g22 <= 1.12:      # 24K is about 9 % above 22K - anything else was read from the wrong place
        g24 = None
    return g22, g24


def parse_silver(t):
    return first(t, [RS + NUM + r"\s*(?:per gram|/\s*(?:1\s*)?g(?:ram)?)\b",
                     r"silver[^₹]{0,80}?(?:per|1)\s*gram[^₹]{0,30}" + RS + NUM,
                     r"1\s*gram[^₹]{0,20}" + RS + NUM], 40, 2000)


def agree(values):
    """the value at least 2 pages show, or None"""
    c = Counter(v for v in values if v)
    if not c:
        return None, 0
    v, n = c.most_common(1)[0]
    return (v, n) if n >= 2 else (None, n)


def collect(day, log, min_agree=2):
    pages = []
    for name, url in GOLD_PAGES:
        try:
            t = fetch(url)
            today = has_today(t, day)
            g22, g24 = parse_gold(t)
            pages.append({"kind": "gold", "name": name, "url": url, "today": today, "g22": g22, "g24": g24})
            log(f"  gold   {name:<11} today's date on page: {'yes' if today else 'NO '} 22K {g22}  24K {g24}")
        except Exception as e:
            pages.append({"kind": "gold", "name": name, "url": url, "error": str(e)[:120]})
            log(f"  gold   {name:<11} not read: {str(e)[:120]}")
    for name, url in SILVER_PAGES:
        try:
            t = fetch(url)
            today = has_today(t, day)
            s = parse_silver(t)
            pages.append({"kind": "silver", "name": name, "url": url, "today": today, "silver": s})
            log(f"  silver {name:<11} today's date on page: {'yes' if today else 'NO '} 1 g {s}")
        except Exception as e:
            pages.append({"kind": "silver", "name": name, "url": url, "error": str(e)[:120]})
            log(f"  silver {name:<11} not read: {str(e)[:120]}")
    gp = [p for p in pages if p["kind"] == "gold" and p.get("today") and p.get("g22")]
    g22, n22 = agree([p["g22"] for p in gp])
    gold = None
    if g22 and n22 >= min_agree:
        same = [p for p in gp if p["g22"] == g22]
        g24, n24 = agree([p.get("g24") for p in same])
        if not g24:      # 24K differs a little between sites: the first agreeing page that has a sensible 24K
            g24 = next((p["g24"] for p in same if p.get("g24")), None)
        if g24:
            gold = {"g22": g22, "g24": g24, "sources": [p["name"] for p in same]}
    sp = [p for p in pages if p["kind"] == "silver" and p.get("today") and p.get("silver")]
    sv, ns = agree([p["silver"] for p in sp])
    silver = {"silver": sv, "sources": [p["name"] for p in sp if p["silver"] == sv]} if sv and ns >= min_agree else None
    return {"gold": gold, "silver": silver, "pages": pages}
