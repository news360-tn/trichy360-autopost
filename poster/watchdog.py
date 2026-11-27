"""owner 18 Nov: GitHub skipped / delayed most scheduled runs (17-18 Nov: rasipalan at 3 PM, gold at 6 PM instead of 7:31 / 9:40 AM).
The posting job keeps itself running all day (a live run starts the next one), so it starts the daily jobs when they are due:
  rasipalan  from 06:43 IST until today's post is saved for every page of this repo (sources publish by about 06:30)
  gold rate  from 09:40 IST until today's post is saved (MJDTA fixes the rate at 9:30 AM)
  afternoon gold check  from 15:40 IST (MJDTA fixes it again at 3:30 PM) until today's afternoon check is saved
  news round when the last collection round started more than 4 h 15 min ago
  YouTube details e-mail (owner 21 Nov: GitHub skipped every one - no "posted" e-mail came) from 12:30 / 21:30 IST when that
    e-mail did not run since 12:05 / 21:05
  Cloudinary clean-up when it has not run for 6 h 30 min (GitHub skipped 3 of its 4 runs a day)
It never posts anything itself, and never starts a job that is queued, running, or was started in the last 40-45 minutes.
python poster/watchdog.py   (needs GH_TOKEN and GITHUB_REPOSITORY; DRY=1 prints what it would start)"""
import datetime as d
import json
import os
import subprocess

IST = d.timezone(d.timedelta(hours=5, minutes=30))
REPO = os.environ.get("GITHUB_REPOSITORY", "")
DRY = os.environ.get("DRY", "") == "1"
BUSY = ("queued", "in_progress", "waiting", "pending", "requested")


def gh(*args):
    return subprocess.run(["gh", *args], capture_output=True, text=True)


def raw(path):
    r = gh("api", f"repos/{REPO}/contents/{path}", "-H", "Accept: application/vnd.github.raw")
    return r.stdout if r.returncode == 0 else None


def names(path):
    r = gh("api", f"repos/{REPO}/contents/{path}", "-q", ".[].name")
    return r.stdout.split() if r.returncode == 0 else None


def runs(wf):
    """[(status, created_at)] newest first; None when the workflow is missing or GitHub did not answer"""
    r = gh("api", f"repos/{REPO}/actions/workflows/{wf}/runs?per_page=5", "-q", '.workflow_runs[]|"\\(.status) \\(.created_at)"')
    if r.returncode != 0:
        return None
    out = []
    for line in r.stdout.splitlines():
        try:
            st, ts = line.split()
            out.append((st, d.datetime.fromisoformat(ts.replace("Z", "+00:00"))))
        except ValueError:
            pass
    return out


def busy(rs, now, minutes):
    """a run is queued / running, or one started less than `minutes` ago (unknown = busy: never start blind)"""
    if rs is None:
        return True
    return any(st in BUSY or (now - t).total_seconds() < minutes * 60 for st, t in rs)


def posted_today(folder, prefix, today):
    """True when every saved post file in folder (name starting with prefix) is dated today; None when there is no such file"""
    files = [n for n in (names(folder) or []) if n.startswith(prefix) and n.endswith(".json")
             and not n.startswith("rasis_")]      # owner 25 Nov: rasis_<page>_<date>.json is the shared rasipalan text, not a post record
    if not files:
        return None
    for n in files:
        try:
            d = json.loads(raw(f"{folder}/{n}") or "{}")
        except ValueError:
            return False
        if isinstance(d, dict) and d.get("date") != today:
            return False
    return True


def start(wf, *inputs):
    args = ["workflow", "run", wf, "-R", REPO]
    for i in inputs:
        args += ["-f", i]
    if DRY:
        print("DRY - would start", wf, *inputs)
        return
    r = gh(*args)
    print(("started " if r.returncode == 0 else "could not start ") + wf, (r.stderr or "").strip()[:200])


ROUNDS = tuple((h, 0) for h in range(0, 24, 2))      # owner 27 Nov: the collection rounds (IST), every 2 hours day and night (pick.yml / research_free.yml)


def round_overdue(now, round_runs):
    """a scheduled round passed 25+ min ago (within the last 2 h) and no round started since: GitHub skipped / delayed it.
    Never at night: after 22:00 nothing is restarted until the 04:00 round (nothing is posted 00:00-05:00 anyway)."""
    ist = now.astimezone(IST)
    due = [ist.replace(hour=h, minute=m, second=0, microsecond=0) for h, m in ROUNDS]
    due = [x for x in due if x + d.timedelta(minutes=25) <= ist]
    if not due or ist - due[-1] > d.timedelta(hours=2):
        return False
    return not busy(round_runs, now, int((ist - due[-1]).total_seconds() // 60) + 10)


def page_names():
    name = REPO.split("/")[-1]
    return ("namakkal", "rasipuram") if name.startswith("news360") else (name.split("360")[0],)


def all_paused(now):
    """owner 21 Nov: True when every page of this repo has its Instagram posting paused (a block / limit) - no rasipalan / gold restart"""
    pages = page_names()
    for pg in pages:
        try:
            until = d.datetime.fromisoformat(json.loads(raw(f"poster/prebuilt/_ig_paused_{pg}.json") or "{}").get("until", ""))
        except (ValueError, TypeError):
            return False
        if until <= now:
            return False
    return bool(pages)


YT_SLOTS = (("am", 12, 5, 180), ("pm", 21, 5, 170))      # owner 21 Nov: the YouTube details e-mails (12:05 / 21:05 IST), minutes they may wait


def yt_due(now, yt_runs):
    """'am' / 'pm' when that e-mail's time passed 25+ min ago (at most ~3 h ago) and no e-mail run started since it; else ''"""
    if yt_runs is None:
        return ""
    ist = now.astimezone(IST)
    for slot, h, m, window in YT_SLOTS:
        t = ist.replace(hour=h, minute=m, second=0, microsecond=0)
        if t + d.timedelta(minutes=25) <= ist < t + d.timedelta(minutes=window):
            if any(st in BUSY or x >= t for st, x in yt_runs):
                return ""
            return slot
    return ""


REPORT_SLOTS = ((9, 0), (13, 0), (18, 0), (22, 0))      # owner 21 Nov: the posted report for all pages (news360 posted_report.yml)


def report_due(now, rep_runs):
    """True when a report time passed 25+ min ago (at most 2 h ago) and no report run started since it"""
    if rep_runs is None:
        return False
    ist = now.astimezone(IST)
    for h, m in REPORT_SLOTS:
        t = ist.replace(hour=h, minute=m, second=0, microsecond=0)
        if t + d.timedelta(minutes=25) <= ist < t + d.timedelta(hours=2):
            return not any(st in BUSY or x >= t for st, x in rep_runs)
    return False


def clean_due(now, clean_runs, minutes=390):
    """the Cloudinary clean-up has not started for 6 h 30 min (its schedule is every 6 hours)"""
    return clean_runs is not None and not busy(clean_runs, now, minutes)


def decide(now, rasi, gold, rasi_runs, gold_runs, round_wf, round_runs, pm=None, yt_runs=None, clean_runs=None, paused=False, rep_runs=None):
    """pure decision (tested): which jobs to start now. rasi / gold / pm: posted_today() result; *_runs: runs()"""
    ist = now.astimezone(IST)
    hm = ist.hour * 60 + ist.minute
    todo = []
    if paused:      # owner 21 Nov: Instagram paused this page - no rasipalan / gold try now (it would make the limit longer)
        rasi = gold = pm = None
    if rasi is False and 6 * 60 + 43 <= hm < 8 * 60 + 40 and not busy(rasi_runs, now, 40):      # owner 19 Nov: before 9 AM only
        todo.append("rasipalan.yml")
    if gold is False and 9 * 60 + 40 <= hm < 21 * 60 and not busy(gold_runs, now, 45):
        todo.append("goldrate.yml")
    elif gold is True and pm is not True and 15 * 60 + 40 <= hm < 18 * 60 and not busy(gold_runs, now, 45):
        todo.append("goldrate.yml pm")
    if round_wf and round_runs and round_overdue(now, round_runs):
        todo.append(round_wf)
    slot = yt_due(now, yt_runs)
    if slot:
        todo.append("youtube.yml " + slot)
    if clean_due(now, clean_runs):
        todo.append("cloudclean.yml")
    if report_due(now, rep_runs):
        todo.append("posted_report.yml")
    return todo


def main():
    now = d.datetime.now(d.timezone.utc)
    today = now.astimezone(IST).strftime("%Y-%m-%d")
    rasi = posted_today("rasipalan/state", "", today)
    gold = posted_today("goldrate/state", "posted_", today)
    pm = posted_today("goldrate/state", "pmcheck_", today)
    round_wf = "pick.yml" if runs("pick.yml") is not None else ("research_free.yml" if names("research_free/ENABLED") is not None or raw("research_free/ENABLED") is not None else "")
    todo = decide(now, rasi, gold, runs("rasipalan.yml"), runs("goldrate.yml"), round_wf, runs(round_wf) if round_wf else None, pm,
                  runs("youtube.yml"), runs("cloudclean.yml"), all_paused(now), runs("posted_report.yml"))
    print(f"watchdog {now.astimezone(IST):%H:%M} IST: rasipalan posted={rasi} gold posted={gold} afternoon check={pm} round={round_wf}"
          f" -> {todo or 'nothing due'}")
    for wf in todo:
        if wf == "rasipalan.yml":
            start(wf, "dry=0")
        elif wf == "goldrate.yml":
            start(wf, "dry=0", "mode=am")
        elif wf == "goldrate.yml pm":
            start("goldrate.yml", "dry=0", "mode=pm")
        elif wf == "pick.yml":
            start(wf, "dry=0", "resume=0")
        elif wf == "research_free.yml":
            start(wf, "dry=false")
        elif wf.startswith("youtube.yml"):
            start("youtube.yml", "slot=" + wf.split()[1])
        elif wf == "cloudclean.yml":
            start(wf, "dry=false", "keep_hours=48")
        elif wf == "posted_report.yml":
            start(wf)


if __name__ == "__main__":
    main()
