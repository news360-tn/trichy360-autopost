"""What Instagram insights taught us (written by poster/insights.py into learned.json). Used ONLY to order candidate stories and to give the
writer style hints. It never relaxes a fact / quality check."""
import json, pathlib

HERE = pathlib.Path(__file__).parent
TOPICS = {
    "weather": ["மழை", "வெயில்", "வானிலை", "எச்சரிக்கை", "புயல்", "வெள்ளம்"],
    "crime": ["கொலை", "கைது", "திருட", "போலீஸ்", "குற்ற", "மோசடி", "தற்கொலை", "கொள்ளை"],
    "accident": ["விபத்து", "பலி", "உயிரிழ", "தீ விபத்து", "மோதி"],
    "temple": ["கோயில்", "கோவில்", "திருவிழா", "தேரோட்ட", "தேர்த்திருவிழா", "சாமி", "பூஜை", "குடமுழுக்கு"],      # not "தேர்": it is inside தேர்வு / தேர்தல்
    "politics": ["முதல்வர்", "அமைச்சர்", "திமுக", "அதிமுக", "எம்எல்ஏ", "எம்.எல்.ஏ", "தேர்தல்", "ஆட்சியர்", "கட்சி"],
    "poultry_agri": ["முட்டை", "கோழி", "விவசாய", "விலை", "கொள்முதல்", "மஞ்சள்", "பண்ணை", "லாரி"],
    "education": ["மாணவ", "பள்ளி", "கல்லூரி", "தேர்வு"],
    "civic": ["குடிநீர்", "சாலை", "பேருந்து", "நகராட்சி", "பஞ்சாயத்து", "குப்பை"],
    "sports_culture": ["போட்டி", "கபடி", "விளையாட்டு", "கலை", "சினிமா", "விருது"],
}


# owner 28 Oct: power cuts and jobs were filed under civic / education_jobs (both -0.5) although they are our most watched news
# ('நாளை 9 பகுதிகளில் மின் தடை' 17,328 views, 'தனியார் வேலைவாய்ப்பு முகாம்' 17,209; page median 374). They are their own topics and
# win over any other topic word in the headline ('சாலை' in a power-cut notice is still a power cut).
FIRST = {
    "power_cut": ["மின்தடை", "மின் தடை", "மின் நிறுத்த", "மின்விநியோகம் நிறுத்த", "power cut", "power shutdown"],
    "jobs": ["வேலைவாய்ப்பு", "வேலை வாய்ப்பு", "காலிப்பணி", "பணியிடங்கள்", "ஆட்சேர்ப்பு", "job fair", "recruitment", "vacanc"],
}
# starting weight until insights has measured MIN_PER_TOPIC posts of the topic (then the measured weight is used)
PRIOR = {"power_cut": 1.5, "crime": 1.2, "accident": 1.0, "civic": 0.8}      # owner 29 Oct (Coimbatore order); measured insights replace these later


def topic(text):
    t = text or ""
    low = t.lower()
    for k, words in FIRST.items():
        if any(w.lower() in low for w in words):
            return k
    best, n = "other", 0
    for k, words in TOPICS.items():
        c = sum(1 for w in words if w in t)
        if c > n:
            best, n = k, c
    return best


def load():
    try:
        return json.loads((HERE / "learned.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def boost(text):
    """score adjustment for a candidate headline from its topic's measured performance (weights are already clamped by insights.py)"""
    t = topic(text)
    w = (load().get("topic_weight") or {}).get(t)
    return float(w) if w is not None else PRIOR.get(t, 0.0)


def hints():
    """short style guidance for the writer prompt; '' until enough posts have been measured"""
    d = load()
    out = []
    if d.get("avg_watch_s"):
        out.append(f"Viewers leave after about {d['avg_watch_s']} seconds on average: the FIRST sentence of reel_script must carry the most surprising fact (a number, place or consequence), never a greeting or background.")
    if d.get("top_openings"):
        out.append("Openings of our best-performing reels (style reference only, never copy facts): " + " | ".join(d["top_openings"][:4]))
    return "\n".join(out)
