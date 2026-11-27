"""owner 27 Nov: a power cut whose cut day has passed is never posted - also when it came in as a 'manual' link (Tirupur RN-259, a
25 Nov cut, went out on 27 Nov). A cancellation / change of an announced cut is posted while its cut day is ahead."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "poster"))
sys.path.insert(0, str(ROOT / "research_free"))
import post      # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))
NOW = datetime.now(IST)


def row(head, days_ago, **k):
    r = {"headline_ta": head, "headline_en": "", "published": (NOW - timedelta(days=days_ago)).isoformat(), "notes": "manual link"}
    r.update(k)
    return r


def test_old_tomorrow_cut_is_over():
    assert post.power_cut_day_passed(row("குமார் நகர் பகுதியில் நாளை மின் தடை", 3)).startswith("stale")


def test_tomorrow_cut_printed_today_is_ahead():
    assert post.power_cut_day_passed(row("நாளை மின்தடை: பொங்கலூர்", 0)) == ""


def test_dated_cut_ahead_and_over():
    d_ahead, d_over = NOW + timedelta(days=2), NOW - timedelta(days=2)
    assert post.power_cut_day_passed(row(f"{d_ahead:%d.%m.%y} மின்தடை: அவிநாசி", 1)) == ""
    assert post.power_cut_day_passed(row(f"{d_over:%d.%m.%y} மின்தடை: அவிநாசி", 4)).startswith("stale")


def test_not_a_power_cut():
    assert post.power_cut_day_passed(row("சாலை விபத்து: இருவர் காயம்", 5)) == ""


def test_cancellation_is_not_held():
    assert post.change_hold(row("நாளை மின்தடை ரத்து: பல்லடம்", 0)) == ""


def test_postponed_or_rescheduled_cut_is_posted():      # owner 27 Nov: reschedule / postpone / cancel news is posted too
    new_day = NOW + timedelta(days=3)
    for head in (f"நாளை மின்தடை ஒத்திவைப்பு: {new_day:%d.%m.%y} அன்று நடைபெறும்", "நாளை மின்தடை ரத்து: பல்லடம்",
                 f"பல்லடம் மின்தடை {new_day:%d.%m.%y}க்கு மாற்றம்"):
        assert post.power_cut_day_passed(row(head, 0)) == "", head
        assert post.change_hold(row(head, 0)) == "", head


def test_powercut_job_never_refuses_a_change():
    sys.path.insert(0, str(ROOT / "research_free"))
    import powercut
    if hasattr(powercut, "_change_without_original"):
        assert powercut._change_without_original({"title": "நாளை மின்தடை ரத்து"}, [{"headline_ta": "x"}]) is False
