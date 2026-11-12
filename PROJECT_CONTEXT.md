# coimbatore360-autopost - project context

Automatic Coimbatore-district news reels for the Instagram page **கோயம்புத்தூர் 360** (`@coimbatore360_official`, placeholder; hashtag `#Coimbatore360`;
`post_to` value in the Sheet: `Coimbatore 360`). A separate, fully independent copy of the Namakkal project `news360-autopost`:
own GitHub repository, own Google account / Sheet / Apps Script, own Instagram token, own Cloudinary account and own free API keys.
Namakkal 360 / Rasipuram 360 are never touched. Same file structure and function names as Namakkal, so Namakkal fixes can be
ported by diff. Everything runs on GitHub Actions; the Google Sheet (through the Apps Script bridge) is the working store.

**Status: not live** (no `LIVE` file, no `research_free/ENABLED`). See the owner setup checklist in `README.md`.

## How it works (end to end)

```
every 2 h    research_free.yml  collect news (newspaper sites incl. Dinamalar Coimbatore page, Google/Bing News, Coimbatore searches)
                                 -> open + check each article -> only Coimbatore-district news of today/yesterday
                                 -> queue by priority (research_free/archive/queue.json)
every 20 min write_stories.yml  write each queued news by priority (free LLM chain only) -> ONE AI image of the main scene
                                 (Cloudflare FLUX schnell -> NVIDIA FLUX -> paid FAL only if both fail) -> story saved in the Sheet
                                 -> starts posting at once
every 5 min  post.yml           checks (Coimbatore only, not stale, no duplicate, daily cap 50; posts at once) -> reel (reel/reel4.py,
                                 Valluvar voice) -> Instagram (one page, no collab)
daily        insights.yml       Instagram insights -> learned topic weights (writer priority)
```

## Rules the owner decided (keep them)

| Area | Rule |
|---|---|
| News scope | Only Coimbatore-district news, published today or yesterday (Coimbatore city, Pollachi, Mettupalayam, Sulur, Annur, Valparai, Kinathukadavu, Madukkarai, Perur, Thondamuthur, Anaimalai, Karamadai ...). Tiruppur, Nilgiris, Erode, Palakkad and every other district are not ours, even when close. "Avinashi Road" is a Coimbatore city road: a headline that also names a Coimbatore place is ours |
| One page | Only கோயம்புத்தூர் 360. No second page, no collaborator, no Rasipuram routing |
| Priority | power cut (TNEB) > crime > accident > civic > the rest |
| Never miss news | Everything eligible is queued and written; duplicates and other-district news are skipped; nothing eligible is dropped |
| Daily cap | 50 reels a day (Instagram's limit) (`DAILY_CAP` in post.yml, also in the collector / writer); urgent news first |
| Posting time | No fixed times (owner 29 Oct): every reel posts the moment it is made (`poster/config.json` `prime_time.enabled: false`) |
| Format | Reel only (no carousel) |
| Voice | **Valluvar only** (free edge-tts `ta-IN-ValluvarNeural`). Google voices are never used, even if a Google key exists |
| Follow line | Spoken: மேலும் செய்திகளுக்கு கோயம்புத்தூர் த்ரீ சிக்ஸ்டி பக்கத்தை பின்தொடருங்கள். Caption: கோயம்புத்தூர் செய்திகளைத் தவறவிடாமல் இருக்க Save செய்து Follow செய்யுங்கள் 📌 |
| Images | ONE new photo-realistic AI image per reel (main scene of THIS news, no text/logos); the reel uses different camera moves / crops of it. Free first: Cloudflare FLUX schnell -> NVIDIA FLUX; paid FAL `flux/schnell` -> `flux/dev` only as the last fallback. Picture check (free Gemini) as in Namakkal |
| Writing | Free LLM chain only; Claude backup OFF (`CLAUDE_MAX_CALLS=0`, no `ANTHROPIC_API_KEY`) |
| Reel language | Formal news Tamil, no slang; everyday Tamil Nadu words in voice, subtitles and cards (பஸ், டூவீலர், போலீசார், கலெக்டர் ...); dates always with the month |
| Website | Off for now (later). `poster/website.py` does nothing without `WEBSITE_INGEST_KEY`; workflows do not pass it |
| Separation | Own accounts and keys, so Namakkal's free API limits are never used; bridge e-mails tagged `COIMBATORE360` |
| Privacy | Personal project; bot commits as `news360-bot`; no office account, office email or Claude lines in commits |

## Main files

| Path | What |
|---|---|
| `research_free/collect.py`, `allnews.py`, `sources.py` | collection, Coimbatore district checks, queue, writer, image |
| `research_free/rules.md`, `examples.json`, `names.py` | writing rules and spoken-word fixes |
| `poster/post.py` | posting checks, prime time, daily cap, Instagram publishing |
| `poster/freshness.py` | stale / duplicate / power-cut timing rules |
| `poster/config.json` | voice (Valluvar), prime time, design switches |
| `reel/reel4.py` | reel renderer (one image, camera moves, voice, opening, dates) |
| `apps_script/Code.gs` | Google Sheet bridge for the Coimbatore 360 account (set the `..._HERE` values; redeploy after changes) |
| `tests/test_regressions.py` | regression tests (run before every push) |

## Sheet bridge (apps_script/Code.gs)

- Page key `coimbatore`, label `கோயம்புத்தூர் 360`, `post_to` `Coimbatore 360`, token property `IG_TOKEN_COIMBATORE` (refreshed weekly).
- Columns: same 31 as Namakkal; column 25 `spare_link` (unused), column 26 `coimbatore_link` (carousel link, unused while reel only),
  27 `reel_link`.
- GET actions: `queue`, `posted_rows`, `token`, `voice`, `recent`, `ping`, `autoPending`.
  POST actions: `posted`, `error`, `addStories`, `archiveNews`, `reoffer`, `setImages`, `repost`.
- E-mail subjects: `COIMBATORE360 STORY`, `COIMBATORE360 REEL`, `[COIMBATORE360 IMAGES NEEDED]` ...

## Secrets (GitHub -> Settings -> Secrets -> Actions; values never in the repo)

BRIDGE_URL, BRIDGE_KEY, GEMINI_API_KEY, GROQ_API_KEY, NVIDIA_API_KEY, CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID,
CLOUDINARY_CLOUD, CLOUDINARY_PRESET; optional MISTRAL_API_KEY, OPENROUTER_API_KEY, GH_MODELS_TOKEN, FAL_KEY (paid image fallback).
Not used: ANTHROPIC_API_KEY, GOOGLE_TTS_API_KEY, WEBSITE_INGEST_KEY. Local copies live only in `.env` (git-ignored).

## Run and check

```
python3 -m unittest discover -s tests        # regression tests (also run by tests.yml on every code push)
python3 tools/repost.py RN-158               # (Actions: repost) post a reel again after it was removed from Instagram
```

## Recent changes
<!-- recent-changes:start (updated automatically by .github/workflows/context.yml - do not edit by hand) -->
| Date | Commit | Change |
|---|---|---|
| 2026-11-11 | `27f7af2` | Apps Script: comment-poll functions renamed without the trailing underscore (private functions are hidden from the Run list) - setupCommentPoll |
| 2026-11-11 | `192dd17` | comment replies: Google Form per batch (works on any device, no account) - news, comment, tick-box replies (one or more), own reply, Reply/Skip/Hide; posted only after the owner submits; 5-minute check (setupCommentPoll_) |
| 2026-11-11 | `de49eec` | facebook RN-312 |
| 2026-11-11 | `026cf77` | comment reply form: the e-mailed link and form buttons use the bridge's own public address (getUrl gave an address that opened Google Drive) (owner 11 Nov) |
| 2026-11-11 | `2247d31` | powercut: notices written |
| 2026-11-11 | `f7697da` | comment replies: one reply form per page (works anywhere) - full news, the comment, 5-7 tick-box replies (one or more) or own text, Post reply / Skip / Hide; nothing is posted before the owner presses Post reply; manual test e-mail (owner 11 Nov) |
| 2026-11-11 | `f0d7f5f` | facebook RN-238 |
| 2026-11-11 | `6a0bacd` | power cuts: a cancellation / postponement / day change is posted (urgent) only when this page posted that cut - never dropped as a duplicate of the original; the power-cut check remembers notices the writer refused (owner 11 Nov) |
| 2026-11-11 | `abb1ac1` | powercut: notices written |
| 2026-11-11 | `6c6ade2` | comments: old unanswered comments offered too (60 days, 100 posts); comments the page already answered in the app are skipped (owner 11 Nov) |
| 2026-11-11 | `e828968` | powercut: notices written |
| 2026-11-11 | `04cdaed` | facebook RN-234 |
| 2026-11-11 | `4157385` | caption ends with 'Source: <paper> (<date>): <article link>'; no source comment under the post (owner 11 Nov) |
| 2026-11-11 | `bbe4aed` | facebook RN-230 |
| 2026-11-11 | `743a5ce` | powercut: notices written |
| 2026-11-11 | `25415ce` | facebook RN-227 |
| 2026-11-11 | `121f6f8` | facebook RN-228 |
| 2026-11-11 | `3ef0d21` | powercut: notices written |
| 2026-11-11 | `c94f28a` | facebook RN-224 |
| 2026-11-11 | `07c0b0f` | facebook RN-225 |
| 2026-11-11 | `547c7e6` | powercut: notices written |
| 2026-11-11 | `a64de44` | Apps Script: comment replies merged into Code.gs - the owner pastes one file (owner 11 Nov) |
| 2026-11-11 | `49b6e3d` | facebook RN-222 |
| 2026-11-11 | `71905fc` | facebook RN-218 |
| 2026-11-11 | `b8c5677` | powercut: notices written |
| 2026-11-11 | `e913c1f` | Facebook: only top news by insights (urgent / best topics), 5 a day 2 h apart, 24 h pause on Facebook's limit (368), no retry; news source (paper + date) on the reel header, end card and captions, article link in the Facebook caption and the page's Instagram comment; comment replies e-mailed with 3 options - posted only after the owner's choice (owner 11 Nov) |
| 2026-11-11 | `3884c40` | facebook retry |
| 2026-11-11 | `789a8d9` | facebook retry |
| 2026-11-11 | `026cd9b` | facebook RN-217 |
| 2026-11-11 | `d95f5a8` | facebook retry |
<!-- recent-changes:end -->
