"""20 Nov: Erode RN-163 (a power-cut list) had a 2,356-character caption - Instagram refused the reel 3 times. Every caption now fits."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "poster"), str(ROOT / "research_free")]
import post      # noqa: E402

AREAS = ", ".join(f"ஊர்{i} நகர்" for i in range(400))
CAP = ("⚡ நாளை கஸ்பாபேட்டை பகுதிகளில் மின் தடை\n\n📰 முழு விவரம்:\nபராமரிப்புப் பணிகள்.\n\n🏘️ கஸ்பாபேட்டை துணை மின் நிலையம்: " + AREAS
       + "\nPower cut tomorrow in Kasipalayam | Erode news\n\n#Erode #Kodumudi #ErodePowerCut #ஈரோடு #Erode360\n\n📰 Source: தினமணி (20 நவம்பர் 2026)")


def test_long_caption_fits_and_keeps_the_end():
    out = post.fit_caption(CAP)
    assert post.ig_len(out) <= 2200
    assert out.endswith("#Erode #Kodumudi #ErodePowerCut #ஈரோடு #Erode360\n\n📰 Source: தினமணி (20 நவம்பர் 2026)")
    assert "Power cut tomorrow in Kasipalayam | Erode news" in out
    body = out.split("\nPower cut")[0]
    assert body.rstrip().endswith("நகர்…")      # cut after a whole area, never in the middle of a word


def test_short_caption_untouched():
    short = "செய்தி\n\n#Erode #Erode360"
    assert post.fit_caption(short) == short


def test_emoji_counted_as_instagram_counts():
    assert post.ig_len("📰") == 2 and post.ig_len("சேலம்") == 5
