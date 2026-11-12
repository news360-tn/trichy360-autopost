"""Post-publication audit: re-read each posted story's source article and fact-check the spoken script against it. Output: results/audit.json"""
import json, sys, pathlib
HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
import allnews, run

out = []
for r in json.load(open(HERE / "audit_input.json", encoding="utf-8")):
    try:
        text = allnews.article_any(r["url"])
        if isinstance(text, tuple):
            text = text[0]
        text = text if isinstance(text, str) else (text or {}).get("text", "")
    except Exception as e:
        out.append({"id": r["id"], "error": "fetch failed: " + str(e)[:100]}); continue
    if not text or len(text) < 200:
        out.append({"id": r["id"], "error": "article text not available"}); continue
    probs = run.factcheck({"tamil_headline": "", "reel_script": r["reel_script"], "slides_spec": "", "caption": ""}, {"title": r["id"], "text": text})
    out.append({"id": r["id"], "article_excerpt": text[:700], "problems": probs})
json.dump(out, open(HERE / "results" / "audit.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False)[:2000])
