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

ROOT = Path(__file__).resolve().parent
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


def game_folder(game):
    start = datetime.fromisoformat(game["start_time"].replace("Z", "+00:00"))
    start = start.astimezone(ZoneInfo("America/Chicago"))
    return start, ROOT / "cards" / start.strftime("%Y-%m-%d") / f"{game['away']}_at_{game['home']}"


def make(game):
    start, folder = game_folder(game)
    game = dict(game, date=start.strftime("%b %-d, %Y"))
    build(game, folder.parent)
    imgs = sorted(folder.glob("*.jpg"))
    sc, home, away = game["score"], game["home"], game["away"]
    win, lose = (home, away) if sc[home] > sc[away] else (away, home)
    return {
        "game_id": game["id"],
        "folder": str(folder.relative_to(ROOT)),
        "images": [RAW + str(p.relative_to(ROOT)) for p in imgs],
        "caption": (folder / "caption.txt").read_text(),
        "title": f"{TEAM_NAMES.get(win, win)} {sc[win]}, {TEAM_NAMES.get(lose, lose)} {sc[lose]}",
    }


if __name__ == "__main__":
    print(json.dumps(make(json.loads(Path(sys.argv[1]).read_text())), indent=2))
