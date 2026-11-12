# Manual story → e-mail (Coimbatore 360; use when automatic collecting is PAUSED, or for extra news)

All e-mails go to the **Coimbatore 360 bridge Gmail** (the new Google account, `OWNER_EMAIL` in `apps_script/Code.gs`) and use the tag
**COIMBATORE360** in the subject. Never send `NEWS360 ...` subjects for Coimbatore: those belong to the Namakkal project.

## 1. Pause / start automatic collecting
GitHub → the Coimbatore 360 repository → **Actions** → **collect-switch** → **Run workflow** → choose
`pause` (automatic collecting/writing stops, posting continues) or `start` (automatic collecting again). Same page on the phone.

## 2. Make the news with another AI (web search ON)
Paste the prompt below, add the news text / link at the end. It gives ONE JSON. Make ONE image (ChatGPT or any image tool, 9:16,
photo-realistic, the main scene of the news, no text/logos).

## 3. Send ONE e-mail to the Coimbatore 360 bridge Gmail (from your allowed address)
- Subject: `COIMBATORE360 STORY` (anything after it is fine)
- Body: paste the JSON (or attach it as story.json)
- Attach the image (png/jpg) or one zip. One story per e-mail. (Several stories in one e-mail: `{"stories":[...]}` and name the images S1_1.png, S2_1.png …)
- Within ~5 minutes you get **[COIMBATORE360 STORY RECEIVED]**: ADDED RN-xx, or the exact problems / DUPLICATE warning. Then it is posted automatically
  as a reel on கோயம்புத்தூர் 360 (Instagram recent-captions duplicate check + source fact check run first; an already posted news is never posted again).
- The sender must be the owner address (`OWNER_EMAIL`) or listed in Script property `ALLOWED_SENDERS`.

## Prompt for the other AI
```
You write Tamil local-news posts for the Instagram page "கோயம்புத்தூர் 360" (Coimbatore 360, Coimbatore district, Tamil Nadu).
Only Coimbatore-district news (Coimbatore city, Pollachi, Mettupalayam, Sulur, Annur, Valparai, Kinathukadavu, Madukkarai, Perur,
Thondamuthur, Anaimalai, Karamadai ...). Tiruppur, Nilgiris, Erode, Palakkad and other districts are NOT ours.
Use ONLY facts from the news below (search the web to confirm). Never invent a name, number, place or cause. If a fact is unclear, leave it out.
Write ONE JSON object only (no explanation) with exactly these keys:
{
 "tamil_headline": "...",            // clear Tamil headline, full place names (பொள்ளாச்சி, மேட்டுப்பாளையம், கிணத்துக்கடவு - never short forms)
 "english_headline": "...",
 "category": "...",                  // Tamil, e.g. மின் தடை, வேலைவாய்ப்பு, விபத்து, குற்றம், வானிலை
 "location": "place, taluk, Coimbatore district",
 "importance": "High|Medium|Low",
 "post_to": "Coimbatore 360",             // always exactly this (one page, no collaborator)
 "source": "https://link-of-the-news-article",          // used only for the fact check, never shown
 "slides_spec": {"v":3,"cat":"...","loc":"short place","hl1":"max 40 chars","hl2":"max 28 chars",
   "slides":[{"title":"max 18 chars","lines":["2-3 short lines, each max 60 chars"]}]},   // 3 or 4 slides (the reel's cards): who/what/when/where/why/how
 "reel_script": "...",               // 85-120 Tamil words, 7-9 sentences with every detail, NO digits and NO English letters (write numbers in Tamil words), strong hook in the first sentence (no greeting), short sentences, plain words, ends with exactly: மேலும் செய்திகளுக்கு கோயம்புத்தூர் த்ரீ சிக்ஸ்டி பக்கத்தை பின்தொடருங்கள்.
 "caption": "..."                    // emoji heading, 3-5 short lines with facts, then a line 📍 place | date, then 3-5 hashtags (include #Coimbatore360), last line: கோயம்புத்தூர் செய்திகளைத் தவறவிடாமல் இருக்க Save செய்து Follow செய்யுங்கள் 📌
}
Rules: no newspaper/TV/website names or links in any text field except "source"; no "comment below" lines; readable plain Tamil.
NEWS:
<paste the news text or link here>
```
(The bridge adds the follow line / save line itself if they are missing, and refuses digits or English letters in the reel script,
fewer than 85 or more than 120 words, fewer than 3 or more than 5 hashtags, or a `post_to` other than `Coimbatore 360`.)


---
# READY REEL (video + caption already made) - post as it is
E-mail to the Coimbatore 360 bridge Gmail, subject `COIMBATORE360 REEL`, attach ONE zip containing ONE `.md` (the caption) and the video (`.mp4`).
No `PAGE:` line is needed (there is only one page; a `PAGE:` line is ignored).
Within ~5 minutes: **[COIMBATORE360 REEL RECEIVED]** ADDED RN-xx (or the problem). Just before posting, the page's recent Instagram captions
are read: if the same news is already there it is NOT posted (the Sheet row says so). Otherwise the video is posted exactly as it is, with your caption
(standard rule: max 5 hashtags, #Coimbatore360 added).
