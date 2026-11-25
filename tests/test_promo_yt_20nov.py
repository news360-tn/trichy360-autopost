"""owner 20 Nov: promotion ads (only what the owner approved, on the chosen pages and dates) + the YouTube details e-mail"""
import json
import os
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "poster"))
sys.path.insert(0, str(ROOT / "reel"))

import promo      # noqa: E402
import promo360   # noqa: E402
import youtube    # noqa: E402

P = {"id": "PR-1", "status": "approved", "pages": "namakkal,salem", "brand": "Sri Textiles", "title": "Deepavali sale",
     "message": "50% off on all sarees", "start": "2026-11-20", "end": "2026-11-22", "per_day": "3"}


class Choose(unittest.TestCase):
    def test_only_approved_on_its_pages_and_dates(self):
        self.assertEqual(promo.choose([P], {}, "namakkal", "2026-11-21")["id"], "PR-1")
        self.assertIsNone(promo.choose([P], {}, "erode", "2026-11-21"))            # not chosen for this page
        self.assertIsNone(promo.choose([P], {}, "namakkal", "2026-11-19"))         # before its start date
        self.assertIsNone(promo.choose([P], {}, "namakkal", "2026-11-23"))         # after its end date
        for st in ("sample_needed", "sample_sent", "changes", "stopped"):
            self.assertIsNone(promo.choose([dict(P, status=st)], {}, "namakkal", "2026-11-21"), st)

    def test_reels_a_day_limit(self):
        self.assertIsNone(promo.choose([P], {"PR-1|namakkal|2026-11-21": 3}, "namakkal", "2026-11-21"))
        self.assertIsNotNone(promo.choose([P], {"PR-1|namakkal|2026-11-21": 2}, "namakkal", "2026-11-21"))
        self.assertIsNotNone(promo.choose([P], {"PR-1|salem|2026-11-21": 3}, "namakkal", "2026-11-21"))      # per page
        self.assertIsNotNone(promo.choose([dict(P, per_day="all")], {"PR-1|namakkal|2026-11-21": 99}, "namakkal", "2026-11-21"))

    def test_no_hub_no_ad(self):
        with mock.patch.dict(os.environ, {"PROMO_URL": "", "PROMO_KEY": ""}):
            self.assertIsNone(promo.active_for("namakkal"))
        with mock.patch.dict(os.environ, {"PROMO_URL": "https://x", "PROMO_KEY": "k"}), \
                mock.patch.object(promo, "promos", side_effect=RuntimeError("hub down")):
            self.assertIsNone(promo.active_for("namakkal"))      # never stops the reel

    def test_caption_says_sponsored(self):
        cap = promo.with_line("Headline\n\nbody\n#tag", P)
        self.assertEqual(cap.split("\n")[:2], ["Headline", "🤝 Sponsored: Sri Textiles"])
        self.assertEqual(promo.with_line(cap, P), cap)


PAGE = ("<html><head><style>body{}</style></head><body><div id='foot'></div>"
        "<script>const D={end_t:20};window.renderAt=function(t){};</script></body></html>")


class AdOnTheReel(unittest.TestCase):
    def test_bottom_during_news_footer_hidden(self):
        out = promo360.add(PAGE, {"title": "Deepavali <sale>", "message": "50% off", "image": ""})
        self.assertIn('id="adbox"', out)
        self.assertIn("top:1548px", out)                       # the big space at the bottom
        self.assertIn("t>=3&&t<e", out)                        # during the news only, never on the FOLLOW end card
        self.assertIn("ft.style.visibility", out)              # the footer logo strip hidden while it shows
        self.assertIn("Deepavali &lt;sale&gt;", out)
        self.assertEqual(promo360.add(out, {"title": "x"}), out)      # only once

    def test_safe(self):
        self.assertEqual(promo360.add(PAGE, None), PAGE)
        self.assertEqual(promo360.add("<html>no player</html>", {"title": "x"}), "<html>no player</html>")


class Wiring(unittest.TestCase):
    def test_post_and_reel(self):
        post = (ROOT / "poster" / "post.py").read_text(encoding="utf-8")
        self.assertIn("PROMO_NOW = promo.active_for(PAGE)", post)
        self.assertIn('env["PROMO_JSON"]', post)
        self.assertIn("promo.mark_used(PROMO_NOW, PAGE, sid)", post)
        self.assertIn('"quiet": posted_quiet()', post)
        reel = (ROOT / "reel" / "reel4.py").read_text(encoding="utf-8")
        self.assertIn("promo360.add(page.read_text()", reel)
        wf = (ROOT / ".github" / "workflows" / "post.yml").read_text(encoding="utf-8")
        self.assertIn("PROMO_URL: ${{ secrets.PROMO_URL || ", wf)
        gs = (ROOT / "apps_script" / "Code.gs").read_text(encoding="utf-8")
        self.assertIn("if (!b.quiet) GmailApp.sendEmail(OWNER_EMAIL", gs)
        cfg = json.loads((ROOT / "poster" / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(cfg["reel_design"], "v4")
        self.assertEqual(cfg["posted_email"], "combined")      # owner 25 Nov: ONE e-mail per news with all three links


def m(ts, cap):
    return {"timestamp": ts, "caption": cap, "media_type": "VIDEO", "permalink": "https://ig/p/" + ts}


class YouTube(unittest.TestCase):
    NOW = datetime(2026, 11, 20, 6, 35, tzinfo=timezone.utc)      # 12:05 IST

    def test_windows(self):
        a, b = youtube.window("am", self.NOW)
        self.assertEqual((a.strftime("%d %H:%M"), b.strftime("%d %H:%M")), ("19 21:05", "20 12:05"))
        a, b = youtube.window("pm", self.NOW)
        self.assertEqual((a.strftime("%H:%M"), b.strftime("%H:%M")), ("12:05", "21:05"))

    def test_most_useful_first(self):
        items = [m("2026-11-20T05:00:00", "சாலை விபத்து"), m("2026-11-20T01:00:00", "நாளை மின் தடை பகுதிகள்"),
                 m("2026-11-20T04:00:00", "வேலைவாய்ப்பு முகாம்")]
        got = [x["caption"] for x in youtube.pick(items, 2)]
        self.assertEqual(got, ["நாளை மின் தடை பகுதிகள்", "வேலைவாய்ப்பு முகாம்"])

    def test_details(self):
        cap = ("🔴 நாமக்கல்லில் நாளை மின் தடை\n🤝 Sponsored: X\n\nகாலை 9 முதல் மாலை 5 வரை.\n\n📰 Source: தினமலர்\n"
               "#Namakkal #PowerCut")
        d = youtube.details(m("2026-11-20T01:00:00", cap), "namakkal", "namakkal_360")
        self.assertTrue(d["title"].startswith("நாமக்கல்லில் நாளை மின் தடை"))
        self.assertTrue(d["title"].endswith(" | Namakkal 360"))
        self.assertLessEqual(len(d["title"]), 100)
        self.assertIn("📰 Source: தினமலர்", d["description"])
        self.assertIn("📅 20 Nov 2026", d["description"])
        self.assertNotIn("Sponsored", d["description"])
        self.assertIn("Namakkal", d["tags"])
        long = youtube.details(m("2026-11-20T01:00:00", "அ" * 150), "coimbatore", "")
        self.assertLessEqual(len(long["title"]), 100)

    def test_times_never_at_night(self):
        late = datetime(2026, 11, 20, 15, 35, tzinfo=timezone.utc)      # 21:05 IST
        for t in youtube.times("pm", 10, late):
            h = datetime.strptime(t, "%d %b, %I:%M %p")
            self.assertFalse(h.hour >= 23 or h.hour < 6 or (h.hour == 6 and h.minute < 30), t)

    def test_ten_a_day(self):
        self.assertEqual((youtube.DAY_MAX, youtube.AM_MAX), (10, 5))
        news = [m(f"2026-11-20T0{i}:00:00", f"news {i}") for i in range(8)]
        self.assertEqual(len(youtube.pick(news, youtube.AM_MAX)), 5)

    def test_email(self):
        d = youtube.details(m("2026-11-20T01:00:00", "Headline\n📰 Source: Dinamalar"), "salem", "salem360")
        subject, text, html = youtube.email("salem", "Salem 360", "salem360", "am",
                                            [(m("2026-11-20T01:00:00", "Headline"), d, "https://res.cloudinary.com/x/video/upload/fl_attachment/a.mp4")],
                                            self.NOW)
        self.assertIn("[YouTube] Salem 360 - 1 reels", subject)
        self.assertIn("fl_attachment", html)
        self.assertIn("Download within 1 day", text)


if __name__ == "__main__":
    unittest.main()
