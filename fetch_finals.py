"""Find NBA games that just went final, build their carousels, queue them.

Runs in GitHub Actions every 10 minutes. Data comes from the NBA's public
live-data feed (no key needed). For every final game whose card folder doesn't
exist yet, it builds the 4 cards and appends an entry to queue.json. The hourly
Claude task reads queue.json and sends each entry to Metricool.

Usage: python3 fetch_finals.py            (normal run)
       python3 fetch_finals.py --dry-run  (print what it would do, write nothing)
"""
import json
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from run_game import ROOT, game_folder, make

SCOREBOARD = "https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json"
BOXSCORE = "https://cdn.nba.com/static/json/liveData/boxscore/boxscore_{}.json"
QUEUE = ROOT / "queue.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/129.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.nba.com/",
    "Origin": "https://www.nba.com",
}
ESPN_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={}"
ESPN_SUMMARY = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={}"
ESPN_ABBR = {"GS": "GSW", "NY": "NYK", "SA": "SAS", "NO": "NOP", "UTAH": "UTA",
             "WSH": "WAS", "PHO": "PHX", "BRK": "BKN", "CHO": "CHA"}


def get(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def game_score(s):
    """John Hollinger's Game Score, from a box-score line."""
    v = (s["points"] + 0.4 * s["fieldGoalsMade"] - 0.7 * s["fieldGoalsAttempted"]
         - 0.4 * (s["freeThrowsAttempted"] - s["freeThrowsMade"])
         + 0.7 * s["reboundsOffensive"] + 0.3 * s["reboundsDefensive"]
         + s["steals"] + 0.7 * s["assists"] + 0.7 * s["blocks"]
         - 0.4 * s["foulsPersonal"] - s["turnovers"])
    return round(v, 1)


def to_game(box):
    g = box["game"]
    out = {"id": f"nba:{g['gameId']}", "start_time": g["gameTimeUTC"],
           "home": g["homeTeam"]["teamTricode"], "away": g["awayTeam"]["teamTricode"],
           "score": {}, "player_stats": {}}
    for side in ("homeTeam", "awayTeam"):
        t = g[side]
        out["score"][t["teamTricode"]] = int(t["score"])
        players = []
        for p in t["players"]:
            s = p.get("statistics") or {}
            if not s or p.get("played") == "0":
                continue
            players.append({"name": p["name"], "stats": {
                "points": s["points"], "rebounds": s["reboundsTotal"], "assists": s["assists"],
                "field_goals_made": s["fieldGoalsMade"], "field_goals_att": s["fieldGoalsAttempted"],
                "three_points_made": s["threePointersMade"], "three_points_att": s["threePointersAttempted"],
                "blocks": s["blocks"], "steals": s["steals"], "turnovers": s["turnovers"],
                "personal_fouls": s["foulsPersonal"], "efficiency_game_score": game_score(s)}})
        out["player_stats"][t["teamTricode"]] = players
    return out


def espn_team(abbr):
    return ESPN_ABBR.get(abbr, abbr)


def espn_games(now):
    """Final/unfinished games from ESPN for yesterday and today (US Central)."""
    out = []
    for d in {(now - timedelta(hours=h)).strftime("%Y%m%d") for h in (6, 30)}:
        for ev in get(ESPN_SCOREBOARD.format(d)).get("events", []):
            comp = ev["competitions"][0]
            teams = {c["homeAway"]: c for c in comp["competitors"]}
            out.append({"source": "espn", "id": ev["id"],
                        "final": comp["status"]["type"].get("completed", False),
                        "status_text": comp["status"]["type"].get("shortDetail", ""),
                        "start_time": ev["date"],
                        "home": espn_team(teams["home"]["team"]["abbreviation"]),
                        "away": espn_team(teams["away"]["team"]["abbreviation"])})
    return out


def espn_box(event_id, stub):
    summ = get(ESPN_SUMMARY.format(event_id))
    out = {"id": f"espn:{event_id}", "start_time": stub["start_time"],
           "home": stub["home"], "away": stub["away"], "score": {}, "player_stats": {}}
    for c in summ["header"]["competitions"][0]["competitors"]:
        out["score"][espn_team(c["team"]["abbreviation"])] = int(c["score"])
    for team in summ["boxscore"]["players"]:
        abbr = espn_team(team["team"]["abbreviation"])
        block = team["statistics"][0]
        idx = {k: i for i, k in enumerate(block["labels"])}
        players = []
        for a in block["athletes"]:
            st = a.get("stats") or []
            if a.get("didNotPlay") or not st:
                continue
            mk = lambda k: [int(x) for x in st[idx[k]].split("-")]
            n = lambda k: int(st[idx[k]])
            fgm, fga = mk("FG"); tpm, tpa = mk("3PT"); ftm, fta = mk("FT")
            line = {"points": n("PTS"), "fieldGoalsMade": fgm, "fieldGoalsAttempted": fga,
                    "freeThrowsMade": ftm, "freeThrowsAttempted": fta,
                    "reboundsOffensive": n("OREB"), "reboundsDefensive": n("DREB"),
                    "steals": n("STL"), "assists": n("AST"), "blocks": n("BLK"),
                    "foulsPersonal": n("PF"), "turnovers": n("TO")}
            players.append({"name": a["athlete"]["displayName"], "stats": {
                "points": line["points"], "rebounds": n("REB"), "assists": line["assists"],
                "field_goals_made": fgm, "field_goals_att": fga,
                "three_points_made": tpm, "three_points_att": tpa,
                "blocks": line["blocks"], "steals": line["steals"], "turnovers": line["turnovers"],
                "personal_fouls": line["foulsPersonal"], "efficiency_game_score": game_score(line)}})
        out["player_stats"][abbr] = players
    return out


def nba_games():
    out = []
    for sg in get(SCOREBOARD)["scoreboard"]["games"]:
        out.append({"source": "nba", "id": sg["gameId"], "final": sg.get("gameStatus") == 3,
                    "status_text": sg.get("gameStatusText", "").strip(),
                    "start_time": sg["gameTimeUTC"],
                    "home": sg["homeTeam"]["teamTricode"], "away": sg["awayTeam"]["teamTricode"]})
    return out


def list_games(now):
    if "--espn" in sys.argv:
        return espn_games(now)
    try:
        return nba_games()
    except Exception as e:  # NBA feed blocks some cloud IPs
        print(f"NBA feed unavailable ({e}); using ESPN")
        return espn_games(now)


def box_for(g):
    if g["source"] == "nba":
        return to_game(get(BOXSCORE.format(g["id"])))
    return espn_box(g["id"], g)


def main(dry_run=False):
    queue = json.loads(QUEUE.read_text()) if QUEUE.exists() else {"queue": []}
    now = datetime.now(timezone.utc)
    games = list_games(now)
    added, seen = [], set()
    for g in games:
        label = f"{g['away']} at {g['home']}"
        if label + g["start_time"][:10] in seen:
            continue
        seen.add(label + g["start_time"][:10])
        if not g["final"]:
            print(f"skip {label}: not final ({g['status_text']})")
            continue
        _, folder = game_folder(g)
        if "--ignore-built" in sys.argv and dry_run:
            pass
        elif folder.exists() or any(e["folder"] == str(folder.relative_to(ROOT)) for e in queue["queue"]):
            print(f"skip {label}: already built ({folder.relative_to(ROOT)})")
            continue
        start = datetime.fromisoformat(g["start_time"].replace("Z", "+00:00"))
        if now - start > timedelta(hours=36):
            print(f"skip {label}: too old")
            continue
        game = box_for(g)
        tops = {t: sorted(ps, key=lambda p: p["stats"]["points"], reverse=True)[:2]
                for t, ps in game["player_stats"].items()}
        print(f"FINAL {label} {game['score']} via {g['source']} top: "
              + "; ".join(f"{p['name']} {p['stats']['points']}p {p['stats']['rebounds']}r "
                          f"{p['stats']['field_goals_made']}-{p['stats']['field_goals_att']} "
                          f"gs{p['stats']['efficiency_game_score']}"
                          for ps in tops.values() for p in ps))
        if dry_run:
            continue
        entry = make(game)
        entry["queued_at"] = now.isoformat(timespec="seconds")
        queue["queue"].append(entry)
        added.append(entry["folder"])
    # keep the queue short: drop entries older than 3 days
    cutoff = now - timedelta(days=3)
    queue["queue"] = [e for e in queue["queue"]
                      if datetime.fromisoformat(e["queued_at"]) > cutoff]
    if not dry_run:
        QUEUE.write_text(json.dumps(queue, indent=2) + "\n")
    print(f"built {len(added)}: {added}")


if __name__ == "__main__":
    main(dry_run="--dry-run" in sys.argv)
