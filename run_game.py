"""Build one game's carousel into the repo and print what to post.

Usage: python3 run_game.py game.json
game.json: {"id", "start_time" (ISO UTC), "home", "away", "score",
            "player_stats": {TEAM: [{"name", "stats": {...}}]}}
Prints a JSON blob: folder, image URLs (in carousel order), caption, title.
"""
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from build_game import build

RAW = "https://raw.githubusercontent.com/fromwaydownton-cards/fromwaydowntown-cards/main/"
TEAM_NAMES = {
    "ATL": "Hawks", "BOS": "Celtics", "BKN": "Nets", "CHA": "Hornets", "CHI": "Bulls",
    "CLE": "Cavaliers", "DAL": "Mavericks", "DEN": "Nuggets", "DET": "Pistons",
    "GSW": "Warriors", "HOU": "Rockets", "IND": "Pacers", "LAC": "Clippers",
    "LAL": "Lakers", "MEM": "Grizzlies", "MIA": "Heat", "MIL": "Bucks",
    "MIN": "Timberwolves", "NOP": "Pelicans", "NYK": "Knicks", "OKC": "Thunder",
    "ORL": "Magic", "PHI": "76ers", "PHX": "Suns", "POR": "Trail Blazers",
    "SAC": "Kings", "SAS": "Spurs", "TOR": "Raptors", "UTA": "Jazz", "WAS": "Wizards",
}

game = json.loads(Path(sys.argv[1]).read_text())
start = datetime.fromisoformat(game["start_time"]).astimezone(ZoneInfo("America/Chicago"))
game["date"] = start.strftime("%b %-d, %Y")
day_dir = Path("cards") / start.strftime("%Y-%m-%d")

folder, made = build(game, day_dir)
pngs = sorted(folder.glob("*.jpg"))
sc, home, away = game["score"], game["home"], game["away"]
win, lose = (home, away) if sc[home] > sc[away] else (away, home)
print(json.dumps({
    "game_id": game["id"],
    "folder": str(folder),
    "images": [RAW + str(p) for p in pngs],
    "caption": (folder / "caption.txt").read_text(),
    "title": f"{TEAM_NAMES[win]} {sc[win]}, {TEAM_NAMES[lose]} {sc[lose]}",
}, indent=2))
