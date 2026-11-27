"""owner 27 Nov evening: one news line in the free edge-tts voice WITH the word clock of the voice.
The captions were timed by letter count, so they ran ahead of / behind the voice; the voice service also tells when each word
is spoken (WordBoundary), and reel4.py times the captions from that.

  python3 edge_words.py <voice> <rate> <pitch> <text> <out.mp3> <out.json>
out.json: {"words": [[word, start_s, end_s], ...]} (times from the start of the mp3). Exit 1 when the voice service fails."""
import asyncio
import json
import sys

import edge_tts


async def _say(voice, rate, pitch, text, mp3, js):
    words, audio = [], bytearray()
    c = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch, boundary="WordBoundary")
    async for ch in c.stream():
        if ch["type"] == "audio":
            audio += ch["data"]
        elif ch["type"] == "WordBoundary":
            a = ch["offset"] / 1e7
            words.append([ch["text"], round(a, 3), round(a + ch["duration"] / 1e7, 3)])
    if len(audio) < 1000:
        raise RuntimeError("no audio")
    with open(mp3, "wb") as f:
        f.write(audio)
    with open(js, "w", encoding="utf-8") as f:
        json.dump({"words": words}, f, ensure_ascii=False)


if __name__ == "__main__":
    try:
        asyncio.run(_say(*sys.argv[1:7]))
    except Exception as e:
        print("edge voice failed:", str(e)[:160], file=sys.stderr)
        sys.exit(1)
