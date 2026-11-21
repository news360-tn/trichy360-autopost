"""owner 18 Nov: GitHub skipped / delayed most scheduled runs (17-18 Nov: rasipalan at 3 PM, gold at 6 PM instead of 7:31 / 9:40 AM).
The posting job keeps itself running all day (a live run starts the next one), so it starts the daily jobs when they are due:
  rasipalan  from 06:43 IST until today's post is saved for every page of this repo (sources publish by about 06:30)
  gold rate  from 09:40 IST until today's post is saved (MJDTA fixes the rate at 9:30 AM)
  afternoon gold check  from 15:40 IST (MJDTA fixes it again at 3:30 PM) until today's afternoon check is saved
  news round when the last collection round started more than 4 h 15 min ago
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
    files = [n for n in (names(folder) or []) if n.startswith(prefix) and n.endswith(".json")]
    if not files:
        return None
    for n in files:
        try:
            if json.loads(raw(f"{folder}/{n}") or "{}").get("date") != today:
                return False
        except ValueError:
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


ROUNDS = ((4, 0), (8, 0), (12, 0), (16, 0), (20, 0))      # owner 21 Nov: the collection rounds (IST), every 4 hours (pick.yml / research_free.yml)


def round_overdue(now, round_runs):
    """a scheduled round passed 25+ min ago (within the last 2 h) and no round started since: GitHub skipped / delayed it.
    Never at night: after 22:00 nothing is restarted until the 04:00 round (nothing is posted 00:00-05:00 anyway)."""
    ist = now.astimezone(IST)
    due = [ist.replace(hour=h, minute=m, second=0, microsecond=0) for h, m in ROUNDS]
    due = [x for x in due if x + d.timedelta(minutes=25) <= ist]
    if not due or ist - due[-1] > d.timedelta(hours=2):
        return False
    return not busy(round_runs, now, int((ist - due[-1]).total_seconds() // 60) + 10)


def decide(now, rasi, gold, rasi_runs, gold_runs, round_wf, round_runs, pm=None):
    """pure decision (tested): which jobs to start now. rasi / gold / pm: posted_today() result; *_runs: runs()"""
    ist = now.astimezone(IST)
    hm = ist.hour * 60 + ist.minute
    todo = []
    if rasi is False and 6 * 60 + 43 <= hm < 8 * 60 + 40 and not busy(rasi_runs, now, 40):      # owner 19 Nov: before 9 AM only
        todo.append("rasipalan.yml")
    if gold is False and 9 * 60 + 40 <= hm < 21 * 60 and not busy(gold_runs, now, 45):
        todo.append("goldrate.yml")
    elif gold is True and pm is not True and 15 * 60 + 40 <= hm < 18 * 60 and not busy(gold_runs, now, 45):
        todo.append("goldrate.yml pm")
    if round_wf and round_runs and round_overdue(now, round_runs):
        todo.append(round_wf)
    return todo


def main():
    now = d.datetime.now(d.timezone.utc)
    today = now.astimezone(IST).strftime("%Y-%m-%d")
    rasi = posted_today("rasipalan/state", "", today)
    gold = posted_today("goldrate/state", "posted_", today)
    pm = posted_today("goldrate/state", "pmcheck_", today)
    round_wf = "pick.yml" if runs("pick.yml") is not None else ("research_free.yml" if names("research_free/ENABLED") is not None or raw("research_free/ENABLED") is not None else "")
    todo = decide(now, rasi, gold, runs("rasipalan.yml"), runs("goldrate.yml"), round_wf, runs(round_wf) if round_wf else None, pm)
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


if __name__ == "__main__":
    main()
