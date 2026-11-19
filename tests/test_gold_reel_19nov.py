"""owner 19 Nov: gold & silver rate also as a reel - posted after the carousel, never twice, a reel problem never touches the carousel.
owner 19 Nov (evening): the reel is the Kovai Minnal / Chennai Minnal pattern in OUR 360 brand (gold360_render.py): 10 s, today's
price from the first frame, every number from the confirmed rate, the page's own logo / name / real username, music only."""
import json
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "goldrate"))
import gold_daily as G      # noqa: E402
import gold_reel            # noqa: E402

DAY = date(2026, 11, 19)
HIST = [{"date": "2026-11-%02d" % d, "g22": 11500 + 20 * d, "g24": 12500 + 20 * d, "silver": 160 + d} for d in range(10, 19)]


def rates(silver=True):
    return G.rates_for_slides(HIST, DAY, {"g22": 11610, "g24": 12666}, {"silver": 172} if silver else None)


def test_reel_done_from_state(tmp_path, monkeypatch):
    monkeypatch.setattr(G, "STATE_DIR", tmp_path)
    assert G.reel_done("namakkal", DAY) == ""
    G.reel_path("namakkal").write_text(json.dumps({"date": DAY.isoformat(), "permalink": "x"}))
    assert G.reel_done("namakkal", DAY)
    assert G.reel_done("namakkal", date(2026, 11, 20)) == ""


def test_reel_done_from_instagram(tmp_path, monkeypatch):
    monkeypatch.setattr(G, "STATE_DIR", tmp_path)
    cap = "🎬 இன்றைய தங்கம், வெள்ளி விலை | " + G.date_ta(DAY)

    def fake_ig(method, path, token, **k):
        if path == "me":
            return {"user_id": "1"}
        return {"data": [{"caption": cap, "permalink": "p1", "media_product_type": "FEED"},
                         {"caption": cap, "permalink": "p2", "media_product_type": "REELS"}]}
    monkeypatch.setattr(G, "ig", fake_ig)
    assert "p2" in G.reel_done("namakkal", DAY, "tok")


def test_carousel_only_is_not_a_reel(tmp_path, monkeypatch):
    monkeypatch.setattr(G, "STATE_DIR", tmp_path)
    monkeypatch.setattr(G, "ig", lambda m, p, t, **k: {"user_id": "1"} if p == "me" else
                        {"data": [{"caption": "இன்றைய தங்கம், வெள்ளி விலை | " + G.date_ta(DAY), "media_product_type": "FEED"}]})
    assert G.reel_done("namakkal", DAY, "tok") == ""


def test_reel_failure_is_only_logged(tmp_path, monkeypatch):
    monkeypatch.setattr(G, "DRY", False)
    monkeypatch.setattr(G, "STATE_DIR", tmp_path)
    monkeypatch.setattr(gold_reel, "make", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("voice down")))
    said = []
    monkeypatch.setattr(G, "log", lambda *a: said.append(" ".join(map(str, a))))
    G.post_reel("namakkal", {}, {}, [], "cap", tmp_path, "tok", DAY)      # must not raise
    assert any("reel NOT POSTED" in s for s in said)
    assert not G.reel_path("namakkal").exists()


def test_reel_posted_saves_state(tmp_path, monkeypatch):
    monkeypatch.setattr(G, "DRY", False)
    monkeypatch.setattr(G, "STATE_DIR", tmp_path)
    monkeypatch.setattr(gold_reel, "make", lambda *a, **k: (tmp_path / "r.mp4", []))
    monkeypatch.setattr(G, "reel_done", lambda *a, **k: "")
    monkeypatch.setattr(G, "upload_video", lambda p: "https://v")
    got = {}
    monkeypatch.setattr(G, "publish_reel", lambda tok, url, cap: got.update(url=url, cap=cap) or ("m1", "link1"))
    G.post_reel("namakkal", {}, {}, [], "cap", tmp_path, "tok", DAY)
    assert got == {"url": "https://v", "cap": "🎬 cap"}
    assert json.loads(G.reel_path("namakkal").read_text())["permalink"] == "link1"


def test_reel_switch_off(tmp_path, monkeypatch):
    monkeypatch.setattr(G, "REEL", False)
    monkeypatch.setattr(gold_reel, "make", lambda *a, **k: pytest.fail("made a reel while switched off"))
    G.post_reel("namakkal", {}, {}, [], "cap", tmp_path, "tok", DAY)


def test_catchup_stops_after_afternoon(monkeypatch):
    monkeypatch.setattr(G, "DRY", False)
    monkeypatch.setattr(G, "FORCE_DATE", "")

    class Late(G.datetime):
        @classmethod
        def now(cls, tz=None):
            return G.datetime(2026, 11, 19, 16, 0, tzinfo=G.IST)
    monkeypatch.setattr(G, "datetime", Late)
    monkeypatch.setattr(G, "reel_done", lambda *a, **k: pytest.fail("checked reels after 15:15"))
    G.reel_catchup(["namakkal"], DAY, {"namakkal": "tok"})


def test_workflow_installs_voice_and_ffmpeg():
    y = (ROOT / ".github" / "workflows" / "goldrate.yml").read_text()
    assert "edge-tts" in y and "imageio-ffmpeg" in y and "numpy" in y


# ---------------- owner 19 Nov (evening): the Kovai Minnal reel pattern in our 360 brand ----------------
import gold360_render as D      # noqa: E402


def page(pg="salem"):
    return dict(G.PAGES[pg], logo=ROOT / "kit" / f"logo_{pg}.png")


def test_reel_is_our_brand_not_theirs():
    html = D.reel_page(page(), rates())
    assert "சேலம்<i>360</i>" in html and "logo_salem.png" in html and "Follow @salem360.official" in html
    assert "#3A070B" in html and "#FFD233" in html      # the 360 logo's maroon + gold
    for theirs in ("Minnal", "minnal", "மின்னல்", "bolt", "#06142E"):
        assert theirs not in html


def test_clock_360_degree_style():
    """owner 19 Nov: "use the clock 360 degree style, because all my pages use 360" """
    html = D.reel_page(page(), rates())
    assert html.count('<span class="e3">360°</span>') == 2      # a 360° clock dial on the gold coin and on the silver coin
    assert html.count('class="ring"') == 2 and 'class="lring"' in html      # rings that sweep a full turn / close round the logo
    assert "conic-gradient(from 0deg" in html and 'class="hand"' in html      # the clockwise clock-hand wipe between screens
    assert html.count('<svg class="dial"') >= 7      # the clock bezels (60 ticks) in the bands and behind the logo
    assert "M12 0C5.37" not in html      # no map pin any more


def test_every_number_from_the_confirmed_rate():
    html = D.reel_page(page(), rates())
    for n in ("₹92,880", "₹11,610", "₹12,666", "₹1,26,660", "₹95,666",      # 1 சவரன் = 8 g, 24K 10 g, 1 சவரன் + 3% GST
              "₹1,72,000", "₹1,720", "₹17,200", "₹1,77,160"):      # silver 1 kg, 10 g, 100 g, 1 kg + 3% GST
        assert n in html, n
    assert "▼ ₹2,000 குறைவு" in html      # 1 சவரன்: 11,610 x 8 against yesterday's 11,860 x 8
    assert "செய்கூலி, சேதாரம் கடைக்கு ஏற்ப தனியாகச் சேரும்" in html


def test_ten_seconds_and_the_cover():
    assert D.reel_timeline(rates())[2] == 10.0      # gold 4.3 + silver 4.3 + follow 1.4
    assert D.reel_timeline(rates(silver=False))[2] == 5.7
    html = D.reel_page(page(), rates(silver=False))
    assert "வெள்ளி விலை" not in html and "தினமும் தங்கம் விலை நிலவரம்" in html
    assert gold_reel.COVER_MS == int(D.COVER * 1000) == 3400


def test_first_frame_already_shows_the_price():
    html = D.reel_page(page(), rates())
    hero = html[html.index('<div class="hero"'):]
    assert hero.startswith('<div class="hero" data-a="-1.00,')      # on screen from frame 0 (people scroll past an empty screen)
    assert 'data-a="-1.00,0.48,count"' in html


def test_afternoon_update_says_so():
    r = G.pm_rates(HIST, DAY, {"g22": 11610, "g24": 12666, "silver": 172}, {"g22": 11570, "g24": 12622}, None)
    html = D.reel_page(page(), r)
    assert "சேலம் • மாலை நிலவரம்" in html and "காலை விலையைவிட" in html


def test_follow_line_uses_the_real_username(monkeypatch):
    monkeypatch.setattr(G, "DRY", False)
    monkeypatch.setattr(G, "ig", lambda m, path, tok, **k: {"username": "salem_real"} if path == "me" else {})
    assert G.page_cfg("salem", "tok")["handle"] == "salem_real"
    monkeypatch.setattr(G, "ig", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))
    assert G.page_cfg("salem", "tok")["handle"] == G.PAGES["salem"]["handle"]      # never raises: the saved handle
    monkeypatch.setattr(G, "DRY", True)
    monkeypatch.setattr(G, "ig", lambda *a, **k: pytest.fail("read Instagram in a dry run"))
    assert G.page_cfg("salem", "tok")["logo"] == ROOT / "kit" / "logo_salem.png"


def test_reel_cover_is_the_built_gold_screen(monkeypatch):
    sent = {}

    def fake_ig(method, path, token, **k):
        if path == "me":
            return {"user_id": "1"}
        if path.endswith("/media"):
            sent.update(k)
            return {"id": "c1"}
        return {"id": "m1", "permalink": "p"}
    monkeypatch.setattr(G, "ig", fake_ig)
    monkeypatch.setattr(G, "wait_ready", lambda *a, **k: None)
    assert G.publish_reel("tok", "https://v", "cap") == ("m1", "p")
    assert sent["media_type"] == "REELS" and sent["thumb_offset"] == "3400"


def test_bright_music_starts_at_once():
    np = pytest.importorskip("numpy")      # the tests machine has no numpy: checked where the reel is made
    sys.path.insert(0, str(ROOT / "reel"))
    import music
    y = music.make(10.0, 7, "bright")
    assert len(y) == 10 * music.SR and np.abs(y[:4410]).max() > 0.05      # no quiet first second


# ---------------- owner 19 Nov: gold & silver rate - REELS ONLY (no carousel), morning and 3:30 PM ----------------
def test_reels_only_by_default():
    assert G.CAROUSEL is False
    assert "REELS ONLY" in (ROOT / ".github" / "workflows" / "goldrate.yml").read_text()


def test_morning_reel_is_the_days_post(tmp_path, monkeypatch):
    monkeypatch.setattr(G, "DRY", False)
    monkeypatch.setattr(G, "FORCE_DATE", DAY.isoformat())
    monkeypatch.setattr(G, "STATE_DIR", tmp_path)
    monkeypatch.setattr(G, "ROOT", tmp_path)
    monkeypatch.setenv("GOLD_PAGES", "salem")
    monkeypatch.setattr(G, "bridge_get", lambda a, **k: {"token": "tok"})
    monkeypatch.setattr(G, "ig", lambda *a, **k: {})
    monkeypatch.setattr(G, "already_posted", lambda *a, **k: "")
    monkeypatch.setattr(G, "reel_catchup", lambda *a, **k: None)
    monkeypatch.setattr(G.sources, "collect", lambda day, log: {"gold": {"g22": 11610, "g24": 12666, "sources": ["a", "b"]},
                                                                "silver": {"silver": 172, "sources": ["a", "b"]}})
    monkeypatch.setattr(G, "load_history", lambda: [dict(h) for h in HIST])
    monkeypatch.setattr(G, "save_today", lambda *a, **k: None)
    monkeypatch.setattr(G.render, "render", lambda *a, **k: pytest.fail("made carousel slides"))
    monkeypatch.setattr(G, "publish", lambda *a, **k: pytest.fail("posted a carousel"))
    made = []
    monkeypatch.setattr(G, "post_reel", lambda pg, p, r, jpgs, cap, out, token, day, pm=False: made.append((pg, token, pm)) or ("m1", "l1"))
    G.main()
    assert made == [("salem", "tok", False)]
    st = json.loads(G.state_path("salem").read_text())
    assert st["permalink"] == "l1" and st["kind"] == "reel" and st["date"] == DAY.isoformat()      # the watchdog reads this file


def test_afternoon_reel_not_blocked_by_the_morning_reel(tmp_path, monkeypatch):
    monkeypatch.setattr(G, "DRY", False)
    monkeypatch.setattr(G, "STATE_DIR", tmp_path)
    monkeypatch.setattr(gold_reel, "make", lambda *a, **k: (tmp_path / "r.mp4", []))
    monkeypatch.setattr(G, "reel_done", lambda *a, **k: "the morning reel")
    monkeypatch.setattr(G, "upload_video", lambda p: "https://v")
    monkeypatch.setattr(G, "publish_reel", lambda tok, url, cap: ("m2", "pm-link"))
    assert G.post_reel("salem", {}, {}, [], "cap", tmp_path, "tok", DAY, pm=True) == ("m2", "pm-link")
    assert not G.reel_path("salem").exists()      # the morning reel's record is not touched
    assert G.post_reel("salem", {}, {}, [], "cap", tmp_path, "tok", DAY) is None      # a second morning reel: never


def test_at_most_five_hashtags():      # owner 19 Nov: max 5 hashtags on every post
    r = rates()
    for cap in (G.caption(G.PAGES["salem"], DAY, r), G.pm_caption(G.PAGES["salem"], DAY, r)):
        tags = [w for w in cap.split() if w.startswith("#")]
        assert len(tags) == 5 and tags[-1] == "#Salem360", tags
