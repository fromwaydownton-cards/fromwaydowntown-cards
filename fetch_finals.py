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
HEADERS = {"User-Agent": "Mozilla/5.0 (fromwaydowntown-cards)", "Accept": "application/json"}


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


def main(dry_run=False):
    queue = json.loads(QUEUE.read_text()) if QUEUE.exists() else {"queue": []}
    queued = {e["game_id"] for e in queue["queue"]}
    games = get(SCOREBOARD)["scoreboard"]["games"]
    now = datetime.now(timezone.utc)
    added = []
    for sg in games:
        label = f"{sg['awayTeam']['teamTricode']} at {sg['homeTeam']['teamTricode']}"
        if sg.get("gameStatus") != 3:
            print(f"skip {label}: not final ({sg.get('gameStatusText', '').strip()})")
            continue
        gid = f"nba:{sg['gameId']}"
        stub = {"start_time": sg["gameTimeUTC"], "home": sg["homeTeam"]["teamTricode"],
                "away": sg["awayTeam"]["teamTricode"]}
        _, folder = game_folder(stub)
        if gid in queued or folder.exists():
            print(f"skip {label}: already built ({folder.relative_to(ROOT)})")
            continue
        start = datetime.fromisoformat(sg["gameTimeUTC"].replace("Z", "+00:00"))
        if now - start > timedelta(hours=36):
            print(f"skip {label}: too old")
            continue
        game = to_game(get(BOXSCORE.format(sg["gameId"])))
        tops = {t: sorted(ps, key=lambda p: p["stats"]["points"], reverse=True)[:2]
                for t, ps in game["player_stats"].items()}
        print(f"FINAL {label} {game['score']} top: "
              + "; ".join(f"{p['name']} {p['stats']['points']}" for ps in tops.values() for p in ps))
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
