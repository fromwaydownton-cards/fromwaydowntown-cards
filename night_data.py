"""Collect one NBA night from ESPN: every game, final scores, full box scores
(with +/-) and headshots for the players who end up on the graphic.

Usage: python3 night_data.py YYYYMMDD     (ESPN/US-Eastern game date)
Writes data/nights/YYYYMMDD.json and data/headshots/<espn id>.png
Prints "ALL_FINAL" or "NOT_FINAL" as the last line.
"""
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={}"
SUMMARY = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={}"
HEADSHOT = "https://a.espncdn.com/i/headshots/nba/players/full/{}.png"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/129.0 Safari/537.36"}
ESPN_ABBR = {"GS": "GSW", "NY": "NYK", "SA": "SAS", "NO": "NOP", "UTAH": "UTA",
             "WSH": "WAS", "PHO": "PHX", "BRK": "BKN", "CHO": "CHA"}


def fetch(url, raw=False):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read() if raw else json.load(r)


def team(abbr):
    return ESPN_ABBR.get(abbr, abbr)


def split(s):
    a, b = s.split("-")
    return int(a), int(b)


def parse_players(summ):
    out = []
    for block in summ["boxscore"].get("players", []):
        abbr = team(block["team"]["abbreviation"])
        st = block["statistics"][0]
        idx = {k: i for i, k in enumerate(st["labels"])}
        for a in st["athletes"]:
            v = a.get("stats") or []
            if a.get("didNotPlay") or not v or v[idx["MIN"]] in ("", "0", "--"):
                continue
            fgm, fga = split(v[idx["FG"]])
            tpm, tpa = split(v[idx["3PT"]])
            pm = v[idx["+/-"]].replace("+", "") if "+/-" in idx else "0"
            out.append({
                "id": a["athlete"]["id"], "name": a["athlete"]["displayName"], "team": abbr,
                "headshot": (a["athlete"].get("headshot") or {}).get("href") or HEADSHOT.format(a["athlete"]["id"]),
                "pts": int(v[idx["PTS"]]), "reb": int(v[idx["REB"]]), "ast": int(v[idx["AST"]]),
                "stl": int(v[idx["STL"]]), "blk": int(v[idx["BLK"]]), "tov": int(v[idx["TO"]]),
                "fgm": fgm, "fga": fga, "tpm": tpm, "tpa": tpa, "pm": int(pm or 0),
            })
    return out


def collect(date):
    sb = fetch(SCOREBOARD.format(date))
    games, players, all_final = [], [], True
    for ev in sb.get("events", []):
        comp = ev["competitions"][0]
        t = {c["homeAway"]: c for c in comp["competitors"]}
        final = comp["status"]["type"].get("completed", False)
        dead = comp["status"]["type"].get("name") in ("STATUS_POSTPONED", "STATUS_CANCELED",
                                                        "STATUS_SUSPENDED", "STATUS_FORFEIT")
        if dead:
            continue
        all_final &= final
        g = {"id": ev["id"], "start": ev["date"], "final": final,
             "status": comp["status"]["type"].get("shortDetail", ""),
             "home": team(t["home"]["team"]["abbreviation"]), "away": team(t["away"]["team"]["abbreviation"]),
             "home_score": int(t["home"].get("score") or 0), "away_score": int(t["away"].get("score") or 0)}
        games.append(g)
        if final:
            for p in parse_players(fetch(SUMMARY.format(ev["id"]))):
                p["game"] = ev["id"]
                players.append(p)
    night = {"date": date, "games": games, "players": players, "all_final": all_final and bool(games)}
    (ROOT / "data" / "nights").mkdir(parents=True, exist_ok=True)
    (ROOT / "data" / "nights" / f"{date}.json").write_text(json.dumps(night, indent=1))
    return night


def save_headshots(ids_urls):
    d = ROOT / "data" / "headshots"
    d.mkdir(parents=True, exist_ok=True)
    for pid, url in ids_urls:
        f = d / f"{pid}.png"
        if f.exists():
            continue
        try:
            f.write_bytes(fetch(url, raw=True))
            print("headshot", pid, f.stat().st_size, "bytes")
        except Exception as e:
            print("headshot FAILED", pid, url, e)


if __name__ == "__main__":
    from leaders import pick
    night = collect(sys.argv[1])
    print(len(night["games"]), "games,", len(night["players"]), "player lines")
    if night["players"]:
        leaders = pick(night["players"])
        for k, p in leaders.items():
            print(f"{k}: {p['name']} ({p['team']}) {p['pts']}p {p['reb']}r {p['ast']}a "
                  f"{p['tpm']}-{p['tpa']} 3pt {p['pm']:+d}")
        save_headshots([(p["id"], p["headshot"]) for p in leaders.values()])
    print("ALL_FINAL" if night["all_final"] else "NOT_FINAL")
