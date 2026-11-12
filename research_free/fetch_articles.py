import json, sys, pathlib
HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
import allnews
out = {}
for it in json.load(open(HERE / "rewrite_input.json", encoding="utf-8")):
    try:
        a = allnews.article_any(it["url"])
        out[it["id"]] = a if isinstance(a, dict) else {"text": str(a)}
        out[it["id"]]["url"] = it["url"]
    except Exception as e:
        out[it["id"]] = {"error": str(e)[:150]}
json.dump(out, open(HERE / "results" / "articles.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print({k: len(v.get("text", "")) for k, v in out.items()})
