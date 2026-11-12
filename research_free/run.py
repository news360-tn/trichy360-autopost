"""Test runner. python research_free/run.py URL [URL...]   -> writes research_free/results/<n>.json (+ report). Never touches the live Sheet."""
import json, sys, datetime
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import llm, sources
from validate import autofix, validate

SYSTEM = (HERE / "rules.md").read_text(encoding="utf-8")
EX = json.loads((HERE / "examples.json").read_text(encoding="utf-8"))
IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))


EXTRA = [""]      # extra instruction for one run (e.g. rewrite.py: the exact number of images that already exist)


def prompt(art, today, errors=None):
    shots = "\n\n".join(f"EXAMPLE ARTICLE:\n{e['article']}\nEXAMPLE OUTPUT:\n{json.dumps(e['output'], ensure_ascii=False)}" for e in EX)
    u = f"{shots}\n\nTODAY (IST): {today}\n\nNOW WRITE THE OUTPUT FOR THIS ARTICLE (facts only from this text):\nHEADLINE: {art['title']}\nPUBLISHED: {art['published']}\nARTICLE:\n{art['text'][:6000]}"
    if EXTRA[0]:
        u += "\n\n" + EXTRA[0]
    try:
        import learned
        h = learned.hints()
        if h:
            u += "\n\nLEARNED FROM OUR INSTAGRAM INSIGHTS (style only; facts still only from the article):\n" + h
    except Exception:
        pass
    if errors:
        u += "\n\nYOUR PREVIOUS ANSWER HAD THESE PROBLEMS. Fix all of them and return the full JSON again:\n- " + "\n- ".join(errors)
    return u


def _norm(x, key=""):
    """full place names everywhere (ப.வேலூர் -> பரமத்தி வேலூர்); spoken role/abbreviation words in the reel script"""
    import names
    if isinstance(x, str):
        if key == "reel_script":       # numbers stay DIGITS (screen text = the article's numbers); the voice says them in words (reel/tts.py)
            return names.spoken(x)
        return names.full_places(x)
    if isinstance(x, list):
        return [_norm(i, key) for i in x]
    if isinstance(x, dict):
        return {k: _norm(v, k) for k, v in x.items()}
    return x


def _obj(d):
    """some free models wrap the answer in a list; accept [ {...} ], reject anything that is not an object"""
    if isinstance(d, list) and d and isinstance(d[0], dict):
        d = d[0]
    if not isinstance(d, dict):
        raise ValueError("model answer was not a JSON object")
    return d


MAX_ATTEMPTS = 10      # owner: a wrong draft is rewritten up to 10 times (with the exact problems listed) before the story is dropped; the round time budget still applies


def write(art, today):
    errors, best = None, None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            d, model = llm.ask_json(SYSTEM, prompt(art, today, errors))
        except Exception as e:      # every free model is busy / out of quota: do not give up, Claude (if the key is set) writes it below
            print("free models unavailable:", str(e)[:120])
            if not llm.claude_available():
                raise
            break
        try:
            d = _norm(autofix(_obj(d)))
        except ValueError as e:
            errors = [str(e)]
            print(f"attempt {attempt} {model}: {e}")
            continue
        errors = validate(d, art["text"] + " " + art["title"])
        if not errors:
            errors = factcheck(d, art)
        print(f"attempt {attempt} {model}: {len(errors)} problems", *errors, sep="\n  ")
        if best is None or len(errors) <= len(best[2]):      # keep the draft with the fewest problems
            best = (d, model, errors, attempt)
        if not errors:
            break
    if (best is None or best[2]) and llm.claude_available():       # free models could not give a clean draft: let Claude rewrite it (max 2 tries)
        errs = best[2] if best else None
        for k in range(3):
            try:
                d, model = llm.ask_claude(SYSTEM, prompt(art, today, errs), max_tokens=5000)
                d = _norm(autofix(_obj(d)))
            except Exception as e:
                print("claude rewrite failed:", str(e)[:150])
                break
            errs = validate(d, art["text"] + " " + art["title"])
            if not errs:
                errs = factcheck(d, art)
            print(f"claude rewrite {k + 1} {model}: {len(errs)} problems", *errs, sep="\n  ")
            if best is None or len(errs) <= len(best[2]):
                best = (d, model, errs, MAX_ATTEMPTS + k + 1)
            if not errs:
                break
    if best is None:
        raise RuntimeError("no usable answer from the models")
    return proofread(best, art)


CHECK = """You are a strict fact-checker for a Tamil local-news page. You get an ARTICLE and a DRAFT (JSON with Tamil text).
Check EVERY claim in the draft's tamil_headline, reel_script, slides_spec and caption against the ARTICLE.
Report a problem for each of these: a place, person role, number, amount, date, time or cause that is NOT in the article or differs from it; an invented detail; a sentence that is ungrammatical or has no clear meaning in Tamil; two different facts mixed into one sentence; an important fact of the article (who did what, where, result such as an arrest) that is missing from the reel_script.
NOT problems: the caption footer (the 📍 place | posting-date line, the Follow line, hashtags), the fixed closing sentence of reel_script that tells viewers to follow the "கோயம்புத்தூர் த்ரீ சிக்ஸ்டி" page, and wording choices such as மூதாட்டி for an elderly woman. The posting date is today's date, not a claim from the article.
Return ONLY JSON: {"ok": true or false, "problems": ["short English description of each problem"]}. ok is true ONLY when the problems list is empty."""


def _cap_body(cap):
    """caption without footer lines (📍 place | posting date, Follow line, hashtags): they are not claims from the article"""
    return "\n".join(l for l in str(cap or "").split("\n") if not (l.strip().startswith(("\U0001F4CD", "#")) or "Follow" in l)).strip()


def factcheck(d, art, claude=True):
    """independent second call: compares the draft with the article. Claude first when ANTHROPIC_API_KEY is set, else the free chain.
    Returns a list of problems."""
    user = "ARTICLE:\n" + art["title"] + "\n" + art["text"][:6000] + "\n\nDRAFT:\n" + json.dumps(
        {k: (_cap_body(d.get(k)) if k == "caption" else d.get(k)) for k in ("tamil_headline", "reel_script", "slides_spec", "caption")}, ensure_ascii=False)
    try:
        try:
            r, m = llm.ask_json(CHECK, user)          # free models first
        except Exception as e:                          # owner: Claude ONLY when the free models are not available
            if not llm.claude_available():
                raise
            print("free fact-check unavailable, using Claude:", str(e)[:100])
            r, m = llm.ask_claude(CHECK, user)
        r = _obj(r)
        probs = [str(x) for x in (r.get("problems") or [])]
        if r.get("ok") is False and not probs:
            probs = ["fact-checker rejected the draft"]
        print(f"factcheck by {m}: {len(probs)} problems", *probs, sep="\n  ")
        return ["fact-check: " + x for x in probs]
    except Exception as e:
        print("factcheck unavailable:", e)
        return ["fact-check: could not be run"]


PROOF = """You are a senior Tamil news editor and proofreader for the Instagram page "கோயம்புத்தூர் 360" (Coimbatore district).
You get a JSON draft. Return the SAME JSON object (same keys, same structure, same facts, same numbers) with ONLY these fixes:
1. Correct Tamil spelling, sandhi (புணர்ச்சி), grammar and place names in every Tamil text.
2. reel_script: make it read like ONE continuous story by a professional Tamil TV news reader: smooth connecting words between sentences (மேலும், இதனால், இதையடுத்து, இந்நிலையில்), no abrupt jumps, no repeated facts, first sentence = the hook. Keep the key facts of the draft (70-160 words: the reel is at most 90 seconds - keep EVERY fact of the draft, never drop one to make it shorter) and give every detail the article has (who, exact place, when, how, numbers, action, what next). Keep EVERY number, date, time, amount and age exactly as the digits written in the draft (10.30 மணி, ரூ.5.70, 65 வயது, 26ஆம் தேதி) - never turn them into words and never change them. No English letters. English words that people say in Tamil must be written in Tamil script so a Tamil voice pronounces them (மொபைல், ஆன்லைன், பஸ்). Keep the last sentence exactly: மேலும் செய்திகளுக்கு கோயம்புத்தூர் த்ரீ சிக்ஸ்டி பக்கத்தை பின்தொடருங்கள்.
3. slides_spec texts and caption: natural modern Tamil, no half-English sentences except fixed words (Follow, Share, Save). Keep the character limits (hl1 40, hl2 28, title 18, lines 60).
4. "scenes" stays exactly as it is: the TWO English image prompts (do not add, split or translate them).
Never add facts. Never remove the follow line or hashtags. Output ONLY the JSON object."""


def proofread(best, art):
    """second free-model pass: Tamil grammar/spelling, smooth news-reader flow. Kept only if it still passes every check."""
    d, model, errors, att = best
    try:
        fixed, m2 = llm.ask_json(PROOF, json.dumps(d, ensure_ascii=False))
        fixed = _obj(fixed)
        e2 = validate(fixed, art["text"] + " " + art["title"])
        if not e2 and not errors:
            e2 = factcheck(fixed, art)
        if len(e2) <= len(errors) and set(fixed) >= set(d):
            print(f"proofread by {m2}: {len(e2)} problems")
            return fixed, model + " + proofread " + m2, e2, att
        print(f"proofread rejected ({len(e2)} problems)", *e2, sep="\n  ")
    except Exception as e:
        print("proofread skipped:", e)
    return best


def main(urls):
    today = datetime.datetime.now(IST).strftime("%A %d %B %Y")
    rep = []
    for n, u in enumerate(urls, 1):
        try:
            art = sources.article(u)
            d, model, errors, att = write(art, today)
        except Exception as e:
            rep.append(f"{n}. FAILED {u}: {type(e).__name__}: {str(e)[:300]}")
            continue
        (HERE / "results" / f"{n}.json").write_text(json.dumps({"url": u, "article": art, "model": model, "attempts": att, "problems": errors, "draft": d}, ensure_ascii=False, indent=1), encoding="utf-8")
        rep.append(f"{n}. {art['title'][:70]} | {model} | attempts {att} | problems {len(errors)}")
    (HERE / "results" / "report.txt").write_text("\n".join(rep) + "\n\n" + "\n".join(llm.LOG), encoding="utf-8")
    print("\n".join(rep))


if __name__ == "__main__":
    main(sys.argv[1:])
