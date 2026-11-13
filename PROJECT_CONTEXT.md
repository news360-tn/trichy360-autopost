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
| 2026-11-13 | `1130b32` | reel: same design as Coimbatore 360 (colours, shapes, fonts) - per-page themes removed; end card keeps 'Source:' (owner 12 Nov); waiting reels rebuilt |
| 2026-11-13 | `9c95ed0` | powercut: notices written |
| 2026-11-13 | `8764fb3` | pick: picked news saved |
| 2026-11-13 | `f479342` | pick: picked news saved |
| 2026-11-13 | `a8be844` | pick: list sent |
| 2026-11-13 | `c130f74` | powercut: notices written |
| 2026-11-13 | `03d5cae` | powercut: notices written |
| 2026-11-13 | `2ff0a3d` | powercut: notices written |
| 2026-11-13 | `c5f80be` | reel: new Trichy 360 footer logo (same size and format as Namakkal/Rasipuram, transparent surround); waiting reels rebuilt |
| 2026-11-13 | `c08f701` | powercut: notices written |
| 2026-11-13 | `ccce0ff` | stories shared |
| 2026-11-13 | `534ed15` | powercut: notices written |
| 2026-11-13 | `2061636` | rasipalan posted |
| 2026-11-13 | `f12b80d` | pick: written and posted |
| 2026-11-13 | `4fce457` | powercut: notices written |
| 2026-11-13 | `35a0f81` | pick: picked news saved |
| 2026-11-13 | `9d5e9b3` | pick: picked news saved |
| 2026-11-13 | `ceee0e4` | pick: list sent |
| 2026-11-13 | `d13fa35` | powercut: notices written |
| 2026-11-12 | `7049695` | powercut: notices written |
| 2026-11-12 | `8462fc7` | voice: numbers read the way people say them - English names in English (பிளஸ் டூ, குரூப் ஃபோர், டி ட்வென்டி, ஃபைவ் ஜி), endings joined (நாற்பதுக்கும், ...ஒன்றில், ரூபாய்க்கு), நெ. -> எண் |
| 2026-11-12 | `8ed41aa` | voice: 'பிளஸ் 2' is read 'பிளஸ் டூ' (was 'பிளஸ் இரண்டு', RN-534); 'பிளஸ் 1' -> 'பிளஸ் ஒன்' |
| 2026-11-12 | `fbcb1a9` | direct upload: create the resumable container on a versioned Instagram API (Salem RN-1: unversioned call wanted video_url; fell back to the link correctly) |
| 2026-11-12 | `4144f71` | reel: spoken follow line names this page (was 'Follow Coimbatore Three Sixty'); waiting reels rebuilt |
| 2026-11-12 | `e1efec6` | powercut: notices written |
| 2026-11-12 | `47f9be2` | stories shared |
| 2026-11-12 | `6defe2d` | powercut: notices written |
| 2026-11-12 | `87f2261` | powercut: notices written |
| 2026-11-12 | `21412f7` | TRIAL: direct reel upload ON for this new page (file instead of Cloudinary link; falls back to the link; never posts twice) |
| 2026-11-12 | `91de910` | cloudinary: keep the last 48 h only, clean once every 48 h (own workflow; hourly step removed) |
<!-- recent-changes:end -->
