# Trichy 360 — views and followers plan (27 Nov 2026)

> **Update 27 Nov evening (owner):** the 6 voices and the 11 topic colour themes are switched off - Valluvar and design A only,
> like the other pages (`reel_voice.ab_voices_off_27nov`, `views_test.topic_themes_off_27nov` keep them). `hook_low` is off.
> Fixed after an audit of the posted reels: first picture change at 1.2 s, 2 s end card, no clock-hand sweep with `cycle_pictures`,
> captions timed from the voice's own word clock (`reel/edge_words.py`). New colour designs are waiting for the owner's pick.

Trichy page only, on Instagram, Facebook and YouTube. The other pages get these changes only after Trichy proves them.
Not changed: the posting limits (pick 30 a day, post cap 35) and the posting times.

## What the data said

Instagram, 141 news reels, 13–26 Nov:
- Watch time decides views. Watched under 5 s: median about 380 views (67% under 500). Watched 10–15 s: 6,200. Watched 15 s or more: 10,800.
- Shares decide views. Share rate under 0.5% of reach: median 586. Over 5%: 9,084.
- Followers come from big reels. The +715 and +619 follower days each had one reel of 41,000–58,000 views.
- 96% of reach is non-followers, so recommendation works.
- Soft news (meetings, statements, functions) stays under 500 at any length.
- Rasipalan: median 203 views, 0 shares in 14 reels. Gold rate: median 534.
- Supply: about 12 news a day were found, against the 30 allowed.

Audit of the posted reels: the first 4–6 s showed one still picture with the headline covering it, and a 6 s still logo card ended every reel. Fact cards were wrong ("கரூர்" showed a ₹ card).

Facebook (7 followers) and YouTube (new) had no per-video numbers, so nothing could be compared there.

## Built on 27 Nov (all switchable in `poster/config.json` → `views_test`)

| Change | Where | Switch |
|---|---|---|
| 11 news themes by topic: accident, police, rain, power cut, temple, government, civic, education, jobs, farming, sports. Topic "other" rotates A / B / C / P | `reel/reel4.py` | `topic_themes`, `styles` |
| Design C readable on bright photos | `reel/reel4.py` | — |
| Headline under the picture's subject; big headline at most 3 s | `reel/reel4.py` | `hook_low`, `hook_max_s` |
| A different picture at every cut (about 1.9 s) | `reel/reel4.py` | `cycle_pictures` |
| Captions only after the big headline | `reel/reel4.py` | `clean_hook` |
| One Tamil share + follow line naming the reel's town, shown as captions too; still logo card only the last 2 s (was 6 s) | `reel/reel4.py` | `end_line_ta`, `end_card_s` |
| 6 free Tamil voices (India, Malaysia, Singapore; man and woman each), one per story | `reel/reel4.py` | `reel_voice.ab_voices` |
| Fact-card labels fixed (Karur, "மக்கள்", "தினமணி") | `reel/reel4.py` | — |
| Prebuilt reels keep their voice / design for the comparison | `poster/post.py` | — |
| YouTube titles cut at a word end; the topic word comes from the headline | `poster/youtube.py` | — |
| Facebook reel plays / watch time / follows and YouTube Short views read daily | `poster/platform_stats.py`, `insights.yml` | — |
| Comparison tool covers Facebook and YouTube | `tools/views_test.py` | — |
| Rasipalan opens with all 12 rasis and today's stars; panchangam after the rasis | `rasipalan/rasi360_render.py` | `rasi_grid` |
| Gold reel shows today's ▲/▼ change big from frame 0 | `goldrate/gold360_render.py` | `gold_change_first` |
| News supply: search results of the last 24 h, all taluk towns searched, writer failures retried, more Trichy places, dropped links logged | `research_free/pick.py`, `allnews.py` | `PICK_SEARCH_HOURS`, `PICK_TOWN_GOOGLE`, `PICK_DECODE_MAX`, `PICK_WRITER_RETRIES` |

Checked before commit: full reels rendered with voice (accident theme), still frames of all themes on a bright photo, gold and rasipalan reels rendered. Tests: full suite plus `tests/test_views_27nov.py` and `tests/test_supply_27nov.py`.

## Measure (from 4 Dec)

`python3 tools/views_test.py` — Instagram by voice, design, length and topic; Facebook and YouTube per day.

Keep a voice or theme only when, after 7 days and at least 15 reels, its median watch time is at least the page median. Remove the rest from config.

Targets (not promises): reels under 500 views from 35% to under 20%; median watch time from 6.1 s to 9 s; Facebook and YouTube show a measurable daily total.

## Next, after a week of data

1. Writer rules: headline at most 32 characters; soft news must open with what changes for people.
2. Trial Reels through the API for weak topics (`trial_params.graduation_strategy = SS_PERFORMANCE`).
3. Deeper Dinamani / Dinamalar listing pages (needs a live look at the pages).
4. YouTube: set `containsSyntheticMedia` for AI pictures; read average view duration from the Analytics API.
5. Owner checks: Instagram Account Status (can be recommended), Facebook Page Status.
