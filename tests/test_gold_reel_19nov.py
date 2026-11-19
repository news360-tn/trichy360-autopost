"""owner 19 Nov: gold & silver rate also as a reel - posted after the carousel, never twice, a reel problem never touches the carousel"""
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


def test_script_reads_rates_and_changes():
    lines = gold_reel.script(G.PAGES[next(iter(G.PAGES))], rates())
    assert "இன்றைய தங்கம் விலை" in lines[0]
    assert "11610" in lines[1] and "250 ரூபாய் குறைந்துள்ளது" in lines[1]
    assert "12666" in lines[2]
    assert "172" in lines[3] and "6 ரூபாய் குறைந்துள்ளது" in lines[3]
    assert "பின்தொடருங்கள்" in lines[-1]


def test_script_without_silver_and_no_change():
    r = rates(silver=False)
    r["g22_prev"] = r["g22"]
    lines = gold_reel.script(G.PAGES[next(iter(G.PAGES))], r)
    assert len(lines) == 4 and "மாற்றம் இல்லை" in lines[1]
    assert not any("வெள்ளி ஒரு கிராம்" in x for x in lines)


def test_hook_words():
    r = rates()
    assert gold_reel.hook(r, "gold")[0] == "தங்கம் விலை ₹250 குறைவு"
    assert gold_reel.hook(r, "silver")[0] == "வெள்ளி விலை ₹6 குறைவு"
    r["g22_prev"] = r["g22"] - 40
    assert gold_reel.hook(r, "gold")[0] == "தங்கம் விலை ₹40 உயர்வு"


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


def test_modern_scenes_match_voice_lines():
    p = G.PAGES[next(iter(G.PAGES))]
    for silver in (True, False):
        r = rates(silver)
        assert len(gold_reel.scene_list(r)) == len(gold_reel.script(p, r))
    html = gold_reel.scene_html(dict(p, logo=None), rates(), "g22", 1, 5)
    assert "11,610" in html and "92,880" in html      # 1 சவரன் = 8 கிராம்
