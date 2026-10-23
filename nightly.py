"""Nightly job: when every game of an NBA night is final, build the leaders
graphic and add it to queue.json for the hourly posting task.

Runs in GitHub Actions every 10 minutes. Checks the current and previous
US-Eastern game dates (ESPN's dates). A night is built once: if
cards/nights/<date>.jpg or <date>.skip exists it is left alone.

Usage: python3 nightly.py                 normal run
       python3 nightly.py --date YYYYMMDD [--test]
         --test: build into cards/test/ and queue a PRIVATE TikTok-only test post
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from leaders import pick
from night_card import render
from night_data import ALL_TEAMS, collect, save_headshots, save_logos

ROOT = Path(__file__).resolve().parent
QUEUE = ROOT / "queue.json"
NIGHTS = ROOT / "cards" / "nights"
RAW = "https://raw.githubusercontent.com/fromwaydownton-cards/fromwaydowntown-cards/main/"
LABEL = {"pts": "Most points", "reb": "Most rebounds", "ast": "Most assists",
         "three": "Best 3PT%", "worst_pm": "Worst +/-"}


def last(name):
    return name.split()[-1]


def question(night, L):
    """A different engagement question each night, built from that night's leaders."""
    pts, reb, ast = L.get("pts"), L.get("reb"), L.get("ast")
    three, worst = L.get("three"), L.get("worst_pm")
    opts = []
    if pts:
        opts.append(f"{pts['name']} dropped {pts['pts']}. Best performance of the night, or was someone better?")
        opts.append(f"{pts['pts']} points for {last(pts['name'])}. Real or a one-night thing?")
    if pts and reb and ast:
        opts.append(f"Whose night are you taking: {last(pts['name'])}, {last(reb['name'])} or {last(ast['name'])}?")
        opts.append(f"Rank them: {last(pts['name'])}'s {pts['pts']} pts, {last(reb['name'])}'s {reb['reb']} reb, "
                    f"{last(ast['name'])}'s {ast['ast']} ast.")
    if worst:
        opts.append(f"{worst['name']} finished {worst['pm']:+d}. Fair to blame him or was it the whole team?")
    if three:
        opts.append(f"{three['name']} went {three['tpm']}-for-{three['tpa']} from three. Who's the best shooter in the league right now?")
    return opts[int(night["date"]) % len(opts)]


def first_comment(L):
    names = [last(L[k]["name"]) for k in ("pts", "reb", "ast", "three") if k in L]
    return "Vote for the best night 👇 " + "  ".join(f"{i}) {n}" for i, n in enumerate(names, 1))


def caption(night, leaders):
    date = datetime.strptime(night["date"], "%Y%m%d").strftime("%b %-d, %Y")
    lines = []
    for k, p in leaders.items():
        if k == "pts":
            v = f"{p['pts']} pts"
        elif k == "reb":
            v = f"{p['reb']} reb"
        elif k == "ast":
            v = f"{p['ast']} ast"
        elif k == "three":
            v = f"{p['tpm']}-{p['tpa']} from 3"
        else:
            v = f"{p['pm']:+d}"
        lines.append(f"{LABEL[k]}: {p['name']} ({p['team']}) {v}")
    n = sum(g["final"] for g in night["games"])
    return (f"{question(night, leaders)}\n\n"
            f"NBA night leaders, {date}. All {n} final scores in the graphic.\n\n"
            + "\n".join(lines)
            + "\n\nDrop your take in the comments. Follow for the leaders every night."
            + "\n\n#NBA #NBAStats #hoops #basketball")


def build(date, test=False):
    night = collect(date)
    if not night["all_final"]:
        left = [f"{g['away']}@{g['home']} {g['status']}" for g in night["games"] if not g["final"]]
        print(f"{date}: not all final ({len(left)} left: {', '.join(left[:4])})")
        return None
    leaders = pick(night["players"])
    save_headshots([(p["id"], p["headshot"]) for p in leaders.values()])
    save_logos(ALL_TEAMS)
    out = (ROOT / "cards" / "test" if test else NIGHTS) / f"{date}.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    render(night, out)
    rel = str(out.relative_to(ROOT))
    entry = {"key": ("test:" if test else "night:") + date, "kind": "nightly", "test": test,
             "folder": rel, "images": [RAW + rel], "caption": caption(night, leaders),
             "first_comment": first_comment(leaders),
             "title": "NBA night leaders " + datetime.strptime(date, "%Y%m%d").strftime("%b %-d"),
             "queued_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    print(f"BUILT {rel}: " + "; ".join(f"{k}={p['name']}" for k, p in leaders.items()))
    return entry


def main():
    queue = json.loads(QUEUE.read_text()) if QUEUE.exists() else {"queue": []}
    keys = {e.get("key") for e in queue["queue"]}
    if "--date" in sys.argv:
        dates, test = [sys.argv[sys.argv.index("--date") + 1]], "--test" in sys.argv
    else:
        now_et = datetime.now(ZoneInfo("America/New_York"))
        dates = [(now_et - timedelta(days=1)).strftime("%Y%m%d"), now_et.strftime("%Y%m%d")]
        test = False
    for date in dates:
        key = ("test:" if test else "night:") + date
        if not test and ((NIGHTS / f"{date}.jpg").exists() or (NIGHTS / f"{date}.skip").exists()
                         or key in keys):
            print(f"{date}: already done")
            continue
        entry = build(date, test)
        if entry:
            queue["queue"] = [e for e in queue["queue"] if e.get("key") != entry["key"]] + [entry]
    cutoff = datetime.now(timezone.utc) - timedelta(days=3)
    queue["queue"] = [e for e in queue["queue"] if datetime.fromisoformat(e["queued_at"]) > cutoff]
    QUEUE.write_text(json.dumps(queue, indent=2) + "\n")


if __name__ == "__main__":
    main()
