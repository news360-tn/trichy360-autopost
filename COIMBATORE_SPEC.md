# Coimbatore 360 – conversion spec (shared by everyone working on this copy)

This folder is a COPY of the Namakkal project (`../news360-autopost`). It becomes a separate, fully independent project
for one Instagram page about **Coimbatore district** news. The Namakkal / Rasipuram project must never be touched or affected.

## Hard rules
- Edit files ONLY inside `/home/icliniq/Music/Workspace/Personal/coimbatore360-autopost`. Never write to `../news360-autopost`.
- No git commands that change anything (no init/commit/push). No posting, no Sheet/Instagram/bridge calls, no paid API calls.
- Keep the same file structure, function names and code style as the Namakkal project (so Namakkal fixes can be ported later by diff).
  Change values and Namakkal-only logic; do not restructure.
- Nothing may run live: no `LIVE` file, no `research_free/ENABLED` file.

## The page (placeholders until the owner decides; keep them in ONE place per file, easy to change)
| Item | Value |
|---|---|
| Page key (code) | `coimbatore` (replaces `namakkal`; there is NO second page – Rasipuram logic and collab are removed / always off) |
| Page label | `கோயம்புத்தூர் 360` |
| Hashtag | `#Coimbatore360` |
| Instagram handle | `coimbatore360_official` (placeholder) |
| Spoken follow line | `மேலும் செய்திகளுக்கு கோயம்புத்தூர் த்ரீ சிக்ஸ்டி பக்கத்தை பின்தொடருங்கள்` |
| Caption save/follow line | `கோயம்புத்தூர் செய்திகளைத் தவறவிடாமல் இருக்க Save செய்து Follow செய்யுங்கள் 📌` |
| Logo / footer files | `kit/logo_coimbatore.png`, `reel/assets/footer_coimbatore.png` (simple placeholder images until the owner sends real ones) |
| post_to value in the Sheet | `Coimbatore 360` |
| Sheet columns | same 31 columns; `namakkal_link` is renamed `coimbatore_link`; `rasipuram_link` is renamed `spare_link` (unused) |
| Apps Script token property | `IG_TOKEN_COIMBATORE` |
| Website | OFF for now (website.py must do nothing when `WEBSITE_INGEST_KEY` is missing; workflows do not pass it) |

## District
- Only Coimbatore-district news, published today or yesterday (same freshness rules as Namakkal).
- **Owner 29 Oct: start with Coimbatore CITY only** (`CITY_ONLY: "1"` in the workflows; `allnews.outside_city`). Towns outside the city (Pollachi, Mettupalayam, Sulur, Annur, Valparai ...) are skipped unless a city area is named; "கோவை" alone stays. Whole district later: set `CITY_ONLY: "0"`.
- Coimbatore places (Tamil): கோவை, கோயம்புத்தூர், பொள்ளாச்சி, மேட்டுப்பாளையம், சூலூர், அன்னூர், கிணத்துக்கடவு, மதுக்கரை, பேரூர், தொண்டாமுத்தூர்,
  ஆனைமலை, வால்பாறை, காரமடை, கருமத்தம்பட்டி, சிறுமுகை, பெரியநாயக்கன்பாளையம், துடியலூர், காந்திபுரம், ஆர்.எஸ்.புரம், உக்கடம், சிங்காநல்லூர்,
  பீளமேடு, சரவணம்பட்டி, போத்தனூர், குனியமுத்தூர், வடவள்ளி, கவுண்டம்பாளையம், சாய்பாபா காலனி, டவுன்ஹால், ஒண்டிப்புதூர், இருகூர், நீலாம்பூர்,
  செட்டிபாளையம், வெள்ளலூர், மருதமலை, வெள்ளியங்கிரி, ஆழியாறு, டாப்சிலிப், நெகமம், கோவில்பாளையம், சோமனூர், எட்டிமடை, தடாகம், ஆலாந்துறை,
  கணுவாய், காளப்பட்டி, வேடப்பட்டி, ஜோதிபுரம்.
- English: Coimbatore, Kovai, Pollachi, Mettupalayam, Sulur, Annur, Valparai, Kinathukadavu, Madukkarai, Perur, Thondamuthur, Anaimalai,
  Karamadai, Singanallur, Peelamedu, Gandhipuram, Ukkadam, Saravanampatti, Podanur, Vadavalli, Thudiyalur, Periyanaickenpalayam, Sirumugai,
  Karumathampatti, Aliyar, Topslip, Marudhamalai.
- Other districts (NOT ours, even though close): திருப்பூர், அவிநாசி, பல்லடம், உடுமலை, தாராபுரம், காங்கேயம், நீலகிரி, ஊட்டி, குன்னூர், கோத்தகிரி, ஈரோடு,
  சத்தியமங்கலம், கோபி, பவானி, பாலக்காடு, நாமக்கல், திருச்சி, கரூர் ... plus the rest of Tamil Nadu / Kerala / Karnataka (reuse the Namakkal OTHER_PLACES
  list, remove the Coimbatore names from it, add Namakkal-district names and the list above).
  Note: "அவிநாசி சாலை" / "Avinashi Road" is a road inside Coimbatore city - a headline that also names a Coimbatore place is ours.
- Newspaper district pages: Dinamalar `https://www.dinamalar.com/news/tamil-nadu-district-news-coimbatore`; link districts `coimbatore` / `kovai`.
- Searches: the Namakkal QUERIES pattern with Coimbatore places, incl. TNEB power cuts (`கோவை மின்தடை`, `பொள்ளாச்சி மின்தடை`, `மேட்டுப்பாளையம் மின்தடை`,
  `Coimbatore power shutdown`), jobs (`கோவை வேலைவாய்ப்பு முகாம்`, `கோவை ஆட்சேர்ப்பு`), Collector (`கோவை ஆட்சியர் அறிவிப்பு`, `Coimbatore collector`).
- Namakkal-only content (egg price centre rule, Kolli Hills, Rasipuram area routing, Rasipuram page) is removed or neutral.

## Priority (from Namakkal insights)
power cut (TNEB) > crime > accident > civic > the rest. `research_free/learned.py` already has power_cut/jobs with PRIOR +1.0; keep it.
Daily cap 50 reels (Instagram's limit; owner 29 Oct: do not miss city news) - `DAILY_CAP` in the workflows.

## Voice – FREE ONLY
Valluvar (edge-tts `ta-IN-ValluvarNeural`) for every reel. Google Charon is never used: remove `reel_voice_alt` from config and make
`pick_voice()` never return Google (also when GOOGLE_TTS_API_KEY exists). Workflows do not pass GOOGLE_TTS_API_KEY.

## Images – ONE image per reel, free first
- The writer produces exactly ONE clear image prompt per story: the main scene of THIS news (place type, event, people), photo-realistic,
  no text/letters/logos/watermark. (Namakkal makes 3 scene prompts; Coimbatore makes 1.)
- Generation order: Cloudflare Workers AI FLUX schnell (free) -> NVIDIA FLUX (free credits) -> only if both fail: FAL `fal-ai/flux/schnell`
  (cheapest paid) -> FAL `fal-ai/flux/dev`.
- Picture check (`imagegen.matches`, free Gemini) as in Namakkal; a non-matching picture is made again (free sources), then used anyway.
- The reel is built from that one image: different camera moves / crops of the same picture per scene; headline cards, subtitles, logo as before.
- No carousel (reel only).

## Writing – FREE ONLY
Free LLM chain as in Namakkal. Claude backup OFF (workflows do not pass ANTHROPIC_API_KEY and set CLAUDE_MAX_CALLS=0).

## Tests
`python3 -m unittest discover -s tests` must pass. Namakkal-specific regression tests are converted to Coimbatore equivalents (or removed when
the rule does not exist here), plus new tests: Coimbatore district check, Tiruppur/Nilgiris rejected, single page / no collab, Valluvar only,
one image per story, free-first image order.
