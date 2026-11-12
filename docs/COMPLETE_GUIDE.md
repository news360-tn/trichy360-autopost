# Coimbatore 360 – Complete Guide (கோயம்புத்தூர் 360, Coimbatore district)

Bridge Gmail (receives your e-mails and sends replies): **the new Coimbatore 360 Google account** (set `OWNER_EMAIL` in `apps_script/Code.gs`;
never the Namakkal Gmail).
Sheet (all stories and status): the new "Coimbatore 360 Log" Sheet (its id goes into `SHEET_ID` in `apps_script/Code.gs`).

All e-mail subjects use the tag **COIMBATORE360** (Namakkal uses NEWS360). Never mix them: a `NEWS360 STORY` mail would go to Namakkal.

---

## 0. Three ways to get a story onto Instagram

| Way | Who makes it | What you send by e-mail | Speed |
|---|---|---|---|
| **A. Automatic collecting** (every 2 hours, written every 20 minutes) | The system: free AI models only (Claude is off) | Nothing. The one image is made automatically (free first). Only if no image can be made you get `[COIMBATORE360 IMAGES NEEDED]` | Posted automatically |
| **B. Your own story** (you or a friend, when you want) | You (or an AI with web search) → you make ONE image → you e-mail | E-mail `COIMBATORE360 STORY`: JSON + 1 image | Posted within ~30 min of your e-mail |
| **C. Ready reel** (you already made the video and caption) | You | E-mail `COIMBATORE360 REEL`: zip with one `.md` (caption) + one video `.mp4` | Posted as it is, within ~30 min |

Posting itself is always automatic (every 5 minutes it looks for ready stories) once the `LIVE` file exists. Every post passes the Instagram duplicate check first.
Format: **reel only** (no carousel), one page **கோயம்புத்தூர் 360**, no collaborator.

---

## 1. Pause and start the automatic collecting

Pausing only stops the automatic collecting and writing (way A). Posting of stories you send (B and C) and of already queued stories continues.

1. Open the Coimbatore 360 repository on GitHub → tab **Actions**.
2. Left side: **collect-switch**.
3. Button **Run workflow** → choose:
   - `pause` → automatic collecting stops.
   - `start` → automatic collecting starts again (every 2 hours).
4. The summary of the run says: "Automatic collecting: ON" or "PAUSED".
5. Phone: same page in the GitHub app or mobile browser.

Full stop (posting too): remove the `LIVE` file, or repository **Settings → Secrets and variables → Actions → Variables** → set `PAUSED` = `true`.

---

## 2. Way A – automatic collecting (when ON)

- Every 4 hours the collector reads all **Coimbatore-district** news. It keeps only news that names a Coimbatore-district place and is today's or yesterday's.
  Tiruppur, Avinashi town, Palladam, Udumalai, Nilgiris (Ooty, Coonoor), Erode, Palakkad and every other district are skipped, even when close.
- Priority: **power cut (TNEB) > crime > accident > civic > the rest.**
- Free AI models write the story. A model that is slow, gives unreadable answers or is over quota is skipped for a while automatically. Claude is never used here.
- One image per story: Cloudflare FLUX schnell (free) → NVIDIA FLUX (free credits) → only if both fail, FAL (paid, cheapest first). The picture is checked against the news (free Gemini); a wrong picture is made again.
- Voice: **Valluvar** (free) for every reel.
- A story is never posted if: its date has passed (power cut of yesterday, job fair over), the same news is already posted, or the source check fails.

Daily cap: **50 reels a day** (Instagram's limit) (`DAILY_CAP` in `post.yml`). Important news first; a story waiting for the cap is posted later, not lost.

---

## 3. PROMPT 1 – collect today's news (give to an AI with web search ON)

Use this when you collect news yourself (way B).

```
You write Tamil local-news posts for the Instagram page "கோயம்புத்தூர் 360" (Coimbatore 360, Coimbatore district, Tamil Nadu).

TASK
1. Search the web for TODAY'S and the last 24 hours' news of ALL Coimbatore district places: Coimbatore city (Gandhipuram, RS Puram, Ukkadam, Singanallur, Peelamedu, Saravanampatti, Podanur, Vadavalli, Thudiyalur, Town Hall ...), Pollachi, Mettupalayam, Sulur, Annur, Valparai, Kinathukadavu, Madukkarai, Perur, Thondamuthur, Anaimalai, Karamadai, Sirumugai, Karumathampatti, Periyanaickenpalayam and every village of the district.
2. Do NOT miss anything important, in this order: TNEB power cuts, job camps / recruitment, accidents, crime, weather / rain alerts, then Collector notices, schools/colleges, transport, health, prices, festivals, road closures.
3. Skip: news outside Coimbatore district (Tiruppur, Nilgiris, Erode, Palakkad ... are NOT ours), old news (before the last 24 hours), national/world news, opinion, advertisements.
4. Use ONLY facts stated in the articles you read. Never invent a name, number, place, date, cause or quote. If a fact is unclear, leave it out.
5. Give every story a real article link.

WRITE
- Full place names always (பொள்ளாச்சி, மேட்டுப்பாளையம், கிணத்துக்கடவு, பெரியநாயக்கன்பாளையம்).
- Role names in full when spoken: ஆர்.டி.ஓ. → வருவாய் கோட்டாட்சியர், எஸ்.பி. → காவல் கண்காணிப்பாளர்.
- Plain, readable Tamil. Short sentences. No English words in the reel script.

OUTPUT: ONE JSON object only (no explanation):
{
 "stories": [
  {
   "tamil_headline": "clear Tamil headline, full place names",
   "english_headline": "short English headline",
   "category": "Tamil category, e.g. மின் தடை / வேலைவாய்ப்பு / விபத்து / குற்றம் / வானிலை",
   "location": "place, taluk, Coimbatore district",
   "importance": "High | Medium | Low",
   "post_to": "Coimbatore 360",
   "source": "https://the-article-link",
   "published": "date of the news, e.g. 24 Oct 2026",
   "slides_spec": {
     "v": 3, "cat": "same as category", "loc": "short place name",
     "hl1": "headline line 1, max 40 characters",
     "hl2": "headline line 2, max 28 characters",
     "slides": [ {"title": "max 18 characters", "lines": ["2 or 3 short lines, each max 60 characters"]} ]
   },
   "reel_script": "85-120 Tamil words: 7-9 sentences giving every detail (hook, who, exact place, when, how, numbers, action, what next). NO digits and NO English letters (write numbers in Tamil words). Strong hook in the first sentence, no greeting. Must end with exactly: மேலும் செய்திகளுக்கு கோயம்புத்தூர் த்ரீ சிக்ஸ்டி பக்கத்தை பின்தொடருங்கள்.",
   "caption": "emoji heading line, then 3-5 short fact lines, then a line: 📍 place | date, then 3-5 hashtags on one line (include #Coimbatore360), last line: கோயம்புத்தூர் செய்திகளைத் தவறவிடாமல் இருக்க Save செய்து Follow செய்யுங்கள் 📌",
   "prompts": ["ONE image prompt: the main scene of this news (see Prompt 2 rules)"]
  }
 ]
}

RULES
- slides: 3 or 4 (they become the headline cards of the reel). prompts: exactly ONE.
- No newspaper, TV or website names and no links in any field except "source".
- No "comment below" / "கமெண்டில்" lines.
- If there is no new important news in the district, return: {"stories": []}
```

## 4. PROMPT 2 – make the ONE image (ChatGPT or any image tool)

```
Make ONE single photograph (not a collage, no panels, no strips, no borders):
- tall vertical 9:16 portrait, 1080x1920 or larger, maximum clarity, tack-sharp, photorealistic;
- the main scene of the news: the place type (city road, bus stand, farm, hills, factory, office), the event, people only from behind or far away;
- NO text, letters, numbers, logos, watermarks or captions in the image; no blood, injuries or dead bodies;
- do NOT crop, resize or edit it afterwards. Name the file S1_1.png (or RN-xx_1.png when the e-mail asks for that name).

Scene: <paste the prompt here>
```

One image per story is enough: the reel uses different camera moves and crops of it.

---

## 5. Way B – send your own story (e-mail with the image)

1. Get the JSON (Prompt 1) and make the image (Prompt 2).
2. Send **one e-mail** to the Coimbatore 360 bridge Gmail
   - **Subject:** `COIMBATORE360 STORY` (any words after it are fine)
   - **Body:** the JSON (paste it as text). For several stories use `{"stories":[ ... ]}`.
   - **Attachments:** the image (png/jpg) or one zip. Several stories in one e-mail: name the images `S1_1.png`, `S2_1.png` … (S1 = first story in the JSON).
   - **One story per e-mail** is the safest.
3. Within about 5 minutes you get `[COIMBATORE360 STORY RECEIVED]`:
   - `ADDED RN-xx` → it will be built and posted automatically (reel and voice are made by the system).
   - `NOT ADDED` → the exact problem is written (headline too long, digits in reel script, `post_to` not `Coimbatore 360`, duplicate of RN-xx, no image). Fix and send again.
4. Post checks before publishing: Instagram duplicate check, source fact check (if `source` has a link), Tamil text check, reel check (1080x1920, voice present).

Sender permission: the `OWNER_EMAIL` address is always allowed. Another person's address must be in the Apps Script property `ALLOWED_SENDERS` (comma-separated).

---

## 6. Way C – ready reel (video + caption made by you)

Nothing is rebuilt; the video is posted exactly as it is, on கோயம்புத்தூர் 360.

1. Make a folder with exactly:
   - `caption.md` – the caption text (a `PAGE:` line is not needed; there is only one page). Max 5 hashtags.
   - `reel.mp4` – the video: **1080 x 1920 (9:16), 10 to 90 seconds, with voice**, not silent, not clipped.
2. Put both files in ONE zip. One zip = one caption; several videos in one zip become one reel each with the same caption.
3. Check the video yourself before sending (voice clear, Tamil words correct, the place and time right, the end line there).
4. Send **one e-mail** to the Coimbatore 360 bridge Gmail, **Subject:** `COIMBATORE360 REEL`, the zip attached (or the two files). Body: nothing needed.
5. Within about 5 minutes you get `[COIMBATORE360 REEL RECEIVED]` with `ADDED RN-xx` or the exact problem.
6. Just before posting, the system reads the page's recent Instagram captions. If the same news is already on the page, it is **not posted**.

Large video (over 25 MB): put the zip in Google Drive, share it, and paste the link in the e-mail body. The system reads Drive links.

---

## 7. Reel template and voice

- Size 1080 x 1920, 9:16. The one image is shown with different slow camera moves and crops per scene; the headline and key facts appear as Tamil cards and subtitles; the கோயம்புத்தூர் 360 logo at the corner and the footer at the bottom.
- Voice: **Valluvar** (free edge-tts) for every reel. Numbers and dates are read clearly with the month.
- At most 90 seconds, ending with the fixed follow line: மேலும் செய்திகளுக்கு கோயம்புத்தூர் த்ரீ சிக்ஸ்டி பக்கத்தை பின்தொடருங்கள்.
- Every built reel is checked: size, duration, voice present, not silent, not clipped.

---

## 8. Caption format (all ways)

```
⚡ Emoji heading line

Fact line 1.
Fact line 2.
📍 Place, Coimbatore | date
#Coimbatore360 #Coimbatore #tag3
கோயம்புத்தூர் செய்திகளைத் தவறவிடாமல் இருக்க Save செய்து Follow செய்யுங்கள் 📌
```
Max 5 hashtags. No "comment below" lines.

---

## 9. Daily routine (what you do)

1. Nothing for way A: collecting, writing, the image and posting are automatic.
2. When you have news yourself: e-mail `COIMBATORE360 STORY` (way B) or `COIMBATORE360 REEL` (way C).
3. Check the `[RECEIVED]` replies for `NOT ADDED` / `DUPLICATE`.
4. Check the Sheet column `post_status` once a day: `Posted`, `Queued`, `Auto images`, `Awaiting images`, `Skipped`.

---

## 10. Quick troubleshooting

| What you see | What it means | What to do |
|---|---|---|
| No reply e-mail after 15 min | Apps Script is not checking | check Apps Script triggers (`processReplies` every 5 min) and that `OWNER_EMAIL` is set |
| `NOT ADDED … image` | no image found | send the image again |
| `DUPLICATE of RN-xx` | same news already in the Sheet | nothing; it will not be posted twice |
| `Checks failed` in Sheet notes | a text or fact check failed | the story is not posted; fix or drop it |
| `LIMIT` / daily cap in the log | 50 reels today reached | story waits; posted automatically later |
| `Instagram token refresh failed` e-mail | the 60-day token could not be refreshed | make a new token and save it as `IG_TOKEN_COIMBATORE` |
| Nothing posts at all | not live yet | the `LIVE` file must exist (README setup checklist) |

---

## 11. Model and cost rules

- Free models only for writing (Gemini, Groq, NVIDIA, Cloudflare, Mistral, OpenRouter, GitHub Models). Claude is off.
- Images: free Cloudflare / NVIDIA first; paid FAL only as the last fallback (one image per reel keeps it cheap).
- Voice: Valluvar (free). Google voice is never used.
- Use Coimbatore 360's own API keys, so Namakkal 360's free limits are never used up.
