"""Fills the "Recent changes" section of PROJECT_CONTEXT.md from git history (code commits only - the bot's log/queue
saves are left out). Run by .github/workflows/context.yml after every code push; safe to run by hand."""
import re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "PROJECT_CONTEXT.md"
SKIP = re.compile(r"^(prebuilt|story writer log|free collector log|check log|insights|context:|Merge )", re.I)
START, END = "<!-- recent-changes:start", "<!-- recent-changes:end -->"


def main(limit=30):
    log = subprocess.run(["git", "log", "--no-merges", "--date=short", "--format=%h|%ad|%s", "-n", "400"],
                         cwd=ROOT, capture_output=True, text=True, check=True).stdout.splitlines()
    rows = []
    for line in log:
        h, d, s = line.split("|", 2)
        if SKIP.search(s):
            continue
        rows.append(f"| {d} | `{h}` | {s.replace('|', '/')} |")
        if len(rows) >= limit:
            break
    text = DOC.read_text(encoding="utf-8")
    a, b = text.index(START), text.index(END)
    head = text[a:text.index("\n", a) + 1]
    table = "| Date | Commit | Change |\n|---|---|---|\n" + "\n".join(rows) + "\n"
    new = text[:a] + head + table + text[b:]
    if new != text:
        DOC.write_text(new, encoding="utf-8")
        print(f"PROJECT_CONTEXT.md: {len(rows)} recent changes")
        return 1
    print("PROJECT_CONTEXT.md already up to date")
    return 0


if __name__ == "__main__":
    sys.exit(0 if main() >= 0 else 1)
