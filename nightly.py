"""Nightly job (GitHub Actions, every 10 minutes): builds the posts and adds
them to queue.json for the hourly posting task.

Since Nov 2026 the account runs on the Guess the Player series:
  - Guess the Player, EVERY night at 8 PM Central, numbered (#1, #2, ...), each
    with its own color theme. On GUESS_DAYS (Tue/Thu/Sat) it's a current player
    with an outlier game from the night before; every other night (or when no
    outlier was found by noon) it's a legend from legends.py: a famous season
    (heat map) or a famous game (every shot), 1996-97 to today.
    The answer is revealed in the next night's post.
  - Monday: weekly per-game leaders (12 PM Central) and the MVP ladder (5 PM
    Central, so 8 PM stays the guess), built when Sunday's games are final.
The nightly recap and nightly top-scorer shot charts are retired.

Usage: python3 nightly.py                    normal run
       python3 nightly.py --date YYYYMMDD [--test]
       python3 nightly.py --legend YYYYMMDD [--test]   build a legends post for that day
         --test: build into cards/test/ and queue a PRIVATE TikTok-only test post
"""
import json
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from night_data import ALL_TEAMS, collect, save_headshots, save_logos
from shot_card import splits, tag_threes
from shots_data import shots_for
from espn_extra import prior_ppg, standings
from guess import pick_outlier
from weekly_cards import mvp as render_mvp
import legends
import legend_card
import weekly_leaders
from themes import theme

GUESS_DAYS = {1, 3, 5}      # current-player guess on Tue, Thu, Sat (Mon=0); legends otherwise
GUESS_HOUR = 20             # 8 PM Central = 6 PM Pacific, every night
WEEKLY_HOUR = 12            # Monday: weekly leaders at 12 PM Central
MVP_HOUR = 17               # Monday: MVP ladder at 5 PM Central (the guess keeps 8 PM)
FALLBACK_HOUR = 12          # by noon Central, a guess day with no current guess gets a legend

ROOT = Path(__file__).resolve().parent
QUEUE = ROOT / "queue.json"
NIGHTS = ROOT / "cards" / "nights"
SERIES = ROOT / "data" / "series.json"
CENTRAL = ZoneInfo("America/Chicago")
RAW = "https://raw.githubusercontent.com/fromwaydownton-cards/fromwaydowntown-cards/main/"
MEDIA_RAW = "https://raw.githubusercontent.com/fromwaydownton-cards/fromwaydowntown-cards/media/"
MEDIA = ROOT / "media"     # videos are published to the 'media' branch (last 8 days kept)
SUFFIXES = {"jr", "jr.", "sr", "sr.", "ii", "iii", "iv", "v"}
TAGS = "#NBA #GuessThePlayer #NBAStats #hoops #basketball"


def last(name):
    """Last name for captions, skipping suffixes: 'Darius Acuff Jr.' -> 'Acuff'."""
    parts = name.split()
    while len(parts) > 1 and parts[-1].lower() in SUFFIXES:
        parts.pop()
    return parts[-1]


def day_after(date):
    return datetime.strptime(date, "%Y%m%d") + timedelta(days=1)


def at_central(day, hour):
    return day.replace(hour=hour, minute=0, second=0, microsecond=0, tzinfo=CENTRAL).isoformat(timespec="seconds")


def now_utc():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------- the series record ------------------------------------------------

def series():
    s = json.loads(SERIES.read_text()) if SERIES.exists() else {}
    s.setdefault("n", 0)
    s.setdefault("days", {})
    s.setdefault("used", [])
    return s


def save_series(s):
    SERIES.parent.mkdir(parents=True, exist_ok=True)
    SERIES.write_text(json.dumps(s, indent=1) + "\n")


def reveal_for(s, day):
    """Yesterday's answer, for today's post."""
    prev = (day - timedelta(days=1)).strftime("%Y%m%d")
    return s["days"].get(prev, {}).get("answer")


def guess_caption(n, hook, reveal):
    return (f"GUESS THE PLAYER #{n}. {hook}\n\n"
            + (f"Last time's answer: {reveal}. Did you get it?\n\n" if reveal else "")
            + "Drop your guess in the comments. Answer in tomorrow's post. "
            + "Follow so you don't miss one.\n\n" + TAGS)


def guess_entry(key, kind, out, caption, day, title, test, extra=None):
    rel = str(out.relative_to(ROOT))
    e = {"key": key, "kind": kind, "test": test, "folder": rel, "images": [RAW + rel], "caption": caption,
         "first_comment": "", "post_at": at_central(day, GUESS_HOUR), "title": title, "queued_at": now_utc()}
    e.update(extra or {})
    return e


# ---------- current player (from last night) ---------------------------------

def build_guess_entry(night, test=False):
    date = night["date"]
    post_day = day_after(date)
    pd = post_day.strftime("%Y%m%d")
    s = series()
    if not test and (post_day.weekday() not in GUESS_DAYS or pd in s["days"]):
        return None
    pick = pick_outlier(night, prior_ppg)
    if not pick:
        print(f"{date}: no outlier game for Guess the Player (a legend will post instead)")
        return None
    shots, _ = shots_for([pick])
    v = shots[pick["id"]]
    gdir = ROOT / "data" / "guess"
    gdir.mkdir(parents=True, exist_ok=True)
    (gdir / f"{date}.json").write_text(json.dumps({"pick": pick, "shots": v}, indent=1))
    tag_threes(v["shots"], pick["tpm"], pick["tpa"])
    sp = splits(v["shots"])
    made = sum(x["made"] for x in v["shots"])
    g = next((g for g in night["games"] if g["id"] == pick["game"]), None)
    hints = []
    if pick.get("normal_src") == "last season":
        hints.append(f"AVERAGED {pick['normal']:g} PPG LAST SEASON")
    elif pick.get("normal_src") == "rookie":
        hints.append("HE'S A ROOKIE")
    else:
        hints.append(f"AVERAGING {pick['normal']:g} PPG THIS SEASON")
    if g:
        mine, theirs = ((g["home_score"], g["away_score"]) if g["home"] == pick["team"]
                        else (g["away_score"], g["home_score"]))
        hints.append(f"HIS TEAM {'WON' if mine > theirs else 'LOST'} BY {abs(mine - theirs)}")
    n = s["n"] + 1
    subject = {"mode": "game", "shots": v["shots"], "n": n,
               "sub": f"FROM LAST NIGHT'S GAMES  ·  {datetime.strptime(date, '%Y%m%d').strftime('%b %-d').upper()}",
               "chips": [("PTS", pick["pts"], True), ("FG", f"{made}-{len(v['shots'])}", False),
                         ("3PT", f"{sp['3PT'][0]}-{sp['3PT'][1]}", False),
                         ("FT", f"{v['ft_made']}-{v['ft_att']}", False)],
               "hints": hints, "reveal": reveal_for(s, post_day), "theme": theme(n)}
    out = (ROOT / "cards" / "test" if test else ROOT / "cards" / "guess") / f"{date}-guess.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    legend_card.render(subject, out)
    hook = f"{pick['pts']} points last night from a guy who usually scores {pick['normal']:g}. Who is it?"
    answer = f"{pick['name']} ({pick['team']}), {pick['pts']} pts vs his usual {pick['normal']:g}"
    e = guess_entry(("test-guess:" if test else "guess:") + date, "guess", out,
                    guess_caption(n, hook, subject["reveal"]), post_day,
                    f"Guess the player #{n}", test, {"subject": "current", "n": n})
    if not test:
        s["n"] = n
        s["days"][pd] = {"n": n, "kind": "current", "key": e["key"], "answer": answer}
        save_series(s)
    _SUBJECTS[e["key"]] = subject
    return e


# ---------- legends ------------------------------------------------------------

_SUBJECTS = {}     # key -> subject, so the video matches the card


def next_legend(s):
    """Next legend in a fixed shuffled order (seasons and games mixed, eras mixed).
    Starts over once every legend has been used."""
    order = legends.ready()
    random.Random(2026).shuffle(order)
    left = [x for x in order if x not in s["used"]]
    if not left:
        s["used"] = []
        left = order
    return left[0] if left else None


def build_legend_entry(day, test=False, force=False):
    pd = day.strftime("%Y%m%d")
    s = series()
    if pd in s["days"] and not force:
        return None
    slug = next_legend(s)
    if not slug:
        print("LEGEND: no legends data yet (run the 'Fetch Guess the Player legends data' workflow)")
        return None
    rec = legends.load(slug)
    e0 = rec["entry"]
    n = s["n"] + 1
    subject = legend_card.legend_subject(rec, n, reveal=reveal_for(s, day))
    out = (ROOT / "cards" / "test" if test else ROOT / "cards" / "guess") / f"{pd}-legend.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    legend_card.render(subject, out)
    if e0["mode"] == "season":
        hook = (f"His shot chart from the {e0['season']} season: {e0['ppg']:.1f} points a game. "
                "Who is it?")
        answer = f"{e0['name']}, {e0['season']} season"
    else:
        hook = f"{e0['pts']} points in one game. Here's every shot. Who did it?"
        answer = (f"{e0['name']}, {e0['pts']} pts on "
                  f"{datetime.strptime(e0['date'], '%Y-%m-%d').strftime('%b %-d, %Y')}")
    e = guess_entry(("test-legend:" if test else "legend:") + pd, "legend", out,
                    guess_caption(n, hook, subject["reveal"]), day,
                    f"Guess the player #{n}", test, {"subject": slug, "n": n})
    if not test:
        s["n"] = n
        s["used"].append(slug)
        s["days"][pd] = {"n": n, "kind": "legend", "slug": slug, "key": e["key"], "answer": answer}
        save_series(s)
    _SUBJECTS[e["key"]] = subject
    print(f"LEGEND #{n} for {pd}: {slug} (answer: {answer})")
    return e


def ensure_series():
    """Make sure today (Central) has a Guess the Player post. Guess days wait
    until noon for the current-player guess; other days get a legend right away."""
    now = datetime.now(CENTRAL)
    day = now.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
    s = series()
    if day.strftime("%Y%m%d") in s["days"]:
        return None
    if day.weekday() in GUESS_DAYS and now.hour < FALLBACK_HOUR:
        return None
    if now.hour >= GUESS_HOUR + 2:       # too late to post today; tomorrow starts fresh
        return None
    return build_legend_entry(day)


# ---------- weekly ------------------------------------------------------------

def build_weekly_entry(night, test=False):
    """Sunday night closes the Mon-Sun week; weekly per-game leaders post Monday."""
    date = night["date"]
    end = datetime.strptime(date, "%Y%m%d")
    if not test and end.weekday() != 6:
        return None
    start = (end - timedelta(days=6)).strftime("%Y%m%d")
    out = (ROOT / "cards" / "test" if test else ROOT / "cards" / "weekly") / f"{start}-{date}.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    L = weekly_leaders.leaders(weekly_leaders.nights_between(start, date))
    save_headshots([(r["id"], r["headshot"]) for rows in L.values() for r in rows[:1]])
    L = weekly_leaders.render(start, date, out)
    rel = str(out.relative_to(ROOT))
    wk = weekly_leaders.week_label(start, date)
    lines = []
    for k, unit, label in weekly_leaders.CATS:
        if L.get(k):
            p = L[k][0]
            lines.append(f"{label.title()}: {p['name']} ({p['team']}) {p['avg']:.1f} {unit}")
    pts = L.get("pts", [{}])[0]
    hook = (f"{pts['name']} led the league with {pts['avg']:.1f} points a game this week. Who had the best week?"
            if pts else "Who had the best week?")
    caption = (f"{hook}\n\nNBA weekly leaders, {wk} (per game, min {weekly_leaders.MIN_GP} games).\n\n"
               + "\n".join(lines)
               + "\n\nDrop your pick in the comments. Follow for Guess the Player every night."
               + "\n\n#NBA #NBAStats #hoops #basketball")
    post_day = day_after(date)
    return {"key": ("test-weekly:" if test else "weekly:") + date, "kind": "weekly", "test": test,
            "folder": rel, "images": [RAW + rel], "caption": caption,
            "first_comment": "Best week? Vote 👇 " + "  ".join(
                f"{i}) {last(L[k][0]['name'])}" for i, k in enumerate(("pts", "reb", "ast"), 1) if L.get(k)),
            "post_at": at_central(post_day, WEEKLY_HOUR), "title": "NBA weekly leaders " + wk,
            "queued_at": now_utc()}


def build_mvp_entry(night, test=False):
    """Sunday night closes the Mon-Sun week; the ladder posts Monday."""
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
            "first_comment": "Your top 5? Drop it below 👇", "post_at": at_central(post_day, MVP_HOUR),
            "week": [start, date],
            "title": "MVP ladder " + wk,
            "queued_at": now_utc()}


def add_video(entry, date):
    """Render the 60-second video for an entry. On any failure the entry stays
    image-only, so a video problem never stops a post."""
    import legend_video
    import video_more
    MEDIA.mkdir(exist_ok=True)
    name = f"{date}-{entry['kind']}{'-test' if entry.get('test') else ''}.mp4"
    out = MEDIA / name
    try:
        if entry["kind"] in ("guess", "legend") and entry["key"] in _SUBJECTS:
            legend_video.build(_SUBJECTS[entry["key"]], out)
        elif entry["kind"] == "mvp":
            video_more.mvp_video(entry["week"][0], entry["week"][1], out)
        else:
            return entry
        entry["videos"] = [MEDIA_RAW + name]
        print(f"VIDEO {name} {out.stat().st_size // 1024} KB")
    except Exception as e:
        print(f"VIDEO FAILED {name}: {e} (posting the image instead)")
    return entry


def build(date, test=False):
    """Once a night is final: save its data (for the weekly graphics), and build
    the current-player guess (posts the next day on GUESS_DAYS) and, on Sunday
    night, the weekly leaders and the MVP ladder. The nightly recap and the
    nightly top-scorer shot charts were retired in Nov 2026."""
    night = collect(date)
    if not night["all_final"]:
        left = [f"{g['away']}@{g['home']} {g['status']}" for g in night["games"] if not g["final"]]
        print(f"{date}: not all final ({len(left)} left: {', '.join(left[:4])})")
        return None
    save_logos(ALL_TEAMS)
    entries = []
    for name, fn in (("GUESS", build_guess_entry), ("WEEKLY", build_weekly_entry), ("MVP", build_mvp_entry)):
        try:
            e = fn(night, test)
            if e:
                entries.append(e)
                print(f"BUILT {e['folder']} (posts {e['post_at']})")
        except Exception as ex:  # one graphic never blocks the others
            print(f"{name} FAILED for {date}: {ex}")
    for e in entries:
        add_video(e, date)
    if not test:
        (NIGHTS / f"{date}.done").write_text(f"processed {datetime.now(timezone.utc).isoformat(timespec='seconds')}\n")
    print(f"{date}: night processed ({len(night['games'])} games)")
    return entries


def main():
    queue = json.loads(QUEUE.read_text()) if QUEUE.exists() else {"queue": []}
    keys = {e.get("key") for e in queue["queue"]}
    if "--date" in sys.argv:
        dates, test = [sys.argv[sys.argv.index("--date") + 1]], "--test" in sys.argv
    else:
        now_et = datetime.now(ZoneInfo("America/New_York"))
        dates = [(now_et - timedelta(days=1)).strftime("%Y%m%d"), now_et.strftime("%Y%m%d")]
        test = "--test" in sys.argv and "--legend" in sys.argv
    NIGHTS.mkdir(parents=True, exist_ok=True)

    def add(entry):
        queue["queue"] = [e for e in queue["queue"] if e.get("key") != entry["key"]] + [entry]

    for date in ([] if "--legend" in sys.argv else dates):
        if not test and any((NIGHTS / f"{date}{ext}").exists() for ext in (".jpg", ".skip", ".done")):
            print(f"{date}: already done")
            continue
        for entry in build(date, test) or []:
            add(entry)
    if "--legend" in sys.argv:            # build a legends post for a given day (tests)
        day = datetime.strptime(sys.argv[sys.argv.index("--legend") + 1], "%Y%m%d")
        e = build_legend_entry(day, test=test, force=True)
        if e:
            add(add_video(e, day.strftime("%Y%m%d")))
    elif not test:
        try:
            e = ensure_series()
            if e:
                add(add_video(e, e["key"].split(":")[1]))
        except Exception as ex:
            print(f"LEGEND FAILED: {ex}")
    cutoff = datetime.now(timezone.utc) - timedelta(days=3)
    queue["queue"] = [e for e in queue["queue"] if datetime.fromisoformat(e["queued_at"]) > cutoff]
    QUEUE.write_text(json.dumps(queue, indent=2) + "\n")


if __name__ == "__main__":
    main()
