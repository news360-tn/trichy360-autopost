"""AI image generation for Coimbatore 360 - ONE realistic 9:16 news photo per story, FREE FIRST:
Cloudflare Workers AI FLUX schnell (free daily allowance) -> NVIDIA NIM FLUX (free credits) -> only if both fail: FAL flux/schnell (cheapest paid)
-> FAL flux/dev. generate(prompt, seed) -> JPEG bytes, or raises. A model that answers 401/403/404 (not in the plan / bad key) is skipped for the
rest of the run, 402/429 (credits / rate limit) switches to the next model."""
import base64, json, os, sys, time, requests

GEN = "https://ai.api.nvidia.com/v1/genai/"
# (model path, request body builder). FLUX only accepts sizes that are multiples of 64 inside 768..1344 -> 768x1344 is 9:16.
MODELS = [      # Coimbatore 29 Oct: schnell first (dev timed out at 100 s); SDXL-lightning / SD3-medium answered 404 and were removed
    ("black-forest-labs/flux.1-schnell", lambda p, s: {"prompt": p, "width": 768, "height": 1344, "seed": s, "steps": 4}),
    ("black-forest-labs/flux.1-dev", lambda p, s: {"prompt": p, "mode": "base", "cfg_scale": 3.5, "width": 768, "height": 1344, "seed": s, "steps": 28}),
]
DEAD = set()
USED = {}


def _one(model, body, key):
    r = requests.post(GEN + model, json=body, timeout=150,
                      headers={"Authorization": "Bearer " + key, "Accept": "application/json"})
    if r.status_code != 200:
        raise RuntimeError(f"{model} {r.status_code}: {r.text[:300]}")
    j = r.json()
    art = (j.get("artifacts") or [{}])[0]
    b64 = art.get("base64") or j.get("image")
    if not b64 or art.get("finishReason") not in (None, "SUCCESS"):
        raise RuntimeError(f"{model} no image ({art.get('finishReason')}): {str(j)[:200]}")
    return base64.b64decode(b64)


FAL_URL = "https://fal.run/"
# fal.ai (paid): used ONLY when Cloudflare and NVIDIA both fail. FAL_MODEL (the last backup) can be switched without code changes,
# e.g. fal-ai/bytedance/seedream/v4/text-to-image
FAL_MODEL = os.environ.get("FAL_MODEL") or "fal-ai/flux/dev"
# fal bills per megapixel rounded UP: 720x1280 = 0.92 MP -> billed as 1 MP (768x1344 = 1.03 MP would be billed as 2 MP)
FAL_W, FAL_H = 720, 1280
# the first paid model: FLUX schnell ($0.003, cheapest); FLUX dev ($0.025) only if schnell fails too
FAL_SCENE_MODEL = os.environ.get("FAL_SCENE_MODEL") or "fal-ai/flux/schnell"


def _fal(prompt, seed, key, model=None):
    model = model or FAL_MODEL
    body = {"prompt": prompt, "image_size": {"width": FAL_W, "height": FAL_H}, "num_images": 1, "seed": seed,
            "enable_safety_checker": True}
    if "schnell" in model:
        body["num_inference_steps"] = 4
    r = requests.post(FAL_URL + model, json=body, timeout=120,
                      headers={"Authorization": "Key " + key, "Content-Type": "application/json"})
    if r.status_code != 200:
        raise RuntimeError(f"fal {model} {r.status_code}: {r.text[:300]}")
    imgs = r.json().get("images") or []
    if not imgs or not imgs[0].get("url"):
        raise RuntimeError(f"fal {model} no image: {r.text[:200]}")
    d = requests.get(imgs[0]["url"], timeout=120)
    d.raise_for_status()
    return d.content


CF = "https://api.cloudflare.com/client/v4/accounts/{}/ai/run/@cf/"
CF_MODELS = [
    ("black-forest-labs/flux-1-schnell", lambda p, s: {"prompt": p, "steps": int(os.environ.get("CF_IMAGE_STEPS", "4"))}),      # 30 Oct: 4 (was 8) = ~230 free pictures/day
]


def _cf(model, body, token, acct):
    r = requests.post(CF.format(acct) + model, json=body, timeout=100, headers={"Authorization": "Bearer " + token})
    if r.status_code != 200:
        raise RuntimeError(f"cloudflare {model} {r.status_code}: {r.text[:300]}")
    if r.headers.get("content-type", "").startswith("image/"):
        return r.content
    j = r.json()
    b64 = (j.get("result") or {}).get("image")
    if not b64:
        raise RuntimeError(f"cloudflare {model} no image: {str(j)[:200]}")
    return base64.b64decode(b64)


_VISION = []


def _vision_models(key):
    """flash models that exist for this key right now (same list as the writer), asked once per run"""
    if not _VISION:
        env = os.environ.get("GEMINI_VISION_MODEL")
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            import llm
            found = llm.gemini_models(key)
        except Exception:
            found = []
        stable = [m for m in found if "preview" not in m]      # a stable, answering model first (3.6 / 3.5 answered on 28 Oct; 3.8 / 3.7 timed out)
        _VISION.extend(dict.fromkeys(([env] if env else []) + stable[2:] + stable[:2] + llm.GEMINI_MODELS))
    return list(_VISION)


def matches(data, headline):
    """a vision model checks that the picture shows the news headline. True when it matches or the check is not available."""
    key = os.environ.get("GEMINI_API_KEY")
    if not key or not headline:
        return True
    try:
        body = {"contents": [{"parts": [
                    {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(data).decode()}},
                    {"text": f'Does this photo show the news story: "{headline}"? Check the place type, the event, and the people. '
                             'Answer only JSON: {"match": true or false, "why": "short reason"}'}]}],
                "generationConfig": {"responseMimeType": "application/json", "temperature": 0}}
        j, last = None, None
        for model in _vision_models(key):      # 28 Oct: gemini-2.5-flash was retired (404) and every picture went out unchecked
            try:      # the newest models often time out or are busy (503): the next one answers
                r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                                  headers={"x-goog-api-key": key, "Content-Type": "application/json"}, json=body, timeout=30)
                if r.status_code == 404:
                    _VISION.remove(model)
                r.raise_for_status()
                j = json.loads(r.json()["candidates"][0]["content"]["parts"][0]["text"])
                break
            except Exception as e:
                last = f"{model}: {e}"
        if j is None:
            raise RuntimeError(last or "no vision model")
        print("image match:", j.get("match"), str(j.get("why", ""))[:120], flush=True)
        return bool(j.get("match"))
    except Exception as e:
        print("image match check unavailable:", str(e)[:120], flush=True)
        return True


def to_story_size(data):
    """FLUX answers a 1024x1024 square: cut the centre 9:16 column and enlarge it to 1152x2048 (the poster crops/enhances again later)"""
    from io import BytesIO
    from PIL import Image
    im = Image.open(BytesIO(data)).convert("RGB")
    w, h = im.size
    if w / h > 0.5625:
        nw = round(h * 9 / 16)
        im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    im = im.resize((1152, 2048), Image.LANCZOS)
    out = BytesIO()
    im.save(out, "JPEG", quality=95, subsampling=0)
    return out.getvalue()


GEMINI_IMAGE_MODELS = [m for m in os.environ.get("GEMINI_IMAGE_MODELS", "gemini-3.1-flash-lite-image,gemini-3.1-flash-image,gemini-2.5-flash-image").split(",") if m]
CLEAN = " Realistic news photograph. No text, no letters, no signboards with writing, no logos, no watermark."


def _gemini_image(prompt, key):
    """owner 29 Oct: every free image source before paid FAL. Gemini image models on the Coimbatore project's FREE tier
    (keep that Google project without billing: then a model outside the free tier answers 429 and costs nothing)."""
    last = None
    for model in GEMINI_IMAGE_MODELS:
        if model in DEAD:
            continue
        body = {"contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": "9:16"}}}
        try:
            r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                              headers={"x-goog-api-key": key, "Content-Type": "application/json"}, json=body, timeout=90)
            if r.status_code != 200:
                raise RuntimeError(f"gemini {model} {r.status_code}: {r.text[:200]}")
            for part in r.json()["candidates"][0]["content"]["parts"]:
                data = (part.get("inlineData") or part.get("inline_data") or {}).get("data")
                if data:
                    USED[model] = USED.get(model, 0) + 1
                    return base64.b64decode(data)
            raise RuntimeError(f"gemini {model} no image")
        except Exception as e:
            last = e
            print("imagegen:", str(e)[:220], file=sys.stderr)
            DEAD.add(model)      # quota 0 / busy / not served: the next source for the rest of this run
    raise RuntimeError(f"gemini image: {last}")


def generate(prompt, seed=0, key=None, cheap=False, free_only=False):
    """ONE picture for the story. free_only=True (the second try after a failed picture check): Cloudflare / NVIDIA only, never FAL.
    `cheap` is kept for callers of the Namakkal code; the order is the same for every picture (free first)."""
    return to_story_size(_generate(prompt, seed, key, cheap, free_only))



# ---- owner 30 Oct: more FREE picture services, tried after Cloudflare and before NVIDIA / paid FAL.
# Each is skipped when its key (GitHub secret) is not set, so nothing changes until the owner adds the key.
# Request shapes from the official API docs (Together images/generations, Pollinations gen API).
def _together(prompt, seed, key):
    body = {"model": os.environ.get("TOGETHER_IMAGE_MODEL", "black-forest-labs/FLUX.1-schnell-Free"), "prompt": prompt[:1800],
            "width": 768, "height": 1344, "steps": 4, "n": 1, "seed": seed, "response_format": "base64"}
    r = requests.post("https://api.together.ai/v1/images/generations", json=body, timeout=60, headers={"Authorization": "Bearer " + key})
    if r.status_code == 400 and "height" in r.text.lower():      # a size the free model does not take: the 9:16 size it does
        body.update(width=576, height=1024)
        r = requests.post("https://api.together.ai/v1/images/generations", json=body, timeout=60, headers={"Authorization": "Bearer " + key})
    if r.status_code != 200:
        raise RuntimeError(f"together {r.status_code}: {r.text[:200]}")
    item = (r.json().get("data") or [{}])[0]
    if item.get("b64_json"):
        return base64.b64decode(item["b64_json"])
    if item.get("url"):
        d = requests.get(item["url"], timeout=60)
        d.raise_for_status()
        return d.content
    raise RuntimeError(f"together no image: {r.text[:200]}")


def _pollinations(prompt, seed, key):
    import urllib.parse
    r = requests.get("https://gen.pollinations.ai/image/" + urllib.parse.quote(prompt[:1500]), timeout=90,
                     params={"width": 768, "height": 1344, "seed": seed, "model": os.environ.get("POLLINATIONS_MODEL", "flux"), "nologo": "true"},
                     headers={"Authorization": "Bearer " + key})
    if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image/"):
        raise RuntimeError(f"pollinations {r.status_code}: {r.text[:200] if not r.headers.get('content-type','').startswith('image/') else ''}")
    return r.content


EXTRA_FREE = [("together", "TOGETHER_API_KEY", _together),      # owner 30 Oct: SiliconFlow removed (not free: "balance insufficient"); Together only with a key (not set)
              ("pollinations", "POLLINATIONS_API_KEY", _pollinations)]


def _extra_free(prompt, seed):
    """the free services after Cloudflare; a service that refuses the key, is out of its free limit or keeps failing is not tried again this run"""
    last = None
    for name, env, fn in EXTRA_FREE:
        key = os.environ.get(env)
        if not key or name in DEAD:
            continue
        for k in range(2):
            try:
                img = fn(prompt, seed + k, key)
                USED[name] = USED.get(name, 0) + 1
                return img, None
            except Exception as e:
                last = e
                m = str(e)
                print("imagegen:", m[:220], file=sys.stderr)
                if any(c in m for c in (" 401", " 402", " 403", " 404")) or (" 429" in m and k == 1):
                    DEAD.add(name)      # no access / out of the free limit: the next service for the rest of this run
                    break
                time.sleep(8 if " 429" in m else 2)
        else:
            DEAD.add(name)      # failed twice: the next service
    return None, last


def _generate(prompt, seed=0, key=None, cheap=False, free_only=False):
    """FREE first: Cloudflare Workers AI FLUX schnell -> Gemini image (free tier) -> NVIDIA FLUX (free credits);
    only when every free source fails: FAL flux/schnell (~Rs 0.26) -> FAL flux/dev; if FAL fails too, the reel uses the plain branded
    background (owner 29 Oct). Cloudinary only stores the picture."""
    if "No text" not in prompt:
        prompt = prompt.rstrip(". ") + "." + CLEAN
    tok, acct = os.environ.get("CLOUDFLARE_API_TOKEN"), os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    last = None
    if tok and acct:
        for model, build in CF_MODELS:
            if model in DEAD:
                continue
            try:
                img = _cf(model, build(prompt, seed), tok, acct)
                USED[model] = USED.get(model, 0) + 1
                return img
            except Exception as e:
                last = e
                m = str(e)
                print("imagegen:", m[:220], file=sys.stderr)
                if any(c in m for c in (" 401", " 403", " 404", " 400", " 422", "no image", "daily free allocation")) or "Timeout" in type(e).__name__:
                    DEAD.add(model)      # 29 Oct: the shared account's 10,000 free neurons were used up - no retry for every picture
    gkey = os.environ.get("GEMINI_API_KEY")
    if gkey and os.environ.get("GEMINI_IMAGE", "0") == "1":      # 29 Oct: free tier answered 429 (quota 0) for every image model
        try:
            return _gemini_image(prompt, gkey)
        except Exception as e:
            last = e
    img, err = _extra_free(prompt, seed)      # owner 30 Oct: Pollinations (free) before NVIDIA and paid FAL
    if img:
        return img
    last = err or last
    nkey = key or os.environ.get("NVIDIA_API_KEY")
    if nkey:
        try:
            return generate_nvidia(prompt, seed, nkey)
        except Exception as e:
            last = e
    fkey = os.environ.get("FAL_KEY")
    if not free_only and os.environ.get("FAL_ENABLE", "1") == "1":      # owner 29 Oct (final): FAL only when NO free source made a picture
        for fm in dict.fromkeys([FAL_SCENE_MODEL, FAL_MODEL]):
            if not fkey or fm in DEAD:
                continue
            for k in range(2):
                try:
                    img = _fal(prompt, seed + k, fkey, fm)
                    USED[fm] = USED.get(fm, 0) + 1
                    return img
                except Exception as e:
                    last = e
                    m = str(e)
                    print("imagegen:", m[:220], file=sys.stderr)
                    if any(c in m for c in (" 401", " 403", " 404", " 422")):
                        DEAD.add(fm)     # bad key / no balance / wrong model id: use the backups for the rest of this run
                        break
                    time.sleep(3)
    raise RuntimeError(f"all image models failed: {last or 'no image service configured'}")


def generate_nvidia(prompt, seed=0, key=None):
    key = key or os.environ.get("NVIDIA_API_KEY")
    if not key:
        raise RuntimeError("NVIDIA_API_KEY missing")
    last = None
    for model, build in MODELS:
        if model in DEAD:
            continue
        for k in range(2):
            try:
                img = _one(model, build(prompt, seed + k), key)
                USED[model] = USED.get(model, 0) + 1
                return img
            except Exception as e:
                last = e
                m = str(e)
                if "Timeout" in type(e).__name__ or "timed out" in m:
                    m += " 504 timeout"
                print("imagegen:", m[:220], file=sys.stderr)
                if any(c in m for c in (" 401", " 403", " 404", " 422", " 504")):
                    DEAD.add(model)
                    break
                if any(c in m for c in (" 402", " 429")):
                    time.sleep(8) if " 429" in m and k == 0 else None
                    if k == 1 or " 402" in m:
                        break
                time.sleep(3)
    raise RuntimeError(f"all image models failed: {last}")


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "test.jpg"
    data = generate(sys.argv[2] if len(sys.argv) > 2 else "Photorealistic news photo, tall vertical, a city road in Coimbatore, Tamil Nadu at dawn, police jeep parked, mist, sharp detail")
    open(out, "wb").write(data)
    print("saved", out, len(data), "bytes", USED)
