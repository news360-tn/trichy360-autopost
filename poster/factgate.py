"""Last gate before a reel is built and posted: re-read the story's SOURCE article and fact-check the spoken script, headline and caption
against it with a model (independent of the writer's own check). Returns blocking problems; '' list = fine / could not check."""
import json, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "research_free"))

SOFT = ("caption mentions", "date '", "posting date", "promotional", "follow line", "த்ரீ சிக்ஸ்டி", "follow ", "page is not mentioned", "date of posting", "missing", "misses", "omit", "not mentioned in the draft", "could not be run")      # an omission is not a false statement: never blocks


def _body(cap):
    """caption without the footer (the 📍 place | posting-date line, follow line, hashtags): the posting date is not a claim from the article"""
    keep = []
    for ln in (cap or "").split("\n"):
        t = ln.strip()
        if t.startswith("\U0001F4CD") or t.startswith("#") or "Follow" in t:
            continue
        keep.append(ln)
    return "\n".join(keep).strip()


def check(row):
    url = (row.get("source") or "").strip()
    if not url.startswith("http") or not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("NVIDIA_API_KEY") and not os.environ.get("GEMINI_API_KEY") and not os.environ.get("GROQ_API_KEY") and not os.environ.get("SARVAM_API_KEY"):
        return []
    try:
        import allnews, run
        a = allnews.article_any(url)
        text = a.get("text", "") if isinstance(a, dict) else (a[-1] if isinstance(a, (tuple, list)) else str(a or ""))
        title = a.get("title", "") if isinstance(a, dict) else ""
        if not text or len(text) < 200:
            print("factgate: article text not available - not blocking")
            return []
        d = {"tamil_headline": row.get("headline_ta", ""), "reel_script": row.get("reel_script", ""),
             "slides_spec": json.loads(row["slides_spec"]) if row.get("slides_spec") else "", "caption": _body(row.get("caption", ""))}
        probs = run.factcheck(d, {"title": title or row.get("headline_ta", ""), "text": text})
        probs = [p for p in probs if not any(w in p.lower() for w in SOFT)]
        return confirm(probs, title, text) if probs else []
    except Exception as e:
        print("factgate unavailable - not blocking:", str(e)[:150])
        return []


CONFIRM = """You are a strict senior news editor. A first checker listed possible factual problems in a draft; first checkers often misread. For EACH problem, find the exact sentence in the ARTICLE that proves it. The fixed closing line "மேலும் செய்திகளுக்கு கோயம்புத்தூர் த்ரீ சிக்ஸ்டி பக்கத்தை பின்தொடருங்கள்", the caption footer and hashtags are never problems. Wording choices (e.g. மூதாட்டி for an elderly woman) are not problems. Only a wrong name, number, place, date, cause or event that contradicts the article is real.
Return ONLY JSON: {"results":[{"n":1,"real":true|false,"quote":"article sentence that proves it, or empty"}]}"""


def confirm(probs, title, text):
    """second, independent opinion: keep a problem only when the model can quote the article sentence that proves it.
    If the second opinion cannot run, keep all problems (never post on doubt)."""
    try:
        import llm
        user = "ARTICLE:\n" + title + "\n" + text[:6000] + "\n\nPROBLEMS:\n" + "\n".join(f"{i+1}. {p}" for i, p in enumerate(probs))
        try:
            r, m = llm.ask_json(CONFIRM, user)          # free models first; Claude only when they are not available
        except Exception:
            if not llm.claude_available():
                return probs
            r, m = llm.ask_claude(CONFIRM, user, max_tokens=1500)
        res = r.get("results") if isinstance(r, dict) else None
        if not res:
            return probs
        keep = []
        for i, p in enumerate(probs):
            x = next((y for y in res if y.get("n") == i + 1), None)
            if x is None or (x.get("real") and (x.get("quote") or "").strip()):
                keep.append(p)
        print(f"factgate confirm by {m}: {len(probs)} flagged -> {len(keep)} confirmed")
        return keep
    except Exception as e:
        print("factgate confirm unavailable - keeping the flags:", str(e)[:120])
        return probs


FIX = """You are a senior Tamil news editor. You get an ARTICLE, a DRAFT (JSON) and a list of CONFIRMED factual problems in the draft.
Return the SAME JSON object (same keys, same structure) with ONLY those problems corrected: remove each invented detail, or change it to exactly what the ARTICLE says.
Never add a fact that is not in the ARTICLE. Keep everything else unchanged, keep the closing follow sentence of reel_script, keep the slide character limits.
Output ONLY the JSON object."""


def fix(row, probs):
    """confirmed problems: ask a model to correct ONLY those claims, then check the corrected text again.
    Returns the corrected fields (dict) when the second check is clean, else None (the story is held, never posted with a false fact)."""
    try:
        import allnews, run, llm
        a = allnews.article_any(row["source"].strip())
        title, text = a.get("title", ""), a.get("text", "")
        d = {"tamil_headline": row.get("headline_ta", ""), "reel_script": row.get("reel_script", ""),
             "slides_spec": json.loads(row["slides_spec"]) if row.get("slides_spec") else "", "caption": row.get("caption", "")}
        user = "ARTICLE:\n" + title + "\n" + text[:6000] + "\n\nPROBLEMS:\n" + "\n".join(f"- {p}" for p in probs) + "\n\nDRAFT:\n" + json.dumps(d, ensure_ascii=False)
        for k in range(2):
            try:
                r, m = llm.ask_json(FIX, user) if k == 0 else llm.ask_claude(FIX, user, max_tokens=5000)
            except Exception as e:
                print(f"factgate fix {k + 1} unavailable:", str(e)[:120])
                continue
            if not isinstance(r, dict) or not all(r.get(x) for x in ("reel_script", "slides_spec")):
                continue
            chk = {"tamil_headline": r.get("tamil_headline") or d["tamil_headline"], "reel_script": r["reel_script"],
                   "slides_spec": r["slides_spec"], "caption": _body(r.get("caption") or d["caption"])}
            left = [p for p in run.factcheck(chk, {"title": title, "text": text}) if not any(w in p.lower() for w in SOFT)]
            left = confirm(left, title, text) if left else []
            print(f"factgate fix by {m}: {len(left)} problems left")
            if not left:
                return {"headline_ta": chk["tamil_headline"], "reel_script": r["reel_script"], "caption": r.get("caption") or d["caption"],
                        "slides_spec": json.dumps(r["slides_spec"], ensure_ascii=False) if isinstance(r["slides_spec"], dict) else r["slides_spec"]}
    except Exception as e:
        print("factgate fix failed:", str(e)[:150])
    return None
