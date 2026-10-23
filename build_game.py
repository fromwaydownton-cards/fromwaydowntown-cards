"""Build post-game cards for the top 2 scorers on each team.

Input: a game_stats JSON (the sports data format: home, away, score,
player_stats{team: [{name, stats}]}) plus "date", e.g. "Oct 21, 2026". Output: one card per player plus a
caption file for the game, in outdir/<AWAY>_at_<HOME>/.

Usage: python3 build_game.py game.json outdir [handle]
"""
import json
import sys
from pathlib import Path

from make_card import render


def box(stats):
    g = lambda k: stats.get(k, 0)
    return {
        "pts": g("points"), "reb": g("rebounds"), "ast": g("assists"),
        "fgm": g("field_goals_made"), "fga": g("field_goals_att"),
        "3pm": g("three_points_made"), "3pa": g("three_points_att"),
        "blk": g("blocks"), "stl": g("steals"), "tov": g("turnovers"),
        "pf": g("personal_fouls"), "gmsc": round(g("efficiency_game_score"), 1),
    }


def build(game, outdir, handle="@FROMWAYDOWNTOWN"):
    home, away = game["home"], game["away"]
    sc = game["score"]
    winner, loser = (home, away) if sc[home] > sc[away] else (away, home)
    matchup = f"{winner} {sc[winner]}, {loser} {sc[loser]}"
    folder = Path(outdir) / f"{away}_at_{home}"
    folder.mkdir(parents=True, exist_ok=True)

    order, made = [], []
    for team in (winner, loser):
        players = sorted(game["player_stats"][team],
                         key=lambda p: p["stats"].get("points", 0), reverse=True)[:2]
        for p in players:
            order.append((team, p))

    for i, (team, p) in enumerate(order, 1):
        slug = f"{i}_{p['name'].split()[-1].lower().replace('.', '')}"
        card = {"slug": slug, "player": p["name"], "team": team,
                "matchup": matchup, "date": game["date"],
                "box": box(p["stats"]), "handle": handle}
        render(card, folder)
        b = card["box"]
        made.append(f"{p['name']} ({team}): {b['pts']} pts, {b['reb']} reb, {b['ast']} ast")

    caption = (f"{matchup}. Top scorers from both sides. Swipe through.\n\n"
               + "\n".join(made)
               + f"\n\n#NBA #{winner} #{loser} #hoops")
    (folder / "caption.txt").write_text(caption)
    return folder, made


if __name__ == "__main__":
    game = json.loads(Path(sys.argv[1]).read_text())
    folder, made = build(game, sys.argv[2], *(sys.argv[3:4]))
    print(folder)
    print("\n".join(made))
