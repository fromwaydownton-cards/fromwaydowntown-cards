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
from shot_card import render as render_shots, splits
from shots_data import build_shots, shots_for
from espn_extra import prior_ppg, standings
from guess import pick_outlier
from weekly_cards import guess as render_guess, mvp as render_mvp

GUESS_DAYS = {1, 3, 5}      # post Guess the Player on Tue, Thu, Sat (Mon=0)
NOON = 12

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
    reveal = guess_reveal(night["date"])
    return (f"{question(night, leaders)}\n\n"
            + (f"{reveal}\n\n" if reveal else "")
            + f"NBA night leaders, {date}. All {n} final scores in the graphic.\n\n"
            + "\n".join(lines)
            + "\n\nDrop your take in the comments. Follow for the leaders every night."
            + "\n\n#NBA #NBAStats #hoops #basketball")


def shots_caption(date, rows):
    d = datetime.strptime(date, "%Y%m%d").strftime("%b %-d")
    top = rows[0]["player"]
    lines = []
    for i, v in enumerate(rows, 1):
        p, sp = v["player"], splits(v["shots"])
        made = sum(s["made"] for s in v["shots"])
        lines.append(f"{i}. {p['name']} ({p['team']}) {p['pts']} pts, {made}-{len(v['shots'])} FG, "
                     f"{sp['3PT'][0]}-{sp['3PT'][1]} 3PT")
    q = [f"Where was {last(top['name'])} most dangerous last night? Paint, midrange or three?",
         f"Whose shot chart are you taking: {', '.join(last(v['player']['name']) for v in rows)}?",
         f"{last(top['name'])} put up {top['pts']}. Which spot on the floor should defenses take away?"]
    return (f"{q[int(date) % len(q)]}\n\nShot charts for the top scorers from {d}.\n\n"
            + "\n".join(lines)
            + "\n\nGreen = made, red = missed. Follow for the leaders every night."
            + "\n\n#NBA #NBAStats #ShotChart #hoops #basketball")


def next_morning(date, hour=9):
    """9:00 AM Central on the morning after the games."""
    day = datetime.strptime(date, "%Y%m%d") + timedelta(days=1)
    return day.replace(hour=hour, tzinfo=ZoneInfo("America/Chicago")).isoformat(timespec="seconds")


def build_shot_entry(night, test=False):
    data = build_shots(night)
    if not data:
        return None
    date = night["date"]
    out = (ROOT / "cards" / "test" if test else ROOT / "cards" / "shots") / f"{date}-shots.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = render_shots(data, date, out)
    rel = str(out.relative_to(ROOT))
    return {"key": ("test-shots:" if test else "shots:") + date, "kind": "shots", "test": test,
            "folder": rel, "images": [RAW + rel], "caption": shots_caption(date, rows),
            "first_comment": "", "post_at": next_morning(date),
            "title": "Top scorer shot charts " + datetime.strptime(date, "%Y%m%d").strftime("%b %-d"),
            "queued_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def day_after(date):
    return datetime.strptime(date, "%Y%m%d") + timedelta(days=1)


def at_central(day, hour):
    return day.replace(hour=hour, minute=0, tzinfo=ZoneInfo("America/Chicago")).isoformat(timespec="seconds")


def guess_reveal(date):
    """If yesterday's night produced a Guess the Player that posted today, return the answer line."""
    prev = (datetime.strptime(date, "%Y%m%d") - timedelta(days=1)).strftime("%Y%m%d")
    f = ROOT / "data" / "guess" / f"{prev}.json"
    if not f.exists():
        return None
    p = json.loads(f.read_text())["pick"]
    return (f"Today's Guess the Player answer: {p['name']} ({p['team']}), {p['pts']} pts "
            f"vs his usual {p['normal']:g}. Did you get it?")


def build_guess_entry(night, test=False):
    date = night["date"]
    post_day = day_after(date)
    if not test and post_day.weekday() not in GUESS_DAYS:
        return None
    pick = pick_outlier(night, prior_ppg)
    if not pick:
        print(f"{date}: no outlier game for Guess the Player")
        return None
    shots, _ = shots_for([pick])
    gdir = ROOT / "data" / "guess"
    gdir.mkdir(parents=True, exist_ok=True)
    (gdir / f"{date}.json").write_text(json.dumps({"pick": pick, "shots": shots[pick["id"]]}, indent=1))
    out = (ROOT / "cards" / "test" if test else ROOT / "cards" / "guess") / f"{date}-guess.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    render_guess(date, out)
    rel = str(out.relative_to(ROOT))
    hint = "He's not a star, and this was way above his usual."
    caption = (f"GUESS THE PLAYER. {pick['pts']} points last night. Who put up this shot chart?\n\n"
               f"{hint} Two hints are on the graphic.\n\n"
               "Drop your guess in the comments. Answer in tonight's post.\n\n"
               "#NBA #GuessThePlayer #NBAStats #hoops #basketball")
    return {"key": ("test-guess:" if test else "guess:") + date, "kind": "guess", "test": test,
            "folder": rel, "images": [RAW + rel], "caption": caption, "first_comment": "",
            "post_at": at_central(post_day, NOON),
            "title": "Guess the player " + post_day.strftime("%b %-d"),
            "queued_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def build_mvp_entry(night, test=False):
    """Sunday night closes the Mon-Sun week; the ladder posts Monday at noon."""
    date = night["date"]
    end = datetime.strptime(date, "%Y%m%d")
    if not test and end.weekday() != 6:
        return None
    start = (end - timedelta(days=6)).strftime("%Y%m%d")
    st = standings()
    out = (ROOT / "cards" / "test" if test else ROOT / "cards" / "mvp") / f"{start}-{date}.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = render_mvp(start, date, out, st)
    save_headshots([(r["id"], r["headshot"]) for r in rows])
    rows = render_mvp(start, date, out, st)      # again, now with every headshot on disk
    rel = str(out.relative_to(ROOT))
    lines = [f"{i}. {r['name']} ({r['team']}) {r['ppg']:.1f} PPG, on/off {r['onoff']:+.0f}, "
             f"team {r['team_w']}-{r['team_l']}" for i, r in enumerate(rows, 1)]
    wk = f"{datetime.strptime(start, '%Y%m%d').strftime('%b %-d')}-{end.strftime('%b %-d')}"
    caption = (f"MVP LADDER, week of {wk}. Is {last(rows[0]['name'])} really No. 1?\n\n"
               + "\n".join(lines)
               + "\n\nRanked by Game Score, on/off impact and team record. Who's too high? Who's missing?"
               + "\n\n#NBA #MVP #NBAStats #hoops #basketball")
    post_day = day_after(date)
    return {"key": ("test-mvp:" if test else "mvp:") + date, "kind": "mvp", "test": test,
            "folder": rel, "images": [RAW + rel], "caption": caption,
            "first_comment": "Your top 5? Drop it below 👇", "post_at": at_central(post_day, NOON),
            "title": "MVP ladder " + wk,
            "queued_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}


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
    entries = [entry]
    try:
        se = build_shot_entry(night, test)
        if se:
            entries.append(se)
            print(f"BUILT {se['folder']} (posts {se['post_at']})")
    except Exception as e:  # a shot-chart problem must never block the leaders post
        print(f"SHOTS FAILED for {date}: {e}")
    for name, fn in (("GUESS", build_guess_entry), ("MVP", build_mvp_entry)):
        try:
            e = fn(night, test)
            if e:
                entries.append(e)
                print(f"BUILT {e['folder']} (posts {e['post_at']})")
        except Exception as ex:  # extra graphics never block the nightly post
            print(f"{name} FAILED for {date}: {ex}")
    return entries


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
        for entry in build(date, test) or []:
            queue["queue"] = [e for e in queue["queue"] if e.get("key") != entry["key"]] + [entry]
    cutoff = datetime.now(timezone.utc) - timedelta(days=3)
    queue["queue"] = [e for e in queue["queue"] if datetime.fromisoformat(e["queued_at"]) > cutoff]
    QUEUE.write_text(json.dumps(queue, indent=2) + "\n")


if __name__ == "__main__":
    main()
